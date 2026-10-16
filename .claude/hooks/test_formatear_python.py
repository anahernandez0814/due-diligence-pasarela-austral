"""Pruebas de formatear_python.py (FR-014, FR-015, FR-023, R12; contracts/guardas.md).

Los archivos viven en un proyecto temporal con su `pyproject.toml`, del que ruff toma la
configuración. `CLAUDE_PROJECT_DIR` es la raíz del repositorio, de la que `uv run` toma
el ruff del `uv.lock`, como en la sesión.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("formatear_python.py")
RAIZ = Path(__file__).resolve().parents[2]
MAL = "x  =  [1,2 ,3]\n"
BIEN = "x = [1, 2, 3]\n"


@pytest.fixture
def proyecto(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ruff]\nline-length = 100\nextend-exclude = ["excluida"]\n', encoding="utf-8"
    )
    (tmp_path / "excluida").mkdir()
    return tmp_path


def entrada(archivo, herramienta="Write"):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": herramienta,
        "tool_input": {"file_path": str(archivo)},
        "cwd": str(RAIZ),
    }


def ejecutar(datos, raiz=RAIZ, cwd=None, path=None):
    """Lanza el script como una terminal normal: sin PYTHONUTF8 ni PYTHONIOENCODING."""
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    entorno["CLAUDE_PROJECT_DIR"] = str(raiz)
    if path is not None:
        entorno["PATH"] = path
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=datos if isinstance(datos, str) else json.dumps(datos, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        cwd=cwd,
        timeout=60,
    )


def contexto(resultado) -> str:
    salida = json.loads(resultado.stdout)
    assert salida["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    return salida["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("herramienta", ["Write", "Edit"])
def test_formatea_un_py_mal_formateado(proyecto, herramienta):
    archivo = proyecto / "a.py"
    archivo.write_text(MAL, encoding="utf-8")
    resultado = ejecutar(entrada(archivo, herramienta))
    assert (resultado.returncode, resultado.stdout) == (0, "")
    assert archivo.read_text(encoding="utf-8") == BIEN
    comprobacion = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", str(archivo)],
        capture_output=True,
        cwd=proyecto,
    )
    assert comprobacion.returncode == 0


def test_no_toca_un_archivo_que_no_es_python(proyecto):
    archivo = proyecto / "notas.md"
    archivo.write_text(MAL, encoding="utf-8")
    resultado = ejecutar(entrada(archivo))
    assert (resultado.returncode, resultado.stdout, resultado.stderr) == (0, "", "")
    assert archivo.read_text(encoding="utf-8") == MAL


def test_error_de_sintaxis_informa_y_conserva_el_archivo(proyecto):
    archivo = proyecto / "configuración.py"
    archivo.write_text("def roto(:\n    pass\n", encoding="utf-8")
    resultado = ejecutar(entrada(archivo))
    assert resultado.returncode == 0
    mensaje = contexto(resultado)
    assert mensaje.startswith("[formatear_python] No se pudo formatear ")
    assert "configuración.py" in mensaje
    assert archivo.read_text(encoding="utf-8") == "def roto(:\n    pass\n"


def test_no_toca_un_py_excluido(proyecto):
    archivo = proyecto / "excluida" / "a.py"
    archivo.write_text(MAL, encoding="utf-8")
    resultado = ejecutar(entrada(archivo))
    assert (resultado.returncode, resultado.stdout) == (0, "")
    assert archivo.read_text(encoding="utf-8") == MAL


def test_formatea_con_el_cwd_fuera_del_repositorio(proyecto):
    archivo = proyecto / "a.py"
    archivo.write_text(MAL, encoding="utf-8")
    resultado = ejecutar(entrada(archivo), cwd=Path(proyecto.anchor))
    assert (resultado.returncode, resultado.stdout) == (0, "")
    assert archivo.read_text(encoding="utf-8") == BIEN


def test_sin_uv_informa_con_salida_0(proyecto):
    archivo = proyecto / "a.py"
    archivo.write_text(MAL, encoding="utf-8")
    vacia = proyecto / "sin_programas"
    vacia.mkdir()
    resultado = ejecutar(entrada(archivo), path=str(vacia))
    assert resultado.returncode == 0
    assert "No se pudo formatear" in contexto(resultado)
    assert archivo.read_text(encoding="utf-8") == MAL


def test_sin_ruff_informa_con_salida_0(proyecto):
    # Un proyecto sin uv.lock ni ruff: `uv run --frozen` no puede ejecutar ruff.
    archivo = proyecto / "a.py"
    archivo.write_text(MAL, encoding="utf-8")
    resultado = ejecutar(entrada(archivo), raiz=proyecto)
    assert resultado.returncode == 0
    assert "No se pudo formatear" in contexto(resultado)
    assert archivo.read_text(encoding="utf-8") == MAL


def test_archivo_inexistente_sale_con_0(proyecto):
    resultado = ejecutar(entrada(proyecto / "no_existe.py"))
    assert (resultado.returncode, resultado.stdout, resultado.stderr) == (0, "", "")


@pytest.mark.parametrize("datos", ["no es json", "[1, 2]", {"tool_input": None}])
def test_nunca_sale_con_2(datos):
    assert ejecutar(datos).returncode == 0
