# Implementation Plan: Errores estructurados y cobertura parcial

**Branch**: `008-errores-estructurados-cobertura` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-errores-estructurados-cobertura/spec.md`

## Summary

Una falla en un frente deja de ser un dato opaco. El coordinador recibe un error estructurado con
el frente, una causa de un conjunto cerrado, lo obtenido y si la política permite otro intento.
Puede pedir **un reintento por frente** con la misma entrada, y el `Delegador` lo hace cumplir en
código. La **cobertura** de los cuatro frentes la calcula un módulo puro nuevo (`cobertura.py`) y
es la única que queda registrada: el `PreToolUse` de `registrar_informe` (del #7) y uno nuevo de
`escalar_a_cumplimiento` sustituyen con `updatedInput` la cobertura que declaró el modelo. Un
sondeo real midió que el SDK 0.2.168 lo aplica a la herramienta MCP por stdio, siempre que se
envíe la entrada completa (R1). `Caso.completo` usa esa misma cobertura.

El presupuesto de turnos del peor caso (15) cabe en `MAX_TURNOS_SEGURIDAD = 30`: un reintento y una
devolución del `Stop` gastan un turno cada uno (R2, medido). El caso (f) se prueba de extremo a
extremo con la simulación y se valida una vez con el modelo real.

## Technical Context

**Language/Version**: Python 3.12 gestionado con uv.

**Primary Dependencies**: `claude-agent-sdk>=0.2.168,<0.3` y `mcp>=2.3,<3`, ya declaradas. **No se
añade ninguna dependencia nueva.**

**Storage**: N/A. El historial de intentos y el último error de cada frente viven en memoria, en el
`Delegador` y en el `EstadoCaso` del caso. La pasarela del #5 guarda los informes en `resultados/`,
sin cambios en el servidor.

**Testing**:
- pytest junto al código, determinista y sin llamar al modelo (FR-015);
- `SesionSimulada` reproduce `updatedInput` como lo midió R1, y `EjecutorSimulado` puede devolver
  resultados en secuencia (R8);
- `sondeo_hooks.py` repite a mano lo medido en R1 y R2 (R9).

**Target Platform**: Windows, macOS y Linux (principio X); validado a mano solo en Windows.

**Project Type**: biblioteca/proceso Python (paquete `due_diligence`; la interfaz de chat es del #11).

**Performance Goals**: el cálculo de la cobertura y la política son instantáneos. El único coste
adicional en modelo es un turno por reintento y el tiempo del subagente reintentado, acotados por
`MAX_REINTENTOS_POR_FRENTE = 1`.

**Constraints**:
- La cobertura registrada es siempre la del código (FR-011). Si no se puede calcular:
  - el informe se deniega (`fallar_cerrado`, #7);
  - el escalamiento **nunca se deniega**: sale con el texto fijo «No se pudo calcular la cobertura;
    debe tratarse como incompleta.» y se sella `fallo_de_hook`, de modo que el caso no figura como
    completo (R6).
- `updatedInput` lleva siempre la entrada completa: el SDK no la fusiona (R1, e3).
- Ningún texto interno de una excepción llega al modelo, a los eventos ni a la cobertura (US2-7).
- Los contratos del #6 se mantienen: `tipo`, `reintentable` y `obtenido`; solo se añaden campos (R4).
- Sin estado de módulo, sin credenciales y solo datos ficticios.

**Scale/Scope**: un caso a la vez. Cambian 9 módulos de `src/due_diligence/` y se añade uno
(`cobertura.py`); hay 3 eventos nuevos; el coordinador pasa de 5 a 6 hooks registrados.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitución v1.0.1. Resultado: **cumple, sin desviaciones.**

| Principio | Estado | Cómo |
|-----------|--------|------|
| **I.1–I.3** | Sin cambios | Los hooks del #7 se conservan. El de `registrar_informe` sigue rechazando primero por las reglas y solo después sustituye la cobertura (R6). Un reintento de registro pasa por el mismo hook de identificación (#7). |
| **I.4** Fuente en cada afirmación | Sin cambios | `obtenido` conserva contenido y metadatos separados. La cobertura es una afirmación del sistema sobre su propia ejecución; su lugar en el esquema del informe es del #9. |
| **I.5** Cobertura declarada | **Cumple, garantizado en código** | `calcular_cobertura` (R5) y el reemplazo en `registrar_informe` y `escalar_a_cumplimiento` (R1, R6); `Caso.completo` usa la misma cobertura. Caso (f). |
| **II** Garantizado vs. sugerido | Cumple | Lo obligatorio está en código: la cobertura registrada (hook), qué se reintenta y cuántas veces (`Delegador`), y el caso completo. El prompt solo orienta cuándo pedir el reintento (R7). |
| **III** Arquitectura de agentes | Cumple | Error estructurado con lo obtenido y `reintentable` (R4); el coordinador decide si reintenta y el código lo guarda (R3); el ciclo sigue terminando por `stop_reason`. `MAX_REINTENTOS_POR_FRENTE = 1` es protección documentada, como `MAX_CIERRES_IMPEDIDOS`, no control del ciclo. Los frentes siguen aislados y en paralelo (FR-013). |
| **IV** Herramientas y MCP | Cumple | La pasarela no cambia. La descripción de `delegar_frente` dice qué hace un pedido repetido (R7). Los errores siguen siendo estructurados y declaran si son reintentables. |
| **V** Escalamiento con criterio | Cumple | El escalamiento registra la cobertura alcanzada calculada en código; el resto del resumen al oficial es del #10. |
| **VI** Transparencia | Cumple | Eventos `frente_reintento`, `reintento_denegado` y `cobertura_sustituida`; la línea de comandos muestra la cobertura y los turnos. |
| **VII** Datos ficticios | Cumple | Solo los del #5 y los simulados. |
| **VIII** Sin credenciales | Cumple | El sondeo y los tests no leen `.env`. |
| **IX** Spec first | Cumple | Spec (`f207a9f`), plan y tareas antes del código; comentarios de avance en el issue. |
| **X** Calidad y pruebas | Cumple | pytest junto al código, ruff, caso (f) obligatorio, revisión independiente y auditoría en `/abrir-pr`. |

**Verificación explícita de cumplimiento (flujo de desarrollo 2)**:
- La auditoría de `/abrir-pr` debe ver **I.5 aplicable y con evidencia**: `cobertura.py`, los hooks
  de `registrar_informe` y `escalar_a_cumplimiento`, y `test_casos_cobertura.py`.
- **I.1, I.2 e I.3 aplican**, porque el diff toca `hooks.py` y `_informe_previo`. Su evidencia son
  los tests del #7, que deben seguir en verde sin debilitarse.
- I.4 sigue delegada al #9.

**Re-evaluación tras el diseño (Fase 1)**: se mantiene. El diseño declara cinco riesgos residuales
(R10) en vez de ocultarlos. El principal: la respuesta final al analista sigue siendo texto del
modelo, mientras que lo autoritativo (informe, escalamiento, eventos y línea de comandos) sale del
código.

## Decisiones del plan

Detalle y mediciones en [research.md](research.md).

1. **`updatedInput` (R1, medido)**: reemplaza la entrada de una herramienta MCP por stdio, con o
   sin `allow`, y **la sustituye entera**. El hook del informe devuelve `allow` + la entrada completa
   con la cobertura del código; no hace falta el plan B (`deny` con motivo).
2. **Turnos (R2, medido)**: un reintento y una devolución del `Stop` gastan un turno cada uno. El
   peor caso suma 15 de 30. `PRESUPUESTO_TURNOS_PEOR_CASO` se calcula con `MAX_REINTENTOS_POR_FRENTE`,
   `MAX_CIERRES_IMPEDIDOS` y los 8 pasos fijos, no como un literal, así que el test que lo compara con
   `MAX_TURNOS_SEGURIDAD` protege si esas constantes cambian. `caso.turnos` lo hace observable.
3. **Política de reintento (R3)**:
   - la pide el modelo y la guarda el `Delegador`;
   - la clave es `(frente, contexto)` y se permite 1 reintento;
   - `reintentable` en la respuesta significa «otro intento permitido»;
   - un pedido que esperó a una ejecución en curso no reintenta;
   - los rechazos sin ejecución no cuentan.
4. **Error estructurado (R4)**:
   - se conserva `tipo` y se añaden `frente`, `causa` (conjunto cerrado), `intento` y
     `reintentos_restantes`;
   - solo `error_de_fuente` con todos sus errores reintentables, y el rechazo de listas antes del
     registro, son reintentables;
   - se quita el texto de la excepción de `detalle_terminacion`.
5. **Cobertura (R5)**:
   - `cobertura.py` es puro y se deriva de la situación y del último error de cada frente;
   - se registra como lista de textos;
   - `Caso.completo` la usa.
6. **Hooks (R6)**:
   - `_informe_previo` sustituye la cobertura tras las reglas y, ante una excepción, falla cerrado
     con `deny`;
   - `_escalar_previo` es nuevo, no mira el sello del libro y nunca deniega. Ante una excepción
     (`degradar_escalamiento`), deja pasar el escalamiento con el texto fijo
     `COBERTURA_NO_CALCULADA` y sella `fallo_de_hook`;
   - ambos dejan el evento `cobertura_sustituida`, que se emite antes de que la pasarela acepte la
     llamada y por eso no dice que quedó registrada.
7. **Instrucciones (R7)**: una regla nueva del coordinador sobre reintentos y cobertura, presente
   también en el modo de demostración, y la descripción de `delegar_frente` ampliada.
8. **Simulación y sondeo (R8, R9)**: `SesionSimulada` aplica `updatedInput`; `en_secuencia` para
   ejecutores; `sondeo_hooks.py` gana (e), (f) y G3.

## Project Structure

### Documentation (this feature)

```text
specs/008-errores-estructurados-cobertura/
├── spec.md
├── plan.md              # este archivo
├── research.md          # R1–R10
├── data-model.md
├── quickstart.md        # Q1–Q7
├── contracts/
│   ├── delegar-frente.md
│   └── cobertura.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/due_diligence/
├── cobertura.py                 # NUEVO: calcular_cobertura, CoberturaFrente, CoberturaCaso (R5)
├── test_cobertura.py            # NUEVO: las 625 combinaciones, motivos y formato (Q4)
├── delegacion.py                # causa, intento, reintentos, política (R3, R4); sin texto de excepción
├── test_delegacion.py           # se amplía; los tests de listas reintentable no cambian
├── test_reintentos.py           # NUEVO: política de reintento (Q3)
├── estado.py                    # EstadoCaso.errores (último error por frente)
├── test_eventos_estado.py       # se amplía
├── eventos.py                   # frente_reintento, reintento_denegado, cobertura_sustituida
├── hooks.py                     # reemplazar_entrada, _informe_previo, _escalar_previo,
│                                #   degradar_escalamiento, COBERTURA_NO_CALCULADA (R6)
├── test_hooks.py                # se amplía
├── coordinador.py               # Caso.cobertura, Caso.completo, Caso.turnos, _REGLA_FALLOS (R7)
├── test_coordinador.py          # se amplía
├── configuracion.py             # MAX_REINTENTOS_POR_FRENTE, PASOS_FIJOS_PEOR_CASO y
│                                #   PRESUPUESTO_TURNOS_PEOR_CASO calculado (R2)
├── test_configuracion.py        # se amplía: presupuesto ≤ MAX_TURNOS_SEGURIDAD
├── simulacion.py                # updatedInput en SesionSimulada, en_secuencia, escalar_con (R8)
├── test_sesion_simulada.py      # se amplía
├── test_casos_cobertura.py      # NUEVO: caso (f) de extremo a extremo (Q2)
├── __main__.py                  # bloque «Cobertura:» y turnos del coordinador
├── test_main.py                 # se amplía
├── sondeo_hooks.py              # experimentos (e), (f) y G3 (R9)
└── test_sondeo_hooks.py         # se amplía (partes puras)

