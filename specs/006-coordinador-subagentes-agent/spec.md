# Feature Specification: Coordinador y subagentes con el Agent SDK

**Feature Branch**: `006-coordinador-subagentes-agent`

**Created**: 2026-10-17

**Status**: Draft

**Input**: Issue #6 de GitHub: "Coordinador y subagentes con el Agent SDK". Construir el núcleo multi-agente: un coordinador que recibe la solicitud del analista, la descompone y delega cada frente de la investigación en subagentes especializados.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Delegar la solicitud del analista en frentes especializados (Priority: P1)

El analista escribe una solicitud en lenguaje natural, por ejemplo: «Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren procesar ventas en línea de suplementos dietarios y estiman unos $80.000.000 mensuales. ¿Lo podemos habilitar esta semana?». El coordinador la descompone en cuatro frentes (registro mercantil, listas restrictivas, noticias y riesgo de categoría) y delega cada uno en un subagente especializado. El coordinador no consulta ninguna fuente por sí mismo: solo delega, y solo él puede registrar el informe o escalar el caso.

**Why this priority**: es el núcleo del sistema. Sin la descomposición y la delegación no hay due diligence multi-agente, y los tickets #7 a #12 se construyen encima.

**Independent Test**: con subagentes simulados, se envía la solicitud del ejemplo y se comprueba que el coordinador delega exactamente los cuatro frentes, con los datos de la solicitud que cada uno necesita, y que no invoca ninguna herramienta de fuentes.

**Acceptance Scenarios**:

1. **Given** la solicitud del ejemplo, **When** el coordinador la procesa, **Then** delega un frente de registro mercantil (con el identificador `CO-TV-0001`), uno de noticias (con el comercio) y uno de riesgo de categoría (con la categoría «suplementos dietarios»), y delega el de listas restrictivas cuando el registro ya respondió.
2. **Given** el coordinador, **When** se revisan las herramientas que tiene disponibles, **Then** son únicamente la delegación en subagentes, `registrar_informe` y `escalar_a_cumplimiento`; ninguna herramienta de consulta de fuentes.
3. **Given** una solicitud sin identificador pero con el nombre del comercio, **When** el coordinador la procesa, **Then** delega el registro mercantil con el nombre y no inventa un identificador.
4. **Given** una solicitud que no indica categoría de negocio, **When** el coordinador la procesa, **Then** no delega el frente de riesgo de categoría con una categoría inventada y deja constancia de que ese frente no se pudo iniciar por falta del dato.

---

### User Story 2 - Aislar a cada subagente en su frente (Priority: P1)

Cada subagente solo puede usar las herramientas de su propio frente (el de registro, la consulta al registro mercantil; el de listas, la consulta de listas restrictivas; el de noticias, la búsqueda de noticias; el de riesgo, la consulta del riesgo de categoría) y solo conoce lo que el coordinador le pasa de forma explícita: no hereda la conversación del analista ni la del coordinador.

**Why this priority**: el aislamiento por frente limita el alcance de cada agente y hace auditable cada hallazgo (principio III). Es también lo que impide que un subagente confunda frentes, por ejemplo tratando una mención en noticias como coincidencia en listas.

**Independent Test**: se inspecciona la configuración de cada subagente y se comprueba su lista de herramientas y el contexto que recibe en la delegación; con un subagente simulado se intenta una herramienta ajena y se comprueba que no está disponible.

**Acceptance Scenarios**:

1. **Given** el subagente de noticias, **When** intenta usar la herramienta de listas restrictivas, **Then** la herramienta no está disponible para él.
2. **Given** el coordinador, **When** intenta usar la herramienta de registro mercantil, **Then** la herramienta no está disponible para él.
3. **Given** una conversación previa con datos que no son de un frente, **When** se delega ese frente, **Then** el subagente recibe solo el contexto pasado de forma explícita (por ejemplo, el identificador y el nombre del comercio) y no el resto de la conversación.
4. **Given** el frente de listas, **When** se delega, **Then** recibe el comercio y su representante legal tal como los devolvió el registro mercantil, y nada más que el coordinador no le haya pasado.

