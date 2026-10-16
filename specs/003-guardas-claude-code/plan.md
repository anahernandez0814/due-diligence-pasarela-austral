# Implementation Plan: Guardas de Claude Code: hooks, permisos y reglas por ruta

**Branch**: `003-guardas-claude-code` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-guardas-claude-code/spec.md` (issue #3)

## Summary

Convertir en garantías las reglas de trabajo que hoy se cumplen por instrucción, con
hooks y permisos de Claude Code versionados en `.claude/`:

- **Cuatro guardas `PreToolUse`** en Python, solo con la biblioteca estándar. Se lanzan
  con `uv run` en forma exec, para funcionar igual en Windows, macOS y Linux. Bloquean
  con código de salida 2 y fallan cerradas (`onFailure: "block"` más un `try/except`
  propio):
  - `guarda_secretos`: archivos de secretos, por cualquier herramienta, y lecturas
    recursivas sin exclusión.
  - `guarda_datos`: tarjetas, NIT, cédulas y credenciales en lo que se escribe, en los
    comandos de terminal y en lo que se publica por el MCP de GitHub.
  - `guarda_spec_previa`: código protegido sin spec, plan y tareas del ticket en curso,
    incluidos `.claude/settings.json`, `.claude/settings.local.json` y `.mcp.json`.
  - `guarda_mcp_github`: limita `projects_write` a `update_project_item` (FR-024).
- **PowerShell desactivada**, por mínimo privilegio: las denegaciones de Bash la mantienen
  apagada. Las guardas la cubren como respaldo si alguien la activa (R5).
- **Un hook `PostToolUse`**, `formatear_python`, que formatea con ruff y nunca bloquea.
- **`permissions.deny` ampliado** como primera barrera, con 58 entradas:
  - secretos para las herramientas de archivo, con las mismas familias que la guarda
    (`.env`, `.env.*`, `*.key` y `secrets/`) y la excepción `!**/.env.example` detrás
    (R6);
  - `Edit(/.claude/settings.local.json)`, anclada a la raíz, porque ese archivo podría
    desactivar todas las guardas (R14);
  - lectores y copiadores de Bash sobre secretos, sin `grep`, para no bloquear búsquedas
    del texto ".env" (R6);
  - siete herramientas del MCP de GitHub, dos de ellas destructivas.
- **Dos reglas por ruta** en `.claude/rules/`.
- **Tests junto a los hooks**, incluida la revisión de todos los archivos versionados con
  el mismo detector.

## Technical Context

**Language/Version**: Python 3.12, solo la biblioteca estándar (`json`, `re`, `shlex`,
`subprocess`, `pathlib`, `fnmatch`, `glob`). Configuración en JSON
(`.claude/settings.json`) y Markdown con frontmatter YAML (`.claude/rules/`).

**Primary Dependencies**:

- Claude Code 2.1.300: hooks `PreToolUse` y `PostToolUse` en forma exec, y `onFailure`,
  que requiere la v2.1.295 o posterior.
- `uv` 0.12, como lanzador de los hooks.
- ruff, en el grupo `dev`, para el formato.
- El servidor MCP remoto de GitHub (ticket #1).

**Storage**: N/A. Las guardas no guardan estado; deducen el ticket de la rama en cada
llamada.

**Testing**:

- pytest con `testpaths = ["src", ".claude/hooks"]` y `pythonpath = [".claude/hooks"]`.
- Tests unitarios del detector y de cada guarda, pruebas de extremo a extremo de cada
  script con JSON en stdin (incluida la rama de PowerShell, que no se prueba en la
  sesión), `test_configuracion.py` y `test_revision_repositorio.py`.
- Escenarios Q1–Q18 del [quickstart](quickstart.md) en una sesión nueva, con ramas
  temporales creadas desde la del ticket (nunca en `main`).

**Target Platform**: sesiones de Claude Code en Windows (Git Bash; la herramienta
PowerShell queda apagada), macOS y Linux.

- **Validación por plataforma (FR-022)**: la validación manual, la suite y el
  quickstart, se hace en Windows, el sistema del equipo.
- **macOS y Linux** los respalda el diseño:
  - forma exec sin shell, que no depende de bash ni de PowerShell;
  - `uv` como lanzador, igual en los tres sistemas;
  - rutas con `pathlib`, normalizadas a `/`;
  - solo la biblioteca estándar.
- Una ejecución en CI sobre otros sistemas queda como mejora opcional del ticket #14.

**Project Type**: configuración versionada de Claude Code más scripts de hook, en un
repositorio de aplicación Python.

**Performance Goals**: cada guarda en menos de 1 s, medida en caliente desde la segunda
llamada de la sesión (SC-004). Lo medido:

- ≈ 0,5 s de arranque con `uv run --no-project`;
- la primera llamada, ≈ 1,1 s, porque `uv` prepara el entorno;
- el recorrido de la raíz para las búsquedas recursivas, ≈ 3 ms.

Las guardas que coinciden con una herramienta corren en paralelo.

**Constraints**:

- Las guardas fallan cerradas; el formato nunca bloquea.
- Ningún valor sensible en mensajes, tests ni documentación; los tests los generan en
  tiempo de ejecución.
- No se editan las skills de Spec Kit.
- Mensajes en español.
- `CLAUDE.md` no cambia (38 líneas).

**Scale/Scope**: 5 scripts de hook, 2 módulos compartidos, unos 9 archivos de test, 2
reglas y 58 entradas de denegación.

No quedan NEEDS CLARIFICATION. Los puntos (a)–(f) del analista y FR-003 se resolvieron en
[research.md](research.md):

| Punto | Dónde |
|-------|-------|
| (a) lenguaje e invocación | R1, R2 |
| (b) matchers | R3 |
| (c) herramientas destructivas y `projects_write` | R4 |
| (d) directorio del plugin | R7 |
| (e) tests | R8 |
| (f) lectura recursiva y texto ejecutable (C1, I1) | R9 |
| FR-003 PowerShell | R5, R6 |
| `.claude/settings.local.json` y cambio de rama | R14 |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Verificación en este plan | Estado |
|-----------|--------|---------------------------|--------|
| I. Reglas de negocio | No | Sus hooks son del Agent SDK, en el ticket #7. | N/A |
| II. Garantizado vs. sugerido | Sí | Es el objeto del ticket. Spec previa, secretos y datos con forma real pasan a hooks `PreToolUse` que bloquean con salida 2, independientemente de lo que decida el modelo, y fallan cerrados. `permissions.deny` es una barrera adicional, que además impide a Claude Code desactivar las guardas desde `.claude/settings.local.json`. Las reglas de `.claude/rules/` solo guían, y así se declaran. | Cumple, con los riesgos residuales declarados (ver abajo) |
| III. Arquitectura de agentes | No | Fuera de alcance. | N/A |
| IV. Herramientas y servidor MCP | Indirecto | La regla `herramientas-mcp.md` recoge las convenciones de IV para cuando se escriba el servidor (#5). | Cumple |
| V. Escalamiento | No | Fuera de alcance. | N/A |
| VI. Transparencia en la interfaz | No | Se refiere a la interfaz de chat. | N/A |
| VII. Solo datos ficticios | Sí | La guarda de datos bloquea lo que entra por Claude Code; la revisión del repositorio cubre todo lo versionado. Los tests construyen los valores en tiempo de ejecución, sin literales. | Cumple |
| VIII. Sin credenciales | Sí | Claude Code no puede leer ni modificar `.env` ni sus variantes por ninguna herramienta (hook más denegaciones), tampoco nombrándolos en el código en línea de un intérprete o shell, en `eval`, en un heredoc que alimenta a un intérprete, ni con una búsqueda recursiva cuya raíz los contiene (R9). `.env.example` sigue accesible. Las credenciales tampoco pueden escribirse ni publicarse en GitHub. Solo escapan los rodeos deliberados (riesgo residual 1). | Cumple |
| IX. Spec first y trazabilidad | Sí | La guarda de spec previa hace cumplir "ningún código sin spec, plan y tareas" a nivel de herramienta. El ticket sigue el ciclo de #2: hooks de Spec Kit para los comentarios y `/abrir-pr`. | Cumple |
| X. Calidad y pruebas | Sí | Tests con pytest junto a los hooks. Formato con ruff tras cada edición, con el hook. La revisión previa al PR sigue siendo la de transición de `/abrir-pr` hasta el ticket #4. No aplica la revisión de reglas de negocio. | Cumple, con la desviación de #4 vigente |
| Restricciones técnicas | Sí | Python 3.12 con uv, pytest y ruff; sin dependencias nuevas; documentación en español. | Cumple |

**Desviaciones que cierra este ticket** (declaradas en el plan de #2 y en la entrada 2 de
`DECISIONES.md`):

- **II, spec previa**: deja de depender de que `/abrir-pr` lo compruebe por instrucción.
  La guarda impide escribir código protegido sin los tres documentos. La comprobación de
  `/abrir-pr` se mantiene como segunda capa.
- **II, secretos**: los huecos de #1 (`head`, `grep`, `Get-Content`, `cp` y `.env.local`)
  los cubren la guarda y las nuevas denegaciones.
- **II, datos con forma real**: pasan de no tener garantía a la guarda más la revisión
  del repositorio.
- **X, formateo**: deja de ser manual antes de cada commit; lo hace el hook tras cada
  Write o Edit de un `.py`.

**Desviación que sigue abierta**: la revisión independiente previa al PR es la de
transición hasta #4.

**Riesgos residuales** (se declaran en la nueva entrada de `DECISIONES.md`):

1. Lecturas de secretos que los ocultan a propósito: rutas construidas al ejecutar, nombres
   codificados (por ejemplo, en base64) y scripts escritos en un archivo y ejecutados
   después (R9). El código en línea de intérpretes y shells, `eval`, los heredocs que
   alimentan a un intérprete y las búsquedas recursivas cuya raíz contiene secretos ya
   **no** son residuales: los cubre la guarda.
2. Escrituras en código protegido que no son reconocibles: `git apply`, `patch`,
   intérpretes, rutas en variables (R10).
3. Un `.py` escrito por comando de terminal no se formatea al momento; lo detecta
   `ruff format --check` (R12).
4. Cambiar a una rama sin `.claude/hooks/` bloquea todas las acciones vigiladas, por el
   fallo cerrado, o deja la sesión sin guardas si se recarga la configuración de esa
   rama. El README pide reiniciar la sesión (R14).

El riesgo de los métodos de borrado de `projects_write`, que la primera versión del plan
aceptaba, queda cerrado con `guarda_mcp_github` (FR-024, R4).

Ninguno contradice los principios II y VIII. Las garantías cubren todas las formas en que
Claude Code nombra un secreto o escribe código: herramientas de archivo, rutas en
comandos, texto ejecutable, búsquedas recursivas y el MCP. Lo que queda son formas de
eludirlas a propósito. Una regla de Bash "isn't a security boundary", según la propia
documentación de Claude Code.

**Resultado de la puerta**: cumple.

**Re-evaluación tras la fase 1**:

- Los contratos no introducen valores sensibles: el detector se define con prosa y
  expresiones de clase de caracteres que no coinciden consigo mismas.
- Los tests generan sus casos.
- Las herramientas de FR-017 quedan fuera de la denegación y un test lo comprueba.
- Las dos capas del fallo cerrado cubren las salidas que Claude Code trata como no
  bloqueantes: un código de salida distinto de 2, el timeout y que el hook no arranque.
- No se añade ninguna regla que encienda herramientas: PowerShell queda apagada (R5).

La puerta sigue cumpliendo.

## Project Structure

### Documentation (this feature)

```text
specs/003-guardas-claude-code/
├── spec.md
├── plan.md                    # Este archivo
├── research.md                # Fase 0: R1–R14
├── data-model.md              # Fase 1: guarda, archivo de secretos, patrón, código protegido, ticket en curso
├── quickstart.md              # Fase 1: Q1–Q18
├── contracts/
│   ├── settings-json.md       # hooks y permissions.deny exactos
│   ├── guardas.md             # interfaz común y comportamiento de cada hook
│   └── detector-datos.md      # definiciones normativas del detector
├── checklists/
│   └── requirements.md
└── tasks.md                   # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
.
├── .claude/
│   ├── settings.json                  # + hooks; permissions.deny ampliado (58 entradas)
│   ├── hooks/                         # Nuevo
│   │   ├── comun.py                   # stdin, raíz, rutas, shlex, fallo cerrado, bloquear()
│   │   ├── detector_datos.py          # tarjeta, NIT, cédula, credenciales
│   │   ├── guarda_secretos.py         # PreToolUse
│   │   ├── guarda_datos.py            # PreToolUse
│   │   ├── guarda_spec_previa.py      # PreToolUse
│   │   ├── guarda_mcp_github.py       # PreToolUse: projects_write solo update_project_item
│   │   ├── formatear_python.py        # PostToolUse
│   │   ├── test_comun.py
│   │   ├── test_detector_datos.py
│   │   ├── test_guarda_secretos.py
│   │   ├── test_guarda_datos.py
│   │   ├── test_guarda_spec_previa.py
│   │   ├── test_guarda_mcp_github.py
│   │   ├── test_formatear_python.py
│   │   ├── test_configuracion.py      # settings.json, FR-017, frontmatter de las reglas
│   │   └── test_revision_repositorio.py  # FR-007: todos los archivos versionados
│   └── rules/                         # Nuevo
│       ├── tests.md                   # paths: **/test_*.py
│       └── herramientas-mcp.md        # paths: src/servidor_mcp/**/*.py
├── pyproject.toml                     # testpaths + .claude/hooks; pythonpath
├── DECISIONES.md                      # Nueva entrada 4; ajuste de la entrada 2
└── README.md                          # Sección breve "Guardas del entorno"
```

**Structure Decision**:

- Los hooks van en `.claude/hooks/`, que llega a quien clona y ya es código protegido
  según FR-011.
- Los tests van junto a cada script (constitución X). Cuando el ticket #13 mueva la
  guarda de datos al plugin (`plugins/<nombre>/`), se llevará el detector y sus tests.
- `plugins/**` y `.claude-plugin/**` quedan protegidos desde ahora (R7).

### Cambios en la documentación

- **`DECISIONES.md`, entrada 4, "Guardas de Claude Code"**: una línea por decisión, con el
  detalle en `research.md`:
  - hooks en Python con `uv run` en forma exec (R1);
  - fallo cerrado con dos capas (R2);
  - matchers como listas exactas (R3);
  - herramientas MCP denegadas, y `projects_write` limitada a `update_project_item`
    por una guarda en lugar de denegarla (R4);
  - PowerShell apagada, con las guardas como respaldo (R5);
  - denegaciones como primera barrera y el hook como garantía, y por qué `grep` no está
    en la lista (R6);
  - ruta del plugin (R7);
  - `.claude/settings.local.json` protegido (R14);
  - riesgos residuales 1–4.
- **`DECISIONES.md`, entrada 2**: la desviación temporal de II y X queda cerrada por la
  entrada 4, salvo la revisión previa, que sigue hasta #4.
- **`README.md`**: sección breve "Guardas del entorno". La ampliación es de #14. Contiene:
  - qué bloquea cada guarda;
  - que requieren `uv` en el `PATH`, y que "se cargan al iniciar la sesión y suelen
    activarse también al guardar `settings.json`; ante la duda, reinicie la sesión";
  - "Ejecute `uv sync` antes de abrir Claude Code";
  - "Con las guardas activas, no cambie a una rama sin `.claude/hooks/`; si ocurre,
    reinicie la sesión" (R14).
- **`CLAUDE.md`**: sin cambios. Las guardas actúan solas y las reglas se cargan por ruta.

### Orden de implementación (guía para `/speckit-tasks`)

1. Módulos compartidos y detector, con sus tests (sin registrar todavía ningún hook).
2. Las cuatro guardas y el formato, con sus tests de extremo a extremo (incluida la rama
   de PowerShell).
3. `pyproject.toml` (`testpaths` y `pythonpath`) y la revisión del repositorio, en verde
   sobre el estado actual.
4. `.claude/settings.json`: hooks y denegaciones, más `test_configuracion.py`. Desde aquí
   las guardas protegen la propia sesión cuando se reinicia.
5. Reglas por ruta.
6. Documentación.
7. Commit, sesión nueva y quickstart Q1–Q18, con las ramas temporales creadas desde la
   del ticket.

Mientras no exista `tasks.md`, la guarda de spec previa bloquearía los pasos 1 y 2. No es
un problema, porque los hooks se registran en el paso 4, cuando `tasks.md` ya existe.

## Complexity Tracking

Sin violaciones de la constitución. La única desviación abierta, la revisión previa al PR
de transición, es la heredada de #2 y se cierra en #4.
