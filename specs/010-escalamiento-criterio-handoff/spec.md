# Feature Specification: Escalamiento con criterio, handoff y ambigüedad

**Feature Branch**: `010-escalamiento-criterio-handoff`

**Created**: 2026-10-18

**Status**: Draft

**Input**: Issue #10 de GitHub: "Escalamiento con criterio, handoff y ambigüedad". Que el sistema escale solo cuando corresponde, entregue al oficial un resumen que se entienda sin la conversación y pida el identificador cuando el comercio es ambiguo. Incluye el contexto heredado: los dos pendientes del #7 que recoge el comentario del #10 (la categoría consultada la elige el modelo; el `Stop` impide pedir el identificador y actúa en cualquier fin de turno), la sección «Lo pendiente» del cierre del #9 (riesgos residuales 1, 2 y 5 y desviaciones D3 y D7) y el riesgo residual 7 del #8 (la guía «no lo repitas» puede impedir volver a pedir listas tras resolver una ambigüedad).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Escalar cuando corresponde y solo entonces (Priority: P1)

El analista pide el due diligence de un comercio. Si hay una coincidencia en listas restrictivas, del comercio o de su representante legal, o la categoría es de alto riesgo, el caso va a un oficial de cumplimiento. Si el comercio es de bajo riesgo y no tiene ningún hallazgo, el caso no se escala y recibe la recomendación de habilitar.

**Why this priority**: es el comportamiento 10 del enunciado, el principio V de la constitución y los casos de prueba (a) y (b). Escalar de más satura al oficial; escalar de menos deja pasar riesgo.

**Independent Test**: sin llamar al modelo, con un coordinador simulado, el comercio de alto riesgo del ejemplo (Tienda Verde SAS) termina escalado y con un informe `decide_cumplimiento`; el comercio de bajo riesgo sin hallazgos termina con un informe `habilitar` y sin escalamiento; y un intento de escalar el de bajo riesgo se rechaza con su motivo.

**Acceptance Scenarios**:

