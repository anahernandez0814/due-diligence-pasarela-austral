---

description: "Lista de tareas del ticket #10, escalamiento con criterio, handoff y ambigüedad"
---

# Tasks: Escalamiento con criterio, handoff y ambigüedad

**Input**: documentos de diseño en `specs/010-escalamiento-criterio-handoff/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/escalar-a-cumplimiento.md](contracts/escalar-a-cumplimiento.md), [contracts/continuacion-y-cierre.md](contracts/continuacion-y-cierre.md) y [quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/ y quickstart.md. Spec en `d49aed0` y plan en `6b4d80e`.

**Tests**: obligatorios (constitución X y FR-023).
- Van junto a cada módulo (`src/…/test_*.py`) y se escriben antes que el código: deben fallar primero.
- Ninguno llama al modelo ni a la red (SC-006).
- Usan `EjecutorSimulado`, `SesionSimulada`, `CoordinadorSimulado` y `PasarelaSimulada` de `simulacion.py`.

**Organization**: dos bloques, cada uno con una parada de revisión de la analista al final (indicación de la analista):
- **Bloque A, la base**: fundamentos (fases 1 y 2) y, por historias, US3 (esperas y continuación), US4 (qué no es una espera) y US5 (categoría), con FR-027 en la cobertura. Termina en la **parada de revisión A**.
- **Bloque B, el escalamiento**: US1 (criterio), US2 (resumen al oficial), los casos de extremo a extremo y la línea de comandos. Termina en la **parada de revisión B**.
- Después, documentación y validación.

Las historias P1 US1 y US2 van en el bloque B porque dependen de la base: la espera del identificador es un motivo de rechazo del escalamiento, y FR-027 cambia las fuentes del resumen.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La verificación del cierre del #10 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US5).
- **[MANUAL]**: la hace la analista, en una sesión nueva de Claude Code abierta en la raíz y con el modelo real. Claude se detiene y espera su confirmación.
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md), D# del [plan](plan.md) o Q# del [quickstart](quickstart.md).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Ningún valor con forma real** (tarjeta, NIT, cédula o credencial) en tareas, tests, código ni documentación.
  - Solo los datos ficticios del #5: `CO-TV-0001` (caso a), `CO-TA-0002` (caso b), `CO-AM-0004` y `CO-AM-0005` (caso d), N-0001, `CO-PL-0003` y `PE-0003`.
  - Sin secuencias de 6 o más dígitos seguidos (principio VII).
- **Todo en español** (FR-022). Los motivos, los eventos, la causa y la cobertura no repiten nombres ni identificadores del comercio ni de personas. Los tests lo comprueban con un nombre ficticio que no debe aparecer en la salida. Solo el resumen guardado lleva los datos del comercio, que son su contenido.
- **Un solo esquema** (R6): `servidor_mcp.informe.validar_resumen` para el resumen y `validar_informe` para el informe. Comparten los validadores de comercio, afirmaciones, conflictos y cobertura. Los llaman la pasarela, el hook y la `PasarelaSimulada`; ninguno revalida la forma por su cuenta.
- **Un solo cálculo** de cada cosa: `calcular_cobertura`, `calcular_conflictos`, `huella_actual`, `espera_del_analista` y `bajo_riesgo_sin_hallazgos`.
- **El escalamiento se confirma en el `PostToolUse`** con lo que dejó pendiente el `PreToolUse` (R8). Nunca se recalculan las causas en el `PostToolUse`.
- **API de `claude-agent-sdk` 0.2.168**:
  - `updatedInput` sustituye la entrada entera y se construye solo con `reemplazar_entrada(entrada_completa)`;
  - las demás salidas, solo con `permitir()`, `denegar(motivo)` y `bloquear_cierre(motivo)`;
  - la continuación usa `ClaudeAgentOptions.resume` (R1, medido).
- **Tests del #5 al #9 que cambian** (T046): se adaptan **sin debilitarse**. Cada uno se cambia solo si falla por el diseño del #10, y se anota en la tabla de T046 con su justificación, que va en el PR. Ninguno se borra.
- **El código no controla el ciclo** (FR-010 del #6): `test_sin_control_propio.py` sigue en verde. Sin `while` en los módulos del ciclo; la pregunta de la línea de comandos tampoco usa `while` (recursión o `for` sobre la entrada, como en `_esperar_si_en_curso`).
- **No se escribe en el código el nombre del archivo de variables de entorno** (R8 del #6). Ningún test ni comando de estas tareas lo lee.
- **Commits** por partes lógicas en la rama `010-escalamiento-criterio-handoff`, nunca en `main`, sin `git commit --amend`. **Ningún commit va después de la revisión** de `/abrir-pr`.
- **Formato**: cada fase de código termina con `uv run ruff format .` y `uv run ruff check .`.
- **Tests**: la suite completa (`uv run pytest`) en verde al cerrar cada fase.
- `DECISIONES.md` no se recorta: solo se amplía. **`docs/bitacora-decisiones.md` no se edita en este ticket.**

---

# Bloque A: la base

## Fase 1: Setup

- [X] T001 Confirmar que la rama es `010-escalamiento-criterio-handoff` y commitear este `tasks.md`. Mensaje convencional en español.
- [X] T002 Línea base: `uv run pytest` y `uv run ruff check .` en verde antes de tocar nada. Anotar aquí el número de tests que pasan (referencia para T045): **4153** (ruff limpio).

---

## Fase 2: Fundamentos (bloquean todas las historias)

**Objetivo**: los datos nuevos del estado, el libro y los eventos, y el `resume` de las opciones, sin cambiar todavía ningún comportamiento.

- [X] T003 [P] Tests en `src/due_diligence/test_eventos_estado.py` (R2, R3, data-model):
  - **`EstadoCaso.mensajes`** empieza vacía; `solicitud` es una propiedad: `mensajes[0]`, o `""` sin mensajes. Asignar `estado.solicitud = "x"` sigue funcionando (compatibilidad del #6 al #9) y deja `mensajes == ["x"]`.
  - **`categoria_bloqueada`** empieza en `False` y `escalamientos_pendientes` vacío.
  - **`Identificacion.clase`** y **`derivar_comercio`** devuelven la clase, uno por caso: `invalida` (respuesta sin la forma), `ninguna`, `varias`, `contradictoria` (fuentes que difieren en el nombre o el representante) y `unica`.
  - **`EstadoCaso.clase_identificacion`**: `None` con el registro sin terminar; la clase consolidada igual que `comercio`; `unica` exactamente cuando `comercio` no es `None`.
  - **`Causa.OTRO_COMERCIO`** existe y su valor es `otro_comercio`.
  - **Eventos**: existen `TIPO_MENSAJE_ANALISTA` (`mensaje_analista`) y `TIPO_ESPERA_ANALISTA` (`espera_analista`).
- [X] T004 Implementar T003:
  - en `src/due_diligence/estado.py`: `mensajes`, `solicitud` como propiedad con *setter*, `categoria_bloqueada`, `escalamientos_pendientes`, `ClaseIdentificacion`, `Identificacion.clase`, la función hermana pura `clase_de(resultado)`, `clase_identificacion` y `Causa.OTRO_COMERCIO`;
  - en `src/due_diligence/eventos.py`: los dos tipos.

  `derivar_comercio` sigue devolviendo `(comercio, motivo)` sin cambiar a sus llamadores; `registrar_identificacion` guarda además `clase_de(respuesta)` (data-model).
- [X] T005 [P] Tests en `src/due_diligence/test_libro.py` (R8, data-model):
  - `Escalamiento(causas, comercio)` es inmutable;
  - `LibroReglas.escalamientos` es `list[Escalamiento]`;
  - `comercio` es la tupla `(identificador, nombre, verificado)` o `None`.
- [X] T006 Implementar T005 en `src/due_diligence/libro.py`. Adaptar a `Escalamiento` los usos de `libro.escalamientos` en `reglas.py` y `hooks.py`, sin cambiar todavía su lógica: `escalamiento_cubre` compara `causas <= e.causas` para todos. Los tests del #7 al #9 que construyen `frozenset` directamente se adaptan en T046.
- [X] T007 [P] Tests en `src/due_diligence/test_configuracion.py` (R1):
  - `opciones_base(..., resume="s-1")` deja `options.resume == "s-1"`;
  - sin `resume`, es `None`;
  - `opciones_coordinador` lo acepta y lo pasa;
  - `opciones_subagente` **no** lo acepta: los subagentes no reanudan.
- [X] T008 Implementar T007 en `src/due_diligence/configuracion.py`.
- [X] T009 Fase 2: ruff, la suite completa y los tests de T046 adaptados. Commit «fundamentos del #10: mensajes, clase de la identificación, escalamientos con comercio y resume».

---

## Fase 3: US3, esperas del analista y continuación del caso (P1)

**Objetivo**: con varias coincidencias o ninguna, el turno termina sin escalar ni informar; el caso continúa con otro mensaje en el mismo estado, y la nueva consulta del registro identifica al comercio.

**Prueba independiente**:
- **Turno 1**: con los dos comercios de nombre casi idéntico, el `Stop` deja terminar con `espera_analista`, sin consultas de listas, escalamiento ni informe.
- **Turno 2**: `Caso.continuar` con el identificador consulta el registro, identifica, delega listas y termina con el cierre de siempre.

- [X] T010 [P] [US3] Tests en `src/due_diligence/test_reglas.py` (R3, data-model `Espera`):
  - **`espera_del_analista`**:
    - registro `terminado` y clase `varias` → `Espera("identificador", <motivo fijo>)`;
    - clase `ninguna` → `Espera("nombre", …)`;
    - clase `contradictoria`, `unica` o `invalida` → `None` (decisión de la analista, D3 del #9 no es espera);
    - registro sin delegar, en curso, rechazado o caído → `None`.
  - **Espera de categoría** (la condición se prueba aquí, el bloqueo en T020): `categoria_bloqueada = True` y `libro.consultas_riesgo` vacía → `Espera("categoria", …)`, también con el comercio identificado **y con el registro caído** (el registro caído, por sí solo, no es espera). Con una `ConsultaRiesgo` registrada (conocida o desconocida) → `None`.
  - **Prioridad**: con `varias` y la categoría bloqueada a la vez, la espera es `identificador`.
  - **Textos fijos**: los motivos no contienen ningún identificador de las coincidencias (`CO-AM-0004`, `CO-AM-0005`).
  - **`_motivo_sin_comercio`** lee la clase, no subcadenas del motivo: con un motivo cuyo texto se cambió y la clase `varias`, sigue devolviendo `MOTIVO_VARIAS_COINCIDENCIAS`.
- [X] T011 [US3] Implementar T010 en `src/due_diligence/reglas.py`: `Espera`, los tres motivos fijos de data-model, `espera_del_analista` y `_motivo_sin_comercio` por clase.
- [X] T012 [P] [US3] Tests en `src/due_diligence/test_hooks.py`, para el `Stop` con esperas (R3, contrato `continuacion-y-cierre.md`):
  - **Espera del identificador**: con el registro en `varias`, una categoría de alto riesgo y sin escalar, `_cierre` devuelve `permitir()`, deja un evento `espera_analista` con el motivo, **no** incrementa `cierres_impedidos` y no marca `cierre_sin_escalar` ni `cierre_sin_informe`.
  - **Espera del nombre**: lo mismo con `ninguna`.
  - **D3 del #9 no es espera**: con la clase `contradictoria` y alto riesgo, el `Stop` exige el escalamiento como en el #9.
  - **Con el sello**: la espera se sigue admitiendo.
  - **Un fallo del propio cálculo de la espera** (parchear `espera_del_analista` para que lance): `fallar_cerrado` bloquea como en el #9; no deja pasar.
  - **El informe durante la espera** (FR-016, R3; movido aquí desde T041 por el hallazgo I1):
    - con la espera `identificador`, `_informe_previo` deniega con `MOTIVO_INFORME_ESPERA_IDENTIFICADOR` dentro de `informe_rechazado`, con la regla `V`, aunque el comercio pedido exista y el informe sea válido en forma;
    - con la espera `nombre`, lo mismo con `MOTIVO_INFORME_ESPERA_NOMBRE`;
    - con la espera `categoria`, el informe sigue las reglas de siempre (se acepta `no_habilitar`);
    - con el sello y la espera `identificador`, el informe mínimo sigue exigiendo escalar antes, como en el #9.

    Es un cambio de comportamiento respecto al #9, que va a la tabla de T046.
- [X] T013 [US3] Implementar T012 en `src/due_diligence/hooks.py` (`_cierre` mira `espera_del_analista` antes que `evaluar_cierre`; `_informe_previo` añade el rechazo de la espera) y en `src/due_diligence/reglas.py` (`MOTIVO_INFORME_ESPERA_IDENTIFICADOR` y `MOTIVO_INFORME_ESPERA_NOMBRE`, con los textos de research R3).
- [X] T018 [P] [US3] Simulación por turnos en `src/due_diligence/simulacion.py`, con sus tests en `test_sesion_simulada.py` (R12):
  - `CoordinadorSimulado(guiones=[[…], […]])` consume un guion por llamada; `guion=[…]` sigue valiendo como un solo turno;
  - lee `options.resume` y lo deja en `self.reanudaciones`;
  - su `ResultMessage` lleva un `session_id` estable (`mensaje_de_resultado(session_id=…)`).
- [X] T014 [P] [US3] Tests en `src/due_diligence/test_coordinador.py` (R1, R2, R4, contrato):
  - **`ejecutar` y `continuar`**: `ejecutar(solicitud)` añade el mensaje y deja `mensaje_analista` («Mensaje 1 del analista.», sin repetir el texto). `continuar(mensaje)` lanza la consulta con `options.resume` igual al `session_id` del último `ResultMessage`, con el **mismo** `HooksDelCaso`, el mismo `Delegador` y el mismo `EstadoCaso`.
  - **Sin sesión**: sin `session_id` previo, `continuar` lanza `CasoSinSesion` con un mensaje en español, sin llamar a la consulta.
  - **Clasificación por turno**: `turnos_del_caso` tiene una `Clasificacion` por turno y `terminacion` es la del último.
  - **`caso.espera`** es la espera del último fin de turno, y `Caso.completo` es falso con espera (FR-018).
  - **Cierre por turno** (R4): al empezar cada turno, `cierres_impedidos` vale 0, y `cierre_sin_escalar` y `cierre_sin_informe` valen `False`.
  - **Test R4 (a)**: el turno 1 agota las devoluciones sin informe (`cierre_sin_informe`). El turno 2 registra el informe vigente. Resultado: `completo` es verdadero y no queda ninguna marca.
  - **Test R4 (b)**: el turno 1 agota las devoluciones. El turno 2 termina sin hacer nada. Resultado: la marca vuelve a quedar puesta y `completo` es falso.

  Los dos tests de R4 usan el `CoordinadorSimulado` de T018.
- [X] T015 [US3] Implementar T014 en `src/due_diligence/coordinador.py`:
  - `Caso.continuar`, `CasoSinSesion`, `session_id` del último `ResultMessage`;
  - `turnos_del_caso`, `espera`, el reinicio por turno y `completo` con la espera.

  `ejecutar` y `continuar` comparten un método privado que lanza el turno; no se duplica el bucle de mensajes.
- [X] T016 [P] [US3] Tests en `src/due_diligence/test_delegacion.py` y `test_hooks_sesiones.py` (FR-017):
  - el registro delegado primero con «Almacén Mirador SAS» (dos coincidencias) y después con `CO-AM-0005` deja `estado.comercio` igual a `CO-AM-0005`;
  - `clase_identificacion` es `unica` y la delegación de listas se permite;
  - la identificación ambigua anterior no impide la nueva: la reinicia `_ejecutar` del registro, como desde el #7. El test lo fija con una `SesionSimulada` que ejecuta el hook del registro.
- [X] T017 [US3] Si T016 falla, corregir en `src/due_diligence/delegacion.py` o `estado.py` la consolidación, sin tocar I.1. Si pasa sin cambios, anotarlo aquí.

  **Resultado**: T016 pasó sin cambios de código; el reinicio de la identificación en `Delegador._ejecutar` del #7 ya lo garantizaba. Los dos tests están en `test_hooks_sesiones.py`, con un `Caso` real, porque la identificación solo la escribe el hook del registro. Con la mutación que quita `reiniciar_identificacion` fallan los dos (2 de 2); se restauró desde una copia propia, sin `git checkout`.
- [X] T019 [US3] Fase 3: ruff, la suite completa y los tests de T046 adaptados. Commit «esperas del analista y continuación del caso (#10, US3)».

---

## Fase 4: US5, la categoría de los mensajes del analista (P2)

**Objetivo**: la categoría delegada tiene que aparecer en un mensaje del analista; si no, se bloquea con I.3 y el caso puede esperar al analista.

**Prueba independiente**: con la solicitud del ejemplo, «suplementos dietarios» se permite y «ropa y accesorios» se bloquea. Con la categoría en un segundo mensaje, se permite (US5).

- [X] T020 [P] [US5] Tests en `src/due_diligence/test_reglas.py` y `test_hooks.py` (R9, FR-020):
  - **`categoria_en_mensajes`**:
    - «suplementos dietarios» está en la solicitud del ejemplo del enunciado;
    - «Suplementos  Dietarios» (mayúsculas y doble espacio) cuenta como la misma;
    - «ropa» no está en «tropa» (límites de palabra);
    - «suplementos dietarios» no está en un mensaje con «suplemento dietario»: riesgo declarado, US5-5;
    - sin mensajes → `False`.
  - **`_delegar_previo` con el frente de categoría**:
    - una categoría que no aparece se deniega con `MOTIVO_CATEGORIA_NO_DEL_ANALISTA`, la regla `I.3` y la acción `delegar_frente categoria`, y marca `categoria_bloqueada`;
    - una que aparece se permite y deja `categoria_bloqueada = False`;
    - una entrada sin categoría se deja pasar (la rechaza el `Delegador`);
    - con el sello, se sigue evaluando por la categoría, no por el sello.
  - **El motivo** no repite la categoría pedida ni datos del comercio.
  - **Espera de categoría de extremo a extremo** (US4-4): el comercio identificado, la categoría bloqueada sin resultado y el `Stop` → espera `categoria`. Si en el turno siguiente el analista da la categoría y se consulta, el `Stop` exige el cierre de siempre.
- [X] T021 [US5] Implementar T020 en `src/due_diligence/reglas.py` (`categoria_en_mensajes`, el motivo) y en `src/due_diligence/hooks.py` (`_delegar_previo`). En `src/due_diligence/delegacion.py`, la descripción de `delegar_frente` añade que la categoría tiene que ser la que dio el analista. El test de la descripción lo comprueba.
  **Nota de T021**: la acción del bloqueo es `delegar_frente (categoria)`, con el formato de las acciones que ya existían (`delegar_frente (listas)`), no `delegar_frente categoria` como decía T020.
- [X] T022 [US5] Fase 4: ruff, la suite y los tests de T046. Commit «categoría de los mensajes del analista (#10, US5)».

---

## Fase 5: US4, qué no es una espera, y FR-027 en la cobertura (P2)

**Objetivo**: con el comercio identificado, una pregunta no es una espera. Además, noticias consultado con otro nombre deja de contar como cubierto, y sus fuentes dejan de valer.

**Prueba independiente**:
- El recorrido de SC-004 da espera exactamente en tres situaciones.
- En el caso (d), elegir `CO-AM-0005` deja noticias no cubierto; elegir `CO-AM-0004` lo conserva.

- [X] T023 [P] [US4] Test del recorrido de SC-004 en `src/due_diligence/test_reglas.py`:
  - parametrizado con los 6 estados del registro (sin delegar, en curso, varias, ninguna, identificado y caído), por los 3 de la categoría (con resultado, sin delegar, bloqueada sin resultado), con y sin causas de escalamiento (36 casos);
  - `espera_del_analista` no es `None` exactamente cuando el registro está en `varias` o `ninguna`, o la categoría está bloqueada sin resultado.
  - Entre los 36, **el registro caído con la categoría bloqueada sin resultado** da la espera `categoria`, y el registro caído con la categoría con resultado o sin delegar da `None` (hallazgo A1).

  Un test aparte, con la clase `contradictoria`, da `None`; con `contradictoria` y la categoría bloqueada, da `categoria`.
- [X] T024 [US4] **Cambiar a sabiendas** el test del #9 `test_limitacion_conocida_el_stop_exige_el_informe_aunque_el_turno_sea_una_pregunta` en `src/due_diligence/test_hooks.py` (FR-015). No se borra:
  - **se conserva con otro nombre y otro comentario** (US4-1): con el comercio identificado y sin una categoría bloqueada, una pregunta sigue bloqueándose con `MOTIVO_SIN_INFORME`. Ya no es una limitación sino lo especificado, y la aserción no cambia;
  - **se añade** el test de la espera de categoría: con la categoría bloqueada sin resultado, el `Stop` admite la espera (US4-4).

  Anotarlo en la tabla de T046.
- [X] T025 [P] [US4] Tests en `src/due_diligence/test_reglas.py`, `test_cobertura.py` y `test_informe.py` (R7, FR-027):
  - **`consulta_del_comercio`**: coincide por `identificador` (`igual_identificador`) o por `nombre` (`igual`); no coincide con otro nombre ni con una entrada malformada.
  - **Cobertura de noticias**, con noticias `terminado` y consultado con «Almacén Mirador SAS»:
    - con el comercio identificado como `CO-AM-0005` (nombre «Almacén Mirador Norte SAS"), noticias **no** está cubierto, con la causa `otro_comercio` y el motivo fijo de data-model;
    - con `CO-AM-0004` («Almacén Mirador SAS»), **sí** está cubierto;
    - sin comercio identificado, sí está cubierto.
  - **La huella cambia** al pasar de un caso a otro: el informe anterior deja de estar vigente.
  - **`fuentes_consultadas`**:
    - con el comercio `CO-AM-0005`, la fuente de noticias de la consulta con el otro nombre **no** cuenta;
    - una afirmación de noticias que la cita da `FUENTE_NO_CONSULTADA`;
    - en listas, una consulta del representante sí cuenta;
    - una del comercio anterior, no;
    - categoría y registro no cambian.
- [X] T026 [US4] Implementar T025:
  - `consulta_del_comercio` en `src/due_diligence/reglas.py`;
  - noticias de otro comercio en `src/due_diligence/cobertura.py` (`_MOTIVOS[Causa.OTRO_COMERCIO]`);
  - las fuentes por comercio en `src/due_diligence/informe.py`.

  La cobertura sigue siendo pura.
- [X] T027 [P] [US4] Instrucciones (R11, FR-028) en `src/due_diligence/test_coordinador.py` y `test_modo_demo.py`:
  - **`_REGLA_TRAS_IDENTIFICAR`** está en las instrucciones normales **y** en las del modo de demostración. Dice que el rechazo de listas por falta de identificación deja de valer cuando el comercio queda identificado, aunque dijera `reintentable false`, y que noticias se vuelve a delegar si se consultó con otro nombre.
  - **`_REGLA_VARIAS_COINCIDENCIAS` ampliada** («termina tu turno sin escalar ni registrar el informe; cuando responda, sigue en el mismo caso»): solo en el modo normal.
- [X] T028 [US4] Implementar T027 en `src/due_diligence/coordinador.py`.
  **Notas de la fase 5**:
  - T023 pasó al escribirlo (prueba una función de T011). Con la mutación que olvida «sin resultado» sobrevivía; se añadió `test_sc004_la_categoria_bloqueada_con_un_resultado_ya_no_es_espera` (6 casos) y la mutación pasó a fallar 4.
  - T026: las mutaciones de la cobertura de noticias y de las fuentes por comercio hacen fallar 2 tests cada una.
  - T026 cambió `EjecutorSimulado`: sin resultado asignado, noticias consulta con el dato de su contexto, como el subagente real.
- [X] T029 [US4] Fase 5: ruff, la suite y los tests de T046. Commit «FR-027 en la cobertura y esperas que no lo son (#10, US4)». **PARADA DE REVISIÓN A**:
  - Claude se detiene y resume a la analista lo hecho en el bloque A (esperas, `Caso.continuar`, cierre por turno, FR-027 y la categoría), con los tests de R4 y del recorrido de SC-004;
  - no sigue con el bloque B hasta su visto bueno.

---

# Bloque B: el escalamiento

## Fase 6: US2, el resumen al oficial (P1)

**Objetivo**: `escalar_a_cumplimiento` con el esquema de afirmaciones, validado en la pasarela y en el hook, y con el comercio, la cobertura, la causa y los conflictos del código.

**Prueba independiente**: un resumen al que le falta cada uno de los cinco campos se rechaza nombrando lo que falta; uno completo se guarda con lo del código (SC-002).

- [X] T030 [P] [US2] Tests en `src/servidor_mcp/test_informe.py` (R6, data-model):
  - **`validar_resumen`** devuelve **todos** los problemas con su ruta: comercio (como el informe), hallazgos (afirmaciones), cobertura, `causa_escalamiento` (texto o lista de textos no vacíos), `accion_recomendada` (texto no vacío) y conflictos.
  - **Campos que faltan**: con varios a la vez, los nombra todos, en el orden `comercio`, `hallazgos`, `cobertura`, `causa_escalamiento`, `accion_recomendada`, `conflictos`.
  - **El mensaje** de `mensaje_resumen` no repite valores recibidos.
  - **`COMERCIO_NO_IDENTIFICADO`** (`{"identificador": "no identificado", "nombre": "no identificado", "verificado": false}`) **pasa** la validación (D2).
- [X] T031 [US2] Implementar T030 en `src/servidor_mcp/informe.py`, reutilizando `_comercio`, `_hallazgos`, `_conflictos` y `_cobertura`. `COMERCIO_NO_IDENTIFICADO` vive aquí y lo importa el hook.
- [X] T032 [P] [US2] Tests en `src/servidor_mcp/test_decisiones.py` y `test_servidor.py` (contrato, Q6):
  - **Sin campos**: `campos_obligatorios_ausentes` con los seis en `campos_faltantes`.
  - **Afirmación mal formada**: `entrada_invalida` con `problemas`.
  - **Forma vieja** `{contenido, fuente}`: `entrada_invalida`.
  - **Completo**: `caso_escalado`, el documento guardado con `conflictos`, `causa_escalamiento` y `registrado_en` en UTC.
  - **Por el protocolo**, los mismos tres casos.
  - **La descripción** de `escalar_a_cumplimiento` dice qué pone el sistema (comercio, cobertura, causa y conflictos) y qué no hace: no comprueba fuentes ni decide si corresponde escalar (constitución IV).
- [X] T033 [US2] Implementar T032 en `src/servidor_mcp/decisiones.py` (sin `_validar` ni `_REQUERIDOS_ESCALAMIENTO` viejo) y `src/servidor_mcp/servidor.py`. Actualizar `src/servidor_mcp/CLAUDE.md` si menciona la forma vieja.
- [X] T034 [P] [US2] Tests en `src/due_diligence/test_hooks.py` para el `PreToolUse` del escalamiento: forma, fuentes y sustitución (R5 pasos 4 y 5, R8, FR-021):
  - **Un resumen con un problema** de forma, una fuente no consultada o un frente cubierto sin afirmación se deniega con el JSON `resumen_rechazado` (`tipo`, `motivos`, `problemas`). Deja `bloqueo_regla` con la regla `I.4` y la acción `escalar_a_cumplimiento`.
  - **Uno válido** devuelve `reemplazar_entrada` con el comercio, la cobertura (`lineas()`), la causa (`causas_del_resumen`) y los conflictos (`como_entrada()`) del código, y con los hallazgos y la acción recomendada tal cual.
    - Deja `cobertura_sustituida` y `datos_sustituidos`.
    - Deja un `Escalamiento` pendiente por `tool_use_id`.
  - **Sin causas** (FR-003, hallazgo U1): la causa lleva una línea fija por cada motivo de `MOTIVOS_SIN_CAUSA` que se cumple, en su orden (research R5). Un test parametrizado prueba cada motivo solo: cobertura incompleta, categoría no determinada, mención en noticias y conflicto entre fuentes. Otro prueba dos a la vez, con las dos líneas en orden. Ninguna línea repite datos del comercio.
  - **D2**: sin comercio identificado ni pedido, deniega con `MOTIVO_SIN_COMERCIO_ESCALAMIENTO`, que pide delegar el registro.
  - **`PostToolUse`**: con `caso_escalado`, añade el `Escalamiento` pendiente a `libro.escalamientos` y deja `escalamiento_registrado` con el id, las causas, el resumen de la cobertura y el número de afirmaciones, sin datos del comercio. Con otra respuesta, lo descarta.
  - **`PostToolUseFailure`**: descarta lo pendiente y deja `consulta_fallida`.
  - **Causas pendientes**: las del `PreToolUse`, no las del momento del `PostToolUse`. Una causa nueva entre los dos hooks queda sin cubrir.
- [X] T035 [US2] Implementar T034 en `src/due_diligence/hooks.py` y `src/due_diligence/reglas.py`:
  - `_escalar_previo` (pasos 4 y 5 de R5), `_escalar_posterior` y `_escalar_fallido`;
  - `causas_del_resumen` y `MOTIVOS_SIN_CAUSA`;
  - `denegar_decision(tipo, …)`, que también usa el informe, en lugar de `denegar_informe`.

  El JSON del informe no cambia; lo comprueban los tests del #9.
- [X] T036 [P] [US2] Tests en `src/due_diligence/test_hooks.py` para el sello y los fallos (R5 paso 1, FR-012, D2):
  - **Con el sello**, el escalamiento pasa sin validar fuentes ni reglas, con la cobertura `COBERTURA_NO_CALCULADA`, los conflictos `no_calculados()` y la causa con «fallo de un hook de verificación»:
    - con el comercio identificado, va ese comercio;
    - sin identificado pero con el pedido, el pedido `verificado: false`;
    - **sin ninguno de los dos, `COMERCIO_NO_IDENTIFICADO`**, y la entrada resultante pasa `validar_resumen` (test del comercio fijo, D2).
  - **Con el sello durante la espera del identificador**, se admite (excepción de FR-016) y después se admite el informe mínimo del #9.
  - **Una excepción** calculando cualquier parte: `degradar_escalamiento` deja pasar con los mismos textos fijos (y `COMERCIO_NO_IDENTIFICADO` si no se pudo calcular el comercio), sella el caso y no deniega. La entrada pasa `validar_resumen`.
- [X] T037 [US2] Implementar T036 en `src/due_diligence/hooks.py` (`_escalar_previo` paso 1 y `degradar_escalamiento`).
  **Notas de la fase 6**:
  - **Quinto motivo sin causa** (T035): `comercio_no_identificado` («…el comercio no está identificado de forma unívoca.»). Sin él, un caso sin comercio identificado y sin los otros cuatro motivos daba una causa vacía, que la propia forma rechaza.
  - **Confirmación sin pendiente** (R8): si el `PostToolUse` no encuentra pendiente (un `PreToolUse` que falló y degradó), registra el escalamiento con las causas y el comercio de ese momento, como hasta el #9: el oficial lo recibió.
  - **Dónde vive** (data-model): `causas_del_resumen` y `menciones_en_noticias` están en `reglas.py` con importaciones diferidas (como `falta_para_cerrar`), para no crear un ciclo con `cobertura.py`.
  - **Adelantado de T044**: `resumen_del_caso`, el paso `("escalar"[, accion])` con un resumen válido, `PasarelaSimulada._escalar` que valida con `validar_resumen`, y `afirmaciones_del_caso` que solo cita fuentes que el hook admite (FR-027). Sin eso la fase no cerraba en verde.
  - Mutaciones: quitar `problemas_de_fuente` del resumen y olvidar lo pendiente en el `PostToolUse` hacen fallar un test cada una.
- [X] T038 [US2] Fase 6: ruff, la suite y los tests de T046. Commit «resumen al oficial con esquema y datos del código (#10, US2)».

---

## Fase 7: US1, escalamiento con criterio (P1)

**Objetivo**: el escalamiento se deniega con un bajo riesgo sin hallazgos comprobado y durante la espera del identificador o del nombre; `decide_cumplimiento` exige un escalamiento vigente para el comercio actual.

**Prueba independiente**: el caso (b) no se puede escalar y termina con `habilitar`. El (a) termina escalado con `decide_cumplimiento`. `decide_cumplimiento` sin escalar se rechaza (SC-001).

- [X] T039 [P] [US1] Tests en `src/due_diligence/test_reglas.py` (R5 paso 3, R8, FR-001 a FR-005):
  - **`bajo_riesgo_sin_hallazgos`** es cierto solo con todo esto a la vez:
    - la cobertura completa (con FR-027);
    - sin coincidencias;
    - la categoría determinada y no alta;
    - la consulta de noticias del comercio con `sin_coincidencias`;
    - los conflictos `sin_conflictos`;
    - sin sello.
  - **Cada condición por separado** lo hace falso, en un test parametrizado: una mención en noticias (US1-7), un conflicto (US1-8), noticias caído, la categoría desconocida, el registro caído, una coincidencia, el alto riesgo y el sello.
  - **`escalamiento_cubre`** solo cuenta los escalamientos del comercio actual: uno de `CO-AM-0004` no cubre a `CO-AM-0005` aunque las causas coincidan.
  - **`escalado_para_el_comercio`** es cierto con un escalamiento del comercio actual, aunque no haya causas.
  - **`evaluar_informe`**:
    - con `decide_cumplimiento` y sin escalamiento del comercio actual, rechaza con `MOTIVO_DECIDE_SIN_ESCALAR` (US1-6);
    - con un escalamiento del comercio anterior, también rechaza;
    - con uno del actual, acepta;
    - `habilitar` y `no_habilitar` no cambian.
  - **`evaluar_escalamiento`** devuelve los rechazos:
    - en la espera del identificador o del nombre, `MOTIVO_ESPERA_IDENTIFICADOR` o `MOTIVO_ESPERA_NOMBRE` con la regla `V`;
    - con `bajo_riesgo_sin_hallazgos`, `MOTIVO_SIN_CAUSA` con la regla `V`;
    - en la espera de la categoría, ninguno.
- [X] T040 [US1] Implementar T039 en `src/due_diligence/reglas.py`. Con el sello, `evaluar_informe_minimo` no cambia: el sello ya es causa.
- [X] T041 [P] [US1] Tests en `src/due_diligence/test_hooks.py` (R5 pasos 2 y 3, FR-016):
  - **`_escalar_previo`** deniega con los motivos de `evaluar_escalamiento` y deja `bloqueo_regla` con la regla `V` y la acción `escalar_a_cumplimiento`;
  - **el orden de R5**: el sello va antes que la espera, la espera antes que el bajo riesgo y el bajo riesgo antes que la forma;
  - **D3**: con alto riesgo y la espera del identificador o del nombre, el escalamiento se rechaza (sin sello) y se admite (con sello).

  El rechazo del informe durante la espera ya está en T012 y T013 (hallazgo I1).
- [X] T042 [US1] Implementar T041 en `src/due_diligence/hooks.py` (`_escalar_previo` pasos 2 y 3).
- [X] T043 [US1] Instrucciones (R11) en `src/due_diligence/coordinador.py`, con sus tests en `test_coordinador.py` y `test_modo_demo.py`:
  - **`_REGLA_ESCALAR`** añade «No escales un comercio de bajo riesgo sin ningún hallazgo»; la quita el modo de demostración;
  - **`_REGLA_RESUMEN_OFICIAL`** va en los dos modos: hallazgos como afirmaciones, acción recomendada para el oficial, y lo que pone el sistema.

  **Notas de la fase 7**:
  - `escalamiento_cubre(libro, comercio=<cualquiera>)`: sin comercio mira todos, como el libro solo del #7; las reglas con el estado pasan la clave del comercio actual (`escalamiento_del_caso_cubre`).
  - `MOTIVO_DECIDE_SIN_ESCALAR` solo se añade cuando no hay causas sin cubrir; con causas, el motivo de escalar ya lo pide.
  - `_REGLA_RESUMEN_OFICIAL` no contiene «escalar», porque el modo de demostración lo exige (test del #9).
  - Mutaciones: sin el criterio en el hook fallan 4; sin la exigencia de escalar para `decide_cumplimiento`, 2.

---

## Fase 8: casos de extremo a extremo, línea de comandos y presupuesto

**Objetivo**: los casos (a), (b) y (d) de extremo a extremo, la línea de comandos con la continuación y el presupuesto de turnos.

- [X] T044 [P] Simulación (R12) en `src/due_diligence/simulacion.py`, con sus tests en `test_sesion_simulada.py`:
  - `resumen_del_caso(estado, accion)`, el par de `informe_del_caso`: una afirmación por consulta válida **del comercio** (R7);
  - `("escalar",)` arma un resumen válido y `("escalar_con", entrada)` envía la entrada tal cual;
  - `PasarelaSimulada._escalar` valida con `validar_resumen`;
  - `_noticias` devuelve N-0001 (con su fuente y fecha ficticias) para `CO-AM-0005` o «Almacén Mirador Norte SAS» y `sin_coincidencias` para lo demás.
- [X] T045 Casos de extremo a extremo en `src/due_diligence/test_casos_escalamiento.py` (nuevo; FR-023, SC-001, SC-003), con el `CoordinadorSimulado` y la `PasarelaSimulada`:
  - **(a)** `CO-TV-0001` con «suplementos dietarios»: escalado con la causa «categoría de alto riesgo», informe `decide_cumplimiento` vigente y `escalamiento_registrado` antes de `informe_registrado`.
  - **(b)** `CO-TA-0002` con «tecnología y software»:
    - el guion intenta escalar, y se rechaza con `MOTIVO_SIN_CAUSA`;
    - después registra `habilitar`;
    - 0 escalamientos en la pasarela y `completo` verdadero.
  - **(d) en dos turnos** («Almacén Mirador SAS», «ropa y accesorios»):
    - **turno 1**: registro, noticias y categoría juntos; el guion intenta listas (bloqueado) y termina con `espera_analista`; 0 consultas de listas, 0 escalamientos y 0 informes;
    - **turno 2**, `continuar("CO-AM-0005")`: registro con el identificador, noticias de nuevo (aparece N-0001), listas del comercio y del representante e informe vigente;
    - `reanudaciones` con el `session_id` del turno 1.
  - **(d) con alto riesgo** («suplementos dietarios»): el turno 1 termina igual, sin escalar; en el turno 2 el `Stop` exige el escalamiento y el guion lo hace antes del informe.
  - **(d) eligiendo `CO-AM-0004`**: noticias se conserva cubierto sin volver a delegar.
  - **FR-027 de extremo a extremo**: en el turno 2, con `CO-AM-0005`, un informe que cita la consulta de noticias del turno 1 se rechaza por I.4.
  - **Ninguna salida** (eventos, motivos y cobertura) contiene «Almacén Mirador Norte SAS» ni `PE-0005`.
- [X] T046 **Tests del #5 al #9 que cambian**, una tarea continua desde la fase 2 que se cierra aquí. Tabla con cada test, por qué cambia y cómo se adapta sin debilitarse (igualdades exactas):

  | Test | Por qué cambia | Cómo se adapta |
  |------|----------------|----------------|
  | **Cambio de comportamiento respecto al #9** (FR-016, hallazgo I1): antes se aceptaba el informe con el comercio pedido (`verificado: false`) ante varias coincidencias; ahora se rechaza. Los tests del #9 que lo fijaran se adaptan con el motivo nuevo (T012). | FR-016 | Igualdad exacta con `MOTIVO_INFORME_ESPERA_IDENTIFICADOR` o `MOTIVO_INFORME_ESPERA_NOMBRE` en `motivos`. |
  | `test_eventos_estado.py::test_los_tipos_de_evento_son_los_del_modelo` | Dos eventos nuevos (`mensaje_analista`, `espera_analista`). | El conjunto exacto añade los dos. |
  | `test_eventos_estado.py::test_la_causa_es_un_conjunto_cerrado_de_ocho_valores`, ahora `…_de_nueve_valores` | La causa nueva `otro_comercio` (FR-027). | El conjunto exacto añade `otro_comercio`; el nombre dice nueve. |
  | `test_reglas.py`: `_libro_con`, `test_una_causa_nueva_posterior_al_escalamiento_no_queda_cubierta`, `test_alto_riesgo_escalado_acepta_decide_cumplimiento_y_no_habilitar` y el informe mínimo tras escalar | `libro.escalamientos` pasa de `frozenset` a `Escalamiento(causas, comercio)` (R8). | Las mismas causas, envueltas en `Escalamiento(…, None)`: el libro solo, sin comercio. Las aserciones no cambian. |
  | `test_hooks.py`: el escalamiento exitoso, el informe tras escalar, el cierre con el escalamiento cubierto y el `Stop` que falla con el sello ya escalado | Lo mismo. | Igualdad exacta con `Escalamiento(frozenset(...), ("CO-TV-0001", "Tienda Verde SAS", True))`, o con `clave_comercio(estado)` donde el test construye el escalamiento. |
  | `test_hooks_sesiones.py` (casos a y c) y `test_casos_reglas.py` (caso a) | Lo mismo. | Igualdad exacta con el `Escalamiento` y la clave del comercio del caso (`CO-PL-0003` o `CO-TV-0001`). |
  | `test_hooks.py::test_con_varias_coincidencias_o_ninguna_no_se_exige_informe` | Ahora es una espera del analista y deja `espera_analista` (R3). | Sigue exigiendo `permitir()`; los eventos pasan de `[]` a exactamente `[espera_analista]`. |
  | `test_hooks.py::test_sin_comercio_identificado_la_cobertura_y_los_conflictos_no_se_contradicen`, variante de varias coincidencias | FR-016: el informe se rechaza durante la espera del identificador (es la fila del cambio respecto al #9). | Se separa en `test_con_varias_coincidencias_la_cobertura_y_los_conflictos_no_se_contradicen`: las mismas igualdades exactas de la cobertura (`registro: cubierto.`) y de los conflictos, con los cálculos puros que pondría el hook, y el rechazo con el motivo exacto. Las variantes «en curso» y «caído» no cambian. |
  | `test_coordinador.py::test_el_orden_del_caso_se_reconstruye_solo_con_los_eventos` | Cada turno empieza con `mensaje_analista` (R2). | La secuencia exacta añade `("mensaje_analista", None)` tras `caso_iniciado`. |
  | `test_casos_reglas.py`: casos b, c (dos) y el límite de devoluciones; `test_casos_cobertura.py`: los tres del caso f; `test_casos_informe.py`: caso g, caso escalado y SC-003 con escalamiento; `test_modo_demo.py`: los tres en demo | FR-020: la categoría delegada tiene que aparecer en un mensaje del analista, y sus solicitudes no la nombraban (por ejemplo, «talleres» o «panaderías» con la solicitud de Tienda Verde). | Cambia solo la **entrada**: cada caso pide el due diligence con la categoría que delega su guion (`SOLICITUD_B`, `SOLICITUD_C`, `SOLICITUD_G`, `SOLICITUD_A` o «Solicitud de <categoría>.» en demo). Ninguna aserción cambia. |
  | `test_hooks.py::test_limitacion_conocida_el_stop_exige_el_informe_aunque_el_turno_sea_una_pregunta` (T024) | FR-015: ya no es una limitación sino lo especificado (US4-1). | Se conserva con otro nombre (`test_con_el_comercio_identificado_una_pregunta_no_es_una_espera_y_exige_el_informe`) y otro comentario; la aserción no cambia. Se añade `test_con_la_categoria_bloqueada_sin_resultado_la_pregunta_es_una_espera`. |
  | `test_hooks.py::test_con_el_informe_no_vigente_el_motivo_nombra_lo_que_cambio` y `test_main.py::_ejecutar_caso_simulado` | FR-027: una consulta de noticias sin argumentos no es del comercio identificado. | Cambia solo la **entrada**: la consulta de noticias lleva `{"identificador": "CO-TV-0001"}`, el dato delegado. Ninguna aserción cambia. |
  | `servidor_mcp/test_decisiones.py`: la ayuda `_escalamiento`, `…sigue_aceptando_el_formato_de_hallazgos_del_5` (ahora `…rechaza_el_formato…`), `…conserva_los_cinco_campos` y `…nombra_los_cinco_campos` (ahora seis), `…le_falta_un_campo` (más `conflictos`) y `…con_un_hallazgo_sin_fuente_es_un_campo_faltante` (ahora `entrada_invalida` con el problema) | Cambia el contrato de `escalar_a_cumplimiento` (R6): afirmaciones del #9 y `conflictos`. | La ayuda pasa al formato nuevo; cada test conserva su igualdad exacta sobre la forma nueva, y el de la forma vieja se invierte (la forma vieja ahora se rechaza, con las rutas exactas). |
  | `servidor_mcp/test_servidor.py`: la ayuda `_escalamiento`, `…sin_campos_da_los_cinco_faltantes` (seis), `TIPOS_JSON` (causa texto o lista, y `conflictos`) y `TIPOS_INCORRECTOS` (más `conflictos`) | Lo mismo, por el protocolo. | Igualdades exactas sobre el contrato nuevo. |
  | `test_hooks.py`: la ayuda `_escalamiento`, `test_el_escalamiento_sustituye_la_cobertura_aunque_el_libro_este_sellado` (parametrizado), `test_una_excepcion_en_el_escalamiento…` y el de las 625 combinaciones | El hook valida el resumen y pone comercio, causa y conflictos (R5); con el sello, la cobertura y los conflictos van como no calculados. | El resumen cita la consulta del caso; las igualdades exactas incluyen ahora todo lo que pone el código (con el sello, `COBERTURA_NO_CALCULADA` en vez de la calculada: cambio a sabiendas de R5) y los eventos `[cobertura_sustituida, datos_sustituidos]`. |
  | `test_hooks_sesiones.py::Caso.escalar`, `test_casos_cobertura.py` (escalamiento con noticias caído), `test_sesion_simulada.py` (pasarela y `escalar_con`) | La simulación y la pasarela simulada validan el resumen como la real. | Cambia la **entrada** a un resumen válido (`resumen_del_caso` o `_resumen_valido`); el caso f comprueba exactamente las afirmaciones, la acción y la causa que llegan. |
  | `test_reglas.py`: `_libro_con` y las ayudas con escalamientos | `escalamiento_cubre` cuenta solo el comercio actual (R8) y estos estados tienen `CO-TV-0001` identificado. | Los escalamientos llevan `CLAVE_TV`, la clave de su comercio; las aserciones no cambian. |
  | `test_reglas.py::test_sin_causas_una_recomendacion_que_no_habilita_se_acepta_sin_escalar`, ahora `…no_habilitar_se_acepta_sin_escalar_y_decide_cumplimiento_exige_escalar` | FR-004: `decide_cumplimiento` exige un escalamiento del comercio actual (D5 del #9). | `no_habilitar` sigue aceptándose igual; `decide_cumplimiento` pasa de `[]` al rechazo exacto, y con el escalamiento vuelve a `[]`. |
  | `test_hooks.py`: 11 tests del #8 y del #9 sobre cobertura, forma, fuentes y comercio del informe (las 625 combinaciones, los frentes cubiertos sin afirmación, el comercio pedido, los eventos de datos, etc.) | Usaban `decide_cumplimiento` como recomendación de relleno, sin escalar: FR-004 la rechaza. | Cambia solo la **entrada** a `no_habilitar`; lo que prueban (cobertura, forma, fuentes, comercio) no depende de la recomendación. |
  | `test_configuracion.py`: `PASOS_FIJOS_PEOR_CASO`, el parametrizado del presupuesto y el valor actual | R10: dos pasos fijos más. | `8 → 10`; `(1, 3, 19) → 21`, `(0, 0, 8) → 10`, `(3, 5, 37) → 39`, `(2, 3, 27) → 29`; `== 21  # 19 hasta el #9`. La comparación con `MAX_TURNOS_SEGURIDAD` sigue. En el barrido, `test_un_reintento_por_frente_y_ocho_pasos_fijos` pasa a `…_diez_pasos_fijos`: el nombre dice lo que comprueba. |
  | `test_sondeo_hooks.py::test_los_experimentos_del_8_se_ejecutan_despues_de_los_del_7` | g6 (`_reanudacion`) se añade al final. | La lista exacta añade `_reanudacion`. |
  | **Barrido previo al PR** (T059): `test_reglas.py::test_alto_riesgo_escalado_acepta_decide_cumplimiento_y_no_habilitar` | No cambia por el diseño: se **refuerza**. Para `habilitar` solo se comprobaba que hubiera algún rechazo. | `habilitar` tras escalar se rechaza exactamente con `["I.3"]`. Ninguna aserción anterior se quita. |

  **Tabla cerrada en T050.** Ningún test se borró; los que cambiaron conservan igualdades exactas o cambian solo su entrada.

  Se esperan, como mínimo:
  - los de `escalar_a_cumplimiento` con la forma vieja: `test_decisiones.py`, `test_servidor.py`, `test_hooks.py`, `test_casos_reglas.py`, `test_casos_cobertura.py`, `test_casos_informe.py` y `test_sesion_simulada.py`;
  - los que construyen `libro.escalamientos` con `frozenset`: `test_reglas.py`, `test_libro.py` y `test_hooks*.py`;
  - los de `decide_cumplimiento` sin escalar;
  - el presupuesto de 19 a 21 en `test_configuracion.py`;
  - la limitación del #9 (T024);
  - las instrucciones en `test_coordinador.py` y `test_modo_demo.py`.
