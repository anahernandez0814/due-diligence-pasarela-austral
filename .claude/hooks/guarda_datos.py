"""Compatibilidad: ejecuta la guarda de datos con forma real del plugin.

La guarda vive en `plugins/guardas-y-revision/hooks/guarda_datos.py`, su única fuente. Este
archivo sirve a las sesiones o versiones de Claude Code que no recargan la configuración y
siguen llamando a la ruta antigua (la 2.1.303 recarga `settings.json` en caliente).
`.claude/settings.json` no registra este archivo.

No tiene lógica: no importa el detector ni arma mensajes, solo ejecuta el archivo del plugin.
Falla cerrado: si no puede ejecutarlo, o si el archivo termina sin decidir, sale con 2 y la
acción se bloquea.
"""

import runpy
import sys
from pathlib import Path

GUARDA = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "guardas-y-revision"
    / "hooks"
    / "guarda_datos.py"
)

if __name__ == "__main__":
    try:
        # Sin PYTHONUTF8, Windows escribe stderr en cp1252 y el mensaje llegaría roto.
        sys.stderr.reconfigure(encoding="utf-8")
        sys.path.insert(0, str(GUARDA.parent))
        runpy.run_path(str(GUARDA), run_name="__main__")
    except SystemExit:
        raise
    except BaseException as error:  # noqa: BLE001 - fallo cerrado
        print(
            f"[guarda_datos] No se pudo ejecutar la guarda del plugin ({type(error).__name__}); "
            "la acción se bloquea por precaución.",
            file=sys.stderr,
        )
        sys.exit(2)
    print(
        "[guarda_datos] La guarda del plugin terminó sin decidir; la acción se bloquea.",
        file=sys.stderr,
    )
    sys.exit(2)
