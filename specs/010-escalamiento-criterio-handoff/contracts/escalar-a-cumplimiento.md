# Contrato: `escalar_a_cumplimiento` (#10)

Sustituye la forma del #5 (`hallazgos` como `{contenido, fuente}` por frente). Las decisiones están en `research.md` R5, R6 y R8.

## Entrada que envía el coordinador

```json
{
  "hallazgos": {
    "registro": [{"texto": "…", "fuente": "Registro Mercantil Ficticio del Sur", "fecha": "2026-09-30"}],
    "listas": [{"texto": "Sin coincidencias del comercio ni del representante.", "fuente": "…", "fecha": "…"}],
    "noticias": [],
    "categoria": [{"texto": "Categoría de alto riesgo.", "fuente": "…", "fecha": "…"}]
  },
  "accion_recomendada": "Revisar la documentación del origen de fondos antes de decidir."
}
```

El coordinador puede enviar también `comercio`, `cobertura`, `causa_escalamiento` y `conflictos`: el hook los sustituye por los del código.

## Lo que llega a la pasarela (entrada completa con `updatedInput`)

```json
{
  "comercio": {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS", "verificado": true},
  "hallazgos": {"…": "tal como los envió el coordinador"},
  "cobertura": ["Cobertura completa: 4 de 4 frentes cubiertos.", "registro: cubierto.", "…"],
  "causa_escalamiento": ["categoría de alto riesgo"],
  "accion_recomendada": "…",
  "conflictos": {"resumen": "Sin conflictos entre las fuentes registrales.", "lista": []}
}
```

Sin causas vigentes (FR-003), `causa_escalamiento` lleva una línea fija por cada motivo que se cumple (`MOTIVOS_SIN_CAUSA`: cobertura incompleta, categoría no determinada, mención en noticias, conflicto entre fuentes y comercio no identificado; research R5).

## Rechazos en el hook (`PreToolUse`, deny)

El motivo es el JSON `resumen_rechazado`, con la forma de `informe_rechazado` del #9:

```json
{
  "error": true,
  "tipo": "resumen_rechazado",
  "mensaje": "No se escala el caso. … Problemas de forma o de fuente: hallazgos.listas[0].fuente: …. Corrige y vuelve a escalar.",
  "reintentable": false,
  "motivos": [{"regla": "V", "texto": "…"}],
  "problemas": [{"ruta": "hallazgos.listas[0].fuente", "texto": "…"}]
}
```

Cada motivo lleva la regla que lo causa (`null` si no es de ninguna, como el de D2); cada problema, su ruta y su texto. El `mensaje` junta los dos en un texto. Lo construye `denegar_decision`, el mismo del informe.

| Situación | Motivo | Regla del evento |
|-----------|--------|------------------|
| Espera del identificador, sin sello ni coincidencia en listas | `MOTIVO_ESPERA_IDENTIFICADOR` | `V` |
| Espera del nombre, sin sello ni coincidencia en listas | `MOTIVO_ESPERA_NOMBRE` | `V` |
| Bajo riesgo sin hallazgos comprobado | `MOTIVO_SIN_CAUSA` | `V` |
| Sin comercio identificado ni pedido (D2 del plan) | `MOTIVO_SIN_COMERCIO_ESCALAMIENTO`: pide delegar primero el registro | — |
| Forma, fuente no consultada o frente cubierto sin afirmación | uno por problema en `problemas` | `I.4` |

Cada rechazo deja `bloqueo_regla` con la acción `escalar_a_cumplimiento`.

## Lo que no se deniega

- **Una excepción en el hook**: `degradar_escalamiento` deja pasar la entrada con la cobertura `COBERTURA_NO_CALCULADA`, los conflictos `no_calculados()` y la causa «fallo de un hook de verificación», y sella el caso.
- **El caso sellado**: no se validan fuentes ni reglas (D4 del plan); se admite incluso durante la espera del identificador (excepción de FR-016). Lleva solo las seis claves del esquema: lo que el coordinador añada fuera de él no llega a la pasarela.
- **Una coincidencia en listas durante la espera del registro** (excepción por I.2 de FR-016): se valida como siempre, con el comercio pedido (`verificado: false`). Sin comercio identificado ni pedido, va `COMERCIO_NO_IDENTIFICADO` (`"no identificado"` en el identificador y el nombre, `verificado: false`).

## Pasarela (`decisiones.escalar_a_cumplimiento`)

1. **Primer nivel**: si faltan `comercio`, `hallazgos`, `cobertura`, `causa_escalamiento`, `accion_recomendada` o `conflictos`, devuelve `campos_obligatorios_ausentes`, con **todos** en `campos_faltantes`. No es reintentable.
2. **Forma**: `validar_resumen` da `entrada_invalida`, con **todos** los `problemas`. No es reintentable.
3. **Válido**: guarda en `escalamientos/ESC-….json` y devuelve `caso_escalado` con un hecho `{id}`.

La pasarela no conoce el caso: no comprueba fuentes, causas ni esperas.

## Confirmación (`PostToolUse` / `PostToolUseFailure`)

- **`PostToolUse` con `caso_escalado`**: añade a `libro.escalamientos` el `Escalamiento` pendiente de ese `tool_use_id` y deja `escalamiento_registrado` con el id, las causas, el resumen de la cobertura y el número de afirmaciones.
- **`PostToolUseFailure`, o una respuesta que no es `caso_escalado`**: descarta lo pendiente y deja `consulta_fallida`.
