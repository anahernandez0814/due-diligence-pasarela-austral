# Feature Specification: Interfaz de chat

**Feature Branch**: `011-interfaz-chat`

**Created**: 2026-10-18

**Status**: Draft

**Input**: Issue #11 de GitHub: "Interfaz de chat". Que el analista converse con el sistema en una interfaz tipo chat y que cualquier persona, sin conocer el código, entienda qué pasó en la conversación (comportamiento 12 del enunciado; principios VI y VIII). El alcance es **todo el issue**, con sus cuatro criterios de aceptación, más cuatro puntos que la analista añadió al arrancar: la hora de Colombia y la fecha UTC del registro (7), un formato de fechas único (8), textos neutros en los eventos de sustitución (9) y, del #10, los turnos por turno y la línea vacía con la espera abierta (10). Recoge también las tres observaciones de la validación manual del #7 (comentario del #11): la acción intentada en el indicador de bloqueo y una sola zona horaria, declarada. Los pendientes que la analista dejó fuera están en «Fuera de alcance».

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversar con el coordinador en varios turnos (Priority: P1)

El analista abre la aplicación, escribe la solicitud de due diligence y ve su mensaje y la respuesta del coordinador como en un chat. Si el coordinador le pide algo (el identificador ante varios comercios parecidos, un nombre válido cuando no hay ninguno o la categoría), el analista responde en el mismo chat y el caso continúa con todo lo que ya se había hecho. Cuando el caso termina, puede empezar uno nuevo sin cerrar la aplicación.

**Why this priority**: es el comportamiento 12 del enunciado y el primer criterio de aceptación del issue. Sin la conversación de varios turnos no se puede reproducir el caso (d), que pide el identificador antes de consultar listas.

**Independent Test**: sin llamar al modelo, con el coordinador simulado, se envía «Almacén Mirador SAS», la conversación muestra el mensaje del analista y la pregunta del coordinador, el analista responde `CO-AM-0005` y el segundo turno continúa en el mismo caso: las listas se consultan solo entonces y el historial conserva los cuatro mensajes en orden.

**Acceptance Scenarios**:

1. **Given** la aplicación abierta sin caso en curso, **When** el analista envía una solicitud, **Then** la conversación muestra su mensaje y, al terminar el turno, la respuesta del coordinador, cada uno identificado como del analista o del coordinador.
2. **Given** un caso que espera al analista (varias coincidencias, ninguna o la categoría), **When** el analista envía su respuesta, **Then** el caso continúa en el mismo estado (no empieza otro) y el historial muestra todos los turnos anteriores.
3. **Given** un caso que quedó **completo**, **When** el analista envía otro mensaje, **Then** ese mensaje inicia un caso nuevo, independiente del anterior, y la conversación lo dice («Caso anterior cerrado; se inició un caso nuevo»). **Given** un caso incompleto o que espera al analista, **When** el analista envía otro mensaje, **Then** el mensaje continúa el mismo caso, como permite el #10, y nada se pierde.
4. **Given** un caso en curso, **When** el analista elige empezar un caso nuevo, **Then** la conversación queda vacía y el siguiente mensaje inicia un caso independiente, sin estado ni eventos del anterior.
5. **Given** un caso que espera al analista, **When** el analista envía un mensaje vacío o solo con espacios, **Then** la interfaz le avisa que el coordinador espera su respuesta y que el caso sigue sin completar, y no envía nada al coordinador. La línea de comandos hace lo mismo: avisa en lugar de terminar en silencio.
6. **Given** un turno que no se puede continuar (el anterior no dejó sesión) o que falla por un error del sistema, **When** el analista envía su mensaje, **Then** la conversación muestra un mensaje en español que explica qué pasó y qué puede hacer (por ejemplo, empezar un caso nuevo), nunca una traza técnica.

---

### User Story 2 - Entender qué pasó en la conversación (Priority: P1)

Cualquier persona que mire la conversación, sin conocer el código, ve cuándo el coordinador delegó en un subagente y en cuál, cuándo una regla de negocio bloqueó una acción (qué regla, por qué y qué se intentó), cuándo se registró el informe y cuándo se escaló el caso. Antes de la recomendación del coordinador ve qué frentes se cubrieron, cuáles fallaron y por qué, y si el caso quedó completo o espera al analista.

**Why this priority**: es el segundo criterio de aceptación del issue y el principio VI de la constitución: «DEBE quedar evidente cuándo el coordinador delega en un subagente, registra el informe o escala el caso». La cobertura antes de la recomendación es la regla I.5 vista por el analista: un informe incompleto nunca se presenta como completo.

