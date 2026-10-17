---

description: "Lista de tareas del ticket #4, revisión independiente y auditoría de cumplimiento"
---

# Tasks: Revisión independiente y auditoría de cumplimiento

**Input**: documentos de diseño en `specs/004-revision-independiente-auditoria/`: [plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/) y [quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/
y quickstart.md.

**Tests**: obligatorios (FR-015 y constitución X). Van junto a cada script, en
`.claude/hooks/test_*.py`, y se escriben antes que el script (deben fallar primero).

**Organization**: una fase por historia de la spec, con una fase previa para los dos
scripts que comparten varias historias:

1. Setup: fase 1.
2. Fundamentos (`veredicto.py` y `preparar_revision.py`): fase 2.
3. US1 revisor de código: fase 3. US2 auditor de cumplimiento: fase 4.
4. US3 consolidación en `/abrir-pr`: fase 5. US4 puerta y protección de veredictos: fase 6.
5. Documentación: fase 7. Commit, sesión nueva y quickstart: fase 8.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La
verificación del cierre de #4 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US4).
- **[MANUAL]**: la hace la analista, fuera de Claude Code o en la interfaz de Claude Code.
  Claude se detiene y espera su confirmación.
- **PARADA A a F**: puntos de revisión de la analista. Claude se detiene, entrega lo que
  se pide en la parada (diff, salida de los tests, decisiones) y no sigue hasta que la
  analista lo indique. Están tras T007 (A), T015 (B), T018 (C), T025 (D), en T029 (E) y tras
  T035 (F).
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md) o
  Q# del [quickstart](quickstart.md).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Ningún valor con forma real** (tarjeta, NIT, cédula o credencial) se escribe en
  tareas, tests, código ni documentación. Los tests construyen sus repositorios git
  temporales y sus valores en tiempo de ejecución (`tmp_path`).
- **Datos ficticios** de apoyo, cuando hagan falta: `CO-TV-0001`, `$80.000.000`.
- **Commits** por partes lógicas en la rama `004-revision-independiente-auditoria`, nunca
  en `main`, y sin `git commit --amend`: cada corrección va en un commit nuevo. Un commit
  nuevo invalida el veredicto del anterior, así que el veredicto se registra en
  `/abrir-pr`, después del último commit. **Ningún commit va después de la revisión**: si
  `/abrir-pr` falla o reporta bloqueantes, se corrige con un commit nuevo y se revisa otra
  vez.
- **Formato**: el hook de #3 formatea cada `.py` escrito o editado. Aun así, cada fase de
  código termina con `uv run ruff format .claude/hooks` y `uv run ruff check .claude/hooks`.
- **Tests**: `uv run pytest .claude/hooks` (`pyproject.toml` ya incluye la ruta en
  `testpaths` y `pythonpath`).
- **Antes de T024 la guarda de PR no actúa**: hasta que se registra en `settings.json`, el
  PR de este ticket se abriría por el flujo antiguo. T024 va después de T017, así que el
  flujo que genera el veredicto ya existe cuando la guarda empieza a bloquear. `/abrir-pr`
  del ticket se ejecuta en una sesión nueva, con el flujo nuevo (T029).
- `.claude/veredictos/` lo escribe solo `veredicto.py registrar` (FR-020): ninguna tarea lo
  crea ni lo modifica a mano, ni siquiera en las pruebas del quickstart.
- **Validación solo en Windows** (FR-016): macOS y Linux los respalda el diseño (forma exec
  sin shell, `uv`, `pathlib` y solo la biblioteca estándar). Ninguna tarea valida otro
  sistema.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: confirmar el punto de partida y excluir de git el directorio de veredictos.

- [X] T001 Confirmar el punto de partida:
  - la rama activa es `004-revision-independiente-auditoria`;
  - `git log --oneline main..HEAD` contiene los commits de spec (`4a095f4`, `7d7bba7`,
    `471f879`), de plan (`880aa89`, `f536e63`) y de tareas (`docs(specs): tareas del
    ticket #4`);
  - `git status --porcelain` está vacío;
  - el issue #4 está en "In Progress" (`mcp__github__projects_list`,
    `list_project_items`);
  - `uv sync` y `uv run pytest` pasan antes de tocar nada.
