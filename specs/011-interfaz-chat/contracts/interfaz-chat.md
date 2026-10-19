# Contrato: interfaz de chat y funciones de presentación (#11)

## Arranque

```bash
uv run streamlit run src/due_diligence/chat.py
```

1. Carga el entorno (`load_dotenv(override=False)`): no pisa variables ya definidas.
2. `configuracion.comprobar_credencial(entorno)`: si devuelve un mensaje, se muestra con `st.error` y la
   aplicación se detiene (`st.stop()`). No hay entrada de chat, no se crea ningún caso y no se
   llama al modelo. El valor de la clave nunca se muestra.
3. Franja fija con los modos activos (`modos_activos(entorno)`), si hay alguno.
4. Título, botón «Caso nuevo», historial y entrada del chat.

## Conversación

- Cada turno del historial se dibuja como: mensaje del analista → (aviso) → indicadores →
  cobertura → estado del caso → respuesta del coordinador → «Turnos del coordinador en este turno:
  N de 30».
- Mensaje enviado → `decidir_mensaje(caso, texto)`:
  - `IGNORAR`: no pasa nada;
  - `AVISO_ESPERA`: se muestra el aviso y no se llama al coordinador;
  - `NUEVO`: se descarta el caso anterior (si lo había) y se crea uno; si el anterior estaba
    completo, el turno lleva `AVISO_CASO_NUEVO`. El historial anterior no se dibuja y el aviso se
    ve desde el principio del turno, antes de «trabajando»;
  - `CONTINUAR`: `Caso.continuar(texto)`.
- Mientras un turno corre: la entrada y el botón «Caso nuevo» están deshabilitados y un
  contenedor «El coordinador está trabajando…» muestra los indicadores en vivo (R1, R7).
- Un fallo del turno se muestra como la respuesta del coordinador con `MENSAJE_SIN_SESION` o
  `MENSAJE_FALLO_TURNO`, nunca como traza.
- «Caso nuevo» vacía la conversación y descarta el caso.
- Mientras el caso espera al analista, el texto de ayuda de la entrada dice qué espera. El plan B
  de FR-005 (un aviso fijo encima de la entrada) **no se aplica**: Streamlit 1.66 sí envía un
  mensaje con solo espacios, que recibe `AVISO_ESPERA` (T033, R6).
- Configuración (`.streamlit/config.toml`, R15): sin la pregunta del correo de la primera ejecución
  y sin estadísticas de uso; la aplicación queda en http://localhost:8501.

## Funciones puras (`presentacion.py`)

| Función | Entrada | Salida |
|---------|---------|--------|
| `hora_colombia(marca)` | `datetime` con zona | `"HH:MM:SS (hora de Colombia)"` |
| `frente_en_palabras(frente)` | `Frente` | «registro mercantil», «listas restrictivas», «noticias» o «riesgo de categoría» |
| `indicador(evento)` | `Evento` | `Indicador` o `None` (mapa de R3) |
| `eventos_del_turno(eventos, n)` | eventos del caso, número de turno | los eventos de ese turno |
| `filas_cobertura(cobertura)` | `CoberturaCaso` | `tuple[FilaCobertura, ...]` |
| `estado_mostrado(caso)` | `Caso` | `EstadoMostrado` (orden de R4) |
| `resumen_del_turno(caso, n, mensaje, aviso=None, respuesta=None)` | `Caso` y datos del turno | `TurnoMostrado` |
| `decidir_mensaje(caso, texto)` | `Caso \| None`, `str` | `DecisionMensaje` (tabla de R6) |
| `aviso_espera(espera)` | `Espera` | `AVISO_ESPERA`: «El coordinador espera su respuesta. {motivo} El caso sigue sin completar.», en dos oraciones (lo usan el chat y la línea de comandos) |
| `mensaje_fallo_turno(error)` | excepción | `MENSAJE_FALLO_TURNO` con solo el tipo del error, sin traza |
| `modos_activos(entorno)` | `Mapping[str, str]` | `list[str]` (R12) |

Ninguna importa Streamlit, llama al modelo ni lee el entorno por su cuenta.

`configuracion.comprobar_credencial(entorno=None) -> str | None` (R8) también es pura, pero vive
en `configuracion.py` porque la usan los dos puntos de entrada.

## Línea de comandos (`python -m due_diligence`)

- Tras cargar el entorno, `comprobar_credencial()`: con un problema, el mismo mensaje que el chat
  en la salida de error y código de salida 2, sin crear el caso ni llamar al modelo (FR-006).

- «turnos del coordinador en este turno: N de 30», con el valor del último turno (FR-004).
- Línea vacía o fin de la entrada con la espera abierta: imprime `AVISO_ESPERA` y termina
  (FR-005). El código de salida no cambia.

## Eventos (cambio de texto, FR-009)

- `cobertura_sustituida`: «Cobertura puesta en {herramienta}: {resumen}. Se sustituyó por la
  calculada.» o «… Coincide con la declarada por el coordinador.»
- `datos_sustituidos`: «Datos del código puestos en {herramienta}: comercio verificado|sin
  verificar. {resumen de conflictos} Se sustituyeron por los calculados: {campos}.» o «…
  Coincide con lo declarado por el coordinador.»
