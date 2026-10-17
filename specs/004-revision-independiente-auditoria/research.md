# Research: Revisión independiente y auditoría de cumplimiento

Decisiones técnicas del ticket #4. Cada decisión cita su fuente. Lo que la documentación no
dice se marca **"la doc no lo especifica"** y se comprueba en la sesión (quickstart, Q1–Q6),
no se da por cierto.

Fuentes consultadas (documentación de Claude Code, consultadas el 2026-10-16):

- Skills: <https://code.claude.com/docs/en/skills.md>
- Subagentes: <https://code.claude.com/docs/en/sub-agents.md>
- Hooks: <https://code.claude.com/docs/en/hooks.md>
- Memoria, CLAUDE.md y reglas: <https://code.claude.com/docs/en/memory.md>

## R1. Cómo se liga una skill con `context: fork` a su subagente

**Decisión**: cada skill declara `context: fork` y `agent: <nombre>` apuntando a un subagente
propio de `.claude/agents/`: `revisar-codigo` → `revisor-codigo`, `auditar-cumplimiento` →
`auditor-cumplimiento`. El cuerpo de la skill es el prompt de la tarea.

**Fuente** (skills.md):

- "The `agent` field specifies which subagent configuration to use. Options include built-in
  agents (`Explore`, `Plan`, `general-purpose`) or any custom subagent from
  `.claude/agents/`. If omitted, uses `general-purpose`."
- "Claude Code starts a new subagent of the type set in the `agent` field and gives it the
  skill content as its prompt. The subagent doesn't see your conversation history, so the
  skill's instructions have to stand on their own."
