# Data Model: Plugin reutilizable para otros equipos (#13)

No hay datos persistentes. Son los archivos de configuración que lee Claude Code y las entradas y
salidas de los scripts. Los formatos exactos están en [contracts/plugin.md](contracts/plugin.md).

## Marketplace (`.claude-plugin/marketplace.json`)

| Campo | Valor | Regla |
|-------|-------|-------|
| `name` | `piezas-reutilizables` | Genérico (FR-004). |
| `owner.name` | Nombre de equipo genérico | Obligatorio en el esquema; no es una persona. |
| `plugins[0].name` | `guardas-y-revision` | Igual que el `name` del manifiesto. |
| `plugins[0].source` | `./plugins/guardas-y-revision` | Relativo a la raíz del marketplace. |
| `plugins[0].description` | En español | Igual que la del manifiesto. |

## Manifiesto (`plugins/guardas-y-revision/.claude-plugin/plugin.json`)

| Campo | Valor | Regla |
|-------|-------|-------|
| `name` | `guardas-y-revision` | Da el prefijo de la skill y del agente (`guardas-y-revision:…`). |
| `version` | `1.0.0` | Se sube cuando cambia una pieza; sin eso, `claude plugin update` no la trae. |
| `description` | En español | Sin términos del proyecto. |
| `author` | Ausente | FR-001: sin datos personales. |

Los componentes se descubren por convención (`agents/`, `skills/` y `hooks/hooks.json`).

## Registro de la guarda

Hay dos registros equivalentes:
- **en el plugin**: `hooks/hooks.json`, con `${CLAUDE_PLUGIN_ROOT}`;
- **en este repositorio**: `.claude/settings.json`, con `${CLAUDE_PROJECT_DIR}/plugins/guardas-y-revision`.

| Campo | Valor común |
|-------|-------------|
| Evento | `PreToolUse` |
| `matcher` | La expresión anclada de R5 |
| `type` | `command` |
| `command` / `args` | `uv` / `run --no-project --python 3.12 --quiet <raíz>/hooks/guarda_datos.py` |
| `timeout` | 10 |
| `onFailure` | `block` |

**Invariante (FR-009)**: en la configuración versionada de este repositorio, cada herramienta que
el matcher acepta tiene **una** ejecución de `guarda_datos.py`, y `enabledPlugins` tiene
`"guardas-y-revision@piezas-reutilizables": false`.

## Entrada y salida de la guarda

Sin cambios respecto al #3, salvo R5 y R10.

- **Entrada**: el JSON de `PreToolUse` por stdin (`tool_name`, `tool_input` y `cwd`).
- **Textos revisados**:
  - Write: `content`;
  - Edit: `new_string`;
  - NotebookEdit: `new_source`;
  - Bash y PowerShell: `command`;
  - cualquier `mcp__…`: todos los valores de texto, recorridos de forma recursiva.
- **Salida**:
  - código 0: permite;
  - código 2: bloquea, con una línea en stderr: `[guarda_datos] Dato con forma real bloqueado:
    <tipo> en <dónde>, línea <n>[; …]. Usa valores claramente ficticios o genera el valor en la
    prueba.`;
  - error propio: código 2, con «La guarda falló (<Tipo>); la acción se bloquea por precaución.».

## Contexto de revisión (salida de `scripts/contexto_revision.py`)

Líneas, en este orden:
1. `CONTEXTO DE REVISIÓN`
2. `Rama: <rama|(ninguna)>`
3. `Commit: <sha>`
4. `Base: <sha12> (git merge-base HEAD <referencia>)`
5. `Ticket: specs/NNN-nombre/`, con sus tres documentos, o `Ticket: no aplica (…)`
6. `Constitución: .specify/memory/constitution.md`, o `Constitución: no aplica`
7. `CONTEXTO INCOMPLETO: <motivo>`, cero o más veces
8. La lista de archivos (completa, o agrupada por directorio)
9. El diff completo si cabe en 14 500 bytes; si no, el aviso de diff omitido

**Siempre sale con código 0.**

## Lista de términos del proyecto (test, fuera del plugin)

Patrones de R11. Cada hallazgo se informa como `archivo:línea:término`.
