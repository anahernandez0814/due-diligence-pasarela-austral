"""consultar_riesgo_categoria: nivel de riesgo (alto, medio o bajo) de una categoría de negocio.

La categoría la aporta quien consulta: el registro mercantil no la devuelve. Se compara
normalizada. Para una categoría desconocida no se inventa un nivel: se declara y se listan las
conocidas. No decide la habilitación ni escala el caso.
"""

from typing import Any

from mcp.types import CallToolResult

from servidor_mcp import datos
from servidor_mcp.entradas import texto_obligatorio
from servidor_mcp.normalizar import igual
from servidor_mcp.respuestas import error, hecho, respuesta


def categorias_conocidas() -> list[str]:
    """Los nombres del catálogo, en su orden. Lanza `DatosNoDisponibles` si falta el archivo."""
    return [c["nombre"] for c in datos.categorias()["categorias"]]


def consultar_riesgo_categoria(categoria: Any = None) -> CallToolResult:
    """Devuelve el nivel de la categoría, o declara que no la reconoce."""
    texto, err = texto_obligatorio(categoria, "categoria")
    if err is not None:
        return err
    try:
        catalogo = datos.categorias()
    except datos.DatosNoDisponibles as exc:
        return error("datos_no_disponibles", str(exc), False)

    fuente, fecha = catalogo["fuente"], catalogo["fecha_corte"]
    for entrada in catalogo["categorias"]:
        if igual(entrada["nombre"], texto):
            return respuesta(
                "categoria_conocida",
                [hecho({"categoria": entrada["nombre"], "nivel": entrada["nivel"]}, fuente, fecha)],
                [fuente],
                fecha,
            )
    return respuesta(
        "categoria_desconocida",
        [
            hecho(
                {
                    "categoria": texto,
                    "categorias_conocidas": [c["nombre"] for c in catalogo["categorias"]],
                },
                fuente,
                fecha,
            )
        ],
        [fuente],
        fecha,
    )
