---

description: "Lista de tareas del ticket #9, informe con procedencia, conflictos y registro"
---

# Tasks: Informe con procedencia, conflictos y registro

**Input**: documentos de diseño en `specs/009-informe-procedencia-conflictos/`: [plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/registrar-informe.md](contracts/registrar-informe.md),
[contracts/cierre.md](contracts/cierre.md) y [quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/ y
quickstart.md. Spec en `6dce052` y plan en `df6bcf9`.

**Tests**: obligatorios (constitución X y FR-019). Van junto a cada módulo (`src/…/test_*.py`) y se
escriben antes que el código: deben fallar primero. Ninguno llama al modelo ni a la red (SC-006).
Usan `EjecutorSimulado`, `SesionSimulada`, `CoordinadorSimulado` y `PasarelaSimulada` de
`simulacion.py`.

**Organization**: una fase por historia de la spec, **en el orden de dependencias del plan**:
- pasarela y fundamentos (fases 1 y 2);
- US1, fuente y fecha (fase 3);
- US2, conflictos (fase 4);
- US3, registro obligatorio y vigente (fase 5); al final, *parada de revisión A*;
- US4, informe mínimo (fase 6);
- US5, traza (fase 7);
- casos de extremo a extremo e instrucciones (fase 8); al final, *parada de revisión B*;
- sondeo y documentación (fase 9);
- validación (fase 10).

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La verificación del
cierre del #9 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US5).
- **[MANUAL]**: la hace la analista, en una sesión nueva de Claude Code abierta en la raíz y con el
  modelo real. Claude se detiene y espera su confirmación.
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md) o Q# del
  [quickstart](quickstart.md).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Ningún valor con forma real** (tarjeta, NIT, cédula o credencial) en tareas, tests, código ni
  documentación. Solo los datos ficticios del #5: `CO-RF-0006` (caso g), `CO-TA-0002`,
  `CO-TV-0001`, etc. Sin secuencias de 6 o más dígitos seguidos (principio VII).
- **Todo en español** (FR-021). Los motivos, los eventos, la cobertura y los resúmenes de conflictos
  no repiten nombres ni identificadores del comercio ni de personas. Los tests lo comprueban con un
  nombre ficticio que no debe aparecer en la salida. Solo el propio informe guardado lleva los
  datos del comercio y los valores en conflicto, que son su contenido.
- **Un solo esquema** (R1, R2): `servidor_mcp.informe.validar_informe`. Lo llaman la pasarela, el
  hook y la `PasarelaSimulada`; ninguno revalida la forma por su cuenta.
