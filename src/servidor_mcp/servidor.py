"""Servidor MCP `pasarela`: las fuentes de la pasarela y sus dos canales de decisión.

Seis herramientas que simulan, con datos ficticios locales, el registro mercantil, las listas
restrictivas, las noticias y el riesgo por categoría, más `registrar_informe` y
`escalar_a_cumplimiento`, que son los únicos canales de decisión (constitución IV).

- Todos los parámetros son opcionales (`Any = None`) y se validan dentro de cada función: el SDK
  rechaza, en inglés y sin estructura, un argumento ausente o de tipo incorrecto antes de entrar
  a la herramienta (R2). El tipo esperado va en la descripción de cada parámetro.
- Las funciones se llaman **por módulo** (`registro.consultar_registro_mercantil(...)`), no con
  `from .registro import ...`, para que un `monkeypatch` actúe sobre la llamada real.
- Una excepción inesperada se convierte en `error_interno`, no reintentable, sin su texto.
- Este módulo no imprime nada: stdout es el canal del protocolo.
"""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult
from pydantic import Field

from servidor_mcp import datos, decisiones, informe, listas, noticias, registro, riesgo
from servidor_mcp.respuestas import error

_registro = logging.getLogger(__name__)

servidor = MCPServer("pasarela")


def _protegido(llamada: Callable[[], CallToolResult]) -> CallToolResult:
    """Ejecuta la herramienta; lo inesperado es `error_interno`, nunca una excepción."""
    try:
        return llamada()
    except Exception:
        _registro.exception("Fallo inesperado en una herramienta de la pasarela")
        return error(
            "error_interno",
            "Ocurrió un error interno en el servidor de la pasarela. No se pudo completar la "
            "operación; no es reintentable sin revisar el servidor.",
            False,
        )


def _categorias_para_la_descripcion() -> str:
    try:
        return ", ".join(riesgo.categorias_conocidas())
    except datos.DatosNoDisponibles:
        return "(el catálogo no está disponible)"


def _p(descripcion: str, tipo: str | list[str] = "string") -> Any:
    """Descripción y tipo JSON de un parámetro.

    Los parámetros se declaran `Any` para que el SDK no rechace un tipo incorrecto en inglés
    (R2); `json_schema_extra` publica en `tools/list` el tipo que sí se espera, y la validación
    sigue siendo la propia de cada herramienta."""
    return Field(description=descripcion, json_schema_extra={"type": tipo})


# --- consultar_registro_mercantil -------------------------------------------------------------


@servidor.tool(
    name="consultar_registro_mercantil",
    description=(
        "Busca un comercio en el registro mercantil por nombre o por identificador. Devuelve, por "
        "cada fuente registral, la existencia, la fecha de constitución, el representante legal y "
        "el estado. Si el nombre coincide con varios comercios devuelve TODOS: no elige uno ni "
        "indica cuál es el correcto; la decisión es de quien consulta, con el identificador. Si "
        "dos fuentes registrales difieren, devuelve ambos valores con su fuente. Ignora la forma "
        "jurídica final del nombre (SAS, SA, Ltda, EU, SCA, S. en C.). Si no hay coincidencias lo "
        "declara de forma explícita, con su fuente y fecha. No consulta listas restrictivas ni "
        "noticias, y no devuelve la categoría de negocio."
    ),
)
def consultar_registro_mercantil(
    nombre: Annotated[
        Any,
        _p(
            "Texto. Nombre del comercio, completo o parcial; se ignoran mayúsculas, tildes, "
            "puntuación y la forma jurídica final. Mínimo 3 caracteres. Indique nombre o "
            "identificador, no ambos."
        ),
    ] = None,
    identificador: Annotated[
        Any,
        _p(
            "Texto. Identificador del comercio, por ejemplo CO-TV-0001; no distingue mayúsculas. "
            "Indique identificador o nombre, no ambos."
        ),
    ] = None,
) -> CallToolResult:
    return _protegido(
        lambda: registro.consultar_registro_mercantil(nombre=nombre, identificador=identificador)
    )


# --- consultar_listas_restrictivas ------------------------------------------------------------


