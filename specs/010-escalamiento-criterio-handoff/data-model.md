# Data Model: Escalamiento con criterio, handoff y ambigüedad (#10)

Solo lo que cambia o se añade respecto al #9. Las decisiones están en `research.md` (R#).

## Resumen al oficial (entrada de `escalar_a_cumplimiento`, R5, R6)

| Campo | Tipo | Quién lo pone | Validación |
|-------|------|---------------|------------|
| `comercio` | `{identificador, nombre, verificado}` | código (`comercio_del_informe`) | `_comercio` del #9 |
| `hallazgos` | `{frente: [Afirmación]}` | coordinador | `_hallazgos` del #9, `problemas_de_fuente` (con R7) y `problemas_de_frentes_cubiertos` |
| `cobertura` | lista de textos | código (`calcular_cobertura(...).lineas()`) | `_cobertura` del #9 |
| `causa_escalamiento` | lista de textos | código (`causas_del_resumen`) | texto o lista de textos no vacíos |
| `accion_recomendada` | texto | coordinador | texto no vacío |
| `conflictos` | `{resumen, lista}` | código (`calcular_conflictos(...).como_entrada()`) | `_conflictos` del #9 |

- Con el sello, el código pone la cobertura `[COBERTURA_NO_CALCULADA]`, los conflictos `no_calculados()` y la causa de las causas vigentes, que incluyen el fallo de hook. No se validan las fuentes. Sin comercio identificado ni pedido, pone `COMERCIO_NO_IDENTIFICADO` (`"no identificado"`, `verificado: false`).
- Guardado en `resultados/escalamientos/ESC-….json`, con `registrado_en` en UTC.

## `Identificacion` y su clase (`estado.py`, R3)

```text
ClaseIdentificacion = unica | varias | ninguna | contradictoria | invalida
Identificacion(comercio, motivo, con_coincidencias, clase)   # `clase` es nuevo
```

La clase la da una función hermana pura, `clase_de(resultado) -> ClaseIdentificacion`, en `estado.py` junto a `derivar_comercio`, que sigue devolviendo `(comercio, motivo)` sin cambiar a sus llamadores. `registrar_identificacion` guarda las dos cosas:

| Clase | Cuándo |
|-------|--------|
| `invalida` | la respuesta no tiene la forma del contrato |
| `ninguna` | sin coincidencias |
| `varias` | más de una coincidencia |
| `contradictoria` | las fuentes difieren en el nombre o el representante legal (D3) |
| `unica` | una sola coincidencia, sin contradicción |

`EstadoCaso.clase_identificacion` consolida la clase igual que `comercio`. Es `None` si el registro no terminó.

## Cambios en `EstadoCaso`

| Campo | Tipo | Escribe | Lee |
|-------|------|---------|-----|
| `mensajes` | `list[str]` | `Caso.ejecutar`, `Caso.continuar` | `categoria_en_mensajes` |
| `solicitud` | propiedad: `mensajes[0]` o `""` | — | compatibilidad del #6 al #9 |
| `categoria_bloqueada` | `bool` | `_delegar_previo` (R9) | `espera_del_analista` |
| `escalamientos_pendientes` | `dict[str, tuple[Escalamiento, str, int]]` por `tool_use_id`: el `Escalamiento`, el resumen de la cobertura y el número de afirmaciones (para el evento, FR-021) | `_escalar_previo` | `_escalar_posterior` y `_escalar_fallido` |

## `Escalamiento` (`libro.py`, R8)

```text
Escalamiento(causas: frozenset[str], comercio: tuple[Any, Any, bool] | None)
LibroReglas.escalamientos: list[Escalamiento]   # antes list[frozenset[str]]
```

`comercio` es la clave `(identificador, nombre, verificado)` del comercio del caso cuando se aceptó el escalamiento, la misma de la `Huella` del #9.

## `Espera` (`reglas.py`, R3)

```text
Espera(clase: "identificador" | "nombre" | "categoria", motivo: str)
```

