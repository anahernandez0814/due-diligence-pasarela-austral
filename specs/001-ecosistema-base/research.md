# Research: Ecosistema base de Claude Code

Fase 0 del plan del ticket #1. Cada punto recoge la decisión, su motivo y las
alternativas evaluadas.

## R1. Servidor MCP de GitHub: remoto por HTTP

- **Decision**: usar el servidor remoto oficial `https://api.githubcopilot.com/mcp/`, de tipo
  `http`, declarado en `.mcp.json` con las cabeceras `Authorization: Bearer ${GITHUB_PAT}` y
  `X-MCP-Toolsets: repos,issues,pull_requests,projects`.
- **Verificación temprana (2026-10-15)**: con el token de la CLI de GitHub (prefijo `gho_`,
  obtenido con `gh auth token`) en `GITHUB_PAT`, `initialize`
  respondió HTTP 200 y `tools/list` devolvió 42 herramientas, entre ellas `projects_list`,
  `projects_get` y `projects_write`. Con este token el servidor remoto no exigió suscripción
  de Copilot. La comprobación se repite en una sesión nueva de Claude Code durante la
  implementación (quickstart, paso 3).
- **Rationale**:
  - No requiere instalar binarios ni contenedores en cada máquina, lo que cumple la
    necesidad 1.
  - El toolset de projects se habilita de forma explícita, como exige el enunciado.
  - Claude Code expande `${VAR}` en `url` y `headers` de `.mcp.json`, así que el token
    nunca se escribe.
- **Alternatives considered**:
  - **Servidor local por stdio (alternativa documentada)**: binario oficial
    `github-mcp-server` de las releases de github/github-mcp-server, ejecutado con
    `github-mcp-server stdio`. Variables de entorno: `GITHUB_PERSONAL_ACCESS_TOKEN=${GITHUB_PAT}`
    y `GITHUB_TOOLSETS=repos,issues,pull_requests,projects`. Se usa si el servidor remoto
    responde 401/403 por la cuenta o la organización. Docker no está instalado en la
    máquina de referencia, así que se prefiere el binario a la imagen
    `ghcr.io/github/github-mcp-server`. Podman sí está disponible y serviría como segunda
    opción. Contrato en [contracts/mcp-json.md](contracts/mcp-json.md).
  - **Imagen Docker**: rechazada como opción por defecto porque añade un requisito de
    instalación.

## R2. Permisos de `GITHUB_PAT`

- **Decision**: `GITHUB_PAT` puede contener el token de la CLI de GitHub (`gh auth token`,
  prefijo `gho_`) o un PAT clásico. En ambos casos necesita los scopes `repo` y `project`.
  Se define como variable de entorno del usuario en el sistema operativo; nunca en `.env`
  ni en el repositorio.
- **Rationale**: `repo` cubre repositorios, issues y pull requests; `project` permite leer y
  escribir el Project v2 (mover tickets). Con una variable de usuario, Claude Code y gh la
  heredan sin archivos.
- **Alternatives considered**: PAT fine-grained. Los Projects de usuario no siempre se
  pueden otorgar con un PAT fine-grained, así que se descarta por ahora. Se documenta en el
  README como posible mejora.

## R3. Habilitar el servidor del proyecto sin pasos manuales

- **Decision**: añadir `"enabledMcpjsonServers": ["github"]` en `.claude/settings.json`,
  junto al bloque `env` y los permisos existentes.
- **Rationale**: sin esta clave, Claude Code pide aprobar cada servidor de `.mcp.json` la
  primera vez; con ella el servidor del equipo queda aprobado al clonar (necesidad 1). Se
  aprueba solo `github`, no todos los servidores.
- **Alternatives considered**: `enableAllProjectMcpServers: true`. Se descarta porque
  aprobaría cualquier servidor futuro sin revisión.

## R4. Proyecto Python con uv y src layout

- **Decision**: `pyproject.toml` con `requires-python = ">=3.12,<3.13"`, `.python-version`
  con `3.12`, backend de construcción `uv_build` y los dos módulos
  (`[tool.uv.build-backend] module-name = ["due_diligence", "servidor_mcp"]`).
  ruff y pytest van en `[dependency-groups] dev`, que `uv sync` instala por defecto.
  `uv.lock` se versiona.
- **Rationale**: con el paquete instalado en modo editable, los tests importan
  `due_diligence` y `servidor_mcp` sin manipular `sys.path`. El lock hace reproducible la
  preparación del entorno.
- **Alternatives considered**: `hatchling` como backend, válido pero una dependencia más
  de la cadena. `pythonpath = ["src"]` en pytest sin instalar el paquete, que queda como
  plan B si el backend multimódulo diera problemas.

## R5. Descubrimiento de tests junto al código

- **Decision**: `[tool.pytest.ini_options]` con `testpaths = ["src"]`,
  `python_files = ["test_*.py"]` y `addopts = ["--import-mode=importlib"]`. Dos
  `test_humo.py`, uno en cada paquete.
- **Rationale**: `testpaths` acota la búsqueda a donde vive el código y la recorre de forma
  recursiva por todas sus carpetas. Con `importlib` no se exigen nombres de archivo únicos
  ni `__init__.py` en las carpetas de tests. Los dos archivos con el mismo nombre son la
  prueba de ambas cosas: con el modo `prepend` por defecto, pytest fallaría con un error de
  módulo duplicado.
- **Alternatives considered**: carpeta `tests/` espejo, que contradice la constitución
  (principio X) y la necesidad 3. `rootdir_conftest` con rutas, innecesario.

## R6. ruff

- **Decision**: `[tool.ruff]` con `target-version = "py312"` y `line-length = 100`, y
  `[tool.ruff.lint] select = ["E", "F", "I", "UP", "B"]`. Comandos `uv run ruff check .` y
  `uv run ruff format .`.
- **Rationale**: es un conjunto de reglas conocido y estable que evita ruido. El formateo
  automático tras cada edición lo impone un hook (ticket #3), no esta configuración.
- **Alternatives considered**: `select = ["ALL"]`, rechazado porque genera demasiado ruido
  para un MVP.

## R7. Finales de línea

- **Decision**: `.gitattributes` con `* text=auto eol=lf` y, en el mismo commit,
  `git add --renormalize .`.
- **Rationale**: elimina los avisos LF/CRLF en Windows y deja el índice coherente. Los
  scripts `.ps1` de Spec Kit funcionan con LF.
- **Alternatives considered**: `core.autocrlf` por persona, rechazado porque no viaja con
  el repositorio.

## R8. CLAUDE.md, README y DECISIONES.md

- **Decision**:
  - **`CLAUDE.md`**: unas 40 líneas como máximo. Idioma, flujo de rama por ticket con PR a
    `main`, comandos uv, dónde vive cada cosa y la línea `@.specify/memory/constitution.md`.
  - **README**: propósito, requisitos (uv, gh), cómo definir `GITHUB_PAT` y sus scopes,
    verificación del entorno, enlace al GitHub Project y un hueco para el enlace al video.
    El enunciado exige ambos enlaces en la entrega.
  - **DECISIONES.md**: dos decisiones (cargar la constitución en cada sesión y el ciclo
    manual de transición); se completa en el ticket #14.
- **Rationale**: importar la constitución evita duplicarla y que diverja. Cargarla en cada
  sesión cuesta unas 190 líneas de contexto, pero garantiza que cualquier tarea parta de
  las reglas de negocio.
- **Alternatives considered**: leer la constitución bajo demanda desde una skill o una
  regla con `paths`. Se rechaza porque las reglas de negocio aplican a casi todo el
  trabajo y una carga condicional podría omitirlas.
