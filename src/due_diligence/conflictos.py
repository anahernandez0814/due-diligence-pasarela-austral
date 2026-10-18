"""Conflictos entre las fuentes registrales, calculados por el código (#9; R6, FR-007 a FR-010).

`calcular_conflictos` es el único cálculo: lo usan el hook de `registrar_informe`, la huella del
informe vigente, `Caso.conflictos` y la línea de comandos. Es puro: lee la última consulta válida
del registro que coincide con el comercio identificado y compara, dato a dato, los hechos de cada
fuente. Hay conflicto cuando dos o más fuentes traen valores distintos del mismo dato.

Los valores van en el orden de la respuesta de la pasarela, que **no indica precedencia**: el
código no elige ninguno (I.4). Los resúmenes son textos fijos y no repiten datos del comercio.

Sin comparación, el estado dice por qué, para que el resumen sea verdadero y la huella distinga los
casos si después se vuelve a delegar el registro: `registro_caido` (la fuente no respondió),
`sin_comercio` (respondió o no terminó, pero no hay comercio identificado) y `sin_consulta` (hay
comercio, pero ninguna consulta válida del registro lo trae).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from due_diligence.cobertura import registro_caido
from due_diligence.estado import EstadoCaso
from due_diligence.frentes import Frente

RESUMEN_SIN_CONFLICTOS = "Sin conflictos entre las fuentes registrales."
RESUMEN_REGISTRO_CAIDO = (
    "No se pudieron comparar las fuentes registrales: el registro no respondió."
)
RESUMEN_SIN_COMERCIO = "No se compararon las fuentes registrales: no hay comercio identificado."
RESUMEN_SIN_CONSULTA = (
    "No se compararon las fuentes registrales: ninguna consulta válida del registro trae el "
    "comercio identificado."
)
RESUMEN_NO_CALCULADOS = (
    "No se pudieron calcular los conflictos; deben tratarse como no verificados."
)
_RESUMENES_SIN_COMPARAR = {
    "registro_caido": RESUMEN_REGISTRO_CAIDO,
    "sin_comercio": RESUMEN_SIN_COMERCIO,
    "sin_consulta": RESUMEN_SIN_CONSULTA,
}
# Los estados en los que no se compararon las fuentes (nunca `sin_conflictos`, hallazgo U1).
SIN_COMPARAR = frozenset(_RESUMENES_SIN_COMPARAR)


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
    # "sin_conflictos", "con_conflictos", uno de `SIN_COMPARAR` o "no_calculados"
    estado: str
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


def sin_comparar(estado: str) -> ConflictosCaso:
    """Sin comparación, con el resumen fijo de su estado (uno de `SIN_COMPARAR`)."""
    return ConflictosCaso(estado, (), _RESUMENES_SIN_COMPARAR[estado])


def no_calculados() -> ConflictosCaso:
    """El marcador del informe mínimo tras un fallo de hook (R9); `calcular_conflictos` no lo da."""
    return ConflictosCaso("no_calculados", (), RESUMEN_NO_CALCULADOS)


def _resumen(cantidad: int) -> str:
    if cantidad == 1:
        return "1 conflicto entre las fuentes registrales."
    return f"{cantidad} conflictos entre las fuentes registrales."


def _hechos_del_comercio(estado: EstadoCaso, identificador: str) -> list[Mapping[str, Any]] | None:
    """Los hechos del comercio en la última consulta válida del registro que coincide con él.

    Se agrupan por el identificador exacto: un hecho con otro identificador es de otro comercio y
    no se compara. Por eso el identificador nunca da un conflicto.
    """
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


def clave_de_valor(valor: Any) -> str:
    """Para comparar valores de cualquier forma (un representante es un objeto) sin elegir uno."""
    return json.dumps(valor, ensure_ascii=False, sort_keys=True)


def calcular_conflictos(estado: EstadoCaso) -> ConflictosCaso:
    """Los conflictos del comercio identificado entre las fuentes registrales (R6).

    Sin comercio identificado, o sin una consulta válida del registro que coincida con él, no hay
    nada que comparar: uno de `SIN_COMPARAR`, nunca `sin_conflictos` (hallazgo U1). Solo el
    registro caído dice que la fuente no respondió.
    """
    comercio = estado.comercio
    if comercio is None:
        return sin_comparar("registro_caido" if registro_caido(estado) else "sin_comercio")
    hechos = _hechos_del_comercio(estado, comercio["identificador"])
    if hechos is None:
        return sin_comparar("sin_consulta")
    datos: list[str] = []
    for hecho in hechos:
        datos += [d for d in hecho["contenido"] if d not in datos]
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
        if len(valores) >= 2 and len({clave_de_valor(v.valor) for v in valores}) > 1:
            lista.append(Conflicto(dato, valores))
    if not lista:
        return ConflictosCaso("sin_conflictos", (), RESUMEN_SIN_CONFLICTOS)
    return ConflictosCaso("con_conflictos", tuple(lista), _resumen(len(lista)))
