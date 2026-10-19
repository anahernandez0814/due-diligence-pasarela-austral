"""Tests de `due_diligence.informe` (#9; R4, R5, R7, R8, data-model): funciones puras del informe.

Fuentes consultadas por frente (FR-004), el comercio que el código pone en el informe (FR-006) y,
desde la fase 5, la huella y la vigencia. Todos los datos son ficticios.
"""

import pytest

from due_diligence import informe as modulo_informe
from due_diligence.estado import Causa, EstadoCaso, Situacion
from due_diligence.frentes import Frente
from due_diligence.informe import (
    NO_CALCULADOS,
    InformeRegistrado,
    cambios,
    comercio_del_informe,
    fuentes_consultadas,
    huella_actual,
    informe_vigente,
    problemas_de_fuente,
    registro_caido,
    registro_reintentable,
    requiere_informe,
)
from due_diligence.libro import Coincidencia
from due_diligence.simulacion import (
    comercios_parecidos,
    consulta,
    consulta_listas,
    error_estructurado,
    respuesta_del_contrato,
    respuesta_registro,
)
from servidor_mcp.informe import FRENTES_INFORME, Problema

SUR = "Registro Mercantil Ficticio del Sur"
LISTA = "Lista Restrictiva Ficticia"


@pytest.fixture(autouse=True)
def _sin_caida_del_registro(monkeypatch):
    """Los tests que consultan el registro real no dependen de la caída simulada de la sesión."""
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)


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
    # Las tildes tampoco importan (T016).
    hallazgos = {"registro": [_afirmacion("Régistro Mercantil Fictício del Sur")]}
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


# ------------------------------------------------------------------ huella y vigencia (R7, R8)


def _error_registro(causa, tipos=(), reintentable=False):
    return {
        "error": True,
        "tipo": "frente_no_terminado",
        "causa": causa.value,
        "reintentable": reintentable,
        "obtenido": {"errores": [{"tipo": t, "reintentable": False} for t in tipos]},
    }


def _registro_no_terminado(estado, error):
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.NO_TERMINADO, "falló")
    estado.errores[Frente.REGISTRO] = error


def _con_informe(estado, huella=None):
    estado.informes.append(
        InformeRegistrado("INF-0001", "no_habilitar", False, huella or huella_actual(estado))
    )


def test_un_frente_que_pasa_de_un_error_a_otro_no_cambia_la_huella():
    estado = EstadoCaso()
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.NO_TERMINADO, "caída")
    estado.errores[Frente.NOTICIAS] = {"causa": "error_de_fuente", "intento": 1}
    antes = huella_actual(estado)
    # Un reintento que vuelve a fallar, con otra causa y otro número de intentos.
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.NO_TERMINADO, "otra")
    estado.errores[Frente.NOTICIAS] = {"causa": "terminacion_anomala", "intento": 2}
    assert huella_actual(estado) == antes


def test_un_frente_que_pasa_a_cubierto_cambia_la_cobertura_de_la_huella():
    estado = EstadoCaso()
    antes = huella_actual(estado)
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.TERMINADO)
    assert cambios(antes, huella_actual(estado)) == ["la cobertura"]


def test_una_causa_nueva_y_un_comercio_distinto_cambian_la_huella():
    estado = EstadoCaso()
    antes = huella_actual(estado)
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    assert cambios(antes, huella_actual(estado)) == ["las causas de escalamiento"]
    antes = huella_actual(estado)
    estado.comercio_pedido = {"identificador": "CO-TA-0002", "nombre": None}
    assert cambios(antes, huella_actual(estado)) == ["el comercio"]


def test_un_conflicto_nuevo_cambia_la_huella():
    from servidor_mcp import datos
    from servidor_mcp.registro import consultar_registro_mercantil

    datos.limpiar_cache()
    estado = EstadoCaso()
    _con_registro_identificado(estado, "CO-RF-0006", "Ferretería Río Fino SAS")
    antes = huella_actual(estado)
    respuesta = consultar_registro_mercantil(identificador="CO-RF-0006").structured_content
    estado.agregar_consultas([consulta(Frente.REGISTRO, {}, respuesta)])
    assert cambios(antes, huella_actual(estado)) == ["los conflictos"]


def test_del_registro_en_curso_al_registro_caido_solo_cambian_los_conflictos():
    # Bloqueante de la revisión del #9: los dos van sin comercio identificado y con el registro no
    # cubierto, pero solo el caído dice que no respondió. La huella los distingue por el estado de
    # los conflictos, así que un informe registrado con uno no queda vigente con el otro.
    estado = EstadoCaso()
    estado.comercio_pedido = {"identificador": "CO-TA-0002", "nombre": None}
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    antes = huella_actual(estado)
    assert antes.conflictos == ("sin_comercio", ())
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.NO_TERMINADO, "caído")
    estado.errores[Frente.REGISTRO] = _error_registro(
        Causa.ERROR_DE_FUENTE, ("servicio_no_disponible",)
    )
    despues = huella_actual(estado)
    assert despues.conflictos == ("registro_caido", ())
    assert cambios(antes, despues) == ["los conflictos"]


