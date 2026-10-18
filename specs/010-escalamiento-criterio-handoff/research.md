# Research: Escalamiento con criterio, handoff y ambigüedad (#10)

Parte de la spec commiteada en `d49aed0`, con la revisión de la analista.

Lo marcado *(medido)* se comprobó con `claude-agent-sdk` 0.2.168, Haiku 5.5 y una herramienta en proceso. Fue en un script del scratchpad fuera del repositorio, con una carpeta de trabajo temporal y sin leer el archivo de entorno. Coste ≈ 0,0014 USD. Lo demás se apoya en lo que ya midieron el #7 (deny, `Stop`, `PostToolUse`), el #8 (`updatedInput` con la entrada completa y los turnos) y el #9 (rechazo del informe en JSON).

## R1. Continuar el caso con otro mensaje del analista (FR-013, FR-019)

**Decision**: `Caso.ejecutar(solicitud)` sigue siendo el primer turno. Un método nuevo, `Caso.continuar(mensaje)`, lanza otra `query()` del coordinador con `resume=<session_id>` del último `ResultMessage`. Lo hace con las mismas opciones del caso: el mismo `HooksDelCaso`, el mismo `Delegador` y un servidor de delegación nuevo sobre el mismo `Delegador`.

- El estado, el libro, los eventos y el historial del `Delegador` son los del objeto `Caso`, así que no se pierde nada (FR-013).
- `opciones_base` acepta un `resume` opcional. Sigue siendo la única que construye `ClaudeAgentOptions`.
- Sin `session_id` (no llegó ningún `ResultMessage`), `continuar` lanza un error claro y no inventa una sesión.
- Cada turno se clasifica por separado (`Clasificacion`) y queda en `caso.turnos_del_caso`, una lista; `caso.terminacion` es la del último turno.

**Medido**:
- La segunda `query()` con `resume` **conserva el contexto** del primer turno, con el mismo `session_id`.
- Los hooks del turno reanudado (`PreToolUse` y `Stop`) **se ejecutan**, y también la herramienta de un servidor en proceso **creado de nuevo**.
- `num_turns` es **del turno, no acumulado** (2 y 2). Así, `MAX_TURNOS_SEGURIDAD` y el presupuesto valen por turno (R10).
- `stop_hook_active` vuelve a `False` en el turno nuevo. No se usa como contador, como en el #7.

**Rationale**: `resume` mantiene la forma de `ejecutar` (una `query()` por turno, terminada por su razón de parada) y no deja un proceso abierto entre mensajes. Eso sirve para la línea de comandos y para la interfaz del #11, que puede volver a ejecutarse entre mensajes.

**Alternatives considered**:
- **`ClaudeSDKClient` abierto entre turnos**: conserva el contexto sin disco, pero obliga a mantener vivo un proceso y un bucle de eventos entre mensajes del analista, que no encaja con la línea de comandos ni con el #11.
- **Volver a mandar toda la conversación en el `prompt`**: duplica texto, rompe la caché y deja que el texto del modelo sea la fuente del estado.
- **Un caso nuevo por mensaje con el estado copiado**: pierde la sesión del modelo y obliga a reconstruir el estado a mano.

## R2. Mensajes del analista (FR-020)

**Decision**: `EstadoCaso.mensajes: list[str]` guarda cada texto del analista en orden. `ejecutar` y `continuar` lo añaden antes de lanzar la `query()`. `solicitud` pasa a ser una propiedad (el primer mensaje) por compatibilidad con los tests del #6 al #9. Cada mensaje deja el evento `mensaje_analista`, sin repetir el texto.

**Rationale**: la categoría se compara con lo que escribió el analista, no con lo que transcribió el modelo, y el evento hace visible el turno en la traza (principio VI) sin copiar datos del comercio.

## R3. Esperas del analista (FR-014, FR-016, FR-018)

**Decision**: una función pura, `reglas.espera_del_analista(estado) -> Espera | None`, devuelve la espera y su motivo con textos fijos. Hay tres:

| Espera | Condición (el código la comprueba) |
|--------|-------------------------------------|
| `identificador` | El registro terminó y su consolidación da `varias` coincidencias. |
| `nombre` | El registro terminó y su consolidación da `ninguna` coincidencia. |
| `categoria` | `estado.categoria_bloqueada` (la última delegación de categoría la bloqueó FR-020) y `libro.consultas_riesgo` está vacía. |

