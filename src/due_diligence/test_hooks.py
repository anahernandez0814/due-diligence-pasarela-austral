"""Tests de los hooks de las reglas de negocio (R1, R2, R5, contrato `hooks.md`).

Los hooks se prueban llamando a sus callbacks directamente con entradas con la forma que el SDK
0.2.168 entrega (medida en R1). Ningún test llama al modelo.
"""

import asyncio
import copy
import itertools
import json
import typing

import pytest
from claude_agent_sdk import types as sdk

from due_diligence import configuracion
from due_diligence import hooks as modulo_hooks
from due_diligence import informe as modulo_informe
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
from due_diligence.informe import InformeRegistrado, clave_comercio, huella_actual
from due_diligence.libro import Coincidencia, ConsultaRiesgo, Escalamiento
from due_diligence.reglas import (
    MOTIVO_CATEGORIA_NO_DETERMINADA,
    MOTIVO_CONSULTA_AJENA,
    MOTIVO_ENTRADA_INFORME,
    MOTIVO_FALTA_LISTAS,
    MOTIVO_HABILITAR_ALTO_RIESGO,
    MOTIVO_HABILITAR_CON_COINCIDENCIA,
    MOTIVO_RECOMENDACION,
    MOTIVO_REGISTRO_PRIMERO,
    MOTIVO_REGISTRO_REINTENTABLE,
    MOTIVO_SIN_COMERCIO,
    MOTIVO_SIN_INFORME,
    causas_vigentes,
    falta_para_cerrar,
    motivo_de_escalar,
)
from due_diligence.simulacion import (
    afirmaciones_del_caso,
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


@pytest.fixture(autouse=True)
def _sin_caida_del_registro(monkeypatch):
    """Los tests que consultan el registro real no dependen de la caída simulada de la sesión."""
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)


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


# Con el sello y sin escalar, el informe mínimo da estos dos motivos, en este orden (R9).
MOTIVOS_SELLADO_SIN_ESCALAR = [
    {
        "regla": None,
        "texto": "Tras un fallo de hook solo decide el oficial: la recomendación debe ser "
        "decide_cumplimiento.",
    },
    {
        "regla": None,
        "texto": "El caso requiere escalamiento a cumplimiento y aún no se ha escalado por: "
        "fallo de un hook de verificación.",
    },
]


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
    assert estado.libro.escalamientos == [
        Escalamiento(
            frozenset({"coincidencia_representante"}), ("CO-TV-0001", "Tienda Verde SAS", True)
        )
    ]
    evento = eventos.eventos()[-1]
    assert evento.tipo == TIPO_ESCALAMIENTO_REGISTRADO and evento.frente is None
    assert "representante legal" in evento.detalle and "PE-0003" not in evento.detalle


def test_sin_pendiente_el_evento_del_escalamiento_lleva_la_cobertura_y_las_afirmaciones():
    # FR-021 (#10): también en el camino sin pendiente (un `PreToolUse` que falló y degradó), el
    # evento dice el id, las causas, la cobertura (la fija «no calculada» que puso la degradación)
    # y el número de afirmaciones del resumen que llegó a la pasarela.
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("suplementos dietarios", "alto"))
    escalado = respuesta_de_decision("caso_escalado", "ESC-0009")
    enviado = _escalamiento()  # una afirmación, en registro
    _ejecutar(_hook(hooks.coordinador(), "PostToolUse"), _post_de(ESCALAR, escalado, enviado))
    assert eventos.eventos()[-1].detalle == (
        "Escalamiento ESC-0009 registrado; cubre: categoría de alto riesgo; cobertura no "
        "calculada; 1 afirmaciones."
    )


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
    estado.libro.escalamientos.append(
        Escalamiento(frozenset({"coincidencia_representante"}), clave_comercio(estado))
    )
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


@pytest.mark.parametrize(
    ("entrada", "motivo", "rutas"),
    [
        (None, MOTIVO_ENTRADA_INFORME, []),
        ("informe", MOTIVO_ENTRADA_INFORME, []),
        ([], MOTIVO_ENTRADA_INFORME, []),
        ({}, MOTIVO_RECOMENDACION, ["hallazgos"]),
        ({"recomendacion": 3}, MOTIVO_RECOMENDACION, ["hallazgos"]),
    ],
)
def test_el_hook_del_informe_con_una_entrada_malformada_deniega(entrada, motivo, rutas):
    _, _, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    assert _es_denegacion(salida)
    # T037: igualdad exacta sobre el JSON del rechazo.
    assert _rechazo(salida)["motivos"] == [{"regla": None, "texto": motivo}]
    assert [p["ruta"] for p in _rechazo(salida)["problemas"]] == rutas


def test_con_el_libro_sellado_el_hook_del_informe_deniega():
    # #9, R9: sigue denegando `no_habilitar` con el sello y sin escalar, ahora con los dos motivos
    # del informe mínimo, en ese orden (T037: igualdad exacta sobre el JSON).
    estado, _, hooks = _caso_con_comercio()
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    assert _es_denegacion(salida)
    assert _rechazo(salida)["motivos"] == MOTIVOS_SELLADO_SIN_ESCALAR
    assert _rechazo(salida)["problemas"] == []


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
    assert _rechazo(salida)["problemas"] == []
    assert eventos.eventos()[-1].regla == "I.2, I.3"


def test_el_hook_del_informe_deniega_habilitar_sin_categoria_determinada():
    estado, eventos, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("habilitar")))
    assert _rechazo(salida)["motivos"] == [
        {"regla": "I.3", "texto": MOTIVO_CATEGORIA_NO_DETERMINADA},
        {"regla": "I.2", "texto": MOTIVO_FALTA_LISTAS},
    ]
    assert _rechazo(salida)["problemas"] == []
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
    estado.libro.escalamientos.append(
        Escalamiento(frozenset({"coincidencia_representante"}), clave_comercio(estado))
    )
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


def _stop_roto(monkeypatch):
    def roto(_estado):
        raise RuntimeError("detalle interno")

    monkeypatch.setattr(modulo_hooks, "evaluar_cierre", roto)


def _tipos_de_cierre(eventos):
    return [e.tipo for e in eventos.eventos() if e.tipo.startswith("cierre_sin_")]


