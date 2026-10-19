"""Pruebas de contexto_revision.py: el contexto que la skill inyecta antes del revisor."""

import ast
import io
import os
import subprocess
import sys
from pathlib import Path

import contexto_revision
import pytest

SCRIPT = Path(__file__).with_name("contexto_revision.py")
MARCA = "CONTEXTO DE REVISIÓN"
_IDENTIDAD = {
    "GIT_AUTHOR_NAME": "Prueba",
    "GIT_AUTHOR_EMAIL": "prueba@example.invalid",
    "GIT_COMMITTER_NAME": "Prueba",
    "GIT_COMMITTER_EMAIL": "prueba@example.invalid",
}


def git(cwd: Path, *args: str) -> str:
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    entorno.update(_IDENTIDAD)
    resultado = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        check=True,
    )
    return resultado.stdout.strip()


def escribir(repo: Path, ruta: str, contenido: str) -> None:
    destino = repo / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8", newline="\n")


def confirmar(repo: Path, mensaje: str = "cambio") -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", mensaje)


def repositorio(tmp_path: Path, rama: str = "cambio", remoto: bool = False) -> Path:
    """`main` con un commit inicial y la rama `rama` con un cambio en `app/a.py`."""
    trabajo = tmp_path / "trabajo"
    trabajo.mkdir()
    git(trabajo, "init", "-q", "-b", "main")
    escribir(trabajo, "README.md", "Repositorio de prueba\n")
    confirmar(trabajo, "inicio")
    if remoto:
        origen = tmp_path / "origen.git"
        origen.mkdir()
        git(origen, "init", "-q", "--bare", "-b", "main")
        git(trabajo, "remote", "add", "origin", str(origen))
        git(trabajo, "push", "-q", "-u", "origin", "main")
    git(trabajo, "switch", "-q", "-c", rama)
    escribir(trabajo, "app/a.py", "x = 1\ny = 2\n")
    confirmar(trabajo, "cambio")
    return trabajo


def lineas(salida: str, prefijo: str) -> list[str]:
    return [x for x in salida.splitlines() if x.startswith(prefijo)]


# --- Marca, base y archivos ------------------------------------------------------------


def test_la_primera_linea_es_la_marca(tmp_path):
    salida = contexto_revision.construir(repositorio(tmp_path))
    assert salida.splitlines()[0] == MARCA


def test_base_main_local_sin_remoto(tmp_path):
    repo = repositorio(tmp_path)
    base = git(repo, "merge-base", "HEAD", "main")
    salida = contexto_revision.construir(repo)
    assert f"Base: {base[:12]} (git merge-base HEAD main)" in salida
    assert "CONTEXTO INCOMPLETO" not in salida
    assert "app/a.py" in salida
    assert "Diff completo:" in salida


def test_base_por_origin_head(tmp_path):
    repo = repositorio(tmp_path, remoto=True)
    git(repo, "remote", "set-head", "origin", "main")
    salida = contexto_revision.construir(repo)
    assert "(git merge-base HEAD origin/main)" in salida


def test_origin_main_gana_al_main_local(tmp_path):
    repo = repositorio(tmp_path, remoto=True)
    base = git(repo, "merge-base", "HEAD", "origin/main")
    git(repo, "switch", "-q", "main")
    escribir(repo, "otro.txt", "solo en el main local\n")
    confirmar(repo, "main local adelantado")
    git(repo, "switch", "-q", "cambio")
    salida = contexto_revision.construir(repo)
    assert f"Base: {base[:12]} (git merge-base HEAD origin/main)" in salida
    assert "otro.txt" not in salida


def test_sin_base_de_fusion_es_incompleto(tmp_path):
    repo = tmp_path / "solo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "trabajo")
    escribir(repo, "a.txt", "a\n")
    confirmar(repo, "inicio")
    salida = contexto_revision.construir(repo)
    assert lineas(salida, "CONTEXTO INCOMPLETO: no hay base de fusión")
    assert "Archivos cambiados" not in salida


def test_fuera_de_un_repositorio_git(tmp_path):
    salida = contexto_revision.construir(tmp_path)
    assert salida.splitlines() == [
        MARCA,
        "CONTEXTO INCOMPLETO: la carpeta no es un repositorio git",
    ]


# --- Archivos movidos -------------------------------------------------------------------

CONTENIDO_MOVIDO = "".join(f"linea_{i} = {i}\n" for i in range(10))


@pytest.fixture
def movidos(tmp_path):
    """La rama mueve `igual.py` tal cual a `lib/`, mueve y cambia `cambia.py` y borra `viejo.py`."""
    repo = repositorio(tmp_path)
    git(repo, "switch", "-q", "main")
    for nombre in ("igual.py", "cambia.py", "viejo.py"):
        escribir(repo, nombre, CONTENIDO_MOVIDO if nombre != "viejo.py" else "a = 1\n")
    confirmar(repo, "archivos que se moverán")
    git(repo, "switch", "-q", "cambio")
    git(repo, "merge", "-q", "--no-edit", "main")
    (repo / "lib").mkdir()
    (repo / "igual.py").rename(repo / "lib" / "igual.py")
    (repo / "cambia.py").unlink()
    (repo / "viejo.py").unlink()
    escribir(repo, "lib/cambia.py", CONTENIDO_MOVIDO.replace("linea_5 = 5", "linea_5 = 50"))
    confirmar(repo, "mueve y borra")
    return repo


