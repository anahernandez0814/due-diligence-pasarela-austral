# Contrato: cambios en `/abrir-pr`

Contrato original: [specs/002-automatizacion-tickets/contracts/abrir-pr.md](../../002-automatizacion-tickets/contracts/abrir-pr.md).
Este ticket reemplaza solo la **sección 2** ("Revisión previa") y ajusta las acciones; las
comprobaciones de la sección 1 no cambian. Decisión: [research.md](../research.md), R11.

## Orden nuevo

| Paso | Qué | Si falla |
|------|-----|----------|
| 1 | Comprobaciones de la sección 1 (sin cambios) | se detiene, sin push ni PR |
| 2 | `git fetch origin main` y `git fetch origin <rama>` (el segundo puede no existir aún) | se detiene si falla el de `main`, porque la base del diff sería la del `main` local |
| 3 | Skills `revisar-codigo` y `auditar-cumplimiento`, con la carpeta del ticket como argumento | un reporte ausente o sin `RESUMEN` válido cuenta como bloqueante (paso 4) |
| 3a | Antes de lanzar las skills, `git rev-parse HEAD` y se **guarda el sha** | se detiene |
| 4a | **Valida cada línea `RESUMEN`** antes de pasarla: solo si coincide exactamente con `RESUMEN: bloqueantes=<dígitos> sugerencias=<dígitos> cobertura=<completa\|incompleta>` (dígitos `0-9`, sin comillas posibles); en cualquier otro caso, `sin resumen` | nunca pasa texto del reporte que no cumpla el formato |
| 4 | `uv run --no-project --python 3.12 --quiet .claude/hooks/veredicto.py registrar --commit <sha guardado> --codigo '…' --auditoria '…'`, con la ruta **relativa** (la variable `${CLAUDE_PROJECT_DIR}` no existe en la herramienta Bash) y las dos líneas ya validadas entre comillas simples | con `con bloqueantes`: muestra los hallazgos, no hay push, ni PR, ni cambio de estado. Si sale con 2 porque `HEAD` cambió durante la revisión (mensaje `El commit cambió durante la revisión…`), no hay veredicto, no hay push ni PR, y se vuelve a ejecutar `/abrir-pr` |
| 5 | `git push -u origin <rama>` | se detiene sin PR |
| 6 | `create_pull_request` (la guarda lo comprueba), estado `In review`, comentario | como hoy |

Los pasos 3 y 4 sustituyen al subagente `Plan` de #2.

## `allowed-tools` de `/abrir-pr`

- Salen: `Agent` y `Bash(git diff:*)`.
- Entran: `Skill(revisar-codigo)`, `Skill(auditar-cumplimiento)`, `Bash(git rev-parse:*)` y
  `Bash(uv run --no-project --python 3.12 --quiet .claude/hooks/veredicto.py registrar:*)`,
  con la ruta relativa y literal (las reglas Bash se comparan con el texto literal del
  comando, research R2.5).
- Siguen: `git branch`, `git status`, `git cat-file`, `git log`, `git fetch`, `git push`, las
  herramientas de lectura y las del MCP de GitHub.

## Descripción del PR

La sección **Revisión previa** pasa a incluir:

- el veredicto consolidado y el commit al que corresponde (el sha guardado en el paso 3a);
- el `RESUMEN` de cada revisión;
- los hallazgos no bloqueantes y cómo se atendió cada uno.

## Salida

Además de lo actual: el veredicto, los dos resúmenes y, si se detuvo, los hallazgos
bloqueantes con su ubicación y la instrucción de corregir con commits nuevos y volver a
ejecutar `/abrir-pr` (un commit nuevo exige una revisión nueva).
