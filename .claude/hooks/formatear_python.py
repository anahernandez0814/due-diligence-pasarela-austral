"""Formato con ruff tras cada edición: PostToolUse sobre Write y Edit (FR-014, FR-015, R12).

Si `tool_input.file_path` es un `.py` que existe, ejecuta, con la raíz como directorio
de trabajo:

    uv run --project <raíz> --frozen --quiet ruff format --force-exclude <archivo>

- `uv run --project` usa el ruff del `uv.lock`, el mismo de `ruff format --check`, venga
  de donde venga el cwd de la sesión.
- `--frozen` evita que un hook reescriba `uv.lock`.
- `--force-exclude` respeta el `extend-exclude` de `pyproject.toml` con rutas explícitas.

El éxito se decide solo por el código de salida: un archivo excluido escribe "No Python
files found" con salida 0, y no es un error. Si ruff falla, o faltan uv o ruff, la
edición se conserva y se informa con `hookSpecificOutput.additionalContext`. Nunca
bloquea: siempre sale con 0.

Contrato: specs/003-guardas-claude-code/contracts/guardas.md.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import comun

NOMBRE = "formatear_python"
TIEMPO_MAXIMO = 25  # segundos; el hook tiene 30


def comando(raiz: Path, archivo: str) -> list[str]:
    return [
        "uv", "run", "--project", str(raiz), "--frozen", "--quiet",
        "ruff", "format", "--force-exclude", archivo,
    ]  # fmt: skip


def formatear(entrada: dict) -> str | None:
    """Formatea el archivo de la entrada. Devuelve None si no hay nada que informar, o
    el motivo por el que no se pudo formatear."""
    datos = entrada.get("tool_input")
    ruta = datos.get("file_path") if isinstance(datos, dict) else None
    if not isinstance(ruta, str) or not ruta.lower().endswith(".py"):
        return None
    raiz = comun.raiz(entrada)
    cwd = comun.cwd(entrada, raiz)
    archivo = ruta if os.path.isabs(ruta) else os.path.join(cwd, ruta)
    if not os.path.isfile(archivo):
        return None
    mostrar = comun.normalizar_ruta(ruta, raiz, cwd)
    try:
        resultado = subprocess.run(
            comando(raiz, archivo),
            cwd=raiz,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIEMPO_MAXIMO,
        )
    except FileNotFoundError:
        return f"No se pudo formatear {mostrar}: no se encontró uv."
    except subprocess.TimeoutExpired:
        return f"No se pudo formatear {mostrar}: ruff tardó más de {TIEMPO_MAXIMO} s."
    if resultado.returncode == 0:
        return None
    lineas = (resultado.stderr + "\n" + resultado.stdout).splitlines()
    primera = next((linea.strip() for linea in lineas if linea.strip()), "")
    primera = primera or f"terminó con el código {resultado.returncode}"
    return f"No se pudo formatear {mostrar}: {primera.rstrip('.')}."


def informar(mensaje: str) -> None:
    salida = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"[{NOMBRE}] {mensaje}",
        }
    }
    print(json.dumps(salida, ensure_ascii=False))


def main() -> None:
    try:
        comun.flujos_utf8()
        motivo = formatear(comun.leer_entrada())
    except Exception as error:  # noqa: BLE001 - el formato nunca bloquea (FR-015)
        motivo = f"No se pudo formatear: error propio ({type(error).__name__})."
    if motivo:
        informar(motivo)
    sys.exit(0)


if __name__ == "__main__":
    main()
