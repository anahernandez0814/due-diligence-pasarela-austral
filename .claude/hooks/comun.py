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


_RUTA_GIT_BASH = re.compile(r"^/([A-Za-z])(/|$)")


def normalizar_ruta(ruta: str, base: Path, cwd: Path | None = None) -> str:
    """Ruta con `/`, relativa a `base` si está dentro; si no, absoluta.

    Las mayúsculas no cuentan al comparar con la raíz, porque Windows y macOS no las
    distinguen en las rutas. En Windows, una ruta de Git Bash `/<letra>/…` se convierte
    en `<LETRA>:/…`.
    """
    texto = ruta.replace("\\", "/")
    if os.name == "nt":
        texto = _RUTA_GIT_BASH.sub(lambda m: m.group(1).upper() + ":/", texto)
    if not os.path.isabs(texto) and not re.match(r"^[A-Za-z]:/", texto):
        texto = str(cwd or base).replace("\\", "/") + "/" + texto
    absoluta = os.path.normpath(texto).replace("\\", "/")
    raiz_partes = _partes(os.path.normpath(str(base)))
    partes = _partes(absoluta)
    if [p.casefold() for p in partes[: len(raiz_partes)]] == [p.casefold() for p in raiz_partes]:
        return "/".join(partes[len(raiz_partes) :])
    return absoluta


# --- División de comandos -----------------------------------------------------------

_HEREDOC = re.compile(r"<<(-?)[ \t]*(['\"]?)([A-Za-z_][\w.-]*)\2")
# Marca que ocupa el lugar de un heredoc quitado. Usa un carácter de uso privado de
# Unicode para que un comando escrito a mano no la contenga por casualidad.
_MARCA = "{}"
_ES_MARCA = re.compile("(\\d+)")
_SEPARADORES = set(";&|\n()")
# Detrás de estos caracteres empieza una palabra, y un `#` abre un comentario.
_ANTES_DE_COMENTARIO = set(" \t\n;&|()")


@dataclass
class _Cuerpo:
    texto: str
    expande: bool  # delimitador sin comillas: bash expande $(…) y `…` en el cuerpo
    operador: str = ""  # texto original del operador, por ejemplo <<'FIN'
    quitado: str = ""  # texto original quitado: el cuerpo y la línea de cierre


@dataclass
class _Superficie:
    texto: str  # el comando sin los cuerpos de los heredocs, con una marca en su lugar
    cuerpos: list[_Cuerpo]
    sustituciones: list[str]  # texto original de cada `$(…)` y `…` de primer nivel


@dataclass
class _Marco:
    """Contexto del recorrido: el comando o el interior de un `$(…)`."""

    comillas: str | None = None  # None, "'", '"' o "cuerpo" (las comillas son literales)
    inicio: int = 0  # dónde empieza el texto de un `$(…)`
    parentesis: int = 0


def _quitar_cuerpos(
    texto: str, inicio: int, pendientes: list[tuple[int, re.Match, bool]]
) -> tuple[int, list[tuple[int, _Cuerpo]], list[str]]:
    """Quita, desde `inicio`, los cuerpos de los heredocs pendientes de la línea.

    Devuelve dónde sigue el recorrido, cada cuerpo con la posición de su operador en la
    salida, y las sustituciones de los cuerpos que expanden. Un heredoc cuyo delimitador
    de cierre no aparece no se quita, ni los que le siguen: sus líneas se analizan como
    comandos.
    """
    cuerpos: list[tuple[int, _Cuerpo]] = []
    sustituciones: list[str] = []
    pos = inicio
    for indice, m, primer_nivel in pendientes:
        quitar_tabs, delimitador = m.group(1) == "-", m.group(3)
        lineas: list[str] = []
        cierre = None
        j = pos
        while True:
            fin = texto.find("\n", j)
            linea = texto[j:] if fin == -1 else texto[j:fin]
            linea = linea.lstrip("\t") if quitar_tabs else linea
            if linea == delimitador:
                cierre = len(texto) if fin == -1 else fin + 1
                break
            lineas.append(linea)
            if fin == -1:
                break
            j = fin + 1
        if cierre is None:
            break
        cuerpo = _Cuerpo("\n".join(lineas), not m.group(2), m.group(0), texto[pos:cierre])
        cuerpos.append((indice, cuerpo))
        if cuerpo.expande and primer_nivel:
            sustituciones += _escanear(cuerpo.texto, cuerpo=True).sustituciones
        pos = cierre
    return pos, cuerpos, sustituciones


