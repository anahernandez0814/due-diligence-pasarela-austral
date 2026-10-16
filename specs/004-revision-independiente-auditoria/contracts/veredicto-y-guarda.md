# Contrato: veredicto, registro y guarda de PR

Entidades en [data-model.md](../data-model.md); decisiones en [research.md](../research.md)
(R7 a R10).

## Registro del veredicto (`.claude/hooks/veredicto.py`)

Módulo con una interfaz de línea de comandos que `/abrir-pr` invoca por Bash.

| Aspecto | Contrato |
|---------|----------|
| Invocación | `uv run --no-project --python 3.12 --quiet <raíz>/.claude/hooks/veredicto.py registrar --codigo "<RESUMEN>" --auditoria "<RESUMEN>"` |
| Qué hace | valida las dos líneas `RESUMEN`, consolida, escribe `.claude/veredictos/<HEAD>.json` y escribe el resultado |
| Consolidación | `aprobado` solo si las dos líneas son válidas, con `bloqueantes=0` y `cobertura=completa`; si no, `con bloqueantes` |
| Salida | una línea: `veredicto: aprobado` o `veredicto: con bloqueantes (<motivo>)` |
| Código de salida | 0 con `aprobado`; 1 con `con bloqueantes`; 2 si no pudo registrar (no hay git, no se puede escribir) |
| Escritura | un archivo por commit; si existe, se sobrescribe (misma revisión repetida sobre el mismo commit) |
| Funciones | `ruta_veredicto(raiz, sha)`, `registrar(...)`, `leer(raiz, sha)` y `consolidar(...)`; las usa también la guarda |

Un `RESUMEN` ausente, repetido o con formato inesperado cuenta como reporte no utilizable y
el veredicto es `con bloqueantes`.

## Guarda de PR (`.claude/hooks/guarda_pr.py`)

Interfaz común de las guardas de #3 ([guardas.md](../../003-guardas-claude-code/contracts/guardas.md)):
JSON en stdin con `tool_name`, `tool_input` y `cwd`; salida 2 y una línea en stderr
`[guarda_pr] <motivo>. <qué hacer>.`; error propio → salida 2; UTF-8; solo biblioteca
estándar.

### Qué se bloquea

| Vía | Entrada reconocida | Rama del PR |
|-----|--------------------|-------------|
| MCP | `tool_name == mcp__github__create_pull_request` | `tool_input.head`, normalizada: si viene como `propietario:rama`, el prefijo debe coincidir con `tool_input.owner` (sin distinguir mayúsculas) y se toma la rama; con otro prefijo (PR desde un fork) se bloquea |
| `gh pr create` | `gh` con `pr create` como primeros no-opciones, en el comando exterior, en los interiores (`bash -c`, `eval`, heredocs) y tras lanzadores (`xargs`, `sudo`, `env -S`…) | `--head` / `-H` o la rama actual |
| `gh api` | endpoint `repos/<o>/<r>/pulls` (sin subrutas) con POST explícito (`-X POST`, `--method POST`) o implícito (`-f`, `-F`, `--field`, `--raw-field`, `--input`); y `graphql` con `createPullRequest` | la rama actual |

Se permiten sin comprobar: `gh pr view`, `gh pr list`, `gh pr status`, `gh api` con GET y
cualquier otro comando (FR-014).

### Comprobación

En este orden; la primera que falla bloquea con su mensaje:

| # | Condición para permitir | Mensaje cuando falla |
|---|--------------------------|----------------------|
| 1 | la rama del PR es la rama actual | Cambia a la rama del PR o usa `/abrir-pr` |
| 2 | `refs/remotes/origin/<rama>` existe | El commit no está publicado: sube la rama con `/abrir-pr` |
| 3 | `origin/<rama>` es igual a `HEAD` | La rama remota no coincide con el commit revisado |
| 4 | existe `.claude/veredictos/<HEAD>.json` y se lee | Falta la revisión de este commit: ejecuta `/abrir-pr` |
| 5 | su `veredicto` es `aprobado` | La revisión tiene bloqueantes: corrígelos, haz un commit y ejecuta `/abrir-pr` |
| — | cualquier excepción | La guarda falló; la acción se bloquea por precaución |

Matcher y registro en `.claude/settings.json`:

```json
{
  "matcher": "Bash|PowerShell|mcp__github__create_pull_request",
  "hooks": [{
    "type": "command",
    "command": "uv",
    "args": ["run", "--no-project", "--python", "3.12", "--quiet",
             "${CLAUDE_PROJECT_DIR}/.claude/hooks/guarda_pr.py"],
    "timeout": 10,
    "onFailure": "block"
  }]
}
```

### Protección del directorio de veredictos (FR-020)

`guarda_spec_previa.py` bloquea, en cualquier rama, escribir, editar, copiar, mover o nombrar
en código en línea `.claude/veredictos/**`, con las vías que ya vigila para
`.claude/settings.local.json` (FR-025 de #3); leerlo se permite. `permissions.deny` añade
`Edit(/.claude/veredictos/**)`. El comando de `veredicto.py registrar` no nombra el directorio,
así que no se bloquea. Mensaje: `[guarda_spec_previa] El directorio de veredictos solo lo
escribe el registro de la revisión. Ejecuta /abrir-pr.`

### Límites declarados

- Invocar `veredicto.py registrar` con `RESUMEN` inventados: la puerta no lo distingue de una
  revisión real (R8). Escribir el archivo a mano ya no es residual.
- Creación fuera de Claude Code, alias de `gh` y construcciones que el extractor de #3 no
  reconoce (R10).
- Commits de otras personas empujados después del último `fetch` (R9).
