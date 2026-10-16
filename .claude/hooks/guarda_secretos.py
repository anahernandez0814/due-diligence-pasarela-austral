"""Guarda de secretos: PreToolUse (FR-001, FR-002, FR-020, FR-023; research R9).

Bloquea leer, buscar, editar o escribir `.env`, `.env.*` (salvo `.env.example`), `*.key` y
lo que hay dentro de `secrets/`, por cualquier herramienta de Claude Code:

- Read, Write, Edit y NotebookEdit: la ruta del archivo.
- Grep: `path` y `glob`, nunca `pattern`, que es el texto buscado (FR-002).
- Glob: `pattern` y `path`, porque el patrón es de rutas.
- Bash y PowerShell: cada palabra de cada subcomando, salvo el patrón de búsqueda; las
  búsquedas recursivas cuya raíz contiene secretos; y, con el extractor de `comun.py`,
  los comandos interiores (con estas mismas reglas) y el código en línea de intérpretes.

Contrato: specs/003-guardas-claude-code/contracts/guardas.md.
"""

import fnmatch
import glob
import os
import re
from pathlib import Path

import comun

GUARDA = "guarda_secretos"

ACCESO = (
    "Acceso bloqueado a un archivo de secretos ({ruta}) con {herramienta}. "
    "Usa .env.example para ver las variables."
)
CODIGO = (
    "Código en línea bloqueado: nombra un archivo de secretos ({construccion}). "
    "Usa .env.example para ver las variables."
)
RECURSIVA = (
    "Búsqueda recursiva bloqueada: {raiz} contiene archivos de secretos. "
    "Busca en una carpeta sin secretos o usa la herramienta Grep, rg o git grep."
)
ANIDAMIENTO = "Comando bloqueado por precaución: tiene más de 3 niveles de shells anidados."

# --- Archivos de secretos (data-model) ----------------------------------------------


def es_secreto(ruta: str, directorio: bool = False) -> bool:
    """`.env`, `.env.*` salvo `.env.example`, `*.key` o algo dentro de `secrets/`.

    Las mayúsculas no cuentan. Con `directorio=True`, la ruta es una carpeta y su último
    componente también cuenta como directorio.
    """
    partes = [p.casefold() for p in ruta.replace("\\", "/").split("/") if p not in ("", ".")]
    if not partes:
        return False
    nombre = partes[-1]
    carpetas = partes if directorio else partes[:-1]
    return (
        nombre == ".env"
        or (nombre.startswith(".env.") and nombre != ".env.example")
        or nombre.endswith(".key")
        or "secrets" in carpetas
    )


def _mostrar(ruta: str) -> str:
    return ruta or "."


def _secreto_en_ruta(palabra: str, base: Path, cwd: Path, expandir: bool = True) -> str | None:
    """Ruta normalizada del secreto que nombra `palabra`, o None.

    Con `expandir=True`, los comodines se expanden contra el `cwd`, como lo haría el
    shell (sin archivos ocultos salvo que el patrón empiece por `.`).
    """
    if not palabra:
        return None
    ruta = comun.normalizar_ruta(palabra, base, cwd)
    completa = ruta if os.path.isabs(ruta) else str(base / ruta)
    if es_secreto(ruta, palabra.endswith(("/", "\\")) or os.path.isdir(completa)):
        return _mostrar(ruta)
    if expandir and "\n" not in palabra and any(c in palabra for c in "*?["):
        for coincidencia in glob.iglob(palabra, root_dir=cwd, recursive=True):
            ruta = comun.normalizar_ruta(coincidencia, base, cwd)
            completa = ruta if os.path.isabs(ruta) else str(base / ruta)
            if es_secreto(ruta, os.path.isdir(completa)):
                return _mostrar(ruta)
    return None


# --- Patrones de rutas (Grep y Glob) --------------------------------------------------

_CANDIDATOS = (".env", ".env.local", "x.key", "secrets/x")


