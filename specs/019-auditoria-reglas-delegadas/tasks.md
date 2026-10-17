---

description: "Lista de tareas del ticket #19, auditoría: reglas delegadas a otro ticket y uv.lock como referencia"
---

# Tasks: Auditoría: reglas delegadas a otro ticket y uv.lock como referencia

**Input**: documentos de diseño en `specs/019-auditoria-reglas-delegadas/`: [plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/) y [quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/
y quickstart.md.

**Tests**: obligatorios (FR-010, FR-013 y constitución X). Van en
`.claude/hooks/test_agentes_skills.py`, junto al código que ya prueba los agentes y las skills,
y se escriben antes que el texto que prueban (deben fallar primero), salvo la función auxiliar
y el test de coherencia, que protegen una propiedad que ya se cumple.

**Organization**: una fase por historia de la spec, con una fase previa para la función
auxiliar que comparten:

1. Setup: fase 1. Fundamentos (`seccion`): fase 2.
2. US1 regla delegada (P1): fase 3. US2 `uv.lock` como referencia (P1): fase 4.
3. US3 los cuatro archivos dicen lo mismo (P2): fase 5.
4. Documentación y calidad: fases 6 y 7. Validación manual: fase 8.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La
verificación del cierre de #19 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US3).
- **[MANUAL]**: la hace la analista en una sesión nueva de Claude Code abierta en la raíz de un
  clon desechable. Claude se detiene y espera su confirmación.
- **PARADA A**: punto de revisión de la analista, tras T013. Claude se detiene, entrega el diff
  de los cuatro archivos de la puerta y no sigue hasta que la analista lo indique.
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md), Q# del
  [quickstart](quickstart.md) o un contrato de [contracts/](contracts/).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Ningún valor con forma real** (tarjeta, NIT, cédula o credencial) se escribe en tareas,
  tests, código ni documentación. Los datos de las pruebas manuales son ficticios (categorías,
  comercios y funciones de ejemplo inventados, `CO-TV-0001`).
- **Commits** por partes lógicas en la rama `019-auditoria-reglas-delegadas`, nunca en `main`, y
  sin `git commit --amend`: cada corrección va en un commit nuevo. Un commit nuevo invalida el
  veredicto del anterior, así que el veredicto se registra en `/abrir-pr`, después del último
  commit. **Ningún commit va después de la revisión**: si `/abrir-pr` falla o reporta
  bloqueantes, se corrige con un commit nuevo y se revisa otra vez.
- **No se tocan** `.claude/hooks/veredicto.py`, `.claude/hooks/guarda_pr.py` ni
  `.claude/hooks/preparar_revision.py`, ni sus tests (FR-009, SC-005).
- **Los tests existentes no se editan**, salvo ampliar la lista `REFERENCIA` si hace falta
  (FR-010, R5). El texto nuevo conserva las frases que ya fijan.
- **Formato**: el hook de #3 formatea cada `.py` escrito o editado. Aun así, cada fase de
  código termina con `uv run ruff format .claude/hooks` y `uv run ruff check .claude/hooks`.
- **Tests**: `uv run pytest .claude/hooks/test_agentes_skills.py` para el ciclo corto y
  `uv run pytest` completo en la fase 7.
- **El texto exacto** de las dos secciones es el de
  [contracts/texto-de-la-puerta.md](contracts/texto-de-la-puerta.md); no se redacta de nuevo.
- **No se toca la rama 005 ni su veredicto con bloqueantes.** Todo lo que necesite esa rama se
  hace en un clon desechable fuera del repositorio (R7).

---

## Phase 1: Setup

- [X] T001 Commitear este `tasks.md`: `docs(specs): tareas del ticket #19`. Con spec y plan ya
  commiteados, deja a la rama con los tres documentos antes de tocar código protegido.
