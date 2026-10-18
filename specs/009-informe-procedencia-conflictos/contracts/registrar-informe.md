# Contrato: `registrar_informe` (#9)

Sustituye el formato de hallazgos del #5 (`{frente: {contenido, fuente}}`). `escalar_a_cumplimiento`
no cambia en este ticket.

## Entrada

```json
{
  "comercio": {"identificador": "CO-RF-0006", "nombre": "Ferretería Río Fino SAS", "verificado": true},
  "hallazgos": {
    "registro": [
      {"texto": "El comercio figura activo.", "fuente": "Registro Mercantil Ficticio del Sur", "fecha": "2026-09-30"}
    ],
    "listas": [
      {"texto": "Sin coincidencias del comercio.", "fuente": "<fuente de la lista>", "fecha": "2026-09-15"}
    ]
  },
  "conflictos": {
    "resumen": "1 conflicto entre las fuentes registrales.",
    "lista": [
      {"dato": "fecha_constitucion", "valores": [
        {"valor": "2016-03-14", "fuente": "Registro Mercantil Ficticio del Sur", "fecha": "2026-09-30"},
        {"valor": "2017-09-02", "fuente": "Registro Único Ficticio de Empresas", "fecha": "2026-09-28"}
      ]}
    ]
  },
  "cobertura": ["Cobertura completa: 4 de 4 frentes cubiertos.", "registro: cubierto.", "…"],
  "recomendacion": "no_habilitar"
}
```

Las fechas y la fuente de listas del ejemplo son ilustrativas. Todos los datos son ficticios.

## Validación

| Capa | Comprueba | Si falla |
|------|-----------|----------|
| Hook `PreToolUse`, modo normal | Reglas del #7 (`evaluar_informe`: recomendación, escalamiento, I.2 e I.3 para `habilitar`), `validar_informe` y fuente consultada (FR-004) | `deny`; el motivo es el JSON `informe_rechazado` con **todos** los motivos y problemas (R3). Evento `bloqueo_regla` con `accion`. |
| Hook `PreToolUse`, caso sellado (R9) | `evaluar_informe_minimo`, `validar_informe` y fuente consultada | Igual. |
| Hook `PreToolUse`, aceptado | Pone `comercio`, `conflictos` y `cobertura` del código (R5) | `allow` con la entrada completa en `updatedInput`. Eventos `cobertura_sustituida` y `datos_sustituidos`. |
| Pasarela | `validar_informe` (forma) | Error `entrada_invalida`, no reintentable, con `problemas: [{ruta, texto}]`, o `campos_obligatorios_ausentes` con `campos_faltantes`. No guarda nada (FR-005). |

### Motivo del deny (R3)

```json
{"error": true, "tipo": "informe_rechazado",
 "mensaje": "No se registra el informe: … Corrige y vuelve a registrarlo.",
 "reintentable": false,
 "motivos": [{"regla": "I.2, I.3", "texto": "El caso requiere escalamiento a cumplimiento y aún no se ha escalado por: …"}],
 "problemas": [{"ruta": "hallazgos.listas[0].fuente", "texto": "La fuente no es ninguna de las consultadas para listas."}]}
```

## Respuesta de la pasarela (sin cambios)

`informe_registrado`, con un hecho `{"id": "INF-xxxxxxxx"}`, la fuente «Registro local de informes
(ficticio)» y la fecha UTC del registro. El documento guardado lleva `registrado_en` en UTC con su
desfase explícito (`+00:00`).

## Garantías

- Ningún informe guardado tiene una afirmación sin texto, fuente o fecha válida (pasarela).
- Ningún informe registrado por el coordinador cita una fuente que el caso no consultó para ese
  frente (hook).
- El comercio, los conflictos y la cobertura registrados son siempre los del código.
- Tras un fallo de hook solo se registra `decide_cumplimiento`, y únicamente después de escalar.
