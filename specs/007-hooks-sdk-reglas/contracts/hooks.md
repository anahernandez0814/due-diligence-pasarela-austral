# Contrato: hooks del caso por agente

Interfaz interna entre el código del producto y el Agent SDK. La construye `hooks.HooksDelCaso(estado,
eventos, entorno)`; el caso la consulta con `.coordinador()` y `.subagente(frente)`, que devuelven el valor
del parámetro `hooks` de `ClaudeAgentOptions` (`{evento: [HookMatcher(...)]}`).

Verificado con el SDK 0.2.168 (research R1 a R3).

## Forma de las entradas que lee cada hook

| Evento | Campos que se usan | Notas |
|--------|--------------------|-------|
| `PreToolUse` | `tool_name`, `tool_input` (dict) | `tool_response` no existe |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response` | `str` (JSON) en stdio; `list` de bloques `{type, text}` en proceso. Se lee con `ejecutor.interpretar_resultado(tool_response, False)` |
| `PostToolUseFailure` | `tool_name`, `tool_input`, `error` (`str` con el JSON del error) | Se lee con `interpretar_resultado(error, True)`. Es la única vía de un error estructurado |
| `Stop` | `stop_hook_active`, `last_assistant_message` | `stop_hook_active` no se usa como contador |

## Salidas permitidas

| Salida | Efecto medido |
|--------|---------------|
| `{}` | La acción sigue |
| `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": <motivo>}}` | La herramienta no se ejecuta; el modelo recibe `tool_result` con `is_error=true` y `PreToolUse:<herramienta> hook error: <motivo>` |
| `{"decision": "block", "reason": <motivo>}` (solo `Stop`) | El coordinador continúa; el motivo llega al modelo; gasta un turno |

Cualquier otra forma, y cualquier excepción, **deja pasar la acción**: por eso las salidas se construyen
con `permitir()`, `denegar()` y `bloquear_cierre()` y todo hook se envuelve con `fallar_cerrado`.

## Hooks por agente

### Coordinador

| Evento | Matcher (nombre completo) | Regla | Qué hace |
|--------|---------------------------|-------|----------|
| `PreToolUse` | `mcp__delegacion__delegar_frente` | I.1 | Si `tool_input.frente` es `listas`: `reglas.permite_delegar_listas(estado)`; se deniega si el registro está `sin_iniciar`, `rechazado` o `no_terminado`, o `terminado` sin comercio único; se permite si está `en_curso` o con comercio. Cualquier otro frente: permite |
| `PreToolUse` | `mcp__pasarela__registrar_informe` | I.2, I.3 | `reglas.evaluar_informe(estado, tool_input)`; deniega con todos los motivos o permite |
| `PostToolUse` | `mcp__pasarela__escalar_a_cumplimiento` | I.2, I.3 | Si el resultado es `caso_escalado`: `libro.escalamientos += causas_vigentes`; evento `escalamiento_registrado` |
| `PostToolUseFailure` | `mcp__pasarela__escalar_a_cumplimiento` | — | Solo deja constancia; el escalamiento no cuenta |
| `Stop` | (sin matcher) | I.2, I.3 | `reglas.evaluar_cierre(estado)`; bloquea hasta `MAX_CIERRES_IMPEDIDOS`; después permite, marca `cierre_sin_escalar` |

### Subagente de registro

| Evento | Matcher | Regla | Qué hace |
|--------|---------|-------|----------|
| `PostToolUse` | `mcp__pasarela__consultar_registro_mercantil` | I.1 | `estado.registrar_identificacion(resultado)`; una coincidencia identifica, cualquier otra respuesta no |
| `PostToolUseFailure` | ídem | I.1 | Evento con el tipo de error; no identifica |

### Subagente de listas

