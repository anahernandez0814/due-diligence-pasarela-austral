"""Guarda de datos con forma real y credenciales (hook PreToolUse).

Revisa con el detector el texto que se escribe, se ejecuta o se publica:

- Write: `content`. Edit: `new_string` (el texto que se reemplaza no cuenta).
  NotebookEdit: `new_source`.
- Bash y PowerShell: el comando completo, heredocs incluidos.
- Herramientas MCP (`mcp__<servidor>__<herramienta>`) que el matcher deja pasar: todos los
  valores de texto de `tool_input`, recorridos de forma recursiva. Qué herramientas llegan lo
  decide el matcher, no el nombre del servidor.

El mensaje dice el tipo y la línea de cada hallazgo, nunca el valor. No hay lista de
valores permitidos ni forma de saltarse la guarda. Ante un error propio, bloquea.
"""

from collections.abc import Iterator

import base_guarda
import detector_datos

GUARDA = "guarda_datos"

MENSAJE = (
    "Dato con forma real bloqueado: {hallazgos}. Usa valores claramente ficticios "
    "o genera el valor en la prueba."
)

_CAMPOS = {"Write": "content", "Edit": "new_string", "NotebookEdit": "new_source"}
_RUTAS = {"Write": "file_path", "Edit": "file_path", "NotebookEdit": "notebook_path"}


def _textos_anidados(valor: object, campo: str = "") -> Iterator[tuple[str, str]]:
    """`(campo, texto)` de cada valor de texto, con su posición (`comments[0].body`)."""
    if isinstance(valor, str):
        yield campo, valor
    elif isinstance(valor, dict):
        for clave, interior in valor.items():
            yield from _textos_anidados(interior, f"{campo}.{clave}" if campo else str(clave))
    elif isinstance(valor, list):
        for i, interior in enumerate(valor):
            yield from _textos_anidados(interior, f"{campo}[{i}]")


def textos(entrada: dict) -> list[tuple[str, str]]:
    """`(dónde, texto)` que se revisan: el archivo o la herramienta, y su texto."""
    herramienta = entrada.get("tool_name") or ""
    datos = entrada.get("tool_input") or {}
    if herramienta in _CAMPOS:
        texto = datos.get(_CAMPOS[herramienta])
        if not isinstance(texto, str):
            return []
        base = base_guarda.raiz(entrada)
        ruta = datos.get(_RUTAS[herramienta]) or ""
        donde = (
            base_guarda.normalizar_ruta(ruta, base, base_guarda.cwd(entrada, base))
            if ruta
            else herramienta
        )
        return [(donde, texto)]
    if herramienta in ("Bash", "PowerShell"):
        comando = datos.get("command")
        return [(herramienta, comando)] if isinstance(comando, str) else []
    if herramienta.startswith("mcp__"):
        return [(f"{herramienta} ({campo})", texto) for campo, texto in _textos_anidados(datos)]
    return []


def motivo(entrada: dict) -> str | None:
    """Motivo del bloqueo, o None si la acción se permite."""
    hallazgos = [
        f"{tipo} en {donde}, línea {linea}"
        for donde, texto in textos(entrada)
        for tipo, linea in detector_datos.buscar(texto)
    ]
    return MENSAJE.format(hallazgos="; ".join(hallazgos)) if hallazgos else None


def revisar(entrada: dict) -> None:
    motivo_ = motivo(entrada)
    if motivo_:
        base_guarda.bloquear(GUARDA, motivo_)


if __name__ == "__main__":
    base_guarda.ejecutar(GUARDA, revisar)