def _escanear(texto: str, powershell: bool = False, cuerpo: bool = False) -> _Superficie:
    """Recorre el comando una vez, sabiendo de comillas, comentarios y `$(…)`.

    - Quita los cuerpos de heredoc, a cualquier profundidad, y deja una marca. Un `<<`
      entre comillas o en un comentario no abre heredoc; dentro de `$(…)` empieza un
      contexto nuevo, aunque vaya entre comillas dobles.
    - Devuelve el texto original de cada `$(…)` y `…` de primer nivel, con sus heredocs
      completos: el cuerpo viaja con su comando.
    - Quita los comentarios: `#` al principio de una palabra y fuera de comillas, hasta
      el salto de línea sin incluirlo. `a#b`, `${#x}` y `$#` no son comentarios.
    - Con `cuerpo=True`, `texto` es el cuerpo de un heredoc que expande: sus comillas
      son literales. En PowerShell no hay heredocs y el escape es la comilla invertida.
    """
    escape = "`" if powershell else "\\"
    salida: list[str] = []
    cuerpos: list[_Cuerpo] = []
    sustituciones: list[str] = []
    pendientes: list[tuple[int, re.Match, bool]] = []
    pila = [_Marco("cuerpo" if cuerpo else None)]
    i, n = 0, len(texto)
    while i < n:
        c, marco = texto[i], pila[-1]
        if marco.comillas == "'":
            marco.comillas = None if c == "'" else "'"
            salida.append(c)
            i += 1
            continue
        if c == escape:
            salida.append(texto[i : i + 2])
            i += 2
            continue
        if c == '"' and marco.comillas in (None, '"'):
            marco.comillas = None if marco.comillas else '"'
        elif c == "'" and marco.comillas is None:
            marco.comillas = "'"
        elif c == "$" and texto[i + 1 : i + 2] == "(" and texto[i + 2 : i + 3] != "(":
            pila.append(_Marco(inicio=i + 2))
            salida.append("$(")
            i += 2
            continue
        elif c == "`" and not powershell:
            fin = i + 1
            while fin < n and texto[fin] != "`":
                fin += 2 if texto[fin] == "\\" else 1
            if len(pila) == 1:
                sustituciones.append(texto[i + 1 : min(fin, n)])
            salida.append(texto[i : fin + 1])
            i = fin + 1
            continue
        elif marco.comillas is None:
            if c == "(" and len(pila) > 1:
                marco.parentesis += 1
            elif c == ")" and len(pila) > 1:
                if marco.parentesis:
                    marco.parentesis -= 1
                else:
                    pila.pop()
                    if len(pila) == 1:
                        sustituciones.append(texto[marco.inicio : i])
            elif c == "#" and (i == 0 or texto[i - 1] in _ANTES_DE_COMENTARIO):
                # Se quita hasta el salto de línea, que sigue separando comandos.
                fin = texto.find("\n", i)
                i = n if fin == -1 else fin
                continue
            elif texto.startswith("<<<", i):
                salida.append("<<<")
                i += 3
                continue
            elif texto.startswith("<<", i) and not powershell:
                m = _HEREDOC.match(texto, i)
                if m:
                    pendientes.append((len(salida), m, len(pila) == 1))
                    salida.append(m.group(0))
                    i = m.end()
                    continue
                salida.append("<<")
                i += 2
                continue
            elif c == "\n" and pendientes:
                salida.append("\n")
                i, quitados, interiores = _quitar_cuerpos(texto, i + 1, pendientes)
                for indice, quitado in quitados:
                    cuerpos.append(quitado)
                    salida[indice] = "<< " + _MARCA.format(len(cuerpos) - 1)
                sustituciones += interiores
                pendientes = []
                continue
        salida.append(c)
        i += 1
    if len(pila) > 1:
        sustituciones.append(texto[pila[1].inicio :])
    return _Superficie("".join(salida), cuerpos, sustituciones)


def _restaurar(palabra: str, cuerpos: list[_Cuerpo]) -> str:
    """Devuelve a una palabra los heredocs que se le quitaron, con cuerpo y cierre."""
    for numero in range(len(cuerpos) - 1, -1, -1):
        marca = "<< " + _MARCA.format(numero)
        pos = palabra.find(marca)
        if pos == -1:
            continue
        cuerpo = cuerpos[numero]
        palabra = palabra[:pos] + cuerpo.operador + palabra[pos + len(marca) :]
        salto = palabra.find("\n", pos + len(cuerpo.operador))
        if salto == -1:
            palabra += "\n" + cuerpo.quitado
        else:
            palabra = palabra[: salto + 1] + cuerpo.quitado + palabra[salto + 1 :]
    return palabra


