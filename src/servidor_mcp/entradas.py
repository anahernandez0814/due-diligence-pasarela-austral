"""Validadores de parámetros de las herramientas (R2).

El SDK rechaza un argumento ausente o de tipo incorrecto antes de entrar a la herramienta, con
texto de pydantic en inglés y sin estructura. Por eso todos los parámetros se declaran opcionales
(`Any = None`) y se validan aquí. Los validadores **nunca lanzan**: devuelven el valor o un error
estructurado en español. Los mensajes nombran el parámetro y el tipo esperado, nunca el valor
recibido.
"""

from typing import Any

from mcp_types import CallToolResult

from servidor_mcp.respuestas import error

_NOMBRES_DE_TIPO = {str: "texto", dict: "objeto", list: "lista"}


def _nombre_del_tipo(esperado: type | tuple[type, ...]) -> str:
    tipos = esperado if isinstance(esperado, tuple) else (esperado,)
    return " o ".join(_NOMBRES_DE_TIPO.get(t, t.__name__) for t in tipos)


def _vacio(valor: Any) -> bool:
    """Ausente, texto en blanco o contenedor vacío. El 0 y el falso no son vacíos."""
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    if isinstance(valor, (dict, list)):
        return not valor
    return False


def texto_obligatorio(valor: Any, parametro: str) -> tuple[str | None, CallToolResult | None]:
    """Un texto no vacío. Devuelve `(texto sin espacios de los bordes, None)` o `(None, error)`."""
    if _vacio(valor):
        return None, error(
            "entrada_invalida", f"Falta el parámetro «{parametro}»: debe ser un texto.", False
        )
    if not isinstance(valor, str):
        return None, error(
            "entrada_invalida", f"El parámetro «{parametro}» debe ser un texto.", False
        )
    return valor.strip(), None


def exactamente_uno(
    nombre: Any, identificador: Any
) -> tuple[tuple[str, str] | None, CallToolResult | None]:
    """Exige `nombre` o `identificador`, uno solo. Un valor en blanco cuenta como ausente.

    Devuelve `(("nombre" | "identificador", texto), None)` o `(None, error)`.
    """
    dados = [
        (clave, valor)
        for clave, valor in (("nombre", nombre), ("identificador", identificador))
        if not _vacio(valor)
    ]
    if len(dados) != 1:
        return None, error(
            "entrada_invalida",
            "Se debe indicar exactamente uno de los parámetros «nombre» e «identificador».",
            False,
        )
    clave, valor = dados[0]
    texto, err = texto_obligatorio(valor, clave)
    if err is not None:
        return None, err
    return (clave, texto), None


def objeto_obligatorio(valor: Any, parametro: str) -> tuple[dict | None, CallToolResult | None]:
    """Un objeto no vacío. Devuelve `(objeto, None)` o `(None, error)`."""
    if _vacio(valor):
        return None, error(
            "entrada_invalida", f"Falta el parámetro «{parametro}»: debe ser un objeto.", False
        )
    if not isinstance(valor, dict):
        return None, error(
            "entrada_invalida", f"El parámetro «{parametro}» debe ser un objeto.", False
        )
    return valor, None


def campos_obligatorios(
    entrada: dict[str, Any], requeridos: dict[str, type | tuple[type, ...]]
) -> CallToolResult | None:
    """Comprueba todos los campos obligatorios de una vez.

    `requeridos` asocia cada nombre con el tipo esperado. Primero se informan **todos** los que
    faltan (`campos_obligatorios_ausentes`, con `campos_faltantes`); si no falta ninguno, todos los
    de tipo incorrecto (`entrada_invalida`). Devuelve `None` si todo está bien.
    """
    faltantes = [nombre for nombre in requeridos if _vacio(entrada.get(nombre))]
    if faltantes:
        lista = ", ".join(f"«{nombre}»" for nombre in faltantes)
        return error(
            "campos_obligatorios_ausentes",
            f"Faltan campos obligatorios: {lista}.",
            False,
            campos_faltantes=faltantes,
        )
    incorrectos = [
        f"«{nombre}» (debe ser {_nombre_del_tipo(tipo)})"
        for nombre, tipo in requeridos.items()
        if not isinstance(entrada[nombre], tipo)
    ]
    if incorrectos:
        return error(
            "entrada_invalida",
            "Campos con un tipo incorrecto: " + ", ".join(incorrectos) + ".",
            False,
        )
    return None
