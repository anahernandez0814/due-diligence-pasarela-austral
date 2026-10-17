"""Guarda de creación de PR: PreToolUse (FR-012 a FR-014, FR-016; R9, R10).

Bloquea crear un pull request si no hay un veredicto aprobado del commit actual, publicado
en la rama, por cualquiera de estas vías:

- la herramienta `mcp__github__create_pull_request` del MCP de GitHub;
- `gh pr create` por terminal (Bash o PowerShell), también tras `bash -c`, `eval`, heredocs,
  `xargs`, `sudo`, `env -S` y demás envoltorios que reconoce el extractor de #3;
- `gh api` con POST al recurso de pull requests y la mutación `createPullRequest` de
  `gh api graphql`.

Se permite todo lo demás (`gh pr view`, `gh pr list`, `gh api` con GET…). La comprobación,
por orden: la rama del PR es la actual, `origin/<rama>` existe y es `HEAD`, existe el
veredicto del commit y es `aprobado`. Compara con la referencia local `origin/<rama>`, no
con la red: `git ls-remote` tarda más de 1 s (R9). Falla cerrada, como las demás guardas.

Contrato: specs/004-revision-independiente-auditoria/contracts/veredicto-y-guarda.md.
"""

import os
import re
from pathlib import Path

import comun
import veredicto

GUARDA = "guarda_pr"
HERRAMIENTA_MCP = "mcp__github__create_pull_request"

FALTA = "Falta la revisión de este commit. Ejecuta /abrir-pr."
BLOQUEANTES = (
    "La revisión de este commit tiene bloqueantes. Corrígelos, haz un commit nuevo y "
    "ejecuta /abrir-pr."
)
NO_PUBLICADO = "El commit no está publicado en origin/{rama}. Sube la rama con /abrir-pr."
NO_COINCIDE = "La rama remota origin/{rama} no coincide con el commit revisado. Ejecuta /abrir-pr."
OTRA_RAMA = (
    "La rama del PR ('{rama}') no es la rama actual ('{actual}'). Cambia a la rama del PR "
    "o usa /abrir-pr."
)
OTRO_REPOSITORIO = (
    "El PR sale de otro repositorio ('{prefijo}'): la revisión solo cubre la rama del propio "
    "repositorio. Usa /abrir-pr."
)
SIN_HEAD = "No se pudo leer la rama del PR (head). Usa /abrir-pr."
SIN_GIT = "No se pudo leer el estado de git de la rama. Ejecuta /abrir-pr desde el repositorio."
ANIDAMIENTO = (
    "Comando bloqueado por precaución: tiene más de 3 niveles de shells anidados y puede "
    "crear un PR. Simplifícalo."
)

_TIENE_GH = re.compile(r"\bgh\b", re.IGNORECASE)
_PULLS = re.compile(r"/?repos/[^/\s]+/[^/\s]+/pulls/?(?:\?.*)?", re.IGNORECASE)
_PROPIETARIO_DE_ORIGIN = re.compile(r"github\.com[:/]([^/\s]+)/", re.IGNORECASE)

# Opciones globales con valor que pueden ir delante del subcomando.
_GLOBALES_CON_VALOR = {"-R", "--repo", "--hostname"}
# Opciones de `gh api` que llevan un valor aparte.
_API_CON_VALOR = {"-H", "--header", "-q", "--jq", "-t", "--template", "--hostname", "--cache"}
_API_CAMPOS = {"-f", "-F", "--field", "--raw-field"}


def _nombre(palabra: str) -> str:
    nombre = palabra.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return nombre.removesuffix(".exe")


# --- Qué comandos de gh crean un PR ---------------------------------------------------


def _posicionales_iniciales(args: list[str]) -> tuple[list[str], int]:
    """Las dos primeras palabras que no son opciones (`pr create`, `api …`) y dónde acaban."""
    palabras: list[str] = []
    i = 0
    while i < len(args) and len(palabras) < 2:
        actual = args[i]
        if actual in _GLOBALES_CON_VALOR:
            i += 2
            continue
        if not actual.startswith("-"):
            palabras.append(actual.lower())
        i += 1
    return palabras, i