def fila(salida: str, ruta: str) -> str:
    coincidencias = [x for x in salida.splitlines() if f"  {ruta}" in x and "+" in x]
    assert coincidencias, f"{ruta} no aparece en la lista"
    return coincidencias[0]


def test_un_movido_sin_cambios_aparece_en_su_ruta_nueva(movidos):
    salida = contexto_revision.construir(movidos)
    assert fila(salida, "lib/igual.py") == (
        "R  +0 -0  lib/igual.py [movido desde igual.py, similitud 100 %]"
    )
    assert "Diff de lib/igual.py" not in salida


def test_un_movido_con_cambios_trae_su_diff(movidos):
    salida = contexto_revision.construir(movidos)
    linea = fila(salida, "lib/cambia.py")
    assert linea.startswith("R  +1 -1  lib/cambia.py [movido desde cambia.py, similitud ")
    assert "Diff completo:" in salida
    assert "+linea_5 = 50" in salida


def test_un_eliminado_de_verdad_sigue_marcado_y_los_movidos_no(movidos):
    salida = contexto_revision.construir(movidos)
    assert [x for x in salida.splitlines() if "[eliminado]" in x] == [
        "D  +0 -1  viejo.py [eliminado]"
    ]


def test_si_el_diff_completo_no_cabe_va_el_de_cada_movido_con_cambios(movidos):
    escribir(movidos, "app/grande.py", "x = 1\n" * 3000)
    confirmar(movidos, "grande")
    salida = contexto_revision.construir(movidos)
    assert "Diff omitido" in salida
    assert "Diff de lib/cambia.py (movido desde cambia.py):" in salida
    assert "+linea_5 = 50" in salida
    assert "Diff de lib/igual.py" not in salida
    justo = len(salida[: salida.index("Diff de lib/cambia.py")].encode("utf-8")) + 10
    salida = contexto_revision.construir(movidos, umbral=justo)
    assert "Diff de lib/cambia.py (movido desde cambia.py) omitido: no cabe en el umbral" in salida
    assert "+linea_5 = 50" not in salida


# --- Spec Kit, opcional ---------------------------------------------------------------


def test_sin_carpeta_specs_el_ticket_no_aplica_y_no_es_incompleto(tmp_path):
    salida = contexto_revision.construir(repositorio(tmp_path))
    assert "Ticket: no aplica (el repositorio no usa una carpeta specs/)" in salida
    assert "Constitución: no aplica" in salida
    assert "CONTEXTO INCOMPLETO" not in salida


NUMERO = "123"
TICKET = f"{NUMERO}-demo"
CONSTITUCION = ".specify/memory/constitution.md"
SIN_PATRON = "la rama «cambio» no sigue el patrón NNN-nombre"
SIN_CARPETA = f"no hay exactamente una carpeta specs/{NUMERO}-* del ticket"
# (rama, carpetas specs/…, motivo) de los casos que no siguen la convención.
FUERA_DE_LA_CONVENCION = [
    pytest.param("cambio", [TICKET], SIN_PATRON, id="rama-sin-patron"),
    pytest.param(TICKET, [], SIN_CARPETA, id="ninguna-carpeta"),
    pytest.param(TICKET, [f"{NUMERO}-uno", f"{NUMERO}-dos"], SIN_CARPETA, id="dos-carpetas"),
]


def con_specs(tmp_path: Path, rama: str, carpetas: list[str], constitucion: bool) -> Path:
    """Repositorio con `specs/` (siempre con la carpeta de otro ticket) y las `carpetas` dadas."""
    repo = repositorio(tmp_path, rama=rama)
    escribir(repo, "specs/999-otro/spec.md", "# spec\n")
    for carpeta in carpetas:
        for nombre in ("spec.md", "plan.md", "tasks.md"):
            escribir(repo, f"specs/{carpeta}/{nombre}", f"# {nombre}\n")
    if constitucion:
        escribir(repo, CONSTITUCION, "# Constitución\n")
    confirmar(repo, "documentos")
    return repo


@pytest.mark.parametrize(
    "constitucion", [True, False], ids=["con-constitucion", "sin-constitucion"]
)
def test_rama_de_ticket_con_una_carpeta_usa_el_ticket(tmp_path, constitucion):
    salida = contexto_revision.construir(con_specs(tmp_path, TICKET, [TICKET], constitucion))
    assert f"Ticket: specs/{TICKET}/" in salida
    assert f"  - specs/{TICKET}/spec.md" in salida
    assert f"specs/{TICKET}/plan.md [referencia]" in salida
    esperada = f"Constitución: {CONSTITUCION}" if constitucion else "Constitución: no aplica"
    assert esperada in salida
    assert "CONTEXTO INCOMPLETO" not in salida


