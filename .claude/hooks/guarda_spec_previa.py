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

# --- Código protegido (data-model) ----------------------------------------------------

_ARCHIVOS_PROTEGIDOS = {".claude/settings.json", ".claude/settings.local.json", ".mcp.json"}
_CARPETAS_PROTEGIDAS = (".claude/hooks", "plugins", ".claude-plugin")


def _relativa(ruta: str) -> str | None:
    """La ruta en minúsculas y con `/`, o None si está fuera de la raíz (absoluta)."""
    texto = ruta.replace("\\", "/").casefold()
    if texto.startswith("/") or re.match(r"^[a-z]:/", texto):
        return None
    return "/".join(p for p in texto.split("/") if p not in ("", "."))


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
_ESCRITURA_POWERSHELL = {"set-content", "add-content", "out-file", "new-item", "ni", "tee-object"}
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
    """`(destino, es carpeta, fuentes)` de cp, mv, install, copy o Copy-Item."""
    destino, carpeta, posicionales = None, False, []
    i = 0
    while i < len(args):
        arg = args[i]
        if powershell and _parametro(arg, ("-destination",)):
            destino = args[i + 1] if i + 1 < len(args) else None
            i += 2
        elif powershell and _parametro(arg, _POWERSHELL_RUTA + _POWERSHELL_OTRO_VALOR):
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
    if destino is None and len(posicionales) >= 2:
        destino, posicionales = posicionales[-1], posicionales[:-1]
    return destino, carpeta, posicionales


def _escritura_powershell(nombre: str, args: list[str]) -> Iterator[str]:
    """Rutas de Set-Content, Add-Content, Out-File, New-Item y Tee-Object.

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


def destinos(texto: str, powershell: bool, cwd: Path) -> Iterator[tuple[str, bool]]:
    """`(ruta, es carpeta)` de cada destino de escritura reconocible del comando."""
    for sub in comun.dividir_comando(texto, powershell=powershell):
        for ruta in _redirecciones(sub):
            yield ruta, False
        programa = comun.quitar_envoltorios(sub)
        if not programa:
            continue
        nombre, args = _nombre(programa[0]), programa[1:]
        if nombre == "tee":
            yield from ((a, False) for a in args if not a.startswith("-"))
        elif nombre in ("cp", "mv", "install") or (powershell and nombre in _COPIA_POWERSHELL):
            destino, carpeta, fuentes = _copia(args, powershell)
            if destino is None:
                continue
            carpeta = carpeta or destino.endswith(("/", "\\"))
            carpeta = carpeta or os.path.isdir(os.path.join(cwd, destino))
            yield destino, carpeta
            if carpeta:
                for fuente in fuentes:
                    base = fuente.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
                    yield destino.rstrip("/\\") + "/" + base, False
        elif nombre == "sed" and any(
            a.startswith("--in-place") or re.fullmatch(r"-[a-zA-Z]*i\S*", a) for a in args
        ):
            omitir = {
                i + 1 for i, a in enumerate(args) if a in ("-e", "-f", "--expression", "--file")
            }
            yield from (
                (a, False) for i, a in enumerate(args) if i not in omitir and not a.startswith("-")
            )
        elif nombre == "touch":
            omitir = {
                i + 1
                for i, a in enumerate(args)
                if a in ("-d", "-t", "-r", "--date", "--reference")
            }
            yield from (
                (a, False) for i, a in enumerate(args) if i not in omitir and not a.startswith("-")
            )
        elif powershell and nombre in _ESCRITURA_POWERSHELL:
            yield from ((r, False) for r in _escritura_powershell(nombre, args))


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
        return SIN_TICKET.format(ruta=ruta, rama=rama or "(HEAD separado)")
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


def _protegidas_en_terminal(
    comando: str, powershell: bool, base: Path, cwd: Path
) -> list[str] | str:
    """Rutas de código protegido del comando, o el mensaje de anidamiento excesivo."""
    extraccion = comun.extraer_texto_ejecutable(comando, powershell=powershell)
    if extraccion.anidamiento_excesivo:
        return ANIDAMIENTO
    rutas = []
    textos = [(comando, powershell)] + [(c.texto, c.powershell) for c in extraccion.comandos]
    for texto, sin_escapes in textos:
        for destino, carpeta in destinos(texto, sin_escapes, cwd):
            ruta = comun.normalizar_ruta(destino, base, cwd)
            if es_protegido(ruta) or (carpeta and _es_carpeta_protegida(ruta)):
                rutas.append(ruta)
    for codigo in extraccion.codigos:
        for nombrada in rutas_en_texto(codigo):
            ruta = comun.normalizar_ruta(nombrada, base, cwd)
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
