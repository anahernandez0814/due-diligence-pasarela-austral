# Contrato: lo que comprueba `test_documentacion.py`

Los tests leen archivos versionados; no llaman al modelo ni a la red. El de la revisión del
historial crea un repositorio git temporal.

| Test | Archivo | Comprueba | Requisito |
|------|---------|-----------|-----------|
| límite de páginas | `DECISIONES.md` | líneas impresas a 90 columnas (R1) ≤ 100 | FR-008, SC-002 |
| once necesidades | `DECISIONES.md` | una fila de tabla que empieza por `\| N \|` para N = 1…11 | FR-009, SC-003 |
| tickets trazados | `DECISIONES.md` | aparecen `#1`…`#13` y `#19` (con límite de palabra) | FR-009, SC-003 |
| sección del Agent SDK | `DECISIONES.md` | sus líneas no vacías ocupan entre 6 y 8 líneas impresas a 90 columnas (R1) | FR-010 |
| enlaces al detalle | `DECISIONES.md` → `docs/decisiones-detalle.md` | cada `docs/decisiones-detalle.md#ancla` existe según los slugs de GitHub (R3); al menos uno por fila de la tabla y por tema de «Flujo de trabajo» y de «Límites conocidos» | FR-012, SC-004 |
| sin pérdida | `docs/decisiones-detalle.md` | las líneas no vacías de `git show f9e82d6:DECISIONES.md` son subsecuencia ordenada; se omite sin git o sin el commit | FR-013, SC-004 |
| añadidos | `docs/decisiones-detalle.md` | aparecen `contexto_revision.py:160`, `revisor-codigo.md:67`, `T055`, `/pull/` y la nota de la espera de la categoría | FR-014 |
| inicio rápido | `README.md` | es la primera sección `##`; contiene en orden `uv python install 3.12`, `uv sync`, `.env.example`, `uv run pytest src`, `streamlit run` | FR-001 |
| contenido del README | `README.md` | los siete mensajes de los casos, el enlace al Project, la línea del video, `marketplace add`, `extraKnownMarketplaces` y «el repositorio y el GitHub Project son públicos» (cambio del 2026-10-19: antes pedía «el repositorio es privado y pide acceso», que ya no es cierto) | FR-004, FR-005 |
| lista de entrega | `docs/entrega.md` | los siete puntos del issue y los dos guiones | FR-017, FR-020, FR-021 |
| historial sin valores | bloques `revision-prefijos` y `revision-detector` de `docs/entrega.md` | en un repo temporal con una credencial generada al ejecutar, cada bloque la encuentra (commit y archivo) y la salida no contiene el valor | FR-019, SC-007 |

## Marcas de los bloques ejecutables de `docs/entrega.md`

Cada bloque va precedido de un comentario HTML que no se ve en GitHub:

```markdown
<!-- bloque: revision-prefijos -->
```bash
…
```
```

El test toma el primer bloque de código después de la marca. Los bloques usan solo `git`,
`xargs` y `uv run --no-project python`, y se ejecutan desde la raíz del repositorio con Git
Bash (en Windows) o bash.

## Instrucciones de cobertura (test existente)

`REFERENCIA` de `.claude/hooks/test_agentes_skills.py` gana `"docs/"`. Los tests
`test_las_instrucciones_listan_la_referencia_que_no_cuenta` y los de las viñetas comprueban
los cuatro textos sin cambiar su lógica.
