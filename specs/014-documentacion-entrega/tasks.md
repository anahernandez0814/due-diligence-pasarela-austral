---

description: "Lista de tareas del ticket #14, documentación de entrega"
---

# Tasks: Documentación de entrega: README y DECISIONES.md

**Input**: documentos de diseño en `specs/014-documentacion-entrega/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/documentos.md](contracts/documentos.md) y [quickstart.md](quickstart.md).

**Prerequisites**: la spec en `51dc26d` y el plan en `2474d5b`, aprobados por la analista con la corrección de la fila 10 (`/abrir-pr` y `/comentar-avance` son comandos; se añade `guarda_mcp_github`).

**Tests**: obligatorios (constitución X; FR-008, FR-009, FR-012, FR-013 y FR-019). Van en `test_documentacion.py`, en la raíz, y en `.claude/hooks/test_agentes_skills.py`. Ninguno llama al modelo ni a la red.

**Organization**: de corrido hasta el barrido (T019) y **se detiene antes de `/abrir-pr`**, que espera el enlace del video.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. El .zip definitivo y la lista de entrega los recorre la analista después del merge, desde `main`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US5).
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md) o Q# del [quickstart](quickstart.md).

---

## Phase 1: Setup

- [X] T001 Commitear `specs/014-documentacion-entrega/tasks.md` en un commit `docs(tasks): …` antes de cualquier cambio (constitución IX).
- [X] T002 Añadir `"test_documentacion.py"` a `testpaths` de `pyproject.toml` (R2).

---

## Phase 2: Foundational: el detalle sin pérdida (US3; R4, R5)

**Bloquea US2**: los enlaces de `DECISIONES.md` apuntan a los encabezados del detalle.

- [X] T003 [US3] Crear `docs/decisiones-detalle.md` con todas las líneas de `git show f9e82d6:DECISIONES.md`, en el mismo orden, y una introducción añadida que diga que es el detalle de `DECISIONES.md` (FR-013).
- [X] T004 [US3] Añadir en `docs/decisiones-detalle.md` las dos notas, cada una después de la línea que corrige, sin tocarla (R5, R12):
  - tras «**Done**» de la entrada 3: los PR no están en el Project y «Pull request merged» no mueve nada; el paso a Done lo hace «Item closed» al cerrarse el issue con el `Closes #N`. FR-015 del #2 no se corrige (historia del ticket);
  - tras la espera `categoria` de la entrada 11: la espera se descarta con **cualquier** frente caído, porque entonces se exige el informe (regla 5, caso f).
