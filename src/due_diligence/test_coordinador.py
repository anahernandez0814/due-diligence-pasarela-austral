"""Tests del coordinador y del caso (contrato `caso.md`, FR-001, FR-002, FR-013, SC-001).

El `query()` del coordinador y el ejecutor de los subagentes son simulados: estos tests validan
el cableado (herramientas, delegación, estado, terminación), no lo que decidiría el modelo.
"""

import asyncio

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
from claude_agent_sdk._errors import ResultError

from due_diligence import configuracion
from due_diligence.coordinador import (
    INSTRUCCIONES_COORDINADOR,
    PROHIBICION_DECISION,
    Caso,
    ejecutar_caso,
)
from due_diligence.estado import Situacion
from due_diligence.eventos import TIPO_CASO_INICIADO, TIPO_TERMINACION
from due_diligence.frentes import FRENTES, Frente
from due_diligence.simulacion import EjecutorSimulado
from due_diligence.terminacion import Terminacion

SOLICITUD = (
    "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren "
    "procesar ventas en línea de suplementos dietarios y estiman unos $80.000.000 mensuales. "
    "¿Lo podemos habilitar esta semana?"
)

DELEGACIONES_DEL_EJEMPLO = [
    {"frente": "registro", "identificador": "CO-TV-0001"},
    {"frente": "noticias", "identificador": "CO-TV-0001"},
    {"frente": "categoria", "categoria": "suplementos dietarios"},
]


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


def _coordinador_simulado(
    delegaciones, fin=None, error_final=None, texto="Resumen para el analista."
):
    """Un `query()` del coordinador que delega como lo haría el SDK y termina como se le diga."""
    llamadas = []
    caso_ref = {}

    async def consulta(*, prompt, options=None):
        llamadas.append((prompt, options))
        if delegaciones:
            delegador = caso_ref["caso"].delegador
            independientes = [d for d in delegaciones if d["frente"] != "listas"]
            await asyncio.gather(*(delegador.delegar(d) for d in independientes))
            for entrada in (d for d in delegaciones if d["frente"] == "listas"):
                await delegador.delegar(entrada)
        yield AssistantMessage(content=[TextBlock(texto)], model="simulado")
        yield fin or _fin()
        if error_final is not None:
            raise error_final

    consulta.llamadas = llamadas
    consulta.caso_ref = caso_ref
    return consulta


def _caso(
    delegaciones,
    *,
    ejecutor=None,
    fin=None,
    error_final=None,
    texto="Resumen para el analista.",
    **kwargs,
):
    ejecutor = ejecutor or EjecutorSimulado()
    consulta = _coordinador_simulado(delegaciones, fin=fin, error_final=error_final, texto=texto)
    caso = Caso(ejecutor=ejecutor, consulta=consulta, **kwargs)
    consulta.caso_ref["caso"] = caso
    return caso, ejecutor, consulta


# ------------------------------------------------------------------ herramientas (FR-002)


def test_las_herramientas_del_coordinador_son_exactamente_las_de_r3():
    caso, _, _ = _caso([])
    opciones = caso.opciones_coordinador()
    assert set(opciones.allowed_tools) == {
        "mcp__delegacion__delegar_frente",
        "mcp__pasarela__registrar_informe",
        "mcp__pasarela__escalar_a_cumplimiento",
    }
    assert set(opciones.disallowed_tools) == {
        "mcp__pasarela__consultar_registro_mercantil",
        "mcp__pasarela__consultar_listas_restrictivas",
        "mcp__pasarela__buscar_noticias",
        "mcp__pasarela__consultar_riesgo_categoria",
    }
    assert opciones.tools == [] and opciones.setting_sources == []


def test_la_instruccion_del_coordinador_prohibe_registrar_y_escalar_pero_las_herramientas_siguen():
    caso, _, _ = _caso([])
    opciones = caso.opciones_coordinador()
    assert PROHIBICION_DECISION in opciones.system_prompt
    assert opciones.system_prompt == INSTRUCCIONES_COORDINADOR
    assert (
        "registrar_informe" in PROHIBICION_DECISION
        and "escalar_a_cumplimiento" in PROHIBICION_DECISION
    )
    assert "NO llames" in PROHIBICION_DECISION
    # FR-002: no se le quitan las herramientas, solo se le instruye.
    assert "mcp__pasarela__registrar_informe" in opciones.allowed_tools
    assert "mcp__pasarela__escalar_a_cumplimiento" in opciones.allowed_tools


def test_las_instrucciones_piden_delegar_juntos_los_frentes_independientes_y_no_inventar_datos():
    texto = INSTRUCCIONES_COORDINADOR
    assert "delegar_frente" in texto
    assert "en la misma respuesta" in texto
    assert "inventes" in texto
    assert "no elijas" in texto


def test_las_opciones_del_coordinador_llevan_el_servidor_de_delegacion_del_caso():
    caso, _, _ = _caso([])
    opciones = caso.opciones_coordinador()
    assert set(opciones.mcp_servers) == {"pasarela", "delegacion"}
    assert caso.delegador.estado is caso.estado


# ------------------------------------------------------------------ el ejemplo (SC-001)


