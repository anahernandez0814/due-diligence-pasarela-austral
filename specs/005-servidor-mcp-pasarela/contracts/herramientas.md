# Contrato: herramientas del servidor `pasarela`

Servidor MCP por stdio, nombre `pasarela`. En Claude Code las herramientas se llaman
`mcp__pasarela__<herramienta>`. Toda herramienta devuelve un `CallToolResult` cuyo `content` es
el JSON de abajo (texto) y cuyo `structured_content` es el mismo objeto (R2).

## Forma común

**Éxito** (`is_error: false`):

```json
{
  "resultado": "coincidencias | sin_coincidencias | ...",
  "hechos": [
    {"contenido": {"...": "..."}, "metadatos": {"fuente": "...", "fecha": "AAAA-MM-DD"}}
  ],
  "metadatos": {"fuentes": ["..."], "fecha": "AAAA-MM-DD"}
}
```

- `contenido` nunca lleva `fuente` ni `fecha`, y `metadatos` nunca lleva contenido (R9).
- `sin_coincidencias`: `hechos` vacío y `metadatos` presentes (FR-010).
- La `fecha` es la `fecha_corte` de la fuente consultada (R8), no el reloj.

**Error** (`is_error: true`):

```json
{
  "error": true,
  "tipo": "entrada_invalida",
  "mensaje": "Texto en español.",
  "reintentable": false,
  "obtenido": {}
}
```

Tipos y reintento: tabla de `data-model.md`. Una búsqueda sin resultados **no** es un error.

## Validación de la entrada (R2)

El SDK 2.3.0 rechaza un argumento ausente o de tipo incorrecto **antes** de entrar a la
herramienta, con texto de pydantic en inglés y sin estructura. Para que el error sea el de este
contrato, **todos los parámetros se declaran opcionales y sin tipo estricto**
(`Annotated[Any, Field(description=...)] = None`) y la herramienta valida dentro:

- **Parámetro ausente o vacío**: en las herramientas de consulta, `entrada_invalida`; en
  `registrar_informe` y `escalar_a_cumplimiento`, `campos_obligatorios_ausentes` con **todos** los
  `campos_faltantes`.
- **Tipo incorrecto** (por ejemplo, un número donde va un texto): `entrada_invalida`, en español,
  no reintentable, con el nombre del parámetro y el tipo esperado.
- **El tipo esperado va en la descripción de cada parámetro**, porque el esquema que ve el
  cliente no lo lleva. Las tablas de entrada de abajo son la fuente.

## `consultar_registro_mercantil`

- **Entrada**: `nombre` **o** `identificador` (exactamente uno; con los dos o con ninguno,
  `entrada_invalida`). El texto se normaliza (R3) y debe tener al menos 3 caracteres.
- **Coincidencia**: por `identificador`, exacta. Por `nombre`, el texto normalizado contenido en
  el nombre normalizado.
- **Respuesta**: `resultado` es `coincidencias` o `sin_coincidencias`. Por cada comercio, los
  hechos van **agrupados por comercio**:

```json
{"contenido": {"identificador": "CO-RF-0006", "nombre": "Ferretería Río Fino SAS",
               "fecha_constitucion": "2016-03-14", "estado": "activo",
               "representante_legal": {"nombre": "…", "identificador": "PE-0006"}},
 "metadatos": {"fuente": "Registro Mercantil Ficticio del Sur", "fecha": "2026-09-30"}}
```

  Un comercio que está en las dos fuentes produce **un hecho por fuente**. Si difieren, ambos se
  devuelven y ninguno se marca como elegido; el orden es por identificador y luego por fuente.
- **Descripción** (texto fijo):
  > Busca un comercio en el registro mercantil por nombre o por identificador. Devuelve, por
  > cada fuente registral, la existencia, la fecha de constitución, el representante legal y el
  > estado. Si el nombre coincide con varios comercios devuelve TODOS: no elige uno ni indica
  > cuál es el correcto; la decisión es de quien consulta, con el identificador. Si dos fuentes
  > registrales difieren, devuelve ambos valores con su fuente. No consulta listas restrictivas
  > ni noticias, y no devuelve la categoría de negocio.

## `consultar_listas_restrictivas`

- **Entrada**: `tipo` (`comercio` o `persona`) y `nombre` **o** `identificador` (exactamente
  uno).
- **Coincidencia**: nombre completo normalizado igual, o identificador igual, entre entradas del
  mismo `tipo`. Nunca parcial.
- **Respuesta**: `coincidencias` (un hecho por lista que coincide, con el nombre de la lista y su
  fuente) o `sin_coincidencias`.