- [X] T047 Presupuesto (R10) en `src/due_diligence/configuracion.py`: `PASOS_FIJOS_PEOR_CASO = 10`, con el comentario de las dos filas nuevas (escalamiento rechazado y corregido, y noticias de nuevo). El test parametrizado de `test_configuracion.py` pasa a `(1, 3, 21), (0, 0, 10), (3, 5, 39), (2, 3, 29)`, y el del valor actual, a `== 21  # 19 hasta el #9`. El comentario dice que el presupuesto es por turno (R1, medido).
- [X] T048 [P] Línea de comandos (R12, FR-019, contrato) en `src/due_diligence/__main__.py`, con sus tests en `test_main.py`:
  - imprime «Esperando al analista: <motivo>» o «Sin espera del analista», y los escalamientos registrados con su id y sus causas (etiquetas fijas);
  - con espera y sin `--sin-continuar`, pregunta por la entrada estándar; con un texto, llama a `caso.continuar` y vuelve a imprimir; con una línea vacía o fin de entrada, termina;
  - con `--sin-continuar`, no pregunta;
  - los tests inyectan la entrada (función `leer`) y no usan la consola real.
- [X] T049 [P] Sondeo repetible en `src/due_diligence/sondeo_hooks.py`, con sus tests en `test_sondeo_hooks.py`:
  - g5 (`ENTRADA_ESCALAMIENTO`) pasa al formato nuevo (afirmaciones, `accion_recomendada` y `conflictos`);
  - se añade g6, `resume`: dos `query()` con Haiku. La segunda reanuda la primera, ejecuta su `Stop` y `num_turns` es del turno. Es la medición de R1, repetible.
  **Notas de la fase 8**:
  - T044: N-0001 sale de `respuesta_noticias`, compartida por la `PasarelaSimulada` y el `EjecutorSimulado` (las noticias de los casos de extremo a extremo vienen del ejecutor, no de la pasarela simulada).
  - T045: los 8 casos pasaron al escribirlos (prueban piezas ya construidas). Con la mutación que quita la espera del `Stop` fallan 2; sin FR-027 en la cobertura, 1.
  - T045, «ninguna salida contiene el nombre ni `PE-0005`»: los eventos `frente_inicio` del #6 llevan a propósito el contexto entregado al subagente. La comprobación cubre los eventos de reglas y de decisiones, los motivos del cierre y la cobertura.
  - T048: `main(argumentos, leer=input)`; la conversación es recursiva (`_conversar`), sin `while`.
  - T049: g6 (`_reanudacion`) repite la medición de R1; g5 usa el resumen del #10.