- [X] T002 Añadir `.claude/veredictos/` a `.gitignore` (R8, FR-010) y comprobar con
  `git check-ignore -v .claude/veredictos/prueba.json` que queda ignorado. Es el único
  cambio de esta tarea; no se crea el directorio.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: los dos scripts que usan varias historias. `veredicto.py` lo usan US3 y US4;
`preparar_revision.py`, US1 y US2.

**⚠️ CRITICAL**: ninguna historia empieza hasta terminar esta fase.

- [X] T003 [P] Escribir `.claude/hooks/test_veredicto.py` (R7, R8, FR-008, FR-010, FR-011;
  debe fallar primero). Repositorios git temporales con `tmp_path`; sin valores reales.
  Casos:
  - **Consolidación**: `aprobado` solo si las dos líneas `RESUMEN` son válidas, con
    `bloqueantes=0` y `cobertura=completa`; con bloqueantes, con `cobertura=incompleta`,
    con una línea ausente, repetida o con formato inesperado → `con bloqueantes`.
  - **Rama sin cambios** (C1, FR-008): `registrar` comprueba con git si hay cambios frente
    a la base (`git diff --quiet <base>..HEAD`, con `<base>` = `git merge-base HEAD
    origin/main`). Sin cambios, el veredicto es `con bloqueantes (sin cambios)` **aunque
    los dos resúmenes sean limpios**; sin base calculable, `con bloqueantes (sin base de
    comparación)`. El reporte no puede revertirlo.
  - **Formato** de la línea, estricto: `RESUMEN: bloqueantes=<entero> sugerencias=<entero>
    cobertura=<completa|incompleta>`; con espacios o campos de más o de menos, no vale.
  - **Registro**: un archivo por commit en `.claude/veredictos/<sha>.json`, con
    `commit`, `rama`, `veredicto`, `fecha` (UTC, ISO 8601), `codigo` y `auditoria`
    (`{bloqueantes, sugerencias, cobertura}`); se sobrescribe si ya existe para el mismo
    commit; un commit nuevo no tiene archivo.
  - **Lectura**: archivo ilegible, con otro formato o con `commit` distinto del nombre →
    "sin veredicto".
  - **CLI**: `registrar --codigo "<RESUMEN>" --auditoria "<RESUMEN>"` escribe una línea
    (`veredicto: aprobado` o `veredicto: con bloqueantes (<motivo>)`) y sale con 0 si
    `aprobado`, 1 si `con bloqueantes` y 2 si no pudo registrar.
- [X] T004 [P] Escribir `.claude/hooks/test_preparar_revision.py` (R4, R6, FR-005; debe
  fallar primero). Repositorios git temporales con un `origin` local. Casos:
  - la primera línea de la salida es exactamente `CONTEXTO DE REVISIÓN`;
  - la base es la de `veredicto.base_de_fusion` (`git merge-base HEAD origin/main`), no el
    `main` local (con un `main` local desactualizado);
  - la lista de archivos trae estado y estadísticas, y marca los eliminados;
  - los archivos de `specs/NNN-*/` van marcados como referencia;
  - el diff completo aparece solo si **toda la salida** queda por debajo de
    `UMBRAL_SALIDA`; por encima, una línea dice que se omitió y la marca, la lista y las
    rutas siguen;
  - si la lista y las rutas por sí solas superan el umbral, la lista se agrupa por
    directorio con sus totales y se dice así;
  - sin `origin/main`, sin merge-base o sin carpeta de specs: `CONTEXTO INCOMPLETO:
    <motivo>` y **salida 0**;
  - la salida siempre termina con código 0 y no usa la red.
- [X] T005 Implementar `.claude/hooks/veredicto.py` (solo biblioteca estándar; R7, R8,
  FR-008, FR-010, FR-011; hace pasar T003). Funciones `ruta_veredicto(raiz, sha)`,
  `consolidar(...)`, `registrar(...)`, `leer(raiz, sha)`, `base_de_fusion(raiz)` y
  `hay_cambios(raiz)`, y la CLI de `registrar`. La ruta la calcula el script; el comando de
  `/abrir-pr` no nombra el directorio.
- [X] T006 Implementar `.claude/hooks/preparar_revision.py` (solo biblioteca estándar; R4,
  R6, FR-005; hace pasar T004). Importa `base_de_fusion` de `veredicto.py` para usar la
  misma base. Constante `UMBRAL_SALIDA`, provisional en 30 000 bytes; T031 la fija en la
  mitad del techo medido en Q4. Sin argumentos ni stdin; siempre sale con 0.
