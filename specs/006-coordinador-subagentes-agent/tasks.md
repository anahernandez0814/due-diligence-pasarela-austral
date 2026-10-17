---

description: "Lista de tareas del ticket #6, coordinador y subagentes con el Agent SDK"
---

# Tasks: Coordinador y subagentes con el Agent SDK

**Input**: documentos de diseño en `specs/006-coordinador-subagentes-agent/`: [plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/delegacion.md](contracts/delegacion.md), [contracts/caso.md](contracts/caso.md) y
[quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/ y
quickstart.md.

**Tests**: obligatorios (constitución X). Van junto a cada módulo, en `src/due_diligence/test_*.py`, y
se escriben antes que el módulo (deben fallar primero). Ninguno llama al modelo ni a la red: usan un
ejecutor simulado y mensajes del SDK simulados (R12).

**Organization**: una fase por historia de la spec, con dos fases previas y tres finales:

1. Setup: fase 1. Fundamentos (`eventos`, `estado`, `frentes`): fase 2.
2. US6 fin del ciclo (P1): fase 3. **Va antes que las demás historias** porque el ejecutor la usa.
3. US2 aislamiento y herramientas por agente (P1): fase 4.
4. US1 delegar la solicitud (P1): fase 5. US3 paralelismo y orden (P1): fase 6.
   US4 listas para comercio y representante (P1): fase 7. US5 estado y eventos (P2): fase 8.
5. Sin control propio y punto de entrada: fase 9. Documentación: fase 10. Validación: fase 11.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La verificación del
cierre de #6 la hace el paso 0 del siguiente `/siguiente-ticket`.

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
  (`CO-TV-0001`, `Tienda Verde SAS`, etc.), sin ninguna secuencia de 6 o más dígitos seguidos.
- **Todo en español**: instrucciones de los agentes, mensajes, eventos y documentación (FR-015).
- **API de `claude-agent-sdk` 0.2.168** (R1 a R6, R14): `query`, `ClaudeAgentOptions`, `tool`,
  `create_sdk_mcp_server`, `ToolAnnotations` de `mcp_types`, `ResultMessage`, `ResultError`
  (`claude_agent_sdk._errors`). Los mensajes simulados de los tests se construyen con esas mismas
  clases.
- **El código no controla el ciclo** (FR-010): ni contadores, ni `while`, ni comparación de texto de
  mensajes para decidir si continúa. `max_turns` aparece **solo** en `configuracion.py`.
- **No se escribe en el código el nombre del archivo de variables de entorno** (R8): se usa
  `load_dotenv()` sin argumentos. Ningún test ni comando de estas tareas lee ese archivo.
- **Commits** por partes lógicas en la rama `006-coordinador-subagentes-agent`, nunca en `main`, y sin
  `git commit --amend`. Un commit nuevo invalida el veredicto del anterior, así que **ningún commit va
  después de la revisión** de `/abrir-pr`.
- **Formato**: el hook de #3 formatea cada `.py` escrito o editado. Cada fase de código termina con
  `uv run ruff format .` y `uv run ruff check .`.
- **Tests**: `uv run pytest src/due_diligence` (`pyproject.toml` ya incluye `src` en `testpaths`).
- `src/due_diligence/*.py` y `pyproject.toml` se editan con spec, plan y tareas de la rama
  commiteados, que deja hecho T001. `DECISIONES.md` no se recorta: solo se amplía. **`docs/bitacora-decisiones.md` no se edita en este ticket**: la
  actualiza la analista desde otro chat.

---

## Fase 1: Setup

- [X] T001 Confirmar que la rama es `006-coordinador-subagentes-agent` y commitear este
  `specs/006-coordinador-subagentes-agent/tasks.md` (`docs(specs): tareas del ticket #6`), para que
  `guarda_spec_previa` deje editar el código protegido. *(Hecha en `4a3cb22`.)*
- [X] T002 Añadir las dependencias con `uv add "claude-agent-sdk>=0.2.168,<0.3" "python-dotenv>=1.2,<2"`
  (actualiza `pyproject.toml` y `uv.lock`, R10). Comprobar con
  `uv run python -c "import claude_agent_sdk, dotenv, mcp_types"` y
  `uv run pytest src/due_diligence/test_humo.py src/servidor_mcp`. Commit: `build: dependencias del
  Agent SDK y python-dotenv`.

---

## Fase 2: Fundamentos (bloquean todas las historias)

**Propósito**: la tabla de frentes, los eventos y el estado, que usan todas las historias. T003 va primero porque `estado.py` y los tests usan `Frente`. Tests primero en eventos y estado.

- [X] T003 Crear `src/due_diligence/frentes.py` con `Frente` (`registro`, `listas`, `noticias`,
  `categoria`) y la tabla de `data-model.md`: herramienta de la pasarela de cada frente (nombre corto
  y completo `mcp__pasarela__<herramienta>`), dependencia (`listas` depende de `registro`) y campos
  de contexto que cada frente necesita. Se prueba con `test_configuracion.py` (T009).
- [X] T004 Escribir `src/due_diligence/test_eventos_estado.py` (R7, data-model). Casos de
  `RegistroEventos`: `secuencia` creciente desde 1 y única aun con 100 eventos registrados desde
  tareas `asyncio` concurrentes; con un reloj inyectado que devuelve siempre la misma marca, el orden
  lo da `secuencia`; `marca` es UTC con zona; `eventos()` devuelve una copia ordenada; tipos válidos
  (`caso_iniciado`, `delegacion`, `frente_inicio`, `frente_fin`, `frente_rechazado`,
  `terminacion`) y un tipo desconocido se rechaza. Casos de `EstadoCaso`: todos los frentes empiezan
  `sin_iniciar`; transiciones permitidas `sin_iniciar → en_curso → terminado | no_terminado` y
  `sin_iniciar → rechazado`, y una transición no permitida se rechaza; `instantanea()` devuelve una
  copia (modificarla no cambia el estado); `comercio` empieza `None`.
- [X] T005 [P] Crear `src/due_diligence/eventos.py` con `Evento` (`secuencia`, `marca`, `tipo`,
  `frente`, `detalle`; dataclass congelada) y `RegistroEventos` (`registrar(tipo, frente=None,
  detalle="")` bajo un `threading.Lock`, reloj inyectable `Callable[[], datetime]` por defecto
  `datetime.now(UTC)`, `eventos()`). Tipos como constantes. Hace pasar la parte de eventos de T004.
- [X] T006 [P] Crear `src/due_diligence/estado.py` con `Consulta`, `ResultadoFrente` y `EstadoCaso`
  tal como los define `data-model.md`: situación de cada frente, `resultados`, `consultas`, `comercio`
  y `terminacion`; `instantanea()` (copia profunda); un frente sin terminar **nunca** figura con un
  resultado vacío (US5-3). Un `EstadoCaso` por `Caso`, sin variables de módulo (FR-014). Hace pasar la
  parte de estado de T004.

---

## Fase 3: US6 Fin del ciclo por razón de parada (P1)

**Meta**: clasificar cómo terminó un ciclo sin contadores ni texto (FR-010 a FR-012).

**Prueba independiente**: la clasificación pura con mensajes de resultado simulados (Q4, SC-005).

- [X] T007 [US6] Escribir `src/due_diligence/test_terminacion.py` (R5). Casos con `ResultMessage`
  simulados: `subtype=success`, `stop_reason=end_turn`, `is_error=False` → `NORMAL`;
  `stop_reason=max_tokens` → `ANOMALA`; **`subtype=error_max_turns` con `stop_reason=tool_use`** y
  `terminal_reason=max_turns` → `LIMITE_SEGURIDAD` (el `subtype` gana al `stop_reason`); un resultado
  con texto «listo» y `stop_reason=max_tokens` → `ANOMALA` (US6-4: el texto no decide);
  `stop_reason=refusal`, `stop_reason=pause_turn`, `is_error=True` y un `subtype` de error distinto →
  `ANOMALA`, con el valor original en el detalle. Un `ResultError` simulado (con `subtype` y
  `terminal_reason`) se clasifica igual que el mensaje equivalente. El detalle devuelto incluye
  `subtype`, `stop_reason` y `terminal_reason` originales.
- [X] T008 [US6] Crear `src/due_diligence/terminacion.py` con `Terminacion` (`NORMAL`, `ANOMALA`,
  `LIMITE_SEGURIDAD`), `clasificar(subtype, stop_reason, is_error, terminal_reason)` como función pura
  en el orden de R5 (subtype primero), `clasificar_resultado(mensaje)` para un `ResultMessage` y
  `clasificar_error(error)` para un `ResultError`. Ninguna función recibe el texto de la respuesta.
  Hace pasar T007.

---

## Fase 4: US2 Aislar a cada subagente en su frente (P1)

**Meta**: opciones del SDK que aíslan el entorno y limitan las herramientas por agente, y el contexto
explícito que recibe cada subagente (FR-002 a FR-004, SC-002).

**Prueba independiente**: se inspeccionan las opciones y los prompts construidos, sin modelo (Q3).

- [X] T009 [US2] Escribir `src/due_diligence/test_configuracion.py` (R2, R3, R8, R9). Casos: toda
  opción de `opciones_base` lleva `setting_sources=[]`, `tools=[]` y `strict_mcp_config=True`;
  `allowed_tools` exactos por agente según la tabla de R3 (coordinador:
  `mcp__delegacion__delegar_frente`, `mcp__pasarela__registrar_informe`,
  `mcp__pasarela__escalar_a_cumplimiento`; cada subagente, solo su `mcp__pasarela__…`);
  `disallowed_tools` de cada subagente = las otras cinco de la pasarela y del coordinador = las cuatro
  de fuentes; **permitidas de la pasarela + prohibidas de la pasarela = exactamente las seis**, para
  cada agente (SC-002); ningún agente lleva herramientas integradas. Modelo por defecto
  `claude-sonnet-5-5` **tanto para el coordinador como para los cuatro subagentes** (R9) y sustitución
  de cada uno por separado con `PASARELA_MODELO_COORDINADOR` y `PASARELA_MODELO_SUBAGENTES`
  (`monkeypatch.setenv`). El servidor
  `pasarela` se declara con `sys.executable -m servidor_mcp` y `cwd` en la raíz, y reenvía
  `PASARELA_FALLA_NOTICIAS` y `PASARELA_RESULTADOS_DIR` si están en el entorno. `max_turns` es una
  constante documentada y **no** aparece fuera de `configuracion.py` (la comprobación del código
  completo es T026). `cargar_entorno` existe, **importar el paquete no la llama** (Q6) y, con `configuracion.load_dotenv` parcheado con `monkeypatch`, se comprueba **solo** que `cargar_entorno()` la llama con `override=False`. **Ningún test ejecuta la carga real** (R8): no leen ni dependen del archivo de entorno del desarrollador.
- [X] T010 [US2] Crear `src/due_diligence/configuracion.py` (R2, R3, R8, R9): constantes de modelos y
  sus variables de entorno, nombres completos de herramientas, `servidor_pasarela(entorno)`,
  `opciones_base(...)` (única función que construye `ClaudeAgentOptions`, con `setting_sources=[]`,
  `tools=[]`, `strict_mcp_config=True`, `cwd` en la raíz), `opciones_coordinador(...)`,
  `opciones_subagente(frente, ...)` y `cargar_entorno()` con `load_dotenv(override=False)` **sin
  argumentos**. `max_turns` como constante `MAX_TURNOS_SEGURIDAD`, con un comentario que diga que es
  solo una protección de seguridad y no controla el ciclo (FR-011). Hace pasar T009.
- [X] T011 [P] [US2] Escribir `src/due_diligence/test_contexto.py` (R11, FR-004, FR-005). El `prompt`
  de cada subagente se construye solo con los campos que su frente necesita: `registro` y `noticias`,
  `identificador` o `nombre`; `categoria`, la categoría; `listas`, el comercio y el representante
  **del estado**. Un campo de otro frente pasado en la entrada **no aparece** en el prompt; el prompt
  no contiene el texto de la solicitud del analista ni nada de la conversación (se comprueba con una
  solicitud con una frase marcadora que no debe aparecer). Sin el dato necesario se devuelve un error
  `frente_rechazado` que nombra el dato, no un prompt con un valor inventado. El `system_prompt` es
  fijo por frente, en español, y menciona su herramienta.
- [X] T012 [US2] Crear `src/due_diligence/contexto.py` con `construir_contexto(frente, entrada,
  estado)` y las instrucciones fijas por frente (`system_prompt`), según R11. Hace pasar T011.
- [X] T013 [P] [US2] Crear `src/due_diligence/sondeo_aislamiento.py` (R2, Q2), ejecutable con
  `uv run python -m due_diligence.sondeo_aislamiento`: construye sus opciones con `dataclasses.replace(opciones_base(...), tools=["Glob"])` (**`opciones_base` no gana ningún parámetro**: solo el sondeo activa la herramienta integrada), hace un `Glob` inofensivo y pregunta por las instrucciones del proyecto; repite con
  `setting_sources=["project"]` como control; imprime la tabla de Q2 y sale con código ≠ 0 si con `[]`
  aparece una skill o agente del repositorio, un evento de hooks o contenido del `CLAUDE.md`. Opción
  `--herramientas` (lista inicial de cada agente frente a R3) y `--limite` (`max_turns=1`, imprime la
  clasificación `LIMITE_SEGURIDAD`, Q4). No corre en `pytest`: es manual (T031 y T032).

**Punto de control**: `uv run pytest src/due_diligence`; `uv run ruff format .` y `uv run ruff check .`.
Commit: `feat(due_diligence): eventos, estado, clasificación del fin del ciclo y opciones aisladas`.

---

## Fase 5: US1 Delegar la solicitud en frentes especializados (P1)

**Meta**: el coordinador delega los cuatro frentes con `delegar_frente`, sin consultar fuentes
(FR-001, FR-002, FR-007, FR-013, FR-015).

**Prueba independiente**: con un ejecutor simulado se procesa la solicitud del ejemplo y se comprueba
qué se delegó y con qué datos (SC-001).

- [X] T014 [P] [US1] Escribir `src/due_diligence/test_ejecutor.py` (R6, R5). `EjecutorSDK` recibe la
  función de consulta inyectable (`consulta=query` por defecto) y se prueba con un flujo simulado de
  mensajes del SDK: un `AssistantMessage` con un `ToolUseBlock` y un `UserMessage` con un
  `ToolResultBlock` cuyo contenido es el JSON del contrato del #5 → una `Consulta` con herramienta,
  argumentos y `resultado` parseado, `valido=True` y el contenido separado de los metadatos tal como
  llega; un resultado que no es JSON del contrato → `resultado=None`, `valido=False`; el texto del
  modelo solo llena `resumen`; el `ResultMessage` final se clasifica con `terminacion` y el detalle;
  un `ToolResultBlock` con `is_error` y el JSON de error de la pasarela (`error`, `tipo`, `mensaje`, `reintentable`, `obtenido`; por ejemplo `servicio_no_disponible` con `reintentable` verdadero) → la `Consulta` **conserva ese error tal como llegó, con su `reintentable`**, y no se marca como resultado inválido (G2); si el flujo termina lanzando `ResultError` tras el `ResultMessage`, **no se vuelve a clasificar**; si
  la lanza sin haber entregado el mensaje, se clasifica con los atributos de la excepción. Las
  opciones se pasan sin modificar.
- [X] T015 [US1] Crear `src/due_diligence/ejecutor.py` con el protocolo `EjecutorSubagente` y
  `EjecutorSDK` (R6, contrato `caso.md`): un `query()` por subagente con `prompt` y opciones dados, y
  la captura de `ToolUseBlock` y `ToolResultBlock` como `Consulta`. Sin `while` ni contadores: se
  consume el flujo con `async for`. Hace pasar T014.
- [X] T016 [US1] Escribir `src/due_diligence/test_delegacion.py`, parte de US1 (contrato
  `delegacion.md`). Con un ejecutor simulado: `registro` con `identificador` delega y devuelve
  `resultados` con el JSON tal cual; sin `identificador` ni `nombre`, `frente_rechazado` no
  reintentable que nombra el dato, y no se lanza ningún subagente (US1-3: sin identificador pero con
  nombre, delega con el nombre y no inventa un identificador); `categoria` sin categoría →
  `frente_rechazado` (US1-4); un frente ya `en_curso` o `terminado` no lanza un segundo subagente y
  devuelve el resultado guardado; un campo de otro frente no se reenvía; un `frente` inválido →
  `entrada_invalida`. Eventos: `delegacion` antes de `frente_inicio` antes de `frente_fin`, y
  `frente_rechazado` con el motivo. Un frente con terminación anómala → error `frente_no_terminado`
  con `obtenido` que conserva las consultas alcanzadas (puede ir vacío). Un frente cuya consulta devolvió el error estructurado de la pasarela → `frente_no_terminado` con **el `reintentable` de ese error** (`true` con noticias caídas, `false` si el error lo trae así) y el error en `obtenido`: no se fija un valor (G2; la política de reintento es del #8).
- [X] T017 [US1] Crear `src/due_diligence/delegacion.py` (R4, contrato `delegacion.md`): función que
  construye, por caso, el servidor en proceso `delegacion` con la herramienta `delegar_frente`
  (`create_sdk_mcp_server`) cerrando sobre el `Caso`; parámetros validados dentro, respuesta y errores
  con la forma del contrato; registra los eventos de la sección «Comportamiento»; usa
  `contexto.construir_contexto`. En este paso se implementa la delegación de un frente sin la espera
  de `listas` (fases 6 y 7). Hace pasar T016.
- [X] T018 [US1] Escribir `src/due_diligence/test_coordinador.py` (contrato `caso.md`, FR-001,
  FR-002). `Caso.ejecutar(solicitud)` con un `query` del coordinador simulado (inyectable) y un
  ejecutor simulado: con la solicitud del ejemplo, los `allowed_tools` y `disallowed_tools` del
  coordinador son exactamente los de R3 y ninguna herramienta de fuentes es invocable por él; el
  coordinador delega `registro`, `noticias` y `categoria` con los datos de la solicitud (SC-001); la
  terminación del coordinador queda en el estado y como evento `terminacion`; las instrucciones del coordinador **prohíben** llamar a `registrar_informe` y `escalar_a_cumplimiento` (se comprueba el texto), y las dos herramientas siguen en su `allowed_tools` (FR-002); `hooks` se reparte a las
  opciones del coordinador **y** a las de cada subagente (R7); `ejecutar_caso` no llama a
  `cargar_entorno`; con una solicitud sin ningún dato identificable no se delega ningún frente y la
  respuesta pide el dato (spec, edge case).
- [X] T019 [US1] Crear `src/due_diligence/coordinador.py` con `Caso` (`estado`, `eventos()`,
  `terminacion`, `ejecutar(solicitud)`), `ejecutar_caso(...)` y las instrucciones de sistema del
  coordinador en español (delegar los frentes independientes **juntos en la misma respuesta**, nunca
  consultar fuentes, no inventar datos, ante varias coincidencias no elegir, y **no llamar a `registrar_informe` ni a `escalar_a_cumplimiento` en este ticket**: son del #9 y del #10, aunque las herramientas sigan disponibles por FR-002; es una instrucción, no una garantía: la cierran los hooks del #7, desviación temporal de II declarada en el plan). `Caso` crea el servidor
  de delegación y las opciones con `configuracion`, consume el flujo del coordinador con `async for`
  y clasifica el `ResultMessage` con `terminacion` (captura `ResultError` como en T015). Hace pasar
  T018.

**Punto de control**: pytest, ruff. Commit: `feat(due_diligence): coordinador, delegación y ejecutor
de subagentes`.

---

## Fase 6: US3 Paralelismo y orden de listas (P1)

**Meta**: los frentes independientes se solapan y `listas` empieza después del fin del registro
(FR-006, SC-003).

**Prueba independiente**: eventos de un caso con subagentes simulados con retardo (Q5 lo repite con el
modelo real).

- [X] T020 [US3] Añadir a `src/due_diligence/test_delegacion.py` (R4, R12). Con un ejecutor simulado con retardo: `asyncio.gather` de `registro`, `noticias` y `categoria` → los tres `frente_inicio` ocurren antes de cualquier `frente_fin` (solape, US3-1); la herramienta `delegar_frente` está anotada con `readOnlyHint=True` (se lee de la herramienta registrada). **Los dos órdenes de la carrera** en el mismo `gather`: `registro` y luego `listas` → `listas` espera y no hay `frente_inicio` de `listas` hasta el `frente_fin` del registro (US3-2, US3-3); `listas` y luego `registro` → `listas` se rechaza con `reintentable: true` y el mensaje «delega primero el registro y vuelve a pedir listas cuando termine», y el **reintento** de `listas` tras el fin del registro se ejecuta. Si el registro termina antes que `noticias`, `listas` empieza después del `frente_fin` del registro y sin esperar a `noticias` (US3-4). Un ejecutor simulado que lanza una excepción en `registro` no deja `listas` esperando para siempre (`listas` se rechaza, `reintentable: false`). Con el registro rechazado por falta de dato, `listas` se rechaza con `reintentable: true`.
- [X] T021 [US3] Implementar en `src/due_diligence/delegacion.py` la anotación `ToolAnnotations(readOnlyHint=True)` (de `mcp_types`) en la herramienta y el orden de `listas`: un `asyncio.Event` por frente del caso. Si el registro está en curso, `listas` espera a su fin (el evento se activa **siempre**, también si el registro termina de forma anómala o con excepción); si está `sin_iniciar` o `rechazado`, `listas` se rechaza con `reintentable: true` y el mensaje «delega primero el registro y vuelve a pedir listas cuando termine». Los rechazos por varias coincidencias, ninguna o un registro que no terminó siguen siendo `reintentable: false`. Hace pasar T020.

---

## Fase 7: US4 Listas para el comercio y su representante legal (P1)

**Meta**: `listas` consulta al comercio y a su representante, tal como los devolvió el registro
(FR-005, FR-013, SC-004).

**Prueba independiente**: un registro simulado que devuelve un comercio con representante, y se
comprueban las dos consultas.

- [X] T022 [US4] Añadir a `src/due_diligence/test_delegacion.py` y `test_contexto.py` (R4, R11). El
  registro simulado devuelve el JSON del contrato del #5 con **un** comercio y su
  `representante_legal` `{nombre, identificador}`: `estado.comercio` queda con identificador, nombre y
  representante, **exactamente como los devolvió el registro** (US4-2); el prompt de `listas` contiene
  al comercio y al representante **del estado aunque la entrada de la herramienta traiga otros datos**;
  el ejecutor simulado de `listas` registra dos `Consulta` (comercio y persona) y ambas quedan en el
  estado con su resultado y fuente (US4-1). Sin `representante_legal` en el registro, se consulta solo
  al comercio y el resultado lo declara (US4-3). **Varias coincidencias** (`coincidencias` con dos
  identificadores), `sin_coincidencias` y un resultado del registro inválido → `estado.comercio` es
  `None`, `listas` no se ejecuta y devuelve `frente_rechazado` con el motivo; el coordinador no elige una coincidencia (FR-013). **El ejecutor simulado de `listas` que consulta solo al comercio** (o solo al representante) deja el frente `no_terminado` con el motivo («falta la consulta del representante» o «del comercio»). Se compara el nombre completo con `igual()` de `servidor_mcp.normalizar` (y los identificadores con `igual_identificador`) **y el tipo de cada consulta** (`comercio` para el comercio, `persona` para el representante). `igual()` es **estricto**: otra capitalización o sin tildes **cuenta**; **otra forma jurídica o un nombre parcial no cuentan** (la pasarela busca por el nombre completo: sería un falso negativo, «Ernesto Calderón» no es «Ernesto Calderón Ibarra»); una consulta con el tipo cambiado no cuenta; sin representante en el registro basta la consulta del comercio (FR-005, SC-004).
- [X] T023 [US4] Implementar en `src/due_diligence/estado.py` la derivación de `comercio` a partir del
  resultado válido del registro (solo con una coincidencia única) y en `delegacion.py` el uso de
  `estado.comercio` como contexto de `listas`, con los eventos de `frente_rechazado`, y tras el subagente de `listas` la comprobación en `estado.consultas` de la consulta del comercio y, si hay, la del representante, con `igual()` de `servidor_mcp.normalizar` (y `igual_identificador`) y el **tipo** de cada consulta (`comercio` para el comercio, `persona` para el representante); si falta una, el frente queda `no_terminado` con el motivo (G1). Hace pasar T022.

**Punto de control**: pytest, ruff. Commit: `feat(due_diligence): paralelismo de frentes y listas con
comercio y representante`.

---

## Fase 8: US5 Estado, procedencia y registro de eventos (P2)

**Meta**: estado legible mientras el caso corre y eventos que reconstruyen el caso (FR-007 a FR-009,
FR-014, SC-006).

**Prueba independiente**: un caso con subagentes simulados y la lectura del estado y de los eventos.

- [X] T024 [US5] Añadir a `src/due_diligence/test_coordinador.py` y `test_eventos_estado.py`. Un caso
  terminado: el estado contiene por cada frente su resultado (contenido separado de `fuente` y
  `fecha`, sin mezclar ni reescribir) y las consultas realizadas (US5-1); cada evento tiene marca,
  frente y tipo, y la lista queda ordenada por `secuencia` (US5-2); un frente cuyo ejecutor termina
  de forma anómala figura `no_terminado`, **no** con un resultado vacío (US5-3); `instantanea()`
  durante la ejecución (desde el ejecutor simulado, que la lee a mitad de un frente) devuelve los
  frentes sin terminar como `en_curso`; **dos casos con la misma solicitud son independientes**: ni el
  estado ni los eventos de uno aparecen en el otro (FR-014); un hook simulado que recibe el `Caso` por
  cierre puede leer el estado de cada frente (R7). A partir de los eventos de un caso completo se
  reconstruye el orden (SC-006): se compara con la secuencia esperada de tipos y frentes.
- [X] T025 [US5] Ajustar lo que falte en `eventos.py`, `estado.py`, `delegacion.py` y `coordinador.py`
  para hacer pasar T024 (sin variables de módulo, copias en `instantanea()` y `eventos()`, estado de
  cada frente actualizado en cada transición).

**Punto de control**: pytest, ruff. Commit: `feat(due_diligence): estado legible y registro de eventos
del caso`.

---

## Fase 9: Sin control propio del ciclo y punto de entrada

- [ ] T026 [P] Escribir `src/due_diligence/test_sin_control_propio.py` (R5, R8, FR-010, FR-011, Q4,
  Q6). Con `ast` y lectura de texto sobre los módulos de `src/due_diligence/` (sin los `test_*.py`):
  ningún `while` en `coordinador.py` ni `ejecutor.py`; `max_turns` solo aparece en `configuracion.py`;
  ninguna decisión de continuar compara el texto de un mensaje (sin `in` ni `==` sobre `TextBlock.text`
  ni sobre `ResultMessage.result`); `cargar_entorno` solo se llama desde `__main__.py`; ningún módulo
  contiene el nombre del archivo de variables de entorno ni el literal de ninguna clave. Declarar en
  el docstring que es una comprobación de forma y no prueba la ausencia total (R5).
- [ ] T027 Crear `src/due_diligence/__main__.py` (contrato `caso.md`, R8): lee la solicitud de los
  argumentos, llama a `cargar_entorno()`, ejecuta el caso con el modelo real e imprime los eventos en
  orden (`secuencia`, marca, tipo, frente, detalle) y el estado final de cada frente. Es el **único**
  lugar que carga el entorno. Hace pasar T026.

**Punto de control**: pytest, ruff. Commit: `feat(due_diligence): punto de entrada manual y
comprobación de forma del ciclo`.

---

## Fase 10: Documentación

- [ ] T028 [P] Añadir una sección breve «Coordinador y subagentes» a `README.md`: cómo ejecutar un
  caso (`uv run python -m due_diligence "<solicitud>"`), de dónde sale la clave (variable de entorno o
  archivo local no versionado, sin nombrar valores), cómo cambiar los modelos con
  `PASARELA_MODELO_COORDINADOR` y `PASARELA_MODELO_SUBAGENTES`, y el aviso del coste en frío del
  coordinador (R14.3).
- [ ] T029 [P] Añadir a `DECISIONES.md` una viñeta de este ticket (una línea por decisión, **sin
  recortar entradas existentes**): opción (a) y el ejecutor inyectable (R1), `setting_sources=[]` (R2),
  `allowed_tools` más `disallowed_tools` (R3), `readOnlyHint` y orden de listas en código (R4),
  clasificación por `subtype` y `stop_reason` (R5), `python-dotenv` solo desde el punto de entrada
  (R8), modelos (Sonnet 5.5 para el coordinador y los cuatro subagentes, con la razón de la analista y Haiku como alternativa descartada) y coste medido en frío y en caliente (R9, R14.3) y los residuales de R13.

---

## Fase 11: Validación con el quickstart

- [ ] T030 Ejecutar Q1, Q3, Q6 y Q7 del quickstart: `uv run ruff format .`, `uv run ruff check .` y
  `uv run pytest` completos; los tests de este ticket y la suite existente en verde, y
  `test_revision_repositorio.py` sin hallazgos en los archivos nuevos. Anotar el resultado al pie de
  esta tarea.
- [ ] T031 [MANUAL] Q2: la analista ejecuta `uv run python -m due_diligence.sondeo_aislamiento
  --herramientas` en una sesión nueva en la raíz. Esperado: la tabla de Q2 (con `[]`, sin skills ni
  agentes del repositorio, 0 eventos de hooks, sin contenido del `CLAUDE.md`) y la lista inicial de
  herramientas de cada agente igual a la de R3. Anotar el resultado aquí.
- [ ] T032 [MANUAL] Q4 manual: `uv run python -m due_diligence.sondeo_aislamiento --limite`. Esperado:
  `LIMITE_SEGURIDAD`, el evento correspondiente y `ResultError` capturada sin romper el caso. Anotar
  el resultado aquí.
- [ ] T033 [MANUAL] Q5: el caso de ejemplo completo con el modelo real, **dos veces seguidas** (frío y
  caliente). Esperado: los ocho puntos de Q5 leyendo solo el registro de eventos, incluido que **no hubo llamadas a `registrar_informe` ni a `escalar_a_cumplimiento`** y que `resultados/` no tiene archivos nuevos (se compara el listado antes y después; C1), y que `listas` hizo la consulta del comercio y la de su representante (G1). «Frío» = la primera ejecución sin otra ejecución ni sondeo en la hora previa; si no se puede garantizar, se anota (A1). Después, **dos solicitudes manuales más** (Q5b, G3): una **sin categoría** y otra **sin nombre ni identificador**; anotar qué hizo el coordinador (frentes delegados, si inventó algún dato, qué pidió al analista). SC-001 se valida a mano. Anotar duración total
  frente a la suma de frentes, si registro, noticias y categoría salieron en el mismo turno, y el coste
  en frío y en caliente, con los cuatro subagentes en Sonnet 5.5 (R9; la analista estimó 0,01 a 0,02 USD
  más por caso que con Haiku). Completar T029 con esos números y **dejarlos en el resumen final de
  `/speckit-implement`** (duración total, solape, coste en frío y en caliente): la analista los usará para
  la bitácora 6.2. Si el coste en frío del coordinador no es aceptable, avisar a la analista antes de cerrar.
- [ ] T034 Revisar que `git status` solo contiene cambios del ticket, que ningún archivo nuevo contiene
  valores con forma real ni el nombre del archivo de variables de entorno, y commitear la
  documentación y las anotaciones de validación: `docs: documentación y validación del ticket #6`.
  Después, `/abrir-pr`.

---

## Dependencias y orden de ejecución

- **Fase 1** → **Fase 2** → **Fase 3 (US6)** → **Fase 4 (US2)** → **Fase 5 (US1)** → **Fase 6 (US3)**
  → **Fase 7 (US4)** → **Fase 8 (US5)** → **Fase 9** → **Fase 10** → **Fase 11**.
- US6 (fase 3) va antes que el resto porque `ejecutor.py` y `coordinador.py` clasifican con ella.
- US2 (fase 4) va antes de US1 porque `delegacion.py` y `coordinador.py` usan `configuracion` y `contexto`.
- US3 y US4 amplían `delegacion.py` y `test_delegacion.py`: se hacen **en orden**, no en paralelo.
- T029 se completa con los números de T033, que también van en el resumen del implement para la bitácora.

## Oportunidades de paralelismo

- Fase 2: T003 y T004 en orden (el test usa `Frente`); después T005 y T006 en paralelo (archivos distintos).
- Fase 4: T011 (test de contexto) en paralelo con T009 (test de configuración); T013 (sondeo) en
  paralelo con T012.
- Fase 5: T014 (test del ejecutor) en paralelo con T016 una vez hechos los fundamentos.
- Fase 9: T026 en paralelo con T027 solo si el test se escribe antes de `__main__.py`.
- Fase 10: T028 y T029 en paralelo (archivos distintos).

## Estrategia de implementación

- **MVP**: fases 1 a 7 (US6, US2, US1, US3 y US4, todas P1), que dan un coordinador que delega, aísla,
  solapa y consulta listas con el representante. US5 (P2) añade las garantías de lectura del estado.
- **Tests antes que el código** en cada fase, con commit por punto de control.
- **Lo que depende del modelo real** (que pida los tres frentes juntos, el coste, el aislamiento) se
  valida a mano en las tareas [MANUAL]; los tests automáticos no llaman al modelo.

## Trazabilidad

| Requisito | Tareas |
|-----------|--------|
| FR-001, FR-002 | T003, T009, T010, T016 a T019 |
| FR-003 | T009, T010, T013 |
| FR-004 | T009 a T012, T013 |
| FR-005 | T011, T022, T023 |
| FR-006 | T020, T021, T033 |
| FR-007 | T006, T014, T015, T024 |
| FR-008 | T004, T006, T024, T025 |
| FR-009 | T004, T005, T024 |
| FR-010 a FR-012 | T007, T008, T009, T010, T026, T032 |
| FR-013 | T016, T018, T022, T023 |
| FR-014 | T004, T006, T024 |
| FR-015, FR-016 | todas (reglas generales), T028, T029 |
| SC-001, SC-002 | T009, T016, T018 |
| SC-003 | T020, T021, T033 |
| SC-004 | T022, T023 |
| SC-005 | T007, T008, T026 |
| SC-006 | T024, T033 |
| SC-007 | T030 |
