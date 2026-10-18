"""Tests de `conflictos.calcular_conflictos` (#9; R6, FR-007, FR-008, data-model, caso g).

Los resultados del registro salen de la pasarela con sus datos ficticios (`CO-RF-0006` tiene dos
fechas de constitución distintas) o se construyen a mano para los casos límite.
"""

import copy

import pytest

from due_diligence.conflictos import (
    RESUMEN_NO_CALCULADOS,
    RESUMEN_REGISTRO_CAIDO,
    RESUMEN_SIN_COMERCIO,
    RESUMEN_SIN_CONFLICTOS,
    RESUMEN_SIN_CONSULTA,
    SIN_COMPARAR,
    calcular_conflictos,
    no_calculados,
)
from due_diligence.estado import Consulta, EstadoCaso, Situacion
from due_diligence.frentes import FRENTES, Frente
from due_diligence.simulacion import comercios_parecidos, respuesta_registro
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


def test_un_hecho_con_otro_identificador_no_se_compara_ni_da_conflictos():
    # Los hechos se agrupan por el identificador exacto del comercio: uno con otro identificador
    # (aquí solo cambia a minúsculas) es de otro comercio, así que ni su identificador ni sus demás
    # datos, aunque difieran, dan un conflicto.
    respuesta = copy.deepcopy(_respuesta("CO-TA-0002"))
    respuesta["hechos"][1]["contenido"]["identificador"] = "co-ta-0002"
    respuesta["hechos"][1]["contenido"]["fecha_constitucion"] = "2001-01-01"
    respuesta["coincidencias"] = ["CO-TA-0002"]
    estado = EstadoCaso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    estado.registrar_identificacion(_respuesta("CO-TA-0002"))
    estado.agregar_consultas([Consulta(Frente.REGISTRO, REGISTRO, {}, respuesta, True)])
    conflictos = calcular_conflictos(estado)
    assert conflictos.estado == "sin_conflictos" and conflictos.lista == ()


def test_una_sola_fuente_con_el_comercio_no_tiene_conflictos():
    respuesta = copy.deepcopy(_respuesta("CO-RF-0006"))
    respuesta["hechos"] = respuesta["hechos"][:1]
    assert calcular_conflictos(_estado(respuesta)).estado == "sin_conflictos"


def test_se_usa_la_ultima_consulta_valida_que_coincide_con_el_comercio():
    estado = _estado(_respuesta("CO-TA-0002"), _respuesta("CO-RF-0006"))
    # El comercio identificado es el de la consulta con coincidencias (consolidación del #6):
    # aquí difieren, así que no hay comercio único y no hay nada que comparar.
    assert estado.comercio is None
    assert calcular_conflictos(estado).estado == "sin_comercio"
    estado = _estado(_respuesta("CO-RF-0006"))
    estado.agregar_consultas(
        [Consulta(Frente.REGISTRO, REGISTRO, {}, _respuesta("CO-TA-0002"), True)]
    )
    assert calcular_conflictos(estado).estado == "con_conflictos"


def test_con_comercio_identificado_y_sin_una_consulta_que_coincida_no_se_comparan():
    # Hallazgo U1: nunca `sin_conflictos`, que afirmaría algo que no se comparó; y tampoco que el
    # registro no respondió, porque respondió.
    estado = EstadoCaso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    estado.registrar_identificacion(_respuesta("CO-RF-0006"))  # sin `estado.consultas`
    conflictos = calcular_conflictos(estado)
    assert conflictos.estado == "sin_consulta"
    assert conflictos.como_entrada() == {"resumen": RESUMEN_SIN_CONSULTA, "lista": []}
    assert RESUMEN_SIN_CONSULTA == (
        "No se compararon las fuentes registrales: ninguna consulta válida del registro trae el "
        "comercio identificado."
    )


def _caido(estado, tipo="servicio_no_disponible"):
    """El registro no terminó por un error de la fuente, como lo deja la delegación (#8)."""
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.NO_TERMINADO, "caído")
    estado.errores[Frente.REGISTRO] = {
        "causa": "error_de_fuente",
        "reintentable": tipo == "servicio_no_disponible",
        "obtenido": {"errores": [{"tipo": tipo}]},
    }
    return estado


def test_solo_con_el_registro_caido_dice_que_el_registro_no_respondio():
    conflictos = calcular_conflictos(_caido(EstadoCaso()))
    assert conflictos.estado == "registro_caido"
    assert conflictos.como_entrada() == {"resumen": RESUMEN_REGISTRO_CAIDO, "lista": []}
    assert RESUMEN_REGISTRO_CAIDO == (
        "No se pudieron comparar las fuentes registrales: el registro no respondió."
    )


def _sin_iniciar():
    return EstadoCaso()


def _en_curso():
    estado = EstadoCaso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    return estado


def _varias_coincidencias():
    respuesta = respuesta_registro(*comercios_parecidos())
    return _estado(respuesta)


def _ninguna_coincidencia():
    return _estado(respuesta_registro())


def _entrada_invalida():
    return _caido(EstadoCaso(), "entrada_invalida")


@pytest.mark.parametrize(
    "construir",
    [_sin_iniciar, _en_curso, _varias_coincidencias, _ninguna_coincidencia, _entrada_invalida],
)
def test_sin_comercio_identificado_por_otro_motivo_no_dice_que_el_registro_no_respondio(construir):
    estado = construir()
    assert estado.comercio is None
    conflictos = calcular_conflictos(estado)
    assert conflictos.estado == "sin_comercio"
    assert conflictos.como_entrada() == {"resumen": RESUMEN_SIN_COMERCIO, "lista": []}
    assert "no respondió" not in conflictos.resumen
    assert RESUMEN_SIN_COMERCIO == (
        "No se compararon las fuentes registrales: no hay comercio identificado."
    )


def test_los_tres_estados_sin_comparacion_son_distintos_y_ninguno_es_sin_conflictos():
    assert SIN_COMPARAR == {"registro_caido", "sin_comercio", "sin_consulta"}
    resumenes = {RESUMEN_REGISTRO_CAIDO, RESUMEN_SIN_COMERCIO, RESUMEN_SIN_CONSULTA}
    assert len(resumenes) == 3 and RESUMEN_SIN_CONFLICTOS not in resumenes


def test_las_consultas_no_validas_no_cuentan():
    estado = _estado(_respuesta("CO-RF-0006"))
    estado.consultas = [
        Consulta(c.frente, c.herramienta, c.argumentos, c.resultado, False)
        for c in estado.consultas
    ]
    assert calcular_conflictos(estado).estado == "sin_consulta"


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
