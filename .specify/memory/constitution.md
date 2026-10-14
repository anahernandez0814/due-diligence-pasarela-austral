<!--
Sync Impact Report
- Cambio de versión: 1.0.0 → 1.0.1 (PATCH: aclaración)
- Cambios en 1.0.1:
  - "Flujo de desarrollo y puertas de calidad", paso 5: cada pull request mantiene en verde
    los tests existentes; los casos (a)–(g) deben pasar en la entrega final y en el ticket
    de la suite de pruebas (antes se exigían en cada pull request).
  - Títulos renombrados: "Core Principles" → "Principios"; "Governance" → "Gobierno".
- Historial 1.0.0 (plantilla sin versión → 1.0.0): plantilla de 5 marcadores reemplazada
  por 10 principios:
  I. Reglas de negocio no negociables
  II. Garantizado vs. sugerido
  III. Arquitectura de agentes
  IV. Herramientas y servidor MCP
  V. Escalamiento con criterio
  VI. Transparencia en la interfaz
  VII. Solo datos ficticios
  VIII. Sin credenciales en el repositorio
  IX. Spec first y trazabilidad
  X. Calidad y pruebas
- Secciones añadidas: Restricciones técnicas; Flujo de desarrollo y puertas de calidad
- Secciones eliminadas: ninguna
- Plantillas: no se modifican (leen la constitución en tiempo de ejecución)
- TODOs diferidos: ninguno
-->

# Constitución de Due Diligence Pasarela Austral

Sistema multi-agente en Python con el Claude Agent SDK para el due diligence de comercios
de la pasarela de pagos ficticia Pasarela Austral. El usuario es un analista interno de la
pasarela, no el comercio.

## Principios

### I. Reglas de negocio no negociables

1. NO DEBE consultarse ninguna lista restrictiva hasta que el comercio esté identificado de
   forma unívoca en el registro mercantil.
2. Una coincidencia en listas restrictivas, del comercio o de su representante legal,
   impide recomendar la habilitación y DEBE escalar el caso a un oficial de cumplimiento.
3. Las categorías de alto riesgo (apuestas, criptoactivos, suplementos dietarios, venta de
   medicamentos) NUNCA reciben habilitación automática; decide un oficial de cumplimiento.
4. Toda afirmación del informe DEBE llevar su fuente. Si dos fuentes se contradicen, se
   muestran ambas con su origen y el sistema NO DEBE elegir una.
5. Si una fuente no responde, el informe se entrega declarando qué frente quedó sin cubrir;
   NUNCA se presenta como completo.

Justificación: son las reglas que definen un due diligence válido; cualquier excepción
expone a la pasarela a riesgo regulatorio.

### II. Garantizado vs. sugerido

Lo que no puede fallar se hace cumplir con código, no con instrucciones.

- Las reglas I.1 e I.2 DEBEN garantizarse con hooks del Agent SDK que bloqueen la acción
  prohibida, independientemente de lo que decida el modelo.
- La protección de secretos, el bloqueo de datos con forma real y la exigencia de
  especificación previa DEBEN garantizarse con hooks y permisos de Claude Code.
- Los prompts y CLAUDE.md solo guían estilo y convenciones; NO DEBEN ser el único
  mecanismo de una regla obligatoria.

Justificación: un modelo puede ignorar una instrucción; un hook no.

### III. Arquitectura de agentes

- Un coordinador descompone la solicitud y delega en subagentes especializados: registro
  mercantil, listas restrictivas, noticias y riesgo de categoría.
- Cada subagente DEBE tener acceso solo a las herramientas de su frente y recibir de forma
  explícita el contexto que necesita, sin heredar la conversación.
- Los frentes independientes se ejecutan en paralelo; listas restrictivas DEBE esperar al
  resultado del registro mercantil.
- Los ciclos continúan o terminan según la razón de parada (`stop_reason`) del modelo;
  NO DEBEN controlarse con un número fijo de iteraciones ni buscando palabras en el texto.
- Los resultados DEBEN separar el contenido de los metadatos (fuente, fecha).
- Un subagente que falla DEBE devolver un error estructurado con lo que alcanzó a obtener
  y si el error es reintentable; el coordinador decide si reintenta o entrega el informe
  con la cobertura incompleta declarada.

Justificación: el aislamiento por frente limita el alcance de cada agente y hace auditable
cada hallazgo.

### IV. Herramientas y servidor MCP

- Las fuentes de la pasarela se consumen ÚNICAMENTE a través del servidor MCP propio, que
  las simula con datos ficticios en archivos locales.
- Las decisiones solo se emiten mediante las herramientas `registrar_informe` y
  `escalar_a_cumplimiento`.
- Cada herramienta DEBE tener una descripción inequívoca de qué hace y qué no hace. En
  particular: una mención en noticias no es una coincidencia en listas restrictivas, y
  varias coincidencias en el registro mercantil no autorizan a elegir una.
