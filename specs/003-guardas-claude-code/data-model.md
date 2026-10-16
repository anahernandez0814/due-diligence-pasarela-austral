# Data Model: Guardas de Claude Code

No hay base de datos. Las entidades son las piezas de configuración y los conceptos que
usan los hooks. Detalle de cada decisión en [research.md](research.md).

## Guarda

Script de `.claude/hooks/` registrado en `.claude/settings.json`.

| Campo | Valores |
|-------|---------|
| `nombre` | `guarda_secretos`, `guarda_datos`, `guarda_spec_previa`, `formatear_python` |
| `evento` | `PreToolUse` (las tres guardas) o `PostToolUse` (formato) |
| `matcher` | expresión regular sobre `tool_name` ([contracts/settings-json.md](contracts/settings-json.md)) |
| `efecto` | bloquear (código de salida 2 y motivo en stderr), permitir (salida 0) o actuar (formatear) |
| `fallo` | cerrado para las tres guardas (excepción propia → salida 2); abierto para el formato (FR-020, FR-015) |
| `timeout` | 10 s las guardas y 30 s el formato (R3) |

Reglas:

- Una guarda solo lee el JSON de stdin, el sistema de archivos y la rama de git. No
  escribe archivos, salvo `formatear_python`, que reescribe el `.py` editado con ruff.
- El mensaje de bloqueo nombra la guarda, el tipo de problema y el archivo o la
  herramienta, en español, y nunca repite un valor sensible (FR-008, FR-023).

## Archivo de secretos

Ruta, normalizada a `/` y relativa a la raíz del repositorio, que cumple alguna de estas
condiciones (FR-001):

- el nombre es `.env`;
- el nombre empieza por `.env.` y no es `.env.example`;
- el nombre termina en `.key`;
- algún componente del directorio es `secrets`.

Las mayúsculas no cuentan: `.ENV` y `Secrets/` también son archivos de secretos, porque
Windows y macOS no distinguen mayúsculas en las rutas.

## Patrón sensible

Definiciones normativas en [contracts/detector-datos.md](contracts/detector-datos.md).

| Tipo | Reconocimiento | Exclusión principal |
|------|----------------|---------------------|
| `tarjeta` | 13–19 dígitos, separados o no por espacio o guion, prefijo 2–6, Luhn válido | marcas de tiempo en ms (empiezan por 1), números pegados a letras o a otros dígitos |
| `nit` | 9 dígitos (con o sin puntos) + guion + DV válido de la DIAN; o tras "NIT" sin guion | DV inválido |
| `cedula` | 6–10 dígitos (con o sin puntos) a corta distancia de una palabra de contexto | sin palabra de contexto; precedido de `$` |
| `credencial` | prefijos de GitHub, Anthropic, AWS y bloques de clave privada con su longitud mínima | prefijo sin la longitud mínima |

Un hallazgo es `(tipo, línea)`; nunca guarda el valor.

## Código protegido

Ruta relativa a la raíz que cumple alguna de estas condiciones (FR-011, R7):

| Protegido | Exento |
|-----------|--------|
| `src/**/*.py`, salvo `test_*.py` | `docs/**`, `specs/**`, `.specify/**` |
| `.claude/hooks/**`, salvo `test_*.py` | el resto de `.claude/**` (`.md` y `.json`) |
| `.claude/settings.json` | `**/test_*.py` |
| `.mcp.json` | cualquier otra ruta no listada |
| `plugins/**` y `.claude-plugin/**` (plugin y marketplace de #13) | |

## Ticket en curso

Se deduce en cada invocación, sin estado guardado:

```text
rama = git branch --show-current
  └─ no cumple ^(\d{3})-  → sin ticket: bloquea todo código protegido
  └─ NNN
       └─ carpetas specs/NNN-*/
            ├─ 0 o más de 1 → bloquea (falta la carpeta o el ticket es ambiguo)
            └─ exactamente 1 → faltan spec.md, plan.md o tasks.md → bloquea nombrando cuáles
                               están los tres → permite
```

En `main`, y con HEAD separado (rama vacía), también se bloquea.

## Regla por ruta

Archivo de `.claude/rules/` con frontmatter YAML:

| Archivo | `paths` |
|---------|---------|
| `tests.md` | `**/test_*.py` |
| `herramientas-mcp.md` | `src/servidor_mcp/**/*.py` |

## Entrada de denegación

Cadena de `permissions.deny` en `.claude/settings.json`. Tres familias: secretos para
las herramientas de archivo, comandos de Bash (y de PowerShell, si se admiten) sobre
secretos, y herramientas del MCP de GitHub por nombre exacto. Lista completa en
[contracts/settings-json.md](contracts/settings-json.md).
