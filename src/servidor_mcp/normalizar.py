"""Normalización de nombres y reglas de coincidencia (R3).

La normalización ignora mayúsculas, tildes, espacios repetidos y puntuación
(`S.A.S.` = `SAS`). Las coincidencias del registro son por contención; las de
listas y noticias, por igualdad del nombre completo. Nunca por parecido.
"""

import re
import unicodedata

MINIMO_CARACTERES = 3

# Formas jurídicas que se ignoran al final del nombre en el registro mercantil, ya normalizadas
# («S.A.S.» → sas, «S. en C.» → s en c). Solo se quitan al final y como palabras completas.
FORMAS_JURIDICAS = (("sas",), ("sa",), ("ltda",), ("eu",), ("sca",), ("s", "en", "c"))

_ELIMINAR = re.compile(r"[.'’]")
_NO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


def normalizar(texto: str) -> str:
    """Devuelve el texto sin tildes, en minúsculas, sin puntos ni apóstrofos y con
    el resto de signos convertidos en un solo espacio."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    simple = _ELIMINAR.sub("", sin_marcas.casefold())
    return _NO_ALFANUMERICO.sub(" ", simple).strip()


def sin_forma_juridica(texto: str) -> str:
    """El texto normalizado sin las formas jurídicas del final (`sas`, `sa`, `ltda`, `eu`,
    `sca`, `s en c`). Solo al final y como palabras completas; si hay varias seguidas, todas."""
    palabras = normalizar(texto).split()
    quitada = True
    while quitada:
        quitada = False
        for forma in FORMAS_JURIDICAS:
            if palabras[-len(forma) :] == list(forma):
                palabras = palabras[: -len(forma)]
                quitada = True
                break
    return " ".join(palabras)


def cumple_minimo(texto: str) -> bool:
    """El nombre buscado en el registro debe tener al menos `MINIMO_CARACTERES` caracteres una
    vez normalizado y sin la forma jurídica final. No aplica a los identificadores."""
    return len(sin_forma_juridica(texto)) >= MINIMO_CARACTERES


def contiene(buscado: str, nombre: str) -> bool:
    """El texto buscado normalizado está contenido en el nombre normalizado."""
    return normalizar(buscado) in normalizar(nombre)


def igual(a: str, b: str) -> bool:
    """Los nombres completos normalizados son idénticos; nunca coincidencia parcial."""
    return normalizar(a) == normalizar(b)


def contiene_en_registro(buscado: str, nombre: str) -> bool:
    """Coincidencia del registro mercantil: el texto buscado está contenido en el nombre del
    comercio, ignorando la forma jurídica final de los dos. Solo la forma jurídica no coincide."""
    texto = sin_forma_juridica(buscado)
    return bool(texto) and texto in sin_forma_juridica(nombre)


def igual_identificador(a: str, b: str) -> bool:
    """Los identificadores son iguales sin distinguir mayúsculas ni espacios de los bordes."""
    return a.strip().casefold() == b.strip().casefold()
