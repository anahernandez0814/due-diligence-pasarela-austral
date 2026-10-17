---

description: "Lista de tareas del ticket #5, servidor MCP de la pasarela con datos ficticios"
---

# Tasks: Servidor MCP de la pasarela con datos ficticios

**Input**: documentos de diseño en `specs/005-servidor-mcp-pasarela/`: [plan.md](plan.md),
[spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/herramientas.md](contracts/herramientas.md) y [quickstart.md](quickstart.md).

**Prerequisites**: plan.md y spec.md (obligatorios); research.md, data-model.md, contracts/
y quickstart.md.

**Tests**: obligatorios (FR-015 y constitución X). Van junto a cada módulo, en
`src/servidor_mcp/test_*.py`, y se escriben antes que el módulo (deben fallar primero).

**Organization**: una fase por historia de la spec, con dos fases previas para lo que
comparten todas:

1. Setup: fase 1. Fundamentos (`normalizar`, `respuestas`, `entradas`, `datos`): fase 2.
2. US4 datos ficticios (P2): fase 3. **Va antes que las historias P1** porque las
   herramientas leen esos archivos.
3. US1 registro mercantil: fase 4. US2 listas, noticias y riesgo: fase 5. US3 canales de
   decisión: fase 6.
4. US5 servidor conectado en Claude Code (P2): fase 7. Documentación: fase 8.
5. Validación con el quickstart: fase 9.

**Alcance de este archivo**: solo tareas que se completan **antes del merge**. La
verificación del cierre de #5 la hace el paso 0 del siguiente `/siguiente-ticket`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes).
- **[Story]**: historia de usuario de la spec (US1 a US5).
- **[MANUAL]**: la hace la analista, en una sesión nueva de Claude Code abierta en la raíz.
  Claude se detiene y espera su confirmación.
- Cada tarea cita su origen: FR-### o SC-### de la spec, R# de [research.md](research.md) o
  Q# del [quickstart](quickstart.md).
- Rutas relativas a la raíz del repositorio.

## Reglas para todas las tareas

- **Ningún valor con forma real** (tarjeta, NIT, cédula o credencial) se escribe en tareas,
  tests, datos, código ni documentación. Los identificadores de los datos son
  `CO-XX-NNNN` y `PE-NNNN`, **sin ninguna secuencia de 6 o más dígitos seguidos** (R8).
  Los valores sensibles que un test necesite se construyen en tiempo de ejecución.
- **Todo en español**: descripciones de herramientas, mensajes de error y documentación (FR-018).
- **Nada se imprime en stdout** desde el servidor: es el canal del protocolo (plan,
  restricciones).
- **API de `mcp` 2.3.0** (R1, R2): `from mcp.server.mcpserver import MCPServer`; las herramientas
  se anotan `-> CallToolResult`; los parámetros son `Annotated[Any, Field(description=...)] = None`
  y se validan dentro. **No** se usa `FastMCP` ni `mcp.server.fastmcp`.
- **Commits** por partes lógicas en la rama `005-servidor-mcp-pasarela`, nunca en `main`, y sin
  `git commit --amend`. Un commit nuevo invalida el veredicto del anterior, así que **ningún
  commit va después de la revisión** de `/abrir-pr`.
- **Formato**: el hook de #3 formatea cada `.py` escrito o editado. Cada fase de código termina
  con `uv run ruff format .` y `uv run ruff check .`.
- **Tests**: `uv run pytest src/servidor_mcp` (`pyproject.toml` ya incluye `src` en `testpaths`).
  Los tests de `decisiones` fijan `PASARELA_RESULTADOS_DIR` con `monkeypatch.setenv` y `tmp_path`;
  ninguno escribe en `resultados/`.
