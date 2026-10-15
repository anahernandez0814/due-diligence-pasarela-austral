# Quickstart: validación del ciclo de tickets

Guía para comprobar que el flujo funciona.

- **Q1–Q9** se ejecutan antes del PR y no mueven tickets reales, salvo Q9, que abre el PR
  del propio ticket #2.
- **Q10 y Q11** se validan con el primer uso real, después del merge
  ([research.md](research.md), R10).

## Requisitos

- Sesión nueva de Claude Code en la raíz del repositorio, en la rama
  `002-automatizacion-tickets`, con el MCP `github` conectado (`/mcp`).
- `GITHUB_PAT` con los scopes `repo` y `project`.
- `/siguiente-ticket`, `/abrir-pr` y `/comentar-avance` aparecen en la lista de comandos.
- **Requisito previo de Q1**: los comentarios existentes ya tienen su marcador. Se añaden
  con `update_issue_comment`:
  - el comentario de cierre del issue #1, con `<!-- ciclo-tickets:cierre -->`;
  - el comentario de inicio del issue #2, con `<!-- ciclo-tickets:inicio -->`.

  El paso 0 corre en **cada** `/siguiente-ticket`, incluidas las pruebas negativas Q1 a
  Q4. Sin el marcador, la primera prueba publicaría un comentario de cierre duplicado en
  #1.

## Antes del PR

| # | Escenario | Cómo | Resultado esperado |
|---|-----------|------|--------------------|
| Q1 | Árbol sucio | Modificar un archivo sin commitearlo y ejecutar `/siguiente-ticket 3`. | Se detiene en la comprobación del árbol; #3 sigue en Todo, sin comentario ni rama nueva. Restaurar el archivo. |
| Q2 | Ticket que no está en Todo | `/siguiente-ticket 2` (#2 está en In Progress). | Se detiene diciendo que #2 no está en Todo; no cambia nada. |
| Q3 | Issue cerrado | `/siguiente-ticket 1`. | Se detiene diciendo que #1 está cerrado; no cambia nada. |
| Q4 | Argumento inválido | `/siguiente-ticket abc`. | Muestra el uso y se detiene. |
| Q5 | Paso 0 sin pendientes | Revisar el informe del paso 0 en Q1–Q4, que ya corren con el requisito previo cumplido. | En cada ejecución, el informe dice que no hay issues cerrados por verificar; #1 no recibe un comentario nuevo. |
| Q4b | Sesión intacta tras un rechazo | Después de Q2, Q3 y Q4, `git branch --show-current`. | Sigue en `002-automatizacion-tickets`: el ticket se rechaza antes de `git switch main`. |
| Q6 | Hook `after_analyze` con argumento | Repetir `/speckit-analyze`, que es de solo lectura. | Al final aparece `EXECUTE_COMMAND: comentar-avance analyze` y se ejecuta `/comentar-avance analyze`. El comentario `analyze` del issue #2 se actualiza, sin crear uno nuevo. **Si el comando dice que el argumento no llegó, aplicar el plan B** ([contracts/comentar-avance.md](contracts/comentar-avance.md)). |
| Q7 | `/comentar-avance especificado` | Invocarlo directamente en la rama del ticket. | Se actualiza el comentario `especificado` manual del issue #2 con "Actualizado: <fecha>"; no se crea uno nuevo. |
| Q8 | `/abrir-pr` sin artefactos | En una rama temporal `999-prueba-abrir-pr`, creada desde la rama del ticket, ejecutar `/abrir-pr`. | Se detiene porque no existe `specs/999-*`; no lanza la revisión, no hace push y no abre PR. Borrar la rama temporal. |
| Q9 | `/abrir-pr` real | En `002-automatizacion-tickets`, ejecutar `/abrir-pr`. | Lanza la revisión previa sobre el diff contra `main`. Si hay bloqueantes, se detiene: se corrigen y se repite. Si no, abre el PR hacia `main` con `Closes #2` y la sección "Revisión previa" con el veredicto; #2 pasa a "In review" y recibe el comentario `pr`. |

Además, antes del PR:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Los tres terminan sin errores. El ticket no añade Python; esto confirma que no se rompió
nada.

## Después del merge (primer uso real)

| # | Escenario | Cómo | Resultado esperado |
|---|-----------|------|--------------------|
| Q10 | Cierre de #2 por el paso 0 | En `main`, ejecutar `/siguiente-ticket`. | Antes del arranque, comenta el cierre de #2 con el marcador `cierre`, porque está en Done por "Item closed". Si no estuviera en Done, lo reporta y no lo mueve. |
| Q11 | Arranque positivo y hook `after_specify` | La misma ejecución de Q10. | Toma #3, el menor en Todo, y lo pasa a "In Progress" con el comentario `inicio`. Crea la rama `003-guardas-claude-code` y `specs/003-guardas-claude-code/spec.md`, y `.specify/feature.json` apunta a esa carpeta. Al terminar `/speckit-specify`, el hook `after_specify` publica el comentario `especificado` en #3; la skill no publica otro. No hay commits en `main`. |

Si Q10 o Q11 fallan, se reporta en el issue #2 y la corrección entra en un ticket nuevo,
nunca como cambio en la rama ya fusionada.

## Recuento SC-003

Al cerrar #2, su issue debe tener los seis marcadores:

- `inicio`, añadido al comentario manual;
- `especificado`;
- `plan`;
- `analyze`;
- `pr`;
- `cierre`.
