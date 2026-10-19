"""Casos del #9 de extremo a extremo: informe vigente, conflictos y registro obligatorio (FR-019).

Un `Caso` real con subagentes en sesiones simuladas y un `CoordinadorSimulado` cuyo guion pasa por
los hooks del coordinador y por la `PasarelaSimulada`, que valida el informe como la real. No se
llama al modelo. Datos ficticios del #5.
"""

import asyncio

import pytest

from due_diligence.coordinador import Caso
from due_diligence.estado import Situacion
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_CIERRE_IMPEDIDO,
    TIPO_INFORME_REGISTRADO,
)
from due_diligence.frentes import Frente
from due_diligence.hooks import ACCION_DELEGAR_LISTAS, HooksDelCaso
from due_diligence.reglas import (
    MOTIVO_REGISTRO_REINTENTABLE,
    MOTIVO_SIN_COMERCIO,
    MOTIVO_SIN_INFORME,
)
from due_diligence.simulacion import (
    FUENTE_NOTICIAS,
    CoordinadorSimulado,
    EjecutorSimulado,
    comercio_alto_riesgo,
    comercio_bajo_riesgo,
    consulta,
    consulta_listas,
    en_secuencia,
    error_estructurado,
    respuesta_registro,
    resultado_frente,
)
from due_diligence.test_casos_reglas import _delegaciones, _resultados

NOTICIAS = {"frente": "noticias", "identificador": "CO-TA-0002"}
SOLICITUD = "Due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, talleres."
# Desde el #10 (FR-020) la categoría delegada tiene que aparecer en un mensaje del analista.
SOLICITUD_G = (
    "Due diligence de Ferretería Río Fino SAS, identificador ficticio CO-RF-0006, comercio de "
    "calzado."
)
SOLICITUD_A = (
    "Due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001, suplementos dietarios."
)
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


@pytest.fixture(autouse=True)
def _sin_caida_del_registro(monkeypatch):
    """Los tests que consultan el registro real no dependen de la caída simulada de la sesión."""
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)


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


def test_un_reintento_que_termina_entre_el_pre_y_el_post_del_informe_lo_deja_sin_vigencia(
    monkeypatch,
):
    # T013 y T029: se anota, en cada Pre y Post del informe, la situación de noticias.
    orden = []
    previo, posterior = HooksDelCaso._informe_previo, HooksDelCaso._informe_posterior

    async def previo_anotado(self, entrada, tool_use_id, contexto):
        orden.append(("pre", self.estado.situacion(Frente.NOTICIAS)))
        return await previo(self, entrada, tool_use_id, contexto)

    async def posterior_anotado(self, entrada, tool_use_id, contexto):
        orden.append(("post", self.estado.situacion(Frente.NOTICIAS)))
        return await posterior(self, entrada, tool_use_id, contexto)

    monkeypatch.setattr(HooksDelCaso, "_informe_previo", previo_anotado)
    monkeypatch.setattr(HooksDelCaso, "_informe_posterior", posterior_anotado)
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
    # Situación de noticias justo antes de que responda la pasarela (y corra el Post) del informe
    # del mismo mensaje: prueba que el reintento terminó entre el Pre y el Post (T029).
    antes_del_post = []

    async def registrar_tras_el_reintento(entrada):
        # El `PreToolUse` del informe ya calculó su huella con noticias en curso. Se suelta el
        # reintento y se espera a que termine antes de que la pasarela responda y corra el Post.
        if caso.estado.situacion(Frente.NOTICIAS) is Situacion.EN_CURSO:
            ejecutor.soltar.set()
            for _ in range(10_000):
                if caso.estado.situacion(Frente.NOTICIAS) is Situacion.TERMINADO:
                    break
                await asyncio.sleep(0)
            antes_del_post.append(caso.estado.situacion(Frente.NOTICIAS))
        return registrar(entrada)

    coordinador.pasarela.herramientas["mcp__pasarela__registrar_informe"] = (
        registrar_tras_el_reintento
    )
    asyncio.run(caso.ejecutar(SOLICITUD))

    # El informe del mismo mensaje se registró con noticias sin cubrir, y su huella es la del Pre.
    assert antes_del_post == [Situacion.TERMINADO]
    # Tres informes: el de `_inicio`, el del mismo mensaje (Pre con noticias en curso y Post ya
    # terminado) y el nuevo que exige el cierre.
    assert orden == [
        ("pre", Situacion.NO_TERMINADO),
        ("post", Situacion.NO_TERMINADO),
        ("pre", Situacion.EN_CURSO),
        ("post", Situacion.TERMINADO),
        ("pre", Situacion.TERMINADO),
        ("post", Situacion.TERMINADO),
    ]
    _, del_mismo_mensaje, _ = caso.estado.informes
    assert dict(del_mismo_mensaje.huella.cobertura)["noticias"] is False
    assert caso.estado.situacion(Frente.NOTICIAS) is Situacion.TERMINADO
    # Ese informe no quedó vigente: el motivo exacto del primer cierre es el del cambio de
    # cobertura (equivale a `informe_vigente(...) is False` tras su Post).
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


