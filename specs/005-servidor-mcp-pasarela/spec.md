# Feature Specification: Servidor MCP de la pasarela con datos ficticios

**Feature Branch**: `005-servidor-mcp-pasarela`

**Created**: 2026-10-17

**Status**: Draft

**Input**: Issue #5 de GitHub: "Servidor MCP de la pasarela con datos ficticios". Simular las fuentes de la pasarela (registro mercantil, listas restrictivas, noticias y riesgo por categoría) y los canales de decisión (registro del informe y escalamiento) en un servidor MCP propio, con datos ficticios locales.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Identificar un comercio en el registro mercantil (Priority: P1)

El analista (o el agente que trabaja para él) busca un comercio por nombre o identificador y recibe lo que el registro sabe de él: existencia, fecha de constitución, representante legal y estado. Si el nombre es ambiguo, recibe **todas** las coincidencias para decidir con el identificador; la herramienta nunca elige una. El registro consolida dos fuentes registrales ficticias; cuando difieren (por ejemplo, en la fecha de constitución), la respuesta incluye ambos valores, cada uno con su fuente.

**Why this priority**: sin identificación unívoca no se puede consultar ninguna lista restrictiva (principio I.1) y las contradicciones entre fuentes deben mostrarse, no resolverse (I.4). Es la base de todo el due diligence.

**Independent Test**: se consulta `CO-TV-0001`, un nombre ambiguo y el comercio con fechas distintas, y se comprueba que devuelven una coincidencia, varias coincidencias y dos fechas con su fuente, respectivamente.

**Acceptance Scenarios**:

1. **Given** el comercio del ejemplo (Tienda Verde SAS, `CO-TV-0001`), **When** se consulta por su identificador, **Then** devuelve una única coincidencia con fecha de constitución, representante legal y estado, y con la fuente y la fecha de consulta separadas del contenido.
2. **Given** dos comercios con nombres casi idénticos, **When** se busca un texto que, normalizado, está contenido en el nombre normalizado de ambos, **Then** devuelve ambas coincidencias, cada una con su identificador, y ninguna marcada como elegida.
3. **Given** un comercio cuyas dos fuentes registrales difieren en la fecha de constitución, **When** se consulta, **Then** la respuesta incluye ambas fechas, cada una atribuida a su fuente, sin escoger una.
4. **Given** un nombre o identificador que no existe, **When** se consulta, **Then** la respuesta indica de forma explícita que no hay coincidencias (no es un error del servicio).

---

### User Story 2 - Verificar listas restrictivas, noticias y riesgo de categoría (Priority: P1)

Con el comercio ya identificado, el analista consulta tres frentes independientes: coincidencias en listas restrictivas ficticias (de un comercio o de una persona, como el representante legal), menciones en un corpus de noticias ficticias y el nivel de riesgo de la categoría de negocio. Las descripciones de las herramientas dejan claro que una mención en noticias no es una coincidencia en listas restrictivas.

**Why this priority**: son los hallazgos sobre los que se decide la habilitación o el escalamiento (I.2, I.3); los casos de prueba (a), (b), (c) y (f) dependen de ellos.

**Independent Test**: se consulta un representante legal presente en las listas, un comercio sin hallazgos, una categoría de alto riesgo y una de riesgo no alto, y se comprueba cada respuesta.

**Acceptance Scenarios**:

1. **Given** un representante legal que figura en las listas ficticias, **When** se consulta como persona, **Then** la respuesta informa la coincidencia con la lista y su fuente.
2. **Given** un comercio de bajo riesgo sin hallazgos, **When** se consultan listas y noticias, **Then** ambas respuestas indican de forma explícita que no hay coincidencias ni menciones.
3. **Given** una persona o comercio con una mención en noticias pero sin coincidencia en listas, **When** se consultan ambos frentes, **Then** cada herramienta responde solo de su frente y la mención no aparece como coincidencia en listas.
4. **Given** cada una de las cuatro categorías de alto riesgo (apuestas, criptoactivos, suplementos dietarios, venta de medicamentos), **When** se consulta su riesgo, **Then** el nivel es alto; **Given** cualquier otra categoría conocida, **Then** el nivel no es alto.
5. **Given** una categoría desconocida, **When** se consulta, **Then** la respuesta es una respuesta definida que declara que la categoría no se reconoce, sin asignarle un nivel por defecto.
6. **Given** que el servicio de noticias está simulado como caído, **When** se buscan noticias, **Then** se devuelve un error estructurado que indica si se puede reintentar, y las demás herramientas siguen funcionando.