**Independent Test**: sin llamar al modelo, con el coordinador simulado, se ejecutan el caso (a) y el caso (f); cada delegación, bloqueo, informe registrado y escalamiento de la traza del caso aparece como un indicador en la conversación, y en cada turno la cobertura y los frentes que fallaron aparecen antes de la respuesta del coordinador.

**Acceptance Scenarios**:

1. **Given** un turno en el que el coordinador delega frentes, **When** se muestra el turno, **Then** hay un indicador por cada delegación, con el frente en palabras («registro mercantil», «listas restrictivas», «noticias», «riesgo de categoría»).
2. **Given** un turno en el que un hook bloquea una acción, **When** se muestra el turno, **Then** el indicador dice la regla (por ejemplo, I.1), el motivo y la acción intentada, sin datos del comercio más allá de los que ya están en la conversación.
3. **Given** un turno en el que se registra el informe o se escala el caso, **When** se muestra el turno, **Then** hay un indicador con el identificador del registro y, según corresponda, la recomendación o las causas del escalamiento.
4. **Given** un turno que termina, **When** se muestra el turno, **Then** antes de la respuesta del coordinador aparecen la cobertura de los cuatro frentes, los que no se cubrieron con su motivo, y si el caso quedó completo, incompleto o esperando al analista.
5. **Given** el caso (f), con noticias caído, **When** termina el turno, **Then** la cobertura dice, antes de la recomendación, que noticias no se cubrió y por qué, y el caso figura como incompleto.
6. **Given** un turno en curso, **When** el coordinador todavía no ha respondido, **Then** la interfaz muestra que está trabajando; los indicadores aparecen a medida que ocurren o, como mínimo, al terminar el turno.
7. **Given** un caso de varios turnos, **When** se muestran los turnos usados por el coordinador, **Then** son los de ese turno frente al límite de 30, no la suma del caso (hoy puede aparecer «35 de 30»).

---

### User Story 3 - Arrancar con la credencial correcta y solo con ella (Priority: P1)

Quien ejecuta la aplicación pone su clave de Anthropic en el archivo de entorno local, como explica la plantilla del repositorio. Si la clave falta, la aplicación no intenta nada: se detiene con un mensaje que explica cómo configurarla.

**Why this priority**: es el cuarto criterio de aceptación del issue y el principio VIII. Sin un mensaje claro, quien califica la prueba no sabe por qué la aplicación no responde, y un respaldo en otra credencial (por ejemplo, una sesión de Claude Code) ocultaría el problema.

**Independent Test**: sin llamar al modelo, se arranca la aplicación sin la clave en el entorno ni en el archivo: se ve el mensaje con los pasos, no se crea ningún caso y no se llama al modelo.

**Acceptance Scenarios**:

1. **Given** la clave en el archivo de entorno local, **When** se arranca la aplicación, **Then** se carga sin pisar una variable ya definida en el sistema y el chat queda listo.
2. **Given** ninguna clave (ni en el sistema ni en el archivo) o una clave vacía, **When** se arranca la aplicación, **Then** se detiene con un mensaje en español que dice qué falta, en qué archivo ponerla (a partir de `.env.example`) y que hay que reiniciar la aplicación; no se puede enviar ningún mensaje.
3. **Given** cualquier configuración, **When** la aplicación arranca o ejecuta un caso, **Then** no recurre a ninguna otra credencial ni muestra el valor de la clave en la interfaz ni en los registros.

---

### User Story 4 - Reproducir los siete casos de prueba desde el chat (Priority: P2)

Quien califica la prueba sigue la documentación: arranca la aplicación (con la caída simulada de noticias o el modo de demostración de hooks cuando el caso lo pide), escribe el mensaje documentado de cada caso (a) a (g) y ve en la conversación el resultado esperado.

**Why this priority**: es el tercer criterio de aceptación del issue. Depende de US1 y US2: sin conversación ni indicadores no hay nada que reproducir.

**Independent Test**: con la documentación y el modelo real, cada uno de los siete mensajes produce en el chat el resultado esperado que la documentación describe (validación manual, con su coste anotado).

**Acceptance Scenarios**:

1. **Given** la documentación, **When** se busca un caso de (a) a (g), **Then** hay un mensaje para escribir en el chat, cómo arrancar la aplicación para ese caso y qué se debe ver en la conversación (indicadores, cobertura y recomendación o escalamiento).
2. **Given** el caso (f), **When** se sigue la documentación, **Then** dice cómo activar la caída simulada de noticias, y la interfaz muestra de forma visible que esa caída está activa.
3. **Given** el caso (e), **When** se sigue la documentación, **Then** dice cómo activar el modo de demostración de hooks, que no desactiva ningún hook, y la interfaz muestra de forma visible que el modo está activo; el intento de consultar listas sin identificación queda bloqueado y señalado.
4. **Given** el caso (d), **When** se sigue la documentación, **Then** describe los dos turnos: el mensaje con el nombre ambiguo y la respuesta con el identificador.

---

### User Story 5 - Horas, fechas y textos que no confunden (Priority: P2)

Las horas de la interfaz están en hora de Colombia y lo dicen. El coordinador sabe que la fecha con la que la pasarela guarda un registro está en UTC, así que no le dice al analista que el informe se registró «un día después de hoy». Las fechas de las respuestas usan un solo formato. Los textos de los eventos de sustitución dicen lo que pasó sin acusar al coordinador de declarar algo distinto cuando solo omitió los campos.

**Why this priority**: son los puntos 7 a 9 de la analista y la segunda observación del #7. Afectan a la comprensión (principio VI), no a las reglas de negocio.

**Independent Test**: sin llamar al modelo, con un reloj fijo a las 22:00 de Colombia (03:00 UTC del día siguiente), las horas de la interfaz salen en hora de Colombia con la zona declarada, y los textos de `cobertura_sustituida` y `datos_sustituidos` salen neutros cuando el coordinador omitió los campos y con la mayúscula correcta tras el punto y coma.

**Acceptance Scenarios**:

1. **Given** cualquier hora mostrada en la interfaz (indicadores, registros), **When** se muestra, **Then** está en hora de Colombia y lleva la zona declarada; los registros guardados y la traza siguen en UTC, como decidió el #9.
2. **Given** el caso (b) ejecutado de noche en Colombia, cuando la fecha UTC ya es la del día siguiente, **When** el coordinador responde, **Then** no presenta la fecha del registro como posterior a hoy ni como una anomalía.
3. **Given** cualquier respuesta del coordinador con fechas, **When** se lee, **Then** todas las fechas usan el mismo formato.
4. **Given** un informe o un escalamiento en el que el coordinador omitió la cobertura, el comercio o los conflictos, **When** el código los sustituye, **Then** el evento dice que se puso lo calculado, sin decir que lo declarado «era distinto».
5. **Given** el evento `datos_sustituidos`, **When** se lee, **Then** no hay mayúscula después de un punto y coma.

---

### Edge Cases

