# Especificación de la funcionalidad: Auditoría: reglas delegadas a otro ticket y uv.lock como referencia

**Rama**: `019-auditoria-reglas-delegadas`

**Creada**: 2026-10-17

**Estado**: Borrador

**Entrada**: Issue #19 de GitHub, "Auditoría: reglas delegadas a otro ticket y uv.lock como referencia".

## Escenarios de usuario y pruebas *(obligatorio)*

### Historia 1 - Una regla delegada a otro ticket no bloquea este ticket (Prioridad: P1)

Quien abre el PR de un ticket necesita que la auditoría de cumplimiento no lo bloquee por
reglas de negocio que la spec de ese ticket entrega, de forma explícita y con nombre, a otro
ticket. Hoy el auditor da por aplicable toda regla que la spec cita, aunque la cite
precisamente para decir que la cumple otro ticket, y la marca `no verificada`, que es
bloqueante. Eso ocurrió en el `/abrir-pr` del #5 (commit `d891cef`): I.1, I.2 e I.3 salieron
bloqueantes porque la spec del #5 las cita para delegarlas al #7 (FR-017 y la línea 161 de
esa spec). El título del #7 cubre las reglas 1, 2 y 3; la spec del #5 hoy solo nombra el
ticket para I.1 e I.2, y la corrección de esa línea se hace al volver al #5, no en este
ticket.

**Por qué esta prioridad**: sin esto, ningún ticket de infraestructura que deje las reglas a
tickets posteriores puede aprobarse, y el #5 queda detenido por un defecto de la puerta y no
por un defecto del cambio. Es el motivo del ticket.

**Prueba independiente**: sobre una copia desechable de la rama 005 con esta corrección y con
la línea 161 de su spec corregida para que diga "I.1, I.2 e I.3 … del ticket #7", lanzar la
auditoría de cumplimiento y comprobar que I.1, I.2 e I.3 salen `no aplica`, cada una con la
razón (delegada al ticket que la spec nombra), y que no aportan bloqueantes.

**Escenarios de aceptación**:

1. **Dado** una spec que cita una regla para delegarla y nombra el ticket responsable, y un
   cambio que no la contradice, **cuando** se audita, **entonces** la regla figura `no
   aplica` con la razón "delegada al ticket #N" y no cuenta como bloqueante.
2. **Dado** una spec que asigna la regla a este mismo ticket, **cuando** se audita,
   **entonces** la regla aplica y se verifica con evidencia, como hasta ahora.
3. **Dado** una spec que cita una regla sin asignarla a un ticket con su número (no la
   delega con nombre), **cuando** se audita, **entonces** la regla sigue aplicando: citar no
   basta para quedar exenta.
4. **Dado** una regla delegada y un cambio que la contradice o la debilita, **cuando** se
   audita, **entonces** la regla sale `incumple` y es bloqueante: delegar no autoriza a
   violarla.
5. **Dado** una regla delegada **con número de ticket**, **cuando** el cambio solo aporta
   datos o clasificación que la regla usa, pero no la hace cumplir, **entonces** sigue
   siendo `no aplica`.
6. **Dado** una regla delegada con número de ticket, **cuando** el cambio borra o debilita
   código o tests que ya la garantizaban, **entonces** la regla aplica y, sin evidencia
   vigente, es bloqueante: la delegación exime de implementar, no de conservar.

---

### Historia 2 - Un archivo generado no reduce la cobertura (Prioridad: P1)

