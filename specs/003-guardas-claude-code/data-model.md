# Data Model: Guardas de Claude Code

No hay base de datos. Las entidades son las piezas de configuración y los conceptos que
usan los hooks. Detalle de cada decisión en [research.md](research.md).

## Guarda

Script de `.claude/hooks/` registrado en `.claude/settings.json`.

| Campo | Valores |
|-------|---------|
| `nombre` | `guarda_secretos`, `guarda_datos`, `guarda_spec_previa`, `guarda_mcp_github`, `formatear_python` |
| `evento` | `PreToolUse` (las cuatro guardas) o `PostToolUse` (formato) |
| `matcher` | lista de nombres exactos de herramienta separados por `\|`, no una expresión regular (R3; [contracts/settings-json.md](contracts/settings-json.md)) |
| `efecto` | bloquear (código de salida 2 y motivo en stderr), permitir (salida 0) o actuar (formatear) |
| `fallo` | cerrado para las cuatro guardas (excepción propia → salida 2, más `onFailure: "block"`); abierto para el formato (FR-020, FR-015, R2) |
| `timeout` | 10 s las guardas y 30 s el formato (R1) |

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

Ruta relativa a la raíz que cumple alguna de estas condiciones (FR-011, R7, R14):

| Protegido | Exento |
|-----------|--------|
| `src/**/*.py`, salvo `test_*.py` | `docs/**`, `specs/**`, `.specify/**` |
| `.claude/hooks/**`, salvo `test_*.py` | el resto de `.claude/**` (`.md` y `.json`) |
| `.claude/settings.json` | `**/test_*.py` |
| `.claude/settings.local.json` (R14) | cualquier otra ruta no listada |
| `.mcp.json` | |
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

Cadena de `permissions.deny` en `.claude/settings.json`. 64 entradas, en tres familias:

- **Herramientas de archivo** (17): secretos más `Edit(./.claude/settings.local.json)`.
- **Bash** (40): lectores y copiadores sobre secretos, sin `grep` (R6).
- **MCP de GitHub** (7): por nombre exacto.

No hay reglas de PowerShell: la herramienta queda apagada por las denegaciones de Bash
(R5). Lista completa en [contracts/settings-json.md](contracts/settings-json.md).

## Método permitido del Project

`guarda_mcp_github` admite en `mcp__github__projects_write` un único valor de
`tool_input.method`: `update_project_item`. Los otros nueve métodos del esquema se
bloquean (FR-024, R4).
