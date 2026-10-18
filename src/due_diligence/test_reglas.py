"""Tests de las reglas puras de negocio I.1, I.2 e I.3 (R7 a R10, FR-002, FR-003, FR-005, FR-008).

Son funciones puras: reciben el estado o el libro y devuelven una decisión. No tocan el SDK ni el
modelo. Los datos son los ficticios del #5; ningún valor tiene forma de tarjeta, NIT o cédula.
"""

import pytest

from due_diligence.reglas import (
    ALTO_RIESGO,
    RECOMENDACIONES,
    consulta_coincide,
    normalizar_recomendacion,
)

COMERCIO = {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS"}
REPRESENTANTE = {"identificador": "PE-0001", "nombre": "Lucía Ferrer Montalvo"}
REPRESENTANTE_SIN_IDENTIFICADOR = {"nombre": "Lucía Ferrer Montalvo"}

# ------------------------------------------------------------------ constantes (FR-008, R10)


def test_las_categorias_de_alto_riesgo_son_una_constante_del_codigo():
    assert ALTO_RIESGO == (
        "apuestas",
        "criptoactivos",
        "suplementos dietarios",
        "venta de medicamentos",
    )


def test_el_conjunto_cerrado_de_recomendaciones():
    assert RECOMENDACIONES == ("habilitar", "no_habilitar", "decide_cumplimiento")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("habilitar", "habilitar"),
        ("Habilitar", "habilitar"),
        (" no habilitar ", "no_habilitar"),
        ("No-Habilitar", "no_habilitar"),
        ("no_habilitar", "no_habilitar"),
        ("DECIDE_CUMPLIMIENTO", "decide_cumplimiento"),
        ("Decide cumplimiento", "decide_cumplimiento"),
        ("aprobar", None),
        ("", None),
        ("   ", None),
        ("habilitar con reservas", None),
        ("no habilitar nunca", None),
        (None, None),
        (3, None),
        (["habilitar"], None),
        ({"valor": "habilitar"}, None),
    ],
)
def test_normalizar_recomendacion(texto, esperado):
    assert normalizar_recomendacion(texto) == esperado


# ------------------------------------------------------------------ consulta_coincide (R7)


@pytest.mark.parametrize(
    ("consulta", "entidad", "tipo", "esperado"),
    [
        # nombre igual, con otras mayúsculas, tildes o puntuación
        ({"tipo": "comercio", "nombre": "Tienda Verde SAS"}, COMERCIO, "comercio", True),
        ({"tipo": "comercio", "nombre": "TIENDA VERDE S.A.S."}, COMERCIO, "comercio", True),
        ({"tipo": "comercio", "nombre": "tienda  verde sas"}, COMERCIO, "comercio", True),
        ({"tipo": "persona", "nombre": "LUCIA FERRER MONTALVO"}, REPRESENTANTE, "persona", True),
        ({"tipo": "persona", "nombre": "lucía ferrer-montalvo"}, REPRESENTANTE, "persona", True),
        # el tipo debe ser el esperado
        ({"tipo": "persona", "nombre": "Tienda Verde SAS"}, COMERCIO, "comercio", False),
        ({"tipo": "comercio", "nombre": "Lucía Ferrer Montalvo"}, REPRESENTANTE, "persona", False),
        ({"tipo": "COMERCIO", "nombre": "Tienda Verde SAS"}, COMERCIO, "comercio", True),
        # identificador
        ({"tipo": "comercio", "identificador": "CO-TV-0001"}, COMERCIO, "comercio", True),
        ({"tipo": "comercio", "identificador": " co-tv-0001 "}, COMERCIO, "comercio", True),
        ({"tipo": "comercio", "identificador": "CO-TV-0009"}, COMERCIO, "comercio", False),
        # trae los dos y uno no coincide
        (
            {"tipo": "comercio", "nombre": "Tienda Verde SAS", "identificador": "CO-TV-0009"},
            COMERCIO,
            "comercio",
            False,
        ),
        (
            {"tipo": "comercio", "nombre": "Otra Tienda SAS", "identificador": "CO-TV-0001"},
            COMERCIO,
            "comercio",
            False,
        ),
        (
            {"tipo": "comercio", "nombre": "Tienda Verde SAS", "identificador": "CO-TV-0001"},
            COMERCIO,
            "comercio",
            True,
        ),
        # sin ninguna clave
        ({"tipo": "comercio"}, COMERCIO, "comercio", False),
        ({"tipo": "comercio", "nombre": None, "identificador": None}, COMERCIO, "comercio", False),
        ({"tipo": "comercio", "nombre": "", "identificador": "  "}, COMERCIO, "comercio", False),
        # un nombre ajeno
        ({"tipo": "comercio", "nombre": "Almacén Mirador SAS"}, COMERCIO, "comercio", False),
        # nombre parcial: no coincide (la pasarela busca por el nombre completo)
        ({"tipo": "comercio", "nombre": "Tienda Verde"}, COMERCIO, "comercio", False),
        # sin tipo
        ({"nombre": "Tienda Verde SAS"}, COMERCIO, "comercio", False),
    ],
)
def test_consulta_coincide(consulta, entidad, tipo, esperado):
    assert consulta_coincide(consulta, entidad, tipo) is esperado


def test_un_identificador_consultado_para_un_representante_sin_identificador_no_coincide():
    # Si el registro devolvió al representante sin identificador, una consulta que trae un
    # identificador no puede verificarse como la misma persona, aunque el nombre coincida (R7).
    consulta = {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo", "identificador": "PE-0001"}
    assert consulta_coincide(consulta, REPRESENTANTE_SIN_IDENTIFICADOR, "persona") is False
    solo_identificador = {"tipo": "persona", "identificador": "PE-0001"}
    assert (
        consulta_coincide(solo_identificador, REPRESENTANTE_SIN_IDENTIFICADOR, "persona") is False
    )
    # También con el identificador vacío o ausente (None) en la entidad.
    con_none = {"nombre": "Lucía Ferrer Montalvo", "identificador": None}
    assert consulta_coincide(solo_identificador, con_none, "persona") is False


def test_un_nombre_para_un_representante_sin_identificador_si_coincide_por_el_nombre():
    consulta = {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo"}
    assert consulta_coincide(consulta, REPRESENTANTE_SIN_IDENTIFICADOR, "persona") is True


def test_un_nombre_para_un_representante_con_identificador_coincide_por_el_nombre():
    consulta = {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo"}
    assert consulta_coincide(consulta, REPRESENTANTE, "persona") is True


def test_una_consulta_con_claves_que_no_son_texto_no_coincide_ni_lanza():
    for malformada in (
        {"tipo": "comercio", "nombre": 3},
        {"tipo": "comercio", "identificador": ["CO-TV-0001"]},
        {"tipo": 7, "nombre": "Tienda Verde SAS"},
    ):
        assert consulta_coincide(malformada, COMERCIO, "comercio") is False
    assert consulta_coincide(None, COMERCIO, "comercio") is False
    assert consulta_coincide("texto", COMERCIO, "comercio") is False
    assert (
        consulta_coincide({"tipo": "comercio", "nombre": "Tienda Verde SAS"}, None, "comercio")
        is False
    )