@servidor.tool(
    name="consultar_listas_restrictivas",
    description=(
        "Verifica un comercio o una persona (por ejemplo, el representante legal) contra las "
        "listas restrictivas. Hay coincidencia solo por nombre completo idéntico (sin distinguir "
        "mayúsculas ni tildes) o por identificador, nunca parcial. Una mención en noticias NO es "
        "una coincidencia en listas restrictivas: eso lo responde buscar_noticias. Si no hay "
        "coincidencias lo declara de forma explícita, con la fuente y la fecha de todas las "
        "listas consultadas. Debe llamarse con el identificador de un comercio ya identificado de "
        "forma unívoca en el registro mercantil."
    ),
)
def consultar_listas_restrictivas(
    tipo: Annotated[Any, _p("Texto. «comercio» o «persona».")] = None,
    nombre: Annotated[
        Any,
        _p(
            "Texto. Nombre completo del comercio o de la persona; no coincide de forma parcial. "
            "Indique nombre o identificador, no ambos."
        ),
    ] = None,
    identificador: Annotated[
        Any,
        _p(
            "Texto. Identificador, por ejemplo CO-TV-0001 o PE-0003; no distingue mayúsculas. "
            "Indique identificador o nombre, no ambos."
        ),
    ] = None,
) -> CallToolResult:
    return _protegido(
        lambda: listas.consultar_listas_restrictivas(
            tipo=tipo, nombre=nombre, identificador=identificador
        )
    )


# --- buscar_noticias --------------------------------------------------------------------------


@servidor.tool(
    name="buscar_noticias",
    description=(
        "Busca menciones de un comercio o una persona en un corpus de noticias. Una mención NO es "
        "una coincidencia en listas restrictivas y no impide ni autoriza nada por sí sola. Si no "
        "hay menciones lo declara de forma explícita, con su fuente y fecha. Si el servicio no "
        "responde devuelve un error reintentable: entonces el frente de noticias queda sin cubrir "
        "y no debe presentarse como completo."
    ),
)
def buscar_noticias(
    nombre: Annotated[
        Any,
        _p(
            "Texto. Nombre completo del comercio o de la persona; no coincide de forma parcial. "
            "Indique nombre o identificador, no ambos."
        ),
    ] = None,
    identificador: Annotated[
        Any,
        _p(
            "Texto. Identificador, por ejemplo CO-AM-0005; no distingue mayúsculas. Indique "
            "identificador o nombre, no ambos."
        ),
    ] = None,
) -> CallToolResult:
    return _protegido(lambda: noticias.buscar_noticias(nombre=nombre, identificador=identificador))


# --- consultar_riesgo_categoria ---------------------------------------------------------------


@servidor.tool(
    name="consultar_riesgo_categoria",
    description=(
        "Devuelve el nivel de riesgo (alto, medio o bajo) de una categoría de negocio, que aporta "
        "quien consulta; el registro mercantil no la devuelve. Categorías conocidas: "
        f"{_categorias_para_la_descripcion()}. El nivel es alto exactamente para apuestas, "
        "criptoactivos, suplementos dietarios y venta de medicamentos. Para una categoría "
        "desconocida no inventa un nivel: lo declara. No decide la habilitación ni escala el caso."
    ),
)
def consultar_riesgo_categoria(
    categoria: Annotated[
        Any,
        _p(
            "Texto. Categoría de negocio tal como la nombró el analista, por ejemplo «apuestas»; "
            "se ignoran mayúsculas, tildes y puntuación."
        ),
    ] = None,
) -> CallToolResult:
    return _protegido(lambda: riesgo.consultar_riesgo_categoria(categoria=categoria))


# --- registrar_informe y escalar_a_cumplimiento ----------------------------------------------


def _esquema(descripcion: str, esquema: dict[str, Any]) -> Any:
    """Como `_p`, con el esquema JSON completo de un objeto (#9, R2): documentación para el
    modelo; la validación sigue siendo `informe.validar_informe`."""
    return Field(description=descripcion, json_schema_extra=esquema)


