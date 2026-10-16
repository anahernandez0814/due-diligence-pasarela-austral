---

description: "Lista de tareas del ticket #3, guardas de Claude Code: hooks, permisos y reglas por ruta"
---

# Tasks: Guardas de Claude Code: hooks, permisos y reglas por ruta

**Input**: documentos de diseño en `specs/003-guardas-claude-code/`: [plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/) y [quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/
y quickstart.md.

**Tests**: obligatorios (FR-021 y constitución X). Van junto a cada script, en
`.claude/hooks/test_*.py`, y se escriben antes que el script (deben fallar primero).

**Organization**: las fases siguen el orden de implementación de `plan.md`:

1. Módulos compartidos y detector: fase 2.
2. Guardas y formato: fases 3 a 7, una por historia.
3. y 4. `pyproject.toml`, revisión del repositorio y `settings.json`: fase 8.
5. Reglas por ruta: fase 9.
6. Documentación: fase 10.
7. Commit, pausa y quickstart: fase 11.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La
verificación del cierre de #3 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US6).
- **[MANUAL]**: la hace la analista, fuera de Claude Code o en la interfaz de Claude Code.
  Claude se detiene y espera su confirmación.
- Cada tarea cita su origen: FR-### de la spec o R# de [research.md](research.md).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Ningún valor con forma real** (tarjeta, NIT, cédula o credencial) se escribe en
  tareas, tests, código ni documentación. Los tests los generan en tiempo de ejecución:
  - dígito de Luhn calculado sobre un prefijo;
  - dígito de verificación de la DIAN calculado;
  - prefijo de credencial concatenado con caracteres aleatorios de `secrets`/`random`.
- **Datos ficticios** de apoyo, cuando hagan falta: `CO-TV-0001`, `$80.000.000` y
  contenidos como `VARIABLE_FICTICIA=valor-de-prueba`.
- **Commits** por partes lógicas en la rama `003-guardas-claude-code`, nunca en `main`, y
  sin `git commit --amend`: cada corrección va en un commit nuevo.
- **Formato manual hasta la sesión nueva**: el hook de formato solo actúa desde que se
  reinicia la sesión (T035). Hasta entonces, cada fase termina con
  `uv run ruff format .claude/hooks` y `uv run ruff check .claude/hooks`.
- **Tests antes de T023**, mientras `pyproject.toml` no incluye `.claude/hooks`:
  `uv run pytest .claude/hooks -o pythonpath=.claude/hooks`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: confirmar el punto de partida.

- [ ] T001 Confirmar el punto de partida:
  - la rama activa es `003-guardas-claude-code`;
  - `git log --oneline main..HEAD` contiene los commits de spec, plan, correcciones,
    checklist y tareas;
  - `git status --porcelain` está vacío;
  - el issue #3 está en "In Progress" (`mcp__github__projects_list`,
    `list_project_items`, `field_names: ["Status"]`);
  - `uv run pytest` está en verde (2 tests de humo).
- [ ] T002 Confirmar lo que todavía no existe y la versión:
  - no existen `.claude/hooks/` ni `.claude/rules/`;
  - `.claude/settings.json` tiene las 6 denegaciones del ticket #1 y no tiene `hooks`;
  - `claude --version` es 2.1.295 o posterior, necesario para `onFailure` (R2).

  Si algo difiere, detenerse e informar.

**Checkpoint**: rama limpia y ninguna guarda creada todavía.

---

## Phase 2: Foundational (Blocking Prerequisites), paso 1 del plan

**Purpose**: los módulos que usan todas las guardas y la revisión del repositorio.

**⚠️ CRITICAL**: ninguna guarda puede empezar antes de terminar esta fase.

