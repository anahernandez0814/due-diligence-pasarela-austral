---

description: "Lista de tareas del ticket #8, errores estructurados y cobertura parcial"
---

# Tasks: Errores estructurados y cobertura parcial

**Input**: documentos de diseño en `specs/008-errores-estructurados-cobertura/`: [plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/delegar-frente.md](contracts/delegar-frente.md),
[contracts/cobertura.md](contracts/cobertura.md) y [quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/ y
quickstart.md.

**Tests**: obligatorios (constitución X y FR-015). Van junto a cada módulo, en
`src/due_diligence/test_*.py`, y se escriben antes que el código: deben fallar primero. Ninguno
llama al modelo ni a la red (SC-006). Usan `EjecutorSimulado`, `SesionSimulada`,
`CoordinadorSimulado` y `PasarelaSimulada` de `simulacion.py`, y mensajes del SDK construidos con sus
propias clases.

**Organization**: una fase por historia de la spec. **El orden es el de las dependencias del plan,
no el de prioridad**: US1 (el caso f, P1) usa el error estructurado (US2), el reintento (US3) y la
cobertura (US4), así que se cierra al final.

1. Fase 1: setup. Fase 2: fundamentos (eventos, estado, constantes y simulación). Al final de la
   fase 2, *parada de revisión A*.
2. US2, error estructurado (P1): fase 3. US3, política de reintento (P1): fase 4. US4, cobertura
   calculada (P2): fase 5.
3. US1, cobertura registrada y caso (f) (P1): fase 6. Al final, *parada de revisión B*.
4. Sondeo y documentación: fase 7. Validación: fase 8.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La verificación del
cierre del #8 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US4).
- **[MANUAL]**: la hace la analista, en una sesión nueva de Claude Code abierta en la raíz y con el
  modelo real. Claude se detiene y espera su confirmación.
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md) o Q# del
  [quickstart](quickstart.md).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Ningún valor con forma real** (tarjeta, NIT, cédula o credencial) en tareas, tests, código ni
  documentación. Se usan los datos ficticios del #5 (`CO-TA-0002`, `Taller Aurora SAS`,
  `CO-TV-0001`, etc.), sin secuencias de 6 o más dígitos seguidos (principio VII).
- **Todo en español** (FR-017). Los motivos y eventos no repiten nombres ni identificadores del
  comercio, y **nunca el texto interno de una excepción** (US2-7). Los tests lo comprueban con:
  - una excepción simulada cuyo texto es `TEXTO-INTERNO-FICTICIO`;
  - un nombre ficticio que no debe aparecer en la salida.
- **Contratos del #6 y del #7 intactos**: `tipo`, `reintentable` y `obtenido` del error no cambian
  de significado, salvo `reintentable`, que ahora tiene en cuenta los reintentos que quedan (R3, R4).
  Los dos tests de `test_delegacion.py` con listas antes del registro y `reintentable is True`
  (`test_listas_sin_haber_delegado_el_registro_se_rechaza_con_reintentable` y
  `test_con_el_registro_rechazado_por_falta_de_dato_listas_se_rechaza_con_reintentable`) **no se
  editan** (FR-003).
- **Un solo cálculo de la cobertura** (R5): `cobertura.calcular_cobertura`. `Caso.completo`, los
  hooks y `__main__` lo llaman; ninguno vuelve a comprobar por su cuenta la situación de los frentes.
