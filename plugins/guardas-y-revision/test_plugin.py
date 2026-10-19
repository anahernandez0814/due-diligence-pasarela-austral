"""Estructura del plugin: manifiesto, hooks.json, agente y skill."""

import json
import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent
MANIFIESTO = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
HOOKS = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
AGENTE = (PLUGIN / "agents" / "revisor-codigo.md").read_text(encoding="utf-8")
SKILL = (PLUGIN / "skills" / "revisar-codigo" / "SKILL.md").read_text(encoding="utf-8")

HERRAMIENTAS_PUBLICACION = [
    "add_issue_comment",
    "update_issue_comment",
    "create_pull_request",
    "update_pull_request",
    "issue_write",
    "add_reply_to_pull_request_comment",
    "pull_request_review_write",
    "add_comment_to_pending_review",
]
REVISADAS = ["Write", "Edit", "NotebookEdit", "Bash", "PowerShell"]
COMANDO_CONTEXTO = (
    'uv run --no-project --python 3.12 --quiet "${CLAUDE_PLUGIN_ROOT}/scripts/contexto_revision.py"'
)


def frontmatter(texto: str) -> dict[str, str]:
    """Campos de primer nivel del frontmatter YAML (`clave: valor`), sin dependencias."""
    bloque = texto.split("---", 2)[1]
    campos = {}
    for linea in bloque.splitlines():
        m = re.match(r"^([a-z-]+):\s*(.*)$", linea)
        if m:
            campos[m.group(1)] = m.group(2).strip()
    return campos


# --- Manifiesto ---------------------------------------------------------------------------


def test_manifiesto_con_nombre_version_y_descripcion_y_autor_de_equipo():
    assert MANIFIESTO["name"] == "guardas-y-revision"
    assert re.fullmatch(r"\d+\.\d+\.\d+", MANIFIESTO["version"])
    assert MANIFIESTO["description"]
    # Sin datos personales (FR-001): el autor es un equipo, sin correo ni URL.
    assert MANIFIESTO["author"] == {"name": "Equipo de plataforma"}


# --- hooks.json ---------------------------------------------------------------------------


def registro() -> tuple[str, dict]:
    (entrada,) = HOOKS["hooks"]["PreToolUse"]
    (hook,) = entrada["hooks"]
    return entrada["matcher"], hook


def test_hooks_solo_tiene_la_guarda_en_pretooluse():
    assert set(HOOKS["hooks"]) == {"PreToolUse"}
    _, hook = registro()
    assert hook["type"] == "command"
    assert hook["command"] == "uv"
    assert hook["args"] == [
        "run",
        "--no-project",
        "--python",
        "3.12",
        "--quiet",
        "${CLAUDE_PLUGIN_ROOT}/hooks/guarda_datos.py",
    ]
    assert hook["timeout"] == 10
    assert hook["onFailure"] == "block"


def test_el_script_del_hook_existe_en_el_plugin():
    _, hook = registro()
    ruta = Path(hook["args"][-1].replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN)))
    assert ruta.is_file()


@pytest.mark.parametrize(
    "herramienta",
    REVISADAS
    + [f"mcp__github__{h}" for h in HERRAMIENTAS_PUBLICACION]
    + [f"mcp__plugin_github_github__{h}" for h in HERRAMIENTAS_PUBLICACION],
)
def test_el_matcher_acepta_las_herramientas_revisadas(herramienta):
    matcher, _ = registro()
    assert re.search(matcher, herramienta)


@pytest.mark.parametrize(
    "herramienta",
    ["Read", "Grep", "Glob", "NotebookRead", "mcp__github__get_issue", "MultiEdit", "Writer"],
)
def test_el_matcher_no_acepta_otras(herramienta):
    matcher, _ = registro()
    assert not re.search(matcher, herramienta)


# --- Agente y skill --------------------------------------------------------------------------


def test_el_agente_es_de_solo_lectura():
    campos = frontmatter(AGENTE)
    assert campos["name"] == "revisor-codigo"
    assert [h.strip() for h in campos["tools"].split(",")] == ["Read", "Grep", "Glob"]


def test_el_agente_cierra_con_la_linea_resumen():
    assert "RESUMEN: bloqueantes=<N> sugerencias=<M> cobertura=<completa|incompleta>" in AGENTE
    assert "no repitas el valor" in AGENTE


def test_la_skill_lanza_el_agente_del_plugin_en_un_contexto_separado():
    campos = frontmatter(SKILL)
    assert campos["name"] == "revisar-codigo"
    assert campos["context"] == "fork"
    assert campos["agent"] == "guardas-y-revision:revisor-codigo"


def test_la_regla_de_allowed_tools_es_el_comando_de_la_linea_dinamica():
    assert f"  - Bash({COMANDO_CONTEXTO})" in SKILL
    assert f"!`{COMANDO_CONTEXTO}`" in SKILL
    assert SKILL.count("!`") == 1


def test_el_script_de_la_skill_existe_en_el_plugin():
    ruta = Path(COMANDO_CONTEXTO.split('"')[1].replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN)))
    assert ruta.is_file()


def test_sin_ticket_no_se_reduce_la_cobertura():
    for texto in (AGENTE, SKILL):
        assert "Ticket: no aplica" in texto
        assert "**no**" in texto