def _head_de_pr_create(args: list[str]) -> str | None:
    """El valor de `--head` o `-H`; el último si se repite; None si no se dice."""
    head = None
    i = 0
    while i < len(args):
        actual = args[i]
        if actual in ("--head", "-H"):
            head = args[i + 1] if i + 1 < len(args) else None
            i += 2
            continue
        if actual.startswith("--head="):
            head = actual.split("=", 1)[1]
        elif actual.startswith("-H") and not actual.startswith("--") and len(actual) > 2:
            head = actual[2:].lstrip("=")
        i += 1
    return head


def _api(args: list[str]) -> tuple[str | None, str | None, bool, dict[str, str]]:
    """`(endpoint, método, lleva_cuerpo, campos)` de los argumentos de `gh api`."""
    endpoint = metodo = None
    con_cuerpo = False
    campos: dict[str, str] = {}
    i = 0
    while i < len(args):
        actual = args[i]
        valor = args[i + 1] if i + 1 < len(args) else None
        if actual in ("-X", "--method"):
            metodo, i = valor, i + 2
        elif actual.startswith("--method="):
            metodo, i = actual.split("=", 1)[1], i + 1
        elif actual.startswith("-X") and not actual.startswith("--") and len(actual) > 2:
            metodo, i = actual[2:], i + 1
        elif actual in _API_CAMPOS:
            con_cuerpo = True
            nombre, _, dato = (valor or "").partition("=")
            campos[nombre] = dato
            i += 2
        elif actual.startswith(("--field=", "--raw-field=")):
            con_cuerpo = True
            nombre, _, dato = actual.split("=", 1)[1].partition("=")
            campos[nombre] = dato
            i += 1
        elif actual.startswith(("-f", "-F")) and not actual.startswith("--") and len(actual) > 2:
            con_cuerpo = True
            nombre, _, dato = actual[2:].partition("=")
            campos[nombre] = dato
            i += 1
        elif actual == "--input":
            con_cuerpo = True
            i += 2
        elif actual.startswith("--input="):
            con_cuerpo = True
            i += 1
        elif actual in _API_CON_VALOR:
            i += 2
        elif actual.startswith("-"):
            i += 1
        else:
            endpoint = endpoint or actual
            i += 1
    return endpoint, metodo, con_cuerpo, campos


def creacion_de_pr(args: list[str]) -> tuple[bool, str | None]:
    """`(crea un PR, head)` para los argumentos de `gh`. `head` es None si no se indica."""
    palabras, fin = _posicionales_iniciales(args)
    if palabras == ["pr", "create"]:
        return True, _head_de_pr_create(args[fin:])
    if palabras[:1] != ["api"]:
        return False, None
    endpoint, metodo, con_cuerpo, campos = _api(args[args.index("api") + 1 :])
    if endpoint is None:
        return False, None
    if endpoint.lower() == "graphql":
        crea = any("createpullrequest" in x.lower() for x in args)
        return crea, None
    publica = (metodo or "").upper() == "POST" or (metodo is None and con_cuerpo)
    if _PULLS.fullmatch(endpoint) and publica:
        return True, campos.get("head") or None
    return False, None


def creaciones_por_terminal(comando: str, powershell: bool) -> list[str | None] | str:
    """El `head` de cada creación de PR del comando (None: no se indica), o el mensaje de
    anidamiento excesivo. Mira el comando, los comandos interiores y los lanzadores."""
    extraccion = comun.extraer_texto_ejecutable(comando, powershell=powershell)
    if extraccion.anidamiento_excesivo:
        return ANIDAMIENTO
    textos = [(comando, powershell)] + [(c.texto, c.powershell) for c in extraccion.comandos]
    creaciones: list[str | None] = []
    for texto, sin_escapes in textos:
        subcomandos = comun.con_lanzados_de_find(
            comun.dividir_comando(texto, powershell=sin_escapes)
        )
        for sub in subcomandos:
            programa = comun.quitar_envoltorios(sub)
            if programa and _nombre(programa[0]) == "gh":
                crea, head = creacion_de_pr(programa[1:])
                if crea:
                    creaciones.append(head)
    return creaciones


