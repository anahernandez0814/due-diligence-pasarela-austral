# Research: Documentación de entrega (#14)

Cada decisión con su motivo y la alternativa descartada. Las sondas se hicieron el
2026-10-19 en la rama `014-documentacion-entrega`, sobre `f9e82d6`.

## R1. Medida de las dos páginas

- **Decisión**: una función de prueba parte cada línea de `DECISIONES.md` con
  `textwrap.wrap(línea, 90)` (corta por palabras) y cuenta `max(1, len(partes))`; el total
  debe ser ≤ 100. Medido hoy: 686 con esta regla (678 cortando por caracteres), lo que
  coincide con las «unas 684» de la analista.
- **Motivo**: es determinista, no depende de un visor de Markdown y castiga las filas de
  tabla largas, que en papel también ocupan varias líneas.
- **Descartado**: contar líneas del archivo (una fila de 400 caracteres contaría una) y
  medir el HTML renderizado (depende del navegador y de la fuente).

## R2. Dónde viven los tests de la documentación

- **Decisión**: `test_documentacion.py` en la raíz, junto a `README.md` y `DECISIONES.md`, y
  `"test_documentacion.py"` añadido a `testpaths` de `pyproject.toml`. Lo recoge
  `uv run pytest`; `uv run pytest src` (el paso del «Inicio rápido») no lo necesita.
- **Motivo**: la convención es «cada test junto a lo que prueba» (`.claude/rules/tests.md`).
  Los documentos están en la raíz y en `docs/`.
- **Descartado**:
  - `docs/test_documentacion.py`: `docs/` pasa a ser referencia para los revisores (R6) y un
    `test_*.py` dentro sería ambiguo (los tests cuentan, `docs/` no);
  - `.claude/hooks/`: no prueba ninguna guarda, y esa carpeta la protege la spec previa.

## R3. Anclas de `DECISIONES.md` al detalle

- **Decisión**: enlaces en línea a los encabezados de `docs/decisiones-detalle.md` con el slug
  de GitHub (minúsculas; se quitan los caracteres que no son letra, dígito, `_`, `-` o
  espacio, conservando las tildes; los espacios pasan a `-`; un repetido lleva `-1`, `-2`).
  El test calcula los slugs del detalle con esa regla y comprueba cada enlace.
- **Motivo**: no añade marcas al detalle y GitHub lo resuelve sin HTML.
- **Descartado**: `<a id="…">` en el detalle (marcas que no son contenido) y enlaces de
  referencia al final (14 líneas más dentro del límite de 100).

## R4. Traslado sin pérdida

- **Decisión**: `docs/decisiones-detalle.md` = el `DECISIONES.md` de `f9e82d6` línea a línea,
  con añadidos intercalados. El test toma la versión de partida con
  `git show f9e82d6:DECISIONES.md` y comprueba que sus líneas no vacías son una subsecuencia
  ordenada de las del detalle. Sin git o sin ese commit (por ejemplo, un clon superficial),
  el test se omite con el motivo.
- **Motivo**: «sin pérdida» comprobable; las correcciones (Project, espera de la categoría)
  van como notas **después** de la línea que corrigen, sin tocarla.
- **Descartado**: copiar el texto de partida dentro del test (otra copia que mantener).

## R5. Dónde va cada añadido del detalle