- `.mcp.json`, `.claude/settings.json` y `src/servidor_mcp/*.py` son código protegido (#3): solo se
  editan con spec, plan y tareas de la rama commiteados, que deja hecho T001.

---

## Fase 1: Setup

- [X] T001 Confirmar que la rama es `005-servidor-mcp-pasarela` y commitear este
  `specs/005-servidor-mcp-pasarela/tasks.md` (`docs(specs): tareas del ticket #5`), para que
  `guarda_spec_previa` deje editar el código protegido.
- [X] T002 Añadir la dependencia con `uv add "mcp>=2.3,<3"` (actualiza `pyproject.toml` y `uv.lock`,
  R1). Comprobar con `uv run python -c "from mcp.server.mcpserver import MCPServer"` y con
  `uv run pytest src/servidor_mcp/test_humo.py`. Commit: `build: dependencia mcp 2.x`.
- [X] T003 [P] Añadir `resultados/` a `.gitignore`, con el comentario
  `# Informes y casos escalados del servidor MCP (ticket #5)` (R6, FR-008, FR-009). Comprobar con
  `git check-ignore resultados/informes/prueba.json`.

---

## Fase 2: Fundamentos (bloquean todas las historias)

**Propósito**: las piezas que usan todas las herramientas. Tests primero.

- [X] T004 [P] Escribir `src/servidor_mcp/test_normalizar.py` (R3). Casos: `S.A.S.` y `SAS` dan lo
  mismo; tildes y `ñ` (`Almacén` → `almacen`); mayúsculas; espacios repetidos; apóstrofo se
  elimina; coma, guion y barra pasan a espacio; `contiene` es subcadena del texto normalizado
  (`almacen mirador` está en `almacen mirador norte sas`); `igual` compara el nombre completo
  normalizado, nunca parcial; el texto normalizado de menos de 3 caracteres se rechaza
  (`MINIMO_CARACTERES = 3`).
- [X] T005 Implementar `src/servidor_mcp/normalizar.py`: `normalizar(texto)` con los cinco pasos de R3
  (NFKD sin marcas combinadas, `casefold`, eliminar `.` y `'`, otros signos a espacio, colapsar),
  `contiene(buscado, nombre)`, `igual(a, b)` y la constante `MINIMO_CARACTERES = 3`. Pasa T004.
- [X] T006 [P] Escribir `src/servidor_mcp/test_respuestas.py` (R2, R9, FR-010, FR-011). `respuesta()`
  devuelve `CallToolResult` con `is_error=False`, `structured_content` igual al JSON del `content`,
  `hechos` y `metadatos` con `fuentes` y `fecha`; con `sin_coincidencias` los `hechos` van vacíos y
  los `metadatos` presentes. `error()` devuelve `is_error=True` con `error: true`, `tipo`,
  `mensaje`, `reintentable` y `obtenido` (por defecto `{}`); `campos_faltantes` solo si se pasa.
  El `contenido` de un hecho nunca lleva las claves `fuente` ni `fecha`, y `metadatos` nunca lleva
  contenido. **Una sola forma** (contrato): ninguna respuesta de éxito lleva `contenido` fuera de
  un hecho; `respuesta(..., coincidencias=[...])` añade `coincidencias` al nivel superior, y solo
  entonces; la `fecha` de un hecho puede ser distinta de la de `metadatos` (la de la noticia, la de
  registro). `ensure_ascii=False`: las tildes no salen como `é`.
- [X] T007 Implementar `src/servidor_mcp/respuestas.py`: `respuesta(resultado, hechos, fuentes, fecha,
  coincidencias=None)` (`coincidencias` solo en el registro mercantil), `hecho(contenido, fuente,
  fecha)` y `error(tipo, mensaje, reintentable, obtenido=None,
  campos_faltantes=None)`. Los tipos de error son los de `data-model.md`: `entrada_invalida`,
  `campos_obligatorios_ausentes`, `servicio_no_disponible`, `datos_no_disponibles`,
  `error_de_almacenamiento` y `error_interno`; `servicio_no_disponible` es el **único**
  reintentable. Pasa T006.
- [X] T008 [P] Escribir `src/servidor_mcp/test_entradas.py` (R2). Los validadores reciben un valor
  `Any` y devuelven el valor o un error en español: `texto_obligatorio` (ausente, vacío, solo
  espacios, o de tipo distinto de `str` → `entrada_invalida` con el nombre del parámetro y el tipo
  esperado), `exactamente_uno(nombre, identificador)` (los dos o ninguno → `entrada_invalida`),
  `objeto_obligatorio` y `campos_obligatorios(entrada, requeridos)` (devuelve **todos** los
  faltantes; un campo vacío cuenta como faltante; un tipo incorrecto → `entrada_invalida`).
- [X] T009 Implementar `src/servidor_mcp/entradas.py` con esos validadores, que **nunca lanzan**. Pasa T008.
- [X] T010 [P] Escribir `src/servidor_mcp/test_datos.py`, parte del cargador (R8), con archivos en
  `tmp_path`: `cargar(ruta)` devuelve el contenido; un archivo ausente, con JSON corrupto o sin
  `"ficticio": true`, `"aviso"` o `"fecha_corte"` lanza `DatosNoDisponibles`; el cargador no
  imprime nada.
- [X] T011 Implementar `src/servidor_mcp/datos.py`: la excepción `DatosNoDisponibles`, `cargar(ruta)`
  con esas validaciones y las funciones `registros()`, `listas()`, `noticias()` y `categorias()`
  que leen `src/servidor_mcp/datos/*.json` (con `Path(__file__)`, sin rutas del sistema) y
  guardan el resultado en caché por proceso. Pasa T010. Al final de la fase: `uv run ruff format .`,
  `uv run ruff check .` y commit `feat(servidor_mcp): normalización, respuestas, entradas y cargador`.

---

## Fase 3: US4 Datos ficticios que reproducen los casos (Prioridad: P2, va primero por dependencia)

**Objetivo**: los datos de `data-model.md`. **Prueba independiente**: `uv run pytest
src/servidor_mcp/test_datos.py src/servidor_mcp/test_datos_casos.py`.

- [X] T012 [P] [US4] Ampliar `src/servidor_mcp/test_datos.py` con los **datos reales** (FR-013, FR-014,
  data-model «Reglas de validación»): cada archivo de `datos/` es `ficticio: true` con `aviso` y
  `fecha_corte`; las URL terminan en `.example`; ningún valor tiene 6 o más dígitos seguidos
  (`\d{6,}`); los identificadores de comercio cumplen `^CO-[A-Z]{2}-\d{4}$` y los de persona
  `^PE-\d{4}$`; `estado` es `activo`, `suspendido` o `cancelado`; `categorias.json` tiene nivel
  `alto` **exactamente** para `apuestas`, `criptoactivos`, `suplementos dietarios` y
  `venta de medicamentos`, y diez categorías en total.
- [X] T013 [P] [US4] Crear `src/servidor_mcp/datos/registro_rmf_sur.json` y
  `src/servidor_mcp/datos/registro_rufe.json` (FR-004, FR-013, R8). Fuentes «Registro Mercantil
  Ficticio del Sur» y «Registro Único Ficticio de Empresas». Seis comercios en **las dos**
  fuentes con los mismos datos, salvo la fecha de `CO-RF-0006` (`2016-03-14` en RMF-Sur y
  `2017-09-02` en RUFE): `CO-TV-0001` Tienda Verde SAS; `CO-TA-0002` Taller Aurora SAS;
  `CO-PL-0003` Panadería Luna Nueva SAS con representante `PE-0003` (Ernesto Calderón Ibarra);
  `CO-AM-0004` Almacén Mirador SAS; `CO-AM-0005` Almacén Mirador Norte SAS; `CO-RF-0006`
  Ferretería Río Fino SAS. Cada comercio con `fecha_constitucion`, `estado` y
  `representante_legal {nombre, identificador}`. **Sin categoría de negocio** (ajuste 4).
- [X] T014 [P] [US4] Crear `src/servidor_mcp/datos/listas_restrictivas.json`: «Lista Restrictiva
  Ficticia A» y «B»; `PE-0003` como **persona** en la A; ni `CO-PL-0003` ni `CO-TV-0001` ni
  `CO-TA-0002` en ninguna lista (caso c, a y b).
- [X] T015 [P] [US4] Crear `src/servidor_mcp/datos/noticias.json`: fuente «Diario Ficticio del Sur»,
  noticias con `id`, `titular`, `fecha`, `url` en `.example` y `menciona[]`. Una menciona a
  `CO-AM-0005` y **ninguna** menciona a `CO-TV-0001` ni a `CO-TA-0002`.
- [X] T016 [P] [US4] Crear `src/servidor_mcp/datos/categorias.json` con las diez categorías de
  `data-model.md`: `alto` (apuestas, criptoactivos, suplementos dietarios, venta de
  medicamentos), `medio` (viajes y turismo, electrodomésticos) y `bajo` (ropa y accesorios,
  restaurantes y alimentos preparados, tecnología y software, educación en línea).
- [X] T017 [US4] Escribir `src/servidor_mcp/test_datos_casos.py`: un test **«datos del caso (x)»**
  por cada caso (a)–(g) según el mapa de `data-model.md`. **Solo prueba que los datos reproducen
  el caso**; los casos completos son del #12.
  (a) `CO-TV-0001` en el registro, sin entradas en listas ni noticias, y «suplementos dietarios»
  `alto`; (b) `CO-TA-0002` limpio y «ropa y accesorios» `bajo`; (c) el representante de
  `CO-PL-0003` es `PE-0003` y figura como persona en listas, y el comercio no; (d) `almacen
  mirador` está contenido en los nombres de `CO-AM-0004` y `CO-AM-0005`; (e) sin datos nuevos:
  el nombre de (d) es ambiguo, comprobado **solo con `datos.py` y `normalizar.contiene`**
  (más de un comercio del registro lo contiene), **sin llamar a `consultar_registro_mercantil`**,
  que no existe hasta T020; (f) sin
  datos nuevos: existe al menos un comercio al que aplicar la variable; (g) `CO-RF-0006` tiene
  dos fechas distintas, cada una en su fuente. Pasa con T013 a T016.
- [X] T018 [US4] `uv run ruff format .`, `uv run ruff check .`, `uv run pytest src/servidor_mcp` y
  `uv run pytest .claude/hooks/test_revision_repositorio.py`. **Antes de ejecutar esa revisión,
  `git add src/servidor_mcp/datos/`**: recorre `git ls-files` y, con los JSON sin versionar, pasaría
  sin leerlos (SC-006). Después, commit `feat(servidor_mcp): datos ficticios de los casos`.

**Punto de control**: los datos reproducen los siete casos y pasan la revisión del repositorio.

---

## Fase 4: US1 Registro mercantil (Prioridad: P1)

**Objetivo**: identificar un comercio sin elegir entre coincidencias. **Prueba independiente**:
`uv run pytest src/servidor_mcp/test_registro.py`.

- [ ] T019 [P] [US1] Escribir `src/servidor_mcp/test_registro.py` (FR-003, FR-004, FR-010, R3, R9):
  por identificador `CO-TV-0001` devuelve `coincidencias: ["CO-TV-0001"]`, con un hecho por fuente
  y `metadatos` con fuente y `fecha_corte`; `almacen mirador` devuelve `coincidencias:
  ["CO-AM-0004", "CO-AM-0005"]` (**2 coincidencias y 4 hechos**, uno por comercio y fuente; las
  coincidencias se cuentan en `coincidencias`, no en `hechos`), sin campo `elegida` ni nada que
  sugiera preferencia, en orden de identificador; `S.A.S.` equivale a `SAS`;
  `CO-RF-0006` devuelve **dos hechos** con `fecha_constitucion` `2016-03-14` y `2017-09-02`, cada
  uno con su fuente; un nombre inexistente devuelve `sin_coincidencias`, con `coincidencias` vacía
  y `metadatos` presentes, y **no** es un error; **un identificador desconocido y corto (por
  ejemplo `X1`) también da `sin_coincidencias`**, porque el mínimo de 3 caracteres es solo para el
  nombre; `nombre` e `identificador` a la vez, ninguno, vacío, un **nombre** de menos de 3
  caracteres normalizados o un tipo incorrecto devuelven `entrada_invalida` no reintentable; un
  archivo de datos ausente devuelve `datos_no_disponibles`.
- [ ] T020 [US1] Implementar `src/servidor_mcp/registro.py` con `consultar_registro_mercantil(nombre,
  identificador)`: valida con `entradas.py`, busca con `normalizar.py` (contención por nombre,
  igualdad por identificador, sin mínimo para el identificador), devuelve un hecho por comercio y
  fuente con la fuente y su `fecha_corte` en los metadatos, y `coincidencias` con los
  identificadores distintos, en orden. Nunca lanza. Pasa T019.

**Punto de control**: US1 funciona por sí sola.

---

## Fase 5: US2 Listas, noticias y riesgo de categoría (Prioridad: P1)

**Objetivo**: los tres frentes independientes. **Prueba independiente**: `uv run pytest
src/servidor_mcp/test_listas.py src/servidor_mcp/test_noticias.py src/servidor_mcp/test_riesgo.py`.

- [ ] T021 [P] [US2] Escribir `src/servidor_mcp/test_listas.py` (FR-005, R3): `PE-0003` como `persona`
  coincide por identificador, y el nombre completo en otras mayúsculas y sin tildes también;
  un nombre **parcial** no coincide; el mismo nombre con `tipo` `comercio` no coincide;
  `CO-TV-0001` y `CO-TA-0002` dan `sin_coincidencias` con `metadatos`; `tipo` ausente, distinto de
  `comercio` o `persona`, o ambos o ninguno de nombre e identificador, dan `entrada_invalida`.
- [ ] T022 [US2] Implementar `src/servidor_mcp/listas.py` con `consultar_listas_restrictivas(tipo,
  nombre, identificador)`: un hecho por lista que coincide, con el nombre de la lista y su
  fuente. Pasa T021.
- [ ] T023 [P] [US2] Escribir `src/servidor_mcp/test_noticias.py` (FR-006, FR-012, R5): `CO-AM-0005`
  devuelve la noticia con titular, url y fuente, y **la `fecha` del hecho es la de la noticia**
  mientras `metadatos.fecha` es la `fecha_corte` del corpus; una persona o comercio sin menciones
  da `sin_coincidencias` con `metadatos`; **`CO-AM-0005` aparece en noticias y no en listas** (US2,
  escenario 3); con `monkeypatch.setenv("PASARELA_FALLA_NOTICIAS", "1")` devuelve
  `servicio_no_disponible` con `reintentable: true` y `obtenido` vacío; con `"0"` o cualquier
  valor distinto de `"1"` funciona; **en la misma instancia**, activar y desactivar la variable
  entre dos llamadas cambia el resultado (R5: se lee en cada llamada).
- [ ] T024 [US2] Implementar `src/servidor_mcp/noticias.py` con `buscar_noticias(nombre,
  identificador)`, leyendo `os.environ.get("PASARELA_FALLA_NOTICIAS") == "1"` **dentro de la
  función**, nunca al importar. Pasa T023.
- [ ] T025 [P] [US2] Escribir `src/servidor_mcp/test_riesgo.py` (FR-007, R4): nivel `alto`
  **exactamente** para las cuatro categorías del enunciado y ninguna otra conocida es `alto`;
  la comparación es normalizada (`Suplementos Dietarios`, `suplementos  dietarios`); una
  categoría desconocida devuelve `categoria_desconocida` con **un hecho** cuyo `contenido` es
  `{categoria, categorias_conocidas}`, **sin `nivel`**, con la fuente y la `fecha_corte` de
  `categorias.json`; una conocida devuelve un hecho con `{categoria, nivel}`; vacía o de tipo
  incorrecto da `entrada_invalida`; toda respuesta lleva `metadatos`.
- [ ] T026 [US2] Implementar `src/servidor_mcp/riesgo.py` con `consultar_riesgo_categoria(categoria)` y
  `categorias_conocidas()`, que la descripción de la herramienta usará. Pasa T025. Al final de la
  fase: `uv run ruff format .`, `uv run ruff check .` y commit
  `feat(servidor_mcp): consultas de registro, listas, noticias y riesgo`.

**Punto de control**: US1 y US2 funcionan por separado.

---

## Fase 6: US3 Registrar el informe y escalar a cumplimiento (Prioridad: P1)

**Objetivo**: los dos canales de decisión. **Prueba independiente**: `uv run pytest
src/servidor_mcp/test_decisiones.py`.

- [ ] T027 [P] [US3] Escribir `src/servidor_mcp/test_decisiones.py` (FR-008, FR-009, R6, R11), con
  `PASARELA_RESULTADOS_DIR` apuntando a `tmp_path`: `registrar_informe` completo guarda
  `informes/INF-<8 hex>.json` y devuelve `informe_registrado` con **un hecho cuyo `contenido` es
  `{id}`** y metadatos con la fuente «Registro local de informes (ficticio)» y la fecha de
  registro; `escalar_a_cumplimiento` completo guarda `escalamientos/ESC-<8 hex>.json` y devuelve
  `caso_escalado` con un hecho `{id}` y la fuente «Registro local de escalamientos (ficticio)»; en
  ambos, ningún `contenido` fuera del hecho; dos informes del
  mismo comercio se conservan con ids distintos; a `registrar_informe` le faltan `comercio`,
  `recomendacion`, `hallazgos` o `cobertura`, y a `escalar_a_cumplimiento` los **cinco** campos
  (`comercio`, `hallazgos`, `cobertura`, `causa_escalamiento`, `accion_recomendada`): error
  `campos_obligatorios_ausentes`, **no reintentable**, con **todos** los `campos_faltantes`; un
  campo presente pero vacío cuenta como faltante; un hallazgo sin `fuente` es faltante; un tipo
  incorrecto (un número donde va un objeto) da `entrada_invalida`; la carpeta se crea si no existe;
  si no se puede escribir (un archivo ocupa el lugar de la carpeta) da `error_de_almacenamiento`;
  sin la variable definida la ruta por defecto es `resultados/` en la raíz, comprobada **sin
  escribir** (solo la ruta calculada); no queda ningún archivo temporal.
- [ ] T028 [US3] Implementar `src/servidor_mcp/decisiones.py` con `registrar_informe(...)` y
  `escalar_a_cumplimiento(...)`: validación con `entradas.py`, carpeta desde
  `PASARELA_RESULTADOS_DIR` (por defecto `resultados/` a partir de `Path(__file__)`, R6), expuesta
  por la función `carpeta_resultados()`, que usa T027 para comprobar la ruta por defecto sin
  escribir; hecho con `contenido` `{id}` y las fuentes de registro del contrato; id con
  `uuid4().hex[:8]`, escritura atómica (archivo temporal y `os.replace`). **No valida reglas de
  negocio** (R11). Pasa T027. Al final: `uv run ruff format .`, `uv run ruff check .` y commit
  `feat(servidor_mcp): registrar informe y escalar a cumplimiento`.

**Punto de control**: las seis funciones existen y se prueban sin servidor.

---

## Fase 7: US5 Servidor disponible en Claude Code (Prioridad: P2)

**Objetivo**: el servidor por protocolo y conectado junto al de GitHub. **Prueba independiente**:
`uv run pytest src/servidor_mcp/test_servidor.py` y Q6.

- [ ] T029 [P] [US5] Escribir `src/servidor_mcp/test_servidor.py` con el **cliente en memoria** del SDK
  (`from mcp.client import Client`, R12). Lista **exactamente** las seis herramientas; cada
  descripción contiene las frases de R10 (una mención en noticias no es una coincidencia en
  listas restrictivas; varias coincidencias no autorizan a elegir una; `registrar_informe` y
  `escalar_a_cumplimiento` son canales de decisión); la de `consultar_riesgo_categoria` lista las
  categorías conocidas; todos los parámetros son opcionales y llevan `description` con el tipo
  esperado; cada herramienta responde **por el protocolo**. **Por el protocolo** (R2): un campo
  ausente y un tipo incorrecto en `registrar_informe`, en `escalar_a_cumplimiento` y en
  `consultar_registro_mercantil` devuelven un error estructurado en español
  (`campos_obligatorios_ausentes` con `campos_faltantes`, o `entrada_invalida`), con
  `is_error=True` y `structured_content`, y el texto **no** contiene `Field required` ni
  `validation error`. Ninguna herramienta lanza una excepción hacia el cliente. **Caso de
  excepción interna**: con `monkeypatch` se hace que la función de una herramienta (por ejemplo
  `registro.consultar_registro_mercantil`) lance una excepción inesperada; por el protocolo, el
  resultado es `error_interno`, `is_error=True`, `reintentable: false`, con el mensaje en español
  y sin el texto de la excepción ni su traza. **Con `PASARELA_FALLA_NOTICIAS=1`** (FR-012,
  `monkeypatch.setenv`), `buscar_noticias` devuelve `servicio_no_disponible` y las **otras cinco**
  herramientas responden con normalidad por el protocolo. **Español** (FR-018): las descripciones
  y los mensajes de error de las seis herramientas están en español (sin las palabras
  `required`, `invalid` ni `error executing`).
- [ ] T030 [US5] Implementar `src/servidor_mcp/servidor.py` (`MCPServer("pasarela")`, las seis herramientas
  con `@servidor.tool()`, `-> CallToolResult`, parámetros `Annotated[Any, Field(description=...)] =
  None`, `try/except` que convierte lo inesperado en `error_interno` no reintentable, y las
  descripciones del contrato). **`servidor.py` llama a las funciones por módulo**
  (`import registro` y `registro.consultar_registro_mercantil(...)`, igual con `listas`,
  `noticias`, `riesgo` y `decisiones`), nunca con `from .registro import f`, para que el
  `monkeypatch` de T029 actúe. Y `src/servidor_mcp/__main__.py` (`servidor.run()`, stdio). Nada se
  imprime en stdout. Pasa T029.
- [ ] T031 [P] [US5] Crear `src/servidor_mcp/CLAUDE.md` con las convenciones del servidor (FR-015):
  `MCPServer` y no `FastMCP`, errores estructurados con `CallToolResult`, parámetros opcionales,
  nada en stdout, datos solo ficticios, variables `PASARELA_*`, tests junto al código.
- [ ] T032 [P] [US5] Añadir a `.claude/hooks/test_configuracion.py` la comprobación de que
  `enabledMcpjsonServers` contiene `github` y `pasarela`, de que `.mcp.json` tiene el bloque
  `pasarela` de tipo `stdio` con `command: uv`, y de que ese bloque **no** contiene `${`, `env` ni
  nada con forma de credencial (R7, FR-016). Debe fallar antes de T033 y T034.
- [ ] T033 [US5] Añadir a `.mcp.json` el bloque `pasarela` con la **primera opción de R7**:
  `{"type": "stdio", "command": "uv", "args": ["run", "--quiet", "python", "-m", "servidor_mcp"]}`,
  sin variables ni `env`.
- [ ] T034 [US5] Añadir `"pasarela"` a `enabledMcpjsonServers` de `.claude/settings.json`, que queda
  `["github", "pasarela"]` (R7, SC-007). Pasa T032. Al final: `uv run ruff format .`,
  `uv run ruff check .`, `uv run pytest` y commit `feat(servidor_mcp): servidor MCP y registro en Claude Code`.

---

## Fase 8: Documentación

- [ ] T035 [P] Añadir al `README.md` una sección breve «Servidor MCP de la pasarela»: las seis
  herramientas, `uv sync` antes de abrir Claude Code, abrir siempre en la raíz, las variables
  `PASARELA_FALLA_NOTICIAS` y `PASARELA_RESULTADOS_DIR`, y que los datos son ficticios.
- [ ] T036 Añadir a `DECISIONES.md` la **entrada 6, de 4 líneas como máximo** (el archivo está en el
  límite de dos páginas): `mcp` 2.x con `MCPServer`; errores como `CallToolResult` con parámetros
  opcionales validados dentro; datos ficticios con fecha de corte; riesgos residuales (caída de
  noticias al lanzar, raíz de `resultados/`, comando de `.mcp.json`). Detalle en
  `specs/005-servidor-mcp-pasarela/research.md`. Contar las líneas de la entrada antes de cerrar.
- [ ] T037 `uv run ruff format .`, `uv run ruff check .`, `uv run pytest`. Commit
  `docs: servidor MCP de la pasarela en el README y en DECISIONES.md`.

---

## Fase 9: Validación con el quickstart

- [ ] T038 Ejecutar Q1, Q2, Q3, Q4 y Q8 del [quickstart](quickstart.md) y anotar el resultado de cada
  uno debajo de esta tarea. **Q8.2** se prueba pasando a la guarda por stdin un `Write` con una
  tarjeta generada en ejecución, como en #3 (`tarjeta` de `test_detector_datos.py`), con el script
  fuera del repositorio y sin escribir el valor en ningún archivo. Si alguno falla, corregir con un commit nuevo y repetirlo.
- [ ] T039 Ejecutar Q5 y Q7 con un script desechable **fuera del repositorio** (carpeta de
  scratchpad): `registrar_informe` con la ruta por defecto, `git check-ignore`, borrar
  `resultados/` y comprobar que no queda nada en `.claude/`; y el servidor lanzado por stdio con
  `PASARELA_FALLA_NOTICIAS=1`, con el mismo error de noticias y las otras cuatro herramientas
  respondiendo. Anotar el resultado.
- [ ] T040 [MANUAL] **Q6 en una sesión nueva** abierta en la raíz del repositorio: `/mcp` muestra
  `github` y `pasarela` conectados **sin pedir aprobación** y las seis herramientas
  `mcp__pasarela__*`; llamar a `consultar_registro_mercantil` con «almacén mirador» y comprobar
  que devuelve dos coincidencias sin elegir. **Si `pasarela` no conecta**, anotar el error de
  `/mcp`, pasar a la segunda opción de R7 (`--directory ${CLAUDE_PROJECT_DIR}`, comprobando en otra
  sesión nueva que se expande) y registrar cuál funcionó en `DECISIONES.md` (la entrada 6 no pasa
  de 4 líneas). **En ese caso, ajustar también la comprobación de T032 en
  `.claude/hooks/test_configuracion.py`**, que hoy exige que el bloque `pasarela` no contenga
  `${`: debe admitir únicamente `${CLAUDE_PROJECT_DIR}` en `args` y seguir rechazando `env` y
  cualquier otra variable o credencial. Claude espera la confirmación de la analista.
- [ ] T041 Anotar en esta lista los resultados de T038 a T040 y commitear
  `docs(specs): resultados de la validación del ticket #5`. Después, `/abrir-pr`. **Ningún commit
  va después de la revisión.**

---

## Dependencias y orden de ejecución

- **Fase 1** no tiene dependencias. T001 va primero: sin él, la guarda bloquea el código protegido.
- **Fase 2** depende de la fase 1 y **bloquea** todas las historias. Dentro: T004→T005, T006→T007,
  T008→T009 y T010→T011; los tres pares de pruebas (T004, T006, T008, T010) son paralelos.
- **Fase 3 (US4)** depende de la fase 2 (T011 para T017). T012 a T016 son paralelos entre sí.
- **Fase 4 (US1)** y **fase 5 (US2)** dependen de las fases 2 y 3; son independientes entre sí.
- **Fase 6 (US3)** depende de la fase 2; no necesita los datos de la fase 3.
- **Fase 7 (US5)** depende de las fases 4 a 6 (T030 registra las seis herramientas).
- **Fase 8** depende de la fase 7. **Fase 9** depende de todo.
- Cada par «test → módulo» respeta el orden: el test se escribe y **falla** antes de implementar.

### Oportunidades de paralelismo

- Fase 2: T004, T006, T008 y T010 a la vez.
- Fase 3: T012 a T016 a la vez.
- Fases 4, 5 y 6: sus tests (T019, T021, T023, T025, T027) a la vez.
- Fase 7: T029, T031 y T032 a la vez.

## Estrategia de implementación

- **MVP**: fases 1 a 4 (US1). Con el registro, un nombre ambiguo ya devuelve todas las
  coincidencias y las dos fuentes contradictorias, que es lo que más depende de este servidor.
- **Entrega incremental**: fase 5 (los tres frentes), fase 6 (canales de decisión), fase 7
  (protocolo y conexión), fases 8 y 9.
- **Alcance**: solo lo que pide el ticket. Sin agentes ni hooks del SDK (#6 y #7), sin validar reglas
  de negocio de orden y sin los casos completos (#12).
