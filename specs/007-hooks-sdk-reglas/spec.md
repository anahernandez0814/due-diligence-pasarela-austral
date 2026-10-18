# Feature Specification: Hooks del SDK: reglas de negocio 1, 2 y 3 garantizadas

**Feature Branch**: `007-hooks-sdk-reglas`

**Created**: 2026-10-18

**Status**: Draft

**Input**: Issue #7 de GitHub: "Hooks del SDK: reglas de negocio 1, 2 y 3 garantizadas". Garantizar con hooks del Agent SDK, y no con instrucciones en el prompt, que nunca se consulten listas sin identificación unívoca, que una coincidencia en listas impida recomendar la habilitación y obligue a escalar, y que un comercio de alto riesgo nunca reciba habilitación automática.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bloquear la consulta de listas sin identificación unívoca (Priority: P1)

Cuando el registro mercantil identifica a un único comercio, el sistema recuerda quién es ese comercio y quién es su representante legal. A partir de ahí, una consulta de listas restrictivas solo se permite si es por ese comercio o por ese representante. Cualquier otra consulta (antes de que el registro responda, con varias coincidencias, sin coincidencias, o por un nombre o identificador distinto) se bloquea y el modelo recibe el motivo, para que pueda corregirse o pedir el dato al analista. Esto ocurre aunque el modelo lo intente, con o sin reglas en su prompt.

**Why this priority**: es la regla I.1 de la constitución y el caso de prueba (e). Consultar listas sobre un comercio mal identificado puede señalar o absolver a la empresa equivocada.

**Independent Test**: sin llamar al modelo, se simulan las respuestas del registro (una coincidencia, varias, ninguna) y se intenta la consulta de listas en cada situación; solo la consulta por el comercio o el representante identificados se permite.

**Acceptance Scenarios**:

1. **Given** un caso donde el registro aún no respondió, **When** se intenta consultar listas por cualquier nombre o identificador, **Then** la consulta se bloquea y el motivo indica que el comercio no está identificado de forma unívoca.
2. **Given** un registro que devolvió exactamente una coincidencia, **When** se consulta listas por ese comercio, **Then** la consulta se permite.
3. **Given** un registro que devolvió exactamente una coincidencia con representante legal, **When** se consulta listas por ese representante, **Then** la consulta se permite.
4. **Given** un registro que devolvió varias coincidencias (nombres casi idénticos), **When** se intenta consultar listas por cualquiera de ellas, **Then** la consulta se bloquea y el motivo indica que hay varias coincidencias y que debe pedirse el identificador al analista.
5. **Given** un registro que no devolvió coincidencias, **When** se intenta consultar listas, **Then** la consulta se bloquea.
6. **Given** un comercio identificado, **When** se intenta consultar listas por un nombre o identificador que no es ni el del comercio ni el de su representante, **Then** la consulta se bloquea.
7. **Given** una consulta bloqueada, **When** se revisa el estado del caso, **Then** el bloqueo consta como evento con su motivo, y la fuente de listas no fue consultada.
8. **Given** un comercio identificado, **When** se consulta listas por el nombre del comercio con el tipo «persona», o por el del representante con el tipo «comercio», **Then** la consulta se bloquea: el tipo debe corresponder (comercio con «comercio», representante con «persona»).
9. **Given** un caso donde el registro no se delegó, fue rechazado o terminó sin una única coincidencia, **When** el coordinador intenta delegar el frente de listas, **Then** la delegación se bloquea antes de lanzar al subagente y el motivo llega al modelo; así el intento del caso (e) lo bloquea un hook también con el modelo real.
10. **Given** el registro en curso, **When** el coordinador delega el frente de listas, **Then** la delegación se permite y espera al fin del registro, como en el #6; si el registro termina sin coincidencia única, la propia delegación se rechaza (defensa adicional) y la consulta de listas sigue bloqueada por el hook de la consulta.
11. **Given** un registro que terminó con una única coincidencia, **When** el coordinador delega listas, **Then** la delegación se permite.

---

### User Story 2 - Registrar toda coincidencia en listas e impedir recomendar la habilitación (Priority: P1)

