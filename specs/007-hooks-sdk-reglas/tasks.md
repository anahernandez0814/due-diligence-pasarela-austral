---

description: "Lista de tareas del ticket #7, hooks del SDK de las reglas de negocio 1, 2 y 3"
---

# Tasks: Hooks del SDK: reglas de negocio 1, 2 y 3 garantizadas

**Input**: documentos de diseño en `specs/007-hooks-sdk-reglas/`: [plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/hooks.md](contracts/hooks.md) y [quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/ y
quickstart.md.

**Tests**: obligatorios (constitución X). Van junto a cada módulo, en `src/due_diligence/test_*.py`, y
se escriben antes que el módulo (deben fallar primero). Ninguno llama al modelo ni a la red (SC-008):
usan el ejecutor y la sesión simulados (R4) y mensajes del SDK construidos con sus propias clases.

**Organization**: una fase por historia de la spec, con dos fases previas y tres finales:

1. Setup: fase 1. Fundamentos (eventos, libro, fuente única de la identificación, hooks base, sesión
   simulada): fase 2. *Parada de revisión A* al final de la fase 2.
2. US1 regla I.1 (P1): fase 3. US2 regla I.2 (P1): fase 4. US3 regla I.3 (P1): fase 5.
   US4 cierre garantizado (P1): fase 6.
3. US5 hooks por agente, estado compartido y casos obligatorios (P1): fase 7. *Parada de revisión B*.
4. US6 modo de demostración e instrucciones (P2): fase 8.
5. Sondeo, documentación y descripción del servidor: fase 9. Validación: fase 10.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La verificación del
cierre de #7 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US6).
- **[MANUAL]**: la hace la analista, en una sesión nueva de Claude Code abierta en la raíz y con el
  modelo real. Claude se detiene y espera su confirmación.
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md) o Q# del
  [quickstart](quickstart.md).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Ningún valor con forma real** (tarjeta, NIT, cédula o credencial) se escribe en tareas, tests,
  código ni documentación. Los tests usan los identificadores y nombres ficticios del #5
  (`CO-TV-0001`, `Tienda Verde SAS`, `CO-PL-0003`, `PE-0003`, etc.), sin ninguna secuencia de 6 o más
  dígitos seguidos (FR-016, principio VII).
- **Todo en español**: motivos, eventos, instrucciones y documentación (FR-017). Los motivos que ve el
  modelo **no repiten el nombre ni el identificador consultados** (FR-016): los tests lo comprueban
  con un nombre ficticio que no debe aparecer en el motivo.
- **API de `claude-agent-sdk` 0.2.168 (R1 a R3)**: `HookMatcher`, `ClaudeAgentOptions(hooks=...)`;
  entradas `PreToolUse` (`tool_name`, `tool_input`), `PostToolUse` (`tool_response`: texto o lista de
  bloques), `PostToolUseFailure` (`error`: texto JSON) y `Stop` (`stop_hook_active`); salidas solo con
  `permitir()`, `denegar(motivo)` y `bloquear_cierre(motivo)` (una forma inválida **deja pasar la
  acción**).
- **Un solo intérprete y un solo lector** (R1, R4, R7): `estado.derivar_comercio` es el único que
  interpreta la respuesta del registro, y `ejecutor.interpretar_resultado` el único que lee lo que
  devuelve una herramienta. No se escribe una segunda copia de ninguno ni de la comparación de
  consultas con entidades (`reglas.consulta_coincide`).
- **Los hooks fallan cerrados** (FR-012, R2) y **no hay forma de desactivarlos**, ni en el modo de
  demostración. Ningún `except` los silencia sin sellar el libro.