def test_un_stop_que_lanza_una_excepcion_bloquea_y_cuenta_hasta_el_limite(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    _stop_roto(monkeypatch)
    for _ in range(MAX_CIERRES_IMPEDIDOS):
        salida = _ejecutar(_stop(hooks), _fin_de_turno())
        assert _es_bloqueo(salida) and "detalle interno" not in salida["reason"]
    assert estado.libro.cierres_impedidos == MAX_CIERRES_IMPEDIDOS
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()  # el límite también vale aquí
    # Faltan el escalamiento (coincidencia) y el informe: se marcan los dos, con su evento.
    assert estado.cierre_sin_escalar is True and estado.cierre_sin_informe is True
    assert _tipos_de_cierre(eventos) == [TIPO_CIERRE_SIN_ESCALAR, TIPO_CIERRE_SIN_INFORME]
    assert eventos.eventos()[-2].regla == "I.2"
    assert estado.libro.fallo_de_hook


def _sello_ya_escalado(estado):
    """Un fallo de hook anterior ya escalado: el sello es causa de escalamiento (#9, R9) y un
    escalamiento que la cubre deja de exigirlo aunque el `Stop` vuelva a sellar el libro."""
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    estado.libro.escalamientos.append(
        Escalamiento(causas_vigentes(estado.libro), clave_comercio(estado))
    )


def test_un_stop_que_falla_sin_informe_vigente_marca_solo_cierre_sin_informe(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()
    _sello_ya_escalado(estado)  # nada pendiente de escalar; falta el informe
    estado.libro.cierres_impedidos = MAX_CIERRES_IMPEDIDOS
    _stop_roto(monkeypatch)
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert estado.cierre_sin_informe is True and estado.cierre_sin_escalar is False
    assert _tipos_de_cierre(eventos) == [TIPO_CIERRE_SIN_INFORME]
    assert "detalle interno" not in eventos.eventos()[-1].detalle


def test_un_stop_que_falla_con_informe_vigente_y_escalamiento_pendiente_marca_solo_escalar(
    monkeypatch,
):
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"  # la huella ya incluye el sello
    _con_informe_vigente(estado)
    estado.libro.cierres_impedidos = MAX_CIERRES_IMPEDIDOS
    _stop_roto(monkeypatch)
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert estado.cierre_sin_escalar is True and estado.cierre_sin_informe is False
    assert _tipos_de_cierre(eventos) == [TIPO_CIERRE_SIN_ESCALAR]


def test_si_tampoco_se_sabe_lo_que_falta_el_stop_marca_los_dos_por_prudencia(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()
    _con_informe_vigente(estado)  # nada falta de verdad, pero no se puede comprobar
    estado.libro.cierres_impedidos = MAX_CIERRES_IMPEDIDOS
    _stop_roto(monkeypatch)

    def tambien_roto(_estado):
        raise RuntimeError("detalle interno")

    monkeypatch.setattr(modulo_hooks, "falta_para_cerrar", tambien_roto)
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert estado.cierre_sin_escalar is True and estado.cierre_sin_informe is True
    assert _tipos_de_cierre(eventos) == [TIPO_CIERRE_SIN_ESCALAR, TIPO_CIERRE_SIN_INFORME]
    assert eventos.eventos()[-2].regla is None
    assert all("detalle interno" not in e.detalle for e in eventos.eventos())


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


def _escalamiento(hallazgos=None):
    """El resumen al oficial del #10 (R6). Sus hallazgos citan la consulta del registro de
    `_caso_con_comercio`; el comercio, la cobertura, la causa y los conflictos los pone el hook."""
    return {
        "comercio": dict(COMERCIO_VERIFICADO),
        "hallazgos": hallazgos
        if hallazgos is not None
        else {
            "registro": [
                {
                    "texto": "Una coincidencia en el registro.",
                    "fuente": FUENTE_REGISTRO,
                    "fecha": "2026-09-30",
                }
            ]
        },
        "cobertura": "completa",
        "causa_escalamiento": "alto riesgo",
        "accion_recomendada": "Revisar el origen de fondos antes de decidir.",
        "conflictos": {"resumen": "Sin conflictos declarados.", "lista": []},
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


@pytest.mark.parametrize("sellado", [False, True])
def test_el_escalamiento_sustituye_la_cobertura_aunque_el_libro_este_sellado(sellado):
    # #8; desde el #10 (R5) el hook también pone el comercio, la causa y los conflictos, y con el
    # sello la cobertura y los conflictos van como no calculados (como el informe mínimo del #9).
    from due_diligence.conflictos import calcular_conflictos, no_calculados

    estado, eventos, hooks = _caso_con_comercio()
    if sellado:
        estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    entrada = _escalamiento()
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, entrada))
    assert not _es_denegacion(salida)
    assert salida["hookSpecificOutput"]["permissionDecision"] == "allow"
    sustituida = _sustituida(salida)
    assert sustituida["hallazgos"] == entrada["hallazgos"]
    assert sustituida["accion_recomendada"] == entrada["accion_recomendada"]
    assert sustituida["comercio"] == COMERCIO_VERIFICADO
    if sellado:
        assert sustituida["cobertura"] == [COBERTURA_NO_CALCULADA]
        assert sustituida["conflictos"] == no_calculados().como_entrada()
        assert sustituida["causa_escalamiento"] == ["fallo de un hook de verificación"]
    else:
        assert sustituida["cobertura"] == calcular_cobertura(estado).lineas()
        assert sustituida["conflictos"] == calcular_conflictos(estado).como_entrada()
    tipos = [e.tipo for e in eventos.eventos()]
    assert tipos == [TIPO_COBERTURA_SUSTITUIDA, TIPO_DATOS_SUSTITUIDOS]
    assert "escalar_a_cumplimiento" in eventos.eventos()[0].detalle


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
    from due_diligence.conflictos import no_calculados
    from servidor_mcp.informe import validar_resumen

    assert _sustituida(salida) == {
        **entrada,
        "comercio": COMERCIO_VERIFICADO,
        "cobertura": [COBERTURA_NO_CALCULADA],
        "causa_escalamiento": ["fallo de un hook de verificación"],
        "conflictos": no_calculados().como_entrada(),
    }
    assert validar_resumen(_sustituida(salida)) == []
    assert modulo_hooks.COBERTURA_NO_CALCULADA == COBERTURA_NO_CALCULADA
    assert estado.libro.fallo_de_hook is not None
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_FALLO_DE_HOOK and TEXTO_INTERNO not in evento.detalle
    # Con el sello y sin escalamiento confirmado, `no_habilitar` se rechaza (#9, R9; el riesgo
    # residual 6 del #8 lo resuelve el informe mínimo, que se prueba aparte).
    informe = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("no_habilitar")))
    assert _es_denegacion(informe)
    assert _rechazo(informe)["motivos"] == MOTIVOS_SELLADO_SIN_ESCALAR
    assert _rechazo(informe)["problemas"] == []


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
    # #9: el informe necesita un comercio (aquí, el pedido), una fuente consultada (FR-004) y una
    # afirmación por frente cubierto (US1-6): cada frente con su consulta y su afirmación.
    estado.comercio_pedido = {"identificador": "CO-TV-0001", "nombre": None}
    estado.agregar_consultas([consulta(frente) for frente in Frente])
    esperada = calcular_cobertura(estado).lineas()
    entrada = {**_informe_de("no_habilitar"), "hallazgos": afirmaciones_del_caso(estado)}
    informe = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    resumen = _escalamiento(hallazgos=afirmaciones_del_caso(estado))
    escalamiento = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, resumen))
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
    entrada = _informe_de("no_habilitar")
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


def test_un_informe_sin_ninguna_afirmacion_se_acepta_si_ningun_frente_quedo_cubierto():
    # I.5: si nada quedó cubierto, el informe se entrega igual. El comercio es el pedido, porque
    # sin el registro terminado no hay comercio identificado.
    estado, _, hooks = _caso()
    estado.comercio_pedido = {"identificador": "CO-TV-0001", "nombre": None}
    assert not any(c.cubierto for c in calcular_cobertura(estado).frentes.values())
    entrada = {**_informe_de("no_habilitar"), "hallazgos": {}}
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    comercio = {"identificador": "CO-TV-0001", "nombre": None, "verificado": False}
    conflictos = {
        "resumen": "No se compararon las fuentes registrales: no hay comercio identificado.",
        "lista": [],
    }
    _comprobar_informe_aceptado(salida, entrada, estado, comercio=comercio, conflictos=conflictos)


FRENTE_CUBIERTO_SIN_AFIRMACION = (
    "El frente {frente} quedó cubierto: su resultado, aunque sea sin hallazgos, debe ir como "
    "afirmación con fuente y fecha."
)


@pytest.mark.parametrize("hallazgos", [{}, {"registro": []}])
def test_un_frente_cubierto_sin_afirmaciones_se_rechaza_con_la_regla_i4(hallazgos):
    # US1-6: «sin hallazgos» también es una afirmación con su fuente y su fecha.
    estado, eventos, hooks = _caso_con_comercio()
    entrada = {**_informe_de("no_habilitar"), "hallazgos": hallazgos}
    rechazo = _rechazo(_ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada)))
    assert rechazo["motivos"] == []
    assert rechazo["problemas"] == [
        {
            "ruta": "hallazgos.registro",
            "texto": FRENTE_CUBIERTO_SIN_AFIRMACION.format(frente="registro"),
        }
    ]
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_BLOQUEO_REGLA and evento.regla == "I.4"
    assert modulo_informe.FRENTE_CUBIERTO_SIN_AFIRMACION == FRENTE_CUBIERTO_SIN_AFIRMACION


def test_cada_frente_cubierto_sin_afirmaciones_se_nombra_y_los_no_cubiertos_no():
    estado, _, hooks = _caso_con_comercio()
    for frente in (Frente.NOTICIAS, Frente.CATEGORIA):
        estado.cambiar_situacion(frente, Situacion.EN_CURSO)
        estado.cambiar_situacion(frente, Situacion.TERMINADO)
    entrada = {**_informe_de("decide_cumplimiento"), "hallazgos": {"categoria": []}}
    rechazo = _rechazo(_ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada)))
    assert [p["ruta"] for p in rechazo["problemas"]] == [
        "hallazgos.registro",
        "hallazgos.noticias",
        "hallazgos.categoria",
    ]


@pytest.mark.parametrize("hallazgos_de_listas", [None, []])
def test_un_frente_no_cubierto_puede_ir_sin_afirmaciones(hallazgos_de_listas):
    # I.5: listas no se delegó; puede faltar o ir vacía mientras el registro, cubierto, se cita.
    estado, _, hooks = _caso_con_comercio()
    entrada = _informe_de("no_habilitar")
    if hallazgos_de_listas is not None:
        entrada["hallazgos"]["listas"] = hallazgos_de_listas
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(salida, entrada, estado)


def test_el_comercio_declarado_distinto_se_sustituye_y_el_evento_lo_dice_sin_datos():
    estado, eventos, hooks = _caso_con_comercio()
    entrada = _informe_de("no_habilitar")
    entrada["comercio"] = {"identificador": "CO-XX-9999", "nombre": "Otro", "verificado": True}
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(salida, entrada, estado)
    datos = eventos.eventos()[-1]
    assert datos.tipo == TIPO_DATOS_SUSTITUIDOS
    assert "comercio verificado" in datos.detalle
    assert "distinto" in datos.detalle and "comercio" in datos.detalle
    for dato in ("CO-TV-0001", "Tienda Verde", "CO-XX-9999", "Otro"):
        assert dato not in datos.detalle


def test_el_comercio_y_los_conflictos_declarados_iguales_el_evento_dice_que_coinciden():
    # T017: la otra rama de `datos_sustituidos`.
    estado, eventos, hooks = _caso_con_comercio()
    entrada = {**_informe_de("no_habilitar"), "conflictos": dict(SIN_CONFLICTOS)}
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(salida, entrada, estado)
    (datos,) = [e for e in eventos.eventos() if e.tipo == TIPO_DATOS_SUSTITUIDOS]
    assert datos.detalle == (
        "Datos del código puestos en registrar_informe: comercio verificado; Sin conflictos "
        "entre las fuentes registrales. Coincide con lo declarado por el coordinador."
    )


def test_un_problema_solo_de_esquema_se_rechaza_con_la_regla_i4():
    # T017: sin motivos de las reglas, un único problema de forma deja `bloqueo_regla [I.4]`.
    estado, eventos, hooks = _caso_con_comercio()
    entrada = _informe_de("no_habilitar")
    entrada["hallazgos"]["registro"][0]["fecha"] = "2026-02-30"
    rechazo = _rechazo(_ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada)))
    assert rechazo["motivos"] == []
    assert [p["ruta"] for p in rechazo["problemas"]] == ["hallazgos.registro[0].fecha"]
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_BLOQUEO_REGLA and evento.regla == "I.4"
    assert estado.informes_pendientes == {}


def test_sin_comercio_identificado_va_el_pedido_sin_verificar():
    estado, _, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Taller Aurora SAS"}
    estado.agregar_consultas([consulta(Frente.REGISTRO)])
    entrada = _informe_de("no_habilitar")
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(
        salida,
        entrada,
        estado,
        comercio={"identificador": None, "nombre": "Taller Aurora SAS", "verificado": False},
        # El registro no se delegó: no hay comercio identificado, pero no está caído.
        conflictos={
            "resumen": "No se compararon las fuentes registrales: no hay comercio identificado.",
            "lista": [],
        },
    )


