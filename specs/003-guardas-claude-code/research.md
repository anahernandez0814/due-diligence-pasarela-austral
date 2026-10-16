# Research: Guardas de Claude Code

Fase 0 del plan del ticket #3. Cada entrada resuelve una incógnita del contexto técnico o
uno de los puntos (a)–(f) del analista. Las citas de Claude Code salen de la documentación
oficial consultada el 2026-10-15 (hooks: https://code.claude.com/docs/en/hooks;
permisos: https://code.claude.com/docs/en/permissions; herramientas:
https://code.claude.com/docs/en/tools-reference; reglas:
https://code.claude.com/docs/en/memory). Versión instalada: Claude Code 2.1.300.

## R1. Lenguaje de los hooks y forma de invocarlos (punto a)

- **Hallazgo**:
  - Un hook `command` sin `args` corre en un shell: `sh -c` en macOS y Linux, Git Bash en
    Windows, o PowerShell si Git Bash no está instalado. En PowerShell,
    `"$CLAUDE_PROJECT_DIR"` no se expande igual que en bash.
  - Con `args`, el hook corre en **forma exec**: Claude Code busca `command` en el `PATH`
    y lo lanza sin shell. Los marcadores como `${CLAUDE_PROJECT_DIR}` se sustituyen en
    `command` y en cada elemento de `args`. La documentación recomienda la forma exec
    para cualquier hook que use un marcador de ruta.
  - `python` no está en el `PATH` de Windows en este equipo; `uv` sí, y ya es requisito
    del proyecto (`CLAUDE.md`, `uv sync`).
  - Tiempos medidos en Windows, en caliente: `uv run --no-project` ≈ 0,5 s;
    `uv run` con proyecto ≈ 0,5–0,7 s; el Python del `.venv` directo ≈ 0,4 s.
- **Decisión**:
  - Hooks en **Python 3.12, solo con la biblioteca estándar**, salvo el de formato, que
    llama a ruff.
  - Forma exec, con `uv` como ejecutable:
    - Guardas: `command: "uv"`, `args: ["run", "--no-project", "--python", "3.12",
      "--quiet", "${CLAUDE_PROJECT_DIR}/.claude/hooks/<guarda>.py"]`. Con `--no-project`,
      `uv` no sincroniza el entorno en cada llamada, y la guarda funciona aunque el
      `.venv` no exista todavía.
    - Formato: se lanza igual que las guardas, `args: ["run", "--no-project",
      "--python", "3.12", "--quiet",
      "${CLAUDE_PROJECT_DIR}/.claude/hooks/formatear_python.py"]`, porque el script solo
      usa la biblioteca estándar (revisión de la parada E). Por dentro invoca
      `uv run --project <raíz> --frozen --quiet ruff format --force-exclude <archivo>`
      (R12): es el único `uv run --project`, y `--frozen` evita que un hook reescriba
      `uv.lock`. Necesita el grupo `dev`, donde está ruff.
  - **Entrada**: cada script lee el JSON de stdin (`tool_name`, `tool_input`, `cwd`,
    `hook_event_name`). La raíz del repositorio sale de la variable de entorno
    `CLAUDE_PROJECT_DIR` y, si falta, de `cwd`. No se usa el directorio actual del
    proceso, porque sigue los `cd` de Claude.
  - **Salida**: bloquear = código de salida **2** con el motivo en stderr, que llega a
    Claude. Permitir = salida 0 sin nada en stdout, para que siga el flujo normal de
    permisos. El formato nunca sale con 2; informa con
    `hookSpecificOutput.additionalContext` en stdout y salida 0.
  - **Timeout**: 10 s para cada guarda y 30 s para el formato. Una comprobación tarda
    0,5 s, y todos los hooks que coinciden corren en paralelo, así que se cumple SC-004
    (< 1 s).
- **Alternativas descartadas**:
  - Forma shell con `"$CLAUDE_PROJECT_DIR"`: depende del shell que haya en cada equipo
    Windows.
  - Scripts de bash o de PowerShell: ninguno de los dos funciona igual en los tres
    sistemas sin instalar nada.
  - El Python del `.venv` directo: la ruta cambia entre Windows (`Scripts/`) y Unix
    (`bin/`), y en un clon recién hecho no existe.
  - Un único script despachador para todas las guardas: ahorra procesos, pero el ticket
    #13 tiene que empaquetar la guarda de datos por separado. Al correr en paralelo, el
    tiempo total es el de la guarda más lenta, no la suma.

## R2. Fallo cerrado (FR-020)

- **Hallazgo**:
  - Un código de salida distinto de 0 y de 2 **no bloquea**: la acción sigue y el
    transcript muestra el error.
  - Un hook que agota su timeout "doesn't block the tool call".
  - Desde la v2.1.295, `"onFailure": "block"` hace que un fallo actúe como la salida 2.
    Cuenta como fallo: que el hook no arranque (por ejemplo, falta `uv`), una salida
    distinta de 0 y 2, el timeout o una salida JSON inválida.
  - Un **script inexistente no es un hook que no arranca**: `uv` sí arranca, no encuentra
    el script ("Failed to spawn") y sale con 2, así que bloquea por la salida 2, con o
    sin `onFailure` (comprobado en Q18a).
- **Decisión**: el fallo cerrado tiene dos capas.
  1. Cada guarda envuelve su lógica en un `try/except BaseException`. Ante cualquier
     excepción escribe en stderr "La guarda <nombre> falló (<tipo de error>); la acción
     se bloquea por precaución." y sale con 2.
  2. Las cuatro guardas (secretos, datos, spec previa y Project, R4) llevan
     `"onFailure": "block"`. Así se cubre lo que el script no puede atrapar: `uv`
     ausente, una salida distinta de 0 y 2 (comprobado en Q18b: un script que sale con
     1 bloquea solo por esta capa) o el timeout. Un script inexistente ya lo bloquea la
     salida 2 de `uv`.

  El formato lleva `"onFailure": "continue"` (FR-015).
- **Consecuencia aceptada**: sin `uv` en el `PATH`, la guarda de secretos bloquea todas
  las lecturas y búsquedas. El mensaje lo explica, y `uv` es requisito del proyecto.

## R3. Matchers exactos (punto b)

- **Hallazgo**:
  - Un matcher que solo contiene letras, dígitos, `_`, `-`, espacios, `,` y `|` es una
    **lista de nombres exactos**. Cualquier otro carácter lo convierte en una expresión
    regular de JavaScript sin anclar, y entonces `Edit|Write` también coincidiría con
    `NotebookEdit`.
  - Las herramientas MCP se llaman `mcp__<servidor>__<herramienta>`.
  - `PowerShell` es una herramienta propia de Claude Code, con los mismos campos que
    `Bash` (`command`). La documentación avisa de que "matching Bash alone is not enough".
  - `MultiEdit` no aparece en la referencia de herramientas, así que no se incluye.
- **Decisión**: listas exactas separadas por `|`, sin caracteres de expresión regular:

  | Hook | Evento | Matcher |
  |------|--------|---------|
  | `guarda_secretos` | PreToolUse | `Read\|Write\|Edit\|NotebookEdit\|Grep\|Glob\|Bash\|PowerShell` |
  | `guarda_datos` | PreToolUse | `Write\|Edit\|NotebookEdit\|Bash\|PowerShell\|mcp__github__add_issue_comment\|mcp__github__update_issue_comment\|mcp__github__create_pull_request\|mcp__github__update_pull_request\|mcp__github__issue_write\|mcp__github__add_reply_to_pull_request_comment\|mcp__github__pull_request_review_write\|mcp__github__add_comment_to_pending_review` |
  | `guarda_spec_previa` | PreToolUse | `Write\|Edit\|NotebookEdit\|Bash\|PowerShell` |
  | `guarda_mcp_github` | PreToolUse | `mcp__github__projects_write` |
  | `formatear_python` | PostToolUse | `Write\|Edit` |

  (En la tabla, `\|` es el `|` literal del JSON.)

  - **`PowerShell` en los matchers es un respaldo**: la herramienta queda desactivada
    por las denegaciones de Bash (R5). Si alguien la activa con
    `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`, las guardas ya la cubren. Esa parte se prueba
    con los tests de extremo a extremo (JSON con `tool_name: "PowerShell"` por stdin),
    no en la sesión.

  - **Tres herramientas que pide FR-004** (`add_issue_comment`, `update_issue_comment` y
    `create_pull_request`), más las cinco que también publican texto y que el proyecto no
    deniega (R4): `update_pull_request`, `issue_write`,
    `add_reply_to_pull_request_comment`, `pull_request_review_write` y
    `add_comment_to_pending_review`. Es un superconjunto de FR-004: una credencial en el
    cuerpo de un PR editado es tan grave como en uno nuevo.
  - En las herramientas MCP, la guarda revisa **todos los valores de texto** de
    `tool_input` (cuerpo, título, comentario), no un campo concreto, para no depender del
    nombre del campo en cada versión del servidor.
  - `NotebookEdit` entra en las guardas de secretos, datos y spec previa: escribe en
    `notebook_path` el contenido de `new_source`.
  - El formato no incluye `NotebookEdit`: un `.ipynb` no es un `.py`.

## R4. Herramientas del MCP de GitHub que se deniegan (punto c)

- **Fuente**: la lista de herramientas que expone el servidor `github` conectado en esta
  sesión, con los toolsets `repos,issues,pull_requests,projects` de `.mcp.json`. Son los
  mismos nombres que muestra `/mcp`. La marca de destructiva (`destructiveHint: true`)
  sale de las anotaciones del código del servidor (`github/github-mcp-server`, carpeta
  `pkg/github/__toolsnaps__`, commit `e3809fe`). El paso Q12 del quickstart lo contrasta
  con `/mcp`, porque `/mcp` es interactivo y no se puede consultar desde esta sesión.
- **Corrección de T003 (2026-10-16)**: la primera versión de esta sección decía que había
  tres herramientas expuestas y marcadas como destructivas. Ese dato salía del código
  fuente del servidor y de la lista de esta sesión, no de lo que expone el servidor con
  los toolsets de `.mcp.json`. La analista lo contrastó en `/mcp`, y coincide con la
  consulta `tools/list` que hizo la revisora con los mismos toolsets:
  - se exponen 42 herramientas;
  - `delete_repository` **no** existe con `repos,issues,pull_requests,projects`;
  - `projects_write` tiene exactamente los 10 métodos descritos más abajo.
- **Herramientas expuestas y marcadas como destructivas**: `delete_file` y
  `projects_write`. `delete_repository` no se expone con estos toolsets y se deniega de
  forma **preventiva**: aparecería si se ampliaran los toolsets.

  | Herramienta | ¿Expuesta? | ¿La usa el proyecto? | Decisión |
  |-------------|------------|----------------------|----------|
  | `mcp__github__delete_file` | Sí, destructiva | No | **Denegar** |
  | `mcp__github__projects_write` | Sí, destructiva | Sí, `update_project_item` en `siguiente-ticket` y `/abrir-pr` | Permitir (FR-017), limitada por `guarda_mcp_github` (FR-024) |
  | `mcp__github__delete_repository` | No, con estos toolsets | No | **Denegar de forma preventiva** |

  Las demás marcadas como destructivas en el código del servidor (`label_write`,
  `discussion_comment_write`, `actions_run_trigger`, reacciones, notificaciones,
  `remove_sub_issue`, `delete_pending_pull_request_review`) no se exponen con estos
  toolsets.
- **Denegadas además, por mínimo privilegio**: no están marcadas como destructivas, pero
  el proyecto nunca las necesita y saltarían las guardas locales o el flujo del equipo.

  | Herramienta | Motivo |
  |-------------|--------|
  | `mcp__github__create_or_update_file` | Escribe en el repositorio remoto sin pasar por las guardas de datos ni de spec previa |
  | `mcp__github__push_files` | Igual que la anterior, con varios archivos |
  | `mcp__github__merge_pull_request` | El merge lo hace una persona tras revisar el PR; el agente no fusiona en `main` |
  | `mcp__github__create_repository` | El proyecto trabaja en un único repositorio |
  | `mcp__github__fork_repository` | Igual que la anterior |

- **Comprobación de FR-017**: `siguiente-ticket`, `/abrir-pr` y `/comentar-avance` usan
  `issue_read`, `add_issue_comment`, `update_issue_comment`, `list_pull_requests`,
  `create_pull_request`, `projects_list`, `projects_get` y `projects_write`. Ninguna está
  en la lista. Un test lo comprueba leyendo esos tres archivos (R8).
- **`projects_write` limitada por una guarda (FR-024)**:
  - Su esquema expone diez métodos: `add_project_item`, `update_project_item`,
    `update_project_items`, `delete_project_item`, `create_project_status_update`,
    `create_project_view`, `update_project_view`, `delete_project_view`,
    `create_project` y `create_iteration_field`.
  - El proyecto solo usa `update_project_item`, en `siguiente-ticket` y `/abrir-pr`.
  - No se puede denegar por argumento: las reglas de permiso de herramientas MCP con
    paréntesis se ignoran.
  - Decisión: guarda `guarda_mcp_github.py` (PreToolUse, matcher
    `mcp__github__projects_write`, timeout 10 s, `onFailure: "block"`). Permite solo si
    `tool_input.method` es exactamente `update_project_item`, y bloquea cualquier otro
    método, también los que no borran: nada más del Project lo necesita el flujo. Cierra
    el que era riesgo residual 3.

## R5. Reglas de permiso de PowerShell (FR-003)

- **Hallazgo**:
  - Claude Code **admite** reglas `PowerShell(...)` en `permissions`, con
    comparación sin distinguir mayúsculas y alias canonicalizados (`gc`, `cat` y `type`
    se tratan como `Get-Content`).
  - Una regla `Read` no cubre los comandos de PowerShell.
  - En Windows con Git Bash, una regla de denegación de `Bash` desactiva la herramienta
    PowerShell, salvo que haya una regla de PowerShell con alcance o
    `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`. Por eso hoy, con solo reglas de Bash, la sesión
    no tiene la herramienta PowerShell.
- **Decisión (revisión del analista)**: PowerShell **se mantiene desactivada**, por
  mínimo privilegio.
  - No se añaden reglas `PowerShell(...)` a `permissions.deny`: encenderían la
    herramienta en Windows con Git Bash.
  - Las denegaciones de Bash la mantienen apagada.
  - Si alguien la activa con `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`, las guardas son la
    garantía, porque tienen `PowerShell` en sus matchers (R3).

  FR-003 queda así: "las denegaciones cubren Bash; la herramienta PowerShell queda
  desactivada por esas denegaciones y, si se activa, las guardas son la garantía".
- **Alternativa descartada**: reglas `PowerShell(...)` en `permissions.deny`. Dan una
  barrera más, pero a costa de encender una herramienta que el proyecto no necesita.

## R6. Patrones de la lista de denegaciones de secretos (FR-003)

- **Hallazgo**:
  - Las reglas `Read(...)` también se aplican a Grep, Glob y LSP. Las reglas `Edit(...)`
    se aplican a Edit, Write y NotebookEdit.
  - **Corrección (I6 de la segunda pasada del análisis)**: además, según la
    documentación de permisos, "Read and Edit deny rules apply to Claude's built-in file
    tools, to file commands Claude Code recognizes in Bash, such as `cat`, `head`, `tail`,
    `sed`, and `tee`, and to the targets of Bash redirections such as `> file` and
    `< file`. They don't apply to a command that reads files without naming them, such
    as `grep -r pattern .` […], or to arbitrary subprocesses that read or write files
    indirectly, like a Python or Node script that opens files itself."
  - Un `allow` no puede rescatar `.env.example` de un `Read(**/.env.*)`, porque se
    evalúa deny, luego ask, luego allow.
  - Las reglas de archivo de deny **sí admiten excepciones** (corrección del analista;
    la primera versión de este hallazgo decía lo contrario). La documentación de permisos
    dice: "A deny or ask pattern that starts with `!` is a gitignore negation. It carves
    the paths it matches out of the `path` or `./path` rules listed before it." Límites:
    - solo recorta reglas **anteriores** de la misma lista; un `!` puesto primero no
      recorta nada;
    - no alcanza reglas ancladas con `/`, `~/` o `//`;
    - no reabre un archivo dentro de un directorio bloqueado entero.
  - Las reglas de Bash no admiten `!`. Comparan el texto del comando y "aren't a
    security boundary".
  - Las dos reglas actuales, `Bash(cat .env*)` y `Bash(type .env*)`, también bloquean
    `cat .env.example`.
- **Decisión**: la lista de denegaciones es la **primera barrera**; el hook es la
  garantía.
  - **Herramientas de archivo**: `Read` y `Edit` sobre `**/.env`, `**/.env.*`,
    `**/*.key` y `**/secrets/**`, es decir, las mismas familias que la guarda (FR-003).
    Les siguen `Read(!**/.env.example)` y `Edit(!**/.env.example)`, **detrás** de las
    reglas que recortan. Ninguna de esas reglas está anclada, así que la excepción las
    alcanza. Además, `Edit(/.claude/settings.local.json)` (R14).
  - **Bash**: los lectores y copiadores más comunes (`cat`, `head`, `tail`, `less`,
    `more`, `cp`, `mv` y `source`) sobre `.env`, `.env.local`, `secrets/` y `*.key`.
    - Se mantienen como **defensa adicional** para los comandos que Claude Code no
      reconoce como de archivo, como `cp`, `mv` o `source`.
    - Las de `cat`, `head` y `tail` son en parte redundantes con las reglas `Read`, sin
      daño.
    - Por eso, en la sesión, un bloqueo de esos comandos puede venir de la capa de
      permisos o de la guarda, y cualquiera de las dos es un resultado válido. La capa de
      permisos y la guarda se comprueban por separado (I9):
      - `test_configuracion.py` comprueba que las reglas existen y están bien formadas;
      - su efecto se ve en la sesión, en Q1 y Q13;
      - la guarda se prueba en los tests por stdin.
  - **Sin `grep`**: una regla como `Bash(grep *.env *)` bloquearía
    `grep -n .env README.md`, una búsqueda del texto ".env" en un archivo normal, que
    FR-002 y SC-001 obligan a permitir. Una regla de permiso no distingue el patrón del
    archivo; la guarda sí (R9 y el contrato de `guarda_secretos`). Por eso `grep` queda
    solo a cargo de la guarda.
  - **Sin PowerShell** (R5).
  - Se sustituyen las dos reglas actuales por otras que no alcanzan `.env.example`. En
    Bash no hay `!`, así que la excepción se consigue con los objetivos (`*.env`,
    `*.env *`, `*.env.local*`), que no coinciden con `cat .env.example`.
  - Total: 58 entradas (11 de archivo, 40 de Bash y 7 del MCP).

  Lista exacta en [contracts/settings-json.md](contracts/settings-json.md).

## R7. Directorio del plugin (punto d)

- **Hallazgo**: el issue #13 pide un plugin con manifiesto `.claude-plugin/plugin.json` y
  un marketplace en el propio repositorio. La convención de Claude Code es un
  `.claude-plugin/marketplace.json` en la raíz que apunta a cada plugin en
  `plugins/<nombre>/`. Cada plugin lleva dentro su propio `.claude-plugin/plugin.json`.
- **Decisión**:
  - Plugins en **`plugins/<nombre>/`** y marketplace en **`.claude-plugin/`** de la raíz.
  - Código protegido: **`plugins/**`** y **`.claude-plugin/**`**, salvo `test_*.py`.
  - Se protege el directorio completo y no un nombre, porque #13 elegirá el nombre del
    plugin. La guarda ya lo protege aunque hoy no exista.
- **Alternativa descartada**: proteger solo `plugins/**/*.py`. El plugin también
  empaqueta un subagente, una skill y la configuración de hooks (`.md` y `.json`), que
  son su código.

## R8. Ubicación de los tests (punto e)

- **Decisión**:
  - Los tests de los hooks van **junto a cada script, en `.claude/hooks/test_*.py`**,
    como pide la constitución (X).
  - La revisión del repositorio completo es
    **`.claude/hooks/test_revision_repositorio.py`**, junto al detector que usa.
  - `pyproject.toml`: `testpaths = ["src", ".claude/hooks"]` y
    `pythonpath = [".claude/hooks"]`, para que los tests importen los módulos de los
    hooks con `--import-mode=importlib`, que ya está configurado. Se comprobó que pytest
    recoge un directorio que empieza por punto cuando está en `testpaths`.
  - `test_configuracion.py`, en la misma carpeta, valida `.claude/settings.json`
    (matchers, `onFailure`, timeouts y lista de denegaciones), la ausencia de las
    herramientas de FR-017 en esa lista y el frontmatter de las dos reglas.
- **Cómo prueban**:
  - Funciones puras del detector y de cada guarda, más una prueba de extremo a extremo
    por guarda que lanza el script con un JSON en stdin y comprueba el código de salida
    y que stderr no repite el valor.
  - La rama de PowerShell de cada guarda se prueba solo así, con JSON por stdin y
    `tool_name: "PowerShell"`, porque en la sesión la herramienta está desactivada (R5).
  - `test_guarda_mcp_github.py` comprueba que `update_project_item` pasa y que los otros
    nueve métodos, un `method` ausente y una entrada malformada se bloquean.
  - Los valores con forma real se construyen en tiempo de ejecución (dígito de Luhn y
    DV de la DIAN calculados; prefijos de credencial concatenados), así que nunca quedan
    literales en el repositorio (spec, casos borde).
  - La guarda de spec previa se prueba en repositorios git temporales (`tmp_path`).
- **Revisión del repositorio**: recorre `git ls-files -z`, salta los binarios (con un
  byte nulo en los primeros 8 KB) y aplica el detector. Al fallar informa archivo, línea
  y tipo, nunca el valor.
- **Cuando llegue #13**: el detector y la guarda de datos se moverán al plugin con sus
  tests. Es decisión de #13, no de este ticket.

## R9. Secretos que no se nombran como ruta (punto f, C1 e I1 del análisis)

- **Hallazgo**:
  - La herramienta Grep "respects .gitignore", y `.gitignore` excluye `.env`, `.env.*`,
    `*.key` y `secrets/`.
  - `rg` respeta `.gitignore` por defecto, y `git grep` solo busca en archivos
    versionados.
  - `grep -r`, `rg` con `-u`, `--no-ignore` o `--hidden`, `find … -exec` y
    `Get-ChildItem -Recurse` no respetan `.gitignore`.
  - Un secreto también se puede leer nombrándolo dentro de un texto que se ejecuta:
    código en línea de un intérprete (`python -c "…open('.env')…"`), `bash -c`, `eval`
    o un heredoc que alimenta a un intérprete. La primera versión del plan lo aceptaba
    como riesgo residual, y el análisis lo marcó como conflicto con la constitución VIII
    (C1).
  - Medido: recorrer la raíz del repositorio podando solo `.git` tarda ≈ 3 ms (813
    archivos).
- **Decisión 1, texto ejecutable (C1; U2, U3, C2 y D1 de la segunda pasada)**:
  - **Extractor compartido**: `comun.py` tiene un único extractor de texto ejecutable.
    Lo usan `guarda_secretos`, que busca nombres de secretos, y `guarda_spec_previa`, que
    busca código protegido (R10). Trata dos casos.
  - **Shells: análisis recursivo (U3)**. El comando interior de `bash -c`, `sh -c`,
    `eval`, `powershell` o `pwsh` con `-Command` o `-c`, y el cuerpo de un heredoc que
    alimenta a `bash` o `sh`, se analizan con **las mismas reglas que el comando
    exterior**: rutas, exclusión del patrón de búsqueda (FR-002) y raíz de las búsquedas
    recursivas. Así:
    - `bash -c "grep -r TOKEN ."` se bloquea, porque la raíz tiene `.env`;
    - `bash -c "grep '.env' src/"` se permite, porque `.env` es el patrón.

    Salvaguardas:
    - si el comando interior no se puede analizar (por ejemplo, `shlex` falla por
      comillas sin cerrar), se vuelve a la revisión como texto;
    - el anidamiento máximo es de **3 niveles**; uno más profundo se bloquea por
      precaución, con un mensaje que lo explica.
  - **Intérpretes de lenguaje: revisión como texto**. Se reconocen por patrón (C2), también
    detrás de `uv run [opciones]`:

    | Intérprete | Patrón del ejecutable | Opciones de código en línea |
    |------------|-----------------------|-----------------------------|
    | Python | `python` con versión opcional (`python3`, `python3.12`) | `-c` |
    | Lanzador de Python | `py`, con opciones de versión opcionales (`-3`, `-3.12`) antes de `-c` | `-c` |
    | Node | `node` | `-e`, `--eval`, `-p`, `--print` |
    | Perl | `perl` | `-e`, `-E` |
    | Ruby | `ruby` | `-e` |

    Se revisa como texto el argumento de esas opciones y el cuerpo de un heredoc que
    alimenta a uno de esos intérpretes (por ejemplo, `python - <<'FIN'`).
  - **Heredocs, acotación confirmada por la analista (D1)**: solo se analizan los que
    alimentan a un intérprete o a un shell. Los que alimentan a otro comando
    (`git commit -F - <<…`, `cat > archivo <<…`) no se revisan como código: un mensaje
    de commit que menciona ".env" no lee nada. Las otras guardas los cubren por su lado:
    - `guarda_datos` revisa el texto **completo** del comando, heredoc incluido, así que
      un dato con forma real en un mensaje de commit o en `cat > archivo <<…` se bloquea;
    - `guarda_spec_previa` revisa el destino de `cat > archivo`, como cualquier
      redirección (R10).
  - **Búsqueda de secretos en el texto (U2)**: una expresión regular encuentra:
    - `.env` sin una letra, un dígito ni `_` detrás. Sí puede seguir `.<sufijo>`, que
      cuenta salvo `.env.example`. Así, `os.environ` y `.environment` no coinciden.
    - un nombre que termina en `.key` seguido de comilla, espacio o fin de texto;
    - `secrets/` o `secrets\`.

    Delante de cualquiera de ellos no puede haber una letra, un dígito, `.`, `_` ni `-`
    pegado. Así, `x.keys()`, `obj.key)` y el módulo `secrets.token_hex` tampoco coinciden.
  - **Correcciones de la revisión de la parada B**: la revisora ejecutó el extractor con
    entradas reales y encontró huecos. Las reglas completas están en el contrato de
    guardas (interfaz común); en resumen:
    - **Heredocs**: `<<` no cuenta si forma parte de `<<<`. Un heredoc sin delimitador
      de cierre no se quita, y sus líneas se analizan como comandos. Antes, un `<<<`
      seguido de otra línea hacía desaparecer esa línea.
    - **Sustitución de comandos**: `$(…)`, también dentro de comillas dobles, y las
      comillas invertidas son comandos interiores (nivel + 1).
    - **Tuberías**: un intérprete o un shell que lee de una tubería recibe como código o
      como comando interior el texto de las etapas anteriores, incluidos los cuerpos de
      heredoc (`echo "…" | python`, `cat <<'FIN' | python3`).
    - **Herestrings** (`<<<`): con un intérprete, la palabra siguiente es código; con
      `bash` o `sh`, un comando interior.
    - **Envoltorios**: se saltan las asignaciones `NOMBRE=valor` y `env`, `exec`,
      `command`, `nohup`, `time`, `nice` y `timeout`. En `uv run` se toma la primera
      palabra que sea un intérprete o un shell, sin lista fija de opciones.
    - **Lanzadores** (revisión previa del PR #17, FR-026): `xargs [opciones] <cmd…>`
      (con `-a`, `-I`, `-n`, `-0` y las demás opciones con valor), `sudo` y `doas`
      (saltando opciones como `-u <usuario>`) se saltan como envoltorios, y el comando que
      lanzan se analiza como programa. `env -S "<cadena>"`, `script -c "<cmd>"` y
      `watch "<cmd>"` (o `watch <cmd…>`) dan un comando interior.
    - **`cmd /c`** y `cmd //c`, también con `/k`, son un shell interior, analizado sin `\`
      como escape.
    - **Rutas de Git Bash**: `/<letra>/…` se convierte en `<LETRA>:/…` en Windows.
  - **Correcciones de la revisión de la parada B2**: un sondeo de regresión encontró que
    el patrón con que Claude Code escribe los commits,
    `git commit -m "$(cat <<'EOF' … EOF)"`, hacía fallar el extractor (`IndexError`). El
    cuerpo se quitaba del texto exterior, pero la marca del heredoc quedaba dentro de
    `$(…)` sin su cuerpo. Con las guardas registradas, el fallo cerrado habría bloqueado
    todos los commits. La raíz era la misma que la del residual `echo "<<X"`: el
    reconocimiento de heredocs no sabía de comillas. Decisión:
    - **Los heredocs conocen las comillas**: `<<` entre comillas simples o dobles, o en
      un comentario, es texto literal. Dentro de `$(…)` empieza un contexto nuevo, aunque
      vaya entre comillas dobles, y ahí sí puede haber heredocs.
    - **El cuerpo viaja con su comando**: el texto de cada `$(…)` se toma del comando
      original, con sus heredocs completos. Las palabras que se analizan como comando
      interior o como código recuperan también los cuerpos que se les quitaron.
    - **Una marca sin cuerpo** lanza `ValueError`, nunca `IndexError`, para que en un
      comando interior se aplique la vuelta a texto.
    - **Prueba de regresión**: un corpus de comandos legítimos del proyecto (commits con
      heredoc, `git log`, `gh api … --jq`, `uv run`, `git switch`) debe analizarse sin
      excepción y sin código ni comandos interiores que nombren secretos.
  - **Correcciones de la revisión de la parada B3, comentarios**: `shlex` trataba `#`
    como comentario también en mitad de una palabra, al contrario que bash, y al saltarse
    el comentario se comía el salto de línea. Así, `echo a#b; cat .env` perdía
    `cat .env`, y con `echo # x` en una línea y `python -c "…"` en la siguiente, el
    programa pasaba a ser `echo` y el código no se detectaba. Decisión:
    - El recorrido único quita los comentarios con la regla de bash y `shlex` no los
      trata (`commenters = ""`).
    - `#` abre comentario solo al principio de una palabra y fuera de comillas. No lo
      abre en `a#b`, `${#var}` ni `$#`. El salto de línea sigue separando comandos.
    - En PowerShell vale la misma regla como respaldo. Los bloques `<# … #>` y las
      comillas ANSI-C de bash (`$'…'`) quedan como límites declarados. Con `$'…'`, si
      `shlex` falla, la guarda bloquea por precaución: es un falso positivo, nunca un
      hueco.
