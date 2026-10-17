"""Pruebas de buscar_noticias (FR-006, FR-012, R5)."""

import pytest

from servidor_mcp import datos
from servidor_mcp.listas import consultar_listas_restrictivas
from servidor_mcp.noticias import buscar_noticias

DIARIO = "Diario Ficticio del Sur"
VARIABLE = "PASARELA_FALLA_NOTICIAS"


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    monkeypatch.delenv(VARIABLE, raising=False)
    datos.limpiar_cache()
    yield
    datos.limpiar_cache()


def _cuerpo(resultado):
    assert resultado.is_error is False
    return resultado.structured_content


def test_un_comercio_con_menciones_devuelve_la_noticia_con_titular_url_y_fuente():
    cuerpo = _cuerpo(buscar_noticias(identificador="CO-AM-0005"))
    assert cuerpo["resultado"] == "coincidencias"
    assert len(cuerpo["hechos"]) == 1
    h = cuerpo["hechos"][0]
    assert h["contenido"] == {
        "id": "N-0001",
        "titular": "Almacén Mirador Norte inaugura una sucursal en la zona industrial",
        "url": "https://diario.example/noticias/n-0001",
    }
    assert h["metadatos"]["fuente"] == DIARIO


def test_la_fecha_del_hecho_es_la_de_la_noticia_y_la_de_nivel_superior_la_fecha_de_corte():
    cuerpo = _cuerpo(buscar_noticias(identificador="CO-AM-0005"))
    assert cuerpo["hechos"][0]["metadatos"]["fecha"] == "2026-03-18"
    assert cuerpo["metadatos"] == {"fuentes": [DIARIO], "fecha": "2026-09-30"}


def test_busca_por_nombre_completo_normalizado_y_no_por_nombre_parcial():
    completo = _cuerpo(buscar_noticias(nombre="ALMACÉN MIRADOR NORTE S.A.S."))
    parcial = _cuerpo(buscar_noticias(nombre="Almacén Mirador"))
    assert completo["resultado"] == "coincidencias"
    assert parcial["resultado"] == "sin_coincidencias"


def test_una_persona_mencionada_aparece():
    cuerpo = _cuerpo(buscar_noticias(identificador="PE-0004"))
    assert [h["contenido"]["id"] for h in cuerpo["hechos"]] == ["N-0003"]


def test_sin_menciones_da_sin_coincidencias_con_metadatos():
    cuerpo = _cuerpo(buscar_noticias(identificador="CO-TV-0001"))
    assert cuerpo["resultado"] == "sin_coincidencias"
    assert cuerpo["hechos"] == []
    assert cuerpo["metadatos"] == {"fuentes": [DIARIO], "fecha": "2026-09-30"}


def test_aparece_en_noticias_y_no_en_listas():
    # US2, escenario 3: una mención en noticias no es una coincidencia en listas.
    noticias = _cuerpo(buscar_noticias(identificador="CO-AM-0005"))
    listas = _cuerpo(consultar_listas_restrictivas(tipo="comercio", identificador="CO-AM-0005"))
    assert noticias["resultado"] == "coincidencias"
    assert listas["resultado"] == "sin_coincidencias"


def test_con_la_variable_en_uno_el_servicio_no_esta_disponible_y_es_reintentable(monkeypatch):
    monkeypatch.setenv(VARIABLE, "1")
    resultado = buscar_noticias(identificador="CO-AM-0005")
    assert resultado.is_error is True
    cuerpo = resultado.structured_content
    assert cuerpo["tipo"] == "servicio_no_disponible"
    assert cuerpo["reintentable"] is True
    assert cuerpo["obtenido"] == {}
    assert "noticias" in cuerpo["mensaje"].lower()


@pytest.mark.parametrize("valor", ["0", "", "true", "11", " 1", "si"])
def test_con_cualquier_valor_distinto_de_uno_el_servicio_funciona(monkeypatch, valor):
    monkeypatch.setenv(VARIABLE, valor)
    assert buscar_noticias(identificador="CO-AM-0005").is_error is False


def test_la_variable_se_lee_en_cada_llamada_en_la_misma_instancia(monkeypatch):
    assert buscar_noticias(identificador="CO-AM-0005").is_error is False
    monkeypatch.setenv(VARIABLE, "1")
    assert buscar_noticias(identificador="CO-AM-0005").is_error is True
    monkeypatch.setenv(VARIABLE, "0")
    assert buscar_noticias(identificador="CO-AM-0005").is_error is False
    monkeypatch.delenv(VARIABLE)
    assert buscar_noticias(identificador="CO-AM-0005").is_error is False


def test_la_caida_no_afecta_a_las_listas(monkeypatch):
    monkeypatch.setenv(VARIABLE, "1")
    assert consultar_listas_restrictivas(tipo="persona", identificador="PE-0003").is_error is False


def test_una_entrada_invalida_se_informa_aunque_el_servicio_este_caido(monkeypatch):
    monkeypatch.setenv(VARIABLE, "1")
    cuerpo = buscar_noticias().structured_content
    assert cuerpo["tipo"] == "entrada_invalida"


@pytest.mark.parametrize(
    "argumentos",
    [{}, {"nombre": ""}, {"nombre": 5}, {"identificador": ["CO-AM-0005"]}]
    + [{"nombre": "Almacén Mirador Norte SAS", "identificador": "CO-AM-0005"}],
)
def test_entradas_invalidas(argumentos):
    resultado = buscar_noticias(**argumentos)
    assert resultado.is_error is True
    assert resultado.structured_content["tipo"] == "entrada_invalida"
    assert resultado.structured_content["reintentable"] is False


def test_un_archivo_de_datos_ausente_da_datos_no_disponibles(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "DIRECTORIO_DATOS", tmp_path)
    cuerpo = buscar_noticias(identificador="CO-AM-0005").structured_content
    assert cuerpo["tipo"] == "datos_no_disponibles"
    assert cuerpo["reintentable"] is False
