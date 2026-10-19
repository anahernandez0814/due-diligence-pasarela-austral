# Feature Specification: Plugin reutilizable para otros equipos

**Feature Branch**: `013-plugin-reutilizable-otros`

**Created**: 2026-10-19

**Status**: Draft

**Input**: Issue #13 de GitHub: "Plugin reutilizable para otros equipos". Que otro equipo de la pasarela pueda instalar en su propio repositorio las piezas reutilizables del ecosistema: un plugin con su manifiesto que empaqueta el subagente `revisor-codigo` y la skill `revisar-codigo` (#4) y el hook de datos con forma real (#3), un marketplace en este repositorio para instalarlo y una sección corta de instalación en el README. El alcance es **todo el issue**, con sus tres criterios de aceptación, más lo que la analista añadió al arrancar: generalizar el hook del #3 si lee rutas propias del repositorio y declarar el cambio, decidir en el plan cómo conviven el plugin y las piezas del repositorio (con su trade-off y un test), probar la instalación en un repositorio de prueba fuera de este con la CLI de Claude Code, y comprobar las pruebas en una copia limpia.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Otro equipo instala el plugin y usa sus tres piezas (Priority: P1)

Una persona de otro equipo de la pasarela, en su propio repositorio, añade el marketplace de este repositorio, instala el plugin y, sin copiar archivos a mano ni editar rutas, obtiene tres cosas: una guarda que bloquea antes de escribir, ejecutar o publicar cualquier texto con un dato con forma real (tarjeta, NIT, cédula o credencial), un subagente revisor independiente de solo lectura y una skill que lo lanza sobre el cambio de su rama.

**Why this priority**: es el primer criterio de aceptación del issue y el motivo del ticket (principio IX: «las piezas reutilizables se empaquetan en un plugin»). Sin la instalación funcionando fuera de este repositorio, el plugin es solo una carpeta.

**Independent Test**: en una carpeta temporal fuera de este repositorio, con un repositorio git nuevo, se instala el plugin desde el marketplace de esta rama y se comprueba cada pieza por separado: la guarda bloquea un valor con forma real generado en la prueba y deja pasar un texto ficticio; el subagente y la skill aparecen instalados, y la skill produce un reporte que termina con la línea de resumen.

**Acceptance Scenarios**:

1. **Given** un repositorio de prueba sin ninguna configuración de Claude Code, **When** se añade el marketplace de este repositorio y se instala el plugin, **Then** el plugin queda instalado y habilitado y sus tres piezas aparecen en Claude Code sin ningún paso manual más.
2. **Given** el plugin instalado en el repositorio de prueba, **When** se intenta escribir un archivo cuyo contenido tiene un número de tarjeta con forma real (generado en la prueba, nunca escrito literalmente), **Then** la acción se bloquea y el mensaje dice el tipo de dato y la línea, nunca el valor.
3. **Given** el plugin instalado, **When** se escribe un archivo con identificadores claramente ficticios, **Then** la acción se permite.
4. **Given** el plugin instalado y una rama con un cambio frente a su base, **When** se invoca la skill de revisión, **Then** el subagente revisor recibe el contexto del cambio (rama, base, archivos y diff si cabe), solo lee, y su reporte termina con `RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>`.
5. **Given** un repositorio de prueba que no usa Spec Kit (sin carpeta de specs del ticket ni constitución), **When** se invoca la skill de revisión, **Then** el revisor revisa calidad y errores, dice que no hay spec del ticket contra la que contrastar y no se detiene por eso.
6. **Given** que la instalación sin interfaz con la CLI de Claude Code no es posible, **When** se documenta la prueba, **Then** quedan los comandos exactos para que la analista la haga en la interfaz interactiva, y la prueba se marca como pendiente de la analista, no como hecha.

---

### User Story 2 - Ninguna pieza del plugin arrastra el proyecto (Priority: P1)

Quien instala el plugin no recibe nada propio de este proyecto: ni el nombre de la pasarela ficticia o del due diligence, ni sus identificadores ficticios, ni rutas de este repositorio (sus carpetas de código, sus specs, sus documentos, sus guardas o sus comandos propios), ni referencias a sus tickets. Las piezas ubican sus scripts con la raíz del plugin que da Claude Code.

