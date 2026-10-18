"""Tests de la herramienta `delegar_frente` (contrato `delegacion.md`, R4, FR-001, FR-013).

Con un ejecutor simulado: ninguno llama al modelo.
"""

import asyncio
import json

import pytest

from due_diligence import configuracion
from due_diligence.delegacion import Delegador
from due_diligence.estado import Causa, EstadoCaso, Situacion
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_DELEGACION,
    TIPO_DELEGACION_REPETIDA,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
    TIPO_FRENTE_INVALIDADO,
    TIPO_FRENTE_RECHAZADO,
    RegistroEventos,
)
from due_diligence.frentes import Frente
from due_diligence.hooks import HooksDelCaso
from due_diligence.simulacion import (
    EjecutorSimulado,
    comercio_del_registro,
    consulta,
    consulta_listas,
    respuesta_del_contrato,
    resultado_frente,
    resultado_listas,
    resultado_registro,
    terminacion_anomala,
)

ERROR_NOTICIAS = {
    "error": True,
    "tipo": "servicio_no_disponible",
    "mensaje": "El servicio de noticias no responde.",
    "reintentable": True,
    "obtenido": {},
}


def _crear(listas_vigilada=True, **kwargs):
    estado, registro, ejecutor = (
        EstadoCaso("solicitud"),
        RegistroEventos(),
        EjecutorSimulado(**kwargs),
    )
    # Desde el #7 la identificación la registra el hook del registro (R4): las opciones de cada
    # subagente llevan los hooks del caso y el ejecutor simulado los ejecuta como el SDK.
    hooks = HooksDelCaso(estado, registro)
    delegador = Delegador(
        estado,
        registro,
        ejecutor,
        lambda frente: configuracion.opciones_subagente(
            frente,
            "instrucciones",
            # `listas_vigilada=False` prueba la defensa propia del Delegador (`_falta_en_listas`)
            # sin que el hook de la consulta de listas (I.1) la bloquee antes.
            hooks=None
            if frente is Frente.LISTAS and not listas_vigilada
            else hooks.subagente(frente),
        ),
    )
    return delegador, estado, registro, ejecutor


def _delegar(delegador, **entrada):
    return asyncio.run(delegador.delegar(entrada))


def _tipos(registro, frente):
    return [(e.secuencia, e.tipo) for e in registro.eventos() if e.frente is frente]


# ------------------------------------------------------------------ éxito


def test_registro_con_identificador_delega_y_devuelve_el_json_tal_cual():
    delegador, estado, _, ejecutor = _crear()
    respuesta = _delegar(delegador, frente="registro", identificador="CO-TV-0001")

    assert respuesta["frente"] == "registro" and respuesta["situacion"] == "terminado"
    assert "error" not in respuesta
    resultado = respuesta["resultados"][0]
    assert resultado["herramienta"] == "consultar_registro_mercantil"
    assert resultado["resultado"] == "coincidencias"  # el JSON del contrato, sin reescribir
    assert resultado["hechos"][0]["contenido"]["identificador"] == "CO-TV-0001"
    assert resultado["hechos"][0]["metadatos"]["fuente"]
    assert len(ejecutor.llamadas) == 1
    assert "CO-TV-0001" in ejecutor.llamadas[0].contexto
    opciones = ejecutor.llamadas[0].opciones
    assert opciones.model == configuracion.modelo_subagentes()
    assert set(opciones.hooks) == {"PostToolUse", "PostToolUseFailure"}  # los hooks del registro
    assert estado.situacion(Frente.REGISTRO) is Situacion.TERMINADO


def test_el_estado_guarda_el_resultado_y_las_consultas():
    delegador, estado, _, _ = _crear()
    _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    assert Frente.REGISTRO in estado.resultados
    assert len(estado.consultas) == 1 and estado.consultas[0].frente is Frente.REGISTRO


def test_con_nombre_y_sin_identificador_delega_con_el_nombre_sin_inventar_un_identificador():
    delegador, _, _, ejecutor = _crear()
    respuesta = _delegar(delegador, frente="registro", nombre="Tienda Verde SAS")
    assert respuesta["situacion"] == "terminado"
    contexto = ejecutor.llamadas[0].contexto
    assert "Tienda Verde SAS" in contexto and "CO-" not in contexto


def test_un_campo_de_otro_frente_no_se_reenvia_al_subagente():
    delegador, _, _, ejecutor = _crear()
    _delegar(
        delegador,
        frente="categoria",
        categoria="suplementos dietarios",
        identificador="CO-TV-0001",
        nombre="Tienda Verde SAS",
    )
    contexto = ejecutor.llamadas[0].contexto
    assert "suplementos dietarios" in contexto
    assert "CO-TV-0001" not in contexto and "Tienda Verde" not in contexto


def test_los_eventos_van_en_orden_delegacion_inicio_fin():
    delegador, _, registro, _ = _crear()
    _delegar(delegador, frente="noticias", nombre="Tienda Verde SAS")
    tipos = _tipos(registro, Frente.NOTICIAS)
    assert [t for _, t in tipos] == [TIPO_DELEGACION, TIPO_FRENTE_INICIO, TIPO_FRENTE_FIN]
    assert [s for s, _ in tipos] == sorted(s for s, _ in tipos)
    assert all(e.detalle for e in registro.eventos())


# ------------------------------------------------------------------ rechazos (FR-013)


@pytest.mark.parametrize("frente", ["registro", "noticias"])
def test_sin_identificador_ni_nombre_se_rechaza_nombrando_el_dato_y_no_se_lanza_ningun_subagente(
    frente,
):
    delegador, estado, registro, ejecutor = _crear()
    respuesta = _delegar(delegador, frente=frente)

    assert respuesta["error"] is True and respuesta["tipo"] == "frente_rechazado"
    assert respuesta["reintentable"] is False
    assert "identificador" in respuesta["mensaje"] and "nombre" in respuesta["mensaje"]
    assert ejecutor.llamadas == []
    assert estado.situacion(Frente(frente)) is Situacion.RECHAZADO
    assert estado.motivo(Frente(frente)) == respuesta["mensaje"]
    eventos = [e for e in registro.eventos() if e.tipo == TIPO_FRENTE_RECHAZADO]
    assert len(eventos) == 1 and eventos[0].detalle == respuesta["mensaje"]
    assert TIPO_FRENTE_INICIO not in [e.tipo for e in registro.eventos()]


def test_categoria_sin_categoria_se_rechaza_y_no_se_inventa_una():
    delegador, estado, _, ejecutor = _crear()
    respuesta = _delegar(delegador, frente="categoria", identificador="CO-TV-0001")
    assert respuesta["tipo"] == "frente_rechazado" and "categoría" in respuesta["mensaje"]
    assert ejecutor.llamadas == []
    assert estado.situacion(Frente.CATEGORIA) is Situacion.RECHAZADO


