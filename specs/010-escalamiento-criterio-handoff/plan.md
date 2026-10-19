# Implementation Plan: Escalamiento con criterio, handoff y ambigüedad

**Branch**: `010-escalamiento-criterio-handoff` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-escalamiento-criterio-handoff/spec.md` (aprobada en `d49aed0`)

## Summary

**El escalamiento pasa a decidirse y completarse en el hook**, como el informe del #9. El `PreToolUse` de `escalar_a_cumplimiento`:
- **Deniega** por cuatro motivos:
  - un caso de bajo riesgo sin hallazgos comprobado (FR-002, con los cuatro frentes cubiertos, sin menciones y sin conflictos);
  - la espera del identificador o del nombre;
  - un resumen con problemas de forma o de fuente;
  - un caso sin comercio (D2).
- **Valida el resumen al oficial** con el esquema de afirmaciones del #9 (`validar_resumen`, compartido con la pasarela), y comprueba la fuente consultada y la afirmación por frente cubierto.
- **Sustituye** comercio, cobertura, causa y conflictos por los del código.
- **Nunca deniega ante una excepción** ni con el caso sellado.

El escalamiento se confirma en el `PostToolUse` con la clave del comercio, así que solo cuenta para el comercio actual. Por eso `decide_cumplimiento` exige un escalamiento previo (FR-004).

**El caso puede continuar**: `Caso.continuar(mensaje)` lanza otra `query()` con `resume=<session_id>`. Está medido: conserva el contexto, ejecuta los hooks y cuenta `num_turns` por turno. El `Stop` reconoce tres esperas del analista que el código comprueba en el estado:
- varias coincidencias en el registro;
- ninguna coincidencia;
- la categoría bloqueada por I.3 y sin ningún resultado.

En una espera, el `Stop` deja terminar el turno sin escalar ni informar y sin gastar devoluciones. En el turno siguiente el cierre vuelve a exigir lo de siempre.

La categoría delegada tiene que aparecer en un mensaje del analista (FR-020). Tras identificar al comercio, noticias consultado con otro nombre deja de contar como cubierto, y sus fuentes dejan de valer para las afirmaciones (FR-027). Las instrucciones aclaran que el rechazo de listas por falta de identificación deja de valer (FR-028).

El presupuesto de turnos pasa a 21 de 30 por turno.

## Technical Context

**Language/Version**: Python 3.12 gestionado con uv.

**Primary Dependencies**: `claude-agent-sdk>=0.2.168,<0.3` y `mcp>=2.3,<3`, ya declaradas. **No se añade ninguna dependencia.** La continuación usa `ClaudeAgentOptions.resume`, que ya existe en el SDK (R1, medido).

**Storage**: los escalamientos, en `resultados/escalamientos/` (pasarela del #5), ahora con afirmaciones, causa del código y conflictos. Los mensajes del analista, la espera, los escalamientos con su comercio y `categoria_bloqueada` viven en memoria, en el `EstadoCaso`. La sesión del coordinador la persiste el SDK; el caso solo guarda su `session_id`.

**Testing**:
- pytest junto al código, determinista y sin llamar al modelo (FR-023);
- `CoordinadorSimulado` con un guion por turno y `resume`;
- `PasarelaSimulada` valida el resumen con la misma función que la pasarela real y devuelve N-0001 para `CO-AM-0005`;
- casos (a), (b) y (d), este en dos turnos, de extremo a extremo;
- recorrido de las esperas: 6 estados del registro por 3 de la categoría (SC-004).

**Target Platform**: Windows, macOS y Linux; validado a mano en Windows.

**Project Type**: biblioteca y proceso Python (`due_diligence` y `servidor_mcp`). La interfaz de chat es del #11.

**Performance Goals**: las funciones nuevas son puras e instantáneas. Cada mensaje del analista es una `query()` reanudada; su coste se mide en Q5.

**Constraints**:
- `updatedInput` con la entrada completa (#8, R1).
- Ningún evento, motivo, causa ni cobertura repite datos del comercio.
- El presupuesto es por turno: 21 de 30 (R10).
- Cambia de forma deliberada el contrato de `escalar_a_cumplimiento` (spec, supuestos); los demás se mantienen.
- Sin estado de módulo, sin credenciales y solo datos ficticios.

**Scale/Scope**:
- cambian 12 módulos de `src/due_diligence/` y 3 de `src/servidor_mcp/`;
- no se añaden módulos de producción;
- se añade un archivo de tests (`test_casos_escalamiento.py`);
- hay 2 eventos nuevos;
- el coordinador sigue con 8 hooks registrados: el `PostToolUseFailure` del escalamiento pasa a descartar el escalamiento pendiente (R8).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitución v1.0.1. Resultado: **cumple, con las desviaciones justificadas D1 a D4** de la sección siguiente.

| Principio | Estado | Cómo |
|-----------|--------|------|
| **I.1** Listas tras la identificación | Cumple, sin cambios en la regla | Los hooks del #7 se conservan. En la espera del identificador, listas sigue bloqueado. Con el identificador, la nueva consulta del registro identifica al comercio (FR-017) y solo entonces se permite listas. Caso (e) dentro del (d). |
| **I.2** Coincidencia en listas | Cumple, con D1 | `causas_vigentes` no cambia. Un escalamiento solo cubre las causas del comercio actual (R8). Caso (c) del #7. |
| **I.3** Alto riesgo | **Cumple, más estricto** | La categoría delegada tiene que estar en los mensajes del analista (R9): cierra el pendiente 1 del #7. Caso (a). |
| **I.4** Fuente en cada afirmación | Cumple, se amplía | El resumen al oficial usa el esquema y la fuente consultada del #9 (R5, R6). Las fuentes de noticias y listas de otro comercio dejan de valer (R7). D1 y D7 del #9 aplican también al resumen (spec). |
| **I.5** Cobertura declarada | Cumple, se amplía | La cobertura del resumen es la del código. Noticias de otro comercio figura como no cubierto (R7). |
| **II** Garantizado vs. sugerido | Cumple | Se hacen cumplir en código: el escalamiento con criterio, el resumen, las esperas, la categoría, `decide_cumplimiento` con escalamiento y la cobertura de FR-027. El prompt solo guía tres cosas: cuándo pedir el identificador, volver a delegar listas y noticias (FR-028) y cómo redactar la acción recomendada (R11). |
| **III** Arquitectura de agentes | Cumple | Cada turno es una `query()` que termina por su `stop_reason`; no hay iteraciones fijas ni búsqueda de palabras. La espera la decide el estado, no el texto. Los subagentes no cambian. |
| **IV** Herramientas y MCP | Cumple | Cambia el contrato de `escalar_a_cumplimiento`, con una descripción que dice qué pone el sistema y qué no hace. Los rechazos son errores estructurados: el JSON `resumen_rechazado` del hook y `campos_obligatorios_ausentes` o `entrada_invalida` de la pasarela. |
| **V** Escalamiento con criterio | **Cumple, garantizado en código**, con D1, D2 y D3 | Se escala si, y solo si, hay causa (FR-001). Escalar un bajo riesgo sin hallazgos comprobado se deniega (FR-002). Se pide el identificador en vez de elegir (esperas, R3). El resumen es autosuficiente y está validado (R6). Casos (a), (b) y (d). |
| **VI** Transparencia | Cumple | `mensaje_analista`, `espera_analista`, `escalamiento_registrado` con causas y afirmaciones, y la acción en los bloqueos. La línea de comandos muestra la espera y los escalamientos. |
| **VII** Datos ficticios | Cumple | Datos del #5: `CO-TV-0001`, `CO-TA-0002`, `CO-AM-0004`, `CO-AM-0005` y N-0001; sin datos nuevos. |
| **VIII** Sin credenciales | Cumple | Los tests y el sondeo de R1 no leen `.env`. |
| **IX** Spec first | Cumple | Spec (`d49aed0`), plan y tareas antes del código; comentarios de avance en el issue. |
| **X** Calidad y pruebas | Cumple | pytest junto al código, ruff, casos (a), (b) y (d) obligatorios, revisión independiente y auditoría en `/abrir-pr`. |

**Verificación explícita de cumplimiento (flujo de desarrollo 2)**:
- La auditoría de `/abrir-pr` debe ver **I.1, I.2, I.3 e I.4 aplicables**, porque el diff toca `hooks.py`, `reglas.py`, el `Stop` y el esquema. Su evidencia son `test_casos_escalamiento.py` y los tests del #7 al #9 que siguen en verde.
- Los tests que cambian van en una tabla del PR, adaptados con igualdades exactas:
  - la forma de `escalar_a_cumplimiento`;
  - `escalamientos` con comercio;
  - `decide_cumplimiento` sin escalar;
  - el presupuesto de 19 a 21;
  - la limitación del `Stop` del #9.
- **I.5 aplica**: la cobertura cambia por FR-027.

**Re-evaluación tras el diseño (Fase 1)**: se mantiene. Los riesgos residuales están en R13 de [research.md](research.md). Los que contradicen un requisito de la spec o un principio son D1 a D4; el resto se explica bajo la tabla.

## Desviaciones justificadas

| # | Desviación | Contradice | Motivo | Mitigación y dónde se resuelve |
|---|------------|------------|--------|--------------------------------|
| D1 | **Las coincidencias de un comercio anterior siguen siendo causas** si el analista cambia de comercio en un turno posterior: el libro no las borra (comportamiento desde el #7, R13.2). Además, el resumen del comercio nuevo muestra la causa «coincidencia del comercio» **sin una afirmación que la respalde**: R7 no deja citar la consulta del otro comercio. | FR-001 («si, y solo si, tiene una causa vigente»), V (escalar de más satura al oficial) y el resumen autosuficiente de V. | Borrar o filtrar coincidencias del libro toca la garantía de I.2 de los tickets #7 al #9. Un error ahí habilita de menos riesgo, que es peor que escalar de más. El caso del cambio de comercio no está entre los obligatorios. | Escala de más, nunca habilita de más. El escalamiento anterior no cubre al comercio nuevo (R8), así que el oficial recibe el caso con la causa nombrada. Aceptada por la analista; queda para un ticket posterior si lo pide. |
| D2 | **Sin comercio identificado ni pedido, el escalamiento se rechaza** (R5, paso 4). Ocurre, por ejemplo, con el alto riesgo detectado antes de delegar el registro. | FR-003 (en un caso sin comercio comprobado, escalar se admite) y FR-001 (el alto riesgo exige escalar). | El oficial no puede recibir un caso sin comercio: el resumen no sería autosuficiente (V). Basta con delegar primero el registro, que deja el comercio pedido. | El motivo del rechazo pide delegar el registro (`MOTIVO_SIN_COMERCIO_ESCALAMIENTO`). Con el sello no se rechaza: va `COMERCIO_NO_IDENTIFICADO` (R5, paso 1) para que FR-012 se cumpla. |
| D3 | **Con alto riesgo y el caso esperando el identificador o el nombre** (varias coincidencias o ninguna), **el escalamiento se rechaza** hasta identificar al comercio (FR-016, R5 paso 2). | Principio V («Se escala por… categoría de alto riesgo») y FR-001. | Escalar un comercio sin identificar llevaría al oficial un caso que no sabe a qué comercio corresponde. V también pide pedir el identificador en vez de elegir. | No se habilita y no figura como completo. La espera tiene salida: el analista da el identificador o corrige el nombre, y el escalamiento se exige en el turno siguiente. Con el sello se escala igual (excepción de FR-016). D3 cubre solo el alto riesgo: una coincidencia en listas de un comercio anterior (D1) se escala sin esperar, y el cierre la exige (excepción por I.2 de FR-016, corrección de la revisión previa). |
| D4 | **Con el caso sellado, el resumen al oficial no comprueba que las fuentes citadas se consultaran** (`resumen_sellado`, R5 paso 1). | FR-008 (el resumen se valida como el informe, con la fuente consultada) e I.4. | Tras un fallo de hook el libro puede haber perdido datos, así que comprobar las fuentes contra él podría rechazar un escalamiento legítimo; escalar es la salida segura (FR-012). | La cobertura y los conflictos van como «no calculados», la causa nombra el fallo de hook, la pasarela sigue exigiendo fuente y fecha en cada afirmación y el caso no figura como completo. |

**Riesgos de R13 que no son desviaciones**:
- **1, plurales y varias categorías en FR-020**: los declara la spec (US5-5, Supuestos).
- **3, `resume` depende de la sesión persistida por el SDK**: si se pierde, `continuar` falla con un error claro. La spec no exige sobrevivir a eso.
- **4, D1 y D7 del #9 en el resumen**: la spec los declara.
- **5, informe vigente con afirmaciones viejas**: decisión aceptada en el #9.
- **6, el texto que pide el identificador lo redacta el modelo**: lo garantizado son las acciones (sin listas, sin escalamiento y sin informe). La spec no exige el texto.
- **7, la acción recomendada no se contrasta**: es texto del coordinador para el oficial (FR-011).
- **El sello durante la espera del registro** (`reglas.espera_exime_de_escalar`, `reglas.py:366-377`): exime de escalar en ese turno, como el alto riesgo (D3). Si el sello vino de un `PostToolUse` de listas que falló, una coincidencia pudo quedar sin registrar; se exige en el turno siguiente, y `habilitar` sigue imposible mientras tanto. Es coherente con FR-014 y FR-016 (sugerencia de la auditoría, cuarta ronda).

**Decisiones de la implementación que no son desviaciones** (anotadas en las notas de las fases 6 a 8 de [tasks.md](tasks.md)). Ninguna contradice un FR, un escenario de la spec ni un principio:
- **El quinto motivo sin causa** («el comercio no está identificado de forma unívoca»). Precisa FR-009, que pide decir por qué se lleva al oficial un caso sin causas; sin él, ese caso daba una causa vacía, que la propia forma rechaza. Los cuatro motivos de R5 se conservan.
- **La confirmación sin pendiente**: el `PostToolUse` registra el escalamiento con las causas de ese momento si su `PreToolUse` falló y lo dejó pasar. Es lo que exigen FR-012 (escalar nunca se deniega por un fallo) y R8 (el escalamiento que el oficial recibió cuenta); sin pendiente, no hay otras causas que usar.
- **El escalamiento con el sello lleva la cobertura y los conflictos «no calculados»**. Es R5 paso 1 y FR-012 aplicados tal cual, como el informe mínimo del #9 (D4 del #9): tras un fallo de hook cualquier cálculo puede estar mal. El test del #8 que esperaba la cobertura calculada con el sello cambió a sabiendas (tabla de T046).
- **La simulación adelantada de T044 a la fase 6** (`resumen_del_caso`, el paso `escalar` válido y la `PasarelaSimulada` que valida el resumen). Es un cambio de orden de las tareas, no de lo especificado: sin él la fase 6 no cerraba en verde.

**Correcciones de la revisión previa de `/abrir-pr`** (commit `2cda1c4`, fase 11 de [tasks.md](tasks.md)):
- **I.2 en la espera del registro** (bloqueante de la auditoría): con D1, una coincidencia de un comercio anterior seguía siendo causa mientras el caso esperaba el identificador, pero el `Stop` admitía la espera y `evaluar_escalamiento` rechazaba escalar, así que quedaba sin escalar y sin marca. Ahora `espera_exime_de_escalar` decide en los dos sitios: las esperas del registro eximen del alto riesgo (D3), no de una coincidencia.
- **Un `asyncio.Event` por ejecución de cada frente** (bloqueante de la revisión de código): cada turno corre en su propio `asyncio.run` (R1), y en Python 3.12 un `Event` queda atado al bucle del primero que lo espera. Reutilizarlo hacía fallar con `RuntimeError` a `listas` si esperaba al registro en curso en dos turnos.
- **El test de US2-7 / FR-007** (bloqueante de la revisión de código): un resumen rechazado, la corrección, el escalamiento aceptado y el cierre permitido, encadenados en el mismo caso.

**Segunda ronda** (commit `8658d6c`, fase 12 de [tasks.md](tasks.md)):
- **El test de FR-010 / US2-5** (bloqueante de la revisión de código): el resumen guardado del caso (g) lleva las dos fechas de constitución con su fuente.
- **Corrección de criterio de la analista**: con el registro caído no hay espera de la categoría y el cierre exige el informe (I.5).
- **D4** declarada; `resumen_sellado` solo con las claves del esquema; descripciones de `escalar_a_cumplimiento` con todos los casos; guía de datos «que dio el analista en sus mensajes»; `CasoSinSesion` como mensaje en la línea de comandos; limpieza de comentarios, código muerto y contrato; riesgo residual 10 de R13.

**Tercera ronda** (commit `ecee137`, que corrige la revisión de `759405b`; fase 13 de [tasks.md](tasks.md)):
- **I.5 con cualquier frente caído** (bloqueante de esa ronda): la espera de la categoría deja de existir si la fuente de **cualquier** frente no respondió (`cobertura.frente_caido`; `registro_caido` pasa a ser su caso del registro). El `Stop` exige el informe y, agotadas las devoluciones, marca `cierre_sin_informe`. Las esperas del identificador y del nombre no cambian con una fuente caída.
- **El rechazo del informe en la espera del registro** ya no pide escalar si la espera exime de escalar (`hooks._sin_pedir_escalar`); con una coincidencia en listas lo sigue pidiendo.
- **Un fallo del `PreToolUse` de `delegar_frente`** se atribuye al frente pedido (`hooks.frente_delegado`), y a listas solo si no se puede leer.
- La descripción de `escalar_a_cumplimiento` dice qué se acepta durante esas esperas.

**Cuarta ronda** (este commit, que corrige la revisión de `ecee137`; fase 14 de [tasks.md](tasks.md)):
- **FR-014 y SC-004 cambian por decisión de la analista** (bloqueante de la revisión de código sobre `ecee137`): la tercera ronda llevó el código más allá de la spec, que solo descartaba la espera de la categoría con el registro caído. La analista mantiene el código, porque es lo que exigen la regla 5 del enunciado («si una fuente no responde, el informe se entrega») y el caso (f) (noticias caídas con el informe entregado). Se alinean la spec (FR-014, SC-004 y la decisión confirmada), el contrato `continuacion-y-cierre.md`, el data-model, R3 y `DECISIONES.md`. **No es una desviación**: tras este commit la spec dice lo mismo que el código, y el recorrido de SC-004 ya lo comprobaba con las listas, las noticias y la categoría caídas.
- **El sexto motivo sin causa** («los conflictos entre fuentes no se pudieron comprobar»), cuando los conflictos no son `sin_conflictos` ni `con_conflictos`. Sin él, un caso con todo cubierto y los conflictos en `sin_consulta` daba una causa vacía y el resumen se rechazaba siempre (FR-003, FR-009). Precisa FR-009, como el quinto.
- El coste y los turnos del coordinador se suman entre turnos; la excepción del caso sellado en la descripción de `escalar_a_cumplimiento`; la guía de `categoria_desconocida` dice que sin confirmación se registra el informe con la categoría no determinada; el riesgo del sello durante la espera del registro, en «Riesgos de R13 que no son desviaciones».

## Decisiones del plan

1. **Continuación (R1)**: `Caso.continuar(mensaje)` con `resume=<session_id>`, sobre el mismo estado, hooks y `Delegador`. Medido con el SDK real:
   - conserva el contexto;
   - ejecuta los hooks y el servidor en proceso nuevo;
   - `num_turns` es por turno.

   Se descartaron `ClaudeSDKClient` abierto y reenviar la conversación.
2. **Mensajes del analista (R2)**: `estado.mensajes`, con `solicitud` como propiedad y el evento `mensaje_analista`.
3. **Esperas (R3)**: `espera_del_analista(estado)`, pura, con tres clases. La identificación gana una `clase`, para no decidir por subcadenas del motivo. D3 del #9 (`contradictoria`) no es espera. El `Stop` mira la espera antes que el cierre y no gasta devoluciones.
4. **Cierre por turno (R4)**: el contador y las marcas del cierre se reinician al empezar cada turno. `completo` sí lee las marcas; la garantía se mantiene porque el `Stop` vuelve a evaluar al final de cada turno e `informe_vigente` depende de las causas. Dos tests lo fijan: el turno 2 que informa deja el caso completo, y el que no hace nada vuelve a poner la marca.
5. **Escalamiento (R5)**: el `PreToolUse`, en orden:
   - con el sello, pasa con textos fijos (sin comercio, `COMERCIO_NO_IDENTIFICADO`);
   - en la espera del identificador o del nombre, deniega;
   - con bajo riesgo sin hallazgos comprobado, deniega;
   - si la forma, las fuentes o los frentes cubiertos fallan, deniega con `resumen_rechazado`; sin comercio, deniega pidiendo delegar el registro (D2);
   - si no, sustituye comercio, cobertura, causa y conflictos.

   `degradar_escalamiento` se mantiene ante excepciones. **Cambio respecto al #8**: el escalamiento ya se puede denegar en dos casos comprobados.
6. **Esquema del resumen (R6)**: `validar_resumen` en `servidor_mcp/informe.py`, compartido por la pasarela, el hook y la simulación. Añade `conflictos` al resumen. El rechazo del hook usa una función común con el informe (`denegar_decision`).
7. **FR-027 (R7)**:
   - la cobertura de noticias exige una consulta del comercio identificado;
   - para noticias y listas, solo cuentan las fuentes de consultas del comercio, y en listas también las de su representante;
   - la categoría se conserva.

   Resuelve el riesgo residual 8 del #9 para esos dos frentes.
8. **Escalamiento vigente (R8)**: `Escalamiento(causas, comercio)`, confirmado en el `PostToolUse` y descartado en el `PostToolUseFailure`. `decide_cumplimiento` exige uno del comercio actual.
9. **Categoría (R9)**: la frase normalizada tiene que estar contenida, con límites de palabra, en algún mensaje. Si no, deniega con I.3 y marca `categoria_bloqueada`.
10. **Presupuesto (R10)**: por turno. Los pasos fijos pasan de 8 a 10 (escalamiento rechazado y noticias de nuevo), así que el total es 21 de 30.
11. **Instrucciones (R11)**:
    - `_REGLA_TRAS_IDENTIFICAR` (FR-028) y `_REGLA_RESUMEN_OFICIAL` van en los dos modos;
    - `_REGLA_VARIAS_COINCIDENCIAS` se amplía (terminar el turno y seguir en el mismo caso) y `_REGLA_ESCALAR` añade «no escales un bajo riesgo sin hallazgos»; las dos las quita el modo de demostración;
    - la descripción de `delegar_frente` pide la categoría del analista.
12. **Simulación y línea de comandos (R12)**:
    - un guion por turno, con `resume`;
    - `resumen_del_caso` para los pasos de escalar;
    - `__main__` pregunta en la entrada estándar cuando hay espera (`--sin-continuar` para no preguntar) y muestra la espera y los escalamientos.
13. **DECISIONES.md**: se escribe en la implementación. Recoge:
    - el escalamiento que se puede denegar (cambio respecto al #8);
    - `decide_cumplimiento` con escalamiento;
    - las tres esperas y D3 del #9 fuera de ellas;
    - la categoría de los mensajes y sus riesgos;
    - FR-027;
    - el cierre por turno;
    - el presupuesto de 21;
    - D1, D2 y D3 de este plan;
    - el rechazo del informe durante la espera del identificador o del nombre (cambio respecto al #9).

## Project Structure

### Documentation (this feature)

```text
specs/010-escalamiento-criterio-handoff/
├── spec.md
├── plan.md              # este archivo
├── research.md          # R1–R13
├── data-model.md
├── quickstart.md        # Q1–Q6
├── contracts/
│   ├── escalar-a-cumplimiento.md
│   └── continuacion-y-cierre.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/servidor_mcp/
├── informe.py               # + validar_resumen, mensaje_resumen (R6)
├── decisiones.py            # escalar_a_cumplimiento con el esquema nuevo; fuera _validar
├── servidor.py              # descripción de escalar_a_cumplimiento
└── test_informe.py, test_decisiones.py, test_servidor.py

