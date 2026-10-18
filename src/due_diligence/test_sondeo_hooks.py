"""Tests de la lógica del sondeo de hooks (T048, Q4): comparar lo esperado con lo medido.

El sondeo real llama al modelo y se ejecuta a mano; aquí solo se prueban, con mediciones
simuladas, la comparación, el informe y los códigos de salida. Ningún test llama al modelo.
"""

import ast
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
