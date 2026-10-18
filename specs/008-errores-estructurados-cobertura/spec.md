# Feature Specification: Errores estructurados y cobertura parcial

**Feature Branch**: `008-errores-estructurados-cobertura`

**Created**: 2026-10-17

**Status**: Draft

**Input**: Issue #8 de GitHub: "Errores estructurados y cobertura parcial". Que una falla en un frente de la investigación no se oculte ni detenga todo: se informa con estructura, el coordinador decide qué hacer y el informe declara lo que quedó sin cubrir.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entregar el informe aunque una fuente no responda, declarando lo que quedó sin cubrir (Priority: P1)

El analista pide el due diligence de un comercio y el servicio de noticias no responde. La investigación no se detiene: los demás frentes siguen, el coordinador entrega el informe y ese informe dice, frente por frente, qué quedó cubierto y qué no, con el motivo. El caso nunca se presenta como completo.

**Why this priority**: es la regla I.5 de la constitución y el caso de prueba (f). Un informe que oculta un frente caído hace creer al analista que se revisó algo que no se revisó.

**Independent Test**: sin llamar al modelo, se simula la caída de noticias (la misma respuesta que da la pasarela con `PASARELA_FALLA_NOTICIAS=1`) con los otros tres frentes terminados, y un coordinador simulado registra el informe; el informe registrado declara noticias como no cubierto y el caso no figura como completo.

**Acceptance Scenarios**:

1. **Given** el servicio de noticias caído y los otros tres frentes terminados, **When** el coordinador registra el informe, **Then** el informe se registra y su cobertura declara noticias como no cubierto, con el motivo, y los otros tres como cubiertos.
2. **Given** el mismo caso, **When** se revisa el estado al terminar, **Then** el caso no figura como completo.
3. **Given** el mismo caso, **When** el coordinador intenta registrar un informe cuya cobertura dice que todo quedó cubierto, **Then** la cobertura que queda registrada es la calculada por el código, no la declarada por el modelo (ver FR-010).
4. **Given** el servicio de noticias caído, **When** se ejecutan registro, categoría y listas, **Then** su resultado no cambia por la caída de noticias: la falla de un frente no detiene ni contamina los demás.
5. **Given** los cuatro frentes terminados con normalidad, **When** se registra el informe, **Then** su cobertura declara los cuatro como cubiertos y la cobertura es completa.

---

### User Story 2 - Que cada frente que falla devuelva un error estructurado (Priority: P1)

Cuando un subagente no puede cubrir su frente, el coordinador recibe un error con estructura fija: qué frente falló, qué tipo de error fue, lo que alcanzó a obtener antes de fallar y si se puede reintentar. El coordinador no tiene que deducirlo leyendo texto.

**Why this priority**: es el principio III («un subagente que falla DEBE devolver un error estructurado con lo que alcanzó a obtener y si el error es reintentable») y la base para decidir si se reintenta y para calcular la cobertura.

**Independent Test**: sin llamar al modelo, se simulan las distintas formas de fallo de un frente (error de la fuente reintentable, error no reintentable, terminación anómala del subagente, subagente sin consultas, resultado con forma inválida, listas con una sola de las dos consultas, excepción) y se comprueba que cada una produce el error estructurado con sus cuatro datos.

**Acceptance Scenarios**:

1. **Given** una fuente que devuelve un error reintentable (servicio no disponible), **When** termina el subagente, **Then** el coordinador recibe un error con el frente, el tipo de error de la fuente, lo obtenido (vacío si nada) y reintentable sí.
2. **Given** una fuente que devuelve un error no reintentable, **When** termina el subagente, **Then** el error dice reintentable no.
3. **Given** el subagente de listas que consultó al comercio con éxito y falló al consultar al representante, **When** termina, **Then** lo obtenido incluye el resultado del comercio, con su fuente y su fecha, y el frente queda no cubierto.
4. **Given** un subagente que terminó de forma anómala (límite de seguridad, razón de parada inesperada o excepción), **When** el coordinador recibe la respuesta, **Then** el tipo de error indica la terminación anómala y no se presenta como error de la fuente.
5. **Given** un subagente que no hizo ninguna consulta o cuyo resultado no tiene la forma del contrato de la pasarela, **When** el coordinador recibe la respuesta, **Then** el tipo de error lo indica de forma distinguible de los anteriores.
6. **Given** un intento que un hook de las reglas bloqueó (#7), **When** se evalúa el frente, **Then** ese bloqueo no se cuenta como error del frente ni lo vuelve reintentable, como ya ocurre desde el #7.
7. **Given** cualquier error estructurado, **When** se revisa el mensaje, **Then** está en español y, ante una excepción del subagente, solo nombra su tipo, sin el texto interno de la excepción. Hoy la delegación incluye ese texto en el error.

---

### User Story 3 - Reintentar solo lo reintentable, con una política fija (Priority: P1)

Si un frente falló con un error reintentable, la política del coordinador permite volver a ejecutarlo; si el error no es reintentable, no se vuelve a ejecutar. Los reintentos tienen un límite, y cuando se agota, el caso sigue y se entrega con la cobertura incompleta declarada. Cada reintento queda en el registro de eventos.

**Why this priority**: es el segundo criterio de aceptación del issue y el principio III («el coordinador decide si reintenta o entrega el informe con la cobertura incompleta declarada»). Hoy, volver a delegar un frente con la misma entrada devuelve el resultado guardado (#6), así que reintentar es imposible.

**Independent Test**: sin llamar al modelo, se simula un frente que falla con error reintentable y después responde bien; con la política se reintenta y el frente queda cubierto. Con un error no reintentable, una nueva delegación con la misma entrada no lanza al subagente. Con un error reintentable persistente, los reintentos se detienen en el límite.

**Acceptance Scenarios**:

1. **Given** un frente que falló con error reintentable, **When** se aplica la política, **Then** el frente se vuelve a ejecutar con la misma entrada y queda constancia del reintento en los eventos.
2. **Given** un reintento que esta vez responde bien, **When** termina, **Then** el frente queda cubierto y el informe lo declara cubierto; los eventos conservan la falla anterior.
3. **Given** un frente que falló con error no reintentable, **When** se vuelve a pedir con la misma entrada, **Then** el subagente no se vuelve a lanzar, el coordinador recibe el mismo error y queda constancia de que el reintento se denegó.
4. **Given** un error reintentable persistente (por ejemplo, noticias con la caída activa), **When** se agota el límite de reintentos, **Then** no se lanza otro intento, el frente queda no cubierto y el caso continúa hasta el informe.
5. **Given** un frente terminado con normalidad, **When** se vuelve a pedir con la misma entrada, **Then** se devuelve el resultado guardado, como en el #6: no es un reintento.
6. **Given** un frente que falló, **When** se vuelve a delegar con otra entrada (por ejemplo, una categoría corregida), **Then** es una delegación nueva, como en el #6, y no consume el límite de reintentos.

---

### User Story 4 - Cobertura calculada por el código y visible en el caso (Priority: P2)

La cobertura del caso (qué frentes quedaron cubiertos, cuáles no y por qué) la calcula el código a partir de lo que devolvieron los subagentes, no la escribe el modelo. Está disponible en el estado del caso para el informe, para la respuesta al analista y para la interfaz.

**Why this priority**: es lo que permite que el informe y el caso nunca se presenten como completos por error; si la cobertura la decidiera el modelo, dependería de que no se equivoque.

**Independent Test**: sin llamar al modelo, se recorren las combinaciones de situación de los cuatro frentes (terminado, no terminado, rechazado, sin iniciar, en curso) y se comprueba que la cobertura es completa solo cuando los cuatro terminaron, y que cada frente no cubierto trae su motivo.

**Acceptance Scenarios**:

1. **Given** un frente que nunca se delegó (por ejemplo, el analista no dio la categoría), **When** se calcula la cobertura, **Then** ese frente figura como no cubierto con el motivo «no se delegó».
2. **Given** el frente de listas rechazado porque el registro no identificó un comercio único, **When** se calcula la cobertura, **Then** listas figura como no cubierto con ese motivo.
3. **Given** el frente de listas invalidado porque el comercio del registro cambió, **When** se calcula la cobertura, **Then** listas figura como no cubierto.
4. **Given** un frente todavía en curso, **When** se calcula la cobertura, **Then** figura como no cubierto.
5. **Given** cualquier combinación con al menos un frente no cubierto, **When** se consulta si el caso es completo, **Then** la respuesta es no.
6. **Given** el caso terminado, **When** se ejecuta desde la línea de comandos, **Then** la salida muestra la cobertura por frente con el motivo de cada frente no cubierto.

### Edge Cases

- **Listas pedida antes del registro**: el rechazo es reintentable (FR-003) y no cuenta como reintento; listas se puede pedir de nuevo cuando el registro termine.
- **Texto interno de una excepción**: no llega al coordinador, ni a los eventos ni al informe; solo el tipo de la excepción (US2-7).
- **Error reintentable sin valor booleano**: un error cuyo indicador de reintento falta o no es sí/no se trata como no reintentable (falla cerrada).
- **Listas con una consulta fallida y otra correcta**: el frente queda no cubierto, lo obtenido conserva la consulta correcta, y el reintento vuelve a ejecutar el frente completo (comercio y representante).
- **Dos pedidos de reintento a la vez**: un frente en curso no se lanza dos veces (como en el #6); el segundo pedido recibe el resultado del primero y no consume otro reintento.
- **Reintento que falla con un error distinto**: lo que decide si se puede volver a intentar es el último error; si ahora no es reintentable, no hay más reintentos.
- **Un reintento de registro que identifica otro comercio**: se aplica lo del #6 y el #7 (listas se invalida y la identificación sale del hook del registro); el reintento no salta esas reglas.
- **El subagente se cancela a mitad de un reintento**: el frente queda no cubierto con el motivo de la cancelación, y no figura como cubierto.
- **Informe registrado antes de que termine un frente**: la cobertura de ese informe declara el frente como no cubierto.
- **Escalamiento con un frente caído**: la cobertura que llega al oficial también es la calculada por el código (FR-011).
- **Falla de todos los frentes**: el caso sigue pudiendo cerrarse con un informe que declara los cuatro frentes no cubiertos; las reglas del #7 siguen impidiendo habilitar (sin categoría determinada ni listas consultadas).
- **Recomendación con cobertura incompleta**: este ticket no añade restricciones a la recomendación por cobertura; las del #7 se mantienen (ver Supuestos).

## Requirements *(mandatory)*

### Functional Requirements

**Error estructurado (US2)**

- **FR-001**: Cada frente que no queda cubierto DEBE producir un error estructurado con, como mínimo: el frente, el tipo de error, un mensaje en español, lo que alcanzó a obtener (los resultados válidos, con su contenido y sus metadatos de fuente y fecha separados, tal como los entregó la pasarela) y si es reintentable.
- **FR-002**: El tipo de error DEBE distinguir, como mínimo: error de la fuente (con el tipo que dio la pasarela), terminación anómala del subagente, subagente sin consultas, resultado con forma inválida, consulta incompleta (listas sin el comercio o sin el representante), frente rechazado por falta de datos y frente cancelado. El plan fija la lista cerrada.
- **FR-003**: Que un error sea reintentable DEBE decidirlo el código con una regla fija, no el modelo. Un indicador ausente o inválido cuenta como no reintentable. El plan fija la tabla de cada tipo, que DEBE respetar estas dos reglas:
  - un frente que se ejecutó y falló es reintentable solo si todos sus errores reales vienen de la fuente y la fuente los declaró reintentables;
  - el rechazo de listas porque el registro todavía no se ha iniciado, o porque su delegación se rechazó, sigue siendo reintentable, como hoy (`test_delegacion.py`, los dos tests de `listas` con rechazo reintentable). Ese rechazo no lanza al subagente; volver a pedir listas cuando el registro termine es una delegación nueva y no consume el límite de reintentos de FR-007.
- **FR-004**: Un bloqueo de un hook de las reglas (#7) NO DEBE contarse como error del frente ni afectar a si es reintentable.

**Política de reintento (US3)**

- **FR-005**: El sistema DEBE permitir volver a ejecutar, con la misma entrada, un frente cuyo último resultado fue un error reintentable. Hoy una delegación repetida con la misma entrada devuelve lo guardado; ese comportamiento se mantiene para los frentes terminados y para los errores no reintentables.
- **FR-006**: Un frente cuyo último error no es reintentable NO DEBE volver a ejecutarse con la misma entrada; el coordinador recibe el mismo error estructurado y queda un evento de reintento denegado.
- **FR-007**: Los reintentos de cada frente DEBEN tener un límite fijado en el código y documentado como protección, no como mecanismo de control del ciclo (principio III), igual que `max_turns` en el #6 y `MAX_CIERRES_IMPEDIDOS` en el #7. Agotado el límite, no se lanza otro intento y queda un evento.
- **FR-008**: La política de reintento DEBE estar definida en el plan y ser determinista: dado el historial de un frente, el código decide si se permite otro intento. El plan decide si el reintento lo pide el modelo del coordinador (con el código como guarda) o lo hace el código de la delegación por sí mismo. En ambos casos, la regla de FR-005 a FR-007 la hace cumplir el código.
- **FR-009**: Cada reintento DEBE registrar un evento con el frente, el número de intento y el motivo, comprensible sin conocer el código. Un reintento que tiene éxito deja el frente cubierto sin borrar del registro de eventos la falla anterior.

**Cobertura (US1, US4)**

- **FR-010**: La cobertura del caso DEBE calcularla el código a partir del estado de los frentes: un frente está cubierto solo si terminó con normalidad; si no, figura como no cubierto con su motivo (no se delegó, rechazado, en curso, falló con su tipo de error, invalidado, cancelado). La cobertura es completa solo si los cuatro frentes están cubiertos.
- **FR-011**: La cobertura que queda registrada con `registrar_informe` y con `escalar_a_cumplimiento` DEBE ser la calculada por el código en el momento de la llamada. Si el modelo declara otra, prevalece la del código o la llamada se rechaza con el motivo; el plan elige el mecanismo. En ningún caso queda registrado un informe o un escalamiento que declare cubierto un frente que el código no da por cubierto.
- **FR-012**: El caso NO DEBE figurar como completo si algún frente no está cubierto. La propiedad que hoy dice si el caso es completo (#7) DEBE usar la misma cobertura calculada.
- **FR-013**: La falla de un frente NO DEBE detener ni modificar la ejecución ni el resultado de los demás frentes, salvo la dependencia ya existente de listas respecto del registro.
- **FR-014**: La cobertura calculada DEBE estar disponible en el estado del caso para la interfaz (#11) y la salida de la línea de comandos DEBE mostrarla por frente.

**Transversales**

- **FR-015**: Todo lo anterior DEBE verificarse con tests deterministas, sin llamar al modelo, incluido el caso de prueba (f) de extremo a extremo con un coordinador y subagentes simulados.
- **FR-016**: El comportamiento con el modelo real y `PASARELA_FALLA_NOTICIAS=1` DEBE comprobarse a mano una vez (quickstart), anotando qué frente se declaró no cubierto y si el coordinador reintentó.
- **FR-017**: Mensajes, eventos y documentación en español; solo datos ficticios; sin credenciales.
- **FR-018**: Fuera de alcance: el formato y el esquema del informe y que todo caso terminado quede registrado (#9), el contenido del resumen al oficial (#10), la presentación en el chat (#11) y la suite de los siete casos (#12).

### Key Entities *(include if feature involves data)*

- **Error de frente**: lo que el coordinador recibe cuando un frente no queda cubierto. Atributos: frente, tipo de error, mensaje, lo obtenido (resultados válidos con su fuente y su fecha), reintentable y, si el plan lo decide, el número de intento.
- **Cobertura de un frente**: cubierto o no cubierto; si no, el motivo y el tipo de error. Se deriva del estado del frente; no se guarda aparte de él.
- **Cobertura del caso**: la cobertura de los cuatro frentes y si es completa. Es la que se registra en el informe y en el escalamiento.
- **Historial de intentos de un frente**: cuántas veces se ejecutó con la misma entrada y el último error; es lo que la política de reintento consulta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las ejecuciones simuladas del caso (f), el informe se registra, declara noticias como no cubierto con su motivo y el caso no figura como completo.
- **SC-002**: En las pruebas de la política, el 100 % de los errores no reintentables se vuelve a ejecutar 0 veces, y ningún frente supera el límite de reintentos.
- **SC-003**: Recorriendo todas las combinaciones de situación de los cuatro frentes, 0 informes o escalamientos quedan registrados con una cobertura que declare cubierto un frente no cubierto, y la cobertura es completa solo en la combinación con los cuatro terminados.
- **SC-004**: El 100 % de las formas de fallo enumeradas en FR-002 produce un error estructurado con los cinco datos de FR-001.
- **SC-005**: Con el modelo real y la caída de noticias activa, la analista identifica qué frente quedó sin cubrir y por qué leyendo solo la respuesta final y los eventos, sin abrir el código.
- **SC-006**: Ningún test llama al modelo; la suite completa y ruff pasan, y los casos de los tickets #6 y #7 siguen en verde.

## Assumptions

- Depende del #6 (estado del caso, delegación, eventos y la forma actual del error `frente_no_terminado`) y del #7 (hooks de `registrar_informe` y `escalar_a_cumplimiento`, y la propiedad de caso completo). El #8 parte de lo que ya existe: el error estructurado con `reintentable` y `obtenido` lo introdujo el #6 y aquí se completa y se formaliza.
- La pasarela ya devuelve errores estructurados con `reintentable` (#5); solo `servicio_no_disponible` es reintentable, y `PASARELA_FALLA_NOTICIAS` se lee en cada llamada, así que un reintento con la caída activa vuelve a fallar.
- «Reintento» significa volver a ejecutar un frente con la misma entrada. Delegar con otra entrada es una delegación nueva, como en el #6.
- **Decisión confirmada por la analista**: este ticket no impide recomendar `habilitar` por tener la cobertura incompleta. Las reglas del #7 ya lo impiden cuando falta listas o la categoría; con noticias caídas, la recomendación queda a criterio del coordinador y el informe declara la cobertura incompleta.
- **Decisión confirmada por la analista**: la cobertura registrada con `escalar_a_cumplimiento` sigue la misma regla que la del informe (FR-011), porque el principio V exige que el resumen al oficial declare la cobertura alcanzada. El resto del contenido del resumen es del #10.
- **Decisión confirmada por la analista**: un frente que se ejecutó y falló solo es reintentable si la fuente lo declara; una terminación anómala o una excepción del subagente no lo son. La excepción es el rechazo de listas antes del registro, que sigue siendo reintentable (FR-003).
- El límite de reintentos y el mecanismo de FR-011 los fija el plan.
- Que todo caso terminado quede registrado con `registrar_informe` es del #9; aquí se verifica con un coordinador simulado que sí lo registra.
- La regla I.4 (fuente y fecha en cada afirmación del informe) se delega al #9.
