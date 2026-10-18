"""Tests del registro de eventos y del estado del caso (R7, data-model, FR-008, FR-009, FR-014)."""

import asyncio
from datetime import UTC, datetime

import pytest

from due_diligence.estado import (
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
    TIPO_CONSULTA_FALLIDA,
    TIPO_DELEGACION,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_FALLO_DE_HOOK,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
    TIPO_MODO_DEMOSTRACION,
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
    }
    assert TIPO_CASO_INICIADO in TIPOS and TIPO_TERMINACION in TIPOS


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
