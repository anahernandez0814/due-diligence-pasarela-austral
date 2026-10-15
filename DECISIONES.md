# Decisiones del ecosistema

Registro breve de las decisiones de diseño del ecosistema de Claude Code y su motivo. Se
completa en el ticket #14 con el mecanismo elegido para cada necesidad del enunciado.

## 1. La constitución se carga en cada sesión con `@import`

- **Necesidad o tema**: convenciones del equipo al clonar, sin configurar nada (necesidad 1).
- **Decisión**: `CLAUDE.md` raíz breve (40 líneas como máximo) con las convenciones del
  equipo, que importa la constitución con `@.specify/memory/constitution.md` en lugar de
  copiarla.
- **Motivo**:
  - Las reglas de negocio y los principios aplican a casi todo el trabajo del proyecto,
    así que cada sesión debe partir de ellos.
  - La importación evita una segunda copia que se desactualice: un cambio en la
    constitución llega a todas las sesiones sin editar `CLAUDE.md`.
  - El coste es de unas 190 líneas de contexto por sesión, aceptable para un MVP.
- **Alternativas descartadas**:
  - Copiar la constitución en `CLAUDE.md`: duplicación que diverge.
  - Cargarla bajo demanda con una skill o una regla con `paths`: podría omitirse justo en
    la tarea donde aplica una regla de negocio.

## 2. Ciclo manual de tickets durante la transición

- **Necesidad o tema**: trazabilidad de cada ticket (constitución IX) antes de que exista la
  automatización del ciclo (#2) y la revisión previa al PR (#4).
- **Decisión**: #1 y #2 siguen el ciclo a mano. Desde #3, el arranque, los comentarios y el
  PR pasan a `/siguiente-ticket`, los hooks de Spec Kit y `/abrir-pr` (entrada 3). La
  revisión previa sigue siendo de transición hasta #4, pero ahora la lanza `/abrir-pr`. El
  ciclo manual era:
  - Rama propia `NNN-nombre-corto` creada desde `main` actualizado; nunca se commitea en
    `main`.
  - `/speckit-specify` con el cuerpo del issue y `--number N`, luego `/speckit-plan` y
    `/speckit-tasks`, para que spec, plan y tareas queden en `specs/`.
  - Claude Code mueve el ticket y comenta en el issue con el MCP de GitHub, o con `gh`
    mientras el MCP no esté configurado.
  - El PR incluye `Closes #N`.
  - La revisión previa al PR se hace con un subagente genérico de solo lectura en un
    contexto separado.
- **Desviación temporal de los principios II y X**: el formateo tras cada edición y las
  garantías con hooks (protección de secretos, bloqueo de datos con forma real, exigencia de
  especificación previa) llegan en el ticket #3. Mientras tanto:
  - El formateo con ruff es manual y se ejecuta antes de cada commit.
  - La protección de `.env` es parcial. La denegación de `.claude/settings.json` bloquea
    Read y Edit sobre `.env` y los comandos `cat .env*` y `type .env*`. Otros comandos de
    Bash (`head`, `grep`, `Get-Content`, `cp`) y variantes como `.env.local` quedan sin
    cubrir hasta los hooks del ticket #3.
- **Motivo**: el proyecto necesita trazabilidad desde el primer ticket, y las piezas que la
  automatizan son, a su vez, tickets del backlog.
- **Alternativas descartadas**: esperar a tener la automatización para empezar, lo que
  dejaría los primeros tickets sin historial en GitHub.

## 3. Ciclo de tickets automatizado

- **Necesidad o tema**: estado del Project sincronizado y avance visible en el issue sin mover tarjetas (necesidad 10, constitución IX). Detalle en `specs/002-automatizacion-tickets/research.md`.
- **Arranque**: skill `siguiente-ticket`. Comprueba todo antes de mover el ticket y luego mueve → comenta → rama → `/speckit-specify` (R3).
- **Número exacto**: `--number` no es estricto, así que la skill pasa `SPECIFY_FEATURE_DIRECTORY=specs/NNN-<nombre>` y verifica `.specify/feature.json` (R1).
- **Sin `context: fork`**: `/speckit-specify` puede preguntar y su resultado debe quedar en la conversación principal; `context: fork` se usará en las revisiones de #4 (R9).
- **Comentarios de avance**: hooks obligatorios de Spec Kit en `.specify/extensions.yml` (`after_specify`, `after_clarify`, `after_plan`, `after_analyze`) que ejecutan `/comentar-avance`. No se editan las skills de Spec Kit, que se sobrescriben al actualizar (R4).
- **Alcance de esos hooks**: son instrucciones que el modelo ejecuta al terminar el comando, no hooks de Claude Code. Mejoran la constancia, pero no la garantizan. Se acepta porque los comentarios no están entre las garantías del principio II (R4).
- **Marcadores**: cada comentario lleva `<!-- ciclo-tickets:<tipo> -->` para no duplicarse. Las actualizaciones amplían el comentario y conservan lo anterior (R6).
- **PR**: `/abrir-pr` comprueba spec, plan y tareas, ejecuta una revisión previa aislada (subagente `Plan`, de transición hasta #4), abre el PR con `Closes #N` y mueve el ticket a In review (R9).
- **Done**: lo hacen los workflows nativos del Project, "Item closed" y "Pull request merged"; nadie mueve tarjetas (FR-016).
- **Verificación posterior al merge**: es el paso 0 de cada `/siguiente-ticket`, que comenta el cierre o lo reporta sin mover la tarjeta. Nunca es una tarea de `tasks.md`, para no dejar cambios en una rama fusionada (R5).
- **Alternativas descartadas**: confiar en `--number`, editar las skills de Spec Kit, una GitHub Action para el cierre y un issue de prueba para validar (R1, R4, R5, R10).
