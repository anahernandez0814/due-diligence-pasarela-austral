"""Casos de prueba obligatorios (a), (b), (c) y (e) de la constitución (X), de extremo a extremo.

Un `Caso` real con subagentes en sesiones simuladas y un `CoordinadorSimulado` cuyo guion pasa por
los hooks del coordinador (`delegar_frente`, `registrar_informe`, `escalar_a_cumplimiento` y el
`Stop`), con los datos ficticios del #5. No se llama al modelo: validan que las reglas I.1, I.2 e
I.3 las hacen cumplir los hooks, no lo que decidiría el modelo.
"""

import asyncio
import json

from due_diligence import configuracion
from due_diligence.coordinador import Caso
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_CIERRE_IMPEDIDO,
    TIPO_CIERRE_SIN_ESCALAR,
    TIPO_CONSULTA_FALLIDA,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_FALLO_DE_HOOK,
)
from due_diligence.frentes import FRENTES, Frente
from due_diligence.libro import Escalamiento
from due_diligence.simulacion import (
    CoordinadorSimulado,
    EjecutorSimulado,
    PasarelaSimulada,
    SesionSimulada,
    comercio_alto_riesgo,
    comercio_bajo_riesgo,
    comercio_con_representante_en_listas,
    comercios_parecidos,
    consulta,
    consulta_listas,
    respuesta_listas,
    respuesta_registro,
    respuesta_riesgo,
    resultado_frente,
)

SOLICITUD = (
    "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren "
    "procesar ventas en línea de suplementos dietarios y estiman unos $80.000.000 mensuales. "
    "¿Lo podemos habilitar esta semana?"
)

LISTAS = FRENTES[Frente.LISTAS].herramienta_completa


def _resultados(comercios, categoria=None, nivel=None, listas=None, identificador=None):
    """Lo que devolverían los subagentes: el registro, la categoría y, si se da, las listas."""
    argumentos = {"identificador": identificador} if identificador else {"nombre": "x"}
    resultados = {
        Frente.REGISTRO: resultado_frente(
            Frente.REGISTRO,
            [consulta(Frente.REGISTRO, argumentos, respuesta_registro(*comercios))],
        )
    }
    if categoria is not None:
        resultados[Frente.CATEGORIA] = resultado_frente(
            Frente.CATEGORIA,
            [
                consulta(
                    Frente.CATEGORIA, {"categoria": categoria}, respuesta_riesgo(categoria, nivel)
                )
            ],
        )
    if listas is not None:
        resultados[Frente.LISTAS] = resultado_frente(Frente.LISTAS, listas)
    return resultados


def _caso(guion, resultados):
    coordinador = CoordinadorSimulado(guion)
    ejecutor = EjecutorSimulado(resultados=resultados)
    caso = Caso(ejecutor=ejecutor, consulta=coordinador)
    coordinador.caso = caso
    asyncio.run(caso.ejecutar(SOLICITUD))
    return caso, coordinador, ejecutor


def _delegaciones(identificador, categoria=None):
    entradas = [
        {"frente": "registro", "identificador": identificador},
        {"frente": "noticias", "identificador": identificador},
    ]
    if categoria:
        entradas.append({"frente": "categoria", "categoria": categoria})
    return ("delegar_paralelo", entradas)


def _bloqueos(caso):
    return [e for e in caso.eventos() if e.tipo == TIPO_BLOQUEO_REGLA]


def _sin_datos_consultados(caso, *datos):
    """Los eventos de las reglas (FR-016) no repiten nombres ni identificadores consultados.

    Solo los eventos de los hooks: el `frente_inicio` del #6 registra a propósito el contexto que
    se entregó a cada subagente.
    """
    del_hook = {
        TIPO_BLOQUEO_REGLA,
        TIPO_CIERRE_IMPEDIDO,
        TIPO_CIERRE_SIN_ESCALAR,
        TIPO_ESCALAMIENTO_REGISTRADO,
        TIPO_FALLO_DE_HOOK,
        TIPO_CONSULTA_FALLIDA,
    }
    texto = json.dumps(
        [(e.detalle, e.regla) for e in caso.eventos() if e.tipo in del_hook], ensure_ascii=False
    )
    for dato in datos:
        assert dato not in texto, dato


# ------------------------------------------------------------------ (a) alto riesgo a un oficial


