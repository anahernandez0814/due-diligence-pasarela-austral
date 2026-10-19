"""Tests del coordinador y del caso (contrato `caso.md`, FR-001, FR-002, FR-013, SC-001).

El `query()` del coordinador y el ejecutor de los subagentes son simulados: estos tests validan
el cableado (herramientas, delegación, estado, terminación), no lo que decidiría el modelo.
"""

import asyncio

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
from claude_agent_sdk._errors import ResultError

from due_diligence import configuracion
from due_diligence.cobertura import calcular_cobertura
from due_diligence.coordinador import (
    _REGLA_FALLOS,
    INSTRUCCIONES_COORDINADOR,
    Caso,
    ejecutar_caso,
)
from due_diligence.estado import Situacion
from due_diligence.eventos import (
    TIPO_CASO_INICIADO,
    TIPO_DELEGACION,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_FALLO_DE_HOOK,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
    TIPO_INFORME_REGISTRADO,
    TIPO_MENSAJE_ANALISTA,
    TIPO_TERMINACION,
)
from due_diligence.frentes import FRENTES, Frente
from due_diligence.simulacion import (
    EjecutorSimulado,
    mensaje_de_resultado,
    resultado_frente,
    resultado_listas,
    terminacion_anomala,
)
from due_diligence.simulacion import consulta as consulta_de_frente
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


@pytest.fixture(autouse=True)
def _sin_caida_del_registro(monkeypatch):
    """Los tests que consultan el registro real no dependen de la caída simulada de la sesión."""
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)


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
    delegaciones,
    fin=None,
    error_final=None,
    texto="Resumen para el analista.",
    en_un_turno=False,
):
    """Un `query()` del coordinador que delega como lo haría el SDK y termina como se le diga."""
    llamadas = []
    caso_ref = {}

    async def consulta(*, prompt, options=None):
        llamadas.append((prompt, options))
        if delegaciones and en_un_turno:
            delegador = caso_ref["caso"].delegador
            await asyncio.gather(*(delegador.delegar(d) for d in delegaciones))
        elif delegaciones:
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
    en_un_turno=False,
    **kwargs,
):
    ejecutor = ejecutor or EjecutorSimulado()
    consulta = _coordinador_simulado(
        delegaciones, fin=fin, error_final=error_final, texto=texto, en_un_turno=en_un_turno
    )
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


def test_ya_no_existe_la_prohibicion_de_decidir_del_6():
    from due_diligence import coordinador

    assert not hasattr(coordinador, "PROHIBICION_DECISION")
    texto = INSTRUCCIONES_COORDINADOR
    for retirado in (
        "NO llames a registrar_informe",
        "aún no está disponible",
        "limítate a delegar",
    ):
        assert retirado not in texto
    assert "No decidas la habilitación" not in texto


def test_la_instruccion_minima_pide_escalar_y_registrar_el_informe_con_los_tres_valores():
    texto = INSTRUCCIONES_COORDINADOR
    assert "llama a escalar_a_cumplimiento" in texto
    assert "coincidencia en listas restrictivas o la categoría es de alto riesgo" in texto
    assert "registra el informe con registrar_informe" in texto
    assert "exactamente habilitar, no_habilitar o decide_cumplimiento" in texto


def test_la_instruccion_dice_cuando_usar_cada_recomendacion():
    texto = INSTRUCCIONES_COORDINADOR
    assert (
        "se escaló (coincidencia en listas o alto riesgo), la recomendación es decide_cumplimiento"
        in texto
    )
    assert "no_habilitar es para un caso que no requiere escalamiento y no se habilita" in texto
    assert "habilitar, solo si no hay coincidencia, el comercio no es de alto riesgo" in texto
    assert "categoría quedó determinada" in texto


def test_las_instrucciones_conservan_la_regla_de_varias_coincidencias_y_el_orden_de_listas():
    texto = INSTRUCCIONES_COORDINADOR
    assert (
        "Si el registro devuelve varias coincidencias, no elijas una ni sigas con listas" in texto
    )
    assert "Después delega listas: usa el comercio que devolvió el registro" in texto
    assert "pide al analista el identificador" in texto


def test_las_instrucciones_conservan_el_resumen_al_analista_sin_decidir_por_el_texto():
    texto = INSTRUCCIONES_COORDINADOR
    assert "resume al analista, frente por frente" in texto
    assert "qué frentes no se pudieron cubrir y por qué" in texto


def test_el_coordinador_usa_las_instrucciones_normales_sin_el_modo_de_demostracion():
    caso, _, _ = _caso([])
    opciones = caso.opciones_coordinador()
    assert opciones.system_prompt == INSTRUCCIONES_COORDINADOR
    # FR-002: las herramientas de decisión siguen entre las del coordinador, ahora con sus hooks.
    assert "mcp__pasarela__registrar_informe" in opciones.allowed_tools
    assert "mcp__pasarela__escalar_a_cumplimiento" in opciones.allowed_tools


def test_las_instrucciones_piden_delegar_juntos_los_frentes_independientes_y_no_inventar_datos():
    texto = INSTRUCCIONES_COORDINADOR
    assert "delegar_frente" in texto
    assert "en la misma respuesta" in texto
    assert "inventes" in texto
    assert "no elijas" in texto


def test_la_categoria_es_el_sector_sin_canal_y_lo_desconocido_se_confirma_en_las_dos_guias():
    from due_diligence.delegacion import DESCRIPCION

    for texto in (INSTRUCCIONES_COORDINADOR, DESCRIPCION):
        assert "sin el canal de venta" in texto
        assert "categoria_desconocida" in texto
        assert "catálogo" in texto
    assert "pide confirmación al analista" in INSTRUCCIONES_COORDINADOR
    # #10, cuarta ronda: sin confirmación no hay espera (FR-015), así que se informa.
    assert (
        "Si el analista no la confirma, registra el informe con la categoría no determinada, sin "
        "recomendar habilitar." in INSTRUCCIONES_COORDINADOR
    )


def test_el_coordinador_trata_de_usted_y_no_menciona_tickets_al_analista():
    assert "de usted" in INSTRUCCIONES_COORDINADOR
    # La única mención a «tickets» es la orden de no mencionarlos.
    assert INSTRUCCIONES_COORDINADOR.lower().count("ticket") == 1


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


def test_otra_excepcion_del_sdk_registra_la_terminacion_anomala_y_se_relanza():
    caso, _, _ = _caso([], error_final=ConnectionError("sin conexión"))
    # El error llega tras el ResultMessage, pero una excepción que no es ResultError no se traga.
    with pytest.raises(ConnectionError):
        asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.terminacion.terminacion is Terminacion.ANOMALA
    ultimo = caso.eventos()[-1]
    assert ultimo.tipo == TIPO_TERMINACION and "ConnectionError" in ultimo.detalle


