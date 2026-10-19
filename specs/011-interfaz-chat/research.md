# Research: Interfaz de chat (#11)

Parte de la spec aprobada en `c7d7ced` y de las indicaciones de la analista para el plan. Lo
marcado *(a medir)* lo comprueba la implementación o el quickstart; no se hizo ninguna llamada al
modelo para este plan.

## R1. Indicadores en vivo o al terminar el turno

**Decisión**: **en vivo, como mejor esfuerzo, y al terminar el turno como versión que vale**.

- `RegistroEventos` gana un `observador` opcional: una función que recibe cada `Evento` justo
  después de guardarlo, dentro de un `try/except Exception` que lo ignora. `Caso(observador=...)`
  lo pasa. Sin observador, nada cambia.
- **El observador se llama DESPUÉS de salir del `with self._candado`, nunca dentro** (ajuste de
  la analista). `_candado` es un `threading.Lock()`, que no es reentrante: si el observador
  registrara otro evento, o leyera `eventos()`, dentro del `with`, el hilo se bloquearía para
  siempre. Un test lo fija: un observador que registra otro evento dentro de su llamada no
  bloquea, y los dos eventos quedan en la traza en orden (el del observador, con la secuencia
  siguiente). El test corre el registro en un hilo con tiempo límite (`join(timeout=…)` y
  aserción de que terminó), para que un bloqueo haga fallar el test y no cuelgue la suite.
- Mientras el turno corre, la interfaz muestra un contenedor «El coordinador está trabajando…» y
  el observador escribe en él cada indicador (con la función pura de R3) a medida que llega.
- Al terminar el turno, la interfaz **vuelve a construir** el turno entero desde la traza
  (`caso.eventos()`) y lo guarda en el historial. Lo que queda en la conversación es siempre esa
  versión; la en vivo solo acompaña la espera.

**Por qué**: un caso con Opus 5.5 tarda de uno a tres minutos por turno. Ver «Delegación al
subagente de registro mercantil» o «Bloqueado por la regla I.1…» mientras ocurre es lo que hace evidente la delegación
(principio VI); un «trabajando» mudo durante dos minutos no lo es. El coste es bajo:

- todos los eventos se registran en el bucle de `asyncio` del hilo que ejecuta el turno (no hay
  hilos en el paquete: el único `threading` es el candado de `eventos.py`), que en Streamlit es el
  hilo del script, así que el observador puede escribir en la página;
- el observador no puede afectar a las reglas: los hooks llaman a `registrar`, y una excepción
  ahí haría que `fallar_cerrado` sellara el caso. Por eso la excepción del observador se traga en
  `registrar` y nunca llega al hook (con su test);
- si algún evento llegara desde otro hilo sin contexto de Streamlit, la escritura en vivo se
  pierde (Streamlit solo avisa en el registro), pero el turno final sale igual de la traza.

**Alternativas descartadas**:
- *Solo al terminar el turno*: más simple (sin cambio en `eventos.py`), pero deja al analista uno
  a tres minutos sin saber qué hace el sistema.
- *Sondear la traza desde otro hilo*: Streamlit no escribe desde hilos sin contexto, y añade
  hilos a un paquete que no los tiene.
- *Construir lo que se guarda a partir de lo visto en vivo*: dos fuentes de verdad; la traza es
  la única.

## R2. Estructura de la aplicación y entrada

**Decisión**: dos módulos nuevos en `src/due_diligence/`:

- `presentacion.py`: **funciones puras, sin Streamlit** (indicación de la analista): de la traza
  a indicadores, la cobertura para mostrar, el estado del caso, el resumen del turno, la hora de
  Colombia, los modos activos, la decisión sobre el mensaje entrante y los textos fijos. Tests
  propios en `test_presentacion.py`.
- `chat.py`: el script de Streamlit. Solo dibuja lo que devuelve `presentacion.py` y llama a
  `Caso.ejecutar` / `Caso.continuar`. Se arranca con `uv run streamlit run src/due_diligence/chat.py`.

`__main__.py` usa las mismas funciones donde coinciden (aviso de la espera vacía, turnos por
turno), para que la línea de comandos y el chat digan lo mismo.

