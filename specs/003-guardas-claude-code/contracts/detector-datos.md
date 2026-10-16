# Contrato: `detector_datos.py`

Módulo de funciones puras que usan `guarda_datos.py` y `test_revision_repositorio.py`
(FR-005 a FR-007). Decisiones en [research.md](../research.md) (R11).

## Interfaz

```text
buscar(texto: str) -> list[Hallazgo]
Hallazgo = (tipo: "tarjeta" | "nit" | "cedula" | "credencial", linea: int)
```

- No devuelve el valor encontrado ni su posición dentro de la línea, solo el tipo y la
  línea.
- Es determinista y no lee archivos ni el entorno.

## Definiciones

En todas, "límite" significa que el valor no está precedido ni seguido de una letra, un
dígito o `_`.

### Tarjeta

- Entre 13 y 19 dígitos, todos seguidos o en grupos separados por un único espacio o un
  único guion.
- El primer dígito es 2, 3, 4, 5 o 6.
- La cadena de dígitos pasa la validación de Luhn.
- Con límite a ambos lados, y sin un dígito al otro lado de un separador (no forma parte
  de un número más largo).
- No cuenta la parte decimal de un número: no puede ir precedido de un dígito seguido de
  `.` o `,` (`(?<!\d[.,])`). Por ejemplo, las cifras tras el punto de `0.4111…` no
  son una tarjeta (corrección de la revisión de la parada B).

### NIT

- Forma con guion: 9 dígitos, seguidos o con puntos de miles (`ddd.ddd.ddd`), luego `-` y
  un dígito, con límite. El dígito final es el DV válido de la DIAN para esos 9 dígitos.
- Forma sin guion: la palabra `NIT` (sin distinguir mayúsculas), opcionalmente seguida de
  `:`, `No.` o `#`, y a continuación 10 dígitos seguidos cuyo último dígito es el DV
  válido de los 9 primeros.

### Cédula

- Una palabra de contexto, sin distinguir mayúsculas salvo `CC`, que va siempre en
  mayúsculas:
  - `cédula` o `cedula`, opcionalmente seguida de `de ciudadanía`;
  - `C.C.`;
  - `CC`, como palabra completa;
  - `documento de identidad`;
  - `identificación` o `identificacion`.
- A continuación, a 20 caracteres como máximo y solo con espacios, `:`, `No.`, `N°`, `#`
  o `número` en medio, un número de 6 a 10 dígitos, seguidos o con puntos de miles, con
  límite.
- Si el número va precedido de `$`, no cuenta.

### Credencial

| Familia | Forma |
|---------|-------|
| GitHub | `ghp_`, `gho_`, `ghu_`, `ghs_` o `ghr_` seguido de 20 o más caracteres `[A-Za-z0-9]`; o `github_pat_` seguido de 20 o más caracteres `[A-Za-z0-9_]` |
| Anthropic | `sk-ant-` seguido de 20 o más caracteres `[A-Za-z0-9_-]` |
| AWS | `AKIA` seguido de exactamente 16 caracteres `[A-Z0-9]`, con límite |
| Clave privada | una línea `-----BEGIN ` + palabras en mayúsculas opcionales + `PRIVATE KEY-----` |

## Exclusiones (FR-006)

- `XX-YY-NNNN` (por ejemplo `CO-TV-0001`): no coincide con ningún patrón, porque tiene
  4 dígitos y letras.
- `$80.000.000`: no es una tarjeta (los puntos no son separadores de tarjeta), no es un
  NIT (no tiene 9 dígitos con guion) y no es una cédula (va precedido de `$` y no tiene
  palabra de contexto).
- Marcas de tiempo en milisegundos (13 dígitos que empiezan por 1), identificadores de
  GitHub (10 a 12 dígitos sin contexto), hashes y valores de `uv.lock`: no cumplen
  prefijo, longitud o límite.
- Un prefijo de credencial sin la longitud mínima (`ghp_` en la documentación) no cuenta.

## Casos de prueba mínimos (en `test_detector_datos.py`)

Los valores positivos se generan en la prueba:

- Decimales: con semilla fija, ningún `repr(random.random())` produce un hallazgo.
- Tarjeta: se calcula el dígito de Luhn para prefijos 2–6 y longitudes 13, 16 y 19, con
  y sin separadores. Se comprueba que el mismo número con un dígito cambiado no
  coincide, ni con prefijo 1.
- NIT: se calcula el DV de la DIAN; con un DV erróneo no coincide.
- Cédula: con cada palabra de contexto coincide; sin contexto o con `$`, no.
- Credencial: prefijo más cadena aleatoria de la longitud mínima; con un carácter menos,
  no coincide.
- Permitidos: el mensaje de ejemplo del enunciado ([docs/enunciado.md](../../../docs/enunciado.md)),
  `CO-TV-0001`, `$80.000.000` y una marca de tiempo en milisegundos actual.
