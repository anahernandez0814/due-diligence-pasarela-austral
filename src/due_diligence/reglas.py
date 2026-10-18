"""Reglas de negocio I.1, I.2 e I.3 como funciones puras (data-model, R7 a R10).

Reciben el estado del caso o el libro de reglas y devuelven una decisión: no tocan el SDK, el
modelo ni el estado de otros módulos. Los hooks (`hooks.py`) solo las adaptan al SDK. La lista de
categorías de alto riesgo y el conjunto cerrado de recomendaciones son constantes del código, no
texto de un prompt (FR-008, FR-019).
"""

from collections.abc import Iterable, Mapping
from typing import Any, NamedTuple

from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.frentes import Frente
from due_diligence.libro import (
    CAUSA_ALTO_RIESGO,
    CAUSA_COINCIDENCIA_COMERCIO,
    CAUSA_COINCIDENCIA_REPRESENTANTE,
    LibroReglas,
)
from servidor_mcp.normalizar import igual, igual_identificador, normalizar

# Categorías de alto riesgo (principio I.3). Se comparan normalizadas con `igual` (R8).
ALTO_RIESGO = (
    "apuestas",
    "criptoactivos",
    "suplementos dietarios",
    "venta de medicamentos",
)

# Conjunto cerrado de recomendaciones del informe (R10). Solo `habilitar` está sujeta a las reglas
# 1 a 3; cualquier otro valor se rechaza.
RECOMENDACION_HABILITAR = "habilitar"
RECOMENDACIONES = (RECOMENDACION_HABILITAR, "no_habilitar", "decide_cumplimiento")


def normalizar_recomendacion(texto: Any) -> str | None:
    """El valor de `RECOMENDACIONES` que corresponde al texto, o `None` si no es uno de los tres.

    Ignora mayúsculas, tildes y signos, y toma espacios y guiones como `_` (`No-Habilitar` →
    `no_habilitar`). Lo que no es texto, o es otra frase, es `None`.
    """
    if not isinstance(texto, str):
        return None
    candidato = normalizar(texto).replace(" ", "_")
    return candidato if candidato in RECOMENDACIONES else None


def _texto(valor: Any) -> str | None:
    """El texto sin espacios de los bordes, o `None` si no es texto o está vacío."""
    if isinstance(valor, str) and valor.strip():
        return valor
    return None


def consulta_coincide(consulta: Any, entidad: Any, tipo: str) -> bool:
    """Si una consulta de listas (`tipo`, `nombre`, `identificador`) es sobre esta entidad (R7).

    El tipo de la consulta debe ser el esperado (`comercio` para el comercio, `persona` para el
    representante legal). La consulta debe traer al menos una clave y **cada clave que trae debe
    existir en la entidad del registro y coincidir**: `igual_identificador` para el identificador e
    `igual` para el nombre completo, de `servidor_mcp.normalizar`, que es lo que usa el servidor.
    Una clave que la entidad no tiene (por ejemplo, un identificador para un representante que el
    registro devolvió sin identificador) no coincide: no se puede verificar que sea la misma
    persona. Una entrada malformada no coincide y no lanza.
    """
    if not isinstance(consulta, Mapping) or not isinstance(entidad, Mapping):
        return False
    tipo_consulta = consulta.get("tipo")
    if not isinstance(tipo_consulta, str) or tipo_consulta.strip().casefold() != tipo:
        return False
    claves = {
        clave: valor
        for clave in ("nombre", "identificador")
        if (valor := consulta.get(clave)) not in (None, "")
    }
    if not claves:
        return False
    for clave, valor in claves.items():
        buscado, existente = _texto(valor), _texto(entidad.get(clave))
        if buscado is None or existente is None:
            return False
        coincide = igual_identificador if clave == "identificador" else igual
        if not coincide(buscado, existente):
            return False
    return True


# --------------------------------------------------------------------------- regla I.1 (listas)

MOTIVO_SIN_COMERCIO = (
    "Aún no hay un comercio identificado de forma unívoca en el registro mercantil."
)
MOTIVO_VARIAS_COINCIDENCIAS = (
    "El registro devolvió varias coincidencias: pida el identificador al analista, no elija una."
)
MOTIVO_SIN_COINCIDENCIAS = "El registro no devolvió coincidencias para el comercio."
MOTIVO_REGISTRO_PRIMERO = (
    "Delegue primero el registro mercantil: listas necesita el resultado del registro."
)
MOTIVO_CONSULTA_AJENA = (
    "La consulta no corresponde al comercio identificado ni a su representante legal, con el "
    "tipo que corresponde (comercio o persona)."
)


