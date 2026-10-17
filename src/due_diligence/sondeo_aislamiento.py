"""Sondeo manual con el modelo real (Q2, Q3, Q4; R2, R3, R5). No corre en `pytest`.

    uv run python -m due_diligence.sondeo_aislamiento                 # aislamiento (Q2)
    uv run python -m due_diligence.sondeo_aislamiento --herramientas  # herramientas por agente (Q3)
    uv run python -m due_diligence.sondeo_aislamiento --limite        # límite de turnos (Q4)

Las opciones salen de `opciones_base`; solo el sondeo de aislamiento activa la herramienta
integrada `Glob` con `dataclasses.replace(...)` para pedir un `Glob` inofensivo. Sale con código
distinto de cero si algo no es lo esperado.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass, field, replace

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)
from claude_agent_sdk._errors import ResultError

from due_diligence import configuracion
from due_diligence.eventos import TIPO_FRENTE_FIN, RegistroEventos
from due_diligence.frentes import (
    HERRAMIENTA_DELEGAR,
    SERVIDOR_DELEGACION,
    Frente,
)
from due_diligence.terminacion import Terminacion, clasificar_error, clasificar_resultado

PROMPT_AISLAMIENTO = (
    "Usa Glob con el patrón 'specs/006-*/spec.md' y luego dime si conoces instrucciones de un "
    "CLAUDE.md del proyecto (sí/no)."
)


@dataclass
class Observacion:
    etiqueta: str
    skills: list[str] = field(default_factory=list)
    agentes: list[str] = field(default_factory=list)
    herramientas: list[str] = field(default_factory=list)
    eventos_de_hooks: int = 0
    respuesta: str = ""


def _nombres_del_repositorio(subcarpeta: str) -> set[str]:
    carpeta = configuracion.RAIZ / ".claude" / subcarpeta
    if not carpeta.is_dir():
        return set()
    return {p.stem if p.is_file() else p.name for p in carpeta.iterdir()}


async def _observar(etiqueta: str, opciones) -> Observacion:
    observacion = Observacion(etiqueta)
    try:
        async for mensaje in query(prompt=PROMPT_AISLAMIENTO, options=opciones):
            if isinstance(mensaje, SystemMessage):
                datos = mensaje.data or {}
                if mensaje.subtype == "init":
                    observacion.skills = list(datos.get("skills", []))
                    observacion.agentes = list(datos.get("agents", []))
                    observacion.herramientas = list(datos.get("tools", []))
                elif "hook" in mensaje.subtype:
                    observacion.eventos_de_hooks += 1
            elif isinstance(mensaje, AssistantMessage):
                for bloque in mensaje.content:
                    if isinstance(bloque, TextBlock):
                        observacion.respuesta = bloque.text
    except ResultError:
        pass
    return observacion


def _opciones_aislamiento(fuentes: list[str]):
    base = configuracion.opciones_base(
        modelo=configuracion.modelo_coordinador(),
        system_prompt="Responde en una línea.",
        permitidas=["Glob"],
        prohibidas=[],
        mcp_servers={},
    )
    return replace(base, tools=["Glob"], include_hook_events=True, setting_sources=fuentes)


async def sondeo_aislamiento() -> int:
    paquete = await _observar("setting_sources=[]  (las del paquete)", _opciones_aislamiento([]))
    control = await _observar(
        'setting_sources=["project"]  (control)', _opciones_aislamiento(["project"])
    )
    propias = _nombres_del_repositorio("skills") | _nombres_del_repositorio("agents")

    print(f"{'Opciones':45} {'skills/agentes del repo':25} {'hooks':>6}  ¿conoce CLAUDE.md?")
    for o in (paquete, control):
        del_repo = sorted(propias & (set(o.skills) | set(o.agentes)))
        repo = ", ".join(del_repo) or "ninguno"
        print(f"{o.etiqueta:45} {repo:25} {o.eventos_de_hooks:>6}  {o.respuesta[:60]!r}")

    errores = []
    if propias & (set(paquete.skills) | set(paquete.agentes)):
        errores.append("con [] aparecen skills o agentes del repositorio")
    if paquete.eventos_de_hooks:
        errores.append("con [] hubo eventos de hooks")
    if "sí" in paquete.respuesta.lower()[:20]:
        errores.append("con [] el agente dice conocer el CLAUDE.md")
    if not (propias & (set(control.skills) | set(control.agentes))) or not control.eventos_de_hooks:
        errores.append(
            "el control con ['project'] no mostró skills, agentes ni hooks: el sondeo no discrimina"
        )
    for e in errores:
        print("FALLA:", e)
    print("OK: el aislamiento se comprueba." if not errores else "El aislamiento NO se comprueba.")
    return 1 if errores else 0


async def _herramientas_iniciales(opciones) -> list[str]:
    herramientas: list[str] = []
    try:
        async for mensaje in query(prompt="Di: ok", options=opciones):
            if isinstance(mensaje, SystemMessage) and mensaje.subtype == "init":
                herramientas = sorted((mensaje.data or {}).get("tools", []))
    except ResultError:
        pass
    return herramientas


async def sondeo_herramientas() -> int:
    @tool(HERRAMIENTA_DELEGAR, "Herramienta de delegación (sondeo).", {"frente": str})
    async def delegar(_args):
        return {"content": [{"type": "text", "text": "ok"}]}

    servidor = create_sdk_mcp_server(SERVIDOR_DELEGACION, tools=[delegar])
    agentes = {
        "coordinador": configuracion.opciones_coordinador(servidor, "Responde en una línea.")
    }
    for frente in Frente:
        agentes[frente.value] = configuracion.opciones_subagente(frente, "Responde en una línea.")

    fallas = 0
    for nombre, opciones in agentes.items():
        vistas = await _herramientas_iniciales(opciones)
        esperadas = sorted(set(opciones.allowed_tools))
        coincide = vistas == esperadas
        fallas += not coincide
        print(f"{nombre:12} {'OK ' if coincide else 'FALLA'} vistas={vistas}")
        if not coincide:
            print(f"{'':12} esperadas={esperadas}")
    return 1 if fallas else 0


async def sondeo_limite() -> int:
    opciones = replace(configuracion.opciones_subagente(Frente.REGISTRO, "Una línea."), max_turns=1)
    prompt = "Consulta con el identificador «CO-TV-0001»."
    eventos = RegistroEventos()
    clasificacion = None
    try:
        async for mensaje in query(prompt=prompt, options=opciones):
            if isinstance(mensaje, ResultMessage):
                clasificacion = clasificar_resultado(mensaje)
    except ResultError as error:
        # El SDK la lanza después del ResultMessage: solo se clasifica si no se vio antes.
        if clasificacion is None:
            clasificacion = clasificar_error(error)
        print("ResultError capturada sin romper el caso.")
    if clasificacion is None:
        print("FALLA: no hubo resultado.")
        return 1
    eventos.registrar(
        TIPO_FRENTE_FIN,
        Frente.REGISTRO,
        f"{clasificacion.terminacion.name} {clasificacion.detalle}",
    )
    for evento in eventos.eventos():
        print(f"evento {evento.secuencia} {evento.tipo} {evento.frente}: {evento.detalle}")
    ok = clasificacion.terminacion is Terminacion.LIMITE_SEGURIDAD
    print(
        "OK: LIMITE_SEGURIDAD."
        if ok
        else f"FALLA: se esperaba LIMITE_SEGURIDAD y fue {clasificacion.terminacion.name}."
    )
    return 0 if ok else 1


def main(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    grupo = analizador.add_mutually_exclusive_group()
    grupo.add_argument(
        "--herramientas", action="store_true", help="herramientas iniciales por agente (Q3)"
    )
    grupo.add_argument(
        "--limite", action="store_true", help="límite de turnos con max_turns=1 (Q4)"
    )
    args = analizador.parse_args(argumentos)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sondeo = (
        sondeo_herramientas
        if args.herramientas
        else sondeo_limite
        if args.limite
        else sondeo_aislamiento
    )
    return asyncio.run(sondeo())


if __name__ == "__main__":
    sys.exit(main())
