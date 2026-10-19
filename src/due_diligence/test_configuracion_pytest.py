"""La marca `e2e` y los dos grupos de pruebas (#12, R4, R5, FR-004, US2).

`uv run pytest` no selecciona los casos de punta a punta, tenga o no la clave; pedidos sin la clave,
se omiten con el motivo y sin crear ningún caso. Como máximo dos subprocesos de pytest, porque la
suite determinista ya ronda los cinco minutos (P1 del analyze), y ninguno puede llamar al modelo:
el segundo define una clave ficticia y una credencial alternativa ficticia, que
`comprobar_credencial` rechaza siempre con `MENSAJE_OTRA_CREDENCIAL`. Así el motivo es el mismo
con o sin el archivo de entorno (que no pisa variables ya definidas) y con o sin una clave en el
entorno de quien ejecuta (H1 del analyze; corrección de la revisión en una copia limpia).

El hijo escribe en UTF-8 (`PYTHONIOENCODING`): en Windows, sin `PYTHONUTF8`, escribiría en cp1252
y la «á» del motivo rompería la lectura de su salida.
"""

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from due_diligence import configuracion, conftest

RAIZ = Path(__file__).resolve().parents[2]
E2E = Path(__file__).with_name("test_e2e_casos.py")


def _pytest(*argumentos, entorno=None):
    hijo = dict(os.environ if entorno is None else entorno)
    hijo["PYTHONIOENCODING"] = "utf-8"
    hijo["COLUMNS"] = "300"  # el motivo de la omisión, en una sola línea del resumen
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *argumentos, str(E2E)],
        cwd=RAIZ,
        env=hijo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def test_la_marca_e2e_esta_registrada_y_excluida_por_defecto():
    opciones = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_ini = opciones["tool"]["pytest"]["ini_options"]
    assert any(m.startswith("e2e:") for m in pytest_ini["markers"])
    addopts = pytest_ini["addopts"]
    assert addopts[addopts.index("-m") + 1] == "not e2e"


def test_por_defecto_no_se_selecciona_ningun_caso_e2e():
    salida = _pytest("--collect-only", "-q")
    assert "7 deselected" in salida.stdout, salida.stdout + salida.stderr


def test_sin_la_credencial_no_se_crea_ningun_caso():
    creados = []
    problema, ejecuciones = conftest.preparar_ejecuciones(
        list("abcdefg"),
        {},
        lambda letra: RAIZ / "no-se-usa",
        crear_caso=lambda entorno: creados.append(entorno),
    )
    assert problema == configuracion.MENSAJE_SIN_CLAVE
    assert ejecuciones == {} and creados == []


def test_pedidos_sin_una_credencial_valida_los_siete_se_omiten_con_el_motivo():
    entorno = dict(os.environ)
    entorno[configuracion.VARIABLE_CLAVE] = "clave-ficticia-de-prueba"
    entorno["ANTHROPIC_AUTH_TOKEN"] = "token-ficticio-de-prueba"
    salida = _pytest("-m", "e2e", "-rs", entorno=entorno)
    assert "7 skipped" in salida.stdout, salida.stdout + salida.stderr
    motivo = configuracion.MENSAJE_OTRA_CREDENCIAL.format(variable="ANTHROPIC_AUTH_TOKEN")
    # Con `-rs`, el resumen trae una línea SKIPPED con el motivo (US2-3).
    assert "SKIPPED" in salida.stdout and motivo[:60] in salida.stdout.replace("\n", "")
    assert "passed" not in salida.stdout and "failed" not in salida.stdout


def test_las_letras_seleccionadas_salen_del_nombre_de_los_tests_e2e():
    class Item:
        def __init__(self, name, e2e=True):
            self.name, self._e2e = name, e2e

        def get_closest_marker(self, nombre):
            return self._e2e if nombre == "e2e" else None

    items = [
        Item("test_caso_d_dos_turnos"),
        Item("test_caso_a_alto_riesgo"),
        Item("test_caso_d_dos_turnos"),
        Item("test_caso_b_bajo_riesgo", e2e=False),
        Item("test_otro"),
    ]
    assert conftest.letras_seleccionadas(items) == ["d", "a"]


def test_el_entorno_de_cada_caso_lleva_solo_sus_modos_y_su_carpeta(tmp_path):
    base = {
        "PASARELA_FALLA_NOTICIAS": "1",
        "PASARELA_FALLA_REGISTRO": "1",
        configuracion.VARIABLE_MODO_DEMO: "1",
        "PASARELA_RESULTADOS_DIR": "resultados",
        "OTRA": "x",
    }
    entorno_b = conftest.entorno_del_caso(base, conftest.CASOS["b"], tmp_path)
    assert entorno_b == {"OTRA": "x", "PASARELA_RESULTADOS_DIR": str(tmp_path)}
    entorno_f = conftest.entorno_del_caso(base, conftest.CASOS["f"], tmp_path)
    assert entorno_f["PASARELA_FALLA_NOTICIAS"] == "1"
    assert configuracion.VARIABLE_MODO_DEMO not in entorno_f
    entorno_e = conftest.entorno_del_caso(base, conftest.CASOS["e"], tmp_path)
    assert entorno_e[configuracion.VARIABLE_MODO_DEMO] == "1"
    assert "PASARELA_FALLA_NOTICIAS" not in entorno_e
    assert base["PASARELA_RESULTADOS_DIR"] == "resultados"  # la base no cambia


def test_los_siete_casos_estan_definidos_y_el_d_tiene_dos_turnos():
    assert sorted(conftest.CASOS) == list("abcdefg")
    assert conftest.CASOS["d"].mensajes[1] == "CO-AM-0004"
    assert all(len(c.mensajes) == 1 for letra, c in conftest.CASOS.items() if letra != "d")