- [X] T005 [US3] Reunir las sugerencias no atendidas de cada PR del comentario `<!-- ciclo-tickets:pr -->` de cada issue cerrado (#1 a #13 y #19) y los datos de T055 del #7 (`specs/007-hooks-sdk-reglas/tasks.md`), sin datos de personas ni valores.
- [X] T006 [US3] Añadir al final de `docs/decisiones-detalle.md` las secciones nuevas (FR-014, R5):
  - «Desviaciones declaradas»: D1–D4 del #10, D1–D2 del #11 y D1–D3 del #12, una línea cada una con la entrada que la contiene y el plan del ticket;
  - «Límites del plugin (PR #29)»: `contexto_revision.py:160` (con constitución y sin `specs/`, «Ticket: no aplica» sin `CONTEXTO INCOMPLETO`) y `revisor-codigo.md:67` (qué Markdown cuenta es ambiguo), con enlace al PR;
  - «Sugerencias no atendidas de los PR»: una línea por PR con su enlace;
  - «Mejoras futuras»: la latencia con Opus 5.5 (T055 del #7: de 23 a 56 s y de 0,07 a 0,16 USD por caso) y lo demás que T005 encuentre como mejora;
  - la recarga en caliente de `settings.json` (entrada 14) se nombra en el índice de límites.

**Checkpoint**: el detalle conserva las 14 entradas y tiene los añadidos.

---

## Phase 3: User Story 2: DECISIONES.md en dos páginas (P1)

**Goal**: la tabla de las once necesidades con «Dónde», la sección del Agent SDK, el flujo de trabajo y los límites conocidos, en 100 líneas o menos.

**Independent Test**: `uv run pytest test_documentacion.py -k decisiones`.

- [X] T007 [US2] Contrastar cada mecanismo de la tabla del plan con su archivo (`CLAUDE.md`, `.gitignore`, `.claude/rules/`, `.claude/settings.json`, `.claude/hooks/`, `.claude/agents/`, `.claude/skills/`, `.claude/commands/`, `.mcp.json`, `.claude-plugin/`, `plugins/`) y anotar el tipo exacto de cada pieza: regla, hook (`PreToolUse` o `PostToolUse`), skill, comando, subagente, MCP o plugin.
- [X] T008 [US2] Reescribir `DECISIONES.md` (FR-008 a FR-012):
  - título e introducción que remite a `docs/decisiones-detalle.md`;
  - tabla `N · Necesidad · Mecanismo · Por qué · Descartado · Dónde`, con las filas 1 a 11; la fila 10 como la fijó la analista (skill `siguiente-ticket`, comandos `/abrir-pr` y `/comentar-avance`, hooks de Spec Kit, MCP de GitHub limitado por `guarda_mcp_github`, workflows nativos del Project con la corrección de los PR); «Dónde» con tickets, archivo principal y enlace al detalle;
  - «Sistema con el Agent SDK», de 6 a 8 líneas: coordinador y subagentes con herramientas restringidas, hooks del SDK para las reglas, servidor MCP, fallas y cobertura parcial, interfaz de chat (#5 a #12);
  - «Flujo de trabajo»: excepciones de arranque del #1, una rama por ticket con merge commit, workflows del Project con la corrección;
  - «Límites conocidos»: lista corta con enlaces al detalle; los añadidos de R5 solo se nombran.
- [X] T009 [US2] Escribir en `test_documentacion.py` los tests de `DECISIONES.md` y del detalle según `contracts/documentos.md`: límite de páginas (imprime la medida si falla), once filas, tickets #1–#13 y #19, sección del Agent SDK de 6 a 8 líneas, enlaces con slugs de GitHub (R3), sin pérdida contra `f9e82d6` (omitido sin git o sin el commit) y añadidos del detalle.

**Checkpoint**: `uv run pytest test_documentacion.py` en verde para US2 y US3.

---

## Phase 4: User Story 4: docs/ como referencia (P1)

**Independent Test**: `uv run pytest .claude/hooks/test_agentes_skills.py`.

- [X] T010 [P] [US4] Añadir `docs/` a la viñeta «Son referencia y no cuentan» de `.claude/agents/revisor-codigo.md`, `.claude/agents/auditor-cumplimiento.md`, `.claude/skills/revisar-codigo/SKILL.md` y `.claude/skills/auditar-cumplimiento/SKILL.md`, con el mismo texto en los cuatro (FR-015).
- [X] T011 [US4] Añadir `"docs/"` a `REFERENCIA` en `.claude/hooks/test_agentes_skills.py` y comprobar que no está entre lo que cuenta (FR-015). La copia del plugin no cambia (R6, FR-016).

---

## Phase 5: User Story 1: README con «Inicio rápido» (P1)

**Independent Test**: `uv run pytest test_documentacion.py -k readme` y Q2 del quickstart.

- [X] T012 [US1] Añadir a `README.md`, como primera sección `##`, el «Inicio rápido» (FR-001, FR-002, FR-006, R7): requisitos previos (`git`, `uv`, clave de Anthropic); `uv python install 3.12`; `uv sync`; copiar `.env.example` a `.env` (PowerShell y bash) y poner la clave con un editor; `uv run pytest src` (unos 25 s, sin clave); `uv run streamlit run src/due_diligence/chat.py` (http://localhost:8501), cada uno con lo que se ve al terminar.
- [X] T013 [US1] Completar el README sin reescribir el resto (FR-003 a FR-007, R7, R8):
  - una sección corta «Credenciales»: `ANTHROPIC_API_KEY` en `.env`; `GITHUB_PAT` en el entorno del sistema porque `.mcp.json` no lee `.env`, con `repo` y `project` (enlaza a la sección del token);
  - «Pruebas»: la suite completa de 4:43 a 6:12 en Windows (D3 del #12), no es el paso principal; los e2e consumen API, con su coste por ejecución completa y por caso; e2e explicado;
  - «Verificar el entorno» remite a «Pruebas»;
  - las referencias «entrada N de DECISIONES.md» pasan a `docs/decisiones-detalle.md`;
  - en el plugin, `extraKnownMarketplaces` además de `marketplace add`, y la frase de visibilidad marcada como **pendiente de la analista** (no se inventa).
- [X] T014 [US1] Escribir en `test_documentacion.py` los tests del README según `contracts/documentos.md`: «Inicio rápido» primera sección con los cinco comandos en orden; los siete mensajes, el Project, la línea del video, `marketplace add`, `extraKnownMarketplaces` y la línea de visibilidad.

---

## Phase 6: User Story 5: docs/entrega.md (P2)

**Independent Test**: `uv run pytest test_documentacion.py -k entrega` y Q3 del quickstart.

- [X] T015 [US5] Crear `docs/entrega.md` (FR-017 a FR-021, R9 a R11):
  - lista de verificación con los siete puntos del issue y la frase de visibilidad;
  - el .zip: clon limpio desde GitHub, `tar.exe -a` (PowerShell) y `zip -r` (bash), listado del contenido (`.git/`, `specs/`, `.specify/memory/`; sin `.venv/`, `.env`, `CLAUDE.local.md`, `.claude/settings.local.json` ni `docs/bitacora-decisiones.md`) y tamaño ≤ 50 MB;
  - la revisión del historial con los bloques marcados `<!-- bloque: revision-prefijos -->` y `<!-- bloque: revision-detector -->`, que solo imprimen commit, archivo y tipo, y qué hacer con un hallazgo sin reescribir el historial;
  - el guion del video de funcionamiento (≤ 5 min, los siete casos) y el de defensa (≤ 15 min: ecosistema, Spec Kit con el #7, Agent SDK), con tiempos por bloque.
- [X] T016 [US5] Escribir en `test_documentacion.py` los tests de `docs/entrega.md`: los puntos de la lista y los dos guiones; y los dos bloques de revisión ejecutados en un repositorio git temporal con una credencial generada al ejecutar, que la encuentran y no imprimen el valor (omitidos sin `bash`).
- [X] T017 [US5] Q3 sobre un clon de esta rama: generar el .zip con los comandos del documento, comprobar el listado y el tamaño, y ejecutar las dos revisiones del historial. Anotar los resultados (sin valores) en este archivo.
  Resultado (2026-10-19, clon limpio de la rama desde la copia local, `ed2e615`):
  - .zip de 12,8 MB y 3990 entradas; `.git/`, `specs/` y `.specify/memory/` presentes; 0
    archivos excluidos (`.venv/`, `.env`, `CLAUDE.local.md`, `settings.local.json`, bitácora,
    `resultados/`).
  - Prefijos: «Sin coincidencias.» en 361 commits (16 s). Detector: «Hallazgos: 0» (82 s).
  - «Historial intacto»: `35b0de1` y `f9e82d6` son antecesores de `main`.
  - **Corregido**: con las herramientas Unix de Git en el `PATH`, `tar.exe` a secas era el GNU
    tar y no generaba el zip; el documento usa `$env:SystemRoot\System32\tar.exe` (R9).

---

## Phase 7: Polish

- [X] T018 Añadir en `docs/decisiones-detalle.md` una entrada corta del #14 (la medida, el traslado y `docs/` como referencia), sin pasar el límite de `DECISIONES.md`.
- [X] T019 Barrido:
  - ruff (`check` y `format --check`);
  - `uv run pytest test_documentacion.py .claude/hooks/test_agentes_skills.py plugins` y `uv run pytest src` cronometrado;
  - Q2: «Inicio rápido» en un clon limpio sin `.env` (pruebas de la aplicación en verde; el chat se detiene con el mensaje de la clave);
  - `uv run pytest` completo (Q4);
  - cada documento coherente con lo construido y las tareas marcadas;
  - commit de los documentos juntos cuando corresponda; sin `--amend`.

  Resultado (2026-10-19):
  - ruff limpio (275 archivos). `test_documentacion.py`: 40 en verde, ninguno omitido; con
    `test_agentes_skills.py` y `plugins`: 351 en verde (44 s). `uv run pytest src`: 3325 en
    verde en 28 s. `uv run pytest` completo: 4977 en verde en 6:23, con el equipo ocupado.
  - `DECISIONES.md`: 99 líneas a 90 columnas (47 de fuente); la sección del Agent SDK, 8.
  - Q2, clon limpio sin `.env` ni clave en el entorno: Python 3.12 ya instalado; `uv sync` 73 s;
    `uv run pytest src` 3325 en verde en 28 s; el chat arranca (`/_stcore/health` responde
    `ok` en 2 s) y la línea de comandos sale con 2 y el mensaje de la clave.
  - **Hallazgo de Q2**: en un clon dentro de `%TEMP%`, el `pytest.exe` recién instalado en
    `.venv` no arranca («Failed to spawn: pytest … Access is denied») y después desaparece, lo
    que apunta a una política de seguridad del equipo; `uv run python -m pytest src` pasa (3325
    en 27,6 s). En `D:` no ocurre. El README lo nombra en el paso 4 con la alternativa.
  - Coherencia: dos «Descartado» de la tabla sin respaldo en los specs (el `pre-commit` de la
    fila 5 y «revisar en la misma sesión» de la fila 8) se cambiaron por los documentados (R11
    del #3 y la entrada 5); la fila 10 aclara que los hooks de Spec Kit son instrucciones.

---

## Dependencies & Execution Order

- Setup → Foundational (detalle) → US2 (necesita los encabezados del detalle) → US4, US1, US5 → Polish.
- US4 es independiente del resto y puede ir en cualquier momento tras el Setup.
- **En paralelo**: T010 con T012 y T015 (archivos distintos).

## Implementation Strategy

Detalle sin pérdida, DECISIONES.md con sus tests, docs/ como referencia, README, entrega.md con la prueba de los bloques, Q3, barrido. Parada antes de `/abrir-pr`.
