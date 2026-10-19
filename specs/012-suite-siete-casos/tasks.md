---

description: "Lista de tareas del ticket #12, suite de los siete casos de prueba obligatorios"
---

# Tasks: Suite de los siete casos de prueba obligatorios

**Input**: documentos de diseño en `specs/012-suite-siete-casos/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/suite-e2e.md](contracts/suite-e2e.md) y [quickstart.md](quickstart.md).

**Prerequisites**: spec en `86f2d75` y plan en `4771b03`, con los dos ajustes de la analista: la escritura del SDK cede una vez en su candado, y tras una interrupción se abre un caso nuevo (opción A).

**Tests**: obligatorios (constitución X, SC-002, SC-003, SC-005 y SC-006).
- Los deterministas van junto a cada módulo (`src/due_diligence/test_*.py`) y se escriben antes que el código: deben fallar primero.
- Ningún test determinista llama al modelo ni carga el archivo de entorno.
- Los únicos que llaman al modelo son los siete de `test_e2e_casos.py`, con la marca `e2e`.

**Organization**: ritmo liviano, sin paradas de revisión intermedias. Se construye de corrido hasta el barrido (T030) y **se detiene antes de `/abrir-pr`**.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La verificación del cierre del #12 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US4).
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md) o Q# del [quickstart](quickstart.md).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Solo datos ficticios** del #5: `CO-TV-0001` (a), `CO-TA-0002` (b, f), `CO-PL-0003` (c), `CO-AM-0004` y `CO-AM-0005` (d, e) y `CO-RF-0006` (g). La clave de los tests es `"clave-ficticia-de-prueba"`. Sin secuencias de 6 o más dígitos seguidos (VII).
- **Todo en español**: mensajes, avisos, nombres de tests y documentación.
- **Ninguna regla de negocio cambia**. Los hooks solo cambian en `fallar_cerrado`, por R9.
- **Nada lee el texto del modelo** en la suite e2e: solo `Observacion` (R6, R7).
- **Nada modifica `os.environ`** en los tests, salvo la carga de `.env` sin pisar nada en la fixture e2e (R5).
- **Presupuesto e2e**: **como máximo dos ejecuciones completas** (T027 y T028), cada una con su fecha, tiempo, coste y resultado anotados. Las repeticiones con `-k` se anotan aparte, en T029.
- Tras cada edición, `uv run ruff format .` y `uv run ruff check .`.

---

## Phase 1: Setup

- [x] T001 Commitear `specs/012-suite-siete-casos/tasks.md` (con las correcciones del analyze, si las hay) junto con cualquier ajuste de la spec o del plan que provoque, en el mismo commit.
- [x] T002 Línea base: `uv run pytest` (4711 en verde, medido el 2026-10-19) y ruff limpio. **Resultado**: 4711 en verde en 264 s y 278 s (dos mediciones), ruff limpio.

---

## Phase 2: Foundational (bloquea US1 y US2)

- [x] T003 [P] Escribir `src/due_diligence/test_configuracion_pytest.py` (R4), que debe fallar primero:
  - `pyproject.toml` (con `tomllib`) registra la marca `e2e` en `[tool.pytest.ini_options].markers`, y `addopts` contiene `-m` y `not e2e`;
  - con **un solo subproceso**, `python -m pytest --collect-only -q src/due_diligence/test_e2e_casos.py`, la selección por defecto no recoge ningún test (P1 del analyze: cada subproceso cuesta segundos en una suite cerca de 5 minutos). Que `-m e2e` selecciona los siete lo prueba el subproceso de T010.
- [x] T004 Marca `e2e` en `pyproject.toml` (R4): `markers = ["e2e: casos (a)–(g) de punta a punta con el modelo real; consume API (uv run pytest -m e2e -rs)"]` y `-m "not e2e"` en `addopts`. T003 en verde cuando exista T009.

---

## Phase 3: User Story 1 — Los siete casos de punta a punta (Priority: P1) 🎯 MVP

**Goal**: un test por caso (a)–(g), en paralelo, que solo ve `Observacion` (FR-001, FR-002, FR-003, FR-005).

**Independent Test**: sin modelo, `test_observacion.py` proyecta los casos simulados y los guardas de R7 pasan; con la clave, `uv run pytest -m e2e -rs` pasa los siete (T027).

### Tests de US1 (antes que el código)

- [x] T005 [P] [US1] Escribir `src/due_diligence/test_observacion.py`, parte 1 (R6). Con `CoordinadorSimulado`, `EjecutorSimulado` y `PasarelaSimulada`, reutilizando los guiones de `test_casos_escalamiento.py`, `test_casos_informe.py` y `test_casos_reglas.py` (sin duplicarlos: se importan o se factorizan a un ayudante común):
  - **(a)**: un `EscalamientoObservado` con `alto_riesgo`, un `InformeObservado` `decide_cumplimiento` y ningún `habilitar`;
  - **(b)**: un `habilitar`, cero escalamientos, cuatro frentes `cubierto` y `completo`;
  - **(d)**, turno 1: `espera == EsperaObservada("identificador", MOTIVO_ESPERA_IDENTIFICADOR)`, una consulta del registro con `clase_registro == "varias"` y cero `consultas_listas`;
  - **(d)**, turno 2 con `CO-AM-0004`: `comercio.identificador == "CO-AM-0004"` y listas consultadas;
  - **(f)**: `InformeObservado.cobertura == observacion.cobertura_lineas` y `cobertura["noticias"].cubierto is False`;
  - **(g)**: un `ConflictoObservado("fecha_constitucion", …)` con dos pares `(valor, fuente)` distintos;
  - **(e)**, con `modo_demostracion`: un `EventoObservado` con `regla == "I.1"`.
- [x] T006 [P] [US1] `test_observacion.py`, parte 2, los guardas de FR-003 (R7, SC-002):
  - los nombres de los campos de `Observacion` y de cada parte son un conjunto cerrado, comparado con igualdad exacta con el de [data-model.md](data-model.md);
  - con un `CoordinadorSimulado` cuya respuesta, resumen de subagente, hallazgos y `accion_recomendada` llevan la marca `«TEXTO-LIBRE-12»`, `repr(observacion)` no la contiene;
  - un análisis AST de `src/due_diligence/test_e2e_casos.py` comprueba que:
    - solo importa `pytest` y `due_diligence.observacion`;
    - no aparece ningún `Name`, `Attribute` ni constante de cadena igual a `Caso`, `respuesta`, `detalle`, `resumen`, `hallazgos`, `accion_recomendada`, `texto` o `mensajes`;
    - no hay llamadas a `startswith`, `endswith`, `find`, `re.*` ni `in` sobre algo que no sea una colección de la observación.

    El guarda tiene su propio test de mutación: un fragmento con `observacion.respuesta` lo hace fallar.

### Implementación de US1

- [x] T007 [US1] `src/due_diligence/observacion.py` (R6, [data-model.md](data-model.md)):
  - las clases inmutables `Observacion`, `EventoObservado`, `ConsultaObservada`, `ConsultaListasObservada`, `EscalamientoObservado`, `InformeObservado`, `ConflictoObservado`, `FrenteObservado`, `EsperaObservada`, `ComercioObservado`, `Metricas` y `Registros`;
  - `observar(caso, registros, duracion_s)` y `leer_registros(carpeta)`, que lee `informes/*.json` y `escalamientos/*.json` en orden de nombre;
  - las reglas del data-model, citadas literalmente: «Nada del modelo: no se copian `respuesta`, `detalle`, `resumen`, `hallazgos`, `accion_recomendada` ni los mensajes del analista» y «Las cadenas que sí se leen son constantes del código».

  `EscalamientoObservado` empareja por orden las causas de `libro.escalamientos` con los `id` de los registros. Si los números difieren, `Observacion.registros_coherentes` es falso y todo test e2e lo comprueba (U2 del analyze).

  Reexporta `MOTIVO_ESPERA_IDENTIFICADOR` y las etiquetas de causa (`CAUSA_ALTO_RIESGO`, `CAUSA_COINCIDENCIA_REPRESENTANTE`) para que el test e2e solo importe `observacion`. El coste se calcula como en `__main__.py:149-155`. T005 en verde.
- [x] T008 [US1] `src/due_diligence/conftest.py` (R1, R3, R5, R8):
  - **fixture de sesión `ejecuciones`**:
    - lee los casos seleccionados de `request.session.items` (los tests con la marca `e2e`; la letra sale del nombre `test_caso_<letra>_…`);
    - comprueba la credencial (`cargar_entorno()` y `comprobar_credencial()`) y, si falla, devuelve el motivo sin crear ningún caso;
    - ejecuta los casos con `asyncio.gather(..., return_exceptions=True)` en un `asyncio.run`, con un `asyncio.Semaphore` de `PASARELA_E2E_PARALELO` (por defecto 7) y `asyncio.timeout(240)` por caso;
    - cada `Caso(entorno=…)` recibe una copia de `os.environ` sin `PASARELA_FALLA_NOTICIAS`, `PASARELA_FALLA_REGISTRO`, `PASARELA_MODO_DEMO_HOOKS` ni `PASARELA_RESULTADOS_DIR`, con su carpeta de `tmp_path_factory` y su modo;
    - guarda una `Observacion` por turno, o el error con la última terminación y el `-k` para repetirlo (R2);
  - **fixture `caso_e2e(letra)`**: hace `pytest.skip(motivo)` si no hay credencial; si no, devuelve las observaciones del caso o falla con el error;
  - **`pytest_terminal_summary`**: una línea por caso ejecutado, `e2e caso (x): 0,21 USD, 96 s`, y el total.

  Sin efectos en el grupo determinista: si ningún test seleccionado tiene la marca `e2e`, la fixture no se usa.
- [x] T009 [US1] `src/due_diligence/test_e2e_casos.py`: los siete tests de [contracts/suite-e2e.md](contracts/suite-e2e.md), con `@pytest.mark.e2e` y los mensajes de la tabla Q4 del quickstart del #11, el (e) con el mensaje literal de la analista. Nombres:
  - `test_caso_a_alto_riesgo`;
  - `test_caso_b_bajo_riesgo`;
  - `test_caso_c_representante`;
  - `test_caso_d_dos_turnos`;
  - `test_caso_e_listas_sin_identificar`;
  - `test_caso_f_noticias_caido`;
  - `test_caso_g_fechas_distintas`.

  Cada uno comprueba también US1-8: ninguna consulta de listas antes de una consulta del registro con `clase_registro == "unica"`. Los mensajes de las aserciones dicen qué evento o qué llamada faltó. T006 y T003 en verde.

**Checkpoint**: `uv run pytest` en verde y sin ningún `e2e` seleccionado.

---

## Phase 4: User Story 2 — Dos grupos por separado (Priority: P1)

**Goal**: el grupo determinista sin clave y el e2e con la omisión visible (FR-004, FR-007).

**Independent Test**: Q1 y Q2 del quickstart.

- [x] T010 [P] [US2] Dos tests de US2-3 (U1 y H1 del analyze):
  - **Unitario**, en `src/due_diligence/test_configuracion_pytest.py`: la función de `conftest.py` que prepara las ejecuciones (`preparar_ejecuciones(letras, entorno, crear_caso)` o equivalente), con un entorno sin `ANTHROPIC_API_KEY`, devuelve el mensaje de `comprobar_credencial` y no llama a un `crear_caso` espía.
  - **Un solo subproceso**: `python -m pytest -m e2e -rs -p no:cacheprovider src/due_diligence/test_e2e_casos.py` con un entorno **sin `ANTHROPIC_API_KEY` y con `ANTHROPIC_AUTH_TOKEN="token-ficticio-de-prueba"`**. `comprobar_credencial` rechaza esa combinación siempre, aunque exista un `.env` con la clave (que no pisa nada), así que **el subproceso nunca puede llamar al modelo**. Comprueba que la salida tiene `7 skipped` y el motivo en las líneas `SKIPPED`.
- [x] T011 [US2] Ajustar `conftest.py` hasta que T010 pase: el motivo de la omisión es el texto de `comprobar_credencial`, sin trazas.

---

## Phase 5: User Story 3 — El hook sigue negando aunque se interrumpa la interfaz (Priority: P1)

**Goal**: FR-008, R9, SC-005 y la opción A.

**Independent Test**: los tests de T012–T016 en verde, sin modelo.

### Tests de US3 (antes que el código)

- [x] T012 [P] [US3] En `src/due_diligence/test_eventos_estado.py`, con una `class Interrupcion(BaseException)` de prueba declarada en `interrupciones`:
  - `registrar` devuelve el evento, guarda la primera interrupción en `interrupcion`, no vuelve a llamar al observador y, fuera de un hook, llama a `al_interrumpir` una vez;
  - una segunda interrupción no reemplaza a la primera;
  - `asyncio.CancelledError` y `KeyboardInterrupt` lanzadas por el observador se propagan;
  - `Exception` se sigue ignorando (#11);
  - sin `interrupciones` declaradas, `Interrupcion` se propaga como hoy.
- [x] T013 [P] [US3] En `src/due_diligence/test_hooks.py`:
  - el `PreToolUse` de `delegar_frente` (listas) sin identificación, envuelto por `fallar_cerrado`, con un observador que lanza `Interrupcion`, devuelve **la denegación de I.1** (no `MOTIVO_FALLO_DE_HOOK`) y `al_interrumpir` se llama una vez, después de decidir;
  - lo mismo con el `PreToolUse` de `registrar_informe` con `habilitar` en un caso con coincidencia en listas (I.2);
  - si el cuerpo del hook lanza `Interrupcion`, `PreToolUse` deniega con `MOTIVO_FALLO_DE_HOOK`, `libro.fallo_de_hook` sigue en `None` y `al_interrumpir` se llama;
  - una `CancelledError` del cuerpo se propaga sin denegación ni sello.
- [x] T014 [P] [US3] En `src/due_diligence/test_coordinador.py`, un `Caso(interrupciones=(Interrupcion,), observador=…)` con una `consulta` falsa que, como el SDK, lanza en una **tarea suelta** (`asyncio.get_running_loop().create_task`) el `PreToolUse` del coordinador para `delegar_frente` (listas) sin identificación. Esa tarea escribe la decisión en una lista **a través de un `anyio.Lock()`** (cede como el `_write_lock` del SDK, `subprocess_cli.py:253`), y la consulta luego espera 60 s:
  - `ejecutar` lanza **el mismo objeto** `Interrupcion` en menos de 2 s (`asyncio.timeout`);
  - la decisión escrita es la denegación de I.1;
  - `caso.terminacion.terminacion is Terminacion.ANOMALA` con `interrumpido por la interfaz`;
  - `caso.interrumpido` es verdadero y `caso.completo` es falso;
  - sin interrupción, cancelar la tarea del turno desde fuera sigue dando `CancelledError` y `caso.interrumpido` es falso.
- [x] T015 [P] [US3] En `src/due_diligence/test_presentacion.py`: `decidir_mensaje` con un caso `interrumpido` y un texto no vacío devuelve `Decision.NUEVO` con `AVISO_TURNO_INTERRUMPIDO` («El turno anterior se interrumpió; se inició un caso nuevo.»), también si el caso espera al analista. Con texto vacío, la regla de la espera no cambia.
- [x] T016 [P] [US3] En `src/due_diligence/test_chat.py`:
  - **jerarquía**: `StopException` y `RerunException` de `streamlit.runtime.scriptrunner_utils.exceptions` heredan de `ScriptControlException`, que hereda de `BaseException` y no de `Exception`;
  - **turno interrumpido**: con `AppTest` y un `crear_caso` simulado cuyo turno lanza `StopException`, la ejecución termina sin traza, no queda `pendiente` y el historial guarda el turno como interrumpido;
  - **opción A**: el siguiente mensaje llama otra vez a `crear_caso` (caso nuevo) y la conversación muestra `AVISO_TURNO_INTERRUMPIDO`;
  - **declaración**: `chat._caso_real` crea el `Caso` con `interrupciones=(ScriptControlException,)`.

### Implementación de US3

- [x] T017 [US3] `src/due_diligence/eventos.py` (R9). `RegistroEventos(reloj, observador, interrupciones=())` con:
  - el atributo `interrupcion`, solo la primera;
  - `al_interrumpir: Callable[[], None] | None`;
  - `interrumpir()`, que llama a `al_interrumpir` una sola vez;
  - una `ContextVar` `DENTRO_DE_HOOK`, que exporta el módulo para `hooks.py`;
  - en `registrar`, `except self._interrupciones`: guarda, apaga el observador y, si no está `DENTRO_DE_HOOK`, llama a `interrumpir()`. `except Exception` se mantiene.

  Comentario que explique por qué `CancelledError` queda fuera. T012 en verde.
- [x] T018 [US3] `src/due_diligence/hooks.py`, en `fallar_cerrado` (R9):
  - pone `DENTRO_DE_HOOK` mientras corre el hook;
  - atrapa también `eventos.interrupciones` del cuerpo: en `PreToolUse` deniega con `MOTIVO_FALLO_DE_HOOK` sin sellar; en los demás tipos, permite;
  - si al terminar hay `eventos.interrupcion`, llama a `eventos.interrumpir()` antes de `return`.

  Se actualiza el docstring («Atrapa `Exception`, no `BaseException`…») con la excepción de las interrupciones declaradas. T013 en verde.
- [x] T019 [US3] `src/due_diligence/coordinador.py` (R9):
  - `Caso(..., interrupciones=())`, que pasa a `RegistroEventos`;
  - en `_turno`, `al_interrumpir = lambda: loop.call_soon(tarea.cancel)` con la tarea actual;
  - `except asyncio.CancelledError`: solo si hay `interrupcion`, hace `uncancel()`, clasifica `Clasificacion(Terminacion.ANOMALA, None, None, "interrumpido por la interfaz", True)`, llama a `_terminar` y relanza la interrupción guardada; si no, relanza la `CancelledError`;
  - la propiedad `interrumpido`.

  T014 en verde.
- [x] T020 [US3] `src/due_diligence/presentacion.py` y `src/due_diligence/chat.py` (R9, opción A):
  - `AVISO_TURNO_INTERRUMPIDO`, y `decidir_mensaje` mira `caso.interrumpido` antes que `completo`;
  - `_caso_real` pasa `interrupciones=(ScriptControlException,)`;
  - `_ejecutar_turno` atrapa `ScriptControlException` alrededor de `asyncio.run`: guarda el turno como interrumpido (con `presentacion.resumen_del_turno` y una respuesta fija, `MENSAJE_TURNO_INTERRUMPIDO`), quita `pendiente` y relanza.

  T015 y T016 en verde.

**Checkpoint**: `uv run pytest` en verde.

---

## Phase 6: User Story 4 — Correcciones pendientes (Priority: P3)

- [x] T021 [P] [US4] Test en `src/due_diligence/test_sesion_simulada.py`, que debe fallar primero: el `EjecutorSimulado` sin resultado de noticias, para un comercio que N-0001 no menciona, devuelve una consulta con `metadatos == {"fuentes": ["Diario Ficticio del Sur"], "fecha": FECHA}` y sin hechos (FR-009, R10).
- [x] T022 [US4] `src/due_diligence/simulacion.py`: `FUENTE_NOTICIAS = "Diario Ficticio del Sur"`, usado en N-0001 y en la respuesta sin mención de `respuesta_noticias`, que ya no devuelve `None`. Buscar con `grep` los tests que dependían de la fuente anterior en noticias y adaptarlos con igualdades exactas; listarlos en la tabla «Tests adaptados» de abajo. T021 en verde y la suite completa en verde.
- [x] T023 [P] [US4] Marcar T046 en `specs/011-interfaz-chat/tasks.md` (FR-010), con una nota: PR #27 fusionado el 2026-10-19.

---

## Phase 7: Documentación

- [x] T024 [P] `README.md`, sección «Pruebas» (FR-007, R12), que reemplaza o amplía «Verificar el entorno»:
  - los dos grupos: `uv run pytest` (sin clave, sin coste, con el tiempo medido en T031) y `uv run pytest -m e2e -rs` (con la clave, el tiempo y el coste de T027/T028);
  - repetir un caso con `-k caso_d` y con `--lf`;
  - `PASARELA_E2E_PARALELO` y la advertencia de que con menos de 7 puede pasar de 5 minutos;
  - **«skipped» no significa que pasó**;
  - las e2e escriben en carpetas temporales, no en `resultados/`;
  - el coste es aproximado.
- [x] T025 [P] `DECISIONES.md`: una sola entrada corta del #12 (R12) que remita al plan. Recoge:
  - la suite e2e en paralelo con `Observacion` como frontera;
  - la interrupción de Streamlit (R9);
  - la opción A, en una línea;
  - US3-9 del #10 fuera de alcance;
  - lo pendiente: las sugerencias de los PR #26 y #27, D7, `RESUMEN_REGISTRO_CAIDO`, el evento de espera con el registro sin delegar y el caso (b) de noche.
- [x] T026 Commit de las fases 2 a 7 (en uno o varios commits por historia, con `(#12)` en el mensaje). `uv run pytest` en verde y ruff limpio antes de cada commit.

---

## Phase 8: Validación con el modelo real y barrido

- [x] T027 Primera ejecución completa de la suite e2e (Q3): `uv run pytest -m e2e -rs`. Anotar aquí la fecha, el tiempo total (`time`), el coste total y por caso (resumen de `conftest`), y el resultado de cada caso.
- [x] T028 Solo si T027 no pasó entera y se corrigió algo que afecta a varios casos: segunda y **última** ejecución completa, anotada igual. Si un caso falla por un camino válido del modelo, se ajusta la verificación a lo que garantiza el sistema (eventos), se anota en `research.md` como R13 y, si choca con un FR, se declara como «Desviación justificada» en spec, plan y tareas, en el mismo commit.
- [x] T029 Repeticiones con `-k` (no cuentan como ejecución completa): cada una con su caso, su motivo, su tiempo y su coste.
- [x] T030 Barrido previo a `/abrir-pr`:
  - `uv run ruff format --check .` y `uv run ruff check .`;
  - `uv run pytest` en verde;
  - análisis de los tests tocados por la rama: ninguno vacío, sin aserciones, ni con `skip` o `xfail` incondicional (los `skip` condicionados a la credencial de `conftest.py` sí, con su motivo);
  - todas las tareas marcadas salvo T032;
  - spec, plan, research, contrato, quickstart, README y DECISIONES coherentes con lo construido;
  - un commit `barrido previo a /abrir-pr del #12`.
- [x] T031 Medir la suite determinista al final: `uv run pytest -q --durations=25` (R11). Anotar aquí el número de tests, el tiempo y los diez más lentos. Si pasa de 4:45, acelerar los más lentos sin quitar aserciones o declarar la desviación. El tiempo va al README (T024).
  **Resultado (2026-10-19)**: 4781 en verde y 7 deseleccionados, en **277,8 s (4:37)**; otra ejecución durante la construcción dio 4:30. Está por debajo de 4:45, así que no se tocó ningún test. Los diez más lentos son todos de `.claude/hooks/`, en tests que crean repositorios git de prueba:
  - `test_preparar_revision.py`: `la_primera_linea_es_la_marca` 3,38 s (preparación) y seis más, de 1,92 a 1,98 s;
  - `test_guarda_pr.py`: `commit_sin_publicar_se_bloquea` 3,25 s y `mcp_sin_veredicto_se_bloquea` 2,02 s;
  - `test_veredicto.py`: `cli_con_el_commit_de_head_aprueba_como_siempre` 2,62 s.

  El margen sigue siendo poco, unos 20 s: es un riesgo para los próximos tickets.
- [ ] T032 **Detenerse** y entregar a la analista el resumen del barrido. `/abrir-pr` lo lanza ella. Ofrecerle como opcional la comprobación manual Q4 (interrupción con «Stop», con el coste de un caso) (G1 del analyze).

---

## Tests adaptados

| Test | Fijaba | Fija ahora | Por qué no se debilita |
|------|--------|------------|------------------------|
| `test_casos_informe.py::test_caso_g_un_conflicto_inventado_por_el_coordinador_no_queda` | La afirmación de noticias citaba «Registro Mercantil Ficticio del Sur» | La cita con `FUENTE_NOTICIAS` («Diario Ficticio del Sur») | Solo pasaba porque las noticias simuladas llevaban la fuente del registro (R10). Ahora la fuente es la del frente, como exige I.4; la aserción sobre los conflictos no cambia. |
| `test_sin_control_propio.py::test_cargar_entorno_solo_se_llama_desde_el_punto_de_entrada` | Lista exacta `["__main__.py", "chat.py"]` | Lista exacta `["__main__.py", "chat.py", "conftest.py"]` | La suite e2e es el tercer punto de entrada que lee la clave (R5), solo con `-m e2e`. La lista sigue siendo exacta: cualquier otro módulo que cargue el entorno la rompe. |
| `PasarelaSimulada._noticias` (no es un test; afecta a los casos simulados) | Sin mención: fuente «Noticias Ficticias» y una clave `coincidencias: []` | La respuesta de `respuesta_noticias`, con la fuente del diario y la forma del contrato real (sin `coincidencias`) | La suite completa siguió en verde: ningún test dependía de la fuente vieja salvo el de arriba. |

## Ejecuciones e2e

| Ejecución | Fecha | Tiempo | Coste | Resultado |
|-----------|-------|--------|-------|-----------|
| T027 | 2026-10-19 07:43 UTC | 85 s en total (83 s de pytest); el caso más lento, el (d), 82 s | 1,10 USD (a 0,16 · b 0,13 · c 0,18 · d 0,24 · e 0,09 · f 0,14 · g 0,15) | **7 de 7 pasaron**; 7 casos a la vez, sin límite de tasa ni reintentos |
| T028 | — | — | — | No hizo falta: T027 pasó entera. Queda sin gastar la segunda ejecución del presupuesto. |
| Repeticiones `-k` (T029) | — | — | — | Ninguna. |

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T004)** → US1 (T005–T009) → US2 (T010–T011).
- **US3 (T012–T020)** y **US4 (T021–T023)** no dependen de US1 y pueden ir antes o en paralelo. T020 depende de T019, T019 de T017, y T018 de T017.
- **Documentación (T024–T026)** después de las historias.
- **T027** necesita todo lo anterior commiteado: es la evidencia de la entrega. T031 va al final, porque mide la suite con todos los tests nuevos.

## Parallel Opportunities

- T003, T005, T006, T012, T013, T014, T015, T016 y T021 son tests en archivos distintos y se pueden escribir en paralelo.
- T023, T024 y T025 son documentos distintos.

## Implementation Strategy

1. **MVP**: Foundational + US1. Los siete tests existen, el grupo determinista sigue sin clave y `Observacion` está protegida por sus guardas.
2. **US3** antes de la ejecución e2e, porque cambia `coordinador.py`, que la e2e ejercita.
3. **US2 y US4**: pequeñas, sin riesgo.
4. **Una sola ejecución e2e completa (T027)**, si todo está en verde; la segunda solo si hace falta.
