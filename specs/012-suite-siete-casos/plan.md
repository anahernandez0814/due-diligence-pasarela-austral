# Implementation Plan: Suite de los siete casos de prueba obligatorios

**Branch**: `012-suite-siete-casos` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/012-suite-siete-casos/spec.md` (aprobada en `86f2d75`)

## Summary

Una suite de punta a punta con el modelo real, `src/due_diligence/test_e2e_casos.py`, con un test
por caso (a)–(g):
- marcada `e2e` y excluida de `uv run pytest`;
- una fixture de sesión ejecuta en paralelo, en un solo bucle de eventos, **solo los casos
  seleccionados**, así que `-k caso_d` cuesta un caso;
- cada test recibe una `Observacion`: una proyección pura del caso (eventos, consultas, libro,
  registros de la pasarela y estado calculado) **sin ningún texto del modelo**;
- dos tests deterministas impiden que una verificación llegue al texto.

Además:
- la **interrupción de Streamlit** durante un hook (R9): se captura en el observador, el hook
  decide y su denegación sale, y la interrupción se relanza en cuanto el hook devuelve, cancelando
  el turno;
- la fuente «Diario Ficticio del Sur» en las noticias simuladas (R10);
- la sección «Pruebas» del README, una entrada de DECISIONES.md y T046 del #11.

## Technical Context

**Language/Version**: Python 3.12 (uv)

**Primary Dependencies**: `claude-agent-sdk` 0.2.168 y `streamlit` 1.66.0, sin cambios. **Ninguna
dependencia nueva**: sin `pytest-xdist` ni `pytest-asyncio` (R1).

**Storage**: los registros de la pasarela de cada caso e2e van a una carpeta temporal de pytest
(`PASARELA_RESULTADOS_DIR`), nunca a `resultados/`.

**Testing**:
- **pytest, dos grupos**: el determinista (`uv run pytest`, sin clave) y el `e2e`
  (`uv run pytest -m e2e -rs`, con la clave y el modelo real);
- **ruff**.

**Target Platform**: el equipo de la analista (Windows), y cualquier equipo con `uv`.

**Project Type**: paquete Python (coordinador, subagentes, servidor MCP, chat y línea de comandos).

**Performance Goals**: cada grupo en menos de 5 minutos.
- Determinista: 4:24 y 4:38 en dos mediciones antes del ticket, con poco margen (R11).
- e2e: el caso más lento más el arranque. **Medido**: 85 s y 1,10 USD con los 7 a la vez (T027).
- Determinista al final: 4:37 con 4781 tests (T031).

**Constraints**:
- **Presupuesto**: como máximo dos ejecuciones e2e completas, de ≈ 1 a 2,5 USD cada una.
- **Verificaciones**: nunca sobre el texto del modelo.
- **Entorno**: nada modifica `os.environ` salvo la carga de `.env` sin pisar nada.

**Scale/Scope**: módulos nuevos `observacion.py` y `conftest.py`, con sus tests; `test_e2e_casos.py`
(7 tests). Cambios pequeños en `eventos.py`, `hooks.py` (`fallar_cerrado`), `coordinador.py`
(`_turno`), `chat.py` y `simulacion.py`, más `pyproject.toml`, el README, DECISIONES.md y el
`tasks.md` del #11.

## Constitution Check

*GATE: antes de la fase 0 y otra vez tras el diseño.* **Cumple, sin desviaciones.**

| Principio | Cómo se cumple |
|-----------|----------------|
| **I.1–I.5** | Ninguna regla cambia. **I.1 e I.2 se refuerzan**: con R9, la denegación sale aunque la interfaz se interrumpa durante el hook. La suite e2e verifica I.1 (casos d y e, y el orden registro → listas en todos), I.2 (casos a y c sin `habilitar`), I.3 (caso a), I.4 (caso g, conflicto con las dos fuentes) e I.5 (caso f, cobertura declarada en el informe). |
| **II** | La garantía de R9 está en código, con tests sin modelo. FR-003 («nunca el texto») también, con dos tests deterministas (R7). |
| **III** | Sin cambios en la arquitectura. Un turno interrumpido termina por cancelación, y se clasifica `ANOMALA`; no hay un número fijo de iteraciones ni búsqueda de palabras. |
| **IV** | Sin cambios en el servidor. Las verificaciones leen lo que registró la pasarela a través de `registrar_informe` y `escalar_a_cumplimiento`. |
| **V** | La suite lo verifica: (a) y (c) escalan con su causa, (b) no escala y recibe `habilitar`, y (d) pide el identificador. |
| **VI** | El chat deja el turno interrumpido en el historial (R9). |
| **VII** | Solo los comercios ficticios del #5 y los mensajes del quickstart del #11. |
| **VIII** | La clave sale de `.env` con `cargar_entorno()` y `comprobar_credencial()`, las mismas funciones que el chat y `__main__`. Sin la clave, los tests se omiten sin llamar al modelo. Claude Code no lee `.env`: lo lee pytest al ejecutarse. |
| **IX** | Issue #12, rama propia, spec, plan y tareas antes del código. |
| **X** | Es el objetivo del ticket: los casos (a)–(g) de punta a punta, con tests junto al código y ruff. La revisión y la auditoría van en `/abrir-pr`. |

**Auditoría de `/abrir-pr`**: aplican I.1–I.5, porque el diff toca `hooks.py`, `eventos.py` y
`coordinador.py`.

**Re-evaluación tras el diseño**: sin cambios. Lo que se apoya en lectura y no en medición (el
orden de escritura del SDK en R9 y el comportamiento de `-m` en R4) está declarado y tiene su test o
su comprobación en la implementación.

## Decisiones (detalle en [research.md](research.md))

1. **R1, en paralelo y por debajo de 5 minutos**: una fixture de sesión con `asyncio.gather` en un
   solo `asyncio.run`.
   - Semáforo `PASARELA_E2E_PARALELO`, por defecto 7.
   - `asyncio.timeout(240)` por caso, para que un caso colgado no pase el grupo de 5 minutos.
   - `return_exceptions=True`: un fallo no tumba a los demás.
   - **Trade-off**: una fixture propia en vez de `pytest-xdist`, a cambio de no añadir dependencias
     y de sumar el coste en un solo sitio. Con 7 casos a la vez conviven unos 28 procesos del CLI
     (en T027 no hubo problemas de memoria: 85 s).
2. **R2, límite de tasa**: la suite no reintenta, porque ya reintenta el CLI. Si se agota, el turno
   queda `ANOMALA` y el test falla con la clasificación, el coste y el `-k` para repetirlo. Si se
   repite, se baja a `PASARELA_E2E_PARALELO=3`; el README advierte que así puede pasar de 5
   minutos.
3. **R3, un solo caso**: la fixture ejecuta solo los casos de los tests que quedaron tras `-k` y
   `-m` (`request.session.items`). `-k caso_d` cuesta un caso y no gasta una ejecución completa;
   también funciona `--lf`.
4. **R4, la marca**: `markers` y `-m "not e2e"` en `addopts`. El grupo se pide con `-m e2e`, porque
   el último `-m` gana. Un test determinista fija la configuración.
5. **R5, la credencial y el entorno**:
   - la credencial pasa por `cargar_entorno()` y `comprobar_credencial()`; si falla, cada test
     e2e se omite con el motivo, visible con `-rs`;
   - cada caso recibe su `entorno`: una copia de `os.environ` sin los modos de simulación, con su
     carpeta temporal de registros y, solo en el (e) y el (f), su modo.
6. **R6, `Observacion`**: `observacion.py` puro.
   - Proyecta eventos (sin `detalle`), consultas (solo los argumentos que identifican), el libro,
     los registros de la pasarela (recomendación, cobertura, conflictos y causas) y el estado
     calculado (cobertura, `completo`, espera y comercio), más el coste y la duración.
   - Se prueba sin modelo con los siete casos simulados.
7. **R7, comprobar sin modelo que no se lee el texto**:
   - **(1)** los campos de `Observacion` son un conjunto cerrado, sin ningún nombre de texto libre,
     y una marca única puesta en la respuesta y en los textos simulados no aparece en
     `repr(observacion)`;
   - **(2)** un análisis AST de `test_e2e_casos.py`: solo importa `pytest` y `observacion`, no nombra
     `Caso`, `respuesta`, `detalle`, `resumen`, `hallazgos`, `accion_recomendada`, `texto` ni
     `mensajes`, y no busca subcadenas.
8. **R8, coste y tiempo**: `pytest_terminal_summary` en `src/due_diligence/conftest.py` imprime una
   línea por caso y el total. El coste es aproximado, como en `__main__`.
9. **R9, la interrupción de Streamlit (FR-008)**:
   - **Qué se captura**: solo las clases que declara el punto de entrada. El chat declara
     `ScriptControlException` (`StopException` y `RerunException`, que heredan de `BaseException`).
     `eventos.py` no importa Streamlit.
   - **Dónde**:
     - **punto principal**, en `RegistroEventos.registrar`, alrededor del observador (la única
       llamada `st.*` durante un turno): guarda **la primera** interrupción, apaga el observador y
       deja que el hook siga y decida;
     - **cinturón**, en `fallar_cerrado`: si una interrupción escapara del cuerpo del hook, el hook
       falla cerrado (`PreToolUse` deniega), sin sellar.
   - **Cuándo se relanza**: en cuanto el hook devuelve su decisión.
     - `fallar_cerrado` sabe, por una `ContextVar`, que está dentro de un hook. Al devolver llama a
       `interrumpir()`, que programa con `call_soon` la cancelación del turno.
     - La escritura del SDK **cede una vez**: `_write_lock` es un `anyio.Lock()` sin
       `fast_acquire` (`subprocess_cli.py:253`), y su `acquire` cede en
       `anyio/_backends/_asyncio.py:1963`. El orden se mantiene porque `cancel()` solo programa
       que el turno despierte, y ese despertar queda detrás de la reanudación del hook, que escribe
       la respuesta. El test de `test_coordinador.py` escribe la decisión a través de un
       `anyio.Lock()` que cede igual, para fijar el orden real.
     - `Caso._turno` convierte la cancelación en la interrupción guardada: el turno queda
       `ANOMALA` (`interrumpido por la interfaz`) y se relanza el mismo objeto.
     - `chat.py` guarda el turno como interrumpido, **quita el mensaje pendiente** para que no se
       repita solo, y relanza. Fuera de un hook, se cancela en el momento.
     - Hay que relanzar **el mismo objeto**, porque Streamlit entrega `RERUN` una sola vez: si se
       traga, la recarga se pierde.
   - **Por qué `CancelledError` queda fuera**:
     - es la cancelación cooperativa de `asyncio`; el SDK la usa cuando el CLI ya abandonó la
       petición y nadie espera una decisión (`query.py:686`);
     - tragarla deja tareas vivas, cuelga `timeout` y `TaskGroup`, y rompe el propio corte del
       turno de R9;
     - es la decisión del #8 en `fallar_cerrado`. `KeyboardInterrupt` y `SystemExit` siguen igual.
   - **Trade-off**: unas 40 líneas en cuatro módulos auditados, a cambio de que la denegación salga
     siempre, el «Stop» corte en segundos y la recarga no se pierda. Descartadas: tragar
     `BaseException`, relanzar al final del turno y dibujar desde otra tarea.
   - **Tests sin modelo** en `test_eventos_estado.py`, `test_hooks.py` (I.1 e I.2),
     `test_coordinador.py` (una tarea suelta y un `anyio.Lock()` como los del SDK, con la
     interrupción en menos de 2 s) y `test_chat.py` (`StopException`, pendiente quitado, jerarquía
     de Streamlit fijada).
   - **El mensaje siguiente a una interrupción (decisión de la analista, opción A)**: abre un caso
     nuevo con un aviso visible («El turno anterior se interrumpió; se inició un caso nuevo.»), con
     el caso nuevo del #11. Nunca reanuda una sesión cortada a mitad de una herramienta.
     `Caso.interrumpido` lo marca y `decidir_mensaje` lo mira primero.
     - **Trade-off**: el analista vuelve a escribir el nombre del comercio. Es un caso raro, y a
       cambio nunca se continúa una sesión cuyo estado en el CLI no está medido.
     - Va a DECISIONES.md en una línea.
     - Tiene su test en `test_chat.py` y en `test_presentacion.py`.
10. **R10, la fuente de noticias simulada**: `FUENTE_NOTICIAS = "Diario Ficticio del Sur"`, y
    `respuesta_noticias` devuelve «sin coincidencias» con esa fuente en vez de `None`.
11. **R11, el tiempo determinista**: se mide con `--durations` tras la implementación. Si pasa de
    4:45, se aceleran los tests más lentos sin quitar aserciones, o se declara la desviación.
12. **R12, documentación**:
    - README, sección «Pruebas»: comandos, tiempos, coste, «skipped» no es «pasó», `-k` y
      `PASARELA_E2E_PARALELO`;
    - DECISIONES.md: una sola entrada corta;
    - T046 del #11.

## Riesgos residuales

1. **Variación del modelo**: un caso puede fallar por un camino válido. La verificación se ajusta a
   lo que garantiza el sistema y se anota; no se reintenta a ciegas.
2. **El caso (e)**: si el modelo no intenta consultar listas, no hay bloqueo que verificar y el test
   falla, como pide la analista. Si pasa en las dos ejecuciones, se decide con la analista si se
   declara una desviación.
3. **R9 se apoya en la lectura del SDK 0.2.168 y de anyio**, por el orden entre escribir la
   respuesta y despertar el turno cancelado. El test lo fija con un `anyio.Lock()` como el del SDK,
   pero no con el transporte real. Si la escritura se cortara, el CLI se cierra en el mismo
   momento, ninguna acción llega a ejecutarse y el bloqueo ya está en la traza.
4. **Memoria con 7 casos a la vez**: si no alcanza, se baja `PASARELA_E2E_PARALELO` y el tiempo
   puede pasar de 5 minutos. En T027 no hubo problemas, con 85 s.
5. **Coste aproximado**: un frente delegado dos veces cuenta su última ejecución.
6. **El tiempo determinista**, cerca de 5 minutos (R11).

## Lo pendiente fuera de alcance (para DECISIONES.md y el #14)

- US3-9 del #10 (decisión de la analista).
- Las demás sugerencias de los PR #26 y #27.
- D7 del #9, `RESUMEN_REGISTRO_CAIDO` y el evento de espera con el registro sin delegar.
- El caso (b) de noche (T043 del #11).
- Integración continua con el modelo real y repeticiones para medir la estabilidad.
- Para DECISIONES.md, una línea: tras un turno interrumpido, el siguiente mensaje abre un caso nuevo
  (opción A).

## Project Structure

### Documentation (this feature)

```text
specs/012-suite-siete-casos/
├── plan.md
├── research.md          # R1–R12
├── data-model.md        # Observacion y la interrupción
├── quickstart.md        # Q1–Q5
├── contracts/
│   └── suite-e2e.md     # comandos, los siete tests y la interrupción
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml                          # marca e2e y -m "not e2e" (R4)
README.md                               # sección «Pruebas» (R12)
DECISIONES.md                           # entrada del #12
specs/011-interfaz-chat/tasks.md        # T046
src/due_diligence/
├── observacion.py                      # NUEVO: Observacion y observar() (R6)
├── test_observacion.py                 # NUEVO: los siete casos simulados y los guardas de R7
├── conftest.py                         # NUEVO: fixture de sesión e2e y resumen de coste (R1, R3, R5, R8)
├── test_e2e_casos.py                   # NUEVO: los siete tests e2e
├── test_configuracion_pytest.py        # NUEVO: la marca registrada y excluida (R4)
├── eventos.py · test_eventos_estado.py # interrupciones, interrupcion, interrumpir (R9)
├── hooks.py · test_hooks.py            # fallar_cerrado: ContextVar, cinturón y aviso (R9)
├── coordinador.py · test_coordinador.py# _turno: cancelación → interrupción (R9)
├── chat.py · test_chat.py              # declara ScriptControlException; pendiente quitado; opción A (R9)
├── presentacion.py · test_presentacion.py # decidir_mensaje: caso interrumpido → caso nuevo (R9)
└── simulacion.py · test_sesion_simulada.py # FUENTE_NOTICIAS (R10)
```

**Structure Decision**: un solo paquete, con los tests junto al código, como en los tickets
anteriores. El `conftest.py` va en `src/due_diligence/` porque solo lo usan los tests e2e de ese
paquete.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
