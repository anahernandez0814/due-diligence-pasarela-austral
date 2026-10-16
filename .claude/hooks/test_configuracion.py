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


def script(hook: dict) -> str:
    return Path(hook["args"][-1].replace("${CLAUDE_PROJECT_DIR}", str(RAIZ))).name


# --- Hooks ----------------------------------------------------------------------------


def test_hay_cuatro_guardas_previas_y_un_formato_posterior():
    assert {script(h) for _, h in entradas("PreToolUse")} == GUARDAS
    assert [script(h) for _, h in entradas("PostToolUse")] == ["formatear_python.py"]


@pytest.mark.parametrize("evento", ["PreToolUse", "PostToolUse"])
def test_matchers_son_listas_de_nombres_exactos(evento):
    for matcher, _ in entradas(evento):
        assert re.fullmatch(r"[A-Za-z0-9_|]+", matcher), matcher


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
        assert hook["args"][-1].startswith("${CLAUDE_PROJECT_DIR}/.claude/hooks/")


@pytest.mark.parametrize("evento", ["PreToolUse", "PostToolUse"])
def test_cada_script_existe(evento):
    for _, hook in entradas(evento):
        assert (RAIZ / ".claude" / "hooks" / script(hook)).is_file(), script(hook)


def test_powershell_esta_en_los_matchers_de_respaldo():
    por_script = {script(h): m.split("|") for m, h in entradas("PreToolUse")}
    for guarda in ("guarda_secretos.py", "guarda_datos.py", "guarda_spec_previa.py"):
        assert "PowerShell" in por_script[guarda]


# --- Denegaciones ---------------------------------------------------------------------


def test_exactamente_58_denegaciones():
    assert len(DENY) == 58
    assert len(set(DENY)) == 58


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
