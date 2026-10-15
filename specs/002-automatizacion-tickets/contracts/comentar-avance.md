# Contrato: comando `/comentar-avance` y `.specify/extensions.yml`

## `.claude/commands/comentar-avance.md`

### Frontmatter

```yaml
description: Comenta en el issue del ticket lo especificado (tras /speckit-specify o /speckit-clarify), lo decidido (tras /speckit-plan) o lo encontrado (tras /speckit-analyze). Lo invocan los hooks de Spec Kit.
argument-hint: "especificado | plan | analyze"
allowed-tools:
  - Read
  - Bash(git branch:*)
  - mcp__github__issue_read
  - mcp__github__add_issue_comment
  - mcp__github__update_issue_comment
```

### Entrada

`$ARGUMENTS` = `especificado`, `plan` o `analyze`. Con cualquier otro valor, incluido el
vacío, se detiene e informa que el argumento no llegó. Eso es lo que verifican los
escenarios Q6 y Q7 del [quickstart](../quickstart.md).

### Pasos

1. Saca la carpeta del ticket de `.specify/feature.json` y N de su prefijo NNN. Si no
   coincide con la rama actual, se detiene.
2. Arma el contenido según el argumento:
   - `especificado`: resumen de `spec.md`:
     - historias con su prioridad;
     - requisitos clave;
     - supuestos;
     - si existe, la sección de aclaraciones que añade `/speckit-clarify`.
   - `plan`: decisiones de `plan.md` y `research.md`, resultado del Constitution Check y
     pendientes.
   - `analyze`: hallazgos del informe de `/speckit-analyze` de esta conversación, con su
     severidad, y cómo se resuelve cada uno. Si no hubo hallazgos, lo hace constar.
3. Lee los comentarios con `get_comments`:
   - Si existe uno con el mismo marcador, lo actualiza con `update_issue_comment`:
     conserva el cuerpo anterior completo y añade al final una sección
     `### Actualización <fecha>` con lo nuevo. Así, `/speckit-clarify` amplía el
     comentario `especificado` en vez de publicar otro, y un analyze repetido no borra los
     hallazgos anteriores ni cómo se resolvieron.
   - Si no existe, lo crea con `add_issue_comment`.

### Salida

Enlace al comentario y si se creó o se actualizó.

## `.specify/extensions.yml`

```yaml
installed: []
hooks:
  after_specify:
    - extension: ciclo-tickets
      command: comentar-avance especificado
      enabled: true
      optional: false
      priority: 10
      prompt: "Comentar en el issue lo especificado"
      description: "Comentario de lo especificado tras /speckit-specify (FR-022)"
      condition: null
  after_clarify:
    - extension: ciclo-tickets
      command: comentar-avance especificado
      enabled: true
      optional: false
      priority: 10
      prompt: "Actualizar en el issue lo especificado con las aclaraciones"
      description: "Actualiza el comentario de lo especificado tras /speckit-clarify (FR-022)"
      condition: null
  after_plan:
    - extension: ciclo-tickets
      command: comentar-avance plan
      enabled: true
      optional: false
      priority: 10
      prompt: "Comentar en el issue lo decidido en el plan"
      description: "Comentario de avance tras /speckit-plan (FR-008)"
      condition: null
  after_analyze:
    - extension: ciclo-tickets
      command: comentar-avance analyze
      enabled: true
      optional: false
      priority: 10
      prompt: "Comentar en el issue los hallazgos del análisis"
      description: "Comentario de avance tras /speckit-analyze (FR-009)"
      condition: null
```

- `optional: false`: el comando de Spec Kit emite `EXECUTE_COMMAND` y le pide al modelo
  que lo ejecute sin preguntar.
- `condition: null`: el hook es siempre ejecutable; Spec Kit no evalúa condiciones en el
  agente.
- **Alcance de la garantía**: estos hooks son instrucciones que el modelo ejecuta al
  terminar el comando de Spec Kit. No son hooks de Claude Code. Mejoran la constancia,
  porque la instrucción viaja con el comando, pero no garantizan la ejecución
  ([research.md](../research.md), R4).
- **Quién publica "especificado"**: `siguiente-ticket` invoca `/speckit-specify`, y el
  comentario lo publica su hook `after_specify`. La skill no lo publica.
- **Plan B** si el argumento no llega: tres comandos sin argumento,
  `comentar-especificado`, `comentar-plan` y `comentar-analyze`, con la misma lógica.
