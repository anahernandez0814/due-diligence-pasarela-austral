"""Pruebas de consultar_listas_restrictivas (FR-005, R3)."""

import pytest

from servidor_mcp import datos
from servidor_mcp.listas import consultar_listas_restrictivas

AUTORIDAD_A = "Autoridad Ficticia de Control A"
AUTORIDAD_B = "Autoridad Ficticia de Control B"
FECHA_MAS_ANTIGUA = "2026-09-20"  # fecha_corte de la Lista Restrictiva Ficticia B


@pytest.fixture(autouse=True)
def _sin_cache():
    datos.limpiar_cache()
    yield
    datos.limpiar_cache()


def _cuerpo(resultado):
    assert resultado.is_error is False
    return resultado.structured_content


def test_una_persona_coincide_por_identificador():
    cuerpo = _cuerpo(consultar_listas_restrictivas(tipo="persona", identificador="PE-0003"))
    assert cuerpo["resultado"] == "coincidencias"
    assert len(cuerpo["hechos"]) == 1
    hecho = cuerpo["hechos"][0]
    assert hecho["contenido"] == {
        "lista": "Lista Restrictiva Ficticia A",
        "tipo": "persona",
        "nombre": "Ernesto Calderón Ibarra",
        "identificador": "PE-0003",
    }
    assert hecho["metadatos"] == {"fuente": AUTORIDAD_A, "fecha": "2026-09-25"}


def test_una_persona_coincide_por_nombre_completo_en_otras_mayusculas_y_sin_tildes():
    cuerpo = _cuerpo(
        consultar_listas_restrictivas(tipo="persona", nombre="ERNESTO CALDERON IBARRA")
    )
    assert cuerpo["resultado"] == "coincidencias"
    assert cuerpo["hechos"][0]["contenido"]["identificador"] == "PE-0003"


def test_un_comercio_de_las_listas_coincide():
    cuerpo = _cuerpo(
        consultar_listas_restrictivas(tipo="comercio", nombre="Importadora Sombra S.A.S.")
    )
    assert cuerpo["resultado"] == "coincidencias"
    assert cuerpo["hechos"][0]["contenido"]["identificador"] == "CO-IS-0090"


def test_un_nombre_parcial_no_coincide():
    for parcial in ("Ernesto Calderón", "Calderón Ibarra", "Ernesto", "Ernesto Calderón Ibarra Jr"):
        cuerpo = _cuerpo(consultar_listas_restrictivas(tipo="persona", nombre=parcial))
        assert cuerpo["resultado"] == "sin_coincidencias", parcial


def test_un_identificador_parcial_no_coincide():
    cuerpo = _cuerpo(consultar_listas_restrictivas(tipo="persona", identificador="PE-000"))
    assert cuerpo["resultado"] == "sin_coincidencias"


def test_el_mismo_nombre_con_otro_tipo_no_coincide():
    cuerpo = _cuerpo(
        consultar_listas_restrictivas(tipo="comercio", nombre="Ernesto Calderón Ibarra")
    )
    assert cuerpo["resultado"] == "sin_coincidencias"
    cuerpo = _cuerpo(consultar_listas_restrictivas(tipo="comercio", identificador="PE-0003"))
    assert cuerpo["resultado"] == "sin_coincidencias"


@pytest.mark.parametrize("identificador", ["CO-TV-0001", "CO-TA-0002"])
def test_comercios_sin_hallazgos_dan_sin_coincidencias_con_metadatos_de_todas_las_listas(
    identificador,
):
    cuerpo = _cuerpo(consultar_listas_restrictivas(tipo="comercio", identificador=identificador))
    assert cuerpo["resultado"] == "sin_coincidencias"
    assert cuerpo["hechos"] == []
    assert cuerpo["metadatos"] == {
        "fuentes": [AUTORIDAD_A, AUTORIDAD_B],
        "fecha": FECHA_MAS_ANTIGUA,
    }


def test_el_representante_de_un_comercio_en_listas_no_arrastra_al_comercio():
    # Caso (c): la persona figura; el comercio por sí solo, no.
    persona = _cuerpo(consultar_listas_restrictivas(tipo="persona", identificador="PE-0003"))
    comercio = _cuerpo(consultar_listas_restrictivas(tipo="comercio", identificador="CO-PL-0003"))
    assert persona["resultado"] == "coincidencias"
    assert comercio["resultado"] == "sin_coincidencias"


def test_la_fecha_de_nivel_superior_es_la_mas_antigua_y_cada_hecho_conserva_la_suya():
    cuerpo = _cuerpo(consultar_listas_restrictivas(tipo="persona", identificador="PE-0003"))
    assert cuerpo["metadatos"]["fecha"] == FECHA_MAS_ANTIGUA
    assert cuerpo["hechos"][0]["metadatos"]["fecha"] == "2026-09-25"
    # Una coincidencia de la otra lista conserva la fecha de esa lista.
    otra = _cuerpo(consultar_listas_restrictivas(tipo="persona", identificador="PE-0091"))
    assert otra["hechos"][0]["metadatos"] == {"fuente": AUTORIDAD_B, "fecha": FECHA_MAS_ANTIGUA}
    assert otra["metadatos"]["fecha"] == FECHA_MAS_ANTIGUA


def test_el_tipo_se_acepta_sin_distinguir_mayusculas():
    cuerpo = _cuerpo(consultar_listas_restrictivas(tipo=" Persona ", identificador="PE-0003"))
    assert cuerpo["resultado"] == "coincidencias"


@pytest.mark.parametrize(
    "argumentos",
    [
        {"nombre": "Ernesto Calderón Ibarra"},  # tipo ausente
        {"tipo": "organizacion", "nombre": "Ernesto Calderón Ibarra"},
        {"tipo": "", "nombre": "Ernesto Calderón Ibarra"},
        {"tipo": 5, "nombre": "Ernesto Calderón Ibarra"},
        {"tipo": "persona"},  # ni nombre ni identificador
        {"tipo": "persona", "nombre": "Ernesto Calderón Ibarra", "identificador": "PE-0003"},
        {"tipo": "persona", "nombre": 5},
    ],
)
def test_entradas_invalidas_dan_entrada_invalida(argumentos):
    resultado = consultar_listas_restrictivas(**argumentos)
    assert resultado.is_error is True
    cuerpo = resultado.structured_content
    assert cuerpo["tipo"] == "entrada_invalida"
    assert cuerpo["reintentable"] is False


def test_un_archivo_de_datos_ausente_da_datos_no_disponibles(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "DIRECTORIO_DATOS", tmp_path)
    resultado = consultar_listas_restrictivas(tipo="persona", identificador="PE-0003")
    assert resultado.is_error is True
    assert resultado.structured_content["tipo"] == "datos_no_disponibles"
    assert resultado.structured_content["reintentable"] is False


@pytest.mark.parametrize("identificador", ["pe-0003", "Pe-0003"])
def test_el_identificador_no_distingue_mayusculas(identificador):
    cuerpo = _cuerpo(consultar_listas_restrictivas(tipo="persona", identificador=identificador))
    assert cuerpo["resultado"] == "coincidencias"


def test_en_listas_el_nombre_es_completo_con_su_forma_juridica():
    con = _cuerpo(
        consultar_listas_restrictivas(tipo="comercio", nombre="Importadora Sombra S.A.S.")
    )
    sin = _cuerpo(consultar_listas_restrictivas(tipo="comercio", nombre="Importadora Sombra"))
    assert con["resultado"] == "coincidencias"
    assert sin["resultado"] == "sin_coincidencias"