| Clase | Condición | Motivo (texto fijo) |
|-------|-----------|---------------------|
| `identificador` | registro `terminado` y clase `varias` | «El registro devolvió varias coincidencias: el caso espera el identificador del analista.» |
| `nombre` | registro `terminado` y clase `ninguna` | «El registro no encontró el comercio: el caso espera que el analista revise el nombre.» |
| `categoria` | `categoria_bloqueada` y sin `consultas_riesgo` | «La categoría no aparece en los mensajes del analista: el caso espera la categoría.» |

La espera `categoria` vale con cualquier estado del registro salvo el caído, y solo si ningún frente está caído: con un frente caído (el registro, las listas, las noticias o la categoría) no hay espera y se exige el informe, con la categoría no determinada (I.5). Con el registro en `varias` o `ninguna`, prevalece el motivo del registro.

Motivos del informe rechazado durante la espera `identificador` o `nombre` (FR-016): `MOTIVO_INFORME_ESPERA_IDENTIFICADOR` y `MOTIVO_INFORME_ESPERA_NOMBRE` (textos en research R3), con la regla `V`.

## `Causa` del #8 (`estado.py`)

Se añade `OTRO_COMERCIO`, con el motivo de cobertura «se consultó con un nombre o identificador que no es el del comercio identificado» (R7). No es reintentable: hace falta otra entrada.

## Funciones puras nuevas o cambiadas

| Función | Módulo | Qué hace |
|---------|--------|----------|
| `espera_del_analista(estado)` | `reglas.py` | R3 |
| `bajo_riesgo_sin_hallazgos(estado)` | `reglas.py` | FR-002, R5 |
| `escalado_para_el_comercio(estado)` | `reglas.py` | FR-004, R8 |
| `escalamiento_cubre(libro, comercio)` | `reglas.py` | ahora filtra por comercio (R8) |
| `categoria_en_mensajes(categoria, mensajes)` | `reglas.py` | FR-020, R9 |
| `consulta_del_comercio(argumentos, comercio)` | `reglas.py` | FR-027, R7 |
| `causas_del_resumen(estado)` | `reglas.py` | FR-009: una línea por causa vigente o, sin causas, una por cada motivo de `MOTIVOS_SIN_CAUSA` que se cumpla (research R5) |
| `clase_de(resultado)` | `estado.py` | la clase de la identificación (R3) |
| `evaluar_escalamiento(estado, entrada)` | `reglas.py` | motivos de rechazo de R5 (espera y bajo riesgo) |
| `evaluar_informe` | `reglas.py` | añade `MOTIVO_DECIDE_SIN_ESCALAR` |
| `fuentes_consultadas` | `informe.py` | noticias y listas, solo las consultas del comercio (R7) |
| `calcular_cobertura` | `cobertura.py` | noticias de otro comercio no cubierto (R7) |
| `validar_resumen`, `mensaje_resumen` | `servidor_mcp/informe.py` | R6 |

## Eventos (`eventos.py`)

| Tipo | Cuándo | Detalle (sin datos del comercio) |
|------|--------|----------------------------------|
| `mensaje_analista` | al empezar cada turno | «Mensaje N del analista.» |
| `espera_analista` | el `Stop` admite una espera | el motivo de la `Espera` |
| `escalamiento_registrado` | ya existe; ahora en la confirmación | id, causas cubiertas, resumen de la cobertura y número de afirmaciones (FR-021) |
| `bloqueo_regla` | ya existe | `accion`: `escalar_a_cumplimiento`, `delegar_frente categoria` |

## Transiciones del fin de turno

```text
Stop ─┬─ espera_del_analista ≠ None ──────────────► permitir; evento espera_analista
      ├─ evaluar_cierre = None ───────────────────► permitir
      ├─ cierres_impedidos < MAX ─────────────────► bloquear; cierres_impedidos += 1
      └─ agotadas ────────────────────────────────► permitir; cierre_sin_escalar / cierre_sin_informe

Turno nuevo (ejecutar / continuar) ──► mensajes += texto; cierres_impedidos = 0; marcas = False
```

## Validación por regla

- **Escalar se deniega** solo:
  - con la espera `identificador` o `nombre`, sin sello;
  - con `bajo_riesgo_sin_hallazgos`;
  - con problemas de forma o de fuente;
  - sin comercio.
- **Si falla un hook**: nunca se deniega (`degradar_escalamiento`).
- **`decide_cumplimiento`**: exige `escalado_para_el_comercio`.