**Why this priority**: es el segundo criterio de aceptación del issue. Una pieza que nombra rutas de este repositorio falla en otro (la skill de hoy ejecuta un script en una ruta de este repositorio) o confunde al otro equipo con requisitos que no son suyos.

**Independent Test**: un test automático recorre todos los archivos del plugin y falla si alguno contiene un término de la lista de términos propios del proyecto; otro comprueba que los scripts se ubican solo con la raíz del plugin.

**Acceptance Scenarios**:

1. **Given** los archivos del plugin, **When** se buscan los términos propios del proyecto (nombre de la pasarela ficticia y del due diligence, identificadores ficticios con la forma de los de este proyecto, rutas de su código, de sus specs, de sus documentos y de sus guardas, sus comandos propios y referencias a sus tickets), **Then** no aparece ninguno.
2. **Given** la configuración del hook del plugin, **When** se lee la ruta de sus scripts, **Then** se construye con la raíz del plugin, nunca con la del proyecto ni con una ruta absoluta.
3. **Given** el hook del #3 en este repositorio, **When** su mensaje de bloqueo cita un identificador ficticio propio del proyecto, **Then** la versión del plugin usa un ejemplo genérico, y el cambio queda declarado.
4. **Given** el subagente y la skill del #4, **When** nombran archivos de este repositorio como lo que cuenta para la cobertura, **Then** la versión del plugin describe lo que cuenta en términos genéricos (código, configuración y tests del cambio; documentación como referencia).

---

### User Story 3 - En este repositorio la guarda se ejecuta una sola vez (Priority: P1)

Quien trabaja en este repositorio sigue protegido por la guarda de datos con forma real exactamente como hasta ahora: una sola ejecución por acción, activa desde un clon recién hecho, con el mismo detector. El revisor propio y `/abrir-pr`, con su veredicto por commit, siguen funcionando igual.

**Why this priority**: es el tercer criterio de aceptación del issue. Dos ejecuciones dan mensajes duplicados y el doble de latencia; ninguna deja sin la protección que la constitución exige garantizar con hooks (principio II).

**Independent Test**: un test lee la configuración versionada de este repositorio y comprueba que, para cada herramienta que la guarda revisa, se registra una sola ejecución de la guarda; otro comprueba que los tests del #3 y del #4 siguen en verde.

**Acceptance Scenarios**:

1. **Given** la configuración versionada de este repositorio, **When** se cuentan las ejecuciones de la guarda de datos para cada herramienta de su matcher (escritura, edición, cuadernos, terminal y publicación en GitHub), **Then** cada una tiene exactamente una.
2. **Given** un clon limpio de este repositorio, sin pasos manuales, **When** se intenta escribir un dato con forma real, **Then** la guarda lo bloquea.
3. **Given** la decisión de convivencia del plan, **When** se lee el plan, **Then** dice qué opción se tomó, su trade-off y qué pasa si alguien instala el plugin a nivel de usuario y abre este repositorio.
4. **Given** la guarda del plugin y la del repositorio, **When** se ejecutan los casos de prueba del detector y de la guarda del #3, **Then** dan los mismos resultados: los mismos hallazgos, el mismo fallo cerrado y el mismo mensaje con la misma ruta relativa. No pueden divergir.
5. **Given** este repositorio con el cambio, **When** se ejecuta `/abrir-pr`, **Then** usa el revisor y la skill propios como hasta ahora y su veredicto sigue registrándose.

---

### User Story 4 - Instrucciones de instalación en el README (Priority: P2)

Quien llega al README encuentra una sección corta que dice qué trae el plugin, qué necesita el equipo para usarlo, los comandos para añadir el marketplace e instalarlo, y cómo desinstalarlo. El README completo lo reescribe el #14.

**Why this priority**: lo pide el alcance del issue; sin instrucciones, otro equipo no sabe que el plugin existe ni cómo instalarlo. Es P2 porque depende de que la instalación funcione (US1).

**Independent Test**: siguiendo solo la sección del README, en el repositorio de prueba, se instala el plugin y se comprueban las tres piezas.

