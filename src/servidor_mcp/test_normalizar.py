"""Pruebas de la normalización y la coincidencia de nombres (R3)."""

import pytest

from servidor_mcp.normalizar import (
    MINIMO_CARACTERES,
    contiene,
    cumple_minimo,
    igual,
    normalizar,
)


def test_puntos_se_eliminan_y_sas_es_igual():
    assert normalizar("S.A.S.") == normalizar("SAS") == "sas"


def test_tildes_y_enie():
    assert normalizar("Almacén") == "almacen"
    assert normalizar("Año Nuevo") == "ano nuevo"
    assert normalizar("Río Fino") == "rio fino"


def test_mayusculas():
    assert normalizar("TIENDA VERDE") == "tienda verde"


def test_espacios_repetidos_y_bordes():
    assert normalizar("  Tienda   Verde  ") == "tienda verde"


def test_apostrofo_se_elimina():
    assert normalizar("O'Brien") == "obrien"


@pytest.mark.parametrize("signo", [",", "-", "/", "(", ")", ";"])
def test_otros_signos_pasan_a_espacio(signo):
    assert normalizar(f"Casa{signo}Norte") == "casa norte"


def test_digitos_se_conservan():
    assert normalizar("Local 12-B") == "local 12 b"


def test_texto_vacio():
    assert normalizar("") == ""
    assert normalizar("  .  ") == ""


def test_contiene_es_subcadena_del_nombre_normalizado():
    assert contiene("almacen mirador", "Almacén Mirador Norte S.A.S.")
    assert contiene("Almacén Mirador", "Almacén Mirador SAS")
    assert contiene("mirador norte", "Almacén Mirador Norte SAS")


def test_contiene_no_coincide_si_no_esta():
    assert not contiene("almacen sur", "Almacén Mirador Norte SAS")


def test_contiene_normaliza_los_dos_lados():
    assert contiene("S.A.S.", "Tienda Verde SAS")


def test_igual_es_el_nombre_completo_normalizado():
    assert igual("tienda verde sas", "Tienda Verde S.A.S.")
    assert igual("TIENDA VERDE SAS", "tienda verde sas")


def test_igual_nunca_es_parcial():
    assert not igual("tienda verde", "Tienda Verde SAS")
    assert not igual("Tienda Verde SAS", "tienda verde")


def test_minimo_de_caracteres_normalizados():
    assert MINIMO_CARACTERES == 3
    assert not cumple_minimo("ab")
    assert not cumple_minimo(" a. ")
    assert cumple_minimo("abc")
    assert cumple_minimo("S.A.S.")  # normaliza a «sas», 3 caracteres


def test_minimo_cuenta_el_texto_normalizado_y_no_el_original():
    assert not cumple_minimo("a....")  # el original tiene 5, el normalizado «a» tiene 1
    assert normalizar("a . b") == "a b"
    assert cumple_minimo("a . b")  # «a b» tiene 3 caracteres
