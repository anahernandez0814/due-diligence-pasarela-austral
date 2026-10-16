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
| Codificación | UTF-8 en stdin, stdout y stderr, independiente del entorno: `comun.ejecutar` reconfigura los tres flujos antes de leer la entrada, sin depender de `PYTHONUTF8` ni `PYTHONIOENCODING` (revisión de la parada C) |
| Valores sensibles | nunca aparecen en stderr ni en stdout |
| Dependencias | solo la biblioteca estándar; `formatear_python` también usa ruff |
| PowerShell | la herramienta está desactivada en la sesión (research R5); las guardas la tratan igual que Bash como respaldo, y esa rama se prueba con JSON por stdin |

Módulos compartidos:

- `comun.py`: lectura de stdin, raíz, normalización de rutas, división de comandos
  (`shlex` con `punctuation_chars`), envoltorio de fallo cerrado, función `bloquear()` y
  el **extractor de texto ejecutable** que comparten `guarda_secretos` y
  `guarda_spec_previa` (research R9, decisión 1; R10). Para un comando, el extractor
  devuelve:
  - los **comandos interiores** de shells y heredocs que alimentan a `bash` o `sh`, que
    cada guarda analiza con sus mismas reglas, hasta 3 niveles de anidamiento;
  - los **textos de código** de intérpretes de lenguaje, que cada guarda revisa como
    texto;
  - una marca de **anidamiento excesivo** (más de 3 niveles), que las dos guardas
    bloquean por precaución.

  Si un comando interior no se puede analizar (`shlex` falla), lo devuelve como texto de
  código.

  **Reglas del extractor** (correcciones de la revisión de la parada B):

  | Construcción | Resultado |
  |--------------|-----------|
  | `bash -c`, `sh -c`, `eval`, `powershell`/`pwsh -Command`/`-c` | comando interior, nivel + 1 |
  | `cmd /c`, `cmd //c`, `cmd /k`, `cmd //k` (Git Bash en Windows) | comando interior, nivel + 1, analizado sin `\` como escape, como PowerShell |
  | sustitución de comandos `$(…)`, también dentro de comillas dobles (no dentro de simples), y comillas invertidas `` `…` `` | comando interior, nivel + 1, con las mismas reglas que `bash -c` |
  | heredoc (`<<FIN`, `<<-FIN`, `<<'FIN'`) que alimenta a `bash` o `sh` | su cuerpo es un comando interior |
  | heredoc que alimenta a un intérprete | su cuerpo es texto de código |
  | herestring (`<<<`) con un intérprete | la palabra siguiente es texto de código |
  | herestring con `bash` o `sh` | la palabra siguiente es un comando interior |
  | `python`/`py`/`node`/`perl`/`ruby` con `-c`/`-e`… | el argumento es texto de código |
  | **tubería**: una etapa es un intérprete sin `-c`/`-e` y sin script (o con `-` como script) | las palabras y los cuerpos de heredoc de las etapas anteriores de esa tubería son texto de código |
  | **tubería**: una etapa es `bash` o `sh` sin `-c` y sin script | las palabras y los cuerpos de heredoc de las etapas anteriores son un comando interior |

  - **Heredocs**: el operador `<<` solo cuenta si no forma parte de `<<<`
    (`(?<!<)<<(?!<)`). Un heredoc cuyo delimitador de cierre no aparece no se quita: sus
    líneas se analizan como comandos.
  - **Heredocs y comillas** (revisión de la parada B2):
    - Un `<<` dentro de comillas simples o dobles es texto literal y no abre un heredoc
      (`echo "<<X"`). Tampoco lo abre dentro de un comentario `#`.
    - Dentro de `$(…)` empieza un contexto nuevo, aunque `$(…)` vaya entre comillas
      dobles: ahí sí puede haber heredocs, como en el commit
      `git commit -m "$(cat <<'EOF' … EOF)"`.
    - El cuerpo empieza tras el primer salto de línea que no está entre comillas.
  - **El cuerpo viaja con su comando**: el texto de una sustitución `$(…)` y el de una
    palabra que se analiza como comando interior o como código (`bash -c "…"`) llevan
    sus heredocs completos, con el cuerpo y la línea de cierre. Así, al analizar
    `$(python3 <<'EOF' … EOF)`, el cuerpo es texto de código, y en `$(cat <<'EOF' … EOF)`
    el comando interior es `cat`, sin código.
  - **Marcas sin cuerpo**: una marca interna de heredoc sin su cuerpo es un error de
    análisis (`ValueError`, nunca `IndexError`); en un comando interior se aplica la
    vuelta a texto.
  - **Comentarios** (revisión de la parada B3): el recorrido quita los comentarios y
    `shlex` no los trata (`commenters = ""`). Regla de bash:
    - `#` abre un comentario solo al principio de una palabra: al principio del texto o
      de una línea, después de un espacio o un tabulador, o después de `;`, `&`, `|`,
      `(` o `)`. Siempre fuera de comillas.
    - El comentario llega hasta el salto de línea, sin incluirlo; el salto sigue
      separando comandos.
    - En mitad de una palabra (`a#b`), en `${#var}` y en `$#` no es comentario.
    - En PowerShell, como respaldo, `#` al principio de una palabra cuenta igual que en
      bash. Los bloques `<# … #>` quedan como límite declarado.
  - **Límite declarado, comillas ANSI-C** (`$'…'`): no se reconocen. Si `shlex` falla
    con ellas, la guarda bloquea por precaución: es un falso positivo, nunca un hueco.
  - **Delante del programa** se saltan:
    - las asignaciones `NOMBRE=valor`;
    - los envoltorios `env [opciones] [NOMBRE=valor…]`, `exec`, `command`, `nohup`,
      `time`, `nice [-n N]` y `timeout [opciones] N`.
  - **`uv run`**: se saltan sus opciones y se toma como programa la primera palabra que
    sea un intérprete o un shell. No se usa una lista fija de opciones con valor.
