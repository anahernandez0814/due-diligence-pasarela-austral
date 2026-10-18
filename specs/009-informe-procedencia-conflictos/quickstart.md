# Quickstart: validación del #9

Comprueba de extremo a extremo lo que el plan promete. Q1 y Q2 son deterministas y no llaman al
modelo; de Q3 a Q6 se usa el modelo real (FR-020) y se anotan los resultados en `tasks.md`. Todos
los comercios son ficticios. No se lee `.env`: la clave del modelo la pone la persona en su
entorno.

## Q1. Suite y formato

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest
```

Esperado: todo en verde. Los tests del #5 al #8 que fijaban el formato anterior de los hallazgos o
el cierre con sello se adaptan sin debilitarse (SC-006), y la tabla de cambios va en el PR.

## Q2. Casos deterministas del #9

```powershell
uv run pytest src/due_diligence/test_casos_informe.py src/due_diligence/test_conflictos.py src/due_diligence/test_informe.py src/servidor_mcp/test_informe.py -v
```

Esperado:
- **Caso (g)** (SC-002): con `CO-RF-0006`, el informe registrado tiene un conflicto
  `fecha_constitucion` con 2016-03-14 y 2017-09-02, cada uno con su fuente y su fecha, aunque el
  coordinador simulado no declare conflictos o declare uno inventado.
- **Validación** (SC-001): un informe con una afirmación sin fuente, sin fecha, con una fecha
  inválida o con una fuente no consultada se rechaza, y el motivo nombra todas las rutas.
- **Cierre** (SC-003): en las combinaciones de escalamiento (sí o no) e informe (ninguno, vigente o
  anterior a un cambio), el cierre solo se permite cuando está todo.
- **Informe vigente** (R7): un reintento que sale bien invalida el informe; uno que vuelve a
  fallar, no. Con el reintento y `registrar_informe` en el mismo mensaje, si el reintento termina
  entre el `PreToolUse` y el `PostToolUse`, el informe queda no vigente.
- **Presupuesto** (R8): `PRESUPUESTO_TURNOS_PEOR_CASO == 19 <= 30`.
- **Orden** (FR-012): con alto riesgo, el informe se rechaza hasta escalar.
- **Fallo de hook** (SC-004): con el sello, el informe se rechaza hasta escalar. Después solo pasa
  `decide_cumplimiento`, con los textos fijos, y el caso no figura como completo.
- **Registro caído**: con `PASARELA_FALLA_REGISTRO=1` simulado, el cierre exige el informe. Con un
  reintento disponible, el motivo dice «reintenta el registro o registra el informe»; con el
  reintento agotado, el motivo general. El comercio sale con `verificado: false`.
- **Limitación conocida**: un fin de turno con el comercio identificado y sin informe se bloquea.

## Q3. Caso (g) con el modelo real (Opus 5.5, ≈ 0,15 a 0,30 USD)

```powershell
uv run python -m due_diligence "Necesito el due diligence de Ferretería Río Fino SAS, identificador ficticio CO-RF-0006, categoría electrodomésticos. ¿Lo podemos habilitar?"
```

Se anota:
1. El bloque de conflictos de la salida: `fecha_constitucion` con los dos valores y sus dos fuentes.
2. Los eventos `cobertura_sustituida`, `datos_sustituidos` e `informe_registrado`, con el id del
   informe.
3. Si hubo un `bloqueo_regla [I.4]`: cuántos, su `accion` y si el coordinador corrigió el informe
   tras recibir el JSON `informe_rechazado` (riesgo residual 7).
4. El documento de `resultados/informes/<id>.json`: cada afirmación con fuente y fecha, los
   conflictos del código y `registrado_en` en UTC. Se cruza su hora con la del evento (FR-018).
5. «Turnos del coordinador: N de 30».

## Q4. Caso escalado con el modelo real

```powershell
uv run python -m due_diligence "Due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001, categoría suplementos dietarios."
```

Se anota:
- el orden de los eventos, `escalamiento_registrado` antes de `informe_registrado`;
- la recomendación `decide_cumplimiento`;
- si hubo un intento de informe antes de escalar, que tuvo que dejar un `bloqueo_regla` con el
  motivo de escalar.

## Q5. Registro caído con el modelo real (para la demo)

```powershell
$env:PASARELA_FALLA_REGISTRO = "1"
uv run python -m due_diligence "Necesito el due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, categoría ropa y accesorios. ¿Lo podemos habilitar?"
Remove-Item Env:PASARELA_FALLA_REGISTRO
```

Se anota:
1. Si el coordinador reintentó el registro y recibió `reintento_denegado`.
2. Que listas se rechazó por falta de comercio (I.1) y que noticias y categoría terminaron.
3. Cobertura: registro y listas no cubiertos; «Caso completo: no».
4. El informe: comercio con `verificado: false`; conflictos «No se pudieron comparar las fuentes
   registrales: el registro no respondió.»; recomendación distinta de `habilitar`.
5. Si el coordinador cerró sin informe y el `Stop` lo devolvió (`cierre_impedido`).

## Q6. Sondeo repetible (Haiku, ≈ 0,02 USD)

```powershell
uv run python -m due_diligence.sondeo_hooks
```

Esperado: todas las mediciones `coinciden`. G4 usa el formato nuevo del informe y la pasarela lo
acepta.

## Q7. Pasarela por el protocolo

```powershell
uv run pytest src/servidor_mcp/test_servidor.py -k informe -v
```

Esperado: por el protocolo MCP, un informe con una afirmación sin fuente devuelve `entrada_invalida`
con `problemas`, y uno válido devuelve `informe_registrado`.
