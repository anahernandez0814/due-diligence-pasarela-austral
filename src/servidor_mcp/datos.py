"""Carga de los datos ficticios de `datos/` (R8).

Cada archivo es JSON, está marcado como ficticio, lleva un aviso en español y la `fecha_corte`
de su fuente. Un archivo ausente, corrupto o sin esas marcas lanza `DatosNoDisponibles`: las
herramientas lo convierten en un error estructurado y nunca presentan datos parciales como
completos. Este módulo no imprime nada: stdout es el canal del protocolo.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

DIRECTORIO_DATOS = Path(__file__).resolve().parent / "datos"

_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DatosNoDisponibles(Exception):
    """Un archivo de datos falta, está corrupto o no cumple las marcas obligatorias."""


def cargar(ruta: Path) -> dict[str, Any]:
    """Lee y valida un archivo de datos."""
    ruta = Path(ruta)
    try:
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DatosNoDisponibles(f"No existe el archivo de datos «{ruta.name}».") from None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise DatosNoDisponibles(f"No se pudo leer el archivo de datos «{ruta.name}».") from None
    if not isinstance(contenido, dict):
        raise DatosNoDisponibles(f"El archivo de datos «{ruta.name}» no es un objeto JSON.")
    if contenido.get("ficticio") is not True:
        raise DatosNoDisponibles(f"El archivo «{ruta.name}» no está marcado «ficticio: true».")
    aviso = contenido.get("aviso")
    if not isinstance(aviso, str) or not aviso.strip():
        raise DatosNoDisponibles(f"Al archivo «{ruta.name}» le falta el «aviso».")
    fecha = contenido.get("fecha_corte")
    if not isinstance(fecha, str) or not _FECHA.match(fecha):
        raise DatosNoDisponibles(
            f"Al archivo «{ruta.name}» le falta «fecha_corte» con formato AAAA-MM-DD."
        )
    return contenido


@cache
def _archivo(nombre: str) -> dict[str, Any]:
    return cargar(DIRECTORIO_DATOS / nombre)


def limpiar_cache() -> None:
    """Olvida lo cargado (para los tests)."""
    _archivo.cache_clear()


def registros() -> list[dict[str, Any]]:
    """Las dos fuentes registrales ficticias, en orden."""
    return [_archivo("registro_rmf_sur.json"), _archivo("registro_rufe.json")]


def listas() -> dict[str, Any]:
    return _archivo("listas_restrictivas.json")


def noticias() -> dict[str, Any]:
    return _archivo("noticias.json")


def categorias() -> dict[str, Any]:
    return _archivo("categorias.json")
