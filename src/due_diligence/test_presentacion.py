"""Tests de las funciones puras de la interfaz de chat (#11, R2–R6, R9, R12, data-model).

`presentacion.py` convierte la traza y el estado del caso en lo que se ve, sin Streamlit. Los casos
son los de los tickets anteriores, de extremo a extremo simulados: un `Caso` real con subagentes
simulados y un `CoordinadorSimulado` cuyo guion pasa por los hooks. No se llama al modelo.
"""

import ast
import asyncio
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from due_diligence import presentacion

# ----------------------------------------------------------------- casos simulados para los tests


def construir(guiones, resultados, num_turns=None, observador=None):
    """Un `Caso` real con subagentes simulados y un `CoordinadorSimulado` por turnos, sin ejecutar.

    Lo usan también los tests de la aplicación (`test_chat.py`) como fábrica de casos.
    """
    from due_diligence.coordinador import Caso
    from due_diligence.simulacion import CoordinadorSimulado, EjecutorSimulado

    coordinador = CoordinadorSimulado(guiones=guiones, num_turns=num_turns)
    caso = Caso(
        ejecutor=EjecutorSimulado(resultados=resultados),
        consulta=coordinador,
        observador=observador,
    )
    coordinador.caso = caso
    return caso


def resultados_a():
    from due_diligence.frentes import Frente
    from due_diligence.simulacion import (
        comercio_alto_riesgo,
        consulta,
        consulta_listas,
        respuesta_registro,
        respuesta_riesgo,
        resultado_frente,
    )

    categoria = "suplementos dietarios"
    riesgo = respuesta_riesgo(categoria, "alto")
    return {
        Frente.REGISTRO: resultado_frente(
            Frente.REGISTRO,
            [
                consulta(
                    Frente.REGISTRO,
                    {"identificador": "CO-TV-0001"},
                    respuesta_registro(comercio_alto_riesgo()),
                )
            ],
        ),
        Frente.CATEGORIA: resultado_frente(
            Frente.CATEGORIA, [consulta(Frente.CATEGORIA, {"categoria": categoria}, riesgo)]
        ),
        Frente.LISTAS: resultado_frente(
            Frente.LISTAS,
            [
                consulta_listas("comercio", identificador="CO-TV-0001"),
                consulta_listas("persona", identificador="PE-0001"),
            ],
        ),
    }


GUION_A = [
    (
        "delegar_paralelo",
        [
            {"frente": "registro", "identificador": "CO-TV-0001"},
            {"frente": "noticias", "identificador": "CO-TV-0001"},
            {"frente": "categoria", "categoria": "suplementos dietarios"},
        ],
    ),
    ("delegar", {"frente": "listas"}),
    ("escalar", "Revisar el origen de fondos antes de decidir."),
    ("informe", "decide_cumplimiento"),
    ("terminar",),
]
SOLICITUD_A = (
    "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001, "
    "de suplementos dietarios."
)
SOLICITUD_D = "Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios."
TURNO_2_D = [
    ("delegar", {"frente": "registro", "identificador": "CO-AM-0004"}),
    ("delegar", {"frente": "listas"}),
    ("informe", "no_habilitar"),
    ("terminar",),
]


def guiones_d():
    from due_diligence.test_casos_escalamiento import TURNO_1_D

    return [TURNO_1_D, TURNO_2_D]


def resultados_d():
    from due_diligence.test_casos_escalamiento import _resultados_d

    return _resultados_d()


def guion_y_resultados_f():
    from due_diligence.test_casos_cobertura import GUION_F, _resultados_bajo_riesgo
    from due_diligence.test_casos_reglas import SOLICITUD_B

    return GUION_F, _resultados_bajo_riesgo(caida=True), SOLICITUD_B


def caso_a(num_turns=None):
    caso = construir([GUION_A], resultados_a(), num_turns=num_turns)
    asyncio.run(caso.ejecutar(SOLICITUD_A))
    return caso