# ------------------------------------------------------------------ hooks y entorno (R7, R8)


def test_los_hooks_del_caso_cierran_sobre_su_propio_estado_y_se_reparten_por_agente():
    """Desde el #7 el `Caso` construye sus hooks con `HooksDelCaso` sobre su estado (R5)."""
    caso, ejecutor, _ = _caso([*DELEGACIONES_DEL_EJEMPLO, {"frente": "listas"}])
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert len(ejecutor.llamadas) == 4
    registro = ejecutor.llamadas_de(Frente.REGISTRO)[0].opciones.hooks
    assert set(registro) == {"PostToolUse", "PostToolUseFailure"}
    assert not ejecutor.llamadas_de(Frente.NOTICIAS)[0].opciones.hooks
    # El hook del registro escribió en el estado de este caso: la identificación salió del hook.
    assert caso.estado.identificaciones
    assert caso.estado.comercio is not None


def test_el_caso_no_acepta_un_parametro_hooks():
    with pytest.raises(TypeError):
        Caso(hooks={"PreToolUse": []})  # las reglas no se desactivan desde fuera


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


# ------------------------------------------------------------ estado y eventos del caso (US5)

TODO_EL_EJEMPLO = [*DELEGACIONES_DEL_EJEMPLO, {"frente": "listas"}]


def _caso_completo(**kwargs):
    """El ejemplo completo con los cuatro frentes pedidos en el mismo turno."""
    return _caso(TODO_EL_EJEMPLO, en_un_turno=True, **kwargs)


def test_el_estado_de_un_caso_terminado_tiene_el_resultado_y_las_consultas_de_cada_frente():
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
    estado = caso.estado

    assert set(estado.resultados) == set(Frente)
    assert len(estado.consultas) == 5  # registro, noticias, categoría y las dos de listas
    for frente in Frente:
        assert estado.situacion(frente) is Situacion.TERMINADO
    for consulta in estado.consultas:
        assert consulta.valido and consulta.resultado["metadatos"]["fuentes"]
        assert consulta.resultado["metadatos"]["fecha"]
        for hecho in consulta.resultado["hechos"]:
            # El contenido y los metadatos (fuente y fecha) llegan separados y no se mezclan.
            assert "fuente" not in hecho["contenido"] and "fecha" not in hecho["contenido"]
            assert hecho["metadatos"]["fuente"] and hecho["metadatos"]["fecha"]


def test_cada_evento_tiene_marca_frente_y_tipo_y_la_lista_va_ordenada_por_secuencia():
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
    eventos = caso.eventos()
    assert [e.secuencia for e in eventos] == list(range(1, len(eventos) + 1))
    assert all(e.marca.tzinfo is not None and e.tipo and e.detalle for e in eventos)
    for frente in Frente:
        tipos = [e.tipo for e in eventos if e.frente is frente]
        assert tipos == [TIPO_DELEGACION, TIPO_FRENTE_INICIO, TIPO_FRENTE_FIN]


def test_un_frente_que_termina_de_forma_anomala_figura_no_terminado_y_no_como_terminado():
    anomalo = resultado_frente(
        Frente.NOTICIAS, [consulta_de_frente(Frente.NOTICIAS)], terminacion_anomala()
    )
    caso, _, _ = _caso_completo(ejecutor=EjecutorSimulado(resultados={Frente.NOTICIAS: anomalo}))
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.estado.situacion(Frente.NOTICIAS) is Situacion.NO_TERMINADO
    assert caso.estado.situacion(Frente.REGISTRO) is Situacion.TERMINADO
    assert "no_terminado" in next(
        e.detalle
        for e in caso.eventos()
        if e.tipo == TIPO_FRENTE_FIN and e.frente is Frente.NOTICIAS
    )


def test_la_instantanea_durante_la_ejecucion_marca_los_frentes_sin_terminar_como_en_curso():
    vistas = []
    referencia = {}

    def espiar(_contexto):
        vistas.append(referencia["caso"].estado.instantanea())
        return resultado_frente(Frente.NOTICIAS)

    ejecutor = EjecutorSimulado(retardo=0.02, resultados={Frente.NOTICIAS: espiar})
    caso, _, _ = _caso_completo(ejecutor=ejecutor)
    referencia["caso"] = caso
    asyncio.run(caso.ejecutar(SOLICITUD))

    instantanea = vistas[0]
    assert instantanea.situacion(Frente.NOTICIAS) is Situacion.EN_CURSO
    assert Frente.NOTICIAS not in instantanea.resultados  # sin resultado vacío mientras corre
    assert instantanea.situacion(Frente.CATEGORIA) is Situacion.EN_CURSO
    assert instantanea.terminacion is None
    # La copia es independiente: lo que ocurrió después no la cambia.
    assert caso.estado.situacion(Frente.NOTICIAS) is Situacion.TERMINADO
    assert instantanea.situacion(Frente.NOTICIAS) is Situacion.EN_CURSO


def test_dos_casos_con_la_misma_solicitud_son_independientes():
    caido = resultado_frente(
        Frente.NOTICIAS, [consulta_de_frente(Frente.NOTICIAS)], terminacion_anomala()
    )
    uno, ejecutor_uno, _ = _caso_completo()
    otro, ejecutor_otro, _ = _caso_completo(
        ejecutor=EjecutorSimulado(resultados={Frente.NOTICIAS: caido})
    )

    async def los_dos():
        await asyncio.gather(uno.ejecutar(SOLICITUD), otro.ejecutar(SOLICITUD))

    asyncio.run(los_dos())

    assert uno.estado is not otro.estado
    assert uno.estado.situacion(Frente.NOTICIAS) is Situacion.TERMINADO
    assert otro.estado.situacion(Frente.NOTICIAS) is Situacion.NO_TERMINADO
    assert len(uno.estado.consultas) == 5
    assert len(ejecutor_uno.llamadas) == 4 and len(ejecutor_otro.llamadas) == 4
    secuencias_uno = {e.secuencia for e in uno.eventos()}
    assert secuencias_uno == set(range(1, len(secuencias_uno) + 1))  # cada caso cuenta desde 1
    assert [e.detalle for e in uno.eventos()] != [e.detalle for e in otro.eventos()]