**Dependencias inyectables**: `chat.py` lee de `st.session_state["dependencias"]` un objeto
`Dependencias` con `cargar_entorno`, `entorno` y `crear_caso(observador)`. Si no está, usa los de
producción (`configuracion.cargar_entorno`, `os.environ` y `Caso(observador=...)`). Así los tests
de `AppTest` inyectan el coordinador simulado y **no cargan `.env`** (R8 del #6: los tests no
cargan el entorno ni llaman al modelo).

**Alternativas descartadas**: un paquete `interfaz/` aparte (no hace falta para dos módulos);
`AppTest.from_function` (no admite cierres, y el simulado necesita objetos).

## R3. De la traza a los indicadores

**Decisión**: `indicador(evento) -> Indicador | None`, pura, con este mapa:

| Evento | Indicador | Texto |
|--------|-----------|-------|
| `delegacion` | delegación | «Delegación al subagente de {frente en palabras}»; detalle solo si aporta: «Reintento con la misma entrada, tras un error que se puede reintentar.» o «Se vuelve a delegar con otra entrada.». La delegación normal va sin detalle, porque el de la traza repite el nombre interno del frente (validación manual) |
| `bloqueo_regla` | bloqueo | «Bloqueado por la regla {regla}: {acción intentada}» + el motivo |
| `informe_registrado` | informe | «Informe registrado» + el detalle (id, recomendación, cobertura, conflictos) |
| `escalamiento_registrado` | escalamiento | «Caso escalado a cumplimiento» + el detalle (id y causas) |
| `fallo_de_hook` | aviso | «Un control de las reglas falló; el caso se bloqueó por precaución» + el detalle |

Los demás eventos no son indicadores: lo que dicen (frentes que fallaron, esperas, terminación)
lo muestran la cobertura y el estado del caso (R4). Frente en palabras: «registro mercantil»,
«listas restrictivas», «noticias», «riesgo de categoría».

**Turno**: los eventos desde el `mensaje_analista` N hasta antes del N+1. Los del inicio
(`caso_iniciado`, `modo_demostracion`) van con el turno 1. `eventos_del_turno(eventos, n)` es pura.

**Datos del comercio**: los detalles y motivos son textos fijos de las reglas, y la acción
intentada no lleva datos del comercio desde el #9 (FR-017). El indicador no añade nada.

## R4. Cobertura y estado del caso antes de la respuesta

**Decisión**: `resumen_del_turno(caso, n) -> TurnoMostrado` reúne, en este orden de dibujo:
indicadores → cobertura → estado del caso → respuesta del coordinador → turnos usados.

- **Cobertura**: la de `caso.cobertura` (la misma que se registra), una fila por frente en
  palabras, cubierto o no y el motivo. En el motivo, los tipos de error conocidos van en palabras
  (`ERRORES_EN_PALABRAS`: «el servicio no está disponible» en lugar de `servicio_no_disponible`), y
  un tipo desconocido queda tal cual (validación manual). La cobertura registrada no cambia.
- **Estado**, un único valor, evaluado en este orden:
  1. `fallo_de_hook` → «Incompleto: un control de las reglas falló».
  2. espera del analista → «Esperando al analista. {motivo}» (dos oraciones: el motivo ya lleva sus dos puntos; validación manual).
  3. terminación anómala → «Incompleto: el turno terminó de forma anómala ({detalle})».
  4. `caso.completo` → «Completo».
  5. si no → «Incompleto», con lo que falta (cobertura incompleta, sin informe vigente,
     `cierre_sin_escalar`, `cierre_sin_informe`).

  Nunca «Completo» si `caso.completo` es falso (I.5).

