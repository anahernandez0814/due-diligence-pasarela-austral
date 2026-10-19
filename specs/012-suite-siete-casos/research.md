# Research: Suite de los siete casos de prueba obligatorios (#12)

Decisiones del plan, con lo medido en el código (sin llamar al modelo) y lo que queda *(a medir)*
en la implementación. Versiones: `claude-agent-sdk` 0.2.168, `streamlit` 1.66.0, Python 3.12.

---

## R1. Los siete casos en paralelo, en un solo bucle de eventos

**Decisión**: una fixture de sesión, `ejecuciones`, ejecuta **solo los casos seleccionados** con
`asyncio.gather` dentro de un único `asyncio.run`. Cada caso es un `Caso` propio con su `entorno`
(R5) y su carpeta de registros. Cada test lee el resultado de su caso, una `Observacion` (R6) o el
error con el que terminó.

- **Concurrencia**: un `asyncio.Semaphore` con `PASARELA_E2E_PARALELO`, por defecto 7: todos a la
  vez. Con 7, en el peor momento conviven unos 28 procesos del CLI (el coordinador y hasta tres
  subagentes por caso, porque listas espera al registro) *(a medir: memoria y tiempo en la primera
  ejecución)*.
- **Tiempo límite por caso**: `asyncio.timeout(240)`, en segundos. Un caso colgado falla con
  «tiempo agotado» sin retener a los demás, y el grupo termina por debajo de 5 minutos aunque un
  caso no responda. El caso (d) cuenta sus dos turnos dentro del mismo límite.
- **Independencia**: `gather(..., return_exceptions=True)`. El fallo de un caso no cancela a los
  otros; su test falla con el error y los demás se evalúan.
- **Tiempo esperado**: el del caso más lento (de 1 a 3 minutos por turno con Opus 5.5; el caso (d)
  tiene dos turnos) más el arranque. *(a medir: la primera ejecución completa fija el número del
  README.)*

**Por qué**: siete casos seguidos tardarían de 7 a 21 minutos. En un solo bucle no hace falta
ninguna dependencia nueva, el coste se suma en un solo sitio (R8) y la selección por `-k` funciona
sin más (R3).

**Alternativas descartadas**:
- `pytest-xdist` (`-n 7`): una dependencia nueva y siete procesos de Python, cada uno con su
  `asyncio.run`, y el coste repartido entre procesos. La selección por `-k` funcionaría igual.
- En serie: no cabe en 5 minutos.
- Un `asyncio.run` por test, con los tests en orden: es la serie de nuevo.

## R2. Si el servicio limita la tasa

**Decisión**: la suite **no reintenta**. El CLI ya reintenta los 429 y 529 con espera exponencial
antes de rendirse *(a medir: si en la primera ejecución aparece algún reintento, se anota)*. Si se
agotan:

- el `ResultMessage` del turno llega con error, o el SDK lanza la excepción, y el `Caso` clasifica
  el turno como anómalo, como siempre;
- el test falla con un mensaje que dice la clasificación del turno (`terminación anómala: …`), el
  coste gastado y cómo repetir solo ese caso (R3);
- si se repite, se baja la concurrencia: `PASARELA_E2E_PARALELO=3`. Con 3, el grupo puede pasar de
  5 minutos y el README lo advierte.

**Por qué**: un reintento dentro del test escondería la inestabilidad y gastaría sin que nadie lo
decida. El presupuesto del ticket son dos ejecuciones completas.

## R3. Volver a ejecutar un solo caso

**Decisión**: la fixture lee `request.session.items`, que son los tests que quedaron después de
`-k` y `-m`, y ejecuta solo sus casos. El nombre de cada test lleva la letra:
`test_caso_a_alto_riesgo`, `test_caso_b_bajo_riesgo`, …, `test_caso_g_fechas_distintas`.

```bash
uv run pytest -m e2e -rs -k caso_d        # solo el (d): el coste de un caso
uv run pytest -m e2e -rs -k "caso_a or caso_f"
uv run pytest -m e2e -rs --lf             # solo los que fallaron en la última ejecución
```

Un caso que falla se repite con su `-k`, que no cuenta como ejecución completa del presupuesto.

## R4. La marca `e2e`, excluida por defecto

