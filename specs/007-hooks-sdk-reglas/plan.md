# Implementation Plan: Hooks del SDK: reglas de negocio 1, 2 y 3 garantizadas

**Branch**: `007-hooks-sdk-reglas` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-hooks-sdk-reglas/spec.md`

## Summary

Las reglas I.1, I.2 e I.3 pasan de ser una guía en el prompt del coordinador a ser hooks del Agent
SDK que bloquean la acción prohibida, tengan o no las reglas en el prompt. Se añaden, en
`src/due_diligence/`, un **libro de reglas** dentro del estado del caso (lo que los hooks
registran), un módulo de **evaluación pura** de las reglas y un módulo de **hooks** que los
adapta al SDK, reparte por agente y envuelve para que fallen cerrados. El coordinador recibe
cuatro hooks (`delegar_frente` de listas, `registrar_informe`, `escalar_a_cumplimiento` y `Stop`) y cada
subagente los que vigilan su propia herramienta.

El sondeo real con el SDK 0.2.168 (research R1 a R3) fija el diseño: `PostToolUse` recibe el resultado
de éxito (texto JSON en stdio, lista de bloques en proceso) y los errores estructurados llegan solo por
`PostToolUseFailure`; **una excepción en un hook deja pasar la acción**, así que cada hook se
envuelve para denegar o bloquear; un `Stop` con `block` hace que el coordinador continúe, cada
devolución gasta un turno y el límite de devoluciones es un contador propio del caso. La
identificación del comercio tiene **una sola fuente de verdad**: se reutiliza `derivar_comercio` como
único intérprete y el hook es el único escritor (R4). El conjunto cerrado de recomendaciones del
informe es `habilitar`, `no_habilitar` y `decide_cumplimiento` (R10). Se retira del coordinador la
prohibición de decidir del #6 (FR-019) y se añade el modo de demostración (R11).

## Technical Context

**Language/Version**: Python 3.12 gestionado con uv.

**Primary Dependencies**: `claude-agent-sdk>=0.2.168,<0.3` y `mcp>=2.3,<3`, ya declaradas por el #6 y el
#5. **No se añade ninguna dependencia nueva.**

**Storage**: N/A. El libro de reglas vive en memoria dentro del `EstadoCaso`, como el resto del
estado del caso (spec, supuestos). Los informes y escalamientos los guarda el servidor del #5 en
`resultados/`, que no cambia.

**Testing**: pytest junto al código, deterministas y sin llamar al modelo (SC-008). Sesiones y
llamadas a herramientas simuladas con `SesionSimulada` (R4). El sondeo con modelo real
(`sondeo_hooks.py`) es manual y repite lo medido en R1 a R3 con Haiku.

**Target Platform**: Windows, macOS y Linux (principio X); validado a mano solo en Windows.

**Project Type**: biblioteca/proceso Python (paquete `due_diligence`, sin interfaz propia; la de chat es #11).

**Performance Goals**: las reglas se evalúan en microsegundos y no añaden llamadas al modelo. El único
coste en modelo es el de los turnos extra de un `Stop` devuelto, acotado por `MAX_CIERRES_IMPEDIDOS`.

**Constraints**:
- Los hooks fallan cerrados (R2); no hay forma de desactivarlos, ni en el modo de demostración.
- Un solo intérprete de la respuesta del registro (`derivar_comercio`) y un solo lector de lo que
  devuelve una herramienta (`interpretar_resultado`); ninguna lógica duplicada (R1, R4, R7).
- Sin estado de módulo: el libro de reglas es por caso (FR-011).
- El texto que ve el modelo no repite nombres ni identificadores consultados (FR-016).
- Sin credenciales ni datos reales (VII, VIII); el sondeo no lee `.env`.

**Scale/Scope**: un caso a la vez en memoria; cuatro hooks en el coordinador y cinco en los subagentes (R5).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitución v1.0.1. Resultado: **cumple, con el cierre parcial de una desviación heredada y sin
desviaciones nuevas.**

| Principio | Estado | Cómo |
|-----------|--------|------|
| **I.1** Sin listas sin identificación unívoca | **Cumple, garantizado por hook** | `PreToolUse` de `consultar_listas_restrictivas` en el subagente de listas y `PreToolUse` de `delegar_frente` (listas) en el coordinador (FR-002, FR-018). Caso (e). |
| **I.2** Coincidencia en listas impide habilitar y escala | **Cumple, garantizado por hook** | `PostToolUse` de listas registra coincidencias; `PreToolUse` de `registrar_informe` rechaza `habilitar` y exige escalar; `Stop` impide cerrar sin escalar (FR-004 a FR-007). Caso (c). |
| **I.3** Alto riesgo nunca recibe habilitación automática | **Cumple, garantizado por hook** | Constante `ALTO_RIESGO` y nivel «alto» persistente; `registrar_informe` rechaza `habilitar` y exige escalar (FR-005, FR-008). Casos (a) y (b). |
| **I.4** Fuente en cada afirmación | Sin cambios | El estado conserva contenido y metadatos por separado (#6); el informe con procedencia es del #9. Los hooks leen contenido, no lo transforman. |
| **I.5** Cobertura declarada | No aplica | Es del #8. Los hooks fallan cerrados ante un fallo, sin presentar el caso como completo (`Caso.completo`). |
| **II** Garantizado vs. sugerido | **Cumple** | I.1, I.2 e I.3 son hooks del SDK, con tests deterministas, y el modo de demostración prueba que no dependen del prompt. **Cierra** la desviación temporal del principio II declarada en el #6 *en lo que toca a las reglas 1 a 3*: `registrar_informe` y `escalar_a_cumplimiento` dejan de estar pre-aprobadas sin guarda. |
| **III** Arquitectura de agentes | Cumple | Hooks por agente con estado compartido, sin que los subagentes compartan conversación (R5); el ciclo sigue terminando por `stop_reason` (el límite de devoluciones del `Stop` es protección documentada y propia del caso, R3). |
| **IV** Herramientas y MCP | Cumple | Las decisiones solo salen por las dos herramientas; las descripciones del servidor no cambian de significado (solo se nombran los tres valores de recomendación como guía). |
| **V** Escalamiento con criterio | Cumple | Escalar solo por coincidencia o alto riesgo; un comercio de bajo riesgo sin hallazgos no se escala y recibe `habilitar` (US3.6). El contenido del resumen al oficial es del #10. |
| **VI** Transparencia | Cumple | Cada bloqueo es un evento con regla y motivo en español, visible en el chat y legible sin conocer el código (R12, SC-007). |
| **VII** Datos ficticios | Cumple | Solo los del #5; ninguna prueba añade datos reales ni valores con forma de tarjeta, NIT o cédula. |
| **VIII** Sin credenciales | Cumple | El sondeo y los tests no leen `.env`; las credenciales de la CLI vienen de la sesión. |
| **IX** Spec first | Cumple | Spec, plan y tareas del ticket antes del código; el issue recibe los comentarios de avance. |
| **X** Calidad y pruebas | Cumple | pytest junto al código, ruff tras cada edición, casos (a), (c) y (e) obligatorios y (b) como contraste. Revisión independiente y auditoría de cumplimiento antes del PR (`/abrir-pr`). |

**Verificación explícita de cumplimiento (constitución, flujo de desarrollo 2)**: las reglas de
negocio I.1, I.2 e I.3 son lo que este ticket implementa, así que la auditoría de `/abrir-pr`
debe verlas **aplicables y con evidencia** (código y tests de `reglas.py`, `hooks.py` y de las
pruebas de los casos). I.4 e I.5 siguen delegadas a #9 y #8 y deben salir `no aplica` con esa
razón.

**Desviaciones**: ninguna nueva. **Cierre parcial** de la del principio II del #6 (reglas 1 a 3). Quedan
abiertas, y son de otros tickets, I.4 e I.5 en el informe y la cobertura (#8 y #9), el contenido del
resumen al oficial (#10) y la revisión de los datos de las respuestas en la interfaz (#11).

**Re-evaluación tras el diseño (Fase 1)**: se mantiene. El diseño añade dos riesgos que se declaran en
vez de ocultarse: que una excepción de un hook de registro bloquea el caso (deliberado, R2) y que la
protección de `Stop` termina el caso marcado como `cierre_sin_escalar` si el modelo insiste más de
`MAX_CIERRES_IMPEDIDOS` veces (R3).

## Decisiones del plan

Detalle y mediciones en [research.md](research.md).

1. **Sondeo real (R1 a R3)**: (a) `PostToolUse` recibe `tool_response` (texto JSON en stdio, lista de
   bloques en proceso). (b) Los errores estructurados de la pasarela llegan solo por
   `PostToolUseFailure`, en `error`. (c) Ante una excepción o una salida inválida el SDK **deja pasar
   la acción**: cada hook se envuelve para denegar o bloquear y los de registro marcan un fallo que
   bloquea los `PreToolUse`. (d) Un `Stop` con `block` hace que el coordinador continúe; cada
   devolución gasta un turno y `stop_hook_active` no sirve de contador: el límite es
   `cierres_impedidos` del caso, `MAX_CIERRES_IMPEDIDOS = 3`.
2. **Una sola fuente de verdad (R4)**: `derivar_comercio` se reutiliza y es el único intérprete;
   el hook de registro es el único escritor; `estado.comercio` pasa a ser una propiedad derivada;
   desaparecen `Delegador._fijar_comercio` y `EstadoCaso.fijar_comercio`. La comparación de consultas
   de listas con el comercio, que ya existía en `_falta_en_listas`, se extrae a una función pura
   compartida (R7).
3. **Hooks por agente (R5)**: una fábrica por caso construye cuatro conjuntos de hooks con cierre
   sobre el mismo estado; `Caso` deja de aceptar `hooks` genérico.
4. **Reglas puras (R7 a R9)**: `reglas.py` decide con funciones puras sobre el libro y `estado.comercio`;
   `hooks.py` solo adapta (lee la entrada del SDK, llama a `reglas`, escribe el libro y devuelve la
   salida tipada). Así las reglas se prueban sin SDK. `consulta_coincide` exige que cada clave que
   trae la consulta exista en la entidad del registro y coincida: un `identificador` consultado para un
   representante sin identificador no coincide (test explícito). `Caso.completo` es `False` también si
   existe `libro.fallo_de_hook`.
5. **Recomendaciones (R10)**: `habilitar`, `no_habilitar` y `decide_cumplimiento`. Lo que no es uno de
   los tres se rechaza siempre.
6. **Instrucciones y demo (R11)**: se retira la prohibición de decidir; la instrucción mínima
   nombra los tres valores y dice cuándo usar cada uno (caso escalado: `decide_cumplimiento`; sin
   escalamiento y sin habilitar: `no_habilitar`; es guía, no hook); el modo de demostración quita la regla 3 y la instrucción de escalar y no toca
   los hooks.
7. **Eventos (R12)**: seis tipos nuevos y un campo `regla` opcional en `Evento`.

## Project Structure

### Documentation (this feature)

```text
specs/007-hooks-sdk-reglas/
├── plan.md              # Este archivo
├── research.md          # Fase 0: sondeo del SDK y decisiones R1 a R12
├── data-model.md        # Fase 1: libro de reglas, causas, eventos
├── quickstart.md        # Fase 1: validación Q1 a Q8
├── contracts/
│   └── hooks.md         # Fase 1: contrato de los hooks por agente
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks, no lo crea este comando)
```

### Source Code (repository root)

```text
src/due_diligence/
├── libro.py                 # NUEVO: LibroReglas, ConsultaListas, Coincidencia, ConsultaRiesgo
├── reglas.py                # NUEVO: ALTO_RIESGO, RECOMENDACIONES, evaluación pura, comparación de consultas
├── hooks.py                 # NUEVO: HooksDelCaso, hooks por agente, fallar_cerrado, salidas tipadas
├── estado.py                # EDITA: libro, identificaciones, comercio derivado; deriva_comercio intacto
├── delegacion.py            # EDITA: sin _fijar_comercio; usa reglas.consulta_coincide
├── coordinador.py           # EDITA: sin PROHIBICION_DECISION; instrucción mínima; hooks por agente; Caso.completo
├── configuracion.py         # EDITA: MAX_CIERRES_IMPEDIDOS; variable de demostración
├── eventos.py               # EDITA: tipos nuevos y campo regla
├── simulacion.py            # EDITA: SesionSimulada que ejecuta los hooks de las opciones
├── sondeo_hooks.py          # NUEVO: sondeo manual con modelo real (Q4)
├── test_libro.py            # NUEVO
├── test_reglas.py           # NUEVO
├── test_hooks.py            # NUEVO
├── test_hooks_sesiones.py   # NUEVO: US5, frentes en sesiones separadas y dos casos
├── test_modo_demo.py        # NUEVO
├── test_estado_identificacion.py  # NUEVO: R4, fuente única
├── test_casos_reglas.py     # NUEVO: casos de prueba (a), (b), (c), (e) con el caso completo
└── (tests del #6 que se adaptan: test_coordinador.py, test_configuracion.py,
     test_delegacion.py, test_eventos_estado.py, test_contexto.py)

