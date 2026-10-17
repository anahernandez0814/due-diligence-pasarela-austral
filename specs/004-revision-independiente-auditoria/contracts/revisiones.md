# Contrato: subagentes, skills y formato del reporte

Entidades en [data-model.md](../data-model.md); decisiones y fuentes en
[research.md](../research.md) (R1 a R7).

## Subagentes (`.claude/agents/`)

| | `revisor-codigo` | `auditor-cumplimiento` |
|---|---|---|
| `tools` | `Read, Grep, Glob` | `Read, Grep, Glob` |
| Revisa | calidad, errores y cumplimiento de la spec del ticket sobre el cambio | las cinco reglas de negocio del principio I contra la spec, el código y los tests |
| Reporta | hallazgos con `archivo:línea`, `BLOQUEANTE` o `SUGERENCIA` | una tabla de las cinco reglas y hallazgos |
| No hace | corregir, proponer parches ni ejecutar nada | lo mismo |

Instrucciones comunes del cuerpo de cada subagente:

- Solo lee y reporta; si encuentra un problema, lo describe, no lo corrige (alcance del issue).
- Lee los documentos del ticket y la constitución con `Read` (R3).
- Cada hallazgo lleva ubicación y razón; no hay hallazgo sin ubicación. Lo que **falta** (un
  requisito sin implementar o sin prueba) no tiene línea en el código: se ubica en el
  requisito (`spec.md:línea` o `tasks.md:línea`) y es **BLOQUEANTE** si el requisito es
  obligatorio. Nunca se rebaja a sugerencia por no poder ubicarlo en el código.
- No repite valores sensibles si los encuentra: dice el tipo y la ubicación.
- Termina con la línea `RESUMEN` (formato abajo).

## Qué cuenta para la cobertura

Hallazgo de T030: con las instrucciones anteriores, el revisor contó la documentación de
referencia y «no ejecutar los tests» como faltas de cobertura, y en el #4 (7 archivos de código,
+893 líneas, y 6 de tests, +1834) no leyó los tests: `/abrir-pr` nunca habría aprobado el
ticket. La regla, que repiten los dos subagentes y las dos skills:

| | Qué |
|---|---|
| **Cuentan** | El código y la configuración de la lista: `src/**`, `.claude/hooks/*.py`, `.claude/settings.json`, `.mcp.json`, `.claude/agents/`, `.claude/skills/` y `.claude/commands/`; y los tests (`test_*.py`). Cualquier otro archivo de la lista que no sea referencia cuenta también; los generados (`uv.lock`) se leen por secciones. Se leen **enteros**; los tests, por secciones si hace falta |
| **Son referencia y no cuentan** | `specs/NNN-*/`, `README.md`, `DECISIONES.md` y `.claude/rules/`. Se leen por secciones o con `Grep` para contrastar; leerlos a medias no reduce la cobertura |
| **No ejecutar tests** | **Nunca reduce la cobertura**: el revisor no tiene Bash. No se reporta como falta ni como hallazgo |
| **Leído a medias** | Un archivo que cuenta y que se leyó a medias se nombra en el reporte, con las líneas leídas, y entonces la cobertura **sí** es incompleta |

**Plan de lectura**, en este orden: (1) la lista de archivos del contexto, (2) el código y la
configuración, (3) los tests, y solo entonces (4) el reporte.

## Skills (`.claude/skills/<nombre>/SKILL.md`)

Frontmatter común:

```yaml
context: fork
agent: <subagente homónimo>
argument-hint: "[carpeta del ticket, p. ej. specs/NNN-nombre]"
allowed-tools:
  - Bash(<comando exacto del script de preparación>)   # solo este
```

La ruta del script se resuelve con una variable de la skill (`${CLAUDE_SKILL_DIR}` o
`${CLAUDE_PROJECT_DIR}`, la que confirme Q1), nunca con una ruta absoluta.

El cuerpo (prompt de la tarea, que el subagente recibe porque no ve la conversación):

