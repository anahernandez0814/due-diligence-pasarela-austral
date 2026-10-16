"""Pruebas de guarda_spec_previa.py (FR-009 a FR-013, FR-020, R7, R10, R14, data-model).

Cada prueba crea un repositorio git en `tmp_path` y sus ramas.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import guarda_spec_previa
import pytest

SCRIPT = Path(__file__).with_name("guarda_spec_previa.py")
DOCUMENTOS = ("spec.md", "plan.md", "tasks.md")


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def crear(tmp_path, monkeypatch):
    """Crea el repositorio con la rama y las carpetas de specs pedidas."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    git(tmp_path, "init", "-q")

    def _crear(rama="099-x", carpetas=("099-x",), documentos=DOCUMENTOS, separada=False):
        if separada:
            git(tmp_path, "-c", "user.name=p", "-c", "user.email=p@example.com",
                "commit", "-q", "--allow-empty", "-m", "inicio")  # fmt: skip
            git(tmp_path, "checkout", "-q", "--detach")
        else:
            git(tmp_path, "symbolic-ref", "HEAD", f"refs/heads/{rama}")
        for carpeta in carpetas:
            (tmp_path / "specs" / carpeta).mkdir(parents=True)
            for documento in documentos:
                (tmp_path / "specs" / carpeta / documento).write_text("# x\n", encoding="utf-8")
        (tmp_path / "src" / "a").mkdir(parents=True, exist_ok=True)
        return tmp_path

    return _crear


def entrada(repo, herramienta, **datos):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": herramienta,
        "tool_input": datos,
        "cwd": str(repo),
    }


def escribir(repo, ruta):
    return guarda_spec_previa.motivo(entrada(repo, "Write", file_path=str(repo / ruta)))


def bash(repo, comando):
    return guarda_spec_previa.motivo(entrada(repo, "Bash", command=comando))


def powershell(repo, comando):
    return guarda_spec_previa.motivo(entrada(repo, "PowerShell", command=comando))


def ejecutar_script(repo, datos):
    """Como una terminal normal: sin PYTHONUTF8 ni PYTHONIOENCODING."""
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


# --- Código protegido (data-model) ----------------------------------------------------

PROTEGIDOS = [
    "src/a/b.py",
    "src/x.py",
    ".claude/hooks/x.py",
    ".claude/hooks/README.md",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".mcp.json",
    "plugins/p/agents/a.md",
    ".claude-plugin/marketplace.json",
]
EXENTOS = [
    "docs/x.md",
    "specs/x.md",
    ".specify/x.md",
    ".claude/commands/x.md",
    "src/a/test_b.py",
    ".claude/hooks/test_x.py",
    "src/a/notas.md",
    "README.md",
]


@pytest.mark.parametrize("ruta", PROTEGIDOS)
def test_es_protegido(ruta):
    assert guarda_spec_previa.es_protegido(ruta)


@pytest.mark.parametrize("ruta", EXENTOS)
def test_no_es_protegido(ruta):
    assert not guarda_spec_previa.es_protegido(ruta)


# --- Bloqueos por la rama o la carpeta ------------------------------------------------


@pytest.mark.parametrize("rama", ["main", "feature-x", "99-x"])
def test_rama_que_no_es_de_un_ticket(crear, rama):
    repo = crear(rama=rama)
    assert escribir(repo, "src/a/b.py") == (
        f"src/a/b.py es código protegido y la rama '{rama}' no es de un ticket "
        "(NNN-nombre). Crea la rama con /siguiente-ticket."
    )


def test_head_separado(crear):
    repo = crear(separada=True)
    assert "la rama '(HEAD separado)' no es de un ticket" in escribir(repo, "src/a/b.py")


def test_rama_sin_carpeta_de_specs(crear):
    repo = crear(carpetas=())
    assert escribir(repo, "src/a/b.py") == (
        "No existe specs/099-*/ para la rama '099-x'. Ejecuta /speckit-specify."
    )


def test_dos_carpetas_de_specs(crear):
    repo = crear(carpetas=("099-a", "099-b"))
    assert escribir(repo, "src/a/b.py") == (
        "Hay varias carpetas specs/099-*/ (099-a, 099-b); el ticket en curso es ambiguo."
    )


def test_falta_tasks(crear):
    repo = crear(documentos=("spec.md", "plan.md"))
    assert escribir(repo, "src/a/b.py") == (
        "Falta tasks.md en specs/099-x/. Completa /speckit-plan o /speckit-tasks antes de "
        "escribir código."
    )


def test_faltan_varios_documentos(crear):
    repo = crear(documentos=("spec.md",))
    assert escribir(repo, "src/a/b.py").startswith("Falta plan.md, tasks.md en specs/099-x/.")


def test_con_los_tres_documentos_se_permite(crear):
    assert escribir(crear(), "src/a/b.py") is None


