# Data Model: Informe con procedencia, conflictos y registro (#9)

Todo vive en memoria, por caso, salvo el informe que la pasarela guarda en `resultados/informes/`.
Sin estado de módulo. Las referencias R# son de [research.md](research.md).

## Afirmación (pasarela, `servidor_mcp/informe.py`)

| Campo | Tipo | Regla |
|-------|------|-------|
| `texto` | str | No vacío tras quitar espacios (FR-002). |
| `fuente` | str | No vacía (FR-002); en el hook, además, una fuente consultada para ese frente (FR-004, R4). |
| `fecha` | str | `AAAA-MM-DD` y fecha real (FR-002). No se contrasta con la fuente (riesgo residual 3). |

Cualquier otro campo es un problema (`campo desconocido`). Las afirmaciones se identifican por su
ruta: `hallazgos.<frente>[<posición desde 0>]`.

## Informe (entrada de `registrar_informe`)

| Parte | Quién la pone | Forma |
|-------|---------------|-------|
| `comercio` | Código (R5) | `{identificador: str \| null, nombre: str \| null, verificado: bool}`. Con `verificado: true` hacen falta los dos textos; con `false`, al menos uno. |
| `hallazgos` | Coordinador | `{<frente>: [Afirmación, …]}`. Las claves pertenecen a `registro`, `listas`, `noticias` y `categoria`. Un frente ausente equivale a una lista vacía. |
| `conflictos` | Código (R6) | `{resumen: str, lista: [Conflicto, …]}`. |
| `cobertura` | Código (#8) | Lista de textos (`CoberturaCaso.lineas()`) o `[COBERTURA_NO_CALCULADA]` tras un fallo de hook. |
| `recomendacion` | Coordinador | `habilitar`, `no_habilitar` o `decide_cumplimiento` (conjunto cerrado del #7). |

`validar_informe(entrada) -> list[Problema]` devuelve todos los problemas de forma. Un `Problema`
tiene `{ruta, texto}`. Una lista vacía significa que la forma es válida.

## Conflicto y ConflictosCaso (`due_diligence/conflictos.py`)

```text
ValorFuente   = {valor: Any, fuente: str, fecha: str}
Conflicto     = {dato: str, valores: [ValorFuente, …]}   # ≥ 2 valores distintos
ConflictosCaso
  estado: "sin_conflictos" | "con_conflictos" | "no_comparables" | "no_calculados"
  lista: tuple[Conflicto, …]
  resumen: str          # texto fijo por estado (R6)
  como_entrada() -> {resumen, lista}
```

- `no_comparables`: el registro está caído, o hay comercio identificado sin una consulta válida
  del registro que coincida en `estado.consultas` (R6, hallazgo U1). No hay datos que comparar.
- `no_calculados`: solo se construye en el modo de informe mínimo (R9); `calcular_conflictos`
  nunca lo devuelve.
- El orden de `valores` es el de la respuesta de la pasarela. No indica precedencia.

## Huella e InformeRegistrado (`due_diligence/informe.py`, `estado.py`)

```text
Huella (frozen)
  cobertura: tuple[(Frente, bool), …]        # solo cubierto o no (R7)
  conflictos: tuple[(dato, tuple[(fuente, valor), …]), …] + estado
  causas: frozenset[str]                      # causas_vigentes, con fallo_de_hook (R9)
  comercio: (identificador, nombre, verificado) | None

InformeRegistrado (frozen)
  id: str                 # el que devolvió la pasarela (INF-xxxxxxxx)
  recomendacion: str
  minimo: bool            # registrado en modo de informe mínimo (FR-014)
  huella: Huella
```

- `huella_actual(estado) -> Huella` es pura. La calcula el `PreToolUse` de `registrar_informe`
  con los mismos datos que pone en la entrada (R7); el `PostToolUse` no la recalcula.
- **Caso sellado** (`libro.fallo_de_hook`): `cobertura` y `conflictos` valen el marcador fijo
  `NO_CALCULADOS`, sin llamar a `calcular_cobertura` ni a `calcular_conflictos`, en el `PreToolUse`
  y en el `Stop` (R7, hallazgo I1). `causas` y `comercio` se calculan igual.
- `informe_vigente(estado) -> bool`: hay informes y `estado.informes[-1].huella ==
  huella_actual(estado)`.
- `cambios(huella_a, huella_b) -> list[str]`: los nombres de los componentes que difieren, para el
  motivo del `Stop`.

## Cambios en `EstadoCaso`

| Campo nuevo | Tipo | Quién lo escribe |
|-------------|------|------------------|
| `comercio_pedido` | `dict \| None` (`identificador`, `nombre`) | El `Delegador`, al delegar el registro (R8). |
| `informes_pendientes` | `dict[str, (Huella, recomendacion, minimo)]`, por `tool_use_id` | El `PreToolUse` de `registrar_informe` que acepta (R7). |
| `informes` | `list[InformeRegistrado]` | El `PostToolUse` de `registrar_informe`: confirma la pendiente de su `tool_use_id` con el id que devolvió la pasarela; el `PostToolUseFailure` la descarta (R7, R10). |
| `cierre_sin_informe` | bool | El `Stop`, al agotar las devoluciones con el informe pendiente (R8). |

## Funciones puras nuevas (`due_diligence/informe.py`)

| Función | Devuelve |
|---------|----------|
| `registro_caido(estado)` | Si el registro no respondió, con o sin reintento disponible (R8). |
| `registro_reintentable(estado)` | Si el último error del registro tiene `reintentable: true`, para el motivo «reintenta el registro o registra el informe» (R8). |
| `requiere_informe(estado)` | `estado.comercio is not None or registro_caido(estado)`. |
| `comercio_del_informe(estado)` | El comercio con `verificado`, o `None` (R5). |
| `fuentes_consultadas(estado, frente)` | Las fuentes de las consultas válidas del frente (R4). |
| `problemas_de_fuente(estado, hallazgos)` | Un `Problema` por afirmación con una fuente no consultada. |

## Cambios en `reglas.py` y `libro.py`

- `CAUSA_FALLO_DE_HOOK = "fallo_de_hook"`, con su etiqueta en `ETIQUETAS_CAUSA` («fallo de un hook
  de verificación»). `causas_vigentes` la incluye si `libro.fallo_de_hook` (R9); `reglas_de` no le
  asigna regla I.2 ni I.3.
- `evaluar_cierre(estado)` devuelve el motivo del escalamiento, el del informe, los dos juntos o
  `None` (R8). Una función auxiliar dice qué falta, para marcar `cierre_sin_escalar` y
  `cierre_sin_informe`.
- `evaluar_informe_minimo(estado, entrada)`: los motivos de `evaluar_informe` (recomendación y
  escalamiento) más el de una recomendación distinta de `decide_cumplimiento` (R9).

## Eventos (`eventos.py`)

| Tipo | Cuándo | Detalle (sin datos del comercio) |
|------|--------|----------------------------------|
| `informe_registrado` (nuevo) | `PostToolUse` de `registrar_informe` con éxito | id, recomendación, resumen de la cobertura, número de conflictos y, si lo es, «informe mínimo» |
| `datos_sustituidos` (nuevo) | `PreToolUse` de `registrar_informe` que acepta | comercio verificado o no, número de conflictos y si lo declarado era distinto |
| `cierre_sin_informe` (nuevo) | `Stop` que agota las devoluciones con el informe pendiente | motivo fijo |
| `bloqueo_regla` (cambia) | como en el #7 | con `accion` relleno; la regla es `I.4` para el esquema y la fuente |

`Evento` gana `accion: str | None = None`, el último campo, para no romper llamadas posicionales.

## Transiciones de la exigencia de cierre

```text
sin comercio ni registro caído ─────────────────────────────▶ no exige informe
comercio identificado | registro caído ─▶ exige informe ─(informe vigente)─▶ cierre permitido
                                              ▲                    │
                                              └── cambio de huella ┘   (R7)
causas sin cubrir ─▶ exige escalar ─(escalamiento que las cubre)─▶ se puede registrar el informe
```
