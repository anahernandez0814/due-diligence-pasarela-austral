"""Tests de los hooks con sesiones separadas por agente (US1 a US5, R4, R5, FR-010).

Cada agente es una `SesionSimulada` con las opciones que `HooksDelCaso` le da y la
`PasarelaSimulada` con los datos ficticios del #5. Lo compartido es el estado del caso; los hooks
van por agente. Ningún test llama al modelo.
"""

import asyncio
import json

from due_diligence import configuracion
from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_CIERRE_IMPEDIDO,
    TIPO_CIERRE_SIN_ESCALAR,
    RegistroEventos,
)
from due_diligence.frentes import FRENTES, Frente
from due_diligence.hooks import HooksDelCaso
from due_diligence.simulacion import (
    PasarelaSimulada,
    SesionSimulada,
    comercio_alto_riesgo,
    comercio_bajo_riesgo,
    comercio_con_representante_en_listas,
    comercios_parecidos,
    error_estructurado,
)

REGISTRO = FRENTES[Frente.REGISTRO].herramienta_completa
LISTAS = FRENTES[Frente.LISTAS].herramienta_completa
DELEGAR = "mcp__delegacion__delegar_frente"
MAX_CIERRES_IMPEDIDOS = configuracion.MAX_CIERRES_IMPEDIDOS
INFORME = "mcp__pasarela__registrar_informe"
RIESGO = FRENTES[Frente.CATEGORIA].herramienta_completa
ESCALAR = "mcp__pasarela__escalar_a_cumplimiento"


class Caso:
    """Un estado, sus eventos y las sesiones de los agentes, sobre una misma pasarela simulada."""

    def __init__(self, **datos):
        self.estado = EstadoCaso("solicitud")
        self.eventos = RegistroEventos()
        self.hooks = HooksDelCaso(self.estado, self.eventos)
        self.pasarela = PasarelaSimulada(**datos)

    def sesion(self, frente, herramientas=None):
        opciones = configuracion.opciones_subagente(
            frente, "instrucciones", hooks=self.hooks.subagente(frente)
        )
        return SesionSimulada(opciones, herramientas or self.pasarela.herramientas)

    def sesion_del_coordinador(self, herramientas=None):
        opciones = configuracion.opciones_coordinador(
            {"type": "sdk", "name": "delegacion", "instance": object()},
            "instrucciones",
            hooks=self.hooks.coordinador(),
        )
        por_defecto = {**self.pasarela.herramientas, DELEGAR: lambda e: {"frente": "x"}}
        return SesionSimulada(opciones, herramientas or por_defecto)

    def coordinador(self):
        """La sesión del coordinador, la misma durante todo el caso."""
        if not hasattr(self, "_coordinador"):
            self._coordinador = self.sesion_del_coordinador()
        return self._coordinador

    def informe(self, recomendacion):
        entrada = {
            "comercio": {"identificador": "CO-PL-0003", "nombre": "Panadería Luna Nueva SAS"},
            "recomendacion": recomendacion,
            "hallazgos": {},
            "cobertura": "completa",
        }
        return asyncio.run(self.coordinador().llamar(INFORME, entrada))

    def terminar(self, mensaje="listo"):
        return asyncio.run(self.coordinador().terminar(mensaje))

    def escalar(self):
        return asyncio.run(self.coordinador().llamar(ESCALAR, {"causa_escalamiento": "x"}))

    def registrar(self, **consulta):
        """El subagente de registro consulta y el frente termina (lo que haría el `Delegador`)."""
        sesion = self.sesion(Frente.REGISTRO)
        asyncio.run(sesion.llamar(REGISTRO, consulta, en_proceso=False))
        self.estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
        self.estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)

    def listas(self, **consulta):
        return asyncio.run(self.sesion(Frente.LISTAS).llamar(LISTAS, consulta))

    def delegar_listas(self):
        sesion = self.sesion_del_coordinador()
        return asyncio.run(sesion.llamar(DELEGAR, {"frente": "listas"}, en_proceso=True))

    def riesgo(self, categoria):
        sesion = self.sesion(Frente.CATEGORIA)
        return asyncio.run(sesion.llamar(RIESGO, {"categoria": categoria}))

    def consultas_de_listas(self):
        return [e for fuente, e in self.pasarela.consultas_a_fuentes if fuente == "listas"]


