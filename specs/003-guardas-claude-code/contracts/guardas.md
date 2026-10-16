# Contrato: guardas de `.claude/hooks/`

Interfaz común y comportamiento de cada hook. Las entidades están en
[data-model.md](../data-model.md) y las decisiones en [research.md](../research.md).

## Interfaz común

| Aspecto | Contrato |
|---------|----------|
| Invocación | `uv run … <script>.py`, en forma exec ([settings-json.md](settings-json.md)) |
| Entrada | JSON en stdin con `hook_event_name`, `tool_name`, `tool_input` y `cwd` |
| Raíz | `CLAUDE_PROJECT_DIR`, o `cwd` si falta. Las rutas se resuelven contra ella y se normalizan a `/` |
| Permitir | salida 0, stdout vacío |
| Bloquear | salida 2 y una sola línea en stderr: `[<guarda>] <motivo>. <qué hacer>.` |
| Error propio | salida 2: `[<guarda>] La guarda falló (<TipoDeError>); la acción se bloquea por precaución.` |
| Idioma | español |
| Valores sensibles | nunca aparecen en stderr ni en stdout |
| Dependencias | solo la biblioteca estándar; `formatear_python` también usa ruff |
| PowerShell | la herramienta está desactivada en la sesión (research R5); las guardas la tratan igual que Bash como respaldo, y esa rama se prueba con JSON por stdin |

Módulos compartidos:

- `comun.py`: lectura de stdin, raíz, normalización de rutas, división de comandos
  (`shlex` con `punctuation_chars`), envoltorio de fallo cerrado y función `bloquear()`.
- `detector_datos.py`: el detector ([detector-datos.md](detector-datos.md)).

## `guarda_secretos.py` (FR-001, FR-002, R9)

Qué revisa según la herramienta:

| Herramienta | Qué revisa |
|-------------|------------|
| Read | `file_path` |
| Write, Edit | `file_path` |
| NotebookEdit | `notebook_path` |
| Grep | `path` y `glob`; **no** `pattern`, que es el texto buscado (FR-002) |
| Glob | `pattern` y `path`, porque el patrón es de rutas |
| Bash, PowerShell | cada palabra de cada subcomando, sin comillas: rutas, destinos de redirección (`<`, `>`, `>>`) y argumentos con comodines, que se expanden contra la raíz |

En Bash y PowerShell no se revisa el patrón de búsqueda de `grep`, `egrep`, `fgrep`,
`rg`, `git grep`, `Select-String` (`-Pattern` o primer posicional) y `findstr`: es el
texto que se busca, no un archivo (FR-002). Una palabra solo cuenta como ruta si es una
ruta completa; el texto `.env` dentro de un mensaje entre comillas
(`git commit -m "protege .env"`) no bloquea.

Bloquea si:

- alguna ruta es un archivo de secretos (data-model);
- el comando es una lectura recursiva sin exclusión, según la lista de R9.

Mensajes:

- `[guarda_secretos] Acceso bloqueado a un archivo de secretos (<ruta>) con <herramienta>. Usa .env.example para ver las variables.`
- `[guarda_secretos] Búsqueda recursiva bloqueada: puede leer archivos de secretos sin nombrarlos. Usa la herramienta Grep, rg o git grep, o excluye .env.`

Permite `.env.example`, la herramienta Grep con un patrón que contiene `.env` y cualquier
ruta que no sea de secretos.

## `guarda_datos.py` (FR-004 a FR-008)

Qué revisa según la herramienta:

| Herramienta | Texto revisado |
|-------------|----------------|
| Write | `content` |
| Edit | `new_string` |
| NotebookEdit | `new_source` |
| Bash, PowerShell | `command` |
| `mcp__github__*` del matcher | todos los valores de texto de `tool_input`, recorridos de forma recursiva |

Bloquea si el detector devuelve algún hallazgo. Mensaje:

- `[guarda_datos] Dato con forma real bloqueado: <tipo> en <archivo o herramienta>, línea <n>. Usa identificadores ficticios (por ejemplo CO-TV-0001) o genera el valor en la prueba.`

Si hay varios hallazgos, se listan los tipos y las líneas, separados por `;`. No hay
lista de valores permitidos ni forma de saltarse la guarda (spec, Assumptions).

## `guarda_spec_previa.py` (FR-009 a FR-013, R7, R10)

Rutas que revisa:

- Write y Edit: `file_path`. NotebookEdit: `notebook_path`.
- Bash y PowerShell: los destinos de escritura reconocibles de R10.

Código protegido según data-model: `src/**/*.py`, `.claude/hooks/**`,
`.claude/settings.json`, `.claude/settings.local.json`, `.mcp.json`, `plugins/**` y
`.claude-plugin/**`, salvo los `test_*.py`.

Si ninguna ruta es código protegido, permite. Si alguna lo es, deduce el ticket en curso
(data-model) y bloquea si falta algo:

| Situación | Mensaje |
|-----------|---------|
| Rama `main`, sin patrón o HEAD separado | `[guarda_spec_previa] <ruta> es código protegido y la rama '<rama>' no es de un ticket (NNN-nombre). Crea la rama con /siguiente-ticket.` |
| Ninguna carpeta `specs/NNN-*` | `[guarda_spec_previa] No existe specs/NNN-*/ para la rama '<rama>'. Ejecuta /speckit-specify.` |
| Más de una carpeta | `[guarda_spec_previa] Hay varias carpetas specs/NNN-*/ (<lista>); el ticket en curso es ambiguo.` |
| Faltan documentos | `[guarda_spec_previa] Falta <lista de spec.md, plan.md, tasks.md> en specs/NNN-<nombre>/. Completa /speckit-plan o /speckit-tasks antes de escribir código.` |

La rama se lee con `git -C <raíz> branch --show-current`. Si git falla, se aplica el fallo
cerrado.

## `guarda_mcp_github.py` (FR-024, R4)

- Matcher: `mcp__github__projects_write`.
- Permite solo si `tool_input.method` es exactamente `update_project_item`.
- Bloquea cualquier otro valor, un `method` ausente o que no sea texto, y un
  `tool_input` que no sea un objeto.
- Mensaje:
  `[guarda_mcp_github] Método '<method>' de projects_write bloqueado: el proyecto solo actualiza ítems del Project (update_project_item).`
  Si `method` falta o no es texto, `<method>` se sustituye por `(ausente)`.
- Fallo cerrado como el resto (salida 2 y `onFailure: "block"`).

## `formatear_python.py` (FR-014, FR-015, R12)

- Actúa solo si `tool_input.file_path` termina en `.py` y el archivo existe.
- Ejecuta `sys.executable -m ruff format <archivo>` con la raíz como directorio de
  trabajo.
- Si funciona: salida 0 sin nada en stdout.
- Si ruff falla: salida 0 y en stdout
  `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "[formatear_python] No se pudo formatear <archivo>: <primera línea del error de ruff>."}}`.
- Nunca sale con 2 ni modifica otros archivos.