Toda coincidencia en listas restrictivas, del comercio o de su representante legal, queda registrada en el estado del caso. Mientras exista una coincidencia, el sistema rechaza cualquier informe que recomiende habilitar y exige que el caso se escale a un oficial de cumplimiento antes de aceptar el informe. El caso no puede darse por terminado sin ese escalamiento.

**Why this priority**: es la regla I.2 y el caso de prueba (c). Habilitar a un comercio cuyo representante figura en una lista restrictiva expone a la pasarela a riesgo regulatorio.

**Independent Test**: sin llamar al modelo, se simula una respuesta de listas con coincidencia del representante legal y se intenta registrar un informe que recomienda habilitar; se rechaza. Se intenta terminar el caso sin escalar; se impide. Tras escalar, un informe que no recomienda habilitar se acepta.

**Acceptance Scenarios**:

1. **Given** una consulta de listas con coincidencia del representante legal, **When** se revisa el estado del caso, **Then** la coincidencia consta con el nombre consultado, la fuente y la fecha.
2. **Given** una coincidencia en listas, **When** se intenta registrar un informe que recomienda habilitar, **Then** el informe se rechaza y el motivo menciona la coincidencia.
3. **Given** una coincidencia en listas y ningún escalamiento, **When** se intenta registrar cualquier informe, **Then** se rechaza hasta que `escalar_a_cumplimiento` se haya ejecutado para el caso.
4. **Given** una coincidencia en listas y el escalamiento ya ejecutado, **When** se registra un informe que no recomienda habilitar, **Then** el informe se acepta.
5. **Given** una coincidencia en listas, **When** el modelo intenta terminar el caso sin haber escalado, **Then** el cierre se impide y el modelo recibe el motivo.
6. **Given** una consulta de listas sin coincidencias para el comercio y el representante, **When** se revisa el estado, **Then** el caso no queda marcado como que requiere escalamiento por listas.

---

### User Story 3 - Impedir la habilitación automática de categorías de alto riesgo o sin categoría determinada (Priority: P1)

Las categorías de alto riesgo (apuestas, criptoactivos, suplementos dietarios y venta de medicamentos) son una lista fija del sistema, no un texto del prompt. Un informe que recomienda habilitar a un comercio de alto riesgo se rechaza, y el caso solo se cierra después de que `escalar_a_cumplimiento` se ejecutó. Tampoco se acepta una recomendación de habilitar si la categoría del caso no quedó determinada o si no se consultaron listas para el comercio y su representante.

**Why this priority**: es la regla I.3 y el caso de prueba (a). La decisión sobre un comercio de alto riesgo es siempre de un oficial de cumplimiento.

**Independent Test**: sin llamar al modelo, se simula el resultado de riesgo de categoría («suplementos dietarios», alto) y se intenta un informe que recomienda habilitar; se rechaza. Con categoría desconocida o no consultada, también se rechaza. Con un comercio de bajo riesgo, sin hallazgos y con listas consultadas, se acepta.

**Acceptance Scenarios**:

1. **Given** una categoría de alto riesgo, **When** se intenta registrar un informe que recomienda habilitar, **Then** se rechaza y el motivo indica que la decisión es de un oficial de cumplimiento.
2. **Given** una categoría de alto riesgo y el escalamiento ya ejecutado, **When** se registra un informe que no recomienda habilitar, **Then** se acepta.
3. **Given** una categoría de alto riesgo y ningún escalamiento, **When** se intenta registrar cualquier informe, **Then** se rechaza hasta escalar.
4. **Given** un caso cuya categoría no se consultó, o cuyo resultado fue categoría desconocida, **When** se intenta registrar un informe que recomienda habilitar, **Then** se rechaza porque la categoría no quedó determinada.
5. **Given** un caso en el que no se consultaron listas para el comercio y su representante legal, **When** se intenta registrar un informe que recomienda habilitar, **Then** se rechaza porque falta la consulta de listas.
6. **Given** un comercio de bajo riesgo, con categoría determinada, listas consultadas para el comercio y su representante y sin coincidencias, **When** se registra un informe que recomienda habilitar, **Then** se acepta y no se exige escalamiento.
7. **Given** una categoría de alto riesgo escrita con otras mayúsculas o sin tildes, **When** se evalúa, **Then** se reconoce como alto riesgo (la comparación sigue la misma normalización que el servidor de la pasarela).
8. **Given** una consulta de riesgo que dio alto riesgo y otra posterior para una categoría de riesgo medio o bajo, **When** se intenta registrar un informe que recomienda habilitar, **Then** se rechaza: el caso sigue siendo de alto riesgo.
9. **Given** una consulta de riesgo cuya respuesta indica nivel «alto» para una categoría que no está en la constante, **When** se evalúa, **Then** el caso es de alto riesgo: lo es si la categoría devuelta está en la constante o si la herramienta respondió nivel «alto».
10. **Given** una consulta de listas con error, o con un tipo que no corresponde al comercio o al representante, **When** se intenta registrar un informe que recomienda habilitar, **Then** esa consulta no cuenta como consulta realizada y el informe se rechaza por falta de consulta válida.

