"""Sondeo de los hooks del Agent SDK con el modelo real (#7, Q4, R1 a R3, G2).

Repite lo que `research.md` midió con el SDK 0.2.168 y comprueba que los hooks del caso
(`HooksDelCaso`) funcionan en una sesión real:

    uv run python -m due_diligence.sondeo_hooks

Usa Haiku (unos 0,01 USD) aunque el producto use Opus 5.5: el sondeo mide el SDK (qué recibe cada
hook y qué hace con su salida), no el modelo, y basta con que el modelo haga la llamada pedida. Usa
las credenciales de la sesión de Claude Code: no hay clave en el repositorio ni se leen archivos de
entorno.

La salida de error de la CLI no se imprime: al medir el hook que falla a propósito, la CLI vuelca su
código JavaScript y ensucia el informe. Se recoge en memoria (sin el aviso de conectores, como hace
`configuracion.filtrar_stderr`) y solo se muestra si alguna medición no coincide, para
diagnosticar.

Cada experimento compara lo esperado con lo medido: `coincide`, `difiere` (el SDK cambió: la
versión está acotada a `<0.3`) o `inconcluso` (el modelo no hizo la llamada que se le pidió; no es
un fallo del hook). Código de salida: 0 si todo coincide, 1 si algo difiere y 2 si solo hay
mediciones inconclusas.

Es una herramienta manual: no la importa el paquete ni la ejecuta la suite de pruebas.
"""

import asyncio
import dataclasses
import json
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    HookMatcher,
    ResultMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    query,
    tool,
)
from claude_agent_sdk._errors import ResultError

from due_diligence import configuracion
from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.eventos import TIPO_BLOQUEO_REGLA, RegistroEventos
from due_diligence.frentes import FRENTES, Frente
from due_diligence.hooks import HooksDelCaso, bloquear_cierre, denegar, permitir

MODELO = "claude-haiku-5-5"
NO_CONCLUYENTE = "no concluyente"
INSTRUCCION = "Eres un agente de prueba. Haz exactamente lo que se te pide, sin más."

REGISTRO = FRENTES[Frente.REGISTRO].herramienta_completa
LISTAS = FRENTES[Frente.LISTAS].herramienta_completa
NOTICIAS = FRENTES[Frente.NOTICIAS].herramienta_completa
DELEGAR = "mcp__delegacion__delegar_frente"

# ------------------------------------------------------------------ salida de error de la CLI

STDERR_DE_LA_CLI: list[str] = []


def recoger_stderr(linea: str) -> None:
    """Callback `stderr` del SDK para el sondeo: guarda la línea en vez de imprimirla.

    Descarta el aviso de conectores, igual que `configuracion.filtrar_stderr`.
    """
    if configuracion.AVISO_CONECTORES in linea.lower():
        return
    STDERR_DE_LA_CLI.append(linea)


# ------------------------------------------------------------------ mediciones


@dataclass(frozen=True)
class Medicion:
    clave: str
    descripcion: str
    esperado: Any
    medido: Any = NO_CONCLUYENTE


def veredicto(medicion: Medicion) -> str:
    """`coincide`, `difiere` o `inconcluso` (el modelo no hizo la llamada pedida)."""
    if medicion.medido == NO_CONCLUYENTE:
        return "inconcluso"
    return "coincide" if medicion.medido == medicion.esperado else "difiere"


def informe(mediciones: list[Medicion]) -> str:
    """Una línea por medición y, si no coincide, lo esperado frente a lo medido."""
    lineas = []
    for medicion in mediciones:
        resultado = veredicto(medicion)
        lineas.append(f"{resultado:<10} {medicion.clave}: {medicion.descripcion}")
        if resultado != "coincide":
            lineas.append(f"{'':<10} esperado: {medicion.esperado!r} | medido: {medicion.medido!r}")
    conteo = {
        v: sum(veredicto(m) == v for m in mediciones) for v in ("coincide", "difiere", "inconcluso")
    }
    lineas.append("")
    lineas.append(
        f"Resumen: {conteo['coincide']} coinciden, {conteo['difiere']} difieren, "
        f"{conteo['inconcluso']} inconclusas."
    )
    return "\n".join(lineas)


