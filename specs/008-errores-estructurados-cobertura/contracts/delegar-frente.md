# Contrato: respuesta de `delegar_frente` ante un fallo y política de reintento

Amplía `specs/006-coordinador-subagentes-agent/contracts/delegacion.md`. Lo que no se nombra
aquí no cambia. Modelo de datos en [data-model.md](../data-model.md); decisiones R3 y R4 en
[research.md](../research.md).

## Frente cubierto (sin cambios)

```json
{"frente": "registro", "situacion": "terminado", "resultados": [...], "resumen": "..."}
```

## Frente no cubierto

```json
{
  "error": true,
  "tipo": "frente_no_terminado",
  "frente": "noticias",
  "causa": "error_de_fuente",
  "mensaje": "La herramienta devolvió un error estructurado (servicio_no_disponible).",
  "reintentable": true,
  "intento": 1,
  "reintentos_restantes": 1,
  "obtenido": {
    "frente": "noticias",
    "resultados": [],
    "errores": [{"error": true, "tipo": "servicio_no_disponible", "reintentable": true, "...": "..."}],
    "terminacion": "..."
  }
}
```

- `tipo` conserva los valores del #6 (`frente_no_terminado`, `frente_rechazado`, `entrada_invalida`).
- `causa` es uno de los valores cerrados de `data-model.md`.
- `reintentable` es `true` solo si la causa es reintentable **y** `reintentos_restantes > 0`.
- `mensaje` y `obtenido.terminacion` nunca contienen el texto interno de una excepción: solo
  `excepción <Tipo>`.
- `obtenido.resultados` conserva lo que el frente alcanzó a obtener, con contenido y metadatos
  separados (por ejemplo, la consulta del comercio en listas cuando falló la del representante).

## Rechazo sin ejecución

Igual que en el #6, con `frente`, `causa: "rechazado"`, `intento: 0` y `reintentos_restantes`
igual a `MAX_REINTENTOS_POR_FRENTE`. **Listas antes del registro, o con el registro rechazado**,
conserva `reintentable: true` (FR-003; los dos tests de `test_delegacion.py`).

## Política al repetir la misma entrada (misma clave `(frente, contexto)`)

| Último resultado con esa clave | Acción | Evento |
|--------------------------------|--------|--------|
| `terminado` | devuelve lo guardado | `delegacion_repetida` |
| error con `reintentable: true` | vuelve a ejecutar el subagente | `frente_reintento` |
| error con `reintentable: false` (causa no reintentable o reintentos agotados) | no ejecuta; devuelve el mismo error con `reintentable: false` y `reintentos_restantes: 0` | `reintento_denegado` |
| la llamada esperó a una ejecución en curso de esa clave | devuelve el resultado de esa ejecución | — |

Otra entrada es otra clave: una delegación nueva, como en el #6.

## Descripción de la herramienta

Añade al final de `DESCRIPCION`: «Repetir un frente con la misma entrada devuelve lo guardado si
terminó. Si devolvió un error con reintentable true, se puede pedir una vez más con la misma
entrada; con reintentable false no se vuelve a ejecutar: sigue con los demás frentes».