- [X] T002 Estado de partida: con `Grep` sobre `.claude/agents` y `.claude/skills`, comprobar que
  `uv.lock` aparece **exactamente cuatro veces** (una por archivo de la puerta, R3); ejecutar
  `uv run pytest .claude/hooks/test_agentes_skills.py` (debe estar en verde) y
  `git status --porcelain` (vacío). Anotar el número de tests que pasan: es la línea base.
  **Resultado de T002** (2026-10-17, rama `019-auditoria-reglas-delegadas`, commit `42ac154`): `uv.lock` aparece 4 veces (`revisor-codigo.md:65`, `auditor-cumplimiento.md:89`, `revisar-codigo/SKILL.md:30` y `auditar-cumplimiento/SKILL.md:31`); `test_agentes_skills.py`: **67 passed**; `git status` limpio.

---

## Phase 2: Foundational (bloquea las historias)

**Propósito**: la función que extrae una sección y la compara, que usan las tres historias.

- [X] T003 Añadir a `.claude/hooks/test_agentes_skills.py`, al final y bajo un encabezado
  «Coherencia entre los archivos de la puerta (FR-013, R4)», la función
  `seccion(cuerpo: str, encabezado: str) -> str` y sus pruebas, según
  [contracts/test-coherencia.md](contracts/test-coherencia.md), apartado «Función»:
  - devuelve el texto desde la línea `## <encabezado>` hasta el siguiente `## ` o el final;
  - normaliza espacios, tabuladores y saltos de línea (un solo espacio, sin extremos);
  - si el encabezado no existe, falla con un mensaje que nombra el archivo;
  - **prueba de la función**: con textos sintéticos, dos secciones que difieren en una palabra
    **no** son iguales y dos que difieren solo en espacios o saltos de línea **sí**.
  Estas pruebas pasan desde el principio (no hay estado rojo: la función es nueva). Reutiliza
  `cargar_agente`, `cargar_skill` y `instrucciones_de_cobertura()`. Origen: FR-013, SC-004, R4.

---

## Phase 3: User Story 1 - Una regla delegada a otro ticket no bloquea este ticket (P1)

**Goal**: una regla que la spec delega con número de ticket sale `no aplica` con la razón; una
regla delegada que el diff contradice sigue bloqueando; borrar o debilitar código o tests de
cualquier regla hace que aplique; citarla sin número sigue aplicando.

**Independent Test**: los tests de T004 pasan con el texto nuevo; en el clon de la rama 005 la
auditoría da I.1 a I.3 `no aplica` (Q3, fase 8).

### Tests de US1 (deben fallar antes de T005 y T006)

- [X] T004 [US1] En `.claude/hooks/test_agentes_skills.py`, sección «Cuándo aplica una regla
  (FR-001 a FR-005, FR-011, FR-012; R1, R2)», con la función `seccion` de T003:
  - el agente `auditor-cumplimiento` y la skill `auditar-cumplimiento` tienen cada uno la
    sección `Cuándo aplica una regla`;
  - la sección contiene, en los dos: «con su número», «no es delegarla», «delegada al ticket
    #N en la spec», «Delegar exime de implementar la regla, no de violarla», «no de
    conservar», «borra o debilita» y «bloqueante»;
  - en la skill, el paso 3 de «Qué hacer» remite a la sección («Cuándo aplica una regla») y la
    frase «el diff toca código o tests que la implementan o la prueban» aparece **una sola
    vez** en el cuerpo (ya no hay un resumen aparte de la regla);
  - en la skill, `CONSTITUCION` sigue apareciendo antes que `spec.md` (la sección nueva no
    menciona `spec.md`).
  Origen: FR-001 a FR-005, FR-011, FR-012, R1, R2, contrato «Bloque 2». Deben fallar con el
  texto actual: ejecutar y anotar los fallos.
  **Resultado de T004**: con el texto anterior fallaron 4 pruebas (`test_la_regla_de_aplicabilidad_dice_lo_que_exige_la_spec` en el agente y en la skill, `test_la_skill_remite_a_la_seccion_y_no_resume_la_regla_aparte` y `test_la_seccion_de_aplicabilidad_de_la_skill_no_menciona_spec_md`); `seccion` y sus 6 pruebas (T003) pasaron desde el principio.

### Implementación de US1

