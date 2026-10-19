# Feature Specification: Documentación de entrega: README y DECISIONES.md

**Feature Branch**: `014-documentacion-entrega`

**Created**: 2026-10-19

**Status**: Draft

**Input**: Issue #14 de GitHub: "Documentación de entrega: README y DECISIONES.md". Dejar el repositorio listo para los evaluadores: instrucciones para correr el sistema y las pruebas en menos de 5 minutos, la justificación de cada decisión del ecosistema en dos páginas como máximo, la lista de verificación de entrega y los guiones de los dos videos. El alcance es **todo el issue**, con sus tres criterios de aceptación, más lo que la analista fijó al arrancar: una medida comprobable de las dos páginas, el traslado sin pérdida del contenido actual de `DECISIONES.md` a un documento de detalle, `docs/` como referencia para los revisores, un «Inicio rápido» al principio del README y `docs/entrega.md` con el empaquetado, la revisión de credenciales y los guiones.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Una persona nueva corre el sistema y las pruebas solo con el README (Priority: P1)

Un evaluador, o una persona nueva del equipo, clona el repositorio y, siguiendo solo el «Inicio rápido» que aparece al principio del README, prepara el entorno, configura su clave, comprueba que la aplicación pasa sus pruebas y abre el chat, todo en menos de 5 minutos. Después encuentra en el mismo README de dónde sale cada credencial, los mensajes para reproducir los siete casos, el enlace al GitHub Project y el del video de funcionamiento.

**Why this priority**: es el primer criterio de aceptación del issue y un requisito explícito del enunciado («instrucciones para correr el sistema y los tests en menos de 5 minutos»). Si el evaluador no consigue correr el sistema, el resto de la entrega no se puede comprobar.

**Independent Test**: en un clon limpio, sin entorno virtual ni `.env`, una persona sigue solo el «Inicio rápido» con un cronómetro y llega al chat abierto con las pruebas de la aplicación en verde en menos de 5 minutos (sin contar la instalación de `uv` ni la obtención de la clave).

**Acceptance Scenarios**:

1. **Given** un clon recién hecho y `uv` instalado, **When** la persona abre el README, **Then** lo primero tras la presentación es un «Inicio rápido» con, en este orden: instalar Python 3.12 con `uv`, instalar las dependencias, crear el archivo de entorno con la clave de Anthropic, correr las pruebas de la aplicación (unos 25 s) y arrancar el chat.
2. **Given** el «Inicio rápido», **When** se siguen sus pasos, **Then** cada uno dice qué debe verse al terminar, y ningún paso exige leer otra sección.
3. **Given** el README, **When** se busca cómo correr todas las pruebas, **Then** la sección «Pruebas» dice que la suite completa tarda de 4:43 a 6:12 en Windows (D3 del #12), por qué, y que no es el paso de verificación principal; y que las pruebas de punta a punta consumen API, con su coste aproximado por ejecución completa y por caso.
4. **Given** el README, **When** se busca de dónde sale cada credencial, **Then** dice que la aplicación lee `ANTHROPIC_API_KEY` del archivo `.env` (que git ignora) y que el MCP de GitHub de Claude Code lee `GITHUB_PAT` del entorno del sistema porque `.mcp.json` no lee `.env`, con los permisos `repo` y `project`.
5. **Given** el README, **When** se buscan los siete casos, **Then** están los mensajes exactos de (a)–(g), con el modo de arranque de cada uno y lo que debe verse.
6. **Given** el README, **When** se buscan los enlaces de la entrega, **Then** están el del GitHub Project y el del video de funcionamiento, este último marcado «pendiente» hasta que la analista lo complete.
7. **Given** otro equipo que quiere las piezas reutilizables, **When** lee el README, **Then** encuentra la línea para añadir el marketplace (`claude plugin marketplace add …` o `extraKnownMarketplaces` en su configuración compartida) y la advertencia «el repositorio es privado y pide acceso», que depende de la visibilidad final.
8. **Given** el resto del README actual, **When** se compara antes y después, **Then** sigue debajo del «Inicio rápido» como referencia, sin reescribirse; solo se ajusta lo que el «Inicio rápido» o la sección «Pruebas» obligan a cambiar.

---

### User Story 2 - DECISIONES.md cubre las once necesidades en dos páginas (Priority: P1)

El evaluador abre `DECISIONES.md` y, en dos páginas como máximo, encuentra para cada una de las once necesidades del ecosistema el mecanismo elegido, por qué, la alternativa descartada y dónde está (ticket o tickets y archivo principal); las decisiones clave del sistema con el Agent SDK; las excepciones de arranque; el flujo de ramas; cómo se mueve el Project, con su corrección; y una lista corta de límites conocidos. Cada tema enlaza a su entrada completa en el documento de detalle.

**Why this priority**: es el segundo criterio de aceptación del issue y un entregable del .zip («DECISIONES.md de máximo dos páginas»). La defensa en video se apoya en este documento.

**Independent Test**: un test automático mide `DECISIONES.md` y falla si supera 100 líneas impresas a 90 columnas, si falta alguna de las once necesidades en la tabla o si algún enlace al detalle no apunta a una sección existente.

**Acceptance Scenarios**:

1. **Given** `DECISIONES.md`, **When** se mide partiendo cada línea en líneas de 90 columnas como máximo, cortando por palabras, y contando una línea vacía como una, **Then** el total es 100 o menos (hoy son unas 684).
2. **Given** `DECISIONES.md`, **When** se lee la tabla de necesidades, **Then** tiene una fila por cada necesidad del 1 al 11 del enunciado, con las columnas mecanismo, por qué, alternativa descartada y «Dónde» (ticket o tickets y archivo principal), de modo que todos los tickets del backlog quedan trazados al menos una vez.
3. **Given** `DECISIONES.md`, **When** se busca el sistema con el Agent SDK, **Then** hay una sección de 6 a 8 líneas con las decisiones clave: coordinador y subagentes con herramientas restringidas, hooks del SDK para las reglas de negocio, diseño del servidor MCP, fallas y cobertura parcial, e interfaz de chat.
4. **Given** `DECISIONES.md`, **When** se buscan los temas transversales, **Then** hay, en pocas líneas cada uno: las excepciones de arranque del #1 (ciclo manual de tickets antes del #2 y de la revisión del #4); una rama por ticket con merge commit; los workflows nativos del Project con la corrección (los PR no están en el Project y «Pull request merged» no mueve nada, aunque FR-015 del #2 y la entrada 3 del detalle digan lo contrario: el paso a Done lo hace «Item closed» al cerrarse el issue por el `Closes #N`); y una lista corta de límites conocidos.
5. **Given** cada necesidad y cada tema de `DECISIONES.md`, **When** se sigue su enlace, **Then** lleva a la entrada correspondiente de `docs/decisiones-detalle.md`.

---

### User Story 3 - El detalle completo se conserva sin pérdida (Priority: P1)

Quien quiere el razonamiento completo de una decisión (las desviaciones, las mediciones, los riesgos residuales) lo encuentra en `docs/decisiones-detalle.md`, que conserva todo lo que hoy dice `DECISIONES.md` y añade lo que hoy está disperso en planes y PR.

**Why this priority**: reducir `DECISIONES.md` a dos páginas no puede borrar lo decidido: el detalle es la evidencia de la defensa y de la trazabilidad (principio IX).

**Independent Test**: cada línea no vacía del `DECISIONES.md` de `main` en el commit de partida aparece tal cual en `docs/decisiones-detalle.md`, y cada uno de los añadidos obligatorios aparece en el detalle o enlazado desde él.

**Acceptance Scenarios**:

1. **Given** el `DECISIONES.md` de partida (entradas 1 a 14), **When** se compara con `docs/decisiones-detalle.md`, **Then** todas sus líneas están en el detalle, en el mismo orden; lo nuevo se añade sin borrar ni reescribir lo anterior, y las correcciones van como notas junto a la línea que corrigen.
2. **Given** el detalle, **When** se buscan los añadidos, **Then** están, en el detalle o enlazados desde él (no copiados en `DECISIONES.md`):
   - las desviaciones D1–D4 del #10, D1–D2 del #11 y D1–D3 del #12;
   - la recarga en caliente de `settings.json` y su consecuencia al mover una guarda;
   - los dos límites del PR #29 (`contexto_revision.py:160`: con constitución pero sin `specs/`, el ticket sale «no aplica» sin `CONTEXTO INCOMPLETO`; `revisor-codigo.md:67` del plugin: es ambiguo qué Markdown cuenta para la cobertura);
   - las sugerencias no atendidas de cada PR, con el enlace al PR;
   - la mejora futura de latencia con Opus 5.5 (T055 del #7: de 23 a 56 s y de 0,07 a 0,16 USD por caso);
   - que la espera de la categoría se descarta con **cualquier** frente caído, porque entonces se exige el informe (regla 5, caso f);
   - la corrección de los workflows del Project en la entrada 3.
3. **Given** `DECISIONES.md`, **When** se buscan esos añadidos, **Then** no se copian: como mucho, un límite conocido los nombra y enlaza.

---

### User Story 4 - Los revisores tratan `docs/` como referencia (Priority: P1)

Al abrir el PR de este ticket, y de cualquier otro que toque `docs/`, la revisión independiente y la auditoría de cumplimiento no exigen leer entero un documento de `docs/` para dar la cobertura por completa: `docs/` es referencia, como `README.md` y `DECISIONES.md`.

**Why this priority**: sin el cambio, `docs/decisiones-detalle.md` (unas 700 líneas) contaría para la cobertura, porque «cualquier otro archivo de la lista que no sea referencia también cuenta», y la puerta del PR podría bloquear por una cobertura incompleta sobre documentación.

**Independent Test**: el test de las instrucciones de cobertura (`REFERENCIA` de `.claude/hooks/test_agentes_skills.py`) incluye `docs/` y pasa con los cuatro textos de la puerta.

**Acceptance Scenarios**:

1. **Given** los dos subagentes revisores y sus dos skills del repositorio, **When** se lee la viñeta «Son referencia y no cuentan», **Then** incluye `docs/`, igual en los cuatro.
2. **Given** el test de las instrucciones de cobertura, **When** se ejecuta, **Then** comprueba `docs/` entre la referencia de los cuatro textos y que no está entre lo que cuenta.
3. **Given** la copia del plugin, **When** se comprueba si necesita lo mismo, **Then** el plan deja constancia del resultado; si necesita un cambio, se hace sin términos del proyecto (el test de términos del #13 sigue en verde).

---

### User Story 5 - La entrega se empaqueta y verifica con una lista concreta (Priority: P2)

La analista, antes de subir el .zip a Code Defense y de publicar el video, sigue `docs/entrega.md`: comprueba los accesos, genera el .zip desde un clon limpio con un comando dado, revisa el historial completo en busca de credenciales sin ver ningún valor, comprueba el tamaño y prueba el enlace del video en una ventana privada. El mismo documento tiene los guiones breves de los dos videos.

**Why this priority**: es el tercer criterio de aceptación del issue. Una credencial o un `.env` dentro del .zip es una falta grave del enunciado. Es P2 porque se ejecuta al final, cuando el resto está listo.

**Independent Test**: se ejecutan los comandos de `docs/entrega.md` en esta rama: el .zip sale de un clon limpio, contiene `.git`, `specs/` y `.specify/memory/`, no contiene ninguno de los archivos excluidos, pesa 50 MB o menos, y la revisión del historial termina sin mostrar ningún valor.

**Acceptance Scenarios**:

1. **Given** `docs/entrega.md`, **When** se lee la lista de verificación, **Then** tiene todos los puntos del issue: acceso de los evaluadores al repositorio y al Project; .zip desde un clon limpio; .zip con `.git`, `specs/` y `.specify/memory/`; historial completo revisado en busca de credenciales; 50 MB como máximo; historial no reescrito; video que se abre sin iniciar sesión, probado en una ventana privada.
2. **Given** el comando del .zip, **When** se ejecuta, **Then** parte de un `git clone` limpio, incluye `.git`, `specs/` y `.specify/memory/` y no incluye `.venv`, `.env`, `CLAUDE.local.md`, `.claude/settings.local.json` ni ningún otro archivo ignorado o no versionado (por ejemplo, la bitácora personal excluida en `.git/info/exclude`).
3. **Given** el comando de revisión del historial, **When** se ejecuta sobre todos los commits de todas las ramas, **Then** busca al menos los prefijos `sk-ant-`, `ghp_` y `github_pat_` y, si se puede, los datos con forma real del detector del proyecto; cada hallazgo muestra solo el commit y el archivo (y, como mucho, el tipo), **nunca el valor**.
4. **Given** el .zip generado, **When** se comprueba su tamaño, **Then** el documento dice cómo medirlo y qué hacer si supera 50 MB.
5. **Given** los guiones, **When** se leen, **Then** el de funcionamiento cabe en 5 minutos con los siete casos en el chat y sin explicar código, y el de defensa cabe en 15 minutos con tres bloques: el ecosistema de Claude Code, Spec Kit con un ticket recorrido de la spec al código, y el sistema con el Agent SDK.

---

### Edge Cases

- **El README dice «pendiente» en el video**: es lo esperado hasta que la analista lo complete; la lista de entrega lo tiene como punto obligatorio antes de subir el .zip, y `/abrir-pr` no se ejecuta hasta tener el enlace.
- **La visibilidad final del repositorio**: si el repositorio pasa a público, la frase «el repositorio es privado y pide acceso» deja de ser cierta; la lista de entrega pide revisarla.
- **Un evaluador sin clave de Anthropic**: el «Inicio rápido» lo dice: las pruebas de la aplicación pasan sin clave; el chat y los e2e no arrancan sin ella, y los e2e salen «skipped», que no es «passed».
- **Un evaluador en macOS o Linux**: los comandos del «Inicio rápido» tienen su variante de bash cuando difieren de PowerShell (copiar el archivo de entorno).
- **Un enlace interno roto**: los enlaces de `DECISIONES.md` al detalle los comprueba el test; si se renombra un encabezado del detalle, el test falla.
- **El detector del proyecto marca datos ficticios del historial** (falsos positivos): el documento explica cómo distinguirlos sin mostrar el valor, y que la decisión de entregar es de la analista.
- **El historial contiene una credencial real**: no se reescribe el historial (lo prohíbe el enunciado); el documento dice que se revoca la credencial y se informa, en lugar de entregar a ciegas.
- **El crecimiento futuro de `DECISIONES.md`**: el test del límite impide que una entrada nueva lo vuelva a pasar de dos páginas; lo largo va al detalle.

## Requirements *(mandatory)*

### Functional Requirements

**README (US1)**

- **FR-001**: El README DEBE empezar, tras la presentación y los enlaces, con una sección «Inicio rápido» con estos pasos en orden: `uv python install 3.12`, `uv sync`, crear `.env` a partir de `.env.example` con `ANTHROPIC_API_KEY`, `uv run pytest src` (unos 25 s) y arrancar el chat. Cada paso DEBE decir qué se ve al terminar.
- **FR-002**: El «Inicio rápido» DEBE completarse en menos de 5 minutos en un clon limpio, sin contar la instalación de `uv` ni la obtención de la clave, y DEBE decir sus requisitos previos (`git`, `uv`, una clave de Anthropic).
- **FR-003**: La sección «Pruebas» DEBE dar el tiempo de la suite completa (de 4:43 a 6:12 en Windows, D3 del #12) y su causa, y DEBE decir que no es el paso de verificación principal. DEBE avisar que las pruebas de punta a punta consumen API, con su coste aproximado por ejecución completa y por caso.
- **FR-004**: El README DEBE decir el origen de cada credencial: `ANTHROPIC_API_KEY` en `.env` (ignorado por git) para la aplicación; `GITHUB_PAT` en el entorno del sistema para el MCP de GitHub de Claude Code, porque `.mcp.json` no lee `.env`, con los permisos `repo` y `project`.
- **FR-005**: El README DEBE contener los mensajes exactos de los siete casos (a)–(g), el enlace al GitHub Project, el enlace al video de funcionamiento, la línea para que otro equipo añada el marketplace (`claude plugin marketplace add …` o `extraKnownMarketplaces`) y la frase «el repositorio y el GitHub Project son públicos».
  - **Cambio (2026-10-19)**: el requisito pedía el video «marcado «pendiente» hasta que la analista lo complete» y la frase «el repositorio es privado y pide acceso». El repositorio y el Project pasaron a públicos y el video quedó enlazado (`43486c8`), así que FR-005 pide la visibilidad real, que es lo que comprueba `test_documentacion.py`.
- **FR-006**: El README DEBE usar lenguaje técnico sin jerga sin explicar: cada término propio (por ejemplo, e2e, guarda, hook, MCP) se explica la primera vez que aparece en el «Inicio rápido» y en «Pruebas».
- **FR-007**: El resto del README actual DEBE quedar debajo del «Inicio rápido» como referencia, sin reescribirse. Solo se cambia lo que contradiga el «Inicio rápido» o la sección «Pruebas» (por ejemplo, «Verificar el entorno» con `uv run pytest` como paso principal).

**DECISIONES.md (US2)**

- **FR-008**: `DECISIONES.md` DEBE medir 100 líneas o menos impresas a 90 columnas: cada línea del archivo se parte en líneas de 90 columnas como máximo, cortando por palabras, y una línea vacía cuenta como una. Un test automático DEBE verificarlo.
- **FR-009**: `DECISIONES.md` DEBE tener una tabla con una fila por cada necesidad del 1 al 11 del enunciado y las columnas: necesidad, mecanismo, por qué, alternativa descartada y «Dónde» (ticket o tickets y archivo principal). Entre todas las filas y las secciones de `DECISIONES.md`, cada ticket del backlog (#1 al #13 y #19) DEBE aparecer al menos una vez. Un test DEBE comprobar las once filas.
- **FR-010**: `DECISIONES.md` DEBE tener una sección de 6 a 8 líneas con las decisiones clave del sistema con el Agent SDK: coordinador y subagentes con herramientas restringidas, hooks del SDK para las reglas de negocio, diseño del servidor MCP, fallas y cobertura parcial, e interfaz de chat.
- **FR-011**: `DECISIONES.md` DEBE tener, en pocas líneas cada uno: las excepciones de arranque del #1; una rama por ticket con merge commit; los workflows nativos del Project con la corrección de FR-015 del #2 y de la entrada 3; y una lista corta de límites conocidos.
- **FR-012**: Cada necesidad y cada tema de `DECISIONES.md` DEBE enlazar a su entrada en `docs/decisiones-detalle.md`. Un test DEBE comprobar que cada enlace al detalle apunta a un encabezado existente.

**Detalle (US3)**

- **FR-013**: `docs/decisiones-detalle.md` DEBE contener, sin pérdida y en el mismo orden, todas las líneas del `DECISIONES.md` de partida (`main` en `f9e82d6`). Lo nuevo se añade; las correcciones van como notas junto a la línea que corrigen, sin borrarla.
- **FR-014**: El detalle DEBE contener, o enlazar, los añadidos de US3-2: D1–D4 del #10, D1–D2 del #11, D1–D3 del #12, la recarga en caliente de `settings.json`, los dos límites del PR #29, las sugerencias no atendidas de cada PR con su enlace, la mejora futura de latencia con Opus 5.5 (T055 del #7) y la espera de la categoría descartada con cualquier frente caído. Ninguno se copia en `DECISIONES.md`.

**Revisores (US4)**

- **FR-015**: `docs/` DEBE figurar en la viñeta «Son referencia y no cuentan» de `.claude/agents/revisor-codigo.md`, `.claude/agents/auditor-cumplimiento.md`, `.claude/skills/revisar-codigo/SKILL.md` y `.claude/skills/auditar-cumplimiento/SKILL.md`, y en `REFERENCIA` de `.claude/hooks/test_agentes_skills.py`.
- **FR-016**: El plan DEBE comprobar si la copia del plugin necesita el mismo cambio. Si lo necesita, se hace sin términos del proyecto; si no, se deja constancia del motivo.

**Entrega (US5)**

- **FR-017**: `docs/entrega.md` DEBE tener la lista de verificación completa del issue (US5-1).
- **FR-018**: `docs/entrega.md` DEBE dar el comando que genera el .zip desde un clon limpio, con `.git`, `specs/` y `.specify/memory/`, y sin `.venv`, `.env`, `CLAUDE.local.md`, `.claude/settings.local.json` ni ningún otro archivo ignorado o no versionado; y el modo de comprobar después lo que contiene y lo que pesa (50 MB como máximo).
- **FR-019**: `docs/entrega.md` DEBE dar un comando concreto que revise el historial completo (todos los commits de todas las ramas) en busca de credenciales, con al menos los prefijos `sk-ant-`, `ghp_` y `github_pat_` y, si se puede, el detector de datos con forma real del proyecto. Cada hallazgo DEBE mostrar solo el commit y el archivo (y, como mucho, el tipo), nunca el valor. DEBE decir qué hacer con un hallazgo sin reescribir el historial.
- **FR-020**: `docs/entrega.md` DEBE pedir comprobar el acceso de los evaluadores al repositorio y al Project, que el historial no se reescribió, la frase de visibilidad del README y que el video se abre sin iniciar sesión, probado en una ventana privada.
- **FR-021**: `docs/entrega.md` DEBE tener los guiones breves de los dos videos: funcionamiento (5 minutos como máximo, los siete casos en el chat, sin explicar código) y defensa (15 minutos como máximo: el ecosistema de Claude Code, Spec Kit con un ticket recorrido de la spec al código, y el sistema con el Agent SDK), con un tiempo orientativo por bloque.

**Restricciones**

- **FR-022**: El ticket NO DEBE cambiar `src/` ni las guardas de `.claude/hooks/` (salvo el test de FR-015); los tests nuevos de la documentación van junto a lo que prueban según la convención del repositorio.
- **FR-023**: Ningún documento ni comando DEBE leer, mostrar ni modificar `.env`; ningún documento DEBE contener un dato con forma real ni un valor de credencial.

### Key Entities

- **DECISIONES.md**: resumen de dos páginas; tabla de las once necesidades, sección del sistema con el Agent SDK, temas transversales y límites conocidos, con enlaces al detalle.
- **docs/decisiones-detalle.md**: el contenido completo de partida más los añadidos; el destino de cada enlace de `DECISIONES.md`.
- **docs/entrega.md**: lista de verificación, comandos del .zip, del tamaño y de la revisión de credenciales, y los guiones de los videos.
- **README.md**: «Inicio rápido» al principio, «Pruebas» con tiempos y costes, credenciales, casos, enlaces y el resto como referencia.
- **Instrucciones de cobertura**: los cuatro textos de la puerta del PR y su test, con `docs/` como referencia.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona que no conoce el proyecto completa el «Inicio rápido» en un clon limpio en menos de 5 minutos, con las pruebas de la aplicación en verde y el chat abierto (validación de la analista, cronometrada).
- **SC-002**: `DECISIONES.md` mide 100 líneas o menos impresas a 90 columnas, y el test lo comprueba en cada ejecución de la suite.
- **SC-003**: El 100 % de las once necesidades tiene fila con mecanismo, por qué, alternativa descartada y «Dónde», y el 100 % de los tickets del backlog aparece al menos una vez en `DECISIONES.md`.
- **SC-004**: El 100 % de las líneas no vacías del `DECISIONES.md` de partida aparece en `docs/decisiones-detalle.md`, y el 100 % de los enlaces de `DECISIONES.md` al detalle llega a un encabezado existente.
- **SC-005**: Los cuatro textos de la puerta del PR listan `docs/` como referencia, y los tests de `.claude/hooks/` y `plugins/` siguen en verde.
- **SC-006**: El .zip generado con el comando de `docs/entrega.md` pesa 50 MB o menos, contiene `.git`, `specs/` y `.specify/memory/`, y 0 archivos excluidos o no versionados.
- **SC-007**: La revisión del historial con el comando de `docs/entrega.md` muestra 0 valores de credencial en su salida, encuentre o no algo.
- **SC-008**: Los dos guiones caben en su tiempo máximo (5 y 15 minutos) según la suma de sus tiempos orientativos.

## Assumptions

- El commit de partida de `DECISIONES.md` es `f9e82d6` (`main` al crear la rama); los tickets posteriores añaden al detalle, no al resumen.
- «Dos páginas» se mide en el texto fuente, no en una vista renderizada: 100 líneas a 90 columnas es el equivalente acordado por la analista. Una fila de tabla larga cuenta todas las líneas en que se parte.
- El tiempo de 5 minutos no incluye instalar `uv` ni conseguir la clave de Anthropic; sí incluye la descarga de Python 3.12 y de las dependencias con una conexión normal.
- Los costes y tiempos que se citan son los ya medidos en los tickets #6, #7, #11 y #12; este ticket no vuelve a medir con el modelo real.
- La bitácora personal (`docs/bitacora-decisiones.md`) no se versiona y queda fuera del .zip por el clon limpio; no es fuente de este ticket.
- El enlace del video y la visibilidad final del repositorio los decide y completa la analista; `/abrir-pr` no se ejecuta hasta tener el enlace.
- **Fuera de alcance**: cambios en `src/` y en las guardas; grabar los videos; reescribir el historial; corregir FR-015 en la spec del #2 (es historia del ticket: la corrección se documenta en `DECISIONES.md` y en el detalle); atender las sugerencias pendientes de los PR (solo se enlazan).