def test_un_hook_que_recibe_el_caso_por_cierre_lee_el_estado_de_cada_frente():
    """Así leerá el estado un hook del #7 (R7): por cierre, sin pasarlo por el modelo."""
    lecturas = []
    referencia = {}

    def hook_simulado(_contexto):
        estado = referencia["caso"].estado
        lecturas.append(
            ({f: estado.situacion(f) for f in Frente}, estado.comercio, estado.motivo_comercio)
        )
        return resultado_listas()

    caso, _, _ = _caso_completo(
        ejecutor=EjecutorSimulado(resultados={Frente.LISTAS: hook_simulado})
    )
    referencia["caso"] = caso
    asyncio.run(caso.ejecutar(SOLICITUD))

    situaciones, comercio, _ = lecturas[0]
    assert situaciones[Frente.REGISTRO] is Situacion.TERMINADO  # ya terminó cuando empieza listas
    assert situaciones[Frente.LISTAS] is Situacion.EN_CURSO
    assert comercio["identificador"] == "CO-TV-0001"


def test_el_orden_del_caso_se_reconstruye_solo_con_los_eventos():
    """SC-006: la secuencia de tipos y frentes cuenta lo que pasó, sin abrir el código."""
    retardos = {
        Frente.REGISTRO: 0.05,
        Frente.NOTICIAS: 0.15,
        Frente.CATEGORIA: 0.25,
        Frente.LISTAS: 0.01,
    }
    caso, _, _ = _caso_completo(ejecutor=EjecutorSimulado(retardos=retardos))
    asyncio.run(caso.ejecutar(SOLICITUD))

    esperado = [
        (TIPO_CASO_INICIADO, None),
        ("mensaje_analista", None),  # #10, R2: cada turno empieza con su mensaje
        (TIPO_DELEGACION, Frente.REGISTRO),
        (TIPO_FRENTE_INICIO, Frente.REGISTRO),
        (TIPO_DELEGACION, Frente.NOTICIAS),
        (TIPO_FRENTE_INICIO, Frente.NOTICIAS),
        (TIPO_DELEGACION, Frente.CATEGORIA),
        (TIPO_FRENTE_INICIO, Frente.CATEGORIA),
        (TIPO_FRENTE_FIN, Frente.REGISTRO),
        (TIPO_DELEGACION, Frente.LISTAS),
        (TIPO_FRENTE_INICIO, Frente.LISTAS),
        (TIPO_FRENTE_FIN, Frente.LISTAS),
        (TIPO_FRENTE_FIN, Frente.NOTICIAS),
        (TIPO_FRENTE_FIN, Frente.CATEGORIA),
        (TIPO_TERMINACION, None),
    ]
    assert [(e.tipo, e.frente) for e in caso.eventos()] == esperado


def test_el_coste_del_coordinador_se_toma_del_resultado():
    con_coste = ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="sesion-de-prueba",
        stop_reason="end_turn",
        total_cost_usd=0.25,
        terminal_reason="completed",
    )
    caso, _, _ = _caso([], fin=con_coste)
    assert caso.coste_usd is None
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.coste_usd == 0.25


# ------------------------------------------------------------- reparto de hooks por agente (#7, R5)

PASARELA = "mcp__pasarela__"
DELEGAR = "mcp__delegacion__delegar_frente"
INFORME = PASARELA + "registrar_informe"
ESCALAR = PASARELA + "escalar_a_cumplimiento"
HERRAMIENTAS_DE_LAS_REGLAS = {
    DELEGAR,
    INFORME,
    ESCALAR,
    PASARELA + "consultar_registro_mercantil",
    PASARELA + "consultar_listas_restrictivas",
    PASARELA + "consultar_riesgo_categoria",
}


def _matchers(hooks):
    return {evento: [m.matcher for m in lista] for evento, lista in hooks.items()}


def test_el_coordinador_tiene_los_hooks_de_delegar_informe_escalar_y_el_stop():
    caso, _, _ = _caso([])
    coordinador = _matchers(caso.opciones_coordinador().hooks)
    assert coordinador == {
        "PreToolUse": [DELEGAR, INFORME, ESCALAR],
        # #9: el `PostToolUse` y el `PostToolUseFailure` del informe (huella pendiente, R7).
        "PostToolUse": [ESCALAR, INFORME],
        "PostToolUseFailure": [ESCALAR, INFORME],
        "Stop": [None],
    }


def test_cada_subagente_tiene_solo_los_hooks_que_vigilan_su_herramienta():
    caso, _, _ = _caso([])
    registro = PASARELA + "consultar_registro_mercantil"
    listas = PASARELA + "consultar_listas_restrictivas"
    riesgo = PASARELA + "consultar_riesgo_categoria"
    esperado = {
        Frente.REGISTRO: {"PostToolUse": [registro], "PostToolUseFailure": [registro]},
        Frente.LISTAS: {
            "PreToolUse": [listas],
            "PostToolUse": [listas],
            "PostToolUseFailure": [listas],
        },
        Frente.CATEGORIA: {"PostToolUse": [riesgo], "PostToolUseFailure": [riesgo]},
        Frente.NOTICIAS: {},
    }
    for frente, hooks in esperado.items():
        assert _matchers(caso._opciones_subagente(frente).hooks or {}) == hooks, frente


def test_ningun_subagente_tiene_stop_y_el_pretooluse_de_listas_solo_esta_en_listas():
    caso, _, _ = _caso([])
    for frente in Frente:
        hooks = caso._opciones_subagente(frente).hooks or {}
        assert "Stop" not in hooks
        tiene_el_de_listas = any(
            m.matcher == PASARELA + "consultar_listas_restrictivas"
            for m in hooks.get("PreToolUse", [])
        )
        assert tiene_el_de_listas is (frente is Frente.LISTAS)
    assert not any(
        m.matcher == PASARELA + "consultar_listas_restrictivas"
        for m in caso.opciones_coordinador().hooks["PreToolUse"]
    )


def test_los_matchers_son_nombres_completos_exactos_de_herramientas_conocidas():
    caso, _, _ = _caso([])
    todos = [caso.opciones_coordinador().hooks]
    todos += [caso._opciones_subagente(f).hooks or {} for f in Frente]
    nombres = {m.matcher for hooks in todos for lista in hooks.values() for m in lista if m.matcher}
    assert nombres <= HERRAMIENTAS_DE_LAS_REGLAS
    for nombre in nombres:
        assert nombre.startswith("mcp__") and "*" not in nombre and "|" not in nombre


