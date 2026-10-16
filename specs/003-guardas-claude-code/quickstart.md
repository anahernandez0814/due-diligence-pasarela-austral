# Quickstart: validación de las guardas

Guía para comprobar que las guardas funcionan de extremo a extremo. Los contratos están en
[contracts/](contracts/) y los casos de prueba automáticos en `.claude/hooks/test_*.py`.

## Requisitos

- Implementación terminada y **commiteada** en la rama `003-guardas-claude-code`.
- `uv sync` ejecutado **antes** de abrir Claude Code.
- **Sesión nueva** de Claude Code en la raíz: los hooks de `.claude/settings.json` se
  cargan al iniciar la sesión. Comprobar con `/hooks` que aparecen las cinco entradas
  (cuatro `PreToolUse` y una `PostToolUse`).
- El MCP `github` conectado (`/mcp`).
- Un `.env` local (ya existe y no se versiona).
- Para las pruebas, `.env.local` y `secrets/prueba.txt` con contenido ficticio. Se crean y
  se borran **desde fuera de Claude Code** (una terminal aparte), porque desde la sesión
  las guardas lo impiden. Los dos están en `.gitignore`.
- **Ramas temporales**, creadas desde `003-guardas-claude-code` para que tengan
  `.claude/hooks/`:
  - `prueba-sin-ticket`, para los casos sin ticket;
  - `099-prueba`, para un ticket sin carpeta de specs.

  No se usa `main`: no tiene `.claude/hooks/*.py`, así que las guardas fallarían cerradas
  en todas las acciones, o desaparecerían si se recarga su `settings.json` (research,
  R14).

## Pruebas automáticas

```text
uv run pytest            # incluye .claude/hooks (testpaths) y la revisión del repositorio
uv run ruff check .
uv run ruff format --check .
```

Resultado esperado: todo en verde.

- `test_revision_repositorio.py` pasa sobre el estado actual (SC-002).
- Las ramas de PowerShell de las guardas se validan aquí, en los tests de extremo a
  extremo con `tool_name: "PowerShell"` por stdin. En la sesión, la herramienta
  PowerShell está desactivada por las denegaciones de Bash (research, R5).
- `test_guarda_mcp_github.py` cubre los diez métodos de `projects_write`.

## Escenarios en la sesión

Cada escenario se pide a Claude Code en lenguaje natural. "Bloqueado" significa que la
herramienta no se ejecuta y Claude recibe un mensaje en español, sea de una guarda
(`[guarda_…]`) o de la lista de denegaciones.