def test_un_frente_rechazado_se_puede_delegar_de_nuevo_con_el_dato_corregido():
    delegador, estado, _, ejecutor = _crear()
    assert _delegar(delegador, frente="categoria")["tipo"] == "frente_rechazado"
    respuesta = _delegar(delegador, frente="categoria", categoria="apuestas")
    assert respuesta["situacion"] == "terminado"
    assert len(ejecutor.llamadas) == 1
    assert estado.situacion(Frente.CATEGORIA) is Situacion.TERMINADO


@pytest.mark.parametrize("entrada", [{}, {"frente": "inventado"}, {"frente": 7}, {"frente": None}])
def test_un_frente_invalido_es_entrada_invalida_no_reintentable(entrada):
    delegador, estado, registro, ejecutor = _crear()
    respuesta = asyncio.run(delegador.delegar(entrada))
    assert respuesta["error"] is True and respuesta["tipo"] == "entrada_invalida"
    assert respuesta["reintentable"] is False
    assert all(s is Situacion.SIN_INICIAR for s in estado.frentes.values())
    assert ejecutor.llamadas == [] and registro.eventos() == []


# ------------------------------------------------------------------ frente repetido


def test_la_misma_entrada_no_lanza_otro_subagente_y_devuelve_lo_guardado_con_un_evento():
    delegador, _, registro, ejecutor = _crear()
    primera = _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    segunda = _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    assert segunda == primera
    assert len(ejecutor.llamadas) == 1
    tipos = [t for _, t in _tipos(registro, Frente.REGISTRO)]
    assert tipos == [
        TIPO_DELEGACION,
        TIPO_FRENTE_INICIO,
        TIPO_FRENTE_FIN,
        TIPO_DELEGACION_REPETIDA,
    ]


def test_otra_entrada_vuelve_a_ejecutar_el_frente_y_lo_registra():
    delegador, estado, registro, ejecutor = _crear()
    _delegar(delegador, frente="categoria", categoria="Venta en línea de suplementos dietarios")
    segunda = _delegar(delegador, frente="categoria", categoria="suplementos dietarios")
    assert len(ejecutor.llamadas) == 2
    assert "«suplementos dietarios»" in ejecutor.llamadas[1].contexto
    assert segunda["situacion"] == "terminado"
    assert estado.situacion(Frente.CATEGORIA) is Situacion.TERMINADO
    eventos = registro.eventos()
    delegaciones = [e for e in eventos if e.tipo == TIPO_DELEGACION]
    assert "otra entrada" not in delegaciones[0].detalle
    assert "otra entrada" in delegaciones[1].detalle
    assert [e.tipo for e in eventos].count(TIPO_FRENTE_FIN) == 2


def test_una_re_delegacion_con_dato_que_falta_conserva_el_resultado_anterior():
    delegador, estado, _, ejecutor = _crear()
    primera = _delegar(delegador, frente="categoria", categoria="suplementos dietarios")
    rechazada = _delegar(delegador, frente="categoria")
    assert rechazada["error"] is True and rechazada["tipo"] == "frente_rechazado"
    assert estado.situacion(Frente.CATEGORIA) is Situacion.TERMINADO
    assert len(ejecutor.llamadas) == 1
    assert _delegar(delegador, frente="categoria", categoria="suplementos dietarios") == primera


def test_un_frente_en_curso_no_lanza_un_segundo_subagente_y_espera_al_primero():
    delegador, _, _, ejecutor = _crear(retardo=0.05)

    async def dos_a_la_vez():
        return await asyncio.gather(
            delegador.delegar({"frente": "noticias", "nombre": "Tienda Verde SAS"}),
            delegador.delegar({"frente": "noticias", "nombre": "Tienda Verde SAS"}),
        )

    primera, segunda = asyncio.run(dos_a_la_vez())
    assert len(ejecutor.llamadas) == 1
    assert primera == segunda


# ------------------------------------------------------------------ no terminado


def test_una_terminacion_anomala_es_frente_no_terminado_con_lo_obtenido():
    anomalo = resultado_frente(
        Frente.NOTICIAS,
        [consulta(Frente.NOTICIAS, {"nombre": "Tienda Verde SAS"})],
        terminacion_anomala(),
    )
    delegador, estado, registro, _ = _crear(resultados={Frente.NOTICIAS: anomalo})
    respuesta = _delegar(delegador, frente="noticias", nombre="Tienda Verde SAS")

    assert respuesta["error"] is True and respuesta["tipo"] == "frente_no_terminado"
    assert respuesta["reintentable"] is False
    assert respuesta["obtenido"]["frente"] == "noticias"
    assert len(respuesta["obtenido"]["resultados"]) == 1  # conserva lo alcanzado
    assert "max_tokens" in respuesta["obtenido"]["terminacion"]
    assert estado.situacion(Frente.NOTICIAS) is Situacion.NO_TERMINADO
    assert Frente.NOTICIAS in estado.resultados  # no se pierde, y no figura como terminado
    fin = [e for e in registro.eventos() if e.tipo == TIPO_FRENTE_FIN][0]
    assert "no_terminado" in fin.detalle and "max_tokens" in fin.detalle


def test_una_terminacion_anomala_sin_consultas_conserva_el_error_con_lo_obtenido_vacio():
    delegador, _, _, _ = _crear(
        resultados={Frente.NOTICIAS: resultado_frente(Frente.NOTICIAS, [], terminacion_anomala())}
    )
    respuesta = _delegar(delegador, frente="noticias", nombre="Tienda Verde SAS")
    assert respuesta["tipo"] == "frente_no_terminado"
    assert respuesta["obtenido"]["resultados"] == []


@pytest.mark.parametrize(("reintentable", "esperado"), [(True, True), (False, False)])
def test_el_error_de_la_pasarela_propaga_su_reintentable_y_se_conserva(reintentable, esperado):
    error = {**ERROR_NOTICIAS, "reintentable": reintentable}
    caido = resultado_frente(
        Frente.NOTICIAS, [consulta(Frente.NOTICIAS, {"nombre": "Tienda Verde SAS"}, error=error)]
    )
    delegador, estado, _, _ = _crear(resultados={Frente.NOTICIAS: caido})
    respuesta = _delegar(delegador, frente="noticias", nombre="Tienda Verde SAS")

    assert respuesta["tipo"] == "frente_no_terminado"
    assert respuesta["reintentable"] is esperado  # el del error, no un valor fijo (G2)
    assert respuesta["obtenido"]["errores"] == [error]
    assert estado.situacion(Frente.NOTICIAS) is Situacion.NO_TERMINADO
    assert estado.consultas[0].error == error


