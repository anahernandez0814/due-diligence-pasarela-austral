"""Pruebas de los validadores de parámetros (R2).

El SDK rechaza, en inglés y sin estructura, un argumento ausente o mal tipado antes de entrar a
la herramienta. Por eso los parámetros son opcionales y estos validadores devuelven el valor o
un error estructurado en español. Nunca lanzan.
"""

import pytest

from servidor_mcp.entradas import (
    campos_obligatorios,
    exactamente_uno,
    objeto_obligatorio,
    texto_obligatorio,
)


def _error(resultado):
    assert resultado.is_error is True
    return resultado.structured_content


# --- texto_obligatorio ---------------------------------------------------------------------


def test_texto_valido_se_devuelve_sin_espacios_de_los_bordes():
    valor, err = texto_obligatorio("  Tienda Verde  ", "nombre")
    assert (valor, err) == ("Tienda Verde", None)


@pytest.mark.parametrize("vacio", [None, "", "   ", "\t\n"])
def test_texto_ausente_o_vacio_es_entrada_invalida(vacio):
    valor, err = texto_obligatorio(vacio, "nombre")
    cuerpo = _error(err)
    assert valor is None
    assert cuerpo["tipo"] == "entrada_invalida"
    assert cuerpo["reintentable"] is False
    assert "nombre" in cuerpo["mensaje"]


@pytest.mark.parametrize("incorrecto", [5, 1.5, True, ["a"], {"a": 1}])
def test_texto_de_tipo_incorrecto_nombra_el_parametro_y_el_tipo_esperado(incorrecto):
    valor, err = texto_obligatorio(incorrecto, "categoria")
    cuerpo = _error(err)
    assert valor is None
    assert cuerpo["tipo"] == "entrada_invalida"
    assert "categoria" in cuerpo["mensaje"]
    assert "texto" in cuerpo["mensaje"]


# --- exactamente_uno -----------------------------------------------------------------------


def test_exactamente_uno_con_nombre():
    clave_valor, err = exactamente_uno("Tienda Verde", None)
    assert (clave_valor, err) == (("nombre", "Tienda Verde"), None)


def test_exactamente_uno_con_identificador():
    clave_valor, err = exactamente_uno(None, " CO-TV-0001 ")
    assert (clave_valor, err) == (("identificador", "CO-TV-0001"), None)


def test_un_valor_vacio_cuenta_como_ausente():
    clave_valor, err = exactamente_uno("   ", "CO-TV-0001")
    assert (clave_valor, err) == (("identificador", "CO-TV-0001"), None)


@pytest.mark.parametrize(
    "nombre, identificador", [("a b c", "CO-TV-0001"), (None, None), ("", " ")]
)
def test_los_dos_o_ninguno_es_entrada_invalida(nombre, identificador):
    clave_valor, err = exactamente_uno(nombre, identificador)
    cuerpo = _error(err)
    assert clave_valor is None
    assert cuerpo["tipo"] == "entrada_invalida"
    assert cuerpo["reintentable"] is False
    assert "nombre" in cuerpo["mensaje"] and "identificador" in cuerpo["mensaje"]


def test_el_tipo_incorrecto_del_valor_dado_es_entrada_invalida():
    clave_valor, err = exactamente_uno(7, None)
    cuerpo = _error(err)
    assert clave_valor is None
    assert cuerpo["tipo"] == "entrada_invalida"
    assert "nombre" in cuerpo["mensaje"]


# --- objeto_obligatorio --------------------------------------------------------------------


def test_objeto_valido_se_devuelve():
    valor, err = objeto_obligatorio({"identificador": "CO-TV-0001"}, "comercio")
    assert (valor, err) == ({"identificador": "CO-TV-0001"}, None)


@pytest.mark.parametrize("vacio", [None, {}])
def test_objeto_ausente_o_vacio_es_entrada_invalida(vacio):
    valor, err = objeto_obligatorio(vacio, "comercio")
    assert valor is None
    assert _error(err)["tipo"] == "entrada_invalida"
    assert "comercio" in _error(err)["mensaje"]


