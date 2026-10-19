"""Tests del registro de eventos y del estado del caso (R7, data-model, FR-008, FR-009, FR-014)."""

import asyncio
from datetime import UTC, datetime

import pytest

from due_diligence.estado import (
    Causa,
    Consulta,
    EstadoCaso,
    ResultadoFrente,
    Situacion,
    TransicionInvalida,
    derivar_comercio,
)
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_CASO_INICIADO,
    TIPO_CIERRE_IMPEDIDO,
    TIPO_CIERRE_SIN_ESCALAR,
    TIPO_COBERTURA_SUSTITUIDA,
    TIPO_CONSULTA_FALLIDA,
    TIPO_DELEGACION,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_FALLO_DE_HOOK,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
    TIPO_FRENTE_REINTENTO,
    TIPO_MODO_DEMOSTRACION,
    TIPO_REINTENTO_DENEGADO,
    TIPO_TERMINACION,
    TIPOS,
    RegistroEventos,
    TipoDeEventoInvalido,
)
from due_diligence.frentes import Frente
from due_diligence.simulacion import comercio_del_registro, respuesta_del_contrato

# ---------------------------------------------------------------- eventos


def test_los_tipos_de_evento_son_los_del_modelo():
    assert TIPOS == {
        "caso_iniciado",
        "delegacion",
        "delegacion_repetida",
        "frente_inicio",
        "frente_fin",
        "frente_rechazado",
        "frente_invalidado",
        "terminacion",
        "bloqueo_regla",
        "cierre_impedido",
        "cierre_sin_escalar",
        "fallo_de_hook",
        "escalamiento_registrado",
        "modo_demostracion",
        "consulta_fallida",
        # Eventos del #8 (data-model, «Eventos nuevos»).
        "frente_reintento",
        "reintento_denegado",
        "cobertura_sustituida",
        # Eventos del #9 (data-model, «Eventos»).
        "informe_registrado",
        "datos_sustituidos",
        "cierre_sin_informe",
        # Eventos del #10 (data-model, «Eventos»).
        "mensaje_analista",
        "espera_analista",
    }
    assert TIPO_CASO_INICIADO in TIPOS and TIPO_TERMINACION in TIPOS


def test_los_tipos_nuevos_del_ticket_8_son_validos():
    registro = RegistroEventos()
    for tipo in (TIPO_FRENTE_REINTENTO, TIPO_REINTENTO_DENEGADO, TIPO_COBERTURA_SUSTITUIDA):
        assert registro.registrar(tipo, Frente.NOTICIAS, "detalle").tipo == tipo
    # El evento se emite antes de que la pasarela acepte la llamada: no puede llamarse «registrada».
    assert "cobertura_registrada" not in TIPOS
    with pytest.raises(TipoDeEventoInvalido):
        registro.registrar("cobertura_registrada")


def test_los_tipos_nuevos_de_los_hooks_son_validos():
    registro = RegistroEventos()
    for tipo in (
        TIPO_BLOQUEO_REGLA,
        TIPO_CIERRE_IMPEDIDO,
        TIPO_CIERRE_SIN_ESCALAR,
        TIPO_FALLO_DE_HOOK,
        TIPO_ESCALAMIENTO_REGISTRADO,
        TIPO_MODO_DEMOSTRACION,
        TIPO_CONSULTA_FALLIDA,
    ):
        assert registro.registrar(tipo).tipo == tipo
    with pytest.raises(TipoDeEventoInvalido):
        registro.registrar("bloqueo_inventado")


def test_el_evento_lleva_la_regla_y_por_defecto_ninguna():
    registro = RegistroEventos()
    sin_regla = registro.registrar(TIPO_DELEGACION, Frente.REGISTRO, "delegado")
    con_regla = registro.registrar(TIPO_BLOQUEO_REGLA, Frente.LISTAS, "motivo", regla="I.1")
    assert sin_regla.regla is None
    assert con_regla.regla == "I.1"
    assert [e.regla for e in registro.eventos()] == [None, "I.1"]
    # Las llamadas posicionales del #6 siguen valiendo: (secuencia, marca, tipo, frente, detalle).
    assert sin_regla.detalle == "delegado"


