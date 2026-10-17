"""Guarda de spec previa: PreToolUse (FR-009 a FR-013, FR-020, FR-023; R7, R10, R14).

Bloquea escribir código protegido si la rama no es de un ticket (`NNN-nombre`) o si
falta `spec.md`, `plan.md` o `tasks.md` en su carpeta `specs/NNN-*/`:

- Write y Edit: `file_path`. NotebookEdit: `notebook_path`.
- Bash y PowerShell: los destinos de escritura reconocibles (R10) del comando y de sus
  comandos interiores, y las rutas de código protegido que nombra el código en línea de
  los intérpretes (U4). No se distingue lectura de escritura.
- Más de 3 niveles de shells anidados se bloquean en cualquier rama.

Contrato: specs/003-guardas-claude-code/contracts/guardas.md.
"""

import fnmatch
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import comun

GUARDA = "guarda_spec_previa"
DOCUMENTOS = ("spec.md", "plan.md", "tasks.md")

SIN_TICKET = (
    "{ruta} es código protegido y la rama '{rama}' no es de un ticket (NNN-nombre). "
    "Crea la rama con /siguiente-ticket."
)
SIN_CARPETA = "No existe specs/{nnn}-*/ para la rama '{rama}'. Ejecuta /speckit-specify."
VARIAS = "Hay varias carpetas specs/{nnn}-*/ ({lista}); el ticket en curso es ambiguo."
FALTAN = (
    "Falta {lista} en specs/{carpeta}/. "
    "Completa /speckit-plan o /speckit-tasks antes de escribir código."
)
ANIDAMIENTO = "Comando bloqueado por precaución: tiene más de 3 niveles de shells anidados."
SETTINGS_LOCAL = (
    ".claude/settings.local.json no se modifica desde Claude Code en ninguna rama: puede "
    "desactivar las guardas. Edítalo fuera de Claude Code."
)
_SETTINGS_LOCAL = ".claude/settings.local.json"
VEREDICTOS = (
    "El directorio de veredictos solo lo escribe el registro de la revisión. Ejecuta /abrir-pr."
)
_VEREDICTOS = ".claude/veredictos"
COPIA_A_CLAUDE = (
    "Copiar de forma recursiva o mover hacia la carpeta .claude se bloquea en cualquier rama, "
    "sin mirar el origen: podría crear un veredicto o desactivar las guardas. Usa un "
    "subdirectorio (.claude/agents/…) o nombra los archivos."
)
BORRAR_CLAUDE = (
    ".claude no se borra ni se mueve entera desde Claude Code: contiene los veredictos y "
    "las guardas."
)

# --- Código protegido (data-model) ----------------------------------------------------

_ARCHIVOS_PROTEGIDOS = {".claude/settings.json", ".claude/settings.local.json", ".mcp.json"}
_CARPETAS_PROTEGIDAS = (".claude/hooks", "plugins", ".claude-plugin")


def _relativa(ruta: str) -> str | None:
    """La ruta en minúsculas y con `/`, o None si está fuera de la raíz (absoluta)."""
    texto = ruta.replace("\\", "/").casefold()
    if texto.startswith("/") or re.match(r"^[a-z]:/", texto):
        return None
    return "/".join(p for p in texto.split("/") if p not in ("", "."))


def ruta_privada(ruta: str) -> str | None:
    """El mensaje de bloqueo si `ruta` es `.claude/settings.local.json` (FR-025 de #3) o está
    en `.claude/veredictos/` (FR-020 de #4); None en otro caso.

    Los dos se bloquean en cualquier rama: no se versionan, así que ningún PR vería el
    cambio. `ruta` es relativa a la raíz y ya está normalizada.
    """
    relativa = _relativa(ruta)  # sin distinguir mayúsculas: Windows y macOS no las distinguen
    if relativa == _SETTINGS_LOCAL:
        return SETTINGS_LOCAL
    if relativa and (relativa == _VEREDICTOS or relativa.startswith(_VEREDICTOS + "/")):
        return VEREDICTOS
    return None


def es_protegido(ruta: str) -> bool:
    """`src/**/*.py`, `.claude/hooks/**`, los dos settings, `.mcp.json`, `plugins/**` y
    `.claude-plugin/**`, salvo los `test_*.py`. `ruta` es relativa a la raíz."""
    relativa = _relativa(ruta)
    if not relativa or fnmatch.fnmatchcase(relativa.rsplit("/", 1)[-1], "test_*.py"):
        return False
    return (
        (relativa.startswith("src/") and relativa.endswith(".py"))
        or relativa in _ARCHIVOS_PROTEGIDOS
        or any(relativa.startswith(c + "/") for c in _CARPETAS_PROTEGIDAS)
    )