# ------------------------------------------------------------------ una sesión real


@dataclass
class Traza:
    """Lo que pasó en una sesión: las llamadas a herramientas, sus resultados y cómo terminó."""

    llamadas: list[str] = field(default_factory=list)
    resultados: list[tuple[bool | None, str]] = field(default_factory=list)
    subtype: str | None = None
    excepcion: str | None = None


def _texto(contenido: Any) -> str:
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "".join(str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in contenido)
    return str(contenido)


def _opciones(
    permitidas: list[str], servidores: dict[str, Any], hooks: Any, max_turns: int | None = None
):
    """Las opciones aisladas del paquete (`opciones_base`: sin `CLAUDE.md`, sin herramientas)."""
    base = configuracion.opciones_base(
        modelo=MODELO,
        system_prompt=INSTRUCCION,
        permitidas=permitidas,
        prohibidas=[],
        mcp_servers=servidores,
        hooks=hooks,
    )
    base = dataclasses.replace(base, stderr=recoger_stderr)
    return dataclasses.replace(base, max_turns=max_turns) if max_turns else base


async def _correr(prompt: str, opciones: Any) -> Traza:
    traza = Traza()
    try:
        async for mensaje in query(prompt=prompt, options=opciones):
            if isinstance(mensaje, AssistantMessage):
                traza.llamadas += [b.name for b in mensaje.content if isinstance(b, ToolUseBlock)]
            elif isinstance(mensaje, UserMessage) and isinstance(mensaje.content, list):
                for bloque in mensaje.content:
                    if isinstance(bloque, ToolResultBlock):
                        traza.resultados.append((bloque.is_error, _texto(bloque.content)))
            elif isinstance(mensaje, ResultMessage):
                traza.subtype = mensaje.subtype
    except ResultError as error:
        traza.excepcion = type(error).__name__
    return traza


def _si_llamo(traza: Traza, medido: Any) -> Any:
    """Lo medido, o `NO_CONCLUYENTE` si el modelo no llamó a ninguna herramienta."""
    return medido if traza.llamadas else NO_CONCLUYENTE


