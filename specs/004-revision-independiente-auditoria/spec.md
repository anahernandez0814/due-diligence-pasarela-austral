# Especificación de la funcionalidad: Revisión independiente y auditoría de cumplimiento

**Rama**: `004-revision-independiente-auditoria`

**Creada**: 2026-10-16

**Estado**: Borrador

**Entrada**: Issue #4 de GitHub, "Revisión independiente y auditoría de cumplimiento".

## Escenarios de usuario y pruebas *(obligatorio)*

### Historia 1 - Revisión independiente del código (Prioridad: P1)

Quien desarrolla un ticket necesita que el cambio de su rama sea revisado por alguien que no
participó en escribirlo. La revisión corre en un contexto separado de la sesión que generó el
código, solo lee, y reporta hallazgos con su ubicación (archivo y línea), distinguiendo los
que bloquean el pull request de las sugerencias. Revisa calidad, errores y cumplimiento de la
especificación del ticket.

**Por qué esta prioridad**: es la mitad del valor del ticket y la exigencia directa del
principio X: nadie debe aprobar su propio código.

**Prueba independiente**: sobre una rama con un cambio que contiene un defecto evidente y
una desviación de la spec, lanzar la revisión y comprobar que reporta ambos con su
ubicación y los clasifica, sin modificar ningún archivo.

**Escenarios de aceptación**:

1. **Dado** una rama con cambios frente a `main`, **cuando** se lanza la revisión de código,
   **entonces** se obtiene un reporte con hallazgos bloqueantes y sugerencias por separado,
   cada uno con archivo y línea.
2. **Dado** una rama cuyo código contradice la `spec.md` del ticket, **cuando** se revisa,
   **entonces** la contradicción se reporta como bloqueante, citando el requisito.
3. **Dado** una rama sin defectos, **cuando** se revisa, **entonces** el reporte declara cero
   bloqueantes y puede incluir sugerencias.
4. **Dado** cualquier revisión, **cuando** termina, **entonces** el árbol de trabajo y el
   historial de git son idénticos a los de antes (los revisores no escriben ni ejecutan
   comandos).

---

### Historia 2 - Auditoría de las reglas de negocio (Prioridad: P1)

Quien abre el pull request necesita saber si las cinco reglas de negocio de la constitución
(principio I) están implementadas como se especificaron. La auditoría, también en un
contexto separado y de solo lectura, verifica cada regla contra la spec, el código y los
tests, y entrega la evidencia con archivo y línea. Una regla sin evidencia se reporta como no
verificada, nunca como cumplida.

**Por qué esta prioridad**: las reglas de negocio definen un due diligence válido; un cambio
que las rompe no debe llegar a `main`.

**Prueba independiente**: auditar una rama con una regla deliberadamente incumplida y
comprobar que esa regla sale como bloqueante, con evidencia, y que las demás salen con su
estado.

**Escenarios de aceptación**:

1. **Dado** una rama, **cuando** se lanza la auditoría, **entonces** el reporte trae las cinco
   reglas, cada una con su estado (cumple, incumple, no aplica a este cambio o no
   verificada) y su evidencia de archivo y línea.
2. **Dado** una regla que el cambio incumple, **cuando** se audita, **entonces** se reporta
   como bloqueante.
3. **Dado** un cambio que no toca ninguna regla de negocio (por ejemplo, solo configuración),
   **cuando** se audita, **entonces** las reglas figuran como "no aplica" con la razón, y no
   se bloquea.
4. **Dado** una regla que aplica al cambio (la spec del ticket la cita o el diff toca código
   que la implementa) y para la que no se encuentra evidencia en la spec, el código ni los
   tests, **cuando** se audita, **entonces** figura como "no verificada" y es bloqueante.
5. **Dado** una regla que la spec del ticket no cita y que el diff no toca, **cuando** se
   audita, **entonces** figura como "no aplica" con esa razón y no bloquea.

---

### Historia 3 - Veredicto consolidado al abrir el PR (Prioridad: P1)

