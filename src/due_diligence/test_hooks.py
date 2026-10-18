"""Tests de los hooks de las reglas de negocio (R1, R2, R5, contrato `hooks.md`).

Los hooks se prueban llamando a sus callbacks directamente con entradas con la forma que el SDK
0.2.168 entrega (medida en R1). Ningún test llama al modelo.
"""

import asyncio
import itertools
import json
import typing

import pytest
from claude_agent_sdk import types as sdk

from due_diligence import configuracion
from due_diligence import hooks as modulo_hooks
from due_diligence.cobertura import calcular_cobertura
from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_CIERRE_IMPEDIDO,
    TIPO_CIERRE_SIN_ESCALAR,
    TIPO_CIERRE_SIN_INFORME,
    TIPO_COBERTURA_SUSTITUIDA,
    TIPO_CONSULTA_FALLIDA,
    TIPO_DATOS_SUSTITUIDOS,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_FALLO_DE_HOOK,
    TIPO_INFORME_REGISTRADO,
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
    reemplazar_entrada,
)
from due_diligence.informe import InformeRegistrado, huella_actual
from due_diligence.libro import Coincidencia, ConsultaRiesgo
from due_diligence.reglas import (
    MOTIVO_CATEGORIA_NO_DETERMINADA,
    MOTIVO_CONSULTA_AJENA,
    MOTIVO_FALTA_LISTAS,
    MOTIVO_HABILITAR_ALTO_RIESGO,
    MOTIVO_HABILITAR_CON_COINCIDENCIA,
    MOTIVO_RECOMENDACION,
    MOTIVO_REGISTRO_PRIMERO,
    MOTIVO_REGISTRO_REINTENTABLE,
    MOTIVO_SIN_COMERCIO,
    MOTIVO_SIN_INFORME,
    motivo_de_escalar,
)
from due_diligence.simulacion import (
    comercio_alto_riesgo,
    comercio_del_registro,
    comercios_parecidos,
    consulta,
    error_estructurado,
    respuesta_de_decision,
    respuesta_del_contrato,
    respuesta_listas,
    respuesta_registro,
    respuesta_riesgo,
)

REGISTRO = "mcp__pasarela__consultar_registro_mercantil"
MAX_CIERRES_IMPEDIDOS = configuracion.MAX_CIERRES_IMPEDIDOS
MAX_TURNOS_SEGURIDAD = configuracion.MAX_TURNOS_SEGURIDAD


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
    respuesta = respuesta_registro(comercio_alto_riesgo())
    estado.registrar_identificacion(respuesta)
    # Lo que hace el `Delegador` en producción (#9, hallazgo U1): la consulta válida queda en el
    # estado, de donde salen las fuentes admitidas (FR-004) y los conflictos.
    estado.agregar_consultas(
        [consulta(Frente.REGISTRO, {"identificador": "CO-TV-0001"}, respuesta)]
    )
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
    assert coordinador["PreToolUse"][0].matcher == DELEGAR


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


# ---------------------------------------------------------- regla I.2: coincidencias y escalamiento

INFORME = "mcp__pasarela__registrar_informe"
ESCALAR = "mcp__pasarela__escalar_a_cumplimiento"


def _coincidencia_de_persona(identificador="PE-0003"):
    return respuesta_listas(
        {"tipo": "persona", "nombre": "(ficticio)", "identificador": identificador}
    )


def _post_de(nombre, respuesta, entrada):
    return _post(respuesta, nombre=nombre, entrada=entrada)


FUENTE_REGISTRO = "Registro Mercantil Ficticio del Sur"
COMERCIO_VERIFICADO = {
    "identificador": "CO-TV-0001",
    "nombre": "Tienda Verde SAS",
    "verificado": True,
}
SIN_CONFLICTOS = {"resumen": "Sin conflictos entre las fuentes registrales.", "lista": []}


def _informe_de(recomendacion):
    """Un informe con la forma del #9 que cita la consulta del registro de `_caso_con_comercio`."""
    return {
        "comercio": dict(COMERCIO_VERIFICADO),
        "recomendacion": recomendacion,
        "hallazgos": {
            "registro": [
                {
                    "texto": "Una coincidencia en el registro.",
                    "fuente": FUENTE_REGISTRO,
                    "fecha": "2026-09-30",
                }
            ]
        },
        "conflictos": {"resumen": "Sin conflictos declarados.", "lista": []},
        "cobertura": "completa",
    }


def _rechazo(salida):
    """El error estructurado del deny de `registrar_informe` (#9, R3)."""
    return json.loads(_motivo(salida))


def test_el_subagente_de_listas_tiene_pre_post_y_failure_con_su_herramienta():
    _, _, hooks = _caso()
    listas = hooks.subagente(Frente.LISTAS)
    assert set(listas) == {"PreToolUse", "PostToolUse", "PostToolUseFailure"}
    for evento in listas:
        assert [m.matcher for m in listas[evento]] == [LISTAS]


def test_el_coordinador_tiene_los_hooks_de_delegar_informe_y_escalar():
    _, _, hooks = _caso()
    coordinador = hooks.coordinador()
    assert [m.matcher for m in coordinador["PreToolUse"]] == [DELEGAR, INFORME, ESCALAR]
    # #9: el `PostToolUse` y el `PostToolUseFailure` del informe confirman o descartan la huella.
    assert [m.matcher for m in coordinador["PostToolUse"]] == [ESCALAR, INFORME]
    assert [m.matcher for m in coordinador["PostToolUseFailure"]] == [ESCALAR, INFORME]


def test_una_consulta_de_listas_con_coincidencia_guarda_la_consulta_y_la_coincidencia():
    estado, _, hooks = _caso_con_comercio()
    entrada = {"tipo": "persona", "identificador": "PE-0003"}
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"),
        _post_de(LISTAS, _coincidencia_de_persona(), entrada),
    )
    (consulta,) = estado.libro.consultas_listas
    assert (consulta.tipo, consulta.identificador, consulta.resultado) == (
        "persona",
        "PE-0003",
        "coincidencias",
    )
    (coincidencia,) = estado.libro.coincidencias
    assert coincidencia.tipo == "persona" and coincidencia.lista == "Lista Restrictiva Ficticia A"
    assert coincidencia.fuente == "Lista Restrictiva Ficticia A" and coincidencia.fecha
    assert coincidencia.causa == "coincidencia_representante"


def test_una_consulta_de_listas_sin_coincidencias_no_deja_coincidencia_ni_requiere_escalar():
    estado, _, hooks = _caso_con_comercio()
    entrada = {"tipo": "comercio", "identificador": "CO-TV-0001"}
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"),
        _post_de(LISTAS, respuesta_listas(), entrada),
    )
    assert estado.libro.coincidencias == []
    (consulta,) = estado.libro.consultas_listas
    assert consulta.tipo == "comercio" and consulta.resultado == "sin_coincidencias"


