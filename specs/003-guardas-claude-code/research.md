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
    - Formato: `args: ["run", "--project", "${CLAUDE_PROJECT_DIR}", "--quiet",
      "${CLAUDE_PROJECT_DIR}/.claude/hooks/formatear_python.py"]`. Necesita el grupo
      `dev`, donde está ruff; el script lo invoca con `sys.executable -m ruff format`.
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
    Cuenta como fallo: que el hook no arranque (por ejemplo, falta `uv` o el script),
    una salida distinta de 0 y 2, el timeout o una salida JSON inválida.
- **Decisión**: el fallo cerrado tiene dos capas.
  1. Cada guarda envuelve su lógica en un `try/except BaseException`. Ante cualquier
     excepción escribe en stderr "La guarda <nombre> falló (<tipo de error>); la acción
     se bloquea por precaución." y sale con 2.
  2. Las cuatro guardas (secretos, datos, spec previa y Project, R4) llevan
     `"onFailure": "block"`. Así se cubre lo que el script no puede atrapar: `uv`
     ausente, script inexistente o timeout.

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
- **Herramientas expuestas y marcadas como destructivas**: exactamente tres.

  | Herramienta | ¿La usa el proyecto? | Decisión |
  |-------------|----------------------|----------|
  | `mcp__github__delete_repository` | No | **Denegar** |
  | `mcp__github__delete_file` | No | **Denegar** |
  | `mcp__github__projects_write` | Sí, `update_project_item` en `siguiente-ticket` y `/abrir-pr` | Permitir (FR-017) |

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

## R9. Riesgo residual de la lectura recursiva (punto f)

- **Hallazgo**:
  - La herramienta Grep "respects .gitignore", y `.gitignore` excluye `.env`, `.env.*`,
    `*.key` y `secrets/`.
  - `rg` respeta `.gitignore` por defecto, y `git grep` solo busca en archivos
    versionados.
  - `grep -r`, `find … -exec` y `Get-ChildItem -Recurse` no respetan `.gitignore`.
- **Decisión**:
  - **Se bloquean** en la guarda de secretos los comandos recursivos que pueden leer
    secretos sin nombrarlos y no los excluyen:
    - `grep`/`egrep`/`fgrep` con `-r`, `-R`, `--recursive` o `-d recurse`, salvo con un
      `--exclude` o `--exclude-dir` que cubra `.env`;
    - `rg` con `-u`, `--no-ignore`, `--hidden` o `-uu`;
    - `find` combinado con `-exec`, `-execdir` o `| xargs` y un lector (`cat`, `head`,
      `tail`, `grep`, `less`, `more`);
    - en PowerShell (respaldo, R5), `Get-ChildItem` (o `gci`, `ls`, `dir`) con `-Recurse` conectado por
      tubería a `Get-Content` o `Select-String`, salvo con un `-Exclude` que cubra
      `.env`.
  - **Se permiten**: la herramienta Grep, `rg` sin esas opciones y `git grep`, porque
    respetan `.gitignore` o solo ven archivos versionados.
  - Un comodín que se expande a un secreto (`cat .e*`, `Get-Content *.local`) también se
    bloquea: la guarda expande cada argumento con comodines contra la raíz del
    repositorio.
  - **Riesgo que se acepta y se declara** en `DECISIONES.md`: rutas construidas en tiempo
    de ejecución (variables, `base64`, `eval`, subshells), intérpretes que leen archivos
    (`python -c`, `node -e`) y copias recursivas de directorios. Las reglas de Bash no
    son una frontera de seguridad y las guardas reconocen formas comunes, no todas.
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
  - El comando se divide por `;`, `&&`, `||` y `|`, y se separa en palabras con `shlex`
    (modo POSIX en Bash; en PowerShell, comillas simples y dobles).
- **Riesgo residual declarado**: `git apply`, `patch`, `git checkout -- <ruta>`,
  intérpretes que escriben archivos (`python -c`), y rutas en variables. Se anota en
  `DECISIONES.md`.

## R11. Detector de datos con forma real (FR-005, FR-006)

- **Decisión**: módulo `detector_datos.py` con funciones puras, compartido por la guarda
  de datos y por la revisión del repositorio. Definiciones en
  [contracts/detector-datos.md](contracts/detector-datos.md).
  - **NIT**: dígito de verificación de la DIAN, con pesos 3, 7, 13, 17, 19, 23, 29, 37,
    41, 43, 47, 53, 59, 67 y 71 aplicados de derecha a izquierda. Con `s = suma mod 11`,
    el DV es `s` si `s` vale 0 o 1, y `11 − s` en otro caso.
  - **Tarjeta**: prefijo 2–6 más Luhn. Una marca de tiempo en milisegundos de 13 dígitos
    empieza por 1, así que no coincide (spec, casos borde).
  - **Límites de palabra** en todos los patrones: un número pegado a letras o dígitos
    (hashes, `uv.lock`, identificadores) no cuenta.
- **Alternativa descartada**: bibliotecas de detección de secretos
  (`detect-secrets`, `gitleaks`). Añaden dependencias, no conocen el NIT ni la cédula
  colombianos y no se pueden ajustar a las exclusiones del proyecto sin configuración
  extra.

## R12. Hook de formato (FR-014, FR-015)

- **Decisión**:
  - Si `tool_input.file_path` termina en `.py`, ejecuta
    `sys.executable -m ruff format <archivo>`, que respeta `pyproject.toml` (incluido
    `extend-exclude`).
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
  - Las personas siguen pudiendo editarlo fuera de Claude Code, que es su función.
  - Las pruebas "sin ticket" del quickstart no se hacen en `main`, sino en una rama
    temporal `prueba-sin-ticket` creada desde `003-guardas-claude-code`, que sí tiene los
    hooks.
  - El README avisa: con las guardas activas, no se cambia a una rama sin
    `.claude/hooks/`, y si ocurre, se reinicia la sesión. Además, `uv sync` se ejecuta
    antes de abrir Claude Code.
