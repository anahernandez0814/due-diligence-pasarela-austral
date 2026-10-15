---
description: Comenta en el issue del ticket lo especificado (tras /speckit-specify o /speckit-clarify), lo decidido (tras /speckit-plan) o lo encontrado (tras /speckit-analyze). Lo invocan los hooks de Spec Kit.
argument-hint: "especificado | plan | analyze"
allowed-tools:
  - Read
  - Bash(git branch:*)
  - mcp__github__issue_read
  - mcp__github__add_issue_comment
  - mcp__github__update_issue_comment
---

# Comentar el avance del ticket

Publica o amplía en el issue del ticket el comentario de avance de una fase de Spec Kit.
Lo ejecutan los hooks obligatorios de `.specify/extensions.yml` y también puede invocarse a
mano. Todo en español. Repositorio: `anahernandez0814/due-diligence-pasarela-austral`.

Contrato: `specs/002-automatizacion-tickets/contracts/comentar-avance.md`.

## Entrada

Argumento recibido: `$ARGUMENTS`

Debe ser exactamente `especificado`, `plan` o `analyze`. Con cualquier otro valor, incluido
el vacío, se detiene y responde: "El argumento no llegó o no es válido: se esperaba
especificado, plan o analyze. Recibido: «$ARGUMENTS»". No publica nada.

## Pasos

1. **Ticket**: lee `.specify/feature.json` y toma `feature_directory`, por ejemplo
   `specs/003-guardas-claude-code`. N es el número de NNN sin ceros a la izquierda.
   `git branch --show-current` debe empezar por el mismo `NNN-`; si no coincide, se detiene
   e informa.
2. **Contenido**, según el argumento:
   - `especificado`: resume `spec.md` de la carpeta:
     - historias con su prioridad;
     - requisitos clave (FR agrupados por tema);
     - criterios de éxito más relevantes;
     - supuestos;
     - si existe, la sección de aclaraciones que añade `/speckit-clarify`.
   - `plan`: resume `plan.md` y `research.md`:
     - decisiones técnicas numeradas, con su referencia R#;
     - el resultado del Constitution Check, con sus desviaciones;
     - lo pendiente.
   - `analyze`: toma el informe de `/speckit-analyze` de esta conversación. Pon una tabla
     con ID, severidad, hallazgo y cómo se resuelve cada uno, más la cobertura y la
     alineación con la constitución. Si no hubo hallazgos, lo hace constar.

   Nunca incluye tokens, credenciales, contenido de `.env` ni datos de personas o comercios
   reales.
3. **Publicar o ampliar**: `mcp__github__issue_read` con `method: get_comments`, recorriendo
   todas las páginas. El marcador es `<!-- ciclo-tickets:<argumento> -->`.
   - Si ya hay un comentario con ese marcador, `mcp__github__update_issue_comment`.
     Conserva **completo** el cuerpo anterior y añade al final:

     ```markdown

     ### Actualización <AAAA-MM-DD>
     <lo nuevo o lo que cambió respecto a lo anterior>
     ```

     Nunca reemplaza ni recorta lo publicado antes.
   - Si no existe, `mcp__github__add_issue_comment` con el marcador como primera línea y
     un encabezado según el argumento:
     - `especificado`: `## Lo especificado (`/speckit-specify`)`;
     - `plan`: `## Plan del ticket (`/speckit-plan`)`;
     - `analyze`: `## Análisis de consistencia (`/speckit-analyze`)`.

## Salida

Enlace al comentario e indicación de si se creó o se amplió.
