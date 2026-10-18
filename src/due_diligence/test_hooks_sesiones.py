"""Tests de los hooks con sesiones separadas por agente (US1 a US5, R4, R5, FR-010).

Cada agente es una `SesionSimulada` con las opciones que `HooksDelCaso` le da y la
`PasarelaSimulada` con los datos ficticios del #5. Lo compartido es el estado del caso; los hooks
van por agente. Ningún test llama al modelo.
"""

import asyncio
import json

from due_diligence import configuracion
from due_diligence.coordinador import Caso as CasoReal
from due_diligence.estado import Consulta, EstadoCaso, Situacion
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_CIERRE_IMPEDIDO,
    TIPO_CIERRE_SIN_ESCALAR,
    TIPO_CIERRE_SIN_INFORME,
    TIPO_COBERTURA_SUSTITUIDA,
    TIPO_DATOS_SUSTITUIDOS,
    TIPO_INFORME_REGISTRADO,
    RegistroEventos,
)
from due_diligence.frentes import FRENTES, Frente
from due_diligence.hooks import HooksDelCaso
from due_diligence.libro import Escalamiento
from due_diligence.simulacion import (
    CoordinadorSimulado,
    EjecutorSimulado,
    PasarelaSimulada,
    SesionSimulada,
    comercio_alto_riesgo,
    comercio_bajo_riesgo,
    comercio_con_representante_en_listas,
    comercios_parecidos,
    error_estructurado,
    informe_del_caso,
    resumen_del_caso,
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
        """Un informe válido del #9: una afirmación por consulta del caso (R12, hallazgo U1)."""
        entrada = informe_del_caso(self.estado, recomendacion)
        return asyncio.run(self.coordinador().llamar(INFORME, entrada))

    def _guardar_consulta(self, frente, herramienta, argumentos, llamada):
        """Lo que hace el `Delegador` en producción: la consulta válida queda en `estado.consultas`.

        FR-004 y los conflictos (#9) leen de ahí; sin esto, los hooks no verían ninguna fuente.
        """
        if llamada.ejecutada and not llamada.es_error:
            resultado = json.loads(llamada.texto)
            self.estado.agregar_consultas(
                [Consulta(frente, herramienta, dict(argumentos), resultado, True)]
            )
        return llamada

    def terminar(self, mensaje="listo"):
        return asyncio.run(self.coordinador().terminar(mensaje))

    def escalar(self):
        """Un resumen al oficial válido del #10 (R6): las afirmaciones de las consultas del caso."""
        entrada = resumen_del_caso(self.estado)
        return asyncio.run(self.coordinador().llamar(ESCALAR, entrada))

    def registrar(self, **consulta):
        """El subagente de registro consulta y el frente termina (lo que haría el `Delegador`)."""
        sesion = self.sesion(Frente.REGISTRO)
        llamada = asyncio.run(sesion.llamar(REGISTRO, consulta, en_proceso=False))
        self._guardar_consulta(Frente.REGISTRO, REGISTRO, consulta, llamada)
        self.estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
        self.estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)

    def listas(self, **consulta):
        llamada = asyncio.run(self.sesion(Frente.LISTAS).llamar(LISTAS, consulta))
        return self._guardar_consulta(Frente.LISTAS, LISTAS, consulta, llamada)

    def delegar_listas(self):
        sesion = self.sesion_del_coordinador()
        return asyncio.run(sesion.llamar(DELEGAR, {"frente": "listas"}, en_proceso=True))

    def riesgo(self, categoria):
        sesion = self.sesion(Frente.CATEGORIA)
        argumentos = {"categoria": categoria}
        llamada = asyncio.run(sesion.llamar(RIESGO, argumentos))
        return self._guardar_consulta(Frente.CATEGORIA, RIESGO, argumentos, llamada)

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
    assert caso.estado.libro.escalamientos == [
        Escalamiento(
            frozenset({"coincidencia_representante"}),
            ("CO-PL-0003", "Panadería Luna Nueva SAS", True),
        )
    ]

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
    assert caso.estado.libro.escalamientos == [
        Escalamiento(frozenset({"alto_riesgo"}), ("CO-TV-0001", "Tienda Verde SAS", True))
    ]
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
    assert caso.informe("decide_cumplimiento").ejecutada  # #9: después de escalar, el informe
    assert caso.terminar("ya escalé").termino is True
    assert caso.estado.cierre_sin_escalar is False
    tipos = [e.tipo for e in caso.eventos.eventos()]
    assert tipos.count(TIPO_CIERRE_IMPEDIDO) == 2 and TIPO_CIERRE_SIN_ESCALAR not in tipos
    assert TIPO_CIERRE_SIN_INFORME not in tipos


def test_un_caso_de_alto_riesgo_tampoco_termina_sin_escalar():
    caso = Caso(registro=[comercio_alto_riesgo()])
    caso.registrar(identificador="CO-TV-0001")
    caso.riesgo("suplementos dietarios")
    cierre = caso.terminar()
    assert cierre.termino is False and "categoría de alto riesgo" in cierre.motivo
    caso.escalar()
    assert caso.informe("decide_cumplimiento").ejecutada  # #9: después de escalar, el informe
    assert caso.terminar().termino is True
    assert TIPO_CIERRE_SIN_INFORME not in [e.tipo for e in caso.eventos.eventos()]


