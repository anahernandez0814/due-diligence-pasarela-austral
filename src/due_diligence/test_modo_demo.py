"""Tests del modo de demostración y de las instrucciones del coordinador (R11, FR-014, FR-019).

`PASARELA_MODO_DEMO_HOOKS=1` quita del prompt del coordinador la regla 3 y la instrucción de
escalar, para que el modelo pueda intentar lo prohibido; los hooks no cambian. Aquí un coordinador
simulado intenta las tres acciones en modo de demostración y los hooks las bloquean. Ningún test
llama al modelo.
"""

import asyncio

import pytest

from due_diligence import configuracion
from due_diligence.contexto import instrucciones
from due_diligence.coordinador import (
    _REGLA_FALLOS,
    INSTRUCCIONES_COORDINADOR,
    Caso,
    instrucciones_coordinador,
)
from due_diligence.eventos import TIPO_BLOQUEO_REGLA, TIPO_CASO_INICIADO, TIPO_MODO_DEMOSTRACION
from due_diligence.frentes import Frente
from due_diligence.simulacion import (
    CoordinadorSimulado,
    EjecutorSimulado,
    comercio_alto_riesgo,
    comercio_con_representante_en_listas,
    comercios_parecidos,
    consulta,
    consulta_listas,
    respuesta_listas,
    respuesta_registro,
    respuesta_riesgo,
    resultado_frente,
)

DEMO = {configuracion.VARIABLE_MODO_DEMO: "1"}

REGLA_3 = "Si el registro devuelve varias coincidencias, no elijas una ni sigas con listas"
ESCALAR = "llama a escalar_a_cumplimiento"
CUANDO_ESCALADO = "la recomendación es decide_cumplimiento"
TRES_VALORES = "exactamente habilitar, no_habilitar o decide_cumplimiento"


# ------------------------------------------------------------------ las instrucciones


def test_con_demo_inactiva_las_instrucciones_son_las_normales():
    assert instrucciones_coordinador(demo=False) == INSTRUCCIONES_COORDINADOR
    assert REGLA_3 in INSTRUCCIONES_COORDINADOR and ESCALAR in INSTRUCCIONES_COORDINADOR


def test_con_demo_activa_se_quitan_la_regla_3_y_la_instruccion_de_escalar():
    texto = instrucciones_coordinador(demo=True)
    assert REGLA_3 not in texto
    assert ESCALAR not in texto and CUANDO_ESCALADO not in texto
    assert "varias coincidencias" not in texto


def test_con_demo_activa_se_conservan_la_delegacion_el_resumen_y_el_registro_del_informe():
    texto = instrucciones_coordinador(demo=True)
    assert "delegar_frente" in texto and "en la misma respuesta" in texto
    assert "Después delega listas: usa el comercio que devolvió el registro" in texto
    assert "resume al analista, frente por frente" in texto
    assert "registra el informe con registrar_informe" in texto
    assert TRES_VALORES in texto  # el modelo puede intentar registrar el informe
    assert "No decidas la habilitación" not in texto
    assert "de usted" in texto


def test_la_numeracion_de_las_reglas_sigue_siendo_contigua_en_los_dos_modos():
    for demo in (False, True):
        lineas = [
            linea
            for linea in instrucciones_coordinador(demo=demo).splitlines()
            if linea[:1].isdigit()
        ]
        numeros = [int(linea.split(".", 1)[0]) for linea in lineas]
        assert numeros == list(range(1, len(numeros) + 1))


def test_la_regla_de_fallos_esta_en_los_dos_modos_y_no_trae_reglas_de_negocio():
    # #8, R7: no es una de las reglas I.1 a I.3 que el modo de demostración quita.
    for demo in (False, True):
        texto = instrucciones_coordinador(demo=demo)
        assert _REGLA_FALLOS in texto
        assert REGLA_3 not in _REGLA_FALLOS and ESCALAR not in _REGLA_FALLOS
    demo = instrucciones_coordinador(demo=True)
    assert REGLA_3 not in demo and ESCALAR not in demo and CUANDO_ESCALADO not in demo