def _registro_con_varias_coincidencias(estado):
    _registro_terminado(estado)
    respuesta = respuesta_registro(*comercios_parecidos())
    estado.registrar_identificacion(respuesta)
    estado.agregar_consultas([consulta(Frente.REGISTRO, {"nombre": "Almacén Mirador"}, respuesta)])


def _registro_en_curso(estado):
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)


def _registro_caido_en_el_estado(estado):
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.NO_TERMINADO, "caído")
    estado.errores[Frente.REGISTRO] = {
        "causa": "error_de_fuente",
        "reintentable": False,
        "obtenido": {"errores": [{"tipo": "servicio_no_disponible"}]},
    }


def test_con_varias_coincidencias_la_cobertura_y_los_conflictos_no_se_contradicen():
    # La variante de varias coincidencias del test siguiente (#9). Desde el #10 (FR-016) el informe
    # se rechaza durante la espera del identificador, así que la cobertura y los conflictos se
    # comprueban con los cálculos puros que el hook pondría, con las mismas igualdades exactas.
    from due_diligence.conflictos import calcular_conflictos
    from due_diligence.reglas import MOTIVO_INFORME_ESPERA_IDENTIFICADOR

    estado, _, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Almacén Mirador"}
    _registro_con_varias_coincidencias(estado)
    lineas = calcular_cobertura(estado).lineas()
    assert lineas[1 + list(Frente).index(Frente.REGISTRO)] == "registro: cubierto."
    assert calcular_conflictos(estado).resumen == (
        "No se compararon las fuentes registrales: no hay comercio identificado."
    )
    entrada = {**_informe_de("no_habilitar"), "hallazgos": afirmaciones_del_caso(estado)}
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    assert _rechazo(salida)["motivos"] == [
        {"regla": "V", "texto": MOTIVO_INFORME_ESPERA_IDENTIFICADOR}
    ]


@pytest.mark.parametrize(
    ("preparar", "linea_registro", "resumen"),
    [
        (
            _registro_en_curso,
            "registro: no cubierto; seguía en curso.",
            "No se compararon las fuentes registrales: no hay comercio identificado.",
        ),
        (
            _registro_caido_en_el_estado,
            "registro: no cubierto; error de la fuente (servicio_no_disponible).",
            "No se pudieron comparar las fuentes registrales: el registro no respondió.",
        ),
    ],
)
def test_sin_comercio_identificado_la_cobertura_y_los_conflictos_no_se_contradicen(
    preparar, linea_registro, resumen
):
    # Bloqueante de la revisión del #9: con varias coincidencias el registro respondió (cobertura
    # «cubierto») y en curso aún no terminó; solo el registro caído dice que no respondió.
    estado, _, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Almacén Mirador"}
    preparar(estado)
    # Con varias coincidencias el registro quedó cubierto y se cita (US1-6); si no, va vacío.
    entrada = {**_informe_de("no_habilitar"), "hallazgos": afirmaciones_del_caso(estado)}
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    comercio = {"identificador": None, "nombre": "Almacén Mirador", "verificado": False}
    conflictos = {"resumen": resumen, "lista": []}
    _comprobar_informe_aceptado(salida, entrada, estado, comercio=comercio, conflictos=conflictos)
    sustituida = _sustituida(salida)
    registro = sustituida["cobertura"][1 + list(Frente).index(Frente.REGISTRO)]
    assert registro == linea_registro
    no_respondio = "no respondió" in sustituida["conflictos"]["resumen"]
    assert no_respondio == registro.startswith("registro: no cubierto; error de la fuente")


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
    hooks, recomendacion="no_habilitar", tool_use_id="t1", identificador="INF-0001", hallazgos=None
):
    """El `PreToolUse` acepta y la pasarela registra: el `PostToolUse` confirma la huella."""
    informe = _informe_de(recomendacion)
    if hallazgos is not None:
        informe["hallazgos"] = hallazgos
    entrada = {**_pre(INFORME, informe), "tool_use_id": tool_use_id}
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


def _detalle_registrado(eventos):
    (registrado,) = [e for e in eventos.eventos() if e.tipo == TIPO_INFORME_REGISTRADO]
    return registrado.detalle


def test_el_evento_del_informe_registrado_cuenta_un_conflicto_en_el_caso_g():
    # T027: el número de conflictos del evento, con el caso (g).
    _, eventos, hooks = _caso_g()
    _aceptar_informe(hooks)
    assert _detalle_registrado(eventos) == (
        "Informe INF-0001 registrado; recomendación: no_habilitar; cobertura incompleta, "
        "1 de 4 frentes; 1 conflicto."
    )


def test_el_evento_del_informe_registrado_cuenta_varios_conflictos(monkeypatch):
    from due_diligence import conflictos as modulo_conflictos
    from servidor_mcp.registro import consultar_registro_mercantil

    original = consultar_registro_mercantil

    def con_dos_conflictos(**argumentos):
        # Copia: no se toca la respuesta que la pasarela pueda tener en caché.
        resultado = copy.deepcopy(original(**argumentos))
        resultado.structured_content["hechos"][1]["contenido"]["estado"] = "inactivo"
        return resultado

    monkeypatch.setattr("servidor_mcp.registro.consultar_registro_mercantil", con_dos_conflictos)
    estado, eventos, hooks = _caso_g()
    assert len(modulo_conflictos.calcular_conflictos(estado).lista) == 2
    _aceptar_informe(hooks)
    assert _detalle_registrado(eventos) == (
        "Informe INF-0001 registrado; recomendación: no_habilitar; cobertura incompleta, "
        "1 de 4 frentes; 2 conflictos."
    )


def test_el_evento_del_informe_registrado_con_el_registro_caido_dice_no_comparadas():
    estado, eventos, hooks = _caso()
    _registro_caido_en_el_estado(estado)
    estado.comercio_pedido = {"identificador": "CO-TA-0002", "nombre": None}
    _aceptar_informe(hooks, hallazgos={})
    assert _detalle_registrado(eventos) == (
        "Informe INF-0001 registrado; recomendación: no_habilitar; cobertura incompleta, "
        "0 de 4 frentes; fuentes registrales no comparadas."
    )


def test_la_recomendacion_queda_en_su_forma_canonica_en_la_pasarela_el_informe_y_el_evento():
    # FR-011: el modelo escribe «No-Habilitar»; lo que se registra es `no_habilitar`.
    estado, eventos, hooks = _caso_con_comercio()
    entrada = _informe_de("No-Habilitar")
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(salida, {**entrada, "recomendacion": "no_habilitar"}, estado)
    assert estado.informes_pendientes["t1"][1] == "no_habilitar"
    respuesta = respuesta_de_decision("informe_registrado", "INF-0003")
    _ejecutar(_post_del_informe(hooks), _post_de(INFORME, respuesta, _sustituida(salida)))
    assert estado.informes[-1].recomendacion == "no_habilitar"
    registrado = eventos.eventos()[-1]
    assert registrado.tipo == TIPO_INFORME_REGISTRADO
    assert "recomendación: no_habilitar;" in registrado.detalle
    assert "No-Habilitar" not in registrado.detalle


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
    # Las noticias ya están cubiertas: el informe nuevo las cita (US1-6). La consulta es del
    # comercio identificado, como la del subagente (#10, FR-027).
    estado.agregar_consultas([consulta(Frente.NOTICIAS, {"identificador": "CO-TV-0001"})])
    _aceptar_informe(
        hooks, tool_use_id="t2", identificador="INF-0002", hallazgos=afirmaciones_del_caso(estado)
    )
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
    from due_diligence.eventos import TIPO_ESPERA_ANALISTA

    estado, eventos, hooks = _caso()
    _registro_terminado(estado)
    estado.registrar_identificacion(respuesta)
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    # Desde el #10 (R3) es una espera del analista: deja `espera_analista` y nada más.
    assert [e.tipo for e in eventos.eventos()] == [TIPO_ESPERA_ANALISTA]


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


def test_con_el_comercio_identificado_una_pregunta_no_es_una_espera_y_exige_el_informe():
    # US4-1 del #10 (FR-015). Era la «limitación conocida» del #9 (R8), que el #10 cambia a
    # sabiendas: solo es espera lo que el código comprueba en el estado (R3). Con el comercio
    # identificado y sin una categoría bloqueada, el texto del fin de turno no cuenta.
    _, _, hooks = _caso_con_comercio()
    pregunta = _fin_de_turno(mensaje="Necesito que me confirme la categoría del comercio.")
    salida = _ejecutar(_stop(hooks), pregunta)
    assert _es_bloqueo(salida) and salida["reason"] == MOTIVO_SIN_INFORME


def test_con_la_categoria_bloqueada_sin_resultado_la_pregunta_es_una_espera():
    # US4-4 del #10: la misma pregunta, con la última delegación de categoría bloqueada por I.3 y
    # sin ningún resultado de categoría, sí es una espera que el código comprueba.
    from due_diligence.eventos import TIPO_ESPERA_ANALISTA

    estado, eventos, hooks = _caso_con_comercio()
    estado.categoria_bloqueada = True
    pregunta = _fin_de_turno(mensaje="Necesito que me confirme la categoría del comercio.")
    assert _ejecutar(_stop(hooks), pregunta) == permitir()
    assert [e.tipo for e in eventos.eventos()] == [TIPO_ESPERA_ANALISTA]
    assert estado.libro.cierres_impedidos == 0


# ------------------------------------------- #9: informe mínimo tras un fallo de hook (US4, R9)

