# Investigación: Servidor MCP de la pasarela con datos ficticios

Cada decisión indica su fuente. Lo marcado **(medido)** se comprobó en un entorno temporal
con `mcp` 2.3.0 instalado, fuera del repositorio. Nada de esto está en la documentación que
conocía el equipo antes del ticket.

## R1. SDK: `mcp` 2.3.0 y `MCPServer`, no `FastMCP`

- **Decisión**: dependencia `mcp` añadida con `uv add "mcp>=2.3,<3"` (el rango fija la versión
  mayor); servidor con `from mcp.server.mcpserver import MCPServer` y herramientas con
  `@servidor.tool()`.
- **Medido**: la última versión es `mcp` 2.3.0. En la 2.x, `mcp.server.fastmcp` **ya no
  existe**: importarlo lanza `ModuleNotFoundError` y remite a la guía de migración
  (`FastMCP` pasa a `MCPServer`). Casi todos los ejemplos publicados son de 1.x y no
  funcionan.
- **Medido**: `MCPServer.run()` usa stdio por defecto; la descripción de una herramienta sale
  del parámetro `description=` o de su docstring.
- **Alternativas descartadas**:
  - Fijar `mcp<2` para usar `FastMCP`: arrastra una versión que ya no recibe cambios.
  - Implementar el protocolo a mano: reinventa lo que da el SDK.

## R2. Errores estructurados: `CallToolResult(is_error=True)` con contenido estructurado

- **Medido**: una excepción dentro de una herramienta llega al cliente como `is_error=True`
  con **texto libre**, justo lo que `.claude/rules/herramientas-mcp.md` prohíbe. Devolver un
  `dict` marca `is_error=False`. Devolver `CallToolResult(content=[...], is_error=True,
  structured_content={...})` conserva las dos cosas y llega intacto al cliente.
- **Decisión**: todas las herramientas se anotan `-> CallToolResult` y construyen su
  resultado con dos funciones (`respuesta()` y `error()`, en `respuestas.py`). El texto
  (`content`) es el mismo JSON que `structured_content`, para el cliente que solo lee texto.
  Ninguna herramienta deja escapar una excepción: un `try/except` envuelve el cuerpo y
  convierte lo inesperado en `error_interno`, no reintentable.
- **Medido, la validación del SDK**: un argumento ausente o de tipo incorrecto lo rechaza el
  SDK **antes de entrar a la herramienta**, con `is_error=True`, texto libre de pydantic en
  inglés (`Field required`, `Input should be a valid string`) y **sin `structured_content`**.
  El `try/except` del cuerpo no lo ve. Por eso **todos los parámetros se declaran opcionales
  y sin tipo estricto** (`Annotated[Any, Field(description=...)] = None`), y la herramienta
  valida dentro:
  - campo ausente o vacío en `registrar_informe` y `escalar_a_cumplimiento`:
    `campos_obligatorios_ausentes` con `campos_faltantes`;
  - tipo incorrecto (un número donde va un texto, un texto donde va un objeto) o combinación
    inválida: `entrada_invalida`, en español, no reintentable;
  - lo mismo en las herramientas de consulta (parámetro ausente o de tipo incorrecto).
- **Medido**: con `Any = None` el SDK pasa el valor tal cual (`None`, un número o un objeto) y
  el esquema que ve el cliente conserva la `description` del parámetro, pero pierde el
  `type`. Por eso **la forma esperada va en la descripción de cada parámetro**
  (por ejemplo «Texto. Nombre completo del comercio»), y es el contrato (`contracts/`) el que
  fija los tipos.
- **Medido**: con `-> CallToolResult` la herramienta no declara `output_schema`. El esquema se
  documenta en `contracts/herramientas.md` y lo comprueban los tests.
- **Alternativa descartada**: lanzar `ToolError`: pierde el indicador `reintentable`.

## R3. Normalización y coincidencia de nombres

- **Decisión**: `normalizar(texto)` (en `normalizar.py`):
  1. NFKD y quitar las marcas combinadas (tildes y diéresis; `ñ` pasa a `n`);
  2. minúsculas con `casefold`;
  3. **eliminar** los puntos y apóstrofos (`S.A.S.` → `sas`, `O'Brien` → `obrien`);
  4. sustituir por un espacio cualquier otro carácter que no sea letra o dígito (coma,
     guion, barra, paréntesis);
  5. colapsar los espacios repetidos y recortar.
- **Registro mercantil**: el texto buscado normalizado debe estar **contenido** como
  subcadena en el nombre normalizado; se devuelven todas las coincidencias, en orden de
  identificador. Con `identificador` la coincidencia es exacta, **sin distinguir mayúsculas**
  (también en listas y noticias).