- [X] T005 [P] [US1] En `.claude/agents/auditor-cumplimiento.md`, sustituir la sección
  `## Cuándo aplica una regla` actual (y el párrafo «Los tests cuentan…», que pasa al punto 4)
  por el texto exacto del «Bloque 2» de
  [contracts/texto-de-la-puerta.md](contracts/texto-de-la-puerta.md). Conserva las frases que
  fijan los tests existentes: «la spec del ticket la cita», «el diff toca código o tests que la
  implementan o la prueban», «sin código de producción ni tests de las reglas» y «borra o
  debilita» (R5). No cambia el frontmatter ni las demás secciones.
- [X] T006 [P] [US1] En `.claude/skills/auditar-cumplimiento/SKILL.md`: añadir la sección
  `## Cuándo aplica una regla` con el texto exacto del «Bloque 2» (entre «Plan de lectura» y
  «Qué hacer») y sustituir el paso 3 de «Qué hacer» por el texto del apartado «Paso 3 de la
  skill de auditoría (reemplazo)» del contrato. La sección **no menciona `spec.md`**. No
  cambia el frontmatter, el comando inyectado ni `allowed-tools`.
- [X] T007 [US1] Ejecutar `uv run pytest .claude/hooks/test_agentes_skills.py`: los tests de T004
  pasan y los existentes (línea base de T002) siguen en verde sin editarlos;
  `uv run ruff format .claude/hooks` y `uv run ruff check .claude/hooks` limpios. Commit:
  `fix(auditoria): una regla delegada con número de ticket es no aplica`.
  **Resultado de T007**: `test_agentes_skills.py` 77 passed (67 de la línea base + 6 de `seccion` + 4 de US1); `ruff format .claude/hooks` y `ruff check .claude/hooks` limpios. Ajuste de forma: el punto 5 del texto de la sección se parte en otras líneas para que «sin código de producción ni tests de las reglas» quede entera en una línea, porque un test existente la busca sin normalizar; el contrato se alineó.

**Checkpoint**: US1 completa y probada por texto. Q3 y Q4 la comprueban con sesiones reales.

---

## Phase 4: User Story 2 - Un archivo generado no reduce la cobertura (P1)

**Goal**: `uv.lock` pasa a la lista de referencia en el bloque de cobertura de los cuatro
archivos; el resto del bloque no cambia.

**Independent Test**: los tests de T008 pasan; SC-003 se comprueba con el `/abrir-pr` real del
#5 (fuera de este ticket, anotado en T022).

### Tests de US2 (deben fallar antes de T009 a T012)

- [X] T008 [US2] En `.claude/hooks/test_agentes_skills.py`, junto a las pruebas de cobertura
  existentes y con `seccion` de T003, parametrizado en los cuatro textos de
  `instrucciones_de_cobertura()`:
  - en la sección `Qué cuenta para la cobertura`, `uv.lock` aparece en la viñeta «Son
    referencia y no cuentan» y **no** en la viñeta «Cuentan»;
  - la sección ya no contiene «se leen por secciones» asociado a archivos generados;
  - se conservan las demás reglas (los tests existentes de cobertura siguen pasando sin
    editarlos): `no cuentan`, `a medias`, `agrupada por directorio`, `No ejecutar tests nunca
    reduce la cobertura` y el plan de lectura.
  Ampliar `REFERENCIA` con `"uv.lock"`: es el único cambio permitido a un test existente (R5), y
  el test que la usa sigue pasando con el texto actual porque `uv.lock` ya aparece en el cuerpo;
  lo que falla antes del cambio es la comprobación de **posición** de la prueba nueva. Origen:
  FR-006, FR-007, R3, R5, contrato «Bloque 1». Deben fallar con el texto actual: ejecutar y
  anotar los fallos.
  **Resultado de T008**: con el texto anterior fallaron 8 pruebas (`test_uv_lock_es_referencia_y_no_cuenta_para_la_cobertura` y `test_ningun_archivo_generado_se_lee_por_secciones_como_archivo_que_cuenta`, cada una en los cuatro textos). `REFERENCIA` ganó `uv.lock`.

