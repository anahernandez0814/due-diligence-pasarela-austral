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
- **Formato manual hasta T036**: según la documentación de hooks, "Direct edits to hooks
  in settings files are normally picked up automatically by the file watcher". Por eso es
  probable que las guardas y el formato se activen en esta misma sesión al guardar
  `settings.json` en T026, no solo al reiniciar. Aun así, cada fase termina con
  `uv run ruff format .claude/hooks` y `uv run ruff check .claude/hooks` hasta T036, por
  si el formato no se activa. El reinicio de T036 se mantiene.
- **Tests antes de T024**, mientras `pyproject.toml` no incluye `.claude/hooks`:
  `uv run pytest .claude/hooks -o pythonpath=.claude/hooks`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: confirmar el punto de partida.

- [X] T001 Confirmar el punto de partida:
  - la rama activa es `003-guardas-claude-code`;
  - `git log --oneline main..HEAD` contiene los commits de spec, plan, correcciones,
    checklist y tareas;
  - `git status --porcelain` está vacío;
  - el issue #3 está en "In Progress" (`mcp__github__projects_list`,
    `list_project_items`, `field_names: ["Status"]`);
  - `uv run pytest` está en verde (4 tests).
- [X] T002 Confirmar lo que todavía no existe y la versión:
  - no existen `.claude/hooks/` ni `.claude/rules/`;
  - `.claude/settings.json` tiene las 6 denegaciones del ticket #1 y no tiene `hooks`;
  - `claude --version` es 2.1.295 o posterior, necesario para `onFailure` (R2).

  Si algo difiere, detenerse e informar.
- [X] T003 [MANUAL] Quickstart Q12, antes de escribir código (FR-016, R4). La analista abre `/mcp`, servidor `github`, y comprueba:
  - que existen tal cual `delete_file`, `create_or_update_file`, `push_files`, `merge_pull_request`, `create_repository` y `fork_repository`;
  - que `delete_repository` **no** aparece con los toolsets actuales, porque su denegación es preventiva;
  - que las marcadas como destructivas son `delete_file` y `projects_write`, y que `projects_write` tiene los 10 métodos de R4.

  Comunica el resultado a Claude. Si algún nombre difiere, se corrigen el contrato y T027 antes de seguir.

  **Resultado (2026-10-16)**: hay 42 herramientas expuestas y todo coincide con lo anterior, también con la consulta `tools/list` de la revisora con los mismos toolsets. El dato inicial de R4, que contaba `delete_repository` como expuesta, se corrigió en `c25b6f5`.

**Checkpoint**: rama limpia, nombres del MCP confirmados y ninguna guarda creada todavía.

---

## Phase 2: Foundational (Blocking Prerequisites), paso 1 del plan

**Purpose**: los módulos que usan todas las guardas y la revisión del repositorio.

**⚠️ CRITICAL**: ninguna guarda puede empezar antes de terminar esta fase.

