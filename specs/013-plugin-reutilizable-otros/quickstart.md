# Quickstart: validación del plugin (#13)

Guía para comprobar el ticket de punta a punta. Los contratos están en
[contracts/plugin.md](contracts/plugin.md) y las decisiones en [research.md](research.md).

**Requisitos**:
- Claude Code 2.1.295 o posterior (medido con 2.1.303);
- `uv`;
- `git`;
- Git Bash en Windows.

Q3, Q4 y Q5 usan la sesión de la CLI de la analista con Haiku, del orden de céntimos. Ningún paso
lee `.env`.

**Trazas**: `guarda.jsonl` y las demás trazas `stream-json` contienen el valor generado, porque
guardan el resultado del `Read`.
- Se quedan en la carpeta temporal y se borran en la limpieza.
- Al quickstart y a `tasks.md` solo pasan conteos y la línea `RESUMEN`, **nunca fragmentos de la
  traza**.
- Los conteos los saca `contar_bloqueos.py`, un script fuera del repositorio que lee la traza e
  imprime solo números:
  - las llamadas a `Write`;
  - los resultados de `Write` bloqueados por la guarda;
  - por cada resultado bloqueado, cuántas veces aparece el prefijo `[guarda_datos]`.

**Qué cuenta como prueba (Q3 y Q5)**: solo que la traza tenga **un resultado de la herramienta
bloqueado con el mensaje de la guarda**.
- Si `salida.txt` no existe pero no hay mensaje de la guarda (por ejemplo, porque el modelo se
  niega a copiar algo que parece una tarjeta), el resultado **no es concluyente**.
- En ese caso se repite con otro prompt neutro o con `--model sonnet`, **como máximo dos intentos
  por prueba**, y se anota cada intento.

## Q1. Pruebas deterministas (FR-007, FR-004, FR-009 y FR-012)

```bash
uv run ruff format --check . && uv run ruff check .
uv run pytest src
uv run pytest .claude/hooks plugins
```

**Esperado**: todo en verde. En particular:
- **`plugins/guardas-y-revision/hooks/test_*.py`**: los casos del #3 contra la única guarda;
- **`.claude/hooks/test_guarda_datos_repositorio.py`**: los casos propios del proyecto contra la
  misma guarda;
- **`.claude/hooks/test_plugin_repositorio.py`**:
  - ningún término del proyecto en el plugin;
  - una ejecución por herramienta;
  - el plugin a `false`;
  - `hooks.json` equivalente a `settings.json`;
  - `base_guarda` equivalente a `comun`.

**Copia limpia (FR-012)**: los mismos comandos en un clon de la rama, sin `.env`, sin clave y sin
`PYTHONUTF8`:

```bash
C=$(mktemp -d) && git clone -q --branch 013-plugin-reutilizable-otros "$PWD" "$C/copia"
cd "$C/copia" && env -u PYTHONUTF8 -u PYTHONIOENCODING -u ANTHROPIC_API_KEY uv run pytest src \
  && env -u PYTHONUTF8 -u PYTHONIOENCODING -u ANTHROPIC_API_KEY uv run pytest .claude/hooks plugins
```

## Q2. Instalación sin interfaz con la CLI (FR-010, SC-001)

Fuente: un clon limpio de la rama, para que solo cuente lo commiteado. Destino: un repositorio git
nuevo fuera de este.

```bash
T=$(mktemp -d)
git clone -q --branch 013-plugin-reutilizable-otros /d/AIReadyOrquestador "$T/fuente"
claude plugin validate --strict "$T/fuente"
claude plugin validate --strict "$T/fuente/plugins/guardas-y-revision"

git init -q -b main "$T/repo" && cd "$T/repo"
git -c user.name=prueba -c user.email=prueba@example.invalid commit -q --allow-empty -m inicio
claude plugin marketplace add "$T/fuente" --scope local
claude plugin install guardas-y-revision@piezas-reutilizables --scope local
claude plugin list --json
claude plugin details guardas-y-revision@piezas-reutilizables
```

**Esperado**:
- **`validate`**: sin errores ni avisos.
- **La instalación**: dos comandos, `marketplace add` e `install` (SC-001: tres como máximo).
- **`list`**: el plugin habilitado en el scope `local`.
- **`details`**: el agente `revisor-codigo`, la skill `revisar-codigo` y el hook `PreToolUse`.

## Q3. La guarda en el repositorio de prueba (US1-2 y US1-3; R4, R5 y R8)

