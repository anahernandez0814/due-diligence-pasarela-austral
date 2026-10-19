"""Tests de la lógica del sondeo de hooks (T048, Q4): comparar lo esperado con lo medido.

El sondeo real llama al modelo y se ejecuta a mano; aquí solo se prueban, con mediciones
simuladas, la comparación, el informe y los códigos de salida. Ningún test llama al modelo.
"""

import ast
import json
import pathlib

import pytest

from due_diligence import sondeo_hooks
from due_diligence.sondeo_hooks import NO_CONCLUYENTE, Medicion, informe, main, veredicto


def _medicion(esperado="x", medido="x", clave="clave"):
    return Medicion(clave, "descripción", esperado, medido)


def test_una_medicion_igual_a_lo_esperado_coincide():
    assert veredicto(_medicion("str", "str")) == "coincide"


def test_una_medicion_distinta_de_lo_esperado_difiere():
    assert veredicto(_medicion("str", "list")) == "difiere"


def test_si_el_modelo_no_hizo_la_llamada_el_resultado_es_inconcluso_no_un_fallo():
    assert veredicto(_medicion("str", NO_CONCLUYENTE)) == "inconcluso"


def test_el_informe_nombra_cada_medicion_con_su_veredicto_y_lo_esperado_frente_a_lo_medido():
    texto = informe(
        [
            _medicion("str", "str", "a_forma"),
            _medicion("PostToolUseFailure", "PostToolUse", "b_vias"),
            _medicion(True, NO_CONCLUYENTE, "c_deny"),
        ]
    )
    assert "a_forma" in texto and "coincide" in texto
    assert "b_vias" in texto and "difiere" in texto
    assert "esperado: 'PostToolUseFailure'" in texto and "medido: 'PostToolUse'" in texto
    assert "c_deny" in texto and "inconcluso" in texto


def test_el_informe_no_incluye_mas_que_lo_medido():
    texto = informe([_medicion("a", "a")])
    assert "CO-TV" not in texto and "tool_response" not in texto


@pytest.fixture
def con_mediciones(monkeypatch):
    def fijar(*mediciones):
        async def sondear():
            return list(mediciones)

        monkeypatch.setattr(sondeo_hooks, "sondear", sondear)

    return fijar


def test_main_devuelve_cero_si_todo_coincide(con_mediciones, capsys):
    con_mediciones(_medicion("a", "a"), _medicion("b", "b"))
    assert main() == 0
    assert "coincide" in capsys.readouterr().out


def test_main_devuelve_uno_si_algo_difiere_y_dice_que_dejo_de_cumplirse(con_mediciones, capsys):
    con_mediciones(_medicion("a", "a"), _medicion("b", "otra cosa", "b_clave"))
    assert main() == 1
    salida = capsys.readouterr().out
    assert "difiere" in salida and "b_clave" in salida


def test_main_devuelve_dos_si_solo_hay_mediciones_inconclusas(con_mediciones):
    con_mediciones(_medicion("a", "a"), _medicion("b", NO_CONCLUYENTE))
    assert main() == 2


def test_una_diferencia_pesa_mas_que_una_medicion_inconclusa(con_mediciones):
    con_mediciones(_medicion("a", NO_CONCLUYENTE), _medicion("b", "otra"))
    assert main() == 1


def test_el_sondeo_no_se_importa_desde_el_paquete_ni_lee_archivos_de_entorno():
    paquete = pathlib.Path(sondeo_hooks.__file__).parent
    assert "sondeo_hooks" not in (paquete / "__init__.py").read_text(encoding="utf-8")
    fuente = pathlib.Path(sondeo_hooks.__file__).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    llamadas = {
        nodo.func.id if isinstance(nodo.func, ast.Name) else getattr(nodo.func, "attr", "")
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
    }
    assert "load_dotenv" not in llamadas and "cargar_entorno" not in llamadas
    assert "dotenv" not in fuente.lower()


def test_el_sondeo_usa_las_opciones_aisladas_del_paquete():
    fuente = pathlib.Path(sondeo_hooks.__file__).read_text(encoding="utf-8")
    assert "opciones_base" in fuente  # setting_sources=[] y tools=[] salen de ahí (R2 del #6)
    assert "ClaudeAgentOptions(" not in fuente


# ------------------------------------------------------------------ la salida de error de la CLI


