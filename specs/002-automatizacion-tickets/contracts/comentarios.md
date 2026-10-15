# Contrato: comentarios de avance en el issue

Todos en español. La primera línea es el marcador invisible; el resto es Markdown visible.
Ningún comentario incluye tokens, datos reales ni contenido de `.env`.

| Tipo | Lo publica | Duplicados | Contenido mínimo |
|------|------------|------------|------------------|
| `inicio` | `siguiente-ticket` | No se repite | Rama, carpeta de specs y siguiente paso. |
| `especificado` | `/comentar-avance especificado`, desde los hooks `after_specify` y `after_clarify` | Se amplía con una sección "Actualización" que conserva lo anterior (clarify amplía el de specify) | Historias con prioridad, requisitos clave, supuestos y aclaraciones, si las hay. |
| `plan` | `/comentar-avance plan`, desde el hook `after_plan` | Se amplía, conservando lo anterior | Decisiones técnicas, Constitution Check y pendientes. |
| `analyze` | `/comentar-avance analyze`, desde el hook `after_analyze` | Se amplía, conservando lo anterior | Hallazgos con severidad y cómo se resuelve cada uno, o "sin hallazgos". |
| `pr` | `/abrir-pr` | No se repite | Enlace al PR; lo especificado, lo decidido y lo pendiente; veredicto de la revisión previa; Status "In review". |
| `cierre` | Paso 0 de `siguiente-ticket` | No se repite | PR que lo cerró, `closed_at`, Status Done y `updated_at` del ítem; pendientes que pasan a otros tickets. |

## Plantillas

```markdown
<!-- ciclo-tickets:inicio -->
Se inicia el ticket. Rama `NNN-nombre-corto`, creada desde `main` actualizado; se ejecuta
`/speckit-specify` para generar la especificación en `specs/NNN-nombre-corto/`.

Siguiente: `/speckit-clarify` si la spec queda con marcadores de aclaración; si no,
`/speckit-plan` cuando la spec esté lista.
```

```markdown
<!-- ciclo-tickets:especificado -->
## Lo especificado (`/speckit-specify`)

- **Historias**: P1 …; P2 …; P3 …
- **Requisitos clave**: FR-… …
- **Supuestos**: …
- **Aclaraciones** (si se ejecutó `/speckit-clarify`): …
```

```markdown
<!-- ciclo-tickets:cierre -->
## Cierre del ticket

- **Issue #N**: cerrado (`completed`) el <closed_at> por el merge del PR #M (`Closes #N`).
- **GitHub Project**: Status Done; el ítem se actualizó el <updated_at>, por el workflow
  "Item closed".

Verificado sin mover tarjetas a mano.
```

Las plantillas de `plan`, `analyze` y `pr` siguen la estructura "Lo decidido / Lo
encontrado / Lo pendiente" de los comentarios de los issues #1 y #2.

## Recuento (SC-003)

Un ticket cerrado con este flujo cumple SC-003 si su issue tiene los seis marcadores
distintos: `inicio`, `especificado`, `plan`, `analyze`, `pr` y `cierre`.

- El issue #1 es anterior al flujo: solo recibe el marcador `cierre`, que se añade a su
  comentario existente.
- El issue #2 recibe los marcadores en sus comentarios manuales. El de inicio se edita
  para añadirlo.
