"""Pruebas de guarda_spec_previa.py (FR-009 a FR-013, FR-020, R7, R10, R14, data-model).

Cada prueba crea un repositorio git en `tmp_path` y sus ramas.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import guarda_spec_previa
import pytest

SCRIPT = Path(__file__).with_name("guarda_spec_previa.py")
DOCUMENTOS = ("spec.md", "plan.md", "tasks.md")


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    """Repositorio git vacío, creado una vez por módulo y copiado en cada prueba."""
    carpeta = tmp_path_factory.mktemp("plantilla-spec-previa")
    git(carpeta, "init", "-q")
    return carpeta


@pytest.fixture
def crear(plantilla, tmp_path, monkeypatch):
    """Crea el repositorio con la rama y las carpetas de specs pedidas."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    shutil.copytree(plantilla, tmp_path, dirs_exist_ok=True)

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


# --- Carpetas, git checkout, git mv, cd y truncate (T017b) ----------------------------

AMPLIACION = [
    ("Bash", "rm -rf ."),
    ("Bash", "git restore ."),
    ("Bash", "git checkout -- ."),
    ("Bash", "git checkout 003-x -- .claude"),
    ("Bash", "rm -rf src/app/"),
    ("Bash", "git checkout 003-x .claude/settings.json"),
    ("Bash", "git checkout HEAD src/app/a.py"),
    ("Bash", "git checkout src/app/a.py"),
    ("Bash", "git mv src/app/a.py docs/a.py"),
    ("Bash", "git -C src rm app/a.py"),
    ("Bash", "cd src && echo x > app/b.py"),
    ("Bash", "cd src/app; cp /tmp/x.py b.py"),
    ("Bash", "pushd .claude && rm settings.json"),
    ("PowerShell", "Set-Location src; Set-Content app/b.py x"),
    ("Bash", "truncate -s 0 src/app/a.py"),
    ("Bash", "truncate --size=0 .mcp.json"),
]


@pytest.fixture
def con_app(crear):
    """Repositorio con `src/app/a.py` en disco, para `git checkout <ruta>`."""

    def _crear(**opciones):
        repo = crear(**opciones)
        (repo / "src" / "app").mkdir(parents=True, exist_ok=True)
        (repo / "src" / "app" / "a.py").write_text("x = 1\n", encoding="utf-8")
        (repo / "docs").mkdir(exist_ok=True)
        return repo

    return _crear


@pytest.mark.parametrize(("herramienta", "comando"), AMPLIACION)
def test_ampliacion_en_main(con_app, herramienta, comando):
    repo = con_app(rama="main")
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando))


@pytest.mark.parametrize(("herramienta", "comando"), AMPLIACION)
def test_ampliacion_con_documentos(con_app, herramienta, comando):
    repo = con_app()
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando)) is None


@pytest.mark.parametrize(
    "comando",
    [
        "rm -rf docs",
        "git checkout 003-x",
        "git checkout main",
        "git checkout -b 004-y main",
        "git checkout -B 004-y 003-x",
        "git mv docs/a.md docs/b.md",
        "git -C docs rm a.md",
        "cd docs && echo x > b.py",
        "cd src && cat app/a.py",
        "truncate -s 0 docs/a.md",
        "truncate -r src/app/a.py docs/a.md",
    ],
)
def test_ampliacion_que_se_permite_en_main(con_app, comando):
    assert bash(con_app(rama="main"), comando) is None


@pytest.mark.parametrize("ruta", ["", ".claude", "src", "src/app", "plugins/p"])
def test_carpetas_que_contienen_codigo_protegido(ruta):
    assert guarda_spec_previa.contiene_protegido(ruta)


@pytest.mark.parametrize("ruta", ["docs", "specs/003-x", ".specify", "../otro"])
def test_carpetas_sin_codigo_protegido(ruta):
    assert not guarda_spec_previa.contiene_protegido(ruta)


# --- Comandos interiores que heredan el cwd (T017c) -----------------------------------

HEREDAN = [
    "cd .claude && bash -c 'rm settings.json'",
    "cd .claude && eval rm settings.json",
    "cd src/app && sh -c 'echo x > b.py'",
    "cd src && python -c \"open('app/b.py','w')\"",
    "cd src/app && python3 - <<'EOF'\nopen('b.py','w')\nEOF",
    'cd .claude && echo "$(rm settings.json)"',
]


