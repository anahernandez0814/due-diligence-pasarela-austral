# Feature Specification: Ecosistema base de Claude Code

**Feature Branch**: `001-ecosistema-base`

**Created**: 2026-10-15

**Status**: Draft

**Input**: Issue #1 de GitHub, "Ecosistema base de Claude Code"
(https://github.com/anahernandez0814/due-diligence-pasarela-austral/issues/1)

**Objetivo**: que cualquier persona que clone el repositorio reciba las convenciones del
equipo sin configurar nada, y que Claude Code pueda leer y actualizar el backlog del
GitHub Project a través del servidor MCP oficial de GitHub.

> Nota: este ticket configura el entorno de trabajo del equipo. Los nombres de
> herramientas (Claude Code, MCP de GitHub, uv, ruff, pytest) forman parte del requisito
> del enunciado y de la constitución, no son decisiones de implementación de esta spec.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Convenciones del equipo al clonar (Priority: P1)

Una persona del equipo clona el repositorio y abre una sesión de Claude Code. Sin configurar
nada, la sesión ya conoce las convenciones del equipo y los principios de la constitución,
porque el archivo de instrucciones del proyecto los importa en vez de copiarlos. Sus
preferencias personales quedan en archivos locales que nunca se suben.

**Why this priority**: es la condición de partida de todos los tickets siguientes; sin
convenciones compartidas cada sesión trabaja con reglas distintas.

**Independent Test**: clonar el repositorio en una carpeta limpia, abrir una sesión nueva y
comprobar que la constitución aparece entre las instrucciones cargadas y que el archivo de
instrucciones no repite su texto.

**Acceptance Scenarios**:

1. **Given** un clon limpio del repositorio, **When** se abre una sesión nueva de Claude
   Code, **Then** las convenciones del equipo y la constitución están cargadas sin pasos
   manuales.
2. **Given** el archivo de instrucciones del proyecto, **When** se revisa su contenido,
   **Then** importa la constitución con `@.specify/memory/constitution.md` y no repite
   ninguno de sus principios.
3. **Given** que una persona crea `CLAUDE.local.md` o `.claude/settings.local.json`,
   **When** revisa el estado de git, **Then** esos archivos no aparecen como cambios a
   subir.

---

### User Story 2 - Backlog del GitHub Project desde Claude Code (Priority: P2)

La persona del equipo pide a Claude Code que lea o actualice el backlog. Claude Code se
conecta al servidor MCP oficial de GitHub, lee el Project y las opciones de su campo
Status, mueve tickets y comenta issues, sin que exista ningún token en el repositorio: la
credencial se toma de la variable de entorno del sistema `GITHUB_PAT`.

**Why this priority**: habilita la trazabilidad del principio IX (estado del ticket y
comentarios en el issue) sin recurrir a comandos manuales; depende de que el entorno base
(P1) exista.

**Independent Test**: con `GITHUB_PAT` definida, abrir una sesión nueva y pedir las opciones
del campo Status del Project; deben listarse Todo, In Progress, In review y Done.

**Acceptance Scenarios**:

1. **Given** `GITHUB_PAT` definida en el sistema, **When** se abre una sesión nueva, **Then**
   el servidor MCP de GitHub aparece conectado con capacidades de repositorios, issues,
   pull requests y projects.
2. **Given** el servidor conectado, **When** se pide leer el GitHub Project, **Then** se
   obtienen sus tickets y las opciones del campo Status.
3. **Given** cualquier archivo del repositorio, **When** se busca un token o credencial,
   **Then** no se encuentra ninguno; la configuración solo referencia el nombre de la
   variable.

---

### User Story 3 - Esqueleto Python verificable (Priority: P3)

La persona del equipo prepara el entorno con un solo comando, ejecuta el linter y la suite de
pruebas, y todo termina sin errores. La suite descubre los tests que viven junto al código
que prueban, aunque estén repartidos en varias carpetas, y existe un test de humo que
demuestra que la configuración funciona.

**Why this priority**: es la base del principio X; los tickets de código posteriores lo
necesitan, pero no bloquea las convenciones ni el acceso al backlog.

**Independent Test**: en un clon limpio ejecutar `uv sync`, `uv run ruff check .` y
`uv run pytest`; los tres terminan con código 0 y pytest reporta el test de humo.

**Acceptance Scenarios**:

1. **Given** un clon limpio con uv instalado, **When** se ejecuta `uv sync`, **Then** el
   entorno queda preparado con Python 3.12 sin errores.
2. **Given** el entorno preparado, **When** se ejecuta `uv run ruff check .`, **Then**
   termina sin errores.
3. **Given** el entorno preparado, **When** se ejecuta `uv run pytest`, **Then** se ejecuta
   el test de humo y termina con código 0.
4. **Given** tests ubicados junto al código en dos carpetas distintas, **When** se ejecuta
   la suite, **Then** se descubren ambos sin tener que moverlos a una carpeta `tests/`.

---

### User Story 4 - Documentación de arranque (Priority: P4)

Quien llega al proyecto encuentra el propósito del proyecto y la preparación del entorno en
el README, el enunciado de la prueba como fuente de requisitos en `docs/enunciado.md` y
las decisiones tomadas, con su motivo, en `DECISIONES.md`. Los finales de línea son
uniformes (LF) en todos los sistemas operativos.

**Why this priority**: facilita la incorporación y la auditoría, pero los tickets
siguientes pueden avanzar sin ella.

**Independent Test**: una persona que no conoce el proyecto sigue el README desde cero y
deja el entorno listo sin preguntar a nadie; `DECISIONES.md` explica las dos decisiones
exigidas.

**Acceptance Scenarios**:

1. **Given** el README, **When** una persona lo lee, **Then** encuentra el propósito del
   proyecto y los pasos para preparar el entorno, incluida la definición de `GITHUB_PAT`.
2. **Given** `DECISIONES.md`, **When** se revisa, **Then** justifica cargar la constitución
   en cada sesión y documenta el ciclo manual de tickets durante la transición.
3. **Given** un archivo de texto editado en Windows, **When** se sube al repositorio,
   **Then** se guarda con finales de línea LF.

---

### Edge Cases

- `GITHUB_PAT` no está definida: el servidor MCP de GitHub no se conecta, ninguna
  credencial aparece en el repositorio y el README indica cómo definirla.
- `GITHUB_PAT` carece de permisos sobre projects: la lectura del Project falla con un
  error visible; el README indica los permisos necesarios.
- Archivos ya subidos con finales CRLF: tras añadir la regla de LF quedan normalizados en
  el repositorio.
- La constitución cambia: el archivo de instrucciones refleja el cambio sin editarse,
  porque la importa.
- No existe carpeta `tests/`: la suite igual descubre los tests junto al código.
- Se crean archivos personales (`CLAUDE.local.md`, `.claude/settings.local.json`) o un
  `.env`: siguen excluidos de git.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El repositorio DEBE incluir un `CLAUDE.md` raíz breve con las convenciones
  del equipo que importe la constitución con `@.specify/memory/constitution.md`.
- **FR-002**: `CLAUDE.md` NO DEBE repetir el contenido de la constitución.
- **FR-003**: El repositorio DEBE incluir `.mcp.json` con el servidor MCP oficial de GitHub
  y los toolsets de repositorios, issues, pull requests y projects.
- **FR-004**: La credencial del servidor MCP DEBE tomarse de la variable de entorno del
  sistema `GITHUB_PAT`; ningún archivo del repositorio DEBE contener un token o credencial.
- **FR-005**: El repositorio DEBE incluir un proyecto Python 3.12 gestionado con uv
  (`pyproject.toml`) con ruff y pytest configurados.
- **FR-006**: pytest DEBE descubrir tests ubicados junto al código que prueban en varias
  carpetas, sin depender de una carpeta `tests/` única.
- **FR-007**: El repositorio DEBE incluir un test de humo que pase con la configuración
  base.
- **FR-008**: El repositorio DEBE incluir `.gitattributes` que fije finales de línea LF.
- **FR-009**: El repositorio DEBE incluir `docs/enunciado.md` con el enunciado de la prueba
  como fuente de requisitos.
- **FR-010**: El repositorio DEBE incluir un `README.md` con el propósito del proyecto y la
  preparación del entorno.
- **FR-011**: El repositorio DEBE incluir `DECISIONES.md` que justifique cargar la
  constitución en cada sesión y documente el ciclo manual de tickets de la transición.
- **FR-012**: `CLAUDE.local.md` y `.claude/settings.local.json` DEBEN seguir excluidos de
  git, igual que `.env`.
- **FR-013**: Toda la documentación nueva DEBE estar en español (constitución, restricciones
  técnicas).

### Key Entities

- **Convenciones del equipo**: reglas compartidas que se versionan en el repositorio y se
  cargan en cada sesión; incluyen la constitución por importación.
- **Preferencias personales**: configuración local de cada persona; nunca se versiona.
- **Configuración del servidor MCP de GitHub**: declara el servidor, sus toolsets y el
  nombre de la variable de entorno de la credencial, nunca su valor.
- **Registro de decisiones**: cada decisión con su contexto, la opción elegida y el motivo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona nueva pasa de clonar el repositorio a tener el entorno verificado
  (dependencias, linter y pruebas en verde) en menos de 5 minutos siguiendo solo el README.
- **SC-002**: En una sesión nueva, el 100 % de las consultas de lectura del GitHub Project
  (tickets y opciones de Status) responden sin pasos manuales adicionales.
- **SC-003**: Una búsqueda de credenciales sobre todo el repositorio encuentra 0 tokens o
  secretos.
- **SC-004**: Los 5 criterios de aceptación del issue #1 se cumplen y quedan verificados en
  el pull request.
- **SC-005**: 0 principios de la constitución aparecen duplicados en `CLAUDE.md`.

## Assumptions

- `GITHUB_PAT` la define cada persona en su sistema con permisos de lectura y escritura
  sobre repositorios, issues, pull requests y projects; no se gestiona desde el repositorio.
- El texto de docs/enunciado.md es copia literal del enunciado original de la prueba,
  entregado por el equipo.
- uv está instalado en la máquina de cada persona; el README indica cómo instalarlo.
- El GitHub Project "Due Diligence - Pasarela Austral" ya existe con el campo Status
  (Todo, In Progress, In review, Done).
- Fuera de alcance: automatización del ciclo de tickets (#2), guardas (#3), revisión antes
  del PR (#4) y el CLAUDE.md del subdirectorio del servidor MCP (#5).
- Transición: hasta fusionar #2 y #4, cada ticket sigue el ciclo a mano (rama propia
  `NNN-nombre-corto` desde `main`, spec/plan/tareas en `specs/`, PR con `Closes #N`,
  revisión con un subagente de solo lectura en contexto separado).
- Trazabilidad: constitución, principios VIII y IX; necesidades del ecosistema 1, 2 y base
  de la 10.