def test_las_opciones_del_sondeo_recogen_el_stderr_de_la_cli_en_vez_de_imprimirlo():
    from due_diligence import configuracion

    opciones = sondeo_hooks._opciones([], {}, None)
    assert opciones.stderr is sondeo_hooks.recoger_stderr
    assert opciones.stderr is not configuracion.filtrar_stderr


def _con_stderr(monkeypatch, *mediciones):
    async def sondear():
        sondeo_hooks.recoger_stderr("Error in hook callback hook_0: 11 | // Version: 2.1.301")
        sondeo_hooks.recoger_stderr("error: fallo simulado del hook")
        return list(mediciones)

    monkeypatch.setattr(sondeo_hooks, "sondear", sondear)
    sondeo_hooks.STDERR_DE_LA_CLI.clear()


def test_si_todo_coincide_solo_se_ven_las_mediciones_y_el_resumen(monkeypatch, capsys):
    _con_stderr(monkeypatch, _medicion("a", "a"), _medicion("b", "b"))
    assert main() == 0
    salida = capsys.readouterr()
    assert "Error in hook callback" not in salida.out + salida.err
    assert "Resumen:" in salida.out


def test_si_algo_no_coincide_se_muestra_el_stderr_recogido_para_diagnosticar(monkeypatch, capsys):
    _con_stderr(monkeypatch, _medicion("a", "a"), _medicion("b", "otra"))
    assert main() == 1
    salida = capsys.readouterr().out
    assert "Salida de error de la CLI" in salida and "Error in hook callback" in salida


def test_el_aviso_de_conectores_no_se_recoge():
    sondeo_hooks.STDERR_DE_LA_CLI.clear()
    sondeo_hooks.recoger_stderr("claude.ai connectors are disabled")
    assert sondeo_hooks.STDERR_DE_LA_CLI == []


# ------------------------------------------------------------------ experimentos del #8 (R9)


def test_los_experimentos_del_8_se_ejecutan_despues_de_los_del_7():
    nombres = [e.__name__ for e in sondeo_hooks.EXPERIMENTOS]
    assert nombres == [
        "_forma_de_tool_response",
        "_via_del_error_estructurado",
        "_excepcion_y_deny",
        "_stop_con_block",
        "_hooks_del_caso",
        "_updated_input",
        "_turnos_de_reintento",
        "_cobertura_del_caso",
        "_reanudacion",  # g6, #10 (R1): `resume` continúa la sesión del coordinador
    ]


def test_el_pedido_lleva_los_argumentos_exactos_con_cobertura_completa():
    pedido = sondeo_hooks.pedir_con("registrar_informe", sondeo_hooks.ENTRADA_INFORME)
    assert "registrar_informe" in pedido
    argumentos = json.loads(pedido.split("responde ok: ", 1)[1])
    assert argumentos == sondeo_hooks.ENTRADA_INFORME
    assert argumentos["cobertura"] == "completa"  # lo que el hook debe sustituir


def test_la_entrada_del_informe_tiene_la_forma_del_9():
    from servidor_mcp.informe import validar_informe

    assert validar_informe(sondeo_hooks.ENTRADA_INFORME) == []


def test_el_hook_del_informe_acepta_la_entrada_de_g4_y_pone_los_datos_del_codigo():
    # Sin el modelo: si el hook la rechazara, g4 mediría «no concluyente» en vez de la cobertura.
    import asyncio

    from due_diligence.cobertura import calcular_cobertura
    from due_diligence.conflictos import sin_comparar

    estado, hooks = sondeo_hooks.caso_del_sondeo_de_cobertura()
    (matcher,) = [m for m in hooks.coordinador()["PreToolUse"] if m.matcher == sondeo_hooks.INFORME]
    entrada = {
        "hook_event_name": "PreToolUse",
        "tool_name": sondeo_hooks.INFORME,
        "tool_input": sondeo_hooks.ENTRADA_INFORME,
        "tool_use_id": "t1",
    }
    salida = asyncio.run(matcher.hooks[0](entrada, "t1", None))
    assert salida["hookSpecificOutput"]["updatedInput"] == {
        "comercio": {
            "identificador": "CO-TV-0001",
            "nombre": "Tienda Verde SAS",
            "verificado": False,
        },
        "recomendacion": "no_habilitar",
        "hallazgos": sondeo_hooks.ENTRADA_INFORME["hallazgos"],
        # El registro del sondeo no se delegó: no hay comercio identificado (no está caído).
        "conflictos": sin_comparar("sin_comercio").como_entrada(),
        "cobertura": calcular_cobertura(estado).lineas(),
    }