NO_CALCULADOS_ENTRADA = {
    "resumen": "No se pudieron calcular los conflictos; deben tratarse como no verificados.",
    "lista": [],
}


def _sellar(estado):
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"


def _escalar_confirmado(hooks):
    """El escalamiento pasa (nunca se deniega) y su `PostToolUse` guarda la instantánea."""
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento()))
    escalado = respuesta_de_decision("caso_escalado", "ESC-0001")
    _ejecutar(
        _hook(hooks.coordinador(), "PostToolUse"), _post_de(ESCALAR, escalado, _sustituida(salida))
    )


def test_sin_escalamiento_el_informe_minimo_se_rechaza():
    estado, _, hooks = _caso_con_comercio()
    _sellar(estado)
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("decide_cumplimiento")))
    assert _rechazo(salida)["motivos"] == [MOTIVOS_SELLADO_SIN_ESCALAR[1]]


@pytest.mark.parametrize("recomendacion", ["habilitar", "no_habilitar"])
def test_tras_escalar_solo_decide_cumplimiento(recomendacion):
    estado, _, hooks = _caso_con_comercio()
    _sellar(estado)
    _escalar_confirmado(hooks)
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de(recomendacion)))
    assert _rechazo(salida)["motivos"] == [MOTIVOS_SELLADO_SIN_ESCALAR[0]]


def test_tras_escalar_el_informe_minimo_se_acepta_con_los_textos_fijos(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()
    _sellar(estado)
    _escalar_confirmado(hooks)

    def roto(_estado):
        raise RuntimeError(TEXTO_INTERNO)

    # Con el sello, ni el `PreToolUse` ni la huella calculan cobertura ni conflictos (I1).
    for modulo in (modulo_hooks, modulo_informe):
        monkeypatch.setattr(modulo, "calcular_cobertura", roto)
        monkeypatch.setattr(modulo, "calcular_conflictos", roto)
    entrada = _informe_de("decide_cumplimiento")
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    assert salida["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert _sustituida(salida) == {
        "comercio": COMERCIO_VERIFICADO,
        "recomendacion": "decide_cumplimiento",
        "hallazgos": entrada["hallazgos"],
        "conflictos": NO_CALCULADOS_ENTRADA,
        "cobertura": [COBERTURA_NO_CALCULADA],
    }
    registrado = respuesta_de_decision("informe_registrado", "INF-0009")
    _ejecutar(_post_del_informe(hooks), _post_de(INFORME, registrado, _sustituida(salida)))
    (informe,) = estado.informes
    assert informe.minimo is True and informe.id == "INF-0009"
    assert eventos.eventos()[-1].detalle == (
        "Informe INF-0009 registrado; recomendación: decide_cumplimiento; cobertura y conflictos "
        "no calculados. Informe mínimo tras un fallo de hook."
    )
    assert all(TEXTO_INTERNO not in e.detalle for e in eventos.eventos())


def test_el_informe_minimo_no_exige_afirmaciones_de_los_frentes_cubiertos():
    # Con el sello la cobertura no se calcula (R9): no hay frentes cubiertos que comprobar.
    estado, _, hooks = _caso_con_comercio()
    _sellar(estado)
    _escalar_confirmado(hooks)
    entrada = {**_informe_de("decide_cumplimiento"), "hallazgos": {}}
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    assert salida["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert _sustituida(salida)["hallazgos"] == {}


def test_el_informe_minimo_sigue_validando_la_forma_y_la_fuente():
    estado, _, hooks = _caso_con_comercio()
    _sellar(estado)
    _escalar_confirmado(hooks)
    entrada = _informe_de("decide_cumplimiento")
    entrada["hallazgos"]["registro"][0]["fecha"] = "2026-02-30"
    entrada["hallazgos"]["noticias"] = [
        {"texto": "Sin menciones.", "fuente": "Diario Ficticio", "fecha": "2026-09-30"}
    ]
    rechazo = _rechazo(_ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada)))
    assert rechazo["motivos"] == []
    assert [p["ruta"] for p in rechazo["problemas"]] == [
        "hallazgos.registro[0].fecha",
        "hallazgos.noticias[0].fuente",
    ]


def test_informe_minimo_tras_escalar_el_stop_permite_cerrar_y_el_caso_no_esta_completo(monkeypatch):
    estado, eventos, hooks = _caso_con_comercio()
    _sellar(estado)
    assert _es_bloqueo(_ejecutar(_stop(hooks), _fin_de_turno()))  # sin escalar ni informe
    _escalar_confirmado(hooks)
    _aceptar_informe(hooks, recomendacion="decide_cumplimiento", tool_use_id="t9")

    def roto(_estado):
        raise RuntimeError(TEXTO_INTERNO)

    monkeypatch.setattr(modulo_informe, "calcular_cobertura", roto)
    monkeypatch.setattr(modulo_informe, "calcular_conflictos", roto)
    antes = len(eventos.eventos())
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert eventos.eventos()[antes:] == []
    assert estado.cierre_sin_informe is False and estado.cierre_sin_escalar is False
    # El caso nunca figura como completo con el sello: con todo lo demás que pide `Caso.completo`
    # cumplido (cobertura completa, fin normal, sin marcas de cierre e informe vigente), el sello
    # basta para que sea `False`.
    from due_diligence.coordinador import Caso
    from due_diligence.informe import informe_vigente
    from due_diligence.terminacion import Clasificacion, Terminacion

    _forzar(estado, [Situacion.TERMINADO] * len(Frente))
    estado.terminacion = Clasificacion(Terminacion.NORMAL, "success", "end_turn", None, False)
    caso = Caso()
    caso.estado = estado
    assert caso.cobertura.completa and informe_vigente(estado) is True
    assert estado.libro.fallo_de_hook
    assert caso.completo is False


def test_si_falla_el_post_del_informe_se_sella_y_pide_escalar_y_el_minimo(monkeypatch):
    # Hallazgo U2: el informe quedó guardado en la pasarela, pero su huella no se confirma.
    original = HooksDelCaso._informe_posterior
    llamadas = []

    async def falla_la_primera(self, entrada, tool_use_id, contexto):
        llamadas.append(tool_use_id)
        if len(llamadas) == 1:
            raise RuntimeError(TEXTO_INTERNO)
        return await original(self, entrada, tool_use_id, contexto)

    monkeypatch.setattr(HooksDelCaso, "_informe_posterior", falla_la_primera)
    estado, eventos, hooks = _caso_con_comercio()
    _aceptar_informe(hooks, tool_use_id="t1")
    assert estado.libro.fallo_de_hook is not None
    assert estado.informes == []
    assert TIPO_FALLO_DE_HOOK in [e.tipo for e in eventos.eventos()]
    # Ahora hay que escalar por el sello, y después el informe (mínimo), en ese orden (T032).
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida)
    assert salida["reason"] == (
        "El caso requiere escalamiento a cumplimiento y aún no se ha escalado por: fallo de un "
        "hook de verificación. Luego registra el informe."
    )
    _escalar_confirmado(hooks)
    _aceptar_informe(hooks, recomendacion="decide_cumplimiento", tool_use_id="t2")
    (informe,) = estado.informes
    assert informe.minimo is True
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()


def test_con_doble_fallo_el_informe_minimo_se_deniega_con_el_motivo_generico(monkeypatch):
    # Riesgo residual 6: si con el sello también falla el control de la fuente, se deniega.
    estado, _, hooks = _caso_con_comercio()
    _sellar(estado)
    _escalar_confirmado(hooks)

    def roto(_estado, _hallazgos):
        raise RuntimeError(TEXTO_INTERNO)

    monkeypatch.setattr(modulo_hooks, "problemas_de_fuente", roto)
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("decide_cumplimiento")))
    assert _es_denegacion(salida) and _motivo(salida) == modulo_hooks.MOTIVO_FALLO_DE_HOOK


# ------------------------------------------- #9: la acción intentada en los bloqueos (US5, FR-017)


def _ultimo_bloqueo(eventos):
    (bloqueo,) = [e for e in eventos.eventos() if e.tipo == TIPO_BLOQUEO_REGLA][-1:]
    return bloqueo


@pytest.mark.parametrize(
    ("recomendacion", "accion"),
    [
        ("habilitar", "registrar_informe (habilitar)"),
        ("aprobar", "registrar_informe (recomendación no válida)"),
    ],
)
def test_el_bloqueo_del_informe_dice_la_recomendacion_intentada(recomendacion, accion):
    _, eventos, hooks = _caso_con_comercio()
    _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de(recomendacion)))
    assert _ultimo_bloqueo(eventos).accion == accion


def test_el_bloqueo_de_un_informe_que_no_es_un_objeto_lo_dice_sin_repetirlo():
    _, eventos, hooks = _caso_con_comercio()
    _ejecutar(_hook_del_informe(hooks), _pre(INFORME, "texto libre"))
    assert _ultimo_bloqueo(eventos).accion == "registrar_informe (entrada no válida)"


@pytest.mark.parametrize(
    ("tipo", "accion"),
    [
        ("persona", "consultar_listas_restrictivas (persona)"),
        ("comercio", "consultar_listas_restrictivas (comercio)"),
        ("otra cosa", "consultar_listas_restrictivas (tipo no válido)"),
    ],
)
def test_el_bloqueo_de_listas_dice_si_la_consulta_era_del_comercio_o_del_representante(
    tipo, accion
):
    _, eventos, hooks = _caso()  # sin comercio identificado: la regla I.1 bloquea
    entrada = {"tipo": tipo, "identificador": "PE-0001"}
    salida = _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PreToolUse"), _pre(LISTAS, entrada))
    assert _es_denegacion(salida)
    assert _ultimo_bloqueo(eventos).accion == accion