def test_el_ejemplo_delega_los_cuatro_frentes_con_los_datos_de_la_solicitud():
    caso, ejecutor, consulta = _caso([*DELEGACIONES_DEL_EJEMPLO, {"frente": "listas"}])
    asyncio.run(caso.ejecutar(SOLICITUD))

    assert sorted(llamada.frente.value for llamada in ejecutor.llamadas) == [
        "categoria",
        "listas",
        "noticias",
        "registro",
    ]
    contexto = {llamada.frente: llamada.contexto for llamada in ejecutor.llamadas}
    assert "CO-TV-0001" in contexto[Frente.REGISTRO]
    assert "CO-TV-0001" in contexto[Frente.NOTICIAS]
    assert "suplementos dietarios" in contexto[Frente.CATEGORIA]
    assert "CO-TV-0001" in contexto[Frente.LISTAS]
    for frente in Frente:
        assert caso.estado.situacion(frente) is Situacion.TERMINADO
    assert consulta.llamadas[0][0] == SOLICITUD  # el coordinador recibe la solicitud tal cual
    assert caso.estado.solicitud == SOLICITUD


def test_ningun_subagente_recibe_la_solicitud_del_analista():
    caso, ejecutor, _ = _caso([*DELEGACIONES_DEL_EJEMPLO, {"frente": "listas"}])
    asyncio.run(caso.ejecutar(SOLICITUD))
    for llamada in ejecutor.llamadas:
        assert "80.000.000" not in llamada.contexto and "habilitar" not in llamada.contexto


def test_la_solicitud_sin_datos_no_delega_ningun_frente():
    caso, ejecutor, _ = _caso([], texto="¿Cuál es el nombre o el identificador del comercio?")
    respuesta = asyncio.run(caso.ejecutar("Necesito un due diligence."))
    assert ejecutor.llamadas == []
    assert all(s is Situacion.SIN_INICIAR for s in caso.estado.frentes.values())
    assert "identificador" in respuesta
    assert caso.terminacion.terminacion is Terminacion.NORMAL


def test_delegar_sin_datos_se_rechaza_aunque_el_coordinador_lo_intente():
    caso, ejecutor, _ = _caso(
        [{"frente": "registro"}, {"frente": "noticias"}, {"frente": "categoria"}]
    )
    asyncio.run(caso.ejecutar("Necesito un due diligence."))
    assert ejecutor.llamadas == []
    assert {
        caso.estado.situacion(f) for f in (Frente.REGISTRO, Frente.NOTICIAS, Frente.CATEGORIA)
    } == {Situacion.RECHAZADO}


# ------------------------------------------------------------------ terminación (R5)


def test_la_terminacion_normal_queda_en_el_estado_y_como_evento():
    caso, _, _ = _caso(DELEGACIONES_DEL_EJEMPLO)
    respuesta = asyncio.run(caso.ejecutar(SOLICITUD))
    assert respuesta == "Resumen para el analista."
    assert caso.respuesta == respuesta
    assert caso.terminacion is caso.estado.terminacion
    assert caso.terminacion.terminacion is Terminacion.NORMAL
    eventos = caso.eventos()
    assert eventos[0].tipo == TIPO_CASO_INICIADO
    assert eventos[-1].tipo == TIPO_TERMINACION and "end_turn" in eventos[-1].detalle
    assert [e.secuencia for e in eventos] == sorted(e.secuencia for e in eventos)


def test_max_tokens_del_coordinador_es_anomala_y_queda_registrada():
    caso, _, _ = _caso([], fin=_fin(stop_reason="max_tokens"), texto="listo")
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.terminacion.terminacion is Terminacion.ANOMALA
    assert "max_tokens" in caso.eventos()[-1].detalle


def test_el_limite_de_seguridad_y_la_result_error_posterior_no_rompen_el_caso():
    error = ResultError(
        "Reached maximum number of turns",
        data={
            "subtype": "error_max_turns",
            "stop_reason": "tool_use",
            "terminal_reason": "max_turns",
        },
        exit_code=1,
    )
    caso, _, _ = _caso(
        [],
        fin=_fin("error_max_turns", "tool_use", True, "max_turns"),
        error_final=error,
    )
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.terminacion.terminacion is Terminacion.LIMITE_SEGURIDAD
    assert "error_max_turns" in caso.eventos()[-1].detalle


# ------------------------------------------------------------------ hooks y entorno (R7, R8)


def test_los_hooks_se_reparten_al_coordinador_y_a_cada_subagente():
    hooks = {"PreToolUse": []}
    caso, ejecutor, _ = _caso([*DELEGACIONES_DEL_EJEMPLO, {"frente": "listas"}], hooks=hooks)
    assert caso.opciones_coordinador().hooks is hooks
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert len(ejecutor.llamadas) == 4
    assert all(llamada.opciones.hooks is hooks for llamada in ejecutor.llamadas)


def test_las_opciones_de_cada_subagente_son_las_aisladas_de_su_frente():
    caso, ejecutor, _ = _caso([*DELEGACIONES_DEL_EJEMPLO, {"frente": "listas"}])
    asyncio.run(caso.ejecutar(SOLICITUD))
    for llamada in ejecutor.llamadas:
        assert llamada.opciones.setting_sources == [] and llamada.opciones.tools == []
        assert llamada.opciones.allowed_tools == [FRENTES[llamada.frente].herramienta_completa]


def test_ejecutar_caso_no_carga_el_entorno(monkeypatch):
    def prohibido():
        raise AssertionError("ejecutar_caso no debe cargar el entorno")

    monkeypatch.setattr(configuracion, "cargar_entorno", prohibido)
    consulta = _coordinador_simulado([])

    caso = asyncio.run(ejecutar_caso(SOLICITUD, ejecutor=EjecutorSimulado(), consulta=consulta))
    assert isinstance(caso, Caso)
    assert caso.terminacion.terminacion is Terminacion.NORMAL


def test_dos_ejecuciones_de_la_misma_solicitud_son_dos_casos():
    uno, _, _ = _caso([])
    otro, _, _ = _caso([])
    assert uno.estado is not otro.estado and uno.eventos() is not otro.eventos()