- [X] T007 Ejecutar `uv run ruff format .claude/hooks`, `uv run ruff check .claude/hooks` y
  `uv run pytest .claude/hooks`, y commitear los archivos de T002 a T006: `feat(hooks):
  registro del veredicto y preparación del contexto de revisión`.

**PARADA A — revisión de la analista** (tras T007): Claude se detiene y entrega el diff de
`veredicto.py` y `preparar_revision.py`, la salida de `uv run pytest .claude/hooks` y cómo
quedó el caso de rama sin cambios y el de `UMBRAL_SALIDA`. No empieza la fase 3 hasta que la
analista lo indique.

**Checkpoint**: el veredicto y el contexto ya existen y están probados; las historias
pueden empezar.

---

## Phase 3: User Story 1 - Revisión independiente del código (Priority: P1) 🎯 MVP

**Goal**: un subagente de solo lectura, en contexto separado, revisa el cambio y reporta
hallazgos con `archivo:línea`, bloqueantes y sugerencias.

**Independent Test**: sobre una rama con un defecto evidente y una desviación de la spec,
`/revisar-codigo specs/NNN-nombre` los reporta con su ubicación, los clasifica y no modifica
ningún archivo (Q7, Q10).

- [ ] T008 [US1] Escribir `.claude/hooks/test_agentes_skills.py` con los casos generales,
  parametrizados por una lista `REVISIONES` de pares (subagente, skill) que de momento
  tiene `revisor-codigo` y `revisar-codigo` (R12, FR-003, FR-004; debe fallar primero):
  - en el subagente, `tools` es exactamente `Read, Grep, Glob`, ni una más (sin `Agent`,
    Bash, `Write`, `Edit`, `NotebookEdit` ni MCP);
  - la skill declara `context: fork`, `agent:` enlazado a un subagente que existe en
    `.claude/agents/`, `argument-hint` y `allowed-tools`;
  - `allowed-tools` de la skill contiene **solo** el comando del script de preparación;
  - el comando inyectado no interpola `$ARGUMENTS` (R2.2) y no usa rutas absolutas (R2.3);
  - el cuerpo de la skill menciona la marca `CONTEXTO DE REVISIÓN`, la línea `RESUMEN` y
    la instrucción de leer la constitución con `Read` (R3).
- [ ] T009 [P] [US1] Crear `.claude/agents/revisor-codigo.md` (FR-001, FR-003, FR-006,
  R5; [contracts/revisiones.md](contracts/revisiones.md)): `tools: Read, Grep, Glob`; rol de
  revisor de calidad, errores y cumplimiento de la spec del ticket; solo reporta, no
  corrige ni propone parches; cada hallazgo con `archivo:línea`, severidad (`BLOQUEANTE` o
  `SUGERENCIA`) y razón; no repite valores sensibles; termina con la línea `RESUMEN`.
- [ ] T010 [P] [US1] Crear `.claude/skills/revisar-codigo/SKILL.md` (FR-004, FR-005, R1, R2,
  R4, R6): `context: fork`, `agent: revisor-codigo`,
  `argument-hint: "[carpeta del ticket, p. ej. specs/NNN-nombre]"` y `allowed-tools` solo
  con el comando de `preparar_revision.py`, con la ruta resuelta por la variable de la
  skill que confirme Q1 (T030). Provisionalmente, `${CLAUDE_PROJECT_DIR}`. El cuerpo
  inyecta la salida del script, ordena leer `spec.md`, `plan.md`, `tasks.md` y la
  constitución, trata `specs/NNN-*/` como referencia que no cuenta para la cobertura, y
  pide `cobertura=incompleta` si falta la marca o no se puede leer un archivo de código o
  configuración. `$ARGUMENTS` solo en prosa.
- [ ] T011 [US1] Ejecutar `uv run ruff format .claude/hooks`, `uv run ruff check
  .claude/hooks` y `uv run pytest .claude/hooks -k agentes_skills`, y commitear: `feat(revision):
  subagente y skill de revisión de código`.

**Checkpoint**: US1 completa. Su validación en sesión (Q1 a Q4 y Q7) va en la fase 8.