- [X] T004 [P] Escribir `.claude/hooks/test_comun.py`, según la interfaz común de [contracts/guardas.md](contracts/guardas.md), R1 y R2. Debe cubrir:
  - **lectura de stdin**: JSON válido; JSON inválido, que lanza error;
  - **raíz**: `CLAUDE_PROJECT_DIR` tiene prioridad sobre `cwd`;
  - **normalización de rutas**: `\` → `/`, relativa a la raíz, rutas fuera de la raíz y
    mayúsculas;
  - **división de comandos**: `;`, `&&`, `||`, `|`, redirecciones `<`, `>` y `>>`, y
    comillas simples y dobles, con `shlex` y `punctuation_chars`;
  - **`bloquear()`**: sale con 2 y escribe una sola línea en stderr con el formato
    `[<guarda>] <motivo>. <qué hacer>.`;
  - **envoltorio de fallo cerrado**: ante una excepción, sale con 2 y escribe
    `[<guarda>] La guarda falló (<TipoDeError>); la acción se bloquea por precaución.`;
  - **extractor de texto ejecutable** (R9, decisión 1; R10; U3, C2 y D1 de la segunda
    pasada del análisis):
    - **comandos interiores**: devuelve como comando interior el argumento de `bash -c`,
      `sh -c`, `eval`, `powershell -Command`, `pwsh -c` y el cuerpo de un heredoc que
      alimenta a `bash` o `sh`, también detrás de `uv run`;
    - **anidamiento**: hasta 3 niveles de anidamiento devuelve los comandos interiores; a
      partir del 4.º marca anidamiento excesivo;
    - **fallo de análisis**: un comando interior con comillas sin cerrar, que `shlex` no
      puede analizar, se devuelve como texto de código;
    - **intérpretes, un test por variante (C2)**: devuelve como texto de código el
      argumento de `python -c`, `python3 -c`, `python3.12 -c`, `py -c`, `py -3 -c`,
      `py -3.12 -c`, `node -e`, `node --eval`, `node -p`, `node --print`, `perl -e`,
      `perl -E` y `ruby -e`, el de `uv run python -c` y `uv run --no-project python -c`,
      y el cuerpo de `python - <<'FIN'`;
    - **heredocs que no son código**: `git commit -F - <<'FIN'` y `cat > archivo <<'FIN'`
      no devuelven ni texto de código ni comandos interiores (D1).
- [X] T005 Implementar `.claude/hooks/comun.py`, solo con la biblioteca estándar, hasta que pase `test_comun.py`, incluido el extractor de texto ejecutable que comparten `guarda_secretos` y `guarda_spec_previa` (contracts/guardas.md, interfaz común; R1, R2, R9, R10).
- [X] T006 [P] Escribir `.claude/hooks/test_detector_datos.py` con los casos mínimos de [contracts/detector-datos.md](contracts/detector-datos.md) (FR-005, FR-006, R11). Todos los positivos se generan en la prueba:
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
- [X] T007 Implementar `.claude/hooks/detector_datos.py` con `buscar(texto) -> list[tuple[str, int]]` y los tipos `"tarjeta"`, `"nit"`, `"cedula"` y `"credencial"`, hasta que pase `test_detector_datos.py` (FR-005, FR-006, R11). Las expresiones regulares usan clases de caracteres, de modo que no coinciden consigo mismas.
- [X] T008 Ejecutar `uv run pytest .claude/hooks -o pythonpath=.claude/hooks`, `uv run ruff format .claude/hooks` y `uv run ruff check .claude/hooks`, todo en verde. Commit: `feat(hooks): módulos comunes y detector de datos con forma real`.

- [X] T008a Correcciones de la revisión de la parada B (contracts/guardas.md, interfaz común; contracts/detector-datos.md; R9 y R11). Tests primero, que deben fallar, en `.claude/hooks/test_comun.py` y `.claude/hooks/test_detector_datos.py`; después, el código en `comun.py` y `detector_datos.py`. Los 9 sondeos de la revisora pasan a ser tests:
  1. **Heredocs**: `<<` no cuenta dentro de `<<<` (`(?<!<)<<(?!<)`). `cat <<< "FIN"` seguido de una línea con `python -c` que abre `.env` devuelve las dos líneas, y la segunda como código. Un heredoc sin delimitador de cierre no se quita: con `echo "<<X"` y en la línea siguiente `cat .env`, la segunda línea queda como subcomando.
  2. **Tarjeta y decimales**: `(?<!\d[.,])` en el patrón. Con semilla fija, 20.000 `repr(random.random())` dan 0 hallazgos.
  3. **Sustitución de comandos**: `echo "$(cat .env)"` y `` echo `cat .env` `` devuelven `cat .env` como comando interior de nivel 1. `echo '$(cat .env)'`, entre comillas simples, no.
  4. **Tuberías**: `echo "print(open('.env').read())" | python` devuelve el texto de la etapa anterior como código; `cat <<'FIN' | python3`, con el cuerpo en las líneas siguientes, devuelve el cuerpo como código; `echo "cat .env" | bash` devuelve un comando interior que contiene `cat .env` (el texto de la etapa anterior, `echo cat .env`).
  5. **Herestrings**: `python <<< "X"` devuelve `X` como código; `bash <<< "cat a"` devuelve `cat a` como comando interior.
  6. **Envoltorios**: `FOO=1 python -c "X"`, `env -i FOO=1 python -c "X"`, `exec`, `command`, `nohup`, `time`, `nice -n 5`, `timeout -s KILL 5` y `uv run --with x --python 3.12 python -c "X"` devuelven `X` como código.
  7. **`cmd`**: `cmd //c "type .env"`, `cmd /c` y `cmd /k` devuelven el comando interior, analizado sin `\` como escape.
  8. **Rutas de Git Bash**: con la raíz `D:\AIReadyOrquestador`, `/d/AIReadyOrquestador/src/due_diligence/x.py` queda `src/due_diligence/x.py`. La conversión solo se aplica en Windows; en otros sistemas, el test se salta.

  Ejecutar pytest y ruff sobre `.claude/hooks`, en verde, y volver a ejecutar los 9 sondeos. Commit: `fix(hooks): correcciones de la revisión de la parada B`.

- [X] T008b Correcciones de la revisión de la parada B2: heredocs que conocen las comillas (contracts/guardas.md, interfaz común; R9). Tests primero, que deben fallar, en `.claude/hooks/test_comun.py`; después, el código en `comun.py`:
  1. **Comillas**: un `<<` dentro de comillas simples o dobles, o en un comentario, es texto literal y no abre heredoc. Dentro de `$(…)` empieza un contexto nuevo, aunque vaya entre comillas dobles. Con `echo "<<X"`, `cat .env` y `X` en tres líneas, `cat .env` se analiza como subcomando.
  2. **El cuerpo viaja con su comando**: el texto de cada `$(…)`, y el de las palabras que se analizan como comando interior o como código, llevan sus heredocs completos.
     - `git commit -m "$(cat <<'EOF'`, una línea de mensaje, `EOF` y `)"` (R1) se analiza sin excepción, y su comando interior `cat` no produce código.
     - El mismo patrón con `python3 <<'EOF'` devuelve el cuerpo como código.
  3. **Marca sin cuerpo**: `_tokenizar` nunca lanza `IndexError`; una marca sin cuerpo lanza `ValueError`, y en un comando interior se aplica la vuelta a texto.
  4. **Corpus de regresión**, parametrizado: comandos legítimos del proyecto que se analizan sin excepción y sin código ni comandos interiores que nombren secretos. Incluye el commit R1, otro commit con heredoc cuyo mensaje menciona `.env` y `secrets/`, `git commit -m "protege .env"`, `git log --format='%h %s' -3`, `gh api repos/x/y/issues --jq '.[] | .title'`, `uv run pytest -q`, `uv run ruff check .` y `git switch main`.

  Ejecutar pytest con `-W error` y ruff sobre `.claude/hooks`, en verde, y volver a ejecutar los 9 sondeos de la parada B y los casos nuevos. Commit: `fix(hooks): heredocs que conocen las comillas`.

