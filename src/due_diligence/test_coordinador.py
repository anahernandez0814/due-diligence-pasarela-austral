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
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
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
        "PostToolUse": [ESCALAR],
        "PostToolUseFailure": [ESCALAR],
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


def test_un_caso_con_los_cuatro_frentes_terminados_y_fin_normal_esta_completo():
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
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


def test_un_caso_con_cierre_sin_escalar_no_esta_completo():
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
    caso.estado.cierre_sin_escalar = True
    assert caso.completo is False


def test_un_caso_con_un_hook_de_registro_que_fallo_no_esta_completo():
    # Un PostToolUse que falló pudo dejar sin registrar una coincidencia: no es un caso completo.
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
    assert caso.completo is True
    caso.estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    assert caso.completo is False


# ------------------------------------------------------------ cobertura y turnos (#8, R2, R5)


def test_la_cobertura_del_caso_es_la_calculada_por_el_codigo():
    caso, _, _ = _caso_completo()
    asyncio.run(caso.ejecutar(SOLICITUD))
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