def caso_d(turnos=1):
    caso = construir(guiones_d(), resultados_d(), num_turns=[3, 4])
    asyncio.run(caso.ejecutar(SOLICITUD_D))
    if turnos == 2:
        asyncio.run(caso.continuar("CO-AM-0004"))
    return caso


def caso_f():
    guion, resultados, solicitud = guion_y_resultados_f()
    caso = construir([guion], resultados)
    asyncio.run(caso.ejecutar(solicitud))
    return caso


@pytest.fixture(autouse=True)
def _sin_caidas(monkeypatch):
    """Los casos simulados no dependen de la caída simulada de la sesión."""
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)
    monkeypatch.delenv("PASARELA_FALLA_NOTICIAS", raising=False)


def _evento(tipo, frente=None, detalle="detalle", regla=None, accion=None, secuencia=1):
    from due_diligence.eventos import Evento

    marca = datetime(2026, 10, 19, 3, 0, 0, tzinfo=UTC)
    return Evento(secuencia, marca, tipo, frente, detalle, regla, accion)


# ------------------------------------------------------------ hora de Colombia (T013, R9, FR-007)


def test_la_hora_se_muestra_en_hora_de_colombia_con_la_zona_declarada():
    marca = datetime(2026, 10, 19, 3, 0, 0, tzinfo=UTC)
    assert presentacion.hora_colombia(marca) == "22:00:00 (hora de Colombia)"


def test_una_marca_en_otra_zona_se_convierte_a_hora_de_colombia():
    madrid = timezone(timedelta(hours=2))
    marca = datetime(2026, 10, 19, 5, 30, 15, tzinfo=madrid)  # 03:30:15 UTC
    assert presentacion.hora_colombia(marca) == "22:30:15 (hora de Colombia)"


# --------------------------------------------- de la traza a los indicadores (T015, R3, FR-002)

DEL_MAPA = {
    "delegacion": "delegacion",
    "bloqueo_regla": "bloqueo",
    "informe_registrado": "informe",
    "escalamiento_registrado": "escalamiento",
    "fallo_de_hook": "aviso",
}


def test_los_frentes_se_nombran_en_palabras():
    from due_diligence.frentes import Frente

    assert [presentacion.frente_en_palabras(f) for f in Frente] == [
        "registro mercantil",
        "listas restrictivas",
        "noticias",
        "riesgo de categoría",
    ]


def test_cada_tipo_del_mapa_da_su_indicador():
    from due_diligence.frentes import Frente

    for secuencia, (tipo, esperado) in enumerate(DEL_MAPA.items(), 1):
        frente = Frente.LISTAS if tipo == "delegacion" else None
        evento = _evento(tipo, frente, "el detalle", "I.1", "una acción", secuencia)
        indicador = presentacion.indicador(evento)
        assert indicador.tipo == esperado
        # La delegación normal no repite el detalle: el título ya nombra el frente.
        assert indicador.detalle == ("" if tipo == "delegacion" else "el detalle")
        assert indicador.hora == "22:00:00 (hora de Colombia)"
        assert indicador.secuencia == secuencia
        assert indicador.titulo


def test_el_indicador_de_delegacion_nombra_el_frente_en_palabras():
    from due_diligence.eventos import TIPO_DELEGACION
    from due_diligence.frentes import Frente

    indicador = presentacion.indicador(_evento(TIPO_DELEGACION, Frente.LISTAS))
    assert indicador.titulo == "Delegación al subagente de listas restrictivas"


def test_el_indicador_de_bloqueo_lleva_la_regla_y_la_accion_intentada():
    from due_diligence.eventos import TIPO_BLOQUEO_REGLA

    accion = "registrar_informe (habilitar)"
    indicador = presentacion.indicador(
        _evento(TIPO_BLOQUEO_REGLA, None, "motivo fijo", "I.3", accion)
    )
    assert indicador.titulo == f"Bloqueado por la regla I.3: {accion}"
    assert indicador.detalle == "motivo fijo"


