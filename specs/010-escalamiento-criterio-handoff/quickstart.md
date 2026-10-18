# Quickstart: validación del #10

Escenarios para comprobar el ticket de extremo a extremo. Los de Q1 y Q2 no llaman al modelo. Los Q3 a Q5 usan el modelo real (Opus 5.5, ≈ 0,15 a 0,30 USD cada uno) y se anotan en `tasks.md`. Las decisiones están en `research.md`. Los contratos, en `contracts/escalar-a-cumplimiento.md` y `contracts/continuacion-y-cierre.md`.

Requisitos: `uv sync` y Claude Code abierto en la raíz. Los casos con el modelo real usan la sesión de Claude Code, sin leer el archivo de entorno desde los tests.

## Q1. Suite y formato

```text
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

**Esperado**:
- todo en verde;
- los tests del #5 al #9 que cambian (forma de `escalar_a_cumplimiento`, `decide_cumplimiento` sin escalar, presupuesto de 19 a 21, limitación del `Stop` y escalamientos con comercio) se adaptan con igualdades exactas y van en la tabla del PR.

## Q2. Casos deterministas del #10

```text
uv run pytest src/due_diligence/test_casos_escalamiento.py -v
```

**Esperado**, con el `CoordinadorSimulado`:
- **(a)**: escalado con la causa «categoría de alto riesgo» y el informe `decide_cumplimiento`.
- **(b)**: el informe `habilitar` y 0 escalamientos. Un escalamiento se rechaza con `MOTIVO_SIN_CAUSA`.
- **(d), en dos turnos**:
  - el primero termina con `espera_analista`, sin consultas de listas, sin escalamiento ni informe;
  - el segundo, con `CO-AM-0005`, identifica al comercio, vuelve a delegar noticias (aparece N-0001), consulta listas del comercio y del representante y registra el informe vigente.
- **(d) con alto riesgo**: el primer turno termina igual y el escalamiento llega en el segundo.
- **Resúmenes incompletos**: un rechazo que nombra todos los campos o problemas.
- **Recorrido de SC-004**: 6 estados del registro por 3 de la categoría, con y sin causas. Hay espera exactamente en tres situaciones.

## Q3. Caso (a) con el modelo real

```text
uv run python -m due_diligence --sin-continuar "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren procesar ventas en línea de suplementos dietarios y estiman unos $80.000.000 mensuales. ¿Lo podemos habilitar esta semana?"
```

**Anotar**:
- el evento `escalamiento_registrado` y su causa;
- el informe `decide_cumplimiento` vigente;
- el archivo `resultados/escalamientos/ESC-….json`.

**Comprobación de SC-005**: la analista lee solo ese archivo y responde las cinco preguntas de US2-6.

## Q4. Caso (b) con el modelo real

```text
uv run python -m due_diligence --sin-continuar "Necesito el due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, categoría tecnología y software."
```

**Anotar**:
- que no hay ningún escalamiento;
- el informe `habilitar` vigente;
- «Caso completo: sí»;
- si el modelo intentó escalar: el `bloqueo_regla` con `MOTIVO_SIN_CAUSA`.

## Q5. Caso (d) con el modelo real, en dos turnos

```text
uv run python -m due_diligence "Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios."
```

**Primer turno, esperado**:
- la respuesta pide el identificador;
- «Esperando al analista: …»;
- sin consultas de listas, sin escalamiento ni informe.

**Segundo turno**: responder `CO-AM-0005` en la entrada estándar.

**Anotar** (FR-024):
- que en el segundo turno se consultaron listas;
- que se volvió a delegar noticias y aparece N-0001;
- el informe vigente;
- los turnos de cada consulta, que se comparan con el presupuesto de 21.

## Q6. Pasarela por el protocolo

```text
uv run pytest src/servidor_mcp/test_servidor.py -k escalar -v
```

**Esperado**:
- `escalar_a_cumplimiento` sin campos da `campos_obligatorios_ausentes` con todos los campos;
- con una afirmación mal formada da `entrada_invalida` con sus `problemas`;
- completo, da `caso_escalado`.