def test_los_hooks_de_todos_los_agentes_cierran_sobre_el_mismo_estado_del_caso():
    from due_diligence.simulacion import (
        SesionSimulada,
        comercio_alto_riesgo,
        respuesta_registro,
    )

    caso, _, _ = _caso([])
    sesion_registro = SesionSimulada(caso._opciones_subagente(Frente.REGISTRO))
    asyncio.run(
        sesion_registro.llamar(
            FRENTES[Frente.REGISTRO].herramienta_completa,
            {"identificador": "CO-TV-0001"},
            respuesta=respuesta_registro(comercio_alto_riesgo()),
        )
    )
    caso.estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    caso.estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    # El hook del subagente de listas, en otra sesión, ve lo que escribió el del registro.
    sesion_listas = SesionSimulada(caso._opciones_subagente(Frente.LISTAS))
    consulta = {"tipo": "comercio", "identificador": "CO-TV-0001"}
    llamada = asyncio.run(
        sesion_listas.llamar(
            FRENTES[Frente.LISTAS].herramienta_completa, consulta, respuesta={"resultado": "x"}
        )
    )
    assert llamada.ejecutada and not llamada.denegada
    # Y el hook del coordinador ve el mismo estado: con el registro terminado permite listas.
    sesion_coordinador = SesionSimulada(caso.opciones_coordinador())
    delegar = asyncio.run(
        sesion_coordinador.llamar(DELEGAR, {"frente": "listas"}, respuesta={"ok": True})
    )
    assert delegar.ejecutada and not delegar.denegada


def test_dos_casos_no_comparten_hooks_estado_ni_libro():
    caso_uno, _, _ = _caso([])
    caso_otro, _, _ = _caso([])
    assert caso_uno.estado is not caso_otro.estado
    assert caso_uno.estado.libro is not caso_otro.estado.libro
    assert caso_uno.hooks is not caso_otro.hooks
    caso_uno.estado.libro.fallo_de_hook = "x"
    assert caso_otro.estado.libro.fallo_de_hook is None


def test_el_caso_y_ejecutar_caso_no_aceptan_un_parametro_hooks():
    with pytest.raises(TypeError):
        Caso(hooks={"PreToolUse": []})
    with pytest.raises(TypeError):
        asyncio.run(ejecutar_caso(SOLICITUD, hooks={"PreToolUse": []}))


# ------------------------------------------------------------------ Caso.completo (#7, FR-007)


def _con_informe_vigente(caso):
    """Un informe registrado con la huella de ahora: desde el #9 (FR-023) el caso completo lo exige.

    El coordinador simulado de estos tests no registra informes; los del #9 que sí lo hacen están en
    `test_casos_informe.py`.
    """
    from due_diligence.informe import InformeRegistrado, huella_actual

    caso.estado.informes.append(
        InformeRegistrado("INF-0001", "decide_cumplimiento", False, huella_actual(caso.estado))
    )


def test_un_caso_con_los_cuatro_frentes_terminados_y_fin_normal_esta_completo():
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.completo is False  # #9: sin informe vigente no está completo
    _con_informe_vigente(caso)
    assert caso.completo is True


def test_un_caso_sin_ejecutar_o_con_un_frente_sin_terminar_no_esta_completo():
    sin_ejecutar, _, _ = _caso([])
    assert sin_ejecutar.completo is False
    parcial, _, _ = _caso(DELEGACIONES_DEL_EJEMPLO, en_un_turno=True)
    asyncio.run(parcial.ejecutar(SOLICITUD))  # listas nunca se delegó
    assert parcial.completo is False


def test_un_caso_con_terminacion_anomala_no_esta_completo():
    caso, _, _ = _caso(TODO_EL_EJEMPLO, en_un_turno=True, fin=_fin(stop_reason="max_tokens"))
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.terminacion.terminacion is Terminacion.ANOMALA
    assert caso.completo is False


@pytest.mark.parametrize("marca", ["cierre_sin_escalar", "cierre_sin_informe"])
def test_un_caso_con_un_cierre_forzado_no_esta_completo_aunque_lo_demas_se_cumpla(marca):
    # Con el informe vigente, todo lo demás se cumple: solo la marca del `Stop` lo impide (#9).
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
    _con_informe_vigente(caso)
    assert caso.completo is True
    setattr(caso.estado, marca, True)
    assert caso.completo is False


def test_un_caso_con_un_hook_de_registro_que_fallo_no_esta_completo():
    # Un PostToolUse que falló pudo dejar sin registrar una coincidencia: no es un caso completo.
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
    _con_informe_vigente(caso)
    assert caso.completo is True
    caso.estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    assert caso.completo is False


# ------------------------------------------------------------ cobertura y turnos (#8, R2, R5)


def test_la_cobertura_del_caso_es_la_calculada_por_el_codigo():
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
    _con_informe_vigente(caso)
    assert caso.cobertura == calcular_cobertura(caso.estado)
    assert caso.cobertura.completa is True and caso.completo is True


def test_un_frente_no_cubierto_impide_el_caso_completo_aunque_lo_demas_se_cumpla():
    caso, _, _ = _caso(DELEGACIONES_DEL_EJEMPLO, en_un_turno=True)  # sin listas
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.terminacion.terminacion is Terminacion.NORMAL
    assert not caso.estado.cierre_sin_escalar and caso.estado.libro.fallo_de_hook is None
    assert caso.cobertura.frentes[Frente.LISTAS].cubierto is False
    assert caso.cobertura.completa is False and caso.completo is False


def test_los_turnos_del_coordinador_salen_del_mensaje_de_resultado():
    caso, _, _ = _caso([], fin=mensaje_de_resultado(num_turns=7))
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.turnos == 7


def test_el_coste_y_los_turnos_del_coordinador_suman_todos_los_turnos_del_caso():
    # #10, cuarta ronda: `total_cost_usd` y `num_turns` son del turno (R1); el caso los suma para
    # que el coste total de la línea de comandos cuente todos los turnos.
    fin = ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=3,
        session_id="sesion-de-prueba",
        stop_reason="end_turn",
        total_cost_usd=0.25,
        terminal_reason="completed",
    )
    caso, _, _ = _caso([], fin=fin)
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert (caso.coste_usd, caso.turnos) == (0.25, 3)
    asyncio.run(caso.continuar("respuesta del analista"))
    assert (caso.coste_usd, caso.turnos) == (0.5, 6)


def test_las_instrucciones_explican_el_reintento_y_que_la_cobertura_la_calcula_el_sistema():
    # #8, R7, FR-008: el reintento lo pide el modelo; el código lo guarda.
    assert "reintentable true" in _REGLA_FALLOS and "una vez" in _REGLA_FALLOS
    assert "reintentable false" in _REGLA_FALLOS
    assert "la calcula el sistema" in _REGLA_FALLOS
    assert _REGLA_FALLOS in INSTRUCCIONES_COORDINADOR


