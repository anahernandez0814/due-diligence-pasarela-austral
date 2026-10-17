"""Pruebas de la forma de las respuestas y de los errores estructurados (R2, R9)."""

import json

import pytest

from servidor_mcp.respuestas import TIPOS_ERROR, error, hecho, respuesta

FUENTE = "Fuente Ficticia"
FECHA = "2026-09-30"


def _texto(resultado):
    return json.loads(resultado.content[0].text)


def test_respuesta_de_exito_tiene_la_forma_comun():
    h = hecho({"id": "X-1"}, FUENTE, FECHA)
    r = respuesta("coincidencias", [h], [FUENTE], FECHA)
    assert r.is_error is False
    assert r.structured_content == {
        "resultado": "coincidencias",
        "hechos": [{"contenido": {"id": "X-1"}, "metadatos": {"fuente": FUENTE, "fecha": FECHA}}],
        "metadatos": {"fuentes": [FUENTE], "fecha": FECHA},
    }


def test_el_texto_es_el_mismo_json_que_el_contenido_estructurado():
    r = respuesta("sin_coincidencias", [], [FUENTE], FECHA)
    assert _texto(r) == r.structured_content


def test_sin_coincidencias_tiene_hechos_vacios_y_metadatos():
    r = respuesta("sin_coincidencias", [], [FUENTE], FECHA)
    assert r.structured_content["hechos"] == []
    assert r.structured_content["metadatos"] == {"fuentes": [FUENTE], "fecha": FECHA}


def test_coincidencias_solo_aparece_si_se_pasa():
    sin = respuesta("coincidencias", [], [FUENTE], FECHA)
    con = respuesta("coincidencias", [], [FUENTE], FECHA, coincidencias=["CO-AA-0001"])
    assert "coincidencias" not in sin.structured_content
    assert con.structured_content["coincidencias"] == ["CO-AA-0001"]


def test_coincidencias_vacia_se_conserva_cuando_se_pasa():
    r = respuesta("sin_coincidencias", [], [FUENTE], FECHA, coincidencias=[])
    assert r.structured_content["coincidencias"] == []


def test_la_fecha_de_un_hecho_puede_ser_distinta_de_la_de_los_metadatos():
    h = hecho({"titular": "Titular ficticio"}, FUENTE, "2026-05-01")
    r = respuesta("coincidencias", [h], [FUENTE], FECHA)
    assert r.structured_content["hechos"][0]["metadatos"]["fecha"] == "2026-05-01"
    assert r.structured_content["metadatos"]["fecha"] == FECHA


def test_ninguna_respuesta_de_exito_lleva_contenido_fuera_de_un_hecho():
    r = respuesta("coincidencias", [hecho({"id": "X-1"}, FUENTE, FECHA)], [FUENTE], FECHA)
    assert "contenido" not in r.structured_content
    assert "contenido" not in r.structured_content["metadatos"]


@pytest.mark.parametrize("clave", ["fuente", "fecha"])
def test_el_contenido_de_un_hecho_no_lleva_fuente_ni_fecha(clave):
    with pytest.raises(ValueError):
        hecho({clave: "x"}, FUENTE, FECHA)


def test_las_tildes_no_salen_escapadas():
    r = respuesta("coincidencias", [hecho({"nombre": "Almacén"}, FUENTE, FECHA)], [FUENTE], FECHA)
    assert "Almacén" in r.content[0].text
    assert "\\u00e9" not in r.content[0].text


def test_error_tiene_la_forma_estructurada():
    e = error("entrada_invalida", "Falta el nombre.", False)
    assert e.is_error is True
    assert e.structured_content == {
        "error": True,
        "tipo": "entrada_invalida",
        "mensaje": "Falta el nombre.",
        "reintentable": False,
        "obtenido": {},
    }
    assert _texto(e) == e.structured_content


def test_error_conserva_lo_obtenido():
    e = error("datos_no_disponibles", "Archivo ausente.", False, obtenido={"parcial": []})
    assert e.structured_content["obtenido"] == {"parcial": []}


def test_campos_faltantes_solo_si_se_pasa():
    sin = error("entrada_invalida", "x", False)
    con = error(
        "campos_obligatorios_ausentes", "Faltan campos.", False, campos_faltantes=["a", "b"]
    )
    assert "campos_faltantes" not in sin.structured_content
    assert con.structured_content["campos_faltantes"] == ["a", "b"]


def test_los_tipos_de_error_son_los_del_modelo_de_datos():
    assert set(TIPOS_ERROR) == {
        "entrada_invalida",
        "campos_obligatorios_ausentes",
        "servicio_no_disponible",
        "datos_no_disponibles",
        "error_de_almacenamiento",
        "error_interno",
    }


def test_solo_servicio_no_disponible_es_reintentable():
    for tipo in TIPOS_ERROR:
        esperado = tipo == "servicio_no_disponible"
        e = error(tipo, "mensaje", esperado)
        assert e.structured_content["reintentable"] is esperado
        with pytest.raises(ValueError):
            error(tipo, "mensaje", not esperado)


def test_un_tipo_de_error_desconocido_se_rechaza():
    with pytest.raises(ValueError):
        error("inventado", "mensaje", False)
