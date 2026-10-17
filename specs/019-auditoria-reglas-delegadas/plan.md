# Implementation Plan: Auditoría: reglas delegadas a otro ticket y uv.lock como referencia

**Branch**: `019-auditoria-reglas-delegadas` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/019-auditoria-reglas-delegadas/spec.md` (issue #19)

## Summary

Corregir dos defectos de la puerta del #4 que bloquearon el `/abrir-pr` del #5, **sin tocar
el código de la puerta**: solo el texto de los dos subagentes y sus dos skills, más un test
que impide que las copias diverjan.

- **Regla delegada** (R1, R2): la sección `Cuándo aplica una regla` pasa a tener cinco pasos
  y se escribe **igual** en el agente y la skill del auditor. Una regla que la spec delega con
  número de ticket (`#N`) sale `no aplica` con esa razón, incluso si el cambio solo aporta
  datos o clasificación que la regla usa; si el diff la contradice, `incumple` (bloqueante); y
  si borra o debilita el código o el test de cualquier regla, esta aplica y, sin evidencia
  vigente, es bloqueante. Citarla sin número sigue aplicando (FR-004).
- **`uv.lock` como referencia** (R3): pasa de "se lee por secciones" a la lista de archivos de
  referencia en el bloque `Qué cuenta para la cobertura` de los cuatro archivos.
- **Test de coherencia** (R4, FR-013): en `test_agentes_skills.py`, compara el bloque de
  cobertura de los cuatro archivos y la regla de aplicabilidad del auditor, y falla si
  difieren. SC-004 pasa a ser código.