def test_la_coincidencia_no_se_borra_aunque_el_registro_cambie_de_comercio():
    estado, _, hooks = _caso_con_comercio()
    entrada = {"tipo": "persona", "identificador": "PE-0003"}
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"),
        _post_de(LISTAS, _coincidencia_de_persona(), entrada),
    )
    estado.reiniciar_identificacion()
    estado.registrar_identificacion(
        respuesta_registro(comercio_del_registro("CO-TA-0002", "Taller Aurora SAS"))
    )
    assert len(estado.libro.coincidencias) == 1


def test_una_consulta_de_listas_con_error_no_entra_al_libro_y_deja_constancia():
    estado, eventos, hooks = _caso_con_comercio()
    error = {
        "error": True,
        "tipo": "datos_no_disponibles",
        "mensaje": "m",
        "reintentable": False,
        "obtenido": {},
    }
    entrada = _fallo(error, nombre=LISTAS)
    _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PostToolUseFailure"), entrada)
    assert estado.libro.consultas_listas == [] and estado.libro.coincidencias == []
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_CONSULTA_FALLIDA and evento.frente is Frente.LISTAS


def test_una_respuesta_ilegible_de_listas_no_entra_al_libro_y_deja_constancia():
    estado, eventos, hooks = _caso_con_comercio()
    entrada = {"tipo": "comercio", "identificador": "CO-TV-0001"}
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"),
        _post_de(LISTAS, "no es json", entrada),
    )
    assert estado.libro.consultas_listas == []
    assert eventos.eventos()[-1].tipo == TIPO_CONSULTA_FALLIDA


def _coincidencias_sin_detalle(hechos):
    """Una respuesta `coincidencias` de listas con los hechos dados."""
    respuesta = respuesta_listas({"tipo": "persona", "nombre": "(ficticio)"})
    respuesta["hechos"] = hechos
    return respuesta


HECHOS_AUSENTES_O_ILEGIBLES = [
    [],
    ["ilegible"],
    [None],
    [{"contenido": "ilegible", "metadatos": {"fuente": "F", "fecha": "2026-09-30"}}],
    [{"contenido": {"lista": "L"}, "metadatos": "ilegible"}],
]


@pytest.mark.parametrize("hechos", HECHOS_AUSENTES_O_ILEGIBLES)
def test_coincidencias_sin_hechos_legibles_cuentan_como_coincidencia_del_tipo_consultado(hechos):
    estado, eventos, hooks = _caso_con_comercio()
    respuesta = _coincidencias_sin_detalle(hechos)
    entrada = {"tipo": "persona", "identificador": "PE-0001"}
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"), _post_de(LISTAS, respuesta, entrada)
    )
    (consulta,) = estado.libro.consultas_listas
    assert consulta.resultado == "coincidencias"
    (coincidencia,) = estado.libro.coincidencias
    assert coincidencia.tipo == "persona" and coincidencia.causa == "coincidencia_representante"
    assert coincidencia.fuente == respuesta["metadatos"]["fuentes"][0]
    assert coincidencia.fecha == respuesta["metadatos"]["fecha"]
    assert eventos.eventos() == [] and estado.libro.fallo_de_hook is None


@pytest.mark.parametrize("hechos", [None, "ilegible", {"contenido": {}}])
def test_coincidencias_con_hechos_que_no_son_lista_es_una_respuesta_ilegible_que_no_cuenta(hechos):
    """Fuera del contrato (`hechos` no es una lista) la respuesta no se lee: no cuenta como consulta
    y deja `consulta_fallida`; habilitar sigue rechazado porque falta la consulta de listas."""
    estado, eventos, hooks = _caso_con_comercio()
    entrada = {"tipo": "persona", "identificador": "PE-0001"}
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"),
        _post_de(LISTAS, _coincidencias_sin_detalle(hechos), entrada),
    )
    assert estado.libro.consultas_listas == [] and estado.libro.coincidencias == []
    assert eventos.eventos()[-1].tipo == TIPO_CONSULTA_FALLIDA


def test_coincidencias_sin_hechos_ni_fuentes_tambien_cuentan_como_coincidencia():
    estado, _, hooks = _caso_con_comercio()
    entrada = {"tipo": "comercio", "identificador": "CO-TV-0001"}
    respuesta = {"resultado": "coincidencias", "hechos": [], "metadatos": {}}
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"), _post_de(LISTAS, respuesta, entrada)
    )
    (coincidencia,) = estado.libro.coincidencias
    assert coincidencia.causa == "coincidencia_comercio"
    assert (coincidencia.fuente, coincidencia.fecha) == ("", "")


def test_un_hecho_ilegible_junto_a_uno_legible_deja_las_dos_coincidencias():
    estado, _, hooks = _caso_con_comercio()
    respuesta = _coincidencia_de_persona("PE-0001")
    respuesta["hechos"].append("ilegible")
    entrada = {"tipo": "persona", "identificador": "PE-0001"}
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"), _post_de(LISTAS, respuesta, entrada)
    )
    legible, sin_detalle = estado.libro.coincidencias
    assert legible.lista == "Lista Restrictiva Ficticia A" and sin_detalle.lista == ""


@pytest.mark.parametrize("resultado", ["parcial", "", None, 3, ...])
def test_un_resultado_de_listas_que_no_es_del_contrato_no_cuenta_y_deja_consulta_fallida(
    resultado,
):
    estado, eventos, hooks = _caso_con_comercio()
    respuesta = respuesta_listas()
    if resultado is ...:
        del respuesta["resultado"]
    else:
        respuesta["resultado"] = resultado
    entrada = {"tipo": "comercio", "identificador": "CO-TV-0001"}
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"), _post_de(LISTAS, respuesta, entrada)
    )
    assert estado.libro.consultas_listas == [] and estado.libro.coincidencias == []
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_CONSULTA_FALLIDA and evento.frente is Frente.LISTAS
    assert "CO-TV-0001" not in evento.detalle


