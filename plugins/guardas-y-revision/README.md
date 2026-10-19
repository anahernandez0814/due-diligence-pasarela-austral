# guardas-y-revision

Plugin de Claude Code con tres piezas:

- **Guarda de datos con forma real** (hook `PreToolUse`): antes de escribir, editar, ejecutar o
  publicar en GitHub un texto, lo revisa y bloquea la acción si tiene una tarjeta (Luhn
  válido), un NIT con su dígito de verificación, una cédula tras una palabra de contexto o una
  credencial (tokens de GitHub, claves de Anthropic y de AWS, claves privadas). El mensaje dice
  el tipo y la línea, nunca el valor. Falla cerrada: si no puede ejecutarse, bloquea.
- **Subagente `guardas-y-revision:revisor-codigo`**: revisor independiente de solo lectura
  (`Read`, `Grep` y `Glob`). Reporta hallazgos `BLOQUEANTE` y `SUGERENCIA` con su ubicación y
  termina con `RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>`.
- **Skill `/guardas-y-revision:revisar-codigo`**: prepara el contexto del cambio de la rama
  (base de fusión, archivos y diff si cabe) y lanza el revisor en un contexto separado. Si el
  repositorio usa Spec Kit (`specs/NNN-nombre/` y `.specify/memory/constitution.md`), el
  revisor contrasta el cambio con la spec del ticket; si no, revisa calidad y errores.

## Instalación

Con el marketplace que lo publica (`<propietario>/<repositorio>` de GitHub o una ruta local):

```bash
claude plugin marketplace add <propietario>/<repositorio>
claude plugin install guardas-y-revision@piezas-reutilizables --scope project
```

O en un paso, en una sesión de Claude Code:
`/plugin install guardas-y-revision --marketplace <propietario>/<repositorio>`.

## Requisitos

- Claude Code 2.1.295 o posterior (`onFailure` en los hooks).
- [`uv`](https://docs.astral.sh/uv/) en el `PATH`: ejecuta los scripts con Python 3.12, que
  descarga si hace falta. Los scripts solo usan la biblioteca estándar.
- `git`, para el contexto de la revisión.

## Matcher de la guarda

`Write`, `Edit`, `NotebookEdit`, `Bash`, `PowerShell` y las herramientas de publicación en
GitHub (`add_issue_comment`, `create_pull_request`, …) de **cualquier** servidor MCP
(`mcp__<servidor>__<herramienta>`), sea cual sea su nombre.

## Actualizaciones

Claude Code ejecuta el plugin desde su caché, por versión: un cambio llega a quien lo tiene
instalado cuando se sube `version` en `.claude-plugin/plugin.json` y se ejecuta
`claude plugin update guardas-y-revision@<marketplace>`.

## Pruebas

Los tests van junto al código (`hooks/test_*.py`, `scripts/test_*.py` y `test_plugin.py`) y
se ejecutan con pytest. Los valores con forma real se generan al ejecutar la prueba; nunca se
escriben literales.