**Decisión**: en `pyproject.toml`, `markers = ["e2e: …"]` y `-m "not e2e"` en `addopts`. Así:

- `uv run pytest` no selecciona ningún test `e2e`, tenga o no la clave;
- `uv run pytest -m e2e -rs` los selecciona, porque el último `-m` de la línea de comandos sustituye
  al de `addopts` *(comportamiento de pytest a comprobar con un test de la configuración en la
  implementación)*.

Un test determinista lee la configuración de pytest y comprueba que `e2e` está registrada y que la
selección por defecto la excluye: si alguien quita el `-m` de `addopts`, falla sin la clave.

## R5. La credencial, la omisión sin clave y el entorno de cada caso

**Credencial**: la fixture llama a `configuracion.cargar_entorno()`, la misma carga sin pisar el
entorno que usan el chat y `__main__`, y después a `configuracion.comprobar_credencial()`. Si
devuelve un problema (falta `ANTHROPIC_API_KEY`, está vacía o hay otra credencial que el CLI usaría
antes), **cada test e2e se omite** con `pytest.skip(<el mensaje de la credencial>)`, sin crear
ningún caso. El motivo se ve con `-rs`, que lleva el comando del README.

- Claude Code sigue sin poder leer `.env`: el archivo lo lee el proceso de pytest en ejecución,
  como lo leen el chat y `__main__`.
- El README advierte que «skipped» no significa que pasó.

**Entorno de cada caso** (FR-005): `Caso(entorno=…)` recibe una copia de `os.environ` sin
`PASARELA_FALLA_NOTICIAS`, `PASARELA_FALLA_REGISTRO`, `PASARELA_MODO_DEMO_HOOKS` ni
`PASARELA_RESULTADOS_DIR`, y con:

- `PASARELA_RESULTADOS_DIR`: una carpeta propia del caso, de `tmp_path_factory`. Los informes y
  escalamientos no se mezclan con `resultados/` ni con los de otro caso;
- `PASARELA_FALLA_NOTICIAS=1`, solo en el (f);
- `PASARELA_MODO_DEMO_HOOKS=1`, solo en el (e).

El `entorno` del `Caso` ya llega al servidor de la pasarela (`configuracion.servidor_pasarela`
reenvía `VARIABLES_PASARELA`), al modo de demostración (`Caso.demo`) y a los modelos. La clave la
toma el CLI del entorno del proceso, como siempre. **Nada modifica `os.environ`**, salvo la carga
de `.env` sin pisar nada.

## R6. Lo que se observa: `Observacion`, sin texto libre

**Decisión**: un módulo nuevo, `src/due_diligence/observacion.py`, con funciones puras que
convierten un `Caso` terminado (y su carpeta de registros) en una `Observacion` inmutable. Los tests
e2e **solo reciben `Observacion`**: nunca ven el `Caso`, su `respuesta` ni ningún texto del modelo.
Detalle en [data-model.md](data-model.md).

Fuentes de la observación, todas escritas por el código:

1. **Traza**: de cada evento, `tipo`, `frente`, `regla` y `accion`. El `detalle` no se copia.
2. **Consultas, en orden**: frente, herramienta y solo los argumentos que identifican (`nombre`,
   `identificador`, `tipo`), más la clase del registro (`clase_de`) en las del registro.
3. **Libro de reglas**: consultas de listas válidas (tipo, nombre, identificador) y causas de cada
   escalamiento.
4. **Registros de la pasarela** (las llamadas a `registrar_informe` y `escalar_a_cumplimiento` que
   aceptó): de la carpeta del caso, la recomendación, la cobertura (la que fija el hook,
   `hooks.py:1099` y `hooks.py:1154`), los conflictos y las causas. **No** se copian `hallazgos`,
   `accion_recomendada` ni ningún texto redactado por el modelo.
5. **Estado calculado**: cobertura por frente (cubierto o no, con su `Causa`), `completo`, la espera
   (`clase` y `motivo`, que son constantes del código), el comercio identificado (identificador y
   nombre de los datos ficticios) y la terminación de cada turno.
6. **Métricas**: coste (el del coordinador más el de cada subagente, como en `__main__`), turnos
   por turno y duración.