---

### User Story 3 - Registrar el informe y escalar a cumplimiento (Priority: P1)

Las decisiones solo salen por dos canales: registrar el informe de due diligence con su recomendación y escalar el caso a un oficial de cumplimiento con un resumen estructurado. Ambos guardan su resultado en una carpeta local que git no versiona.

**Why this priority**: la constitución (IV) exige que las decisiones solo se emitan por estas dos herramientas, para poder protegerlas y auditarlas.

**Independent Test**: se registra un informe y se escala un caso, y se comprueba que cada uno queda guardado localmente, es recuperable y no entra en git.

**Acceptance Scenarios**:

1. **Given** un informe con su recomendación y sus fuentes, **When** se registra, **Then** queda guardado y la respuesta confirma su registro con un identificador.
2. **Given** un caso a escalar con un resumen estructurado, **When** se escala, **Then** queda guardado como caso escalado y la respuesta lo confirma.
3. **Given** datos incompletos en el informe o el escalamiento, **When** se envían, **Then** se devuelve un error estructurado que indica qué falta y que no es reintentable sin corregirlo.

---

### User Story 4 - Datos ficticios que reproducen los casos de prueba (Priority: P2)

Los archivos de datos locales contienen lo necesario para reproducir los siete casos obligatorios: Tienda Verde SAS (`CO-TV-0001`, suplementos dietarios), un comercio de bajo riesgo sin hallazgos, un representante legal en listas, dos comercios de nombres casi idénticos y un comercio con fechas de constitución distintas. Todo es evidentemente ficticio y cada archivo de datos lo declara.