**Acceptance Scenarios**:

1. **Given** el README, **When** se busca la sección del plugin, **Then** tiene las tres piezas en una línea cada una, los requisitos, los comandos de instalación (desde GitHub y desde una copia local) y el de desinstalación.
2. **Given** la sección, **When** se siguen sus comandos en el repositorio de prueba, **Then** el plugin queda instalado sin consultar otra documentación.

---

### Edge Cases

- **El plugin instalado a nivel de usuario y abierto este repositorio**: la guarda del plugin y la del repositorio coincidirían. El plan decide cómo se evita la doble ejecución o, si no se puede garantizar en ese escenario, lo declara como riesgo residual con su efecto (un mensaje duplicado, nunca menos protección).
- **El plugin se deshabilita o se desinstala en este repositorio**: la guarda del repositorio no puede depender de que el plugin esté instalado; un clon limpio queda protegido sin pasos manuales (principio II).
- **Un repositorio de otro equipo ya tiene su propio subagente o su propia skill con el mismo nombre**: las piezas del plugin no deben pisarlas; Claude Code las distingue por el nombre del plugin.
- **El revisor en una rama sin base de fusión** (repositorio sin rama principal o recién creado): el contexto preparado lo dice con `CONTEXTO INCOMPLETO` y el revisor declara `cobertura=incompleta`, como en el #4; la preparación nunca aborta la skill.
- **El revisor fuera de un repositorio git**: igual que el caso anterior, el contexto lo dice y la cobertura es incompleta.
- **La guarda ante una entrada que no puede leer o un error propio**: falla cerrada y bloquea, como en el #3.
- **El equipo no tiene el entorno que necesita el hook** (por ejemplo, el ejecutor de Python): el hook falla cerrado y bloquea, con un mensaje que dice qué falta; la sección del README lo pone en los requisitos.
- **Rutas con espacios o en Windows**: la raíz del plugin puede contener espacios; el hook y la skill funcionan igual.
- **El marketplace apunta a una rama que aún no está en `main`**: la prueba de instalación usa la rama del ticket o la copia local; las instrucciones del README usan la fuente estable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001, manifiesto**: el plugin DEBE tener su manifiesto `.claude-plugin/plugin.json` con nombre, versión y descripción en español. El nombre DEBE ser genérico, sin el nombre de este proyecto. El manifiesto NO DEBE llevar datos personales.
- **FR-002, las tres piezas**: el plugin DEBE empaquetar:
  - el subagente revisor independiente, de solo lectura (`Read`, `Grep` y `Glob`), con el mismo formato de reporte del #4 (cada hallazgo `BLOQUEANTE` o `SUGERENCIA` con `archivo:línea` y su razón, valores sensibles por tipo y ubicación, y la línea final `RESUMEN: …`);
  - la skill que lo lanza en un contexto separado con el contexto del cambio preparado por un script del propio plugin;
  - la guarda de datos con forma real del #3, en `PreToolUse`, con el mismo matcher, el mismo detector (tarjeta con Luhn, NIT con dígito de verificación, cédula con palabra de contexto y credenciales), el mensaje con tipo y línea sin el valor, y el fallo cerrado.
  - **Autocontenido**: un plugin instalado se copia a una caché y no llega a archivos fuera de su carpeta. El plugin DEBE llevar dentro todo lo que importan sus scripts. Hoy la guarda importa `comun` (`.claude/hooks/guarda_datos.py:19`) y el script de contexto importa `comun` y `veredicto` (`.claude/hooks/preparar_revision.py:20-21`). El script de la skill del plugin NO DEBE usar `veredicto` ni nada de `/abrir-pr`.