En el caso (d), la fixture toma una `Observacion` al terminar cada turno.

**Por qué un módulo propio**: es la frontera que garantiza FR-003. Es puro, se prueba sin modelo con
`CoordinadorSimulado` (los siete casos simulados producen la `Observacion` esperada) y mantiene los
tests e2e cortos.

## R7. Comprobar sin modelo que ninguna verificación lee el texto (FR-003, SC-002)

Dos tests deterministas en `test_observacion.py`:

1. **La observación no tiene texto libre**: los campos de `Observacion` y de sus partes son un
   conjunto cerrado, que el test compara con igualdad exacta. Ninguno se llama `respuesta`,
   `detalle`, `resumen`, `hallazgos`, `accion_recomendada`, `texto` o `mensajes`. Además, con un
   `CoordinadorSimulado` cuya respuesta y cuyos textos de afirmaciones llevan una marca única
   (`«TEXTO-LIBRE-…»`), `repr(observacion)` no contiene la marca.
2. **Los tests e2e no pueden llegar al texto**: un análisis AST de `test_e2e_casos.py` comprueba
   que:
   - solo importa `pytest` y `due_diligence.observacion`;
   - no nombra `Caso`, `respuesta`, `detalle`, `resumen`, `hallazgos`, `accion_recomendada`,
     `texto` ni `mensajes`, ni como atributo ni como cadena;
   - no usa `in`, `startswith` ni expresiones regulares sobre cadenas que no sean constantes del
     código importadas de `observacion` (por ejemplo, `MOTIVO_ESPERA_IDENTIFICADOR`).

Si alguien añade una verificación sobre el texto, falla `uv run pytest`, sin la clave.

## R8. Coste y tiempo de cada ejecución

`Observacion.metricas` lleva el coste y la duración de cada caso. Un `pytest_terminal_summary` en
`src/due_diligence/conftest.py` imprime, tras el grupo e2e, una línea por caso y el total:
`e2e caso (a): 0,21 USD, 96 s`.

- El coste es aproximado, igual que en `__main__`: el coordinador más el último resultado de cada
  frente. Un frente delegado dos veces cuenta solo su última ejecución. Se declara en el README.
- Los números de las (como máximo) dos ejecuciones completas se anotan en `tasks.md`, en el
  quickstart (Q3) y, redondeados, en el README.

## R9. La interrupción de la interfaz durante un hook (FR-008)

### Lo medido en el código

- **Dónde nace**: Streamlit lanza `StopException` o `RerunException`, las dos subclases de
  `streamlit.runtime.scriptrunner_utils.exceptions.ScriptControlException(BaseException)`, en
  cualquier llamada `st.*` del hilo del script cuando hay una petición pendiente
  (`script_runner.py:522`, `_maybe_handle_execution_control_request`). Durante un turno, la única
  llamada `st.*` es la del observador del chat (`chat.py:53`, `_mostrar_en_vivo`), que corre dentro
  de `RegistroEventos.registrar`. Lo llaman los hooks, el manejador de la herramienta
  `delegar_frente` y el propio `Caso`.
- **Dónde se pierde hoy**: el SDK ejecuta cada hook en una tarea suelta (`query.py:380`,
  `spawn_task` → `loop.create_task`) y solo atrapa `Exception` (`query.py:692`).
  `ScriptControlException` atraviesa `registrar` (`eventos.py:134`, `except Exception`) y
  `fallar_cerrado` (`hooks.py:452`), queda guardada en esa tarea y nadie la recoge. Así:
  - el SDK **no escribe ninguna respuesta** al CLI, ni la denegación de I.1 o I.2 ni un error, y el
    CLI se queda esperando la decisión del hook *(lo que hace el CLI al vencer esa espera no está
    medido: no se puede suponer que deniegue)*;
  - el «Stop» del analista **se pierde**: el turno sigue trabajando y gastando.
- **`STOP` y `RERUN` no se comportan igual**: con `STOP`, cada llamada `st.*` siguiente vuelve a
  lanzar la excepción (`script_requests.py:442`, «remain stopped»). Con `RERUN`, la petición se
  entrega **una sola vez** y el estado vuelve a `CONTINUE`. Si se traga, la recarga se pierde para
  siempre: hay que guardar **ese objeto** y relanzarlo.