@pytest.mark.parametrize(("rama", "carpetas", "motivo"), FUERA_DE_LA_CONVENCION)
def test_con_constitucion_fuera_de_la_convencion_es_incompleto(tmp_path, rama, carpetas, motivo):
    salida = contexto_revision.construir(con_specs(tmp_path, rama, carpetas, constitucion=True))
    assert lineas(salida, "CONTEXTO INCOMPLETO:") == [f"CONTEXTO INCOMPLETO: {motivo}"]
    assert not lineas(salida, "Ticket:")


@pytest.mark.parametrize(("rama", "carpetas", "motivo"), FUERA_DE_LA_CONVENCION)
def test_sin_constitucion_fuera_de_la_convencion_el_ticket_no_aplica(
    tmp_path, rama, carpetas, motivo
):
    salida = contexto_revision.construir(con_specs(tmp_path, rama, carpetas, constitucion=False))
    assert lineas(salida, "Ticket:") == [f"Ticket: no aplica (sin constitución, {motivo})"]
    assert "CONTEXTO INCOMPLETO" not in salida


def test_specs_para_otra_cosa_sin_constitucion_no_reduce_la_cobertura(tmp_path):
    # Otro equipo usa specs/ para sus tests, y GitHub crea la rama NNN-título desde el issue.
    repo = repositorio(tmp_path, rama=f"{NUMERO}-arreglar-el-login")
    escribir(repo, "specs/test_login.py", "def test_login():\n    assert True\n")
    escribir(repo, "specs/datos/usuarios.json", "[]\n")
    confirmar(repo, "tests")
    salida = contexto_revision.construir(repo)
    assert lineas(salida, "Ticket:") == [f"Ticket: no aplica (sin constitución, {SIN_CARPETA})"]
    assert "Constitución: no aplica" in salida
    assert "CONTEXTO INCOMPLETO" not in salida


# --- Umbral -------------------------------------------------------------------------------


def test_diff_omitido_si_supera_el_umbral(tmp_path):
    repo = repositorio(tmp_path)
    escribir(repo, "app/grande.py", "x = 1\n" * 3000)
    confirmar(repo, "grande")
    salida = contexto_revision.construir(repo)
    assert "Diff completo:" not in salida
    assert "Diff omitido" in salida
    assert "app/grande.py" in salida


def test_lista_agrupada_si_la_lista_no_cabe(tmp_path):
    repo = repositorio(tmp_path)
    for i in range(40):
        escribir(repo, f"app/m{i:02d}.py", "x = 1\n")
    confirmar(repo, "muchos")
    salida = contexto_revision.construir(repo, umbral=500)
    assert "lista agrupada por directorio" in salida
    assert "app/: 41 archivos" in salida


# --- Script ---------------------------------------------------------------------------------


def test_el_script_sale_con_0_y_la_marca(tmp_path):
    repo = repositorio(tmp_path)
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        timeout=60,
    )
    assert resultado.returncode == 0
    assert resultado.stdout.splitlines()[0] == MARCA
    assert "app/a.py" in resultado.stdout


def test_error_inesperado_sale_con_0_y_contexto_incompleto(monkeypatch, capsys):
    def falla(_raiz):
        raise RuntimeError("fallo")

    monkeypatch.setattr(contexto_revision, "construir", falla)
    assert contexto_revision.main() == 0
    assert capsys.readouterr().out.splitlines() == [
        MARCA,
        "CONTEXTO INCOMPLETO: error inesperado (RuntimeError)",
    ]


def test_si_no_puede_reconfigurar_los_flujos_sale_con_0_y_contexto_incompleto(monkeypatch, capsys):
    class StderrQueFalla(io.StringIO):
        def reconfigure(self, **_):
            raise OSError("sin reconfigurar")

    monkeypatch.setattr(sys, "stderr", StderrQueFalla())
    assert contexto_revision.main() == 0
    assert capsys.readouterr().out.splitlines() == [
        MARCA,
        "CONTEXTO INCOMPLETO: error inesperado (OSError)",
    ]


def test_solo_usa_la_biblioteca_estandar():
    arbol = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    modulos = {
        alias.name.split(".")[0]
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Import)
        for alias in nodo.names
    } | {
        nodo.module.split(".")[0]
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }
    assert modulos <= set(sys.stdlib_module_names)


@pytest.mark.parametrize("variable", ["CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT"])
def test_la_raiz_es_el_directorio_actual(tmp_path, monkeypatch, variable):
    # Bash no recibe las variables del plugin: la skill ejecuta el script en el proyecto.
    monkeypatch.setenv(variable, str(tmp_path / "otra"))
    monkeypatch.chdir(tmp_path)
    assert contexto_revision.raiz() == Path.cwd()
