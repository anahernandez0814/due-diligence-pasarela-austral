"""Pruebas de la normalización y la coincidencia de nombres (R3)."""

import pytest

from servidor_mcp.normalizar import (
    MINIMO_CARACTERES,
    contiene,
    contiene_en_registro,
    cumple_minimo,
    igual,
    igual_identificador,
    normalizar,
    sin_forma_juridica,
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
    assert cumple_minimo("Mirador")


def test_minimo_cuenta_el_texto_normalizado_y_no_el_original():
    assert not cumple_minimo("a....")  # el original tiene 5, el normalizado «a» tiene 1
    assert normalizar("a . b") == "a b"
    assert cumple_minimo("a . b")  # «a b» tiene 3 caracteres


@pytest.mark.parametrize(
    "texto",
    [
        "Almacén Mirador SAS",
        "Almacén Mirador S.A.S.",
        "Almacén Mirador S.A.",
        "Almacén Mirador SA",
        "Almacén Mirador Ltda.",
        "Almacén Mirador LTDA",
        "Almacén Mirador E.U.",
        "Almacén Mirador EU",
        "Almacén Mirador S.C.A.",
        "Almacén Mirador SCA",
        "Almacén Mirador S. en C.",
        "Almacén Mirador S en C",
        "almacen mirador",
    ],
)
def test_sin_forma_juridica_quita_la_forma_final(texto):
    assert sin_forma_juridica(texto) == "almacen mirador"


def test_la_forma_juridica_solo_se_quita_al_final():
    assert sin_forma_juridica("SAS Mirador") == "sas mirador"
    assert sin_forma_juridica("Casa SA Norte") == "casa sa norte"
    assert sin_forma_juridica("Sasa Mirador") == "sasa mirador"


def test_una_forma_juridica_pegada_a_otra_palabra_no_se_quita():
    assert sin_forma_juridica("Almacen Pesas") == "almacen pesas"
    assert sin_forma_juridica("Tienda Casa") == "tienda casa"


def test_solo_la_forma_juridica_queda_vacia():
    for solo in ("SAS", "S.A.S.", "sa", "Ltda.", "S. en C."):
        assert sin_forma_juridica(solo) == ""


def test_varias_formas_finales_se_quitan_todas():
    assert sin_forma_juridica("Casa S.A. SAS") == "casa"


def test_el_minimo_se_cuenta_despues_de_quitar_la_forma_juridica():
    assert not cumple_minimo("SAS")
    assert not cumple_minimo("S.A.S.")
    assert not cumple_minimo("Ltda.")
    assert not cumple_minimo("ab SAS")
    assert cumple_minimo("abc SAS")


def test_contiene_en_registro_ignora_la_forma_juridica_de_los_dos_lados():
    nombre_norte = "Almacén Mirador Norte S.A.S."
    nombre_mirador = "Almacén Mirador SAS"
    for buscado in ("Almacén Mirador SAS", "Almacén Mirador S.A.S.", "almacen mirador"):
        assert contiene_en_registro(buscado, nombre_norte)
        assert contiene_en_registro(buscado, nombre_mirador)
    assert contiene_en_registro("Mirador Norte SAS", nombre_norte)
    assert not contiene_en_registro("Mirador Norte SAS", nombre_mirador)


def test_contiene_en_registro_con_otra_forma_juridica():
    assert contiene_en_registro("Ferretería Río Fino Ltda", "Ferretería Río Fino SAS")


def test_contiene_en_registro_no_coincide_con_solo_la_forma_juridica():
    assert not contiene_en_registro("SAS", "Almacén Mirador SAS")
    assert not contiene_en_registro("", "Almacén Mirador SAS")


def test_contiene_sigue_siendo_literal_para_el_resto_de_usos():
    assert not contiene("Almacén Mirador SAS", "Almacén Mirador Norte SAS")


def test_el_identificador_no_distingue_mayusculas():
    assert igual_identificador("co-tv-0001", "CO-TV-0001")
    assert igual_identificador(" Co-Tv-0001 ", "CO-TV-0001")
    assert not igual_identificador("CO-TV", "CO-TV-0001")
    assert not igual_identificador("CO-TV-0002", "CO-TV-0001")
