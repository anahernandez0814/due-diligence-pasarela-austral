# Contrato: suite de punta a punta y grupos de pruebas (#12)

## Comandos

| Grupo | Comando | Clave | Coste | Tiempo |
|-------|---------|-------|-------|--------|
| Determinista | `uv run pytest` | no | 0 | < 5 min (4:24 medido antes del ticket, R11) |
| Punta a punta | `uv run pytest -m e2e -rs` | sí | 1,10 USD medido (T027) | 85 s medido (T027) |
| Un caso | `uv run pytest -m e2e -rs -k caso_d` | sí | el de un caso | el de un caso |

- `uv run pytest` **nunca** selecciona un test `e2e`, tenga o no la clave (R4).
- Sin la clave, `-m e2e` omite los siete tests con el mensaje de `comprobar_credencial`, que se ve
  con `-rs`. Ningún test crea un `Caso` ni llama al modelo. «Skipped» no es «pasó».
- `PASARELA_E2E_PARALELO=<n>` limita cuántos casos corren a la vez. Por defecto son 7.
- Al terminar, el resumen de pytest añade una línea por caso con su coste y su duración, más el
  total (R8).

## Los siete tests

Cada test recibe solo su `Observacion` (o la lista de las de cada turno en el (d)) y comprueba,
como mínimo, lo de abajo. Las constantes se importan del código; nada lee el texto del modelo.

| Test | Arranque | Verificaciones |
|------|----------|----------------|
| `test_caso_a_alto_riesgo` | normal | Un escalamiento con `alto_riesgo` en sus causas. Un informe `decide_cumplimiento`. Ningún informe `habilitar`. |
| `test_caso_b_bajo_riesgo` | normal | Un informe `habilitar`. Cero escalamientos. Los cuatro frentes cubiertos. `completo`. |
| `test_caso_c_representante` | normal | Un escalamiento con `coincidencia_representante`. Ningún informe `habilitar`. |
| `test_caso_d_dos_turnos` | normal, dos turnos | **Turno 1**: `espera.clase == "identificador"` y `espera.motivo == MOTIVO_ESPERA_IDENTIFICADOR`; alguna consulta del registro con `clase_registro == "varias"`; cero consultas de listas; cero informes y cero escalamientos. **Turno 2** (`continuar("CO-AM-0004")`): `comercio.identificador == "CO-AM-0004"`; al menos una consulta de listas de tipo `comercio`, y todas por el identificador o el nombre de `CO-AM-0004`, ninguna por los de `CO-AM-0005`; un informe registrado. |
| `test_caso_e_listas_sin_identificar` | `PASARELA_MODO_DEMO_HOOKS=1` | Al menos un evento `bloqueo_regla` con `regla == "I.1"` y frente `listas`. Cero consultas de listas válidas. |
| `test_caso_f_noticias_caido` | `PASARELA_FALLA_NOTICIAS=1` | Un informe registrado cuya `cobertura` es igual a `cobertura_lineas` y declara noticias sin cubrir. `cobertura["noticias"].cubierto` es falso. `completo` es falso. |
| `test_caso_g_fechas_distintas` | normal | Un informe registrado con un conflicto `fecha_constitucion` de dos valores distintos, cada uno con una fuente distinta. |
| *(todos)* | | Ninguna consulta de listas va antes de una consulta del registro con `clase_registro == "unica"` (US1-8). |

Si una verificación falla por un camino válido del modelo y no por una garantía del sistema, se
cambia a lo que el sistema garantiza y el cambio se anota en `research.md` (R13, en la
implementación). Si falta una garantía del sistema, es un error del producto.

## Interrupción de la interfaz (FR-008, R9)

| Situación | Resultado |
|-----------|-----------|
| `ScriptControlException` del observador dentro de un hook | El hook devuelve su decisión (la de I.1 o I.2, si deniega). Después se cancela el turno y se relanza la misma excepción. |
| `ScriptControlException` del observador fuera de un hook | Se cancela el turno en el momento y se relanza la misma excepción. |
| `ScriptControlException` desde el cuerpo de un hook | En `PreToolUse`, deniega con el motivo genérico, sin sello. En los demás tipos, permite. Después se relanza. |
| `Exception` del observador | Se ignora (#11). |
| `CancelledError`, `KeyboardInterrupt` o `SystemExit` | Se propagan, sin cambios. |
| En el chat, la interrupción relanzada | El turno queda en el historial como interrumpido, se quita el mensaje pendiente y Streamlit para o recarga. |
| En el chat, el mensaje siguiente a un turno interrumpido | Abre un caso nuevo con el aviso «El turno anterior se interrumpió; se inició un caso nuevo.». Nunca reanuda la sesión cortada (opción A). |
| En la línea de comandos | Sin cambios: no declara interrupciones. |