---

### User Story 4 - Que el caso no pueda terminar sin escalar cuando corresponde (Priority: P1)

Cuando un caso requiere escalamiento (por coincidencia en listas o por categoría de alto riesgo), el coordinador no puede dar por terminado el due diligence sin haber llamado a `escalar_a_cumplimiento`. Si intenta terminar, el cierre se impide y recibe el motivo; el ciclo continúa para que escale.

**Why this priority**: sin este cierre, el modelo podría omitir el escalamiento simplemente dejando de actuar, y los otros hooks no lo detectarían porque no hay una acción que bloquear.

**Independent Test**: sin llamar al modelo, se prepara un caso que requiere escalamiento y se simula el fin de turno del coordinador; se impide. Tras ejecutar el escalamiento, el fin de turno se permite.

**Acceptance Scenarios**:

1. **Given** un caso que requiere escalamiento sin escalar, **When** el coordinador intenta terminar, **Then** el cierre se impide y el motivo nombra la causa (coincidencia en listas, alto riesgo o ambas).
2. **Given** un caso que requiere escalamiento con el escalamiento ya ejecutado, **When** el coordinador termina, **Then** el cierre se permite.
3. **Given** un caso que no requiere escalamiento, **When** el coordinador termina, **Then** el cierre se permite.
4. **Given** un cierre impedido, **When** se revisa el registro de eventos, **Then** consta el intento con su motivo.
5. **Given** un coordinador que insiste en terminar sin escalar, **When** se agotan las veces que se le devuelve el motivo, **Then** el caso queda marcado como terminado sin el escalamiento obligatorio, y no se presenta como completo ni como habilitado.

---

### User Story 5 - Estado compartido y hooks por agente con subagentes en sesiones separadas (Priority: P1)

Cada subagente se ejecuta en su propia sesión, sin compartir la conversación con el coordinador. Lo compartido es el estado del caso: lo que un subagente de registro obtiene lo ve el hook que vigila al subagente de listas, y lo que listas encuentra lo ve el hook que vigila al coordinador. Los hooks, en cambio, van por agente: el de la consulta de listas solo en el subagente de listas; el de fin de turno, el de `registrar_informe` y el de `delegar_frente` solo en el coordinador; los de registro y de listas que alimentan el estado, en el subagente cuya herramienta vigilan. El fin de turno de un subagente no bloquea. Nada depende de que los agentes compartan memoria de conversación.

**Why this priority**: el aislamiento por frente (principio III) es una decisión del #6; las garantías del #7 no pueden depender de que se rompa.

**Independent Test**: con ejecutores simulados que corren cada frente como una sesión separada, se ejecuta un caso completo y se comprueba que los hooks de cada sesión leen y escriben el mismo estado del caso, y que dos casos distintos no comparten nada.

**Acceptance Scenarios**:

1. **Given** un subagente de registro que identifica un comercio en una sesión, **When** el subagente de listas intenta consultar en otra sesión, **Then** el hook de listas ve al comercio identificado.
2. **Given** un subagente de listas que registra una coincidencia en su sesión, **When** el coordinador intenta registrar un informe en otra, **Then** el hook del coordinador ve la coincidencia.
3. **Given** dos casos distintos ejecutándose a la vez, **When** uno identifica a un comercio y registra una coincidencia, **Then** el otro caso no ve nada de eso.
4. **Given** el estado del caso, **When** lo lee un hook, **Then** lo que lee es lo que escribieron los hooks de los otros frentes y las respuestas reales de las herramientas, no lo que el modelo transcribió o resumió.
5. **Given** la configuración de cada agente, **When** se inspecciona, **Then** el subagente de listas tiene el hook de la consulta de listas y el coordinador tiene los de fin de turno, `registrar_informe` y `delegar_frente`, y ningún subagente tiene el de fin de turno.
6. **Given** un subagente que termina su turno en un caso que requiere escalamiento, **When** se evalúa su fin de turno, **Then** no se bloquea: el cierre del caso es del coordinador.

