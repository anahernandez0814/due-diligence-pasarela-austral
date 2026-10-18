"""Tests de la política de reintento (#8, R3, contrato `delegar-frente.md`; FR-005 a FR-009,
US3-1 a US3-6, SC-002).

El reintento lo pide el modelo volviendo a delegar el frente con la misma entrada; el `Delegador`
decide si se ejecuta. Con el ejecutor simulado: ninguno llama al modelo.
"""

import asyncio

from due_diligence import configuracion
from due_diligence.delegacion import DESCRIPCION, Delegador
from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_DELEGACION_REPETIDA,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INVALIDADO,
    TIPO_FRENTE_REINTENTO,
    TIPO_REINTENTO_DENEGADO,
    RegistroEventos,
)
from due_diligence.frentes import Frente
from due_diligence.hooks import HooksDelCaso
from due_diligence.simulacion import (
    EjecutorSimulado,
    comercio_del_registro,
    consulta,
    consulta_listas,
    en_secuencia,
    error_estructurado,
    resultado_frente,
    resultado_listas,
    resultado_registro,
)

NOTICIAS = {"frente": "noticias", "identificador": "CO-TV-0001"}
REGISTRO = {"frente": "registro", "identificador": "CO-TV-0001"}
LISTAS = {"frente": "listas"}
REINTENTABLE = error_estructurado("servicio_no_disponible", True)
NO_REINTENTABLE = error_estructurado("datos_no_disponibles", False)


def _crear(**kwargs):
    estado, registro, ejecutor = (
        EstadoCaso("solicitud"),
        RegistroEventos(),
        EjecutorSimulado(**kwargs),
    )
    hooks = HooksDelCaso(estado, registro)
    delegador = Delegador(
        estado,
        registro,
        ejecutor,
        lambda frente: configuracion.opciones_subagente(
            frente, "instrucciones", hooks=hooks.subagente(frente)
        ),
    )
    return delegador, estado, registro, ejecutor


def _delegar(delegador, entrada):
    return asyncio.run(delegador.delegar(entrada))


def _caido(error, frente=Frente.NOTICIAS, argumentos=None):
    return resultado_frente(frente, [consulta(frente, argumentos or {"nombre": "x"}, error=error)])


def _eventos(registro, tipo, frente=Frente.NOTICIAS):
    return [e for e in registro.eventos() if e.tipo == tipo and e.frente is frente]


# ------------------------------------------------------------------ US3-1 y US3-2


def test_un_error_reintentable_se_vuelve_a_ejecutar_y_el_frente_queda_cubierto():
    delegador, estado, registro, ejecutor = _crear(
        resultados={
            Frente.NOTICIAS: en_secuencia(_caido(REINTENTABLE), resultado_frente(Frente.NOTICIAS))
        }
    )
    primera = _delegar(delegador, NOTICIAS)
    assert primera["reintentable"] is True and primera["intento"] == 1
    assert primera["reintentos_restantes"] == 1

    segunda = _delegar(delegador, NOTICIAS)

    assert len(ejecutor.llamadas_de(Frente.NOTICIAS)) == 2
    assert segunda["situacion"] == "terminado"
    assert estado.situacion(Frente.NOTICIAS) is Situacion.TERMINADO
    assert Frente.NOTICIAS not in estado.errores
    # Los eventos conservan la falla anterior (FR-009).
    fines = _eventos(registro, TIPO_FRENTE_FIN)
    assert len(fines) == 2 and "no_terminado" in fines[0].detalle
    (reintento,) = _eventos(registro, TIPO_FRENTE_REINTENTO)
    assert "1 de 1" in reintento.detalle
    assert "servicio_no_disponible" in reintento.detalle
    assert reintento.secuencia > fines[0].secuencia


# ------------------------------------------------------------------ US3-3