def test_la_secuencia_crece_desde_uno():
    registro = RegistroEventos()
    primero = registro.registrar(TIPO_CASO_INICIADO)
    segundo = registro.registrar(TIPO_DELEGACION, Frente.REGISTRO, "delegado")
    assert (primero.secuencia, segundo.secuencia) == (1, 2)
    assert segundo.frente is Frente.REGISTRO and segundo.detalle == "delegado"
    assert primero.frente is None


def test_cien_eventos_concurrentes_tienen_secuencias_unicas():
    registro = RegistroEventos()

    async def uno():
        await asyncio.sleep(0)
        registro.registrar(TIPO_FRENTE_INICIO, Frente.NOTICIAS)

    async def todos():
        await asyncio.gather(*(uno() for _ in range(100)))

    asyncio.run(todos())
    secuencias = [e.secuencia for e in registro.eventos()]
    assert sorted(secuencias) == list(range(1, 101))
    assert secuencias == sorted(secuencias)


def test_con_la_misma_marca_el_orden_lo_da_la_secuencia():
    fija = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    registro = RegistroEventos(reloj=lambda: fija)
    for _ in range(5):
        registro.registrar(TIPO_FRENTE_FIN, Frente.REGISTRO)
    eventos = registro.eventos()
    assert {e.marca for e in eventos} == {fija}
    assert [e.secuencia for e in eventos] == [1, 2, 3, 4, 5]


def test_la_marca_es_utc_con_zona():
    evento = RegistroEventos().registrar(TIPO_CASO_INICIADO)
    assert evento.marca.tzinfo is not None
    assert evento.marca.utcoffset().total_seconds() == 0


def test_eventos_devuelve_una_copia():
    registro = RegistroEventos()
    registro.registrar(TIPO_CASO_INICIADO)
    copia = registro.eventos()
    copia.clear()
    assert len(registro.eventos()) == 1


def test_un_tipo_desconocido_se_rechaza():
    with pytest.raises(TipoDeEventoInvalido):
        RegistroEventos().registrar("inventado")


def test_dos_registros_no_comparten_eventos():
    uno, otro = RegistroEventos(), RegistroEventos()
    uno.registrar(TIPO_CASO_INICIADO)
    assert otro.eventos() == []


# ----------------------------------------------------------------- estado


def test_todos_los_frentes_empiezan_sin_iniciar():
    estado = EstadoCaso("solicitud")
    assert {f: estado.situacion(f) for f in Frente} == {f: Situacion.SIN_INICIAR for f in Frente}
    assert estado.comercio is None and estado.terminacion is None
    assert estado.consultas == [] and estado.resultados == {}


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        (Situacion.SIN_INICIAR, Situacion.EN_CURSO),
        (Situacion.EN_CURSO, Situacion.TERMINADO),
        (Situacion.EN_CURSO, Situacion.NO_TERMINADO),
        (Situacion.SIN_INICIAR, Situacion.RECHAZADO),
        (Situacion.RECHAZADO, Situacion.EN_CURSO),
        (Situacion.RECHAZADO, Situacion.RECHAZADO),
        (Situacion.TERMINADO, Situacion.EN_CURSO),
        (Situacion.NO_TERMINADO, Situacion.EN_CURSO),
        (Situacion.TERMINADO, Situacion.NO_TERMINADO),
    ],
)
def test_transiciones_permitidas(origen, destino):
    estado = EstadoCaso("")
    if origen is not Situacion.SIN_INICIAR:
        _llevar_a(estado, Frente.REGISTRO, origen)
    estado.cambiar_situacion(Frente.REGISTRO, destino, "motivo")
    assert estado.situacion(Frente.REGISTRO) is destino


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        (Situacion.SIN_INICIAR, Situacion.TERMINADO),
        (Situacion.SIN_INICIAR, Situacion.NO_TERMINADO),
        (Situacion.EN_CURSO, Situacion.SIN_INICIAR),
        (Situacion.EN_CURSO, Situacion.RECHAZADO),
        (Situacion.NO_TERMINADO, Situacion.TERMINADO),
    ],
)
def test_transiciones_no_permitidas_se_rechazan(origen, destino):
    estado = EstadoCaso("")
    if origen is not Situacion.SIN_INICIAR:
        _llevar_a(estado, Frente.REGISTRO, origen)
    with pytest.raises(TransicionInvalida):
        estado.cambiar_situacion(Frente.REGISTRO, destino)
    assert estado.situacion(Frente.REGISTRO) is origen


