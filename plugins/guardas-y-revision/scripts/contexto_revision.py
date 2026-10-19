"""Contexto de la revisión: lo que la skill inyecta antes de crear el subagente revisor.

Imprime, en este orden: la marca `CONTEXTO DE REVISIÓN`, la rama, el commit, la base de fusión,
el ticket y la constitución si el repositorio usa Spec Kit, la lista de archivos cambiados con
estadísticas y, solo si toda la salida cabe en `UMBRAL_SALIDA`, el diff completo.

Siempre sale con 0: un comando inyectado que falla aborta la invocación de la skill y el
revisor no vería nada. Lo que no se puede calcular se dice con `CONTEXTO INCOMPLETO: <motivo>`.
No recibe argumentos ni stdin, no usa la red y solo usa la biblioteca estándar.
"""

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

MARCA = "CONTEXTO DE REVISIÓN"
UMBRAL_SALIDA = 14_500
CONSTITUCION = ".specify/memory/constitution.md"
DOCUMENTOS_DEL_TICKET = ("spec.md", "plan.md", "tasks.md")
BASES = ("origin/main", "origin/master", "main", "master")

_RAMA_DE_TICKET = re.compile(r"(\d{3})-[a-z0-9-]+")


def git(raiz: Path, *args: str) -> tuple[int, str]:
    """`(código, stdout sin espacios sobrantes)` de git en `raiz`."""
    try:
        resultado = subprocess.run(
            ["git", *args],
            cwd=raiz,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return 1, ""
    return resultado.returncode, resultado.stdout.strip()


def raiz() -> Path:
    """La raíz del repositorio git del directorio actual, o el directorio actual."""
    actual = Path.cwd()
    codigo, salida = git(actual, "rev-parse", "--show-toplevel")
    return Path(salida) if codigo == 0 and salida else actual


def _bytes(texto: str) -> int:
    return len(texto.encode("utf-8"))


def base_de_fusion(raiz: Path) -> tuple[str, str] | None:
    """`(sha, referencia)` de la base de fusión con la rama principal, o None."""
    candidatas = []
    codigo, cabeza = git(raiz, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if codigo == 0 and cabeza.startswith("refs/remotes/"):
        candidatas.append(cabeza.removeprefix("refs/remotes/"))
    candidatas += [c for c in BASES if c not in candidatas]
    for referencia in candidatas:
        if git(raiz, "rev-parse", "--verify", "--quiet", f"{referencia}^{{commit}}")[0] != 0:
            continue
        codigo, sha = git(raiz, "merge-base", "HEAD", referencia)
        if codigo == 0 and sha:
            return sha, referencia
    return None


def _archivos(raiz: Path, base: str) -> list[tuple[str, int | None, int | None, str]]:
    """`(estado, añadidas, borradas, ruta)` por archivo; None en los binarios."""
    _, estados = git(
        raiz, "-c", "core.quotepath=false", "diff", "--no-renames", "--name-status", base, "HEAD"
    )
    _, numeros = git(
        raiz, "-c", "core.quotepath=false", "diff", "--no-renames", "--numstat", base, "HEAD"
    )
    cifras: dict[str, tuple[int | None, int | None]] = {}
    for fila in numeros.splitlines():
        partes = fila.split("\t", 2)
        if len(partes) == 3:
            añadidas, borradas, ruta = partes
            cifras[ruta] = (
                None if añadidas == "-" else int(añadidas),
                None if borradas == "-" else int(borradas),
            )
    archivos = []
    for fila in estados.splitlines():
        partes = fila.split("\t", 1)
        if len(partes) == 2:
            estado, ruta = partes
            añadidas, borradas = cifras.get(ruta, (None, None))
            archivos.append((estado[:1], añadidas, borradas, ruta))
    return archivos


def _lista(archivos: list, carpeta: str | None) -> list[str]:
    filas = []
    for estado, añadidas, borradas, ruta in archivos:
        cifras = "binario" if añadidas is None else f"+{añadidas} -{borradas}"
        marcas = ""
        if estado == "D":
            marcas += " [eliminado]"
        if carpeta is not None and ruta.startswith(carpeta):
            marcas += " [referencia]"
        filas.append(f"{estado}  {cifras}  {ruta}{marcas}")
    return filas


def _agrupada(archivos: list) -> list[str]:
    grupos: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for _, añadidas, borradas, ruta in archivos:
        directorio = ruta.rsplit("/", 1)[0] + "/" if "/" in ruta else "./"
        grupo = grupos[directorio]
        grupo[0] += 1
        grupo[1] += añadidas or 0
        grupo[2] += borradas or 0
    return [
        f"{directorio}: {n} archivos +{a} -{b}" for directorio, (n, a, b) in sorted(grupos.items())
    ]


def _ticket(raiz: Path, rama: str) -> tuple[str | None, str | None, str | None]:
    """`(carpeta, línea, motivo de incompleto)` del ticket según la convención de Spec Kit."""
    if not (raiz / "specs").is_dir():
        return None, "Ticket: no aplica (el repositorio no usa una carpeta specs/)", None
    coincidencia = _RAMA_DE_TICKET.fullmatch(rama)
    if coincidencia is None:
        return None, None, f"la rama «{rama or '(ninguna)'}» no sigue el patrón NNN-nombre"
    numero = coincidencia.group(1)
    carpetas = sorted(p for p in (raiz / "specs").glob(f"{numero}-*") if p.is_dir())
    if len(carpetas) != 1:
        return None, None, f"no hay exactamente una carpeta specs/{numero}-* del ticket"
    carpeta = f"specs/{carpetas[0].name}/"
    return carpeta, f"Ticket: {carpeta}", None


def construir(raiz: Path, umbral: int = UMBRAL_SALIDA) -> str:
    """El contexto de revisión completo, con la marca en la primera línea."""
    raiz = Path(raiz)
    salida = [MARCA]
    incompleto: list[str] = []

    if git(raiz, "rev-parse", "--git-dir")[0] != 0:
        salida.append("CONTEXTO INCOMPLETO: la carpeta no es un repositorio git")
        return "\n".join(salida) + "\n"

    _, rama = git(raiz, "branch", "--show-current")
    salida.append(f"Rama: {rama or '(ninguna)'}")
    codigo_head, sha = git(raiz, "rev-parse", "HEAD")
    if codigo_head == 0 and sha:
        salida.append(f"Commit: {sha}")
    else:
        incompleto.append("no se pudo leer el commit actual (HEAD)")
    base = base_de_fusion(raiz)
    if base is None:
        incompleto.append(
            "no hay base de fusión con origin/HEAD, origin/main, origin/master, main ni master"
        )
    else:
        salida.append(f"Base: {base[0][:12]} (git merge-base HEAD {base[1]})")

    carpeta, linea, motivo = _ticket(raiz, rama)
    if motivo:
        incompleto.append(motivo)
    elif linea:
        salida.append(linea)
        if carpeta:
            salida.extend(f"  - {carpeta}{nombre}" for nombre in DOCUMENTOS_DEL_TICKET)
    if (raiz / CONSTITUCION).is_file():
        salida.append(f"Constitución: {CONSTITUCION}")
    else:
        salida.append("Constitución: no aplica")
    salida.extend(f"CONTEXTO INCOMPLETO: {razon}" for razon in incompleto)
    if base is None:
        return "\n".join(salida) + "\n"

    archivos = _archivos(raiz, base[0])
    lista = [f"Archivos cambiados ({len(archivos)}):", *_lista(archivos, carpeta)]
    cabecera = "\n".join(salida)
    agrupada = _bytes(cabecera + "\n" + "\n".join(lista)) > umbral
    if agrupada:
        lista = [
            f"Archivos cambiados ({len(archivos)}), lista agrupada por directorio "
            "(la lista completa no cabe en el umbral):",
            *_agrupada(archivos),
        ]
    sin_diff = cabecera + "\n" + "\n".join(lista)
    if not agrupada:
        _, diff = git(raiz, "-c", "core.quotepath=false", "diff", "--no-renames", base[0], "HEAD")
        completo = f"{sin_diff}\nDiff completo:\n{diff}\n"
        if _bytes(completo) <= umbral:
            return completo
    aviso = (
        f"Diff omitido: la salida superaría el umbral de {umbral} bytes. Lee los archivos de "
        "la lista con Read y Grep."
    )
    return f"{sin_diff}\n{aviso}\n"


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(flujo, "reconfigure", None)
        if reconfigurar is not None:
            reconfigurar(encoding="utf-8")
    try:
        print(construir(raiz()), end="")
    except Exception as error:  # noqa: BLE001 - siempre sale con 0
        print(f"{MARCA}\nCONTEXTO INCOMPLETO: error inesperado ({type(error).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
