"""Casos del #10 de extremo a extremo: escalamiento con criterio, resumen al oficial y ambigüedad.

Casos de prueba (a), (b) y (d) de la constitución (X), este último en dos turnos del mismo caso
(FR-023, SC-001, SC-003). Un `Caso` real con subagentes simulados y un `CoordinadorSimulado` cuyo
guion pasa por los hooks del coordinador y por la `PasarelaSimulada`, que valida el informe y el
resumen como la real. No se llama al modelo. Datos ficticios del #5.
"""

import asyncio

import pytest

from due_diligence.coordinador import Caso
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_CIERRE_IMPEDIDO,
    TIPO_COBERTURA_SUSTITUIDA,
    TIPO_DATOS_SUSTITUIDOS,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_ESPERA_ANALISTA,
    TIPO_INFORME_REGISTRADO,
)
from due_diligence.frentes import Frente
from due_diligence.informe import informe_vigente
from due_diligence.reglas import (
    MOTIVO_SIN_CAUSA,
    MOTIVO_VARIAS_COINCIDENCIAS,
    motivo_de_escalar,
)
from due_diligence.simulacion import (
    FUENTE,
    CoordinadorSimulado,
    EjecutorSimulado,
    comercio_alto_riesgo,
    comercio_bajo_riesgo,
    comercios_parecidos,
    consulta,
    consulta_listas,
    respuesta_registro,
    respuesta_riesgo,
    resultado_frente,
)

SOLICITUD_A = (
    "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren "
    "procesar ventas en línea de suplementos dietarios y estiman unos $80.000.000 mensuales. "
    "¿Lo podemos habilitar esta semana?"
)
SOLICITUD_B = (
    "Necesito el due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, "
    "categoría tecnología y software."
)
SOLICITUD_D = "Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios."
SOLICITUD_D_ALTO = "Necesito el due diligence de Almacén Mirador SAS, de suplementos dietarios."
NORTE, ALMACEN = "CO-AM-0005", "CO-AM-0004"


@pytest.fixture(autouse=True)
def _sin_caidas(monkeypatch):
    """Los casos no dependen de la caída simulada de la sesión."""
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)
    monkeypatch.delenv("PASARELA_FALLA_NOTICIAS", raising=False)


def _riesgo(categoria, nivel):
    return resultado_frente(
        Frente.CATEGORIA,
        [consulta(Frente.CATEGORIA, {"categoria": categoria}, respuesta_riesgo(categoria, nivel))],
    )


def _registro(identificador, *comercios):
    return resultado_frente(
        Frente.REGISTRO,
        [
            consulta(
                Frente.REGISTRO, {"identificador": identificador}, respuesta_registro(*comercios)
            )
        ],
    )


def _listas(identificador, representante):
    return resultado_frente(
        Frente.LISTAS,
        [
            consulta_listas("comercio", identificador=identificador),
            consulta_listas("persona", identificador=representante),
        ],
    )


def _caso(guiones, resultados, solicitud):
    coordinador = CoordinadorSimulado(guiones=guiones)
    ejecutor = EjecutorSimulado(resultados=resultados)
    caso = Caso(ejecutor=ejecutor, consulta=coordinador)
    coordinador.caso = caso
    asyncio.run(caso.ejecutar(solicitud))
    return caso, coordinador, ejecutor


def _tipos(caso):
    return [e.tipo for e in caso.eventos()]


def _delegaciones(dato, categoria):
    return (
        "delegar_paralelo",
        [
            {"frente": "registro", **dato},
            {"frente": "noticias", **dato},
            {"frente": "categoria", "categoria": categoria},
        ],
    )


# --------------------------------------------------------------- caso (a): va a un oficial