- Para no decidir por subcadenas del motivo (sugerencia de la revisión del #7), `Identificacion` gana un campo `clase` (`unica`, `varias`, `ninguna`, `contradictoria` o `invalida`), que fija `derivar_comercio`. `EstadoCaso.clase_identificacion` lo consolida igual que `comercio`. `_motivo_sin_comercio` pasa a leer la clase.
- La clase sale de una función hermana pura, `clase_de(resultado)`, junto a `derivar_comercio`, que sigue devolviendo `(comercio, motivo)` para no tocar a sus llamadores.
- `contradictoria` (D3 del #9) **no** es una espera (decisión de la analista).
- **El registro caído, por sí solo, no es una espera**. La espera `categoria` vale con cualquier estado del registro, también el caído, porque solo mira `categoria_bloqueada` y `consultas_riesgo`. Con el registro en `varias` o `ninguna`, prevalece el motivo del registro.
- **Durante la espera `identificador` o `nombre`** (FR-016):
  - el `PreToolUse` de `registrar_informe` rechaza el informe con su motivo fijo: `MOTIVO_INFORME_ESPERA_IDENTIFICADOR` («El registro devolvió varias coincidencias: pida el identificador al analista antes de registrar el informe.») o `MOTIVO_INFORME_ESPERA_NOMBRE` («El registro no encontró el comercio: pida al analista que revise el nombre antes de registrar el informe.»);
  - la regla del evento es `V`;
  - el rechazo va en `informe_rechazado` junto a los demás motivos;
  - con el sello, no cambia: el informe mínimo exige escalar antes, y el escalamiento se admite (R5).

  **Cambio respecto al #9**: el #9 aceptaba el informe con el comercio pedido (`verificado: false`) ante varias coincidencias; FR-016 lo rechaza.
- **Durante la espera `categoria`** el informe sigue las reglas de siempre (sin categoría determinada no se puede `habilitar`).
- En el `Stop`, la espera se comprueba **antes** que `evaluar_cierre`. Si la hay, el `Stop` permite terminar sin tocar `cierres_impedidos` y deja el evento `espera_analista` con el motivo.
- **La espera de la categoría exime solo del informe** (corrección de la parada A): si con ella falta escalar (una coincidencia en listas o el sello), el `Stop` evalúa el escalamiento como un cierre normal, con su devolución o la marca `cierre_sin_escalar` al agotarlas. Las esperas del registro no lo necesitan: sin identificación no hay listas ni coincidencias.
- Con el sello, la espera no cambia: el `Stop` la admite igual, y escalar se admite (R5).

**Rationale**: las tres condiciones salen del estado que escriben los hooks y el `Delegador`, no del texto del modelo. Una pregunta del coordinador con el comercio identificado y la categoría con resultado sigue siendo un cierre (FR-015).

**Alternatives considered**: una herramienta `pedir_dato_al_analista` que el modelo llame para declarar la espera. Se descartó porque el modelo podría llamarla para saltarse el cierre; la espera tiene que comprobarla el código.

## R4. Contador y marcas del cierre por turno

**Decision**: al empezar cada turno (`ejecutar` y `continuar`), `libro.cierres_impedidos` vuelve a 0, y `cierre_sin_escalar` y `cierre_sin_informe` vuelven a `False`. Son del último cierre, no del caso entero.

**Rationale**: las devoluciones gastan turnos del `max_turns` del turno (R1, medido). Si un turno agotó las devoluciones y el analista sigue la conversación, el turno siguiente tiene que poder escalar e informar.

`Caso.completo` **sí** lee `cierre_sin_escalar` y `cierre_sin_informe` (`coordinador.py:224-225`), así que reiniciarlas podría parecer que debilita la garantía del #7. No la debilita, por dos razones:

- **El `Stop` vuelve a evaluar al final de cada turno.** Si el turno nuevo tampoco escala o informa, agota sus devoluciones y vuelve a poner la marca.
- **`informe_vigente` depende de las causas** (huella del #9). Un informe solo cuenta si se registró después de escalar las causas vigentes.

Dos tests lo fijan:

- **(a)** El turno 1 agota las devoluciones sin informe. El turno 2 registra el informe vigente. Resultado: `completo` es verdadero y no queda ninguna marca.
- **(b)** El turno 1 agota las devoluciones. El turno 2 termina sin hacer nada. Resultado: la marca vuelve a quedar puesta y `completo` es falso.

## R5. Escalamiento con criterio y resumen al oficial (FR-001 a FR-012, FR-016)

**Decision**: el `PreToolUse` de `escalar_a_cumplimiento` (`_escalar_previo`) pasa a decidir y completar, como el del informe. Sigue envuelto en `degradar_escalamiento`, que nunca deniega ante una excepción. Hace esto, en orden:

1. **Con el sello** (`fallo_de_hook`): no valida reglas ni fuentes, porque el libro puede haber perdido un hecho.
   - Pone el comercio del código (o el pedido, `verificado: false`), la cobertura `COBERTURA_NO_CALCULADA`, los conflictos `no_calculados()` y la causa con las etiquetas de las causas vigentes, entre ellas el sello.
   - Sin comercio identificado ni pedido, pone `COMERCIO_NO_IDENTIFICADO`: `{"identificador": "no identificado", "nombre": "no identificado", "verificado": false}`. Son textos fijos que pasan la validación de forma de la pasarela, así que FR-012 se cumple. `degradar_escalamiento` usa el mismo comercio cuando la excepción llega antes de calcularlo.
   - Deja pasar el escalamiento; la forma la valida la pasarela.
   - Es la excepción de FR-016: se admite también durante la espera del identificador.
2. **Espera del identificador o del nombre** (R3): deniega con `MOTIVO_ESPERA_IDENTIFICADOR` o `MOTIVO_ESPERA_NOMBRE`.
3. **Bajo riesgo sin hallazgos comprobado** (`reglas.bajo_riesgo_sin_hallazgos(estado)`, FR-002): deniega con `MOTIVO_SIN_CAUSA`. La función es pura y exige todo esto:
   - `calcular_cobertura(estado).completa`, con FR-027 (R7);
   - sin coincidencias;
   - `categoria_determinada` y no `es_alto_riesgo`;
   - la última consulta de noticias del comercio identificado con resultado `sin_coincidencias`;
   - `calcular_conflictos(estado).estado == "sin_conflictos"`;
   - sin sello.
4. **Forma y fuentes**: `validar_resumen` (R6) sobre la entrada completa, `problemas_de_fuente` (FR-004 del #9, con la restricción de R7) y `problemas_de_frentes_cubiertos`.
   - Si hay problemas, deniega con el JSON `resumen_rechazado`, que nombra todos.
   - Sin comercio (ni identificado ni pedido), deniega con `MOTIVO_SIN_COMERCIO_ESCALAMIENTO`: «Delegue primero el registro mercantil: el oficial necesita saber de qué comercio se trata.» Es la desviación D2 del plan: contradice FR-003 cuando el alto riesgo se detecta antes de delegar el registro.
5. **Si acepta**: devuelve la entrada completa con `updatedInput`.
   - **Del código**: comercio, cobertura (`lineas()`), causa y conflictos (`como_entrada()`).
   - **Del coordinador, tal cual**: hallazgos y acción recomendada.
   - Deja los eventos `cobertura_sustituida` y `datos_sustituidos`.
   - Guarda el escalamiento como pendiente por `tool_use_id`, con las causas y la clave del comercio (R8).

**La causa** (FR-009) es una lista de textos:

- con causas vigentes, una línea por causa con `ETIQUETAS_CAUSA`;
- sin causas (FR-003), una línea por cada motivo que se cumpla, con etiquetas fijas de `MOTIVOS_SIN_CAUSA`, en este orden:
  - `cobertura_incompleta`: «Sin causa de escalamiento vigente: la cobertura está incompleta.»
  - `categoria_no_determinada`: «Sin causa de escalamiento vigente: la categoría no quedó determinada.»
  - `mencion_en_noticias`: «Sin causa de escalamiento vigente: hay menciones en noticias.»
  - `conflicto_entre_fuentes`: «Sin causa de escalamiento vigente: hay conflictos entre las fuentes registrales.»

  Lo calcula `causas_del_resumen(estado)` con las mismas lecturas que `bajo_riesgo_sin_hallazgos`. Si no se cumple ninguno, el caso es de bajo riesgo comprobado y el escalamiento ya se rechazó (paso 3).

**Rationale**: es el mismo patrón que el informe del #9 (validar, sustituir y confirmar en el `PostToolUse`). El escalamiento solo se deniega cuando el código puede afirmar que no corresponde (FR-002) o que falta el identificador (FR-016). En cualquier duda, o ante una excepción, sale.

**Cambio respecto al #8**: el escalamiento deja de «no denegarse nunca» en dos casos: el bajo riesgo comprobado y la espera del identificador. La protección ante un fallo calculando la cobertura se conserva (FR-012).

**Alternatives considered**: validar el resumen solo en la pasarela. Se descartó porque FR-004 (fuente consultada) solo se puede comprobar con el caso, igual que en el #9.

## R6. Esquema del resumen al oficial (FR-006 a FR-011)

**Decision**: `servidor_mcp/informe.py` gana `validar_resumen(entrada)` y `mensaje_resumen(problemas)`. Comparten con `validar_informe` los validadores de `comercio`, `hallazgos` (afirmaciones), `conflictos` y `cobertura`:

| Campo | Forma | Quién lo pone |
|-------|-------|---------------|
| `comercio` | `{identificador, nombre, verificado}`, como en el informe | código |
| `hallazgos` | por frente, lista de `{texto, fuente, fecha}`, como en el informe | coordinador |
| `cobertura` | texto o lista de textos | código |
| `causa_escalamiento` | texto o lista de textos no vacíos | código |
| `accion_recomendada` | texto no vacío | coordinador |
| `conflictos` | `{resumen, lista}`, como en el informe | código (FR-010) |

- **En la pasarela** (`decisiones.escalar_a_cumplimiento`): los cinco de primer nivel siguen nombrándose todos con `campos_obligatorios_ausentes`, como en el #5 (FR-007). `conflictos` es obligatorio en la pasarela, como en el informe del #9, porque el hook siempre lo pone. Después, la forma da `entrada_invalida` con todos los `problemas`. Se quita `_validar` (forma vieja `{contenido, fuente}`).
- **En el hook**: el rechazo es el JSON `resumen_rechazado`, con la misma forma que `informe_rechazado` del #9 (`motivos` y `problemas`). Se construye con una función común, `denegar_decision(tipo, …)`, que sustituye a `denegar_informe` y resuelve la duplicación que señaló la revisión del #9.
- La `PasarelaSimulada` valida con `validar_resumen`, como el informe (R12 del #9).

**Rationale**: un solo validador para la forma (I.4), como en el #9, y los mismos mensajes en español con todos los problemas.

## R7. Frente consultado con otro nombre (FR-027) y fuentes de FR-004

**Decision**: una función pura, `reglas.consulta_del_comercio(argumentos, comercio)`, dice si una consulta de noticias es del comercio identificado. Es así si su `identificador` coincide con `igual_identificador` o su `nombre` con `igual`, la misma normalización del servidor.

- **Cobertura** (`cobertura._del_frente`): noticias `terminado` cuenta como cubierto solo si no hay comercio identificado o si alguna consulta válida de su último resultado (`estado.resultados[NOTICIAS].consultas`) es del comercio. Si no, queda no cubierto, con la causa nueva `Causa.OTRO_COMERCIO` y el motivo fijo «se consultó con un nombre o identificador que no es el del comercio identificado».
- **Fuentes** (`informe.fuentes_consultadas`): para noticias y listas, con el comercio identificado, solo cuentan las consultas del comercio (o, en listas, de su representante). Así una afirmación de noticias no puede apoyarse en la consulta del primer turno. Esto resuelve el riesgo residual 8 del #9 para esos dos frentes.
- La categoría no se toca: no depende del comercio.

**Rationale**:
- **Cálculo puro**: al vivir en la cobertura, cambia la huella del informe (FR-023 del #9) y la condición de FR-002 sin ningún mecanismo más. No hay carrera con un frente de noticias que termina después del registro.
- **Datos del caso (d)**:
  - noticias consultado con «Almacén Mirador SAS» sigue cubierto si el analista elige `CO-AM-0004`, que es ese nombre;
  - deja de estarlo si elige `CO-AM-0005`, «Almacén Mirador Norte SAS», y N-0001 aparece al volver a delegar.

**Alternatives considered**: invalidar noticias en el `Delegador` al cambiar el comercio, como `_invalidar_listas`. Se descartó porque no cubre un noticias que termina después del registro y añade un estado que la cobertura ya puede calcular.

## R8. Escalamiento vigente para el comercio actual (FR-004)

**Decision**: `libro.escalamientos` pasa de `list[frozenset[str]]` a `list[Escalamiento]`, con `causas` y `comercio`. `comercio` es la misma clave de la huella del #9: `(identificador, nombre, verificado)` de `comercio_del_informe`.

- `escalamiento_cubre` solo mira los escalamientos del comercio actual.
- `escalado_para_el_comercio(estado)`, función nueva, dice si hay alguno para el comercio actual, aunque el caso no tenga causas.
- `evaluar_informe` rechaza `decide_cumplimiento` sin un escalamiento para el comercio actual, con `MOTIVO_DECIDE_SIN_ESCALAR`. Con el sello ya lo exige `evaluar_informe_minimo`, porque el sello es causa.
- El `PostToolUse` confirma el escalamiento pendiente (R5) solo si la pasarela devuelve `caso_escalado`. El `PostToolUseFailure` lo descarta. Es el mismo patrón que la huella del informe (R7 del #9). Ahora el `PostToolUse` lee las causas de lo pendiente: las del momento en que se aceptó, no las del momento en que llegó la respuesta.

- **Un segundo escalamiento sin causa nueva** (caso límite de la spec) se admite y deja el mismo evento, `escalamiento_registrado`, con su id y las causas que cubre. No hay un tipo de evento distinto: para el cierre no cambia nada, y el evento ya dice qué cubre.

**Rationale**: un escalamiento del comercio anterior no cubre al nuevo, ni para el cierre ni para admitir `decide_cumplimiento` (caso límite de la spec).

## R9. Categoría de los mensajes del analista (FR-020)

**Decision**: el `PreToolUse` de `delegar_frente` (`_delegar_previo`) también vigila el frente de categoría. Con `reglas.categoria_en_mensajes(categoria, mensajes)`, la categoría tiene que aparecer en algún mensaje.

- **Comparación**: con la normalización de `servidor_mcp.normalizar`, como frase completa delimitada por espacios: `f" {normalizar(categoria)} "` contenido en `f" {normalizar(mensaje)} "`. Así «suplementos dietarios» aparece en «…ventas en línea de suplementos dietarios…» y «ropa» no aparece en «tropa».
- **Si no aparece**: deniega con la regla `I.3`, la acción `delegar_frente categoria` y `MOTIVO_CATEGORIA_NO_DEL_ANALISTA` («La categoría no aparece en los mensajes del analista: use la que dio o pregúntesela.»). Marca `estado.categoria_bloqueada = True`.
- **Si aparece**: permite y deja `categoria_bloqueada = False`.
- **Una entrada sin categoría** se deja pasar: la rechaza el `Delegador`, como desde el #6.
- **Con el sello**: no se deniega por el sello, porque delegar la categoría no decide nada. Las reglas de listas sí siguen selladas.

**Riesgos declarados**:
- la normalización no cubre plurales («suplemento dietario» frente a «suplementos dietarios»; US5-5);
- un mensaje que menciona varias categorías («no vende apuestas, vende ropa») deja pasar las dos. No se añade nada para una categoría de alto riesgo mencionada: escalar de más por una negación también es un error (principio V).

**Alternatives considered**:
- Extraer la categoría del texto con código: es adivinar.
- Un campo estructurado de categoría en la solicitud: cambia la interfaz del analista, que es del #11.

## R10. Presupuesto de turnos

**Decision**: el presupuesto es por turno, porque `num_turns` es del turno (R1, medido). Los pasos fijos del peor caso suben de 8 a 10:

- **escalamiento rechazado por la forma y corregido**: un turno más, como el informe rechazado del #9;
- **noticias vuelto a delegar** tras identificar al comercio (FR-027): un turno más en el segundo turno del caso (d).

`PRESUPUESTO_TURNOS_PEOR_CASO = 10 + 4 + 4 + 3 = 21 ≤ 30`. El test del #8 y del #9 cambia el valor esperado de 19 a 21, sin debilitarse.

Una espera no gasta devoluciones: termina el turno.

**El turno 2 del caso (d)** tiene menos pasos que el peor caso del turno 1: registro con el identificador y noticias de nuevo (juntos), listas, escalar (con un rechazo de forma), el informe (con un rechazo) y la respuesta. No vuelve a delegar la categoría, que se conserva.

## R11. Instrucciones del coordinador (FR-028, FR-011)

**Decision**: tres guías nuevas en `coordinador.py`, con sus tests de texto:

1. **`_REGLA_TRAS_IDENTIFICAR`** (FR-028, en los dos modos): «Si listas se rechazó porque el comercio no estaba identificado, ese rechazo deja de valer cuando el registro lo identifica: vuelve a delegar listas, aunque el rechazo dijera reintentable false. Vuelve a delegar también noticias con el comercio identificado si lo consultaste con otro nombre.» No es una regla I.1 a I.3, así que va también en el modo de demostración. El test comprueba el texto en los dos modos.
2. **`_REGLA_RESUMEN_OFICIAL`** (FR-011): pide escribir los hallazgos del resumen como las afirmaciones del informe y una acción recomendada dirigida al oficial. El comercio, la cobertura, la causa y los conflictos los pone el sistema. Va en los dos modos, porque es la forma del canal, no una regla de escalar.
3. **`_REGLA_VARIAS_COINCIDENCIAS` (ampliada)**: «…pide al analista el identificador y termina tu turno sin escalar ni registrar el informe; cuando responda, sigue en el mismo caso.» La quita el modo de demostración, como en el #7.

Además, `_REGLA_ESCALAR` dice «No escales un comercio de bajo riesgo sin ningún hallazgo» (guía de V; la garantía es FR-002). La descripción de `delegar_frente` añade que la categoría tiene que ser la que dio el analista.

## R12. Simulación y línea de comandos

**Decision**:
- **`CoordinadorSimulado`**: acepta varios guiones, uno por turno (`guiones=[[…], […]]`). Cada llamada consume el siguiente. Lee `options.resume` y devuelve un `ResultMessage` con un `session_id` estable. Los pasos `("escalar",)` y `("escalar_con", …)` pasan a armar un resumen válido con `resumen_del_caso(estado, accion)`, el par de `informe_del_caso`.
- **`PasarelaSimulada`**: `_escalar` valida con `validar_resumen`, y `_noticias` devuelve N-0001 para `CO-AM-0005`.
- **`__main__`**: tras imprimir el caso, si `reglas.espera_del_analista(caso.estado)` hay espera, pregunta en la entrada estándar («El coordinador espera su respuesta; escríbala o deje la línea vacía para terminar:»). Con un texto, llama a `caso.continuar(texto)` y vuelve a imprimir. Con una línea vacía o fin de entrada, termina. Con `--sin-continuar` no pregunta, para los tests. Imprime también los escalamientos registrados y la espera del analista.

## R13. Riesgos residuales

1. **Plurales y varias categorías en FR-020** (R9).
2. **Coincidencias de un comercio anterior**: siguen siendo causas si el analista cambia de comercio, porque el libro no las borra (comportamiento desde el #7). El caso nuevo tendría que escalarse de nuevo, y su resumen mostraría la causa «coincidencia del comercio» sin una afirmación que la respalde: R7 no deja citar la consulta del otro comercio. Es conservador: escala de más, nunca habilita de más (D1 del plan).
8. **Sin comercio no se escala** (D2 del plan): un alto riesgo detectado antes de delegar el registro no se puede escalar hasta que el registro dé un comercio pedido o identificado.
9. **Alto riesgo en la espera del identificador o del nombre** (D3 del plan): el escalamiento se rechaza hasta identificar al comercio.
3. **`resume` depende de la persistencia de sesiones del SDK** en el disco del usuario. Si se pierde la sesión, `continuar` falla con un error claro y el estado del caso sigue en memoria.
4. **D1 y D7 del #9** aplican también al resumen (Supuestos de la spec).
5. **Riesgo residual 1 del #9** (informe vigente con afirmaciones viejas): decisión aceptada, sin cambio.
6. **El texto de la respuesta al analista** sigue siendo del modelo: que muestre las coincidencias y pida el identificador es guía. Lo garantizado es que no se consultan listas, no se escala y no se informa sin identificador.
7. **La acción recomendada** no se contrasta con nada: es texto del coordinador para el oficial.
