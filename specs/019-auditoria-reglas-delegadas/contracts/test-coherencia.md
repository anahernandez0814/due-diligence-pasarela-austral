# Contrato: test de coherencia de los archivos de la puerta

Cumple FR-013 y SC-004 ([research.md](../research.md), R4). Vive en
`.claude/hooks/test_agentes_skills.py`, junto al código que ya prueba esos cuatro archivos.

## Función

```text
seccion(cuerpo: str, encabezado: str) -> str
```

- Busca la línea `## <encabezado>` y devuelve el texto hasta el siguiente encabezado de nivel 2
  (`## `) o el final del cuerpo.
- Normaliza: colapsa cualquier secuencia de espacios, tabuladores y saltos de línea en un solo
  espacio y recorta los extremos. Así, el ajuste de líneas de un archivo no produce falsos
  fallos, pero una palabra distinta sí.
- Si el encabezado no existe, falla con un mensaje que nombra el archivo.

## Pruebas

| Prueba | Qué exige | Falla si |
|--------|-----------|----------|
| bloque de cobertura igual | `Qué cuenta para la cobertura` existe en los dos agentes y las dos skills y es igual en los cuatro | falta en alguno o difiere |
| aplicabilidad igual | `Cuándo aplica una regla` existe en el agente y la skill del auditor y es igual | falta o difiere |
| `uv.lock` es referencia | en el bloque, `uv.lock` aparece en «Son referencia y no cuentan» y no en «Cuentan» | aparece como archivo que cuenta |
| la función detecta diferencias | con textos sintéticos: dos bloques que difieren en una palabra no son iguales; dos que difieren en espacios o saltos de línea sí | la función no distingue o distingue de más |
| la delegación exige número | el bloque de aplicabilidad contiene «con su número» y «no es delegarla» | falta alguna de las dos frases |
| delegar no exime de conservar | el bloque contiene «no de conservar» y «borra o debilita» | falta alguna |

Los mensajes de fallo nombran los archivos que difieren. Los tests existentes no se editan,
salvo ampliar la lista `REFERENCIA` con `uv.lock` (R5).

## Límites

- Garantiza que el texto **está escrito igual**; no que el modelo lo interprete bien (R6: lo
  comprueba el quickstart).
- No compara el bloque con un texto canónico: la fuente de verdad son los propios archivos
  entre sí (FR-013).