def _grabador(registro: list[dict[str, Any]], etiqueta: str):
    async def hook(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
        registro.append({"hook": etiqueta, **entrada})
        return permitir()

    return hook


def _pasarela(extra: dict[str, str] | None = None) -> dict[str, Any]:
    entorno = {"PASARELA_RESULTADOS_DIR": tempfile.mkdtemp(prefix="sondeo7-"), **(extra or {})}
    return {"pasarela": configuracion.servidor_pasarela(entorno)}


def _servidor_en_proceso(ejecuciones: list[Any]):
    @tool("delegar_frente", "Delega un frente de la investigación.", {"frente": str})
    async def delegar_frente(args: dict[str, Any]) -> dict[str, Any]:
        ejecuciones.append(args)
        return {"content": [{"type": "text", "text": json.dumps({"ok": True})}]}

    return {"delegacion": create_sdk_mcp_server("delegacion", tools=[delegar_frente])}


PEDIR_REGISTRO = (
    "Llama una vez a consultar_registro_mercantil con identificador CO-TV-0001 y responde ok."
)

# ------------------------------------------------------------------ experimentos (R1 a R3)


async def _forma_de_tool_response() -> list[Medicion]:
    """(a) Qué forma tiene `tool_response` en `PostToolUse` (R1)."""
    vistos: list[dict[str, Any]] = []
    stdio = {"PostToolUse": [HookMatcher(matcher=REGISTRO, hooks=[_grabador(vistos, "post")])]}
    await _correr(PEDIR_REGISTRO, _opciones([REGISTRO], _pasarela(), stdio))
    forma_stdio = type(vistos[0]["tool_response"]).__name__ if vistos else NO_CONCLUYENTE

    en_proceso: list[dict[str, Any]] = []
    hooks = {"PostToolUse": [HookMatcher(matcher=DELEGAR, hooks=[_grabador(en_proceso, "post")])]}
    pedido = "Llama una vez a delegar_frente con frente registro y responde ok."
    await _correr(pedido, _opciones([DELEGAR], _servidor_en_proceso([]), hooks))
    forma_en_proceso = (
        type(en_proceso[0]["tool_response"]).__name__ if en_proceso else NO_CONCLUYENTE
    )
    return [
        Medicion("a1_stdio", "tool_response de un servidor stdio", "str", forma_stdio),
        Medicion(
            "a2_en_proceso", "tool_response de un servidor en proceso", "list", forma_en_proceso
        ),
    ]


async def _via_del_error_estructurado() -> list[Medicion]:
    """(b) Un error estructurado de la pasarela llega por `PostToolUseFailure` (R1)."""
    vistos: list[dict[str, Any]] = []
    hooks = {
        "PostToolUse": [HookMatcher(matcher=NOTICIAS, hooks=[_grabador(vistos, "PostToolUse")])],
        "PostToolUseFailure": [
            HookMatcher(matcher=NOTICIAS, hooks=[_grabador(vistos, "PostToolUseFailure")])
        ],
    }
    servidores = _pasarela({"PASARELA_FALLA_NOTICIAS": "1"})
    pedido = "Llama una vez a buscar_noticias con identificador CO-TV-0001 y di qué devolvió."
    await _correr(pedido, _opciones([NOTICIAS], servidores, hooks))
    vias = sorted({v["hook"] for v in vistos}) if vistos else NO_CONCLUYENTE
    tipo = NO_CONCLUYENTE
    for visto in vistos:
        if visto["hook"] == "PostToolUseFailure":
            try:
                tipo = json.loads(visto["error"]).get("tipo")
            except ValueError:
                tipo = "ilegible"
    return [
        Medicion("b1_via", "hooks que ven el error estructurado", ["PostToolUseFailure"], vias),
        Medicion("b2_tipo", "tipo del error en `error` (JSON)", "servicio_no_disponible", tipo),
    ]


async def _excepcion_y_deny() -> list[Medicion]:
    """(c) Una excepción en un hook deja pasar la acción; un deny la bloquea (R2)."""

    async def roto(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
        raise RuntimeError("fallo simulado del hook")

    vistos: list[dict[str, Any]] = []
    hooks = {
        "PreToolUse": [HookMatcher(matcher=REGISTRO, hooks=[roto])],
        "PostToolUse": [HookMatcher(matcher=REGISTRO, hooks=[_grabador(vistos, "post")])],
    }
    traza = await _correr(PEDIR_REGISTRO, _opciones([REGISTRO], _pasarela(), hooks))
    se_ejecuto = bool(vistos) if traza.llamadas else NO_CONCLUYENTE

    async def deniega(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
        return denegar("MOTIVO-DE-PRUEBA")

    ejecuciones: list[Any] = []
    bloqueo = {"PreToolUse": [HookMatcher(matcher=DELEGAR, hooks=[deniega])]}
    pedido = "Llama una vez a delegar_frente con frente listas y cuenta qué respondió."
    otra = await _correr(pedido, _opciones([DELEGAR], _servidor_en_proceso(ejecuciones), bloqueo))
    motivo_llega = (
        any(error and "MOTIVO-DE-PRUEBA" in texto for error, texto in otra.resultados)
        if otra.llamadas
        else NO_CONCLUYENTE
    )
    sin_ejecutar = (len(ejecuciones) == 0) if otra.llamadas else NO_CONCLUYENTE
    return [
        Medicion(
            "c1_excepcion", "una excepción en PreToolUse deja pasar la acción", True, se_ejecuto
        ),
        Medicion("c2_deny_bloquea", "un deny impide ejecutar la herramienta", True, sin_ejecutar),
        Medicion("c3_deny_motivo", "el motivo del deny llega al modelo", True, motivo_llega),
    ]


async def _stop_con_block() -> list[Medicion]:
    """(d) Un `Stop` con `block` hace continuar; cada devolución gasta un turno (R3)."""
    activos: list[bool] = []

    async def siempre(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
        activos.append(bool(entrada.get("stop_hook_active")))
        return bloquear_cierre("Falta escalar el caso: responde de nuevo con la palabra ESCALADO.")

    hooks = {"Stop": [HookMatcher(hooks=[siempre])]}
    traza = await _correr("Responde únicamente con la palabra listo.", _opciones([], {}, hooks, 4))
    mediciones = [
        Medicion(
            "d1_continua", "el Stop invocado en cada devolución", [False, True, True, True], activos
        ),
        Medicion(
            "d2_turnos",
            "cada devolución gasta un turno de max_turns",
            "error_max_turns",
            traza.subtype,
        ),
    ]

    llamadas: list[bool] = []

    async def dos_veces(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
        llamadas.append(bool(entrada.get("stop_hook_active")))
        return bloquear_cierre("Falta escalar.") if len(llamadas) <= 2 else permitir()

    hooks = {"Stop": [HookMatcher(hooks=[dos_veces])]}
    otra = await _correr("Responde únicamente con la palabra listo.", _opciones([], {}, hooks, 30))
    mediciones.append(
        Medicion("d3_termina", "tras permitir, el caso termina normal", "success", otra.subtype)
    )
    mediciones.append(Medicion("d4_cuenta", "veces que se invocó el Stop", 3, len(llamadas)))
    return mediciones


# ---------------------------------------------------------- los hooks del caso con el SDK real (G2)


async def _hooks_del_caso() -> list[Medicion]:
    """(G2) `HooksDelCaso` en sesiones reales: identificación por el hook y listas bloqueado."""
    estado, eventos = EstadoCaso("sondeo"), RegistroEventos()
    hooks = HooksDelCaso(estado, eventos)
    servidores = _pasarela()

    opciones = configuracion.opciones_subagente(
        Frente.REGISTRO, INSTRUCCION, hooks=hooks.subagente(Frente.REGISTRO)
    )
    opciones = dataclasses.replace(opciones, mcp_servers=servidores, stderr=recoger_stderr)
    traza = await _correr(PEDIR_REGISTRO, opciones)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.TERMINADO)
    comercio = (estado.comercio or {}).get("identificador")
    mediciones = [
        Medicion(
            "g1_identifica",
            "el hook del registro identifica al comercio",
            "CO-TV-0001",
            _si_llamo(traza, comercio),
        )
    ]

    listas = configuracion.opciones_subagente(
        Frente.LISTAS, INSTRUCCION, hooks=hooks.subagente(Frente.LISTAS)
    )
    listas = dataclasses.replace(listas, mcp_servers=servidores, stderr=recoger_stderr)
    ajena = (
        "Llama una vez a consultar_listas_restrictivas con tipo persona y nombre "
        "Mateo Ríos Cabrera."
    )
    traza = await _correr(ajena, listas)
    reglas = [e.regla for e in eventos.eventos() if e.tipo == TIPO_BLOQUEO_REGLA]
    mediciones.append(
        Medicion(
            "g2_bloquea_ajena",
            "el hook de listas bloquea una consulta ajena (I.1)",
            (0, ["I.1"]),
            _si_llamo(traza, (len(estado.libro.consultas_listas), reglas)),
        )
    )

    propia = (
        "Llama una vez a consultar_listas_restrictivas con tipo comercio e identificador "
        "CO-TV-0001."
    )
    traza = await _correr(propia, listas)
    mediciones.append(
        Medicion(
            "g3_permite_propia",
            "el hook de listas permite la consulta del comercio",
            1,
            _si_llamo(traza, len(estado.libro.consultas_listas)),
        )
    )
    return mediciones


# ------------------------------------------------------------------ punto de entrada


async def sondear() -> list[Medicion]:
    """Todos los experimentos, uno tras otro, y sus mediciones."""
    STDERR_DE_LA_CLI.clear()
    mediciones: list[Medicion] = []
    for experimento in (
        _forma_de_tool_response,
        _via_del_error_estructurado,
        _excepcion_y_deny,
        _stop_con_block,
        _hooks_del_caso,
    ):
        mediciones += await experimento()
    return mediciones


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    mediciones = asyncio.run(sondear())
    print(informe(mediciones))
    veredictos = {veredicto(m) for m in mediciones}
    if veredictos != {"coincide"} and STDERR_DE_LA_CLI:
        print()
        print("Salida de error de la CLI (para diagnosticar):")
        for linea in STDERR_DE_LA_CLI:
            print(f"  {linea}")
    if "difiere" in veredictos:
        return 1
    return 2 if "inconcluso" in veredictos else 0


if __name__ == "__main__":
    sys.exit(main())