def test_con_coincidencias_sin_hechos_se_rechaza_habilitar_y_se_exige_escalar():
    estado, eventos, hooks = _caso_con_comercio()
    listas = _hook(hooks.subagente(Frente.LISTAS), "PostToolUse")
    _ejecutar(
        listas,
        _post_de(LISTAS, respuesta_listas(), {"tipo": "comercio", "identificador": "CO-TV-0001"}),
    )
    _ejecutar(
        listas,
        _post_de(
            LISTAS, _coincidencias_sin_detalle([]), {"tipo": "persona", "identificador": "PE-0001"}
        ),
    )
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))

    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("habilitar")))
    assert _es_denegacion(salida)
    assert "no se puede recomendar habilitar" in _motivo(salida)
    assert "aún no se ha escalado" in _motivo(salida)
    assert _es_bloqueo(_ejecutar(_stop(hooks), _fin_de_turno()))

    escalado = respuesta_de_decision("caso_escalado", "ESC-0001")
    _ejecutar(_hook(hooks.coordinador(), "PostToolUse"), _post_de(ESCALAR, escalado, {}))
    informe = _pre(INFORME, _informe_de("decide_cumplimiento"))
    antes = len(eventos.eventos())  # el mismo test registró antes un bloqueo legítimo
    salida = _ejecutar(_hook_del_informe(hooks), informe)
    _comprobar_informe_aceptado(salida, informe["tool_input"], estado)
    assert [e.tipo for e in eventos.eventos()[antes:]] == [
        TIPO_COBERTURA_SUSTITUIDA,
        TIPO_DATOS_SUSTITUIDOS,
    ]
    # #9: la pasarela acepta y el `PostToolUse` confirma la huella; sin eso no hay informe vigente.
    registrado = respuesta_de_decision("informe_registrado", "INF-0001")
    _ejecutar(_post_del_informe(hooks), _post_de(INFORME, registrado, informe["tool_input"]))
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()


def test_un_resultado_de_listas_fuera_del_contrato_no_cuenta_para_habilitar():
    estado, _, hooks = _caso_con_comercio()
    listas = _hook(hooks.subagente(Frente.LISTAS), "PostToolUse")
    _ejecutar(
        listas,
        _post_de(LISTAS, respuesta_listas(), {"tipo": "comercio", "identificador": "CO-TV-0001"}),
    )
    parcial = respuesta_listas()
    parcial["resultado"] = "parcial"
    _ejecutar(listas, _post_de(LISTAS, parcial, {"tipo": "persona", "identificador": "PE-0001"}))
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))

    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("habilitar")))
    assert _es_denegacion(salida) and MOTIVO_FALTA_LISTAS in _motivo(salida)


def test_un_escalamiento_exitoso_guarda_la_instantanea_de_las_causas_y_deja_el_evento():
    estado, eventos, hooks = _caso_con_comercio()
    _ejecutar(
        _hook(hooks.subagente(Frente.LISTAS), "PostToolUse"),
        _post_de(
            LISTAS, _coincidencia_de_persona(), {"tipo": "persona", "identificador": "PE-0003"}
        ),
    )
    escalado = respuesta_de_decision("caso_escalado", "ESC-0001")
    _ejecutar(_hook(hooks.coordinador(), "PostToolUse"), _post_de(ESCALAR, escalado, {}))
    assert estado.libro.escalamientos == [frozenset({"coincidencia_representante"})]
    evento = eventos.eventos()[-1]
    assert evento.tipo == TIPO_ESCALAMIENTO_REGISTRADO and evento.frente is None
    assert "representante legal" in evento.detalle and "PE-0003" not in evento.detalle


def test_un_escalamiento_con_error_o_con_otro_resultado_no_cuenta():
    estado, eventos, hooks = _caso_con_comercio()
    error = error_estructurado("campos_obligatorios_ausentes", False)
    _ejecutar(_hook(hooks.coordinador(), "PostToolUseFailure"), _fallo(error, nombre=ESCALAR))
    otro = respuesta_de_decision("informe_registrado", "INF-0001")
    _ejecutar(_hook(hooks.coordinador(), "PostToolUse"), _post_de(ESCALAR, otro, {}))
    assert estado.libro.escalamientos == []
    assert [e.tipo for e in eventos.eventos()] == [TIPO_CONSULTA_FALLIDA, TIPO_CONSULTA_FALLIDA]


def _hook_del_informe(hooks):
    return hooks.coordinador()["PreToolUse"][1].hooks[0]


def _post_del_informe(hooks):
    return hooks.coordinador()["PostToolUse"][1].hooks[0]


def _fallo_del_informe(hooks):
    return hooks.coordinador()["PostToolUseFailure"][1].hooks[0]


def _comprobar_informe_aceptado(salida, entrada, estado, comercio=None, conflictos=None):
    """Un informe aceptado (#8, T021; #9, T037): igualdad exacta sobre la entrada completa.

    No es denegación; `permissionDecision` es `allow`; `hallazgos` y `recomendacion` llegan
    intactos; `comercio`, `conflictos` y `cobertura` son los del código, escritos aquí salvo la
    cobertura, que ya comprobaba el #8 con su cálculo.
    """
    assert not _es_denegacion(salida)
    especifica = salida["hookSpecificOutput"]
    assert especifica["permissionDecision"] == "allow"
    assert especifica["updatedInput"] == {
        "comercio": comercio or COMERCIO_VERIFICADO,
        "recomendacion": entrada["recomendacion"],
        "hallazgos": entrada["hallazgos"],
        "conflictos": conflictos or SIN_CONFLICTOS,
        "cobertura": calcular_cobertura(estado).lineas(),
    }


def test_el_hook_del_informe_deniega_habilitar_con_coincidencia_con_la_regla_i2():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))  # solo I.2
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("habilitar")))
    assert _es_denegacion(salida)
    rechazo = _rechazo(salida)
    assert rechazo["motivos"] == [
        {"regla": "I.2", "texto": motivo_de_escalar({"coincidencia_representante"})},
        {"regla": "I.2", "texto": MOTIVO_HABILITAR_CON_COINCIDENCIA},
        {"regla": "I.2", "texto": MOTIVO_FALTA_LISTAS},
    ]
    assert rechazo["problemas"] == []
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_BLOQUEO_REGLA and evento.regla == "I.2"


def test_el_hook_del_informe_permite_no_habilitar_si_el_caso_esta_escalado():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    estado.libro.escalamientos.append(frozenset({"coincidencia_representante"}))
    for recomendacion in ("no_habilitar", "decide_cumplimiento"):
        entrada = _informe_de(recomendacion)
        antes = len(eventos.eventos())
        salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
        _comprobar_informe_aceptado(salida, entrada, estado)
        assert [e.tipo for e in eventos.eventos()[antes:]] == [
            TIPO_COBERTURA_SUSTITUIDA,
            TIPO_DATOS_SUSTITUIDOS,
        ]
    assert not any(e.tipo == TIPO_BLOQUEO_REGLA for e in eventos.eventos())


def test_el_hook_del_informe_deniega_una_recomendacion_fuera_del_conjunto():
    _, eventos, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("aprobar")))
    assert _es_denegacion(salida)
    assert _rechazo(salida)["motivos"] == [{"regla": None, "texto": MOTIVO_RECOMENDACION}]
    assert _rechazo(salida)["problemas"] == []
    assert eventos.eventos()[0].regla is None