- **Rutas de Git Bash** (`normalizar_ruta`): en Windows, una ruta `/<letra>/…` se
  convierte en `<LETRA>:/…` antes de normalizar. Por ejemplo,
  `/d/AIReadyOrquestador/src/due_diligence/x.py` queda `src/due_diligence/x.py` con la
  raíz `D:\AIReadyOrquestador`.
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

**Texto ejecutable (R9, decisión 1)**: con el extractor de `comun.py`, en Bash y en
PowerShell (como respaldo).

| Construcción | Cómo se revisa |
|--------------|----------------|
| `bash -c`, `sh -c`, `eval`, `powershell`/`pwsh` con `-Command` o `-c`, y heredoc que alimenta a `bash` o `sh` | el comando interior se analiza con **todas las reglas de esta guarda**: rutas, exclusión del patrón de búsqueda y raíz recursiva; hasta 3 niveles |
| `python` con versión opcional (`python3`, `python3.12`) con `-c` | el argumento, como texto |
| `py` con opciones de versión opcionales (`-3`, `-3.12`) y `-c` | el argumento, como texto |
| `node` con `-e`, `--eval`, `-p` o `--print` | el argumento, como texto |
| `perl` con `-e` o `-E`; `ruby` con `-e` | el argumento, como texto |
| heredoc que alimenta a uno de esos intérpretes (`python - <<'FIN'`) | el cuerpo, como texto |

- Las demás construcciones del extractor (sustitución de comandos, comillas invertidas,
  tuberías hacia un intérprete o un shell, herestrings y `cmd /c`) siguen las reglas de
  la interfaz común: los comandos interiores, con todas las reglas de esta guarda; los
  textos de código, como texto.
- Todo lo anterior vale también detrás de `uv run`, de las asignaciones `NOMBRE=valor` y
  de los envoltorios `env`, `exec`, `command`, `nohup`, `time`, `nice` y `timeout`.
- Un comando interior que `shlex` no puede analizar se revisa como texto.
- Más de 3 niveles de anidamiento se bloquean por precaución.
- **Heredocs (acotación confirmada, D1)**: un heredoc que alimenta a otro comando
  (`git commit -F - <<…`, `cat > archivo <<…`) no se revisa como código.
