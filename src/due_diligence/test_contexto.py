"""Tests del contexto explícito de cada subagente (R11, FR-004, FR-005, FR-013).

El prompt lo construye el código, solo con los campos que el frente necesita.
"""

import pytest

from due_diligence.contexto import FrenteRechazado, construir_contexto, instrucciones
from due_diligence.estado import EstadoCaso
from due_diligence.frentes import FRENTES, Frente

MARCADOR = "FRASE-MARCADORA-DE-LA-CONVERSACION"
SOLICITUD = (
    f"Necesito el due diligence de Tienda Verde SAS, CO-TV-0001. {MARCADOR}. "
    "Estiman unos $80.000.000 mensuales de suplementos dietarios."
)

COMERCIO = {
    "identificador": "CO-TV-0001",
    "nombre": "Tienda Verde SAS",
    "representante_legal": {"nombre": "Lucía Ferrer Montalvo", "identificador": "PE-0001"},
}


def _estado(comercio=None, motivo=""):
    estado = EstadoCaso(SOLICITUD)
    estado.fijar_comercio(comercio, motivo)
    return estado


ENTRADA_COMPLETA = {
    "identificador": "CO-TV-0001",
    "nombre": "Tienda Verde SAS",
    "categoria": "suplementos dietarios",
}


# ---------------------------------------------------- solo lo que cada frente necesita


@pytest.mark.parametrize("frente", [Frente.REGISTRO, Frente.NOTICIAS])
def test_registro_y_noticias_reciben_el_identificador_y_nada_de_otros_frentes(frente):
    prompt = construir_contexto(frente, ENTRADA_COMPLETA, _estado())
    assert "CO-TV-0001" in prompt
    assert "suplementos" not in prompt
    assert "Tienda Verde" not in prompt  # con identificador no hace falta el nombre


@pytest.mark.parametrize("frente", [Frente.REGISTRO, Frente.NOTICIAS])
def test_sin_identificador_se_usa_el_nombre_y_no_se_inventa_un_identificador(frente):
    prompt = construir_contexto(frente, {"nombre": "Tienda Verde SAS"}, _estado())
    assert "Tienda Verde SAS" in prompt
    assert "CO-" not in prompt


def test_categoria_recibe_solo_la_categoria():
    prompt = construir_contexto(Frente.CATEGORIA, ENTRADA_COMPLETA, _estado())
    assert "suplementos dietarios" in prompt
    assert "CO-TV-0001" not in prompt and "Tienda Verde" not in prompt


def test_listas_recibe_el_comercio_y_el_representante_del_estado():
    prompt = construir_contexto(Frente.LISTAS, {}, _estado(COMERCIO))
    for valor in ("CO-TV-0001", "Tienda Verde SAS", "Lucía Ferrer Montalvo", "PE-0001"):
        assert valor in prompt
    assert "comercio" in prompt and "persona" in prompt


def test_listas_usa_lo_del_estado_aunque_la_entrada_traiga_otros_datos():
    entrada = {
        "identificador": "CO-XX-9999",
        "nombre": "Otro Comercio SAS",
        "categoria": "apuestas",
    }
    prompt = construir_contexto(Frente.LISTAS, entrada, _estado(COMERCIO))
    assert "CO-XX-9999" not in prompt and "Otro Comercio" not in prompt and "apuestas" not in prompt
    assert "CO-TV-0001" in prompt


def test_listas_sin_representante_consulta_solo_al_comercio():
    comercio = {**COMERCIO, "representante_legal": None}
    prompt = construir_contexto(Frente.LISTAS, {}, _estado(comercio))
    assert "CO-TV-0001" in prompt
    assert "no devolvió representante" in prompt
    assert "Lucía" not in prompt


def test_los_valores_del_representante_van_tal_cual():
    comercio = {
        **COMERCIO,
        "representante_legal": {
            "nombre": "  María  del Carmen O'Brien-Ñúñez ",
            "identificador": None,
        },
    }
    prompt = construir_contexto(Frente.LISTAS, {}, _estado(comercio))
    assert "  María  del Carmen O'Brien-Ñúñez " in prompt


# ---------------------------------------------------- nada de la conversación


@pytest.mark.parametrize("frente", list(Frente))
def test_el_prompt_no_contiene_la_solicitud_ni_nada_de_la_conversacion(frente):
    prompt = construir_contexto(frente, ENTRADA_COMPLETA, _estado(COMERCIO))
    assert MARCADOR not in prompt
    assert "80.000.000" not in prompt
    assert "Necesito el due diligence" not in prompt
    assert "habilitar" not in prompt


# ---------------------------------------------------- sin el dato: no se inventa nada (FR-013)


@pytest.mark.parametrize("frente", [Frente.REGISTRO, Frente.NOTICIAS])
@pytest.mark.parametrize("entrada", [{}, {"nombre": ""}, {"identificador": "   "}, {"nombre": 5}])
def test_registro_y_noticias_sin_identificador_ni_nombre_se_rechazan_nombrando_el_dato(
    frente, entrada
):
    with pytest.raises(FrenteRechazado) as error:
        construir_contexto(frente, entrada, _estado())
    assert "identificador" in str(error.value) and "nombre" in str(error.value)


@pytest.mark.parametrize("entrada", [{}, {"categoria": ""}, {"categoria": None}, {"categoria": 7}])
def test_categoria_sin_categoria_se_rechaza_y_no_se_inventa_una(entrada):
    with pytest.raises(FrenteRechazado) as error:
        construir_contexto(Frente.CATEGORIA, entrada, _estado())
    assert "categoría" in str(error.value)


def test_listas_sin_comercio_unico_se_rechaza_con_el_motivo_del_estado():
    estado = _estado(None, "el registro devolvió varias coincidencias")
    with pytest.raises(FrenteRechazado) as error:
        construir_contexto(Frente.LISTAS, {}, estado)
    assert "varias coincidencias" in str(error.value)


def test_listas_sin_comercio_ni_motivo_dice_que_el_registro_no_identifico_al_comercio():
    with pytest.raises(FrenteRechazado) as error:
        construir_contexto(Frente.LISTAS, {}, _estado())
    assert "registro" in str(error.value)


# ---------------------------------------------------- instrucciones fijas por frente


@pytest.mark.parametrize("frente", list(Frente))
def test_las_instrucciones_son_fijas_en_espanol_y_nombran_su_herramienta(frente):
    texto = instrucciones(frente)
    assert FRENTES[frente].herramienta in texto
    assert instrucciones(frente) == texto
    assert "Eres" in texto and "herramienta" in texto


@pytest.mark.parametrize("frente", list(Frente))
def test_las_instrucciones_no_nombran_herramientas_de_otros_frentes(frente):
    texto = instrucciones(frente)
    for otro, definicion in FRENTES.items():
        if otro is not frente:
            assert definicion.herramienta not in texto
    assert "registrar_informe" not in texto and "escalar_a_cumplimiento" not in texto


def test_las_instrucciones_de_noticias_dicen_que_una_mencion_no_es_coincidencia_en_listas():
    assert "no es una coincidencia" in instrucciones(Frente.NOTICIAS)
