"""Pruebas del esquema del informe (#9, R2, data-model «Afirmación» e «Informe»).

`validar_informe` es pura: devuelve todos los problemas de forma, con su ruta, y nunca repite el
valor recibido. Todos los datos son ficticios.
"""

import copy

import pytest

from servidor_mcp.informe import FRENTES_INFORME, Problema, validar_informe

SUR = "Registro Mercantil Ficticio del Sur"
RUFE = "Registro Único Ficticio de Empresas"
VALOR_FICTICIO = "VALOR-QUE-NO-DEBE-REPETIRSE"


def _informe():
    """El informe del contrato `registrar-informe.md`, con `CO-RF-0006` (caso g)."""
    return {
        "comercio": {
            "identificador": "CO-RF-0006",
            "nombre": "Ferretería Río Fino SAS",
            "verificado": True,
        },
        "hallazgos": {
            "registro": [
                {"texto": "El comercio figura activo.", "fuente": SUR, "fecha": "2026-09-30"}
            ],
            "listas": [
                {
                    "texto": "Sin coincidencias del comercio.",
                    "fuente": "Lista Ficticia de Sanciones",
                    "fecha": "2026-09-15",
                }
            ],
        },
        "conflictos": {
            "resumen": "1 conflicto entre las fuentes registrales.",
            "lista": [
                {
                    "dato": "fecha_constitucion",
                    "valores": [
                        {"valor": "2016-03-14", "fuente": SUR, "fecha": "2026-09-30"},
                        {"valor": "2017-09-02", "fuente": RUFE, "fecha": "2026-09-28"},
                    ],
                }
            ],
        },
        "cobertura": ["Cobertura completa: 4 de 4 frentes cubiertos.", "registro: cubierto."],
        "recomendacion": "no_habilitar",
    }


def _rutas(problemas):
    return [p.ruta for p in problemas]


def test_un_informe_valido_no_tiene_problemas():
    assert validar_informe(_informe()) == []


def test_los_frentes_del_informe_son_los_cuatro():
    assert FRENTES_INFORME == ("registro", "listas", "noticias", "categoria")


def test_un_problema_se_convierte_en_un_diccionario_con_ruta_y_texto():
    assert Problema("comercio", "Falta el campo.").como_dict() == {
        "ruta": "comercio",
        "texto": "Falta el campo.",
    }


def test_una_entrada_que_no_es_un_objeto_es_un_problema():
    (problema,) = validar_informe("texto")
    assert problema.ruta == ""


def test_faltan_las_cinco_partes_y_se_nombran_todas():
    problemas = validar_informe({})
    assert _rutas(problemas) == [
        "comercio",
        "recomendacion",
        "hallazgos",
        "cobertura",
        "conflictos",
    ]


# --- afirmaciones ----------------------------------------------------------------------------


@pytest.mark.parametrize("campo", ["texto", "fuente", "fecha"])
def test_una_afirmacion_sin_un_campo_obligatorio_es_un_problema(campo):
    informe = _informe()
    del informe["hallazgos"]["registro"][0][campo]
    assert _rutas(validar_informe(informe)) == [f"hallazgos.registro[0].{campo}"]


@pytest.mark.parametrize("vacio", ["", "   ", None, 5])
def test_texto_y_fuente_deben_ser_texto_no_vacio(vacio):
    informe = _informe()
    informe["hallazgos"]["listas"][0]["texto"] = vacio
    informe["hallazgos"]["listas"][0]["fuente"] = vacio
    assert _rutas(validar_informe(informe)) == [
        "hallazgos.listas[0].texto",
        "hallazgos.listas[0].fuente",
    ]


@pytest.mark.parametrize("fecha", ["2026-02-30", "30/09/2026", "", None, "2026-9-30", 20260930])
def test_la_fecha_debe_ser_aaaa_mm_dd_y_real(fecha):
    informe = _informe()
    informe["hallazgos"]["registro"][0]["fecha"] = fecha
    (problema,) = validar_informe(informe)
    assert problema.ruta == "hallazgos.registro[0].fecha"
    assert "AAAA-MM-DD" in problema.texto