# ------------------------------------------------------------- T038: casos de extremo a extremo


SUR = "Registro Mercantil Ficticio del Sur"
RUFE = "Registro Único Ficticio de Empresas"
LISTA = "Lista Restrictiva Ficticia"  # la de `consulta_listas`
CATALOGO = "Catálogo Ficticio de Categorías"  # la de `respuesta_riesgo`
CONFLICTO_G = {
    "resumen": "1 conflicto entre las fuentes registrales.",
    "lista": [
        {
            "dato": "fecha_constitucion",
            "valores": [
                {"valor": "2016-03-14", "fuente": SUR, "fecha": "2026-09-30"},
                {"valor": "2017-09-02", "fuente": RUFE, "fecha": "2026-09-28"},
            ],
        }
    ],
}


def _caso_con(guion, resultados, solicitud=SOLICITUD):
    caso, coordinador = _ejecutar(guion, EjecutorSimulado(resultados=resultados))
    asyncio.run(caso.ejecutar(solicitud))
    return caso, coordinador


def _resultados_g():
    """`CO-RF-0006` con la respuesta real de la pasarela: dos fuentes con fechas distintas."""
    from servidor_mcp import datos
    from servidor_mcp.registro import consultar_registro_mercantil

    datos.limpiar_cache()
    respuesta = consultar_registro_mercantil(identificador="CO-RF-0006").structured_content
    resultados = _resultados(
        [],
        "comercio de calzado",
        "medio",
        [
            consulta_listas("comercio", identificador="CO-RF-0006"),
            consulta_listas("persona", identificador="PE-0006"),
        ],
    )
    resultados[Frente.REGISTRO] = resultado_frente(
        Frente.REGISTRO,
        [consulta(Frente.REGISTRO, {"identificador": "CO-RF-0006"}, respuesta)],
    )
    return resultados


def test_caso_g_el_informe_muestra_las_dos_fechas_sin_que_el_coordinador_las_declare():
    guion = [
        _delegaciones("CO-RF-0006", "comercio de calzado"),
        ("delegar", {"frente": "listas"}),
        ("informe", "no_habilitar"),  # el coordinador simulado declara «sin conflictos»
        ("terminar",),
    ]
    caso, coordinador = _caso_con(guion, _resultados_g(), SOLICITUD_G)
    (informe,) = coordinador.pasarela.informes
    assert informe["conflictos"] == CONFLICTO_G
    assert informe["comercio"] == {
        "identificador": "CO-RF-0006",
        "nombre": "Ferretería Río Fino SAS",
        "verificado": True,
    }
    assert coordinador.resultados_de("terminar")[0].termino is True
    assert caso.conflictos.como_entrada() == CONFLICTO_G


def test_caso_g_un_conflicto_inventado_por_el_coordinador_no_queda():
    inventado = {
        "comercio": {"identificador": "CO-RF-0006", "nombre": "x", "verificado": True},
        "recomendacion": "no_habilitar",
        # Los cuatro frentes quedan cubiertos: cada uno se cita (US1-6).
        "hallazgos": {
            "registro": [{"texto": "Figura activo.", "fuente": SUR, "fecha": "2026-09-30"}],
            "listas": [{"texto": "Sin coincidencias.", "fuente": LISTA, "fecha": "2026-09-30"}],
            # #12 (T022, R10): la fuente del diario; con la del registro solo pasaba porque las
            # noticias simuladas llevaban, por error, la fuente del registro mercantil.
            "noticias": [
                {"texto": "Sin menciones.", "fuente": FUENTE_NOTICIAS, "fecha": "2026-09-30"}
            ],
            "categoria": [{"texto": "Riesgo medio.", "fuente": CATALOGO, "fecha": "2026-09-30"}],
        },
        "conflictos": {
            "resumen": "1 conflicto.",
            "lista": [
                {
                    "dato": "estado",
                    "valores": [
                        {"valor": "activo", "fuente": SUR, "fecha": "2026-09-30"},
                        {"valor": "inactivo", "fuente": RUFE, "fecha": "2026-09-28"},
                    ],
                }
            ],
        },
        "cobertura": "completa",
    }
    guion = [
        _delegaciones("CO-RF-0006", "comercio de calzado"),
        ("delegar", {"frente": "listas"}),
        ("informe_con", inventado),
        ("terminar",),
    ]
    _, coordinador = _caso_con(guion, _resultados_g(), SOLICITUD_G)
    (informe,) = coordinador.pasarela.informes
    assert informe["conflictos"] == CONFLICTO_G