- **Un solo cálculo** de cada cosa: `calcular_cobertura` (#8), `calcular_conflictos` (R6) y
  `huella_actual` (R7).
- **La huella se calcula en el `PreToolUse`** de `registrar_informe` y el `PostToolUse` solo la
  confirma (R7). Nunca se recalcula en el `PostToolUse`.
- **API de `claude-agent-sdk` 0.2.168**:
  - `updatedInput` sustituye la entrada entera y se construye solo con
    `reemplazar_entrada(entrada_completa)`;
  - las demás salidas, solo con `permitir()`, `denegar(motivo)` y `bloquear_cierre(motivo)`;
  - el motivo del deny de `registrar_informe` es el JSON `informe_rechazado` (R3).
- **Tests del #5 al #8 que cambian** (T037): se adaptan **sin debilitarse**. Cada uno se cambia
  solo si falla por el diseño del #9, y se anota en la tabla de T037 con su justificación, que va
  en el PR. Ninguno se borra.
- **El código no controla el ciclo** (FR-010 del #6): `test_sin_control_propio.py` sigue en verde.
  Sin `while` en los módulos del ciclo.
- **No se escribe en el código el nombre del archivo de variables de entorno** (R8 del #6). Ningún
  test ni comando de estas tareas lo lee.
- **Commits** por partes lógicas en la rama `009-informe-procedencia-conflictos`, nunca en `main`,
  sin `git commit --amend`. **Ningún commit va después de la revisión** de `/abrir-pr`.
- **Formato**: cada fase de código termina con `uv run ruff format .` y `uv run ruff check .`.
- **Tests**: la suite completa (`uv run pytest`) en verde al cerrar cada fase.
- `DECISIONES.md` no se recorta: solo se amplía. **`docs/bitacora-decisiones.md` no se edita en este
  ticket.**

---

## Fase 1: Setup

- [X] T001 Confirmar que la rama es `009-informe-procedencia-conflictos` y commitear este
  `tasks.md`. Mensaje convencional en español.
- [X] T002 Línea base: `uv run pytest` y `uv run ruff check .` en verde antes de tocar nada. Anotar
  aquí el número de tests que pasan (referencia para T040): **3928** (ruff limpio).

---

## Fase 2: Fundamentos (bloquean todas las historias)

**Propósito**: el esquema de la pasarela, el registro con su interruptor, la hora UTC, los campos
nuevos del estado, los eventos, el presupuesto de turnos y los pasos nuevos de la simulación.

### Pasarela: esquema del informe (R2, R3)

- [X] T003 [P] Tests en `src/servidor_mcp/test_informe.py` para `validar_informe(entrada) ->
  list[Problema]` (data-model, «Afirmación» e «Informe»; contrato `registrar-informe.md`):
  - un informe válido, como el del contrato con `CO-RF-0006`, da `[]`;
  - **afirmación**: «`texto` no vacío tras quitar espacios», «`fuente` no vacía» y «`fecha`
    `AAAA-MM-DD` y fecha real». `"2026-02-30"`, `"30/09/2026"`, `""` y `None` son problemas, y un
    campo de más es «campo desconocido»;
  - **rutas**: `hallazgos.<frente>[<posición desde 0>].<campo>`;
  - **todos los problemas**, no solo el primero: dos afirmaciones mal formadas en frentes distintos
    dan dos o más problemas (SC-001);
  - `hallazgos` admite solo las claves `registro`, `listas`, `noticias` y `categoria`; otra clave
    es un problema. Un frente ausente equivale a una lista vacía;
  - **comercio** `{identificador, nombre, verificado}`: con `verificado: true` hacen falta los dos
    textos; con `false`, al menos uno; `verificado` debe ser bool;
  - **conflictos** `{resumen: str, lista: [...]}`. Cada conflicto es `{dato, valores}` con al menos
    2 valores, y cada valor `{valor, fuente, fecha}`;
  - **cobertura**: texto o lista de textos; **recomendación**: texto (el conjunto cerrado lo valida
    el #7, no esta función);
  - los textos de los problemas están en español y ningún problema repite el valor recibido.
- [X] T004 Implementar lo de T003 en `src/servidor_mcp/informe.py` (nuevo):
  - `Problema` (frozen, `ruta`, `texto`) y `validar_informe`, puro y sin E/S;
  - `FRENTES_INFORME = ("registro", "listas", "noticias", "categoria")`, con un test que lo compara
    con `due_diligence.frentes.Frente` desde `src/due_diligence/test_informe.py` (T016), sin
    importar `due_diligence` desde `servidor_mcp`;
  - el esquema JSON de los parámetros `comercio`, `hallazgos` y `conflictos`, para publicarlo con
    `json_schema_extra` en `servidor.py`.

  Validación escrita a mano, sin pydantic (R2). Hace pasar T003.
- [X] T005 Tests en `src/servidor_mcp/test_decisiones.py` y `src/servidor_mcp/test_servidor.py`:
  - `registrar_informe` con un informe válido se guarda con `conflictos` y `comercio.verificado`;
  - con problemas de forma devuelve `entrada_invalida`, no reintentable, con `problemas: [{ruta,
    texto}]`, y **no escribe ningún archivo** (FR-005);
  - con campos de primer nivel ausentes sigue dando `campos_obligatorios_ausentes` con todos los
    nombres, ahora también `conflictos`;
  - **`registrado_en` en UTC** con desfase `+00:00`, y la fecha del hecho es la fecha UTC (R10),
    con `_ahora` parcheado a una hora en que la fecha UTC y la local difieren;
  - `escalar_a_cumplimiento` **no cambia**: sigue aceptando `hallazgos.{frente}.{contenido, fuente}`;
  - por el protocolo MCP: el informe válido devuelve `informe_registrado`, y uno con una afirmación
    sin fuente, `entrada_invalida` con `problemas` (Q7);
  - la descripción de `registrar_informe` dice qué hace: el comercio, los conflictos y la cobertura
    los pone el sistema, y cada afirmación lleva su fuente y su fecha. También dice **qué no hace**
    (constitución IV, hallazgo C1): no comprueba que la fuente se haya consultado (lo hace el
    sistema antes de llamarla), no decide la habilitación y no escala el caso.
- [X] T006 Implementar lo de T005:
  - en `src/servidor_mcp/respuestas.py`, `error(..., problemas=None)`, que añade `problemas` al
    cuerpo si se pasa;
  - en `src/servidor_mcp/decisiones.py`, `registrar_informe(comercio, recomendacion, hallazgos,
    conflictos, cobertura)` con `validar_informe`. La validación de `escalar_a_cumplimiento` queda
    separada y sin cambios. `_ahora()` devuelve `datetime.now(UTC)`;
  - en `src/servidor_mcp/servidor.py`, el parámetro `conflictos`, los esquemas de T004 y la
    descripción nueva.

  Hace pasar T005 una vez adaptados los tests de T037 que fallen.
- [X] T007 [P] Tests en `src/servidor_mcp/test_registro.py` (R11): con
  `PASARELA_FALLA_REGISTRO=1`, puesto con `monkeypatch`, devuelve `servicio_no_disponible` con
  `reintentable: true` y el mensaje de R11. La variable se lee en cada llamada: cambiarla entre dos
  llamadas cambia el resultado. Una entrada inválida se rechaza antes que la caída, como en
  noticias. Sin la variable, el resultado no cambia.
- [X] T008 Implementar lo de T007 en `src/servidor_mcp/registro.py`, copiando el patrón de
  `src/servidor_mcp/noticias.py:19-29` (`VARIABLE_FALLA = "PASARELA_FALLA_REGISTRO"`), y anotar la
  variable en `src/servidor_mcp/CLAUDE.md`. Hace pasar T007.

### Estado, eventos y presupuesto

- [X] T009 [P] Tests en `src/due_diligence/test_eventos_estado.py` (data-model):
  - `informe_registrado`, `datos_sustituidos` y `cierre_sin_informe` están en `eventos.TIPOS`;
  - `Evento` tiene `accion: str | None = None` como **último** campo, y
    `registrar(..., accion=...)` lo guarda;
  - `EstadoCaso()` tiene `comercio_pedido is None`, `informes_pendientes == {}`, `informes == []` y
    `cierre_sin_informe is False`, y dos estados no comparten esas colecciones.
- [X] T010 Implementar lo de T009 en `src/due_diligence/eventos.py` y `src/due_diligence/estado.py`.
  `InformeRegistrado` y `Huella` se definen en `src/due_diligence/informe.py` (T026); `estado.py`
  los importa solo con `TYPE_CHECKING`, para no crear ciclos. Hace pasar T009.
- [X] T011 [P] Tests en `src/due_diligence/test_configuracion.py` (R8):
  - `presupuesto_turnos_peor_caso(max_reintentos, max_cierres)` devuelve `PASOS_FIJOS_PEOR_CASO +
    2 * len(Frente) * max_reintentos + max_cierres`; con `(3, 5)` da 37;
  - **`PRESUPUESTO_TURNOS_PEOR_CASO == 19`** y `<= MAX_TURNOS_SEGURIDAD`;
  - sigue sin ser un literal (comprobación con `ast` del #8).

  Es la adaptación de los tests del #8 de las líneas 284 y 291 (T037).
- [X] T012 Implementar lo de T011 en `src/due_diligence/configuracion.py`. El comentario explica el
  término nuevo: un informe nuevo por cada reintento posible, porque un reintento con éxito
  invalida el informe (R8). Hace pasar T011.

### Simulación (R12)

- [X] T013 [P] Tests en `src/due_diligence/test_sesion_simulada.py`:
  - `PasarelaSimulada` rechaza un informe mal formado con `entrada_invalida` y `problemas`, usando
    `validar_informe`, y guarda el válido con `conflictos`;
  - el paso `("informe", recomendacion)` del `CoordinadorSimulado` arma un informe **válido**: una
    afirmación por consulta válida del caso, con la fuente y la fecha de sus metadatos;
  - el paso `("informe_con", entrada)` envía esa entrada tal cual;
  - el paso `("mismo_mensaje", [pasos])` ejecuta los pasos con `asyncio.gather`. Con un ejecutor que
    espera un `asyncio.Event`, el test puede hacer que un `delegar` termine **entre** el `PreToolUse`
    y el `PostToolUse` de un `registrar_informe` del mismo mensaje;
  - `SesionSimulada.llamar` pasa a los hooks el mismo `tool_use_id` en `PreToolUse` y en
    `PostToolUse` o `PostToolUseFailure` de una llamada, y distinto entre llamadas.
- [X] T014 Implementar lo de T013 en `src/due_diligence/simulacion.py`, documentando los pasos
  nuevos en el docstring de `CoordinadorSimulado`. Hace pasar T013.
- [X] T015 Fase 2 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest` en
  verde. Los tests adaptados se anotan en T037. Commit «fundamentos del ticket #9».

---

## Fase 3: US1, fuente y fecha en cada afirmación (P1)

**Objetivo**: el hook rechaza en un solo deny estructurado todo informe con una afirmación sin
texto, sin fuente, sin fecha válida o con una fuente no consultada, y pone el comercio del código.

**Prueba independiente**: sin modelo, tres informes (sin fuente, sin fecha y con una fuente no
consultada) se rechazan nombrando las rutas, y uno completo se registra (SC-001).

- [X] T016 [P] [US1] Tests en `src/due_diligence/test_informe.py` para `fuentes_consultadas(estado,
  frente)` y `problemas_de_fuente(estado, hallazgos)` (R4):
  - las fuentes de los metadatos de los hechos y las de `metadatos.fuentes`: una respuesta
    `sin_coincidencias` de listas da sus fuentes sin tener hechos;
  - solo cuentan las consultas **válidas** del frente; las de otro frente no;
  - se compara con `normalizar.igual`: mayúsculas, tildes y espacios de más no importan;
  - un frente sin consultas válidas no admite ninguna fuente;
  - un problema por cada afirmación con una fuente no consultada, con su ruta;
  - `comercio_del_informe(estado)`: el identificado con `verificado: true` (solo `identificador` y
    `nombre`), o `None` sin comercio ni registro caído;
  - `servidor_mcp.informe.FRENTES_INFORME` coincide con los valores de `Frente` (T004; hallazgo T2:
    va aquí y no en T020).
- [X] T017 [US1] Tests en `src/due_diligence/test_hooks.py` para el `PreToolUse` de
  `registrar_informe` en modo normal (R1, R3, R5; contrato `registrar-informe.md`):
  - el motivo del deny es JSON que se puede leer con `json.loads`, con `error: true`, `tipo:
    "informe_rechazado"`, `reintentable: false`, `motivos` (regla y texto) y `problemas` (ruta y
    texto);
  - **un solo rechazo** con todo: un `habilitar` con coincidencia **y** una afirmación sin fuente
    trae el motivo I.2 y el problema de esquema juntos;
  - la regla del evento `bloqueo_regla` es `I.4` para el esquema y la fuente, y la unión con I.2 o
    I.3 si se juntan;
  - si acepta: `updatedInput` es la entrada **completa**, con `hallazgos` y `recomendacion` del
    coordinador y `comercio`, `conflictos` y `cobertura` del código. Un comercio declarado distinto
    se sustituye (FR-006);
  - eventos `cobertura_sustituida` (sin cambios) y `datos_sustituidos`, que dice si lo declarado
    era distinto y nunca el nombre ni el identificador.
- [X] T018 [US1] Implementar `fuentes_consultadas`, `problemas_de_fuente` y `comercio_del_informe`
  en `src/due_diligence/informe.py` (nuevo, puro). En `src/due_diligence/hooks.py`, reescribir
  `_informe_previo` para el modo normal:
  - acumula `evaluar_informe`, `validar_informe` y `problemas_de_fuente`;
  - deniega con el JSON de R3 mediante una función `denegar_informe(motivos, problemas)` que usa
    `denegar`;
  - si acepta, `reemplazar_entrada` con la entrada completa.

  Los conflictos se ponen con un marcador provisional `{"resumen": "", "lista": []}` hasta T023.
  Hace pasar T016 y T017.
- [X] T019 [US1] Fase 3: ruff, la suite completa y los tests de T037 adaptados. Commit «esquema y
  fuentes del informe (#9, US1)».

---

## Fase 4: US2, conflictos entre fuentes (P1)

**Objetivo**: el código compara las fuentes registrales y el informe registrado muestra cada
conflicto con sus dos valores y sus fuentes, declare lo que declare el coordinador.

**Prueba independiente**: con `CO-RF-0006`, el informe registrado por un coordinador simulado que
no declara conflictos contiene el de `fecha_constitucion` con 2016-03-14 y 2017-09-02 (SC-002).

- [X] T020 [P] [US2] Tests en `src/due_diligence/test_conflictos.py` para
  `calcular_conflictos(estado) -> ConflictosCaso` (R6, data-model):
  - `CO-RF-0006` da un conflicto `fecha_constitucion` con dos `ValorFuente`, el del Registro
    Mercantil Ficticio del Sur y el del Registro Único Ficticio de Empresas, en el orden de la
    respuesta. El resumen es «1 conflicto entre las fuentes registrales.»;
  - `CO-TA-0002` da `sin_conflictos` y «Sin conflictos entre las fuentes registrales.»;
  - dos datos distintos dan dos conflictos; un dato de una sola fuente no es conflicto;
  - `identificador` nunca se compara;
  - con el registro caído, `no_comparables` y «No se pudieron comparar las fuentes registrales: el
    registro no respondió.»;
  - se usa la última consulta válida cuyas `coincidencias` son exactamente el comercio identificado;
  - **con comercio identificado y sin ninguna consulta válida del registro que coincida** en
    `estado.consultas`, `no_comparables`, con el mismo resumen que el registro caído y nunca
    `sin_conflictos` (R6, hallazgo U1);
  - es puro: no escribe en el estado ni registra eventos;
  - el resumen no repite datos del comercio.
- [X] T021 [US2] Implementar `src/due_diligence/conflictos.py` (nuevo): `ValorFuente`, `Conflicto`,
  `ConflictosCaso` con `como_entrada()`, y las constantes de los cuatro resúmenes fijos, incluido el
  de `no_calculados` para la fase 6. Hace pasar T020.
- [X] T022 [US2] Tests en `src/due_diligence/test_hooks.py`: el informe aceptado lleva en
  `updatedInput` los conflictos de `calcular_conflictos`. Un conflicto declarado por el coordinador
  que el código no detecta no queda, y uno omitido aparece (FR-009). Si `calcular_conflictos` lanza
  una excepción, el informe se deniega con el motivo genérico y se sella el libro (`fallar_cerrado`,
  R9). En `src/due_diligence/test_coordinador.py`, **`Caso.conflictos`** devuelve lo mismo que
  `calcular_conflictos(caso.estado)` para un caso con `CO-RF-0006` y para uno sin conflictos (FR-010,
  hallazgo G1).
- [X] T023 [US2] Quitar el marcador de T018 y poner `calcular_conflictos(estado).como_entrada()` en
  `_informe_previo`. En `src/due_diligence/coordinador.py`, la propiedad `Caso.conflictos`, al lado de
  `Caso.cobertura` y con el mismo estilo: un solo cálculo, sin estado propio. Hace pasar T022.
- [X] T024 [US2] Fase 4: ruff, la suite completa y commit «conflictos del informe (#9, US2)».

---

## Fase 5: US3, informe obligatorio y vigente (P1)

**Objetivo**: el `Stop` exige, después del escalamiento, un informe vigente cuando hay comercio
identificado o registro caído, con el contador compartido. La huella se calcula en el `PreToolUse`
y se confirma en el `PostToolUse`.

**Prueba independiente**: un coordinador simulado que intenta terminar sin informe recibe la
devolución; con el informe vigente termina. Un reintento con éxito, incluido el que termina en el
mismo mensaje que el informe, exige un informe nuevo (SC-003).

- [X] T025 [P] [US3] Tests en `src/due_diligence/test_informe.py` (R7, R8, data-model):
  - **`huella_actual`**:
    - la cobertura entra solo como `(frente, cubierto)`, así que un frente que pasa de un error a
      otro con más intentos **no** cambia la huella;
    - un frente que pasa a cubierto, un conflicto nuevo, una causa nueva (coincidencia o
      `fallo_de_hook`) o un comercio distinto, **sí**;
    - **con el caso sellado** (hallazgo I1), los componentes de cobertura y de conflictos valen
      `NO_CALCULADOS`: con `calcular_cobertura` y `calcular_conflictos` parcheados para lanzar una
      excepción, `huella_actual` no los llama y no falla, y dos llamadas seguidas dan la misma
      huella. Las causas y el comercio se siguen calculando;
  - **`cambios(a, b)`** nombra los componentes que difieren: «la cobertura», «los conflictos»,
    «las causas de escalamiento» y «el comercio»;
  - **`informe_vigente`**: `False` sin informes y `True` solo si la huella del último coincide con
    la actual;
  - **`registro_caido`** es cierto con el registro `no_terminado` y una de estas causas:
    - `terminacion_anomala`, `sin_consultas`, `resultado_invalido` o `cancelado`;
    - `error_de_fuente` con algún tipo `servicio_no_disponible`, `datos_no_disponibles` o
      `error_interno`.

    Vale **con `reintentable: true` o `false`**. Es falso con solo `entrada_invalida` (caso
    límite), con el registro `rechazado`, `terminado`, `sin_iniciar` o `en_curso`;
  - `registro_reintentable` lee `reintentable` del último error del registro;
  - `requiere_informe`: comercio identificado o registro caído; falso con varias coincidencias o
    ninguna;
  - `comercio_del_informe` con el registro caído da `estado.comercio_pedido` con `verificado:
    false`, sin inventar el dato que falte.
- [X] T026 [US3] Implementar en `src/due_diligence/informe.py`: `Huella`, `InformeRegistrado`,
  `huella_actual`, `cambios`, `informe_vigente`, `registro_caido`, `registro_reintentable` y
  `requiere_informe`, y completar `comercio_del_informe`. En `src/due_diligence/delegacion.py`, al
  delegar el registro con un contexto válido, guardar `estado.comercio_pedido` con el
  `identificador` y el `nombre` de la entrada (`None` si falta). Con un test en
  `src/due_diligence/test_delegacion.py`: una nueva delegación de registro con otra entrada lo
  reemplaza. Hace pasar T025.
- [X] T027 [US3] Tests en `src/due_diligence/test_hooks.py` y `src/due_diligence/test_reglas.py`
  (R7, R8; contrato `cierre.md`):
  - **pendiente y confirmación**:
    - el `PreToolUse` que acepta guarda la huella en `estado.informes_pendientes[tool_use_id]`;
    - el `PostToolUse` con éxito la pasa a `estado.informes` con el id `INF-…` de la respuesta y
      emite `informe_registrado` (id, recomendación, resumen de la cobertura, número de
      conflictos; FR-016);
    - el `PostToolUseFailure` la descarta sin evento `informe_registrado`;
    - un deny no deja pendiente;
  - **cierre**:
    - sin informe, con comercio identificado, devuelve «Falta registrar el informe…»;
    - con el informe no vigente, el motivo nombra lo que cambió;
    - con el registro caído y `reintentable: true`, «El registro mercantil no respondió: reintenta
      el registro o registra el informe.»;
    - sin escalamiento ni informe, primero el motivo del escalamiento y «Luego registra el
      informe.»;
    - sin comercio (varias coincidencias, ninguna o entrada inválida) no exige informe;
  - **contador compartido**: las devoluciones por el informe suman a `libro.cierres_impedidos`.
    Agotadas, se permite el cierre, se marca `cierre_sin_informe` (y `cierre_sin_escalar` si
    también faltaba) y se emite `cierre_sin_informe`;
  - **limitación conocida (#10)**: con el comercio identificado, un fin de turno «para preguntar
    algo al analista» y sin informe se bloquea. El test lo dice en su nombre y en un comentario;
  - el coordinador registra **ocho** hooks, con `PostToolUse` y `PostToolUseFailure` de
    `registrar_informe`.
- [X] T028 [US3] Implementar lo de T027:
  - en `src/due_diligence/reglas.py`, `evaluar_cierre(estado)` con el informe, más una función que
    diga qué falta;
  - en `src/due_diligence/hooks.py`:
    - `_informe_previo` guarda la pendiente con `huella_actual` **calculada con los mismos datos que
      sustituye**;
    - `_informe_posterior` y el fallo del informe;
    - `_cierre` marca `cierre_sin_informe`;
    - los matchers nuevos en `coordinador()`;
  - en `src/due_diligence/coordinador.py`, `Caso.completo` exige además `not cierre_sin_informe` e
    `informe_vigente(estado)`.

  Hace pasar T027.
- [X] T029 [US3] Test de **orden** en `src/due_diligence/test_casos_informe.py` (nuevo; R7, la
  corrección de la analista):
  1. noticias falla con un error reintentable y se registra un informe vigente;
  2. con `("mismo_mensaje", [("delegar", {"frente": "noticias", …}), ("informe", "no_habilitar")])`,
     el reintento de noticias **termina con éxito entre** el `PreToolUse` y el `PostToolUse` del
     informe;
  3. la huella confirmada es la del `PreToolUse`, con noticias no cubierto;
  4. `informe_vigente` es `False` y el `Stop` devuelve «cambió la cobertura»;
  5. un informe nuevo lo deja vigente.

  En el mismo archivo, el contraste: si el reintento termina **antes** del `PreToolUse`, el informe
  queda vigente.
- [X] T030 [US3] Fase 5: ruff, la suite completa y los tests de T037 adaptados. Commit «informe
  obligatorio y vigente (#9, US3)». **PARADA DE REVISIÓN A.**

---

## Fase 6: US4, informe mínimo tras un fallo de hook (P2)

**Objetivo**: con el sello, primero se escala y después solo se admite `decide_cumplimiento`, con
la cobertura y los conflictos en textos fijos; el caso nunca figura como completo (R9).

**Prueba independiente**: con el sello forzado, el informe se rechaza hasta escalar; después,
`habilitar` y `no_habilitar` se rechazan y `decide_cumplimiento` se registra con los textos fijos
(SC-004).

- [ ] T031 [P] [US4] Tests en `src/due_diligence/test_reglas.py`:
  - `causas_vigentes` incluye `CAUSA_FALLO_DE_HOOK` con `libro.fallo_de_hook`;
  - su etiqueta es «fallo de un hook de verificación»;
  - `reglas_de` no le asigna I.2 ni I.3;
  - `evaluar_informe_minimo` rechaza las recomendaciones distintas de `decide_cumplimiento` con
    «Tras un fallo de hook solo decide el oficial: la recomendación debe ser
    decide_cumplimiento.», y también el informe sin escalamiento que cubra la causa;
  - con el sello y sin otras causas, `evaluar_cierre` exige escalar (cambio respecto al #7, R9).
- [ ] T032 [US4] Tests en `src/due_diligence/test_hooks.py`:
  - con el sello, `_informe_previo`:
    - rechaza con el JSON (R3) hasta que hay un escalamiento cuya instantánea incluye la causa;
    - después admite `decide_cumplimiento` con `cobertura == [COBERTURA_NO_CALCULADA]` y los
      conflictos con el resumen de `no_calculados`;
    - sigue validando el esquema y FR-004;
  - el `InformeRegistrado` confirmado tiene `minimo: True` y el evento lo dice;
  - **informe mínimo tras escalar → el `Stop` permite cerrar** (hallazgo I1):
    - se sella el libro, se escala, con el `PostToolUse` que guarda la instantánea con
      `fallo_de_hook`, y se registra `decide_cumplimiento`;
    - el `Stop` devuelve `permitir()`, sin `cierre_impedido` ni `cierre_sin_informe`;
    - **`caso.completo` sigue siendo `False`**;
    - con `calcular_cobertura` y `calcular_conflictos` parcheados para lanzar, el resultado es el
      mismo: ni el `PreToolUse` ni el `Stop` los llaman con el sello;
  - **sin escalamiento, el informe mínimo se rechaza** (US4-5): `decide_cumplimiento` con el sello y
    sin escalar da el motivo de escalar primero;
  - **fallo del `PostToolUse` del informe** (hallazgo U2): con `_informe_posterior` parcheado para
    lanzar, el libro queda sellado, la pendiente no pasa a `estado.informes`, y el caso exige
    escalar y después el informe mínimo, que se confirma con `minimo: True`;
  - con un doble fallo (`problemas_de_fuente` lanza con el caso sellado), se deniega con el motivo
    genérico (riesgo residual 6);
  - el caso sellado no figura como completo aunque tenga escalamiento e informe.
- [ ] T033 [US4] Implementar lo de T031 y T032:
  - en `src/due_diligence/reglas.py`, `CAUSA_FALLO_DE_HOOK` (constante en
    `src/due_diligence/libro.py`), su etiqueta y `evaluar_informe_minimo`;
  - en `src/due_diligence/hooks.py`, el camino del sello en `_informe_previo`, que sustituye a la
    denegación directa por `_sellado`.

  Hace pasar T031 y T032.
- [ ] T034 [US4] Fase 6: ruff, la suite completa y los tests de T037 adaptados. Commit «informe
  mínimo tras un fallo de hook (#9, US4)».

---

## Fase 7: US5, traza comprensible (P2)

**Objetivo**: el bloqueo dice la acción intentada, sin datos del comercio, y la salida muestra la
hora con UTC, los conflictos y los informes.

**Prueba independiente**: un bloqueo de `habilitar` deja `accion == "registrar_informe
(habilitar)"`, y la salida de la línea de comandos muestra «UTC», el conflicto y el informe
(SC-005).

- [ ] T035 [P] [US5] Tests en `src/due_diligence/test_hooks.py` y `src/due_diligence/test_main.py`
  (R10, R12):
  - **`accion` en cada bloqueo**:
    - `registrar_informe (<recomendación>)`; con una recomendación que no es del conjunto,
      `registrar_informe (recomendación no válida)`, sin repetirla;
    - `consultar_listas_restrictivas (comercio|persona)`;
    - `delegar_frente (listas)`;
    - ninguna acción lleva nombres ni identificadores;
  - **`imprimir_caso`**:
    - imprime la hora de los eventos con «UTC», la `accion` de los bloqueos, el bloque
      «Conflictos:» y los informes (id, recomendación, vigente sí o no, mínimo);
    - sigue mostrando la cobertura (#8).
- [ ] T036 [US5] Implementar lo de T035 en `src/due_diligence/hooks.py` (`_denegar_por_regla`
  recibe `accion`) y en `src/due_diligence/__main__.py`. El bloque «Conflictos:» lee
  `caso.conflictos` (T023), no vuelve a calcularlos. Hace pasar T035.

### Tests del #5 al #8 que cambian

- [ ] T037 Revisar y adaptar **sin debilitar** los tests que fallen por el diseño del #9. La tabla
  se completa durante las fases 2 a 7 y va en el PR. Candidatos:

  | Test | Por qué cambia | Cómo se adapta |
  |------|----------------|----------------|
  | `src/servidor_mcp/test_decisiones.py`: `test_un_informe_completo_se_guarda_y_devuelve_un_hecho_con_el_id`, `test_el_archivo_del_informe_conserva_lo_recibido`, `test_dos_informes_del_mismo_comercio_se_conservan_con_ids_distintos`, `test_a_registrar_informe_le_falta_un_campo`, `test_registrar_informe_nombra_todos_los_campos_que_faltan` | Formato nuevo del informe (R2) | Mismas comprobaciones con un informe del formato nuevo. La lista de campos que faltan es **exactamente** la de antes más `conflictos`, en el mismo orden; no basta con que la incluya. |
  | `test_decisiones.py`: `test_un_hallazgo_sin_fuente_es_un_campo_faltante`, `test_un_hallazgo_sin_contenido_es_un_campo_faltante` | La afirmación tiene `texto`, `fuente` y `fecha` | Pasan a `entrada_invalida`, y la aserción es de igualdad exacta: `problemas == [{"ruta": "hallazgos.registro[0].fuente", "texto": …}]` (o `.texto`), un único problema, y ningún archivo escrito. |
  | `test_decisiones.py`: `test_la_fecha_de_registro_es_la_de_la_hora_local_y_no_la_utc` | Cambio deliberado a UTC (R10, aceptado por la analista) | Se invierte: la fecha es la UTC. No es debilitar: cambia el contrato. |
  | `src/servidor_mcp/test_servidor.py`: `test_registrar_informe_responde_por_el_protocolo`, `test_registrar_informe_sin_campos_da_campos_obligatorios_ausentes`, `test_registrar_informe_con_un_campo_ausente_nombra_ese_campo`, `test_registrar_informe_con_un_tipo_incorrecto_da_entrada_invalida` | Formato nuevo | Igual, con el formato nuevo. |
  | `src/due_diligence/test_configuracion.py` (líneas 284 y 291) | Presupuesto de 19 (R8) | T011. |
  | `src/due_diligence/test_hooks.py`: `test_el_coordinador_registra_seis_hooks`, `test_el_coordinador_tiene_los_hooks_de_delegar_informe_y_escalar`; `src/due_diligence/test_coordinador.py`: `test_el_coordinador_tiene_los_hooks_de_delegar_informe_escalar_y_el_stop` | `PostToolUse` y `PostToolUseFailure` del informe | Ocho hooks; se añaden los matchers del informe a la lista esperada. |
  | `test_hooks.py`: `test_con_el_libro_sellado_el_hook_del_informe_deniega` (línea 916) y `test_una_excepcion_en_el_escalamiento_lo_deja_pasar_con_el_texto_fijo_y_sella` (línea 1285, del #8) | Con el sello hay informe mínimo (R9); `_motivo(salida) == SELLADO` deja de ser el motivo | Siguen denegando `no_habilitar` con el sello y sin escalamiento que cubra la causa. La igualdad exacta se conserva sobre el JSON: `motivos ==` exactamente los dos de R9 (recomendación distinta de `decide_cumplimiento` y escalar primero por «fallo de un hook de verificación»), en ese orden, y `problemas == []`. El camino que acepta va en T032. |
  | `test_hooks.py`: `test_el_informe_aceptado_sustituye_la_cobertura_y_lo_dice_sin_decir_registrada`, `test_si_la_cobertura_declarada_coincide_el_evento_no_dice_que_era_distinta`, `test_cuando_el_informe_se_deniega_no_se_registra_cobertura_sustituida`, `test_los_dos_canales_ponen_exactamente_la_cobertura_calculada`, `test_el_hook_del_informe_permite_no_habilitar_si_el_caso_esta_escalado` | Informe válido y `updatedInput` con comercio y conflictos | El informe de la prueba usa el formato nuevo. La igualdad sigue siendo exacta sobre la entrada completa: `_sustituida(salida) == {**entrada, "comercio": …, "conflictos": …, "cobertura": …}`, con los valores esperados escritos en el test, no leídos del código. Donde hoy se exige un único evento (`(evento,) = …`), pasa a la lista exacta de tipos: `[cobertura_sustituida, datos_sustituidos]`. |
  | `test_hooks.py`: los `test_el_hook_del_informe_deniega_*` y `test_el_hook_del_informe_con_una_entrada_malformada_deniega` | El motivo es JSON (R3) | Se lee con `json.loads` y se exige **igualdad exacta**: `motivos == [{"regla": …, "texto": <el motivo de hoy>}]` con la misma lista y orden de motivos que hoy, y `problemas == []` cuando el informe de la prueba es válido. Buscar el motivo «dentro» de la lista no basta. |
  | `src/due_diligence/test_hooks_sesiones.py`: `test_caso_c_habilitar_se_rechaza_y_solo_se_acepta_el_informe_tras_escalar`, `test_caso_c_los_rechazos_llevan_la_regla_i2_en_el_evento_y_sin_datos_consultados`, `test_caso_a_alto_riesgo_no_se_habilita_y_exige_escalar_antes_de_cualquier_informe`, `test_caso_a_sin_categoria_determinada_no_se_puede_habilitar`, `test_caso_b_bajo_riesgo_sin_hallazgos_se_habilita_sin_escalar`, `test_habilitar_sin_haber_consultado_listas_se_rechaza_aunque_el_riesgo_sea_bajo` | El helper `Caso.informe` arma hoy un informe con el formato viejo y `"cobertura": "completa"`, que I.4 rechazaría y cambiaría la regla de los eventos (`I.2` → `I.2, I.4`) | Los helpers del caso (`registrar`, `listas` y `riesgo`) **llenan `estado.consultas`** con la `Consulta` válida que simulan, como hace el `Delegador` en producción (R6, hallazgo U1); no se usan hallazgos vacíos. `Caso.informe` arma un informe **válido** con una afirmación por consulta válida, con la fuente y la fecha de sus metadatos. Lo mismo hace `_caso_con_comercio` de `test_hooks.py`. Las aserciones de los tests no cambian; las reglas de los eventos siguen siendo exactamente las de hoy (por ejemplo, `regla == "I.2"`). |
  | `test_hooks_sesiones.py`: `test_un_caso_de_bajo_riesgo_sin_hallazgos_termina_sin_trabas` | El cierre exige informe (FR-011), y registrarlo emite eventos | Se registra un informe válido con `no_habilitar` (sin listas consultadas, `habilitar` se rechazaría) antes de `terminar()`. `eventos == []` se sustituye por la **lista exacta de tipos** que el diseño emite en ese camino, en orden: `[TIPO_COBERTURA_SUSTITUIDA, TIPO_DATOS_SUSTITUIDOS, TIPO_INFORME_REGISTRADO]`. Los dos primeros salen del `PreToolUse` que acepta y el último del `PostToolUse`; `terminar()` no añade ninguno. Un `consulta_fallida`, `fallo_de_hook`, `bloqueo_regla`, `cierre_impedido` o `cierre_sin_informe` hace fallar el test, como hoy. |
  | `test_hooks_sesiones.py`: `test_un_caso_con_coincidencia_no_termina_hasta_que_se_escala`, `test_un_caso_de_alto_riesgo_tampoco_termina_sin_escalar` | El cierre exige informe (FR-011) | Se registra el informe (`decide_cumplimiento`) después de escalar y antes del último `terminar()`. Se conservan las cuentas exactas de hoy (`tipos.count(TIPO_CIERRE_IMPEDIDO) == 2`, `TIPO_CIERRE_SIN_ESCALAR not in tipos`) y se añade `TIPO_CIERRE_SIN_INFORME not in tipos`. |
  | `test_hooks_sesiones.py`: `test_un_coordinador_que_insiste_en_terminar_sin_escalar_termina_marcado_y_no_completo` | Ahora también falta el informe | Se conservan todas las aserciones exactas de hoy (`== MAX_CIERRES_IMPEDIDOS` devoluciones, `cierre_sin_escalar is True`, sin escalamientos) y se añaden `cierre_sin_informe is True` y `tipos.count(TIPO_CIERRE_SIN_INFORME) == 1`. |
  | `src/due_diligence/test_casos_reglas.py`: `test_el_caso_sigue_siendo_el_mismo_con_el_limite_de_devoluciones_agotado` y los casos (a), (b) y (c) que terminan | El cierre exige informe | Las aserciones del #7 se mantienen con las mismas igualdades exactas, por ejemplo `[c.termino for c in cierres] == [False] * MAX_CIERRES_IMPEDIDOS + [True]`. Se añade `cierre_sin_informe is True` donde falte el informe y `is False` donde se registre. |
  | `src/due_diligence/test_casos_cobertura.py` | El paso `informe` arma el formato nuevo (T014) | Sin cambios si T014 cubre el formato; si no, solo el guion. Las aserciones no se tocan. |
  | `src/due_diligence/test_sondeo_hooks.py` | `ENTRADA_INFORME` nuevo (T041) | Igualdad exacta: `validar_informe(ENTRADA_INFORME) == []`. Las demás aserciones del #8 sobre la entrada y sus campos no se tocan. |
  | `src/due_diligence/test_main.py` y `src/due_diligence/test_eventos_estado.py` | Hora con UTC y campo `accion` | Las líneas esperadas de la salida se reescriben **completas**, como hoy, con la hora y su «UTC», en lugar de comprobar que contengan «UTC». Las comparaciones de `Evento` siguen siendo de igualdad, ahora con `accion` (`None` donde no aplica). |
  | `src/due_diligence/test_coordinador.py`: `test_la_instruccion_minima_pide_escalar_y_registrar_el_informe_con_los_tres_valores` y `src/due_diligence/test_modo_demo.py` | Instrucciones nuevas (T039) | Siguen exigiendo los tres valores; se añade la guía de las afirmaciones. |

  **Añadidos durante la implementación** (fase 2), con la misma regla:

  | Test | Por qué cambia | Cómo se adapta |
  |------|----------------|----------------|
  | `src/due_diligence/test_eventos_estado.py`: `test_los_tipos_de_evento_son_los_del_modelo` | Tres tipos nuevos (T010) | La igualdad exacta del conjunto se conserva, con los tres tipos del #9 añadidos. |
  | `src/servidor_mcp/test_decisiones.py`: `test_la_hora_por_defecto_es_la_local_con_su_desfase` → `test_la_hora_por_defecto_es_utc_con_su_desfase`, y `test_la_fecha_de_registro_es_la_de_la_hora_local_y_no_la_utc` → `test_la_fecha_de_registro_es_la_utc_y_no_la_local` | Contrato cambiado a UTC (R10, aceptado) | Se renombran porque su nombre afirmaba lo contrario. Las igualdades siguen siendo exactas: desfase `timedelta(0)`, fecha `"2026-10-18"` y `registrado_en == "2026-10-18T04:30:00+00:00"` para las 23:30 en UTC−5. |
  | `test_decisiones.py`: `test_el_comercio_necesita_identificador_y_nombre` | El comercio lleva `verificado` (R2) | `problemas ==` exactamente un problema en `comercio.identificador` y otro en `comercio.nombre`, con `verificado: true`. |
  | `src/servidor_mcp/test_servidor.py`: `TIPOS_JSON` y `TIPOS_INCORRECTOS` | Parámetro `conflictos` | El diccionario exacto de tipos gana `"conflictos": "object"`; se añade el caso de tipo incorrecto `{"conflictos": "texto"}`. |
  | `src/due_diligence/test_hooks.py`: `test_con_coincidencias_sin_hechos_se_rechaza_habilitar_y_…` (fase 3) | El informe aceptado emite también `datos_sustituidos` | La lista exacta de tipos pasa de `[cobertura_sustituida]` a `[cobertura_sustituida, datos_sustituidos]`. |
  | `test_hooks.py`: `_caso_con_comercio` y el test de las 625 combinaciones (fase 3) | FR-004 y el comercio leen `estado.consultas` y el comercio pedido | El helper llena `estado.consultas` con la consulta del registro (U1); en las 625 combinaciones se fija un comercio pedido y una consulta del registro. Las aserciones sobre la cobertura no cambian. |
  | `test_hooks.py`: `test_un_caso_que_no_requiere_escalamiento_puede_terminar`, `test_un_caso_con_el_escalamiento_cubierto_puede_terminar`, `test_un_caso_que_requiere_escalamiento_sin_escalar_no_puede_terminar`, `test_agotadas_las_devoluciones_el_stop_deja_terminar_y_marca_cierre_sin_escalar` (fase 5) | Con el comercio identificado, el `Stop` exige además el informe | Un helper `_con_informe_vigente` registra un informe con la huella del momento justo antes del `Stop`, así siguen probando solo el escalamiento. Se conservan exactas `eventos == []`, `evento.detalle == salida["reason"]` y `ultimo.tipo == TIPO_CIERRE_SIN_ESCALAR`. Los casos sin informe van en tests nuevos. |
  | `test_hooks.py`: `test_con_coincidencias_sin_hechos_…` (fase 5) | Hace falta confirmar la huella para que el informe esté vigente | Se ejecuta el `PostToolUse` del informe con la respuesta de la pasarela antes del `Stop`, que sigue debiendo dar `permitir()`. |
  | `test_hooks.py`: `test_el_coordinador_registra_seis_hooks` → `test_el_coordinador_registra_ocho_hooks`; `test_el_coordinador_tiene_los_hooks_de_delegar_informe_y_escalar`; `test_coordinador.py`: `test_el_coordinador_tiene_los_hooks_de_delegar_informe_escalar_y_el_stop` (fase 5) | `PostToolUse` y `PostToolUseFailure` del informe | Igualdad exacta: 8 hooks, y matchers `[ESCALAR, INFORME]` en los dos. Se renombra porque el nombre decía seis. |
  | `src/due_diligence/test_reglas.py`: los siete tests de `evaluar_cierre` del #7 (fase 5) | Con el comercio identificado se exige el informe | Usan `_estado_de_cierre`, que añade un informe vigente; sus igualdades exactas (por ejemplo, el motivo completo de la coincidencia) no cambian. El motivo con «Luego registra el informe.» va en un test nuevo. |
  | `test_coordinador.py`: `test_un_caso_con_los_cuatro_frentes_terminados_y_fin_normal_esta_completo`, `test_un_caso_con_un_hook_de_registro_que_fallo_no_esta_completo`, `test_la_cobertura_del_caso_es_la_calculada_por_el_codigo` (fase 5) | `Caso.completo` exige un informe vigente | Se registra un informe vigente antes de `completo is True`. El primero comprueba además que sin informe es `False` (se refuerza). |
  | `src/due_diligence/test_sesion_simulada.py`: `test_la_pasarela_simulada_guarda_informes_y_escalamientos` | La `PasarelaSimulada` valida como la real (R12) | El informe de la prueba es válido y la igualdad `pasarela.informes == [informe]` sigue siendo exacta; el rechazo va en un test nuevo. |

  Ninguno se borra. Si un test no está en la tabla y falla, se añade con su justificación antes de
  cambiarlo.

  **Criterio para toda la tabla**: una aserción de igualdad exacta (`==`, una lista completa de
  eventos, un único evento desempaquetado o un motivo literal) se adapta con otra igualdad exacta
  sobre el valor nuevo, nunca con una pertenencia (`in`), una ausencia parcial («ningún X») ni un
  subconjunto. Si el valor nuevo no se puede escribir exacto en el test, se anota en la tabla por
  qué antes de relajar nada.

---

## Fase 8: casos de extremo a extremo e instrucciones

- [ ] T038 [P] Casos en `src/due_diligence/test_casos_informe.py` con el `CoordinadorSimulado` y la
  `PasarelaSimulada` (FR-019, Q2):
  - **caso (g)** con `CO-RF-0006`:
    - el informe registrado tiene el conflicto `fecha_constitucion` con los dos valores y sus
      fuentes, sin que el coordinador lo declare (SC-002);
    - con un conflicto inventado por el coordinador, solo queda el del código;
  - **caso escalado** con `CO-TV-0001` en suplementos dietarios:
    - el informe antes de escalar se rechaza (FR-012);
    - después del escalamiento se registra `decide_cumplimiento` y el cierre se permite;
  - **matriz de SC-003**: escalamiento requerido (sí o no) × informe (ninguno, vigente o anterior a
    un cambio). El cierre solo se permite con todo;
  - **registro caído**, con el `EjecutorSimulado` devolviendo para el registro la respuesta de la
    pasarela con `PASARELA_FALLA_REGISTRO=1` (`servicio_no_disponible`, reintentable):
    - primer fin de turno: motivo «reintenta el registro o registra el informe»;
    - tras el reintento fallido: motivo general;
    - el informe se registra con `verificado: false`, registro y listas no cubiertos, conflictos
      `no_comparables` y `habilitar` rechazado;
  - **registro sin coincidencias**: no se exige informe (decisión (a));
  - **entrada inválida**: no es registro caído y no se exige informe;
  - **informe vigente**:
    - un reintento que vuelve a fallar no invalida el informe;
    - uno que sale bien sí; el caso del mismo mensaje está en T029.
- [ ] T039 Instrucciones del coordinador en `src/due_diligence/coordinador.py` (R12), con tests en
  `src/due_diligence/test_coordinador.py` y `src/due_diligence/test_modo_demo.py`. La guía dice:
  - una afirmación por dato, con la fuente y la fecha de los metadatos del resultado;
  - los conflictos y la cobertura los pone el sistema;
  - primero escalar y después registrar el informe;
  - con el registro caído, reintentar o registrar el informe con el comercio pedido.

  La guía del informe está también en el modo de demostración, porque no es una regla I.1 a I.3.
  Los tests de T037 de estas instrucciones se adaptan.
- [ ] T040 Fases 7 y 8: ruff, la suite completa (anotar el número de tests, frente a T002), la
  tabla de T037 completa y commit «casos de extremo a extremo e instrucciones (#9)». **PARADA DE
  REVISIÓN B.**

---

## Fase 9: sondeo y documentación

- [ ] T041 [P] `src/due_diligence/sondeo_hooks.py`: `ENTRADA_INFORME` en el formato nuevo (R12),
  con su test en `src/due_diligence/test_sondeo_hooks.py`.
- [ ] T042 [P] `DECISIONES.md` (solo se amplía):
  - **decisión (a)**: si el registro responde que no hay ningún comercio, se pide al analista que
    revise el nombre y no se exige informe;
  - **decisión (b)**: con el registro caído, el comercio del informe es el que pidió el analista,
    sin verificar;
  - **cambio respecto al #7 (R9)**: un caso sellado sin otras causas ya no puede cerrarse sin
    escalar; el sello es una causa de escalamiento, y el informe mínimo solo admite
    `decide_cumplimiento`;
  - el registro caído exige informe aunque quede un reintento (R8);
  - la huella del informe vigente y qué cuenta como cambio (R7);
  - el presupuesto de 19 de 30 turnos (R8);
  - el rechazo del informe en JSON (R3);
  - la hora en UTC (R10; el #11 mostrará la hora de Colombia).
- [ ] T043 [P] `README.md`: la variable `PASARELA_FALLA_REGISTRO`, junto a
  `PASARELA_FALLA_NOTICIAS`, y el bloque de conflictos de la salida.
- [ ] T044 Fase 9: ruff, la suite completa y commit «sondeo y documentación del #9».

---

## Fase 10: validación

- [ ] T045 Q1 y Q2 del quickstart: ruff, la suite completa y los casos del #9 en verde. Anotar aquí
  el número de tests.
- [ ] T046 [MANUAL] Q3, caso (g) con el modelo real (Opus 5.5, ≈ 0,15 a 0,30 USD). Anotar:
  - el bloque de conflictos;
  - los eventos `cobertura_sustituida`, `datos_sustituidos` e `informe_registrado`;
  - los `bloqueo_regla [I.4]`, con su `accion`, y si el coordinador corrigió el informe tras el
    JSON `informe_rechazado` (riesgo residual 7);
  - el documento guardado, con `registrado_en` en UTC cruzado con la hora del evento;
  - los turnos, coste y duración.
- [ ] T047 [MANUAL] Q4, caso escalado con `CO-TV-0001` en suplementos dietarios. Anotar el orden
  `escalamiento_registrado` → `informe_registrado`, la recomendación y si hubo un informe
  rechazado antes de escalar.
- [ ] T048 [MANUAL] Q5, registro caído con `PASARELA_FALLA_REGISTRO=1` y `CO-TA-0002` (demo).
  Anotar:
  - si el coordinador reintentó;
  - listas rechazada, y noticias y categoría terminadas;
  - la cobertura y «Caso completo: no»;
  - el informe con `verificado: false`, los conflictos `no_comparables` y una recomendación
    distinta de `habilitar`;
  - si hubo `cierre_impedido`.
- [ ] T049 [MANUAL] Q6, sondeo repetible (Haiku, ≈ 0,02 USD): todas las mediciones `coinciden`,
  con G4 en el formato nuevo.
- [ ] T050 Commitear las anotaciones de T045 a T049 en este archivo. **Ningún commit después de la
  revisión de `/abrir-pr`.** Después, `/abrir-pr`. La descripción del PR incluye:
  - la tabla de T037;
  - el cambio respecto al #7 de R9;
  - el presupuesto de 19 turnos;
  - en «Lo pendiente», para el #10: los riesgos residuales 2 (`decide_cumplimiento` sin escalar
    con el registro caído) y 5 (`Stop` en cualquier fin de turno), y el 1 (informe vigente con
    afirmaciones viejas) como decisión aceptada.

---

## Dependencias y orden de ejecución

- **Fase 1** (T001, T002) → **Fase 2**:
  - T003 → T004 → T005 → T006 (la pasarela, en serie);
  - T007 → T008, T009 → T010, T011 → T012 y T013 → T014, independientes entre sí;
  - T015 al final.
- **US1 (fase 3)**: T016 y T017 → T018 → T019. Necesita T004 (`validar_informe`), T010 (estado y
  eventos) y T014 (simulación).
- **US2 (fase 4)**: T020 → T021 → T022 → T023 → T024. Necesita T018 (`_informe_previo`).
- **US3 (fase 5)**: T025 → T026 → T027 → T028 → T029 → T030. Necesita US2 (los conflictos entran en
  la huella) y T014 (`mismo_mensaje`). **Parada A.**
- **US4 (fase 6)**: T031 y T032 → T033 → T034. Necesita US3 (la huella incluye la causa del sello).
- **US5 (fase 7)**: T035 → T036. Puede ir en paralelo a la fase 6, pero los dos tocan `hooks.py`:
  en serie.
- **T037**: continua, de la fase 2 a la 8; se cierra en T040.
- **Fase 8**: T038 y T039 → T040. **Parada B.**
- **Fase 9**: T041, T042 y T043 en paralelo; T044 al final.
- **Fase 10**: T045 → T046 a T049 (manuales, pueden ir juntas) → T050.

## Oportunidades de paralelismo

- Fase 2: T007, T009, T011 y T013 tocan archivos distintos; T003 a T006 son la pasarela, en serie.
- Fase 3: T016 (`test_informe.py`) y T017 (`test_hooks.py`).
- Fase 4: T020 en paralelo a cualquier tarea que no toque `conflictos.py`.
- Fase 9: T041, T042 y T043.
- Todo lo que toca `src/due_diligence/hooks.py` (T018, T023, T028, T033 y T036) va en serie.

## Estrategia de implementación

1. **MVP**: fases 1 a 4 (US1 y US2). Cada afirmación lleva una fuente consultada y su fecha, y el
   caso (g) muestra los dos valores. Con eso se cumplen los dos primeros criterios de aceptación
   del issue.
2. La fase 5 cumple el tercero, que todo due diligence terminado queda registrado, con el informe
   vigente y el registro caído.
3. La fase 6 cierra el riesgo residual 6 del #8 y la fase 7, las observaciones del #7.
4. **No se ejecuta un caso con el modelo real antes de T039**: hasta entonces el coordinador no
   tiene la guía de las afirmaciones, y los informes se rechazarían por I.4.
5. Las paradas A y B son puntos de revisión de la analista, no de commit.

## Trazabilidad

| Requisito | Tareas |
|-----------|--------|
| FR-001, FR-002 | T003, T004, T005, T006 |
| FR-003 | T017, T018 |
| FR-004 | T016, T017, T018, T032 |
| FR-005 | T005, T006 |
| FR-006 | T016, T017, T018, T025, T026 |
| FR-007, FR-008 | T020, T021 |
| FR-009 | T022, T023 |
| FR-010 | T020, T022, T023 (`Caso.conflictos`), T035, T036 |
| FR-011 | T011, T012, T025 a T028, T038 |
| FR-012 | T031, T038 |
| FR-013 | T027, T028 |
| FR-014 | T031, T032, T033 |
| FR-015 | T037 (sin debilitar), T017 |
| FR-016 | T027, T028 |
| FR-017 | T035, T036 |
| FR-018 | T005, T006, T035, T036 |
| FR-019 | T003 a T039 (tests sin modelo), T029, T038 |
| FR-020 | T046, T047, T048 |
| FR-021 | reglas para todas las tareas, T017, T020, T035 |
| FR-022 | alcance: ninguna tarea toca el resumen al oficial (#10) ni la interfaz (#11) |
| FR-023 | T025, T026, T027, T028, T029 |
| SC-001 | T003, T017, T045 |
| SC-002 | T020, T038, T046 |
| SC-003 | T027, T038 |
| SC-004 | T032 |
| SC-005 | T035, T046 |
| SC-006 | T015, T019, T024, T030, T034, T040, T044, T045 |