def test_un_bloqueo_sin_accion_ni_regla_sigue_teniendo_titulo():
    from due_diligence.eventos import TIPO_BLOQUEO_REGLA

    assert presentacion.indicador(_evento(TIPO_BLOQUEO_REGLA, regla="I.1")).titulo == (
        "Bloqueado por la regla I.1"
    )
    assert presentacion.indicador(_evento(TIPO_BLOQUEO_REGLA)).titulo == (
        "Bloqueado por una regla de negocio"
    )


def test_los_demas_tipos_no_son_indicadores():
    from due_diligence.eventos import TIPOS

    assert set(DEL_MAPA) <= TIPOS
    for tipo in sorted(TIPOS - set(DEL_MAPA)):
        assert presentacion.indicador(_evento(tipo)) is None, tipo


def test_los_eventos_se_reparten_por_turno_y_los_del_inicio_van_con_el_primero():
    from due_diligence import eventos as e

    tipos = [
        e.TIPO_CASO_INICIADO,
        e.TIPO_MODO_DEMOSTRACION,
        e.TIPO_MENSAJE_ANALISTA,
        e.TIPO_DELEGACION,
        e.TIPO_TERMINACION,
        e.TIPO_MENSAJE_ANALISTA,
        e.TIPO_INFORME_REGISTRADO,
        e.TIPO_TERMINACION,
    ]
    eventos = [_evento(t, secuencia=n) for n, t in enumerate(tipos, 1)]
    assert [x.secuencia for x in presentacion.eventos_del_turno(eventos, 1)] == [1, 2, 3, 4, 5]
    assert [x.secuencia for x in presentacion.eventos_del_turno(eventos, 2)] == [6, 7, 8]
    assert presentacion.eventos_del_turno(eventos, 3) == []


# ------------------------------------- cobertura, estado y resumen del turno (T015, R4, FR-003)


def test_la_cobertura_tiene_los_cuatro_frentes_en_orden_y_motivo_solo_si_falta():
    filas = presentacion.filas_cobertura(caso_f().cobertura)
    assert [f.frente for f in filas] == [
        "registro mercantil",
        "listas restrictivas",
        "noticias",
        "riesgo de categoría",
    ]
    for fila in filas:
        assert (fila.motivo == "") is fila.cubierto
    (noticias,) = [f for f in filas if f.frente == "noticias"]
    assert noticias.cubierto is False
    assert noticias.motivo == "error de la fuente (el servicio no está disponible)"


def test_el_estado_completo_solo_si_el_caso_esta_completo():
    casos = [caso_a(), caso_d(1), caso_d(2), caso_f()]
    for caso in casos:
        assert (presentacion.estado_mostrado(caso).clase == "completo") is caso.completo
    assert [presentacion.estado_mostrado(c).clase for c in casos] == [
        "completo",
        "esperando",
        "completo",
        "incompleto",
    ]


def test_el_estado_en_espera_dice_que_espera():
    caso = caso_d(1)
    estado = presentacion.estado_mostrado(caso)
    # Dos oraciones: el motivo ya lleva sus dos puntos (validación manual).
    assert estado.texto == (
        "Esperando al analista. El registro devolvió varias coincidencias: el caso espera el "
        "identificador del analista."
    )


def test_el_estado_incompleto_dice_lo_que_falta():
    estado = presentacion.estado_mostrado(caso_f())
    assert estado.texto == "Incompleto: hay frentes sin cubrir."


def test_el_estado_incompleto_junta_todo_lo_que_falta():
    caso = caso_a()
    caso.estado.cierre_sin_escalar = True
    caso.estado.cierre_sin_informe = True
    estado = presentacion.estado_mostrado(caso)
    assert estado.clase == "incompleto"
    assert "terminó sin el escalamiento obligatorio" in estado.texto
    assert "terminó sin el informe vigente" in estado.texto


