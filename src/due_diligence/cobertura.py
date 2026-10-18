"""Cobertura del caso calculada por el código (#8, R5, contrato `cobertura.md`; FR-010, FR-012).

`calcular_cobertura` es el único cálculo: lo usan `Caso.completo`, los hooks de
`registrar_informe` y `escalar_a_cumplimiento` y la línea de comandos. Es puro: lee la situación de
cada frente y su último error en el estado, no escribe nada y no registra eventos.

`registro_caido` (#9, R8) lee lo mismo para el frente de registro. Vive aquí para que lo usen
`informe.py` y `conflictos.py` sin importarse entre ellos.

Los motivos son textos fijos por situación y causa: el motivo crudo del estado puede traer
identificadores del registro (por ejemplo, las coincidencias de un nombre ambiguo) y la cobertura
no repite datos del comercio.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from due_diligence.ejecutor import es_bloqueo_de_hook
from due_diligence.estado import Causa, EstadoCaso, Situacion
from due_diligence.frentes import Frente
from due_diligence.reglas import consulta_del_comercio

MOTIVO_SIN_INICIAR = "no se delegó"
MOTIVO_EN_CURSO = "seguía en curso"
MOTIVO_SIN_DETALLE = "no terminó"

_MOTIVOS: dict[Causa, str] = {
    Causa.TERMINACION_ANOMALA: "el subagente no terminó con normalidad",
    Causa.ERROR_DE_FUENTE: "error de la fuente",
    Causa.SIN_CONSULTAS: "el subagente no hizo ninguna consulta",
    Causa.RESULTADO_INVALIDO: "un resultado no tiene la forma del contrato de la pasarela",
    Causa.CONSULTA_INCOMPLETA: "faltó la consulta del comercio o de su representante legal",
    Causa.RECHAZADO: (
        "se rechazó la delegación: faltaba un dato o el registro no identificó un comercio único"
    ),
    Causa.CANCELADO: "se canceló",
    Causa.INVALIDADO: "el comercio del registro cambió después de consultar listas",
    # #10, FR-027 (R7): noticias consultado con otro nombre o identificador.
    Causa.OTRO_COMERCIO: (
        "se consultó con un nombre o identificador que no es el del comercio identificado"
    ),
}
# Causas de un registro que no respondió (#9, R8). `error_de_fuente` solo si algún error real no es
# `entrada_invalida`: con una entrada inválida la fuente respondió (caso límite de la spec).
_CAUSAS_DE_CAIDA = frozenset(
    {Causa.TERMINACION_ANOMALA, Causa.SIN_CONSULTAS, Causa.RESULTADO_INVALIDO, Causa.CANCELADO}
)


@dataclass(frozen=True)
class CoberturaFrente:
    frente: Frente
    cubierto: bool
    motivo: str  # vacío si está cubierto
    causa: Causa | None
    intentos: int


@dataclass(frozen=True)
class CoberturaCaso:
    frentes: dict[Frente, CoberturaFrente]  # los cuatro, en el orden de `Frente`
    completa: bool

    def lineas(self) -> list[str]:
        """La cobertura que se registra: una línea de resumen y una por frente (contrato)."""
        cubiertos = sum(c.cubierto for c in self.frentes.values())
        total = len(self.frentes)
        estado = "completa" if self.completa else "incompleta"
        lineas = [f"Cobertura {estado}: {cubiertos} de {total} frentes cubiertos."]
        for cobertura in self.frentes.values():
            if cobertura.cubierto:
                lineas.append(f"{cobertura.frente.value}: cubierto.")
                continue
            intentos = f"; {cobertura.intentos} intentos" if cobertura.intentos > 1 else ""
            lineas.append(f"{cobertura.frente.value}: no cubierto; {cobertura.motivo}{intentos}.")
        return lineas


def _causa(error: Mapping[str, Any] | None) -> Causa | None:
    try:
        return Causa(error.get("causa")) if error else None
    except ValueError:
        return None


def _motivo(causa: Causa | None, error: Mapping[str, Any] | None) -> str:
    if causa is None:
        return MOTIVO_SIN_DETALLE
    if causa is Causa.ERROR_DE_FUENTE:
        # Solo los errores de la fuente: un bloqueo de hook (#7) no es un error de la fuente.
        obtenido = (error or {}).get("obtenido") or {}
        tipos = [
            str(e.get("tipo"))
            for e in obtenido.get("errores") or []
            if isinstance(e, dict) and not es_bloqueo_de_hook(e)
        ]
        return f"{_MOTIVOS[causa]} ({', '.join(tipos)})" if tipos else _MOTIVOS[causa]
    return _MOTIVOS[causa]


def _de_otro_comercio(estado: EstadoCaso, frente: Frente) -> bool:
    """Noticias terminó, pero para otro comercio que el identificado (#10, FR-027, R7).

    Con el comercio identificado, su último resultado tiene consultas válidas y ninguna es del
    comercio: por ejemplo, la del nombre ambiguo del primer turno del caso (d). Sin comercio
    identificado, o sin resultado guardado, no se puede afirmar que sea de otro.
    """
    comercio = estado.comercio
    resultado = estado.resultados.get(frente)
    if frente is not Frente.NOTICIAS or comercio is None or resultado is None:
        return False
    validas = [c for c in resultado.consultas if c.valido]
    return bool(validas) and not any(consulta_del_comercio(c.argumentos, comercio) for c in validas)


def _del_frente(estado: EstadoCaso, frente: Frente) -> CoberturaFrente:
    situacion = estado.situacion(frente)
    if situacion is Situacion.TERMINADO and _de_otro_comercio(estado, frente):
        motivo = _MOTIVOS[Causa.OTRO_COMERCIO]
        return CoberturaFrente(frente, False, motivo, Causa.OTRO_COMERCIO, 0)
    if situacion is Situacion.TERMINADO:
        return CoberturaFrente(frente, True, "", None, 0)
    if situacion is Situacion.SIN_INICIAR:
        return CoberturaFrente(frente, False, MOTIVO_SIN_INICIAR, None, 0)
    if situacion is Situacion.EN_CURSO:
        return CoberturaFrente(frente, False, MOTIVO_EN_CURSO, None, 0)
    error = estado.errores.get(frente)
    causa = _causa(error)
    intentos = error.get("intento", 0) if error else 0
    return CoberturaFrente(
        frente, False, _motivo(causa, error), causa, intentos if isinstance(intentos, int) else 0
    )


def calcular_cobertura(estado: EstadoCaso) -> CoberturaCaso:
    """La cobertura de los cuatro frentes: cubierto solo si terminó con normalidad (FR-010)."""
    frentes = {frente: _del_frente(estado, frente) for frente in Frente}
    return CoberturaCaso(frentes, all(c.cubierto for c in frentes.values()))


def registro_caido(estado: EstadoCaso) -> bool:
    """El registro no terminó y la fuente no respondió, quede o no un reintento (R8)."""
    if estado.situacion(Frente.REGISTRO) is not Situacion.NO_TERMINADO:
        return False
    error = estado.errores.get(Frente.REGISTRO) or {}
    try:
        causa = Causa(error.get("causa"))
    except ValueError:
        return False
    if causa in _CAUSAS_DE_CAIDA:
        return True
    if causa is not Causa.ERROR_DE_FUENTE:
        return False
    errores = (error.get("obtenido") or {}).get("errores") or []
    tipos = [e.get("tipo") for e in errores if isinstance(e, Mapping) and not es_bloqueo_de_hook(e)]
    return any(tipo != "entrada_invalida" for tipo in tipos)