def test_un_campo_de_mas_en_la_afirmacion_es_un_campo_desconocido_sin_repetirlo():
    informe = _informe()
    informe["hallazgos"]["registro"][0][VALOR_FICTICIO] = "x"
    (problema,) = validar_informe(informe)
    assert problema.ruta == "hallazgos.registro[0]"
    assert "desconocido" in problema.texto
    assert VALOR_FICTICIO not in problema.ruta + problema.texto


def test_una_afirmacion_que_no_es_un_objeto_es_un_problema():
    informe = _informe()
    informe["hallazgos"]["registro"] = ["El comercio figura activo."]
    assert _rutas(validar_informe(informe)) == ["hallazgos.registro[0]"]


def test_se_devuelven_todos_los_problemas_y_no_solo_el_primero():
    informe = _informe()
    del informe["hallazgos"]["registro"][0]["fuente"]
    informe["hallazgos"]["listas"][0]["fecha"] = "2026-13-01"
    informe["hallazgos"]["noticias"] = [{"texto": " ", "fuente": "Diario Ficticio"}]
    assert _rutas(validar_informe(informe)) == [
        "hallazgos.registro[0].fuente",
        "hallazgos.listas[0].fecha",
        "hallazgos.noticias[0].texto",
        "hallazgos.noticias[0].fecha",
    ]


# --- hallazgos -------------------------------------------------------------------------------


def test_un_frente_ausente_equivale_a_una_lista_vacia():
    informe = _informe()
    informe["hallazgos"] = {"registro": informe["hallazgos"]["registro"], "categoria": []}
    assert validar_informe(informe) == []


def test_un_frente_desconocido_es_un_problema_sin_repetir_la_clave():
    informe = _informe()
    informe["hallazgos"][VALOR_FICTICIO] = []
    (problema,) = validar_informe(informe)
    assert problema.ruta == "hallazgos"
    assert "registro, listas, noticias o categoria" in problema.texto
    assert VALOR_FICTICIO not in problema.ruta + problema.texto


def test_el_valor_de_un_frente_debe_ser_una_lista():
    informe = _informe()
    informe["hallazgos"]["registro"] = {"texto": "x", "fuente": SUR, "fecha": "2026-09-30"}
    assert _rutas(validar_informe(informe)) == ["hallazgos.registro"]


@pytest.mark.parametrize("hallazgos", [["registro"], "texto", 5])
def test_los_hallazgos_deben_ser_un_objeto(hallazgos):
    assert _rutas(validar_informe({**_informe(), "hallazgos": hallazgos})) == ["hallazgos"]


# --- comercio --------------------------------------------------------------------------------


def test_comercio_verificado_necesita_identificador_y_nombre():
    informe = _informe()
    informe["comercio"]["nombre"] = None
    assert _rutas(validar_informe(informe)) == ["comercio.nombre"]


def test_comercio_sin_verificar_basta_con_uno_de_los_dos():
    informe = _informe()
    informe["comercio"] = {
        "identificador": None,
        "nombre": "Taller Aurora SAS",
        "verificado": False,
    }
    assert validar_informe(informe) == []
    informe["comercio"] = {"identificador": "CO-TA-0002", "nombre": None, "verificado": False}
    assert validar_informe(informe) == []


def test_comercio_sin_verificar_y_sin_ningun_dato_es_un_problema():
    informe = _informe()
    informe["comercio"] = {"identificador": None, "nombre": "  ", "verificado": False}
    assert _rutas(validar_informe(informe)) == ["comercio"]