# --- Comprobación ---------------------------------------------------------------------


def _raiz_del_repositorio(entrada: dict) -> Path:
    """La raíz donde `veredicto.py` escribe: CLAUDE_PROJECT_DIR o la del repositorio git."""
    base = comun.raiz(entrada)
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return base
    codigo, superior = veredicto.git(base, "rev-parse", "--show-toplevel")
    return Path(superior) if codigo == 0 and superior else base


def _propietario_de_origin(raiz: Path) -> str | None:
    codigo, url = veredicto.git(raiz, "remote", "get-url", "origin")
    coincidencia = _PROPIETARIO_DE_ORIGIN.search(url) if codigo == 0 else None
    return coincidencia.group(1) if coincidencia else None


def comprobar(raiz: Path, head: str | None, propietario: str | None) -> str | None:
    """El motivo del bloqueo, o None si hay un veredicto aprobado del commit publicado."""
    codigo, actual = veredicto.git(raiz, "branch", "--show-current")
    if codigo != 0 or not actual:
        return SIN_GIT
    rama = actual if head is None else head
    if ":" in rama:
        prefijo, rama = rama.split(":", 1)
        if not propietario or prefijo.casefold() != propietario.casefold():
            return OTRO_REPOSITORIO.format(prefijo=prefijo)
    if not rama:
        return SIN_HEAD
    if rama != actual:
        return OTRA_RAMA.format(rama=rama, actual=actual)
    codigo, sha = veredicto.git(raiz, "rev-parse", "HEAD")
    if codigo != 0 or not sha:
        return SIN_GIT
    codigo, remoto = veredicto.git(
        raiz, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{rama}"
    )
    if codigo != 0 or not remoto:
        return NO_PUBLICADO.format(rama=rama)
    if remoto != sha:
        return NO_COINCIDE.format(rama=rama)
    datos = veredicto.leer(raiz, sha)
    if datos is None:
        return FALTA
    if datos["veredicto"] != veredicto.APROBADO:
        return BLOQUEANTES
    return None


def motivo(entrada: dict) -> str | None:
    """Motivo del bloqueo, o None si la acción se permite."""
    herramienta = entrada.get("tool_name") or ""
    datos = entrada.get("tool_input")

    if herramienta == HERRAMIENTA_MCP:
        head = datos.get("head") if isinstance(datos, dict) else None
        if not isinstance(head, str) or not head:
            return SIN_HEAD
        propietario = datos.get("owner")
        raiz = _raiz_del_repositorio(entrada)
        return comprobar(raiz, head, propietario if isinstance(propietario, str) else None)

    if herramienta in ("Bash", "PowerShell"):
        comando = (datos or {}).get("command") if isinstance(datos, dict) else None
        if comando is None:
            return None
        if not isinstance(comando, str):
            raise TypeError("el comando no es texto")
        if not _TIENE_GH.search(comando):
            return None
        creaciones = creaciones_por_terminal(comando, herramienta == "PowerShell")
        if isinstance(creaciones, str):
            return creaciones
        if not creaciones:
            return None
        raiz = _raiz_del_repositorio(entrada)
        propietario = _propietario_de_origin(raiz)
        for head in creaciones:
            bloqueo = comprobar(raiz, head, propietario)
            if bloqueo:
                return bloqueo
    return None


def revisar(entrada: dict) -> None:
    motivo_ = motivo(entrada)
    if motivo_:
        comun.bloquear(GUARDA, motivo_)


if __name__ == "__main__":
    comun.ejecutar(GUARDA, revisar)