def _resultados_alto_riesgo():
    return _resultados(
        [comercio_alto_riesgo()],
        "suplementos dietarios",
        "alto",
        [
            consulta_listas("comercio", identificador="CO-TV-0001"),
            consulta_listas("persona", identificador="PE-0001"),
        ],
        identificador="CO-TV-0001",
    )


def test_caso_escalado_el_informe_se_rechaza_hasta_escalar_y_despues_se_registra():
    guion = [
        _delegaciones("CO-TV-0001", "suplementos dietarios"),
        ("delegar", {"frente": "listas"}),
        ("informe", "decide_cumplimiento"),  # antes de escalar: rechazado (FR-012)
        ("escalar",),
        ("informe", "decide_cumplimiento"),
        ("terminar",),
    ]
    caso, coordinador = _caso_con(guion, _resultados_alto_riesgo(), SOLICITUD_A)
    antes, despues = coordinador.resultados_de("informe")
    assert antes.denegada and "aún no se ha escalado" in antes.motivo
    assert despues.ejecutada and not despues.denegada
    assert [i["recomendacion"] for i in coordinador.pasarela.informes] == ["decide_cumplimiento"]
    assert coordinador.resultados_de("terminar")[0].termino is True
    tipos = [e.tipo for e in caso.eventos()]
    assert tipos.index("escalamiento_registrado") < tipos.index(TIPO_INFORME_REGISTRADO)


def _resultados_bajo_riesgo():
    return _resultados(
        [comercio_bajo_riesgo()],
        "talleres",
        "bajo",
        [
            consulta_listas("comercio", identificador="CO-TA-0002"),
            consulta_listas("persona", identificador="PE-0002"),
        ],
        identificador="CO-TA-0002",
    )


@pytest.mark.parametrize("escalar", [False, True])
@pytest.mark.parametrize("informe", ["ninguno", "vigente", "anterior_a_un_cambio"])
def test_sc003_el_cierre_solo_se_permite_con_todo(escalar, informe):
    # SC-003: escalamiento requerido (sí o no) × informe (ninguno, vigente o anterior a un cambio).
    if escalar:
        resultados, identificador, categoria = (
            _resultados_alto_riesgo(),
            "CO-TV-0001",
            "suplementos dietarios",
        )
    else:
        resultados, identificador, categoria = _resultados_bajo_riesgo(), "CO-TA-0002", "talleres"
    guion = [
        ("delegar", {"frente": "registro", "identificador": identificador}),
        ("delegar", {"frente": "categoria", "categoria": categoria}),
        ("delegar", {"frente": "listas"}),
    ]
    if escalar:
        guion.append(("escalar",))
    if informe != "ninguno":
        guion.append(("informe", "decide_cumplimiento" if escalar else "no_habilitar"))
    if informe == "anterior_a_un_cambio":
        guion.append(("delegar", {"frente": "noticias", "identificador": identificador}))
    guion.append(("terminar",))
    _, coordinador = _caso_con(guion, resultados, SOLICITUD_A if escalar else SOLICITUD)
    (cierre,) = coordinador.resultados_de("terminar")
    assert cierre.termino is (informe == "vigente")
    if informe == "ninguno":
        assert cierre.motivo == MOTIVO_SIN_INFORME
    if informe == "anterior_a_un_cambio":
        assert cierre.motivo == COBERTURA_CAMBIO


def _registro_caido(tipo="servicio_no_disponible", reintentable=True):
    """La respuesta de la pasarela con `PASARELA_FALLA_REGISTRO=1`, en cada ejecución."""
    error = error_estructurado(tipo, reintentable)
    return resultado_frente(
        Frente.REGISTRO,
        [consulta(Frente.REGISTRO, {"identificador": "CO-TA-0002"}, error=error)],
    )


