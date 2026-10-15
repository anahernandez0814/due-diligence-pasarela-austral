---

description: "Lista de tareas del ticket #1, ecosistema base de Claude Code"
---

# Tasks: Ecosistema base de Claude Code

**Input**: Documentos de diseño en `specs/001-ecosistema-base/` ([plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md))

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md y contracts/

**Tests**: la spec exige un test de humo (FR-007) y la verificación del descubrimiento en
varias carpetas (FR-006). Son las únicas tareas de test; no se pide TDD.

**Organization**: tareas agrupadas por historia de usuario (US1 a US4 de la spec), cada una
verificable por separado.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia de usuario a la que pertenece (US1, US2, US3, US4)
- Rutas relativas a la raíz del repositorio

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: preparar la rama y los finales de línea antes de crear archivos nuevos.

- [X] T001 Confirmar que la rama activa es `001-ecosistema-base`, que contiene los commits de spec, plan y tasks, y que el issue #1 está en "In Progress" en el GitHub Project (`gh project item-list 1 --owner anahernandez0814`)
- [X] T002 Crear `.gitattributes` en la raíz con la línea exacta `* text=auto eol=lf` (research R7)
- [X] T003 Normalizar los archivos ya versionados con `git add --renormalize .` y hacer commit de `.gitattributes` y los archivos normalizados (mensaje `chore: finales de línea LF con .gitattributes`); comprobar después que `git ls-files --eol | grep -v "i/lf" | grep -v "i/none" | grep -v "i/-text"` no devuelve nada

**Checkpoint**: el índice está en LF; los archivos nuevos entran ya normalizados.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: comprobar las exclusiones de git de las que dependen todas las historias.

- [X] T004 Verificar con `git check-ignore -v CLAUDE.local.md .claude/settings.local.json .env` que los tres archivos están ignorados por `.gitignore` (FR-012). Si falta alguno, añadir la regla en `.gitignore` sin quitar las existentes

**Checkpoint**: los archivos personales y de secretos no pueden entrar al repositorio.

---

## Phase 3: User Story 1 - Convenciones del equipo al clonar (Priority: P1) 🎯 MVP

**Goal**: una sesión nueva de Claude Code carga las convenciones del equipo y la constitución
sin configuración manual.

**Independent Test**: `grep -n "@.specify/memory/constitution.md" CLAUDE.md` devuelve una línea,
`wc -l CLAUDE.md` da 40 líneas como máximo y ningún principio de la constitución aparece
copiado.

### Implementation for User Story 1

- [X] T005 [US1] Crear `CLAUDE.md` en la raíz, en español y de 40 líneas como máximo, con estas secciones (data-model, "Convenciones del equipo"):
  - **Idioma**: español en mensajes y documentación.
  - **Flujo**: "Una rama `NNN-nombre-corto` por ticket desde `main`; PR hacia `main` con `Closes #N`", y spec, plan y tareas en `specs/` antes de escribir código.
  - **Comandos**: `uv sync`, `uv run ruff check .`, `uv run ruff format .`, `uv run pytest`.
  - **Mapa del repositorio**: `src/`, `specs/`, `docs/`, `.specify/`, `.claude/`.
  - **Personal**: las preferencias van en `CLAUDE.local.md` y `.claude/settings.local.json`, que no se versionan.
  - **Constitución**: la línea `@.specify/memory/constitution.md`, sin copiar ningún principio.
- [X] T006 [US1] Validar `CLAUDE.md`: la importación aparece exactamente una vez, el archivo tiene 40 líneas como máximo y no contiene el texto de ningún principio de `.specify/memory/constitution.md` (SC-005)

**Checkpoint**: US1 verificable por separado; el MVP del ticket queda entregado.

---

## Phase 4: User Story 2 - Backlog del GitHub Project desde Claude Code (Priority: P2)

**Goal**: Claude Code se conecta al servidor MCP oficial de GitHub con los toolsets repos,
issues, pull_requests y projects, sin credenciales en el repositorio.

**Independent Test**: en una sesión nueva, `/mcp` muestra `github` conectado sin pedir
aprobación, y la consulta de opciones del campo Status devuelve Todo, In Progress, In review y
Done (quickstart, paso 3).

