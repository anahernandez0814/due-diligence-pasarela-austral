"""Casos del #9 de extremo a extremo: informe vigente, conflictos y registro obligatorio (FR-019).

Un `Caso` real con subagentes en sesiones simuladas y un `CoordinadorSimulado` cuyo guion pasa por
los hooks del coordinador y por la `PasarelaSimulada`, que valida el informe como la real. No se
llama al modelo. Datos ficticios del #5.
"""

import asyncio

from due_diligence.coordinador import Caso
from due_diligence.estado import Situacion
from due_diligence.eventos import TIPO_CIERRE_IMPEDIDO, TIPO_INFORME_REGISTRADO
from due_diligence.frentes import Frente
from due_diligence.simulacion import (
    CoordinadorSimulado,
    EjecutorSimulado,
    comercio_bajo_riesgo,
    consulta,
    consulta_listas,
    en_secuencia,
    error_estructurado,
    resultado_frente,
)
from due_diligence.test_casos_reglas import _resultados

NOTICIAS = {"frente": "noticias", "identificador": "CO-TA-0002"}
SOLICITUD = "Due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, talleres."
COBERTURA_CAMBIO = (
    "El informe registrado ya no está vigente: cambió la cobertura después de registrarlo. "
    "Registra uno nuevo."
)


class EjecutorConEspera(EjecutorSimulado):
    """El reintento de noticias no termina hasta que el test lo suelta (R7, corrección de la
    analista): así el reintento puede terminar entre el `PreToolUse` y el `PostToolUse` del
    informe enviado en el mismo mensaje."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.soltar = asyncio.Event()

    async def __call__(self, frente, contexto, opciones):
        if frente is Frente.NOTICIAS and self.llamadas_de(Frente.NOTICIAS):
            await self.soltar.wait()
        return await super().__call__(frente, contexto, opciones)


def _resultados_con_noticias_que_se_recuperan():
    listas = [
        consulta_listas("comercio", identificador="CO-TA-0002"),
        consulta_listas("persona", identificador="PE-0002"),
    ]
    resultados = _resultados(
        [comercio_bajo_riesgo()], "talleres", "bajo", listas, identificador="CO-TA-0002"
    )
    caida = resultado_frente(
        Frente.NOTICIAS,
        [consulta(Frente.NOTICIAS, {"identificador": "CO-TA-0002"}, error=error_estructurado())],
    )
    responde = resultado_frente(
        Frente.NOTICIAS, [consulta(Frente.NOTICIAS, {"identificador": "CO-TA-0002"})]
    )
    resultados[Frente.NOTICIAS] = en_secuencia(caida, responde)
    return resultados


def _inicio():
    return [
        (
            "delegar_paralelo",
            [
                {"frente": "registro", "identificador": "CO-TA-0002"},
                NOTICIAS,
                {"frente": "categoria", "categoria": "talleres"},
            ],
        ),
        ("delegar", {"frente": "listas"}),
        ("informe", "no_habilitar"),  # vigente: noticias no cubierto
    ]


def _ejecutar(guion, ejecutor):
    coordinador = CoordinadorSimulado(guion)
    caso = Caso(ejecutor=ejecutor, consulta=coordinador)
    coordinador.caso = caso
    return caso, coordinador


def test_un_reintento_que_termina_entre_el_pre_y_el_post_del_informe_lo_deja_sin_vigencia():
    ejecutor = EjecutorConEspera(resultados=_resultados_con_noticias_que_se_recuperan())
    guion = [
        *_inicio(),
        ("mismo_mensaje", [("delegar", NOTICIAS), ("informe", "no_habilitar")]),
        ("terminar",),
        ("informe", "no_habilitar"),
        ("terminar",),
    ]
    caso, coordinador = _ejecutar(guion, ejecutor)
    registrar = coordinador.pasarela.herramientas["mcp__pasarela__registrar_informe"]

    async def registrar_tras_el_reintento(entrada):
        # El `PreToolUse` del informe ya calculó su huella con noticias en curso. Se suelta el
        # reintento y se espera a que termine antes de que la pasarela responda y corra el Post.
        if caso.estado.situacion(Frente.NOTICIAS) is Situacion.EN_CURSO:
            ejecutor.soltar.set()
            for _ in range(10_000):
                if caso.estado.situacion(Frente.NOTICIAS) is Situacion.TERMINADO:
                    break
                await asyncio.sleep(0)
        return registrar(entrada)

    coordinador.pasarela.herramientas["mcp__pasarela__registrar_informe"] = (
        registrar_tras_el_reintento
    )
    asyncio.run(caso.ejecutar(SOLICITUD))

    # El informe del mismo mensaje se registró con noticias sin cubrir, y su huella es la del Pre.
    _, del_mismo_mensaje, _ = caso.estado.informes
    assert dict(del_mismo_mensaje.huella.cobertura)["noticias"] is False
    assert caso.estado.situacion(Frente.NOTICIAS) is Situacion.TERMINADO
    # El Stop ve que cambió la cobertura y exige un informe nuevo; con él, el caso cierra.
    primer_cierre, segundo_cierre = coordinador.resultados_de("terminar")
    assert primer_cierre.termino is False and primer_cierre.motivo == COBERTURA_CAMBIO
    assert segundo_cierre.termino is True
    tipos = [e.tipo for e in caso.eventos()]
    assert tipos.count(TIPO_INFORME_REGISTRADO) == 3
    assert tipos.count(TIPO_CIERRE_IMPEDIDO) == 1
    assert caso.estado.cierre_sin_informe is False


def test_si_el_reintento_termina_antes_del_pre_el_informe_queda_vigente():
    # Contraste: con el reintento ya terminado, la huella del informe incluye noticias cubierto.
    ejecutor = EjecutorSimulado(resultados=_resultados_con_noticias_que_se_recuperan())
    guion = [*_inicio(), ("delegar", NOTICIAS), ("informe", "no_habilitar"), ("terminar",)]
    caso, coordinador = _ejecutar(guion, ejecutor)
    asyncio.run(caso.ejecutar(SOLICITUD))
    ultimo = caso.estado.informes[-1]
    assert dict(ultimo.huella.cobertura)["noticias"] is True
    (cierre,) = coordinador.resultados_de("terminar")
    assert cierre.termino is True
    assert TIPO_CIERRE_IMPEDIDO not in [e.tipo for e in caso.eventos()]
