# Contrato: API del caso

Interfaz que consumen los hooks del #7, el manejo de fallas del #8, el informe del #9, el
escalamiento del #10, la interfaz del #11 y los tests del #12. Módulo `due_diligence`.

## Ejecutar un caso

```text
ejecutar_caso(solicitud: str, *, ejecutor=None, hooks=None, reloj=None) -> Caso
Caso(...)                      # para quien necesita el estado y los eventos mientras corre
await caso.ejecutar(solicitud) # ejecuta el ciclo del coordinador
```

- `ejecutor`: un `EjecutorSubagente`. Por defecto `EjecutorSDK`; los tests pasan uno simulado (R1).
- `hooks`: diccionario `ClaudeAgentOptions.hooks` del SDK. **Se aplica al coordinador y a las opciones de
  cada subagente** (R7). Lo define el #7; el #6 solo lo reparte.
- `reloj`: función que devuelve la hora UTC con zona, para los tests.
- `ejecutar_caso` **no** carga el entorno (`cargar_entorno` solo la llama `__main__`, R8).

## Lectura mientras corre

| Miembro | Devuelve |
|---------|----------|
| `caso.estado.instantanea()` | copia del `EstadoCaso` (data-model): situación de cada frente, resultados, consultas, `comercio`, terminación |
| `caso.eventos()` | lista de `Evento` ordenada por `secuencia` |
| `caso.terminacion` | `Terminacion` del ciclo del coordinador, o `None` mientras corre |

Un frente sin terminar figura como `en_curso`, `no_terminado` o `no_iniciado`, nunca con un resultado
vacío (spec, US5-3).

## Opciones del SDK que construye el paquete

Una sola función (`configuracion.opciones_base`) fija, para **coordinador y subagentes**:

| Opción | Valor | Razón |
|--------|-------|-------|
| `setting_sources` | `[]` | ni `CLAUDE.md`, ni hooks, ni ajustes del repositorio o del usuario (R2) |
| `tools` | `[]` | sin herramientas integradas |
| `strict_mcp_config` | `True` | solo los servidores declarados en las opciones |
| `allowed_tools` / `disallowed_tools` | por agente, nombres completos (R3) | herramientas mínimas |
| `model` | coordinador y subagentes por separado (R9) | coste y calidad |
| `max_turns` | protección de seguridad, **solo aquí** | no controla el ciclo (R5) |
| `cwd` | raíz del repositorio | el servidor `pasarela` encuentra sus datos |

Herramientas de cada agente (R3): coordinador `mcp__delegacion__delegar_frente`,
`mcp__pasarela__registrar_informe`, `mcp__pasarela__escalar_a_cumplimiento`; cada subagente, la
herramienta `mcp__pasarela__…` de su frente.

## Clasificación del fin del ciclo

```text
clasificar(subtype, stop_reason, is_error, terminal_reason) -> Terminacion
```

| Entrada | Resultado |
|---------|-----------|
| `subtype == "error_max_turns"` (con cualquier `stop_reason`; en la práctica `tool_use`) | `LIMITE_SEGURIDAD` |
| `subtype == "success"`, `is_error` falso y `stop_reason == "end_turn"` | `NORMAL` |
| `stop_reason == "max_tokens"` | `ANOMALA` |
| cualquier otra combinación (otros `subtype` de error, `is_error` verdadero, `refusal`, `pause_turn`…) | `ANOMALA` |

El texto de la respuesta no es un parámetro. Al terminar, el coordinador y cada subagente registran un
evento (`terminacion` o `frente_fin`) con la clasificación y los tres valores originales. Si el SDK lanza
`ResultError` después del `ResultMessage` (lo hace con `error_max_turns`, R5), no se vuelve a clasificar;
si lo lanza sin haber entregado el mensaje, se clasifica con los atributos de la excepción.

## Ejecutor de subagentes

```text
class EjecutorSubagente(Protocol):
    async def __call__(self, frente: Frente, contexto: str, opciones: ClaudeAgentOptions) -> ResultadoFrente
```

`EjecutorSDK` hace un `query()` con `prompt=contexto` y `opciones`, recoge los `ToolUseBlock` y
`ToolResultBlock` como `Consulta` (R6) y clasifica el `ResultMessage`. Los tests lo sustituyen por un
ejecutor simulado que espera un tiempo conocido y devuelve un `ResultadoFrente`.

## Punto de entrada manual

`uv run python -m due_diligence "<solicitud>"`: carga el entorno (R8), ejecuta el caso con el modelo
real e imprime los eventos en orden. Es una ayuda para el quickstart; la interfaz de chat es del #11.