- **API de `claude-agent-sdk` 0.2.168 (R1)**:
  - `updatedInput` en `hookSpecificOutput` de `PreToolUse` **sustituye la entrada entera**; se
    construye solo con `reemplazar_entrada(entrada_completa)`;
  - las demás salidas, solo con `permitir()`, `denegar(motivo)` y `bloquear_cierre(motivo)` (#7).
- **El código no controla el ciclo** (FR-010 del #6): `test_sin_control_propio.py` sigue en verde.
  Los reintentos se cuentan en un diccionario del `Delegador`, sin `while`. `MAX_REINTENTOS_POR_FRENTE`
  vive solo en `configuracion.py`.
- **No se escribe en el código el nombre del archivo de variables de entorno** (R8 del #6). Ningún
  test ni comando de estas tareas lo lee.
- **Commits** por partes lógicas en la rama `008-errores-estructurados-cobertura`, nunca en `main`,
  sin `git commit --amend`. Un commit nuevo invalida el veredicto del anterior, así que **ningún
  commit va después de la revisión** de `/abrir-pr`.
- **Formato**: el hook del #3 formatea cada `.py` escrito o editado. Cada fase de código termina con
  `uv run ruff format .` y `uv run ruff check .`.
- **Tests**: `uv run pytest src/due_diligence`, y la suite completa (`uv run pytest`) al cerrar cada
  fase.
- `DECISIONES.md` no se recorta: solo se amplía. **`docs/bitacora-decisiones.md` no se edita en este
  ticket.**

---

## Fase 1: Setup

- [X] T001 Confirmar que la rama es `008-errores-estructurados-cobertura` y commitear este
  `tasks.md`. La spec y el plan ya están en `f207a9f` y `5b54494`. Mensaje convencional en español.
- [X] T002 Línea base: `uv run pytest` y `uv run ruff check .` en verde antes de tocar nada. Anotar
  aquí el número de tests que pasan (referencia para T031): **2482** (ruff limpio).

---

## Fase 2: Fundamentos (bloquean todas las historias)

**Propósito**: lo que usan todas las historias: tipos de evento, el último error de cada frente en
el estado, la causa como conjunto cerrado, las constantes de reintento y de presupuesto de turnos,
y la simulación de `updatedInput`. Tests primero.

### Eventos, estado y causa

- [X] T003 [P] Tests en `src/due_diligence/test_eventos_estado.py` (data-model, «Eventos nuevos» y
  «Cambios en entidades existentes»):
  - `frente_reintento`, `reintento_denegado` y `cobertura_sustituida` están en `eventos.TIPOS` y
    se registran sin `TipoDeEventoInvalido`;
  - **`cobertura_registrada` no existe** (indicación de la analista);
  - `EstadoCaso().errores == {}` y dos estados no comparten el diccionario;
  - `Causa` tiene exactamente los ocho valores `terminacion_anomala`, `error_de_fuente`,
    `sin_consultas`, `resultado_invalido`, `consulta_incompleta`, `rechazado`, `cancelado` e
    `invalidado`.
- [X] T004 Implementar lo de T003:
  - en `src/due_diligence/eventos.py`, las constantes `TIPO_FRENTE_REINTENTO`,
    `TIPO_REINTENTO_DENEGADO` y `TIPO_COBERTURA_SUSTITUIDA`, añadidas a `TIPOS`;
  - en `src/due_diligence/estado.py`, el `StrEnum` `Causa` con esos ocho valores y el campo
    `errores: dict[Frente, dict[str, Any]]` de `EstadoCaso`, con `default_factory=dict`. Es el
    último `ErrorFrente` de cada frente.
  
  `Causa` va en `estado.py` para que `cobertura.py` lo use sin importar la delegación (data-model).
  Hace pasar T003.

### Constantes (R2, R3)

- [X] T005 [P] Tests en `src/due_diligence/test_configuracion.py`:
  - `MAX_REINTENTOS_POR_FRENTE == 1` y `PASOS_FIJOS_PEOR_CASO == 8`;
  - `presupuesto_turnos_peor_caso(max_reintentos, max_cierres)` devuelve
    `PASOS_FIJOS_PEOR_CASO + len(Frente) * max_reintentos + max_cierres` con otros valores (por
    ejemplo, `(3, 5)` da 25);
  - `PRESUPUESTO_TURNOS_PEOR_CASO == presupuesto_turnos_peor_caso(MAX_REINTENTOS_POR_FRENTE,
    MAX_CIERRES_IMPEDIDOS)`, que hoy vale 15;
  - **`PRESUPUESTO_TURNOS_PEOR_CASO <= MAX_TURNOS_SEGURIDAD`**;
  - el valor de `PRESUPUESTO_TURNOS_PEOR_CASO` en `configuracion.py` no es un literal: el test lo
    comprueba con `ast`, como `test_sin_control_propio.py` (indicación de la analista).
- [X] T006 Implementar lo de T005 en `src/due_diligence/configuracion.py`, con estos comentarios:
  - en `MAX_REINTENTOS_POR_FRENTE = 1`: «PROTECCIÓN, no control del ciclo (principio III); 1 por
    indicación de la analista; R3»;
  - en `PASOS_FIJOS_PEOR_CASO = 8`: las filas de la tabla de R2 que no dependen de otras
    constantes;
  - `presupuesto_turnos_peor_caso(...)`, y `PRESUPUESTO_TURNOS_PEOR_CASO` calculado con ella.
  
  Hace pasar T005.

### Simulación (R8)

- [X] T007 [P] Tests en `src/due_diligence/test_sesion_simulada.py`:
  - con un `PreToolUse` que devuelve `reemplazar_entrada(...)`, la herramienta recibe esa entrada
    **entera** y `PostToolUse` y `PostToolUseFailure` ven en `tool_input` la entrada sustituida;
  - con solo `{cobertura}`, la herramienta recibe solo `{cobertura}`, sin fusionar (R1, e3);
  - un `deny` sigue ganando aunque otro hook devuelva `updatedInput`. El test lleva un comentario:
    es un supuesto conservador de la simulación, **no medido** (R1), y producción nunca combina dos
    `PreToolUse` sobre la misma herramienta;
  - `en_secuencia(r1, r2)` da `r1` en la primera ejecución, `r2` en la segunda y `r2` en las
    siguientes;
  - el paso `("escalar_con", entrada)` de `CoordinadorSimulado` llama a `escalar_a_cumplimiento`
    con esa entrada.
  
  Para `reemplazar_entrada`, el test construye el diccionario a mano hasta que exista (T023) y
  después se cambia a la función.
- [X] T008 Implementar lo de T007 en `src/due_diligence/simulacion.py`:
  - `SesionSimulada.llamar`: si no hay `deny` y alguna salida de `PreToolUse` trae
    `hookSpecificOutput.updatedInput`, `argumentos` pasa a ser esa entrada (copia), y se usa en la
    llamada y en `base["tool_input"]`;
  - la función `en_secuencia(*resultados)`, que devuelve `contexto -> ResultadoFrente`;
  - el paso `escalar_con` en `CoordinadorSimulado`, que se documenta en su docstring.
  
  Hace pasar T007.
- [X] T009 Fase 2 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest` en
  verde. Los tests del #6 y del #7 no cambian. Commit «fundamentos del ticket #8».
  **PARADA DE REVISIÓN A.**

---

## Fase 3: US2 Error estructurado de cada frente (P1)

**Goal**: cada frente no cubierto devuelve el `ErrorFrente` de
[data-model.md](data-model.md) y [contracts/delegar-frente.md](contracts/delegar-frente.md), sin el
texto interno de una excepción.

**Independent Test**: con el `EjecutorSimulado`, cada forma de fallo produce el error con
`frente`, `tipo`, `causa`, `mensaje`, `reintentable`, `intento`, `reintentos_restantes` y
`obtenido`.

- [X] T010 [US2] Tests en `src/due_diligence/test_delegacion.py` (FR-001 a FR-004, US2-1 a US2-7,
  SC-004). Un test por causa:
  - `error_de_fuente` reintentable (`error_estructurado("servicio_no_disponible", True)`) →
    `reintentable is True`, `intento == 1` y `reintentos_restantes == 1`;
  - `error_de_fuente` no reintentable → `reintentable is False`;
  - errores mezclados (uno reintentable y otro no) → `False`;
  - un error con `reintentable` ausente o `"true"` (texto) → `False`;
  - `terminacion_anomala` (con `terminacion_anomala()` y con una excepción del ejecutor) →
    `False`, y la causa no es `error_de_fuente`;
  - `sin_consultas`, `resultado_invalido` y `consulta_incompleta` (listas sin el representante),
    todos con `False`.
  
  Además:
  - la prioridad de la tabla de data-model cuando concurren dos causas;
  - listas con el comercio consultado bien y el representante con error → `obtenido.resultados`
    trae el resultado del comercio con `contenido` y `metadatos` separados (US2-3);
  - un bloqueo de hook (`TIPO_BLOQUEADO_POR_HOOK`) no cuenta como error ni como causa (FR-004);
  - **excepción** `RuntimeError("TEXTO-INTERNO-FICTICIO")` del ejecutor: el texto no aparece en
    `mensaje`, `obtenido.terminacion`, `estado.motivo(frente)`, el detalle de ningún evento ni
    `estado.errores`. Sí aparece `excepción RuntimeError` (US2-7);
  - un rechazo sin ejecución lleva `frente`, `causa: "rechazado"`, `intento: 0` y
    `reintentos_restantes == MAX_REINTENTOS_POR_FRENTE`;
  - **los dos tests de listas reintentable no se editan** y siguen pasando;
  - `estado.errores[frente]` guarda el último error, y un frente que después termina bien borra su
    entrada;
  - un frente cancelado (`asyncio.CancelledError` del ejecutor) deja `estado.errores[frente]`
    con la causa `cancelado`;
  - `entrada_invalida` no lleva `frente`.
- [X] T011 [US2] Implementar lo de T010 en `src/due_diligence/delegacion.py`:
  - `_evaluar` devuelve `(situacion, motivo, causa)` con la prioridad de data-model;
  - `_respuesta` y `_rechazar` añaden `frente`, `causa`, `intento` y `reintentos_restantes` (en
    esta fase, `intento = 1` o `0`; el historial llega en T014). `reintentable` es la causa
    reintentable según la tabla y `is True` en cada error real;
  - `_concluir` y `_rechazar` escriben `estado.errores` y lo borran al terminar;
  - el `finally` de `_ejecutar` deja la causa `cancelado`;
  - en `_ejecutar`, `detalle_terminacion = f"excepción {type(error).__name__}"`, sin `{error}`.
  
  Hace pasar T010 sin romper el resto de la suite.
- [X] T012 [US2] Fase 3 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest`
  en verde.

---

## Fase 4: US3 Reintentar solo lo reintentable (P1)

**Goal**: la política de [contracts/delegar-frente.md](contracts/delegar-frente.md): la pide el
modelo, la guarda el `Delegador`, con 1 reintento por `(frente, contexto)` (R3).

**Independent Test**: con `en_secuencia`, un error reintentable seguido de un éxito deja el frente
terminado tras 2 ejecuciones; uno no reintentable se ejecuta 1 vez; un tercer pedido se deniega.

- [X] T013 [US3] Tests en `src/due_diligence/test_reintentos.py`, un archivo nuevo (FR-005 a
  FR-009, US3-1 a US3-6, SC-002):
  - **US3-1 y US3-2**: noticias con `en_secuencia(error reintentable, éxito)`. El segundo
    `delegar` con la misma entrada ejecuta otra vez (`len(ejecutor.llamadas_de(NOTICIAS)) == 2`),
    el frente queda `terminado` y los eventos conservan el primer `frente_fin` no terminado y un
    `frente_reintento` con «1 de 1» y la causa;
  - **US3-3**: con un error no reintentable, el segundo `delegar` no ejecuta, devuelve el mismo
    error con `reintentable: false` y `reintentos_restantes: 0` y registra `reintento_denegado`
    con «no es reintentable»;
  - **US3-4**: con un error reintentable persistente, la segunda llamada ejecuta y la tercera no.
    La tercera registra `reintento_denegado` con «se agotaron los reintentos», y la respuesta de la
    segunda ya trae `reintentable: false`;
  - **US3-5**: un frente terminado devuelve lo guardado y `delegacion_repetida`, sin ejecutar;
  - **US3-6**: con otra entrada (otra categoría), se ejecuta aunque la primera agotara su
    reintento, y la nueva clave tiene su propio reintento;
  - **pedidos simultáneos**: dos `delegar` iguales con `asyncio.gather` sobre un frente con
    retardo y error reintentable producen 1 ejecución, y los dos reciben el mismo error;
  - **un rechazo sin ejecución** (listas antes del registro) no cuenta: tras el registro, listas
    se ejecuta como primer intento (`intento == 1`);
  - **registro que cambia de comercio**: listas se invalida y su siguiente ejecución es
    `intento == 1`;
  - **reintento con otro error**: si el segundo intento falla con un error no reintentable, no hay
    más reintentos;
  - **el texto de `DESCRIPCION`** contiene «reintentable true» y «una vez más» (R7).
- [X] T014 [US3] Implementar lo de T013 en `src/due_diligence/delegacion.py`:
  - `self._intentos: dict[tuple[Frente, str], int]` y `self._ultimo: dict[tuple[Frente, str],
    dict]`;
  - en `delegar`, tras construir el contexto, la regla de data-model, «Historial de intentos»;
  - **la espera a una ejecución en curso de la misma clave devuelve su resultado sin reintentar**:
    se recuerda si esta llamada esperó en `_esperar_si_en_curso`;
  - `intento` y `reintentos_restantes` salen del historial;
  - eventos `frente_reintento` y `reintento_denegado`, con los textos de data-model;
  - `DESCRIPCION` ampliada como dice el contrato.
  
  Sin `while` (`test_sin_control_propio.py`). Hace pasar T013.
- [X] T015 [US3] Fase 4 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest`
  en verde. Commit «error estructurado y política de reintento (#8)».

---

## Fase 5: US4 Cobertura calculada por el código (P2)

**Goal**: `calcular_cobertura(estado)`, pura, y su uso en `Caso` y en la línea de comandos (R5,
[contracts/cobertura.md](contracts/cobertura.md)).

**Independent Test**: en las 625 combinaciones de situación de los cuatro frentes, la cobertura es
completa solo con los cuatro `terminado`.

- [ ] T016 [P] [US4] Tests en `src/due_diligence/test_cobertura.py`, un archivo nuevo (FR-010,
  FR-012, US4-1 a US4-5, SC-003):
  - **las 5⁴ = 625 combinaciones** de `Situacion` (se fuerzan con `estado._situaciones`, solo en
    el test): `completa` ⇔ las cuatro `terminado`;
  - **cada frente no cubierto** lleva un motivo no vacío; `sin_iniciar` lleva «no se delegó» y
    `en_curso`, «seguía en curso»;
  - con `estado.errores[f]`, la causa y los intentos aparecen en `CoberturaFrente` y en su línea;
  - **listas invalidada** (`MOTIVO_COMERCIO_CAMBIO`) → no cubierto con ese motivo;
  - **`lineas()`**:
    - la primera es exactamente «Cobertura completa: 4 de 4 frentes cubiertos.» o «Cobertura
      incompleta: N de 4 frentes cubiertos.»;
    - después, una línea por frente en el orden registro, listas, noticias, categoría, con el
      formato del contrato;
  - **no repite datos**: con `estado.solicitud` y un comercio ficticio en el estado, ni el nombre
    ni el identificador aparecen en `lineas()`;
  - **es pura**: `estado.instantanea()` antes y después es igual, y no se registra ningún evento.
- [ ] T017 [US4] Implementar `src/due_diligence/cobertura.py`: `CoberturaFrente` y `CoberturaCaso`
  (dataclasses congeladas), `calcular_cobertura(estado)` y `CoberturaCaso.lineas()`, como en
  data-model y el contrato. Lee `estado.situacion`, `estado.motivo` y `estado.errores`. No importa
  `delegacion`. Hace pasar T016.
- [ ] T018 [P] [US4] Tests (FR-012, FR-014, R2):
  - en `src/due_diligence/test_coordinador.py`:
    - `caso.cobertura` es `calcular_cobertura(caso.estado)`;
    - `caso.completo` es falso si un frente no está cubierto aunque las condiciones del #7 se
      cumplan, y verdadero con los cuatro cubiertos y esas condiciones;
    - `caso.turnos` toma `num_turns` del `ResultMessage` (con `mensaje_de_resultado`, ajustando
      `num_turns`) y es `None` sin `ResultMessage`;
  - en `src/due_diligence/test_main.py`:
    - `imprimir_caso` muestra un bloque «Cobertura:» con `caso.cobertura.lineas()`;
    - muestra «turnos del coordinador: N de 30» o «turnos del coordinador: sin dato».
- [ ] T019 [US4] Implementar lo de T018:
  - en `src/due_diligence/coordinador.py`:
    - la propiedad `cobertura`;
    - `completo` usa `self.cobertura.completa` en lugar de `all(... TERMINADO ...)`, conservando las
      condiciones del #7 y actualizando el docstring («La cobertura declarada es del #8» pasa a
      citar R5);
    - el atributo `turnos`, con `num_turns` en `ejecutar`;
  - en `src/due_diligence/__main__.py`, el bloque «Cobertura:» tras «Frentes:» y la línea de
    turnos en «Números de la validación», con `MAX_TURNOS_SEGURIDAD`;
  - en `src/due_diligence/simulacion.py`, el parámetro `num_turns: int = 1` en
    `mensaje_de_resultado` (U1 del análisis), para que T018 construya un `ResultMessage` con
    otros turnos.
  
  Hace pasar T018.
  
  **Tests del #7 que cambian en este ticket** (I1 del análisis; detalle y justificación en T021).
  Esta tarea **no** edita ninguno: `test_coordinador.py:564-572` cambia en la fase 6, cuando T023
  añade el hook de escalar.
  - `test_hooks.py:798` y `test_hooks.py:866-867`: el informe aceptado devuelve
    `reemplazar_entrada` y registra `cobertura_sustituida`;
  - `test_hooks.py:603-608` y `test_coordinador.py:564-572`: el inventario de hooks del
    coordinador añade el `PreToolUse` de `ESCALAR`;
  - `test_eventos_estado.py`, `test_los_tipos_de_evento_son_los_del_modelo` (#6), ya cambiado en
    T003: el inventario de eventos añade los tres tipos nuevos.
- [ ] T020 [US4] Fase 5 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest`
  en verde. Commit «cobertura calculada por el código (#8)».

---

## Fase 6: US1 Cobertura registrada y caso (f) (P1)

**Goal**: la cobertura que llega a la pasarela es la del código, en los dos canales de decisión
(R1, R6), y el caso (f) se entrega declarando noticias como no cubierto.

**Independent Test**: `test_casos_cobertura.py` con el coordinador simulado: el informe guardado
por la pasarela simulada trae la cobertura del código y `caso.completo` es falso.

- [ ] T021 [US1] Tests en `src/due_diligence/test_hooks.py` (FR-011, R6,
  [contracts/cobertura.md](contracts/cobertura.md)).
  
  **Tests de los tickets #6 y #7 que cambian (I1 del análisis).** Son exactamente cinco: cuatro del
  #7 y un inventario del #6. Ningún otro test de esos tickets se edita. Esta lista y su
  justificación van también en la descripción del PR (T034).
  
  | Test | Hoy | Por qué cambia | Cómo queda (sin debilitarse) |
  |------|-----|----------------|------------------------------|
  | `test_hooks.py:798`, en `test_con_coincidencias_sin_hechos_se_rechaza_habilitar_y_se_exige_escalar` | el informe `decide_cumplimiento`, tras escalar, da `== permitir()` | el hook acepta devolviendo `reemplazar_entrada` (R1, R6) | ver la lista de abajo |
  | `test_hooks.py:866-867`, en `test_el_hook_del_informe_permite_no_habilitar_si_el_caso_esta_escalado` | `no_habilitar` y `decide_cumplimiento` dan `== permitir()` y `eventos == []` | igual que el anterior, y la llamada registra `cobertura_sustituida` | ver la lista de abajo |
  | `test_hooks.py:603-608`, `test_el_coordinador_tiene_los_hooks_de_delegar_informe_y_escalar` | `PreToolUse == [DELEGAR, INFORME]` | hay un `PreToolUse` nuevo de `escalar_a_cumplimiento` (R6) | `PreToolUse == [DELEGAR, INFORME, ESCALAR]`; el resto, igual |
  | `test_coordinador.py:564-572`, `test_el_coordinador_tiene_los_hooks_de_delegar_informe_escalar_y_el_stop` | inventario de hooks del coordinador | el mismo `PreToolUse` nuevo | solo se añade `ESCALAR` a `"PreToolUse"`; el resto del diccionario, igual |
  | `test_eventos_estado.py`, `test_los_tipos_de_evento_son_los_del_modelo` (#6; cambiado en T003) | inventario exacto de `TIPOS` | tres tipos de evento nuevos (data-model) | solo se añaden `frente_reintento`, `reintento_denegado` y `cobertura_sustituida`; ningún tipo anterior sale |
  
  Los dos tests del informe aceptado comprueban, **como mínimo**, lo mismo que hoy, para cada
  recomendación que hoy prueban:
  - la salida **no es una denegación** y `permissionDecision == "allow"`;
  - en `updatedInput`, `recomendacion`, `comercio`, `hallazgos` y cualquier otro campo de la
    entrada llegan **intactos**, y `cobertura == calcular_cobertura(estado).lineas()`;
  - los eventos que registra **esa llamada** son exactamente uno, `cobertura_sustituida`, sin
    ningún `bloqueo_regla`. En el test de la línea 798 se miden los eventos nuevos desde justo
    antes de la llamada, porque el mismo test registra antes un `bloqueo_regla` legítimo.
  
  **`_informe_previo`**:
  - con libro sellado o con una regla que rechaza, sigue denegando como en el #7. Los tests de
    denegación del #7 no se editan;
  - si no, devuelve `reemplazar_entrada({**tool_input, "cobertura": lineas})`, con
    `permissionDecision == "allow"` y la entrada **completa** (comercio, recomendación y hallazgos
    intactos);
  - registra `cobertura_sustituida`. Su detalle dice si la declarada era distinta y **no contiene
    «registrad»**;
  - `tool_input` que no es un objeto → `deny` con `MOTIVO_ENTRADA_MALFORMADA`;
  - una excepción de `calcular_cobertura` (con `monkeypatch` en `hooks.calcular_cobertura`) →
    `deny` con `MOTIVO_FALLO_DE_HOOK` y libro sellado (`fallar_cerrado`);
  - **cuando `_informe_previo` deniega** (por el sello, por una regla o por una entrada
    malformada), **no se registra `cobertura_sustituida`**.
  
  **`_escalar_previo`**:
  - reemplaza la cobertura y registra `cobertura_sustituida`;
  - **con el libro sellado también reemplaza y no deniega**;
  - con `tool_input` que no es un objeto → `permitir()`;
  - **una excepción de `calcular_cobertura` → `allow` + `updatedInput` con `{**tool_input,
    "cobertura": [COBERTURA_NO_CALCULADA]}`**, con el texto exacto «No se pudo calcular la
    cobertura; debe tratarse como incompleta.»;
  - con esa excepción, `libro.fallo_de_hook` queda sellado y el evento `fallo_de_hook` no contiene
    `TEXTO-INTERNO-FICTICIO`;
  - después, `_informe_previo` deniega por el sello;
  - **ninguna salida de `_escalar_previo` tiene `permissionDecision == "deny"`**, en ningún caso
    probado.
  
  **`HooksDelCaso.coordinador()`**: tiene `PreToolUse` para `HERRAMIENTA_ESCALAR`, y son 6 hooks
  registrados en total.
  
  **Las 625 combinaciones (G1 del análisis, SC-003)**: un test parametrizado sobre las 5⁴
  combinaciones de `Situacion` de los cuatro frentes, forzadas en el estado como en T016. En cada
  una:
  - `_informe_previo`, con un informe que las reglas aceptan (recomendación `decide_cumplimiento`
    y libro sin causas), devuelve `updatedInput["cobertura"] == calcular_cobertura(estado).lineas()`;
  - `_escalar_previo` también, exactamente;
  - ninguna línea declara «cubierto» un frente que no está `terminado`.
- [ ] T022 [US1] Tests de extremo a extremo en `src/due_diligence/test_casos_cobertura.py`, un
  archivo nuevo (US1-1 a US1-5, FR-013, SC-001). Se construye como `test_casos_reglas.py` del #7:
  `Caso` con `EjecutorSimulado`, `CoordinadorSimulado` y `PasarelaSimulada`.
  - **Caso (f)**: `CO-TA-0002`, categoría de riesgo bajo, noticias con
    `error_estructurado("servicio_no_disponible", True)` en todas las ejecuciones (como la pasarela
    con `PASARELA_FALLA_NOTICIAS=1`).
    - El guion delega los tres frentes en paralelo, pide noticias otra vez (reintento), otra más
      (denegada), delega listas, registra el informe `habilitar` (con `cobertura: "completa"`
      declarada) y termina.
    - Se comprueba:
      - `pasarela.informes[0]["cobertura"] == caso.cobertura.lineas()`;
      - la primera línea es «Cobertura incompleta: 3 de 4 frentes cubiertos.»;
      - noticias figura «no cubierto», con su causa y 2 intentos;
      - eventos `frente_reintento`, `reintento_denegado` y `cobertura_sustituida`;
      - `caso.completo is False`;
      - registro, listas y categoría `terminado`, con los mismos resultados que en el contraste
        (FR-013).
  - **Contraste sin la caída**: cobertura completa, `caso.completo is True` y ningún
    `frente_reintento` (Q7).
  - **Escalamiento**: un comercio de alto riesgo con noticias caído y el paso `("escalar_con", {...
    "cobertura": "completa" ...})` → `pasarela.escalamientos[0]["cobertura"]` es la del código.
  - **Comprobación de mutación**, a mano y sin commitear: con `_informe_previo` devolviendo
    `permitir()` tras las reglas, el caso (f) falla. Anotarlo en T031.
- [ ] T023 [US1] Implementar lo de T021 y T022 en `src/due_diligence/hooks.py`:
  - `reemplazar_entrada(entrada)` y `COBERTURA_NO_CALCULADA`;
  - en `_informe_previo`, tras las reglas: comprobación de objeto, `calcular_cobertura`, evento y
    `reemplazar_entrada`;
  - `_escalar_previo`;
  - **`degradar_escalamiento(hook, estado, eventos)`**, que no deniega (contrato):
    1. sella con el mismo `_registrar_fallo` del #7;
    2. si la entrada es un objeto, devuelve `reemplazar_entrada` con `COBERTURA_NO_CALCULADA`;
    3. si no, `permitir()`.
  - `coordinador()` registra `_escalar_previo` envuelto con `degradar_escalamiento`, **no** con
    `fallar_cerrado`.
  
  Cambiar T007 para usar `reemplazar_entrada`. Hace pasar T021 y T022.
- [ ] T024 [US1] Instrucciones del coordinador (R7, FR-008; sirve también a US3):
  - tests en `src/due_diligence/test_coordinador.py` y `src/due_diligence/test_modo_demo.py`:
    - `_REGLA_FALLOS` está en `instrucciones_coordinador(demo=False)` y en
      `instrucciones_coordinador(demo=True)`;
    - nombra «reintentable», «una vez» y que la cobertura la calcula el sistema;
    - las reglas que el #7 quita en el modo de demostración siguen sin aparecer en él;
  - implementación en `src/due_diligence/coordinador.py`.
- [ ] T025 [US1] Fase 6 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest`
  en verde. Los tests del #7 (`test_hooks.py`, `test_casos_reglas.py`, `test_hooks_sesiones.py`,
  `test_modo_demo.py`) pasan, y `git diff main -- src/due_diligence/test_hooks.py
  src/due_diligence/test_coordinador.py src/due_diligence/test_eventos_estado.py` muestra que de los
  tests del #6 y del #7 solo cambiaron los cinco de T021, de la forma descrita allí. Commit «cobertura registrada y caso (f)
  (#8)». **PARADA DE REVISIÓN B.**

---

## Fase 7: Sondeo y documentación

- [ ] T026 [P] Experimentos repetibles en `src/due_diligence/sondeo_hooks.py` (R9, Q5), con el mismo
  patrón `Medicion` y `veredicto` del #7 y `PASARELA_RESULTADOS_DIR` en una carpeta temporal:
  - **(e) `updatedInput`**:
    - `e1`: entrada completa con `allow` → la pasarela guarda la cobertura del hook;
    - `e2`: solo `{cobertura}` → no se guarda ningún informe, y se registra el tipo del error de
      `PostToolUseFailure`, que R1 dejó sin medir;
  - **(f) turnos**: un reintento y dos devoluciones del `Stop` → `num_turns == 5` y `success`;
  - **G3**: `HooksDelCaso` real sobre `registrar_informe`, en un estado con noticias
    `no_terminado`. El modelo declara «completa» y la pasarela guarda `caso.cobertura.lineas()`.
  
  Tests de las partes puras en `src/due_diligence/test_sondeo_hooks.py`: las claves nuevas y sus
  valores esperados.
- [ ] T027 [P] `DECISIONES.md`: **entrada 9, «Errores estructurados y cobertura»**, sin recortar las
  anteriores. Recoge:
  - la cobertura calculada en código y sustituida con `updatedInput` (medido: la entrada entera);
  - el escalamiento que nunca se deniega y su texto fijo;
  - 1 reintento por frente pedido por el modelo y guardado por el código;
  - que el «tipo de error» de FR-002 es el campo `causa`, y que `tipo` se conserva por
    compatibilidad con el #6 (T1 del análisis);
  - el presupuesto de turnos calculado;
  - los riesgos residuales de R10.
- [ ] T028 [P] `README.md`: una sección breve, «Fallas de una fuente y cobertura». Explica que el
  coordinador puede reintentar una vez un frente con error reintentable, que el informe declara la
  cobertura calculada por el sistema y cómo verlo con `PASARELA_FALLA_NOTICIAS=1`.
- [ ] T029 Fase 7 completa: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest` en
  verde. Commit «sondeo y documentación del ticket #8».

---

## Fase 8: Validación con el quickstart

- [ ] T030 Revisión de coherencia antes de validar:
  - `Grep` de `cobertura_registrada` en `src/` (0 resultados), de `TEXTO-INTERNO-FICTICIO` (solo en
    tests) y de `{error}` en `src/due_diligence/delegacion.py` (0 resultados);
  - `calcular_cobertura` se define una sola vez y `Caso.completo` no recorre `Situacion` por su
    cuenta.
- [ ] T031 Ejecutar Q1 a Q4 del [quickstart](quickstart.md) y anotar aquí el resultado:
  - número de tests frente a la línea base de T002;
  - el caso (f) simulado y la comprobación de mutación de T022;
  - la política de reintento y el error estructurado, incluido R6;
  - las 625 combinaciones.
  
  Resultado: **____**.
- [ ] T032 [MANUAL] Q5 del quickstart: `uv run python -m due_diligence.sondeo_hooks` (Haiku,
  ≈ 0,02 USD), en una sesión de Claude Code nueva abierta en la raíz. Anotar:
  - si (a) a (d), G2, (e), (f) y G3 coinciden;
  - el tipo de error medido en `e2`.
  
  Si algo `difiere`, aplicar el plan B de R1 (`deny` con motivo) y anotarlo. Resultado: **____**.
- [ ] T033 [MANUAL] Q6 y Q7 del quickstart con el coordinador real (Opus 5.5, ≈ 0,15 a 0,30 USD por
  solicitud): Taller Aurora con `PASARELA_FALLA_NOTICIAS=1` y sin ella. En Q6, anotar los seis
  puntos del quickstart: reintentos, bloque «Cobertura:», evento `cobertura_sustituida`, caso
  completo, turnos (se anota N; si pasa de 15, qué turnos sobraron; solo es fallo `error_max_turns`)
  y si la respuesta al analista dice qué frente faltó (SC-005, valorado por
  la analista sin abrir el código). En Q7, cobertura completa y `habilitar`. Resultado: **____**.
- [ ] T034 Commitear la anotación de T031 a T033 en este archivo. **Ningún commit después de la
  revisión de `/abrir-pr`.** Después, `/abrir-pr`. La descripción del PR incluye la tabla de los
  cinco tests del #6 y del #7 que cambian (T021), con su justificación, y en «Lo pendiente» el riesgo
  residual 6, que hereda el #9 (C1 del análisis).

---

## Dependencias y orden de ejecución

- **Fase 1** (T001, T002) → **Fase 2**:
  - T003 → T004 y T005 → T006, independientes entre sí;
  - T007 → T008;
  - T009 al final. **Parada A.**
- **US2 (fase 3)**: T010 → T011 → T012. Necesita T004 (`Causa`, `estado.errores`) y T006
  (`MAX_REINTENTOS_POR_FRENTE`).
- **US3 (fase 4)**: T013 → T014 → T015. Necesita US2 (causa e `intento`) y T008 (`en_secuencia`).
- **US4 (fase 5)**: T016 → T017 y T018 → T019, con T019 después de T017; T020 al final. Necesita
  US2 (`estado.errores`) y, para los intentos de la cobertura, US3.
- **US1 (fase 6)**: T021 y T022 → T023 → T024 → T025. Necesita US3, US4 y T008. **Parada B.**
- **Fase 7**: T026, T027 y T028 en paralelo, después de la fase 6; T029 al final.
- **Fase 8**: T030 → T031 → T032 y T033 (manuales, pueden ir juntas) → T034.

## Oportunidades de paralelismo

- Fase 2: T003, T005 y T007 tocan archivos distintos.
- Fase 5: T016 (`test_cobertura.py`) y T018 (`test_coordinador.py`, `test_main.py`).
- Fase 7: T026, T027 y T028.
- T010 y T013 tocan `delegacion.py` en el mismo orden, y T021 y T023, `hooks.py`: van en serie.

## Estrategia de implementación

1. **MVP**: fases 1 a 4 (error estructurado y reintento). El coordinador ya recibe errores con
   causa y puede reintentar noticias, pero la cobertura todavía la declara el modelo.
2. La fase 5 añade la cobertura calculada y `Caso.completo` con un solo criterio.
3. La fase 6 cierra I.5: la cobertura registrada es la del código y el caso (f) pasa de extremo a
   extremo. **Sin la fase 6 no se cumple el criterio de aceptación del issue.**
4. **No se ejecuta un caso con el modelo real antes de T024**: hasta entonces el coordinador no tiene
   la instrucción sobre reintentos.
5. Las paradas A y B son puntos de revisión de la analista, no de commit.

## Trazabilidad

| Requisito | Tareas |
|-----------|--------|
| FR-001, FR-002 | T003, T004, T010, T011 |
| FR-003 | T010, T011, T013 |
| FR-004 | T010, T011 |
| FR-005, FR-006 | T013, T014 |
| FR-007 | T005, T006, T013, T014 |
| FR-008 | T013, T014, T024 |
| FR-009 | T003, T004, T013, T014 |
| FR-010 | T016, T017 |
| FR-011 | T007, T008, T021, T022, T023, T026 |
| FR-012 | T016, T018, T019, T022 |
| FR-013 | T022 |
| FR-014 | T018, T019 |
| FR-015 | T003 a T025 (tests sin modelo) |
| FR-016 | T032, T033 |
| FR-017 | reglas para todas las tareas, T010, T021 |
| FR-018 | alcance: ninguna tarea toca el esquema del informe (#9) ni el resumen al oficial (#10) |
| SC-001 | T022, T031 |
| SC-002 | T013, T031 |
| SC-003 | T016, T022, T031 |
| SC-004 | T010, T031 |
| SC-005 | T033 |
| SC-006 | T009, T012, T015, T020, T025, T029, T031 |
