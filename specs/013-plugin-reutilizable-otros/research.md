# Research: Plugin reutilizable para otros equipos (#13)

Fuentes: la documentación oficial de Claude Code, consultada el 2026-10-19 (las URL van en cada
decisión), la ayuda de la CLI 2.1.303 (`claude plugin --help` y sus subcomandos) y la lectura del
código de `main` (`acf52f8`). Lo que la documentación no dice se marca **no documentado** y se
comprueba en el quickstart (Q3 y Q4), con su alternativa.

## R1. Estructura: plugin en `plugins/guardas-y-revision/` y marketplace en la raíz

**Decisión**:

```text
.claude-plugin/marketplace.json            # marketplace «piezas-reutilizables»
plugins/guardas-y-revision/
├── .claude-plugin/plugin.json             # nombre, versión 1.0.0, descripción
├── README.md                              # uso del plugin, genérico
├── agents/revisor-codigo.md
├── skills/revisar-codigo/SKILL.md
├── hooks/hooks.json                       # PreToolUse → guarda_datos.py
├── hooks/guarda_datos.py                  # la guarda (única fuente, R2)
├── hooks/detector_datos.py                # el detector (única fuente, R2)
├── hooks/base_guarda.py                   # lo que la guarda usaba de comun (R2)
├── hooks/test_*.py                        # tests genéricos de la guarda y el detector
├── scripts/contexto_revision.py           # contexto de la skill (R6)
├── scripts/test_contexto_revision.py
└── test_plugin.py                         # manifiesto, hooks.json, agente y skill
```

- **Nombre del plugin**: `guardas-y-revision`. Dice lo que trae y no nombra el proyecto (FR-001).
- **Nombre del marketplace**: `piezas-reutilizables`.
- **Versión**: `1.0.0`.
- **Manifiesto**: sin `author` (FR-001, sin datos personales). El marketplace exige `owner.name`
  (create-marketplace: «The file requires a `name`, an `owner`, and a `plugins` array»): se pone
  un nombre de equipo genérico, no una persona.
- **Fuente**: `"source": "./plugins/guardas-y-revision"`, que se resuelve desde la raíz del
  marketplace, no desde `.claude-plugin/` (marketplace-reference).

**Por qué la carpeta `scripts/` aparte**: `contexto_revision.py` no es un hook. Lleva otro nombre
que el `preparar_revision.py` del repositorio porque los dos directorios están en el `pythonpath`
de pytest, y dos módulos con el mismo nombre chocarían.

**Alternativas**:
- El plugin en la raíz, con `plugin.json` en `.claude-plugin/` junto al marketplace: mezcla el
  repositorio con el plugin, y el plugin copiaría a la caché todo el repositorio.
- Un repositorio aparte para el plugin: fuera de alcance; el issue pide el marketplace en este.

## R2. FR-007: una sola fuente de la guarda, dentro del plugin

**El problema**: un plugin instalado se copia a `~/.claude/plugins/cache/<marketplace>/<plugin>/<versión>/`.
Los archivos fuera de su carpeta no se copian y una ruta que sale de ella se rechaza (loading:
«Files outside the plugin directory aren't copied»; «A path that points outside the plugin as
written, such as `../shared-utils`»). Por eso el plugin no puede importar el `comun.py` del
repositorio (`guarda_datos.py:19`).

**Decisión**: la guarda completa **se mueve** al plugin y queda como su única fuente.
- `git mv` de `.claude/hooks/guarda_datos.py` y `.claude/hooks/detector_datos.py` a
  `plugins/guardas-y-revision/hooks/`.
- Lo que la guarda usaba de `comun` (`leer_entrada`, `raiz`, `cwd`, `normalizar_ruta`,
  `bloquear`, `flujos_utf8` y `ejecutar`) pasa a `plugins/guardas-y-revision/hooks/base_guarda.py`,
  sin otras dependencias que la biblioteca estándar.
- **Este repositorio ejecuta ese mismo archivo**: `.claude/settings.json` registra
  `${CLAUDE_PROJECT_DIR}/plugins/guardas-y-revision/hooks/guarda_datos.py` (R3). Con
  `uv run --no-project script.py`, `sys.path[0]` es la carpeta del script, así que la guarda
  importa su `detector_datos` y su `base_guarda`, nunca el `comun` del repositorio.
- **No hay dos guardas que comparar**: el detector, el fallo cerrado, el mensaje con tipo y línea,
  la ruta relativa y los textos por herramienta son el mismo código en este repositorio y en el
  plugin. La copia de la caché es la distribución de una versión, no una segunda fuente.

