"""Piezas compartidas por las guardas de Claude Code.

- Lectura del JSON de stdin, raíz del repositorio y normalización de rutas.
- División de comandos de terminal en subcomandos (Bash y PowerShell).
- Bloqueo con código de salida 2 y envoltorio de fallo cerrado.
- Extractor de texto ejecutable: comandos interiores de shells y código en línea de
  intérpretes (research R9, decisión 1; R10).

Solo usa la biblioteca estándar. Contrato: specs/003-guardas-claude-code/contracts/guardas.md.
"""

import json
import os
import re
import shlex
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn, TextIO

MAX_NIVELES = 3

# --- Entrada y rutas ----------------------------------------------------------------


def leer_entrada(flujo: TextIO | None = None) -> dict:
    """Lee el JSON del hook. Lanza ValueError si no es un objeto JSON."""
    texto = (flujo or sys.stdin).read()
    datos = json.loads(texto)
    if not isinstance(datos, dict):
        raise ValueError("la entrada del hook no es un objeto JSON")
    return datos


def raiz(entrada: dict) -> Path:
    """Raíz del repositorio: CLAUDE_PROJECT_DIR o, si falta, el cwd de la entrada."""
    proyecto = os.environ.get("CLAUDE_PROJECT_DIR")
    if proyecto:
        return Path(proyecto)
    return Path(entrada.get("cwd") or os.getcwd())


def cwd(entrada: dict, base: Path) -> Path:
    """Directorio de trabajo del comando (sigue los `cd` de Claude)."""
    return Path(entrada.get("cwd") or base)


def _partes(ruta: str) -> list[str]:
    return [p for p in ruta.replace("\\", "/").split("/") if p not in ("", ".")]


def normalizar_ruta(ruta: str, base: Path, cwd: Path | None = None) -> str:
    """Ruta con `/`, relativa a `base` si está dentro; si no, absoluta.

    Las mayúsculas no cuentan al comparar con la raíz, porque Windows y macOS no las
    distinguen en las rutas.
    """
    texto = ruta.replace("\\", "/")
    if not os.path.isabs(texto) and not re.match(r"^[A-Za-z]:/", texto):
        texto = str(cwd or base).replace("\\", "/") + "/" + texto
    absoluta = os.path.normpath(texto).replace("\\", "/")
    raiz_partes = _partes(os.path.normpath(str(base)))
    partes = _partes(absoluta)
    if [p.casefold() for p in partes[: len(raiz_partes)]] == [p.casefold() for p in raiz_partes]:
        return "/".join(partes[len(raiz_partes) :])
    return absoluta


# --- División de comandos -----------------------------------------------------------

_HEREDOC = re.compile(r"<<(?!<)(-?)[ \t]*(['\"]?)([A-Za-z_][\w.-]*)\2")
_MARCA = "__heredoc_{}__"
_SEPARADORES = set(";&|\n()")


@dataclass
class _Tokens:
    subcomandos: list[list[str]]
    cuerpos: list[list[str]]  # cuerpos de heredoc de cada subcomando, en orden


def _separar_heredocs(comando: str) -> tuple[str, list[str]]:
    """Quita los cuerpos de los heredocs y deja una marca en su lugar."""
    lineas = comando.split("\n")
    salida: list[str] = []
    cuerpos: list[str] = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        pendientes: list[tuple[str, bool]] = []

        def marcar(m: re.Match, pendientes=pendientes) -> str:
            pendientes.append((m.group(3), m.group(1) == "-"))
            return "<< " + _MARCA.format(len(cuerpos) + len(pendientes) - 1)

        salida.append(_HEREDOC.sub(marcar, linea))
        i += 1
        for delimitador, quitar_tabs in pendientes:
            cuerpo: list[str] = []
            while i < len(lineas):
                actual = lineas[i].lstrip("\t") if quitar_tabs else lineas[i]
                i += 1
                if actual == delimitador:
                    break
                cuerpo.append(actual)
            cuerpos.append("\n".join(cuerpo))
    return "\n".join(salida), cuerpos