def test_con_varios_errores_solo_es_reintentable_si_todos_lo_son():
    errores = [ERROR_NOTICIAS, {**ERROR_NOTICIAS, "reintentable": False}]
    caido = resultado_frente(
        Frente.NOTICIAS, [consulta(Frente.NOTICIAS, {"nombre": "x"}, error=e) for e in errores]
    )
    delegador, _, _, _ = _crear(resultados={Frente.NOTICIAS: caido})
    assert _delegar(delegador, frente="noticias", nombre="x")["reintentable"] is False


def test_un_resultado_invalido_es_no_terminado():
    invalido = resultado_frente(Frente.NOTICIAS, [consulta(Frente.NOTICIAS, {}, None, None)])
    invalido.consultas[0].valido = False
    invalido.consultas[0].resultado = None
    delegador, estado, _, _ = _crear(resultados={Frente.NOTICIAS: invalido})
    respuesta = _delegar(delegador, frente="noticias", nombre="x")
    assert respuesta["tipo"] == "frente_no_terminado" and respuesta["reintentable"] is False
    assert estado.situacion(Frente.NOTICIAS) is Situacion.NO_TERMINADO


def test_una_terminacion_normal_sin_ninguna_consulta_es_no_terminado():
    delegador, estado, _, _ = _crear(
        resultados={Frente.NOTICIAS: resultado_frente(Frente.NOTICIAS, [])}
    )
    respuesta = _delegar(delegador, frente="noticias", nombre="x")
    assert respuesta["tipo"] == "frente_no_terminado"
    assert estado.situacion(Frente.NOTICIAS) is Situacion.NO_TERMINADO


def test_si_el_ejecutor_lanza_una_excepcion_el_frente_queda_no_terminado():
    delegador, estado, _, _ = _crear(
        excepciones={Frente.NOTICIAS: RuntimeError("falló el proceso")}
    )
    respuesta = _delegar(delegador, frente="noticias", nombre="x")
    assert respuesta["tipo"] == "frente_no_terminado"
    assert "RuntimeError" in respuesta["obtenido"]["terminacion"]
    assert estado.situacion(Frente.NOTICIAS) is Situacion.NO_TERMINADO


# ------------------------------------------------------------------ servidor en proceso


def test_el_servidor_en_proceso_expone_solo_delegar_frente():
    delegador, _, _, _ = _crear()
    servidor = delegador.servidor()
    assert servidor["type"] == "sdk" and servidor["name"] == "delegacion"
    assert delegador.herramienta.name == "delegar_frente"
    assert "subagente" in delegador.herramienta.description


def test_el_manejador_devuelve_el_json_como_texto_y_marca_el_error():
    delegador, _, _, _ = _crear()

    bien = asyncio.run(
        delegador.herramienta.handler({"frente": "registro", "identificador": "CO-TV-0001"})
    )
    assert bien["is_error"] is False
    assert json.loads(bien["content"][0]["text"])["situacion"] == "terminado"

    mal = asyncio.run(delegador.herramienta.handler({"frente": "categoria"}))
    assert mal["is_error"] is True
    assert json.loads(mal["content"][0]["text"])["tipo"] == "frente_rechazado"


# ------------------------------------------------------------ paralelismo y orden de listas (US3)

MENSAJE_REGISTRO_PRIMERO = "delega primero el registro y vuelve a pedir listas cuando termine"


async def _a_la_vez(delegador, *entradas):
    return await asyncio.gather(*(delegador.delegar(e) for e in entradas))


def _secuencia(registro, tipo, frente):
    return next(e.secuencia for e in registro.eventos() if e.tipo == tipo and e.frente is frente)


REGISTRO = {"frente": "registro", "identificador": "CO-TV-0001"}
NOTICIAS = {"frente": "noticias", "identificador": "CO-TV-0001"}
CATEGORIA = {"frente": "categoria", "categoria": "suplementos dietarios"}
LISTAS = {"frente": "listas"}


def test_la_herramienta_esta_anotada_como_de_solo_lectura_para_que_el_sdk_la_solape():
    delegador, _, _, _ = _crear()
    anotaciones = delegador.herramienta.annotations
    assert anotaciones is not None and anotaciones.read_only_hint is True


def test_registro_noticias_y_categoria_se_solapan():
    delegador, _, registro, ejecutor = _crear(retardo=0.05)
    asyncio.run(_a_la_vez(delegador, REGISTRO, NOTICIAS, CATEGORIA))
    inicios = [
        _secuencia(registro, TIPO_FRENTE_INICIO, f)
        for f in (Frente.REGISTRO, Frente.NOTICIAS, Frente.CATEGORIA)
    ]
    fines = [
        _secuencia(registro, TIPO_FRENTE_FIN, f)
        for f in (Frente.REGISTRO, Frente.NOTICIAS, Frente.CATEGORIA)
    ]
    assert max(inicios) < min(fines)  # los tres empiezan antes de que termine cualquiera
    llamadas = ejecutor.llamadas
    assert all(a.inicio < b.fin for a in llamadas for b in llamadas)


def test_registro_y_luego_listas_en_el_mismo_gather_listas_espera_al_fin_del_registro():
    delegador, estado, registro, ejecutor = _crear(retardo=0.05)
    asyncio.run(_a_la_vez(delegador, REGISTRO, LISTAS))
    assert _secuencia(registro, TIPO_FRENTE_INICIO, Frente.LISTAS) > _secuencia(
        registro, TIPO_FRENTE_FIN, Frente.REGISTRO
    )
    assert _secuencia(registro, TIPO_DELEGACION, Frente.LISTAS) > _secuencia(
        registro, TIPO_FRENTE_FIN, Frente.REGISTRO
    )
    assert (
        ejecutor.llamadas_de(Frente.LISTAS)[0].inicio
        >= ejecutor.llamadas_de(Frente.REGISTRO)[0].fin
    )
    assert estado.situacion(Frente.LISTAS) is Situacion.TERMINADO


def test_dos_listas_mientras_corre_el_registro_lanzan_un_solo_subagente_y_responden_igual():
    delegador, estado, registro, ejecutor = _crear(retardo=0.05)
    reg, primera, segunda = asyncio.run(_a_la_vez(delegador, REGISTRO, LISTAS, LISTAS))

    assert reg["situacion"] == "terminado"
    assert "error" not in primera and primera["situacion"] == "terminado"
    assert primera == segunda
    assert len(ejecutor.llamadas_de(Frente.LISTAS)) == 1
    assert [e.tipo for e in registro.eventos() if e.frente is Frente.LISTAS].count(
        TIPO_FRENTE_INICIO
    ) == 1
    assert estado.situacion(Frente.LISTAS) is Situacion.TERMINADO


