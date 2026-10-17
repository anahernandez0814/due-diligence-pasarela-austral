"""Tests del punto de entrada manual (contrato `caso.md`, R8, Q6).

El caso se ejecuta con un coordinador y un ejecutor simulados: nada llama al modelo ni carga el
entorno real (`cargar_entorno` se parchea).
"""

import asyncio
from datetime import UTC, datetime, timedelta

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from due_diligence import __main__ as principal
from due_diligence import configuracion
from due_diligence.coordinador import Caso
from due_diligence.eventos import (
    TIPO_DELEGACION,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
    RegistroEventos,
)
from due_diligence.frentes import Frente
from due_diligence.simulacion import EjecutorSimulado, resultado_frente


def _fin(stop_reason="end_turn", coste=0.5):
    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="sesion-de-prueba",
        stop_reason=stop_reason,
        total_cost_usd=coste,
        terminal_reason="completed",
    )


def _ejecutar_caso_simulado(fin, llamadas):
    async def falso(solicitud):
        referencia = {}

        async def consulta(*, prompt, options=None):
            delegador = referencia["caso"].delegador
            await asyncio.gather(
                delegador.delegar({"frente": "registro", "identificador": "CO-TV-0001"}),
                delegador.delegar({"frente": "noticias", "identificador": "CO-TV-0001"}),
            )
            yield AssistantMessage(
                content=[TextBlock("Resumen para el analista.")], model="simulado"
            )
            yield fin

        noticias = resultado_frente(Frente.NOTICIAS)
        noticias.coste_usd = 0.01
        caso = Caso(
            ejecutor=EjecutorSimulado(retardo=0.01, resultados={Frente.NOTICIAS: noticias}),
            consulta=consulta,
        )
        referencia["caso"] = caso
        llamadas.append("ejecutar_caso")
        await caso.ejecutar(solicitud)
        return caso

    return falso


def test_sin_solicitud_muestra_el_uso_y_no_carga_el_entorno(monkeypatch, capsys):
    cargas = []
    monkeypatch.setattr(configuracion, "cargar_entorno", lambda: cargas.append(1))
    assert principal.main([]) == 2
    assert "Uso:" in capsys.readouterr().err
    assert cargas == []


def test_con_solicitud_carga_el_entorno_una_vez_antes_de_ejecutar_y_lo_imprime_todo(
    monkeypatch, capsys
):
    orden = []
    monkeypatch.setattr(configuracion, "cargar_entorno", lambda: orden.append("cargar_entorno"))
    monkeypatch.setattr(principal, "ejecutar_caso", _ejecutar_caso_simulado(_fin(), orden))

    codigo = principal.main(["Necesito el due diligence", "de Tienda Verde SAS"])

    assert codigo == 0
    assert orden == ["cargar_entorno", "ejecutar_caso"]
    salida = capsys.readouterr().out
    for esperado in (
        "Eventos del caso:",
        "caso_iniciado",
        "frente_inicio",
        "registro",
        "terminado",
        "Terminación del caso: normal",
        "Resumen para el analista.",
        "solape de registro, noticias y categoría: True",
        "coste de coordinador: 0.5000 USD",
        "coste de noticias: 0.0100 USD",
        "coste total: 0.5100 USD",
        "duración de registro:",
        "duración total del caso:",
    ):
        assert esperado in salida


def test_una_terminacion_anomala_devuelve_uno(monkeypatch, capsys):
    monkeypatch.setattr(configuracion, "cargar_entorno", lambda: True)
    monkeypatch.setattr(
        principal, "ejecutar_caso", _ejecutar_caso_simulado(_fin(stop_reason="max_tokens"), [])
    )
    assert principal.main(["solicitud"]) == 1
    assert "Terminación del caso: anomala" in capsys.readouterr().out


def _eventos(*tipos_y_frentes):
    """Eventos con una marca que avanza un segundo por evento."""
    base = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    contador = iter(range(100))
    registro = RegistroEventos(reloj=lambda: base + timedelta(seconds=next(contador)))
    for tipo, frente in tipos_y_frentes:
        registro.registrar(tipo, frente, "x")
    return registro.eventos()


def test_las_duraciones_salen_de_las_marcas_de_inicio_y_fin():
    eventos = _eventos(
        (TIPO_FRENTE_INICIO, Frente.REGISTRO),
        (TIPO_FRENTE_INICIO, Frente.NOTICIAS),
        (TIPO_FRENTE_FIN, Frente.REGISTRO),
        (TIPO_FRENTE_FIN, Frente.NOTICIAS),
    )
    assert principal.duraciones(eventos) == {Frente.REGISTRO: 2.0, Frente.NOTICIAS: 2.0}


def test_hubo_solape_se_lee_de_la_secuencia_de_los_eventos():
    solapados = _eventos(
        (TIPO_DELEGACION, Frente.REGISTRO),
        (TIPO_FRENTE_INICIO, Frente.REGISTRO),
        (TIPO_FRENTE_INICIO, Frente.NOTICIAS),
        (TIPO_FRENTE_FIN, Frente.REGISTRO),
        (TIPO_FRENTE_FIN, Frente.NOTICIAS),
    )
    en_serie = _eventos(
        (TIPO_FRENTE_INICIO, Frente.REGISTRO),
        (TIPO_FRENTE_FIN, Frente.REGISTRO),
        (TIPO_FRENTE_INICIO, Frente.NOTICIAS),
        (TIPO_FRENTE_FIN, Frente.NOTICIAS),
    )
    un_solo_frente = _eventos(
        (TIPO_FRENTE_INICIO, Frente.REGISTRO), (TIPO_FRENTE_FIN, Frente.REGISTRO)
    )
    assert principal.hubo_solape(solapados) is True
    assert principal.hubo_solape(en_serie) is False
    assert principal.hubo_solape(un_solo_frente) is None


def test_una_re_delegacion_no_cambia_el_solape_ni_la_duracion_del_primer_ciclo():
    eventos = _eventos(
        (TIPO_FRENTE_INICIO, Frente.REGISTRO),
        (TIPO_FRENTE_INICIO, Frente.CATEGORIA),
        (TIPO_FRENTE_FIN, Frente.REGISTRO),
        (TIPO_FRENTE_FIN, Frente.CATEGORIA),
        (TIPO_FRENTE_INICIO, Frente.CATEGORIA),
        (TIPO_FRENTE_FIN, Frente.CATEGORIA),
    )
    assert principal.hubo_solape(eventos) is True
    assert principal.duraciones(eventos)[Frente.CATEGORIA] == 2.0
