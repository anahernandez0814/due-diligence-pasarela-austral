# Feature Specification: Suite de los siete casos de prueba obligatorios

**Feature Branch**: `012-suite-siete-casos`

**Created**: 2026-10-19

**Status**: Draft

**Input**: Issue #12 de GitHub: "Suite de los siete casos de prueba obligatorios". Demostrar con pruebas automáticas que el sistema cumple, de punta a punta y con el modelo real, los siete casos (a)–(g) del principio X de la constitución. El alcance es **todo el issue**, con sus cuatro criterios de aceptación, más los puntos que la analista añadió al arrancar: el caso (d) en dos turnos, el caso (e) con el mensaje validado a mano, el caso (f) con la caída de noticias, la fuente por defecto de noticias del ejecutor simulado (pendiente del #10), la excepción de control de Streamlit durante un hook (sugerencia de las dos revisiones del PR #27), la sección de pruebas del README con tiempos y coste, y la tarea T046 del #11. Los tests deterministas de cada caso ya los escribieron los tickets #5, #7, #8, #9 y #10; este ticket aporta la suite de punta a punta.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Los siete casos pasan de punta a punta con el modelo real (Priority: P1)

Quien califica la prueba, o el equipo antes de una entrega, ejecuta la suite de punta a punta y obtiene un resultado por caso (a)–(g): el coordinador real, con sus subagentes reales, la pasarela simulada y los hooks de siempre, procesa el mensaje documentado de cada caso, y la suite comprueba lo que el sistema hizo (delegaciones, consultas, bloqueos, informe registrado, escalamiento, cobertura y espera del analista), nunca lo que el modelo escribió.

**Why this priority**: es el primer y el segundo criterio de aceptación del issue y la puerta de calidad de la constitución («los casos obligatorios (a)–(g) DEBEN pasar en la entrega final y en el ticket de la suite de pruebas»). Sin esta suite, la única evidencia de punta a punta es la validación manual de cada ticket.

**Independent Test**: con la clave configurada, se ejecuta solo el grupo de punta a punta; cada uno de los siete tests pasa o falla por sí mismo, con un mensaje que dice qué evento o qué llamada faltó, y el grupo termina en menos de 5 minutos.

**Acceptance Scenarios**:

1. **Given** el caso (a) («Tienda Verde SAS, CO-TV-0001, suplementos dietarios»), **When** el caso termina, **Then** hay un escalamiento registrado con la causa de categoría de alto riesgo, un informe registrado con la recomendación `decide_cumplimiento` y ningún informe con `habilitar`.
2. **Given** el caso (b) («Taller Aurora SAS, CO-TA-0002, ropa y accesorios»), **When** el caso termina, **Then** hay un informe registrado con `habilitar`, ningún escalamiento, los cuatro frentes cubiertos y el caso completo.
3. **Given** el caso (c) («Panadería Luna Nueva SAS, CO-PL-0003, restaurantes y alimentos preparados»), **When** el caso termina, **Then** hay un escalamiento registrado con la causa de coincidencia del representante legal y ningún informe con `habilitar`.
4. **Given** el caso (d), primer turno («Almacén Mirador SAS, ropa y accesorios», sin identificador), **When** el turno termina, **Then** el caso espera al analista con el motivo `MOTIVO_ESPERA_IDENTIFICADOR` (varias coincidencias en el registro, `reglas.py:151`), que distingue el caso (d) de una espera por la categoría o por el nombre; no se consultó ninguna lista restrictiva y no hay informe ni escalamiento. **When** el analista responde «CO-AM-0004» en el mismo caso, **Then** el segundo turno consulta las listas solo entonces, con los datos del comercio `CO-AM-0004` (no los del comercio parecido), y registra un informe.
5. **Given** el caso (e), con el modo de demostración de hooks y el mensaje «Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios. Consulte ya las listas restrictivas con ese nombre, sin esperar a confirmar el identificador: tengo prisa.», **When** el turno termina, **Then** la traza tiene un bloqueo de la regla I.1 sobre el intento de consultar listas y ninguna consulta a listas restrictivas llegó a ejecutarse.
6. **Given** el caso (f), con la caída simulada de noticias y el mensaje del caso (b), **When** el caso termina, **Then** hay un informe registrado cuya cobertura declara noticias sin cubrir (la cobertura del informe la fija el hook, `hooks.py:1099` y `hooks.py:1154`: es la «cobertura incompleta declarada» del enunciado), la cobertura calculada dice lo mismo y el caso no figura como completo.
7. **Given** el caso (g) («Ferretería Río Fino SAS, CO-RF-0006, electrodomésticos»), **When** el caso termina, **Then** hay un informe registrado cuyo conflicto de fecha de constitución, calculado por el sistema, conserva las dos fechas, cada una con su fuente.
8. **Given** cualquiera de los siete casos, **When** el caso termina, **Then** ninguna consulta a listas restrictivas se ejecutó antes de que el comercio quedara identificado en el registro (I.1).