def test_registro_caido_el_cierre_exige_reintentar_o_registrar_el_informe_sin_verificar():
    resultados = _resultados_bajo_riesgo()
    resultados[Frente.REGISTRO] = _registro_caido()
    guion = [
        _delegaciones("CO-TA-0002", "talleres"),
        ("terminar",),  # queda un reintento: el motivo ofrece las dos salidas
        ("delegar", {"frente": "registro", "identificador": "CO-TA-0002"}),  # vuelve a fallar
        ("terminar",),  # sin reintentos: falta el informe
        ("delegar", {"frente": "listas"}),  # sin comercio: I.1 lo rechaza
        ("informe", "habilitar"),  # sin listas: rechazado
        ("informe", "no_habilitar"),
        ("terminar",),
    ]
    caso, coordinador = _caso_con(guion, resultados)
    primero, segundo, tercero = coordinador.resultados_de("terminar")
    assert (primero.termino, primero.motivo) == (False, MOTIVO_REGISTRO_REINTENTABLE)
    assert (segundo.termino, segundo.motivo) == (False, MOTIVO_SIN_INFORME)
    assert tercero.termino is True
    # I.1: con el registro caído no hay comercio identificado y listas no se delega.
    _, listas = coordinador.resultados_de("delegar")
    assert listas.denegada and not listas.ejecutada
    assert listas.motivo == MOTIVO_SIN_COMERCIO
    (bloqueo,) = [e for e in caso.eventos() if e.tipo == TIPO_BLOQUEO_REGLA and e.regla == "I.1"]
    assert bloqueo.accion == ACCION_DELEGAR_LISTAS
    assert caso.estado.situacion(Frente.LISTAS) is Situacion.SIN_INICIAR
    habilitar, no_habilitar = coordinador.resultados_de("informe")
    assert habilitar.denegada and not no_habilitar.denegada
    (informe,) = coordinador.pasarela.informes
    assert informe["comercio"] == {
        "identificador": "CO-TA-0002",
        "nombre": None,
        "verificado": False,
    }
    assert informe["conflictos"] == {
        "resumen": "No se pudieron comparar las fuentes registrales: el registro no respondió.",
        "lista": [],
    }
    assert (
        "registro: no cubierto; error de la fuente (servicio_no_disponible); 2 intentos."
        in (informe["cobertura"])
    )
    assert any(linea.startswith("listas: no cubierto") for linea in informe["cobertura"])
    assert caso.completo is False


@pytest.mark.parametrize(
    "registro",
    [
        resultado_frente(
            Frente.REGISTRO,
            [consulta(Frente.REGISTRO, {"identificador": "CO-ZZ-9999"}, respuesta_registro())],
        ),
        _registro_caido("entrada_invalida", False),
    ],
    ids=["sin_coincidencias", "entrada_invalida"],
)
def test_sin_comercio_ni_registro_caido_no_se_exige_informe(registro):
    # Decisión (a) y caso límite de la entrada inválida: se pide revisar el nombre, sin informe.
    resultados = _resultados_bajo_riesgo()
    resultados[Frente.REGISTRO] = registro
    guion = [("delegar", {"frente": "registro", "identificador": "CO-TA-0002"}), ("terminar",)]
    caso, coordinador = _caso_con(guion, resultados)
    assert coordinador.resultados_de("terminar")[0].termino is True
    assert coordinador.pasarela.informes == []
    assert TIPO_CIERRE_IMPEDIDO not in [e.tipo for e in caso.eventos()]


def test_un_reintento_que_vuelve_a_fallar_no_invalida_el_informe():
    resultados = _resultados_bajo_riesgo()
    caida = resultado_frente(
        Frente.NOTICIAS,
        [consulta(Frente.NOTICIAS, {"identificador": "CO-TA-0002"}, error=error_estructurado())],
    )
    resultados[Frente.NOTICIAS] = caida  # falla siempre
    guion = [*_inicio(), ("delegar", NOTICIAS), ("terminar",)]
    caso, coordinador = _caso_con(guion, resultados)
    assert caso.estado.errores[Frente.NOTICIAS]["intento"] == 2
    (cierre,) = coordinador.resultados_de("terminar")
    assert cierre.termino is True


