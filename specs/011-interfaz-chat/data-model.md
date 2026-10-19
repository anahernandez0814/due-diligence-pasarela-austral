# Data model: Interfaz de chat (#11)

Estructuras nuevas o cambiadas. Las de `presentacion.py` son inmutables (`frozen`) y no conocen
Streamlit. Ninguna se guarda fuera de la sesión de la interfaz.

## Cambios en entidades existentes

### `RegistroEventos` (`eventos.py`)
- **Nuevo** `observador: Callable[[Evento], None] | None = None` en el constructor.
- `registrar` llama al observador **después de salir** del `with self._candado` (un
  `threading.Lock`, no reentrante), nunca dentro: un observador que registra otro evento no
  bloquea. Una excepción del observador se ignora: nunca llega al hook que registró el evento (R1).

### `configuracion.py`
- **Nueva** `comprobar_credencial(entorno=None) -> str | None` y sus mensajes
  `MENSAJE_SIN_CLAVE` y `MENSAJE_OTRA_CREDENCIAL` (R8). La usan el chat y `__main__.py`.

### `Caso` (`coordinador.py`)
- **Nuevo** parámetro `observador` (se pasa al `RegistroEventos`).
- **Nuevo** `turnos_por_turno: list[int | None]`: un valor por turno, en orden; `None` si el turno
  no dejó `ResultMessage` (R5). `turnos` sigue siendo la suma del caso.

### `hooks.py`
- Textos de `cobertura_sustituida` y `datos_sustituidos` (R11). Sin cambios de comportamiento.

### `coordinador.py`, instrucciones
- **Nueva** `_REGLA_FECHAS` en los dos modos (R9, R10).
- `_REGLA_RESUMEN` empieza por la cobertura y los frentes que fallaron (R4).

## Entidades nuevas (`presentacion.py`)

### `Indicador`
| Campo | Tipo | Notas |
|-------|------|-------|
| `tipo` | `str` | `delegacion`, `bloqueo`, `informe`, `escalamiento` o `aviso` |
| `titulo` | `str` | frase corta en español (R3) |
| `detalle` | `str` | motivo o detalle del evento, sin datos añadidos |
| `hora` | `str` | `HH:MM:SS (hora de Colombia)` (R9) |
| `secuencia` | `int` | la del evento: da el orden |

Se construye solo desde un `Evento` de la traza, nunca desde el texto del modelo.

### `FilaCobertura`
| Campo | Tipo | Notas |
|-------|------|-------|
| `frente` | `str` | en palabras |
| `cubierto` | `bool` | |
| `motivo` | `str` | vacío si está cubierto |

### `EstadoMostrado`
| Campo | Tipo | Notas |
|-------|------|-------|
| `clase` | `str` | `completo`, `incompleto` o `esperando` |
| `texto` | `str` | frase para el analista (R4) |

Regla: `clase == "completo"` si y solo si `caso.completo` (I.5).

### `TurnoMostrado`
| Campo | Tipo | Notas |
|-------|------|-------|
| `numero` | `int` | 1, 2, … dentro del caso |
| `mensaje` | `str` | el del analista |
| `aviso` | `str \| None` | p. ej. «Caso anterior cerrado; se inició un caso nuevo.» |
| `indicadores` | `tuple[Indicador, ...]` | en orden de `secuencia` |
| `cobertura` | `tuple[FilaCobertura, ...]` | los cuatro frentes, en el orden de `Frente` |
| `estado` | `EstadoMostrado` | |
| `respuesta` | `str` | la del coordinador, o el mensaje de fallo (R6) |
| `turnos` | `str` | `"N de 30"` o `"sin dato"` (R5) |

Orden de dibujo: mensaje → aviso → indicadores → cobertura → estado → respuesta → turnos.

### `Decision` (R6)
`StrEnum` con `NUEVO`, `CONTINUAR`, `AVISO_ESPERA` e `IGNORAR`, más el texto del aviso cuando lo
hay (`DecisionMensaje(accion, aviso)`).

### `Dependencias` (`chat.py`, R2)
| Campo | Tipo | Producción |
|-------|------|-----------|
| `cargar_entorno` | `Callable[[], object]` | `configuracion.cargar_entorno` |
| `entorno` | `Callable[[], Mapping[str, str]]` | `lambda: os.environ` |
| `crear_caso` | `Callable[[Callable[[Evento], None] \| None], Caso]` | `lambda obs: Caso(observador=obs)` |

## Estado de la sesión de Streamlit (`st.session_state`)

| Clave | Contenido |
|-------|-----------|
| `caso` | el `Caso` en curso, o ausente |
| `historial` | `list[TurnoMostrado]` del caso en curso |
| `pendiente` | el texto enviado que todavía no se procesó (R7), o ausente |
| `dependencias` | solo en los tests (R13) |

Transiciones: sin caso → (mensaje) → caso con turno 1 → (mensaje, caso incompleto o en espera) →
turno 2 del mismo caso; (mensaje, caso completo) → caso nuevo con aviso; («Caso nuevo») → sin
caso e historial vacío.

## Textos fijos nuevos (`presentacion.py`)

- `AVISO_CASO_NUEVO`, `AVISO_ESPERA` (con el motivo de la espera), `MENSAJE_FALLO_TURNO` (con el
  tipo de error), `MENSAJE_SIN_SESION` (movido desde `__main__`).
- Las tres líneas de modos activos (R12).
- Los nombres de los frentes en palabras (R3).