@dataclass
class _Tokens:
    subcomandos: list[list[str]]
    cuerpos: list[list[_Cuerpo]]  # cuerpos de heredoc de cada subcomando, en orden
    tuberia: list[bool]  # True si el subcomando recibe la salida del anterior por `|`
    sustituciones: list[str]  # texto original de cada `$(…)` y `…` de primer nivel


def _tokenizar(comando: str, powershell: bool) -> _Tokens:
    superficie = _escanear(comando, powershell)
    cuerpos = superficie.cuerpos
    lex = shlex.shlex(superficie.texto, posix=not powershell, punctuation_chars=";&|<>()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""  # el recorrido ya quitó los comentarios, con la regla de bash
    resultado = _Tokens([], [], [], superficie.sustituciones)
    actual: list[str] = []
    actual_cuerpos: list[_Cuerpo] = []
    tuberia_actual = False
    tokens = list(lex)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        marca = _ES_MARCA.fullmatch(tokens[i + 1]) if i + 1 < len(tokens) else None
        if token and all(c in _SEPARADORES for c in token):
            if actual:
                resultado.subcomandos.append(actual)
                resultado.cuerpos.append(actual_cuerpos)
                resultado.tuberia.append(tuberia_actual)
            actual, actual_cuerpos = [], []
            tuberia_actual = token.strip("\n") in ("|", "|&")
        elif token == "<<" and marca:
            indice = int(marca.group(1))
            if indice >= len(cuerpos):
                raise ValueError("marca de heredoc sin cuerpo")
            actual_cuerpos.append(cuerpos[indice])
            i += 1
        else:
            if powershell and len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
                token = token[1:-1]
            if "" in token:
                token = _restaurar(token, cuerpos)
            actual.append(token)
        i += 1
    if actual:
        resultado.subcomandos.append(actual)
        resultado.cuerpos.append(actual_cuerpos)
        resultado.tuberia.append(tuberia_actual)
    return resultado


def dividir_comando(comando: str, powershell: bool = False) -> list[list[str]]:
    """Subcomandos separados por `;`, `&&`, `||`, `|`, `&`, paréntesis o saltos de línea.

    Las redirecciones quedan como palabras (`<`, `>`, `>>`, `<<<`). Los cuerpos de los
    heredocs se quitan de los subcomandos; una palabra que contenía un heredoc, como el
    `"$(cat <<'EOF' … EOF)"` de un commit, lo conserva completo. Con `powershell=True` la
    barra invertida no es un escape (PowerShell y `cmd`). Lanza ValueError si el
    comando no se puede analizar.
    """
    return _tokenizar(comando, powershell).subcomandos


# --- Bloqueo y fallo cerrado --------------------------------------------------------


def bloquear(guarda: str, mensaje: str) -> NoReturn:
    """Bloquea la acción: una sola línea en stderr y código de salida 2."""
    linea = " ".join(mensaje.split())
    print(f"[{guarda}] {linea}", file=sys.stderr)
    sys.exit(2)


def flujos_utf8() -> None:
    """UTF-8 en stdin, stdout y stderr, independiente de PYTHONUTF8 y PYTHONIOENCODING.

    Sin esas variables, Python en Windows usa cp1252 en las tuberías. Los flujos que no
    se pueden reconfigurar (los de las pruebas) se dejan como están.
    """
    for flujo in (sys.stdin, sys.stdout, sys.stderr):
        reconfigurar = getattr(flujo, "reconfigure", None)
        if reconfigurar is not None:
            reconfigurar(encoding="utf-8")


def ejecutar(guarda: str, revisar: Callable[[dict], None]) -> NoReturn:
    """Lee la entrada y ejecuta la guarda; ante cualquier error propio, bloquea."""
    try:
        flujos_utf8()
        revisar(leer_entrada())
    except SystemExit:
        raise
    except BaseException as error:  # noqa: BLE001 - fallo cerrado (FR-020)
        bloquear(
            guarda,
            f"La guarda falló ({type(error).__name__}); la acción se bloquea por precaución.",
        )
    sys.exit(0)


# --- Envoltorios delante del programa -----------------------------------------------

_SHELLS = {"bash", "sh"}
_POWERSHELL = {"powershell", "pwsh"}
_PYTHON = re.compile(r"python(\d+(\.\d+)?)?")
_ASIGNACION = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_OPCIONES_CON_VALOR = {
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "exec": {"-a"},
    "command": set(),
    "nohup": set(),
    "time": {"-f", "--format", "-o", "--output"},
    "nice": {"-n", "--adjustment"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
}


def _nombre(palabra: str) -> str:
    nombre = palabra.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return nombre.removesuffix(".exe")


def _es_interprete(palabra: str) -> bool:
    nombre = _nombre(palabra)
    return bool(_PYTHON.fullmatch(nombre)) or nombre in {"py", "node", "perl", "ruby"}


def _es_shell(palabra: str) -> bool:
    return _nombre(palabra) in _SHELLS | _POWERSHELL | {"cmd"}


def quitar_envoltorios(palabras: list[str]) -> list[str]:
    """Quita lo que va delante del programa: asignaciones y envoltorios.

    Se saltan `NOMBRE=valor`, `env [opciones] [NOMBRE=valor…]`, `exec`, `command`,
    `nohup`, `time`, `nice [-n N]`, `timeout [opciones] N` y `uv run`, del que se toma
    como programa la primera palabra que sea un intérprete o un shell.
    """
    resto = list(palabras)
    while resto:
        if _ASIGNACION.match(resto[0]):
            resto = resto[1:]
            continue
        nombre = _nombre(resto[0])
        if nombre in _OPCIONES_CON_VALOR:
            con_valor = _OPCIONES_CON_VALOR[nombre]
            i = 1
            while i < len(resto) and (
                resto[i].startswith("-") or (nombre == "env" and _ASIGNACION.match(resto[i]))
            ):
                i += 2 if resto[i] in con_valor else 1
            if nombre == "timeout" and i < len(resto):
                i += 1  # la duración
            resto = resto[i:]
            continue
        if nombre == "uv" and len(resto) > 1 and resto[1] == "run":
            args = resto[2:]
            indice = next(
                (k for k, w in enumerate(args) if _es_interprete(w) or _es_shell(w)), None
            )
            if indice is None:
                indice = next((k for k, w in enumerate(args) if not w.startswith("-")), len(args))
            resto = args[indice:]
            continue
        break
    return resto


# --- Extractor de texto ejecutable --------------------------------------------------


@dataclass
class ComandoInterior:
    texto: str
    powershell: bool  # True: se tokeniza sin `\` como escape (PowerShell o `cmd`)
    nivel: int
    cmd: bool = False


@dataclass
class Extraccion:
    comandos: list[ComandoInterior] = field(default_factory=list)
    codigos: list[str] = field(default_factory=list)
    anidamiento_excesivo: bool = False


def _opciones_de_codigo(palabra: str) -> set[str]:
    nombre = _nombre(palabra)
    if _PYTHON.fullmatch(nombre) or nombre == "py":
        return {"-c"}
    if nombre == "node":
        return {"-e", "--eval", "-p", "--print"}
    if nombre == "perl":
        return {"-e", "-E"}
    if nombre == "ruby":
        return {"-e"}
    return set()


def _codigo_de_interprete(palabras: list[str]) -> str | None:
    """Argumento de código en línea de python, py, node, perl o ruby, si lo hay."""
    opciones = _opciones_de_codigo(palabras[0])
    if not opciones:
        return None
    for i, arg in enumerate(palabras[1:], start=1):
        if arg in opciones:
            return palabras[i + 1] if i + 1 < len(palabras) else ""
        clave, igual, valor = arg.partition("=")
        if igual and clave in opciones:
            return valor
        if not arg.startswith("-") or arg in ("-m", "-"):
            return None
    return None


def _interior_de_shell(palabras: list[str]) -> tuple[str, bool, bool] | None:
    """Comando interior de `bash -c`, `sh -c`, `eval`, `pwsh -Command` o `cmd /c`.

    Devuelve `(texto, sin_escapes, es_cmd)`.
    """
    nombre, args = _nombre(palabras[0]), palabras[1:]
    if nombre == "eval":
        return (" ".join(args), False, False) if args else None
    if nombre in _SHELLS:
        for i, arg in enumerate(args):
            if arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]:
                return (args[i + 1], False, False) if i + 1 < len(args) else None
            if not arg.startswith("-"):
                return None
        return None
    if nombre in _POWERSHELL:
        for i, arg in enumerate(args):
            if arg.lower() in ("-command", "-c"):
                return (" ".join(args[i + 1 :]), True, False) if i + 1 < len(args) else None
        return None
    if nombre == "cmd":
        for i, arg in enumerate(args):
            if arg.lower() in ("/c", "//c", "/k", "//k"):
                return (" ".join(args[i + 1 :]), True, True) if i + 1 < len(args) else None
        return None
    return None


def _lee_de_stdin(palabras: list[str]) -> bool:
    """Intérprete o shell sin código en línea ni script: lee el programa de stdin."""
    if not (_es_interprete(palabras[0]) or _nombre(palabras[0]) in _SHELLS):
        return False
    if _codigo_de_interprete(palabras) is not None or _interior_de_shell(palabras):
        return False
    for arg in palabras[1:]:
        if arg in ("-", "-s"):
            return True
        if not arg.startswith("-"):
            return False
    return True


def extraer_texto_ejecutable(comando: str, powershell: bool = False) -> Extraccion:
    """Comandos interiores de shells y código en línea de intérpretes de `comando`.

    - Comandos interiores, con su nivel, para que cada guarda los analice con sus
      mismas reglas: `bash -c`, `sh -c`, `eval`, `pwsh -Command`, `cmd /c`,
      sustituciones `$(…)` y de comillas invertidas, heredocs y herestrings que
      alimentan a `bash` o `sh`, y lo que una tubería pasa a `bash` o `sh`. Se buscan
      también dentro de ellos.
    - Texto de código de `python`, `py`, `node`, `perl` y `ruby`: opción en línea,
      heredoc, herestring o lo que una tubería pasa al intérprete.
    - Un comando interior que no se puede analizar se devuelve como texto.
    - Con más de MAX_NIVELES shells anidados se marca anidamiento excesivo.
    """
    extraccion = Extraccion()
    _extraer(comando, powershell, False, 0, extraccion)
    return extraccion


def _texto_de_etapa(palabras: list[str], cuerpos: list[_Cuerpo]) -> str:
    return "\n".join([" ".join(palabras)] + [c.texto for c in cuerpos])


def _extraer(
    comando: str, powershell: bool, es_cmd: bool, nivel: int, extraccion: Extraccion
) -> None:
    tokens = _tokenizar(comando, powershell)
    interiores: list[tuple[str, bool, bool]] = []

    if not es_cmd:
        interiores += [(s, powershell, False) for s in tokens.sustituciones]

    etapas: list[tuple[list[str], list[_Cuerpo]]] = []
    for originales, cuerpos, en_tuberia in zip(
        tokens.subcomandos, tokens.cuerpos, tokens.tuberia, strict=True
    ):
        anteriores = etapas if en_tuberia else []
        etapas = [*anteriores, (originales, cuerpos)]
        palabras = quitar_envoltorios(originales)
        if not palabras:
            continue
        es_shell = _nombre(palabras[0]) in _SHELLS
        interprete = _es_interprete(palabras[0])

        interior = _interior_de_shell(palabras)
        if interior is not None:
            interiores.append(interior)
        codigo = _codigo_de_interprete(palabras)
        if codigo is not None:
            extraccion.codigos.append(codigo)

        for k, palabra in enumerate(palabras[:-1]):
            if palabra == "<<<":
                if interprete:
                    extraccion.codigos.append(palabras[k + 1])
                elif es_shell:
                    interiores.append((palabras[k + 1], False, False))
        for cuerpo in cuerpos:
            if es_shell:
                interiores.append((cuerpo.texto, False, False))
            elif interprete and codigo is None:
                extraccion.codigos.append(cuerpo.texto)

        if anteriores and _lee_de_stdin(palabras):
            texto = "\n".join(_texto_de_etapa(p, c) for p, c in anteriores)
            if interprete:
                extraccion.codigos.append(texto)
            else:
                interiores.append((texto, False, False))

    for texto, sin_escapes, es_cmd_interior in interiores:
        if nivel + 1 > MAX_NIVELES:
            extraccion.anidamiento_excesivo = True
            continue
        try:
            _tokenizar(texto, sin_escapes)
        except ValueError:
            extraccion.codigos.append(texto)
            continue
        extraccion.comandos.append(ComandoInterior(texto, sin_escapes, nivel + 1, es_cmd_interior))
        _extraer(texto, sin_escapes, es_cmd_interior, nivel + 1, extraccion)