### Implementation for User Story 2

- [X] T007 [P] [US2] Crear `.mcp.json` en la raíz con la configuración principal de [contracts/mcp-json.md](contracts/mcp-json.md):
  - Servidor `github`, `"type": "http"`, `"url": "https://api.githubcopilot.com/mcp/"`.
  - Cabeceras `"Authorization": "Bearer ${GITHUB_PAT}"` y `"X-MCP-Toolsets": "repos,issues,pull_requests,projects"`.
  - Invariante: ningún valor de token, solo `${GITHUB_PAT}`.
- [X] T008 [P] [US2] Añadir `"enabledMcpjsonServers": ["github"]` en `.claude/settings.json`, conservando sin cambios el bloque `env` (`PYTHONIOENCODING`, `PYTHONUTF8`) y el bloque `permissions.deny` existentes (research R3)
- [X] T009 [US2] Buscar credenciales en los archivos versionados y en los nuevos aún no versionados (los ignorados quedan fuera) con `git grep --untracked -nE "gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9-]{20,}"`; el resultado debe estar vacío (SC-003, FR-004)
- [ ] T010 [US2] Verificación manual de la analista en una sesión nueva de Claude Code (Claude no puede abrirla por sí mismo):
  - `/mcp` muestra `github` conectado y al menos una herramienta de cada toolset: repos, issues, pull_requests y projects.
  - Leer el GitHub Project "Due Diligence - Pasarela Austral" devuelve sus tickets y las opciones del campo Status.
  - Si falla con 401/403, sustituir `.mcp.json` por la alternativa stdio de [contracts/mcp-json.md](contracts/mcp-json.md), que requiere el binario `github-mcp-server` en el PATH, y repetir la verificación.

**Checkpoint**: US2 verificable por separado; a partir de aquí el seguimiento del ticket puede
hacerse por el MCP en vez de `gh`.

---

## Phase 5: User Story 3 - Esqueleto Python verificable (Priority: P3)

**Goal**: `uv sync`, `uv run ruff check .` y `uv run pytest` terminan con código 0, y pytest
descubre tests junto al código en dos carpetas.

**Independent Test**: en un clon limpio, los comandos del quickstart, pasos 1 y 2, terminan con
código 0 y `--collect-only` lista los dos `test_humo.py`.

### Implementation for User Story 3

- [ ] T011 [P] [US3] Crear `.python-version` en la raíz con el contenido `3.12`
- [ ] T012 [P] [US3] Crear `pyproject.toml` en la raíz exactamente según [contracts/pyproject.md](contracts/pyproject.md):
  - `[project]`: `name = "due-diligence-pasarela-austral"`, `version = "0.1.0"`, `requires-python = ">=3.12,<3.13"`, `dependencies = []`.
  - `[dependency-groups] dev = ["pytest", "ruff"]`.
  - `[build-system]` con `requires = ["uv_build>=0.12,<0.13"]` y `build-backend = "uv_build"`, y `[tool.uv.build-backend] module-name = ["due_diligence", "servidor_mcp"]`.
  - `[tool.ruff]` con `target-version = "py312"`, `line-length = 100` y `extend-exclude = [".specify"]` (no formatear ni revisar los scripts de Spec Kit); `[tool.ruff.lint] select = ["E", "F", "I", "UP", "B"]`.
  - `[tool.pytest.ini_options]` con `testpaths = ["src"]`, `python_files = ["test_*.py"]` y `addopts = ["--import-mode=importlib"]`.
