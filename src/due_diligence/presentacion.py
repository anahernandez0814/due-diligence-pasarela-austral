"""Lo que muestra la interfaz de chat, en funciones puras (#11, R2).

Convierten la traza de eventos y el estado del `Caso` en indicadores, cobertura, estado del caso y
turnos, y deciden qué hacer con un mensaje del analista. No importan Streamlit, no llaman al modelo
y no leen el entorno por su cuenta: `chat.py` solo dibuja lo que devuelven, y `__main__` usa los
mismos textos donde coinciden. Lo que se muestra sale de la traza y del estado, nunca del texto del
modelo (R3, R4).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import TYPE_CHECKING

from due_diligence import configuracion
from due_diligence.cobertura import CoberturaCaso
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_DELEGACION,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_FALLO_DE_HOOK,
    TIPO_INFORME_REGISTRADO,
    TIPO_MENSAJE_ANALISTA,
    Evento,
)
from due_diligence.frentes import Frente
from due_diligence.informe import informe_vigente
from due_diligence.terminacion import Terminacion

if TYPE_CHECKING:
    from due_diligence.coordinador import Caso
    from due_diligence.reglas import Espera

# Colombia no tiene horario de verano: una zona fija evita depender de `tzdata`, que `zoneinfo`
# necesita en Windows (R9). La traza y los registros siguen en UTC (#9, R10).
ZONA_COLOMBIA = timezone(timedelta(hours=-5))

FRENTES_EN_PALABRAS = {
    Frente.REGISTRO: "registro mercantil",
    Frente.LISTAS: "listas restrictivas",
    Frente.NOTICIAS: "noticias",
    Frente.CATEGORIA: "riesgo de categoría",
}

# Clases del estado del caso (R4).
COMPLETO, INCOMPLETO, ESPERANDO = "completo", "incompleto", "esperando"

# Textos fijos de la conversación (R6). `MENSAJE_SIN_SESION` es el del #10, que `__main__` importa.
AVISO_CASO_NUEVO = "Caso anterior cerrado; se inició un caso nuevo."
# #12 (R9, opción A): tras un turno cortado con «Stop», el siguiente mensaje abre un caso nuevo y
# nunca reanuda una sesión del coordinador que quedó a mitad de una herramienta.
AVISO_TURNO_INTERRUMPIDO = "El turno anterior se interrumpió; se inició un caso nuevo."
MENSAJE_TURNO_INTERRUMPIDO = (
    "Turno interrumpido por el analista. El caso queda sin completar; el siguiente mensaje inicia "
    "un caso nuevo."
)
# Dos oraciones, sin unir dos «dos puntos» seguidos: el motivo ya lleva los suyos (validación).
AVISO_ESPERA = "El coordinador espera su respuesta. {motivo} El caso sigue sin completar."
MENSAJE_FALLO_TURNO = (
    "El turno falló por un error del sistema ({tipo}). El caso queda incompleto; puede escribir de "
    "nuevo o iniciar un caso nuevo."
)
MENSAJE_SIN_SESION = (
    "No se puede continuar el caso: el turno anterior no dejó una sesión del coordinador que "
    "reanudar. El caso queda como está, sin completar; inicie uno nuevo con la solicitud completa."
)


class Decision(StrEnum):
    """Qué hacer con un mensaje del analista (R6)."""

    NUEVO = "nuevo"
    CONTINUAR = "continuar"
    AVISO_ESPERA = "aviso_espera"
    IGNORAR = "ignorar"


@dataclass(frozen=True)
class DecisionMensaje:
    accion: Decision
    aviso: str | None = None


@dataclass(frozen=True)
class Indicador:
    """Algo que hizo el sistema, visible en la conversación (R3). Sale de un evento de la traza."""

    tipo: str  # delegacion, bloqueo, informe, escalamiento o aviso
    titulo: str
    detalle: str
    hora: str
    secuencia: int


@dataclass(frozen=True)
class FilaCobertura:
    frente: str  # en palabras
    cubierto: bool
    motivo: str  # vacío si está cubierto


@dataclass(frozen=True)
class EstadoMostrado:
    clase: str  # completo, incompleto o esperando; «completo» si y solo si `caso.completo`
    texto: str


@dataclass(frozen=True)
class TurnoMostrado:
    """Un turno tal como se dibuja: mensaje → aviso → indicadores → cobertura → estado → respuesta
    → turnos (data-model)."""

    numero: int
    mensaje: str
    aviso: str | None
    indicadores: tuple[Indicador, ...]
    cobertura: tuple[FilaCobertura, ...]
    estado: EstadoMostrado
    respuesta: str
    turnos: str


def hora_colombia(marca: datetime) -> str:
    """La hora de un evento en hora de Colombia, con la zona declarada (FR-007)."""
    return f"{marca.astimezone(ZONA_COLOMBIA):%H:%M:%S} (hora de Colombia)"


def frente_en_palabras(frente: Frente) -> str:
    return FRENTES_EN_PALABRAS[frente]


def aviso_espera(espera: "Espera") -> str:
    """El aviso ante un mensaje vacío con la espera abierta (chat y línea de comandos)."""
    return AVISO_ESPERA.format(motivo=espera.motivo)


# Los tipos de error de la pasarela y del ejecutor, en palabras (validación manual: el chat
# mostraba el código interno). Un tipo que no está aquí se deja tal cual.
ERRORES_EN_PALABRAS = {
    "servicio_no_disponible": "el servicio no está disponible",
    "datos_no_disponibles": "la fuente no tiene datos disponibles",
    "entrada_invalida": "la consulta tenía una entrada inválida",
    "campos_obligatorios_ausentes": "faltaban campos obligatorios en la consulta",
    "error_interno": "error interno de la fuente",
    "error_de_almacenamiento": "no se pudo guardar el registro",
    "error_de_herramienta": "la herramienta devolvió un error",
}
_TIPOS_DE_ERROR = re.compile(r"\(([a-z_]+(?:, [a-z_]+)*)\)")


def _motivo_en_palabras(motivo: str) -> str:
    """El motivo de la cobertura con los tipos de error conocidos en palabras.

    `cobertura.py` los pone entre paréntesis («error de la fuente (servicio_no_disponible)»); la
    cobertura registrada no cambia, solo lo que se muestra.
    """

    def traducir(encontrado: re.Match[str]) -> str:
        tipos = encontrado.group(1).split(", ")
        return f"({', '.join(ERRORES_EN_PALABRAS.get(t, t) for t in tipos)})"

    return _TIPOS_DE_ERROR.sub(traducir, motivo)


def _detalle_de_delegacion(detalle: str) -> str:
    """Solo lo que aporta: el título ya nombra el frente en palabras.

    `delegacion.py` escribe «Se delega el frente X.», «Se reintenta el frente X con la misma
    entrada.» o «Se vuelve a delegar el frente X con otra entrada.», con el nombre interno del
    frente; aquí no se repite.
    """
    if detalle.startswith("Se reintenta"):
        return "Reintento con la misma entrada, tras un error que se puede reintentar."
    if "con otra entrada" in detalle:
        return "Se vuelve a delegar con otra entrada."
    return ""


def mensaje_fallo_turno(error: BaseException) -> str:
    """Un turno que falló, explicado sin traza: solo el tipo del error (FR-001)."""
    return MENSAJE_FALLO_TURNO.format(tipo=type(error).__name__)


def _titulo_bloqueo(evento: Evento) -> str:
    regla = f"la regla {evento.regla}" if evento.regla else "una regla de negocio"
    accion = f": {evento.accion}" if evento.accion else ""
    return f"Bloqueado por {regla}{accion}"


def indicador(evento: Evento) -> Indicador | None:
    """El indicador de un evento, o `None` si el evento no es uno (mapa de R3).

    Los demás eventos (frentes que fallaron, esperas, terminación) los muestran la cobertura y el
    estado del caso. El título no añade datos del comercio: el detalle es el del evento, con los
    textos fijos de las reglas, y la acción intentada no lleva datos del comercio (#9, FR-017).
    """
    detalle = evento.detalle
    if evento.tipo == TIPO_DELEGACION:
        frente = frente_en_palabras(evento.frente) if evento.frente else "un frente"
        tipo, titulo = "delegacion", f"Delegación al subagente de {frente}"
        detalle = _detalle_de_delegacion(detalle)
    elif evento.tipo == TIPO_BLOQUEO_REGLA:
        tipo, titulo = "bloqueo", _titulo_bloqueo(evento)
    elif evento.tipo == TIPO_INFORME_REGISTRADO:
        tipo, titulo = "informe", "Informe registrado"
    elif evento.tipo == TIPO_ESCALAMIENTO_REGISTRADO:
        tipo, titulo = "escalamiento", "Caso escalado a cumplimiento"
    elif evento.tipo == TIPO_FALLO_DE_HOOK:
        tipo = "aviso"
        titulo = "Un control de las reglas falló; el caso se bloqueó por precaución"
    else:
        return None
    return Indicador(tipo, titulo, detalle, hora_colombia(evento.marca), evento.secuencia)


def eventos_del_turno(eventos: Sequence[Evento], n: int) -> list[Evento]:
    """Los eventos del turno `n` (desde 1): del `mensaje_analista` n hasta antes del siguiente.

    Los anteriores al primer mensaje (`caso_iniciado`, `modo_demostracion`) van con el turno 1.
    """
    turno, del_turno = 1, []
    vistos = 0
    for evento in eventos:
        if evento.tipo == TIPO_MENSAJE_ANALISTA:
            vistos += 1
            turno = vistos
        if turno == n:
            del_turno.append(evento)
    return del_turno


def filas_cobertura(cobertura: CoberturaCaso) -> tuple[FilaCobertura, ...]:
    """La cobertura calculada por el sistema (la que se registra), un frente por fila (FR-003).

    El motivo de un frente sin cubrir lleva los tipos de error en palabras.
    """
    return tuple(
        FilaCobertura(
            frente_en_palabras(c.frente),
            c.cubierto,
            "" if c.cubierto else _motivo_en_palabras(c.motivo),
        )
        for c in cobertura.frentes.values()
    )


def _lo_que_falta(caso: "Caso") -> list[str]:
    estado = caso.estado
    faltas = []
    if estado.terminacion is None:
        faltas.append("el turno no terminó")
    if not caso.cobertura.completa:
        faltas.append("hay frentes sin cubrir")
    if estado.cierre_sin_escalar:
        faltas.append("terminó sin el escalamiento obligatorio")
    if estado.cierre_sin_informe:
        faltas.append("terminó sin el informe vigente")
    if not informe_vigente(estado) and not estado.cierre_sin_informe:
        faltas.append("no hay un informe vigente")
    return faltas


def estado_mostrado(caso: "Caso") -> EstadoMostrado:
    """El estado del caso al terminar el turno, en el orden de R4.

    «Completo» si y solo si `caso.completo` (I.5): las ramas anteriores solo se dan con el caso
    incompleto, porque `completo` exige que no haya fallo de hook, ni espera, ni terminación
    anómala.
    """
    estado = caso.estado
    if estado.libro.fallo_de_hook is not None:
        return EstadoMostrado(
            INCOMPLETO,
            "Incompleto: un control de las reglas falló y el caso se bloqueó por precaución.",
        )
    espera = caso.espera
    if espera is not None:
        # Dos oraciones: el motivo ya lleva sus dos puntos (validación manual).
        return EstadoMostrado(ESPERANDO, f"Esperando al analista. {espera.motivo}")
    terminacion = estado.terminacion
    if terminacion is not None and terminacion.terminacion is not Terminacion.NORMAL:
        return EstadoMostrado(
            INCOMPLETO, f"Incompleto: el turno terminó de forma anómala ({terminacion.detalle})."
        )
    if caso.completo:
        return EstadoMostrado(COMPLETO, "Completo.")
    faltas = _lo_que_falta(caso) or ["el caso no cumple las condiciones de completo"]
    return EstadoMostrado(INCOMPLETO, f"Incompleto: {'; '.join(faltas)}.")


def resumen_del_turno(
    caso: "Caso",
    n: int,
    mensaje: str,
    aviso: str | None = None,
    respuesta: str | None = None,
) -> TurnoMostrado:
    """El turno `n` del caso tal como se guarda en el historial: todo sale de la traza (R1, R4).

    `turnos` es el del turno `n` frente al límite, nunca la suma del caso (FR-004).
    """
    eventos = eventos_del_turno(caso.eventos(), n)
    indicadores = tuple(i for i in map(indicador, eventos) if i is not None)
    por_turno = caso.turnos_por_turno
    turnos = por_turno[n - 1] if n <= len(por_turno) else None
    return TurnoMostrado(
        numero=n,
        mensaje=mensaje,
        aviso=aviso,
        indicadores=indicadores,
        cobertura=filas_cobertura(caso.cobertura),
        estado=estado_mostrado(caso),
        respuesta=caso.respuesta if respuesta is None else respuesta,
        turnos=configuracion.turnos_usados(turnos),
    )


def decidir_mensaje(caso: "Caso | None", texto: str) -> DecisionMensaje:
    """Qué hacer con un mensaje del analista (R6, FR-001, FR-005, US1-3).

    - Vacío o solo espacios: si el caso espera al analista, se avisa y no se llama al coordinador;
      si no, se ignora.
    - Sin caso, o con el caso anterior **completo**: caso nuevo; en el segundo, con aviso (decisión
      de la analista: con D1 del #10, las coincidencias de un comercio anterior siguen siendo causas
      del caso, y un caso de prueba heredaría el escalamiento del anterior).
    - Con el caso incompleto o en espera: se continúa el mismo caso.
    - #12 (R9, opción A): con el último turno interrumpido, caso nuevo con aviso, aunque esperara al
      analista: la sesión del coordinador quedó cortada a mitad de una herramienta.
    """
    if not texto.strip():
        espera = caso.espera if caso is not None else None
        if espera is not None:
            return DecisionMensaje(Decision.AVISO_ESPERA, aviso_espera(espera))
        return DecisionMensaje(Decision.IGNORAR)
    if caso is None:
        return DecisionMensaje(Decision.NUEVO)
    if caso.interrumpido:
        return DecisionMensaje(Decision.NUEVO, AVISO_TURNO_INTERRUMPIDO)
    if caso.completo:
        return DecisionMensaje(Decision.NUEVO, AVISO_CASO_NUEVO)
    return DecisionMensaje(Decision.CONTINUAR)


# Los modos de simulación que la interfaz muestra en una franja fija (R12, FR-010). Se activan con
# el valor exacto «1», como en el servidor (`noticias.py`, `registro.py`) y en
# `configuracion.modo_demostracion`, y se leen al arrancar: cambiarlos exige reiniciar.
MODOS = (
    ("PASARELA_FALLA_NOTICIAS", "Caída simulada de noticias activa (caso f)."),
    ("PASARELA_FALLA_REGISTRO", "Caída simulada del registro mercantil activa."),
    (
        configuracion.VARIABLE_MODO_DEMO,
        "Modo de demostración de hooks activo (caso e): las reglas no están en las instrucciones "
        "del coordinador; los hooks siguen activos.",
    ),
)


def modos_activos(entorno: Mapping[str, str]) -> list[str]:
    """Una línea por cada modo de simulación activo, en el orden de `MODOS`."""
    return [texto for variable, texto in MODOS if entorno.get(variable, "") == "1"]
