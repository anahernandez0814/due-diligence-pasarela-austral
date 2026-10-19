---

description: "Lista de tareas del ticket #11, interfaz de chat"
---

# Tasks: Interfaz de chat

**Input**: documentos de diseño en `specs/011-interfaz-chat/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/interfaz-chat.md](contracts/interfaz-chat.md) y [quickstart.md](quickstart.md).

**Prerequisites**: spec en `c7d7ced` (FR-006 ampliado a la línea de comandos en el commit de T001) y plan en `ecd687c`. Incluye las 8 correcciones del analyze (I1, T1, U1, I2, C1, C2, A1 y U2), aprobadas por la analista.

**Tests**: obligatorios (constitución X, SC-002, SC-003, SC-004 y SC-006).
- Van junto a cada módulo (`src/due_diligence/test_*.py`) y se escriben antes que el código: deben fallar primero.
- Ninguno llama al modelo ni a la red, y ninguno carga el archivo de entorno.
- Usan `CoordinadorSimulado`, `EjecutorSimulado` y `PasarelaSimulada` de `simulacion.py`, y `streamlit.testing.v1.AppTest` para la aplicación (R13).

**Organization**: dos bloques, cada uno con una parada de revisión de la analista al final:
- **Bloque A, la base**: dependencia, ampliación del coordinador simulado, observador sin bloqueo, turnos por turno, `comprobar_credencial()` y las funciones puras de `presentacion.py`. Termina en la **parada de revisión A**.
- **Bloque B, la aplicación**: textos de los hooks y reglas del coordinador, línea de comandos, `chat.py`, documentación y validación con el modelo real. Termina en la **parada de revisión B**.
- Después, `/abrir-pr`.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La verificación del cierre del #11 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US5).
- **[MANUAL]**: la hace la analista, en una sesión nueva de Claude Code abierta en la raíz y con el modelo real. Claude se detiene y espera su confirmación.
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md) o Q# del [quickstart](quickstart.md).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Ningún valor con forma real** (tarjeta, NIT, cédula o credencial) en tareas, tests, código ni documentación.
  - Solo los datos ficticios del #5: `CO-TV-0001` (a), `CO-TA-0002` (b, f), `CO-PL-0003` (c), `CO-AM-0004` y `CO-AM-0005` (d, e) y `CO-RF-0006` (g).
  - La clave de los tests es `"clave-ficticia-de-prueba"`. Sin secuencias de 6 o más dígitos seguidos (principio VII).
- **Todo en español**: textos de la interfaz, avisos, mensajes y documentación.
- **Ninguna regla ni ningún hook cambia de comportamiento**. En `hooks.py` solo cambian dos textos de eventos (R11). Los tests de los hooks del #7 al #10 siguen en verde salvo los que fijan esos textos.
- **Lo que se muestra sale de la traza y del estado del caso** (`caso.eventos()`, `caso.cobertura`, `caso.completo`, `caso.espera`), nunca del texto del modelo (R3, R4).
- **`presentacion.py` no importa Streamlit**, no llama al modelo y no lee el entorno por su cuenta (R2). `chat.py` no contiene lógica que no esté en `presentacion.py` o en `configuracion.py`.
- **El observador se llama después de salir del `with self._candado`, nunca dentro** (R1). Su excepción se ignora dentro de `registrar`.
- **Archivo de entorno**: lo cargan solo los dos puntos de entrada, `__main__.py` y `chat.py`, con `configuracion.cargar_entorno()`, que no nombra el archivo (R8 del #6). **Ningún módulo nombra el archivo, tampoco los mensajes de ayuda** (`test_sin_control_propio.py`, garantía R8 del #6; desviación D1 del plan): el mensaje lo describe y remite al README, que sí lo nombra. Ningún test lo carga; `test_chat.py` inyecta `Dependencias` y `test_main.py` parchea `cargar_entorno`.
- **El código no controla el ciclo** (FR-010 del #6): `test_sin_control_propio.py` sigue en verde. Sin `while` en `chat.py` ni en `presentacion.py`.
- **Tests de los tickets anteriores que cambian** (T032): se adaptan **sin debilitarse**, con igualdades exactas. Cada uno se cambia solo si falla por el diseño del #11, y se anota en la tabla de T032 con su justificación, que va en el PR. Ninguno se borra.
- **Commits** por partes lógicas en la rama `011-interfaz-chat`, nunca en `main`, sin `git commit --amend`. **Ningún commit va después de la revisión** de `/abrir-pr`.
- **Formato**: cada fase de código termina con `uv run ruff format .` y `uv run ruff check .`.
- **Tests**: la suite completa (`uv run pytest`) en verde al cerrar cada fase.
- **`DECISIONES.md`**: solo una entrada corta del #11, que remite a `plan.md` para lo pendiente (decisión de la analista; el #14 lo reescribe). `docs/bitacora-decisiones.md` no se edita.

---

# Bloque A: la base

## Fase 1: Setup

- [x] T001 Commitear `specs/011-interfaz-chat/tasks.md` en la rama `011-interfaz-chat`, junto con las correcciones del analyze en `spec.md` (I1: FR-006, SC-004 y los supuestos incluyen la línea de comandos), `data-model.md` (I2) y `quickstart.md` (C2, A1).
- [x] T002 Añadir `streamlit` a las dependencias con `uv add streamlit` (`pyproject.toml` y `uv.lock`) y comprobar con `uv run python -c "from streamlit.testing.v1 import AppTest"` que `AppTest` está disponible (R13). Anotar en `research.md` (R13) la versión instalada.
- [x] T003 Línea base: `uv run pytest` en verde y anotar el número de tests en la sección «Tests adaptados» de este archivo.

---

## Fase 2: Fundacional (simulación, observador, turnos por turno y credencial)

**Purpose**: lo que necesitan la interfaz y la línea de comandos. Bloquea las fases siguientes.

- [x] T004 [P] Tests de la ampliación de `CoordinadorSimulado` en `src/due_diligence/test_sesion_simulada.py` (U1 del analyze):
  - con `num_turns=[3, 4]` y dos guiones, el `ResultMessage` del primer turno lleva `num_turns == 3` y el del segundo `4`;
  - sin `num_turns`, cada turno sigue llevando 1, como hasta ahora;
  - el paso `("lanzar", excepcion)` ejecuta los pasos anteriores del guion y lanza esa excepción desde la `query()`, sin `ResultMessage`;
  - un `Caso` con ese guion termina el turno con `Terminacion.ANOMALA` y relanza la excepción, como hace con un fallo real del SDK.
- [x] T005 Implementar en `src/due_diligence/simulacion.py`, en `CoordinadorSimulado`:
  - el parámetro `num_turns: list[int] | None = None`, un valor por guion, que se pasa a `mensaje_de_resultado(num_turns=…)`;
  - el paso `("lanzar", excepcion)`, documentado en el docstring con los demás pasos.

  T004 en verde.
- [x] T006 [P] Tests del observador en `src/due_diligence/test_eventos_estado.py` (R1):
  - el observador recibe cada evento, en orden y después de guardarlo: dentro de la llamada, `eventos()` ya incluye ese evento;
  - sin observador, `registrar` se comporta igual que antes;
  - una excepción del observador no sale de `registrar` y el evento queda guardado;
  - **sin bloqueo**: un observador que llama a `registrar` con otro evento dentro de su llamada, una sola vez, no bloquea, y la traza tiene los dos eventos en orden, el del observador con la secuencia siguiente. El registro corre en un `threading.Thread` con `join(timeout=5)` y una aserción de que el hilo terminó (`not hilo.is_alive()`), para que un bloqueo haga fallar el test en lugar de colgar la suite;
  - lo mismo con un observador que llama a `eventos()`.
- [x] T007 Implementar el observador en `src/due_diligence/eventos.py` (R1, data-model): `RegistroEventos(reloj=None, observador=None)`. `registrar` crea y guarda el evento dentro del `with self._candado` y, **ya fuera del `with`**, llama a `observador(evento)` dentro de `try/except Exception: pass`. Un comentario explica por qué va fuera (el `Lock` no es reentrante) y por qué se ignora la excepción (un hook que registra no debe fallar). T006 en verde.
- [x] T008 Tests de `Caso` en `src/due_diligence/test_coordinador.py` (R1, R5, FR-004), con la simulación de T005:
  - `Caso(observador=f)` entrega a `f` los mismos eventos que `caso.eventos()`, en orden;
  - el caso (a) simulado (guion de `test_casos_escalamiento.py`) con un observador que lanza en cada evento termina igual que sin observador: sin `fallo_de_hook`, con el escalamiento y el informe, y con el mismo `caso.completo`;
  - dos turnos con `CoordinadorSimulado(num_turns=[3, 4])` dan `caso.turnos_por_turno == [3, 4]` y `caso.turnos == 7`;
  - un turno con el paso `("lanzar", RuntimeError(...))` añade `None` a `turnos_por_turno`.
- [x] T009 Implementar en `src/due_diligence/coordinador.py`: el parámetro `observador` de `Caso` (lo pasa a `RegistroEventos`) y `turnos_por_turno: list[int | None]`, con un valor por turno (el `num_turns` del `ResultMessage`, o `None` si no lo hubo), añadido una sola vez por turno en `_terminar`. `Caso.turnos` sigue siendo la suma (R5). T008 en verde.
- [x] T010 [P] Tests de `comprobar_credencial` en `src/due_diligence/test_configuracion.py` (R8, FR-006):
  - devuelve `MENSAJE_SIN_CLAVE` sin `ANTHROPIC_API_KEY`, con valor vacío y con solo espacios;
  - devuelve `None` con la clave ficticia y sin alternativas;
  - devuelve `MENSAJE_OTRA_CREDENCIAL` con cada una de `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_USE_BEDROCK` y `CLAUDE_CODE_USE_VERTEX`, aunque la clave esté;
  - ningún mensaje contiene el valor de la clave;
  - con `entorno=None` lee `os.environ` (con `monkeypatch`).
- [x] T011 Implementar `comprobar_credencial(entorno=None) -> str | None`, `MENSAJE_SIN_CLAVE` y `MENSAJE_OTRA_CREDENCIAL` en `src/due_diligence/configuracion.py` (R8).
  - `MENSAJE_SIN_CLAVE` explica que hay que copiar la plantilla de variables de entorno de la raíz (la que termina en «.example») como archivo de entorno local, poner la clave en `ANTHROPIC_API_KEY` y reiniciar, y remite al README. **No nombra el archivo** (desviación D1 del plan).
  - `MENSAJE_OTRA_CREDENCIAL` nombra la variable alternativa encontrada y pide quitarla, porque la aplicación solo usa `ANTHROPIC_API_KEY`.

  T010 en verde.
- [x] T012 `uv run ruff format .`, `uv run ruff check .` y `uv run pytest`; commit «simulación, observador, turnos por turno y credencial (#11)».

**Checkpoint**: la base está lista. Ningún comportamiento visible ha cambiado todavía.

---

## Fase 3: User Story 2, funciones puras de lo que se ve (Priority: P1)

**Goal**: convertir la traza y el estado del caso en indicadores, cobertura, estado y turnos, sin Streamlit (FR-002, FR-003, FR-004). Empieza por `hora_colombia`, que usan los indicadores (T1 del analyze).

**Independent Test**: con el caso (a) y el caso (f) simulados, `resumen_del_turno` devuelve un indicador por cada delegación, bloqueo, informe y escalamiento de la traza, en orden; la cobertura de los cuatro frentes; y el estado correcto.

- [ ] T013 [P] [US5] Tests de `hora_colombia` en `src/due_diligence/test_presentacion.py` (nuevo) (R9, FR-007):
  - `03:00 UTC` → `"22:00:00 (hora de Colombia)"`, también desde una marca en otra zona;
  - siempre con la zona declarada.
- [ ] T014 [US5] Implementar `hora_colombia` en `src/due_diligence/presentacion.py` (nuevo), con `timezone(timedelta(hours=-5))` y sin `zoneinfo` (R9). T013 en verde.
- [ ] T015 [US2] Tests en `src/due_diligence/test_presentacion.py` (R3, R4, R5, data-model):
  - `frente_en_palabras` para los cuatro frentes;
  - `indicador`:
    - devuelve un indicador por cada tipo del mapa de R3 (`delegacion`, `bloqueo_regla` con `regla`, motivo y `accion`, `informe_registrado`, `escalamiento_registrado` y `fallo_de_hook`), con su `tipo`, `titulo`, `detalle`, `hora` (de `hora_colombia`) y `secuencia`;
    - devuelve `None` para los demás tipos de `eventos.TIPOS`;
    - el título de un bloqueo contiene la regla y la acción intentada;
  - `eventos_del_turno`: con dos `mensaje_analista`, cada turno tiene sus eventos; `caso_iniciado` y `modo_demostracion` van en el turno 1;
  - `filas_cobertura`: cuatro filas en el orden de `Frente`, con el motivo vacío si el frente está cubierto;
  - `estado_mostrado`, recorriendo el orden de R4: fallo de hook, espera (con su motivo), terminación anómala, completo e incompleto. **`clase == "completo"` si y solo si `caso.completo`**, comprobado sobre todos los casos simulados del test;
  - `resumen_del_turno` con el caso (a) simulado: los indicadores de la traza de ese turno en orden de `secuencia` (SC-002), las cuatro filas de cobertura, el estado «Completo», la respuesta y `turnos == "N de 30"` con el valor de `turnos_por_turno` de ese turno, nunca la suma (FR-004; con `num_turns=[3, 4]`, el turno 2 dice «4 de 30»);
  - el caso (f) simulado (noticias con `servicio_no_disponible`): noticias «no cubierto» con su motivo, y el estado incompleto;
  - ningún texto del indicador lleva un nombre ficticio de comercio o de persona que no esté en el detalle del evento;
  - `presentacion.py` no importa `streamlit`: se comprueba con `ast` sobre el archivo.
- [ ] T016 [US2] Implementar en `src/due_diligence/presentacion.py` `Indicador`, `FilaCobertura`, `EstadoMostrado` y `TurnoMostrado` (dataclasses `frozen`, campos de data-model), y `frente_en_palabras`, `indicador`, `eventos_del_turno`, `filas_cobertura`, `estado_mostrado` y `resumen_del_turno(caso, n, mensaje, aviso=None, respuesta=None)`, según el mapa de R3 y el orden de R4. `turnos` usa `configuracion.turnos_usados(caso.turnos_por_turno[n - 1])`, o `"sin dato"` si falta. T015 en verde.

---

## Fase 4: User Story 1, decisión sobre el mensaje entrante (Priority: P1)

**Goal**: la regla de caso nuevo, continuar o aviso, como función pura (FR-001, FR-005, US1-3, R6).

**Independent Test**: la tabla de R6 completa con casos simulados.

- [ ] T017 [US1] Tests de `decidir_mensaje` en `src/due_diligence/test_presentacion.py` (R6):
  - sin caso → `NUEVO` sin aviso;
  - caso completo → `NUEVO` con `AVISO_CASO_NUEVO` («Caso anterior cerrado; se inició un caso nuevo.»);
  - caso incompleto, por ejemplo el (f) → `CONTINUAR`;
  - caso en espera, el (d) tras el turno 1 → `CONTINUAR` con texto, y `AVISO_ESPERA` con `""` o `"   "`, con el motivo de la espera y la frase «El caso sigue sin completar»;
  - texto vacío sin espera → `IGNORAR`.

  También: `MENSAJE_SIN_SESION` y `MENSAJE_FALLO_TURNO` (con el nombre del tipo de error) no contienen trazas.
- [ ] T018 [US1] Implementar en `src/due_diligence/presentacion.py` `Decision` (`StrEnum`), `DecisionMensaje(accion, aviso)`, `decidir_mensaje(caso, texto)`, `AVISO_CASO_NUEVO`, `AVISO_ESPERA` (plantilla con el motivo), `MENSAJE_FALLO_TURNO` (plantilla con el tipo) y `MENSAJE_SIN_SESION`.
  - `MENSAJE_SIN_SESION` se mueve aquí desde `__main__.py`, que lo importa para seguir exponiéndolo con el mismo nombre, sin romper `test_main.py`.

  T017 en verde.

---

## Fase 5: User Story 4, modos activos (Priority: P2)

- [ ] T019 [US4] Tests de `modos_activos` en `src/due_diligence/test_presentacion.py` (R12, FR-010):
  - lista vacía sin variables;
  - una línea por cada una de `PASARELA_FALLA_NOTICIAS`, `PASARELA_FALLA_REGISTRO` y `PASARELA_MODO_DEMO_HOOKS`, solo con el valor exacto `"1"`; `"0"`, `"true"` y `""` no cuentan;
  - las tres juntas, en ese orden;
  - el texto del modo de demostración dice que los hooks siguen activos.
- [ ] T020 [US4] Implementar `modos_activos(entorno)` en `src/due_diligence/presentacion.py`, con los textos de R12. T019 en verde.
- [ ] T021 `uv run ruff format .`, `uv run ruff check .` y `uv run pytest`; commit «funciones puras de la interfaz (#11)».

---

## 🛑 PARADA DE REVISIÓN A

- [ ] T022 **Parada A**: Claude se detiene y presenta a la analista:
  - el SHA;
  - los archivos del bloque A: `simulacion.py`, `eventos.py`, `coordinador.py`, `configuracion.py` y `presentacion.py`, con sus tests;
  - el número de tests frente a la línea base de T003;
  - lo que conviene mirar: el test sin bloqueo del observador (T006), el del observador que lanza en el caso (a) (T008), los mensajes de credencial (T011) y la tabla del estado del caso (T015).

  No se sigue con el bloque B hasta que la analista lo apruebe.

---

# Bloque B: la aplicación

## Fase 6: User Story 5, textos neutros y reglas de fechas del coordinador (Priority: P2)

**Goal**: FR-007, FR-008 y FR-009 en el paquete.

**Independent Test**: los eventos de sustitución salen neutros, y las instrucciones del coordinador llevan la regla de fechas en los dos modos.

- [ ] T023 [P] [US5] Tests de los textos en `src/due_diligence/test_hooks.py` (R11, FR-009):
  - informe con la cobertura **omitida** → `cobertura_sustituida` termina en «Se sustituyó por la calculada.»;
  - informe con una cobertura distinta → el mismo texto;
  - cobertura igual a la calculada → «Coincide con la declarada por el coordinador.»;
  - `datos_sustituidos` con el comercio y los conflictos omitidos → «Se sustituyeron por los calculados: comercio, conflictos.»;
  - en ningún evento de la traza aparece «era distint»;
  - `datos_sustituidos` no tiene un «; » seguido de una mayúscula (expresión regular);
  - el mismo test para `escalar_a_cumplimiento`.

  Adaptar con igualdades exactas `test_hooks.py:1757` y cualquier otro test que fije los textos anteriores (`grep -rn "era distint\|Coincide con l" src`), y anotarlos en T032.
- [ ] T024 [US5] Cambiar los textos en `src/due_diligence/hooks.py`, en `_evento_cobertura` y `_evento_datos`, como en R11 y el contrato: punto en vez de punto y coma, y «Se sustituyó por la calculada.» o «Se sustituyeron por los calculados: {campos}.». Sin cambios de comportamiento. T023 en verde.
- [ ] T025 [P] [US5] Tests de las instrucciones en `src/due_diligence/test_coordinador.py` (R9, R10, R4):
  - `instrucciones_coordinador(demo=False)` y `demo=True` contienen `_REGLA_FECHAS` completa (AAAA-MM-DD y la fecha de registro en UTC, «no la presentes como una fecha posterior a hoy»);
  - `_REGLA_RESUMEN` pide empezar por la cobertura y los frentes que fallaron;
  - adaptar los tests que fijan la lista o el número de reglas, y anotarlos en T032.
- [ ] T026 [US5] Añadir `_REGLA_FECHAS` a las dos listas de `instrucciones_coordinador` y ajustar `_REGLA_RESUMEN` en `src/due_diligence/coordinador.py` (R9, R4). T025 en verde.

---

## Fase 7: User Stories 1, 2 y 3 en la línea de comandos (Priority: P1)

- [ ] T027 [P] [US3] Tests en `src/due_diligence/test_main.py` (R8, FR-006):
  - sin `ANTHROPIC_API_KEY`, `main([...])` devuelve 2, imprime `MENSAJE_SIN_CLAVE` en la salida de error y **no llama** a `ejecutar_caso` (parcheado con un contador);
  - lo mismo con `ANTHROPIC_AUTH_TOKEN` y `MENSAJE_OTRA_CREDENCIAL`;
  - la comprobación va después de `cargar_entorno` (orden registrado);
  - **adaptación**: un fixture `autouse` del módulo fija la clave ficticia y quita las variables alternativas con `monkeypatch`, para que los tests existentes sigan llegando a `ejecutar_caso`. Anotarlo en T032.
- [ ] T028 [P] [US2] Tests en `src/due_diligence/test_main.py` (R5, FR-004): con `CoordinadorSimulado(num_turns=[3, 4])` en dos turnos (T005), la salida del segundo dice «turnos del coordinador en este turno: 4 de 30» y nunca «7 de 30». Adaptar `test_la_salida_muestra_la_cobertura_y_los_turnos_del_coordinador` y anotarlo en T032.
- [ ] T029 [P] [US1] Tests en `src/due_diligence/test_main.py` (R6, FR-005):
  - con espera abierta, una línea vacía, una con solo espacios y el fin de la entrada imprimen `AVISO_ESPERA` con el motivo antes de terminar;
  - sin espera no se imprime;
  - el código de salida es el mismo que antes del cambio.
- [ ] T030 [US1] Cambiar `src/due_diligence/__main__.py`:
  - `comprobar_credencial()` justo después de `configuracion.cargar_entorno()`: con un problema, el mensaje a stderr y `return 2`;
  - «turnos del coordinador en este turno: …» con el último valor de `turnos_por_turno`;
  - `AVISO_ESPERA` en `_conversar` ante la línea vacía o el fin de la entrada con espera;
  - el docstring ya no dice que es «el ÚNICO lugar que carga el entorno»: son los dos puntos de entrada.

  T027 a T029 en verde.
- [ ] T031 `uv run ruff format .`, `uv run ruff check .` y `uv run pytest`; commit «textos neutros, fechas y línea de comandos (#11)».
- [ ] T032 Tabla de tests adaptados en este archivo, bajo «Tests adaptados». Una fila por test: archivo:línea, qué fijaba, qué fija ahora y por qué no se debilita. Va al PR.

---

## Fase 8: User Stories 1 a 4, aplicación de chat (Priority: P1)

**Goal**: el chat de Streamlit sobre `presentacion.py` y `Caso` (FR-001 a FR-006 y FR-010).

**Independent Test**: con `AppTest` y el coordinador simulado, el caso (d) en dos turnos, el (a), el (f), la parada sin clave y el caso nuevo se ven como dice el contrato.

- [ ] T033 [US1] Medición con `AppTest` (R6, R13; U2 y C1 del analyze):
  - **queda como test** en `src/due_diligence/test_chat.py` solo el envío de espacios: si `st.chat_input` deja enviar `"   "`. Ese resultado decide la rama de FR-005 en T034 y T035; si no deja enviarlos, se aplica el **plan B de FR-005** (aviso fijo encima de la entrada), ya decidido por la analista: no es una desviación;
  - **se anota en `research.md`** (R13), sin test: qué colecciones de `AppTest` dan acceso a `st.chat_message`, `st.status`, `st.error` y `st.info`, y si `AppTest` procesa un `pendiente` sembrado en la misma ejecución. Si lo procesa, el test de C1 de T034 no se puede escribir: se anota aquí y queda como comprobación manual en Q4.
- [ ] T034 [P] [US1] Tests de `AppTest` en `src/due_diligence/test_chat.py` (R13, contrato). Cada uno inyecta `session_state["dependencias"]` antes de `run()`:
  - `cargar_entorno`, que no hace nada;
  - `entorno: Mapping[str, str]` con la clave ficticia (I2);
  - `crear_caso(observador)`, que construye un `Caso` con `CoordinadorSimulado(guiones=...)`, `EjecutorSimulado` y el observador, y asigna `coordinador.caso`.

  Tests:
  - **caso (d) en dos turnos**:
    - turno 1: el mensaje del analista, ningún indicador de delegación a listas, el estado «Esperando al analista» y la respuesta del coordinador;
    - turno 2, tras enviar `CO-AM-0004`: la delegación a listas, el informe registrado y los dos turnos en el historial, en orden;
  - **caso (a)**: los indicadores de delegación, escalamiento e informe, en el orden de la traza (SC-002);
  - **caso (f)**: noticias «no cubierto» con su motivo aparece **antes** que la respuesta del coordinador (SC-003; el orden se comprueba por la posición de los elementos);
  - **caso completo seguido de otro mensaje**: el turno nuevo lleva `AVISO_CASO_NUEVO` y el `Caso` es otro (la fábrica se llamó dos veces);
  - **«Caso nuevo»**: tras pulsarlo, el historial queda vacío;
  - **sin clave**: `entorno` vacío, `MENSAJE_SIN_CLAVE` en `st.error`, sin entrada de chat y la fábrica de casos sin llamar (SC-004). Lo mismo con `ANTHROPIC_AUTH_TOKEN` y `MENSAJE_OTRA_CREDENCIAL`;
  - **modos**: con `PASARELA_FALLA_NOTICIAS="1"` y `PASARELA_MODO_DEMO_HOOKS="1"` en `entorno`, la franja muestra las dos líneas de `modos_activos`;
  - **FR-005, según T033**:
    - con el plan B: tras el turno 1 del caso (d) se ve `AVISO_ESPERA` encima de la entrada, y tras el turno 2 ya no;
    - si no: enviar `"   "` con la espera abierta muestra `AVISO_ESPERA` y no llama a `continuar`;
  - **fallo del turno**: con el paso `("lanzar", RuntimeError(...))` de T005, la respuesta es `MENSAJE_FALLO_TURNO` sin traza y el estado «Incompleto»;
  - **pendiente sembrado (C1)**: con un mensaje en `session_state["pendiente"]` antes de `run()`, la entrada del chat y el botón «Caso nuevo» aparecen deshabilitados. Solo si T033 muestra que `AppTest` lo permite; si no, queda como comprobación manual en Q4.
- [ ] T035 [US1] Implementar `src/due_diligence/chat.py` (nuevo) según el contrato y R1, R2, R7, R8 y R12:
  - `Dependencias` (dataclass, con `entorno: Mapping[str, str]`) con los valores de producción por defecto, leída de `st.session_state.get("dependencias")`;
  - arranque:
    - `cargar_entorno()` y `comprobar_credencial(entorno)`;
    - con un problema, `st.error` y `st.stop()`;
    - después, la franja de `modos_activos`;
  - botón «Caso nuevo», deshabilitado mientras hay un `pendiente`, que vacía `caso` e `historial`;
  - historial: cada `TurnoMostrado` en el orden de dibujo de data-model, con `st.chat_message("user")` y `st.chat_message("assistant")`;
  - aviso fijo de espera (plan B de FR-005, si aplica según T033) y texto de ayuda de la entrada con el motivo de la espera;
  - `st.chat_input(disabled=pendiente)`: al enviar, `decidir_mensaje`. Con `NUEVO` o `CONTINUAR`, el texto se guarda en `pendiente` y se llama a `st.rerun()` (R7);
  - con un `pendiente`:
    - `st.status("El coordinador está trabajando…")`, con un observador que escribe en él `indicador(evento)` en vivo;
    - `asyncio.run(caso.ejecutar(...))` o `asyncio.run(caso.continuar(...))`;
    - `CasoSinSesion` → `MENSAJE_SIN_SESION`, y otra excepción → `MENSAJE_FALLO_TURNO`, sin traza;
    - el turno se guarda con `resumen_del_turno`, se borra el `pendiente` y `st.rerun()`;
  - sin `while`.

  Adaptar `test_cargar_entorno_solo_se_llama_desde_el_punto_de_entrada` (`test_sin_control_propio.py`) a `["__main__.py", "chat.py"]`, los dos puntos de entrada de R8, y anotarlo en T032. T034 en verde.
- [ ] T036 `uv run ruff format .`, `uv run ruff check .` y `uv run pytest`; commit «aplicación de chat (#11)».

---

## Fase 9: User Story 4, documentación (Priority: P2)

- [ ] T037 [P] [US4] Sección «Interfaz de chat» en `README.md` (FR-010):
  - cómo arrancar (`uv run streamlit run src/due_diligence/chat.py`);
  - qué hacer sin clave, en el chat y en la línea de comandos;
  - qué se ve en cada turno (indicadores en vivo, cobertura antes de la respuesta, estado y turnos);
  - la regla del caso nuevo;
  - cómo activar `PASARELA_FALLA_NOTICIAS=1` (caso f) y `PASARELA_MODO_DEMO_HOOKS=1` (caso e), en PowerShell y en bash, **reiniciando la aplicación**;
  - la tabla de los siete casos de Q4, con su mensaje y lo que se debe ver.

  Actualizar también:
  - el punto «Credenciales» de «Coordinador y subagentes»: dos puntos de entrada y `comprobar_credencial`;
  - la mención de la hora en UTC: la traza en UTC y el chat en hora de Colombia.
- [ ] T038 [P] Entrada corta del #11 en `DECISIONES.md`, de unas pocas líneas: observador en vivo con la traza como verdad, `comprobar_credencial` común, hora de Colombia en la interfaz y UTC en la traza, caso nuevo tras un caso completo, y lo pendiente en `specs/011-interfaz-chat/plan.md`.
- [ ] T039 Commit «documentación de la interfaz de chat (#11)».

---

## Fase 10: Validación

- [ ] T040 Q1 de [quickstart.md](quickstart.md): `uv run ruff format --check .`, `uv run ruff check .` y `uv run pytest`, en verde, con el número de tests anotado junto a la línea base de T003.
- [ ] T041 [MANUAL] Q3: arranque sin clave en el chat y en la línea de comandos (Q6, último punto). Sin modelo.
- [ ] T042 [MANUAL] Q4: los siete casos desde el chat con el modelo real, con el coste de cada uno. Se observan los indicadores **en vivo** durante el turno (C2) y, si T033 no lo pudo probar, la entrada deshabilitada (C1). La analista valora SC-005 con (a), (d) y (e).
- [ ] T043 [MANUAL] Q5 y Q6: la hora de Colombia en los indicadores; la línea de comandos con los turnos de este turno y el aviso ante la línea vacía. **Condicional (A1)**: el caso (b) sin «un día después de hoy» solo se comprueba si la prueba cae después de las 19:00 de Colombia; si no, se anota como no ejecutado.
- [ ] T044 Anotar los resultados de T041 a T043 en este archivo, bajo «Resultados de la validación», y commitear.

---

## 🛑 PARADA DE REVISIÓN B

- [ ] T045 **Parada B**: Claude se detiene y presenta a la analista:
  - el diff del bloque B;
  - la tabla de T032;
  - las mediciones de T033;
  - los resultados de T041 a T043.

  No se ejecuta `/abrir-pr` hasta que la analista lo apruebe.

---

## Fase 11: Cierre

- [ ] T046 `/abrir-pr`: revisión independiente y auditoría de cumplimiento (I.1–I.5 aplican porque el diff toca `hooks.py`, `eventos.py` y `coordinador.py`), PR hacia `main` con `Closes #11` y la tabla de T032. Ningún commit después de la revisión.

