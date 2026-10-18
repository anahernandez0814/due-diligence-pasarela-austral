# Feature Specification: Informe con procedencia, conflictos y registro

**Feature Branch**: `009-informe-procedencia-conflictos`

**Created**: 2026-10-18

**Status**: Draft

**Input**: Issue #9 de GitHub: "Informe con procedencia, conflictos y registro". Producir el informe de due diligence en el que cada afirmación tiene su fuente, los datos contradictorios se muestran juntos y la recomendación queda registrada. Incluye el contexto heredado: las tres observaciones de la validación manual del #7 (comentario en el #9) y el riesgo residual 6 del #8.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Que cada afirmación del informe lleve su fuente y su fecha (Priority: P1)

El analista recibe un informe en el que cada afirmación, frente por frente, dice de qué fuente sale y con qué fecha. Si el coordinador intenta registrar un informe con una afirmación sin fuente o sin fecha, el registro se rechaza con un motivo que nombra cada afirmación incompleta, y el coordinador tiene que corregirlo.

**Why this priority**: es la regla I.4 de la constitución («toda afirmación del informe DEBE llevar su fuente») y el primer criterio de aceptación del issue. Una afirmación sin fuente no se puede auditar.

**Independent Test**: sin llamar al modelo, se intenta registrar un informe con una afirmación sin fuente, otro con una afirmación sin fecha y otro completo; los dos primeros se rechazan nombrando la afirmación y el tercero se registra.

**Acceptance Scenarios**:

1. **Given** un informe con una afirmación sin fuente, **When** se intenta registrar, **Then** se rechaza, el motivo nombra el frente y la afirmación sin fuente y no se guarda nada.
2. **Given** un informe con una afirmación sin fecha, o con una fecha que no es una fecha válida, **When** se intenta registrar, **Then** se rechaza con el mismo tipo de motivo.
3. **Given** un informe con varias afirmaciones incompletas en frentes distintos, **When** se intenta registrar, **Then** el motivo nombra todas, no solo la primera.
4. **Given** un informe con una afirmación cuya fuente no es ninguna de las que el caso consultó para ese frente, **When** se intenta registrar, **Then** se rechaza con el motivo (decisión de la analista, ver Supuestos).
5. **Given** un informe en el que todas las afirmaciones tienen una fuente consultada y una fecha válida, **When** se registra, **Then** queda guardado con sus afirmaciones, fuentes y fechas tal como se enviaron.
6. **Given** un frente cuyo resultado es «sin hallazgos» (por ejemplo, listas sin coincidencias), **When** se registra el informe, **Then** esa conclusión también es una afirmación con su fuente y su fecha.

---

### User Story 2 - Que los datos contradictorios entre fuentes aparezcan juntos, sin elegir uno (Priority: P1)

Cuando las dos fuentes registrales dan valores distintos para el mismo dato del comercio identificado (por ejemplo, la fecha de constitución), el código lo detecta al comparar los datos estructurados y el informe registrado muestra los dos valores, cada uno con su fuente y su fecha. Ni el modelo ni el código eligen uno.

**Why this priority**: es la segunda mitad de la regla I.4 («si dos fuentes se contradicen, se muestran ambas con su origen y el sistema NO DEBE elegir una»), el comportamiento 8 del enunciado y el caso de prueba (g).

**Independent Test**: sin llamar al modelo, con el registro de un comercio cuyas dos fuentes difieren en la fecha de constitución, se calculan los conflictos y se registra el informe con un coordinador simulado; el informe registrado contiene un conflicto con los dos valores y sus dos fuentes, aunque el coordinador no lo haya declarado.

**Acceptance Scenarios**:

1. **Given** un comercio identificado cuyas dos fuentes registrales dan fechas de constitución distintas, **When** se registra el informe, **Then** el informe contiene un conflicto sobre la fecha de constitución con los dos valores, cada uno con su fuente y su fecha (caso de prueba g).
2. **Given** el mismo caso, **When** el coordinador declara en el informe un único valor de la fecha de constitución como si no hubiera conflicto, u omite el conflicto, **Then** la sección de conflictos que queda registrada es la calculada por el código, con los dos valores.
3. **Given** el mismo caso, **When** el coordinador declara un conflicto que el código no detecta, **Then** no queda registrado como conflicto.
4. **Given** un comercio cuyas dos fuentes coinciden en todos los datos, **When** se registra el informe, **Then** la sección de conflictos está vacía y lo dice de forma explícita.
5. **Given** dos fuentes que difieren en más de un dato, **When** se registra el informe, **Then** aparece un conflicto por cada dato distinto.
6. **Given** un dato que solo una de las fuentes trae, **When** se calculan los conflictos, **Then** no se presenta como conflicto, pero el dato conserva su única fuente.