def test_el_bloqueo_de_delegar_listas_lo_dice():
    _, eventos, hooks = _caso()
    _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), _pre(DELEGAR, {"frente": "listas"}))
    assert _ultimo_bloqueo(eventos).accion == "delegar_frente (listas)"
    _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), _pre(DELEGAR, "texto"))
    assert _ultimo_bloqueo(eventos).accion == "delegar_frente (entrada no válida)"


def test_con_el_libro_sellado_el_bloqueo_de_listas_tambien_dice_la_accion():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    entrada = {"tipo": "comercio", "identificador": "CO-TV-0001"}
    _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PreToolUse"), _pre(LISTAS, entrada))
    assert _ultimo_bloqueo(eventos).accion == "consultar_listas_restrictivas (comercio)"


def test_ninguna_accion_repite_nombres_ni_identificadores():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    _ejecutar(_hook_del_informe(hooks), _pre(INFORME, _informe_de("habilitar")))
    entrada = {"tipo": "persona", "identificador": "PE-0001", "nombre": "Lucía Ferrer Montalvo"}
    _ejecutar(_hook(hooks.subagente(Frente.LISTAS), "PreToolUse"), _pre(LISTAS, entrada))
    acciones = " ".join(e.accion or "" for e in eventos.eventos())
    for dato in ("CO-TV-0001", "Tienda Verde", "PE-0001", "Lucía"):
        assert dato not in acciones


# ---------------------------------------------- #10: esperas del analista en el Stop (T012)


def _con_alto_riesgo(estado):
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("suplementos dietarios", "alto"))
    return estado


def _registro_sin_coincidencias(estado):
    _registro_terminado(estado)
    respuesta = respuesta_registro()
    estado.registrar_identificacion(respuesta)
    estado.agregar_consultas([consulta(Frente.REGISTRO, {"nombre": "Almacén Mirado"}, respuesta)])


def _eventos_de(eventos, tipo):
    return [e for e in eventos.eventos() if e.tipo == tipo]


@pytest.mark.parametrize(
    ("preparar", "motivo"),
    [
        (_registro_con_varias_coincidencias, "MOTIVO_ESPERA_IDENTIFICADOR"),
        (_registro_sin_coincidencias, "MOTIVO_ESPERA_NOMBRE"),
    ],
)
def test_el_stop_admite_la_espera_del_registro_sin_escalar_ni_gastar_devoluciones(preparar, motivo):
    from due_diligence import reglas
    from due_diligence.eventos import TIPO_ESPERA_ANALISTA

    estado, eventos, hooks = _caso()
    preparar(estado)
    _con_alto_riesgo(estado)  # el caso exige escalar, pero falta el dato del analista
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    (evento,) = _eventos_de(eventos, TIPO_ESPERA_ANALISTA)
    assert evento.detalle == getattr(reglas, motivo)
    assert estado.libro.cierres_impedidos == 0
    assert estado.cierre_sin_escalar is False and estado.cierre_sin_informe is False
    assert _eventos_de(eventos, TIPO_CIERRE_IMPEDIDO) == []


def test_d3_del_9_no_es_espera_y_el_stop_exige_escalar():
    estado, _, hooks = _caso()
    _registro_terminado(estado)
    otra = {**comercio_alto_riesgo(), "nombre": "Tienda Verde Ltda"}
    estado.registrar_identificacion(
        {
            "resultado": "coincidencias",
            "hechos": [
                {"contenido": comercio_alto_riesgo(), "metadatos": {}},
                {"contenido": otra, "metadatos": {}},
            ],
            "coincidencias": ["CO-TV-0001"],
        }
    )
    _con_alto_riesgo(estado)
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida) and salida["reason"] == motivo_de_escalar({"alto_riesgo"})
    assert estado.libro.cierres_impedidos == 1


def test_con_el_sello_la_espera_del_identificador_se_sigue_admitiendo():
    estado, _, hooks = _caso()
    _registro_con_varias_coincidencias(estado)
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()


def test_si_falla_el_calculo_de_la_espera_el_stop_bloquea(monkeypatch):
    estado, _, hooks = _caso()
    _registro_con_varias_coincidencias(estado)

    def lanza(_estado):
        raise RuntimeError("detalle interno")

    monkeypatch.setattr("due_diligence.hooks.espera_del_analista", lanza)
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida) and "detalle interno" not in salida["reason"]


# -------------------------------------- #10: el informe durante la espera (T012, FR-016, I1)


def _informe_del_caso(estado, recomendacion):
    return {**_informe_de(recomendacion), "hallazgos": afirmaciones_del_caso(estado)}


@pytest.mark.parametrize(
    ("preparar", "motivo"),
    [
        (_registro_con_varias_coincidencias, "MOTIVO_INFORME_ESPERA_IDENTIFICADOR"),
        (_registro_sin_coincidencias, "MOTIVO_INFORME_ESPERA_NOMBRE"),
    ],
)
def test_el_informe_se_rechaza_mientras_se_espera_el_identificador_o_el_nombre(preparar, motivo):
    from due_diligence import reglas

    estado, eventos, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Almacén Mirador"}
    preparar(estado)
    entrada = _informe_del_caso(estado, "no_habilitar")  # válido en forma y en fuentes
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    assert _es_denegacion(salida)
    rechazo = _rechazo(salida)
    assert rechazo["motivos"] == [{"regla": "V", "texto": getattr(reglas, motivo)}]
    assert rechazo["problemas"] == []
    (evento,) = _eventos_de(eventos, TIPO_BLOQUEO_REGLA)
    assert evento.regla == "V"
    assert estado.informes_pendientes == {}


def test_en_la_espera_de_la_categoria_el_informe_sigue_las_reglas_de_siempre():
    # Ni la espera lo rechaza ni lo deja pasar todo: un informe válido se acepta como siempre y
    # `habilitar` con una coincidencia se rechaza con I.2, como siempre.
    estado, _, hooks = _caso_con_comercio()
    estado.categoria_bloqueada = True
    entrada = _informe_del_caso(estado, "no_habilitar")
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    _comprobar_informe_aceptado(salida, entrada, estado)
    con_coincidencia, _, hooks_c = _caso_con_comercio()
    con_coincidencia.categoria_bloqueada = True
    con_coincidencia.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    habilitar = _informe_del_caso(con_coincidencia, "habilitar")
    rechazo = _rechazo(_ejecutar(_hook_del_informe(hooks_c), _pre(INFORME, habilitar)))
    assert {"regla": "I.2", "texto": MOTIVO_HABILITAR_CON_COINCIDENCIA} in rechazo["motivos"]


def test_con_el_sello_y_la_espera_el_informe_minimo_sigue_exigiendo_escalar_antes():
    estado, _, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Almacén Mirador"}
    _registro_con_varias_coincidencias(estado)
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    entrada = _informe_del_caso(estado, "decide_cumplimiento")
    salida = _ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada))
    assert _es_denegacion(salida)
    textos = [m["texto"] for m in _rechazo(salida)["motivos"]]
    assert textos == [motivo_de_escalar({"fallo_de_hook"})]  # sin el motivo de la espera
    estado.libro.escalamientos.append(
        Escalamiento(causas_vigentes(estado.libro), clave_comercio(estado))
    )
    assert not _es_denegacion(_ejecutar(_hook_del_informe(hooks), _pre(INFORME, entrada)))


# ---------------------------------- #10: la categoría delegada es la del analista (T020, FR-020)

SOLICITUD_CON_CATEGORIA = "Due diligence de Tienda Verde SAS, de suplementos dietarios."


def _delegar(hooks, entrada):
    return _ejecutar(_hook(hooks.coordinador(), "PreToolUse"), _pre(DELEGAR, entrada))


def test_una_categoria_que_no_esta_en_los_mensajes_se_bloquea_con_i3():
    from due_diligence.hooks import ACCION_DELEGAR_CATEGORIA
    from due_diligence.reglas import MOTIVO_CATEGORIA_NO_DEL_ANALISTA

    estado, eventos, hooks = _caso()
    estado.solicitud = SOLICITUD_CON_CATEGORIA
    salida = _delegar(hooks, {"frente": "categoria", "categoria": "ropa y accesorios"})
    assert _es_denegacion(salida) and _motivo(salida) == MOTIVO_CATEGORIA_NO_DEL_ANALISTA
    assert estado.categoria_bloqueada is True
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_BLOQUEO_REGLA and evento.regla == "I.3"
    assert evento.accion == ACCION_DELEGAR_CATEGORIA == "delegar_frente (categoria)"
    assert "ropa" not in evento.detalle and "Tienda Verde" not in evento.detalle


def test_una_categoria_de_los_mensajes_se_permite_y_quita_el_bloqueo():
    estado, eventos, hooks = _caso()
    estado.solicitud = SOLICITUD_CON_CATEGORIA
    estado.categoria_bloqueada = True
    salida = _delegar(hooks, {"frente": "categoria", "categoria": "Suplementos Dietarios"})
    assert salida == permitir()
    assert estado.categoria_bloqueada is False and eventos.eventos() == []


def test_la_categoria_dada_en_un_mensaje_posterior_se_permite():
    estado, _, hooks = _caso()
    estado.solicitud = "Due diligence de Taller Aurora SAS."
    assert _es_denegacion(_delegar(hooks, {"frente": "categoria", "categoria": "talleres"}))
    estado.mensajes.append("Es de talleres.")
    assert _delegar(hooks, {"frente": "categoria", "categoria": "talleres"}) == permitir()


def test_una_delegacion_de_categoria_sin_categoria_no_la_bloquea_el_hook():
    # La rechaza el `Delegador`, como desde el #6: lo fijan los tests de `test_delegacion.py` del
    # frente sin su dato. Aquí solo se comprueba que el hook la deja pasar sin marcar el bloqueo.
    estado, eventos, hooks = _caso()
    assert _delegar(hooks, {"frente": "categoria"}) == permitir()
    assert estado.categoria_bloqueada is False and eventos.eventos() == []


