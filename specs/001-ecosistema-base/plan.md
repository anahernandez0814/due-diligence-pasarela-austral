# Implementation Plan: Ecosistema base de Claude Code

**Branch**: `001-ecosistema-base` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-ecosistema-base/spec.md` (issue #1)

## Summary

Dejar el repositorio listo para que cualquier persona que lo clone trabaje con las
convenciones del equipo y con el backlog del GitHub Project desde Claude Code, sin
credenciales en el repositorio. Se añaden:

- `CLAUDE.md` breve que importa la constitución.
- `.mcp.json` con el servidor MCP remoto oficial de GitHub. El token se toma de
  `GITHUB_PAT` y se habilitan los toolsets repos, issues, pull_requests y projects.
- Un proyecto Python 3.12 con uv, ruff y pytest, con tests junto al código en dos paquetes
  bajo `src/`.
- `.gitattributes` con LF y la normalización de los archivos ya versionados.
- README, DECISIONES.md y `docs/enunciado.md`.

La conexión al servidor remoto ya se verificó en la fase 0 (ver [research.md](research.md),
R1). La alternativa local por stdio queda documentada por si otra persona no puede usar el
servidor remoto.

## Technical Context

**Language/Version**: Python 3.12 (fijado con `requires-python` y `.python-version`)

**Primary Dependencies**: grupo de desarrollo `dev` con ruff y pytest. Sin dependencias de
ejecución en este ticket; `claude-agent-sdk` y Streamlit entran en los tickets del sistema.

**Storage**: N/A

**Testing**: pytest con `testpaths = ["src"]` y `--import-mode=importlib`; tests `test_*.py`
junto al módulo que prueban.

**Target Platform**: estaciones de desarrollo Windows, macOS y Linux con uv y gh instalados.

**Project Type**: repositorio de aplicación Python (src layout) con configuración de
Claude Code versionada.

**Performance Goals**: preparar el entorno y verificarlo en menos de 5 minutos con el
README (SC-001).

**Constraints**: ninguna credencial versionada (principio VIII). `CLAUDE.md` de 40
líneas como máximo, sin repetir la constitución. Documentación en español.

**Scale/Scope**: equipo pequeño y un solo GitHub Project ("Due Diligence - Pasarela
Austral").

No quedan NEEDS CLARIFICATION: todas las incógnitas se resolvieron en
[research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Verificación en este plan | Estado |
|-----------|--------|---------------------------|--------|
| I. Reglas de negocio | No | El ticket no implementa lógica de due diligence. | N/A |
| II. Garantizado vs. sugerido | Parcial | `CLAUDE.md` solo guía estilo y convenciones. Ninguna regla obligatoria depende de él; las guardas con hooks son del ticket #3. | Cumple con desviación temporal (ver abajo) |
| III. Arquitectura de agentes | No | Fuera de alcance. | N/A |
| IV. Herramientas y servidor MCP | No | El servidor MCP propio llega en un ticket posterior. Aquí solo se reserva su paquete `src/servidor_mcp/`. | N/A |
| V. Escalamiento | No | Fuera de alcance. | N/A |
| VI. Transparencia en la interfaz | No | Fuera de alcance. | N/A |
| VII. Solo datos ficticios | Sí | Los tests de humo y la documentación no contienen datos de personas ni de comercios. | Cumple |
| VIII. Sin credenciales | Sí | `.mcp.json` solo referencia `${GITHUB_PAT}`. Se mantienen `.env` en `.gitignore` y la denegación de lectura y edición de `.env` en `.claude/settings.json`. Antes del commit se busca que no haya tokens. | Cumple |
| IX. Spec first y trazabilidad | Sí | spec, plan y tareas en `specs/001-ecosistema-base/`, rama propia, PR con `Closes #1`, ticket en In Progress, comentarios en el issue. Convenciones en `CLAUDE.md` versionado; lo personal en `CLAUDE.local.md` y `.claude/settings.local.json`, ignorados. | Cumple |
| X. Calidad y pruebas | Sí | pytest con tests junto al código y ruff (check y format) configurados. Revisión previa al PR con un subagente de solo lectura en contexto separado (transición, ver DECISIONES.md). | Cumple con desviación temporal (ver abajo) |
| Restricciones técnicas | Sí | Python 3.12 con uv, pytest, ruff, documentación en español. | Cumple |

**Desviación temporal de los principios II y X**: el formateo con ruff tras cada edición (X)
y las garantías con hooks de Claude Code (II: protección de secretos, bloqueo de datos con
forma real y exigencia de especificación previa) llegan en el ticket #3. Mientras tanto:

- El formateo es manual (T018) y se ejecuta antes de cada commit.
- La protección de `.env` se apoya en la denegación de lectura y edición que ya existe en
  `.claude/settings.json`.

Esta desviación se recoge también en la entrada de transición de `DECISIONES.md` (T022).

**Resultado de la puerta**: cumple, con la desviación temporal declarada arriba.

**Re-evaluación tras la fase 1**: el diseño (contratos de `.mcp.json` y `pyproject.toml`,
`CLAUDE.md`) no introduce credenciales, datos reales ni reglas obligatorias apoyadas solo en
instrucciones. La puerta sigue cumpliendo.

## Project Structure

### Documentation (this feature)

```text
specs/001-ecosistema-base/
├── spec.md
├── plan.md              # Este archivo
├── research.md          # Fase 0
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/
│   ├── mcp-json.md      # Contrato de .mcp.json y alternativa stdio
│   └── pyproject.md     # Contrato de pyproject.toml (uv, ruff, pytest)
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
.
├── CLAUDE.md                  # Convenciones del equipo + @.specify/memory/constitution.md
├── README.md                  # Propósito, requisitos, GITHUB_PAT, verificación, enlaces
├── DECISIONES.md              # Decisiones del ecosistema (se completa en #14)
├── .mcp.json                  # Servidor MCP de GitHub (remoto, http)
├── .gitattributes             # * text=auto eol=lf
├── .python-version            # 3.12
├── pyproject.toml             # Proyecto uv, ruff, pytest
├── uv.lock                    # Generado por uv sync, versionado
├── .claude/settings.json      # + enabledMcpjsonServers: ["github"]
├── docs/
│   └── enunciado.md           # Copia literal del enunciado
└── src/
    ├── due_diligence/         # Sistema multi-agente (tickets posteriores)
    │   ├── __init__.py
    │   └── test_humo.py
    └── servidor_mcp/          # Servidor MCP propio (tickets posteriores)
        ├── __init__.py
        └── test_humo.py       # Mismo nombre a propósito: prueba importlib
```

**Structure Decision**: un solo proyecto Python con src layout y dos paquetes, que son las
dos piezas que exige la constitución: el sistema multi-agente y el servidor MCP propio.
Cada paquete tiene su `test_humo.py`. Que los dos archivos se llamen igual demuestra a la
vez que pytest descubre tests en varias carpetas y que `--import-mode=importlib` evita el
choque de nombres. No hay carpeta `tests/`.

## Complexity Tracking

Sin violaciones permanentes de la constitución. La única desviación es temporal (II y X,
hasta el ticket #3) y está declarada en la verificación de la constitución.
