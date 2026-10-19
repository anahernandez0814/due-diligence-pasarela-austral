"""Interfaz de chat del due diligence, con Streamlit (#11, contrato `interfaz-chat.md`).

    uv run streamlit run src/due_diligence/chat.py

Es el segundo punto de entrada que carga el entorno (el otro es `__main__`) y comprueba la
credencial con la misma función (R8). Solo dibuja: lo que se ve sale de `presentacion.py`, que lee
la traza y el estado del `Caso`, nunca el texto del modelo. Los indicadores se muestran en vivo
con el observador del registro de eventos y, al terminar el turno, el turno se reconstruye de la
traza (R1). Un turno a la vez: el mensaje queda pendiente y la entrada se deshabilita mientras el
coordinador trabaja (R7).
"""

import asyncio
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import streamlit as st

from due_diligence import configuracion, presentacion
from due_diligence.coordinador import Caso, CasoSinSesion
from due_diligence.eventos import Evento
from due_diligence.presentacion import Decision, Indicador, TurnoMostrado

ICONOS = {
    "delegacion": "➡️",
    "bloqueo": "⛔",
    "informe": "📝",
    "escalamiento": "🚩",
    "aviso": "⚠️",
}


def _caso_real(observador: Callable[[Evento], None] | None) -> Caso:
    return Caso(observador=observador)


@dataclass(frozen=True)
class Dependencias:
    """Lo que la aplicación toma de fuera (R2). Los tests la sustituyen en `session_state`."""

    cargar_entorno: Callable[[], object] = configuracion.cargar_entorno
    entorno: Mapping[str, str] = field(default_factory=lambda: os.environ)
    crear_caso: Callable[[Callable[[Evento], None] | None], Caso] = _caso_real


def _dibujar_indicador(indicador: Indicador) -> None:
    st.markdown(f"{ICONOS[indicador.tipo]} **{indicador.titulo}** · {indicador.hora}")
    st.caption(indicador.detalle)


def _mostrar_en_vivo(evento: Evento) -> None:
    """El observador del caso: escribe el indicador en el contenedor activo, el de «trabajando»."""
    indicador = presentacion.indicador(evento)
    if indicador is not None:
        _dibujar_indicador(indicador)


def _dibujar_turno(turno: TurnoMostrado) -> None:
    """Un turno en el orden de data-model: la cobertura y el estado, antes que la respuesta."""
    with st.chat_message("user"):
        st.markdown(turno.mensaje)
    with st.chat_message("assistant"):
        if turno.aviso:
            st.info(turno.aviso)
        for indicador in turno.indicadores:
            _dibujar_indicador(indicador)
        filas = [
            f"- ✅ {f.frente}: cubierto"
            if f.cubierto
            else f"- ❌ {f.frente}: no cubierto — {f.motivo}"
            for f in turno.cobertura
        ]
        st.markdown("**Cobertura** (calculada por el sistema):\n\n" + "\n".join(filas))
        estado = f"**Estado del caso**: {turno.estado.texto}"
        if turno.estado.clase == presentacion.COMPLETO:
            st.success(estado)
        elif turno.estado.clase == presentacion.ESPERANDO:
            st.info(estado)
        else:
            st.warning(estado)
        st.markdown(turno.respuesta or "(sin respuesta)")
        st.caption(f"Turnos del coordinador en este turno: {turno.turnos}")


def _ejecutar_turno(
    dependencias: Dependencias, texto: str, decision: Decision, aviso: str | None
) -> None:
    """Ejecuta el turno pendiente con los indicadores en vivo y lo guarda en el historial."""
    with st.chat_message("user"):
        st.markdown(texto)
    with st.chat_message("assistant"):
        with st.status("El coordinador está trabajando…", expanded=True) as trabajando:
            if decision is Decision.NUEVO:
                st.session_state["caso"] = dependencias.crear_caso(_mostrar_en_vivo)
                st.session_state["historial"] = []
            caso: Caso = st.session_state["caso"]
            numero = len(caso.estado.mensajes) + 1
            respuesta = None
            turno = caso.ejecutar(texto) if decision is Decision.NUEVO else caso.continuar(texto)
            try:
                asyncio.run(turno)
            except CasoSinSesion:
                respuesta = presentacion.MENSAJE_SIN_SESION
            except Exception as error:  # el `Caso` ya clasificó el turno como anómalo
                respuesta = presentacion.mensaje_fallo_turno(error)
            trabajando.update(label="Turno terminado", state="complete", expanded=False)
    st.session_state["historial"].append(
        presentacion.resumen_del_turno(caso, numero, texto, aviso, respuesta)
    )
    del st.session_state["pendiente"]
    st.rerun()


def main() -> None:
    st.set_page_config(page_title="Due diligence · Pasarela Austral")
    dependencias = st.session_state.get("dependencias") or Dependencias()
    dependencias.cargar_entorno()
    problema = configuracion.comprobar_credencial(dependencias.entorno)
    if problema is not None:
        st.error(problema)
        st.stop()

    st.title("Due diligence de comercios")
    st.caption(
        "Pasarela Austral · datos ficticios. Las horas van en hora de Colombia; la traza y los "
        "registros se guardan en UTC."
    )
    for modo in presentacion.modos_activos(dependencias.entorno):
        st.warning(modo)

    pendiente = st.session_state.get("pendiente")
    if st.button("Caso nuevo", disabled=pendiente is not None):
        st.session_state.pop("caso", None)
        st.session_state["historial"] = []
    for turno in st.session_state.get("historial", []):
        _dibujar_turno(turno)
    if pendiente is not None:
        _ejecutar_turno(dependencias, *pendiente)

    caso = st.session_state.get("caso")
    espera = caso.espera if caso is not None else None
    ayuda = presentacion.aviso_espera(espera) if espera else "Escriba la solicitud del analista"
    texto = st.chat_input(ayuda, disabled=pendiente is not None)
    if texto is None:
        return
    decision = presentacion.decidir_mensaje(caso, texto)
    if decision.accion is Decision.AVISO_ESPERA:
        st.info(decision.aviso)
    elif decision.accion is not Decision.IGNORAR:
        st.session_state["pendiente"] = (texto, decision.accion, decision.aviso)
        st.rerun()


if __name__ == "__main__":
    main()