def test_el_fallo_de_un_hook_gana_a_todo_lo_demas():
    caso = caso_d(1)  # también espera al analista
    caso.estado.libro.fallo_de_hook = "simulado"
    estado = presentacion.estado_mostrado(caso)
    assert estado.clase == "incompleto"
    assert estado.texto == (
        "Incompleto: un control de las reglas falló y el caso se bloqueó por precaución."
    )


def test_una_terminacion_anomala_se_muestra_como_incompleta_con_su_detalle():
    from due_diligence.simulacion import terminacion_anomala

    caso = caso_a()
    caso.estado.terminacion = terminacion_anomala()
    estado = presentacion.estado_mostrado(caso)
    assert estado.clase == "incompleto"
    detalle = caso.estado.terminacion.detalle
    assert estado.texto == f"Incompleto: el turno terminó de forma anómala ({detalle})."


def test_el_resumen_del_turno_del_caso_a_tiene_todos_los_indicadores_en_orden():
    caso = caso_a(num_turns=[3])
    turno = presentacion.resumen_del_turno(caso, 1, SOLICITUD_A)
    esperados = [ev for ev in caso.eventos() if ev.tipo in DEL_MAPA]
    assert esperados  # SC-002: uno por cada evento del mapa, en el orden de la traza
    assert [i.secuencia for i in turno.indicadores] == [ev.secuencia for ev in esperados]
    tipos = [i.tipo for i in turno.indicadores]
    assert tipos.count("delegacion") == 4
    assert tipos.index("escalamiento") < tipos.index("informe")
    assert len(turno.cobertura) == 4
    assert turno.estado.clase == "completo"
    assert turno.respuesta == caso.respuesta
    assert (turno.numero, turno.mensaje, turno.aviso) == (1, SOLICITUD_A, None)
    assert turno.turnos == "3 de 30"


def test_los_turnos_del_resumen_son_los_de_ese_turno_nunca_la_suma():
    caso = caso_d(2)
    assert caso.turnos == 7
    uno = presentacion.resumen_del_turno(caso, 1, SOLICITUD_D)
    dos = presentacion.resumen_del_turno(caso, 2, "CO-AM-0004")
    assert (uno.turnos, dos.turnos) == ("3 de 30", "4 de 30")
    listas = "Delegación al subagente de listas restrictivas"
    # Cada turno lleva solo sus indicadores: listas se delega (y se ejecuta) en el turno 2.
    assert listas not in [i.titulo for i in uno.indicadores]
    assert listas in [i.titulo for i in dos.indicadores]
    # El intento del turno 1 quedó bloqueado por I.1 y se ve como bloqueo.
    assert any(i.tipo == "bloqueo" and "I.1" in i.titulo for i in uno.indicadores)


def test_un_turno_sin_dato_de_turnos_lo_dice():
    caso = caso_a()
    caso.turnos_por_turno = [None]
    assert presentacion.resumen_del_turno(caso, 1, SOLICITUD_A).turnos == "sin dato"
    assert presentacion.resumen_del_turno(caso, 2, "otro").turnos == "sin dato"


def test_el_resumen_acepta_otra_respuesta_y_un_aviso():
    turno = presentacion.resumen_del_turno(caso_a(), 1, SOLICITUD_A, aviso="aviso", respuesta="r")
    assert (turno.aviso, turno.respuesta) == ("aviso", "r")


def test_el_caso_f_muestra_noticias_sin_cubrir_y_el_caso_incompleto():
    turno = presentacion.resumen_del_turno(caso_f(), 1, "solicitud")
    (noticias,) = [f for f in turno.cobertura if f.frente == "noticias"]
    assert noticias.cubierto is False
    assert turno.estado.clase == "incompleto"


def test_los_titulos_de_los_indicadores_no_anaden_datos_del_comercio_ni_de_personas():
    caso = caso_a()
    for indicador in presentacion.resumen_del_turno(caso, 1, SOLICITUD_A).indicadores:
        for dato in ("Tienda Verde", "Lucía Ferrer", "CO-TV-0001", "PE-0001"):
            assert dato not in indicador.titulo


