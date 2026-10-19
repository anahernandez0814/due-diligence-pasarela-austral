# Data Model: Suite de los siete casos (#12)

Estructuras nuevas del ticket. Todas son inmutables (`dataclass(frozen=True)` o `NamedTuple`) y
salen de funciones puras de `src/due_diligence/observacion.py`. **Ninguna lleva texto escrito por el
modelo** (FR-003, R6, R7).

## Observacion

Lo que un test e2e puede ver de un caso después de un turno. Se construye con
`observar(caso, registros, duracion_s) -> Observacion`. `registros` es un `Registros(informes,
escalamientos)`, con los documentos que aceptó la pasarela:
- en la suite e2e salen de `leer_registros(carpeta)`, de los JSON de la carpeta del caso;
- en los tests deterministas, de `PasarelaSimulada.informes` y `.escalamientos`.

| Campo | Tipo | De dónde sale |
|-------|------|---------------|
| `eventos` | `tuple[EventoObservado, ...]` | `caso.eventos()`, sin `detalle` |
| `consultas` | `tuple[ConsultaObservada, ...]` | `caso.estado.consultas`, en orden |
| `consultas_listas` | `tuple[ConsultaListasObservada, ...]` | `caso.estado.libro.consultas_listas` |
| `escalamientos` | `tuple[EscalamientoObservado, ...]` | `libro.escalamientos` y la subcarpeta `escalamientos/` del caso |
| `informes` | `tuple[InformeObservado, ...]` | `estado.informes` y la subcarpeta `informes/` del caso |
| `cobertura` | `dict[str, FrenteObservado]` | `caso.cobertura` (calculada) |
| `cobertura_lineas` | `tuple[str, ...]` | `caso.cobertura.lineas()`: el texto fijo que el hook pone en el informe |
| `completo` | `bool` | `caso.completo` |
| `espera` | `EsperaObservada \| None` | `caso.espera` |
| `comercio` | `ComercioObservado \| None` | `comercio_del_informe(estado)`: identificador y nombre de los datos ficticios |
| `terminaciones` | `tuple[str, ...]` | `Terminacion` de cada turno (`normal`, `anomala`, `limite_seguridad`) con su `subtype` |
| `metricas` | `Metricas` | coste, turnos por turno y duración |
| `registros_coherentes` | `bool` | los informes del caso y los registrados por la pasarela tienen los mismos `id` (se emparejan por id), y los escalamientos del libro y los registrados son tantos como los otros (se emparejan por orden de registro, `registrado_en`) |

### Partes

- **EventoObservado**: `tipo: str`, `frente: str | None`, `regla: str | None`,
  `accion: str | None`.
- **ConsultaObservada**: `frente: str`, `herramienta: str`, `nombre: str | None`,
  `identificador: str | None`, `tipo: str | None`, `valida: bool` y `clase_registro: str | None`.
  Este último solo en el registro, con `clase_de`: `unica`, `varias`, `ninguna`, `contradictoria` o
  `invalida`.
- **ConsultaListasObservada**: `tipo` (`comercio` o `persona`), `nombre`, `identificador` y
  `resultado`.
- **EscalamientoObservado**: `id: str`, del archivo `ESC-…`, y `causas: frozenset[str]`, con las
  etiquetas de `libro.py`, como `alto_riesgo` o `coincidencia_representante`.
- **InformeObservado**: `id: str` (`INF-…`), `recomendacion: str`, `minimo: bool`,
  `cobertura: tuple[str, ...]` (la del archivo, fijada por el hook) y
  `conflictos: tuple[ConflictoObservado, ...]`.
- **ConflictoObservado**: `campo: str`, como `fecha_constitucion`, y
  `valores: tuple[tuple[str, str], ...]`, con un par `(valor, fuente)` por cada fuente.