---

## Phase 4: User Story 2 - Auditoría de las reglas de negocio (Priority: P1)

**Goal**: un segundo subagente de solo lectura verifica las cinco reglas del principio I con
evidencia, con estados `cumple`, `incumple`, `no aplica` o `no verificada`.

**Independent Test**: una rama con una regla deliberadamente incumplida sale con esa regla
bloqueante y las demás con su estado (Q8); este ticket, sin código de producción, sale con
las cinco `no aplica` (Q9).

- [ ] T012 [US2] Ampliar `REVISIONES` en `.claude/hooks/test_agentes_skills.py` con el par
  `auditor-cumplimiento` y `auditar-cumplimiento` (debe fallar primero). Añadir al
  auditor: el cuerpo menciona las cinco reglas del principio I, los cuatro estados, la razón
  obligatoria de cada `no aplica` y que una regla sin evidencia nunca es `cumple`.
- [ ] T013 [P] [US2] Crear `.claude/agents/auditor-cumplimiento.md` (FR-002, FR-003,
  FR-007, R5, R7): `tools: Read, Grep, Glob`; verifica las cinco reglas del principio I de
  `.specify/memory/constitution.md` contra la spec, el código y los tests, con evidencia de
  archivo y línea. Una regla **aplica** si la spec del ticket la cita o si el diff toca
  código que la implementa; si no aplica, estado `no aplica` con esa razón; si aplica y no
  hay evidencia, `no verificada` y bloqueante. Sin código de producción, las cinco `no
  aplica`. Tabla de las cinco reglas y línea `RESUMEN` al final.
- [ ] T014 [P] [US2] Crear `.claude/skills/auditar-cumplimiento/SKILL.md` (FR-004, FR-005,
  R1, R2): mismas reglas que T010, con `agent: auditor-cumplimiento` y la constitución como
  documento principal.
- [ ] T015 [US2] Ejecutar `uv run ruff format .claude/hooks`, `uv run ruff check
  .claude/hooks` y `uv run pytest .claude/hooks -k agentes_skills`, y commitear: `feat(revision):
  subagente y skill de auditoría de cumplimiento`.

**PARADA B — revisión de la analista** (tras T015): Claude se detiene y entrega los dos
subagentes y las dos skills (frontmatter y cuerpo completos), y la salida de los tests de
`test_agentes_skills.py`. La analista revisa las instrucciones de los revisores antes de que
se usen.

**Checkpoint**: US1 y US2 funcionan por separado, cada una con su skill.

---

## Phase 5: User Story 3 - Veredicto consolidado al abrir el PR (Priority: P1)

**Goal**: `/abrir-pr` ejecuta las dos revisiones, consolida el veredicto, lo registra para
el commit actual y no abre el PR si hay bloqueantes.

**Independent Test**: con una rama aprobada, el cierre registra el veredicto del commit; con
un bloqueante, no hay push, ni PR ni cambio de estado. Q12 y Q13 se prueban sin
`/abrir-pr` (skills y `veredicto.py registrar` a mano); `/abrir-pr` completo se valida una
vez, en T036 (Q12, Q13).

- [ ] T016 [US3] Añadir a `.claude/hooks/test_agentes_skills.py` la comprobación de
  `/abrir-pr` (R12; debe fallar primero): ya no usa `Agent` ni `git diff`, declara las dos
  `Skill(...)` y el comando de `veredicto.py registrar`, y menciona `git fetch origin main`.
- [ ] T017 [US3] Reescribir la sección 2 de `.claude/commands/abrir-pr.md` y ajustar sus
  acciones según [contracts/abrir-pr.md](contracts/abrir-pr.md) (FR-008, FR-009, FR-010,
  FR-019, R11; hace pasar T016). Orden: comprobaciones sin cambios → `git fetch origin main`
  (falla → se detiene) y `git fetch origin <rama>` (**no es fatal si la rama aún no existe
  en el remoto**) → skills `revisar-codigo` y `auditar-cumplimiento` con la carpeta del
  ticket → `veredicto.py registrar` con las dos líneas `RESUMEN` → con bloqueantes, se
  detiene sin push ni PR ni cambio de estado y muestra los hallazgos → `git push -u origin
  <rama>` → PR, estado y comentario. `allowed-tools`: salen `Agent` y `Bash(git diff:*)`;
  entran `Skill(revisar-codigo)`, `Skill(auditar-cumplimiento)`, el comando de
  `veredicto.py registrar` y `Bash(git rev-parse:*)`. La descripción del PR cita el
  veredicto, el commit, los dos `RESUMEN` y los hallazgos no bloqueantes. No quedan dos
  revisiones: se elimina el subagente `Plan`.
