"""Estado compartido de un caso (R6, R7, data-model, FR-007, FR-008, FR-014).

Un `EstadoCaso` por `Caso`, sin variables de módulo. Guarda la situación de cada frente, los
resultados (con el contenido separado de los metadatos, tal como los entrega el servidor) y las
consultas realizadas. Los hooks del #7 y la interfaz lo leen con `instantanea()`.
"""

import copy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from due_diligence.frentes import Frente
from due_diligence.libro import LibroReglas

if TYPE_CHECKING:
    from due_diligence.terminacion import Clasificacion


class Situacion(StrEnum):
    SIN_INICIAR = "sin_iniciar"  # aún no delegado
    EN_CURSO = "en_curso"
    TERMINADO = "terminado"
    NO_TERMINADO = "no_terminado"
    RECHAZADO = "rechazado"  # la última delegación se rechazó, con un motivo


# Transiciones permitidas. `rechazado` puede volver a delegarse con el dato corregido, y un frente
# terminado o no terminado, volver a ejecutarse cuando se delega con otra entrada. Uno terminado
# pasa a no terminado si lo que lo sustenta cambia (listas, si cambia el comercio del registro), y
# uno no terminado sigue no terminado con el motivo nuevo en el mismo caso, como `rechazado` (#8:
# antes, listas fallido e invalidado después lanzaba `TransicionInvalida`).
_TRANSICIONES: dict[Situacion, frozenset[Situacion]] = {
    Situacion.SIN_INICIAR: frozenset({Situacion.EN_CURSO, Situacion.RECHAZADO}),
    Situacion.EN_CURSO: frozenset({Situacion.TERMINADO, Situacion.NO_TERMINADO}),
    Situacion.TERMINADO: frozenset({Situacion.EN_CURSO, Situacion.NO_TERMINADO}),
    Situacion.NO_TERMINADO: frozenset({Situacion.EN_CURSO, Situacion.NO_TERMINADO}),
    Situacion.RECHAZADO: frozenset({Situacion.EN_CURSO, Situacion.RECHAZADO}),
}


class Causa(StrEnum):
    """Por qué un frente no quedó cubierto: el «tipo de error» de FR-002 (#8, R4, data-model).

    Conjunto cerrado. Vive aquí, y no en la delegación, para que `cobertura.py` lo use sin
    importarla. El campo `tipo` del error se conserva por compatibilidad con el #6.
    """

    TERMINACION_ANOMALA = "terminacion_anomala"
    ERROR_DE_FUENTE = "error_de_fuente"
    SIN_CONSULTAS = "sin_consultas"
    RESULTADO_INVALIDO = "resultado_invalido"
    CONSULTA_INCOMPLETA = "consulta_incompleta"
    RECHAZADO = "rechazado"
    CANCELADO = "cancelado"
    INVALIDADO = "invalidado"


class TransicionInvalida(ValueError):
    """Cambio de situación que el modelo no permite."""


@dataclass
class Consulta:
    """Una llamada a una herramienta de la pasarela hecha por un subagente."""

    frente: Frente
    herramienta: str
    argumentos: dict[str, Any]
    resultado: dict[str, Any] | None
    valido: bool
    # Error estructurado de la pasarela tal como llegó (error, tipo, mensaje, reintentable,
    # obtenido); None si la herramienta no devolvió uno.
    error: dict[str, Any] | None = None


@dataclass
class ResultadoFrente:
    """Lo que devuelve un ejecutor al terminar un subagente."""

    frente: Frente
    consultas: list[Consulta]
    resumen: str  # texto del modelo: solo informativo, nunca decide nada
    terminacion: "Clasificacion | None"
    detalle_terminacion: str
    coste_usd: float | None = None  # `total_cost_usd` del subagente, si el SDK lo informó


@dataclass(frozen=True)
class Identificacion:
    """Lo que `derivar_comercio` devolvió para una consulta válida del registro (R4).

    `con_coincidencias` dice si esa respuesta traía coincidencias; la consolidación de varias
    consultas ignora las que no las tienen, como hacía el #6.
    """

    comercio: dict[str, Any] | None
    motivo: str
    con_coincidencias: bool