def test_el_motivo_queda_con_la_situacion():
    estado = EstadoCaso("")
    estado.cambiar_situacion(Frente.CATEGORIA, Situacion.RECHAZADO, "falta la categoría")
    assert estado.motivo(Frente.CATEGORIA) == "falta la categoría"
    assert estado.motivo(Frente.REGISTRO) == ""


def test_un_frente_sin_terminar_no_tiene_resultado_vacio():
    estado = EstadoCaso("")
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.EN_CURSO)
    assert Frente.NOTICIAS not in estado.resultados
    assert estado.situacion(Frente.NOTICIAS) is Situacion.EN_CURSO


def test_guardar_resultado_y_consultas():
    estado = EstadoCaso("")
    consulta = Consulta(
        frente=Frente.REGISTRO,
        herramienta="mcp__pasarela__consultar_registro_mercantil",
        argumentos={"identificador": "CO-TV-0001"},
        resultado={"resultado": "sin_coincidencias", "hechos": [], "metadatos": {}},
        valido=True,
    )
    resultado = ResultadoFrente(Frente.REGISTRO, [consulta], "resumen", None, "")
    estado.guardar_resultado(resultado)
    estado.agregar_consultas([consulta])
    assert estado.resultados[Frente.REGISTRO] is resultado
    assert estado.consultas == [consulta]
    assert consulta.error is None


def test_instantanea_devuelve_una_copia_independiente():
    estado = EstadoCaso("solicitud")
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    copia = estado.instantanea()
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    estado.registrar_identificacion(
        respuesta_del_contrato("coincidencias", [comercio_del_registro()], ["CO-TV-0001"])
    )
    assert copia.situacion(Frente.REGISTRO) is Situacion.EN_CURSO
    assert copia.comercio is None
    copia.cambiar_situacion(Frente.REGISTRO, Situacion.NO_TERMINADO)
    assert estado.situacion(Frente.REGISTRO) is Situacion.TERMINADO


def test_dos_estados_no_comparten_nada():
    uno, otro = EstadoCaso("a"), EstadoCaso("b")
    uno.cambiar_situacion(Frente.LISTAS, Situacion.RECHAZADO, "x")
    uno.agregar_consultas([_consulta()])
    assert otro.situacion(Frente.LISTAS) is Situacion.SIN_INICIAR
    assert otro.consultas == []


# ---------------------------------------------------------------- errores y causa (#8)


def test_un_frente_no_terminado_sigue_no_terminado_con_el_motivo_nuevo():
    # Listas que falló y después queda invalidado porque el registro cambió de comercio (#8).
    estado = EstadoCaso("")
    _llevar_a(estado, Frente.LISTAS, Situacion.NO_TERMINADO)
    estado.cambiar_situacion(Frente.LISTAS, Situacion.NO_TERMINADO, "el comercio cambió")
    assert estado.situacion(Frente.LISTAS) is Situacion.NO_TERMINADO
    assert estado.motivo(Frente.LISTAS) == "el comercio cambió"


def test_el_estado_empieza_sin_errores_y_no_los_comparte():
    uno, otro = EstadoCaso("a"), EstadoCaso("b")
    assert uno.errores == {} and otro.errores == {}
    uno.errores[Frente.NOTICIAS] = {"causa": Causa.ERROR_DE_FUENTE.value}
    assert otro.errores == {}
    assert uno.instantanea().errores == {Frente.NOTICIAS: {"causa": "error_de_fuente"}}


def test_la_causa_es_un_conjunto_cerrado_de_nueve_valores():
    assert {c.value for c in Causa} == {
        "terminacion_anomala",
        "error_de_fuente",
        "sin_consultas",
        "resultado_invalido",
        "consulta_incompleta",
        "rechazado",
        "cancelado",
        "invalidado",
        "otro_comercio",  # #10, FR-027
    }


# ---------------------------------------------------------------- ayudas


def _consulta():
    return Consulta(
        frente=Frente.NOTICIAS,
        herramienta="mcp__pasarela__buscar_noticias",
        argumentos={"nombre": "Tienda Verde SAS"},
        resultado=None,
        valido=False,
    )