La instrucción `_REGLA_RESUMEN` del coordinador también pide empezar por la cobertura y los
frentes que fallaron (pendiente del #9: «la respuesta empieza por la recomendación»); la garantía
del orden es la interfaz, el texto del modelo solo lo acompaña.

## R5. Turnos por turno (FR-004)

**Decisión**: `Caso` gana `turnos_por_turno: list[int | None]`, un valor por turno (`num_turns`
del `ResultMessage`, o `None` si no hubo). `Caso.turnos` sigue siendo la suma del caso, porque lo
usan los tests del #8 y del #10 y la validación de costes, pero **ya no se muestra frente al
límite**. La línea de comandos imprime «turnos del coordinador en este turno: N de 30» y el chat
lo mismo en cada turno.

**Alternativa descartada**: cambiar `Caso.turnos` a «el del último turno»: rompe tests que fijan
la suma y mezcla dos significados.

## R6. Mensaje entrante: caso nuevo, continuar o aviso (FR-001, FR-005, US1-3)

**Decisión**: `decidir_mensaje(caso, texto) -> Decision`, pura:

| Situación | Decisión |
|-----------|----------|
| texto vacío o solo espacios, caso esperando al analista | `AVISO_ESPERA`: «El coordinador espera su respuesta. {motivo} El caso sigue sin completar.» (dos oraciones, validación manual). No se llama al coordinador. |
| texto vacío o solo espacios, sin espera | `IGNORAR` |
| sin caso | `NUEVO` |
| caso **completo** | `NUEVO`, con el aviso «Caso anterior cerrado; se inició un caso nuevo.» (decisión de la analista) |
| caso incompleto o en espera | `CONTINUAR` |

El botón «Caso nuevo» siempre vacía la conversación y descarta el caso.

**Línea de comandos**: `_conversar` ya termina con una línea vacía; ahora, si había espera,
imprime antes el mismo `AVISO_ESPERA` (FR-005). El código de salida no cambia (contrato del #10).

*(a medir)* `st.chat_input` no envía un texto vacío. Si tampoco deja enviar uno con solo
espacios, el aviso no se puede provocar desde la página y se aplica la **alternativa decidida por
la analista (plan B de FR-005)**: mientras el caso espera al analista, el chat muestra un aviso
fijo encima de la entrada, «El coordinador espera su respuesta: {motivo}. El caso sigue sin
completar.» (el mismo `AVISO_ESPERA`), con su test en `AppTest`: caso (d) tras el turno 1, el
aviso está presente; tras el turno 2, ya no. Si la medición muestra que sí se envían espacios,
se usa la decisión `AVISO_ESPERA` de la tabla y el aviso fijo sobra. La función pura se prueba
igual en los dos casos. La línea de comandos mantiene el aviso ante la línea vacía.

**Medido (T033, Streamlit 1.66.0): sí se envían espacios, así que el plan B no se aplica.** En el
frontend (`static/static/js/ChatInput.*.js`), el envío se habilita con `J = … D!=="" || …`, sin
`trim()`, y la función de envío (`St`) solo comprueba `!J`; manda el valor tal cual. Un texto vacío
no se puede enviar, pero «   » sí, y llega así al script (comprobado con `AppTest`). El chat usa la
rama `AVISO_ESPERA` de `decidir_mensaje`; además, el texto de ayuda de la entrada dice qué espera
el coordinador. El test que queda es el de T034: «   » con la espera abierta muestra el aviso y no
llama a `continuar`.

**Fallos**: `CasoSinSesion` → el mensaje `MENSAJE_SIN_SESION` del #10 (se mueve a
`presentacion.py` y `__main__` lo importa). Otra excepción del turno (el `Caso` ya la clasifica
como anómala y la relanza) → «El turno falló por un error del sistema ({tipo}). El caso queda
incompleto; puede escribir de nuevo o iniciar un caso nuevo.», sin traza.

## R7. Un turno a la vez en Streamlit

**Decisión**: patrón de «mensaje pendiente». Al enviar, el texto se guarda en
`session_state["pendiente"]` y se pide `st.rerun()`. En la ejecución siguiente se dibuja el
historial, la entrada **deshabilitada** y el botón «Caso nuevo» deshabilitado, y solo entonces se
ejecuta el turno con el contenedor en vivo. Al terminar se guarda el turno, se borra el pendiente
y `st.rerun()`.

**Por qué**: Streamlit interrumpe la ejecución en curso cuando el usuario interactúa. Si eso
pasara a mitad de un turno, se cortaría la `query()` del coordinador con el caso a medias. Con la
entrada deshabilitada no hay interacción que lo provoque (caso límite de la spec).

**Async**: cada turno con `asyncio.run(...)` en el hilo del script, como ya hace `__main__` en
cada turno. `Caso.continuar` funciona entre bucles distintos porque el CLI ya lo hace así (#10).

## R8. Credencial (FR-006)

**Decisión** (ajustada por la analista: una sola función para los dos puntos de entrada): al
arrancar, `chat.py` llama a `dependencias.cargar_entorno()` (por defecto
`configuracion.cargar_entorno`, `load_dotenv(override=False)`) y `__main__.py` a
`configuracion.cargar_entorno()`; los dos llaman después a la misma función pura
`configuracion.comprobar_credencial(entorno=None) -> str | None` (con `None` lee `os.environ`,
como `modo_demostracion`):

- `ANTHROPIC_API_KEY` ausente o vacía → mensaje con los pasos: copiar la plantilla de variables
  de entorno de la raíz como archivo de entorno local, poner la clave en `ANTHROPIC_API_KEY` y
  reiniciar la aplicación. **El mensaje no nombra el archivo** (desviación D1 del plan): ningún
  módulo lo nombra, por la garantía R8 del #6 que fija `test_sin_control_propio.py`. Remite al
  README, que da los nombres.
- definida alguna variable que el CLI de Claude Code usa **antes** que `ANTHROPIC_API_KEY`
  (`ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`) → mensaje que pide
  quitarla, porque la aplicación solo usa `ANTHROPIC_API_KEY`.

Con un problema:
- **chat**: `st.error(mensaje)` y `st.stop()`: no se dibuja la entrada, no se crea ningún caso,
  no se llama al modelo;
- **línea de comandos**: el mismo mensaje en la salida de error y código de salida 2 (el de un
  error de uso), antes de crear el caso; no se llama al modelo.

El valor de la clave no se muestra nunca. Tests: la función pura (clave ausente, vacía, presente,
y cada variable alternativa), el chat con `AppTest` y `main()` de la línea de comandos, cada uno
sin clave y con una credencial alternativa. Los tests existentes de `test_main.py` que llegan a
crear el caso fijan una clave ficticia en el entorno con `monkeypatch` (adaptación, no
debilitamiento).

**Por qué la segunda comprobación**: con `ANTHROPIC_API_KEY` definida, el CLI la usa antes que el
inicio de sesión de Claude Code o un token OAuth; solo ganan las de la lista, según la precedencia
documentada de Claude Code *(a medir: no se midió; si la documentación cambia, la lista se
ajusta)*. Sin esto, «ninguna otra credencial» dependería de lo que haya en el entorno.

`__main__.py` deja de ser «el ÚNICO lugar que carga el entorno»: ahora son los dos puntos de
entrada; el paquete, `ejecutar_caso` y los tests siguen sin cargarlo. Se actualizan el docstring
y el README.

## R9. Hora de Colombia y fecha UTC del registro (FR-007)

**Decisión**:
- `hora_colombia(marca) -> "HH:MM:SS (hora de Colombia)"` con una zona fija
  `timezone(timedelta(hours=-5))`. Colombia no tiene horario de verano, y así no hace falta
  `tzdata` en Windows (`zoneinfo("America/Bogota")` falla sin ese paquete). La traza y los
  registros siguen en UTC (#9, R10).
- El coordinador: una regla nueva `_REGLA_FECHAS` en sus instrucciones, en los dos modos:
  «Escribe todas las fechas como AAAA-MM-DD. La fecha que devuelve la pasarela al guardar un
  informe o un caso para el oficial está en UTC y puede ser la del día siguiente en Colombia: no
  la presentes como una fecha posterior a hoy ni como una anomalía.» Un test fija el texto. **No
  nombra `escalar_a_cumplimiento`**: un test del #7 garantiza que el modo de demostración no lleva
  ninguna mención a escalar, y la regla va en los dos modos.

**Garantía**: es guía (principio II: comprensión y estilo, no una regla de negocio). Lo
garantizado en código es lo que dibuja la interfaz. *(a medir)* El caso (b) de noche en el
quickstart.

**Alternativa descartada**: que la pasarela devuelva la fecha de Colombia. Cambia el contrato del
#5 y la decisión de UTC del #9 para corregir una frase del modelo.

## R10. Formato de fechas (FR-008)

**Decisión**: `AAAA-MM-DD` en todo lo que dibuja la interfaz (las fechas que ya vienen así de las
fuentes y de los conflictos no se reformatean) y en la regla `_REGLA_FECHAS` del coordinador
(R9). Las horas van aparte, con R9.

## R11. Textos neutros en las sustituciones (FR-009)

**Decisión**: en `hooks.py`:
- `cobertura_sustituida`: si la declarada no coincide (distinta **u omitida**), «Se sustituyó por
  la calculada.»; si coincide, se mantiene «Coincide con la declarada por el coordinador.».
- `datos_sustituidos`: «Datos del código puestos en {herramienta}: comercio verificado. {resumen
  de conflictos} …». El punto y coma pasa a punto, porque el resumen de conflictos es una frase
  con mayúscula. Si no coincide: «Se sustituyeron por los calculados: {campos}.»; si coincide,
  «Coincide con lo declarado por el coordinador.».

Los tests que fijan esos textos (`test_hooks.py:1757` y los que se encuentren al construir) se
adaptan con igualdades exactas, sin debilitarse.

## R12. Modos de simulación visibles (FR-010)

**Decisión**: `modos_activos(entorno) -> list[str]`, pura, con el valor exacto `1` como en el
servidor y en `configuracion.modo_demostracion`:
- `PASARELA_FALLA_NOTICIAS` → «Caída simulada de noticias activa (caso f).»
- `PASARELA_FALLA_REGISTRO` → «Caída simulada del registro mercantil activa.»
- `PASARELA_MODO_DEMO_HOOKS` → «Modo de demostración de hooks activo (caso e): las reglas no
  están en las instrucciones del coordinador; los hooks siguen activos.»

La interfaz los muestra en una franja fija arriba de la conversación, en cada ejecución. Se leen
del entorno al arrancar (decisión de la analista); para cambiarlos hay que reiniciar la
aplicación con la variable, como dice el README.

## R13. Pruebas de la aplicación sin modelo

**Decisión**: `streamlit.testing.v1.AppTest.from_file(".../chat.py")`, con
`session_state["dependencias"]` inyectado antes de `run()`:
- `crear_caso` construye un `Caso` con `CoordinadorSimulado(guiones=[...])` y `EjecutorSimulado`,
  como `test_casos_escalamiento.py`;
- `entorno` con una clave ficticia (`"clave-ficticia-de-prueba"`) y, según el test, los modos;
- `cargar_entorno` que no hace nada.

Se prueban: el caso (d) en dos turnos, el caso (a) con sus indicadores, el (f) con la cobertura
antes de la respuesta, la parada sin clave, caso completo → caso nuevo, y el botón «Caso nuevo».
*(a medir, T033)* De la medición, **solo el envío de espacios queda como test** (decide la rama de
FR-005). Lo demás se anota aquí, sin test:
- qué elementos expone `AppTest` para `st.status`, `st.chat_message`, `st.error` y `st.info`; si
  alguno no se puede inspeccionar, el test comprueba el texto en `markdown`, y el orden se prueba
  en las funciones puras;
- si `AppTest` procesa un `pendiente` sembrado en la misma ejecución. Si lo procesa, la entrada
  deshabilitada (R7) se comprueba a mano en Q4.

**Medido (T033, con una app de prueba fuera del repositorio)**:
- `AppTest` expone `chat_input` (con `disabled`), `chat_message` (con `name`: `user` o
  `assistant`), `status`, `info`, `error`, `caption`, `button` (con `disabled`) y `markdown`. Los
  hijos de un `chat_message` se recorren en orden (`children`), así que el orden cobertura →
  respuesta se comprueba por posición.
- Con un `pendiente` sembrado en una app que no lo procesa, la entrada y el botón salen
  deshabilitados. En `chat.py` el pendiente se procesa en la misma ejecución, que termina con
  `st.rerun()`, y `AppTest` solo deja ver el estado final, ya habilitado: la entrada deshabilitada
  **durante** el turno no se puede comprobar con `AppTest` y queda como comprobación manual en Q4
  (C1 del analyze).

`CoordinadorSimulado` se amplía con `num_turns` por guion y un paso `("lanzar", excepcion)` (U1
del analyze), con su test, para los turnos por turno y el fallo del turno.

`streamlit` se añade a las dependencias del proyecto con `uv add`: `streamlit>=1.66,<2` en `pyproject.toml`, 1.66.0 en `uv.lock` (T002).

## R15. Configuración de Streamlit (validación manual)

**Decisión**: `.streamlit/config.toml` en la raíz, con `browser.gatherUsageStats = false` y
`server.showEmailPrompt = false`.

**Por qué**: la primera ejecución de Streamlit en un equipo pregunta un correo en la terminal
(«Welcome to Streamlit! … Email:») y no arranca hasta pulsar Enter; un evaluador puede creer que
se colgó. **Medido** (Streamlit 1.66.0, `runtime/credentials.py`, `check_credentials`):
`gatherUsageStats` no la quita; solo la omiten `server.headless` o `server.showEmailPrompt = false`.
Se eligió `showEmailPrompt` porque `headless` además deja de abrir el navegador.

Comprobado en un arranque real con un perfil de usuario sin credenciales de Streamlit: sin la
configuración aparece la pregunta; con ella, no, y el navegador se abre solo. El README dice qué
hacer si aun así aparece (dejar el correo vacío y pulsar Enter; la aplicación queda en
http://localhost:8501).

**Alternativa descartada**: `server.headless = true`, porque el analista tendría que abrir la
dirección a mano.

## R16. Una afirmación de listas por autoridad (validación manual)

**Decisión**: `_REGLA_AFIRMACIONES`, en los dos modos, añade: «En listas restrictivas, escribe una
afirmación por cada autoridad consultada, cada una con su propia fuente; no juntes varias
autoridades en una sola afirmación.».

**Por qué**: en 4 de los 7 casos de la validación, el hook (I.4) rechazó el primer informe por
juntar varias autoridades en una afirmación con una sola fuente. Es guía de estilo (principio II):
la garantía sigue siendo el hook. No menciona el escalamiento, así que puede ir en el modo de
demostración.

## R14. Riesgos residuales

1. **FR-007 y FR-008 en el texto del modelo** son guía, no garantía (R9, R10). El caso (b) de
   noche (US5-2) **no se pudo observar** en la validación manual: fue después de medianoche, cuando
   la fecha local y la UTC coinciden (T043). Solo lo fija el test del texto de `_REGLA_FECHAS`.
2. **El observador en vivo** depende de que los eventos lleguen en el hilo del script (R1); si
   no, se pierde la vista en vivo, nunca el turno guardado.
3. **La precedencia de credenciales** del CLI no se midió (R8).
4. **Recargar la página pierde el caso** (estado en memoria; spec).
5. **Un caso incompleto se continúa con el mensaje siguiente** (por ejemplo, tras el caso f): la
   conversación lo deja ver y el analista usa «Caso nuevo» (decisión de la analista).
6. **El detalle de la delegación se decide por el texto de `delegacion.py`** («Se reintenta…»,
   «…con otra entrada»): si ese texto cambia, lo detectan los tests con eventos reales del
   `Delegador` (casos f y d), no el tipo del evento.
7. **El coste por caso no se ve en el chat** (desviación D2 del plan).

## DECISIONES.md

En este ticket solo se añade **una entrada corta del #11** (decisión de la analista); el #14 lo
reescribe completo. Lo que sigue queda registrado aquí y en `plan.md` como pendiente fuera de
alcance, y la entrada corta remite a este archivo.

## Pendiente fuera de alcance de este ticket

- D7 del #9: el comercio pedido pierde el nombre con el registro caído y la consulta solo por
  identificador.
- La redacción de `RESUMEN_REGISTRO_CAIDO` para todas las causas (`terminacion_anomala`,
  `cancelado`).
- Las 14 sugerencias de la revisión del PR #26 (entre ellas `informe.py:158`,
  `escalamiento_cubre` con el comercio por defecto, las tres duplicaciones, el test de dos turnos
  de US3-9 y R13.10).
- El evento de espera que ya no queda en la traza con el registro sin delegar.
- Mejoras de la interfaz: persistencia de casos entre sesiones, un control de los modos de
  simulación dentro del chat y diseño visual.
