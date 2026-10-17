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
  - **CLI**: `registrar --commit <sha> --codigo "<RESUMEN>" --auditoria "<RESUMEN>"`
    escribe una línea (`veredicto: aprobado` o `veredicto: con bloqueantes (<motivo>)`) y
    sale con 0 si `aprobado`, 1 si `con bloqueantes` y 2 si no pudo registrar.
  - **Ampliado tras la parada A (hallazgo 1: el veredicto queda atado al commit
    revisado)**: `--commit` distinto de `HEAD` → salida 2, ningún archivo creado y el
    mensaje `El commit cambió durante la revisión (revisado <7 caracteres>, actual <7
    caracteres>): ejecute /abrir-pr de nuevo.` en stderr; `--commit` ausente → salida 2;
    `--commit` no hexadecimal o abreviado → salida 2; `--commit` igual a `HEAD` → el
    comportamiento de siempre. El sha del archivo es el de `--commit`.
  - **Ampliado tras la parada A (hallazgo 2: formato estricto)**: `bloqueantes=٠` y
    `bloqueantes=０` (dígitos de otros alfabetos) → reporte no utilizable; el formato usa
    solo `[0-9]`.
  - **Ampliado tras la parada C (hallazgo 1: la raíz no es el directorio actual)**: sin
    `CLAUDE_PROJECT_DIR`, ejecutado desde una subcarpeta del repositorio, `registrar`
    escribe el veredicto en la raíz del repositorio (`git rev-parse --show-toplevel`) y no
    en la subcarpeta; con `CLAUDE_PROJECT_DIR` definida, manda esa; fuera de un repositorio y
    sin la variable, usa el directorio actual y el error se reporta como hasta ahora (salida
    2). La función `raiz()` lo resuelve en ese orden.
- [X] T004 [P] Escribir `.claude/hooks/test_preparar_revision.py` (R4, R6, FR-005; debe
  fallar primero). Repositorios git temporales con un `origin` local. Casos:
  - la primera línea de la salida es exactamente `CONTEXTO DE REVISIÓN`;
  - **ampliado tras la parada A**: la salida contiene `Commit: <sha completo de HEAD>`,
    justo después de `Rama:`;
  - **ampliado tras la parada C**: ejecutado desde una subcarpeta del repositorio y sin
    `CLAUDE_PROJECT_DIR`, encuentra `specs/NNN-*/` en la raíz (`Ticket: specs/…`, sin
    `CONTEXTO INCOMPLETO`), con la misma raíz que `veredicto.py`;
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
  misma base. Constante `UMBRAL_SALIDA`, provisional en 30 000 bytes; T031 la fijó en
  14 500, la mitad del techo medido en Q4(a). Sin argumentos ni stdin; siempre sale con 0.
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

- [X] T008 [US1] Escribir `.claude/hooks/test_agentes_skills.py` con los casos generales,
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
- [X] T009 [P] [US1] Crear `.claude/agents/revisor-codigo.md` (FR-001, FR-003, FR-006,
  R5; [contracts/revisiones.md](contracts/revisiones.md)): `tools: Read, Grep, Glob`; rol de
  revisor de calidad, errores y cumplimiento de la spec del ticket; solo reporta, no
  corrige ni propone parches; cada hallazgo con `archivo:línea`, severidad (`BLOQUEANTE` o
  `SUGERENCIA`) y razón; no repite valores sensibles; termina con la línea `RESUMEN`.
- [X] T010 [P] [US1] Crear `.claude/skills/revisar-codigo/SKILL.md` (FR-004, FR-005, R1, R2,
  R4, R6): `context: fork`, `agent: revisor-codigo`,
  `argument-hint: "[carpeta del ticket, p. ej. specs/NNN-nombre]"` y `allowed-tools` solo
  con el comando de `preparar_revision.py`, con la ruta resuelta por la variable de la
  skill que confirme Q1 (T030). Provisionalmente, `${CLAUDE_PROJECT_DIR}`. El cuerpo
  inyecta la salida del script, ordena leer `spec.md`, `plan.md`, `tasks.md` y la
  constitución, trata `specs/NNN-*/` como referencia que no cuenta para la cobertura, y
  pide `cobertura=incompleta` si falta la marca o no se puede leer un archivo de código o
  configuración. `$ARGUMENTS` solo en prosa, y solo como pista: la carpeta del ticket es la
  de la línea `Ticket:` del contexto, calculada con git (ajuste tras la parada B).