@pytest.mark.parametrize("entrada", [None, "informe", [], {}, {"recomendacion": 3}])
def test_el_hook_del_informe_con_una_entrada_malformada_deniega(entrada):
    _, _, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    assert _es_denegacion(salida)


def test_con_el_libro_sellado_el_hook_del_informe_deniega():
    estado, _, hooks = _caso_con_comercio()
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    assert _es_denegacion(salida) and _motivo(salida) == SELLADO


def test_el_hook_del_informe_si_evaluar_informe_lanza_una_excepcion_deniega(monkeypatch):
    estado, _, hooks = _caso_con_comercio()

    def roto(_estado, _entrada):
        raise RuntimeError("detalle interno")

    monkeypatch.setattr(modulo_hooks, "evaluar_informe", roto)
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    assert _es_denegacion(salida) and estado.libro.fallo_de_hook


# ------------------------------------------------------------------ regla I.3: riesgo de categoría

RIESGO = "mcp__pasarela__consultar_riesgo_categoria"


def test_el_subagente_de_categoria_tiene_post_y_failure_con_su_herramienta():
    _, _, hooks = _caso()
    categoria = hooks.subagente(Frente.CATEGORIA)
    assert set(categoria) == {"PostToolUse", "PostToolUseFailure"}
    for evento in categoria:
        assert [m.matcher for m in categoria[evento]] == [RIESGO]


def test_el_subagente_de_noticias_no_tiene_hooks():
    # Una mención en noticias no es una coincidencia en listas (principio IV): no vigila nada.
    _, _, hooks = _caso()
    assert hooks.subagente(Frente.NOTICIAS) == {}


@pytest.mark.parametrize(
    ("categoria", "nivel"),
    [("suplementos dietarios", "alto"), ("talleres", "bajo"), ("comercio de calzado", "medio")],
)
def test_una_categoria_conocida_guarda_su_nivel(categoria, nivel):
    estado, eventos, hooks = _caso()
    entrada = {"categoria": categoria}
    _ejecutar(
        _hook(hooks.subagente(Frente.CATEGORIA), "PostToolUse"),
        _post_de(RIESGO, respuesta_riesgo(categoria, nivel), entrada),
    )
    assert [(c.categoria, c.nivel) for c in estado.libro.consultas_riesgo] == [(categoria, nivel)]
    assert eventos.eventos() == []


def test_una_categoria_desconocida_entra_sin_nivel_y_con_la_categoria_pedida():
    estado, _, hooks = _caso()
    _ejecutar(
        _hook(hooks.subagente(Frente.CATEGORIA), "PostToolUse"),
        _post_de(RIESGO, respuesta_riesgo("algo raro", None), {"categoria": "algo raro"}),
    )
    assert [(c.categoria, c.nivel) for c in estado.libro.consultas_riesgo] == [("algo raro", None)]


def test_un_nivel_que_no_es_del_catalogo_cuenta_como_sin_nivel():
    estado, _, hooks = _caso()
    respuesta = respuesta_riesgo("talleres", "intermedio")
    _ejecutar(
        _hook(hooks.subagente(Frente.CATEGORIA), "PostToolUse"),
        _post_de(RIESGO, respuesta, {"categoria": "talleres"}),
    )
    assert [(c.categoria, c.nivel) for c in estado.libro.consultas_riesgo] == [("talleres", None)]


def test_una_consulta_de_riesgo_con_error_no_entra_al_libro_y_deja_constancia():
    estado, eventos, hooks = _caso()
    error = error_estructurado("datos_no_disponibles", False)
    _ejecutar(
        _hook(hooks.subagente(Frente.CATEGORIA), "PostToolUseFailure"), _fallo(error, nombre=RIESGO)
    )
    assert estado.libro.consultas_riesgo == []
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_CONSULTA_FALLIDA and evento.frente is Frente.CATEGORIA


def test_una_respuesta_ilegible_de_riesgo_no_entra_al_libro_y_deja_constancia():
    estado, eventos, hooks = _caso()
    _ejecutar(
        _hook(hooks.subagente(Frente.CATEGORIA), "PostToolUse"),
        _post_de(RIESGO, "no es json", {"categoria": "talleres"}),
    )
    assert estado.libro.consultas_riesgo == []
    assert eventos.eventos()[0].tipo == TIPO_CONSULTA_FALLIDA


def test_el_hook_del_informe_deniega_habilitar_en_alto_riesgo_con_la_regla_i3():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("suplementos dietarios", "alto"))
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("habilitar")))
    assert _es_denegacion(salida)
    assert _rechazo(salida)["motivos"] == [
        {"regla": "I.3", "texto": motivo_de_escalar({"alto_riesgo"})},
        {"regla": "I.3", "texto": MOTIVO_HABILITAR_ALTO_RIESGO},
        {"regla": "I.2", "texto": MOTIVO_FALTA_LISTAS},
    ]
    assert eventos.eventos()[-1].regla == "I.2, I.3"


def test_el_hook_del_informe_deniega_habilitar_sin_categoria_determinada():
    estado, eventos, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("habilitar")))
    assert _rechazo(salida)["motivos"] == [
        {"regla": "I.3", "texto": MOTIVO_CATEGORIA_NO_DETERMINADA},
        {"regla": "I.2", "texto": MOTIVO_FALTA_LISTAS},
    ]
    assert eventos.eventos()[-1].regla == "I.2, I.3"


# ------------------------------------------------------------------ cierre garantizado (FR-007, R3)


def _stop(hooks):
    return hooks.coordinador()["Stop"][0].hooks[0]


def _fin_de_turno(activo=False, mensaje="listo"):
    return {
        "hook_event_name": "Stop",
        "stop_hook_active": activo,
        "last_assistant_message": mensaje,
    }


def _es_bloqueo(salida):
    return salida.get("decision") == "block"


def _con_informe_vigente(estado):
    """Un informe registrado con la huella de ahora (#9, T037): los tests del #7 sobre el `Stop`
    siguen probando solo el escalamiento, con sus mismas igualdades exactas."""
    estado.informes.append(
        InformeRegistrado("INF-0001", "no_habilitar", False, huella_actual(estado))
    )


def test_el_coordinador_tiene_el_stop_sin_matcher_y_ningun_subagente_lo_tiene():
    _, _, hooks = _caso()
    assert hooks.coordinador()["Stop"][0].matcher is None
    for frente in Frente:
        assert "Stop" not in hooks.subagente(frente)


def test_un_caso_que_no_requiere_escalamiento_puede_terminar():
    estado, eventos, hooks = _caso_con_comercio()
    _con_informe_vigente(estado)
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert eventos.eventos() == []


def test_un_caso_con_el_escalamiento_cubierto_puede_terminar():
    estado, _, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    estado.libro.escalamientos.append(frozenset({"coincidencia_representante"}))
    _con_informe_vigente(estado)
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()


