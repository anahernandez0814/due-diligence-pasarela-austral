# Research: Automatización del ciclo de tickets en GitHub

Fase 0 del plan del ticket #2. Cada entrada resuelve una incógnita del contexto técnico o
uno de los hallazgos (a)–(i) del analista.

## R1. Número de la feature: `--number` no es estricto

- **Hallazgo**: `create_new_feature.py --number N` "prefiere" el número y lo corrige en
  silencio si ya existe `specs/NNN-*` (`--help`: "auto-corrected if its specs prefix
  exists"). Además, la skill `speckit-specify` instalada no lee `--number`: con
  `feature_numbering: sequential` toma "el siguiente número libre" de `specs/`. Hoy
  coincide con el issue solo porque el backlog se ejecuta en orden; con un argumento fuera
  de orden (por ejemplo `/siguiente-ticket 7` con `specs/` hasta 004) daría `005`.
- **Decisión**: `siguiente-ticket` calcula la carpeta exacta `specs/NNN-<nombre-corto>` y
  la pasa a `/speckit-specify` como `SPECIFY_FEATURE_DIRECTORY` explícito, que la skill usa
  tal cual (paso 3, orden de resolución 1). También pasa `--number N`, como pide el issue,
  aunque no sea el mecanismo que fija el número. Dos comprobaciones lo blindan:
  - **Antes**: no existe ninguna carpeta `specs/NNN-*` con el número del issue.
  - **Después**: `.specify/feature.json` contiene `"feature_directory": "specs/NNN-<nombre-corto>"`
    y existe `specs/NNN-<nombre-corto>/spec.md`. Si no, se detiene y lo informa.
- **Alternativas descartadas**:
  - Fiarse de `--number`: falla en silencio.
  - Editar `speckit-specify` para que respete `--number`: las skills de Spec Kit se
    sobrescriben al actualizar.
  - Llamar a `create_new_feature.py` desde la skill: hereda la corrección silenciosa y
    `python` no está en el PATH de Windows (hay que usar el intérprete de `specify-cli` o
    `uv run --no-project python`).

## R2. La rama del ticket

- **Hallazgo**: no hay hook `before_specify` ni extensión git instalada
  (`.specify/extensions.yml` no existe). `speckit-specify` crea la carpeta de specs pero
  no la rama.
- **Decisión**: la skill crea la rama con `git switch -c NNN-<nombre-corto>` desde `main`
  actualizado, justo antes de invocar `/speckit-specify`.
- **Alternativa descartada**: instalar la extensión git de Spec Kit. Añade una dependencia
  y su propia convención de nombres para resolver un solo comando.

## R3. Orden del arranque (FR-021)

- **Decisión**: primero todas las comprobaciones sin efectos; después las acciones, en un
  orden en el que un fallo deja el menor estado incoherente posible.
  1. Paso 0: verificación posterior al merge de tickets anteriores (R5). Solo lee el
     Project y comenta issues cerrados.
  2. Comprobaciones, en este orden:
     1. Árbol de trabajo limpio; se guarda la rama actual.
     2. El MCP responde y el campo Status tiene la opción exacta "In Progress".
     3. El ticket elegido existe en el Project, está abierto y en Todo.
     4. Nombre corto, NNN y rama.
     5. La rama no existe en `origin`.
     6. `git switch main` y `git pull --ff-only`.
     7. Ya sobre `main` actualizado: la rama no existe en local ni hay `specs/NNN-*`.
     Todo lo que puede rechazar el ticket va antes de cambiar de rama, así que un rechazo
     (Q2, Q3, Q4) deja la sesión donde estaba. Si fallan 6 o 7, la skill vuelve a la rama
     guardada y lo informa.
  3. Acciones: mover a "In Progress" → comentario de inicio → `git switch -c` →
     `/speckit-specify` → comprobación de `feature.json`.
- **Motivo**: ningún fallo previsible deja el ticket en "In Progress" sin rama. Si una
  acción falla después de mover el ticket (por ejemplo, la creación de la rama), la skill
  lo informa con el paso exacto y no intenta deshacer en silencio: el comentario de inicio
  ya explica en el issue lo que pasó.
- **Alternativa descartada**: crear la rama antes de mover el ticket. Un fallo del MCP
  dejaría una rama local huérfana y el Project sin reflejarlo; el orden elegido falla antes
  de tocar nada.

## R4. Comentarios de avance (specify, clarify, plan, analyze): hooks nativos de Spec Kit

- **Hallazgo**: `speckit-plan` y `speckit-analyze` (y el resto de comandos) leen
  `.specify/extensions.yml` al terminar (`hooks.after_plan`, `hooks.after_analyze`) y, para
  cada hook con `optional: false`, emiten `EXECUTE_COMMAND: <command>` y lo ejecutan. El
  formato de cada entrada, tomado de `specify_cli/extensions` (`register_hooks`), es:
  `extension`, `command`, `enabled`, `optional`, `priority`, `prompt`, `description`,
  `condition`. La interpretación la hace el agente, así que basta con el archivo; no hace
  falta instalar una extensión.
- **Decisión**: `.specify/extensions.yml` versionado con cuatro hooks obligatorios de la
  extensión local `ciclo-tickets`:
  - `after_specify` → `command: comentar-avance especificado` (FR-022)
  - `after_clarify` → `command: comentar-avance especificado` (actualiza el anterior)
  - `after_plan` → `command: comentar-avance plan`
  - `after_analyze` → `command: comentar-avance analyze`
  Todos ejecutan el comando versionado `.claude/commands/comentar-avance.md`. No se edita
  ninguna skill de Spec Kit. Como `siguiente-ticket` invoca `/speckit-specify`, el
  comentario `especificado` lo publica el hook `after_specify` y no la skill.
- **Qué garantizan estos hooks**: son instrucciones que el modelo ejecuta al terminar el
  comando de Spec Kit, no hooks de Claude Code. Mejoran la constancia, porque la
  instrucción viaja con el comando y no depende de recordarla, pero no la garantizan: un
  modelo puede no emitir o no ejecutar el `EXECUTE_COMMAND`. Es aceptable, porque los
  comentarios de avance no están entre las garantías obligatorias del principio II
  (reglas I.1 e I.2, secretos, datos con forma real y spec previa).
- **Riesgo y verificación**: el formato no prevé argumentos; `command` es un identificador.
  `comentar-avance plan` no tiene puntos, así que la sustitución `.` → `-` no lo altera, y
  el agente invoca `/comentar-avance plan`. El quickstart (escenarios Q6 y Q7) comprueba
  que el argumento llega. **Plan B** si no llega: tres comandos sin argumento,
  `comentar-especificado`, `comentar-plan` y `comentar-analyze`, con la misma lógica
  compartida.
- **Riesgo de convivencia**: si en el futuro se instala una extensión real con
  `specify extension add`, `register_hooks` solo purga las entradas de *su* `extension`;
  las de `ciclo-tickets` se mantienen.
- **Alternativas descartadas**:
  - Editar `speckit-plan` y `speckit-analyze`: se pierde al actualizar Spec Kit.
  - Pedir el comentario solo en `siguiente-ticket` como instrucción: depende de que la
    sesión lo recuerde, justo lo que los hooks evitan.
  - Hooks de Claude Code (`PostToolUse`/`Stop`): no saben cuándo terminó un comando de
    Spec Kit y son del ticket #3.

## R5. Verificación posterior al merge como paso 0 de `siguiente-ticket`

- **Decisión**: al empezar, la skill revisa los ítems del Project que son issues cerrados
  con `state_reason: completed` y no tienen comentario con el marcador
  `ciclo-tickets:cierre`. Para cada uno:
  - Si su Status es Done: comenta el cierre (PR que lo cerró, hora de cierre y hora del
    ítem) con el marcador.
  - Si no es Done: lo reporta a la persona del equipo, no mueve la tarjeta y no comenta,
    para que la siguiente ejecución lo vuelva a revisar.
  Luego sigue con el arranque. Con el Todo vacío (después de #14) hace el paso 0 y después
  informa que no quedan tickets.
- **Último ticket**: después del merge de #14 no hay arranque que dispare el paso 0, así
  que hace falta una ejecución más de `/siguiente-ticket` para registrar su cierre. Lo
  recuerdan la salida de `/abrir-pr` ("tras el merge, el próximo `/siguiente-ticket`
  registra el cierre; si era el último ticket, ejecútalo una vez más") y la sección "Ciclo
  de un ticket" del README.
- **Fallo del MCP en el paso 0**: si `list_project_items` o `get_comments` fallan, la skill
  se detiene e informa (FR-021). No sigue con el arranque, porque el resto también
  depende del MCP.
- **Motivo**: es el primer momento en que alguien vuelve a trabajar después de un merge,
  y no necesita archivos del repositorio. Cumple FR-017 y FR-018: nada de lo posterior al
  merge vive en `tasks.md`.
- **Issues cerrados antes de este flujo**: el issue #1 ya tiene su comentario de cierre,
  pero sin marcador. Durante la implementación se añade el marcador a ese comentario
  existente (editándolo, no duplicándolo), para que el paso 0 no lo vuelva a comentar.
- **Issues cerrados como "not planned"**: se excluyen; no hay nada que verificar.
- **Alternativas descartadas**:
  - Un comando aparte `/verificar-cierre`: depende de que alguien lo recuerde.
  - Una GitHub Action al cerrar el issue: añade otra pieza y otro token fuera de Claude
    Code; el workflow nativo del Project ya hace el movimiento y solo falta registrarlo.
  - Una tarea en `tasks.md`: es el problema observado en el ticket #1.

## R6. Marcadores en los comentarios

- **Decisión**: cada comentario del flujo empieza con un comentario HTML invisible:
  `<!-- ciclo-tickets:inicio -->`, `especificado`, `plan`, `analyze`, `pr` y `cierre`.
  Sirven para:
  - Detectar los existentes con `issue_read` (`get_comments`).
  - No duplicar: `inicio`, `pr` y `cierre` no se repiten. `especificado`, `plan` y
    `analyze` se actualizan si ya existen (clarify tras specify, o analyze repetido tras
    corregir). Se editan con `update_issue_comment` **añadiendo** al final una sección
    "Actualización <fecha>" con lo nuevo y **conservando** el cuerpo anterior. Reemplazarlo
    borraría del issue los hallazgos previos y cómo se resolvieron (SC-004).
  - Contar SC-003 (seis marcadores distintos por ticket cerrado).
- **Alternativa descartada**: reconocer los comentarios por su encabezado visible. Es
  frágil ante cambios de redacción.

## R7. Nombre corto de la rama

- **Decisión**: regla determinista a partir del título del issue:
  1. Quitar tildes y diacríticos (á→a, ñ→n, ü→u) y pasar a minúsculas.
  2. Cambiar todo lo que no sea `a-z0-9` por espacios.
  3. Quitar palabras vacías: a, al, con, de, del, el, en, la, las, los, para, por, un,
     una, y.
  4. Tomar las tres primeras palabras restantes y unirlas con `-`.
  Ejemplos: "Guardas de Claude Code: hooks, permisos y reglas por ruta" →
  `guardas-claude-code`; "Servidor MCP de la pasarela con datos ficticios" →
  `servidor-mcp-pasarela`; "Interfaz de chat" → `interfaz-chat`.
- **Motivo**: el mismo título da siempre el mismo nombre, sin depender del criterio de la
  sesión. Las ramas de #1 y #2 se crearon a mano y no se renombran.
- **Alternativa descartada**: dejar que el modelo resuma el título; no es reproducible.

## R8. Herramientas reales del MCP de GitHub

Verificadas en este ticket y en el #1, con el Project #1 del usuario `anahernandez0814`
(Status: Todo `f75ad846`, In Progress `47fc9ee4`, In review `65894d4b`, Done `98236657`,
campo `426232599`):

| Uso | Herramienta | Método o parámetros |
|-----|-------------|---------------------|
| Opciones del campo Status | `projects_list` | `list_project_fields` |
| Ítems y su Status | `projects_list` | `list_project_items` con `field_names: ["Status"]` y `query` (`is:issue state:open`, `is:issue state:closed`) |
| Un ítem | `projects_get` | `get_project_item` |
| Mover el ticket | `projects_write` | `update_project_item` con `updated_field {"name":"Status","value":"In Progress"}` |
| Cuerpo, estado y comentarios del issue | `issue_read` | `get`, `get_comments` |
| Comentar | `add_issue_comment` | — |
| Actualizar el comentario de plan o analyze | `update_issue_comment` | — |
| PR existente de la rama | `list_pull_requests` | `head: anahernandez0814:<rama>`, `state: open` |
| Abrir el PR | `create_pull_request` | `head`, `base: main` |

En los `allowed-tools` se escriben con el prefijo `mcp__github__`. Los nombres y los
identificadores del Project se leen en cada ejecución, no se escriben a fuego: la skill
busca la opción por su nombre exacto y se detiene si no existe.

## R9. Comandos y skills de Claude Code

- **Decisión**:
  - `siguiente-ticket` como skill en `.claude/skills/siguiente-ticket/SKILL.md`, con
    `allowed-tools` y `argument-hint: "[número de issue]"`, como pide el issue.
  - `/abrir-pr` y `/comentar-avance` como comandos en `.claude/commands/`, con
    `description`, `argument-hint` y `allowed-tools`.
  - La skill invoca `/speckit-specify` mediante la herramienta Skill, así que `Skill` va en
    sus `allowed-tools`.
- **Sin `context: fork` en `siguiente-ticket`**: la skill invoca `/speckit-specify`, que
  puede hacer preguntas de aclaración, y su resultado (spec, `feature.json`, siguiente
  paso) tiene que quedar en la conversación principal, donde sigue el ciclo. Un contexto
  bifurcado devolvería solo un resumen y cortaría ese diálogo. `context: fork` se usará en
  las skills de revisión del ticket #4, que sí deben aislarse de la sesión que generó el
  código.
- **Revisión previa dentro de `/abrir-pr`**: es un paso aislado del comando. Hasta el
  ticket #4, lanza un subagente de tipo `Plan`, en contexto separado, sobre el diff contra
  `main`.
  - Se elige `Plan` y no `general-purpose` porque no tiene Edit, Write ni NotebookEdit:
    el "solo lectura" lo limitan las herramientas y no solo la instrucción.
  - La limitación es parcial, porque `Plan` conserva Bash; la instrucción sigue
    prohibiendo comandos con efectos.
  - La restricción completa, con un agente definido solo con Read, Grep y Glob, queda para
    las skills de revisión del #4. Si hay hallazgos bloqueantes, se detiene; si no, registra el
  veredicto en la descripción del PR. El #4 lo reemplaza por `revisar-codigo`,
  `auditar-cumplimiento` y su puerta mecánica sin tocar el resto del comando.
- **Motivo**: es la forma que exige el enunciado; las dos variantes se versionan y llegan
  a quien clona el repositorio.

## R10. Validación sin efectos sobre el backlog real

- **Hallazgo**: un arranque positivo de `siguiente-ticket` mueve un ticket real. Antes del
  merge de #2, el ticket siguiente en Todo es el #3.
- **Decisión**:
  - **Antes del PR**: los escenarios negativos (árbol sucio, número que no está en Todo,
    issue cerrado) y el paso 0 sobre #1, que no tienen efectos. Además, `/comentar-avance`
    con `analyze` disparado por el hook real al repetir `/speckit-analyze`, que es de solo
    lectura, y `/comentar-avance especificado` invocado directamente, que actualiza el
    comentario manual de #2. Por último, `/abrir-pr` en su caso negativo y luego en real,
    con su revisión previa, para abrir el PR del propio ticket #2.
  - **Después del merge**: el primer uso real, `/siguiente-ticket` para arrancar #3, valida
    el arranque positivo, el hook `after_specify` y, con su paso 0, el cierre de #2. Si algo falla, se reporta en el
    issue #2 y se corrige en un ticket nuevo.
- **Alternativa descartada**: crear un issue de prueba en el Project. Deja rastro en el
  backlog y en la numeración de issues para validar algo que el uso real valida igual.
