# Investigación: Auditoría: reglas delegadas a otro ticket y uv.lock como referencia

Decisiones del plan, con su porqué y las alternativas descartadas. Lo que no se pudo
comprobar leyendo el repositorio se marca **"se comprueba en el quickstart"**.

## R1. Dónde vive la regla de aplicabilidad y cómo se mantiene igual

**Decisión**: la regla de aplicabilidad es una sección `## Cuándo aplica una regla` con texto
**idéntico** en `.claude/agents/auditor-cumplimiento.md` y en
`.claude/skills/auditar-cumplimiento/SKILL.md`. En la skill, el paso 3 de "Qué hacer" pasa a
remitir a esa sección y deja de resumir la regla con otras palabras.

**Porqué**: hoy la regla está en el agente como sección y en la skill como un párrafo del paso
3, con redacción distinta. FR-005 y FR-013 piden igualdad comprobable por un test; solo se
puede comparar mecánicamente un bloque que existe con el mismo encabezado en los dos sitios.

**Alternativas**: dejar el párrafo del paso 3 y compararlo con la sección (se descarta: dos
redacciones nunca serán iguales); quitar la regla de la skill y dejarla solo en el agente (se
descarta: la skill es lo que el modelo lee primero y FR-005 exige las dos copias iguales).

## R2. Orden de decisión y correspondencia con los estados

**Decisión**: cinco pasos, en este orden, y cada uno acaba en uno de los cuatro estados que
ya existen (sin estados nuevos):

1. **Delegada con número** → `no aplica`, razón «delegada al ticket #N en la spec». Prevalece
   sobre el código que solo aporta datos o clasificación (decisión confirmada por la analista).
2. **Delegada y contradicha o debilitada por el diff** → `incumple`, bloqueante (FR-003, FR-011).
3. **Citada sin delegarla con número, asignada a este ticket, o el diff toca código o tests que
   la implementan o la prueban** → aplica y se verifica con evidencia.
4. **Código o test borrado o debilitado, de cualquier regla** → aplica; sin evidencia vigente
   es `no verificada`, bloqueante (FR-012). El paso 4 gana al 1: delegar exime de implementar,
   no de conservar.
5. **Ninguna** → `no aplica`, con la razón. Sin código de producción ni tests de las reglas, las
   cinco son `no aplica`.

**Porqué**: así la delegación solo exime lo que dice la spec (FR-002), la citada sin número
sigue aplicando (FR-004) y lo que ya #4 exigía, que borrar un test toca la regla, queda
intacto (FR-012).

**Interpretación que se declara**: el issue dice "aplica si la spec asigna su cumplimiento a
este ticket". Una spec que **cita** una regla sin delegarla con número se trata como que **la
asigna a este ticket**: es lo que dice FR-004 y lo que hoy hace el auditor. Sin esa lectura, una
regla citada sin más y sin código tocado pasaría a `no aplica` y se perdería una verificación.

**Alternativas**: un estado nuevo `delegada` (se descarta: obliga a cambiar `veredicto.py` y
`RESUMEN`, fuera del alcance); que la delegación sin número también exima (se descarta: lo
excluye FR-004 y la condición de la analista).

## R3. `uv.lock` como referencia

**Decisión**: en el bloque "Qué cuenta para la cobertura" de los cuatro archivos, `uv.lock` pasa
de "los generados (`uv.lock`) se leen por secciones" (que cuenta) a la lista de **referencia**:
«`specs/NNN-*/`, `README.md`, `DECISIONES.md`, `.claude/rules/` y los archivos generados por
herramientas (`uv.lock`)». El resto del bloque no cambia (FR-007).

**Porqué**: son exactamente cuatro apariciones, una por archivo (`Grep` sobre `.claude/`); no
hay otra instrucción que lo haga contar.

**`preparar_revision.py` queda como está**: marca `[referencia]` solo `specs/NNN-*/`
(`_es_referencia`). `uv.lock` seguirá apareciendo sin esa marca en la lista del contexto, y la
exención vive en el texto que lee cada revisión. Es una limitación declarada del alcance (el
issue excluye ese archivo): si el modelo ignorara el texto y leyera `uv.lock` a medias, lo
nombraría y la cobertura sería incompleta. **Este ticket no lo prueba con una sesión**: SC-003
se comprueba con el `/abrir-pr` real del #5, cuyo diff trae `uv.lock`, y queda anotado como
verificación pendiente de #5.

**Alternativa**: marcarlo desde `preparar_revision.py` (se descarta por alcance; sería una
mejora futura que quitaría la dependencia del texto).

## R4. Test de coherencia entre los cuatro archivos (FR-013, SC-004)

**Decisión**: en `.claude/hooks/test_agentes_skills.py`, que ya carga los cuatro textos con
`instrucciones_de_cobertura()`, se añade una sección "Coherencia entre los archivos de la
puerta":

- una función pura `seccion(cuerpo, encabezado)` que devuelve el texto desde `## <encabezado>`
  hasta el siguiente encabezado `## ` y lo normaliza (espacios y saltos de línea colapsados);
