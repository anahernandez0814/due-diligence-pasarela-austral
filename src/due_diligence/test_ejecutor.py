"""Tests del ejecutor de subagentes (R5, R6, contrato `caso.md`).

`EjecutorSDK` recibe la función de consulta; aquí se le da un flujo de mensajes del SDK simulado.
Ninguno de estos tests llama al modelo.
"""

import asyncio
import json

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk._errors import ResultError

from due_diligence.ejecutor import EjecutorSDK
from due_diligence.frentes import Frente
from due_diligence.terminacion import Terminacion

HERRAMIENTA = "mcp__pasarela__consultar_registro_mercantil"

RESULTADO_DEL_CONTRATO = {
    "resultado": "coincidencias",
    "coincidencias": ["CO-TV-0001"],
    "hechos": [
        {
            "contenido": {
                "identificador": "CO-TV-0001",
                "nombre": "Tienda Verde SAS",
                "estado": "activo",
            },
            "metadatos": {"fuente": "Registro Mercantil Ficticio del Sur", "fecha": "2026-09-30"},
        }
    ],
    "metadatos": {"fuentes": ["Registro Mercantil Ficticio del Sur"], "fecha": "2026-09-30"},
}

ERROR_DE_LA_PASARELA = {
    "error": True,
    "tipo": "servicio_no_disponible",
    "mensaje": "El servicio de noticias no responde.",
    "reintentable": True,
    "obtenido": {},
}


def _uso(id_, argumentos, nombre=HERRAMIENTA):
    return AssistantMessage(content=[ToolUseBlock(id_, nombre, argumentos)], model="simulado")


def _respuesta_de_herramienta(id_, contenido, es_error=None):
    return UserMessage(content=[ToolResultBlock(id_, contenido, es_error)])


def _texto(texto):
    return AssistantMessage(content=[TextBlock(texto)], model="simulado")


def _fin(subtype="success", stop_reason="end_turn", is_error=False, terminal="completed"):
    return ResultMessage(
        subtype=subtype,
        duration_ms=1,
        duration_api_ms=1,
        is_error=is_error,
        num_turns=1,
        session_id="sesion-de-prueba",
        stop_reason=stop_reason,
        terminal_reason=terminal,
    )


def _consulta(mensajes, error_final=None):
    """Una función de consulta que entrega los mensajes y, si se pide, lanza una excepción."""
    llamadas = []

    async def consulta(*, prompt, options=None):
        llamadas.append((prompt, options))
        for mensaje in mensajes:
            yield mensaje
        if error_final is not None:
            raise error_final

    consulta.llamadas = llamadas
    return consulta


def _ejecutar(
    mensajes, error_final=None, frente=Frente.REGISTRO, contexto="contexto", opciones=None
):
    consulta = _consulta(mensajes, error_final)
    resultado = asyncio.run(EjecutorSDK(consulta=consulta)(frente, contexto, opciones))
    return resultado, consulta


def test_una_consulta_con_resultado_del_contrato_queda_con_contenido_y_metadatos_separados():
    resultado, _ = _ejecutar(
        [
            _uso("t1", {"identificador": "CO-TV-0001"}),
            _respuesta_de_herramienta("t1", json.dumps(RESULTADO_DEL_CONTRATO)),
            _texto("CO-TV-0001 existe y está activo."),
            _fin(),
        ]
    )
    assert len(resultado.consultas) == 1
    consulta = resultado.consultas[0]
    assert consulta.frente is Frente.REGISTRO
    assert consulta.herramienta == HERRAMIENTA
    assert consulta.argumentos == {"identificador": "CO-TV-0001"}
    assert consulta.valido is True and consulta.error is None
    assert consulta.resultado == RESULTADO_DEL_CONTRATO  # tal como llegó, sin reescribir
    hecho = consulta.resultado["hechos"][0]
    assert "fuente" not in hecho["contenido"] and "fecha" not in hecho["contenido"]
    assert hecho["metadatos"]["fuente"] and hecho["metadatos"]["fecha"]
    assert resultado.terminacion.terminacion is Terminacion.NORMAL


def test_el_contenido_como_lista_de_bloques_de_texto_tambien_se_interpreta():
    bloques = [{"type": "text", "text": json.dumps(RESULTADO_DEL_CONTRATO)}]
    resultado, _ = _ejecutar(
        [
            _uso("t1", {"identificador": "CO-TV-0001"}),
            _respuesta_de_herramienta("t1", bloques),
            _fin(),
        ]
    )
    assert resultado.consultas[0].valido is True
    assert resultado.consultas[0].resultado == RESULTADO_DEL_CONTRATO


def test_un_resultado_que_no_es_json_queda_invalido_sin_resultado():
    resultado, _ = _ejecutar(
        [_uso("t1", {"nombre": "x"}), _respuesta_de_herramienta("t1", "esto no es json"), _fin()]
    )
    consulta = resultado.consultas[0]
    assert consulta.resultado is None and consulta.valido is False and consulta.error is None


def test_un_json_sin_la_forma_del_contrato_queda_invalido():
    resultado, _ = _ejecutar(
        [
            _uso("t1", {"nombre": "x"}),
            _respuesta_de_herramienta("t1", json.dumps({"hola": 1})),
            _fin(),
        ]
    )
    consulta = resultado.consultas[0]
    assert consulta.resultado is None and consulta.valido is False and consulta.error is None