- **Forma jurídica final, solo en el registro**: `sin_forma_juridica()` quita del final del
  nombre normalizado `sas`, `sa`, `ltda`, `eu`, `sca` y `s en c` (de «S. en C.»), en el texto
  buscado y en el nombre del comercio. Motivo: «Almacén Mirador SAS» solo devolvía
  `CO-AM-0004` (`almacen mirador sas` no está contenido en `almacen mirador norte sas`) y el
  caso (d) no se reproducía con el mensaje natural del analista. Listas y noticias siguen con el
  nombre completo, forma jurídica incluida, para no ampliar coincidencias donde la precisión
  importa (I.2).
- **Listas restrictivas y noticias**: igualdad del nombre completo normalizado, o del
  identificador. Nunca parcial.
- **Mínimo de 3 caracteres, solo para `nombre`** (decisión validada por la analista y recogida
  en la spec): el nombre buscado debe tener **al menos 3 caracteres normalizados, contados después de quitar la forma jurídica final** (`SAS` solo no cumple);
  con menos,
  `entrada_invalida` no reintentable. Sin mínimo, `a` devolvería todo el registro. **No aplica al
  `identificador`**: uno desconocido, aunque sea corto, da `sin_coincidencias`.
- **Noticias** (decisión validada y recogida en la spec): se aplica la regla de las listas
  (igualdad del nombre completo normalizado o del identificador) para que "una mención no sea
  una coincidencia difusa". Una noticia menciona entidades por nombre completo.
- **Alternativas descartadas**: coincidencia por palabras sueltas o por parecido
  (Levenshtein): produce coincidencias que la analista no puede justificar (I.2 exige
  precisión en listas).

## R4. Categoría: entrada de la consulta, no dato del registro

- **Decisión** (ajuste 4 de la revisión de la spec): `consultar_riesgo_categoria(categoria)`
  recibe la categoría que el analista nombró. El registro mercantil no la devuelve.
- La categoría se compara **normalizada** con `normalizar()`. La descripción de la
  herramienta **lista las categorías conocidas**, generadas desde `categorias.json` al
  construir el servidor, para que el agente no tenga que adivinar nombres.
- Niveles: `alto`, `medio` y `bajo`. Los cuatro `alto` son los del enunciado; el resto de
  categorías conocidas son `medio` o `bajo`. Una desconocida devuelve
  `resultado: "categoria_desconocida"` con la lista de conocidas y **sin nivel**.
- **Alternativa descartada**: tratar la desconocida como riesgo alto: lo decide la regla de
  negocio (I.3), no la fuente; el servidor solo declara que no la reconoce.

## R5. Caída de noticias: la variable se lee en cada llamada

- **Decisión** (2 del usuario): `os.environ.get("PASARELA_FALLA_NOTICIAS") == "1"` dentro de
  `buscar_noticias`, en cada llamada y no al importar el módulo ni al arrancar. Así un test
  activa y desactiva la caída con `monkeypatch`, sin reiniciar el servidor.
- Con cualquier valor distinto de `"1"` el servicio funciona. El error es `servicio_no_disponible`,
  **reintentable**, con `obtenido` vacío.
- **Límite declarado**: un servidor ya lanzado por Claude Code hereda su entorno al arrancar;
  la variable no se puede cambiar desde la conversación. La caída se prueba en proceso
  (tests) o relanzando el servidor con la variable.

## R6. Carpeta de resultados

- **Decisión** (3 del usuario): la ruta sale de `PASARELA_RESULTADOS_DIR`; si no está definida,
  `resultados/` en la raíz del repositorio (calculada desde `__file__`: `src/servidor_mcp/` →
  raíz). Los tests definen la variable con `monkeypatch.setenv` y `tmp_path`.
- Queda **fuera de `.claude/`** (esa carpeta es configuración y está protegida) y se añade
  `resultados/` a `.gitignore`. Dentro: `informes/<id>.json` y `escalamientos/<id>.json`.
- Escritura atómica (archivo temporal y `os.replace`) para que una lectura nunca vea un JSON
  a medias. La carpeta se crea si no existe; si no se puede escribir, `error_de_almacenamiento`
  (no reintentable).
- Identificador: `INF-<uuid4 hex[:8]>` y `ESC-<uuid4 hex[:8]>`. Dos informes del mismo comercio
  se conservan, cada uno con su id.
- **Límite**: la raíz calculada desde `__file__` vale con la instalación editable de `uv`
  (la del proyecto). Si el paquete se instalara en otro sitio, hay que definir la variable.

## R7. Registro en `.mcp.json` y `enabledMcpjsonServers`

