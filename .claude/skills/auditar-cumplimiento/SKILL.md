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

Pista de la carpeta del ticket: $ARGUMENTS

Audita el cambio de esta rama frente a las cinco reglas de negocio del principio I de la
constitución. Eres independiente de la sesión que lo generó: no ves su conversación, y todo
lo que necesitas está aquí o lo lees tú.

## Contexto preparado

!`uv run --no-project --python 3.12 --quiet ${CLAUDE_PROJECT_DIR}/.claude/hooks/preparar_revision.py`

## Qué cuenta para la cobertura

`cobertura=completa` significa que leíste todo lo que cuenta.

- **Cuentan**: el código y la configuración de la lista (`src/**`, `.claude/hooks/*.py`,
  `.claude/settings.json`, `.mcp.json`, `.claude/agents/`, `.claude/skills/` y
  `.claude/commands/`) y los tests (`test_*.py`). Se leen enteros; los tests, por secciones si
  hace falta. Cualquier otro archivo de la lista que no sea referencia también cuenta; los
  generados (`uv.lock`) se leen por secciones.
- **Son referencia y no cuentan**: `specs/NNN-*/`, `README.md`, `DECISIONES.md` y
  `.claude/rules/`. Léelos por secciones o con `Grep` para contrastar; leerlos a medias no
  reduce la cobertura.
- **No ejecutar tests nunca reduce la cobertura**: no tienes Bash. No lo reportes como falta
  ni como hallazgo.
- **Un archivo que cuenta y que leíste a medias** lo nombras en el reporte, con
  las líneas leídas, y entonces la cobertura es `incompleta`.
- Si no puedes leer un archivo que cuenta, si el contexto está incompleto o si la lista viene
  **agrupada por directorio** (no sabes qué archivos leer), la cobertura es `incompleta`.

## Plan de lectura

En este orden, y no reportes antes de terminarlo:

1. La lista de archivos del contexto: qué cambió y qué cuenta.
2. El código y la configuración, enteros.
3. Los tests, por secciones si hace falta.
4. Solo entonces, el reporte.

## Qué hacer

1. **Comprueba el contexto.** La salida de arriba debe empezar con la línea
   `CONTEXTO DE REVISIÓN`. Si no la ves (la preparación falló o está desactivada) o contiene
   una línea `CONTEXTO INCOMPLETO`, dilo en el reporte y declara `cobertura=incompleta`: no
   audites a ciegas ni supongas el contenido del cambio.
2. **Lee primero la constitución**, `.specify/memory/constitution.md`, con `Read`: el
   principio I son las cinco reglas que verificas, con su texto exacto. Después lee
   `spec.md`, `plan.md` y `tasks.md` de la carpeta del ticket: es la de la línea `Ticket:` del contexto,
   calculada con git a partir de la rama, que es la fuente fiable. El argumento de arriba
   solo es una pista; si indica otra carpeta, dilo en el reporte y declara
   `cobertura=incompleta`.
3. **Decide cuáles de las cinco reglas aplican** al cambio: una regla aplica si la spec del
   ticket la cita o si el diff toca código o tests que la implementan o la prueban. Sin
   código de producción ni tests de las reglas, las cinco son `no aplica`, con la razón. Un
   cambio que solo borra o debilita el test de una regla sí la toca: esa regla aplica, y sin
   evidencia vigente es `no verificada` y bloqueante.
4. **Verifica las que aplican** contra la spec, el código y los tests, con `Read` y `Grep`.
   Si la salida trae el diff completo, úsalo; si dice que se omitió por tamaño, lee los
   archivos de la lista, empezando por los de código y configuración.
   - Sigue el plan de lectura y las reglas de cobertura de arriba: los archivos de
     `specs/NNN-*/` van marcados como **referencia** en la lista y no cuentan.
5. **Reporta** en español: la tabla de las cinco reglas, con su estado (`cumple`,
   `incumple`, `no aplica` o `no verificada`) y su evidencia con `archivo:línea`, y los
   hallazgos con su severidad. Una regla sin evidencia nunca es `cumple`. No corrijas ni
   propongas parches. No repitas valores sensibles: di el tipo y la ubicación.
6. **Cierra** con la línea de resumen, la última de tu reporte y con este formato exacto:

   ```text
   RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>
   ```
