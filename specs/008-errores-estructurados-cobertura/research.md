# Research: Errores estructurados y cobertura parcial

**Ticket**: #8 | **Fecha**: 2026-10-17 | **Spec**: [spec.md](spec.md)

Lo marcado *(medido)* se comprobó con `claude-agent-sdk` 0.2.168, Haiku 5.5 y el servidor `pasarela`
del #5 por stdio, en un script temporal fuera del repositorio (`sondeo8.py`, en el scratchpad de la
sesión) con una carpeta de resultados temporal. No se leyó `.env`. Coste ≈ 0,01 USD. R9 lo convierte
en experimentos repetibles de `sondeo_hooks.py`.

Indicaciones de la analista para el plan:
- La pasarela solo acepta `cobertura` como texto o lista (`src/servidor_mcp/decisiones.py`).
- FR-011: medir si `updatedInput` reemplaza la cobertura; si no, `deny` con motivo.
- El reintento lo pide el modelo, con el código como guarda, y 1 reintento por frente.
- Verificar que los reintentos y las devoluciones del `Stop` caben en `max_turns`.

---

## R1. `updatedInput` en `PreToolUse` con una herramienta MCP por stdio *(medido)*

**Pregunta**: ¿puede el `PreToolUse` de `registrar_informe` reemplazar la cobertura que declara el
modelo por la calculada en código (FR-011)?

El tipo `PreToolUseHookSpecificOutput` del SDK 0.2.168 declara `updatedInput: dict`. Se midió con un
hook que devuelve `updatedInput` y un modelo al que se pide registrar un informe con
`cobertura: "completa"`; se leyó lo que guardó la pasarela en la carpeta temporal.

| Experimento | Salida del hook | Lo que guardó la pasarela | `tool_input` en `PostToolUse` |
|-------------|-----------------|---------------------------|-------------------------------|
| e1 | `permissionDecision: allow` + entrada **completa** con la cobertura del código | 1 informe, con la cobertura del código | la del código |
| e2 | sin `permissionDecision` + entrada completa | 1 informe, con la cobertura del código | la del código |
| e3 | `permissionDecision: allow` + **solo** `{cobertura}` | ningún informe: la pasarela recibió solo `cobertura` y no lo guardó (faltan los demás campos obligatorios; el tipo exacto del error no se registró en el sondeo y R9 lo medirá) | solo `cobertura` |

**Hallazgos**:
- `updatedInput` **sí** cambia lo que recibe la herramienta MCP por stdio, con o sin `allow`.
- **Sustituye la entrada entera; no se fusiona** (e3). El hook debe devolver la entrada del modelo
  completa con la `cobertura` reemplazada.
- `PostToolUse` ve la entrada ya reemplazada.

**Decisión**: el mismo `PreToolUse` que ya evalúa las reglas del informe (`_informe_previo`, #7)
devuelve, si las reglas no rechazan, `permissionDecision: "allow"` y `updatedInput` con la entrada
completa y `cobertura` sustituida por la del código (R5). `escalar_a_cumplimiento` recibe un
`PreToolUse` nuevo que hace lo mismo. Se usa `allow` porque es la combinación documentada y la
herramienta ya está pre-aprobada en `allowed_tools`, así que no amplía ningún permiso.

Un solo hook por herramienta decide `deny` o reemplazo: no se combinan dos `PreToolUse` sobre la
misma herramienta, porque no se midió cómo el SDK mezcla un `deny` y un `updatedInput` de hooks
distintos.

**Alternativas descartadas**:
- `deny` con motivo para que el modelo reescriba la cobertura: gasta un turno, y que la copie bien
  depende del modelo. Era el plan B de la analista, y no hace falta porque `updatedInput` funciona.
- Comprobar en `PostToolUse` y marcar el caso: no puede deshacer un informe ya guardado.

---

## R2. Turnos: reintentos y devoluciones del `Stop` frente a `max_turns` *(medido)*

**Medido (e4)**: un `delegar_frente` en proceso que falla con error reintentable la primera vez, un
modelo al que se pide reintentar una vez y un `Stop` que bloquea dos veces → 2 llamadas, 3
invocaciones del `Stop`, `subtype=success` y `num_turns=5`. **Cada respuesta del modelo que termina
en una herramienta, y cada devolución del `Stop`, gasta un turno**, como midió el #7 (R3:
`max_turns=4` con 4 invocaciones del `Stop` dio `error_max_turns` y `num_turns=5`). Los turnos de un
subagente son de su propio `query()` y no cuentan para el coordinador.

