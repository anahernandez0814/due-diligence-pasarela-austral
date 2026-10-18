"""Tests de `due_diligence.informe` (#9; R4, R5, R7, R8, data-model): funciones puras del informe.

Fuentes consultadas por frente (FR-004), el comercio que el código pone en el informe (FR-006) y,
desde la fase 5, la huella y la vigencia. Todos los datos son ficticios.
"""

from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.frentes import Frente
from due_diligence.informe import comercio_del_informe, fuentes_consultadas, problemas_de_fuente
from due_diligence.simulacion import (
    consulta,
    consulta_listas,
    error_estructurado,
    respuesta_del_contrato,
    respuesta_registro,
)
from servidor_mcp.informe import FRENTES_INFORME, Problema

SUR = "Registro Mercantil Ficticio del Sur"
LISTA = "Lista Restrictiva Ficticia"


def _afirmacion(fuente, fecha="2026-09-30"):
    return {"texto": "Sin novedades.", "fuente": fuente, "fecha": fecha}


def _con_registro_identificado(estado, identificador="CO-TA-0002", nombre="Taller Aurora SAS"):
    comercio = {
        "identificador": identificador,
        "nombre": nombre,
        "fecha_constitucion": "2018-08-03",
        "estado": "activo",
        "representante_legal": None,
    }
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    estado.registrar_identificacion(respuesta_registro(comercio))


def test_los_frentes_del_esquema_son_los_del_caso():
    # T004 y hallazgo T2: el esquema de la pasarela no importa `due_diligence`; se compara aquí.
    assert FRENTES_INFORME == tuple(f.value for f in Frente)


# ------------------------------------------------------------------ fuentes consultadas (R4)


def test_las_fuentes_salen_de_los_hechos_y_de_los_metadatos_de_las_consultas_validas():
    estado = EstadoCaso()
    estado.agregar_consultas([consulta(Frente.REGISTRO), consulta_listas("comercio", nombre="x")])
    assert fuentes_consultadas(estado, Frente.REGISTRO) == [SUR]
    # Una respuesta `sin_coincidencias` de listas no tiene hechos, pero sí su fuente.
    assert fuentes_consultadas(estado, Frente.LISTAS) == [LISTA]


def test_solo_cuentan_las_consultas_validas_del_frente():
    estado = EstadoCaso()
    fallida = consulta(Frente.NOTICIAS, {"nombre": "x"}, error=error_estructurado())
    estado.agregar_consultas([fallida, consulta(Frente.REGISTRO)])
    assert fuentes_consultadas(estado, Frente.NOTICIAS) == []
    assert fuentes_consultadas(estado, Frente.CATEGORIA) == []


def test_las_fuentes_de_los_hechos_y_de_los_metadatos_no_se_repiten():
    estado = EstadoCaso()
    respuesta = respuesta_del_contrato("coincidencias", [{"a": 1}, {"a": 2}], ["x"])
    estado.agregar_consultas([consulta(Frente.REGISTRO, {}, respuesta)] * 2)
    assert fuentes_consultadas(estado, Frente.REGISTRO) == [SUR]


def test_una_afirmacion_con_una_fuente_consultada_no_es_un_problema_aunque_cambie_la_forma():
    estado = EstadoCaso()
    estado.agregar_consultas([consulta(Frente.REGISTRO)])
    hallazgos = {"registro": [_afirmacion("  registro mercantil ficticio del SUR ")]}
    assert problemas_de_fuente(estado, hallazgos) == []


def test_un_problema_por_afirmacion_con_una_fuente_no_consultada():
    estado = EstadoCaso()
    estado.agregar_consultas([consulta(Frente.REGISTRO)])
    hallazgos = {
        "registro": [_afirmacion(SUR), _afirmacion("Fuente Inventada")],
        "noticias": [_afirmacion(SUR)],  # la fuente existe, pero no se consultó para noticias
    }
    assert problemas_de_fuente(estado, hallazgos) == [
        Problema(
            "hallazgos.registro[1].fuente",
            "La fuente no es ninguna de las consultadas para registro.",
        ),
        Problema(
            "hallazgos.noticias[0].fuente",
            "La fuente no es ninguna de las consultadas para noticias.",
        ),
    ]


def test_las_afirmaciones_mal_formadas_las_nombra_el_esquema_y_no_esta_comprobacion():
    estado = EstadoCaso()
    hallazgos = {"registro": [{"texto": "x"}, "no es un objeto"], "otro": [], "listas": "x"}
    assert problemas_de_fuente(estado, hallazgos) == []
    assert problemas_de_fuente(estado, "no es un objeto") == []


# ------------------------------------------------------------------ comercio del informe (R5)


def test_el_comercio_identificado_va_verificado_con_identificador_y_nombre():
    estado = EstadoCaso()
    _con_registro_identificado(estado)
    assert comercio_del_informe(estado) == {
        "identificador": "CO-TA-0002",
        "nombre": "Taller Aurora SAS",
        "verificado": True,
    }


def test_sin_comercio_identificado_va_el_pedido_sin_verificar_y_sin_inventar_datos():
    estado = EstadoCaso()
    estado.comercio_pedido = {"identificador": None, "nombre": "Taller Aurora SAS"}
    assert comercio_del_informe(estado) == {
        "identificador": None,
        "nombre": "Taller Aurora SAS",
        "verificado": False,
    }


def test_sin_comercio_identificado_ni_pedido_no_hay_comercio_para_el_informe():
    assert comercio_del_informe(EstadoCaso()) is None


def test_el_identificado_prevalece_sobre_el_pedido():
    estado = EstadoCaso()
    estado.comercio_pedido = {"identificador": "CO-TA-0002", "nombre": None}
    _con_registro_identificado(estado)
    assert comercio_del_informe(estado)["verificado"] is True
