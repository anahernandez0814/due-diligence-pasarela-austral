# Contrato: skill `siguiente-ticket`

Archivo: `.claude/skills/siguiente-ticket/SKILL.md`.

## Frontmatter

```yaml
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
```

## Entrada

- Sin argumento: el ítem del Project en Todo con el menor número de issue.
- Con argumento `N` (entero): el issue #N.
- Cualquier otro argumento: se detiene y muestra el uso.

## Pasos (en este orden)

**Paso 0, verificación posterior al merge** ([research.md](../research.md), R5):

1. `list_project_items` con `query: "is:issue state:closed"` y `field_names: ["Status"]`.
2. Para cada issue con `state_reason: completed` sin comentario `ciclo-tickets:cierre`:
   - Status Done → comentario `cierre` ([comentarios.md](comentarios.md)).
   - Otro Status → se anota para el informe final; no se mueve ni se comenta.
3. Si `list_project_items` o `get_comments` fallan, se detiene e informa (FR-021), sin
   seguir con el arranque.

**Paso 1, comprobaciones** (si alguna falla, se detiene sin mover el ticket). Las
comprobaciones remotas y del ticket van antes de cambiar de rama, para que un ticket
rechazado (por ejemplo, Q2: `/siguiente-ticket 2`) deje la sesión en la rama donde estaba:

1. `git status --porcelain` vacío. Antes, guarda la rama actual
   (`git branch --show-current`).
2. `list_project_fields`: el campo Status tiene la opción exacta "In Progress". Esta
   llamada sirve también para comprobar que el MCP está disponible.
3. Ticket elegido: con argumento, el ítem de #N existe en el Project, el issue está
   abierto y su Status es Todo; sin argumento, existe al menos un ítem abierto en Todo
   (si no, informa "no quedan tickets en Todo" y termina, después del paso 0).
4. Nombre corto según R7, NNN con tres dígitos y rama `NNN-<nombre-corto>`.
5. La rama no existe en `origin` (`git ls-remote --heads origin NNN-<nombre-corto>`).
6. `git switch main` y `git pull --ff-only` sin error.
7. Ya sobre `main` actualizado: la rama no existe en local (`git branch --list`) y no hay
   ninguna carpeta `specs/NNN-*`.

Si fallan los pasos 6 o 7, vuelve a la rama guardada en el paso 1 (`git switch <rama>`) y
lo informa. Hasta aquí no se ha movido el ticket ni se ha comentado nada.

**Paso 2, acciones**:

1. `update_project_item` con `updated_field {"name": "Status", "value": "In Progress"}`.
2. Comentario `inicio` en el issue.
3. `git switch -c NNN-<nombre-corto>`.
4. `/speckit-specify` con el cuerpo del issue como insumo, más
   `SPECIFY_FEATURE_DIRECTORY=specs/NNN-<nombre-corto>` y `--number N`. Al terminar, el
   hook `after_specify` publica el comentario `especificado`; la skill **no** lo publica,
   para no duplicarlo.
5. Comprobación: `.specify/feature.json` apunta a `specs/NNN-<nombre-corto>` y existe su
   `spec.md`. Si no, lo informa como error. Si falta el comentario `especificado` en el
   issue, lo informa (el hook no se ejecutó) y sugiere `/comentar-avance especificado`;
   no lo publica por su cuenta.

La skill no usa `context: fork`: `/speckit-specify` puede hacer preguntas de aclaración, y
su resultado tiene que quedar en la conversación principal, donde sigue el ciclo.

## Secuencia del ticket (se muestra al terminar)

specify → clarify (solo si quedan marcadores `[NEEDS CLARIFICATION]`) → plan → tasks →
analyze → implement → converge (solo si quedan brechas) → `/abrir-pr`.

Recordatorios que muestra la skill:

- Los comentarios tras specify, clarify, plan y analyze los publican los hooks de
  `.specify/extensions.yml`.
- `tasks.md` solo contiene tareas que se completan antes del merge.
- `/abrir-pr` ejecuta la revisión previa antes de subir la rama.

## Salida

Mensaje en español con:

- Paso 0: issues verificados y comentados; issues cerrados que no están en Done (si los
  hay).
- Ticket elegido, rama, carpeta de specs y enlace al comentario de inicio.
- Siguiente comando de la secuencia.

## Errores

Cada error indica el paso que no se completó y el estado en el que queda el ticket. Si
falla el paso 2.3 o posterior con el ticket ya en "In Progress", la skill lo dice
explícitamente y no revierte el Status en silencio.