1. **Given** el comercio de alto riesgo del ejemplo, identificado, sin coincidencias en listas, **When** el coordinador termina el due diligence, **Then** el caso queda escalado a un oficial con la causa «categoría de alto riesgo» y el informe registrado lleva `decide_cumplimiento` (caso de prueba a).
2. **Given** un comercio de bajo riesgo sin hallazgos comprobado (FR-002: los cuatro frentes cubiertos, sin coincidencias en listas, la categoría determinada y no alta, sin menciones en noticias, sin conflictos y sin sello), **When** el coordinador termina el due diligence, **Then** no hay escalamiento y el informe registrado lleva `habilitar` (caso de prueba b).
3. **Given** ese mismo comercio de bajo riesgo sin hallazgos comprobado, **When** el coordinador intenta escalarlo, **Then** el escalamiento se rechaza con un motivo que dice que el caso no tiene causa de escalamiento, y no se guarda nada.
4. **Given** un comercio cuyo representante legal tiene una coincidencia en listas, **When** el coordinador termina, **Then** el caso queda escalado con la causa «coincidencia del representante legal en listas restrictivas», como desde el #7.
5. **Given** un caso sin causas de escalamiento pero con algún frente sin cubrir (por ejemplo, noticias o el registro caídos) o con la categoría no determinada, **When** el coordinador decide escalarlo, **Then** el escalamiento se admite pero el cierre no lo exige: el caso no es de bajo riesgo sin hallazgos comprobado y llevarlo al oficial es una salida segura.
6. **Given** un caso sin escalamiento vigente para el comercio actual, **When** el coordinador registra el informe con `decide_cumplimiento`, **Then** el informe se rechaza con un motivo que dice que el oficial solo decide un caso que le llegó escalado (riesgo residual 2 del #9).
7. **Given** un comercio de bajo riesgo, con las listas sin coincidencias y una mención en noticias, **When** el coordinador decide escalarlo, **Then** el escalamiento se admite (no se rechaza), porque el caso no es de bajo riesgo sin hallazgos comprobado; **And** si no lo escala, el cierre no se lo exige, porque una mención en noticias no es una coincidencia en listas (principio IV).
8. **Given** un comercio de bajo riesgo con un conflicto entre fuentes registrales (caso g), **When** el coordinador decide escalarlo, **Then** el escalamiento se admite y el cierre no lo exige.

---

### User Story 2 - Un resumen al oficial que se entiende sin la conversación (Priority: P1)

Cuando el caso se escala, el oficial de cumplimiento recibe un resumen autosuficiente: el comercio, los hallazgos de cada frente con su fuente y su fecha, la cobertura alcanzada, la causa del escalamiento y una acción recomendada. Si al resumen le falta alguno de los cinco campos, o una afirmación no tiene fuente, el escalamiento se rechaza con un motivo que nombra todo lo que falta, y el coordinador tiene que corregirlo.

**Why this priority**: es el comportamiento 11 del enunciado, el principio V («el resumen al oficial DEBE ser autosuficiente») y el cuarto criterio de aceptación del issue. El oficial no tiene acceso a la conversación.

**Independent Test**: sin llamar al modelo, se intenta escalar con un resumen al que le falta cada uno de los cinco campos, con una afirmación sin fuente y con uno completo; los incompletos se rechazan nombrando lo que falta y el completo queda guardado con el comercio, la cobertura y la causa calculados por el código.

**Acceptance Scenarios**:

1. **Given** un resumen al que le falta el comercio, los hallazgos, la cobertura, la causa o la acción recomendada, **When** se intenta escalar, **Then** se rechaza con un error estructurado que nombra el campo que falta y no se guarda nada.
2. **Given** un resumen al que le faltan varios campos, **When** se intenta escalar, **Then** el motivo los nombra todos, no solo el primero.
3. **Given** un resumen con una afirmación sin fuente, sin fecha, con una fecha inválida o con una fuente que el caso no consultó para ese frente, **When** se intenta escalar, **Then** se rechaza con el mismo tipo de motivo que el informe del #9.
4. **Given** un resumen completo en el que el coordinador declara otro comercio, otra cobertura u otra causa, **When** se escala, **Then** lo que queda guardado es el comercio, la cobertura y la causa calculados por el código; las afirmaciones y la acción recomendada son las del coordinador.
5. **Given** un comercio cuyas dos fuentes registrales se contradicen en un dato (caso g) y que además se escala, **When** se guarda el resumen, **Then** incluye los conflictos calculados por el código, con los dos valores y sus fuentes, como el informe.
6. **Given** un resumen guardado, **When** lo lee alguien sin acceso a la conversación, **Then** puede responder sin otra información qué comercio es, qué se encontró en cada frente y de dónde, qué frentes no se cubrieron y por qué, por qué se escaló y qué se recomienda hacer.
7. **Given** un resumen rechazado, **When** el coordinador lo corrige y vuelve a escalar en el mismo caso, **Then** el escalamiento se admite y cuenta para el cierre.

---

### User Story 3 - Ante comercios parecidos, pedir el identificador y seguir en el mismo caso (Priority: P1)

Si el registro mercantil devuelve varios comercios con nombres parecidos, el coordinador no elige uno: muestra al analista las coincidencias y le pide el identificador. Su turno termina ahí sin que el cierre le exija escalar ni registrar el informe, aunque la categoría sea de alto riesgo. Cuando el analista responde con el identificador, el due diligence continúa en el mismo caso: solo entonces se consultan las listas restrictivas, y los frentes que se consultaron con el nombre ambiguo se vuelven a delegar con el comercio identificado.

**Why this priority**: es el comportamiento 9 del enunciado, el principio V («el coordinador DEBE pedir el identificador al analista en vez de elegir»), el caso de prueba (d) y el pendiente 2 del #7: hoy el cierre trata cada fin de turno como el fin del caso y obliga a escalar un comercio sin identificar.

**Independent Test**: sin llamar al modelo, con un coordinador simulado y los dos comercios de nombre casi idéntico de los datos ficticios, el primer turno termina pidiendo el identificador, sin consultas de listas, sin escalamiento y sin informe; el segundo turno, con el identificador, identifica al comercio, vuelve a delegar noticias, consulta listas y termina con el informe. Con una categoría de alto riesgo, el primer turno termina igual y el escalamiento llega en el segundo.

**Acceptance Scenarios**:

1. **Given** una solicitud cuyo nombre coincide con dos comercios del registro, **When** el coordinador termina su turno pidiendo el identificador, **Then** el cierre lo permite sin exigir escalamiento ni informe, el caso queda «esperando al analista» con un evento que lo dice, y no figura como completo (caso de prueba d).
2. **Given** el mismo caso, **When** se revisan las consultas, **Then** no hay ninguna consulta de listas restrictivas, y un intento de consultarlas se bloquea como desde el #7 (caso de prueba e).
3. **Given** el mismo caso con una categoría de alto riesgo, **When** el coordinador termina su turno pidiendo el identificador, **Then** el cierre lo permite igual; el escalamiento queda pendiente para cuando el comercio esté identificado.
4. **Given** el caso esperando el identificador, **When** el coordinador intenta escalar o registrar el informe sin el comercio identificado, **Then** se rechaza con un motivo que dice que primero hace falta el identificador.
5. **Given** el caso esperando al analista, **When** el analista responde con el identificador de uno de los comercios, **Then** el due diligence continúa en el mismo caso: la categoría ya consultada se conserva, el registro identifica al comercio y solo entonces se consultan listas del comercio y de su representante legal.
6. **Given** la solicitud «Almacén Mirador SAS», con noticias consultadas en el primer turno con ese nombre, **When** el analista responde `CO-AM-0005` y el registro identifica ese comercio, **Then** noticias deja de contar como cubierto para él, el coordinador vuelve a delegar noticias con el comercio identificado y la noticia N-0001 aparece en el resultado; el informe no puede declarar noticias cubierto sin menciones con la consulta del primer turno.
7. **Given** el segundo turno, **When** el coordinador termina, **Then** el cierre exige lo de siempre: el escalamiento si hay causas y después el informe vigente.
8. **Given** una solicitud cuyo nombre no coincide con ningún comercio, **When** el coordinador termina su turno pidiendo al analista que revise el nombre, **Then** el cierre lo permite sin escalamiento ni informe y el caso queda esperando al analista (decisión (a) del #9).
9. **Given** el caso esperando al analista, **When** el analista responde con un identificador que el registro tampoco encuentra o que vuelve a ser ambiguo, **Then** el caso sigue esperando al analista y no se consultan listas.
10. **Given** un primer turno en el que la delegación de listas se rechazó por falta de identificación, **When** en el segundo turno el comercio queda identificado, **Then** el coordinador vuelve a delegar listas: ese rechazo ya no vale (riesgo residual 7 del #8).

---

### User Story 4 - Que el cierre distinga esperar al analista de cerrar el caso (Priority: P2)

El cierre del caso solo permite terminar un turno sin escalamiento ni informe cuando el código puede comprobar que el coordinador está esperando un dato del analista que hace falta para seguir: el identificador ante varias coincidencias, un nombre válido cuando el registro no encontró ninguno, o la categoría cuando la que se intentó delegar no estaba en los mensajes del analista. En cualquier otro fin de turno con el comercio identificado, el cierre exige lo de siempre.

**Why this priority**: resuelve el riesgo residual 5 del #9 y la limitación fijada con un test en ese ticket, que el #10 debe cambiar a sabiendas. Es P2 porque las esperas del caso (d) ya las cubre la US3; esta historia fija qué no es una espera.

**Independent Test**: sin llamar al modelo, se recorren los estados del registro (sin delegar, en curso, varias coincidencias, ninguna coincidencia, comercio identificado, caído) combinados con los de la categoría (con resultado, sin delegar, última delegación bloqueada por I.3 sin resultado) y se comprueba en cuáles el cierre admite esperar al analista; el test del #9 que fijaba la limitación cambia a sabiendas.

**Acceptance Scenarios**:

1. **Given** el comercio identificado y la categoría con resultado, **When** el coordinador termina su turno con una pregunta al analista sin escalar ni registrar el informe, **Then** el cierre exige el escalamiento (si hay causas) y el informe, como en el #9: no hay un dato que el código sepa que falta.
2. **Given** el registro que devolvió varias coincidencias o ninguna, **When** el coordinador termina su turno, **Then** es una espera del analista y el cierre la permite.
3. **Given** el registro caído, **When** el coordinador termina su turno, **Then** no es una espera del analista: el cierre exige reintentar el registro o el informe, como en el #9.
4. **Given** el comercio identificado y la última delegación de categoría bloqueada por I.3 sin ningún resultado de categoría en el caso, **When** el coordinador termina su turno preguntando la categoría al analista, **Then** es una espera del analista y el cierre la permite; cuando el analista la da y la categoría se consulta, el cierre exige lo de siempre.
5. **Given** las fuentes registrales que difieren en el nombre o en el representante legal del comercio (D3 del #9), **When** el coordinador termina su turno, **Then** no es una espera del analista: el cierre se evalúa como en el #9.
6. **Given** una espera del analista, **When** termina el turno, **Then** no cuenta como cierre impedido ni consume las devoluciones del cierre, y el caso no queda marcado como terminado sin escalar ni sin informe.

---

### User Story 5 - Que la categoría consultada sea la que dio el analista (Priority: P2)

El nivel de riesgo depende de la categoría que se consulta, y hoy la elige el coordinador. Con este ticket, el código comprueba que la categoría que se delega aparece en los mensajes del analista; si no aparece, la delegación se bloquea y el coordinador tiene que pedirle la categoría al analista, en una espera que el cierre admite (US4-4).

**Why this priority**: es el pendiente 1 del #7 (riesgo residual de I.3): si el coordinador consulta una categoría de bajo riesgo para un comercio de alto riesgo, hoy el informe acepta `habilitar`. Es P2 porque el caso de prueba (a) ya escala con el modelo real; esto cierra el hueco cuando el modelo se equivoca.

**Independent Test**: sin llamar al modelo, con la solicitud del ejemplo («…suplementos dietarios…»), una delegación de la categoría «suplementos dietarios» se permite y una de «ropa» se bloquea con su motivo; con la categoría que el analista da en un segundo mensaje, se permite.

**Acceptance Scenarios**:

1. **Given** una solicitud que menciona la categoría del comercio, **When** el coordinador delega el frente de categoría con esa categoría, **Then** la delegación se permite.
2. **Given** la misma solicitud, **When** el coordinador delega una categoría que no aparece en ningún mensaje del analista, **Then** la delegación se bloquea con un motivo que pide usar la categoría que dio el analista o preguntársela, y deja un evento de bloqueo.
3. **Given** una solicitud sin categoría, **When** el analista la da en un mensaje posterior del mismo caso, **Then** la delegación con esa categoría se permite.
4. **Given** la categoría escrita con otras mayúsculas, tildes o espacios en la solicitud, **When** se compara, **Then** cuenta como la misma, con la normalización de siempre.
5. **Given** la categoría escrita en singular en la solicitud («suplemento dietario») y delegada en plural («suplementos dietarios»), **When** se compara, **Then** no cuenta como la misma y la delegación se bloquea: la normalización no cubre plurales (riesgo declarado).

---

### Edge Cases

- **El analista responde con un identificador que no estaba entre las coincidencias**: es su decisión; se consulta el registro con ese identificador y rige lo que devuelva.
- **El analista responde sin identificador** (por ejemplo, «el de Medellín»): el coordinador no elige con ese dato; vuelve a pedir el identificador y el caso sigue esperando.
- **Varias coincidencias y categoría de alto riesgo**: el turno termina pidiendo el identificador; la categoría consultada sigue en el caso y, cuando el comercio quede identificado, el cierre exige el escalamiento.
- **Frente consultado con el nombre ambiguo**: tras identificar al comercio, noticias (y cualquier frente que dependa del nombre del comercio) no cuenta como cubierto para él hasta que se vuelva a delegar con el comercio identificado; la categoría no depende del comercio y se conserva.
- **Fuentes registrales que difieren en el nombre o el representante legal** (D3 del #9): no es una espera del analista, porque no hay datos ficticios con ese caso y dejaría el caso sin salida. Sigue como desviación declarada del #9: el comercio no queda identificado y el cierre se evalúa como en el #9.
- **Coincidencia en listas y alto riesgo a la vez**: un solo escalamiento con las dos causas.
- **Una causa nueva después de escalar** (por ejemplo, una coincidencia que aparece al reintentar listas): el escalamiento anterior no la cubre y hay que escalar de nuevo, como desde el #7.
- **Escalar dos veces sin causa nueva**: se admite y no cambia nada para el cierre; el plan decide si deja un evento distinto.
- **Fallo de un hook al validar o completar el resumen al oficial**: el escalamiento sale igual, con textos fijos que declaran lo que no se pudo calcular, y el caso queda sellado, como el informe mínimo del #9. Escalar sigue siendo la salida segura.
- **Caso sellado por un fallo de hook sin otras causas**: el escalamiento se admite (el sello es causa desde el #9).
- **Caso sellado por un fallo de hook mientras espera el identificador o un nombre válido**: escalar se admite aunque el comercio no esté identificado, porque es la salida segura (excepción de FR-016, FR-012), y después se admite el informe mínimo del #9 (`decide_cumplimiento`, con textos fijos). El caso no figura como completo.
- **Registro caído y sin otras causas**: el coordinador puede escalar (US1-5) y después registrar `decide_cumplimiento`, o registrar `no_habilitar` sin escalar; `habilitar` sigue bloqueado.
- **El analista cambia de comercio en un mensaje posterior**: rige el comercio del último registro; lo anterior deja de estar vigente como en el #9, y el escalamiento anterior no cuenta para el comercio nuevo, ni para cubrir sus causas ni para admitir `decide_cumplimiento` (FR-004).
- **Una solicitud que menciona varias categorías** (por ejemplo, «no vende apuestas, vende ropa»): las dos aparecen en el mensaje y el código no puede saber cuál es la del comercio. Queda como riesgo declarado; el plan decide si una categoría de alto riesgo mencionada exige algo más.
- **Mensaje del analista sin caso previo que esperara respuesta**: es un mensaje más del mismo caso; el coordinador lo atiende con el estado que ya tiene.

## Requirements *(mandatory)*

### Functional Requirements

**Escalamiento con criterio (US1)**

- **FR-001**: Un caso DEBE exigir escalamiento si, y solo si, tiene una causa vigente: coincidencia del comercio o del representante legal en listas restrictivas, categoría de alto riesgo o el sello de fallo de hook (#7 y #9). Una mención en noticias o un conflicto entre fuentes no es causa.
- **FR-002**: Un intento de escalar un caso **de bajo riesgo sin hallazgos comprobado** DEBE rechazarse con un motivo. Lo es solo si se cumplen todas estas condiciones:
  - los cuatro frentes están cubiertos para el comercio identificado;
  - las listas del comercio y de su representante legal se consultaron sin coincidencias;
  - la categoría está determinada y no es de alto riesgo;
  - noticias no devolvió ninguna mención;
  - no hay conflictos entre fuentes;
  - no hay sello de fallo de hook.

  Lo DEBE hacer cumplir el código, en el mismo punto que hoy completa la cobertura del escalamiento.
- **FR-003**: En cualquier otro caso sin causas, el escalamiento DEBE admitirse pero el cierre NO DEBE exigirlo. Por ejemplo: un frente sin cubrir (noticias o el registro caídos, que dejan la cobertura incompleta), la categoría no determinada, una mención en noticias o un conflicto entre fuentes. Es una salida segura cuando el código no puede comprobar el bajo riesgo sin hallazgos.
- **FR-004**: El informe con `decide_cumplimiento` DEBE exigir un escalamiento vigente para el comercio actual: un escalamiento hecho para otro comercio del mismo caso (si el analista cambió de comercio) no cuenta. Sin él, el informe se rechaza con un motivo. Las demás reglas del informe del #7 y del #9 no cambian.
- **FR-005**: El comercio de bajo riesgo sin hallazgos DEBE poder terminar con `habilitar` y sin escalamiento; ninguna regla nueva lo impide (caso de prueba b).

**Resumen al oficial (US2)**

- **FR-006**: El resumen de `escalar_a_cumplimiento` DEBE tener cinco campos obligatorios: comercio, hallazgos por frente, cobertura alcanzada, causa del escalamiento y acción recomendada. DEBE estar escrito como esquema verificable por código, no solo descrito en un prompt.
- **FR-007**: Un resumen al que le falte alguno de los cinco campos DEBE rechazarse con un error estructurado (constitución IV) que nombre **todos** los que faltan, y DEBE permitir que el coordinador corrija y vuelva a escalar en el mismo caso. Un resumen inválido NUNCA queda guardado, ni siquiera en parte.
- **FR-008**: Los hallazgos del resumen DEBEN seguir el mismo esquema de afirmaciones del informe del #9: cada afirmación con texto, fuente y fecha válida, la fuente consultada para ese frente (FR-027) y al menos una afirmación por frente cubierto.
- **FR-009**: El comercio, la cobertura y la causa del resumen DEBE ponerlos el código, como el comercio, la cobertura y los conflictos del informe del #9: si el coordinador declara otros, prevalecen los del código. La causa usa las etiquetas fijas de cada causa vigente, sin nombres ni identificadores. Si el caso no tiene causas (FR-003), la causa lo declara con un texto fijo que dice por qué se lleva al oficial (por ejemplo, la cobertura incompleta).
- **FR-010**: El resumen guardado DEBE incluir también los conflictos entre fuentes calculados por el código, para que el oficial vea los dos valores con su origen (I.4).
- **FR-011**: La acción recomendada la DEBE redactar el coordinador; es un texto no vacío dirigido al oficial.
- **FR-012**: Si falla un hook al validar o completar el resumen, el escalamiento NO DEBE denegarse: sale con textos fijos del código que declaran lo que no se pudo calcular y el caso queda sellado (#8, #9).

**Ambigüedad y continuación del caso (US3, US4)**

- **FR-013**: El caso DEBE poder continuar con un mensaje nuevo del analista conservando su estado: los resultados de los frentes, las consultas, las causas, los escalamientos, los informes y los eventos. Ningún dato del turno anterior se pierde ni se recalcula sin delegar; lo que deja de valer para el comercio identificado lo fija FR-027.
- **FR-014**: El código DEBE reconocer como **espera del analista** solo estos fines de turno:
  - el comercio no está identificado porque el registro respondió con varias coincidencias;
  - el comercio no está identificado porque el registro respondió sin ninguna coincidencia;
  - la última delegación de categoría la bloqueó la regla I.3 (FR-020) y el caso no tiene ningún resultado de categoría.

  En una espera del analista, el cierre DEBE permitir terminar el turno sin escalamiento ni informe, sin consumir las devoluciones del cierre, con un evento que diga que el caso espera al analista y por qué.
- **FR-015**: Cualquier otro fin de turno DEBE evaluarse como un cierre, igual que en el #9: con el comercio identificado o el registro caído, se exigen el escalamiento si hay causas y el informe vigente. El test del #9 que fijaba la limitación del fin de turno DEBE cambiar a sabiendas.
- **FR-016**: Mientras el caso espera el identificador o un nombre válido (los dos primeros puntos de FR-014), escalar y registrar el informe DEBEN rechazarse con un motivo que pida ese dato, y las listas siguen bloqueadas por I.1. **Excepción**: si el caso está sellado por un fallo de hook (causa `fallo_de_hook`), escalar SÍ se admite, porque es la salida segura (FR-012), y después el informe mínimo del #9 como siempre. En la espera de la categoría, escalar y registrar el informe siguen las reglas de siempre (sin categoría determinada no se puede habilitar).
- **FR-017**: Cuando el analista responde con el identificador, una nueva consulta del registro con ese dato DEBE poder identificar al comercio aunque la consulta anterior del mismo caso fuera ambigua; la identificación anterior no impide la nueva.
- **FR-018**: Un caso que espera al analista NO DEBE figurar como completo.
- **FR-019**: La línea de comandos DEBE permitir responder al coordinador en el mismo caso cuando espera al analista.
- **FR-027**: Con el comercio identificado, un frente que se consultó con un nombre o un identificador que no corresponde a ese comercio NO DEBE contar como cubierto para él en la cobertura del #8. Es el caso de noticias consultadas en el primer turno con el nombre ambiguo. La cobertura lo declara con su motivo y las afirmaciones de ese frente solo pueden citar consultas hechas para el comercio identificado (FR-004 del #9). El coordinador tiene que volver a delegarlo con el comercio identificado. El frente de categoría no depende del comercio y se conserva.
- **FR-028**: Las instrucciones del coordinador DEBEN aclarar que un rechazo de listas por falta de identificación deja de valer cuando el comercio queda identificado, y que entonces se vuelve a delegar listas, aunque ese rechazo trajera `reintentable: false` (riesgo residual 7 del #8). Un test DEBE fijar ese texto en las instrucciones, también en el modo de demostración.

**Categoría de la solicitud (US5)**

- **FR-020**: Una delegación del frente de categoría DEBE bloquearse si la categoría no aparece, normalizada, en ningún mensaje del analista del caso. El bloqueo deja un evento con la regla I.3 y la acción intentada, sin datos del comercio. La normalización es la de siempre (mayúsculas, tildes, espacios y puntuación); no cubre plurales.

**Traza (todas)**

- **FR-021**: Un escalamiento aceptado DEBE dejar un evento con su identificador, las causas que cubre, el resumen de la cobertura y el número de afirmaciones, sin datos del comercio; uno rechazado deja el evento de bloqueo con su motivo.
- **FR-022**: Los motivos, eventos y textos fijos van en español y no repiten nombres ni identificadores de comercios o personas.

**Transversales**

- **FR-023**: Todo lo anterior DEBE verificarse con tests deterministas, sin llamar al modelo, incluidos los casos de prueba (a), (b) y (d) de extremo a extremo con un coordinador simulado. El caso (d) va en dos turnos del mismo caso, con el escenario de US3-6 (la noticia N-0001 aparece tras volver a delegar noticias).
- **FR-024**: El comportamiento con el modelo real DEBE comprobarse a mano una vez (quickstart) con los casos (a), (b) y (d), este último en dos turnos. Se anotan el escalamiento, el resumen guardado, el informe y los eventos. En el caso (d) se anota además que en el segundo turno se consultaron listas y se volvió a delegar noticias.
- **FR-025**: Solo datos ficticios; sin credenciales.
- **FR-026**: Fuera de alcance: la presentación en el chat (#11) y la suite de los siete casos (#12).

### Key Entities *(include if feature involves data)*

- **Causa de escalamiento**: coincidencia del comercio, coincidencia del representante, alto riesgo o fallo de hook. Cada una tiene una etiqueta fija. La calcula el código.
- **Resumen al oficial**: comercio (del código), hallazgos por frente como afirmaciones (del coordinador, validadas), cobertura (del código), causa (del código), conflictos (del código) y acción recomendada (del coordinador). Es lo que se guarda con `escalar_a_cumplimiento`.
- **Espera del analista**: el estado de un caso cuyo turno terminó porque falta un dato del analista que el código sabe que hace falta. Puede ser el identificador ante varias coincidencias, un nombre válido si no hubo ninguna, o la categoría si la última delegación de categoría se bloqueó por I.3 sin ningún resultado. Lleva el motivo.
- **Mensaje del analista**: cada texto que el analista envía en el caso, en orden. La categoría que se delega tiene que aparecer en alguno.
- **Caso de bajo riesgo sin hallazgos comprobado**: el caso en el que el código puede afirmar que no hay ningún hallazgo con toda la información necesaria (FR-002). Es el único en que escalar se rechaza.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las ejecuciones simuladas, el caso (a) termina escalado con un informe `decide_cumplimiento` y el caso (b) termina con un informe `habilitar` y 0 escalamientos.
- **SC-002**: El 100 % de los resúmenes al oficial de prueba a los que les falta alguno de los cinco campos, o con una afirmación sin fuente, sin fecha o con una fuente no consultada, se rechaza, y el motivo nombra todo lo que falta.
- **SC-003**: En el 100 % de las ejecuciones simuladas del caso (d), los dos turnos terminan así, en el mismo caso:
  - el primero, sin consultas de listas, sin escalamiento y sin informe;
  - el segundo, con el identificador: el comercio identificado, noticias vuelto a delegar con N-0001 en el resultado, las listas consultadas y el informe vigente.
- **SC-004**: El cierre admite esperar al analista exactamente en tres situaciones: varias coincidencias, ninguna coincidencia, y la categoría bloqueada por I.3 sin resultado. Se comprueba recorriendo los seis estados del registro (sin delegar, en curso, varias coincidencias, ninguna, identificado y caído), combinados con los tres de la categoría (con resultado, sin delegar, bloqueada por I.3 sin resultado), con y sin causas de escalamiento.
- **SC-005**: Un lector sin acceso a la conversación responde con el resumen guardado del caso (a) las cinco preguntas de US2-6 sin abrir otro archivo (comprobación manual de la analista).
- **SC-006**: Ningún test llama al modelo; la suite completa y ruff pasan, y los tests de los tickets #5 a #9 siguen en verde (los que cambian por el nuevo esquema o por FR-004, FR-015 y FR-027 se adaptan sin debilitarse).

## Assumptions

- Depende del #7 (causas, escalamiento previo al informe, cierre e I.1 sobre listas), del #8 (cobertura calculada y sustituida en el escalamiento) y del #9 (esquema de afirmaciones, fuente consultada, conflictos, informe vigente y cierre con informe obligatorio).
- Cambia el contrato de `escalar_a_cumplimiento` del #5: los hallazgos pasan de un texto y una fuente por frente a la lista de afirmaciones del #9, y el resumen guardado añade los conflictos. Los tests del #5 al #9 que fijan la forma anterior se adaptan sin debilitarse.
- Los datos ficticios ya tienen lo que hace falta: Tienda Verde SAS en una categoría de alto riesgo (a), un comercio de bajo riesgo sin hallazgos (b) y los dos comercios de nombre casi idéntico, «Almacén Mirador SAS» (`CO-AM-0004`) y «Almacén Mirador Norte SAS» (`CO-AM-0005`), con la noticia N-0001 solo del segundo (d). No hace falta añadir datos.
- La continuación del caso es de la lógica del caso y de la línea de comandos; mostrarla turno a turno en el chat es del #11.
- **Decisión confirmada por la analista, con ajuste**: escalar un caso de bajo riesgo sin hallazgos comprobado se **rechaza en código** (FR-002), aunque el #8 decidió que el escalamiento nunca se deniega. Lo que el #8 protegía, que un fallo calculando la cobertura no impida escalar, se mantiene con FR-012. El ajuste: ese caso exige los cuatro frentes cubiertos, cero menciones en noticias y cero conflictos; cualquier otro caso sin causas admite el escalamiento sin exigirlo (FR-003).
- **Decisión confirmada por la analista, con ajuste**: `decide_cumplimiento` exige un escalamiento previo, vigente para el comercio actual (FR-004). Así se resuelve el riesgo residual 2 del #9 (D5): el oficial solo decide lo que le llega.
- **Decisión confirmada por la analista, con ajuste**: las esperas del analista son solo las que el código puede comprobar (FR-014). A las dos del registro se añade la categoría bloqueada por I.3 sin resultado, para que FR-020 («pregúntesela al analista») no choque con FR-015. Una pregunta del coordinador con el comercio identificado y la categoría con resultado sigue exigiendo el cierre completo. Por ejemplo, ante una categoría desconocida (que sí es un resultado), el coordinador registra el informe con la categoría no determinada, sin `habilitar`.
- **Decisión confirmada por la analista, con ajuste**: la categoría delegada tiene que aparecer en un mensaje del analista (FR-020), en lugar de declarar el pendiente 1 del #7 como riesgo residual.
- **Riesgos declarados de FR-020**:
  - una solicitud que menciona varias categorías;
  - la normalización no cubre plurales: «suplemento dietario» en la solicitud frente a «suplementos dietarios» en la delegación se bloquea, y el coordinador tiene que preguntar al analista (US5-5).
- **Decisión cambiada por la analista**: las fuentes registrales que difieren en el nombre o el representante (D3 del #9) **no** son una espera del analista. No hay datos ficticios con ese caso, y la espera dejaría el caso sin salida, porque el analista no puede resolver una contradicción entre fuentes con un identificador. D3 sigue como desviación declarada del #9.
- **Decisión de la analista**: tras identificar al comercio, un frente consultado con un nombre que no le corresponde no cuenta como cubierto para él (FR-027); la categoría sí se conserva. Así, el caso (d) no puede declarar noticias cubierto con la consulta del nombre ambiguo, que no encuentra la noticia N-0001 de `CO-AM-0005`.
- **Decisión de la analista**: el riesgo residual 7 del #8 se resuelve en las instrucciones del coordinador, con un test sobre su texto (FR-028), y se comprueba con el modelo real en el caso (d) (FR-024). El código ya ejecuta listas cuando el comercio queda identificado.
- El riesgo residual 1 del #9 (informe vigente con afirmaciones viejas) sigue siendo una decisión aceptada y no cambia.
- **Desviaciones del #9 que también aplican al resumen al oficial**, porque reutiliza el esquema de afirmaciones y el comercio del informe. Siguen como desviaciones declaradas y no se corrigen en este ticket:
  - **D1**: la fecha de cada afirmación no se contrasta con la del resultado que cita; solo se valida que sea una fecha real;
  - **D7**: el comercio pedido pierde el nombre cuando la consulta se hace solo con el identificador, con el registro caído. Pasa al #11.
- El presupuesto de turnos del #8 y del #9 es por turno del coordinador: una espera del analista termina el turno y el siguiente tiene su propio presupuesto. El plan comprueba que sigue cabiendo con las devoluciones nuevas: el escalamiento rechazado y corregido, y la nueva delegación de noticias.
- El plan fija:
  - el esquema exacto del resumen y dónde se valida (pasarela, hook o ambos);
  - el texto fijo de la causa cuando no hay causas;
  - cómo continúa la conversación del coordinador en el mismo caso;
  - cómo se guardan los mensajes del analista;
  - cómo se normaliza la categoría al compararla;
  - cómo decide el código que una consulta corresponde al comercio identificado (FR-027);
  - cómo se vigila el escalamiento después de una espera;
  - qué hace vigente un escalamiento para el comercio actual (FR-004).
