"""Repositorios git temporales para las pruebas del ticket #4.

Los usan `test_veredicto.py`, `test_preparar_revision.py` y `test_guarda_pr.py`. No es un
módulo de pruebas: pytest solo recoge `test_*.py`.
"""

import os
import subprocess
from pathlib import Path

_IDENTIDAD = {
    "GIT_AUTHOR_NAME": "Prueba",
    "GIT_AUTHOR_EMAIL": "prueba@example.invalid",
    "GIT_COMMITTER_NAME": "Prueba",
    "GIT_COMMITTER_EMAIL": "prueba@example.invalid",
}


def git(cwd: Path, *args: str, comprobar: bool = True) -> str:
    """Ejecuta git en `cwd` y devuelve stdout sin espacios sobrantes."""
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    entorno.update(_IDENTIDAD)
    resultado = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        check=False,
    )
    if comprobar and resultado.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} falló: {resultado.stderr.strip()}")
    return resultado.stdout.strip()


def escribir(repo: Path, ruta: str, contenido: str) -> None:
    destino = repo / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8", newline="\n")


def confirmar(repo: Path, mensaje: str = "cambio") -> str:
    """Añade todo, hace un commit y devuelve su sha completo."""
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", mensaje)
    return git(repo, "rev-parse", "HEAD")


def crear_repo(tmp_path: Path, rama: str = "004-demo") -> Path:
    """Repositorio de trabajo con un `origin` local, `main` publicada y la rama del ticket.

    La rama queda creada y activa, sin commits propios. `origin/main` existe.
    """
    origen = tmp_path / "origen.git"
    trabajo = tmp_path / "trabajo"
    origen.mkdir()
    git(origen, "init", "-q", "--bare", "-b", "main")
    trabajo.mkdir()
    git(trabajo, "init", "-q", "-b", "main")
    git(trabajo, "remote", "add", "origin", str(origen))
    escribir(trabajo, "README.md", "Repositorio de prueba\n")
    confirmar(trabajo, "inicio")
    git(trabajo, "push", "-q", "-u", "origin", "main")
    git(trabajo, "switch", "-q", "-c", rama)
    return trabajo