def test_caso_a_un_comercio_de_alto_riesgo_nunca_se_habilita_y_va_a_un_oficial():
    guion = [
        _delegaciones("CO-TV-0001", "suplementos dietarios"),
        ("delegar", {"frente": "listas"}),
        ("informe", "habilitar"),  # el modelo intenta habilitar
        ("terminar",),  # e intenta cerrar sin escalar
        ("escalar",),
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
    caso, coordinador, _ = _caso(guion, resultados)

    informes = coordinador.resultados_de("informe")
    assert informes[0].denegada and not informes[0].ejecutada
    assert "decisión es de un oficial de cumplimiento" in informes[0].motivo
    cierres = coordinador.resultados_de("terminar")
    assert cierres[0].termino is False  # el primer intento de cerrar se impide
    assert "categoría de alto riesgo" in cierres[0].motivo
    assert coordinador.resultados_de("escalar")[0].ejecutada
    assert informes[1].ejecutada and not informes[1].denegada
    assert cierres[1].termino is True

    pasarela = coordinador.pasarela
    assert len(pasarela.escalamientos) == 1 and len(pasarela.informes) == 1
    assert pasarela.informes[0]["recomendacion"] == "decide_cumplimiento"
    assert caso.estado.libro.escalamientos == [
        Escalamiento(frozenset({"alto_riesgo"}), ("CO-TV-0001", "Tienda Verde SAS", True))
    ]
    assert caso.estado.cierre_sin_escalar is False
    assert caso.completo is True  # los cuatro frentes terminaron y el cierre fue normal

    assert {e.regla for e in _bloqueos(caso)} == {"I.3"}
    tipos = [e.tipo for e in caso.eventos()]
    assert TIPO_CIERRE_IMPEDIDO in tipos and TIPO_ESCALAMIENTO_REGISTRADO in tipos
    _sin_datos_consultados(caso, "PE-0001", "Lucía")


def test_caso_a_ni_sin_categoria_determinada_se_puede_habilitar():
    guion = [
        _delegaciones("CO-TV-0001"),  # el analista no dio categoría: el frente no se delegó
        ("delegar", {"frente": "listas"}),
        ("informe", "habilitar"),
        ("terminar",),
    ]
    listas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("persona", identificador="PE-0001"),
    ]
    resultados = _resultados([comercio_alto_riesgo()], listas=listas, identificador="CO-TV-0001")
    caso, coordinador, _ = _caso(guion, resultados)
    habilitar = coordinador.resultados_de("informe")[0]
    assert habilitar.denegada and "La categoría del caso no quedó determinada" in habilitar.motivo
    assert coordinador.pasarela.informes == []
    assert caso.completo is False  # el frente de categoría nunca se delegó


# ------------------------------------------------------------------ (b) bajo riesgo sin hallazgos


def test_caso_b_un_comercio_de_bajo_riesgo_sin_hallazgos_se_habilita_sin_escalar():
    guion = [
        _delegaciones("CO-TA-0002", "talleres"),
        ("delegar", {"frente": "listas"}),
        ("informe", "habilitar"),
        ("terminar",),
    ]
    listas = [
        consulta_listas("comercio", identificador="CO-TA-0002"),
        consulta_listas("persona", identificador="PE-0002"),
    ]
    resultados = _resultados(
        [comercio_bajo_riesgo()], "talleres", "bajo", listas, identificador="CO-TA-0002"
    )
    caso, coordinador, _ = _caso(guion, resultados)

    informe = coordinador.resultados_de("informe")[0]
    assert informe.ejecutada and not informe.denegada
    assert coordinador.resultados_de("terminar")[0].termino is True  # sin escalar
    assert coordinador.pasarela.escalamientos == []
    assert coordinador.pasarela.informes[0]["recomendacion"] == "habilitar"
    assert _bloqueos(caso) == []
    assert caso.estado.libro.coincidencias == [] and caso.estado.libro.escalamientos == []
    assert caso.estado.cierre_sin_escalar is False
    assert caso.completo is True


# ------------------------------------------------------------------ (c) representante en listas


def _listas_con_el_representante_en_listas():
    return [
        consulta_listas("comercio", identificador="CO-PL-0003"),
        consulta(
            Frente.LISTAS,
            {"tipo": "persona", "identificador": "PE-0003"},
            respuesta_listas(
                {"tipo": "persona", "nombre": "(ficticio)", "identificador": "PE-0003"}
            ),
        ),
    ]


def test_caso_c_el_representante_con_coincidencia_impide_habilitar_y_exige_escalar():
    guion = [
        _delegaciones("CO-PL-0003", "panaderías"),
        ("delegar", {"frente": "listas"}),
        ("informe", "habilitar"),
        ("terminar",),
        ("escalar",),
        ("informe", "no_habilitar"),
        ("terminar",),
    ]
    resultados = _resultados(
        [comercio_con_representante_en_listas()],
        "panaderías",
        "bajo",
        _listas_con_el_representante_en_listas(),
        "CO-PL-0003",
    )
    caso, coordinador, _ = _caso(guion, resultados)

    assert [c.causa for c in caso.estado.libro.coincidencias] == ["coincidencia_representante"]
    informes = coordinador.resultados_de("informe")
    assert informes[0].denegada and "no se puede recomendar habilitar" in informes[0].motivo
    cierres = coordinador.resultados_de("terminar")
    assert cierres[0].termino is False
    assert "coincidencia del representante legal" in cierres[0].motivo
    assert informes[1].ejecutada and cierres[1].termino is True
    assert coordinador.pasarela.informes[0]["recomendacion"] == "no_habilitar"
    assert len(coordinador.pasarela.escalamientos) == 1
    assert {e.regla for e in _bloqueos(caso)} == {"I.2"}
    _sin_datos_consultados(caso, "PE-0003", "Ernesto", "CO-PL-0003", "Panadería")


