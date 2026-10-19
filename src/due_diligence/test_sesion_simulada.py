"""Tests de `SesionSimulada` (R4, R12): una sesión de agente que ejecuta los hooks de sus opciones
como lo hace el SDK 0.2.168, sin llamar al modelo.

El orden y los efectos reproducen lo medido en `research.md` (R1 a R3): `PreToolUse` → herramienta →
`PostToolUse` (éxito) o `PostToolUseFailure` (error estructurado); un `deny` impide ejecutar la
herramienta y el modelo recibe el motivo; una excepción en un hook **deja pasar la acción**; un
`Stop` con `block` hace continuar y `stop_hook_active` pasa a `True`.
"""

import asyncio
import json

import pytest
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from due_diligence.hooks import bloquear_cierre, denegar, permitir, reemplazar_entrada
from due_diligence.simulacion import SesionSimulada

HERRAMIENTA = "mcp__pasarela__consultar_registro_mercantil"
OTRA = "mcp__pasarela__buscar_noticias"
OK = {"resultado": "sin_coincidencias", "hechos": [], "metadatos": {"fuentes": [], "fecha": "x"}}
ERROR = {
    "error": True,
    "tipo": "servicio_no_disponible",
    "mensaje": "m",
    "reintentable": True,
    "obtenido": {},
}


def _opciones(hooks):
    return ClaudeAgentOptions(hooks=hooks)


def _ejecutar(sesion, *args, **kwargs):
    return asyncio.run(sesion.llamar(*args, **kwargs))


class _Traza:
    def __init__(self):
        self.entradas = []

    def hook(self, nombre, salida=None):
        async def callback(entrada, tool_use_id, contexto):
            self.entradas.append((nombre, entrada, tool_use_id))
            return salida if salida is not None else permitir()

        return callback


def test_el_orden_es_pre_herramienta_post_y_las_entradas_tienen_la_forma_del_sdk():
    traza = _Traza()
    ejecuciones = []

    def herramienta(entrada):
        ejecuciones.append(entrada)
        return OK

    opciones = _opciones(
        {
            "PreToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("pre")])],
            "PostToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("post")])],
        }
    )
    sesion = SesionSimulada(opciones, {HERRAMIENTA: herramienta})
    resultado = _ejecutar(sesion, HERRAMIENTA, {"identificador": "CO-TV-0001"})

    assert [n for n, _, _ in traza.entradas] == ["pre", "post"]
    pre, post = traza.entradas[0][1], traza.entradas[1][1]
    assert pre["hook_event_name"] == "PreToolUse" and pre["tool_name"] == HERRAMIENTA
    assert pre["tool_input"] == {"identificador": "CO-TV-0001"} and "tool_response" not in pre
    assert post["hook_event_name"] == "PostToolUse"
    assert isinstance(post["tool_response"], str)  # texto JSON, como en un servidor stdio
    assert json.loads(post["tool_response"]) == OK
    assert traza.entradas[0][2] == traza.entradas[1][2]  # mismo tool_use_id
    assert ejecuciones == [{"identificador": "CO-TV-0001"}]
    assert resultado.ejecutada and not resultado.es_error and not resultado.denegada
    assert json.loads(resultado.texto) == OK


def test_una_herramienta_en_proceso_entrega_la_respuesta_como_lista_de_bloques():
    traza = _Traza()
    opciones = _opciones(
        {"PostToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("post")])]}
    )
    sesion = SesionSimulada(opciones, {HERRAMIENTA: lambda _e: OK})
    _ejecutar(sesion, HERRAMIENTA, {}, en_proceso=True)
    respuesta = traza.entradas[0][1]["tool_response"]
    assert respuesta == [{"type": "text", "text": json.dumps(OK, ensure_ascii=False)}]


def test_un_deny_impide_ejecutar_la_herramienta_y_el_modelo_recibe_el_motivo():
    traza = _Traza()
    ejecuciones = []
    opciones = _opciones(
        {
            "PreToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[_deniega("MOTIVO-X")])],
            "PostToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("post")])],
            "PostToolUseFailure": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("fallo")])],
        }
    )
    sesion = SesionSimulada(opciones, {HERRAMIENTA: lambda e: ejecuciones.append(e) or OK})
    resultado = _ejecutar(sesion, HERRAMIENTA, {"identificador": "CO-TV-0001"})
    assert ejecuciones == [] and not resultado.ejecutada
    assert resultado.denegada and resultado.es_error and resultado.motivo == "MOTIVO-X"
    assert resultado.texto == f"PreToolUse:{HERRAMIENTA} hook error: MOTIVO-X"
    assert traza.entradas == []  # ni PostToolUse ni PostToolUseFailure


