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
    CAUSA_FALLO_DE_HOOK,
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


def consulta_del_comercio(argumentos: Any, comercio: Any) -> bool:
    """Si una consulta de noticias es del comercio identificado (#10, FR-027, R7).

    Trae al menos su `identificador` o su `nombre`, y **cada uno que trae** coincide con el del
    comercio: `igual_identificador` para el identificador e `igual` para el nombre completo, la
    normalización del servidor. Una entrada malformada no es del comercio y no lanza.
    """
    if not isinstance(argumentos, Mapping) or not isinstance(comercio, Mapping):
        return False
    claves = {
        clave: valor
        for clave in ("identificador", "nombre")
        if (valor := argumentos.get(clave)) not in (None, "")
    }
    if not claves:
        return False
    for clave, valor in claves.items():
        buscado, existente = _texto(valor), _texto(comercio.get(clave))
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

    Se apoya en `estado.clase_identificacion` (#10, R3) para distinguir la causa (varias
    coincidencias, ninguna), no en subcadenas del motivo del registro, y devuelve siempre un texto
    propio, sin los identificadores que traiga ese motivo.
    """
    clase = estado.clase_identificacion
    if clase == "varias":
        return MOTIVO_VARIAS_COINCIDENCIAS
    if clase == "ninguna":
        return MOTIVO_SIN_COINCIDENCIAS
    return MOTIVO_SIN_COMERCIO


# ------------------------------------------------------------ esperas del analista (#10, R3)

MOTIVO_ESPERA_IDENTIFICADOR = (
    "El registro devolvió varias coincidencias: el caso espera el identificador del analista."
)
MOTIVO_ESPERA_NOMBRE = (
    "El registro no encontró el comercio: el caso espera que el analista revise el nombre."
)
MOTIVO_ESPERA_CATEGORIA = (
    "La categoría no aparece en los mensajes del analista: el caso espera la categoría."
)


class Espera(NamedTuple):
    """Un fin de turno que espera un dato del analista (#10, R3, data-model).

    `clase` es `identificador`, `nombre` o `categoria`; `motivo`, un texto fijo sin datos del caso.
    """

    clase: str
    motivo: str


MOTIVO_INFORME_ESPERA_IDENTIFICADOR = (
    "El registro devolvió varias coincidencias: pida el identificador al analista antes de "
    "registrar el informe."
)
MOTIVO_INFORME_ESPERA_NOMBRE = (
    "El registro no encontró el comercio: pida al analista que revise el nombre antes de "
    "registrar el informe."
)
# Regla de los rechazos por una espera del analista: el principio V (pedir el identificador en vez
# de elegir), que no es ninguna de las reglas I.1 a I.5.
REGLA_ESPERA = "V"


def espera_del_analista(estado: EstadoCaso) -> Espera | None:
    """La espera del analista que el código comprueba en el estado, o `None` (FR-014, R3).

    - `identificador`: el registro terminó con varias coincidencias.
    - `nombre`: el registro terminó sin ninguna coincidencia.
    - `categoria`: la última delegación de categoría la bloqueó FR-020 y el caso no tiene ningún
      resultado de categoría. Vale con cualquier estado del registro, también el caído.

    Las del registro prevalecen. Ninguna otra situación es una espera: ni el registro caído, que
    por sí solo exige reintentar o informar, ni las fuentes que difieren en el nombre o el
    representante (D3 del #9, `contradictoria`). Es pura: no escribe nada.
    """
    clase = estado.clase_identificacion
    if clase == "varias":
        return Espera("identificador", MOTIVO_ESPERA_IDENTIFICADOR)
    if clase == "ninguna":
        return Espera("nombre", MOTIVO_ESPERA_NOMBRE)
    if estado.categoria_bloqueada and not estado.libro.consultas_riesgo:
        return Espera("categoria", MOTIVO_ESPERA_CATEGORIA)
    return None


def motivo_del_informe_en_espera(estado: EstadoCaso) -> "Rechazo | None":
    """El rechazo del informe durante la espera del identificador o del nombre (FR-016, R3).

    `None` sin espera o con la espera de la categoría, en la que el informe sigue las reglas de
    siempre. Cambio respecto al #9, que aceptaba el informe con el comercio pedido ante varias
    coincidencias.
    """
    espera = espera_del_analista(estado)
    if espera is None or espera.clase == "categoria":
        return None
    if espera.clase == "identificador":
        return Rechazo(MOTIVO_INFORME_ESPERA_IDENTIFICADOR, REGLA_ESPERA)
    return Rechazo(MOTIVO_INFORME_ESPERA_NOMBRE, REGLA_ESPERA)


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


# ------------------------------------------------- categoría del analista (#10, FR-020, R9)

MOTIVO_CATEGORIA_NO_DEL_ANALISTA = (
    "La categoría no aparece en los mensajes del analista: use la que dio o pregúntesela."
)


def categoria_en_mensajes(categoria: Any, mensajes: Iterable[str]) -> bool:
    """Si la categoría aparece, como frase completa, en algún mensaje del analista (R9).

    Compara con `normalizar` de la pasarela (mayúsculas, tildes, espacios y puntuación no importan)
    y con límites de palabra: «ropa» no aparece en «tropa». No cubre plurales («suplemento
    dietario» no es «suplementos dietarios»): es un riesgo declarado (US5-5). Una categoría vacía
    o que no es texto no aparece.
    """
    if not isinstance(categoria, str) or not normalizar(categoria):
        return False
    buscada = f" {normalizar(categoria)} "
    return any(buscada in f" {normalizar(mensaje)} " for mensaje in mensajes)


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
    CAUSA_FALLO_DE_HOOK: "fallo de un hook de verificación",
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
    """Las causas de escalamiento del caso: claves fijas, sin nombres ni identificadores (R9).

    Desde el #9 (R9) incluye el sello `fallo_de_hook`: un caso sellado tiene que llegar al oficial,
    también sin coincidencias ni alto riesgo (cambio respecto al #7). No es una regla I.2 ni I.3.
    """
    causas = {coincidencia.causa for coincidencia in libro.coincidencias}
    if es_alto_riesgo(libro):
        causas.add(CAUSA_ALTO_RIESGO)
    if libro.fallo_de_hook:
        causas.add(CAUSA_FALLO_DE_HOOK)
    return frozenset(causas)


def requiere_escalamiento(libro: LibroReglas) -> bool:
    return bool(causas_vigentes(libro))


def escalamiento_cubre(libro: LibroReglas) -> bool:
    """Si algún escalamiento exitoso cubría todas las causas vigentes (vacío ⇒ `True`).

    Una causa posterior a la instantánea de un escalamiento queda sin cubrir y exige escalar de
    nuevo; una segunda coincidencia de la misma entidad no es una causa nueva (R9).
    """
    causas = causas_vigentes(libro)
    return not causas or any(causas <= e.causas for e in libro.escalamientos)


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


MOTIVO_SOLO_OFICIAL = (
    "Tras un fallo de hook solo decide el oficial: la recomendación debe ser decide_cumplimiento."
)


def evaluar_informe_minimo(estado: EstadoCaso, entrada: Any) -> list[Rechazo]:
    """Los motivos por los que se rechaza el informe con el caso sellado (#9, FR-014, R9).

    Solo `decide_cumplimiento` y solo después de un escalamiento que cubra las causas vigentes,
    entre ellas el sello. Las reglas de `habilitar` no hacen falta: con el sello no se admite.
    """
    if not isinstance(entrada, Mapping):
        return [Rechazo(MOTIVO_ENTRADA_INFORME, None)]
    rechazos: list[Rechazo] = []
    if normalizar_recomendacion(entrada.get("recomendacion")) != "decide_cumplimiento":
        rechazos.append(Rechazo(MOTIVO_SOLO_OFICIAL, None))
    libro = estado.libro
    if not escalamiento_cubre(libro):
        causas = causas_vigentes(libro)
        rechazos.append(Rechazo(motivo_de_escalar(causas), reglas_de(causas)))
    return rechazos


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


# ------------------------------------------- causa del resumen al oficial (#10, FR-009, R5)

# Sin causas vigentes (FR-003), una línea por cada motivo que se cumpla, en este orden.
MOTIVOS_SIN_CAUSA = {
    "cobertura_incompleta": "Sin causa de escalamiento vigente: la cobertura está incompleta.",
    "categoria_no_determinada": (
        "Sin causa de escalamiento vigente: la categoría no quedó determinada."
    ),
    "mencion_en_noticias": "Sin causa de escalamiento vigente: hay menciones en noticias.",
    "conflicto_entre_fuentes": (
        "Sin causa de escalamiento vigente: hay conflictos entre las fuentes registrales."
    ),
    # Precisión de la implementación (T035): sin él, un caso sin comercio identificado y sin los
    # otros cuatro motivos daría una causa vacía.
    "comercio_no_identificado": (
        "Sin causa de escalamiento vigente: el comercio no está identificado de forma unívoca."
    ),
}
MOTIVO_SIN_COMERCIO_ESCALAMIENTO = (
    "Delegue primero el registro mercantil: el oficial necesita saber de qué comercio se trata."
)


def menciones_en_noticias(estado: EstadoCaso) -> bool:
    """Si el último resultado de noticias trae menciones (FR-002, R5).

    Con el comercio identificado solo cuentan sus consultas (FR-027, R7): una mención encontrada
    con el nombre ambiguo no es de este comercio.
    """
    resultado = estado.resultados.get(Frente.NOTICIAS)
    if resultado is None:
        return False
    comercio = estado.comercio
    return any(
        c.valido
        and isinstance(c.resultado, Mapping)
        and c.resultado.get("resultado") == "coincidencias"
        and (comercio is None or consulta_del_comercio(c.argumentos, comercio))
        for c in resultado.consultas
    )


def causas_del_resumen(estado: EstadoCaso) -> list[str]:
    """Las líneas de la causa que pone el código en el resumen al oficial (FR-009, R5).

    Con causas vigentes, una por causa con su etiqueta fija. Sin causas (FR-003), una por cada
    motivo de `MOTIVOS_SIN_CAUSA` que se cumpla. Ninguna repite datos del comercio.
    """
    # Importación diferida: `cobertura.py` y `conflictos.py` importan este módulo.
    from due_diligence.cobertura import calcular_cobertura
    from due_diligence.conflictos import calcular_conflictos

    causas = causas_vigentes(estado.libro)
    if causas:
        return [texto for clave, texto in ETIQUETAS_CAUSA.items() if clave in causas]
    motivos = {
        "cobertura_incompleta": not calcular_cobertura(estado).completa,
        "categoria_no_determinada": not categoria_determinada(estado.libro),
        "mencion_en_noticias": menciones_en_noticias(estado),
        "conflicto_entre_fuentes": calcular_conflictos(estado).estado == "con_conflictos",
        "comercio_no_identificado": estado.comercio is None,
    }
    return [MOTIVOS_SIN_CAUSA[clave] for clave, cumple in motivos.items() if cumple]


# Motivos del cierre por el informe (#9, contrato `cierre.md`): textos fijos, sin datos del caso.
MOTIVO_SIN_INFORME = (
    "Falta registrar el informe del caso con registrar_informe (habilitar, no_habilitar o "
    "decide_cumplimiento)."
)
MOTIVO_REGISTRO_REINTENTABLE = (
    "El registro mercantil no respondió: reintenta el registro o registra el informe."
)
MOTIVO_INFORME_NO_VIGENTE = (
    "El informe registrado ya no está vigente: cambió {cambios} después de registrarlo. Registra "
    "uno nuevo."
)
SUFIJO_LUEGO_INFORME = " Luego registra el informe."


def falta_para_cerrar(estado: EstadoCaso) -> tuple[bool, bool]:
    """(falta escalar, falta el informe vigente) para que el caso pueda terminar (#9, R8).

    El informe solo se exige si `requiere_informe` (comercio identificado o registro caído).
    """
    # Importación diferida: `informe.py` importa este módulo (`causas_vigentes`).
    from due_diligence import informe

    falta_escalar = not escalamiento_cubre(estado.libro)
    falta_informe = informe.requiere_informe(estado) and not informe.informe_vigente(estado)
    return falta_escalar, falta_informe


def _motivo_del_informe(estado: EstadoCaso) -> str:
    from due_diligence import informe

    if estado.informes:
        cambios = informe.cambios(estado.informes[-1].huella, informe.huella_actual(estado))
        if cambios:
            enumerados = (
                cambios[0] if len(cambios) == 1 else f"{', '.join(cambios[:-1])} y {cambios[-1]}"
            )
            return MOTIVO_INFORME_NO_VIGENTE.format(cambios=enumerados)
    if informe.registro_caido(estado) and informe.registro_reintentable(estado):
        return MOTIVO_REGISTRO_REINTENTABLE
    return MOTIVO_SIN_INFORME


def evaluar_cierre(estado: EstadoCaso) -> str | None:
    """El motivo por el que el caso no puede terminar, o `None` si puede (#7 FR-007; #9 R8).

    No puede terminar un caso que requiere escalamiento sin que `escalar_a_cumplimiento` haya
    cubierto sus causas vigentes (#7), ni un caso que requiere informe sin un informe vigente (#9).
    Si faltan los dos, primero el escalamiento: el informe se rechazaría hasta escalar (FR-012).
    Los motivos usan solo textos y etiquetas fijas.
    """
    falta_escalar, falta_informe = falta_para_cerrar(estado)
    if falta_escalar:
        motivo = motivo_de_escalar(causas_vigentes(estado.libro))
        return motivo + SUFIJO_LUEGO_INFORME if falta_informe else motivo
    if falta_informe:
        return _motivo_del_informe(estado)
    return None