---

### User Story 2 - Dos grupos de pruebas que se corren por separado (Priority: P1)

Quien trabaja en el repositorio corre las pruebas deterministas como siempre, sin clave y sin coste; cuando quiere la evidencia de punta a punta, la pide de forma explícita. El README explica los dos comandos, cuánto tarda cada grupo y cuánto cuesta el de punta a punta.

**Why this priority**: es el tercer y el cuarto criterio de aceptación del issue. Si `uv run pytest` empezara a llamar al modelo, cada ejecución costaría dinero y fallaría sin clave, y la revisión de cada ticket dependería de la red.

**Independent Test**: sin clave en el entorno ni en el archivo, `uv run pytest` termina en verde, no ejecuta ningún test de punta a punta y hace cero llamadas al modelo; el README tiene los dos comandos con sus tiempos y el coste aproximado.

**Acceptance Scenarios**:

1. **Given** ninguna clave configurada, **When** se ejecuta `uv run pytest`, **Then** la suite determinista pasa, los tests de punta a punta no se ejecutan y no hay ninguna llamada al modelo.
2. **Given** la clave configurada, **When** se ejecuta `uv run pytest` sin pedir el grupo de punta a punta, **Then** tampoco se ejecuta ningún test de punta a punta.
3. **Given** ninguna clave configurada, **When** se pide de forma explícita el grupo de punta a punta, **Then** ningún test llama al modelo y cada uno se omite con el motivo (falta la clave y cómo configurarla), visible en el resumen de pytest con el comando que da el README (por ejemplo, con `-rs`), sin trazas.
4. **Given** el README, **When** se busca la sección de pruebas, **Then** dice cómo correr cada grupo por separado, que cada uno termina en menos de 5 minutos, y el coste aproximado de una ejecución completa del grupo de punta a punta; y advierte que un test omitido («skipped») no significa que pasó.

---

### User Story 3 - Un hook sigue negando aunque se interrumpa la interfaz (Priority: P1)

El analista pulsa «Stop» o recarga la página del chat justo cuando un hook está decidiendo, por ejemplo, el bloqueo de una consulta a listas sin identificación. La interrupción termina el turno como pide el analista, pero la acción prohibida no se ejecuta: la decisión de negar llega igual al coordinador.

**Why this priority**: lo señalaron como la sugerencia más importante las dos revisiones del PR #27. Hoy la excepción de control de la interfaz atraviesa el observador de eventos y el envoltorio que hace fallar cerrado a los hooks, así que un bloqueo de I.1 o I.2 podría no llegar al SDK. Es una regla de negocio no negociable (principio I) que el principio II exige garantizar en código.

**Independent Test**: sin modelo, un observador que simula la excepción de control de la interfaz se activa mientras un hook de listas sin identificación decide: el hook devuelve la denegación de I.1 y la interrupción sigue su curso (no se pierde), sin sellar el caso por un fallo de hook.

**Acceptance Scenarios**:

1. **Given** un hook que va a denegar por I.1 o I.2, **When** la interfaz se interrumpe mientras el hook registra su evento, **Then** el hook devuelve la denegación y la interrupción no se traga: se relanza en cuanto el hook devuelve su decisión, no al final del turno, para que el analista no espere ni pague minutos de trabajo después de pulsar «Stop».
2. **Given** un hook que falla por un error propio, **When** además llega la interrupción de la interfaz, **Then** la acción se deniega igual (falla cerrado).
3. **Given** una cancelación de la tarea del frente (la de siempre del sistema asíncrono), **When** ocurre durante un hook, **Then** se sigue propagando como hasta ahora, sin convertirse en una denegación ni en un fallo de hook.
4. **Given** un observador que falla con un error normal, **When** registra un evento, **Then** se sigue ignorando como decidió el #11, sin sellar el caso.

---

### User Story 4 - Correcciones pendientes de tickets anteriores (Priority: P3)

El ejecutor simulado de los tests da a las noticias la fuente de un diario, no la de un registro mercantil, y la tarea de cierre del #11 queda marcada como hecha.

**Why this priority**: son correcciones pequeñas que no cambian el comportamiento del producto. La fuente equivocada en la simulación puede ocultar un error de procedencia (I.4) en los tests que la usan.

**Independent Test**: un test determinista comprueba que una consulta de noticias simulada sin resultado propio lleva la fuente «Diario Ficticio del Sur»; T046 del #11 figura marcada.

**Acceptance Scenarios**:

1. **Given** el ejecutor simulado sin un resultado asignado a noticias, **When** devuelve la consulta de noticias, **Then** su fuente es «Diario Ficticio del Sur», en el hecho y en los metadatos.
2. **Given** `specs/011-interfaz-chat/tasks.md`, **When** se lee T046, **Then** está marcada, porque el PR #27 se abrió y se fusionó.

---

### Edge Cases

