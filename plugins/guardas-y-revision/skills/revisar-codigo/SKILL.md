---
name: revisar-codigo
description: Revisión independiente del cambio de la rama frente a su base, en un contexto separado de la sesión que lo generó. Calidad, errores y, si el repositorio tiene la spec del ticket, su cumplimiento; reporta hallazgos bloqueantes y sugerencias con su ubicación. Solo lee, no corrige.
context: fork
agent: guardas-y-revision:revisor-codigo
argument-hint: "[carpeta de specs del ticket, opcional]"
allowed-tools:
  - Bash(uv run --no-project --python 3.12 --quiet "${CLAUDE_PLUGIN_ROOT}/scripts/contexto_revision.py")
---

# Revisión independiente del código

Pista de la carpeta del ticket: $ARGUMENTS

Revisa el cambio de esta rama frente a su base de fusión. Eres independiente de la sesión que
lo generó: no ves su conversación, y todo lo que necesitas está aquí o lo lees tú.

## Contexto preparado

!`uv run --no-project --python 3.12 --quiet "${CLAUDE_PLUGIN_ROOT}/scripts/contexto_revision.py"`

## Qué hacer

1. **Comprueba el contexto.** La salida de arriba debe empezar con la línea
   `CONTEXTO DE REVISIÓN`. Si no la ves (la preparación falló o está desactivada) o contiene
   una línea `CONTEXTO INCOMPLETO`, dilo en el reporte y declara `cobertura=incompleta`: no
   revises a ciegas ni supongas el contenido del cambio.
2. **Lee la referencia, si existe.**
   - Si el contexto trae `Ticket: specs/…/`, esa carpeta (calculada con git a partir de la
     rama) es la fuente fiable: lee con `Read` su `spec.md`, `plan.md` y `tasks.md`. El
     argumento de arriba solo es una pista; si indica otra carpeta, dilo en el reporte y
     declara `cobertura=incompleta`.
   - Si trae `Constitución: <ruta>`, léela: lo que no se negocia.
   - Si dice `Ticket: no aplica`, revisa calidad y errores y di en el reporte que no hubo spec
     contra la que contrastar; eso **no** reduce la cobertura.
3. **Revisa el cambio.** Si la salida trae el diff completo, revísalo. Si dice que el diff se
   omitió por tamaño, lee con `Read` y `Grep` los archivos de la lista, empezando por los de
   código y configuración. Sigue el plan de lectura y las reglas de cobertura de tu rol. Un
   archivo marcado `[movido desde …]` se lee en su ruta nueva; la anterior no se busca.
4. **Reporta** en español, con el formato de tu rol: cada hallazgo en una línea con su
   severidad (`BLOQUEANTE` o `SUGERENCIA`), su ubicación `archivo:línea` y su razón. No
   corrijas ni propongas parches. No repitas valores sensibles: di el tipo y la ubicación.
5. **Cierra** con la línea de resumen, la última de tu reporte y con este formato exacto:

   ```text
   RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>
   ```