def test_caso_a_el_alto_riesgo_va_a_un_oficial_y_el_informe_lo_deja_al_oficial():
    resultados = {
        Frente.REGISTRO: _registro("CO-TV-0001", comercio_alto_riesgo()),
        Frente.CATEGORIA: _riesgo("suplementos dietarios", "alto"),
        Frente.LISTAS: _listas("CO-TV-0001", "PE-0001"),
    }
    guion = [
        _delegaciones({"identificador": "CO-TV-0001"}, "suplementos dietarios"),
        ("delegar", {"frente": "listas"}),
        ("escalar", "Revisar el origen de fondos antes de decidir."),
        ("informe", "decide_cumplimiento"),
        ("terminar",),
    ]
    caso, coordinador, _ = _caso([guion], resultados, SOLICITUD_A)
    (resumen,) = coordinador.pasarela.escalamientos
    assert resumen["causa_escalamiento"] == ["categoría de alto riesgo"]
    assert resumen["comercio"] == {
        "identificador": "CO-TV-0001",
        "nombre": "Tienda Verde SAS",
        "verificado": True,
    }
    assert resumen["accion_recomendada"] == "Revisar el origen de fondos antes de decidir."
    assert resumen["cobertura"][0] == "Cobertura completa: 4 de 4 frentes cubiertos."
    (informe,) = coordinador.pasarela.informes
    assert informe["recomendacion"] == "decide_cumplimiento"
    tipos = _tipos(caso)
    assert tipos.index(TIPO_ESCALAMIENTO_REGISTRADO) < tipos.index(TIPO_INFORME_REGISTRADO)
    assert coordinador.resultados_de("terminar")[-1].termino is True
    assert informe_vigente(caso.estado) and caso.completo is True


# ------------------------------------------- caso (b): bajo riesgo, habilitar y sin escalar


def test_caso_b_el_bajo_riesgo_no_se_puede_escalar_y_se_habilita():
    resultados = {
        Frente.REGISTRO: _registro("CO-TA-0002", comercio_bajo_riesgo()),
        Frente.CATEGORIA: _riesgo("tecnología y software", "bajo"),
        Frente.LISTAS: _listas("CO-TA-0002", "PE-0002"),
    }
    guion = [
        _delegaciones({"identificador": "CO-TA-0002"}, "tecnología y software"),
        ("delegar", {"frente": "listas"}),
        ("escalar",),  # el coordinador lo intenta: se rechaza (US1-3)
        ("informe", "habilitar"),
        ("terminar",),
    ]
    caso, coordinador, _ = _caso([guion], resultados, SOLICITUD_B)
    (escalar,) = coordinador.resultados_de("escalar")
    assert escalar.denegada and MOTIVO_SIN_CAUSA in escalar.texto
    assert coordinador.pasarela.escalamientos == []
    (informe,) = coordinador.pasarela.informes
    assert informe["recomendacion"] == "habilitar"
    assert coordinador.resultados_de("terminar")[-1].termino is True
    assert caso.completo is True
    bloqueo = next(e for e in caso.eventos() if e.tipo == TIPO_BLOQUEO_REGLA)
    assert bloqueo.regla == "V" and bloqueo.accion == "escalar_a_cumplimiento"


# ------------------------------------------- caso (d): dos comercios parecidos, dos turnos


def _registro_por_contexto(contexto):
    parecidos = {c["identificador"]: c for c in comercios_parecidos()}
    for identificador, comercio in parecidos.items():
        if identificador in contexto:
            return _registro(identificador, comercio)
    return resultado_frente(
        Frente.REGISTRO,
        [
            consulta(
                Frente.REGISTRO,
                {"nombre": "Almacén Mirador SAS"},
                respuesta_registro(*comercios_parecidos()),
            )
        ],
    )


def _listas_por_contexto(contexto):
    if ALMACEN in contexto:
        return _listas(ALMACEN, "PE-0004")
    return _listas(NORTE, "PE-0005")


def _resultados_d(categoria="ropa y accesorios", nivel="bajo"):
    return {
        Frente.REGISTRO: _registro_por_contexto,
        Frente.CATEGORIA: _riesgo(categoria, nivel),
        Frente.LISTAS: _listas_por_contexto,
    }