def test_presentacion_no_importa_streamlit():
    arbol = ast.parse(Path(presentacion.__file__).read_text(encoding="utf-8"))
    importados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados |= {a.name.split(".")[0] for a in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module.split(".")[0])
    assert "streamlit" not in importados


# ------------------------------------- el mensaje entrante (T017, R6, FR-001, FR-005, US1-3)


def test_sin_caso_el_mensaje_inicia_uno_nuevo_sin_aviso():
    decision = presentacion.decidir_mensaje(None, "Necesito el due diligence de Taller Aurora SAS.")
    assert decision == presentacion.DecisionMensaje(presentacion.Decision.NUEVO, None)


def test_tras_un_caso_completo_el_mensaje_inicia_uno_nuevo_y_lo_avisa():
    caso = caso_a()
    assert caso.completo
    decision = presentacion.decidir_mensaje(caso, "Otro comercio.")
    assert decision.accion is presentacion.Decision.NUEVO
    assert decision.aviso == presentacion.AVISO_CASO_NUEVO
    assert presentacion.AVISO_CASO_NUEVO == "Caso anterior cerrado; se inició un caso nuevo."


def test_un_caso_incompleto_o_en_espera_se_continua():
    for caso in (caso_f(), caso_d(1)):
        decision = presentacion.decidir_mensaje(caso, "CO-AM-0004")
        assert decision == presentacion.DecisionMensaje(presentacion.Decision.CONTINUAR, None)


@pytest.mark.parametrize("texto", ["", "   ", "\n\t"])
def test_un_mensaje_vacio_con_la_espera_abierta_se_avisa_sin_llamar_al_coordinador(texto):
    caso = caso_d(1)
    decision = presentacion.decidir_mensaje(caso, texto)
    assert decision.accion is presentacion.Decision.AVISO_ESPERA
    assert decision.aviso == presentacion.aviso_espera(caso.espera)
    assert decision.aviso == (
        "El coordinador espera su respuesta. El registro devolvió varias coincidencias: el caso "
        "espera el identificador del analista. El caso sigue sin completar."
    )


@pytest.mark.parametrize("caso", [None, "completo", "incompleto"])
def test_un_mensaje_vacio_sin_espera_se_ignora(caso):
    caso = {None: None, "completo": caso_a(), "incompleto": caso_f()}[caso]
    decision = presentacion.decidir_mensaje(caso, "  ")
    assert decision == presentacion.DecisionMensaje(presentacion.Decision.IGNORAR, None)


def test_los_mensajes_de_fallo_explican_que_hacer_sin_trazas():
    fallo = presentacion.mensaje_fallo_turno(RuntimeError("detalle interno"))
    assert fallo == (
        "El turno falló por un error del sistema (RuntimeError). El caso queda incompleto; puede "
        "escribir de nuevo o iniciar un caso nuevo."
    )
    for mensaje in (fallo, presentacion.MENSAJE_SIN_SESION):
        assert "Traceback" not in mensaje and "detalle interno" not in mensaje
        assert "nuevo" in mensaje


def test_la_linea_de_comandos_expone_el_mismo_mensaje_sin_sesion():
    from due_diligence import __main__ as principal

    assert principal.MENSAJE_SIN_SESION is presentacion.MENSAJE_SIN_SESION


# ------------------------------------------------------- modos activos (T019, R12, FR-010)

NOTICIAS, REGISTRO, DEMO = (
    "PASARELA_FALLA_NOTICIAS",
    "PASARELA_FALLA_REGISTRO",
    "PASARELA_MODO_DEMO_HOOKS",
)


def test_sin_variables_no_hay_modos_activos():
    assert presentacion.modos_activos({}) == []