def test_guardados_lee_solo_los_json_que_son_objetos(tmp_path):
    (tmp_path / "informes").mkdir()
    (tmp_path / "informes" / "a.json").write_text('{"cobertura": ["x"]}', encoding="utf-8")
    (tmp_path / "b.json").write_text("[1, 2]", encoding="utf-8")
    (tmp_path / "c.json").write_text("no es json", encoding="utf-8")
    (tmp_path / "d.txt").write_text('{"cobertura": "y"}', encoding="utf-8")
    assert sondeo_hooks.guardados(tmp_path) == [{"cobertura": ["x"]}]


def test_el_tipo_esperado_de_la_entrada_parcial_es_el_que_da_la_pasarela():
    # Sin los demás campos obligatorios, la pasarela no escribe nada y devuelve este tipo.
    from servidor_mcp import decisiones

    error = decisiones.registrar_informe(cobertura=sondeo_hooks.COBERTURA_DEL_SONDEO)
    assert error.is_error is True
    assert error.structured_content["tipo"] == sondeo_hooks.TIPO_ERROR_ENTRADA_PARCIAL


def test_los_turnos_esperados_son_un_reintento_y_dos_devoluciones():
    # Primer intento, reintento, tres respuestas finales (dos devueltas por el Stop): R2 del #8.
    assert sondeo_hooks.TURNOS_REINTENTO_Y_DOS_DEVOLUCIONES == 5


# ---------------------------------------------------------- #10: g5 en el formato nuevo y g6 (T049)


def test_la_entrada_de_g5_tiene_la_forma_del_resumen_al_oficial():
    from servidor_mcp.informe import validar_resumen

    assert validar_resumen(sondeo_hooks.ENTRADA_ESCALAMIENTO) == []


def test_el_hook_del_escalamiento_acepta_la_entrada_de_g5_y_pone_la_cobertura_del_codigo():
    # Sin el modelo: si el hook la rechazara, g5 mediría «no concluyente» en vez de la cobertura.
    import asyncio

    from due_diligence.cobertura import calcular_cobertura

    estado, hooks = sondeo_hooks.caso_del_sondeo_de_cobertura()
    (matcher,) = [m for m in hooks.coordinador()["PreToolUse"] if m.matcher == sondeo_hooks.ESCALAR]
    entrada = {
        "hook_event_name": "PreToolUse",
        "tool_name": sondeo_hooks.ESCALAR,
        "tool_input": sondeo_hooks.ENTRADA_ESCALAMIENTO,
        "tool_use_id": "t1",
    }
    salida = asyncio.run(matcher.hooks[0](entrada, "t1", None))
    sustituida = salida["hookSpecificOutput"]["updatedInput"]
    assert sustituida["cobertura"] == calcular_cobertura(estado).lineas()
    assert sustituida["hallazgos"] == sondeo_hooks.ENTRADA_ESCALAMIENTO["hallazgos"]


def test_g6_espera_el_contexto_el_stop_reanudado_y_los_turnos_por_turno(monkeypatch):
    # Sin el modelo: las sesiones se sustituyen; se comprueba qué espera g6 y que el segundo turno
    # reanuda la sesión del primero, sin repetirle el código (si no, no mediría el contexto).
    import asyncio

    codigo = sondeo_hooks.CODIGO_DEL_SONDEO
    assert codigo in sondeo_hooks.PRIMER_TURNO and codigo not in sondeo_hooks.SEGUNDO_TURNO
    reanudaciones = []

    async def falsa(prompt, opciones):
        reanudaciones.append(opciones.resume)
        traza = sondeo_hooks.Traza(llamadas=["mcp__caso__anotar"], num_turns=2)
        return sondeo_hooks._ConSesion(traza, "s-1")

    monkeypatch.setattr(sondeo_hooks, "_correr_con_sesion", falsa)
    mediciones = asyncio.run(sondeo_hooks._reanudacion())
    assert [(m.clave, m.esperado) for m in mediciones] == [
        ("g6_contexto", [codigo]),
        ("g6_stop_reanudado", True),
        ("g6_turnos_por_turno", 2),
    ]
    assert reanudaciones == [None, "s-1"]
