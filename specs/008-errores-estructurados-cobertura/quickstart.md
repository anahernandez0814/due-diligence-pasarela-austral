# Quickstart: validación del ticket #8

Escenarios para comprobar que el ticket cumple la spec. Se ejecutan desde la raíz del repositorio,
en Windows con PowerShell. Contratos en [contracts/](contracts/); decisiones en
[research.md](research.md).

**Requisitos previos**: `uv sync`. La rama `008-errores-estructurados-cobertura` con la
implementación commiteada. Q5 y Q6 usan el modelo real con las credenciales de la sesión de Claude
Code; ninguno lee `.env`.

## Q1. Formato, lint y suite completa

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest
```

Esperado:
- ruff limpio y todos los tests en verde, incluidos los del #6 y el #7 (SC-006);
- se anota el número de tests frente a la línea base.

## Q2. Caso (f) de extremo a extremo, simulado

```powershell
uv run pytest src/due_diligence/test_casos_cobertura.py -v
```

Esperado (SC-001):
- el informe que guarda la pasarela simulada trae la cobertura del código, con noticias «no
  cubierto» y la primera línea «Cobertura incompleta: 3 de 4»;
- el coordinador simulado había declarado «completa»;
- los eventos muestran `frente_reintento`, `reintento_denegado` (si el guion insiste) y
  `cobertura_sustituida`;
- `caso.completo` es `False`.

Comprobación de mutación: sin el reemplazo de la cobertura en el hook, la prueba falla.

## Q3. Política de reintento y error estructurado

```powershell
uv run pytest src/due_diligence/test_reintentos.py src/due_diligence/test_delegacion.py src/due_diligence/test_hooks.py -v
```

Esperado (SC-002, SC-004, y R6 en `test_hooks.py`):
- con una excepción simulada en el cálculo de la cobertura, el escalamiento pasa con
  `COBERTURA_NO_CALCULADA`, el libro queda sellado y `caso.completo` es falso; el informe, en
  cambio, se deniega;
- un error reintentable se ejecuta exactamente 2 veces y uno no reintentable, 1;
- un tercer pedido se deniega con `reintentable: false`;
- cada causa de la tabla de `data-model.md` produce el error con sus campos;
- los dos tests de listas antes del registro siguen dando `reintentable: true`;
- ningún error contiene el texto de una excepción simulada.

## Q4. Cobertura en todas las combinaciones

```powershell
uv run pytest src/due_diligence/test_cobertura.py -v
```

Esperado (SC-003): en las 5⁴ combinaciones de situación de los cuatro frentes, la cobertura es
completa solo con los cuatro `terminado`, y la cobertura registrada nunca declara cubierto un
frente que no lo está.

## Q5. Sondeo repetible con el modelo real (Haiku, ≈ 0,02 USD)

```powershell
uv run python -m due_diligence.sondeo_hooks
```

Esperado:
- todas las mediciones `coinciden` y el código de salida es 0;
- las nuevas son:
  - (e): `updatedInput` reemplaza la entrada completa; con solo la cobertura, no se fusiona;
  - (f): un reintento y dos devoluciones del `Stop` dan `num_turns=5`;
  - G3: la pasarela guarda la cobertura de `HooksDelCaso`, no la que declaró el modelo.
- Si algo `difiere`, se aplica el plan B de R1 (`deny` con motivo) y se anota.

## Q6. Caso (f) con el modelo real (Opus 5.5, ≈ 0,15 a 0,30 USD)

```powershell
$env:PASARELA_FALLA_NOTICIAS = "1"
uv run python -m due_diligence "Necesito el due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, categoría ropa y accesorios. ¿Lo podemos habilitar?"
Remove-Item Env:PASARELA_FALLA_NOTICIAS
```

Se anota en la validación:
1. Si el coordinador reintentó noticias, cuántas veces, y si recibió `reintento_denegado`.
2. El bloque «Cobertura:» de la salida: noticias no cubierto y la primera línea «incompleta».
3. El evento `cobertura_sustituida` y si la cobertura declarada por el modelo se sustituyó.
4. «Caso completo: no».
5. «Turnos del coordinador: N de 30». Se anota N. El 15 de R2 es la estimación del peor caso, no
   un límite: si N pasa de 15, se anota qué turnos sobraron. Solo es fallo si el caso termina en
   `error_max_turns`.
6. Si la respuesta final al analista dice qué frente quedó sin cubrir y por qué (SC-005). La
   analista lo valora leyendo solo la respuesta y los eventos.

## Q7. Sin la caída (contraste)

La misma solicitud de Q6 sin la variable.

Esperado:
- cobertura completa y «Caso completo: sí»;
- ningún evento `frente_reintento`;
- recomendación `habilitar`, el caso (b) del #7.
