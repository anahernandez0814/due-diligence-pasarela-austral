"""Registro de eventos con marca de tiempo (R7, FR-009).

Cada caso tiene su propio `RegistroEventos`. `secuencia` es un entero creciente, único por caso:
da un orden estable aunque dos marcas coincidan. El reloj se inyecta para los tests.

Desde el #11 (R1) acepta un `observador` opcional que recibe cada evento ya guardado: la interfaz de
chat lo usa para mostrar los indicadores en vivo. La traza sigue siendo la única fuente de verdad.

Desde el #12 (R9) acepta también `interrupciones`: las excepciones de control con las que el punto
de entrada corta el turno (en el chat, la `ScriptControlException` de Streamlit al pulsar «Stop» o
recargar). Si el observador lanza una, se guarda la primera y el evento se devuelve con normalidad:
el hook que registraba sigue y decide, y la interrupción se relanza en cuanto devuelve su decisión.
"""

import threading
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime

from due_diligence.frentes import Frente

TIPO_CASO_INICIADO = "caso_iniciado"
TIPO_DELEGACION = "delegacion"
TIPO_DELEGACION_REPETIDA = "delegacion_repetida"
TIPO_FRENTE_INICIO = "frente_inicio"
TIPO_FRENTE_FIN = "frente_fin"
TIPO_FRENTE_RECHAZADO = "frente_rechazado"
TIPO_FRENTE_INVALIDADO = "frente_invalidado"
TIPO_TERMINACION = "terminacion"
# Eventos de los hooks de las reglas de negocio (#7, R12).
TIPO_BLOQUEO_REGLA = "bloqueo_regla"
TIPO_CIERRE_IMPEDIDO = "cierre_impedido"
TIPO_CIERRE_SIN_ESCALAR = "cierre_sin_escalar"
TIPO_FALLO_DE_HOOK = "fallo_de_hook"
TIPO_ESCALAMIENTO_REGISTRADO = "escalamiento_registrado"
TIPO_MODO_DEMOSTRACION = "modo_demostracion"
# Una herramienta de una regla devolvió un error estructurado (llega por `PostToolUseFailure`, R1).
TIPO_CONSULTA_FALLIDA = "consulta_fallida"
# Errores estructurados y cobertura (#8, data-model). `cobertura_sustituida` se emite en el
# `PreToolUse`, antes de que la pasarela acepte la llamada: dice qué cobertura se puso en ella,
# nunca que quedó registrada.
TIPO_FRENTE_REINTENTO = "frente_reintento"
TIPO_REINTENTO_DENEGADO = "reintento_denegado"
TIPO_COBERTURA_SUSTITUIDA = "cobertura_sustituida"
# Informe con procedencia, conflictos y registro (#9, data-model «Eventos»). `informe_registrado` se
# emite en el `PostToolUse` cuando la pasarela acepta; `datos_sustituidos`, en el `PreToolUse` que
# pone el comercio y los conflictos del código; `cierre_sin_informe`, cuando el `Stop` agota las
# devoluciones con el informe pendiente.
TIPO_INFORME_REGISTRADO = "informe_registrado"
TIPO_DATOS_SUSTITUIDOS = "datos_sustituidos"
TIPO_CIERRE_SIN_INFORME = "cierre_sin_informe"
# Continuación del caso (#10, data-model «Eventos»): `mensaje_analista` al empezar cada turno, sin
# repetir el texto; `espera_analista`, cuando el `Stop` admite una espera del analista (R3).
TIPO_MENSAJE_ANALISTA = "mensaje_analista"
TIPO_ESPERA_ANALISTA = "espera_analista"

TIPOS = frozenset(
    {
        TIPO_CASO_INICIADO,
        TIPO_DELEGACION,
        TIPO_DELEGACION_REPETIDA,
        TIPO_FRENTE_INICIO,
        TIPO_FRENTE_FIN,
        TIPO_FRENTE_RECHAZADO,
        TIPO_FRENTE_INVALIDADO,
        TIPO_TERMINACION,
        TIPO_BLOQUEO_REGLA,
        TIPO_CIERRE_IMPEDIDO,
        TIPO_CIERRE_SIN_ESCALAR,
        TIPO_FALLO_DE_HOOK,
        TIPO_ESCALAMIENTO_REGISTRADO,
        TIPO_MODO_DEMOSTRACION,
        TIPO_CONSULTA_FALLIDA,
        TIPO_FRENTE_REINTENTO,
        TIPO_REINTENTO_DENEGADO,
        TIPO_COBERTURA_SUSTITUIDA,
        TIPO_INFORME_REGISTRADO,
        TIPO_DATOS_SUSTITUIDOS,
        TIPO_CIERRE_SIN_INFORME,
        TIPO_MENSAJE_ANALISTA,
        TIPO_ESPERA_ANALISTA,
    }
)


