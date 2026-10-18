# Modelo de datos: Hooks del SDK: reglas de negocio 1, 2 y 3

Todo vive en memoria, por caso, sin estado de módulo (FR-011). Las entidades nuevas son
`LibroReglas` y sus partes (`libro.py`); `EstadoCaso` (`estado.py`, #6) las contiene y cambia cómo guarda
la identificación. Nada de esto se serializa ni se pasa por el SDK.

## EstadoCaso (cambios)

| Campo / propiedad | Antes (#6) | Ahora |
|-------------------|------------|-------|
| `comercio`, `motivo_comercio` | campos escritos por `fijar_comercio` | **propiedades derivadas** de `identificaciones` y de la situación del registro (R4) |
| `identificaciones` | no existía | `list[tuple[dict \| None, str]]`: el resultado de `derivar_comercio` de cada consulta válida del registro |
| `libro` | no existía | `LibroReglas` del caso |
| `cierre_sin_escalar` | no existía | `bool`; se marca cuando el `Stop` agota `MAX_CIERRES_IMPEDIDOS` sin que el caso esté escalado |

Métodos: `registrar_identificacion(respuesta)` (llama a `derivar_comercio`, único intérprete),
`reiniciar_identificacion()` (al volver a delegar el registro). **Se eliminan** `fijar_comercio` y
`Delegador._fijar_comercio`.

**`comercio` (propiedad)**: si el frente de registro no está `terminado` →
`None` con el motivo «El registro mercantil no terminó…»; si no hay identificaciones →
«El registro no devolvió datos.»; si alguna consulta con coincidencias no identifica a un comercio →
`None` con el motivo de `derivar_comercio`; si las que sí identifican difieren entre sí →
`None` («identifican comercios distintos: no se elige uno»); si no hay ninguna con coincidencias, el
motivo es el de la primera consulta. En cualquier otro caso es el dict
`{identificador, nombre, representante_legal | None}` que devolvió `derivar_comercio`.
Es la lógica de `_fijar_comercio` del #6, movida.

## LibroReglas

Lo que los hooks registran para decidir. Los hooks de `PostToolUse` son los únicos que lo escriben.

| Campo | Tipo | Quién lo escribe | Quién lo lee |
|-------|------|------------------|--------------|
| `consultas_listas` | `list[ConsultaListas]` | `PostToolUse` de listas | `registrar_informe` (FR-005) |
| `coincidencias` | `list[Coincidencia]` (nunca se borran) | `PostToolUse` de listas | causas vigentes, `registrar_informe`, `Stop` |
| `consultas_riesgo` | `list[ConsultaRiesgo]` | `PostToolUse` de riesgo | alto riesgo y categoría determinada |
| `escalamientos` | `list[frozenset[str]]` (instantáneas de las causas) | `PostToolUse` de `escalar_a_cumplimiento` | cobertura de causas |
| `cierres_impedidos` | `int` | hook de `Stop` | límite `MAX_CIERRES_IMPEDIDOS` |
| `fallo_de_hook` | `str \| None` (sticky) | el envoltorio de cualquier hook | los `PreToolUse` de las tres reglas |

### ConsultaListas

`tipo` (`comercio` o `persona`), `nombre` (`str | None`), `identificador` (`str | None`), `resultado`
(`coincidencias` o `sin_coincidencias`). Solo entra una consulta válida (llegó por `PostToolUse`,
con la forma del contrato). Se compara siempre contra el comercio **vigente** al evaluar, no contra el
que había al consultar (R7).

### Coincidencia

`clave` (`listas:<tipo>:<identificador o nombre normalizado>`), `tipo`, `lista`, `fuente`, `fecha`. Se
añade una por cada hecho de una respuesta `coincidencias` de listas. **No se borra** aunque el registro cambie
de comercio.

### ConsultaRiesgo

`categoria` (`str`), `nivel` (`alto`, `medio`, `bajo` o `None` si la categoría fue desconocida).

## Funciones puras (`reglas.py`)

Reciben el libro y el comercio; no tocan el SDK ni el estado de otros módulos.

| Función | Devuelve |
|---------|----------|
| `es_alto_riesgo(libro)` | `True` si alguna consulta tiene la categoría en `ALTO_RIESGO` (`igual`) o `nivel == "alto"`; persistente |
| `categoria_determinada(libro)` | `True` si `es_alto_riesgo` o la **última** consulta tiene nivel |
| `causas_vigentes(libro)` | `frozenset` de claves de las coincidencias más `"alto_riesgo"` si aplica |
| `escalamiento_cubre(libro)` | `True` si alguna instantánea contiene todas las causas vigentes (vacío ⇒ `True`) |
| `requiere_escalamiento(libro)` | `bool(causas_vigentes)` |
| `consulta_coincide(consulta, entidad, tipo)` | `True` si el tipo es el esperado, la consulta trae al menos una clave y **cada clave que trae** (`nombre`, `identificador`) existe en la entidad del registro y coincide. Si la consulta trae una clave que la entidad no tiene (por ejemplo, un `identificador` para un representante sin identificador), **no coincide** (R7); la usa también `Delegador._falta_en_listas` |
| `permite_listas(estado, entrada)` | `(permitida, motivo)` para el hook de la consulta de listas (R6, R7) |
| `permite_delegar_listas(estado)` | `(permitida, motivo)` para el hook de `delegar_frente` (R6) |
| `evaluar_informe(estado, entrada)` | lista de motivos de rechazo (vacía si se acepta); nombra todas las causas |
| `evaluar_cierre(estado)` | `None` si puede terminar, o el motivo si requiere escalamiento sin cubrir |
| `normalizar_recomendacion(texto)` | uno de `RECOMENDACIONES` o `None` |

`evaluar_informe` aplica, en orden y acumulando motivos:

1. recomendación fuera de `RECOMENDACIONES` (R10);
2. caso que requiere escalamiento sin cubrir (US2.3, US3.3): para cualquier recomendación;
3. solo si la recomendación es `habilitar`: coincidencias en listas (I.2), alto riesgo (I.3), categoría no
   determinada (I.3), falta de consulta válida de listas del comercio o del representante cuando existe
   (I.1/I.2). Sin representante, basta la del comercio.

## Salida del hook

Los hooks devuelven siempre una de tres formas tipadas (`hooks.py`), validadas por test contra los
literales del SDK:

- `permitir()` → `{}`;
- `denegar(motivo)` → `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
  "permissionDecisionReason": motivo}}`;
- `bloquear_cierre(motivo)` → `{"decision": "block", "reason": motivo}` (solo `Stop`).

## Eventos nuevos

| Tipo | Cuándo | `frente` | `regla` |
|------|--------|----------|---------|
| `bloqueo_regla` | un `PreToolUse` deniega | el del agente (`listas`) o `None` | `I.1`, `I.2` o `I.3` |
| `cierre_impedido` | el `Stop` devuelve el cierre | `None` | `I.2` o `I.3` |
| `cierre_sin_escalar` | el `Stop` agota el límite y deja terminar | `None` | `I.2` o `I.3` |
| `fallo_de_hook` | el envoltorio atrapa una excepción | el del agente | `None` |
| `escalamiento_registrado` | `PostToolUse` de `escalar_a_cumplimiento` con éxito | `None` | `None` |
| `modo_demostracion` | al iniciar un caso con la variable activa | `None` | `None` |

`Evento` gana `regla: str | None = None`. El detalle es el motivo en español y no repite el nombre ni el
identificador consultados.

## Transiciones

```text
registro (PostToolUse, una coincidencia) → identificaciones += derivar_comercio(...)
registro frente → terminado            → comercio (propiedad) = identificación consolidada
listas  (PreToolUse)                   → permitido solo si consulta_coincide(comercio | representante)
listas  (PostToolUse)                  → consultas_listas += …; coincidencias += … (si las hay)
riesgo  (PostToolUse)                  → consultas_riesgo += …
escalar (PostToolUse, caso_escalado)   → escalamientos += causas_vigentes(libro)
informe (PreToolUse)                   → evaluar_informe(...) ⇒ permitir o denegar
Stop                                   → evaluar_cierre(...) ⇒ permitir, o bloquear (cierres_impedidos += 1)
                                         o, agotado el límite, permitir + cierre_sin_escalar
```

## Caso completo (`Caso.completo`)

Propiedad **nueva** (el #6 no la tiene): `True` solo si los cuatro frentes están `terminado`, la
terminación es normal, **no** hay `cierre_sin_escalar` y **no** existe `libro.fallo_de_hook`. Sirve para que
un caso cortado por el límite de devoluciones del `Stop` no se presente como completo y para que un
`PostToolUse` que falló (y pudo dejar sin registrar una coincidencia, una identificación o una consulta) no
deje pasar el caso como completo; la cobertura declarada es del #8.
