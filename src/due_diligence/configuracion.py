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

# Un mismo modelo para el coordinador y los cuatro subagentes (R9 del #6). Desde el #7 es Opus 5.5
# por decisión de la analista, fijado aquí y no solo por variable de entorno, para que quien ejecute
# el producto sin archivo de entorno obtenga el mismo modelo. Cada uno se sustituye por separado con
# su variable de entorno (por ejemplo, para volver a `claude-sonnet-5-5`), sin tocar el código.
MODELO_POR_DEFECTO = "claude-opus-5-5"
VARIABLE_MODELO_COORDINADOR = "PASARELA_MODELO_COORDINADOR"
VARIABLE_MODELO_SUBAGENTES = "PASARELA_MODELO_SUBAGENTES"

# PROTECCIÓN DE SEGURIDAD, no un mecanismo de control (FR-010, FR-011): el ciclo lo ejecuta el
# SDK y termina por la razón de parada del modelo. Este límite solo evita un ciclo desbocado; si
# se alcanza, el SDK lo informa como `error_max_turns` y se registra aparte (R5).
MAX_TURNOS_SEGURIDAD = 30

# PROTECCIÓN DE SEGURIDAD, no el mecanismo de la regla (#7, R3): cuántas veces el hook de `Stop`
# contradice el fin de turno del coordinador cuando el caso requiere escalamiento y no se escaló.
# Lo garantizado en código es que ese caso nunca se recomienda habilitar, nunca figura como
# completo y queda marcado `cierre_sin_escalar`; que el escalamiento ocurra depende del modelo,
# con este número de oportunidades. El ciclo sigue terminando por la razón de parada; este contador
# solo limita las devoluciones, igual que `max_turns`. Es menor que `MAX_TURNOS_SEGURIDAD`: las
# devoluciones gastan turnos (medido en R3) y no deben llevar por sí solas a `error_max_turns`.
MAX_CIERRES_IMPEDIDOS = 3

# PROTECCIÓN, no control del ciclo (principio III; #8, R3): cuántas veces se puede volver a
# ejecutar un frente con la misma entrada tras un error reintentable. Lo pide el modelo y lo
# guarda el `Delegador`; el ciclo sigue terminando por la razón de parada. 1, por indicación de
# la analista.
MAX_REINTENTOS_POR_FRENTE = 1

# Presupuesto de turnos del peor caso razonable del coordinador (#8, R2, medido: cada reintento y
# cada devolución del `Stop` gastan un turno). Los pasos fijos son las filas de la tabla de R2 que
# no dependen de otras constantes: tres frentes juntos, listas, categoría con otra entrada, listas
# rechazada por la carrera, escalar, informe rechazado, informe aceptado y respuesta final. El #10
# (R10) añade dos: el escalamiento rechazado por la forma y corregido, y noticias vuelto a delegar
# con el comercio identificado (FR-027). El presupuesto es **por turno**: cada mensaje del analista
# es una `query()` y su `num_turns` no se acumula (#10, R1, medido).
PASOS_FIJOS_PEOR_CASO = 10


def presupuesto_turnos_peor_caso(max_reintentos: int, max_cierres: int) -> int:
    """Turnos del peor caso: pasos fijos, reintentos, informes nuevos y devoluciones del `Stop`.

    El #9 (R8) suma un informe nuevo por cada reintento posible: un reintento con éxito cambia la
    cobertura, invalida el informe vigente (FR-023) y pide otro, que no estaba en ningún término.
    No cuenta un cambio de comercio, una coincidencia nueva ni un informe enviado en el mismo
    mensaje que una primera delegación: los cubre el margen hasta `MAX_TURNOS_SEGURIDAD`.
    """
    reintentos = len(Frente) * max_reintentos
    informes_nuevos = len(Frente) * max_reintentos
    return PASOS_FIJOS_PEOR_CASO + reintentos + informes_nuevos + max_cierres


# Se calcula, no se escribe a mano: si suben los reintentos o las devoluciones, sube con ellos y el
# test que lo compara con `MAX_TURNOS_SEGURIDAD` protege (indicación de la analista).
PRESUPUESTO_TURNOS_PEOR_CASO = presupuesto_turnos_peor_caso(
    MAX_REINTENTOS_POR_FRENTE, MAX_CIERRES_IMPEDIDOS
)


def turnos_usados(turnos: int | None) -> str:
    """«N de MAX_TURNOS_SEGURIDAD» para la línea de comandos (#8, R2), o «sin dato».

    Vive aquí para que el límite de turnos solo se nombre en este módulo (FR-010 del #6).
    """
    return "sin dato" if turnos is None else f"{turnos} de {MAX_TURNOS_SEGURIDAD}"