@pytest.mark.parametrize("verificado", [None, "si", 1])
def test_verificado_debe_ser_verdadero_o_falso(verificado):
    informe = _informe()
    informe["comercio"]["verificado"] = verificado
    assert _rutas(validar_informe(informe)) == ["comercio.verificado"]


def test_un_campo_de_mas_en_el_comercio_es_un_problema():
    informe = _informe()
    informe["comercio"]["representante"] = "x"
    assert _rutas(validar_informe(informe)) == ["comercio"]


# --- conflictos ------------------------------------------------------------------------------


def test_sin_conflictos_la_lista_puede_estar_vacia():
    informe = _informe()
    informe["conflictos"] = {
        "resumen": "Sin conflictos entre las fuentes registrales.",
        "lista": [],
    }
    assert validar_informe(informe) == []


def test_un_conflicto_necesita_al_menos_dos_valores():
    informe = _informe()
    informe["conflictos"]["lista"][0]["valores"].pop()
    assert _rutas(validar_informe(informe)) == ["conflictos.lista[0].valores"]


def test_cada_valor_en_conflicto_necesita_su_fuente_y_una_fecha_real():
    informe = _informe()
    valores = informe["conflictos"]["lista"][0]["valores"]
    del valores[0]["fuente"]
    valores[1]["fecha"] = "2026-02-30"
    assert _rutas(validar_informe(informe)) == [
        "conflictos.lista[0].valores[0].fuente",
        "conflictos.lista[0].valores[1].fecha",
    ]


def test_el_resumen_de_conflictos_es_obligatorio():
    informe = _informe()
    informe["conflictos"] = {"lista": []}
    assert _rutas(validar_informe(informe)) == ["conflictos.resumen"]


def test_un_conflicto_sin_dato_es_un_problema():
    informe = _informe()
    del informe["conflictos"]["lista"][0]["dato"]
    assert _rutas(validar_informe(informe)) == ["conflictos.lista[0].dato"]


# --- cobertura y recomendación ---------------------------------------------------------------


@pytest.mark.parametrize("cobertura", ["Cobertura completa.", ["a", "b"]])
def test_la_cobertura_es_texto_o_lista_de_textos(cobertura):
    assert validar_informe({**_informe(), "cobertura": cobertura}) == []


@pytest.mark.parametrize("cobertura", [5, ["a", 3], {"a": 1}])
def test_una_cobertura_mal_formada_es_un_problema(cobertura):
    assert _rutas(validar_informe({**_informe(), "cobertura": cobertura})) == ["cobertura"]


def test_la_recomendacion_es_texto_y_el_conjunto_cerrado_no_se_valida_aqui():
    assert validar_informe({**_informe(), "recomendacion": "aprobar"}) == []
    assert _rutas(validar_informe({**_informe(), "recomendacion": 5})) == ["recomendacion"]


# --- textos ----------------------------------------------------------------------------------


def test_los_textos_estan_en_espanol_y_no_repiten_lo_recibido():
    informe = _informe()
    informe["hallazgos"]["registro"][0]["fecha"] = VALOR_FICTICIO
    informe["comercio"]["verificado"] = VALOR_FICTICIO
    informe["recomendacion"] = 5
    problemas = validar_informe(informe)
    assert len(problemas) == 3
    for problema in problemas:
        assert VALOR_FICTICIO not in problema.texto
        assert any(palabra in problema.texto for palabra in ("Debe", "debe", "Falta"))


def test_validar_no_modifica_la_entrada():
    informe = _informe()
    copia = copy.deepcopy(informe)
    informe["hallazgos"]["registro"][0]["fecha"] = "mal"
    copia["hallazgos"]["registro"][0]["fecha"] = "mal"
    validar_informe(informe)
    assert informe == copia


def test_un_informe_sin_ninguna_afirmacion_es_valido():
    # I.5: si ningún frente quedó cubierto, el informe se entrega igual, sin afirmaciones.
    assert validar_informe({**_informe(), "hallazgos": {}}) == []
