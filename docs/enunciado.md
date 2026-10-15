# Prueba técnica Claude Code + Agent SDK — Escenario Pagos: Due diligence de comercios

## Propósito de la prueba
Vas a construir un sistema multi-agente con el Claude Agent SDK que resuelve un caso real del sector financiero, y lo vas a construir dentro de un entorno de desarrollo con Claude Code configurado como lo haría un equipo profesional. Después sustentarás tus decisiones.

No evaluamos únicamente el sistema que entregues. Evaluamos tres cosas inseparables: el sistema funcional, la forma en que parametrizaste tu ecosistema de Claude Code para construirlo y el ciclo de vida que seguiste, guiado por especificaciones y trazado en GitHub.

Asumimos que usarás Claude Code durante toda la construcción; eso es lo esperado. Lo que calificamos es tu criterio: dónde vive cada pieza de configuración, por qué elegiste cada mecanismo y qué tan bien entiendes lo que entregaste. Una línea bien ubicada vale más que diez páginas de CLAUDE.md.

La prueba toma como referencia los dominios de la certificación Claude Certified Architect – Foundations: arquitectura agéntica y orquestación, diseño de herramientas e integración MCP, configuración y flujos de Claude Code, prompt engineering y salida estructurada, y gestión de contexto y confiabilidad

## Reglas generales

- Duración: Dos semanas calendario. Los tres entregables deben estar cargados a más tardar el domingo 18 de octubre de 2026. Estimamos entre 12 y 15 horas efectivas.
- Alcance: Se califica un MVP sólido, no un producto completo. Si te falta tiempo, prioriza los comportamientos obligatorios del sistema.
- Uso de IA: Se espera que uses Claude Code durante toda la construcción. No es trampa; es el objeto de la prueba.
- Datos: Todos los datos deben ser ficticios. Ningún dato real de comercios,personas, noticias o listas restrictivas, ni siquiera en logs o en la configuración
- Repositorio: Repositorio propio en GitHub con acceso para los evaluadores, acompañado de un GitHub Project donde vive el backlog.
- Lenguaje: Python o TypeScript, a tu elección.
- Trabajo individual: La prueba es individual. Cada persona tiene un escenario asignado; no se cambia ni se escoge.

El tiempo es limitado a propósito. Preferimos pocas piezas bien ubicadas y bien justificadas que muchas piezas decorativas.

## Tu escenario: due diligence de comercios con arquitectura multi-agente
Eres parte del equipo de riesgo de una pasarela de pagos ficticia, Pasarela Austral. Antes de habilitar a un comercio para procesar pagos, un analista de cumplimiento revisa a mano el registro mercantil, las listas restrictivas, las noticias y el riesgo de la categoría del negocio, y redacta un informe. La pasarela quiere un sistema multi-agente que haga esa investigación, entregue un informe con fuentes y sepa cuándo la decisión le corresponde a un oficial de cumplimiento.

Quien conversa con el sistema es un analista interno de la pasarela, no el comercio. Un mensaje típico se ve así: "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren procesar ventas en línea de suplementos dietarios y estiman unos $80.000.000 mensuales. ¿Lo podemos habilitar esta semana?"

Un agente coordinador recibe la solicitud, la descompone y delega cada frente de la investigación en subagentes especializados: registro mercantil, listas restrictivas, noticias y riesgo de la categoría. Después sintetiza un informe con su recomendación. Las fuentes son ficticias y viven en un servidor MCP que tú construyes, con datos locales.

Categorías de alto riesgo de la pasarela: apuestas, criptoactivos, suplementos dietarios y venta de medicamentos.

### Reglas de negocio de la pasarela, que tu solución debe respetar:
1. Ninguna consulta a listas restrictivas se hace sin que el comercio esté identificado de forma unívoca en el registro mercantil.
2. Una coincidencia en listas restrictivas, del comercio o de su representante legal, impide recomendar la habilitación y escala el caso a un oficial de cumplimiento.
3. Un comercio en una categoría de alto riesgo nunca recibe una recomendación de habilitación automática; la decisión es de un oficial de cumplimiento.
4. Cada afirmación del informe tiene su fuente. Si dos fuentes se contradicen,el informe muestra ambas; no elige una.
5. Si una fuente no responde, el informe se entrega indicando qué frente quedó sin cubrir; nunca se presenta como completo.

Las categorías de alto riesgo y las reglas son parte del enunciado y no se negocian.

## Ciclo de vida: Spec Driven Development con Spec Kit
Todo el desarrollo del sistema sigue Spec Driven Development con Spec Kit: primero se define qué y por qué, después cómo. No se escribe código de producción sin una especificación, un plan y una lista de tareas que lo respalden.