def _motivo_sin_comercio(estado: EstadoCaso) -> str:
    """El motivo de que no haya un comercio único, con textos fijos: no repite nada consultado.

    Se apoya en `estado.motivo_comercio` solo para distinguir la causa (varias coincidencias,
    ninguna) y devuelve siempre un texto propio, sin los identificadores que traiga el del registro.
    """
    motivo = estado.motivo_comercio
    if "varias coincidencias" in motivo:
        return MOTIVO_VARIAS_COINCIDENCIAS
    if "ninguna coincidencia" in motivo:
        return MOTIVO_SIN_COINCIDENCIAS
    return MOTIVO_SIN_COMERCIO


def permite_listas(estado: EstadoCaso, entrada: Any) -> tuple[bool, str]:
    """(permitida, motivo) de una consulta de listas restrictivas (regla I.1, FR-002, R6, R7).

    Solo se permite por el comercio identificado de forma unívoca (tipo `comercio`) o por su
    representante legal (tipo `persona`); cualquier otra consulta, o una entrada malformada, se
    bloquea. Lee solo `estado.comercio`: no mira `estado.consultas` ni `estado.resultados`.
    """
    comercio = estado.comercio
    if comercio is None:
        return False, _motivo_sin_comercio(estado)
    if consulta_coincide(entrada, comercio, "comercio"):
        return True, ""
    representante = comercio.get("representante_legal")
    if representante and consulta_coincide(entrada, representante, "persona"):
        return True, ""
    return False, MOTIVO_CONSULTA_AJENA


def permite_delegar_listas(estado: EstadoCaso) -> tuple[bool, str]:
    """(permitida, motivo) de delegar el frente de listas (regla I.1, FR-018, R6).

    Se bloquea si el registro no se delegó, fue rechazado o no terminó, o si terminó sin un
    comercio único. Con el registro en curso se permite: la herramienta espera a que termine
    (R4 del #6) y, si termina sin coincidencia única, la propia delegación se rechaza.
    """
    situacion = estado.situacion(Frente.REGISTRO)
    if situacion is Situacion.EN_CURSO:
        return True, ""
    if situacion is Situacion.SIN_INICIAR:
        return False, MOTIVO_REGISTRO_PRIMERO
    if situacion in (Situacion.RECHAZADO, Situacion.NO_TERMINADO):
        return False, MOTIVO_SIN_COMERCIO
    if estado.comercio is None:
        return False, _motivo_sin_comercio(estado)
    return True, ""


# ------------------------------------------------------------------------ reglas I.2 e I.3 (cierre)


class Rechazo(NamedTuple):
    """El motivo de un rechazo del informe y la regla que lo causa (`None` si no es de las tres)."""

    texto: str
    regla: str | None


# Etiquetas fijas de cada causa: los motivos se construyen solo con ellas, sin nombres ni
# identificadores consultados (FR-013, FR-016). El orden es el de aparición en los motivos.
ETIQUETAS_CAUSA = {
    CAUSA_COINCIDENCIA_COMERCIO: "coincidencia del comercio en listas restrictivas",
    CAUSA_COINCIDENCIA_REPRESENTANTE: "coincidencia del representante legal en listas restrictivas",
    CAUSA_ALTO_RIESGO: "categoría de alto riesgo",
}

MOTIVO_RECOMENDACION = (
    "La recomendación debe ser exactamente habilitar, no_habilitar o decide_cumplimiento."
)
MOTIVO_ENTRADA_INFORME = "El informe no tiene la forma esperada; se bloquea por precaución."
MOTIVO_HABILITAR_ALTO_RIESGO = (
    "La categoría es de alto riesgo: la decisión es de un oficial de cumplimiento."
)
MOTIVO_CATEGORIA_NO_DETERMINADA = "La categoría del caso no quedó determinada."
MOTIVO_FALTA_LISTAS = (
    "Falta la consulta de listas restrictivas del comercio y de su representante legal."
)
MOTIVO_HABILITAR_CON_COINCIDENCIA = (
    "Hay una coincidencia en listas restrictivas: no se puede recomendar habilitar. "
    "Escale el caso a cumplimiento."
)


def es_alto_riesgo(libro: LibroReglas) -> bool:
    """Si el caso es de alto riesgo: alguna consulta de riesgo dio una categoría de la constante
    (comparada con `igual`) o el nivel «alto». Es persistente: otra categoría consultada después
    no lo baja (R8, FR-008)."""
    return any(
        consulta.nivel == "alto" or any(igual(consulta.categoria, c) for c in ALTO_RIESGO)
        for consulta in libro.consultas_riesgo
    )


