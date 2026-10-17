"""Pruebas de guarda_pr.py (R9, R10, FR-012 a FR-014, FR-016; contracts/veredicto-y-guarda.md).

Cada prueba crea un repositorio git con un `origin` local en `tmp_path`. Los veredictos los
escribe `veredicto.py`, como en uso real; los tests no usan datos reales.
"""

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import guarda_pr
import pytest
import veredicto
from repositorio_pruebas import confirmar, copiar_plantilla, crear_repo, escribir, git

SCRIPT = Path(__file__).with_name("guarda_pr.py")
LIMPIO = "RESUMEN: bloqueantes=0 sugerencias=0 cobertura=completa"
CON_BLOQUEANTES = "RESUMEN: bloqueantes=2 sugerencias=0 cobertura=completa"
RAMA = "004-demo"
PROPIETARIO = "anahernandez0814"
REPOSITORIO = "due-diligence-pasarela-austral"
ENDPOINT = f"repos/{PROPIETARIO}/{REPOSITORIO}/pulls"


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    """Rama del ticket con un cambio, publicada en `origin`, sin veredicto; una vez por módulo."""
    carpeta = tmp_path_factory.mktemp("plantilla-guarda-pr")
    trabajo = crear_repo(carpeta, RAMA)
    escribir(trabajo, "src/a.py", "x = 1\n")
    confirmar(trabajo, "cambio")
    git(trabajo, "push", "-q", "-u", "origin", RAMA)
    return carpeta


@pytest.fixture
def repo(plantilla, tmp_path, monkeypatch):
    """Copia de la plantilla: rama del ticket con un cambio, publicada, sin veredicto."""
    trabajo = copiar_plantilla(plantilla, tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(trabajo))
    return trabajo


def aprobar(repo, codigo=LIMPIO, auditoria=LIMPIO):
    return veredicto.registrar(repo, git(repo, "rev-parse", "HEAD"), codigo, auditoria)


def entrada_mcp(repo, **cambios):
    datos = {
        "owner": PROPIETARIO,
        "repo": REPOSITORIO,
        "head": RAMA,
        "base": "main",
        "title": "Titulo",
        "body": "Cuerpo",
    }
    datos.update(cambios)
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "mcp__github__create_pull_request",
        "tool_input": datos,
        "cwd": str(repo),
    }


def entrada_terminal(repo, comando, herramienta="Bash"):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": herramienta,
        "tool_input": {"command": comando},
        "cwd": str(repo),
    }


def motivo_mcp(repo, **cambios):
    return guarda_pr.motivo(entrada_mcp(repo, **cambios))


def motivo_terminal(repo, comando, herramienta="Bash"):
    return guarda_pr.motivo(entrada_terminal(repo, comando, herramienta))


# --- Comandos que crean un PR y los que no ---------------------------------------------

