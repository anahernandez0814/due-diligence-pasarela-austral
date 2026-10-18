"""Hooks del Agent SDK que garantizan las reglas I.1, I.2 e I.3 (R1 a R6, FR-010, FR-012).

`HooksDelCaso` construye, para un caso, los hooks de cada agente con cierre sobre **el mismo**
`EstadoCaso` y registro de eventos: lo compartido es el estado, los hooks van por agente
(`contracts/hooks.md`). Son funciones Python del proceso del caso: no hay estado de módulo y no se
pasa nada por el SDK.

Lo medido con el SDK 0.2.168 (research R1 a R3) condiciona el diseño:

- `PostToolUse` recibe `tool_response` como texto JSON (stdio) o lista de bloques (en proceso); un
  error estructurado de la pasarela llega solo por `PostToolUseFailure`. Un único lector,
  `ejecutor.interpretar_resultado`, entiende las dos formas.
- Una excepción o una salida inválida en un hook **deja pasar la acción**. Por eso cada hook se
  envuelve con `fallar_cerrado` y sus salidas se construyen solo con `permitir`, `denegar` y
  `bloquear_cierre`.
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from claude_agent_sdk import HookMatcher

from due_diligence.ejecutor import interpretar_resultado
from due_diligence.estado import EstadoCaso
from due_diligence.eventos import (
    TIPO_CONSULTA_FALLIDA,
    TIPO_FALLO_DE_HOOK,
    RegistroEventos,
)
from due_diligence.frentes import FRENTES, Frente

Hook = Callable[[dict[str, Any], str | None, Any], Awaitable[dict[str, Any]]]

MOTIVO_FALLO_DE_HOOK = "No se pudo verificar la regla; se bloquea por precaución."
MOTIVO_LIBRO_SELLADO = "No se pudo registrar un hecho de la regla; se bloquea por precaución."

# --------------------------------------------------------------------------- salidas tipadas


def permitir() -> dict[str, Any]:
    """La acción sigue."""
    return {}


def denegar(motivo: str) -> dict[str, Any]:
    """`PreToolUse`: la herramienta no se ejecuta y el modelo recibe el motivo."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        }
    }


def bloquear_cierre(motivo: str) -> dict[str, Any]:
    """`Stop`: el coordinador no termina y el motivo llega al modelo."""
    return {"decision": "block", "reason": motivo}


# --------------------------------------------------------------------------- lectura


def leer_respuesta(contenido: Any, es_error: bool = False) -> tuple[Any, Any]:
    """(resultado del contrato, error estructurado) de lo que devolvió una herramienta.

    Reutiliza `ejecutor.interpretar_resultado`, el único lector (R1): acepta el texto JSON de un
    servidor stdio y la lista de bloques de uno en proceso. Lo que no es ni lo uno ni lo otro, o no
    es texto ni lista, es `(None, None)`.
    """
    if contenido is not None and not isinstance(contenido, (str, list, tuple)):
        return None, None
    return interpretar_resultado(contenido, es_error)


# --------------------------------------------------------------------------- fallo cerrado


def _registrar_fallo(
    tipo: str, error: Exception, estado: EstadoCaso, eventos: RegistroEventos, frente: Frente | None
) -> None:
    """Deja el sello y el evento; el texto de la excepción no sale al modelo ni al evento."""
    estado.libro.fallo_de_hook = f"{tipo}: {type(error).__name__}"
    eventos.registrar(
        TIPO_FALLO_DE_HOOK,
        frente,
        f"Un hook de {tipo} falló: la regla no se pudo verificar y se bloquea por precaución.",
    )


def fallar_cerrado(
    hook: Hook,
    tipo: str,
    estado: EstadoCaso,
    eventos: RegistroEventos,
    frente: Frente | None = None,
) -> Hook:
    """Envuelve un hook para que un fallo no deje pasar la acción (FR-012, R2).

    - `PreToolUse`: deniega con un motivo genérico.
    - `Stop`: bloquea el cierre y cuenta como una devolución.
    - `PostToolUse` y `PostToolUseFailure`: no pueden impedir nada; sellan el libro y los
      `PreToolUse` de las reglas deniegan mientras el sello exista.

    Atrapa `Exception`, no `BaseException`: una cancelación del frente se propaga.
    """

    async def envuelto(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
        try:
            return await hook(entrada, tool_use_id, contexto)
        except Exception as error:
            _registrar_fallo(tipo, error, estado, eventos, frente)
            if tipo == "PreToolUse":
                return denegar(MOTIVO_FALLO_DE_HOOK)
            if tipo == "Stop":
                estado.libro.cierres_impedidos += 1
                return bloquear_cierre(MOTIVO_FALLO_DE_HOOK)
            return permitir()

    return envuelto


# --------------------------------------------------------------------------- hooks del caso


class HooksDelCaso:
    """Los hooks de un caso, por agente, sobre el mismo estado y registro de eventos (R5)."""

    def __init__(
        self,
        estado: EstadoCaso,
        eventos: RegistroEventos,
        entorno: Mapping[str, str] | None = None,
    ) -> None:
        self.estado = estado
        self.eventos = eventos
        self.entorno = entorno

    # -------------------------------------------------------------- construcción

    def _matcher(
        self, herramienta: str, hook: Hook, tipo: str, frente: Frente | None
    ) -> HookMatcher:
        envuelto = fallar_cerrado(hook, tipo, self.estado, self.eventos, frente)
        return HookMatcher(matcher=herramienta, hooks=[envuelto])

    def subagente(self, frente: Frente) -> dict[str, list[HookMatcher]]:
        """Los hooks del subagente de un frente (los que vigilan su propia herramienta)."""
        herramienta = FRENTES[frente].herramienta_completa
        if frente is Frente.REGISTRO:
            return {
                "PostToolUse": [
                    self._matcher(herramienta, self._registro_posterior, "PostToolUse", frente)
                ],
                "PostToolUseFailure": [
                    self._matcher(
                        herramienta,
                        self._fallo_de_herramienta(frente),
                        "PostToolUseFailure",
                        frente,
                    )
                ],
            }
        return {}

    def coordinador(self) -> dict[str, list[HookMatcher]]:
        """Los hooks del coordinador."""
        return {}

    # -------------------------------------------------------------- registro (FR-001)

    async def _registro_posterior(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """Guarda la identificación que `derivar_comercio` saca de una respuesta válida."""
        resultado, _ = leer_respuesta(entrada.get("tool_response"))
        if resultado is not None:
            self.estado.registrar_identificacion(resultado)
        return permitir()

    # -------------------------------------------------------------- errores de herramienta

    def _fallo_de_herramienta(self, frente: Frente) -> Hook:
        """`PostToolUseFailure`: un error estructurado de la pasarela no cuenta como consulta."""

        async def hook(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
            _, error = leer_respuesta(entrada.get("error"), es_error=True)
            tipo = error.get("tipo") if isinstance(error, dict) else None
            etiqueta = tipo if isinstance(tipo, str) else "desconocido"
            self.eventos.registrar(
                TIPO_CONSULTA_FALLIDA,
                frente,
                f"La herramienta devolvió un error estructurado ({etiqueta}); no cuenta.",
            )
            return permitir()

        return hook