- [ ] T003 [P] Escribir `.claude/hooks/test_comun.py`, según la interfaz común de [contracts/guardas.md](contracts/guardas.md), R1 y R2. Debe cubrir:
  - **lectura de stdin**: JSON válido; JSON inválido, que lanza error;
  - **raíz**: `CLAUDE_PROJECT_DIR` tiene prioridad sobre `cwd`;
  - **normalización de rutas**: `\` → `/`, relativa a la raíz, rutas fuera de la raíz y
    mayúsculas;
  - **división de comandos**: `;`, `&&`, `||`, `|`, redirecciones `<`, `>` y `>>`, y
    comillas simples y dobles, con `shlex` y `punctuation_chars`;
  - **`bloquear()`**: sale con 2 y escribe una sola línea en stderr con el formato
    `[<guarda>] <motivo>. <qué hacer>.`;
  - **envoltorio de fallo cerrado**: ante una excepción, sale con 2 y escribe
    `[<guarda>] La guarda falló (<TipoDeError>); la acción se bloquea por precaución.`
- [ ] T004 Implementar `.claude/hooks/comun.py`, solo con la biblioteca estándar, hasta que pase `test_comun.py` (contracts/guardas.md, interfaz común; R1, R2, R10).
- [ ] T005 [P] Escribir `.claude/hooks/test_detector_datos.py` con los casos mínimos de [contracts/detector-datos.md](contracts/detector-datos.md) (FR-005, FR-006, R11). Todos los positivos se generan en la prueba:
  - **Tarjeta**:
    - coincide con prefijos 2 a 6, longitudes 13, 16 y 19, y con y sin separadores
      (espacio o guion);
    - no coincide con un dígito cambiado, con prefijo 1 ni con una marca de tiempo actual
      en milisegundos (`time.time_ns() // 10**6`).
  - **NIT**: coincide con el DV calculado, con guion o tras la palabra "NIT"; no coincide
    con un DV erróneo.
  - **Cédula**: coincide con cada palabra de contexto; no coincide sin contexto ni
    precedida de `$`.
  - **Credenciales**: coinciden las cuatro familias con su longitud mínima; no coinciden
    con un carácter menos.
  - **Permitidos**: el mensaje de ejemplo, leído en tiempo de ejecución de
    `docs/enunciado.md`; `CO-TV-0001`; `$80.000.000`.
  - **Resultado**: `buscar()` devuelve solo pares `(tipo, linea)`, nunca el valor.
- [ ] T006 Implementar `.claude/hooks/detector_datos.py` con `buscar(texto) -> list[tuple[str, int]]` y los tipos `"tarjeta"`, `"nit"`, `"cedula"` y `"credencial"`, hasta que pase `test_detector_datos.py` (FR-005, FR-006, R11). Las expresiones regulares usan clases de caracteres, de modo que no coinciden consigo mismas.
- [ ] T007 Ejecutar `uv run pytest .claude/hooks -o pythonpath=.claude/hooks`, `uv run ruff format .claude/hooks` y `uv run ruff check .claude/hooks`, todo en verde. Commit: `feat(hooks): módulos comunes y detector de datos con forma real`.

**Checkpoint**: `comun` y `detector_datos` probados. Ninguna guarda registrada.

---

## Phase 3: User Story 1 - Los secretos no se tocan desde Claude Code (Priority: P1) 🎯 MVP

**Goal**: ninguna herramienta de Claude Code abre ni modifica archivos de secretos, y
`.env.example` sigue accesible.

**Independent Test**: los tests de extremo a extremo de `guarda_secretos` bloquean `.env`,
`.env.local` y `secrets/` por Read, Grep, Bash y PowerShell, y permiten `.env.example`.

- [ ] T008 [P] [US1] Escribir `.claude/hooks/test_guarda_secretos.py` (FR-001, FR-002, R9, contracts/guardas.md).
  - **Montaje**: unitarios de la función de decisión y de extremo a extremo, que lanzan
    el script con `sys.executable`, un JSON por stdin y `CLAUDE_PROJECT_DIR=tmp_path`. Los
    archivos de secretos se crean en `tmp_path`, con contenido ficticio y un marcador.
  - **Se bloquean (salida 2)**:
    - Read, Write y Edit de `.env`, `.env.local`, `.ENV`, `x.key` y `secrets/a.txt`;
    - NotebookEdit con `notebook_path` en `secrets/`;
    - Grep con `path` o `glob` hacia secretos;
    - Glob con un patrón que nombra `.env`;
    - Bash: `head .env.local`, `cat ./secrets/a.txt`, redirección `< .env`, un comodín
      que se expande a `.env.local`, `grep -r` sin `--exclude`, `rg --no-ignore`,
      `rg --hidden`, `rg -u`, `find … -exec cat` y `find … | xargs cat`;
    - PowerShell, como respaldo: `Get-Content .env.local` y
      `Get-ChildItem -Recurse | Select-String`.
  - **Se permiten (salida 0)**:
    - Read y Edit de `.env.example`;
    - Grep con `pattern` `.env` en `src/`;
    - `grep -n .env README.md`, `git grep ".env"` y `rg TOKEN`;
    - `grep -r --exclude=.env* TOKEN .`;
    - `git commit -m "protege .env"`.
  - **Mensajes**: stderr nunca contiene el marcador y sigue los formatos del contrato.
