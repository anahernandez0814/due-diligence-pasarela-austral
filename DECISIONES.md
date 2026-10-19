# Decisiones del ecosistema

Qué mecanismo resuelve cada necesidad del enunciado, por qué y qué se descartó. El razonamiento
completo, las mediciones y los riesgos residuales están en
[docs/decisiones-detalle.md](docs/decisiones-detalle.md) («E*n*» enlaza a su entrada *n*).

## Necesidades del ecosistema

| N | Necesidad | Mecanismo | Por qué | Descartado | Dónde |
|---|-----------|-----------|---------|------------|-------|
| 1 | Convenciones al clonar | Memoria `CLAUDE.md` con `@import` de la constitución; `CLAUDE.md` de subdirectorio en `src/servidor_mcp/`; `.claude/` versionado | Llegan solas a cada sesión, sin copias que diverjan | Copiar la constitución; cargarla con una skill | #1, #5 · `CLAUDE.md` [E1](docs/decisiones-detalle.md#1-la-constitución-se-carga-en-cada-sesión-con-import) |
| 2 | Lo personal no afecta | `CLAUDE.local.md` y `.claude/settings.local.json` en `.gitignore`; el hook `guarda_spec_previa` impide que Claude escriba `settings.local.json` | Lo personal no se versiona ni apaga las guardas | Solo `.gitignore` | #1, #3 · `.gitignore` [E4](docs/decisiones-detalle.md#4-guardas-de-claude-code) |
| 3 | Tests junto al código | Regla `.claude/rules/tests.md` con `paths: **/test_*.py`; `testpaths` de pytest | Se carga al tocar un test, en cualquier carpeta | Un `CLAUDE.md` por carpeta: se repite y diverge | #3, #12 · `.claude/rules/tests.md` [E4](docs/decisiones-detalle.md#4-guardas-de-claude-code) |
| 4 | Spec antes del código | Hook `PreToolUse` `guarda_spec_previa`: sin spec, plan y tareas del ticket no se escribe código protegido | Código, no instrucción (II) | Pedirlo en `CLAUDE.md` | #3 · `.claude/hooks/guarda_spec_previa.py` [E4](docs/decisiones-detalle.md#4-guardas-de-claude-code) |
| 5 | Sin datos con forma real | Hook `PreToolUse` `guarda_datos` del plugin (Luhn, dígito DIAN, credenciales) al escribir, ejecutar o publicar | Bloquea antes de que el dato exista | `detect-secrets` o `gitleaks`: no conocen NIT ni cédula | #3, #13 · `plugins/guardas-y-revision/hooks/` [E14](docs/decisiones-detalle.md#14-plugin-reutilizable-para-otros-equipos) |
| 6 | Secretos intocables | Permisos `deny` y hook `PreToolUse` `guarda_secretos`, también en la terminal | El permiso es la primera barrera; el hook, la garantía | Solo `deny`: Bash lo rodea | #1, #3 · `.claude/settings.json` [E4](docs/decisiones-detalle.md#4-guardas-de-claude-code) |
| 7 | Formato tras editar | Hook `PostToolUse` `formatear_python` (ruff); nunca bloquea | No depende del modelo | Formatear antes del commit | #3 · `.claude/hooks/formatear_python.py` [E4](docs/decisiones-detalle.md#4-guardas-de-claude-code) |
| 8 | Revisión independiente | Subagente `revisor-codigo` (`Read, Grep, Glob`) vía la skill `revisar-codigo` con `context: fork`; hook `PreToolUse` `guarda_pr` exige el veredicto del commit | Contexto aparte y solo lectura; la puerta es código | Un veredicto global, no por commit | #4 · `.claude/skills/revisar-codigo/` [E5](docs/decisiones-detalle.md#5-revisión-independiente-y-puerta-de-pr) |
| 9 | Cumplimiento de reglas | Subagente `auditor-cumplimiento` vía la skill `auditar-cumplimiento` (`context: fork`): evidencia por regla I.1–I.5 | Separa negocio de calidad | Un solo revisor para todo | #4, #19 · `.claude/agents/` [E5](docs/decisiones-detalle.md#5-revisión-independiente-y-puerta-de-pr) |
| 10 | Tickets sincronizados | Skill `siguiente-ticket`; comandos `/abrir-pr` y `/comentar-avance`; hooks de Spec Kit (instrucciones, no de Claude Code); MCP de GitHub limitado por el hook `PreToolUse` `guarda_mcp_github` (`projects_write` solo `update_project_item`); workflow «Item closed» | Nadie mueve tarjetas | GitHub Action propia | #2, #3 · `.claude/hooks/guarda_mcp_github.py` [E3](docs/decisiones-detalle.md#3-ciclo-de-tickets-automatizado) |
| 11 | Piezas para otro equipo | Plugin `guardas-y-revision` (subagente, skill y hook) en el marketplace del repositorio; aquí, deshabilitado | Dos comandos, sin rutas del proyecto | Usar aquí el hook del plugin | #13 · `.claude-plugin/` [E14](docs/decisiones-detalle.md#14-plugin-reutilizable-para-otros-equipos) |

