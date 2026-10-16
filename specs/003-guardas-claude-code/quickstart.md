# Quickstart: validación de las guardas

Guía para comprobar que las guardas funcionan de extremo a extremo. Los contratos están en
[contracts/](contracts/) y los casos de prueba automáticos en `.claude/hooks/test_*.py`.

## Requisitos

- Implementación terminada en la rama `003-guardas-claude-code`, con `uv sync` hecho.
- **Sesión nueva** de Claude Code en la raíz: los hooks de `.claude/settings.json` se
  cargan al iniciar la sesión. Comprobar con `/hooks` que aparecen las cuatro entradas.
- El MCP `github` conectado (`/mcp`).
- Un `.env` local (ya existe y no se versiona). Para las pruebas se crean además
  `.env.local` y `secrets/prueba.txt` con contenido ficticio, y se borran al terminar.
  Los dos están en `.gitignore`.

## Pruebas automáticas

```text
uv run pytest            # incluye .claude/hooks (testpaths) y la revisión del repositorio
uv run ruff check .
uv run ruff format --check .
```

Resultado esperado: todo en verde. `test_revision_repositorio.py` pasa sobre el estado
actual (SC-002).

## Escenarios en la sesión

Cada escenario se pide a Claude Code en lenguaje natural. "Bloqueado" significa que la
herramienta no se ejecuta y Claude recibe el mensaje `[guarda_…]` en español.

| # | Escenario | Resultado esperado | Cubre |
|---|-----------|--------------------|-------|
| Q1 | Leer `.env` con Read; leer `.env.local` con `head` (Bash) y con `Get-Content` (PowerShell) | Los tres bloqueados (por la lista de denegaciones o por `guarda_secretos`); ningún mensaje muestra el contenido | US1-1, US1-2, FR-001, FR-003 |
| Q2 | Buscar con `grep -r TOKEN .` y con `Get-ChildItem -Recurse \| Select-String TOKEN` | Bloqueados como búsqueda recursiva | R9 |
| Q3 | Leer y editar `.env.example`; buscar con la herramienta Grep el patrón `\.env` en `src/`; `git grep ".env"` | Permitidos | US1-3, US1-4, FR-002 |
| Q4 | Pedir a Claude que calcule en la propia petición un número de 16 dígitos con prefijo 4 que pase Luhn y lo escriba en `docs/prueba.md`; repetir con un NIT con DV válido y con "cédula" seguida de 8 dígitos | Los tres bloqueados (`tarjeta`, `nit`, `cedula`), sin repetir el valor; el archivo no se crea | US2-1 a US2-3, FR-008 |
| Q5 | Escribir `docs/prueba.md` con el mensaje de ejemplo del enunciado (`CO-TV-0001`, `$80.000.000`) | Permitido; borrar el archivo después | US2-5, FR-006 |
| Q6 | Pedir que publique en el issue #3 un comentario con un token con forma de credencial construido en la sesión | Bloqueado por `guarda_datos` antes de publicarse; el issue no recibe el comentario | US2-7, FR-004 |
| Q7 | En una rama temporal `099-prueba` sin `specs/099-*`, crear `src/due_diligence/x.py` con Write y con `echo > src/due_diligence/x.py` | Los dos bloqueados: falta la carpeta del ticket | US3-1, US3-5 |
| Q8 | En `main` (sin commitear nada), editar `.claude/settings.json` | Bloqueado: la rama no es de un ticket | US3-3, US3-4, FR-011 |
| Q9 | En `003-guardas-claude-code`, crear `src/due_diligence/x.py` mal formateado | Permitido y, al terminar, `uv run ruff format --check src/due_diligence/x.py` no da diferencias; borrar el archivo | US3-2, US4-1, SC-003 |
| Q10 | Escribir un `.py` con un error de sintaxis | La edición se conserva; Claude recibe "No se pudo formatear" | US4-3, FR-015 |
| Q11 | Escribir `docs/prueba.md` o `specs/003-guardas-claude-code/notas.md` en `main` | Permitido (exento); borrar después | US3-4 |
| Q12 | `/mcp` → servidor `github` → lista de herramientas | Los nombres de [contracts/settings-json.md](contracts/settings-json.md) coinciden con los de la lista, y las marcadas como destructivas son `delete_repository`, `delete_file` y `projects_write` | FR-016, R4 |
| Q13 | Pedir que use `mcp__github__delete_file` sobre un archivo cualquiera | Denegado por la configuración; no llega al servidor | US5-1 |
| Q14 | `/siguiente-ticket abc` (entrada inválida, solo muestra el uso) y después `/comentar-avance plan` en la rama del ticket | Funcionan: sus herramientas MCP no están denegadas | US5-2, FR-017 |
| Q15 | Abrir `src/due_diligence/test_humo.py`; abrir `src/servidor_mcp/__init__.py` | Las reglas `tests.md` y `herramientas-mcp.md` aparecen en el contexto (`/memory` o la respuesta de Claude) | US6, FR-018, FR-019 |
| Q16 | Medir el tiempo de una guarda: `echo '{"tool_name":"Read","tool_input":{"file_path":"README.md"}}' \| uv run --no-project --python 3.12 --quiet .claude/hooks/guarda_secretos.py` | Termina con 0 en menos de 1 s | SC-004 |

Al terminar, borrar `.env.local`, `secrets/`, la rama `099-prueba` y cualquier archivo de
prueba. `git status` debe quedar limpio.

## Fallo cerrado

- Q17: renombrar de forma temporal `.claude/hooks/guarda_secretos.py` desde fuera de
  Claude Code y pedir que lea `README.md`. Resultado: bloqueado por `onFailure: "block"`.
  Restaurar el nombre.