def test_listas_antes_que_registro_se_rechaza_con_reintentable_y_se_reintenta():
    delegador, estado, registro, ejecutor = _crear(retardo=0.02)
    listas, reg = asyncio.run(_a_la_vez(delegador, LISTAS, REGISTRO))

    assert listas["error"] is True and listas["tipo"] == "frente_rechazado"
    assert listas["reintentable"] is True
    assert MENSAJE_REGISTRO_PRIMERO in listas["mensaje"]
    assert ejecutor.llamadas_de(Frente.LISTAS) == []
    assert estado.situacion(Frente.LISTAS) is Situacion.RECHAZADO
    assert reg["situacion"] == "terminado"
    assert TIPO_FRENTE_INICIO not in [
        e.tipo for e in registro.eventos() if e.frente is Frente.LISTAS
    ]

    # El reintento, ya terminado el registro, se ejecuta.
    reintento = asyncio.run(delegador.delegar(LISTAS))
    assert reintento["situacion"] == "terminado"
    assert len(ejecutor.llamadas_de(Frente.LISTAS)) == 1
    assert estado.situacion(Frente.LISTAS) is Situacion.TERMINADO


def test_listas_sin_haber_delegado_el_registro_se_rechaza_con_reintentable():
    delegador, _, _, ejecutor = _crear()
    respuesta = _delegar(delegador, **LISTAS)
    assert respuesta["tipo"] == "frente_rechazado" and respuesta["reintentable"] is True
    assert MENSAJE_REGISTRO_PRIMERO in respuesta["mensaje"]
    assert ejecutor.llamadas == []


def test_con_el_registro_rechazado_por_falta_de_dato_listas_se_rechaza_con_reintentable():
    delegador, estado, _, _ = _crear()
    assert _delegar(delegador, frente="registro")["tipo"] == "frente_rechazado"
    respuesta = _delegar(delegador, **LISTAS)
    assert respuesta["tipo"] == "frente_rechazado" and respuesta["reintentable"] is True
    assert estado.situacion(Frente.LISTAS) is Situacion.RECHAZADO


def test_si_el_registro_termina_antes_que_noticias_listas_no_espera_a_noticias():
    delegador, _, registro, _ = _crear(retardos={Frente.REGISTRO: 0.01, Frente.NOTICIAS: 0.3})
    asyncio.run(_a_la_vez(delegador, NOTICIAS, REGISTRO, LISTAS))
    inicio_listas = _secuencia(registro, TIPO_FRENTE_INICIO, Frente.LISTAS)
    assert inicio_listas > _secuencia(registro, TIPO_FRENTE_FIN, Frente.REGISTRO)
    assert inicio_listas < _secuencia(registro, TIPO_FRENTE_FIN, Frente.NOTICIAS)


def test_si_el_registro_falla_con_una_excepcion_listas_no_espera_para_siempre():
    delegador, estado, _, _ = _crear(
        retardo=0.02, excepciones={Frente.REGISTRO: RuntimeError("falló")}
    )

    async def con_limite():
        return await asyncio.wait_for(_a_la_vez(delegador, REGISTRO, LISTAS), timeout=5)

    registro_resp, listas = asyncio.run(con_limite())
    assert registro_resp["tipo"] == "frente_no_terminado"
    assert estado.situacion(Frente.REGISTRO) is Situacion.NO_TERMINADO
    assert listas["tipo"] == "frente_rechazado" and listas["reintentable"] is False
    assert estado.situacion(Frente.LISTAS) is Situacion.RECHAZADO


# ------------------------------------------------------- listas: comercio y representante (US4)

COMERCIO_ESPERADO = {
    "identificador": "CO-TV-0001",
    "nombre": "Tienda Verde SAS",
    "representante_legal": {"nombre": "Lucía Ferrer Montalvo", "identificador": "PE-0001"},
}


def _registro_y_listas(consultas_de_listas=None, registro=None, retardo=0.0, vigilada=True):
    """El registro y `listas` en el mismo turno; devuelve la respuesta de `listas`."""
    resultados = {Frente.REGISTRO: registro or resultado_registro()}
    if consultas_de_listas is not None:
        resultados[Frente.LISTAS] = resultado_listas(consultas_de_listas)
    delegador, estado, _, ejecutor = _crear(
        listas_vigilada=vigilada, resultados=resultados, retardo=retardo
    )
    _, listas = asyncio.run(_a_la_vez(delegador, REGISTRO, LISTAS))
    return listas, estado, ejecutor


def test_el_comercio_del_estado_es_exactamente_el_que_devolvio_el_registro():
    _, estado, _ = _registro_y_listas()
    assert estado.comercio == COMERCIO_ESPERADO
    assert estado.motivo_comercio == ""


def test_el_prompt_de_listas_usa_el_estado_aunque_la_entrada_traiga_otros_datos():
    delegador, _, _, ejecutor = _crear()
    asyncio.run(delegador.delegar(REGISTRO))
    asyncio.run(
        delegador.delegar({"frente": "listas", "identificador": "CO-XX-9999", "nombre": "Otro SAS"})
    )
    contexto = ejecutor.llamadas_de(Frente.LISTAS)[0].contexto
    assert (
        "CO-TV-0001" in contexto and "Lucía Ferrer Montalvo" in contexto and "PE-0001" in contexto
    )
    assert "CO-XX-9999" not in contexto and "Otro SAS" not in contexto


def test_listas_consulta_al_comercio_y_al_representante_y_ambas_quedan_en_el_estado():
    listas, estado, _ = _registro_y_listas()
    assert listas["situacion"] == "terminado"
    consultas = [c for c in estado.consultas if c.frente is Frente.LISTAS]
    assert [c.argumentos["tipo"] for c in consultas] == ["comercio", "persona"]
    assert all(c.valido and c.resultado["metadatos"]["fuentes"] for c in consultas)
    assert [r["argumentos"]["tipo"] for r in listas["resultados"]] == ["comercio", "persona"]


def test_si_listas_consulta_solo_al_comercio_el_frente_queda_no_terminado():
    listas, estado, _ = _registro_y_listas(
        [consulta_listas("comercio", identificador="CO-TV-0001")]
    )
    assert listas["tipo"] == "frente_no_terminado" and listas["reintentable"] is False
    assert "consulta del representante" in listas["mensaje"]
    assert estado.situacion(Frente.LISTAS) is Situacion.NO_TERMINADO
    assert estado.motivo(Frente.LISTAS) == listas["mensaje"]


def test_si_listas_consulta_solo_al_representante_el_frente_queda_no_terminado():
    listas, estado, _ = _registro_y_listas([consulta_listas("persona", identificador="PE-0001")])
    assert listas["tipo"] == "frente_no_terminado" and "consulta del comercio" in listas["mensaje"]
    assert estado.situacion(Frente.LISTAS) is Situacion.NO_TERMINADO


def test_otra_capitalizacion_o_sin_tildes_cuenta_porque_igual_la_normaliza():
    consultas = [
        consulta_listas("comercio", identificador="co-tv-0001"),
        consulta_listas("persona", nombre="LUCIA FERRER MONTALVO"),
    ]
    listas, estado, _ = _registro_y_listas(consultas)
    assert listas["situacion"] == "terminado"
    assert estado.situacion(Frente.LISTAS) is Situacion.TERMINADO


