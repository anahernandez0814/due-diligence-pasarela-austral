# Contrato: plugin `guardas-y-revision` y marketplace `piezas-reutilizables`

## 1. Instalación (lo que promete el README)

```bash
# Desde GitHub (tras el merge; requiere acceso al repositorio)
claude plugin marketplace add anahernandez0814/due-diligence-pasarela-austral
claude plugin install guardas-y-revision@piezas-reutilizables --scope project

# Desde una copia local
claude plugin marketplace add <ruta de la copia>
claude plugin install guardas-y-revision@piezas-reutilizables --scope project

# Desinstalar
claude plugin uninstall guardas-y-revision@piezas-reutilizables --scope project
```

**Requisitos**: Claude Code 2.1.295 o posterior, `uv` en el `PATH` y `git`.

**Ámbitos**:
- `--scope project` comparte la instalación con el equipo en el `.claude/settings.json` del otro
  repositorio;
- `--scope user` la deja en todos los proyectos de la persona;
- `--scope local` la deja solo para la persona en ese repositorio.

## 2. Guarda de datos con forma real (hook)

- **Evento**: `PreToolUse`.
- **Matcher** (R5):
  `^(Write|Edit|NotebookEdit|Bash|PowerShell|mcp__.+__(add_issue_comment|update_issue_comment|create_pull_request|update_pull_request|issue_write|add_reply_to_pull_request_comment|pull_request_review_write|add_comment_to_pending_review))$`.
- **Detecta**:
  - tarjeta: 13 a 19 dígitos, prefijo 2–6 y Luhn válido;
  - NIT: 9 dígitos con el dígito de verificación de la DIAN, con guion o tras la palabra `NIT`;
  - cédula: de 6 a 10 dígitos tras una palabra de contexto;
  - credenciales: tokens de GitHub, claves de Anthropic, claves de acceso de AWS y claves privadas
    PEM.
- **Bloquea**: con código 2 y una línea en stderr con el tipo, dónde y la línea, **nunca el valor**.
- **No hay lista de valores permitidos ni forma de saltarse la guarda.**
- **Falla cerrado**:
  - ante un error propio, bloquea;
  - si `uv` falta o el proceso falla, bloquea `onFailure: block`.
- **Raíz del proyecto**: la usa solo para mostrar rutas relativas, y la toma de `CLAUDE_PROJECT_DIR`
  o del `cwd` de la entrada.

## 3. Skill `/guardas-y-revision:revisar-codigo`

- **Frontmatter**:
  - `context: fork`;
  - `agent: guardas-y-revision:revisor-codigo`;
  - `allowed-tools` con la regla Bash exacta de la línea `!`;
  - `argument-hint` opcional: la carpeta de specs del ticket.
- **Línea `!`**: `uv run --no-project --python 3.12 --quiet "${CLAUDE_PLUGIN_ROOT}/scripts/contexto_revision.py"`.
- **Pasos para el subagente**:
  1. comprueba la marca del contexto;
  2. lee el ticket y la constitución si el contexto los da;
  3. revisa el cambio;
  4. reporta;
  5. cierra con la línea `RESUMEN`.

## 4. Subagente `guardas-y-revision:revisor-codigo`

- **Herramientas**: `Read`, `Grep` y `Glob`. No corrige, no ejecuta y no lanza agentes.
- **Hallazgos**: `- BLOQUEANTE|SUGERENCIA archivo:línea — razón`.
- **Valores sensibles**: por tipo y ubicación, sin el valor.
- **Cobertura**: `completa` si leyó entero todo lo que cuenta.
  - **Cuenta**: el código, la configuración y los tests del cambio.
  - **Son referencia**: la carpeta de specs del ticket, la documentación en Markdown y los archivos
    generados.
  - **Sin ticket** (`Ticket: no aplica`): la cobertura no baja; el reporte dice que no hubo spec
    contra la que contrastar.
- **Última línea, exacta**: `RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>`.

## 5. Script `scripts/contexto_revision.py`

- **Ejecución**: sin argumentos y sin stdin. Solo la biblioteca estándar y `git`. Siempre sale con
  código 0.
- **Salida**: la del [data-model](../data-model.md#contexto-de-revisión-salida-de-scriptscontexto_revisionpy).
- **Base de fusión**: la primera referencia que exista entre `origin/HEAD` (su rama),
  `origin/main`, `origin/master`, `main` y `master`. Si no hay ninguna: `CONTEXTO INCOMPLETO`.
- **Spec Kit**:
  - si existe `specs/`, la regla del #4 (rama `NNN-nombre` y una sola carpeta `specs/NNN-*`), y su
    fallo es `CONTEXTO INCOMPLETO`;
  - si no existe, `Ticket: no aplica`.

## 6. Este repositorio

- **`.claude/settings.json`**:
  - registra la guarda con el registro equivalente al de `hooks.json` (data-model) y la ruta
    `${CLAUDE_PROJECT_DIR}/plugins/guardas-y-revision/hooks/guarda_datos.py`;
  - declara `"enabledPlugins": {"guardas-y-revision@piezas-reutilizables": false}`.
- **Sin cambios**: `.claude/agents/revisor-codigo.md`, `.claude/skills/revisar-codigo/` y
  `preparar_revision.py`, y `/abrir-pr` con su veredicto.
