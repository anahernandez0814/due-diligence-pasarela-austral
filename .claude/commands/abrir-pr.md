---
description: "Verifica spec, plan y tareas del ticket, ejecuta la revisión independiente y la auditoría de cumplimiento, registra el veredicto del commit revisado, sube la rama, abre el PR hacia main con Closes #N, mueve el ticket a In review y comenta en el issue."
argument-hint: ""
allowed-tools:
  - Bash(git branch:*)
  - Bash(git status:*)
  - Bash(git cat-file:*)
  - Bash(git log:*)
  - Bash(git fetch:*)
  - Bash(git rev-parse:*)
  - Bash(git push:*)
  - Bash(uv run --no-project --python 3.12 --quiet ${CLAUDE_PROJECT_DIR}/.claude/hooks/veredicto.py registrar:*)
  - Read
  - Glob
  - Grep
  - Skill(revisar-codigo)
  - Skill(auditar-cumplimiento)
  - mcp__github__projects_list
  - mcp__github__projects_write
  - mcp__github__issue_read
  - mcp__github__add_issue_comment
  - mcp__github__list_pull_requests
  - mcp__github__create_pull_request
---

# Abrir el PR del ticket

Abre el pull request de la rama del ticket hacia `main`. No recibe argumentos: el ticket
se deduce de la rama actual. Todos los mensajes, la descripción del PR y el comentario van
en español.

Datos fijos: repositorio `anahernandez0814/due-diligence-pasarela-austral`; GitHub Project
número `1` del usuario `anahernandez0814`, con el campo `Status`.

Contratos: `specs/002-automatizacion-tickets/contracts/abrir-pr.md` y, para la revisión y
el veredicto, `specs/004-revision-independiente-auditoria/contracts/abrir-pr.md`.

## 1. Comprobaciones

Si alguna falla, el comando se detiene e informa del motivo. No sube la rama, no abre el
PR y no cambia el estado del ticket.

1. `git branch --show-current`: la rama no es `main` y cumple `^(\d{3})-[a-z0-9-]+$`.
   N es el número de NNN sin ceros a la izquierda.
2. `git status --porcelain` no devuelve nada.
3. Carpeta del ticket. Glob no devuelve carpetas, así que usa Glob con `specs/NNN-*/*` y
   toma las carpetas distintas de los resultados. Debe haber **exactamente una**. Para
   `spec.md`, `plan.md` y `tasks.md` de esa carpeta, `git cat-file -e HEAD:<ruta>` termina
   sin error. Si falta alguno o no está commiteado, nombra cuál.
4. `mcp__github__issue_read` (`method: get`, `issue_number: N`): el issue existe y está
   abierto.
5. `mcp__github__list_pull_requests` con `head: anahernandez0814:<rama>` y `state: open` no
   devuelve ningún PR. Si existe uno, lo enlaza y termina sin hacer nada más.
6. `mcp__github__projects_list` (`method: list_project_fields`): el campo `Status` tiene la
   opción exacta `In review`.
7. `mcp__github__projects_list` (`method: list_project_items`, `field_names: ["Status"]`,
   `query: "is:issue"`), recorriendo todas las páginas: el ítem cuyo `content.number` es N
   existe en el Project. Guarda su `id` (`item_id`) para la acción 3.3. Si no aparece, se
   detiene.

## 2. Revisión independiente y veredicto

Sustituye a la revisión de transición del ticket #2. Las revisiones las hacen dos
subagentes de solo lectura, en contexto separado de esta sesión, y el veredicto queda
atado al commit que se revisó. Un hook (`guarda_pr`) bloquea la creación del PR si no hay
un veredicto aprobado de ese commit, publicado en la rama.

1. **Actualiza las referencias.** `git fetch origin main`: si falla, se detiene, porque la
   base del diff sería la del `main` local. Después `git fetch origin <rama>`: **no es
   fatal si la rama aún no existe en el remoto**.
2. **Guarda el commit que se revisa.** `git rev-parse HEAD`: guarda el sha completo como
   `SHA_REVISADO`. Es el commit al que se ata el veredicto, no el que exista al terminar.
3. **Lanza las dos revisiones.** Con la herramienta Skill, `revisar-codigo` y
   `auditar-cumplimiento`, cada una con la carpeta del ticket de la comprobación 1.3 como
   argumento (por ejemplo, `specs/NNN-nombre`). Cada una se ejecuta en un contexto separado
   y devuelve un reporte que termina con una línea `RESUMEN`. No las repitas ni las
   interpretes: el veredicto no lo decides tú.