@pytest.mark.parametrize("ruta", PROTEGIDOS)
def test_codigo_protegido_sin_documentos(crear, ruta):
    assert escribir(crear(documentos=()), ruta)


@pytest.mark.parametrize("ruta", EXENTOS)
def test_exentos_incluso_en_main(crear, ruta):
    assert escribir(crear(rama="main"), ruta) is None


@pytest.mark.parametrize("herramienta", ["Edit", "Write"])
def test_edit_y_write_revisan_file_path(crear, herramienta):
    repo = crear(rama="main")
    datos = entrada(repo, herramienta, file_path=str(repo / ".mcp.json"))
    assert guarda_spec_previa.motivo(datos)


def test_notebook_edit_revisa_notebook_path(crear):
    repo = crear(rama="main")
    plugin = entrada(repo, "NotebookEdit", notebook_path=str(repo / "plugins" / "p" / "n.ipynb"))
    docs = entrada(repo, "NotebookEdit", notebook_path=str(repo / "docs" / "n.ipynb"))
    assert guarda_spec_previa.motivo(plugin)
    assert guarda_spec_previa.motivo(docs) is None


# --- Destinos por terminal (R10) ------------------------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        "echo x > src/a/x.py",
        "echo x >> src/a/x.py",
        "echo x >| src/a/x.py",
        "ls &> src/a/x.py",
        "echo x | tee src/a/x.py",
        "tee -a .claude/hooks/x.py < notas.txt",
        "cp a.py src/a/x.py",
        "mv a.py src/a/",
        "install -t src/a x.py",
        "install -m 755 x.py .claude/hooks/x.py",
        "sed -i 's/a/b/' src/a/x.py",
        "sed -i.bak -e 's/a/b/' .claude/settings.json",
        "touch .mcp.json",
        "cat > src/a/x.py <<'FIN'\nx = 1\nFIN",
        "echo hola; echo x > plugins/p/a.md",
    ],
)
def test_destinos_bash(crear, comando):
    assert bash(crear(rama="main"), comando)


@pytest.mark.parametrize(
    "comando",
    [
        'Set-Content src/a/x.py "x"',
        "Set-Content -Path src/a/x.py -Value x",
        "Set-Content -Encoding utf8 src/a/x.py x",
        "Add-Content -Path .claude/hooks/x.py -Value x",
        '"x" | Out-File -FilePath src/a/x.py',
        "New-Item src/a/x.py",
        "New-Item -Path src/a -Name x.py",
        "Copy-Item a.py -Destination src/a/x.py",
        "Copy-Item a.py src/a/x.py",
        "Move-Item a.py .claude/hooks/x.py",
        "echo x > src/a/x.py",
    ],
)
def test_destinos_powershell(crear, comando):
    assert powershell(crear(rama="main"), comando)


@pytest.mark.parametrize(
    "comando",
    [
        "ls 2>&1",
        "ls > /dev/null",
        "ls 2>/dev/null",
        "echo x > notas.txt",
        "cp src/a/x.py copia.py",
        "cat src/a/x.py",
        "sed -n 1,5p src/a/x.py",
        'git commit -m "toca src/a/x.py"',
        "git commit -m \"$(cat <<'EOF'\nfix(hooks): mensaje\nEOF\n)\"",
        "git log --format='%h %s' -3",
        "uv run pytest -q",
    ],
)
def test_destinos_que_se_ignoran(crear, comando):
    assert bash(crear(rama="main"), comando) is None


# --- Texto ejecutable (I7, U4) --------------------------------------------------------

ESCRITURAS_EJECUTABLES = [
    "python -c \"open('src/a/x.py','w').write('')\"",
    'bash -c "echo > src/a/x.py"',
    "cat > src/a/x.py <<'FIN'\nx = 1\nFIN",
]


@pytest.mark.parametrize("comando", ESCRITURAS_EJECUTABLES)
def test_texto_ejecutable_sin_documentos(crear, comando):
    assert bash(crear(documentos=()), comando)


@pytest.mark.parametrize("comando", ESCRITURAS_EJECUTABLES)
def test_texto_ejecutable_con_documentos(crear, comando):
    assert bash(crear(), comando) is None


@pytest.mark.parametrize("documentos", [(), DOCUMENTOS])
def test_cuatro_niveles_se_bloquean_en_cualquier_rama(crear, documentos):
    repo = crear(documentos=documentos)
    assert bash(repo, r'''eval "bash -c \"sh -c 'bash -c true'\""''') == (
        "Comando bloqueado por precaución: tiene más de 3 niveles de shells anidados."
    )


