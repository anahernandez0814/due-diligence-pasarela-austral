"""Funciones puras del informe del caso (#9; R4, R5, R7, R8, data-model).

- `fuentes_consultadas` y `problemas_de_fuente`: la fuente de cada afirmación tiene que ser una de
  las que el caso consultó para ese frente (FR-004). La pasarela no conoce el caso, así que esto lo
  comprueba el hook. Las fuentes salen de `estado.consultas`, que escribe el `Delegador`.
- `comercio_del_informe`: el comercio que el código pone en el informe (FR-006).
- `huella_actual`, `informe_vigente` y `cambios`: qué cuenta como cambio para FR-023 (R7, decisión
  de la analista): solo la cobertura (cubierto o no por frente), los conflictos, las causas de
  escalamiento y el comercio.
- `registro_caido` y `requiere_informe`: cuándo el cierre exige el informe (FR-011, R8).

Ninguna escribe en el estado ni registra eventos.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from due_diligence.cobertura import CoberturaCaso, calcular_cobertura
from due_diligence.conflictos import ConflictosCaso, calcular_conflictos
from due_diligence.ejecutor import es_bloqueo_de_hook
from due_diligence.estado import Causa, EstadoCaso, Situacion
from due_diligence.frentes import Frente
from due_diligence.reglas import causas_vigentes
from servidor_mcp.informe import Problema
from servidor_mcp.normalizar import igual

FUENTE_NO_CONSULTADA = "La fuente no es ninguna de las consultadas para {frente}."
# Componente de la huella con el caso sellado (hallazgo I1): el informe mínimo lleva textos fijos
# en la cobertura y los conflictos, así que la huella no los calcula, ni en el `PreToolUse` ni en
# el `Stop`.
NO_CALCULADOS = "no_calculados"
# Causas de un registro que no respondió (R8). `error_de_fuente` solo si algún error real no es
# `entrada_invalida`: con una entrada inválida la fuente respondió (caso límite de la spec).
_CAUSAS_DE_CAIDA = frozenset(
    {Causa.TERMINACION_ANOMALA, Causa.SIN_CONSULTAS, Causa.RESULTADO_INVALIDO, Causa.CANCELADO}
)
_NOMBRES_DE_COMPONENTE = {
    "cobertura": "la cobertura",
    "conflictos": "los conflictos",
    "causas": "las causas de escalamiento",
    "comercio": "el comercio",
}


@dataclass(frozen=True)
class Huella:
    """Lo que, si cambia, deja el informe sin vigencia (R7)."""

    cobertura: tuple[tuple[str, bool], ...] | str
    conflictos: tuple[Any, ...] | str
    causas: frozenset[str]
    comercio: tuple[Any, Any, bool] | None


@dataclass(frozen=True)
class InformeRegistrado:
    id: str  # el que devolvió la pasarela (INF-…)
    recomendacion: str
    minimo: bool  # registrado con el caso sellado (FR-014)
    huella: Huella


def fuentes_consultadas(estado: EstadoCaso, frente: Frente) -> list[str]:
    """Las fuentes de las consultas válidas del frente, sin repetir y en orden de aparición (R4).

    Cuentan la fuente de cada hecho y las de `metadatos.fuentes`: una respuesta sin coincidencias
    no tiene hechos, pero sí su fuente.
    """
    fuentes: list[str] = []
    for c in estado.consultas:
        if c.frente is not frente or not c.valido or not isinstance(c.resultado, Mapping):
            continue
        de_hechos = [
            (h.get("metadatos") or {}).get("fuente")
            for h in c.resultado.get("hechos") or []
            if isinstance(h, Mapping)
        ]
        metadatos = c.resultado.get("metadatos") or {}
        for fuente in [*de_hechos, *(metadatos.get("fuentes") or [])]:
            if isinstance(fuente, str) and fuente.strip() and fuente not in fuentes:
                fuentes.append(fuente)
    return fuentes


def problemas_de_fuente(estado: EstadoCaso, hallazgos: Any) -> list[Problema]:
    """Un problema por afirmación cuya fuente no se consultó para su frente (FR-004).

    Solo mira las afirmaciones bien formadas: lo mal formado ya lo nombra `validar_informe`. Compara
    con `normalizar.igual` (mayúsculas, tildes y espacios no importan).
    """
    if not isinstance(hallazgos, Mapping):
        return []
    problemas: list[Problema] = []
    for frente in Frente:
        afirmaciones = hallazgos.get(frente.value)
        if not isinstance(afirmaciones, list):
            continue
        admitidas = fuentes_consultadas(estado, frente)
        for posicion, afirmacion in enumerate(afirmaciones):
            fuente = afirmacion.get("fuente") if isinstance(afirmacion, Mapping) else None
            if not isinstance(fuente, str) or not fuente.strip():
                continue
            if not any(igual(fuente, admitida) for admitida in admitidas):
                problemas.append(
                    Problema(
                        f"hallazgos.{frente.value}[{posicion}].fuente",
                        FUENTE_NO_CONSULTADA.format(frente=frente.value),
                    )
                )
    return problemas


def huella_con(
    estado: EstadoCaso, cobertura: CoberturaCaso | None, conflictos: ConflictosCaso | None
) -> Huella:
    """La huella con la cobertura y los conflictos ya calculados (los mismos que se sustituyen).

    Con el caso sellado no se usan: los dos componentes valen `NO_CALCULADOS` (hallazgo I1).
    """
    comercio = comercio_del_informe(estado)
    if estado.libro.fallo_de_hook or cobertura is None or conflictos is None:
        componente_cobertura: tuple[tuple[str, bool], ...] | str = NO_CALCULADOS
        componente_conflictos: tuple[Any, ...] | str = NO_CALCULADOS
    else:
        componente_cobertura = tuple(
            (frente.value, c.cubierto) for frente, c in cobertura.frentes.items()
        )
        componente_conflictos = (
            conflictos.estado,
            tuple(
                (
                    c.dato,
                    tuple(
                        (v.fuente, json.dumps(v.valor, ensure_ascii=False, sort_keys=True))
                        for v in c.valores
                    ),
                )
                for c in conflictos.lista
            ),
        )
    return Huella(
        componente_cobertura,
        componente_conflictos,
        causas_vigentes(estado.libro),
        (comercio["identificador"], comercio["nombre"], comercio["verificado"])
        if comercio
        else None,
    )


def huella_actual(estado: EstadoCaso) -> Huella:
    """La huella del caso ahora. Con el sello, sin llamar a los cálculos (hallazgo I1)."""
    if estado.libro.fallo_de_hook:
        return huella_con(estado, None, None)
    return huella_con(estado, calcular_cobertura(estado), calcular_conflictos(estado))


def cambios(antes: Huella, despues: Huella) -> list[str]:
    """Los componentes que difieren, nombrados para el motivo del `Stop`, sin datos del caso."""
    return [
        nombre
        for campo, nombre in _NOMBRES_DE_COMPONENTE.items()
        if getattr(antes, campo) != getattr(despues, campo)
    ]


def informe_vigente(estado: EstadoCaso) -> bool:
    """Si hay informe y la huella del último coincide con la actual (FR-023)."""
    return bool(estado.informes) and estado.informes[-1].huella == huella_actual(estado)


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


def registro_reintentable(estado: EstadoCaso) -> bool:
    """Si la política del #8 admite otro intento del registro (su último error lo dice)."""
    return (estado.errores.get(Frente.REGISTRO) or {}).get("reintentable") is True


def requiere_informe(estado: EstadoCaso) -> bool:
    """El cierre exige informe con el comercio identificado o con el registro caído (FR-011)."""
    return estado.comercio is not None or registro_caido(estado)


def comercio_del_informe(estado: EstadoCaso) -> dict[str, Any] | None:
    """El comercio que va en el informe (FR-006, R5), o `None` si no hay ninguno.

    El identificado de forma unívoca va con `verificado: true`. Sin identificación, el que pidió el
    analista (la última delegación del registro) va con `verificado: false` y sin inventar el dato
    que falte: es el caso del registro caído, y también el de un informe que el coordinador
    registra sin comercio identificado. Sin ninguno de los dos, no hay comercio.
    """
    comercio = estado.comercio
    if comercio is not None:
        return {
            "identificador": comercio.get("identificador"),
            "nombre": comercio.get("nombre"),
            "verificado": True,
        }
    pedido = estado.comercio_pedido
    if pedido is None:
        return None
    return {
        "identificador": pedido.get("identificador"),
        "nombre": pedido.get("nombre"),
        "verificado": False,
    }