**Tests (FR-007 y SC-004)**:
- `test_detector_datos.py` y `test_guarda_datos.py` del #3 se mueven junto al código, a
  `plugins/guardas-y-revision/hooks/`. Se quitan las partes propias del proyecto (FR-004).
- Esas partes no se pierden: pasan a `.claude/hooks/test_guarda_datos_repositorio.py`, que prueba
  la misma guarda del plugin. Son:
  - el ejemplo del enunciado no se bloquea (`docs/enunciado.md`);
  - los identificadores ficticios de este proyecto no son hallazgos.
- **Ningún test del #3 se borra ni se debilita**: cada uno queda en uno de los dos archivos, y la
  tabla de T-adaptación de `tasks.md` dice adónde fue.
- `test_revision_repositorio.py` sigue importando `test_guarda_datos` y `detector_datos`, ahora
  desde el `pythonpath` del plugin.

**Duplicación que queda**: `base_guarda.py` repite unas 60 líneas de `comun.py`, que las demás
guardas del repositorio siguen usando. Un test de `.claude/hooks/` ejecuta las dos
implementaciones de `normalizar_ruta`, `raiz`, `cwd`, `bloquear` y `ejecutar` con los mismos
casos y falla si difieren.

**Alternativas**:
- **Copia generalizada en el plugin y un test de equivalencia**: dos fuentes que mantener. Además,
  el plugin necesitaría una copia de `comun.py` (729 líneas, con referencias a specs de este
  proyecto) o una reescritura. El test solo cubriría los casos que alguien escriba.
- **`comun.py` importa `base_guarda` del plugin**: elimina también la duplicación de las
  funciones, pero hace que todas las guardas del repositorio dependan de `sys.path` manipulado
  hacia la carpeta del plugin. Es más riesgo que unas 60 líneas probadas por equivalencia.
- **Symlink del plugin al repositorio**: la documentación rechaza «A symlink that leads outside
  the plugin», y en Windows los symlinks exigen permisos.

## R3. FR-009: convivencia. El plugin no se habilita aquí, y el proyecto lo deshabilita

**Hechos**:
- **Deduplicación**: «If you define the same handler in more than one settings file, it runs
  once. A plugin's or skill's copy of the same handler stays separate» (hooks). Es decir, la
  guarda del proyecto y la del plugin **se ejecutarían las dos**.
- **Precedencia de `enabledPlugins`**: se fusiona clave por clave, y gana la fuente de mayor
  precedencia que nombra el plugin. El orden, de menor a mayor, es `--add-dir`, `user`, `project`,
  `local`, `flag` y `managed` (loading: «These sources merge key by key…»).

**Decisión (opción B)**:
1. `.claude/settings.json` sigue registrando la guarda de datos con su `PreToolUse`, ahora
   apuntando al script del plugin dentro del repositorio (R2).
2. El plugin **no se habilita** en este repositorio: ni `extraKnownMarketplaces` ni un
   `enabledPlugins` a `true`.
3. `.claude/settings.json` declara `"enabledPlugins": {"guardas-y-revision@piezas-reutilizables": false}`.

**El caso del plugin instalado a nivel de usuario**: la analista instala el plugin en
`~/.claude/settings.json` para usarlo en otros proyectos y abre este. El `false` del proyecto gana
sobre el `true` del usuario, así que el plugin no carga aquí y la guarda corre una vez.

**Lo que no cubre (riesgo residual 1)**: un `true` en `.claude/settings.local.json` de este
repositorio (`--scope local`), que es personal y no versionado, gana sobre el proyecto. El efecto
sería un mensaje de bloqueo duplicado, **nunca menos protección**. Se declara en DECISIONES.md.

**Trade-off**:

| | **B (elegida)**: el repositorio registra la guarda y el plugin se deshabilita | **A**: el repositorio usa el hook del plugin y deja de registrar el suyo |
|---|---|---|
| Clon limpio | Protegido sin pasos (principio II, FR-009). | Sin protección hasta añadir el marketplace, instalar el plugin y confiar en la carpeta. Viola II. |
| Cambiar la guarda | Se aplica al instante. | Se aplica solo tras subir la versión y `claude plugin update`, porque el plugin corre desde la caché. |
| Fuente del código | Una (R2). | Una. |
| Registro del hook | Dos: `settings.json` y `hooks.json`. Un test exige que el matcher, el `timeout`, el `onFailure` y los argumentos sean iguales, salvo la variable de la raíz. | Uno. |
| Usa la instalación real del plugin | No en este repositorio. Lo cubre la prueba de instalación (quickstart Q2–Q4). | Sí. |

