# Contrato: comando `/abrir-pr`

Archivo: `.claude/commands/abrir-pr.md`.

## Frontmatter

```yaml
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
```

## Entrada

Ninguna. El ticket se deduce de la rama actual.

## Pasos

### 1. Comprobaciones

Si alguna falla, se detiene sin subir la rama, sin abrir el PR y sin cambiar el estado del
ticket.

1. La rama actual no es `main` y cumple `^(\d{3})-[a-z0-9-]+$`; N = `int(NNN)`.
2. `git status --porcelain` está vacío.
3. Existe exactamente una carpeta `specs/NNN-*`, y `spec.md`, `plan.md` y `tasks.md`
   están en `HEAD` (`git cat-file -e HEAD:<ruta>`). Si falta alguno, lo nombra. Glob no
   devuelve carpetas, así que la carpeta se deduce de Glob `specs/NNN-*/*`.
4. El issue #N existe y está abierto.
5. `list_pull_requests` con `head: anahernandez0814:<rama>` y `state: open` no devuelve
   ninguno. Si hay uno, lo enlaza y termina.
6. El campo Status tiene la opción exacta "In review".
7. El ítem de #N está en el Project. Se busca con `list_project_items` y
   `query: "is:issue"`, recorriendo todas las páginas, y se guarda su `item_id` para la
   acción 3. Así, que el ticket no esté en el Project se detecta antes del push.

### 2. Revisión previa (paso aislado, de transición)

El ticket #4 reemplazará esta sección por las skills `revisar-codigo` y
`auditar-cumplimiento` y por su puerta mecánica. El resto del comando no depende de cómo
se haga la revisión, solo de su veredicto.

1. `git fetch origin main` y `git diff origin/main...HEAD`.
2. Lanza un subagente de tipo `Plan` en contexto separado.
   - Ese tipo no tiene Edit, Write ni NotebookEdit, así que no puede editar archivos con
     sus herramientas: el "solo lectura" lo limitan las herramientas, no solo la
     instrucción.
   - Conserva Bash, así que la instrucción sigue prohibiéndole comandos con efectos (git,
     redirecciones, borrados). La restricción completa, con un agente definido solo con
     Read, Grep y Glob, llega con las skills de revisión del ticket #4.

   El subagente recibe:
   - el diff;
   - `spec.md`, `plan.md` y `tasks.md`;
   - los criterios de aceptación del issue #N;
   - la constitución.
3. El subagente devuelve:
   - un veredicto: **aprobado**, **aprobado con cambios** o **bloqueado**;
   - sus hallazgos, cada uno con severidad (bloqueante, importante o menor), archivo y
     motivo.
4. Si hay algún hallazgo bloqueante, el comando se detiene sin push ni PR, y muestra los
   hallazgos para corregirlos.
5. El veredicto y los hallazgos no bloqueantes van a la sección "Revisión previa" de la
   descripción del PR.

### 3. Acciones

1. `git push -u origin <rama>`. Si falla, se detiene.
2. `create_pull_request` con `head: <rama>`, `base: main`, título
   `<título del issue> (#N)` y descripción en español:
   - Resumen de lo implementado, a partir de `spec.md`, `plan.md` y `git log origin/main..HEAD`.
   - Criterios de aceptación del issue y cómo se verificaron.
   - Revisión previa: veredicto y hallazgos no bloqueantes.
   - Desviaciones o pendientes.
   - `Closes #N`.
   - Al final, la línea de atribución exacta que usó el PR #15:
     `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
3. `update_project_item` con `updated_field {"name": "Status", "value": "In review"}`.
4. Comentario `pr` en el issue ([comentarios.md](comentarios.md)).

## Salida

Enlace al PR, veredicto de la revisión, Status nuevo y enlace al comentario. Termina con
este recordatorio: "Tras el merge, el próximo `/siguiente-ticket` registra el cierre en el
issue. Si era el último ticket, ejecútalo una vez más para registrarlo."

## Lo que no hace

- No corrige los hallazgos de la revisión: los muestra y, si son bloqueantes, se detiene.
- No ejecuta la revisión de cumplimiento de reglas de negocio. Eso llega con
  `auditar-cumplimiento` en el ticket #4.
- No fusiona el PR.
- No garantiza por código que la spec exista ni que la revisión se haya hecho. Ambas
  comprobaciones son por instrucción hasta los hooks del ticket #3 y la puerta mecánica
  del #4 (desviación temporal del principio II).