CREAN_UN_PR = [
    "gh pr create --title x --body y",
    "gh pr create -t x -b y -B main",
    "gh pr create --fill",
    "gh pr create --repo o/r --fill",
    "gh --version && gh pr create --fill",
    "gh.exe pr create --fill",
    "bash -c 'gh pr create --fill'",
    'eval "gh pr create --fill"',
    "sudo gh pr create --fill",
    "env GH_PAGER=cat gh pr create --fill",
    "env -S 'gh pr create --fill'",
    "echo 1 | xargs gh pr create --fill",
    "cat <<EOF | bash\ngh pr create --fill\nEOF",
    "bash -c \"bash -c 'gh pr create --fill'\"",
    f"gh api {ENDPOINT} -X POST -f title=t -f head={RAMA} -f base=main",
    f"gh api {ENDPOINT} --method POST",
    f"gh api -X post {ENDPOINT}",
    f"gh api {ENDPOINT} --method=POST",
    f"gh api /{ENDPOINT}/ -X POST",
    f"gh api {ENDPOINT} -f title=t -f head={RAMA} -f base=main",
    f"gh api {ENDPOINT} -F title=t",
    f"gh api {ENDPOINT} --field title=t",
    f"gh api {ENDPOINT} --raw-field title=t",
    f"gh api {ENDPOINT} --input cuerpo.json",
    "gh api graphql -f query='mutation { createPullRequest(input: {}) { clientMutationId } }'",
    # Opciones con valor de `gh api` que no son el endpoint (revisión de T030)
    f"gh api -p nebula {ENDPOINT} -X POST",
    f"gh api --preview nebula {ENDPOINT} -f title=x",
    f"gh api -p nebula -X POST {ENDPOINT}",
    f"gh api --cache 1h {ENDPOINT} -X POST",
    f"gh api -H 'Accept: application/json' {ENDPOINT} -X POST",
    # `gh pr new` es el alias oficial de `gh pr create` (hallazgo 1 de la parada D)
    "gh pr new --fill",
    "gh pr new -t x -b y -B main",
    "gh pr new --repo o/r --fill",
    "gh.exe pr new --fill",
    "bash -c 'gh pr new --fill'",
    'eval "gh pr new --fill"',
    "sudo gh pr new --fill",
    "echo 1 | xargs gh pr new --fill",
    # El endpoint como URL completa (hallazgo 2)
    f"gh api https://api.github.com/{ENDPOINT} -f title=x",
    f"gh api https://api.github.com/{ENDPOINT} -X POST",
    f"gh api https://api.github.com/{ENDPOINT}/ --method POST",
    f"gh api http://api.github.com/{ENDPOINT} -X POST",
    f"gh api https://ghe.example.com/api/v3/{ENDPOINT} -f title=x",
    f"gh api https://localhost:1/{ENDPOINT} -f title=x",
    f"gh api https://api.github.com/{ENDPOINT}?draft=true -X POST",
    f"gh api -X POST https://api.github.com/{ENDPOINT}",
]

NO_CREAN_UN_PR = [
    "gh pr view 3",
    "gh pr list",
    "gh pr list --state open",
    "gh pr status",
    "gh pr checks 3",
    "gh issue create --title x",
    f"gh api {ENDPOINT}",
    f"gh api {ENDPOINT} -X GET",
    f"gh api {ENDPOINT}/1",
    f"gh api {ENDPOINT}/1/comments -X POST -f body=x",
    "gh api graphql -f query='query { viewer { login } }'",
    "echo gh pr create",
    "echo gh pr new",
    f"gh api https://api.github.com/{ENDPOINT}",
    f"gh api https://api.github.com/{ENDPOINT} -X GET",
    f"gh api https://api.github.com/{ENDPOINT}/1 -X POST -f body=x",
    f"gh api https://ghe.example.com/api/v3/{ENDPOINT}/1/comments -X POST -f body=x",
    "gh api https://api.github.com/user",
    f"gh api https://api.github.com/repos/{PROPIETARIO}/{REPOSITORIO}/issues -X POST -f title=x",
    "git status",
    "git push -u origin rama",
    "uv run pytest",
    "ls -la",
    "",
]


# --- Sin veredicto, con bloqueantes, de otro commit o ilegible -----------------------


def test_mcp_sin_veredicto_se_bloquea(repo):
    assert "Falta la revisión" in motivo_mcp(repo)


@pytest.mark.parametrize("comando", CREAN_UN_PR)
@pytest.mark.parametrize("herramienta", ["Bash", "PowerShell"])
def test_la_terminal_sin_veredicto_se_bloquea(repo, comando, herramienta):
    assert "Falta la revisión" in motivo_terminal(repo, comando, herramienta)


@pytest.mark.parametrize("comando", NO_CREAN_UN_PR)
def test_lo_que_no_crea_un_pr_se_permite_aunque_no_haya_veredicto(repo, comando):
    assert motivo_terminal(repo, comando) is None