- Los errores de las herramientas DEBEN ser estructurados e indicar si se puede reintentar.

Justificación: un único punto de acceso a las fuentes y a las decisiones permite
verificarlas y protegerlas con hooks.

### V. Escalamiento con criterio

- Se escala por coincidencia en listas restrictivas o por categoría de alto riesgo.
- Un comercio de bajo riesgo sin hallazgos NO DEBE escalarse y recibe recomendación de
  habilitación.
- Si el registro devuelve varios comercios parecidos, el coordinador DEBE pedir el
  identificador al analista en vez de elegir.
- El resumen al oficial DEBE ser autosuficiente, porque el oficial no tiene acceso a la
  conversación: comercio, hallazgos por frente con fuentes, cobertura alcanzada, causa del
  escalamiento y acción recomendada.

Justificación: escalar de más satura al oficial; escalar de menos deja pasar riesgo.

### VI. Transparencia en la interfaz

La interacción ocurre en una interfaz de chat donde se ven turno a turno los mensajes del
analista y las respuestas del coordinador. DEBE quedar evidente cuándo el coordinador
delega en un subagente, registra el informe o escala el caso. Alguien que no conoce el
código DEBE poder entender qué pasó en la conversación.

### VII. Solo datos ficticios

NO DEBE existir ningún dato real de comercios, personas, noticias, listas, documentos de
identidad, NIT o tarjetas en código, tests, logs ni configuración.

### VIII. Sin credenciales en el repositorio

Las credenciales se gestionan con variables de entorno y un archivo `.env` excluido de git.
Claude Code NO DEBE poder leer ni modificar `.env`. Solo se versiona `.env.example` sin
valores reales.

### IX. Spec first y trazabilidad

- Ningún código de producción sin especificación, plan y tareas en `specs/`.
- Cada cambio nace de un issue de GitHub, va en su propia rama y entra por un pull request
  que referencia y cierra ese issue.
- El estado del ticket en el GitHub Project DEBE reflejar el avance real, y el issue recibe
  comentarios de lo especificado, lo decidido y lo pendiente.
- Las convenciones del equipo se versionan en el repositorio; las preferencias personales
  quedan fuera de él; las piezas reutilizables se empaquetan en un plugin.

### X. Calidad y pruebas

- Tests con pytest junto al código que prueban.
- El código se formatea con ruff tras cada edición.
- Antes de abrir un pull request, el código DEBE pasar una revisión independiente de la
  sesión que lo generó y una revisión de cumplimiento de las reglas de negocio.
- Casos de prueba obligatorios que DEBEN pasar:
  - (a) comercio en categoría de alto riesgo que va a un oficial;
  - (b) comercio de bajo riesgo sin hallazgos con recomendación de habilitación;
  - (c) representante legal con coincidencia en listas restrictivas;
  - (d) dos comercios con nombres casi idénticos en el registro;
  - (e) intento de consultar listas sin identificación unívoca, que debe ser bloqueado;
  - (f) falla del servicio de noticias, con el informe entregado y la cobertura incompleta
    declarada;
  - (g) dos fuentes con fechas de constitución distintas.

## Restricciones técnicas

- Python 3.12 gestionado con uv.
- `claude-agent-sdk` para el coordinador y los subagentes.
- Servidor MCP propio con datos ficticios en archivos locales.
- pytest para pruebas y ruff para formato y lint.
- Interfaz de chat con Streamlit.
- Mensajes al analista y documentación en español.
- Alcance MVP: los comportamientos obligatorios (Principios I, V y casos de prueba de X)
  tienen prioridad sobre cualquier funcionalidad extra.

## Flujo de desarrollo y puertas de calidad

1. Issue de GitHub → rama propia → `spec.md`, `plan.md` y `tasks.md` en `specs/`.
2. Cada plan DEBE incluir una verificación explícita de cumplimiento de esta constitución.
3. Implementación con tests junto al código y formato con ruff tras cada edición.
4. Revisión independiente y revisión de cumplimiento de reglas de negocio.
5. Pull request que referencia y cierra el issue, con el ticket del GitHub Project
   actualizado. Cada pull request DEBE mantener en verde los tests existentes; los casos
   obligatorios (a)–(g) DEBEN pasar en la entrega final y en el ticket de la suite de
   pruebas.

## Gobierno

- Esta constitución prevalece sobre cualquier otra guía del proyecto (CLAUDE.md, prompts,
  documentación).
- Cambiarla requiere un pull request que explique el motivo y actualice la versión.
- Versionado semántico: MAJOR para eliminar o redefinir principios de forma incompatible;
  MINOR para añadir principios o ampliar materialmente una guía; PATCH para aclaraciones y
  correcciones de redacción.
- Toda especificación y todo plan DEBEN verificar su cumplimiento; toda desviación debe
  justificarse por escrito en el plan.

**Version**: 1.0.1 | **Ratified**: 2026-10-14 | **Last Amended**: 2026-10-14