- **FR-003, raíz del plugin**: los scripts del plugin DEBEN ubicarse con `${CLAUDE_PLUGIN_ROOT}`. Ninguna pieza del plugin DEBE depender de una ruta de este repositorio, de una ruta absoluta ni de un archivo fuera de la carpeta del plugin. Para mostrar rutas relativas, la guarda puede usar la raíz del proyecto que da Claude Code al hook, que es genérica.
- **FR-004, sin rastros del proyecto**: ningún archivo del plugin DEBE contener rutas, nombres ni datos propios de este proyecto: el nombre de la pasarela ficticia o del due diligence, identificadores ficticios con la forma de los de este proyecto, rutas de su código, de sus specs, de sus documentos o de sus guardas, sus comandos propios ni referencias a sus tickets. Un test automático DEBE comprobarlo con una lista de términos que vive fuera del plugin.
- **FR-005, hook generalizado y declarado**: si el hook del #3 contiene algo propio del repositorio, la versión del plugin lo generaliza y el cambio DEBE quedar declarado en el plan y en DECISIONES.md. Como mínimo: el ejemplo del mensaje de bloqueo (hoy, un identificador ficticio del proyecto) y las referencias a la documentación del #3.
- **FR-006, revisor genérico**: el subagente y la skill del plugin DEBEN funcionar en un repositorio cualquiera.
  - Si el repositorio sigue la convención de Spec Kit (una carpeta de specs del ticket que se deduce de la rama, o una constitución), el revisor la usa como criterio de cumplimiento.
  - Si no la sigue, revisa calidad y errores, lo dice en el reporte y **no** reduce la cobertura por eso.
  - Lo que cuenta para la cobertura se describe de forma genérica: código, configuración y tests del cambio; la documentación es referencia.
  - El script que prepara el contexto DEBE salir siempre sin error, y decir con `CONTEXTO INCOMPLETO: <motivo>` lo que no pudo calcular, como en el #4.
- **FR-007, una sola guarda**: la guarda de datos con forma real del plugin y la de este repositorio NO DEBEN poder divergir, **la guarda completa y no solo el detector**: el detector, y lo que viene de `comun`:
  - el fallo cerrado;
  - el mensaje con el tipo y la línea, sin el valor;
  - la ruta relativa a la raíz del proyecto;
  - los textos revisados por herramienta.

  O hay una sola fuente que el plugin lleva dentro, o un test falla si divergen. Los tests del detector y de la guarda del #3 (`test_detector_datos.py` y `test_guarda_datos.py`) DEBEN ejecutarse también contra la versión del plugin.
- **FR-008, marketplace**: este repositorio DEBE tener un marketplace que liste el plugin, de modo que otro proyecto lo instale apuntando a este repositorio en GitHub o a una copia local, sin publicarlo en marketplaces externos.
- **FR-009, convivencia**: en este repositorio, con su configuración versionada, la guarda de datos con forma real DEBE ejecutarse **una sola vez** por acción.
  - El plan decide cómo (por ejemplo, que este repositorio use la guarda del plugin y deje de registrar la suya, o que el plugin no se habilite aquí), con su trade-off.
  - La guarda DEBE quedar activa desde un clon limpio, sin pasos manuales (principio II).
  - Un test automático DEBE comprobarlo.
  - El revisor propio, `/abrir-pr` y el veredicto por commit DEBEN seguir funcionando igual.
- **FR-010, prueba de instalación**: la instalación DEBE probarse en un repositorio git nuevo en una carpeta temporal fuera de este, primero sin interfaz con la CLI de Claude Code (`claude plugin …`).
  - Se comprueban las tres piezas: la guarda bloquea un valor con forma real generado en la prueba y deja pasar uno ficticio; el subagente y la skill quedan instalados, y la skill produce un reporte con la línea de resumen.
  - Si algún paso exige la interfaz interactiva, quedan los comandos exactos para la analista y el paso se marca pendiente, no hecho.
  - El resultado se anota en el quickstart del ticket.