def test_otras_herramientas_se_permiten(repo):
    entrada = {"tool_name": "Read", "tool_input": {"file_path": "x"}, "cwd": str(repo)}
    assert guarda_pr.motivo(entrada) is None
    entrada = {"tool_name": "mcp__github__issue_read", "tool_input": {}, "cwd": str(repo)}
    assert guarda_pr.motivo(entrada) is None


def test_veredicto_con_bloqueantes_se_bloquea_y_dice_que_se_corrija(repo):
    aprobar(repo, CON_BLOQUEANTES, LIMPIO)
    texto = motivo_mcp(repo)
    assert "bloqueantes" in texto
    assert "/abrir-pr" in texto
    assert "Falta la revisión" not in texto


def test_veredicto_de_otro_commit_se_bloquea(repo):
    aprobar(repo)
    escribir(repo, "src/b.py", "y = 2\n")
    confirmar(repo, "otro commit")
    git(repo, "push", "-q", "origin", RAMA)
    assert "Falta la revisión" in motivo_mcp(repo)


def test_veredicto_ilegible_se_trata_como_inexistente(repo):
    archivo = veredicto.ruta_veredicto(repo, git(repo, "rev-parse", "HEAD"))
    archivo.parent.mkdir(parents=True)
    archivo.write_text("{no es json", encoding="utf-8")
    assert "Falta la revisión" in motivo_mcp(repo)


def test_veredicto_con_otro_formato_se_trata_como_inexistente(repo):
    sha = git(repo, "rev-parse", "HEAD")
    archivo = veredicto.ruta_veredicto(repo, sha)
    archivo.parent.mkdir(parents=True)
    archivo.write_text(json.dumps({"commit": sha, "veredicto": "quiza"}), encoding="utf-8")
    assert "Falta la revisión" in motivo_mcp(repo)


# --- Con veredicto aprobado del commit publicado ------------------------------------------


def test_mcp_con_veredicto_aprobado_se_permite(repo):
    assert aprobar(repo) == ("aprobado", None)
    assert motivo_mcp(repo) is None


@pytest.mark.parametrize("comando", CREAN_UN_PR)
@pytest.mark.parametrize("herramienta", ["Bash", "PowerShell"])
def test_la_terminal_con_veredicto_aprobado_se_permite(repo, comando, herramienta):
    aprobar(repo)
    assert motivo_terminal(repo, comando, herramienta) is None


# --- Publicación (R9) -----------------------------------------------------------------


def test_commit_sin_publicar_se_bloquea(tmp_path, monkeypatch):
    trabajo = crear_repo(tmp_path, RAMA)
    escribir(trabajo, "src/a.py", "x = 1\n")
    confirmar(trabajo, "cambio")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(trabajo))
    aprobar(trabajo)
    assert "no está publicado" in motivo_mcp(trabajo)
    assert "no está publicado" in motivo_terminal(trabajo, "gh pr create --fill")


def test_commit_nuevo_sin_publicar_aunque_este_aprobado_se_bloquea(repo):
    escribir(repo, "src/b.py", "y = 2\n")
    confirmar(repo, "commit nuevo")
    aprobar(repo)
    assert "no coincide" in motivo_mcp(repo)


def test_rama_remota_con_otros_commits_se_bloquea(repo):
    aprobar(repo)
    git(repo, "update-ref", f"refs/remotes/origin/{RAMA}", git(repo, "rev-parse", "main"))
    assert "no coincide" in motivo_mcp(repo)


def test_la_comprobacion_usa_la_referencia_local_y_no_la_red(repo):
    # Con un origin inalcanzable, la guarda sigue decidiendo con origin/<rama> local.
    aprobar(repo)
    git(repo, "remote", "set-url", "origin", str(repo / "no-existe.git"))
    assert motivo_mcp(repo) is None


# --- Rama del PR -----------------------------------------------------------------------


