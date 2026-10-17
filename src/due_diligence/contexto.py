"""Contexto explícito de cada subagente (R11, FR-004, FR-005, FR-013).

El `prompt` de cada subagente lo construye este código, no el modelo, y contiene solo los campos
que su frente necesita: nada de la solicitud del analista ni de la conversación del coordinador.
Si falta el dato necesario no se inventa un valor: se lanza `FrenteRechazado`.
"""

from collections.abc import Mapping
from typing import Any

from due_diligence.estado import EstadoCaso
from due_diligence.frentes import Frente


class FrenteRechazado(Exception):
    """La delegación no puede hacerse: falta un dato o una dependencia. El texto es el motivo."""


_INSTRUCCIONES: dict[Frente, str] = {
    Frente.REGISTRO: (
        "Eres el subagente del registro mercantil de la pasarela de pagos. Tu única herramienta es "
        "consultar_registro_mercantil. Llámala una vez con el dato que recibes (un identificador o "
        "un nombre) y responde con un resumen de una o dos líneas. Si hay varias coincidencias, "
        "nómbralas todas: no elijas una. No consultas listas restrictivas ni noticias."
    ),
    Frente.NOTICIAS: (
        "Eres el subagente de noticias de la pasarela de pagos. Tu única herramienta es "
        "buscar_noticias. Llámala una vez con el dato que recibes y responde con un resumen de "
        "una o dos líneas. Una mención en noticias no es una coincidencia en listas restrictivas: "
        "no la presentes como tal. Si la herramienta devuelve un error, repórtalo tal cual."
    ),
    Frente.CATEGORIA: (
        "Eres el subagente de riesgo de categoría de la pasarela de pagos. Tu única herramienta "
        "es consultar_riesgo_categoria. Llámala una vez con la categoría que recibes y responde "
        "con un resumen de una o dos líneas. No decides la habilitación ni escalas el caso."
    ),
    Frente.LISTAS: (
        "Eres el subagente de listas restrictivas de la pasarela de pagos. Tu única herramienta "
        "es consultar_listas_restrictivas. Haz una consulta por cada entidad que recibes (el "
        "comercio y, si lo hay, su representante legal), con el tipo indicado y exactamente los "
        "valores dados, sin modificarlos, y responde con un resumen de una o dos líneas por "
        "entidad. Una mención en noticias no es una coincidencia en listas."
    ),
}


SOLO_LO_DEL_RESULTADO = "No afirmes nada que no esté en el resultado de la herramienta."


def instrucciones(frente: Frente) -> str:
    """El `system_prompt` fijo del subagente de un frente."""
    return f"{_INSTRUCCIONES[frente]} {SOLO_LO_DEL_RESULTADO}"


def _texto(entrada: Mapping[str, Any], campo: str) -> str | None:
    valor = entrada.get(campo)
    if isinstance(valor, str) and valor.strip():
        return valor
    return None


def _entidad(valor: Mapping[str, Any] | None, tipo: str) -> str:
    """Una línea de entidad para el prompt de listas: identificador si lo hay; si no, el nombre."""
    identificador = _texto(valor or {}, "identificador")
    nombre = _texto(valor or {}, "nombre")
    if identificador:
        return f"tipo {tipo}, identificador «{identificador}»" + (
            f", nombre «{nombre}»" if nombre else ""
        )
    return f"tipo {tipo}, nombre «{nombre}»"


def construir_contexto(frente: Frente, entrada: Mapping[str, Any], estado: EstadoCaso) -> str:
    """El prompt del subagente de un frente, con solo lo que ese frente necesita (R11)."""
    if frente in (Frente.REGISTRO, Frente.NOTICIAS):
        identificador, nombre = _texto(entrada, "identificador"), _texto(entrada, "nombre")
        if not identificador and not nombre:
            raise FrenteRechazado(
                "Falta el dato del comercio: se necesita el identificador o el nombre."
            )
        if identificador:
            return f"Consulta con el identificador «{identificador}»."
        return f"Consulta con el nombre «{nombre}»."

    if frente is Frente.CATEGORIA:
        categoria = _texto(entrada, "categoria")
        if not categoria:
            raise FrenteRechazado(
                "Falta la categoría de negocio: no se inventa una; la aporta el analista."
            )
        return f"Consulta el riesgo de la categoría «{categoria}»."

    # Listas: el comercio y el representante salen del estado, tal como los devolvió el registro.
    comercio = estado.comercio
    if comercio is None:
        raise FrenteRechazado(
            estado.motivo_comercio
            or "El registro mercantil no identificó un comercio de forma unívoca."
        )
    lineas = [
        "Consulta las listas restrictivas para estas entidades, tal como las devolvió el registro "
        "mercantil, sin modificar ninguno de sus valores. Haz una consulta por cada una, con el "
        "identificador si lo tiene y, si no, con el nombre:",
        f"1. Comercio: {_entidad(comercio, 'comercio')}.",
    ]
    representante = comercio.get("representante_legal")
    if representante:
        lineas.append(f"2. Representante legal: {_entidad(representante, 'persona')}.")
    else:
        lineas.append("El registro no devolvió representante legal: consulta solo al comercio.")
    return "\n".join(lineas)