def _deniega(motivo):
    async def hook(entrada, tool_use_id, contexto):
        return denegar(motivo)

    return hook


def test_un_error_estructurado_llega_por_postfailure_y_no_por_posttooluse():
    traza = _Traza()
    opciones = _opciones(
        {
            "PostToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("post")])],
            "PostToolUseFailure": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("fallo")])],
        }
    )
    sesion = SesionSimulada(opciones, {HERRAMIENTA: lambda _e: ERROR})
    resultado = _ejecutar(sesion, HERRAMIENTA, {})
    assert [n for n, _, _ in traza.entradas] == ["fallo"]
    entrada = traza.entradas[0][1]
    assert entrada["hook_event_name"] == "PostToolUseFailure"
    assert json.loads(entrada["error"]) == ERROR and "tool_response" not in entrada
    assert resultado.ejecutada and resultado.es_error and not resultado.denegada


def test_los_matchers_son_nombres_exactos():
    traza = _Traza()
    opciones = _opciones(
        {"PreToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("pre")])]}
    )
    sesion = SesionSimulada(opciones, {OTRA: lambda _e: OK})
    _ejecutar(sesion, OTRA, {})
    assert traza.entradas == []


def test_una_excepcion_en_un_hook_deja_pasar_la_accion_como_hace_el_sdk():
    async def roto(entrada, tool_use_id, contexto):
        raise RuntimeError("fallo del hook")

    ejecuciones = []
    opciones = _opciones({"PreToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[roto])]})
    sesion = SesionSimulada(opciones, {HERRAMIENTA: lambda e: ejecuciones.append(e) or OK})
    resultado = _ejecutar(sesion, HERRAMIENTA, {})
    assert ejecuciones == [{}] and resultado.ejecutada and not resultado.denegada
    assert [str(e) for e in sesion.excepciones_de_hooks] == ["fallo del hook"]


def test_sin_hooks_la_herramienta_se_ejecuta_y_una_desconocida_se_avisa():
    sesion = SesionSimulada(_opciones(None), {HERRAMIENTA: lambda _e: OK})
    assert _ejecutar(sesion, HERRAMIENTA, {}).ejecutada
    try:
        _ejecutar(sesion, OTRA, {})
    except KeyError as error:
        assert OTRA in str(error)
    else:
        raise AssertionError("una herramienta sin implementación simulada debe avisar")


def test_una_respuesta_dada_sustituye_a_la_herramienta():
    sesion = SesionSimulada(_opciones(None), {})
    resultado = _ejecutar(sesion, HERRAMIENTA, {}, respuesta=OK)
    assert json.loads(resultado.texto) == OK


def test_el_stop_bloquea_hasta_que_el_hook_permite_y_stop_hook_active_pasa_a_verdadero():
    entradas = []

    async def stop(entrada, tool_use_id, contexto):
        entradas.append(entrada)
        if len(entradas) <= 2:
            return bloquear_cierre("falta escalar")
        return permitir()

    sesion = SesionSimulada(_opciones({"Stop": [HookMatcher(hooks=[stop])]}))
    primero = asyncio.run(sesion.terminar("listo"))
    segundo = asyncio.run(sesion.terminar("ESCALADO"))
    tercero = asyncio.run(sesion.terminar("ESCALADO"))
    assert (primero.termino, primero.motivo) == (False, "falta escalar")
    assert (segundo.termino, tercero.termino) == (False, True)
    assert [e["stop_hook_active"] for e in entradas] == [False, True, True]
    assert entradas[0]["hook_event_name"] == "Stop"
    assert entradas[0]["last_assistant_message"] == "listo"


def test_un_stop_que_lanza_una_excepcion_deja_terminar_como_hace_el_sdk():
    async def roto(entrada, tool_use_id, contexto):
        raise RuntimeError("fallo")

    sesion = SesionSimulada(_opciones({"Stop": [HookMatcher(hooks=[roto])]}))
    assert asyncio.run(sesion.terminar("listo")).termino is True
    assert len(sesion.excepciones_de_hooks) == 1


def test_las_llamadas_quedan_registradas_en_orden():
    sesion = SesionSimulada(_opciones(None), {HERRAMIENTA: lambda _e: OK, OTRA: lambda _e: OK})
    _ejecutar(sesion, HERRAMIENTA, {})
    _ejecutar(sesion, OTRA, {})
    assert [llamada.herramienta for llamada in sesion.llamadas] == [HERRAMIENTA, OTRA]


# ------------------------------------------------------------------ datos de los casos (G1)


def _pasarela(**kwargs):
    from due_diligence.simulacion import PasarelaSimulada

    return PasarelaSimulada(**kwargs)


def _llamar(pasarela, corto, entrada):
    sesion = SesionSimulada(_opciones(None), pasarela.herramientas)
    return json.loads(_ejecutar(sesion, f"mcp__pasarela__{corto}", entrada).texto)


def test_la_pasarela_simulada_devuelve_dos_comercios_parecidos_para_el_nombre_ambiguo():
    from due_diligence.simulacion import comercios_parecidos

    pasarela = _pasarela(registro=comercios_parecidos())
    respuesta = _llamar(pasarela, "consultar_registro_mercantil", {"nombre": "Almacén Mirador"})
    assert respuesta["coincidencias"] == ["CO-AM-0004", "CO-AM-0005"]
    unica = _llamar(pasarela, "consultar_registro_mercantil", {"identificador": "CO-AM-0004"})
    assert unica["coincidencias"] == ["CO-AM-0004"]
    ninguna = _llamar(pasarela, "consultar_registro_mercantil", {"nombre": "Nada Parecido"})
    assert ninguna["resultado"] == "sin_coincidencias"


def test_la_pasarela_simulada_devuelve_coincidencia_de_listas_solo_para_la_persona_del_caso_c():
    pasarela = _pasarela(en_listas={"persona": {"PE-0003"}})
    con = _llamar(
        pasarela, "consultar_listas_restrictivas", {"tipo": "persona", "identificador": "PE-0003"}
    )
    assert con["resultado"] == "coincidencias"
    como_comercio = _llamar(
        pasarela,
        "consultar_listas_restrictivas",
        {"tipo": "comercio", "identificador": "PE-0003"},
    )
    assert como_comercio["resultado"] == "sin_coincidencias"
    otro = _llamar(
        pasarela, "consultar_listas_restrictivas", {"tipo": "persona", "identificador": "PE-0002"}
    )
    assert otro["resultado"] == "sin_coincidencias"


def test_la_pasarela_simulada_clasifica_el_riesgo_por_categoria():
    pasarela = _pasarela()
    alto = _llamar(pasarela, "consultar_riesgo_categoria", {"categoria": "Suplementos Dietarios"})
    assert alto["hechos"][0]["contenido"]["nivel"] == "alto"
    bajo = _llamar(pasarela, "consultar_riesgo_categoria", {"categoria": "talleres"})
    assert bajo["hechos"][0]["contenido"]["nivel"] == "bajo"
    desconocida = _llamar(pasarela, "consultar_riesgo_categoria", {"categoria": "algo raro"})
    assert desconocida["resultado"] == "categoria_desconocida"


def _informe_valido(**cambios):
    """Un informe con la forma del #9 (R2), con datos ficticios."""
    return {
        "comercio": {
            "identificador": "CO-TA-0002",
            "nombre": "Taller Aurora SAS",
            "verificado": True,
        },
        "recomendacion": "habilitar",
        "hallazgos": {
            "registro": [
                {"texto": "Figura activo.", "fuente": "Registro Ficticio", "fecha": "2026-09-30"}
            ]
        },
        "conflictos": {"resumen": "Sin conflictos entre las fuentes registrales.", "lista": []},
        "cobertura": "completa",
    } | cambios


def test_la_pasarela_simulada_guarda_informes_y_escalamientos():
    # #9: el informe tiene que tener la forma del esquema; la igualdad sigue siendo exacta.
    pasarela = _pasarela()
    informe = _llamar(pasarela, "registrar_informe", _informe_valido())
    escalamiento = _llamar(pasarela, "escalar_a_cumplimiento", _resumen_valido())
    assert informe["resultado"] == "informe_registrado"
    assert escalamiento["resultado"] == "caso_escalado"
    assert pasarela.informes == [_informe_valido()]
    assert pasarela.escalamientos == [_resumen_valido()]


def test_la_pasarela_simulada_rechaza_un_resumen_mal_formado_como_la_real():
    # #10, R6: la misma `validar_resumen` que la pasarela; nada se guarda.
    pasarela = _pasarela()
    respuesta = _llamar(pasarela, "escalar_a_cumplimiento", {"causa_escalamiento": "x"})
    assert respuesta["error"] is True and respuesta["tipo"] == "entrada_invalida"
    assert respuesta["mensaje"].startswith("El resumen al oficial no tiene la forma esperada")
    assert pasarela.escalamientos == []


def _resumen_valido():
    """Un resumen al oficial con la forma del #10 (contrato `escalar-a-cumplimiento.md`)."""
    return {
        **{k: v for k, v in _informe_valido().items() if k != "recomendacion"},
        "causa_escalamiento": ["categoría de alto riesgo"],
        "accion_recomendada": "Revisar el caso.",
    }


def test_la_pasarela_simulada_rechaza_un_informe_mal_formado_como_la_real():
    # #9, R12: la misma `validar_informe` que la pasarela; nada se guarda.
    pasarela = _pasarela()
    entrada = _informe_valido()
    del entrada["hallazgos"]["registro"][0]["fuente"]
    respuesta = _llamar(pasarela, "registrar_informe", entrada)
    assert respuesta["error"] is True
    assert respuesta["tipo"] == "entrada_invalida"
    assert respuesta["reintentable"] is False
    assert respuesta["problemas"] == [
        {"ruta": "hallazgos.registro[0].fuente", "texto": "Debe ser un texto no vacío."}
    ]
    assert pasarela.informes == []


# ------------------------------------------------------------------ updatedInput (#8, R1, R8)

INFORME = "mcp__pasarela__registrar_informe"
ENTRADA_DEL_MODELO = {
    "comercio": {"identificador": "CO-TA-0002", "nombre": "Taller Aurora SAS"},
    "recomendacion": "habilitar",
    "hallazgos": {},
    "cobertura": "completa",
}


def _sustituye(entrada):
    # La salida que usa producción (contrato `cobertura.md`, R1).
    return reemplazar_entrada(entrada)


def _sesion_con_pre(salidas_pre, recibido):
    def herramienta(entrada):
        recibido.append(entrada)
        return OK

    traza = _Traza()
    opciones = _opciones(
        {
            "PreToolUse": [
                HookMatcher(matcher=INFORME, hooks=[traza.hook("pre", s) for s in salidas_pre])
            ],
            "PostToolUse": [HookMatcher(matcher=INFORME, hooks=[traza.hook("post")])],
            "PostToolUseFailure": [HookMatcher(matcher=INFORME, hooks=[traza.hook("fallo")])],
        }
    )
    return SesionSimulada(opciones, {INFORME: herramienta}), traza


def test_updated_input_sustituye_la_entrada_entera_y_post_la_ve():
    sustituida = {**ENTRADA_DEL_MODELO, "cobertura": ["Cobertura incompleta: 3 de 4."]}
    recibido = []
    sesion, traza = _sesion_con_pre([_sustituye(sustituida)], recibido)
    resultado = _ejecutar(sesion, INFORME, ENTRADA_DEL_MODELO)
    assert resultado.ejecutada and not resultado.denegada
    assert recibido == [sustituida]
    (post,) = [e for n, e, _ in traza.entradas if n == "post"]
    assert post["tool_input"] == sustituida


def test_updated_input_parcial_no_se_fusiona_con_la_entrada_del_modelo():
    # R1, e3 (medido): el SDK sustituye la entrada entera; con solo la cobertura, la herramienta no
    # recibe los demás campos.
    recibido = []
    sesion, _ = _sesion_con_pre([_sustituye({"cobertura": ["x"]})], recibido)
    _ejecutar(sesion, INFORME, ENTRADA_DEL_MODELO)
    assert recibido == [{"cobertura": ["x"]}]


def test_post_tool_use_failure_tambien_ve_la_entrada_sustituida():
    sustituida = {**ENTRADA_DEL_MODELO, "cobertura": ["y"]}
    sesion, traza = _sesion_con_pre([_sustituye(sustituida)], [])
    _ejecutar(sesion, INFORME, ENTRADA_DEL_MODELO, respuesta=ERROR)
    (fallo,) = [e for n, e, _ in traza.entradas if n == "fallo"]
    assert fallo["tool_input"] == sustituida


def test_un_deny_gana_aunque_otro_hook_devuelva_updated_input():
    # Supuesto conservador de la simulación, NO medido (R1): no se midió cómo mezcla el SDK un deny
    # y un updatedInput de hooks distintos. Producción nunca combina dos PreToolUse sobre la misma
    # herramienta: un solo hook decide deny o sustitución.
    recibido = []
    sesion, _ = _sesion_con_pre(
        [_sustituye({**ENTRADA_DEL_MODELO, "cobertura": ["z"]}), denegar("no")], recibido
    )
    resultado = _ejecutar(sesion, INFORME, ENTRADA_DEL_MODELO)
    assert resultado.denegada and recibido == []


def test_sin_updated_input_la_entrada_llega_sin_cambios():
    recibido = []
    sesion, _ = _sesion_con_pre([permitir()], recibido)
    _ejecutar(sesion, INFORME, ENTRADA_DEL_MODELO)
    assert recibido == [ENTRADA_DEL_MODELO]


# ------------------------------------------------------------------ en_secuencia y escalar_con (#8)


def test_en_secuencia_da_un_resultado_por_ejecucion_y_repite_el_ultimo():
    from due_diligence.frentes import Frente
    from due_diligence.simulacion import en_secuencia, resultado_frente

    primero, segundo = resultado_frente(Frente.NOTICIAS), resultado_frente(Frente.NOTICIAS)
    siguiente = en_secuencia(primero, segundo)
    assert siguiente("contexto") is primero
    assert siguiente("contexto") is segundo
    assert siguiente("otro contexto") is segundo


def test_el_paso_escalar_con_llama_a_escalar_con_esa_entrada():
    from due_diligence.simulacion import CoordinadorSimulado

    entrada = _resumen_valido()  # #10: la pasarela simulada valida el resumen
    coordinador = CoordinadorSimulado([("escalar_con", entrada)])

    async def consumir():
        return [m async for m in coordinador(prompt="p", options=_opciones(None))]

    asyncio.run(consumir())
    assert coordinador.pasarela.escalamientos == [entrada]
    ((tipo, resultado),) = coordinador.pasos
    assert tipo == "escalar_con" and resultado.ejecutada


# ------------------------------------------------------------- #9: informe y mismo mensaje (R12)


def test_el_paso_informe_arma_un_informe_valido_con_las_consultas_del_caso():
    from due_diligence.estado import EstadoCaso
    from due_diligence.frentes import Frente
    from due_diligence.simulacion import consulta, informe_del_caso, respuesta_riesgo
    from servidor_mcp.informe import validar_informe

    estado = EstadoCaso()
    estado.agregar_consultas(
        [
            consulta(Frente.REGISTRO),
            consulta(
                Frente.CATEGORIA, {"categoria": "talleres"}, respuesta_riesgo("talleres", "bajo")
            ),
            consulta(Frente.NOTICIAS, error={"error": True, "tipo": "servicio_no_disponible"}),
        ]
    )
    informe = informe_del_caso(estado, "no_habilitar")
    assert validar_informe(informe) == []
    assert informe["hallazgos"] == {
        "registro": [
            {
                "texto": "Resultado de la consulta: sin_coincidencias.",
                "fuente": "Registro Mercantil Ficticio del Sur",
                "fecha": "2026-09-30",
            }
        ],
        "categoria": [
            {
                "texto": "Resultado de la consulta: categoria_conocida.",
                "fuente": "Catálogo Ficticio de Categorías",
                "fecha": "2026-09-30",
            }
        ],
    }
    # Sin comercio identificado, declara un comercio sin verificar (lo sustituye el hook).
    assert informe["comercio"] == {
        "identificador": None,
        "nombre": "sin identificar",
        "verificado": False,
    }


def test_el_paso_informe_del_coordinador_simulado_registra_ese_informe_valido():
    # T013: el paso `("informe", recomendacion)` del `CoordinadorSimulado`, no solo la función.
    from types import SimpleNamespace

    from due_diligence.estado import EstadoCaso
    from due_diligence.frentes import Frente
    from due_diligence.simulacion import CoordinadorSimulado, consulta, informe_del_caso
    from servidor_mcp.informe import validar_informe

    estado = EstadoCaso()
    estado.agregar_consultas([consulta(Frente.REGISTRO)])
    coordinador = CoordinadorSimulado([("informe", "no_habilitar")])
    coordinador.caso = SimpleNamespace(estado=estado)
    _consumir(coordinador)
    (registrado,) = coordinador.pasarela.informes
    assert registrado == informe_del_caso(estado, "no_habilitar")
    assert validar_informe(registrado) == []
    assert registrado["hallazgos"]["registro"][0]["fuente"] == "Registro Mercantil Ficticio del Sur"


def _consumir(coordinador):
    async def consumir():
        return [m async for m in coordinador(prompt="p", options=_opciones(None))]

    return asyncio.run(consumir())


def test_el_paso_informe_con_envia_la_entrada_tal_cual():
    from due_diligence.simulacion import CoordinadorSimulado

    entrada = _informe_valido(recomendacion="decide_cumplimiento")
    coordinador = CoordinadorSimulado([("informe_con", entrada)])
    _consumir(coordinador)
    assert coordinador.pasarela.informes == [entrada]


def test_el_paso_mismo_mensaje_ejecuta_sus_pasos_a_la_vez():
    from due_diligence.simulacion import CoordinadorSimulado

    coordinador = CoordinadorSimulado(
        [("mismo_mensaje", [("escalar_con", {"causa_escalamiento": "a"}), ("informe_con", {})])]
    )
    orden = []
    escalar = coordinador.pasarela.herramientas["mcp__pasarela__escalar_a_cumplimiento"]
    soltar = asyncio.Event()

    async def escalar_lento(entrada):
        orden.append("escalar empieza")
        await soltar.wait()  # solo avanza si el otro paso corre mientras tanto
        orden.append("escalar termina")
        return escalar(entrada)

    def informe(entrada):
        orden.append("informe")
        soltar.set()
        return {"error": True, "tipo": "entrada_invalida", "mensaje": "m", "reintentable": False}

    coordinador.pasarela.herramientas["mcp__pasarela__escalar_a_cumplimiento"] = escalar_lento
    coordinador.pasarela.herramientas["mcp__pasarela__registrar_informe"] = informe
    _consumir(coordinador)
    assert orden == ["escalar empieza", "informe", "escalar termina"]
    ((tipo, resultados),) = coordinador.pasos
    assert tipo == "mismo_mensaje" and len(resultados) == 2


def test_pre_y_post_reciben_el_mismo_tool_use_id_y_cada_llamada_el_suyo():
    traza = _Traza()
    opciones = _opciones(
        {
            "PreToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("pre")])],
            "PostToolUse": [HookMatcher(matcher=HERRAMIENTA, hooks=[traza.hook("post")])],
        }
    )
    sesion = SesionSimulada(opciones, {HERRAMIENTA: lambda e: OK})

    async def dos_a_la_vez():
        await asyncio.gather(
            sesion.llamar(HERRAMIENTA, {"a": 1}), sesion.llamar(HERRAMIENTA, {"a": 2})
        )

    asyncio.run(dos_a_la_vez())
    ids = {
        (nombre, entrada["tool_input"]["a"]): tool_use_id
        for nombre, entrada, tool_use_id in traza.entradas
    }
    assert ids[("pre", 1)] == ids[("post", 1)]
    assert ids[("pre", 2)] == ids[("post", 2)]
    assert ids[("pre", 1)] != ids[("pre", 2)]


# ------------------------------------------------- #10: el coordinador simulado por turnos (T018)


def _consumir_con(coordinador, opciones):
    async def consumir():
        return [m async for m in coordinador(prompt="p", options=opciones)]

    return asyncio.run(consumir())


def test_el_coordinador_simulado_consume_un_guion_por_turno():
    from claude_agent_sdk import ResultMessage

    from due_diligence.simulacion import CoordinadorSimulado

    uno, dos = _informe_valido(), _informe_valido(recomendacion="decide_cumplimiento")
    coordinador = CoordinadorSimulado(guiones=[[("informe_con", uno)], [("informe_con", dos)]])
    primero = _consumir_con(coordinador, ClaudeAgentOptions())
    assert coordinador.pasarela.informes == [uno]
    segundo = _consumir_con(coordinador, ClaudeAgentOptions(resume="sesion-de-prueba"))
    assert coordinador.pasarela.informes == [uno, dos]
    # Cada turno termina con su `ResultMessage`, con el mismo `session_id` estable.
    for mensajes in (primero, segundo):
        (resultado,) = [m for m in mensajes if isinstance(m, ResultMessage)]
        assert resultado.session_id == "sesion-de-prueba"
    assert coordinador.reanudaciones == [None, "sesion-de-prueba"]


def test_un_guion_solo_sigue_valiendo_como_un_turno():
    from due_diligence.simulacion import CoordinadorSimulado

    entrada = _informe_valido()
    coordinador = CoordinadorSimulado([("informe_con", entrada)])
    _consumir_con(coordinador, ClaudeAgentOptions())
    assert coordinador.pasarela.informes == [entrada]
    assert coordinador.reanudaciones == [None]


def test_un_turno_de_mas_que_el_guion_no_ejecuta_ningun_paso():
    from due_diligence.simulacion import CoordinadorSimulado

    coordinador = CoordinadorSimulado(guiones=[[("informe_con", _informe_valido())]])
    _consumir_con(coordinador, ClaudeAgentOptions())
    _consumir_con(coordinador, ClaudeAgentOptions(resume="sesion-de-prueba"))
    assert len(coordinador.pasarela.informes) == 1


def test_el_mensaje_de_resultado_acepta_otro_session_id():
    from due_diligence.simulacion import mensaje_de_resultado

    assert mensaje_de_resultado().session_id == "sesion-de-prueba"
    assert mensaje_de_resultado(session_id="otra").session_id == "otra"


# ---------------------------------------------- #10: noticias N-0001 y el resumen (T044, R12)


def test_la_pasarela_simulada_devuelve_n_0001_solo_para_el_comercio_que_menciona():
    pasarela = _pasarela()
    for entrada in ({"identificador": "CO-AM-0005"}, {"nombre": "Almacén Mirador Norte SAS"}):
        respuesta = _llamar(pasarela, "buscar_noticias", entrada)
        assert respuesta["resultado"] == "coincidencias"
        (hecho,) = respuesta["hechos"]
        assert hecho["contenido"]["id"] == "N-0001"
        assert hecho["metadatos"] == {"fuente": "Diario Ficticio del Sur", "fecha": "2026-03-18"}
    for entrada in ({"nombre": "Almacén Mirador SAS"}, {"identificador": "CO-AM-0004"}):
        assert _llamar(pasarela, "buscar_noticias", entrada)["resultado"] == "sin_coincidencias"


def test_el_ejecutor_simulado_consulta_noticias_con_su_contexto_y_encuentra_n_0001():
    from due_diligence.frentes import Frente
    from due_diligence.simulacion import EjecutorSimulado

    ejecutor = EjecutorSimulado()
    norte = asyncio.run(
        ejecutor(Frente.NOTICIAS, "Consulta con el identificador «CO-AM-0005».", _opciones(None))
    )
    (consulta,) = norte.consultas
    assert consulta.argumentos == {"identificador": "CO-AM-0005"}
    assert consulta.resultado["hechos"][0]["contenido"]["id"] == "N-0001"
    ambiguo = asyncio.run(
        ejecutor(Frente.NOTICIAS, "Consulta con el nombre «Almacén Mirador SAS».", _opciones(None))
    )
    assert ambiguo.consultas[0].argumentos == {"nombre": "Almacén Mirador SAS"}
    assert ambiguo.consultas[0].resultado["resultado"] == "sin_coincidencias"


@pytest.mark.parametrize(
    "contexto",
    [
        "Consulta con el nombre «Almacén Mirador SAS».",
        "Consulta con el identificador «CO-TA-0002».",
        "Sin dato del comercio.",
    ],
)
def test_las_noticias_simuladas_sin_mencion_llevan_la_fuente_del_diario(contexto):
    # #12 (T021, R10, FR-009): antes llevaban la del registro mercantil, «Registro Mercantil
    # Ficticio del Sur», que podía ocultar un error de procedencia (I.4) en los tests.
    from due_diligence.frentes import Frente
    from due_diligence.simulacion import FECHA, FUENTE_NOTICIAS, EjecutorSimulado

    assert FUENTE_NOTICIAS == "Diario Ficticio del Sur"
    resultado = asyncio.run(EjecutorSimulado()(Frente.NOTICIAS, contexto, _opciones(None)))
    (consulta,) = resultado.consultas
    assert consulta.resultado == {
        "resultado": "sin_coincidencias",
        "hechos": [],
        "metadatos": {"fuentes": [FUENTE_NOTICIAS], "fecha": FECHA},
    }


def test_el_resumen_del_caso_es_valido_y_solo_cita_fuentes_admitidas():
    from due_diligence.estado import EstadoCaso
    from due_diligence.frentes import Frente
    from due_diligence.simulacion import consulta, resumen_del_caso
    from servidor_mcp.informe import validar_resumen

    estado = EstadoCaso()
    estado.agregar_consultas([consulta(Frente.REGISTRO)])
    resumen = resumen_del_caso(estado, "Revisar.")
    assert resumen["accion_recomendada"] == "Revisar."
    assert set(resumen) == {
        "comercio",
        "hallazgos",
        "cobertura",
        "causa_escalamiento",
        "accion_recomendada",
        "conflictos",
    }
    assert validar_resumen(resumen) == []
    from due_diligence.informe import fuentes_consultadas

    assert resumen["hallazgos"]
    for frente, afirmaciones in resumen["hallazgos"].items():
        admitidas = fuentes_consultadas(estado, Frente(frente))
        assert all(a["fuente"] in admitidas for a in afirmaciones), frente


# ------------------------------- #11: turnos por guion y un paso que lanza (T004, U1 del analyze)


def _resultado(mensajes):
    from claude_agent_sdk import ResultMessage

    (resultado,) = [m for m in mensajes if isinstance(m, ResultMessage)]
    return resultado


def test_el_coordinador_simulado_devuelve_los_turnos_de_cada_guion():
    from due_diligence.simulacion import CoordinadorSimulado

    coordinador = CoordinadorSimulado(guiones=[[], []], num_turns=[3, 4])
    primero = _consumir_con(coordinador, ClaudeAgentOptions())
    segundo = _consumir_con(coordinador, ClaudeAgentOptions(resume="sesion-de-prueba"))
    assert (_resultado(primero).num_turns, _resultado(segundo).num_turns) == (3, 4)


def test_sin_turnos_por_guion_cada_turno_sigue_valiendo_uno():
    from due_diligence.simulacion import CoordinadorSimulado

    coordinador = CoordinadorSimulado(guiones=[[], []])
    for resume in (None, "sesion-de-prueba"):
        assert (
            _resultado(_consumir_con(coordinador, ClaudeAgentOptions(resume=resume))).num_turns == 1
        )


def test_el_paso_lanzar_ejecuta_lo_anterior_y_lanza_sin_resultado():
    import pytest

    from due_diligence.simulacion import CoordinadorSimulado

    entrada = _informe_valido()
    error = RuntimeError("fallo simulado del SDK")
    coordinador = CoordinadorSimulado([("informe_con", entrada), ("lanzar", error)])
    mensajes = []

    async def consumir():
        async for mensaje in coordinador(prompt="p", options=ClaudeAgentOptions()):
            mensajes.append(mensaje)

    with pytest.raises(RuntimeError) as lanzada:
        asyncio.run(consumir())
    assert lanzada.value is error
    # El paso anterior se ejecutó; no llegó ningún mensaje, tampoco el `ResultMessage`.
    assert coordinador.pasarela.informes == [entrada]
    assert mensajes == []


def test_un_caso_con_el_paso_lanzar_termina_el_turno_como_anomalo_y_relanza():
    import pytest

    from due_diligence.coordinador import Caso
    from due_diligence.simulacion import CoordinadorSimulado, EjecutorSimulado
    from due_diligence.terminacion import Terminacion

    coordinador = CoordinadorSimulado([("lanzar", RuntimeError("fallo simulado del SDK"))])
    caso = Caso(ejecutor=EjecutorSimulado(resultados={}), consulta=coordinador)
    coordinador.caso = caso
    with pytest.raises(RuntimeError):
        asyncio.run(caso.ejecutar("Necesito el due diligence de Taller Aurora SAS."))
    assert caso.terminacion.terminacion is Terminacion.ANOMALA
    assert caso.terminacion.terminal_reason == "excepción RuntimeError"
