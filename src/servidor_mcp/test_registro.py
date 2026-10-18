"""Pruebas de consultar_registro_mercantil (FR-003, FR-004, FR-010, R3, R9)."""

import pytest

from servidor_mcp import datos
from servidor_mcp.registro import consultar_registro_mercantil

RMF = "Registro Mercantil Ficticio del Sur"
RUFE = "Registro Único Ficticio de Empresas"


@pytest.fixture(autouse=True)
def _sin_cache(monkeypatch):
    # Los tests de la caída la ponen ellos mismos; los demás no dependen de la de la sesión.
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)
    datos.limpiar_cache()
    yield
    datos.limpiar_cache()


def _cuerpo(resultado):
    assert resultado.is_error is False
    return resultado.structured_content


def _claves(valor):
    """Todas las claves de un JSON, a cualquier profundidad."""
    if isinstance(valor, dict):
        for clave, v in valor.items():
            yield clave
            yield from _claves(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _claves(v)


def test_por_identificador_devuelve_una_coincidencia_con_un_hecho_por_fuente():
    cuerpo = _cuerpo(consultar_registro_mercantil(identificador="CO-TV-0001"))
    assert cuerpo["resultado"] == "coincidencias"
    assert cuerpo["coincidencias"] == ["CO-TV-0001"]
    assert [h["metadatos"]["fuente"] for h in cuerpo["hechos"]] == [RMF, RUFE]
    contenido = cuerpo["hechos"][0]["contenido"]
    assert contenido["nombre"] == "Tienda Verde SAS"
    assert contenido["estado"] == "activo"
    assert contenido["fecha_constitucion"] == "2019-04-12"
    assert contenido["representante_legal"] == {
        "nombre": "Lucía Ferrer Montalvo",
        "identificador": "PE-0001",
    }


def test_la_fecha_de_nivel_superior_es_la_fecha_de_corte_mas_antigua_de_las_dos_fuentes():
    cuerpo = _cuerpo(consultar_registro_mercantil(identificador="CO-TV-0001"))
    assert cuerpo["metadatos"] == {"fuentes": [RMF, RUFE], "fecha": "2026-09-28"}
    # Cada hecho conserva la fecha de corte de su propia fuente.
    assert [h["metadatos"]["fecha"] for h in cuerpo["hechos"]] == ["2026-09-30", "2026-09-28"]


def test_el_contenido_no_lleva_fuente_ni_fecha():
    cuerpo = _cuerpo(consultar_registro_mercantil(identificador="CO-TV-0001"))
    for h in cuerpo["hechos"]:
        assert "fuente" not in h["contenido"]
        assert "fecha" not in h["contenido"]


def test_nombre_ambiguo_devuelve_las_dos_coincidencias_y_cuatro_hechos():
    cuerpo = _cuerpo(consultar_registro_mercantil(nombre="almacen mirador"))
    assert cuerpo["resultado"] == "coincidencias"
    assert cuerpo["coincidencias"] == ["CO-AM-0004", "CO-AM-0005"]
    # Uno por comercio y fuente, en orden de identificador y luego de fuente.
    assert [
        (h["contenido"]["identificador"], h["metadatos"]["fuente"]) for h in cuerpo["hechos"]
    ] == [
        ("CO-AM-0004", RMF),
        ("CO-AM-0004", RUFE),
        ("CO-AM-0005", RMF),
        ("CO-AM-0005", RUFE),
    ]


def test_nada_sugiere_que_se_haya_elegido_una_coincidencia():
    cuerpo = _cuerpo(consultar_registro_mercantil(nombre="almacen mirador"))
    prohibidas = {"elegida", "elegido", "seleccionada", "recomendada", "principal", "preferida"}
    assert not prohibidas & set(_claves(cuerpo))


def test_un_nombre_mas_especifico_devuelve_solo_su_comercio():
    cuerpo = _cuerpo(consultar_registro_mercantil(nombre="ALMACÉN MIRADOR NORTE"))
    assert cuerpo["coincidencias"] == ["CO-AM-0005"]


def test_sas_con_y_sin_puntos_es_el_mismo_nombre():
    con_puntos = _cuerpo(consultar_registro_mercantil(nombre="Tienda Verde S.A.S."))
    sin_puntos = _cuerpo(consultar_registro_mercantil(nombre="tienda verde sas"))
    assert con_puntos["coincidencias"] == sin_puntos["coincidencias"] == ["CO-TV-0001"]


def test_dos_fuentes_con_fechas_de_constitucion_distintas_devuelven_ambas_con_su_fuente():
    cuerpo = _cuerpo(consultar_registro_mercantil(identificador="CO-RF-0006"))
    assert cuerpo["coincidencias"] == ["CO-RF-0006"]
    assert len(cuerpo["hechos"]) == 2
    por_fuente = {
        h["metadatos"]["fuente"]: h["contenido"]["fecha_constitucion"] for h in cuerpo["hechos"]
    }
    assert por_fuente == {RMF: "2016-03-14", RUFE: "2017-09-02"}


def test_un_nombre_inexistente_es_sin_coincidencias_y_no_es_un_error():
    resultado = consultar_registro_mercantil(nombre="Comercio Que No Existe")
    cuerpo = _cuerpo(resultado)
    assert cuerpo["resultado"] == "sin_coincidencias"
    assert cuerpo["coincidencias"] == []
    assert cuerpo["hechos"] == []
    assert cuerpo["metadatos"] == {"fuentes": [RMF, RUFE], "fecha": "2026-09-28"}


@pytest.mark.parametrize("identificador", ["X1", "ZZ", "CO-ZZ-9999", "co-tv-0001x"])
def test_un_identificador_desconocido_aunque_sea_corto_es_sin_coincidencias(identificador):
    cuerpo = _cuerpo(consultar_registro_mercantil(identificador=identificador))
    assert cuerpo["resultado"] == "sin_coincidencias"
    assert cuerpo["coincidencias"] == []
    assert cuerpo["metadatos"]["fecha"] == "2026-09-28"


def test_el_identificador_es_exacto_y_no_parcial():
    cuerpo = _cuerpo(consultar_registro_mercantil(identificador="CO-TV"))
    assert cuerpo["resultado"] == "sin_coincidencias"


@pytest.mark.parametrize(
    "argumentos",
    [
        {"nombre": "Tienda Verde", "identificador": "CO-TV-0001"},
        {},
        {"nombre": ""},
        {"nombre": "   "},
        {"nombre": "ab"},
        {"nombre": " a. "},
        {"nombre": 5},
        {"nombre": ["Tienda Verde"]},
        {"identificador": 5},
    ],
)
def test_entradas_invalidas_dan_entrada_invalida_no_reintentable(argumentos):
    resultado = consultar_registro_mercantil(**argumentos)
    assert resultado.is_error is True
    cuerpo = resultado.structured_content
    assert cuerpo["tipo"] == "entrada_invalida"
    assert cuerpo["reintentable"] is False
    assert cuerpo["obtenido"] == {}


def test_el_minimo_de_tres_caracteres_es_solo_para_el_nombre():
    assert consultar_registro_mercantil(nombre="abc").is_error is False
    assert consultar_registro_mercantil(nombre="sas").is_error is True  # solo la forma jurídica
    assert consultar_registro_mercantil(identificador="X1").is_error is False


def test_un_archivo_de_datos_ausente_da_datos_no_disponibles(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "DIRECTORIO_DATOS", tmp_path)
    resultado = consultar_registro_mercantil(identificador="CO-TV-0001")
    assert resultado.is_error is True
    cuerpo = resultado.structured_content
    assert cuerpo["tipo"] == "datos_no_disponibles"
    assert cuerpo["reintentable"] is False
    assert "hechos" not in cuerpo  # nada parcial presentado como completo


def test_nunca_lanza_con_un_archivo_corrupto(tmp_path, monkeypatch):
    (tmp_path / "registro_rmf_sur.json").write_text("{ roto", encoding="utf-8")
    monkeypatch.setattr(datos, "DIRECTORIO_DATOS", tmp_path)
    resultado = consultar_registro_mercantil(nombre="Tienda Verde")
    assert resultado.structured_content["tipo"] == "datos_no_disponibles"


@pytest.mark.parametrize(
    "nombre",
    ["Almacén Mirador SAS", "Almacén Mirador S.A.S.", "ALMACEN MIRADOR sas", "almacen mirador"],
)
def test_el_mensaje_natural_con_forma_juridica_devuelve_las_dos_coincidencias(nombre):
    cuerpo = _cuerpo(consultar_registro_mercantil(nombre=nombre))
    assert cuerpo["coincidencias"] == ["CO-AM-0004", "CO-AM-0005"]
    assert len(cuerpo["hechos"]) == 4


def test_una_forma_juridica_distinta_a_la_del_comercio_tambien_coincide():
    cuerpo = _cuerpo(consultar_registro_mercantil(nombre="Ferretería Río Fino Ltda."))
    assert cuerpo["coincidencias"] == ["CO-RF-0006"]


def test_con_forma_juridica_el_nombre_mas_especifico_sigue_acotando():
    cuerpo = _cuerpo(consultar_registro_mercantil(nombre="Almacén Mirador Norte SAS"))
    assert cuerpo["coincidencias"] == ["CO-AM-0005"]


@pytest.mark.parametrize("solo", ["SAS", "S.A.S.", "sa", "Ltda.", "S. en C.", "ab SAS"])
def test_solo_la_forma_juridica_da_entrada_invalida(solo):
    resultado = consultar_registro_mercantil(nombre=solo)
    assert resultado.is_error is True
    cuerpo = resultado.structured_content
    assert cuerpo["tipo"] == "entrada_invalida"
    assert cuerpo["reintentable"] is False


@pytest.mark.parametrize("identificador", ["co-tv-0001", "Co-Tv-0001", " CO-TV-0001 "])
def test_el_identificador_no_distingue_mayusculas(identificador):
    cuerpo = _cuerpo(consultar_registro_mercantil(identificador=identificador))
    assert cuerpo["coincidencias"] == ["CO-TV-0001"]


@pytest.mark.parametrize("corto", ["SAS", "S.A.S.", "ab", "ab SAS", "Ltda."])
def test_el_mensaje_de_nombre_demasiado_corto_explica_como_se_cuenta_el_minimo(corto):
    cuerpo = consultar_registro_mercantil(nombre=corto).structured_content
    assert cuerpo["tipo"] == "entrada_invalida"
    mensaje = cuerpo["mensaje"]
    assert "3 caracteres" in mensaje
    # El mínimo se cuenta sin la forma jurídica final: el mensaje lo dice y nombra las formas.
    assert "forma jurídica" in mensaje
    assert "SAS" in mensaje and "Ltda" in mensaje
    # El texto es fijo: no repite lo que escribió quien consulta.
    otro = consultar_registro_mercantil(nombre="xy").structured_content["mensaje"]
    assert mensaje == otro


# --- caída simulada del registro (#9, R11) ---------------------------------------------------

VARIABLE_FALLA = "PASARELA_FALLA_REGISTRO"


def test_con_la_variable_el_registro_no_esta_disponible_y_es_reintentable(monkeypatch):
    monkeypatch.setenv(VARIABLE_FALLA, "1")
    resultado = consultar_registro_mercantil(identificador="CO-TA-0002")
    assert resultado.is_error is True
    cuerpo = resultado.structured_content
    assert cuerpo["tipo"] == "servicio_no_disponible"
    assert cuerpo["reintentable"] is True
    assert cuerpo["mensaje"] == (
        "El registro mercantil no está disponible. Se puede reintentar; mientras tanto, el "
        "comercio no queda identificado."
    )


def test_la_variable_del_registro_se_lee_en_cada_llamada(monkeypatch):
    monkeypatch.setenv(VARIABLE_FALLA, "1")
    assert consultar_registro_mercantil(identificador="CO-TA-0002").is_error is True
    monkeypatch.setenv(VARIABLE_FALLA, "0")
    assert consultar_registro_mercantil(identificador="CO-TA-0002").is_error is False
    monkeypatch.setenv(VARIABLE_FALLA, "1")
    assert consultar_registro_mercantil(identificador="CO-TA-0002").is_error is True


def test_una_entrada_invalida_se_rechaza_antes_que_la_caida(monkeypatch):
    monkeypatch.setenv(VARIABLE_FALLA, "1")
    cuerpo = consultar_registro_mercantil().structured_content
    assert cuerpo["tipo"] == "entrada_invalida"
    cuerpo = consultar_registro_mercantil(nombre="SAS").structured_content
    assert cuerpo["tipo"] == "entrada_invalida"


def test_sin_la_variable_el_registro_responde_igual(monkeypatch):
    monkeypatch.delenv(VARIABLE_FALLA, raising=False)
    cuerpo = _cuerpo(consultar_registro_mercantil(identificador="CO-RF-0006"))
    assert cuerpo["coincidencias"] == ["CO-RF-0006"]