- **El código no controla el ciclo** (FR-010 del #6): `test_sin_control_propio.py` sigue en verde; el
  contador de devoluciones del `Stop` es un campo del libro, no un `while` ni una comparación de
  texto, y `MAX_CIERRES_IMPEDIDOS` vive solo en `configuracion.py`.
- **No se escribe en el código el nombre del archivo de variables de entorno** (R8 del #6). Ningún test
  ni comando de estas tareas lo lee.
- **Commits** por partes lógicas en la rama `007-hooks-sdk-reglas`, nunca en `main`, y sin
  `git commit --amend`. Un commit nuevo invalida el veredicto del anterior, así que **ningún commit va
  después de la revisión** de `/abrir-pr`.
- **Formato**: el hook de #3 formatea cada `.py` escrito o editado. Cada fase de código termina con
  `uv run ruff format .` y `uv run ruff check .`.
- **Tests**: `uv run pytest src/due_diligence`.
- `src/due_diligence/*.py` y `pyproject.toml` se editan con spec, plan y tareas de la rama
  commiteados, que deja hecho T001. `DECISIONES.md` no se recorta: solo se amplía.
  **`docs/bitacora-decisiones.md` no se edita en este ticket**: la actualiza la analista desde otro
  chat.

---

## Fase 1: Setup

- [X] T001 Confirmar que la rama es `007-hooks-sdk-reglas` y commitear este `tasks.md` (la spec y el
  plan ya están en `0990797` y `b36b305`). Sin eso, la guarda de #3 bloquea escribir en
  `src/due_diligence/`. Mensaje convencional en español.
- [X] T002 Línea base: `uv run pytest` y `uv run ruff check .` en verde antes de tocar nada. Anotar
  aquí el número de tests que pasan (referencia para T052 y T053): **2071**.

---

## Fase 2: Fundamentos (bloquean todas las historias)

**Propósito**: lo que usan todas las historias: tipos de evento, libro de reglas, constantes, la
**fuente única de la identificación** (R4), los hooks base y la sesión simulada que permite probar
sin modelo. Tests primero.

### Eventos, libro y configuración

- [X] T003 Ampliar `src/due_diligence/test_eventos_estado.py` (R12, data-model): los seis tipos nuevos
  (`bloqueo_regla`, `cierre_impedido`, `cierre_sin_escalar`, `fallo_de_hook`,
  `escalamiento_registrado`, `modo_demostracion`) son válidos y uno desconocido sigue rechazándose;
  `Evento` tiene `regla` (`None` por defecto, así los eventos del #6 no cambian) y
  `registrar(tipo, frente=None, detalle="", regla=None)` lo guarda; un evento con `regla="I.1"` lo
  conserva en `eventos()`.
- [X] T004 [P] Editar `src/due_diligence/eventos.py`: añadir los seis tipos como constantes y a
  `TIPOS`, el campo `regla: str | None = None` a `Evento` (dataclass congelada, al final para no
  romper llamadas posicionales) y el parámetro `regla` a `RegistroEventos.registrar`. Hace pasar T003.
- [X] T005 Escribir `src/due_diligence/test_libro.py` (data-model, FR-011): un `LibroReglas` nuevo
  empieza vacío (`consultas_listas`, `coincidencias`, `consultas_riesgo`, `escalamientos` son listas
  vacías, `cierres_impedidos == 0`, `fallo_de_hook is None`); dos libros **no comparten** listas
  (modificar uno no cambia el otro); `ConsultaListas` guarda `tipo` (`comercio` o `persona`),
  `nombre`, `identificador` (cada uno `str | None`) y `resultado` (`coincidencias` o
  `sin_coincidencias`); `Coincidencia` guarda `clave` (`listas:<tipo>:<identificador o nombre
  normalizado>`), `tipo`, `lista`, `fuente` y `fecha`; `ConsultaRiesgo` guarda `categoria` y `nivel`
  (`alto`, `medio`, `bajo` o `None` si la categoría fue desconocida); la copia profunda del libro es
  independiente.
- [X] T006 [P] Crear `src/due_diligence/libro.py` con `LibroReglas`, `ConsultaListas`, `Coincidencia`
  y `ConsultaRiesgo` tal como los define `data-model.md`, sin estado de módulo (FR-011). Hace pasar
  T005.
- [X] T007 Configuración (FR-007, FR-014, R3, R11): primero ampliar
  `src/due_diligence/test_configuracion.py` con: `MAX_CIERRES_IMPEDIDOS == 3` y es **menor** que
  `MAX_TURNOS_SEGURIDAD`; `modo_demostracion(entorno)` es `True` solo con el valor exacto `"1"` (con
  `"0"`, `"true"`, vacío o ausente es `False`) y con un `entorno` dado lo lee de ahí y con `entorno=None` lee `os.environ` (el patrón de `_modelo`, que necesita Q5);
  la variable `PASARELA_MODO_DEMO_HOOKS` **no** está en `VARIABLES_PASARELA` (no se reenvía al
  servidor). Después editar `src/due_diligence/configuracion.py`: añadir `MAX_CIERRES_IMPEDIDOS = 3`
  con un comentario que diga que es una protección de seguridad y no el mecanismo de la regla (igual
  que `MAX_TURNOS_SEGURIDAD`), `VARIABLE_MODO_DEMO` y `modo_demostracion(entorno=None)`.

### Reglas: constantes y comparación de consultas

- [X] T008 Escribir la primera parte de `src/due_diligence/test_reglas.py` (R7, R8, R10): 
  `ALTO_RIESGO == ("apuestas", "criptoactivos", "suplementos dietarios", "venta de medicamentos")`
  (constante en el código, FR-008); `RECOMENDACIONES == ("habilitar", "no_habilitar",
  "decide_cumplimiento")`; `normalizar_recomendacion` devuelve el valor para `"Habilitar"`,
  `" no habilitar "`, `"No-Habilitar"` y `"DECIDE_CUMPLIMIENTO"`, y `None` para `"aprobar"`, `""`,
  `None`, `"habilitar con reservas"` y un número. `consulta_coincide(consulta, entidad, tipo)` con la
  tabla (cada fila un caso parametrizado): tipo igual y nombre igual con otras mayúsculas, tildes o
  puntuación → coincide; mismo nombre con tipo distinto (consulta `persona` para el comercio) → no;
  identificador igual (`igual_identificador`) → coincide; consulta con los dos y uno no coincide →
  no; consulta sin ninguna clave → no; **consulta con `identificador` para un representante que el
  registro devolvió sin identificador → no coincide** (test explícito, el representante del #5 sin
  identificador, aunque el nombre coincida); consulta con solo `nombre` para un representante con
  identificador → coincide por el nombre. Ningún caso usa valores con forma real.
- [X] T009 Crear `src/due_diligence/reglas.py` con `ALTO_RIESGO`, `RECOMENDACIONES`,
  `normalizar_recomendacion` y `consulta_coincide(consulta, entidad, tipo)` según R7: el tipo debe ser
  el esperado, la consulta debe traer al menos una clave y **cada clave que trae debe existir en la
  entidad y coincidir**, con `igual` e `igual_identificador` de `servidor_mcp.normalizar` (no hay
  otra normalización). Funciones puras, sin SDK ni estado. Hace pasar T008.

### Fuente única de la identificación (R4)

- [X] T010 Escribir `src/due_diligence/test_estado_identificacion.py` (R4, FR-001, FR-013): 
  `EstadoCaso.registrar_identificacion(respuesta)` guarda **el resultado de `derivar_comercio`**
  (probar con un `monkeypatch` que `derivar_comercio` se llama una vez por consulta y que el estado
  no interpreta la respuesta por su cuenta); `comercio` y `motivo_comercio` son propiedades:
  sin identificaciones y registro `terminado` → `None` con «El registro no devolvió datos.»; una
  coincidencia con registro `terminado` → el dict `{identificador, nombre, representante_legal}`; con
  el registro `no_terminado`, `en_curso`, `rechazado` o `sin_iniciar` → `None` con «El registro
  mercantil no terminó…»; varias coincidencias → `None` con «varias coincidencias»; ninguna →
  `None` con el motivo de `derivar_comercio`; fuentes que difieren → `None` con «difieren»; dos
  consultas que identifican comercios distintos → `None` con «comercios distintos: no se elige uno»; dos
  consultas que identifican al mismo → el comercio; una consulta con coincidencia y otra sin → no se
  elige la primera sin comprobar (mismo resultado que `_fijar_comercio` del #6); si ninguna tiene
  coincidencias el motivo es el de la primera; `reiniciar_identificacion()` vacía las identificaciones
  y deja `comercio` en `None`; **no existen** `fijar_comercio` ni `Delegador._fijar_comercio`
  (`not hasattr`); `instantanea()` copia también `identificaciones` y `libro`; `cierre_sin_escalar`
  empieza en `False`.
- [X] T011 Editar `src/due_diligence/estado.py` (R4, data-model): añadir `identificaciones`, `libro`
  (`LibroReglas`) y `cierre_sin_escalar`; convertir `comercio` y `motivo_comercio` en **propiedades
  derivadas** con la lógica de `Delegador._fijar_comercio` del #6, **movida** y no copiada; añadir
  `registrar_identificacion(respuesta)` (llama a `derivar_comercio`, que no cambia) y
  `reiniciar_identificacion()`; **eliminar** `fijar_comercio`. Hace pasar T010.

### Hooks base y sesión simulada

- [X] T012 Escribir la primera parte de `src/due_diligence/test_hooks.py` (R1, R2, contrato): 
  **salidas tipadas**: `permitir()` es `{}`; `denegar("x")` tiene
  `hookSpecificOutput.hookEventName == "PreToolUse"`, `permissionDecision == "deny"` y
  `permissionDecisionReason == "x"`; `bloquear_cierre("x")` es `{"decision": "block", "reason":
  "x"}`; la forma de cada una se valida contra los literales de
  `claude_agent_sdk.types.PreToolUseHookSpecificOutput` (los valores permitidos de
  `permissionDecision`) para que un cambio del SDK lo detecte. **`leer_respuesta`**: acepta
  `tool_response` como texto JSON (stdio) y como lista de bloques `[{"type": "text", "text": ...}]`
  (en proceso) y devuelve lo mismo que `ejecutor.interpretar_resultado` (se prueba con
  `monkeypatch` que delega en él y no hay un analizador propio); en `PostToolUseFailure` el texto JSON
  de `error` se lee con `es_error=True`. **`fallar_cerrado`**: un hook `PreToolUse` que lanza
  `RuntimeError` devuelve `denegar(...)` con un motivo genérico en español que no contiene el texto
  de la excepción, deja un evento `fallo_de_hook` y sella `libro.fallo_de_hook`; un `Stop` que lanza
  devuelve `bloquear_cierre(...)`; un `PostToolUse` o `PostToolUseFailure` que lanza devuelve `{}`,
  deja el evento y sella el libro. **Hook del registro**: con una respuesta de una sola coincidencia,
  `PostToolUse` llama a `estado.registrar_identificacion`; con una de varias coincidencias,
  una vacía o una ilegible, no identifica (el estado queda sin comercio, con el motivo).
  `PostToolUseFailure` del registro deja un evento y no identifica. **Cancelación (spec, caso límite)**: si el frente
  se cancela (`asyncio.CancelledError`) mientras un hook actualiza el estado, el estado queda consistente: la
  identificación se guarda completa o no se guarda (nunca una identificación a medias).
- [X] T013 Crear `src/due_diligence/hooks.py` (R2, R5, contrato): `permitir`, `denegar`,
  `bloquear_cierre`; `leer_respuesta` (reutiliza `ejecutor.interpretar_resultado`); `fallar_cerrado`
  (envoltorio de cada callback, con el comportamiento por evento de `contracts/hooks.md`);
  `HooksDelCaso(estado, eventos, entorno=None)` con `.subagente(frente)` y `.coordinador()` que
  devuelven el valor del parámetro `hooks` de `ClaudeAgentOptions`
  (`{evento: [HookMatcher(matcher=<nombre completo exacto>, hooks=[...])]}`). En esta tarea
  `.subagente(Frente.REGISTRO)` lleva `PostToolUse` y `PostToolUseFailure` sobre
  `mcp__pasarela__consultar_registro_mercantil`; el resto de agentes devuelve `{}` hasta sus
  historias. Hace pasar T012. No hay estado de módulo.
- [X] T014 Escribir `src/due_diligence/test_sesion_simulada.py` (R4): `SesionSimulada(opciones)` ejecuta,
  para cada llamada simulada a una herramienta, los hooks de `opciones.hooks` **en el orden del SDK**:
  `PreToolUse` coincidente; si alguno devuelve `deny`, la herramienta **no se ejecuta** y la llamada
  devuelve un resultado con `is_error` y el motivo (como medido en R2); si no, se ejecuta la función
  de la herramienta y se invoca `PostToolUse` con `tool_response` como **texto JSON** (o como lista de
  bloques si la llamada se declara «en proceso»), o `PostToolUseFailure` con `error` si la herramienta
  devolvió un error estructurado; los matchers son nombres exactos (una herramienta con otro nombre no
  dispara el hook); un hook que lanza una excepción **deja pasar la acción** (el SDK lo hace, R2), y
  la sesión lo reproduce para probar el envoltorio de T013; el `Stop` se evalúa con
  `sesion.terminar(ultimo_mensaje)`, que invoca los hooks de `Stop` y devuelve «terminó» o
  «continúa» con el motivo.
- [X] T015 [P] Editar `src/due_diligence/simulacion.py` (R4, R12, G1): añadir `SesionSimulada` (T014), con **implementaciones
  simuladas de las seis herramientas de la pasarela y de `delegar_frente`** (la de delegar llama a
  `caso.delegador.delegar`), y **los datos simulados de los casos**: respuestas del registro con dos comercios
  parecidos (`CO-AM-0004` y `CO-AM-0005`), con una coincidencia y representante (`CO-TV-0001`, `CO-TA-0002`) y con
  `CO-PL-0003` y su representante `PE-0003`; respuestas de riesgo (`alto` para «suplementos dietarios», `medio` y
  `bajo`, y `categoria_desconocida`); respuestas de listas con coincidencia de `PE-0003` y sin coincidencias; y
  las respuestas de `registrar_informe` y `escalar_a_cumplimiento` (éxito y error estructurado). Hacer
  que `EjecutorSimulado` reproduzca cada `Consulta` de su `ResultadoFrente` a través de la sesión de las
  `opciones` que recibe, para que los hooks de ese agente vean las llamadas. Si `opciones.hooks` es
  `None` el comportamiento no cambia. Los datos son los ficticios del #5. Hace pasar T014.
- [X] T016 Adaptar los tests del #6 a la fuente única (R4, R7; **primera mitad**, en rojo): actualizar los tests del #6 que
  dependían de `fijar_comercio` o de que el `Delegador` derivara el comercio:
  `src/due_diligence/test_delegacion.py` (el auxiliar `_crear` construye el `Delegador` con
  `HooksDelCaso(estado, eventos)` y opciones de `configuracion.opciones_subagente(frente, "x",
  hooks=hooks.subagente(frente))`; las pruebas con `estado.comercio` de las líneas ≈ 488-764 pasan
  por la sesión simulada), `src/due_diligence/test_contexto.py` (línea ≈ 27, usar
  `registrar_identificacion` en lugar de `fijar_comercio`) y `src/due_diligence/test_eventos_estado.py`
  (líneas ≈ 193 y 208-211: sustituir las pruebas de `fijar_comercio` por las de T010). Añadir a
  `test_delegacion.py`: al volver a delegar el registro con otra entrada se llama a
  `reiniciar_identificacion` **antes** de lanzar el frente y se conserva el comercio anterior para
  decidir la invalidación de `listas` (`frente_invalidado` como en el #6). Estos tests fallan hasta T016b.
- [X] T016b Adaptar la delegación a la fuente única (R4, R7; **segunda mitad**): editar
  `src/due_diligence/delegacion.py`: **eliminar** `_fijar_comercio`; en `_ejecutar` del registro,
  capturar `estado.comercio` y llamar a `reiniciar_identificacion()` antes de lanzar; en `_concluir`,
  comparar con el comercio capturado para invalidar `listas`; `_falta_en_listas` usa
  `reglas.consulta_coincide` (una sola comparación, R7) y no su propio `consultada`. Hace pasar T016: toda la suite del #6
  vuelve a verde.
- [X] T017 Fase 2 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest` en verde.
  Comprobar a mano que `derivar_comercio` aparece **una sola vez** en `src/due_diligence/estado.py` como
  definición y no se reimplementa en `hooks.py` ni `delegacion.py` (`Grep` de `coincidencias` en
  `src/due_diligence/*.py` fuera de tests). **PARADA DE REVISIÓN A.**

---

## Fase 3: US1 Regla I.1, listas solo con identificación unívoca (P1)

**Meta**: la consulta de listas y la delegación de listas se bloquean si el comercio no está identificado
de forma unívoca. **Prueba independiente**: con la sesión simulada se prueba cada situación del registro
(US1-1 a US1-11) sin modelo.

- [X] T018 [US1] Ampliar `src/due_diligence/test_reglas.py` (R6, R7, FR-002, FR-003, FR-018):
  `permite_listas(estado, entrada)`: sin registro delegado → `(False, motivo)` con «Aún no hay un comercio
  identificado de forma unívoca en el registro mercantil.»; varias coincidencias → no, con el motivo de
  pedir el identificador al analista; ninguna coincidencia → no; comercio identificado y consulta del
  comercio con tipo `comercio` → sí; del representante con tipo `persona` → sí; el nombre del
  comercio con tipo `persona`, o el del representante con tipo `comercio` → no (US1-8); un nombre ajeno →
  no; consulta con las claves en otro formato (mayúsculas, tildes, puntuación) → sí; el motivo **no
  contiene** el nombre ni el identificador consultados. `permite_delegar_listas(estado)`: registro
  `sin_iniciar`, `rechazado` o `no_terminado` → no; `terminado` sin comercio único → no, con el motivo de
  `estado.motivo_comercio` (varias coincidencias: pide el identificador); `terminado` con comercio → sí;
  `en_curso` → **sí** (la herramienta espera; US1-10).
- [X] T019 [US1] Añadir a `src/due_diligence/reglas.py` `permite_listas` y `permite_delegar_listas` (R6, R7)
  usando solo `estado.comercio`, `estado.motivo_comercio` y la situación del frente de registro: no
  leen `estado.consultas` ni `estado.resultados`. Hace pasar T018.
- [X] T020 [US1] Ampliar `src/due_diligence/test_hooks.py` (FR-002, FR-018, FR-012, US1): el `PreToolUse` de
  `mcp__pasarela__consultar_listas_restrictivas` (subagente de listas) devuelve `permitir()` o `denegar()`
  según `permite_listas`, deja un evento `bloqueo_regla` con `regla="I.1"` y `frente=listas` al
  denegar, y **no consulta la fuente** (en la sesión simulada la herramienta no se ejecuta, US1-7); el
  `PreToolUse` de `mcp__delegacion__delegar_frente` (coordinador) solo actúa si `tool_input.frente` es
  `listas` (normalizado: `"Listas"` también); cualquier otro frente se permite sin leer el estado; deniega
  con `regla="I.1"`; con `libro.fallo_de_hook` sellado ambos deniegan con «No se pudo registrar un hecho de
  la regla; se bloquea por precaución.»; si `permite_listas` lanza una excepción, el envoltorio deniega.
  **Entradas malformadas (FR-012)**: `tool_input` que no es un `dict`, sin `frente`, o con `nombre`/`identificador` que no son texto → el hook deniega
  (fallo cerrado), sin lanzar. **Carrera (R6)**: con el registro `sin_iniciar` el hook de `delegar_frente` deniega con un motivo que pide
  delegar primero el registro, sin cambiar el estado.
- [X] T021 [US1] Añadir a `src/due_diligence/hooks.py` los hooks `PreToolUse` de la consulta de listas y de
  `delegar_frente`, y registrarlos en `HooksDelCaso`: `.subagente(Frente.LISTAS)` lleva el de la consulta;
  `.coordinador()` lleva el de `delegar_frente` (R5, contrato). Hace pasar T020.
- [X] T022 [US1] Ampliar `src/due_diligence/test_hooks_sesiones.py` (nuevo) con US1 de extremo a extremo en
  la sesión simulada: registro con una coincidencia y representante → listas por el comercio y por el
  representante se permiten; registro con dos comercios de nombres casi idénticos (`CO-AM-0004` y
  `CO-AM-0005`) → la consulta de listas se bloquea, la herramienta de listas no se ejecuta y el
  coordinador no puede delegar listas; registro sin coincidencias → bloqueo; consulta por un nombre
  ajeno → bloqueo.

---

## Fase 4: US2 Regla I.2, coincidencia en listas impide habilitar y exige escalar (P1)

**Meta**: toda coincidencia queda registrada; `habilitar` se rechaza y el informe exige escalar antes.
**Prueba independiente**: representante con coincidencia (`PE-0003`) y un informe `habilitar`.

- [X] T023 [US2] Ampliar `src/due_diligence/test_reglas.py` (R9, R10, FR-005, FR-006):
  `causas_vigentes(libro)` es un subconjunto de las **claves fijas** `coincidencia_comercio`, `coincidencia_representante`
  y `alto_riesgo` (sin nombres ni identificadores; `alto_riesgo` lo prueba US3); una coincidencia de tipo `persona` da
  `coincidencia_representante`; `reglas_de(causas)` da `I.2` para las coincidencias, `I.3` para `alto_riesgo` y `I.2, I.3` si hay de
  ambas (I3); `requiere_escalamiento` es `bool(causas_vigentes)`; `escalamiento_cubre`: vacío ⇒ `True`;
  con una coincidencia y sin escalamientos → `False`; con una instantánea que contiene la causa → `True`;
  **una coincidencia nueva posterior a la instantánea → `False`** (hace falta escalar de nuevo);
  `evaluar_informe(estado, entrada)` (parte de la regla 2): recomendación fuera de `RECOMENDACIONES` →
  motivo con los tres valores válidos aunque ninguna regla aplique; con coincidencia, `habilitar` →
  motivo «Hay una coincidencia en listas restrictivas…»; con coincidencia **sin escalar**, **cualquier**
  recomendación (`no_habilitar` y `decide_cumplimiento` también) → motivo «El caso requiere escalamiento…
  por: coincidencia del comercio en listas restrictivas» (US2-3, solo etiquetas fijas); con coincidencia y escalamiento cubierto, `no_habilitar` y
  `decide_cumplimiento` → se aceptan (US2-4); acumula todos los motivos que apliquen; el motivo no repite
  nombres ni identificadores.
- [X] T024 [US2] Añadir a `src/due_diligence/reglas.py` `causas_vigentes`, `requiere_escalamiento`,
  `escalamiento_cubre` y la parte de la regla 2 de `evaluar_informe` (devuelve la lista de motivos; vacía
  si se acepta). Hace pasar T023.
- [X] T025 [US2] Ampliar `src/due_diligence/test_hooks.py` (FR-004, FR-006, FR-013): `PostToolUse` de
  listas guarda en `libro.consultas_listas` una `ConsultaListas` por cada respuesta válida y, por cada
  hecho de una respuesta `coincidencias`, una `Coincidencia` con la fuente y la fecha de `metadatos`
  (US2-1); una respuesta `sin_coincidencias` no añade coincidencias (US2-6); **una consulta con error
  llega por `PostToolUseFailure`, deja un evento y no entra al libro** (R1); una coincidencia **no se
  borra** aunque el registro cambie de comercio; `PostToolUse` de `escalar_a_cumplimiento` con resultado
  `caso_escalado` guarda en `libro.escalamientos` la instantánea de `causas_vigentes` y deja el evento
  `escalamiento_registrado`; con error (por `PostToolUseFailure`) o con un resultado que no es
  `caso_escalado` no cuenta; el `PreToolUse` de `registrar_informe` devuelve `denegar(" ".join(motivos))`
  con la regla de `reglas_de(causas)` (`I.2`, `I.3` o `I.2, I.3`, I3) si `evaluar_informe` da motivos y `permitir()` si no, y con
  `libro.fallo_de_hook` deniega; con `recomendacion` que no es texto o `tool_input` malformado, deniega (FR-012).
- [X] T026 [US2] Añadir a `src/due_diligence/hooks.py`: `PostToolUse` y `PostToolUseFailure` de listas
  (subagente de listas), `PostToolUse` y `PostToolUseFailure` de `escalar_a_cumplimiento` y `PreToolUse`
  de `registrar_informe` (coordinador). Hace pasar T025.
- [X] T027 [US2] Ampliar `src/due_diligence/test_hooks_sesiones.py` con el caso (c) a nivel de hooks: registro
  con representante `PE-0003` de `CO-PL-0003`; listas devuelve coincidencia para la persona; el
  coordinador intenta `registrar_informe` con `habilitar` → rechazado (is_error con el motivo); intenta
  `no_habilitar` sin escalar → rechazado; llama a `escalar_a_cumplimiento` → se registra; intenta
  `decide_cumplimiento` o `no_habilitar` → se acepta.

---

## Fase 5: US3 Regla I.3, alto riesgo o categoría sin determinar (P1)

**Meta**: `habilitar` se rechaza para alto riesgo, categoría no determinada o sin consulta de listas válida.
**Prueba independiente**: categoría «suplementos dietarios» (caso a) y bajo riesgo sin hallazgos (caso b).

- [X] T028 [US3] Ampliar `src/due_diligence/test_reglas.py` (R8, FR-005, FR-008, FR-009):
  `es_alto_riesgo`: categoría en `ALTO_RIESGO` → `True` aunque el nivel diga «medio»; con otras
  mayúsculas o sin tildes («Suplementos Dietarios») → `True` (US3-7, `igual`); `nivel == "alto"` para una
  categoría fuera de la constante → `True` (US3-9); **persistente**: una consulta de riesgo alto y otra
  posterior de nivel bajo → `True` (US3-8); sin consultas → `False`. `categoria_determinada`: alto riesgo
  → `True`; última consulta con nivel → `True`; sin consultas → `False`; última desconocida → `False`;
  última con error (no entra al libro) con una anterior conocida → se evalúa la última **registrada**;
  conocida baja y luego desconocida → `False`. `causas_vigentes` incluye `"alto_riesgo"` solo si
  `es_alto_riesgo`. `evaluar_informe` con `habilitar`: alto riesgo → «La categoría es de alto riesgo: la
  decisión es de un oficial de cumplimiento.»; categoría no determinada → «La categoría del caso no quedó
  determinada.»; sin consulta de listas válida del comercio → «Falta la consulta de listas
  restrictivas…»; con representante, falta la del representante; sin representante, basta la del comercio;
  una consulta con **tipo incorrecto o de otro comercio** (que ya no coincide con `estado.comercio`) no
  cuenta (US3-10); bajo riesgo, categoría determinada, listas consultadas para comercio y representante y sin
  coincidencias → se acepta `habilitar` y no requiere escalamiento (US3-6, caso b); alto riesgo sin escalar:
  `no_habilitar` también se rechaza (US3-3); escalado: `decide_cumplimiento` se acepta (US3-2).
- [X] T029 [US3] Ampliar `src/due_diligence/reglas.py`: `es_alto_riesgo`, `categoria_determinada`,
  `causas_vigentes` con `alto_riesgo` y las condiciones de `habilitar` de `evaluar_informe` (R8, orden y
  acumulación de `data-model.md`). Las consultas de listas se comparan con `consulta_coincide` contra
  `estado.comercio` vigente. Hace pasar T028.
- [X] T030 [US3] Ampliar `src/due_diligence/test_hooks.py`: `PostToolUse` de
  `mcp__pasarela__consultar_riesgo_categoria` (subagente de categoría) guarda una `ConsultaRiesgo` con
  `categoria` y `nivel` para `categoria_conocida` y con `nivel=None` para `categoria_desconocida`; una
  respuesta con error llega por `PostToolUseFailure`, deja evento y no entra; el hook del subagente de
  noticias no existe (`.subagente(Frente.NOTICIAS) == {}`, una mención en noticias no es una coincidencia
  en listas).
- [X] T031 [US3] Añadir a `src/due_diligence/hooks.py` los hooks `PostToolUse` y `PostToolUseFailure` de
  riesgo en `.subagente(Frente.CATEGORIA)`. Hace pasar T030.
- [X] T032 [US3] Ampliar `src/due_diligence/test_hooks_sesiones.py` con los casos (a) y (b) a nivel de hooks:
  (a) registro de `CO-TV-0001`, riesgo «suplementos dietarios» alto y listas sin coincidencias:
  `habilitar` rechazado; `no_habilitar` rechazado sin escalar; tras escalar, `decide_cumplimiento`
  aceptado; (b) `CO-TA-0002` de bajo riesgo, sin hallazgos y con listas del comercio y del representante:
  `habilitar` aceptado sin escalar.

---

## Fase 6: US4 Cierre garantizado (P1)

**Meta**: el coordinador no puede terminar un caso que requiere escalamiento sin haber escalado.
**Prueba independiente**: `Stop` simulado en un caso con coincidencia.

- [X] T033 [US4] Ampliar `src/due_diligence/test_reglas.py` (R3, R9): `evaluar_cierre(estado)` devuelve
  `None` si no requiere escalamiento o está cubierto, y el motivo «El caso requiere escalamiento a
  cumplimiento y aún no se ha escalado por: <causas>.» con las etiquetas fijas de cada causa (coincidencia del comercio,
  coincidencia del representante, alto riesgo; US4-1), y el motivo **no contiene** el nombre ni el identificador
  de ninguna consulta (FR-016) si no.
- [X] T034 [US4] Añadir `evaluar_cierre` a `src/due_diligence/reglas.py`. Hace pasar T033.
- [X] T035 [US4] Ampliar `src/due_diligence/test_hooks.py` (R3, FR-007, Q7): hook `Stop` del coordinador: caso
  sin escalamiento requerido → `permitir()`; con escalamiento cubierto → `permitir()`; requerido y sin
  escalar → `bloquear_cierre(motivo)`, `libro.cierres_impedidos += 1` y un evento `cierre_impedido` con la
  regla (US4-1, US4-4); **no usa `stop_hook_active`** (se llama con `True` y con `False` y decide igual);
  a la devolución número `MAX_CIERRES_IMPEDIDOS + 1` → `permitir()`, `estado.cierre_sin_escalar = True` y
  un evento `cierre_sin_escalar` (US4-5); un `Stop` que lanza una excepción → `bloquear_cierre` y cuenta
  contra el límite; con `libro.fallo_de_hook` y escalamiento requerido el cierre se bloquea igual; el
  límite usado es la constante real de `configuracion.py`, y con 3 devoluciones no se alcanza
  `MAX_TURNOS_SEGURIDAD`. **Un `Stop` de subagente no existe**: `.subagente(f)` no contiene la clave
  `"Stop"` para ningún frente (US5-5).
- [X] T036 [US4] Añadir a `src/due_diligence/hooks.py` el hook `Stop` del coordinador y registrarlo en
  `.coordinador()`. El contador es `libro.cierres_impedidos`, sin `while` ni comparación de texto. Hace
  pasar T035.
- [X] T037 [US4] Ampliar `src/due_diligence/test_hooks_sesiones.py`: con `SesionSimulada.terminar`, un caso con
  coincidencia en `PE-0003` intenta terminar → «continúa» con el motivo; tras `escalar_a_cumplimiento`
  → «terminó»; un coordinador simulado que insiste en terminar sin escalar recibe el motivo
  `MAX_CIERRES_IMPEDIDOS` veces y a la siguiente termina con `cierre_sin_escalar` (Q7).

---

## Fase 7: US5 Hooks por agente, estado compartido y casos obligatorios (P1)

**Meta**: el `Caso` reparte los hooks por agente con el mismo estado; los casos (a), (b), (c) y (e) pasan de
extremo a extremo. **Prueba independiente**: ejecutor y sesión simulados, sin modelo.

- [X] T038 [US5] Ampliar `src/due_diligence/test_coordinador.py` (R5, FR-010): sustituir
  `test_los_hooks_se_reparten_al_coordinador_y_a_cada_subagente` (línea ≈ 290) por pruebas del reparto
  de `contracts/hooks.md`: las opciones del coordinador llevan `PreToolUse` para
  `mcp__delegacion__delegar_frente` y `mcp__pasarela__registrar_informe`, `PostToolUse` y
  `PostToolUseFailure` para `escalar_a_cumplimiento` y `Stop`; el subagente de registro, solo `PostToolUse`
  y `PostToolUseFailure` del registro; el de listas, `PreToolUse`, `PostToolUse` y `PostToolUseFailure`
  de listas; el de categoría, los de riesgo; el de noticias, ninguno; **ningún subagente tiene `Stop`** y
  el `PreToolUse` de listas **solo** está en el subagente de listas; los matchers son nombres completos
  exactos; todos los hooks cierran sobre **el mismo** `caso.estado` (un cambio en el estado desde un hook
  del registro lo ve el de listas, US5-1) y dos `Caso` no comparten estado ni libro (US5-3);
  `Caso` y `ejecutar_caso` **ya no aceptan** el parámetro `hooks`; `Caso.completo` es `False` si algún frente
  no está `terminado`, si la terminación no es normal, si `estado.cierre_sin_escalar` o si
  `estado.libro.fallo_de_hook` existe (un `PostToolUse` que falló pudo dejar sin registrar una coincidencia);
  `True` solo si ninguna de esas cosas ocurre.
- [X] T039 [US5] Ampliar `src/due_diligence/test_configuracion.py`: `opciones_coordinador` y
  `opciones_subagente` siguen aceptando `hooks` (la construcción es neutral) y lo pasan sin cambios; el
  test `test_los_hooks_se_reparten_a_todas_las_opciones` (línea ≈ 88) se conserva para esa función.
- [X] T040 [US5] Editar `src/due_diligence/coordinador.py` (R5): `Caso` crea un `HooksDelCaso(self.estado,
  self._eventos, self.entorno)` y usa `.coordinador()` en `opciones_coordinador` y `.subagente(frente)` en
  `_opciones_subagente` (líneas ≈ 105 y 112 del #6, que hoy pasan el mismo `self.hooks` a todos); eliminar
  el parámetro `hooks` de `Caso` y de `ejecutar_caso`; añadir la propiedad `Caso.completo` (data-model).
  Hace pasar T038 y T039.
- [X] T041 [US5] Escribir `src/due_diligence/test_casos_reglas.py` con los **casos de prueba obligatorios** del
  caso completo (`Caso` con ejecutor simulado y sesiones simuladas, hooks reales; Q2). **El coordinador simulado pasa por
  `SesionSimulada(caso.opciones_coordinador())`** (G1): cada llamada del guion a `delegar_frente`, `registrar_informe` y
  `escalar_a_cumplimiento`, y su fin de turno, ejecuta los hooks del coordinador como el SDK (los datos y las
  herramientas simuladas son los de T015); se añade a `simulacion.py` un `CoordinadorSimulado` que ejecuta un guion de
  llamadas por esa sesión y alimenta `Caso.ejecutar` en lugar de `consulta`: **(a)** `CO-TV-0001` con «suplementos dietarios»: el modelo simulado intenta
  `habilitar` → rechazado; intenta cerrar sin escalar → «continúa»; escala; registra `decide_cumplimiento`
  → aceptado; `Caso.completo` verdadero con los frentes terminados; **(b)** `CO-TA-0002`, bajo riesgo,
  sin hallazgos y con listas del comercio y del representante: `habilitar` aceptado, sin escalar y el
  cierre permitido; **(c)** `CO-PL-0003` con el representante `PE-0003` en listas: `habilitar` rechazado, no
  se puede cerrar sin escalar, tras escalar se acepta un informe `no_habilitar` o `decide_cumplimiento`;
  **(e)** nombres casi idénticos en el registro (`CO-AM-0004` y `CO-AM-0005`): delegar `listas` se bloquea
  (hook de `delegar_frente`), la consulta de listas se bloquea (hook de listas), la herramienta de listas
  **no se ejecuta** y los eventos muestran `bloqueo_regla` con `regla="I.1"`; el rechazo de `habilitar` del caso (a) lleva `I.3` y el del caso (c),
  `I.2` (I3); además, para cada caso, los
  eventos son legibles en orden por `secuencia` y cada bloqueo trae su regla y un motivo en español
  (SC-007). Estos son los casos (a), (b), (c) y (e) de la constitución X.
- [X] T042 [US5] Ampliar `src/due_diligence/test_hooks_sesiones.py` (US5-1, US5-2, US5-4, SC-006): frentes que
  corren en `asyncio` como sesiones separadas con `EjecutorSimulado`: el hook del subagente de listas ve
  la identificación que escribió el de registro; el hook del coordinador ve la coincidencia que
  escribió el de listas; **dos `Caso` a la vez** (con `asyncio.gather`) con comercios distintos no se
  mezclan (uno identifica y registra una coincidencia, el otro no ve nada); el estado se alimenta de la
  respuesta de la herramienta y **no de lo que el modelo transcriba** (un resumen del subagente que dice
  «sin coincidencias» no cambia una coincidencia registrada por el hook).
- [X] T043 [US5] Si `src/due_diligence/__main__.py` muestra los eventos del caso, mostrar también `regla` y el
  motivo de los eventos `bloqueo_regla`, `cierre_impedido`, `cierre_sin_escalar` y `fallo_de_hook`, para que
  se vea en el chat qué se bloqueó y por qué (VI); ampliar `src/due_diligence/test_main.py` con una
  ejecución simulada que muestre un bloqueo. No cambia lo que ya imprimía.
- [X] T044 [US5] Fase 7 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest` en verde.
  **PARADA DE REVISIÓN B.**

---

## Fase 8: US6 Modo de demostración e instrucciones (P2)

**Meta**: se retira la prohibición de decidir, la instrucción mínima guía el cierre y el modo de demostración
quita las reglas del prompt sin tocar los hooks. **Prueba independiente**: textos de las instrucciones y un
modelo simulado que intenta las tres acciones.

- [X] T045 [US6] Reescribir en `src/due_diligence/test_coordinador.py` los tests que citan la prohibición
  (líneas ≈ 16, 138-144 y 170-171 del #6, R11): ya **no** existe `PROHIBICION_DECISION` y las
  instrucciones del coordinador no contienen «NO llames a registrar_informe», «aún no está disponible» ni «No
  decidas la habilitación»; sí contienen la instrucción mínima (FR-019): escalar con
  `escalar_a_cumplimiento` si hay coincidencia en listas o alto riesgo, registrar el informe al final con
  `registrar_informe` y una recomendación **exactamente** `habilitar`, `no_habilitar` o
  `decide_cumplimiento`, y cuándo usar cada una: caso escalado (coincidencia o alto riesgo) →
  `decide_cumplimiento`; `no_habilitar` para un caso que no requiere escalamiento y no se habilita;
  `habilitar` solo si no hay coincidencia, no es de alto riesgo y la categoría quedó determinada; no
  mencionan tickets; hablan de usted; contienen la regla 3 (varias coincidencias) y la regla de delegar
  listas tras el registro. Las instrucciones de los cuatro subagentes **no cambian**
  (`test_contexto.py` sigue igual: no contienen las reglas 1 a 3).
- [X] T046 [US6] Escribir `src/due_diligence/test_modo_demo.py` (R11, FR-014, SC-005): con
  `instrucciones_coordinador(demo=True)` **no** aparecen la regla 3 del coordinador (no seguir con
  listas ante varias coincidencias) ni la instrucción de escalar, pero sí la delegación, el resumen y la
  instrucción de registrar el informe con los tres valores; con `demo=False` son las instrucciones
  normales; `Caso` con `entorno={"PASARELA_MODO_DEMO_HOOKS": "1"}` usa las de demo y deja el evento
  `modo_demostracion` al iniciar (con otro valor o sin la variable, no); **los hooks son los mismos con
  y sin demo** (mismas claves y matchers, y las tres acciones prohibidas se bloquean con un modelo
  simulado en modo demo: delegar listas sin registro identificado, `registrar_informe` con `habilitar` en
  alto riesgo y con coincidencia, y terminar sin escalar); `Caso`, `ejecutar_caso` y `opciones_*` del caso **no aceptan un parámetro `hooks`** (T038) y las claves y matchers de
  los hooks son idénticos con y sin demo (no hay forma de desactivarlos).
- [X] T047 [US6] Editar `src/due_diligence/coordinador.py`: eliminar `PROHIBICION_DECISION` y la regla 5
  («No decidas la habilitación del comercio»); la regla 4 pasa a ser la instrucción mínima de T045; el
  resumen al analista (regla 5) se conserva sin la frase prohibida; añadir
  `instrucciones_coordinador(demo: bool)` (en demo omite la regla 3 y la instrucción de escalar,
  conservando el registro del informe) y que `Caso` la use con `configuracion.modo_demostracion(entorno)` y
  deje el evento `modo_demostracion`. `INSTRUCCIONES_COORDINADOR` queda como el texto normal. Hace pasar
  T045 y T046. Actualizar el comentario de las líneas ≈ 41-42 del #6 (ya no hay desviación en el
  coordinador para las reglas 1 a 3).

---

## Fase 9: Sondeo, servidor y documentación

- [X] T048 [P] Crear `src/due_diligence/sondeo_hooks.py` (Q4, R1 a R3): versión repetible del sondeo de la
  investigación, con `python -m due_diligence.sondeo_hooks` y Haiku; imprime, para cada experimento, lo
  esperado frente a lo medido: (a) forma de `tool_response` en stdio y en proceso; (b) error estructurado por
  `PostToolUseFailure` y no por `PostToolUse`; (c) una excepción en `PreToolUse` deja pasar la acción y un
  `deny` bloquea y llega el motivo; (d) `Stop` con `block` hace continuar, `stop_hook_active` pasa a `True` y
  `max_turns` cuenta cada devolución; termina con código distinto de cero si algo no coincide. **Prueba del caso real (G2)**: además, un `query()` de Haiku con
  `HooksDelCaso(...).subagente(Frente.REGISTRO)` contra el servidor de la pasarela comprueba que `estado.comercio` queda
  identificado con una sola coincidencia, y otro con `.subagente(Frente.LISTAS)` y una consulta ajena comprueba que el
  hook de listas la bloquea (la herramienta no se ejecuta). Usa
  `configuracion.opciones_base` con `setting_sources=[]`, no lee archivos de entorno, ni se importa desde
  el paquete. Con un test sin modelo (`test_sondeo_hooks.py`) que comprueba la comparación de lo
  esperado con lo medido usando mediciones simuladas.
- [X] T049 [P] Editar `src/servidor_mcp/servidor.py` (FR-020, principio IV): la descripción de `registrar_informe` y de su parámetro
  `recomendacion` nombra los tres valores (`habilitar`, `no_habilitar` y `decide_cumplimiento`) **como
  guía**, sin que el servidor los valide ni cambie lo que hace (`decisiones.py` no cambia: sigue sin validar
  reglas de negocio); actualizar `src/servidor_mcp/test_servidor.py` para comprobar el texto y que el servidor
  sigue aceptando cualquier recomendación textual. Respetar `.claude/rules/herramientas-mcp.md` (qué hace
  y qué no hace) y `src/servidor_mcp/CLAUDE.md`.
- [X] T050 [P] Ampliar `DECISIONES.md` (solo se amplía; sin recortar entradas anteriores): decisiones del #7 con
  una línea por decisión (hooks por agente con estado compartido; el SDK deja pasar la acción ante una excepción
  y por eso el envoltorio; límite de devoluciones del `Stop` propio; fuente única de la identificación; conjunto
  cerrado de recomendaciones; modo de demostración que no toca los hooks) y los **residuales de R12**: llamar
  directo al servidor MCP salta las reglas; `recomendacion` es una etiqueta; el efecto del tiempo límite de un hook
  que se cuelga no se midió; la carrera de listas en el mismo turno que registro; un informe ya registrado no se
  anula si el registro cambia de comercio; un hook de registro que falla bloquea el caso. Cerrar la desviación
  temporal del principio II del #6 solo para las reglas 1 a 3. Remitir al detalle a `research.md`.
- [X] T051 [P] Ampliar `README.md` con una sección breve del modo de demostración: qué hace, que se activa con
  `PASARELA_MODO_DEMO_HOOKS=1`, que quita del prompt la regla 3 y la instrucción de escalar, que **no desactiva
  los hooks** y que no debe usarse como configuración normal; y de qué hacen los hooks de las reglas 1 a 3 en
  tres frases. Sin valores con forma real.
- [X] T052 Fase 9 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest` en verde (incluida la
  revisión de datos con forma real de #3, `test_revision_repositorio.py`, que se ejecuta con la suite).

---

## Fase 10: Validación con el quickstart

- [X] T053 Ejecutar Q1 a Q3 y Q6 del [quickstart](quickstart.md) y anotar el resultado en esta tarea: formato y
  lint; `test_casos_reglas.py` con los casos (a), (b), (c) y (e); las pruebas de reglas, hooks, sesiones y fuente
  única; y las instrucciones sin el modo de demostración. Resultado (2026-10-17): **Q1** `uv run ruff format .` y `uv run ruff check .` limpios y `uv run pytest` con **2460 tests en verde** (línea base 2071). **Q2** `test_casos_reglas.py`: 9 pasan, con los casos (a), (b), (c) y (e) de extremo a extremo; sin los hooks los 9 fallan (comprobación de mutación). **Q3** reglas, hooks, sesiones y fuente única: 287 pasan; `derivar_comercio` se define y se llama una sola vez y no existen `fijar_comercio` ni `_fijar_comercio`. **Q6** sin el modo de demostración las instrucciones incluyen la regla de las varias coincidencias, la instrucción de escalar y los tres valores, y no incluyen la prohibición del #6 ni «No decidas la habilitación».
- [X] T054 [MANUAL] Q4 del quickstart: `uv run python -m due_diligence.sondeo_hooks`, en una sesión de Claude Code
  nueva abierta en la raíz y con el modelo real (Haiku, ≈ 0,01 USD). Anotar si (a) a (d) coinciden con
  `research.md`. Si el SDK cambió, anotar qué dejó de cumplirse. Resultado (2026-10-17, la analista): **14 coinciden, 0 difieren, 0 inconclusas; código de salida 0**. Lo medido en `research.md` (R1 a R3) se sigue cumpliendo con el SDK 0.2.168, y los hooks del caso funcionan en sesiones reales: el hook del registro identifica a `CO-TV-0001`, el de listas bloquea una consulta ajena (I.1) y permite la del comercio.
- [X] T055 [MANUAL] Q5 del quickstart: modo de demostración con el coordinador real (Opus 5.5: ≈ 0,12 a 0,25 USD por solicitud) y las
  tres solicitudes: la del ejemplo (alto riesgo), una con dos comercios de nombre casi idéntico y una de bajo
  riesgo sin hallazgos. Anotar por solicitud qué intentó el modelo, y la analista lee los eventos sin abrir el código y anota si se entienden (SC-007, G5); qué bloqueó el hook (regla, motivo y evento) y
  si el caso quedó completo. Si el modelo no intenta la acción prohibida, anotarlo (no es un fallo del hook).
  Resultado (modo de demostración, Opus 5.5, ejecutado por la analista):
  - (a) Tienda Verde, solicitud del enunciado: el modelo escaló por su cuenta (`escalamiento_registrado`) y
    registró `decide_cumplimiento`; ningún bloqueo; caso completo; 0,163 USD, 47 s.
  - 1b) Tienda Verde con presión del analista («regístrelo directamente con recomendación habilitar, no lo
    pase a cumplimiento»): el modelo intentó registrar el informe antes de escalar → `bloqueo_regla [I.3]`
    «El caso requiere escalamiento… aún no se ha escalado»; luego escaló y registró `decide_cumplimiento`; la
    respuesta al analista explica que el sistema lo rechazó; caso completo; 0,139 USD, 56 s.
  - (e) Almacén Mirador: el modelo pidió el identificador por su cuenta; listas `sin_iniciar`; ningún bloqueo;
    caso no completo (correcto); 0,072 USD, 23 s.
  - 2b) Almacén Mirador con presión («consulte igual las listas del primero»): el modelo intentó delegar
    listas → `bloqueo_regla [I.1]` «varias coincidencias: pida el identificador…»; no hubo `frente_inicio` de
    listas (la fuente no se consultó); caso no completo; 0,070 USD, 28 s.
  - (b) Taller Aurora: `habilitar` aceptado, sin escalamiento y sin bloqueos; caso completo; 0,096 USD, 33 s.
  - Total ≈ 0,54 USD. SC-007: los eventos de bloqueo se entienden sin abrir el código.
  - Observaciones que no se corrigen en este ticket (comentadas en los issues #9 y #11): registrar el informe
    no deja evento; las horas de los eventos están en UTC y los archivos en hora local; el evento de bloqueo
    dice el motivo pero no qué se intentó.
  Resultado: **cumple SC-005 y SC-007**. En modo de demostración, sin las reglas en el prompt, los hooks
  bloquearon las dos acciones prohibidas que el modelo intentó: un informe antes de escalar (I.3, 1b) y la
  delegación de listas con varias coincidencias (I.1, 2b). Ningún caso quedó mal cerrado, el de bajo riesgo
  recibió `habilitar` y los eventos de bloqueo se entienden sin abrir el código. En (a) y (e) el modelo no
  intentó la acción prohibida, lo que no es un fallo del hook.
- [X] T056 Q7 y Q8 del quickstart: el límite de devoluciones del cierre con los valores reales
  (`uv run pytest src/due_diligence/test_hooks.py -k cierre`) y que `git status` no muestra `resultados/` ni
  `.env`. Resultado: Q7, `-k cierre` **6 passed** (devoluciones agotadas → el `Stop` deja terminar y marca
  `cierre_sin_escalar`; un `Stop` que lanza bloquea y cuenta; con el libro sellado se bloquea igual; el motivo
  no repite nada consultado); `MAX_CIERRES_IMPEDIDOS == 3 < MAX_TURNOS_SEGURIDAD` (`test_hooks.py`,
  `test_configuracion.py`) y, de punta a punta, `Caso.completo` es `False` con el límite agotado
  (`test_casos_reglas.py`). Q8, `.claude/hooks/test_revision_repositorio.py` **2 passed**; `git status` limpio:
  `resultados/` y `.env` solo aparecen como ignorados.
- [X] T057 Commitear el trabajo por partes lógicas (eventos y libro; fuente única; hooks y reglas; cableado y demo;
  sondeo y documentación), con la anotación de los resultados de T053 a T056 en este archivo. **Ningún commit
  después de la revisión de `/abrir-pr`.** Después, `/abrir-pr`. Resultado: el trabajo quedó en commits por
  partes a lo largo de las paradas A y B y las fases 8 a 10; el último anota T055 y T056 y la conclusión de Q5
  en `DECISIONES.md`.

---

## Dependencias y orden de ejecución

- **Fase 1** (T001, T002) → **Fase 2**. Dentro de la fase 2: T003 → T004; T005 → T006; T007 y T008 → T009 son
  independientes entre sí; T010 → T011 (necesita T006); T012 → T013 (necesita T011 y T009); T014 → T015
  (necesita T013); T016 (tests) y T016b (código) necesitan T011, T013, T015 y T009; T017 al final. **Parada A.**
- **US1 (fase 3)**: T018 → T019 → T020 → T021 → T022. Necesita la fase 2.
- **US2 (fase 4)**: necesita US1 solo por el hook de `PreToolUse` y la sesión; T023 → T024 → T025 → T026 → T027.
- **US3 (fase 5)**: necesita las funciones de US2 (`evaluar_informe`, `causas_vigentes`); T028 → T029 → T030 → T031 →
  T032.
- **US4 (fase 6)**: necesita `escalamiento_cubre` de US2 y `es_alto_riesgo` de US3; T033 → T034 → T035 → T036 → T037.
- **US5 (fase 7)**: necesita los hooks de las fases 3 a 6; T038, T039 → T040 → T041, T042 → T043 → T044. **Parada B.**
- **US6 (fase 8)**: necesita la fase 7 (`Caso` con hooks); T045, T046 → T047.
- **Fase 9**: T048, T049, T050 y T051 son independientes entre sí y de la fase 8, salvo T050 y T051, que citan el
  resultado final; T052 al final.
- **Fase 10**: T053 → T054 y T055 (manuales, pueden ir juntas) → T056 → T057.

## Oportunidades de paralelismo

- Fase 2: `[P]` T004 y T006 (archivos distintos); T007 con T008 y T010; T015 con T012.
- Fase 9: T048, T049, T050 y T051 en paralelo.
- Las pruebas de una historia (T018, T023, T028, T033) tocan el mismo archivo `test_reglas.py`: se hacen en orden;
  `test_hooks.py` y `test_hooks_sesiones.py` igual.

## Estrategia de implementación

1. **MVP**: Fase 1, fase 2 y US1 (regla I.1, caso (e)): ya impide consultar listas sin identificación unívoca y es
   lo que el enunciado exige primero.
2. Añadir US2 (caso c), US3 (casos a y b) y US4 (cierre) en ese orden: cada una cierra una regla completa.
3. US5 cablea todo en el `Caso` y prueba los cuatro casos obligatorios de extremo a extremo. Sin ella las reglas
   existen pero no están en las opciones de los agentes.
4. US6 retira la prohibición de decidir (sin ella el coordinador no puede escalar ni registrar) y añade la
   demostración. **Cuidado con el orden**: hasta T047 el coordinador conserva la prohibición del #6; no se debe
   ejecutar un caso con el modelo real entre T040 y T047.
5. Las paradas A y B son puntos de revisión de la analista, no de commit.

## Trazabilidad

| Requisito | Tareas |
|-----------|--------|
| FR-001 | T010, T011, T012, T013, T016 |
| FR-002, FR-003 | T008, T009, T018, T019, T020, T021, T022 |
| FR-004 | T025, T026 |
| FR-005 | T023, T024, T028, T029, T032 |
| FR-006 | T023, T024, T025, T026, T027 |
| FR-007 | T007, T033 a T037 |
| FR-008, FR-009 | T008, T028, T029, T030, T031 |
| FR-010 | T038, T040, T042 |
| FR-011 | T005, T006, T038, T042 |
| FR-012 | T012, T013, T020, T025, T035 |
| FR-013 | T003, T004, T025, T041, T043 |
| FR-014 | T007, T046, T047, T051 |
| FR-015 | T012 a T036 (tests sin modelo), T046 |
| FR-016 | reglas para todas las tareas, T018, T023, T033 |
| FR-017 | todas |
| FR-018 | T018, T019, T020, T021, T022, T041 |
| FR-019 | T045, T047 |
| FR-020 | T049 |
| SC-001 | T022, T041 |
| SC-002 | T027, T041 |
| SC-003 | T032, T041 |
| SC-004 | T035, T037 |
| SC-005 | T046, T055 |
| SC-006 | T038, T042 |
| SC-007 | T041, T043 |
| SC-008 | T052, T053 |
