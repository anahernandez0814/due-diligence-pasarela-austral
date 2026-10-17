# Modelo de datos: Servidor MCP de la pasarela

Todos los archivos están en `src/servidor_mcp/datos/`, marcados `"ficticio": true`, con un
`"aviso"` en español y una `"fecha_corte"` (R8). Los nombres son inventados; los dominios,
`.example`.

## Entidades

### Fuente registral (`registro_rmf_sur.json`, `registro_rufe.json`)

| Campo | Descripción |
|-------|-------------|
| `ficticio`, `aviso` | Marca y aviso en español. |
| `fuente` | Nombre de la fuente (`Registro Mercantil Ficticio del Sur` o `Registro Único Ficticio de Empresas`). |
| `fecha_corte` | Fecha (`AAAA-MM-DD`) de los datos de la fuente. Es la `fecha` de los metadatos. |
| `comercios[]` | Lista de comercios de esa fuente. |

**Comercio de una fuente**: `identificador` (`CO-XX-NNNN`), `nombre`, `fecha_constitucion`,
`estado` (`activo`, `suspendido` o `cancelado`) y `representante_legal`
(`{nombre, identificador}` con `PE-NNNN`).

La **categoría de negocio no está aquí** (ajuste 4): la aporta el analista.

### Lista restrictiva (`listas_restrictivas.json`)

`listas[]`, cada una con `lista` (nombre), `fuente`, `fecha_corte` y `entradas[]`. Una entrada es
`{tipo: "persona"|"comercio", nombre, identificador}`. La coincidencia es por nombre completo
normalizado o por identificador (R3).

### Noticia (`noticias.json`)

`fuente`, `fecha_corte` y `noticias[]` con `id`, `titular`, `fecha`, `url` (`.example`) y
`menciona[]` (entidades por `{nombre, identificador}`). Se busca igual que en las listas.

### Categoría de negocio (`categorias.json`)

`categorias[]` con `nombre` y `nivel` (`alto`, `medio`, `bajo`), y `fuente` y `fecha_corte`.

| Nivel | Categorías |
|-------|------------|
| `alto` (exactamente estas) | apuestas, criptoactivos, suplementos dietarios, venta de medicamentos |
| `medio` | viajes y turismo, electrodomésticos |
| `bajo` | ropa y accesorios, restaurantes y alimentos preparados, tecnología y software, educación en línea |

### Informe (`<resultados>/informes/INF-xxxxxxxx.json`)

`id`, `registrado_en`, `comercio` (`{identificador, nombre}`), `recomendacion`, `hallazgos`
(`frente → {contenido, fuente}`) y `cobertura`. Un informe por llamada; no se sobrescribe.

### Caso escalado (`<resultados>/escalamientos/ESC-xxxxxxxx.json`)

`id`, `registrado_en`, `comercio`, `hallazgos`, `cobertura`, `causa_escalamiento` y
`accion_recomendada`.

### Error estructurado

| Campo | Descripción |
|-------|-------------|
| `error` | `true`. |
| `tipo` | `entrada_invalida`, `campos_obligatorios_ausentes`, `servicio_no_disponible`, `datos_no_disponibles`, `error_de_almacenamiento` o `error_interno`. |
| `mensaje` | Texto en español, sin repetir valores de entrada sensibles. |
| `reintentable` | `true` o `false`. |
| `obtenido` | Lo que se alcanzó a obtener (puede ir vacío). |
| `campos_faltantes` | Solo en `campos_obligatorios_ausentes`: nombres de todos los campos que faltan. |

| Tipo | Reintentable |
|------|--------------|
| `entrada_invalida` | no |
| `campos_obligatorios_ausentes` | no |
| `servicio_no_disponible` | **sí** (caída simulada de noticias) |
| `datos_no_disponibles` (archivo ausente o corrupto) | no |
| `error_de_almacenamiento` | no |
| `error_interno` | no |

## Mapa caso → dato

Los comercios son ficticios. El caso (e) y el (f) **no añaden datos**: reutilizan los de otros
casos.

| Caso | Qué reproduce | Datos | Cómo se ve en las herramientas |
|------|---------------|-------|--------------------------------|
| (a) alto riesgo a oficial | Tienda Verde SAS, `CO-TV-0001`, categoría **suplementos dietarios** (la nombra el analista) | `CO-TV-0001` en las dos fuentes registrales, con la misma fecha; **sin entradas en listas ni noticias** | registro: una coincidencia; listas y noticias: sin coincidencias; riesgo de «suplementos dietarios»: `alto`. El escalamiento sale solo de la categoría. |
| (b) bajo riesgo, sin hallazgos | Taller Aurora SAS, `CO-TA-0002`, categoría **ropa y accesorios** | `CO-TA-0002` en las dos fuentes, sin listas ni noticias | todo limpio; riesgo `bajo`; recomendación de habilitación. |
| (c) representante en listas | Panadería Luna Nueva SAS, `CO-PL-0003`; su representante legal, Ernesto Calderón Ibarra (`PE-0003`) | `PE-0003` aparece como **persona** en `Lista Restrictiva Ficticia A`; el comercio **no** figura en listas. **Es el representante de un comercio del registro**, no una persona suelta | registro devuelve `PE-0003` como representante; `consultar_listas_restrictivas(tipo=persona, identificador=PE-0003)` devuelve la coincidencia; el comercio por sí solo no. |
| (d) nombres casi idénticos | Almacén Mirador SAS (`CO-AM-0004`) y Almacén Mirador Norte SAS (`CO-AM-0005`) | los dos en el registro | buscar «almacén mirador» devuelve ambos; ninguno marcado como elegido. |
| (e) listas sin identificación unívoca | el nombre ambiguo del caso (d) | **sin datos nuevos** | el servidor, por sí solo, **no bloquea**: la consulta con ese nombre devuelve dos coincidencias. El bloqueo de listas sin identificación lo hace el hook del #7. Aquí se comprueba que el registro entrega la ambigüedad que el hook usa. |
| (f) falla de noticias | cualquier comercio, con `PASARELA_FALLA_NOTICIAS=1` | **sin datos nuevos** (se usa `CO-TV-0001`) | `buscar_noticias` devuelve `servicio_no_disponible`, reintentable; las otras cuatro herramientas funcionan. |
| (g) fechas distintas | Ferretería Río Fino SAS, `CO-RF-0006` | fecha de constitución `2016-03-14` en el Registro Mercantil Ficticio del Sur y `2017-09-02` en el Registro Único Ficticio de Empresas | una coincidencia con **dos hechos**, cada uno con su fuente; sin elegir. |

Datos adicionales, sin caso propio:

- **Mención sin lista** (US2, escenario 3): una noticia de `Diario Ficticio del Sur` menciona
  a `CO-AM-0005` (Almacén Mirador Norte SAS), que no está en listas.
- **Categorías**: las nueve de la tabla anterior; cualquier otra devuelve `categoria_desconocida`.

## Reglas de validación

- Los identificadores de comercio cumplen `^CO-[A-Z]{2}-\d{4}$` y los de persona, `^PE-\d{4}$`.
- Ningún valor de los archivos tiene 6 o más dígitos seguidos.
- Cada comercio del caso (a), (b), (c) y (g) existe en las **dos** fuentes, con los mismos datos
  salvo la fecha de `CO-RF-0006`.
- Cada archivo tiene `ficticio: true`, `aviso` y `fecha_corte`.
- Los cuatro `alto` de `categorias.json` son exactamente los cuatro del enunciado.