- **El analista envía un mensaje mientras un turno está en curso**: no se envía otro turno al coordinador hasta que termine el actual; el mensaje no se pierde en silencio (o se bloquea la entrada mientras se trabaja, con el indicador de «trabajando»).
- **Dos casos de prueba seguidos sin pulsar «caso nuevo»**: si el primero quedó completo, el segundo mensaje inicia un caso nuevo y no hereda sus causas (con D1 del #10, las coincidencias de un comercio anterior siguen siendo causas del caso). Si el primero quedó incompleto (por ejemplo, el caso f), el segundo mensaje lo continúa: la conversación lo deja ver y el analista usa «caso nuevo».
- **La aplicación se recarga o se cierra a mitad de un caso**: el caso en curso se pierde; al volver, la conversación está vacía y se empieza uno nuevo. La persistencia entre sesiones queda como mejora futura.
- **Los dos modos de simulación a la vez** (noticias caído y demostración de hooks): se admiten, y la interfaz muestra los dos.
- **La caída simulada del registro** (`PASARELA_FALLA_REGISTRO=1`, del #9): se activa igual que la de noticias y la interfaz la muestra, aunque no corresponde a ninguno de los siete casos.
- **Un turno que termina por el límite de turnos u otra terminación anómala**: la conversación lo dice y el caso figura como incompleto.
- **Un caso con varios informes o escalamientos** (por ejemplo, el informe se registra de nuevo tras un reintento): cada uno tiene su indicador.
- **Un bloqueo que se repite** (el coordinador lo intenta dos veces): cada intento tiene su indicador.
- **La clave definida en el sistema y no en el archivo**: la aplicación arranca con la del sistema; el archivo no la pisa.
- **El fallo de un hook** (el caso queda sellado por precaución): la conversación lo señala como un aviso visible, con el caso incompleto.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (conversación)**: La interfaz DEBE mostrar la conversación turno a turno, con cada mensaje identificado como del analista o del coordinador, y DEBE permitir varios turnos en el mismo caso: mientras el caso esté incompleto o espere al analista, cada mensaje del analista continúa el caso con su estado. Si el caso quedó completo, el siguiente mensaje DEBE iniciar un caso nuevo y la conversación DEBE decirlo («Caso anterior cerrado; se inició un caso nuevo»). DEBE permitir además empezar un caso nuevo en cualquier momento, independiente del anterior, sin reiniciar la aplicación. Un turno que no se puede continuar o que falla DEBE terminar con un mensaje en español que explique qué pasó y qué hacer, nunca con una traza.
- **FR-002 (indicadores)**: La conversación DEBE señalar, en el turno en que ocurren y en el orden en que ocurrieron: cada delegación en un subagente (con el frente en palabras), cada bloqueo de una regla (con la regla, el motivo y la acción intentada), cada informe registrado (con su identificador y su recomendación) y cada escalamiento (con su identificador y sus causas). Mientras el turno está en curso, la interfaz DEBE mostrar que el coordinador está trabajando. Si los indicadores se muestran a medida que ocurren o al terminar el turno lo decide el plan, con su trade-off.
- **FR-003 (cobertura antes de la recomendación)**: Al terminar cada turno, la interfaz DEBE mostrar, antes de la respuesta del coordinador: la cobertura de los cuatro frentes calculada por el sistema, los frentes que no se cubrieron con su motivo, y si el caso quedó completo, incompleto o esperando al analista (y qué espera). Un caso incompleto NUNCA se presenta como completo (I.5).
- **FR-004 (turnos por turno)**: Los turnos usados por el coordinador se DEBEN mostrar por turno, frente al límite de seguridad de 30, en la interfaz y en la línea de comandos; nunca como la suma de todos los turnos del caso.
- **FR-005 (mensaje vacío con la espera abierta)**: Si el caso espera al analista y este envía un mensaje vacío o solo con espacios, la interfaz DEBE avisarle que el coordinador espera su respuesta y que el caso sigue sin completar, sin enviar nada al coordinador. La línea de comandos DEBE dar el mismo aviso antes de terminar, en lugar de terminar en silencio.
- **FR-006 (credencial)**: La aplicación de chat y la línea de comandos DEBEN cargar `ANTHROPIC_API_KEY` desde el archivo de entorno local, sin pisar una variable ya definida en el sistema, y comprobarla con la misma función (`comprobar_credencial`). Si la clave falta o está vacía, o hay definida otra credencial que se usaría en su lugar, DEBEN detenerse antes de crear ningún caso, con el mismo mensaje en español que explique cómo configurarla. NO DEBEN recurrir a ninguna otra credencial ni mostrar el valor de la clave.
- **FR-007 (hora de Colombia y fecha UTC del registro)**: Toda hora que muestre la interfaz DEBE estar en hora de Colombia, con la zona declarada; los registros guardados y la traza siguen en UTC. El coordinador DEBE saber que la fecha con la que la pasarela guarda un informe o un escalamiento está en UTC, de modo que no la presente al analista como una fecha posterior a hoy ni como una anomalía.
- **FR-008 (formato de fechas único)**: Las fechas de las respuestas del coordinador y de la interfaz DEBEN usar un único formato, el `AAAA-MM-DD` de las fuentes y las afirmaciones.
- **FR-009 (textos neutros en las sustituciones)**: Los eventos `cobertura_sustituida` y `datos_sustituidos` DEBEN decir que se puso lo calculado por el sistema («se sustituyó por la calculada») sin afirmar que lo declarado por el coordinador «era distinto» cuando solo faltaban los campos, y DEBEN respetar la mayúscula correcta tras el punto y coma.
- **FR-010 (reproducción documentada)**: La documentación DEBE explicar cómo arrancar la aplicación, cómo activar la caída simulada de noticias (caso f) y el modo de demostración de hooks (caso e), reiniciando la aplicación con la variable, y dar, para cada caso (a) a (g), el mensaje que se escribe en el chat (los dos turnos en el caso d) y lo que se debe ver. Cuando un modo de simulación está activo, la interfaz DEBE mostrarlo de forma visible durante toda la conversación.

### Key Entities

- **Conversación**: la secuencia de turnos de un caso tal como la ve el analista. Pertenece a un solo caso; empezar un caso nuevo empieza una conversación nueva.
- **Turno**: un mensaje del analista y todo lo que provocó: los indicadores, la cobertura y el estado del caso al terminar, la respuesta del coordinador y los turnos que usó el coordinador.
- **Indicador**: una señal visible en la conversación de algo que hizo el sistema (delegación, bloqueo, informe registrado, escalamiento), en lenguaje natural, sacada de la traza del caso y no del texto del modelo.
- **Modo de simulación**: la caída simulada de noticias o del registro, o el modo de demostración de hooks. Se activa al arrancar y es visible en la interfaz.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los siete casos de prueba (a) a (g) se reproducen desde el chat con los mensajes documentados y muestran el resultado que describe la documentación (validación manual con el modelo real, con el coste anotado).
- **SC-002**: En el 100 % de las ejecuciones simuladas, cada delegación, bloqueo, informe registrado y escalamiento de la traza del caso tiene su indicador en la conversación, en el turno y el orden en que ocurrió.
- **SC-003**: En el 100 % de los turnos simulados, la cobertura y los frentes que fallaron aparecen antes de la respuesta del coordinador, y ningún caso incompleto se muestra como completo.
- **SC-004**: Sin la clave, la aplicación de chat y la línea de comandos muestran el mensaje con los pasos y hacen cero llamadas al modelo.
- **SC-005**: Una persona que no conoce el código, viendo la conversación de los casos (a), (d) y (e), puede decir qué subagentes se consultaron, qué se bloqueó y por qué, y si el caso se registró o se escaló (valoración manual de la analista).
- **SC-006**: Ningún test llama al modelo, y los tests de los tickets anteriores siguen en verde; los que cambian por FR-004, FR-005 o FR-009 se adaptan sin debilitarse.

## Assumptions

- **Tecnología**: la interfaz es Streamlit, como fija la constitución; se añade como dependencia. Es una aplicación local de un solo analista, sin autenticación propia.
- **Reutilización**: la interfaz usa el `Caso` del #10 (`ejecutar` y `continuar`), su traza de eventos y su cobertura; no cambia las reglas de negocio ni los hooks. La línea de comandos sigue funcionando y recibe las correcciones de FR-004, FR-005, FR-006 y FR-009 (la comprobación de la credencial es la misma función en los dos puntos de entrada, por decisión de la analista en la revisión del plan).
- **Estado en memoria**: el caso vive mientras la sesión de la interfaz está abierta; recargar la página lo pierde.
- **Hora de Colombia**: UTC−5 todo el año (Colombia no tiene horario de verano).
- **Decisión de la analista**: los modos de simulación se activan con las variables de entorno de siempre (`PASARELA_FALLA_NOTICIAS=1`, `PASARELA_MODO_DEMO_HOOKS=1`) al arrancar la aplicación, no con un control dentro del chat; la interfaz los muestra, y la documentación dice que para los casos (e) y (f) hay que reiniciar la aplicación con la variable. Un control en la interfaz queda como mejora futura.
- **Decisión de la analista**: el formato único de fechas es `AAAA-MM-DD` (FR-008). Lo que escribe el coordinador lo guían sus instrucciones, no lo garantiza el código (principio II: es estilo, no una regla de negocio); lo que muestra la interfaz sí lo fija el código.
- **Decisión de la analista** (US1-3, FR-001): un mensaje tras un caso **completo** inicia un caso nuevo y la conversación lo dice; tras un caso incompleto o en espera, continúa el mismo caso. Motivo: con D1 del #10, las coincidencias de un comercio anterior siguen siendo causas del caso, y quien evalúe dos casos de prueba seguidos sin pulsar «caso nuevo» vería un escalamiento ajeno. El botón «caso nuevo» se mantiene.
- **Coste**: cada caso con el modelo real cuesta del orden de 0,15 a 0,30 USD con Opus 5.5; la validación manual de los siete casos se anota en el quickstart.
- **Datos**: los siete casos ya están en los datos ficticios (`test_datos_casos.py`); no hacen falta datos nuevos (principio VII).
- **Fuera de alcance** (el plan los anota como pendientes para DECISIONES.md):
  - D7 del #9 (el comercio pedido pierde el nombre con el registro caído y la consulta solo por identificador);
  - la redacción de `RESUMEN_REGISTRO_CAIDO` para todas las causas;
  - las 14 sugerencias de la revisión del PR #26 (entre ellas `informe.py:158`, `escalamiento_cubre` con el comercio por defecto, las duplicaciones, el test de dos turnos de US3-9 y R13.10);
  - el evento de espera que ya no queda en la traza con el registro sin delegar;
  - diseño visual elaborado, persistencia de casos entre sesiones y un control de los modos de simulación dentro de la interfaz.
