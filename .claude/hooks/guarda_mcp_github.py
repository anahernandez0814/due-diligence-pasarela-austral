"""Guarda de `projects_write` del MCP de GitHub: PreToolUse (FR-024, FR-020, R4).

`mcp__github__projects_write` agrupa diez métodos; el proyecto solo necesita
`update_project_item`, con el que `/siguiente-ticket` y `/abrir-pr` mueven la tarjeta.
Cualquier otro método, un `method` ausente o que no es texto, y un `tool_input` que no es
un objeto se bloquean.

Pese al nombre, hoy solo limita `projects_write`; si otro ticket le añade herramientas,
cada una necesita su matcher y su test.

Contrato: specs/003-guardas-claude-code/contracts/guardas.md.
"""

import comun

GUARDA = "guarda_mcp_github"
PERMITIDO = "update_project_item"

MENSAJE = (
    "Método '{metodo}' de projects_write bloqueado: el proyecto solo actualiza ítems del "
    "Project (update_project_item)."
)


def motivo(entrada: dict) -> str | None:
    """Motivo del bloqueo, o None si el método es exactamente `update_project_item`."""
    datos = entrada.get("tool_input")
    metodo = datos.get("method") if isinstance(datos, dict) else None
    if metodo == PERMITIDO:
        return None
    return MENSAJE.format(metodo=metodo if isinstance(metodo, str) else "(ausente)")


def revisar(entrada: dict) -> None:
    motivo_ = motivo(entrada)
    if motivo_:
        comun.bloquear(GUARDA, motivo_)


if __name__ == "__main__":
    comun.ejecutar(GUARDA, revisar)