# Modo de demostración (#7, R11): quita del prompt del coordinador las instrucciones de las
# reglas de negocio para que el modelo pueda intentar las acciones prohibidas. NO desactiva ningún
# hook y no se reenvía al servidor de la pasarela.
VARIABLE_MODO_DEMO = "PASARELA_MODO_DEMO_HOOKS"

# Variables del servidor `pasarela` que se reenvían a su proceso si están definidas (#5; el #9
# añade la caída simulada del registro, pareja de la de noticias).
VARIABLES_PASARELA = (
    "PASARELA_FALLA_NOTICIAS",
    "PASARELA_FALLA_REGISTRO",
    "PASARELA_RESULTADOS_DIR",
)


def _modelo(variable: str, entorno: Mapping[str, str] | None) -> str:
    valor = (os.environ if entorno is None else entorno).get(variable, "").strip()
    return valor or MODELO_POR_DEFECTO


def modo_demostracion(entorno: Mapping[str, str] | None = None) -> bool:
    """`True` solo con el valor exacto `1`. Con `entorno=None` lee `os.environ` (como `_modelo`)."""
    fuente = os.environ if entorno is None else entorno
    return fuente.get(VARIABLE_MODO_DEMO, "") == "1"


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


AVISO_CONECTORES = "claude.ai connectors are disabled"


def filtrar_stderr(linea: str) -> None:
    """Callback `stderr` del SDK: descarta el aviso de conectores y deja pasar lo demás.

    Cada CLI lo emite al arrancar con `strict_mcp_config`; no informa de nada. Cualquier otra línea
    (un error real) se escribe en la salida de error.
    """
    if AVISO_CONECTORES in linea.lower():
        return
    print(linea, file=sys.stderr)


def opciones_base(
    *,
    modelo: str,
    system_prompt: str,
    permitidas: list[str],
    prohibidas: list[str],
    mcp_servers: dict[str, Any],
    hooks: Any = None,
    resume: str | None = None,
) -> ClaudeAgentOptions:
    """Única función que construye `ClaudeAgentOptions` (R2).

    `resume` es el `session_id` del turno anterior del coordinador (#10, R1): la `query()` del
    turno siguiente continúa esa conversación. Los subagentes nunca reanudan.
    """
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
        stderr=filtrar_stderr,
        resume=resume,
    )


def opciones_coordinador(
    servidor_delegacion: Any,
    system_prompt: str,
    *,
    hooks: Any = None,
    entorno: Mapping[str, str] | None = None,
    resume: str | None = None,
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
        resume=resume,
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


# Credencial (#11, R8, FR-006): la única es `ANTHROPIC_API_KEY`. La comprueban los dos puntos de
# entrada (el chat y `__main__`) después de cargar el entorno y antes de crear ningún caso. El
# mensaje describe el archivo sin nombrarlo, porque ningún módulo lo nombra (R8 del #6, que fija
# `test_sin_control_propio.py`); el README lo nombra paso a paso (desviación D1 del plan).
VARIABLE_CLAVE = "ANTHROPIC_API_KEY"
# Las que el CLI de Claude Code usaría antes que `ANTHROPIC_API_KEY`, según su precedencia
# documentada (no medida, R14): con alguna definida, la clave del proyecto no sería la que se usa.
CREDENCIALES_ALTERNATIVAS = (
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
)
MENSAJE_SIN_CLAVE = (
    "Falta la clave de Anthropic: la variable ANTHROPIC_API_KEY no está definida o está vacía. "
    "Para configurarla, copie la plantilla de variables de entorno de la raíz del repositorio (la "
    "que termina en «.example») como archivo de entorno local, sin esa terminación; ponga su clave "
    "en ANTHROPIC_API_KEY (solo en ese archivo, que no se sube al repositorio) y reinicie la "
    "aplicación. El README lo explica paso a paso en «Interfaz de chat»."
)
MENSAJE_OTRA_CREDENCIAL = (
    "Está definida la variable {variable}, que haría usar otra credencial en lugar de "
    "ANTHROPIC_API_KEY. Esta aplicación solo usa ANTHROPIC_API_KEY: quite {variable} del entorno y "
    "reinicie la aplicación."
)


def comprobar_credencial(entorno: Mapping[str, str] | None = None) -> str | None:
    """El mensaje que detiene la aplicación, o `None` si la credencial está bien (#11, R8).

    Pura: con `entorno=None` lee `os.environ` (como `modo_demostracion`). Nunca incluye el valor de
    ninguna variable.
    """
    fuente = os.environ if entorno is None else entorno
    if not fuente.get(VARIABLE_CLAVE, "").strip():
        return MENSAJE_SIN_CLAVE
    for variable in CREDENCIALES_ALTERNATIVAS:
        if fuente.get(variable, "").strip():
            return MENSAJE_OTRA_CREDENCIAL.format(variable=variable)
    return None