src/due_diligence/
├── estado.py                # mensajes, solicitud (propiedad), categoria_bloqueada,
│                            # escalamientos_pendientes, Identificacion.clase, Causa.OTRO_COMERCIO
├── libro.py                 # Escalamiento(causas, comercio)
├── reglas.py                # espera_del_analista, bajo_riesgo_sin_hallazgos, escalado_para_el_comercio,
│                            # categoria_en_mensajes, consulta_del_comercio, causas_del_resumen,
│                            # evaluar_escalamiento; escalamiento_cubre y evaluar_informe cambian
├── cobertura.py             # noticias de otro comercio (R7)
├── informe.py               # fuentes_consultadas por comercio (R7)
├── hooks.py                 # _escalar_previo, _escalar_posterior, _escalar_fallido, _delegar_previo
│                            # (categoría), _cierre (esperas), denegar_decision
├── eventos.py               # mensaje_analista, espera_analista
├── coordinador.py           # Caso.continuar, espera, turnos_del_caso; instrucciones (R11)
├── configuracion.py         # opciones_base(resume=...), PASOS_FIJOS_PEOR_CASO = 10
├── delegacion.py            # descripción de delegar_frente (categoría)
├── simulacion.py            # guiones por turno, resume, resumen_del_caso, N-0001, validar_resumen
├── __main__.py              # continuación por la entrada estándar, espera y escalamientos
├── test_casos_escalamiento.py   # nuevo: (a), (b), (d) en dos turnos, SC-004
└── test_*.py                # existentes: se amplían o se adaptan
```

**Structure Decision**: los dos paquetes existentes, sin módulos de producción nuevos. Las reglas nuevas son funciones puras en `reglas.py`, junto a las del #7, y el esquema del resumen va junto al del informe, en `servidor_mcp/informe.py`.

## Orden de implementación sugerido

1. **Pasarela**: `validar_resumen` y `escalar_a_cumplimiento` con el esquema nuevo (tests primero).
2. **Estado y libro**: `mensajes`, `Identificacion.clase`, `Escalamiento`, `categoria_bloqueada` y `Causa.OTRO_COMERCIO`.
3. **Funciones puras**: esperas, bajo riesgo sin hallazgos, escalamiento por comercio, categoría en mensajes, consulta del comercio y causas del resumen. Después, la cobertura y las fuentes de FR-027.
4. **Reglas**: `evaluar_informe` con `decide_cumplimiento`, `escalamiento_cubre` por comercio y `evaluar_escalamiento`.
5. **Hooks**: `_escalar_previo`, `_escalar_posterior` y `_escalar_fallido`; la categoría en `_delegar_previo`; las esperas en `_cierre`; `denegar_decision`.
6. **Coordinador**: `continuar`, cierre por turno, instrucciones y `opciones_base(resume)`.
7. **Simulación**: guiones por turno, `resumen_del_caso` y noticias de `CO-AM-0005`.
8. **Casos de extremo a extremo**: (a), (b), (d) en dos turnos y SC-004.
9. **Línea de comandos**, presupuesto y adaptación de los tests del #5 al #9.
10. **Documentación**: `DECISIONES.md`, `README.md` y el `CLAUDE.md` de `servidor_mcp`.
11. **Quickstart** Q1 a Q6.

## Complexity Tracking

Sin violaciones de la constitución que justificar. Las desviaciones de requisitos de la spec y de los principios I.4 y V son D1 a D4, con su motivo y su mitigación arriba.