def test_con_el_caso_sellado_la_huella_no_calcula_cobertura_ni_conflictos(monkeypatch):
    estado = EstadoCaso()
    estado.comercio_pedido = {"identificador": "CO-TA-0002", "nombre": None}
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"

    def roto(_estado):
        raise RuntimeError("no se debe llamar")

    monkeypatch.setattr(modulo_informe, "calcular_cobertura", roto)
    monkeypatch.setattr(modulo_informe, "calcular_conflictos", roto)
    primera = huella_actual(estado)
    assert primera.cobertura == NO_CALCULADOS and primera.conflictos == NO_CALCULADOS
    # T031 (repuesta tras la parada A): con el sello, la causa `fallo_de_hook` entra en la huella.
    # Las causas y el comercio se siguen calculando (T025).
    assert primera.causas == frozenset({"fallo_de_hook"})
    assert primera.comercio == ("CO-TA-0002", None, False)
    assert huella_actual(estado) == primera


def test_el_sello_es_una_causa_nueva_que_cambia_la_huella():
    estado = EstadoCaso()
    antes = huella_actual(estado)
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    # La cobertura y los conflictos pasan a no calculados; las causas ganan el sello.
    assert cambios(antes, huella_actual(estado)) == [
        "la cobertura",
        "los conflictos",
        "las causas de escalamiento",
    ]


def test_informe_vigente_solo_si_la_huella_del_ultimo_coincide():
    estado = EstadoCaso()
    assert informe_vigente(estado) is False
    _con_informe(estado)
    assert informe_vigente(estado) is True
    estado.cambiar_situacion(Frente.CATEGORIA, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.CATEGORIA, Situacion.TERMINADO)
    assert informe_vigente(estado) is False
    _con_informe(estado)  # un informe nuevo lo deja vigente
    assert informe_vigente(estado) is True


@pytest.mark.parametrize(
    ("causa", "tipos"),
    [
        (Causa.TERMINACION_ANOMALA, ()),
        (Causa.SIN_CONSULTAS, ()),
        (Causa.RESULTADO_INVALIDO, ()),
        (Causa.CANCELADO, ()),
        (Causa.ERROR_DE_FUENTE, ("servicio_no_disponible",)),
        (Causa.ERROR_DE_FUENTE, ("datos_no_disponibles",)),
        (Causa.ERROR_DE_FUENTE, ("error_interno",)),
    ],
)
@pytest.mark.parametrize("reintentable", [True, False])
def test_el_registro_esta_caido_si_la_fuente_no_respondio_con_o_sin_reintento(
    causa, tipos, reintentable
):
    estado = EstadoCaso()
    _registro_no_terminado(estado, _error_registro(causa, tipos, reintentable))
    assert registro_caido(estado) is True
    assert requiere_informe(estado) is True
    assert registro_reintentable(estado) is reintentable


def test_una_entrada_invalida_no_es_registro_caido():
    estado = EstadoCaso()
    _registro_no_terminado(estado, _error_registro(Causa.ERROR_DE_FUENTE, ("entrada_invalida",)))
    assert registro_caido(estado) is False
    assert requiere_informe(estado) is False


@pytest.mark.parametrize(
    "situacion",
    [Situacion.SIN_INICIAR, Situacion.EN_CURSO, Situacion.TERMINADO, Situacion.RECHAZADO],
)
def test_un_registro_que_no_quedo_no_terminado_no_esta_caido(situacion):
    estado = EstadoCaso()
    estado._situaciones[Frente.REGISTRO] = situacion
    # Con un error de caída guardado: decide la situación, no la ausencia de error (T025).
    estado.errores[Frente.REGISTRO] = _error_registro(
        Causa.ERROR_DE_FUENTE, ("servicio_no_disponible",)
    )
    assert registro_caido(estado) is False


def test_requiere_informe_con_comercio_identificado_y_no_con_varias_o_ninguna():
    estado = EstadoCaso()
    _con_registro_identificado(estado)
    assert requiere_informe(estado) is True
    for respuesta in (respuesta_registro(*comercios_parecidos()), respuesta_registro()):
        sin_comercio = EstadoCaso()
        sin_comercio.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
        sin_comercio.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
        sin_comercio.registrar_identificacion(respuesta)
        assert requiere_informe(sin_comercio) is False


# -------------------------------- #10: fuentes de noticias y listas por comercio (T025, FR-027)

NOTICIAS_FICTICIAS = "Noticias Ficticias"


def _noticias(argumentos):
    respuesta = respuesta_del_contrato("sin_coincidencias", fuente=NOTICIAS_FICTICIAS)
    return consulta(Frente.NOTICIAS, argumentos, respuesta)


def _identificado_como(estado, identificador):
    parecidos = {c["identificador"]: c for c in comercios_parecidos()}
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    estado.registrar_identificacion(respuesta_registro(parecidos[identificador]))
    return estado


