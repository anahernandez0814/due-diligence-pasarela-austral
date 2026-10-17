"""consultar_registro_mercantil: busca un comercio en las dos fuentes registrales ficticias.

Devuelve **todas** las coincidencias y nunca elige una. Cada comercio produce un hecho por
fuente en la que figura; si las fuentes difieren, ambos valores se devuelven con su fuente.
Las coincidencias se cuentan en `coincidencias`, no en `hechos`. No consulta listas ni noticias
y no devuelve la categoría de negocio.
"""

from typing import Any

from mcp.types import CallToolResult

from servidor_mcp import datos
from servidor_mcp.entradas import exactamente_uno
from servidor_mcp.normalizar import contiene, cumple_minimo
from servidor_mcp.respuestas import error, hecho, respuesta


def _contenido(comercio: dict[str, Any]) -> dict[str, Any]:
    return {
        "identificador": comercio["identificador"],
        "nombre": comercio["nombre"],
        "fecha_constitucion": comercio["fecha_constitucion"],
        "estado": comercio["estado"],
        "representante_legal": comercio["representante_legal"],
    }


def consultar_registro_mercantil(nombre: Any = None, identificador: Any = None) -> CallToolResult:
    """Busca por `nombre` (contención del texto normalizado) o por `identificador` (exacto)."""
    busqueda, err = exactamente_uno(nombre, identificador)
    if err is not None:
        return err
    clave, texto = busqueda
    if clave == "nombre" and not cumple_minimo(texto):
        return error(
            "entrada_invalida",
            "El nombre debe tener al menos 3 caracteres, sin contar signos de puntuación.",
            False,
        )

    try:
        fuentes = datos.registros()
    except datos.DatosNoDisponibles as exc:
        return error("datos_no_disponibles", str(exc), False)

    if clave == "identificador":

        def coincide(comercio: dict[str, Any]) -> bool:
            return comercio["identificador"] == texto
    else:

        def coincide(comercio: dict[str, Any]) -> bool:
            return contiene(texto, comercio["nombre"])

    identificadores = sorted(
        {c["identificador"] for f in fuentes for c in f["comercios"] if coincide(c)}
    )
    hechos = [
        hecho(_contenido(c), f["fuente"], f["fecha_corte"])
        for identificador_comercio in identificadores
        for f in fuentes
        for c in f["comercios"]
        if c["identificador"] == identificador_comercio
    ]
    return respuesta(
        "coincidencias" if identificadores else "sin_coincidencias",
        hechos,
        [f["fuente"] for f in fuentes],
        min(f["fecha_corte"] for f in fuentes),
        coincidencias=identificadores,
    )
