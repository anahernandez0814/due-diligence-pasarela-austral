"""Veredicto de la revisión previa al PR: consolidación, registro y lectura (R7, R8).

`/abrir-pr` ejecuta las dos revisiones, pasa sus líneas `RESUMEN` a la CLI de este módulo
(`registrar`) y la guarda de PR lee el resultado con `leer`. Un archivo por commit en
`.claude/veredictos/<sha>.json`, ignorado por git. Solo este módulo escribe el directorio:
ninguna herramienta de Claude Code puede hacerlo (FR-020).

Contrato: specs/004-revision-independiente-auditoria/contracts/veredicto-y-guarda.md.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import comun

APROBADO = "aprobado"
CON_BLOQUEANTES = "con bloqueantes"
DIRECTORIO = Path(".claude") / "veredictos"

_RESUMEN = re.compile(
    r"RESUMEN: bloqueantes=(\d+) sugerencias=(\d+) cobertura=(completa|incompleta)"
)
_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


# --- Línea RESUMEN y consolidación ---------------------------------------------------


def parsear_resumen(texto: str) -> dict | None:
    """Los datos de la línea `RESUMEN` de un reporte, o None si no es utilizable.

    Tiene que haber exactamente una línea que empiece por `RESUMEN:` y tiene que cumplir el
    formato completo; una ausente, repetida o con otro formato no vale (R7).
    """
    lineas = [x.strip() for x in texto.splitlines() if x.strip().startswith("RESUMEN:")]
    if len(lineas) != 1:
        return None
    coincidencia = _RESUMEN.fullmatch(lineas[0])
    if coincidencia is None:
        return None
    return {
        "bloqueantes": int(coincidencia.group(1)),
        "sugerencias": int(coincidencia.group(2)),
        "cobertura": coincidencia.group(3),
    }


def _motivo_del_reporte(nombre: str, resumen: dict | None) -> str | None:
    if resumen is None:
        return f"reporte de {nombre} no utilizable"
    if resumen["bloqueantes"]:
        return f"{resumen['bloqueantes']} bloqueante(s) en la revisión de {nombre}"
    if resumen["cobertura"] != "completa":
        return f"cobertura incompleta en la revisión de {nombre}"
    return None


def consolidar(
    codigo: dict | None, auditoria: dict | None, cambios: bool | None
) -> tuple[str, str | None]:
    """`(veredicto, motivo)`. `aprobado` solo si todo está limpio y hay cambios.

    Que haya cambios frente a la base lo comprueba git, no el reporte, y no lo revierte
    ningún reporte (FR-008).
    """
    if cambios is None:
        return CON_BLOQUEANTES, "sin base de comparación"
    if not cambios:
        return CON_BLOQUEANTES, "sin cambios"
    for nombre, resumen in (("código", codigo), ("auditoría", auditoria)):
        motivo = _motivo_del_reporte(nombre, resumen)
        if motivo:
            return CON_BLOQUEANTES, motivo
    return APROBADO, None


# --- git -----------------------------------------------------------------------------


def git(raiz: Path, *args: str) -> tuple[int, str]:
    resultado = subprocess.run(
        ["git", *args],
        cwd=raiz,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return resultado.returncode, resultado.stdout.strip()


def base_de_fusion(raiz: Path) -> str | None:
    """`git merge-base HEAD origin/main`, o None si no se puede calcular (R6)."""
    codigo, salida = git(raiz, "merge-base", "HEAD", "refs/remotes/origin/main")
    return salida if codigo == 0 and salida else None


def hay_cambios(raiz: Path) -> bool | None:
    """Si HEAD difiere de la base de fusión; None si no hay base (R7)."""
    base = base_de_fusion(raiz)
    if base is None:
        return None
    codigo, _ = git(raiz, "diff", "--quiet", base, "HEAD")
    if codigo == 0:
        return False
    if codigo == 1:
        return True
    return None


# --- Archivos ------------------------------------------------------------------------


def ruta_veredicto(raiz: Path, sha: str) -> Path:
    """`<raíz>/.claude/veredictos/<sha>.json`; el sha tiene que ser hexadecimal."""
    if not _SHA.fullmatch(sha):
        raise ValueError("el identificador del commit no es un sha hexadecimal completo")
    return Path(raiz) / DIRECTORIO / f"{sha}.json"


def leer(raiz: Path, sha: str) -> dict | None:
    """El veredicto del commit, o None si no existe, es ilegible o tiene otro formato."""
    try:
        datos = json.loads(ruta_veredicto(raiz, sha).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict):
        return None
    if datos.get("commit") != sha:
        return None
    if datos.get("veredicto") not in (APROBADO, CON_BLOQUEANTES):
        return None
    return datos


def registrar(raiz: Path, codigo: str, auditoria: str) -> tuple[str, str | None]:
    """Consolida los dos reportes, escribe el veredicto del commit actual y lo devuelve."""
    raiz = Path(raiz)
    codigo_git, sha = git(raiz, "rev-parse", "HEAD")
    if codigo_git != 0:
        raise RuntimeError("no se pudo leer el commit actual: ¿es un repositorio git?")
    _, rama = git(raiz, "branch", "--show-current")
    resumen_codigo = parsear_resumen(codigo)
    resumen_auditoria = parsear_resumen(auditoria)
    veredicto, motivo = consolidar(resumen_codigo, resumen_auditoria, hay_cambios(raiz))
    datos = {
        "commit": sha,
        "rama": rama,
        "veredicto": veredicto,
        "fecha": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "codigo": resumen_codigo,
        "auditoria": resumen_auditoria,
    }
    destino = ruta_veredicto(raiz, sha)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return veredicto, motivo


# --- Línea de comandos ---------------------------------------------------------------


def _raiz() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="veredicto.py", description=__doc__.splitlines()[0])
    subcomandos = parser.add_subparsers(dest="orden", required=True)
    registro = subcomandos.add_parser("registrar", help="registra el veredicto del commit actual")
    registro.add_argument("--codigo", required=True, help="reporte o línea RESUMEN de la revisión")
    registro.add_argument(
        "--auditoria", required=True, help="reporte o línea RESUMEN de la auditoría"
    )
    argumentos = parser.parse_args(argv)
    try:
        veredicto, motivo = registrar(_raiz(), argumentos.codigo, argumentos.auditoria)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"No se pudo registrar el veredicto: {error}", file=sys.stderr)
        return 2
    print(f"veredicto: {veredicto}" + (f" ({motivo})" if motivo else ""))
    return 0 if veredicto == APROBADO else 1


if __name__ == "__main__":
    comun.flujos_utf8()
    sys.exit(main(sys.argv[1:]))
