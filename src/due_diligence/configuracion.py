"""Configuración del SDK: opciones de cada agente, herramientas permitidas y modelos (R2, R3, R9).

Toda opción que construye el paquete pasa por `opciones_base`, que fija el aislamiento:
`setting_sources=[]` (ni `CLAUDE.md`, ni hooks, ni ajustes del repositorio o del usuario),
`tools=[]` (sin herramientas integradas) y `strict_mcp_config=True` (solo los servidores
declarados aquí). `allowed_tools` solo pre-aprueba y no oculta las demás (medido en R3), por eso
cada agente lleva también `disallowed_tools` con el complemento.
"""

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions
from dotenv import load_dotenv

from due_diligence.frentes import (
    FRENTES,
    HERRAMIENTA_DELEGAR,
    HERRAMIENTAS_DECISION,
    HERRAMIENTAS_FUENTES,
    SERVIDOR_DELEGACION,
    SERVIDOR_PASARELA,
    Frente,
    herramientas_ajenas,
    nombre_completo,
)

# Raíz del repositorio: src/due_diligence/configuracion.py → tres niveles arriba.
RAIZ = Path(__file__).resolve().parents[2]

# Un mismo modelo para el coordinador y los cuatro subagentes (R9). Cada uno se sustituye por
# separado con su variable de entorno, sin tocar el código.
MODELO_POR_DEFECTO = "claude-sonnet-5-5"
VARIABLE_MODELO_COORDINADOR = "PASARELA_MODELO_COORDINADOR"
VARIABLE_MODELO_SUBAGENTES = "PASARELA_MODELO_SUBAGENTES"

# PROTECCIÓN DE SEGURIDAD, no un mecanismo de control (FR-010, FR-011): el ciclo lo ejecuta el
# SDK y termina por la razón de parada del modelo. Este límite solo evita un ciclo desbocado; si
# se alcanza, el SDK lo informa como `error_max_turns` y se registra aparte (R5).
MAX_TURNOS_SEGURIDAD = 30

# Variables del servidor `pasarela` que se reenvían a su proceso si están definidas (#5).
VARIABLES_PASARELA = ("PASARELA_FALLA_NOTICIAS", "PASARELA_RESULTADOS_DIR")


def _modelo(variable: str, entorno: Mapping[str, str] | None) -> str:
    valor = (os.environ if entorno is None else entorno).get(variable, "").strip()
    return valor or MODELO_POR_DEFECTO


def modelo_coordinador(entorno: Mapping[str, str] | None = None) -> str:
    return _modelo(VARIABLE_MODELO_COORDINADOR, entorno)


def modelo_subagentes(entorno: Mapping[str, str] | None = None) -> str:
    return _modelo(VARIABLE_MODELO_SUBAGENTES, entorno)


def servidor_pasarela(entorno: Mapping[str, str] | None = None) -> dict[str, Any]:
    """El servidor `pasarela` del #5, por stdio, con el intérprete actual.

    Con `setting_sources=[]` el SDK no lee `.mcp.json`, así que se declara aquí (R3).
    """
    fuente = os.environ if entorno is None else entorno
    reenviadas = {v: fuente[v] for v in VARIABLES_PASARELA if v in fuente}
    servidor: dict[str, Any] = {
        "type": "stdio",
        "command": sys.executable,
        "args": ["-m", "servidor_mcp"],
    }
    if reenviadas:
        servidor["env"] = reenviadas
    return servidor


def herramientas_coordinador() -> tuple[list[str], list[str]]:
    """(permitidas, prohibidas) del coordinador: delegar y los canales de decisión (FR-002)."""
    permitidas = [
        nombre_completo(HERRAMIENTA_DELEGAR, SERVIDOR_DELEGACION),
        *(nombre_completo(h) for h in HERRAMIENTAS_DECISION),
    ]
    prohibidas = [nombre_completo(h) for h in HERRAMIENTAS_FUENTES]
    return permitidas, prohibidas


def herramientas_subagente(frente: Frente) -> tuple[list[str], list[str]]:
    """(permitidas, prohibidas) de un subagente: solo la herramienta de su frente (FR-003)."""
    permitidas = [FRENTES[frente].herramienta_completa]
    prohibidas = [nombre_completo(h) for h in herramientas_ajenas(frente)]
    return permitidas, prohibidas


def opciones_base(
    *,
    modelo: str,
    system_prompt: str,
    permitidas: list[str],
    prohibidas: list[str],
    mcp_servers: dict[str, Any],
    hooks: Any = None,
) -> ClaudeAgentOptions:
    """Única función que construye `ClaudeAgentOptions` (R2)."""
    return ClaudeAgentOptions(
        model=modelo,
        system_prompt=system_prompt,
        allowed_tools=permitidas,
        disallowed_tools=prohibidas,
        mcp_servers=mcp_servers,
        hooks=hooks,
        setting_sources=[],
        tools=[],
        strict_mcp_config=True,
        cwd=str(RAIZ),
        max_turns=MAX_TURNOS_SEGURIDAD,
    )


def opciones_coordinador(
    servidor_delegacion: Any,
    system_prompt: str,
    *,
    hooks: Any = None,
    entorno: Mapping[str, str] | None = None,
) -> ClaudeAgentOptions:
    permitidas, prohibidas = herramientas_coordinador()
    return opciones_base(
        modelo=modelo_coordinador(entorno),
        system_prompt=system_prompt,
        permitidas=permitidas,
        prohibidas=prohibidas,
        mcp_servers={
            SERVIDOR_PASARELA: servidor_pasarela(entorno),
            SERVIDOR_DELEGACION: servidor_delegacion,
        },
        hooks=hooks,
    )


def opciones_subagente(
    frente: Frente,
    system_prompt: str,
    *,
    hooks: Any = None,
    entorno: Mapping[str, str] | None = None,
) -> ClaudeAgentOptions:
    permitidas, prohibidas = herramientas_subagente(frente)
    return opciones_base(
        modelo=modelo_subagentes(entorno),
        system_prompt=system_prompt,
        permitidas=permitidas,
        prohibidas=prohibidas,
        mcp_servers={SERVIDOR_PASARELA: servidor_pasarela(entorno)},
        hooks=hooks,
    )


def cargar_entorno() -> bool:
    """Carga las variables del archivo de entorno del proyecto, sin pisar las ya definidas (R8).

    Solo la llama el punto de entrada (`__main__`): ni el paquete, ni `ejecutar_caso`, ni los
    tests la usan. No lleva el nombre del archivo: `load_dotenv()` lo busca subiendo desde aquí.
    """
    return load_dotenv(override=False)
