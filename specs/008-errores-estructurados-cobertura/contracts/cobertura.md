# Contrato: cobertura calculada y cobertura registrada

Modelo en [data-model.md](../data-model.md); decisiones R1, R5 y R6 en
[research.md](../research.md). Amplía `specs/007-hooks-sdk-reglas/contracts/hooks.md`.

## `calcular_cobertura(estado) -> CoberturaCaso`

- Es una función pura: no escribe en el estado ni registra eventos.
- Los cuatro frentes siempre aparecen, en el orden de `Frente` (registro, listas, noticias,
  categoría).
- La cobertura es completa solo si los cuatro están cubiertos.

`CoberturaCaso.lineas()` devuelve la lista que se registra (la pasarela acepta texto o lista):

```text
línea 0: "Cobertura completa: 4 de 4 frentes cubiertos."
         | "Cobertura incompleta: N de 4 frentes cubiertos."
línea i: "<frente>: cubierto."
         | "<frente>: no cubierto; <motivo>[; <n> intentos]."
```

Los motivos están en español y no repiten nombres ni identificadores del comercio.

## Hooks del coordinador

| Herramienta | Hook | Comportamiento |
|-------------|------|----------------|
| `registrar_informe` | `PreToolUse` (`_informe_previo`, #7) | 1) Libro sellado → `deny`. 2) Reglas I.1 a I.3 que rechazan → `deny` (#7). 3) `tool_input` que no es un objeto → `deny` con `MOTIVO_ENTRADA_MALFORMADA`. 4) Si no, `allow` + `updatedInput` = `{**tool_input, "cobertura": cobertura.lineas()}` y el evento `cobertura_sustituida`. |
| `escalar_a_cumplimiento` | `PreToolUse` (`_escalar_previo`, **nuevo**) | **Nunca deniega.** 1) `tool_input` que no es un objeto → `permitir()` sin cambios (la pasarela lo rechazará). 2) Si no, `allow` + `updatedInput` con la cobertura del código y el evento `cobertura_sustituida`. No mira el sello del libro. |

- **Ante una excepción**:
  - `_informe_previo` va envuelto con `fallar_cerrado` (#7): se deniega la llamada y nunca pasa la
    cobertura del modelo.
  - `_escalar_previo` va envuelto con `degradar_escalamiento`, que no deniega:
    1. sella `libro.fallo_de_hook` y registra el evento `fallo_de_hook`, sin el texto de la
       excepción;
    2. si `tool_input` es un objeto, devuelve `allow` + `updatedInput` con la entrada completa y
       `cobertura = [COBERTURA_NO_CALCULADA]`;
    3. si no, devuelve `permitir()`.

    `COBERTURA_NO_CALCULADA` es el texto fijo del código: «No se pudo calcular la cobertura; debe
    tratarse como incompleta.». Con el sello, `Caso.completo` es falso y los `PreToolUse` de las
    reglas, incluido el del informe, deniegan (#7).
- **`updatedInput`**: lleva siempre la entrada **completa**, porque el SDK la sustituye entera
  (R1, e3). `PostToolUse` de `escalar_a_cumplimiento` (#7) no cambia.
- **Evento `cobertura_sustituida`**: se emite en el `PreToolUse`, antes de que la pasarela acepte la
  llamada. Dice qué cobertura se puso en la llamada y si la declarada por el coordinador era
  distinta; nunca que el informe o el escalamiento quedaron registrados.

Salida tipada que se añade a `hooks.py`, junto a `permitir`, `denegar` y `bloquear_cierre`:

```python
def reemplazar_entrada(entrada: dict) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "allow",
                                   "updatedInput": entrada}}
```

## `Caso`

- `caso.cobertura` → `calcular_cobertura(caso.estado)`.
- `caso.completo` → `caso.cobertura.completa`, y las condiciones del #7.
- `caso.turnos` → `num_turns` del coordinador, o `None` si no hubo `ResultMessage`.

## Línea de comandos

Tras «Frentes:», un bloque «Cobertura:» con `cobertura.lineas()`; en «Números de la validación»,
«turnos del coordinador: N de 30» (o «sin dato»).