- [X] T011 [US1] Ejecutar `uv run ruff format .claude/hooks`, `uv run ruff check
  .claude/hooks` y `uv run pytest .claude/hooks -k agentes_skills`, y commitear: `feat(revision):
  subagente y skill de revisión de código`.

**Checkpoint**: US1 completa. Su validación en sesión (Q1 a Q4 y Q7) va en la fase 8.

---

## Phase 4: User Story 2 - Auditoría de las reglas de negocio (Priority: P1)

**Goal**: un segundo subagente de solo lectura verifica las cinco reglas del principio I con
evidencia, con estados `cumple`, `incumple`, `no aplica` o `no verificada`.

**Independent Test**: una rama con una regla deliberadamente incumplida sale con esa regla
bloqueante y las demás con su estado (Q8); este ticket, sin código de producción ni tests
de las reglas, sale con las cinco `no aplica` (Q9); y una rama que solo borra o debilita el
test de una regla no la deja en `no aplica` (Q9b).

- [X] T012 [US2] Ampliar `REVISIONES` en `.claude/hooks/test_agentes_skills.py` con el par
  `auditor-cumplimiento` y `auditar-cumplimiento` (debe fallar primero). Añadir al
  auditor: el cuerpo menciona las cinco reglas del principio I, los cuatro estados, la razón
  obligatoria de cada `no aplica` y que una regla sin evidencia nunca es `cumple`.
  - **Ampliado tras la parada B** (hallazgos 1, 2 y 3; deben fallar primero):
    `test_el_auditor_define_cuando_aplica_una_regla` exige "código o tests" y "ni tests de
    las reglas"; un test del revisor comprueba que no contiene "ponlo como sugerencia" y sí
    la regla de ubicar lo que falta en el requisito (`spec.md:línea` o `tasks.md:línea`), con
    severidad bloqueante si es obligatorio; y un test de las dos skills comprueba que
    nombran la línea `Ticket:` del contexto como la carpeta que manda y que `$ARGUMENTS`
    solo es una pista (si indica otra carpeta, se dice y `cobertura=incompleta`).
- [X] T013 [P] [US2] Crear `.claude/agents/auditor-cumplimiento.md` (FR-002, FR-003,
  FR-007, R5, R7): `tools: Read, Grep, Glob`; verifica las cinco reglas del principio I de
  `.specify/memory/constitution.md` contra la spec, el código y los tests, con evidencia de
  archivo y línea. Una regla **aplica** si la spec del ticket la cita o si el diff toca
  código **o tests** que la implementan o la prueban; si no aplica, estado `no aplica` con
  esa razón; si aplica y no hay evidencia, `no verificada` y bloqueante. Sin código de
  producción **ni tests de las reglas**, las cinco `no aplica`. Un cambio que solo borra o
  debilita el test de una regla sí la toca. Tabla de las cinco reglas y línea `RESUMEN` al
  final.
- [X] T014 [P] [US2] Crear `.claude/skills/auditar-cumplimiento/SKILL.md` (FR-004, FR-005,
  R1, R2): mismas reglas que T010, con `agent: auditor-cumplimiento` y la constitución como
  documento principal.