def _es_carpeta_protegida(ruta: str) -> bool:
    """Carpeta en la que copiar o mover un archivo puede crear código protegido."""
    relativa = _relativa(ruta)
    if not relativa:
        return False
    return any(
        relativa == c or relativa.startswith(c + "/") for c in ("src", *_CARPETAS_PROTEGIDAS)
    )


_RAICES_PROTEGIDAS = ("src", *_ARCHIVOS_PROTEGIDOS, *_CARPETAS_PROTEGIDAS)


def contiene_protegido(ruta: str, carpeta: bool = True) -> bool:
    """Borrar, restaurar o mover `ruta` alcanza código protegido (revisión de la parada E).

    Cuenta la raíz (relativa vacía), un ancestro de algo protegido (`.claude`) y, si
    `ruta` es una carpeta, una carpeta dentro de una zona protegida (`src/app`). Una ruta
    fuera de la raíz no cuenta.
    """
    relativa = _relativa(ruta)
    if relativa is None or relativa.split("/")[0] == "..":
        return False
    if relativa == "":
        return True
    if any(r.startswith(relativa + "/") for r in _RAICES_PROTEGIDAS):
        return True
    return carpeta and _es_carpeta_protegida(relativa)


# --- Código protegido en el texto (U4) ------------------------------------------------

_SEPARADOR = r"(?:\\\\|\\|/)"
_RUTA_EN_TEXTO = re.compile(
    rf"(?<![\w.-])(?:\.{_SEPARADOR})?("
    rf"(?:\.claude-plugin|\.claude|plugins|src)(?:{_SEPARADOR}[\w.-]+)+"
    r"|\.mcp\.json(?![\w.-])"
    r")",
    re.IGNORECASE,
)


def rutas_en_texto(texto: str) -> list[str]:
    """Rutas con `/`, `\\` o `\\\\` como separador que empiezan por una carpeta o un
    archivo protegido; quien llama decide si son código protegido."""
    return [re.sub(r"\\\\|\\", "/", m.group(1)) for m in _RUTA_EN_TEXTO.finditer(texto)]


# --- Destinos de escritura por terminal (R10) -----------------------------------------

_NULOS = {"/dev/null", "nul", "$null"}
_COPIA_CON_VALOR = {
    "-t", "-S", "-m", "-o", "-g",
    "--target-directory", "--suffix", "--mode", "--owner", "--group",
}  # fmt: skip
_COPIA_POWERSHELL = {"cp", "cpi", "copy", "copy-item", "mv", "mi", "move", "move-item"}
_MOVIMIENTO = {"mv", "mi", "move", "move-item"}
_ESCRITURA_POWERSHELL = {"set-content", "add-content", "out-file", "new-item", "ni", "tee-object"}
_BORRADO_POWERSHELL = {"remove-item", "del", "erase", "rd", "ri", "rmdir"}
_GIT_CON_VALOR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
_POWERSHELL_RUTA = ("-path", "-literalpath", "-filepath")
_POWERSHELL_OTRO_VALOR = (
    "-value", "-encoding", "-itemtype", "-type", "-inputobject", "-stream", "-width",
    "-filter", "-include", "-exclude", "-credential", "-variable",
)  # fmt: skip


def _nombre(palabra: str) -> str:
    return palabra.replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")


def _parametro(arg: str, nombres: tuple[str, ...]) -> bool:
    """`arg` es uno de los parámetros de PowerShell `nombres`, quizá abreviado."""
    arg = arg.lower().split(":", 1)[0]
    return len(arg) >= 2 and arg.startswith("-") and any(n.startswith(arg) for n in nombres)


def _redirecciones(palabras: list[str]) -> Iterator[str]:
    for k, palabra in enumerate(palabras[:-1]):
        if ">" not in palabra or not set(palabra) <= set("<>&|"):
            continue
        siguiente = palabras[k + 1]
        if palabra.endswith("&") and re.fullmatch(r"\d+|-", siguiente):
            continue  # duplicación de descriptores: 2>&1
        if siguiente.lower() not in _NULOS:
            yield siguiente


