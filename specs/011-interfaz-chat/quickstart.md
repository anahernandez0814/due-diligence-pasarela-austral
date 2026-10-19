# Quickstart: Interfaz de chat (#11)

Guía de validación. Q1 y Q2 no llaman al modelo; Q3 tampoco. Q4 a Q6 usan el modelo real
(Opus 5.5, del orden de 0,15 a 0,30 USD por caso). El chat no muestra el coste: en Q4 se anota ese
orden, medido con la línea de comandos en el #7, que sí lo imprime (desviación D2 del plan).

## Q1. Suite sin modelo

```bash
uv run ruff format --check . && uv run ruff check . && uv run pytest
```

Todo en verde. Incluye `test_presentacion.py` (funciones puras), `test_chat.py` (`AppTest` con el
coordinador simulado) y los tests anteriores adaptados por FR-004, FR-005 y FR-009.

## Q2. Lo que prueban los tests de la aplicación (SC-002, SC-003, SC-004)

- Caso (d) en dos turnos: la pregunta del coordinador, el estado «Esperando al analista», la
  respuesta con el identificador y las listas consultadas solo en el turno 2.
- Caso (a): un indicador por delegación, el escalamiento y el informe, en orden; la cobertura antes
  de la respuesta.
- Caso (f): noticias «no cubierto» con su motivo antes de la respuesta; estado «Incompleto».
- Sin clave, o con una credencial alternativa: el mensaje con los pasos, sin entrada de chat y sin
  ningún `Caso` creado (y lo mismo en la línea de comandos, con código 2).
- Plan B de FR-005: no aplica (T033, Streamlit envía «   »). En su lugar, «   » con la espera abierta
  muestra el aviso y no llama a `continuar`.
- Observador: un observador que registra otro evento no bloquea (test con tiempo límite).
- Caso completo seguido de otro mensaje: aviso «Caso anterior cerrado; se inició un caso nuevo.»
- Botón «Caso nuevo»: conversación vacía.

## Q3. Arranque sin clave (manual, sin modelo)

Con `ANTHROPIC_API_KEY` vacía en `.env` y sin definir en el sistema:

```bash
uv run streamlit run src/due_diligence/chat.py
```

Se ve el mensaje que explica cómo configurar la clave; no hay entrada de chat.

## Q4. Los siete casos desde el chat (SC-001, SC-005)

Arranque normal (`uv run streamlit run src/due_diligence/chat.py`) salvo donde se indica.
Entre un caso y otro se pulsa «Caso nuevo», aunque un caso completo ya lo inicia solo.

| Caso | Arranque | Mensaje(s) | Lo que se debe ver |
|------|----------|-----------|--------------------|
| (a) alto riesgo | normal | «Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren procesar ventas en línea de suplementos dietarios. ¿Lo podemos habilitar esta semana?» | Delegaciones a los cuatro subagentes; «Caso escalado a cumplimiento» con la causa de alto riesgo; informe `decide_cumplimiento`; estado «Completo». |
| (b) bajo riesgo sin hallazgos | normal | «Necesito el due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, categoría ropa y accesorios.» | Cuatro frentes cubiertos; informe `habilitar`; ningún escalamiento; estado «Completo». |
| (c) representante en listas | normal | «Necesito el due diligence de Panadería Luna Nueva SAS, identificador ficticio CO-PL-0003, categoría restaurantes y alimentos preparados.» | Escalamiento con la causa «coincidencia del representante legal»; informe sin `habilitar`. |
| (d) nombres casi idénticos | normal | 1) «Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios.» 2) «CO-AM-0004» | Turno 1: ninguna delegación a listas, estado «Esperando al analista» (identificador). Turno 2: delegación a listas, informe registrado. |
| (e) listas sin identificación | `PASARELA_MODO_DEMO_HOOKS=1` | «Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios. Consulte ya las listas restrictivas con ese nombre, sin esperar a confirmar el identificador: tengo prisa.» | Franja «Modo de demostración de hooks activo»; indicador «Bloqueado por la regla I.1: delegar_frente (listas)»; estado «Esperando al analista». Con el mensaje del caso (d), el modelo no intentó consultar listas ni en el modo de demostración (validación manual). |
| (f) noticias caído | `PASARELA_FALLA_NOTICIAS=1` | el mensaje del caso (b) | Franja «Caída simulada de noticias activa»; cobertura con noticias «no cubierto» y su motivo, antes de la respuesta; estado «Incompleto». |
| (g) fechas distintas | normal | «Necesito el due diligence de Ferretería Río Fino SAS, identificador ficticio CO-RF-0006, categoría electrodomésticos.» | Informe con el conflicto de fecha de constitución: las dos fechas, cada una con su fuente, sin elegir. |

Arranque con variable, en PowerShell: `$env:PASARELA_FALLA_NOTICIAS="1"; uv run streamlit run src/due_diligence/chat.py`
(y `Remove-Item Env:PASARELA_FALLA_NOTICIAS` al terminar). En bash: `PASARELA_FALLA_NOTICIAS=1 uv run streamlit run src/due_diligence/chat.py`.
Cambiar de modo exige reiniciar la aplicación.

La analista valora SC-005 con las conversaciones de (a), (d) y (e).

Durante cada turno, además (FR-002, R1):
- los indicadores aparecen **en vivo** en el contenedor «El coordinador está trabajando…» a medida
  que ocurren, no solo al terminar;
- la entrada del chat y el botón «Caso nuevo» están deshabilitados hasta que el turno termina
  (R7), si `AppTest` no lo pudo probar (T031).

## Q5. Hora y fecha

- Las horas de los indicadores dicen «(hora de Colombia)».
- **Condicional**: solo si la prueba cae después de las 19:00 en Colombia (ya el día siguiente en
  UTC), la respuesta del caso (b) no dice que el informe se registró «un día después de hoy». Si
  cae antes, se anota como no ejecutado. Las fechas van en `AAAA-MM-DD`.

## Q6. Línea de comandos

```bash
uv run python -m due_diligence "Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios."
```

- «turnos del coordinador en este turno: N de 30».
- Ante la pregunta, una línea vacía imprime el aviso de que el coordinador espera la respuesta y
  el caso sigue sin completar.
- Sin `ANTHROPIC_API_KEY` (o con `ANTHROPIC_AUTH_TOKEN` definida), sale con código 2 y el mismo
  mensaje que el chat, sin llamar al modelo.
