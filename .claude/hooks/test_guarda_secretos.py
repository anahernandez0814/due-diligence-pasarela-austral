"""Pruebas de guarda_secretos.py (FR-001, FR-002, FR-020, R9; contracts/guardas.md).

Los archivos de secretos se crean en `tmp_path` con contenido ficticio y un marcador; los
mensajes de bloqueo nunca deben repetirlo.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import guarda_secretos
import pytest

SCRIPT = Path(__file__).with_name("guarda_secretos.py")
MARCADOR = "MARCADOR_FICTICIO_DE_PRUEBA"

FORMATOS = [
    r"Acceso bloqueado a un archivo de secretos \(.+\) con \w+\. "
    r"Usa \.env\.example para ver las variables\.",
    r"Código en línea bloqueado: nombra un archivo de secretos \(.+\)\. "
    r"Usa \.env\.example para ver las variables\.",
    r"Búsqueda recursiva bloqueada: .+ contiene archivos de secretos\. "
    r"Busca en una carpeta sin secretos o usa la herramienta Grep, rg o git grep\.",
    r"Comando bloqueado por precaución: tiene más de 3 niveles de shells anidados\.",
]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Raíz con `.env` y otros secretos, y una carpeta `src/` sin secretos (R9, decisión 2)."""
    (tmp_path / ".env").write_text(f"VARIABLE_FICTICIA={MARCADOR}\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text(f"VARIABLE_FICTICIA={MARCADOR}\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("VARIABLE_FICTICIA=\n", encoding="utf-8")
    (tmp_path / "x.key").write_text(MARCADOR, encoding="utf-8")
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "a.txt").write_text(MARCADOR, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hola')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Copia .env.example\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


def entrada(repo, herramienta, **datos):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": herramienta,
        "tool_input": datos,
        "cwd": str(repo),
    }


def bash(repo, comando):
    return guarda_secretos.motivo(entrada(repo, "Bash", command=comando))


def powershell(repo, comando):
    return guarda_secretos.motivo(entrada(repo, "PowerShell", command=comando))


def ejecutar_script(repo, datos):
    """Lanza el script como lo haría una terminal normal: sin PYTHONUTF8 ni
    PYTHONIOENCODING, y con el JSON en UTF-8 sin escapar las tildes."""
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=datos if isinstance(datos, str) else json.dumps(datos, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**entorno, "CLAUDE_PROJECT_DIR": str(repo)},
        timeout=30,
    )


# --- Archivos de secretos (data-model) ----------------------------------------------


@pytest.mark.parametrize(
    "ruta", [".env", ".env.local", ".ENV", "x.key", "secrets/a.txt", "Secrets/b", "a/.env"]
)
def test_es_secreto(ruta):
    assert guarda_secretos.es_secreto(ruta)


@pytest.mark.parametrize("ruta", [".env.example", "src/app.py", "x.env", "secrets.py", "env"])
def test_no_es_secreto(ruta):
    assert not guarda_secretos.es_secreto(ruta)


# --- Herramientas de archivo ----------------------------------------------------------


@pytest.mark.parametrize("herramienta", ["Read", "Write", "Edit"])
@pytest.mark.parametrize("ruta", [".env", ".env.local", ".ENV", "x.key", "secrets/a.txt"])
def test_herramientas_de_archivo_bloquean_secretos(repo, herramienta, ruta):
    assert guarda_secretos.motivo(entrada(repo, herramienta, file_path=str(repo / ruta)))


@pytest.mark.parametrize("herramienta", ["Read", "Edit"])
def test_env_example_sigue_accesible(repo, herramienta):
    datos = entrada(repo, herramienta, file_path=str(repo / ".env.example"))
    assert guarda_secretos.motivo(datos) is None


def test_notebook_edit_en_secrets(repo):
    datos = entrada(repo, "NotebookEdit", notebook_path=str(repo / "secrets" / "n.ipynb"))
    assert guarda_secretos.motivo(datos)


