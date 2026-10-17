---
name: auditar-cumplimiento
description: Auditoría independiente de las cinco reglas de negocio de la constitución contra la spec, el código y los tests del cambio, en un contexto separado de la sesión que lo generó. Entrega estado y evidencia por regla. Solo lee, no corrige.
context: fork
agent: auditor-cumplimiento
argument-hint: "[carpeta del ticket, p. ej. specs/NNN-nombre]"
allowed-tools:
  - Bash(uv run --no-project --python 3.12 --quiet ${CLAUDE_PROJECT_DIR}/.claude/hooks/preparar_revision.py)
---

# Auditoría de cumplimiento de las reglas de negocio

Carpeta del ticket: $ARGUMENTS

Audita el cambio de esta rama frente a las cinco reglas de negocio del principio I de la
constitución. Eres independiente de la sesión que lo generó: no ves su conversación, y todo
lo que necesitas está aquí o lo lees tú.

## Contexto preparado

!`uv run --no-project --python 3.12 --quiet ${CLAUDE_PROJECT_DIR}/.claude/hooks/preparar_revision.py`

## Qué hacer

1. **Comprueba el contexto.** La salida de arriba debe empezar con la línea
   `CONTEXTO DE REVISIÓN`. Si no la ves (la preparación falló o está desactivada) o contiene
   una línea `CONTEXTO INCOMPLETO`, dilo en el reporte y declara `cobertura=incompleta`: no
   audites a ciegas ni supongas el contenido del cambio.
2. **Lee primero la constitución**, `.specify/memory/constitution.md`, con `Read`: el
   principio I son las cinco reglas que verificas, con su texto exacto. Después lee
   `spec.md`, `plan.md` y `tasks.md` de la carpeta del ticket.
3. **Decide cuáles de las cinco reglas aplican** al cambio: una regla aplica si la spec del
   ticket la cita o si el diff toca código que la implementa. Sin código de producción,
   las cinco son `no aplica`, con la razón.
4. **Verifica las que aplican** contra la spec, el código y los tests, con `Read` y `Grep`.
   Si la salida trae el diff completo, úsalo; si dice que se omitió por tamaño, lee los
   archivos de la lista, empezando por los de código y configuración.
   - Los archivos de `specs/NNN-*/` van marcados como **referencia**: léelos por secciones
     o con `Grep`, y **no cuentan para la cobertura**. Cuentan el código y la
     configuración.
   - Si la lista viene **agrupada por directorio**, no puedes saber qué archivos leer:
     declara `cobertura=incompleta`.
   - Si no puedes leer algún archivo de código o configuración de la lista, declara
     `cobertura=incompleta` y di cuál.
5. **Reporta** en español: la tabla de las cinco reglas, con su estado (`cumple`,
   `incumple`, `no aplica` o `no verificada`) y su evidencia con `archivo:línea`, y los
   hallazgos con su severidad. Una regla sin evidencia nunca es `cumple`. No corrijas ni
   propongas parches. No repitas valores sensibles: di el tipo y la ubicación.
6. **Cierra** con la línea de resumen, la última de tu reporte y con este formato exacto:

   ```text
   RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>
   ```
