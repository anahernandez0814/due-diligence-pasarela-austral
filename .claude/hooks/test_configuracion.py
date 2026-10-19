"""Invariantes de .claude/settings.json (FR-003, FR-016, FR-017, FR-022, R3, R6, R14).

Comprueba que los hooks y las reglas de la capa de permisos existen y están bien
formados, según contracts/settings-json.md. Su efecto se ve en la sesión (quickstart Q1 y
Q13); las guardas se prueban por stdin en sus propios tests.
"""

import fnmatch
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CONFIGURACION = json.loads((RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8"))
HOOKS = CONFIGURACION["hooks"]
DENY = CONFIGURACION["permissions"]["deny"]

GUARDAS = {
    "guarda_secretos.py",
    "guarda_datos.py",
    "guarda_spec_previa.py",
    "guarda_mcp_github.py",
    "guarda_pr.py",
}
MCP_DENEGADAS = {
    "mcp__github__delete_repository",
    "mcp__github__delete_file",
    "mcp__github__create_or_update_file",
    "mcp__github__push_files",
    "mcp__github__merge_pull_request",
    "mcp__github__create_repository",
    "mcp__github__fork_repository",
}
USAN_EL_MCP = [
    ".claude/skills/siguiente-ticket/SKILL.md",
    ".claude/commands/abrir-pr.md",
    ".claude/commands/comentar-avance.md",
]


def entradas(evento: str) -> list[tuple[str, dict]]:
    return [(e["matcher"], h) for e in HOOKS[evento] for h in e["hooks"]]


# #13 (R2, R5): la guarda de datos vive en el plugin y su matcher es una expresión anclada que
# acepta las herramientas de publicación de cualquier servidor MCP.
RUTA_GUARDA_DATOS = "${CLAUDE_PROJECT_DIR}/plugins/guardas-y-revision/hooks/guarda_datos.py"
MATCHER_GUARDA_DATOS = (
    "^(Write|Edit|NotebookEdit|Bash|PowerShell|mcp__.+__(add_issue_comment|update_issue_comment"
    "|create_pull_request|update_pull_request|issue_write|add_reply_to_pull_request_comment"
    "|pull_request_review_write|add_comment_to_pending_review))$"
)


def ruta(hook: dict) -> Path:
    return Path(hook["args"][-1].replace("${CLAUDE_PROJECT_DIR}", str(RAIZ)))


def script(hook: dict) -> str:
    return ruta(hook).name


# --- Hooks ----------------------------------------------------------------------------


def test_hay_cinco_guardas_previas_y_un_formato_posterior():
    assert {script(h) for _, h in entradas("PreToolUse")} == GUARDAS
    assert [script(h) for _, h in entradas("PostToolUse")] == ["formatear_python.py"]


@pytest.mark.parametrize("evento", ["PreToolUse", "PostToolUse"])
def test_matchers_son_listas_de_nombres_exactos(evento):
    for matcher, hook in entradas(evento):
        if script(hook) == "guarda_datos.py":
            continue  # expresión anclada (#13, R5): test_matcher_de_la_guarda_de_datos
        assert re.fullmatch(r"[A-Za-z0-9_|]+", matcher), matcher


def test_matcher_de_la_guarda_de_datos_es_la_expresion_anclada():
    matchers = [m for m, h in entradas("PreToolUse") if script(h) == "guarda_datos.py"]
    assert matchers == [MATCHER_GUARDA_DATOS]


def test_guardas_bloquean_si_fallan_con_timeout_de_10():
    for _, hook in entradas("PreToolUse"):
        assert hook["onFailure"] == "block", script(hook)
        assert hook["timeout"] <= 10, script(hook)


def test_formato_continua_si_falla():
    for _, hook in entradas("PostToolUse"):
        assert hook["onFailure"] == "continue"


@pytest.mark.parametrize("evento", ["PreToolUse", "PostToolUse"])
def test_forma_exec_con_uv_sin_proyecto(evento):
    for _, hook in entradas(evento):
        assert hook["type"] == "command"
        assert hook["command"] == "uv"
        assert hook["args"][:-1] == ["run", "--no-project", "--python", "3.12", "--quiet"]
        if script(hook) == "guarda_datos.py":
            assert hook["args"][-1] == RUTA_GUARDA_DATOS
        else:
            assert hook["args"][-1].startswith("${CLAUDE_PROJECT_DIR}/.claude/hooks/")


@pytest.mark.parametrize("evento", ["PreToolUse", "PostToolUse"])
def test_cada_script_existe(evento):
    for _, hook in entradas(evento):
        assert ruta(hook).is_file(), script(hook)


def test_powershell_esta_en_los_matchers_de_respaldo():
    por_script = {script(h): m.split("|") for m, h in entradas("PreToolUse")}
    for guarda in ("guarda_secretos.py", "guarda_datos.py", "guarda_spec_previa.py"):
        assert "PowerShell" in por_script[guarda]


# --- Denegaciones ---------------------------------------------------------------------


def test_exactamente_59_denegaciones():
    assert len(DENY) == 59
    assert len(set(DENY)) == 59


def test_sin_reglas_de_powershell_ni_de_grep():
    assert not [r for r in DENY if r.startswith(("PowerShell(", "Bash(grep"))]


@pytest.mark.parametrize("herramienta", ["Read", "Edit"])
def test_excepcion_de_env_example_va_detras_de_su_regla(herramienta):
    assert DENY.index(f"{herramienta}(!**/.env.example)") > DENY.index(f"{herramienta}(**/.env.*)")


def _patron_de_bash(regla: str) -> re.Pattern:
    interior = regla.removeprefix("Bash(").removesuffix(")")
    return re.compile(".*".join(re.escape(parte) for parte in interior.split("*")))


def test_ninguna_regla_de_bash_bloquea_cat_env_example():
    reglas = [r for r in DENY if r.startswith("Bash(")]
    assert len(reglas) == 40
    assert not [r for r in reglas if _patron_de_bash(r).fullmatch("cat .env.example")]


@pytest.mark.parametrize(
    "comando", ["cat .env", "head .env.local", "cp secrets/a.txt x", "source .env", "tail x.key"]
)
def test_las_reglas_de_bash_cubren_los_secretos(comando):
    assert any(_patron_de_bash(r).fullmatch(comando) for r in DENY if r.startswith("Bash("))


@pytest.mark.parametrize("herramienta", ["Read", "Edit"])
def test_ninguna_regla_de_archivo_deja_fuera_env_example(herramienta):
    # La última regla que coincide decide: debe ser la excepción con `!`.
    decision = None
    for regla in DENY:
        m = re.fullmatch(rf"{herramienta}\((!?)(.+)\)", regla)
        if m and fnmatch.fnmatchcase("carpeta/.env.example", m.group(2)):
            decision = m.group(1) == "!"
    assert decision is True


def test_settings_local_no_se_edita_desde_claude_code():
    assert "Edit(/.claude/settings.local.json)" in DENY


def test_estan_las_7_herramientas_mcp():
    assert MCP_DENEGADAS == {r for r in DENY if r.startswith("mcp__")}


@pytest.mark.parametrize("archivo", USAN_EL_MCP)
def test_las_herramientas_que_usa_el_proyecto_no_se_deniegan(archivo):
    texto = (RAIZ / archivo).read_text(encoding="utf-8")
    usadas = set(re.findall(r"mcp__github__\w+", texto))
    assert usadas, archivo
    assert usadas.isdisjoint(DENY), usadas & set(DENY)


# --- Reglas por ruta (FR-018, FR-019, R13) --------------------------------------------


def frontmatter_paths(archivo: Path) -> list[str]:
    """Los elementos de `paths` del frontmatter YAML, sin dependencias externas.

    Solo admite la forma del proyecto: `paths:` seguida de una lista de cadenas entre
    comillas dobles, todo entre las dos primeras líneas `---`.
    """
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    assert lineas[0] == "---", f"{archivo.name}: no empieza por ---"
    cierre = lineas.index("---", 1)
    cabecera = lineas[1:cierre]
    assert cabecera[0] == "paths:", f"{archivo.name}: falta paths"
    elementos = []
    for linea in cabecera[1:]:
        m = re.fullmatch(r'  - "([^"]+)"', linea)
        assert m, f"{archivo.name}: elemento de paths mal formado: {linea!r}"
        elementos.append(m.group(1))
    return elementos


@pytest.mark.parametrize(
    ("regla", "glob"),
    [("tests.md", "**/test_*.py"), ("herramientas-mcp.md", "src/servidor_mcp/**/*.py")],
)
def test_reglas_declaran_exactamente_su_glob(regla, glob):
    assert frontmatter_paths(RAIZ / ".claude" / "rules" / regla) == [glob]


# --- Guarda de PR y directorio de veredictos (ticket #4: FR-012, FR-016, FR-020) ------

MATCHER_GUARDA_PR = "Bash|PowerShell|mcp__github__create_pull_request"
DENEGACION_VEREDICTOS = "Edit(/.claude/veredictos/**)"


def test_la_guarda_de_pr_esta_registrada_con_su_matcher_exacto():
    registradas = [(m, h) for m, h in entradas("PreToolUse") if script(h) == "guarda_pr.py"]
    assert len(registradas) == 1
    matcher, hook = registradas[0]
    assert matcher == MATCHER_GUARDA_PR
    assert hook["onFailure"] == "block"
    assert hook["timeout"] == 10
    assert hook["type"] == "command"
    assert hook["command"] == "uv"
    assert hook["args"] == [
        "run",
        "--no-project",
        "--python",
        "3.12",
        "--quiet",
        "${CLAUDE_PROJECT_DIR}/.claude/hooks/guarda_pr.py",
    ]


def test_el_matcher_de_la_guarda_de_pr_es_una_lista_de_nombres_exactos():
    assert re.fullmatch(r"[A-Za-z0-9_|]+", MATCHER_GUARDA_PR)
    assert MATCHER_GUARDA_PR.split("|") == [
        "Bash",
        "PowerShell",
        "mcp__github__create_pull_request",
    ]


def test_los_veredictos_no_se_editan_desde_claude_code():
    assert DENEGACION_VEREDICTOS in DENY
    assert DENY.index(DENEGACION_VEREDICTOS) == DENY.index("Edit(/.claude/settings.local.json)") + 1


def test_la_denegacion_de_veredictos_es_de_edicion_y_no_de_lectura():
    # Leer el directorio sigue permitido: la puerta y las personas consultan los veredictos.
    assert "Read(/.claude/veredictos/**)" not in DENY
    assert not [r for r in DENY if r.startswith("Read(") and "veredictos" in r]


def test_crear_el_pr_por_el_mcp_no_se_deniega():
    assert "mcp__github__create_pull_request" not in DENY


def test_las_entradas_de_los_hooks_de_3_no_cambian():
    esperadas = {
        "guarda_secretos.py": "Read|Write|Edit|NotebookEdit|Grep|Glob|Bash|PowerShell",
        "guarda_spec_previa.py": "Write|Edit|NotebookEdit|Bash|PowerShell",
        "guarda_mcp_github.py": "mcp__github__projects_write",
    }
    por_script = {script(h): m for m, h in entradas("PreToolUse")}
    for nombre, matcher in esperadas.items():
        assert por_script[nombre] == matcher


# --- Servidor MCP de la pasarela (ticket #5, R7, FR-016) --------------------------------------

MCP_JSON = json.loads((RAIZ / ".mcp.json").read_text(encoding="utf-8"))
PASARELA = MCP_JSON["mcpServers"].get("pasarela", {})


def test_el_servidor_de_la_pasarela_esta_aprobado_junto_al_de_github():
    # Sin esto, el servidor del proyecto queda pendiente de aprobación y no conecta (SC-007).
    assert "github" in CONFIGURACION["enabledMcpjsonServers"]
    assert "pasarela" in CONFIGURACION["enabledMcpjsonServers"]


def test_mcp_json_registra_la_pasarela_junto_a_github_por_stdio_con_uv():
    assert {"github", "pasarela"} <= set(MCP_JSON["mcpServers"])
    assert PASARELA["type"] == "stdio"
    assert PASARELA["command"] == "uv"
    assert PASARELA["args"] == ["run", "--quiet", "python", "-m", "servidor_mcp"]


def test_el_bloque_de_la_pasarela_no_lleva_variables_ni_env_ni_credenciales():
    assert PASARELA  # el bloque existe
    texto = json.dumps(PASARELA)
    assert "${" not in texto  # no se da por hecho que ${CLAUDE_PROJECT_DIR} se expanda (R7)
    assert "env" not in PASARELA
    assert not re.search(r"gh[pousr]_|github_pat_|sk-ant-|AKIA|-----BEGIN", texto)