def test_rama_del_pr_distinta_de_la_actual_se_bloquea(repo):
    aprobar(repo)
    assert "Cambia a la rama" in motivo_mcp(repo, head="otra-rama")


@pytest.mark.parametrize("head", [RAMA, f"{PROPIETARIO}:{RAMA}", f"{PROPIETARIO.upper()}:{RAMA}"])
def test_head_con_y_sin_prefijo_de_propietario_se_normaliza(repo, head):
    aprobar(repo)
    assert motivo_mcp(repo, head=head) is None


def test_head_con_otro_propietario_es_un_pr_desde_un_fork_y_se_bloquea(repo):
    aprobar(repo)
    texto = motivo_mcp(repo, head=f"otro:{RAMA}")
    assert "otro repositorio" in texto


def test_head_con_prefijo_y_sin_owner_se_bloquea(repo):
    aprobar(repo)
    assert motivo_mcp(repo, owner="", head=f"{PROPIETARIO}:{RAMA}") is not None


@pytest.mark.parametrize("head", [None, "", 3, ["x"]])
def test_head_ausente_o_ilegible_se_bloquea(repo, head):
    aprobar(repo)
    entrada = entrada_mcp(repo)
    entrada["tool_input"]["head"] = head
    assert guarda_pr.motivo(entrada) is not None


def test_mcp_con_tool_input_que_no_es_un_objeto_se_bloquea(repo):
    entrada = entrada_mcp(repo)
    entrada["tool_input"] = None
    assert guarda_pr.motivo(entrada) is not None


@pytest.mark.parametrize(
    "comando",
    [
        "gh pr create --head {rama}",
        "gh pr create -H {rama}",
        "gh pr new --head {rama}",
        "gh pr new -H {rama}",
    ],
)
def test_head_de_la_terminal_igual_a_la_rama_actual_se_permite(repo, comando):
    aprobar(repo)
    assert motivo_terminal(repo, comando.format(rama=RAMA)) is None


@pytest.mark.parametrize(
    "comando",
    [
        "gh pr create --head otra",
        "gh pr create -H otra",
        "gh pr new --head otra",
        "gh pr new -H otra",
    ],
)
def test_head_de_la_terminal_distinto_de_la_rama_actual_se_bloquea(repo, comando):
    aprobar(repo)
    assert "Cambia a la rama" in motivo_terminal(repo, comando)


def test_head_de_la_terminal_con_prefijo_se_bloquea_si_no_se_puede_comprobar_el_propietario(repo):
    aprobar(repo)
    assert motivo_terminal(repo, f"gh pr create --head {PROPIETARIO}:{RAMA}") is not None


def test_head_de_la_terminal_con_el_propietario_de_origin_se_permite(repo):
    aprobar(repo)
    git(repo, "remote", "set-url", "origin", f"https://github.com/{PROPIETARIO}/{REPOSITORIO}.git")
    assert motivo_terminal(repo, f"gh pr create --head {PROPIETARIO}:{RAMA}") is None
    assert motivo_terminal(repo, f"gh pr create --head otro:{RAMA}") is not None


def test_head_del_gh_api_se_lee_de_los_campos(repo):
    aprobar(repo)
    comando = f"gh api {ENDPOINT} -f head=otra -f base=main -f title=t"
    assert "Cambia a la rama" in motivo_terminal(repo, comando)


# --- Anidamiento excesivo y rutas ----------------------------------------------------


def anidar(interior: str) -> str:
    """Cuatro niveles de shells anidados: más de los 3 que analiza el extractor."""
    for shell in ("bash -c", "sh -c", "bash -c", "eval"):
        interior = f"{shell} {shlex.quote(interior)}"
    return interior


def test_anidamiento_excesivo_con_gh_se_bloquea(repo):
    aprobar(repo)
    assert "precaución" in motivo_terminal(repo, anidar("gh pr view 1"))


