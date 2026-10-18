# Implementation Plan: Informe con procedencia, conflictos y registro

**Branch**: `009-informe-procedencia-conflictos` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-informe-procedencia-conflictos/spec.md` (aprobada en `6dce052`)

## Summary

El informe pasa a tener un esquema verificable: cada frente es una lista de afirmaciones con texto,
fuente y fecha. La **pasarela** valida la forma con una función pura (`servidor_mcp/informe.py`)
que el **hook** de `registrar_informe` reutiliza. El hook comprueba además que cada fuente sea una
de las consultadas para ese frente (FR-004).

El código pone tres partes y sustituye lo que declaró el modelo con `updatedInput`, como la
cobertura del #8:
- el **comercio**, el identificado o, con el registro caído, el pedido sin verificar;
- los **conflictos**, de un módulo puro nuevo (`conflictos.py`) que compara las dos fuentes
  registrales;
- la **cobertura**.

El `Stop` exige, después del escalamiento, un **informe vigente**: uno cuya huella (cobertura
cubierto o no, conflictos, causas y comercio) no cambió desde que se registró. La huella se calcula
en el `PreToolUse`, con lo mismo que se sustituye, y se confirma en el `PostToolUse` si la pasarela
acepta. El informe se exige siempre que haya comercio identificado o registro caído, aunque quede
un reintento del registro, con el mismo contador de devoluciones. El presupuesto de turnos sube a
19 de 30.

Tras un fallo de hook, el sello pasa a ser una causa de escalamiento. Así el informe mínimo
(`decide_cumplimiento`, con textos fijos) solo se registra después de escalar.

Se añaden:
- los eventos `informe_registrado`, `datos_sustituidos` y `cierre_sin_informe`, y la acción
  intentada en los bloqueos;
- la hora en UTC en todo;
- el interruptor `PASARELA_FALLA_REGISTRO=1` para probar el registro caído con el modelo real.

## Technical Context

**Language/Version**: Python 3.12 gestionado con uv.

**Primary Dependencies**: `claude-agent-sdk>=0.2.168,<0.3` y `mcp>=2.3,<3`, ya declaradas. **No se
añade ninguna dependencia.** La validación del esquema es manual, no con pydantic, para tener
mensajes en español que nombren todos los problemas (R2).

**Storage**: los informes, en `resultados/informes/` (pasarela del #5), ahora con `conflictos`,
`comercio.verificado` y `registrado_en` en UTC. La huella de cada informe, el comercio pedido y
`cierre_sin_informe` viven en memoria, en el `EstadoCaso`.

**Testing**:
- pytest junto al código, determinista y sin llamar al modelo (FR-019);
- `PasarelaSimulada` valida con la misma función que la pasarela real (R12);
- el caso (g), el caso escalado y el registro caído, de extremo a extremo con el
  `CoordinadorSimulado`.

**Target Platform**: Windows, macOS y Linux; validado a mano en Windows.

**Project Type**: biblioteca/proceso Python (`due_diligence` y `servidor_mcp`; la interfaz de chat es
del #11).

**Performance Goals**: el cálculo de conflictos, la huella y la validación son instantáneos. El coste
en modelo es un turno por informe rechazado, ya incluido en los pasos fijos del presupuesto.

**Constraints**:
- `updatedInput` con la entrada completa (#8, R1). El informe se acepta con `allow` + entrada
  completa.
- Ningún evento, motivo, cobertura ni conflicto repite datos del comercio, salvo los valores en
  conflicto dentro del propio informe, que son su contenido.
- El presupuesto de turnos pasa de 15 a 19 de 30. Se suma un informe nuevo por cada reintento
  posible, y las devoluciones por el informe comparten `MAX_CIERRES_IMPEDIDOS` (R8).
- Los contratos anteriores se mantienen salvo el de `registrar_informe`, que cambia de forma
  deliberada (spec, supuestos).
- Sin estado de módulo, sin credenciales y solo datos ficticios.

**Scale/Scope**:
- cambian 10 módulos de `src/due_diligence/` y 4 de `src/servidor_mcp/`;
- se añaden 3 módulos (`servidor_mcp/informe.py`, `due_diligence/conflictos.py` y
  `due_diligence/informe.py`);
- hay 3 eventos nuevos;
- el coordinador pasa de 6 a 8 hooks registrados (`PostToolUse` y `PostToolUseFailure` del
  informe).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitución v1.0.1. Resultado: **cumple, con las desviaciones justificadas** de la sección
siguiente (D1 a D7), cada una con su motivo, su mitigación y el ticket que la resuelve.

| Principio | Estado | Cómo |
|-----------|--------|------|
| **I.1** Listas tras la identificación | Sin cambios | Los hooks del #7 se conservan. Con el registro caído no hay comercio y listas se sigue rechazando. |
| **I.2 / I.3** Coincidencia y alto riesgo | Sin cambios en la regla; más estricto el cierre | `evaluar_informe` sigue igual y fija el orden escalamiento → informe (FR-012). El sello es una causa más (R9): un caso sellado tiene que llegar al oficial. |
| **I.4** Fuente en cada afirmación y conflictos | **Cumple, garantizado en código**, con D1, D2, D3 y D4 | Esquema en la pasarela y en el hook (R1, R2), fuente consultada y una afirmación por frente cubierto en el hook (R1, R4), conflictos calculados y sustituidos (R5, R6). Caso (g). |
| **I.5** Cobertura declarada | Cumple, se amplía, con D4 y D6 | Cobertura del #8 sin cambios. Además, el informe obligatorio en el cierre (R8) incluye el registro caído (regla 5 del enunciado). |
| **II** Garantizado vs. sugerido | Cumple | Esquema, fuente, comercio, conflictos, informe obligatorio y vigente, e informe mínimo: todo en código (pasarela, hooks y `Stop`). El prompt solo orienta cómo escribir las afirmaciones (R12). |
| **III** Arquitectura de agentes | Cumple | Sin cambios en la delegación; el `Delegador` solo guarda el comercio pedido. Los resultados conservan contenido y metadatos separados, que es de donde salen las fuentes admitidas. El ciclo sigue terminando por `stop_reason`. |
| **IV** Herramientas y MCP | Cumple | Cambia el contrato de `registrar_informe`, con una descripción que dice qué pone el sistema. Los rechazos son errores estructurados: el JSON `informe_rechazado` del hook (R3) y `entrada_invalida` con `problemas` en la pasarela. |
| **V** Escalamiento con criterio | Cumple, con D5 | Los escalamientos solo aumentan con un fallo de hook, que es excepcional. El contenido del resumen al oficial es del #10. |
| **VI** Transparencia | Cumple | `informe_registrado`, `datos_sustituidos`, `cierre_sin_informe`, la acción en los bloqueos y la hora en UTC (R10). |
| **VII** Datos ficticios | Cumple | `CO-RF-0006` y el resto de datos del #5; sin datos nuevos. |
| **VIII** Sin credenciales | Cumple | Los tests y el sondeo no leen `.env`. |
| **IX** Spec first | Cumple | Spec (`6dce052`), plan y tareas antes del código; comentarios de avance en el issue. |
| **X** Calidad y pruebas | Cumple | pytest junto al código, ruff, caso (g) obligatorio, revisión independiente y auditoría en `/abrir-pr`. |

**Verificación explícita de cumplimiento (flujo de desarrollo 2)**:
- La auditoría de `/abrir-pr` debe ver **I.4 aplicable y con evidencia**: `servidor_mcp/informe.py`,
  `conflictos.py`, `informe.py`, el `PreToolUse` de `registrar_informe` y `test_casos_informe.py`.
- **I.1, I.2, I.3 e I.5 aplican**, porque el diff toca `hooks.py`, `reglas.py` y el `Stop`. Su
  evidencia son los tests del #7 y del #8, que siguen en verde. Los que cambian por el sello como
  causa o por el formato nuevo se adaptan sin debilitarse, y la tabla va en el PR.

**Re-evaluación tras el diseño (Fase 1)**: se mantiene. Los riesgos residuales están declarados en
R13 de [research.md](research.md); los que contradicen un FR, un escenario de la spec o un
principio son las desviaciones D1 a D7, y el resto se explica al final de esa sección.

## Desviaciones justificadas

Revisadas tras la tercera revisión de `/abrir-pr` (fase 13 de [tasks.md](tasks.md)): todo lo que
figuraba como riesgo residual (R13) o como declaración del PR (T050) y contradice un FR, un
escenario de la spec o un principio de la constitución.

| # | Desviación | Contradice | Motivo | Mitigación y dónde se resuelve |
|---|------------|------------|--------|--------------------------------|
| D1 | **La fecha de una afirmación no se contrasta** con la del resultado que cita; solo se valida que sea una fecha real (riesgo residual 3, R4). | Entidad «Afirmación» de la spec (la fecha es la de los metadatos del resultado citado) e I.4. | Una afirmación no apunta a un hecho concreto: puede resumir varios hechos con fechas distintas (las dos fuentes registrales del caso (g) tienen fechas distintas) o una respuesta sin hechos. Contrastarla exigiría una referencia al hecho citado que el esquema (R2) no tiene. | La fuente sí se contrasta con las consultadas (FR-004) y la fecha se valida como fecha (FR-002). El #10 puede añadir la referencia al hecho si reutiliza el esquema de afirmaciones. |
| D2 | **Un informe aceptado por la pasarela sin huella pendiente no deja evento** ni constancia: si el `PostToolUse` no encuentra la huella de un `PreToolUse` que lo aceptara, no hace nada (`hooks.py`, `_informe_posterior`). | FR-016 y US5-1 (todo informe aceptado deja `informe_registrado`). | La huella solo se calcula en el `PreToolUse`, con los mismos datos que se sustituyen (R7); recalcularla en el `PostToolUse` daría por vigente un informe con datos que no se comprobaron. Sin un `PreToolUse` que aceptara la llamada no se ejecuta (un deny la impide), así que solo ocurre si el `tool_use_id` no coincide entre los dos hooks, algo que no se ha observado. | El informe no cuenta como vigente: el `Stop` sigue exigiendo uno y el caso no figura como completo. Si el #11 necesita la constancia, puede añadir un evento sin huella. |
| D3 | **Un conflicto en el nombre o en el representante legal no llega al informe**: el #6 no identifica el comercio cuando las fuentes difieren en esos datos (`estado.py`, `derivar_comercio`), así que los conflictos quedan `sin_comercio` y no se muestran los dos valores. | I.4 (si dos fuentes se contradicen, se muestran ambas), US2 y FR-007. | Esos datos definen la identidad del comercio: si las fuentes no coinciden, el comercio no está identificado de forma unívoca y no se pueden consultar listas (I.1). Es un caso para pedir el identificador al analista (V), no para un informe. | No se exige informe (FR-011); si el coordinador lo registra, va con el comercio pedido `verificado: false` y no se puede habilitar. La ambigüedad y lo que se muestra al analista son del #10. |
| D4 | **El informe mínimo va sin conflictos ni cobertura calculados**, aunque se pudieran calcular: con el sello `fallo_de_hook` los dos son textos fijos y no se exige una afirmación por frente cubierto (FR-014, R9). | I.4 (mostrar los conflictos), I.5 (declarar qué frente quedó sin cubrir), FR-009 y US1-6. | FR-014 lo manda: tras un fallo de hook el libro puede haber perdido un hecho (una coincidencia o una identificación), así que cualquier cálculo puede estar mal. Declarar que no se calculó es lo único que no afirma algo falso. | Solo admite `decide_cumplimiento` y después de escalar (el sello es causa, R9); el caso nunca figura como completo. |
| D5 | **Con el registro caído y sin otras causas, el informe puede salir con `decide_cumplimiento` sin escalar** (riesgo residual 2). | V (el oficial solo decide lo que recibe) y el sentido de «decisión del oficial» de US3. | La regla general («¿`decide_cumplimiento` exige escalar?») afecta al resumen al oficial, que está fuera de alcance (FR-022). | `habilitar` sigue bloqueado sin listas y el caso no figura como completo (cobertura incompleta). Lo resuelve el #10. |
| D6 | **Con un doble fallo de hooks el informe mínimo puede no registrarse** (riesgo residual 6): si con el caso sellado también falla la comprobación de FR-004, `fallar_cerrado` deniega. | US3 y FR-011 (todo due diligence terminado queda registrado). | Ante un fallo no se deja pasar lo que no se pudo verificar (FR-012 del #7, R2); aceptar el informe sin validarlo rompería I.4. | El `Stop` agota las devoluciones y marca `cierre_sin_informe` con su evento (FR-013), también cuando el que falla es el propio `Stop` (fase 13); el caso nunca figura como completo. |
| D7 | **El comercio pedido es el de la última delegación del registro, no el de la solicitud**: si el coordinador consulta solo con el identificador, el informe va con `nombre: null` aunque el analista diera el nombre (T048). | FR-006 (el comercio es el que pidió el analista). | La solicitud es texto libre; la delegación es lo único estructurado que el código tiene del pedido. Sacar el nombre del texto sería adivinar, y el comercio pedido no inventa el dato que falta (R5). | El comercio va `verificado: false` y no se puede habilitar. Lo retoma el #10 o el #11 (observación de T050). |

**Riesgos de R13 que no son desviaciones**:
- **1, informe vigente con afirmaciones viejas**: FR-023 lo admite de forma explícita, por decisión
  de la analista.
- **4, el texto no se verifica contra el contenido**: I.4 exige la fuente de cada afirmación, y eso
  se garantiza; la exactitud de la frase no la exige ni la constitución ni la spec.
- **5, `Stop` en cualquier fin de turno**: es el escenario 8 de US3 y la limitación conocida de los
  supuestos de la spec; lo resuelve el #10.
- **7, motivo del deny en JSON**: FR-003 se cumple en el código; falta observar cómo lo usa el
  modelo real, y en Q3 no hubo rechazos.
- **8, fuentes de un comercio anterior**: FR-004 pide una fuente que el caso consultó para ese
  frente, y lo fue. Los nombres de fuente son genéricos, así que no permite citar una fuente que
  el caso no consultó.

## Decisiones del plan

Detalle en [research.md](research.md).

1. **Dónde se valida cada cosa (R1)**:
   - forma del informe: pasarela y hook, con la misma función;
   - fuente consultada (FR-004): solo el hook, porque la pasarela no conoce el caso;
   - al menos una afirmación por frente cubierto (US1-6), aunque su resultado sea «sin
     hallazgos»: solo el hook, igual que FR-004, porque qué frentes quedaron cubiertos
     depende del estado del caso (`calcular_cobertura`). Un frente no cubierto puede ir
     vacío (I.5) y con el caso sellado (informe mínimo, R9) no se exige, porque la cobertura
     no se calcula;
   - comercio, conflictos y cobertura: los pone el hook;
   - informe obligatorio y vigente: el `Stop`.
2. **Esquema (R2)**: comercio `{identificador, nombre, verificado}`, hallazgos por frente como lista
   de `{texto, fuente, fecha}`, conflictos `{resumen, lista}`, cobertura y recomendación. Se
   devuelven todos los problemas, con su ruta. `escalar_a_cumplimiento` no cambia.
3. **Rechazo estructurado (R3)**: el deny del hook lleva como motivo el JSON `informe_rechazado`,
   con los motivos de las reglas y los problemas del esquema y de las fuentes, en un solo rechazo.
4. **Fuentes consultadas (R4)**: las de los metadatos de los hechos y las de `metadatos.fuentes` de
   las consultas válidas del frente, comparadas con `normalizar.igual`.
5. **Sustitución (R5)**: el código pone comercio, conflictos y cobertura en la entrada completa. Se
   conserva `cobertura_sustituida` y se añade `datos_sustituidos`.
6. **Conflictos (R6)**: se comparan los datos de los hechos del comercio identificado, uno por
   fuente. Hay conflicto cuando dos o más fuentes traen valores distintos, y se muestran en el
   orden de la pasarela, sin precedencia. Hay resumen fijo para «sin conflictos» y para «no
   comparables» (registro caído).
7. **Qué cuenta como cambio para FR-023 (R7)**, la propuesta de la analista: la huella tiene la
   cobertura (solo cubierto o no), los conflictos, las causas y el comercio. Un reintento que
   vuelve a fallar no cambia la huella; uno que sale bien, un cambio de comercio o una coincidencia
   nueva, sí. **La huella se calcula en el `PreToolUse`**, con los mismos datos que se sustituyen,
   y queda pendiente por `tool_use_id`. **El `PostToolUse` solo la confirma** si la pasarela
   acepta. Así, un reintento que termina entre los dos hooks (en el mismo mensaje) deja el informe
   no vigente. Hay un test de ese orden.
8. **Cierre (R8)**:
   - el `Stop` exige el escalamiento y después un informe vigente cuando hay comercio identificado
     o registro caído;
   - el registro está caído cuando no terminó y la fuente no respondió, **con o sin reintento
     disponible** (decisión de la analista); `entrada_invalida` no cuenta;
   - con un reintento disponible, el motivo es «reintenta el registro o registra el informe»;
   - contador compartido; el presupuesto sube a 19 de 30, con un informe nuevo por cada reintento
     posible;
   - `cierre_sin_informe` y su evento;
   - `Caso.completo` exige un informe vigente;
   - la limitación del fin de turno queda fijada con un test para el #10.
9. **FR-014 y FR-012 tras un fallo de hook (R9)**: el sello es una causa de escalamiento
   (`CAUSA_FALLO_DE_HOOK`). Primero hay que escalar, porque escalar nunca se deniega; después, el
   informe mínimo solo con `decide_cumplimiento`, con la cobertura y los conflictos en textos fijos,
   y el esquema y FR-004 validados. Un fallo del cálculo de conflictos en modo normal deniega,
   sella y lleva al informe mínimo.
10. **Traza (R10)**: `informe_registrado` en el `PostToolUse` del informe; el campo `accion` en
    `Evento`; todo en UTC, también `registrado_en` de la pasarela; la línea de comandos imprime la
    hora con UTC.
11. **`PASARELA_FALLA_REGISTRO` (R11)**: el patrón de `noticias.py:19-29`, leído en cada llamada,
    devuelve `servicio_no_disponible` reintentable; lo cubre Q5.
12. **Simulación, sondeo y línea de comandos (R12)**: `PasarelaSimulada` valida como la real; el
    `CoordinadorSimulado` arma informes válidos y tiene los pasos `("informe_con", entrada)` y
    `("mismo_mensaje", [pasos])`; el sondeo G4 usa el formato nuevo; la línea de comandos muestra
    los conflictos y los informes.
13. **DECISIONES.md**, se escribe en la implementación, con:
    - las decisiones (a) y (b) de la spec;
    - **el cambio respecto al #7 de R9**: un caso sellado sin otras causas ya no puede cerrarse sin
      escalar;
    - el registro caído que exige informe aunque quede un reintento (R8);
    - el presupuesto de 19 turnos (R8);
    - el rechazo del informe en JSON (R3, aceptado);
    - la hora en UTC (R10, aceptada; el #11 mostrará la hora de Colombia).

## Project Structure

### Documentation (this feature)

```text
specs/009-informe-procedencia-conflictos/
├── spec.md
├── plan.md                    # este archivo
├── research.md                # R1–R13
├── data-model.md
├── quickstart.md              # Q1–Q7
├── contracts/
│   ├── registrar-informe.md
│   └── cierre.md
├── checklists/requirements.md
└── tasks.md                   # /speckit-tasks
```

### Source Code (repository root)

```text
src/servidor_mcp/
├── informe.py            # NUEVO: validar_informe, Problema, esquema JSON de los parámetros (R2)
├── decisiones.py         # registrar_informe con validar_informe, conflictos; registrado_en UTC (R2, R10)
├── registro.py           # PASARELA_FALLA_REGISTRO (R11)
├── respuestas.py         # error(..., problemas=...) (R3)
├── servidor.py           # parámetros y descripción de registrar_informe (R2)
└── test_informe.py, test_decisiones.py, test_registro.py, test_servidor.py