- [X] T015 [US2] Ejecutar `uv run ruff format .claude/hooks`, `uv run ruff check
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

- [X] T016 [US3] Añadir a `.claude/hooks/test_agentes_skills.py` la comprobación de
  `/abrir-pr` (R12; debe fallar primero): ya no usa `Agent` ni `git diff`, declara las dos
  `Skill(...)` y el comando de `veredicto.py registrar`, y menciona `git fetch origin main`.
  - **Ampliado tras la parada C** (hallazgos 1 y 2): `/abrir-pr` no usa
    `${CLAUDE_PROJECT_DIR}` en ningún sitio (la variable no existe en la herramienta Bash);
    el comando de registro y su regla de `allowed-tools` llevan la ruta relativa
    `.claude/hooks/veredicto.py`; antes de registrar, cada línea `RESUMEN` se pasa solo si
    coincide exactamente con `RESUMEN: bloqueantes=<dígitos> sugerencias=<dígitos>
    cobertura=<completa|incompleta>` y, si no, se pasa `sin resumen`; y las skills sí
    conservan la variable.
- [X] T017 [US3] Reescribir la sección 2 de `.claude/commands/abrir-pr.md` y ajustar sus
  acciones según [contracts/abrir-pr.md](contracts/abrir-pr.md) (FR-008, FR-009, FR-010,
  FR-019, R11; hace pasar T016). Orden: comprobaciones sin cambios → `git fetch origin main`
  (falla → se detiene) y `git fetch origin <rama>` (**no es fatal si la rama aún no existe
  en el remoto**) → `git rev-parse HEAD` y **se guarda el sha** → skills `revisar-codigo`
  y `auditar-cumplimiento` con la carpeta del ticket → `veredicto.py registrar --commit
  <sha guardado>` con las dos líneas `RESUMEN` (si sale con 2 porque `HEAD` cambió, no hay
  veredicto, push ni PR: se vuelve a ejecutar `/abrir-pr`) → con bloqueantes, se detiene
  sin push ni PR ni cambio de estado y muestra los hallazgos → `git push -u origin <rama>`
  → PR, estado y comentario. `allowed-tools`: salen `Agent` y `Bash(git diff:*)`;
  entran `Skill(revisar-codigo)`, `Skill(auditar-cumplimiento)`, el comando de
  `veredicto.py registrar` y `Bash(git rev-parse:*)`. La descripción del PR cita el
  veredicto, **ese sha guardado**, los dos `RESUMEN` y los hallazgos no bloqueantes. No
  quedan dos revisiones: se elimina el subagente `Plan`. **Ajuste tras la parada C**: la
  ruta del registro es relativa (`.claude/hooks/veredicto.py`, también en su regla de
  `allowed-tools`) y cada línea `RESUMEN` se valida con el formato exacto antes de pasarla
  (si no, `sin resumen`).
- [X] T018 [US3] Ejecutar `uv run ruff format .claude/hooks`, `uv run ruff check
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