## Sistema con el Agent SDK

- Coordinador (#6): delega con `delegar_frente`; cada subagente, solo su herramienta.
- Contexto explícito; listas espera al registro; el ciclo termina por `stop_reason`.
- Hooks del SDK (#7, #9, #10): las reglas I.1 a I.5 en código, que falla cerrado.
- Servidor MCP (#5): datos ficticios, descripciones sin ambigüedad, errores reintentables.
- Fallas (#8): error estructurado por frente; la cobertura la calcula el código.
- Chat (#11, #12): Streamlit; los indicadores salen de la traza, no del texto del modelo.
- Detalle: [E6](docs/decisiones-detalle.md#6-servidor-mcp-de-la-pasarela) a [E13](docs/decisiones-detalle.md#13-suite-de-los-siete-casos).

## Flujo de trabajo

- **Arranque** (#1, [E2](docs/decisiones-detalle.md#2-ciclo-manual-de-tickets-durante-la-transición)): #1 y #2 hicieron a mano el ciclo que automatizan #2 y #4; hasta el #3, formato y `.env` a mano.
- **Ramas** ([E16](docs/decisiones-detalle.md#16-flujo-de-ramas-por-ticket)): un ticket, una rama `NNN-nombre` desde `main` y un PR con `Closes #N` y merge commit.
- **Project**: «Item closed» pasa a Done al cerrarse el issue; los PR no están en el Project, así que «Pull request merged» no mueve nada (corrige FR-015 del #2 y la [E3](docs/decisiones-detalle.md#3-ciclo-de-tickets-automatizado)).

## Límites conocidos

- Las reglas valen para lo que pasa por el SDK con sus hooks ([E8](docs/decisiones-detalle.md#8-hooks-del-sdk-reglas-de-negocio-1-2-y-3)).
- Rodeos deliberados de las guardas y escrituras no reconocidas ([E4](docs/decisiones-detalle.md#4-guardas-de-claude-code)).
- La puerta garantiza que la revisión ocurrió, no que encontró todo ([E5](docs/decisiones-detalle.md#5-revisión-independiente-y-puerta-de-pr)).
- [Desviaciones](docs/decisiones-detalle.md#desviaciones-declaradas) de #10 a #12 y [límites del plugin](docs/decisiones-detalle.md#límites-del-plugin-pr-29).
- `settings.json` se recarga en caliente ([E14](docs/decisiones-detalle.md#14-plugin-reutilizable-para-otros-equipos)).
- [Sugerencias no atendidas](docs/decisiones-detalle.md#sugerencias-no-atendidas-de-los-pr) de los PR.
- `uv run pytest` tarda más de 5 min en Windows; latencia con Opus ([mejoras](docs/decisiones-detalle.md#mejoras-futuras)).
