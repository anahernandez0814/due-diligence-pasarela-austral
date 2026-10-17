"""Tests de la clasificación del fin del ciclo (R5, FR-010 a FR-012, SC-005).

Se alimenta con mensajes de resultado simulados: el texto de la respuesta nunca decide.
"""

import pytest
from claude_agent_sdk import ResultMessage
from claude_agent_sdk._errors import ResultError

from due_diligence.terminacion import (
    Terminacion,
    clasificar,
    clasificar_error,
    clasificar_resultado,
    sin_resultado,
)


def _resultado(
    subtype="success", stop_reason="end_turn", is_error=False, terminal="completed", texto=""
):
    return ResultMessage(
        subtype=subtype,
        duration_ms=1,
        duration_api_ms=1,
        is_error=is_error,
        num_turns=1,
        session_id="sesion-de-prueba",
        stop_reason=stop_reason,
        result=texto,
        terminal_reason=terminal,
    )


def test_end_turn_es_una_terminacion_normal():
    clasificacion = clasificar_resultado(_resultado())
    assert clasificacion.terminacion is Terminacion.NORMAL


def test_max_tokens_es_una_terminacion_anomala():
    clasificacion = clasificar_resultado(_resultado(stop_reason="max_tokens"))
    assert clasificacion.terminacion is Terminacion.ANOMALA


def test_error_max_turns_con_stop_reason_tool_use_es_el_limite_de_seguridad():
    # Medido en R14: al agotar max_turns el stop_reason llega como tool_use, no como max_tokens.
    clasificacion = clasificar_resultado(
        _resultado(
            subtype="error_max_turns", stop_reason="tool_use", is_error=True, terminal="max_turns"
        )
    )
    assert clasificacion.terminacion is Terminacion.LIMITE_SEGURIDAD


@pytest.mark.parametrize("stop_reason", ["end_turn", "max_tokens", "tool_use", None])
def test_el_subtype_del_limite_gana_al_stop_reason(stop_reason):
    clasificacion = clasificar("error_max_turns", stop_reason, True, "max_turns")
    assert clasificacion.terminacion is Terminacion.LIMITE_SEGURIDAD


@pytest.mark.parametrize("texto", ["listo", "Listo, terminé el caso", "TERMINADO"])
def test_el_texto_no_decide_max_tokens_sigue_siendo_anomala(texto):
    clasificacion = clasificar_resultado(_resultado(stop_reason="max_tokens", texto=texto))
    assert clasificacion.terminacion is Terminacion.ANOMALA


@pytest.mark.parametrize("texto", ["", "error", "no pude terminar"])
def test_el_texto_no_decide_end_turn_sigue_siendo_normal(texto):
    assert clasificar_resultado(_resultado(texto=texto)).terminacion is Terminacion.NORMAL


@pytest.mark.parametrize(
    ("subtype", "stop_reason", "is_error", "terminal"),
    [
        ("success", "refusal", False, "completed"),
        ("success", "pause_turn", False, "completed"),
        ("success", "stop_sequence", False, "completed"),
        ("success", None, False, "completed"),
        ("success", "end_turn", True, "api_error"),
        ("error_during_execution", "end_turn", True, "error"),
        ("error_max_budget_usd", "tool_use", True, "max_budget"),
    ],
)
def test_cualquier_otro_caso_es_anomalo_con_el_valor_original_en_el_detalle(
    subtype, stop_reason, is_error, terminal
):
    clasificacion = clasificar(subtype, stop_reason, is_error, terminal)
    assert clasificacion.terminacion is Terminacion.ANOMALA
    assert f"subtype={subtype}" in clasificacion.detalle
    assert f"stop_reason={stop_reason}" in clasificacion.detalle
    assert f"terminal_reason={terminal}" in clasificacion.detalle


def test_el_detalle_incluye_los_tres_valores_originales():
    clasificacion = clasificar_resultado(_resultado())
    assert clasificacion.subtype == "success"
    assert clasificacion.stop_reason == "end_turn"
    assert clasificacion.terminal_reason == "completed"
    for valor in ("success", "end_turn", "completed"):
        assert valor in clasificacion.detalle


def test_un_result_error_se_clasifica_como_el_mensaje_equivalente():
    datos = {
        "subtype": "error_max_turns",
        "stop_reason": "tool_use",
        "terminal_reason": "max_turns",
    }
    error = ResultError("Reached maximum number of turns (1)", data=datos, exit_code=1)
    del_error = clasificar_error(error)
    del_mensaje = clasificar_resultado(
        _resultado(
            subtype="error_max_turns", stop_reason="tool_use", is_error=True, terminal="max_turns"
        )
    )
    assert del_error.terminacion is del_mensaje.terminacion is Terminacion.LIMITE_SEGURIDAD
    assert (del_error.subtype, del_error.stop_reason, del_error.terminal_reason) == (
        del_mensaje.subtype,
        del_mensaje.stop_reason,
        del_mensaje.terminal_reason,
    )


def test_un_result_error_de_la_api_es_anomalo():
    datos = {"subtype": "success", "stop_reason": "end_turn", "terminal_reason": "api_error"}
    clasificacion = clasificar_error(ResultError("API Error", data=datos, exit_code=1))
    assert clasificacion.terminacion is Terminacion.ANOMALA
    assert "api_error" in clasificacion.detalle


def test_un_result_error_sin_datos_es_anomalo():
    assert (
        clasificar_error(ResultError("sin datos", exit_code=1)).terminacion is Terminacion.ANOMALA
    )


def test_un_flujo_sin_mensaje_de_resultado_es_anomalo():
    clasificacion = sin_resultado()
    assert clasificacion.terminacion is Terminacion.ANOMALA
    assert "sin mensaje de resultado" in clasificacion.detalle


def test_las_funciones_no_reciben_el_texto_de_la_respuesta():
    import inspect

    for funcion in (clasificar,):
        parametros = set(inspect.signature(funcion).parameters)
        assert parametros == {"subtype", "stop_reason", "is_error", "terminal_reason"}