def test_con_otro_comercio_identificado_la_fuente_de_noticias_no_cuenta():
    estado = _identificado_como(EstadoCaso(), "CO-AM-0005")
    estado.agregar_consultas([_noticias({"nombre": "Almacén Mirador SAS"})])
    assert fuentes_consultadas(estado, Frente.NOTICIAS) == []
    hallazgos = {"noticias": [_afirmacion(NOTICIAS_FICTICIAS)]}
    assert problemas_de_fuente(estado, hallazgos) == [
        Problema(
            "hallazgos.noticias[0].fuente",
            "La fuente no es ninguna de las consultadas para noticias.",
        )
    ]


def test_con_la_consulta_del_comercio_identificado_la_fuente_de_noticias_cuenta():
    estado = _identificado_como(EstadoCaso(), "CO-AM-0005")
    estado.agregar_consultas(
        [_noticias({"nombre": "Almacén Mirador SAS"}), _noticias({"identificador": "CO-AM-0005"})]
    )
    assert fuentes_consultadas(estado, Frente.NOTICIAS) == [NOTICIAS_FICTICIAS]


def test_en_listas_cuentan_el_comercio_y_su_representante_y_no_el_comercio_anterior():
    estado = _identificado_como(EstadoCaso(), "CO-AM-0005")
    estado.agregar_consultas([consulta_listas("comercio", identificador="CO-AM-0004")])
    assert fuentes_consultadas(estado, Frente.LISTAS) == []
    estado.agregar_consultas([consulta_listas("persona", identificador="PE-0005")])
    assert fuentes_consultadas(estado, Frente.LISTAS) == [LISTA]
    # Y la del propio comercio identificado, sola.
    del_comercio = _identificado_como(EstadoCaso(), "CO-AM-0005")
    del_comercio.agregar_consultas([consulta_listas("comercio", identificador="CO-AM-0005")])
    assert fuentes_consultadas(del_comercio, Frente.LISTAS) == [LISTA]


def test_sin_comercio_identificado_cuentan_todas_las_consultas_como_en_el_9():
    estado = EstadoCaso()
    estado.agregar_consultas([_noticias({"nombre": "cualquiera"})])
    assert fuentes_consultadas(estado, Frente.NOTICIAS) == [NOTICIAS_FICTICIAS]


def test_la_huella_cambia_al_pasar_noticias_a_no_cubierto():
    # El registro ya terminó (ambiguo) antes y después: solo noticias cambia la cobertura.
    from due_diligence.cobertura import calcular_cobertura
    from due_diligence.estado import ResultadoFrente
    from due_diligence.simulacion import terminacion_normal

    estado = EstadoCaso()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    estado.registrar_identificacion(respuesta_registro(*comercios_parecidos()))
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.TERMINADO)
    estado.guardar_resultado(
        ResultadoFrente(
            Frente.NOTICIAS,
            [_noticias({"nombre": "Almacén Mirador SAS"})],
            "",
            terminacion_normal(),
            "",
        )
    )
    antes = huella_actual(estado)
    assert calcular_cobertura(estado).frentes[Frente.NOTICIAS].cubierto is True
    # T025 (barrido): un informe registrado con la huella de antes deja de estar vigente.
    estado.informes.append(InformeRegistrado("INF-0001", "no_habilitar", False, antes))
    assert informe_vigente(estado) is True
    estado.reiniciar_identificacion()
    parecidos = {c["identificador"]: c for c in comercios_parecidos()}
    estado.registrar_identificacion(respuesta_registro(parecidos["CO-AM-0005"]))
    assert calcular_cobertura(estado).frentes[Frente.NOTICIAS].cubierto is False
    # También cambian los conflictos (ya hay comercio que comparar) y el comercio; la cobertura
    # solo cambia por noticias, porque el registro estaba terminado antes y después.
    assert "la cobertura" in cambios(antes, huella_actual(estado))
    assert informe_vigente(estado) is False


def test_con_el_comercio_identificado_registro_y_categoria_siguen_contando_sus_fuentes():
    # T025 (barrido): el filtro de FR-027 solo toca noticias y listas; registro y categoría no
    # dependen del comercio consultado y sus fuentes valen aunque la consulta traiga otros datos.
    from due_diligence.simulacion import respuesta_riesgo

    estado = _identificado_como(EstadoCaso(), "CO-AM-0005")
    estado.agregar_consultas(
        [
            consulta(Frente.REGISTRO, {"nombre": "Almacén Mirador SAS"}),
            consulta(
                Frente.CATEGORIA,
                {"categoria": "ropa y accesorios"},
                respuesta_riesgo("ropa y accesorios", "bajo"),
            ),
        ]
    )
    assert fuentes_consultadas(estado, Frente.REGISTRO) == [SUR]
    assert fuentes_consultadas(estado, Frente.CATEGORIA) == ["Catálogo Ficticio de Categorías"]
