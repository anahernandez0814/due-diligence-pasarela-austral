# Investigación: Coordinador y subagentes con el Agent SDK

Todo lo marcado *(medido)* se comprobó el 2026-10-17 con `claude-agent-sdk` 0.2.168 y
`python-dotenv` 1.2.4 en un entorno temporal (`uv run --no-project --with …`), fuera del
repositorio, contra el servidor `pasarela` del #5 y modelos reales. Ningún sondeo leyó `.env`.

## R1. Dónde se simulan los subagentes: opción (a), herramienta de delegación propia

**Decisión**: el coordinador delega con **una herramienta propia**, `delegar_frente`, expuesta como
servidor MCP en proceso (`create_sdk_mcp_server`). Cada delegación lanza al subagente con **su propio
`query()`**, a través de un **ejecutor inyectable** (`EjecutorSubagente`). En producción el ejecutor
es `EjecutorSDK`; en los tests, un ejecutor simulado con retardos controlados.

**Por qué**:
- **FR-002 se cumple a la letra**: el coordinador solo ve `delegar_frente`, `registrar_informe` y
  `escalar_a_cumplimiento`. Con la opción (b) (subagentes nativos con `AgentDefinition`) el
  coordinador necesita la herramienta nativa de subagentes del SDK, cuyo alcance no
  controlamos: en principio puede lanzar cualquier agente definido, y el SDK lista los integrados
  (`Explore`, `general-purpose`, `Plan`…) aunque `tools=[]` *(medido: lista inicial)*, no solo los
  cuatro frentes. No se midió que los lance; basta que la herramienta no sea la nuestra.
- **El test de solape exigido por el issue es posible**: con (b) el subagente es un proceso del
  modelo y el solape solo se vería con una llamada real. Con (a) el ejecutor se sustituye y el
  solape se verifica con eventos de un caso completo y subagentes simulados (SC-003).
- **Las dependencias se hacen cumplir en código**, no por la instrucción al modelo: la herramienta
  sabe qué frentes ya terminaron (R4).
- **El contexto explícito (FR-004) es estructural**: cada `query()` arranca una sesión nueva; el
  subagente solo recibe el `prompt` que el código construye (R11).

**Alternativa descartada**: (b). Tiene a su favor menos código y las transcripciones de subagentes
del SDK; pero no permite inyectar un ejecutor, no impide por construcción que el coordinador lance
otros agentes y deja el orden de listas a la voluntad del modelo.

**Coste de (a)**: no se usan las funciones propias de subagentes del SDK (por ejemplo, su
transcripción aparte); el registro de eventos propio (R7) cubre lo que la interfaz necesita.

## R2. Aislamiento del entorno de desarrollo: `setting_sources=[]` en toda opción *(medido)*

**Decisión**: **toda** construcción de opciones (coordinador y los cuatro subagentes) pasa por una
única función (`configuracion.opciones_base`) que fija `setting_sources=[]`, `tools=[]` y
`strict_mcp_config=True`. Un test comprueba que ninguna opción construida por el paquete se aparta de
eso, y el sondeo `sondeo_aislamiento` lo demuestra contra el modelo real.

