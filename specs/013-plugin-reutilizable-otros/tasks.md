---

description: "Lista de tareas del ticket #13, plugin reutilizable para otros equipos"
---

# Tasks: Plugin reutilizable para otros equipos

**Input**: documentos de diseño en `specs/013-plugin-reutilizable-otros/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/plugin.md](contracts/plugin.md) y [quickstart.md](quickstart.md).

**Prerequisites**:
- la spec en `acf52f8`, con los tres ajustes de la analista;
- el plan en `0a83b74`, con sus tres ajustes: Q5 obligatoria, solo cuenta el mensaje de la guarda en la traza y las trazas no salen de la carpeta temporal.

**Tests**: obligatorios (constitución X; FR-004, FR-007, FR-009 y FR-012).
- Los genéricos van junto al código, dentro del plugin.
- Los propios de este repositorio van en `.claude/hooks/`.
- Ningún test determinista llama al modelo. Las únicas llamadas son las de Q3, Q4 y Q5 con `claude -p`.

**Organization**: ritmo liviano, sin paradas intermedias. Se construye de corrido hasta el barrido (T027) y **se detiene antes de `/abrir-pr`**.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La verificación del cierre del #13 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US4).
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md) o Q# del [quickstart](quickstart.md).

---

## Phase 1: Setup

- [ ] T001 Commitear `specs/013-plugin-reutilizable-otros/tasks.md` en un commit `docs(tasks): …` antes de cualquier código (constitución IX).
- [ ] T002 En `pyproject.toml`:
  - añadir `plugins` a `testpaths`;
  - añadir `plugins/guardas-y-revision/hooks` y `plugins/guardas-y-revision/scripts` a `pythonpath`.

---

## Phase 2: Foundational: la guarda pasa al plugin como única fuente (R2, R5, R10)

**⚠️ Bloquea** US1 y US3: el plugin y este repositorio usan este mismo archivo.

- [ ] T003 Mover con `git mv` a `plugins/guardas-y-revision/hooks/`:
  - `.claude/hooks/guarda_datos.py`;
  - `.claude/hooks/detector_datos.py`;
  - `.claude/hooks/test_guarda_datos.py`;
  - `.claude/hooks/test_detector_datos.py`.

  Sin cambios de contenido en este paso.
- [ ] T004 Crear `plugins/guardas-y-revision/hooks/base_guarda.py`.
  - Contiene `leer_entrada`, `raiz`, `cwd`, `normalizar_ruta`, `bloquear`, `flujos_utf8` y `ejecutar`, copiadas de `.claude/hooks/comun.py` sin cambiar su comportamiento.
  - Solo usa la biblioteca estándar.
  - Sus docstrings no remiten a specs ni a tickets (FR-004).
- [ ] T005 Generalizar `plugins/guardas-y-revision/hooks/guarda_datos.py` (R10 y R5; FR-002, FR-003 y FR-005):
  - importa `base_guarda` en vez de `comun`;
  - el mensaje pasa a ser «Dato con forma real bloqueado: {hallazgos}. Usa valores claramente ficticios o genera el valor en la prueba.»;
  - `textos()` revisa todos los valores de texto de cualquier herramienta que empiece por `mcp__`;
  - docstrings sin rutas de specs.
- [ ] T006 Generalizar `plugins/guardas-y-revision/hooks/detector_datos.py`: docstrings sin rutas de specs. Ningún cambio de lógica.
- [ ] T007 Repartir los tests movidos (FR-007 y SC-004; R2). **Ningún test se borra ni se debilita.**
  - **Se quedan en `plugins/…/hooks/test_guarda_datos.py` y `test_detector_datos.py`**: los casos genéricos. No usan la raíz del repositorio ni términos del proyecto, y el texto del mensaje pasa al nuevo (R10).
  - **Pasan a `.claude/hooks/test_guarda_datos_repositorio.py`**: los casos propios del proyecto, contra la misma guarda:
    - el ejemplo del enunciado no se bloquea;
    - `CO-TV-0001` no es hallazgo;
    - los mensajes que lo citaban.
  - **Se añade un test** que comprueba que la guarda revisa una herramienta `mcp__otro_servidor__add_issue_comment`, por el cambio de R5.
  - La tabla de adaptación va al final de este archivo.
- [ ] T008 En `.claude/settings.json` (R3 y R5; FR-009):
  - la entrada de la guarda de datos pasa a `${CLAUDE_PROJECT_DIR}/plugins/guardas-y-revision/hooks/guarda_datos.py`, con el matcher anclado de R5;
  - se añade `"enabledPlugins": {"guardas-y-revision@piezas-reutilizables": false}`.

  En `.claude/hooks/test_configuracion.py`, adaptar las expectativas de la ruta y admitir el matcher de R5 **solo para la guarda de datos**; las demás guardas siguen con listas de nombres exactos (cambio declarado en R5).
- [ ] T009 Ejecutar `uv run ruff format . && uv run ruff check .` y `uv run pytest .claude/hooks plugins`, y dejarlo en verde.

**Checkpoint**: este repositorio ya usa la guarda del plugin, con el mismo comportamiento.

---

## Phase 3: User Story 1, otro equipo instala el plugin (Priority: P1) 🎯 MVP

**Goal**: el plugin se instala desde el marketplace y sus tres piezas funcionan en un repositorio de prueba.

**Independent Test**: Q2, Q3 y Q4 del quickstart.

- [ ] T010 [P] [US1] Crear `plugins/guardas-y-revision/.claude-plugin/plugin.json` con `name` `guardas-y-revision`, `version` `1.0.0` y `description` en español, sin `author` (FR-001). Crear `.claude-plugin/marketplace.json` con:
  - `name`: `piezas-reutilizables`;
  - `owner.name`: un nombre de equipo genérico;
  - `plugins`: `[{name, source: "./plugins/guardas-y-revision", description}]`.

  Sin `homepage` (R1 y R11).
- [ ] T011 [P] [US1] Crear `plugins/guardas-y-revision/hooks/hooks.json` con `PreToolUse`, el matcher de R5, `"type": "command"`, `"command": "uv"`, `args` `["run","--no-project","--python","3.12","--quiet","${CLAUDE_PLUGIN_ROOT}/hooks/guarda_datos.py"]`, `"timeout": 10` y `"onFailure": "block"` (R9).
- [ ] T012 [P] [US1] Crear `plugins/guardas-y-revision/scripts/test_contexto_revision.py`, que debe fallar primero, con repositorios git temporales:
  - el repositorio no es git;
  - sin base de fusión;
  - base `main` sin remoto;
  - `origin/HEAD`;
  - sin `specs/` (`Ticket: no aplica`, sin `CONTEXTO INCOMPLETO`);
  - con `specs/` y rama `NNN-nombre`;
  - con `specs/` y la rama sin el patrón (incompleto);
  - con y sin constitución;
  - lista agrupada y diff omitido por el umbral;
  - error inesperado: código 0 con `CONTEXTO INCOMPLETO`;
  - no importa `veredicto` ni `comun` (FR-002 y FR-006).
- [ ] T013 [US1] Crear `plugins/guardas-y-revision/scripts/contexto_revision.py` según R6 y el data-model, y dejar T012 en verde.
- [ ] T014 [P] [US1] Crear `plugins/guardas-y-revision/agents/revisor-codigo.md`, la versión genérica del agente del #4 (R7, contrato §4). Herramientas `Read`, `Grep` y `Glob`, y la misma línea `RESUMEN`.
- [ ] T015 [P] [US1] Crear `plugins/guardas-y-revision/skills/revisar-codigo/SKILL.md` (R4 y R7, contrato §3):
  - `context: fork`;
  - `agent: guardas-y-revision:revisor-codigo`;
  - `allowed-tools` con la regla exacta de la línea `!`;
  - la línea `!` con `"${CLAUDE_PLUGIN_ROOT}/scripts/contexto_revision.py"`;
  - los pasos genéricos, incluido «sin ticket no reduce la cobertura».
- [ ] T016 [P] [US1] Crear `plugins/guardas-y-revision/README.md`: qué trae, los requisitos (R9) y que los cambios llegan al subir la `version`. Genérico, sin términos del proyecto.
- [ ] T017 [US1] Crear `plugins/guardas-y-revision/test_plugin.py`:
  - el manifiesto y el marketplace válidos y coherentes (mismo nombre y descripción);
  - `hooks.json` usa solo `${CLAUDE_PLUGIN_ROOT}`, con `onFailure` `block` y el matcher que acepta las 13 herramientas;
  - el agente tiene exactamente `Read, Grep, Glob`;
  - la skill tiene `fork`, el agente con prefijo, y la regla de `allowed-tools` es igual al comando de la línea `!`.
- [ ] T018 [US1] Ejecutar `claude plugin validate --strict .` y `claude plugin validate --strict plugins/guardas-y-revision`, y corregir hasta cero avisos. Ruff y `uv run pytest plugins` en verde. Commit.
- [ ] T019 [US1] **Q2**: instalación sin interfaz en una carpeta temporal fuera del repositorio, desde un clon limpio de la rama. Anotar aquí los comandos usados, el número de comandos de instalación y lo que dicen `list` y `details` (SC-001).
- [ ] T020 [US1] **Q3**: la guarda en el repositorio de prueba, con `contar_bloqueos.py` en el scratchpad. Anotar solo conteos, con dos intentos como máximo si no es concluyente. Si el plugin no carga por la confianza, usar `--plugin-dir` y anotar Q6 para la analista.
- [ ] T021 [US1] **Q4**: la skill y el subagente. Anotar la línea `RESUMEN`, si apareció la marca del contexto y `Ticket: no aplica`, y qué agente corrió.
  - **Si falla R4 o R7**: aplicar la alternativa, declararla y actualizar spec, plan, research, contrato, quickstart y este archivo en el mismo commit.

**Checkpoint**: las tres piezas funcionan fuera del repositorio, o lo que falte queda en Q6 con sus comandos.

---

## Phase 4: User Story 2, ninguna pieza arrastra el proyecto (Priority: P1)

**Goal**: cero términos del proyecto en el plugin (FR-004 y SC-002).

**Independent Test**: `uv run pytest .claude/hooks/test_plugin_repositorio.py -k terminos`.

- [ ] T022 [US2] Crear `.claude/hooks/test_plugin_repositorio.py` con:
  - la lista de patrones de R11, que recorre `git ls-files plugins/` y `.claude-plugin/marketplace.json` e informa `archivo:línea:término`;
  - `CLAUDE_PROJECT_DIR` prohibido solo en `hooks.json` y en `SKILL.md`;
  - un segundo test que comprueba que cada patrón detecta su muestra;
  - un tercero que comprueba que `hooks.json` y el `SKILL.md` solo construyen rutas con `${CLAUDE_PLUGIN_ROOT}` (US2-2).

  Corregir lo que aparezca.

---

## Phase 5: User Story 3, una sola ejecución en este repositorio (Priority: P1)

**Goal**: FR-007, FR-009 y SC-003 demostrados con tests y con Q5.

**Independent Test**: `uv run pytest .claude/hooks/test_plugin_repositorio.py` y Q5.

- [ ] T023 [US3] En `.claude/hooks/test_plugin_repositorio.py`:
  - **Una ejecución por herramienta**: para cada una de las 13 herramientas (las 5 del sistema y las 8 de publicación con el servidor `github` y con otro nombre), exactamente una entrada de `PreToolUse` de `.claude/settings.json` cuyo matcher la acepta ejecuta `guarda_datos.py` (SC-003).
  - **El plugin, deshabilitado**: `enabledPlugins` lo tiene a `false` y no hay `extraKnownMarketplaces` que lo traiga.
  - **Los dos registros, equivalentes**: el de `settings.json` y el de `hooks.json` tienen el mismo matcher, `type`, `command`, `timeout` y `onFailure`, y los mismos `args` salvo la raíz.
  - **Una sola fuente**: no existe `.claude/hooks/guarda_datos.py` ni `.claude/hooks/detector_datos.py`.
  - **`base_guarda` equivale a `comun`**: `normalizar_ruta` (con los casos de `test_comun.py`), `raiz`, `cwd`, `bloquear` y `ejecutar` dan el mismo resultado en las dos implementaciones.
- [ ] T024 [US3] **Q5, obligatoria**:
  - en el clon limpio de la rama (sin `.env`, sin clave y sin `PYTHONUTF8`), `claude -p --model haiku --strict-mcp-config` con `Write` y el valor generado en disco;
  - anotar las llamadas a `Write`, los resultados bloqueados y los `[guarda_datos]` de cada uno: deben ser exactamente 1;
  - dos intentos como máximo si no es concluyente.

---

## Phase 6: User Story 4, instrucciones en el README (Priority: P2)

- [ ] T025 [US4] Añadir al `README.md` la sección corta «Plugin para otros equipos» (FR-011, contrato §1):
  - las tres piezas, en una línea cada una;
  - los requisitos;
  - la instalación desde GitHub (tras el merge; el repositorio es privado) y desde una copia local;
  - la desinstalación;
  - que en este repositorio el plugin está deshabilitado a propósito (R3).

  No tocar el resto del README (#14).

---

## Phase 7: Polish

- [ ] T026 Añadir a `DECISIONES.md` una entrada corta del #13:
  - la guarda como única fuente en el plugin;
  - la convivencia (opción B) y el riesgo de `settings.local.json`;
  - los cambios declarados en la guarda (R10 y R5);
  - lo que haya quedado pendiente de Q6.
- [ ] T027 Barrido:
  - ruff;
  - Q1 completa: `uv run pytest src` y `uv run pytest .claude/hooks plugins`, en el repositorio y en una copia limpia sin `.env`, sin clave y sin `PYTHONUTF8`;
  - `claude plugin validate --strict`;
  - cada documento coherente con lo construido;
  - las tareas marcadas;
  - el coste de las ejecuciones de `claude -p` anotado;
  - la limpieza de las carpetas temporales y de las trazas, y `marketplace remove` hecho.

  Commit. **Parada antes de `/abrir-pr`.**

---

## Dependencies & Execution Order

- **Fases y tareas**:
  - Setup (T001–T002), luego Foundational (T003–T009): bloquean todo.
  - US1: T010–T018 antes de Q2–Q4 (T019–T021), que exigen los archivos commiteados porque se instala desde un clon.
  - US2 (T022) y US3 (T023) pueden ir en paralelo con T010–T017. T024 (Q5) necesita T008 commiteado.
  - US4 (T025) tras T019, para documentar los comandos que funcionaron.
  - Polish al final.
- **En paralelo**: T010, T011, T012, T014, T015 y T016 (archivos distintos).

## Implementation Strategy

Foundational, US1 hasta T018, US2 y US3 (tests), commit, Q2–Q5 con la CLI, US4, DECISIONES.md y barrido.

## Tabla de adaptación de los tests del #3 (T007)

La rellena T007: cada test de `test_guarda_datos.py` y `test_detector_datos.py`, adónde fue y si cambió su expectativa.