**Test (SC-003)**, en `.claude/hooks/test_plugin_repositorio.py`, con la configuración versionada:
- para cada herramienta que revisa la guarda (`Write`, `Edit`, `NotebookEdit`, `Bash`,
  `PowerShell` y los ocho nombres de publicación en GitHub), exactamente una entrada de
  `PreToolUse` cuyo matcher la acepta ejecuta `guarda_datos.py`;
- `enabledPlugins` tiene el plugin a `false`, y ningún `extraKnownMarketplaces` lo trae;
- el registro de `settings.json` y el de `hooks.json` son equivalentes (tabla de arriba).

**Alternativas**:
- **A**: descartada por la tabla.
- **Registrar la guarda solo en `hooks.json` y cargar el plugin con `--plugin-dir`**: exige un
  argumento al arrancar Claude Code y no es configuración versionada.

## R4. `${CLAUDE_PLUGIN_ROOT}` en la skill: supuesto a verificar

**Lo documentado** (skills): «In a plugin skill, Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}`
and `${CLAUDE_PLUGIN_DATA}` in the same two places»: «the skill's markdown content, and Bash
rules in the allowed-tools frontmatter».
- **`allowed-tools`**: está documentado.
- **La línea `!`**: forma parte del contenido markdown, pero la documentación **no la nombra**.
- **Windows**: «On Windows, the substituted paths use forward slashes» (manifest-reference).
- **Bash**: las variables **no** están en el entorno de los comandos que Claude ejecuta con Bash.
  Por eso la línea `!` depende de la sustitución en el texto, no de `$CLAUDE_PLUGIN_ROOT` en la
  shell.

**Decisión**: el `SKILL.md` del plugin usa la misma forma en la línea `!` y en `allowed-tools`,
con la ruta entre comillas por si la raíz tiene espacios:

```text
!`uv run --no-project --python 3.12 --quiet "${CLAUDE_PLUGIN_ROOT}/scripts/contexto_revision.py"`
```

**Verificación**: Q4 del quickstart. La skill ejecutada en el repositorio de prueba tiene que
mostrar la marca `CONTEXTO DE REVISIÓN` en el contexto del subagente.

**Alternativas, en este orden, si Q4 falla**:
1. **`${CLAUDE_SKILL_DIR}`**, con el script dentro de la carpeta de la skill. Su sustitución está
   documentada en los mismos dos sitios, y la línea `!` tampoco se nombra.
   - **Trade-off**: el script queda dentro de la skill, no en `scripts/`.
2. **Sin `context: fork`**: la skill se ejecuta en la sesión principal. Ella corre el script con
   Bash (la ruta ya sustituida en el texto, lo que sí está documentado) y lanza el subagente con
   la herramienta Agent, pasándole la salida.
   - **Trade-off**: el contexto lo transcribe el modelo en vez de inyectarse antes del subagente,
     y se pierde la garantía del #4 de que el revisor ve exactamente la salida del script.
   - Se declararía como «Desviación justificada» de FR-002.

## R5. El matcher de GitHub: una expresión general, anclada

**El problema**: hoy el matcher nombra `mcp__github__add_issue_comment` y otros siete, y la guarda
solo revisa las herramientas que empiezan por `mcp__github__`. En otro equipo, el mismo servidor
puede llamarse distinto; por ejemplo, el de un plugin queda como `mcp__plugin_github_github__…`.
Si la guarda depende de un requisito del README que nadie lee, se pierde la protección sin que nadie
lo note.

**Decisión**: expresión general y anclada, la misma en `hooks.json` y en `settings.json`:

```text
^(Write|Edit|NotebookEdit|Bash|PowerShell|mcp__.+__(add_issue_comment|update_issue_comment|create_pull_request|update_pull_request|issue_write|add_reply_to_pull_request_comment|pull_request_review_write|add_comment_to_pending_review))$
```

- **En la guarda**: `textos()` revisa los valores de texto de **cualquier** herramienta `mcp__…`
  que le llegue. Quién llega lo decide el matcher.
- **Las anclas**: hacen que el resultado sea el mismo tanto si Claude Code compara el patrón entero
  como si busca una subcadena. Q3 comprueba en el repositorio de prueba que el matcher dispara
  con `Write`.
- **Trade-off**: la guarda puede revisar herramientas de otro servidor con los mismos nombres. Eso
  es más revisión, nunca menos.

**Cambio declarado respecto al #3** (FR-005): el test `test_matchers_son_listas_de_nombres_exactos`
de `test_configuracion.py` admite esta única expresión para la guarda de datos. Las demás guardas
siguen con listas de nombres exactos.

**Alternativa**: dejar `mcp__github__` y ponerlo como requisito en el README. Descartada porque
falla en silencio.

## R6. Script de contexto genérico: `contexto_revision.py`

**Decisión**: un script nuevo, solo con la biblioteca estándar, que sigue el contrato del #4 en la
salida (marca, `CONTEXTO INCOMPLETO`, umbral de 14 500 bytes, lista agrupada y diff solo si cabe,
siempre con código 0), sin `veredicto`, sin `comun` y sin `/abrir-pr`.

**Base de fusión**: la primera referencia que exista entre:
1. la rama a la que apunta `refs/remotes/origin/HEAD`;
2. `origin/main`;
3. `origin/master`;
4. `main`;
5. `master`.

Se imprime `Base: <sha> (git merge-base HEAD <referencia>)`. Si no hay ninguna, sale
`CONTEXTO INCOMPLETO`.

**Spec Kit, opcional**:
- **Si existe `specs/`**: se aplica la regla del #4 (rama `NNN-nombre` y una sola carpeta
  `specs/NNN-*`), y su fallo es `CONTEXTO INCOMPLETO`.
- **Si no existe**: `Ticket: no aplica (el repositorio no usa una carpeta specs/)`, que no es
  incompleto (FR-006).
- **La constitución**: `.specify/memory/constitution.md` si existe; si no, `Constitución: no aplica`.

**Por qué no se reutiliza `preparar_revision.py`**: depende de `veredicto` y de `origin/main`, y es
parte de la puerta de `/abrir-pr`. La analista confirmó que el repositorio conserva el suyo.

## R7. Subagente y skill genéricos

**Decisión**: el subagente y la skill del plugin son copias editadas de las del #4. Conservan:
- la independencia;
- las herramientas `Read`, `Grep` y `Glob`;
- el formato de los hallazgos;
- los valores sensibles por tipo y ubicación;
- el plan de lectura;
- la línea `RESUMEN`.

Cambian:
- **Lo que cuenta**: el código, la configuración y los tests del cambio. Son referencia la carpeta
  de specs del ticket, la documentación en Markdown y los archivos generados (lockfiles).
- **Las convenciones**: las de `CLAUDE.md` y `.claude/rules/` del repositorio revisado, si existen.
- **Sin ticket**: si el contexto dice `Ticket: no aplica`, se revisan la calidad y los errores, el
  reporte lo dice y la cobertura no baja.
- **Fuera**: las menciones a `/abrir-pr`, `src/**` y `DECISIONES.md`.

**Nombre del agente en la skill**: `agent: guardas-y-revision:revisor-codigo`.
- Lo documentado: los agentes de plugin se llaman `<plugin>:<nombre>` (components), pero que
  `agent:` acepte el prefijo **no está documentado**.
- Q4 lo comprueba. Si falla, se usa `agent: revisor-codigo`. En un repositorio que tenga un agente
  propio con ese nombre, ese ganaría (riesgo residual 3).

## R8. Prueba de instalación con la CLI (FR-010)

**Hechos**:
- **La CLI**: `claude plugin marketplace add <ruta|owner/repo[@ref]>`,
  `claude plugin install <plugin>@<marketplace> --scope local` y `claude plugin validate`, todos
  sin interfaz (cli-reference: «Most plugins install without a prompt»).
- **La confianza**: un plugin de proyecto o local «loads only after the same trust check …
  Trusting a parent folder or running with `-p` isn't enough» (loading). La carpeta de prueba,
  recién creada, no es de confianza. Es probable que `claude -p` no cargue el plugin hasta que
  alguien confíe en ella en la interfaz.

**Decisión**: tres niveles; el detalle y los comandos están en el quickstart.
1. **Instalación sin interfaz** (Q2):
   - un clon limpio de la rama como fuente del marketplace, para que solo cuente lo commiteado;
   - un repositorio git nuevo en el scratchpad;
   - `validate`, `marketplace add --scope local`, `install --scope local`, `list --json` y
     `details`.
2. **Las piezas con `claude -p` y Haiku** (Q3 y Q4), primero con el plugin instalado.
   - **Si no carga por la confianza**: las mismas comprobaciones en otro repositorio de prueba con
     `--plugin-dir`. Eso prueba las piezas, pero no la carga desde la instalación.
   - **Lo que exige la interfaz queda pendiente de la analista**, con sus comandos exactos (Q6),
     marcado como pendiente y no como hecho.
3. **Limpieza**: `claude plugin uninstall` y `claude plugin marketplace remove`, y se borra la
   carpeta temporal. Se toca el registro de marketplaces del usuario y se deja como estaba.

**Ajustes de la analista al plan**:
- **Q5 es obligatoria**: en el clon limpio de la rama, la guarda se dispara con el matcher nuevo y
  cada resultado bloqueado de `Write` lleva un solo `[guarda_datos]`.
- **En Q3 y Q5 solo cuenta el mensaje de la guarda en la traza**: sin él, el resultado no es
  concluyente, con dos intentos como máximo.
- **Las trazas no salen de la carpeta temporal**: a los documentos solo pasan conteos.

**Coste**: de tres a cinco ejecuciones con Haiku, del orden de céntimos.

**Fuente GitHub**: el repositorio es **privado** y la rama no se sube hasta `/abrir-pr`. El README
documenta la fuente `anahernandez0814/due-diligence-pasarela-austral`, que sirve tras el merge y
pide acceso al repositorio; la prueba usa la copia local.

## R9. Requisitos del entorno del plugin

**Decisión**: el hook y el script de contexto se ejecutan como las guardas del repositorio:
`"command": "uv", "args": ["run", "--no-project", "--python", "3.12", "--quiet", "${CLAUDE_PLUGIN_ROOT}/…"]`.

- **Forma exec**: documentada, con `${CLAUDE_PLUGIN_ROOT}` sustituido en `command` y en cada
  `args`.
- **Windows**: «exec form requires `command` to resolve to a real executable such as a `.exe`».
  `uv` se instala como `uv.exe`.
- **El hook**: `"timeout": 10` y `"onFailure": "block"`, que exige Claude Code 2.1.295 o posterior.
  Si `uv` falta o el script falla, la acción se bloquea.
- **Requisitos del README**: Claude Code 2.1.295 o posterior, `uv` en el `PATH` y `git`. Python 3.12
  lo resuelve `uv`.

**Alternativa**: `python3` o `py`. Su nombre y su versión varían entre sistemas, y en Windows
`python3` puede ser el alias de la Store.

## R10. Generalización del hook del #3 (FR-005)

**Cambios en la guarda**, que se aplican también en este repositorio porque es la misma fuente:
1. El mensaje de bloqueo deja el ejemplo `CO-TV-0001`:
   «Dato con forma real bloqueado: {hallazgos}. Usa valores claramente ficticios o genera el
   valor en la prueba.»
2. Los docstrings ya no remiten a `specs/003-…`; describen el comportamiento.
3. La guarda revisa cualquier herramienta `mcp__…` que le llegue (R5).

**Lo que no cambia**: la guarda no lee rutas propias del repositorio. La raíz la toma de
`CLAUDE_PROJECT_DIR` o del `cwd` de la entrada, que da Claude Code en cualquier proyecto.

**Tests**: los que fijaban el texto del mensaje con `CO-TV-0001` (`test_guarda_datos.py:180` y
`:194`) pasan a fijar el texto nuevo. Los que comprueban que `CO-TV-0001` no se detecta se quedan
en `.claude/hooks/test_guarda_datos_repositorio.py`.

## R11. FR-004: la lista de términos del proyecto

**Decisión**: `.claude/hooks/test_plugin_repositorio.py` recorre `git ls-files plugins/` y el
`marketplace.json`, y falla con `archivo:línea:término` si aparece alguno de estos patrones (sin
distinguir mayúsculas):
- **Nombres**: `pasarela austral`, `due diligence` y `due-diligence`.
- **Identificadores**: los que siguen la forma de los de este proyecto, `CO-[A-Z]{2}-\d{4}`.
- **Rutas**: `src/`, `specs/0`, `DECISIONES`, `.claude/hooks`, `docs/enunciado`, `.mcp.json` y
  `servidor_mcp`.
- **Comandos y skills propios**: `/abrir-pr`, `/siguiente-ticket`, `comentar-avance`,
  `auditar-cumplimiento` y `veredicto`.
- **Variables**: `CLAUDE_PROJECT_DIR` en `hooks.json` y en el `SKILL.md`, donde solo vale
  `CLAUDE_PLUGIN_ROOT`.
- **Tickets**: el patrón `#\d+`.

`CLAUDE_PROJECT_DIR` sí puede aparecer en `base_guarda.py`, que lo lee para mostrar rutas
relativas (FR-003).

Un segundo test comprueba que la lista detecta cada término en un archivo de muestra; si no, una
lista rota pasaría en verde.

**Excepción**: el `marketplace.json` puede nombrar el repositorio de GitHub en su
`metadata.homepage`. Se decide no ponerlo, y así la lista se aplica también al marketplace.