def test_un_caso_que_requiere_escalamiento_sin_escalar_no_puede_terminar():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    _con_informe_vigente(estado)
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida)
    assert "por: coincidencia del representante legal en listas restrictivas" in salida["reason"]
    assert estado.libro.cierres_impedidos == 1
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_CIERRE_IMPEDIDO and evento.regla == "I.2"
    assert evento.frente is None and evento.detalle == salida["reason"]


def test_el_cierre_por_alto_riesgo_lleva_la_regla_i3_y_con_ambas_causas_i2_i3():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("apuestas", "alto"))
    _ejecutar(_stop(hooks), _fin_de_turno())
    assert eventos.eventos()[-1].regla == "I.3"
    estado.libro.coincidencias.append(Coincidencia("comercio", "L", "F", "2026-09-30"))
    _ejecutar(_stop(hooks), _fin_de_turno())
    assert eventos.eventos()[-1].regla == "I.2, I.3"


def test_el_stop_no_usa_stop_hook_active_para_decidir():
    estado, _, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    assert _es_bloqueo(_ejecutar(_stop(hooks), _fin_de_turno(activo=False)))
    assert _es_bloqueo(_ejecutar(_stop(hooks), _fin_de_turno(activo=True)))
    assert estado.libro.cierres_impedidos == 2  # cuenta el contador del libro, no el indicador


def test_agotadas_las_devoluciones_el_stop_deja_terminar_y_marca_cierre_sin_escalar():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    _con_informe_vigente(estado)
    for _ in range(MAX_CIERRES_IMPEDIDOS):
        assert _es_bloqueo(_ejecutar(_stop(hooks), _fin_de_turno(activo=True)))
    assert estado.cierre_sin_escalar is False
    siguiente = _ejecutar(_stop(hooks), _fin_de_turno(activo=True))
    assert siguiente == permitir()
    assert estado.cierre_sin_escalar is True
    assert estado.libro.cierres_impedidos == MAX_CIERRES_IMPEDIDOS
    ultimo = eventos.eventos()[-1]
    assert ultimo.tipo == TIPO_CIERRE_SIN_ESCALAR and ultimo.regla == "I.2"
    assert "sin el escalamiento obligatorio" in ultimo.detalle
    assert [e.tipo for e in eventos.eventos()].count(TIPO_CIERRE_IMPEDIDO) == MAX_CIERRES_IMPEDIDOS


def test_el_limite_de_devoluciones_es_la_constante_real_y_menor_que_el_de_turnos():
    assert MAX_CIERRES_IMPEDIDOS == 3
    assert MAX_CIERRES_IMPEDIDOS < MAX_TURNOS_SEGURIDAD


def test_un_stop_que_lanza_una_excepcion_bloquea_y_cuenta_hasta_el_limite(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()

    def roto(_estado):
        raise RuntimeError("detalle interno")

    monkeypatch.setattr(modulo_hooks, "evaluar_cierre", roto)
    for _ in range(MAX_CIERRES_IMPEDIDOS):
        salida = _ejecutar(_stop(hooks), _fin_de_turno())
        assert _es_bloqueo(salida) and "detalle interno" not in salida["reason"]
    assert estado.libro.cierres_impedidos == MAX_CIERRES_IMPEDIDOS
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()  # el límite también vale aquí
    assert estado.cierre_sin_escalar is True
    assert estado.libro.fallo_de_hook


def test_con_el_libro_sellado_y_escalamiento_requerido_el_cierre_se_bloquea_igual():
    estado, _, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    assert _es_bloqueo(_ejecutar(_stop(hooks), _fin_de_turno()))


def test_el_motivo_del_cierre_no_repite_nada_consultado():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("comercio", "L", "F", "2026-09-30"))
    salida = _ejecutar(_stop(hooks), _fin_de_turno(mensaje="Tienda Verde SAS: listo"))
    texto = salida["reason"] + eventos.eventos()[-1].detalle
    for dato in ("CO-TV-0001", "Tienda Verde", "PE-0001", "Lucía"):
        assert dato not in texto


# ------------------------------------------------- cobertura registrada (#8, R1, R6, FR-011)

TEXTO_INTERNO = "TEXTO-INTERNO-FICTICIO"
COBERTURA_NO_CALCULADA = "No se pudo calcular la cobertura; debe tratarse como incompleta."
COMBINACIONES = list(itertools.product(list(Situacion), repeat=len(Frente)))


def _hook_del_escalamiento(hooks):
    return hooks.coordinador()["PreToolUse"][2].hooks[0]


def _escalamiento():
    return {
        "comercio": {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS"},
        "hallazgos": {},
        "cobertura": "completa",
        "causa_escalamiento": "alto riesgo",
        "accion_recomendada": "revisar",
    }


def _forzar(estado, situaciones):
    for frente, situacion in zip(Frente, situaciones, strict=True):
        estado._situaciones[frente] = situacion


def _sustituida(salida):
    return salida["hookSpecificOutput"]["updatedInput"]


def test_reemplazar_entrada_tiene_la_forma_medida_en_r1():
    entrada = {"a": 1}
    assert reemplazar_entrada(entrada) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": entrada,
        }
    }
    salida = typing.cast(sdk.SyncHookJSONOutput, reemplazar_entrada(entrada))
    assert salida["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def test_el_informe_aceptado_sustituye_la_cobertura_y_lo_dice_sin_decir_registrada():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))
    entrada = _informe_de("no_habilitar")
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(salida, entrada, estado)
    evento, datos = eventos.eventos()
    assert datos.tipo == TIPO_DATOS_SUSTITUIDOS
    assert evento.tipo == TIPO_COBERTURA_SUSTITUIDA and evento.frente is None
    assert "registrar_informe" in evento.detalle
    assert "distinta" in evento.detalle  # el modelo declaró «completa»
    assert "registrad" not in evento.detalle  # se emite antes de que la pasarela acepte
    for dato in ("CO-TV-0001", "Tienda Verde"):
        assert dato not in evento.detalle


def test_si_la_cobertura_declarada_coincide_el_evento_no_dice_que_era_distinta():
    estado, eventos, hooks = _caso_con_comercio()
    entrada = {**_informe_de("no_habilitar"), "cobertura": calcular_cobertura(estado).lineas()}
    _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    evento, datos = eventos.eventos()
    assert datos.tipo == TIPO_DATOS_SUSTITUIDOS
    assert evento.tipo == TIPO_COBERTURA_SUSTITUIDA and "distinta" not in evento.detalle


@pytest.mark.parametrize(
    "preparar",
    ["sellado", "regla", "malformada"],
)
def test_cuando_el_informe_se_deniega_no_se_registra_cobertura_sustituida(preparar):
    estado, eventos, hooks = _caso_con_comercio()
    entrada = _informe_de("no_habilitar")
    if preparar == "sellado":
        estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    elif preparar == "regla":
        # habilitar sin la categoría determinada ni la consulta de listas: I.3 e I.2
        entrada = _informe_de("habilitar")
    else:
        entrada = "no es un objeto"  # la rechaza la regla del #7 (MOTIVO_ENTRADA_INFORME)
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    assert _es_denegacion(salida)
    assert not any(e.tipo == TIPO_COBERTURA_SUSTITUIDA for e in eventos.eventos())


def test_una_excepcion_calculando_la_cobertura_deniega_el_informe(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()

    def roto(estado):
        raise RuntimeError(TEXTO_INTERNO)

    monkeypatch.setattr(modulo_hooks, "calcular_cobertura", roto)
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    assert _es_denegacion(salida) and _motivo(salida) == modulo_hooks.MOTIVO_FALLO_DE_HOOK
    assert estado.libro.fallo_de_hook is not None
    assert not any(e.tipo == TIPO_COBERTURA_SUSTITUIDA for e in eventos.eventos())
    assert all(TEXTO_INTERNO not in e.detalle for e in eventos.eventos())


def test_el_escalamiento_sustituye_la_cobertura_aunque_el_libro_este_sellado():
    for sellado in (False, True):
        estado, eventos, hooks = _caso_con_comercio()
        if sellado:
            estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
        entrada = _escalamiento()
        salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, entrada))
        assert not _es_denegacion(salida)
        assert salida["hookSpecificOutput"]["permissionDecision"] == "allow"
        sustituida = _sustituida(salida)
        assert {k: v for k, v in sustituida.items() if k != "cobertura"} == {
            k: v for k, v in entrada.items() if k != "cobertura"
        }
        assert sustituida["cobertura"] == calcular_cobertura(estado).lineas()
        (evento,) = eventos.eventos()
        assert evento.tipo == TIPO_COBERTURA_SUSTITUIDA
        assert "escalar_a_cumplimiento" in evento.detalle