# --------------------------------------------------------- US1: la regla I.1 de extremo a extremo


def test_con_un_comercio_identificado_listas_consulta_al_comercio_y_al_representante():
    caso = Caso(registro=[comercio_alto_riesgo()])
    caso.registrar(identificador="CO-TV-0001")
    por_el_comercio = caso.listas(tipo="comercio", identificador="CO-TV-0001")
    por_el_representante = caso.listas(tipo="persona", identificador="PE-0001")
    assert por_el_comercio.ejecutada and por_el_representante.ejecutada
    assert len(caso.consultas_de_listas()) == 2
    assert not caso.delegar_listas().denegada
    assert caso.eventos.eventos() == []


def test_con_dos_comercios_parecidos_no_se_consulta_listas_ni_se_delega():
    caso = Caso(registro=comercios_parecidos())
    caso.registrar(nombre="Almacén Mirador")
    bloqueada = caso.listas(tipo="comercio", identificador="CO-AM-0004")
    assert bloqueada.denegada and not bloqueada.ejecutada
    assert "varias coincidencias" in bloqueada.motivo
    assert caso.consultas_de_listas() == []  # la fuente de listas no se consultó
    delegacion = caso.delegar_listas()
    assert delegacion.denegada and "pida el identificador al analista" in delegacion.motivo
    reglas = [(e.tipo, e.regla) for e in caso.eventos.eventos()]
    assert reglas == [(TIPO_BLOQUEO_REGLA, "I.1"), (TIPO_BLOQUEO_REGLA, "I.1")]


def test_con_el_registro_sin_coincidencias_se_bloquea_la_consulta_y_la_delegacion():
    caso = Caso(registro=[comercio_alto_riesgo()])
    caso.registrar(nombre="Nada Parecido")
    assert caso.listas(tipo="comercio", nombre="Tienda Verde SAS").denegada
    assert caso.consultas_de_listas() == []
    assert caso.delegar_listas().denegada


def test_una_consulta_por_un_nombre_ajeno_se_bloquea_aunque_haya_comercio():
    caso = Caso(registro=[comercio_alto_riesgo()])
    caso.registrar(identificador="CO-TV-0001")
    ajena = caso.listas(tipo="persona", nombre="Mateo Ríos Cabrera")
    assert ajena.denegada and not ajena.ejecutada
    assert caso.consultas_de_listas() == []
    assert "Mateo" not in json.dumps([e.detalle for e in caso.eventos.eventos()])


def test_antes_de_que_el_registro_responda_se_bloquea_listas():
    caso = Caso(registro=[comercio_alto_riesgo()])
    assert caso.listas(tipo="comercio", identificador="CO-TV-0001").denegada
    assert caso.delegar_listas().denegada  # el registro ni siquiera se delegó


# ---------------------------------------- US2: coincidencia en listas de extremo a extremo (caso c)


def _caso_c():
    caso = Caso(
        registro=[comercio_con_representante_en_listas()], en_listas={"persona": {"PE-0003"}}
    )
    caso.registrar(identificador="CO-PL-0003")
    assert caso.listas(tipo="comercio", identificador="CO-PL-0003").ejecutada
    assert caso.listas(tipo="persona", identificador="PE-0003").ejecutada
    return caso