- [ ] T013 [P] [US3] Crear `src/due_diligence/__init__.py` con un docstring en español: "Sistema multi-agente de due diligence de comercios de Pasarela Austral." Sin otra lógica
- [ ] T014 [P] [US3] Crear `src/servidor_mcp/__init__.py` con un docstring en español: "Servidor MCP propio que simula las fuentes de Pasarela Austral con datos ficticios locales." Sin otra lógica
- [ ] T015 [P] [US3] Crear `src/due_diligence/test_humo.py` con un test que importe `due_diligence` y compruebe que se carga desde `src/due_diligence/` y que `sys.version_info[:2] == (3, 12)`; sin datos de personas ni comercios (principio VII)
- [ ] T016 [P] [US3] Crear `src/servidor_mcp/test_humo.py` (mismo nombre a propósito, research R5) con un test equivalente para `servidor_mcp`
- [ ] T017 [US3] Ejecutar `uv sync`, que genera `uv.lock` y `.venv/`; comprobar que `.venv/` sigue ignorado y que `uv.lock` se versiona (research R4). Plan B si `uv_build` no acepta varios módulos: añadir `pythonpath = ["src"]` en pytest y documentarlo en [research.md](research.md), R4
- [ ] T018 [US3] Ejecutar `uv run ruff format .` y `uv run ruff check .`, y corregir lo que reporten hasta que ambos terminen con código 0
- [ ] T019 [US3] Ejecutar `uv run pytest --collect-only -q` y `uv run pytest`: deben aparecer `src/due_diligence/test_humo.py` y `src/servidor_mcp/test_humo.py` sin error de módulo duplicado, y la suite debe terminar con código 0 (FR-006, FR-007)

**Checkpoint**: US3 verificable por separado; base lista para los tickets de código.

---

## Phase 6: User Story 4 - Documentación de arranque (Priority: P4)

**Goal**: README, enunciado y registro de decisiones permiten incorporarse y auditar el
proyecto.

**Independent Test**: siguiendo solo el README, una persona deja el entorno verificado en menos
de 5 minutos (SC-001), y `DECISIONES.md` contiene las dos decisiones exigidas (FR-011).

### Implementation for User Story 4

- [ ] T020 [P] [US4] Incorporar `docs/enunciado.md`, que ya existe sin versionar, sin modificar su contenido: es copia literal del enunciado entregado por el equipo (FR-009, Assumptions). Solo se añade a git
- [ ] T021 [P] [US4] Crear `README.md` en la raíz, en español, con:
  - Propósito del proyecto.
  - Requisitos: uv y gh.
  - Cómo definir `GITHUB_PAT` como variable de entorno del usuario: token de `gh auth token` o PAT clásico, en ambos casos con los scopes `repo` y `project`; `gh auth status` muestra los scopes (research R2).
  - Verificación del entorno: `uv sync`, `uv run ruff check .`, `uv run pytest` y `/mcp` en Claude Code.
  - Alternativa stdio si el servidor remoto da 401/403.
  - Enlace al GitHub Project https://github.com/users/anahernandez0814/projects/1 y un apartado "Video de funcionamiento" con el enlace pendiente.
- [ ] T022 [P] [US4] Crear `DECISIONES.md` en la raíz, breve y en español. Cada entrada tiene **Necesidad o tema**, **Decisión**, **Motivo** y **Alternativas descartadas** (data-model, "Registro de decisiones"). Entradas:
  - (1) Cargar la constitución en cada sesión con `@.specify/memory/constitution.md` desde `CLAUDE.md` (research R8).
  - (2) Ciclo manual de tickets durante la transición hasta fusionar #2 y #4: rama propia desde `main`, spec, plan y tareas en `specs/`, PR con `Closes #N`, revisión con un subagente genérico de solo lectura en contexto separado. Incluye la desviación temporal de los principios II y X: el formateo tras cada edición y las garantías con hooks llegan en el ticket #3; mientras tanto el formateo es manual (T018).
  - Nota: el documento se completa en el ticket #14.

**Checkpoint**: las cuatro historias están completas y son verificables por separado.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: validación final, revisión independiente y cierre trazable del ticket.

- [ ] T023 Ejecutar los pasos 1, 2, 4, 5 y 6 de [quickstart.md](quickstart.md) y anotar el resultado de cada uno (el paso 3 es T010). Además, para SC-001:
  - Hacer un clon limpio de la rama en una carpeta temporal fuera del repositorio.
  - Seguir solo el README y cronometrar desde el clonado hasta tener `uv sync`, `uv run ruff check .` y `uv run pytest` en verde.
  - El tiempo debe ser menor de 5 minutos; anotarlo y borrar después la carpeta temporal.