def test_un_escalamiento_que_no_es_un_objeto_pasa_sin_cambios():
    _, eventos, hooks = _caso_con_comercio()
    assert _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, "texto")) == permitir()
    assert eventos.eventos() == []


def test_una_excepcion_en_el_escalamiento_lo_deja_pasar_con_el_texto_fijo_y_sella(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()

    def roto(estado):
        raise RuntimeError(TEXTO_INTERNO)

    monkeypatch.setattr(modulo_hooks, "calcular_cobertura", roto)
    entrada = _escalamiento()
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, entrada))

    assert not _es_denegacion(salida)
    assert salida["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert _sustituida(salida) == {**entrada, "cobertura": [COBERTURA_NO_CALCULADA]}
    assert modulo_hooks.COBERTURA_NO_CALCULADA == COBERTURA_NO_CALCULADA
    assert estado.libro.fallo_de_hook is not None
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_FALLO_DE_HOOK and TEXTO_INTERNO not in evento.detalle
    # Con el sello, el informe ya no se acepta (riesgo residual 6, lo resuelve el #9).
    informe = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    assert _es_denegacion(informe) and _motivo(informe) == SELLADO


def test_ningun_caso_probado_del_escalamiento_deniega(monkeypatch):
    salidas = []
    for entrada in (_escalamiento(), "texto", None, 3):
        _, _, hooks = _caso_con_comercio()
        salidas.append(_ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, entrada)))

    def roto(estado):
        raise RuntimeError(TEXTO_INTERNO)

    monkeypatch.setattr(modulo_hooks, "calcular_cobertura", roto)
    for entrada in (_escalamiento(), "texto"):
        _, _, hooks = _caso_con_comercio()
        salidas.append(_ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, entrada)))
    assert not any(_es_denegacion(s) for s in salidas)


def test_el_coordinador_registra_ocho_hooks():
    # Seis hasta el #8; el #9 añade el `PostToolUse` y el `PostToolUseFailure` del informe.
    _, _, hooks = _caso()
    coordinador = hooks.coordinador()
    assert sum(len(m.hooks) for lista in coordinador.values() for m in lista) == 8


@pytest.mark.parametrize("situaciones", COMBINACIONES)
def test_los_dos_canales_ponen_exactamente_la_cobertura_calculada(situaciones):
    # G1 del análisis (SC-003): en las 625 combinaciones, lo que llega a la pasarela es la
    # cobertura del código y ninguna línea declara cubierto un frente que no terminó.
    estado, _, hooks = _caso()
    _forzar(estado, situaciones)
    # #9: el informe necesita un comercio (aquí, el pedido) y una fuente consultada (FR-004).
    estado.comercio_pedido = {"identificador": "CO-TV-0001", "nombre": None}
    estado.agregar_consultas([consulta(Frente.REGISTRO)])
    esperada = calcular_cobertura(estado).lineas()
    informe = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("decide_cumplimiento")))
    escalamiento = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento()))
    for salida in (informe, escalamiento):
        cobertura = _sustituida(salida)["cobertura"]
        assert cobertura == esperada
        for frente, situacion in zip(Frente, situaciones, strict=True):
            linea = cobertura[1 + list(Frente).index(frente)]
            if situacion is not Situacion.TERMINADO:
                assert linea.startswith(f"{frente.value}: no cubierto")


# ------------------------------------------- #9: esquema, fuentes, comercio y conflictos (US1, US2)


def _caso_g():
    """Un caso con `CO-RF-0006` identificado y sus dos fuentes registrales (caso g)."""
    from servidor_mcp import datos
    from servidor_mcp.registro import consultar_registro_mercantil

    datos.limpiar_cache()
    respuesta = consultar_registro_mercantil(identificador="CO-RF-0006").structured_content
    estado, eventos, hooks = _caso()
    _registro_terminado(estado)
    estado.registrar_identificacion(respuesta)
    estado.agregar_consultas(
        [consulta(Frente.REGISTRO, {"identificador": "CO-RF-0006"}, respuesta)]
    )
    return estado, eventos, hooks


CONFLICTO_G = {
    "resumen": "1 conflicto entre las fuentes registrales.",
    "lista": [
        {
            "dato": "fecha_constitucion",
            "valores": [
                {"valor": "2016-03-14", "fuente": FUENTE_REGISTRO, "fecha": "2026-09-30"},
                {
                    "valor": "2017-09-02",
                    "fuente": "Registro Único Ficticio de Empresas",
                    "fecha": "2026-09-28",
                },
            ],
        }
    ],
}