### Implementación de US2

- [X] T009 [P] [US2] En `.claude/agents/revisor-codigo.md`, sustituir la sección `## Qué cuenta
  para la cobertura` por el texto exacto del «Bloque 1» de
  [contracts/texto-de-la-puerta.md](contracts/texto-de-la-puerta.md): quita «los generados
  (`uv.lock`) se leen por secciones» de **Cuentan** y añade «y los archivos generados por
  herramientas (`uv.lock`)» a **Son referencia y no cuentan**. Nada más.
- [X] T010 [P] [US2] El mismo cambio en `.claude/skills/revisar-codigo/SKILL.md`.
- [X] T011 [US2] El mismo cambio en `.claude/agents/auditor-cumplimiento.md` (después de T005:
  es el mismo archivo).
- [X] T012 [US2] El mismo cambio en `.claude/skills/auditar-cumplimiento/SKILL.md` (después de
  T006: es el mismo archivo).
- [X] T013 [US2] Ejecutar `uv run pytest .claude/hooks/test_agentes_skills.py`: los tests de
  T008 pasan, los existentes siguen en verde; `uv run ruff format .claude/hooks` y
  `uv run ruff check .claude/hooks` limpios. Commit: `fix(auditoria): uv.lock pasa a archivo de
  referencia en los cuatro archivos de la puerta`. Después, **PARADA A**: entregar a la analista
  `git diff main...HEAD -- .claude/agents .claude/skills` y la salida de los tests, y esperar su
  confirmación antes de seguir.
  **Resultado de T013**: `test_agentes_skills.py` 85 passed (77 + 8 de US2); `ruff format .claude/hooks` y `ruff check .claude/hooks` limpios. El mismo reemplazo se aplicó a los cuatro archivos y cada uno coincidía exactamente una vez.

**Checkpoint**: US1 y US2 completas. Los cuatro archivos de la puerta tienen el texto final.

---

## Phase 5: User Story 3 - Los cuatro archivos de la puerta dicen lo mismo (P2)

**Goal**: un test falla si el bloque de cobertura o la regla de aplicabilidad difieren entre
los archivos (FR-013, SC-004).

**Independent Test**: Q2: cambiar una palabra de una copia hace fallar el test, y restaurarla
lo vuelve a poner en verde.

- [X] T014 [US3] En `.claude/hooks/test_agentes_skills.py`, bajo el encabezado de T003 y según
  [contracts/test-coherencia.md](contracts/test-coherencia.md), apartado «Pruebas»:
  - **bloque de cobertura igual**: `Qué cuenta para la cobertura` existe en los dos agentes y en
    las dos skills y es igual en los cuatro (el mensaje de fallo nombra los archivos que
    difieren);
  - **aplicabilidad igual**: `Cuándo aplica una regla` existe en el agente y en la skill del
    auditor y es igual;
  - **`uv.lock` es referencia**: en el bloque, en «Son referencia y no cuentan» y no en
    «Cuentan» (si T008 ya lo cubre, esta prueba lo comprueba sobre el bloque común);
  - **la delegación exige número**: el bloque de aplicabilidad contiene «con su número» y «no es
    delegarla»; **delegar no exime de conservar**: contiene «no de conservar» y «borra o
    debilita».
  Pasan desde que existen T005, T006 y T009 a T012. Origen: FR-005, FR-008, FR-013, SC-004, R4.
- [X] T015 [US3] **Q2**: en la rama, cambiar **una palabra** del bloque de cobertura de solo una
  de las cuatro copias y ejecutar `uv run pytest .claude/hooks/test_agentes_skills.py`: debe
  fallar nombrando el archivo. Repetir con la sección `Cuándo aplica una regla` del agente del
  auditor. Deshacer cada cambio con `git restore` del archivo y comprobar que vuelve a pasar y
  que `git status --porcelain` queda vacío (sin commit en medio). Anotar el resultado. Commit
  de T014: `test(auditoria): los cuatro archivos de la puerta deben decir lo mismo`.

