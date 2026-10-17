# Implementation Plan: Servidor MCP de la pasarela con datos ficticios

**Branch**: `005-servidor-mcp-pasarela` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-servidor-mcp-pasarela/spec.md`

## Summary

Servidor MCP propio (`pasarela`, por stdio) con seis herramientas que simulan las cuatro fuentes
de la pasarela y los dos canales de decisión, con datos ficticios en JSON local. Se construye con
`mcp` 2.3.0 (`MCPServer`, no `FastMCP`, R1). Cada herramienta devuelve contenido separado de
metadatos y, ante un fallo, un error estructurado con `reintentable` y lo obtenido, construido con
`CallToolResult(is_error=True)` (R2). Como el SDK rechaza por su cuenta, en inglés y sin
estructura, un argumento ausente o mal tipado, todos los parámetros son opcionales (`Any = None`)
y se validan dentro de la herramienta (R2). El servidor solo simula fuentes: las reglas I.1 e I.2 las
garantizan los hooks del #7.

Decisiones del analista incorporadas: servidor en `enabledMcpjsonServers`, variable de noticias
leída en cada llamada, carpeta de resultados por variable de entorno y fuera de `.claude/`, mapa
caso→dato, comando de `.mcp.json` probado en una sesión nueva, dependencia con `uv add`.

## Technical Context

**Language/Version**: Python 3.12 (uv).

**Primary Dependencies**: `mcp>=2.3,<3`, añadida con `uv add "mcp>=2.3,<3"` (actualiza
`pyproject.toml` y `uv.lock`). Sin otras dependencias de ejecución.

**Storage**: JSON de solo lectura en `src/servidor_mcp/datos/` y, para informes y casos escalados,
JSON en la carpeta `PASARELA_RESULTADOS_DIR` (por defecto `resultados/`, ignorada por git).

**Testing**: pytest junto al código; cliente en memoria del SDK para probar por el protocolo.

**Target Platform**: Windows validado a mano; el diseño usa `pathlib`, `os.replace` y la biblioteca
estándar, sin rutas del sistema.

**Project Type**: servidor MCP (stdio) dentro de la librería `servidor_mcp`.

**Performance Goals**: respuesta interactiva; los datos son pocos y se cargan una vez por proceso.

**Constraints**: stdout reservado al protocolo (nada se imprime); sin credenciales; solo datos
ficticios; la variable de noticias se lee en cada llamada.

**Scale/Scope**: seis comercios en dos fuentes, dos listas restrictivas, unas pocas noticias y nueve
categorías.

## Constitution Check

*GATE: pasa antes de la investigación y se vuelve a comprobar tras el diseño.*

| Principio | Estado | Cómo |
|-----------|--------|------|
| I.4 (fuente en cada afirmación; contradicciones visibles) | Cumple | Un hecho por fuente; ninguna coincidencia marcada como elegida (R9). |
| I.5 (fuente caída no se presenta como completo) | Cumple | `servicio_no_disponible`, reintentable, con la descripción que avisa de que el frente queda sin cubrir (R5, R10). |
| I.1, I.2, I.3 | No aplica al servidor | Las garantizan los hooks del SDK del #7; el servidor solo simula fuentes (FR-017). Los datos reproducen los casos (a), (c) y (e) para que el #7 los pruebe. |
| II (garantizado vs. sugerido) | Cumple | El servidor no pretende garantizar reglas; la descripción de listas lo dice como guía (R10). |
| III | Cumple | Errores estructurados con `obtenido` y `reintentable`; contenido separado de metadatos. |
| IV | Cumple | Seis herramientas con descripción inequívoca; decisiones solo por `registrar_informe` y `escalar_a_cumplimiento`. |
| V | Cumple | El escalamiento exige los cinco campos del resumen autosuficiente (R11). |
| VI | No aplica | La interfaz es del #11. |
| VII | Cumple | Datos inventados, `.example`, sin secuencias de 6 o más dígitos; `guarda_datos` y su revisión del repositorio los vigilan. |
| VIII | Cumple | Sin credenciales: `.mcp.json` no lleva secretos y las variables `PASARELA_*` no lo son. |
| IX | Cumple | Ticket #5, rama propia, spec, plan y tareas antes del código. |
| X | Cumple | pytest junto al código; ruff tras cada edición; revisión previa en `/abrir-pr`. Aquí solo se prueba que los datos reproducen cada caso (`test_datos_casos.py`, tests «datos del caso (x)»); los casos completos, con el coordinador y los hooks, son del #12. |

**Desviaciones nuevas**: ninguna. No hay Complexity Tracking.

**Re-evaluación tras el diseño**: sin cambios. El riesgo de VIII (que el servidor arranque desde
otro directorio y no encuentre datos) no es de credenciales: se cubre con `datos_no_disponibles`
y con Q6.

## Project Structure

### Documentation (this feature)

```text
specs/005-servidor-mcp-pasarela/
├── spec.md
├── plan.md
├── research.md          # R1 a R12
├── data-model.md        # entidades, errores y mapa caso→dato
├── quickstart.md        # Q1 a Q8
├── contracts/
│   └── herramientas.md  # las seis herramientas y la forma de sus respuestas
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks (no existe todavía)
```

### Source Code (repository root)

```text
src/servidor_mcp/
├── __init__.py               # existente
├── __main__.py               # python -m servidor_mcp → servidor.run()
├── CLAUDE.md                 # convenciones del servidor
├── servidor.py               # MCPServer y registro de las seis herramientas
├── respuestas.py             # respuesta() y error(): CallToolResult (R2, R9)
├── entradas.py               # validadores de parámetros Any: nunca lanzan (R2)
├── normalizar.py             # normalizar() y reglas de coincidencia (R3)
├── datos.py                  # carga y validación de los JSON; DatosNoDisponibles
├── registro.py               # consultar_registro_mercantil
├── listas.py                 # consultar_listas_restrictivas
├── noticias.py               # buscar_noticias (variable leída por llamada, R5)
├── riesgo.py                 # consultar_riesgo_categoria
├── decisiones.py             # registrar_informe y escalar_a_cumplimiento (R6, R11)
├── datos/
│   ├── registro_rmf_sur.json
│   ├── registro_rufe.json
│   ├── listas_restrictivas.json
│   ├── noticias.json
│   └── categorias.json
├── test_humo.py              # existente
├── test_normalizar.py
├── test_respuestas.py
├── test_entradas.py
├── test_datos.py
├── test_registro.py
├── test_listas.py
├── test_noticias.py
├── test_riesgo.py
├── test_decisiones.py
├── test_servidor.py          # cliente en memoria: las seis herramientas por el protocolo
└── test_datos_casos.py       # «datos del caso (x)», de (a) a (g): solo los datos