def test_el_rechazo_del_informe_es_un_error_estructurado_con_reglas_y_problemas_juntos():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))
    entrada = _informe_de("habilitar")
    del entrada["hallazgos"]["registro"][0]["fuente"]
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    rechazo = _rechazo(salida)
    assert set(rechazo) == {"error", "tipo", "mensaje", "reintentable", "motivos", "problemas"}
    assert rechazo["error"] is True
    assert rechazo["tipo"] == "informe_rechazado"
    assert rechazo["reintentable"] is False
    assert [m["regla"] for m in rechazo["motivos"]] == ["I.2", "I.2", "I.2"]
    assert rechazo["problemas"] == [
        {"ruta": "hallazgos.registro[0].fuente", "texto": "Debe ser un texto no vacío."}
    ]
    assert "hallazgos.registro[0].fuente" in rechazo["mensaje"]
    assert rechazo["mensaje"].endswith("Corrige y vuelve a registrarlo.")
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_BLOQUEO_REGLA and evento.regla == "I.2, I.4"


def test_una_afirmacion_con_una_fuente_no_consultada_se_rechaza_con_la_regla_i4():
    estado, eventos, hooks = _caso_con_comercio()
    entrada = _informe_de("decide_cumplimiento")
    entrada["hallazgos"]["listas"] = [
        {"texto": "Sin coincidencias.", "fuente": FUENTE_REGISTRO, "fecha": "2026-09-30"}
    ]
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    rechazo = _rechazo(salida)
    assert rechazo["motivos"] == []
    assert rechazo["problemas"] == [
        {
            "ruta": "hallazgos.listas[0].fuente",
            "texto": "La fuente no es ninguna de las consultadas para listas.",
        }
    ]
    (evento,) = eventos.eventos()
    assert evento.regla == "I.4"
    assert not any(e.tipo == TIPO_COBERTURA_SUSTITUIDA for e in eventos.eventos())


def test_un_informe_valido_sin_ninguna_afirmacion_se_acepta():
    # I.5: si nada quedó cubierto, el informe se entrega igual.
    estado, _, hooks = _caso_con_comercio()
    entrada = {**_informe_de("decide_cumplimiento"), "hallazgos": {}}
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(salida, entrada, estado)


def test_el_comercio_declarado_distinto_se_sustituye_y_el_evento_lo_dice_sin_datos():
    estado, eventos, hooks = _caso_con_comercio()
    entrada = _informe_de("decide_cumplimiento")
    entrada["comercio"] = {"identificador": "CO-XX-9999", "nombre": "Otro", "verificado": True}
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(salida, entrada, estado)
    datos = eventos.eventos()[-1]
    assert datos.tipo == TIPO_DATOS_SUSTITUIDOS
    assert "comercio verificado" in datos.detalle
    assert "distinto" in datos.detalle and "comercio" in datos.detalle
    for dato in ("CO-TV-0001", "Tienda Verde", "CO-XX-9999", "Otro"):
        assert dato not in datos.detalle


def test_sin_comercio_identificado_va_el_pedido_sin_verificar():
    estado, _, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Taller Aurora SAS"}
    estado.agregar_consultas([consulta(Frente.REGISTRO)])
    entrada = _informe_de("decide_cumplimiento")
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(
        salida,
        entrada,
        estado,
        comercio={"identificador": None, "nombre": "Taller Aurora SAS", "verificado": False},
        conflictos={
            "resumen": "No se pudieron comparar las fuentes registrales: el registro no respondió.",
            "lista": [],
        },
    )


def test_sin_comercio_identificado_ni_pedido_el_informe_se_rechaza():
    _, eventos, hooks = _caso()
    salida = _ejecutar(
        _hook_del_informe(hooks), _pre(INFORME, {**_informe_de("no_habilitar"), "hallazgos": {}})
    )
    assert _rechazo(salida)["motivos"] == [
        {"regla": None, "texto": modulo_hooks.MOTIVO_SIN_COMERCIO_INFORME}
    ]
    assert eventos.eventos()[-1].tipo == TIPO_BLOQUEO_REGLA


def test_caso_g_los_conflictos_del_informe_son_los_del_codigo():
    estado, eventos, hooks = _caso_g()
    comercio_g = {
        "identificador": "CO-RF-0006",
        "nombre": "Ferretería Río Fino SAS",
        "verificado": True,
    }
    for declarados in (
        {"resumen": "Sin conflictos declarados.", "lista": []},  # omite el conflicto
        {  # inventa uno que el código no detecta
            "resumen": "1 conflicto.",
            "lista": [
                {
                    "dato": "estado",
                    "valores": [
                        {"valor": "activo", "fuente": "A", "fecha": "2026-09-30"},
                        {"valor": "inactivo", "fuente": "B", "fecha": "2026-09-30"},
                    ],
                }
            ],
        },
    ):
        entrada = {**_informe_de("no_habilitar"), "conflictos": declarados}
        salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
        _comprobar_informe_aceptado(
            salida, entrada, estado, comercio=comercio_g, conflictos=CONFLICTO_G
        )
    datos = [e for e in eventos.eventos() if e.tipo == TIPO_DATOS_SUSTITUIDOS]
    assert all("1 conflicto" in e.detalle for e in datos)
    assert all("2016" not in e.detalle and "Ferretería" not in e.detalle for e in datos)


def test_si_calcular_conflictos_lanza_el_informe_se_deniega_y_se_sella(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()

    def roto(estado):
        raise RuntimeError(TEXTO_INTERNO)

    monkeypatch.setattr(modulo_hooks, "calcular_conflictos", roto)
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    assert _es_denegacion(salida) and _motivo(salida) == modulo_hooks.MOTIVO_FALLO_DE_HOOK
    assert estado.libro.fallo_de_hook is not None
    assert all(TEXTO_INTERNO not in e.detalle for e in eventos.eventos())


# ------------------------------------------- #9: informe obligatorio y vigente (US3, R7, R8)


def _aceptar_informe(
    hooks, recomendacion="no_habilitar", tool_use_id="t1", identificador="INF-0001"
):
    """El `PreToolUse` acepta y la pasarela registra: el `PostToolUse` confirma la huella."""
    entrada = {**_pre(INFORME, _informe_de(recomendacion)), "tool_use_id": tool_use_id}
    salida = _ejecutar(_hook_del_informe(hooks), entrada)
    respuesta = respuesta_de_decision("informe_registrado", identificador)
    post = {**_post_de(INFORME, respuesta, _sustituida(salida)), "tool_use_id": tool_use_id}
    _ejecutar(_post_del_informe(hooks), post)
    return salida


def test_el_pretooluse_deja_la_huella_pendiente_y_el_post_la_confirma():
    estado, eventos, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    assert not _es_denegacion(salida)
    huella, recomendacion, minimo = estado.informes_pendientes["t1"]
    assert huella == huella_actual(estado)
    assert (recomendacion, minimo) == ("no_habilitar", False)
    assert estado.informes == []
    respuesta = respuesta_de_decision("informe_registrado", "INF-0007")
    _ejecutar(_post_del_informe(hooks), _post_de(INFORME, respuesta, _sustituida(salida)))
    assert estado.informes_pendientes == {}
    assert estado.informes == [InformeRegistrado("INF-0007", "no_habilitar", False, huella)]
    registrado = eventos.eventos()[-1]
    assert registrado.tipo == TIPO_INFORME_REGISTRADO
    assert registrado.detalle == (
        "Informe INF-0007 registrado; recomendación: no_habilitar; cobertura incompleta, "
        "1 de 4 frentes; sin conflictos."
    )


def test_un_post_con_error_descarta_la_pendiente_sin_evento_de_informe():
    estado, eventos, hooks = _caso_con_comercio()
    _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    error = error_estructurado("entrada_invalida", False)
    _ejecutar(_fallo_del_informe(hooks), _fallo(error, nombre=INFORME))
    assert estado.informes_pendientes == {} and estado.informes == []
    assert TIPO_INFORME_REGISTRADO not in [e.tipo for e in eventos.eventos()]
    assert eventos.eventos()[-1].tipo == TIPO_CONSULTA_FALLIDA


def test_un_deny_no_deja_pendiente():
    estado, _, hooks = _caso_con_comercio()
    _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("aprobar")))
    assert estado.informes_pendientes == {}