# ------------------------------------------------------------------ el caso y el evento


def test_un_caso_con_la_variable_en_uno_usa_las_instrucciones_de_demo_y_deja_el_evento():
    caso = Caso(entorno=DEMO, consulta=CoordinadorSimulado([]))
    assert caso.opciones_coordinador().system_prompt == instrucciones_coordinador(demo=True)
    asyncio.run(caso.ejecutar("solicitud"))
    tipos = [e.tipo for e in caso.eventos()]
    assert tipos[:2] == [TIPO_CASO_INICIADO, TIPO_MODO_DEMOSTRACION]
    evento = caso.eventos()[1]
    assert "los hooks siguen activos" in evento.detalle and evento.regla is None


@pytest.mark.parametrize("valor", [None, "0", "true", "", "11"])
def test_con_otro_valor_o_sin_la_variable_es_el_modo_normal_y_no_deja_evento(valor):
    entorno = {} if valor is None else {configuracion.VARIABLE_MODO_DEMO: valor}
    caso = Caso(entorno=entorno, consulta=CoordinadorSimulado([]))
    assert caso.opciones_coordinador().system_prompt == INSTRUCCIONES_COORDINADOR
    asyncio.run(caso.ejecutar("solicitud"))
    assert TIPO_MODO_DEMOSTRACION not in [e.tipo for e in caso.eventos()]


def test_las_instrucciones_de_los_subagentes_no_cambian_con_la_demo():
    normal = Caso(entorno={}, consulta=CoordinadorSimulado([]))
    demo = Caso(entorno=DEMO, consulta=CoordinadorSimulado([]))
    for frente in Frente:
        esperado = instrucciones(frente)
        assert normal._opciones_subagente(frente).system_prompt == esperado
        assert demo._opciones_subagente(frente).system_prompt == esperado


# ------------------------------------------------------------------ los hooks no cambian


def _matchers(opciones):
    return {e: [m.matcher for m in lista] for e, lista in (opciones.hooks or {}).items()}


@pytest.mark.parametrize("entorno", [{}, DEMO, {configuracion.VARIABLE_MODO_DEMO: "0"}])
def test_los_hooks_son_los_mismos_con_y_sin_demo(entorno):
    referencia = Caso(entorno={}, consulta=CoordinadorSimulado([]))
    caso = Caso(entorno=entorno, consulta=CoordinadorSimulado([]))
    assert _matchers(caso.opciones_coordinador()) == _matchers(referencia.opciones_coordinador())
    for frente in Frente:
        assert _matchers(caso._opciones_subagente(frente)) == _matchers(
            referencia._opciones_subagente(frente)
        )
    assert _matchers(caso.opciones_coordinador())["Stop"] == [None]


def test_no_hay_ninguna_forma_de_desactivar_los_hooks():
    import inspect

    from due_diligence.coordinador import ejecutar_caso

    for objetivo in (Caso.__init__, ejecutar_caso):
        assert "hooks" not in inspect.signature(objetivo).parameters
    assert not hasattr(configuracion, "DESACTIVAR_HOOKS")


# ------------------------------------------------------------------ las tres acciones, en demo


def _caso_en_demo(guion, comercios, categoria=None, nivel=None, listas=None, identificador=None):
    argumentos = {"identificador": identificador} if identificador else {"nombre": "x"}
    resultados = {
        Frente.REGISTRO: resultado_frente(
            Frente.REGISTRO, [consulta(Frente.REGISTRO, argumentos, respuesta_registro(*comercios))]
        )
    }
    if categoria:
        resultados[Frente.CATEGORIA] = resultado_frente(
            Frente.CATEGORIA,
            [
                consulta(
                    Frente.CATEGORIA, {"categoria": categoria}, respuesta_riesgo(categoria, nivel)
                )
            ],
        )
    if listas:
        resultados[Frente.LISTAS] = resultado_frente(Frente.LISTAS, listas)
    coordinador = CoordinadorSimulado(guion)
    caso = Caso(
        entorno=DEMO, ejecutor=EjecutorSimulado(resultados=resultados), consulta=coordinador
    )
    coordinador.caso = caso
    asyncio.run(caso.ejecutar("solicitud"))
    return caso, coordinador