TURNO_1_D = [
    _delegaciones({"nombre": "Almacén Mirador SAS"}, "ropa y accesorios"),
    ("delegar", {"frente": "listas"}),  # sin identificación: lo bloquea el hook (caso e)
    ("terminar",),  # pide el identificador
]


def test_caso_d_primer_turno_pide_el_identificador_sin_listas_ni_escalar_ni_informar():
    caso, coordinador, ejecutor = _caso([TURNO_1_D], _resultados_d(), SOLICITUD_D)
    (listas,) = [r for t, r in coordinador.pasos if t == "delegar" and r.denegada]
    assert MOTIVO_VARIAS_COINCIDENCIAS in listas.texto
    assert [e.regla for e in caso.eventos() if e.tipo == TIPO_BLOQUEO_REGLA] == ["I.1"]
    assert ejecutor.llamadas_de(Frente.LISTAS) == []
    assert coordinador.pasarela.escalamientos == [] and coordinador.pasarela.informes == []
    assert coordinador.resultados_de("terminar")[0].termino is True
    assert TIPO_ESPERA_ANALISTA in _tipos(caso)
    assert caso.espera.clase == "identificador" and caso.completo is False


def test_caso_d_segundo_turno_con_co_am_0005_vuelve_a_delegar_noticias_y_consulta_listas():
    turno_2 = [
        (
            "mismo_mensaje",
            [
                ("delegar", {"frente": "registro", "identificador": NORTE}),
                ("delegar", {"frente": "noticias", "identificador": NORTE}),
            ],
        ),
        ("delegar", {"frente": "listas"}),
        ("informe", "no_habilitar"),
        ("terminar",),
    ]
    caso, coordinador, ejecutor = _caso([TURNO_1_D, turno_2], _resultados_d(), SOLICITUD_D)
    asyncio.run(caso.continuar(NORTE))
    assert caso.estado.comercio["identificador"] == NORTE
    noticias = caso.estado.resultados[Frente.NOTICIAS].consultas[0]
    assert noticias.argumentos == {"identificador": NORTE}
    assert noticias.resultado["hechos"][0]["contenido"]["id"] == "N-0001"  # US3-6
    (listas,) = ejecutor.llamadas_de(Frente.LISTAS)
    assert NORTE in listas.contexto and "PE-0005" in listas.contexto
    assert coordinador.reanudaciones == [None, "sesion-de-prueba"]
    assert coordinador.resultados_de("terminar")[-1].termino is True
    assert informe_vigente(caso.estado) and caso.espera is None
    assert caso.cobertura.completa and caso.completo is True


def test_caso_d_con_alto_riesgo_el_primer_turno_espera_y_el_segundo_exige_escalar():
    turno_1 = [
        _delegaciones({"nombre": "Almacén Mirador SAS"}, "suplementos dietarios"),
        ("terminar",),
    ]
    turno_2 = [
        ("delegar", {"frente": "registro", "identificador": NORTE}),
        ("delegar", {"frente": "noticias", "identificador": NORTE}),
        ("delegar", {"frente": "listas"}),
        ("terminar",),  # el Stop exige el escalamiento
        ("escalar",),
        ("informe", "decide_cumplimiento"),
        ("terminar",),
    ]
    resultados = _resultados_d("suplementos dietarios", "alto")
    caso, coordinador, _ = _caso([turno_1, turno_2], resultados, SOLICITUD_D_ALTO)
    primero = coordinador.resultados_de("terminar")[0]
    assert primero.termino is True and coordinador.pasarela.escalamientos == []
    assert caso.espera.clase == "identificador" and TIPO_ESPERA_ANALISTA in _tipos(caso)
    asyncio.run(caso.continuar(NORTE))
    impedido, final = coordinador.resultados_de("terminar")[1:]
    assert impedido.termino is False
    assert impedido.motivo == motivo_de_escalar({"alto_riesgo"}) + " Luego registra el informe."
    assert final.termino is True
    (resumen,) = coordinador.pasarela.escalamientos
    assert resumen["comercio"]["identificador"] == NORTE
    assert caso.completo is True


