"""Detector de datos con forma real y credenciales (FR-005, FR-006).

Funciones puras: no leen archivos ni el entorno. `buscar()` devuelve solo el tipo y la
línea de cada hallazgo, nunca el valor. Las expresiones usan clases de caracteres, de
modo que su propio texto no coincide con ellas.

Contrato: specs/003-guardas-claude-code/contracts/detector-datos.md.
"""

import re

Hallazgo = tuple[str, int]

# --- Tarjeta: 13 a 19 dígitos, prefijo 2-6, separador opcional espacio o guion --------

# (?<!\d[.,]): la parte decimal de un número no cuenta (contrato, revisión de la parada B).
_TARJETA = re.compile(r"(?<![\w])(?<!\d[ -])(?<!\d[.,])[2-6]\d(?:[ -]?\d){11,17}(?![\w])(?![ -]\d)")


def _luhn(digitos: str) -> bool:
    total = 0
    for i, c in enumerate(reversed(digitos)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _tarjetas(texto: str):
    for m in _TARJETA.finditer(texto):
        bruto = m.group(0)
        if "  " in bruto or "--" in bruto or " -" in bruto or "- " in bruto:
            continue
        digitos = re.sub(r"[ -]", "", bruto)
        if 13 <= len(digitos) <= 19 and _luhn(digitos):
            yield m.start()


# --- NIT: 9 dígitos y dígito de verificación de la DIAN ------------------------------

_PESOS_DIAN = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)
_NIT_GUION = re.compile(r"(?<![\w.])(\d{3})\.?(\d{3})\.?(\d{3})-(\d)(?![\w])")
_NIT_PALABRA = re.compile(r"(?<![\w])nit\s*(?::|no\.?|#)?\s*(\d{9})(\d)(?![\w])", re.IGNORECASE)


def dv_dian(nueve: str) -> int:
    """Dígito de verificación de la DIAN para un NIT de 9 dígitos."""
    s = sum(int(d) * p for d, p in zip(reversed(nueve), _PESOS_DIAN, strict=False)) % 11
    return s if s in (0, 1) else 11 - s


def _nits(texto: str):
    for m in _NIT_GUION.finditer(texto):
        if dv_dian(m.group(1) + m.group(2) + m.group(3)) == int(m.group(4)):
            yield m.start()
    for m in _NIT_PALABRA.finditer(texto):
        if dv_dian(m.group(1)) == int(m.group(2)):
            yield m.start()


# --- Cédula: número de 6 a 10 dígitos tras una palabra de contexto -------------------

_CONTEXTO = (
    r"(?:(?i:(?<![\w])c[ée]dula(?:\s+de\s+ciudadan[íi]a)?"
    r"|(?<![\w])documento\s+de\s+identidad"
    r"|(?<![\w])identificaci[óo]n)"
    r"|(?<![\w])C\.C\."
    r"|(?<![\w])CC(?![\w]))"
)
_ENTRE = r"(?P<entre>(?:[ \t]|:|#|(?i:n[°º]|no\.|n[úu]mero))*)"
_NUMERO = r"(?P<numero>\d{1,3}(?:\.\d{3}){1,3}|\d{6,10})(?![\w])(?!\.\d)"
_CEDULA = re.compile(_CONTEXTO + _ENTRE + _NUMERO)


def _cedulas(texto: str):
    for m in _CEDULA.finditer(texto):
        digitos = m.group("numero").replace(".", "")
        if len(m.group("entre")) <= 20 and 6 <= len(digitos) <= 10:
            yield m.start()


# --- Credenciales ---------------------------------------------------------------------

_CREDENCIALES = [
    re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?<![A-Za-z0-9_])sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?<![A-Za-z0-9_])AKIA[A-Z0-9]{16}(?![A-Za-z0-9_])"),
    re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"),
]


def _credenciales(texto: str):
    for patron in _CREDENCIALES:
        for m in patron.finditer(texto):
            yield m.start()


# --- Interfaz -----------------------------------------------------------------------


def buscar(texto: str) -> list[Hallazgo]:
    """Hallazgos `(tipo, línea)` de `texto`, ordenados por línea y sin repetir."""
    hallazgos: set[Hallazgo] = set()
    for tipo, buscador in (
        ("tarjeta", _tarjetas),
        ("nit", _nits),
        ("cedula", _cedulas),
        ("credencial", _credenciales),
    ):
        for inicio in buscador(texto):
            hallazgos.add((tipo, texto.count("\n", 0, inicio) + 1))
    return sorted(hallazgos, key=lambda h: (h[1], h[0]))