def test_sin_mensaje_de_resultado_no_hay_dato_de_turnos():
    async def sin_resultado(*, prompt, options=None):
        yield AssistantMessage(content=[TextBlock("texto")], model="simulado")

    caso = Caso(ejecutor=EjecutorSimulado(), consulta=sin_resultado)
    assert caso.turnos is None
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.turnos is None


# ------------------------------------------------------------------ #9: conflictos del caso (G1)


def test_caso_conflictos_es_el_calculo_del_codigo_con_y_sin_conflictos():
    from due_diligence.conflictos import calcular_conflictos
    from due_diligence.estado import Consulta
    from due_diligence.frentes import FRENTES, Frente
    from servidor_mcp import datos
    from servidor_mcp.registro import consultar_registro_mercantil

    datos.limpiar_cache()
    for identificador, esperado in (
        ("CO-RF-0006", "con_conflictos"),
        ("CO-TA-0002", "sin_conflictos"),
    ):
        caso = Caso()
        respuesta = consultar_registro_mercantil(identificador=identificador).structured_content
        caso.estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
        caso.estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
        caso.estado.registrar_identificacion(respuesta)
        herramienta = FRENTES[Frente.REGISTRO].herramienta_completa
        caso.estado.agregar_consultas([Consulta(Frente.REGISTRO, herramienta, {}, respuesta, True)])
        assert caso.conflictos == calcular_conflictos(caso.estado)
        assert caso.conflictos.estado == esperado


def test_las_instrucciones_guian_las_afirmaciones_del_informe():
    # #9, T039, R12: guía, no garantía (la garantía es el hook de registrar_informe).
    from due_diligence.coordinador import _REGLA_AFIRMACIONES

    for fragmento in (
        "una lista de afirmaciones",
        "texto, fuente y fecha",
        "metadatos del resultado",
        "fuentes que consultaste para ese frente",
        "Cada frente cubierto lleva al menos una afirmación, también si no hubo hallazgos",
        "El comercio, los conflictos entre fuentes y la cobertura los pone el sistema",
        "reintenta el registro o registra el informe",
    ):
        assert fragmento in _REGLA_AFIRMACIONES, fragmento
    assert _REGLA_AFIRMACIONES in INSTRUCCIONES_COORDINADOR
    assert (
        "Si hay que escalar, registra el informe después de escalar." in INSTRUCCIONES_COORDINADOR
    )


# ------------------------------------------- #10: continuación del caso y cierre por turno (T014)

SOLICITUD_B = "Due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, talleres."


def _resultados_b():
    from due_diligence.simulacion import comercio_bajo_riesgo, consulta_listas
    from due_diligence.test_casos_reglas import _resultados

    resultados = _resultados(
        [comercio_bajo_riesgo()],
        "talleres",
        "bajo",
        [
            consulta_listas("comercio", identificador="CO-TA-0002"),
            consulta_listas("persona", identificador="PE-0002"),
        ],
        identificador="CO-TA-0002",
    )
    resultados[Frente.NOTICIAS] = resultado_frente(
        Frente.NOTICIAS, [consulta_de_frente(Frente.NOTICIAS, {"identificador": "CO-TA-0002"})]
    )
    return resultados


DELEGACIONES_B = [
    ("delegar", {"frente": "registro", "identificador": "CO-TA-0002"}),
    ("delegar", {"frente": "noticias", "identificador": "CO-TA-0002"}),
    ("delegar", {"frente": "categoria", "categoria": "talleres"}),
    ("delegar", {"frente": "listas"}),
]


def _caso_por_turnos(guiones, resultados=None):
    from due_diligence.simulacion import CoordinadorSimulado

    coordinador = CoordinadorSimulado(guiones=guiones)
    caso = Caso(ejecutor=EjecutorSimulado(resultados=resultados or {}), consulta=coordinador)
    coordinador.caso = caso
    return caso, coordinador


def test_ejecutar_y_continuar_registran_cada_mensaje_sin_repetir_su_texto():
    from due_diligence.eventos import TIPO_MENSAJE_ANALISTA

    caso, _, _ = _caso([])
    asyncio.run(caso.ejecutar(SOLICITUD))
    asyncio.run(caso.continuar("CO-AM-0005"))
    assert caso.estado.mensajes == [SOLICITUD, "CO-AM-0005"]
    detalles = [e.detalle for e in caso.eventos() if e.tipo == TIPO_MENSAJE_ANALISTA]
    assert detalles == ["Mensaje 1 del analista.", "Mensaje 2 del analista."]
    assert all("CO-AM-0005" not in e.detalle for e in caso.eventos())


def test_continuar_reanuda_la_sesion_con_el_mismo_caso():
    caso, _, consulta = _caso([])
    estado, hooks, delegador = caso.estado, caso.hooks, caso.delegador
    asyncio.run(caso.ejecutar(SOLICITUD))
    asyncio.run(caso.continuar("respuesta del analista"))
    (_, primeras), (prompt, segundas) = consulta.llamadas
    assert primeras.resume is None
    assert segundas.resume == "sesion-de-prueba" and prompt == "respuesta del analista"
    assert caso.estado is estado and caso.hooks is hooks and caso.delegador is delegador


def test_continuar_sin_una_sesion_previa_falla_sin_llamar_a_la_consulta():
    from due_diligence.coordinador import CasoSinSesion

    caso, _, consulta = _caso([])
    with pytest.raises(CasoSinSesion) as error:
        asyncio.run(caso.continuar("hola"))
    assert "sesión" in str(error.value)
    assert consulta.llamadas == []


def test_cada_turno_tiene_su_clasificacion_y_la_terminacion_es_la_del_ultimo():
    caso, _, _ = _caso([])
    asyncio.run(caso.ejecutar(SOLICITUD))
    asyncio.run(caso.continuar("otra cosa"))
    assert len(caso.turnos_del_caso) == 2
    assert caso.terminacion is caso.turnos_del_caso[-1]
    assert all(t.terminacion is Terminacion.NORMAL for t in caso.turnos_del_caso)