- [ ] T009 [US1] Implementar `.claude/hooks/guarda_secretos.py` con `comun` hasta que pase `test_guarda_secretos.py`. Debe:
  - revisar por herramienta según la tabla del contrato;
  - excluir el patrón de búsqueda de `grep`, `egrep`, `fgrep`, `rg`, `git grep`, `Select-String` y `findstr`;
  - expandir los comodines contra la raíz;
  - aplicar la lista de lecturas recursivas de R9.

  Origen: FR-001, FR-002, FR-020, FR-023, R9.
- [ ] T010 [US1] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): guarda de secretos`.

**Checkpoint**: la guarda de secretos funciona por stdin; todavía no está registrada.

---

## Phase 4: User Story 2 - Ningún archivo recibe datos con forma real ni credenciales (Priority: P1)

**Goal**: lo que se escribe, se ejecuta o se publica por el MCP de GitHub no lleva datos
con forma real.

**Independent Test**: los tests de extremo a extremo de `guarda_datos` bloquean cada tipo
generado en cada herramienta y permiten el mensaje de ejemplo del enunciado.

- [ ] T011 [P] [US2] Escribir `.claude/hooks/test_guarda_datos.py` (FR-004, FR-006, FR-008, R3, contracts/guardas.md). Con valores generados en la prueba, con las mismas funciones auxiliares de `test_detector_datos.py`:
  - **Se bloquean**:
    - Write (`content`), Edit (`new_string`), NotebookEdit (`new_source`), Bash y
      PowerShell (`command`);
    - las 8 herramientas MCP del matcher, incluido un valor anidado dentro de un objeto o
      una lista de `tool_input`.
  - **Se permiten**: el mensaje de ejemplo del enunciado; el `old_string` de un Edit que
    contiene un valor, porque solo se revisa el texto nuevo.
  - **Mensajes**: stderr tiene el tipo y la línea, y nunca contiene el valor; con varios
    hallazgos, aparecen todos separados por `;`.
- [ ] T012 [US2] Implementar `.claude/hooks/guarda_datos.py` con `comun` y `detector_datos` hasta que pase `test_guarda_datos.py`, con el mensaje del contrato. Origen: FR-004, FR-008, FR-020, FR-023.
- [ ] T013 [US2] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): guarda de datos con forma real`.

**Checkpoint**: la guarda de datos funciona por stdin. La revisión del repositorio llega
en T024.

---

## Phase 5: User Story 3 - No se escribe código sin especificación (Priority: P1)

**Goal**: el código protegido solo se escribe con spec, plan y tareas del ticket de la
rama.

**Independent Test**: en repositorios git temporales, la guarda bloquea en `main`, sin
patrón y sin documentos, y permite en una rama con los tres.

- [ ] T014 [P] [US3] Escribir `.claude/hooks/test_guarda_spec_previa.py` con repositorios git temporales (`git init` en `tmp_path` y ramas creadas en la prueba). Origen: FR-009 a FR-013, R7, R10, R14, data-model.
  - **Bloqueos por la rama o la carpeta**:
    - `main`, una rama sin el patrón `NNN-` y HEAD separado;
    - `099-x` sin `specs/099-*`;
    - dos carpetas `specs/099-*`;
    - falta `tasks.md`, y el mensaje lo nombra.
  - **Permitido**: los tres documentos presentes.
  - **Código protegido**: `src/a/b.py`, `.claude/hooks/x.py`, `.claude/settings.json`,
    `.claude/settings.local.json`, `.mcp.json`, `plugins/p/agents/a.md` y
    `.claude-plugin/marketplace.json`.
  - **Exentos, incluso en `main`**: `docs/x.md`, `specs/x.md`, `.specify/x.md`,
    `.claude/commands/x.md`, `src/a/test_b.py` y `.claude/hooks/test_x.py`.
  - **Destinos por terminal que se detectan**:
    - Bash: `>`, `>>`, `tee`, `cp`, `mv`, `install -t`, `sed -i` y `touch`;
    - PowerShell, como respaldo: `Set-Content`, `Out-File`, `New-Item` y
      `Copy-Item -Destination`.
  - **Destinos que se ignoran**: `2>&1` y `> /dev/null`.
  - **NotebookEdit**: se revisa `notebook_path`.
  - **Fallo cerrado**: si git falla (por ejemplo, `CLAUDE_PROJECT_DIR` no es un
    repositorio), sale con 2.
