"""Contexto de las skills de revisión: lo que se inyecta antes de crear el subagente (R2, R4, R6).

Imprime, en este orden: la marca `CONTEXTO DE REVISIÓN`, la rama, la base de fusión, las rutas
del ticket y de la constitución, la lista de archivos cambiados con estadísticas (los movidos,
en su ruta nueva y con la anterior) y, solo si toda la salida cabe en `UMBRAL_SALIDA`, el diff
completo; si no cabe, el diff de cada archivo movido con cambios que quepa.

Siempre sale con 0: un comando inyectado que falla aborta toda la invocación de la skill y
el revisor nunca vería nada. Lo que no se puede calcular se dice con
`CONTEXTO INCOMPLETO: <motivo>`. No recibe argumentos ni stdin (R2.2) y no usa la red: el
`fetch` lo hace `/abrir-pr` antes.

Contrato: specs/004-revision-independiente-auditoria/contracts/revisiones.md.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

import comun
import veredicto

# La misma raíz que veredicto.py: CLAUDE_PROJECT_DIR, la del repositorio git o el directorio actual.
raiz = veredicto.raiz

MARCA = "CONTEXTO DE REVISIÓN"
# La mitad del mayor tamaño que llegó completo a la inyección (Q4(a): 29 000 bytes en línea;
# con 30 000 ya llega solo una vista previa y una ruta). T031, R4.
UMBRAL_SALIDA = 14_500
CONSTITUCION = ".specify/memory/constitution.md"
DOCUMENTOS_DEL_TICKET = ("spec.md", "plan.md", "tasks.md")

_RAMA_DE_TICKET = re.compile(r"(\d{3})-[a-z0-9-]+")


def _bytes(texto: str) -> int:
    return len(texto.encode("utf-8"))


class Archivo(NamedTuple):
    """Un archivo del cambio; `anterior` y `similitud` solo si git detectó que se movió."""

    estado: str
    añadidas: int | None
    borradas: int | None
    ruta: str
    anterior: str | None = None
    similitud: int | None = None


def _archivos(raiz: Path, base: str) -> list[Archivo]:
    """Los archivos del cambio, con los movidos detectados (`-M`); cifras None en los binarios.

    Con `-z` las rutas llegan tal cual y separadas por NUL. Un movido trae dos rutas, la
    anterior y la nueva; en `--numstat` van tras un campo de ruta vacío.
    """
    _, numeros = veredicto.git(raiz, "diff", "-M", "-z", "--numstat", base, "HEAD")
    cifras: dict[str, tuple[int | None, int | None]] = {}
    campos = numeros.split("\0")
    i = 0
    while i < len(campos):
        partes = campos[i].split("\t")
        i += 1
        if len(partes) != 3:
            continue
        añadidas, borradas, ruta = partes
        if not ruta and i + 1 < len(campos):
            ruta = campos[i + 1]
            i += 2
        cifras[ruta] = (
            None if añadidas == "-" else int(añadidas),
            None if borradas == "-" else int(borradas),
        )
    _, estados = veredicto.git(raiz, "diff", "-M", "-z", "--name-status", base, "HEAD")
    campos = estados.split("\0")
    archivos = []
    i = 0
    while i + 1 < len(campos):
        estado = campos[i]
        if estado.startswith("R") and i + 2 < len(campos):
            anterior, ruta, similitud = campos[i + 1], campos[i + 2], int(estado[1:] or 0)
            i += 3
        else:
            anterior, ruta, similitud = None, campos[i + 1], None
            i += 2
        añadidas, borradas = cifras.get(ruta, (None, None))
        archivos.append(Archivo(estado[:1], añadidas, borradas, ruta, anterior, similitud))
    return archivos


def _es_referencia(ruta: str, carpeta: str | None) -> bool:
    return carpeta is not None and ruta.startswith(carpeta)


def _lista(archivos: list, carpeta: str | None) -> list[str]:
    filas = []
    for estado, añadidas, borradas, ruta, anterior, similitud in archivos:
        cifras = "binario" if añadidas is None else f"+{añadidas} -{borradas}"
        marcas = ""
        if estado == "D":
            marcas += " [eliminado]"
        if anterior is not None:
            marcas += f" [movido desde {anterior}, similitud {similitud} %]"
        if _es_referencia(ruta, carpeta):
            marcas += " [referencia]"
        filas.append(f"{estado}  {cifras}  {ruta}{marcas}")
    return filas


def _agrupada(archivos: list) -> list[str]:
    grupos: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for _, añadidas, borradas, ruta, *_ in archivos:
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


def _diffs_de_movidos(raiz: Path, base: str, archivos: list, salida: str, umbral: int) -> str:
    """`salida` con el diff de cada archivo movido con cambios, mientras quepa en `umbral`.

    Un diff que no cabe deja un aviso con su nombre, solo si el aviso cabe. Los que no caben ni
    así se cuentan en una sola línea final, la única que puede pasar del umbral.
    """
    sin_aviso = 0
    for archivo in archivos:
        if archivo.anterior is None or archivo.similitud == 100:
            continue
        titulo = f"Diff de {archivo.ruta} (movido desde {archivo.anterior})"
        _, diff = veredicto.git(
            raiz,
            "-c",
            "core.quotepath=false",
            "diff",
            "-M",
            base,
            "HEAD",
            "--",
            archivo.anterior,
            archivo.ruta,
        )
        bloque = f"{titulo}:\n{diff}\n"
        aviso = f"{titulo} omitido: no cabe en el umbral. Lee el archivo en su ruta nueva.\n"
        if _bytes(salida + bloque) <= umbral:
            salida += bloque
        elif _bytes(salida + aviso) <= umbral:
            salida += aviso
        else:
            sin_aviso += 1
    if sin_aviso:
        salida += (
            f"Diffs de archivos movidos omitidos sin aviso propio: {sin_aviso}. No caben en el "
            "umbral; lee en su ruta nueva los archivos marcados [movido desde …].\n"
        )
    return salida


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
        _, diff = veredicto.git(raiz, "-c", "core.quotepath=false", "diff", "-M", base, "HEAD")
        completo = f"{sin_diff}\nDiff completo:\n{diff}\n"
        if _bytes(completo) <= umbral:
            return completo
    aviso = (
        f"Diff omitido: la salida superaría el umbral de {umbral} bytes. Lee los archivos de "
        "la lista con Read y Grep."
    )
    return _diffs_de_movidos(raiz, base, archivos, f"{sin_diff}\n{aviso}\n", umbral)


def main() -> int:
    comun.flujos_utf8()
    try:
        print(construir(raiz()), end="")
    except Exception as error:  # noqa: BLE001 - siempre sale con 0 (R2)
        print(f"{MARCA}\nCONTEXTO INCOMPLETO: error inesperado ({type(error).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