---

### User Story 3 - Ejecutar los frentes independientes en paralelo y listas después del registro (Priority: P1)

Los frentes que no dependen unos de otros (registro mercantil, noticias del comercio y riesgo de categoría) se ejecutan al mismo tiempo. El frente de listas restrictivas espera a que el registro mercantil termine, porque necesita el comercio y su representante legal tal como los devolvió el registro.

**Why this priority**: es el orden de dependencias que fija la constitución (III); además reduce el tiempo total del due diligence. Ejecutar listas antes del registro violaría la secuencia que los hooks de #7 harán cumplir.

**Independent Test**: con subagentes simulados que tardan un tiempo conocido, se ejecuta un caso completo y se comprueba, con los eventos registrados, que los tres frentes independientes se solapan en el tiempo y que listas empieza después de que el registro terminó.

**Acceptance Scenarios**:

1. **Given** un caso nuevo, **When** el coordinador inicia la investigación, **Then** los eventos muestran que registro, noticias y categoría empiezan sin esperar unos a otros y se solapan.
2. **Given** el registro mercantil aún en curso, **When** se consulta el registro de eventos, **Then** no existe ningún evento de inicio del frente de listas.
3. **Given** el registro mercantil terminado, **When** el coordinador continúa, **Then** el frente de listas empieza después del evento de fin del registro.
4. **Given** que el registro termina antes que noticias o categoría, **When** el coordinador continúa, **Then** listas empieza después del evento de fin del registro.

---

### User Story 4 - Consultar listas para el comercio y para su representante legal (Priority: P1)

El frente de listas restrictivas consulta tanto al comercio como a su representante legal, tal como los devolvió el registro mercantil. Una coincidencia del representante cuenta como hallazgo del caso, no solo la del comercio.

**Why this priority**: el caso de prueba (c) de la constitución es un representante legal con coincidencia en listas; si solo se consultara al comercio, el hallazgo se perdería.

**Independent Test**: con un registro simulado que devuelve un comercio y su representante, se ejecuta el frente de listas y se comprueban dos consultas: una por el comercio y otra por el representante.

**Acceptance Scenarios**:

1. **Given** un registro que devolvió un comercio y su representante legal, **When** se ejecuta el frente de listas, **Then** se consulta al comercio y al representante, cada uno con su resultado y su fuente.
2. **Given** un registro cuyo representante legal es un nombre distinto del comercio, **When** se ejecuta el frente de listas, **Then** el nombre consultado es el que devolvió el registro, sin modificarlo.
3. **Given** un registro que no devolvió representante legal, **When** se ejecuta el frente de listas, **Then** se consulta solo al comercio y el resultado deja constancia de que no había representante que consultar.

---

### User Story 5 - Estado del caso, resultados con procedencia y registro de eventos (Priority: P2)

Mientras dura el caso, el sistema mantiene un estado compartido: el resultado de cada frente y las consultas realizadas. Cada resultado de un subagente separa el contenido de los metadatos (fuente y fecha). Además, se registran eventos con marca de tiempo: cada delegación, el inicio y el fin de cada frente. El estado y el registro de eventos están disponibles para los hooks de #7, la interfaz de #11 y los tests.

**Why this priority**: los hooks de #7 necesitan el estado para decidir (por ejemplo, si el registro ya identificó al comercio) y la interfaz necesita los eventos para mostrar lo que pasa; pero el flujo de delegación funciona sin ellos.

**Independent Test**: se ejecuta un caso con subagentes simulados y se comprueba que el estado contiene el resultado y las consultas de cada frente, y que el registro de eventos tiene una delegación, un inicio y un fin por frente, ordenados por marca de tiempo.

**Acceptance Scenarios**:

1. **Given** un caso terminado, **When** se consulta el estado, **Then** contiene, por cada frente, su resultado (contenido separado de fuente y fecha) y las consultas que realizó.
2. **Given** un caso en curso, **When** se consulta el registro de eventos, **Then** cada evento tiene marca de tiempo, el frente y su tipo (delegación, inicio o fin).
3. **Given** un frente que no terminó, **When** se consulta el estado, **Then** ese frente figura como no terminado y no con un resultado vacío.

---

### User Story 6 - Terminar el ciclo según la razón de parada del modelo (Priority: P1)

El ciclo agéntico lo ejecuta el Claude Agent SDK: el código del proyecto no le añade contadores de iteraciones ni búsqueda de texto para decidir si continúa o termina. El límite de turnos (`max_turns`) es solo una protección de seguridad y está documentado como tal. Cuando el ciclo termina, el resultado se clasifica por la razón de parada (`stop_reason`) y el subtipo (`subtype`) del mensaje de resultado (`ResultMessage`): `end_turn` es una terminación normal; `max_tokens`, una terminación anómala; `error_max_turns`, el límite de seguridad. Cada caso queda registrado como evento.

**Why this priority**: lo exige la constitución (III) y evita dos fallos típicos: cortar un caso a medias por un contador propio y declarar terminado un caso por una frase del texto. Además, distinguir cómo terminó el ciclo evita presentar como completo un caso que se cortó.

**Independent Test**: se alimenta la clasificación con mensajes de resultado simulados (con distintos `stop_reason` y `subtype`) y se comprueba que cada uno se clasifica como normal, anómalo o límite de seguridad y que deja su evento; con un texto que contiene «listo» pero con `max_tokens`, la clasificación sigue siendo anómala. Se revisa además que el código del proyecto no contiene contadores de iteraciones ni búsqueda de palabras en el texto para controlar el ciclo.

**Acceptance Scenarios**:

1. **Given** un mensaje de resultado con `stop_reason` `end_turn`, **When** se clasifica, **Then** es una terminación normal y queda registrada como tal.
2. **Given** un mensaje de resultado con `stop_reason` `max_tokens`, **When** se clasifica, **Then** es una terminación anómala: no se trata como un fin normal y queda registrada como evento.
3. **Given** un mensaje de resultado con `subtype` `error_max_turns`, **When** se clasifica, **Then** es el límite de seguridad, distinto de una terminación normal y de una anómala, y queda registrado como evento.
4. **Given** un mensaje de resultado con texto que parece una conclusión (por ejemplo, «listo») pero con `stop_reason` `max_tokens`, **When** se clasifica, **Then** el texto no decide: sigue siendo una terminación anómala.
5. **Given** el código del proyecto, **When** se revisa, **Then** no añade contadores de iteraciones ni búsqueda de palabras en el texto para decidir si el ciclo continúa o termina, y `max_turns` figura como protección de seguridad documentada.

---

### Edge Cases

