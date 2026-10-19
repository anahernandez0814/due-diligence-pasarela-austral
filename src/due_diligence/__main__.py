"""Punto de entrada manual: ejecuta un caso con el modelo real (contrato `caso.md`, R8).

    uv run python -m due_diligence "<solicitud del analista>"

Es uno de los dos puntos de entrada que cargan el entorno (`configuracion.cargar_entorno`); el otro
es la interfaz de chat (`chat.py`, #11). Ni el paquete, ni `ejecutar_caso`, ni los tests lo hacen.
Tras cargarlo comprueba la credencial con la misma función que el chat (#11, R8). Imprime los
eventos en orden, la situación de cada frente y los números que se anotan en la validación
(duración de cada frente, solape y coste).
"""

import asyncio
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from due_diligence import configuracion
from due_diligence.coordinador import Caso, CasoSinSesion, ejecutar_caso
from due_diligence.eventos import (
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
    Evento,
)
from due_diligence.frentes import Frente
from due_diligence.informe import informe_vigente

# El mismo texto que el chat (#11, R6): vive en `presentacion` y se sigue exponiendo aquí.
from due_diligence.presentacion import MENSAJE_SIN_SESION, aviso_espera
from due_diligence.terminacion import Terminacion

USO = 'Uso: uv run python -m due_diligence [--sin-continuar] "<solicitud del analista>"'
# #10 (R12, contrato `continuacion-y-cierre.md`): con espera del analista se le pregunta por la
# entrada estándar, salvo con esta bandera (para los tests y las validaciones de un solo turno).
BANDERA_SIN_CONTINUAR = "--sin-continuar"
PREGUNTA_AL_ANALISTA = (
    "El coordinador espera su respuesta; escríbala o deje la línea vacía para terminar: "
)
INDEPENDIENTES = (Frente.REGISTRO, Frente.NOTICIAS, Frente.CATEGORIA)


def _hora(marca: datetime) -> str:
    """La hora del evento en UTC, como los eventos y los informes guardados (#9, R10).

    Convierte antes de formatear: un reloj inyectado en otra zona no se muestra como UTC.
    """
    return marca.astimezone(UTC).strftime("%H:%M:%S.%f")[:-3] + " UTC"


def _eventos_de(eventos: list[Evento], tipo: str) -> dict[Frente, Evento]:
    """El primer evento de cada frente: una re-delegación no cambia el inicio ni el solape."""
    primeros: dict[Frente, Evento] = {}
    for evento in eventos:
        if evento.tipo == tipo and evento.frente is not None:
            primeros.setdefault(evento.frente, evento)
    return primeros


def duraciones(eventos: list[Evento]) -> dict[Frente, float]:
    """Segundos entre el inicio y el fin de cada frente que terminó."""
    inicios, fines = _eventos_de(eventos, TIPO_FRENTE_INICIO), _eventos_de(eventos, TIPO_FRENTE_FIN)
    return {f: (fines[f].marca - inicios[f].marca).total_seconds() for f in inicios if f in fines}


def _si_no(valor: bool | None) -> str:
    return "no aplica" if valor is None else ("sí" if valor else "no")


def hubo_solape(eventos: list[Evento]) -> bool | None:
    """¿Los frentes independientes empezaron antes de que terminara alguno de ellos?

    Solo cuenta los que se delegaron. `None` (se imprime «no aplica») si no empezó más de uno.
    Se lee de la secuencia de los eventos, no del reloj.
    """
    inicios, fines = _eventos_de(eventos, TIPO_FRENTE_INICIO), _eventos_de(eventos, TIPO_FRENTE_FIN)
    empezados = [inicios[f].secuencia for f in INDEPENDIENTES if f in inicios]
    terminados = [fines[f].secuencia for f in INDEPENDIENTES if f in fines]
    if len(empezados) < 2:
        return None
    return not terminados or max(empezados) < min(terminados)