- [ ] T024 Repetir la búsqueda de credenciales sobre todo el contenido preparado con `git grep --cached -nE "gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9-]{20,}"` (resultado vacío) y confirmar que `.env` no está en `git ls-files` (principio VIII)
- [ ] T025 Hacer commit de la implementación por partes lógicas, con mensajes en español y sin incluir `.env`, `.venv/` ni archivos personales
- [ ] T026 Revisión independiente antes del PR: lanzar un subagente genérico de solo lectura, en contexto separado, que revise el diff `main...001-ecosistema-base` frente a la spec, el plan y los 5 criterios de aceptación del issue #1. Aplicar las correcciones que proponga. La revisión de cumplimiento de reglas de negocio (principio X) no aplica porque el ticket no implementa los principios I a V; se deja anotado en el PR
- [ ] T027 Subir la rama con `git push -u origin 001-ecosistema-base` y abrir el PR hacia `main` con la descripción en español, la lista de criterios de aceptación verificados y `Closes #1`
- [ ] T028 Mover el issue #1 a "In review" en el GitHub Project y comentar en el issue lo implementado, lo decidido y lo pendiente. El comentario debe aclarar que `GITHUB_PAT` puede ser el token de `gh auth token` o un PAT clásico, ambos con los scopes `repo` y `project`, y corregir así el comentario del plan, que decía solo "PAT clásico". Usar el MCP de GitHub si T010 pasó; si no, `gh`
- [ ] T029 Después del merge del PR: VERIFICAR, sin mover a mano, que el workflow "Item closed" del GitHub Project pasó el issue #1 a "Done" al cerrarse con `Closes #1`, y comentar el cierre en el issue. Si no ocurrió, reportarlo en vez de moverlo manualmente

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias. T003 depende de T002.
- **Foundational (Phase 2)**: depende de Setup y bloquea todas las historias.
- **User Stories (Phases 3 a 6)**: dependen de Foundational; son independientes entre sí.
- **Polish (Phase 7)**: depende de las cuatro historias. Orden T023 → T024 → T025 → T026 →
  T027 → T028 → T029 (T029 después del merge).

### User Story Dependencies

- **US1 (P1)**: sin dependencias de otras historias.
- **US2 (P2)**: sin dependencias. T009 depende de T007 y T008; T010 depende de T007 y T008.
- **US3 (P3)**: sin dependencias. T017 depende de T011 a T016; T018 depende de T017; T019
  depende de T018.
- **US4 (P4)**: sin dependencias para crear los archivos. Los comandos del README deben
  coincidir con los de US1 y US3, y se revisan en T023.

### Parallel Opportunities

- US1, US2, US3 y US4 pueden avanzar en paralelo tras la fase 2.
- Dentro de US2: T007 y T008.
- Dentro de US3: T011 a T016 (seis archivos distintos).
- Dentro de US4: T020, T021 y T022.

---

## Parallel Example: User Story 3

```bash
# Crear en paralelo todos los archivos del esqueleto:
Task: "Crear .python-version con 3.12"
Task: "Crear pyproject.toml según contracts/pyproject.md"
Task: "Crear src/due_diligence/__init__.py"
Task: "Crear src/servidor_mcp/__init__.py"
Task: "Crear src/due_diligence/test_humo.py"
Task: "Crear src/servidor_mcp/test_humo.py"

# Después, en secuencia: T017 (uv sync) → T018 (ruff) → T019 (pytest)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Fases 1 y 2: LF y exclusiones verificadas.
2. Fase 3 (US1): `CLAUDE.md` con la constitución importada.
3. **Parar y validar** con el Independent Test de US1.

### Incremental Delivery

1. Setup + Foundational.
2. US1: convenciones.
3. US2: MCP de GitHub. Con T010 en verde, el seguimiento del ticket pasa a hacerse por MCP.
4. US3: esqueleto Python.
5. US4: documentación.
6. Polish: quickstart, revisión independiente, PR con `Closes #1` y ticket en "In review".

---

## Notes

- [P] = archivos distintos y sin dependencias pendientes.
- Ninguna tarea escribe un token, ni lee o modifica `.env` (principio VIII).
- Ningún archivo contiene datos reales de personas, comercios, NIT o tarjetas (principio VII).
- Hacer commit tras cada tarea o grupo lógico; no commitear nunca en `main`.