def _copia(args: list[str], powershell: bool) -> tuple[str | None, bool, list[str]]:
    """`(destino, es carpeta, fuentes)` de cp, mv, install, copy, Copy-Item o Move-Item."""
    destino, carpeta, posicionales, fuentes = None, False, [], []
    i = 0
    while i < len(args):
        arg = args[i]
        if powershell and _parametro(arg, ("-destination",)):
            destino = args[i + 1] if i + 1 < len(args) else None
            i += 2
        elif powershell and _parametro(arg, _POWERSHELL_RUTA):
            fuentes += args[i + 1 : i + 2]
            i += 2
        elif powershell and _parametro(arg, _POWERSHELL_OTRO_VALOR):
            i += 2
        elif arg in ("-t", "--target-directory") and i + 1 < len(args):
            destino, carpeta = args[i + 1], True
            i += 2
        elif arg.startswith("--target-directory="):
            destino, carpeta = arg.split("=", 1)[1], True
            i += 1
        elif arg in _COPIA_CON_VALOR:
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            posicionales.append(arg)
            i += 1
    if destino is None and posicionales and len(fuentes) + len(posicionales) >= 2:
        destino, posicionales = posicionales[-1], posicionales[:-1]
    return destino, carpeta, fuentes + posicionales


def _origen_opaco(fuente: str) -> bool:
    """El origen no deja saber qué nombres llegan: termina en `/.` o lleva comodines."""
    texto = fuente.replace("\\", "/")
    return texto.endswith("/.") or any(c in texto for c in "*?[")


def _termina_en_barra(fuente: str) -> bool:
    """En macOS y BSD, `cp -R origen/ destino` copia el contenido de `origen`."""
    return fuente.endswith(("/", "\\"))


def _sin_directorio_de_destino(args: list[str]) -> bool:
    """`-T` o `--no-target-directory`, suelto o dentro de un grupo (`-rT`): el origen se
    copia o se mueve *como* el destino, así que su contenido llega al destino."""
    return any(
        arg == "--no-target-directory" or (re.fullmatch(r"-[a-zA-Z]*T[a-zA-Z]*", arg) is not None)
        for arg in args
    )


def _es_recursiva(args: list[str], powershell: bool) -> bool:
    """`cp -r`, `-R`, `-a`, `--recursive`, `--archive` o `-Recurse`."""
    for arg in args:
        if powershell and _parametro(arg, ("-recurse",)):
            return True
        if arg in ("--recursive", "--archive") or re.fullmatch(r"-[a-zA-Z]*[rRa][a-zA-Z]*", arg):
            return True
    return False


def _escritura_powershell(nombre: str, args: list[str]) -> Iterator[str]:
    """Rutas de Set-Content, Add-Content, Out-File, New-Item, Tee-Object y Remove-Item.

    Se toman los valores de `-Path`, `-LiteralPath` y `-FilePath` y todos los argumentos
    posicionales: si un parámetro desconocido lleva valor, sobra una ruta, nunca falta.
    """
    rutas, nombre_item, i = [], None, 0
    while i < len(args):
        arg = args[i]
        if _parametro(arg, _POWERSHELL_RUTA):
            rutas += args[i + 1 : i + 2]
            i += 2
        elif nombre in ("new-item", "ni") and _parametro(arg, ("-name",)):
            nombre_item = args[i + 1] if i + 1 < len(args) else None
            i += 2
        elif _parametro(arg, _POWERSHELL_OTRO_VALOR):
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            rutas.append(arg)
            i += 1
    if nombre_item:
        rutas = [f"{r}/{nombre_item}" for r in rutas or ["."]]
    yield from rutas


def _posicionales(args: list[str], con_valor: tuple[str, ...] = ()) -> list[str]:
    """Argumentos que no son opciones, saltando el valor de las opciones `con_valor`."""
    omitir = {i + 1 for i, a in enumerate(args) if a in con_valor}
    return [a for i, a in enumerate(args) if i not in omitir and not a.startswith("-")]


def _rutas_de_git(args: list[str], cwd: Path) -> tuple[list[str], Path]:
    """Rutas que modifican `git rm`, `git mv`, `git checkout` y `git restore`, y la
    carpeta respecto a la que se resuelven (la de `git -C <dir>`, si la hay).

    En `git checkout` sin `--`, los posicionales a partir del segundo son rutas, y el
    primero solo si existe en disco: `git checkout 003-x` no cuenta.
    """
    i, carpeta = 0, cwd
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            carpeta = Path(os.path.join(carpeta, args[i + 1]))
        i += 2 if args[i] in _GIT_CON_VALOR else 1
    if i >= len(args):
        return [], carpeta
    subcomando, resto = args[i], args[i + 1 :]
    if subcomando == "checkout":
        if "--" in resto:
            return resto[resto.index("--") + 1 :], carpeta
        posicionales = _posicionales(resto, ("-b", "-B", "--orphan"))
        primero = posicionales[:1]
        if primero and not os.path.exists(os.path.join(carpeta, primero[0])):
            primero = []
        return primero + posicionales[1:], carpeta
    if subcomando in ("rm", "mv"):
        return _posicionales(resto), carpeta
    if subcomando == "restore":
        return _posicionales(resto, ("-s", "--source", "--pathspec-from-file")), carpeta
    return [], carpeta