def imprimir_caso(caso: Caso, escribir: Callable[[str], None] = print) -> None:
    eventos = caso.eventos()
    escribir("Eventos del caso:")
    for evento in eventos:
        frente = evento.frente.value if evento.frente else "-"
        # Los eventos de las reglas (#7) llevan la regla de negocio que los causó: se ve en el chat.
        regla = f" [{evento.regla}]" if evento.regla else ""
        # La acción que un bloqueo impidió, sin datos del comercio (#9, FR-017).
        accion = f" (acción: {evento.accion})" if evento.accion else ""
        escribir(
            f"{evento.secuencia:>3}  {_hora(evento.marca)}  {evento.tipo:<24} {frente:<10} "
            f"{evento.detalle}{regla}{accion}"
        )
    escribir("")
    escribir("Frentes:")
    for frente, situacion in caso.estado.frentes.items():
        motivo = caso.estado.motivo(frente)
        escribir(f"  {frente.value:<10} {situacion.value}" + (f" ({motivo})" if motivo else ""))
    escribir(f"  consultas realizadas: {len(caso.estado.consultas)}")
    if caso.estado.comercio:
        escribir(f"  comercio del registro: {caso.estado.comercio.get('identificador')}")
    escribir("")
    # La misma cobertura que se registra en el informe y en el escalamiento (#8, FR-014).
    escribir("Cobertura:")
    for linea in caso.cobertura.lineas():
        escribir(f"  {linea}")
    escribir("")
    # Los conflictos que el código pone en el informe (#9, FR-010): todos los valores, sin elegir.
    conflictos = caso.conflictos
    escribir("Conflictos:")
    escribir(f"  {conflictos.resumen}")
    for conflicto in conflictos.lista:
        valores = "; ".join(f"{v.valor} ({v.fuente}, {v.fecha})" for v in conflicto.valores)
        escribir(f"  {conflicto.dato}: {valores}")
    escribir("")
    escribir("Informes registrados:")
    informes = caso.estado.informes
    if not informes:
        escribir("  ninguno")
    vigente = informe_vigente(caso.estado)
    for posicion, informe in enumerate(informes):
        es_vigente = vigente and posicion == len(informes) - 1
        minimo = "; informe mínimo" if informe.minimo else ""
        escribir(
            f"  {informe.id}: recomendación {informe.recomendacion}; "
            f"vigente: {'sí' if es_vigente else 'no'}{minimo}"
        )
    escribir("")
    # Los escalamientos que la pasarela aceptó, con su id y sus causas, como dice su evento (#10).
    escribir("Escalamientos registrados:")
    escalamientos = [e.detalle for e in eventos if e.tipo == TIPO_ESCALAMIENTO_REGISTRADO]
    if not escalamientos:
        escribir("  ninguno")
    for detalle in escalamientos:
        escribir(f"  {detalle}")
    espera = caso.espera
    escribir(f"Esperando al analista: {espera.motivo}" if espera else "Sin espera del analista")
    escribir("")
    escribir("Números de la validación:")
    for frente, segundos in duraciones(eventos).items():
        escribir(f"  duración de {frente.value}: {segundos:.1f} s")
    if len(eventos) > 1:
        total = (eventos[-1].marca - eventos[0].marca).total_seconds()
        escribir(f"  duración total del caso: {total:.1f} s")
    solape = hubo_solape(eventos)
    escribir(f"  solape entre los frentes independientes delegados: {_si_no(solape)}")
    costes = {"coordinador": caso.coste_usd}
    for frente, resultado in caso.estado.resultados.items():
        costes[frente.value] = resultado.coste_usd
    for nombre, coste in costes.items():
        escribir(f"  coste de {nombre}: {'sin dato' if coste is None else f'{coste:.4f} USD'}")
    conocidos = [c for c in costes.values() if c is not None]
    escribir(f"  coste total: {sum(conocidos):.4f} USD")
    # Los del último turno frente al límite, que es por turno (#11, FR-004); nunca la suma del caso.
    ultimo = caso.turnos_por_turno[-1] if caso.turnos_por_turno else None
    escribir(f"  turnos del coordinador en este turno: {configuracion.turnos_usados(ultimo)}")
    escribir("")
    if caso.terminacion:
        escribir(f"Terminación del caso: {caso.terminacion.terminacion.value}")
    escribir(f"Caso completo: {'sí' if caso.completo else 'no'}")
    if caso.estado.cierre_sin_escalar:
        escribir("El caso terminó sin el escalamiento obligatorio (cierre_sin_escalar).")
    if caso.estado.cierre_sin_informe:
        escribir("El caso terminó sin el informe vigente (cierre_sin_informe).")
    if caso.estado.libro.fallo_de_hook:
        escribir("Un hook de las reglas falló: el caso se bloqueó por precaución.")
    escribir("")
    escribir("Respuesta del coordinador:")
    escribir(caso.respuesta or "(sin respuesta)")


def _conversar(caso: Caso, leer: Callable[[str], str]) -> bool:
    """Mientras el caso espera al analista, pregunta y continúa en el mismo caso (#10, FR-019).

    Termina con una línea vacía o con el fin de la entrada, y antes avisa de que el coordinador
    sigue esperando (#11, FR-005), en lugar de terminar en silencio. Es recursiva y no un `while`,
    como el resto del ciclo (FR-010 del #6): cada vuelta es un turno más que termina por su razón
    de parada. Devuelve `False` si el caso no se pudo continuar por falta de sesión: el analista ve
    `MENSAJE_SIN_SESION`, no una traza.
    """
    espera = caso.espera
    if espera is None:
        return True
    try:
        respuesta = leer(PREGUNTA_AL_ANALISTA).strip()
    except EOFError:
        respuesta = ""
    if not respuesta:
        print(aviso_espera(espera))
        return True
    try:
        asyncio.run(caso.continuar(respuesta))
    except CasoSinSesion:
        print(MENSAJE_SIN_SESION, file=sys.stderr)
        return False
    imprimir_caso(caso)
    return _conversar(caso, leer)


def main(argumentos: list[str] | None = None, leer: Callable[[str], str] = input) -> int:
    partes = list(sys.argv[1:] if argumentos is None else argumentos)
    continuar = BANDERA_SIN_CONTINUAR not in partes
    solicitud = " ".join(p for p in partes if p != BANDERA_SIN_CONTINUAR).strip()
    if not solicitud:
        print(USO, file=sys.stderr)
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    configuracion.cargar_entorno()
    problema = configuracion.comprobar_credencial()
    if problema is not None:
        print(problema, file=sys.stderr)
        return 2
    caso = asyncio.run(ejecutar_caso(solicitud))
    imprimir_caso(caso)
    continuado = _conversar(caso, leer) if continuar else True
    normal = caso.terminacion is not None and caso.terminacion.terminacion is Terminacion.NORMAL
    return 0 if normal and continuado else 1


if __name__ == "__main__":
    sys.exit(main())