@pytest.mark.parametrize("comando", HEREDAN)
def test_interiores_heredan_el_cwd_en_main(con_app, comando):
    assert bash(con_app(rama="main"), comando)


@pytest.mark.parametrize("comando", HEREDAN)
def test_interiores_heredan_el_cwd_con_documentos(con_app, comando):
    assert bash(con_app(), comando) is None


@pytest.mark.parametrize(
    "comando",
    [
        "cd docs && bash -c 'rm -rf build'",
        'cd docs && python -c "print(1)"',
        'python -c "print(1)"',
        "cd src && uv run pytest",
        "bash -c 'rm settings.json'; cd .claude",
    ],
)
def test_interiores_tras_un_cd_que_se_permiten_en_main(con_app, comando):
    assert bash(con_app(rama="main"), comando) is None


def test_mensaje_del_codigo_en_una_carpeta_protegida(con_app):
    assert bash(con_app(rama="main"), 'cd src && python -c "print(1)"') == (
        "src es código protegido y la rama 'main' no es de un ticket (NNN-nombre). "
        "Crea la rama con /siguiente-ticket."
    )


# --- settings.local.json en cualquier rama (T049, FR-025) -----------------------------

LOCAL = ".claude/settings.local.json"
MSG_LOCAL = (
    ".claude/settings.local.json no se modifica desde Claude Code en ninguna rama: puede "
    "desactivar las guardas. Edítalo fuera de Claude Code."
)
MODIFICAN_LOCAL = [
    ("Write", {"file_path": LOCAL}),
    ("Bash", {"command": "echo '{\"disableAllHooks\": true}' > .claude/settings.local.json"}),
    ("Bash", {"command": "cp /tmp/x.json .claude/settings.local.json"}),
    ("Bash", {"command": "python -c \"open('.claude/settings.local.json','w').write('{}')\""}),
    ("Bash", {"command": "rm .claude/settings.local.json"}),
    ("Bash", {"command": "mv .claude/settings.local.json x"}),
]


@pytest.mark.parametrize("rama", ["main", "003-x"])
@pytest.mark.parametrize(("herramienta", "datos"), MODIFICAN_LOCAL)
def test_settings_local_bloqueado_en_cualquier_rama(crear, rama, herramienta, datos):
    repo = crear(rama=rama)
    if "file_path" in datos:
        datos = {"file_path": str(repo / LOCAL)}
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, **datos)) == MSG_LOCAL


def test_leer_settings_local_se_permite(crear):
    repo = crear()
    comando = "cat .claude/settings.local.json"
    assert guarda_spec_previa.motivo(entrada(repo, "Bash", command=comando)) is None


def test_settings_json_sigue_la_regla_normal(crear):
    # Rama de ticket con sus tres documentos: settings.json se permite.
    repo = crear()
    datos = entrada(repo, "Write", file_path=str(repo / ".claude/settings.json"))
    assert guarda_spec_previa.motivo(datos) is None


# --- Lanzadores (T050, FR-026) --------------------------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        "echo x | xargs sh -c 'echo > src/app/b.py'",
        "sudo sh -c 'echo > src/app/b.py'",
        "env -S 'echo > src/app/b.py'",
        'script -c "echo > src/app/b.py" /dev/null',
    ],
)
def test_lanzadores_escriben_codigo_protegido_en_main(con_app, comando):
    assert guarda_spec_previa.motivo(entrada(con_app(rama="main"), "Bash", command=comando))


@pytest.mark.parametrize(
    "comando",
    [
        "echo x | xargs sh -c 'echo > src/app/b.py'",
        "sudo sh -c 'echo > src/app/b.py'",
    ],
)
def test_lanzadores_con_documentos_se_permiten(con_app, comando):
    assert guarda_spec_previa.motivo(entrada(con_app(), "Bash", command=comando)) is None


# --- find -exec como lanzador (T053, FR-026) ------------------------------------------

FIND_EXEC = [
    "find docs -exec cp {} src/app/ \\;",
    "find docs -exec rm src/app/a.py \\;",
    "find docs -execdir mv {} src/app/b.py +",
]


@pytest.mark.parametrize("comando", FIND_EXEC)
def test_find_exec_escribe_codigo_protegido_en_main(con_app, comando):
    assert bash(con_app(rama="main"), comando)


@pytest.mark.parametrize("comando", FIND_EXEC)
def test_find_exec_con_documentos_se_permite(con_app, comando):
    assert bash(con_app(), comando) is None


