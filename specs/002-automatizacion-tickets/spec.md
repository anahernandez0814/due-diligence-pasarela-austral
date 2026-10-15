# Feature Specification: Automatización del ciclo de tickets en GitHub

**Feature Branch**: `002-automatizacion-tickets`

**Created**: 2026-10-15

**Status**: Draft

**Input**: Issue #2 de GitHub, "Automatización del ciclo de tickets en GitHub"
(https://github.com/anahernandez0814/due-diligence-pasarela-austral/issues/2), más el
aprendizaje del ticket #1 sobre la verificación posterior al merge.

**Objetivo**: que el estado de los tickets en el GitHub Project se mantenga sincronizado con
el avance real sin intervención manual, que cada ticket recorra el ciclo completo de Spec
Kit y que un evaluador pueda reconstruir el avance del proyecto solo mirando GitHub.

> Nota: este ticket configura el flujo de trabajo del equipo. Los nombres de piezas y
> herramientas (skill `siguiente-ticket`, comando `/abrir-pr`, MCP de GitHub, comandos de
> Spec Kit, opciones de Status del Project) forman parte del requisito del issue y del
> enunciado, no son decisiones de implementación de esta spec.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tomar el siguiente ticket y arrancarlo (Priority: P1)

La persona del equipo pide a Claude Code el siguiente ticket. Sin indicar nada más, se toma
del GitHub Project el ítem en Todo con el menor número de issue (el backlog está numerado en
orden de ejecución); si la persona indica un número, se toma ese. El ticket pasa a
"In Progress", el issue recibe un comentario de inicio y, desde `main` actualizado, se crea
la rama `NNN-nombre-corto` y la carpeta `specs/NNN-*` con el número del issue, usando el
cuerpo del issue como insumo de la especificación.

**Why this priority**: es la entrada del ciclo; sin ella, cada ticket se arranca a mano y el
estado del Project depende de la memoria de quien trabaja.

**Independent Test**: con varios ítems en Todo, invocar la skill sin argumento y comprobar
que toma el de menor número, que el Project lo muestra en "In Progress", que el issue tiene
el comentario de inicio y que la rama y la carpeta de specs llevan el número del issue.
Repetir con un número explícito.

**Acceptance Scenarios**:

1. **Given** los issues #3, #4 y #7 en Todo, **When** se invoca la skill sin argumento,
   **Then** se toma el #3.
2. **Given** el issue #7 en Todo, **When** se invoca la skill con el argumento `7`,
   **Then** se toma el #7 aunque haya números menores en Todo.
3. **Given** el ticket tomado, **When** termina el arranque, **Then** su Status en el
   Project es "In Progress" y el issue tiene un comentario de inicio con la rama y la
   carpeta de specs.
4. **Given** el ticket #N tomado, **When** termina el arranque, **Then** existe la rama
   `NNN-nombre-corto` creada desde `main` actualizado, existe `specs/NNN-*/spec.md` con el
   mismo número, y no hay ningún commit nuevo en `main`.

---

### User Story 2 - Abrir el pull request del ticket (Priority: P2)

Terminada la implementación, la persona del equipo ejecuta `/abrir-pr`. El comando
comprueba que la especificación, el plan y las tareas del ticket están commiteados en la
rama; si falta alguno, se detiene y dice cuál. Si están, sube la rama, abre el pull request
hacia `main` con `Closes #N`, mueve el ticket a "In review" y comenta en el issue lo
especificado, lo decidido y lo pendiente.

**Why this priority**: es la salida del ciclo y la que garantiza que el merge cierre el
issue; depende de que el ticket se haya arrancado con la convención de P1.

**Independent Test**: en una rama de ticket sin `tasks.md` commiteado, ejecutar
`/abrir-pr` y comprobar que se detiene sin abrir PR. Commitear el archivo, repetir y
comprobar el PR con `Closes #N`, el Status "In review" y el comentario del issue.

**Acceptance Scenarios**:

1. **Given** una rama de ticket a la que le falta `spec.md`, `plan.md` o `tasks.md` (o que
   los tiene sin commitear), **When** se ejecuta `/abrir-pr`, **Then** se detiene, indica
   qué falta y no sube la rama ni abre PR ni cambia el estado del ticket.
2. **Given** una rama de ticket con los tres artefactos commiteados, **When** se ejecuta
   `/abrir-pr`, **Then** se abre un PR de esa rama hacia `main` cuya descripción contiene
   `Closes #N`.
3. **Given** el PR abierto, **When** termina el comando, **Then** el ticket está en
   "In review" y el issue tiene un comentario con lo especificado, lo decidido y lo
   pendiente, con enlace al PR.

---

### User Story 3 - Avance del ticket visible en el issue (Priority: P2)

Mientras el ticket recorre el ciclo de Spec Kit (specify → clarify si quedan marcadores de
aclaración → plan → tasks → analyze → implement → converge si quedan brechas), el issue
recibe comentarios en los puntos de decisión: después de `/speckit-specify` y de
`/speckit-clarify` (lo especificado), después de `/speckit-plan` (lo decidido) y después
de `/speckit-analyze` (las inconsistencias encontradas y cómo se resolvieron). Un
evaluador que solo mire GitHub reconstruye qué se especificó, qué se decidió y qué quedó
pendiente, sin esperar a que se abra el PR.

**Why this priority**: es lo que hace auditable el ciclo; puede probarse con un solo ticket
y no depende de que el PR exista.

**Independent Test**: recorrer specify, plan y analyze de un ticket y comprobar que el
issue tiene los tres comentarios con su contenido.

**Acceptance Scenarios**:

1. **Given** un ticket arrancado, **When** se completa `/speckit-specify`, **Then** el
   issue recibe un comentario con el resumen de lo especificado: historias, requisitos
   clave y supuestos.
2. **Given** un ticket con el comentario de lo especificado, **When** se completa
   `/speckit-clarify`, **Then** ese mismo comentario se actualiza con las aclaraciones, sin
   crear otro.
3. **Given** un ticket especificado, **When** se completa `/speckit-plan`, **Then** el issue
   recibe un comentario con las decisiones del plan y su verificación de la constitución.
4. **Given** un ticket con tareas generadas, **When** se completa `/speckit-analyze`,
   **Then** el issue recibe un comentario con las inconsistencias encontradas y cómo se
   resolvieron (o la constancia de que no hubo).
5. **Given** la secuencia del ticket, **When** la spec tiene marcadores de aclaración o el
   implement deja brechas, **Then** la secuencia incluye `/speckit-clarify` o
   `/speckit-converge` respectivamente; si no, se omiten.

---

### User Story 4 - Cierre automático y verificación posterior al merge (Priority: P3)

Al fusionar el PR, `Closes #N` cierra el issue y los workflows nativos del Project
("Item closed" y "Pull request merged") pasan el issue y el PR a Done sin que nadie mueva
tarjetas. Después, se verifica que el ticket quedó en Done y el resultado se registra en un
comentario del issue, no en `tasks.md`: así ningún ticket deja cambios pendientes en una
rama ya fusionada. Si el ticket no quedó en Done, se reporta en vez de moverlo a mano.

**Why this priority**: el mecanismo de Done ya está activo en el Project; este ticket lo
documenta, lo verifica y corrige el problema observado en el ticket #1, donde una tarea
posterior al merge obligó a guardar un cambio fuera de la rama del ticket.

**Independent Test**: fusionar el PR de un ticket y comprobar, solo leyendo GitHub, que el
issue está cerrado, que el ítem está en Done y que el issue tiene el comentario de cierre;
comprobar que `tasks.md` del ticket no tiene ninguna tarea que deba ejecutarse después del
merge.

**Acceptance Scenarios**:

1. **Given** un PR con `Closes #N`, **When** se fusiona, **Then** el issue #N queda cerrado
   y en Done sin intervención manual.
2. **Given** el ticket fusionado, **When** se hace la verificación posterior al merge,
   **Then** el issue recibe un comentario de cierre con el estado verificado y ningún
   archivo del repositorio cambia.
3. **Given** el ticket fusionado que no quedó en Done, **When** se hace la verificación,
   **Then** se reporta la discrepancia a la persona del equipo y el ticket no se mueve a
   mano.
4. **Given** el `tasks.md` de cualquier ticket generado con este flujo, **When** se revisa,
   **Then** no contiene tareas que deban ejecutarse después del merge.

---

### Edge Cases

- No hay ningún ítem en Todo: la skill lo informa y no crea rama ni carpeta.
- El número indicado no existe, no está en el Project, está cerrado o no está en Todo (por
  ejemplo, ya en "In Progress"): la skill lo informa y se detiene sin cambiar su estado; no
  retoma un ticket en curso sin que la persona lo pida.
- Hay cambios sin commitear en el directorio de trabajo o `main` no puede actualizarse sin
  conflicto: la skill se detiene antes de crear la rama, sin mover el ticket.
- La rama `NNN-*` o la carpeta `specs/NNN-*` del ticket ya existe: la skill se detiene y lo
  informa en vez de sobrescribir.
- El MCP de GitHub no está conectado o falla: no se intenta mover el ticket por otra vía en
  silencio; se informa qué paso no se completó.
- Las opciones de Status del Project no coinciden con los nombres esperados ("Todo",
  "In Progress", "In review", "Done"): se informa y no se elige una opción parecida.
- `/abrir-pr` se ejecuta en `main` o en una rama sin el formato `NNN-nombre-corto`: se
  detiene.
- Ya existe un PR abierto para la rama: `/abrir-pr` no abre otro; informa el existente.
- La subida de la rama falla: no se abre PR ni se cambia el estado del ticket.
- El issue tiene varios ítems en el Project o está en otro Project: se usa el Project del
  repositorio, "Due Diligence - Pasarela Austral".

## Requirements *(mandatory)*

### Functional Requirements

**Arranque del ticket (skill `siguiente-ticket`)**

- **FR-001**: La skill DEBE tomar, sin argumento, el ítem del Project en Todo con el menor
  número de issue, y con argumento, el issue indicado.
- **FR-002**: La skill DEBE declarar las herramientas que puede usar (`allowed-tools`) y
  una pista de argumento (`argument-hint`).
- **FR-003**: La skill DEBE leer el Project y mover el ticket solo a través del MCP de
  GitHub, a la opción de Status "In Progress" con su nombre exacto.
- **FR-004**: La skill DEBE comentar en el issue el inicio del ticket, con la rama y la
  carpeta de specs.
- **FR-005**: La skill DEBE partir de `main` actualizado, crear la rama `NNN-nombre-corto`
  e invocar `/speckit-specify` con el cuerpo del issue como insumo y `--number N`, de modo
  que rama, carpeta `specs/NNN-*` y número de issue coincidan.
- **FR-006**: Ningún paso de la skill DEBE commitear en `main`.
- **FR-007**: La skill DEBE definir la secuencia del ticket: specify → clarify si quedan
  marcadores de aclaración → plan → tasks → analyze → implement → converge si quedan
  brechas.

**Avance en el issue**

- **FR-008**: Después de `/speckit-plan`, el issue DEBE recibir un comentario con lo
  decidido.
- **FR-009**: Después de `/speckit-analyze`, el issue DEBE recibir un comentario con las
  inconsistencias encontradas y cómo se resolvieron.
- **FR-022**: Después de `/speckit-specify`, el issue DEBE recibir un comentario con el
  resumen de lo especificado (historias, requisitos clave y supuestos). Si después se
  ejecuta `/speckit-clarify`, ese comentario DEBE actualizarse con las aclaraciones en
  lugar de publicar otro. (Se numera FR-022 para no renumerar los requisitos que ya citan
  el plan y sus artefactos.)

**Apertura del PR (comando `/abrir-pr`)**

- **FR-010**: El comando DEBE estar versionado en `.claude/commands/`.
- **FR-011**: El comando DEBE verificar que `specs/NNN-*/spec.md`, `plan.md` y `tasks.md`
  están commiteados en la rama del ticket y detenerse, indicando cuál falta, si no lo
  están.
- **FR-012**: El comando DEBE subir la rama y abrir el PR de esa rama hacia `main` con
  `Closes #N` en la descripción.
- **FR-013**: El comando DEBE mover el ticket a "In review" y comentar en el issue lo
  especificado, lo decidido y lo pendiente.
- **FR-014**: Si la verificación o la subida fallan, el comando NO DEBE abrir PR ni cambiar
  el estado del ticket.

**Cierre**

- **FR-015**: El paso a Done DEBE hacerlo el Project con sus workflows nativos ("Item
  closed" para el issue, "Pull request merged" para el PR), sin mover tarjetas a mano.
- **FR-016**: La decisión de FR-015 DEBE quedar documentada en `DECISIONES.md`.
- **FR-017**: La verificación posterior al merge (que el ticket quedó cerrado y en Done)
  DEBE registrarse en un comentario del issue y NO DEBE modificar archivos del repositorio.
  Si el ticket no quedó en Done, se reporta en vez de moverlo.
- **FR-018**: El flujo DEBE indicar que `tasks.md` contiene solo tareas que se completan
  antes del merge; la verificación posterior al merge no es una tarea de `tasks.md`.

**Transversales**

- **FR-019**: Todo cambio de Status de este flujo DEBE quedar acompañado de un comentario en
  el issue, de modo que el historial del issue explique cada transición.
- **FR-020**: Los comentarios y mensajes a la persona del equipo DEBEN estar en español.
- **FR-021**: Ante cualquier error de GitHub o de git, el flujo DEBE detenerse e informar
  qué paso no se completó, sin dejar el ticket en un estado que contradiga el avance real.

### Key Entities

- **Ticket**: issue de GitHub con número, cuerpo (insumo de la spec), estado abierto o
  cerrado y comentarios de avance.
- **Ítem del Project**: representación del ticket en "Due Diligence - Pasarela Austral",
  con el campo Status (Todo, In Progress, In review, Done).
- **Rama del ticket**: `NNN-nombre-corto`, creada desde `main`; NNN es el número del issue
  con tres dígitos.
- **Carpeta de specs del ticket**: `specs/NNN-*` con `spec.md`, `plan.md` y `tasks.md`.
- **Pull request del ticket**: de la rama del ticket hacia `main`, con `Closes #N`.
- **Comentario de avance**: comentario del issue en cada punto del ciclo (inicio,
  especificado, plan, analyze, PR, cierre).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Arrancar un ticket (selección, cambio a "In Progress", comentario de inicio,
  rama y spec) requiere una sola invocación de la persona del equipo.
- **SC-002**: En los tickets que usan este flujo, el 100 % de los cambios de Status (In
  Progress, In review, Done) ocurren sin mover tarjetas a mano.
- **SC-003**: Cada ticket cerrado con este flujo tiene en su issue al menos seis
  comentarios de avance: inicio, especificado, plan, analyze, apertura del PR y cierre.
- **SC-004**: Un evaluador que solo mira GitHub puede responder, para cualquier ticket
  cerrado, qué se especificó, qué se decidió, qué quedó pendiente y cuándo cambió de
  estado, sin abrir el repositorio local.
- **SC-005**: `/abrir-pr` se detiene en el 100 % de los casos en que falta o no está
  commiteado alguno de los tres artefactos del ticket.
- **SC-006**: Ningún ticket cerrado con este flujo deja cambios pendientes de commitear en
  su rama después del merge, y ningún commit entra en `main` sin PR.

## Assumptions

- El Project "Due Diligence - Pasarela Austral" ya tiene el campo Status con las opciones
  Todo, In Progress, In review y Done, y los workflows "Item closed" y "Pull request
  merged" activos (verificado en el ticket #1: el issue #1 pasó a Done al fusionar el
  PR #15).
- El MCP de GitHub con el toolset de projects está configurado (ticket #1) y `GITHUB_PAT`
  tiene los scopes `repo` y `project`.
- El backlog está numerado en orden de ejecución, así que el menor número en Todo es el
  siguiente ticket.
- La verificación posterior al merge se ejecuta en una sesión posterior al merge, por
  ejemplo al arrancar el ticket siguiente; el mecanismo concreto se decide en el plan.
- La revisión independiente previa al PR es del ticket #4; mientras no exista, aplica la
  transición del ticket #1 (subagente genérico de solo lectura en contexto separado).
- Las guardas con hooks (exigencia de spec previa, protección de secretos) son del ticket
  #3; este ticket no las implementa.
- El propio ticket #2 se construye con la transición descrita en #1.
