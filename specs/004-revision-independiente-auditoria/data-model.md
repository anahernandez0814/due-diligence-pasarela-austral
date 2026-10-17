# Data Model: Revisión independiente y auditoría de cumplimiento

No hay base de datos. Las entidades son los archivos de configuración y los datos que
intercambian las skills, `/abrir-pr` y la guarda. Detalle de cada decisión en
[research.md](research.md).

## Subagente

Archivo de `.claude/agents/`.

| Campo | Valores |
|-------|---------|
| `name` | `revisor-codigo` o `auditor-cumplimiento` |
| `tools` | exactamente `Read, Grep, Glob` (R5); sin `Agent`, sin Bash, sin escritura, sin MCP |
| `description` | qué revisa y que solo reporta |
| Cuerpo | el rol, el formato del reporte (R7) y la prohibición de proponer o aplicar cambios |

Regla: ningún subagente declara una herramienta que escriba, edite o ejecute (FR-003). Lo
verifica `test_agentes_skills.py`.

## Skill de revisión

`SKILL.md` en `.claude/skills/revisar-codigo/` y `.claude/skills/auditar-cumplimiento/`.

| Campo | Valores |
|-------|---------|
| `context` | `fork` |
| `agent` | el subagente homónimo (R1) |
| `allowed-tools` | solo el comando del script de preparación, con la ruta resuelta por una variable de la skill y sin rutas absolutas (R2) |
| `argument-hint` | la carpeta del ticket, por ejemplo `specs/NNN-nombre` |
| Cuerpo | la inyección del contexto (R6), las rutas de los documentos, la instrucción de leer la constitución (R3) y el formato del reporte |

Regla: `$ARGUMENTS` solo aparece en prosa, nunca dentro del comando inyectado (R2).

## Contexto de revisión

Lo que imprime `preparar_revision.py` y las skills inyectan.

| Elemento | Contenido |
|----------|-----------|
| Base | `git merge-base HEAD origin/main` |
| Archivos | lista de cambiados, con estado y estadísticas (`numstat`); los eliminados, marcados |
| Marca | primera línea fija: `CONTEXTO DE REVISIÓN`; si el subagente no la ve, `cobertura=incompleta` |
| Commit | `Commit: <sha completo de HEAD>`, justo después de `Rama:`; es el commit revisado |
| Diff | completo si **toda la salida** queda por debajo de `UMBRAL_SALIDA` (provisional, 30 000 bytes; Q4 lo ajusta); si no, una línea que dice que se omitió |
| Ticket | carpeta `specs/NNN-*/` y rutas de `spec.md`, `plan.md` y `tasks.md`; sus archivos van marcados como **referencia** y no cuentan para la cobertura |
| Constitución | ruta de `.specify/memory/constitution.md` |
| Estado | `CONTEXTO INCOMPLETO: <motivo>` si algo falla; el script termina siempre con 0 |

## Reporte de revisión

Lo que devuelve cada subagente. Texto en español.

| Parte | Contenido |
|-------|-----------|
| Hallazgos | cada uno con severidad (`BLOQUEANTE` o `SUGERENCIA`), ubicación `archivo:línea` y razón |
| Reglas (solo el auditor) | las cinco reglas del principio I, con estado (`cumple`, `incumple`, `no aplica`, `no verificada`), razón de cada "no aplica" y evidencia |
| `RESUMEN` | última línea: `RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa\|incompleta>` |

Reglas de validación (R7):

- La línea `RESUMEN` se lee con una expresión estricta; ausente o con otro formato, el
  reporte no es utilizable.
- `cobertura=incompleta` solo si algún archivo de la lista no se pudo leer.
- Una regla que aplica y no tiene evidencia es `no verificada` y cuenta como bloqueante.

## Veredicto

Archivo `.claude/veredictos/<sha>.json`, ignorado por git (R8).

| Campo | Valores |
|-------|---------|
| `commit` | sha completo; coincide con el nombre del archivo |
| `rama` | rama del ticket |
| `veredicto` | `aprobado` o `con bloqueantes` |
| `fecha` | UTC, ISO 8601 |
| `codigo`, `auditoria` | `{bloqueantes, sugerencias, cobertura}` de cada revisión |

Reglas:

- `aprobado` solo si las dos líneas `RESUMEN` son válidas, con `bloqueantes=0` y
  `cobertura=completa` (R7) **y el cambio frente a la base no está vacío**, comprobado con
  git por el registro y no por el reporte. Sin cambios: `con bloqueantes (sin cambios)`; sin
  base calculable: `con bloqueantes (sin base de comparación)`.
- El veredicto queda atado al commit **revisado**, que `/abrir-pr` guarda antes de lanzar las
  skills y pasa a `registrar --commit <sha>`. Si no coincide con `HEAD` al registrar, no se
  escribe nada. Un sha ausente, abreviado o no hexadecimal tampoco se acepta.
- Se registran los dos veredictos; la guarda solo acepta `aprobado`.
- Ninguna herramienta de Claude Code modifica el directorio, en ninguna rama (FR-020); solo lo
  escribe `veredicto.py registrar`. Leerlo está permitido.
- Un archivo por commit: un commit nuevo no tiene archivo y el veredicto anterior no vale.
- Archivo ilegible, con otro formato o con `commit` distinto del nombre: "sin veredicto".

Transiciones: un commit sin veredicto → `con bloqueantes` (se corrige y se commitea, y es otro
commit) o `aprobado` → PR creado. No hay estado intermedio ni caducidad por tiempo.

## Guarda de PR

Script `.claude/hooks/guarda_pr.py` registrado en `.claude/settings.json`.

| Campo | Valores |
|-------|---------|
| `evento` | `PreToolUse` |
| `matcher` | lista exacta `Bash\|PowerShell\|mcp__github__create_pull_request` (R10) |
| `efecto` | bloquear (salida 2 y motivo en stderr) o permitir (salida 0) |
| `fallo` | cerrado: excepción propia → salida 2, más `onFailure: "block"` |
| `timeout` | 10 s |

Reglas: solo lee stdin, el sistema de archivos y git; no escribe nada. El mensaje dice qué
falta y cómo obtenerlo, en español, sin repetir contenido del comando.