- **La respuesta del hook sale antes de que el turno despierte cancelado** (corregido en la
  revisión del plan): cuando el hook devuelve, el SDK convierte la salida y llama a
  `transport.write` (`query.py:648-683`). La escritura **sí cede el control una vez**:
  `_write_lock` es un `anyio.Lock()` sin `fast_acquire` (`subprocess_cli.py:253`), y su `acquire`
  cede con un punto de control protegido (`anyio/_backends/_asyncio.py:1963`) antes de escribir. El
  orden se mantiene igual:
  - el `loop.call_soon(tarea_del_turno.cancel)` se programa antes de que el hook devuelva;
  - `cancel()` no corta nada en el momento: solo programa que la tarea del turno despierte con la
    cancelación;
  - ese despertar queda en la cola **detrás** de la reanudación de la tarea del hook, que ya cedió
    dentro de `acquire`;
  - la tarea del hook se reanuda, escribe la respuesta y suelta el candado. Solo después despierta
    el turno cancelado y empieza el cierre de la `query()`.

### Decisión

1. **Qué se captura**: solo las clases que el punto de entrada declara como interrupciones. El chat
   pasa `interrupciones=(ScriptControlException,)` al `Caso`, y este a `RegistroEventos`.
   `eventos.py` no importa Streamlit; la línea de comandos no declara ninguna y no cambia.
