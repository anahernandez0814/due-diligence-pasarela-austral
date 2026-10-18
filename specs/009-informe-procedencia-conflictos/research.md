# Research: Informe con procedencia, conflictos y registro (#9)

Parte de la spec aprobada (`6dce052`) y de las indicaciones de la analista para el plan. No hubo
mediciones con el modelo ni con el SDK: todo lo que el diseño necesita del SDK ya lo midieron el
#7 (deny, `Stop`, `PostToolUse` y `PostToolUseFailure` del coordinador) y el #8 (`updatedInput`
sustituye la entrada entera, y los turnos). Lo que no está medido se marca *(no medido)* y lo
comprueba el quickstart con el modelo real.

## R1. Dónde se valida cada cosa

**Decisión**: la validación se reparte según quién tiene el dato. Nada obligatorio queda en el
prompt.

| Qué | Dónde | Por qué |
|-----|-------|---------|
| Esquema del informe (FR-001, FR-002): partes, afirmaciones con texto, fuente y fecha válida, claves de frente conocidas | **Pasarela** (`servidor_mcp/informe.py`, función pura) **y hook**, que reutiliza la misma función | La pasarela es el contrato del registro y no debe guardar un informe mal formado venga de donde venga (FR-005). El hook lo comprueba antes para que el coordinador reciba en un solo rechazo todo lo que falla. |
| Fuente consultada (FR-004) | **Hook** `PreToolUse` de `registrar_informe` | La pasarela no conoce el estado del caso (indicación de la analista). Las fuentes salen de las consultas válidas del caso. |
| Al menos una afirmación por frente cubierto (US1-6) | **Hook** `PreToolUse` de `registrar_informe`, salvo con el caso sellado | Igual que FR-004: qué frentes quedaron cubiertos depende del estado del caso (`calcular_cobertura`). Un frente no cubierto puede ir vacío (I.5). Con el sello la cobertura no se calcula (R9), así que no se exige. Se añadió tras la revisión del commit `2004581`. |
| Comercio del informe (FR-006) | **Hook**, por sustitución (R5) | Lo decide la identificación del #6, o el comercio pedido con el registro caído. |
| Conflictos (FR-007 a FR-009) | **Código puro** (`conflictos.py`) y sustitución en el **hook** | Se comparan datos estructurados del registro. |
| Cobertura (#8) | Sin cambios: `cobertura.py` y sustitución en el hook | |
| Reglas I.2 e I.3 y orden escalamiento → informe (FR-012, FR-015) | Sin cambios: `evaluar_informe` en el hook | Ya lo garantiza el #7. |
| Informe obligatorio y vigente (FR-011, FR-013, FR-023) | **`Stop`** del coordinador (`evaluar_cierre`) y `PostToolUse` de `registrar_informe` | El cierre ya es el punto donde se exige el escalamiento. |
| Informe mínimo tras un fallo de hook (FR-014) | **Hook** `PreToolUse` de `registrar_informe` | Es donde hoy se deniega por el sello. |

**Alternativas descartadas**:
- Validar todo en la pasarela inyectando las fuentes consultadas por `updatedInput`: contradice la
  indicación de la analista, y la pasarela pasaría a depender de un dato del caso.
- Validar el esquema solo en el hook: un cliente sin hooks podría guardar un informe sin fuentes.

## R2. Esquema del informe

**Decisión**: `registrar_informe` recibe cinco partes y se valida con una función pura,
`validar_informe(entrada) -> list[Problema]`, en `src/servidor_mcp/informe.py`. Cada problema
tiene una ruta (`hallazgos.listas[1].fuente`) y un texto en español, y se devuelven **todos**. El
detalle está en [contracts/registrar-informe.md](contracts/registrar-informe.md).

- `comercio`: `{identificador, nombre, verificado}`. Con `verificado: true` hacen falta los dos
  textos; con `false` basta uno.
- `hallazgos`: objeto cuyas claves son frentes (`registro`, `listas`, `noticias`, `categoria`).
  Cada valor es una lista de afirmaciones `{texto, fuente, fecha}`. Un frente ausente equivale a
  una lista vacía y una clave desconocida es un problema.
- `fecha`: `AAAA-MM-DD`, que sea una fecha real.
- `conflictos`, `cobertura` y `recomendacion`: los dos primeros los pone el código (R5) y la
  pasarela solo comprueba su forma; la recomendación sigue siendo texto, y el conjunto cerrado lo
  valida el #7.

Validación escrita a mano, no con pydantic: la convención del servidor exige mensajes en español
y nombrar todos los campos que faltan (`src/servidor_mcp/CLAUDE.md`).

**Por qué la afirmación junta texto, fuente y fecha en un objeto** (hallazgo T3 del análisis,
decisión de la analista: se justifica y no cambia el formato). La convención `{contenido,
metadatos}` del proyecto es para los **resultados** de la pasarela: lo que devuelve una fuente y
lo que el principio III pide separar. La afirmación es lo contrario, la **cita** que el
coordinador escribe a partir de esos resultados. Su fuente y su fecha son la referencia que I.4
exige junto a cada frase, no metadatos de la herramienta que la recibe. Un objeto plano de tres
campos obligatorios es más difícil de enviar incompleto que uno anidado y deja rutas cortas en
los problemas (`hallazgos.listas[1].fuente`). `ValorFuente` sigue el mismo criterio: es una cita
de cada fuente en conflicto. El esquema JSON de cada
parámetro se publica en `tools/list` con `json_schema_extra`, como el resto de herramientas.

`escalar_a_cumplimiento` **no cambia de formato** en este ticket (spec, supuestos): su validación
de `hallazgos` se separa de la del informe.

## R3. Rechazo del informe como error estructurado

**Decisión**: cuando el hook deniega `registrar_informe`, el motivo (`permissionDecisionReason`)
es el **JSON de un error estructurado**, con la misma forma que los de la pasarela:

```json
{"error": true, "tipo": "informe_rechazado", "mensaje": "…", "reintentable": false,
 "motivos": [{"regla": "I.2", "texto": "…"}],
 "problemas": [{"ruta": "hallazgos.listas[1].fuente", "texto": "…"}]}
```

`mensaje` junta todos los motivos y problemas en una frase. `reintentable: false` porque la misma
entrada volvería a fallar; el mensaje dice que se corrija y se vuelva a registrar. Los rechazos de
la pasarela (esquema) ya son estructurados: `entrada_invalida` con `problemas`.

**Por qué**: FR-003 y la constitución IV piden un error estructurado. El #7 denegaba con texto
plano; los tests del #7 que buscan el motivo como subcadena siguen pasando, porque el JSON lo
contiene (`ensure_ascii=False`). *(No medido: cómo presenta el SDK al modelo un motivo largo en
JSON; lo comprueba Q3.)*

**Alternativa descartada**: texto plano con las rutas enumeradas. Se entiende, pero no es un
error estructurado.

**Aceptada por la analista**; Q3 lo comprueba con el modelo real.

## R4. Fuentes consultadas (FR-004)

**Decisión**: las fuentes admitidas de un frente son las de sus consultas **válidas** en
`estado.consultas`:

- la `fuente` de los metadatos de cada hecho;
- las fuentes de `metadatos.fuentes`. Así una respuesta `sin_coincidencias`, sin hechos, también
  da su fuente (listas y noticias la declaran ahí).

La comparación usa `servidor_mcp.normalizar.igual`, sin distinguir mayúsculas, tildes ni espacios
de más, y el texto del coordinador se guarda tal cual. Un frente sin consultas válidas, como el
registro caído, no admite afirmaciones con fuente; su lista tiene que ir vacía.

**No se exige** que la fecha de la afirmación coincida con la de la fuente: solo que sea una fecha
válida (FR-002). Queda como riesgo residual 3.

## R5. Comercio, conflictos y cobertura que pone el código

**Decisión**: el `PreToolUse` de `registrar_informe`, si acepta, devuelve `reemplazar_entrada` con
la entrada **completa** (#8, R1). Tiene `hallazgos` y `recomendacion` del coordinador, más tres
partes del código:

- `comercio`: el identificado (`estado.comercio`, con `verificado: true`) o, con el registro caído,
  el pedido (`estado.comercio_pedido`, con `verificado: false`, sin inventar el dato que falte).
  **Ajuste de la implementación** (fase 3): el pedido sin verificar se usa siempre que no hay
  comercio identificado, no solo con el registro caído. Si el coordinador registra un informe que
  no se le exige, por ejemplo con varias coincidencias, el comercio queda declarado como no
  verificado en lugar de rechazarse. Sin comercio identificado ni pedido, el hook deniega con
  `MOTIVO_SIN_COMERCIO_INFORME`;
- `conflictos`: `calcular_conflictos(estado)` (R6);
- `cobertura`: `calcular_cobertura(estado).lineas()`, como en el #8.

Se sustituye, no se rechaza, igual que la cobertura del #8: así no se gasta un turno en una
corrección que el código sabe hacer. Se mantiene `cobertura_sustituida` sin cambios y se añade
`datos_sustituidos`, que dice si el comercio se marcó sin verificar, cuántos conflictos se
pusieron y si lo declarado por el coordinador era distinto. No lleva datos del comercio.

## R6. Conflictos entre fuentes registrales

**Decisión**: un módulo puro nuevo, `src/due_diligence/conflictos.py`.
`calcular_conflictos(estado) -> ConflictosCaso`:

- Toma la última consulta **válida** del registro cuyas `coincidencias` son exactamente el comercio
  identificado, y sus hechos con ese identificador (uno por fuente). Si no hay ninguna consulta que
  cumpla eso (comercio identificado, pero sin una consulta del registro que coincida en
  `estado.consultas`), el resultado es `no_comparables`, con el mismo resumen que el registro
  caído. Nunca es `sin_conflictos`, que afirmaría algo que no se comparó (hallazgo U1).
  **Cambio tras la revisión de `/abrir-pr` (T051)**: `no_comparables` se divide en
  `registro_caido`, `sin_comercio` y `sin_consulta`, cada uno con su resumen. El resumen único
  decía que el registro no respondió también cuando sí respondió (data-model).
- `estado.consultas` solo lo escribe el `Delegador` (`delegacion.py:483`). Los helpers de los tests
  a nivel de hook (`Caso` de `test_hooks_sesiones.py` y `_caso_con_comercio` de `test_hooks.py`)
  **la llenan** con las mismas consultas que simulan, para que FR-004 y los conflictos se prueben
  como en producción.
- Compara cada dato del contenido salvo `identificador`. Si dos o más fuentes traen valores
  distintos, eso es un conflicto con un valor por fuente (`valor`, `fuente`, `fecha`), en el orden
  de la respuesta de la pasarela, que **no indica precedencia**. Un dato que trae una sola fuente
  no es conflicto. En la práctica salen `fecha_constitucion` y `estado`; el nombre y el
  representante, si difieren, ya impiden identificar el comercio (#6).
- Resumen fijo, según el caso: «Sin conflictos entre las fuentes registrales.», «N conflictos
  entre las fuentes registrales.» o «No se pudieron comparar las fuentes registrales: el registro
  no respondió.» (registro caído).
- Tras un fallo de hook (R9): «No se pudieron calcular los conflictos; deben tratarse como no
  verificados.»

Los datos ficticios ya tienen el caso (g): `CO-RF-0006`, con 2016-03-14 en el Registro Mercantil
Ficticio del Sur y 2017-09-02 en el Registro Único Ficticio de Empresas. No se añaden datos.

## R7. Informe vigente (FR-023): qué cuenta como cambio

**Decisión**, la propuesta de la analista: cada informe tiene una **huella**. Un informe está
vigente si la huella actual coincide con la del último informe registrado.

**Cuándo se calcula** (corrección de la analista): en el **`PreToolUse`** de `registrar_informe`, en
el mismo momento y con los mismos datos que se sustituyen en la entrada (R5).
- El hook la guarda como **pendiente**, con el `tool_use_id` como clave, junto con la recomendación
  y si es el informe mínimo.
- El **`PostToolUse`** solo la **confirma** si la pasarela aceptó: pasa la pendiente a
  `estado.informes`, con el id del informe.
- El `PostToolUseFailure` y los deny la descartan.

Si se calculara en el `PostToolUse`, un reintento que termina entre los dos hooks dejaría vigente un
informe con contenido viejo. Por ejemplo, `delegar_frente` y `registrar_informe` en el mismo
mensaje, que el SDK ejecuta en paralelo: el informe se arma sin el frente reintentado y la huella
se tomaría ya con él. Calculada en el `PreToolUse`, la huella describe exactamente lo que se
registró, y el `Stop` ve que cambió. Un test fija ese orden (R12).

La huella tiene cuatro componentes:

1. **Cobertura**: por frente, solo cubierto o no cubierto, sin la causa ni el número de intentos.
2. **Conflictos**: cada dato con sus pares de fuente y valor, y el resumen.
3. **Causas**: `causas_vigentes(libro)`, que con R9 incluye el fallo de hook.
4. **Comercio**: identificador y nombre del comercio del caso, más si está verificado.

Por tanto:
- un reintento que vuelve a fallar **no** invalida el informe: el frente sigue no cubierto, aunque
  cambien la causa o los intentos;
- un reintento que sale bien, un cambio de comercio, una coincidencia nueva, la invalidación de
  listas o un fallo de hook **sí** lo invalidan.

Es el patrón de `escalamiento_cubre`, que compara con las instantáneas de cada escalamiento.

**Caso sellado** (hallazgo I1). Con `libro.fallo_de_hook`, los componentes de **cobertura** y de
**conflictos** de la huella valen el marcador fijo «no calculados», sin llamar a
`calcular_cobertura` ni a `calcular_conflictos`. Pasa igual en el `PreToolUse` y en el `Stop`,
porque los dos usan `huella_actual`.
- **Por qué**: el informe mínimo registra los textos fijos en esas dos partes. Si la huella
  guardada tuviera «no calculados» y la del `Stop` calculara los valores reales, o fallara al
  calcularlos, nunca coincidirían: el cierre se devolvería hasta `cierre_sin_informe` con el informe
  registrado.
- Las **causas** (con `fallo_de_hook`) y el **comercio** se siguen calculando.
- Un informe registrado antes del sello deja de estar vigente, porque cambian las causas y los dos
  componentes. Lo correcto es pedir el informe mínimo.

El motivo del `Stop` dice qué componente cambió («cambió la cobertura después de registrarlo»),
sin datos del comercio.

**Alternativas descartadas**:
- Cualquier cambio en los resultados de los frentes: un reintento fallido exigiría otro informe
  idéntico.
- Comparar las líneas de cobertura: incluyen «; 2 intentos», y un reintento fallido lo invalidaría.

**Consecuencia**: si se vuelve a delegar noticias con otro nombre, o se cambia una categoría de
nivel bajo a medio, el informe sigue vigente aunque sus afirmaciones de ese frente queden viejas
(riesgo residual 1).

## R8. Informe obligatorio en el cierre (FR-011, FR-013) y registro caído

**Decisión**: `evaluar_cierre(estado)` comprueba, en orden:

1. el escalamiento, como en el #7;
2. si `requiere_informe(estado)`, que haya un informe vigente.

`requiere_informe` es cierto cuando hay comercio identificado o cuando hay **registro caído**. El
registro está caído si se cumplen las dos condiciones:
- la situación del registro es `no_terminado`;
- la fuente no respondió: la causa es `terminacion_anomala`, `sin_consultas`, `resultado_invalido`
  o `cancelado`, o es `error_de_fuente` con algún tipo distinto de `entrada_invalida`
  (`servicio_no_disponible`, `datos_no_disponibles` o `error_interno`).

Por tanto, `error_de_fuente` con solo `entrada_invalida` **no** es registro caído: la fuente
respondió (caso límite de la spec).

**Con o sin reintento disponible** (decisión de la analista): el registro caído exige informe aunque
la política del #8 todavía admita otro intento. El comportamiento 7 del enunciado dice que el
coordinador decide si reintenta o entrega el informe; cerrar sin ninguna de las dos cosas no vale.
- Si el último error del registro tiene `reintentable: true`, el motivo del `Stop` ofrece las dos
  salidas: «El registro mercantil no respondió: reintenta el registro o registra el informe.»
- Si ya no admite otro intento, el motivo es el general, falta el informe.
- Si después el reintento sale bien, el comercio pasa de pedido a identificado, la huella cambia y
  el informe anterior deja de estar vigente (R7).

Si faltan las dos cosas, el motivo pide escalar primero y registrar el informe después: el informe
se rechazaría hasta escalar (FR-012).

- **Contador compartido**: las devoluciones usan `libro.cierres_impedidos` y
  `MAX_CIERRES_IMPEDIDOS`. Si se agotan, se marca `cierre_sin_escalar`, `cierre_sin_informe`
  (nuevo) o los dos, según lo que faltara, con el evento `cierre_sin_informe`.
- **`Caso.completo`** pide además `not cierre_sin_informe` y un informe vigente.
- **Presupuesto de turnos**: se suma un término a la fórmula y pasa de 15 a **19 de 30**. Mantener
  15 no se puede justificar con el caso informe → reintento con éxito → informe nuevo:
  - el informe aceptado ya está entre los 8 pasos fijos del #8;
  - el reintento está en el término de reintentos (`len(Frente) × MAX_REINTENTOS_POR_FRENTE`);
  - la devolución del `Stop` por el informe no vigente está en `MAX_CIERRES_IMPEDIDOS`;
  - pero el **informe nuevo** que le sigue no está en ningún término. No sustituye a otro paso
    fijo: el «informe rechazado» de los pasos fijos puede haber ocurrido igual.

  Cada reintento con éxito puede invalidar el informe una vez y pedir uno nuevo, así que el término
  es uno por reintento posible:

  `PASOS_FIJOS_PEOR_CASO (8) + len(Frente) × MAX_REINTENTOS_POR_FRENTE (4) + len(Frente) ×
  MAX_REINTENTOS_POR_FRENTE (4, informes nuevos) + MAX_CIERRES_IMPEDIDOS (3) = 19 ≤ 30`.

  La fórmula sigue siendo calculada, y el test del #8 que la compara con `MAX_TURNOS_SEGURIDAD`
  cambia el valor esperado de 15 a 19, sin debilitarse. Las devoluciones siguen compartiendo el
  contador, como pide FR-011. FR-011 y el supuesto de la spec se actualizan con el 19.

  **Exclusiones del peor caso razonable** (hallazgo A1). La fórmula no cuenta tres situaciones que
  también invalidan el informe y piden uno nuevo:
  - un cambio de comercio, que el #8 ya excluía de su peor caso;
  - una coincidencia nueva tras volver a consultar listas;
  - un informe registrado en el mismo mensaje que una primera delegación, que T029 demuestra
    posible.

  Las tres dependen de que el coordinador haga algo que sus instrucciones no le piden. Quedan
  cubiertas por el **margen de 11 turnos** (30 − 19) y, en último término, por `max_turns`, que
  termina el caso como `error_max_turns`, nunca como completo.
- **Limitación conocida, que resuelve el #10**: el `Stop` no distingue una pregunta al analista de
  un cierre definitivo, así que exige el informe en cualquier fin de turno con comercio
  identificado o registro caído. Un test lo fija.

**Comercio pedido**: el `Delegador` guarda en `estado.comercio_pedido` el identificador y el
nombre de la última delegación de registro que pasó `construir_contexto`. Es lo que pidió el
analista a través del coordinador.

## R9. Fallo de hook: informe mínimo (FR-014) y orden escalamiento → informe (FR-012)

**Decisión**: el sello `fallo_de_hook` pasa a ser **una causa de escalamiento más**,
`CAUSA_FALLO_DE_HOOK`, en `causas_vigentes`. Con eso, FR-012 se aplica igual que con las otras
causas.

1. **Escalar primero**: con el caso sellado, `evaluar_informe` rechaza el informe hasta que un
   escalamiento cubra esa causa. Escalar nunca se deniega (#8, R6): el `PostToolUse` del
   escalamiento guarda la instantánea con `fallo_de_hook` incluida.
2. **Después, el informe mínimo**:
   - solo con `decide_cumplimiento`; cualquier otra recomendación se rechaza con «Tras un fallo de
     hook solo decide el oficial: la recomendación debe ser decide_cumplimiento.»;
   - el esquema y FR-004 se siguen validando;
   - la cobertura y los conflictos se sustituyen por los textos fijos (`COBERTURA_NO_CALCULADA`
     del #8 y el de R6), y el comercio, como en R5.
3. **Cierre**: con el sello, el `Stop` exige el escalamiento (por la causa) y el informe mínimo
   vigente. El caso nunca figura como completo, porque `completo` ya exige `fallo_de_hook is None`.

**Por qué el sello obliga a escalar**: `decide_cumplimiento` sin escalamiento deja la decisión a un
oficial que nunca recibe el caso. Hoy, un caso sellado sin otras causas puede terminar sin
escalamiento y sin informe; con este ticket tiene que llegar al oficial.

**Cálculo de conflictos que falla en modo normal**: `fallar_cerrado` deniega y sella. El siguiente
intento va por el camino del informe mínimo, con el texto fijo, así que la spec no necesita un
caso aparte.

**Doble fallo** (también falla el cálculo de FR-004 con el caso sellado): `fallar_cerrado`
deniega. El riesgo residual 6 del #8 solo se repite si fallan dos hooks (riesgo residual 6).

**Fallo del `PostToolUse` del informe** (hallazgo U2). Si `_informe_posterior` lanza una excepción,
`fallar_cerrado` sella el libro. El informe ya quedó guardado en la pasarela, pero su huella no se
confirma: la pendiente no pasa a `estado.informes`. Con el sello, el caso exige escalar y después el
informe mínimo, así que puede quedar un segundo informe guardado en `resultados/informes/`. Se
acepta: los dos documentos quedan, y la traza (`fallo_de_hook` seguido del `informe_registrado` del
informe mínimo) explica por qué. Lo fija un test de T032.

**Cambio respecto al #7**: un caso sellado sin coincidencias ni alto riesgo ya no puede cerrarse
sin escalar. Los tests del #7 que fijan el cierre con sello se adaptan sin debilitarse: lo que
hace cumplir el cierre ahora es más estricto.

## R10. Traza: eventos y zona horaria (FR-016 a FR-018)

**Decisión**:
- **`informe_registrado`**, nuevo, en el `PostToolUse` de `registrar_informe`: «Informe INF-xxxx
  registrado; recomendación: no_habilitar; cobertura incompleta, 3 de 4 frentes; 1 conflicto.»
  Si es el mínimo, lo dice. Un rechazo (deny del hook o error de la pasarela) no lo genera. Un
  error de la pasarela llega por `PostToolUseFailure` y deja `consulta_fallida`, como el
  escalamiento.
- **`accion` en `Evento`**: un campo opcional nuevo al final, como `regla` en el #7, con la acción
  intentada sin datos del comercio. Ejemplos: `registrar_informe (habilitar)`,
  `consultar_listas_restrictivas (persona)`, `delegar_frente (listas)`. Los bloqueos lo rellenan
  y la línea de comandos lo imprime.
- **Zona horaria, se unifica en UTC**: los eventos ya usan `datetime.now(UTC)`. La pasarela pasa
  de la hora local a UTC en `registrado_en`, y la fecha del hecho del registro también es UTC. La
  línea de comandos imprime la hora con «UTC».

**Alternativa descartada**: hora local en todo. Depende de la máquina y complica comparar trazas
de la demo.

**Aceptada por la analista**, con la etiqueta UTC explícita. En el #11, la interfaz mostrará la hora
de Colombia.

## R11. Interruptor `PASARELA_FALLA_REGISTRO` (indicación de la analista)

**Decisión**: copiar el patrón de `noticias.py:19-29` en `registro.py`. `VARIABLE_FALLA =
"PASARELA_FALLA_REGISTRO"` se lee en cada llamada; con valor `1` devuelve
`error(SERVICIO_NO_DISPONIBLE, "El registro mercantil no está disponible. Se puede reintentar;
mientras tanto, el comercio no queda identificado.", True)`. Se comprueba después de validar la
entrada, como en noticias.

Con el interruptor puesto, el reintento del #8 vuelve a fallar. El registro queda caído (R8), listas
se rechaza por falta de comercio (I.1), noticias y categoría siguen, y el informe se registra con el
comercio pedido sin verificar. Lo cubre Q5 con el modelo real y la demo puede mostrarlo.

## R12. Simulación, sondeo y línea de comandos

- **`PasarelaSimulada`**: valida `registrar_informe` con la misma `validar_informe` de la
  pasarela, para que los tests del caso no acepten lo que la real rechaza.
- **`CoordinadorSimulado`**: el paso `("informe", recomendacion)` arma un informe válido a partir
  de las consultas del caso (una afirmación por consulta válida, con su fuente y su fecha). Hay dos
  pasos nuevos:
  - `("informe_con", entrada)`, para probar rechazos;
  - `("mismo_mensaje", [pasos])`, que ejecuta varias llamadas con `asyncio.gather`, como el SDK
    ejecuta las de un mismo mensaje.

  Con este último, el test de R7 lanza en el mismo mensaje el reintento de un frente, que termina
  con éxito, y `registrar_informe`. Comprueba que la huella confirmada es la del `PreToolUse` y que
  el `Stop` exige un informe nuevo.
- **`sondeo_hooks.py`**: `ENTRADA_INFORME` pasa al formato nuevo, porque la pasarela real
  rechazaría el anterior.
- **Línea de comandos**: imprime los conflictos junto a la cobertura, los informes registrados
  (id, recomendación y si están vigentes), `accion` en los bloqueos y la hora con UTC.
- **Instrucciones del coordinador** (guía, no garantía):
  - una afirmación por dato, con la fuente y la fecha de los metadatos del resultado;
  - los conflictos los pone el sistema;
  - primero escalar y después registrar el informe;
  - con el registro caído, informe con el comercio pedido.

  La regla del informe también está en el modo de demostración, porque no es una regla I.1 a I.3.
  La excepción es «primero escalar y después registrar el informe»: es guía de escalamiento (I.2 e
  I.3), así que va aparte y el modo de demostración la quita junto con la guía de escalar
  (fase 13).

## R13. Riesgos residuales

Los que contradicen un FR, un escenario de la spec o un principio de la constitución están como
desviaciones justificadas (D1 a D7) en [plan.md](plan.md), con su motivo y su mitigación.

1. **Informe vigente con afirmaciones viejas**: una nueva delegación que no cambia la cobertura,
   los conflictos, las causas ni el comercio (noticias con otro nombre, otra categoría del mismo
   nivel de causa) deja vigente un informe cuyas afirmaciones de ese frente ya no son las últimas
   (R7, decisión de la analista).
2. **Registro caído y `decide_cumplimiento` sin escalar**: si no hay otras causas (por ejemplo, una
   categoría de riesgo bajo), el informe del registro caído puede registrarse con
   `decide_cumplimiento` sin que el caso se escale, y la decisión queda en manos de un oficial que
   no lo recibe. Es el mismo argumento de R9, pero la solución general («¿`decide_cumplimiento`
   exige escalar?») es del #10. *(Antes, este punto era el registro fallido con un reintento
   disponible; lo resolvió la analista en R8: el `Stop` también exige el informe en ese caso.)*
3. **La fecha de una afirmación no se contrasta** con la de su fuente; solo se valida que sea una
   fecha (R4).
4. **El texto de una afirmación no se verifica contra el contenido** de la fuente: I.4 garantiza la
   atribución, no la exactitud de la frase.
5. **`Stop` en cualquier fin de turno** con comercio identificado o registro caído (R8); lo resuelve
   el #10.
6. **Doble fallo de hooks** con el caso sellado: el informe mínimo puede no registrarse (R9).
7. **Motivo del deny en JSON** *(no medido)*: cómo lo presenta el SDK al modelo; lo comprueba Q3.
8. **Fuentes de un comercio anterior**: tras un cambio de comercio, las consultas válidas del
   anterior siguen contando para FR-004. Los nombres de las fuentes son genéricos por fuente, no
   por comercio, así que no permite citar una fuente que el caso no consultó.
