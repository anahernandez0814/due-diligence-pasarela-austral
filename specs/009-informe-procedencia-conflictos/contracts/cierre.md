# Contrato: cierre del caso con el informe obligatorio (#9)

Amplía el `Stop` del coordinador del #7. Lo garantiza `evaluar_cierre` dentro del hook `Stop`,
envuelto con `fallar_cerrado`.

## Qué se exige

| Situación del caso | Escalamiento | Informe |
|--------------------|--------------|---------|
| Sin comercio identificado: varias coincidencias, ninguna o entrada inválida | Si hay causas (#7) | No |
| Comercio identificado | Si hay causas (#7) | Vigente (FR-011, FR-023) |
| Registro caído con un reintento disponible (R8) | Si hay causas | Vigente, o reintentar el registro: el motivo ofrece las dos salidas |
| Registro caído sin reintentos (R8) | Si hay causas, por ejemplo alto riesgo | Vigente, con el comercio pedido sin verificar |
| Caso sellado por un fallo de hook | Sí: el sello es una causa (R9) | Vigente y mínimo (`decide_cumplimiento`), si el caso requiere informe |

## Motivos del `Stop` (textos fijos, sin datos del comercio)

- Escalamiento: el del #7 (`motivo_de_escalar`), con la etiqueta nueva «fallo de un hook de
  verificación» cuando corresponde.
- Sin informe: «Falta registrar el informe del caso con registrar_informe (habilitar, no_habilitar
  o decide_cumplimiento).»
- Registro caído con un reintento disponible y sin informe: «El registro mercantil no respondió:
  reintenta el registro o registra el informe.»
- Informe no vigente: «El informe registrado ya no está vigente: cambió <la cobertura | los
  conflictos | las causas de escalamiento | el comercio> después de registrarlo. Registra uno
  nuevo.»
- Faltan los dos: primero el motivo del escalamiento y después «Luego registra el informe.»

## Devoluciones

- Cada devolución suma 1 a `libro.cierres_impedidos`, el contador del #7, compartido.
- Con `cierres_impedidos >= MAX_CIERRES_IMPEDIDOS` el cierre se permite y se marca lo que faltaba:
  `cierre_sin_escalar` (evento `cierre_sin_escalar`), `cierre_sin_informe` (evento
  `cierre_sin_informe`) o los dos.
- Si el propio `Stop` falla con una excepción, `fallar_cerrado` bloquea y cuenta igual. Agotadas
  las devoluciones, marca lo que falta con los mismos eventos; si tampoco puede saberlo, marca los
  dos por prudencia (fase 13). Como el sello del fallo es una causa (R9), falta el escalamiento
  salvo que uno anterior ya cubriera el sello.
- `PRESUPUESTO_TURNOS_PEOR_CASO` pasa a 19 de 30: se suma un informe nuevo por cada reintento
  posible, porque un reintento con éxito invalida el informe (R8).

## Vigencia (R7)

La huella del informe se calcula en el `PreToolUse` que lo acepta y se confirma en el `PostToolUse`
si la pasarela lo guardó. Un reintento que termina entre los dos hooks deja el informe no vigente.

## `Caso.completo`

Hace falta todo esto:
- la cobertura completa;
- la terminación normal;
- `not cierre_sin_escalar`;
- `not cierre_sin_informe`;
- `fallo_de_hook is None`;
- un informe vigente.

## Limitación conocida (#10)

El `Stop` se evalúa en cada fin de turno. Con el comercio identificado o el registro caído, también
cuando el coordinador termina el turno para preguntar algo al analista, se exige el informe. Un test
fija este comportamiento.