2. **Dónde se captura**:
   - **Punto principal**, `RegistroEventos.registrar`, alrededor del observador:
     `except self._interrupciones`. Guarda **la primera** interrupción en `interrupcion`, apaga el
     observador (no más llamadas `st.*` en el turno) y devuelve el evento con normalidad, así que el
     hook sigue y decide como siempre. `except Exception` sigue ignorando los errores del
     observador (#11). `asyncio.CancelledError`, `KeyboardInterrupt` y `SystemExit` siguen
     propagándose.
   - **Cinturón**, `fallar_cerrado`: si una interrupción declarada escapara del cuerpo del hook, se
     captura igual y el hook falla cerrado. En `PreToolUse` deniega con `MOTIVO_FALLO_DE_HOOK`, sin
     sellar el caso, porque no es un fallo de las reglas. En los demás tipos, permite, porque el
     turno se corta enseguida.
3. **Cuándo se relanza**: en cuanto el hook devuelve su decisión, no al final del turno.
   - `fallar_cerrado` marca con una `ContextVar` que está dentro de un hook. Si al terminar el hook
     hay una interrupción guardada, llama a `eventos.interrumpir()` justo antes de `return`.
   - Fuera de un hook (el `Caso` o el `Delegador`), `registrar` llama a `interrumpir()` en el
     momento.
   - `interrumpir()` llama al aviso que el `Caso` registró al empezar el turno:
     `loop.call_soon(tarea_del_turno.cancel)`. Por lo leído arriba, el turno despierta cancelado
     después de que el SDK escribió la respuesta del hook, aunque la escritura ceda una vez en el
     candado.
   - `Caso._turno` atrapa la `CancelledError` **solo si** hay una interrupción guardada. Llama a
     `uncancel()`, clasifica el turno como `ANOMALA` con el detalle `interrumpido por la interfaz`
     y relanza **el mismo objeto** guardado. Sin interrupción guardada, la `CancelledError` sigue
     como siempre.
   - Al cerrar la `query()`, el SDK cancela sus tareas, incluidos los subagentes en curso, y cierra
     el CLI. Ninguna acción pendiente llega a ejecutarse.
   - `asyncio.run` relanza la interrupción en el hilo del script. En `chat.py`, `_ejecutar_turno`
     la atrapa solo para:
     - guardar el turno en el historial como interrumpido;
     - **quitar el mensaje pendiente**, porque si no la siguiente ejecución del script repetiría el
       turno y volvería a gastar.

     Después la relanza, y Streamlit para o recarga.
4. **Por qué `asyncio.CancelledError` queda fuera**:
   - Es la señal de cancelación cooperativa de `asyncio` y el SDK la usa para abandonar una
     petición. `query.py:686` dice «the CLI has already abandoned this request, so don't write a
     response»: no queda nadie esperando una decisión que entregar.
   - Tragarla rompe la cancelación. La tarea seguiría viva; `asyncio.timeout`, `TaskGroup` y el
     cierre de `asyncio.run` se colgarían o mentirían; y el propio mecanismo de este R9, que corta
     el turno cancelándolo, dejaría de funcionar.
   - Es la decisión del #8, escrita en la documentación de `fallar_cerrado`: «Atrapa `Exception`,
     no `BaseException`: una cancelación del frente se propaga».
   - `KeyboardInterrupt` y `SystemExit` quedan fuera por lo mismo: terminan el proceso, y con él el
     CLI.

### Trade-off

Cambian `eventos.py`, `hooks.py` (`fallar_cerrado`), `coordinador.py` (`_turno`) y `chat.py`: unas
40 líneas en módulos que audita `/abrir-pr`. A cambio:

- la denegación de I.1 e I.2 sale siempre;
- el «Stop» corta el turno en cuanto el hook decide;
- la recarga no se pierde;
- nada de eso depende de cómo trate el CLI un hook sin respuesta.

**Alternativas descartadas**:
- **Atrapar `BaseException` y tragarla**: la denegación sale, pero el «Stop» y la recarga se
  pierden y el turno sigue gastando. Va contra el ajuste 4 de la analista.
- **Relanzar al final del turno**: la descartó la analista, porque el analista esperaría y pagaría
  minutos de trabajo.
- **Que el observador solo encole y dibujar desde otra tarea**: la interrupción ya no nacería en un
  hook, pero cortar el turno desde esa tarea cancelaría también los hooks en curso antes de que
  respondieran. Habría que contar los hooks en vuelo para esperar a que terminaran: más piezas para
  el mismo resultado.

### Tests (sin modelo)

- **`test_eventos_estado.py`**: con una `Interrupcion(BaseException)` de prueba declarada,
  `registrar` devuelve el evento, guarda la primera interrupción, no vuelve a llamar al observador
  y llama a `interrumpir` fuera de un hook. `CancelledError` y `KeyboardInterrupt` del observador se
  propagan, y `Exception` se sigue ignorando.
- **`test_hooks.py`**:
  - el `PreToolUse` de listas sin identificación, envuelto, con un observador que lanza la
    interrupción, devuelve **la denegación de I.1** (no la genérica) y avisa después de decidir;
  - lo mismo con el `PreToolUse` del informe con `habilitar` en un caso con coincidencia (I.2);
  - si el cuerpo del hook lanza la interrupción, se deniega con el motivo genérico y sin sello;
  - una `CancelledError` del cuerpo se propaga.
- **`test_coordinador.py`**: un `Caso` con una `consulta` falsa que, como el SDK, ejecuta el hook de
  `delegar_frente` (listas) **en una tarea suelta** y escribe la decisión **a través de un
  `anyio.Lock()`**, que cede igual que el `_write_lock` del SDK. Así el test fija el orden real y
  no uno ideal. Después espera 60 s:
  - `ejecutar` lanza la interrupción en menos de 2 s;
  - la decisión guardada es la denegación de I.1;
  - el turno queda `ANOMALA` (`interrumpido por la interfaz`) y el caso no está completo;
  - sin interrupción, una cancelación externa sigue siendo `CancelledError`.
- **`test_chat.py`**:
  - con un `Caso` simulado cuyo turno lanza `StopException`, la ejecución de `AppTest` termina, no
    queda el mensaje pendiente y el historial guarda el turno como interrumpido;
  - un test fija la ruta de importación y la jerarquía: `StopException` y `RerunException` heredan
    de `ScriptControlException`, que hereda de `BaseException` y no de `Exception`. Si Streamlit lo
    cambia, este test falla.

**Riesgo residual**: el orden entre escribir la respuesta y despertar el turno cancelado se apoya en
la lectura del SDK 0.2.168 y de anyio. El test de `test_coordinador.py` lo fija con una tarea suelta
y un `anyio.Lock()` como el del SDK, pero no con el transporte real. Si el SDK cambiara y la
escritura se cortara, el CLI se cierra en ese mismo momento, ninguna acción llega a ejecutarse y el
bloqueo ya está en la traza. Se declara en el plan.

### El mensaje siguiente a una interrupción (decisión de la analista, opción A)

Tras un turno interrumpido, el siguiente mensaje del analista **abre un caso nuevo** con un aviso
visible. Reutiliza el caso nuevo del #11 (`Decision.NUEVO` con su aviso): «El turno anterior se
interrumpió; se inició un caso nuevo.». **Nunca reanuda** una sesión cortada a mitad de una
herramienta.

- **Cómo**: `Caso.interrumpido`, que es verdadero si el último turno terminó por una interrupción.
  `presentacion.decidir_mensaje` lo mira antes que la espera y que el estado completo.
- **Trade-off**: el analista vuelve a escribir el nombre del comercio. Es un caso raro (pulsar
  «Stop» a mitad de un turno). A cambio, nunca se continúa una sesión del coordinador que quedó con
  una llamada a herramienta sin resultado, cuyo estado en el CLI no está medido. Va a DECISIONES.md
  en una línea.
- **Test**: en `test_chat.py`, tras un turno simulado que lanza `StopException`, el siguiente
  mensaje crea un caso nuevo (el `crear_caso` se llama otra vez) y la conversación muestra el
  aviso. En `test_presentacion.py`, `decidir_mensaje` con un caso interrumpido devuelve
  `Decision.NUEVO` con el aviso.

## R10. La fuente por defecto de noticias en el `EjecutorSimulado` (FR-009)

Medido: sin un resultado asignado, `EjecutorSimulado._resultado` construye la consulta de noticias
con `consulta(frente, argumentos, respuesta_noticias(argumentos))`. Si el comercio no aparece en
N-0001, `respuesta_noticias` devuelve `None`, y `consulta` usa `respuesta_del_contrato(...)` con la
`FUENTE` del módulo, «Registro Mercantil Ficticio del Sur» (`simulacion.py:26` y `:74`).

**Decisión**:
- una constante `FUENTE_NOTICIAS = "Diario Ficticio del Sur"`, la misma que ya usa N-0001;
- `respuesta_noticias` devuelve, sin mención, `respuesta_del_contrato("sin_coincidencias", [],
  fuente=FUENTE_NOTICIAS)` en vez de `None`;
- `consulta()` sigue con su valor por defecto para los demás frentes;
- un test nuevo fija la fuente en el hecho y en los metadatos;
- los tests que dependían de la fuente anterior se adaptan con igualdades exactas y se listan en
  `tasks.md` *(a buscar en la implementación: un primer barrido no encontró ninguno que compare la
  fuente de noticias)*.

## R11. Tiempo de la suite determinista

Medido el 2026-10-19 en el equipo de la analista: **4711 tests en 264 s (4:24)**. Está por debajo de
5 minutos, pero con poco margen, y este ticket añade tests. Una segunda ejecución, con
`--durations=25`, tardó 278 s (4:38). Los más lentos son los tests de las guardas de
`.claude/hooks/` que crean repositorios git de prueba: 1 a 3 s cada uno, unos 45 s entre los 25. El
resto del tiempo se reparte entre los miles de tests rápidos.

**Decisión**: medir con `--durations` después de la implementación. Si el grupo pasa de 4:45, se
aceleran los tests más lentos sin quitar aserciones, o se declara la desviación. El README da el
número medido.

## R12. Documentación y cierre

- **README, sección «Pruebas»**:
  - los dos comandos: `uv run pytest` y `uv run pytest -m e2e -rs`;
  - repetir un caso (`-k caso_d`) y la variable `PASARELA_E2E_PARALELO`;
  - el tiempo medido de cada grupo y el coste aproximado de una ejecución completa;
  - la advertencia de que «skipped» no es «pasó»;
  - que las pruebas e2e escriben en carpetas temporales, no en `resultados/`.
- **`DECISIONES.md`**: una sola entrada corta del #12. Lleva la suite e2e en paralelo con
  `Observacion` como frontera y la interrupción de Streamlit (R9). Lo pendiente queda listado: US3-9
  del #10, las sugerencias de los PR #26 y #27, D7, `RESUMEN_REGISTRO_CAIDO` y el caso (b) de noche.
- **T046 del #11**, marcada en `specs/011-interfaz-chat/tasks.md`.