@pytest.mark.parametrize("variable", [NOTICIAS, REGISTRO, DEMO])
def test_cada_modo_se_activa_solo_con_el_valor_exacto_uno(variable):
    assert len(presentacion.modos_activos({variable: "1"})) == 1
    for valor in ("0", "true", "", " 1", "si"):
        assert presentacion.modos_activos({variable: valor}) == []


def test_los_tres_modos_juntos_en_su_orden():
    modos = presentacion.modos_activos({DEMO: "1", REGISTRO: "1", NOTICIAS: "1"})
    assert modos == [
        "Caída simulada de noticias activa (caso f).",
        "Caída simulada del registro mercantil activa.",
        "Modo de demostración de hooks activo (caso e): las reglas no están en las instrucciones "
        "del coordinador; los hooks siguen activos.",
    ]


def test_el_modo_de_demostracion_coincide_con_el_de_la_configuracion():
    from due_diligence import configuracion

    for valor in ("1", "0", "", "true"):
        entorno = {DEMO: valor}
        activo = any("demostración" in m for m in presentacion.modos_activos(entorno))
        assert activo is configuracion.modo_demostracion(entorno)


# ------------------------------------------------ validación manual: textos que se leen mejor


def test_la_delegacion_normal_no_repite_el_detalle_y_el_reintento_lo_dice_en_palabras():
    # El detalle de la traza dice «Se delega el frente categoria» (nombre interno, sin tilde).
    indicadores = presentacion.resumen_del_turno(caso_f(), 1, "solicitud").indicadores
    delegaciones = [i for i in indicadores if i.tipo == "delegacion"]
    detalles = [i.detalle for i in delegaciones]
    assert "" in detalles
    (reintento,) = [d for d in detalles if d]  # el caso (f) reintenta noticias una vez
    assert reintento == "Reintento con la misma entrada, tras un error que se puede reintentar."
    for indicador in delegaciones:
        assert "categoria" not in indicador.detalle and "Se delega" not in indicador.detalle


def test_volver_a_delegar_con_otra_entrada_lo_dice_sin_el_nombre_interno():
    dos = presentacion.resumen_del_turno(caso_d(2), 2, "CO-AM-0004")
    (registro,) = [
        i for i in dos.indicadores if i.titulo == "Delegación al subagente de registro mercantil"
    ]
    assert registro.detalle == "Se vuelve a delegar con otra entrada."


@pytest.mark.parametrize(
    ("motivo", "esperado"),
    [
        (
            "error de la fuente (servicio_no_disponible)",
            "error de la fuente (el servicio no está disponible)",
        ),
        (
            "error de la fuente (datos_no_disponibles, servicio_no_disponible)",
            "error de la fuente (la fuente no tiene datos disponibles, el servicio no está "
            "disponible)",
        ),
        ("error de la fuente (codigo_desconocido)", "error de la fuente (codigo_desconocido)"),
        (
            "error de la fuente (servicio_no_disponible, codigo_desconocido)",
            "error de la fuente (el servicio no está disponible, codigo_desconocido)",
        ),
        ("no se delegó", "no se delegó"),
    ],
)
def test_la_cobertura_muestra_los_codigos_de_error_conocidos_en_palabras(motivo, esperado):
    from due_diligence.cobertura import CoberturaCaso, CoberturaFrente
    from due_diligence.frentes import Frente

    frentes = {f: CoberturaFrente(f, True, "", None, 0) for f in Frente}
    frentes[Frente.NOTICIAS] = CoberturaFrente(Frente.NOTICIAS, False, motivo, None, 1)
    filas = presentacion.filas_cobertura(CoberturaCaso(frentes, False))
    (noticias,) = [f for f in filas if f.frente == "noticias"]
    assert noticias.motivo == esperado


def test_cada_codigo_conocido_tiene_su_traduccion():
    for codigo, palabras in presentacion.ERRORES_EN_PALABRAS.items():
        assert codigo not in palabras and palabras == palabras.lower()