- [X] T008c Correcciones de la revisión de la parada B3: comentarios con la regla de bash (contracts/guardas.md, interfaz común; R9). Tests primero, que deben fallar, en `.claude/hooks/test_comun.py`; después, el código en `comun.py`. El recorrido quita los comentarios y `shlex` no los trata (`commenters = ""`). `#` abre comentario solo al principio de una palabra (al principio del texto o de una línea, tras espacio o tabulador, o tras `;`, `&`, `|`, `(` o `)`) y fuera de comillas; llega hasta el salto de línea, sin incluirlo. En PowerShell, la misma regla como respaldo.
  1. `echo # x` y en la línea siguiente `python -c "open('.env')"`: el código se detecta.
  2. `echo a#b; cat .env`: `["cat", ".env"]` es un subcomando.
  3. `# instala` y en la línea siguiente `uv sync`, y `git log --format='#%h %s'`: sin cambios.
  4. `echo ${#x}` y `echo $#`: el `#` no es comentario.
  5. `test_heredoc_en_un_comentario_es_texto` comprueba el resultado completo.

  Ejecutar pytest con `-W error` y ruff sobre `.claude/hooks`, en verde, y volver a ejecutar los 9 sondeos y los de comentarios. Commit: `fix(hooks): comentarios con la regla de bash`.

**Checkpoint**: `comun` y `detector_datos` probados. Ninguna guarda registrada.

---

## Phase 3: User Story 1 - Los secretos no se tocan desde Claude Code (Priority: P1) 🎯 MVP

**Goal**: ninguna herramienta de Claude Code abre ni modifica archivos de secretos, y
`.env.example` sigue accesible.

**Independent Test**: los tests de extremo a extremo de `guarda_secretos` bloquean `.env`,
`.env.local` y `secrets/` por Read, Grep, Bash y PowerShell, y permiten `.env.example`.

- [X] T009 [P] [US1] Escribir `.claude/hooks/test_guarda_secretos.py` (FR-001, FR-002, R9, contracts/guardas.md).
  - **Montaje**: unitarios de la función de decisión y de extremo a extremo, que lanzan
    el script con `sys.executable`, un JSON por stdin y `CLAUDE_PROJECT_DIR=tmp_path`. Los
    archivos de secretos se crean en `tmp_path`, con contenido ficticio y un marcador.
  - **Montaje de las búsquedas recursivas**: `tmp_path` tiene un `.env` en la raíz y una
    carpeta `src/` sin secretos (R9, decisión 2).
  - **Se bloquean (salida 2)**:
    - Read, Write y Edit de `.env`, `.env.local`, `.ENV`, `x.key` y `secrets/a.txt`;
    - NotebookEdit con `notebook_path` en `secrets/`;
    - Grep con `path` o `glob` hacia secretos;
    - Glob con un patrón que nombra `.env`;
    - Bash, rutas: `head .env.local`, `head .env.staging` (aunque no exista; en la sesión también lo para la regla `Read`, I6),
      `cat ./secrets/a.txt`, `cp .env.local x`, `grep TOKEN .env.local`, redirección
      `< .env` y un comodín que se expande a `.env.local` (US1-2, G2, G3);
    - Bash, búsquedas recursivas cuya raíz contiene `.env`: `grep -r TOKEN .`,
      `rg --no-ignore TOKEN`, `rg --hidden TOKEN`, `rg -u TOKEN`, `find . -exec cat {} +`
      y `find . | xargs cat` (I1);
    - Bash, texto ejecutable que nombra un secreto (US1-6, C1): `python -c` y
      `uv run python -c` con código que abre `.env`, `node -e` con código que lee
      `.env.local`, `bash -c "cat .env"`, `eval "cat .env"` y un heredoc
      `python - <<'FIN'` cuyo cuerpo abre `.env`;
    - Bash, shells anidados con las mismas reglas que el exterior (U3):
      `bash -c "grep -r TOKEN ."`, porque la raíz tiene `.env`, y un anidamiento de 4
      niveles (`bash -c` dentro de `sh -c` dentro de `bash -c` dentro de `eval`), que se
      bloquea por precaución;
    - PowerShell, como respaldo: `Get-Content .env.local`,
      `Get-ChildItem -Recurse | Select-String TOKEN` sobre la raíz y
      `pwsh -Command "Get-Content .env"`.
  - **Se permiten (salida 0)**:
    - Read y Edit de `.env.example`;
    - Grep con `pattern` `.env` en `src/`;
    - `grep -n .env README.md`, `grep -rn ".env" src/` (en `src/` no hay secretos),
      `git grep ".env"` y `rg TOKEN`;
    - `python -c "print(1)"`, y `python -c` con `x.keys()`, con `secrets.token_hex(8)`,
      con `os.environ` y con el texto `.environment` (U2);
    - `bash -c "grep '.env' src/"`, porque `.env` es el patrón de búsqueda (U3, FR-002);
    - `git commit -m "protege .env"` y un `git commit -F - <<'FIN'` cuyo mensaje menciona
      `.env`, porque el heredoc no alimenta a un intérprete.
  - **Tiempo**: el recorrido de la raíz de `tmp_path` termina en menos de 1 s (SC-004).
  - **Mensajes**: stderr nunca contiene el marcador y sigue los formatos del contrato.