**Presupuesto del peor caso razonable del coordinador** (cada fila en un turno propio, sin
aprovechar el paralelismo):

| Paso | Turnos |
|------|--------|
| Registro, noticias y categoría juntos | 1 |
| Listas | 1 |
| Un reintento por frente (`MAX_REINTENTOS_POR_FRENTE = 1`), uno por turno | 4 |
| Categoría con otra entrada tras `categoria_desconocida` | 1 |
| Listas rechazada una vez por la carrera de R6 del #7 | 1 |
| `escalar_a_cumplimiento` | 1 |
| Un informe rechazado por una regla y el informe aceptado | 2 |
| Devoluciones del `Stop` (`MAX_CIERRES_IMPEDIDOS = 3`) | 3 |
| Respuesta final | 1 |
| **Total** | **15** |

**Decisión**: `MAX_TURNOS_SEGURIDAD = 30` se mantiene. Deja 15 turnos de margen para rechazos de
hooks no previstos, y un reintento denegado cuesta un turno, pero la respuesta denegada dice
`reintentable: false` (R3) para que el modelo no insista.
- `PRESUPUESTO_TURNOS_PEOR_CASO` **se calcula** en `configuracion.py`, no es el literal 15
  (indicación de la analista):
  `PASOS_FIJOS_PEOR_CASO + len(Frente) * MAX_REINTENTOS_POR_FRENTE + MAX_CIERRES_IMPEDIDOS`.
  `PASOS_FIJOS_PEOR_CASO = 8` son las filas de la tabla que no dependen de esas constantes: tres
  frentes juntos, listas, categoría con otra entrada, listas rechazada por la carrera, escalar,
  informe rechazado, informe aceptado y respuesta final. Con los valores actuales da 8 + 4 + 3 = 15.
  Un test exige `PRESUPUESTO_TURNOS_PEOR_CASO <= MAX_TURNOS_SEGURIDAD`. Si alguien sube los
  reintentos o las devoluciones del `Stop`, el presupuesto sube con ellos y el test protege.
- `Caso` guarda `num_turns` del `ResultMessage` del coordinador (`caso.turnos`) y la línea de
  comandos lo muestra, para observarlo en Q6 con el modelo real.