def test_con_el_sello_la_categoria_se_evalua_por_la_categoria_y_no_por_el_sello():
    estado, _, hooks = _caso()
    estado.solicitud = SOLICITUD_CON_CATEGORIA
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    ok = {"frente": "categoria", "categoria": "suplementos dietarios"}
    assert _delegar(hooks, ok) == permitir()
    otra = {"frente": "categoria", "categoria": "apuestas"}
    assert _es_denegacion(_delegar(hooks, otra))


def test_la_espera_de_categoria_de_extremo_a_extremo_en_el_stop():
    from due_diligence.eventos import TIPO_ESPERA_ANALISTA
    from due_diligence.reglas import MOTIVO_ESPERA_CATEGORIA

    estado, eventos, hooks = _caso_con_comercio()
    estado.solicitud = "Due diligence de Tienda Verde SAS."
    _delegar(hooks, {"frente": "categoria", "categoria": "suplementos dietarios"})
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()  # US4-4
    assert [e.detalle for e in eventos.eventos() if e.tipo == TIPO_ESPERA_ANALISTA] == [
        MOTIVO_ESPERA_CATEGORIA
    ]
    # Turno siguiente: el analista da la categoría, se delega y se consulta; ya no es espera.
    estado.mensajes.append("Es de suplementos dietarios.")
    assert _delegar(hooks, {"frente": "categoria", "categoria": "suplementos dietarios"}) == (
        permitir()
    )
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("suplementos dietarios", "alto"))
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida) and salida["reason"] == (
        motivo_de_escalar({"alto_riesgo"}) + " Luego registra el informe."
    )


# ------------------------- #10, parada A: la espera de la categoría no exime de escalar (FR-014)


def _espera_de_categoria_con_coincidencia():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    estado.categoria_bloqueada = True
    return estado, eventos, hooks


def test_a_con_una_coincidencia_la_espera_de_categoria_exige_escalar_y_gasta_una_devolucion():
    from due_diligence.eventos import TIPO_ESPERA_ANALISTA

    estado, eventos, hooks = _espera_de_categoria_con_coincidencia()
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida)
    assert salida["reason"] == motivo_de_escalar({"coincidencia_representante"})
    assert estado.libro.cierres_impedidos == 1
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_CIERRE_IMPEDIDO and evento.regla == "I.2"
    assert TIPO_ESPERA_ANALISTA not in [e.tipo for e in eventos.eventos()]


def test_b_ya_escalado_la_espera_de_categoria_se_admite_sin_el_informe():
    from due_diligence.eventos import TIPO_ESPERA_ANALISTA

    estado, eventos, hooks = _espera_de_categoria_con_coincidencia()
    estado.libro.escalamientos.append(
        Escalamiento(causas_vigentes(estado.libro), clave_comercio(estado))
    )
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert [e.tipo for e in eventos.eventos()] == [TIPO_ESPERA_ANALISTA]
    assert estado.libro.cierres_impedidos == 0 and estado.informes == []


def test_c_agotadas_las_devoluciones_la_espera_de_categoria_marca_cierre_sin_escalar():
    from due_diligence.coordinador import Caso as _CasoReal  # solo para `completo`

    estado, eventos, hooks = _espera_de_categoria_con_coincidencia()
    estado.libro.cierres_impedidos = MAX_CIERRES_IMPEDIDOS
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert estado.cierre_sin_escalar is True
    assert estado.cierre_sin_informe is False  # la espera de la categoría exime del informe
    assert _tipos_de_cierre(eventos) == [TIPO_CIERRE_SIN_ESCALAR]
    caso = _CasoReal()
    caso.estado = estado
    assert caso.completo is False


def test_d_con_el_sello_la_espera_de_categoria_exige_escalar():
    estado, _, hooks = _caso_con_comercio()
    estado.categoria_bloqueada = True
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida)
    assert salida["reason"] == motivo_de_escalar({"fallo_de_hook"})
    assert estado.libro.cierres_impedidos == 1


# ------------------------------------- #10: el PreToolUse del escalamiento (T034, R5, R6, R8)


def _denegado_por_resumen(salida):
    assert _es_denegacion(salida)
    rechazo = json.loads(_motivo(salida))
    assert rechazo["tipo"] == "resumen_rechazado" and rechazo["reintentable"] is False
    return rechazo


@pytest.mark.parametrize(
    ("cambio", "ruta"),
    [
        ({"hallazgos": {"registro": [{"texto": "x", "fuente": FUENTE_REGISTRO}]}}, "fecha"),
        (
            {"hallazgos": {"registro": [{"texto": "x", "fuente": "Otra", "fecha": "2026-09-30"}]}},
            "fuente",
        ),
        ({"hallazgos": {}}, "hallazgos.registro"),  # frente cubierto sin afirmación (US1-6)
        ({"accion_recomendada": ["x"]}, "accion_recomendada"),
    ],
)
def test_un_resumen_con_un_problema_se_rechaza_con_i4_y_lo_nombra(cambio, ruta):
    estado, eventos, hooks = _caso_con_comercio()
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, {**_escalamiento(), **cambio}))
    rechazo = _denegado_por_resumen(salida)
    assert any(p["ruta"].endswith(ruta) for p in rechazo["problemas"]), rechazo["problemas"]
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_BLOQUEO_REGLA and evento.regla == "I.4"
    assert evento.accion == "escalar_a_cumplimiento"
    assert estado.escalamientos_pendientes == {}


def test_us2_7_tras_un_resumen_rechazado_se_corrige_se_escala_y_el_caso_cierra():
    # FR-007: el rechazo no deja nada guardado, el coordinador corrige y vuelve a escalar en el
    # mismo caso, y ese escalamiento es el que cuenta para el cierre.
    estado, _, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    incompleto = {k: v for k, v in _escalamiento().items() if k != "accion_recomendada"}
    rechazo = _denegado_por_resumen(
        _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, incompleto))
    )
    assert any(p["ruta"] == "accion_recomendada" for p in rechazo["problemas"])
    assert estado.escalamientos_pendientes == {} and estado.libro.escalamientos == []
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida) and salida["reason"].startswith(
        motivo_de_escalar({"coincidencia_representante"})
    )

    _escalar_confirmado(hooks)
    assert estado.libro.escalamientos == [
        Escalamiento(
            frozenset({"coincidencia_representante"}), ("CO-TV-0001", "Tienda Verde SAS", True)
        )
    ]
    assert falta_para_cerrar(estado) == (False, True)  # escalado: solo falta el informe
    _aceptar_informe(hooks, "decide_cumplimiento", tool_use_id="t2")
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert estado.cierre_sin_escalar is False and estado.cierre_sin_informe is False


def test_un_resumen_valido_sustituye_lo_del_codigo_y_deja_pendiente_el_escalamiento():
    from due_diligence.conflictos import calcular_conflictos
    from due_diligence.reglas import causas_del_resumen

    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    # US2-4, FR-009: lo declarado es distinto en el comercio, la cobertura y la causa; lo que llega
    # a la pasarela es lo del código. El comercio declarado es otro, para que una entrada que
    # dejara pasar el del coordinador no coincida por casualidad con el del código.
    declarado = {
        **_escalamiento(),
        "comercio": {
            "identificador": "CO-ZZ-9999",
            "nombre": "Comercio Declarado SAS",
            "verificado": False,
        },
        "causa_escalamiento": "otra causa",
        "cobertura": "completa",
    }
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, declarado))
    sustituida = _sustituida(salida)
    assert sustituida["comercio"] == COMERCIO_VERIFICADO != declarado["comercio"]
    assert sustituida == {
        "comercio": COMERCIO_VERIFICADO,
        "hallazgos": declarado["hallazgos"],
        "cobertura": calcular_cobertura(estado).lineas(),
        "causa_escalamiento": ["coincidencia del representante legal en listas restrictivas"],
        "accion_recomendada": declarado["accion_recomendada"],
        "conflictos": calcular_conflictos(estado).como_entrada(),
    }
    assert sustituida["causa_escalamiento"] == causas_del_resumen(estado)
    assert [e.tipo for e in eventos.eventos()] == [
        TIPO_COBERTURA_SUSTITUIDA,
        TIPO_DATOS_SUSTITUIDOS,
    ]
    (pendiente,) = estado.escalamientos_pendientes.values()
    assert pendiente[0] == Escalamiento(
        frozenset({"coincidencia_representante"}), ("CO-TV-0001", "Tienda Verde SAS", True)
    )


@pytest.mark.parametrize(
    ("preparar", "esperadas"),
    [
        ("cobertura", ["Sin causa de escalamiento vigente: la cobertura está incompleta."]),
        ("categoria", ["Sin causa de escalamiento vigente: la categoría no quedó determinada."]),
        ("noticias", ["Sin causa de escalamiento vigente: hay menciones en noticias."]),
        (
            "conflicto",
            ["Sin causa de escalamiento vigente: hay conflictos entre las fuentes registrales."],
        ),
        (
            "comercio",
            [
                "Sin causa de escalamiento vigente: el comercio no está identificado de forma "
                "unívoca."
            ],
        ),
        (
            "dos",
            [
                "Sin causa de escalamiento vigente: la cobertura está incompleta.",
                "Sin causa de escalamiento vigente: la categoría no quedó determinada.",
            ],
        ),
    ],
)
def test_sin_causas_la_causa_lleva_una_linea_por_motivo(preparar, esperadas):
    # U1 del análisis: cada motivo solo, y dos a la vez, en su orden; ninguno repite datos.
    from due_diligence.reglas import causas_del_resumen

    estado = _estado_sin_causas(preparar)
    lineas = causas_del_resumen(estado)
    assert lineas == esperadas
    assert all("Tienda Verde" not in linea and "CO-TV" not in linea for linea in lineas)


