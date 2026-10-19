"""Casos de la guarda de datos propios de este proyecto (#13, R2).

La guarda vive en el plugin (`plugins/guardas-y-revision/hooks/`) y es la misma que ejecuta
este repositorio. Sus tests genéricos van junto a ella; aquí quedan los que dependen de este
proyecto: el mensaje de ejemplo del enunciado y los identificadores ficticios `CO-XX-NNNN`.
También el archivo de compatibilidad `.claude/hooks/guarda_datos.py`.
"""

import ast
import io
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import detector_datos
import guarda_datos
import pytest
from test_guarda_datos import entrada, generar

RAIZ = Path(__file__).resolve().parents[2]
COMPATIBILIDAD = Path(__file__).with_name("guarda_datos.py")
GUARDA_PLUGIN = RAIZ / "plugins" / "guardas-y-revision" / "hooks" / "guarda_datos.py"
IDENTIFICADORES = ["CO-TV-0001", "CO-TA-0002", "CO-AM-0004"]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


def mensaje_de_ejemplo() -> str:
    enunciado = (RAIZ / "docs" / "enunciado.md").read_text(encoding="utf-8")
    return re.search(r'"(Necesito el due diligence[^"]*)"', enunciado).group(1)


# --- Lo que se permite en este proyecto ----------------------------------------------


def test_la_guarda_importada_es_la_del_plugin():
    assert Path(guarda_datos.__file__).resolve() == GUARDA_PLUGIN.resolve()


def test_mensaje_de_ejemplo_del_enunciado_no_coincide():
    mensaje = mensaje_de_ejemplo()
    assert "CO-TV-0001" in mensaje
    assert detector_datos.buscar(mensaje) == []


@pytest.mark.parametrize("herramienta", ["Write", "Bash", "mcp__github__add_issue_comment"])
def test_mensaje_de_ejemplo_del_enunciado_se_permite(repo, herramienta):
    mensaje = mensaje_de_ejemplo()
    if herramienta == "mcp__github__add_issue_comment":
        datos = {"body": mensaje}
    elif herramienta == "Write":
        datos = {"file_path": str(repo / "docs" / "x.md"), "content": mensaje}
    else:
        datos = {"command": f"echo '{mensaje}'"}
    assert guarda_datos.motivo(entrada(repo, herramienta, datos)) is None


@pytest.mark.parametrize("identificador", IDENTIFICADORES)
def test_identificadores_ficticios_del_proyecto_no_coinciden(identificador):
    assert detector_datos.buscar(identificador) == []


def test_edit_con_identificador_del_proyecto_se_permite(repo):
    datos = {
        "file_path": str(repo / "a.py"),
        "old_string": f"numero = '{generar('tarjeta')}'",
        "new_string": "numero = 'CO-TV-0001'",
    }
    assert guarda_datos.motivo(entrada(repo, "Edit", datos)) is None


# --- Archivo de compatibilidad ---------------------------------------------------------


def ejecutar(script: Path, datos: dict, raiz: Path) -> subprocess.CompletedProcess:
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(datos, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**entorno, "CLAUDE_PROJECT_DIR": str(raiz)},
        timeout=30,
    )


def test_compatibilidad_no_tiene_logica_de_deteccion():
    arbol = ast.parse(COMPATIBILIDAD.read_text(encoding="utf-8"))
    importados = {
        alias.name.split(".")[0]
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Import)
        for alias in nodo.names
    } | {
        nodo.module.split(".")[0]
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }
    assert importados <= {"runpy", "sys", "pathlib"}
    assert not [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef | ast.ClassDef)]
    texto = COMPATIBILIDAD.read_text(encoding="utf-8")
    assert "runpy.run_path(" in texto and 'run_name="__main__"' in texto
    for termino in ("detector_datos", "buscar(", "Dato con forma real", "re.compile"):
        assert termino not in texto


def test_settings_no_registra_la_compatibilidad():
    texto = (RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert ".claude/hooks/guarda_datos.py" not in texto
    assert "plugins/guardas-y-revision/hooks/guarda_datos.py" in texto


def test_compatibilidad_ejecuta_la_guarda_del_plugin(repo):
    bloquea = entrada(repo, "Write", {"file_path": str(repo / "a.py"), "content": generar("nit")})
    resultado = ejecutar(COMPATIBILIDAD, bloquea, repo)
    assert resultado.returncode == 2
    assert resultado.stderr.count("[guarda_datos] Dato con forma real bloqueado: nit") == 1
    permite = entrada(repo, "Write", {"file_path": str(repo / "a.md"), "content": "CO-TV-0001"})
    assert ejecutar(COMPATIBILIDAD, permite, repo).returncode == 0


def test_compatibilidad_falla_cerrado_si_falta_la_guarda_del_plugin(tmp_path):
    hooks = tmp_path / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    copia = hooks / "guarda_datos.py"
    shutil.copy(COMPATIBILIDAD, copia)
    datos = entrada(tmp_path, "Write", {"file_path": str(tmp_path / "a.md"), "content": "hola"})
    resultado = ejecutar(copia, datos, tmp_path)
    assert resultado.returncode == 2
    assert "No se pudo ejecutar la guarda del plugin (FileNotFoundError)" in resultado.stderr


def test_compatibilidad_falla_cerrado_si_la_guarda_no_carga(tmp_path):
    hooks = tmp_path / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    copia = hooks / "guarda_datos.py"
    shutil.copy(COMPATIBILIDAD, copia)
    plugin = tmp_path / "plugins" / "guardas-y-revision" / "hooks"
    plugin.mkdir(parents=True)
    (plugin / "guarda_datos.py").write_text("import modulo_que_no_existe\n", encoding="utf-8")
    datos = entrada(tmp_path, "Write", {"file_path": str(tmp_path / "a.md"), "content": "hola"})
    resultado = ejecutar(copia, datos, tmp_path)
    assert resultado.returncode == 2
    assert "No se pudo ejecutar la guarda del plugin (ModuleNotFoundError)" in resultado.stderr


def test_compatibilidad_falla_cerrado_si_no_puede_reconfigurar_stderr(monkeypatch):
    class StderrQueFalla(io.StringIO):
        def reconfigure(self, **_):
            raise OSError("sin reconfigurar")

    stderr = StderrQueFalla()
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(sys, "path", list(sys.path))
    with pytest.raises(SystemExit) as salida:
        runpy.run_path(str(COMPATIBILIDAD), run_name="__main__")
    assert salida.value.code == 2
    assert "No se pudo ejecutar la guarda del plugin (OSError)" in stderr.getvalue()


def test_compatibilidad_falla_cerrado_si_la_guarda_no_decide(tmp_path):
    hooks = tmp_path / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    copia = hooks / "guarda_datos.py"
    shutil.copy(COMPATIBILIDAD, copia)
    plugin = tmp_path / "plugins" / "guardas-y-revision" / "hooks"
    plugin.mkdir(parents=True)
    (plugin / "guarda_datos.py").write_text("x = 1\n", encoding="utf-8")
    datos = entrada(tmp_path, "Write", {"file_path": str(tmp_path / "a.md"), "content": "hola"})
    resultado = ejecutar(copia, datos, tmp_path)
    assert resultado.returncode == 2
    assert "terminó sin decidir" in resultado.stderr
