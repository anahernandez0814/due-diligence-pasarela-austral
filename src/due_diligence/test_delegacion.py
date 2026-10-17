"""Tests de la herramienta `delegar_frente` (contrato `delegacion.md`, R4, FR-001, FR-013).

Con un ejecutor simulado: ninguno llama al modelo.
"""

import asyncio
import json

import pytest

from due_diligence.delegacion import Delegador
from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.eventos import (
    TIPO_DELEGACION,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
    TIPO_FRENTE_RECHAZADO,
    RegistroEventos,
)
from due_diligence.frentes import Frente
from due_diligence.simulacion import (
    EjecutorSimulado,
    consulta,
    resultado_frente,
    terminacion_anomala,
)

ERROR_NOTICIAS = {
    "error": True,
    "tipo": "servicio_no_disponible",
    "mensaje": "El servicio de noticias no responde.",
    "reintentable": True,
    "obtenido": {},
}


def _crear(**kwargs):
    estado, registro, ejecutor = (
        EstadoCaso("solicitud"),
        RegistroEventos(),
        EjecutorSimulado(**kwargs),
    )
    delegador = Delegador(estado, registro, ejecutor, lambda frente: ("opciones", frente))
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
    assert ejecutor.llamadas[0].opciones == ("opciones", Frente.REGISTRO)
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


def test_un_frente_terminado_no_lanza_un_segundo_subagente_y_devuelve_lo_guardado():
    delegador, _, _, ejecutor = _crear()
    primera = _delegar(delegador, frente="registro", identificador="CO-TV-0001")
    segunda = _delegar(delegador, frente="registro", identificador="CO-OTRO-9999")
    assert segunda == primera
    assert len(ejecutor.llamadas) == 1


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