def test_caso_c_habilitar_se_rechaza_y_solo_se_acepta_el_informe_tras_escalar():
    caso = _caso_c()
    assert [c.causa for c in caso.estado.libro.coincidencias] == ["coincidencia_representante"]

    habilitar = caso.informe("habilitar")
    assert habilitar.denegada and not habilitar.ejecutada
    assert "no se puede recomendar habilitar" in habilitar.motivo
    sin_escalar = caso.informe("no_habilitar")  # tampoco se acepta sin escalar
    assert sin_escalar.denegada and "aún no se ha escalado" in sin_escalar.motivo
    assert caso.pasarela.informes == []  # ningún informe llegó al servidor

    assert caso.escalar().ejecutada
    assert caso.estado.libro.escalamientos == [frozenset({"coincidencia_representante"})]

    assert caso.informe("habilitar").denegada  # escalar no habilita
    aceptado = caso.informe("decide_cumplimiento")
    assert aceptado.ejecutada and not aceptado.denegada
    assert caso.informe("no_habilitar").ejecutada
    assert len(caso.pasarela.informes) == 2


def test_caso_c_los_rechazos_llevan_la_regla_i2_en_el_evento_y_sin_datos_consultados():
    caso = _caso_c()
    caso.riesgo("panaderías")  # bajo riesgo y determinada: el único motivo es la coincidencia
    caso.informe("habilitar")
    (evento,) = [e for e in caso.eventos.eventos() if e.tipo == TIPO_BLOQUEO_REGLA]
    assert evento.regla == "I.2"
    for dato in ("PE-0003", "Ernesto", "CO-PL-0003", "Panadería"):
        assert dato not in evento.detalle


def test_un_escalamiento_con_error_no_cubre_el_caso():
    caso = _caso_c()
    sesion = caso.sesion_del_coordinador(
        {
            **caso.pasarela.herramientas,
            ESCALAR: lambda e: error_estructurado("campos_obligatorios_ausentes", False),
        }
    )
    caso._coordinador = sesion
    assert caso.escalar().es_error
    assert caso.estado.libro.escalamientos == []
    assert caso.informe("decide_cumplimiento").denegada


# --------------------------------------- US3: alto riesgo y bajo riesgo de extremo a extremo (a, b)


def test_caso_a_alto_riesgo_no_se_habilita_y_exige_escalar_antes_de_cualquier_informe():
    caso = Caso(registro=[comercio_alto_riesgo()])
    caso.registrar(identificador="CO-TV-0001")
    assert caso.listas(tipo="comercio", identificador="CO-TV-0001").ejecutada
    assert caso.listas(tipo="persona", identificador="PE-0001").ejecutada
    assert caso.riesgo("suplementos dietarios").ejecutada
    assert [c.categoria for c in caso.estado.libro.consultas_riesgo] == ["suplementos dietarios"]

    habilitar = caso.informe("habilitar")
    assert habilitar.denegada and "decisión es de un oficial de cumplimiento" in habilitar.motivo
    assert caso.informe("no_habilitar").denegada  # sin escalar tampoco se acepta
    assert caso.pasarela.informes == []

    assert caso.escalar().ejecutada
    assert caso.estado.libro.escalamientos == [frozenset({"alto_riesgo"})]
    assert caso.informe("habilitar").denegada  # escalar no habilita
    assert caso.informe("decide_cumplimiento").ejecutada
    assert len(caso.pasarela.informes) == 1
    rechazos = [e for e in caso.eventos.eventos() if e.tipo == TIPO_BLOQUEO_REGLA]
    assert {e.regla for e in rechazos} == {"I.3"}


def test_caso_a_sin_categoria_determinada_no_se_puede_habilitar():
    caso = Caso(registro=[comercio_alto_riesgo()])
    caso.registrar(identificador="CO-TV-0001")
    caso.listas(tipo="comercio", identificador="CO-TV-0001")
    caso.listas(tipo="persona", identificador="PE-0001")
    sin_consultar = caso.informe("habilitar")
    assert (
        sin_consultar.denegada
        and "La categoría del caso no quedó determinada" in sin_consultar.motivo
    )
    caso.riesgo("algo raro")  # desconocida: sigue sin determinarse
    assert caso.informe("habilitar").denegada


