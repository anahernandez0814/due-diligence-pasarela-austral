# Investigación: Hooks del SDK: reglas de negocio 1, 2 y 3 garantizadas

Todo lo marcado *(medido)* se comprobó el 2026-10-18 con `claude-agent-sdk` 0.2.168 (CLI 2.1.301)
en un entorno temporal (`uv run --no-project --with claude-agent-sdk==0.2.168 --with "mcp>=2.3,<3"`),
con `claude-haiku-5-5`, contra el servidor `pasarela` del #5 y una herramienta en proceso como
`delegar_frente`. El sondeo vivió fuera del repositorio (`sondeo_hooks.py`, en el directorio
temporal de la sesión) y no leyó ningún archivo de entorno. Coste total: ≈ 0,006 USD. El plan lo
convierte en un sondeo repetible dentro del repositorio (`sondeo_hooks.py`, tarea de Q4).

## R1. Qué recibe cada hook *(medido)*: preguntas (a) y (b)

| Evento | Herramienta | Qué llega |
|--------|-------------|-----------|
| `PostToolUse` | MCP por stdio (`mcp__pasarela__consultar_registro_mercantil`) | `tool_response` es un **`str`** con el JSON de la respuesta, tal como lo devolvió el servidor (`resultado`, `coincidencias`, `hechos`, `metadatos`). |
| `PostToolUse` | MCP en proceso (`mcp__delegacion__delegar_frente`) | `tool_response` es una **`list`** de bloques: `[{"type": "text", "text": "<json>"}]`. |
| `PostToolUseFailure` | MCP por stdio con `is_error=true` | `PostToolUse` **no se invoca**; llega `PostToolUseFailure` con `error`, un `str` con el JSON del error estructurado completo (`error`, `tipo`, `mensaje`, `reintentable`, `obtenido`, y `campos_faltantes` si lo trae). `tool_response` no existe. |
| `PreToolUse` | cualquiera | `tool_input` ya es un `dict` con los argumentos del modelo; `tool_response` es `None`. |

Respuestas:

- **(a)** Sí: `PostToolUse` recibe el `tool_response` de una herramienta MCP. Su forma depende del
  servidor: texto JSON para stdio y lista de bloques para el servidor en proceso. Los hooks no
  pueden asumir una forma: leen ambas.
- **(b)** Un error estructurado de la pasarela llega **solo por `PostToolUseFailure`**, con el
  JSON del error en `error`. Consecuencia: los hooks que registran hechos (`PostToolUse`) solo
  ven respuestas de éxito; una consulta con error **no entra en el libro de reglas** y, por tanto,
  nunca cuenta como consulta realizada (FR-005). `PostToolUseFailure` se usa solo para dejar
  evento y para que `escalar_a_cumplimiento` con error no cuente como escalamiento.
- Un error de validación de `registrar_informe` (b2) llega igual por `PostToolUseFailure`.
  Los errores reales de la pasarela salen por la misma vía que la caída de noticias (b).

**Decisión**: un único lector de lo que devolvió una herramienta. El #6 ya tiene
`ejecutor.interpretar_resultado(contenido, es_error)`, que acepta texto o lista de bloques, separa
el resultado del contrato del error estructurado y no lanza. Los hooks lo **reutilizan** (con
`es_error=False` en `PostToolUse` y `True` en `PostToolUseFailure`); no se escribe un segundo
analizador.

## R2. Qué hace el SDK si un hook de Python lanza una excepción *(medido)*: pregunta (c)

| Caso | Resultado medido |
|------|------------------|
| `PreToolUse` que lanza `RuntimeError` | El SDK imprime `Error in hook callback` por la salida de error y **la herramienta se ejecuta** (el `PostToolUse` posterior y el resultado llegaron al modelo). |
| `PostToolUse` que lanza | La respuesta llega al modelo sin cambios. |
| `PreToolUse` que devuelve una forma inválida (`permissionDecision: "quizás"`) | Error de validación (`ZodError`) por la salida de error y **la herramienta se ejecuta**. |
| `Stop` que lanza | El caso **termina con normalidad** (`success`, `end_turn`). |
| `PreToolUse` que devuelve `permissionDecision: "deny"` con motivo (herramienta en proceso) | La herramienta **no se ejecuta** (0 ejecuciones) y el modelo recibe `tool_result` con `is_error=true` y el texto `PreToolUse:<herramienta> hook error: <motivo>`. El motivo llega al modelo. |

