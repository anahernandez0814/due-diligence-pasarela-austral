---
paths:
  - "**/test_*.py"
---

# Convenciones de pruebas

- **Junto al módulo**: cada `test_*.py` va en la misma carpeta que el módulo que prueba
  (`src/…/x.py` → `src/…/test_x.py`; `.claude/hooks/x.py` → `.claude/hooks/test_x.py`).
- **Solo datos ficticios** (constitución, principio VII): comercios, personas, noticias,
  listas y documentos inventados, con identificadores de formato propio como
  `CO-TV-0001`. Ningún dato real en tests, fixtures ni salidas esperadas.
- **Valores con forma real, construidos al ejecutar**: una tarjeta, un NIT, una cédula o
  una credencial nunca se escriben literales en el test. Se generan en la prueba: dígito
  de Luhn calculado sobre un prefijo, dígito de verificación de la DIAN calculado,
  prefijo de credencial concatenado con caracteres aleatorios. Las guardas bloquean
  escribirlos y la revisión del repositorio falla si aparecen.
- **pytest y ruff**: `uv run pytest` recoge `src/` y `.claude/hooks/`; el código se
  formatea con ruff.
- **Casos obligatorios** de la constitución (principio X), que DEBEN pasar en la entrega
  final y en el ticket de la suite de pruebas:
  - (a) comercio en categoría de alto riesgo que va a un oficial;
  - (b) comercio de bajo riesgo sin hallazgos con recomendación de habilitación;
  - (c) representante legal con coincidencia en listas restrictivas;
  - (d) dos comercios con nombres casi idénticos en el registro;
  - (e) intento de consultar listas sin identificación unívoca, que debe ser bloqueado;
  - (f) falla del servicio de noticias, con el informe entregado y la cobertura
    incompleta declarada;
  - (g) dos fuentes con fechas de constitución distintas.