Quien abre el PR necesita que las dos revisiones puedan declarar la cobertura completa
cuando leyeron todo lo que cuenta. El archivo de dependencias bloqueado (`uv.lock`) lo
genera la herramienta y es muy largo; hoy cuenta como archivo a leer "por secciones", y leer
solo una parte (60 líneas de unas 568 en el #5) dejó las dos revisiones con
`cobertura=incompleta`, lo que impide aprobar.

**Por qué esta prioridad**: junto con la historia 1 explica por qué las dos revisiones del
#5 salieron incompletas; con un archivo generado en el diff, ningún ticket que cambie
dependencias podría aprobarse.

**Prueba independiente**: en un cambio donde el único archivo no leído entero es `uv.lock`,
lanzar las dos revisiones y comprobar que la cobertura sale completa.

**Escenarios de aceptación**:

1. **Dado** un cambio que modifica `uv.lock`, **cuando** una revisión lo lee a medias o no
   lo lee, **entonces** la cobertura no se rebaja por ese archivo.
2. **Dado** un cambio donde otro archivo que sí cuenta se leyó a medias, **cuando** se
   revisa, **entonces** la cobertura sigue siendo `incompleta`: solo `uv.lock` queda
   exento.
3. **Dado** que `uv.lock` es referencia, **cuando** una revisión lo consulta, **entonces**
   puede contrastarlo con `pyproject.toml` por secciones o con búsquedas, como el resto de
   la referencia.

---

### Historia 3 - Los cuatro archivos de la puerta dicen lo mismo (Prioridad: P2)

Quien mantiene la puerta necesita que las reglas de cobertura y de aplicabilidad no
diverjan entre los dos revisores y sus dos skills. Hoy el bloque de cobertura está repetido
en cuatro archivos (los dos agentes y las dos skills); si se corrige uno y se olvida otro, la
revisión se comporta distinto según quién la lanza.

**Por qué esta prioridad**: protege la corrección de las dos historias anteriores; sin ella
el defecto reaparece por una copia desactualizada.

**Prueba independiente**: comparar el texto de los cuatro archivos y comprobar que el
bloque de cobertura, con `uv.lock` como referencia, es el mismo, y que la regla de
aplicabilidad es la misma en los dos del auditor.

**Escenarios de aceptación**:

1. **Dado** los dos agentes y las dos skills, **cuando** se compara el bloque "Qué cuenta
   para la cobertura", **entonces** es idéntico y lista `uv.lock` entre la referencia.
2. **Dado** el agente y la skill del auditor, **cuando** se compara su regla de cuándo
   aplica una regla, **entonces** dicen lo mismo, incluida la excepción de la regla
   delegada y su salvedad.

---

### Casos límite

- **Delegación sin número de ticket** ("lo cubrirá otro ticket", sin número): no cuenta como
  delegada; la regla sigue aplicando. Tampoco prevalece sobre el código que solo aporta datos
  o clasificación: sin número, no hay delegación.
- **Delegación a un ticket que no existe en el repositorio o en el Project**: el auditor no lo
  verifica; la spec nombra el ticket y eso basta. Comprobarlo queda fuera del alcance.
- **Regla delegada en una parte y asignada en otra**: si la spec asigna a este ticket algún
  aspecto de la regla (por ejemplo, la clasificación) y delega otro (su aplicación), aplica
  solo el aspecto asignado; el aspecto delegado es `no aplica` con su razón.
- **Cambio que contradice una regla delegada** (por ejemplo, un código que habilita
  automáticamente una categoría de alto riesgo): bloqueante, aunque la spec la delegue.
- **Cambio sin código de producción ni tests de las reglas**: las cinco `no aplica`, como
  hasta ahora; la nueva excepción no cambia ese caso.
- **Cambio que borra o debilita el código o el test de cualquier regla, delegada o no**: la
  regla aplica y, sin evidencia vigente en el código y en los tests, es `no verificada` y
  bloqueante. La delegación exime de implementar la regla, no de conservar lo que ya la
  garantiza.
- **`uv.lock` ausente del cambio**: no hay efecto.
- **`uv.lock` el único archivo del cambio**: la cobertura queda completa; no hay nada que
  cuente para leer, y eso no es un cambio vacío.

## Requisitos *(obligatorio)*

### Requisitos funcionales

- **FR-001**: La regla de cuándo aplica una regla de negocio del principio I DEBE decir que
  aplica si la spec del ticket asigna su cumplimiento a este ticket o si el diff toca código o
  tests que la implementan o la prueban. Citarla no basta.
- **FR-002**: Si la spec del ticket cita una regla para delegarla y nombra el ticket
  responsable **con su número** (`#N`), la regla DEBE salir `no aplica` con esa razón,
  indicando el ticket nombrado, y no aporta bloqueantes. La delegación prevalece incluso
  sobre el código del cambio que solo aporta datos o clasificación que la regla usa, pero
  únicamente si consta el número del ticket.
- **FR-003**: La excepción de FR-002 NO DEBE aplicar si el diff contradice o debilita la
  regla: entonces la regla sale `incumple` y es bloqueante.
- **FR-004**: Una spec que cita una regla sin nombrar con número un ticket responsable NO
  DEBE quedar exenta; la regla sigue aplicando.
- **FR-005**: La regla de aplicabilidad de FR-001 a FR-004 DEBE estar escrita igual en el
  agente `auditor-cumplimiento` y en la skill `auditar-cumplimiento`.
- **FR-006**: `uv.lock` DEBE figurar entre los archivos de referencia, que no cuentan para la
  cobertura, en los cuatro archivos de la puerta: los agentes `revisor-codigo` y
  `auditor-cumplimiento` y las skills `revisar-codigo` y `auditar-cumplimiento`.
- **FR-007**: El texto de cobertura DEBE dejar de pedir que `uv.lock` se lea por secciones
  como archivo que cuenta; el resto de las reglas de cobertura (archivos que cuentan,
  lectura a medias, contexto incompleto, lista agrupada) NO DEBE cambiar.
- **FR-008**: El bloque "Qué cuenta para la cobertura" DEBE ser idéntico en los cuatro
  archivos.
- **FR-009**: El cambio NO DEBE modificar `veredicto.py`, `guarda_pr.py` ni
  `preparar_revision.py`, ni sus tests.
- **FR-010**: Los tests existentes DEBEN seguir en verde, en particular los que comprueban
  la estructura de los agentes y de las skills (herramientas de solo lectura, `agent:`,
  `allowed-tools`).
- **FR-011**: Una regla delegada que el cambio contradice DEBE reportarse con ubicación y
  razón, como cualquier otro bloqueante.
- **FR-012**: Si el cambio borra o debilita el código o el test de cualquier regla, delegada
  o no, la regla DEBE aplicar y, sin evidencia vigente en el código y en los tests, ser
  `no verificada` y bloqueante. La delegación exime de implementar la regla, no de conservar
  lo que ya la garantiza. Esto se conserva de la regla actual de #4 y la delegación no lo
  relaja.
- **FR-013**: Un test automático DEBE comparar el bloque "Qué cuenta para la cobertura" de
  los cuatro archivos de la puerta y la regla de aplicabilidad del agente y de la skill del
  auditor, y DEBE fallar si difieren. Es el mecanismo que garantiza FR-005 y FR-008: la
  igualdad no depende de que alguien recuerde actualizar todas las copias.

### Entidades clave

- **Regla de negocio**: cada una de las cinco del principio I de la constitución, con su
  estado en la auditoría: `cumple`, `incumple`, `no aplica` o `no verificada`.
- **Delegación**: constancia en la spec del ticket de que una regla la cumple otro ticket,
  con el número de ese ticket. Es lo que convierte "citada" en `no aplica`.
- **Archivo de referencia**: archivo que la revisión consulta para contrastar y que no
  cuenta para la cobertura.
- **Archivos de la puerta**: los dos agentes y las dos skills de revisión, que deben decir
  lo mismo en lo que comparten.

## Criterios de éxito *(obligatorio)*

### Resultados medibles

- **SC-001**: En una copia de la rama 005 con esta corrección y con la línea 161 de su spec
  corregida a "I.1, I.2 e I.3 … del ticket #7", la auditoría reporta I.1, I.2 e I.3 como `no
  aplica`, cada una con su razón, y esas tres reglas aportan 0 bloqueantes. La corrección real
  de la rama 005 se hace al volver al #5.
- **SC-002**: En un cambio sembrado que contradice una regla que su spec delega, la
  auditoría reporta al menos un bloqueante con su ubicación (100 % de los casos probados).
- **SC-003**: En un cambio donde el único archivo no leído entero es `uv.lock`, las dos
  revisiones pueden declarar la cobertura completa.
- **SC-004**: La diferencia entre los bloques de cobertura de los cuatro archivos es de 0
  líneas, y entre la regla de aplicabilidad del agente y de la skill del auditor, de 0 líneas;
  y lo verifica un test automático (FR-013), no una lectura.
- **SC-008**: Un cambio sembrado que borra el código o el test de una regla (delegada o no)
  da un bloqueante en el 100 % de los casos probados.
- **SC-005**: El diff del ticket no toca ninguno de los tres archivos que quedan fuera del
  alcance, ni sus tests.
- **SC-006**: La suite de pruebas del repositorio sigue en verde tras el cambio.
- **SC-007**: La puerta del #5 deja de bloquearse por las reglas I.1 a I.3: el siguiente
  `/abrir-pr` del #5 puede llegar a un veredicto distinto de "con bloqueantes" por ese motivo
  (el veredicto final depende de lo que encuentren las revisiones).

## Supuestos

- La delegación debe constar **en la spec del ticket** con el número del ticket responsable;
  el auditor no consulta GitHub ni verifica que ese ticket exista o cubra la regla.
- Cuando una spec delega una regla, la **delegación prevalece** sobre "el diff toca código
  que la implementa" si ese código solo aporta datos o clasificación que la regla usa, pero no
  la hace cumplir, **y únicamente si la spec nombra el ticket con su número** (FR-002). Es lo
  que exige el criterio del #5: el servidor clasifica el riesgo de la categoría (I.3) y aun
  así I.3 sale `no aplica`. Decisión confirmada por la analista con esa condición.
- El título del #7 cubre las reglas 1, 2 y 3. La spec del #5 solo nombra el ticket para I.1 e
  I.2 (su línea 161); corregirla para que diga "I.1, I.2 e I.3 … del ticket #7" es tarea del
  #5, y este ticket solo la usa en la copia desechable que valida SC-001.
- El "#10" que aparece en el cuerpo del issue #19 como segundo ticket delegado era un error;
  la delegación es solo al #7.
- La constitución no cambia: el principio I y el principio II siguen igual. Esta corrección
  afina cuándo se audita cada regla, no qué dice cada regla.
- Quien delega asume el riesgo de la delegación: la regla queda verificada cuando se audita
  el ticket que la recibe. El comentario de la auditoría del #5 sugiere, además, dejar por
  escrito la desviación en el plan; es una buena práctica de ese ticket, no un requisito de
  este.
- `preparar_revision.py` no marca `uv.lock` como referencia en la lista de archivos del
  contexto, y no se modifica; la regla vive en el texto de los cuatro archivos, que es lo que
  lee cada revisión.
- La validación del criterio sobre la rama 005 se hace en una copia desechable fuera del
  repositorio, como en #4, sin tocar la rama 005 ni su veredicto con bloqueantes registrado.
- La validación es solo en Windows, como en #3 y #4.
- Depende de #4 (lo corrige) y desbloquea #5.
