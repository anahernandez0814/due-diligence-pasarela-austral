"""Tests de los hooks de las reglas de negocio (R1, R2, R5, contrato `hooks.md`).

Los hooks se prueban llamando a sus callbacks directamente con entradas con la forma que el SDK
0.2.168 entrega (medida en R1). Ningún test llama al modelo.
"""

import asyncio
import json
import typing

import pytest
from claude_agent_sdk import types as sdk

from due_diligence import hooks as modulo_hooks
from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.eventos import (
    TIPO_CONSULTA_FALLIDA,
    TIPO_FALLO_DE_HOOK,
    RegistroEventos,
)
from due_diligence.frentes import Frente
from due_diligence.hooks import (
    HooksDelCaso,
    bloquear_cierre,
    denegar,
    fallar_cerrado,
    leer_respuesta,
    permitir,
)
from due_diligence.simulacion import comercio_del_registro, respuesta_del_contrato

REGISTRO = "mcp__pasarela__consultar_registro_mercantil"


def _caso():
    estado = EstadoCaso("solicitud")
    eventos = RegistroEventos()
    return estado, eventos, HooksDelCaso(estado, eventos)


def _hook(hooks, evento):
    return hooks[evento][0].hooks[0]


def _registro_terminado(estado):
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)


def _post(respuesta, nombre=REGISTRO, entrada=None):
    texto = respuesta if isinstance(respuesta, str) else json.dumps(respuesta, ensure_ascii=False)
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": nombre,
        "tool_input": entrada or {"identificador": "CO-TV-0001"},
        "tool_response": texto,
        "tool_use_id": "t1",
    }


def _fallo(error, nombre=REGISTRO):
    return {
        "hook_event_name": "PostToolUseFailure",
        "tool_name": nombre,
        "tool_input": {"identificador": "CO-TV-0001"},
        "error": json.dumps(error, ensure_ascii=False),
        "tool_use_id": "t1",
    }


def _ejecutar(hook, entrada):
    return asyncio.run(hook(entrada, entrada.get("tool_use_id"), None))


# ------------------------------------------------------------------ salidas tipadas (R2)


def test_permitir_es_un_objeto_vacio():
    assert permitir() == {}


def test_denegar_tiene_la_forma_de_pretooluse_del_sdk():
    salida = denegar("motivo")
    assert salida == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "motivo",
        }
    }
    especifica = salida["hookSpecificOutput"]
    pistas = typing.get_type_hints(sdk.PreToolUseHookSpecificOutput)
    assert especifica["permissionDecision"] in typing.get_args(pistas["permissionDecision"])
    assert especifica["hookEventName"] in typing.get_args(pistas["hookEventName"])
    assert set(especifica) <= set(pistas)


def test_bloquear_cierre_tiene_la_forma_del_stop_del_sdk():
    salida = bloquear_cierre("motivo")
    assert salida == {"decision": "block", "reason": "motivo"}
    pistas = typing.get_type_hints(sdk.SyncHookJSONOutput)
    assert salida["decision"] in typing.get_args(pistas["decision"])
    assert set(salida) <= set(pistas)


# ------------------------------------------------------------------ leer_respuesta (R1)


RESPUESTA = respuesta_del_contrato("coincidencias", [comercio_del_registro()], ["CO-TV-0001"])


def test_leer_respuesta_acepta_el_texto_json_de_stdio():
    resultado, error = leer_respuesta(json.dumps(RESPUESTA))
    assert resultado == RESPUESTA and error is None


def test_leer_respuesta_acepta_la_lista_de_bloques_de_un_servidor_en_proceso():
    bloques = [{"type": "text", "text": json.dumps(RESPUESTA)}]
    assert leer_respuesta(bloques) == (RESPUESTA, None)


def test_leer_respuesta_de_un_fallo_devuelve_el_error_estructurado():
    error = {
        "error": True,
        "tipo": "servicio_no_disponible",
        "mensaje": "no disponible",
        "reintentable": True,
        "obtenido": {},
    }
    resultado, leido = leer_respuesta(json.dumps(error), es_error=True)
    assert resultado is None and leido == error


@pytest.mark.parametrize("ilegible", ["no es json", "[1, 2]", "{}", None, 7])
def test_leer_respuesta_ilegible_no_es_ni_resultado_ni_error(ilegible):
    assert leer_respuesta(ilegible) == (None, None)