def test_caso_b_bajo_riesgo_sin_hallazgos_se_habilita_sin_escalar():
    caso = Caso(registro=[comercio_bajo_riesgo()])
    caso.registrar(identificador="CO-TA-0002")
    assert caso.listas(tipo="comercio", identificador="CO-TA-0002").ejecutada
    assert caso.listas(tipo="persona", identificador="PE-0002").ejecutada
    assert caso.riesgo("talleres").ejecutada

    aceptado = caso.informe("habilitar")
    assert aceptado.ejecutada and not aceptado.denegada
    assert len(caso.pasarela.informes) == 1
    assert caso.estado.libro.escalamientos == [] and caso.estado.libro.coincidencias == []
    assert [e for e in caso.eventos.eventos() if e.tipo == TIPO_BLOQUEO_REGLA] == []


def test_habilitar_sin_haber_consultado_listas_se_rechaza_aunque_el_riesgo_sea_bajo():
    caso = Caso(registro=[comercio_bajo_riesgo()])
    caso.registrar(identificador="CO-TA-0002")
    caso.riesgo("talleres")
    rechazado = caso.informe("habilitar")
    assert rechazado.denegada and "Falta la consulta de listas restrictivas" in rechazado.motivo


# --------------------------------------------- US4: el cierre garantizado de extremo a extremo


def test_un_caso_con_coincidencia_no_termina_hasta_que_se_escala():
    caso = _caso_c()
    sin_escalar = caso.terminar()
    assert sin_escalar.termino is False
    assert "coincidencia del representante legal en listas restrictivas" in sin_escalar.motivo
    assert caso.terminar().termino is False  # insiste y se le sigue devolviendo
    assert caso.escalar().ejecutada
    assert caso.terminar("ya escalé").termino is True
    assert caso.estado.cierre_sin_escalar is False
    tipos = [e.tipo for e in caso.eventos.eventos()]
    assert tipos.count(TIPO_CIERRE_IMPEDIDO) == 2 and TIPO_CIERRE_SIN_ESCALAR not in tipos


def test_un_caso_de_alto_riesgo_tampoco_termina_sin_escalar():
    caso = Caso(registro=[comercio_alto_riesgo()])
    caso.registrar(identificador="CO-TV-0001")
    caso.riesgo("suplementos dietarios")
    cierre = caso.terminar()
    assert cierre.termino is False and "categoría de alto riesgo" in cierre.motivo
    caso.escalar()
    assert caso.terminar().termino is True


def test_un_caso_de_bajo_riesgo_sin_hallazgos_termina_sin_trabas():
    caso = Caso(registro=[comercio_bajo_riesgo()])
    caso.registrar(identificador="CO-TA-0002")
    caso.riesgo("talleres")
    assert caso.terminar().termino is True
    assert caso.eventos.eventos() == []


def test_un_coordinador_que_insiste_en_terminar_sin_escalar_termina_marcado_y_no_completo():
    caso = _caso_c()
    devoluciones = [caso.terminar() for _ in range(MAX_CIERRES_IMPEDIDOS)]
    assert [d.termino for d in devoluciones] == [False] * MAX_CIERRES_IMPEDIDOS
    ultimo = caso.terminar()
    assert ultimo.termino is True  # se agotaron las oportunidades
    assert caso.estado.cierre_sin_escalar is True
    assert caso.estado.libro.escalamientos == []  # y nunca se escaló
    assert caso.pasarela.escalamientos == []
    assert caso.informe("habilitar").denegada  # el caso sigue sin poder habilitarse
    tipos = [e.tipo for e in caso.eventos.eventos()]
    assert tipos.count(TIPO_CIERRE_IMPEDIDO) == MAX_CIERRES_IMPEDIDOS
    assert TIPO_CIERRE_SIN_ESCALAR in tipos


def test_el_fin_de_turno_de_un_subagente_no_se_bloquea():
    caso = _caso_c()
    for frente in Frente:
        sesion = caso.sesion(frente)
        assert asyncio.run(sesion.terminar("listo")).termino is True