- **Validación con sesiones reales** (R6, R7): en clones desechables fuera del repositorio,
  incluida la rama 005 (con `git merge --no-ff` de esta rama y la línea 161 de su spec
  corregida a «I.1, I.2 e I.3 … del ticket #7»). La corrección real de la rama 005 se hace al
  volver al #5, y SC-003 (`uv.lock`) se comprueba con el `/abrir-pr` real del #5.

No se modifican `veredicto.py`, `guarda_pr.py` ni `preparar_revision.py`, ni sus tests
(FR-009).

## Technical Context

**Language/Version**: Python 3.12 gestionado con uv (solo el test); el resto es Markdown con
frontmatter.

**Primary Dependencies**: ninguna nueva. El test usa pytest y la biblioteca estándar, y reutiliza
los cargadores de `test_agentes_skills.py`.

**Storage**: archivos versionados (`.claude/agents/`, `.claude/skills/`); sin datos nuevos.

**Testing**: pytest junto al módulo (`.claude/hooks/test_agentes_skills.py`); ruff para formato
y lint. El comportamiento del auditor se valida con sesiones reales (quickstart Q3 a Q5).

**Target Platform**: Claude Code en Windows (validación manual solo en Windows, como #3 y #4).

**Project Type**: configuración del entorno de Claude Code (agentes, skills y tests).

**Performance Goals**: N/A. No cambia el tamaño relevante del contexto de la revisión.

**Constraints**: FR-009 (tres archivos y sus tests intactos); FR-010 (tests existentes en verde
sin editarlos, salvo ampliar `REFERENCIA`); el frontmatter de agentes y skills no cambia
(herramientas de solo lectura, `agent:`, `allowed-tools`).

**Scale/Scope**: 4 archivos de texto, 1 archivo de tests y 1 entrada de `DECISIONES.md`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Verificación en este plan | Estado |
|-----------|--------|---------------------------|--------|
| I. Reglas de negocio | Indirecto | No implementa reglas: afina **cuándo se audita** cada una. No cambia el texto del principio I ni los cuatro estados. Una regla delegada que se contradice sigue bloqueando (R2, FR-003, FR-012). | Cumple |
| II. Garantizado vs. sugerido | Sí | La puerta que bloquea el PR sigue siendo el hook `guarda_pr` y `veredicto.py`, sin cambios. Lo que se afina es la instrucción del auditor, que es la parte "guiada" del mecanismo; por eso la **igualdad del texto** se garantiza con un test (FR-013, R4) y no por convención. Límite declarado: el test garantiza el texto, no la interpretación del modelo (R6). | Cumple, con el límite declarado |
| III. Arquitectura de agentes | Sí | Los agentes siguen con `tools: Read, Grep, Glob`, contexto explícito y sin lanzar otros subagentes: el frontmatter no se toca y sus tests lo siguen verificando. | Cumple |
| IV. Herramientas y servidor MCP | No | No toca el servidor ni las herramientas de decisión. | N/A |
| V. Escalamiento | No | Fuera de alcance. | N/A |
| VI. Transparencia en la interfaz | No | Se refiere a la interfaz de chat. | N/A |
| VII. Solo datos ficticios | Sí | Los repositorios y datos de prueba del quickstart son inventados (categorías, comercios y funciones de ejemplo). El test construye textos sintéticos. | Cumple |
| VIII. Sin credenciales | Sí | No se añaden lecturas ni herramientas; no hay valores sensibles en ningún artefacto. | Cumple |
| IX. Spec first y trazabilidad | Sí | Issue #19, rama propia, spec, plan y tareas antes de tocar los archivos. Corrige #4 y desbloquea #5. | Cumple |
| X. Calidad y pruebas | Sí | Test nuevo con pytest junto al módulo; ruff tras la edición; revisión independiente y auditoría antes del PR. **La auditoría de este ticket debe dar las cinco reglas `no aplica` con razón**, porque no toca código de producción (la spec no delega nada). | Cumple |
| Restricciones técnicas | Sí | Python 3.12 con uv, pytest y ruff; sin dependencias nuevas; documentación en español. | Cumple |

**Sin desviaciones.** Riesgos residuales; los dos primeros van a una viñeta de la entrada 5 de
`DECISIONES.md` (R8):

1. El auditor no consulta GitHub: una spec que delegue a un ticket inexistente o que no cubra
   la regla deja esa regla sin auditar hasta que el ticket receptor la asigne a sí mismo.
2. El comportamiento del auditor depende del modelo; el test garantiza que el texto está
   escrito igual, no que se interprete bien. Lo acota el quickstart (Q3 a Q5).
3. `uv.lock` sigue sin marca `[referencia]` en la lista del contexto, porque
   `preparar_revision.py` queda fuera del alcance; la exención vive en el texto (R3).

**Re-evaluación tras el diseño**: se mantiene. El diseño no añade archivos de código, estados ni
dependencias; el único código nuevo es un test.

## Project Structure

### Documentation (this feature)

```text
specs/019-auditoria-reglas-delegadas/
├── plan.md                         # Este archivo
├── research.md                     # R1 a R8, con los límites declarados
├── data-model.md                   # reglas, delegación, referencia y archivos de la puerta
├── quickstart.md                   # Q1 a Q6; SC-003 se comprueba en el /abrir-pr del #5
├── contracts/
│   ├── texto-de-la-puerta.md       # el texto exacto de las dos secciones
│   └── test-coherencia.md          # el test que compara los cuatro archivos
├── checklists/requirements.md
└── tasks.md                        # lo crea /speckit-tasks (no este comando)
```

### Source Code (repository root)

```text
.claude/
├── agents/
│   ├── auditor-cumplimiento.md     # sección «Cuándo aplica una regla» nueva; cobertura con uv.lock
│   └── revisor-codigo.md           # cobertura con uv.lock
├── skills/
│   ├── auditar-cumplimiento/SKILL.md  # sección nueva, paso 3 remite a ella; cobertura con uv.lock
│   └── revisar-codigo/SKILL.md        # cobertura con uv.lock
└── hooks/
    └── test_agentes_skills.py      # sección de coherencia (función `seccion` y sus pruebas)
DECISIONES.md                       # una viñeta en la entrada 5 (sin entrada nueva)
```

**Structure Decision**: no hay estructura nueva. Todo ocurre en los cuatro archivos de la
puerta, en el test que ya los prueba y en `DECISIONES.md`. Quedan **intactos** `veredicto.py`,
`guarda_pr.py`, `preparar_revision.py` y sus tests (FR-009, SC-005).

## Orden de implementación

1. **Tests primero** (`rules/tests.md`): la sección de coherencia y la ampliación de `REFERENCIA`
   fallan con los textos actuales (rojo).
2. **Bloque de cobertura** en los cuatro archivos (R3): `uv.lock` a referencia.
3. **Sección de aplicabilidad** en el agente y la skill del auditor y el paso 3 de la skill
   (R1, R2).
4. **Suite en verde** con ruff (Q1), y Q2 (el test detecta una diferencia).
5. **`DECISIONES.md`**: una viñeta en la entrada 5 con el criterio de la regla delegada y los
   dos límites (R8).
6. **Validación manual** Q3 a Q6 en clones desechables y anotación de resultados. SC-003 se
   anota como verificación pendiente del `/abrir-pr` real del #5.
7. `/abrir-pr`: la revisión independiente y la auditoría de **este** ticket; ningún commit
   después de la revisión.