- [ ] T015 [US3] Implementar `.claude/hooks/guarda_spec_previa.py` con `comun` hasta que pase `test_guarda_spec_previa.py`. Debe:
  - leer la rama con `git -C <raíz> branch --show-current`;
  - usar los mensajes de la tabla del contrato;
  - tomar la lista de código protegido de data-model.

  Origen: FR-009 a FR-013, FR-020, FR-023, R7, R10, R14.
- [ ] T016 [US3] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): guarda de spec previa`.

**Checkpoint**: la guarda de spec previa funciona en repositorios temporales.

---

## Phase 6: User Story 4 - El código queda formateado tras cada edición (Priority: P2)

**Goal**: cada `.py` escrito o editado queda formateado, sin bloquear nunca.

**Independent Test**: un `.py` mal formateado queda limpio para `ruff format --check`; uno
con un error de sintaxis se conserva y se informa.

- [ ] T017 [P] [US4] Escribir `.claude/hooks/test_formatear_python.py` (FR-014, FR-015, R12), con un proyecto temporal con `pyproject.toml` y el script lanzado con `sys.executable` del `.venv`:
  - un `.py` mal formateado queda limpio para `ruff format --check`;
  - un `.md` no se toca;
  - un `.py` con un error de sintaxis devuelve salida 0 y en stdout el JSON `hookSpecificOutput.additionalContext` con "No se pudo formatear", y el archivo queda igual;
  - un archivo inexistente devuelve salida 0;
  - nunca sale con 2.
- [ ] T018 [US4] Implementar `.claude/hooks/formatear_python.py`, que ejecuta `sys.executable -m ruff format <archivo>` con la raíz como directorio de trabajo, hasta que pase `test_formatear_python.py`. Origen: FR-014, FR-015, FR-023, R12.
- [ ] T019 [US4] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): formato con ruff tras cada edición`.

**Checkpoint**: el formato funciona por stdin.

---

## Phase 7: User Story 5 - Herramientas destructivas del MCP de GitHub (Priority: P2)

**Goal**: `projects_write` solo permite `update_project_item`. La denegación por nombre de
las otras herramientas llega en T025.

**Independent Test**: los tests de `guarda_mcp_github` permiten `update_project_item` y
bloquean los otros nueve métodos.

- [ ] T020 [P] [US5] Escribir `.claude/hooks/test_guarda_mcp_github.py` (FR-024, R4, contracts/guardas.md):
  - `update_project_item` sale con 0;
  - los otros nueve métodos del esquema (`add_project_item`, `update_project_items`, `delete_project_item`, `create_project_status_update`, `create_project_view`, `update_project_view`, `delete_project_view`, `create_project` y `create_iteration_field`) salen con 2 y el mensaje del contrato;
  - sin `method`, sale con 2 y el texto `(ausente)`;
  - un `method` que no es texto y un `tool_input` que no es un objeto salen con 2.