- [X] T010 [US1] Implementar `.claude/hooks/guarda_secretos.py` con `comun` hasta que pase `test_guarda_secretos.py`. Debe:
  - revisar por herramienta según la tabla del contrato;
  - excluir el patrón de búsqueda de `grep`, `egrep`, `fgrep`, `rg`, `git grep`, `Select-String` y `findstr`;
  - expandir los comodines contra la raíz;
  - con el extractor de `comun.py`, analizar los comandos interiores de shells, `eval` y heredocs a `bash` o `sh` con estas mismas reglas, y revisar como texto, con el patrón de nombres del contrato (U2), el código de `python`, `node`, `perl` y `ruby` (R9, decisión 1);
  - bloquear por precaución más de 3 niveles de anidamiento;
  - bloquear las búsquedas recursivas solo si su raíz, resuelta contra el `cwd` del JSON y recorrida con `os.walk` podando solo `.git`, contiene archivos de secretos (R9, decisión 2).

  Origen: FR-001, FR-002, FR-020, FR-023, R9.
- [X] T011 [US1] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): guarda de secretos`.
- [X] T011a Corrección de la revisión de la parada C: UTF-8 en los flujos, independiente del entorno (contracts/guardas.md, interfaz común). Tests primero, que deben fallar; después, el código en `comun.py`:
  - `comun.ejecutar`, antes de leer la entrada, reconfigura `sys.stdin`, `sys.stdout` y `sys.stderr` con `encoding="utf-8"`;
  - los tests de extremo a extremo lanzan el script quitando del entorno `PYTHONUTF8` y `PYTHONIOENCODING`;
  - un test con una ruta con tilde en el JSON de stdin, y otro que comprueba que un mensaje con tilde llega bien en stderr.

  pytest pasa con y sin esas variables. Commit: `fix(hooks): UTF-8 en los flujos de las guardas`.

**Checkpoint**: la guarda de secretos funciona por stdin; todavía no está registrada.

---

## Phase 4: User Story 2 - Ningún archivo recibe datos con forma real ni credenciales (Priority: P1)

**Goal**: lo que se escribe, se ejecuta o se publica por el MCP de GitHub no lleva datos
con forma real.

**Independent Test**: los tests de extremo a extremo de `guarda_datos` bloquean cada tipo
generado en cada herramienta y permiten el mensaje de ejemplo del enunciado.

- [X] T012 [P] [US2] Escribir `.claude/hooks/test_guarda_datos.py` (FR-004, FR-006, FR-008, R3, contracts/guardas.md). Con valores generados en la prueba, con las mismas funciones auxiliares de `test_detector_datos.py`:
  - **Se bloquean**:
    - Write (`content`), Edit (`new_string`), NotebookEdit (`new_source`), Bash y
      PowerShell (`command`);
    - las 8 herramientas MCP del matcher, incluido un valor anidado dentro de un objeto o
      una lista de `tool_input`.
  - **Se permiten**: el mensaje de ejemplo del enunciado; el `old_string` de un Edit que
    contiene un valor, porque solo se revisa el texto nuevo.
  - **Mensajes**: stderr tiene el tipo y la línea, y nunca contiene el valor; con varios
    hallazgos, aparecen todos separados por `;`.
- [X] T013 [US2] Implementar `.claude/hooks/guarda_datos.py` con `comun` y `detector_datos` hasta que pase `test_guarda_datos.py`, con el mensaje del contrato. Origen: FR-004, FR-008, FR-020, FR-023.
- [X] T014 [US2] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): guarda de datos con forma real`.

**Checkpoint**: la guarda de datos funciona por stdin. La revisión del repositorio llega
en T025.

---

## Phase 5: User Story 3 - No se escribe código sin especificación (Priority: P1)

**Goal**: el código protegido solo se escribe con spec, plan y tareas del ticket de la
rama.

**Independent Test**: en repositorios git temporales, la guarda bloquea en `main`, sin
patrón y sin documentos, y permite en una rama con los tres.

- [X] T015 [P] [US3] Escribir `.claude/hooks/test_guarda_spec_previa.py` con repositorios git temporales (`git init` en `tmp_path` y ramas creadas en la prueba). Origen: FR-009 a FR-013, R7, R10, R14, data-model.
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
  - **Texto ejecutable, con el extractor de `comun.py` (I7 de la segunda pasada)**:
    - en `099-x`, sin documentos, se bloquean
      `python -c "open('src/a/x.py','w').write('')"`, `bash -c "echo > src/a/x.py"` y
      `cat > src/a/x.py <<'FIN'`;
    - en una rama con los tres documentos, los mismos tres se permiten, porque la guarda
      no distingue lectura de escritura;
    - en cualquier rama, un anidamiento de 4 niveles se bloquea por precaución.
  - **Reconocimiento de código protegido en el texto (U4 de la tercera pasada)**:
    - en `099-x` se bloquean `python -c "open('src/due_diligence/x.py','w')"` y un
      `python -c` con la ruta `'.\\src\\x.py'`;
    - en `099-x` se permiten `python -c "import due_diligence"` y
      `python -c "open('src/due_diligence/test_x.py')"`: un módulo sin ruta y un
      `test_*.py` no cuentan.
  - **NotebookEdit**: se revisa `notebook_path`.
  - **Fallo cerrado**: si git falla (por ejemplo, `CLAUDE_PROJECT_DIR` no es un
    repositorio), sale con 2.
- [X] T016 [US3] Implementar `.claude/hooks/guarda_spec_previa.py` con `comun` hasta que pase `test_guarda_spec_previa.py`. Debe:
  - leer la rama con `git -C <raíz> branch --show-current`;
  - usar los mensajes de la tabla del contrato;
  - tomar la lista de código protegido de data-model;
  - usar el extractor de `comun.py`: los comandos interiores, con estas mismas reglas de destinos, y los textos de código, buscando nombres de código protegido.

  Origen: FR-009 a FR-013, FR-020, FR-023, R7, R10, R14.
