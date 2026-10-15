# Due Diligence Pasarela Austral: convenciones del equipo

## Idioma

Mensajes al analista, documentación, commits y comentarios de issues en español.

## Flujo de trabajo

- Un ticket = un issue de GitHub = una rama `NNN-nombre-corto` creada desde `main`.
- Antes de escribir código: `spec.md`, `plan.md` y `tasks.md` del ticket en `specs/`.
- Nunca se commitea en `main`; el cambio entra por PR hacia `main` con `Closes #N`.
- Mueve el ticket a In Progress al empezar y a In review al abrir el PR.

## Comandos

- `uv sync`: prepara el entorno (Python 3.12).
- `uv run ruff format .` y `uv run ruff check .`: formato y lint.
- `uv run pytest`: suite de pruebas.

## Dónde vive cada cosa

- `src/`: código; cada `test_*.py` va junto al módulo que prueba.
- `specs/`: especificación, plan y tareas de cada ticket.
- `docs/`: enunciado de la prueba y documentación.
- `.specify/`: Spec Kit y la constitución.
- `.claude/`: configuración compartida de Claude Code.

## Lo personal queda fuera

Las preferencias personales van en `CLAUDE.local.md` y `.claude/settings.local.json`; no se
versionan.

## Constitución

Prevalece sobre esta guía:

@.specify/memory/constitution.md
