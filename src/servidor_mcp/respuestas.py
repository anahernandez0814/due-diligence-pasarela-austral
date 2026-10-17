"""Forma de las respuestas del servidor: contenido separado de metadatos (R2, R9).

Toda herramienta devuelve un `CallToolResult`. El texto es el mismo JSON que el
contenido estructurado, para el cliente que solo lee texto. Los errores llevan
`is_error=True` porque el SDK, ante una excepción, solo entrega texto libre.
"""

import json
from typing import Any

from mcp.types import CallToolResult, TextContent

SERVICIO_NO_DISPONIBLE = "servicio_no_disponible"

TIPOS_ERROR = (
    "entrada_invalida",
    "campos_obligatorios_ausentes",
    SERVICIO_NO_DISPONIBLE,
    "datos_no_disponibles",
    "error_de_almacenamiento",
    "error_interno",
)

_CLAVES_DE_METADATOS = ("fuente", "fecha")


def _resultado(cuerpo: dict[str, Any], es_error: bool) -> CallToolResult:
    texto = json.dumps(cuerpo, ensure_ascii=False, indent=2)
    return CallToolResult(
        content=[TextContent(type="text", text=texto)],
        structured_content=cuerpo,
        is_error=es_error,
    )


def hecho(contenido: dict[str, Any], fuente: str, fecha: str) -> dict[str, Any]:
    """Un hecho: el contenido por un lado y su fuente y su fecha por otro."""
    repetidas = [clave for clave in _CLAVES_DE_METADATOS if clave in contenido]
    if repetidas:
        raise ValueError(f"El contenido de un hecho no lleva metadatos: {repetidas}")
    return {"contenido": contenido, "metadatos": {"fuente": fuente, "fecha": fecha}}


def respuesta(
    resultado: str,
    hechos: list[dict[str, Any]],
    fuentes: list[str],
    fecha: str,
    coincidencias: list[str] | None = None,
) -> CallToolResult:
    """Respuesta de éxito. `coincidencias` solo la usa el registro mercantil."""
    for h in hechos:
        if set(h) != {"contenido", "metadatos"}:
            raise ValueError("Cada hecho se construye con hecho()")
    cuerpo: dict[str, Any] = {"resultado": resultado}
    if coincidencias is not None:
        cuerpo["coincidencias"] = list(coincidencias)
    cuerpo["hechos"] = hechos
    cuerpo["metadatos"] = {"fuentes": list(fuentes), "fecha": fecha}
    return _resultado(cuerpo, es_error=False)


def error(
    tipo: str,
    mensaje: str,
    reintentable: bool,
    obtenido: dict[str, Any] | None = None,
    campos_faltantes: list[str] | None = None,
) -> CallToolResult:
    """Error estructurado. Solo `servicio_no_disponible` es reintentable."""
    if tipo not in TIPOS_ERROR:
        raise ValueError(f"Tipo de error desconocido: {tipo}")
    if reintentable != (tipo == SERVICIO_NO_DISPONIBLE):
        raise ValueError("Solo servicio_no_disponible es reintentable")
    cuerpo: dict[str, Any] = {
        "error": True,
        "tipo": tipo,
        "mensaje": mensaje,
        "reintentable": reintentable,
        "obtenido": obtenido if obtenido is not None else {},
    }
    if campos_faltantes is not None:
        cuerpo["campos_faltantes"] = list(campos_faltantes)
    return _resultado(cuerpo, es_error=True)
