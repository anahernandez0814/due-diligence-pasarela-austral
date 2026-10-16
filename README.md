# Due Diligence Pasarela Austral

Sistema multi-agente en Python con el Claude Agent SDK para el due diligence de comercios de
la pasarela de pagos ficticia **Pasarela Austral**. Lo usa un analista interno de la
pasarela: un coordinador delega en subagentes especializados (registro mercantil, listas
restrictivas, noticias y riesgo de categoría) y entrega un informe con fuentes, o escala el
caso a un oficial de cumplimiento. Todos los datos son ficticios.

- **GitHub Project (backlog)**: https://github.com/users/anahernandez0814/projects/1
- **Video de funcionamiento**: _pendiente_
- **Requisitos de la prueba**: [docs/enunciado.md](docs/enunciado.md)
- **Principios del proyecto**: [constitución](.specify/memory/constitution.md)
- **Decisiones**: [DECISIONES.md](DECISIONES.md)

## Requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/): gestiona Python 3.12 y las
  dependencias; no hace falta instalar Python aparte.
- [GitHub CLI (gh)](https://cli.github.com/), con sesión iniciada (`gh auth login`).
- [Claude Code](https://docs.claude.com/en/docs/claude-code), para trabajar con las
  convenciones del equipo y el backlog.

## Preparar el entorno

```bash
git clone https://github.com/anahernandez0814/due-diligence-pasarela-austral.git
cd due-diligence-pasarela-austral
uv sync
```

## Verificar el entorno

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Los tres comandos deben terminar sin errores; pytest ejecuta los tests de `src/` y de
`.claude/hooks/`.

## Token de GitHub para Claude Code (`GITHUB_PAT`)

Claude Code lee y actualiza el GitHub Project con el servidor MCP oficial de GitHub
(configurado en [.mcp.json](.mcp.json)). La credencial se toma de la variable de entorno del
sistema `GITHUB_PAT`; **nunca se escribe en el repositorio ni en `.env`**.

`GITHUB_PAT` puede ser el token de la CLI de GitHub o un PAT clásico. En ambos casos necesita
los scopes `repo` y `project`.

**Opción A: token de la CLI de GitHub.**

```bash
gh auth refresh -s project   # añade el scope project si falta
gh auth status               # muestra los scopes del token
```

**Opción B: PAT clásico.** Créelo en GitHub, en *Settings → Developer settings → Personal
access tokens (classic)*, con los scopes `repo` y `project`. Un PAT fine-grained queda como
posible mejora: no siempre permite dar acceso a los Projects de usuario.

**Definir la variable** a nivel de usuario y reiniciar la terminal, VS Code o Claude Code.
No escriba el token en la línea de comandos: quedaría en el historial del shell.

En Windows (PowerShell), con la opción A:

```powershell
[Environment]::SetEnvironmentVariable("GITHUB_PAT", (gh auth token), "User")
```

Con esta opción la variable guarda una copia del token. Si vuelve a ejecutar
`gh auth login` o `gh auth refresh`, repita el comando.

En Windows con un PAT clásico, péguelo cuando lo pida `Read-Host`, que no lo muestra ni lo
guarda en el historial:

```powershell
$s = Read-Host "PAT" -AsSecureString
[Environment]::SetEnvironmentVariable("GITHUB_PAT", [System.Net.NetworkCredential]::new('', $s).Password, "User")
```

En macOS o Linux con la opción A, añada esta línea al perfil del shell (`~/.bashrc`,
`~/.zshrc`). El token se lee en cada sesión, así que no se desactualiza:

```bash
export GITHUB_PAT="$(gh auth token)"
```

En macOS o Linux con un PAT clásico, guárdelo en el llavero del sistema y léalo desde el
perfil, en vez de dejarlo en texto plano.

En macOS, `-w` sin valor pide el token sin mostrarlo:

```bash
security add-generic-password -a "$USER" -s GITHUB_PAT -w
export GITHUB_PAT="$(security find-generic-password -s GITHUB_PAT -w)"   # en el perfil
```

En Linux, con libsecret:

```bash
secret-tool store --label=GITHUB_PAT service github_pat
export GITHUB_PAT="$(secret-tool lookup service github_pat)"   # en el perfil
```

**Comprobarlo.** En una sesión nueva de Claude Code en la raíz del repositorio, ejecute
`/mcp`: `github` debe aparecer conectado, sin pedir aprobación.

**Si `github` falla con 401/403**, aplique la alternativa local por stdio descrita en
[specs/001-ecosistema-base/contracts/mcp-json.md](specs/001-ecosistema-base/contracts/mcp-json.md).
Necesita el binario `github-mcp-server` en el PATH. Configúrela solo para usted, en ámbito
local (`claude mcp add-json github '<json>' --scope local`); no modifique ni commitee el
`.mcp.json` del equipo.

## Guardas del entorno

Claude Code trabaja con cuatro guardas y un hook de formato, registrados en
[.claude/settings.json](.claude/settings.json). Las decisiones están en la entrada 4 de
[DECISIONES.md](DECISIONES.md).

- **`guarda_secretos`**: bloquea leer, buscar, editar o escribir `.env`, `.env.*` (salvo
  `.env.example`), `*.key` y `secrets/`, también desde la terminal y desde código en línea.
- **`guarda_datos`**: bloquea escribir, ejecutar o publicar en GitHub tarjetas, NIT,
  cédulas o credenciales con forma real.
- **`guarda_spec_previa`**: bloquea escribir, borrar o restaurar código protegido
  (`src/**/*.py`, `.claude/hooks/`, `.claude/settings.json`, `.claude/settings.local.json`,
  `.mcp.json` y el plugin) si la rama no es de un ticket o le faltan la spec, el plan o
  las tareas. `.claude/settings.local.json`, que no se versiona y puede desactivar las
  guardas, se bloquea en cualquier rama; solo se edita fuera de Claude Code.
- **`guarda_mcp_github`**: limita `projects_write` del MCP de GitHub a mover tarjetas
  (`update_project_item`).
- **`formatear_python`**: formatea con ruff cada `.py` escrito o editado; nunca bloquea.

Las guardas requieren `uv` en el `PATH`. Se cargan al iniciar la sesión y suelen
activarse también al guardar `settings.json`; ante la duda, reinicie la sesión.

- Ejecute `uv sync` antes de abrir Claude Code.
- Con las guardas activas, no cambie a una rama sin `.claude/hooks/`; si ocurre, reinicie
  la sesión.

## Cómo se trabaja

Las convenciones del equipo están en [CLAUDE.md](CLAUDE.md) y se cargan solas en cada sesión
de Claude Code. Cada ticket es un issue del Project, con su propia rama, su especificación,
plan y tareas en [specs/](specs/), y un pull request que cierra el issue. Las preferencias
personales van en `CLAUDE.local.md` y `.claude/settings.local.json`, que git ignora.

### Ciclo de un ticket

```text
/siguiente-ticket → specify → (clarify) → plan → tasks → analyze → implement → (converge) → /abrir-pr → merge
```

- **`/siguiente-ticket [N]`**: hace tres cosas.
  - Registra el cierre de los tickets ya fusionados.
  - Toma el siguiente ticket en Todo, o el #N, y lo pasa a In Progress.
  - Comenta el inicio en el issue y crea la rama `NNN-nombre-corto` y `specs/NNN-*`.
- **Hooks de `.specify/extensions.yml`**: al terminar specify, clarify, plan y analyze,
  `/comentar-avance` deja en el issue lo especificado, lo decidido y lo encontrado.
- **`/abrir-pr`**:
  - Comprueba que la spec, el plan y las tareas están commiteados.
  - Ejecuta la revisión previa.
  - Abre el PR con `Closes #N` y pasa el ticket a In review.
- **Done**: lo hace el workflow "Item closed" del Project al fusionar. El siguiente
  `/siguiente-ticket` registra ese cierre en el issue. Tras el merge del último ticket,
  ejecútelo una vez más para registrarlo.
