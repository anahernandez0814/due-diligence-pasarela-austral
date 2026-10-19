"""Pruebas de contexto_revision.py: el contexto que la skill inyecta antes del revisor."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import contexto_revision
import pytest

SCRIPT = Path(__file__).with_name("contexto_revision.py")
MARCA = "CONTEXTO DE REVISIÓN"
_IDENTIDAD = {
    "GIT_AUTHOR_NAME": "Prueba",
    "GIT_AUTHOR_EMAIL": "prueba@example.invalid",
    "GIT_COMMITTER_NAME": "Prueba",
    "GIT_COMMITTER_EMAIL": "prueba@example.invalid",
}


def git(cwd: Path, *args: str) -> str:
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    entorno.update(_IDENTIDAD)
    resultado = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        check=True,
    )
    return resultado.stdout.strip()


def escribir(repo: Path, ruta: str, contenido: str) -> None:
    destino = repo / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8", newline="\n")


def confirmar(repo: Path, mensaje: str = "cambio") -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", mensaje)


def repositorio(tmp_path: Path, rama: str = "cambio", remoto: bool = False) -> Path:
    """`main` con un commit inicial y la rama `rama` con un cambio en `app/a.py`."""
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    git(trabajo, "init", "-q", "-b", "main")
    escribir(trabajo, "README.md", "Repositorio de prueba\n")
    confirmar(trabajo, "inicio")
    if remoto:
        origen = tmp_path / "origen.git"
        origen.mkdir()
        git(origen, "init", "-q", "--bare", "-b", "main")
        git(trabajo, "remote", "add", "origin", str(origen))
        git(trabajo, "push", "-q", "-u", "origin", "main")
    git(trabajo, "switch", "-q", "-c", rama)
    escribir(trabajo, "app/a.py", "x = 1\ny = 2\n")
    confirmar(trabajo, "cambio")
    return trabajo


def lineas(salida: str, prefijo: str) -> list[str]:
    return [x for x in salida.splitlines() if x.startswith(prefijo)]


# --- Marca, base y archivos ------------------------------------------------------------


def test_la_primera_linea_es_la_marca(tmp_path):
    salida = contexto_revision.construir(repositorio(tmp_path))
    assert salida.splitlines()[0] == MARCA


def test_base_main_local_sin_remoto(tmp_path):
    repo = repositorio(tmp_path)
    base = git(repo, "merge-base", "HEAD", "main")
    salida = contexto_revision.construir(repo)
    assert f"Base: {base[:12]} (git merge-base HEAD main)" in salida
    assert "CONTEXTO INCOMPLETO" not in salida
    assert "app/a.py" in salida
    assert "Diff completo:" in salida


def test_base_por_origin_head(tmp_path):
    repo = repositorio(tmp_path, remoto=True)
    git(repo, "remote", "set-head", "origin", "main")
    salida = contexto_revision.construir(repo)
    assert "(git merge-base HEAD origin/main)" in salida


def test_origin_main_gana_al_main_local(tmp_path):
    repo = repositorio(tmp_path, remoto=True)
    base = git(repo, "merge-base", "HEAD", "origin/main")
    git(repo, "switch", "-q", "main")
    escribir(repo, "otro.txt", "solo en el main local\n")
    confirmar(repo, "main local adelantado")
    git(repo, "switch", "-q", "cambio")
    salida = contexto_revision.construir(repo)
    assert f"Base: {base[:12]} (git merge-base HEAD origin/main)" in salida
    assert "otro.txt" not in salida


def test_sin_base_de_fusion_es_incompleto(tmp_path):
    repo = tmp_path / "solo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "trabajo")
    escribir(repo, "a.txt", "a\n")
    confirmar(repo, "inicio")
    salida = contexto_revision.construir(repo)
    assert lineas(salida, "CONTEXTO INCOMPLETO: no hay base de fusión")
    assert "Archivos cambiados" not in salida


def test_fuera_de_un_repositorio_git(tmp_path):
    salida = contexto_revision.construir(tmp_path)
    assert salida.splitlines() == [
        MARCA,
        "CONTEXTO INCOMPLETO: la carpeta no es un repositorio git",
    ]


# --- Spec Kit, opcional ---------------------------------------------------------------


def test_sin_carpeta_specs_el_ticket_no_aplica_y_no_es_incompleto(tmp_path):
    salida = contexto_revision.construir(repositorio(tmp_path))
    assert "Ticket: no aplica (el repositorio no usa una carpeta specs/)" in salida
    assert "Constitución: no aplica" in salida
    assert "CONTEXTO INCOMPLETO" not in salida


def test_con_specs_y_rama_de_ticket(tmp_path):
    repo = repositorio(tmp_path, rama="123-demo")
    for nombre in ("spec.md", "plan.md", "tasks.md"):
        escribir(repo, f"specs/123-demo/{nombre}", f"# {nombre}\n")
    escribir(repo, ".specify/memory/constitution.md", "# Constitución\n")
    confirmar(repo, "documentos")
    salida = contexto_revision.construir(repo)
    assert "Ticket: specs/123-demo/" in salida
    assert "  - specs/123-demo/spec.md" in salida
    assert "Constitución: .specify/memory/constitution.md" in salida
    assert "specs/123-demo/plan.md [referencia]" in salida
    assert "CONTEXTO INCOMPLETO" not in salida


def test_con_specs_y_rama_sin_el_patron_es_incompleto(tmp_path):
    repo = repositorio(tmp_path, rama="cambio")
    escribir(repo, "specs/123-demo/spec.md", "# spec\n")
    confirmar(repo, "documentos")
    salida = contexto_revision.construir(repo)
    assert lineas(salida, "CONTEXTO INCOMPLETO: la rama «cambio» no sigue el patrón NNN-nombre")


# --- Umbral -------------------------------------------------------------------------------


def test_diff_omitido_si_supera_el_umbral(tmp_path):
    repo = repositorio(tmp_path)
    escribir(repo, "app/grande.py", "x = 1\n" * 3000)
    confirmar(repo, "grande")
    salida = contexto_revision.construir(repo)
    assert "Diff completo:" not in salida
    assert "Diff omitido" in salida
    assert "app/grande.py" in salida


def test_lista_agrupada_si_la_lista_no_cabe(tmp_path):
    repo = repositorio(tmp_path)
    for i in range(40):
        escribir(repo, f"app/m{i:02d}.py", "x = 1\n")
    confirmar(repo, "muchos")
    salida = contexto_revision.construir(repo, umbral=500)
    assert "lista agrupada por directorio" in salida
    assert "app/: 41 archivos" in salida


# --- Script ---------------------------------------------------------------------------------


def test_el_script_sale_con_0_y_la_marca(tmp_path):
    repo = repositorio(tmp_path)
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        timeout=60,
    )
    assert resultado.returncode == 0
    assert resultado.stdout.splitlines()[0] == MARCA
    assert "app/a.py" in resultado.stdout


def test_error_inesperado_sale_con_0_y_contexto_incompleto(monkeypatch, capsys):
    def falla(_raiz):
        raise RuntimeError("fallo")

    monkeypatch.setattr(contexto_revision, "construir", falla)
    assert contexto_revision.main() == 0
    assert capsys.readouterr().out.splitlines() == [
        MARCA,
        "CONTEXTO INCOMPLETO: error inesperado (RuntimeError)",
    ]


def test_solo_usa_la_biblioteca_estandar():
    arbol = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    modulos = {
        alias.name.split(".")[0]
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Import)
        for alias in nodo.names
    } | {
        nodo.module.split(".")[0]
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }
    assert modulos <= set(sys.stdlib_module_names)


@pytest.mark.parametrize("variable", ["CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT"])
def test_la_raiz_es_el_directorio_actual(tmp_path, monkeypatch, variable):
    # Bash no recibe las variables del plugin: la skill ejecuta el script en el proyecto.
    monkeypatch.setenv(variable, str(tmp_path / "otra"))
    monkeypatch.chdir(tmp_path)
    assert contexto_revision.raiz() == Path.cwd()
