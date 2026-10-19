# Implementation Plan: Documentación de entrega: README y DECISIONES.md

**Branch**: `014-documentacion-entrega` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/014-documentacion-entrega/spec.md`

## Summary

Dejar el repositorio listo para la entrega con cinco piezas:

1. `DECISIONES.md` reescrito como resumen de ≤ 100 líneas a 90 columnas: tabla de las once
   necesidades con «Dónde», sección del Agent SDK, flujo de trabajo y límites conocidos, todo
   enlazado al detalle.
2. `docs/decisiones-detalle.md` con el `DECISIONES.md` de `f9e82d6` sin pérdida, más los
   añadidos (R5).
3. `docs/` como referencia en los cuatro textos de la puerta del PR y en su test (R6); la
   copia del plugin no cambia.
4. README con «Inicio rápido» al principio; el resto queda como referencia con dos ajustes (R7).
5. `docs/entrega.md`: lista de verificación, .zip, revisión del historial sin valores y
   guiones (R9–R11).

Un `test_documentacion.py` en la raíz comprueba la medida, la estructura, los enlaces, el
traslado sin pérdida y que los comandos de revisión nunca imprimen un valor
(`contracts/documentos.md`).

## Technical Context

**Language/Version**: Markdown; Python 3.12 para los tests (biblioteca estándar).

**Primary Dependencies**: pytest y ruff (ya en el proyecto); `git`, `bash` y `uv` para el
test de los bloques de revisión.

**Storage**: archivos del repositorio.

**Testing**: pytest; `test_documentacion.py` añadido a `testpaths`.

**Target Platform**: Windows 11 (equipo de la analista) y macOS/Linux para quien clone.

**Project Type**: documentación de un repositorio existente.

**Performance Goals**: «Inicio rápido» en menos de 5 minutos; `test_documentacion.py` en
pocos segundos, sin red.

**Constraints**: `DECISIONES.md` ≤ 100 líneas a 90 columnas; nada lee `.env`; sin cambios en
`src/` ni en las guardas; .zip ≤ 50 MB.

**Scale/Scope**: 14 entradas de partida (250 líneas), 11 necesidades, 15 tickets, 7 casos.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cumplimiento |
|-----------|--------------|
| I. Reglas de negocio | No aplica: no se toca `src/`. La auditoría de `/abrir-pr` dará I.1–I.5 «no aplica». |
| II. Garantizado vs. sugerido | No se crea ni se debilita ninguna regla. Lo verificable de la entrega (límite, enlaces, sin pérdida, sin valores) queda en tests, no en instrucciones. |
| III–VI | No aplican (sin cambios en el sistema). `DECISIONES.md` los resume y enlaza. |
| VII. Solo datos ficticios | Los documentos solo citan identificadores ficticios ya presentes; el test de los bloques genera la credencial al ejecutar. |
| VIII. Sin credenciales | Ningún paso lee ni muestra `.env`; el README dice crearlo desde `.env.example`; la revisión del historial nunca imprime el valor. |
| IX. Spec first y trazabilidad | Es el ticket de la entrega: issue #14, rama propia, spec/plan/tareas; `DECISIONES.md` traza todos los tickets. |
| X. Calidad y pruebas | Tests junto a lo que prueban (raíz y `.claude/hooks/`); ruff; la revisión y la auditoría van en `/abrir-pr`, que espera el enlace del video. |

**Resultado**: cumple, sin desviaciones. Reevaluado tras el diseño: igual.

## Decisiones

Detalle y alternativas descartadas en [research.md](research.md).

1. **Medida (R1)**: `textwrap.wrap(línea, 90)`, una línea vacía cuenta una; ≤ 100. Hoy, 686.
2. **Tests (R2)**: `test_documentacion.py` en la raíz, añadido a `testpaths`.
3. **Enlaces (R3)**: slugs de GitHub de los encabezados del detalle, comprobados por el test.
4. **Sin pérdida (R4)**: subsecuencia de las líneas de `git show f9e82d6:DECISIONES.md`;
   correcciones como notas tras la línea corregida.
5. **Añadidos (R5)**: índice de desviaciones (#10 D1–D4, #11 D1–D2, #12 D1–D3), límites del
   PR #29, sugerencias no atendidas por PR, mejora de latencia (T055 del #7), y dos notas
   (Project, espera de la categoría).
6. **Revisores (R6)**: `docs/` en los cuatro textos y en `REFERENCIA`. El plugin ya cubre
   `docs/*.md` con «la documentación en Markdown fuera de la configuración de Claude Code»:
   no cambia.
7. **README (R7, R8)**: «Inicio rápido» con cinco pasos; «Verificar el entorno» remite a
   «Pruebas»; las referencias a entradas de `DECISIONES.md` pasan al detalle; línea del
   marketplace con `marketplace add` y `extraKnownMarketplaces`, y la frase de visibilidad.
8. **.zip (R9)**: clon limpio desde GitHub y `tar.exe -a` (bsdtar del sistema); `zip -r` en
   macOS/Linux; listado y tamaño.
9. **Credenciales (R10)**: `git grep -l` por prefijos sobre `git rev-list --all` y el
   detector del proyecto sobre cada blob único; solo commit, archivo y tipo. Sondas: 0
   hallazgos (36 s y 80 s).
10. **Guiones (R11)**: funcionamiento ≤ 5 min y defensa ≤ 15 min (5 + 4 + 6) con el #7 como
    ticket de ejemplo.
11. **Project (R12)**: la corrección va en `DECISIONES.md` y como nota en el detalle; la spec
    del #2 no se toca.

## Tabla de las once necesidades (borrador para la implementación)

| N | Mecanismo | Dónde |
|---|-----------|-------|
| 1 | `CLAUDE.md` del proyecto con `@import` de la constitución; `.claude/` versionado | #1 · `CLAUDE.md` |
| 2 | `CLAUDE.local.md` y `settings.local.json` ignorados; la guarda impide que Claude escriba `settings.local.json` | #1, #3 · `.gitignore` |
| 3 | Regla con `paths: **/test_*.py` y `testpaths` | #1, #12 · `.claude/rules/tests.md` |
| 4 | Hook `PreToolUse` `guarda_spec_previa` | #3 · `.claude/hooks/guarda_spec_previa.py` |
| 5 | Hook `PreToolUse` `guarda_datos`, en el plugin | #3, #13 · `plugins/…/guarda_datos.py` |
| 6 | Denegaciones de permisos + hook `guarda_secretos` | #1, #3 · `.claude/settings.json` |
| 7 | Hook `PostToolUse` `formatear_python` (ruff) | #3 · `.claude/hooks/formatear_python.py` |
| 8 | Subagente `revisor-codigo` de solo lectura + skill con `context: fork` + puerta `guarda_pr` | #4 · `.claude/skills/revisar-codigo/` |
| 9 | Subagente `auditor-cumplimiento` + su skill; reglas delegadas | #4, #19 · `.claude/agents/auditor-cumplimiento.md` |
| 10 | Skill `siguiente-ticket`, comandos `/abrir-pr` y `/comentar-avance` (`.claude/commands/`), hooks de Spec Kit, MCP de GitHub limitado por el hook `PreToolUse` `guarda_mcp_github` (`projects_write` solo con `update_project_item`) y workflows nativos del Project, con la corrección de los PR | #2, #3 · `.claude/skills/siguiente-ticket/`, `.claude/hooks/guarda_mcp_github.py` |
| 11 | Plugin `guardas-y-revision` y marketplace en el repositorio | #13 · `.claude-plugin/marketplace.json` |

La sección del Agent SDK traza #5 a #12. Cada mecanismo se contrasta con el archivo antes de
escribirlo, y cada fila cita el tipo exacto de cada pieza tal como está en el repositorio
(regla, hook, skill, comando, subagente, MCP, plugin). Corrección de la analista al aprobar el
plan: `/abrir-pr` y `/comentar-avance` son comandos, no skills.

## Project Structure

### Documentation (this feature)

```text
specs/014-documentacion-entrega/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/documentos.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Archivos que cambia el ticket