- [X] T017 [US3] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): guarda de spec previa`.
- [X] T017a [US3] Corrección de la revisión de la parada D: borrar, restaurar y mover también es modificar (FR-009, FR-012, R10, contracts/guardas.md). Tests primero, que deben fallar, en `.claude/hooks/test_guarda_spec_previa.py`; después, el código en `guarda_spec_previa.py`:
  - destinos nuevos: las palabras que no son opciones de `rm`, `unlink` y `git rm`; las rutas de `git checkout … -- <rutas>` y de `git restore <rutas>` (con o sin `--source`); las fuentes de `mv`; en PowerShell, `Remove-Item`, `del`, `erase`, `rd`, `ri` y las fuentes de `Move-Item`;
  - en `main` se bloquean `rm .claude/settings.json`, `git checkout 003-x -- .claude/settings.json` y `mv src/app/a.py docs/a.py`; en una rama con los tres documentos, se permiten;
  - en `main` se permiten `rm docs/x.md` y `git checkout 003-x`, sin `--`.

  Ejecutar pytest con y sin `PYTHONUTF8`/`PYTHONIOENCODING`, y ruff. Commit: `fix(hooks): borrar, restaurar y mover código protegido`.
- [X] T017b [US3] Corrección de la revisión de la parada E (FR-012, R10, contracts/guardas.md). Tests primero, que deben fallar, en `.claude/hooks/test_guarda_spec_previa.py`; después, el código en `guarda_spec_previa.py`. Se bloquean en `main` y se permiten con los tres documentos:
  1. **Carpetas que contienen código protegido**, al borrar, restaurar o mover (función aparte de la del destino de una copia: la raíz, un ancestro de algo protegido o una carpeta dentro de una zona protegida): `rm -rf .claude`, `rm -rf .`, `git restore .`, `git checkout -- .`, `git checkout 003-x -- .claude`, `mv .claude .claude-viejo` y `Remove-Item -Recurse .claude`. `rm -rf docs` se sigue permitiendo.
  2. **`git checkout` sin `--`**: `git checkout 003-x .claude/settings.json`, `git checkout HEAD src/app/a.py` y `git checkout src/app/a.py` (existe en disco). Se siguen permitiendo `git checkout 003-x`, `git checkout main` y `git checkout -b 004-y main`.
  3. **`git mv` y `git -C`**: `git mv src/app/a.py docs/a.py` y `git -C src rm app/a.py`.
  4. **`cd` dentro del comando**: `cd src && echo x > app/b.py`, `cd src/app; cp /tmp/x.py b.py` y `pushd .claude && rm settings.json`.
  5. **`truncate`**: `truncate -s 0 src/app/a.py`.

  Ejecutar pytest con y sin `PYTHONUTF8`/`PYTHONIOENCODING`, y ruff. Commit: `fix(hooks): carpetas, git checkout, git mv, cd y truncate`.
- [X] T017c [US3] Corrección del cierre de la revisión de la parada E (FR-012, R10, contracts/guardas.md). Tests primero, que deben fallar, en `.claude/hooks/test_comun.py` (el `padre` y el `origen` que anota el extractor) y en `.claude/hooks/test_guarda_spec_previa.py`; después, el código en `comun.py` y `guarda_spec_previa.py`:
  - los comandos interiores heredan la carpeta vigente en el subcomando donde aparecen;
  - un texto de código de intérprete cuenta como código protegido si esa carpeta cuenta según la regla de carpetas, salvo la raíz;
  - se bloquean en `main` y se permiten con los tres documentos: `cd .claude && bash -c 'rm settings.json'`, `cd .claude && eval rm settings.json`, `cd src/app && sh -c 'echo x > b.py'`, `cd src && python -c "open('app/b.py','w')"` y `cd src/app && python3 - <<'EOF'` con `open('b.py','w')` en el cuerpo;
  - se siguen permitiendo en `main`: `cd docs && bash -c 'rm -rf build'`, `cd docs && python -c "print(1)"`, `python -c "print(1)"` en la raíz y `cd src && uv run pytest`.

  Ejecutar pytest con y sin `PYTHONUTF8`/`PYTHONIOENCODING`, y ruff. Commit: `fix(hooks): comandos interiores que heredan el cwd`.

**Checkpoint**: la guarda de spec previa funciona en repositorios temporales.

---

## Phase 6: User Story 4 - El código queda formateado tras cada edición (Priority: P2)

**Goal**: cada `.py` escrito o editado queda formateado, sin bloquear nunca.

**Independent Test**: un `.py` mal formateado queda limpio para `ruff format --check`; uno
con un error de sintaxis se conserva y se informa.

- [X] T018 [P] [US4] Escribir `.claude/hooks/test_formatear_python.py` (FR-014, FR-015, R12), con los archivos en un proyecto temporal con `pyproject.toml` (su configuración de ruff, con `extend-exclude`), el script lanzado con `sys.executable` y la raíz del repositorio en `CLAUDE_PROJECT_DIR`, de la que `uv run` toma el ruff del `uv.lock` (revisión de la parada E):
  - un `.py` mal formateado queda limpio para `ruff format --check`;
  - un `.md` no se toca;
  - un `.py` con un error de sintaxis devuelve salida 0 y en stdout el JSON `hookSpecificOutput.additionalContext` con "No se pudo formatear", y el archivo queda igual;
  - un `.py` en una carpeta de `extend-exclude` no se toca;
  - el script lanzado con el cwd fuera del repositorio formatea igual;
  - sin uv o sin ruff disponibles, `additionalContext` y salida 0;
  - un archivo inexistente devuelve salida 0;
  - nunca sale con 2.
- [X] T019 [US4] Implementar `.claude/hooks/formatear_python.py`, que ejecuta `uv run --project <raíz> --frozen --quiet ruff format --force-exclude <archivo>` con la raíz como directorio de trabajo y decide el éxito solo por el código de salida, hasta que pase `test_formatear_python.py`. Origen: FR-014, FR-015, FR-023, R12.
- [X] T020 [US4] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): formato con ruff tras cada edición`.