- Campos respetados: "Claude Code accepts every field in the table above." Entre ellos
  `allowed-tools`, `argument-hint` y `model` ("with `context: fork`, the value sets the
  forked subagent's model instead").

**Consecuencias**:

- Sin `agent:` la skill correría como `general-purpose`, con todas las herramientas. El
  campo es obligatorio para cumplir FR-003.
- El subagente no ve la conversación: es la independencia que pide FR-004. El prompt (la
  skill) tiene que bastarse solo (R3, R6).
- Una skill por revisión, porque un subagente puede lanzar otros por defecto (R5), pero el
  diseño no depende de eso.

**Alternativas descartadas**: un solo subagente con las dos tareas (mezcla la revisión
técnica y la de negocio, y se contamina el reporte) y subagentes `Plan` o `Explore`
integrados (no cumplen "herramientas restringidas a su rol" de forma versionada y
verificable, y no reciben CLAUDE.md, R3).

## R2. Inyección del diff: sintaxis, permisos y Bash (FR-003 frente a FR-005)

**Decisión**: el contexto lo prepara la propia skill con la sintaxis de inyección
(signo de exclamación seguido del comando entre comillas invertidas) que ejecuta un script
del proyecto, y el subagente queda **sin Bash**. La skill declara en `allowed-tools` solo el
comando exacto del script; el subagente declara en `tools` solo `Read`, `Grep` y `Glob`.

**Fuente** (skills.md):

- Momento: "The `!`<command>`` syntax runs shell commands before the skill content is sent to
  Claude. The command output replaces the placeholder, so Claude receives actual data, not
  the command itself."
- Permisos: "Injected commands never prompt for permission while the skill renders. Claude
  Code checks each one against your permission rules first." Se pre-aprueba con
  `allowed-tools`, por ejemplo `Bash(gh *)`. Un comando que una regla `deny` encuentra
  "aborts the invocation".
- Fallo: "A failed command aborts the entire skill invocation, not just its own placeholder.
  Claude never sees the skill content for that invocation." Un código de salida distinto de
  cero es fallo, salvo el 1 en comandos de búsqueda y comparación.
- `allowed-tools` no restringe: "every tool remains callable, and your permission settings
  still govern tools that are not listed." Solo pre-aprueba durante ese turno.

**Resolución de FR-003 frente a FR-005**: no chocan, porque la inyección la hace la skill al
renderizarse, antes de crear el subagente. El subagente recibe el resultado ya inyectado y
no necesita Bash.

**Lo que la doc no especifica** (se comprueba, Q2 y Q3):

- Con `context: fork`, la doc no dice de forma explícita que la inyección ocurra antes de
  crear el subagente; es la lectura natural ("before the skill content is sent").
- La doc no dice que `allowed-tools` de la skill añada herramientas a un subagente con
  `tools` limitadas. Si lo hiciera, el subagente ganaría Bash y se rompería FR-003. Q2
  comprueba que el subagente **no puede ejecutar un comando**.

**Consecuencias de diseño**:

1. **El script no puede fallar**: un fallo aborta toda la invocación y el revisor nunca vería
   nada. `preparar_revision.py` sale siempre con 0; si no puede calcular algo, lo dice en su
   salida con un marcador (`CONTEXTO INCOMPLETO: …`), y el revisor lo trata como "no pudo
   leer" (R6).
2. **Nada del argumento llega al shell**: `$ARGUMENTS` es texto que escribe el modelo; si se
   interpolara dentro del comando inyectado, sería una inyección de comandos. El script
   deduce el ticket de la rama; `$ARGUMENTS` solo aparece en prosa de la skill.
3. **Mínimo privilegio en `allowed-tools`**: el patrón es el comando exacto del script, no
   `Bash(git *)`. La ruta del script se resuelve con una variable de la propia skill
   (`${CLAUDE_SKILL_DIR}` o `${CLAUDE_PROJECT_DIR}`, ver Q1), nunca con una ruta absoluta:
   el comando y su patrón deben funcionar en cualquier clon y desde cualquier carpeta de
   trabajo. Q1 comprueba cuál de las dos variables se resuelve dentro de una skill y que el
   patrón de `allowed-tools` coincide con el comando ya resuelto.
4. **Marca de contexto**: la salida del script empieza con la línea fija
   `CONTEXTO DE REVISIÓN`. Si el subagente no la ve (la inyección falló, o está desactivada
   con `disableSkillShellExecution`), no hay contexto fiable: lo reporta y declara
   `cobertura=incompleta` (R7). Así una inyección que no corrió no se confunde con un cambio
   vacío.
4. `disable-model-invocation` no se usa: `/abrir-pr` invoca las skills con la herramienta
   Skill y la doc dice que ese campo impide que Claude la cargue (skills.md: "Set to `true`
   to prevent Claude from automatically loading this skill"). No se arriesga la invocación.

## R3. ¿Recibe el subagente CLAUDE.md y la constitución?

**Decisión**: no se depende del `@import`. Cada skill ordena leer
`.specify/memory/constitution.md` con `Read` y entrega explícitamente las rutas de `spec.md`,
`plan.md` y `tasks.md`. Los subagentes personalizados no activan `omitClaudeMd`.

**Fuente**:

- sub-agents.md, "What loads at startup": el subagente recibe "every level of the CLAUDE.md
  hierarchy the main conversation loads, including `~/.claude/CLAUDE.md`, project rules,
  `CLAUDE.local.md`, managed policy files, and any AGENTS.md files". Y: "The built-in
  Explore and Plan agents skip this." Los personalizados con `omitClaudeMd: true` no lo
  cargan.
- Historial: "It doesn't see your conversation history, the skills you've already invoked,
  or the files Claude has already read." Solo los forks de la conversación la heredan.
- Imports: memory.md dice, en general, "Imported files are expanded and loaded into context at
  launch alongside the CLAUDE.md that references them." **La doc no lo especifica para
  subagentes**; la inferencia es que el `@.specify/memory/constitution.md` de `CLAUDE.md`
  llega con él. No se confía en una inferencia para una regla obligatoria (II).
- Reglas por ruta: las `.claude/rules/` con `paths:` cargan bajo demanda cuando el subagente
  trabaja con archivos que coinciden (sub-agents.md). La regla `tests.md` (`**/test_*.py`)
  puede cargarse al leer tests; es deseable.

**Consecuencia**: leer la constitución con `Read` es independiente de lo que cargue el
subagente, y deja la lectura **visible** en el reporte (el auditor cita el principio I). Q3
comprueba si además llega por `@import`, solo como dato para `DECISIONES.md`.

## R4. Límite de tamaño de la inyección y diffs grandes

**Decisión**: el umbral se aplica a **toda la salida** de `preparar_revision.py` (marca, lista
de archivos, rutas del ticket y diff), no solo al diff: lo que Claude Code mide es la salida
completa del comando. El script emite **siempre** la marca, la lista con estadísticas y las
rutas; añade el diff completo **solo si la salida total sigue por debajo de
`UMBRAL_SALIDA`**, que vale **la mitad del techo medido** de la herramienta Bash (el margen
es ese 50 %). Valor provisional hasta medirlo: 30 000 bytes; Q4 mide el techo real y T031
fija el valor definitivo. Por encima, la salida indica que el
diff se omitió y el revisor lee los archivos de la lista con `Read` y `Grep`. Si la lista y
las rutas por sí solas superaran el umbral (PR con cientos de archivos), la lista se agrupa
por directorio con sus totales y se dice así.

**Fuente** (skills.md):

- Timeout: "each command runs under the Bash tool's default 2-minute timeout."
- Tamaño: "output past the Bash tool's inline ceiling arrives as a file path plus a short
  preview", no como texto truncado. **El valor numérico no se pudo leer** (está en una página
  enlazada, "Output limits"): la doc no lo especifica en lo consultado. Q4 lo mide con una
  salida de tamaño conocido: ¿llega en línea o como ruta?
- Cuerpo de la skill: solo recomienda "Keep `SKILL.md` under 500 lines"; no hay límite duro
  documentado. Tras la compactación, cada skill invocada conserva "the first 5,000 tokens".
- Salida de `Read` y `Grep` del subagente: **la doc no lo especifica**; no hay tope numérico
  documentado.

**Por qué un umbral propio en vez de confiar en el de Claude Code**: con un umbral
desconocido, un diff grande llegaría como "ruta de archivo más vista previa" sin que el
diseño lo controle. Con un umbral propio, por debajo de él el diff llega entero y por encima
el comportamiento es el especificado (spec, caso límite de diffs grandes): lista más lectura
selectiva. El PR #17 pesaba ≈ 370 KB y sin esta salida ningún PR real se aprobaría.

**Cobertura**: "no cubrió el cambio" significa **no poder leer algún archivo de la lista**
(por ejemplo, un binario). Solo entonces el reporte declara `cobertura=incompleta` y el
veredicto no puede ser aprobado (R7). Un diff omitido por tamaño no es falta de cobertura.

**Los documentos del propio ticket no cuentan para la cobertura**: los archivos de
`specs/NNN-*/` (spec, plan, tareas, research, contratos…) se leen como referencia, con `Grep`
o por secciones, y no hace falta leerlos enteros. Cuentan el código y la configuración. Sin
esto, un PR como el #17, cuyo diff pesaba ≈ 370 KB en su mayoría de documentos, no podría
aprobarse nunca. Q4 usa un clon desechable de la rama 004 con `origin/main` en
`b7d5f48^1` (R13) y comprueba que la revisión termina con `cobertura=completa`.

**Alternativas descartadas**: entregar siempre el diff entero (inviable, ≈ 370 KB), entregar
solo la lista sin diff nunca (pierde el contexto de las líneas cambiadas en los cambios
pequeños) y dar `Bash(git diff)` al subagente (viola FR-003).

## R5. Herramientas de los subagentes

**Decisión**: `tools: Read, Grep, Glob` en cada subagente. Sin `Agent`, sin MCP, sin Bash.

**Fuente** (sub-agents.md):

- "`tools`: Inherits every tool available to subagents if omitted." Hay que listarlas.
- "`disallowedTools`: Tools to deny, removed from inherited or specified list."
- Por defecto, "a subagent can spawn subagents of its own, up to three layers below the main
  conversation"; se impide quitando `Agent` de `tools`.
- Las herramientas MCP se otorgan o quitan por servidor (`mcp__<server>`); con una lista
  explícita de `tools`, las que no están en ella no existen para el subagente.

**Consecuencia**: la lista explícita cumple FR-003 desde el rol, no por la instrucción del
prompt. `test_agentes_skills.py` verifica que `tools` es exactamente ese conjunto. Q2 lo
comprueba en la sesión (el subagente no puede ejecutar un comando ni escribir).

**Límite honesto**: `Read` puede leer cualquier archivo, también los secretos. Lo cubre
`guarda_secretos` para `Read|Grep|Glob`, si los hooks de la sesión se aplican a las
herramientas de los subagentes (**la doc no lo especifica**; Q5). Se declara en
`DECISIONES.md`.

## R6. Contexto de cada revisión: base de fusión y entrega

**Decisión**: `preparar_revision.py` (en `.claude/hooks/`, solo biblioteca estándar) imprime:

0. **Marca**: la primera línea de la salida es `CONTEXTO DE REVISIÓN` (R2.4).
1. **Base**: `git merge-base HEAD origin/main`, con `origin/main` actualizado por el `git
   fetch origin main` que `/abrir-pr` ejecuta **antes** de las skills. El script no usa la
   red ni el `main` local (spec FR-001, ajuste 3).
2. **Lista de archivos** cambiados (`git diff --numstat` y `--name-status` de
   `<base>..HEAD`) con estadísticas.
3. **Diff completo**, solo si la salida total cabe en el umbral (R4).
4. **Ticket**: carpeta `specs/NNN-*/` deducida de la rama y rutas de `spec.md`, `plan.md` y
   `tasks.md`, más la ruta de la constitución. Los archivos de esa carpeta aparecen en la
   lista marcados como **referencia**: no cuentan para la cobertura (R4).
5. **Estado**: si algo falla (sin `origin/main`, sin merge-base, rama sin carpeta de specs),
   emite `CONTEXTO INCOMPLETO: <motivo>` y termina con 0 (R2, consecuencia 1).

La misma salida alimenta las dos skills; cada una la inyecta en su cuerpo. Los archivos
**eliminados** figuran en la lista y no se pueden leer: el revisor los trata como leídos por
el diff si cabe, o como "no pudo leer" si el diff se omitió; el script marca los eliminados
para que no cuenten como falta de cobertura cuando el diff está presente.

**Alternativas descartadas**: `git diff origin/main...HEAD` ejecutado por la skill sin
script (no limita el tamaño, no sale siempre con 0) y diff contra el `main` local (puede
estar desactualizado: spec, ajuste 3).

## R7. Formato del reporte y consolidación del veredicto

**Decisión**: cada subagente termina su reporte con **una línea de resumen** de formato fijo
y el registro la valida de forma estricta:

```text
RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>
```

El auditor añade antes del resumen una tabla de las cinco reglas con estado y evidencia
(cumple, incumple, no aplica, no verificada). `/abrir-pr` pasa las dos líneas a
`registrar_veredicto` (R8), que consolida:

- **aprobado** solo si las dos líneas se leen, las dos tienen `bloqueantes=0` y
  `cobertura=completa`, **y el cambio frente a la base no está vacío**;
- **con bloqueantes** en cualquier otro caso, incluida una línea ausente o con formato
  inesperado (FR-008).

**Cambio vacío (determinista)**: lo comprueba `veredicto.py registrar` con git
(`git diff --quiet <base>..HEAD`, con la misma base que `preparar_revision.py`: `git
merge-base HEAD origin/main`), no el reporte. Sin cambios, el veredicto es `con bloqueantes
(sin cambios)` diga lo que diga el reporte; si no puede calcular la base, `con bloqueantes
(sin base de comparación)`. La base y la comprobación son funciones de `veredicto.py` que
`preparar_revision.py` importa, para que las dos usen la misma.

Cada subagente declara `cobertura=incompleta` también si la salida inyectada no empieza con
la marca `CONTEXTO DE REVISIÓN` (R2.4) o si no pudo leer algún archivo de código o
configuración de la lista (R4).

Por qué una línea de máquina y no leer el texto libre: el veredicto gobierna la puerta
(principio II); la fuente de verdad son números validados, no una interpretación del texto.
La misma regla del proyecto (principio III) evita decidir por palabras en el texto; aquí se
valida un formato fijo y su ausencia bloquea.

**Cuándo aplica una regla de negocio** (spec FR-007): aplica si la spec del ticket la cita o
si el diff toca código o tests que la implementan o la prueban. La instrucción del auditor lo
detalla y exige la razón de cada "no aplica". Sin código de producción ni tests de las
reglas, las cinco figuran "no aplica". Un cambio que solo borra o debilita el test de una
regla **sí la toca**: sin evidencia vigente es `no verificada` y bloqueante.

## R8. Veredicto: dónde vive, qué guarda y quién lo escribe

**Decisión**: `registrar_veredicto` es un script (`veredicto.py`, en `.claude/hooks/`)
con subcomando de línea de comandos que `/abrir-pr` invoca por Bash. Guarda un archivo por
commit en `.claude/veredictos/<sha>.json`, ignorado por git (`.gitignore`). El `<sha>` es el
del commit **revisado** (`--commit`, obligatorio y hexadecimal completo), no el que exista al
registrar: si `HEAD` cambió mientras corrían las revisiones, no escribe nada. Sin esa
comprobación, un commit hecho durante la revisión quedaría aprobado sin que nadie lo
revisara. El formato de `RESUMEN` usa solo dígitos `[0-9]`.

```json
{
  "commit": "<sha completo>",
  "rama": "004-...",
  "veredicto": "aprobado | con bloqueantes",
  "fecha": "2026-10-16T21:00:00Z",
  "codigo": {"bloqueantes": 0, "sugerencias": 2, "cobertura": "completa"},
  "auditoria": {"bloqueantes": 0, "sugerencias": 1, "cobertura": "completa"}
}
```

- Se registran **los dos veredictos** (spec FR-010); la puerta solo acepta `aprobado`.
- Un archivo por commit, no uno global: un commit nuevo no tiene archivo, por lo que el
  veredicto anterior deja de valer sin lógica adicional (FR-011), y se conservan los de
  bloqueantes para trazabilidad.
- El módulo es el único lugar que conoce el formato; la guarda y el registro lo comparten.
- Un archivo ilegible o con formato inesperado es "sin veredicto" (spec, caso límite).

**Protección del directorio (FR-020)**: `.claude/veredictos/` se protege con el patrón de
FR-025 de #3 para `.claude/settings.local.json`: ninguna herramienta lo modifica, en ninguna
rama (no se versiona ni depende del ticket). Se cubre en las dos capas de #3:

- `guarda_spec_previa.py` añade el directorio a su lista de rutas bloqueadas en cualquier
  rama, con las mismas vías que ya vigila para `settings.local.json`: Write, Edit y
  NotebookEdit, redirecciones, `tee`, `cp`, `mv`, `sed -i`, `touch` y el código en línea o
  los comandos interiores que lo nombran. Leerlo sigue permitido, porque la puerta y las
  personas lo consultan.
- `permissions.deny` gana `Edit(/.claude/veredictos/**)` como primera barrera, anclada a la
  raíz como la de `settings.local.json`.

La única vía de registro es la CLI de `veredicto.py`: el comando que `/abrir-pr` ejecuta no
nombra el directorio (la ruta la calcula el script), así que la guarda no lo bloquea.

**Límite declarado** (FR-018, a `DECISIONES.md`): la puerta comprueba que exista un
veredicto aprobado del commit actual escrito por el comando de registro; no sabe si los
`RESUMEN` que recibió vienen de una revisión real. Quien invoque `veredicto.py registrar`
con resúmenes inventados obtiene un veredicto aprobado. Es la limitación que el issue acepta,
ahora reducida a esa vía.

**Alternativas descartadas**: un archivo único `ultimo.json` (se pisa y pierde la
trazabilidad), guardarlo en `.git/` (no hay motivo, y `.claude/` ya está en la configuración
de la sesión), una nota de git (viaja con el repositorio, lo que no se quiere) y firmarlo
(el issue acepta el límite; una firma con clave local no cambia quién puede escribirlo).

## R9. Commit publicado: cómo comprueba la guarda el último commit de la rama

**Decisión**: la guarda compara con la referencia de seguimiento local `refs/remotes/origin/<rama>`
(`git rev-parse`, milisegundos), no con `git ls-remote`. `/abrir-pr` ejecuta `git fetch
origin <rama>` antes de registrar el veredicto y `git push` actualiza esa referencia.

**Medición** (2026-10-16, esta máquina): `git ls-remote --heads origin` tarda ≈ **1,2 s**.
Solo eso ya supera el 1 s de SC-004, sin contar el ≈ 0,5 s de arranque de `uv run`. Con la
referencia local, la guarda queda en el orden de 0,5 s.

**Qué cubre y qué no**:

- Cubre: commit sin publicar (no hay `origin/<rama>` o apunta a otro commit) y rama remota con
  otros commits **conocidos tras el último `fetch`/`push`** (spec FR-011, FR-012).
- No cubre: un commit que otra persona empujó a la rama **después** del último fetch de esta
  máquina. Se declara como residual en `DECISIONES.md`. `git push` de `/abrir-pr` falla si la
  rama remota avanzó (no es un avance rápido), lo que lo cubre en la práctica.

**Alternativa**: `git ls-remote` en la guarda, autoritativa, a costa de ≈ 1,2 s y de fallar
cerrada sin red. **Es una decisión para la analista**: se deja `ls-remote` fuera por SC-004;
si prefiere autoridad sobre velocidad, cambia FR-011 a "autoritativa" y SC-004 a "excluida la
red". Recomendado: referencia local.

## R10. La guarda de PR: qué vigila y cómo

**Decisión**: una guarda `PreToolUse`, `guarda_pr.py`, con matcher
`Bash|PowerShell|mcp__github__create_pull_request`, misma interfaz que las demás
(`comun.ejecutar`, salida 2, `onFailure: "block"`, timeout de 10 s).

**Fuente** (hooks.md): "Exit with code 2 to block the action"; el mensaje es el stderr del
hook. `onFailure: "block"` cubre el timeout, que `uv` falte y otros códigos de salida (que por
defecto no bloquean); es la misma decisión de #3 (R2). Para MCP: "MCP tools follow the naming
pattern `mcp__<server>__<tool>`", es decir `mcp__github__create_pull_request`; sus campos de
`tool_input` son los del esquema de la herramienta (`owner`, `repo`, `head`, `base`, `title`,
`body`), que `/abrir-pr` ya usa. Todos los hooks que coinciden corren en paralelo.

**Qué detecta**:

| Vía | Detección |
|-----|-----------|
| MCP | `tool_name == mcp__github__create_pull_request`; la rama es `tool_input.head`, **normalizada**: el campo puede venir como `propietario:rama` (la forma de la API de GitHub). Si trae prefijo, debe coincidir con `tool_input.owner` (sin distinguir mayúsculas) y se toma lo que sigue a los dos puntos; si el prefijo es otro, es un PR desde un fork y se bloquea. Con test |
| `gh pr create` | el extractor de #3 (`extraer_texto_ejecutable`) y `quitar_envoltorios` recorren el comando exterior, los interiores (`bash -c`, `eval`, heredocs) y los lanzadores; en cada comando simple, programa `gh` con los dos primeros no-opciones `pr create`; la rama es `--head`/`-H` o la actual |
| `gh api` | programa `gh` con `api` y endpoint `repos/<o>/<r>/pulls` (sin subrutas) y método POST, explícito (`-X`, `--method`) o implícito (`-f`, `-F`, `--field`, `--raw-field`, `--input`); y `graphql` cuyo texto contenga `createPullRequest` |
| Otros | `gh pr view`, `gh pr list`, `gh api` con GET, etc. se permiten (FR-014) |

**Comprobación** (misma para las tres vías, una vez identificada la rama):

1. HEAD y la rama actual (`git rev-parse HEAD`, `git branch --show-current`).
2. Si la rama del PR no es la actual → bloquea (no hay forma de probar el veredicto de otra
   rama sin cambiar de rama; mensaje: cambia a la rama o usa `/abrir-pr`).
3. `refs/remotes/origin/<rama>` existe y es igual a HEAD (R9).
4. `.claude/veredictos/<HEAD>.json` existe, se lee con el formato esperado y trae
   `veredicto: aprobado`.
5. Cualquier excepción → salida 2.

El mensaje dice qué falta (sin veredicto, con bloqueantes, commit sin publicar o rama remota
distinta, revisión de otro commit) y cómo obtenerlo (`/abrir-pr`).

**Alternativas descartadas**: un `permissions.deny` para `gh pr create` (el propio `/abrir-pr`
crea el PR por el MCP, y `deny` no admite condiciones sobre el veredicto; como barrera sola
bloquearía también el uso legítimo) y bloquear `Bash(gh *)` entero (rompe el ciclo de
tickets).

**Riesgos residuales** (a `DECISIONES.md`):

- Crear el PR fuera de Claude Code (la web, otro cliente, `curl` a la API) no pasa por la
  guarda.
- Alias de `gh`, `gh` invocado con rutas construidas al ejecutar o con una variable como
  subcomando, o `gh` dentro de un script escrito y ejecutado después: el extractor no los
  reconoce (mismo alcance que las guardas de #3, R9 y R10).
- Invocar `veredicto.py registrar` con `RESUMEN` inventados: la puerta no lo distingue de una
  revisión real (R8). Escribir el archivo a mano ya no es residual (FR-020).

## R11. Cambios en `/abrir-pr` y en el resto del ciclo

**Decisión**: la sección 2 de `.claude/commands/abrir-pr.md` (revisión de transición con el
subagente `Plan`) se **reemplaza**; no quedan dos revisiones (FR-019). Orden nuevo:

1. Comprobaciones (como hoy, sin cambios).
2. `git fetch origin main <rama>` (R6, R9; el fetch de `<rama>` falla sin error fatal si aún
   no existe).
3. Skill `revisar-codigo` y skill `auditar-cumplimiento`, con la carpeta del ticket como
   argumento; cada una devuelve su reporte (con la línea `RESUMEN`).
3a. Antes de las skills, `git rev-parse HEAD` y se guarda el sha: es el commit que se revisa.
4. `veredicto.py registrar --commit <sha>` con las dos líneas (R7, R8). Si `HEAD` cambió
   durante la revisión, no escribe nada y sale con 2 (el veredicto es del commit revisado,
   no del que exista al registrar). Con bloqueantes, se detiene, muestra los hallazgos y no
   hay push ni PR (FR-009).
5. `git push -u origin <rama>` (actualiza `origin/<rama>`, R9).
6. `create_pull_request` (la guarda de R10 lo comprueba), estado y comentario, como hoy; la
   sección "Revisión previa" de la descripción pasa a citar el veredicto, los dos resúmenes y
   los hallazgos no bloqueantes.

`allowed-tools` de `/abrir-pr`: sale `Agent` y `Bash(git diff:*)`; entran `Skill(revisar-codigo)`,
`Skill(auditar-cumplimiento)`, `Bash(git fetch:*)` (ya está), el comando de `registrar_veredicto`
y `Bash(git rev-parse:*)`. Los permisos exactos se fijan en la implementación.

**Orden y guarda**: el push va **antes** de crear el PR y **después** del veredicto; la guarda
exige que HEAD esté publicado, así que no se puede abrir el PR sin haber empujado el commit
revisado.

**Documentación**: `DECISIONES.md` gana una entrada 5; el README, una frase en "Ciclo de un
ticket"; `DECISIONES.md` entrada 3 se anota ("la revisión de transición queda reemplazada
por #4"). `CLAUDE.md` no cambia (37 líneas).

## R12. Tests

**Decisión**: pytest junto a cada módulo, en `.claude/hooks/`, como en #3 (`testpaths` ya lo
cubre):

- `test_veredicto.py`: registrar, leer, formato inesperado, un archivo por commit,
  consolidación con resúmenes válidos, ausentes y mal formados, y rama sin cambios frente a
  la base (`con bloqueantes (sin cambios)` aunque los dos resúmenes sean limpios) o sin base
  calculable.
- `test_preparar_revision.py`: lista y estadísticas, umbral, base de fusión, archivos
  eliminados, marcador de contexto incompleto y salida 0 siempre. Con repositorios temporales
  creados en el test.
- `test_guarda_pr.py`: cada vía (MCP, `gh pr create`, `gh api` POST implícito y explícito,
  envoltorios), los permitidos (`gh pr view`, `gh api` GET), commit sin publicar, rama remota
  distinta, veredicto con bloqueantes, de otro commit, ilegible; y la ejecución de extremo a
  extremo por stdin con salida 2. Repositorios temporales; ningún dato real.
- `test_agentes_skills.py`:
  - en los dos subagentes, `tools` es exactamente `Read, Grep, Glob` (ni una más);
  - cada skill declara `context: fork`, `agent:` enlazado a un subagente que existe en
    `.claude/agents/`, `argument-hint` y `allowed-tools`;
  - `allowed-tools` de las skills contiene **solo** el comando del script de preparación;
  - el comando inyectado no interpola `$ARGUMENTS` (R2.2) y no usa rutas absolutas (R2.3);
  - `/abrir-pr` ya no usa `Agent`.
- Ampliación de `test_guarda_spec_previa.py`: el directorio de veredictos se bloquea en
  cualquier rama por Write, Edit, redirección, `cp`, `mv` y código en línea, se permite
  leerlo, y el comando de registro no se bloquea (FR-020).
- En `test_guarda_pr.py`, además: `head` con y sin prefijo `propietario:rama`, con prefijo
  que no coincide con `owner` (bloquea) y con distinto uso de mayúsculas (R10).
- Ampliación de `test_configuracion.py`: la guarda está registrada con `onFailure: "block"`,
  su matcher es la lista exacta y `permissions.deny` incluye `Edit(/.claude/veredictos/**)`.

## R13. Lo que se comprueba en la sesión (no se supone)

| # | Qué | Por qué |
|---|-----|---------|
| 1 | Qué variable resuelve la ruta del script dentro de una skill (`${CLAUDE_SKILL_DIR}` o `${CLAUDE_PROJECT_DIR}`) y que el comando y su patrón de `allowed-tools` funcionan en cualquier clon y desde cualquier carpeta, sin rutas absolutas | La doc da el ejemplo `Bash(gh *)`; no se asume cómo coincide un patrón con un comando con `uv run` y variables |
| 2 | El subagente **no** puede ejecutar un comando ni escribir | `allowed-tools` de la skill podría ampliar sus herramientas (la doc no lo especifica) |
| 3 | Si la constitución llega por `@import` | La doc no lo especifica para subagentes; solo informa, el diseño no depende de ello |
| 4 | El techo real de la salida inyectada, con una salida de tamaño conocido (¿llega en línea o como ruta?), y una revisión de un PR grande en un **clon desechable** de la rama 004, fuera del repositorio, con `git update-ref refs/remotes/origin/main b7d5f48^1`: el diff es el del #3 más el del #4 (41 archivos, ≈ 475 KB, medido) y las skills ya están en el clon | La doc enlaza una página que no se pudo leer; hay que fijar `UMBRAL_SALIDA` (la mitad del techo) y comprobar `cobertura=completa` con un PR grande. El rango `b7d5f48^1..5225965` solo da un diff vacío, porque `5225965` ya está en `origin/main`. No sirve un worktree: comparte las referencias y movería el `origin/main` real |
| 5 | Si los hooks de la sesión se aplican a las herramientas del subagente | La doc no lo especifica; define si `guarda_secretos` protege al revisor |
| 6 | La inyección y los hooks (`!comando` ¿pasa por `PreToolUse`?) | No se asume; el diseño no se apoya en ello |

El resultado de cada comprobación se anota en `DECISIONES.md` y, si contradice una hipótesis,
se corrige el plan antes de seguir.