@pytest.mark.parametrize(
    "datos",
    [
        {"pattern": "TOKEN", "path": "secrets"},
        {"pattern": "TOKEN", "path": ".env.local"},
        {"pattern": "TOKEN", "glob": ".env*"},
        {"pattern": "TOKEN", "glob": "*.{env,key}"},
    ],
)
def test_grep_hacia_secretos(repo, datos):
    assert guarda_secretos.motivo(entrada(repo, "Grep", **datos))


@pytest.mark.parametrize(
    "datos",
    [
        {"pattern": ".env", "path": "src"},
        {"pattern": ".env"},
        {"pattern": "TOKEN", "glob": "*.py"},
    ],
)
def test_grep_con_patron_env_se_permite(repo, datos):
    assert guarda_secretos.motivo(entrada(repo, "Grep", **datos)) is None


@pytest.mark.parametrize("patron", ["**/.env", ".env*", "**/secrets/*", "*.key"])
def test_glob_que_nombra_secretos(repo, patron):
    assert guarda_secretos.motivo(entrada(repo, "Glob", pattern=patron))


@pytest.mark.parametrize("patron", ["**/*.py", ".env.example", "*", "docs/**/*.md"])
def test_glob_sin_secretos(repo, patron):
    assert guarda_secretos.motivo(entrada(repo, "Glob", pattern=patron)) is None


# --- Bash: rutas ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        "head .env.local",
        "head .env.staging",
        "cat ./secrets/a.txt",
        "cp .env.local x",
        "grep TOKEN .env.local",
        "wc -l < .env",
        "cat .env.l*",
        "cat secrets/*",
        "FOO=1 cat .env",
        "tail --file=.env",
        "cp -r secrets copia",
        "cat " + "/".join(["", "d", "otra", ".env"]),
    ],
)
def test_bash_bloquea_rutas_de_secretos(repo, comando):
    assert bash(repo, comando)


# --- Bash: búsquedas recursivas (R9, decisión 2) -------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        "grep -r TOKEN .",
        "grep -rn TOKEN",
        "grep --recursive TOKEN .",
        "grep -d recurse TOKEN .",
        "rg --no-ignore TOKEN",
        "rg --hidden TOKEN",
        "rg -u TOKEN",
        "rg -uu TOKEN .",
        "find . -exec cat {} +",
        "find . -name '*.txt' -execdir head {} \\;",
        "find . | xargs cat",
        "find . -type f | xargs -I {} grep TOKEN {}",
    ],
)
def test_busquedas_recursivas_con_secretos_en_la_raiz(repo, comando):
    assert "Búsqueda recursiva" in bash(repo, comando)


@pytest.mark.parametrize(
    "comando",
    [
        "grep -rn .env src/",
        'grep -rn ".env" src/',
        "rg TOKEN",
        "rg -u TOKEN src",
        "find src -exec cat {} +",
        "find . -name '*.py'",
        "find . | xargs echo",
    ],
)
def test_busquedas_recursivas_sin_secretos(repo, comando):
    assert bash(repo, comando) is None


def test_recorrido_de_la_raiz_en_menos_de_un_segundo(repo):
    inicio = time.perf_counter()
    assert bash(repo, "grep -r TOKEN .")
    assert bash(repo, "grep -r TOKEN src") is None
    assert time.perf_counter() - inicio < 1  # SC-004


# --- Bash: texto ejecutable (R9, decisión 1) ------------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        "python -c \"print(open('.env').read())\"",
        "uv run python -c \"open('.env')\"",
        "python3 -c \"open('./.env.local')\"",
        "py -3 -c \"open('secrets/a.txt')\"",
        "node -e \"require('fs').readFileSync('.env.local')\"",
        "perl -e \"open(F, '.env')\"",
        "ruby -e \"File.read('x.key')\"",
        "python - <<'FIN'\nprint(open('.env').read())\nFIN",
        "echo \"print(open('.env').read())\" | python",
    ],
)
def test_codigo_en_linea_que_nombra_secretos(repo, comando):
    assert "Código en línea" in bash(repo, comando)