```text
DECISIONES.md                         # reescrito como resumen
README.md                             # «Inicio rápido» + dos ajustes
docs/decisiones-detalle.md            # nuevo: partida sin pérdida + añadidos
docs/entrega.md                       # nuevo: lista, .zip, credenciales, guiones
test_documentacion.py                 # nuevo
pyproject.toml                        # testpaths
.claude/agents/revisor-codigo.md      # docs/ como referencia
.claude/agents/auditor-cumplimiento.md
.claude/skills/revisar-codigo/SKILL.md
.claude/skills/auditar-cumplimiento/SKILL.md
.claude/hooks/test_agentes_skills.py  # REFERENCIA
```

**Structure Decision**: los documentos de la entrega en la raíz (los que pide el enunciado) y
en `docs/` (detalle y entrega); el test en la raíz, junto a ellos.

## Riesgos residuales

1. El slug de GitHub se reproduce en el test; si GitHub cambiara su algoritmo, un enlace
   podría romperse sin que el test falle.
2. El test sin pérdida se omite en un clon superficial o sin `f9e82d6`.
3. El test de los bloques de revisión necesita `bash`; sin él, se omite con el motivo.
4. Los tiempos y costes citados son de mediciones anteriores; el «Inicio rápido» lo
   cronometra la analista (SC-001).
5. La frase de visibilidad y el enlace del video dependen de la analista, y `/abrir-pr`
   espera al enlace.

## Complexity Tracking

Sin violaciones de la constitución.
