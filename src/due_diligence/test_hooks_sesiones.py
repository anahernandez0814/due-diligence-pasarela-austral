"""Tests de los hooks con sesiones separadas por agente (US1 a US5, R4, R5, FR-010).

Cada agente es una `SesionSimulada` con las opciones que `HooksDelCaso` le da y la
`PasarelaSimulada` con los datos ficticios del #5. Lo compartido es el estado del caso; los hooks
van por agente. Ningún test llama al modelo.
"""

import asyncio
import json

from due_diligence import configuracion
from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.eventos import TIPO_BLOQUEO_REGLA, RegistroEventos
from due_diligence.frentes import FRENTES, Frente
from due_diligence.hooks import HooksDelCaso
from due_diligence.simulacion import (
    PasarelaSimulada,
    SesionSimulada,
    comercio_alto_riesgo,
    comercios_parecidos,
)

REGISTRO = FRENTES[Frente.REGISTRO].herramienta_completa
LISTAS = FRENTES[Frente.LISTAS].herramienta_completa
DELEGAR = "mcp__delegacion__delegar_frente"


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
        return SesionSimulada(opciones, herramientas or {DELEGAR: lambda e: {"frente": "x"}})

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