| Evento | Matcher | Regla | Qué hace |
|--------|---------|-------|----------|
| `PreToolUse` | `mcp__pasarela__consultar_listas_restrictivas` | I.1 | `reglas.permite_listas(estado, tool_input)`; solo el comercio con tipo `comercio` o el representante con tipo `persona`; cada clave que trae la consulta debe existir en la entidad del registro y coincidir (una clave que la entidad no tiene, por ejemplo un `identificador` para un representante sin identificador, no coincide); deniega si no hay comercio identificado |
| `PostToolUse` | ídem | I.2 | `libro.consultas_listas += …` y `libro.coincidencias += …` por cada hecho |
| `PostToolUseFailure` | ídem | — | Evento; la consulta no cuenta |

### Subagente de categoría

| Evento | Matcher | Regla | Qué hace |
|--------|---------|-------|----------|
| `PostToolUse` | `mcp__pasarela__consultar_riesgo_categoria` | I.3 | `libro.consultas_riesgo += (categoria, nivel)`; `categoria_desconocida` entra sin nivel |
| `PostToolUseFailure` | ídem | — | Evento; la consulta no cuenta |

### Subagente de noticias

Sin hooks. Una mención en noticias no es una coincidencia en listas (IV).

## Fallo cerrado (FR-012)

`fallar_cerrado(hook, tipo)` envuelve cada callback:

| Evento | Ante `Exception` |
|--------|------------------|
| `PreToolUse` | `denegar("No se pudo verificar la regla; se bloquea por precaución.")`, evento `fallo_de_hook` y `libro.fallo_de_hook` |
| `Stop` | `bloquear_cierre(...)`, cuenta contra `MAX_CIERRES_IMPEDIDOS`, evento `fallo_de_hook` |
| `PostToolUse`, `PostToolUseFailure` | `libro.fallo_de_hook` (sticky) y evento `fallo_de_hook`; devuelve `{}` |

Mientras `libro.fallo_de_hook` exista, los `PreToolUse` de las tres reglas deniegan con el motivo
«No se pudo registrar un hecho de la regla; se bloquea por precaución.», y `Caso.completo` es `False`: un
`PostToolUse` que falló pudo dejar sin registrar una coincidencia, y el caso no se presenta como completo.

## Guía del coordinador (no es hook)

La instrucción mínima del coordinador (FR-019) dice qué valor de recomendación usar. Es guía; los hooks
garantizan solo lo que está en las tablas de arriba:

- caso escalado (coincidencia en listas o alto riesgo) → `decide_cumplimiento`;
- caso que no requiere escalamiento y no se habilita → `no_habilitar`;
- caso que no requiere escalamiento y se habilita → `habilitar`.

Un valor distinto de los tres se rechaza (R10).

## Motivos

Todos en español, sin repetir nombres ni identificadores consultados, y con la regla en el evento:

| Situación | Motivo (resumen) |
|-----------|------------------|
| Listas sin registro identificado | «Aún no hay un comercio identificado de forma unívoca en el registro mercantil.» |
| Varias coincidencias | «El registro devolvió varias coincidencias: pida el identificador al analista, no elija una.» |
| Sin coincidencias | «El registro no devolvió coincidencias para el comercio.» |
| Entidad o tipo ajeno | «La consulta no corresponde al comercio identificado ni a su representante legal, con el tipo que corresponde (comercio o persona).» |
| `habilitar` con coincidencia | «Hay una coincidencia en listas restrictivas: no se puede recomendar habilitar. Escale el caso a cumplimiento.» |
| `habilitar` en alto riesgo | «La categoría es de alto riesgo: la decisión es de un oficial de cumplimiento.» |
| Categoría no determinada | «La categoría del caso no quedó determinada.» |
| Falta consulta de listas | «Falta la consulta de listas restrictivas del comercio y de su representante legal.» |
| Falta escalar | «El caso requiere escalamiento a cumplimiento y aún no se ha escalado por: <causas>.» |
| Recomendación fuera del conjunto | «La recomendación debe ser exactamente habilitar, no_habilitar o decide_cumplimiento.» |

## Reparto (FR-010)

Un test recorre las opciones de los cinco agentes de un `Caso` y comprueba la tabla de arriba: el `Stop` solo
en el coordinador, el `PreToolUse` de listas solo en el subagente de listas, y ningún hook de más.
