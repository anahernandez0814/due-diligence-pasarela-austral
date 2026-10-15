---
name: siguiente-ticket
description: Toma el siguiente ticket del GitHub Project (o el indicado), verifica el cierre de los anteriores, lo mueve a In Progress, comenta el inicio y crea su rama y su spec con Spec Kit.
argument-hint: "[número de issue]"
allowed-tools:
  - Bash(git status:*)
  - Bash(git switch:*)
  - Bash(git pull:*)
  - Bash(git branch:*)
  - Bash(git ls-remote:*)
  - Read
  - Glob
  - Skill
  - mcp__github__projects_list
  - mcp__github__projects_get
  - mcp__github__projects_write
  - mcp__github__issue_read
  - mcp__github__add_issue_comment
---

# Siguiente ticket

Arranca un ticket del backlog sin mover tarjetas a mano. Todos los mensajes y comentarios
van en español.

Datos fijos del proyecto:

- Repositorio: `anahernandez0814/due-diligence-pasarela-austral`.
- GitHub Project: número `1` del usuario `anahernandez0814` ("Due Diligence - Pasarela
  Austral"), `owner_type: user`.
- Campo de estado: `Status`, con las opciones `Todo`, `In Progress`, `In review` y `Done`.
  Las opciones se buscan siempre por su nombre exacto; si no aparece el nombre exacto, la
  skill se detiene y no elige una parecida.

Contrato: `specs/002-automatizacion-tickets/contracts/siguiente-ticket.md`.

## Entrada

`$ARGUMENTS`:

- Vacío: el ítem del Project en Todo con el **menor número de issue**.
- Un entero `N`: el issue #N.
- Cualquier otra cosa: muestra el uso (`/siguiente-ticket [número de issue]`) y se detiene
  sin hacer nada más.

## Paso 0, verificación posterior al merge

Corre en **cada** invocación con una entrada válida (vacía o un entero), antes de todo lo
demás, también cuando el ticket pedido se vaya a rechazar o no quede nada en Todo. Con una
entrada inválida no corre: solo se muestra el uso. Registra en el issue el cierre de los tickets ya
fusionados. No modifica archivos del repositorio y nunca mueve tarjetas.

1. `mcp__github__projects_list` con `method: list_project_items`,
   `field_names: ["Status"]` y `query: "is:issue state:closed"`, recorriendo todas las
   páginas.
2. Para cada issue con `content.state_reason: completed` (viene en cada ítem de
   `list_project_items`), se excluyen los `not_planned`. Revisa sus comentarios con
   `mcp__github__issue_read` (`method: get_comments`), recorriendo todas las páginas. Si ya
   hay uno con
   `<!-- ciclo-tickets:cierre -->`, no hace nada con ese issue. Si no:
   - **Status `Done`**: lee el issue (`method: get`) y publica con
     `mcp__github__add_issue_comment`:

     ```markdown
     <!-- ciclo-tickets:cierre -->
     ## Cierre del ticket

     - **Issue #N**: cerrado (`completed`) el <closed_at> por el merge del PR #M (`Closes #N`).
     - **GitHub Project**: Status Done; el ítem se actualizó el <updated_at del ítem>, por
       el workflow "Item closed".

     Verificado sin mover tarjetas a mano.
     ```

     El PR sale de `closed_by_pull_requests`. Si viene vacío, porque el issue se cerró sin
     PR, la línea dice "cerrado sin PR asociado" y se anota en el informe final. Si quedan
     pendientes que pasan a otros tickets, se añaden en una sección "Lo pendiente".
   - **Otro Status**: lo anota para el informe final. No mueve la tarjeta y no comenta,
     para que la siguiente ejecución lo vuelva a revisar.
3. Si `list_project_items` o `get_comments` fallan, se detiene e informa: el MCP no está
   disponible y el resto de la skill también depende de él.

## Paso 1, comprobaciones

Si alguna falla, la skill se detiene e informa del motivo. Las comprobaciones remotas y del
ticket van antes de cambiar de rama, para que un ticket rechazado deje la sesión en la rama
donde estaba.

1. Guarda la rama actual con `git branch --show-current`. Comprueba que
   `git status --porcelain` no devuelve nada. Si hay cambios sin commitear, se detiene.
2. `mcp__github__projects_list` con `method: list_project_fields`. El campo `Status` debe
   tener la opción exacta `In Progress`. Esta llamada comprueba también que el MCP de
   GitHub está disponible; si falla, se detiene.
3. Ticket elegido. En `list_project_items` usa siempre `field_names: ["Status"]` y recorre
   todas las páginas (`after` con `pageInfo.nextCursor` mientras `hasNextPage` sea
   `true`).
   - **Sin argumento**: `list_project_items` con `query: "is:issue state:open"`. Elige el
     ítem con Status `Todo` y menor `content.number`. Si no hay ninguno, informa "No quedan
     tickets en Todo" y termina. Después lee el issue con `mcp__github__issue_read`
     (`method: get`) para tener título y cuerpo.
   - **Con argumento N**, en este orden:
     1. `mcp__github__issue_read` (`method: get`) del issue #N. Si no existe, informa que
        el issue #N no existe. Si está cerrado, informa que está cerrado (con su
        `state_reason`). En los dos casos se detiene.
     2. `list_project_items` con `query: "is:issue"`, sin filtro de estado. Busca el ítem
        cuyo `content.number` es N. Si no aparece, informa que #N no está en el Project.
        Si su Status no es `Todo`, informa el Status actual. En los dos casos se detiene.
        Un ticket ya en `In Progress` no se retoma sin que la persona lo pida.
4. Calcula el nombre corto, NNN y la rama (ver "Nombre corto" más abajo). La rama es
   `NNN-<nombre-corto>`.
5. `git ls-remote --heads origin 'refs/heads/NNN-*'` no devuelve nada. Si existe en
   `origin` cualquier rama con ese NNN, aunque tenga otro nombre corto, se detiene.
6. `git switch main` y después `git pull --ff-only`.
7. Ya sobre `main` actualizado:
   - `git branch --list 'NNN-*'` no devuelve nada.
   - No existe ninguna carpeta `specs/NNN-*`, con el mismo NNN y cualquier nombre. Glob
     no devuelve carpetas, así que usa Glob con `specs/NNN-*/**`: si devuelve algún
     archivo, la carpeta existe y la skill se detiene.

Si fallan los pasos 6 o 7, vuelve con `git switch <rama guardada>` e informa. Hasta aquí no
se ha movido el ticket ni se ha comentado nada.

## Nombre corto

Regla determinista a partir del título del issue:

1. Quitar tildes y diacríticos (á→a, é→e, í→i, ó→o, ú→u, ü→u, ñ→n) y pasar a minúsculas.
2. Cambiar todo lo que no sea `a-z` o `0-9` por espacios.
3. Quitar las palabras vacías: a, al, con, de, del, el, en, la, las, los, para, por, un,
   una, y.
4. Tomar las tres primeras palabras restantes y unirlas con `-`.

NNN es el número del issue con tres dígitos (3 → `003`, 12 → `012`).

Ejemplos:

- "Guardas de Claude Code: hooks, permisos y reglas por ruta" → `guardas-claude-code`.
- "Servidor MCP de la pasarela con datos ficticios" → `servidor-mcp-pasarela`.
- "Interfaz de chat" → `interfaz-chat`.

## Paso 2, acciones

En este orden:

1. `mcp__github__projects_write` con `method: update_project_item`, `owner:
   anahernandez0814`, `project_number: 1`, el `item_id` del ítem y `updated_field:
   {"name": "Status", "value": "In Progress"}`.
2. Comentario de inicio. Antes, `mcp__github__issue_read` con `method: get_comments`,
   recorriendo todas las páginas: si ya hay un comentario que contiene `<!-- ciclo-tickets:inicio -->`, no publica otro. Si no,
   `mcp__github__add_issue_comment` con este cuerpo:

   ```markdown
   <!-- ciclo-tickets:inicio -->
   Se inicia el ticket. Rama `NNN-nombre-corto`, creada desde `main` actualizado; se ejecuta
   `/speckit-specify` para generar la especificación en `specs/NNN-nombre-corto/`.

   Siguiente: `/speckit-clarify` si la spec queda con marcadores de aclaración; si no,
   `/speckit-plan` cuando la spec esté lista.
   ```

3. `git switch -c NNN-<nombre-corto>`.
4. Invoca `/speckit-specify` con la herramienta Skill (`skill: speckit-specify`). En
   `args` van el cuerpo del issue como descripción de la feature y, en líneas aparte:
   - `SPECIFY_FEATURE_DIRECTORY=specs/NNN-<nombre-corto>`: la carpeta exacta, que
     `speckit-specify` usa tal cual.
   - `--number N`.
   - `Issue #N de GitHub: <título>`.

   No pases solo `--number`: no es estricto, y la skill de Spec Kit toma el siguiente
   número libre de `specs/`.
5. Comprobación: `.specify/feature.json` contiene
   `"feature_directory": "specs/NNN-<nombre-corto>"` y existe
   `specs/NNN-<nombre-corto>/spec.md`. Si no, lo informa como error.
6. El comentario de lo especificado lo publica el hook `after_specify` de
   `.specify/extensions.yml`, al terminar `/speckit-specify`. La skill **no** lo publica.
   Comprueba con `mcp__github__issue_read` (`method: get_comments`, todas las páginas) que
   existe un comentario con
   `<!-- ciclo-tickets:especificado -->`. Si falta, informa que el hook no se ejecutó y
   sugiere `/comentar-avance especificado`.

Si algo falla después de la acción 1, informa del paso exacto que no se completó y de que
el ticket quedó en `In Progress`. No reviertas el Status en silencio: el comentario de
inicio ya explica en el issue lo que pasó.

## Secuencia del ticket

Al terminar, muestra la secuencia que sigue:

specify → clarify (solo si la spec tiene marcadores `[NEEDS CLARIFICATION]`) → plan →
tasks → analyze → implement → converge (solo si quedan brechas) → `/abrir-pr`.

Recordatorios:

- Los comentarios de avance tras specify, clarify, plan y analyze los publican los hooks de
  `.specify/extensions.yml`. Si un hook no se ejecutó, `/comentar-avance
  especificado|plan|analyze` lo publica a mano.
- `tasks.md` solo contiene tareas que se completan **antes del merge**. La verificación
  posterior al merge no es una tarea: la hace el paso 0 del siguiente `/siguiente-ticket`.
- `/abrir-pr` ejecuta la revisión previa antes de subir la rama.

## Salida

Mensaje en español con:

- Paso 0: issues cuyo cierre se registró, con enlace al comentario, y los issues cerrados
  que no están en Done (si los hay).
- Ticket elegido, rama, carpeta de specs y enlace al comentario de inicio.
- Resultado de la comprobación de `feature.json` y del comentario de lo especificado.
- El siguiente comando de la secuencia.
