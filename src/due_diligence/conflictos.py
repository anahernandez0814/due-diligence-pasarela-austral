"""Conflictos entre las fuentes registrales, calculados por el código (#9; R6, FR-007 a FR-010).

`calcular_conflictos` es el único cálculo: lo usan el hook de `registrar_informe`, la huella del
informe vigente, `Caso.conflictos` y la línea de comandos. Es puro: lee la última consulta válida
del registro que coincide con el comercio identificado y compara, dato a dato, los hechos de cada
fuente. Hay conflicto cuando dos o más fuentes traen valores distintos del mismo dato.

Los valores van en el orden de la respuesta de la pasarela, que **no indica precedencia**: el
código no elige ninguno (I.4). Los resúmenes son textos fijos y no repiten datos del comercio.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from due_diligence.estado import EstadoCaso
from due_diligence.frentes import Frente

RESUMEN_SIN_CONFLICTOS = "Sin conflictos entre las fuentes registrales."
RESUMEN_NO_COMPARABLES = (
    "No se pudieron comparar las fuentes registrales: el registro no respondió."
)
RESUMEN_NO_CALCULADOS = (
    "No se pudieron calcular los conflictos; deben tratarse como no verificados."
)
# El identificador es la clave con la que se agrupan los hechos del comercio, no un dato.
_NO_SE_COMPARA = frozenset({"identificador"})


@dataclass(frozen=True)
class ValorFuente:
    valor: Any
    fuente: str
    fecha: str


@dataclass(frozen=True)
class Conflicto:
    dato: str
    valores: tuple[ValorFuente, ...]


@dataclass(frozen=True)
class ConflictosCaso:
    estado: str  # "sin_conflictos", "con_conflictos", "no_comparables" o "no_calculados"
    lista: tuple[Conflicto, ...]
    resumen: str

    def como_entrada(self) -> dict[str, Any]:
        """La sección `conflictos` del informe (contrato `registrar-informe.md`)."""
        return {
            "resumen": self.resumen,
            "lista": [
                {
                    "dato": c.dato,
                    "valores": [
                        {"valor": v.valor, "fuente": v.fuente, "fecha": v.fecha} for v in c.valores
                    ],
                }
                for c in self.lista
            ],
        }


def no_comparables() -> ConflictosCaso:
    return ConflictosCaso("no_comparables", (), RESUMEN_NO_COMPARABLES)


def no_calculados() -> ConflictosCaso:
    """El marcador del informe mínimo tras un fallo de hook (R9); `calcular_conflictos` no lo da."""
    return ConflictosCaso("no_calculados", (), RESUMEN_NO_CALCULADOS)


def _resumen(cantidad: int) -> str:
    if cantidad == 1:
        return "1 conflicto entre las fuentes registrales."
    return f"{cantidad} conflictos entre las fuentes registrales."


def _hechos_del_comercio(estado: EstadoCaso, identificador: str) -> list[Mapping[str, Any]] | None:
    """Los hechos del comercio en la última consulta válida del registro que coincide con él."""
    coinciden = [
        c.resultado
        for c in estado.consultas
        if c.frente is Frente.REGISTRO
        and c.valido
        and isinstance(c.resultado, Mapping)
        and c.resultado.get("coincidencias") == [identificador]
    ]
    if not coinciden:
        return None
    return [
        h
        for h in coinciden[-1].get("hechos") or []
        if isinstance(h, Mapping)
        and isinstance(h.get("contenido"), Mapping)
        and h["contenido"].get("identificador") == identificador
    ]


def _clave(valor: Any) -> str:
    """Para comparar valores de cualquier forma (un representante es un objeto) sin elegir uno."""
    return json.dumps(valor, ensure_ascii=False, sort_keys=True)


def calcular_conflictos(estado: EstadoCaso) -> ConflictosCaso:
    """Los conflictos del comercio identificado entre las fuentes registrales (R6).

    Sin comercio identificado, o sin una consulta válida del registro que coincida con él, no hay
    nada que comparar: `no_comparables`, nunca `sin_conflictos` (hallazgo U1).
    """
    comercio = estado.comercio
    if comercio is None:
        return no_comparables()
    hechos = _hechos_del_comercio(estado, comercio["identificador"])
    if hechos is None:
        return no_comparables()
    datos: list[str] = []
    for hecho in hechos:
        datos += [d for d in hecho["contenido"] if d not in _NO_SE_COMPARA and d not in datos]
    lista: list[Conflicto] = []
    for dato in datos:
        valores = tuple(
            ValorFuente(
                h["contenido"][dato],
                str((h.get("metadatos") or {}).get("fuente", "")),
                str((h.get("metadatos") or {}).get("fecha", "")),
            )
            for h in hechos
            if dato in h["contenido"]
        )
        if len(valores) >= 2 and len({_clave(v.valor) for v in valores}) > 1:
            lista.append(Conflicto(dato, valores))
    if not lista:
        return ConflictosCaso("sin_conflictos", (), RESUMEN_SIN_CONFLICTOS)
    return ConflictosCaso("con_conflictos", tuple(lista), _resumen(len(lista)))