Al abrir el pull request, el flujo de cierre del ticket ejecuta las dos revisiones, las
consolida en un solo veredicto (aprobado o con bloqueantes) y lo muestra a la persona. Si hay
bloqueantes, no se abre el PR. Si aprueba, el veredicto queda registrado para el commit
actual.

**Por qué esta prioridad**: sin consolidación, las dos revisiones serían opcionales y su
resultado no gobernaría la entrega.

**Prueba independiente**: con una rama aprobada, ejecutar el cierre y comprobar que se
registra el veredicto del commit; con una rama con un bloqueante, comprobar que no se abre el
PR ni se registra aprobación.

**Escenarios de aceptación**:

1. **Dado** que ambas revisiones terminan sin bloqueantes, **cuando** se consolida, **entonces**
   el veredicto es "aprobado" y queda registrado para el commit actual en un archivo que git
   no versiona.
2. **Dado** que alguna revisión reporta un bloqueante, **cuando** se consolida, **entonces** el
   veredicto es "con bloqueantes", se muestran los hallazgos y se registra igualmente, para
   dejar trazabilidad, sin que valga para abrir el PR.
3. **Dado** que una de las dos revisiones falla o no devuelve un reporte utilizable, **cuando**
   se consolida, **entonces** el veredicto no es "aprobado".
4. **Dado** un veredicto aprobado de un commit anterior, **cuando** se hace un commit nuevo,
   **entonces** ese veredicto deja de valer y hace falta revisar de nuevo.

---

### Historia 4 - Puerta mecánica contra PR sin revisión (Prioridad: P1)

Aunque la persona o el modelo intenten saltarse el flujo, crear un pull request sin un
veredicto aprobado para el commit actual queda bloqueado, tanto por la herramienta de
GitHub del proyecto como por la línea de comandos `gh pr create`. La regla se hace cumplir
con un hook, no con instrucciones (principio II).

**Por qué esta prioridad**: sin la puerta, la revisión es una sugerencia que cualquiera puede
omitir.

**Prueba independiente**: sin veredicto, intentar crear un PR por las dos vías y comprobar el
bloqueo con un mensaje que dice qué falta; con veredicto aprobado del commit actual,
comprobar que se permite.

**Escenarios de aceptación**:

1. **Dado** que no existe veredicto para el commit actual, **cuando** se intenta crear un PR con
   la herramienta de GitHub del proyecto, **entonces** se bloquea con un mensaje que indica
   ejecutar la revisión.
2. **Dado** el mismo estado, **cuando** se intenta `gh pr create` por terminal, **entonces** se
   bloquea igual.
3. **Dado** un veredicto "aprobado" para el commit actual, **cuando** se crea el PR por
   cualquiera de las dos vías, **entonces** se permite.
4. **Dado** un veredicto con bloqueantes o de otro commit, **cuando** se intenta crear el PR,
   **entonces** se bloquea.
5. **Dado** cualquier fallo interno de la guarda (archivo ilegible, formato inesperado),
   **cuando** se intenta crear un PR, **entonces** se bloquea (falla cerrada).
6. **Dado** un veredicto aprobado cuyo commit no está publicado en el remoto, o cuya rama
   remota tiene otros commits, **cuando** se intenta crear el PR, **entonces** se bloquea.
7. **Dado** que no hay veredicto aprobado, **cuando** se intenta crear un PR con `gh api` y
   método POST contra el recurso de pull requests, **entonces** se bloquea igual.

---

### Casos límite

- Rama sin cambios frente a `main`: la revisión lo declara y no hay nada que aprobar; no se
  registra veredicto aprobado.
- Diff muy grande: la revisión siempre recibe la lista de archivos cambiados con sus
  estadísticas, y el diff completo solo si cabe en un umbral. Si no cabe, lee los archivos de
  la lista con sus herramientas de lectura. Solo si no puede leer algún archivo de la lista
  declara que no cubrió el cambio, y entonces el veredicto no puede ser "aprobado".