---

### User Story 6 - Modo de demostración sin reglas en el prompt (Priority: P2)

Para demostrar que la garantía es del código y no del prompt, existe un modo de demostración documentado, que se activa con una variable de entorno (por ejemplo, `PASARELA_MODO_DEMO_HOOKS=1`). En ese modo se quitan del prompt las instrucciones que guían las reglas de negocio 1, 2 y 3: en el coordinador, la regla 3 (no seguir con listas ante varias coincidencias) y la instrucción de escalar; en los subagentes, las que se refieran a esas reglas. Así el modelo puede intentar las acciones prohibidas (por ejemplo, delegar listas sin registro identificado) y los hooks siguen activos y las bloquean. Se ve en el chat (los intentos bloqueados constan como eventos con su motivo) y en las pruebas.

**Why this priority**: es la prueba de que las reglas no dependen del prompt (principio II). Es una herramienta de demostración y de verificación; el sistema funciona sin ella.

**Independent Test**: se verifica que, con la variable activa, el texto de instrucciones de los agentes no contiene las reglas; y, con un modelo simulado que intenta las tres acciones prohibidas, los tres hooks las bloquean. Con la variable inactiva, el comportamiento por defecto no cambia.

**Acceptance Scenarios**:

1. **Given** el modo de demostración activo, **When** se construyen las instrucciones del coordinador y de los subagentes, **Then** no incluyen la regla 3 del coordinador ni la instrucción de escalar, ni las instrucciones de los subagentes que guían las reglas 1, 2 y 3.
2. **Given** el modo de demostración activo y un modelo simulado que delega listas sin registro identificado o que consulta listas sin identificación, **When** se ejecuta, **Then** el hook de `delegar_frente` o el de la consulta lo bloquea y el bloqueo se ve en los eventos del chat.
3. **Given** el modo de demostración activo y un modelo simulado que registra un informe que recomienda habilitar a un comercio de alto riesgo o con coincidencia en listas, **When** se ejecuta, **Then** el hook lo rechaza.
4. **Given** el modo de demostración activo y un modelo simulado que intenta terminar sin escalar, **When** se ejecuta, **Then** el hook impide el cierre.
5. **Given** el modo de demostración inactivo (por defecto), **When** se construyen las instrucciones del coordinador, **Then** incluyen la guía de las reglas y la instrucción mínima de este ticket (escalar y registrar el informe), y ya no incluyen la prohibición de decidir del #6 ni la regla «No decidas la habilitación»; las instrucciones de los subagentes no cambian.
6. **Given** el modo de demostración, **When** se lee la documentación, **Then** explica qué hace, cómo se activa y que no debe usarse como configuración normal.

---

### Edge Cases