def test_el_nombre_del_comercio_sin_su_forma_juridica_no_cuenta():
    # La pasarela busca por el nombre completo: «Tienda Verde» daría sin coincidencias.
    consultas = [
        consulta_listas("comercio", nombre="Tienda Verde"),
        consulta_listas("persona", identificador="PE-0001"),
    ]
    listas, _, _ = _registro_y_listas(consultas, vigilada=False)
    assert listas["tipo"] == "frente_no_terminado" and "consulta del comercio" in listas["mensaje"]


def test_un_nombre_parcial_del_representante_no_cuenta():
    consultas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("persona", nombre="Lucía Ferrer"),
    ]
    listas, _, _ = _registro_y_listas(consultas, vigilada=False)
    assert listas["tipo"] == "frente_no_terminado"
    assert "consulta del representante" in listas["mensaje"]


def test_una_consulta_con_el_tipo_cambiado_no_cuenta():
    consultas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("comercio", nombre="Lucía Ferrer Montalvo"),  # tipo equivocado
    ]
    listas, _, _ = _registro_y_listas(consultas, vigilada=False)
    assert listas["tipo"] == "frente_no_terminado"
    assert "consulta del representante" in listas["mensaje"]


def test_el_nombre_del_comercio_con_el_tipo_persona_no_cuenta_como_consulta_del_comercio():
    consultas = [
        consulta_listas("persona", nombre="Tienda Verde SAS"),  # tipo equivocado
        consulta_listas("persona", identificador="PE-0001"),
    ]
    listas, _, _ = _registro_y_listas(consultas, vigilada=False)
    assert listas["tipo"] == "frente_no_terminado" and "consulta del comercio" in listas["mensaje"]


def test_las_consultas_de_mas_no_estorban():
    consultas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("persona", identificador="PE-0001"),
        consulta_listas("persona", nombre="Otra Persona Ficticia"),
    ]
    listas, _, _ = _registro_y_listas(consultas, vigilada=False)
    assert listas["situacion"] == "terminado"


def test_sin_representante_en_el_registro_basta_la_consulta_del_comercio():
    registro = resultado_registro([comercio_del_registro(representante=None)])
    listas, estado, ejecutor = _registro_y_listas(
        [consulta_listas("comercio", identificador="CO-TV-0001")], registro=registro
    )
    assert estado.comercio["representante_legal"] is None
    assert listas["situacion"] == "terminado"
    assert "no devolvió representante" in ejecutor.llamadas_de(Frente.LISTAS)[0].contexto


def test_varias_coincidencias_no_ejecutan_listas_y_no_son_reintentables():
    registro = resultado_registro(
        [
            comercio_del_registro("CO-AM-0004", "Almacén Mirador SAS", None),
            comercio_del_registro("CO-AM-0005", "Almacén Mirador del Norte SAS", None),
        ]
    )
    listas, estado, ejecutor = _registro_y_listas(registro=registro)
    assert estado.comercio is None
    assert listas["tipo"] == "frente_rechazado" and listas["reintentable"] is False
    assert "varias coincidencias" in listas["mensaje"]
    assert ejecutor.llamadas_de(Frente.LISTAS) == []
    assert estado.situacion(Frente.LISTAS) is Situacion.RECHAZADO


def test_sin_coincidencias_no_ejecuta_listas_y_no_es_reintentable():
    listas, estado, ejecutor = _registro_y_listas(registro=resultado_registro([]))
    assert estado.comercio is None
    assert listas["tipo"] == "frente_rechazado" and listas["reintentable"] is False
    assert "ninguna coincidencia" in listas["mensaje"]
    assert ejecutor.llamadas_de(Frente.LISTAS) == []


def test_un_registro_que_no_termino_bien_no_ejecuta_listas():
    anomalo = resultado_frente(Frente.REGISTRO, [], terminacion_anomala())
    listas, estado, ejecutor = _registro_y_listas(registro=anomalo)
    assert estado.comercio is None
    assert listas["tipo"] == "frente_rechazado" and listas["reintentable"] is False
    assert "no terminó" in listas["mensaje"]
    assert ejecutor.llamadas_de(Frente.LISTAS) == []


def test_si_las_fuentes_difieren_en_el_representante_no_se_elige_una():
    otro = {"nombre": "Pedro Ríos Quintero", "identificador": "PE-0002"}
    respuesta = respuesta_del_contrato(
        "coincidencias",
        [comercio_del_registro(), comercio_del_registro(representante=otro)],
        ["CO-TV-0001"],
    )
    registro = resultado_frente(Frente.REGISTRO, [consulta(Frente.REGISTRO, {}, respuesta)])
    listas, estado, _ = _registro_y_listas(registro=registro)
    assert estado.comercio is None and "difieren" in listas["mensaje"]


def test_si_las_fuentes_difieren_solo_en_la_fecha_el_comercio_se_deriva_igual():
    # Caso (g): dos fechas de constitución, cada una con su fuente; el comercio es el mismo.
    otra_fecha = {**comercio_del_registro(), "fecha_constitucion": "2017-09-02"}
    respuesta = respuesta_del_contrato(
        "coincidencias", [comercio_del_registro(), otra_fecha], ["CO-TV-0001"]
    )
    registro = resultado_frente(Frente.REGISTRO, [consulta(Frente.REGISTRO, {}, respuesta)])
    listas, estado, _ = _registro_y_listas(registro=registro)
    assert estado.comercio == COMERCIO_ESPERADO
    assert listas["situacion"] == "terminado"


def test_caso_g_el_estado_conserva_las_dos_fechas_de_constitucion_cada_una_con_su_fuente():
    # CO-RF-0006: dos fuentes con fechas distintas; el sistema no elige ninguna (principio I.4).
    rmf, rufe = "Registro Mercantil Ficticio del Sur", "Registro Único Ficticio de Empresas"
    base = comercio_del_registro("CO-RF-0006", "Ferretería Río Fino SAS", None)
    hechos = [
        {
            "contenido": {**base, "fecha_constitucion": fecha},
            "metadatos": {"fuente": fuente, "fecha": "2026-09-30"},
        }
        for fuente, fecha in ((rmf, "2016-03-14"), (rufe, "2017-09-02"))
    ]
    respuesta = {
        "resultado": "coincidencias",
        "coincidencias": ["CO-RF-0006"],
        "hechos": hechos,
        "metadatos": {"fuentes": [rmf, rufe], "fecha": "2026-09-30"},
    }
    registro = resultado_frente(Frente.REGISTRO, [consulta(Frente.REGISTRO, {}, respuesta)])
    delegador, estado, _, _ = _crear(resultados={Frente.REGISTRO: registro})

    devuelta = _delegar(delegador, frente="registro", identificador="CO-RF-0006")

    def pares(hechos_):
        return {(h["contenido"]["fecha_constitucion"], h["metadatos"]["fuente"]) for h in hechos_}

    esperados = {("2016-03-14", rmf), ("2017-09-02", rufe)}
    assert pares(estado.consultas[0].resultado["hechos"]) == esperados
    assert pares(estado.resultados[Frente.REGISTRO].consultas[0].resultado["hechos"]) == esperados
    assert pares(devuelta["resultados"][0]["hechos"]) == esperados
    assert estado.comercio["identificador"] == "CO-RF-0006"  # una sola fecha no se elige


