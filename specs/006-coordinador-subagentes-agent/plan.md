# Implementation Plan: Coordinador y subagentes con el Agent SDK

**Branch**: `006-coordinador-subagentes-agent` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-coordinador-subagentes-agent/spec.md`

## Summary

Un coordinador (Claude Agent SDK) que no consulta fuentes: solo delega con **una herramienta propia**,
`delegar_frente`, y decide con `registrar_informe` y `escalar_a_cumplimiento`. Cada delegación lanza a
un subagente con **su propio `query()`**, mediante un **ejecutor inyectable** (R1): en producción el
SDK; en los tests, un ejecutor simulado que permite verificar el solape. Las garantías del ticket
viven en código y no en el prompt:

- **Aislamiento** (R2, R3): toda opción lleva `setting_sources=[]` y `tools=[]`; cada agente tiene
  `allowed_tools` con los nombres completos `mcp__pasarela__…` **y** `disallowed_tools` con el resto, porque
  `allowed_tools` solo pre-aprueba y deja las otras herramientas a la vista *(medido)*.
- **Orden y paralelismo** (R4): `delegar_frente` se anota `readOnlyHint` (sin eso el SDK serializa las
  llamadas *(medido)*) y **listas espera al registro** dentro de la herramienta, con el comercio y el
  representante tomados del estado, no de lo que transcriba el modelo.
- **Fin del ciclo** (R5): lo ejecuta el SDK; el resultado se clasifica por `subtype` y `stop_reason`
  (`error_max_turns` trae `stop_reason=tool_use` *(medido)*, por eso el `subtype` va primero).
- **Estado y eventos** (R6, R7): se capturan de las llamadas a herramientas, no del texto, y quedan
  accesibles por referencia para los hooks del #7.
- **Modelos** (R9): Sonnet 5.5 para el coordinador y para los cuatro subagentes; **.env** con
  `python-dotenv` solo desde el punto de entrada (R8).

No hay hooks de negocio (#7), manejo de fallas (#8), informe (#9), escalamiento (#10) ni interfaz (#11).

## Technical Context

**Language/Version**: Python 3.12 (uv).

**Primary Dependencies**: `claude-agent-sdk>=0.2.168,<0.3` y `python-dotenv>=1.2,<2`, con `uv add`
(actualiza `pyproject.toml` y `uv.lock`); conviven con `mcp>=2.3,<3` (R10).

**Storage**: ninguno. Estado y eventos en memoria durante el caso (R7).

**Testing**: pytest junto al código (`src/due_diligence/test_*.py`), `asyncio` con `asyncio.run`
dentro de cada test (sin plugin nuevo). Sin red ni modelo; los sondeos con el modelo real son manuales
(R12).

**Target Platform**: Windows validado a mano; sin rutas del sistema (`pathlib`, `sys.executable`).

**Project Type**: librería `due_diligence` (coordinador y subagentes) que consume el servidor `servidor_mcp`.

**Performance Goals**: los tres frentes independientes se solapan: el caso dura lo del más lento de
ellos más el registro→listas, no la suma (Q5).

**Constraints**: sin credenciales en el repositorio (la clave llega por entorno o `.env`); solo datos
ficticios del #5; el código no controla el ciclo (FR-010); herramientas mínimas por agente (FR-002, FR-003).

**Scale/Scope**: un caso a la vez por `Caso`; cuatro frentes; cinco procesos del servidor por caso (R13).

## Constitution Check

*GATE: pasa antes de la investigación y se vuelve a comprobar tras el diseño.*

| Principio | Estado | Cómo |
|-----------|--------|------|
| I.1 (listas solo con comercio identificado) | Cumple en el orden; la garantía es del #7 | `delegar_frente(listas)` no se ejecuta sin una coincidencia única del registro (R4). Es orden de ejecución, no el mecanismo obligatorio: lo garantizan los hooks del #7 (II). |
| I.2, I.3 | No aplica al ticket | Las garantizan los hooks del #7; aquí no se escala ni se habilita. |
| I.4 (fuente en cada afirmación) | Cumple | El resultado de cada frente conserva `contenido` y `metadatos` del servidor, capturados de la llamada (R6). |
| I.5 (fuente caída no se presenta como completa) | Parcial, por diseño | Un frente no terminado figura como tal en el estado; una terminación anómala o el límite de seguridad quedan como eventos y no como fin normal (R5). La cobertura declarada es del #8. |
| II (garantizado vs. sugerido) | Cumple, con una desviación temporal | Aislamiento, herramientas por agente, orden de listas y clasificación del fin están en código y con tests. Lo que depende del modelo (pedir los tres frentes juntos) se declara como límite (R4, R13). **Desviación temporal**: el coordinador conserva `registrar_informe` y `escalar_a_cumplimiento` (FR-002), pre-aprobadas y sin guarda hasta los hooks del #7 (Complexity Tracking). |
| III (arquitectura) | Cumple | Coordinador + 4 subagentes, herramientas solo de su frente, contexto explícito, paralelo con listas tras el registro, ciclo por `stop_reason` sin contador ni búsqueda de texto, contenido separado de metadatos. El error estructurado del subagente es del #8; aquí se conserva lo obtenido. |
| IV | Cumple | Solo se consumen las fuentes por el servidor `pasarela`; las decisiones, solo por sus dos herramientas, que solo el coordinador tiene. |
| V | No aplica | El escalamiento con criterio es del #10. |
| VI (transparencia) | Cumple como base | El registro de eventos permite reconstruir delegaciones, inicio y fin de cada frente; la interfaz es del #11. |
| VII | Cumple | Solo datos del #5; los tests usan datos inventados y ejecutores simulados. |
| VIII | Cumple | La clave llega por entorno o `.env`; el código no contiene su nombre de archivo ni valores (R8). Los tests no cargan el `.env`. |
| IX | Cumple | Issue #6, rama propia, spec, plan y tareas antes del código. |
| X | Cumple | pytest junto al código, ruff tras cada edición, revisión previa en `/abrir-pr`. Los casos (a)–(g) completos son del #12. |

**Desviaciones**: una temporal, de II (Complexity Tracking).

**Re-evaluación tras el diseño**: sin cambios. El único punto que roza el principio III («no controlar
con un número fijo de iteraciones») es `max_turns`; la constitución lo permite como protección y el
issue lo exige documentado: vive en `configuracion.py`, con comentario, y su activación se clasifica
aparte (R5).

## Project Structure

### Documentation (this feature)

```text
specs/006-coordinador-subagentes-agent/
├── spec.md
├── plan.md              # este archivo
├── research.md          # R1 a R14
├── data-model.md
├── quickstart.md        # Q1 a Q7
├── contracts/
│   ├── delegacion.md    # herramienta delegar_frente y contexto por frente
│   └── caso.md          # API del caso: ejecutar_caso, estado, eventos, terminación
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/due_diligence/
├── __init__.py
├── __main__.py                  # punto de entrada manual; único que carga el entorno (R8)
├── configuracion.py             # modelos, nombres de herramientas, opciones_base, max_turns, cargar_entorno
├── frentes.py                   # los cuatro frentes: herramienta, instrucción, dependencia
├── contexto.py                  # construye el prompt de cada subagente desde la delegación
├── eventos.py                   # Evento y RegistroEventos
├── estado.py                    # EstadoCaso, ResultadoFrente, Consulta
├── terminacion.py               # clasificar(...) → Terminacion
├── ejecutor.py                  # EjecutorSubagente (protocolo) y EjecutorSDK
├── delegacion.py                # herramienta delegar_frente y servidor en proceso
├── coordinador.py               # Caso, ejecutar_caso, opciones del coordinador
├── sondeo_aislamiento.py        # sondeo manual con el modelo real (Q2)
├── test_configuracion.py
├── test_terminacion.py
├── test_eventos_estado.py
├── test_contexto.py
├── test_ejecutor.py             # captura de consultas y resultados con mensajes simulados
├── test_delegacion.py           # solape, dependencia, contexto, listas con representante
├── test_coordinador.py          # herramientas y opciones del coordinador y los subagentes
├── test_sin_control_propio.py   # R5: ni contadores ni búsqueda de texto
└── test_humo.py                 # ya existe
```

**Structure Decision**: todo en la librería `due_diligence`, que `pyproject.toml` ya declara como
módulo; cada `test_*.py` junto al módulo que prueba (CLAUDE.md). Un módulo por responsabilidad, para
que el #7 (hooks), el #8 (fallas) y el #11 (interfaz) amplíen sin reescribir.

## Complexity Tracking

Una desviación **temporal** del principio II, que cierran los hooks del #7:

| Desviación | Por qué hace falta | Alternativa descartada |
|------------|--------------------|------------------------|
| El coordinador tiene `registrar_informe` y `escalar_a_cumplimiento` (pre-aprobadas) y ningún hook las protege hasta el #7. Las reglas I.2 e I.3 (escalar con coincidencia en listas; nunca habilitar automáticamente una categoría de alto riesgo) y la obligación de no consultar listas sin comercio identificado (I.1) dependen entonces del orden en código (R4) y de la instrucción del coordinador. | FR-002 fija que el coordinador conserva las dos herramientas y los tickets #9 y #10 las usan. | Quitárselas al coordinador: contradice FR-002 y obligaría a rehacer el #9 y el #10. |

**Mitigación en este ticket** (instrucción, no garantía): las instrucciones del coordinador le prohíben llamar a esas dos herramientas (T019); Q5 y T033 comprueban que no hubo llamadas y que `resultados/` no tiene archivos nuevos. **Cierre**: los hooks del SDK del #7 (reglas I.1, I.2 e I.3). Hasta entonces el coordinador no se expone a un analista real: la interfaz es del #11.