def _tokenizar(comando: str, powershell: bool) -> _Tokens:
    if powershell:
        texto, cuerpos = comando, []
    else:
        texto, cuerpos = _separar_heredocs(comando)
    lex = shlex.shlex(texto, posix=not powershell, punctuation_chars=";&|<>()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = "" if powershell else "#"
    subcomandos: list[list[str]] = []
    cuerpos_sub: list[list[str]] = []
    actual: list[str] = []
    actual_cuerpos: list[str] = []
    tokens = list(lex)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token and all(c in _SEPARADORES for c in token):
            if actual:
                subcomandos.append(actual)
                cuerpos_sub.append(actual_cuerpos)
            actual, actual_cuerpos = [], []
        elif token == "<<" and i + 1 < len(tokens) and tokens[i + 1].startswith("__heredoc_"):
            indice = int(tokens[i + 1].removeprefix("__heredoc_").removesuffix("__"))
            actual_cuerpos.append(cuerpos[indice])
            i += 1
        else:
            if powershell and len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
                token = token[1:-1]
            actual.append(token)
        i += 1
    if actual:
        subcomandos.append(actual)
        cuerpos_sub.append(actual_cuerpos)
    return _Tokens(subcomandos, cuerpos_sub)


def dividir_comando(comando: str, powershell: bool = False) -> list[list[str]]:
    """Subcomandos separados por `;`, `&&`, `||`, `|`, `&`, paréntesis o saltos de línea.

    Las redirecciones quedan como palabras (`<`, `>`, `>>`). Los cuerpos de los heredocs
    se quitan; el extractor de texto ejecutable los recupera cuando hace falta.
    """
    return _tokenizar(comando, powershell).subcomandos


# --- Bloqueo y fallo cerrado --------------------------------------------------------


def bloquear(guarda: str, mensaje: str) -> NoReturn:
    """Bloquea la acción: una sola línea en stderr y código de salida 2."""
    linea = " ".join(mensaje.split())
    print(f"[{guarda}] {linea}", file=sys.stderr)
    sys.exit(2)


def ejecutar(guarda: str, revisar: Callable[[dict], None]) -> NoReturn:
    """Lee la entrada y ejecuta la guarda; ante cualquier error propio, bloquea."""
    try:
        revisar(leer_entrada())
    except SystemExit:
        raise
    except BaseException as error:  # noqa: BLE001 - fallo cerrado (FR-020)
        bloquear(
            guarda,
            f"La guarda falló ({type(error).__name__}); la acción se bloquea por precaución.",
        )
    sys.exit(0)


# --- Extractor de texto ejecutable --------------------------------------------------

_SHELLS = {"bash", "sh"}
_POWERSHELL = {"powershell", "pwsh"}
_PYTHON = re.compile(r"python(\d+(\.\d+)?)?")
_OPCIONES_UV_CON_VALOR = {
    "--with",
    "--with-requirements",
    "--python",
    "-p",
    "--project",
    "--directory",
    "--env-file",
    "--group",
    "--extra",
    "--index",
    "--package",
}


@dataclass
class ComandoInterior:
    texto: str
    powershell: bool
    nivel: int


@dataclass
class Extraccion:
    comandos: list[ComandoInterior] = field(default_factory=list)
    codigos: list[str] = field(default_factory=list)
    anidamiento_excesivo: bool = False


def _nombre(palabra: str) -> str:
    nombre = palabra.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return nombre.removesuffix(".exe")


def _sin_uv_run(palabras: list[str]) -> list[str]:
    """Quita `uv run [opciones]` del principio del subcomando."""
    if len(palabras) < 2 or _nombre(palabras[0]) != "uv" or palabras[1] != "run":
        return palabras
    i = 2
    while i < len(palabras) and palabras[i].startswith("-"):
        i += 2 if palabras[i] in _OPCIONES_UV_CON_VALOR else 1
    return palabras[i:]


def _codigo_de_interprete(palabras: list[str]) -> str | None:
    """Argumento de código en línea de python, py, node, perl o ruby, si lo hay."""
    nombre, args = _nombre(palabras[0]), palabras[1:]
    if _PYTHON.fullmatch(nombre) or nombre == "py":
        opciones = {"-c"}
    elif nombre == "node":
        opciones = {"-e", "--eval", "-p", "--print"}
    elif nombre == "perl":
        opciones = {"-e", "-E"}
    elif nombre == "ruby":
        opciones = {"-e"}
    else:
        return None
    for i, arg in enumerate(args):
        if arg in opciones:
            return args[i + 1] if i + 1 < len(args) else ""
        clave, igual, valor = arg.partition("=")
        if igual and clave in opciones:
            return valor
        if not arg.startswith("-") or arg in ("-m", "-"):
            return None
    return None


def _es_interprete(palabra: str) -> bool:
    nombre = _nombre(palabra)
    return bool(_PYTHON.fullmatch(nombre)) or nombre in {"py", "node", "perl", "ruby"}


def _interior_de_shell(palabras: list[str]) -> tuple[str, bool] | None:
    """Comando interior de `bash -c`, `sh -c`, `eval` o `pwsh -Command`."""
    nombre, args = _nombre(palabras[0]), palabras[1:]
    if nombre == "eval":
        return (" ".join(args), False) if args else None
    if nombre in _SHELLS:
        for i, arg in enumerate(args):
            if arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]:
                return (args[i + 1], False) if i + 1 < len(args) else None
            if not arg.startswith("-"):
                return None
        return None
    if nombre in _POWERSHELL:
        for i, arg in enumerate(args):
            if arg.lower() in ("-command", "-c"):
                return (" ".join(args[i + 1 :]), True) if i + 1 < len(args) else None
        return None
    return None


