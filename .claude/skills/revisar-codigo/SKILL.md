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

Pista de la carpeta del ticket: $ARGUMENTS

Revisa el cambio de esta rama frente a su base de fusión. Eres independiente de la sesión que
lo generó: no ves su conversación, y todo lo que necesitas está aquí o lo lees tú.

## Contexto preparado

!`uv run --no-project --python 3.12 --quiet ${CLAUDE_PROJECT_DIR}/.claude/hooks/preparar_revision.py`

## Qué cuenta para la cobertura

`cobertura=completa` significa que leíste todo lo que cuenta.

- **Cuentan**: el código y la configuración de la lista (`src/**`, `.claude/hooks/*.py`,
  `.claude/settings.json`, `.mcp.json`, `.claude/agents/`, `.claude/skills/` y
  `.claude/commands/`) y los tests (`test_*.py`). Se leen enteros; los tests, por secciones si
  hace falta. Cualquier otro archivo de la lista que no sea referencia también cuenta.
- **Son referencia y no cuentan**: `specs/NNN-*/`, `README.md`, `DECISIONES.md`, `docs/`,
  `.claude/rules/` y los archivos generados por herramientas (`uv.lock`). Léelos por secciones
  o con `Grep` para contrastar; leerlos a medias no reduce la cobertura.
- **Un archivo movido** aparece en su ruta nueva con la marca
  `[movido desde <ruta anterior>, similitud N %]`. Léelo en la ruta nueva: cuenta como
  cualquier otro y, si se movió con cambios, el contexto trae su diff o dice que no cabe. La
  ruta anterior ya no existe y no cuenta como archivo sin leer.
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
   revises a ciegas ni supongas el contenido del cambio.
2. **Lee la referencia.** La carpeta del ticket es la de la línea `Ticket:` del contexto,
   calculada con git a partir de la rama: es la fuente fiable. El argumento de arriba solo
   es una pista; si indica otra carpeta, dilo en el reporte y declara
   `cobertura=incompleta`. Con `Read`, lee `spec.md`, `plan.md` y `tasks.md` de esa carpeta
   y la constitución, `.specify/memory/constitution.md`. Son tu criterio: la spec dice qué
   se pidió, el plan y las tareas cómo, y la constitución lo que no se negocia.
3. **Revisa el cambio.** Si la salida trae el diff completo, revísalo. Si dice que el diff se
   omitió por tamaño, lee con `Read` y `Grep` los archivos de la lista, empezando por los de
   código y configuración.
   - Sigue el plan de lectura y las reglas de cobertura de arriba: los archivos de
     `specs/NNN-*/` van marcados como **referencia** en la lista y no cuentan.
   - Un archivo marcado `[movido desde …]` se lee en su ruta nueva; la anterior no se busca.
4. **Reporta** en español, con el formato de tu rol: cada hallazgo en una línea con su
   severidad (`BLOQUEANTE` o `SUGERENCIA`), su ubicación `archivo:línea` y su razón. No
   corrijas ni propongas parches. No repitas valores sensibles: di el tipo y la ubicación.
5. **Cierra** con la línea de resumen, la última de tu reporte y con este formato exacto:

   ```text
   RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>
   ```