- **Decisión** (1 del usuario): se añade `"pasarela"` a `enabledMcpjsonServers` de
  `.claude/settings.json`, que hoy solo tiene `"github"`. **Sin eso, el servidor del
  proyecto queda pendiente de aprobación y no conecta** sin que alguien lo apruebe (SC-007).
- **Decisión** (5): el comando de `.mcp.json` **no** da por hecho que `${CLAUDE_PROJECT_DIR}`
  se expanda en ese archivo (la documentación lo garantiza para los hooks, no para `.mcp.json`).
  - **Primera opción**, sin variables:
    `{"type": "stdio", "command": "uv", "args": ["run", "--quiet", "python", "-m",
    "servidor_mcp"]}`. Claude Code lanza el servidor desde su directorio de trabajo, y
    el proyecto exige abrirlo siempre en la raíz (`CLAUDE.md`).
  - **Segunda opción**, solo si la primera no conecta y la expansión se comprueba en una
    sesión nueva: `["run", "--quiet", "--directory", "${CLAUDE_PROJECT_DIR}", ...]`.
  - Cuál queda se decide con el quickstart Q6, **en una sesión nueva abierta en la raíz**, no
    con un lanzamiento a mano desde la terminal (que siempre funciona desde la raíz).
  - Sin credenciales: el bloque no lleva `env` con secretos. `PASARELA_*` no son secretos.
- `uv run --quiet`: el primer arranque sincroniza el entorno y no debe imprimir en stdout
  (rompería el protocolo); `--quiet` y la sincronización previa que exige el README
  (`uv sync`) lo evitan.
- **Riesgo**: si la sincronización del primer arranque tarda más que el tiempo de espera de
  conexión de Claude Code, el servidor aparece caído. El README ya pide `uv sync` antes de
  abrir Claude Code; el quickstart lo comprueba.

## R8. Datos ficticios

- **Decisión**: JSON en `src/servidor_mcp/datos/`, un archivo por frente, cada uno con
  `"ficticio": true`, un `"aviso"` en español y la `"fecha_corte"` de la fuente:
  `registro_rmf_sur.json`, `registro_rufe.json` (las dos fuentes registrales),
  `listas_restrictivas.json`, `noticias.json` y `categorias.json`.
- **Fuentes ficticias**: «Registro Mercantil Ficticio del Sur» (RMF-Sur) y «Registro Único
  Ficticio de Empresas» (RUFE); listas «Lista Restrictiva Ficticia A» y «B»; noticias de
  «Diario Ficticio del Sur». Dominios `.example` en las URL. Ninguna entidad real.
- **Identificadores**: `CO-<2 letras>-<4 dígitos>` para comercios y `PE-<4 dígitos>` para
  personas, sin ninguna secuencia de 6 o más dígitos seguidos: ni NIT, ni cédula (con
  contexto), ni tarjeta (Luhn de 13 a 19) pueden coincidir con el patrón de `guarda_datos`.
- **La fecha de las respuestas** es la `fecha_corte` del archivo de la fuente, no el reloj:
  así los tests son deterministas y la fecha describe la fuente (principio I.4).
- **Residual: nombres verosímiles**. Los nombres de personas y comercios son inventados, pero
  verosímiles, y no se puede descartar un homónimo real. Se acepta como residual de la regla
  VII: los nombres no se contrastan con ninguna fuente real, y cada archivo lleva el aviso de
  que es ficticio. Cualquier coincidencia con una persona o empresa real es casual.
- **Dentro de `src/`**: el empaquetado de `uv_build` incluye los archivos del módulo. Los JSON
  no son código protegido (la guarda protege `src/**/*.py`), pero los lee la revisión de
  datos con forma real de #3 (`git ls-files`).

## R9. Estructura de la respuesta: contenido separado de metadatos

- **Decisión**: toda consulta devuelve
  `{"resultado": <estado>, "hechos": [...], "metadatos": {"fuentes": [...], "fecha": ...}}`.
  Cada **hecho** es `{"contenido": {...}, "metadatos": {"fuente": ..., "fecha": ...}}`. Con
  `resultado: "sin_coincidencias"` los hechos van vacíos y los metadatos van igual
  (ajuste 5 de la revisión de la spec).
- **Una sola forma** (análisis I1): ninguna respuesta de éxito lleva `contenido` fuera de un
  hecho. `registrar_informe` y `escalar_a_cumplimiento` devuelven un hecho con `contenido`
  `{id}` y metadatos con la fuente «Registro local de informes (ficticio)» o «Registro local de
  escalamientos (ficticio)» y la fecha de registro. Una categoría desconocida devuelve un hecho
  con `contenido` `{categoria, categorias_conocidas}`, sin nivel, con la fuente de
  `categorias.json`.
