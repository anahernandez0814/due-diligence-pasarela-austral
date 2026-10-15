---

description: "Lista de tareas del ticket #2, automatización del ciclo de tickets en GitHub"
---

# Tasks: Automatización del ciclo de tickets en GitHub

**Input**: Documentos de diseño en `specs/002-automatizacion-tickets/`: [plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/) y [quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/
y quickstart.md.

**Tests**: el ticket no añade Python, así que no hay tests pytest nuevos. La validación es
el [quickstart](quickstart.md) (Q1–Q9) más ruff y pytest en verde sobre lo existente.

**Organization**: tareas agrupadas por historia de usuario (US1 a US4 de la spec), cada una
verificable por separado.

**Alcance de este archivo (FR-018)**: solo contiene tareas que se completan **antes del
merge**. La verificación del cierre de #2 y el primer arranque real (Q10 y Q11) no son
tareas. Los hace `/siguiente-ticket` después del merge y quedan registrados en comentarios
de los issues #2 y #3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario a la que pertenece (US1, US2, US3, US4).
- Rutas relativas a la raíz del repositorio.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: confirmar el punto de partida del ticket.

- [X] T001 Confirmar el punto de partida:
  - La rama activa es `002-automatizacion-tickets`.
  - `git log --oneline main..HEAD` contiene los commits de spec, plan, ajustes del plan y tareas.
  - `git status --porcelain` está vacío.
  - El issue #2 está en "In Progress": `mcp__github__projects_list`, `list_project_items`, `field_names: ["Status"]`.
- [X] T002 Confirmar que no existen `.specify/extensions.yml`, `.claude/commands/` ni `.claude/skills/siguiente-ticket/`. Confirmar también que `git diff --stat main -- .claude/skills/speckit-*` está vacío: las skills de Spec Kit no se editan en este ticket.

**Checkpoint**: rama limpia y ninguna pieza del flujo creada aún.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: confirmar los nombres reales de los que dependen la skill y los comandos.

- [X] T003 Leer con `mcp__github__projects_list` (`list_project_fields`, Project #1 de `anahernandez0814`) el campo Status. Confirmar que tiene exactamente las opciones `Todo`, `In Progress`, `In review` y `Done`, sin variantes de mayúsculas ni espacios (data-model: "La opción de Status se busca por nombre exacto en `list_project_fields`; si no está, el flujo se detiene"). Si difieren, detenerse y reportarlo antes de escribir nada.

**Checkpoint**: los nombres que escribirán la skill y los comandos coinciden con el Project.

---

## Phase 3: User Story 1 - Tomar el siguiente ticket y arrancarlo (Priority: P1) 🎯 MVP

**Goal**: con una sola invocación, el ticket elegido pasa a "In Progress", recibe el
comentario de inicio y tiene rama y carpeta de specs con el número del issue.

**Independent Test**: Q1–Q4 y Q4b del [quickstart](quickstart.md). El arranque positivo
(Q11) se valida después del merge, con el primer uso real.

### Implementation for User Story 1

- [X] T004 [US1] Crear `.claude/skills/siguiente-ticket/SKILL.md`:
  - Frontmatter exacto de [contracts/siguiente-ticket.md](contracts/siguiente-ticket.md): `name`, `description`, `argument-hint: "[número de issue]"` y la lista de `allowed-tools` (git status/switch/pull/branch/ls-remote, Read, Glob, Skill y las cinco herramientas `mcp__github__*`).
  - Sin `context: fork` (research R9).
  - Sección "Entrada": sin argumento, el menor número en Todo; con un entero N, el issue #N; con cualquier otro argumento, muestra el uso y se detiene.
- [X] T005 [US1] En `.claude/skills/siguiente-ticket/SKILL.md`, escribir el "Paso 1, comprobaciones" en el orden exacto del contrato:
  1. `git status --porcelain` vacío, guardando antes la rama actual con `git branch --show-current`.
  2. `list_project_fields` con la opción exacta "In Progress".
  3. Ticket abierto, en el Project y en Todo. Si no queda ninguno en Todo, lo informa y termina.
  4. Nombre corto, NNN y rama.
  5. `git ls-remote --heads origin NNN-<nombre-corto>` vacío.
  6. `git switch main` y `git pull --ff-only`.
  7. Sobre `main`: `git branch --list NNN-<nombre-corto>` vacío y ninguna carpeta `specs/NNN-*`.

  Si fallan 6 o 7, `git switch <rama guardada>` y lo informa. Dejar escrito que hasta aquí no se mueve ni se comenta nada.
- [X] T006 [US1] En `.claude/skills/siguiente-ticket/SKILL.md`, escribir la regla del nombre corto (research R7):
  - Quitar tildes y diacríticos y pasar a minúsculas.
  - Cambiar lo que no sea `a-z0-9` por espacios.
  - Quitar las palabras vacías: a, al, con, de, del, el, en, la, las, los, para, por, un, una, y.
  - Tomar las tres primeras palabras y unirlas con `-`.
  - NNN es el número del issue con tres dígitos.
  - Incluir los ejemplos: "Guardas de Claude Code: hooks, permisos y reglas por ruta" → `guardas-claude-code`; "Interfaz de chat" → `interfaz-chat`.
- [X] T007 [US1] En `.claude/skills/siguiente-ticket/SKILL.md`, escribir el "Paso 2, acciones", en este orden:
  1. `mcp__github__projects_write` `update_project_item` con `updated_field {"name": "Status", "value": "In Progress"}`.
  2. Comentario `inicio` con la plantilla de [contracts/comentarios.md](contracts/comentarios.md), que empieza con `<!-- ciclo-tickets:inicio -->` e incluye la línea "Siguiente: …". Antes de publicarlo, `get_comments` comprueba que no exista ya uno con ese marcador.
  3. `git switch -c NNN-<nombre-corto>`.
  4. Invocar `/speckit-specify` con la herramienta Skill, pasando el cuerpo del issue, `SPECIFY_FEATURE_DIRECTORY=specs/NNN-<nombre-corto>` y `--number N`.
  5. Comprobar que `.specify/feature.json` contiene `"feature_directory": "specs/NNN-<nombre-corto>"` y que existe su `spec.md`.
  6. Comprobar que el issue tiene el comentario `especificado`. Si falta, informarlo y sugerir `/comentar-avance especificado`, **sin publicarlo**.

  Si algo falla después del paso 1, decir el paso exacto y que el ticket quedó en "In Progress", sin revertir en silencio.
- [X] T008 [US1] En `.claude/skills/siguiente-ticket/SKILL.md`, escribir:
  - La "Secuencia del ticket": specify → clarify (solo con marcadores `[NEEDS CLARIFICATION]`) → plan → tasks → analyze → implement → converge (solo si quedan brechas) → `/abrir-pr`.
  - Los recordatorios:
    - Los hooks de `.specify/extensions.yml` publican los comentarios.
    - `tasks.md` solo lleva tareas anteriores al merge.
    - `/abrir-pr` hace la revisión previa.
  - El formato de salida en español: paso 0, ticket, rama, carpeta, enlace al comentario y siguiente comando.

**Checkpoint**: la skill arranca un ticket; todavía sin paso 0 (US4).

---

## Phase 4: User Story 2 - Abrir el pull request del ticket (Priority: P2)

**Goal**: `/abrir-pr` se detiene si faltan los artefactos o si la revisión previa
(FR-023) tiene bloqueantes. Si no, abre el PR con `Closes #N`, pasa el ticket a
"In review" y comenta.

**Independent Test**: Q8 (caso negativo con la rama temporal `999-prueba-abrir-pr`) y Q9
(PR real del ticket #2).

### Implementation for User Story 2

- [X] T009 [P] [US2] Crear `.claude/commands/abrir-pr.md` con:
  - El frontmatter exacto de [contracts/abrir-pr.md](contracts/abrir-pr.md), incluidos `Agent`, `Bash(git fetch:*)` y `Bash(git diff:*)`.
  - La sección "1. Comprobaciones":
    1. Rama distinta de `main` que cumple `^(\d{3})-[a-z0-9-]+$`.
    2. Árbol limpio.
    3. Una sola carpeta `specs/NNN-*`, con `spec.md`, `plan.md` y `tasks.md` en `HEAD` según `git cat-file -e HEAD:<ruta>`.
    4. Issue #N abierto.
    5. Ningún PR abierto para la rama (`list_pull_requests` con `head: anahernandez0814:<rama>`).
    6. Opción exacta "In review".

  Si alguna falla: sin push, sin PR y sin cambio de estado.
- [X] T010 [US2] En `.claude/commands/abrir-pr.md`, escribir la sección "2. Revisión previa" como bloque aislado, con un encabezado que diga que el ticket #4 la reemplaza por `revisar-codigo`, `auditar-cumplimiento` y su puerta mecánica:
  1. `git fetch origin main` y `git diff origin/main...HEAD`.
  2. Subagente de tipo `Plan` en contexto separado, con la instrucción de no ejecutar comandos con efectos. Recibe el diff, `spec.md`, `plan.md`, `tasks.md`, los criterios de aceptación del issue y la constitución.
  3. Devuelve un veredicto (aprobado, aprobado con cambios o bloqueado) y los hallazgos con severidad (bloqueante, importante o menor), archivo y motivo.
  4. Con algún bloqueante, se detiene sin push.
- [X] T011 [US2] En `.claude/commands/abrir-pr.md`, escribir la sección "3. Acciones":
  1. `git push -u origin <rama>`.
  2. `create_pull_request` con título `<título del issue> (#N)` y descripción en español con: resumen, criterios de aceptación verificados, "Revisión previa" (veredicto y hallazgos no bloqueantes), desviaciones y pendientes, `Closes #N` y la línea final exacta `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
  3. `update_project_item` a "In review".
  4. Comentario `<!-- ciclo-tickets:pr -->` con lo especificado, lo decidido y lo pendiente, y el enlace al PR. No se publica si ya existe uno con ese marcador.
  5. Salida con el recordatorio del contrato: "Tras el merge, el próximo `/siguiente-ticket` registra el cierre en el issue. Si era el último ticket, ejecútalo una vez más para registrarlo."

**Checkpoint**: `/abrir-pr` completo y aislado de cómo se haga la revisión.

---

## Phase 5: User Story 3 - Avance del ticket visible en el issue (Priority: P2)

**Goal**: los comandos de Spec Kit dejan en el issue lo especificado, lo decidido y lo
encontrado, sin editar sus skills.

**Independent Test**: Q6 (hook `after_analyze` al repetir `/speckit-analyze`) y Q7
(`/comentar-avance especificado`).

### Implementation for User Story 3

- [X] T012 [P] [US3] Crear `.claude/commands/comentar-avance.md` según [contracts/comentar-avance.md](contracts/comentar-avance.md):
  - Frontmatter con `argument-hint: "especificado | plan | analyze"` y `allowed-tools` (Read, `Bash(git branch:*)`, `issue_read`, `add_issue_comment`, `update_issue_comment`).
  - Con un argumento distinto de esos tres, incluido el vacío, se detiene diciendo que "el argumento no llegó".
  - N sale de `.specify/feature.json` y debe coincidir con la rama actual.
  - Contenido por tipo, según el contrato.
  - Si existe un comentario con el mismo marcador, se actualiza con `update_issue_comment`: conserva el cuerpo anterior completo y añade al final una sección `### Actualización <fecha>` con lo nuevo. Si no existe, se crea.
- [X] T013 [P] [US3] Crear `.specify/extensions.yml` con el contenido exacto de [contracts/comentar-avance.md](contracts/comentar-avance.md): `installed: []` y los hooks `after_specify` y `after_clarify` (`comentar-avance especificado`), `after_plan` (`comentar-avance plan`) y `after_analyze` (`comentar-avance analyze`), todos con `extension: ciclo-tickets`, `enabled: true`, `optional: false`, `priority: 10` y `condition: null`. Validar que el YAML se lee: `"/c/Users/ana.hernandez/AppData/Roaming/uv/tools/specify-cli/Scripts/python.exe" -c "import yaml,sys; print(yaml.safe_load(open('.specify/extensions.yml', encoding='utf-8'))['hooks'].keys())"` debe listar las cuatro claves.

**Checkpoint**: desde este momento, los comandos de Spec Kit de esta rama disparan los hooks.

---

## Phase 6: User Story 4 - Cierre automático y verificación posterior al merge (Priority: P3)

**Goal**: el paso a Done queda en manos de los workflows nativos, y su verificación se
registra en un comentario, sin tareas posteriores al merge.

**Independent Test**: Q5 (paso 0 sin pendientes). El cierre real de #2 (Q10) se valida
después del merge.

### Implementation for User Story 4

- [X] T014 [US4] En `.claude/skills/siguiente-ticket/SKILL.md` (depende de T004–T008), escribir el "Paso 0, verificación posterior al merge" antes del paso 1:
  - `list_project_items` con `query: "is:issue state:closed"` y `field_names: ["Status"]`.
  - Para cada issue con `state_reason: completed` sin comentario `<!-- ciclo-tickets:cierre -->`:
    - Con Status Done: comentario `cierre` con la plantilla de [contracts/comentarios.md](contracts/comentarios.md) (PR que lo cerró, `closed_at`, `updated_at` del ítem).
    - Con otro Status: anotarlo para el informe, sin mover la tarjeta y sin comentar.
  - Se excluyen los cerrados como `not_planned`.
  - Con el Todo vacío, hacer el paso 0 y luego informar que no quedan tickets.
  - Si `list_project_items` o `get_comments` fallan, detenerse e informarlo (FR-021), sin seguir con el arranque.
- [X] T015 [P] [US4] En `DECISIONES.md`:
  - Añadir la entrada 3, "Ciclo de tickets automatizado", **breve: unas 15 líneas, una por decisión, con el detalle remitido a `research.md`** (R1, R4, R5, R6, R9). El enunciado limita `DECISIONES.md` a dos páginas para las 11 necesidades, y el ticket #14 todavía tiene que completarlo. Recoge los puntos de plan.md, sección "Cambios en la documentación":
    - Done por "Item closed" y "Pull request merged" (FR-016).
    - Hooks de Spec Kit en `after_specify`, `after_clarify`, `after_plan` y `after_analyze`, y su alcance real: instrucciones que el modelo ejecuta, no hooks de Claude Code; sugerido, no garantizado, aceptable porque los comentarios no están en las garantías de II.
    - Paso 0 en lugar de tareas posteriores al merge.
    - `SPECIFY_FEATURE_DIRECTORY` porque `--number` no es estricto.
    - Por qué `siguiente-ticket` no usa `context: fork`.
    - Revisión previa aislada en `/abrir-pr`, con subagente `Plan`.
    - Marcadores.
    - Alternativas descartadas: una línea que remite a `research.md`.
  - Comprobar que la entrada 3 no pasa de unas 15 líneas.
  - Ajustar la entrada 2: desde #3 el ciclo usa `/siguiente-ticket`, los hooks y `/abrir-pr`; la revisión sigue de transición hasta #4; la desviación de II y X sigue hasta #3.

**Checkpoint**: las cuatro historias implementadas.

---

## Phase 7: Polish, validación y PR

**Purpose**: documentación breve, puertas de calidad, marcadores y validación en el orden
que exige el paso 0, y apertura del PR.

- [X] T016 [P] En `CLAUDE.md`, sustituir la línea "Mueve el ticket a In Progress al empezar y a In review al abrir el PR." por "Cada ticket se arranca con `/siguiente-ticket` y se cierra con `/abrir-pr`; no se mueven tarjetas a mano." Comprobar que `wc -l CLAUDE.md` da 40 como máximo (hoy 37) y que la importación `@.specify/memory/constitution.md` sigue presente una vez.
- [X] T017 [P] En `README.md`, añadir una sección breve "Ciclo de un ticket", con la secuencia `/siguiente-ticket` → specify → (clarify) → plan → tasks → analyze → implement → (converge) → `/abrir-pr` → merge, y una línea por pieza: skill, hooks de `.specify/extensions.yml` y `/abrir-pr`. Incluir que el cierre de cada ticket lo registra el siguiente `/siguiente-ticket` y que, tras el merge del último ticket, se ejecuta una vez más. Sin repetir `DECISIONES.md`; la ampliación es del ticket #14.
- [X] T018 Puertas de calidad:
  - `uv run ruff check .`, `uv run ruff format --check .` y `uv run pytest` en verde.
  - `git grep -nE "gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9-]{20,}"` sin resultados (principio VIII).
  - `git diff --stat main -- .claude/skills/speckit-*` vacío.
- [X] T019 Hacer commit de la implementación por partes lógicas, con mensajes en español: skill, comandos, `extensions.yml`, documentación. `git status --porcelain` debe quedar vacío.
- [X] T020 **Requisito previo de Q1.** Con `mcp__github__update_issue_comment`, editar el comentario de cierre del issue #1 (id `6191823695`) y añadir `<!-- ciclo-tickets:cierre -->` como primera línea, sin cambiar el resto del texto. Comprobar con `issue_read get_comments` que el marcador está.
- [X] T021 **Requisito previo de Q1.** Con `mcp__github__update_issue_comment`, editar el comentario de inicio del issue #2 (id `6192325009`) y añadir `<!-- ciclo-tickets:inicio -->` como primera línea, sin cambiar el resto. Comprobar que el issue #2 tiene ya los marcadores `inicio`, `especificado`, `plan` y `analyze`; este último lo publica a mano `/speckit-analyze` antes de implementar.
- [X] T022 Abrir una sesión nueva de Claude Code en la rama, para que se carguen la skill y los comandos nuevos.
  - **Desviación (2026-10-15)**: verificado en la misma sesión; las piezas se cargaron sin reiniciar. La analista comprobó que `/siguiente-ticket`, `/abrir-pr` y `/comentar-avance` aparecen en la lista de comandos y que el MCP `github` está conectado, así que no se abrió sesión nueva.
  - La primera instrucción en esa sesión es exactamente: "continúa tasks.md del ticket #2 desde T023". Así la sesión retoma desde este archivo, sin depender de la conversación anterior.
  - Antes de T023, comprobar en `/mcp` que `github` está conectado y que `/siguiente-ticket`, `/abrir-pr` y `/comentar-avance` aparecen en la lista de comandos.
- [X] T023 Ejecutar Q1, Q2, Q3, Q4, Q4b y Q5 del [quickstart](quickstart.md) en ese orden (depende de T020 y T021) y anotar el resultado de cada uno en esta tarea. En Q1–Q3, el paso 0 debe informar que no hay issues cerrados por verificar, y #1 no debe recibir comentarios nuevos. En Q4 el paso 0 no corre, porque la entrada inválida se rechaza antes (`0e8e1cb`). Después de Q1, restaurar el archivo modificado.
  - **Resultado (2026-10-15)**:
    - **Q1** (`/siguiente-ticket 3` con `README.md` modificado): el paso 0 no encontró nada que registrar y la skill se detuvo en la comprobación 1.1, árbol sucio. #3 siguió en Todo con 1 comentario, sin rama `003-*` local ni remota. Se restauró el README.
    - **Q2** (`/siguiente-ticket 2`): se detuvo porque el Status de #2 es `In Progress`, no `Todo`. Sin cambios.
    - **Q3** (`/siguiente-ticket 1`): la primera ejecución reveló el defecto de que, con `state:open`, decía "no está en el Project". Se corrigió en `dc7ede6`. Ahora se detiene con "#1 está cerrado (`completed`)".
    - **Q4** (`/siguiente-ticket abc`): muestra el uso y se detiene sin efectos. Reveló una ambigüedad entre "Entrada" y el paso 0, corregida en `0e8e1cb` y `c76d497`: la entrada se valida antes del paso 0.
    - **Q4b**: tras Q2, Q3 y Q4, la sesión siguió en `002-automatizacion-tickets`.
    - **Q5**: el paso 0 de Q1–Q3 no tuvo nada que registrar, y #1 siguió con 4 comentarios, sin duplicar el cierre.
- [X] T024 Ejecutar Q6: repetir `/speckit-analyze` y comprobar que emite `EXECUTE_COMMAND: comentar-avance analyze`, que `/comentar-avance` recibe `analyze` y que el comentario `analyze` de #2 se actualiza sin duplicarse. **Si el argumento no llega**, aplicar el plan B:
  - Crear `.claude/commands/comentar-especificado.md`, `comentar-plan.md` y `comentar-analyze.md`, sin argumento y con la misma lógica.
  - Cambiar los `command` de `.specify/extensions.yml`.
  - Actualizar contracts/comentar-avance.md, `DECISIONES.md` y el comentario del plan del issue.
  - Hacer commit y repetir Q6.
  - **Resultado (2026-10-15)**: `/speckit-analyze` terminó emitiendo `EXECUTE_COMMAND: comentar-avance analyze`, y `/comentar-avance` recibió `analyze`, así que el argumento llega y **no hace falta el plan B**. El comentario `analyze` de #2 (id `6196776121`) se amplió con "Actualización 2026-10-15", conservando completo lo anterior, y no se creó otro. El análisis dio 0 críticos, altos y medios, y 2 bajos: I2, la redacción de T023, corregida en esta anotación, y U2, el caso límite de argumento no numérico, en `a9aa629`.
- [X] T025 Ejecutar Q7: `/comentar-avance especificado` amplía el comentario `especificado` de #2 con una sección "Actualización <fecha>", conserva el texto anterior y no crea otro.
  - **Resultado (2026-10-15)**: el comentario `especificado` (id `6195609150`) se amplió con "Actualización 2026-10-15", con FR-023, FR-014, FR-022, los casos límite y el supuesto ajustado. Conservó su texto y no se creó otro.
- [X] T026 Ejecutar Q8:
  1. `git switch -c 999-prueba-abrir-pr` y `/abrir-pr`. Debe detenerse por no existir `specs/999-*`, sin revisión, sin push y sin PR.
  2. `git switch 002-automatizacion-tickets` y `git branch -d 999-prueba-abrir-pr`. Basta el borrado seguro, porque la rama no tiene commits propios.
  3. Comprobar con `git ls-remote --heads origin 999-prueba-abrir-pr` que no se subió.
  - **Resultado (2026-10-15)**: `/abrir-pr` pasó las comprobaciones 1 (formato de rama) y 2 (árbol limpio) y se detuvo en la 3: no existe `specs/999-*`. No lanzó revisión, no hizo push y no abrió PR. `git branch -d` borró la rama sin error, y `git ls-remote` confirma que nunca se subió.
- [X] T027 Anotar en T023–T026 los resultados, marcar T001–T026 y hacer commit (`docs(specs): validación del quickstart del ticket #2`), para que el árbol quede limpio antes de `/abrir-pr`.
- [ ] T028 Ejecutar Q9: `/abrir-pr` en `002-automatizacion-tickets`.
  - Si la revisión previa devuelve bloqueantes, corregirlos, hacer commit y repetir.
  - Comprobar el PR hacia `main` con `Closes #2`, la sección "Revisión previa" y la línea de atribución exacta.
  - Comprobar que #2 está en "In review" y tiene el comentario `pr`.
  - Comprobar que la salida termina con el recordatorio del cierre tras el merge.
- [ ] T029 Marcar T028 y T029 en este archivo, hacer commit (`docs(specs): marca T028 y T029 del ticket #2`) y `git push` a la rama del PR, **antes del merge**. Después del merge no queda ninguna tarea pendiente (FR-018).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup y bloquea todas las historias (T003 fija los nombres de Status).
- **User Stories (Phases 3 a 6)**: dependen de Foundational.
  - US1, US2 y US3 tocan archivos distintos y son independientes entre sí.
  - US4 depende de US1, porque T014 escribe en el mismo `SKILL.md`. T015 es independiente.
- **Polish (Phase 7)**: depende de las cuatro historias. El orden es obligatorio:
  1. Documentación y puertas: T016 y T017 en paralelo, después T018 y T019.
  2. **Marcadores: T020 y T021**, antes de cualquier `/siguiente-ticket`.
  3. Sesión nueva: T022.
  4. Pruebas sin efectos: T023, T024, T025 y T026.
  5. Commit de resultados: T027.
  6. PR real: T028.
  7. Marca final antes del merge: T029.

### User Story Dependencies

- **US1 (P1)**: T004 → T005 → T006 → T007 → T008 (mismo archivo).
- **US2 (P2)**: T009 → T010 → T011 (mismo archivo).
- **US3 (P2)**: T012 y T013 en paralelo (archivos distintos).
- **US4 (P3)**: T014 después de T008; T015 en paralelo con todo.

### Orden de las tareas MCP respecto a las pruebas

```text
T019 commit de la implementación
  └─▶ T020 marcador "cierre" en #1  ┐  requisito previo de Q1: el paso 0 corre en
      T021 marcador "inicio" en #2  ┘  cada /siguiente-ticket, incluidas Q1–Q4
        └─▶ T022 sesión nueva
              └─▶ T023 Q1–Q5 y Q4b ─▶ T024 Q6 ─▶ T025 Q7 ─▶ T026 Q8
                    └─▶ T027 commit de resultados ─▶ T028 Q9 (/abrir-pr real) ─▶ T029
```

### Parallel Opportunities

- T009 (US2), T012 y T013 (US3) y T015 (US4) pueden escribirse en paralelo con la cadena
  T004–T008 de US1.
- T016 y T017 en paralelo.
- T020 y T021 en paralelo entre sí, pero las dos antes de T022.

---

## Parallel Example: tras Foundational

```text
Cadena US1:  T004 → T005 → T006 → T007 → T008 → T014
En paralelo: T009 → T010 → T011  |  T012  |  T013  |  T015
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Setup y Foundational (T001–T003).
2. US1 (T004–T008): `/siguiente-ticket` arranca un ticket.
3. **Parar y validar**: Q1–Q4b, después de T020 y T021, en sesión nueva.

### Incremental Delivery

1. US1 → arranque.
2. US3 → comentarios de avance con hooks; desde aquí, los comandos de Spec Kit de la rama
   comentan solos.
3. US2 → `/abrir-pr` con revisión previa.
4. US4 → paso 0 y `DECISIONES.md`.
5. Polish → validación en orden y PR.

---

## Fuera de tasks.md (después del merge, no son tareas)

- **Q10**: el paso 0 del primer `/siguiente-ticket` comenta el cierre de #2 si está en Done,
  o lo reporta sin moverlo.
- **Q11**: ese mismo `/siguiente-ticket` arranca #3 (`003-guardas-claude-code`) y el hook
  `after_specify` publica su comentario `especificado`.

Si alguno falla, se reporta en el issue #2 y se corrige en un ticket nuevo, nunca en la
rama ya fusionada.