**Por qué**: el SDK carga por defecto la configuración de Claude Code (`CLAUDE.md`, hooks, skills,
agentes, permisos) del repositorio y del usuario. FR-004 pide que los agentes no la reciban, y los
hooks de `.claude/settings.json` (las guardas del #3) son del entorno de **desarrollo**; los del
producto son los del SDK del #7.

**Medición** (mismo `Glob` sobre `specs/006-*/spec.md`, `cwd` en la raíz, `include_hook_events=True`):

| `setting_sources` | Skills del repo | Agentes del repo | Eventos de hooks | ¿Conoce el `CLAUDE.md`? |
|---|---|---|---|---|
| `[]` | ninguna | solo los integrados | **0** | No: «existen `CLAUDE.md`… pero no los he leído» |
| `["project"]` (control) | `siguiente-ticket` | `auditor-cumplimiento`, `revisor-codigo` | `PreToolUse:Glob` (inicio y respuesta) | Sí: cita sus convenciones |

Con `[]` el agente puede ver que el archivo existe **solo si tiene herramientas de archivo**; los
nuestros tienen `tools=[]` y solo las herramientas de la pasarela, así que no pueden leerlo.

## R3. Herramientas permitidas: `allowed_tools` **y** `disallowed_tools` *(medido)*

**Hallazgo**: `allowed_tools` solo **pre-aprueba**; no oculta las demás. Un subagente con
`allowed_tools=[mcp__pasarela__consultar_registro_mercantil]` **veía las seis** herramientas de la
pasarela en su lista inicial y, al intentar `buscar_noticias`, la llamada se **denegó** (dos
`permission_denials`) en lugar de no existir. Con `disallowed_tools` con las otras cinco, la lista
inicial quedó con **una sola** herramienta.

**Decisión**: cada agente lleva `allowed_tools` con los nombres completos de **sus** herramientas
(`mcp__pasarela__<herramienta>`, `mcp__delegacion__delegar_frente`) y `disallowed_tools` con **el
resto de las herramientas de la pasarela**, calculado como el complemento sobre la lista de seis. Así
la herramienta ajena no está disponible (SC-002), no solo denegada. Un test compara la lista inicial
exacta de cada agente con la esperada; el sondeo la compara con la lista real de la sesión.

| Agente | `allowed_tools` | Modelo |
|--------|-----------------|--------|
| Coordinador | `mcp__delegacion__delegar_frente`, `mcp__pasarela__registrar_informe`, `mcp__pasarela__escalar_a_cumplimiento` | Sonnet 5.5 |
| Registro | `mcp__pasarela__consultar_registro_mercantil` | Sonnet 5.5 |
| Listas | `mcp__pasarela__consultar_listas_restrictivas` | Sonnet 5.5 |
| Noticias | `mcp__pasarela__buscar_noticias` | Sonnet 5.5 |
| Riesgo | `mcp__pasarela__consultar_riesgo_categoria` | Sonnet 5.5 |

El coordinador lleva `disallowed_tools` con las cuatro herramientas de fuentes. Como `.mcp.json` no se
carga con `setting_sources=[]`, el servidor `pasarela` se declara en las opciones (`sys.executable -m
servidor_mcp`, `cwd` en la raíz), con las variables `PASARELA_*` presentes en el entorno reenviadas.

## R4. Paralelismo y orden: `readOnlyHint` y dependencia en código *(medido)*

**Hallazgo**: el SDK emite un `AssistantMessage` por bloque, así que tres llamadas del mismo turno
aparecen como `[1, 1, 1]` bloques; no se puede inferir el paralelismo del mensaje. Con tres
llamadas de 2 s a una herramienta en proceso:

| Herramienta | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| Sin anotación | inicio 0 / 2 / 4 s (**serie**, 6 s) | inicio 0 / 2 / 4 s (**serie**, 6 s) |
| `readOnlyHint=True` | inicio 0 / 0,1 / 0,2 s (**solape**, 2,2 s) | inicio 0 / 0,2 / 0,3 s (**solape**, 2,3 s) |

**Decisión**:
- `delegar_frente` se registra con `ToolAnnotations(readOnlyHint=True)`: sin ella el SDK ejecuta las
  llamadas una tras otra y FR-006 no se cumpliría aunque el modelo las pida juntas. Es **correcto**
  anotarla así: delegar un frente no modifica nada fuera del caso; la anotación es la señal que el SDK
  usa para ejecutar en paralelo. Los canales de decisión no pasan por ella.
- El **orden de listas no depende del modelo**: si el modelo pide `listas` en el mismo turno que
  `registro`, la herramienta **espera** a que el registro termine (un `asyncio.Event` por frente del
  caso) y recién entonces empieza. Si el registro terminó sin una coincidencia única o no se delegó,
  `listas` **no se ejecuta** y devuelve un error estructurado no reintentable (FR-013). Esto es el
  orden de ejecución; la garantía dura de I.1 e I.2 sigue siendo de los hooks del #7.
- **Que se hagan las dos consultas de listas lo comprueba el código** (FR-005): tras el subagente,
  `delegar_frente` verifica en `estado.consultas` que hay una por el comercio y otra por el representante
  (si hay), con `igual()` de `servidor_mcp.normalizar` y no con igualdad exacta; si falta una, el frente
  queda `no_terminado` con el motivo.
- **Los datos de listas van del estado al prompt del subagente de listas** (FR-005): el comercio y el
  representante se toman del resultado del registro guardado, no de lo que el coordinador transcriba.
  Así «tal como los devolvió el registro» se cumple en lo que el código entrega. **Que el nombre que
  el subagente finalmente consulta coincida con el del estado lo comprobará un hook `PreToolUse` del
  #7, junto con I.1** (R13, punto 7): el subagente es un modelo y podría alterarlo al llamar a la herramienta.

**Límite declarado**: que registro, noticias y categoría **se pidan en el mismo turno** lo decide el
modelo (la instrucción de sistema lo pide). Si los pide en turnos distintos, el resultado es
correcto pero serializado. El test de solape comprueba el mecanismo (la herramienta admite llamadas
simultáneas y respeta la dependencia); la medición con el modelo real va en el quickstart (Q5).

## R5. Clasificación del fin del ciclo *(medido)*

**Hallazgos**, con `max_turns=1` y una consulta que necesita dos turnos:
- Se recibe un `ResultMessage` con `subtype="error_max_turns"`, `is_error=True`,
  `terminal_reason="max_turns"` y **`stop_reason="tool_use"`** (no `max_tokens`).
- Después, `query()` **lanza `ResultError`** (`subtype`, `terminal_reason`, `stop_reason`, `errors`
  en la excepción), un `ProcessError` por la salida distinta de cero de la CLI.
- Con turnos suficientes: `subtype="success"`, `stop_reason="end_turn"`, `terminal_reason="completed"`.
- `max_tokens` no se pudo provocar de forma fiable; se cubre con mensajes simulados.

**Decisión** — `terminacion.clasificar(subtype, stop_reason, is_error, terminal_reason)`, una función
pura, con este orden (el `subtype` primero, porque el límite de turnos trae `stop_reason=tool_use`):
1. `subtype == "error_max_turns"` → **LIMITE_SEGURIDAD**.
2. `subtype == "success"`, `is_error` falso y `stop_reason == "end_turn"` → **NORMAL**.
3. Cualquier otro caso → **ANOMALA**: `stop_reason == "max_tokens"` (el caso previsto), y también
   cualquier `subtype` de error, `is_error` verdadero o un `stop_reason` que no es `end_turn`
   (`refusal`, `pause_turn`…). El valor original va en el evento.

El texto de la respuesta **no interviene**. El código que consume el flujo del SDK captura
`ResultError`: si ya vio el `ResultMessage` no hace nada más; si no lo vio, clasifica con los
atributos de la excepción. Ni contadores ni `break` por texto (FR-010); `max_turns` solo se fija en
`configuracion.py`, con el comentario de protección de seguridad.

**Test de ausencia de control propio**: `test_sin_control_propio.py` recorre con `ast` los módulos de
`due_diligence/`: sin `while` en el coordinador ni el ejecutor, `max_turns` solo en `configuracion.py`
y ninguna comparación de texto de mensaje en las decisiones de continuar. Es una comprobación de
forma, no una prueba de ausencia total; el límite se declara.

## R6. Resultados de los subagentes: se capturan de las llamadas, no del texto

**Hallazgo** *(medido)*: el `ToolResultBlock` de una herramienta de la pasarela trae el JSON del
contrato del #5 como texto (`resultado`, `hechos[].contenido`, `hechos[].metadatos`, `metadatos`).

**Decisión**: el ejecutor recoge, de cada `ToolUseBlock` y su `ToolResultBlock`, la **consulta**
(herramienta y argumentos) y el **resultado** (el JSON del servidor, parseado). Eso es lo que entra
en el estado (FR-007, FR-008): contenido separado de metadatos por construcción, **sin pasar por el
texto del modelo**, que solo se guarda como `resumen` informativo. Un resultado que no es un JSON del contrato queda marcado como `resultado_invalido` y no se presenta como completo. **Si la herramienta devuelve el error estructurado de la pasarela** (`is_error`; `error`, `tipo`, `reintentable`, `obtenido`), se conserva en la `Consulta` sin reescribir, el frente queda `no_terminado` y `frente_no_terminado` propaga su `reintentable` en vez de fijar `false`. La política de reintentos es del #8.

## R7. Estado del caso y registro de eventos: en memoria, accesibles por referencia

**Decisión**: un `Caso` por solicitud, con su `EstadoCaso` y su `RegistroEventos`, ambos en memoria y
sin estado global (FR-014). Los hooks del SDK del #7 son **funciones Python** pasadas en
`ClaudeAgentOptions(hooks=…)`; leen el estado por **cierre** (la función se construye con la
referencia al `Caso`). Por eso `ejecutar_caso` acepta `hooks` y los reparte al coordinador **y a las
opciones de cada subagente** (cada `query()` es una sesión aparte y no los hereda). El #6 no define
hooks de negocio; solo deja ese punto de extensión y el estado legible.

**Eventos**: `Evento(secuencia, marca, tipo, frente, detalle)`. Tipos: `caso_iniciado`, `delegacion`,
`frente_inicio`, `frente_fin`, `frente_rechazado`, `terminacion`. `secuencia` (entero creciente,
asignado bajo un candado) da orden estable aunque dos marcas coincidan. La `marca` es una fecha y hora
UTC con zona; el reloj se inyecta para los tests. La interfaz (#11) consume `eventos()` en orden.

## R8. Carga del `.env` con `python-dotenv`

**Decisión**: `python-dotenv` 1.2.4. `configuracion.cargar_entorno()` llama a
`load_dotenv(override=False)` y **solo la invoca el punto de entrada** (`__main__.py`). Ni la importación
del paquete ni `ejecutar_caso` ni los tests la llaman. La carga **no escribe el nombre del archivo**:
`load_dotenv()` sin argumentos lo busca subiendo desde el archivo que la llama, así el código no
contiene ese literal, que la guarda de secretos (#3) podría bloquear al escribirlo con una herramienta de Claude Code.

**Por qué no `uv run --env-file .env`**: la guarda de secretos bloquea ese comando por nombrar el archivo.

**Qué pasa si falta**: `override=False` respeta una variable ya exportada; sin archivo no falla. La
CLI que usa el SDK también acepta la sesión de Claude Code del usuario; en los sondeos de esta
investigación funcionó así, sin clave. `ANTHROPIC_API_KEY` es lo que cubre una máquina sin sesión.
El test `test_configuracion` comprueba que ningún módulo salvo `__main__` llama a `cargar_entorno`.

## R9. Modelos: Sonnet 5.5 para el coordinador y para los cuatro subagentes

**Decisión** (analista, 2026-10-17): el coordinador y los cuatro subagentes usan `claude-sonnet-5-5`,
con identificador completo (no el alias `sonnet`, que puede resolver a otro modelo con el tiempo). El
modelo del coordinador y el de los subagentes se leen de variables de entorno distintas
(`PASARELA_MODELO_COORDINADOR` y `PASARELA_MODELO_SUBAGENTES`), con el mismo valor por defecto, para
poder cambiar uno sin tocar el otro ni el código.

**Razón**:
- **Más fidelidad al copiar datos**: aunque un subagente solo hace una llamada a su herramienta y
  resume, tiene que copiar sin alterar el identificador, el nombre y el representante que el código le
  entrega (R4, R11). Un error ahí cambia lo que se consulta. Se acepta pagar un modelo más capaz a cambio
  de esa fidelidad.
- **Coste estimado por la analista**: unos **0,01 a 0,02 USD más por caso** respecto de subagentes en
  Haiku. Es una estimación: el coste real de un caso completo, con los cuatro subagentes en Sonnet, se
  mide en frío y en caliente en Q5 (T034) y se anota en `DECISIONES.md`.
- **El coordinador** decide qué datos extraer de una solicitud en lenguaje natural, qué frentes delegar
  y, en #9 y #10, redactará recomendaciones y resúmenes al oficial. No se elige el modelo más grande
  porque **las decisiones obligatorias no dependen del modelo**: las garantizan los hooks (principio II)
  y el orden lo hace cumplir la herramienta (R4).
- **Medido** (R14.3): una llamada mínima sin herramientas cuesta ≈ 0,005 USD con Sonnet 5.5; cuando el
  coordinador llama a una herramienta en proceso, el SDK escribe en la caché un prefijo de unos
  30 000 tokens (≈ 0,129 USD con Sonnet en frío, ≈ 0,004 en caliente). Un caso en frío con Sonnet
  cuesta **del orden de 0,13 USD** *(corregido en 14.4: en el caso real, ≈ 0,06 USD)* y en caliente (misma hora), del orden de 0,01 a 0,03; el coste lo
  domina el coordinador, no los subagentes.

**Alternativas descartadas**:
- **Haiku 5.5 para los subagentes**: más barato y rápido. Medido con el mismo servidor: una llamada
  mínima ≈ 0,0002 USD (unas 20 veces menos que Sonnet) y los dos frentes del sondeo de R14.1,
  ≈ 0,0003 USD en total, con ≈ 5 s por frente. Se descarta por la fidelidad al copiar datos, no por
  falta de capacidad para la tarea.
- **Haiku 5.5 para el coordinador**: ≈ 0,006 USD en frío con una llamada a una herramienta en proceso.
  Se descarta porque el coordinador es el que interpreta la solicitud y, más adelante, redacta.
- **Opus 5.5 para el coordinador**: mejora el razonamiento, pero aquí no es el cuello de botella y
  encarece cada caso sin una necesidad medida. Si #9 o #10 muestran que el coordinador falla en el
  resumen al oficial, se sube con la variable de entorno y se documenta.

**Dónde se documenta**: una viñeta breve en `DECISIONES.md`, con una línea por decisión y sin recortar
entradas existentes. La bitácora `docs/bitacora-decisiones.md` (sección 6.2) **no se edita en este
ticket**: la actualiza la analista desde otro chat. Para eso, tras T034 el resumen de `/speckit-implement`
deja los números medidos (duración, solape, coste en frío y en caliente).

## R10. Dependencias

`uv add "claude-agent-sdk>=0.2.168,<0.3" "python-dotenv>=1.2,<2"`. **Resueltas** junto a
`mcp>=2.3,<3` y `pydantic>=2` (`uv pip compile`): `claude-agent-sdk==0.2.168`, `mcp==2.3.0`,
`mcp-types==2.3.0`, `python-dotenv==1.2.4`, sin conflicto. El SDK trae su propia CLI (carpeta
`_bundled`). Se acota la versión menor porque el SDK es 0.x y su API cambia entre menores.

## R11. Contexto explícito y prompts

**Decisión**: el `prompt` de cada subagente lo construye **el código** a partir de los campos de la
delegación (`contexto.py`), no el modelo; el `system_prompt` es fijo por frente, en español, e indica
la herramienta, qué no hace y que debe responder con un resumen de una o dos líneas.

| Frente | Recibe (solo esto) | Falta algo |
|--------|--------------------|-----------|
| Registro | `identificador` o `nombre` | `frente_rechazado`: pide el dato |
| Noticias | `identificador` o `nombre` del comercio | ídem |
| Riesgo | `categoria` | ídem; no se inventa una categoría |
| Listas | comercio (`identificador`, `nombre`) y representante (`nombre`, `identificador`) **del resultado del registro** | sin coincidencia única: no se ejecuta |

`delegar_frente` recibe `frente`, `identificador`, `nombre` y `categoria`; ignora lo que ese frente
no necesita. Con `setting_sources=[]` y `tools=[]` (R2, R3), el agente no tiene otra vía de contexto.

## R12. Pruebas

- **Ejecutor inyectable** (`EjecutorSimulado`): devuelve `ResultadoFrente` fijo tras un retardo
  `asyncio.sleep`; registra cuándo empezó y terminó. Es el mecanismo del test de solape (SC-003).
- **El solape se prueba con llamadas simultáneas**: el test lanza `asyncio.gather` de tres llamadas
  a la herramienta (lo que hace el SDK con `readOnlyHint`, R4) y comprueba, con los eventos, que los
  tres frentes se solapan y que `listas` empieza **después** de `frente_fin` del registro, incluso
  si se pide en el mismo `gather`.
- **Clasificación**: `ResultMessage` simulados (`end_turn`, `max_tokens`, `error_max_turns` con
  `stop_reason="tool_use"`, `refusal`, un `is_error` verdadero) y un `ResultError` simulado; un caso
  con el texto «listo» y `max_tokens` (US6-4).
- **Herramientas por agente**: lista exacta de `allowed_tools` y `disallowed_tools` por agente; la
  unión de las permitidas y las no permitidas de la pasarela es siempre las seis (SC-002).
- **Opciones**: toda construcción lleva `setting_sources=[]`, `tools=[]`, `strict_mcp_config`;
  el `prompt` del subagente no contiene texto de la conversación (FR-004).
- **Con el modelo real, a mano** (quickstart): aislamiento (`sondeo_aislamiento`), caso de ejemplo
  completo y solape con tiempos. No corren en `pytest` (costo y red); se marcan como manuales.

## R13. Riesgos residuales

1. **El modelo decide si pide los tres frentes juntos** (R4): el resultado es correcto, pero puede
   serializarse. Se mide en Q5 y se ajusta la instrucción de sistema si hace falta.
2. **El coordinador puede no llamar a un frente** que debía delegar: este ticket no obliga a
   completar los cuatro (la cobertura declarada es del #8, el informe del #9). El estado lo muestra
   como `sin_iniciar`.
3. **Cinco procesos del servidor `pasarela`** por caso (uno por agente con sesión propia): aceptable
   con datos locales; si pesara, se comparte uno en el #11.
4. **`max_tokens` solo se cubre con mensajes simulados** (R5): el SDK real no lo produjo en los sondeos.
5. **`SDK` 0.x**: cambios entre versiones menores; versión acotada y sondeo repetible (`quickstart` Q2).
6. **Los hooks del #7 deben pasarse a cada `query()`** (R7): si el #7 olvida los de los subagentes,
   las reglas no los alcanzan. Los tests del #7 deben cubrirlo; aquí se deja el punto de extensión.
7. **Punto del #7: el nombre consultado en listas**. El código entrega al subagente de listas el
   comercio y el representante tomados del estado (R4), pero el subagente es un modelo y puede
   cambiar el argumento al llamar a la herramienta. Que el nombre o identificador de cada llamada a
   `consultar_listas_restrictivas` coincida con el del estado lo comprobará un hook `PreToolUse` del
   #7, junto con I.1 (comercio identificado de forma unívoca). El #6 no lo comprueba.
8. **Desviación temporal de II: herramientas de decisión sin guarda**. El coordinador conserva
   `registrar_informe` y `escalar_a_cumplimiento` (FR-002) y están pre-aprobadas, pero no hay hooks hasta el
   #7. Mitigación: la instrucción del coordinador se las prohíbe en este ticket (son del #9 y del #10) y Q5
   comprueba que no hubo llamadas y que `resultados/` no tiene archivos nuevos. Es una instrucción, no una
   garantía; la cierra el #7. Se declara en el plan.
9. **Coste en frío del coordinador** (R9, R14): la primera llamada con herramientas de la hora escribe
   un prefijo grande en la caché.
10. **`listas` en curso mientras el registro se repite**. Si el registro se vuelve a ejecutar y su
   comercio cambia, `listas` ya terminado pasa a `no_terminado` («el comercio del registro cambió; vuelva
   a delegar listas»). Pero un `listas` que **sigue en curso** en ese momento no se invalida: terminará con
   resultados del comercio anterior. Es un riesgo residual: lo cubre el hook del #7 (el nombre o
   identificador de cada consulta de listas debe coincidir con el comercio del estado, punto 7).

## R14. Sondeo de la opción (a): `query()` anidado y herramienta lenta *(medido)*

Entorno temporal fuera del repositorio, `claude-agent-sdk` 0.2.168, sin leer `.env`. Coordinador con
Sonnet 5.5 y subagentes con Haiku 5.5 reales contra el servidor `pasarela` del #5 (el sondeo se hizo
con Haiku en los subagentes por coste; la decisión final es Sonnet para todos, R9). **Nada falló: la
opción (a) se mantiene.**

**14.1. `delegar_frente` lanza un `query()` de subagente desde dentro de la herramienta, con el
`query()` del coordinador abierto.** Herramienta en proceso con `readOnlyHint=True`; cada llamada abre
un subagente con `setting_sources=[]`, `tools=[]`, su herramienta de la pasarela permitida y las otras
cinco prohibidas (R3), y devuelve su resultado al coordinador.

| Ejecución | Frentes | Inicio | Fin | Duración de cada frente | Coordinador (total) |
|-----------|---------|--------|-----|-------------------------|---------------------|
| 1 | registro, noticias (juntos) | 2,3 s y 2,6 s | 7,5 s y 7,5 s | 5,2 s y 4,9 s | 10,7 s |
| 2 | registro, noticias (juntos) | 3,6 s y 3,9 s | 9,0 s y 9,0 s | 5,4 s y 5,1 s | ≈ 11 s |

- Cada subagente hizo **una** consulta, a **su** herramienta (`consultar_registro_mercantil` y
  `buscar_noticias`), y el coordinador recibió el resultado de ambos como `tool_result` y terminó con
  `success` / `end_turn`.
- **Dos a la vez se solapan de verdad**: cada frente tarda ≈ 5 s (arranque de la CLI del subagente y
  del servidor `pasarela` por stdio, más dos llamadas del modelo); en serie serían ≈ 10 s.
- El coordinador necesitó ≈ 2,3 s antes de delegar y ≈ 2,4 s para responder tras los resultados.

**14.2. Una herramienta en proceso con `readOnlyHint` que tarda 130 s no se corta.** La herramienta
empezó a los 2,0 s y terminó a los 132,0 s; el resultado llegó al modelo (`es_error` ausente) y el
ciclo terminó `success` / `end_turn` a los 133,1 s. **No se encontró un límite de espera hasta 130 s**,
que cubre con margen los ≈ 5 s de un frente (y un frente con reintentos del #8). No se probó nada por
encima de 130 s ni se ha buscado una variable para configurarlo: si el #8 introduce esperas más largas,
habrá que medirlo entonces.

**14.3. Coste: hallazgo que corrige R9.** El `ResultMessage` del coordinador con Sonnet 5.5 dio
≈ 0,13 USD, no centavos. Se aisló con Haiku como sondeo de control:

| Caso | Escrito en caché | Coste |
|------|------------------|-------|
| Sonnet, sin servidores ni llamadas | ≈ 1 300 tokens | ≈ 0,005 USD |
| Sonnet, llama a `delegar_frente` (primera vez, caché fría) | **≈ 32 000 tokens** | **≈ 0,129 USD** |
| Sonnet, la misma llamada otra vez (caché caliente) | 0 escritos, 32 112 leídos | ≈ 0,004 USD |
| Haiku como coordinador, llama a `delegar_frente` | ≈ 29 000 tokens | ≈ 0,006 USD |
| Dos subagentes Haiku (los dos frentes de 14.1) | ≈ 1 200 de entrada cada uno | ≈ 0,0003 en total |

La causa exacta del prefijo de ≈ 30 000 tokens (aparece cuando el coordinador usa una herramienta
en proceso, y no con una consulta sin herramientas) **no se ha identificado**; no depende de
`setting_sources` ni de `skills`. Implicaciones:
- Los **subagentes** con Haiku salieron baratos (≈ 0,0003 USD los dos); con Sonnet (R9) costarán más
  y se miden en Q5. El coste de un caso lo domina **el coordinador**.
- En frío (la primera vez de cada hora) un caso con Sonnet cuesta del orden de **0,13 USD**; en
  caliente, del orden de 0,01 USD. Con Haiku como coordinador, ≈ 0,006 en frío.
- No cambia la opción (a). Sí obliga a **medir en Q5 el coste de un caso completo en frío y en caliente**
  y a anotar esos números. El plan mantiene Sonnet 5.5 para el coordinador y los subagentes (R9) y lo deja
  sustituible por variable de entorno.

**Para las tareas**: el ejecutor real hace `query()` desde dentro de la herramienta y el `cwd` de cada
subagente es la raíz del repositorio; el test automático sigue usando el ejecutor simulado. Q5 repite
esta medición con el caso completo.

**14.4. Corrección con la validación real (T033, 2026-10-17).** El prefijo de ≈ 30 000 tokens de 14.3 **no
apareció en el caso completo**. Tres ejecuciones con Sonnet 5.5 en los cinco agentes costaron 0,0656,
0,0569 (frío) y 0,0577 USD (caliente): **unos 0,06 USD por caso**, con el coordinador entre 0,026 y 0,034
y cada subagente entre 0,006 y 0,011, sin diferencia apreciable entre frío y caliente. Las cifras de
≈ 0,13 USD de R9 y 14.3 valen para el sondeo aislado, no para el caso real.
