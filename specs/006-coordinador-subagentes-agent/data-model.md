# Modelo de datos: Coordinador y subagentes

Todo vive en memoria durante un caso. Nada se persiste (Supuestos de la spec).

## Frente

Los cuatro frentes son constantes del paquete (`frentes.py`), no datos del caso.

| Frente | Herramienta de la pasarela | Depende de | Contexto que recibe (R11) |
|--------|----------------------------|-----------|---------------------------|
| `registro` | `consultar_registro_mercantil` | — | `identificador` o `nombre` |
| `noticias` | `buscar_noticias` | — | `identificador` o `nombre` del comercio |
| `categoria` | `consultar_riesgo_categoria` | — | `categoria` |
| `listas` | `consultar_listas_restrictivas` | `registro` | comercio y representante, **del resultado del registro** |

## Situación de un frente

`sin_iniciar` → `en_curso` → `terminado` | `no_terminado`, o `sin_iniciar` → `rechazado`

- `sin_iniciar`: el coordinador aún no lo delegó.
- `en_curso`: hay un evento `frente_inicio` y aún no `frente_fin`.
- `terminado`: el subagente terminó con una terminación **normal**, sus resultados son válidos, **ninguna consulta devolvió un error estructurado de la pasarela** y, en `listas`, están hechas todas las consultas que exige la entidad (comercio y, si lo hay, representante).
- `no_terminado`: el subagente terminó de forma anómala o por el límite de seguridad (R5), su resultado no es válido (R6), una consulta devolvió un error estructurado de la pasarela o faltó una consulta obligatoria de `listas` (R4). Conserva lo que alcanzó a obtener, que puede ir vacío (spec, US5-3).
- `rechazado`: la delegación se rechazó antes de lanzar al subagente (falta un dato, `listas` sin coincidencia única del registro). Lleva el motivo. No es `sin_iniciar`: este es «aún no delegado».

Un frente `no_terminado` o `rechazado` **nunca** figura con un resultado vacío: el estado dice que no
terminó. El manejo (reintento, cobertura declarada) es del #8.

## Consulta

Una llamada a una herramienta de la pasarela hecha por un subagente.

| Campo | Contenido |
|-------|-----------|
| `frente` | frente que la hizo |
| `herramienta` | nombre completo (`mcp__pasarela__…`) |
| `argumentos` | los que usó el subagente |
| `resultado` | el JSON de la pasarela (contrato del #5), ya parseado; `None` si no era un JSON válido |
| `valido` | `True` si `resultado` es un objeto con `resultado`, `hechos` y `metadatos` |
| `error` | el error estructurado de la pasarela, tal como llegó (`error`, `tipo`, `mensaje`, `reintentable`, `obtenido`), si la herramienta devolvió uno (`is_error` del `ToolResultBlock`); `None` si no. Se conserva sin reescribir, con su `reintentable` (R6) |

## ResultadoFrente

Lo que devuelve un ejecutor al terminar un subagente.

| Campo | Contenido |
|-------|-----------|
| `frente` | |
| `consultas` | lista de `Consulta`, en orden |
| `resumen` | texto del modelo, solo informativo; **no se usa para decidir** |
| `terminacion` | `Terminacion` (R5) |
| `detalle_terminacion` | `subtype`, `stop_reason` y `terminal_reason` originales |

El **contenido** y los **metadatos** (fuente y fecha) están en `Consulta.resultado`, separados como
los entrega el servidor: `hechos[].contenido`, `hechos[].metadatos` y `metadatos`. El estado no los
mezcla ni los reescribe (FR-007).

## EstadoCaso

| Campo | Contenido |
|-------|-----------|
| `solicitud` | texto original del analista, solo para la interfaz (los subagentes no lo reciben) |
| `frentes` | `frente → situación` (arriba) |
| `resultados` | `frente → ResultadoFrente`, solo de los frentes que lo tienen |
| `consultas` | todas las `Consulta`, en orden de llegada |
| `comercio` | derivado del resultado del registro **solo si hay una coincidencia única**: `{identificador, nombre, representante_legal}`; si no, `None` |
| `terminacion` | terminación del ciclo del coordinador, o `None` mientras corre |

- **`comercio` es la única fuente de los datos de listas** (R4, FR-005). Con varias coincidencias, con
  `sin_coincidencias` o sin resultado del registro vale `None` y `listas` no se ejecuta (FR-013).
- **Lectura segura mientras el caso corre**: `instantanea()` devuelve una copia; los hooks del #7 y la
  interfaz leen de ahí (spec, edge case de la consulta en curso).
- **Un caso, un estado** (FR-014): se crea en `Caso` y no se comparte; no hay variables de módulo.

## Evento

| Campo | Contenido |
|-------|-----------|
| `secuencia` | entero creciente desde 1, único por caso; da orden estable aunque coincidan las marcas |
| `marca` | fecha y hora UTC con zona (reloj inyectable en los tests) |
| `tipo` | `caso_iniciado`, `delegacion`, `frente_inicio`, `frente_fin`, `frente_rechazado`, `terminacion` |
| `frente` | frente al que se refiere, o `None` (`caso_iniciado`, `terminacion` del coordinador) |
| `detalle` | texto en español para la interfaz; en `terminacion` y `frente_fin`, la clasificación y los valores originales de `subtype`, `stop_reason` y `terminal_reason` |

Reglas de orden que comprueban los tests (SC-003):
- Por cada frente delegado: `delegacion` antes de `frente_inicio` antes de `frente_fin`.
- `frente_inicio` de `listas` tiene `secuencia` mayor que `frente_fin` de `registro`.
- Si `listas` se pidió antes de terminar el registro, no hay `frente_inicio` de `listas` hasta ese fin.

## Terminacion

`NORMAL` | `ANOMALA` | `LIMITE_SEGURIDAD`. La produce `terminacion.clasificar` (R5) para el
coordinador y para cada subagente. Un evento `terminacion` o `frente_fin` la lleva siempre.

## Delegación

Entrada de la herramienta `delegar_frente` (contrato en `contracts/delegacion.md`): `frente`,
`identificador`, `nombre`, `categoria`. El código toma de ella **solo** los campos que el frente
necesita (R11).

## Caso

Agrupa `EstadoCaso`, `RegistroEventos`, el ejecutor, los `hooks` opcionales y las opciones del
coordinador. Se crea con `Caso(...)` y se ejecuta con `await caso.ejecutar(solicitud)`; la función
`ejecutar_caso(solicitud, …)` los combina para el uso normal (contrato en `contracts/caso.md`).