def test_en_demo_delegar_listas_sin_registro_identificado_lo_bloquea_el_hook():
    guion = [
        ("delegar", {"frente": "registro", "nombre": "Almacén Mirador"}),
        ("delegar", {"frente": "listas"}),  # sin la regla 3 en el prompt, el modelo lo intenta
        ("terminar",),
    ]
    caso, coordinador = _caso_en_demo(guion, comercios_parecidos())
    delegacion = coordinador.resultados_de("delegar")[1]
    assert delegacion.denegada and not delegacion.ejecutada
    bloqueos = [e for e in caso.eventos() if e.tipo == TIPO_BLOQUEO_REGLA]
    assert [e.regla for e in bloqueos] == ["I.1"]
    assert caso.completo is False


def test_en_demo_registrar_un_informe_que_habilita_a_un_alto_riesgo_lo_rechaza_el_hook():
    guion = [
        (
            "delegar_paralelo",
            [
                {"frente": "registro", "identificador": "CO-TV-0001"},
                {"frente": "categoria", "categoria": "suplementos dietarios"},
            ],
        ),
        ("delegar", {"frente": "listas"}),
        ("informe", "habilitar"),
        ("terminar",),  # y sin escalar tampoco se le deja terminar
    ]
    listas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("persona", identificador="PE-0001"),
    ]
    caso, coordinador = _caso_en_demo(
        guion, [comercio_alto_riesgo()], "suplementos dietarios", "alto", listas, "CO-TV-0001"
    )
    assert coordinador.resultados_de("informe")[0].denegada
    assert coordinador.pasarela.informes == []
    assert coordinador.resultados_de("terminar")[0].termino is False


def test_en_demo_registrar_un_informe_que_habilita_con_coincidencia_lo_rechaza_el_hook():
    guion = [
        (
            "delegar_paralelo",
            [
                {"frente": "registro", "identificador": "CO-PL-0003"},
                {"frente": "categoria", "categoria": "panaderías"},
            ],
        ),
        ("delegar", {"frente": "listas"}),
        ("informe", "habilitar"),
        ("terminar",),
    ]
    listas = [
        consulta_listas("comercio", identificador="CO-PL-0003"),
        consulta(
            Frente.LISTAS,
            {"tipo": "persona", "identificador": "PE-0003"},
            respuesta_listas(
                {"tipo": "persona", "nombre": "(ficticio)", "identificador": "PE-0003"}
            ),
        ),
    ]
    caso, coordinador = _caso_en_demo(
        guion, [comercio_con_representante_en_listas()], "panaderías", "bajo", listas, "CO-PL-0003"
    )
    assert coordinador.resultados_de("informe")[0].denegada
    assert coordinador.resultados_de("terminar")[0].termino is False
    assert coordinador.pasarela.informes == []


def test_en_demo_terminar_sin_escalar_lo_impide_el_hook_de_fin_de_turno():
    guion = [
        (
            "delegar_paralelo",
            [
                {"frente": "registro", "identificador": "CO-TV-0001"},
                {"frente": "categoria", "categoria": "suplementos dietarios"},
            ],
        ),
        ("terminar",),
    ]
    caso, coordinador = _caso_en_demo(
        guion, [comercio_alto_riesgo()], "suplementos dietarios", "alto", None, "CO-TV-0001"
    )
    cierre = coordinador.resultados_de("terminar")[0]
    assert cierre.termino is False and "categoría de alto riesgo" in cierre.motivo