@dataclass
class EstadoCaso:
    solicitud: str = ""
    terminacion: "Clasificacion | None" = None
    # Identificaciones registradas por el hook del registro (único escritor, R4). `comercio` y
    # `motivo_comercio` se derivan de ellas y de la situación del frente de registro.
    identificaciones: list[Identificacion] = field(default_factory=list)
    # Lo que los hooks de las reglas registran para decidir I.1, I.2 e I.3 (data-model).
    libro: LibroReglas = field(default_factory=LibroReglas)
    # El `Stop` agotó `MAX_CIERRES_IMPEDIDOS` sin que el caso estuviera escalado (R3).
    cierre_sin_escalar: bool = False
    resultados: dict[Frente, ResultadoFrente] = field(default_factory=dict)
    consultas: list[Consulta] = field(default_factory=list)
    # Último error estructurado de cada frente no cubierto (#8, data-model `ErrorFrente`). Lo
    # escribe la delegación; un frente que termina con normalidad borra su entrada.
    errores: dict[Frente, dict[str, Any]] = field(default_factory=dict)
    _situaciones: dict[Frente, Situacion] = field(
        default_factory=lambda: {f: Situacion.SIN_INICIAR for f in Frente}
    )
    _motivos: dict[Frente, str] = field(default_factory=dict)

    @property
    def frentes(self) -> dict[Frente, Situacion]:
        return dict(self._situaciones)

    def situacion(self, frente: Frente) -> Situacion:
        return self._situaciones[frente]

    def motivo(self, frente: Frente) -> str:
        return self._motivos.get(frente, "")

    def cambiar_situacion(self, frente: Frente, nueva: Situacion, motivo: str = "") -> None:
        actual = self._situaciones[frente]
        if nueva not in _TRANSICIONES[actual]:
            raise TransicionInvalida(
                f"El frente {frente.value} no puede pasar de {actual.value} a {nueva.value}."
            )
        self._situaciones[frente] = nueva
        self._motivos[frente] = motivo

    def guardar_resultado(self, resultado: ResultadoFrente) -> None:
        self.resultados[resultado.frente] = resultado

    def agregar_consultas(self, consultas: list[Consulta]) -> None:
        self.consultas.extend(consultas)

    def registrar_identificacion(self, respuesta: Any) -> None:
        """Guarda lo que `derivar_comercio` devuelve para una respuesta del registro (R4).

        `derivar_comercio` es el único intérprete: aquí no se decide nada sobre la respuesta.
        """
        comercio, motivo = derivar_comercio(respuesta)
        con_coincidencias = isinstance(respuesta, dict) and bool(respuesta.get("coincidencias"))
        self.identificaciones.append(Identificacion(comercio, motivo, con_coincidencias))

    def reiniciar_identificacion(self) -> None:
        """Olvida las identificaciones: el registro se vuelve a delegar con otra entrada."""
        self.identificaciones.clear()

    def _consolidar_comercio(self) -> tuple[dict[str, Any] | None, str]:
        """(comercio, motivo) del caso. Es la lógica de `_fijar_comercio` del #6, movida aquí.

        Solo hay comercio si el registro terminó con normalidad y todas las consultas con
        coincidencias identifican al mismo (principios I.1 e I.4: no se elige una).
        """
        if self.situacion(Frente.REGISTRO) is not Situacion.TERMINADO:
            motivo = self.motivo(Frente.REGISTRO)
            return None, f"El registro mercantil no terminó. {motivo}".strip()
        if not self.identificaciones:
            return None, "El registro no devolvió datos."
        derivadas = [i for i in self.identificaciones if i.con_coincidencias]
        if not derivadas:
            derivadas = self.identificaciones[:1]
        for identificacion in derivadas:
            if identificacion.comercio is None:
                return None, identificacion.motivo
        if any(i.comercio != derivadas[0].comercio for i in derivadas):
            return None, (
                "Las consultas del registro identifican comercios distintos: no se elige uno; "
                "hace falta el identificador."
            )
        return derivadas[0].comercio, ""

    @property
    def comercio(self) -> dict[str, Any] | None:
        return self._consolidar_comercio()[0]

    @property
    def motivo_comercio(self) -> str:
        return self._consolidar_comercio()[1]

    def instantanea(self) -> "EstadoCaso":
        """Copia independiente: modificarla no cambia el estado del caso."""
        return copy.deepcopy(self)


def derivar_comercio(resultado: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str]:
    """(comercio, motivo) a partir del resultado del registro, tal como lo devolvió (FR-005).

    Solo hay comercio con una coincidencia única y sin contradicción entre las fuentes registrales
    en el nombre o el representante legal (principio I.4: no se elige entre fuentes). Si no, el
    comercio es `None` y el motivo dice por qué.
    """
    if not isinstance(resultado, dict) or not isinstance(resultado.get("hechos"), list):
        return None, "El resultado del registro mercantil no tiene la forma esperada."
    coincidencias = resultado.get("coincidencias") or []
    if resultado.get("resultado") != "coincidencias" or not coincidencias:
        return None, "El registro mercantil no devolvió ninguna coincidencia."
    if len(coincidencias) != 1:
        return None, (
            "El registro mercantil devolvió varias coincidencias "
            f"({', '.join(map(str, coincidencias))}): "
            "no se elige una; hace falta el identificador."
        )
    contenidos = [
        h.get("contenido", {})
        for h in resultado["hechos"]
        if isinstance(h, dict) and h.get("contenido", {}).get("identificador") == coincidencias[0]
    ]
    if not contenidos:
        return None, "El resultado del registro mercantil no trae el comercio de la coincidencia."
    versiones = {(c.get("nombre"), _clave(c.get("representante_legal"))) for c in contenidos}
    if len(versiones) != 1:
        return None, (
            "Las fuentes registrales difieren en el nombre o el representante legal: "
            "no se elige una."
        )
    primero = contenidos[0]
    representante = primero.get("representante_legal")
    return {
        "identificador": primero.get("identificador"),
        "nombre": primero.get("nombre"),
        "representante_legal": dict(representante) if representante else None,
    }, ""


def _clave(representante: Any) -> tuple[Any, Any] | None:
    if not representante:
        return None
    return representante.get("nombre"), representante.get("identificador")