- [ ] T021 [US5] Implementar `.claude/hooks/guarda_mcp_github.py` con `comun` hasta que pase `test_guarda_mcp_github.py`. Origen: FR-024, FR-020, FR-023, R4.
- [ ] T022 [US5] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): guarda de projects_write`.

**Checkpoint**: las cinco piezas funcionan por stdin.

---

## Phase 8: Integración, pasos 3 y 4 del plan

**Purpose**: incorporar los tests a la suite, revisar el repositorio completo y registrar
las guardas y las denegaciones.

- [ ] T023 En `pyproject.toml`, `[tool.pytest.ini_options]`: `testpaths = ["src", ".claude/hooks"]` y `pythonpath = [".claude/hooks"]`, conservando `--import-mode=importlib`. `uv run pytest`, sin argumentos, recoge `src/` y `.claude/hooks/` y queda en verde (R8).
- [ ] T024 Escribir `.claude/hooks/test_revision_repositorio.py` (FR-007, SC-002, R8):
  - **Recorrido**: `git ls-files -z`; salta los binarios (un byte nulo en los primeros
    8 KB) y aplica `detector_datos.buscar`.
  - **Test 1, estado actual**: sin hallazgos. Si falla, informa `archivo:línea:tipo`,
    nunca el valor.
  - **Test 2, muestra generada**: la misma función de recorrido, aplicada a archivos de
    `tmp_path` con una muestra generada de cada tipo, detecta el 100 %.

  Si el test 1 encuentra algo en el repositorio, se corrige el archivo afectado y no el
  detector, y se informa a la analista.
- [ ] T025 Actualizar `.claude/settings.json` exactamente según [contracts/settings-json.md](contracts/settings-json.md):
  - conserva `env` y `enabledMcpjsonServers`;
  - añade `hooks`, con cuatro entradas `PreToolUse` y una `PostToolUse`, en forma exec y con `onFailure`;
  - sustituye `permissions.deny` por las **58 entradas** del contrato, en ese orden, con `Read(!**/.env.example)` y `Edit(!**/.env.example)` detrás de las reglas de `**/.env.*`.

  Origen: FR-003, FR-016, FR-017, FR-022, R1 a R6, R14. Los hooks de esta sesión no se recargan: se activan al reiniciar (T035).
- [ ] T026 Escribir `.claude/hooks/test_configuracion.py` con los invariantes de [contracts/settings-json.md](contracts/settings-json.md), leyendo `.claude/settings.json` con `json`. Origen: FR-003, FR-016, FR-017, FR-022, R3, R6, R14.
  - **Hooks**:
    - cada matcher solo contiene `[A-Za-z0-9_|]`;
    - las 4 guardas llevan `onFailure: "block"` y `timeout` ≤ 10, y el formato,
      `onFailure: "continue"`;
    - cada script de `args` existe en `.claude/hooks/`.
  - **Denegaciones**:
    - exactamente 58 entradas;
    - ninguna empieza por `PowerShell(` ni por `Bash(grep`;
    - cada `!**/.env.example` va detrás de su regla `**/.env.*`;
    - ninguna regla de Bash coincide con `cat .env.example`, interpretando `*` como
      cualquier secuencia;
    - están las 7 herramientas MCP del contrato.
  - **FR-017**: ninguna herramienta `mcp__github__*` mencionada en
    `.claude/skills/siguiente-ticket/SKILL.md`, `.claude/commands/abrir-pr.md` o
    `.claude/commands/comentar-avance.md` está denegada.
- [ ] T027 Ejecutar `uv run pytest`, `uv run ruff check .` y `uv run ruff format --check .`, todo en verde. Commits:
  - `test(hooks): revisión del repositorio en la suite`, con T023 y T024;
  - `feat(config): registra las guardas y amplía permissions.deny`, con T025 y T026.

**Checkpoint**: la suite completa en verde, y las guardas registradas para la próxima
sesión.

---

## Phase 9: User Story 6 - Convenciones por ruta para tests y herramientas MCP (Priority: P3)

**Goal**: las convenciones de pruebas y de herramientas MCP se cargan solo en sus archivos.

**Independent Test**: el frontmatter de las dos reglas declara exactamente sus globs, y
`test_configuracion.py` lo comprueba.

- [ ] T028 [P] [US6] Crear `.claude/rules/tests.md` con frontmatter YAML `paths:` como lista y el único elemento `"**/test_*.py"` (R13). Contenido de FR-018:
  - el test va junto al módulo;
  - solo datos ficticios;
  - los valores con forma real se construyen en tiempo de ejecución;
  - los casos obligatorios (a)–(g) de la constitución.
- [ ] T029 [P] [US6] Crear `.claude/rules/herramientas-mcp.md` con frontmatter `paths:` y el único elemento `"src/servidor_mcp/**/*.py"` (R13). Contenido de FR-019, del principio IV:
  - descripción inequívoca de qué hace y qué no;
  - errores estructurados que dicen si se puede reintentar;
  - contenido separado de metadatos;
  - solo datos ficticios.
- [ ] T030 [US6] Ampliar `.claude/hooks/test_configuracion.py`: lee el frontmatter de las dos reglas sin dependencias externas (entre los dos `---`) y comprueba que `paths` contiene exactamente su glob (FR-018, FR-019, R13). Ejecutar `uv run pytest` en verde. Commit: `feat(rules): reglas por ruta para tests y herramientas MCP`.

**Checkpoint**: las seis historias quedan cubiertas por tests automáticos.

---

## Phase 10: Polish & Cross-Cutting Concerns, paso 6 del plan (documentación)

- [ ] T031 [P] `DECISIONES.md`, nueva entrada 4, "Guardas de Claude Code", con una línea por decisión, sin partir líneas, y el detalle remitido a `specs/003-guardas-claude-code/research.md`. Decisiones:
  - hooks en Python con `uv run` en forma exec (R1);
  - fallo cerrado en dos capas (R2);
  - matchers como listas exactas (R3);
  - las 7 herramientas MCP denegadas, y `projects_write` limitada por una guarda (R4);
  - PowerShell apagada, con las guardas como respaldo (R5);
  - denegaciones como primera barrera, la excepción `!**/.env.example` y por qué `grep` no está (R6);
  - ruta del plugin (R7);
  - `settings.local.json` protegido (R14);
  - riesgos residuales 1–4 del plan.

  En la entrada 2, la desviación temporal de II y X queda cerrada por la entrada 4, salvo la revisión previa, que sigue hasta #4.
- [ ] T032 [P] `README.md`, nueva sección breve "Guardas del entorno" (plan, "Cambios en la documentación"; R14):
  - qué bloquea cada guarda;
  - que requieren `uv` en el `PATH` y se cargan al iniciar la sesión;
  - las frases exactas "Ejecute `uv sync` antes de abrir Claude Code" y "Con las guardas activas, no cambie a una rama sin `.claude/hooks/`; si ocurre, reinicie la sesión".
- [ ] T033 Comprobar que `git diff main -- CLAUDE.md` está vacío y que `CLAUDE.md` sigue en 40 líneas o menos. Commit: `docs: decisiones y README de las guardas del entorno`.

---

## Phase 11: Validación, paso 7 del plan (commit, pausa y quickstart)

**Purpose**: comprobar en una sesión real lo que los tests prueban por stdin. Los
escenarios son los de [quickstart.md](quickstart.md).

- [ ] T034 Comprobación previa a la pausa:
  - `uv run pytest`, `uv run ruff check .` y `uv run ruff format --check .` en verde;
  - `git status --porcelain` vacío;
  - todo commiteado, para que las ramas temporales tengan `.claude/hooks/`.

  Informar del resultado y continuar con T035.
- [ ] T035 [MANUAL] **Pausa para reiniciar la sesión**. Claude se detiene aquí y lo avisa. La analista:
  1. cierra la sesión;
  2. ejecuta `uv sync` en una terminal;
  3. abre una sesión nueva de Claude Code en la raíz, en `003-guardas-claude-code`;
  4. comprueba con `/hooks` que hay cinco entradas (cuatro `PreToolUse` y una `PostToolUse`);
  5. escribe "continúa tasks.md del ticket #3 desde T036".
- [ ] T036 [MANUAL] Desde una terminal fuera de Claude Code, crear `.env.local` y `secrets/prueba.txt` con contenido ficticio (`VARIABLE_FICTICIA=valor-de-prueba`). Confirmar a Claude que están creados.
- [ ] T037 Crear las ramas temporales desde `003-guardas-claude-code`, sin cambiar de rama: `git branch prueba-sin-ticket` y `git branch 099-prueba` (quickstart, requisitos; R14).
- [ ] T038 [US1] Quickstart Q1–Q3: secretos bloqueados por Read y Bash; `grep -r` bloqueado; `.env.example`, `grep -n .env README.md`, la herramienta Grep y `git grep` permitidos. Anotar el resultado de cada escenario.
- [ ] T039 [US2] Quickstart Q4–Q6: tarjeta, NIT y cédula calculados en la propia petición y bloqueados; mensaje de ejemplo permitido; comentario con una credencial construida en la sesión bloqueado antes de publicarse en #3. Si llegara a publicarse, la analista lo borra a mano en GitHub y se registra como fallo.
- [ ] T040 [US3] Quickstart Q7–Q11:
  - en `099-prueba`, Write y `echo >` hacia `src/` bloqueados;
  - en `prueba-sin-ticket`, `.claude/settings.json` y `.claude/settings.local.json` bloqueados, y `docs/` y `specs/` permitidos;
  - en `003-guardas-claude-code`, un `.py` mal formateado queda formateado y uno con un error de sintaxis se informa.

  Volver a `003-guardas-claude-code` y borrar los archivos de prueba.
- [ ] T041 [MANUAL] [US5] Quickstart Q12: la analista abre `/mcp`, servidor `github`, y comprueba que los 7 nombres denegados del contrato existen tal cual y que las herramientas marcadas como destructivas son `delete_repository`, `delete_file` y `projects_write`. Comunica el resultado a Claude.
- [ ] T042 [US5] Quickstart Q13–Q15:
  - `delete_file` sobre `no-existe.txt`, denegado;
  - `projects_write` con `delete_project_item` y un `item_id` inexistente, bloqueado por la guarda, y con `update_project_item` del Status de #3 a "In Progress", permitido sin cambios;
  - `/siguiente-ticket abc` y `/comentar-avance plan` funcionan.
- [ ] T043 [US6] Quickstart Q16–Q17: las reglas aparecen al abrir sus archivos, y una guarda tarda menos de 1 s (SC-004).
- [ ] T044 [MANUAL] Quickstart Q18, fallo cerrado. La analista renombra `.claude/hooks/guarda_secretos.py` desde fuera de Claude Code; Claude intenta leer `README.md` y debe quedar bloqueado por `onFailure: "block"`; la analista restaura el nombre desde fuera.
- [ ] T045 [MANUAL] Desde fuera de Claude Code, borrar `.env.local` y la carpeta `secrets/`.
- [ ] T046 Limpieza. En `003-guardas-claude-code`, `git branch -d prueba-sin-ticket` y `git branch -d 099-prueba`; deben funcionar con `-d` porque no tienen commits propios. Borrar cualquier archivo de prueba. `git status --porcelain` vacío.
- [ ] T047 Registrar la validación:
  - marcar `[X]` las tareas hechas;
  - si algún escenario falló, corregirlo con commits nuevos, sin `--amend`, y repetir el escenario.

  Commit: `docs(specs): validación del quickstart del ticket #3`.
- [ ] T048 Ejecutar `/abrir-pr`. Abre el PR con `Closes #3`, mueve el ticket a "In review" y comenta; la revisión previa sigue siendo la de transición hasta #4. Detenerse sin fusionar.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (fase 1)**: sin dependencias.
- **Foundational (fase 2)**: depende de la fase 1 y bloquea todas las guardas.
- **Guardas (fases 3–7)**: dependen de la fase 2. Son independientes entre sí; se hacen en
  el orden del plan (US1 → US2 → US3 → US4 → US5).
- **Integración (fase 8)**:
  - T024 depende de T006 y de T023;
  - T025 depende de que existan los cinco scripts, de las fases 3–7;
  - T026 depende de T025.
- **Reglas (fase 9)**: T030 depende de T026.
- **Documentación (fase 10)**: depende de las fases 8 y 9, que fijan lo que se documenta.
- **Validación (fase 11)**: depende de todo lo anterior y va estrictamente en orden. T035
  es una pausa obligatoria.

### Within Each Story

- El test se escribe antes que el script y debe fallar primero.
- Un commit por fase, sin `--amend`.

### Parallel Opportunities

- T003 ∥ T005: tests de `comun` y del detector, en archivos distintos.
- Primer paso de cada guarda, cuando la fase 2 termina: T008 ∥ T011 ∥ T014 ∥ T017 ∥ T020
  (tests en archivos distintos). Las implementaciones también pueden ir en paralelo; los
  commits, uno por guarda.
- T028 ∥ T029; T031 ∥ T032.

## Parallel Example: guardas tras la fase 2

```text
T008 test_guarda_secretos.py
T011 test_guarda_datos.py
T014 test_guarda_spec_previa.py
T017 test_formatear_python.py
T020 test_guarda_mcp_github.py
```

## Implementation Strategy

### MVP First

1. Fases 1 y 2.
2. Fase 3 (US1, secretos), la guarda más urgente por el principio VIII.
3. Para un MVP parcial: T023, T025 con solo `guarda_secretos` registrada, y validación de
   Q1–Q3. El plan completo, sin embargo, registra todo junto en T025.

### Incremental Delivery

Cada fase de guarda termina en un commit con sus tests en verde. El registro en
`settings.json` (T025) es el único punto en que las guardas pasan a actuar, y solo desde
la sesión nueva (T035).

## Notes

- Tareas manuales: T035, T036, T041, T044 y T045.
- T037–T040, T042, T043 y T046 las ejecuta Claude en la sesión nueva, a petición de la
  analista.
- `CLAUDE.md` no cambia.
- No se editan las skills de Spec Kit.