def test_find_exec_sin_escrituras_en_main(con_app):
    repo = con_app(rama="main")
    assert bash(repo, 'find docs -name "*.md" -exec cat {} +') is None


# --- Directorio de veredictos en cualquier rama (ticket #4: FR-020, R8) -----------------

VEREDICTOS = ".claude/veredictos"
FICHERO = f"{VEREDICTOS}/{'a' * 40}.json"
MSG_VEREDICTOS = (
    "El directorio de veredictos solo lo escribe el registro de la revisión. Ejecuta /abrir-pr."
)
MODIFICAN_VEREDICTOS = [
    ("Write", {"file_path": FICHERO}),
    ("Edit", {"file_path": FICHERO, "old_string": "a", "new_string": "b"}),
    ("NotebookEdit", {"notebook_path": f"{VEREDICTOS}/x.ipynb", "new_source": "x"}),
    ("Bash", {"command": f"echo '{{}}' > {FICHERO}"}),
    ("Bash", {"command": f"echo '{{}}' >> {FICHERO}"}),
    ("Bash", {"command": f"echo '{{}}' | tee {FICHERO}"}),
    ("Bash", {"command": f"cp /tmp/x.json {FICHERO}"}),
    ("Bash", {"command": f"cp /tmp/x.json {VEREDICTOS}/"}),
    ("Bash", {"command": f"mv /tmp/x.json {FICHERO}"}),
    ("Bash", {"command": f"mv {FICHERO} /tmp/x.json"}),
    ("Bash", {"command": f"sed -i s/a/b/ {FICHERO}"}),
    ("Bash", {"command": f"touch {FICHERO}"}),
    ("Bash", {"command": f"rm {FICHERO}"}),
    ("Bash", {"command": f"rm -r {VEREDICTOS}"}),
    ("Bash", {"command": f"python -c \"open('{FICHERO}','w').write('{{}}')\""}),
    ("Bash", {"command": f"python3.12 -c \"open('{VEREDICTOS}/x.json','w')\""}),
    ("Bash", {"command": f"node -e \"require('fs').writeFileSync('{FICHERO}','{{}}')\""}),
    ("Bash", {"command": f"bash -c 'echo > {FICHERO}'"}),
    ("Bash", {"command": f'eval "echo x > {FICHERO}"'}),
    ("Bash", {"command": f"python - <<'EOF'\nopen('{FICHERO}', 'w')\nEOF"}),
    ("Bash", {"command": f"cat <<'EOF' | bash\necho x > {FICHERO}\nEOF"}),
    ("Bash", {"command": f"echo ok && echo x > {FICHERO}"}),
    ("Bash", {"command": f"echo x > .CLAUDE/Veredictos/{'a' * 40}.json"}),
    ("PowerShell", {"command": f"Set-Content {FICHERO} '{{}}'"}),
    ("PowerShell", {"command": f"Remove-Item {FICHERO}"}),
]


@pytest.mark.parametrize("rama", ["main", "003-x"])
@pytest.mark.parametrize(("herramienta", "datos"), MODIFICAN_VEREDICTOS)
def test_veredictos_bloqueado_en_cualquier_rama(crear, rama, herramienta, datos):
    repo = crear(rama=rama)
    if "file_path" in datos:
        datos = {**datos, "file_path": str(repo / datos["file_path"])}
    if "notebook_path" in datos:
        datos = {**datos, "notebook_path": str(repo / datos["notebook_path"])}
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, **datos)) == MSG_VEREDICTOS


LEEN_VEREDICTOS = [
    ("Bash", f"cat {FICHERO}"),
    ("Bash", f"ls {VEREDICTOS}"),
    ("Bash", f"head -n 3 {FICHERO}"),
    ("Bash", f"git check-ignore -v {FICHERO}"),
    ("PowerShell", f"Get-Content {FICHERO}"),
]


@pytest.mark.parametrize("rama", ["main", "003-x"])
@pytest.mark.parametrize(("herramienta", "comando"), LEEN_VEREDICTOS)
def test_leer_los_veredictos_se_permite(crear, rama, herramienta, comando):
    repo = crear(rama=rama)
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando)) is None


@pytest.mark.parametrize("rama", ["main", "003-x"])
def test_la_herramienta_read_no_es_de_esta_guarda(crear, rama):
    repo = crear(rama=rama)
    assert guarda_spec_previa.motivo(entrada(repo, "Read", file_path=str(repo / FICHERO))) is None