def test_un_error_no_reintentable_no_se_vuelve_a_ejecutar():
    delegador, _, registro, ejecutor = _crear(resultados={Frente.NOTICIAS: _caido(NO_REINTENTABLE)})
    primera = _delegar(delegador, NOTICIAS)
    segunda = _delegar(delegador, NOTICIAS)

    assert len(ejecutor.llamadas_de(Frente.NOTICIAS)) == 1
    assert segunda["causa"] == primera["causa"] == "error_de_fuente"
    assert segunda["mensaje"] == primera["mensaje"]
    assert segunda["reintentable"] is False and segunda["reintentos_restantes"] == 0
    (denegado,) = _eventos(registro, TIPO_REINTENTO_DENEGADO)
    assert "no es reintentable" in denegado.detalle
    assert _eventos(registro, TIPO_FRENTE_REINTENTO) == []


# ------------------------------------------------------------------ US3-4


def test_un_error_reintentable_persistente_se_detiene_en_el_limite():
    delegador, estado, registro, ejecutor = _crear(
        resultados={Frente.NOTICIAS: _caido(REINTENTABLE)}
    )
    primera = _delegar(delegador, NOTICIAS)
    segunda = _delegar(delegador, NOTICIAS)
    tercera = _delegar(delegador, NOTICIAS)

    assert len(ejecutor.llamadas_de(Frente.NOTICIAS)) == 1 + configuracion.MAX_REINTENTOS_POR_FRENTE
    assert primera["reintentable"] is True
    # La respuesta del último intento permitido ya dice que no hay otro (R3).
    assert segunda["intento"] == 2 and segunda["reintentos_restantes"] == 0
    assert segunda["reintentable"] is False
    assert tercera["reintentable"] is False and tercera["reintentos_restantes"] == 0
    (denegado,) = _eventos(registro, TIPO_REINTENTO_DENEGADO)
    assert "se agotaron los reintentos" in denegado.detalle
    assert estado.situacion(Frente.NOTICIAS) is Situacion.NO_TERMINADO


# ------------------------------------------------------------------ US3-5 y US3-6


def test_un_frente_terminado_devuelve_lo_guardado_y_no_es_un_reintento():
    delegador, _, registro, ejecutor = _crear()
    primera = _delegar(delegador, NOTICIAS)
    segunda = _delegar(delegador, NOTICIAS)
    assert segunda == primera and len(ejecutor.llamadas_de(Frente.NOTICIAS)) == 1
    assert len(_eventos(registro, TIPO_DELEGACION_REPETIDA)) == 1
    assert _eventos(registro, TIPO_FRENTE_REINTENTO) == []


def test_otra_entrada_es_una_delegacion_nueva_con_su_propio_reintento():
    def categoria(contexto):
        return _caido(REINTENTABLE, Frente.CATEGORIA, {"categoria": "c"})

    delegador, _, registro, ejecutor = _crear(resultados={Frente.CATEGORIA: categoria})
    primera_entrada = {"frente": "categoria", "categoria": "venta de ropa en línea"}
    otra_entrada = {"frente": "categoria", "categoria": "ropa y accesorios"}
    _delegar(delegador, primera_entrada)
    _delegar(delegador, primera_entrada)  # agota el reintento de esta entrada
    assert _delegar(delegador, primera_entrada)["reintentable"] is False

    nueva = _delegar(delegador, otra_entrada)
    assert len(ejecutor.llamadas_de(Frente.CATEGORIA)) == 3
    assert nueva["intento"] == 1 and nueva["reintentable"] is True
    _delegar(delegador, otra_entrada)
    assert len(ejecutor.llamadas_de(Frente.CATEGORIA)) == 4
    assert len(_eventos(registro, TIPO_FRENTE_REINTENTO, Frente.CATEGORIA)) == 2


# ------------------------------------------------------------------ casos límite