- Commit aprobado que no es el último publicado de la rama (no se ha subido, o la rama remota
  tiene otros commits): el veredicto no vale y la puerta bloquea.
- Veredicto con bloqueantes: se registra para trazabilidad, pero la puerta solo acepta
  "aprobado".
- `gh api` con POST al recurso de pull requests crea un PR igual que `gh pr create`: se
  bloquea con el mismo criterio. Otras formas de crear un PR fuera de Claude Code (la web de
  GitHub, otro cliente) no pasan por la guarda y se declaran como residual.
- Archivo de veredicto manipulado a mano: el hook solo comprueba que exista un veredicto
  aprobado del commit actual; no puede saber quién lo escribió. Es un límite declarado, no
  un defecto.
- Commit nuevo tras la aprobación (incluso enmendado): el veredicto previo no sirve.
- Comandos parecidos a `gh pr create` que no crean un PR (`gh pr view`, `gh pr list`): no se
  bloquean.
- Creación del PR con `gh` envuelta en otro comando o en un shell anidado: se trata igual que
  la forma directa, con el mismo criterio de las demás guardas del proyecto.
- Veredicto con formato inesperado: se trata como inexistente.
- Los revisores no pueden corregir: si encuentran un problema, solo lo reportan.

## Requisitos *(obligatorio)*

### Requisitos funcionales

- **FR-001**: Debe existir un revisor de código que revisa el diff de la rama frente a la
  base de fusión con la rama principal actualizada del remoto (no frente al `main` local), en
  cuanto a calidad, errores y cumplimiento de la spec del ticket, y reporta cada hallazgo
  con su ubicación.
- **FR-002**: Debe existir un auditor de cumplimiento que verifica las cinco reglas de
  negocio de la constitución contra la spec, el código y los tests, con evidencia de archivo y
  línea.
- **FR-003**: Ni el revisor ni el auditor pueden escribir, editar ni ejecutar comandos: solo
  disponen de herramientas de lectura. Esto lo limita la configuración del rol, no solo la
  instrucción.
- **FR-004**: Cada revisión se ofrece como una skill propia que se ejecuta en un contexto
  separado de la sesión que generó el código, con herramientas permitidas explícitas y una
  pista del argumento que espera. Hay una skill por revisión, porque un subagente no puede
  lanzar a otro.
- **FR-005**: Cada revisión recibe siempre, como contexto de su propia skill, la lista de
  archivos cambiados con estadísticas y los documentos del ticket; recibe el diff completo
  solo si cabe en un umbral. Si no cabe, lee los archivos de la lista con sus herramientas de
  lectura. Solo no poder leer algún archivo de la lista impide la aprobación.
- **FR-006**: Cada reporte separa los hallazgos bloqueantes de las sugerencias, y cada
  hallazgo trae ubicación y razón.
- **FR-007**: El auditor informa por cada regla su estado (cumple, incumple, no aplica,
  no verificada) con evidencia; una regla sin evidencia nunca se reporta como cumplida. Una
  regla aplica al cambio si la spec del ticket la cita o si el diff toca código que la
  implementa. Si no aplica, figura como "no aplica" con esa razón; si aplica y no hay
  evidencia, es bloqueante.
- **FR-008**: El flujo de apertura del PR ejecuta ambas revisiones y consolida un veredicto:
  "aprobado" solo si ninguna tiene bloqueantes y ambas devolvieron un reporte utilizable;
  en cualquier otro caso, "con bloqueantes".
- **FR-009**: Con veredicto "con bloqueantes" no se abre el PR ni se cambia el estado del
  ticket; se muestran los hallazgos.
- **FR-010**: Cada veredicto, "aprobado" o "con bloqueantes", se registra para el commit
  actual en un archivo que git no versiona, con el identificador del commit, el veredicto y
  la fecha. La puerta solo acepta "aprobado".