def test_caso_d_eligiendo_co_am_0004_noticias_se_conserva_sin_volver_a_delegar():
    turno_2 = [
        ("delegar", {"frente": "registro", "identificador": ALMACEN}),
        ("delegar", {"frente": "listas"}),
        ("informe", "no_habilitar"),
        ("terminar",),
    ]
    caso, coordinador, ejecutor = _caso([TURNO_1_D, turno_2], _resultados_d(), SOLICITUD_D)
    asyncio.run(caso.continuar(ALMACEN))
    assert len(ejecutor.llamadas_de(Frente.NOTICIAS)) == 1  # la del primer turno
    assert caso.cobertura.frentes[Frente.NOTICIAS].cubierto is True
    assert caso.completo is True


def test_fr027_un_informe_que_cita_las_noticias_del_primer_turno_se_rechaza():
    sin_menciones = {
        "comercio": {"identificador": NORTE, "nombre": "x", "verificado": True},
        "recomendacion": "no_habilitar",
        "hallazgos": {
            "noticias": [{"texto": "Sin menciones.", "fuente": FUENTE, "fecha": "2026-09-30"}]
        },
        "conflictos": {"resumen": "Sin conflictos declarados.", "lista": []},
        "cobertura": "completa",
    }
    turno_2 = [
        ("delegar", {"frente": "registro", "identificador": NORTE}),
        ("informe_con", sin_menciones),
    ]
    caso, coordinador, _ = _caso([TURNO_1_D, turno_2], _resultados_d(), SOLICITUD_D)
    asyncio.run(caso.continuar(NORTE))
    (informe,) = coordinador.resultados_de("informe_con")
    assert informe.denegada and "hallazgos.noticias[0].fuente" in informe.texto
    assert coordinador.pasarela.informes == []
    noticias = caso.cobertura.frentes[Frente.NOTICIAS]
    assert noticias.cubierto is False and noticias.causa.value == "otro_comercio"


# ------------------------------------------------- textos sin datos del comercio (FR-022)

TIPOS_DE_REGLA_Y_DECISION = {
    TIPO_BLOQUEO_REGLA,
    TIPO_CIERRE_IMPEDIDO,
    TIPO_ESPERA_ANALISTA,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_COBERTURA_SUSTITUIDA,
    TIPO_DATOS_SUSTITUIDOS,
    TIPO_INFORME_REGISTRADO,
}


def test_los_motivos_eventos_y_cobertura_no_repiten_el_comercio_ni_su_representante():
    # Los eventos `frente_inicio` del #6 llevan a propósito el contexto entregado al subagente: se
    # comprueban los eventos de las reglas y de las decisiones, los motivos y la cobertura.
    turno_2 = [
        (
            "mismo_mensaje",
            [
                ("delegar", {"frente": "registro", "identificador": NORTE}),
                ("delegar", {"frente": "noticias", "identificador": NORTE}),
            ],
        ),
        ("delegar", {"frente": "listas"}),
        ("informe", "no_habilitar"),
        ("terminar",),
    ]
    caso, coordinador, _ = _caso([TURNO_1_D, turno_2], _resultados_d(), SOLICITUD_D)
    asyncio.run(caso.continuar(NORTE))
    textos = [e.detalle for e in caso.eventos() if e.tipo in TIPOS_DE_REGLA_Y_DECISION]
    textos += [r.motivo for r in coordinador.resultados_de("terminar") if r.motivo]
    textos += caso.cobertura.lineas()
    for texto in textos:
        for dato in ("Almacén Mirador Norte SAS", NORTE, "PE-0005", "Gaspar Linares"):
            assert dato not in texto, (dato, texto)
