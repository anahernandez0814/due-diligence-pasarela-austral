"""Funciones puras del informe del caso (#9; R4, R5, R7, R8, data-model).

- `fuentes_consultadas` y `problemas_de_fuente`: la fuente de cada afirmación tiene que ser una de
  las que el caso consultó para ese frente (FR-004). La pasarela no conoce el caso, así que esto lo
  comprueba el hook. Las fuentes salen de `estado.consultas`, que escribe el `Delegador`.
- `comercio_del_informe`: el comercio que el código pone en el informe (FR-006).

Ninguna escribe en el estado ni registra eventos.
"""

from collections.abc import Mapping
from typing import Any

from due_diligence.estado import EstadoCaso
from due_diligence.frentes import Frente
from servidor_mcp.informe import Problema
from servidor_mcp.normalizar import igual

FUENTE_NO_CONSULTADA = "La fuente no es ninguna de las consultadas para {frente}."


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