def categoria_determinada(libro: LibroReglas) -> bool:
    """Si la categoría del caso quedó determinada (R8).

    Lo está si el caso es de alto riesgo o si la **última** consulta de riesgo registrada fue
    conocida (con nivel). Sin consultas, o con la última desconocida, no lo está.
    """
    if es_alto_riesgo(libro):
        return True
    return bool(libro.consultas_riesgo) and libro.consultas_riesgo[-1].nivel is not None


def causas_vigentes(libro: LibroReglas) -> frozenset[str]:
    """Las causas de escalamiento del caso: claves fijas, sin nombres ni identificadores (R9)."""
    causas = {coincidencia.causa for coincidencia in libro.coincidencias}
    if es_alto_riesgo(libro):
        causas.add(CAUSA_ALTO_RIESGO)
    return frozenset(causas)


def requiere_escalamiento(libro: LibroReglas) -> bool:
    return bool(causas_vigentes(libro))


def escalamiento_cubre(libro: LibroReglas) -> bool:
    """Si algún escalamiento exitoso cubría todas las causas vigentes (vacío ⇒ `True`).

    Una causa posterior a la instantánea de un escalamiento queda sin cubrir y exige escalar de
    nuevo; una segunda coincidencia de la misma entidad no es una causa nueva (R9).
    """
    causas = causas_vigentes(libro)
    return not causas or any(causas <= instantanea for instantanea in libro.escalamientos)


def reglas_de(causas: Iterable[str]) -> str | None:
    """Las reglas del evento según las causas: `I.2`, `I.3` o `I.2, I.3` (`None` sin causas)."""
    causas = set(causas)
    reglas = []
    if causas & {CAUSA_COINCIDENCIA_COMERCIO, CAUSA_COINCIDENCIA_REPRESENTANTE}:
        reglas.append("I.2")
    if CAUSA_ALTO_RIESGO in causas:
        reglas.append("I.3")
    return ", ".join(reglas) or None


def motivo_de_escalar(causas: Iterable[str]) -> str:
    """El motivo de que el caso requiera escalamiento, con las etiquetas fijas de sus causas."""
    causas = set(causas)
    etiquetas = ", ".join(texto for clave, texto in ETIQUETAS_CAUSA.items() if clave in causas)
    return f"El caso requiere escalamiento a cumplimiento y aún no se ha escalado por: {etiquetas}."


def _listas_consultadas(estado: EstadoCaso) -> bool:
    """Si hay una consulta válida de listas del comercio y, si el registro lo devolvió, de su
    representante. Se compara con el comercio **vigente**: las consultas de otro no cuentan (R7)."""
    comercio = estado.comercio
    if comercio is None:
        return False

    def hay(tipo: str, entidad: Mapping[str, Any]) -> bool:
        return any(
            consulta_coincide(
                {"tipo": c.tipo, "nombre": c.nombre, "identificador": c.identificador},
                entidad,
                tipo,
            )
            for c in estado.libro.consultas_listas
        )

    representante = comercio.get("representante_legal")
    return hay("comercio", comercio) and (not representante or hay("persona", representante))


def evaluar_informe(estado: EstadoCaso, entrada: Any) -> list[Rechazo]:
    """Los motivos por los que se rechaza `registrar_informe`; vacía si se acepta (FR-005, FR-006).

    Acumula todos los que apliquen: una recomendación fuera del conjunto cerrado, un caso que
    requiere escalamiento sin cubrir (para cualquier recomendación) y, solo si se recomienda
    habilitar, cada condición de las reglas I.2 e I.3. Una entrada malformada se rechaza.
    """
    if not isinstance(entrada, Mapping):
        return [Rechazo(MOTIVO_ENTRADA_INFORME, None)]
    libro = estado.libro
    rechazos: list[Rechazo] = []
    recomendacion = normalizar_recomendacion(entrada.get("recomendacion"))
    if recomendacion is None:
        rechazos.append(Rechazo(MOTIVO_RECOMENDACION, None))
    causas = causas_vigentes(libro)
    if not escalamiento_cubre(libro):
        rechazos.append(Rechazo(motivo_de_escalar(causas), reglas_de(causas)))
    if recomendacion == RECOMENDACION_HABILITAR:
        if libro.coincidencias:
            rechazos.append(Rechazo(MOTIVO_HABILITAR_CON_COINCIDENCIA, "I.2"))
        if es_alto_riesgo(libro):
            rechazos.append(Rechazo(MOTIVO_HABILITAR_ALTO_RIESGO, "I.3"))
        elif not categoria_determinada(libro):
            rechazos.append(Rechazo(MOTIVO_CATEGORIA_NO_DETERMINADA, "I.3"))
        if not _listas_consultadas(estado):
            rechazos.append(Rechazo(MOTIVO_FALTA_LISTAS, "I.2"))
    return rechazos