- [ ] T018 [US3] Ejecutar `uv run ruff format .claude/hooks`, `uv run ruff check
  .claude/hooks` y `uv run pytest .claude/hooks -k agentes_skills`, y commitear: `feat(abrir-pr):
  revisión independiente y veredicto en /abrir-pr`.

**PARADA C — revisión de la analista** (tras T018): Claude se detiene y entrega el diff de
`.claude/commands/abrir-pr.md` frente a su versión de #2, para revisar el orden de los pasos
y los permisos.

**Checkpoint**: US3 completa; el flujo nuevo reemplaza la revisión de transición de #2.

---

## Phase 6: User Story 4 - Puerta mecánica contra PR sin revisión (Priority: P1)

**Goal**: un hook bloquea crear el PR sin un veredicto aprobado del commit actual, por el
MCP de GitHub y por la terminal, y nadie puede escribir el directorio de veredictos.

**Independent Test**: sin veredicto, `create_pull_request`, `gh pr create` y `gh api` con
POST se bloquean; con veredicto aprobado del commit publicado, se permiten (por stdin;
Q11, Q14, Q16).

- [ ] T019 [P] [US4] Escribir `.claude/hooks/test_guarda_pr.py` (R10, FR-012 a FR-014,
  FR-016; debe fallar primero). Repositorios git temporales con un `origin` local y
  veredictos escritos con `veredicto.py`. Casos:
  - **MCP**: `mcp__github__create_pull_request` sin veredicto, con bloqueantes, aprobado
    de otro commit, ilegible, y aprobado con commit publicado (se permite);
  - **`head` normalizado**: sin prefijo, `propietario:rama` con el mismo `owner` (sin
    distinguir mayúsculas), con otro prefijo (PR desde un fork → bloquea) y distinta de la
    rama actual (bloquea);
  - **`gh pr create`**: directo, con `--head`/`-H`, tras `bash -c`, `eval`, heredoc,
    `xargs`, `sudo` y `env -S`;
  - **`gh api`**: `repos/<o>/<r>/pulls` con `-X POST`, con `--method POST`, con `-f`/`-F`/
    `--field`/`--raw-field`/`--input` (POST implícito) y `graphql` con `createPullRequest`
    → se bloquean sin veredicto; el mismo endpoint con GET, y `repos/<o>/<r>/pulls/1`, se
    permiten;
  - **Permitidos sin comprobar**: `gh pr view`, `gh pr list`, `gh pr status`, `git status`;
  - **Publicación** (R9): sin `origin/<rama>`, con `origin/<rama>` distinta de HEAD
    (bloquea), y con la rama actual distinta de la del PR;
  - **Fallo cerrado**: una excepción propia sale con 2; un script que sale con 1 queda
    cubierto por `onFailure`;
  - **Extremo a extremo** por stdin: salida 2 con una sola línea `[guarda_pr] <motivo>. <qué
    hacer>.` en stderr, y nada en stdout al permitir;
  - **Tiempo** (SC-004, A1): una llamada en caliente, desde la segunda, tarda menos de 1 s.
- [ ] T020 [US4] Implementar `.claude/hooks/guarda_pr.py` (solo biblioteca estándar;
  [contracts/veredicto-y-guarda.md](contracts/veredicto-y-guarda.md); R9, R10; hace pasar
  T019). Interfaz común de #3 con `comun.ejecutar` y `comun.bloquear`, y el extractor de
  texto ejecutable de `comun.py` para `gh` envuelto. Comprobación en el orden del
  contrato: rama del PR = rama actual → `origin/<rama>` existe → es igual a HEAD → existe
  el veredicto → es `aprobado`. Compara con la referencia local, nunca con `git ls-remote`.
