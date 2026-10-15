# Implementation Plan: Automatización del ciclo de tickets en GitHub

**Branch**: `002-automatizacion-tickets` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-automatizacion-tickets/spec.md` (issue #2)

## Summary

Automatizar el ciclo de cada ticket con piezas versionadas de Claude Code y Spec Kit, sin
mover tarjetas a mano:

- **Skill `siguiente-ticket`**: empieza con el paso 0, la verificación posterior al merge
  de los tickets cerrados. Después hace todas las comprobaciones sin efectos y solo
  entonces mueve el ticket a "In Progress", comenta el inicio, crea la rama y ejecuta
  `/speckit-specify` con la carpeta exacta `specs/NNN-<nombre-corto>`.
- **Hooks obligatorios de Spec Kit** en `.specify/extensions.yml` (`after_specify`,
  `after_clarify`, `after_plan`, `after_analyze`) que ejecutan
  `/comentar-avance especificado|plan|analyze`, sin editar las skills de Spec Kit. El
  comentario de lo especificado lo publica el hook `after_specify`, no la skill.
- **Comando `/abrir-pr`**:
  - Verifica que spec, plan y tareas están commiteados.
  - Ejecuta la revisión previa como paso aislado (FR-023): un subagente de solo lectura en
    contexto separado; se detiene si hay bloqueantes.
  - Sube la rama, abre el PR con `Closes #N` y el veredicto de la revisión, mueve el
    ticket a "In review" y comenta.
- **Done** por los workflows nativos del Project. La verificación posterior al merge se
  registra en un comentario del issue y no en `tasks.md`.

Cada comentario lleva un marcador HTML invisible para no duplicarse y para contar SC-003.

## Technical Context

**Language/Version**: Markdown (skill y comandos de Claude Code) y YAML
(`.specify/extensions.yml`). Sin código Python nuevo.

