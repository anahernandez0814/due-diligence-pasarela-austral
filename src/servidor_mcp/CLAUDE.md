# Servidor MCP de la pasarela

Convenciones de `src/servidor_mcp/`. Complementan `.claude/rules/herramientas-mcp.md` y la
constitución (principios I.4, IV y VII); no las repiten.

- **SDK**: `mcp` 2.x. Se usa `from mcp.server.mcpserver import MCPServer`, **no** `FastMCP`
  (`mcp.server.fastmcp` ya no existe). `CallToolResult` y `TextContent` se importan de
  `mcp.types`; `pydantic` está declarado en `pyproject.toml`.
- **Errores**: toda herramienta devuelve un `CallToolResult`. Los errores se construyen con
  `respuestas.error()` (`is_error=True`, `tipo`, `mensaje` en español, `reintentable`,
  `obtenido`). Nunca se lanza una excepción hacia el cliente: lo inesperado es `error_interno`.
  Solo `servicio_no_disponible` es reintentable.
- **Parámetros**: todos opcionales (`Annotated[Any, Field(description=...)] = None`) y validados
  dentro con `entradas.py`. El SDK rechaza, en inglés y sin estructura, un argumento ausente o mal
  tipado antes de entrar a la herramienta. El tipo esperado va en la descripción del parámetro.
- **Una sola forma de respuesta**: `resultado`, `hechos[]` (cada uno con `contenido` y
  `metadatos`) y `metadatos` de nivel superior. Nada de `contenido` fuera de un hecho. El
  contenido nunca lleva `fuente` ni `fecha`. Detalle en
  `specs/005-servidor-mcp-pasarela/contracts/herramientas.md`.
- **Coincidencias**: el registro busca por contención, ignorando la forma jurídica final; listas y
  noticias, por nombre completo. Nunca por parecido. El identificador no distingue mayúsculas.
  Ante varias coincidencias **no se elige una**.
- **Funciones por módulo**: `servidor.py` llama a `registro.f(...)`, no a `from .registro import f`,
  para que un `monkeypatch` actúe.
- **Nada en stdout**: es el canal del protocolo. Los diagnósticos van a stderr.
- **Datos**: solo ficticios, en `datos/*.json`, cada uno con `ficticio: true`, `aviso` y
  `fecha_corte`. Sin secuencias de 6 o más dígitos, sin dominios reales (`.example`). La fecha de
  las respuestas es la `fecha_corte` de la fuente, no el reloj.
- **Variables**: `PASARELA_FALLA_NOTICIAS` y `PASARELA_FALLA_REGISTRO` (#9; las dos se leen en cada
  llamada, no al arrancar, y simulan `servicio_no_disponible` reintentable) y
  `PASARELA_RESULTADOS_DIR` (carpeta de informes y escalamientos; por defecto `resultados/`, fuera
  de `.claude/` y en `.gitignore`). Los tests usan `monkeypatch` y `tmp_path`.
- **Tests**: `test_*.py` junto a cada módulo; `test_servidor.py` llama por el protocolo.
- **Sin reglas de negocio de orden**: el servidor simula fuentes; las reglas I.1 e I.2 las
  garantizan los hooks del SDK (ticket #7).
