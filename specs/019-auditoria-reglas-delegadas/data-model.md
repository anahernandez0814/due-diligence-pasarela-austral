# Modelo de datos: Auditoría: reglas delegadas a otro ticket y uv.lock como referencia

Este ticket no guarda datos nuevos: cambia el texto que gobierna a dos subagentes y a sus
skills. Las "entidades" son los conceptos que ese texto usa y los archivos donde viven.

## Regla de negocio (existente, sin cambios)

Cada una de las cinco del principio I de la constitución (`I.1` a `I.5`). Estado en la
auditoría, uno de cuatro, sin estados nuevos (R2):

| Estado | Significado | ¿Bloquea? |
|--------|-------------|-----------|
| `cumple` | evidencia con `archivo:línea` en código y tests | no |
| `incumple` | el cambio la contradice o la debilita | sí |
| `no aplica` | no aplica al cambio, con la razón | no |
| `no verificada` | aplica y no hay evidencia | sí |

## Delegación (concepto nuevo, solo en el texto)

Constancia **en la spec del ticket** de que una regla la cumple otro ticket.

| Campo | Regla |
|-------|-------|
| Regla | una de `I.1` a `I.5`, citada en la spec |
| Ticket responsable | número con `#N` (p. ej. `#7`); sin número no es delegación (FR-004) |
| Razón en el reporte | «delegada al ticket #N en la spec» |

Validación: el auditor no consulta GitHub; no comprueba que `#N` exista ni que cubra la regla
(límite 1 de R8).

Transiciones de estado de una regla ante un cambio:

```text
delegada con número ──(el diff no la toca ni la contradice)──▶ no aplica (con razón)
delegada con número ──(el diff la contradice o debilita)─────▶ incumple (bloqueante)
cualquier regla     ──(el diff borra o debilita su código o test; sin evidencia vigente)─▶ no verificada (bloqueante)
citada sin número   ──────────────────────────────────────────▶ aplica (como asignada a este ticket)
```

## Archivo de referencia (ampliado)

Archivo que la revisión consulta para contrastar y que no cuenta para la cobertura. Antes:
`specs/NNN-*/`, `README.md`, `DECISIONES.md`, `.claude/rules/`. Ahora, además, los archivos
generados por herramientas: `uv.lock`. Leerlos a medias no reduce la cobertura.

## Archivos de la puerta

| Archivo | Rol | Bloques que debe tener igual |
|---------|-----|------------------------------|
| `.claude/agents/revisor-codigo.md` | agente de revisión de código | cobertura |
| `.claude/skills/revisar-codigo/SKILL.md` | skill de revisión de código | cobertura |
| `.claude/agents/auditor-cumplimiento.md` | agente de auditoría | cobertura y aplicabilidad |
| `.claude/skills/auditar-cumplimiento/SKILL.md` | skill de auditoría | cobertura y aplicabilidad |

"Igual" se mide con el test de coherencia (`contracts/test-coherencia.md`), tras normalizar
espacios y saltos de línea.

## Fuera del modelo (no cambian)

`veredicto.py`, `guarda_pr.py`, `preparar_revision.py` y sus tests; el formato de la línea
`RESUMEN`; el veredicto por commit.
