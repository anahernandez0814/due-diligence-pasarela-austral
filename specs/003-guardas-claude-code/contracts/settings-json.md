# Contrato: `.claude/settings.json`

Estado final del archivo tras el ticket #3. Las claves `env` y `enabledMcpjsonServers` del
ticket #1 se conservan sin cambios. Decisiones en [research.md](../research.md) (R1–R6).

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
- Las tres guardas llevan `"onFailure": "block"` y `timeout` ≤ 10; el formato lleva
  `"onFailure": "continue"`.
- Cada script nombrado en `args` existe en `.claude/hooks/`.

## `permissions.deny`

Sustituye a la lista del ticket #1. Primera barrera; la garantía es el hook (R6).

### Herramientas de archivo (16)

`Read(...)` cubre Read, Grep, Glob y LSP; `Edit(...)` cubre Edit, Write y NotebookEdit.
Para cada objetivo hay una regla `Read(<objetivo>)` y otra `Edit(<objetivo>)`:

| Objetivo |
|----------|
| `**/.env` |
| `**/.env.local` |
| `**/.env.*.local` |
| `**/.env.development` |
| `**/.env.production` |
| `**/.env.test` |
| `**/*.key` |
| `**/secrets/**` |

`.env.example` no coincide con ninguno.

### Comandos de Bash (35)

`Bash(<comando> <objetivo>)` para cada combinación de:

- comandos: `cat`, `head`, `tail`, `grep`, `cp`, `mv`, `source`;
- objetivos: `*.env`, `*.env *`, `*.env.local*`, `*secrets/*`, `*.key`.

Ejemplo: `Bash(head *.env.local*)`. Ninguno coincide con `cat .env.example`. Sustituyen
a `Bash(cat .env*)` y `Bash(type .env*)`, que sí lo bloqueaban.

### Comandos de PowerShell (20)

`PowerShell(<cmdlet> <objetivo>)` para cada combinación de:

- cmdlets: `Get-Content`, `Select-String`, `Copy-Item`, `Move-Item` (los alias como
  `gc`, `cat` o `type` se canonicalizan);
- objetivos: los mismos cinco de Bash.

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
`siguiente-ticket` y `/abrir-pr` (FR-017). Las otras cinco se deniegan por mínimo
privilegio (R4).

Invariantes que verifica `test_configuracion.py`:

- Están las 78 entradas: 16 + 35 + 20 + 7.
- Ninguna herramienta `mcp__github__*` que aparezca en
  `.claude/skills/siguiente-ticket/SKILL.md`, `.claude/commands/abrir-pr.md` o
  `.claude/commands/comentar-avance.md` está en la lista (FR-017).
- Ninguna regla de archivo coincide con `.env.example`.