def test_dos_pedidos_simultaneos_ejecutan_una_vez_y_no_consumen_el_reintento():
    delegador, _, _, ejecutor = _crear(
        resultados={Frente.NOTICIAS: _caido(REINTENTABLE)}, retardos={Frente.NOTICIAS: 0.05}
    )

    async def a_la_vez():
        return await asyncio.gather(delegador.delegar(NOTICIAS), delegador.delegar(NOTICIAS))

    primera, segunda = asyncio.run(a_la_vez())
    assert len(ejecutor.llamadas_de(Frente.NOTICIAS)) == 1
    assert primera == segunda
    # El reintento sigue disponible: lo pide el modelo después, no un pedido simultáneo.
    assert _delegar(delegador, NOTICIAS)["intento"] == 2
    assert len(ejecutor.llamadas_de(Frente.NOTICIAS)) == 2


def test_un_rechazo_sin_ejecucion_no_cuenta_como_intento():
    caida = resultado_listas(
        [
            consulta_listas("comercio", identificador="CO-TV-0001"),
            consulta(
                Frente.LISTAS, {"tipo": "persona", "identificador": "PE-0001"}, error=REINTENTABLE
            ),
        ]
    )
    delegador, _, _, ejecutor = _crear(resultados={Frente.LISTAS: caida})
    rechazo = _delegar(delegador, LISTAS)  # antes del registro: se rechaza sin ejecutar
    assert rechazo["intento"] == 0 and ejecutor.llamadas_de(Frente.LISTAS) == []

    _delegar(delegador, REGISTRO)
    listas = _delegar(delegador, LISTAS)
    assert len(ejecutor.llamadas_de(Frente.LISTAS)) == 1
    assert listas["intento"] == 1 and listas["reintentable"] is True


def test_si_el_registro_cambia_de_comercio_listas_empieza_de_nuevo_en_el_intento_uno():
    otro = comercio_del_registro(
        "CO-PL-0003",
        "Pago Latino SAS",
        {"nombre": "Mario Quispe Vargas", "identificador": "PE-0099"},
    )
    registros = iter([resultado_registro(), resultado_registro([otro])])

    def listas(contexto):
        persona = "PE-0099" if "CO-PL-0003" in contexto else "PE-0001"
        comercio = "CO-PL-0003" if "CO-PL-0003" in contexto else "CO-TV-0001"
        return resultado_listas(
            [
                consulta_listas("comercio", identificador=comercio),
                consulta(
                    Frente.LISTAS, {"tipo": "persona", "identificador": persona}, error=REINTENTABLE
                ),
            ]
        )

    delegador, _, _, ejecutor = _crear(
        resultados={Frente.REGISTRO: lambda contexto: next(registros), Frente.LISTAS: listas}
    )
    _delegar(delegador, REGISTRO)
    assert _delegar(delegador, LISTAS)["intento"] == 1
    _delegar(delegador, {"frente": "registro", "identificador": "CO-PL-0003"})
    nueva = _delegar(delegador, LISTAS)
    assert nueva["intento"] == 1 and len(ejecutor.llamadas_de(Frente.LISTAS)) == 2


def test_el_reintento_de_listas_vuelve_a_pasar_por_el_hook_de_la_consulta_de_listas():
    # Caso límite de la spec: un reintento de listas no se salta la regla I.1.
    caida = resultado_listas(
        [
            consulta_listas("comercio", identificador="CO-TV-0001"),
            consulta(
                Frente.LISTAS, {"tipo": "persona", "identificador": "PE-0001"}, error=REINTENTABLE
            ),
        ]
    )
    exito_con_una_de_mas = resultado_listas(
        [
            consulta_listas("comercio", identificador="CO-TV-0001"),
            consulta_listas("persona", identificador="PE-0001"),
            consulta_listas("persona", nombre="Otra Persona Ficticia"),  # el hook la bloquea
        ]
    )
    delegador, estado, registro, ejecutor = _crear(
        resultados={Frente.LISTAS: en_secuencia(caida, exito_con_una_de_mas)}
    )
    _delegar(delegador, REGISTRO)
    assert _delegar(delegador, LISTAS)["reintentable"] is True

    reintento = _delegar(delegador, LISTAS)

    llamadas = ejecutor.llamadas_de(Frente.LISTAS)
    assert len(llamadas) == 2 and "PreToolUse" in llamadas[1].opciones.hooks
    assert reintento["situacion"] == "terminado"
    (marca,) = _eventos(registro, TIPO_FRENTE_REINTENTO, Frente.LISTAS)
    bloqueos = [e for e in registro.eventos() if e.tipo == TIPO_BLOQUEO_REGLA]
    assert [(e.regla, e.frente) for e in bloqueos] == [("I.1", Frente.LISTAS)]
    assert bloqueos[0].secuencia > marca.secuencia  # el bloqueo es del reintento
    assert estado.situacion(Frente.LISTAS) is Situacion.TERMINADO