- **Decisión 2, búsquedas recursivas (I1)**: se bloquean **solo si su raíz contiene
  archivos de secretos** (FR-002: la búsqueda "no apunta a archivos de secretos").
  - Se aplica a:
    - `grep`, `egrep` y `fgrep` con `-r`, `-R`, `--recursive` o `-d recurse`;
    - `rg` con `-u`, `-uu`, `--no-ignore` o `--hidden`;
    - `find` combinado con `-exec`, `-execdir` o `| xargs` y un lector (`cat`, `head`,
      `tail`, `grep`, `less` o `more`);
    - en PowerShell, `Get-ChildItem` (o `gci`, `ls`, `dir`) con `-Recurse`, conectado
      por tubería a `Get-Content` o `Select-String`.
  - **Raíz de la búsqueda**: los argumentos de ruta del comando, o `.` si no hay
    ninguno, resueltos contra el `cwd` del JSON de entrada.
  - **Recorrido**: se recorre cada raíz con `os.walk`, podando solo `.git`. Se para en el
    primer archivo de secretos (data-model) y se bloquea. Si la raíz no tiene ninguno, se
    permite.
  - **Exclusiones**: un `--exclude` o `-Exclude` que cubre `.env` no cambia la decisión,
    porque solo cuenta lo que hay bajo la raíz. Se mantiene simple a propósito.
  - **Ejemplos**: `grep -rn ".env" src/` se permite (en `src/` no hay secretos) y
    `grep -r TOKEN .` se bloquea (la raíz tiene `.env`).
