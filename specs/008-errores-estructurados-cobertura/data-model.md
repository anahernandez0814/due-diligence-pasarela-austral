# Data Model: Errores estructurados y cobertura parcial

**Ticket**: #8 | **Fecha**: 2026-10-17 | Decisiones en [research.md](research.md).

Todo vive en memoria, por caso, como el estado del #6 y el libro de reglas del #7. Sin estado de
módulo.

## Causa (conjunto cerrado, R4)

`StrEnum` en `delegacion.py` (o en un módulo propio si `cobertura.py` la necesita sin importar la
delegación; lo decide la implementación sin cambiar los valores):

| Valor | Origen | Reintentable |
|-------|--------|--------------|
| `terminacion_anomala` | `ResultadoFrente.terminacion` no es `NORMAL` | no |
| `error_de_fuente` | alguna consulta efectiva con `error` (sin contar bloqueos de hook) | sí si todos los errores reales traen `reintentable is True` |
| `sin_consultas` | ninguna consulta efectiva | no |
| `resultado_invalido` | alguna consulta efectiva sin la forma del contrato | no |
| `consulta_incompleta` | listas sin el comercio o sin el representante | no |
| `rechazado` | `frente_rechazado` sin ejecución | no; **sí** para listas antes del registro o con el registro rechazado (FR-003) |
| `cancelado` | el frente quedó `en_curso` al salir de `_ejecutar` | no |
| `invalidado` | listas, porque el comercio del registro cambió | no aplica (otra ejecución) |

Prioridad cuando concurren: la de la tabla, que es el orden de `Delegador._evaluar`.

## ErrorFrente (R4)

Lo que el coordinador recibe de `delegar_frente` cuando un frente no queda cubierto. También se
guarda el último por frente en `EstadoCaso.errores`.

| Campo | Tipo | Regla |
|-------|------|-------|
| `error` | `True` | siempre |
| `tipo` | `frente_no_terminado` \| `frente_rechazado` \| `entrada_invalida` | sin cambios respecto del #6; **se conserva por compatibilidad con el #6** y no es el «tipo de error» de FR-002 |
| `frente` | texto | el frente; ausente solo en `entrada_invalida` (no hay frente válido) |
| `causa` | `Causa` | tabla anterior. **Es el «tipo de error» de FR-001 y FR-002.** El tipo que dio la pasarela sigue en `obtenido.errores[].tipo` |
| `mensaje` | texto en español | sin el texto interno de una excepción, sin nombres ni identificadores del comercio |
| `reintentable` | bool | `causa` reintentable **y** `reintentos_restantes > 0` (R3) |
| `intento` | entero ≥ 1 | ejecuciones con esta entrada, incluida esta; 0 en un rechazo sin ejecución |
| `reintentos_restantes` | entero ≥ 0 | `MAX_REINTENTOS_POR_FRENTE` menos los usados con esta entrada |
| `obtenido` | objeto | sin cambios respecto del #6: `frente`, `resultados` (contenido y metadatos separados), `errores`, `terminacion` |

## Historial de intentos (R3)

En el `Delegador`, por caso: `intentos: dict[tuple[Frente, str], int]`, con la clave
`(frente, contexto)`.
- Sube en 1 cada vez que `_ejecutar` lanza al subagente con esa clave.
- Un rechazo no lo cambia.
- El contexto de listas se olvida al invalidarse (#6), así que una ejecución posterior de listas
  tiene otra clave o empieza de cero.

Regla de `delegar` con una clave ya vista:

```text
último resultado terminado                                         → lo guardado  (delegacion_repetida)
último error con causa reintentable y intentos ≤ MAX_REINTENTOS    → ejecutar     (frente_reintento)
llamada que esperó a esa misma ejecución en curso                  → su resultado (sin reintentar)
en otro caso                                                       → mismo error con reintentable=false
                                                                     y reintentos_restantes=0
                                                                     (reintento_denegado)
```

## CoberturaFrente y CoberturaCaso (R5)

Se calculan con `cobertura.calcular_cobertura(estado)` cada vez que se piden; no se guardan.

| Entidad | Campos |
|---------|--------|
| `CoberturaFrente` | `frente`, `cubierto: bool`, `motivo: str` (vacío si está cubierto), `causa: Causa \| None`, `intentos: int` |
| `CoberturaCaso` | `frentes: dict[Frente, CoberturaFrente]` (los cuatro, en el orden de `Frente`), `completa: bool`, `lineas() -> list[str]` (formato registrado de R5) |

De la situación del frente:

| Situación | Cubierto | Motivo |
|-----------|----------|--------|
| `terminado` | sí | — |
| `sin_iniciar` | no | «no se delegó» |
| `en_curso` | no | «seguía en curso» |
| `rechazado` | no | motivo del rechazo |
| `no_terminado` | no | motivo del frente (causa, sin texto de excepción) |

`completa` ⇔ los cuatro cubiertos. `Caso.completo` = `completa` y las condiciones del #7
(terminación normal, sin `cierre_sin_escalar` y sin `fallo_de_hook`).

## Cambios en entidades existentes

- **`EstadoCaso`** (#6): `errores: dict[Frente, dict]`, con el último `ErrorFrente` de cada frente.
  - Lo escriben `Delegador._concluir` y `_rechazar`.
  - Un frente que termina con normalidad borra su entrada.
- **`Caso`** (#6, #7):
  - `turnos: int | None`, con `num_turns` del `ResultMessage` del coordinador (R2);
  - `cobertura`, una propiedad que delega en `calcular_cobertura`.
- **`ResultadoFrente.detalle_terminacion`**: ante una excepción, solo `excepción <Tipo>`.

## Eventos nuevos (principio VI)

| Tipo | Frente | Detalle (ejemplo) |
|------|--------|-------------------|
| `frente_reintento` | el frente | «Reintento 1 de 1 del frente noticias: el intento anterior falló (error de la fuente: servicio_no_disponible).» |
| `reintento_denegado` | el frente | «No se reintenta el frente noticias: se agotaron los reintentos.» o «…: el error no es reintentable.» |
| `cobertura_sustituida` | — | «Cobertura puesta en registrar_informe: incompleta, 3 de 4 frentes (falta noticias). La declarada por el coordinador era distinta y se sustituyó por la calculada.» Se emite en el `PreToolUse`, antes de que la pasarela acepte la llamada: nunca dice que quedó registrada. |

## Constantes (configuracion.py)

| Constante | Valor | Comentario obligatorio |
|-----------|-------|------------------------|
| `MAX_REINTENTOS_POR_FRENTE` | `1` | Protección, no control del ciclo (principio III); indicación de la analista |
| `PASOS_FIJOS_PEOR_CASO` | `8` | Filas de la tabla de R2 que no dependen de otras constantes |
| `PRESUPUESTO_TURNOS_PEOR_CASO` | `PASOS_FIJOS_PEOR_CASO + len(Frente) * MAX_REINTENTOS_POR_FRENTE + MAX_CIERRES_IMPEDIDOS` (hoy 15) | Calculado, no literal; un test exige `<= MAX_TURNOS_SEGURIDAD` |

En `hooks.py`: `COBERTURA_NO_CALCULADA = "No se pudo calcular la cobertura; debe tratarse como
incompleta."`, el texto fijo con el que sale un escalamiento si falla el cálculo (R6).
| `MAX_TURNOS_SEGURIDAD` | `30` | Sin cambios |
