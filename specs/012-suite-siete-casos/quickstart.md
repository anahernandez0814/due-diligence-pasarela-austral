# Quickstart: Suite de los siete casos (#12)

Comandos y resultados esperados. El contrato está en
[contracts/suite-e2e.md](contracts/suite-e2e.md) y las estructuras en [data-model.md](data-model.md).

## Q1. Grupo determinista, sin clave (SC-003, SC-006)

```bash
uv run pytest
uv run ruff format --check . && uv run ruff check .
```

- Todo en verde. Ningún test `e2e` seleccionado: aparecen como «deselected».
- Menos de 5 minutos. Se anota el tiempo medido (antes del ticket: 4711 tests, 264 s).
- Lo mismo con la clave definida: `uv run pytest` sigue sin ejecutar los tests `e2e`.

## Q2. Grupo e2e sin clave (US2-3)

Con `ANTHROPIC_API_KEY` sin definir y sin archivo de entorno (o renombrándolo durante la prueba):

```bash
uv run pytest -m e2e -rs
```

- Los siete tests salen «skipped». Con `-rs`, el motivo es el mensaje de `comprobar_credencial`.
- No se crea ningún caso y no se llama al modelo. Coste 0.

## Q3. Grupo e2e con el modelo real (SC-001, SC-004): como máximo dos ejecuciones

```bash
uv run pytest -m e2e -rs
```

- Los siete casos pasan.
- El resumen final trae una línea por caso con su coste y su duración, más el total.
- Se anotan en `tasks.md` y en el README:
  - **Ejecución 1**: fecha, tiempo total, coste total y casos que fallaron, con el motivo.
  - **Ejecución 2**, si hace falta: lo mismo.
- Si un caso falla, se repite solo ese caso (no cuenta como ejecución completa):
  `uv run pytest -m e2e -rs -k caso_e`.
- Si el servicio limita la tasa, se repite con `PASARELA_E2E_PARALELO=3` y se anota.
- **Resultado (T027, 2026-10-19)**: 7 de 7 en 85 s y 1,10 USD, en la primera ejecución.
- `resultados/` no cambia: `git status` limpio tras la ejecución.

## Q4. Interrupción de la interfaz (FR-008), opcional y con el modelo

Con el modo de demostración, que es el caso (e):

```bash
PASARELA_MODO_DEMO_HOOKS=1 uv run streamlit run src/due_diligence/chat.py
```

1. Enviar el mensaje del caso (e).
2. Pulsar «Stop» en cuanto aparezca el indicador «Bloqueado por la regla I.1».

Resultado esperado:
- el script se detiene en segundos, no al terminar el turno;
- el turno queda en el historial como interrumpido;
- la entrada vuelve a estar habilitada y el turno no se repite solo;
- no hay ninguna consulta de listas en la traza.

Si se omite, lo cubren los tests deterministas de R9; se anota como no ejecutado.

**Ejecuciones de la analista** (2026-10-19):

| Ejecución | Cuándo pulsó «Stop» | Resultado |
|-----------|---------------------|-----------|
| 1 | Después del bloqueo de I.1 | El turno ya había terminado solo: no hubo nada que cortar. |
| 2 | Después del bloqueo de I.1 | Igual que la 1: el turno terminó solo. |
| 3 | **Antes** del bloqueo de I.1 | El turno **se cortó** (el bloqueo no llegó a dibujarse), pero al pulsar «Rerun» **el mismo turno arrancó otra vez**, con delegaciones nuevas, y volvió a gastar. **Defecto real, corregido** en `chat.py` (R9, «Lo que encontró la Q4»). |

**Lo esperado tras la corrección**, con «Stop» pulsado antes del bloqueo (desviación D1):
- el turno se corta en el siguiente evento, no al instante;
- el contenedor «El coordinador está trabajando…» queda congelado hasta pulsar «Rerun»;
- tras el «Rerun», el turno aparece en el historial como interrumpido y **no se repite**: no hay
  delegaciones nuevas;
- el siguiente mensaje abre un caso nuevo, con el aviso «El turno anterior se interrumpió; se inició
  un caso nuevo.» (opción A).

La analista repite la Q4 después de esta corrección.

## Q5. Correcciones

- `uv run pytest src/due_diligence/test_sesion_simulada.py -k fuente`: las noticias simuladas por
  defecto llevan «Diario Ficticio del Sur».
- `specs/011-interfaz-chat/tasks.md`: T046 marcada.
- `DECISIONES.md`: una sola entrada nueva, la del #12.