---

## Tests adaptados (T032)

| Test | Fijaba | Fija ahora | Por qué no se debilita |
|------|--------|-----------|------------------------|
| _(se completa en T023, T025, T027 y T028)_ | | | |

Línea base (T003): 4606 tests en verde, en `c60a722` con `streamlit` 1.66.0 instalado.

## Resultados de la validación (T044)

_Pendiente._

---

## Dependencies & Execution Order

- **Fase 1** → **Fase 2** (bloquea todo; T004–T005 antes que T008) → **Fase 3** (T013–T014 antes que T015–T016, que usan `hora_colombia`) → **Fases 4 y 5** (después de la 3: comparten `presentacion.py` y `test_presentacion.py`) → **Parada A**.
- **Bloque B**:
  - la **Fase 6** (`hooks.py` y `coordinador.py`) y la **Fase 7** (`__main__.py`) son independientes entre sí;
  - la **Fase 8** necesita las fases 2 a 5;
  - la **Fase 9** necesita la 8 (los mensajes y la regla del caso nuevo, definitivos);
  - la **Fase 10** necesita todo → **Parada B** → **Fase 11**.
- **Dentro de cada fase**: los tests primero (deben fallar), luego la implementación.

### Historias

- **US1** (conversación): T017–T018, T029–T030, T033–T035.
- **US2** (entender qué pasó): T015–T016, T028, T034.
- **US3** (credencial): T010–T011 (fundacional), T027, T034.
- **US4** (siete casos): T019–T020, T037, T042.
- **US5** (horas, fechas y textos): T013–T014, T023–T026, T043.

### Parallel Opportunities

- T004, T006 y T010: tres archivos de test distintos (T008 espera a T005).
- T023, T025 y T027–T029: T023 en `test_hooks.py`, T025 en `test_coordinador.py` y T027–T029 en `test_main.py`.
- T037 y T038.

## Implementation Strategy

- **MVP**: el bloque A y la fase 8 con el caso (d): el chat de varios turnos con indicadores, cobertura y estado.
- **Incremento**: fases 6 y 7 (textos, fechas y línea de comandos), después la documentación y la validación con el modelo real.
- Cada parada de revisión es un punto de entrega estable, con la suite en verde.