**Checkpoint**: el formato funciona por stdin.

---

## Phase 7: User Story 5 - Herramientas destructivas del MCP de GitHub (Priority: P2)

**Goal**: `projects_write` solo permite `update_project_item`. La denegación por nombre de
las otras herramientas llega en T026.

**Independent Test**: los tests de `guarda_mcp_github` permiten `update_project_item` y
bloquean los otros nueve métodos.

- [X] T021 [P] [US5] Escribir `.claude/hooks/test_guarda_mcp_github.py` (FR-024, R4, contracts/guardas.md):
  - `update_project_item` sale con 0;
  - los otros nueve métodos del esquema (`add_project_item`, `update_project_items`, `delete_project_item`, `create_project_status_update`, `create_project_view`, `update_project_view`, `delete_project_view`, `create_project` y `create_iteration_field`) salen con 2 y el mensaje del contrato;
  - sin `method`, sale con 2 y el texto `(ausente)`;
  - un `method` que no es texto y un `tool_input` que no es un objeto salen con 2.
- [X] T022 [US5] Implementar `.claude/hooks/guarda_mcp_github.py` con `comun` hasta que pase `test_guarda_mcp_github.py`. Origen: FR-024, FR-020, FR-023, R4.
- [X] T023 [US5] Ejecutar los tests y ruff sobre `.claude/hooks`, en verde. Commit: `feat(hooks): guarda de projects_write`.

**Checkpoint**: las cinco piezas funcionan por stdin.

---

## Phase 8: Integración, pasos 3 y 4 del plan

**Purpose**: incorporar los tests a la suite, revisar el repositorio completo y registrar
las guardas y las denegaciones.

- [X] T024 En `pyproject.toml`, `[tool.pytest.ini_options]`: `testpaths = ["src", ".claude/hooks"]` y `pythonpath = [".claude/hooks"]`, conservando `--import-mode=importlib`. `uv run pytest`, sin argumentos, recoge `src/` y `.claude/hooks/` y queda en verde (R8).
- [X] T025 Escribir `.claude/hooks/test_revision_repositorio.py` (FR-007, SC-002, R8):
  - **Recorrido**: `git ls-files -z`; salta los binarios (un byte nulo en los primeros
    8 KB) y aplica `detector_datos.buscar`.
  - **Test 1, estado actual**: sin hallazgos. Si falla, informa `archivo:línea:tipo`,
    nunca el valor.
  - **Test 2, muestra generada**: la misma función de recorrido, aplicada a archivos de
    `tmp_path` con una muestra generada de cada tipo, detecta el 100 %.

  Si el test 1 encuentra algo en el repositorio, **no se corrige nada por cuenta propia**:
  detenerse e informar `archivo:línea:tipo`. La analista decide:
  - si es un dato real, se corrige el archivo;
  - si es un falso positivo, se ajusta el detector, con su test en
    `test_detector_datos.py` y una nota en
    [contracts/detector-datos.md](contracts/detector-datos.md).

  Nunca se editan a mano `uv.lock` ni archivos de `.specify/`.
- [X] T026 Actualizar `.claude/settings.json` exactamente según [contracts/settings-json.md](contracts/settings-json.md):
  - conserva `env` y `enabledMcpjsonServers`;
  - añade `hooks`, con cuatro entradas `PreToolUse` y una `PostToolUse`, en forma exec y con `onFailure`;
  - sustituye `permissions.deny` por las **58 entradas** del contrato, en ese orden, con `Read(!**/.env.example)` y `Edit(!**/.env.example)` detrás de las reglas de `**/.env.*`.

  Origen: FR-003, FR-016, FR-017, FR-022, R1 a R6, R14.
  - **Activación**: el observador de archivos suele recoger los hooks en esta misma
    sesión al guardar el archivo, así que es probable que las guardas actúen desde aquí.
    El formato manual con ruff se mantiene hasta T036 por si el formato no se activa, y
    el reinicio de T036 se mantiene.
  - **Si desde aquí aparece un bloqueo `[guarda_…]` inesperado**, detenerse e informar;
    nunca desactivar las guardas ni buscar un rodeo.
- [X] T027 Escribir `.claude/hooks/test_configuracion.py` con los invariantes de [contracts/settings-json.md](contracts/settings-json.md), leyendo `.claude/settings.json` con `json`. Origen: FR-003, FR-016, FR-017, FR-022, R3, R6, R14. Comprueba que las reglas de la **capa de permisos** existen y están bien formadas; su efecto se ve en la sesión, en Q1 y Q13. La guarda se prueba en los tests por stdin (I6, I9).
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
- [X] T028 Ejecutar `uv run pytest`, `uv run ruff check .` y `uv run ruff format --check .`, todo en verde. Commits:
  - `test(hooks): revisión del repositorio en la suite`, con T024 y T025;
  - `feat(config): registra las guardas y amplía permissions.deny`, con T026 y T027.

**Checkpoint**: la suite completa en verde, y las guardas registradas para la próxima
sesión.

---

## Phase 9: User Story 6 - Convenciones por ruta para tests y herramientas MCP (Priority: P3)