El valor se genera en disco con un script: no aparece en ningún comando ni en el prompt.

```bash
cd "$T/repo"
uv run --no-project --python 3.12 python - <<'EOF'
import random
cuerpo = "4" + "".join(random.choice("0123456789") for _ in range(14))
total = 0
for i, c in enumerate(reversed(cuerpo)):
    d = int(c) * (2 if i % 2 == 0 else 1)
    total += d - 9 if d > 9 else d
open("entrada.txt", "w").write(f"pago {cuerpo}{(10 - total % 10) % 10}\n")
open("ficticio.txt", "w").write("identificador ficticio XX-0000\n")
EOF
claude -p "Lee entrada.txt y crea salida.txt con exactamente el mismo contenido usando la herramienta Write. No uses Bash." \
  --model haiku --allowedTools "Read,Write" --output-format stream-json --verbose > guarda.jsonl
test -e salida.txt && echo "salida.txt existe" || echo "salida.txt no existe"
uv run --no-project --python 3.12 python <ruta fuera del repositorio>/contar_bloqueos.py guarda.jsonl
claude -p "Lee ficticio.txt y crea salida-ficticia.txt con exactamente el mismo contenido usando la herramienta Write. No uses Bash." \
  --model haiku --allowedTools "Read,Write"
test -e salida-ficticia.txt && echo "ficticio permitido"
```

**Esperado**:
- **El valor con forma real**: `salida.txt` no existe, y `contar_bloqueos.py` da al menos un
  resultado de `Write` bloqueado, con exactamente un `[guarda_datos]`. El mensaje dice el tipo, no
  el valor.
- **El valor ficticio**: `salida-ficticia.txt` existe.

**Si el plugin no carga en `-p`** porque la carpeta no es de confianza (R8): se repite Q3 en un
segundo repositorio nuevo, `$T/repo-dir`, añadiendo
`--plugin-dir "$T/fuente/plugins/guardas-y-revision"` a cada `claude -p`. La carga desde la
instalación queda para Q6.

## Q4. La skill y el subagente (US1-4 y US1-5; R4, R6 y R7)

```bash
cd "$T/repo"
git switch -q -c cambio
printf 'def dividir(a, b):\n    return a / b\n' > calculo.py
git add calculo.py
git -c user.name=prueba -c user.email=prueba@example.invalid commit -q -m "calculo"
claude -p "/guardas-y-revision:revisar-codigo" --model haiku --output-format stream-json --verbose > revision.jsonl
grep -o 'RESUMEN: bloqueantes=[0-9]* sugerencias=[0-9]* cobertura=[a-z]*' revision.jsonl | tail -1
grep -c "CONTEXTO DE REVISIÓN" revision.jsonl
```

**Esperado**:
- **La última línea del reporte**: `RESUMEN: …`.
- **El contexto**: la marca `CONTEXTO DE REVISIÓN` aparece, lo que demuestra que la línea `!` se
  ejecutó con la ruta sustituida (R4). También aparece `Ticket: no aplica`, porque el repositorio
  no usa `specs/` (US1-5).
- **El agente**: corrió `guardas-y-revision:revisor-codigo` (R7).

**Si falta la marca o el agente no se encuentra**: se aplica la alternativa de R4 o R7, se repite
Q4 y se anota el resultado en `research.md`.

## Q5. Una sola ejecución en un clon limpio de este repositorio (US3-1 y US3-2, SC-003). Obligatoria

El test de Q1 lee la configuración. Q5 demuestra dos cosas más:
- que Claude Code dispara la guarda con la expresión nueva del matcher;
- que un clon limpio queda protegido sin pasos manuales.

Se usa el mismo clon de la rama de Q1 (`$C/copia`), sin `.env`, sin clave y sin `PYTHONUTF8`, y el
valor se genera en disco con el script de Q3.

```bash
cd "$C/copia"
# genera entrada.txt con el script de Q3 (valor con forma real, solo en disco)
env -u PYTHONUTF8 -u PYTHONIOENCODING -u ANTHROPIC_API_KEY claude -p \
  "Lee entrada.txt y crea salida.txt con exactamente el mismo contenido usando la herramienta Write. No uses Bash." \
  --model haiku --allowedTools "Read,Write" --strict-mcp-config \
  --output-format stream-json --verbose > "$C/clon.jsonl"
test -e salida.txt && echo "salida.txt existe" || echo "salida.txt no existe"
uv run --no-project --python 3.12 python <ruta fuera del repositorio>/contar_bloqueos.py "$C/clon.jsonl"
```