- [X] T019 [P] [US4] Escribir `.claude/hooks/test_guarda_pr.py` (R10, FR-012 a FR-014,
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
  - **Ampliado tras la parada D** (hallazgos 1 y 2): `gh pr new` (el alias oficial de
    `gh pr create`), con sus opciones (`--fill`, `--head`, `-H`) y en todos los envoltorios
    de `gh pr create`, se bloquea y se permite igual que él; y `gh api` con el endpoint como
    URL completa (`https://api.github.com/repos/<o>/<r>/pulls`, con `https://<host>/api/v3/…`
    de GitHub Enterprise y con `?query`) con POST explícito o implícito se bloquea, mientras
    que la URL con GET, la de una subruta (`…/pulls/1`) y la de otro recurso se permiten;
  - **Publicación** (R9): sin `origin/<rama>`, con `origin/<rama>` distinta de HEAD
    (bloquea), y con la rama actual distinta de la del PR;
  - **Fallo cerrado**: una excepción propia sale con 2; un script que sale con 1 queda
    cubierto por `onFailure`;
  - **Extremo a extremo** por stdin: salida 2 con una sola línea `[guarda_pr] <motivo>. <qué
    hacer>.` en stderr, y nada en stdout al permitir;
  - **Tiempo** (SC-004, A1): una llamada en caliente, desde la segunda, tarda menos de 1 s.
- [X] T020 [US4] Implementar `.claude/hooks/guarda_pr.py` (solo biblioteca estándar;
  [contracts/veredicto-y-guarda.md](contracts/veredicto-y-guarda.md); R9, R10; hace pasar
  T019). Interfaz común de #3 con `comun.ejecutar` y `comun.bloquear`, y el extractor de
  texto ejecutable de `comun.py` para `gh` envuelto. Comprobación en el orden del
  contrato: rama del PR = rama actual → `origin/<rama>` existe → es igual a HEAD → existe
  el veredicto → es `aprobado`. Compara con la referencia local, nunca con `git ls-remote`.
- [X] T021 [P] [US4] Ampliar `.claude/hooks/test_configuracion.py` **solo con tests**, que
  deben fallar primero (FR-016, R10, R12, R8): la guarda está registrada con `onFailure:
  "block"`, `timeout: 10` y el matcher es la lista exacta
  `Bash|PowerShell|mcp__github__create_pull_request`; `permissions.deny` incluye
  `Edit(/.claude/veredictos/**)` junto a la de `settings.local.json`; y el resto de las
  entradas de #3 no cambia. No toca `settings.json`.
- [X] T022 [P] [US4] Ampliar `.claude/hooks/test_guarda_spec_previa.py` con la protección del
  directorio de veredictos (FR-020, R8; debe fallar primero): se bloquea en cualquier rama
  (también en una rama de ticket con sus documentos) escribir, editar, notebook, `>` y
  `>>`, `tee`, `cp`, `mv`, `sed -i`, `touch` y código en línea (`python -c`, `node -e`,
  `bash -c`, `eval`, heredoc a un intérprete) que lo nombre; se permite leerlo (`Read`,
  `cat`); el comando `uv run … veredicto.py registrar …` no se bloquea. Mensaje: `El
  directorio de veredictos solo lo escribe el registro de la revisión. Ejecuta /abrir-pr.`
  - **Ampliado tras la parada D** (hallazgo 3), en cualquier rama, también para
    `settings.local.json` (FR-025 de #3), con una regla **sobre el destino** y no sobre el
    origen (segunda ronda): hacia la carpeta `.claude` misma, toda copia recursiva y todo
    movimiento se bloquea sin mirar el origen (`cp -r /tmp/falso/. .claude`,
    `cp -a /tmp/falso/. .claude/`, `cp -r /tmp/falso/* .claude/`, `cp -rT /tmp/falso .claude`,
    `cp -r --no-target-directory /tmp/falso .claude`, `cp -R /tmp/falso/ .claude` (en macOS y
    BSD, la barra final copia el contenido), `mv -T /tmp/falso .claude`,
    `Copy-Item -Recurse C:\tmp\falso\* .claude`); hacia subcarpetas (`.claude/agents/…`), la
    regla normal; hacia la raíz, la copia recursiva con origen opaco (`/.`, comodines), con
    `-T`/`--no-target-directory` o con barra final; y borrar o mover `.claude` entera:
    `rm -rf .claude`, `Remove-Item -Recurse -Force .claude`, `mv .claude x`. Se siguen
    permitiendo `cp archivo .claude/otro-directorio/`, `cp archivo .claude/` (sin recursión),
    `ls .claude`, `cp -r src/otro dir-temporal/` y `cp -r /tmp/falso .` (sin barra, que copia la
    carpeta entera con su nombre), y se sigue bloqueando cuando el nombre aparece
    (`cp -r …/veredictos .claude/`, `Move-Item`).
  - **Ampliado tras la parada F** (hallazgo): hacia la carpeta `.claude` misma, también se
    bloquea la copia **no recursiva** con origen que lleva comodines: `cp /tmp/x/* .claude/`,
    `cp /tmp/x/settings.local.* .claude/`, `Copy-Item C:\tmp\x\* .claude\` (antes salían con 0 y
    colocaban un `settings.local.json` falso). Siguen permitidos `cp /tmp/x/*.md
    .claude/agents/` y `cp nota.md .claude/`. Los tests que permitían `cp /tmp/falso/*
    .claude/` y `Copy-Item C:\tmp\falso\* .claude` pasan a la lista de bloqueados.
- [X] T023 [US4] Ampliar `.claude/hooks/guarda_spec_previa.py` (FR-020, R8; hace pasar T022):
  añadir `.claude/veredictos/**` al mismo tratamiento que `.claude/settings.local.json`
  (FR-025 de #3), con las mismas vías y sin distinguir rama, pero permitiendo la lectura.
  Leer antes el código de FR-025 y reutilizarlo; no duplicar el recorrido de comandos.
- [X] T024 [US4] Registrar la guarda y la denegación en `.claude/settings.json` (FR-016,
  R8, R10; hace pasar T021): la entrada `PreToolUse` de
  [contracts/veredicto-y-guarda.md](contracts/veredicto-y-guarda.md), con el matcher
  `Bash|PowerShell|mcp__github__create_pull_request`, `timeout: 10` y `onFailure: "block"`;
  y `Edit(/.claude/veredictos/**)` en `permissions.deny`, junto a la de
  `settings.local.json`, sin reordenar la lista. **Esta es la tarea en que la guarda
  empieza a actuar** (ver "Reglas para todas las tareas"); va después de T017.
- [X] T025 [US4] Ejecutar `uv run ruff format .claude/hooks`, `uv run ruff check
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

- [X] T026 [P] Escribir la entrada 5 de `DECISIONES.md` (FR-018, SC-006), con unas 15
  líneas y una por decisión, y el detalle remitido a `research.md`: dos subagentes de solo
  lectura y una skill con `context: fork` por revisión (R1, R5); inyección con script que
  sale siempre con 0, marca `CONTEXTO DE REVISIÓN` y umbral sobre toda la salida (R2, R4);
  la constitución se lee con `Read` (R3); veredicto por commit, protegido, y rama sin
  cambios rechazada por el registro (R8); puerta con `origin/<rama>` local, no `ls-remote`
  (R9); la guarda de PR (R10). Los **riesgos residuales**: (1) invocar `veredicto.py
  registrar` con `RESUMEN` inventados; (2) crear el PR fuera de Claude Code, alias de `gh`
  y construcciones que el extractor no reconoce; (3) commits empujados por otra persona
  tras el último `fetch`; (4) `Read` del subagente y `guarda_secretos`; (5) la calidad de
  la revisión depende del modelo; (6) la validación de la línea `RESUMEN` antes de pasarla es
  una instrucción de `/abrir-pr`, no código (contrato, "Límites declarados"); (7) la ruta
  relativa del registro exige ejecutarlo desde la raíz y, si no, `/abrir-pr` se detiene sin
  push ni PR (falla cerrado); (8) la mutación GraphQL leída de un archivo (`-F query=@archivo`,
  `--input`) y otros clientes HTTP (`curl`, etc.) con el token de `gh`, que son rodeos
  deliberados; (9) los alias propios de `gh` (`gh alias set`): el alias oficial `gh pr new`
  sí se bloquea. Añadir una nota en la entrada 3 ("la revisión de
  transición de `/abrir-pr` queda reemplazada por #4"). Los resultados de Q1 a Q6 se añaden
  en T033.
- [X] T027 [P] Añadir una frase en la sección "Ciclo de un ticket" de `README.md`:
  `/abrir-pr` ejecuta la revisión independiente y la auditoría, y el hook bloquea el PR sin
  veredicto aprobado del commit actual. `CLAUDE.md` no cambia.
- [X] T028 Ejecutar la suite completa y `uv run ruff format --check .`, `uv run ruff check
  .`, y commitear: `docs: decisiones y ciclo de ticket de la revisión independiente`.

---

## Phase 8: Sesión nueva y quickstart (Polish & Cross-Cutting)

**Purpose**: validar de extremo a extremo con una sesión nueva. Se hace con la implementación
**commiteada**. Los escenarios están en el [quickstart](quickstart.md).

- [X] T029 [MANUAL] La analista abre una **sesión nueva** de Claude Code en la raíz, tras
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
  `/revisar-codigo`; el diff es el del #3 más el del #4 (56 archivos, ≈ 663 KB, medido el 2026-10-16) y
  debe terminar con `cobertura=completa`. No sirve el rango `b7d5f48^1..5225965` (vacío)
  ni un worktree (movería el `origin/main` real).
- [X] T031 Fijar `UMBRAL_SALIDA` en `.claude/hooks/preparar_revision.py` en **la mitad del
  techo medido en Q4** (A2) y el test de T004 que lo fija; y, si Q1 pide otra variable o
  patrón, corregir las dos skills y `/abrir-pr`. Si no hace falta ningún cambio, se anota.
  Commit nuevo: `fix(revision): ajuste con las comprobaciones de la sesión`.
- [X] T032 Ejecutar Q5 y Q6 (R5, R13) y anotar: si `guarda_secretos` alcanza a las
  herramientas del subagente y si la inyección pasa por `PreToolUse`. Si `Read` del
  subagente queda sin protección, declararlo en la entrada 5 de `DECISIONES.md` (T033).
- [X] T033 Ejecutar Q7 a Q10 (revisión, auditoría y que los revisores no modifican nada)
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

---

## Resultados de la validación

Sesión nueva del 2026-10-16, rama `004-revision-independiente-auditoria`, Windows.

### Notas de T029

- `/agents` ya no existe en esta versión de Claude Code («The /agents wizard has been
  removed»). Los subagentes se comprueban en Q1 y Q3; las skills `/revisar-codigo` y
  `/auditar-cumplimiento` aparecen como (project).
- `/hooks` muestra cinco `PreToolUse` [Project] (incluida `guarda_pr`) y una `PostToolUse`
  [Project]. Los hooks [User] y [Plugin] que se ven son del equipo de la analista, no del
  proyecto.
- El diff de Q4(b) medido hoy es de 56 archivos y ≈ 663 KB (no 41 y 475 KB).

### Q1 (parcial: desde la raíz)

- `/revisar-codigo specs/004-revision-independiente-auditoria` desde la raíz: la inyección con
  `${CLAUDE_PROJECT_DIR}` se resolvió y corrió sin pedir permiso; el revisor recibió el
  contexto con la marca `CONTEXTO DE REVISIÓN`, sin `CONTEXTO INCOMPLETO`, y el aviso de diff
  omitido por tamaño. Terminó con `RESUMEN: bloqueantes=2 sugerencias=3 cobertura=incompleta`
  (los bloqueantes eran T030 a T036 aún abiertas; la cobertura quedó incompleta porque no
  leyó los archivos de test).
- Pendiente: desde una subcarpeta y desde un clon en otra ruta.

### Q2

- El revisor dispone solo de `Read`, `Grep` y `Glob` (más la herramienta de entrega del
  informe). No tiene Bash, Write, Edit ni Agent; ninguno de los cuatro intentos fue posible y
  `prueba-q2.txt` no se creó. El diseño de R2 se mantiene.

### Q3

- La constitución y el `CLAUDE.md` del proyecto llegan al subagente en su contexto inicial
  (por el `@import`): citó la primera línea del principio I sin usar `Read`, `Grep` ni `Glob`.
  Dato para `DECISIONES.md` (R3); el diseño sigue pidiendo leerla con `Read`.

### Q4(a)

Medido con la skill temporal `medir-salida` (inyección `` !`...` `` que imprime líneas de 89
bytes ASCII y termina con `FIN-<n>`), una invocación por tamaño, el 2026-10-16:

| Tamaño pedido (bytes) | Resultado |
|---|---|
| 20 000 | en línea, completa (`FIN-20000`) |
| 29 000 | en línea, completa (`FIN-29000`) |
| 30 000 | **no llega en línea**: vista previa de 2 KB y ruta a un archivo (`Output too large (29.7KB)`); sin `FIN-` |
| 40 000 | **no llega en línea**: vista previa de 2 KB y ruta a un archivo (`Output too large (39.6KB)`); sin `FIN-` |

- Techo real: entre 29 000 y 30 000 bytes; en la práctica, 30 000 es el límite (coincide con el
  valor provisional). Por encima, el modelo no recibe el contenido sino una vista previa de
  2 KB y una ruta, sin aviso de truncado distinto de ese mensaje.
- Para T031: la mitad del techo es ≈ 14 500 bytes (mitad del mayor tamaño confirmado en
  línea, 29 000). El provisional de 30 000 es el techo, no su mitad, y debe bajarse.
- La skill temporal `medir-salida` se borró y no se commiteó (T031).

### Q4(b) y Q1 desde el clon (`C:\Temp\clon-q4`)

Con las instrucciones anteriores a las correcciones de cobertura:

- `RESUMEN: bloqueantes=2 sugerencias=2 cobertura=incompleta`; diff omitido: sí.
- Bloqueantes: T029 a T036 abiertas y `UMBRAL_SALIDA` provisional (esperables).
- No cubrió: los tests del #4, el código del #3, `.claude/rules`, `README`, `DECISIONES`, 330 de
  las 586 líneas de `guarda_spec_previa.py`, y «no ejecutó tests».
- Hallazgo de la analista: el revisor no sabía qué cuenta para la cobertura. Contó la
  documentación de referencia y «no ejecutar tests» (no tiene Bash), y en Q1 (solo el #4: 7
  archivos de código, +893 líneas, y 6 de tests, +1834) no leyó los tests. `/abrir-pr` nunca
  habría aprobado el ticket. Corregido en `884adee` (contrato), `e20e9f4` (subagentes y skills)
  y `f1d9b0c` (`UMBRAL_SALIDA = 14_500`).

### Q1 desde la subcarpeta `specs`

- Pendiente: el mensaje de la analista trajo la marca `<COMPLETE AQUÍ>`; lo completa ella.

### T030, revisión en la raíz tras las correcciones (2026-10-16, HEAD `f1d9b0c`)

`/revisar-codigo specs/004-revision-independiente-auditoria` desde la raíz:

- `RESUMEN: bloqueantes=1 sugerencias=8 cobertura=completa`. El contexto llegó completo, leyó
  enteros el código, la configuración y los tests, y no contó «no ejecutar tests» ni la
  documentación de referencia como faltas. Con el diff omitido por tamaño, la cobertura
  completa se consigue con el plan de lectura.
- El bloqueante es el esperado: T030 a T036 abiertas.
- Sugerencias: 3 eran defectos reales y se corrigieron en `db40b84`: un literal corrupto (un
  tabulador y un salto de página) en un test de `test_guarda_spec_previa.py`; que
  `settings.local.json` se comparaba sin `casefold` (en Windows y macOS `.claude/Settings.local.json`
  escapaba); y que `gh api -p x …/pulls -X POST` tomaba `x` como endpoint.
- Quedan como sugerencias, sin corregir: `cp /tmp/falso/* .claude/` sin `-r` sigue permitido (no
  crea directorios, así que no afecta a los veredictos, pero sí podría sobrescribir
  `settings.local.json`); `_nombre` repetida en tres módulos; con unos 140 archivos la lista se
  agrupa por directorio y entonces la cobertura es incompleta; y el bloque de cobertura repetido
  en cuatro archivos.

### Q5 y Q6 (T032)

- **Q5**: el subagente `revisor-codigo` intentó leer `.env.local`. `Read` lo bloqueó la regla de
  permisos («File is in a directory that is denied by your permission settings») y `Grep`, el
  hook `guarda_secretos` (`[guarda_secretos] Acceso bloqueado a un archivo de secretos
  (.env.local) con Grep`). Los hooks **sí** alcanzan a las herramientas del subagente. No llegó
  a ver contenido (0 líneas).
- **Q6**: una skill temporal inyectó `grep -r <patrón inexistente> .` desde la raíz, que contiene
  `.env.local`; como comando normal de Bash, `guarda_secretos` lo bloquea. La inyección **se
  ejecutó**: **no pasa por `PreToolUse`**, solo por las reglas de permisos. El diseño no depende
  de ello (el único comando inyectado es fijo, versionado y sin argumentos) y se declara como
  residual en `DECISIONES.md`. La skill temporal se borró y no se commiteó.

### Q7 a Q15 (T033)

Rama temporal `099-prueba`, desde la del ticket, con `specs/099-prueba/` y datos ficticios, y con
`refs/remotes/origin/main` movido a propósito entre commits para que el diff fuera solo el de la
prueba. **`origin/main` se restauró con `git fetch origin main` y vale otra vez `b7d5f48`.** Los
commits A a F son temporales y no se publicaron.

| Q | Escenario | Resultado |
|---|-----------|-----------|
| Q7 | `/revisar-codigo` con un defecto (`dividir` sin proteger) y una regla I.1 incumplida | `bloqueantes=4 sugerencias=1 cobertura=completa`: reportó los dos con `archivo:línea` (`division.py:5`, `consulta_listas.py:6`) y que faltaban los tests |
| Q8 | `/auditar-cumplimiento` sobre lo mismo | I.1 `incumple`, I.2 a I.5 `no aplica` con razón; `bloqueantes=3 sugerencias=0 cobertura=completa` |
| Q9 | `/auditar-cumplimiento` sobre este ticket | las cinco reglas `no aplica`, con la razón; `bloqueantes=0 sugerencias=0 cobertura=completa` |
| Q9b | commit que solo borra el test de I.3 | I.3 **no** sale `no aplica`: `no verificada` y bloqueante; `bloqueantes=2 sugerencias=1 cobertura=completa` |
| Q10 | `git status` y `git log` antes y después de Q7, Q8 y Q9b | idénticos: mismo `HEAD`, sin cambios sin commitear y sin stashes |
| Q11 | sin veredicto, en la sesión: `create_pull_request` del MCP, `gh pr create`, `gh pr new` y `gh api -X POST …/pulls` | los cuatro bloqueados por `guarda_pr`. `gh pr view 17` y `gh api …/pulls/17` (GET) se permiten |
| Q12 | `veredicto.py registrar` con bloqueantes, y con la rama sin cambios | `con bloqueantes (2 bloqueante(s) en la revisión de auditoría)` y `con bloqueantes (sin cambios)`, ambas con salida 1 y el archivo registrado |
| Q13 | commit con el defecto corregido y los tests restaurados; las dos skills de nuevo | `bloqueantes=0` en las dos (la primera vez la revisión pidió el test de I.3 que el commit C había borrado); `registrar` → `aprobado`, salida 0 |
| Q14 | con veredicto aprobado, intentar crear el PR (con el commit sin publicar, y otra vez tras un commit nuevo) | bloqueado las dos veces (`El commit no está publicado en origin/099-prueba`). El caso del veredicto de otro commit y de la rama remota distinta están en `test_guarda_pr.py`, por stdin |
| Q15 | tiempo de `guarda_pr.py` con el comando real de `settings.json`, en caliente | ≈ 475 a 495 ms por llamada: **pasa** (< 1 s) |

- La guarda comprueba antes la publicación que el veredicto, así que en la sesión el mensaje es
  el de «no publicado»; que con veredicto aprobado y commit publicado se **permite** lo prueba
  `test_guarda_pr.py` por stdin, porque publicar crearía una rama remota.
- SC-005 (que quien no conoce el código entienda los reportes sin abrirlo): pendiente de la
  analista, con los reportes de Q7 y Q8 de esta sesión.

### Q16 (T034, parcial)

- En la rama del ticket y en `prueba-revision` (sin patrón `NNN-`): `Write` y `Edit` sobre
  `.claude/veredictos/` los deniega `permissions.deny`; `echo >`, `cp`, `mv` y `python -c` que lo
  nombra los bloquea `guarda_spec_previa` («El directorio de veredictos solo lo escribe el
  registro de la revisión»). Leerlo con `Read` y `cat` se permite y `veredicto.py registrar`
  funciona. Ninguna de las pruebas creó ni modificó archivos.
- Q17 (inyección desactivada con `disableSkillShellExecution`): pendiente de la analista, porque
  exige editar `settings.local.json` desde fuera de Claude Code.