- Si se agotan los turnos, el caso termina `error_max_turns` y no figura como completo (#6).

---

## R3. Política de reintento: la pide el modelo y la guarda el código

**Decisión** (indicación de la analista): el coordinador decide si reintenta volviendo a llamar a
`delegar_frente` con la misma entrada; el `Delegador` (código) decide si se ejecuta.

- **Clave del historial**: `(frente, contexto)`. El contexto lo construye el código desde la
  entrada (`construir_contexto`, #6), así que «la misma entrada» es exactamente el mismo contexto.
  Otra entrada es otra clave: una delegación nueva que no consume el reintento (US3-6).
- **Regla**: con la misma clave, si el último resultado fue
  - `terminado` → se devuelve lo guardado y se registra el evento `delegacion_repetida`, como en el #6 (US3-5);
  - un error con `causa` reintentable (R4) y quedan reintentos (`MAX_REINTENTOS_POR_FRENTE = 1`) →
    se vuelve a ejecutar, con el evento `frente_reintento` («reintento 1 de 1 del frente noticias; el
    intento anterior falló: servicio_no_disponible»);
  - en otro caso → no se ejecuta; se devuelve el mismo error con `reintentable: false`,
    `reintentos_restantes: 0` y el evento `reintento_denegado`, con el motivo «no reintentable» o
    «se agotaron los reintentos».
- **`reintentable` en la respuesta** significa «la política permite otro intento»: la fuente lo
  declaró reintentable **y** quedan reintentos. Así el modelo no gasta turnos pidiendo lo que se
  le va a denegar (R2).
- **Pedidos simultáneos** (caso límite de la spec): una llamada que esperó a que el mismo frente
  terminara (`_esperar_si_en_curso`, #6) devuelve el resultado de esa ejecución sin reintentar,
  aunque fuera un error reintentable.
- **Rechazos sin ejecución** (por ejemplo, listas antes del registro) no cuentan como intento y
  conservan su `reintentable` actual (FR-003).
- **Registro que cambia de comercio**: invalida listas y borra su contexto (#6); el historial de
  listas con el contexto anterior deja de aplicar porque el contexto nuevo es otra clave.

**Constitución III**: el ciclo sigue terminando por `stop_reason`. `MAX_REINTENTOS_POR_FRENTE` solo
limita cuántas veces se vuelve a ejecutar un frente, igual que `MAX_CIERRES_IMPEDIDOS` limita las
devoluciones del `Stop`; es protección documentada en `configuracion.py`, no control del ciclo.

**Alternativas descartadas**:
- Reintento automático dentro de `delegar_frente`: la analista prefiere que lo pida el modelo, y la
  constitución III dice que el coordinador decide.
- Un `PreToolUse` sobre `delegar_frente` que deniegue el reintento: duplicaría en el hook el
  historial que ya tiene el `Delegador`, y el `Delegador` ya es código, no instrucción.
- Contar los reintentos solo por frente, sin la entrada: impediría la delegación nueva con una
  categoría corregida que el #6 permite.

---

## R4. Error estructurado de un frente

Hoy (#6) un frente que no termina devuelve `{error, tipo: "frente_no_terminado", mensaje,
reintentable, obtenido: {frente, resultados, errores, terminacion}}`, y un rechazo devuelve
`tipo: "frente_rechazado"`. Los tests del #6 y del #7 leen `tipo` y `reintentable`.

**Decisión**: se conserva `tipo` y se añaden, en el primer nivel, `frente`, `causa`, `intento` y
`reintentos_restantes`. `causa` es un conjunto cerrado; su prioridad sigue el orden de
`Delegador._evaluar`:

| `causa` | Cuándo | Reintentable |
|---------|--------|--------------|
| `terminacion_anomala` | el subagente no terminó con normalidad (límite, razón de parada inesperada, excepción, sin `ResultMessage`) | no |
| `error_de_fuente` | la herramienta devolvió un error estructurado (se excluyen los bloqueos de hook, #7) | sí, solo si **todos** los errores reales traen `reintentable: true` |
| `sin_consultas` | el subagente no hizo ninguna consulta efectiva | no |
| `resultado_invalido` | un resultado no tiene la forma del contrato de la pasarela | no |
| `consulta_incompleta` | listas sin el comercio o sin el representante | no |
| `cancelado` | el frente se canceló a mitad (solo consta en el estado y la cobertura; el modelo no recibe respuesta) | no |
| `rechazado` | rechazo sin ejecución (`frente_rechazado`) | no, salvo listas antes del registro o con el registro rechazado, que sigue siendo sí (FR-003; los dos tests de `test_delegacion.py`) |
| `invalidado` | listas, porque el comercio del registro cambió (solo en el estado y la cobertura) | no aplica: volver a delegar listas es una ejecución nueva (#6) |

- `obtenido` no cambia: los resultados válidos con contenido y metadatos separados, los errores y
  la terminación.
- Un `reintentable` ausente o que no es `True` cuenta como no reintentable, como ya hace
  `_respuesta` con `is True`.
- **Texto de una excepción** (US2-7): `Delegador._ejecutar` deja de incluir `{error}` en
  `detalle_terminacion`, que queda solo en `excepción <Tipo>`. De ahí salían el motivo del frente,
  el campo `terminacion` del error, el evento `frente_fin` y la salida de la línea de comandos. Es
  el mismo criterio que `_registrar_fallo` de los hooks del #7.

**Alternativa descartada**: renombrar `tipo` a la causa. Rompería los contratos del #6 y el #7 y
sus tests sin aportar nada que `causa` no dé.

---

## R5. Cobertura calculada en código

**Decisión**: un módulo puro nuevo, `cobertura.py`, con `calcular_cobertura(estado) ->
CoberturaCaso`.
- **Cobertura de cada frente**: se deriva de la situación (#6), del motivo y de la `causa` del
  último error del frente, que el `Delegador` guarda en `EstadoCaso.errores[frente]`.
  - `terminado` → cubierto;
  - `sin_iniciar` → «no se delegó»;
  - `en_curso` → «seguía en curso»;
  - `rechazado`, `no_terminado` o invalidado → su motivo y su causa.
- **Cobertura completa**: solo con los cuatro frentes cubiertos.
- **`Caso.completo`** (#7) deja de comprobar la situación de los frentes por su cuenta y usa
  `calcular_cobertura(...).completa`. Así hay un solo criterio, y las demás condiciones del #7 no
  cambian.

**Formato registrado**: la pasarela acepta `cobertura` como texto o lista. Se registra una lista de
textos en español, en orden fijo (registro, listas, noticias, categoría), con una primera línea de
resumen:

```text
["Cobertura incompleta: 3 de 4 frentes cubiertos.",
 "registro: cubierto.",
 "listas: cubierto.",
 "noticias: no cubierto; error de la fuente (servicio_no_disponible); 2 intentos.",
 "categoria: cubierto."]
```

- El mismo texto lo muestra la línea de comandos (FR-014).
- Los motivos no repiten nombres ni identificadores del comercio (criterio del #7, FR-016).
- Cada línea es una afirmación del sistema sobre su propia ejecución. Que el informe le asigne una
  fuente en su esquema es del #9.

---

## R6. Hooks de los canales de decisión

- **`_informe_previo`** (#7): libro sellado → `deny`; reglas que rechazan → `deny` (sin cambios).
  Si no, `tool_input` que no es un objeto → `deny` con `MOTIVO_ENTRADA_MALFORMADA`; si lo es,
  `allow` + `updatedInput` con la entrada completa y la cobertura del código (R1), y el evento
  `cobertura_sustituida`.
- **`_escalar_previo`** (nuevo, `PreToolUse` de `escalar_a_cumplimiento` en el coordinador): misma
  sustitución y mismo evento. **No** mira el sello del libro y **nunca deniega**: escalar es la
  acción segura y no debe impedirse (indicación de la analista).
- **Evento `cobertura_sustituida`** (indicación de la analista: no `cobertura_registrada`). Se emite
  en el `PreToolUse`, **antes** de que la pasarela acepte la llamada. Por eso dice qué cobertura se
  puso en la llamada, no que quedó registrada: la cobertura resumida (completa, o qué frentes faltan)
  y si la que declaró el coordinador era distinta. Si la pasarela rechaza la llamada, lo dirá su
  error (`PostToolUseFailure`) y el evento sigue siendo cierto. Es visible en el chat (principio VI).
- **Ante un fallo, cada hook va por un camino distinto**:
  - **Informe: falla cerrado.** `_informe_previo` sigue envuelto con `fallar_cerrado` (#7): una
    excepción calculando la cobertura deniega la llamada; nunca deja pasar la cobertura del modelo.
  - **Escalamiento: degrada sin denegar.** `_escalar_previo` no usa `fallar_cerrado`, sino un
    envoltorio propio, `degradar_escalamiento`. Ante una excepción calculando la cobertura:
    1. sella `libro.fallo_de_hook` y registra el evento `fallo_de_hook` (#7), sin el texto de la
       excepción;
    2. deja pasar el escalamiento con `updatedInput` = la entrada completa y
       `cobertura = [COBERTURA_NO_CALCULADA]`, el texto fijo del código «No se pudo calcular la
       cobertura; debe tratarse como incompleta.»;
    3. si `tool_input` no es un objeto (no hay entrada que completar), deja pasar la llamada sin
       cambios: la pasarela la rechazará por su cuenta. Escalar nunca se deniega desde este hook.
  - **Consecuencia del sello**, la misma del #7: `Caso.completo` es falso y los `PreToolUse` de las
    reglas, incluido el del informe, deniegan mientras el sello exista. Es coherente, porque el
    informe necesitaría la misma cobertura que no se pudo calcular. El caso queda escalado con la
    cobertura declarada incompleta, y el oficial lo ve.

---

## R7. Instrucciones del coordinador y descripción de `delegar_frente`

- **`DESCRIPCION` de `delegar_frente`**: con la misma entrada, un frente terminado devuelve lo
  guardado; un error con `reintentable: true` se puede pedir una vez más; con `false` no se vuelve
  a ejecutar.
- **Regla nueva del coordinador** (`_REGLA_FALLOS`): si un frente devuelve un error con
  `reintentable: true`, puede volver a delegarlo una vez con la misma entrada; si es `false`, no lo
  repite, sigue con los demás frentes y registra el informe. La cobertura del informe la calcula el
  sistema. Está también en el modo de demostración, porque no es una de las reglas I.1 a I.3 que ese
  modo quita (#7, R11).
- `_REGLA_RESUMEN` ya pide decir al analista qué frentes no se pudieron cubrir y por qué; no cambia.

---

## R8. Simulación para los tests

- **`SesionSimulada`** aplica `updatedInput` como el SDK (R1): si un `PreToolUse` lo devuelve sin
  `deny`, la herramienta recibe esa entrada **entera**, y `PostToolUse` la ve.
- **`EjecutorSimulado`**: un ayudante `en_secuencia(*resultados)` devuelve un resultado distinto en
  cada ejecución de un frente (por ejemplo, error reintentable y después éxito).
- **`CoordinadorSimulado`**: ya declara `cobertura: "completa"` en su informe y su escalamiento
  simulado no la trae. Sirve para probar que la registrada es la del código. Se añade el paso
  `("escalar_con", entrada)`, para probar el escalamiento con una entrada completa.
- **El caso (f) de extremo a extremo** (`test_casos_cobertura.py`):
  - noticias responde siempre `error_estructurado("servicio_no_disponible", True)`, como la
    pasarela con `PASARELA_FALLA_NOTICIAS=1`;
  - el guion delega los tres frentes, reintenta noticias, delega listas, registra el informe y
    termina;
  - comprueba el informe guardado por la pasarela simulada, los eventos y `caso.completo is False`.

---

## R9. Sondeo repetible

`sondeo_hooks.py` gana tres experimentos con Haiku (≈ 0,01 USD más):
- **(e)**: e1 y e3 de R1, el reemplazo completo y la entrada parcial que no se fusiona.
- **(f)**: e4 de R2, los turnos del reintento y del `Stop`.
- **G3**: el `PreToolUse` real de `HooksDelCaso` sobre `registrar_informe`. Un modelo registra un
  informe con `cobertura: "completa"` en un caso con noticias sin cubrir, y la pasarela guarda la
  cobertura del código.

Si el SDK cambia (la versión está acotada a `<0.3`), el sondeo lo marca como `difiere` y vuelve a
aplicar el plan B de la analista (`deny` con motivo).

---

## R10. Riesgos residuales

1. **La respuesta final del coordinador al analista es texto del modelo** y podría contradecir la
   cobertura. Lo autoritativo es lo registrado (informe y escalamiento), los eventos y la línea de
   comandos, todos calculados en código. Mostrarlo en el chat es del #11.
2. **Alternar entradas** (A, B, A) da a cada entrada su propio reintento. Cada delegación nueva es
   legítima desde el #6 y cuesta un turno; lo acota `max_turns`.
3. **`updatedInput` depende del SDK 0.2.168** (R1). El sondeo repetible lo vigila.
4. **Con `PASARELA_FALLA_NOTICIAS=1` el reintento vuelve a fallar siempre**, porque la variable se
   lee en cada llamada. Es lo esperado: prueba el límite y la entrega con cobertura incompleta.
5. **Recomendación con cobertura incompleta**: no se restringe más allá del #7 (decisión confirmada
   por la analista).
6. **Escalamiento con la cobertura no calculada** (R6): si falla el cálculo, el escalamiento sale
   con el texto fijo «No se pudo calcular la cobertura; debe tratarse como incompleta.», el caso
   queda sellado y el informe ya no se puede registrar. Se prefiere escalar a bloquear el canal
   seguro. **Lo resolverá el #9**, dueño de «todo caso terminado queda registrado»: este ticket no
   cambia el diseño (C1 del análisis, decisión de la analista).
7. **`_REGLA_FALLOS` dice «no lo repitas» ante `reintentable: false`** (`coordinador.py`). El
   rechazo de listas porque el registro devolvió varias coincidencias trae `reintentable: false`.
   Si después el analista da el identificador y el registro identifica un comercio único, el código
   sí ejecutaría listas, pero el prompt puede llevar al modelo a no volver a pedirla, y listas
   quedaría sin cubrir en el caso (d). **Lo resolverá el #10**, dueño de la ambigüedad del
   registro (revisión independiente del #8, decisión de la analista).
