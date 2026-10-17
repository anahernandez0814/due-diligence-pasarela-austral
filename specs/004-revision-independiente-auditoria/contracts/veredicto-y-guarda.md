# Contrato: veredicto, registro y guarda de PR

Entidades en [data-model.md](../data-model.md); decisiones en [research.md](../research.md)
(R7 a R10).

## Registro del veredicto (`.claude/hooks/veredicto.py`)

Módulo con una interfaz de línea de comandos que `/abrir-pr` invoca por Bash.

| Aspecto | Contrato |
|---------|----------|
| Invocación | `uv run --no-project --python 3.12 --quiet .claude/hooks/veredicto.py registrar --commit <sha> --codigo '<RESUMEN>' --auditoria '<RESUMEN>'`, ejecutada desde la raíz del repositorio. La ruta es **relativa**: `${CLAUDE_PROJECT_DIR}` no existe en la herramienta Bash (research R2.5) |
| Raíz | La calculan los scripts: `CLAUDE_PROJECT_DIR` si existe; si no, `git rev-parse --show-toplevel` desde el directorio actual; y si tampoco, el directorio actual (el error se reporta como hasta ahora). Ejecutado desde una subcarpeta, el veredicto se escribe en la raíz del repositorio, donde la guarda lo busca |
| Entradas | Las dos líneas llegan **ya validadas** por `/abrir-pr` (ver [abrir-pr.md](abrir-pr.md)): solo `RESUMEN: bloqueantes=<dígitos> sugerencias=<dígitos> cobertura=<completa\|incompleta>` o `sin resumen`, sin comillas posibles |
| `--commit` | **Obligatorio**: el sha completo (hexadecimal, 40 o 64 caracteres) del commit que se revisó. Es el que `/abrir-pr` guardó antes de lanzar las skills. Ausente, abreviado o no hexadecimal: salida 2 sin escribir nada |
| Commit cambiado | Si `--commit` no coincide con `HEAD`, **no escribe nada** y sale con 2, con este mensaje en stderr: `El commit cambió durante la revisión (revisado <7 caracteres>, actual <7 caracteres>): ejecute /abrir-pr de nuevo.` Sin archivo de veredicto, la guarda ya bloquea, así que no hace falta otro estado |
| Qué hace | comprueba que `--commit` es `HEAD`, valida las dos líneas `RESUMEN` (formato estricto: dígitos `[0-9]`, no los de otros alfabetos), consolida, escribe `.claude/veredictos/<--commit>.json` y escribe el resultado. El veredicto queda atado al commit que se revisó, no al que exista al registrar |
| Consolidación | `aprobado` solo si las dos líneas son válidas, con `bloqueantes=0` y `cobertura=completa`, **y hay cambios frente a la base** (`git diff --quiet <base>..HEAD` con `<base>` = `git merge-base HEAD origin/main`, la misma que `preparar_revision.py`); si no, `con bloqueantes`. Sin cambios: `con bloqueantes (sin cambios)`; sin base calculable: `con bloqueantes (sin base de comparación)`. El reporte no puede revertirlo |
| Salida | una línea: `veredicto: aprobado` o `veredicto: con bloqueantes (<motivo>)` |
| Código de salida | 0 con `aprobado`; 1 con `con bloqueantes`; 2 si no pudo registrar (no hay git, no se puede escribir, `--commit` ausente, no hexadecimal, abreviado o distinto de `HEAD`) |
| Escritura | un archivo por commit; si existe, se sobrescribe (misma revisión repetida sobre el mismo commit) |
| Funciones | `ruta_veredicto(raiz, sha)`, `registrar(...)`, `leer(raiz, sha)`, `consolidar(...)`, `base_de_fusion(raiz)` y `hay_cambios(raiz)`; las usa también la guarda, y `preparar_revision.py` importa la base |

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
- La validación de la línea `RESUMEN` antes de pasarla es una **instrucción de `/abrir-pr`,
  no código**. Que se ejecutara un comando ajeno exigiría tres fallos a la vez: un contenido
  manipulado que hace al revisor escribir una comilla en la línea `RESUMEN`, el modelo
  ignorando la validación, y la capa de permisos dejándolo pasar (exige que cada parte de un
  comando compuesto coincida con una regla permitida). Leer los reportes de un archivo o de
  stdin no lo elimina: el modelo seguiría escribiendo el texto en un comando o en un archivo
  temporal. Por eso el contrato no cambia y el límite se declara.
- La ruta relativa del registro **exige ejecutarlo desde la raíz**. Desde una subcarpeta,
  `uv` no encuentra el script y sale con 2: `/abrir-pr` se detiene sin push ni PR (falla
  cerrado).
