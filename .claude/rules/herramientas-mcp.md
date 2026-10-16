---
paths:
  - "src/servidor_mcp/**/*.py"
---

# Convenciones de las herramientas del servidor MCP

Principio IV de la constitución. Las fuentes de la pasarela se consumen solo a través de
este servidor, y las decisiones solo con `registrar_informe` y `escalar_a_cumplimiento`.

- **Descripción inequívoca**: cada herramienta dice qué hace y qué no hace. En
  particular, una mención en noticias no es una coincidencia en listas restrictivas, y
  varias coincidencias en el registro mercantil no autorizan a elegir una.
- **Errores estructurados**: un error devuelve un objeto con el tipo de error, un
  mensaje en español y si se puede reintentar (`reintentable`), además de lo que se
  alcanzó a obtener. Nunca una excepción sin capturar ni un texto libre.
- **Contenido separado de metadatos**: el resultado distingue el contenido de su fuente
  y su fecha, para que el informe pueda citar cada afirmación (principios I.4 y III).
- **Solo datos ficticios**: el servidor simula las fuentes con datos inventados en
  archivos locales (principio VII). Ningún dato real de comercios, personas, noticias,
  listas, documentos de identidad, NIT o tarjetas.
