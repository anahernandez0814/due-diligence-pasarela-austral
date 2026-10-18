# Quickstart: validar los hooks de las reglas de negocio 1, 2 y 3

Guía de validación. Los detalles están en [contracts/hooks.md](contracts/hooks.md),
[data-model.md](data-model.md) y [research.md](research.md). Todo desde la raíz del repositorio
(Claude Code y los comandos, siempre en la raíz).

## Requisitos previos

```powershell
uv sync
```

- Las pruebas **no** llaman al modelo. Q4 y Q5 sí, y usan la sesión de Claude Code (sin clave ni `.env`).
- Q4 cuesta ≈ 0,01 USD (Haiku: mide el SDK, no el modelo). Q5 usa el producto real, que desde el #7 es
  Opus 5.5 en los cinco agentes: el doble por token que Sonnet 5.5, así que cada solicitud se estima en
  0,12 a 0,25 USD (0,06 USD medidos con Sonnet en el #6, más los turnos que añaden las devoluciones del cierre).

## Q1. Suite y formato

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest
```

**Esperado**: todo en verde, incluidos los tests del #6 adaptados.

## Q2. Los casos de prueba obligatorios con el caso completo (sin modelo)

```powershell
uv run pytest src/due_diligence/test_casos_reglas.py -v
```

**Esperado**, un test por caso con subagentes en sesiones simuladas y los hooks reales del caso:

| Caso | Qué comprueba |
|------|---------------|
| (a) | `habilitar` a un comercio de alto riesgo (suplementos dietarios) se rechaza; sin escalar no se acepta ni `no_habilitar`; tras escalar, `decide_cumplimiento` se acepta |
| (b) | bajo riesgo, sin hallazgos y con listas consultadas: `habilitar` se acepta, sin escalar y el `Stop` permite terminar |
| (c) | coincidencia del representante en listas: `habilitar` se rechaza, el `Stop` impide terminar, y tras escalar el informe `decide_cumplimiento` se acepta |
| (e) | listas con nombres casi idénticos en el registro (varias coincidencias): la delegación de listas y la consulta se bloquean y la fuente no se consulta |

## Q3. Reglas, hooks y reparto por agente

```powershell
uv run pytest src/due_diligence/test_reglas.py src/due_diligence/test_hooks.py src/due_diligence/test_hooks_sesiones.py src/due_diligence/test_estado_identificacion.py -v
```

**Esperado**:
- Las tablas de decisión de `reglas.py` (tipo, normalización, alto riesgo persistente, categoría
  determinada por la última consulta, causas vigentes, recomendación fuera del conjunto).
- Fallo cerrado: un hook que lanza una excepción deniega, bloquea el cierre o sella el libro; las salidas
  de los tres constructores tienen la forma del SDK.
- Reparto: el `Stop` solo en el coordinador; el hook de la consulta de listas solo en el subagente de
  listas; ningún `Stop` en un subagente.
- Sesiones separadas: lo que el hook del registro guarda lo ve el de listas, y dos casos no comparten nada.
- Fuente única: no existe `fijar_comercio` y `comercio` se deriva de `derivar_comercio` una sola vez.

## Q4. Sondeo con el SDK real (repetible)

```powershell
uv run python -m due_diligence.sondeo_hooks
```

**Esperado** (Haiku, servidor de la pasarela y una herramienta en proceso), con la salida de cada
experimento:
- `PostToolUse` recibe `tool_response` (texto en stdio, lista en proceso).
- Un error estructurado llega por `PostToolUseFailure`, no por `PostToolUse`.
- Una excepción en un hook **deja pasar** la acción (por eso se envuelven) y un `deny` bloquea y llega el motivo.
- Un `Stop` con `block` hace continuar al modelo, `stop_hook_active` pasa a `True` y `max_turns` cuenta cada devolución.

Si el SDK cambia (la versión está acotada a `<0.3`), el sondeo muestra qué dejó de cumplirse.

## Q5. Modo de demostración con el modelo real

```powershell
$env:PASARELA_MODO_DEMO_HOOKS = "1"
uv run python -m due_diligence "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren procesar ventas en línea de suplementos dietarios y estiman unos `$80.000.000 mensuales. ¿Lo podemos habilitar esta semana?"
Remove-Item Env:PASARELA_MODO_DEMO_HOOKS
```

Tres solicitudes, cada una con su resultado anotado en la validación:
1. La del ejemplo (alto riesgo): el modelo intenta `registrar_informe` con `habilitar`; el hook lo rechaza y el
   `Stop` impide cerrar hasta escalar. Los eventos muestran `modo_demostracion`, `bloqueo_regla` (I.3) y
   `escalamiento_registrado`.
2. Una con el nombre casi idéntico de dos comercios del registro (varias coincidencias): el modelo, sin la
   regla 3 en el prompt, puede intentar delegar `listas`; el hook de `delegar_frente` lo bloquea (I.1).
3. Una con un comercio de bajo riesgo sin hallazgos: no se bloquea nada y el informe `habilitar` se acepta.

**Esperado**: el bloqueo se ve en el chat como una herramienta con error y su motivo, y en los eventos. Si
el modelo no intenta la acción prohibida, la validación lo anota (no es un fallo del hook, es lo que hizo el
modelo) y los tests de Q2 son los que prueban la garantía.

## Q6. Sin el modo de demostración

Repetir la solicitud (1) sin la variable. **Esperado**: las instrucciones del coordinador incluyen la regla 3 y
la instrucción de escalar; no incluyen «No decidas la habilitación» ni la prohibición del #6; los hooks son
los mismos.

## Q7. Límite de devoluciones del cierre

```powershell
uv run pytest src/due_diligence/test_hooks.py -k "cierre" -v
```

**Esperado**: un coordinador simulado que insiste en terminar sin escalar recibe el motivo
`MAX_CIERRES_IMPEDIDOS` veces; a la siguiente se permite el cierre, el evento `cierre_sin_escalar` consta y
`Caso.completo` es `False`. El límite es menor que `MAX_TURNOS_SEGURIDAD`.

## Q8. Datos y credenciales

- La suite de revisión del repositorio (`test_revision_repositorio.py`, de #3) pasa: los tests y el sondeo no
  añaden datos con forma real ni credenciales.
- `git status` no muestra `resultados/` ni `.env`.