DECISIONES.md                    # entrada 9: errores estructurados y cobertura
README.md                        # una sección breve: reintento y cobertura
```

**Structure Decision**: un solo paquete, `src/due_diligence/`, como en el #6 y el #7, con los tests
junto a cada módulo. `src/servidor_mcp/` no cambia.

## Orden de implementación (para `/speckit-tasks`)

1. Línea base de la suite.
2. Eventos y constantes (`MAX_REINTENTOS_POR_FRENTE`, `PASOS_FIJOS_PEOR_CASO` y
   `PRESUPUESTO_TURNOS_PEOR_CASO` calculado, con su test).
3. Error estructurado y causas en `delegacion.py`, con el último error en `EstadoCaso` y sin el texto
   de la excepción. Tests primero.
4. Política de reintento. Tests primero (`test_reintentos.py`).
5. `cobertura.py` puro. Tests primero (`test_cobertura.py`).
6. `SesionSimulada` con `updatedInput` y `en_secuencia`.
7. Hooks `_informe_previo` y `_escalar_previo`, `reemplazar_entrada` y `degradar_escalamiento`.
8. `Caso.cobertura`, `Caso.completo`, `Caso.turnos`, instrucciones y descripción.
9. `__main__.py`.
10. `test_casos_cobertura.py`, el caso (f), con una comprobación de mutación.
11. Sondeo (e), (f) y G3.
12. `DECISIONES.md` y README.
13. Quickstart Q1–Q7, anotado en `tasks.md`.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