def _llevar_a(estado, frente, destino):
    """Lleva un frente a una situación por transiciones permitidas."""
    if destino is Situacion.RECHAZADO:
        estado.cambiar_situacion(frente, Situacion.RECHAZADO, "motivo")
        return
    estado.cambiar_situacion(frente, Situacion.EN_CURSO)
    if destino in (Situacion.TERMINADO, Situacion.NO_TERMINADO):
        estado.cambiar_situacion(frente, destino)


# ------------------------------------------------------- derivar_comercio (FR-005, FR-013)


def _registro(*contenidos, coincidencias=None, resultado="coincidencias"):
    return respuesta_del_contrato(resultado, list(contenidos), coincidencias)


def test_derivar_comercio_con_una_coincidencia_unica():
    respuesta = _registro(comercio_del_registro(), coincidencias=["CO-TV-0001"])
    comercio, motivo = derivar_comercio(respuesta)
    assert motivo == ""
    assert comercio["identificador"] == "CO-TV-0001"
    assert comercio["representante_legal"]["nombre"] == "Lucía Ferrer Montalvo"


def test_derivar_comercio_sin_representante():
    sin = comercio_del_registro(representante=None)
    comercio, _ = derivar_comercio(_registro(sin, coincidencias=["CO-TV-0001"]))
    assert comercio["representante_legal"] is None


@pytest.mark.parametrize(
    ("resultado", "texto"),
    [
        (None, "forma esperada"),
        ({"hola": 1}, "forma esperada"),
        (
            {"resultado": "sin_coincidencias", "hechos": [], "coincidencias": []},
            "ninguna coincidencia",
        ),
        (
            {"resultado": "coincidencias", "hechos": [], "coincidencias": ["A", "B"]},
            "varias coincidencias",
        ),
        (
            {"resultado": "coincidencias", "hechos": [], "coincidencias": ["A"]},
            "no trae el comercio",
        ),
    ],
)
def test_derivar_comercio_sin_comercio_unico_da_el_motivo(resultado, texto):
    comercio, motivo = derivar_comercio(resultado)
    assert comercio is None and texto in motivo


# ---------------------------------------------------------------- #9: informe y traza


def test_los_tres_eventos_del_9_existen_y_se_registran():
    from due_diligence.eventos import (
        TIPO_CIERRE_SIN_INFORME,
        TIPO_DATOS_SUSTITUIDOS,
        TIPO_INFORME_REGISTRADO,
    )

    assert TIPO_INFORME_REGISTRADO == "informe_registrado"
    assert TIPO_DATOS_SUSTITUIDOS == "datos_sustituidos"
    assert TIPO_CIERRE_SIN_INFORME == "cierre_sin_informe"
    eventos = RegistroEventos()
    for tipo in (TIPO_INFORME_REGISTRADO, TIPO_DATOS_SUSTITUIDOS, TIPO_CIERRE_SIN_INFORME):
        assert tipo in TIPOS
        eventos.registrar(tipo, None, "detalle")
    assert [e.tipo for e in eventos.eventos()] == [
        TIPO_INFORME_REGISTRADO,
        TIPO_DATOS_SUSTITUIDOS,
        TIPO_CIERRE_SIN_INFORME,
    ]


def test_el_evento_lleva_la_accion_intentada_como_ultimo_campo():
    from dataclasses import fields

    from due_diligence.eventos import Evento

    assert [f.name for f in fields(Evento)][-1] == "accion"
    eventos = RegistroEventos(reloj=lambda: datetime(2026, 10, 18, tzinfo=UTC))
    sin = eventos.registrar(TIPO_BLOQUEO_REGLA, None, "motivo", regla="I.2")
    con = eventos.registrar(
        TIPO_BLOQUEO_REGLA, None, "motivo", regla="I.2", accion="registrar_informe (habilitar)"
    )
    assert sin.accion is None
    assert con.accion == "registrar_informe (habilitar)"
    # Las llamadas posicionales del #6 y del #7 siguen valiendo.
    assert eventos.registrar(TIPO_DELEGACION, Frente.REGISTRO, "d", "I.1").regla == "I.1"


def test_el_estado_empieza_sin_informes_ni_comercio_pedido_y_no_los_comparte():
    a, b = EstadoCaso(), EstadoCaso()
    assert a.comercio_pedido is None
    assert a.informes_pendientes == {}
    assert a.informes == []
    assert a.cierre_sin_informe is False
    a.informes_pendientes["x"] = object()
    a.informes.append(object())
    assert b.informes_pendientes == {} and b.informes == []


