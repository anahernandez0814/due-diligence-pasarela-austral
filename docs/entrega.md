# Entrega

Lista de verificación, comandos y guiones para entregar la prueba (#14). Los comandos se
ejecutan **después del merge del último PR**, desde `main` en GitHub. Ninguno lee ni muestra
`.env`, y ninguno imprime el valor de una credencial.

## Lista de verificación

- [ ] **Acceso de los evaluadores** al repositorio (colaboradores o visibilidad) y al GitHub
  Project (https://github.com/users/anahernandez0814/projects/1), comprobado con su usuario o
  en una ventana privada.
- [ ] **Visibilidad** (_pendiente de la analista_): la frase del README
  «el repositorio es privado y pide acceso» coincide con la visibilidad final; si el
  repositorio pasa a público, se corrige en el README.
- [ ] **Video de funcionamiento** enlazado en el README, en lugar de «_pendiente_», y probado en
  una ventana privada: se abre sin iniciar sesión ni pedir acceso.
- [ ] **El .zip se genera desde un clon limpio** (`git clone`), para que no entre ningún archivo
  ignorado o no versionado ([Generar el .zip](#generar-el-zip)).
- [ ] **El .zip incluye** `.git/` (el historial), `specs/` y `.specify/memory/`, y **no incluye**
  `.venv/`, `.env`, `CLAUDE.local.md`, `.claude/settings.local.json`, `resultados/`, cachés ni
  la bitácora personal `docs/bitacora-decisiones.md`.
- [ ] **El historial completo se revisó en busca de credenciales**, con los dos comandos de
  [Revisar credenciales](#revisar-credenciales-en-el-historial), sin hallazgos.
- [ ] **El .zip pesa 50 MB como máximo.**
- [ ] **El historial no se reescribió**: sin `rebase`, `--amend` publicado ni `push --force`.
  Desde el clon: `git merge-base --is-ancestor 35b0de1 origin/main && git merge-base
  --is-ancestor f9e82d6 origin/main && echo "Historial intacto"` (el primer commit y el de
  partida del #14 siguen en `main`).

## Generar el .zip

En una carpeta vacía fuera del repositorio de trabajo. **Windows (PowerShell)**, con el
`tar.exe` del sistema (Windows 10 o posterior), que con `-a` elige el formato zip por la
extensión. Se llama por su ruta completa: si el `PATH` tiene las herramientas Unix de Git, un
`tar.exe` a secas puede ser el GNU tar de Git, que no genera zip.

```powershell
$destino = Join-Path $env:TEMP "entrega-pasarela"
New-Item -ItemType Directory $destino | Out-Null
git clone https://github.com/anahernandez0814/due-diligence-pasarela-austral.git "$destino\due-diligence-pasarela-austral"
$tar = Join-Path $env:SystemRoot "System32\tar.exe"
& $tar -a -c -f "$destino\due-diligence-pasarela-austral.zip" -C $destino due-diligence-pasarela-austral
```

**macOS o Linux (bash)**:

```bash
destino="$(mktemp -d)"
git clone https://github.com/anahernandez0814/due-diligence-pasarela-austral.git "$destino/due-diligence-pasarela-austral"
(cd "$destino" && zip -qr due-diligence-pasarela-austral.zip due-diligence-pasarela-austral)
```

**Comprobar el contenido y el tamaño** (PowerShell; en bash, `unzip -l` y `du -h`):

```powershell
$zip = "$destino\due-diligence-pasarela-austral.zip"
$lista = & $tar -t -f $zip
foreach ($r in "/.git/", "/specs/", "/.specify/memory/") { "$r " + [bool]($lista -match [regex]::Escape($r)) }
$lista | Select-String -Pattern '/\.venv/|/\.env$|CLAUDE\.local\.md|settings\.local\.json|bitacora-decisiones|/resultados/'
"{0:N1} MB" -f ((Get-Item $zip).Length / 1MB)
```

Esperado: `True` en las tres carpetas, ninguna línea en la búsqueda de excluidos y 50 MB o
menos. Si pasa de 50 MB, se mira qué pesa con `git count-objects -vH` en el clon; no se borra
historia para reducirlo.

## Revisar credenciales en el historial

Desde la raíz del clon limpio, en Git Bash (Windows) o bash. Los dos comandos recorren
**todos los commits de todas las ramas** y solo imprimen el commit, el archivo y, en el
segundo, el tipo de dato; **nunca el valor**.

**1. Prefijos de credenciales** (claves de Anthropic y tokens de GitHub), con `git grep -l`,
que solo imprime `<commit>:<archivo>`:

<!-- bloque: revision-prefijos -->
```bash
hallazgos="$(git rev-list --all | xargs git grep -l -E 'sk-ant-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}')"
echo "${hallazgos:-Sin coincidencias.}"
```

**2. El detector de datos con forma real del proyecto** (tarjetas, NIT, cédulas y
credenciales; `plugins/guardas-y-revision/hooks/detector_datos.py`), sobre cada versión
distinta de cada archivo del historial:

<!-- bloque: revision-detector -->
```bash
DETECTOR="${DETECTOR:-plugins/guardas-y-revision/hooks}" uv run --no-project --python 3.12 python -I - <<'PY'
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.environ["DETECTOR"]))
from detector_datos import buscar  # devuelve solo (tipo, línea), nunca el valor


def git(*args, entrada=None):
    return subprocess.run(["git", *args], input=entrada, capture_output=True, check=True).stdout


rutas = {}
for linea in git("rev-list", "--all", "--objects").decode().splitlines():
    sha, _, ruta = linea.partition(" ")
    if ruta:
        rutas.setdefault(sha, ruta)
formato = "--batch-check=%(objectname) %(objecttype) %(objectsize)"
objetos = git("cat-file", formato, entrada="\n".join(rutas).encode()).decode().split()
hallazgos = 0
for sha, tipo, tamano in zip(objetos[::3], objetos[1::3], objetos[2::3]):
    if tipo != "blob" or int(tamano) > 2_000_000:
        continue
    datos = git("cat-file", "blob", sha)
    if b"\0" in datos[:8000]:
        continue
    for tipo_dato in sorted({t for t, _ in buscar(datos.decode("utf-8", "replace"))}):
        commit = git("log", "--all", "--format=%h", f"--find-object={sha}").decode().split()[-1]
        print(f"{commit}  {rutas[sha]}  {tipo_dato}")
        hallazgos += 1
print(f"Hallazgos: {hallazgos}")
PY
```

Esperado: «Sin coincidencias.» y «Hallazgos: 0». El 2026-10-19, en un clon limpio de la rama
del #14 (361 commits), los dos dieron 0, en unos 16 y 82 s.

**Con un hallazgo**, no se reescribe el historial (el enunciado lo prohíbe):

1. Se abre el archivo en ese commit fuera de una sesión de Claude Code y sin compartir la
   pantalla, para ver si es un dato ficticio que el detector confunde.
2. Si es una credencial real, se revoca en su servicio (consola de Anthropic o ajustes de
   GitHub) antes de entregar, y la analista decide cómo declararlo.

## Guion del video de funcionamiento

Máximo 5 minutos, con el sistema en el chat y sin explicar código. Preparación: `.env` con la
clave, el chat arrancado en modo normal y la tabla de los siete casos del README a mano. Cada
caso tarda de 25 a 55 s con el modelo; «Caso nuevo» entre uno y otro.

| Tiempo | Qué se muestra |
|--------|----------------|
| 0:00–0:15 | El chat abierto y qué es: un analista pide el due diligence de un comercio ficticio. |
| 0:15–0:50 | (a) alto riesgo: escalamiento a cumplimiento, informe `decide_cumplimiento`, «Completo». |
| 0:50–1:25 | (b) bajo riesgo: cuatro frentes cubiertos, `habilitar`, sin escalamiento. |
| 1:25–2:00 | (c) representante en listas: escalamiento por la coincidencia; no se habilita. |
| 2:00–2:35 | (g) fechas distintas: el informe muestra las dos fechas con su fuente, sin elegir. |
| 2:35–3:25 | (d) nombres casi idénticos: pide el identificador; con `CO-AM-0004`, sigue. |
| 3:25–4:10 | Reinicio con la caída de noticias, (f): «noticias: no cubierto», estado «Incompleto». |
| 4:10–4:55 | Reinicio en modo de demostración, (e): «Bloqueado por la regla I.1». |

## Guion del video de defensa

Máximo 15 minutos, hablando del código entregado. [DECISIONES.md](../DECISIONES.md) sirve de
índice.

**1. Ecosistema de Claude Code (0:00–5:00).**

- `CLAUDE.md` con el `@import` de la constitución, y `src/servidor_mcp/CLAUDE.md` como
  ejemplo de subdirectorio; lo personal en `CLAUDE.local.md` y `.claude/settings.local.json`.
- Reglas con `paths` en `.claude/rules/`.
- Hooks de `.claude/settings.json`: las cuatro guardas `PreToolUse`, el formato
  `PostToolUse` y los permisos `deny`. Se muestra un bloqueo en vivo, por ejemplo leer `.env`.
- Subagentes de solo lectura, las skills con `context: fork`, `allowed-tools` y
  `argument-hint`, y los comandos `/abrir-pr` y `/comentar-avance`.
- `.mcp.json` con GitHub (`GITHUB_PAT` del entorno) y la pasarela.
- El plugin con su marketplace y por qué aquí está deshabilitado.
- En cada pieza, la alternativa descartada (la columna de `DECISIONES.md`).

**2. Spec Kit, de la spec al código con el #7 (5:00–9:00).**

- La constitución (`.specify/memory/constitution.md`), principios I y II.
- `specs/007-hooks-sdk-reglas/`: `spec.md` (las reglas I.1 a I.3 como requisitos),
  `research.md` (lo medido del SDK), `plan.md` y `tasks.md`.
- El código, `src/due_diligence/hooks.py` y `reglas.py`, y sus tests.
- El issue #7 con sus comentarios de avance, el PR #23 y el Project.

**3. Sistema con el Agent SDK (9:00–15:00).**

- El coordinador (`coordinador.py`) y `delegar_frente` (`delegacion.py`): cada subagente con
  su propio `query()`, solo su herramienta (`allowed_tools` y `disallowed_tools`) y el contexto
  explícito de `contexto.py`.
- El paralelismo, y listas, que espera al registro; el fin del ciclo por `stop_reason`
  (`terminacion.py`).
- Los hooks de las reglas (`hooks.py`): I.1 y I.2 bloquean, el `Stop` exige escalar y todo
  falla cerrado.
- Las fallas y la cobertura parcial: el error estructurado y `cobertura.py`, con el caso (f).
- La procedencia y los conflictos (`informe.py`, `conflictos.py`) y el escalamiento con
  criterio (`reglas.py`).
- El diseño de las herramientas MCP (`src/servidor_mcp/`): las descripciones que separan una
  mención en noticias de una coincidencia en listas, y las varias coincidencias del registro.