- **FR-011, README**: el README DEBE tener una sección corta con lo que trae el plugin, los requisitos, los comandos para añadir el marketplace e instalarlo (desde GitHub y desde una copia local) y el de desinstalación. No reescribe el resto del README (#14).
- **FR-012, pruebas**: los tests nuevos van junto al código que prueban y se ejecutan con las suites existentes. En una copia limpia (clon de la rama, sin `.env`, sin clave y sin `PYTHONUTF8`), `uv run pytest src` y las pruebas de `.claude/hooks` DEBEN pasar, igual que las del plugin.
- **FR-013, documentación del ticket**: DECISIONES.md recibe solo una entrada corta del #13. Cualquier choque con un FR o con la constitución se declara como «Desviación justificada» y se actualizan todos los documentos en el mismo commit.

### Key Entities

- **Plugin**: carpeta con su manifiesto, el subagente, la skill, el hook y sus scripts. Tiene nombre, versión y descripción; se identifica en Claude Code por su nombre.
- **Marketplace**: catálogo versionado en este repositorio que lista el plugin y dónde está su carpeta.
- **Guarda de datos con forma real**: el hook de `PreToolUse` y su detector; recibe la acción que Claude Code va a ejecutar y la bloquea o la deja pasar.
- **Contexto de revisión**: lo que el script de la skill imprime antes de lanzar el subagente: marca, rama, base, ticket y constitución si existen, archivos cambiados y diff si cabe.
- **Lista de términos del proyecto**: lo que no puede aparecer en el plugin; vive en los tests, fuera del plugin.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: en un repositorio de prueba nuevo, la instalación del plugin se completa con, como máximo, tres comandos, y el 100 % de las comprobaciones de sus tres piezas pasan (o las que exigen la interfaz quedan con sus comandos exactos y marcadas pendientes de la analista).
- **SC-002**: el 0 % de los archivos del plugin contiene algún término de la lista de términos del proyecto.
- **SC-003**: en este repositorio, el 100 % de las herramientas que revisa la guarda tienen exactamente una ejecución por acción en la configuración versionada.
- **SC-004**: la guarda del plugin y la de este repositorio (el detector y lo que viene de `comun`) dan el mismo resultado en el 100 % de los casos de prueba del detector y de la guarda del #3.
- **SC-005**: en una copia limpia, el 100 % de los tests de `src`, de `.claude/hooks` y del plugin pasan, y los tests anteriores siguen en verde.
- **SC-006**: alguien que no conoce el código instala el plugin siguiendo solo la sección del README (valoración de la analista en el repositorio de prueba).

## Assumptions

- **Usuarios**: equipos de la misma pasarela, con Claude Code y soporte de plugins. El detector cubre los formatos de datos que maneja la pasarela (tarjetas, NIT y cédula de Colombia, y credenciales comunes): son del dominio, no de este proyecto.
- **Requisitos del entorno**: el hook y el script de la skill se ejecutan con Python 3.12 a través de uv, como las guardas de este repositorio, y solo usan la biblioteca estándar. El plan lo confirma y la sección del README lo pone como requisito.
- **Supuesto a verificar en el plan**: `${CLAUDE_PLUGIN_ROOT}` se expande dentro de la skill de un plugin, tanto en la línea `!` que prepara el contexto como en `allowed-tools`. El plan lo confirma en la documentación oficial (research). Si no se expande, propone la alternativa con su trade-off.
- **Convención de Spec Kit**: la carpeta de specs del ticket que se deduce de la rama y la constitución de Spec Kit son convenciones de la herramienta, no de este proyecto; el revisor las usa si existen.
- **Decisión confirmada por la analista**: el subagente y la skill del repositorio **se conservan** tal como están, porque `/abrir-pr`, su veredicto por commit y su lista de cobertura dependen de ellos; el plugin lleva una versión genérica de los dos. La guarda, en cambio, tiene una sola fuente o un test de equivalencia (FR-007).
- **Decisión confirmada por la analista**: el revisor del plugin, en un repositorio sin Spec Kit, revisa calidad y errores y declara que no hay spec, sin reducir la cobertura (FR-006).
- **Decisión confirmada por la analista**: el plugin vive en una carpeta propia dentro de este repositorio y el marketplace en su raíz; el plan fija los nombres. La prueba de instalación usa la rama del ticket (o la copia local) porque el plugin aún no está en `main`.
- **Fuera de alcance**:
  - publicar el plugin en marketplaces externos;
  - empaquetar el auditor de cumplimiento, las demás guardas, `/abrir-pr`, el veredicto o las skills de Spec Kit (son propios de este proyecto);
  - el README completo y la reescritura de DECISIONES.md (#14);
  - el versionado o la publicación de nuevas versiones del plugin.
- **Dependencias**: #3 (la guarda y el detector) y #4 (el subagente, la skill y el script de contexto), ya fusionados.