def test_caso_c_habilitar_sigue_rechazado_aunque_se_escale():
    guion = [
        _delegaciones("CO-PL-0003", "panaderías"),
        ("delegar", {"frente": "listas"}),
        ("escalar",),
        ("informe", "habilitar"),
        ("informe", "decide_cumplimiento"),
        ("terminar",),
    ]
    resultados = _resultados(
        [comercio_con_representante_en_listas()],
        "panaderías",
        "bajo",
        _listas_con_el_representante_en_listas(),
        "CO-PL-0003",
    )
    caso, coordinador, _ = _caso(guion, resultados)
    habilitar, aceptado = coordinador.resultados_de("informe")
    assert habilitar.denegada and aceptado.ejecutada
    assert coordinador.pasarela.informes[0]["recomendacion"] == "decide_cumplimiento"
    assert caso.completo is True


# ------------------------------------------------------------------ (e) listas sin identificación


def test_caso_e_nombres_casi_identicos_bloquean_listas_y_su_herramienta_no_se_ejecuta():
    guion = [
        ("delegar", {"frente": "registro", "nombre": "Almacén Mirador"}),
        ("delegar", {"frente": "listas"}),  # el modelo intenta seguir con listas
        ("delegar", {"frente": "listas"}),  # e insiste
        ("terminar",),
    ]
    resultados = _resultados(comercios_parecidos())
    caso, coordinador, ejecutor = _caso(guion, resultados)

    primero, segundo = coordinador.resultados_de("delegar")[1:]
    for delegacion in (primero, segundo):
        assert delegacion.denegada and not delegacion.ejecutada
        assert "varias coincidencias" in delegacion.motivo
        assert "pida el identificador al analista" in delegacion.motivo
    assert ejecutor.llamadas_de(Frente.LISTAS) == []  # el subagente de listas no se lanzó
    assert caso.estado.comercio is None
    assert caso.completo is False  # listas nunca corrió: no se presenta como completo
    assert [(e.tipo, e.regla) for e in _bloqueos(caso)] == [(TIPO_BLOQUEO_REGLA, "I.1")] * 2
    _sin_datos_consultados(caso, "CO-AM-0004", "CO-AM-0005", "Almacén")


def test_caso_e_un_subagente_de_listas_que_lo_intenta_igual_es_bloqueado_por_su_hook():
    # Aunque la delegación no existiera, la consulta misma se bloquea y la fuente no se consulta.
    guion = [("delegar", {"frente": "registro", "nombre": "Almacén Mirador"}), ("terminar",)]
    caso, coordinador, _ = _caso(guion, _resultados(comercios_parecidos()))
    pasarela: PasarelaSimulada = coordinador.pasarela
    opciones = caso._opciones_subagente(Frente.LISTAS)
    sesion = SesionSimulada(opciones, pasarela.herramientas)
    for consulta_ajena in (
        {"tipo": "comercio", "identificador": "CO-AM-0004"},
        {"tipo": "comercio", "nombre": "Almacén Mirador SAS"},
        {"tipo": "persona", "nombre": "Renata Olmedo Sáenz"},
    ):
        intento = asyncio.run(sesion.llamar(LISTAS, consulta_ajena))
        assert intento.denegada and not intento.ejecutada
    assert [f for f, _ in pasarela.consultas_a_fuentes if f == "listas"] == []
    assert len(_bloqueos(caso)) == 3 and {e.regla for e in _bloqueos(caso)} == {"I.1"}


def test_caso_e_con_el_registro_sin_coincidencias_tampoco_se_consulta_listas():
    guion = [
        ("delegar", {"frente": "registro", "identificador": "CO-XX-0000"}),
        ("delegar", {"frente": "listas"}),
        ("terminar",),
    ]
    caso, coordinador, ejecutor = _caso(guion, _resultados([]))
    delegacion = coordinador.resultados_de("delegar")[1]
    assert delegacion.denegada and "no devolvió coincidencias" in delegacion.motivo
    assert ejecutor.llamadas_de(Frente.LISTAS) == []


# ---------------------------------------------------- el modo de las reglas no depende de la sesión


def test_el_caso_sigue_siendo_el_mismo_con_el_limite_de_devoluciones_agotado():
    guion = [
        _delegaciones("CO-PL-0003", "panaderías"),
        ("delegar", {"frente": "listas"}),
        *[("terminar",)] * (configuracion.MAX_CIERRES_IMPEDIDOS + 1),
        ("informe", "habilitar"),
    ]
    resultados = _resultados(
        [comercio_con_representante_en_listas()],
        "panaderías",
        "bajo",
        _listas_con_el_representante_en_listas(),
        "CO-PL-0003",
    )
    caso, coordinador, _ = _caso(guion, resultados)
    cierres = coordinador.resultados_de("terminar")
    assert [c.termino for c in cierres] == [False] * configuracion.MAX_CIERRES_IMPEDIDOS + [True]
    assert caso.estado.cierre_sin_escalar is True and caso.completo is False
    assert coordinador.pasarela.escalamientos == []  # el escalamiento depende del modelo
    assert coordinador.resultados_de("informe")[0].denegada  # y habilitar sigue sin poder