def test_anidamiento_excesivo_sin_gh_se_permite(repo):
    assert motivo_terminal(repo, anidar("echo hola")) is None


def test_desde_una_subcarpeta_y_sin_la_variable_busca_el_veredicto_en_la_raiz(repo, monkeypatch):
    aprobar(repo)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    subcarpeta = repo / "src"
    assert motivo_terminal(subcarpeta, "gh pr create --fill") is None


# --- Fallo cerrado y extremo a extremo -------------------------------------------------


def ejecutar_script(datos, repo, con_variable=True):
    """Como una terminal normal: sin PYTHONUTF8 ni PYTHONIOENCODING."""
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    if con_variable:
        entorno["CLAUDE_PROJECT_DIR"] = str(repo)
    else:
        entorno.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=datos if isinstance(datos, str) else json.dumps(datos, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        check=False,
    )


def test_e2e_bloquea_con_una_sola_linea_en_stderr(repo):
    resultado = ejecutar_script(entrada_mcp(repo), repo)
    assert resultado.returncode == 2
    assert resultado.stdout == ""
    lineas = resultado.stderr.strip().splitlines()
    assert len(lineas) == 1
    assert lineas[0].startswith("[guarda_pr] ")
    assert "/abrir-pr" in lineas[0]


def test_e2e_bloquea_gh_pr_create_por_terminal(repo):
    resultado = ejecutar_script(entrada_terminal(repo, "gh pr create --fill"), repo)
    assert resultado.returncode == 2
    assert "[guarda_pr] Falta la revisión" in resultado.stderr


def test_e2e_permite_con_veredicto_aprobado_sin_salida(repo):
    aprobar(repo)
    for entrada in (entrada_mcp(repo), entrada_terminal(repo, "gh pr create --fill")):
        resultado = ejecutar_script(entrada, repo)
        assert resultado.returncode == 0
        assert resultado.stdout == ""
        assert resultado.stderr == ""


def test_e2e_permite_lo_que_no_crea_un_pr(repo):
    resultado = ejecutar_script(entrada_terminal(repo, "gh pr view 3"), repo)
    assert resultado.returncode == 0


@pytest.mark.parametrize("datos", ["no es json", "[]", "null", ""])
def test_e2e_entrada_ilegible_falla_cerrado(repo, datos):
    resultado = ejecutar_script(datos, repo)
    assert resultado.returncode == 2
    assert "La guarda falló" in resultado.stderr
    assert "por precaución" in resultado.stderr


def test_e2e_un_error_propio_falla_cerrado(repo):
    entrada = entrada_terminal(repo, "gh pr create --fill")
    entrada["tool_input"]["command"] = 42  # no es texto
    resultado = ejecutar_script(entrada, repo)
    assert resultado.returncode == 2
    assert resultado.stderr.startswith("[guarda_pr] ")


def test_e2e_sin_repositorio_bloquea(tmp_path):
    entrada = entrada_mcp(tmp_path)
    resultado = ejecutar_script(entrada, tmp_path, con_variable=False)
    assert resultado.returncode == 2
    assert resultado.stderr.startswith("[guarda_pr] ")


def test_e2e_la_salida_no_repite_el_comando(repo):
    secreto = "valor-que-no-debe-aparecer"
    resultado = ejecutar_script(
        entrada_terminal(repo, f"gh pr create --title {secreto} --fill"), repo
    )
    assert resultado.returncode == 2
    assert secreto not in resultado.stderr


def test_la_guarda_tarda_menos_de_un_segundo_en_caliente(repo):
    aprobar(repo)
    entrada = entrada_mcp(repo)
    ejecutar_script(entrada, repo)  # la primera llamada calienta la caché del sistema
    inicio = time.perf_counter()
    resultado = ejecutar_script(entrada, repo)
    assert resultado.returncode == 0
    assert time.perf_counter() - inicio < 1.0