**Goal**: las convenciones de pruebas y de herramientas MCP se cargan solo en sus archivos.

**Independent Test**: el frontmatter de las dos reglas declara exactamente sus globs, y
`test_configuracion.py` lo comprueba.

- [X] T029 [P] [US6] Crear `.claude/rules/tests.md` con frontmatter YAML `paths:` como lista y el único elemento `"**/test_*.py"` (R13). Contenido de FR-018:
  - el test va junto al módulo;
  - solo datos ficticios;
  - los valores con forma real se construyen en tiempo de ejecución;
  - los casos obligatorios (a)–(g) de la constitución.
- [X] T030 [P] [US6] Crear `.claude/rules/herramientas-mcp.md` con frontmatter `paths:` y el único elemento `"src/servidor_mcp/**/*.py"` (R13). Contenido de FR-019, del principio IV:
  - descripción inequívoca de qué hace y qué no;
  - errores estructurados que dicen si se puede reintentar;
  - contenido separado de metadatos;
  - solo datos ficticios.
- [X] T031 [US6] Ampliar `.claude/hooks/test_configuracion.py`: lee el frontmatter de las dos reglas sin dependencias externas (entre los dos `---`) y comprueba que `paths` contiene exactamente su glob (FR-018, FR-019, R13). Ejecutar `uv run pytest` en verde. Commit: `feat(rules): reglas por ruta para tests y herramientas MCP`.

**Checkpoint**: las seis historias quedan cubiertas por tests automáticos.

---

## Phase 10: Polish & Cross-Cutting Concerns, paso 6 del plan (documentación)

- [ ] T032 [P] `DECISIONES.md`, nueva entrada 4, "Guardas de Claude Code", con una línea por decisión, sin partir líneas, y el detalle remitido a `specs/003-guardas-claude-code/research.md`. Decisiones:
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

  Comprobar que `DECISIONES.md` completo sigue cabiendo en dos páginas, el límite del enunciado que debe respetar el ticket #14; si no, resumir las entradas.
- [ ] T033 [P] `README.md`, nueva sección breve "Guardas del entorno" (plan, "Cambios en la documentación"; R14):
  - qué bloquea cada guarda;
  - que requieren `uv` en el `PATH`, y que "se cargan al iniciar la sesión y suelen activarse también al guardar `settings.json`; ante la duda, reinicie la sesión";
  - las frases exactas "Ejecute `uv sync` antes de abrir Claude Code" y "Con las guardas activas, no cambie a una rama sin `.claude/hooks/`; si ocurre, reinicie la sesión".
- [ ] T034 Comprobar que `git diff main -- CLAUDE.md` está vacío y que `CLAUDE.md` sigue en 40 líneas o menos. Commit: `docs: decisiones y README de las guardas del entorno`.

---

## Phase 11: Validación, paso 7 del plan (commit, pausa y quickstart)

**Purpose**: comprobar en una sesión real lo que los tests prueban por stdin. Los
escenarios son los de [quickstart.md](quickstart.md).

- [ ] T035 Comprobación previa a la pausa:
  - `uv run pytest`, `uv run ruff check .` y `uv run ruff format --check .` en verde;
  - `git status --porcelain` vacío;
  - todo commiteado, para que las ramas temporales tengan `.claude/hooks/`.

  Informar del resultado y continuar con T036.
- [ ] T036 [MANUAL] **Pausa para reiniciar la sesión**. Claude se detiene aquí y lo avisa. La analista:
  1. cierra la sesión;
  2. ejecuta `uv sync` en una terminal;
  3. abre una sesión nueva de Claude Code en la raíz, en `003-guardas-claude-code`;
  4. comprueba con `/hooks` que hay cinco entradas (cuatro `PreToolUse` y una `PostToolUse`);
  5. escribe "continúa tasks.md del ticket #3 desde T037".
- [ ] T037 [MANUAL] Desde una terminal fuera de Claude Code, crear `.env.local` y `secrets/prueba.txt` con contenido ficticio (`VARIABLE_FICTICIA=valor-de-prueba`). Confirmar a Claude que están creados.
- [ ] T038 Crear las ramas temporales desde `003-guardas-claude-code`, sin cambiar de rama: `git branch prueba-sin-ticket` y `git branch 099-prueba` (quickstart, requisitos; R14).
- [ ] T039 [US1] Quickstart Q1–Q3. Anotar el resultado de cada escenario.
  - **Q1**: secretos bloqueados por Read y Bash, incluido `head .env.staging` (no hace falta que exista). Para cada caso se anota qué capa bloqueó, el prefijo `[guarda_secretos]` o el mensaje de permisos de Claude Code; las dos son un resultado válido (R6, I6).
  - **Q2**: bloqueados `grep -r TOKEN .` (la raíz tiene `.env`) y el código en línea que abre `.env` sin imprimirlo (`python -c` y `uv run python -c`).
  - **Q3**: permitidos `.env.example`, `grep -n .env README.md`, `grep -rn ".env" src/`, la herramienta Grep, `git grep` y `python -c "print(1)"`.