def test_leer_respuesta_delega_en_interpretar_resultado_sin_analizador_propio(monkeypatch):
    llamadas = []

    def falso(contenido, es_error):
        llamadas.append((contenido, es_error))
        return {"hecho": "por el único lector"}, None

    monkeypatch.setattr(modulo_hooks, "interpretar_resultado", falso)
    assert leer_respuesta("x", es_error=True) == ({"hecho": "por el único lector"}, None)
    assert llamadas == [("x", True)]


# ------------------------------------------------------------------ fallar_cerrado (FR-012, R2)


def _envuelto(tipo, hook, estado, eventos):
    return fallar_cerrado(hook, tipo, estado, eventos, Frente.LISTAS)


async def _roto(entrada, tool_use_id, contexto):
    raise RuntimeError("detalle interno que el modelo no debe ver")


def test_un_pretooluse_que_lanza_deniega_con_un_motivo_generico_y_sella_el_libro():
    estado, eventos, _ = _caso()
    salida = asyncio.run(_envuelto("PreToolUse", _roto, estado, eventos)({}, "t1", None))
    razon = salida["hookSpecificOutput"]["permissionDecisionReason"]
    assert salida["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "detalle interno" not in razon and "RuntimeError" not in razon
    assert "se bloquea por precaución" in razon
    assert estado.libro.fallo_de_hook
    assert [e.tipo for e in eventos.eventos()] == [TIPO_FALLO_DE_HOOK]
    assert eventos.eventos()[0].frente is Frente.LISTAS
    assert "detalle interno" not in eventos.eventos()[0].detalle


def test_un_stop_que_lanza_bloquea_el_cierre_y_cuenta_como_devolucion():
    estado, eventos, _ = _caso()
    salida = asyncio.run(_envuelto("Stop", _roto, estado, eventos)({}, None, None))
    assert salida["decision"] == "block"
    assert estado.libro.cierres_impedidos == 1
    assert estado.libro.fallo_de_hook
    assert eventos.eventos()[0].tipo == TIPO_FALLO_DE_HOOK


@pytest.mark.parametrize("tipo", ["PostToolUse", "PostToolUseFailure"])
def test_un_post_que_lanza_devuelve_vacio_sella_el_libro_y_deja_el_evento(tipo):
    estado, eventos, _ = _caso()
    salida = asyncio.run(_envuelto(tipo, _roto, estado, eventos)({}, "t1", None))
    assert salida == {}
    assert estado.libro.fallo_de_hook
    assert eventos.eventos()[0].tipo == TIPO_FALLO_DE_HOOK


def test_un_hook_que_no_falla_pasa_su_salida_sin_cambios():
    estado, eventos, _ = _caso()

    async def bien(entrada, tool_use_id, contexto):
        return denegar("a propósito")

    salida = asyncio.run(_envuelto("PreToolUse", bien, estado, eventos)({}, "t1", None))
    assert salida == denegar("a propósito")
    assert estado.libro.fallo_de_hook is None and eventos.eventos() == []


def test_la_cancelacion_no_se_traga_ni_sella_el_libro():
    # `CancelledError` es `BaseException`: el envoltorio atrapa `Exception`, no la cancelación.
    estado, eventos, _ = _caso()

    async def lento(entrada, tool_use_id, contexto):
        await asyncio.sleep(10)

    async def probar():
        tarea = asyncio.create_task(
            _envuelto("PostToolUse", lento, estado, eventos)({}, "t1", None)
        )
        await asyncio.sleep(0)
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea

    asyncio.run(probar())
    assert estado.libro.fallo_de_hook is None and eventos.eventos() == []


# ------------------------------------------------------------------ hook del registro (FR-001)


def test_el_subagente_de_registro_tiene_post_y_failure_con_el_nombre_exacto():
    _, _, hooks = _caso()
    registro = hooks.subagente(Frente.REGISTRO)
    assert set(registro) == {"PostToolUse", "PostToolUseFailure"}
    for evento in registro:
        assert [m.matcher for m in registro[evento]] == [REGISTRO]


def test_una_coincidencia_unica_identifica_al_comercio():
    estado, _, hooks = _caso()
    _ejecutar(_hook(hooks.subagente(Frente.REGISTRO), "PostToolUse"), _post(RESPUESTA))
    _registro_terminado(estado)
    assert estado.comercio is not None and estado.comercio["identificador"] == "CO-TV-0001"


def test_una_respuesta_de_una_coincidencia_en_lista_de_bloques_tambien_identifica():
    estado, _, hooks = _caso()
    bloques = [{"type": "text", "text": json.dumps(RESPUESTA)}]
    entrada = _post(RESPUESTA)
    entrada["tool_response"] = bloques
    _ejecutar(_hook(hooks.subagente(Frente.REGISTRO), "PostToolUse"), entrada)
    _registro_terminado(estado)
    assert estado.comercio is not None


@pytest.mark.parametrize(
    ("respuesta", "motivo"),
    [
        (
            respuesta_del_contrato(
                "coincidencias",
                [
                    comercio_del_registro("CO-AM-0004", "Almacén Mirador SAS"),
                    comercio_del_registro("CO-AM-0005", "Almacén Mirador del Sur SAS"),
                ],
                ["CO-AM-0004", "CO-AM-0005"],
            ),
            "varias coincidencias",
        ),
        (respuesta_del_contrato("sin_coincidencias", [], []), "ninguna coincidencia"),
    ],
)
def test_varias_coincidencias_o_ninguna_no_identifican(respuesta, motivo):
    estado, _, hooks = _caso()
    _ejecutar(_hook(hooks.subagente(Frente.REGISTRO), "PostToolUse"), _post(respuesta))
    _registro_terminado(estado)
    assert estado.comercio is None
    assert motivo in estado.motivo_comercio


@pytest.mark.parametrize("ilegible", ["no es json", "{}", "[]"])
def test_una_respuesta_ilegible_no_identifica(ilegible):
    estado, _, hooks = _caso()
    _ejecutar(_hook(hooks.subagente(Frente.REGISTRO), "PostToolUse"), _post(ilegible))
    _registro_terminado(estado)
    assert estado.comercio is None and estado.identificaciones == []
    assert estado.motivo_comercio == "El registro no devolvió datos."


def test_un_fallo_de_la_herramienta_deja_un_evento_y_no_identifica():
    estado, eventos, hooks = _caso()
    error = {
        "error": True,
        "tipo": "datos_no_disponibles",
        "mensaje": "mensaje",
        "reintentable": False,
        "obtenido": {},
    }
    _ejecutar(_hook(hooks.subagente(Frente.REGISTRO), "PostToolUseFailure"), _fallo(error))
    _registro_terminado(estado)
    assert estado.comercio is None and estado.identificaciones == []
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_CONSULTA_FALLIDA and evento.frente is Frente.REGISTRO
    assert "datos_no_disponibles" in evento.detalle
    assert estado.libro.fallo_de_hook is None  # un error de la herramienta no es un fallo del hook


def test_si_el_hook_del_registro_falla_se_sella_el_libro_y_nada_queda_identificado(monkeypatch):
    estado, eventos, hooks = _caso()

    def roto(_respuesta):
        raise RuntimeError("fallo")

    monkeypatch.setattr(estado, "registrar_identificacion", roto)
    _ejecutar(_hook(hooks.subagente(Frente.REGISTRO), "PostToolUse"), _post(RESPUESTA))
    _registro_terminado(estado)
    assert estado.comercio is None
    assert estado.libro.fallo_de_hook
    assert eventos.eventos()[0].tipo == TIPO_FALLO_DE_HOOK


def test_cancelar_el_frente_antes_de_que_corra_el_hook_no_deja_una_identificacion_a_medias():
    estado, _, hooks = _caso()
    hook = _hook(hooks.subagente(Frente.REGISTRO), "PostToolUse")

    async def probar():
        tarea = asyncio.create_task(hook(_post(RESPUESTA), "t1", None))
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea
        assert estado.identificaciones == []  # no se guardó nada
        await hook(_post(RESPUESTA), "t2", None)
        assert len(estado.identificaciones) == 1  # se guardó completa

    asyncio.run(probar())
    _registro_terminado(estado)
    assert estado.comercio is not None
    assert estado.identificaciones[0].comercio == estado.comercio
