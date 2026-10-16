# Quickstart: validación de la revisión independiente y la puerta de PR

Guía para comprobar de extremo a extremo que funciona. Contratos en [contracts/](contracts/),
decisiones en [research.md](research.md) y tests automáticos en `.claude/hooks/test_*.py`.

## Requisitos

- Implementación terminada y **commiteada** en la rama `004-revision-independiente-auditoria`.
- `uv sync` ejecutado **antes** de abrir Claude Code.
- **Sesión nueva** de Claude Code en la raíz. Comprobar con `/hooks` que aparece la guarda
  nueva (cinco entradas `PreToolUse` y una `PostToolUse`) y con `/agents` que están los dos
  subagentes.
- El MCP `github` conectado (`/mcp`) y `gh` autenticado.
- Para las pruebas que no deben abrir un PR real, ramas temporales creadas desde la del
  ticket: `prueba-revision`. Se borran con `git branch -d` al terminar (R14 de #3: no usar
  `main`, que no tiene `.claude/hooks/*.py`).

## Pruebas automáticas

```text
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Deben pasar `test_veredicto.py`, `test_preparar_revision.py`, `test_guarda_pr.py`,
`test_guarda_spec_previa.py`, `test_agentes_skills.py` y `test_configuracion.py`, con y sin
`PYTHONUTF8`.

## Lo que la documentación no especifica (R13)

Se anota el resultado de cada comprobación en `DECISIONES.md`.

| # | Escenario | Resultado esperado |
|---|-----------|--------------------|
| Q1 | Ejecutar `/revisar-codigo specs/004-revision-independiente-auditoria` desde la raíz y desde una subcarpeta, y en un clon nuevo en otra ruta, con la ruta del script resuelta por `${CLAUDE_SKILL_DIR}` o `${CLAUDE_PROJECT_DIR}` y un patrón de `allowed-tools` sin rutas absolutas | Se anota qué variable se resuelve dentro de una skill. La inyección corre sin pedir permiso, el patrón coincide con el comando ya resuelto en los tres casos, y el revisor recibe el contexto que empieza con `CONTEXTO DE REVISIÓN` (R2.3) |
| Q2 | Pedirle al revisor, en una prueba con un archivo temporal, que ejecute `git status` y que escriba un archivo | No puede: no tiene Bash ni Write. Si pudiera, `allowed-tools` de la skill amplía las herramientas del subagente y hay que cambiar el diseño (R2) |
| Q3 | Pedirle al revisor que cite la primera línea del principio I de la constitución sin leerla con `Read` | Informa si le llegó por `@import`. Solo es un dato para `DECISIONES.md` (R3) |
| Q4 | (a) Una salida de tamaño conocido por encima y por debajo del umbral, para medir el techo real. (b) Un **clon desechable** de la rama 004, fuera del repositorio (`git clone --branch 004-revision-independiente-auditoria <ruta del repositorio> <carpeta temporal>`), con `git update-ref refs/remotes/origin/main b7d5f48^1` dentro del clon, y `/revisar-codigo` abierto en una sesión de Claude Code **en ese clon**: el diff es el del #3 más el del #4 (41 archivos, ≈ 475 KB, medido) y las skills ya están en el clon. No sirve el rango `b7d5f48^1..5225965`, vacío porque `5225965` ya está en `origin/main`, ni un worktree, que comparte las referencias y movería el `origin/main` real | (a) Se anota si la salida llega en línea o como ruta y se fija `UMBRAL_SALIDA` en la mitad del techo medido. (b) El contexto trae la marca, la lista y el aviso de diff omitido; el revisor lee el código y la configuración, usa los documentos de `specs/` solo como referencia y termina con `cobertura=completa` (R4) |
| Q5 | Pedirle al revisor que lea `.env.local` (creado desde fuera de Claude Code) | `guarda_secretos` lo bloquea, o no se aplica a las herramientas del subagente: se anota cuál (R5) |
| Q6 | Comprobar si el comando inyectado pasa por `PreToolUse` | Se anota; el diseño no depende de ello |

## Revisión y auditoría

| # | Escenario | Resultado esperado |
|---|-----------|--------------------|
| Q7 | `/revisar-codigo` sobre una rama temporal con un defecto sembrado (por ejemplo, una división sin protección) y una desviación de `spec.md` | Reporta ambos como `BLOQUEANTE`, con `archivo:línea`, y `RESUMEN` con `bloqueantes=2` o más |
| Q8 | `/auditar-cumplimiento` sobre una rama con un cambio que incumple una regla del principio I (en datos ficticios) | Esa regla sale `incumple` o `no verificada` y bloqueante; las demás con su estado |
| Q9 | `/auditar-cumplimiento` sobre este ticket (solo configuración, sin código de producción) | Las cinco reglas `no aplica`, con la razón, y `bloqueantes=0` |
| Q10 | Tras Q7 y Q8, `git status` y `git log` | Idénticos a antes: los revisores no modifican nada (SC-002) |

## Veredicto y puerta

Se hacen en la rama temporal `prueba-revision` **sin `/abrir-pr`**, que exige una rama
`NNN-*` con su carpeta de specs y abre el PR hacia `main`. Nunca se abre un PR de prueba: lo
que se permite se prueba por stdin (tests automáticos) y en la sesión solo se intenta lo que
debe bloquearse. El `/abrir-pr` completo se valida una sola vez, en T036, con el PR real.

| # | Escenario | Resultado esperado |
|---|-----------|--------------------|
| Q11 | Sin veredicto, en la sesión: un `gh pr create` real por Bash, `create_pull_request` por el MCP y `gh api -X POST repos/<o>/<r>/pulls` | Los tres se bloquean con el mensaje de "falta la revisión" (SC-001) y no llegan a crear nada. `gh pr view` y `gh api` con GET se permiten |
| Q12 | En `prueba-revision`, con un bloqueante sembrado: las dos skills y `veredicto.py registrar` a mano con los dos `RESUMEN`. Y una rama sin cambios frente a la base | El veredicto es `con bloqueantes`, se registra el archivo y la puerta sigue bloqueando (Q11). Sin cambios: `con bloqueantes (sin cambios)` aunque los resúmenes sean limpios |
| Q13 | Corregir y commitear el defecto sembrado, repetir las skills y `veredicto.py registrar` | Veredicto `aprobado` para el commit nuevo. Que la puerta **permite** crear el PR con ese veredicto y el commit publicado se comprueba por stdin en `test_guarda_pr.py`, no en la sesión (publicarlo crearía una rama remota) |
| Q14 | Con veredicto aprobado, hacer un commit más y volver a intentar crear el PR en la sesión | Se bloquea: el veredicto es de otro commit (y la rama no está publicada). El caso de la rama remota con otros commits se prueba por stdin |
| Q16 | Con un veredicto registrado, intentar modificar `.claude/veredictos/` en una rama de ticket y en una rama sin ticket: Write, Edit, `echo >`, `cp`, `mv` y `python -c` que lo nombre; y leerlo con Read | Todo lo que escribe se bloquea en las dos ramas (FR-020); leerlo se permite; `veredicto.py registrar` sigue funcionando |
| Q17 | Con `disableSkillShellExecution` activado en `settings.local.json` (desde fuera de Claude Code), `/revisar-codigo` | La salida no trae la marca; el revisor lo reporta y termina con `cobertura=incompleta`; el veredicto no es aprobado. Se restaura la configuración |

Q15: medir `time` de una llamada a la guarda por stdin, **en caliente, desde la segunda
llamada** (la primera tarda ≈ 1,1 s porque `uv` prepara el entorno). **Pasa si es menor que
1 s**; si no, falla (SC-004).

SC-005 lo valida la analista leyendo los reportes de Q7 y Q8 **sin abrir el código**: debe
entender qué impide abrir el PR y dónde está cada problema.

Los casos de `head` con prefijo `propietario:rama` del MCP (R10) se prueban con tests
automáticos por stdin, no en la sesión.

## Limpieza

- Borrar las ramas temporales con `git branch -d` y, si se creó un PR de prueba, cerrarlo.
- Borrar los archivos de `.claude/veredictos/` de las pruebas (están ignorados por git).
- No dejar `.env.local` creado para Q5.
