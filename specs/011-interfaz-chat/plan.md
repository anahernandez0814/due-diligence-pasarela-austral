# Implementation Plan: Interfaz de chat

**Branch**: `011-interfaz-chat` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-interfaz-chat/spec.md` (aprobada en `c7d7ced`)

## Summary

Un chat con Streamlit sobre el `Caso` del #10. Cada turno se dibuja así: mensaje del analista →
indicadores (delegación, bloqueo con regla, motivo y acción, informe registrado, escalamiento) →
cobertura y frentes que fallaron → estado del caso → respuesta del coordinador → turnos de ese
turno frente a 30.

Todo lo que se muestra sale de **funciones puras** (`presentacion.py`, sin Streamlit), que leen la
traza de eventos y el estado del caso, no el texto del modelo. Los indicadores salen **en vivo**,
por un observador opcional del registro de eventos, y el turno guardado se reconstruye de la traza
al terminar (R1).

Se corrigen además, en el paquete y en la línea de comandos:
- los turnos por turno;
- el aviso ante la línea vacía con la espera abierta;
- los textos neutros de las sustituciones;
- la guía de fechas y UTC del coordinador.

## Technical Context

**Language/Version**: Python 3.12 (uv)

**Primary Dependencies**:
- `claude-agent-sdk` 0.2.168 (sin cambios);
- **`streamlit`, nueva**, con `uv add`; la versión queda fijada en `uv.lock`;
- `python-dotenv` (ya está).

**Storage**: N/A. El caso vive en `st.session_state`; los informes y escalamientos los sigue
guardando la pasarela en `resultados/`.

**Testing**:
- pytest;
- `streamlit.testing.v1.AppTest` con `CoordinadorSimulado` y `EjecutorSimulado` (R13);
- ningún test llama al modelo ni carga `.env`.

**Target Platform**: aplicación local (Windows, macOS, Linux) en el navegador.

**Project Type**: paquete Python con una aplicación de chat y una línea de comandos.

**Performance Goals**: N/A. El tiempo lo marca el modelo, de uno a tres minutos por turno; los
indicadores en vivo cubren la espera.

**Constraints**:
- un turno a la vez (R7);
- sin credenciales distintas de `ANTHROPIC_API_KEY` (R8);
- sin datos reales (VII).

**Scale/Scope**:
- un analista y un caso a la vez;
- dos módulos nuevos (`presentacion.py` y `chat.py`) con sus tests;
- cambios pequeños en `eventos.py`, `coordinador.py`, `hooks.py` (textos) y `__main__.py`.

## Constitution Check

*GATE: antes de la fase 0 y otra vez tras el diseño.* **Cumple, con una desviación justificada de
la spec (D1), declarada durante la construcción del bloque A.**

| Principio | Cómo se cumple |
|-----------|----------------|
| **I.1–I.5** | No cambia ninguna regla ni ningún hook. En `hooks.py` solo cambian dos textos de eventos (R11). El observador no puede afectar a un hook: su excepción se ignora en `registrar` (R1, con test). I.5 se ve en la interfaz: «Completo» si y solo si `caso.completo`, y la cobertura va antes de la respuesta (R4). |
| **II** | Lo obligatorio sigue en hooks. FR-007 (UTC) y FR-008 (formato) en el texto del modelo son guía de estilo y comprensión, no reglas de negocio; lo que dibuja la interfaz lo fija el código (R9, R10). |
| **III** | Cada turno sigue terminando por su `stop_reason`. La interfaz no controla el ciclo: llama a `ejecutar` y `continuar`. |
| **IV** | Sin cambios en el servidor ni en sus contratos. |
| **V** | Sin cambios. La interfaz muestra la espera del identificador y el escalamiento. |
| **VI** | Es el objetivo del ticket. Los indicadores salen de la traza, en lenguaje natural, y la hora de Colombia va declarada. |
| **VII** | Los mensajes documentados usan los comercios ficticios del #5. La clave de los tests es ficticia y sin forma real. |
| **VIII** | `ANTHROPIC_API_KEY` desde `.env` con python-dotenv, sin pisar el entorno. La aplicación se detiene si falta y no usa otras credenciales (R8). Nada lee `.env` fuera de los dos puntos de entrada. |
| **IX** | Issue #11, rama propia, spec, plan y tareas antes del código. |
| **X** | Tests junto al código (`test_presentacion.py`, `test_chat.py`) y ruff. La revisión y la auditoría van en `/abrir-pr`. Los casos (a), (d) y (f) se ejercitan también desde la interfaz simulada. |

**Auditoría de `/abrir-pr`**: I.1–I.5 aplican, porque el diff toca `hooks.py`, `eventos.py` y
`coordinador.py`. Los tests anteriores que cambian por FR-004, FR-005 o FR-009 van en una tabla del
PR, adaptados con igualdades exactas.

**Re-evaluación tras el diseño**: sin cambios. Ninguna decisión de R1–R13 contradice un FR ni un
principio. Lo que no se garantiza en código (R14.1–R14.3) está declarado.

## Decisiones (detalle en [research.md](research.md))

1. **R1, indicadores en vivo**: observador opcional en `RegistroEventos`, que escribe en vivo como
   mejor esfuerzo. El turno guardado se reconstruye de la traza.
   - **Trade-off**: un cambio pequeño en `eventos.py` y un `try/except` que protege a los hooks, a
     cambio de no dejar al analista uno a tres minutos ante un «trabajando» mudo.
   - **Sin bloqueo**: el observador se llama **después de salir** del `with self._candado` (un
     `threading.Lock`, no reentrante), nunca dentro. Un test con tiempo límite lo fija: un
     observador que registra otro evento no bloquea y los dos quedan en orden.
2. **R2, estructura**: `presentacion.py` puro y `chat.py` de Streamlit con `Dependencias`
   inyectables para los tests.
3. **R3, mapa de la traza a los indicadores**: cinco tipos de indicador.
4. **R4, estado del caso**: el orden de evaluación, con «Completo» solo si `caso.completo`.
5. **R5, turnos por turno**: `Caso.turnos_por_turno`; `Caso.turnos` sigue siendo la suma, pero ya
   no se muestra frente a 30.
6. **R6, mensaje entrante**: `decidir_mensaje`. Un caso completo hace que el siguiente mensaje
   inicie uno nuevo (decisión de la analista), y el aviso de espera vacía vale también en la línea
   de comandos.
   - **Plan B de FR-005, decidido**: si `st.chat_input` no deja enviar un mensaje con solo
     espacios, el chat muestra un aviso fijo encima de la entrada mientras el caso espera («El
     coordinador espera su respuesta: …»), con su test en `AppTest`.
7. **R7, un turno a la vez**: mensaje pendiente y entrada deshabilitada mientras se trabaja.
8. **R8, credencial**: una sola función, `configuracion.comprobar_credencial()`, que usan el chat
   y `__main__.py`.
   - Los dos se detienen, con el mismo mensaje, sin `ANTHROPIC_API_KEY` o con una credencial que
     el CLI usaría antes.
   - La línea de comandos sale con el código 2.
   - Hay un test por cada punto de entrada.
9. **R9 y R10, horas y fechas**: hora de Colombia con zona fija UTC−5, `_REGLA_FECHAS` en el
   coordinador y `AAAA-MM-DD`.
10. **R11, textos neutros**: «Se sustituyó por la calculada.», y punto en vez de punto y coma.
11. **R12, modos activos**: franja fija con los modos activos, leídos al arrancar.
12. **R13, tests de la aplicación**: `AppTest` con el coordinador simulado y `Dependencias`
    inyectadas.

## Project Structure

### Documentation (this feature)

```text
specs/011-interfaz-chat/
├── spec.md
├── plan.md
├── research.md          # R1–R14 y lo pendiente para DECISIONES.md
├── data-model.md
├── quickstart.md        # Q1–Q6
├── contracts/
│   └── interfaz-chat.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/due_diligence/
├── presentacion.py        # NUEVO: funciones puras de la interfaz (R2–R6, R8–R12)
├── test_presentacion.py   # NUEVO
├── chat.py                # NUEVO: aplicación de Streamlit (R1, R2, R7, R8, R12)
├── test_chat.py           # NUEVO: AppTest con el coordinador simulado (R13)
├── eventos.py             # observador opcional (R1)
├── coordinador.py         # observador, turnos_por_turno, _REGLA_FECHAS, _REGLA_RESUMEN (R1, R4, R5, R9)
├── configuracion.py       # comprobar_credencial() y sus mensajes (R8)
├── hooks.py               # textos de cobertura_sustituida y datos_sustituidos (R11)
├── __main__.py            # credencial, turnos por turno, aviso de espera vacía (R5, R6, R8)
└── test_*.py              # adaptaciones de FR-004, FR-005, FR-006 y FR-009
README.md                  # sección «Interfaz de chat» y los siete casos (FR-010)
DECISIONES.md              # solo una entrada corta del #11 (el #14 lo reescribe)
pyproject.toml, uv.lock    # streamlit
```

**Structure Decision**: un solo paquete, `src/due_diligence/`, como hasta ahora. La interfaz es un
módulo más, con su lógica separada en funciones puras.

## Orden de construcción y paradas de revisión

1. Dependencia `streamlit`.
2. `eventos.py` (observador, fuera del candado) y `coordinador.py` (observador y
   `turnos_por_turno`).
3. `configuracion.comprobar_credencial()` y `presentacion.py`, con sus tests.
4. **Parada A**: funciones puras, credencial, observador y turnos por turno, con la suite en verde.
5. Textos de `hooks.py` (FR-009) y reglas del coordinador (FR-007, FR-008, `_REGLA_RESUMEN`).
6. `__main__.py`: FR-004, FR-005 y FR-006.
7. `chat.py` y `test_chat.py`.
8. README, la entrada corta del #11 en DECISIONES.md y el quickstart.
9. **Parada B**: aplicación completa, suite en verde y Q3–Q6 con el modelo real.
10. `/abrir-pr`.

## Riesgos residuales

Detalle en R14 de [research.md](research.md):
1. FR-007 y FR-008 en el texto del modelo son guía, no garantía.
2. La vista en vivo depende de que los eventos lleguen en el hilo del script; el turno guardado
   no.
3. La precedencia de credenciales del CLI no se midió.
4. Recargar la página pierde el caso.
5. Un caso incompleto se continúa con el mensaje siguiente; el analista usa «Caso nuevo».

## Pendiente fuera de alcance

En este ticket DECISIONES.md solo recibe una entrada corta del #11, que remite aquí; el #14 lo
reescribe completo. Queda pendiente:
- D7 del #9;
- la redacción de `RESUMEN_REGISTRO_CAIDO` para todas las causas;
- las 14 sugerencias del PR #26 (entre ellas `informe.py:158`, `escalamiento_cubre` con el
  comercio por defecto, las duplicaciones, el test de dos turnos de US3-9 y R13.10);
- el evento de espera que ya no queda en la traza con el registro sin delegar;
- mejoras de la interfaz:
  - persistencia de los casos;
  - control de los modos dentro del chat;
  - diseño visual.

## Desviación justificada

### D1. El mensaje sin clave no nombra el archivo de entorno (US3-2)

- **Qué dice la spec**: US3-2 pedía que el mensaje dijera «en qué archivo ponerla (a partir de
  `.env.example`)».
- **Con qué choca**: la garantía R8 del #6, que fija `test_sin_control_propio.py`
  (`test_ningun_modulo_nombra_el_archivo_de_entorno_ni_escribe_una_clave`). Ningún módulo de
  `src/due_diligence/` contiene el nombre literal del archivo de entorno, tampoco dentro del de la
  plantilla. Se descubrió al cerrar la fase 2 (T012), con la suite.
- **Qué se hace**: `MENSAJE_SIN_CLAVE` describe el archivo sin nombrarlo y remite al README, que
  sí lo nombra paso a paso:
  - copiar la plantilla de variables de entorno de la raíz (la que termina en «.example») como
    archivo de entorno local, sin esa terminación;
  - poner la clave en `ANTHROPIC_API_KEY`;
  - reiniciar.
- **Por qué no se adapta el test**: excluir los mensajes de ese test lo debilitaría, y la garantía
  del #6 vale más que nombrar el archivo en el mensaje.
- **Mitigación**: la sección «Interfaz de chat» del README (T037) da los pasos con los nombres
  exactos.
- **Documentos actualizados en el mismo commit**: spec (US3-2), este plan, `research.md` (R8) y
  `tasks.md` (reglas y T011).

Relacionado, sin ser una desviación: `test_cargar_entorno_solo_se_llama_desde_el_punto_de_entrada`
del #6 fija `["__main__.py"]`. Con el chat como segundo punto de entrada (R8), en T035 pasa a
`["__main__.py", "chat.py"]`, y se anota en la tabla de T032.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