# ------------------------------------------------------------------ varias consultas del registro


def _registro_con_dos_consultas(primera, segunda):
    def de(comercios):
        contenidos = comercios
        ids = list(dict.fromkeys(c["identificador"] for c in comercios))
        return consulta(
            Frente.REGISTRO,
            {},
            respuesta_del_contrato("coincidencias", contenidos, ids),
        )

    return resultado_frente(Frente.REGISTRO, [de(primera), de(segunda)])


def test_si_una_consulta_del_registro_da_varias_coincidencias_no_se_elige_la_otra():
    unico = [comercio_del_registro()]
    varias = [
        comercio_del_registro("CO-AM-0004", "Almacén Mirador SAS", None),
        comercio_del_registro("CO-AM-0005", "Almacén Mirador del Norte SAS", None),
    ]
    registro = _registro_con_dos_consultas(unico, varias)
    listas, estado, ejecutor = _registro_y_listas(registro=registro)
    assert estado.comercio is None and "varias coincidencias" in estado.motivo_comercio
    assert listas["tipo"] == "frente_rechazado" and listas["reintentable"] is False
    assert ejecutor.llamadas_de(Frente.LISTAS) == []


def test_si_las_consultas_del_registro_dan_comercios_distintos_no_hay_comercio():
    otro = comercio_del_registro("CO-PL-0003", "Pago Latino SAS", None)
    registro = _registro_con_dos_consultas([comercio_del_registro()], [otro])
    listas, estado, ejecutor = _registro_y_listas(registro=registro)
    assert estado.comercio is None and "comercios distintos" in estado.motivo_comercio
    assert listas["tipo"] == "frente_rechazado"
    assert ejecutor.llamadas_de(Frente.LISTAS) == []


def test_dos_consultas_del_registro_que_dan_el_mismo_comercio_lo_fijan():
    registro = _registro_con_dos_consultas([comercio_del_registro()], [comercio_del_registro()])
    listas, estado, _ = _registro_y_listas(registro=registro)
    assert estado.comercio == COMERCIO_ESPERADO
    assert listas["situacion"] == "terminado"


# ------------------------------------------------------------------ el comercio cambia


def _registro_cambia_de_comercio():
    otro = comercio_del_registro(
        "CO-PL-0003",
        "Pago Latino SAS",
        {"nombre": "Mario Quispe Vargas", "identificador": "PE-0099"},
    )
    registros = iter([resultado_registro(), resultado_registro([otro])])
    return _crear(
        resultados={
            Frente.REGISTRO: lambda contexto: next(registros),
            Frente.LISTAS: lambda contexto: resultado_listas(
                [
                    consulta_listas("comercio", identificador="CO-PL-0003"),
                    consulta_listas("persona", identificador="PE-0099"),
                ]
                if "CO-PL-0003" in contexto
                else None
            ),
        }
    )


def test_si_el_registro_cambia_de_comercio_listas_deja_de_estar_terminado_y_se_reintenta():
    delegador, estado, registro, ejecutor = _registro_cambia_de_comercio()
    _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    assert _delegar(delegador, frente="listas")["situacion"] == "terminado"

    _delegar(delegador, frente="registro", identificador="CO-PL-0003")

    assert estado.comercio["identificador"] == "CO-PL-0003"
    assert estado.situacion(Frente.LISTAS) is Situacion.NO_TERMINADO
    assert (
        estado.motivo(Frente.LISTAS) == "El comercio del registro cambió; vuelva a delegar listas."
    )
    ultimo = [e for e in registro.eventos() if e.frente is Frente.LISTAS][-1]
    assert ultimo.tipo == TIPO_FRENTE_INVALIDADO and "cambió" in ultimo.detalle
    assert [e.tipo for e in registro.eventos() if e.frente is Frente.LISTAS].count(
        TIPO_FRENTE_FIN
    ) == 1

    nueva = _delegar(delegador, frente="listas")
    assert nueva["situacion"] == "terminado"
    assert len(ejecutor.llamadas_de(Frente.LISTAS)) == 2
    assert "CO-PL-0003" in ejecutor.llamadas_de(Frente.LISTAS)[1].contexto


def test_si_el_registro_se_repite_y_el_comercio_no_cambia_listas_sigue_terminado():
    delegador, estado, _, _ = _crear()
    _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    _delegar(delegador, frente="listas")
    _delegar(delegador, frente="registro", nombre="Tienda Verde SAS")
    assert estado.situacion(Frente.LISTAS) is Situacion.TERMINADO


def test_volver_al_comercio_anterior_tampoco_reutiliza_el_resultado_viejo_de_listas():
    delegador, _, _, ejecutor = _registro_cambia_de_comercio()
    _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    _delegar(delegador, frente="listas")
    _delegar(delegador, frente="registro", identificador="CO-PL-0003")
    _delegar(delegador, frente="listas")
    delegador._ejecutor.resultados[Frente.REGISTRO] = resultado_registro()
    _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    _delegar(delegador, frente="listas")
    assert len(ejecutor.llamadas_de(Frente.LISTAS)) == 3


def test_al_volver_a_delegar_el_registro_se_reinicia_la_identificacion_antes_de_lanzar_el_frente():
    visto = {}

    def segundo_registro(contexto):
        # Cuando el ejecutor arranca por segunda vez, lo identificado antes ya se olvidó (R4).
        visto["identificaciones"] = list(estado.identificaciones)
        visto["comercio"] = estado.comercio
        return resultado_registro()

    resultados = iter([resultado_registro(), None])

    def registro(contexto):
        siguiente = next(resultados)
        return siguiente if siguiente is not None else segundo_registro(contexto)

    delegador, estado, registro_eventos, _ = _crear(resultados={Frente.REGISTRO: registro})
    _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    assert estado.comercio == COMERCIO_ESPERADO
    _delegar(delegador, frente="registro", identificador="CO-TV-0001 ")
    assert visto == {"identificaciones": [], "comercio": None}
    assert estado.comercio == COMERCIO_ESPERADO  # y al terminar vuelve a identificarse