_COMERCIO = _p("Objeto. El comercio: «identificador» y «nombre», ambos texto.", "object")
_COMERCIO_INFORME = _esquema(
    "Objeto. El comercio: «identificador» y «nombre» (texto o null) y «verificado» (verdadero o "
    "falso). Lo pone el sistema con el comercio identificado en el registro mercantil.",
    informe.ESQUEMA_COMERCIO,
)
_AFIRMACIONES = _esquema(
    "Objeto. Las afirmaciones del informe por frente: la clave es el frente (registro, listas, "
    "noticias o categoria) y el valor, una lista de objetos con «texto», «fuente» y «fecha» "
    "(AAAA-MM-DD), los tres obligatorios. Ninguna afirmación sin su fuente y su fecha.",
    informe.ESQUEMA_HALLAZGOS,
)
_CONFLICTOS = _esquema(
    "Objeto. Los datos en que las fuentes registrales se contradicen: «resumen» (texto) y "
    "«lista», con cada dato y sus valores, uno por fuente con su «fuente» y su «fecha». Lo pone "
    "el sistema; ningún valor prevalece sobre otro.",
    informe.ESQUEMA_CONFLICTOS,
)
_HALLAZGOS = _p(
    "Objeto. Un hallazgo por frente: la clave es el frente (por ejemplo «registro») y el valor es "
    "un objeto con «contenido» y «fuente», ambos texto. Ningún hallazgo sin fuente.",
    "object",
)
_COBERTURA = _p(
    "Texto o lista. Frentes cubiertos y frentes que quedaron sin cubrir.", ["string", "array"]
)


@servidor.tool(
    name="registrar_informe",
    description=(
        "Registra el informe de due diligence con su recomendación, las afirmaciones de cada "
        "frente con su fuente y su fecha, los conflictos entre fuentes y la cobertura alcanzada. "
        "Es uno de los dos canales de decisión. El comercio, los conflictos y la cobertura los "
        "pone el sistema a partir de lo consultado; las afirmaciones y la recomendación, quien "
        "registra. La recomendación es habilitar, no_habilitar o decide_cumplimiento (es una "
        "guía: el servidor no la valida). No valida reglas de negocio ni decide: guarda lo que "
        "recibe. Tampoco comprueba que cada fuente se haya consultado ni que cada frente cubierto "
        "lleve su afirmación (eso lo hace el sistema antes de llamarla) ni escala el caso: para "
        "eso está escalar_a_cumplimiento. Si falta un campo obligatorio o una afirmación no tiene "
        "la forma esperada, devuelve un error no reintentable que nombra cada problema."
    ),
)
def registrar_informe(
    comercio: Annotated[Any, _COMERCIO_INFORME] = None,
    recomendacion: Annotated[
        Any,
        _p("Texto. La recomendación del informe: habilitar, no_habilitar o decide_cumplimiento."),
    ] = None,
    hallazgos: Annotated[Any, _AFIRMACIONES] = None,
    conflictos: Annotated[Any, _CONFLICTOS] = None,
    cobertura: Annotated[Any, _COBERTURA] = None,
) -> CallToolResult:
    return _protegido(
        lambda: decisiones.registrar_informe(
            comercio=comercio,
            recomendacion=recomendacion,
            hallazgos=hallazgos,
            conflictos=conflictos,
            cobertura=cobertura,
        )
    )


@servidor.tool(
    name="escalar_a_cumplimiento",
    description=(
        "Pasa el caso a un oficial de cumplimiento con un resumen estructurado y autosuficiente: "
        "el oficial no tiene acceso a la conversación. Es uno de los dos canales de decisión. Se "
        "escala por coincidencia en listas restrictivas o por categoría de alto riesgo, nunca por "
        "una mención en noticias. No emite una recomendación de habilitación. Si falta un campo "
        "obligatorio devuelve un error no reintentable que lo nombra."
    ),
)
def escalar_a_cumplimiento(
    comercio: Annotated[Any, _COMERCIO] = None,
    hallazgos: Annotated[Any, _HALLAZGOS] = None,
    cobertura: Annotated[Any, _COBERTURA] = None,
    causa_escalamiento: Annotated[
        Any, _p("Texto. Por qué se escala: coincidencia en listas o categoría de alto riesgo.")
    ] = None,
    accion_recomendada: Annotated[
        Any, _p("Texto. La acción que se recomienda al oficial de cumplimiento.")
    ] = None,
) -> CallToolResult:
    return _protegido(
        lambda: decisiones.escalar_a_cumplimiento(
            comercio=comercio,
            hallazgos=hallazgos,
            cobertura=cobertura,
            causa_escalamiento=causa_escalamiento,
            accion_recomendada=accion_recomendada,
        )
    )