---

### User Story 3 - Que todo due diligence terminado quede registrado, también los escalados (Priority: P1)

Cuando el coordinador termina el due diligence de un comercio identificado, el caso no puede cerrarse sin un informe vigente registrado con una recomendación entre habilitar, no habilitar o decisión del oficial. Esto vale también cuando el caso se escala, en el orden que ya fija el #7: primero el escalamiento y después el informe. El escalamiento no sustituye al informe. Vale también cuando el registro no respondió tras los reintentos: el informe se entrega declarando el registro y las listas como no cubiertos.

**Why this priority**: es el tercer criterio de aceptación del issue y la regla 5 del enunciado. Hoy el cierre solo exige el escalamiento cuando corresponde; un caso de bajo riesgo puede terminar sin informe y un caso escalado puede no tener informe.

**Independent Test**: sin llamar al modelo, con un coordinador simulado que intenta terminar sin registrar el informe, el cierre se impide con un motivo; al registrar el informe, el caso puede terminar. En un caso que exige escalamiento, el informe se rechaza hasta que se escala, y después hace falta el informe. Si un frente cambia después del informe, hace falta uno nuevo.

**Acceptance Scenarios**:

1. **Given** un comercio de bajo riesgo identificado y sin hallazgos, **When** el coordinador intenta terminar sin registrar el informe, **Then** el cierre se impide con un motivo que dice que falta registrar el informe.
2. **Given** un caso que exige escalamiento y ya fue escalado, **When** el coordinador intenta terminar sin el informe, **Then** el cierre se impide igual.
3. **Given** un caso que exige escalamiento y que todavía no se ha escalado, **When** el coordinador intenta registrar el informe, con cualquier recomendación, **Then** el informe se rechaza por la regla del #7 con el motivo de escalar primero, y el cierre se sigue impidiendo.
4. **Given** un caso con el informe vigente registrado (y el escalamiento antes, si corresponde), **When** el coordinador termina, **Then** el cierre se permite.
5. **Given** un registro que no respondió tras los reintentos del #8, **When** el coordinador intenta terminar sin informe, **Then** el cierre se impide. El informe que se registra lleva como comercio el que pidió el analista, declarado sin verificar; su cobertura declara el registro y las listas como no cubiertos, y `habilitar` sigue bloqueado (decisión de la analista, ver Supuestos).
6. **Given** un registro que respondió con varias coincidencias o con ninguna, **When** el coordinador termina el turno para pedir el identificador o que el analista revise el nombre, **Then** el cierre no exige informe y el caso no figura como completo.
7. **Given** un caso con el informe registrado, **When** después cambia el resultado de algún frente (un reintento que sale bien, un cambio de comercio o una coincidencia nueva) y el coordinador intenta terminar, **Then** el cierre se impide porque ese informe ya no está vigente y hace falta uno nuevo.
8. **Given** un comercio identificado y un coordinador que termina el turno para preguntar algo al analista, **When** se evalúa el cierre, **Then** se exige el informe igual (limitación conocida, ver Supuestos).
9. **Given** un caso en el que se agotan las devoluciones del cierre sin informe, **When** el coordinador termina, **Then** el caso queda marcado como terminado sin informe, deja un evento y nunca figura como completo.
10. **Given** una recomendación que no es una de las tres admitidas, **When** se intenta registrar el informe, **Then** se rechaza, como desde el #7.

---

### User Story 4 - Informe mínimo cuando la cobertura no se pudo calcular (Priority: P2)

