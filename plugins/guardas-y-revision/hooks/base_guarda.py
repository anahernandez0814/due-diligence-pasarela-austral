"""Piezas comunes de la guarda: entrada del hook, rutas, bloqueo y fallo cerrado.

- Lectura del JSON de stdin, raíz del proyecto y normalización de rutas.
- Bloqueo con código de salida 2 y envoltorio de fallo cerrado.

Solo usa la biblioteca estándar, para que el plugin no dependa de nada fuera de su carpeta.
"""

import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, TextIO

# --- Entrada y rutas ----------------------------------------------------------------


def leer_entrada(flujo: TextIO | None = None) -> dict:
    """Lee el JSON del hook. Lanza ValueError si no es un objeto JSON."""
    texto = (flujo or sys.stdin).read()
    datos = json.loads(texto)
    if not isinstance(datos, dict):
        raise ValueError("la entrada del hook no es un objeto JSON")
    return datos


def raiz(entrada: dict) -> Path:
    """Raíz del proyecto: CLAUDE_PROJECT_DIR o, si falta, el cwd de la entrada."""
    proyecto = os.environ.get("CLAUDE_PROJECT_DIR")
    if proyecto:
        return Path(proyecto)
    return Path(entrada.get("cwd") or os.getcwd())


def cwd(entrada: dict, base: Path) -> Path:
    """Directorio de trabajo del comando (sigue los `cd` de Claude)."""
    return Path(entrada.get("cwd") or base)


def _partes(ruta: str) -> list[str]:
    return [p for p in ruta.replace("\\", "/").split("/") if p not in ("", ".")]


_RUTA_GIT_BASH = re.compile(r"^/([A-Za-z])(/|$)")


def normalizar_ruta(ruta: str, base: Path, cwd: Path | None = None) -> str:
    """Ruta con `/`, relativa a `base` si está dentro; si no, absoluta.

    Las mayúsculas no cuentan al comparar con la raíz, porque Windows y macOS no las
    distinguen en las rutas. En Windows, una ruta de Git Bash `/<letra>/…` se convierte
    en `<LETRA>:/…`.
    """
    texto = ruta.replace("\\", "/")
    if os.name == "nt":
        texto = _RUTA_GIT_BASH.sub(lambda m: m.group(1).upper() + ":/", texto)
    if not os.path.isabs(texto) and not re.match(r"^[A-Za-z]:/", texto):
        texto = str(cwd or base).replace("\\", "/") + "/" + texto
    absoluta = os.path.normpath(texto).replace("\\", "/")
    raiz_partes = _partes(os.path.normpath(str(base)))
    partes = _partes(absoluta)
    if [p.casefold() for p in partes[: len(raiz_partes)]] == [p.casefold() for p in raiz_partes]:
        return "/".join(partes[len(raiz_partes) :])
    return absoluta


# --- Bloqueo y fallo cerrado --------------------------------------------------------


def bloquear(guarda: str, mensaje: str) -> NoReturn:
    """Bloquea la acción: una sola línea en stderr y código de salida 2."""
    linea = " ".join(mensaje.split())
    print(f"[{guarda}] {linea}", file=sys.stderr)
    sys.exit(2)


def flujos_utf8() -> None:
    """UTF-8 en stdin, stdout y stderr, independiente de PYTHONUTF8 y PYTHONIOENCODING.

    Sin esas variables, Python en Windows usa cp1252 en las tuberías. Los flujos que no
    se pueden reconfigurar (los de las pruebas) se dejan como están.
    """
    for flujo in (sys.stdin, sys.stdout, sys.stderr):
        reconfigurar = getattr(flujo, "reconfigure", None)
        if reconfigurar is not None:
            reconfigurar(encoding="utf-8")


def ejecutar(guarda: str, revisar: Callable[[dict], None]) -> NoReturn:
    """Lee la entrada y ejecuta la guarda; ante cualquier error propio, bloquea."""
    try:
        flujos_utf8()
        revisar(leer_entrada())
    except SystemExit:
        raise
    except BaseException as error:  # noqa: BLE001 - fallo cerrado
        bloquear(
            guarda,
            f"La guarda falló ({type(error).__name__}); la acción se bloquea por precaución.",
        )
    sys.exit(0)
