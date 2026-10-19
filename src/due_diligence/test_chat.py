"""Tests de la aplicación de chat con `AppTest` (#11, R13, contrato `interfaz-chat.md`).

Cada test inyecta `session_state["dependencias"]` antes de `run()`: un `cargar_entorno` que no
hace nada (ningún test carga el archivo de entorno), un entorno con una clave ficticia y una
fábrica de casos con el `CoordinadorSimulado`. No se llama al modelo.

El envío de un mensaje con solo espacios se prueba aquí porque llega así al script: el frontend
de Streamlit 1.66 lo envía (medido en T033, R6). La entrada deshabilitada **durante** un turno no
se puede ver con `AppTest`, que solo muestra el estado final (T033, C1): se comprueba a mano en Q4.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from due_diligence import configuracion, presentacion
from due_diligence.test_presentacion import (
    GUION_A,
    SOLICITUD_A,
    SOLICITUD_D,
    construir,
    guion_y_resultados_f,
    guiones_d,
    resultados_a,
    resultados_d,
)

APP = str(Path(__file__).with_name("chat.py"))
CLAVE = {configuracion.VARIABLE_CLAVE: "clave-ficticia-de-prueba"}


@dataclass
class Fabrica:
    """Crea un `Caso` simulado por cada caso nuevo de la aplicación y los guarda en orden."""

    guiones: list[list[tuple[Any, ...]]]
    resultados: Any  # función sin argumentos: unos resultados nuevos para cada caso
    num_turns: list[int] | None = None
    casos: list[Any] = field(default_factory=list)
    interrupciones: tuple[type[BaseException], ...] = ()

    def __call__(self, observador):
        caso = construir(
            self.guiones, self.resultados(), self.num_turns, observador, self.interrupciones
        )
        self.casos.append(caso)
        return caso


@dataclass(frozen=True)
class Dependencias:
    """Las mismas que lee `chat.py` (por nombre de atributo)."""

    crear_caso: Any
    entorno: dict[str, str]
    cargar_entorno: Any = lambda: None


@pytest.fixture(autouse=True)
def _sin_caidas(monkeypatch):
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)
    monkeypatch.delenv("PASARELA_FALLA_NOTICIAS", raising=False)


def _app(fabrica, entorno=None):
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["dependencias"] = Dependencias(fabrica, CLAVE if entorno is None else entorno)
    return at.run()


def _enviar(at, texto):
    return at.chat_input[0].set_value(texto).run()


def _textos(mensaje):
    """Los textos de los elementos de un mensaje del chat, en el orden en que se dibujan."""
    return [v for v in (getattr(c, "value", None) for c in mensaje.children.values()) if v]


def _turnos(at):
    """(usuario, asistente) de cada turno del historial."""
    mensajes = list(at.chat_message)
    return list(zip(mensajes[0::2], mensajes[1::2], strict=True))


def _contiene(textos, fragmento):
    return [i for i, t in enumerate(textos) if fragmento in str(t)]


def fabrica_a():
    return Fabrica([GUION_A], resultados_a)


def fabrica_d():
    return Fabrica(guiones_d(), resultados_d, num_turns=[3, 4])


# --------------------------------------------------------------------------- conversación


def test_el_caso_d_se_conversa_en_dos_turnos_del_mismo_caso():
    fabrica = fabrica_d()
    at = _enviar(_app(fabrica), SOLICITUD_D)
    ((usuario, asistente),) = _turnos(at)
    assert usuario.name == "user" and asistente.name == "assistant"
    assert _textos(usuario) == [SOLICITUD_D]
    textos = _textos(asistente)
    assert not _contiene(textos, "Delegación al subagente de listas restrictivas")
    assert _contiene(textos, "Bloqueado por la regla I.1")
    assert _contiene(textos, "Esperando al analista")
    assert _contiene(textos, "Turnos del coordinador en este turno: 3 de 30")

    at = _enviar(at, "CO-AM-0004")
    (_, primero), (usuario_2, segundo) = _turnos(at)
    assert _textos(usuario_2) == ["CO-AM-0004"]
    textos = _textos(segundo)
    assert _contiene(textos, "Delegación al subagente de listas restrictivas")
    assert _contiene(textos, "Informe registrado")
    assert _contiene(textos, "Turnos del coordinador en este turno: 4 de 30")
    assert len(fabrica.casos) == 1  # el segundo mensaje continuó el mismo caso
    assert fabrica.casos[0].estado.mensajes == [SOLICITUD_D, "CO-AM-0004"]


def test_el_caso_a_muestra_cada_indicador_de_la_traza_en_orden():
    fabrica = fabrica_a()
    at = _enviar(_app(fabrica), SOLICITUD_A)
    ((_, asistente),) = _turnos(at)
    textos = _textos(asistente)
    (caso,) = fabrica.casos
    esperados = presentacion.resumen_del_turno(caso, 1, SOLICITUD_A).indicadores
    assert len(esperados) >= 6  # cuatro delegaciones, el escalamiento y el informe (SC-002)
    posiciones = [_contiene(textos, i.titulo) for i in esperados]
    assert all(posiciones), "falta algún indicador"
    primeras = [p[0] for p in posiciones]
    assert primeras == sorted(primeras)  # en el orden de la traza
    escalado = _contiene(textos, "Caso escalado a cumplimiento")[0]
    assert escalado < _contiene(textos, "Informe registrado")[0]


def test_en_el_caso_f_la_cobertura_va_antes_que_la_respuesta():
    guion, resultados, solicitud = guion_y_resultados_f()
    fabrica = Fabrica([guion], lambda: resultados)
    at = _enviar(_app(fabrica), solicitud)
    ((_, asistente),) = _turnos(at)
    textos = _textos(asistente)
    (noticias,) = _contiene(textos, "noticias: no cubierto")
    assert "el servicio no está disponible" in textos[noticias]
    (respuesta,) = _contiene(textos, fabrica.casos[0].respuesta)
    assert noticias < respuesta  # SC-003
    assert _contiene(textos, "Incompleto")
    assert not _contiene(textos, "Completo.")


def test_tras_un_caso_completo_el_siguiente_mensaje_inicia_uno_nuevo_y_lo_dice():
    fabrica = fabrica_a()
    at = _enviar(_app(fabrica), SOLICITUD_A)
    assert fabrica.casos[0].completo
    at = _enviar(at, SOLICITUD_A)
    assert len(fabrica.casos) == 2
    ((_, asistente),) = _turnos(at)  # el historial es el del caso nuevo
    assert _textos(asistente)[0] == presentacion.AVISO_CASO_NUEVO


def test_caso_nuevo_vacia_la_conversacion():
    fabrica = fabrica_d()
    at = _enviar(_app(fabrica), SOLICITUD_D)
    assert _turnos(at)
    at = at.button[0].click().run()
    assert at.button[0].label == "Caso nuevo"
    assert _turnos(at) == []
    at = _enviar(at, SOLICITUD_D)
    assert len(fabrica.casos) == 2  # el mensaje siguiente inicia otro caso


@pytest.mark.parametrize("texto", ["   ", "\t"])
def test_un_mensaje_con_solo_espacios_y_la_espera_abierta_avisa_sin_continuar(texto):
    fabrica = fabrica_d()
    at = _enviar(_app(fabrica), SOLICITUD_D)
    (caso,) = fabrica.casos
    aviso = presentacion.aviso_espera(caso.espera)
    at = _enviar(at, texto)
    assert aviso in [i.value for i in at.info]
    assert caso.estado.mensajes == [SOLICITUD_D]  # no se llamó a `continuar`
    assert len(_turnos(at)) == 1


def test_un_turno_que_falla_se_explica_sin_traza():
    error = RuntimeError("detalle interno del SDK")
    fabrica = Fabrica([[("lanzar", error)]], dict)
    at = _enviar(_app(fabrica), SOLICITUD_A)
    ((_, asistente),) = _turnos(at)
    textos = _textos(asistente)
    assert _contiene(textos, presentacion.mensaje_fallo_turno(error))
    assert not _contiene(textos, "detalle interno") and not _contiene(textos, "Traceback")
    assert _contiene(textos, "Incompleto")


# --------------------------------------------------------------------- credencial y modos


@pytest.mark.parametrize(
    ("entorno", "esperado"),
    [
        ({}, configuracion.MENSAJE_SIN_CLAVE),
        (
            {**CLAVE, "ANTHROPIC_AUTH_TOKEN": "otra-ficticia"},
            configuracion.MENSAJE_OTRA_CREDENCIAL.format(variable="ANTHROPIC_AUTH_TOKEN"),
        ),
    ],
)
def test_sin_credencial_valida_la_aplicacion_se_detiene_sin_crear_casos(entorno, esperado):
    fabrica = fabrica_a()
    at = _app(fabrica, entorno)
    assert [e.value for e in at.error] == [esperado]
    assert len(at.chat_input) == 0
    assert fabrica.casos == []  # SC-004: ni casos ni llamadas al modelo
    assert "clave-ficticia-de-prueba" not in esperado and "otra-ficticia" not in esperado


def test_la_franja_muestra_los_modos_activos():
    entorno = {**CLAVE, "PASARELA_FALLA_NOTICIAS": "1", "PASARELA_MODO_DEMO_HOOKS": "1"}
    at = _app(fabrica_a(), entorno)
    avisos = [w.value for w in at.warning]
    assert avisos == presentacion.modos_activos(entorno)
    assert len(avisos) == 2


def test_sin_modos_no_hay_franja():
    assert [w.value for w in _app(fabrica_a()).warning] == []


# ------------------------------------------- revisión de la parada B (mutaciones J4 y J8)


def test_un_caso_incompleto_nunca_se_pinta_como_completo_y_uno_completo_si():
    # J4, I.5: tampoco en color. El caso (f) va en `st.warning` y sin ningún `st.success`.
    guion, resultados, solicitud = guion_y_resultados_f()
    at = _enviar(_app(Fabrica([guion], lambda: resultados)), solicitud)
    assert [s.value for s in at.success] == []
    (estado,) = [w.value for w in at.warning if "Estado del caso" in w.value]
    assert "Incompleto" in estado

    fabrica = fabrica_a()
    at = _enviar(_app(fabrica), SOLICITUD_A)
    assert fabrica.casos[0].completo
    assert [s.value for s in at.success] == ["**Estado del caso**: Completo."]
    assert not [w.value for w in at.warning if "Estado del caso" in w.value]


def test_sin_sesion_que_continuar_la_conversacion_lo_explica_sin_traza():
    # J8: el turno anterior no dejó `session_id`; `continuar` lanza `CasoSinSesion`.
    fabrica = fabrica_d()
    at = _enviar(_app(fabrica), SOLICITUD_D)
    (caso,) = fabrica.casos
    caso.session_id = None
    at = _enviar(at, "CO-AM-0004")
    (_, primero), (_, segundo) = _turnos(at)
    textos = _textos(segundo)
    assert _contiene(textos, presentacion.MENSAJE_SIN_SESION)
    assert not _contiene(textos, "Traceback") and not _contiene(textos, "CasoSinSesion")
    assert caso.estado.mensajes == [SOLICITUD_D]  # no llegó a empezar el turno
    assert len(fabrica.casos) == 1


def test_un_caso_nuevo_no_dibuja_el_historial_anterior_y_avisa_desde_el_principio():
    # Validación manual: el aviso llegaba al final y, mientras corría el turno, se veía el
    # historial del caso anterior. La fábrica falla al crear el segundo caso: `AppTest` muestra lo
    # que se dibujó hasta ese punto, es decir, lo que se ve durante el turno.
    class FallaAlSegundo(Fabrica):
        def __call__(self, observador):
            if self.casos:
                raise RuntimeError("se detiene aquí para ver la página durante el turno")
            return super().__call__(observador)

    fabrica = FallaAlSegundo([GUION_A], resultados_a)
    at = _enviar(_app(fabrica), SOLICITUD_A)
    assert fabrica.casos[0].completo
    at = _enviar(at, "Otro comercio, por favor.")
    assert at.exception  # la parada provocada
    ((usuario, asistente),) = _turnos(at)  # ningún turno del caso anterior
    assert _textos(usuario) == ["Otro comercio, por favor."]
    assert _textos(asistente)[0] == presentacion.AVISO_CASO_NUEVO


# ------------------------------------- #12: la interrupción de Streamlit (T016, R9, opción A)


def test_las_excepciones_de_control_de_streamlit_heredan_de_baseexception():
    # Fija la ruta y la jerarquía en las que se apoya R9: si Streamlit las cambia, este test falla.
    from streamlit.runtime.scriptrunner_utils.exceptions import (
        RerunException,
        ScriptControlException,
        StopException,
    )

    assert issubclass(StopException, ScriptControlException)
    assert issubclass(RerunException, ScriptControlException)
    assert issubclass(ScriptControlException, BaseException)
    assert not issubclass(ScriptControlException, Exception)


def test_el_chat_declara_la_interrupcion_de_streamlit_al_crear_el_caso():
    from streamlit.runtime.scriptrunner_utils.exceptions import ScriptControlException

    from due_diligence import chat

    caso = chat._caso_real(None)
    assert caso._eventos.interrupciones == (ScriptControlException,)


def _fabrica_interrumpida():
    from streamlit.runtime.scriptrunner_utils.exceptions import (
        ScriptControlException,
        StopException,
    )

    # El primer caso se corta con «Stop»; el segundo es el del caso (a), que termina.
    guiones = iter([[[("lanzar", StopException())]], [GUION_A]])
    fabrica = Fabrica([], resultados_a, interrupciones=(ScriptControlException,))
    original = fabrica.__call__

    def crear(observador):
        fabrica.guiones = next(guiones)
        return original(observador)

    return fabrica, crear


def test_un_turno_interrumpido_queda_en_el_historial_sin_pendiente():
    fabrica, crear = _fabrica_interrumpida()
    at = _enviar(_app(crear), SOLICITUD_A)
    assert not at.exception
    assert "pendiente" not in at.session_state
    (historial,) = at.session_state["historial"]
    assert historial.respuesta == presentacion.MENSAJE_TURNO_INTERRUMPIDO
    (caso,) = fabrica.casos
    assert caso.interrumpido and not caso.completo


def test_el_turno_interrumpido_relanza_la_interrupcion_y_el_script_se_detiene():
    # Mutación K15: si `_ejecutar_turno` no relanzara la interrupción, el script seguiría y
    # dibujaría la entrada; con una recarga, Streamlit no la volvería a entregar y se perdería.
    _, crear = _fabrica_interrumpida()
    at = _enviar(_app(crear), SOLICITUD_A)
    assert not at.exception
    # La entrada se dibuja después del turno: si aparece, el script siguió tras la interrupción.
    assert len(at.chat_input) == 0, "el script siguió después de la interrupción: no se relanzó"


def test_tras_un_turno_interrumpido_el_siguiente_mensaje_abre_un_caso_nuevo_con_aviso():
    fabrica, crear = _fabrica_interrumpida()
    at = _enviar(_app(crear), SOLICITUD_A)
    # Tras «Stop» el script quedó parado a mitad; la siguiente ejecución (la próxima interacción
    # del analista) dibuja la entrada otra vez y no repite el turno interrumpido.
    at = at.run()
    assert len(fabrica.casos) == 1
    at = _enviar(at, SOLICITUD_A)
    assert len(fabrica.casos) == 2  # nunca se reanuda la sesión cortada
    ((_, asistente),) = _turnos(at)  # el historial es el del caso nuevo
    assert _textos(asistente)[0] == presentacion.AVISO_TURNO_INTERRUMPIDO
    assert fabrica.casos[1].completo