- **FR-011**: Un veredicto solo vale para el commit para el que se registró, y solo si ese
  commit es también el último publicado de la rama: si no está publicado, o la rama remota
  tiene otros commits, no vale.
- **FR-012**: Un hook previo a la acción bloquea la creación de un PR, tanto por la
  herramienta de GitHub del proyecto como por `gh pr create` y `gh api` con POST al recurso
  de pull requests en terminal, si no existe un veredicto aprobado válido (FR-011) para el
  commit actual. El mensaje dice qué falta y cómo obtenerlo.
- **FR-013**: La guarda falla cerrada (como las demás del proyecto): ante cualquier error
  interno o veredicto ilegible, bloquea.
- **FR-014**: La guarda no bloquea comandos de `gh` que no crean un PR.
- **FR-015**: La guarda y la lógica de registro y lectura del veredicto tienen tests
  automáticos, junto al código, incluidos los casos de bloqueo y de permiso.
- **FR-016**: La configuración de la guarda se versiona en la configuración compartida del
  proyecto y funciona en Windows, macOS y Linux.
- **FR-017**: Los mensajes y reportes al usuario están en español.
- **FR-018**: El límite del mecanismo (el hook verifica que exista un veredicto aprobado del
  commit actual, no lo genera ni comprueba quién lo escribió) se declara en
  `DECISIONES.md`.
- **FR-019**: Esta funcionalidad reemplaza la revisión de transición que `/abrir-pr` tenía
  desde el ticket #2; no deben quedar dos revisiones paralelas.

### Entidades clave

- **Reporte de revisión**: hallazgos de una revisión, cada uno con severidad (bloqueante o
  sugerencia), ubicación y razón; para la auditoría, además el estado de cada regla y su
  evidencia.
- **Veredicto**: resultado consolidado (aprobado o con bloqueantes) ligado a un commit y a una
  fecha, guardado fuera del control de versiones. Se conservan los de bloqueantes para
  trazabilidad.

## Criterios de éxito *(obligatorio)*

### Resultados medibles

- **SC-001**: El 100 % de los intentos de crear un PR sin veredicto aprobado del commit actual
  se bloquean por las dos vías, y el 100 % de los que sí lo tienen se permiten.
- **SC-002**: Ningún revisor modifica archivos ni historial: tras cada revisión, el estado del
  repositorio es idéntico al previo.
- **SC-003**: En un cambio con un defecto y una regla de negocio incumplida sembrados, ambas
  revisiones los reportan como bloqueantes con su ubicación.
- **SC-004**: La comprobación de la puerta tarda menos de 1 segundo en uso normal.
- **SC-005**: Una persona que no conoce el código entiende a partir del reporte qué impide
  abrir el PR y dónde está cada problema.
- **SC-006**: Se cierra la desviación temporal del principio X declarada en #2 (revisión
  previa de transición) y se cumplen los criterios de aceptación del issue #4.

## Supuestos

- La puerta verifica la existencia del veredicto aprobado del commit actual; no puede
  garantizar que lo generó una revisión real. El límite se declara en `DECISIONES.md`.
- Las cinco reglas de negocio son las del principio I de la constitución; si cambian, la
  auditoría las toma de allí.
- Cuando todavía no hay código de producción, la auditoría marca las reglas como "no aplica"
  con la razón y no bloquea por ausencia.
- Las skills de revisión preparan como contexto la lista de archivos cambiados con
  estadísticas y, si cabe en un umbral, el diff completo; los diffs reales pueden pesar
  cientos de KB (el del PR #17 rondaba los 370 KB), así que el diff completo no es requisito.
  Los revisores no ejecutan comandos ni consultan git.
- El archivo de veredicto vive en una ruta ya excluida de git o que esta funcionalidad
  excluye.
- Dependencia: #2 (`/abrir-pr`) y las guardas de #3, cuya configuración se amplía con esta
  guarda.
- Corregir los hallazgos queda fuera: lo hace la persona, o la sesión de desarrollo, y se
  vuelve a revisar.