- [X] T050 Fase 8: ruff, la suite completa y la tabla de T046 cerrada. Commit «casos (a), (b) y (d), línea de comandos y presupuesto (#10)». **PARADA DE REVISIÓN B**:
  - Claude se detiene y resume a la analista el bloque B (escalamiento con criterio, resumen al oficial, casos de extremo a extremo y línea de comandos), con la tabla de T046;
  - no sigue hasta su visto bueno.

---

## Fase 9: documentación

- [X] T051 [P] `DECISIONES.md`, que solo se amplía (decisión 13 del plan):
  - el escalamiento que se puede denegar, como cambio respecto al #8;
  - `decide_cumplimiento` con escalamiento;
  - las tres esperas y D3 del #9 fuera de ellas;
  - la categoría de los mensajes, con sus riesgos;
  - FR-027;
  - el cierre por turno;
  - el presupuesto de 21;
  - D1, D2 y D3;
  - el rechazo del informe durante la espera (cambio respecto al #9).
- [X] T052 [P] `README.md`: la continuación del caso en la línea de comandos (`--sin-continuar`) y el resumen al oficial.
- [X] T053 Fase 9: commit «documentación del #10».

---

## Fase 10: validación

- [X] T054 Q1 y Q2 del quickstart: ruff, la suite completa y `test_casos_escalamiento.py` en verde. Anotar aquí el número de tests (frente al de T002): **4388** (4153 en T002); formato y ruff limpios; `test_casos_escalamiento.py`, 8 de 8.
- [X] T055 [MANUAL] Q3, caso (a) con el modelo real (Opus 5.5, ≈ 0,15 a 0,30 USD). Anotar:
  - `escalamiento_registrado` y su causa;
  - el informe `decide_cumplimiento` vigente;
  - si hubo `resumen_rechazado` y si el coordinador lo corrigió;
  - el archivo `ESC-….json`;
  - turnos, coste y duración.

  **SC-005**: la analista lee solo ese archivo y responde las cinco preguntas de US2-6.

  **Resultado (aprobado por la analista)**:
  - `ESC-6871431f` («cubre: categoría de alto riesgo», evento 17) **antes** que `INF-1b5cc60c`, `decide_cumplimiento` vigente (evento 20).
  - Sin resúmenes rechazados. «Caso completo: sí». 7 de 30 turnos, 0,1863 USD, 50,8 s.
  - **SC-005**: la analista leyó solo el resumen guardado y respondió sin dudas las cinco preguntas de US2-6 (5 de 5). La acción recomendada es concreta y sirve sin la conversación.
- [X] T056 [MANUAL] Q4, caso (b) con el modelo real. Anotar:
  - 0 escalamientos;
  - `habilitar` vigente;
  - «Caso completo: sí»;
  - si el modelo intentó escalar (`bloqueo_regla [V]`).

  **Resultado (aprobado por la analista)**: sin escalamientos, `INF-e4797cf6` `habilitar` vigente, caso completo. El modelo no intentó escalar: el rechazo de FR-002 queda probado por los tests y la mutación (fase 7). 6 de 30 turnos, 0,1080 USD, 40,5 s.
- [X] T057 [MANUAL] Q5, caso (d) en dos turnos con el modelo real. Anotar (FR-024):
  - turno 1: que se pidió el identificador, la espera y 0 consultas de listas;
  - turno 2 (`CO-AM-0005`): que **se consultaron listas**, que se volvió a delegar noticias (N-0001) y el informe vigente;
  - turnos de cada consulta frente al presupuesto de 21, y coste.

  **Resultado (aprobado por la analista)**:
  - **Turno 1**: `espera_analista` (evento 12), listas `sin_iniciar`, sin escalamiento ni informe, «Caso completo: no». 4 de 30 turnos.
  - **Turno 2**, con «El identificador es CO-AM-0005.», en el mismo caso:
    - el registro y noticias, vueltos a delegar «con otra entrada»;
    - N-0001 en el informe;
    - **listas consultadas** con `CO-AM-0005` y `PE-0005`;
    - `INF-f7ba3dfe`, `habilitar` vigente, caso completo. 5 de 30 turnos.
  - El coordinador advirtió al analista que `CO-AM-0005` es «Almacén Mirador Norte SAS» y ofreció rehacer el caso con `CO-AM-0004`, sin elegir por su cuenta. Coste ≈ 0,19 USD en total.
- [X] T058 [MANUAL] Sondeo repetible (Haiku, ≈ 0,02 USD): todas las mediciones `coinciden`, con g5 en el formato nuevo y g6 (`resume`).

  **Resultado (aprobado por la analista)**: 23 coinciden, 0 difieren, 0 inconclusas. g5 y las tres de g6 coinciden. `$LASTEXITCODE` 0.
- [X] T059 Commitear las anotaciones de T054 a T058 en este archivo. **Ningún commit después de la revisión de `/abrir-pr`.** Después, `/abrir-pr`. La descripción del PR incluye la tabla de T046 y las desviaciones D1, D2 y D3 del plan.

## Para otros tickets (no se corrige en el #10)

- **#12, simulación de noticias**: sin un resultado asignado, el `EjecutorSimulado` da a noticias la fuente por defecto `FUENTE` («Registro Mercantil Ficticio del Sur»); la real es «Diario Ficticio del Sur». Por eso el resumen simulado del caso (a) cita el registro como fuente de noticias. Solo afecta a la simulación: la pasarela real usa su fuente y FR-004 compara con la fuente que devolvió cada consulta (observación de la analista en la parada B).
- **#11, hora en UTC frente a la de Colombia** (observación de la analista en T056): las horas se guardan en UTC (#9, R10). En el caso (b), el coordinador le dijo al analista que el informe tenía fecha «un día después de hoy»: era la 01:06 UTC del 19, las 20:06 del 18 en Colombia. Para el #11:
  - la interfaz muestra la hora de Colombia;
  - el coordinador sabe que `registrado_en` está en UTC.

---

## Dependencias y orden de ejecución

- **Fase 1** (T001, T002) → **Fase 2**: T003 → T004; T005 → T006; T007 → T008, independientes entre sí; T009 al final.
- **US3 (fase 3)**: T010 → T011; T012 → T013 (necesita T011); T018 antes de T014 → T015; T016 → T017; T019. Necesita la fase 2.
- **US5 (fase 4)**: T020 → T021 → T022. Necesita T011 (la espera de categoría) y T015 (los mensajes del caso).
- **US4 (fase 5)**: T023 y T024 (necesitan T013 y T021); T025 → T026; T027 → T028; T029. **Parada A.**
- **US2 (fase 6)**: T030 → T031 → T032 → T033 (la pasarela, en serie); T034 → T035; T036 → T037; T038. Necesita la parada A (fuentes de R7 y esperas).
- **US1 (fase 7)**: T039 → T040 → T041 → T042; T043. Necesita T035 (`_escalar_previo`).
- **T046**: continua, de la fase 2 a la 8; se cierra en T050.
- **Fase 8**: T044 → T045; T047, T048 y T049 en paralelo; T050. **Parada B.**
- **Fase 9**: T051 y T052 en paralelo → T053.
- **Fase 10**: T054 → T055 a T058 (manuales, pueden ir juntas) → T059.

## Oportunidades de paralelismo

- **Fase 2**: T003, T005 y T007 tocan archivos distintos.
- **Fase 3**: T010 (`test_reglas.py`), T014 (`test_coordinador.py`), T016 (`test_delegacion.py`) y T018 (`simulacion.py`).
- **Fase 6**: T030 y T034 (pasarela y hook, archivos distintos).
- **Fase 8**: T047, T048 y T049.
- **Fase 9**: T051 y T052.
- **En serie**: todo lo que toca `src/due_diligence/hooks.py` (T013, T021, T035, T037, T042) y todo lo que toca `reglas.py` (T011, T021, T026, T035, T040).

## Estrategia de implementación

1. **Bloque A**: las esperas, la continuación y el cierre por turno cierran el pendiente 2 del #7 y el riesgo residual 5 del #9. Con FR-027, el caso (d) se vuelve correcto en dos turnos.
2. **Bloque B**: el criterio y el resumen cumplen los criterios de aceptación (a), (b) y el resumen validado. El caso (d) de extremo a extremo cierra el tercero.
3. **No se ejecuta un caso con el modelo real antes de T043**: hasta entonces el coordinador no tiene la guía del resumen, y los escalamientos se rechazarían por la forma.
4. **Las paradas A y B** son puntos de revisión de la analista, no de commit.

## Trazabilidad

| Requisito | Tareas |
|-----------|--------|
| FR-001 | T039, T045 |
| FR-002 | T039, T041, T045 |
| FR-003 | T034, T039 |
| FR-004 | T005, T006, T034, T039 |
| FR-005 | T045 |
| FR-006, FR-007 | T030 a T033 |
| FR-008 | T025, T030, T034 |
| FR-009 | T034, T035 |
| FR-010 | T030, T034 |
| FR-011 | T030, T043 |
| FR-012 | T036, T037 (D2: comercio fijo) |
| FR-013 | T014, T015, T045 |
| FR-014 | T010 a T013, T020, T023 |
| FR-015 | T024 |
| FR-016 | T012, T013 (informe), T036, T039, T041, T042 (escalamiento) |
| FR-017 | T016, T017 |
| FR-018 | T014, T015 |
| FR-019 | T048 |
| FR-020 | T020, T021 |
| FR-021 | T034 |
| FR-022 | reglas para todas las tareas, T010, T020, T034, T045 |
| FR-023 | T045 |
| FR-024 | T055, T056, T057 |
| FR-025 | reglas para todas las tareas |
| FR-026 | alcance: ninguna tarea toca la interfaz de chat (#11) ni la suite de los siete casos (#12) |
| FR-027 | T025, T026, T045 |
| FR-028 | T027, T028, T057 |
| SC-001 | T045, T055, T056 |
| SC-002 | T030, T032, T034 |
| SC-003 | T045, T057 |
| SC-004 | T023 |
| SC-005 | T055 |
| SC-006 | T009, T019, T022, T029, T038, T050, T054 |
| R4 (tests a y b) | T014 |
| D2 (comercio fijo con el sello) | T030, T036 |
| D3 (alto riesgo en la espera) | T041 |
