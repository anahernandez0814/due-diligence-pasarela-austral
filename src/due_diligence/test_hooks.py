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
    TIPO_BLOQUEO_REGLA,
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
from due_diligence.reglas import (
    MOTIVO_CONSULTA_AJENA,
    MOTIVO_REGISTRO_PRIMERO,
    MOTIVO_SIN_COMERCIO,
)
from due_diligence.simulacion import (
    comercio_alto_riesgo,
    comercio_del_registro,
    comercios_parecidos,
    respuesta_del_contrato,
    respuesta_registro,
)

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


# ------------------------------------------------------------------ registro ilegible (FR-001)


@pytest.mark.parametrize("ilegible", ["no es json", "{}", "[]"])
def test_una_respuesta_ilegible_del_registro_deja_constancia_como_consulta_fallida(ilegible):
    estado, eventos, hooks = _caso()
    _ejecutar(_hook(hooks.subagente(Frente.REGISTRO), "PostToolUse"), _post(ilegible))
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_CONSULTA_FALLIDA and evento.frente is Frente.REGISTRO
    assert "no tiene la forma del contrato" in evento.detalle
    assert "no es json" not in evento.detalle  # no repite lo recibido
    assert estado.libro.fallo_de_hook is None  # una respuesta ilegible no es un fallo del hook


def test_un_error_estructurado_que_llega_por_posttooluse_tambien_deja_constancia():
    estado, eventos, hooks = _caso()
    error = {
        "error": True,
        "tipo": "datos_no_disponibles",
        "mensaje": "m",
        "reintentable": False,
        "obtenido": {},
    }
    _ejecutar(_hook(hooks.subagente(Frente.REGISTRO), "PostToolUse"), _post(error))
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_CONSULTA_FALLIDA and "datos_no_disponibles" in evento.detalle
    _registro_terminado(estado)
    assert estado.comercio is None


def test_una_respuesta_valida_del_registro_no_deja_evento_de_consulta_fallida():
    _, eventos, hooks = _caso()
    _ejecutar(_hook(hooks.subagente(Frente.REGISTRO), "PostToolUse"), _post(RESPUESTA))
    assert eventos.eventos() == []


# ------------------------------------------------------------- regla I.1: listas (FR-002, FR-018)

LISTAS = "mcp__pasarela__consultar_listas_restrictivas"
DELEGAR = "mcp__delegacion__delegar_frente"
SELLADO = "No se pudo registrar un hecho de la regla; se bloquea por precaución."


def _pre(nombre, entrada):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": nombre,
        "tool_input": entrada,
        "tool_use_id": "t1",
    }


def _caso_con_comercio():
    estado, eventos, hooks = _caso()
    _registro_terminado(estado)
    estado.registrar_identificacion(respuesta_registro(comercio_alto_riesgo()))
    return estado, eventos, hooks


def _es_denegacion(salida):
    return salida.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def _motivo(salida):
    return salida["hookSpecificOutput"]["permissionDecisionReason"]


def test_el_subagente_de_listas_tiene_el_pretooluse_de_su_herramienta():
    _, _, hooks = _caso()
    listas = hooks.subagente(Frente.LISTAS)
    assert "PreToolUse" in listas
    assert [m.matcher for m in listas["PreToolUse"]] == [LISTAS]


def test_el_coordinador_tiene_el_pretooluse_de_delegar_frente():
    _, _, hooks = _caso()
    coordinador = hooks.coordinador()
    assert [m.matcher for m in coordinador["PreToolUse"]] == [DELEGAR]