@pytest.mark.parametrize(
    "comando",
    [
        'bash -c "cat .env"',
        'sh -c "head .env.local"',
        'eval "cat .env"',
        "bash <<'FIN'\ncat .env\nFIN",
        'echo "$(cat .env)"',
        "echo `cat .env`",
        'cmd //c "type .env"',
    ],
)
def test_comandos_interiores_con_las_mismas_reglas(repo, comando):
    assert "Acceso bloqueado" in bash(repo, comando)


def test_shell_anidado_con_busqueda_recursiva(repo):
    assert "Búsqueda recursiva" in bash(repo, 'bash -c "grep -r TOKEN ."')


def test_cuatro_niveles_de_shells_se_bloquean(repo):
    comando = r'''eval "bash -c \"sh -c 'bash -c true'\""'''
    assert "más de 3 niveles" in bash(repo, comando)


def test_tres_niveles_de_shells_se_permiten(repo):
    assert bash(repo, r'''eval "bash -c \"sh -c 'true'\""''') is None


# --- Bash: lo que se permite (FR-002, U2, U3, D1) -------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        "grep -n .env README.md",
        "grep -e .env README.md",
        'git grep ".env"',
        "git grep -n -e .env -- src",
        "rg .env src",
        'python -c "print(1)"',
        'python -c "d = {}; d.keys()"',
        'python -c "import secrets; secrets.token_hex(8)"',
        'python -c "import os; os.environ"',
        "python -c \"print('.environment')\"",
        "bash -c \"grep '.env' src/\"",
        'git commit -m "protege .env"',
        "git commit -F - <<'FIN'\nprotege .env y secrets/\nFIN",
        "git commit -m \"$(cat <<'EOF'\nfix(hooks): protege .env y secrets/\n\n"
        'Co-Authored-By: Claude <noreply@anthropic.com>\nEOF\n)"',
        "git log --format='%h %s' -3",
        "gh api repos/x/y/issues --jq '.[] | .title'",
        "uv run pytest -q",
        "uv run ruff check .",
        "git switch main",
        "cat .env.example",
        "ls src",
        "echo hola # cat .env",
    ],
)
def test_bash_permitido(repo, comando):
    assert bash(repo, comando) is None


# --- PowerShell, como respaldo --------------------------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        "Get-Content .env.local",
        "Get-Content -Path .\\secrets\\a.txt",
        "Get-ChildItem -Recurse | Select-String TOKEN",
        "gci -r | Get-Content",
        'pwsh -Command "Get-Content .env"',
    ],
)
def test_powershell_bloquea(repo, comando):
    assert powershell(repo, comando)


@pytest.mark.parametrize(
    "comando",
    [
        "Select-String -Pattern .env -Path README.md",
        "Select-String .env README.md",
        "Get-ChildItem -Recurse src | Select-String TOKEN",
        "Get-Content .env.example",
        "Get-ChildItem -Recurse",
    ],
)
def test_powershell_permitido(repo, comando):
    assert powershell(repo, comando) is None


def test_findstr_excluye_el_patron(repo):
    assert bash(repo, 'cmd //c "findstr .env README.md"') is None
    assert bash(repo, 'cmd //c "findstr TOKEN .env"')


# --- De extremo a extremo: código de salida y mensajes --------------------------------


