# Implementation Plan: Revisión independiente y auditoría de cumplimiento

**Branch**: `004-revision-independiente-auditoria` | **Date**: 2026-10-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-revision-independiente-auditoria/spec.md` (issue #4)

## Summary

Que ningún pull request se abra sin una revisión independiente y una auditoría de las reglas
de negocio, y que esa exigencia la haga cumplir un hook, no una instrucción:

- **Dos subagentes de solo lectura** en `.claude/agents/`: `revisor-codigo` y
  `auditor-cumplimiento`, con `tools: Read, Grep, Glob` (R5).
- **Dos skills con `context: fork`** en `.claude/skills/`: `revisar-codigo` y
  `auditar-cumplimiento`, cada una ligada a su subagente con `agent:` (R1). Preparan el
  contexto con un script inyectado antes de crear el subagente (R2): lista de archivos con
  estadísticas siempre y el diff completo solo si toda la salida cabe en `UMBRAL_SALIDA`
  (14 500 bytes: la mitad del mayor tamaño que llegó completo, Q4(a)) (R4, R6). La salida empieza con la marca
  `CONTEXTO DE REVISIÓN`. Los documentos del ticket no cuentan para la cobertura. El
  subagente no necesita Bash.
- **Consolidación en `/abrir-pr`**: ejecuta las dos skills, valida la línea `RESUMEN` de cada
  reporte y registra el veredicto del commit actual, aprobado o con bloqueantes, en
  `.claude/veredictos/<sha>.json`, ignorado por git (R7, R8). Reemplaza la revisión de
  transición del ticket #2 (R11).
- **Puerta mecánica**: la guarda `guarda_pr` (`PreToolUse`) bloquea `create_pull_request` del
  MCP de GitHub, `gh pr create` y `gh api` con POST a `pulls` si no hay un veredicto aprobado
  del commit actual, y si ese commit no es el último publicado de la rama (R9, R10). Falla
  cerrada, como las guardas de #3.
- **`.claude/veredictos/` protegido** (FR-020): `guarda_spec_previa` lo bloquea en cualquier
  rama, con el patrón de `settings.local.json` de #3, más una denegación en
  `permissions.deny`. La única vía de registro es la CLI de `veredicto.py` (R8).
- **Tests con pytest** junto a cada módulo y declaración del límite del mecanismo en
  `DECISIONES.md` (R12, FR-018).

## Technical Context

**Language/Version**: Python 3.12, solo la biblioteca estándar. Configuración en JSON
(`.claude/settings.json`) y Markdown con frontmatter YAML (agentes, skills, comandos).

**Primary Dependencies**:

- Claude Code 2.1.300: skills con `context: fork` y `agent:`, subagentes personalizados,
  inyección de comandos en skills, hooks `PreToolUse` con `onFailure` (v2.1.295 o posterior).
- `uv` 0.12 como lanzador de los scripts, igual que las guardas de #3.
- `git` y, para la comprobación manual, `gh`.
- El servidor MCP de GitHub (ticket #1), solo para `create_pull_request`.
- Los módulos de #3: `comun.py` (extractor de texto ejecutable, `ejecutar`, `bloquear`).

**Storage**: archivos JSON en `.claude/veredictos/`, uno por commit, ignorados por git (R8).

**Testing**: pytest con `testpaths = ["src", ".claude/hooks"]` y `pythonpath =
[".claude/hooks"]` (sin cambios en `pyproject.toml`). Tests unitarios y de extremo a extremo
por stdin, con repositorios git temporales. Escenarios Q1–Q17 del [quickstart](quickstart.md)
en una sesión nueva.

**Target Platform**: sesiones de Claude Code en Windows (Git Bash; validación manual, solo
en Windows, el sistema del equipo) y, por diseño, macOS y Linux: forma exec sin shell, `uv`,
`pathlib` y solo la biblioteca estándar (FR-016). Ninguna tarea valida otro sistema; CI
sobre otros sistemas queda como mejora opcional de #14, igual que en #3.

**Project Type**: configuración versionada de Claude Code más scripts, en un repositorio de
aplicación Python.

**Performance Goals**: la comprobación de la puerta en menos de 1 s (SC-004), **medida en
caliente desde la segunda llamada de la sesión**, como en #3: la primera llamada tarda
≈ 1,1 s porque `uv` prepara el entorno. ≈ 0,5 s de arranque de `uv run --no-project` más
milisegundos de `git rev-parse`. `git ls-remote` se descarta porque solo él tarda ≈ 1,2 s
(R9). Q15 lo mide y pasa o falla con ese umbral.

**Constraints**:

- La guarda falla cerrada; los revisores no escriben ni ejecutan (FR-003).
- Nada del argumento de la skill llega al shell (R2).
- Ningún valor sensible en mensajes, tests ni documentos; los tests construyen sus datos.
- No se editan las skills de Spec Kit ni `CLAUDE.md` (37 líneas).
- Mensajes y reportes en español.

**Scale/Scope**: 3 scripts nuevos (`veredicto.py`, `preparar_revision.py`, `guarda_pr.py`) con
sus tests, 1 test de agentes y skills, 2 subagentes, 2 skills, 1 comando modificado,
`guarda_spec_previa.py` ampliada con su test, 1 entrada de hook y 1 denegación en
`settings.json` y 1 línea en `.gitignore`.

No quedan NEEDS CLARIFICATION. Las cuatro preguntas del analista sobre la documentación de
Claude Code están resueltas, con fuente, en [research.md](research.md); lo que la doc no
especifica se comprueba en el quickstart:

| Punto | Dónde |
|-------|-------|
| Ligar skill `context: fork` con su subagente | R1 |
| Inyección del diff, `allowed-tools`, subagente sin Bash (FR-003 y FR-005) | R2 |
| ¿El subagente recibe CLAUDE.md y la constitución? | R3 |
| Límite de tamaño de la inyección | R4 |
| Lo que la doc no especifica y se comprueba | R13 (Q1–Q6) |

**Decisión para la analista** (R9): la guarda compara con `origin/<rama>` local y no con
`git ls-remote` (≈ 1,2 s, incompatible con SC-004). El costo es no ver los commits que otra
persona empuje después del último `fetch`; `git push` lo cubre en la práctica. Recomendado.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Verificación en este plan | Estado |
|-----------|--------|---------------------------|--------|
| I. Reglas de negocio | Indirecto | El auditor verifica las cinco reglas contra spec, código y tests (R7); este ticket no implementa reglas. | Cumple |
| II. Garantizado vs. sugerido | Sí | La exigencia de revisión previa pasa de instrucción de `/abrir-pr` a un hook `PreToolUse` que bloquea con salida 2 y falla cerrado (R10). Las skills y los subagentes solo producen el reporte; lo obligatorio lo hace cumplir la guarda. El directorio de veredictos lo protege el mismo mecanismo de #3 (FR-020), así que el veredicto solo lo escribe la CLI de `veredicto.py`. Se declara el límite: no comprueba que los `RESUMEN` registrados vengan de una revisión real (R8). | Cumple, con el límite declarado |
| III. Arquitectura de agentes | Sí | Cada subagente tiene solo las herramientas de su rol (`Read`, `Grep`, `Glob`) y recibe su contexto de forma explícita, sin heredar la conversación (R1, R3, R5). No lanzan otros subagentes. | Cumple |
| IV. Herramientas y servidor MCP | Indirecto | No toca el servidor del proyecto. Las decisiones del sistema (`registrar_informe`, `escalar_a_cumplimiento`) no se tocan. | N/A |
| V. Escalamiento | No | Fuera de alcance. | N/A |
| VI. Transparencia en la interfaz | No | Se refiere a la interfaz de chat. Los reportes se muestran en la conversación de `/abrir-pr`. | N/A |
| VII. Solo datos ficticios | Sí | Los tests construyen sus repositorios y valores en tiempo de ejecución; `guarda_datos` revisa lo que se publica en el PR. | Cumple |
| VIII. Sin credenciales | Sí | El subagente tiene `Read`: depende de `guarda_secretos` si los hooks alcanzan a sus herramientas (R5, Q5), y de las denegaciones de `Read`. Se declara. | Cumple, con verificación Q5 |
| IX. Spec first y trazabilidad | Sí | Spec, plan y tareas antes del código; el veredicto de cada commit queda registrado, también con bloqueantes. | Cumple |
| X. Calidad y pruebas | Sí | **Cierra la desviación de #2**: la revisión independiente y la de cumplimiento pasan a ser dos subagentes y la puerta es un hook. Tests con pytest junto al código; formato con el hook de #3. | Cumple |
| Restricciones técnicas | Sí | Python 3.12 con uv, pytest y ruff; sin dependencias nuevas; documentación en español. | Cumple |

**Desviación que cierra este ticket**: la revisión previa de transición de `/abrir-pr`
(subagente `Plan`, ticket #2) queda reemplazada y no queda ninguna revisión paralela (FR-019,
SC-006).

**Sin desviaciones nuevas.** Riesgos residuales (a la entrada 5 de `DECISIONES.md`):

1. Invocar `veredicto.py registrar` con `RESUMEN` inventados: la puerta no lo distingue de una
   revisión real (R8; límite del issue). Escribir el archivo del veredicto a mano ya no es
   residual: lo bloquea `guarda_spec_previa` (FR-020).
2. Crear el PR fuera de Claude Code (web, otro cliente, `curl`) no pasa por la guarda; alias
   de `gh` y construcciones que el extractor de #3 no reconoce (R10).
3. Commits empujados por otra persona después del último `fetch` (R9).
4. `Read` del subagente depende de `guarda_secretos` si los hooks alcanzan al subagente (R5).
5. La calidad de la revisión depende del modelo; la puerta garantiza que ocurrió, no que
   encontró todo.

## Project Structure

### Documentation (this feature)

```text
specs/004-revision-independiente-auditoria/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── revisiones.md    # subagentes, skills y formato del reporte
│   ├── veredicto-y-guarda.md  # veredicto, registro y guarda de PR
│   └── abrir-pr.md      # cambios en /abrir-pr
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
.claude/
├── agents/
│   ├── revisor-codigo.md            # nuevo: tools Read, Grep, Glob
│   └── auditor-cumplimiento.md      # nuevo: tools Read, Grep, Glob
├── skills/
│   ├── revisar-codigo/SKILL.md      # nuevo: context fork, agent revisor-codigo
│   └── auditar-cumplimiento/SKILL.md  # nuevo: context fork, agent auditor-cumplimiento
├── commands/
│   └── abrir-pr.md                  # cambia: sección 2 reemplazada (R11)
├── hooks/
│   ├── veredicto.py                 # nuevo: registro, lectura y consolidación
│   ├── preparar_revision.py         # nuevo: contexto de las skills (R6)
│   ├── guarda_pr.py                 # nuevo: puerta de creación de PR (R10)
│   ├── guarda_spec_previa.py        # cambia: bloquea .claude/veredictos/ en cualquier rama (R8)
│   ├── test_guarda_spec_previa.py   # cambia: casos del directorio de veredictos
│   ├── test_veredicto.py            # nuevo
│   ├── test_preparar_revision.py    # nuevo
│   ├── test_guarda_pr.py            # nuevo
│   ├── test_agentes_skills.py       # nuevo
│   └── test_configuracion.py        # cambia: registra guarda_pr
├── veredictos/                      # generado, ignorado por git
└── settings.json                    # cambia: una entrada PreToolUse y Edit(/.claude/veredictos/**) en deny
.gitignore                           # cambia: .claude/veredictos/
DECISIONES.md                        # cambia: entrada 5 y nota en la 3
README.md                            # cambia: una frase en "Ciclo de un ticket"
```

**Structure Decision**: los scripts viven en `.claude/hooks/` con sus tests, como las
guardas de #3, porque comparten `comun.py` y la ruta ya está en `testpaths` y `pythonpath`.
`preparar_revision.py` y `veredicto.py` no son hooks, pero son código de la misma familia y
protegido por `guarda_spec_previa` (`.claude/hooks/**`); no se crea un directorio nuevo.
Los agentes y las skills son Markdown de configuración de `.claude/` y están exentos de la
guarda de spec previa.

## Complexity Tracking

No hay violaciones de la constitución que justificar.