- [ ] T021 [P] [US4] Ampliar `.claude/hooks/test_configuracion.py` **solo con tests**, que
  deben fallar primero (FR-016, R10, R12, R8): la guarda está registrada con `onFailure:
  "block"`, `timeout: 10` y el matcher es la lista exacta
  `Bash|PowerShell|mcp__github__create_pull_request`; `permissions.deny` incluye
  `Edit(/.claude/veredictos/**)` junto a la de `settings.local.json`; y el resto de las
  entradas de #3 no cambia. No toca `settings.json`.
- [ ] T022 [P] [US4] Ampliar `.claude/hooks/test_guarda_spec_previa.py` con la protección del
  directorio de veredictos (FR-020, R8; debe fallar primero): se bloquea en cualquier rama
  (también en una rama de ticket con sus documentos) escribir, editar, notebook, `>` y
  `>>`, `tee`, `cp`, `mv`, `sed -i`, `touch` y código en línea (`python -c`, `node -e`,
  `bash -c`, `eval`, heredoc a un intérprete) que lo nombre; se permite leerlo (`Read`,
  `cat`); el comando `uv run … veredicto.py registrar …` no se bloquea. Mensaje: `El
  directorio de veredictos solo lo escribe el registro de la revisión. Ejecuta /abrir-pr.`