**Checkpoint**: las tres historias completas.
  **Resultado de T014**: 7 pruebas nuevas (bloque de cobertura igual en los cuatro, aplicabilidad igual en el agente y la skill del auditor, la delegación exige número y delegar no exime de conservar, en ambos textos, y el mensaje que nombra los archivos que difieren); `test_agentes_skills.py` pasa de 85 a **92 passed**. La comprobación de `uv.lock` como referencia ya la cubrían las pruebas de T008, por lo que no se duplicó.
  **Resultado de T015 (Q2)**: (1) cambiar «para contrastar» por «para comparar» solo en `.claude/skills/revisar-codigo/SKILL.md`: **falla** `test_el_bloque_de_cobertura_es_igual_en_los_cuatro_archivos` con el mensaje «difiere entre los archivos de la puerta: agente revisor-codigo + agente auditor-cumplimiento + skill auditar-cumplimiento | skill revisar-codigo» (1 failed, 91 passed); (2) cambiar «prevalece» por «predomina» solo en `.claude/agents/auditor-cumplimiento.md`: **falla** `test_la_regla_de_aplicabilidad_es_igual_en_el_agente_y_en_la_skill_del_auditor` con «difiere entre el agente y la skill del auditor: agente auditor-cumplimiento | skill auditar-cumplimiento» (1 failed, 91 passed). Tras `git restore` de cada archivo vuelve a **92 passed** y `git status` solo muestra el test nuevo, sin commit en medio.

---

## Phase 6: Documentación

- [X] T016 Añadir **una viñeta** a la entrada 5 de `DECISIONES.md` («Revisión independiente y
  puerta de PR»), sin entrada nueva y sin recortar nada por el límite de páginas (R8), con:
  - el criterio de la regla delegada: se delega solo con número de ticket en la spec, prevalece
    sobre el código que solo aporta datos o clasificación, no sobre el que la contradice ni
    sobre el que borra o debilita lo que ya la garantiza, y una regla citada sin número se trata
    como asignada a este ticket;
  - **los dos límites**: (1) el auditor no consulta GitHub, así que no comprueba que el ticket
    nombrado exista ni que cubra la regla; (2) el test garantiza que el texto de los cuatro
    archivos es el mismo, no que el modelo lo interprete bien.
  Commit: `docs: criterio de la regla delegada en la entrada 5 de DECISIONES.md`.

---

## Phase 7: Calidad

- [X] T017 **Q1**: `uv run ruff format .`, `uv run ruff check .` y `uv run pytest` completo, con y
  sin `PYTHONUTF8` y `PYTHONIOENCODING`. Esperado: todo en verde y los tests existentes sin
  editar, salvo lo permitido (FR-010, SC-006). Si algo falla, corregir con un commit nuevo.
- [X] T018 **Q6**: `git diff --stat main...HEAD`: ninguna línea de `veredicto.py`, `guarda_pr.py`,
  `preparar_revision.py` ni de sus tests. Los archivos cambiados son los dos agentes, las dos
  skills, `test_agentes_skills.py`, `DECISIONES.md` y `specs/019-*/`. Anotar el resultado
  (FR-009, SC-005).

  **Resultado de T017 (Q1)**: `uv run ruff format .` (100 archivos sin cambios) y `uv run ruff check .` limpios; `uv run pytest` completo **sin** `PYTHONUTF8` ni `PYTHONIOENCODING`: **1467 passed** en 246 s; **con** `PYTHONUTF8=1` y `PYTHONIOENCODING=utf-8`: **1467 passed** en 243 s. Los tests existentes no se editaron, salvo ampliar `REFERENCIA` con `uv.lock`.
  **Resultado de T018 (Q6)**: `git diff --stat main...HEAD`: 15 archivos, +1487 −33; ninguna línea de `veredicto.py`, `guarda_pr.py`, `preparar_revision.py` ni de sus tests. Cambiados: los dos agentes, las dos skills, `test_agentes_skills.py`, `DECISIONES.md` y `specs/019-*/`.

---

## Phase 8: Validación manual con sesiones reales