class TipoDeEventoInvalido(ValueError):
    """Se intentó registrar un tipo de evento que el modelo no define."""


@dataclass(frozen=True)
class Evento:
    secuencia: int
    marca: datetime
    tipo: str
    frente: Frente | None
    detalle: str
    # La regla de negocio que causó el evento ("I.1", "I.2", "I.3" o varias separadas por coma);
    # `None` en los eventos que no son de una regla. Al final para no romper llamadas posicionales.
    regla: str | None = None
    # La acción que un bloqueo impidió, sin datos del comercio (#9, FR-017): por ejemplo
    # «registrar_informe (habilitar)». Último campo, por la misma razón que `regla`.
    accion: str | None = None


def _ahora() -> datetime:
    return datetime.now(UTC)


# La pone `hooks.fallar_cerrado` mientras corre un hook (#12, R9): dentro de un hook, la
# interrupción no se avisa al registrarla sino cuando el hook ya devolvió su decisión.
DENTRO_DE_HOOK: ContextVar[bool] = ContextVar("DENTRO_DE_HOOK", default=False)


class RegistroEventos:
    def __init__(
        self,
        reloj: Callable[[], datetime] | None = None,
        observador: Callable[[Evento], None] | None = None,
        interrupciones: tuple[type[BaseException], ...] = (),
    ) -> None:
        self._reloj = reloj or _ahora
        self._eventos: list[Evento] = []
        self._candado = threading.Lock()
        self._observador = observador
        self.interrupciones = interrupciones
        # La primera interrupción que lanzó el observador (#12, R9) y el aviso que corta el turno;
        # lo pone el `Caso` al empezar cada turno. `interrumpir` lo llama una sola vez.
        self.interrupcion: BaseException | None = None
        self.al_interrumpir: Callable[[], None] | None = None
        self._avisado = False

    def registrar(
        self,
        tipo: str,
        frente: Frente | None = None,
        detalle: str = "",
        regla: str | None = None,
        accion: str | None = None,
    ) -> Evento:
        if tipo not in TIPOS:
            raise TipoDeEventoInvalido(f"Tipo de evento desconocido: {tipo!r}.")
        with self._candado:
            evento = Evento(
                len(self._eventos) + 1, self._reloj(), tipo, frente, detalle, regla, accion
            )
            self._eventos.append(evento)
        # Fuera del `with`: `_candado` no es reentrante, y un observador que registre otro evento o
        # lea la traza bloquearía el hilo para siempre. Su excepción se ignora porque quien registra
        # suele ser un hook: si fallara, `fallar_cerrado` sellaría el caso por un fallo de la vista.
        # Una interrupción declarada se guarda y apaga el observador: con «Stop», cada llamada a
        # Streamlit volvería a lanzarla, y una recarga solo se entrega una vez, así que hay que
        # relanzar este mismo objeto (#12, R9). `asyncio.CancelledError`, `KeyboardInterrupt` y
        # `SystemExit` no se tocan: son la cancelación de las tareas y el fin del proceso, y quien
        # cancela no espera ninguna decisión que entregar.
        if self._observador is not None:
            try:
                self._observador(evento)
            except self.interrupciones as interrupcion:
                self._observador = None
                if self.interrupcion is None:
                    self.interrupcion = interrupcion
                if not DENTRO_DE_HOOK.get():
                    self.interrumpir()
            except Exception:
                pass
        return evento

    def interrumpir(self) -> None:
        """Avisa al `Caso` para que corte el turno, una sola vez y solo si hay una interrupción."""
        if self.interrupcion is None or self._avisado or self.al_interrumpir is None:
            return
        self._avisado = True
        self.al_interrumpir()

    def eventos(self) -> list[Evento]:
        with self._candado:
            return list(self._eventos)