.mcp.json                     # + bloque "pasarela" (R7)
.claude/settings.json         # + "pasarela" en enabledMcpjsonServers (R7)
.gitignore                    # + resultados/
pyproject.toml, uv.lock       # + mcp (uv add)
DECISIONES.md                 # + entrada 6 de 4 líneas como máximo; el detalle, en research.md
README.md                     # + sección breve del servidor
```

**Structure Decision**: un módulo por herramienta con su test al lado, porque la regla de `tests`
de #3 pide los tests junto al código y cada herramienta tiene reglas distintas. La lógica pura
(`normalizar`, búsqueda, validación) está separada del registro en `servidor.py`, de modo que los
tests llamen a las funciones y, aparte, a las herramientas por el protocolo.

**Código protegido**: `.mcp.json` y `.claude/settings.json` son código protegido de #3, y
`src/servidor_mcp/*.py` también; solo se editan con spec, plan y tareas del ticket commiteados.

## Orden de implementación

1. `uv add "mcp>=2.3,<3"`; `.gitignore`.
2. `normalizar.py`, `respuestas.py`, `entradas.py` y `datos.py` con sus tests.
3. Los cinco archivos de datos y `test_datos.py`.
4. Herramientas de consulta (`registro`, `listas`, `noticias`, `riesgo`) con sus tests.
5. `decisiones.py` con su test (carpeta por variable, `tmp_path`).
6. `servidor.py`, `__main__.py` y `test_servidor.py` (con campo ausente y tipo incorrecto por el
   protocolo); después `test_datos_casos.py`.
7. `.mcp.json`, `.claude/settings.json` y `src/servidor_mcp/CLAUDE.md`.
8. README y `DECISIONES.md`.
9. Quickstart Q1 a Q8; **Q6 en una sesión nueva**.

## Riesgos residuales (irán a `DECISIONES.md`)

- La caída de noticias se activa al lanzar el servidor, no desde la conversación (R5).
- La raíz por defecto de `resultados/` se calcula desde `__file__` y vale con la instalación
  editable del proyecto (R6).
- El comando de `.mcp.json` depende de abrir Claude Code en la raíz y de que `uv sync` esté hecho
  (R7); Q6 lo comprueba.
- Los nombres de los datos son inventados pero verosímiles: no se descarta un homónimo real (R8).

## Decisiones para la analista

1. **Mínimo de 3 caracteres** en las búsquedas por nombre (R3): validado, solo para el nombre; ya
   está en la spec.
2. **Noticias por nombre completo** o identificador, igual que las listas (R3): validado; ya está en
   la spec.
3. **`mcp` 2.x**: el rango `>=2.3,<3` obliga a `MCPServer`; casi toda la documentación pública es de
   1.x (R1).