def _estado_sin_causas(motivo):
    """Un caso sin causas donde se cumple exactamente `motivo` (o los dos primeros con «dos»)."""
    from due_diligence.estado import ResultadoFrente
    from due_diligence.simulacion import respuesta_del_contrato, terminacion_normal

    estado, _, _ = _caso_con_comercio()
    frentes = list(Frente) if motivo != "cobertura" and motivo != "dos" else [Frente.REGISTRO]
    for frente in frentes:
        if frente is not Frente.REGISTRO:
            estado.cambiar_situacion(frente, Situacion.EN_CURSO)
            estado.cambiar_situacion(frente, Situacion.TERMINADO)
    noticias = respuesta_del_contrato("sin_coincidencias", fuente="Noticias Ficticias")
    if motivo == "noticias":
        noticias = respuesta_del_contrato(
            "coincidencias", [{"titular": "Una noticia ficticia"}], fuente="Noticias Ficticias"
        )
    estado.guardar_resultado(
        ResultadoFrente(
            Frente.NOTICIAS,
            [consulta(Frente.NOTICIAS, {"identificador": "CO-TV-0001"}, noticias)],
            "",
            terminacion_normal(),
            "",
        )
    )
    if motivo not in ("categoria", "dos"):
        estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))
    if motivo == "conflicto":
        otra = {**comercio_alto_riesgo(), "fecha_constitucion": "2001-01-01"}
        estado.reiniciar_identificacion()
        estado.registrar_identificacion(
            {
                "resultado": "coincidencias",
                "hechos": [
                    {
                        "contenido": comercio_alto_riesgo(),
                        "metadatos": {"fuente": FUENTE_REGISTRO, "fecha": "2026-09-30"},
                    },
                    {
                        "contenido": otra,
                        "metadatos": {"fuente": "Otro Registro Ficticio", "fecha": "2026-09-28"},
                    },
                ],
                "coincidencias": ["CO-TV-0001"],
            }
        )
        estado.agregar_consultas(
            [
                consulta(
                    Frente.REGISTRO,
                    {"identificador": "CO-TV-0001"},
                    {
                        "resultado": "coincidencias",
                        "hechos": [
                            {
                                "contenido": comercio_alto_riesgo(),
                                "metadatos": {"fuente": FUENTE_REGISTRO, "fecha": "2026-09-30"},
                            },
                            {
                                "contenido": otra,
                                "metadatos": {
                                    "fuente": "Otro Registro Ficticio",
                                    "fecha": "2026-09-28",
                                },
                            },
                        ],
                        "coincidencias": ["CO-TV-0001"],
                        "metadatos": {"fuentes": [FUENTE_REGISTRO], "fecha": "2026-09-30"},
                    },
                )
            ]
        )
    if motivo == "comercio":
        estado.reiniciar_identificacion()
        estado.registrar_identificacion({"hola": 1})  # registro terminado, sin comercio
    return estado


def test_sin_comercio_identificado_ni_pedido_el_escalamiento_se_rechaza_pidiendo_el_registro():
    # D2 del plan: el oficial no puede recibir un caso sin comercio.
    from due_diligence.reglas import MOTIVO_SIN_COMERCIO_ESCALAMIENTO

    estado, eventos, hooks = _caso()
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("suplementos dietarios", "alto"))
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento({})))
    rechazo = _denegado_por_resumen(salida)
    assert {"regla": None, "texto": MOTIVO_SIN_COMERCIO_ESCALAMIENTO} in rechazo["motivos"]
    assert MOTIVO_SIN_COMERCIO_ESCALAMIENTO == (
        "Delegue primero el registro mercantil: el oficial necesita saber de qué comercio se trata."
    )


def _post_escalado(hooks, identificador="ESC-0001", tool_use_id="t1"):
    escalado = respuesta_de_decision("caso_escalado", identificador)
    entrada = _post_de(ESCALAR, escalado, {})
    entrada["tool_use_id"] = tool_use_id
    return _ejecutar(_hook(hooks.coordinador(), "PostToolUse"), entrada)


def test_el_post_confirma_las_causas_del_pre_y_no_las_del_momento():
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("suplementos dietarios", "alto"))
    _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento()))
    # Una causa nueva entre los dos hooks: no la cubre este escalamiento.
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    _post_escalado(hooks)
    assert estado.libro.escalamientos == [
        Escalamiento(frozenset({"alto_riesgo"}), ("CO-TV-0001", "Tienda Verde SAS", True))
    ]
    assert estado.escalamientos_pendientes == {}
    evento = eventos.eventos()[-1]
    assert evento.tipo == TIPO_ESCALAMIENTO_REGISTRADO
    assert evento.detalle == (
        "Escalamiento ESC-0001 registrado; cubre: categoría de alto riesgo; cobertura "
        "incompleta, 1 de 4 frentes; 1 afirmaciones."
    )
    from due_diligence.reglas import escalamiento_cubre

    assert escalamiento_cubre(estado.libro) is False  # la coincidencia nueva sigue sin cubrir


def test_el_post_con_otra_respuesta_y_el_fallo_descartan_lo_pendiente():
    estado, eventos, hooks = _caso_con_comercio()
    _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento()))
    otro = respuesta_de_decision("informe_registrado", "INF-0001")
    _ejecutar(_hook(hooks.coordinador(), "PostToolUse"), _post_de(ESCALAR, otro, {}))
    assert estado.escalamientos_pendientes == {} and estado.libro.escalamientos == []
    _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento()))
    error = error_estructurado("entrada_invalida", False)
    _ejecutar(_hook(hooks.coordinador(), "PostToolUseFailure"), _fallo(error, nombre=ESCALAR))
    assert estado.escalamientos_pendientes == {} and estado.libro.escalamientos == []
    assert eventos.eventos()[-1].tipo == TIPO_CONSULTA_FALLIDA


def test_un_segundo_escalamiento_sin_causa_nueva_deja_el_mismo_evento():
    # U2 del análisis (R8): no hay un tipo de evento distinto.
    estado, eventos, hooks = _caso_con_comercio()
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("suplementos dietarios", "alto"))
    for numero in (1, 2):
        _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento()))
        _post_escalado(hooks, f"ESC-000{numero}")
    registrados = [e for e in eventos.eventos() if e.tipo == TIPO_ESCALAMIENTO_REGISTRADO]
    assert [e.detalle.split(" registrado")[0] for e in registrados] == [
        "Escalamiento ESC-0001",
        "Escalamiento ESC-0002",
    ]
    assert len(estado.libro.escalamientos) == 2


# ------------------------------------------- #10: el sello y los fallos (T036, R5, FR-012, D2)


@pytest.mark.parametrize("comercio", ["identificado", "pedido", "ninguno"])
def test_con_el_sello_el_escalamiento_pasa_con_textos_fijos_y_el_comercio_que_haya(comercio):
    from due_diligence.conflictos import no_calculados
    from servidor_mcp.informe import COMERCIO_NO_IDENTIFICADO, validar_resumen

    if comercio == "identificado":
        estado, eventos, hooks = _caso_con_comercio()
        esperado = COMERCIO_VERIFICADO
    else:
        estado, eventos, hooks = _caso()
        esperado = COMERCIO_NO_IDENTIFICADO
        if comercio == "pedido":
            estado.comercio_pedido = {"identificador": "CO-TV-0001", "nombre": None}
            esperado = {"identificador": "CO-TV-0001", "nombre": None, "verificado": False}
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    entrada = _escalamiento(hallazgos={"registro": [{"texto": "x"}]})  # ni se validan las fuentes
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, entrada))
    assert not _es_denegacion(salida)
    sustituida = _sustituida(salida)
    assert sustituida["comercio"] == esperado
    assert sustituida["cobertura"] == [COBERTURA_NO_CALCULADA]
    assert sustituida["conflictos"] == no_calculados().como_entrada()
    assert sustituida["causa_escalamiento"] == ["fallo de un hook de verificación"]
    if comercio == "ninguno":
        # D2: el comercio fijo pasa la forma; la afirmación sin fuente y fecha la rechazaría la
        # pasarela, que es la que valida la forma con el sello.
        assert validar_resumen({**sustituida, "hallazgos": {}}) == []


def test_con_el_sello_durante_la_espera_del_identificador_se_escala_y_despues_el_informe_minimo():
    estado, _, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Almacén Mirador"}
    _registro_con_varias_coincidencias(estado)
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento({})))
    assert not _es_denegacion(salida)
    _post_escalado(hooks)
    informe = {**_informe_de("decide_cumplimiento"), "hallazgos": afirmaciones_del_caso(estado)}
    assert not _es_denegacion(_ejecutar(_hook_del_informe(hooks), _pre(INFORME, informe)))


def test_una_excepcion_sin_comercio_calculable_deja_pasar_el_comercio_fijo(monkeypatch):
    from servidor_mcp.informe import COMERCIO_NO_IDENTIFICADO, validar_resumen

    estado, eventos, hooks = _caso_con_comercio()

    def roto(estado):
        raise RuntimeError(TEXTO_INTERNO)

    monkeypatch.setattr(modulo_hooks, "calcular_cobertura", roto)
    monkeypatch.setattr(modulo_hooks, "comercio_del_informe", roto)
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento({})))
    assert not _es_denegacion(salida)
    sustituida = _sustituida(salida)
    assert sustituida["comercio"] == COMERCIO_NO_IDENTIFICADO
    assert validar_resumen(sustituida) == []
    assert estado.libro.fallo_de_hook is not None
    assert all(TEXTO_INTERNO not in e.detalle for e in eventos.eventos())


