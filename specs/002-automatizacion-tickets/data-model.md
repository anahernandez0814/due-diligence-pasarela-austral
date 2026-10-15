# Data Model: Automatización del ciclo de tickets en GitHub

El ticket no persiste datos propios: todo el estado vive en GitHub (issue, ítem del
Project, PR) y en git (rama, carpeta de specs). Este modelo describe esas entidades tal
como las lee y escribe el flujo.

## Entidades

### Ticket (issue de GitHub)

| Campo | Origen | Uso |
|-------|--------|-----|
| `number` | `issue_read get` | N; da NNN (tres dígitos) para la rama y la carpeta. |
| `title` | `issue_read get` | Fuente del nombre corto ([research.md](research.md), R7). |
| `body` | `issue_read get` | Insumo de `/speckit-specify`. |
| `state`, `state_reason` | `issue_read get` | Abierto para arrancar; `closed` + `completed` para el paso 0. |
| `closed_at`, `closed_by_pull_requests` | `issue_read get` | Datos del comentario de cierre. |
| comentarios | `issue_read get_comments` | Detección de marcadores. |

### Ítem del Project

Project #1 "Due Diligence - Pasarela Austral" del usuario `anahernandez0814`.

| Campo | Uso |
|-------|-----|
| `id` | Para `update_project_item`. |
| `content.number` | Enlace con el ticket. |
| `Status` | Todo, In Progress, In review, Done (nombres exactos). |
| `updated_at` | Evidencia del cambio automático a Done en el comentario de cierre. |

### Rama del ticket

- Nombre `NNN-<nombre-corto>`: NNN es el número del issue con tres dígitos y el nombre
  corto sigue la regla R7.
- Se crea desde `main` actualizado con `pull --ff-only`. Nunca hay commits en `main`.
- Validación de `/abrir-pr`: `^(\d{3})-[a-z0-9-]+$`; el número del issue es `int(NNN)`.

### Carpeta de specs del ticket

- `specs/NNN-<nombre-corto>/` con `spec.md`, `plan.md` y `tasks.md`, más los artefactos de
  plan (`research.md`, `data-model.md`, `contracts/`, `quickstart.md`, `checklists/`).
- `.specify/feature.json` apunta a ella tras `/speckit-specify`.
- Antes de crearla no existe ninguna carpeta `specs/NNN-*` con el mismo NNN.

### Pull request del ticket

- `head`: la rama del ticket; `base`: `main`.
- Título: `<título del issue> (#N)`.
- Descripción en español, con `Closes #N`.
- Como mucho uno abierto por rama.

### Comentario de avance

- Primera línea: `<!-- ciclo-tickets:<tipo> -->`, con `tipo` ∈ {inicio, especificado,
  plan, analyze, pr, cierre}.
- Contenido por tipo en [contracts/comentarios.md](contracts/comentarios.md).
- Duplicados: `inicio`, `pr` y `cierre` no se repiten; `especificado`, `plan` y `analyze`
  se amplían sobre el existente con una sección "Actualización <fecha>" que conserva el
  cuerpo anterior (clarify amplía el de specify).

## Transiciones del Status

```text
Todo ──(siguiente-ticket)──▶ In Progress ──(/abrir-pr)──▶ In review ──(merge + "Item closed")──▶ Done
  │                              │                            │                                  │
  └ comentario: —                └ inicio                     └ pr                               └ cierre (paso 0 del siguiente arranque)
                                 (+ especificado, plan y analyze por hooks mientras está In Progress)
```

| Transición | Quién la hace | Precondiciones | Comentario |
|------------|---------------|----------------|------------|
| Todo → In Progress | `siguiente-ticket` | Comprobaciones de R3 en verde | `inicio` (y `especificado` por el hook `after_specify`) |
| In Progress → In review | `/abrir-pr` | Spec, plan y tareas commiteados; árbol limpio; revisión previa sin bloqueantes; push correcto; sin PR abierto | `pr` |
| In review → Done | Workflow nativo "Item closed" | PR fusionado con `Closes #N` | `cierre`, lo publica el paso 0 del siguiente `siguiente-ticket` |

Ninguna transición se hace moviendo tarjetas a mano. Si el paso 0 encuentra un issue
cerrado que no está en Done, lo reporta y no lo mueve.

## Reglas de validación

- La opción de Status se busca por nombre exacto en `list_project_fields`; si no está, el
  flujo se detiene (no elige una parecida).
- El ticket elegido debe ser un issue abierto del repositorio, presente en el Project y en
  Todo.
- Ningún comentario incluye tokens, datos personales reales ni contenido de `.env`
  (principios VII y VIII).