- Solicitud sin ningún dato identificable del comercio (ni nombre ni identificador): el coordinador no delega ningún frente y pide al analista el dato que falta.
- El registro mercantil devuelve varias coincidencias: el coordinador no elige una ni delega listas con una de ellas; pedir el identificador al analista es del ticket #10, aquí solo se garantiza que no se elige.
- El registro mercantil devuelve que no hay coincidencias: el frente de listas no se delega con datos inventados; queda sin iniciar y consta en el estado.
- Un subagente devuelve un error: el estado lo conserva con lo que se alcanzó a obtener; el manejo de fallas (reintentos, cobertura declarada) es del ticket #8.
- Dos frentes terminan en el mismo instante: el registro de eventos conserva un orden estable y el frente de listas sigue sin empezar hasta el fin del registro.
- La misma solicitud procesada dos veces: son dos casos independientes, cada uno con su estado y su registro de eventos; no comparten nada.
- Consulta del estado o del registro de eventos mientras el caso está en curso: devuelve lo disponible en ese momento, marcando los frentes sin terminar.
- Un subagente intenta una herramienta de otro frente: no está disponible; el intento no cambia el estado del caso.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST tener un coordinador, construido con el Claude Agent SDK, que reciba la solicitud del analista, la descomponga en los cuatro frentes (registro mercantil, listas restrictivas, noticias y riesgo de categoría) y delegue cada uno en un subagente especializado.
- **FR-002**: Las únicas herramientas del coordinador MUST ser la delegación en subagentes, `registrar_informe` y `escalar_a_cumplimiento`. El coordinador MUST NOT poder invocar las herramientas de consulta de fuentes.
- **FR-003**: Cada subagente MUST tener acceso únicamente a las herramientas del servidor de la pasarela de su frente: el de registro, a `consultar_registro_mercantil`; el de listas, a `consultar_listas_restrictivas`; el de noticias, a `buscar_noticias`; el de riesgo, a `consultar_riesgo_categoria`. Un subagente MUST NOT poder invocar las herramientas de otro frente ni los canales de decisión.
- **FR-004**: Cada subagente MUST recibir solo el contexto que el coordinador le pasa de forma explícita en la delegación, sin heredar la conversación del analista ni la del coordinador. Los agentes MUST NOT recibir tampoco la configuración del entorno de desarrollo: ni `CLAUDE.md`, ni hooks, ni ajustes del repositorio o del usuario.
- **FR-005**: El coordinador MUST delegar el frente de listas con el comercio y su representante legal tal como los devolvió el registro mercantil, sin modificarlos, y el frente de listas MUST consultar a ambos. Si el registro no devolvió representante, MUST consultar solo al comercio y dejar constancia.
- **FR-006**: Los frentes independientes (registro mercantil, noticias del comercio y riesgo de categoría) MUST ejecutarse en paralelo. El frente de listas MUST NOT empezar antes de que termine el registro mercantil.
- **FR-007**: El resultado de cada subagente MUST separar el contenido de los metadatos (fuente y fecha), y el sistema MUST conservar esa separación hasta el estado del caso.
- **FR-008**: El sistema MUST mantener, por cada caso, un estado compartido con el resultado de cada frente y las consultas realizadas, accesible para los hooks del ticket #7 y para la interfaz. Un frente que no terminó MUST figurar como no terminado.
- **FR-009**: El sistema MUST registrar eventos con marca de tiempo: cada delegación, y el inicio y el fin de cada frente. El registro MUST estar disponible para la interfaz (#11) y para los tests.
- **FR-010**: El ciclo agéntico MUST ejecutarlo el Claude Agent SDK; el código del proyecto MUST NOT añadirle contadores de iteraciones ni búsqueda de palabras en el texto de la respuesta para decidir si continúa o termina. Al terminar, el resultado MUST clasificarse por el `stop_reason` y el `subtype` del `ResultMessage`: `end_turn` es una terminación normal, `max_tokens` es una terminación anómala y `error_max_turns` es el límite de seguridad. Cada caso MUST registrarse como evento.
- **FR-011**: `max_turns` MUST ser solo una protección de seguridad y estar documentado como tal; su activación (`error_max_turns`) MUST distinguirse de una terminación normal y de una anómala.
- **FR-012**: Una terminación anómala (`max_tokens`) MUST NOT tratarse como un fin normal ni presentarse como caso completo.
- **FR-013**: El coordinador MUST NOT elegir entre varias coincidencias del registro, ni inventar el identificador, la categoría o el representante legal; ante datos ausentes o ambiguos MUST dejar constancia en el estado y no delegar el frente que dependa de ellos.
- **FR-014**: Cada caso MUST tener su propio estado y su propio registro de eventos; dos casos MUST NOT compartir datos.
- **FR-015**: Los mensajes al analista, las instrucciones de los agentes, los eventos y la documentación MUST estar en español.
- **FR-016**: El sistema MUST NOT incluir los hooks de reglas de negocio (#7), el manejo de fallas (#8), el informe final (#9), el escalamiento con criterio (#10) ni la interfaz (#11). El código y sus tests MUST seguir las convenciones del repositorio (pytest junto al código, ruff).

### Key Entities *(include if feature involves data)*

- **Solicitud del analista**: mensaje en lenguaje natural con el comercio (nombre o identificador), lo que quiere hacer y, a veces, la categoría de negocio y un monto estimado.
- **Caso**: una ejecución del due diligence para una solicitud; tiene su estado y su registro de eventos.
- **Frente**: una línea de la investigación (registro mercantil, listas restrictivas, noticias o riesgo de categoría), con su subagente, sus herramientas y su dependencia (listas depende del registro).
- **Subagente**: agente especializado en un frente, con herramientas limitadas a ese frente y un contexto recibido de forma explícita.
- **Delegación**: encargo del coordinador a un subagente, con el contexto explícito que ese frente necesita.
- **Resultado de frente**: lo que devuelve un subagente, con el contenido separado de los metadatos (fuente y fecha).
- **Estado del caso**: resultado de cada frente, consultas realizadas y situación de cada frente (sin iniciar, en curso, terminado, no terminado).
- **Evento**: registro con marca de tiempo de una delegación, del inicio de un frente, del fin de un frente o de una terminación anómala.
- **Razón de parada**: motivo por el que el modelo detuvo su respuesta (pidió una herramienta o delegación, terminó su turno, se cortó por límite); es lo que gobierna el ciclo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de los casos de prueba con todos los datos de la solicitud, con subagentes simulados, el coordinador delega exactamente los cuatro frentes y ninguna consulta de fuentes sale del coordinador.
- **SC-002**: En el 100 % de las pruebas, ningún subagente puede usar una herramienta de otro frente y el coordinador no puede usar ninguna herramienta de fuentes.
- **SC-003**: En el 100 % de las ejecuciones simuladas, el registro de eventos muestra solape de registro, noticias y categoría, y el inicio de listas posterior al fin del registro.
- **SC-004**: En el 100 % de las ejecuciones con representante legal, el frente de listas realiza una consulta por el comercio y otra por el representante.
- **SC-005**: Con mensajes de resultado simulados, el 100 % se clasifica correctamente (`end_turn` normal, `max_tokens` anómala, `error_max_turns` límite de seguridad) con su evento, con independencia del texto de la respuesta; y el código del proyecto no contiene contadores de iteraciones ni búsqueda de texto que controlen el ciclo.
- **SC-006**: Cada delegación, inicio y fin de frente tiene su evento con marca de tiempo, y alguien que no conoce el código puede reconstruir en qué orden ocurrió el caso solo con el registro de eventos.
- **SC-007**: Los tests del ticket pasan en verde junto con la suite existente, y ruff no reporta hallazgos.

## Assumptions

- La solicitud llega como texto del analista; el coordinador extrae de ella el nombre o el identificador del comercio y, si aparece, la categoría. La interfaz de chat que la captura es del ticket #11.
- El servidor MCP de la pasarela (ticket #5) ya expone las seis herramientas; este ticket las consume y no las modifica.
- Que listas espere al registro y que no se consulten listas sin un comercio identificado de forma unívoca son dos garantías distintas: aquí se implementa el orden de ejecución y que el coordinador no elige ni inventa; la garantía dura de las reglas I.1, I.2 e I.3, independiente de lo que decida el modelo, es de los hooks del ticket #7.
- Las noticias que se consultan en paralelo son las del comercio (por su nombre o identificador de la solicitud); las noticias del representante legal no se incluyen en este ticket.
- El estado del caso y el registro de eventos viven en memoria durante el caso y se exponen mediante una interfaz de consulta; su persistencia no forma parte de este ticket.
- La validación se hace con subagentes simulados y mensajes de resultado simulados para la clasificación del fin del ciclo; una ejecución real contra el modelo es opcional y no requiere credenciales en el repositorio (principio VIII), que se leen del entorno.
- Los datos de pruebas son los ficticios del ticket #5; no se añade ningún dato real (principio VII).
- Depende del ticket #5 (servidor MCP de la pasarela) y de las guardas del ticket #3 (reglas por ruta y protección de datos y secretos).