# ------------------------------- #10: escalar con criterio en el hook (T041, R5 pasos 2 y 3, D3)


def _bajo_riesgo_en_el_hook():
    """El caso (b) comprobado sobre `_caso`: los cuatro frentes y sin hallazgos (FR-002)."""
    from due_diligence.estado import ResultadoFrente
    from due_diligence.libro import ConsultaListas
    from due_diligence.simulacion import (
        comercio_bajo_riesgo,
        respuesta_del_contrato,
        terminacion_normal,
    )

    estado, eventos, hooks = _caso()
    _registro_terminado(estado)
    respuesta = respuesta_registro(comercio_bajo_riesgo())
    estado.registrar_identificacion(respuesta)
    estado.agregar_consultas(
        [consulta(Frente.REGISTRO, {"identificador": "CO-TA-0002"}, respuesta)]
    )
    for frente in (Frente.NOTICIAS, Frente.CATEGORIA, Frente.LISTAS):
        estado.cambiar_situacion(frente, Situacion.EN_CURSO)
        estado.cambiar_situacion(frente, Situacion.TERMINADO)
    noticias = respuesta_del_contrato("sin_coincidencias", fuente="Noticias Ficticias")
    estado.guardar_resultado(
        ResultadoFrente(
            Frente.NOTICIAS,
            [consulta(Frente.NOTICIAS, {"identificador": "CO-TA-0002"}, noticias)],
            "",
            terminacion_normal(),
            "",
        )
    )
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))
    estado.libro.consultas_listas = [
        ConsultaListas("comercio", None, "CO-TA-0002", "sin_coincidencias"),
        ConsultaListas("persona", None, "PE-0002", "sin_coincidencias"),
    ]
    return estado, eventos, hooks


def test_escalar_un_bajo_riesgo_sin_hallazgos_comprobado_se_rechaza_con_v():
    from due_diligence.reglas import MOTIVO_SIN_CAUSA

    estado, eventos, hooks = _bajo_riesgo_en_el_hook()
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento({})))
    rechazo = _denegado_por_resumen(salida)
    assert rechazo["motivos"] == [{"regla": "V", "texto": MOTIVO_SIN_CAUSA}]
    assert rechazo["problemas"] == []  # el rechazo por criterio va antes que la forma
    (evento,) = eventos.eventos()
    assert evento.tipo == TIPO_BLOQUEO_REGLA and evento.regla == "V"
    assert evento.accion == "escalar_a_cumplimiento"
    assert estado.escalamientos_pendientes == {}


@pytest.mark.parametrize(
    ("preparar", "motivo"),
    [
        (_registro_con_varias_coincidencias, "MOTIVO_ESPERA_IDENTIFICADOR"),
        (_registro_sin_coincidencias, "MOTIVO_ESPERA_NOMBRE"),
    ],
)
def test_escalar_durante_la_espera_del_registro_se_rechaza_tambien_con_alto_riesgo(
    preparar, motivo
):
    # FR-016 y D3 del plan: sin identificar al comercio no se escala, ni con alto riesgo.
    from due_diligence import reglas

    estado, eventos, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Almacén Mirador"}
    preparar(estado)
    _con_alto_riesgo(estado)
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento({})))
    rechazo = _denegado_por_resumen(salida)
    assert rechazo["motivos"] == [{"regla": "V", "texto": getattr(reglas, motivo)}]
    assert eventos.eventos()[-1].regla == "V"


def test_con_el_sello_la_espera_no_impide_escalar():
    # El orden de R5: el sello va antes que la espera (excepción de FR-016).
    estado, _, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Almacén Mirador"}
    _registro_con_varias_coincidencias(estado)
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento({})))
    assert not _es_denegacion(salida)


def _espera_del_registro_con_coincidencia(preparar):
    """D1: el libro conserva la coincidencia de otro comercio y el caso espera al analista."""
    estado, eventos, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Almacén Mirador"}
    preparar(estado)
    estado.libro.coincidencias.append(Coincidencia("comercio", "L", "F", "2026-09-30"))
    return estado, eventos, hooks


ESPERAS_DEL_REGISTRO = [_registro_con_varias_coincidencias, _registro_sin_coincidencias]


@pytest.mark.parametrize("preparar", ESPERAS_DEL_REGISTRO)
def test_i2_la_espera_del_registro_no_exime_de_escalar_una_coincidencia(preparar):
    # Hallazgo de la auditoría del #10: la regla I.2 no espera al identificador del comercio nuevo.
    from due_diligence.eventos import TIPO_ESPERA_ANALISTA

    estado, eventos, hooks = _espera_del_registro_con_coincidencia(preparar)
    salida = _ejecutar(_stop(hooks), _fin_de_turno())
    assert _es_bloqueo(salida)
    assert salida["reason"] == motivo_de_escalar({"coincidencia_comercio"})  # sin el informe
    assert estado.libro.cierres_impedidos == 1
    (evento,) = _eventos_de(eventos, TIPO_CIERRE_IMPEDIDO)
    assert evento.regla == "I.2"
    assert _eventos_de(eventos, TIPO_ESPERA_ANALISTA) == []


@pytest.mark.parametrize("preparar", ESPERAS_DEL_REGISTRO)
def test_i2_agotadas_las_devoluciones_en_la_espera_del_registro_marca_cierre_sin_escalar(preparar):
    estado, eventos, hooks = _espera_del_registro_con_coincidencia(preparar)
    estado.libro.cierres_impedidos = MAX_CIERRES_IMPEDIDOS
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert estado.cierre_sin_escalar is True
    assert estado.cierre_sin_informe is False  # la espera del registro exime del informe
    assert _tipos_de_cierre(eventos) == [TIPO_CIERRE_SIN_ESCALAR]


@pytest.mark.parametrize("preparar", ESPERAS_DEL_REGISTRO)
def test_i2_en_la_espera_del_registro_la_coincidencia_se_escala_y_luego_se_espera(preparar):
    from due_diligence.eventos import TIPO_ESPERA_ANALISTA

    estado, eventos, hooks = _espera_del_registro_con_coincidencia(preparar)
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento()))
    assert not _es_denegacion(salida)
    sustituida = _sustituida(salida)
    assert sustituida["comercio"] == {
        "identificador": None,
        "nombre": "Almacén Mirador",
        "verificado": False,
    }
    assert sustituida["causa_escalamiento"] == ["coincidencia del comercio en listas restrictivas"]
    escalado = respuesta_de_decision("caso_escalado", "ESC-0001")
    _ejecutar(
        _hook(hooks.coordinador(), "PostToolUse"), _post_de(ESCALAR, escalado, _sustituida(salida))
    )
    assert _ejecutar(_stop(hooks), _fin_de_turno()) == permitir()
    assert len(_eventos_de(eventos, TIPO_ESPERA_ANALISTA)) == 1
    assert estado.libro.cierres_impedidos == 0 and estado.cierre_sin_escalar is False


def test_la_espera_va_antes_que_la_forma_y_el_bajo_riesgo_antes_que_la_forma():
    from due_diligence.reglas import MOTIVO_ESPERA_IDENTIFICADOR, MOTIVO_SIN_CAUSA

    estado, _, hooks = _caso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Almacén Mirador"}
    _registro_con_varias_coincidencias(estado)
    mal_formado = {**_escalamiento({}), "accion_recomendada": ["x"]}
    rechazo = _denegado_por_resumen(
        _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, mal_formado))
    )
    assert rechazo["motivos"] == [{"regla": "V", "texto": MOTIVO_ESPERA_IDENTIFICADOR}]
    assert rechazo["problemas"] == []
    _, _, hooks_b = _bajo_riesgo_en_el_hook()
    rechazo = _denegado_por_resumen(
        _ejecutar(_hook_del_escalamiento(hooks_b), _pre(ESCALAR, mal_formado))
    )
    assert rechazo["motivos"] == [{"regla": "V", "texto": MOTIVO_SIN_CAUSA}]
    assert rechazo["problemas"] == []  # ni rastro de la forma: el criterio va antes


def test_en_la_espera_de_la_categoria_el_escalamiento_se_admite():
    estado, _, hooks = _caso_con_comercio()
    estado.categoria_bloqueada = True
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, _escalamiento()))
    assert not _es_denegacion(salida)


def test_un_bajo_riesgo_con_una_mencion_en_noticias_se_puede_escalar():
    # US1-7: no es de bajo riesgo sin hallazgos comprobado; escalar se admite (y no se exige).
    from due_diligence.estado import ResultadoFrente
    from due_diligence.simulacion import consulta_listas, respuesta_del_contrato, terminacion_normal

    estado, _, hooks = _bajo_riesgo_en_el_hook()
    mencion = respuesta_del_contrato(
        "coincidencias", [{"titular": "Una noticia ficticia"}], fuente="Noticias Ficticias"
    )
    estado.guardar_resultado(
        ResultadoFrente(
            Frente.NOTICIAS,
            [consulta(Frente.NOTICIAS, {"identificador": "CO-TA-0002"}, mencion)],
            "",
            terminacion_normal(),
            "",
        )
    )
    estado.agregar_consultas(
        [
            consulta(Frente.NOTICIAS, {"identificador": "CO-TA-0002"}, mencion),
            consulta(Frente.CATEGORIA, {"categoria": "talleres"}),
            consulta_listas("comercio", identificador="CO-TA-0002"),
        ]
    )
    resumen = _escalamiento(hallazgos=afirmaciones_del_caso(estado))
    salida = _ejecutar(_hook_del_escalamiento(hooks), _pre(ESCALAR, resumen))
    assert not _es_denegacion(salida), _motivo(salida) if _es_denegacion(salida) else ""
    assert _sustituida(salida)["causa_escalamiento"] == [
        "Sin causa de escalamiento vigente: hay menciones en noticias."
    ]