def test_un_caso_de_bajo_riesgo_sin_hallazgos_termina_sin_trabas():
    caso = Caso(registro=[comercio_bajo_riesgo()])
    caso.registrar(identificador="CO-TA-0002")
    caso.riesgo("talleres")
    # #9: el cierre exige el informe; sin listas consultadas, `habilitar` se rechazaría.
    assert caso.informe("no_habilitar").ejecutada
    assert caso.terminar().termino is True
    # Antes, `eventos == []`. Ahora la lista exacta de lo que emite registrar el informe, en orden;
    # `terminar()` no añade ninguno (T037).
    assert [e.tipo for e in caso.eventos.eventos()] == [
        TIPO_COBERTURA_SUSTITUIDA,
        TIPO_DATOS_SUSTITUIDOS,
        TIPO_INFORME_REGISTRADO,
    ]


def test_un_coordinador_que_insiste_en_terminar_sin_escalar_termina_marcado_y_no_completo():
    caso = _caso_c()
    devoluciones = [caso.terminar() for _ in range(MAX_CIERRES_IMPEDIDOS)]
    assert [d.termino for d in devoluciones] == [False] * MAX_CIERRES_IMPEDIDOS
    ultimo = caso.terminar()
    assert ultimo.termino is True  # se agotaron las oportunidades
    assert caso.estado.cierre_sin_escalar is True
    assert caso.estado.cierre_sin_informe is True  # #9: tampoco registró el informe (T037)
    assert caso.estado.libro.escalamientos == []  # y nunca se escaló
    assert caso.pasarela.escalamientos == []
    assert caso.pasarela.informes == []
    tipos = [e.tipo for e in caso.eventos.eventos()]
    assert tipos.count(TIPO_CIERRE_IMPEDIDO) == MAX_CIERRES_IMPEDIDOS
    assert tipos.count(TIPO_CIERRE_SIN_ESCALAR) == 1
    assert tipos.count(TIPO_CIERRE_SIN_INFORME) == 1
    assert tipos[-2:] == [TIPO_CIERRE_SIN_ESCALAR, TIPO_CIERRE_SIN_INFORME]
    assert caso.informe("habilitar").denegada  # el caso sigue sin poder habilitarse


def test_el_fin_de_turno_de_un_subagente_no_se_bloquea():
    caso = _caso_c()
    for frente in Frente:
        sesion = caso.sesion(frente)
        assert asyncio.run(sesion.terminar("listo")).termino is True


# ---------------------------------- US5: sesiones separadas, dos casos y estado de las herramientas


def _frentes_de(comercio, representante_en_listas=False, resumen="resumen del subagente"):
    from due_diligence.simulacion import (
        consulta,
        consulta_listas,
        respuesta_listas,
        respuesta_registro,
        resultado_frente,
    )

    id_comercio = comercio["identificador"]
    id_persona = comercio["representante_legal"]["identificador"]
    persona = consulta_listas("persona", identificador=id_persona)
    if representante_en_listas:
        persona = consulta(
            Frente.LISTAS,
            {"tipo": "persona", "identificador": id_persona},
            respuesta_listas(
                {"tipo": "persona", "nombre": "(ficticio)", "identificador": id_persona}
            ),
        )
    registro = consulta(
        Frente.REGISTRO, {"identificador": id_comercio}, respuesta_registro(comercio)
    )
    return {
        Frente.REGISTRO: resultado_frente(Frente.REGISTRO, [registro]),
        Frente.LISTAS: resultado_frente(
            Frente.LISTAS,
            [consulta_listas("comercio", identificador=id_comercio), persona],
            resumen=resumen,
        ),
    }


def _caso_real(comercio, **kwargs):
    guion = [
        ("delegar_paralelo", [{"frente": "registro", "identificador": comercio["identificador"]}]),
        ("delegar", {"frente": "listas"}),
        ("terminar",),
    ]
    coordinador = CoordinadorSimulado(guion)
    caso = CasoReal(
        ejecutor=EjecutorSimulado(resultados=_frentes_de(comercio, **kwargs)), consulta=coordinador
    )
    coordinador.caso = caso
    return caso


def test_el_hook_de_listas_ve_la_identificacion_que_escribio_el_del_registro_en_otra_sesion():
    caso = _caso_real(comercio_alto_riesgo())
    asyncio.run(caso.ejecutar("solicitud"))
    assert caso.estado.situacion(Frente.LISTAS) is Situacion.TERMINADO
    consultas = [c for c in caso.estado.consultas if c.frente is Frente.LISTAS]
    assert len(consultas) == 2 and all(c.valido and c.error is None for c in consultas)
    assert [c.tipo for c in caso.estado.libro.consultas_listas] == ["comercio", "persona"]


