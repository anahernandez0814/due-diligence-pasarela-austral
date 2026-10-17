---
name: revisar-codigo
description: Revisión independiente del cambio de la rama, en un contexto separado de la sesión que lo generó. Calidad, errores y cumplimiento de la spec del ticket; reporta hallazgos bloqueantes y sugerencias con su ubicación. Solo lee, no corrige.
context: fork
agent: revisor-codigo
argument-hint: "[carpeta del ticket, p. ej. specs/NNN-nombre]"
allowed-tools:
  - Bash(uv run --no-project --python 3.12 --quiet ${CLAUDE_PROJECT_DIR}/.claude/hooks/preparar_revision.py)
---

# Revisión independiente del código

Carpeta del ticket: $ARGUMENTS

Revisa el cambio de esta rama frente a su base de fusión. Eres independiente de la sesión que
lo generó: no ves su conversación, y todo lo que necesitas está aquí o lo lees tú.

## Contexto preparado

!`uv run --no-project --python 3.12 --quiet ${CLAUDE_PROJECT_DIR}/.claude/hooks/preparar_revision.py`

## Qué hacer

1. **Comprueba el contexto.** La salida de arriba debe empezar con la línea
   `CONTEXTO DE REVISIÓN`. Si no la ves (la preparación falló o está desactivada) o contiene
   una línea `CONTEXTO INCOMPLETO`, dilo en el reporte y declara `cobertura=incompleta`: no
   revises a ciegas ni supongas el contenido del cambio.
2. **Lee la referencia.** Con `Read`, lee `spec.md`, `plan.md` y `tasks.md` de la carpeta del
   ticket y la constitución, `.specify/memory/constitution.md`. Son tu criterio: la spec
   dice qué se pidió, el plan y las tareas cómo, y la constitución lo que no se negocia.
3. **Revisa el cambio.** Si la salida trae el diff completo, revísalo. Si dice que el diff se
   omitió por tamaño, lee con `Read` y `Grep` los archivos de la lista, empezando por los de
   código y configuración.
   - Los archivos de `specs/NNN-*/` van marcados como **referencia**: léelos por secciones o
     con `Grep`, no hace falta leerlos enteros, y **no cuentan para la cobertura**. Cuentan
     el código y la configuración.
   - Si la lista viene **agrupada por directorio**, no puedes saber qué archivos leer:
     declara `cobertura=incompleta`.
   - Si no puedes leer algún archivo de código o configuración de la lista, declara
     `cobertura=incompleta` y di cuál.
4. **Reporta** en español, con el formato de tu rol: cada hallazgo en una línea con su
   severidad (`BLOQUEANTE` o `SUGERENCIA`), su ubicación `archivo:línea` y su razón. No
   corrijas ni propongas parches. No repitas valores sensibles: di el tipo y la ubicación.
5. **Cierra** con la línea de resumen, la última de tu reporte y con este formato exacto:

   ```text
   RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>
   ```