REGISTRO = (
    "uv run --no-project --python 3.12 --quiet .claude/hooks/veredicto.py registrar "
    f"--commit {'a' * 40} --codigo 'RESUMEN: bloqueantes=0 sugerencias=0 cobertura=completa' "
    "--auditoria 'sin resumen'"
)


@pytest.mark.parametrize("rama", ["main", "003-x"])
def test_el_comando_de_registro_no_se_bloquea(crear, rama):
    repo = crear(rama=rama)
    assert guarda_spec_previa.motivo(entrada(repo, "Bash", command=REGISTRO)) is None


@pytest.mark.parametrize("rama", ["main", "003-x"])
def test_otros_archivos_de_claude_siguen_su_regla_normal(crear, rama):
    repo = crear(rama=rama)
    comando = "echo x > .claude/otro-directorio/a.txt"
    resultado = guarda_spec_previa.motivo(entrada(repo, "Bash", command=comando))
    assert resultado != MSG_VEREDICTOS


def test_un_nombre_parecido_no_cuenta_como_el_directorio_de_veredictos(crear):
    repo = crear(rama="003-x")
    for ruta in (".claude/veredictos-otros/x.json", ".claude/veredictosx", "veredictos/x.json"):
        resultado = guarda_spec_previa.motivo(entrada(repo, "Bash", command=f"echo x > {ruta}"))
        assert resultado != MSG_VEREDICTOS, ruta


# --- Copias que ocultan los nombres y borrar .claude entera (parada D, hallazgo 3) ----------

COPIA_A_CLAUDE = guarda_spec_previa.COPIA_A_CLAUDE
BORRAR_CLAUDE = guarda_spec_previa.BORRAR_CLAUDE

COPIAS_OPACAS = [
    ("Bash", "cp -r /tmp/falso/. .claude"),
    ("Bash", "cp -a /tmp/falso/. .claude/"),
    # Regla sobre el destino: no se mira el origen (segunda ronda de la parada D)
    ("Bash", "cp -rT /tmp/falso .claude"),
    ("Bash", "cp -r --no-target-directory /tmp/falso .claude"),
    ("Bash", "cp -R /tmp/falso/ .claude"),
    ("Bash", "cp -r /tmp/falso .claude"),
    ("Bash", "cp -r /tmp/falso .claude/"),
    ("Bash", "cp -r src-dir .claude/"),
    ("Bash", "cp -aT /tmp/falso .claude"),
    ("Bash", "mv -T /tmp/falso .claude"),
    ("Bash", "mv /tmp/falso .claude"),
    ("Bash", "mv archivo.txt .claude/"),
    ("Bash", "cp -R /tmp/falso/ ."),
    ("Bash", "cp -rT /tmp/falso ."),
    ("Bash", "cp -r --no-target-directory /tmp/falso ./"),
    ("PowerShell", r"Copy-Item -Recurse C:	mpalso .claude"),
    ("Bash", "cp -r /tmp/falso/* .claude/"),
    ("Bash", "cp -R /tmp/falso/. .claude"),
    ("Bash", "cp -rf /tmp/falso/* .claude"),
    ("Bash", "cp --recursive /tmp/falso/. .claude/"),
    ("Bash", "cp -r /tmp/falso/. ."),
    ("Bash", "cp -r /tmp/falso/* ./"),
    ("Bash", "cp -r /tmp/falso/. -t .claude"),
    ("Bash", "mv /tmp/falso/* .claude/"),
    ("Bash", "mv /tmp/falso/. .claude"),
    ("Bash", "bash -c 'cp -r /tmp/falso/. .claude'"),
    ("Bash", 'eval "cp -r /tmp/falso/* .claude/"'),
    ("Bash", "sudo cp -r /tmp/falso/. .claude"),
    ("Bash", "echo ok && cp -r /tmp/falso/. .claude/"),
    ("PowerShell", r"Copy-Item -Recurse C:\tmp\falso\* .claude"),
    ("PowerShell", r"Copy-Item -Recurse -Path C:\tmp\falso\* -Destination .claude"),
    ("PowerShell", r"Copy-Item -Recurse C:\tmp\falso\* ."),
    ("PowerShell", "cp -Recurse /tmp/falso/* .claude"),
    ("PowerShell", r"Move-Item C:\tmp\falso\* .claude"),
]

