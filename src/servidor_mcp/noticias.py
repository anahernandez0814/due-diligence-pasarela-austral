"""buscar_noticias: busca menciones de un comercio o una persona en un corpus ficticio.

Una mención no es una coincidencia en listas restrictivas. La coincidencia es por nombre
completo normalizado o por identificador de las entidades que cada noticia menciona, nunca
parcial. Con `PASARELA_FALLA_NOTICIAS=1` el servicio simula una caída reintentable; la variable
se lee **en cada llamada** (R5), nunca al importar el módulo ni al arrancar.
"""

import os
from typing import Any

from mcp.types import CallToolResult

from servidor_mcp import datos
from servidor_mcp.entradas import exactamente_uno
from servidor_mcp.normalizar import igual
from servidor_mcp.respuestas import SERVICIO_NO_DISPONIBLE, error, hecho, respuesta

VARIABLE_FALLA = "PASARELA_FALLA_NOTICIAS"


def buscar_noticias(nombre: Any = None, identificador: Any = None) -> CallToolResult:
    """Busca `nombre` (completo, normalizado) o `identificador` entre las menciones."""
    busqueda, err = exactamente_uno(nombre, identificador)
    if err is not None:
        return err
    clave, texto = busqueda

    if os.environ.get(VARIABLE_FALLA) == "1":
        return error(
            SERVICIO_NO_DISPONIBLE,
            "El servicio de noticias no está disponible. Se puede reintentar; mientras tanto, "
            "el frente de noticias queda sin cubrir.",
            True,
        )

    try:
        corpus = datos.noticias()
    except datos.DatosNoDisponibles as exc:
        return error("datos_no_disponibles", str(exc), False)

    def menciona(entidad: dict[str, Any]) -> bool:
        if clave == "identificador":
            return entidad["identificador"] == texto
        return igual(entidad["nombre"], texto)

    hechos = [
        hecho(
            {"id": noticia["id"], "titular": noticia["titular"], "url": noticia["url"]},
            corpus["fuente"],
            noticia["fecha"],
        )
        for noticia in sorted(corpus["noticias"], key=lambda n: n["id"])
        if any(menciona(entidad) for entidad in noticia["menciona"])
    ]
    return respuesta(
        "coincidencias" if hechos else "sin_coincidencias",
        hechos,
        [corpus["fuente"]],
        corpus["fecha_corte"],
    )