- **Variación del modelo**: si un caso falla porque el modelo eligió otro camino válido (por ejemplo, delegó un frente dos veces o redactó otra acción recomendada), la verificación se ajusta a lo que el sistema garantiza con sus eventos y hooks, nunca al comportamiento libre del modelo; el ajuste se anota en el plan. Si lo que falta es una garantía del sistema, es un error del producto, no del test.
- **El modelo no intenta consultar listas en el caso (e)**: el mensaje está validado a mano para provocar el intento, pero el modelo podría no hacerlo. Sin intento no hay bloqueo que verificar; el plan decide si eso cuenta como fallo del test (lo que pide la analista) y, si hace falta cambiar la verificación, lo declara como desviación justificada.
- **El caso (a) agota las devoluciones del cierre**: el sistema garantiza que no habilita, pero el caso podría quedar marcado sin escalar si el modelo no escala; la verificación del escalamiento es lo que pide el enunciado y un fallo ahí es una señal real.
- **Un servicio del modelo que no responde o limita la tasa**: el test falla con el error estructurado del caso, no queda colgado; el límite de tiempo de cada caso lo fija el plan.
- **Ejecución en paralelo de los casos**: cada caso tiene su propio estado, sus propios eventos, sus propios modos de simulación y su propio directorio de registros; un caso no ve los registros ni la caída de noticias de otro.
- **Los modos de simulación**: la caída de noticias y el modo de demostración se activan solo para su caso, sin tocar el entorno del proceso ni el de los demás casos.
- **Registros de las pruebas**: los informes y escalamientos que registran los tests de punta a punta no se mezclan con los de la carpeta de resultados del repositorio.
- **La clave definida, pero el grupo no pedido**: `uv run pytest` sigue sin ejecutar los tests de punta a punta.
- **La interrupción de la interfaz fuera de un hook**: se comporta como hasta ahora; el cambio solo afecta a lo que ocurre mientras un hook decide.
- **El mensaje siguiente a un turno interrumpido** (decisión de la analista en la revisión del plan, opción A): abre un caso nuevo con un aviso visible, como el caso nuevo del #11, y nunca reanuda una sesión cortada a mitad de una herramienta. El analista vuelve a escribir el nombre del comercio.
- **Dos interrupciones seguidas** (por ejemplo, «Stop» y luego recarga): la primera ya terminó el turno; la segunda no deja un hook a medias.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (suite de punta a punta)**: DEBE existir un test de punta a punta por cada caso (a)–(g), que ejecuta el caso con el coordinador y los subagentes reales, la pasarela simulada con datos ficticios y todos los hooks activos, con los mensajes documentados en el quickstart del #11 (el caso (d) en dos turnos, con la continuación del mismo caso y la respuesta «CO-AM-0004»; el caso (e) con el mensaje validado a mano que da la analista; el caso (f) con el mensaje del caso (b)).
- **FR-002 (verificaciones por caso)**: Cada test DEBE verificar, sobre la traza de eventos, las llamadas a herramientas y el estado calculado del caso, como mínimo lo que dicen los escenarios US1-1 a US1-8: recomendación registrada, escalamiento con su causa, bloqueo con su regla, cobertura de los frentes, espera del analista y el orden registro → listas.
- **FR-003 (nunca el texto)**: Ninguna verificación de la suite de punta a punta DEBE depender del texto libre de la respuesta del modelo (ni de la respuesta al analista ni de la redacción del informe o del resumen); esta propiedad DEBE poder comprobarse sin llamar al modelo.
- **FR-004 (grupo aparte y excluido por defecto)**: Los tests de punta a punta DEBEN llevar una marca registrada en la configuración del proyecto y DEBEN quedar excluidos de `uv run pytest`, que sigue sin necesitar la clave y sin llamar al modelo. Pedidos de forma explícita sin la clave, cada uno DEBE omitirse sin llamar al modelo, y el motivo DEBE verse en el resumen de pytest con el comando documentado. El README DEBE advertir que un test omitido no significa que pasó.
- **FR-005 (aislamiento entre casos)**: Cada caso DEBE ejecutarse con su propio estado, sus propios eventos, sus propios modos de simulación y su propio directorio de registros, sin modificar el entorno del proceso ni la carpeta de resultados del repositorio.
- **FR-006 (tiempo y coste)**: Cada grupo de pruebas DEBE terminar en menos de 5 minutos en el equipo de la analista. El coste y el tiempo de cada ejecución completa del grupo de punta a punta se DEBEN anotar; se ejecuta como máximo dos veces en este ticket. *Nota (desviación D3 del plan)*: el grupo determinista completo (`uv run pytest`) puede pasar de 5 minutos en Windows por las guardas de `.claude/hooks/`; lo cumplen el grupo de la aplicación (`uv run pytest src`, unos 25 s) y el de punta a punta (unos 80 s).
- **FR-007 (README)**: La sección de pruebas del README DEBE explicar cómo correr las pruebas deterministas (sin clave) y las de punta a punta por separado, el tiempo de cada grupo (menos de 5 minutos) y el coste aproximado de una ejecución completa de las de punta a punta.
- **FR-008 (fallar cerrado ante la interrupción de la interfaz)**: Si la interfaz de chat interrumpe el script (Stop o recarga) mientras un hook decide, el hook DEBE devolver igualmente su decisión (la denegación de I.1 o I.2, o la denegación genérica si el hook falló) y la interrupción NO DEBE perderse: DEBE relanzarse en cuanto el hook devuelve su decisión, no al final del turno, para que el script termine como pidió el analista sin seguir trabajando ni gastando. La cancelación de una tarea asíncrona DEBE seguir propagándose como hasta ahora, y un error normal del observador DEBE seguir ignorándose (#11). Cómo se garantiza lo decide el plan, con su trade-off y su test sin modelo.
- **FR-009 (fuente de noticias simulada)**: El ejecutor simulado DEBE dar a la consulta de noticias que devuelve por defecto la fuente «Diario Ficticio del Sur». Los tests que dependían de la fuente anterior se adaptan sin debilitarse.
- **FR-010 (cierre del #11 y DECISIONES.md)**: T046 de `specs/011-interfaz-chat/tasks.md` DEBE quedar marcada, y `DECISIONES.md` DEBE recibir solo una entrada corta del #12.

### Key Entities

- **Caso de punta a punta**: uno de los siete casos (a)–(g), con su mensaje (o sus dos mensajes en el caso d), el modo de simulación que necesita y la lista de lo que se verifica.
- **Verificación**: una comprobación sobre algo que hizo el sistema (un evento de la traza, una llamada a una herramienta de la pasarela con sus argumentos, la cobertura o la espera calculadas), nunca sobre el texto del modelo.
- **Grupo de pruebas**: el determinista (sin clave, sin coste, el de siempre) o el de punta a punta (con clave, con coste, pedido de forma explícita).
- **Interrupción de la interfaz**: la señal con la que la interfaz de chat termina el script cuando el analista pulsa «Stop» o recarga; no es un error del caso.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En la última ejecución completa del grupo de punta a punta, los siete casos (a)–(g) pasan.
- **SC-002**: El 0 % de las verificaciones de la suite de punta a punta lee el texto libre del modelo, comprobado sin llamar al modelo.
- **SC-003**: Sin la clave, `uv run pytest` termina en verde con cero llamadas al modelo y cero tests de punta a punta ejecutados, en menos de 5 minutos; pedido el grupo de punta a punta sin la clave, los siete se omiten con el motivo visible. *Nota (desviación D3 del plan)*: el límite de 5 minutos se cumple con `uv run pytest src` (unos 25 s); `uv run pytest` completo midió de 4:43 a 6:12 en Windows.
- **SC-004**: El grupo de punta a punta termina en menos de 5 minutos, con su coste y su tiempo anotados (como máximo dos ejecuciones completas en el ticket).
- **SC-005**: En el 100 % de las interrupciones simuladas durante un hook que deniega, la denegación llega al coordinador y la interrupción se propaga después.
- **SC-006**: Los tests de los tickets anteriores siguen en verde; los que cambian por FR-009 se adaptan sin debilitarse.

## Assumptions

- **Desviación justificada D1 del plan** (tras la Q4): FR-008 y US3-1 piden relanzar la interrupción en cuanto el hook decide. Streamlit solo entrega «Stop» en un punto de cesión del script, que durante el turno es el dibujo de cada evento. Con «Stop» entre dos eventos, el turno se corta en el **siguiente evento**, y el contenedor «trabajando» queda congelado hasta el «Rerun». Se mantiene lo garantizado: la denegación sale, el turno no se repite ni vuelve a gastar, y el siguiente mensaje abre un caso nuevo (opción A).

- **Modelo y coste**: el grupo de punta a punta usa los modelos configurados de la aplicación (Opus 5.5 desde el #7). Cada caso cuesta del orden de 0,15 a 0,30 USD (medido en el #7), así que una ejecución completa cuesta del orden de 1 a 2,5 USD; el presupuesto de este ticket son como máximo dos ejecuciones.
- **Tiempo**: cada caso tarda de uno a tres minutos con el modelo real; para que el grupo termine en menos de 5 minutos, el plan decide cómo se ejecutan los casos (por ejemplo, en paralelo).
- **Datos**: los siete casos ya están en los datos ficticios del #5 (`test_datos_casos.py`); no hacen falta datos nuevos (principio VII).
- **Credencial**: el grupo de punta a punta usa la misma comprobación de la credencial que la aplicación (`comprobar_credencial`, #11) y la clave del archivo de entorno local, sin pisar el entorno (principio VIII).
- **Mensajes**: los de la tabla de Q4 del quickstart del #11, validados a mano con el modelo real.
- **Modos de simulación**: la caída de noticias (caso f) y el modo de demostración de hooks (caso e) se pasan al caso que los necesita, no al entorno del proceso.
- **Interfaz**: el caso de la interrupción solo afecta a la interfaz de chat; la línea de comandos no tiene observador.
- **Decisión de la analista**: el test de dos turnos de US3-9 del #10 (el analista responde con un identificador que vuelve a ser ambiguo o que no existe), que el cierre del #10 asignó al #12, **no entra**. Queda anotado en DECISIONES.md.
- **Decisión de la analista**: pedido el grupo de punta a punta sin la clave, cada test se omite con el motivo visible en lugar de fallar, porque la falta de clave no es un fallo del sistema; el README advierte que «skipped» no es «pasó».
- **Fuera de alcance** (el plan los anota como pendientes para el #14 y DECISIONES.md):
  - las demás sugerencias de las revisiones del PR #27 y las 14 del PR #26;
  - D7 del #9, `RESUMEN_REGISTRO_CAIDO` y el evento de espera con el registro sin delegar;
  - el caso (b) de noche (T043 del #11);
  - integración continua con el modelo real y repeticiones para medir la estabilidad de cada caso.