- **Representante legal ausente**: el registro identifica al comercio pero no devuelve representante; el hook solo permite consultar al comercio, y consultar listas por cualquier otro nombre se bloquea. Un informe que recomienda habilitar sin representante consultado (por no existir) puede aceptarse solo si consta que el registro no devolvió representante.
- **Consulta repetida del registro**: si el registro se consulta otra vez y cambia el resultado (de una coincidencia a varias, o a otro comercio), el estado de identificación se reemplaza por el último resultado y se invalida lo que dependía del anterior: las consultas de listas hechas para el comercio anterior no cuentan para permitir un informe.
- **Coincidencia previa y comercio cambiado**: una coincidencia en listas ya registrada no se borra porque el registro cambie; el caso sigue requiriendo escalamiento.
- **Respuesta de herramienta con error o ilegible**: la identificación solo se guarda con una respuesta válida de exactamente una coincidencia; una respuesta con error, vacía o con forma inesperada no identifica a nadie. Las guardas fallan cerradas: ante la duda, bloquean.
- **Fallo de un hook**: si un hook falla o no puede leer el estado, la acción vigilada se bloquea, nunca se permite.
- **Consulta de listas fallida o parcial**: si la consulta de listas devuelve un error, no cuenta como consulta realizada para permitir una recomendación de habilitar; el manejo de fallas y de la cobertura declarada es del ticket #8.
- **Recomendación no reconocible**: un informe cuya recomendación no es reconocible como «no habilitar» se trata como recomendación de habilitar cuando alguna regla aplica (falla cerrada).
- **Informe de no habilitar**: nunca se rechaza por las reglas 2 y 3 (excepto por la exigencia de escalar antes cuando corresponde); las reglas solo impiden habilitar.
- **Escalamiento ejecutado y luego nueva coincidencia**: si tras escalar aparece una coincidencia nueva, el escalamiento previo no cubre la causa nueva y debe ejecutarse otra vez antes de aceptar el informe.
- **Nombres con distinto formato**: la comparación entre el nombre consultado y el del registro usa la misma normalización que el servidor de la pasarela (mayúsculas, tildes, espacios, puntuación).
- **Dos solicitudes iguales**: son dos casos independientes, cada uno con su estado y sus hooks.
- **Hook y subagente cancelado**: si un frente se cancela mientras su hook actualiza el estado, el estado queda consistente (se guarda completo o no se guarda).
- **Mensajes**: todo motivo que recibe el modelo o ve el analista está en español y no repite datos sensibles.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Tras cada consulta al registro mercantil, el sistema MUST guardar en el estado del caso el comercio y su representante legal solo si hubo exactamente una coincidencia, tal como los devolvió el registro. Con varias coincidencias, ninguna o una respuesta con error o ilegible, MUST NOT guardar identificación alguna y MUST dejar constancia del motivo.
- **FR-002**: Antes de cada consulta de listas restrictivas, el sistema MUST permitirla solo si el nombre o identificador consultado corresponde al comercio identificado de forma unívoca, con el tipo «comercio», o a su representante legal, con el tipo «persona». En cualquier otro caso (incluido un tipo que no corresponde) MUST bloquearla, devolver al modelo el motivo y registrar el bloqueo como evento.
- **FR-003**: La comparación de FR-002 MUST usar la misma normalización de nombres que el servidor de la pasarela, comparar también por identificador cuando exista y comparar además el tipo de la consulta.
- **FR-004**: Tras cada consulta de listas restrictivas, el sistema MUST registrar en el estado del caso cada coincidencia (a quién corresponde, fuente y fecha) y cada consulta realizada, sin depender del texto que el modelo produzca.
- **FR-005**: Antes de cada `registrar_informe`, el sistema MUST rechazar una recomendación de habilitar si hay alguna coincidencia en listas, si no se consultaron listas para el comercio y para su representante legal (cuando existe), si la categoría del caso no quedó determinada o si es de alto riesgo. Solo cuenta como consulta de listas la que fue válida (sin error) y con el tipo correcto. El motivo MUST nombrar todas las causas que apliquen.
- **FR-006**: Antes de cada `registrar_informe`, si el caso tiene coincidencia en listas o categoría de alto riesgo, el sistema MUST aceptar el informe solo después de que `escalar_a_cumplimiento` se ejecutó con éxito para el caso y para la causa vigente.
- **FR-007**: Al intentar terminar el due diligence, el sistema MUST impedir el cierre si el caso requiere escalamiento (FR-006) y `escalar_a_cumplimiento` no se ejecutó, devolviendo al coordinador el motivo y registrando el intento como evento. El número de veces que se devuelve el motivo MUST ser limitado y documentado; agotado, el caso queda marcado como terminado sin el escalamiento obligatorio y MUST NOT presentarse como completo ni como habilitado.
- **FR-008**: La lista de categorías de alto riesgo (apuestas, criptoactivos, suplementos dietarios y venta de medicamentos) MUST ser una constante en el código; ningún texto del prompt es necesario para que se cumpla. La categoría del caso MUST salir de los resultados de la herramienta de riesgo de categoría, no de lo que el modelo afirme. Una categoría es de alto riesgo si la categoría devuelta está en la constante o si la herramienta respondió nivel «alto»; si alguna consulta de riesgo del caso dio alto riesgo, el caso es de alto riesgo aunque después se consulte otra categoría.
- **FR-009**: Una categoría no consultada, desconocida o con resultado ilegible MUST tratarse como no determinada.
- **FR-010**: El estado del caso MUST ser el mismo para el coordinador y para todos los subagentes aunque cada uno corra en una sesión separada, y MUST alimentarse de las respuestas reales de las herramientas, no de lo que el modelo transcriba. Los hooks MUST asignarse por agente: el de la consulta de listas, solo al subagente de listas; los de fin de turno, `registrar_informe` y `delegar_frente`, solo al coordinador; los que alimentan el estado, al agente cuya herramienta vigilan. El fin de turno de un subagente MUST NOT bloquear.
- **FR-011**: Cada caso MUST tener su propio estado de reglas; dos casos MUST NOT compartir identificación, coincidencias ni escalamientos.
- **FR-012**: Los hooks MUST fallar cerrados: si no pueden leer el estado, interpretar la entrada de la herramienta o terminar su evaluación, MUST bloquear la acción vigilada.
- **FR-013**: Cada bloqueo, rechazo o cierre impedido MUST registrarse como evento con marca de tiempo, la regla que lo causó (I.1, I.2 o I.3) y un motivo en español, disponible para la interfaz (#11) y para los tests.
- **FR-014**: El sistema MUST ofrecer un modo de demostración, activado por una variable de entorno documentada, que quite del prompt del coordinador y de los subagentes las instrucciones de las reglas 1, 2 y 3, dejando los hooks activos. Con la variable inactiva el comportamiento por defecto MUST NOT cambiar.
- **FR-015**: Los hooks MUST poder ejecutarse y probarse sin llamar al modelo, con entradas de herramientas y respuestas simuladas.
- **FR-016**: El sistema MUST NOT tomar decisiones de negocio fuera de estas reglas: no redacta el resumen al oficial (#10), no maneja reintentos ni cobertura declarada (#8) ni arma el informe final con procedencia (#9). Los motivos de bloqueo MUST NOT repetir datos sensibles.
- **FR-017**: Los mensajes al modelo, los eventos y la documentación MUST estar en español; el código y sus tests MUST seguir las convenciones del repositorio (pytest junto al código, ruff).
- **FR-018**: Antes de cada delegación del frente de listas, un hook del coordinador MUST bloquear la delegación si el registro no se delegó, fue rechazado o terminó sin coincidencia única, devolviendo al modelo el motivo y registrando el evento. Si el registro está en curso, MUST permitirla (la herramienta espera, como en el #6). El rechazo interno de la delegación del #6 MUST conservarse como defensa adicional.
- **FR-019**: Este ticket MUST retirar del coordinador la prohibición de decidir del #6 (la constante `PROHIBICION_DECISION` y la regla «No decidas la habilitación») y sustituirla por una instrucción mínima: escalar con `escalar_a_cumplimiento` cuando haya coincidencia en listas o categoría de alto riesgo, y registrar el informe al final con una recomendación del conjunto cerrado que defina el plan. El contenido del resumen al oficial es del #10 y la procedencia del informe, del #9. Esta instrucción es guía; la garantía son los hooks.

### Key Entities *(include if feature involves data)*

- **Identificación del comercio**: resultado de la consulta al registro cuando hubo exactamente una coincidencia: comercio (nombre e identificador) y representante legal, con fuente y fecha. Puede reemplazarse por una consulta posterior.
- **Consulta de listas**: a quién se consultó (comercio o representante), con qué tipo («comercio» o «persona»), resultado, fuente y fecha; incluye si fue válida o con error. Solo una consulta válida y de tipo correcto cuenta para permitir una recomendación de habilitar.
- **Coincidencia en listas**: hallazgo de una consulta de listas, con a quién corresponde, fuente y fecha. Una vez registrada no se borra.
- **Categoría del caso**: nivel de riesgo según las consultas de riesgo del caso; puede ser alto, medio, bajo o no determinada. Es alto si la categoría devuelta está en la constante de alto riesgo o la herramienta respondió «alto», y una vez alto no baja aunque se consulte otra categoría.
- **Causa de escalamiento**: coincidencia en listas, categoría de alto riesgo, o ambas; determina si el caso requiere escalamiento.
- **Escalamiento ejecutado**: constancia de que `escalar_a_cumplimiento` respondió con éxito para el caso y qué causas cubría.
- **Regla garantizada**: I.1, I.2 o I.3, con su hook y el evento que deja al actuar.
- **Modo de demostración**: configuración que quita las reglas del prompt; no altera los hooks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las pruebas de bloqueo de listas (sin registro previo, varias coincidencias, ninguna, nombre ajeno), la consulta se bloquea; en el 100 % de las pruebas con comercio o representante identificados, se permite (caso de prueba e).
- **SC-002**: En el 100 % de las pruebas con coincidencia del representante legal, un informe que recomienda habilitar se rechaza, el caso no puede cerrarse sin escalar, y tras escalar el informe de no habilitar se acepta (caso de prueba c).
- **SC-003**: En el 100 % de las pruebas con categoría de alto riesgo, no consultada o desconocida, un informe que recomienda habilitar se rechaza; con un comercio de bajo riesgo, sin hallazgos y con listas consultadas, se acepta sin escalar (casos de prueba a y b).
- **SC-004**: En el 100 % de las pruebas de fin de turno, un caso que requiere escalamiento no puede terminar sin `escalar_a_cumplimiento`, y uno que no lo requiere termina sin trabas.
- **SC-005**: En el modo de demostración, con las reglas fuera del prompt y un modelo simulado que intenta las tres acciones prohibidas, el 100 % se bloquea.
- **SC-006**: En el 100 % de las pruebas con frentes en sesiones separadas, el estado que ve cada hook coincide con lo que escribieron los otros y dos casos no comparten nada; cada hook está solo en los agentes que le corresponden y ningún fin de turno de subagente bloquea.
- **SC-007**: Cada bloqueo, rechazo o cierre impedido deja un evento con su regla y motivo en español, y alguien que no conoce el código puede entender en el registro de eventos qué se bloqueó y por qué.
- **SC-008**: Ninguna prueba de los hooks llama al modelo; los tests del ticket pasan junto con la suite existente y ruff no reporta hallazgos.

## Assumptions

- Depende del ticket #6 (coordinador, subagentes, estado del caso y registro de eventos, con el punto de extensión `hooks` que se reparte al coordinador y a cada subagente) y del #5 (herramientas de la pasarela y su forma de respuesta). Este ticket cierra la desviación temporal del principio II declarada en el #6 solo en lo que toca a las reglas I.1, I.2 e I.3: `registrar_informe` y `escalar_a_cumplimiento` dejan de estar pre-aprobadas sin guarda para esas reglas y el coordinador deja de tener prohibido decidir (FR-019). Las demás reglas y el contenido del resumen al oficial (#10) y de la procedencia del informe (#9) siguen pendientes.
- El #6 pasa hoy el mismo conjunto de hooks a todos los agentes (`coordinador.py`, líneas 105 y 112); este ticket lo cambia para repartirlos por agente (FR-010).
- La recomendación del informe llega en un campo de texto libre; el plan define el conjunto cerrado de recomendaciones reconocibles como «no habilitar» y todo lo demás se trata como habilitar cuando una regla aplica (falla cerrada). Si hace falta restringir los valores del campo en el servidor, es una decisión del plan.
- «Determinada» significa que la herramienta de riesgo de categoría respondió con un nivel conocido (alto, medio o bajo) para la categoría de la solicitud; la categoría la aporta el analista y su extracción es del coordinador (#6).
- Los hooks de las reglas son funciones Python del Agent SDK, ejecutadas en el proceso del caso; las guardas de Claude Code (ticket #3) son otro mecanismo y no se tocan.
- Decisión por defecto, sin marcador: no se exige que el escalamiento sea para el mismo texto que el informe, solo que haya ocurrido con éxito para el caso y cubra las causas vigentes.
- Decisión por defecto, sin marcador: el límite de reintentos del cierre impedido y su valor los fija el plan; es una protección de seguridad documentada, no el mecanismo de control de la regla.
- El contenido del resumen al oficial, el manejo de fallas y la cobertura declarada, el informe final y la interfaz son de los tickets #10, #8, #9 y #11.
- Validación con tests deterministas sin modelo; una prueba manual con el modelo real en modo de demostración es opcional y no requiere credenciales en el repositorio (principio VIII).
- Los datos de pruebas son los ficticios del ticket #5; no se añade ningún dato real (principio VII).