def test_el_comercio_anterior_se_conserva_para_decidir_la_invalidacion_de_listas():
    # El comercio que ya estaba (capturado antes de reiniciar) es contra el que se compara al
    # concluir: con el mismo comercio listas sigue terminado; con otro, deja de estarlo.
    delegador, estado, registro, _ = _registro_cambia_de_comercio()
    _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    _delegar(delegador, frente="listas")
    _delegar(delegador, frente="registro", identificador="CO-PL-0003")
    assert estado.situacion(Frente.LISTAS) is Situacion.NO_TERMINADO
    invalidaciones = [e for e in registro.eventos() if e.tipo == TIPO_FRENTE_INVALIDADO]
    assert len(invalidaciones) == 1


def _consultas_de_listas_con_una_de_mas():
    return [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("persona", identificador="PE-0001"),
        consulta_listas("persona", nombre="Otra Persona Ficticia"),  # de más: el hook la bloquea
    ]


def test_una_consulta_de_mas_bloqueada_no_hace_fallar_el_frente_si_las_necesarias_se_hicieron():
    # Decisión de la analista: lo bloqueado no cuenta contra el frente si el comercio y el
    # representante se consultaron de forma válida. El intento queda como evento de la regla.
    listas, estado, registro, _ = _registro_y_listas_con_eventos(
        _consultas_de_listas_con_una_de_mas()
    )
    assert listas["situacion"] == "terminado" and "error" not in listas
    assert estado.situacion(Frente.LISTAS) is Situacion.TERMINADO
    bloqueos = [e for e in registro.eventos() if e.tipo == TIPO_BLOQUEO_REGLA]
    assert [(e.regla, e.frente) for e in bloqueos] == [("I.1", Frente.LISTAS)]
    # La respuesta al coordinador solo trae las consultas válidas, sin el intento bloqueado.
    assert len(listas["resultados"]) == 2
    assert "Otra Persona" not in json.dumps(listas)
    # El estado conserva el intento como traza, con su tipo de error.
    bloqueadas = [
        c for c in estado.consultas if c.error and c.error["tipo"] == "bloqueado_por_hook"
    ]
    assert len(bloqueadas) == 1 and bloqueadas[0].valido is False


def test_si_lo_bloqueado_era_una_consulta_necesaria_el_frente_no_termina():
    consultas = [
        consulta_listas("comercio", nombre="Otro Comercio SAS"),  # no es el comercio: se bloquea
        consulta_listas("persona", identificador="PE-0001"),
    ]
    listas, estado, _, _ = _registro_y_listas_con_eventos(consultas)
    assert listas["tipo"] == "frente_no_terminado"
    assert "consulta del comercio" in listas["mensaje"]
    assert estado.situacion(Frente.LISTAS) is Situacion.NO_TERMINADO


def test_un_error_real_de_la_herramienta_sigue_haciendo_fallar_el_frente():
    consultas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("persona", identificador="PE-0001"),
        consulta(
            Frente.LISTAS, {"tipo": "persona", "identificador": "PE-0001"}, error=ERROR_NOTICIAS
        ),
    ]
    listas, _, _, _ = _registro_y_listas_con_eventos(consultas)
    assert listas["tipo"] == "frente_no_terminado"
    assert listas["reintentable"] is True  # solo cuentan los errores reales para reintentar


def test_el_bloqueo_de_un_hook_no_vuelve_reintentable_a_un_frente_que_fallo_por_otra_causa():
    consultas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("persona", nombre="Otra Persona Ficticia"),  # bloqueada
    ]
    listas, _, _, _ = _registro_y_listas_con_eventos(consultas)
    assert listas["tipo"] == "frente_no_terminado" and listas["reintentable"] is False


def _registro_y_listas_con_eventos(consultas_de_listas):
    resultados = {
        Frente.REGISTRO: resultado_registro(),
        Frente.LISTAS: resultado_listas(consultas_de_listas),
    }
    delegador, estado, registro, ejecutor = _crear(resultados=resultados)
    _, listas = asyncio.run(_a_la_vez(delegador, REGISTRO, LISTAS))
    return listas, estado, registro, ejecutor


# ------------------------------------------------------------------ error estructurado (#8, R4)

TEXTO_INTERNO = "TEXTO-INTERNO-FICTICIO"


def _caido(error):
    return resultado_frente(
        Frente.NOTICIAS, [consulta(Frente.NOTICIAS, {"nombre": "Tienda Verde SAS"}, error=error)]
    )


def _noticias_con(resultado):
    delegador, estado, registro, ejecutor = _crear(resultados={Frente.NOTICIAS: resultado})
    return _delegar(delegador, **NOTICIAS), estado, registro, ejecutor


def test_un_error_de_fuente_reintentable_lleva_todos_los_campos_del_error_de_frente():
    respuesta, estado, _, _ = _noticias_con(_caido(ERROR_NOTICIAS))
    assert respuesta["error"] is True and respuesta["tipo"] == "frente_no_terminado"
    assert respuesta["frente"] == "noticias"
    assert respuesta["causa"] == Causa.ERROR_DE_FUENTE == "error_de_fuente"
    assert isinstance(respuesta["mensaje"], str) and respuesta["mensaje"]
    assert respuesta["reintentable"] is True
    assert respuesta["intento"] == 1
    assert respuesta["reintentos_restantes"] == configuracion.MAX_REINTENTOS_POR_FRENTE
    assert respuesta["obtenido"]["errores"] == [ERROR_NOTICIAS]
    # El tipo concreto de la pasarela sigue en `obtenido.errores[].tipo` (T1 del análisis).
    assert respuesta["obtenido"]["errores"][0]["tipo"] == "servicio_no_disponible"
    assert estado.errores[Frente.NOTICIAS] == respuesta


def test_un_error_de_fuente_no_reintentable_no_es_reintentable():
    respuesta, _, _, _ = _noticias_con(_caido({**ERROR_NOTICIAS, "reintentable": False}))
    assert respuesta["causa"] == "error_de_fuente" and respuesta["reintentable"] is False


@pytest.mark.parametrize("valor", [None, "true", 1, "sí"])
def test_un_indicador_de_reintento_ausente_o_invalido_cuenta_como_no_reintentable(valor):
    error = {k: v for k, v in ERROR_NOTICIAS.items() if k != "reintentable"}
    if valor is not None:
        error["reintentable"] = valor
    respuesta, _, _, _ = _noticias_con(_caido(error))
    assert respuesta["causa"] == "error_de_fuente" and respuesta["reintentable"] is False


def test_una_terminacion_anomala_gana_al_error_de_fuente_y_no_es_reintentable():
    anomalo = _caido(ERROR_NOTICIAS)
    anomalo.terminacion = terminacion_anomala()
    respuesta, _, _, _ = _noticias_con(anomalo)
    assert respuesta["causa"] == "terminacion_anomala"
    assert respuesta["reintentable"] is False