- [ ] T040 [US2] Quickstart Q4–Q6: tarjeta, NIT y cédula calculados en la propia petición y bloqueados; mensaje de ejemplo permitido; comentario con una credencial construida en la sesión bloqueado antes de publicarse en #3. Si llegara a publicarse, la analista lo borra a mano en GitHub y se registra como fallo.
- [ ] T041 [US3] Quickstart Q7–Q11:
  - en `099-prueba`, Write y `echo >` hacia `src/` bloqueados, y `python -c "open('src/due_diligence/x.py','w').close()"` bloqueado por `[guarda_spec_previa]` (G4). Si el archivo llegara a crearse por un fallo, se borra en la limpieza y se registra como fallo;
  - en `prueba-sin-ticket`, una edición de `.claude/settings.json` que no cambia nada (un texto reemplazado por sí mismo) y la escritura de `.claude/settings.local.json`, bloqueadas; después, `git diff --quiet .claude/` termina con 0. `docs/` y `specs/` permitidos;
  - en `003-guardas-claude-code`, un `.py` mal formateado queda formateado y uno con un error de sintaxis se informa.

  Volver a `003-guardas-claude-code` y borrar los archivos de prueba.
- [ ] T042 [US5] Quickstart Q13–Q15:
  - `delete_file` sobre `no-existe.txt`, denegado;
  - `projects_write` con `delete_project_item` y un `item_id` inexistente, bloqueado por la guarda, y con `update_project_item` del Status de #3 a "In Progress", permitido sin cambios;
  - `/siguiente-ticket abc` funciona: su paso 0 usa las herramientas MCP de lectura. No se ejecuta `/comentar-avance plan`, que añadiría una actualización de prueba al comentario "plan" de #3.
- [ ] T043 [US6] Quickstart Q16–Q17. Las reglas aparecen al abrir sus archivos. Una guarda tarda menos de 1 s medida en caliente, desde la segunda llamada de la sesión (tres llamadas seguidas); la primera puede tardar más, ≈ 1,1 s, porque `uv` prepara el entorno (SC-004).
- [ ] T044 [MANUAL] Quickstart Q18, fallo cerrado. La analista renombra `.claude/hooks/guarda_secretos.py` desde fuera de Claude Code; Claude intenta leer `README.md` y debe quedar bloqueado por `onFailure: "block"`; la analista restaura el nombre desde fuera.
- [ ] T045 [MANUAL] Desde fuera de Claude Code, borrar `.env.local` y la carpeta `secrets/`.
- [ ] T046 Limpieza. En `003-guardas-claude-code`, `git branch -d prueba-sin-ticket` y `git branch -d 099-prueba`; deben funcionar con `-d` porque no tienen commits propios. Borrar cualquier archivo de prueba. `git status --porcelain` vacío.
- [ ] T047 Registrar la validación:
  - marcar `[X]` las tareas hechas;
  - si algún escenario falló, corregirlo con commits nuevos, sin `--amend`, y repetir el escenario.

  Commit: `docs(specs): validación del quickstart del ticket #3`.

  T048 no se marca aquí: se marca después de abrir el PR, en un commit nuevo de la misma rama, que se suma al PR.
- [ ] T048 Ejecutar `/abrir-pr`. Abre el PR con `Closes #3`, mueve el ticket a "In review" y comenta; la revisión previa sigue siendo la de transición hasta #4. Detenerse sin fusionar.

  Al ejecutarse en la sesión nueva, valida FR-017 para las herramientas de escritura: `projects_write` con `update_project_item`, `add_issue_comment` y `create_pull_request` pasan por `guarda_datos` y `guarda_mcp_github` sin bloquearse.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (fase 1)**: sin dependencias.
- **Foundational (fase 2)**: depende de la fase 1 y bloquea todas las guardas.
- **Guardas (fases 3–7)**: dependen de la fase 2. Son independientes entre sí; se hacen en
  el orden del plan (US1 → US2 → US3 → US4 → US5).
- **Integración (fase 8)**:
  - T025 depende de T007 y de T024;
  - T026 depende de que existan los cinco scripts, de las fases 3–7;
  - T027 depende de T026.
- **Reglas (fase 9)**: T031 depende de T027.
- **Documentación (fase 10)**: depende de las fases 8 y 9, que fijan lo que se documenta.
- **Validación (fase 11)**: depende de todo lo anterior y va estrictamente en orden. T036
  es una pausa obligatoria.

### Within Each Story

- El test se escribe antes que el script y debe fallar primero.
- Un commit por fase, sin `--amend`.

### Parallel Opportunities

- T004 ∥ T006: tests de `comun` y del detector, en archivos distintos.
- Primer paso de cada guarda, cuando la fase 2 termina: T009 ∥ T012 ∥ T015 ∥ T018 ∥ T021
  (tests en archivos distintos). Las implementaciones también pueden ir en paralelo; los
  commits, uno por guarda.
- T029 ∥ T030; T032 ∥ T033.

## Parallel Example: guardas tras la fase 2

```text
T009 test_guarda_secretos.py
T012 test_guarda_datos.py
T015 test_guarda_spec_previa.py
T018 test_formatear_python.py
T021 test_guarda_mcp_github.py
```

## Implementation Strategy

### MVP First

1. Fases 1 y 2.
2. Fase 3 (US1, secretos), la guarda más urgente por el principio VIII.
3. Para un MVP parcial: T024, T026 con solo `guarda_secretos` registrada, y validación de
   Q1–Q3. El plan completo, sin embargo, registra todo junto en T026.

### Incremental Delivery

Cada fase de guarda termina en un commit con sus tests en verde. El registro en
`settings.json` (T026) es el único punto en que las guardas pasan a actuar. Es probable
que lo hagan desde ese momento, por el observador de archivos, y con seguridad desde la
sesión nueva (T036).

## Notes

- Tareas manuales: T003, T036, T037, T044 y T045.
- T038–T041, T042, T043 y T046 las ejecuta Claude en la sesión nueva, a petición de la
  analista.
- `CLAUDE.md` no cambia.
- No se editan las skills de Spec Kit.