Instala Spec Kit con la integración para Claude Code y sigue este ciclo. Los comandos se muestran con prefijo /speckit. ; según la versión pueden aparecer como /speckit-

1. Una vez por proyecto: /speckit.constitution. La constitución debe recoger los principios del proyecto, incluidas las reglas de negocio de la pasarela, el uso exclusivo de datos ficticios y el criterio de qué se hace cumplir con hooks y qué con instrucciones.

2. Por cada ticket de tu backlog: /speckit.specify tomando como insumo el contenido del issue de GitHub. Usa /speckit.clarify si la especificación queda ambigua.

3. /speckit.plan con tus decisiones técnicas: lenguaje, estructura del coordinador y los subagentes, diseño del servidor MCP.

4. /speckit.tasks para obtener las tareas. Opcionalmente, /speckit.taskstoissues para convertirlas en issues hijos del ticket.

5. /speckit.analyze antes de implementar, para revisar la consistencia entre especificación, plan y tareas.

6. /speckit.implement para construir, y /speckit.converge si al final quedan brechas entre lo especificado y lo construido.

Los artefactos de Spec Kit, la constitución en .specify/memory/ y las carpetas de cada feature en specs/, se versionan en el repositorio. Son evidencia de tu proceso y se revisan en la sustentación.

No es obligatorio pasar cada ticket por todos los pasos opcionales. Sí es obligatorio que cada ticket implementado tenga su especificación, su plan y sus tareas en el repositorio.

## Gestión del proyecto en GitHub
El backlog vive en GitHub y Claude Code lo lee y lo actualiza por sí mismo a través del servidor MCP oficial de GitHub. La planificación y el avance no se gestionan a mano: se arrastran desde los tickets y se reflejan en ellos a medida que el proyecto avanza.

### Preparación:
1. Crea tu repositorio y un GitHub Project asociado con un campo de estado, por ejemplo Todo, In progress, In review y Done.
2. Construye tu propio backlog a partir de los requisitos de este enunciado,con un issue por funcionalidad, y agrégalos al Project. Cómo descompones el trabajo también se evalúa.
3. Configura el servidor MCP de GitHub en Claude Code. Ten en cuenta que el toolset de projects no viene habilitado por defecto; habilitarlo es parte de la prueba.

**Lo que debe ocurrir de forma autónoma durante el desarrollo:**
- Claude Code toma el siguiente ticket del Project y lo usa como insumo de /speckit.specify
- Al iniciar un ticket, lo mueve a In progress. Al abrir el pull request, a In review. Al fusionarlo, a Done.
- Cada pull request referencia y cierra su issue.
- El issue recibe comentarios de avance con lo que se especificó, lo que se decidió y lo que quedó pendiente.

Cómo automatizas esto es decisión tuya. Puede ser un comando, una skill, un subagente, un hook o una combinación. Lo vamos a revisar en la sustentación.

El historial del Project y de los issues es evidencia. Un evaluador debe poder reconstruir cómo avanzó el proyecto solo mirando GitHub.


## Requisitos del ecosistema de Claude Code

Tu repositorio debe tener un ecosistema de Claude Code parametrizado como lo haría un equipo profesional. Estos son los mínimos; los comandos que instala Spec Kit no cuentan para ellos.

| Componente | Mínimo | Condicion |
|-----------|-----------|-----------|
| CLAUDE.md | Jerarquía correcta| Convenciones de equipo a nivel de proyecto, separadas de lo personal. Al menos un uso de @import o de CLAUDE.md por subdirectorio, justificado.|
| Reglas en .claude/rules/ | 2 | Al menos 2 con alcance por ruta mediante paths y patrones glob. |
| Subagentes | 2 | Cada uno con herramientas restringidas a su rol. |
| Skills | 2 | Entre todas deben usar context: fork, allowed-tools y argument-hint. |
| Hooks | 2 | Al menos uno que bloquee antes de ejecutar y uno que actúe después de una edición.|
| Comandos propios | 1 | Compartidos con el equipo vía control de versiones|
| Servidores MCP | 2 | El de GitHub y el propio del escenario. Ninguna credencial en el repositorio |
| Plugin | 1 | Empaqueta al menos un subagente, una skill y un hook reutilizables por otro equipo. Pueden ser los recursos creados para los requerimientos anteriores. |