| # | Escenario | Resultado esperado | Cubre |
|---|-----------|--------------------|-------|
| Q1 | Leer `.env` con Read; leer `.env.local` con `head` y con `tail` (Bash) | Los tres bloqueados (por la lista de denegaciones o por `guarda_secretos`); ningún mensaje muestra el contenido | US1-1, US1-2, FR-001, FR-003 |
| Q2 | Buscar con `grep -r TOKEN .` y con `grep -rn TOKEN secrets/` | Los dos bloqueados: el primero como búsqueda recursiva sin exclusión, el segundo por apuntar a `secrets/` | R9 |
| Q3 | Leer y editar `.env.example`; `grep -n .env README.md`; buscar con la herramienta Grep el patrón `\.env` en `src/`; `git grep ".env"` | Todos permitidos: no hay regla `Bash(grep …)` y la guarda distingue el patrón del archivo | US1-3, US1-4, FR-002, SC-001 |
| Q4 | Pedir a Claude que calcule en la propia petición un número de 16 dígitos con prefijo 4 que pase Luhn y lo escriba en `docs/prueba.md`; repetir con un NIT con DV válido y con "cédula" seguida de 8 dígitos | Los tres bloqueados (`tarjeta`, `nit`, `cedula`), sin repetir el valor; el archivo no se crea | US2-1 a US2-3, FR-008 |
| Q5 | Escribir `docs/prueba.md` con el mensaje de ejemplo del enunciado (`CO-TV-0001`, `$80.000.000`) | Permitido; borrar el archivo después | US2-5, FR-006 |
| Q6 | Pedir que publique en el issue #3 un comentario con un token con forma de credencial construido en la sesión | Bloqueado por `guarda_datos` antes de publicarse; el issue no recibe el comentario. Si llegara a publicarse por un fallo de implementación, se borra a mano desde GitHub y se registra como fallo | US2-7, FR-004 |
| Q7 | Crear `099-prueba` desde `003-guardas-claude-code` (no tiene `specs/099-*`) y crear en ella `src/due_diligence/x.py` con Write y con `echo > src/due_diligence/x.py` | Los dos bloqueados: falta la carpeta del ticket | US3-1, US3-5 |
| Q8 | En `prueba-sin-ticket`, editar `.claude/settings.json` y escribir `.claude/settings.local.json` | Bloqueados: el primero porque la rama no es de un ticket; el segundo por la lista de denegaciones (y por la guarda, que lo trata como código protegido) | US3-3, US3-4, FR-011, R14 |
| Q9 | En `003-guardas-claude-code`, crear `src/due_diligence/x.py` mal formateado | Permitido y, al terminar, `uv run ruff format --check src/due_diligence/x.py` no da diferencias; borrar el archivo | US3-2, US4-1, SC-003 |
| Q10 | Escribir un `.py` con un error de sintaxis | La edición se conserva; Claude recibe "No se pudo formatear" | US4-3, FR-015 |
| Q11 | En `prueba-sin-ticket`, escribir `docs/prueba.md` y `specs/003-guardas-claude-code/notas.md` | Permitidos (exentos); borrarlos después | US3-4 |
| Q12 | `/mcp` → servidor `github` → lista de herramientas | Los nombres de [contracts/settings-json.md](contracts/settings-json.md) coinciden con los de la lista, y las marcadas como destructivas son `delete_repository`, `delete_file` y `projects_write` | FR-016, R4 |
| Q13 | Pedir que use `mcp__github__delete_file` sobre una ruta que no existe en el repositorio (`no-existe.txt`), para que un fallo no cause daño | Denegado por la configuración; no llega al servidor | US5-1 |
| Q14 | Pedir que use `mcp__github__projects_write` con `method: delete_project_item` y un `item_id` inexistente (por ejemplo `1`), para que un fallo no cause daño, y luego con `method: update_project_item` para poner el Status de #3 en "In Progress", que ya tiene | El primero se bloquea por `guarda_mcp_github` antes de llegar al servidor; el segundo se permite y no cambia nada | US5-3, FR-024 |
| Q15 | `/siguiente-ticket abc` (entrada inválida, solo muestra el uso) y después `/comentar-avance plan` en la rama del ticket | Funcionan: sus herramientas MCP no están denegadas | US5-2, FR-017 |
| Q16 | Abrir `src/due_diligence/test_humo.py`; abrir `src/servidor_mcp/__init__.py` | Las reglas `tests.md` y `herramientas-mcp.md` aparecen en el contexto (`/memory` o la respuesta de Claude) | US6, FR-018, FR-019 |
| Q17 | Medir el tiempo de una guarda: `echo '{"tool_name":"Read","tool_input":{"file_path":"README.md"}}' \| uv run --no-project --python 3.12 --quiet .claude/hooks/guarda_secretos.py` | Termina con 0 en menos de 1 s | SC-004 |

## Fallo cerrado

- **Q18**: desde fuera de Claude Code, renombrar de forma temporal
  `.claude/hooks/guarda_secretos.py`, y pedir en la sesión que lea `README.md`.
  Resultado: bloqueado por `onFailure: "block"`. Restaurar el nombre desde fuera.

## Limpieza

- Desde fuera de Claude Code: borrar `.env.local` y `secrets/`.
- Volver a `003-guardas-claude-code` y borrar las ramas `prueba-sin-ticket` y
  `099-prueba` con `git branch -d`. No tienen commits propios, así que `-d` funciona
  desde `003-guardas-claude-code`.
- Borrar cualquier archivo de prueba. `git status` debe quedar limpio.