@pytest.mark.parametrize(
    ("herramienta", "datos"),
    [
        ("Read", {"file_path": ".env"}),
        ("Bash", {"command": "head .env.local"}),
        ("Bash", {"command": "python -c \"open('.env')\""}),
        ("Bash", {"command": "grep -r TOKEN ."}),
        ("Bash", {"command": r'''eval "bash -c \"sh -c 'bash -c true'\""'''}),
        ("PowerShell", {"command": "Get-Content .env.local"}),
    ],
)
def test_script_bloquea_con_salida_2_y_una_linea(repo, herramienta, datos):
    resultado = ejecutar_script(repo, entrada(repo, herramienta, **datos))
    assert resultado.returncode == 2
    assert resultado.stdout == ""
    lineas = resultado.stderr.strip().splitlines()
    assert len(lineas) == 1
    assert lineas[0].startswith("[guarda_secretos] ")
    assert MARCADOR not in resultado.stderr
    mensaje = lineas[0].removeprefix("[guarda_secretos] ")
    assert any(re.fullmatch(formato, mensaje) for formato in FORMATOS), mensaje


@pytest.mark.parametrize(
    ("herramienta", "datos"),
    [
        ("Read", {"file_path": ".env.example"}),
        ("Bash", {"command": "grep -n .env README.md"}),
        ("Grep", {"pattern": ".env", "path": "src"}),
    ],
)
def test_script_permite_con_salida_0(repo, herramienta, datos):
    resultado = ejecutar_script(repo, entrada(repo, herramienta, **datos))
    assert (resultado.returncode, resultado.stdout, resultado.stderr) == (0, "", "")


def test_script_falla_cerrado_con_entrada_invalida(repo):
    resultado = ejecutar_script(repo, "no es json")
    assert resultado.returncode == 2
    assert resultado.stderr.strip() == (
        "[guarda_secretos] La guarda falló (JSONDecodeError); la acción se bloquea por precaución."
    )


# --- UTF-8 en los flujos, independiente del entorno (T011a) ---------------------------


def test_script_lee_una_ruta_con_tilde(repo):
    # "Í" en UTF-8 lleva el byte 0x8D, que cp1252 no define: sin UTF-8 en stdin, la
    # lectura falla. "ó" no basta, porque sus bytes sobreviven a la ida y vuelta.
    datos = entrada(repo, "Read", file_path="docs/configuración/Índice/.env")
    resultado = ejecutar_script(repo, datos)
    assert resultado.returncode == 2
    assert "(docs/configuración/Índice/.env) con Read" in resultado.stderr


def test_script_escribe_un_mensaje_con_tilde(repo):
    resultado = ejecutar_script(repo, entrada(repo, "Bash", command="grep -r TOKEN ."))
    assert resultado.returncode == 2
    assert resultado.stderr.strip() == "[guarda_secretos] " + guarda_secretos.RECURSIVA.format(
        raiz="."
    )


# --- Lanzadores (T050, FR-026) --------------------------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        'echo x | xargs sh -c "cat .env"',
        'sudo sh -c "cat .env"',
        "sudo cat .env",
        "env -S 'cat .env'",
        'script -c "cat .env" /dev/null',
        "watch cat .env",
        "xargs -a lista.txt cat .env",
    ],
)
def test_lanzadores_que_nombran_secretos(repo, comando):
    assert bash(repo, comando)


@pytest.mark.parametrize(
    "comando", ["echo x | xargs echo", "sudo -u otro ls", "env -S 'echo hola'"]
)
def test_lanzadores_sin_secretos(repo, comando):
    assert bash(repo, comando) is None


# --- find -exec como lanzador (T053, FR-026) ------------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        'find docs -exec sh -c "cat .env" \\;',
        "find docs -exec cat .env {} \\;",
        "find docs -execdir head .env.local {} +",
    ],
)
def test_find_exec_con_raiz_sin_secretos_bloquea_secretos(repo, comando):
    assert bash(repo, comando)


@pytest.mark.parametrize(
    "comando",
    [
        'find docs -name "*.md" -exec cat {} +',
        'find src -name "*.py" -exec uv run ruff check {} +',
    ],
)
def test_find_exec_sin_secretos_se_permite(repo, comando):
    (repo / "docs").mkdir(exist_ok=True)
    assert bash(repo, comando) is None