- **Se permiten siempre**: la herramienta Grep, `rg` sin esas opciones y `git grep`.
- **Comodines**: un comodín que se expande a un secreto (`cat .e*`, `Get-Content *.local`)
  se bloquea, porque la guarda expande cada argumento con comodines contra la raíz.
- **Riesgo que se acepta y se declara** en `DECISIONES.md`:
  - Rutas construidas al ejecutar (variables, concatenaciones, subshells que generan el
    nombre).
  - Nombres codificados, por ejemplo en base64.
  - Scripts escritos en un archivo y ejecutados después.
  - **Lectores de archivos completos** (revisión previa del PR #17): `tar c`, `zip -r` y
    `git show <rev>:<ruta>`. Leen todo un árbol o una revisión sin nombrar el secreto;
    `.env` nunca se versionó, así que `git show` no lo alcanza.

  Las reglas de Bash no son una frontera de seguridad. Las guardas reconocen todas las
  formas en que se nombra un secreto, pero no las que lo ocultan a propósito.
- **Alternativa descartada para el MVP**: el sandbox de Bash de Claude Code, con
  denegación de lectura a nivel de sistema operativo. Cambia el comportamiento de todos
  los comandos, y su soporte en Windows nativo, el sistema del equipo, no está
  garantizado. Se anota como mejora posible.

## R10. Reconocimiento de escrituras en comandos de terminal (FR-012)

- **Decisión**: la guarda de spec previa extrae los destinos de escritura reconocibles y
  comprueba si alguno es código protegido.
  - **Bash**: redirecciones `>`, `>>` y `>|`, salvo `/dev/null` y los descriptores
    (`2>&1`); `tee [-a]`; el último argumento de `cp`, `mv` e `install`, o el de `-t`;
    los archivos de `sed -i`; `touch`.
  - **PowerShell** (respaldo, R5): redirecciones `>` y `>>`; `Set-Content`, `Add-Content`, `Out-File` y
    `New-Item` (`-Path`, `-FilePath` o primer posicional); `Copy-Item` y `Move-Item`
    (`-Destination` o segundo posicional).
  - **Borrar, restaurar y mover también es modificar** (revisión de la parada D, FR-009 y
    FR-012):
    - Bash: `rm`, `unlink` y `git rm`, con todas las palabras que no son opciones;
    - `git checkout … -- <rutas>` y `git restore <rutas>`, con o sin `--source`. Un
      `git checkout <rama>` sin `--` no cuenta;
    - las **fuentes** de `mv`, además del destino;
    - PowerShell, como respaldo: `Remove-Item`, `del`, `erase`, `rd` y `ri`, y las
      fuentes de `Move-Item` (y de sus alias `mv`, `mi` y `move`).
  - **Ampliación de la revisión de la parada E**:
    - **Carpetas que contienen código protegido**, al borrar, restaurar o mover: cuenta
      la raíz (`rm -rf .`, `git restore .`), una carpeta que es ancestro de algo
      protegido (`.claude`) y una carpeta dentro de una zona protegida (`src/app/`).
      Es una regla distinta de la del destino de una copia. `rm -rf docs` se permite.
    - **`git checkout` sin `--`**: se saltan las opciones con valor (`-b`, `-B`,
      `--orphan`); los posicionales a partir del segundo son rutas, y el primero solo si
      existe en disco. `git checkout 003-x` y `git checkout -b 004-y main` no cuentan.
    - **`git mv`**: cada posicional es una ruta. **`git -C <dir>`**: las rutas se
      resuelven respecto a `<dir>`.
    - **`cd` dentro del comando**: `cd`, `pushd`, `Set-Location`, `sl` y `chdir` con un
      argumento literal cambian la carpeta respecto a la que se resuelven las rutas
      siguientes del mismo comando.
    - **Comandos interiores y código tras un `cd`** (cierre de la parada E): la
      interpretación anterior, que analizaba cada comando interior desde el cwd de la
      sesión, dejaba pasar `cd .claude && bash -c 'rm settings.json'`. Decisión:
      - los comandos interiores (`bash -c`, `sh -c`, `eval`, `cmd /c`,
        `powershell -c`, heredocs hacia un shell) heredan la carpeta vigente en el
        subcomando donde aparecen. El extractor de `comun.py` anota, para cada comando
        interior y cada texto de código, de qué texto y de qué subcomando sale. Si no se
        sabe (una sustitución que no se encuentra en ninguna palabra), se prueba con
        todas las carpetas de ese texto;
      - un texto de código de intérprete cuenta como código protegido si la carpeta
        vigente cuenta según la regla de carpetas, salvo la raíz: el patrón U4 no puede
        resolver rutas relativas como `app/b.py`. Así, `cd src && python -c "…"` se
        bloquea fuera de un ticket, y `cd docs && python -c "print(1)"` y un
        `python -c` en la raíz se siguen permitiendo.
    - **`truncate`**: sus posicionales son rutas, saltando el valor de `-s`, `-r`,
      `--size` y `--reference`.
  - El comando se divide por `;`, `&&`, `||` y `|`, y se separa en palabras con `shlex`
    (modo POSIX en Bash; en PowerShell, comillas simples y dobles).
- **Texto ejecutable (I7 de la segunda pasada)**: la guarda usa el mismo extractor de
  `comun.py` que `guarda_secretos` (R9, decisión 1):
  - los shells anidados (`bash -c`, `sh -c`, `eval`, `pwsh -Command`, y los heredocs que
    alimentan a `bash` o `sh`) se analizan con estas mismas reglas de destinos;
  - en el código en línea de `python`, `node`, `perl` y `ruby` se buscan como texto
    nombres de código protegido (data-model), con este criterio:
    **Código protegido en el texto (U4 de la tercera pasada)**:
      - cuenta una **ruta**, con `/`, `\` o `\\` como separador (la doble barra es como
        se escribe `\` dentro de un literal de Python) y opcionalmente `./`, `.\` o `.\\`
        delante, que coincida con la lista del data-model: `src/…/*.py`,
        `.claude/hooks/…`, `.claude/settings.json`, `.claude/settings.local.json`,
        `.mcp.json`, `plugins/…` y `.claude-plugin/…`;
      - delante de la ruta no puede haber una letra, un dígito, `_`, `.` ni `-` pegados;
      - una ruta cuyo nombre de archivo es `test_*.py` no cuenta;
      - un nombre de módulo sin ruta (`import due_diligence`, `due_diligence.config`) no
        cuenta.
  - No se distingue entre lectura y escritura: la guarda solo bloquea cuando faltan spec,
    plan o tareas, o cuando la rama no es de un ticket. En la rama de un ticket con los
    tres documentos, un `python -c` que nombra `src/x.py` se permite igual.
- **Riesgo residual declarado**: `git apply`, `patch`, `git reset`, `git stash`,
  `find … -delete`, `find … -exec rm`, `xargs rm`, los `cd -`, `cd ~` y `cd $X`, y las
  rutas en variables o construidas al ejecutar. Desde la revisión previa del PR #17,
  también las escrituras que la guarda no reconoce: `perl -pi`, `dd of=`, `curl -o`,
  `wget -O`, `ln -sf`, `rsync`, `tar -C` y `tar x`, `unzip -d`, `git clean`,
  `uv run ruff check --fix` y `ruff format`. Motivo: escriben en código versionado, que
  el diff del PR y la revisión previa ven. Se anota en `DECISIONES.md`. Los
  intérpretes y shells que nombran código protegido ya no son residuales, ni
  `git checkout` (con o sin `--`), `git restore` y `git mv`, que se vigilan desde las
  revisiones de las paradas D y E.

## R11. Detector de datos con forma real (FR-005, FR-006)

- **Decisión**: módulo `detector_datos.py` con funciones puras, compartido por la guarda
  de datos y por la revisión del repositorio. Definiciones en
  [contracts/detector-datos.md](contracts/detector-datos.md).
  - **NIT**: dígito de verificación de la DIAN, con pesos 3, 7, 13, 17, 19, 23, 29, 37,
    41, 43, 47, 53, 59, 67 y 71 aplicados de derecha a izquierda. Con `s = suma mod 11`,
    el DV es `s` si `s` vale 0 o 1, y `11 − s` en otro caso.
  - **Tarjeta**: prefijo 2–6 más Luhn. Una marca de tiempo en milisegundos de 13 dígitos
    empieza por 1, así que no coincide (spec, casos borde).
  - **Decimales (revisión de la parada B)**: la parte decimal de un número no cuenta como
    tarjeta (`(?<!\d[.,])`). Sin esa condición, 1.042 de 20.000 `repr(random.random())`
    se marcaban como tarjeta.
  - **Límites de palabra** en todos los patrones: un número pegado a letras o dígitos
    (hashes, `uv.lock`, identificadores) no cuenta.
- **Alternativa descartada**: bibliotecas de detección de secretos
  (`detect-secrets`, `gitleaks`). Añaden dependencias, no conocen el NIT ni la cédula
  colombianos y no se pueden ajustar a las exclusiones del proyecto sin configuración
  extra.

## R12. Hook de formato (FR-014, FR-015)

- **Decisión**:
  - Si `tool_input.file_path` termina en `.py`, ejecuta
    `uv run --project <raíz> --frozen --quiet ruff format --force-exclude <archivo>`,
    con la raíz como directorio de trabajo (revisión de la parada E):
    - `uv run --project <raíz>` usa el ruff del `uv.lock` (0.17.0), el mismo de
      `ruff format --check`. `sys.executable` no sirve: con `uv run --no-project`, solo
      es el Python del `.venv` cuando el cwd está dentro del repositorio, y desde otra
      carpeta es un Python sin ruff ("No module named 'ruff'").
    - `--frozen` evita que un hook reescriba `uv.lock`.
    - `--force-exclude` hace que se respete el `extend-exclude` de `pyproject.toml`
      aunque la ruta se pase de forma explícita. Sin él, ruff formatea igual un archivo
      de `.specify/`, como se comprobó en la parada E.
    - El éxito se decide solo por el código de salida: con `--force-exclude`, un
      archivo excluido escribe "No Python files found" en stderr con salida 0, y eso no
      es un error.
    - Si faltan uv o ruff, se devuelve el mismo `additionalContext` que cuando ruff
      falla.
  - Si ruff falla, por ejemplo por un error de sintaxis, devuelve en stdout
    `hookSpecificOutput.additionalContext` ("No se pudo formatear <archivo>: …") y sale
    con 0. La edición se conserva.
  - Solo formatea: no ejecuta `ruff check --fix` (spec, Assumptions).
- **Hallazgo**: en PostToolUse, la salida 2 no deshace nada y `decision: "block"` termina
  el turno por defecto. Por eso se usa `additionalContext`.
- **Límite declarado**: un `.py` escrito por un comando de terminal no se formatea al
  momento. Lo detecta `ruff format --check` antes del PR.

## R13. Reglas por ruta (FR-018, FR-019)

- **Hallazgo**: el frontmatter YAML admite `paths` como lista. La regla se carga cuando
  Claude lee, escribe o edita un archivo que coincide. Si el YAML no es válido, la regla
  se carga como si no tuviera `paths`. Las reglas son contexto, no garantía.
- **Decisión**: `paths` como lista YAML entre comillas (`- "**/test_*.py"` y
  `- "src/servidor_mcp/**/*.py"`). `test_configuracion.py` valida que el frontmatter se
  pueda leer y contenga exactamente esos globs.

