# Contrato: el texto de los cuatro archivos de la puerta

Entidades en [data-model.md](../data-model.md); decisiones en [research.md](../research.md)
(R1 a R5). Este contrato fija las **dos secciones** que se escriben igual en los archivos y qué
sustituye del contrato del #4.

## Bloque 1 — `## Qué cuenta para la cobertura` (los cuatro archivos)

Sustituye la fila "Cuentan / Son referencia" de `specs/004-…/contracts/revisiones.md`. Solo
cambia `uv.lock` (R3); el resto de la sección queda como está hoy.

```markdown
## Qué cuenta para la cobertura

`cobertura=completa` significa que leíste todo lo que cuenta.

- **Cuentan**: el código y la configuración de la lista (`src/**`, `.claude/hooks/*.py`,
  `.claude/settings.json`, `.mcp.json`, `.claude/agents/`, `.claude/skills/` y
  `.claude/commands/`) y los tests (`test_*.py`). Se leen enteros; los tests, por secciones si
  hace falta. Cualquier otro archivo de la lista que no sea referencia también cuenta.
- **Son referencia y no cuentan**: `specs/NNN-*/`, `README.md`, `DECISIONES.md`,
  `.claude/rules/` y los archivos generados por herramientas (`uv.lock`). Léelos por secciones
  o con `Grep` para contrastar; leerlos a medias no reduce la cobertura.
- **No ejecutar tests nunca reduce la cobertura**: no tienes Bash. No lo reportes como falta
  ni como hallazgo.
- **Un archivo que cuenta y que leíste a medias** lo nombras en el reporte, con
  las líneas leídas, y entonces la cobertura es `incompleta`.
- Si no puedes leer un archivo que cuenta, si el contexto está incompleto o si la lista viene
  **agrupada por directorio** (no sabes qué archivos leer), la cobertura es `incompleta`.
```

Cambios respecto al texto actual: se quita «los generados (`uv.lock`) se leen por secciones»
de **Cuentan** y se añade «y los archivos generados por herramientas (`uv.lock`)» a
**Son referencia**. Nada más.

## Bloque 2 — `## Cuándo aplica una regla` (agente y skill del auditor)

En el agente sustituye la sección del mismo nombre; en la skill es una sección nueva (después
de "Plan de lectura", antes de "Qué hacer") y el paso 3 de "Qué hacer" pasa a remitir a ella.
No menciona `spec.md` (la skill exige que la constitución se nombre antes que `spec.md`).

```markdown
## Cuándo aplica una regla

Decide, para cada una de las cinco reglas, en este orden:

1. **Delegada con número.** La spec del ticket cita la regla para delegarla y nombra el ticket
   responsable con su número (`#N`). La regla es `no aplica`, con la razón «delegada al ticket
   #N en la spec». La delegación prevalece incluso sobre el código del cambio que solo aporta
   datos o clasificación que la regla usa y no la hace cumplir. Salvo los puntos 2 y 4.
   Citarla sin delegarla con un número de ticket no es delegarla: sigue el punto 3.
2. **Delegada y contradicha.** Si el diff contradice o debilita una regla delegada, es
   `incumple` y es **bloqueante**. Delegar exime de implementar la regla, no de violarla.
3. **Asignada a este ticket.** Si la spec del ticket la cita sin delegarla con número, o le
   asigna su cumplimiento, o el diff toca código o tests que la implementan o la prueban, la
   regla aplica y la verificas con los estados de abajo.
4. **Borrada o debilitada.** Sea delegada o no, un cambio que borra o debilita el código o el
   test de una regla la toca: aplica y, si sin ese código o ese test ya no hay evidencia
   vigente en el código y en los tests, es `no verificada` y bloqueante. La delegación exime
   de implementar, no de conservar lo que ya garantiza la regla. Nunca la des por `no aplica`
   porque no se tocó código de producción.
5. **Ninguna de las anteriores.** `no aplica`, y das **la razón**.
   Sin código de producción ni tests de las reglas en el cambio (por ejemplo, solo
   configuración o documentación), las cinco reglas son `no aplica`, con esa razón, y eso no
   bloquea.
```

Los tests existentes buscan algunas frases sin normalizar los saltos de línea («sin código de
producción ni tests de las reglas», «borra o debilita»), así que esas frases van enteras en una
sola línea del archivo: el ajuste de líneas del punto 5 es solo de forma.

Frases del texto actual que se conservan porque las fijan tests existentes (R5): «la spec del
ticket la cita», «el diff toca código o tests que la implementan o la prueban», «sin código de
producción ni tests de las reglas», «borra o debilita».

## Paso 3 de la skill de auditoría (reemplazo)

```markdown
3. **Decide cuáles de las cinco reglas aplican** al cambio con la sección «Cuándo aplica una
   regla» de arriba, y reporta la razón de cada `no aplica`.
```

## Qué no cambia

La tabla de las cinco reglas y de los cuatro estados, el formato de reporte, la línea
`RESUMEN`, el plan de lectura, la constitución como documento principal y el comando inyectado.