@pytest.mark.parametrize(
    "consulta",
    [
        {"tipo": "comercio", "identificador": "CO-TV-0001"},
        {"tipo": "comercio", "nombre": "Tienda Verde SAS"},
        {"tipo": "persona", "identificador": "PE-0001"},
        {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo"},
    ],
)
def test_el_hook_de_listas_permite_al_comercio_y_a_su_representante(consulta):
    _, eventos, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PreToolUse"), _pre(LISTAS, consulta))
    assert salida == permitir() and eventos.eventos() == []


def test_el_hook_de_listas_sin_comercio_deniega_deja_evento_con_la_regla_y_el_motivo():
    _, eventos, hooks = _caso()
    entrada = _pre(LISTAS, {"tipo": "comercio", "nombre": "Tienda Verde SAS"})
    salida = _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PreToolUse"), entrada)
    assert _es_denegacion(salida) and _motivo(salida) == MOTIVO_SIN_COMERCIO
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_BLOQUEO_REGLA and evento.regla == "I.1"
    assert evento.frente is Frente.LISTAS and evento.detalle == MOTIVO_SIN_COMERCIO


def test_el_hook_de_listas_con_una_consulta_ajena_deniega_sin_repetir_lo_consultado():
    _, eventos, hooks = _caso_con_comercio()
    entrada = _pre(LISTAS, {"tipo": "persona", "nombre": "Mateo Ríos Cabrera"})
    salida = _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PreToolUse"), entrada)
    assert _es_denegacion(salida) and _motivo(salida) == MOTIVO_CONSULTA_AJENA
    assert "Mateo" not in eventos.eventos()[0].detalle


@pytest.mark.parametrize(
    "entrada",
    [None, "texto", ["tipo"], {}, {"tipo": "comercio", "nombre": 3}, {"tipo": 4, "nombre": "x"}],
)
def test_el_hook_de_listas_con_una_entrada_malformada_deniega(entrada):
    _, _, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PreToolUse"), _pre(LISTAS, entrada))
    assert _es_denegacion(salida)


def test_el_hook_de_listas_si_permite_listas_lanza_una_excepcion_deniega_y_sella(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()

    def roto(_estado, _entrada):
        raise RuntimeError("detalle interno")

    monkeypatch.setattr(modulo_hooks, "permite_listas", roto)
    entrada = _pre(LISTAS, {"tipo": "comercio", "identificador": "CO-TV-0001"})
    salida = _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PreToolUse"), entrada)
    assert _es_denegacion(salida) and "detalle interno" not in _motivo(salida)
    assert estado.libro.fallo_de_hook
    assert eventos.eventos()[0].tipo == TIPO_FALLO_DE_HOOK


def test_con_el_libro_sellado_el_hook_de_listas_deniega_aunque_la_consulta_sea_valida():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    entrada = _pre(LISTAS, {"tipo": "comercio", "identificador": "CO-TV-0001"})
    salida = _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PreToolUse"), entrada)
    assert _es_denegacion(salida) and _motivo(salida) == SELLADO
    assert eventos.eventos()[-1].tipo == TIPO_BLOQUEO_REGLA


@pytest.mark.parametrize("frente", ["listas", "Listas", " LISTAS "])
def test_el_hook_de_delegar_deniega_listas_si_el_registro_no_se_delego(frente):
    _, eventos, hooks = _caso()
    salida = _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), _pre(DELEGAR, {"frente": frente}))
    assert _es_denegacion(salida) and _motivo(salida) == MOTIVO_REGISTRO_PRIMERO
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_BLOQUEO_REGLA and evento.regla == "I.1"
    assert evento.frente is Frente.LISTAS


def test_el_hook_de_delegar_permite_listas_con_comercio_y_con_el_registro_en_curso():
    _, _, hooks = _caso_con_comercio()
    pre = _pre(DELEGAR, {"frente": "listas"})
    assert _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), pre) == permitir()
    en_curso, _, otros_hooks = _caso()
    en_curso.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    assert _ejecutar(_hook(otros_hooks.coordinador(), "PreToolUse"), pre) == permitir()


def test_el_hook_de_delegar_deniega_listas_si_el_registro_termino_con_varias_coincidencias():
    estado, _, hooks = _caso()
    _registro_terminado(estado)
    estado.registrar_identificacion(respuesta_registro(*comercios_parecidos()))
    pre = _pre(DELEGAR, {"frente": "listas"})
    salida = _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), pre)
    assert _es_denegacion(salida) and "varias coincidencias" in _motivo(salida)
    assert "pida el identificador al analista" in _motivo(salida)


@pytest.mark.parametrize("frente", ["registro", "noticias", "categoria", "foo"])
def test_el_hook_de_delegar_deja_pasar_otros_frentes_sin_leer_el_estado(frente):
    _, eventos, hooks = _caso()  # sin registro: listas se denegaría
    salida = _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), _pre(DELEGAR, {"frente": frente}))
    assert salida == permitir() and eventos.eventos() == []


@pytest.mark.parametrize("entrada", [None, "listas", [], {}, {"frente": 3}, {"frente": None}])
def test_el_hook_de_delegar_con_una_entrada_malformada_deniega(entrada):
    _, _, hooks = _caso()
    salida = _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), _pre(DELEGAR, entrada))
    assert _es_denegacion(salida)


def test_con_el_libro_sellado_el_hook_de_delegar_deniega_listas():
    estado, _, hooks = _caso_con_comercio()
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    pre = _pre(DELEGAR, {"frente": "listas"})
    salida = _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), pre)
    assert _es_denegacion(salida) and _motivo(salida) == SELLADO


def test_el_hook_de_delegar_si_permite_delegar_listas_lanza_una_excepcion_deniega(monkeypatch):
    estado, _, hooks = _caso_con_comercio()

    def roto(_estado):
        raise RuntimeError("detalle interno")

    monkeypatch.setattr(modulo_hooks, "permite_delegar_listas", roto)
    pre = _pre(DELEGAR, {"frente": "listas"})
    salida = _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), pre)
    assert _es_denegacion(salida) and estado.libro.fallo_de_hook
