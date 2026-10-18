"""Caso de prueba obligatorio (f) de la constitución (X), de extremo a extremo (#8; US1-1 a
US1-5, FR-011, FR-013, SC-001).

El servicio de noticias falla como lo hace la pasarela con `PASARELA_FALLA_NOTICIAS=1`: un error
estructurado `servicio_no_disponible`, reintentable, en todas las ejecuciones. Un `Caso` real con
subagentes en sesiones simuladas y un `CoordinadorSimulado` cuyo guion pasa por los hooks del
coordinador. El coordinador simulado declara siempre «cobertura: completa»: lo que se comprueba es
que lo registrado es la cobertura calculada por el código. No se llama al modelo.

Reutiliza los ayudantes de los casos del #7 (`test_casos_reglas.py`) sin modificarlos.
"""

from due_diligence.eventos import (
    TIPO_COBERTURA_SUSTITUIDA,
    TIPO_FRENTE_REINTENTO,
    TIPO_REINTENTO_DENEGADO,
)
from due_diligence.frentes import Frente
from due_diligence.simulacion import (
    comercio_alto_riesgo,
    comercio_bajo_riesgo,
    consulta,
    consulta_listas,
    error_estructurado,
    resultado_frente,
)
from due_diligence.test_casos_reglas import _caso, _delegaciones, _resultados

NOTICIAS = {"frente": "noticias", "identificador": "CO-TA-0002"}
DECLARADA = "completa"


def _noticias_caidas():
    """La respuesta de la pasarela con `PASARELA_FALLA_NOTICIAS=1`, en cada ejecución."""
    error = error_estructurado("servicio_no_disponible", True)
    return resultado_frente(
        Frente.NOTICIAS, [consulta(Frente.NOTICIAS, {"identificador": "CO-TA-0002"}, error=error)]
    )


def _resultados_bajo_riesgo(caida):
    listas = [
        consulta_listas("comercio", identificador="CO-TA-0002"),
        consulta_listas("persona", identificador="PE-0002"),
    ]
    resultados = _resultados(
        [comercio_bajo_riesgo()], "talleres", "bajo", listas, identificador="CO-TA-0002"
    )
    if caida:
        resultados[Frente.NOTICIAS] = _noticias_caidas()
    return resultados


GUION_F = [
    _delegaciones("CO-TA-0002", "talleres"),
    ("delegar", NOTICIAS),  # reintento: el error era reintentable
    ("delegar", NOTICIAS),  # se deniega: se agotó el reintento
    ("delegar", {"frente": "listas"}),
    ("informe", "habilitar"),  # el coordinador simulado declara «cobertura: completa»
    ("terminar",),
]


def _tipos(caso):
    return [e.tipo for e in caso.eventos()]


def test_caso_f_el_informe_se_entrega_y_declara_noticias_no_cubierto():
    caso, coordinador, ejecutor = _caso(GUION_F, _resultados_bajo_riesgo(caida=True))

    (informe,) = coordinador.resultados_de("informe")
    assert informe.ejecutada and not informe.denegada  # el informe se entrega (I.5)
    (registrado,) = coordinador.pasarela.informes
    assert registrado["recomendacion"] == "habilitar"
    # Lo registrado es la cobertura del código, no la «completa» que declaró el coordinador.
    assert registrado["cobertura"] != DECLARADA
    assert registrado["cobertura"] == caso.cobertura.lineas()
    assert registrado["cobertura"][0] == "Cobertura incompleta: 3 de 4 frentes cubiertos."
    assert registrado["cobertura"][3] == (
        "noticias: no cubierto; error de la fuente (servicio_no_disponible); 2 intentos."
    )
    for frente in (Frente.REGISTRO, Frente.LISTAS, Frente.CATEGORIA):
        assert caso.cobertura.frentes[frente].cubierto

    tipos = _tipos(caso)
    assert TIPO_FRENTE_REINTENTO in tipos and TIPO_REINTENTO_DENEGADO in tipos
    assert TIPO_COBERTURA_SUSTITUIDA in tipos
    assert len(ejecutor.llamadas_de(Frente.NOTICIAS)) == 2  # el intento y un reintento
    assert caso.completo is False  # nunca se presenta como completo (I.5)


def test_caso_f_la_caida_de_noticias_no_cambia_los_demas_frentes():
    caido, _, _ = _caso(GUION_F, _resultados_bajo_riesgo(caida=True))
    contraste, _, _ = _caso(GUION_F, _resultados_bajo_riesgo(caida=False))
    for frente in (Frente.REGISTRO, Frente.LISTAS, Frente.CATEGORIA):
        assert caido.estado.situacion(frente) is contraste.estado.situacion(frente)
        assert caido.estado.resultados[frente].consultas == (
            contraste.estado.resultados[frente].consultas
        )


def test_sin_la_caida_la_cobertura_es_completa_y_no_hay_reintentos():
    caso, coordinador, _ = _caso(GUION_F, _resultados_bajo_riesgo(caida=False))
    (registrado,) = coordinador.pasarela.informes
    assert registrado["cobertura"][0] == "Cobertura completa: 4 de 4 frentes cubiertos."
    assert caso.cobertura.completa and caso.completo is True
    assert TIPO_FRENTE_REINTENTO not in _tipos(caso)


def test_el_escalamiento_con_noticias_caido_registra_la_cobertura_del_codigo():
    escalamiento = {
        "comercio": {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS"},
        "hallazgos": {},
        "cobertura": DECLARADA,
        "causa_escalamiento": "categoría de alto riesgo",
        "accion_recomendada": "decide un oficial de cumplimiento",
    }
    guion = [
        _delegaciones("CO-TV-0001", "suplementos dietarios"),
        ("delegar", {"frente": "listas"}),
        ("escalar_con", escalamiento),
        ("informe", "decide_cumplimiento"),
        ("terminar",),
    ]
    listas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("persona", identificador="PE-0001"),
    ]
    resultados = _resultados(
        [comercio_alto_riesgo()], "suplementos dietarios", "alto", listas, "CO-TV-0001"
    )
    resultados[Frente.NOTICIAS] = _noticias_caidas()
    caso, coordinador, _ = _caso(guion, resultados)

    (escalado,) = coordinador.pasarela.escalamientos
    assert escalado["cobertura"] == caso.cobertura.lineas()
    assert escalado["cobertura"][0] == "Cobertura incompleta: 3 de 4 frentes cubiertos."
    # El resto del escalamiento llega intacto.
    assert {k: v for k, v in escalado.items() if k != "cobertura"} == {
        k: v for k, v in escalamiento.items() if k != "cobertura"
    }
    assert coordinador.pasarela.informes[0]["cobertura"] == caso.cobertura.lineas()
    assert caso.completo is False
