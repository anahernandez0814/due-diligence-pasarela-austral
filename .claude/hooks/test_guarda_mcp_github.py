"""Pruebas de guarda_mcp_github.py (FR-024, FR-020, R4; contracts/guardas.md)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import guarda_mcp_github
import pytest

SCRIPT = Path(__file__).with_name("guarda_mcp_github.py")

OTROS_METODOS = [
    "add_project_item",
    "update_project_items",
    "delete_project_item",
    "create_project_status_update",
    "create_project_view",
    "update_project_view",
    "delete_project_view",
    "create_project",
    "create_iteration_field",
]


def entrada(datos):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "mcp__github__projects_write",
        "tool_input": datos,
    }


def mensaje(metodo: str) -> str:
    return (
        f"Método '{metodo}' de projects_write bloqueado: el proyecto solo actualiza ítems "
        "del Project (update_project_item)."
    )


def ejecutar_script(datos):
    """Como una terminal normal: sin PYTHONUTF8 ni PYTHONIOENCODING."""
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=datos if isinstance(datos, str) else json.dumps(datos, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        timeout=30,
    )


def test_update_project_item_se_permite():
    datos = {
        "method": "update_project_item",
        "owner": "o",
        "project_number": 1,
        "item_id": 7,
        "updated_field": {"name": "Status", "value": "In Progress"},
    }
    assert guarda_mcp_github.motivo(entrada(datos)) is None


@pytest.mark.parametrize("metodo", OTROS_METODOS)
def test_los_otros_metodos_se_bloquean(metodo):
    assert guarda_mcp_github.motivo(entrada({"method": metodo})) == mensaje(metodo)


@pytest.mark.parametrize(
    "datos",
    [{}, {"method": None}, {"method": 3}, {"method": ["update_project_item"]}],
)
def test_metodo_ausente_o_que_no_es_texto(datos):
    assert guarda_mcp_github.motivo(entrada(datos)) == mensaje("(ausente)")


@pytest.mark.parametrize("datos", [None, "update_project_item", ["update_project_item"], 1])
def test_tool_input_que_no_es_un_objeto(datos):
    assert guarda_mcp_github.motivo(entrada(datos)) == mensaje("(ausente)")


@pytest.mark.parametrize("metodo", ["Update_Project_Item", " update_project_item", "update"])
def test_solo_el_nombre_exacto(metodo):
    assert guarda_mcp_github.motivo(entrada({"method": metodo})) == mensaje(metodo)


# --- De extremo a extremo -------------------------------------------------------------


def test_script_permite_con_salida_0():
    resultado = ejecutar_script(entrada({"method": "update_project_item"}))
    assert (resultado.returncode, resultado.stdout, resultado.stderr) == (0, "", "")


@pytest.mark.parametrize("metodo", OTROS_METODOS)
def test_script_bloquea_con_salida_2(metodo):
    resultado = ejecutar_script(entrada({"method": metodo}))
    assert resultado.returncode == 2
    assert resultado.stdout == ""
    assert resultado.stderr.strip() == "[guarda_mcp_github] " + mensaje(metodo)


def test_script_sin_metodo_sale_con_2():
    resultado = ejecutar_script(entrada({}))
    assert resultado.returncode == 2
    assert "(ausente)" in resultado.stderr


def test_script_falla_cerrado_con_entrada_invalida():
    resultado = ejecutar_script("no es json")
    assert resultado.returncode == 2
    assert resultado.stderr.strip() == (
        "[guarda_mcp_github] La guarda falló (JSONDecodeError); la acción se bloquea por "
        "precaución."
    )
