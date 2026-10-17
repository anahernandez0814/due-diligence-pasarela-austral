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


def _ahora() -> datetime:
    return datetime.now(UTC)


class RegistroEventos:
    def __init__(self, reloj: Callable[[], datetime] | None = None) -> None:
        self._reloj = reloj or _ahora
        self._eventos: list[Evento] = []
        self._candado = threading.Lock()

    def registrar(self, tipo: str, frente: Frente | None = None, detalle: str = "") -> Evento:
        if tipo not in TIPOS:
            raise TipoDeEventoInvalido(f"Tipo de evento desconocido: {tipo!r}.")
        with self._candado:
            evento = Evento(len(self._eventos) + 1, self._reloj(), tipo, frente, detalle)
            self._eventos.append(evento)
        return evento

    def eventos(self) -> list[Evento]:
        with self._candado:
            return list(self._eventos)
