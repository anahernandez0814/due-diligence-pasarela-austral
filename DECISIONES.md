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

- **Necesidad o tema**: trazabilidad de cada ticket (constitución IX) antes de la automatización del ciclo (#2) y de la revisión previa al PR (#4).
- **Decisión**: #1 y #2 siguieron el ciclo a mano (rama desde `main`, Spec Kit, ticket y comentarios con el MCP de GitHub, PR con `Closes #N`, revisión previa con un subagente). Desde #3 lo automatiza la entrada 3.
- **Desviación temporal de II y X**: formateo manual antes de cada commit y protección parcial de `.env` (solo Read, Edit, `cat .env*` y `type .env*`) hasta #3. La cierra la entrada 4, salvo la revisión previa, que sigue siendo de transición hasta #4.
- **Motivo**: trazabilidad desde el primer ticket, aunque las piezas que la automatizan sean tickets del backlog.
- **Alternativa descartada**: esperar a la automatización, lo que dejaría los primeros tickets sin historial en GitHub.

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

## 4. Guardas de Claude Code

- **Necesidad o tema**: reglas que se cumplen con código, no con instrucciones (necesidades 3 a 7; constitución II, VII, VIII y IX). Detalle en `specs/003-guardas-claude-code/research.md`.
- **Hooks**: Python 3.12 con la biblioteca estándar, en forma exec con `uv run --no-project --python 3.12 --quiet`, igual en Windows, macOS y Linux (R1).
- **Fallo cerrado en dos capas**: salida 2 ante un error propio y `onFailure: "block"` si el hook no arranca o se agota; el formato nunca bloquea (R2).
- **Matchers**: listas exactas de nombres, no expresiones regulares, con PowerShell como respaldo (R3).
- **MCP de GitHub**: 7 herramientas denegadas por nombre; `projects_write` se permite para el ciclo de tickets, limitada a `update_project_item` por `guarda_mcp_github` (R4).
- **PowerShell**: apagada por las denegaciones de Bash con Git Bash, sin reglas `PowerShell(...)`, que la encenderían; si se activa, la cubren las guardas (R5).
- **Denegaciones**: primera barrera, y el hook la garantía; `!**/.env.example` va detrás de `**/.env.*`, y `grep` no se deniega para poder buscar el texto ".env" (R6).
- **Plugin**: `plugins/<nombre>/` y `.claude-plugin/`, protegidos como código desde ya (R7).
- **`settings.local.json`**: Claude Code no puede escribirlo, borrarlo, moverlo ni restaurarlo para desactivar las guardas; se bloquea en cualquier rama porque no se versiona (R14, FR-025).
- **Texto ejecutable**: un extractor común analiza `bash -c`, `eval`, sustituciones, heredocs, tuberías, código en línea y los lanzadores `xargs`, `sudo`, `doas`, `env -S`, `script -c` y `watch`, hasta 3 niveles (R9, R10, FR-026).
- **Riesgos residuales**: (1) lecturas de secretos ocultas: rodeos deliberados (variables, base64, scripts) y lectores de archivos completos (`tar c`, `zip -r`, `git show <rev>:<ruta>`) (R9); (2) escrituras no reconocibles: `git apply`/`patch`/`git reset`/`git stash`, `find …`, `xargs rm`, `cd $X`, rutas construidas al ejecutar y programas que escriben en código versionado que el PR ve; lista completa en R10; (3) `.py` escritos por terminal se formatean en `ruff format --check` (R12); (4) cambiar a una rama sin `.claude/hooks/` exige reiniciar la sesión (R14).
