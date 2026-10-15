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

Los tres comandos deben terminar sin errores; pytest ejecuta los tests de humo de `src/`.

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

**Opción B: PAT clásico.** Créalo en GitHub, en *Settings → Developer settings → Personal
access tokens (classic)*, con los scopes `repo` y `project`. Un PAT fine-grained queda como
posible mejora: no siempre permite dar acceso a los Projects de usuario.

**Definir la variable** a nivel de usuario y reiniciar la terminal, VS Code o Claude Code.
No escribas el token en la línea de comandos: quedaría en el historial del shell.

En Windows (PowerShell), con la opción A:

```powershell
[Environment]::SetEnvironmentVariable("GITHUB_PAT", (gh auth token), "User")
```

Con esta opción la variable guarda una copia del token. Si vuelves a ejecutar
`gh auth login` o `gh auth refresh`, repite el comando.

En Windows con un PAT clásico, pégalo cuando lo pida `Read-Host`, que no lo muestra ni lo
guarda en el historial:

```powershell
$s = Read-Host "PAT" -AsSecureString
[Environment]::SetEnvironmentVariable("GITHUB_PAT", [System.Net.NetworkCredential]::new('', $s).Password, "User")
```

En macOS o Linux con la opción A, añade esta línea al perfil del shell (`~/.bashrc`,
`~/.zshrc`). El token se lee en cada sesión, así que no se desactualiza:

```bash
export GITHUB_PAT="$(gh auth token)"
```

En macOS o Linux con un PAT clásico, guárdalo en el llavero del sistema y léelo desde el
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

**Comprobarlo.** En una sesión nueva de Claude Code en la raíz del repositorio, ejecuta
`/mcp`: `github` debe aparecer conectado, sin pedir aprobación.

**Si `github` falla con 401/403**, aplica la alternativa local por stdio descrita en
[specs/001-ecosistema-base/contracts/mcp-json.md](specs/001-ecosistema-base/contracts/mcp-json.md).
Necesita el binario `github-mcp-server` en el PATH. Configúrala solo para ti, en ámbito
local (`claude mcp add-json github '<json>' --scope local`); no modifiques ni commitees el
`.mcp.json` del equipo.

## Cómo se trabaja

Las convenciones del equipo están en [CLAUDE.md](CLAUDE.md) y se cargan solas en cada sesión
de Claude Code. Cada ticket es un issue del Project, con su propia rama, su especificación,
plan y tareas en [specs/](specs/), y un pull request que cierra el issue. Las preferencias
personales van en `CLAUDE.local.md` y `.claude/settings.local.json`, que git ignora.
