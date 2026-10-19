"""Esquema del informe de `registrar_informe` (#9, R2, data-model, contrato `registrar-informe.md`).

`validar_informe` es el **único** validador de la forma del informe: lo usan la pasarela
(`decisiones.registrar_informe`), el hook del coordinador y la `PasarelaSimulada`. Es puro y
devuelve **todos** los problemas, cada uno con su ruta (`hallazgos.listas[1].fuente`) y un texto en
español. Nunca repite el valor recibido: una clave desconocida se informa en la ruta de su padre.

Valida la forma, no las reglas de negocio: que la recomendación sea del conjunto cerrado, que la
fuente se haya consultado o que el caso esté escalado lo comprueban los hooks del SDK.

La afirmación junta texto, fuente y fecha en un objeto plano: es la cita que escribe el
coordinador a partir de los resultados, no un resultado de la pasarela (research R2, T3).
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

FRENTES_INFORME = ("registro", "listas", "noticias", "categoria")
# Orden en que se nombran las partes que faltan (el del #5, con `conflictos` al final).
PARTES_INFORME = ("comercio", "recomendacion", "hallazgos", "cobertura", "conflictos")
# El resumen al oficial de `escalar_a_cumplimiento` (#10, R6): los cinco campos del principio V y
# los conflictos que pone el código (FR-010), en el orden en que se nombran los que faltan.
PARTES_RESUMEN = (
    "comercio",
    "hallazgos",
    "cobertura",
    "causa_escalamiento",
    "accion_recomendada",
    "conflictos",
)
# El comercio que pone el código en un escalamiento sin comercio identificado ni pedido, con el
# caso sellado (#10, R5, D2): textos fijos que pasan la validación, para que escalar no se deniegue.
COMERCIO_NO_IDENTIFICADO = {
    "identificador": "no identificado",
    "nombre": "no identificado",
    "verificado": False,
}

_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")
_CAMPOS_AFIRMACION = ("texto", "fuente", "fecha")
_CAMPOS_COMERCIO = ("identificador", "nombre", "verificado")
_CAMPOS_VALOR = ("valor", "fuente", "fecha")

FALTA = "Falta el campo."
DEBE_SER_TEXTO = "Debe ser un texto no vacío."
DEBE_SER_OBJETO = "Debe ser un objeto."
DEBE_SER_LISTA = "Debe ser una lista."
DEBE_SER_FECHA = "Debe ser una fecha AAAA-MM-DD válida."
DEBE_SER_BOOL = "Debe ser verdadero o falso."
CAMPO_DESCONOCIDO = "Tiene un campo desconocido; debe tener solo: {campos}."
FRENTE_DESCONOCIDO = "Tiene un frente desconocido; debe ser registro, listas, noticias o categoria."
COMERCIO_VERIFICADO = "Con verificado verdadero hacen falta el identificador y el nombre."
COMERCIO_SIN_DATOS = "Debe tener al menos el identificador o el nombre."
COBERTURA_MAL = "Debe ser un texto no vacío o una lista de textos no vacíos."
DOS_VALORES = "Debe ser una lista con al menos dos valores en conflicto."


@dataclass(frozen=True)
class Problema:
    ruta: str
    texto: str

    def como_dict(self) -> dict[str, str]:
        return {"ruta": self.ruta, "texto": self.texto}


def _texto(valor: Any) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _fecha(valor: Any) -> bool:
    if not isinstance(valor, str) or not _FECHA.fullmatch(valor):
        return False
    try:
        date.fromisoformat(valor)
    except ValueError:
        return False
    return True


def _presente(objeto: Mapping[str, Any], campo: str) -> bool:
    """Como `entradas._vacio` al revés: ausente, texto en blanco o contenedor vacío no cuentan."""
    valor = objeto.get(campo)
    if isinstance(valor, str):
        return bool(valor.strip())
    if isinstance(valor, (list, dict)):
        return bool(valor)
    return valor is not None


def _desconocidos(objeto: Mapping[str, Any], ruta: str, campos: tuple[str, ...]) -> list[Problema]:
    if any(clave not in campos for clave in objeto):
        return [Problema(ruta, CAMPO_DESCONOCIDO.format(campos=", ".join(campos)))]
    return []


def _citas(objeto: Mapping[str, Any], ruta: str, campos: tuple[str, ...]) -> list[Problema]:
    """Una afirmación o un valor en conflicto: textos no vacíos y la fecha válida."""
    problemas = _desconocidos(objeto, ruta, campos)
    for campo in campos:
        if campo == "valor":
            if campo not in objeto:
                problemas.append(Problema(f"{ruta}.{campo}", FALTA))
            continue
        if campo == "fecha":
            if not _fecha(objeto.get(campo)):
                problemas.append(Problema(f"{ruta}.{campo}", DEBE_SER_FECHA))
            continue
        if not _texto(objeto.get(campo)):
            problemas.append(Problema(f"{ruta}.{campo}", DEBE_SER_TEXTO))
    return problemas


def _comercio(comercio: Any) -> list[Problema]:
    if not isinstance(comercio, Mapping):
        return [Problema("comercio", DEBE_SER_OBJETO)]
    problemas = _desconocidos(comercio, "comercio", _CAMPOS_COMERCIO)
    verificado = comercio.get("verificado")
    if not isinstance(verificado, bool):
        return [*problemas, Problema("comercio.verificado", DEBE_SER_BOOL)]
    if verificado:
        problemas += [
            Problema(f"comercio.{campo}", COMERCIO_VERIFICADO)
            for campo in ("identificador", "nombre")
            if not _texto(comercio.get(campo))
        ]
        return problemas
    datos = [comercio.get(campo) for campo in ("identificador", "nombre")]
    if not any(_texto(dato) for dato in datos):
        problemas.append(Problema("comercio", COMERCIO_SIN_DATOS))
    problemas += [
        Problema(f"comercio.{campo}", DEBE_SER_TEXTO)
        for campo, dato in zip(("identificador", "nombre"), datos, strict=True)
        if dato is not None and not isinstance(dato, str)
    ]
    return problemas


def _hallazgos(hallazgos: Any) -> list[Problema]:
    if not isinstance(hallazgos, Mapping):
        return [Problema("hallazgos", DEBE_SER_OBJETO)]
    problemas = []
    if any(frente not in FRENTES_INFORME for frente in hallazgos):
        problemas.append(Problema("hallazgos", FRENTE_DESCONOCIDO))
    for frente in FRENTES_INFORME:
        if frente not in hallazgos:
            continue
        afirmaciones = hallazgos[frente]
        if not isinstance(afirmaciones, list):
            problemas.append(Problema(f"hallazgos.{frente}", DEBE_SER_LISTA))
            continue
        for posicion, afirmacion in enumerate(afirmaciones):
            ruta = f"hallazgos.{frente}[{posicion}]"
            if not isinstance(afirmacion, Mapping):
                problemas.append(Problema(ruta, DEBE_SER_OBJETO))
                continue
            problemas += _citas(afirmacion, ruta, _CAMPOS_AFIRMACION)
    return problemas


def _conflictos(conflictos: Any) -> list[Problema]:
    if not isinstance(conflictos, Mapping):
        return [Problema("conflictos", DEBE_SER_OBJETO)]
    problemas = _desconocidos(conflictos, "conflictos", ("resumen", "lista"))
    if not _texto(conflictos.get("resumen")):
        problemas.append(Problema("conflictos.resumen", DEBE_SER_TEXTO))
    lista = conflictos.get("lista")
    if not isinstance(lista, list):
        return [*problemas, Problema("conflictos.lista", DEBE_SER_LISTA)]
    for posicion, conflicto in enumerate(lista):
        ruta = f"conflictos.lista[{posicion}]"
        if not isinstance(conflicto, Mapping):
            problemas.append(Problema(ruta, DEBE_SER_OBJETO))
            continue
        problemas += _desconocidos(conflicto, ruta, ("dato", "valores"))
        if not _texto(conflicto.get("dato")):
            problemas.append(Problema(f"{ruta}.dato", DEBE_SER_TEXTO))
        valores = conflicto.get("valores")
        if not isinstance(valores, list) or len(valores) < 2:
            problemas.append(Problema(f"{ruta}.valores", DOS_VALORES))
            continue
        for indice, valor in enumerate(valores):
            ruta_valor = f"{ruta}.valores[{indice}]"
            if not isinstance(valor, Mapping):
                problemas.append(Problema(ruta_valor, DEBE_SER_OBJETO))
                continue
            problemas += _citas(valor, ruta_valor, _CAMPOS_VALOR)
    return problemas


def _textos(valor: Any, ruta: str) -> list[Problema]:
    """Un texto no vacío o una lista no vacía de textos no vacíos (cobertura y causa)."""
    if _texto(valor):
        return []
    if isinstance(valor, list) and valor and all(_texto(linea) for linea in valor):
        return []
    return [Problema(ruta, COBERTURA_MAL)]


def _cobertura(cobertura: Any) -> list[Problema]:
    return _textos(cobertura, "cobertura")


def _faltan(entrada: Mapping[str, Any], partes: tuple[str, ...]) -> list[Problema]:
    """Las partes ausentes, en su orden. `hallazgos: {}` vale: un frente no cubierto va vacío."""
    return [
        Problema(parte, FALTA)
        for parte in partes
        if not _presente(entrada, parte)
        and not (parte == "hallazgos" and isinstance(entrada.get(parte), Mapping))
    ]


def validar_informe(entrada: Any) -> list[Problema]:
    """Todos los problemas de forma del informe; `[]` si es válido. No modifica la entrada."""
    if not isinstance(entrada, Mapping):
        return [Problema("", "La entrada debe ser un objeto.")]
    # `hallazgos: {}` vale: un informe sin afirmaciones se entrega igual si no se cubrió nada
    # (I.5). Ausente sigue siendo «falta». Qué frentes quedaron cubiertos depende del caso: que
    # cada uno lleve su afirmación (US1-6) lo comprueba el hook, no la pasarela.
    faltan = _faltan(entrada, PARTES_INFORME)
    if faltan:
        return faltan
    problemas = _comercio(entrada["comercio"])
    if not _texto(entrada["recomendacion"]):
        problemas.append(Problema("recomendacion", DEBE_SER_TEXTO))
    problemas += _hallazgos(entrada["hallazgos"])
    problemas += _cobertura(entrada["cobertura"])
    problemas += _conflictos(entrada["conflictos"])
    return problemas


def validar_resumen(entrada: Any) -> list[Problema]:
    """Todos los problemas de forma del resumen al oficial; `[]` si es válido (#10, R6).

    Es el **único** validador del resumen: lo usan la pasarela (`decisiones`), el hook del
    coordinador y la `PasarelaSimulada`. Comparte con `validar_informe` los validadores de
    comercio, afirmaciones, cobertura y conflictos. Valida la forma, no si corresponde escalar.
    """
    if not isinstance(entrada, Mapping):
        return [Problema("", "La entrada debe ser un objeto.")]
    faltan = _faltan(entrada, PARTES_RESUMEN)
    if faltan:
        return faltan
    problemas = _comercio(entrada["comercio"])
    problemas += _hallazgos(entrada["hallazgos"])
    problemas += _cobertura(entrada["cobertura"])
    problemas += _textos(entrada["causa_escalamiento"], "causa_escalamiento")
    if not _texto(entrada["accion_recomendada"]):
        problemas.append(Problema("accion_recomendada", DEBE_SER_TEXTO))
    problemas += _conflictos(entrada["conflictos"])
    return problemas


def _frase(sujeto: str, problemas: list[Problema]) -> str:
    partes = "; ".join(
        f"{p.ruta or 'entrada'}: {p.texto[0].lower()}{p.texto[1:].rstrip('.')}" for p in problemas
    )
    return f"{sujeto} no tiene la forma esperada ({len(problemas)} problemas): {partes}."


def mensaje(problemas: list[Problema]) -> str:
    """Una frase en español que nombra cada ruta con su problema, para el campo `mensaje`."""
    return _frase("El informe", problemas)


def mensaje_resumen(problemas: list[Problema]) -> str:
    """La frase de `mensaje` para el resumen al oficial (#10, R6)."""
    return _frase("El resumen al oficial", problemas)


# Esquema JSON que se publica en `tools/list` para cada parte (R2). Es documentación para el
# modelo: la validación es `validar_informe`, no este esquema.
_AFIRMACION = {
    "type": "object",
    "properties": {
        "texto": {"type": "string"},
        "fuente": {"type": "string"},
        "fecha": {"type": "string", "description": "AAAA-MM-DD"},
    },
}
ESQUEMA_COMERCIO = {
    "type": "object",
    "properties": {
        "identificador": {"type": ["string", "null"]},
        "nombre": {"type": ["string", "null"]},
        "verificado": {"type": "boolean"},
    },
}
ESQUEMA_HALLAZGOS = {
    "type": "object",
    "properties": {frente: {"type": "array", "items": _AFIRMACION} for frente in FRENTES_INFORME},
}
ESQUEMA_CONFLICTOS = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string"},
        "lista": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dato": {"type": "string"},
                    "valores": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "valor": {},
                                "fuente": {"type": "string"},
                                "fecha": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}
