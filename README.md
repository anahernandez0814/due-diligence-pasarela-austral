# Due Diligence Pasarela Austral

Sistema multi-agente en Python con el Claude Agent SDK para el due diligence de comercios de
la pasarela de pagos ficticia **Pasarela Austral**. Lo usa un analista interno de la
pasarela: un coordinador delega en subagentes especializados (registro mercantil, listas
restrictivas, noticias y riesgo de categoría) y entrega un informe con fuentes, o escala el
caso a un oficial de cumplimiento. Todos los datos son ficticios.

- **GitHub Project (backlog)**: https://github.com/users/anahernandez0814/projects/1
- **Video de funcionamiento**: _pendiente_
- **Requisitos de la prueba**: [docs/enunciado.md](docs/enunciado.md)
- **Principios del proyecto**: [constitución](.specify/memory/constitution.md)
- **Decisiones**: [DECISIONES.md](DECISIONES.md)

## Requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/): gestiona Python 3.12 y las
  dependencias; no hace falta instalar Python aparte.
- [GitHub CLI (gh)](https://cli.github.com/), con sesión iniciada (`gh auth login`).
- [Claude Code](https://docs.claude.com/en/docs/claude-code), para trabajar con las
  convenciones del equipo y el backlog.

## Preparar el entorno

```bash
git clone https://github.com/anahernandez0814/due-diligence-pasarela-austral.git
cd due-diligence-pasarela-austral
uv sync
```

## Verificar el entorno

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Los tres comandos deben terminar sin errores; pytest ejecuta los tests de `src/` y de
`.claude/hooks/`.

## Token de GitHub para Claude Code (`GITHUB_PAT`)

Claude Code lee y actualiza el GitHub Project con el servidor MCP oficial de GitHub
(configurado en [.mcp.json](.mcp.json)). La credencial se toma de la variable de entorno del
sistema `GITHUB_PAT`; **nunca se escribe en el repositorio ni en `.env`**.

`GITHUB_PAT` puede ser el token de la CLI de GitHub o un PAT clásico. En ambos casos necesita
los scopes `repo` y `project`.

**Opción A: token de la CLI de GitHub.**

```bash
gh auth refresh -s project   # añade el scope project si falta
gh auth status               # muestra los scopes del token
```

**Opción B: PAT clásico.** Créelo en GitHub, en *Settings → Developer settings → Personal
access tokens (classic)*, con los scopes `repo` y `project`. Un PAT fine-grained queda como
posible mejora: no siempre permite dar acceso a los Projects de usuario.

**Definir la variable** a nivel de usuario y reiniciar la terminal, VS Code o Claude Code.
No escriba el token en la línea de comandos: quedaría en el historial del shell.

En Windows (PowerShell), con la opción A:

```powershell
[Environment]::SetEnvironmentVariable("GITHUB_PAT", (gh auth token), "User")
```

Con esta opción la variable guarda una copia del token. Si vuelve a ejecutar
`gh auth login` o `gh auth refresh`, repita el comando.

En Windows con un PAT clásico, péguelo cuando lo pida `Read-Host`, que no lo muestra ni lo
guarda en el historial:

```powershell
$s = Read-Host "PAT" -AsSecureString
[Environment]::SetEnvironmentVariable("GITHUB_PAT", [System.Net.NetworkCredential]::new('', $s).Password, "User")
```

En macOS o Linux con la opción A, añada esta línea al perfil del shell (`~/.bashrc`,
`~/.zshrc`). El token se lee en cada sesión, así que no se desactualiza:

```bash
export GITHUB_PAT="$(gh auth token)"
```

En macOS o Linux con un PAT clásico, guárdelo en el llavero del sistema y léalo desde el
perfil, en vez de dejarlo en texto plano.

En macOS, `-w` sin valor pide el token sin mostrarlo:

```bash
security add-generic-password -a "$USER" -s GITHUB_PAT -w
export GITHUB_PAT="$(security find-generic-password -s GITHUB_PAT -w)"   # en el perfil
```

En Linux, con libsecret:

```bash
secret-tool store --label=GITHUB_PAT service github_pat
export GITHUB_PAT="$(secret-tool lookup service github_pat)"   # en el perfil
```

**Abra Claude Code siempre en la raíz del repositorio.** Desde una subcarpeta (por ejemplo
`specs`) Claude Code no carga la configuración del proyecto: las guardas no actúan y
`/revisar-codigo` falla al no encontrar `.claude/hooks/preparar_revision.py`.

**Comprobarlo.** En una sesión nueva de Claude Code en la raíz del repositorio, ejecute
`/mcp`: `github` debe aparecer conectado, sin pedir aprobación.

**Si `github` falla con 401/403**, aplique la alternativa local por stdio descrita en
[specs/001-ecosistema-base/contracts/mcp-json.md](specs/001-ecosistema-base/contracts/mcp-json.md).
Necesita el binario `github-mcp-server` en el PATH. Configúrela solo para usted, en ámbito
local (`claude mcp add-json github '<json>' --scope local`); no modifique ni commitee el
`.mcp.json` del equipo.

## Servidor MCP de la pasarela

El servidor `pasarela` ([src/servidor_mcp/](src/servidor_mcp/)) simula, con **datos ficticios**,
las fuentes de la pasarela y sus dos canales de decisión. Está registrado en
[.mcp.json](.mcp.json) junto al de GitHub y aprobado en `.claude/settings.json`, sin
credenciales. Las decisiones están en la entrada 6 de [DECISIONES.md](DECISIONES.md).

| Herramienta | Qué hace |
|-------------|----------|
| `consultar_registro_mercantil` | Busca un comercio por nombre o identificador en dos fuentes registrales; devuelve todas las coincidencias, sin elegir. |
| `consultar_listas_restrictivas` | Verifica un comercio o una persona; coincide solo por nombre completo o identificador. |
| `buscar_noticias` | Busca menciones en un corpus de noticias; una mención no es una coincidencia en listas. |
| `consultar_riesgo_categoria` | Devuelve el nivel de riesgo (alto, medio o bajo) de una categoría. |
| `registrar_informe` | Registra el informe con su recomendación, sus hallazgos con fuente y fecha, los conflictos y la cobertura; uno de los dos canales de decisión. Rechaza el que no tiene esa forma. |
| `escalar_a_cumplimiento` | Escala el caso con un resumen autosuficiente; el otro canal de decisión. |

- **Antes de abrir Claude Code**: ejecute `uv sync`. El servidor se lanza con
  `uv run --quiet python -m servidor_mcp`; abra Claude Code **siempre en la raíz** del repositorio.
- **Comprobarlo**: en una sesión nueva, `/mcp` debe mostrar `github` y `pasarela` conectados, sin
  pedir aprobación, y las seis herramientas `mcp__pasarela__*`.
- **`PASARELA_FALLA_NOTICIAS=1`** simula la caída del servicio de noticias: `buscar_noticias`
  devuelve un error reintentable y las demás herramientas siguen respondiendo. Se lee en cada
  llamada, pero un servidor ya lanzado hereda el entorno de Claude Code al arrancar.
- **`PASARELA_FALLA_REGISTRO=1`** (desde el #9) simula, igual, la caída del registro mercantil:
  `consultar_registro_mercantil` devuelve `servicio_no_disponible` reintentable y el comercio no
  queda identificado.
- **`PASARELA_RESULTADOS_DIR`** fija la carpeta de los informes y los casos escalados. Por defecto
  es `resultados/` en la raíz, que git ignora.
- **Los datos son ficticios**: nombres inventados, dominios `.example` y ningún documento, NIT o
  tarjeta con forma real. Cada archivo de `src/servidor_mcp/datos/` lo declara.

## Coordinador y subagentes

El paquete [src/due_diligence/](src/due_diligence/) es el núcleo multi-agente del ticket #6. Un
coordinador recibe la solicitud del analista y delega cada frente (registro mercantil, listas
restrictivas, noticias y riesgo de categoría) en un subagente con su propio `query()` del Claude
Agent SDK. El coordinador solo tiene la herramienta `delegar_frente` y las dos de decisión; cada
subagente, solo la herramienta de su frente y el contexto que se le pasa de forma explícita. Registro,
noticias y categoría corren en paralelo; listas espera al registro y consulta al comercio y a su
representante legal tal como los devolvió el registro. Las decisiones están en
[specs/006-coordinador-subagentes-agent/](specs/006-coordinador-subagentes-agent/).

- **Ejecutar un caso con el modelo real** (gasta tokens; desde el #10, `--sin-continuar` para no preguntar al analista):
  `uv run python -m due_diligence "<solicitud del analista>"`. Imprime los eventos con su hora, la
  situación de cada frente, la duración de cada uno, si hubo solape, el coste y la respuesta del
  coordinador. **Coste**: en la validación real del #6, un caso completo con Sonnet 5.5 en los cinco agentes costó unos 0,06 USD, sin
  diferencia apreciable entre frío y caliente; con Opus 5.5, que cuesta el doble por token, se estima en unos 0,12 USD. Sale con 0 si el ciclo terminó con una razón de parada normal, 1 si no y 2 sin solicitud.
- **Modelos**: por defecto `claude-opus-5-5` en el coordinador y en los cuatro subagentes (desde el
  #7); `PASARELA_MODELO_COORDINADOR` y `PASARELA_MODELO_SUBAGENTES` permiten cambiarlo, por ejemplo a
  `claude-sonnet-5-5`. El límite de 30 turnos es solo una protección de seguridad: el ciclo termina
  por la razón de parada del modelo.
- **Credenciales**: el modelo se autentica con `ANTHROPIC_API_KEY`, que cargan desde `.env` (con
  python-dotenv, sin pisar el entorno) los dos puntos de entrada: `__main__` y la interfaz de chat.
  Los dos la comprueban con la misma función (`comprobar_credencial`, desde el #11) y se detienen
  con un mensaje si falta o si hay otra credencial que se usaría en su lugar; la línea de comandos
  sale entonces con 2. Los tests no cargan el archivo ni llaman al modelo.
- **Sondeo de aislamiento** (manual, gasta tokens): `uv run python -m due_diligence.sondeo_aislamiento`
  comprueba que ni `CLAUDE.md` ni los hooks del repositorio llegan a los agentes;
  `--herramientas` lista las herramientas iniciales de cada agente y `--limite` provoca el límite de turnos.
- **Tests**: `uv run pytest src/due_diligence` usa un ejecutor simulado ([simulacion.py](src/due_diligence/simulacion.py)).
- **Reglas de negocio con hooks** (ticket #7, [specs/007-hooks-sdk-reglas/](specs/007-hooks-sdk-reglas/)):
  las reglas 1, 2 y 3 las hacen cumplir hooks del Agent SDK, no el prompt. Listas solo se consulta
  con el comercio identificado de forma unívoca en el registro; una coincidencia en listas, o una
  categoría de alto riesgo, impide recomendar habilitar y obliga a escalar con
  `escalar_a_cumplimiento`; el coordinador no puede terminar un caso que requiere escalamiento sin
  escalar. El informe solo admite las recomendaciones `habilitar`, `no_habilitar` y
  `decide_cumplimiento`. Cada bloqueo deja un evento con la regla y el motivo, que `python -m
  due_diligence` imprime junto a si el caso quedó completo.
- **Modo de demostración**: con `PASARELA_MODO_DEMO_HOOKS=1` se quitan del prompt del coordinador la
  regla de las varias coincidencias y la guía de escalar, para que el modelo pueda intentar las
  acciones prohibidas y se vea que el hook las bloquea. **No desactiva ningún hook** y no es una
  configuración normal: sirve para demostrar y probar que las reglas no dependen del prompt.
  Ejemplo: `PASARELA_MODO_DEMO_HOOKS=1 uv run python -m due_diligence "<solicitud>"`.
- **Sondeo de los hooks** (manual, gasta tokens, unos 0,02 USD): `uv run python -m
  due_diligence.sondeo_hooks` repite lo medido con el SDK (forma de `tool_response`, vía de los
  errores estructurados, qué pasa si un hook falla, el `Stop` con `block`; desde el #8,
  `updatedInput` y los turnos de un reintento) y prueba los hooks del caso con una sesión real,
  incluida la cobertura que llega a `registrar_informe` y `escalar_a_cumplimiento`. Sale con 0 si
  todo coincide, 1 si algo difiere y 2 si solo hay mediciones inconclusas.
- **Fallas de una fuente y cobertura** (ticket #8,
  [specs/008-errores-estructurados-cobertura/](specs/008-errores-estructurados-cobertura/)): una
  falla en un frente no detiene el caso.
  - El coordinador recibe un error estructurado: frente, causa, lo que se alcanzó a obtener y si
    se puede reintentar.
  - Con `reintentable: true` puede volver a delegar ese frente **una vez** con la misma entrada; el
    código no vuelve a ejecutar lo que no es reintentable.
  - La cobertura (qué frentes quedaron cubiertos y cuáles no, con su motivo) la calcula el sistema.
    Es la que se registra en el informe y en el escalamiento, aunque el modelo declare otra, y
    `python -m due_diligence` la muestra junto a los turnos usados del coordinador. Un caso con un
    frente sin cubrir nunca figura como completo.
  - Para verlo: `PASARELA_FALLA_NOTICIAS=1 uv run python -m due_diligence "<solicitud>"`. Noticias
    falla, el coordinador puede reintentarlo una vez y el informe se entrega declarando noticias
    como no cubierto.
- **Informe con procedencia y conflictos** (ticket #9,
  [specs/009-informe-procedencia-conflictos/](specs/009-informe-procedencia-conflictos/)):
  - Cada afirmación del informe lleva su fuente y su fecha, y la fuente debe haberse consultado
    para ese frente. Un informe que no cumple se rechaza con un error estructurado que dice qué
    falla.
  - El comercio, los conflictos y la cobertura los pone el sistema. Si dos fuentes registrales
    dicen cosas distintas (por ejemplo, la fecha de constitución), el informe muestra los dos
    valores, cada uno con su fuente y su fecha, sin elegir.
  - Todo caso con comercio identificado, o con el registro caído, termina con un informe vigente
    registrado; si hay que escalar, el informe va después del escalamiento.
  - `python -m due_diligence` muestra la hora de los eventos en UTC (la traza y los registros
    siguen en UTC; desde el #11 la interfaz de chat las muestra en hora de Colombia), la acción intentada de cada
    bloqueo, el bloque **Conflictos** (el resumen y una línea por dato con cada valor, su fuente y
    su fecha) y los **Informes registrados**, con su recomendación y si siguen vigentes.
  - Para ver el registro caído: `PASARELA_FALLA_REGISTRO=1 uv run python -m due_diligence
    "<solicitud>"`. El informe lleva el comercio pedido con `verificado: false`.
- **Escalamiento con criterio, resumen al oficial y ambigüedad** (ticket #10,
  [specs/010-escalamiento-criterio-handoff/](specs/010-escalamiento-criterio-handoff/)):
  - **Cuándo se escala**: se escala por una coincidencia en listas o por una categoría de alto
    riesgo. Escalar un comercio de bajo riesgo sin ningún hallazgo se rechaza, y
    `decide_cumplimiento` exige haber escalado antes.
  - **El resumen al oficial**: lleva el comercio, las afirmaciones de cada frente con su fuente y
    su fecha, la cobertura, la causa, la acción recomendada y los conflictos. Se valida como el
    informe. El comercio, la cobertura, la causa y los conflictos los pone el sistema; el oficial
    no ve la conversación.
  - **Varios comercios parecidos**: el coordinador pide el identificador y termina su turno sin
    escalar ni registrar el informe. Lo mismo si no hay ninguno, o si la categoría que intentó no
    la dio el analista. La categoría delegada tiene que aparecer en los mensajes del analista.
  - **Continuar la conversación**: cuando el caso espera al analista, `python -m due_diligence`
    lo pregunta en la consola. Con una respuesta, el caso continúa en el mismo estado; con una
    línea vacía, termina. `--sin-continuar` no pregunta:
    `uv run python -m due_diligence --sin-continuar "<solicitud>"`.
  - **La salida** muestra si el caso espera al analista y los **Escalamientos registrados**, con
    su id y sus causas. Desde el #11, los turnos del coordinador son los del último turno frente
    al límite de 30, y una línea vacía con la espera abierta avisa de que el coordinador sigue
    esperando antes de terminar.

## Interfaz de chat

La forma normal de usar el sistema (ticket #11,
[specs/011-interfaz-chat/](specs/011-interfaz-chat/)). Se ven los mensajes del analista y las
respuestas del coordinador, turno a turno, y lo que hizo el sistema en cada turno.

**Arrancar.** Copie `.env.example` como `.env` en la raíz y ponga su clave en `ANTHROPIC_API_KEY`
(solo en `.env`, que git ignora). Después:

```bash
uv run streamlit run src/due_diligence/chat.py
```

Sin la clave, o con una credencial alternativa definida (`ANTHROPIC_AUTH_TOKEN`,
`CLAUDE_CODE_USE_BEDROCK` o `CLAUDE_CODE_USE_VERTEX`), la aplicación se detiene con un mensaje
que explica qué hacer; reiníciela después de corregirlo. Cada caso gasta tokens: del orden de 0,15
a 0,30 USD con Opus 5.5.

**Qué se ve en cada turno**, en este orden:
1. El mensaje del analista.
2. Los **indicadores**, a medida que ocurren dentro de «El coordinador está trabajando…»:
   - ➡️ cada delegación en un subagente, con su frente;
   - ⛔ cada bloqueo de una regla, con la regla, la acción intentada y el motivo;
   - 📝 cada informe registrado;
   - 🚩 cada escalamiento a cumplimiento;
   - ⚠️ el fallo de un control de las reglas.

   Salen de la traza del caso, no del texto del modelo, con la hora de Colombia.
3. La **cobertura** de los cuatro frentes calculada por el sistema, con el motivo de los que no
   se cubrieron, y el **estado del caso** (completo, incompleto o esperando al analista), siempre
   **antes** de la respuesta del coordinador.
4. La respuesta del coordinador y los turnos que usó en ese turno, frente al límite de 30.

**Varios turnos.** Si el caso espera al analista (el identificador, un nombre válido o la
categoría) o quedó incompleto, el mensaje siguiente continúa el mismo caso. Si el caso quedó
**completo**, el mensaje siguiente inicia uno nuevo y la conversación lo dice. «Caso nuevo»
empieza otro en cualquier momento. Un mensaje con solo espacios mientras el coordinador espera se
avisa y no se envía. Recargar la página pierde el caso.

**Modos de simulación.** Se activan con una variable de entorno **al arrancar**; para cambiarlos
hay que detener la aplicación y arrancarla de nuevo. Cuando hay uno activo, una franja lo indica
arriba de la conversación.

| Modo | PowerShell | bash |
|------|-----------|------|
| Caída de noticias (caso f) | `$env:PASARELA_FALLA_NOTICIAS="1"; uv run streamlit run src/due_diligence/chat.py` | `PASARELA_FALLA_NOTICIAS=1 uv run streamlit run src/due_diligence/chat.py` |
| Demostración de hooks (caso e) | `$env:PASARELA_MODO_DEMO_HOOKS="1"; uv run streamlit run src/due_diligence/chat.py` | `PASARELA_MODO_DEMO_HOOKS=1 uv run streamlit run src/due_diligence/chat.py` |

En PowerShell la variable queda en la sesión: quítela con `Remove-Item Env:PASARELA_FALLA_NOTICIAS`
(o `Env:PASARELA_MODO_DEMO_HOOKS`) antes de volver al arranque normal. El modo de demostración
quita las reglas de las instrucciones del coordinador, pero **no desactiva ningún hook**.

**Los siete casos de prueba desde el chat.** Pulse «Caso nuevo» entre uno y otro.

| Caso | Arranque | Mensaje(s) | Lo que se debe ver |
|------|----------|-----------|--------------------|
| (a) alto riesgo | normal | «Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren procesar ventas en línea de suplementos dietarios. ¿Lo podemos habilitar esta semana?» | Delegaciones a los cuatro subagentes, «Caso escalado a cumplimiento» por categoría de alto riesgo, informe `decide_cumplimiento`, estado «Completo». |
| (b) bajo riesgo sin hallazgos | normal | «Necesito el due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, categoría ropa y accesorios.» | Cuatro frentes cubiertos, informe `habilitar`, ningún escalamiento, estado «Completo». |
| (c) representante en listas | normal | «Necesito el due diligence de Panadería Luna Nueva SAS, identificador ficticio CO-PL-0003, categoría restaurantes y alimentos preparados.» | Escalamiento por la coincidencia del representante legal en listas; el informe no recomienda `habilitar`. |
| (d) nombres casi idénticos | normal | 1) «Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios.» 2) «CO-AM-0004» | Turno 1: sin delegación a listas, estado «Esperando al analista» (identificador). Turno 2: delegación a listas e informe registrado. |
| (e) listas sin identificación | demostración de hooks | el mensaje 1) del caso (d) | Franja del modo de demostración; si el coordinador intenta consultar listas, «Bloqueado por la regla I.1»; estado «Esperando al analista». |
| (f) noticias caído | caída de noticias | el mensaje del caso (b) | Franja de la caída; la cobertura dice «noticias: no cubierto» con el motivo, antes de la respuesta; estado «Incompleto». |
| (g) fechas distintas | normal | «Necesito el due diligence de Ferretería Río Fino SAS, identificador ficticio CO-RF-0006, categoría electrodomésticos.» | Informe con el conflicto de la fecha de constitución: las dos fechas, cada una con su fuente, sin elegir. |

## Guardas del entorno

Claude Code trabaja con cuatro guardas y un hook de formato, registrados en
[.claude/settings.json](.claude/settings.json). Las decisiones están en la entrada 4 de
[DECISIONES.md](DECISIONES.md).

- **`guarda_secretos`**: bloquea leer, buscar, editar o escribir `.env`, `.env.*` (salvo
  `.env.example`), `*.key` y `secrets/`, también desde la terminal y desde código en línea.
- **`guarda_datos`**: bloquea escribir, ejecutar o publicar en GitHub tarjetas, NIT,
  cédulas o credenciales con forma real.
- **`guarda_spec_previa`**: bloquea escribir, borrar o restaurar código protegido
  (`src/**/*.py`, `.claude/hooks/`, `.claude/settings.json`, `.claude/settings.local.json`,
  `.mcp.json` y el plugin) si la rama no es de un ticket o le faltan la spec, el plan o
  las tareas. `.claude/settings.local.json`, que no se versiona y puede desactivar las
  guardas, se bloquea en cualquier rama; solo se edita fuera de Claude Code.
- **`guarda_mcp_github`**: limita `projects_write` del MCP de GitHub a mover tarjetas
  (`update_project_item`).
- **`formatear_python`**: formatea con ruff cada `.py` escrito o editado; nunca bloquea.

Las guardas requieren `uv` en el `PATH`. Se cargan al iniciar la sesión y suelen
activarse también al guardar `settings.json`; ante la duda, reinicie la sesión.

- Ejecute `uv sync` antes de abrir Claude Code.
- Con las guardas activas, no cambie a una rama sin `.claude/hooks/`; si ocurre, reinicie
  la sesión.

## Cómo se trabaja

Las convenciones del equipo están en [CLAUDE.md](CLAUDE.md) y se cargan solas en cada sesión
de Claude Code. Cada ticket es un issue del Project, con su propia rama, su especificación,
plan y tareas en [specs/](specs/), y un pull request que cierra el issue. Las preferencias
personales van en `CLAUDE.local.md` y `.claude/settings.local.json`, que git ignora.

### Ciclo de un ticket

```text
/siguiente-ticket → specify → (clarify) → plan → tasks → analyze → implement → (converge) → /abrir-pr → merge
```

- **`/siguiente-ticket [N]`**: hace tres cosas.
  - Registra el cierre de los tickets ya fusionados.
  - Toma el siguiente ticket en Todo, o el #N, y lo pasa a In Progress.
  - Comenta el inicio en el issue y crea la rama `NNN-nombre-corto` y `specs/NNN-*`.
- **Hooks de `.specify/extensions.yml`**: al terminar specify, clarify, plan y analyze,
  `/comentar-avance` deja en el issue lo especificado, lo decidido y lo encontrado.
- **`/abrir-pr`**:
  - Comprueba que la spec, el plan y las tareas están commiteados.
  - Ejecuta la revisión independiente y la auditoría de las reglas de negocio, dos subagentes de
    solo lectura en contexto separado, y registra el veredicto del commit revisado.
  - Un hook bloquea crear el PR, por el MCP de GitHub o por `gh`, si no hay un veredicto
    aprobado del commit actual publicado en la rama.
  - Abre el PR con `Closes #N` y pasa el ticket a In review.
- **Done**: lo hace el workflow "Item closed" del Project al fusionar. El siguiente
  `/siguiente-ticket` registra ese cierre en el issue. Tras el merge del último ticket,
  ejecútelo una vez más para registrarlo.
