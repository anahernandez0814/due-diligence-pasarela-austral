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
| Registro | `mcp__pasarela__consultar_registro_mercantil` | Haiku 5.5 |
| Listas | `mcp__pasarela__consultar_listas_restrictivas` | Haiku 5.5 |
| Noticias | `mcp__pasarela__buscar_noticias` | Haiku 5.5 |
| Riesgo | `mcp__pasarela__consultar_riesgo_categoria` | Haiku 5.5 |

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
texto del modelo**, que solo se guarda como `resumen` informativo. Un resultado que no es un JSON del
contrato queda marcado como `resultado_invalido` y no se presenta como completo.

## R7. Estado del caso y registro de eventos: en memoria, accesibles por referencia

**Decisión**: un `Caso` por solicitud, con su `EstadoCaso` y su `RegistroEventos`, ambos en memoria y
sin estado global (FR-014). Los hooks del SDK del #7 son **funciones Python** pasadas en
`ClaudeAgentOptions(hooks=…)`; leen el estado por **cierre** (la función se construye con la
referencia al `Caso`). Por eso `ejecutar_caso` acepta `hooks` y los reparte al coordinador **y a las
opciones de cada subagente** (cada `query()` es una sesión aparte y no los hereda). El #6 no define
hooks de negocio; solo deja ese punto de extensión y el estado legible.

**Eventos**: `Evento(secuencia, marca, tipo, frente, detalle)`. Tipos: `caso_iniciado`, `delegacion`,
`frente_inicio`, `frente_fin`, `frente_no_iniciado`, `terminacion`. `secuencia` (entero creciente,
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

## R9. Modelos: Sonnet 5.5 para el coordinador, Haiku 5.5 para los subagentes

**Decisión**: coordinador `claude-sonnet-5-5`; subagentes `claude-haiku-5-5`, con identificadores
completos (no los alias `sonnet` y `haiku`, que pueden resolver a otro modelo con el tiempo). Ambos
se pueden sustituir con `PASARELA_MODELO_COORDINADOR` y `PASARELA_MODELO_SUBAGENTES`, sin tocar código.

**Razón**:
- **Los subagentes solo consultan su fuente**: una llamada a una herramienta con argumentos
  conocidos (el código los fija en el prompt) y un resumen corto. Es trabajo de clasificar y copiar,
  donde un modelo pequeño es suficiente y 4 llamadas por caso multiplican el coste y la latencia.
- **El coordinador** decide qué datos extraer de una solicitud en lenguaje natural, qué frentes
  delegar y, en #9 y #10, redactará recomendaciones y resúmenes al oficial: ahí la calidad importa
  más que el coste. No se elige el modelo más grande porque **las decisiones obligatorias no
  dependen del modelo**: las garantizan los hooks (principio II) y el orden lo hace cumplir la
  herramienta (R4).
- **Medido** (una llamada mínima, sin herramientas): Sonnet 5.5 ≈ 0,005 USD; Haiku 5.5 ≈ 0,0002 USD,
  unas 20 veces menos. **Corrección tras R14**: cuando el coordinador llama a una herramienta en
  proceso, el SDK escribe en la caché un prefijo de unos 30 000 tokens (≈ 0,129 USD con Sonnet en frío,
  ≈ 0,006 con Haiku, ≈ 0,004 con Sonnet si la caché está caliente). Con dos subagentes Haiku el coste
  de estos fue ≈ 0,0003. Un caso en frío con Sonnet cuesta **del orden de 0,13 USD**, no de centavos;
  en caliente (misma hora), del orden de 0,01. El coste real de un caso completo se mide en frío y en
  caliente en Q5 y se anota en `DECISIONES.md` y la bitácora 6.2. Si el coste en frío importa, la
  decisión se revisa con esos números (R14).
- **Alternativa descartada**: Opus 5.5 para el coordinador. Mejora el razonamiento, pero aquí no es el
  cuello de botella y encarece cada caso sin una necesidad medida. Si #9 o #10 muestran que el
  coordinador falla en el resumen al oficial, se sube con la variable de entorno y se documenta.

**Dónde se documenta**: bitácora 6.2 (pasa de «pendiente» a decidido) y una viñeta breve en
`DECISIONES.md`, con una línea por decisión, sin recortar entradas existentes.

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
| Registro | `identificador` o `nombre` | `frente_no_iniciado`: pide el dato |
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
8. **Coste en frío del coordinador** (R9, R14): la primera llamada con herramientas de la hora escribe
   un prefijo grande en la caché.

## R14. Sondeo de la opción (a): `query()` anidado y herramienta lenta *(medido)*

Entorno temporal fuera del repositorio, `claude-agent-sdk` 0.2.168, sin leer `.env`. Coordinador con
Sonnet 5.5 y subagentes con Haiku 5.5 reales contra el servidor `pasarela` del #5. **Nada falló: la
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
- Los **subagentes** salen baratos con Haiku; el coste de un caso lo domina **el coordinador**.
- En frío (la primera vez de cada hora) un caso con Sonnet cuesta del orden de **0,13 USD**; en
  caliente, del orden de 0,01 USD. Con Haiku como coordinador, ≈ 0,006 en frío.
- No cambia la opción (a). Sí obliga a **medir en Q5 el coste de un caso completo en frío y en caliente**
  y a decidir con esos números el modelo del coordinador (R9). El plan mantiene Sonnet 5.5 por calidad
  y lo deja sustituible por variable de entorno.

**Para las tareas**: el ejecutor real hace `query()` desde dentro de la herramienta y el `cwd` de cada
subagente es la raíz del repositorio; el test automático sigue usando el ejecutor simulado. Q5 repite
esta medición con el caso completo.