## R14. `.claude/settings.local.json` y el cambio de rama (revisión del analista)

- **Hallazgo**:
  - `.claude/settings.local.json` es personal y no se versiona (`.gitignore`), pero se
    impone a la configuración del proyecto. Un `"disableAllHooks": true` en ese archivo
    apaga todas las guardas.
  - Las guardas viven en `.claude/hooks/` de la rama actual. En `main`, mientras no se
    fusione este ticket, no existen. Si la sesión cambia a una rama sin esos scripts,
    cada guarda falla al arrancar y `onFailure: "block"` bloquea todas las acciones que
    vigila. Si se recarga el `settings.json` de esa rama, las guardas desaparecen.
- **Decisión**:
  - `Edit(/.claude/settings.local.json)` en `permissions.deny`. Esta regla cubre Edit,
    Write y NotebookEdit. Va anclada con `/`: en la configuración del proyecto, `/path`
    se resuelve desde la raíz del proyecto, mientras que `./path` sería relativa al
    directorio actual, que cambia con los `cd`.
  - `.claude/settings.local.json` pasa a ser código protegido (FR-011), así que la
    guarda de spec previa también vigila las escrituras por terminal que lo tengan como
    destino.
  - **En cualquier rama** (revisión previa del PR #17, FR-025): escribir, borrar, mover
    o restaurar `.claude/settings.local.json`, por terminal o con código en línea que lo
    nombra, se bloquea aunque la rama tenga spec, plan y tareas. El archivo no se
    versiona, así que ningún PR vería el cambio. Leerlo sigue permitido. El mensaje es
    propio: `[guarda_spec_previa] .claude/settings.local.json no se modifica desde Claude
    Code en ninguna rama: puede desactivar las guardas. Edítalo fuera de Claude Code.`
  - Las personas siguen pudiendo editarlo fuera de Claude Code, que es su función.
  - Las pruebas "sin ticket" del quickstart no se hacen en `main`, sino en una rama
    temporal `prueba-sin-ticket` creada desde `003-guardas-claude-code`, que sí tiene los
    hooks.
  - El README avisa: con las guardas activas, no se cambia a una rama sin
    `.claude/hooks/`, y si ocurre, se reinicia la sesión. Además, `uv sync` se ejecuta
    antes de abrir Claude Code.
