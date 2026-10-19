"""Pruebas de guarda_datos.py: qué revisa, qué bloquea, el mensaje y el fallo cerrado.

Ningún valor con forma real se escribe en este archivo: se generan en la prueba con las
funciones de test_detector_datos.py.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import guarda_datos
import pytest
from test_detector_datos import ALNUM, AZAR, aleatorio, con_puntos, dv_dian, nueve_digitos, tarjeta

SCRIPT = Path(__file__).with_name("guarda_datos.py")
MENSAJE_FINAL = "Usa valores claramente ficticios o genera el valor en la prueba."

HERRAMIENTAS_MCP = [
    "mcp__github__add_issue_comment",
    "mcp__github__update_issue_comment",
    "mcp__github__create_pull_request",
    "mcp__github__update_pull_request",
    "mcp__github__issue_write",
    "mcp__github__add_reply_to_pull_request_comment",
    "mcp__github__pull_request_review_write",
    "mcp__github__add_comment_to_pending_review",
]


def generar(tipo: str) -> str:
    """Un valor con forma real del tipo pedido, generado al ejecutar la prueba."""
    if tipo == "tarjeta":
        return tarjeta(AZAR.choice("23456"), 16)
    if tipo == "nit":
        nueve = nueve_digitos()
        return f"{con_puntos(nueve)}-{dv_dian(nueve)}"
    if tipo == "cedula":
        return f"cédula {AZAR.randint(10_000_000, 99_999_999)}"
    return "ghp_" + aleatorio(ALNUM, 36)


TIPOS = ["tarjeta", "nit", "cedula", "credencial"]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


def entrada(repo, herramienta, datos):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": herramienta,
        "tool_input": datos,
        "cwd": str(repo),
    }


def ejecutar_script(repo, datos):
    """Como una terminal normal: sin PYTHONUTF8 ni PYTHONIOENCODING."""
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=datos if isinstance(datos, str) else json.dumps(datos, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**entorno, "CLAUDE_PROJECT_DIR": str(repo)},
        timeout=30,
    )


# --- Herramientas de archivo y de terminal --------------------------------------------


def datos_de(herramienta: str, repo: Path, texto: str) -> dict:
    archivo = str(repo / "lib" / "a.py")
    if herramienta == "Write":
        return {"file_path": archivo, "content": texto}
    if herramienta == "Edit":
        return {"file_path": archivo, "old_string": "x = 1", "new_string": texto}
    if herramienta == "NotebookEdit":
        return {"notebook_path": str(repo / "n.ipynb"), "new_source": texto}
    return {"command": f"echo '{texto}' > notas.txt"}


@pytest.mark.parametrize("tipo", TIPOS)
@pytest.mark.parametrize("herramienta", ["Write", "Edit", "NotebookEdit", "Bash", "PowerShell"])
def test_bloquea_cada_tipo_en_cada_herramienta(repo, herramienta, tipo):
    texto = f"línea uno\nvalor {generar(tipo)} aquí"
    motivo = guarda_datos.motivo(entrada(repo, herramienta, datos_de(herramienta, repo, texto)))
    assert motivo and f"{tipo} en " in motivo


def test_bash_revisa_los_heredocs(repo):
    comando = f"git commit -F - <<'FIN'\nmensaje\n{generar('tarjeta')}\nFIN"
    motivo = guarda_datos.motivo(entrada(repo, "Bash", {"command": comando}))
    assert motivo and "tarjeta en Bash, línea 3" in motivo


# --- Herramientas del MCP de GitHub ---------------------------------------------------


@pytest.mark.parametrize("tipo", TIPOS)
@pytest.mark.parametrize("herramienta", HERRAMIENTAS_MCP)
def test_bloquea_en_las_herramientas_mcp(repo, herramienta, tipo):
    datos = {"owner": "o", "repo": "r", "body": f"Hola\n{generar(tipo)}"}
    motivo = guarda_datos.motivo(entrada(repo, herramienta, datos))
    assert motivo and f"{tipo} en {herramienta} (body), línea 2" in motivo


@pytest.mark.parametrize(
    ("datos", "campo"),
    [
        ({"comments": [{"path": "a.py", "body": "VALOR"}]}, "comments[0].body"),
        ({"review": {"event": "COMMENT", "body": "VALOR"}}, "review.body"),
        ({"labels": ["uno", "VALOR"]}, "labels[1]"),
    ],
)
def test_bloquea_valores_anidados(repo, datos, campo):
    valor = generar("credencial")
    datos = json.loads(json.dumps(datos).replace("VALOR", valor))
    motivo = guarda_datos.motivo(entrada(repo, "mcp__github__pull_request_review_write", datos))
    assert (
        motivo
        and f"credencial en mcp__github__pull_request_review_write ({campo}), línea 1" in motivo
    )


@pytest.mark.parametrize(
    "herramienta",
    ["mcp__plugin_github_github__add_issue_comment", "mcp__otro_servidor__create_pull_request"],
)
def test_revisa_las_herramientas_mcp_de_cualquier_servidor(repo, herramienta):
    datos = {"body": f"Hola\n{generar('tarjeta')}"}
    motivo = guarda_datos.motivo(entrada(repo, herramienta, datos))
    assert motivo and f"tarjeta en {herramienta} (body), línea 2" in motivo


def test_valores_que_no_son_texto_se_ignoran(repo):
    datos = {"owner": "o", "repo": "r", "issue_number": 3, "draft": False, "body": None}
    assert guarda_datos.motivo(entrada(repo, "mcp__github__issue_write", datos)) is None


# --- Lo que se permite ----------------------------------------------------------------


def test_edit_solo_revisa_el_texto_nuevo(repo):
    datos = {
        "file_path": str(repo / "a.py"),
        "old_string": f"numero = '{generar('tarjeta')}'",
        "new_string": "numero = 'XX-0000'",
    }
    assert guarda_datos.motivo(entrada(repo, "Edit", datos)) is None


def test_herramienta_fuera_del_matcher_se_permite(repo):
    datos = {"file_path": str(repo / "a.txt")}
    assert guarda_datos.motivo(entrada(repo, "Read", datos)) is None


# --- Mensajes -------------------------------------------------------------------------


def test_mensaje_con_un_hallazgo(repo):
    datos = {"file_path": str(repo / "lib" / "a.py"), "content": f"x\n{generar('nit')}"}
    assert guarda_datos.motivo(entrada(repo, "Write", datos)) == (
        f"Dato con forma real bloqueado: nit en lib/a.py, línea 2. {MENSAJE_FINAL}"
    )


def test_script_lista_varios_hallazgos_sin_el_valor(repo):
    valores = [generar("tarjeta"), generar("nit"), generar("credencial")]
    contenido = f"a\n{valores[0]}\nb\n{valores[1]}\n{valores[2]}"
    datos = entrada(repo, "Write", {"file_path": str(repo / "a.py"), "content": contenido})
    resultado = ejecutar_script(repo, datos)
    assert resultado.returncode == 2
    assert resultado.stdout == ""
    assert resultado.stderr.strip() == (
        "[guarda_datos] Dato con forma real bloqueado: tarjeta en a.py, línea 2; "
        f"nit en a.py, línea 4; credencial en a.py, línea 5. {MENSAJE_FINAL}"
    )
    for valor in valores:
        assert valor not in resultado.stderr


def test_script_permite_con_salida_0(repo):
    datos = entrada(repo, "Write", {"file_path": str(repo / "a.md"), "content": "XX-0000"})
    resultado = ejecutar_script(repo, datos)
    assert (resultado.returncode, resultado.stdout, resultado.stderr) == (0, "", "")


def test_script_falla_cerrado_con_entrada_invalida(repo):
    resultado = ejecutar_script(repo, "no es json")
    assert resultado.returncode == 2
    assert resultado.stderr.strip() == (
        "[guarda_datos] La guarda falló (JSONDecodeError); la acción se bloquea por precaución."
    )