4. **Registra el veredicto.** De cada reporte toma **solo la línea `RESUMEN`** (la última,
   con el formato `RESUMEN: bloqueantes=N sugerencias=M cobertura=…`), nunca el reporte
   completo: un reporte entre comillas en una terminal permitiría inyectar comandos. Si un
   reporte no trae esa línea, pasa el texto `sin resumen` en su lugar. Ejecuta, con las
   líneas entre comillas simples:

   ```text
   uv run --no-project --python 3.12 --quiet ${CLAUDE_PROJECT_DIR}/.claude/hooks/veredicto.py registrar --commit <SHA_REVISADO> --codigo '<RESUMEN de revisar-codigo>' --auditoria '<RESUMEN de auditar-cumplimiento>'
   ```

5. **Interpreta el resultado** por el código de salida:
   - **0, `aprobado`**: sigue con las acciones.
   - **1, `con bloqueantes`**: se detiene **sin push ni PR** y sin cambiar el estado del
     ticket. Muestra los hallazgos bloqueantes de los dos reportes, con su ubicación, y el
     motivo del veredicto, e indica que se corrijan con commits nuevos y que hay que
     volver a ejecutar `/abrir-pr` (un commit nuevo exige una revisión nueva). El veredicto queda
     registrado para trazabilidad, pero la puerta solo acepta `aprobado`.
   - **2**: no hay veredicto. Si el mensaje es `El commit cambió durante la revisión…`,
     `HEAD` cambió mientras corrían las revisiones: se detiene sin push ni PR y se
     vuelve a ejecutar `/abrir-pr`. Con cualquier otro mensaje, informa el error y se
     detiene.
6. **Guarda para la descripción del PR**: el veredicto, `SHA_REVISADO`, los dos `RESUMEN` y
   los hallazgos no bloqueantes (sugerencias) de los dos reportes.

## 3. Acciones

1. `git push -u origin <rama>`. Si falla, se detiene sin PR y sin cambiar el estado.
2. `mcp__github__create_pull_request` con `owner: anahernandez0814`, `repo:
   due-diligence-pasarela-austral`, `head: <rama>`, `base: main` y título
   `<título del issue> (#N)`. La guarda `guarda_pr` lo bloquea si no hay veredicto aprobado
   del commit actual, publicado en la rama. La descripción, en español, tiene estas
   secciones:
   - **Resumen**: lo implementado, a partir de `spec.md`, `plan.md` y
     `git log origin/main..HEAD`.
   - **Criterios de aceptación**: los del issue y cómo se verificó cada uno.
   - **Revisión previa**: el veredicto, el commit revisado (`SHA_REVISADO`), el `RESUMEN` de
     la revisión de código y el de la auditoría, y las sugerencias con cómo se atendió cada
     una.
   - **Desviaciones y pendientes**.
   - Una línea `Closes #N`.
   - Al final, la línea exacta:
     `🤖 Generated with [Claude Code](https://claude.com/claude-code)`

   Si falla, se detiene sin cambiar el estado. Informa que la rama ya está subida y que
   puede volver a ejecutarse `/abrir-pr`.
3. `mcp__github__projects_write` con `method: update_project_item`, `owner:
   anahernandez0814`, `project_number: 1`, el `item_id` guardado en la comprobación 1.7 y
   `updated_field: {"name": "Status", "value": "In review"}`. Si falla, informa que el PR
   existe (con su enlace) y que el ticket sigue en `In Progress`, sin reintentar en
   silencio.
4. Comentario en el issue. Antes, `mcp__github__issue_read` (`method: get_comments`),
   recorriendo todas las páginas: si ya hay un comentario con `<!-- ciclo-tickets:pr -->`,
   no publica otro. Si no, `mcp__github__add_issue_comment` con:

   ```markdown
   <!-- ciclo-tickets:pr -->
   ## PR abierto: #M, en revisión

   El ticket pasa a **In review**. PR: #M (`<rama>` → `main`, con `Closes #N`).

   ### Lo especificado
   …
   ### Lo decidido
   …
   ### Revisión previa
   Veredicto del commit `SHA_REVISADO`: … (los dos `RESUMEN` y las sugerencias, y cómo se
   atendieron)
   ### Lo pendiente
   …
   ```

## Salida

Enlace al PR, veredicto de la revisión con su commit, Status nuevo y enlace al comentario.
Termina con este recordatorio:

> Tras el merge, el próximo `/siguiente-ticket` registra el cierre en el issue. Si era el
> último ticket, ejecútalo una vez más para registrarlo.
