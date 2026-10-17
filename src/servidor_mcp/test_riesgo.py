"""Pruebas de consultar_riesgo_categoria (FR-007, R4)."""

import pytest

from servidor_mcp import datos
from servidor_mcp.riesgo import categorias_conocidas, consultar_riesgo_categoria

ALTO_RIESGO = ["apuestas", "criptoactivos", "suplementos dietarios", "venta de medicamentos"]
FUENTE = "Catálogo Ficticio de Categorías de Riesgo"


@pytest.fixture(autouse=True)
def _sin_cache():
    datos.limpiar_cache()
    yield
    datos.limpiar_cache()


def _cuerpo(resultado):
    assert resultado.is_error is False
    return resultado.structured_content


def _claves(valor):
    if isinstance(valor, dict):
        for clave, v in valor.items():
            yield clave
            yield from _claves(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _claves(v)


def _nivel(categoria):
    return _cuerpo(consultar_riesgo_categoria(categoria=categoria))["hechos"][0]["contenido"][
        "nivel"
    ]


@pytest.mark.parametrize("categoria", ALTO_RIESGO)
def test_las_cuatro_categorias_del_enunciado_son_de_nivel_alto(categoria):
    assert _nivel(categoria) == "alto"


def test_ninguna_otra_categoria_conocida_es_alta():
    otras = [c for c in categorias_conocidas() if c not in ALTO_RIESGO]
    assert len(otras) == 6
    assert {_nivel(c) for c in otras} == {"medio", "bajo"}


def test_el_nivel_alto_es_exactamente_el_de_las_cuatro_categorias():
    altas = [c for c in categorias_conocidas() if _nivel(c) == "alto"]
    assert sorted(altas) == sorted(ALTO_RIESGO)


@pytest.mark.parametrize(
    "escrita",
    [
        "Suplementos Dietarios",
        "suplementos  dietarios",
        "  SUPLEMENTOS DIETARIOS  ",
        "suplementos-dietarios",
    ],
)
def test_la_comparacion_es_normalizada(escrita):
    contenido = _cuerpo(consultar_riesgo_categoria(categoria=escrita))["hechos"][0]["contenido"]
    assert contenido == {"categoria": "suplementos dietarios", "nivel": "alto"}


def test_la_comparacion_ignora_tildes():
    contenido = _cuerpo(consultar_riesgo_categoria(categoria="Educacion en linea"))["hechos"][0][
        "contenido"
    ]
    assert contenido == {"categoria": "educación en línea", "nivel": "bajo"}


def test_una_categoria_conocida_lleva_fuente_y_fecha_de_corte():
    cuerpo = _cuerpo(consultar_riesgo_categoria(categoria="apuestas"))
    assert cuerpo["resultado"] == "categoria_conocida"
    assert cuerpo["hechos"][0]["metadatos"] == {"fuente": FUENTE, "fecha": "2026-09-30"}
    assert cuerpo["metadatos"] == {"fuentes": [FUENTE], "fecha": "2026-09-30"}


def test_una_categoria_desconocida_no_inventa_un_nivel():
    cuerpo = _cuerpo(consultar_riesgo_categoria(categoria="Venta de globos"))
    assert cuerpo["resultado"] == "categoria_desconocida"
    assert len(cuerpo["hechos"]) == 1
    contenido = cuerpo["hechos"][0]["contenido"]
    assert contenido == {
        "categoria": "Venta de globos",
        "categorias_conocidas": categorias_conocidas(),
    }
    assert "nivel" not in set(_claves(cuerpo))
    assert cuerpo["hechos"][0]["metadatos"] == {"fuente": FUENTE, "fecha": "2026-09-30"}
    assert cuerpo["metadatos"] == {"fuentes": [FUENTE], "fecha": "2026-09-30"}


def test_las_categorias_conocidas_son_las_diez_del_catalogo_en_orden():
    conocidas = categorias_conocidas()
    assert len(conocidas) == 10
    assert conocidas[:4] == ALTO_RIESGO
    assert "educación en línea" in conocidas


@pytest.mark.parametrize("categoria", [None, "", "   ", 5, ["apuestas"], {"a": 1}])
def test_vacia_o_de_tipo_incorrecto_da_entrada_invalida(categoria):
    resultado = consultar_riesgo_categoria(categoria=categoria)
    assert resultado.is_error is True
    cuerpo = resultado.structured_content
    assert cuerpo["tipo"] == "entrada_invalida"
    assert cuerpo["reintentable"] is False


def test_sin_argumentos_da_entrada_invalida():
    assert consultar_riesgo_categoria().structured_content["tipo"] == "entrada_invalida"


def test_un_archivo_de_datos_ausente_da_datos_no_disponibles(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "DIRECTORIO_DATOS", tmp_path)
    cuerpo = consultar_riesgo_categoria(categoria="apuestas").structured_content
    assert cuerpo["tipo"] == "datos_no_disponibles"
    assert cuerpo["reintentable"] is False
    with pytest.raises(datos.DatosNoDisponibles):
        categorias_conocidas()
