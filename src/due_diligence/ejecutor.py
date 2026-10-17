"""Ejecutor de subagentes: un `query()` por subagente (R1, R5, R6, contrato `caso.md`).

El protocolo `EjecutorSubagente` permite sustituir el SDK por un ejecutor simulado en los tests.
`EjecutorSDK` consume el flujo con `async for` (sin `while` ni contadores, FR-010), recoge cada
llamada a una herramienta de la pasarela como una `Consulta` y clasifica cómo terminó el ciclo.

El resultado de cada consulta se toma del `ToolResultBlock`, no del texto del modelo: el contenido
y los metadatos llegan separados como los entrega el servidor y no se reescriben (FR-007).
"""

import json
from collections.abc import Callable
from typing import Any, Protocol

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)
from claude_agent_sdk._errors import ResultError

from due_diligence.estado import Consulta, ResultadoFrente
from due_diligence.frentes import FRENTES, Frente
from due_diligence.terminacion import (
    Clasificacion,
    clasificar_error,
    clasificar_resultado,
    sin_resultado,
)

_CLAVES_DEL_CONTRATO = ("resultado", "hechos", "metadatos")


class EjecutorSubagente(Protocol):
    async def __call__(
        self, frente: Frente, contexto: str, opciones: ClaudeAgentOptions
    ) -> ResultadoFrente: ...


def _texto_de(contenido: Any) -> str:
    """El texto de un `ToolResultBlock`: una cadena o una lista de bloques de texto."""
    if contenido is None:
        return ""
    if isinstance(contenido, str):
        return contenido
    partes = []
    for bloque in contenido:
        if isinstance(bloque, dict):
            partes.append(str(bloque.get("text", "")))
        else:
            partes.append(str(getattr(bloque, "text", "")))
    return "".join(partes)


def _es_del_contrato(objeto: Any) -> bool:
    return (
        isinstance(objeto, dict)
        and all(clave in objeto for clave in _CLAVES_DEL_CONTRATO)
        and isinstance(objeto["hechos"], list)
        and isinstance(objeto["metadatos"], dict)
    )


def interpretar_resultado(
    contenido: Any, es_error: bool | None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """(resultado del contrato, error estructurado) de lo que devolvió una herramienta.

    El error de la pasarela se conserva tal como llegó, con su `reintentable`; un error que no es
    JSON se envuelve con la misma forma y `reintentable: false`. Lo que no es ni lo uno ni lo otro
    queda como `(None, None)`: un resultado inválido.
    """
    texto = _texto_de(contenido)
    try:
        objeto = json.loads(texto)
    except ValueError:
        objeto = None
    if isinstance(objeto, dict) and objeto.get("error") is True:
        return None, objeto
    if es_error:
        error = {
            "error": True,
            "tipo": "error_de_herramienta",
            "mensaje": texto,
            "reintentable": False,
            "obtenido": {},
        }
        return None, error
    if _es_del_contrato(objeto):
        return objeto, None
    return None, None


class EjecutorSDK:
    """Lanza al subagente con `query()` y recoge sus consultas y cómo terminó."""

    def __init__(self, consulta: Callable[..., Any] = query) -> None:
        self._consulta = consulta

    async def __call__(
        self, frente: Frente, contexto: str, opciones: ClaudeAgentOptions
    ) -> ResultadoFrente:
        consultas: list[Consulta] = []
        por_id: dict[str, Consulta] = {}
        ajenas: set[str] = set()
        propia = FRENTES[frente].herramienta_completa
        resumen = ""
        clasificacion: Clasificacion | None = None
        coste: float | None = None
        try:
            async for mensaje in self._consulta(prompt=contexto, options=opciones):
                if isinstance(mensaje, AssistantMessage):
                    for bloque in mensaje.content:
                        if isinstance(bloque, ToolUseBlock):
                            if bloque.name != propia:  # herramienta ajena: no es una consulta
                                ajenas.add(bloque.id)
                                continue
                            nueva = Consulta(
                                frente, bloque.name, dict(bloque.input), None, False, None
                            )
                            consultas.append(nueva)
                            por_id[bloque.id] = nueva
                        elif isinstance(bloque, TextBlock):
                            resumen = bloque.text
                elif isinstance(mensaje, UserMessage) and isinstance(mensaje.content, list):
                    for bloque in mensaje.content:
                        if not isinstance(bloque, ToolResultBlock):
                            continue
                        if bloque.tool_use_id in ajenas:
                            continue
                        resultado, error = interpretar_resultado(bloque.content, bloque.is_error)
                        consulta = por_id.get(bloque.tool_use_id)
                        if consulta is None:
                            consulta = Consulta(frente, "", {}, None, False, None)
                            consultas.append(consulta)
                        consulta.resultado = resultado
                        consulta.valido = resultado is not None
                        consulta.error = error
                elif isinstance(mensaje, ResultMessage):
                    clasificacion = clasificar_resultado(mensaje)
                    coste = mensaje.total_cost_usd
        except ResultError as error:
            # El SDK la lanza después del ResultMessage: solo se clasifica si no se vio antes.
            if clasificacion is None:
                clasificacion = clasificar_error(error)
        if clasificacion is None:
            clasificacion = sin_resultado()
        return ResultadoFrente(
            frente, consultas, resumen, clasificacion, clasificacion.detalle, coste
        )