def _expandir_llaves(texto: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", texto)
    if not m:
        return [texto]
    return [
        variante
        for alternativa in m.group(1).split(",")
        for variante in _expandir_llaves(texto[: m.start()] + alternativa + texto[m.end() :])
    ]


def _patron_nombra_secreto(patron: str) -> bool:
    """Un patrón de rutas (glob) nombra secretos si alcanzaría `.env`, `x.key` o `secrets/`.

    Un patrón sin `env`, `key` ni `secret` literal (`*`, `**/*.py`) no los nombra.
    """
    texto = patron.replace("\\", "/").casefold()
    for variante in _expandir_llaves(texto):
        if es_secreto(variante):
            return True
        if any(t in variante for t in ("env", "key", "secret")):
            for candidato in _CANDIDATOS:
                if fnmatch.fnmatchcase(candidato, variante):
                    return True
                if fnmatch.fnmatchcase("a/" + candidato, variante):
                    return True
    return False


# --- Nombres de secretos en el texto de código (contrato, U2) -------------------------

_NOMBRE_SECRETO = re.compile(
    r"(?<![\w.-])(?:"
    r"\.env(?!\w)(?!\.example(?![\w.-]))"  # .env y .env.<sufijo>, salvo .env.example
    r"|[\w.-]*[\w-]\.key(?=[\"'\s]|$)"  # <nombre>.key seguido de comilla, espacio o fin
    r"|secrets[/\\]"
    r")",
    re.IGNORECASE,
)


def nombra_secreto(texto: str) -> bool:
    return bool(_NOMBRE_SECRETO.search(texto))


# --- Patrón de búsqueda de grep, rg, git grep, Select-String y findstr ----------------

_GREP = {"grep", "egrep", "fgrep"}
_GREP_CON_VALOR = {
    "-e", "-f", "-m", "-A", "-B", "-C", "-d", "-D",
    "--regexp", "--file", "--max-count", "--after-context", "--before-context",
    "--context", "--directories", "--devices", "--label", "--include", "--exclude",
    "--exclude-dir", "--exclude-from", "--binary-files", "--group-separator",
}  # fmt: skip
_RG_CON_VALOR = {
    "-e", "-f", "-g", "-t", "-T", "-m", "-A", "-B", "-C", "-j", "-M", "-d", "-r", "-E",
    "--regexp", "--file", "--glob", "--iglob", "--type", "--type-not", "--type-add",
    "--type-clear", "--max-count", "--after-context", "--before-context", "--context",
    "--threads", "--max-columns", "--max-depth", "--replace", "--encoding", "--pre",
    "--pre-glob", "--sort", "--sortr", "--ignore-file", "--max-filesize", "--colors",
    "--color", "--path-separator", "--context-separator", "--engine",
}  # fmt: skip
_GIT_GREP_CON_VALOR = {
    "-e", "-f", "-A", "-B", "-C", "-m",
    "--max-depth", "--threads", "--max-count", "--context", "--after-context",
    "--before-context",
}  # fmt: skip
_OPCIONES_DE_PATRON = {"-e", "--regexp"}
_OPCIONES_DE_ARCHIVO_DE_PATRON = {"-f", "--file"}
_GIT_CON_VALOR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
_FIND_PATRONES = {
    "-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename",
    "-regex", "-iregex", "-lname", "-ilname",
}  # fmt: skip
_LECTORES = {"cat", "head", "tail", "grep", "less", "more"}
_XARGS_CON_VALOR = {"-I", "-n", "-L", "-P", "-d", "-E", "-s", "-a"}
_LECTORES_POWERSHELL = {"get-content", "gc", "cat", "type", "select-string", "sls"}


def _nombre(palabra: str) -> str:
    return palabra.replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")


def _opciones(
    args: list[str], con_valor: set[str]
) -> tuple[list[tuple[int, str, int | None]], list[int]]:
    """Recorre `args` al estilo getopt.

    Devuelve las opciones `(índice, nombre, índice del valor o None)` y los índices de
    los argumentos posicionales. Una opción corta con el valor pegado (`-eX`) no tiene
    valor aparte.
    """
    opciones: list[tuple[int, str, int | None]] = []
    posicionales: list[int] = []
    i, fin = 0, False
    while i < len(args):
        arg = args[i]
        if fin or arg == "-" or not arg.startswith("-"):
            posicionales.append(i)
        elif arg == "--":
            fin = True
        else:
            larga = arg.startswith("--")
            nombre = arg.split("=", 1)[0] if larga else arg[:2]
            separado = ("=" not in arg) if larga else len(arg) == 2
            if nombre in con_valor and separado and i + 1 < len(args):
                opciones.append((i, nombre, i + 1))
                i += 2
                continue
            opciones.append((i, nombre, None))
        i += 1
    return opciones, posicionales


def _busqueda(args: list[str], con_valor: set[str]) -> tuple[set[int], list[int]]:
    """Índices de los patrones de búsqueda y de las rutas de grep, rg o git grep."""
    opciones, posicionales = _opciones(args, con_valor)
    patrones: set[int] = set()
    explicito = False
    for indice, nombre, valor in opciones:
        if nombre in _OPCIONES_DE_PATRON:
            patrones.add(indice if valor is None else valor)
            explicito = True
        elif nombre in _OPCIONES_DE_ARCHIVO_DE_PATRON:
            explicito = True
    if not explicito and posicionales:
        patrones.add(posicionales[0])
        posicionales = posicionales[1:]
    return patrones, posicionales


def _subcomando_git(args: list[str]) -> int | None:
    """Índice del subcomando de git en `args`, saltando sus opciones globales."""
    i = 0
    while i < len(args):
        if args[i] in _GIT_CON_VALOR:
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            return i
    return None


def _parametro_powershell(arg: str, nombre: str) -> bool:
    """`arg` es el parámetro `nombre` de PowerShell, quizá abreviado (`-Pat`)."""
    arg = arg.lower().split(":", 1)[0]
    return len(arg) >= 2 and arg.startswith("-") and nombre.startswith(arg)


def _patron_select_string(args: list[str]) -> set[int]:
    con_valor = ("-path", "-literalpath", "-encoding", "-context", "-include", "-exclude")
    i, posicionales = 0, []
    while i < len(args):
        arg = args[i]
        if _parametro_powershell(arg, "-pattern") and len(arg) >= 4:
            return {i + 1}
        if arg.startswith("-"):
            i += 2 if any(_parametro_powershell(arg, n) for n in con_valor) else 1
            continue
        posicionales.append(i)
        i += 1
    return {posicionales[0]} if posicionales else set()


def _patron_findstr(args: list[str]) -> set[int]:
    explicitos = {i for i, a in enumerate(args) if a.lower().startswith("/c:")}
    if explicitos:
        return explicitos
    posicionales = [i for i, a in enumerate(args) if not a.startswith("/")]
    return {posicionales[0]} if posicionales else set()


def _patrones(programa: list[str]) -> set[int]:
    """Índices, dentro de `programa`, de las palabras que son texto buscado, no rutas."""
    nombre, args = _nombre(programa[0]), programa[1:]
    if nombre in _GREP:
        indices = _busqueda(args, _GREP_CON_VALOR)[0]
    elif nombre == "rg":
        indices = _busqueda(args, _RG_CON_VALOR)[0]
    elif nombre == "git":
        sub = _subcomando_git(args)
        if sub is None or args[sub] != "grep":
            return set()
        resto = args[sub + 1 :]
        return {sub + 2 + i for i in _busqueda(resto, _GIT_GREP_CON_VALOR)[0]}
    elif nombre in ("select-string", "sls"):
        indices = _patron_select_string(args)
    elif nombre == "findstr":
        indices = _patron_findstr(args)
    elif nombre == "find":
        indices = {i + 1 for i, a in enumerate(args[:-1]) if a in _FIND_PATRONES}
    else:
        return set()
    return {i + 1 for i in indices}


# --- Búsquedas recursivas (R9, decisión 2) --------------------------------------------


def _grep_recursivo(args: list[str]) -> bool:
    for i, arg in enumerate(args):
        if arg == "--":
            return False
        if arg in ("--recursive", "--dereference-recursive", "--directories=recurse"):
            return True
        if arg in ("-d", "--directories") and args[i + 1 : i + 2] == ["recurse"]:
            return True
        if re.fullmatch(r"-[a-zA-Z]*[rR][a-zA-Z]*", arg):
            return True
    return False


def _rg_sin_ignorar(args: list[str]) -> bool:
    for arg in args:
        if arg == "--":
            return False
        if arg.startswith("--no-ignore") or arg in ("--hidden", "-."):
            return True
        if re.fullmatch(r"-[a-zA-Z.]*u[a-zA-Z.]*", arg):
            return True
    return False


def _raices_find(args: list[str]) -> list[str]:
    raices = []
    for arg in args:
        if arg.startswith(("-", "(", "!", ")")):
            break
        raices.append(arg)
    return raices or ["."]


def _find_con_lector(args: list[str]) -> bool:
    return any(
        a in ("-exec", "-execdir", "-ok", "-okdir") and _nombre(args[i + 1]) in _LECTORES
        for i, a in enumerate(args[:-1])
    )


def _xargs_con_lector(programa: list[str]) -> bool:
    if _nombre(programa[0]) != "xargs":
        return False
    _, posicionales = _opciones(programa[1:], _XARGS_CON_VALOR)
    return bool(posicionales) and _nombre(programa[1 + posicionales[0]]) in _LECTORES


def _gci_recursivo(programa: list[str], powershell: bool) -> bool:
    nombres = {"get-childitem", "gci"} | ({"ls", "dir"} if powershell else set())
    if _nombre(programa[0]) not in nombres:
        return False
    return any(_parametro_powershell(a, "-recurse") for a in programa[1:])


def _raices_gci(args: list[str]) -> list[str]:
    raices, i, posicionales = [], 0, []
    while i < len(args):
        arg = args[i]
        if any(_parametro_powershell(arg, n) for n in ("-path", "-literalpath")):
            raices += args[i + 1 : i + 2]
            i += 2
        elif any(_parametro_powershell(arg, n) for n in ("-filter", "-include", "-exclude")):
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            posicionales.append(arg)
            i += 1
    return raices + posicionales[:1] or ["."]


def _raices_recursivas(subcomandos: list[list[str]], powershell: bool) -> list[str]:
    """Raíces de las búsquedas recursivas del comando."""
    programas = [comun.quitar_envoltorios(s) for s in subcomandos]
    raices: list[str] = []
    for k, programa in enumerate(programas):
        if not programa:
            continue
        nombre, args = _nombre(programa[0]), programa[1:]
        siguientes = [p for p in programas[k + 1 :] if p]
        if nombre in _GREP and _grep_recursivo(args):
            _, rutas = _busqueda(args, _GREP_CON_VALOR)
            raices += [args[i] for i in rutas] or ["."]
        elif nombre == "rg" and _rg_sin_ignorar(args):
            _, rutas = _busqueda(args, _RG_CON_VALOR)
            raices += [args[i] for i in rutas] or ["."]
        elif nombre == "find" and (
            _find_con_lector(args) or any(_xargs_con_lector(p) for p in siguientes)
        ):
            raices += _raices_find(args)
        elif _gci_recursivo(programa, powershell) and any(
            _nombre(p[0]) in _LECTORES_POWERSHELL for p in siguientes
        ):
            raices += _raices_gci(args)
    return raices


def _contiene_secretos(raiz: str, base: Path, cwd: Path) -> bool:
    """Recorre la raíz con os.walk, podando solo `.git`; para en el primer secreto."""
    ruta = comun.normalizar_ruta(raiz, base, cwd)
    completa = ruta if os.path.isabs(ruta) else str(base / ruta)
    if os.path.isfile(completa):
        return es_secreto(ruta)
    if es_secreto(ruta, directorio=True):
        return True
    for carpeta, subcarpetas, archivos in os.walk(completa):
        subcarpetas[:] = [s for s in subcarpetas if s != ".git"]
        for archivo in archivos:
            if es_secreto(comun.normalizar_ruta(os.path.join(carpeta, archivo), base)):
                return True
    return False


# --- Comandos de terminal -------------------------------------------------------------


def _revisar_comando(
    texto: str, powershell: bool, base: Path, cwd: Path, herramienta: str
) -> str | None:
    """Rutas y búsquedas recursivas de un comando, sin entrar en su texto ejecutable."""
    subcomandos = comun.dividir_comando(texto, powershell=powershell)
    for sub in subcomandos:
        programa = comun.quitar_envoltorios(sub)
        delante = len(sub) - len(programa)
        omitir = {delante + i for i in _patrones(programa)} if programa else set()
        for k, palabra in enumerate(sub):
            if k in omitir:
                continue
            candidatos = [palabra]
            if "=" in palabra:
                candidatos.append(palabra.split("=", 1)[1])
            for candidato in candidatos:
                ruta = _secreto_en_ruta(candidato, base, cwd)
                if ruta:
                    return ACCESO.format(ruta=ruta, herramienta=herramienta)
    for raiz in _raices_recursivas(subcomandos, powershell):
        if _contiene_secretos(raiz, base, cwd):
            return RECURSIVA.format(raiz=_mostrar(comun.normalizar_ruta(raiz, base, cwd)))
    return None


def _revisar_terminal(
    comando: str, powershell: bool, base: Path, cwd: Path, herramienta: str
) -> str | None:
    # Primero el texto ejecutable, para que el código en línea reciba su propio mensaje
    # aunque su argumento también parezca una ruta.
    extraccion = comun.extraer_texto_ejecutable(comando, powershell=powershell)
    if extraccion.anidamiento_excesivo:
        return ANIDAMIENTO
    if any(nombra_secreto(codigo) for codigo in extraccion.codigos):
        return CODIGO.format(construccion=f"código de un intérprete en {herramienta}")
    textos = [(comando, powershell)] + [(c.texto, c.powershell) for c in extraccion.comandos]
    for texto, sin_escapes in textos:
        motivo_ = _revisar_comando(texto, sin_escapes, base, cwd, herramienta)
        if motivo_:
            return motivo_
    return None


# --- Decisión -------------------------------------------------------------------------


def motivo(entrada: dict) -> str | None:
    """Motivo del bloqueo, o None si la acción se permite."""
    herramienta = entrada.get("tool_name") or ""
    datos = entrada.get("tool_input") or {}
    base = comun.raiz(entrada)
    cwd = comun.cwd(entrada, base)

    if herramienta in ("Read", "Write", "Edit", "NotebookEdit"):
        clave = "notebook_path" if herramienta == "NotebookEdit" else "file_path"
        ruta = _secreto_en_ruta(datos.get(clave) or "", base, cwd, expandir=False)
        return ACCESO.format(ruta=ruta, herramienta=herramienta) if ruta else None

    if herramienta in ("Grep", "Glob"):
        carpeta = datos.get("path") or ""
        if carpeta:
            ruta = comun.normalizar_ruta(carpeta, base, cwd)
            if es_secreto(ruta, directorio=True):
                return ACCESO.format(ruta=_mostrar(ruta), herramienta=herramienta)
        patron = datos.get("glob" if herramienta == "Grep" else "pattern") or ""
        if patron and _patron_nombra_secreto(patron):
            return ACCESO.format(ruta=patron, herramienta=herramienta)
        return None

    if herramienta in ("Bash", "PowerShell"):
        comando = datos.get("command") or ""
        return _revisar_terminal(comando, herramienta == "PowerShell", base, cwd, herramienta)

    return None


def revisar(entrada: dict) -> None:
    motivo_ = motivo(entrada)
    if motivo_:
        comun.bloquear(GUARDA, motivo_)


if __name__ == "__main__":
    comun.ejecutar(GUARDA, revisar)