- [ ] T023 [US4] Ampliar `.claude/hooks/guarda_spec_previa.py` (FR-020, R8; hace pasar T022):
  añadir `.claude/veredictos/**` al mismo tratamiento que `.claude/settings.local.json`
  (FR-025 de #3), con las mismas vías y sin distinguir rama, pero permitiendo la lectura.
  Leer antes el código de FR-025 y reutilizarlo; no duplicar el recorrido de comandos.
- [ ] T024 [US4] Registrar la guarda y la denegación en `.claude/settings.json` (FR-016,
  R8, R10; hace pasar T021): la entrada `PreToolUse` de
  [contracts/veredicto-y-guarda.md](contracts/veredicto-y-guarda.md), con el matcher
  `Bash|PowerShell|mcp__github__create_pull_request`, `timeout: 10` y `onFailure: "block"`;
  y `Edit(/.claude/veredictos/**)` en `permissions.deny`, junto a la de
  `settings.local.json`, sin reordenar la lista. **Esta es la tarea en que la guarda
  empieza a actuar** (ver "Reglas para todas las tareas"); va después de T017.
- [ ] T025 [US4] Ejecutar `uv run ruff format .claude/hooks`, `uv run ruff check
  .claude/hooks` y `uv run pytest .claude/hooks` (la suite completa), con y sin
  `PYTHONUTF8` y `PYTHONIOENCODING`, y commitear por partes: `feat(hooks): guarda de
  creación de PR` (T019, T020, T021 y T024) y `feat(hooks): protección del directorio de
  veredictos` (T022 y T023).

**PARADA D — revisión de la analista** (tras T025): Claude se detiene y entrega el diff de
`guarda_pr.py`, `guarda_spec_previa.py` y `settings.json`, la salida de la suite completa y
el tiempo medido de la guarda. La analista decide si sigue con la documentación.

**Checkpoint**: la puerta y la protección están registradas y probadas por stdin. Falta la
validación en sesión (fase 8).

---

## Phase 7: Documentación

**Purpose**: dejar declaradas las decisiones y el límite del mecanismo.

- [ ] T026 [P] Escribir la entrada 5 de `DECISIONES.md` (FR-018, SC-006), con unas 15
  líneas y una por decisión, y el detalle remitido a `research.md`: dos subagentes de solo
  lectura y una skill con `context: fork` por revisión (R1, R5); inyección con script que
  sale siempre con 0, marca `CONTEXTO DE REVISIÓN` y umbral sobre toda la salida (R2, R4);
  la constitución se lee con `Read` (R3); veredicto por commit, protegido, y rama sin
  cambios rechazada por el registro (R8); puerta con `origin/<rama>` local, no `ls-remote`
  (R9); la guarda de PR (R10). Los **riesgos residuales**: (1) invocar `veredicto.py
  registrar` con `RESUMEN` inventados; (2) crear el PR fuera de Claude Code, alias de `gh`
  y construcciones que el extractor no reconoce; (3) commits empujados por otra persona
  tras el último `fetch`; (4) `Read` del subagente y `guarda_secretos`; (5) la calidad de
  la revisión depende del modelo. Añadir una nota en la entrada 3 ("la revisión de
  transición de `/abrir-pr` queda reemplazada por #4"). Los resultados de Q1 a Q6 se añaden
  en T033.
- [ ] T027 [P] Añadir una frase en la sección "Ciclo de un ticket" de `README.md`:
  `/abrir-pr` ejecuta la revisión independiente y la auditoría, y el hook bloquea el PR sin
  veredicto aprobado del commit actual. `CLAUDE.md` no cambia.
- [ ] T028 Ejecutar la suite completa y `uv run ruff format --check .`, `uv run ruff check
  .`, y commitear: `docs: decisiones y ciclo de ticket de la revisión independiente`.

---

## Phase 8: Sesión nueva y quickstart (Polish & Cross-Cutting)

**Purpose**: validar de extremo a extremo con una sesión nueva. Se hace con la implementación
**commiteada**. Los escenarios están en el [quickstart](quickstart.md).

- [ ] T029 [MANUAL] La analista abre una **sesión nueva** de Claude Code en la raíz, tras
  `uv sync`, y comprueba con `/hooks` las entradas (cinco `PreToolUse` y una `PostToolUse`) y
  con `/agents` los dos subagentes. Crea desde fuera de Claude Code el `.env.local` que
  pide Q5, la rama temporal `prueba-revision` desde la del ticket y el **clon desechable**
  de Q4(b), fuera del repositorio. Primera instrucción de esa sesión: "continúa tasks.md del
  ticket #4 desde T030".

**PARADA E — pausa manual** (en T029): Claude no sigue hasta que la analista confirme la
sesión nueva, las entradas de `/hooks` y `/agents`, y que los archivos y el clon de prueba
existen.

- [ ] T030 Ejecutar Q1 a Q4 y anotar el resultado de cada una al pie de este archivo
  (R2, R4, R13): variable que resuelve la ruta del script, que el patrón de `allowed-tools`
  funciona desde cualquier carpeta y clon, que el subagente no puede ejecutar ni escribir,
  si la constitución llega por `@import`, el techo real de la salida inyectada. **Q4(b) es
  manual en parte**: la analista abre Claude Code **en el clon desechable**, con
  `git update-ref refs/remotes/origin/main b7d5f48^1` dentro del clon, y ejecuta
  `/revisar-codigo`; el diff es el del #3 más el del #4 (41 archivos, ≈ 475 KB, medido) y
  debe terminar con `cobertura=completa`. No sirve el rango `b7d5f48^1..5225965` (vacío)
  ni un worktree (movería el `origin/main` real).
- [ ] T031 Fijar `UMBRAL_SALIDA` en `.claude/hooks/preparar_revision.py` en **la mitad del
  techo medido en Q4** (A2) y el test de T004 que lo fija; y, si Q1 pide otra variable o
  patrón, corregir las dos skills y `/abrir-pr`. Si no hace falta ningún cambio, se anota.
  Commit nuevo: `fix(revision): ajuste con las comprobaciones de la sesión`.
- [ ] T032 Ejecutar Q5 y Q6 (R5, R13) y anotar: si `guarda_secretos` alcanza a las
  herramientas del subagente y si la inyección pasa por `PreToolUse`. Si `Read` del
  subagente queda sin protección, declararlo en la entrada 5 de `DECISIONES.md` (T033).
- [ ] T033 Ejecutar Q7 a Q10 (revisión, auditoría y que los revisores no modifican nada)
  y Q11 a Q15 (veredicto, puerta, commit nuevo y tiempo de la guarda en caliente, que
  **pasa o falla** con 1 s), con la rama temporal y **sin `/abrir-pr`**: las skills y
  `veredicto.py registrar` a mano, y la guarda por stdin y en la sesión (un `gh pr create`
  real sin veredicto). Nunca se abre un PR de prueba. **SC-005 lo valida la analista
  leyendo los reportes de Q7 y Q8 sin abrir el código** [MANUAL]. Anotar los resultados al
  pie y añadir los de Q1 a Q6 a `DECISIONES.md`.
- [ ] T034 Ejecutar Q16 y Q17 (FR-020 y la marca de contexto): el directorio de veredictos
  no se modifica por ninguna herramienta en ninguna rama y la revisión sin inyección
  declara `cobertura=incompleta`. `disableSkillShellExecution` se activa y se restaura
  desde fuera de Claude Code.
- [ ] T035 [MANUAL] Limpieza: borrar `.env.local`, el clon desechable y los archivos de
  `.claude/veredictos/` de las pruebas desde fuera de Claude Code, y las ramas temporales
  con `git branch -d`.

**PARADA F — revisión de la analista** (tras T035, antes de `/abrir-pr`): Claude se detiene
y entrega los resultados anotados de Q1 a Q17, lo que cambió en T031 y el estado del
repositorio (`git status --porcelain`, `git log --oneline main..HEAD`). La analista decide
si se lanza `/abrir-pr`.

- [ ] T036 Commitear los resultados anotados al pie de este archivo y en `DECISIONES.md`
  (`docs(specs): resultados de la validación del ticket #4`), **marcando T036 `[X]` en ese
  mismo commit** y comprobando `git status --porcelain` vacío. Ningún commit va después de
  la revisión. Después se lanza `/abrir-pr` en esta misma sesión nueva: genera el veredicto
  del último commit y pasa por la guarda; es la única vez que se valida el flujo completo
  (Q12 y Q13 con el PR real). Si falla o reporta bloqueantes, se corrige con un commit nuevo
  y se revisa otra vez.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Fase 1** (T001, T002): sin dependencias.
- **Fase 2** (T003 a T007): depende de la fase 1 y **bloquea** las historias. La parada A
  cierra la fase.
- **Fases 3 y 4** (US1, US2): dependen de la fase 2; son independientes entre sí, salvo que
  comparten `test_agentes_skills.py` (T012 sigue a T008).
- **Fase 5** (US3): depende de T005 (`veredicto.py`) y de las skills de las fases 3 y 4.
- **Fase 6** (US4): depende de T005 (`veredicto.py`) y de `comun.py` de #3; **T024 va
  después de T017**, porque la guarda no debe empezar a bloquear antes de que exista el
  flujo que genera el veredicto.
- **Fase 7** (documentación): después de las fases 3 a 6.
- **Fase 8** (sesión nueva): con todo commiteado.

### Within a phase

- Los tests van antes que su implementación y deben fallar primero (T016 antes de T017;
  T021 antes de T024).
- T023 después de T022; T024 después de T020, T021 y T023.
- Un commit por parte lógica; ninguno con `--amend`.

### Parallel Opportunities

- T003 ∥ T004 (tests en archivos distintos).
- T009 ∥ T010; T013 ∥ T014.
- T019 ∥ T021 ∥ T022 (tests en archivos distintos).
- T026 ∥ T027.
- Las fases 3, 4 y 5 pueden hacerse en paralelo con T019 a T023, que no comparten archivos;
  T024 espera a T017. Las paradas B, C y D no se saltan.

## Parallel Example: tras la fase 2

```text
T008 test_agentes_skills.py (revisor)
T019 test_guarda_pr.py
T022 test_guarda_spec_previa.py (veredictos)
```

## Implementation Strategy

### MVP First

1. Fases 1 y 2, hasta la parada A.
2. Fases 3, 4 y 5, que producen el veredicto.
3. Fase 6 (US4), la puerta y la protección: es lo que el principio II exige que sea
   garantizado, no sugerido. Con `veredicto.py`, las skills y la puerta, ningún PR se abre
   sin veredicto.
4. **Aviso**: la puerta sola, sin las skills, bloquearía todos los PR. Por eso su registro
   (T024) va al final de la fase 6 y después de T017.

### Incremental Delivery

Cada fase termina en un commit con sus tests en verde y, en las paradas, en una revisión de
la analista. La guarda de PR empieza a actuar en T024; la protección de veredictos, en T023
y T024. La validación en sesión (T029 a T034) es la única que prueba la inyección, los
subagentes y la puerta con el cliente real.

## Notes

- Tareas manuales: T029, T035 y, en T030 y T033, Q4(b) en el clon desechable y la lectura de
  SC-005. Paradas de revisión: A (tras T007), B (tras T015), C (tras T018), D (tras T025), E
  (en T029) y F (tras T035).
- T030 a T034 las ejecuta Claude en la sesión nueva, a petición de la analista.
- `CLAUDE.md` no cambia. No se editan las skills de Spec Kit.
- Los resultados de Q1 a Q17 se anotan al pie de este archivo, en una sección "Resultados de
  la validación", al ejecutarlos.