- un test que exige que el bloque `Qué cuenta para la cobertura` exista en los cuatro y sea
  igual;
- un test que exige que `Cuándo aplica una regla` exista en el agente y en la skill del
  auditor y sea igual;
- un test de la propia función que prueba con textos sintéticos que **falla** si difieren en
  un carácter, y que no falla por saltos de línea o espacios distintos.

**Porqué**: es el mecanismo que pide la analista para que SC-004 sea código y no lectura. Va
junto al módulo que ya prueba esos archivos (`rules/tests.md`) y no añade dependencias.

**Alternativa**: comparar contra un texto canónico guardado en el test (se descarta: dos
fuentes de verdad; FR-013 pide comparar los archivos entre sí).

## R5. Tests existentes que tocan este texto

**Decisión**: el texto nuevo **conserva** las frases que fijan los tests actuales:
«la spec del ticket la cita», «el diff toca código o tests que la implementan o la prueban»,
«sin código de producción ni tests de las reglas» y «borra o debilita»; y la skill conserva
«las cinco reglas» y no menciona `spec.md` antes de la constitución. Así los tests actuales
siguen en verde sin editarlos (FR-010); `REFERENCIA` gana `uv.lock` y una comprobación de que
ya no aparece como archivo que cuenta.

**Se comprueba en el quickstart** (Q1): que la suite completa pase tras el cambio.

## R6. Casos de prueba nuevos sobre el comportamiento del auditor

**Decisión**: además del test de texto, los casos de comportamiento se prueban con sesiones
reales sobre repositorios desechables (quickstart), porque el auditor es un subagente y su
reporte depende del modelo. Los tests de texto garantizan que la regla **está escrita igual**;
el quickstart comprueba que **se interpreta bien**. Se declara el límite: el comportamiento del
modelo no lo garantiza ningún test, solo se verifica en los casos probados.

## R7. Cómo se valida SC-001 sin tocar la rama 005

**Decisión**: en un **clon desechable fuera del repositorio** (como Q4(b) de #4):

1. `git clone` del repositorio local a una carpeta del scratchpad; `origin/main` del clon es el
   `main` actual (incluye #4).
2. Cambiar a la rama 005 del clon y hacer `git merge --no-ff` de la rama 019 en ella (no se
   copian archivos: el merge trae los cuatro tal como quedarán).
3. Corregir en el clon la línea 161 de la spec del #5 a «I.1, I.2 e I.3 … del ticket #7».
4. Commitear en el clon, abrir una **sesión nueva de Claude Code en la raíz del clon** y lanzar
   `/auditar-cumplimiento specs/005-servidor-mcp-pasarela`.

**Porqué**: la auditoría lee el repositorio de la sesión; un worktree movería referencias del
repositorio real y la rama 005 debe quedar intacta con su veredicto con bloqueantes. El
clon necesita sus propios hooks, que vienen en la rama.

**Se comprueba en el quickstart** (Q3): que el clon arranca sin bloquear las guardas, que la
auditoría ve la línea corregida y devuelve I.1 a I.3 `no aplica` con la razón. La corrección
real de la rama 005 se hace al volver al #5, no aquí (decisión de la analista).

**Reglas de `preparar_revision.py` que condicionan las ramas de prueba** (verificadas leyendo el
script): no hace `fetch`; compara contra `git merge-base HEAD origin/main`; exige una rama
`NNN-nombre` y una sola carpeta `specs/NNN-*`. Por eso toda rama de prueba se llama
`098-<nombre>` con su `specs/098-<nombre>/`, cada una nace de `main` del clon, y lo que deba
estar en la base se commitea en `main` y se avanza `origin/main` con `git update-ref` antes de
crear la rama: añadir y borrar un test en la misma rama deja un diff vacío (Q5).

## R8. Documentación

**Decisión**: **sin entrada nueva**: una viñeta en la entrada 5 de `DECISIONES.md`
(«Revisión independiente y puerta de PR») con el criterio de la regla delegada y los dos límites
de abajo; sin recortar nada por el límite de páginas (queda para su reorganización). El
contrato `specs/004-…/contracts/revisiones.md` queda como historia: la fila de cobertura que dice
que `uv.lock` se lee por secciones **la sustituye** `contracts/texto-de-la-puerta.md` de este
ticket; no se edita el contrato del #4.

## Límites declarados

Los dos primeros van a la viñeta de la entrada 5 de `DECISIONES.md`; el tercero queda aquí y en
el plan.

1. El auditor no consulta GitHub: no comprueba que el ticket nombrado exista ni que cubra la
   regla. Una spec que delegue por error deja la regla sin auditar hasta que el ticket
   receptor la asigne a sí mismo y se audite.
2. El comportamiento del auditor depende del modelo: el test garantiza el texto, no la
   interpretación.
3. `uv.lock` sin marca `[referencia]` en la lista del contexto (R3).