def test_la_huella_pendiente_es_la_de_los_datos_sustituidos_y_no_se_recalcula_en_el_post():
    estado, _, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    antes = estado.informes_pendientes["t1"][0]
    # Entre los dos hooks termina otro frente: la huella confirmada sigue siendo la del Pre (R7).
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.TERMINADO)
    respuesta = respuesta_de_decision("informe_registrado", "INF-0001")
    _ejecutar(_post_del_informe(hooks), _post_de(INFORME, respuesta, _sustituida(salida)))
    assert estado.informes[-1].huella == antes != huella_actual(estado)


def test_sin_informe_con_comercio_identificado_el_cierre_se_impide():
    estado, eventos, hooks = _caso_con_comercio()
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida) and salida["reason"] == MOTIVO_SIN_INFORME
    assert MOTIVO_SIN_INFORME == (
        "Falta registrar el informe del caso con registrar_informe (habilitar, no_habilitar o "
        "decide_cumplimiento)."
    )
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_CIERRE_IMPEDIDO and evento.regla is None
    assert estado.libro.cierres_impedidos == 1


def test_con_el_informe_vigente_el_cierre_se_permite():
    _, _, hooks = _caso_con_comercio()
    _aceptar_informe(hooks)
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()


def test_con_el_informe_no_vigente_el_motivo_nombra_lo_que_cambio():
    estado, _, hooks = _caso_con_comercio()
    _aceptar_informe(hooks)
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.TERMINADO)
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert salida["reason"] == (
        "El informe registrado ya no está vigente: cambió la cobertura después de registrarlo. "
        "Registra uno nuevo."
    )
    _aceptar_informe(hooks, tool_use_id="t2", identificador="INF-0002")
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()


def test_con_el_registro_caido_y_un_reintento_el_motivo_ofrece_las_dos_salidas():
    estado, _, hooks = _caso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.NO_TERMINADO, "caído")
    estado.errores[Frente.REGISTRO] = {
        "causa": "error_de_fuente",
        "reintentable": True,
        "obtenido": {"errores": [{"tipo": "servicio_no_disponible"}]},
    }
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert salida["reason"] == MOTIVO_REGISTRO_REINTENTABLE
    assert MOTIVO_REGISTRO_REINTENTABLE == (
        "El registro mercantil no respondió: reintenta el registro o registra el informe."
    )
    estado.errores[Frente.REGISTRO]["reintentable"] = False
    assert _ejecutar(_stop(hooks), _fin_de_turno())["reason"] == MOTIVO_SIN_INFORME


def test_sin_escalar_ni_informe_primero_el_escalamiento_y_luego_el_informe():
    estado, _, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert salida["reason"] == (
        "El caso requiere escalamiento a cumplimiento y aún no se ha escalado por: coincidencia "
        "del representante legal en listas restrictivas. Luego registra el informe."
    )


@pytest.mark.parametrize(
    "respuesta", [respuesta_registro(*comercios_parecidos()), respuesta_registro()]
)
def test_con_varias_coincidencias_o_ninguna_no_se_exige_informe(respuesta):
    estado, eventos, hooks = _caso()
    _registro_terminado(estado)
    estado.registrar_identificacion(respuesta)
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert eventos.eventos() == []


def test_la_entrada_invalida_en_el_registro_no_exige_informe():
    estado, _, hooks = _caso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.NO_TERMINADO, "inválida")
    estado.errores[Frente.REGISTRO] = {
        "causa": "error_de_fuente",
        "reintentable": False,
        "obtenido": {"errores": [{"tipo": "entrada_invalida"}]},
    }
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()


def test_las_devoluciones_por_el_informe_comparten_el_contador_y_marcan_cierre_sin_informe():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.cierres_impedidos = MAX_CIERRES_IMPEDIDOS - 1  # ya gastadas en otra cosa
    assert _es_bloqueo(_ejecutar(_stop(hooks), _fin_de_turno()))
    assert estado.libro.cierres_impedidos == MAX_CIERRES_IMPEDIDOS
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert estado.cierre_sin_informe is True and estado.cierre_sin_escalar is False
    ultimo = eventos.eventos()[-1]
    assert ultimo.tipo == TIPO_CIERRE_SIN_INFORME
    assert ultimo.detalle == (
        "El caso termina sin el informe vigente: se agotaron las 3 devoluciones del cierre."
    )


def test_agotadas_las_devoluciones_sin_escalar_ni_informe_se_marcan_los_dos():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    estado.libro.cierres_impedidos = MAX_CIERRES_IMPEDIDOS
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert estado.cierre_sin_escalar is True and estado.cierre_sin_informe is True
    assert [e.tipo for e in eventos.eventos()] == [TIPO_CIERRE_SIN_ESCALAR, TIPO_CIERRE_SIN_INFORME]


def test_limitacion_conocida_el_stop_exige_el_informe_aunque_el_turno_sea_una_pregunta():
    # Limitación conocida (#9, R8; la resuelve el #10): el `Stop` no distingue una pregunta al
    # analista de un cierre definitivo. Con el comercio identificado y sin informe, se bloquea.
    _, _, hooks = _caso_con_comercio()
    pregunta = _fin_de_turno(mensaje="Necesito que me confirme la categoría del comercio.")
    salida = _ejecutar(_stop(hooks), pregunta)
    assert _es_bloqueo(salida) and salida["reason"] == MOTIVO_SIN_INFORME