**Why this priority**: los tickets siguientes (#6 a #12) consumen estos datos, pero se puede probar el servidor con un subconjunto; por eso va después de las herramientas.

**Independent Test**: se revisan los archivos de datos y se comprueba que cada caso (a)–(g) tiene datos que lo reproducen y que ninguno tiene forma de documento, NIT o tarjeta reales ni nombra entidades reales.

**Acceptance Scenarios**:

1. **Given** los archivos de datos, **When** se revisan, **Then** cada uno está marcado como ficticio y usa nombres inventados y dominios `.example`.
2. **Given** los siete casos de prueba, **When** se buscan sus datos, **Then** existe al menos un comercio o persona que reproduce cada uno.
3. **Given** las guardas de datos de #3, **When** se revisa el repositorio, **Then** no encuentran ningún dato con forma real.

---

### User Story 5 - Servidor disponible en Claude Code (Priority: P2)

El servidor queda registrado en la configuración compartida del proyecto, junto al de GitHub y sin credenciales, de modo que en una sesión de Claude Code aparezca conectado y sus herramientas estén disponibles durante el desarrollo.

**Why this priority**: permite probar a mano las herramientas, pero no es parte del comportamiento de negocio.

**Independent Test**: se abre una sesión nueva en la raíz del repositorio y se comprueba que el servidor de la pasarela figura conectado junto al de GitHub.

**Acceptance Scenarios**:

1. **Given** una sesión nueva en la raíz del repositorio, **When** se listan los servidores MCP, **Then** el de la pasarela y el de GitHub aparecen conectados.
2. **Given** la configuración versionada, **When** se revisa, **Then** no contiene ninguna credencial.

---

### Edge Cases

- Búsqueda con texto vacío o solo con espacios: error estructurado no reintentable que pide un nombre o identificador.
- Nombres que difieren solo en mayúsculas, tildes, espacios repetidos o puntuación (por ejemplo, «S.A.S.» y «SAS»): se tratan como el mismo nombre al normalizar.
- Identificador con formato desconocido: respuesta de "sin coincidencias", no un error del servicio.
- Persona o comercio consultado en listas con un nombre parcialmente parecido a una entrada de la lista: no se declara coincidencia por parecido; solo por coincidencia del nombre completo normalizado o del identificador.
- Una herramienta recibe un tipo de entidad que no admite (por ejemplo, una persona en una herramienta solo de comercios): error estructurado no reintentable.
- Archivo de datos ausente o corrupto: error estructurado del servidor, indicado como no reintentable, sin respuestas parciales presentadas como completas.
- Carpeta de resultados inexistente al registrar un informe: se crea; si no se puede escribir, error estructurado.
- Dos informes para el mismo comercio: ambos se conservan, cada uno con su identificador.
- `PASARELA_FALLA_NOTICIAS` con cualquier valor distinto de `1`: el servicio de noticias funciona con normalidad.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El servidor MUST exponer exactamente seis herramientas: `consultar_registro_mercantil`, `consultar_listas_restrictivas`, `buscar_noticias`, `consultar_riesgo_categoria`, `registrar_informe` y `escalar_a_cumplimiento`.
- **FR-002**: Cada herramienta MUST tener una descripción que diga qué hace y qué no hace. Como mínimo: una mención en `buscar_noticias` no es una coincidencia en `consultar_listas_restrictivas`; ante varias coincidencias en el registro no se debe elegir una; `registrar_informe` y `escalar_a_cumplimiento` son los únicos canales de decisión.
- **FR-003**: `consultar_registro_mercantil` MUST buscar por nombre o por identificador y devolver, por cada coincidencia, existencia, fecha de constitución, representante legal y estado; con un nombre ambiguo MUST devolver todas las coincidencias, sin marcar ninguna como elegida.
- **FR-004**: El registro mercantil MUST consolidar dos fuentes registrales ficticias. Si difieren en algún dato, la respuesta MUST incluir ambos valores, cada uno con su fuente, y no elegir uno.
- **FR-005**: `consultar_listas_restrictivas` MUST aceptar un comercio o una persona (por ejemplo, el representante legal) y devolver las coincidencias con la lista y su fuente, o declarar de forma explícita que no hay.
- **FR-006**: `buscar_noticias` MUST buscar menciones de un comercio o una persona en un corpus ficticio y devolverlas con su fuente y fecha, o declarar de forma explícita que no hay.
- **FR-007**: `consultar_riesgo_categoria` MUST devolver nivel alto exactamente para apuestas, criptoactivos, suplementos dietarios y venta de medicamentos, y un nivel no alto para las demás categorías conocidas. La categoría se compara normalizada, y la descripción de la herramienta MUST listar las categorías conocidas. Para una categoría desconocida MUST devolver una respuesta definida que declare que no se reconoce, sin inventar un nivel.
- **FR-008**: `registrar_informe` MUST exigir comercio, recomendación, hallazgos por frente con su fuente y cobertura alcanzada; guardar el informe en una carpeta local excluida de git y confirmarlo con un identificador. Si falta alguno de esos campos, MUST devolver un error no reintentable que lo nombra.
- **FR-009**: `escalar_a_cumplimiento` MUST exigir los cinco campos del resumen al oficial: comercio, hallazgos por frente con fuentes, cobertura alcanzada, causa del escalamiento y acción recomendada; guardar el caso en una carpeta local excluida de git y confirmarlo con un identificador. Si falta alguno, MUST devolver un error no reintentable que lo nombra.
- **FR-010**: Toda respuesta de consulta, incluidas las que no tienen coincidencias, MUST separar el contenido de los metadatos (fuente y fecha).
- **FR-011**: Todo error MUST ser estructurado e indicar si se puede reintentar, y MUST distinguir un error del servicio de una búsqueda sin resultados.
- **FR-012**: Con `PASARELA_FALLA_NOTICIAS=1`, `buscar_noticias` MUST devolver un error estructurado reintentable, sin afectar a las otras herramientas.
- **FR-013**: Los datos MUST vivir en archivos locales, cada uno marcado como ficticio, y MUST permitir reproducir los siete casos de prueba obligatorios, incluido Tienda Verde SAS (`CO-TV-0001`, suplementos dietarios).
- **FR-014**: Ningún dato MUST tener forma de documento de identidad, NIT o tarjeta reales, ni nombrar entidades, personas, noticias o listas reales; los nombres son inventados y los dominios `.example`.
- **FR-015**: El código del servidor MUST vivir en `src/servidor_mcp/`, con tests por herramienta junto al código y un `CLAUDE.md` en ese subdirectorio con sus convenciones.
- **FR-016**: El servidor MUST registrarse en `.mcp.json` junto al de GitHub y sin credenciales, y aparecer conectado en una sesión de Claude Code.
- **FR-017**: El servidor MUST NOT incluir agentes ni hooks del SDK (tickets #6 y #7), ni aplicar reglas de negocio de orden (como bloquear listas sin identificación): esa garantía es de los hooks del SDK.
- **FR-018**: Las descripciones, mensajes de error y documentación MUST estar en español.

### Key Entities *(include if feature involves data)*

- **Comercio**: entidad de la pasarela con identificador, nombre, y un registro en cada una de las dos fuentes registrales (fecha de constitución, representante legal, estado).
- **Persona**: individuo ficticio (por ejemplo, un representante legal) con nombre y, opcionalmente, un identificador ficticio.
- **Fuente registral**: origen de un dato del registro; cada dato lleva la fuente de la que procede.
- **Entrada de lista restrictiva**: comercio o persona que figura en una lista ficticia, con el nombre de la lista y su fecha.
- **Noticia**: mención ficticia con titular, fecha, fuente y las entidades que menciona.
- **Categoría de negocio**: nombre y nivel de riesgo (alto o no alto).
- **Informe**: resultado del due diligence de un comercio, con su recomendación, hallazgos por frente con fuentes y cobertura alcanzada.
- **Caso escalado**: caso enviado a un oficial de cumplimiento con un resumen estructurado y su causa.
- **Error estructurado**: tipo de fallo, mensaje en español, indicador de si es reintentable y lo que se alcanzó a obtener (puede ir vacío).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Las seis herramientas responden según su propósito en el 100 % de los casos de prueba definidos, y cada una tiene al menos un test.
- **SC-002**: Los siete casos de prueba obligatorios (a)–(g) se pueden reproducir con los datos, sin añadir datos a mano.
- **SC-003**: El 100 % de las respuestas de consulta separa el contenido de los metadatos (fuente y fecha).
- **SC-004**: Un nombre ambiguo devuelve el 100 % de las coincidencias del registro; ninguna respuesta marca una como elegida.
- **SC-005**: El 100 % de los errores indica si es reintentable, y la caída simulada de noticias siempre se declara como tal.
- **SC-006**: La revisión de datos con forma real sobre el repositorio no encuentra ningún hallazgo en los archivos del servidor.
- **SC-007**: En una sesión nueva de Claude Code, el servidor de la pasarela aparece conectado junto al de GitHub, sin pedir credenciales.

## Assumptions

- El destinatario directo de las herramientas son los agentes del ticket #6; el analista las ve a través de ellos.
- Las herramientas simulan las fuentes: no hacen validaciones de negocio de orden ni escalan por sí solas; las reglas I.1 e I.2 las garantizan los hooks del ticket #7.
- La normalización de nombres ignora mayúsculas, tildes, espacios repetidos y puntuación (S.A.S. = SAS). En `consultar_registro_mercantil`, un nombre coincide si el texto buscado normalizado está contenido en el nombre normalizado del comercio, y se devuelven todas las coincidencias. En `consultar_listas_restrictivas` solo hay coincidencia por nombre completo normalizado o por identificador, nunca parcial.
- La categoría de negocio la aporta el analista en su solicitud; el registro mercantil no la devuelve. Por eso la consulta de riesgo recibe la categoría como entrada y el comercio no la lleva como dato del registro.
- "Nivel no alto" puede tener valores propios (por ejemplo, bajo y medio) siempre que ninguno sea alto; los valores exactos los fija el plan.
- Las categorías conocidas distintas de las cuatro de alto riesgo incluyen al menos dos (por ejemplo, de bajo y de medio riesgo).
- Los informes y casos escalados se guardan en una carpeta local que git no versiona; su ubicación y formato los fija el plan.
- Depende del ticket #1 (entorno base, `.mcp.json`) y de las guardas del #3, cuya regla `herramientas-mcp` apunta a `src/servidor_mcp/`.
