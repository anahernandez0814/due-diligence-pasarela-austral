# Quickstart: validación del ticket #1

Guía para comprobar que el ecosistema base funciona de punta a punta. Cubre los criterios
de aceptación del issue #1 y SC-001 a SC-005.

## Requisitos previos

- uv y gh instalados.
- `GITHUB_PAT` definida como variable de entorno del usuario, con el token de la CLI de
  GitHub (`gh auth token`) o con un PAT clásico. En ambos casos necesita los scopes `repo` y
  `project`; con la CLI, `gh auth status` muestra los scopes del token. Ver
  [research.md](research.md), R2.

## 1. Entorno Python (criterio 3, SC-001)

```bash
git clone <repo> && cd <repo>
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Esperado: los cuatro comandos terminan con código 0 y pytest ejecuta los dos tests de humo.
Todo el recorrido, clonado incluido, toma menos de 5 minutos.

## 2. Tests en varias carpetas

```bash
uv run pytest --collect-only -q
```

Esperado: aparecen `src/due_diligence/test_humo.py` y `src/servidor_mcp/test_humo.py` sin
error de módulo duplicado ([contracts/pyproject.md](contracts/pyproject.md)).

## 3. Servidor MCP de GitHub (criterio 1, SC-002)

1. Abrir una sesión nueva de Claude Code en la raíz del repositorio.
2. Ejecutar `/mcp`. Esperado: `github` conectado, sin pedir aprobación.
3. Pedir: "lista las opciones del campo Status del GitHub Project". Esperado: Todo, In
   Progress, In review y Done.

Si el paso 2 falla con 401/403, aplicar la alternativa stdio de
[contracts/mcp-json.md](contracts/mcp-json.md) y repetir.

## 4. Sin credenciales (criterio 2, SC-003)

```bash
git grep --untracked -nE "gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9-]{20,}"
```

Esperado: sin resultados. `.mcp.json` solo contiene `${GITHUB_PAT}`.

## 5. Convenciones y archivos personales (criterios 4 y 5, SC-005)

```bash
grep -n "@.specify/memory/constitution.md" CLAUDE.md
wc -l CLAUDE.md
git check-ignore -v CLAUDE.local.md .claude/settings.local.json .env
```

Esperado: la importación aparece una vez, `CLAUDE.md` tiene 40 líneas como máximo y
los tres archivos personales están ignorados. Ningún principio de la constitución está
copiado en `CLAUDE.md`.

## 6. Finales de línea

```bash
git ls-files --eol | grep -v "i/lf" | grep -v "i/none" | grep -v "i/-text"
```

Esperado: sin resultados; todos los archivos de texto están en LF en el índice.