**Primary Dependencies**: Claude Code (skills, comandos, `allowed-tools`); Spec Kit
1.2.1.dev0 (hooks de `extensions.yml`, `speckit-specify` con `SPECIFY_FEATURE_DIRECTORY`);
servidor MCP remoto de GitHub con el toolset de projects (ticket #1); git.

**Storage**: N/A. El estado vive en GitHub (issue, ítem del Project, PR) y en git.

**Testing**: escenarios del [quickstart](quickstart.md) (Q1–Q9 antes del PR; Q10–Q11
con el primer uso real) más `ruff check`, `ruff format --check` y `pytest` en verde.

**Target Platform**: sesiones de Claude Code en Windows, macOS y Linux. Los pasos usan git
y el MCP, no comandos propios de un shell.

**Project Type**: configuración versionada de Claude Code y Spec Kit en un repositorio de
aplicación Python.

**Performance Goals**: arrancar un ticket con una sola invocación (SC-001).

**Constraints**:

- No editar las skills de Spec Kit (`.claude/skills/speckit-*`), que se sobrescriben al
  actualizar.
- Ningún commit en `main`.
- `CLAUDE.md` de 40 líneas como máximo.
- Comentarios y mensajes en español.
- Sin credenciales.

**Scale/Scope**: un repositorio, un Project (#1 de `anahernandez0814`) y 14 tickets.

No quedan NEEDS CLARIFICATION: los hallazgos (a)–(i) del analista y las incógnitas
técnicas se resolvieron en [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Verificación en este plan | Estado |
|-----------|--------|---------------------------|--------|
| I. Reglas de negocio | No | El ticket no implementa lógica de due diligence. | N/A |
| II. Garantizado vs. sugerido | Sí | Varias piezas se cumplen por instrucción de la skill y de los comandos: la comprobación de spec previa de `/abrir-pr`, su revisión previa y el orden del arranque. La garantía con hooks de "especificación previa" es del ticket #3. Los comentarios de avance son **sugeridos, no garantizados**: los hooks de `.specify/extensions.yml` son instrucciones que el modelo ejecuta al terminar el comando de Spec Kit, no hooks de Claude Code. Mejoran la constancia, porque la instrucción viaja con el comando, pero no la garantizan. Es aceptable, porque los comentarios no están en la lista de garantías de II. | Cumple con desviación temporal (ver abajo) |
| III. Arquitectura de agentes | No | Fuera de alcance. | N/A |
| IV. Herramientas y servidor MCP | No | Se refiere al servidor MCP propio de la pasarela; aquí solo se usa el MCP de GitHub. | N/A |
| V. Escalamiento | No | Fuera de alcance. | N/A |
| VI. Transparencia en la interfaz | No | Se refiere a la interfaz de chat del sistema. | N/A |
| VII. Solo datos ficticios | Sí | Los comentarios solo contienen números de issue, ramas, rutas y decisiones; nada de personas ni comercios. | Cumple |
| VIII. Sin credenciales | Sí | El MCP usa `${GITHUB_PAT}` (ticket #1). Ni la skill ni los comandos leen `.env` ni escriben tokens en comentarios o archivos. | Cumple |
| IX. Spec first y trazabilidad | Sí | Es el objeto del ticket. Rama por ticket desde `main`, `specs/NNN-*` antes de implementar, PR con `Closes #N`, Status sincronizado sin mover tarjetas a mano, y comentarios de lo especificado, lo decidido y lo pendiente en cada punto del ciclo. Las piezas se versionan en `.claude/` y `.specify/`. | Cumple |
| X. Calidad y pruebas | Parcial | El ticket no añade Python, así que no hay tests pytest nuevos. La validación es el quickstart más `ruff check`, `ruff format --check` y `pytest` en verde. La revisión independiente previa al PR pasa a ser un paso aislado de `/abrir-pr`, de transición hasta el ticket #4. Usa un subagente de tipo `Plan` en contexto separado: sin Edit, Write ni NotebookEdit, el "solo lectura" lo limitan sus herramientas. Conserva Bash, así que la instrucción sigue cubriendo los comandos con efectos. La revisión de cumplimiento de reglas de negocio no aplica. | Cumple con desviación temporal (ver abajo) |
| Restricciones técnicas | Sí | Sin dependencias nuevas; documentación en español. | Cumple |

**Desviación temporal del principio II**: la constitución exige que la exigencia de
especificación previa se garantice con hooks de Claude Code. En este ticket:

- `/abrir-pr` comprueba por instrucción que `spec.md`, `plan.md` y `tasks.md` están
  commiteados en la rama.
- La revisión previa de `/abrir-pr` también es por instrucción.
- El orden comprobaciones → acciones de `siguiente-ticket` también es por instrucción.

Un modelo podría saltarse esas comprobaciones. La garantía con hooks llega en el ticket #3,
que además debe cubrir los huecos de `.env` y denegar las herramientas destructivas del MCP
de GitHub (comentario en el issue #3).

**Desviación temporal del principio X**: siguen vigentes las del ticket #1. El formateo con
ruff es manual y se ejecuta antes de cada commit. La revisión previa al PR es con un
subagente de tipo `Plan`, ahora dentro de `/abrir-pr`, hasta el ticket #4.

**Resultado de la puerta**: cumple, con las desviaciones temporales declaradas.

**Re-evaluación tras la fase 1**:

- Los contratos no introducen credenciales, datos reales ni reglas de negocio.
- Todo lo que depende de instrucciones está declarado arriba: la comprobación de spec
  previa, la revisión previa, el orden del arranque y los comentarios de avance.
- Los hooks de `.specify/extensions.yml` acercan la instrucción de comentar al momento en
  que hace falta, porque viaja con el comando de Spec Kit. Aun así, la ejecuta el modelo:
  mejora la constancia, pero no la garantiza.

La puerta sigue cumpliendo.

## Project Structure

### Documentation (this feature)

```text
specs/002-automatizacion-tickets/
├── spec.md
├── plan.md                    # Este archivo
├── research.md                # Fase 0: R1–R10
├── data-model.md              # Fase 1: entidades y transiciones del Status
├── quickstart.md              # Fase 1: escenarios Q1–Q10
├── contracts/
│   ├── siguiente-ticket.md    # Skill: paso 0, comprobaciones, acciones
│   ├── abrir-pr.md            # Comando /abrir-pr
│   ├── comentar-avance.md     # Comando /comentar-avance y .specify/extensions.yml
│   └── comentarios.md         # Marcadores y plantillas de los comentarios
├── checklists/
│   └── requirements.md
└── tasks.md                   # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
.
├── .claude/
│   ├── skills/
│   │   └── siguiente-ticket/
│   │       └── SKILL.md       # Nuevo
│   └── commands/
│       ├── abrir-pr.md        # Nuevo
│       └── comentar-avance.md # Nuevo (plan B: comentar-especificado, -plan y -analyze)
├── .specify/
│   └── extensions.yml         # Nuevo: hooks after_specify, after_clarify, after_plan, after_analyze
├── CLAUDE.md                  # +1 línea: siguiente-ticket y /abrir-pr (≤ 40 líneas)
├── DECISIONES.md              # Nueva entrada 3; ajuste de la entrada 2
└── README.md                  # Sección breve "Ciclo de un ticket"
```

**Structure Decision**: no hay código de aplicación; todo son piezas de configuración
versionadas donde Claude Code y Spec Kit las buscan. La skill y los comandos van en
`.claude/` (llegan a quien clona); los hooks van en `.specify/extensions.yml`, el punto de
extensión que ya leen las skills de Spec Kit.

### Cambios en la documentación

- **`DECISIONES.md`, nueva entrada 3, "Ciclo de tickets automatizado"**: breve, de unas
  15 líneas, con una línea por decisión y el detalle remitido a `research.md`. El
  enunciado limita `DECISIONES.md` a dos páginas para las 11 necesidades, y el ticket #14
  todavía tiene que completarlo. Decisiones que recoge:
  - Done por los workflows nativos "Item closed" y "Pull request merged" (FR-016).
  - Comentarios de lo especificado, del plan y del análisis con hooks obligatorios de Spec
    Kit (`after_specify`, `after_clarify`, `after_plan`, `after_analyze`) en lugar de
    editar sus skills.
  - **Alcance real de esos hooks**: son instrucciones que el modelo ejecuta al terminar el
    comando de Spec Kit, no hooks de Claude Code. Mejoran la constancia, pero no la
    garantizan. Se acepta porque los comentarios de avance no están entre las garantías
    del principio II.
  - Verificación posterior al merge como paso 0 de `siguiente-ticket` y en un comentario,
    no en `tasks.md`.
  - `SPECIFY_FEATURE_DIRECTORY` explícito porque `--number` no es estricto.
  - **Por qué `siguiente-ticket` no usa `context: fork`**: invoca `/speckit-specify`, que
    puede hacer preguntas de aclaración, y su resultado debe quedar en la conversación
    principal, donde sigue el ciclo. `context: fork` se usará en las skills de revisión
    del ticket #4.
  - Revisión previa como paso aislado de `/abrir-pr`, que el ticket #4 reemplazará.
  - Marcadores de comentario.
  - Alternativas descartadas (R1, R4, R5).
- **`DECISIONES.md`, entrada 2 (transición)**:
  - Desde #3, el arranque, los comentarios y el PR pasan a `siguiente-ticket`, a los hooks
    y a `/abrir-pr`.
  - La revisión previa sigue siendo de transición (subagente de tipo `Plan`), pero ahora la lanza
    `/abrir-pr`, hasta #4.
  - La desviación temporal de II y X sigue hasta #3.
- **`CLAUDE.md`**: la línea "Mueve el ticket a In Progress al empezar y a In review al
  abrir el PR" se sustituye por "Cada ticket se arranca con `/siguiente-ticket` y se
  cierra con `/abrir-pr`; no se mueven tarjetas a mano". Se queda en 37 líneas.
- **`README.md`**: sección breve "Ciclo de un ticket", con la secuencia y los tres
  comandos. Incluye que, tras el merge del último ticket, `/siguiente-ticket` se ejecuta
  una vez más para registrar su cierre. La ampliación completa es del ticket #14.

### Tareas fuera de los archivos (MCP), antes del PR

Son **requisito previo de Q1** y de cualquier ejecución de `/siguiente-ticket`. El paso 0
corre en cada invocación, incluidas las pruebas negativas Q1 a Q3 (Q4 se rechaza antes por entrada inválida). Sin el marcador, la
primera prueba publicaría un comentario de cierre duplicado en #1.

- Editar el comentario de cierre del issue #1 con `update_issue_comment` para añadir
  `<!-- ciclo-tickets:cierre -->` (R5).
- Editar el comentario de inicio del issue #2 con `update_issue_comment` para añadir
  `<!-- ciclo-tickets:inicio -->`. Los comentarios manuales de lo especificado, del plan y
  del análisis de #2 ya llevan su marcador.

Orden en `tasks.md`: implementación de la skill y los comandos → estas dos ediciones →
Q1–Q9.

### Lo que no entra en `tasks.md`

La verificación del cierre de #2 y el primer arranque real (Q10 y Q11) ocurren después del
merge, con `/siguiente-ticket`. Quedan registrados en comentarios de los issues #2 y #3, no
como tareas de este ticket (FR-018).

## Complexity Tracking

Sin violaciones permanentes de la constitución. Las desviaciones de II y X son temporales,
están declaradas en la verificación de la constitución y se cierran en los tickets #3 y #4.
