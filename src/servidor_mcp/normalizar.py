"""Normalización de nombres y reglas de coincidencia (R3).

La normalización ignora mayúsculas, tildes, espacios repetidos y puntuación
(`S.A.S.` = `SAS`). Las coincidencias del registro son por contención; las de
listas y noticias, por igualdad del nombre completo. Nunca por parecido.
"""

import re
import unicodedata

MINIMO_CARACTERES = 3

_ELIMINAR = re.compile(r"[.'’]")
_NO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


def normalizar(texto: str) -> str:
    """Devuelve el texto sin tildes, en minúsculas, sin puntos ni apóstrofos y con
    el resto de signos convertidos en un solo espacio."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    simple = _ELIMINAR.sub("", sin_marcas.casefold())
    return _NO_ALFANUMERICO.sub(" ", simple).strip()


def cumple_minimo(texto: str) -> bool:
    """El nombre buscado en el registro debe tener al menos `MINIMO_CARACTERES`
    caracteres una vez normalizado. No aplica a los identificadores."""
    return len(normalizar(texto)) >= MINIMO_CARACTERES


def contiene(buscado: str, nombre: str) -> bool:
    """El texto buscado normalizado está contenido en el nombre normalizado."""
    return normalizar(buscado) in normalizar(nombre)


def igual(a: str, b: str) -> bool:
    """Los nombres completos normalizados son idénticos; nunca coincidencia parcial."""
    return normalizar(a) == normalizar(b)
