"""Registro de eventos con marca de tiempo (R7, FR-009).

Cada caso tiene su propio `RegistroEventos`. `secuencia` es un entero creciente, único por caso:
da un orden estable aunque dos marcas coincidan. El reloj se inyecta para los tests.
"""

import threading
from collections.abc import Callable
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


def _ahora() -> datetime:
    return datetime.now(UTC)


class RegistroEventos:
    def __init__(self, reloj: Callable[[], datetime] | None = None) -> None:
        self._reloj = reloj or _ahora
        self._eventos: list[Evento] = []
        self._candado = threading.Lock()

    def registrar(
        self,
        tipo: str,
        frente: Frente | None = None,
        detalle: str = "",
        regla: str | None = None,
    ) -> Evento:
        if tipo not in TIPOS:
            raise TipoDeEventoInvalido(f"Tipo de evento desconocido: {tipo!r}.")
        with self._candado:
            evento = Evento(len(self._eventos) + 1, self._reloj(), tipo, frente, detalle, regla)
            self._eventos.append(evento)
        return evento

    def eventos(self) -> list[Evento]:
        with self._candado:
            return list(self._eventos)