Si un hook falló durante el caso (sello `fallo_de_hook`), hoy el informe se deniega siempre y un caso escalado queda sin informe (riesgo residual 6 del #8). Con este ticket, en esa situación se admite un informe mínimo: solo con la recomendación «decisión del oficial» y con la cobertura sustituida por el texto fijo que dice que no se pudo calcular. El caso sigue sin figurar como completo.

**Why this priority**: resuelve el riesgo residual 6 heredado del #8 y hace que el tercer criterio de aceptación se cumpla también en ese caso. Es P2 porque solo ocurre cuando falla un hook.

**Independent Test**: sin llamar al modelo, se fuerza el sello de fallo de hook; un informe con `habilitar` o `no_habilitar` se rechaza, uno con `decide_cumplimiento` se registra con el texto fijo de cobertura, y el caso no figura como completo.

**Acceptance Scenarios**:

1. **Given** el caso sellado por un fallo de hook, **When** el coordinador registra el informe con `decide_cumplimiento`, **Then** se registra con la cobertura sustituida por el texto fijo y el evento lo dice.
2. **Given** el caso sellado, **When** el coordinador intenta registrar el informe con `habilitar` o `no_habilitar`, **Then** se rechaza con un motivo que dice que, tras un fallo de hook, solo decide el oficial.
3. **Given** el caso sellado, **When** se revisa el estado al terminar, **Then** el caso no figura como completo aunque el informe se haya registrado.
4. **Given** el caso sellado, **When** el informe mínimo trae afirmaciones, **Then** cada una sigue necesitando su fuente y su fecha (US1).

---

### User Story 5 - Una traza del caso que se entiende sin el código (Priority: P2)

El analista, o quien revise el caso después, ve en los eventos cuándo se registró el informe y con qué recomendación, qué acción se intentó cuando un hook bloqueó algo, y puede cruzar la hora de un evento con la del archivo guardado porque ambas declaran su zona horaria.

**Why this priority**: son las tres observaciones de la validación manual del #7, dejadas en este ticket. El comportamiento 12 del enunciado y el principio VI piden que se vea cuándo se registra el informe; la interfaz (#11) lo mostrará a partir de estos eventos.

**Independent Test**: sin llamar al modelo, se registra un informe y se provoca un bloqueo de regla; los eventos incluyen el registro del informe con su identificador y su recomendación, y el bloqueo con la acción intentada, sin datos del comercio. Las marcas de tiempo del evento y del documento guardado declaran su zona.

**Acceptance Scenarios**:

1. **Given** un informe aceptado por la pasarela, **When** se revisan los eventos, **Then** hay un evento de informe registrado con el identificador que devolvió la pasarela, la recomendación, el resumen de la cobertura y el número de conflictos.
2. **Given** un informe rechazado (por las reglas o por la validación), **When** se revisan los eventos, **Then** no hay evento de informe registrado.
3. **Given** un bloqueo de regla, **When** se revisa su evento, **Then** dice qué se intentó (la herramienta y, si es el informe, la recomendación rechazada; si es listas, si la consulta era del comercio o del representante), sin nombres ni identificadores del comercio o de personas.
4. **Given** un evento y el informe guardado del mismo caso, **When** se comparan sus horas, **Then** ambas declaran la zona horaria de forma explícita y se pueden cruzar sin suponer nada.

---

### Edge Cases

- **Afirmación con fuente pero sin texto**: se rechaza; una afirmación vacía no aporta nada auditable.
- **Fuente escrita de otra forma** (mayúsculas, espacios): el plan decide si se normaliza o se exige la forma exacta; nunca se acepta una fuente que no se consultó.
- **Frente no cubierto**: puede no tener afirmaciones; la cobertura (código del #8) ya declara por qué. Lo obtenido antes de fallar puede citarse con su fuente.
- **Registro con un solo origen para el comercio**: sin conflictos; el informe lo dice de forma explícita.
- **Conflicto en el nombre o el representante legal**: ya impide identificar el comercio (#6); no llega a un informe.
- **Conflicto en el estado del comercio** (por ejemplo, activo en una fuente y no en la otra): es un conflicto más, con los dos valores.
- **Varios informes en el mismo caso** (el coordinador registra, cambia algo y registra otra vez): se admiten, porque un cambio en los frentes exige un informe nuevo (FR-023). El cierre solo cuenta el vigente y los eventos los muestran todos.
- **El analista cambia de comercio a mitad de conversación**: el informe del comercio anterior deja de estar vigente; el exigido es el del comercio identificado en ese momento (FR-023).
- **Fin de turno con el comercio identificado para preguntar algo al analista**: el cierre exige el informe igual, porque no distingue una pregunta de un cierre definitivo. Es una limitación conocida, fijada con un test; la solución de fondo es del #10. Con el registro caído pasa lo mismo.
- **Registro que responde que la entrada no es válida** (por ejemplo, un nombre demasiado corto): la fuente respondió, así que no es un registro caído; el coordinador pide al analista que corrija el nombre, como en la decisión (a). El plan fija qué causas del #8 cuentan como registro caído.
- **Registro caído y reintentado con éxito**: si el reintento identifica al comercio, rige el caso normal y el informe anterior, si lo había, deja de estar vigente.
- **Registro caído con solo el nombre del comercio**: el informe no inventa un identificador; el plan decide cómo se representa el comercio sin verificar.
- **Fallo del cálculo de los conflictos**: el informe no se registra con conflictos inventados ni con la sección vacía como si no los hubiera; el plan decide si se deniega o se registra con un texto fijo que declare que no se pudieron calcular, y el caso no figura como completo.
- **Informe con el comercio de otro identificador**: el comercio registrado es siempre el identificado por el código; si el coordinador declara otro, prevalece el del código o la llamada se rechaza (el plan elige).

## Requirements *(mandatory)*

### Functional Requirements

**Esquema y validación del informe (US1)**

- **FR-001**: El informe registrado DEBE tener estas partes: comercio, hallazgos por frente, conflictos, cobertura y recomendación. El plan fija el esquema; DEBE estar escrito como esquema verificable por código, no solo descrito en un prompt.
- **FR-002**: Los hallazgos de cada frente DEBEN ser una lista de afirmaciones; cada afirmación DEBE tener un texto no vacío, una fuente y una fecha válida. Una afirmación sin alguno de los tres hace que el registro se rechace.
- **FR-003**: El rechazo DEBE ser un error estructurado (constitución IV) con un motivo en español que nombre cada afirmación incompleta por su frente y su posición, y DEBE permitir que el coordinador corrija y vuelva a registrar en el mismo caso.
- **FR-004**: La fuente de cada afirmación DEBE ser una de las fuentes que el caso consultó para ese frente, según los resultados guardados de los frentes. Una afirmación con una fuente no consultada se rechaza con el motivo.
- **FR-005**: La validación DEBE hacerla el código antes de que el informe quede guardado; un informe inválido NUNCA queda guardado, ni siquiera en parte.
- **FR-006**: El comercio del informe registrado DEBE ser el identificado de forma unívoca por el código (#6). Si el coordinador declara otro, prevalece el del código o la llamada se rechaza; el plan elige el mecanismo. Con el registro caído (FR-011), el comercio es el que pidió el analista y el informe DEBE declararlo de forma explícita como no verificado en el registro mercantil.

**Conflictos entre fuentes (US2)**

- **FR-007**: Los conflictos DEBE calcularlos el código comparando los datos estructurados de las fuentes registrales para el comercio identificado: hay conflicto en un dato cuando dos fuentes lo traen con valores distintos.
- **FR-008**: Cada conflicto DEBE incluir el dato, y por cada fuente, el valor, la fuente y su fecha. El código NO DEBE elegir ni ordenar los valores como si uno prevaleciera.
- **FR-009**: La sección de conflictos que queda registrada DEBE ser la calculada por el código en el momento de la llamada, igual que la cobertura del #8: si el coordinador declara otra, prevalece la del código. Si no hay conflictos, la sección lo dice de forma explícita.
- **FR-010**: El cálculo de conflictos DEBE ser determinista y DEBE estar disponible en el estado del caso para la interfaz (#11). La salida de la línea de comandos DEBE mostrar los conflictos junto a la cobertura.

**Registro obligatorio (US3, US4)**

- **FR-011**: Un due diligence terminado NO DEBE poder cerrarse sin un informe vigente (FR-023) registrado con una de las tres recomendaciones: `habilitar`, `no_habilitar` o `decide_cumplimiento`. Está terminado cuando el coordinador cierra en una de estas dos situaciones:
  - **Comercio identificado** de forma unívoca.
  - **Registro caído**: el registro no respondió y la política de reintento del #8 ya no admite otro intento con esa entrada. El comercio del informe es el que pidió el analista (FR-006); la cobertura declara el registro y las listas como no cubiertos, y `habilitar` sigue bloqueado por las reglas del #7 (sin listas consultadas no se puede habilitar).

  Con varias coincidencias o ninguna, no se exige informe. La exigencia DEBE hacerla cumplir el código, en el mismo punto que hoy exige el escalamiento. Las devoluciones por falta de informe DEBEN usar el mismo contador `MAX_CIERRES_IMPEDIDOS` que las del escalamiento, no uno propio, para que el presupuesto calculado de turnos del #8 siga en 15 de 30.
- **FR-012**: El escalamiento NO DEBE sustituir al informe: un caso que exige escalamiento solo puede cerrarse con el escalamiento y el informe, en ese orden, el que ya fija el #7. Mientras el escalamiento no cubra las causas vigentes, `evaluar_informe` rechaza el informe con cualquier recomendación; este ticket mantiene esa regla.
- **FR-013**: Si se agotan las devoluciones del cierre sin informe, el caso DEBE quedar marcado como terminado sin informe, con un evento, y NUNCA figurar como completo.
- **FR-023**: Para el cierre solo DEBE valer un informe **vigente**: registrado después del último cambio en los resultados de los frentes y para el comercio del caso en ese momento (el identificado o, con el registro caído, el pedido), igual que `escalamiento_cubre` compara con las instantáneas de cada escalamiento. Si después se vuelve a delegar y cambia algo (un reintento que sale bien, un cambio de comercio, una coincidencia nueva), el informe anterior deja de valer y hace falta uno nuevo. El mecanismo lo decide el plan.
- **FR-014**: Con el caso sellado por un fallo de hook, el informe DEBE admitirse solo con la recomendación `decide_cumplimiento` y con la cobertura y los conflictos sustituidos por textos fijos del código que declaran que no se pudieron calcular. Cualquier otra recomendación se rechaza con el motivo. El caso sigue sin figurar como completo.
- **FR-015**: Las reglas del #7 sobre el informe (I.2, I.3, recomendación del conjunto cerrado) y la cobertura del #8 DEBEN seguir cumpliéndose igual; este ticket añade validaciones, no quita ninguna.

**Traza del caso (US5)**

- **FR-016**: Un informe aceptado por la pasarela DEBE dejar un evento con el identificador del informe, la recomendación, el resumen de la cobertura y el número de conflictos, sin datos del comercio. Un informe rechazado no lo deja.
- **FR-017**: El evento de bloqueo de regla DEBE decir la acción intentada (la herramienta y, si aplica, la recomendación rechazada o el tipo de consulta de listas), sin nombres ni identificadores de comercios o personas.
- **FR-018**: Las marcas de tiempo de los eventos y de los documentos guardados DEBEN declarar su zona horaria de forma explícita. El plan decide si además se unifican en una sola zona.

**Transversales**

- **FR-019**: Todo lo anterior DEBE verificarse con tests deterministas, sin llamar al modelo, incluido el caso de prueba (g) de extremo a extremo con un coordinador simulado.
- **FR-020**: El comportamiento con el modelo real DEBE comprobarse a mano una vez (quickstart) con el comercio de fechas de constitución distintas y con un caso escalado, anotando el informe registrado, sus conflictos y los eventos.
- **FR-021**: Mensajes, eventos y documentación en español; solo datos ficticios; sin credenciales.
- **FR-022**: Fuera de alcance: el contenido del resumen al oficial en `escalar_a_cumplimiento` y la ambigüedad (#10), la presentación en el chat (#11) y la suite de los siete casos (#12).

### Key Entities *(include if feature involves data)*

- **Afirmación**: una frase del informe sobre un frente. Atributos: texto, fuente y fecha (la fecha de corte de la fuente, no la del reloj).
- **Hallazgos de un frente**: la lista de afirmaciones de ese frente; puede estar vacía si el frente no quedó cubierto.
- **Conflicto**: un dato del comercio con valores distintos según la fuente. Atributos: el dato y, por cada fuente, el valor, la fuente y la fecha. Lo calcula el código; no se guarda aparte del resultado del registro.
- **Informe**: comercio, hallazgos por frente, conflictos, cobertura (#8) y recomendación. Es lo que se guarda con `registrar_informe`.
- **Exigencia de cierre**: lo que el caso necesita para poder terminar: el escalamiento si corresponde (#7) y, después, el informe vigente si el comercio está identificado o el registro cayó (este ticket).
- **Informe vigente**: el último informe registrado, si no ha cambiado nada en los frentes ni el comercio del caso desde entonces. Es el único que cuenta para el cierre.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los informes de prueba con al menos una afirmación sin fuente, sin fecha o con una fuente no consultada se rechaza, y el motivo nombra todas las afirmaciones incompletas.
- **SC-002**: En el 100 % de las ejecuciones simuladas del caso (g), el informe registrado muestra las dos fechas de constitución, cada una con su fuente y su fecha, declare lo que declare el coordinador.
- **SC-003**: 0 casos simulados con comercio identificado o con el registro caído terminan con normalidad sin un informe vigente, incluidos los escalados. Recorriendo las combinaciones de escalamiento (sí o no) e informe (ninguno, vigente o anterior a un cambio), el cierre se permite solo cuando están todos los requisitos.
- **SC-004**: Con el sello de fallo de hook, el 100 % de los informes con `habilitar` o `no_habilitar` se rechaza y el informe con `decide_cumplimiento` se registra; el caso nunca figura como completo.
- **SC-005**: Leyendo solo los eventos de un caso, la analista identifica cuándo se registró el informe, con qué recomendación y qué acción bloqueó cada hook, sin abrir el código.
- **SC-006**: Ningún test llama al modelo; la suite completa y ruff pasan, y los casos de los tickets #5 a #8 siguen en verde (los que cambian por el nuevo esquema se adaptan sin debilitarse).

## Assumptions

- Depende del #6 (estado del caso, identificación del comercio y resultados guardados de los frentes, con fuente y fecha separadas del contenido), del #7 (hooks de `registrar_informe` y del cierre) y del #8 (cobertura calculada y sustituida en la llamada).
- La pasarela ya devuelve la fecha de constitución desde dos fuentes registrales ficticias, una hecho por fuente; en los datos ficticios hay un comercio cuyas fuentes difieren en esa fecha (caso g). No hace falta añadir datos.
- Cambia el contrato de `registrar_informe` del #5: los hallazgos pasan de un texto y una fuente por frente a una lista de afirmaciones con fuente y fecha, y se añaden los conflictos. Los tests del #5 al #8 que fijan la forma anterior se adaptan sin debilitarse. El formato de `escalar_a_cumplimiento` no cambia en este ticket; el #10 decide si reutiliza el esquema de afirmaciones.
- Mencionar en una afirmación uno de los valores en conflicto, con su fuente, no es «elegir uno»: la sección de conflictos del código muestra siempre los dos.
- Los conflictos se calculan sobre las fuentes registrales, que son las únicas con datos estructurados comparables del mismo comercio. Las noticias no se comparan con el registro.
- **Decisión confirmada por la analista**: la fuente de cada afirmación tiene que ser una de las consultadas para ese frente (FR-004), no solo un texto no vacío.
- **Decisión confirmada por la analista**: un due diligence está «terminado», y por tanto exige informe, cuando el comercio quedó identificado de forma unívoca o cuando el registro no respondió tras los reintentos (regla 5 del enunciado: el informe se entrega declarando el frente sin cubrir). Con varias coincidencias o ninguna no se exige informe (FR-011).
- **Decisión confirmada por la analista**: el riesgo residual 6 del #8 se resuelve con el informe mínimo de FR-014 (solo `decide_cumplimiento`, con textos fijos), no aceptándolo como excepción.
- **Para DECISIONES.md (a)**: si el registro responde que no hay ningún comercio, se pide al analista que revise el nombre y no se exige informe.
- **Para DECISIONES.md (b)**: con el registro caído, el comercio del informe es el que pidió el analista, sin verificar.
- **Limitación conocida, que resuelve el #10**: el `Stop` exige el informe en cualquier fin de turno con el comercio identificado (o con el registro caído), también cuando el coordinador termina el turno para preguntar algo al analista, porque el cierre no distingue una pregunta de un cierre definitivo. Un test fija este comportamiento para que el #10 lo cambie a sabiendas.
- La pasarela no tiene un interruptor para tirar el registro, como `PASARELA_FALLA_NOTICIAS` para noticias. El caso del registro caído se prueba con la simulación del coordinador y los subagentes, no con el modelo real.
- El presupuesto de turnos del #8 (`PRESUPUESTO_TURNOS_PEOR_CASO`, 15 de 30) no cambia, porque las devoluciones por falta de informe comparten `MAX_CIERRES_IMPEDIDOS` (FR-011).
- El plan fija: el esquema exacto, dónde se valida (pasarela, hook o ambos), el mecanismo de FR-006, FR-009 y FR-023, la normalización de las fuentes, qué causas del #8 cuentan como registro caído, cómo se representa el comercio sin verificar y la zona horaria común.