**Propósito**: comprobar que el auditor interpreta bien el texto (R6). El comportamiento depende
del modelo: cada escenario se corre **una vez** y se anota lo que salió. Requiere la rama
commiteada hasta T018. Los escenarios y sus reglas están en el [quickstart](quickstart.md).

- [X] T019 Preparar el clon desechable y las ramas de prueba con un script **fuera del
  repositorio** (carpeta de scratchpad, no se versiona; `git clone <repo local> clon-019`, sin
  `git push` nunca):
  - **Q3**: en la rama `005-servidor-mcp-pasarela` del clon, `git merge --no-ff
    origin/019-auditoria-reglas-delegadas`, corregir la línea 161 de
    `specs/005-servidor-mcp-pasarela/spec.md` a «I.1, I.2 e I.3 … del ticket #7» y commitear en
    el clon (si `DECISIONES.md` entra en conflicto, se resuelve en el clon conservando ambos
    cambios);
  - **Q4**: rama `098-delegada-contradice` desde `main` del clon, con
    `specs/098-delegada-contradice/` (spec que delega I.3 «al ticket #7», cita I.1 sin número ni
    ticket, más `plan.md` y `tasks.md`) y un `src/` ficticio que contradice I.3 sin código ni
    test de I.1;
  - **Q5**: en `main` del clon, commitear `src/prueba_098/regla.py` (implementa I.3) y
    `src/prueba_098/test_regla.py`, luego `git update-ref refs/remotes/origin/main main`, y
    crear `098-borra-test` desde ese `main` con `specs/098-borra-test/` (spec que delega I.3
    «al ticket #7») y un commit que borra `test_regla.py`.
  Cada rama `098-*` nace de `main` del clon (una sola carpeta `specs/098-*`). `uv sync` en el
  clon. Datos ficticios. Entregar a la analista la ruta del clon y el comando de cada escenario.
  **Resultado de T019**: clon en `C:\Users\ana.hernandez\AppData\Local\Temp\claude\D--AIReadyOrquestador\326bdc06-818e-4d19-80f7-aac699694e93\scratchpad\clon-019` (script `preparar-clon-019.sh` en el mismo scratchpad, fuera del repositorio; el remoto del clon no admite push). Q3: rama `005-servidor-mcp-pasarela` con `git merge --no-ff` de `origin/019-auditoria-reglas-delegadas` (sin conflictos) y la línea 161 de su spec corregida a «I.1, I.2 e I.3 … del ticket #7». Q4: rama `098-delegada-contradice`. Q5: `main` del clon con `src/prueba_098/` (regla y test), `origin/main` avanzado con `git update-ref`, y rama `098-borra-test` que borra `test_regla.py`. `preparar_revision.py` verificado en las tres ramas: salida 0, sin `CONTEXTO INCOMPLETO`, carpeta del ticket correcta; el diff de la 005 se omite por tamaño (58 archivos) y el de las dos `098` es completo.
- [ ] T020 [MANUAL] **Q3** (SC-001): sesión nueva en la raíz del clon, en la rama 005 del merge:
  `/auditar-cumplimiento specs/005-servidor-mcp-pasarela`. Esperado: I.1, I.2 e I.3 `no aplica`
  con la razón «delegada al ticket #7»; I.4 e I.5 `cumple`; 0 bloqueantes de las tres primeras.
  Claude espera la confirmación de la analista y anota el `RESUMEN` y la tabla.
- [ ] T021 [MANUAL] **Q4** (SC-002, FR-004, FR-011): sesión nueva en la raíz del clon, en
  `098-delegada-contradice`: `/auditar-cumplimiento specs/098-delegada-contradice`. Esperado:
  **I.3 `incumple`** y **I.1 `no verificada`**, las dos bloqueantes, con ubicación y razón;
  `bloqueantes≥2`. Claude espera la confirmación y anota el resultado.
- [ ] T022 [MANUAL] **Q5** (SC-008, FR-012): sesión nueva en la raíz del clon, en `098-borra-test`:
  `/auditar-cumplimiento specs/098-borra-test`. Esperado: I.3 aplica pese a estar delegada y
  sale `no verificada` (o `incumple`), bloqueante; nunca `no aplica`. Claude espera la
  confirmación y anota el resultado.
- [ ] T023 Anotar en esta lista los resultados de Q1 a Q6 (T015, T017, T018, T020 a T022) y,
  como **verificación pendiente de #5**, SC-003: «`uv.lock` no reduce la cobertura» se comprueba
  con el `/abrir-pr` real del #5, cuyo diff trae `uv.lock`; este ticket solo cubre el texto
  (T008, T014). Borrar la carpeta `clon-019` del scratchpad. Commit:
  `docs(specs): resultados de la validación del ticket #19`. Después, `/abrir-pr`. **Ningún
  commit va después de la revisión.**

---

## Dependencias y orden de ejecución

- **Fase 1** no tiene dependencias. T001 va primero.
- **Fase 2** (T003) depende de la fase 1 y bloquea US1, US2 y US3, porque todas usan `seccion`.
- **US1** (T004 a T007) y **US2** (T008 a T013) son independientes entre sí por sus tests, pero
  comparten dos archivos: T011 va después de T005 y T012 después de T006.
- **US3** (T014, T015) depende de que US1 y US2 hayan dejado el texto final: sus pruebas
  comparan los cuatro archivos.
- **Fase 6** (T016) puede ir en cualquier momento tras T013; se deja aquí para que el commit de
  documentación sea propio.
- **Fase 7** depende de todo el código y los textos. **Fase 8** depende de la rama commiteada
  hasta T018 y de la confirmación de la analista en cada tarea [MANUAL].
- Orden resumido:

```text
T001 ─▶ T002 ─▶ T003 ─┬─▶ T004 ─▶ T005 ┐
                      │         T006 ┤─▶ T007
                      └─▶ T008 ─▶ T009 ┐
                                T010 ┤
                                T011 (tras T005) ┤─▶ T013 ─▶ PARADA A ─▶ T014 ─▶ T015
                                T012 (tras T006) ┘                              │
                                                                T016 ◀──────────┘
                                                                  │
                                                  T017 ─▶ T018 ─▶ T019 ─▶ T020 ─▶ T021 ─▶ T022 ─▶ T023 ─▶ /abrir-pr
```

## Parallel Example: User Story 2

```text
# Los dos archivos del revisor de código no los toca ninguna otra tarea:
T009 .claude/agents/revisor-codigo.md
T010 .claude/skills/revisar-codigo/SKILL.md
# T005 y T006 (auditor) también son paralelas entre sí; T011 y T012 esperan a esas dos.
```

## Implementation Strategy

- **MVP**: US1 (T003 a T007). Es lo que desbloquea la auditoría de la rama 005 por las reglas
  I.1 a I.3. Se puede parar ahí y validar Q3.
- **Incremental**: US2 quita el segundo motivo de cobertura incompleta del #5; US3 evita que el
  defecto reaparezca por una copia desactualizada.
- **Criterio de parada A**: tras T013 los cuatro archivos tienen su texto final y la analista
  lo revisa antes de escribir el test de coherencia y validar con sesiones reales.
- **Límite declarado**: el test garantiza el texto, no la interpretación del modelo. Por eso la
  fase 8 existe y se anota lo que salga, sin repetir hasta que salga bien.

## Cobertura de los requisitos

| Requisito | Tareas |
|-----------|--------|
| FR-001 a FR-005, FR-011, FR-012 | T004, T005, T006, T007, T020, T021, T022 |
| FR-006, FR-007, FR-008 | T008 a T013, T014 |
| FR-009 | T018 |
| FR-010 | T002, T007, T013, T017 |
| FR-013 | T003, T014, T015 |
| SC-001 | T020 |
| SC-002 | T021 |
| SC-003 | T008, T014 (texto) y `/abrir-pr` del #5 (T023, pendiente de #5) |
| SC-004 | T003, T014, T015 |
| SC-005 | T018 |
| SC-006 | T017 |
| SC-007 | T020 (el veredicto real del #5 llega con su `/abrir-pr`) |
| SC-008 | T022 |