@pytest.mark.parametrize("incorrecto", ["texto", 5, ["a"]])
def test_objeto_de_tipo_incorrecto_es_entrada_invalida(incorrecto):
    valor, err = objeto_obligatorio(incorrecto, "comercio")
    assert valor is None
    assert "objeto" in _error(err)["mensaje"]


# --- campos_obligatorios -------------------------------------------------------------------

REQUERIDOS = {"comercio": dict, "recomendacion": str, "hallazgos": dict, "cobertura": (str, list)}


def _completos():
    return {
        "comercio": {"identificador": "CO-TV-0001"},
        "recomendacion": "habilitar",
        "hallazgos": {"registro": {"contenido": "x", "fuente": "y"}},
        "cobertura": "completa",
    }


def test_campos_completos_no_dan_error():
    assert campos_obligatorios(_completos(), REQUERIDOS) is None


def test_devuelve_todos_los_campos_que_faltan():
    entrada = {"recomendacion": "habilitar"}
    cuerpo = _error(campos_obligatorios(entrada, REQUERIDOS))
    assert cuerpo["tipo"] == "campos_obligatorios_ausentes"
    assert cuerpo["reintentable"] is False
    assert cuerpo["campos_faltantes"] == ["comercio", "hallazgos", "cobertura"]
    for nombre in ("comercio", "hallazgos", "cobertura"):
        assert nombre in cuerpo["mensaje"]


@pytest.mark.parametrize("vacio", [None, "", "  ", {}, []])
def test_un_campo_vacio_cuenta_como_faltante(vacio):
    entrada = _completos() | {"cobertura": vacio}
    cuerpo = _error(campos_obligatorios(entrada, REQUERIDOS))
    assert cuerpo["campos_faltantes"] == ["cobertura"]


def test_cobertura_acepta_texto_o_lista():
    assert (
        campos_obligatorios(_completos() | {"cobertura": ["registro", "listas"]}, REQUERIDOS)
        is None
    )


def test_un_tipo_incorrecto_es_entrada_invalida_y_nombra_todos_los_campos():
    entrada = _completos() | {"comercio": "texto", "recomendacion": 5}
    cuerpo = _error(campos_obligatorios(entrada, REQUERIDOS))
    assert cuerpo["tipo"] == "entrada_invalida"
    assert cuerpo["reintentable"] is False
    assert "comercio" in cuerpo["mensaje"] and "recomendacion" in cuerpo["mensaje"]
    assert "campos_faltantes" not in cuerpo


def test_si_faltan_y_hay_tipos_incorrectos_se_informan_primero_los_que_faltan():
    entrada = _completos() | {"comercio": "texto"}
    del entrada["cobertura"]
    cuerpo = _error(campos_obligatorios(entrada, REQUERIDOS))
    assert cuerpo["tipo"] == "campos_obligatorios_ausentes"
    assert cuerpo["campos_faltantes"] == ["cobertura"]


def test_cero_y_falso_no_son_vacios_son_tipo_incorrecto():
    entrada = _completos() | {"recomendacion": 0}
    cuerpo = _error(campos_obligatorios(entrada, REQUERIDOS))
    assert cuerpo["tipo"] == "entrada_invalida"


def test_los_validadores_nunca_lanzan_con_valores_raros():
    class Raro:
        def __str__(self):  # pragma: no cover - no debe invocarse
            raise RuntimeError("no se debe llamar")

    for valor in (Raro(), object(), b"bytes", 3 + 4j):
        assert texto_obligatorio(valor, "x")[1] is not None
        assert objeto_obligatorio(valor, "x")[1] is not None
        assert exactamente_uno(valor, None)[1] is not None
        assert campos_obligatorios({"comercio": valor}, {"comercio": dict}) is not None