- **Descripción**:
  > Verifica un comercio o una persona (por ejemplo, el representante legal) contra las listas
  > restrictivas. Hay coincidencia solo por nombre completo idéntico (sin distinguir mayúsculas
  > ni tildes) o por identificador, nunca parcial. Una mención en noticias NO es una coincidencia
  > en listas restrictivas: eso lo responde `buscar_noticias`. Debe llamarse con el
  > identificador de un comercio ya identificado de forma unívoca en el registro mercantil.

  La última frase es una guía; el servidor no la impone (R10, FR-017). La garantiza el hook del
  ticket #7.

## `buscar_noticias`

- **Entrada**: `nombre` **o** `identificador` (exactamente uno).
- **Coincidencia**: nombre completo normalizado igual, o identificador igual, entre las entidades
  mencionadas por cada noticia (R3).
- **Respuesta**: `coincidencias` (un hecho por noticia: titular, url; metadatos con la fuente y la
  fecha de la noticia) o `sin_coincidencias`.
- **Error**: con `PASARELA_FALLA_NOTICIAS=1` (leída en cada llamada, R5), `servicio_no_disponible`,
  `reintentable: true`.
- **Descripción**:
  > Busca menciones de un comercio o una persona en un corpus de noticias. Una mención NO es
  > una coincidencia en listas restrictivas y no impide ni autoriza nada por sí sola. Si el
  > servicio no responde devuelve un error reintentable: entonces el frente de noticias queda
  > sin cubrir y no debe presentarse como completo.

## `consultar_riesgo_categoria`

- **Entrada**: `categoria` (texto). Se compara normalizada (R3).
- **Respuesta**: `resultado: "categoria_conocida"` con un hecho `{categoria, nivel}`
  (`alto`, `medio` o `bajo`), o `resultado: "categoria_desconocida"` con la lista de categorías
  conocidas y **sin nivel**.
- **Descripción** (las categorías conocidas se generan desde `categorias.json`):
  > Devuelve el nivel de riesgo (alto, medio o bajo) de una categoría de negocio, que aporta
  > quien consulta; el registro mercantil no la devuelve. Categorías conocidas: {lista}. El
  > nivel es alto exactamente para apuestas, criptoactivos, suplementos dietarios y venta de
  > medicamentos. Para una categoría desconocida no inventa un nivel: lo declara. No decide la
  > habilitación ni escala el caso.

## `registrar_informe`

- **Entrada** (todas obligatorias):

| Campo | Contenido |
|-------|-----------|
| `comercio` | `{identificador, nombre}` |
| `recomendacion` | texto no vacío |
| `hallazgos` | objeto `frente → {contenido, fuente}`; ningún hallazgo sin fuente |
| `cobertura` | texto o lista no vacíos: frentes cubiertos y frentes sin cubrir |

- **Respuesta**: `resultado: "informe_registrado"` y `contenido.id` (`INF-xxxxxxxx`).
- **Error**: `campos_obligatorios_ausentes`, no reintentable, con `campos_faltantes`.
- **Descripción**:
  > Registra el informe de due diligence con su recomendación, sus hallazgos por frente con la
  > fuente de cada uno y la cobertura alcanzada. Es uno de los dos canales de decisión.
  > No valida reglas de negocio ni decide: guarda lo que recibe. Si falta un campo
  > obligatorio devuelve un error no reintentable que lo nombra.

## `escalar_a_cumplimiento`

- **Entrada** (todas obligatorias): `comercio`, `hallazgos`, `cobertura`, `causa_escalamiento`
  y `accion_recomendada`, con la forma de arriba.
- **Respuesta**: `resultado: "caso_escalado"` y `contenido.id` (`ESC-xxxxxxxx`).
- **Error**: `campos_obligatorios_ausentes`, no reintentable, con `campos_faltantes`.
- **Descripción**:
  > Pasa el caso a un oficial de cumplimiento con un resumen estructurado y autosuficiente: el
  > oficial no tiene acceso a la conversación. Es uno de los dos canales de decisión. Se escala
  > por coincidencia en listas restrictivas o por categoría de alto riesgo, nunca por una
  > mención en noticias. No emite una recomendación de habilitación.

## Garantías que comprueban los tests

- El servidor lista exactamente estas seis herramientas.
- Ninguna herramienta lanza una excepción hacia el cliente: todo fallo es un error estructurado.
- Ninguna respuesta marca una coincidencia como elegida.
- Las descripciones contienen las frases de la constitución (R10).
- Las respuestas de éxito y de «sin coincidencias» llevan `metadatos` con `fuentes` y `fecha`.