_CAMBIO_DE_CARPETA = {"cd", "pushd", "chdir", "set-location", "sl"}


def _nueva_carpeta(args: list[str], base: Path, cwd: Path) -> Path:
    """Carpeta tras `cd`, `pushd`, `Set-Location`, `sl` o `chdir` con argumento literal.

    `cd -`, `cd ~`, `cd $X` y `cd` sin argumento dejan la carpeta como estaba (residual
    declarado en R10).
    """
    destino = None
    for i, arg in enumerate(args):
        if _parametro(arg, ("-path", "-literalpath")):
            destino = args[i + 1] if i + 1 < len(args) else None
            break
        if not arg.startswith("-"):
            destino = arg
            break
    if not destino or destino.startswith("~") or any(c in destino for c in "$%`"):
        return cwd
    ruta = comun.normalizar_ruta(destino, base, cwd)
    return Path(ruta) if os.path.isabs(ruta) else base / ruta


def destinos(texto: str, powershell: bool, base: Path, cwd: Path) -> Iterator[tuple[str, str]]:
    """`(ruta normalizada, tipo)` de cada ruta que el comando escribe, borra, restaura o
    mueve. Tipos:

    - `archivo`: se escribe en la ruta;
    - `copia`: la ruta es la carpeta de destino de una copia o un movimiento;
    - `borrado`: se borra, se restaura desde git o es la fuente de un movimiento;
    - `borrado_carpeta`: lo mismo, y la ruta es una carpeta;
    - `claude_entera`: la ruta es `.claude` y se borra o se mueve entera;
    - `copia_recursiva` y `movimiento`: la ruta es el destino de una copia recursiva o de
      un movimiento, sin mirar el origen;
    - `copia_con_comodin`: copia no recursiva cuyo origen lleva comodines;
    - `copia_oculta`: lo mismo que `copia_recursiva`, y el origen oculta los nombres que
      llegan (`/.`, comodines, barra final o `-T`/`--no-target-directory`).

    Las rutas se resuelven tras los `cd` del propio comando (revisiones D y E).
    """
    actual = cwd

    def resolver(ruta: str, carpeta: Path | None = None) -> str:
        return comun.normalizar_ruta(ruta, base, carpeta or actual)

    def es_carpeta(ruta: str, carpeta: Path | None = None) -> bool:
        return ruta.endswith(("/", "\\")) or os.path.isdir(os.path.join(carpeta or actual, ruta))

    def borrado(ruta: str, carpeta: Path | None = None) -> tuple[str, str]:
        tipo = "borrado_carpeta" if es_carpeta(ruta, carpeta) else "borrado"
        return resolver(ruta, carpeta), tipo

    def borrado_directo(ruta: str) -> Iterator[tuple[str, str]]:
        """Borrado con rm, mv o Remove-Item; `.claude` entera añade `claude_entera`. El
        `git checkout` o `git restore` de `.claude` no: no toca lo que git no versiona."""
        yield borrado(ruta)
        if resolver(ruta) == ".claude":
            yield ".claude", "claude_entera"

    subcomandos = comun.dividir_comando(texto, powershell=powershell)
    for sub in comun.con_lanzados_de_find(subcomandos):  # find -exec <cmd> (FR-026)
        for ruta in _redirecciones(sub):
            yield resolver(ruta), "archivo"
        programa = comun.quitar_envoltorios(sub)
        if not programa:
            continue
        nombre, args = _nombre(programa[0]), programa[1:]
        if nombre in _CAMBIO_DE_CARPETA:
            actual = _nueva_carpeta(args, base, actual)
        elif nombre == "tee":
            yield from ((resolver(a), "archivo") for a in _posicionales(args))
        elif nombre in ("cp", "mv", "install") or (powershell and nombre in _COPIA_POWERSHELL):
            destino, carpeta, fuentes = _copia(args, powershell)
            if nombre in _MOVIMIENTO:
                for f in fuentes:  # mover también borra la fuente
                    yield from borrado_directo(f)
            if destino is None:
                continue
            # La regla es sobre el destino, no sobre el origen (parada D, segunda ronda).
            if nombre in _MOVIMIENTO:
                yield resolver(destino), "movimiento"
            elif _es_recursiva(args, powershell):
                yield resolver(destino), "copia_recursiva"
                if any(
                    _origen_opaco(f) or _termina_en_barra(f) for f in fuentes
                ) or _sin_directorio_de_destino(args):
                    yield resolver(destino), "copia_oculta"
            elif any(_origen_opaco(f) for f in fuentes):
                # Sin recursión, pero con comodines: no se ven los nombres (parada F)
                yield resolver(destino), "copia_con_comodin"
            if carpeta or es_carpeta(destino):
                yield resolver(destino), "copia"
                for fuente in fuentes:
                    nombre_fuente = fuente.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
                    yield resolver(destino.rstrip("/\\") + "/" + nombre_fuente), "archivo"
            else:
                yield resolver(destino), "archivo"
        elif nombre == "sed" and any(
            a.startswith("--in-place") or re.fullmatch(r"-[a-zA-Z]*i\S*", a) for a in args
        ):
            rutas = _posicionales(args, ("-e", "-f", "--expression", "--file"))
            yield from ((resolver(a), "archivo") for a in rutas)
        elif nombre == "touch":
            rutas = _posicionales(args, ("-d", "-t", "-r", "--date", "--reference"))
            yield from ((resolver(a), "archivo") for a in rutas)
        elif nombre == "truncate":
            rutas = _posicionales(args, ("-s", "-r", "--size", "--reference"))
            yield from ((resolver(a), "archivo") for a in rutas)
        elif nombre in ("rm", "unlink"):
            for a in _posicionales(args):
                yield from borrado_directo(a)
        elif nombre == "git":
            rutas, carpeta = _rutas_de_git(args, actual)
            yield from (borrado(r, carpeta) for r in rutas)
        elif powershell and nombre in _ESCRITURA_POWERSHELL:
            yield from ((resolver(r), "archivo") for r in _escritura_powershell(nombre, args))
        elif powershell and nombre in _BORRADO_POWERSHELL:
            for r in _escritura_powershell(nombre, args):
                yield from borrado_directo(r)


