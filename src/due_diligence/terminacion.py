"""Clasificación del fin de un ciclo agéntico (R5, FR-010 a FR-012).

El ciclo lo ejecuta el Claude Agent SDK: este módulo no controla nada, solo clasifica cómo terminó
según el `subtype` y el `stop_reason` del `ResultMessage` (o de la `ResultError` que el SDK lanza
después). El texto de la respuesta no es un parámetro de ninguna función.

El `subtype` se mira primero: al agotar `max_turns` el SDK entrega `subtype=error_max_turns` con
`stop_reason=tool_use` (medido en R14), no `max_tokens`.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from claude_agent_sdk import ResultMessage
from claude_agent_sdk._errors import ResultError


class Terminacion(StrEnum):
    NORMAL = "normal"
    ANOMALA = "anomala"
    LIMITE_SEGURIDAD = "limite_seguridad"


@dataclass(frozen=True)
class Clasificacion:
    terminacion: Terminacion
    subtype: str | None
    stop_reason: str | None
    terminal_reason: str | None
    is_error: bool

    @property
    def detalle(self) -> str:
        """Los valores originales, para el evento y para quien lea el registro."""
        return (
            f"subtype={self.subtype} stop_reason={self.stop_reason} "
            f"terminal_reason={self.terminal_reason} is_error={self.is_error}"
        )


def clasificar(
    subtype: str | None,
    stop_reason: str | None,
    is_error: bool,
    terminal_reason: str | None,
) -> Clasificacion:
    """Clasifica por `subtype` y `stop_reason`, en este orden:

    1. `error_max_turns` → límite de seguridad (cualquiera sea el `stop_reason`).
    2. `success`, sin error y `end_turn` → normal.
    3. Cualquier otra combinación → anómala (`max_tokens`, `refusal`, `is_error`…).
    """
    if subtype == "error_max_turns":
        terminacion = Terminacion.LIMITE_SEGURIDAD
    elif subtype == "success" and not is_error and stop_reason == "end_turn":
        terminacion = Terminacion.NORMAL
    else:
        terminacion = Terminacion.ANOMALA
    return Clasificacion(terminacion, subtype, stop_reason, terminal_reason, is_error)


def clasificar_resultado(mensaje: ResultMessage) -> Clasificacion:
    return clasificar(
        mensaje.subtype, mensaje.stop_reason, mensaje.is_error, mensaje.terminal_reason
    )


def clasificar_error(error: ResultError) -> Clasificacion:
    """Clasifica la excepción que el SDK lanza si el ciclo terminó con un error.

    El SDK la lanza solo después de terminar con `is_error` verdadero, así que lo es siempre.
    """
    datos: dict[str, Any] = getattr(error, "data", None) or {}
    return clasificar(
        getattr(error, "subtype", None),
        datos.get("stop_reason"),
        True,
        getattr(error, "terminal_reason", None),
    )


def sin_resultado() -> Clasificacion:
    """El flujo terminó sin entregar un `ResultMessage`: no puede tratarse como un fin normal."""
    return Clasificacion(Terminacion.ANOMALA, None, None, "sin mensaje de resultado", True)
