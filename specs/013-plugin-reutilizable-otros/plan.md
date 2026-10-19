# Implementation Plan: Plugin reutilizable para otros equipos

**Branch**: `013-plugin-reutilizable-otros` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/013-plugin-reutilizable-otros/spec.md` (aprobada en `acf52f8`)

## Summary

El plugin `guardas-y-revision` vive en `plugins/guardas-y-revision/` y el marketplace
`piezas-reutilizables` en `.claude-plugin/marketplace.json`, en la raíz del repositorio. Empaqueta:
- **la guarda de datos con forma real del #3**: se **mueve** al plugin y queda como su única fuente,
  autocontenida;
- **el subagente revisor y su skill**: versiones genéricas de las del #4, con un script de
  contexto propio, sin `veredicto`.

Este repositorio sigue registrando la guarda en `.claude/settings.json`, ahora apuntando al script
del plugin, y deshabilita el plugin con `enabledPlugins`. Así la guarda corre una sola vez aunque
alguien instale el plugin a nivel de usuario.

La instalación se prueba con la CLI en un repositorio temporal, y las piezas con `claude -p` y
Haiku. Lo que exija la interfaz queda con sus comandos exactos para la analista.

## Technical Context

**Language/Version**: Python 3.12 (solo la biblioteca estándar en el plugin), Markdown y JSON para
el manifiesto, el marketplace, el agente, la skill y `hooks.json`.

**Primary Dependencies**:
- Claude Code 2.1.295 o posterior (`onFailure`); se mide con 2.1.303;
- `uv` para ejecutar los scripts;
- `git` para el contexto de revisión.

**Storage**: N/A. La caché de plugins de Claude Code la gestiona la CLI.

**Testing**:
- pytest: `testpaths` gana `plugins`, y `pythonpath` gana `plugins/guardas-y-revision/hooks` y
  `plugins/guardas-y-revision/scripts`;
- ruff;
- `claude plugin validate --strict`;
- quickstart Q2–Q4 con la CLI y `claude -p --model haiku`.

**Target Platform**: Windows 11 (medido) y cualquier sistema donde corra Claude Code con `uv`.

**Project Type**: configuración y scripts de Claude Code (plugin y marketplace).

**Performance Goals**: la guarda sigue por debajo de su `timeout` de 10 s, como en el #3.

**Constraints**:
- el plugin es autocontenido (se copia a una caché);
- ningún término del proyecto en el plugin;
- la guarda está activa desde un clon limpio (principio II);
- la guarda se ejecuta una sola vez por acción.

**Scale/Scope**: unos 12 archivos nuevos en el plugin, 2 movidos, 4 tests del repositorio
adaptados o nuevos, `settings.json`, `pyproject.toml`, el README y DECISIONES.md.

## Constitution Check

*GATE: antes de la fase 0 y otra vez tras el diseño.* **Cumple la constitución, sin desviaciones.**

| Principio | Cómo se cumple |
|-----------|----------------|
| **I.1–I.5** | No aplica: el ticket no toca el sistema multiagente, los hooks del SDK ni el servidor MCP. |
| **II** | La protección de datos con forma real **sigue garantizada por un hook de Claude Code** registrado en la configuración versionada, activo desde un clon limpio sin instalar nada (R3). El plugin deshabilitado aquí no la reemplaza ni la duplica. El fallo cerrado se conserva (`onFailure: block`, y `ejecutar` bloquea ante cualquier error). |
| **III, IV, V y VI** | No aplican. |
| **VII** | Los tests generan los valores con forma real en tiempo de ejecución, como en el #3. `test_revision_repositorio.py` sigue recorriendo todo el repositorio, también `plugins/`. |
| **VIII** | Sin credenciales. La prueba con `claude -p` usa la sesión de la CLI de la analista, no `.env`. |
| **IX** | Issue #13, rama propia, spec, plan y tareas antes del código. **Es el principio que el ticket cumple**: «las piezas reutilizables se empaquetan en un plugin». |
| **X** | Tests junto al código: los genéricos dentro del plugin, junto a la guarda y el script; los propios del repositorio en `.claude/hooks/`. Ruff tras cada edición. Revisión y auditoría en `/abrir-pr`. |

**Auditoría de `/abrir-pr`**: las reglas I.1–I.5 **no aplican**, porque el diff no toca `src/`. El
auditor lo declara con su evidencia.

**Re-evaluación tras el diseño**: sin cambios. Lo que se apoya en documentación que no lo dice
explícitamente tiene su comprobación en el quickstart, con una alternativa que, si hiciera falta, se
declara como desviación:
- la línea `!` y el prefijo del agente: R4 y R7, comprobados en Q4;
- la confianza en `-p`: R8, comprobada en Q3.

## Decisiones (detalle en [research.md](research.md))

1. **Estructura (R1)**:
   - `plugins/guardas-y-revision/` con el manifiesto, el agente, la skill, `hooks/hooks.json`, los
     scripts y sus tests;
   - `.claude-plugin/marketplace.json` en la raíz, con `"source": "./plugins/guardas-y-revision"`;
   - nombres genéricos y sin `author`.
2. **FR-007, una sola fuente con el plugin en caché (R2)**:
   - `guarda_datos.py` y `detector_datos.py` se mueven al plugin con `git mv`;
   - lo que usaban de `comun` pasa a `base_guarda.py`, dentro del plugin;
   - `.claude/settings.json` ejecuta ese mismo archivo, así que no hay dos guardas que puedan
     divergir;
   - la copia de la caché es la distribución de una versión, no otra fuente.

   **Los tests del #3 se mueven junto al código**. Sus casos propios del proyecto (el enunciado y
   los identificadores ficticios) quedan en `.claude/hooks/test_guarda_datos_repositorio.py`,
   contra la misma guarda. Las unas 60 líneas que `base_guarda.py` repite de `comun.py` tienen un
   test de equivalencia.
3. **FR-009, convivencia (R3), opción B**:
   - el repositorio registra la guarda (protegido desde el clon, principio II);
   - el plugin no se habilita;
   - `enabledPlugins` lo pone a `false` en `.claude/settings.json`.

   **El plugin instalado a nivel de usuario**: el `false` del proyecto gana sobre el `true` del
   usuario (precedencia clave por clave), así que corre una sola vez. Solo un `true` en
   `settings.local.json` (local gana sobre proyecto) lo duplicaría: es el riesgo residual 1, con un
   mensaje duplicado y nunca menos protección.

   **Trade-off frente a la opción A** (el repositorio usa el hook del plugin):
   - A deja sin protección un clon recién hecho y aplica los cambios de la guarda solo tras
     `claude plugin update`;
   - B mantiene dos registros (`settings.json` y `hooks.json`), que un test obliga a ser
     equivalentes, y no usa la instalación real en este repositorio, lo que cubre el quickstart.

   **Test**: una sola ejecución por herramienta del matcher, el plugin a `false` y los dos
   registros equivalentes.
4. **`${CLAUDE_PLUGIN_ROOT}` en la skill (R4)**:
   - en `allowed-tools`, la sustitución está documentada;
   - en la línea `!`, la documentación dice «el contenido markdown», pero no nombra la línea.

   Se usa en las dos y se verifica en Q4. Si falla, se pasa a `${CLAUDE_SKILL_DIR}` con el script en
   la skill. Si también falla, la skill se ejecuta sin `fork` y lanza el agente con Agent; eso se
   declararía como desviación de FR-002.
5. **El matcher de GitHub (R5)**: una expresión general y anclada,
   `mcp__.+__(add_issue_comment|…)`, la misma en `hooks.json` y en `settings.json`. La guarda revisa
   cualquier `mcp__…` que le llegue.
   - Funciona aunque el servidor se llame distinto.
   - **Trade-off**: más revisión, nunca menos.
   - Se descartó dejarlo como requisito del README, porque falla en silencio.
6. **Contexto genérico (R6)**: `scripts/contexto_revision.py`, sin `veredicto` y con el mismo
   contrato de salida del #4.
   - La base de fusión sale de `origin/HEAD`, `origin/main`, `origin/master`, `main` o `master`.
   - Spec Kit es opcional: sin `specs/`, se escribe `Ticket: no aplica`, que no cuenta como
     contexto incompleto.
7. **Revisor y skill genéricos (R7)**:
   - la misma independencia, las mismas herramientas de solo lectura, el mismo formato y la misma
     línea `RESUMEN`;
   - la cobertura se describe en términos genéricos;
   - `agent: guardas-y-revision:revisor-codigo`, verificado en Q4, con `revisor-codigo` como
     alternativa.
8. **Prueba de instalación (R8)**: la fuente es un clon limpio de la rama en el scratchpad, y el
   destino, un repositorio git nuevo. Los comandos exactos están en el
   [quickstart](quickstart.md):
   - Q2: `validate --strict`, `marketplace add --scope local`, `install --scope local`,
     `list --json` y `details`;
   - Q3 y Q4: la guarda y la skill con `claude -p --model haiku`;
   - si la confianza impide cargar el plugin en `-p`: `--plugin-dir` en otro repositorio, más la
     Q6 pendiente de la analista en la interfaz;
   - **Q5, obligatoria**: en el clon limpio de la rama de Q1, `claude -p --model haiku` intenta
     escribir con `Write` el valor generado en disco. La escritura se bloquea y **cada resultado
     bloqueado lleva exactamente un `[guarda_datos]`**. Se cuentan los resultados de la
     herramienta en la traza `stream-json`, no las apariciones del texto. Eso demuestra que Claude
     Code dispara la guarda con el matcher nuevo y US3-2 (clon sin pasos manuales);
   - **qué cuenta como prueba en Q3 y Q5**: solo un resultado de la herramienta bloqueado con el
     mensaje de la guarda. Sin ese mensaje (por ejemplo, si el modelo se niega a copiar), el
     resultado no es concluyente y se repite con otro prompt o con `sonnet`, con dos intentos
     como máximo, anotados;
   - **las trazas** contienen el valor generado: se quedan en la carpeta temporal y se borran en
     la limpieza. A los documentos solo pasan conteos y la línea `RESUMEN`;
   - la limpieza.
9. **Entorno (R9)**: `uv run --no-project --python 3.12 --quiet` en forma exec, con `timeout` 10 y
   `onFailure: block`. El README pone los requisitos: Claude Code 2.1.295 o posterior, `uv` y
   `git`.
10. **Cambios declarados en la guarda (R10, FR-005)**:
    - el mensaje sin `CO-TV-0001`;
    - los docstrings sin rutas de specs;
    - el matcher y la revisión de las herramientas `mcp__…` generales.

    La guarda no leía rutas propias del repositorio.
11. **FR-004 (R11)**: un test con la lista de términos del proyecto, fuera del plugin, y otro que
    comprueba que la lista detecta cada término.
12. **Documentación**:
    - la sección «Plugin para otros equipos» del README, corta: las piezas, los requisitos, la
      instalación desde GitHub y desde una copia local, y la desinstalación;
    - un `README.md` genérico dentro del plugin;
    - una entrada corta en DECISIONES.md.

## Riesgos residuales

1. **El plugin habilitado en `settings.local.json` de este repositorio**: la guarda corre dos veces
   y el mensaje sale duplicado. No baja la protección. Es una configuración personal.
2. **Lo no documentado** (la línea `!`, el prefijo en `agent:` y la confianza en `-p`): se comprueba
   en Q3 y Q4, con las alternativas de R4, R7 y R8.
3. **Un agente propio llamado `revisor-codigo` en el repositorio de otro equipo**: si hubiera que
   usar el nombre sin prefijo, ese agente ganaría.
4. **Las versiones del plugin**: otro equipo recibe los cambios de la guarda solo cuando se sube la
   `version` de `plugin.json` y ejecuta `claude plugin update`. Queda anotado en el README del
   plugin.
5. **`base_guarda.py` repite funciones de `comun.py`**: lo cubre el test de equivalencia, que solo
   prueba los casos escritos.

## Lo pendiente fuera de alcance

- Publicar en marketplaces externos y el versionado del plugin.
- El README completo y DECISIONES.md (#14).
- Empaquetar las demás guardas, el auditor, `/abrir-pr` o Spec Kit.

## Project Structure

### Documentation (this feature)

```text
specs/013-plugin-reutilizable-otros/
├── spec.md
├── plan.md
├── research.md          # R1–R11
├── data-model.md
├── contracts/plugin.md
├── quickstart.md        # Q1–Q6
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
.claude-plugin/marketplace.json                    # nuevo
plugins/guardas-y-revision/                        # nuevo (ver R1)
├── .claude-plugin/plugin.json
├── README.md
├── agents/revisor-codigo.md
├── skills/revisar-codigo/SKILL.md
├── hooks/{hooks.json, guarda_datos.py, detector_datos.py, base_guarda.py}
├── hooks/{test_guarda_datos.py, test_detector_datos.py, test_base_guarda.py}
├── scripts/{contexto_revision.py, test_contexto_revision.py}
└── test_plugin.py
.claude/settings.json                              # ruta del script, matcher general, enabledPlugins
.claude/hooks/test_configuracion.py                # adaptado (ruta y matcher)
.claude/hooks/test_guarda_datos_repositorio.py     # nuevo: casos propios del proyecto
.claude/hooks/test_plugin_repositorio.py           # nuevo: FR-004, FR-009 y equivalencia con comun
.claude/hooks/test_revision_repositorio.py         # sin cambios de fondo (importa del plugin)
pyproject.toml                                     # testpaths y pythonpath
README.md                                          # sección corta del plugin
DECISIONES.md                                      # entrada corta del #13
```

**Structure Decision**: el plugin en su propia carpeta, autocontenido. El repositorio solo lo
referencia desde `settings.json`, para la guarda, y desde el marketplace.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
