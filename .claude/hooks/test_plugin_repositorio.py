"""El plugin `guardas-y-revision` visto desde este repositorio (#13).

- FR-004 y SC-002: ningún archivo del plugin ni del marketplace contiene términos de este
  proyecto. La lista vive aquí, fuera del plugin (R11).
- FR-009 y SC-003: la guarda de datos se ejecuta una sola vez por acción con la configuración
  versionada; el plugin está deshabilitado aquí y su registro equivale al de `settings.json`
  (R3).
- R2: `base_guarda.py` del plugin y `comun.py` del repositorio dan el mismo resultado en las
  funciones que comparten.
"""

import io
import json
import re
import subprocess
import sys
from pathlib import Path

import base_guarda
import comun
import pytest

RAIZ = Path(__file__).resolve().parents[2]
PLUGIN = RAIZ / "plugins" / "guardas-y-revision"
MARKETPLACE = RAIZ / ".claude-plugin" / "marketplace.json"
CONFIGURACION = json.loads((RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8"))
HOOKS_PLUGIN = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
ID_PLUGIN = "guardas-y-revision@piezas-reutilizables"

# --- FR-004: términos del proyecto (R11) ---------------------------------------------------

TERMINOS = {
    "nombre de la pasarela": r"pasarela\s+austral",
    "due diligence": r"due[\s-]diligence",
    "identificador ficticio del proyecto": r"\bCO-[A-Z]{2}-\d{4}\b",
    "ruta de código": r"(?<![\w/])src/",
    "carpeta de specs de un ticket": r"specs/0\d\d",
    "documento de decisiones": r"DECISIONES",
    "guardas del repositorio": r"\.claude/hooks",
    "enunciado": r"docs/enunciado",
    "configuración MCP del proyecto": r"\.mcp\.json",
    "servidor del proyecto": r"servidor_mcp",
    "comando propio": r"/abrir-pr|/siguiente-ticket|comentar-avance|auditar-cumplimiento",
    "veredicto": r"veredicto",
    "referencia a un ticket": r"(?<![\w&#])#\d+\b",
}
MUESTRAS = {
    "nombre de la pasarela": "la Pasarela Austral",
    "due diligence": "un due diligence",
    "identificador ficticio del proyecto": "CO-TV-0001",
    "ruta de código": "ver src/a.py",
    "carpeta de specs de un ticket": "specs/012-suite/spec.md",
    "documento de decisiones": "en DECISIONES.md",
    "guardas del repositorio": "en .claude/hooks/x.py",
    "enunciado": "docs/enunciado.md",
    "configuración MCP del proyecto": "el .mcp.json",
    "servidor del proyecto": "python -m servidor_mcp",
    "comando propio": "usa /abrir-pr",
    "veredicto": "el veredicto del commit",
    "referencia a un ticket": "como en el #4",
}
SOLO_RAIZ_DEL_PLUGIN = {"hooks/hooks.json", "skills/revisar-codigo/SKILL.md"}


def archivos_del_plugin() -> list[Path]:
    salida = subprocess.run(
        ["git", "-C", str(RAIZ), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
        + ["plugins/", ".claude-plugin/"],
        capture_output=True,
        check=True,
    ).stdout
    return [RAIZ / r for r in salida.decode("utf-8").split("\0") if r]


def hallazgos(ruta: Path, relativa: str) -> list[str]:
    encontrados = []
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        for nombre, patron in TERMINOS.items():
            if re.search(patron, linea, re.IGNORECASE):
                encontrados.append(f"{relativa}:{numero}:{nombre}")
        if relativa in SOLO_RAIZ_DEL_PLUGIN and "CLAUDE_PROJECT_DIR" in linea:
            encontrados.append(f"{relativa}:{numero}:CLAUDE_PROJECT_DIR")
    return encontrados


def test_ningun_archivo_del_plugin_tiene_terminos_del_proyecto():
    archivos = archivos_del_plugin()
    assert MARKETPLACE in archivos and PLUGIN / ".claude-plugin" / "plugin.json" in archivos
    encontrados = []
    for ruta in archivos:
        if ruta.suffix in {".py", ".md", ".json"}:
            relativa = ruta.relative_to(PLUGIN if PLUGIN in ruta.parents else RAIZ).as_posix()
            encontrados += hallazgos(ruta, relativa)
    assert encontrados == [], "Términos del proyecto en el plugin:\n" + "\n".join(encontrados)


@pytest.mark.parametrize("nombre", sorted(TERMINOS))
def test_cada_termino_detecta_su_muestra(nombre):
    assert re.search(TERMINOS[nombre], MUESTRAS[nombre], re.IGNORECASE)


@pytest.mark.parametrize("relativa", sorted(SOLO_RAIZ_DEL_PLUGIN))
def test_la_raiz_del_proyecto_esta_prohibida_en_el_hook_y_la_skill(tmp_path, relativa):
    muestra = tmp_path / "muestra"
    muestra.write_text("${CLAUDE_PROJECT_DIR}/x.py\n", encoding="utf-8")
    assert hallazgos(muestra, relativa) == [f"{relativa}:1:CLAUDE_PROJECT_DIR"]


def test_el_hook_y_la_skill_solo_construyen_rutas_con_la_raiz_del_plugin():
    for relativa in SOLO_RAIZ_DEL_PLUGIN:
        texto = (PLUGIN / relativa).read_text(encoding="utf-8")
        variables = set(re.findall(r"\$\{([A-Z_]+)\}", texto))
        assert variables == {"CLAUDE_PLUGIN_ROOT"}, (relativa, variables)
        assert not re.search(r"[A-Za-z]:[\\/]|\.\./", texto), relativa


def test_el_marketplace_lista_el_plugin_desde_su_carpeta():
    datos = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    manifiesto = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text("utf-8"))
    assert datos["name"] == "piezas-reutilizables"
    assert datos["owner"]["name"]
    (entrada,) = datos["plugins"]
    assert entrada["name"] == manifiesto["name"] == "guardas-y-revision"
    assert entrada["source"] == "./plugins/guardas-y-revision"
    assert entrada["description"] == manifiesto["description"]


# --- FR-009: una sola ejecución por acción (R3) ---------------------------------------------

PUBLICACION = [
    "add_issue_comment",
    "update_issue_comment",
    "create_pull_request",
    "update_pull_request",
    "issue_write",
    "add_reply_to_pull_request_comment",
    "pull_request_review_write",
    "add_comment_to_pending_review",
]
HERRAMIENTAS = (
    ["Write", "Edit", "NotebookEdit", "Bash", "PowerShell"]
    + [f"mcp__github__{h}" for h in PUBLICACION]
    + [f"mcp__plugin_github_github__{h}" for h in PUBLICACION]
)


def acepta(matcher: str, herramienta: str) -> bool:
    """Como Claude Code: lista de nombres exactos o, si hay otros caracteres, expresión."""
    if re.fullmatch(r"[A-Za-z0-9_|]+", matcher):
        return herramienta in matcher.split("|")
    return re.search(matcher, herramienta) is not None


def ejecuciones_de_la_guarda(herramienta: str) -> int:
    return sum(
        1
        for entrada in CONFIGURACION["hooks"]["PreToolUse"]
        if acepta(entrada["matcher"], herramienta)
        for hook in entrada["hooks"]
        if hook["args"][-1].endswith("/guarda_datos.py")
    )


@pytest.mark.parametrize("herramienta", HERRAMIENTAS)
def test_la_guarda_se_ejecuta_una_sola_vez_por_herramienta(herramienta):
    assert ejecuciones_de_la_guarda(herramienta) == 1


def test_el_plugin_esta_deshabilitado_en_este_repositorio():
    assert CONFIGURACION["enabledPlugins"][ID_PLUGIN] is False
    assert "extraKnownMarketplaces" not in CONFIGURACION


def registro(entradas: list[dict]) -> tuple[str, dict]:
    (par,) = [
        (e["matcher"], h)
        for e in entradas
        for h in e["hooks"]
        if h["args"][-1].endswith("/guarda_datos.py")
    ]
    return par


def test_el_registro_del_plugin_equivale_al_del_repositorio():
    matcher_repo, hook_repo = registro(CONFIGURACION["hooks"]["PreToolUse"])
    matcher_plugin, hook_plugin = registro(HOOKS_PLUGIN["hooks"]["PreToolUse"])
    assert matcher_repo == matcher_plugin
    for campo in ("type", "command", "timeout", "onFailure"):
        assert hook_repo[campo] == hook_plugin[campo], campo
    assert hook_repo["args"][:-1] == hook_plugin["args"][:-1]
    assert (
        hook_repo["args"][-1]
        == "${CLAUDE_PROJECT_DIR}/plugins/guardas-y-revision/hooks/guarda_datos.py"
    )
    assert hook_plugin["args"][-1] == "${CLAUDE_PLUGIN_ROOT}/hooks/guarda_datos.py"


def test_la_guarda_tiene_una_sola_fuente():
    assert not (RAIZ / ".claude" / "hooks" / "detector_datos.py").exists()
    assert (PLUGIN / "hooks" / "detector_datos.py").is_file()
    assert (PLUGIN / "hooks" / "guarda_datos.py").is_file()


# --- R2: base_guarda equivale a comun en lo que comparten ------------------------------------


def casos_de_rutas(raiz: Path) -> list[tuple[str, Path, Path | None]]:
    return [
        ("lib\\a\\b.py", raiz, None),
        (str(raiz / "lib" / "b.py"), raiz, None),
        ("../x.py", raiz, raiz / "lib"),
        (str(raiz.parent / "fuera.txt"), raiz, None),
        (str(raiz).upper() + "/lib/B.py", Path(str(raiz).lower()), None),
        ("/c/Users/x/a.py", raiz, None),
        ("a.py", raiz, None),
    ]


def test_normalizar_ruta_es_igual(tmp_path):
    for ruta, base, cwd in casos_de_rutas(tmp_path):
        assert base_guarda.normalizar_ruta(ruta, base, cwd) == comun.normalizar_ruta(
            ruta, base, cwd
        ), ruta


@pytest.mark.parametrize("proyecto", [None, "otro"])
@pytest.mark.parametrize("entrada", [{"cwd": "c1"}, {}])
def test_raiz_y_cwd_son_iguales(tmp_path, monkeypatch, proyecto, entrada):
    if proyecto:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / proyecto))
    else:
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert base_guarda.raiz(entrada) == comun.raiz(entrada)
    assert base_guarda.cwd(entrada, tmp_path) == comun.cwd(entrada, tmp_path)