- **FrenteObservado**: `cubierto: bool` y `causa: str | None`, un valor de `Causa`.
- **EsperaObservada**: `clase: str` (`identificador`, `nombre` o `categoria`) y `motivo: str`, que
  es una constante de `reglas.py`.
- **ComercioObservado**: `identificador: str | None`, `nombre: str | None` y `verificado: bool` (si quedó identificado de forma unívoca en el registro).
- **Metricas**: `coste_usd: float | None`, `turnos: tuple[int | None, ...]` y `duracion_s: float`.

### Reexportaciones

`observacion.py` reexporta lo que los tests e2e necesitan comparar, para que no importen nada más: `MOTIVO_ESPERA_*`, las etiquetas de causa (`CAUSA_*`), `TIPO_BLOQUEO_REGLA` y dos comparadores de datos ficticios normalizados, `mismo_nombre` y `mismo_identificador` (los de `servidor_mcp.normalizar`).

### Reglas

- **Conjunto cerrado de campos**: `test_observacion.py` compara los nombres de los campos con
  igualdad exacta (R7). Añadir un campo exige cambiar ese test a sabiendas.
- **Nada del modelo**: no se copian `respuesta`, `detalle`, `resumen`, `hallazgos`,
  `accion_recomendada` ni los mensajes del analista.
- **Las cadenas que sí se leen** son constantes del código, como `motivo`, `cobertura` y
  `cobertura_lineas`. Los tests las comparan por igualdad con la constante importada, nunca por
  subcadena.

## CasoE2E

La definición de un caso de punta a punta, en `conftest.py` (`CASOS`), junto a la fixture que lo ejecuta: así `test_e2e_casos.py` solo importa `pytest` y `observacion` (R7).

| Campo | Tipo | Ejemplo |
|-------|------|---------|
| `letra` | `str` | `"d"` |
| `mensajes` | `tuple[str, ...]` | `("Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios.", "CO-AM-0004")` |
| `modos` | `dict[str, str]` | `{"PASARELA_MODO_DEMO_HOOKS": "1"}` en el (e); `{"PASARELA_FALLA_NOTICIAS": "1"}` en el (f) |

Los mensajes son los de la tabla Q4 del quickstart del #11.

## Ejecucion

Lo que la fixture de sesión guarda por caso: `observaciones: tuple[Observacion, ...]` (una por
turno) o `error: BaseException` (tiempo agotado, fallo del SDK). Un test con `error` falla con su
tipo, su mensaje, la última terminación conocida y el `-k` para repetirlo (R2).

## Interrupción de la interfaz (R9)

Cambios en estructuras existentes, sin datos nuevos del caso:

- **`RegistroEventos`**:
  - `interrupciones: tuple[type[BaseException], ...]`, que por defecto es `()`;
  - `interrupcion: BaseException | None`, solo la primera;
  - `al_interrumpir: Callable[[], None] | None`, que pone el `Caso` al empezar cada turno;
  - `interrumpir()`.
- **`Caso`**:
  - un parámetro nuevo, `interrupciones`, que pasa a `RegistroEventos`;
  - un turno interrumpido queda clasificado `ANOMALA` con el detalle `interrumpido por la
    interfaz`;
  - la propiedad `interrumpido` es verdadera si el último turno terminó así.
    `presentacion.decidir_mensaje` la mira primero: el siguiente mensaje abre un caso nuevo con
    aviso (opción A).
- **`hooks.py`**: la `ContextVar` `_DENTRO_DE_HOOK`, que pone `fallar_cerrado`.

Transiciones del turno con la interrupción:

```text
en curso ──(observador lanza la interrupción)──▶ interrupción guardada, observador apagado
   │                                              │
   │                       dentro de un hook ─────┤── el hook decide y devuelve ──▶ interrumpir()
   │                       fuera de un hook  ─────┴──────────────────────────────▶ interrumpir()
   ▼
interrumpir() ─▶ call_soon(cancelar el turno) ─▶ _turno: ANOMALA + relanza la interrupción
```