**Necesidades que tu ecosistema debe resolver.** Para cada una, tú decides el mecanismo y lo justificas en tu documento de decisiones:
1. Todo desarrollador que clone el repositorio recibe las convenciones del equipo sin configurar nada.
2. Tus preferencias personales no afectan a tus compañeros.
3. Los tests viven junto al código que prueban, en muchas carpetas, y todos siguen las mismas convenciones.
4. No se escribe código de un ticket sin que exista su especificación en specs/.
5. Ningún archivo del repositorio puede contener algo con forma de documento de identidad real, de NIT real o de número de tarjeta real.
6. Los archivos de secretos y variables de entorno no se leen ni se modifican desde Claude Code.
7. El código queda formateado después de cada edición.
8. Antes de abrir un pull request, el código pasa por una revisión independiente de la sesión que lo generó.
9. Una revisión de cumplimiento verifica que las reglas de negocio de la pasarela estén implementadas como se especificaron.
10. El estado de los tickets en GitHub se mantiene sincronizado con el avance real, sin intervención manual.
11. Otro equipo de la pasarela puede instalar tus piezas reutilizables en su propio repositorio.

Un mismo componente puede resolver varias necesidades, y una necesidad puede resolverse con varios componentes. Lo que evaluamos es que la elección sea la adecuada y que la sepas defender.
Requisitos del sistema multi-agente

## El sistema se construye con el Claude Agent SDK. 
El coordinador y los subagentes consumen las fuentes de la pasarela desde tu servidor MCP, que las simula con datos ficticios en memoria o en archivos locales; no necesitas una base de datos real.

**Herramientas mínimas del servidor MCP:**

| Herramienta | Proposito |
|-------------|-----------|
| consultar_registro_mercantil | Busca un comercio por nombre o identificador: existencia, fecha de constitución, representante legal y estado. Puede devolver varias coincidencias. |
| consultar_listas_restrictivas | Verifica un comercio o una persona contra listas restrictivas ficticias |
| buscar_noticias | Busca menciones de un comercio o una persona en un corpus de noticias ficticias.|
| consultar_riesgo_categoria | Devuelve el nivel de riesgo de una categoría de negocio |
| registrar_informe | Registra el informe de due diligence con su recomendación.|
| escalar_a_cumplimiento | Pasa el caso a un oficial de cumplimiento con un resumen estructurado|

**Comportamientos obligatorios:**
1. Arquitectura coordinador-subagentes. Un coordinador descompone la solicitud y delega en al menos tres subagentes especializados. Cada subagente tiene acceso solo a las herramientas de su frente.
2. Contexto explícito. Los subagentes no heredan la conversación del coordinador: reciben de forma explícita lo que necesitan. Sus resultados separan el contenido de los metadatos, como la fuente y la fecha.
3. Ejecución en paralelo. Los frentes que no dependen entre sí se investigan en paralelo. Los que sí dependen, como las listas restrictivas respecto del registro mercantil, esperan a su dependencia.
4. Ciclo agéntico correcto. El coordinador y los subagentes continúan o terminan según la razón de parada del modelo, no por un número fijo de iteraciones ni por buscar palabras en el texto.
5. Reglas de negocio garantizadas, no sugeridas. Las reglas 1 y 2 del escenario se hacen cumplir con hooks del SDK. Una instrucción en el prompt no es suficiente.
6. Descripciones de herramientas que eviten confusiones. Debe quedar claro que una mención en buscar_noticias no es una coincidencia en consultar_listas_restrictivas, y qué hacer con varias coincidencias en el registro.
7. Errores estructurados y cobertura parcial. Un subagente que falla devuelve un error estructurado con lo que alcanzó a obtener y si se puede reintentar. El coordinador decide si reintenta o si entrega el informe con la cobertura incompleta declarada.
8. Procedencia y conflictos. Cada afirmación del informe se vincula a su fuente. Los datos contradictorios entre fuentes se reportan juntos, con su origen.
9. Ambigüedad. Si el registro devuelve varios comercios con nombres parecidos,el coordinador pide el identificador en lugar de elegir.
10. Escalamiento con criterio. Escala cuando hay coincidencia en listas y cuando la categoría es de alto riesgo. No escala comercios de bajo riesgo sin hallazgos.
11. Handoff útil. El resumen al oficial de cumplimiento incluye el comercio,los hallazgos por frente con sus fuentes, la cobertura alcanzada, la causa del escalamiento y una acción recomendada. El oficial no tiene acceso a la conversación.
12. Interfaz de chat. La interacción con el sistema ocurre en una interfaz que simula un chat: se ven los mensajes del analista y las respuestas del coordinador turno a turno, y cuando el coordinador delega en un subagente, registra el informe o escala, la interfaz lo hace evidente. No se califica el diseño visual, sino que alguien que no conoce el código entienda qué pasó en la conversación.

**Casos de prueba que tu repositorio debe incluir y pasar:**
- El mensaje de ejemplo del escenario: un comercio en categoría de alto riesgo que debe ir a un oficial.
- Un comercio de bajo riesgo sin hallazgos, con recomendación de habilitación.
- Un representante legal con coincidencia en listas restrictivas.
- Dos comercios con nombres casi idénticos en el registro.
- Un intento de consultar listas restrictivas sin identificación unívoca, que debe ser bloqueado.
- Una falla del servicio de noticias, con el informe entregado y la cobertura incompleta declarada.
- Dos fuentes que reportan fechas de constitución distintas