@pytest.mark.parametrize("texto", ['{"a": 1}', "[1]", "no es json"])
def test_leer_entrada_es_igual(texto):
    def resultado(modulo):
        try:
            return ("ok", modulo.leer_entrada(io.StringIO(texto)))
        except Exception as error:  # noqa: BLE001 - se compara el tipo de error
            return ("error", type(error).__name__)

    assert resultado(base_guarda) == resultado(comun)


def ejecutar_en_subproceso(modulo: str, cuerpo: str, entrada: str) -> tuple[int, str, str]:
    codigo = (
        f"import sys; sys.path[:0] = {[str(PLUGIN / 'hooks'), str(RAIZ / '.claude' / 'hooks')]!r}\n"
        f"import {modulo} as m\n{cuerpo}\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", codigo],
        input=entrada,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return r.returncode, r.stdout, r.stderr


@pytest.mark.parametrize(
    ("cuerpo", "entrada"),
    [
        ("m.bloquear('g', 'motivo  con\\n espacios')", ""),
        ("m.ejecutar('g', lambda e: None)", '{"a": 1}'),
        ("m.ejecutar('g', lambda e: m.bloquear('g', 'no'))", '{"a": 1}'),
        ("m.ejecutar('g', lambda e: 1 / 0)", '{"a": 1}'),
        ("m.ejecutar('g', lambda e: None)", "no es json"),
    ],
)
def test_bloquear_y_ejecutar_son_iguales(cuerpo, entrada):
    assert ejecutar_en_subproceso("base_guarda", cuerpo, entrada) == ejecutar_en_subproceso(
        "comun", cuerpo, entrada
    )