# ---------------------------------------------------------------- #10: fundamentos (T003)


def test_los_mensajes_del_analista_empiezan_vacios_y_solicitud_es_el_primero():
    estado = EstadoCaso()
    assert estado.mensajes == [] and estado.solicitud == ""
    estado.mensajes.append("primero")
    estado.mensajes.append("segundo")
    assert estado.solicitud == "primero"


def test_solicitud_sigue_aceptando_la_forma_del_6_al_9():
    # Por posición (`EstadoCaso("…")`) y por asignación, como lo usan los tests anteriores.
    assert EstadoCaso("x").mensajes == ["x"]
    estado = EstadoCaso()
    estado.solicitud = "x"
    assert estado.mensajes == ["x"] and estado.solicitud == "x"
    estado.solicitud = "y"  # sustituye el primer mensaje, no añade otro
    assert estado.mensajes == ["y"]


def test_los_mensajes_no_se_comparten_entre_casos():
    a, b = EstadoCaso("a"), EstadoCaso("b")
    a.mensajes.append("otro")
    assert b.mensajes == ["b"]
    assert a.instantanea().mensajes == ["a", "otro"]


def test_el_estado_empieza_sin_categoria_bloqueada_ni_escalamientos_pendientes():
    estado = EstadoCaso()
    assert estado.categoria_bloqueada is False
    assert estado.escalamientos_pendientes == {}


@pytest.mark.parametrize(
    ("resultado", "clase"),
    [
        (None, "invalida"),
        ({"hola": 1}, "invalida"),
        ({"resultado": "otra_cosa", "hechos": [], "coincidencias": []}, "invalida"),
        ({"resultado": "sin_coincidencias", "hechos": [], "coincidencias": []}, "ninguna"),
        ({"resultado": "coincidencias", "hechos": [], "coincidencias": ["A", "B"]}, "varias"),
        ({"resultado": "coincidencias", "hechos": [], "coincidencias": ["A"]}, "invalida"),
    ],
)
def test_clase_de_sin_comercio_unico(resultado, clase):
    from due_diligence.estado import clase_de

    assert clase_de(resultado) == clase


def test_clase_de_unica_y_contradictoria():
    from due_diligence.estado import clase_de

    unica = _registro(comercio_del_registro(), coincidencias=["CO-TV-0001"])
    assert clase_de(unica) == "unica"
    otra_fuente = {**comercio_del_registro(), "nombre": "Tienda Verde Ltda"}
    contradictoria = _registro(comercio_del_registro(), otra_fuente, coincidencias=["CO-TV-0001"])
    assert clase_de(contradictoria) == "contradictoria"
    assert derivar_comercio(contradictoria)[0] is None  # derivar_comercio no cambia


def _registro_terminado_con(estado, *respuestas):
    _llevar_a(estado, Frente.REGISTRO, Situacion.TERMINADO)
    for respuesta in respuestas:
        estado.registrar_identificacion(respuesta)


def test_la_identificacion_guarda_su_clase():
    estado = EstadoCaso()
    _registro_terminado_con(
        estado, _registro(comercio_del_registro(), coincidencias=["CO-TV-0001"])
    )
    assert estado.identificaciones[0].clase == "unica"


def test_clase_identificacion_se_consolida_como_el_comercio():
    estado = EstadoCaso()
    assert estado.clase_identificacion is None  # el registro no terminó
    varias = {"resultado": "coincidencias", "hechos": [], "coincidencias": ["A", "B"]}
    _registro_terminado_con(estado, varias)
    assert estado.clase_identificacion == "varias" and estado.comercio is None


def test_clase_identificacion_es_unica_exactamente_con_comercio():
    estado = EstadoCaso()
    _registro_terminado_con(
        estado, _registro(comercio_del_registro(), coincidencias=["CO-TV-0001"])
    )
    assert estado.clase_identificacion == "unica" and estado.comercio is not None
    # Dos consultas que identifican comercios distintos: hace falta el identificador.
    otro = comercio_del_registro(identificador="CO-TA-0002", nombre="Taller Aurora SAS")
    estado.registrar_identificacion(_registro(otro, coincidencias=["CO-TA-0002"]))
    assert estado.comercio is None and estado.clase_identificacion == "varias"