**Respuesta (c)**: el SDK **deja pasar la acción** ante una excepción o una salida inválida del
hook. Por FR-012 cada hook se envuelve (`hooks.fallar_cerrado`):

- `PreToolUse`: ante cualquier excepción devuelve `deny` con un motivo genérico en español y deja
  un evento `fallo_de_hook`.
- `Stop`: ante cualquier excepción devuelve `decision: "block"` (cuenta contra el límite de R3).
- `PostToolUse` y `PostToolUseFailure` no pueden impedir nada: ante una excepción **marcan el
  libro con `fallo_de_hook`** (sticky), los hooks de `PreToolUse` de las tres reglas deniegan
  mientras el sello exista y `Caso.completo` es `False` (un `PostToolUse` que falló pudo dejar sin
  registrar una coincidencia, y el caso no puede presentarse como completo). Así, un hecho que no se pudo registrar no se convierte en un permiso:
  lo que no consta no se permite (fallo cerrado), y el caso queda bloqueado en lugar de seguir
  sin garantía.
- Las salidas de los hooks se construyen con funciones tipadas (`denegar(motivo)`,
  `bloquear_cierre(motivo)`, `permitir()`), no con diccionarios a mano, y un test valida su forma
  contra los literales del SDK, porque una forma inválida también deja pasar la acción.

Límite declarado: el envoltorio atrapa `Exception`; un `KeyboardInterrupt` o un fallo del proceso
del SDK no lo atrapa. Un hook que se cuelga lo corta el tiempo límite del propio SDK, cuyo efecto
no se midió; el plan no lo da por cerrado (residual 3 de R12).

## R3. Un `Stop` con `decision: "block"` y el límite de devoluciones *(medido)*: pregunta (d)

Con un hook de `Stop` que siempre devuelve `{"decision": "block", "reason": "…"}` y `max_turns=4`:

- **El modelo continúa**: tras cada bloqueo respondió otra vez. El texto del `reason` llegó al
  modelo (respondió «ESCALADO», la palabra que pedía el motivo).
- **`stop_hook_active`**: `False` en la primera llamada y `True` en las siguientes. Es solo un
  indicador de «ya se devolvió una vez»; **no sirve de contador**.