BORRAN_CLAUDE_ENTERA = [
    ("Bash", "rm -rf .claude"),
    ("Bash", "rm -r .claude/"),
    ("Bash", "rm -rf ./.claude"),
    ("Bash", "mv .claude x"),
    ("Bash", "mv .claude/ /tmp/x"),
    ("Bash", "mv .claude .claude-viejo"),
    ("PowerShell", "Remove-Item -Recurse .claude"),
    ("Bash", "bash -c 'rm -rf .claude'"),
    ("Bash", "echo ok && rm -rf .claude"),
    ("PowerShell", "Remove-Item -Recurse -Force .claude"),
    ("PowerShell", "Move-Item .claude x"),
]


@pytest.mark.parametrize("rama", ["main", "003-x"])
@pytest.mark.parametrize(("herramienta", "comando"), COPIAS_OPACAS)
def test_copiar_o_mover_hacia_claude_sin_saber_los_nombres_se_bloquea(
    crear, rama, herramienta, comando
):
    repo = crear(rama=rama)
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando)) == COPIA_A_CLAUDE


@pytest.mark.parametrize("rama", ["main", "003-x"])
@pytest.mark.parametrize(("herramienta", "comando"), BORRAN_CLAUDE_ENTERA)
def test_borrar_o_mover_claude_entera_se_bloquea(crear, rama, herramienta, comando):
    repo = crear(rama=rama)
    assert guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando)) == BORRAR_CLAUDE


def test_los_mensajes_explican_el_motivo_y_la_salida():
    assert "veredicto" in COPIA_A_CLAUDE
    assert "subdirectorio" in COPIA_A_CLAUDE
    assert "origen" in COPIA_A_CLAUDE
    assert "veredicto" in BORRAR_CLAUDE


PERMITIDOS_JUNTO_A_CLAUDE = [
    ("Bash", "cp archivo.txt .claude/otro-directorio/"),
    ("Bash", "cp /tmp/falso/* .claude/"),
    ("Bash", "cp -r src-no-protegida dir-temporal/"),
    ("Bash", "cp -r /tmp/falso/. dir-temporal"),
    # Hacia subcarpetas, la regla normal; hacia la raíz, solo la copia que oculta nombres
    ("Bash", "cp -r /tmp/falso ."),
    ("Bash", "cp -r /tmp/falso/algo ."),
    ("Bash", "cp -r src-no-protegida .claude/agents/"),
    ("Bash", "cp archivo .claude/"),
    ("Bash", "mv archivo .claude/agents/x"),
    ("Bash", "mv a.txt ./b.txt"),
    ("Bash", "cp -r /tmp/falso/* dir-temporal/"),
    ("Bash", "mv /tmp/*.log ."),
    ("Bash", "mv a.txt b.txt"),
    ("Bash", "rm .claude/otro-directorio/a.txt"),
    ("Bash", "rm -rf dir-temporal"),
    ("Bash", "rm -rf .claude-no-es-esta"),
    ("Bash", "ls .claude"),
    ("Bash", "cat .claude/settings.json"),
    ("PowerShell", r"Copy-Item C:\tmp\falso\* .claude"),
    ("PowerShell", r"Copy-Item -Recurse C:\tmp\falso\* dir-temporal"),
    ("PowerShell", "Remove-Item -Recurse -Force dir-temporal"),
]


@pytest.mark.parametrize("rama", ["main", "003-x"])
@pytest.mark.parametrize(("herramienta", "comando"), PERMITIDOS_JUNTO_A_CLAUDE)
def test_lo_que_no_oculta_nombres_ni_borra_claude_se_permite(crear, rama, herramienta, comando):
    repo = crear(rama=rama)
    resultado = guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando))
    assert resultado not in (COPIA_A_CLAUDE, BORRAR_CLAUDE, MSG_VEREDICTOS, MSG_LOCAL)


@pytest.mark.parametrize("rama", ["main", "003-x"])
def test_cuando_el_nombre_aparece_sigue_bloqueandose(crear, rama):
    repo = crear(rama=rama)
    (repo / ".claude").mkdir()  # como en el repositorio real, es una carpeta
    for herramienta, comando in (
        ("Bash", "cp -r /tmp/falso/veredictos .claude/"),
        ("PowerShell", r"Move-Item C:\tmp\falso\veredictos .claude"),
    ):
        resultado = guarda_spec_previa.motivo(entrada(repo, herramienta, command=comando))
        # Lo bloquea la regla del destino o, si no, la del nombre (FR-020)
        assert resultado in (COPIA_A_CLAUDE, MSG_VEREDICTOS), comando