src/due_diligence/
├── conflictos.py         # NUEVO: calcular_conflictos, ConflictosCaso (R6)
├── informe.py            # NUEVO: huella, informe_vigente, registro_caido, requiere_informe,
│                         #        comercio_del_informe, fuentes_consultadas, problemas_de_fuente (R4, R7, R8)
├── estado.py             # comercio_pedido, informes, cierre_sin_informe
├── delegacion.py         # guarda comercio_pedido (R8)
├── reglas.py             # CAUSA_FALLO_DE_HOOK, evaluar_cierre con informe, evaluar_informe_minimo (R8, R9)
├── hooks.py              # _informe_previo (normal y mínimo), _informe_posterior, _cierre, accion (R3, R5, R9, R10)
├── eventos.py            # 3 tipos nuevos, Evento.accion (R10)
├── coordinador.py        # instrucciones del informe; completo con informe vigente (R8, R12)
├── configuracion.py      # presupuesto de turnos con los informes nuevos tras un reintento: 19 (R8)
├── simulacion.py         # PasarelaSimulada valida; CoordinadorSimulado arma informes (R12)
├── sondeo_hooks.py       # ENTRADA_INFORME con el formato nuevo (R12)
├── __main__.py           # conflictos, informes, accion, hora UTC (R10, R12)
└── test_conflictos.py, test_informe.py, test_casos_informe.py (NUEVOS) + tests existentes adaptados