## Entregables y sustentación

La prueba tiene tres entregables. Los tres deben estar listos a más tardar el domingo 18 de octubre de 2026

| Entregable | Dónde se entrega | Qué demuestra |
|------------|------------------|---------------|
| Repositorio y GitHub Project | GitHub, con acceso para los evaluadores | El historial real de la construcción: commits, issues, pull requests y el avance del Project.|
| Defensa del código | Fase Code Defense de Edu Ranker: archivo .zip y video de defensa | Que entiendes y puedes justificar lo que construiste.|
| Video de funcionamiento | Enlace en el README del repositorio | Que el sistema funciona. |

1. Repositorio y GitHub Project: Es el mismo repositorio donde trabajaste durante las dos semanas, con su Project y su historial intactos. No se reescribe el historial antes de entregar
2. Defensa del código en Code Defense: En la fase Code Defense de Edu Ranker subes tu repositorio como archivo .zip y grabas un video de hasta 15 minutos defendiendo tu código. Esta defensa no es para mostrar que el sistema funciona; para eso está el tercer entregable. Aquí se defiende cómo está construido.

** El archivo .zip debe incluir:**
- El repositorio completo, con la carpeta .git para conservar el historial de commits.
- README con instrucciones para correr el sistema y los tests en menos de 5 minutos, el enlace a tu GitHub Project y el enlace al video de funcionamiento.
- DECISIONES.md de máximo dos páginas: qué mecanismo elegiste para cada necesidad del ecosistema y por qué.
- Los artefactos de Spec Kit versionados

No incluyas dependencias instaladas como node_modules o entornos virtuales. El tamaño maximo es de 50MB. Un archivo .env o cualquier credencial dentro del .zip es falta grave

**Lo que debes defender en el video:**
1. La parametrización del ecosistema. Recorre la configuración de Claude Code: memoria, reglas, skills, agentes, hooks, comandos, servidores MCP y plugin. Explica por qué cada pieza está donde está y qué alternativa descartaste.
2. Las especificaciones. Muestra cómo están estructurados los artefactos de Spec Kit: la constitución y, para al menos un ticket, cómo la especificación se convirtió en plan, tareas y código.
3. El sistema construido con el Agent SDK. Explica cómo descompone el coordinador, qué contexto recibe cada subagente y qué herramientas tiene, cómo garantizan los hooks las reglas de negocio, cómo se manejan las fallas y la cobertura parcial, y el diseño de las herramientas MCP

La defensa incluye una revisión de autoría: tu explicación se contrasta con el código entregado. HABLA DE TU CÓDIGO, NO DE CÓMO DEBERÍA SER UN CÓDIGO ASÍ.

3. Video de funcionamiento

Un video corto, de máximo 5 minutos, con el sistema funcionando en su interfaz de chat. Corre los casos de prueba obligatorios y deja que se vea el resultado de cada uno. No expliques el código; eso va en la defensa. Publícalo donde los evaluadores puedan verlo sin pedir acceso y deja el enlace en el README

**Criterios de evaluación** 
La sustentación no es un área más: es la condición de validez de todas las demás. Un elemento que está en el repositorio pero no se sustenta adecuadamente en el video vale cero, sin importar su calidad.

| Area | Peso | Que observamos |
|Ecosistema de Claude Code| 25% | Cada pieza en el lugar correcto, con el mecanismo adecuado a la necesidad. Mínimos cumplidos.|
| Sistema multi-agente y servidor MCP | 25% | Comportamientos obligatorios y casos de prueba funcionando en una interfaz de chat comprensible. Reglas de negocio garantizadas por hooks.|
| Ciclo de vida y trazabilidad | 15% | Spec Kit aplicado por ticket. Backlog en GitHub actualizado de forma autónoma y reconstruible.|
| Sustentación | 35% | Justificación de decisiones, comprensión de alternativas y dominio del propio código.|

El funcionamiento del sistema se verifica con el video de funcionamiento. Todo lo demás se califica en dos momentos: lo que está en el repositorio y lo que defiendes sobre ello en Code Defense. Si en la defensa no puedes explicar un elemento, ese elemento pierde su puntaje. Si la revisión de autoría no confirma que el código es tuyo, la entrega completa pierde validez

Una regla de negocio que dependa solo del prompt, una credencial en el repositorio o un dato que parezca real son faltas graves, sin importar el resto de la entrega. La calidad pesa más que la cantidad: superar los mínimos no suma si las piezas adicionales no resuelven una necesidad real.