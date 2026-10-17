# Quickstart: validar el coordinador y los subagentes

Prerrequisitos: `uv sync` hecho, Claude Code abierto en la raíz del repositorio. Q1, Q3, Q4 y Q7 son
automáticos y no usan modelo. **Q2, Q5 y Q6 usan el modelo real** (unos centavos) y se corren a mano;
necesitan una sesión de Claude Code iniciada o `ANTHROPIC_API_KEY` en el entorno. **Nunca se abre el
archivo de variables de entorno desde Claude Code** (guarda de secretos).

Contratos: [delegacion](contracts/delegacion.md), [caso](contracts/caso.md). Modelo de datos:
[data-model.md](data-model.md).

## Q1. Suite y formato (automático)

```text
uv sync
uv run ruff format .
uv run ruff check .
uv run pytest
```

Esperado: todo en verde, con los tests nuevos de `src/due_diligence/` y la suite existente.

## Q2. Aislamiento del entorno de desarrollo (manual, modelo real; R2)

```text
uv run python -m due_diligence.sondeo_aislamiento
```

El sondeo usa las **mismas opciones** que el coordinador (`opciones_base`), pide un `Glob` inofensivo y
pregunta por las instrucciones del proyecto; repite con `setting_sources=["project"]` como control.
Esperado, en una tabla impresa:

| Opciones | Skills del repo | Agentes del repo | Eventos de hooks | ¿Conoce `CLAUDE.md`? |
|----------|-----------------|------------------|------------------|----------------------|
| `setting_sources=[]` (las del paquete) | ninguna | solo integrados | 0 | no |
| `["project"]` (control) | `siguiente-ticket` | `auditor-cumplimiento`, `revisor-codigo` | ≥ 1 | sí |

Falla (código de salida ≠ 0) si con `[]` aparece cualquier skill o agente del repositorio, algún evento
de hooks o contenido del `CLAUDE.md`. Resultado de la investigación: R2.

## Q3. Herramientas por agente (automático, más una comprobación manual)

Automático: `test_coordinador.py` compara la lista **exacta** de `allowed_tools` y `disallowed_tools` de
cada agente con la tabla de R3, y que permitidas + no permitidas de la pasarela suman siempre las seis.
Manual, dentro del sondeo de Q2 (opción `--herramientas`): la lista inicial de herramientas que ve cada
agente en la sesión real es **exactamente** la de la tabla, sin las ajenas.

## Q4. Fin del ciclo (automático, más una comprobación manual)

Automático: `test_terminacion.py` con mensajes de resultado simulados: `end_turn` → normal;
`max_tokens` → anómala; `error_max_turns` con `stop_reason="tool_use"` → límite de seguridad;
«listo» con `max_tokens` → anómala; `refusal` e `is_error` → anómala; un `ResultError` simulado.
`test_sin_control_propio.py` comprueba que el código no tiene `while` ni contadores en el coordinador y
el ejecutor, que `max_turns` solo está en `configuracion.py` y que no se compara texto de mensajes.

Manual: `uv run python -m due_diligence.sondeo_aislamiento --limite` ejecuta una consulta con
`max_turns=1` y debe imprimir `LIMITE_SEGURIDAD` y el evento correspondiente (R5: `subtype=error_max_turns`,
`stop_reason=tool_use`, y `ResultError` capturada sin romper el caso).

## Q5. Caso de ejemplo completo (manual, modelo real)

```text
uv run python -m due_diligence "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren procesar ventas en línea de suplementos dietarios y estiman unos $80.000.000 mensuales. ¿Lo podemos habilitar esta semana?"
```

Esperado, leyendo **solo** el registro de eventos impreso (SC-006):

1. `caso_iniciado`, y tres `delegacion` seguidas: `registro`, `noticias` y `categoria`.
2. Los tres `frente_inicio` **antes** de cualquier `frente_fin` (solape; si salen en turnos distintos, el
   resultado es correcto pero serializado: se anota y se ajusta la instrucción, R4).
3. `frente_inicio` de `listas` **después** de `frente_fin` de `registro`.
4. En `listas`, dos consultas: `CO-TV-0001` (comercio) y su representante legal, con el nombre que
   devolvió el registro.
5. Cuatro frentes `terminado`, con terminación `NORMAL`, y la terminación del coordinador `NORMAL`.
6. Ningún intento de herramienta ajena; el coordinador no llamó a ninguna herramienta de fuentes.

Se anota en `DECISIONES.md` (6.2): duración total frente a la suma de frentes (un frente tarda ≈ 5 s,
R14) y el coste del caso (`total_cost_usd` del coordinador y de los subagentes), **en frío y en caliente**:
la primera ejecución de la hora paga la escritura en caché del coordinador (≈ 0,13 USD con Sonnet,
R14.3) y la segunda, no. Con esos números se confirma o se cambia el modelo del coordinador (R9).

## Q6. El entorno se carga solo desde el punto de entrada (automático)

`test_configuracion.py`: ningún módulo salvo `__main__.py` llama a `cargar_entorno`, el paquete no la
llama al importarse y los tests no dependen de variables de entorno del archivo. Q5 es el único
escenario que lo carga.

## Q7. Datos reales y secretos (automático)

`test_revision_repositorio.py` (de #3) recorre los archivos versionados: no debe encontrar nada en los
archivos nuevos. Los tests de este ticket usan solo los identificadores y nombres ficticios del #5.

## Criterios de salida

Q1, Q3, Q4, Q6 y Q7 en verde; Q2 y Q5 con la tabla y el registro de eventos esperados, anotados en
`tasks.md`; `DECISIONES.md` actualizado (modelos, coste medido, hallazgos de R2 a R5). La bitácora
6.2 la actualiza la analista desde otro chat, con los números que deja el resumen del implement.