src/servidor_mcp/servidor.py  # EDITA: la descripción de registrar_informe nombra los tres valores
DECISIONES.md                 # entrada del ticket (residuales de R12)
README.md                     # sección del modo de demostración
```

**Structure Decision**: se queda en el paquete `due_diligence` del #6 (un solo proyecto, `src/`), con tests junto al
módulo que prueban (CLAUDE.md del repositorio). La separación `libro` (datos) / `reglas` (decisión)
/ `hooks` (SDK) deja las reglas probables sin SDK y el adaptador delgado.

## Orden de implementación

1. **Eventos y libro**: `eventos.py` (tipos y `regla`), `libro.py`, `test_libro.py`.
2. **Reglas puras**: `reglas.py` (constantes, `causas_vigentes`, `evaluar_informe`, `evaluar_cierre`,
   `consulta_coincide`, `permite_listas`), con `test_reglas.py` primero (rojo).
3. **Fuente única de la identificación (R4)**: `estado.py` (identificaciones, propiedades),
   `delegacion.py` (sin `_fijar_comercio`, usa `consulta_coincide`), adaptación de tests del #6 y
   `SesionSimulada`. *Parada de revisión A.*
4. **Hooks**: `hooks.py` y `test_hooks.py` (incluye el envoltorio y la validez de las salidas),
   `test_hooks_sesiones.py`.
5. **Cableado**: `coordinador.py` (hooks por agente, instrucciones, `Caso.completo`, demo),
   `configuracion.py`; `test_modo_demo.py` y `test_casos_reglas.py`. *Parada de revisión B.*
6. **Sondeo y documentación**: `sondeo_hooks.py`, descripción de `registrar_informe`, `DECISIONES.md`,
   `README.md`.
7. **Validación**: quickstart Q1 a Q8, `uv run pytest`, `uv run ruff format .` y `uv run ruff check .`.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
