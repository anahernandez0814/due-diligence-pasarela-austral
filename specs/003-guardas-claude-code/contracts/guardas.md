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

**Texto ejecutable (R9, decisión 1)**: además de las rutas, en Bash y en PowerShell
(como respaldo) se revisa **como texto**, buscando nombres de archivos de secretos:

| Construcción | Texto revisado |
|--------------|----------------|
| `python`, `python3`, `py`, `node`, `ruby` o `perl` con `-c` o `-e`, también detrás de `uv run [opciones]` | el argumento de `-c` o `-e` |
| `bash -c` y `sh -c` | el argumento de `-c` |
| `powershell` y `pwsh` con `-Command` o `-c` | el argumento |
| `eval` | todos sus argumentos |
| heredoc (`<<`, `<<-`, `<<'FIN'`) cuyo comando es uno de los anteriores | el cuerpo del heredoc |

- Un heredoc que alimenta a otro comando (`git commit -F - <<…`, `cat > archivo <<…`) no
  se revisa como código.
- Patrón de nombres en el texto:
  - `.env` o `.env.<sufijo>`, salvo `.env.example`;
  - `<nombre>.key` seguido de comilla, espacio o fin de texto;
  - `secrets/` o `secrets\`.
  - Siempre sin una letra, un dígito, `.`, `_` o `-` pegado delante.
- No coinciden: `x.keys()`, `obj.key)` ni `secrets.token_hex`.

**Búsquedas recursivas (R9, decisión 2)**: `grep -r`/`-R`/`--recursive`/`-d recurse`,
`rg` con `-u`/`-uu`/`--no-ignore`/`--hidden`, `find` con `-exec`/`-execdir`/`| xargs` y un
lector, y `Get-ChildItem -Recurse` (o `gci`, `ls`, `dir`) con tubería a `Get-Content` o
`Select-String`.

- La raíz son los argumentos de ruta, o `.` si no hay ninguno, resueltos contra el `cwd`
  del JSON.
- Se recorre con `os.walk` podando solo `.git`, y se para en el primer archivo de
  secretos.
- Bloquea solo si alguna raíz contiene archivos de secretos.
- Ejemplos: `grep -rn ".env" src/` se permite; `grep -r TOKEN .` se bloquea, porque la
  raíz tiene `.env`.

Bloquea si:

- alguna ruta es un archivo de secretos (data-model);
- algún texto ejecutable nombra un archivo de secretos;
- una búsqueda recursiva tiene una raíz que contiene archivos de secretos.

Mensajes:

- `[guarda_secretos] Acceso bloqueado a un archivo de secretos (<ruta>) con <herramienta>. Usa .env.example para ver las variables.`
- `[guarda_secretos] Código en línea bloqueado: nombra un archivo de secretos (<construcción>). Usa .env.example para ver las variables.`
- `[guarda_secretos] Búsqueda recursiva bloqueada: <raíz> contiene archivos de secretos. Busca en una carpeta sin secretos o usa la herramienta Grep, rg o git grep.`

Permite:

- `.env.example`;
- la herramienta Grep con un patrón que contiene `.env`;
- `grep -n .env README.md`, `grep -rn ".env" src/` y `git grep ".env"`;
- `python -c` sin nombres de secretos y `git commit -m "protege .env"`;
- cualquier ruta que no sea de secretos.

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

> Alcance actual: pese al nombre, hoy solo limita `projects_write`. El nombre se mantiene
> por si otro ticket le añade límites a más herramientas del MCP de GitHub; cada
> herramienta nueva necesitaría su matcher y su test.

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