def test_clase_identificacion_sin_datos_del_registro_terminado_es_invalida():
    estado = EstadoCaso()
    _llevar_a(estado, Frente.REGISTRO, Situacion.TERMINADO)
    assert estado.clase_identificacion == "invalida"


def test_la_causa_otro_comercio_existe():
    assert Causa.OTRO_COMERCIO.value == "otro_comercio"


def test_los_eventos_del_10_existen_y_se_registran():
    from due_diligence.eventos import TIPO_ESPERA_ANALISTA, TIPO_MENSAJE_ANALISTA

    assert TIPO_MENSAJE_ANALISTA == "mensaje_analista"
    assert TIPO_ESPERA_ANALISTA == "espera_analista"
    eventos = RegistroEventos()
    for tipo in (TIPO_MENSAJE_ANALISTA, TIPO_ESPERA_ANALISTA):
        assert tipo in TIPOS
        eventos.registrar(tipo, None, "detalle")
    assert [e.tipo for e in eventos.eventos()] == [TIPO_MENSAJE_ANALISTA, TIPO_ESPERA_ANALISTA]


# ------------------------------------------------- #11: el observador del registro (T006, R1)


def _sin_bloqueo(accion, limite=5.0):
    """Ejecuta `accion` en un hilo con tiempo límite: un bloqueo falla el test y no cuelga nada."""
    import threading

    errores = []

    def ejecutar():
        try:
            accion()
        except BaseException as error:  # el test lo vuelve a lanzar en el hilo principal
            errores.append(error)

    hilo = threading.Thread(target=ejecutar, daemon=True)
    hilo.start()
    hilo.join(timeout=limite)
    assert not hilo.is_alive(), "registrar se bloqueó: el observador se llamó dentro del candado"
    if errores:
        raise errores[0]


def test_el_observador_recibe_cada_evento_en_orden_y_ya_guardado():
    vistos = []
    registro = RegistroEventos(observador=lambda e: vistos.append((e, registro.eventos()[-1])))
    _sin_bloqueo(lambda: registro.registrar(TIPO_CASO_INICIADO, None, "uno"))
    _sin_bloqueo(lambda: registro.registrar(TIPO_DELEGACION, Frente.REGISTRO, "dos"))
    assert [e.detalle for e, _ in vistos] == ["uno", "dos"]
    # Dentro de la llamada, el evento ya está en la traza: se observa después de guardarlo.
    assert all(evento is ultimo for evento, ultimo in vistos)
    assert [e for e, _ in vistos] == registro.eventos()


def test_sin_observador_registrar_no_cambia():
    registro = RegistroEventos()
    evento = registro.registrar(TIPO_CASO_INICIADO, None, "uno")
    assert registro.eventos() == [evento]
    assert evento.secuencia == 1


def test_la_excepcion_del_observador_no_sale_de_registrar_y_el_evento_queda():
    def observador(evento):
        raise RuntimeError("fallo del observador")

    registro = RegistroEventos(observador=observador)
    evento = registro.registrar(TIPO_BLOQUEO_REGLA, None, "motivo", regla="I.1")
    assert registro.eventos() == [evento]


def test_un_observador_que_registra_otro_evento_no_bloquea_y_los_dos_quedan_en_orden():
    def observador(evento):
        if evento.tipo == TIPO_CASO_INICIADO:
            registro.registrar(TIPO_MODO_DEMOSTRACION, None, "desde el observador")

    registro = RegistroEventos(observador=observador)
    _sin_bloqueo(lambda: registro.registrar(TIPO_CASO_INICIADO, None, "primero"))
    eventos = registro.eventos()
    assert [(e.secuencia, e.tipo) for e in eventos] == [
        (1, TIPO_CASO_INICIADO),
        (2, TIPO_MODO_DEMOSTRACION),
    ]


def test_un_observador_que_lee_la_traza_no_bloquea():
    leidos = []
    registro = RegistroEventos(observador=lambda e: leidos.append(len(registro.eventos())))
    _sin_bloqueo(lambda: registro.registrar(TIPO_CASO_INICIADO, None, "uno"))
    assert leidos == [1]