DECISIONES.md, README.md  # decisiones (a) y (b) y las del plan; PASARELA_FALLA_REGISTRO
```

**Structure Decision**: el mismo proyecto único de los tickets anteriores, con los tests junto a
cada módulo (principio X). El esquema vive en `servidor_mcp`, porque es el contrato del registro, y
`due_diligence` lo importa, como ya importa `servidor_mcp.normalizar` (`reglas.py`).

## Orden de implementación sugerido

1. Pasarela: `informe.py`, `respuestas.problemas`, `decisiones.py`, `servidor.py`, el interruptor
   del registro y UTC, con sus tests.
2. `conflictos.py` y `informe.py` de `due_diligence` (puros), con sus tests.
3. Estado, eventos (`accion`) y `delegacion.comercio_pedido`.
4. `reglas.py`: causa del sello, `evaluar_cierre` y `evaluar_informe_minimo`.
5. Hooks: `_informe_previo`, `_informe_posterior`, `_cierre` y `accion` en los bloqueos; adaptar
   los tests del #7 y del #8 sin debilitarlos.
6. `coordinador.py` (`completo` e instrucciones) y la simulación.
7. Casos de extremo a extremo: (g), escalado, registro caído, vigencia, sello y limitación del `Stop`.
8. Línea de comandos, sondeo, `DECISIONES.md` y `README.md`.
9. Quickstart Q1–Q7.

## Complexity Tracking

Sin complejidad añadida que justificar. Las desviaciones de la constitución y de la spec están en
«Desviaciones justificadas».