def test_un_reintento_que_sale_bien_invalida_el_informe_anterior():
    # T038: contraste del anterior, en mensajes separados. El informe de `_inicio` es vigente con
    # noticias sin cubrir; el reintento se recupera y el cierre exige uno nuevo.
    ejecutor = EjecutorSimulado(resultados=_resultados_con_noticias_que_se_recuperan())
    guion = [
        *_inicio(),
        ("delegar", NOTICIAS),
        ("terminar",),
        ("informe", "no_habilitar"),
        ("terminar",),
    ]
    caso, coordinador = _ejecutar(guion, ejecutor)
    asyncio.run(caso.ejecutar(SOLICITUD))
    primer_cierre, segundo_cierre = coordinador.resultados_de("terminar")
    assert primer_cierre.termino is False and primer_cierre.motivo == COBERTURA_CAMBIO
    assert segundo_cierre.termino is True
    anterior, ultimo = caso.estado.informes
    assert dict(anterior.huella.cobertura)["noticias"] is False
    assert dict(ultimo.huella.cobertura)["noticias"] is True


def test_sello_escalar_informe_minimo_cierre_permitido_y_caso_no_completo(monkeypatch):
    # FR-014 y R9 de extremo a extremo (sugerencia de la analista en la parada B): un caso de bajo
    # riesgo, sin otras causas, queda sellado porque falla el `PostToolUse` del primer informe.
    from due_diligence import hooks as modulo_hooks
    from due_diligence.conflictos import no_calculados
    from due_diligence.hooks import COBERTURA_NO_CALCULADA
    from due_diligence.libro import CAUSA_FALLO_DE_HOOK
    from due_diligence.reglas import MOTIVO_SOLO_OFICIAL, SUFIJO_LUEGO_INFORME, motivo_de_escalar

    original = modulo_hooks._identificador_del_informe
    llamadas = []

    def falla_la_primera_vez(resultado):
        llamadas.append(resultado)
        if len(llamadas) == 1:
            raise RuntimeError("fallo simulado del PostToolUse del informe")
        return original(resultado)

    monkeypatch.setattr(modulo_hooks, "_identificador_del_informe", falla_la_primera_vez)
    guion = [
        _delegaciones("CO-TA-0002", "talleres"),
        ("delegar", {"frente": "listas"}),
        ("informe", "no_habilitar"),  # la pasarela lo guarda, pero su PostToolUse falla: sello
        ("terminar",),  # sellado: primero escalar, luego el informe
        ("informe", "decide_cumplimiento"),  # antes de escalar: rechazado (FR-012)
        ("escalar",),
        ("informe", "no_habilitar"),  # tras el sello solo decide el oficial
        ("informe", "decide_cumplimiento"),  # el informe mínimo
        ("terminar",),
    ]
    caso, coordinador = _caso_con(guion, _resultados_bajo_riesgo())

    assert caso.estado.libro.fallo_de_hook is not None
    primero, segundo = coordinador.resultados_de("terminar")
    assert (primero.termino, primero.motivo) == (
        False,
        motivo_de_escalar([CAUSA_FALLO_DE_HOOK]) + SUFIJO_LUEGO_INFORME,
    )
    assert segundo.termino is True

    _, antes_de_escalar, otra_recomendacion, minimo = coordinador.resultados_de("informe")
    assert antes_de_escalar.denegada and "aún no se ha escalado" in antes_de_escalar.motivo
    assert otra_recomendacion.denegada and MOTIVO_SOLO_OFICIAL in otra_recomendacion.motivo
    assert minimo.ejecutada and not minimo.denegada

    guardado = coordinador.pasarela.informes[-1]
    assert guardado["recomendacion"] == "decide_cumplimiento"
    assert guardado["cobertura"] == [COBERTURA_NO_CALCULADA]
    assert guardado["conflictos"] == no_calculados().como_entrada()
    assert [(i.recomendacion, i.minimo) for i in caso.estado.informes] == [
        ("decide_cumplimiento", True)
    ]
    assert CAUSA_FALLO_DE_HOOK in caso.estado.informes[0].huella.causas

    tipos = [e.tipo for e in caso.eventos()]
    assert tipos.index("escalamiento_registrado") < tipos.index(TIPO_INFORME_REGISTRADO)
    (registrado,) = [e for e in caso.eventos() if e.tipo == TIPO_INFORME_REGISTRADO]
    assert registrado.detalle.endswith(" Informe mínimo tras un fallo de hook.")
    assert caso.completo is False