# --- Ticket en curso (data-model) -----------------------------------------------------


def _rama(base: Path) -> str:
    resultado = subprocess.run(
        ["git", "-C", str(base), "branch", "--show-current"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=5,
    )
    return resultado.stdout.strip()


def _ticket(base: Path, ruta: str) -> str | None:
    """Qué le falta al ticket en curso para escribir `ruta`, o None si tiene todo."""
    rama = _rama(base)
    m = re.match(r"^(\d{3})-", rama)
    if not m:
        return SIN_TICKET.format(ruta=ruta or ".", rama=rama or "(HEAD separado)")
    nnn = m.group(1)
    specs = base / "specs"
    carpetas = (
        sorted(p.name for p in specs.glob(f"{nnn}-*") if p.is_dir()) if specs.is_dir() else []
    )
    if not carpetas:
        return SIN_CARPETA.format(nnn=nnn, rama=rama)
    if len(carpetas) > 1:
        return VARIAS.format(nnn=nnn, lista=", ".join(carpetas))
    faltan = [d for d in DOCUMENTOS if not (specs / carpetas[0] / d).is_file()]
    if faltan:
        return FALTAN.format(lista=", ".join(faltan), carpeta=carpetas[0])
    return None


# --- Decisión -------------------------------------------------------------------------


def carpetas_por_subcomando(texto: str, powershell: bool, base: Path, cwd: Path) -> list[Path]:
    """Carpeta vigente al empezar cada subcomando de `texto`, tras los `cd` anteriores.

    Los índices coinciden con el `origen` que anota el extractor de `comun.py`.
    """
    actual, carpetas = cwd, []
    for sub in comun.dividir_comando(texto, powershell=powershell):
        carpetas.append(actual)
        programa = comun.quitar_envoltorios(sub)
        if programa and _nombre(programa[0]) in _CAMBIO_DE_CARPETA:
            actual = _nueva_carpeta(programa[1:], base, actual)
    return carpetas


def _protegidas_en_terminal(
    comando: str, powershell: bool, base: Path, cwd: Path
) -> list[str] | str:
    """Rutas de código protegido del comando, o el mensaje de anidamiento excesivo.

    Cada comando interior y cada texto de código heredan la carpeta vigente en el
    subcomando donde aparecen (T017c). Si el extractor no sabe de qué subcomando salen,
    se prueba con todas las carpetas de su padre.
    """
    extraccion = comun.extraer_texto_ejecutable(comando, powershell=powershell)
    if extraccion.anidamiento_excesivo:
        return ANIDAMIENTO

    # Para el texto 0 (el comando) y cada comando interior (1, 2, …): la tabla de
    # carpetas por subcomando de cada carpeta de inicio posible.
    tablas: list[list[list[Path]]] = []

    def heredadas(padre: int, origen: int) -> list[Path]:
        candidatas: list[Path] = []
        for tabla in tablas[padre + 1]:
            elegidas = [tabla[origen]] if 0 <= origen < len(tabla) else tabla
            candidatas += [c for c in elegidas if c not in candidatas]
        return candidatas or [cwd]

    rutas: list[str] = []
    textos = [(comando, powershell, -1, -1)]
    textos += [(c.texto, c.powershell, c.padre, c.origen) for c in extraccion.comandos]
    for indice, (texto, sin_escapes, padre, origen) in enumerate(textos):
        inicios = [cwd] if indice == 0 else heredadas(padre, origen)
        tablas.append([carpetas_por_subcomando(texto, sin_escapes, base, i) for i in inicios])
        for inicio in inicios:
            for ruta, tipo in destinos(texto, sin_escapes, base, inicio):
                # settings.local.json se bloquea al escribir, borrar o mover, en cualquier
                # rama (FR-025): no se versiona, así que ningún PR vería el cambio.
                privado = ruta_privada(ruta)
                if privado:
                    return privado
                if (
                    tipo in ("copia_recursiva", "movimiento", "copia_con_comodin")
                    and ruta == ".claude"
                ) or (tipo == "copia_oculta" and ruta == ""):
                    return COPIA_A_CLAUDE
                if tipo == "claude_entera":
                    return BORRAR_CLAUDE
                if (
                    es_protegido(ruta)
                    or (tipo == "copia" and _es_carpeta_protegida(ruta))
                    or (
                        tipo.startswith("borrado")
                        and contiene_protegido(ruta, tipo.endswith("carpeta"))
                    )
                ):
                    rutas.append(ruta)

    for codigo, (padre, origen) in zip(extraccion.codigos, extraccion.codigos_origen, strict=True):
        for carpeta in heredadas(padre, origen):
            # El código que se ejecuta dentro de una carpeta con código protegido cuenta,
            # salvo en la raíz: U4 no puede resolver rutas relativas como `app/b.py`.
            relativa = comun.normalizar_ruta(str(carpeta), base)
            if relativa and contiene_protegido(relativa):
                rutas.append(relativa)
            for nombrada in rutas_en_texto(codigo):
                ruta = comun.normalizar_ruta(nombrada, base, carpeta)
                privado = ruta_privada(ruta)
                if privado:
                    return privado
                if es_protegido(ruta):
                    rutas.append(ruta)
    return rutas


def motivo(entrada: dict) -> str | None:
    """Motivo del bloqueo, o None si la acción se permite."""
    herramienta = entrada.get("tool_name") or ""
    datos = entrada.get("tool_input") or {}
    base = comun.raiz(entrada)
    cwd = comun.cwd(entrada, base)

    if herramienta in ("Write", "Edit", "NotebookEdit"):
        clave = "notebook_path" if herramienta == "NotebookEdit" else "file_path"
        ruta = comun.normalizar_ruta(datos.get(clave) or "", base, cwd)
        privado = ruta_privada(ruta)
        if privado:
            return privado  # cualquier rama (FR-025 de #3 y FR-020 de #4)
        rutas = [ruta] if datos.get(clave) and es_protegido(ruta) else []
    elif herramienta in ("Bash", "PowerShell"):
        resultado = _protegidas_en_terminal(
            datos.get("command") or "", herramienta == "PowerShell", base, cwd
        )
        if isinstance(resultado, str):
            return resultado
        rutas = resultado
    else:
        return None

    return _ticket(base, rutas[0]) if rutas else None


def revisar(entrada: dict) -> None:
    motivo_ = motivo(entrada)
    if motivo_:
        comun.bloquear(GUARDA, motivo_)


if __name__ == "__main__":
    comun.ejecutar(GUARDA, revisar)
