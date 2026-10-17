"""consultar_listas_restrictivas: verifica un comercio o una persona contra las listas ficticias.

Hay coincidencia solo por nombre completo normalizado o por identificador, nunca parcial, y solo
entre entradas del mismo `tipo`. Una mención en noticias no es una coincidencia en listas.
Siempre se consultan todas las listas: la `fecha` de nivel superior es la `fecha_corte` más
antigua de ellas y cada hecho conserva la de su lista.
"""

from typing import Any

from mcp.types import CallToolResult

from servidor_mcp import datos
from servidor_mcp.entradas import exactamente_uno, texto_obligatorio
from servidor_mcp.normalizar import igual, igual_identificador
from servidor_mcp.respuestas import error, hecho, respuesta

TIPOS = ("comercio", "persona")


def consultar_listas_restrictivas(
    tipo: Any = None, nombre: Any = None, identificador: Any = None
) -> CallToolResult:
    """Busca `nombre` o `identificador` entre las entradas del `tipo` indicado."""
    tipo_texto, err = texto_obligatorio(tipo, "tipo")
    if err is not None:
        return err
    tipo_normalizado = tipo_texto.casefold()
    if tipo_normalizado not in TIPOS:
        return error(
            "entrada_invalida",
            "El parámetro «tipo» debe ser «comercio» o «persona».",
            False,
        )
    busqueda, err = exactamente_uno(nombre, identificador)
    if err is not None:
        return err
    clave, texto = busqueda

    try:
        listas = datos.listas()["listas"]
    except datos.DatosNoDisponibles as exc:
        return error("datos_no_disponibles", str(exc), False)

    def coincide(entrada: dict[str, Any]) -> bool:
        if entrada["tipo"] != tipo_normalizado:
            return False
        if clave == "identificador":
            return igual_identificador(entrada["identificador"], texto)
        return igual(entrada["nombre"], texto)

    hechos = [
        hecho(
            {
                "lista": lista["lista"],
                "tipo": entrada["tipo"],
                "nombre": entrada["nombre"],
                "identificador": entrada["identificador"],
            },
            lista["fuente"],
            lista["fecha_corte"],
        )
        for lista in listas
        for entrada in lista["entradas"]
        if coincide(entrada)
    ]
    return respuesta(
        "coincidencias" if hechos else "sin_coincidencias",
        hechos,
        [lista["fuente"] for lista in listas],
        min(lista["fecha_corte"] for lista in listas),
    )