def test_la_espera_del_caso_y_el_caso_que_espera_no_esta_completo():
    from due_diligence.reglas import MOTIVO_ESPERA_IDENTIFICADOR
    from due_diligence.simulacion import comercios_parecidos, respuesta_registro

    resultados = {
        Frente.REGISTRO: resultado_frente(
            Frente.REGISTRO,
            [
                consulta_de_frente(
                    Frente.REGISTRO,
                    {"nombre": "Almacén Mirador SAS"},
                    respuesta_registro(*comercios_parecidos()),
                )
            ],
        )
    }
    caso, coordinador = _caso_por_turnos(
        [[("delegar", {"frente": "registro", "nombre": "Almacén Mirador SAS"}), ("terminar",)]],
        resultados,
    )
    asyncio.run(caso.ejecutar("Due diligence de Almacén Mirador SAS."))
    assert coordinador.resultados_de("terminar")[0].termino is True
    assert (
        caso.espera.clase == "identificador" and caso.espera.motivo == MOTIVO_ESPERA_IDENTIFICADOR
    )
    assert caso.completo is False


def test_el_cierre_se_reinicia_al_empezar_cada_turno():
    caso, _, _ = _caso([])
    asyncio.run(caso.ejecutar(SOLICITUD))
    caso.estado.libro.cierres_impedidos = configuracion.MAX_CIERRES_IMPEDIDOS
    caso.estado.cierre_sin_escalar = caso.estado.cierre_sin_informe = True
    vistos = {}
    original = caso._consulta

    async def mira(*, prompt, options=None):
        vistos["cierres"] = caso.estado.libro.cierres_impedidos
        vistos["marcas"] = (caso.estado.cierre_sin_escalar, caso.estado.cierre_sin_informe)
        async for mensaje in original(prompt=prompt, options=options):
            yield mensaje

    caso._consulta = mira
    asyncio.run(caso.continuar("sigo"))
    assert vistos == {"cierres": 0, "marcas": (False, False)}


AGOTAR = [("terminar",)] * (configuracion.MAX_CIERRES_IMPEDIDOS + 1)


def test_r4_a_el_turno_2_que_registra_el_informe_deja_el_caso_completo():
    caso, coordinador = _caso_por_turnos(
        [[*DELEGACIONES_B, *AGOTAR], [("informe", "no_habilitar"), ("terminar",)]],
        _resultados_b(),
    )
    asyncio.run(caso.ejecutar(SOLICITUD_B))
    assert caso.estado.cierre_sin_informe is True and caso.completo is False
    asyncio.run(caso.continuar("¿Lo registra, por favor?"))
    assert coordinador.resultados_de("terminar")[-1].termino is True
    assert caso.estado.cierre_sin_escalar is False and caso.estado.cierre_sin_informe is False
    assert caso.completo is True


def test_r4_b_el_turno_2_que_no_hace_nada_vuelve_a_poner_la_marca():
    caso, coordinador = _caso_por_turnos([[*DELEGACIONES_B, *AGOTAR], [*AGOTAR]], _resultados_b())
    asyncio.run(caso.ejecutar(SOLICITUD_B))
    asyncio.run(caso.continuar("¿Y entonces?"))
    # Sin el reinicio, el turno 2 dejaría cerrar en su primer intento (el contador seguiría lleno);
    # con él, vuelve a devolver MAX veces y la marca la pone el turno 2.
    maximo = configuracion.MAX_CIERRES_IMPEDIDOS
    turno_2 = coordinador.resultados_de("terminar")[-(maximo + 1) :]
    assert [r.termino for r in turno_2] == [False] * maximo + [True]
    assert caso.estado.cierre_sin_informe is True
    assert caso.estado.libro.cierres_impedidos == configuracion.MAX_CIERRES_IMPEDIDOS
    assert caso.completo is False


# ------------------------------------------------ #10: guía tras identificar (T027, FR-028)


def test_la_guia_tras_identificar_dice_que_el_rechazo_de_listas_deja_de_valer():
    from due_diligence.coordinador import _REGLA_TRAS_IDENTIFICAR, instrucciones_coordinador

    for fragmento in (
        "ese rechazo deja de valer cuando el registro lo identifica",
        "vuelve a delegar listas",
        "aunque el rechazo dijera reintentable false",
        "vuelve a delegar noticias con el comercio identificado",
    ):
        assert fragmento in _REGLA_TRAS_IDENTIFICAR, fragmento
    for demo in (False, True):  # también en el modo de demostración (FR-028)
        assert _REGLA_TRAS_IDENTIFICAR in instrucciones_coordinador(demo=demo)


def test_la_regla_de_varias_coincidencias_pide_terminar_el_turno_y_seguir_en_el_mismo_caso():
    from due_diligence.coordinador import _REGLA_VARIAS_COINCIDENCIAS, instrucciones_coordinador

    assert (
        "termina tu turno sin escalar ni registrar el informe; cuando responda, sigue en el mismo "
        "caso" in _REGLA_VARIAS_COINCIDENCIAS
    )
    assert _REGLA_VARIAS_COINCIDENCIAS in INSTRUCCIONES_COORDINADOR
    assert _REGLA_VARIAS_COINCIDENCIAS not in instrucciones_coordinador(demo=True)


# ------------------------------------------- #10: guías del escalamiento y del resumen (T043)


def test_la_regla_de_escalar_pide_no_escalar_el_bajo_riesgo_sin_hallazgos():
    from due_diligence.coordinador import _REGLA_ESCALAR, instrucciones_coordinador

    assert "No escales un comercio de bajo riesgo sin ningún hallazgo" in _REGLA_ESCALAR
    assert _REGLA_ESCALAR in INSTRUCCIONES_COORDINADOR
    assert _REGLA_ESCALAR not in instrucciones_coordinador(demo=True)


def test_la_guia_del_resumen_al_oficial_esta_en_los_dos_modos():
    from due_diligence.coordinador import _REGLA_RESUMEN_OFICIAL, instrucciones_coordinador

    for fragmento in (
        "resumen al oficial de cumplimiento",
        "los hallazgos de cada frente como las afirmaciones del informe",
        "una acción recomendada dirigida al oficial",
        "el comercio, la cobertura, la causa y los conflictos los pone el sistema",
    ):
        assert fragmento in _REGLA_RESUMEN_OFICIAL, fragmento
    for demo in (False, True):
        assert _REGLA_RESUMEN_OFICIAL in instrucciones_coordinador(demo=demo)


# ------------------------------------- #11: observador y turnos por turno (T008, R1, R5, FR-004)


