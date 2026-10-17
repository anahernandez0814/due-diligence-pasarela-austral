"""Pruebas de preparar_revision.py (R4, R6, FR-005; contracts/revisiones.md)."""

import os
import subprocess
import sys
from pathlib import Path

import preparar_revision
import pytest
from repositorio_pruebas import confirmar, crear_repo, escribir, git

SCRIPT = Path(__file__).with_name("preparar_revision.py")
MARCA = "CONTEXTO DE REVISIÓN"


@pytest.fixture
def repo(tmp_path):
    """`main` publicada con `viejo.py`, y la rama del ticket con un cambio de cada tipo."""
    trabajo = crear_repo(tmp_path)
    git(trabajo, "switch", "-q", "main")
    escribir(trabajo, "viejo.py", "a = 1\nb = 2\n")
    confirmar(trabajo, "añade viejo.py")
    git(trabajo, "push", "-q", "origin", "main")
    git(trabajo, "switch", "-q", "004-demo")
    git(trabajo, "merge", "-q", "main")
    (trabajo / "viejo.py").unlink()
    escribir(trabajo, "src/a.py", "x = 1\ny = 2\n")
    escribir(trabajo, "README.md", "Repositorio de prueba\nOtra línea\n")
    for nombre in ("spec.md", "plan.md", "tasks.md"):
        escribir(trabajo, f"specs/004-demo/{nombre}", f"# {nombre}\n")
    confirmar(trabajo, "cambio del ticket")
    return trabajo


def linea(salida: str, ruta: str) -> str:
    coincidencias = [x for x in salida.splitlines() if ruta in x and "+" in x]
    assert coincidencias, f"{ruta} no aparece en la lista"
    return coincidencias[0]


def test_la_primera_linea_es_la_marca(repo):
    assert preparar_revision.construir(repo).splitlines()[0] == MARCA


def test_la_base_es_la_de_origin_main_y_no_el_main_local(repo):
    base = git(repo, "merge-base", "HEAD", "origin/main")
    git(repo, "switch", "-q", "main")
    escribir(repo, "otro.txt", "solo en el main local\n")
    confirmar(repo, "main local adelantado")
    git(repo, "switch", "-q", "004-demo")
    salida = preparar_revision.construir(repo)
    assert base[:12] in salida
    assert "otro.txt" not in salida


def test_la_lista_trae_estado_y_estadisticas(repo):
    salida = preparar_revision.construir(repo)
    assert "+2 -0" in linea(salida, "src/a.py")
    assert "+1 -0" in linea(salida, "README.md")
    assert "+0 -2" in linea(salida, "viejo.py")


def test_los_eliminados_van_marcados(repo):
    salida = preparar_revision.construir(repo)
    assert "[eliminado]" in linea(salida, "viejo.py")
    assert "[eliminado]" not in linea(salida, "src/a.py")


def test_los_documentos_del_ticket_van_como_referencia(repo):
    salida = preparar_revision.construir(repo)
    assert "[referencia]" in linea(salida, "specs/004-demo/spec.md")
    assert "[referencia]" in linea(salida, "specs/004-demo/tasks.md")
    assert "[referencia]" not in linea(salida, "src/a.py")


def test_trae_las_rutas_del_ticket_y_de_la_constitucion(repo):
    salida = preparar_revision.construir(repo)
    for ruta in (
        "specs/004-demo/spec.md",
        "specs/004-demo/plan.md",
        "specs/004-demo/tasks.md",
        ".specify/memory/constitution.md",
    ):
        assert ruta in salida


def test_el_diff_completo_va_si_toda_la_salida_cabe_en_el_umbral(repo):
    umbral = 20_000
    salida = preparar_revision.construir(repo, umbral)
    assert "x = 1" in salida
    assert "Diff omitido" not in salida
    assert len(salida.encode("utf-8")) <= umbral


def test_el_diff_se_omite_si_la_salida_total_superaria_el_umbral(repo):
    escribir(repo, "src/grande.py", "".join(f"valor_{i} = {i}\n" for i in range(2000)))
    confirmar(repo, "archivo grande")
    umbral = 6_000
    salida = preparar_revision.construir(repo, umbral)
    assert "Diff omitido" in salida
    assert "valor_1999" not in salida
    assert salida.splitlines()[0] == MARCA
    assert "src/grande.py" in salida
    assert "specs/004-demo/spec.md" in salida
    assert len(salida.encode("utf-8")) <= umbral


