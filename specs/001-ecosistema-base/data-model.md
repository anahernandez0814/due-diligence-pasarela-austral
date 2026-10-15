# Data Model: Ecosistema base de Claude Code

Este ticket no tiene datos de negocio. Sus "entidades" son los archivos de configuración
del ecosistema, sus campos obligatorios y las reglas que deben cumplir.

## Convenciones del equipo — `CLAUDE.md`

| Campo | Regla |
|-------|-------|
| Idioma | Español en mensajes y documentación. |
| Flujo | Una rama `NNN-nombre-corto` por ticket desde `main`; PR hacia `main` con `Closes #N`. |
| Comandos | `uv sync`, `uv run ruff check .`, `uv run ruff format .`, `uv run pytest`. |
| Mapa | Dónde viven `src/`, `specs/`, `docs/`, `.specify/`, `.claude/`. |
| Constitución | Línea `@.specify/memory/constitution.md`; ningún principio copiado. |

Validación: 40 líneas como máximo (FR-001, FR-002, SC-005).

## Preferencias personales

| Archivo | Regla |
|---------|-------|
| `CLAUDE.local.md` | Ignorado por git. |
| `.claude/settings.local.json` | Ignorado por git. |
| `.env` | Ignorado por git; lectura y edición denegadas en `.claude/settings.json`. |

Validación: `git check-ignore` devuelve coincidencia para los tres (FR-012).

## Configuración del servidor MCP de GitHub — `.mcp.json`

| Campo | Valor |
|-------|-------|
| Nombre | `github` |
| Tipo | `http` |
| URL | `https://api.githubcopilot.com/mcp/` |
| Credencial | Referencia `${GITHUB_PAT}`, nunca el valor |
| Toolsets | `repos,issues,pull_requests,projects` |

Relación: `.claude/settings.json` lo habilita con `enabledMcpjsonServers: ["github"]`.
Contrato completo en [contracts/mcp-json.md](contracts/mcp-json.md) (FR-003, FR-004).

## Proyecto Python — `pyproject.toml`

| Sección | Regla |
|---------|-------|
| `[project]` | Python `>=3.12,<3.13`, sin dependencias de ejecución por ahora. |
| `[dependency-groups] dev` | ruff, pytest. |
| `[tool.ruff]` | `target-version = "py312"`. |
| `[tool.pytest.ini_options]` | `testpaths = ["src"]`, `--import-mode=importlib`. |

Contrato completo en [contracts/pyproject.md](contracts/pyproject.md) (FR-005 a FR-007).

## Registro de decisiones — `DECISIONES.md`

Cada entrada: **Necesidad o tema**, **Decisión**, **Motivo**, **Alternativas descartadas**.
Entradas iniciales: (1) cargar la constitución en cada sesión con `@import`; (2) ciclo
manual de tickets hasta fusionar #2 y #4 (FR-011). Máximo dos páginas al completarse (#14).