def _caso_a_con(observador):
    """El caso (a) del #10, de extremo a extremo simulado, con un observador de la traza."""
    from due_diligence.simulacion import (
        CoordinadorSimulado,
        comercio_alto_riesgo,
        consulta_listas,
        respuesta_registro,
        respuesta_riesgo,
    )

    categoria = "suplementos dietarios"
    resultados = {
        Frente.REGISTRO: resultado_frente(
            Frente.REGISTRO,
            [
                consulta_de_frente(
                    Frente.REGISTRO,
                    {"identificador": "CO-TV-0001"},
                    respuesta_registro(comercio_alto_riesgo()),
                )
            ],
        ),
        Frente.CATEGORIA: resultado_frente(
            Frente.CATEGORIA,
            [
                consulta_de_frente(
                    Frente.CATEGORIA, {"categoria": categoria}, respuesta_riesgo(categoria, "alto")
                )
            ],
        ),
        Frente.LISTAS: resultado_frente(
            Frente.LISTAS,
            [
                consulta_listas("comercio", identificador="CO-TV-0001"),
                consulta_listas("persona", identificador="PE-0001"),
            ],
        ),
    }
    guion = [
        (
            "delegar_paralelo",
            [
                {"frente": "registro", "identificador": "CO-TV-0001"},
                {"frente": "noticias", "identificador": "CO-TV-0001"},
                {"frente": "categoria", "categoria": categoria},
            ],
        ),
        ("delegar", {"frente": "listas"}),
        ("escalar", "Revisar el origen de fondos antes de decidir."),
        ("informe", "decide_cumplimiento"),
        ("terminar",),
    ]
    coordinador = CoordinadorSimulado(guion)
    caso = Caso(
        ejecutor=EjecutorSimulado(resultados=resultados),
        consulta=coordinador,
        observador=observador,
    )
    coordinador.caso = caso
    asyncio.run(
        caso.ejecutar(
            "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001, "
            "de suplementos dietarios."
        )
    )
    return caso


def test_el_observador_del_caso_recibe_los_mismos_eventos_que_la_traza():
    vistos = []
    caso = _caso_a_con(vistos.append)
    assert vistos == caso.eventos()
    assert [e.secuencia for e in vistos] == list(range(1, len(vistos) + 1))


def test_un_observador_que_lanza_no_cambia_el_caso_a():
    def lanza(evento):
        raise RuntimeError("fallo de la vista")

    con_fallo, sin_observador = _caso_a_con(lanza), _caso_a_con(None)
    tipos = [e.tipo for e in con_fallo.eventos()]
    assert TIPO_FALLO_DE_HOOK not in tipos
    assert con_fallo.estado.libro.fallo_de_hook is None
    assert tipos == [e.tipo for e in sin_observador.eventos()]
    assert TIPO_ESCALAMIENTO_REGISTRADO in tipos and TIPO_INFORME_REGISTRADO in tipos
    assert con_fallo.completo is sin_observador.completo is True


def test_los_turnos_se_guardan_por_turno_y_el_caso_los_sigue_sumando():
    from due_diligence.simulacion import CoordinadorSimulado

    coordinador = CoordinadorSimulado(guiones=[[], []], num_turns=[3, 4])
    caso = Caso(ejecutor=EjecutorSimulado(), consulta=coordinador)
    coordinador.caso = caso
    assert caso.turnos_por_turno == []
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.turnos_por_turno == [3]
    asyncio.run(caso.continuar("respuesta del analista"))
    assert caso.turnos_por_turno == [3, 4]
    assert caso.turnos == 7


def test_un_turno_que_lanza_guarda_turnos_sin_dato():
    from due_diligence.simulacion import CoordinadorSimulado

    coordinador = CoordinadorSimulado([("lanzar", RuntimeError("fallo simulado del SDK"))])
    caso = Caso(ejecutor=EjecutorSimulado(), consulta=coordinador)
    coordinador.caso = caso
    with pytest.raises(RuntimeError):
        asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.turnos_por_turno == [None]


def test_un_turno_sin_mensaje_de_resultado_guarda_turnos_sin_dato():
    async def sin_resultado(*, prompt, options=None):
        yield AssistantMessage(content=[TextBlock("texto")], model="simulado")

    caso = Caso(ejecutor=EjecutorSimulado(), consulta=sin_resultado)
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.turnos_por_turno == [None]


# ------------------------------------- #11: fechas y orden del resumen (T025, R9, R10, R4)


def test_la_regla_de_fechas_esta_en_los_dos_modos():
    from due_diligence.coordinador import _REGLA_FECHAS, instrucciones_coordinador

    for fragmento in (
        "AAAA-MM-DD",
        "al guardar un informe o un caso para el oficial",
        "está en UTC",
        "puede ser la del día siguiente en Colombia",
        "no la presentes como una fecha posterior a hoy ni como una anomalía",
    ):
        assert fragmento in _REGLA_FECHAS, fragmento
    for demo in (False, True):  # es guía de estilo, no una regla de negocio: va en los dos
        assert _REGLA_FECHAS in instrucciones_coordinador(demo=demo)


def test_el_resumen_al_analista_empieza_por_la_cobertura():
    from due_diligence.coordinador import _REGLA_RESUMEN

    assert _REGLA_RESUMEN.startswith(
        "Al terminar, empieza por la cobertura: qué frentes no se pudieron cubrir y por qué"
    )
    assert "frente por frente" in _REGLA_RESUMEN and "fuente y su fecha" in _REGLA_RESUMEN


def test_las_afirmaciones_de_listas_van_una_por_autoridad_en_los_dos_modos():
    # Validación manual del #11: en 4 de los 7 casos el hook (I.4) rechazó el primer informe por
    # juntar varias autoridades en una afirmación. Es guía de estilo; la garantía sigue en el hook.
    from due_diligence.coordinador import _REGLA_AFIRMACIONES, instrucciones_coordinador

    assert (
        "En listas restrictivas, escribe una afirmación por cada autoridad consultada, cada una "
        "con su propia fuente; no juntes varias autoridades en una sola afirmación."
    ) in _REGLA_AFIRMACIONES
    for demo in (False, True):
        assert _REGLA_AFIRMACIONES in instrucciones_coordinador(demo=demo)


# ------------------------------- #12: la interrupción de la interfaz durante un hook (T014, R9)


class Interrupcion(BaseException):
    """Como `ScriptControlException` de Streamlit: hereda de `BaseException`, no de `Exception`."""


