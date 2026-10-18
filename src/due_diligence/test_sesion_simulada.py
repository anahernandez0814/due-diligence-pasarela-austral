"""Tests de `SesionSimulada` (R4, R12): una sesión de agente que ejecuta los hooks de sus opciones
como lo hace el SDK 0.2.168, sin llamar al modelo.

El orden y los efectos reproducen lo medido en `research.md` (R1 a R3): `PreToolUse` → herramienta →
`PostToolUse` (éxito) o `PostToolUseFailure` (error estructurado); un `deny` impide ejecutar la
herramienta y el modelo recibe el motivo; una excepción en un hook **deja pasar la acción**; un
`Stop` con `block` hace continuar y `stop_hook_active` pasa a `True`.
"""

import asyncio
import json

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from due_diligence.hooks import bloquear_cierre, denegar, permitir
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


def test_la_pasarela_simulada_guarda_informes_y_escalamientos():
    pasarela = _pasarela()
    informe = _llamar(pasarela, "registrar_informe", {"recomendacion": "habilitar"})
    escalamiento = _llamar(pasarela, "escalar_a_cumplimiento", {"causa_escalamiento": "x"})
    assert informe["resultado"] == "informe_registrado"
    assert escalamiento["resultado"] == "caso_escalado"
    assert pasarela.informes == [{"recomendacion": "habilitar"}]
    assert pasarela.escalamientos == [{"causa_escalamiento": "x"}]
