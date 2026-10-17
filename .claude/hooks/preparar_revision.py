"""Contexto de las skills de revisión: lo que se inyecta antes de crear el subagente (R2, R4, R6).

Imprime, en este orden: la marca `CONTEXTO DE REVISIÓN`, la rama, la base de fusión, las rutas
del ticket y de la constitución, la lista de archivos cambiados con estadísticas y, solo si
toda la salida cabe en `UMBRAL_SALIDA`, el diff completo.

Siempre sale con 0: un comando inyectado que falla aborta toda la invocación de la skill y
el revisor nunca vería nada. Lo que no se puede calcular se dice con
`CONTEXTO INCOMPLETO: <motivo>`. No recibe argumentos ni stdin (R2.2) y no usa la red: el
`fetch` lo hace `/abrir-pr` antes.

Contrato: specs/004-revision-independiente-auditoria/contracts/revisiones.md.
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import comun
import veredicto

MARCA = "CONTEXTO DE REVISIÓN"
# Provisional: la fija T031 en la mitad del techo medido en Q4 (R4).
UMBRAL_SALIDA = 30_000
CONSTITUCION = ".specify/memory/constitution.md"
DOCUMENTOS_DEL_TICKET = ("spec.md", "plan.md", "tasks.md")

_RAMA_DE_TICKET = re.compile(r"(\d{3})-[a-z0-9-]+")


def _bytes(texto: str) -> int:
    return len(texto.encode("utf-8"))


def _archivos(raiz: Path, base: str) -> list[tuple[str, int | None, int | None, str]]:
    """`(estado, añadidas, borradas, ruta)` por archivo; None en los binarios."""
    _, estados = veredicto.git(
        raiz, "-c", "core.quotepath=false", "diff", "--no-renames", "--name-status", base, "HEAD"
    )
    _, numeros = veredicto.git(
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


def _es_referencia(ruta: str, carpeta: str | None) -> bool:
    return carpeta is not None and ruta.startswith(carpeta)


def _lista(archivos: list, carpeta: str | None) -> list[str]:
    filas = []
    for estado, añadidas, borradas, ruta in archivos:
        cifras = "binario" if añadidas is None else f"+{añadidas} -{borradas}"
        marcas = ""
        if estado == "D":
            marcas += " [eliminado]"
        if _es_referencia(ruta, carpeta):
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


def _carpeta_del_ticket(raiz: Path, rama: str) -> tuple[str | None, str | None]:
    """`(carpeta, motivo)`: `specs/NNN-nombre/` de la rama, o el motivo de no tenerla."""
    coincidencia = _RAMA_DE_TICKET.fullmatch(rama)
    if coincidencia is None:
        return None, f"la rama «{rama or '(ninguna)'}» no sigue el patrón NNN-nombre"
    carpetas = sorted(p for p in (raiz / "specs").glob(f"{coincidencia.group(1)}-*") if p.is_dir())
    if len(carpetas) != 1:
        return None, f"no hay exactamente una carpeta specs/{coincidencia.group(1)}-* del ticket"
    return f"specs/{carpetas[0].name}/", None


def construir(raiz: Path, umbral: int = UMBRAL_SALIDA) -> str:
    """El contexto de revisión completo, con la marca en la primera línea."""
    raiz = Path(raiz)
    salida = [MARCA]
    incompleto: list[str] = []

    codigo, _ = veredicto.git(raiz, "rev-parse", "--git-dir")
    if codigo != 0:
        salida.append("CONTEXTO INCOMPLETO: la carpeta no es un repositorio git")
        return "\n".join(salida) + "\n"

    _, rama = veredicto.git(raiz, "branch", "--show-current")
    salida.append(f"Rama: {rama or '(ninguna)'}")
    codigo_head, sha = veredicto.git(raiz, "rev-parse", "HEAD")
    if codigo_head == 0 and sha:
        salida.append(f"Commit: {sha}")
    else:
        incompleto.append("no se pudo leer el commit actual (HEAD)")
    base = veredicto.base_de_fusion(raiz)
    if base is None:
        incompleto.append(
            "no hay base de fusión: falta origin/main (¿se hizo git fetch origin main?)"
        )
    else:
        salida.append(f"Base: {base[:12]} (git merge-base HEAD origin/main)")

    carpeta, motivo = _carpeta_del_ticket(raiz, rama)
    if carpeta is None:
        incompleto.append(motivo or "sin carpeta de specs del ticket")
    else:
        salida.append(f"Ticket: {carpeta}")
        salida.extend(f"  - {carpeta}{nombre}" for nombre in DOCUMENTOS_DEL_TICKET)
    salida.append(f"Constitución: {CONSTITUCION}")
    salida.extend(f"CONTEXTO INCOMPLETO: {razon}" for razon in incompleto)
    if base is None:
        return "\n".join(salida) + "\n"

    archivos = _archivos(raiz, base)
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
        _, diff = veredicto.git(
            raiz, "-c", "core.quotepath=false", "diff", "--no-renames", base, "HEAD"
        )
        completo = f"{sin_diff}\nDiff completo:\n{diff}\n"
        if _bytes(completo) <= umbral:
            return completo
    aviso = (
        f"Diff omitido: la salida superaría el umbral de {umbral} bytes. Lee los archivos de "
        "la lista con Read y Grep."
    )
    return f"{sin_diff}\n{aviso}\n"


def main() -> int:
    comun.flujos_utf8()
    raiz = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    try:
        print(construir(raiz), end="")
    except Exception as error:  # noqa: BLE001 - siempre sale con 0 (R2)
        print(f"{MARCA}\nCONTEXTO INCOMPLETO: error inesperado ({type(error).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