def extraer_texto_ejecutable(comando: str, powershell: bool = False) -> Extraccion:
    """Comandos interiores de shells y código en línea de intérpretes de `comando`.

    - Los comandos interiores (de `bash -c`, `sh -c`, `eval`, `pwsh -Command` y de los
      heredocs que alimentan a `bash` o `sh`) se devuelven con su nivel, para que cada
      guarda los analice con sus mismas reglas. Se buscan también dentro de ellos.
    - El código de `python`, `py`, `node`, `perl` y `ruby` (opción en línea o heredoc)
      se devuelve como texto.
    - Un comando interior que no se puede analizar se devuelve como texto.
    - Con más de MAX_NIVELES shells anidados se marca anidamiento excesivo.
    """
    extraccion = Extraccion()
    _extraer(comando, powershell, 0, extraccion)
    return extraccion


def _extraer(comando: str, powershell: bool, nivel: int, extraccion: Extraccion) -> None:
    tokens = _tokenizar(comando, powershell)
    for palabras, cuerpos in zip(tokens.subcomandos, tokens.cuerpos, strict=True):
        palabras = _sin_uv_run(palabras)
        if not palabras:
            continue
        interiores: list[tuple[str, bool]] = []
        interior = _interior_de_shell(palabras)
        if interior is not None:
            interiores.append(interior)
        codigo = _codigo_de_interprete(palabras)
        if codigo is not None:
            extraccion.codigos.append(codigo)
        nombre = _nombre(palabras[0])
        for cuerpo in cuerpos:
            if nombre in _SHELLS:
                interiores.append((cuerpo, False))
            elif _es_interprete(palabras[0]) and codigo is None:
                extraccion.codigos.append(cuerpo)
        for texto, es_powershell in interiores:
            if nivel + 1 > MAX_NIVELES:
                extraccion.anidamiento_excesivo = True
                continue
            try:
                _tokenizar(texto, es_powershell)
            except ValueError:
                extraccion.codigos.append(texto)
                continue
            extraccion.comandos.append(ComandoInterior(texto, es_powershell, nivel + 1))
            _extraer(texto, es_powershell, nivel + 1, extraccion)