1. La inyección del contexto: la salida de `preparar_revision.py` (R6). `$ARGUMENTS`
   **no** se interpola en el comando.
2. La instrucción: lee `spec.md`, `plan.md`, `tasks.md` y la constitución; revisa el cambio.
   **La carpeta del ticket es la de la línea `Ticket:` del contexto**, calculada con git a
   partir de la rama, que es la fuente fiable. `$ARGUMENTS` es solo una pista: si indica otra
   carpeta, el revisor lo dice en el reporte y declara `cobertura=incompleta`.
3. Qué hacer si el diff se omitió por tamaño: leer los archivos de la lista con `Read` y
   `Grep`; solo `cobertura=incompleta` si algún archivo de código o configuración no se puede
   leer. Los archivos de `specs/NNN-*/` se leen como referencia (por secciones o con `Grep`) y
   no cuentan para la cobertura. Si la lista viene **agrupada por directorio**, el revisor no
   puede saber qué archivos leer y reporta `cobertura=incompleta`.
4. Qué hacer si la salida no empieza con `CONTEXTO DE REVISIÓN` (la inyección falló o está
   desactivada), o si ve `CONTEXTO INCOMPLETO`: reportarlo y `cobertura=incompleta`.
5. El formato del reporte.

Invocación: `/abrir-pr` las ejecuta con la herramienta Skill y la carpeta del ticket. También
pueden invocarse a mano (`/revisar-codigo specs/NNN-nombre`), sin registrar veredicto.

## Script de preparación (`.claude/hooks/preparar_revision.py`)

| Aspecto | Contrato |
|---------|----------|
| Invocación | `uv run --no-project --python 3.12 --quiet ${CLAUDE_PROJECT_DIR}/.claude/hooks/preparar_revision.py`. Las skills **conservan** la variable: skills.md la sustituye en el contenido de la skill y en las reglas Bash de `allowed-tools` |
| Raíz | La calcula el script: `CLAUDE_PROJECT_DIR` si existe; si no, `git rev-parse --show-toplevel` desde el directorio actual; y si tampoco, el directorio actual. Desde una subcarpeta usa la raíz del repositorio, donde está `specs/` |
| Entrada | ninguna; ni argumentos ni stdin. La rama y las rutas salen de git (R2) |
| Salida | texto en stdout: base, lista de archivos, diff o aviso de omisión, ticket y constitución (R6) |
| Código de salida | siempre 0; un fallo se dice en la salida con `CONTEXTO INCOMPLETO: <motivo>` |
| Red | ninguna; usa `origin/main` ya actualizado por `/abrir-pr` |
| Marca | la primera línea de la salida es `CONTEXTO DE REVISIÓN` (R2.4) |
| Commit | la línea `Commit: <sha completo de HEAD>` va justo después de `Rama:`: es el commit que se revisa y al que `/abrir-pr` ata el veredicto |
| Umbral | `UMBRAL_SALIDA` (14 500 bytes: la mitad del mayor tamaño que llegó completo en Q4(a)) sobre **toda** la salida: el diff completo solo si la salida total queda por debajo; marca, lista y rutas se emiten siempre |
| Referencia | los archivos de `specs/NNN-*/` van marcados como referencia y no cuentan para la cobertura |

## Formato del reporte

```text
## Hallazgos
- BLOQUEANTE src/due_diligence/x.py:42 — <razón>
- SUGERENCIA .claude/hooks/y.py:10 — <razón>

## Reglas de negocio            (solo el auditor)
| Regla | Estado | Razón o evidencia |
|-------|--------|-------------------|
| I.1 … | no aplica | la spec del ticket no la cita y el diff no toca código ni tests que la implementen o la prueben |

RESUMEN: bloqueantes=1 sugerencias=1 cobertura=completa
```

Validación de `RESUMEN` (la hace `veredicto.py`): línea completa
`RESUMEN: bloqueantes=<entero> sugerencias=<entero> cobertura=<completa|incompleta>`; si no
hay exactamente una, el reporte no es utilizable.
