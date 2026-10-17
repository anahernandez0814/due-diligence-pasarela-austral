# Contrato: herramienta `delegar_frente`

Servidor MCP **en proceso** `delegacion` (`create_sdk_mcp_server`), nombre completo de la herramienta
para el coordinador: `mcp__delegacion__delegar_frente`. Es la **única** vía de delegación (FR-002).

## Registro de la herramienta

- Anotación `readOnlyHint=True`: sin ella el SDK ejecuta las llamadas de un mismo turno una tras otra
  y no hay solape *(medido, research R4)*. Un test comprueba la anotación.
- Se construye **por caso** con una referencia al `Caso` (estado, eventos, ejecutor): no hay estado de
  módulo (FR-014).

## Entrada

| Campo | Tipo | Obligatorio | Uso |
|-------|------|-------------|-----|
| `frente` | `registro` \| `listas` \| `noticias` \| `categoria` | sí | frente a delegar |
| `identificador` | texto | según el frente | registro y noticias |
| `nombre` | texto | según el frente | registro y noticias, si no hay identificador |
| `categoria` | texto | solo `categoria` | riesgo de categoría |

Como en el servidor del #5, los parámetros se validan **dentro** de la herramienta y no por el esquema,
para devolver el error de este contrato en español. El código toma de la entrada **solo** los campos que
el frente necesita (data-model, tabla de frentes); los demás se ignoran, no se reenvían.

## Comportamiento

1. **Valida** `frente` y los datos del frente. Falta algo → `frente_rechazado`, error no
   reintentable que nombra el dato (nunca se inventa un valor).
2. **`listas` espera al registro**: si el registro está en curso, la llamada **espera** a que termine
   (evento `frente_fin` del registro) antes de empezar; si el registro no se delegó, `rechazado`. Con
   el registro terminado:
   - sin **coincidencia única** (varias, ninguna o resultado inválido) → `frente_rechazado`, error no
     reintentable; el coordinador **no elige** una coincidencia (FR-013);
   - con coincidencia única, el contexto es `estado.comercio` (comercio y representante, tal como los
     devolvió el registro, **sin pasar por el modelo**): van **del estado al prompt del subagente de
     listas**. Que el nombre que el subagente consulta coincida con el del estado **no lo comprueba este
     ticket**: lo hará un hook `PreToolUse` del #7, junto con I.1 (research R13, punto 7). Sin
     representante, se consulta solo al comercio y el resultado lo declara (FR-005).
3. **Registra** `delegacion` y, al lanzar al subagente, `frente_inicio` con el contexto.
4. **Ejecuta** al subagente con el ejecutor del caso. Mientras tanto otras llamadas pueden correr.
   En `listas`, al terminar **comprueba en `estado.consultas`** que hay una consulta por el comercio y,
   si hay representante, otra por el representante, comparando los nombres con `igual()` de
   `servidor_mcp.normalizar` (y los identificadores con `igual_identificador`), **no con igualdad
   exacta**. Si falta alguna, el frente queda `no_terminado` con el motivo («falta la consulta del
   representante» o «del comercio»). Esto comprueba que se hicieron las dos consultas; que el nombre
   sea exactamente el del estado lo comprueba el hook del #7 (research R13.7).
5. **Registra** `frente_fin` con la terminación clasificada, guarda el `ResultadoFrente` en el estado y
   actualiza la situación del frente (`terminado` o `no_terminado`).
6. **Responde** al coordinador con el resultado (abajo).

Un frente ya delegado en este caso **no se vuelve a ejecutar** si está `en_curso` o `terminado`: la
llamada repetida devuelve el resultado guardado (o espera al que está en curso). Reintentar un frente
`no_terminado` es del #8.

## Respuesta

Éxito (el frente terminó con terminación normal):

```json
{
  "frente": "registro",
  "situacion": "terminado",
  "resultados": [{"herramienta": "consultar_registro_mercantil", "resultado": "coincidencias",
                  "hechos": ["…"], "metadatos": {"fuentes": ["…"], "fecha": "AAAA-MM-DD"}}],
  "resumen": "texto corto del subagente, solo informativo"
}
```

- `resultados` reproduce, **tal cual**, el JSON de cada consulta del subagente (contenido y metadatos
  separados). El coordinador lo lee; el estado guarda lo mismo.
- En `listas` hay una entrada por consulta: la del comercio y, si hay, la del representante, cada una
  con el nombre consultado.

Terminación no normal o frente no iniciado, como error estructurado:

```json
{"error": true, "tipo": "frente_no_terminado | frente_rechazado | entrada_invalida",
 "mensaje": "Texto en español.", "reintentable": false,
 "obtenido": {"frente": "noticias", "resultados": []}}
```

`obtenido` conserva lo que el subagente alcanzó a recoger (puede ir vacío). `reintentable` es `false` para `frente_rechazado` y `entrada_invalida`. En `frente_no_terminado`, si una consulta devolvió el error estructurado de la pasarela (por ejemplo `servicio_no_disponible` de noticias, que es reintentable), se **propaga su `reintentable`** y se conserva el error en `obtenido`; si no hubo error estructurado (terminación anómala, consulta que falta), es `false`. **No se fija un valor**: la política de reintento es del #8.

## Garantías que comprueban los tests

- La herramienta está anotada `readOnlyHint`.
- Tres llamadas simultáneas a `registro`, `noticias` y `categoria` se solapan en el tiempo.
- `listas`, pedida junto a `registro` o antes, empieza **después** del fin del registro.
- `listas` recibe en su prompt el comercio y el representante **del estado**, aunque el modelo pase
  otros datos. (Que el subagente consulte exactamente esos nombres es del #7.)
- Sin coincidencia única, `listas` no se ejecuta y no hay `frente_inicio` de `listas`.
- Una llamada con un campo de otro frente no lo reenvía al subagente.
- Un frente repetido no lanza dos subagentes.
- Si el subagente de `listas` consulta solo al comercio o solo al representante, el frente queda
  `no_terminado` con el motivo; las mayúsculas, tildes y la forma jurídica no cuentan como diferencia.
- Un error estructurado de la pasarela queda en la `Consulta` y su `reintentable` llega al coordinador.