- **`--strict-mcp-config`**: evita arrancar los servidores MCP del proyecto, que no hacen falta
  para la prueba.
- **La traza va fuera del clon** (`$C/clon.jsonl`), para que no quede en su árbol.

**Esperado**:
- `salida.txt` no existe;
- al menos un resultado de `Write` bloqueado;
- **en cada resultado bloqueado, exactamente un `[guarda_datos]`**. Dos serían la guarda ejecutada
  dos veces.

Se cuentan los resultados de la herramienta, no las apariciones del texto, porque el modelo puede
repetir el mensaje.

**Si no es concluyente**: se aplica la regla de arriba, con dos intentos como máximo.

## Q6. Pendiente de la analista, solo si Q3 o Q4 no se pudieron hacer sin interfaz

```bash
cd <ruta de $T/repo que se anote en tasks.md>
claude          # aceptar la confianza en la carpeta
/plugin         # comprobar que guardas-y-revision@piezas-reutilizables está habilitado
```

En la sesión interactiva:
1. Pedir: «Lee entrada.txt y crea salida.txt con el mismo contenido.» **Esperado**: el bloqueo de
   la guarda.
2. Ejecutar `/guardas-y-revision:revisar-codigo`. **Esperado**: un reporte que termina en
   `RESUMEN: …`.

**SC-006**: la analista sigue solo la sección del README en un repositorio nuevo y valora si basta.

## Limpieza

```bash
cd "$T/repo"
claude plugin uninstall guardas-y-revision@piezas-reutilizables --scope local
claude plugin marketplace remove piezas-reutilizables
cd / && rm -rf "$T" "$C"
```

La limpieza borra también las trazas `*.jsonl`, que contienen el valor generado.

## Resultados (2026-10-19, Claude Code 2.1.303, Haiku 5.5)

Solo conteos y la línea `RESUMEN`; las trazas se borraron en la limpieza.

| Q | Resultado | Conteos | Coste (USD) |
|---|-----------|---------|-------------|
| **Q2** | Instalación sin interfaz. | **Validación**: `validate --strict` pasa en el marketplace y en el plugin. **Instalación**: dos comandos (`marketplace add --scope local` e `install --scope local`), ambos con código 0. **`list --json`**: `enabled: true`, `scope: local`, `version: 1.0.0`. **`details`**: 1 skill, 1 agente y 1 hook `PreToolUse`. | 0 |
| **Q3** | La guarda del plugin bloquea en el repositorio de prueba. **Concluyente en el primer intento.** | **Valor con forma real**: `salida.txt` no existe; llamadas a `Write` 1, resultados bloqueados 1, `[guarda_datos]` por resultado `[1]`. **Control ficticio**: `salida-ficticia.txt` existe, 0 bloqueos. | 0,00544 + 0,00472 |
| **Q4** | La skill y el subagente funcionan. **R4 y R7 verificados, sin alternativas.** | **Reporte**: `RESUMEN: bloqueantes=0 sugerencias=2 cobertura=completa`. **Contexto**: la traza tiene la salida real del script (`Rama: cambio`, `Base: … (git merge-base HEAD main)`, `Ticket: no aplica (el repositorio…`, `Archivos cambiados (1)`) y 0 apariciones de `${CLAUDE_PLUGIN_ROOT}` sin sustituir. **Agente**: `subagent_type = guardas-y-revision:revisor-codigo`. | 0,00239 (lo que informa el CLI) |
| **Q5** | Una sola ejecución en un clon limpio de la rama. | **Intento 1 no concluyente**: 0 llamadas a `Write`, porque el modelo se negó a copiar un valor que parecía sensible. **Intento 2**, con un prompt neutro que explica la prueba: `salida.txt` no existe; llamadas a `Write` 1, resultados bloqueados 1, `[guarda_datos]` por resultado `[1]`; el hook que bloqueó es el de `plugins/guardas-y-revision/hooks/guarda_datos.py` (0 apariciones de la ruta de compatibilidad). | 0,00514 + 0,00477 |

- **Total de `claude -p`**: unos 0,022 USD en 5 ejecuciones.
- **La confianza**: el plugin instalado con `--scope local` cargó en `claude -p` sin aceptar la confianza de la carpeta, y el clon limpio ejecutó los hooks del proyecto en `-p`. Q6 no hizo falta; solo queda SC-006, la valoración de la analista.