- En el registro, una coincidencia con dos fuentes lleva **un hecho por fuente**: el que dice
  `fecha_constitucion: 2016-03-14` con la fuente RMF-Sur y el que dice `2017-09-02` con RUFE.
  El servidor no resuelve la contradicción ni marca una como la correcta (I.4).
- **Coincidencias** (análisis I2): el registro añade en el nivel superior `coincidencias`, la
  lista de identificadores de comercio distintos, en orden. SC-004 y el caso (d) cuentan
  `coincidencias`, no `hechos`: `almacen mirador` da 2 coincidencias y 4 hechos.
- **Fecha** (análisis I3): `metadatos.fecha` es la `fecha_corte` de la fuente; **si la respuesta
  consulta varias fuentes, la más antigua de ellas** (registro: `2026-09-28`; listas: la más
  antigua de las listas), y cada hecho conserva la suya. La `fecha` de cada hecho es la de su
  origen (en noticias, la de la noticia; en los canales de decisión, la de registro).
- Ninguna coincidencia lleva un campo `elegida` ni un orden que sugiera preferencia: el
  orden es el del identificador.
- Un test comprueba que ninguna respuesta contiene `contenido` con claves de metadatos
  (`fuente`, `fecha`) ni `metadatos` con claves de contenido.

## R10. Descripciones de las herramientas

- **Decisión**: cada descripción tiene tres partes: **qué hace**, **qué no hace** y **cómo
  responde cuando no hay resultados**. Textos en `contracts/herramientas.md`. Un test comprueba
  que contienen las frases que fija la constitución: la mención en noticias no es una
  coincidencia en listas, varias coincidencias no autorizan a elegir, y
  `registrar_informe`/`escalar_a_cumplimiento` son los únicos canales de decisión.
- La de `consultar_listas_restrictivas` **no** dice «consúltese solo con identificación
  unívoca» como regla que el servidor imponga: la regla I.1 la garantiza el hook del #7. La
  descripción indica que debe llamarse con el identificador del comercio ya identificado, como
  guía, y el contrato lo anota como "sugerido, no garantizado".

## R11. Validación de los canales de decisión

- **`registrar_informe`** exige `comercio` (con `identificador` y `nombre`), `recomendacion`
  (texto no vacío; el vocabulario de recomendaciones lo fijan #9 y #10), `hallazgos` (un objeto
  `frente → hallazgo`, cada hallazgo con `contenido` y `fuente`) y `cobertura` (texto o lista
  no vacíos).
- **`escalar_a_cumplimiento`** exige los cinco campos del comportamiento 11: `comercio`,
  `hallazgos`, `cobertura`, `causa_escalamiento`, `accion_recomendada`.
- Si faltan campos, el error es `campos_obligatorios_ausentes`, **no reintentable**, y
  nombra **todos** los que faltan (`campos_faltantes`), no solo el primero. Un campo
  presente pero vacío cuenta como faltante.
- El servidor **no valida el contenido de negocio** (no comprueba que una categoría alta no
  reciba habilitación): eso es del hook del #7 sobre `registrar_informe`.

## R12. Tests

- pytest junto a cada módulo (`test_normalizar.py`, `test_registro.py`, `test_listas.py`,
  `test_noticias.py`, `test_riesgo.py`, `test_decisiones.py`, `test_datos.py`,
  `test_servidor.py` y `test_datos_casos.py`). `test_humo.py` ya existe y se conserva.
- `test_servidor.py` usa el cliente en memoria del SDK (`from mcp.client import Client;
  Client(servidor)`, **medido**): lista las seis herramientas, comprueba descripciones y
  llama a cada una por el protocolo, no solo como función.
- `test_datos_casos.py` implementa el mapa caso→dato de `data-model.md`: un test llamado
  «datos del caso (x)» por cada caso (a)–(g), contra los datos reales de `datos/`. **Solo
  prueba que los datos reproducen el caso**; el caso completo, con el coordinador y los
  hooks, es del ticket #12.
- `test_servidor.py` incluye, **por el protocolo**, un campo ausente y un tipo incorrecto en
  `registrar_informe`, en `escalar_a_cumplimiento` y en una herramienta de consulta
  (`consultar_registro_mercantil`): el resultado es un error estructurado en español y no el
  texto de pydantic.
- `test_datos.py` comprueba que cada archivo es `ficticio: true`, que las URL son `.example`
  y que ningún valor tiene 6 o más dígitos seguidos. La revisión del repositorio de #3 corre
  además sobre estos archivos (`test_revision_repositorio.py`).
- La variable de resultados y la de noticias se fijan con `monkeypatch`; ningún test escribe
  en `resultados/` ni depende del orden.
