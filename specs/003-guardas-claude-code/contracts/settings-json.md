# Contrato: `.claude/settings.json`

Estado final del archivo tras el ticket #3. Las claves `env` y `enabledMcpjsonServers` del
ticket #1 se conservan sin cambios. Decisiones en [research.md](../research.md) (R1–R6 y
R14).

## `hooks`

Todas las entradas usan la forma exec (`command` + `args`), sin shell.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read|Write|Edit|NotebookEdit|Grep|Glob|Bash|PowerShell",
        "hooks": [
          {
            "type": "command",
            "command": "uv",
            "args": ["run", "--no-project", "--python", "3.12", "--quiet",
                     "${CLAUDE_PROJECT_DIR}/.claude/hooks/guarda_secretos.py"],
            "timeout": 10,
            "onFailure": "block"
          }
        ]
      },
      {
        "matcher": "Write|Edit|NotebookEdit|Bash|PowerShell|mcp__github__add_issue_comment|mcp__github__update_issue_comment|mcp__github__create_pull_request|mcp__github__update_pull_request|mcp__github__issue_write|mcp__github__add_reply_to_pull_request_comment|mcp__github__pull_request_review_write|mcp__github__add_comment_to_pending_review",
        "hooks": [
          {
            "type": "command",
            "command": "uv",
            "args": ["run", "--no-project", "--python", "3.12", "--quiet",
                     "${CLAUDE_PROJECT_DIR}/.claude/hooks/guarda_datos.py"],
            "timeout": 10,
            "onFailure": "block"
          }
        ]
      },
      {
        "matcher": "Write|Edit|NotebookEdit|Bash|PowerShell",
        "hooks": [
          {
            "type": "command",
            "command": "uv",
            "args": ["run", "--no-project", "--python", "3.12", "--quiet",
                     "${CLAUDE_PROJECT_DIR}/.claude/hooks/guarda_spec_previa.py"],
            "timeout": 10,
            "onFailure": "block"
          }
        ]
      },
      {
        "matcher": "mcp__github__projects_write",
        "hooks": [
          {
            "type": "command",
            "command": "uv",
            "args": ["run", "--no-project", "--python", "3.12", "--quiet",
                     "${CLAUDE_PROJECT_DIR}/.claude/hooks/guarda_mcp_github.py"],
            "timeout": 10,
            "onFailure": "block"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "uv",
            "args": ["run", "--project", "${CLAUDE_PROJECT_DIR}", "--quiet",
                     "${CLAUDE_PROJECT_DIR}/.claude/hooks/formatear_python.py"],
            "timeout": 30,
            "onFailure": "continue"
          }
        ]
      }
    ]
  }
}
```

Invariantes que verifica `test_configuracion.py`:

- Cada matcher contiene solo letras, dígitos, `_` y `|`, así que es una lista de nombres
  exactos, no una expresión regular.
- Las cuatro guardas llevan `"onFailure": "block"` y `timeout` ≤ 10; el formato lleva
  `"onFailure": "continue"`.
- `PowerShell` está en los matchers de las guardas de secretos, datos y spec previa como
  respaldo (R3, R5). No hay ninguna regla `PowerShell(...)` en `permissions`.
- Cada script nombrado en `args` existe en `.claude/hooks/`.

## `permissions.deny`

Sustituye a la lista del ticket #1. Primera barrera; la garantía es el hook (R6).

### Herramientas de archivo (11)

`Read(...)` cubre Read, Grep, Glob y LSP; `Edit(...)` cubre Edit, Write y NotebookEdit.
El orden importa: la excepción con `!` solo recorta las reglas `path` o `./path`
**anteriores** de la misma lista (R6).

```text
Read(**/.env)
Edit(**/.env)
Read(**/.env.*)
Edit(**/.env.*)
Read(**/*.key)
Edit(**/*.key)
Read(**/secrets/**)
Edit(**/secrets/**)
Read(!**/.env.example)
Edit(!**/.env.example)
Edit(/.claude/settings.local.json)
```

- Las 8 primeras cubren las mismas familias que la guarda: `.env`, todas las variantes
  `.env.*`, `*.key` y `secrets/` (FR-003).
- Las 2 excepciones van detrás de `**/.env.*` y devuelven el acceso a `.env.example`.
- La última, de solo escritura, impide que Claude Code escriba
  `"disableAllHooks": true` u otra configuración que desactive las guardas (R14). Las
  personas lo siguen editando fuera de Claude Code. Con `/`, la ruta se resuelve desde
  la raíz del proyecto, porque la regla está en la configuración del proyecto. Con `./`
  sería relativa al directorio actual, que cambia con los `cd`.

### Comandos de Bash (40)

`Bash(<comando> <objetivo>)` para cada combinación de:

- comandos: `cat`, `head`, `tail`, `less`, `more`, `cp`, `mv`, `source`;
- objetivos: `*.env`, `*.env *`, `*.env.local*`, `*secrets/*`, `*.key`.

Ejemplo: `Bash(head *.env.local*)`. Ninguno coincide con `cat .env.example`. Sustituyen
a `Bash(cat .env*)` y `Bash(type .env*)`, que sí lo bloqueaban.

`grep` no está en la lista a propósito: `Bash(grep *.env *)` bloquearía
`grep -n .env README.md`, que FR-002 y SC-001 obligan a permitir. `grep` queda a cargo
de `guarda_secretos`, que distingue el patrón buscado de los archivos (R6).

### PowerShell (0)

No se añaden reglas `PowerShell(...)`: con Git Bash en Windows, las denegaciones de Bash
mantienen apagada la herramienta PowerShell, y una regla de PowerShell la encendería
(R5). Si alguien la activa con `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`, la garantía son las
guardas.

### Herramientas del MCP de GitHub (7)

```text
mcp__github__delete_repository
mcp__github__delete_file
mcp__github__create_or_update_file
mcp__github__push_files
mcp__github__merge_pull_request
mcp__github__create_repository
mcp__github__fork_repository
```

Las dos primeras son las expuestas con `destructiveHint: true` que el proyecto no usa
(FR-016). `mcp__github__projects_write`, también destructiva, se permite porque la usan
`siguiente-ticket` y `/abrir-pr` (FR-017), pero `guarda_mcp_github` la limita a
`update_project_item` (FR-024). Las otras cinco se deniegan por mínimo privilegio (R4).

Invariantes que verifica `test_configuracion.py`:

- Están exactamente las 58 entradas: 11 + 40 + 0 + 7.
- Ninguna entrada empieza por `PowerShell(` ni por `Bash(grep`.
- `Read(!**/.env.example)` aparece después de `Read(**/.env.*)`, y
  `Edit(!**/.env.example)` después de `Edit(**/.env.*)`.
- Ninguna regla de Bash coincide con `cat .env.example`. El test interpreta el `*` de
  cada regla como "cualquier secuencia de caracteres" y la compara con el comando
  completo.
- Ninguna herramienta `mcp__github__*` que aparezca en
  `.claude/skills/siguiente-ticket/SKILL.md`, `.claude/commands/abrir-pr.md` o
  `.claude/commands/comentar-avance.md` está en la lista (FR-017).
- Ninguna regla de archivo coincide con `.env.example`.