def test_el_error_estructurado_de_la_pasarela_se_conserva_con_su_reintentable():
    resultado, _ = _ejecutar(
        [
            _uso("t1", {"nombre": "Tienda Verde SAS"}, "mcp__pasarela__buscar_noticias"),
            _respuesta_de_herramienta("t1", json.dumps(ERROR_DE_LA_PASARELA), es_error=True),
            _fin(),
        ],
        frente=Frente.NOTICIAS,
    )
    consulta = resultado.consultas[0]
    assert consulta.error == ERROR_DE_LA_PASARELA  # tal como llegó
    assert consulta.error["reintentable"] is True
    assert consulta.error["tipo"] == "servicio_no_disponible"
    assert consulta.resultado is None and consulta.valido is False


def test_el_error_se_reconoce_aunque_is_error_no_venga_marcado():
    resultado, _ = _ejecutar(
        [
            _uso("t1", {"nombre": "x"}),
            _respuesta_de_herramienta("t1", json.dumps(ERROR_DE_LA_PASARELA), es_error=None),
            _fin(),
        ]
    )
    assert resultado.consultas[0].error == ERROR_DE_LA_PASARELA


def test_un_error_que_no_es_json_con_is_error_no_se_pierde():
    resultado, _ = _ejecutar(
        [
            _uso("t1", {"nombre": "x"}),
            _respuesta_de_herramienta("t1", "Fallo de la herramienta", True),
            _fin(),
        ]
    )
    error = resultado.consultas[0].error
    assert error is not None and error["mensaje"] == "Fallo de la herramienta"
    assert error["reintentable"] is False


def test_las_consultas_conservan_el_orden_y_el_texto_solo_llena_el_resumen():
    resultado, _ = _ejecutar(
        [
            _uso("t1", {"tipo": "comercio", "identificador": "CO-TV-0001"}, "mcp__pasarela__x"),
            _uso("t2", {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo"}, "mcp__pasarela__x"),
            _respuesta_de_herramienta("t1", json.dumps(RESULTADO_DEL_CONTRATO)),
            _respuesta_de_herramienta("t2", json.dumps(RESULTADO_DEL_CONTRATO)),
            _texto("Sin coincidencias en ninguna lista."),
            _fin(),
        ],
        frente=Frente.LISTAS,
    )
    assert [c.argumentos["tipo"] for c in resultado.consultas] == ["comercio", "persona"]
    assert resultado.resumen == "Sin coincidencias en ninguna lista."
    assert all(c.frente is Frente.LISTAS for c in resultado.consultas)


def test_un_resultado_sin_consulta_conocida_se_conserva_sin_herramienta():
    resultado, _ = _ejecutar(
        [_respuesta_de_herramienta("desconocido", json.dumps(RESULTADO_DEL_CONTRATO)), _fin()]
    )
    assert resultado.consultas[0].herramienta == "" and resultado.consultas[0].argumentos == {}


def test_el_texto_del_modelo_no_cambia_la_terminacion():
    resultado, _ = _ejecutar([_texto("listo, terminé todo"), _fin(stop_reason="max_tokens")])
    assert resultado.terminacion.terminacion is Terminacion.ANOMALA
    assert resultado.resumen == "listo, terminé todo"


def test_el_detalle_de_la_terminacion_lleva_los_valores_originales():
    resultado, _ = _ejecutar([_fin()])
    assert "subtype=success" in resultado.detalle_terminacion
    assert "stop_reason=end_turn" in resultado.detalle_terminacion


def test_si_el_sdk_lanza_result_error_despues_del_resultado_no_se_vuelve_a_clasificar():
    # Medido en R14: con error_max_turns llega el ResultMessage y después la excepción.
    error = ResultError(
        "Reached maximum number of turns",
        data={
            "subtype": "error_during_execution",
            "stop_reason": "end_turn",
            "terminal_reason": "x",
        },
        exit_code=1,
    )
    resultado, _ = _ejecutar(
        [
            _fin(
                subtype="error_max_turns",
                stop_reason="tool_use",
                is_error=True,
                terminal="max_turns",
            )
        ],
        error_final=error,
    )
    assert resultado.terminacion.terminacion is Terminacion.LIMITE_SEGURIDAD
    assert "error_max_turns" in resultado.detalle_terminacion


def test_result_error_sin_resultado_previo_se_clasifica_con_la_excepcion():
    error = ResultError(
        "API Error",
        data={"subtype": "success", "stop_reason": "end_turn", "terminal_reason": "api_error"},
        exit_code=1,
    )
    resultado, _ = _ejecutar([_texto("parcial")], error_final=error)
    assert resultado.terminacion.terminacion is Terminacion.ANOMALA
    assert "api_error" in resultado.detalle_terminacion


def test_un_flujo_sin_mensaje_de_resultado_es_anomalo():
    resultado, _ = _ejecutar([_texto("sin cierre")])
    assert resultado.terminacion.terminacion is Terminacion.ANOMALA


def test_las_opciones_y_el_prompt_se_pasan_sin_modificar():
    opciones = object()
    _, consulta = _ejecutar([_fin()], contexto="el contexto exacto", opciones=opciones)
    assert consulta.llamadas == [("el contexto exacto", opciones)]
