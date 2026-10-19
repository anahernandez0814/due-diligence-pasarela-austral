# Quickstart: validación del #14

Todo desde la raíz del repositorio, en la rama `014-documentacion-entrega`. Nada lee `.env`.

## Q1. Tests de la documentación y de la puerta

```bash
uv run pytest test_documentacion.py .claude/hooks/test_agentes_skills.py plugins -q
uv run ruff check . && uv run ruff format --check .
```

Esperado: todo en verde. El test del límite imprime las líneas medidas si falla.

## Q2. «Inicio rápido» en un clon limpio (cronometrado)

En una carpeta temporal fuera del repositorio, sin `.venv`:

```bash
git clone --branch 014-documentacion-entrega <ruta de esta copia> clon && cd clon
# seguir solo el «Inicio rápido» del README, con cronómetro
```

- Sin crear `.env`: `uv run pytest src` en verde; el chat se detiene con el mensaje de la
  clave (comprobado sin gastar API).
- La analista repite el recorrido con su clave y anota el tiempo total (SC-001).

## Q3. .zip y revisión del historial

Con los comandos de `docs/entrega.md`, sobre un clon de esta rama:

- el .zip lista `.git/`, `specs/` y `.specify/memory/`, ningún archivo excluido, y pesa ≤ 50 MB;
- las dos revisiones de credenciales terminan con 0 hallazgos y sin imprimir valores.

El .zip definitivo se genera después del merge, desde `main` en GitHub (lista de entrega).

## Q4. Suite completa

```bash
uv run pytest
```

Esperado: todo en verde (de 4 a 6 min en Windows).

## Q5. Pendiente de la analista

- Cronometrar el «Inicio rápido» (SC-001).
- Completar el enlace del video y revisar la frase de visibilidad.
- Recorrer la lista de `docs/entrega.md` tras el merge.