- **Cada devolución gasta un turno de `max_turns`**: el hook se invocó 4 veces, el caso terminó con
  `subtype=error_max_turns` y `num_turns=5`, y después `query()` lanzó `ResultError` (el mismo
  comportamiento de R5 del #6).
- Con un hook que bloquea dos veces y luego permite: se invocó 3 veces, terminó con `success` y
  `end_turn`, y `num_turns=3`.
- Un `Stop` que lanza una excepción deja terminar (R2).

**Decisión**: el límite de devoluciones es un contador **propio en el libro del caso**
(`cierres_impedidos`), no `stop_hook_active` ni `max_turns`:

- `MAX_CIERRES_IMPEDIDOS = 3`, constante en `configuracion.py`, documentada como **protección de
  seguridad** y no como el mecanismo de la regla (igual que `MAX_TURNOS_SEGURIDAD`): la regla es
  «un caso que requiere escalamiento no termina sin escalar»; el límite solo evita que un modelo que
  insiste agote `max_turns`.
- Llegado al límite, el hook **deja terminar**, marca `cierre_sin_escalar` en el estado y deja el
  evento `cierre_sin_escalar`. El caso **no se presenta como completo ni como habilitado**
  (`Caso.completo` es `False`); eso es lo que ve la interfaz (#11) y el informe (#9).
- El límite (3) es mucho menor que `MAX_TURNOS_SEGURIDAD` (30), de modo que las devoluciones no
  llevan al caso a `error_max_turns` por sí solas; un test lo comprueba con los valores reales.
- El `Stop` solo va en el coordinador. Cada subagente es un `query()` propio, así que un `Stop`
  puesto en sus opciones también se dispararía (el SDK lo invoca en cada sesión): por eso el reparto
  por agente de R5 es una garantía de código y un test comprueba que ningún subagente lo lleva.

## R4. Una sola fuente de verdad para la identificación del comercio

**Hallazgo**: hoy hay un intérprete y dos escritores potenciales. `estado.derivar_comercio(resultado)`
interpreta una respuesta del registro (una coincidencia, sin contradicción entre fuentes); y
`Delegador._fijar_comercio` (`delegacion.py:349`) consolida las consultas del frente (todas
coinciden, no se elige la primera) y escribe `estado.comercio`. Si además el hook `PostToolUse` del
registro escribiera su propia copia, habría dos escritores y dos criterios sobre «cuándo está
identificado».

**Decisión: se reutiliza `derivar_comercio` como único intérprete, y el hook pasa a ser el único
escritor.**

- `derivar_comercio` **no cambia**: es la única función que decide qué es una identificación
  unívoca (una coincidencia, hechos coherentes, representante tal como lo devolvió el registro).
- El hook `PostToolUse` del registro llama a `EstadoCaso.registrar_identificacion(respuesta)`, que
  guarda **el resultado de `derivar_comercio` de cada consulta válida** (en `identificaciones`).
- `EstadoCaso.comercio` y `motivo_comercio` pasan de campos escritos a **propiedades derivadas**
  de `identificaciones` y de la situación del frente de registro. La consolidación de
  `_fijar_comercio` (todas las consultas con coincidencia deben coincidir; si ninguna tiene
  coincidencia, el motivo es el de la primera; si el registro no terminó con normalidad no hay
  comercio) **se mueve** a esa propiedad, no se copia.
- Se eliminan `Delegador._fijar_comercio` y `EstadoCaso.fijar_comercio`. El `Delegador` sigue
  **leyendo** `estado.comercio` (para `construir_contexto`, `_falta_en_listas` y la invalidación
  de listas) y no vuelve a derivar nada.
- Al volver a delegar el registro con otra entrada, el `Delegador` llama a
  `estado.reiniciar_identificacion()` antes de lanzar el frente y conserva el comercio anterior
  para decidir la invalidación de listas (`_invalidar_listas`), como hoy.
- El hook de la consulta de listas (regla I.1) y el de `delegar_frente` leen **solo**
  `estado.comercio` y la situación del frente de registro; no consultan `estado.consultas` ni
  `estado.resultados`.

**Consecuencia para los tests del #6**: los ejecutores simulados no ejecutan hooks, así que una
consulta simulada del registro ya no basta para fijar el comercio. `simulacion.py` gana una
**sesión simulada** (`SesionSimulada`) que, para cada llamada a una herramienta, ejecuta los hooks
que el código puso en `opciones.hooks` en el mismo orden que el SDK (`PreToolUse` → herramienta →
`PostToolUse` o `PostToolUseFailure`). Los tests de #6 que dependen del comercio se adaptan a
`SesionSimulada`; los que no (solape, contexto, eventos) siguen igual.

**Alternativa descartada**: dejar el comercio en el `Delegador` y que el hook solo lo lea. Contradice
FR-001 (el hook guarda) y deja la identificación dependiendo de que un frente termine bien, no de lo
que la herramienta devolvió.

## R5. Reparto de hooks por agente (FR-010)

`coordinador.py` pasa hoy el mismo `self.hooks` al coordinador y a los cuatro subagentes (líneas 105
y 112). Se sustituye por una fábrica (`hooks.HooksDelCaso`) que construye, para el caso, los hooks de
cada agente con cierre sobre **el mismo** estado y registro de eventos:

| Agente | Hooks |
|--------|-------|
| Coordinador | `PreToolUse` sobre `mcp__delegacion__delegar_frente` (frente `listas`); `PreToolUse` sobre `mcp__pasarela__registrar_informe`; `PostToolUse` y `PostToolUseFailure` sobre `mcp__pasarela__escalar_a_cumplimiento`; `Stop`. |
| Subagente registro | `PostToolUse` y `PostToolUseFailure` sobre `mcp__pasarela__consultar_registro_mercantil`. |
| Subagente listas | `PreToolUse`, `PostToolUse` y `PostToolUseFailure` sobre `mcp__pasarela__consultar_listas_restrictivas`. |
| Subagente categoría | `PostToolUse` y `PostToolUseFailure` sobre `mcp__pasarela__consultar_riesgo_categoria`. |
| Subagente noticias | ninguno. |

- **Lo compartido es el estado.** Los hooks de cada sesión escriben y leen el mismo `EstadoCaso`,
  porque son funciones Python del proceso del caso que cierran sobre él (no hay estado de módulo).
  El estado no se serializa ni se pasa por el SDK, así que no depende de que las sesiones compartan
  conversación.
- `Caso` deja de aceptar un parámetro `hooks` genérico: las reglas no se desactivan desde fuera.
  `opciones_coordinador` y `opciones_subagente` de `configuracion.py` conservan su parámetro `hooks`
  (la función de construcción es neutral), y el test de R2 del #6 se actualiza.
- El **matcher** de cada hook es el nombre completo exacto de la herramienta, no un patrón.
- Los hooks del repositorio (`.claude/`) siguen sin cargarse (`setting_sources=[]`): estos son los
  hooks del **producto**, los de `.claude/` son del entorno de desarrollo.

## R6. Hook de `delegar_frente` para listas (FR-018)

- `PreToolUse` sobre `mcp__delegacion__delegar_frente`, solo si `tool_input.frente == "listas"`
  (se compara normalizado; un frente que no es `listas` se permite sin más).
- Se **deniega** si la situación del registro es `sin_iniciar`, `rechazado` o `no_terminado`, o si
  es `terminado` pero `estado.comercio` es `None` (varias coincidencias, ninguna o fuentes que no
  coinciden). El motivo dice cuál y, si hay varias coincidencias, que se pida el identificador al
  analista.
- Si el registro está `en_curso` se **permite**: la herramienta espera al fin del registro (R4 del
  #6) y, si termina sin coincidencia única, la propia delegación se rechaza (`_rechazar`), que queda
  como defensa adicional.
- **Carrera aceptada**: si el modelo pide `registro` y `listas` en el mismo turno, el hook de
  `listas` puede ejecutarse antes de que `registro` pase a `en_curso`. Entonces ve `sin_iniciar` y
  deniega con un motivo que pide delegar primero el registro; es el mismo desenlace que el rechazo
  reintentable de `_esperar_al_registro` del #6. No es un bloqueo definitivo y no cambia el estado.
- Con modelo real, el hook se ve en el chat como un `tool_result` con `is_error=true` y el motivo
  (medido en e1) y como un evento `bloqueo_regla` con `regla=I.1`.

## R7. Qué cuenta como consulta de listas válida y cómo se comparan los nombres (FR-002, FR-003, FR-005)

- La consulta se compara **siempre contra `estado.comercio`** en el momento de evaluar, no contra
  lo que se guardó cuando se hizo. Si el registro cambia de comercio, las consultas del comercio
  anterior dejan de coincidir y por tanto de contar (caso límite «consulta repetida del registro»);
  las **coincidencias** ya registradas no se borran.
- Comparación de una consulta `(tipo, nombre|identificador)` con una entidad `(tipo_esperado, nombre,
  identificador)`: el tipo debe ser el esperado (`comercio` para el comercio, `persona` para el
  representante); la consulta debe traer al menos una clave y **cada clave que trae debe existir en la
  entidad del registro y coincidir** (`igual_identificador` para el identificador e `igual` para el
  nombre, de `servidor_mcp.normalizar`, que es lo que usa el servidor; no hay otra normalización).
  Si la consulta trae los dos y uno no coincide, no coincide; y si trae una clave que la entidad no
  tiene (por ejemplo, un `identificador` para un representante que el registro devolvió sin
  identificador), tampoco coincide: no se puede verificar que sea la misma persona. Un test
  explícito cubre el representante sin identificador.
- Esta comparación **ya existe** en `Delegador._falta_en_listas` (`delegacion.py:276`), que comprueba
  que el subagente consultó a ambos. Se extrae a una función pura `reglas.consulta_coincide(...)` y
  `_falta_en_listas` la usa: una sola comparación para el hook y para la defensa del #6.
- Una consulta de listas cuenta si es **válida** (llegó por `PostToolUse`, es decir sin error; R1) y
  su resultado es del contrato. Una con error no entra al libro.

## R8. Categoría del caso y alto riesgo (FR-008, FR-009)

- `reglas.ALTO_RIESGO` es una **constante** del código: `("apuestas", "criptoactivos",
  "suplementos dietarios", "venta de medicamentos")`. Ningún prompt la contiene.
- Cada respuesta de `consultar_riesgo_categoria` válida entra al libro como `ConsultaRiesgo(categoria,
  nivel)`, con `nivel` en `alto|medio|bajo`, o como `categoria_desconocida` (sin nivel).
- **Alto riesgo** si alguna consulta del caso tiene la categoría en `ALTO_RIESGO` (comparada con
  `igual`) **o** devolvió `nivel == "alto"`. Es **persistente**: una consulta posterior de otra
  categoría no lo baja.
- **Categoría determinada** si el caso es de alto riesgo, o si la **última** consulta de riesgo fue
  conocida (con nivel). Sin consultas, o con la última desconocida o con error, no está determinada.
  La categoría la pone el analista y la delega el coordinador (#6); el hook solo mira lo que
  la herramienta respondió.
- Un caso de alto riesgo **requiere escalamiento**; uno con categoría no determinada **no requiere
  escalamiento, pero no puede recomendarse habilitar** (FR-005).

## R9. Escalamiento y causas vigentes (FR-006, FR-007)

- **Causas vigentes** (`reglas.causas_vigentes`): un conjunto de textos estables. Una por cada
  coincidencia registrada (`listas:<tipo>:<identificador|nombre normalizado>`) y `alto_riesgo` si el
  caso es de alto riesgo.
- `PostToolUse` sobre `escalar_a_cumplimiento` con resultado `caso_escalado` guarda en el libro una
  **instantánea de las causas vigentes en ese momento**. Un escalamiento con error (llega por
  `PostToolUseFailure`) no cuenta.
- El caso está **cubierto** si alguna instantánea contiene todas las causas vigentes (`>=`). Una
  coincidencia o un alto riesgo posterior a la instantánea quedan fuera, así que hace falta escalar
  de nuevo (caso límite «escalamiento ejecutado y luego nueva coincidencia»).
- Las causas **no incluyen el texto** del escalamiento: el contenido del resumen al oficial es del
  #10 y el hook no lo valida (FR-016).

## R10. Conjunto cerrado de recomendaciones del informe (FR-019)

`registrar_informe.recomendacion` es texto libre en el servidor (#5), que no valida reglas. El
conjunto cerrado vive en `reglas.RECOMENDACIONES`, tres valores:

| Valor | Significado | Cuándo aplica |
|-------|-------------|---------------|
| `habilitar` | Recomienda habilitar al comercio. | Solo si no hay coincidencias, no es de alto riesgo, la categoría está determinada y se consultaron listas para el comercio y su representante. |
| `no_habilitar` | Recomienda no habilitar. | Siempre admisible. |
| `decide_cumplimiento` | No recomienda: la decisión es de un oficial. | Siempre admisible; es lo que corresponde a un caso de alto riesgo o con coincidencia, después de escalar. |

- La comparación normaliza (sin tildes, minúsculas, espacios y guiones a `_`), de modo que `No
  habilitar` se reconoce. **Cualquier otro valor se rechaza** con un motivo que lista los tres.
  Es más estricto que lo que dice la spec (tratarlo como `habilitar` solo si una regla aplica):
  se rechaza también cuando ninguna aplica, porque un informe con una recomendación que ningún
  consumidor puede interpretar tampoco debe quedar registrado. La spec se ajusta en el mismo
  sentido (edge case y asunto de FR-019).
- Las reglas 1 a 3 **solo impiden `habilitar`**. `no_habilitar` y `decide_cumplimiento` no se
  rechazan por esas reglas; sí por la exigencia de escalar antes cuando el caso lo requiere
  (US2.3 y US3.3).
- Qué texto va a los hallazgos y a la cobertura sigue siendo del #8 y del #9. La descripción de
  `registrar_informe` en el servidor nombra los tres valores como guía (el servidor no los valida);
  la garantía es el hook.

## R11. Instrucciones del coordinador y modo de demostración (FR-014, FR-019)

- Se retiran `PROHIBICION_DECISION` y la regla 5 («No decidas la habilitación del comercio»). La
  regla 4 pasa a ser la instrucción mínima: *«Si hay una coincidencia en listas restrictivas o la
  categoría es de alto riesgo, llama a escalar_a_cumplimiento. Al final registra el informe con
  registrar_informe y una recomendación que sea exactamente habilitar, no_habilitar o
  decide_cumplimiento. Cuando el caso se escaló (coincidencia en listas o alto riesgo), la
  recomendación es decide_cumplimiento; no_habilitar es para un caso que no requiere escalamiento y
  no se habilita; habilitar, solo si no hay coincidencia, el comercio no es de alto riesgo y la
  categoría quedó determinada.»* Es guía; la garantía son los hooks. El resumen al analista
  (regla 5) se conserva sin la frase prohibida.
- Se reescriben los tests de `test_coordinador.py` que citan la prohibición (líneas 138-144 y 170-171
  del #6): ahora comprueban que **no** está y que la instrucción mínima sí.
- **Modo de demostración**: `PASARELA_MODO_DEMO_HOOKS=1` (se lee por caso desde `entorno`, como las
  demás `PASARELA_*`; no se reenvía al servidor). Un valor distinto de `1` es modo normal.
  `instrucciones_coordinador(demo)` omite, en demo, la regla 3 (no seguir con listas ante varias
  coincidencias) y la instrucción de escalar; conserva la delegación, el resumen y la instrucción de
  registrar el informe, para que el modelo pueda intentar lo prohibido. Los subagentes **no
  cambian**: sus instrucciones no contienen reglas de negocio 1 a 3 (solo «una mención en
  noticias no es una coincidencia en listas», que es la guía de IV, no una de las tres reglas).
- Al arrancar el caso en demo se deja el evento `modo_demostracion`, para que la interfaz y quien
  lea el registro sepan que las reglas no están en el prompt. **Los hooks no cambian en demo.**
  No hay forma de desactivarlos.

## R12. Eventos y residuales

- **Eventos nuevos** en `eventos.py`: `bloqueo_regla`, `cierre_impedido`, `cierre_sin_escalar`,
  `fallo_de_hook`, `escalamiento_registrado` y `modo_demostracion`. `Evento` gana un campo
  `regla: str | None` (`"I.1"`, `"I.2"`, `"I.3"`; por defecto `None`, así los eventos del #6 no
  cambian) y `RegistroEventos.registrar` un parámetro opcional con el mismo nombre. El motivo va en
  español y no repite nombres ni identificadores consultados (FR-016).
- **Residuales declarados** (van a `DECISIONES.md`):
  1. Las reglas valen para lo que pasa por las herramientas del SDK con los hooks del caso. Quien
     llame directamente al servidor MCP o escriba en `resultados/` por otra vía las salta; es el
     alcance del principio II para este ticket.
  2. `recomendacion` es una etiqueta: que el texto de los hallazgos o el resumen digan otra cosa es
     materia de #9 y #10.
  3. Un hook que se cuelga: el efecto del tiempo límite del SDK no se midió.
  4. La carrera de R6: un `listas` pedido en el mismo turno que `registro` puede rechazarse una vez
     y exigir reintento.
  5. Si el registro cambia de comercio **después** de un informe ya registrado, el informe no se
     anula (los informes son del #9).
  6. Un caso donde un hook de registro falla queda bloqueado en lugar de degradarse: es deliberado.
- **Qué no se midió**: el efecto del tiempo límite de un hook que se cuelga; el comportamiento con
  varios `PostToolUse` simultáneos del mismo matcher más allá de lo que garantiza `asyncio`;
  la ejecución completa de un caso real en modo demostración (la hace Q5 con el coordinador real).
