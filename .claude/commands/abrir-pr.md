---
description: "Verifica spec, plan y tareas del ticket, ejecuta la revisión previa, sube la rama, abre el PR hacia main con Closes #N, mueve el ticket a In review y comenta en el issue."
argument-hint: ""
allowed-tools:
  - Bash(git branch:*)
  - Bash(git status:*)
  - Bash(git cat-file:*)
  - Bash(git log:*)
  - Bash(git fetch:*)
  - Bash(git diff:*)
  - Bash(git push:*)
  - Read
  - Glob
  - Grep
  - Agent
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

Contrato: `specs/002-automatizacion-tickets/contracts/abrir-pr.md`.

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

## 2. Revisión previa

> **Paso aislado, de transición.** El ticket #4 reemplaza esta sección por las skills
> `revisar-codigo` y `auditar-cumplimiento` y por su puerta mecánica. El resto del comando
> solo depende del veredicto que sale de aquí.

1. `git fetch origin main` y `git diff origin/main...HEAD`.
2. Lanza un subagente con la herramienta Agent, `subagent_type: Plan`, en contexto
   separado.
   - El tipo `Plan` no tiene Edit, Write ni NotebookEdit.
   - Conserva Bash, así que el prompt le prohíbe expresamente cualquier comando con
     efectos: git que modifique algo, redirecciones a archivos, borrados o instalaciones.

   El prompt le da:
   - el diff completo;
   - las rutas de `spec.md`, `plan.md` y `tasks.md` del ticket y de
     `.specify/memory/constitution.md`, para que las lea;
   - los criterios de aceptación del issue #N, copiados del cuerpo del issue.

   Y le pide revisar el diff frente a esos documentos (correcciones, consistencia,
   cumplimiento de la constitución, credenciales o datos con forma real) y devolver:
   - un **veredicto**: `aprobado`, `aprobado con cambios` o `bloqueado`;
   - sus **hallazgos**, cada uno con severidad (`bloqueante`, `importante` o `menor`),
     archivo y motivo.
3. Si hay algún hallazgo `bloqueante`, el comando se detiene sin push ni PR, muestra los
   hallazgos e indica que se corrijan con commits nuevos y se vuelva a ejecutar
   `/abrir-pr`.
4. Guarda el veredicto y los hallazgos no bloqueantes para la descripción del PR.

## 3. Acciones

1. `git push -u origin <rama>`. Si falla, se detiene sin PR y sin cambiar el estado.
2. `mcp__github__create_pull_request` con `owner: anahernandez0814`, `repo:
   due-diligence-pasarela-austral`, `head: <rama>`, `base: main` y título
   `<título del issue> (#N)`. La descripción, en español, tiene estas secciones:
   - **Resumen**: lo implementado, a partir de `spec.md`, `plan.md` y
     `git log origin/main..HEAD`.
   - **Criterios de aceptación**: los del issue y cómo se verificó cada uno.
   - **Revisión previa**: el veredicto y los hallazgos no bloqueantes, y cómo se atendió
     cada uno.
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
   Veredicto: … (hallazgos no bloqueantes y cómo se atendieron)
   ### Lo pendiente
   …
   ```

## Salida

Enlace al PR, veredicto de la revisión, Status nuevo y enlace al comentario. Termina con
este recordatorio:

> Tras el merge, el próximo `/siguiente-ticket` registra el cierre en el issue. Si era el
> último ticket, ejecútalo una vez más para registrarlo.
