# Quickstart: validación del servidor MCP de la pasarela

Cada escenario indica lo que debe pasar. Los marcados **[sesión nueva]** se hacen en una
sesión de Claude Code **recién abierta en la raíz del repositorio**, no con un comando lanzado a
mano (R7). Validación solo en Windows (FR-021 de #3 queda como declaración).

Requisitos: `uv sync`, rama `005-servidor-mcp-pasarela`, `GITHUB_PAT` definida.

## Q1. Calidad y suite

1. `uv run ruff format .` y `uv run ruff check .`: sin cambios ni avisos.
2. `uv run pytest`: todo en verde, incluidos los tests de `src/servidor_mcp/`, los de
   `.claude/hooks/` y la revisión del repositorio de #3 (que recorre los JSON de datos).

## Q2. Las seis herramientas por el protocolo

`uv run pytest src/servidor_mcp/test_servidor.py`: el cliente en memoria lista exactamente las
seis herramientas, sus descripciones tienen las frases de R10 y cada una responde por el
protocolo. Además, por el protocolo, un campo ausente y un tipo incorrecto en
`registrar_informe`, `escalar_a_cumplimiento` y `consultar_registro_mercantil` devuelven un error
estructurado en español (`campos_obligatorios_ausentes` con `campos_faltantes`, o
`entrada_invalida`), nunca el texto de pydantic.

## Q3. Los datos reproducen los siete casos

`uv run pytest src/servidor_mcp/test_datos_casos.py`: un test «datos del caso (x)» por cada caso
(a)–(g), según el mapa de `data-model.md`. Solo prueba que los datos reproducen el caso; el caso
completo es del #12. Debe verse que (e) y (f) **no añaden datos** y que (c) usa al representante de
`CO-PL-0003`.

## Q4. Criterios que se verifican a mano sobre los datos

1. Abrir `datos/*.json`: todos con `"ficticio": true` y `aviso`; dominios `.example`.
2. Buscar en `datos/` una secuencia de 6 o más dígitos seguidos: no hay ninguna.
3. `uv run pytest .claude/hooks/test_revision_repositorio.py`: sin hallazgos (SC-006).

## Q5. Resultados fuera de git

1. Ejecutar `uv run pytest src/servidor_mcp/test_decisiones.py`: crea archivos solo en
   `tmp_path`; `git status --short` no muestra nada nuevo.
2. Con `PASARELA_RESULTADOS_DIR` sin definir, lanzar una vez `registrar_informe` (script
   desechable fuera del repositorio) y comprobar que el archivo cae en `resultados/informes/` y
   que `git check-ignore resultados/informes/<id>.json` lo reconoce.
3. Borrar `resultados/` al terminar. No debe haber nada en `.claude/`.

## Q6. Conexión en Claude Code **[sesión nueva]**

1. Comprobar en `.claude/settings.json` que `enabledMcpjsonServers` es `["github",
   "pasarela"]` y en `.mcp.json` que el bloque `pasarela` **no** usa `${CLAUDE_PROJECT_DIR}`
   (primera opción de R7) ni ninguna credencial.
2. Abrir una sesión nueva en la raíz y ejecutar `/mcp`.
3. Esperado: `github` y `pasarela` conectados, **sin pedir aprobación**, y las seis herramientas
   `mcp__pasarela__*` listadas.
4. Si `pasarela` no conecta: anotar el error de `/mcp` y pasar a la segunda opción de R7
   (`--directory ${CLAUDE_PROJECT_DIR}`), comprobando en otra sesión nueva que la variable se
   expande. Registrar cuál opción funcionó en `DECISIONES.md`.
5. Ejercicio de humo desde la conversación: pedir `consultar_registro_mercantil` con
   «almacén mirador» y comprobar que devuelve dos coincidencias, sin elegir.

## Q7. Caída de noticias

1. En proceso (tests): `buscar_noticias` devuelve `servicio_no_disponible` con
   `reintentable: true` con la variable en `1`, y funciona al ponerla en `0` **en la misma
   instancia** (R5).
2. Relanzando el servidor con la variable (`PASARELA_FALLA_NOTICIAS=1`) y llamando por stdio con un
   script desechable: mismo error; las otras cuatro herramientas responden.

## Q8. Guardas de #3 sobre este ticket

1. Con la rama `005-*` y `spec.md`, `plan.md` y `tasks.md` commiteados, crear un `.py` en
   `src/servidor_mcp/` pasa `guarda_spec_previa`.
2. Con un script desechable **fuera del repositorio**, igual que en #3: construir en ejecución una
   tarjeta (la función `tarjeta` de `.claude/hooks/test_detector_datos.py`, sin escribir el valor en
   ningún archivo) y pasar por stdin a `uv run --no-project --python 3.12
   .claude/hooks/guarda_datos.py` un `Write` sobre `src/servidor_mcp/datos/prueba.json` con ese
   valor. Esperado: salida 2, bloqueado, y el mensaje no repite el valor. Nada se escribe en el
   repositorio.
3. `uv run pytest` sigue en verde con y sin `PYTHONUTF8`/`PYTHONIOENCODING`.

## Criterio de cierre

Q1 a Q8 con el resultado esperado, anotados en `tasks.md`. La revisión previa de #4 corre en
`/abrir-pr`.
