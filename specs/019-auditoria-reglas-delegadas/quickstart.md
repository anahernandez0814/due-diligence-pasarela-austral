# Guía de validación: Auditoría: reglas delegadas a otro ticket y uv.lock como referencia

Escenarios para comprobar el ticket de punta a punta. Contratos en
[contracts/](contracts/), decisiones en [research.md](research.md). Validación **solo en
Windows**, como en #3 y #4. Q3 a Q5 los corre la analista en **sesiones nuevas abiertas en la
raíz de un clon desechable**, fuera del repositorio y sin tocar la rama 005 ni el veredicto
con bloqueantes que ya tiene registrado. Los resultados se anotan en `tasks.md`.

Los reportes del auditor dependen del modelo (R6): cada escenario de comportamiento se corre
**una vez** y se anota lo que salió; si un resultado no es el esperado, se anota como fallo y
no se repite hasta que salga bien.

## Reglas de `preparar_revision.py` que condicionan las pruebas

El script **no hace fetch** y calcula el diff con `git merge-base HEAD origin/main`; exige que
la rama se llame `NNN-nombre` y que exista **una sola** carpeta `specs/NNN-*`. De ahí:

- Toda rama de prueba se llama `098-<nombre>` y tiene su carpeta `specs/098-<nombre>/` con
  `spec.md`, `plan.md` y `tasks.md`. Con un nombre como `prueba-uvlock` el contexto sale
  `CONTEXTO INCOMPLETO`.
- Cada rama `098-*` se crea **desde `main` del clon**, nunca desde otra `098-*`, para que
  haya una sola carpeta `specs/098-*`.
- Lo que deba estar en la base (Q5) se commitea en `main` del clon y se avanza
  `origin/main` con `git update-ref refs/remotes/origin/main main` **antes** de crear la rama.
  Añadir y borrar en la misma rama deja un diff vacío.

## Preparación del clon desechable (Q3 a Q5)

Carpeta de scratchpad `…/clon-019` (fuera del repositorio).

1. `git clone <ruta del repositorio> clon-019`. `origin` es el repositorio local y
   `origin/main` es el `main` actual, que ya incluye #4. Nunca `git push` desde el clon.
2. Dentro, `git fetch origin 019-auditoria-reglas-delegadas` para tener la rama del ticket
   (hay que haberla commiteado antes).
3. `uv sync` y abrir Claude Code **en la raíz del clon**, nunca desde una subcarpeta.

## Q1. Suite y formato

`uv run ruff format .`, `uv run ruff check .` y `uv run pytest`: todo en verde, también con y
sin `PYTHONUTF8` / `PYTHONIOENCODING`. Esperado: los tests de coherencia nuevos pasan y los
actuales no se editaron (salvo `REFERENCIA`) (FR-010, SC-006).

## Q2. El test de coherencia falla si los archivos difieren (SC-004)

1. En la rama del ticket, cambiar **una palabra** del bloque `Qué cuenta para la cobertura` de
   solo una de las cuatro copias y ejecutar `uv run pytest .claude/hooks/test_agentes_skills.py`.
2. Esperado: falla y el mensaje nombra el archivo que difiere. Repetir con la sección `Cuándo
   aplica una regla` del agente del auditor.
3. Deshacer con `git restore` de ese archivo y comprobar que vuelve a pasar. `git status` queda
   limpio.

## Q3. SC-001: la rama 005 con la regla corregida

1. En el clon, `git switch 005-servidor-mcp-pasarela` y
   `git merge --no-ff origin/019-auditoria-reglas-delegadas` (no se copian archivos: el merge
   trae los cuatro archivos tal como quedarán). Si `DECISIONES.md` entra en conflicto, se
   resuelve en el clon conservando los dos cambios; es del clon, no del repositorio.
2. En `specs/005-servidor-mcp-pasarela/spec.md` línea 161, corregir a «I.1, I.2 e I.3 … del
   ticket #7». Commitear en el clon.
3. Sesión nueva en la raíz del clon: `/auditar-cumplimiento specs/005-servidor-mcp-pasarela`.
4. Esperado: I.1, I.2 e I.3 salen `no aplica`, cada una con la razón «delegada al ticket #7»;
   I.4 e I.5 siguen con `cumple`; las tres primeras aportan 0 bloqueantes.
5. Anotar el `RESUMEN` y la tabla. La corrección real de la línea 161 queda para el #5.

## Q4. SC-002, FR-004 y FR-011: delegada y contradicha, y citada sin número

Una sola rama y **una sola auditoría**:

1. Rama `098-delegada-contradice` desde `main` del clon, con `specs/098-delegada-contradice/`:
   - la spec **delega I.3 «al ticket #7»** (con número);
   - la spec **cita I.1 en prosa sin número ni ticket** («lo cubrirá otro ticket»);
   - un `src/` ficticio que **contradice I.3** (por ejemplo, una función que devuelve
     `habilitar` para una categoría de alto riesgo) y **ningún código ni test de I.1**.
2. `/auditar-cumplimiento specs/098-delegada-contradice` en sesión nueva.
3. Esperado: **I.3 `incumple`**, bloqueante, con ubicación y razón (la delegación no la
   exime); **I.1 `no verificada`**, bloqueante (citada sin número: se trata como asignada a
   este ticket y no hay evidencia). `RESUMEN` con `bloqueantes≥2`.

## Q5. SC-008 y FR-012: borrar el test de una regla

1. **En `main` del clon** (es la base): commitear un `src/prueba_098/regla.py` ficticio que
   implemente I.3 (una función que no habilita la categoría de alto riesgo) y su
   `src/prueba_098/test_regla.py`. Luego:
   `git update-ref refs/remotes/origin/main main`.
2. Rama `098-borra-test` desde ese `main`, con `specs/098-borra-test/` cuya spec **delega I.3
   «al ticket #7»**, y un commit que **borra `test_regla.py`** y deja el código.
3. `/auditar-cumplimiento specs/098-borra-test` en sesión nueva.
4. Esperado: I.3 aplica pese a estar delegada y sale `no verificada` (o `incumple`),
   bloqueante; nunca `no aplica`.

## Q6. SC-005: el alcance se respeta

`git diff --stat main...HEAD` en la rama del ticket: ninguna línea de `veredicto.py`,
`guarda_pr.py`, `preparar_revision.py` ni de sus tests. Los archivos cambiados son los dos
agentes, las dos skills, `test_agentes_skills.py`, `DECISIONES.md` y `specs/019-*/`.

## SC-003: `uv.lock` no reduce la cobertura (se anota, no se prueba aquí)

No hay escenario propio en este ticket. Se comprueba con el **`/abrir-pr` real del #5**, cuyo
diff trae `uv.lock`: las dos revisiones deben poder terminar con `cobertura=completa` si leyeron
todo lo que cuenta. Queda anotado en `tasks.md` como verificación pendiente de #5; este ticket
solo cubre el texto (Q2 y el test de coherencia).

## Limpieza

Borrar la carpeta `clon-019` del scratchpad. No se cambia nada en el repositorio real ni en la
rama 005.