def _coordinador_con_hook_suelto(escritas):
    """Un `query()` que, como el SDK 0.2.168, ejecuta el `PreToolUse` en una tarea suelta.

    - `query.py:380`: el hook corre en `spawn_task` (`loop.create_task`), no en la tarea del turno.
    - `subprocess_cli.py:253`: la respuesta se escribe dentro de un `anyio.Lock()` sin
      `fast_acquire`, cuyo `acquire` cede una vez; aquí también, para fijar el orden real.
    - `query.close()` cancela las tareas en curso al cerrar: si el turno se cortara antes de que la
      respuesta saliera, la decisión se perdería y el test lo vería.
    """
    caso_ref = {}

    async def consulta(*, prompt, options=None):
        import anyio

        candado = anyio.Lock()
        hook = caso_ref["caso"].hooks.coordinador()["PreToolUse"][0].hooks[0]
        entrada = {
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__delegacion__delegar_frente",
            "tool_input": {"frente": "listas"},
            "tool_use_id": "t1",
        }

        async def manejar():
            decision = await hook(entrada, "t1", {"signal": None})
            async with candado:
                escritas.append(decision)

        tarea = asyncio.get_running_loop().create_task(manejar())
        try:
            await asyncio.sleep(60)  # el CLI seguiría trabajando: el turno no termina solo
            yield AssistantMessage(content=[TextBlock("no debe llegar")], model="simulado")
        finally:
            tarea.cancel()

    return consulta, caso_ref


def _observador_que_interrumpe_en_bloqueos(evento):
    if evento.regla is not None:
        raise Interrupcion("Stop")


def test_la_interrupcion_corta_el_turno_al_decidir_el_hook_y_la_denegacion_sale():
    from due_diligence.reglas import MOTIVO_REGISTRO_PRIMERO

    escritas = []
    consulta, caso_ref = _coordinador_con_hook_suelto(escritas)
    caso = Caso(
        ejecutor=EjecutorSimulado(),
        consulta=consulta,
        observador=_observador_que_interrumpe_en_bloqueos,
        interrupciones=(Interrupcion,),
    )
    caso_ref["caso"] = caso

    async def probar():
        with pytest.raises(Interrupcion) as lanzada:
            async with asyncio.timeout(2):
                await caso.ejecutar(SOLICITUD)
        # Mutación K9: sin `uncancel()`, la tarea seguiría marcada como cancelada y la siguiente
        # espera de quien llamó (el chat, `asyncio.run`) se cortaría sola.
        return lanzada.value, asyncio.current_task().cancelling()

    interrupcion, cancelando = asyncio.run(probar())
    assert cancelando == 0
    # El mismo objeto que lanzó el observador: Streamlit entrega una recarga una sola vez.
    assert interrupcion is caso._eventos.interrupcion
    (decision,) = escritas
    especifica = decision["hookSpecificOutput"]
    assert especifica["permissionDecision"] == "deny"
    assert especifica["permissionDecisionReason"] == MOTIVO_REGISTRO_PRIMERO
    assert caso.terminacion.terminacion is Terminacion.ANOMALA
    assert "interrumpido por la interfaz" in caso.terminacion.detalle
    assert caso.interrumpido is True and caso.completo is False
    assert caso.eventos()[-1].tipo == TIPO_TERMINACION


def test_sin_interrupcion_una_cancelacion_externa_sigue_siendo_cancelacion():
    consulta, caso_ref = _coordinador_con_hook_suelto([])
    caso = Caso(ejecutor=EjecutorSimulado(), consulta=consulta, interrupciones=(Interrupcion,))
    caso_ref["caso"] = caso

    async def probar():
        tarea = asyncio.create_task(caso.ejecutar(SOLICITUD))
        await asyncio.sleep(0.05)
        tarea.cancel()
        await tarea

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(probar())
    assert caso.interrumpido is False


def test_un_caso_sin_turnos_no_esta_interrumpido():
    assert Caso(ejecutor=EjecutorSimulado()).interrumpido is False


def test_una_interrupcion_que_sale_de_la_consulta_tambien_marca_el_turno_interrumpido():
    interrupcion = Interrupcion("Stop")

    async def consulta(*, prompt, options=None):
        raise interrupcion
        yield  # pragma: no cover

    caso = Caso(ejecutor=EjecutorSimulado(), consulta=consulta, interrupciones=(Interrupcion,))
    with pytest.raises(Interrupcion) as lanzada:
        asyncio.run(caso.ejecutar(SOLICITUD))
    assert lanzada.value is interrupcion
    assert caso.interrumpido is True
    assert caso.terminacion.terminacion is Terminacion.ANOMALA


def test_una_interrupcion_antes_de_la_consulta_corta_el_turno_sin_esperar_a_un_hook():
    # Mutación K13: la interrupción del primer evento (`caso_iniciado`, antes de que el turno ponga
    # su aviso) queda guardada; el turno la avisa al empezar, sin que ningún hook llegue a correr.
    vistos = []

    def observador(evento):
        vistos.append(evento.tipo)
        raise Interrupcion("Stop")

    iniciadas = []

    async def consulta(*, prompt, options=None):
        iniciadas.append(prompt)
        # Sin el aviso, el turno esperaría aquí y terminaría con normalidad, sin la interrupción.
        # No se usa `asyncio.timeout`: su cancelación, con la interrupción ya guardada, también
        # se convertiría en la interrupción y el test pasaría tarde.
        await asyncio.sleep(3)
        yield AssistantMessage(content=[TextBlock("no debe llegar")], model="simulado")

    caso = Caso(
        ejecutor=EjecutorSimulado(),
        consulta=consulta,
        observador=observador,
        interrupciones=(Interrupcion,),
    )

    async def probar():
        inicio = asyncio.get_running_loop().time()
        with pytest.raises(Interrupcion):
            await caso.ejecutar(SOLICITUD)
        return asyncio.get_running_loop().time() - inicio

    assert asyncio.run(probar()) < 2
    assert vistos == [TIPO_CASO_INICIADO]  # el observador se apagó en el primer evento
    assert caso.interrumpido is True
    assert caso.terminacion.terminacion is Terminacion.ANOMALA


def test_fuera_del_turno_un_evento_no_programa_la_cancelacion_en_un_bucle_cerrado():
    # Revisión de a7f853e: el `mensaje_analista` de `continuar` se registra antes de que el turno
    # ponga su aviso. Con el aviso del turno anterior, `call_soon` iría a un bucle ya cerrado (el
    # chat corre cada turno en su propio `asyncio.run`) y lanzaría `RuntimeError`.
    interrumpir = {"activo": False}

    def observador(evento):
        if interrumpir["activo"]:
            raise Interrupcion("Stop")

    async def consulta(*, prompt, options=None):
        yield _fin()

    caso = Caso(
        ejecutor=EjecutorSimulado(),
        consulta=consulta,
        observador=observador,
        interrupciones=(Interrupcion,),
    )
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso._eventos.al_interrumpir is None
    interrumpir["activo"] = True
    caso._eventos.registrar(TIPO_MENSAJE_ANALISTA, None, "Mensaje 2 del analista.")
    # La interrupción queda guardada para el turno siguiente, que la avisa al empezar.
    assert isinstance(caso._eventos.interrupcion, Interrupcion)
