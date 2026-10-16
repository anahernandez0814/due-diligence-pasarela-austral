"""Pruebas de comun.py: entrada, rutas, comandos, bloqueo y texto ejecutable."""

import io
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import comun
import pytest

# --- Lectura de stdin ---------------------------------------------------------------


def test_leer_entrada_json_valido():
    entrada = comun.leer_entrada(io.StringIO(json.dumps({"tool_name": "Read"})))
    assert entrada == {"tool_name": "Read"}


@pytest.mark.parametrize("texto", ["no es json", "[1, 2]", ""])
def test_leer_entrada_invalida_lanza_error(texto):
    with pytest.raises(ValueError):
        comun.leer_entrada(io.StringIO(texto))


# --- Raíz del repositorio -----------------------------------------------------------


def test_raiz_prioriza_claude_project_dir(monkeypatch, tmp_path):
    otra = tmp_path / "otra"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert comun.raiz({"cwd": str(otra)}) == tmp_path


def test_raiz_usa_cwd_si_falta_la_variable(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert comun.raiz({"cwd": str(tmp_path)}) == tmp_path


# --- Normalización de rutas ---------------------------------------------------------


def test_normalizar_ruta_relativa_con_barras_invertidas(tmp_path):
    assert comun.normalizar_ruta("src\\a\\b.py", tmp_path) == "src/a/b.py"


def test_normalizar_ruta_absoluta_dentro_de_la_raiz(tmp_path):
    ruta = str(tmp_path / "src" / "b.py")
    assert comun.normalizar_ruta(ruta, tmp_path) == "src/b.py"


def test_normalizar_ruta_relativa_al_cwd(tmp_path):
    assert comun.normalizar_ruta("../x.py", tmp_path, cwd=tmp_path / "src") == "x.py"


def test_normalizar_ruta_fuera_de_la_raiz_queda_absoluta(tmp_path):
    fuera = tmp_path.parent / "fuera.txt"
    resultado = comun.normalizar_ruta(str(fuera), tmp_path)
    assert resultado.endswith("/fuera.txt")
    assert not resultado.startswith("..")


def test_normalizar_ruta_no_distingue_mayusculas_de_la_raiz(tmp_path):
    ruta = str(tmp_path).upper() + "/src/B.py"
    assert comun.normalizar_ruta(ruta, Path(str(tmp_path).lower())) == "src/B.py"


# --- División de comandos -----------------------------------------------------------


def test_dividir_por_separadores():
    assert comun.dividir_comando("a 1; b 2 && c || d | e") == [
        ["a", "1"],
        ["b", "2"],
        ["c"],
        ["d"],
        ["e"],
    ]


def test_dividir_por_saltos_de_linea():
    assert comun.dividir_comando("a 1\nb 2") == [["a", "1"], ["b", "2"]]


def test_dividir_conserva_redirecciones():
    assert comun.dividir_comando("cat < x > y >> z") == [["cat", "<", "x", ">", "y", ">>", "z"]]


def test_dividir_quita_comillas():
    assert comun.dividir_comando("""echo "a b" 'c d'""") == [["echo", "a b", "c d"]]


def test_dividir_powershell_conserva_barras_invertidas():
    assert comun.dividir_comando("Get-Content '.\\a b.txt'", powershell=True) == [
        ["Get-Content", ".\\a b.txt"]
    ]


def test_dividir_quita_el_cuerpo_de_los_heredocs():
    comando = "git commit -F - <<'FIN'\nmensaje; con | separadores\nFIN\necho fin"
    assert comun.dividir_comando(comando) == [
        ["git", "commit", "-F", "-"],
        ["echo", "fin"],
    ]


# --- Bloqueo y fallo cerrado --------------------------------------------------------


def test_bloquear_sale_con_2_y_una_linea(capsys):
    with pytest.raises(SystemExit) as salida:
        comun.bloquear("guarda_x", "Motivo de prueba.\nOtra línea. Haz algo.")
    assert salida.value.code == 2
    error = capsys.readouterr().err
    assert error.startswith("[guarda_x] Motivo de prueba.")
    assert error.strip().count("\n") == 0


def test_ejecutar_permite_con_salida_0(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    with pytest.raises(SystemExit) as salida:
        comun.ejecutar("guarda_x", lambda entrada: None)
    assert salida.value.code == 0


def test_ejecutar_falla_cerrado_ante_una_excepcion(monkeypatch, capsys):
    def revisar(entrada):
        raise KeyError("x")

    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    with pytest.raises(SystemExit) as salida:
        comun.ejecutar("guarda_x", revisar)
    assert salida.value.code == 2
    assert capsys.readouterr().err.strip() == (
        "[guarda_x] La guarda falló (KeyError); la acción se bloquea por precaución."
    )


def test_ejecutar_falla_cerrado_si_el_json_es_invalido(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("no es json"))
    with pytest.raises(SystemExit) as salida:
        comun.ejecutar("guarda_x", lambda entrada: None)
    assert salida.value.code == 2
    assert "La guarda falló" in capsys.readouterr().err


# --- UTF-8 en los flujos, independiente del entorno (T011a) -------------------------

_GUARDA_DE_ECO = (
    "import comun\n"
    "comun.ejecutar('guarda_x', lambda e: comun.bloquear('guarda_x', e['ruta'] + ' ñandú.'))\n"
)


def entorno_sin_utf8() -> dict[str, str]:
    """El entorno de una terminal normal: sin PYTHONUTF8 ni PYTHONIOENCODING."""
    return {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}


def test_ejecutar_usa_utf8_en_stdin_y_stderr_sin_variables_de_entorno():
    resultado = subprocess.run(
        [sys.executable, "-c", _GUARDA_DE_ECO],
        input=json.dumps({"ruta": "docs/configuración/.env"}, ensure_ascii=False).encode(),
        capture_output=True,
        cwd=Path(comun.__file__).parent,
        env=entorno_sin_utf8(),
        timeout=30,
    )
    assert resultado.returncode == 2
    assert resultado.stderr.decode("utf-8").strip() == "[guarda_x] docs/configuración/.env ñandú."


# --- Extractor de texto ejecutable: comandos interiores ------------------------------


def interiores(comando, powershell=False):
    return [c.texto for c in comun.extraer_texto_ejecutable(comando, powershell).comandos]


@pytest.mark.parametrize(
    ("comando", "esperado"),
    [
        ('bash -c "cat a"', "cat a"),
        ("sh -c 'cat a'", "cat a"),
        ('bash -lc "cat a"', "cat a"),
        ('eval "cat a"', "cat a"),
        ("eval cat a", "cat a"),
        ('uv run bash -c "cat a"', "cat a"),
        ('uv run --no-project bash -c "cat a"', "cat a"),
        ("bash <<'FIN'\ncat a\nFIN", "cat a"),
        ("sh <<FIN\ncat a\nFIN", "cat a"),
    ],
)
def test_comandos_interiores_de_shells(comando, esperado):
    assert interiores(comando) == [esperado]


@pytest.mark.parametrize(
    "comando",
    ['powershell -Command "Get-Content a"', 'pwsh -c "Get-Content a"'],
)
def test_comandos_interiores_de_powershell(comando):
    extraccion = comun.extraer_texto_ejecutable(comando)
    assert [(c.texto, c.powershell) for c in extraccion.comandos] == [("Get-Content a", True)]


def test_anidamiento_hasta_3_niveles():
    comando = """eval "bash -c 'sh -c \\"cat a\\"'" """
    extraccion = comun.extraer_texto_ejecutable(comando)
    assert [c.nivel for c in extraccion.comandos] == [1, 2, 3]
    assert extraccion.comandos[-1].texto == "cat a"
    assert not extraccion.anidamiento_excesivo


def test_anidamiento_de_4_niveles_es_excesivo():
    interior = "cat a"
    for shell in ("bash -c", "sh -c", "bash -c", "eval"):
        interior = f"{shell} {shlex.quote(interior)}"
    assert comun.extraer_texto_ejecutable(interior).anidamiento_excesivo


def test_comando_interior_que_no_se_puede_analizar_pasa_a_texto():
    extraccion = comun.extraer_texto_ejecutable("""bash -c "echo 'sin cerrar" """)
    assert extraccion.comandos == []
    assert extraccion.codigos == ["echo 'sin cerrar"]


# --- Extractor de texto ejecutable: intérpretes ------------------------------------


@pytest.mark.parametrize(
    "comando",
    [
        'python -c "X"',
        'python3 -c "X"',
        'python3.12 -c "X"',
        'py -c "X"',
        'py -3 -c "X"',
        'py -3.12 -c "X"',
        'node -e "X"',
        'node --eval "X"',
        'node -p "X"',
        'node --print "X"',
        'perl -e "X"',
        'perl -E "X"',
        'ruby -e "X"',
        'uv run python -c "X"',
        'uv run --no-project python -c "X"',
        "python - <<'FIN'\nX\nFIN",
    ],
)
def test_codigo_en_linea_de_interpretes(comando):
    extraccion = comun.extraer_texto_ejecutable(comando)
    assert extraccion.codigos == ["X"]
    assert extraccion.comandos == []


def test_script_de_python_no_es_codigo_en_linea():
    assert comun.extraer_texto_ejecutable("python script.py -c X").codigos == []


def test_interprete_dentro_de_un_shell():
    extraccion = comun.extraer_texto_ejecutable("""bash -c "python -c 'X'" """)
    assert extraccion.codigos == ["X"]


# --- Extractor de texto ejecutable: heredocs que no son código ----------------------


@pytest.mark.parametrize(
    "comando",
    [
        "git commit -F - <<'FIN'\nmensaje\nFIN",
        "cat > archivo <<'FIN'\ncontenido\nFIN",
        "echo hola",
    ],
)
def test_heredocs_y_comandos_sin_texto_ejecutable(comando):
    extraccion = comun.extraer_texto_ejecutable(comando)
    assert extraccion.comandos == []
    assert extraccion.codigos == []
    assert not extraccion.anidamiento_excesivo


# --- Correcciones de la revisión de la parada B (T008a) -----------------------------


def test_herestring_no_se_toma_por_heredoc():
    comando = 'cat <<< "FIN"\npython -c "open(\'.env\')"'
    assert comun.dividir_comando(comando)[-1] == ["python", "-c", "open('.env')"]
    assert comun.extraer_texto_ejecutable(comando).codigos == ["open('.env')"]


def test_heredoc_sin_cierre_no_se_quita():
    assert comun.dividir_comando('echo "<<X"\ncat .env') == [["echo", "<<X"], ["cat", ".env"]]


@pytest.mark.parametrize("comando", ['echo "$(cat .env)"', "echo `cat .env`", "echo $(cat .env)"])
def test_sustitucion_de_comandos_es_comando_interior(comando):
    extraccion = comun.extraer_texto_ejecutable(comando)
    assert [(c.texto, c.nivel) for c in extraccion.comandos] == [("cat .env", 1)]


def test_sustitucion_entre_comillas_simples_no_cuenta():
    assert comun.extraer_texto_ejecutable("echo '$(cat .env)'").comandos == []


def test_sustitucion_en_heredoc_sin_comillas_cuenta():
    comando = "cat > a.txt <<FIN\n$(cat .env)\nFIN"
    assert [c.texto for c in comun.extraer_texto_ejecutable(comando).comandos] == ["cat .env"]


def test_sustitucion_en_heredoc_con_comillas_no_cuenta():
    comando = "cat > a.txt <<'FIN'\n$(cat .env)\nFIN"
    assert comun.extraer_texto_ejecutable(comando).comandos == []


def test_tuberia_hacia_un_interprete_es_codigo():
    comando = "echo \"print(open('.env').read())\" | python"
    codigos = comun.extraer_texto_ejecutable(comando).codigos
    assert any("open('.env')" in c for c in codigos)


def test_heredoc_por_tuberia_hacia_un_interprete_es_codigo():
    comando = "cat <<'FIN' | python3\nprint(open('.env').read())\nFIN"
    codigos = comun.extraer_texto_ejecutable(comando).codigos
    assert any("print(open('.env').read())" in c for c in codigos)


def test_tuberia_hacia_un_shell_es_comando_interior():
    comando = 'echo "cat .env" | bash'
    assert any("cat .env" in c.texto for c in comun.extraer_texto_ejecutable(comando).comandos)


def test_tuberia_hacia_un_script_no_es_codigo():
    assert comun.extraer_texto_ejecutable("echo hola | python script.py").codigos == []


def test_herestring_con_interprete_es_codigo():
    assert comun.extraer_texto_ejecutable('python <<< "X"').codigos == ["X"]


def test_herestring_con_shell_es_comando_interior():
    extraccion = comun.extraer_texto_ejecutable('bash <<< "cat a"')
    assert [c.texto for c in extraccion.comandos] == ["cat a"]


@pytest.mark.parametrize(
    "prefijo",
    [
        "FOO=1",
        "env -i FOO=1",
        "exec",
        "command",
        "nohup",
        "time",
        "nice -n 5",
        "timeout -s KILL 5",
        "uv run --with x --python 3.12",
        "FOO=1 nohup env BAR=2",
    ],
)
def test_envoltorios_delante_del_interprete(prefijo):
    assert comun.extraer_texto_ejecutable(f'{prefijo} python -c "X"').codigos == ["X"]


def test_quitar_envoltorios_deja_el_programa():
    assert comun.quitar_envoltorios(["FOO=1", "timeout", "5", "cp", "a", "b"]) == ["cp", "a", "b"]


@pytest.mark.parametrize("opcion", ["/c", "//c", "/k", "//K"])
def test_cmd_es_un_shell_interior(opcion):
    extraccion = comun.extraer_texto_ejecutable(f'cmd {opcion} "type .env"')
    assert [(c.texto, c.powershell, c.cmd) for c in extraccion.comandos] == [
        ("type .env", True, True)
    ]


def test_cmd_se_analiza_sin_barra_invertida_como_escape():
    extraccion = comun.extraer_texto_ejecutable('cmd //c "type .\\.env"')
    interior = extraccion.comandos[0]
    assert comun.dividir_comando(interior.texto, powershell=interior.powershell) == [
        ["type", ".\\.env"]
    ]


@pytest.mark.skipif(os.name != "nt", reason="las rutas /<letra>/ solo existen en Windows")
def test_ruta_de_git_bash_se_convierte_en_windows():
    base = Path("D:\\AIReadyOrquestador")
    ruta = "/d/AIReadyOrquestador/src/due_diligence/x.py"
    assert comun.normalizar_ruta(ruta, base) == "src/due_diligence/x.py"


@pytest.mark.skipif(os.name != "nt", reason="las rutas /<letra>/ solo existen en Windows")
def test_ruta_de_git_bash_desde_tmp_path(tmp_path):
    unidad, resto = str(tmp_path).replace("\\", "/").split(":", 1)
    ruta = f"/{unidad.lower()}{resto}/src/x.py"
    assert comun.normalizar_ruta(ruta, tmp_path) == "src/x.py"


# --- Correcciones de la revisión de la parada B2 (T008b) ----------------------------

# Nombres de secretos, como el patrón de texto de guarda_secretos (contrato).
_SECRETO = re.compile(
    r"(?<![\w.-])(?:\.env(?![\w])(?!\.example)|secrets[/\\]|[\w-]+\.key(?=[\"' ]|$))"
)

_COMMIT_R1 = "git commit -m \"$(cat <<'EOF'\nfix(hooks): mensaje\nEOF\n)\""


def test_commit_con_heredoc_en_sustitucion_no_falla():
    extraccion = comun.extraer_texto_ejecutable(_COMMIT_R1)
    assert extraccion.codigos == []
    assert [comun.dividir_comando(c.texto) for c in extraccion.comandos] == [[["cat"]]]


def test_heredoc_de_interprete_en_sustitucion_es_codigo():
    comando = "git commit -m \"$(python3 <<'EOF'\nimport sys\nprint(sys.argv)\nEOF\n)\""
    assert comun.extraer_texto_ejecutable(comando).codigos == ["import sys\nprint(sys.argv)"]


@pytest.mark.parametrize("comillas", ['"', "'"])
def test_heredoc_entre_comillas_es_texto(comillas):
    comando = f"echo {comillas}<<X{comillas}\ncat .env\nX"
    assert comun.dividir_comando(comando) == [["echo", "<<X"], ["cat", ".env"], ["X"]]


def test_heredoc_en_un_comentario_es_texto():
    comando = "echo hola # <<X\ncat .env\nX"
    assert comun.dividir_comando(comando) == [["echo", "hola"], ["cat", ".env"], ["X"]]


def test_el_cuerpo_viaja_con_la_palabra_de_bash_c():
    sustitucion = "$(python3 <<'EOF'\nX\nEOF\n)"
    extraccion = comun.extraer_texto_ejecutable(f'bash -c "{sustitucion}"')
    assert sustitucion in [c.texto for c in extraccion.comandos]
    assert "X" in extraccion.codigos


def test_cuerpo_con_comillas_y_parentesis_no_rompe_la_sustitucion():
    comando = (
        'echo "$(cat <<\'FIN\'\nfix(x): dice "hola" y it\'s (o no\nFIN\n)"\necho "$(cat .env)"'
    )
    extraccion = comun.extraer_texto_ejecutable(comando)
    assert "cat .env" in [c.texto for c in extraccion.comandos]


def test_marca_sin_cuerpo_lanza_value_error():
    with pytest.raises(ValueError):
        comun.dividir_comando("cat << " + comun._MARCA.format(0))


def test_marca_sin_cuerpo_en_comando_interior_vuelve_a_texto():
    texto = "cat << " + comun._MARCA.format(0)
    assert texto in comun.extraer_texto_ejecutable(f'bash -c "{texto}"').codigos


def test_delimitador_con_forma_de_marca_antigua_no_falla():
    assert comun.dividir_comando("cat << __heredoc_0__") == [["cat", "<<", "__heredoc_0__"]]


@pytest.mark.parametrize(
    "comando",
    [
        _COMMIT_R1,
        "git commit -m \"$(cat <<'EOF'\nfix(hooks): protege .env y secrets/\n\n"
        'Co-Authored-By: Claude <noreply@anthropic.com>\nEOF\n)"',
        'git commit -m "$(cat <<\'EOF\'\nfix(x): dice "hola" y it\'s\nEOF\n)"',
        "git commit -q -F - <<'EOF'\nprotege .env y secrets/\nEOF",
        'git commit -m "protege .env"',
        "git log --format='%h %s' -3",
        "gh api repos/x/y/issues --jq '.[] | .title'",
        "uv run pytest -q",
        "uv run ruff check .",
        "git switch main",
    ],
)
def test_corpus_de_comandos_legitimos(comando):
    comun.dividir_comando(comando)
    extraccion = comun.extraer_texto_ejecutable(comando)
    assert not extraccion.anidamiento_excesivo
    assert [c for c in extraccion.codigos if _SECRETO.search(c)] == []
    for interior in extraccion.comandos:
        for palabras in comun.dividir_comando(interior.texto, powershell=interior.powershell):
            assert [p for p in palabras if _SECRETO.search(p)] == [], interior.texto


# --- Correcciones de la revisión de la parada B3 (T008c): comentarios ---------------


def test_comentario_no_se_come_el_salto_de_linea():
    comando = "echo # x\npython -c \"open('.env')\""
    assert comun.extraer_texto_ejecutable(comando).codigos == ["open('.env')"]


def test_almohadilla_en_mitad_de_palabra_no_es_comentario():
    assert comun.dividir_comando("echo a#b; cat .env") == [["echo", "a#b"], ["cat", ".env"]]


@pytest.mark.parametrize(
    ("comando", "esperado"),
    [
        ("# instala\nuv sync", [["uv", "sync"]]),
        ("git log --format='#%h %s'", [["git", "log", "--format=#%h %s"]]),
        ("echo ${#x}", [["echo", "${#x}"]]),
        ("echo $#", [["echo", "$#"]]),
        ("echo a;# b\necho c", [["echo", "a"], ["echo", "c"]]),
        ("echo a|# b\ncat", [["echo", "a"], ["cat"]]),
        ("(echo a)#b", [["echo", "a"]]),
        ("\t# b\necho c", [["echo", "c"]]),
    ],
)
def test_comentarios_con_la_regla_de_bash(comando, esperado):
    assert comun.dividir_comando(comando) == esperado


def test_comentario_en_powershell_como_respaldo():
    comando = "Get-Content a # x\nGet-Content .env\nWrite-Output a#b"
    assert comun.dividir_comando(comando, powershell=True) == [
        ["Get-Content", "a"],
        ["Get-Content", ".env"],
        ["Write-Output", "a#b"],
    ]