def test_el_hook_del_coordinador_ve_la_coincidencia_que_escribio_el_de_listas_en_otra_sesion():
    caso = _caso_real(comercio_con_representante_en_listas(), representante_en_listas=True)
    asyncio.run(caso.ejecutar("solicitud"))
    assert [c.causa for c in caso.estado.libro.coincidencias] == ["coincidencia_representante"]
    cierre = caso.hooks.coordinador()["Stop"][0].hooks[0]
    salida = asyncio.run(cierre({"stop_hook_active": False}, None, None))
    assert salida["decision"] == "block"  # el Stop del coordinador ve lo del subagente de listas


def test_dos_casos_a_la_vez_no_se_mezclan():
    uno = _caso_real(comercio_con_representante_en_listas(), representante_en_listas=True)
    otro = _caso_real(comercio_alto_riesgo())

    async def a_la_vez():
        await asyncio.gather(uno.ejecutar("solicitud uno"), otro.ejecutar("solicitud otro"))

    asyncio.run(a_la_vez())
    assert uno.estado.comercio["identificador"] == "CO-PL-0003"
    assert otro.estado.comercio["identificador"] == "CO-TV-0001"
    assert len(uno.estado.libro.coincidencias) == 1 and otro.estado.libro.coincidencias == []
    assert uno.estado.libro is not otro.estado.libro
    assert [e.regla for e in otro.eventos()] == [None] * len(otro.eventos())  # sin bloqueos ajenos


def test_el_estado_sale_de_la_respuesta_de_la_herramienta_y_no_del_resumen_del_modelo():
    # El resumen del subagente dice «sin coincidencias», pero la herramienta devolvió una.
    caso = _caso_real(
        comercio_con_representante_en_listas(),
        representante_en_listas=True,
        resumen="Sin coincidencias en listas restrictivas para el comercio ni su representante.",
    )
    asyncio.run(caso.ejecutar("solicitud"))
    assert len(caso.estado.libro.coincidencias) == 1
    assert "Sin coincidencias" in caso.estado.resultados[Frente.LISTAS].resumen


# ------------------------------------- #10: la consulta con el identificador identifica (T016)


def _registro_por_contexto(contexto):
    """El registro según la entrada: el nombre ambiguo da dos coincidencias; el id, una."""
    from due_diligence.simulacion import consulta, respuesta_registro, resultado_frente

    parecidos = comercios_parecidos()
    if "CO-AM-0005" in contexto:
        argumentos, comercios = {"identificador": "CO-AM-0005"}, [parecidos[1]]
    else:
        argumentos, comercios = {"nombre": "Almacén Mirador SAS"}, parecidos
    return resultado_frente(
        Frente.REGISTRO,
        [consulta(Frente.REGISTRO, argumentos, respuesta_registro(*comercios))],
    )


def test_tras_varias_coincidencias_la_consulta_con_el_identificador_identifica_al_comercio():
    from due_diligence.reglas import permite_delegar_listas

    caso = CasoReal(ejecutor=EjecutorSimulado(resultados={Frente.REGISTRO: _registro_por_contexto}))
    delegador = caso.delegador
    asyncio.run(delegador.delegar({"frente": "registro", "nombre": "Almacén Mirador SAS"}))
    assert caso.estado.comercio is None and caso.estado.clase_identificacion == "varias"
    assert permite_delegar_listas(caso.estado)[0] is False
    asyncio.run(delegador.delegar({"frente": "registro", "identificador": "CO-AM-0005"}))
    assert caso.estado.comercio["identificador"] == "CO-AM-0005"
    assert caso.estado.clase_identificacion == "unica"
    # La identificación ambigua anterior no queda: `_ejecutar` del registro la reinicia (#7).
    assert [i.clase for i in caso.estado.identificaciones] == ["unica"]
    assert permite_delegar_listas(caso.estado) == (True, "")


def test_tras_identificar_listas_se_delega_y_consulta_al_comercio_y_al_representante():
    from due_diligence.simulacion import consulta_listas, resultado_frente

    listas = resultado_frente(
        Frente.LISTAS,
        [
            consulta_listas("comercio", identificador="CO-AM-0005"),
            consulta_listas("persona", identificador="PE-0005"),
        ],
    )
    caso = CasoReal(
        ejecutor=EjecutorSimulado(
            resultados={Frente.REGISTRO: _registro_por_contexto, Frente.LISTAS: listas}
        )
    )
    delegador = caso.delegador
    asyncio.run(delegador.delegar({"frente": "registro", "nombre": "Almacén Mirador SAS"}))
    rechazo = asyncio.run(delegador.delegar({"frente": "listas"}))
    assert rechazo["error"] is True and rechazo["reintentable"] is False
    asyncio.run(delegador.delegar({"frente": "registro", "identificador": "CO-AM-0005"}))
    respuesta = asyncio.run(delegador.delegar({"frente": "listas"}))
    assert respuesta["situacion"] == "terminado"
    assert caso.estado.situacion(Frente.LISTAS) is Situacion.TERMINADO