def test_el_error_de_fuente_gana_al_resultado_invalido():
    resultado = resultado_frente(
        Frente.NOTICIAS,
        [
            consulta(Frente.NOTICIAS, {"nombre": "x"}, error=ERROR_NOTICIAS),
            consulta(Frente.NOTICIAS, {}, None, None),
        ],
    )
    resultado.consultas[1].valido = False
    resultado.consultas[1].resultado = None
    respuesta, _, _, _ = _noticias_con(resultado)
    assert respuesta["causa"] == "error_de_fuente"


def test_sin_consultas_y_resultado_invalido_tienen_su_propia_causa():
    vacio, _, _, _ = _noticias_con(resultado_frente(Frente.NOTICIAS, []))
    assert vacio["causa"] == "sin_consultas" and vacio["reintentable"] is False

    invalido = resultado_frente(Frente.NOTICIAS, [consulta(Frente.NOTICIAS, {}, None, None)])
    invalido.consultas[0].valido = False
    invalido.consultas[0].resultado = None
    respuesta, _, _, _ = _noticias_con(invalido)
    assert respuesta["causa"] == "resultado_invalido" and respuesta["reintentable"] is False


def test_listas_sin_el_representante_es_consulta_incompleta():
    listas, estado, _ = _registro_y_listas(
        [consulta_listas("comercio", identificador="CO-TV-0001")]
    )
    assert listas["causa"] == "consulta_incompleta" and listas["reintentable"] is False
    assert estado.errores[Frente.LISTAS]["causa"] == "consulta_incompleta"


def test_un_bloqueo_de_hook_no_es_causa_y_listas_queda_con_consulta_incompleta():
    consultas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta_listas("persona", nombre="Otra Persona Ficticia"),  # bloqueada por el hook (I.1)
    ]
    listas, _, _, _ = _registro_y_listas_con_eventos(consultas)
    assert listas["causa"] == "consulta_incompleta" and listas["reintentable"] is False


def test_listas_con_el_comercio_bien_y_el_representante_con_error_conserva_lo_obtenido():
    consultas = [
        consulta_listas("comercio", identificador="CO-TV-0001"),
        consulta(
            Frente.LISTAS, {"tipo": "persona", "identificador": "PE-0001"}, error=ERROR_NOTICIAS
        ),
    ]
    listas, _, _, _ = _registro_y_listas_con_eventos(consultas)
    assert listas["causa"] == "error_de_fuente"
    (obtenido,) = listas["obtenido"]["resultados"]
    assert obtenido["argumentos"] == {"tipo": "comercio", "identificador": "CO-TV-0001"}
    # Contenido y metadatos llegan separados, como los entregó la pasarela.
    assert obtenido["metadatos"]["fuentes"]
    assert all({"contenido", "metadatos"} <= set(hecho) for hecho in obtenido["hechos"])


def test_una_excepcion_del_subagente_solo_nombra_su_tipo_en_ninguna_salida():
    delegador, estado, registro, _ = _crear(
        excepciones={Frente.NOTICIAS: RuntimeError(TEXTO_INTERNO)}
    )
    respuesta = _delegar(delegador, **NOTICIAS)
    assert respuesta["causa"] == "terminacion_anomala" and respuesta["reintentable"] is False
    assert "excepción RuntimeError" in respuesta["obtenido"]["terminacion"]
    salidas = [
        json.dumps(respuesta, ensure_ascii=False),
        estado.motivo(Frente.NOTICIAS),
        json.dumps(estado.errores[Frente.NOTICIAS], ensure_ascii=False, default=str),
        estado.resultados[Frente.NOTICIAS].detalle_terminacion,
        *(e.detalle for e in registro.eventos()),
    ]
    assert all(TEXTO_INTERNO not in salida for salida in salidas)


def test_un_rechazo_sin_ejecucion_lleva_causa_rechazado_e_intento_cero():
    delegador, estado, _, ejecutor = _crear()
    respuesta = _delegar(delegador, frente="categoria")  # sin la categoría: se rechaza
    assert respuesta["tipo"] == "frente_rechazado" and respuesta["frente"] == "categoria"
    assert respuesta["causa"] == "rechazado"
    assert respuesta["intento"] == 0
    assert respuesta["reintentos_restantes"] == configuracion.MAX_REINTENTOS_POR_FRENTE
    assert respuesta["reintentable"] is False
    assert estado.errores[Frente.CATEGORIA]["causa"] == "rechazado"
    assert ejecutor.llamadas == []


def test_listas_antes_del_registro_es_rechazo_reintentable_sin_intento():
    # FR-003: el rechazo sigue siendo reintentable, como fijan los tests de listas de arriba.
    delegador, _, _, _ = _crear()
    respuesta = _delegar(delegador, **LISTAS)
    assert respuesta["causa"] == "rechazado" and respuesta["reintentable"] is True
    assert respuesta["intento"] == 0


def test_un_frente_que_despues_termina_bien_borra_su_error_del_estado():
    def noticias(contexto):
        if "Nombre Que Falla" in contexto:
            return _caido(ERROR_NOTICIAS)
        return resultado_frente(Frente.NOTICIAS)

    delegador, estado, _, _ = _crear(resultados={Frente.NOTICIAS: noticias})
    _delegar(delegador, frente="noticias", nombre="Nombre Que Falla")
    assert estado.errores[Frente.NOTICIAS]["causa"] == "error_de_fuente"
    _delegar(delegador, frente="noticias", nombre="Tienda Verde SAS")
    assert Frente.NOTICIAS not in estado.errores


def test_un_frente_cancelado_deja_la_causa_cancelado_en_el_estado():
    delegador, estado, _, _ = _crear(retardos={Frente.NOTICIAS: 5})

    async def cancelar():
        tarea = asyncio.create_task(delegador.delegar(NOTICIAS))
        await asyncio.sleep(0.05)
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea

    asyncio.run(cancelar())
    assert estado.situacion(Frente.NOTICIAS) is Situacion.NO_TERMINADO
    assert estado.errores[Frente.NOTICIAS]["causa"] == "cancelado"
    assert estado.errores[Frente.NOTICIAS]["reintentable"] is False


def test_listas_invalidada_deja_la_causa_invalidado_en_el_estado():
    delegador, estado, _, _ = _registro_cambia_de_comercio()
    _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    _delegar(delegador, frente="listas")
    _delegar(delegador, frente="registro", identificador="CO-PL-0003")
    assert estado.errores[Frente.LISTAS]["causa"] == "invalidado"


def test_una_entrada_invalida_no_es_un_error_de_frente():
    delegador, _, _, _ = _crear()
    respuesta = _delegar(delegador, frente="inventado")
    assert respuesta["tipo"] == "entrada_invalida"
    assert "frente" not in respuesta and "causa" not in respuesta
