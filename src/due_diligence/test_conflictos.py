"""Tests de `conflictos.calcular_conflictos` (#9; R6, FR-007, FR-008, data-model, caso g).

Los resultados del registro salen de la pasarela con sus datos ficticios (`CO-RF-0006` tiene dos
fechas de constitución distintas) o se construyen a mano para los casos límite.
"""

import copy

import pytest

from due_diligence.conflictos import (
    RESUMEN_NO_CALCULADOS,
    RESUMEN_NO_COMPARABLES,
    RESUMEN_SIN_CONFLICTOS,
    calcular_conflictos,
    no_calculados,
)
from due_diligence.estado import Consulta, EstadoCaso, Situacion
from due_diligence.frentes import FRENTES, Frente
from servidor_mcp import datos
from servidor_mcp.registro import consultar_registro_mercantil

SUR = "Registro Mercantil Ficticio del Sur"
RUFE = "Registro Único Ficticio de Empresas"
REGISTRO = FRENTES[Frente.REGISTRO].herramienta_completa


@pytest.fixture(autouse=True)
def _sin_cache(monkeypatch):
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)
    datos.limpiar_cache()
    yield
    datos.limpiar_cache()


def _respuesta(identificador):
    return consultar_registro_mercantil(identificador=identificador).structured_content


def _estado(*respuestas):
    """Un caso cuyo registro terminó con estas respuestas, en orden, como lo deja el `Delegador`."""
    estado = EstadoCaso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    for respuesta in respuestas:
        estado.registrar_identificacion(respuesta)
        estado.agregar_consultas([Consulta(Frente.REGISTRO, REGISTRO, {}, respuesta, True)])
    return estado


def test_caso_g_las_dos_fechas_de_constitucion_aparecen_con_su_fuente():
    conflictos = calcular_conflictos(_estado(_respuesta("CO-RF-0006")))
    assert conflictos.estado == "con_conflictos"
    assert conflictos.resumen == "1 conflicto entre las fuentes registrales."
    assert conflictos.como_entrada() == {
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
    }


def test_un_comercio_con_las_dos_fuentes_iguales_no_tiene_conflictos():
    conflictos = calcular_conflictos(_estado(_respuesta("CO-TA-0002")))
    assert conflictos.estado == "sin_conflictos"
    assert conflictos.como_entrada() == {"resumen": RESUMEN_SIN_CONFLICTOS, "lista": []}
    assert RESUMEN_SIN_CONFLICTOS == "Sin conflictos entre las fuentes registrales."


def test_dos_datos_distintos_dan_dos_conflictos_en_el_orden_del_contenido():
    respuesta = copy.deepcopy(_respuesta("CO-RF-0006"))
    respuesta["hechos"][1]["contenido"]["estado"] = "inactivo"
    conflictos = calcular_conflictos(_estado(respuesta))
    assert [c.dato for c in conflictos.lista] == ["fecha_constitucion", "estado"]
    assert conflictos.resumen == "2 conflictos entre las fuentes registrales."


def test_un_dato_de_una_sola_fuente_no_es_conflicto():
    respuesta = copy.deepcopy(_respuesta("CO-TA-0002"))
    respuesta["hechos"][0]["contenido"]["capital"] = "ficticio"
    assert calcular_conflictos(_estado(respuesta)).estado == "sin_conflictos"


def test_el_identificador_nunca_se_compara():
    respuesta = copy.deepcopy(_respuesta("CO-TA-0002"))
    respuesta["hechos"][1]["contenido"]["identificador"] = "co-ta-0002"
    respuesta["coincidencias"] = ["CO-TA-0002"]
    estado = EstadoCaso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    estado.registrar_identificacion(_respuesta("CO-TA-0002"))
    estado.agregar_consultas([Consulta(Frente.REGISTRO, REGISTRO, {}, respuesta, True)])
    assert all(c.dato != "identificador" for c in calcular_conflictos(estado).lista)


def test_una_sola_fuente_con_el_comercio_no_tiene_conflictos():
    respuesta = copy.deepcopy(_respuesta("CO-RF-0006"))
    respuesta["hechos"] = respuesta["hechos"][:1]
    assert calcular_conflictos(_estado(respuesta)).estado == "sin_conflictos"


def test_se_usa_la_ultima_consulta_valida_que_coincide_con_el_comercio():
    estado = _estado(_respuesta("CO-TA-0002"), _respuesta("CO-RF-0006"))
    # El comercio identificado es el de la consulta con coincidencias (consolidación del #6):
    # aquí difieren, así que no hay comercio único y no hay nada que comparar.
    assert estado.comercio is None
    assert calcular_conflictos(estado).estado == "no_comparables"
    estado = _estado(_respuesta("CO-RF-0006"))
    estado.agregar_consultas(
        [Consulta(Frente.REGISTRO, REGISTRO, {}, _respuesta("CO-TA-0002"), True)]
    )
    assert calcular_conflictos(estado).estado == "con_conflictos"


def test_con_comercio_identificado_y_sin_una_consulta_que_coincida_no_son_comparables():
    # Hallazgo U1: nunca `sin_conflictos`, que afirmaría algo que no se comparó.
    estado = EstadoCaso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    estado.registrar_identificacion(_respuesta("CO-RF-0006"))  # sin `estado.consultas`
    conflictos = calcular_conflictos(estado)
    assert conflictos.estado == "no_comparables"
    assert conflictos.como_entrada() == {"resumen": RESUMEN_NO_COMPARABLES, "lista": []}


def test_con_el_registro_caido_no_son_comparables():
    estado = EstadoCaso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.NO_TERMINADO, "caído")
    conflictos = calcular_conflictos(estado)
    assert conflictos.estado == "no_comparables"
    assert RESUMEN_NO_COMPARABLES == (
        "No se pudieron comparar las fuentes registrales: el registro no respondió."
    )


def test_las_consultas_no_validas_no_cuentan():
    estado = _estado(_respuesta("CO-RF-0006"))
    estado.consultas = [
        Consulta(c.frente, c.herramienta, c.argumentos, c.resultado, False)
        for c in estado.consultas
    ]
    assert calcular_conflictos(estado).estado == "no_comparables"


def test_el_marcador_no_calculados_tiene_su_resumen_fijo():
    conflictos = no_calculados()
    assert conflictos.estado == "no_calculados"
    assert conflictos.como_entrada() == {"resumen": RESUMEN_NO_CALCULADOS, "lista": []}
    assert RESUMEN_NO_CALCULADOS == (
        "No se pudieron calcular los conflictos; deben tratarse como no verificados."
    )


def test_es_pura_y_el_resumen_no_repite_datos_del_comercio():
    estado = _estado(_respuesta("CO-RF-0006"))
    antes = copy.deepcopy(estado)
    conflictos = calcular_conflictos(estado)
    assert estado == antes
    for dato in ("CO-RF-0006", "Ferretería", "Río Fino"):
        assert dato not in conflictos.resumen
