# Feature Specification: Guardas de Claude Code: hooks, permisos y reglas por ruta

**Feature Branch**: `003-guardas-claude-code`

**Created**: 2026-10-15

**Status**: Draft

**Input**: Issue #3 de GitHub, "Guardas de Claude Code: hooks, permisos y reglas por ruta"
(https://github.com/anahernandez0814/due-diligence-pasarela-austral/issues/3), más el
comentario del issue con el aprendizaje del ticket #1 sobre las herramientas destructivas
del MCP de GitHub.

**Objetivo**: que las reglas de trabajo del equipo se cumplan de forma garantizada mientras
se desarrolla: sin especificación no se escribe código, ningún archivo contiene datos con
forma real ni credenciales, los secretos no se tocan y el código queda formateado tras
cada edición.

> Nota: este ticket configura las guardas del entorno de trabajo. Los nombres de piezas y
> eventos (hooks `PreToolUse` y `PostToolUse` de Claude Code, `permissions.deny`, reglas
> en `.claude/rules/` con `paths`, ruff, MCP de GitHub) forman parte del requisito del
> issue, del enunciado y de la constitución (principio II), no son decisiones de
> implementación de esta spec.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Los secretos no se tocan desde Claude Code (Priority: P1)

Una persona del equipo trabaja con Claude Code en el repositorio. Si una acción, de
cualquier herramienta (lectura, búsqueda, edición, escritura o comando de terminal),
intenta abrir o modificar un archivo de secretos (`.env`, `.env.*`, `*.key` o algo dentro
de `secrets/`), se bloquea antes de ejecutarse y se explica por qué. `.env.example` sigue
accesible, porque no tiene valores reales.

**Why this priority**: es la necesidad 6 del enunciado y el principio VIII. Hoy la
protección es parcial: el ticket #1 dejó sin cubrir variantes como `.env.local` y
comandos como `head`, `grep` o `Get-Content`.

**Independent Test**: intentar leer `.env` y `.env.local` con la herramienta de lectura,
con un comando de terminal y con una búsqueda que apunte a ellos; las tres acciones se
bloquean. Leer `.env.example` funciona.

**Acceptance Scenarios**:

1. **Given** un archivo `.env` en la raíz, **When** Claude Code intenta leerlo, editarlo o
   escribirlo con cualquier herramienta, **Then** la acción se bloquea con un mensaje que
   nombra la regla.
2. **Given** `.env.local` o un archivo dentro de `secrets/`, **When** un comando de
   terminal lo lee (por ejemplo `head`, `grep`, `Get-Content`, `cp`), **Then** se bloquea.
3. **Given** `.env.example`, **When** se lee o se edita, **Then** la acción se permite.
4. **Given** una búsqueda cuyo patrón contiene el texto ".env" y que no apunta a archivos
   de secretos, **When** se ejecuta, **Then** se permite.
5. **Given** la configuración compartida del equipo, **When** se revisa la lista de
   denegaciones, **Then** incluye los mismos patrones de secretos que el hook.
6. **Given** código en línea de un intérprete que abre `.env`, **When** se ejecuta,
   **Then** se bloquea.

---

### User Story 2 - Ningún archivo recibe datos con forma real ni credenciales (Priority: P1)

Cuando Claude Code va a escribir o editar un archivo, a ejecutar un comando de terminal
cuyo texto contiene datos o a publicar un comentario o un PR por el MCP de GitHub, se
revisa el contenido antes de ejecutar. Si aparece un número de tarjeta, un NIT, una
cédula con forma real o un token con forma de credencial, la acción se bloquea con un
mensaje que dice qué tipo de dato se encontró, sin repetir el valor. Los datos ficticios
del proyecto, como el identificador `CO-TV-0001` o el monto
`$80.000.000` del mensaje de ejemplo del enunciado, se permiten.

Además, una revisión automática del repositorio completo recorre todos los archivos
versionados con el mismo detector y falla si encuentra algo, para cubrir lo que no entró
por Claude Code.

**Why this priority**: es la necesidad 5 del enunciado y el principio VII. Un dato real o
una credencial en el repositorio es el error más caro y más difícil de deshacer.

**Independent Test**: intentar escribir un archivo con cada tipo de dato sensible
(construido en la prueba, sin dejarlo literal en el repositorio) y comprobar que se
bloquea; escribir el mensaje de ejemplo del enunciado y comprobar que se permite;
ejecutar la revisión del repositorio sobre el estado actual y comprobar que pasa.

**Acceptance Scenarios**:

1. **Given** un contenido con un número de 13 a 19 dígitos, con prefijo de emisor (2 a
   6), que pasa la validación de Luhn, **When** se escribe o se edita un archivo,
   **Then** se bloquea.
2. **Given** un contenido con un NIT con dígito de verificación válido, **When** se
   escribe, **Then** se bloquea.
3. **Given** un contenido con un número con forma de cédula colombiana real, **When** se
   escribe, **Then** se bloquea.
4. **Given** un contenido con un token con forma de credencial (GitHub, Anthropic, AWS o
   una clave privada), **When** se escribe o aparece en un comando de terminal, **Then**
   se bloquea.
5. **Given** el mensaje de ejemplo del enunciado, con `CO-TV-0001` y `$80.000.000`,
   **When** se escribe, **Then** se permite.
6. **Given** el estado actual del repositorio, **When** se ejecuta la revisión de todos
   los archivos versionados, **Then** no encuentra nada y pasa.
7. **Given** un comentario de issue cuyo cuerpo contiene un token con forma de
   credencial, **When** Claude Code intenta publicarlo por el MCP de GitHub, **Then** se
   bloquea antes de publicarse.

---

### User Story 3 - No se escribe código sin especificación (Priority: P1)

Cuando Claude Code va a crear o modificar código protegido, se comprueba antes que el
ticket en curso tiene su especificación, su plan y sus tareas. El ticket se deduce de la
rama actual `NNN-*`, que corresponde a `specs/NNN-*/`. Si falta alguno, o si la rama es
`main` o no sigue el patrón, la acción se bloquea con un mensaje que dice qué falta.

**Why this priority**: es la necesidad 4 del enunciado y el principio IX. Hoy se cumple
solo por instrucción (desviación temporal declarada en #1 y #2); este ticket la convierte
en garantía.

**Independent Test**: en una rama de ticket sin `tasks.md`, intentar crear un archivo
`src/**/*.py`; se bloquea diciendo que falta `tasks.md`. Con los tres documentos, la
creación se permite. En `main`, se bloquea siempre.

**Acceptance Scenarios**:

1. **Given** la rama `NNN-x` sin `specs/NNN-*/tasks.md`, **When** se escribe código
   protegido, **Then** se bloquea con un mensaje que nombra el archivo que falta.
2. **Given** la rama `NNN-x` con spec, plan y tareas, **When** se escribe código
   protegido, **Then** se permite.
3. **Given** la rama `main` o una rama sin el patrón `NNN-*`, **When** se escribe código
   protegido, **Then** se bloquea.
4. **Given** cualquier rama, **When** se escribe un archivo exento (`docs/`, `specs/`,
   `.specify/`, un Markdown o JSON de `.claude/` distinto de `.claude/settings.json` y
   `.claude/settings.local.json`, o un `test_*.py`), **Then** se permite; **When** se
   escribe `.claude/settings.json`, `.claude/settings.local.json` o `.mcp.json` sin spec,
   plan y tareas, **Then** se bloquea como código protegido.
5. **Given** una rama sin spec, **When** un comando de terminal escribe de forma
   reconocible en código protegido (redirección, copia o movimiento con destino
   protegido) o nombra código protegido en el código en línea de un intérprete o de un
   shell, **Then** se bloquea.

---

### User Story 4 - El código queda formateado tras cada edición (Priority: P2)

Después de que Claude Code escribe o edita un archivo Python, el archivo se formatea
automáticamente con la herramienta de formato del proyecto. Si el formato no se puede
aplicar (por ejemplo, el archivo tiene un error de sintaxis), se informa sin bloquear ni
deshacer la edición.

**Why this priority**: es la necesidad 7 del enunciado y el principio X. Cierra la
desviación temporal de "formateo manual antes de cada commit" de #1 y #2.

**Independent Test**: editar un archivo Python dejándolo mal formateado y comprobar que,
al terminar la edición, el comprobador de formato no encuentra diferencias.

**Acceptance Scenarios**:

1. **Given** un archivo Python mal formateado, **When** Claude Code lo edita, **Then**
   queda formateado al terminar la edición.
2. **Given** un archivo que no es Python, **When** se edita, **Then** no se formatea.
3. **Given** un archivo Python con un error de sintaxis, **When** se edita, **Then** la
   edición se conserva y se informa que no se pudo formatear.

---

### User Story 5 - Herramientas destructivas del MCP de GitHub denegadas (Priority: P2)

El MCP de GitHub expone herramientas marcadas como destructivas, como borrar un
repositorio o borrar un archivo. Por mínimo privilegio, las que el proyecto nunca
necesita quedan denegadas en la configuración compartida, con sus nombres exactos tal
como aparecen en la lista del MCP. Las que usa el ciclo de tickets siguen permitidas, y
la de escritura del Project, que también puede borrar, queda limitada a actualizar
ítems.

**Why this priority**: aprendizaje del ticket #1 (comentario del issue). Reduce el daño
posible de un error del modelo sin afectar al flujo.

**Independent Test**: en una sesión nueva, intentar invocar una herramienta destructiva
denegada; Claude Code no la ejecuta. Ejecutar `/siguiente-ticket` con un argumento que se
rechaza y comprobar que sus herramientas de lectura siguen funcionando.

**Acceptance Scenarios**:

1. **Given** la configuración compartida, **When** se intenta usar una herramienta
   destructiva denegada del MCP de GitHub, **Then** no se ejecuta.
2. **Given** las herramientas que usan `siguiente-ticket`, `/abrir-pr` y
   `/comentar-avance`, **When** se revisa la lista de denegaciones, **Then** ninguna
   aparece.
3. **Given** la herramienta de escritura del Project, que no se deniega porque el ciclo
   de tickets mueve tarjetas con ella, **When** se invoca con un método distinto de
   actualizar un ítem (por ejemplo, borrar un ítem o una vista), **Then** se bloquea
   antes de llegar al servidor; **When** se invoca para actualizar el Status de un ítem,
   **Then** se permite.

---

### User Story 6 - Convenciones por ruta para tests y herramientas MCP (Priority: P3)

Cuando Claude Code trabaja en un archivo de pruebas (`**/test_*.py`) o en una herramienta
del servidor MCP propio (`src/servidor_mcp/**/*.py`), recibe automáticamente las
convenciones de ese tipo de archivo, sin cargarlas en el resto del trabajo.

**Why this priority**: es la necesidad 3 del enunciado y el requisito de al menos 2
reglas con alcance por ruta. Guía el estilo; no es una garantía.

**Independent Test**: leer el frontmatter de las dos reglas y comprobar sus globs; abrir
un `test_*.py` y comprobar que la regla de tests está en el contexto.

**Acceptance Scenarios**:

1. **Given** `.claude/rules/tests.md`, **When** se lee su frontmatter, **Then** declara
   `paths` con `**/test_*.py`.
2. **Given** `.claude/rules/herramientas-mcp.md`, **When** se lee su frontmatter,
   **Then** declara `paths` con `src/servidor_mcp/**/*.py`.

---

### Edge Cases

- Un test de los detectores necesita un valor con forma real: lo construye en tiempo de
  ejecución (por ejemplo, calculando el dígito de verificación), de modo que el valor
  literal nunca queda escrito en el repositorio ni pasa por los hooks.
- Un número largo que no es sensible (identificadores de comentarios o de ítems de
  GitHub, hashes, marcas de tiempo en milisegundos de 13 dígitos que empiezan por 1) no
  se bloquea si no cumple todas las condiciones de su patrón (longitud, prefijo de
  emisor, separadores, dígito de verificación o palabra de contexto).
- La herramienta PowerShell está desactivada por las denegaciones de Bash; si alguien la
  activa, las guardas tratan igual los comandos de terminal de Bash y de PowerShell: un
  `Get-Content .env.local` se bloquea igual que un `head .env.local`, y un
  `Set-Content` hacia código protegido igual que una redirección.
- Un monto con signo de pesos y separador de miles (`$80.000.000`) no se bloquea, aunque
  tenga la cantidad de dígitos de una cédula.
- El mensaje de bloqueo no repite el valor sensible: dice el tipo y dónde, no el dato.
- Un hook falla por un error propio (excepción, tiempo agotado): las guardas de secretos,
  datos, spec previa y Project bloquean la acción (fallo cerrado) y lo informan; el hook
  de formato nunca bloquea.
- Una búsqueda recursiva por terminal (`grep -r`, `rg` sin respetar `.gitignore`,
  `find … -exec`, `Get-ChildItem -Recurse`) se bloquea solo si su raíz contiene archivos
  de secretos. `grep -rn ".env" src/` se permite, porque `src/` no tiene secretos (FR-002);
  `grep -r TOKEN .` se bloquea, porque la raíz del repositorio tiene `.env`.
- La rama tiene el patrón `NNN-*` pero existen dos carpetas `specs/NNN-*`: se bloquea el
  código protegido, porque el ticket en curso es ambiguo.
- Se edita `.claude/hooks/**` en el propio ticket que crea los hooks: aplica la misma
  regla de spec previa, que este ticket cumple.
- Varias ediciones en una sola acción: se revisa cada archivo y cada fragmento nuevo.

## Requirements *(mandatory)*

### Functional Requirements

**Secretos**

- **FR-001**: Un hook previo a la ejecución DEBE bloquear cualquier lectura, búsqueda
  dirigida, edición o escritura de `.env`, `.env.*` (excepto `.env.example`), `*.key` o
  archivos dentro de `secrets/`, por cualquier herramienta de Claude Code, incluidos los
  comandos de terminal que los nombran. En esta spec, "comandos de terminal" son los de
  las herramientas Bash y PowerShell de Claude Code.
- **FR-002**: Una búsqueda cuyo patrón contiene el texto ".env", sin apuntar a archivos de
  secretos, NO DEBE bloquearse.
- **FR-003**: La lista de denegaciones de la configuración compartida DEBE incluir los
  mismos patrones de secretos que el hook, para todas las herramientas de archivo y para
  los comandos de terminal más comunes de lectura y copia. Las denegaciones cubren Bash;
  la herramienta PowerShell queda desactivada por esas denegaciones y, si se activa, las
  guardas son la garantía.

**Datos con forma real y credenciales**

- **FR-004**: Un hook previo a la ejecución DEBE revisar, y bloquear la acción si
  encuentra un dato con forma real o una credencial:
  - el contenido nuevo de cada escritura o edición de archivo;
  - el texto de cada comando de terminal (Bash y PowerShell);
  - el texto que se publica por el MCP de GitHub: como mínimo, el cuerpo de
    `add_issue_comment`, `update_issue_comment` y `create_pull_request`.
- **FR-005**: El detector DEBE reconocer, con estas definiciones:
  - **Tarjeta**: 13 a 19 dígitos, seguidos o en grupos separados por un espacio o un
    guion, cuyo primer dígito es 2, 3, 4, 5 o 6 (prefijo de emisor), que pasan la
    validación de Luhn y no forman parte de una palabra o de un número más largo.
  - **NIT**: 9 dígitos (con o sin puntos de miles) seguidos de guion y un dígito de
    verificación válido según el algoritmo de la DIAN; o, tras la palabra "NIT", 9 dígitos
    más un dígito de verificación válido aunque falte el guion.
  - **Cédula colombiana**: un número de 6 a 10 dígitos (con o sin puntos de miles)
    precedido, a corta distancia, de una palabra de contexto: "cédula", "cedula", "C.C.",
    "CC", "documento de identidad" o "identificación".
  - **Credenciales**: tokens de GitHub (`ghp_`, `gho_`, `ghu_`, `ghs_` o `ghr_` seguidos
    de al menos 20 caracteres alfanuméricos, o `github_pat_` seguido de 20 o más
    caracteres `[A-Za-z0-9_]`), claves de Anthropic
    (`sk-ant-` seguido de al menos 20 caracteres), claves de acceso de AWS (`AKIA`
    seguido de 16 caracteres en mayúsculas o dígitos) y bloques de clave privada
    (`-----BEGIN … PRIVATE KEY-----`).
- **FR-006**: El detector NO DEBE bloquear los identificadores ficticios del proyecto
  (formato `XX-YY-NNNN`, como `CO-TV-0001`) ni los montos con signo de pesos y separador
  de miles (como `$80.000.000`).
- **FR-007**: Una revisión automática DEBE recorrer todos los archivos versionados con el
  mismo detector, ejecutarse con la suite de pruebas del proyecto y fallar si encuentra
  algún dato con forma real o credencial.
- **FR-008**: El mensaje de bloqueo DEBE indicar el tipo de dato y el archivo o comando,
  y NO DEBE repetir el valor encontrado.

**Spec previa**

- **FR-009**: Un hook previo a la ejecución DEBE bloquear crear o modificar código
  protegido si no existen `spec.md`, `plan.md` y `tasks.md` en la única carpeta
  `specs/NNN-*/` que corresponde a la rama actual `NNN-*`.
- **FR-010**: En `main`, en una rama sin el patrón `NNN-*` o con más de una carpeta
  `specs/NNN-*`, el hook DEBE bloquear todo código protegido.
- **FR-011**: Código protegido: `src/**/*.py` (excepto `test_*.py`), `.claude/hooks/**`,
  `.claude/settings.json` y `.mcp.json` (registran las guardas y los servidores MCP),
  `.claude/settings.local.json` (puede desactivar todas las guardas) y el directorio del
  plugin. Exentos: `docs/`, `specs/`, `.specify/`, el resto de los Markdown
  y JSON de `.claude/` y los `test_*.py`.
- **FR-012**: El hook DEBE cubrir las herramientas de escritura y edición de archivos y
  los comandos de terminal, de Bash y de PowerShell, que escriben de forma reconocible en
  una ruta protegida (redirección, `tee`, `Set-Content`, `Out-File`, copia o movimiento
  con destino protegido), incluidos los que van dentro de otro shell (`bash -c`, `eval`)
  y el código en línea de un intérprete que nombra una ruta protegida.
- **FR-013**: El mensaje de bloqueo DEBE decir qué documento falta, o por qué la rama no
  permite código.

**Formato**

- **FR-014**: Un hook posterior a la edición DEBE formatear con la herramienta de formato
  del proyecto cada archivo Python escrito o editado con las herramientas Write y Edit de
  Claude Code.
- **FR-015**: El hook de formato NO DEBE bloquear ni deshacer la edición; si no puede
  formatear, DEBE informarlo.

**Herramientas destructivas del MCP de GitHub**

- **FR-016**: La lista de denegaciones de la configuración compartida DEBE incluir, con
  sus nombres exactos, las herramientas del MCP de GitHub marcadas como destructivas que
  el proyecto no usa, como mínimo borrar un repositorio y borrar un archivo.
- **FR-017**: NO DEBE denegarse ninguna herramienta que usen `siguiente-ticket`,
  `/abrir-pr` o `/comentar-avance`.
- **FR-024**: Un hook previo a la ejecución DEBE limitar la herramienta de escritura del
  Project del MCP de GitHub (`projects_write`, que el ciclo de tickets necesita) al único
  método que usa el proyecto, actualizar un ítem (`update_project_item`), y bloquear
  cualquier otro método, incluidos los de borrado.

**Reglas por ruta**

- **FR-018**: DEBE existir `.claude/rules/tests.md` con `paths` que cubra `**/test_*.py`
  y las convenciones comunes de pruebas: junto al módulo, solo datos ficticios, valores
  sensibles construidos en tiempo de ejecución y los casos obligatorios de la
  constitución.
- **FR-019**: DEBE existir `.claude/rules/herramientas-mcp.md` con `paths` que cubra
  `src/servidor_mcp/**/*.py` y las convenciones de diseño de herramientas del principio
  IV: descripción inequívoca de qué hace y qué no, errores estructurados que dicen si se
  puede reintentar, contenido separado de metadatos y solo datos ficticios.

**Transversales**

- **FR-020**: Las guardas de secretos, datos, spec previa y Project (FR-024) DEBEN
  fallar cerradas: si el propio hook falla, la acción se bloquea con un mensaje que lo
  explica.
- **FR-021**: Los hooks DEBEN tener pruebas automáticas que se ejecuten con la suite del
  proyecto y pasen.
- **FR-022**: Los hooks y la configuración DEBEN estar en la configuración compartida
  versionada, de modo que quien clona el repositorio los recibe sin configurar nada, y
  DEBEN funcionar en Windows, macOS y Linux.
- **FR-023**: Los mensajes de los hooks DEBEN estar en español.

### Key Entities

- **Guarda**: comprobación automática asociada a un evento (antes de ejecutar una acción
  o después de una edición), con su alcance (herramientas y rutas) y su efecto (bloquear,
  permitir o actuar).
- **Patrón sensible**: tipo de dato (tarjeta, NIT, cédula, credencial), su regla de
  reconocimiento y sus exclusiones.
- **Archivo de secretos**: archivo cuyo nombre o ruta coincide con `.env`, `.env.*`
  (excepto `.env.example`), `*.key` o `secrets/`.
- **Código protegido**: archivo que solo se puede crear o modificar con spec, plan y
  tareas del ticket en curso: el código de `src/`, los hooks, `.claude/settings.json`,
  `.claude/settings.local.json`, `.mcp.json` y el plugin.
- **Ticket en curso**: el que indica el prefijo `NNN` de la rama actual, con su carpeta
  `specs/NNN-*/`.
- **Regla por ruta**: archivo de `.claude/rules/` con `paths` que limita a qué archivos
  aplica.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los casos de bloqueo de los criterios de aceptación se bloquean
  (secretos, cada tipo de dato sensible, código sin spec), y el 0 % de los casos
  permitidos se bloquea (`.env.example`, mensaje de ejemplo del enunciado, archivos
  exentos, búsqueda con el texto ".env").
- **SC-002**: La revisión de todos los archivos versionados no encuentra nada en el
  estado del repositorio al cerrar el ticket, y detecta el 100 % de una muestra de
  valores sensibles generados durante la prueba.
- **SC-003**: Después de cualquier edición de un archivo Python con sintaxis válida, el
  comprobador de formato no encuentra diferencias en ese archivo.
- **SC-004**: Las guardas no añaden una espera perceptible: cada comprobación termina en
  menos de 1 segundo, medida en caliente, desde la segunda llamada de la sesión. La
  primera llamada puede tardar más (≈ 1,1 s medido), porque `uv` prepara el entorno.
- **SC-005**: El 100 % de los mensajes de bloqueo dicen qué se bloqueó y por qué, en
  español, y ninguno repite un valor sensible.
- **SC-006**: Al cerrar el ticket, la desviación temporal del principio II declarada en
  #1 y #2 queda cerrada para la spec previa, los secretos y los datos con forma real, y la
  del principio X, para el formateo.

## Assumptions

- **Cédula con contexto**: sin palabra de contexto, un número de 6 a 10 dígitos no se
  bloquea. Exigir contexto evita falsos positivos con identificadores de GitHub y otros
  números largos del repositorio; el resto de formas reales (tarjeta, NIT) se reconocen
  por su estructura.
- **Datos ficticios**: las pruebas que necesitan valores con forma real los generan en
  tiempo de ejecución; no hay una lista de valores permitidos ni una forma de saltarse
  las guardas.
- **Riesgo residual**: la guarda reconoce los secretos nombrados en rutas, en el código en
  línea de los intérpretes y de los shells, en `eval` y en los heredocs, y las búsquedas
  recursivas cuya raíz contiene secretos. Escapan solo los rodeos deliberados: rutas
  construidas al ejecutar, texto codificado (por ejemplo, en base64) y scripts escritos
  en un archivo y ejecutados después. La búsqueda de Claude Code respeta `.gitignore`,
  que excluye `.env`.
- **Directorio del plugin**: aún no existe (#13). El plan fija su ruta para que la guarda
  de spec previa ya la proteja.
- **Formato**: la herramienta de formato es la del proyecto (ruff, ticket #1). El hook
  solo formatea; no corrige reglas de lint. Un `.py` escrito por un comando de terminal
  no pasa por el hook; lo detecta `ruff format --check` antes del PR.
- **Herramientas destructivas**: la lista exacta se toma de la lista del MCP de GitHub en
  una sesión con el servidor conectado y se fija en el plan.
- **Ciclo del ticket**: este ticket se construye con el ciclo automatizado de #2. La
  revisión previa al PR sigue siendo la de transición de `/abrir-pr` hasta #4.
- Los hooks del Agent SDK para las reglas de negocio son del ticket #7.