@pytest.mark.parametrize(
    "comando",
    [
        "python -c \"open('src/due_diligence/x.py','w')\"",
        r'''python -c "open('.\\src\\x.py','w')"''',
        r'''python -c "open('.\\\\src\\\\x.py','w')"''',
        "python -c \"open('./.claude/settings.json')\"",
        "node -e \"require('fs').writeFileSync('plugins/p/a.md', '')\"",
    ],
)
def test_codigo_protegido_en_el_texto(crear, comando):
    assert bash(crear(documentos=()), comando)


@pytest.mark.parametrize(
    "comando",
    [
        'python -c "import due_diligence"',
        'python -c "import due_diligence.config"',
        "python -c \"open('src/due_diligence/test_x.py')\"",
        "python -c \"open('docs/x.md','w')\"",
        "python -c \"open('mysrc/x.py','w')\"",
    ],
)
def test_texto_que_no_es_codigo_protegido(crear, comando):
    assert bash(crear(documentos=()), comando) is None


# --- De extremo a extremo -------------------------------------------------------------


def test_script_bloquea_con_salida_2_y_una_linea(crear):
    repo = crear(rama="main")
    resultado = ejecutar_script(repo, entrada(repo, "Write", file_path=str(repo / "src/x.py")))
    assert resultado.returncode == 2
    assert resultado.stdout == ""
    assert resultado.stderr.strip() == (
        "[guarda_spec_previa] src/x.py es código protegido y la rama 'main' no es de un "
        "ticket (NNN-nombre). Crea la rama con /siguiente-ticket."
    )


def test_script_permite_con_salida_0(crear):
    repo = crear()
    resultado = ejecutar_script(repo, entrada(repo, "Write", file_path=str(repo / "src/x.py")))
    assert (resultado.returncode, resultado.stdout, resultado.stderr) == (0, "", "")


def test_script_falla_cerrado_si_git_falla(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    resultado = ejecutar_script(
        tmp_path, entrada(tmp_path, "Write", file_path=str(tmp_path / "src/x.py"))
    )
    assert resultado.returncode == 2
    assert resultado.stderr.strip() == (
        "[guarda_spec_previa] La guarda falló (CalledProcessError); la acción se bloquea "
        "por precaución."
    )


def test_exento_no_necesita_git(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    datos = entrada(tmp_path, "Write", file_path=str(tmp_path / "docs" / "x.md"))
    assert guarda_spec_previa.motivo(datos) is None


# --- Borrar, restaurar y mover también es modificar (T017a) ---------------------------

MODIFICACIONES = [
    ("Bash", "rm .claude/settings.json"),
    ("Bash", "rm -f src/a/x.py"),
    ("Bash", "unlink .mcp.json"),
    ("Bash", "git rm -q --cached .claude/hooks/x.py"),
    ("Bash", "git checkout 003-x -- .claude/settings.json"),
    ("Bash", "git checkout -- src/a/x.py"),
    ("Bash", "git restore .claude/settings.json"),
    ("Bash", "git restore --source=HEAD~1 src/a/x.py"),
    ("Bash", "git restore --source HEAD~1 --staged src/a/x.py"),
    ("Bash", "mv src/app/a.py docs/a.py"),
    ("PowerShell", "Remove-Item .claude/settings.json"),
    ("PowerShell", "del src/a/x.py"),
    ("PowerShell", "erase .mcp.json"),
    ("PowerShell", "rd plugins/p -Recurse"),
    ("PowerShell", "ri -Path .claude/hooks/x.py"),
    ("PowerShell", "Move-Item src/a/x.py docs/x.py"),
    ("PowerShell", "Move-Item -Path src/a/x.py -Destination docs/x.py"),
]


@pytest.mark.parametrize(("herramienta", "comando"), MODIFICACIONES)
def test_borrar_restaurar_y_mover_en_main(crear, herramienta, comando):
    repo = crear(rama="main")
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando))


@pytest.mark.parametrize(("herramienta", "comando"), MODIFICACIONES)
def test_borrar_restaurar_y_mover_con_documentos(crear, herramienta, comando):
    repo = crear()
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando)) is None


@pytest.mark.parametrize(
    ("herramienta", "comando"),
    [
        ("Bash", "rm docs/x.md"),
        ("Bash", "rm -rf build"),
        ("Bash", "git checkout 003-x"),
        ("Bash", "git checkout -b 004-y"),
        ("Bash", "git restore docs/x.md"),
        ("Bash", "mv docs/a.md docs/b.md"),
        ("PowerShell", "Remove-Item docs/x.md"),
        ("PowerShell", "Move-Item docs/a.md docs/b.md"),
    ],
)
def test_borrar_y_mover_lo_no_protegido_en_main(crear, herramienta, comando):
    repo = crear(rama="main")
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando)) is None


def test_mensaje_de_un_borrado_en_main(crear):
    assert bash(crear(rama="main"), "rm .claude/settings.json") == (
        ".claude/settings.json es código protegido y la rama 'main' no es de un ticket "
        "(NNN-nombre). Crea la rama con /siguiente-ticket."
    )
