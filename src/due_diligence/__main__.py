"""Punto de entrada manual: ejecuta un caso con el modelo real (contrato `caso.md`, R8).

    uv run python -m due_diligence "<solicitud del analista>"

Es el ÚNICO lugar que carga el entorno (`configuracion.cargar_entorno`): ni el paquete, ni
`ejecutar_caso`, ni los tests lo hacen. Imprime los eventos en orden, la situación de cada frente y
los números que se anotan en la validación (duración de cada frente, solape y coste). La interfaz
de chat es del ticket #11.
"""

import asyncio
import sys
from collections.abc import Callable
from datetime import datetime

from due_diligence import configuracion
from due_diligence.coordinador import Caso, ejecutar_caso
from due_diligence.eventos import TIPO_FRENTE_FIN, TIPO_FRENTE_INICIO, Evento
from due_diligence.frentes import Frente
from due_diligence.informe import informe_vigente
from due_diligence.terminacion import Terminacion

USO = 'Uso: uv run python -m due_diligence "<solicitud del analista>"'
INDEPENDIENTES = (Frente.REGISTRO, Frente.NOTICIAS, Frente.CATEGORIA)


def _hora(marca: datetime) -> str:
    """La hora del evento con su zona: los eventos y los informes guardados van en UTC (#9, R10)."""
    return marca.strftime("%H:%M:%S.%f")[:-3] + " UTC"


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
    escribir(f"  turnos del coordinador: {configuracion.turnos_usados(caso.turnos)}")
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


def main(argumentos: list[str] | None = None) -> int:
    solicitud = " ".join(sys.argv[1:] if argumentos is None else argumentos).strip()
    if not solicitud:
        print(USO, file=sys.stderr)
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    configuracion.cargar_entorno()
    caso = asyncio.run(ejecutar_caso(solicitud))
    imprimir_caso(caso)
    normal = caso.terminacion is not None and caso.terminacion.terminacion is Terminacion.NORMAL
    return 0 if normal else 1


if __name__ == "__main__":
    sys.exit(main())
