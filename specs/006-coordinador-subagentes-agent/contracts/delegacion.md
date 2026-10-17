# Contrato: herramienta `delegar_frente`

Servidor MCP **en proceso** `delegacion` (`create_sdk_mcp_server`), nombre completo de la herramienta
para el coordinador: `mcp__delegacion__delegar_frente`. Es la **única** vía de delegación (FR-002).

## Registro de la herramienta

- Anotación `readOnlyHint=True`: sin ella el SDK ejecuta las llamadas de un mismo turno una tras otra
  y no hay solape *(medido, research R4)*. Un test comprueba la anotación.
- Se construye **por caso** con una referencia al `Caso` (estado, eventos, ejecutor): no hay estado de
  módulo (FR-014).
- La lógica vive en la clase `Delegador(estado, eventos, ejecutor, opciones_subagente)`
  (`src/due_diligence/delegacion.py`): `delegar(entrada)` hace lo descrito abajo, `herramienta` es la
  `SdkMcpTool` con la anotación y `servidor()` el servidor en proceso `delegacion`. Si falta un dato del
  frente, el contexto (`contexto.construir_contexto`) lanza `FrenteRechazado` y el delegador lo traduce
  en un `frente_rechazado`.

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
   (evento `frente_fin` del registro) antes de empezar; si el registro está sin iniciar (o fue rechazado), `listas` se rechaza con `reintentable: true` y el mensaje «delega primero el registro y vuelve a pedir listas cuando termine» (pasa con llamadas del mismo turno, que llegan con 0,1 a 0,3 s de diferencia); el coordinador la repite cuando el registro termine. Con
   el registro terminado:
   - sin **coincidencia única** (varias, ninguna o resultado inválido) → `frente_rechazado`, error **no reintentable** (a diferencia del rechazo por registro sin iniciar); el coordinador **no elige** una coincidencia (FR-013);
   - con coincidencia única, el contexto es `estado.comercio` (comercio y representante, tal como los
     devolvió el registro, **sin pasar por el modelo**): van **del estado al prompt del subagente de
     listas**. Que el nombre que el subagente consulta coincida con el del estado **no lo comprueba este
     ticket**: lo hará un hook `PreToolUse` del #7, junto con I.1 (research R13, punto 7). Sin
     representante, se consulta solo al comercio y el resultado lo declara (FR-005).
3. **Registra** `delegacion` y, al lanzar al subagente, `frente_inicio` con el contexto.
4. **Ejecuta** al subagente con el ejecutor del caso. Mientras tanto otras llamadas pueden correr.
   En `listas`, al terminar **comprueba en `estado.consultas`** que hay una consulta por el comercio y,
   si hay representante, otra por el representante, comparando el nombre completo con `igual()` de `servidor_mcp.normalizar` (y los identificadores con `igual_identificador`) y el **tipo** de cada consulta: `comercio` para el comercio y `persona` para el representante. `igual()` es **estricto**: ignora mayúsculas, tildes y puntuación, pero no la forma jurídica ni acepta un nombre parcial, porque la pasarela busca por el nombre completo (otra forma sería un falso negativo y no cuenta). Si falta alguna, el frente queda `no_terminado` con el motivo («falta la consulta del
   representante» o «del comercio»). Esto comprueba que se hicieron las dos consultas; que el nombre
   sea exactamente el del estado lo comprueba el hook del #7 (research R13.7).
5. **Registra** `frente_fin` con la terminación clasificada, guarda el `ResultadoFrente` en el estado y
   actualiza la situación del frente (`terminado` o `no_terminado`).
6. **Responde** al coordinador con el resultado (abajo).

Un frente `en_curso` no se lanza dos veces: la llamada repetida espera al que corre. Con el frente ya
terminado o no terminado, se compara la **entrada** (el contexto construido) con la anterior: si es
**idéntica**, devuelve el resultado guardado y registra `delegacion_repetida`; si es **distinta**, vuelve
a ejecutar el frente (`delegacion` con «otra entrada», nuevo `frente_inicio` y `frente_fin`). Lo hallado
en la validación real: el coordinador corrigió la categoría y recibió el resultado anterior. Si el registro se vuelve a ejecutar y el comercio del estado cambia, `listas` ya terminado (o no terminado)
pasa a `no_terminado` con el motivo «el comercio del registro cambió; vuelva a delegar listas», con su evento
`frente_fin`, y su entrada se olvida para que el reintento se ejecute (caso (c): sin esto, el resultado era
de otro comercio). Un `listas` en curso no se invalida (research R13.10). La política
de cuándo reintentar un frente `no_terminado` es del #8.

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
- `listas`, pedida en el mismo turno que `registro` y después de él, empieza **después** del fin del registro. Pedida antes de que el registro se delegue, se rechaza con `reintentable: true` y mensaje «delega primero el registro…»; al repetirla cuando el registro termina, se ejecuta.
- Los rechazos de `listas` por varias coincidencias, ninguna o un registro que no terminó son `reintentable: false`.
- `listas` recibe en su prompt el comercio y el representante **del estado**, aunque el modelo pase
  otros datos. (Que el subagente consulte exactamente esos nombres es del #7.)
- Sin coincidencia única, `listas` no se ejecuta y no hay `frente_inicio` de `listas`.
- Una llamada con un campo de otro frente no lo reenvía al subagente.
- Un frente repetido no lanza dos subagentes.
- Si el subagente de `listas` consulta solo al comercio o solo al representante, el frente queda
  `no_terminado` con el motivo; las mayúsculas y las tildes no cuentan como diferencia, pero **la forma jurídica sí** (`igual()` es estricto) y el tipo de la consulta debe corresponder a la entidad (`comercio` o `persona`).
- Un error estructurado de la pasarela queda en la `Consulta` y su `reintentable` llega al coordinador.