| Añadido | Dónde |
|---------|-------|
| D1–D4 del #10 | Ya están en la entrada 11; se añade un índice «Desviaciones declaradas» con enlace a cada una y a `specs/010-…/plan.md`. |
| D1–D2 del #11 | Ya en la entrada 12; mismo índice, con `specs/011-…/plan.md`. |
| D1–D3 del #12 | Ya en la entrada 13; mismo índice, con `specs/012-…/plan.md`. |
| Recarga en caliente de `settings.json` | Ya en la entrada 14; el índice de límites la enlaza. |
| Límites del PR #29 | Sección nueva «Límites del plugin», con `contexto_revision.py:160` y `revisor-codigo.md:67` del plugin y el enlace al PR. |
| Sugerencias no atendidas | Sección nueva, una línea por PR con enlace, tomadas del comentario `ciclo-tickets:pr` de cada issue. |
| Latencia con Opus 5.5 (T055 del #7) | Sección nueva «Mejoras futuras», con 23–56 s y 0,07–0,16 USD por caso. |
| Espera de la categoría con cualquier frente caído | Nota tras la línea de la espera `categoria` de la entrada 11. |
| Corrección de los workflows del Project | Nota tras la línea «Done» de la entrada 3 (FR-016 del #2). |

## R6. `docs/` como referencia para los revisores

- **Decisión**: añadir `docs/` a la viñeta «Son referencia y no cuentan» de los cuatro textos
  de la puerta y a `REFERENCIA` del test. El test existente comprueba ya que cada ruta de
  `REFERENCIA` aparece en los cuatro.
- **La copia del plugin no cambia**: su revisor dice «la documentación en Markdown fuera de
  la configuración de Claude Code» (`plugins/guardas-y-revision/agents/revisor-codigo.md:68`),
  que ya cubre `docs/*.md` de forma genérica, y su skill no tiene bloque de cobertura. Nombrar
  `docs/` en el plugin sería un supuesto de estructura del otro repositorio. La ambigüedad
  de esa línea es justo el límite del PR #29 que se documenta (R5).

## R7. «Inicio rápido»

- **Decisión**: cinco pasos con su comprobación: `uv python install 3.12`; `uv sync`; copiar
  `.env.example` a `.env` (`Copy-Item` en PowerShell, `cp` en bash) y poner la clave con un
  editor; `uv run pytest src` (unos 25 s, todo en verde, sin clave); `uv run streamlit run
  src/due_diligence/chat.py` (http://localhost:8501). Requisitos previos: `git`, `uv` y una
  clave de Anthropic.
- **Cambios en el resto del README**: «Verificar el entorno» deja de proponer `uv run pytest`
  como paso principal y remite a «Pruebas»; las referencias «la entrada N de DECISIONES.md»
  pasan a enlazar el detalle. Nada más se reescribe.
- **Descartado**: `uv run pytest` como verificación (4:43–6:12 en Windows, D3 del #12).

## R8. La línea del marketplace

- **Decisión**: `claude plugin marketplace add anahernandez0814/due-diligence-pasarela-austral`
  y, para todo el equipo, en el `.claude/settings.json` del otro repositorio:
  `"extraKnownMarketplaces": {"piezas-reutilizables": {"source": {"source": "github",
  "repo": "anahernandez0814/due-diligence-pasarela-austral"}}}`. Documentado en
  code.claude.com/docs/en/plugins/org: la clave es el `name` del `marketplace.json` y solo
  aplica en una carpeta de confianza; cada persona instala el plugin una vez con
  `claude plugin install … --scope project`.
- **Frase de visibilidad**: «el repositorio es privado y pide acceso», junto a la línea, con
  un punto en `docs/entrega.md` para revisarla si cambia la visibilidad.

## R9. El .zip

- **Decisión** (PowerShell, Windows 10 o posterior, con el `tar.exe` del sistema, bsdtar 3.8):
  `git clone` desde GitHub en una carpeta temporal y `tar.exe -a -c -f <zip> -C <padre>
  <carpeta>`; `-a` elige el formato zip por la extensión. En macOS o Linux, `zip -r`. Después:
  listar el contenido con `tar.exe -t -f` y comprobar que están `.git/`, `specs/` y
  `.specify/memory/` y que no hay `.venv/`, `.env`, `CLAUDE.local.md`,
  `.claude/settings.local.json` ni `docs/bitacora-decisiones.md`; tamaño con `Get-Item`.
- **Motivo**: el clon limpio garantiza por construcción que no entra nada ignorado ni no
  versionado; el `tar` de Git Bash es GNU y no hace zip.
- **Descartado**: `Compress-Archive` (omite archivos ocultos con comodines) y `git archive`
  (no incluye `.git`).

## R10. Revisión de credenciales en el historial

- **Decisión**: dos comandos en `docs/entrega.md`:
  1. **Prefijos** con `git grep -l` sobre cada commit de `git rev-list --all`:
     `sk-ant-[A-Za-z0-9_-]{20,}`, `ghp_[A-Za-z0-9]{36}` y `github_pat_[A-Za-z0-9_]{22,}`.
     `-l` imprime solo `<commit>:<archivo>`. Sonda: 356 commits, 0 hallazgos, unos 36 s.
  2. **El detector del proyecto** (`plugins/guardas-y-revision/hooks/detector_datos.py`,
     `buscar()` devuelve solo tipo y línea): un script Python en línea que recorre cada blob
     único de `git rev-list --all --objects`, ignora binarios y lo que pasa de 2 MB, e imprime
     tipo, archivo y el primer commit que lo contiene (`git log --all --find-object`). Sonda:
     2468 objetos, 0 hallazgos, unos 80 s.
- **Ningún valor**: los dos solo imprimen commit, archivo y tipo. Un test ejecuta los dos
  bloques de `docs/entrega.md` en un repositorio git temporal con una credencial generada al
  ejecutar y comprueba que la encuentran y que el valor no aparece en la salida.
- **Con un hallazgo real**: no se reescribe el historial (lo prohíbe el enunciado); se revoca
  la credencial y la analista decide.
- **Descartado**: `git log -p | grep` (imprime la línea con el valor) y herramientas externas
  (gitleaks, trufflehog), que añaden una dependencia sin ganancia para tres prefijos.

## R11. Guiones

- **Funcionamiento** (≤ 5 min): arranque con `.env` ya creado; los siete casos en el orden del
  README, unos 35 s cada uno, con los dos reinicios de modo (f y e). Sin explicar código.
- **Defensa** (≤ 15 min): ecosistema (unos 5 min: CLAUDE.md, reglas, skills, subagentes,
  hooks, comando, MCP y plugin, con la tabla de `DECISIONES.md`); Spec Kit (unos 4 min:
  constitución y un ticket de la spec al código, propuesta el #7); Agent SDK (unos 6 min:
  coordinador, contexto y herramientas de cada subagente, hooks de las reglas, fallas y
  cobertura, diseño de las herramientas MCP).

## R12. Workflows del Project: la corrección

- Lo que se documentó en FR-015 del #2 y en la entrada 3: «"Item closed" y "Pull request
  merged" pasan a Done». Lo real, según la analista: los PR no están en el Project, así que
  «Pull request merged» no mueve nada; el paso a Done lo hace «Item closed» cuando el
  `Closes #N` del PR cierra el issue. La spec del #2 no se corrige (es historia del ticket);
  la corrección va en `DECISIONES.md` y como nota en el detalle.