- **Patrón de nombres en el texto**:
  - `.env` sin una letra, un dígito ni `_` detrás. Puede seguir `.<sufijo>`, salvo
    `.env.example`.
  - `<nombre>.key` seguido de comilla, espacio o fin de texto.
  - `secrets/` o `secrets\`.
  - Siempre sin una letra, un dígito, `.`, `_` ni `-` pegado delante.
- **No coinciden**: `os.environ`, `.environment`, `x.keys()`, `obj.key)` ni
  `secrets.token_hex`.

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
- `[guarda_secretos] Comando bloqueado por precaución: tiene más de 3 niveles de shells anidados.`

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
| Bash, PowerShell | `command` completo, heredocs incluidos (también los que alimentan a `git commit` o a `cat > archivo`) |
| `mcp__github__*` del matcher | todos los valores de texto de `tool_input`, recorridos de forma recursiva |

Bloquea si el detector devuelve algún hallazgo. Mensaje:

- `[guarda_datos] Dato con forma real bloqueado: <tipo> en <archivo o herramienta>, línea <n>. Usa identificadores ficticios (por ejemplo CO-TV-0001) o genera el valor en la prueba.`

Si hay varios hallazgos, se listan los tipos y las líneas, separados por `;`. No hay
lista de valores permitidos ni forma de saltarse la guarda (spec, Assumptions).

## `guarda_spec_previa.py` (FR-009 a FR-013, R7, R10)

Rutas que revisa:

- Write y Edit: `file_path`. NotebookEdit: `notebook_path`.
- Bash y PowerShell:
  - los destinos de escritura reconocibles de R10, incluido el de `cat > archivo <<…`;
  - borrar, restaurar o mover también es modificar (revisión de la parada D): las
    palabras que no son opciones de `rm`, `unlink` y `git rm`; las rutas de
    `git checkout … -- <rutas>` y de `git restore <rutas>` (con o sin `--source`; un
    `git checkout <rama>` sin `--` no cuenta); las fuentes de `mv`, además del destino; y
    en PowerShell, como respaldo, `Remove-Item`, `del`, `erase`, `rd`, `ri` y las fuentes
    de `Move-Item`. Residuales declarados: `git apply`, `patch`, `git reset` y
    `git stash`;
  - con el extractor de `comun.py`:
    - los comandos interiores de shells y heredocs se analizan con estas mismas reglas,
      hasta 3 niveles;
    - en el código en línea de `python`, `node`, `perl` y `ruby` se buscan como texto
      nombres de código protegido.
- **Código protegido en el texto (U4 de la tercera pasada)**:
  - cuenta una **ruta**, con `/`, `\` o `\\` como separador (la doble barra es como se
    escribe `\` dentro de un literal de Python) y opcionalmente `./`, `.\` o `.\\`
    delante, que coincida con la lista del data-model: `src/…/*.py`,
    `.claude/hooks/…`, `.claude/settings.json`, `.claude/settings.local.json`,
    `.mcp.json`, `plugins/…` y `.claude-plugin/…`;
  - delante de la ruta no puede haber una letra, un dígito, `_`, `.` ni `-` pegados;
  - una ruta cuyo nombre de archivo es `test_*.py` no cuenta;
  - un nombre de módulo sin ruta (`import due_diligence`, `due_diligence.config`) no
    cuenta.
  - Ejemplos en una rama sin documentos:
    - se bloquean `open('src/due_diligence/x.py','w')` y `'.\\src\\x.py'`;
    - se permiten `import due_diligence` y `open('src/due_diligence/test_x.py')`.
- No se distingue entre lectura y escritura: el bloqueo solo depende de que falten
  documentos o de que la rama no sea de un ticket. En la rama de un ticket con spec, plan
  y tareas, `python -c` y `bash -c "echo > src/x.py"` se permiten.
- Más de 3 niveles de anidamiento se bloquean por precaución.

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
| Más de 3 niveles de shells anidados (en cualquier rama) | `[guarda_spec_previa] Comando bloqueado por precaución: tiene más de 3 niveles de shells anidados.` |

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