def test_si_la_lista_sola_supera_el_umbral_se_agrupa_por_directorio(repo):
    for i in range(60):
        escribir(repo, f"src/modulo/f{i:02d}.py", "a = 1\n")
    for i in range(30):
        escribir(repo, f"docs/d{i:02d}.md", "texto\n")
    confirmar(repo, "muchos archivos")
    salida = preparar_revision.construir(repo, 1_200)
    assert "agrupada por directorio" in salida
    assert "src/modulo/: 60 archivos" in salida
    assert "docs/: 30 archivos" in salida
    assert "f59.py" not in salida
    assert "Diff omitido" in salida
    assert salida.splitlines()[0] == MARCA


def test_sin_origin_main_dice_que_el_contexto_esta_incompleto(repo):
    git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    salida = preparar_revision.construir(repo)
    assert salida.splitlines()[0] == MARCA
    assert "CONTEXTO INCOMPLETO:" in salida


def test_sin_carpeta_de_specs_dice_que_esta_incompleto(tmp_path):
    repo = crear_repo(tmp_path)
    escribir(repo, "src/a.py", "x = 1\n")
    confirmar(repo, "cambio sin specs")
    salida = preparar_revision.construir(repo)
    assert "CONTEXTO INCOMPLETO:" in salida
    assert "specs" in salida.split("CONTEXTO INCOMPLETO:")[1].splitlines()[0]


def test_una_rama_sin_patron_de_ticket_dice_que_esta_incompleto(tmp_path):
    repo = crear_repo(tmp_path, rama="prueba-revision")
    escribir(repo, "src/a.py", "x = 1\n")
    confirmar(repo, "cambio")
    assert "CONTEXTO INCOMPLETO:" in preparar_revision.construir(repo)


def test_fuera_de_un_repositorio_no_lanza_y_dice_que_esta_incompleto(tmp_path):
    salida = preparar_revision.construir(tmp_path)
    assert salida.splitlines()[0] == MARCA
    assert "CONTEXTO INCOMPLETO:" in salida


def ejecutar_script(cwd, **entorno_extra):
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    entorno.pop("CLAUDE_PROJECT_DIR", None)
    entorno.update(entorno_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        check=False,
    )


def test_el_script_sale_con_cero_y_empieza_por_la_marca(repo):
    resultado = ejecutar_script(repo)
    assert resultado.returncode == 0
    assert resultado.stdout.splitlines()[0] == MARCA


def test_el_script_sale_con_cero_aunque_no_haya_repositorio(tmp_path):
    resultado = ejecutar_script(tmp_path)
    assert resultado.returncode == 0
    assert resultado.stdout.splitlines()[0] == MARCA
    assert "CONTEXTO INCOMPLETO:" in resultado.stdout


def test_el_script_usa_claude_project_dir_si_esta_definida(repo, tmp_path):
    otra = tmp_path / "otra"
    otra.mkdir()
    resultado = ejecutar_script(otra, CLAUDE_PROJECT_DIR=str(repo))
    assert resultado.returncode == 0
    assert "src/a.py" in resultado.stdout


def test_el_script_no_recibe_argumentos():
    assert "sys.argv" not in SCRIPT.read_text(encoding="utf-8")


def test_la_salida_trae_el_commit_completo_de_head_justo_despues_de_la_rama(repo):
    lineas = preparar_revision.construir(repo).splitlines()
    posicion = next(i for i, x in enumerate(lineas) if x.startswith("Rama:"))
    assert lineas[posicion + 1] == f"Commit: {git(repo, 'rev-parse', 'HEAD')}"


def test_el_commit_cambia_con_un_commit_nuevo(repo):
    antes = preparar_revision.construir(repo)
    escribir(repo, "src/nuevo.py", "z = 3\n")
    nuevo = confirmar(repo, "otro commit")
    despues = preparar_revision.construir(repo)
    assert f"Commit: {nuevo}" in despues
    assert f"Commit: {nuevo}" not in antes


def test_el_script_desde_una_subcarpeta_encuentra_los_specs_en_la_raiz_del_repositorio(repo):
    subcarpeta = repo / "src"
    resultado = ejecutar_script(subcarpeta)
    assert resultado.returncode == 0
    assert "Ticket: specs/004-demo/" in resultado.stdout
    assert "CONTEXTO INCOMPLETO" not in resultado.stdout
    assert "src/a.py" in resultado.stdout


def test_preparar_y_veredicto_calculan_la_misma_raiz(repo, monkeypatch):
    import veredicto

    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(repo / "src")
    assert preparar_revision.raiz() == veredicto.raiz()