def test_un_reintento_del_registro_que_identifica_otro_comercio_deja_listas_invalidada():
    # Solo hay comercio con el registro terminado: para reintentarlo, antes tiene que fallar, y esa
    # falla ya invalida listas. El reintento identifica otro comercio y listas sigue invalidada
    # hasta que se vuelve a delegar, ahora con el comercio nuevo.
    caido = _caido(REINTENTABLE, Frente.REGISTRO, {"identificador": "CO-PL-0003"})
    otro = comercio_del_registro(
        "CO-PL-0003",
        "Pago Latino SAS",
        {"nombre": "Mario Quispe Vargas", "identificador": "PE-0099"},
    )

    def listas(contexto):
        if "CO-PL-0003" in contexto:
            return resultado_listas(
                [
                    consulta_listas("comercio", identificador="CO-PL-0003"),
                    consulta_listas("persona", identificador="PE-0099"),
                ]
            )
        return resultado_listas()

    delegador, estado, registro, ejecutor = _crear(
        resultados={
            Frente.REGISTRO: en_secuencia(resultado_registro(), caido, resultado_registro([otro])),
            Frente.LISTAS: listas,
        }
    )
    otra_entrada = {"frente": "registro", "identificador": "CO-PL-0003"}
    _delegar(delegador, REGISTRO)
    assert _delegar(delegador, LISTAS)["situacion"] == "terminado"
    assert _delegar(delegador, otra_entrada)["reintentable"] is True
    assert estado.situacion(Frente.LISTAS) is Situacion.NO_TERMINADO

    reintento = _delegar(delegador, otra_entrada)

    assert reintento["situacion"] == "terminado"
    assert len(_eventos(registro, TIPO_FRENTE_REINTENTO, Frente.REGISTRO)) == 1
    assert estado.comercio["identificador"] == "CO-PL-0003"
    assert estado.situacion(Frente.LISTAS) is Situacion.NO_TERMINADO
    assert estado.errores[Frente.LISTAS]["causa"] == "invalidado"
    assert _eventos(registro, TIPO_FRENTE_INVALIDADO, Frente.LISTAS)
    assert len(ejecutor.llamadas_de(Frente.LISTAS)) == 1

    nueva = _delegar(delegador, LISTAS)
    assert nueva["situacion"] == "terminado"
    assert len(ejecutor.llamadas_de(Frente.LISTAS)) == 2
    assert "CO-PL-0003" in ejecutor.llamadas_de(Frente.LISTAS)[1].contexto


def test_si_el_reintento_falla_con_un_error_no_reintentable_no_hay_mas():
    delegador, _, registro, ejecutor = _crear(
        resultados={Frente.NOTICIAS: en_secuencia(_caido(REINTENTABLE), _caido(NO_REINTENTABLE))}
    )
    _delegar(delegador, NOTICIAS)
    segunda = _delegar(delegador, NOTICIAS)
    assert segunda["reintentable"] is False
    tercera = _delegar(delegador, NOTICIAS)
    assert tercera["reintentable"] is False
    assert len(ejecutor.llamadas_de(Frente.NOTICIAS)) == 2
    assert len(_eventos(registro, TIPO_REINTENTO_DENEGADO)) == 1


def test_la_descripcion_explica_el_pedido_repetido():
    assert "reintentable true" in DESCRIPCION
    assert "una vez más" in DESCRIPCION
    assert "reintentable false" in DESCRIPCION
