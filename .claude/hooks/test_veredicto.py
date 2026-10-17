"""Pruebas de veredicto.py (R7, R8, FR-008, FR-010, FR-011; contracts/veredicto-y-guarda.md)."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import veredicto
from repositorio_pruebas import confirmar, crear_repo, escribir, git

SCRIPT = Path(__file__).with_name("veredicto.py")
LIMPIO = "RESUMEN: bloqueantes=0 sugerencias=2 cobertura=completa"
CON_BLOQUEANTES = "RESUMEN: bloqueantes=3 sugerencias=0 cobertura=completa"
INCOMPLETO = "RESUMEN: bloqueantes=0 sugerencias=0 cobertura=incompleta"
ACTUAL = object()
FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@pytest.fixture
def repo(tmp_path):
    return crear_repo(tmp_path)


@pytest.fixture
def repo_con_cambio(repo):
    escribir(repo, "src/a.py", "x = 1\n")
    confirmar(repo, "cambio")
    return repo


def registrar(repo, codigo, auditoria, commit=None):
    """Registra el veredicto del commit revisado; por omisión, el actual."""
    if commit is None:
        commit = git(repo, "rev-parse", "HEAD")
    return veredicto.registrar(repo, commit, codigo, auditoria)


def archivos_de_veredicto(repo):
    return sorted((repo / ".claude" / "veredictos").glob("*.json"))


# --- Línea RESUMEN -------------------------------------------------------------------


def test_parsear_resumen_valido():
    assert veredicto.parsear_resumen(LIMPIO) == {
        "bloqueantes": 0,
        "sugerencias": 2,
        "cobertura": "completa",
    }


def test_parsear_resumen_dentro_de_un_reporte():
    reporte = f"## Hallazgos\n- SUGERENCIA a.py:1 — algo\n\n{CON_BLOQUEANTES}\n"
    assert veredicto.parsear_resumen(reporte) == {
        "bloqueantes": 3,
        "sugerencias": 0,
        "cobertura": "completa",
    }


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "sin resumen",
        "RESUMEN: bloqueantes=0 sugerencias=2",
        "RESUMEN: bloqueantes=0  sugerencias=2 cobertura=completa",
        "RESUMEN: bloqueantes=a sugerencias=2 cobertura=completa",
        "RESUMEN: bloqueantes=0 sugerencias=2 cobertura=parcial",
        f"{LIMPIO} extra",
        "resumen: bloqueantes=0 sugerencias=2 cobertura=completa",
        "RESUMEN: sugerencias=2 bloqueantes=0 cobertura=completa",
        f"{LIMPIO}\n{LIMPIO}",
        f"{LIMPIO}\n{CON_BLOQUEANTES}",
        # Dígitos de otros alfabetos: el formato usa solo [0-9] (hallazgo 2)
        "RESUMEN: bloqueantes=٠ sugerencias=2 cobertura=completa",
        "RESUMEN: bloqueantes=０ sugerencias=2 cobertura=completa",
        "RESUMEN: bloqueantes=0 sugerencias=٢ cobertura=completa",
        "RESUMEN: bloqueantes=0 sugerencias=２ cobertura=incompleta",
    ],
)
def test_parsear_resumen_no_utilizable(texto):
    assert veredicto.parsear_resumen(texto) is None


# --- Consolidación ------------------------------------------------------------------


def _resumen(bloqueantes=0, cobertura="completa"):
    return {"bloqueantes": bloqueantes, "sugerencias": 0, "cobertura": cobertura}


def test_consolidar_aprobado():
    assert veredicto.consolidar(_resumen(), _resumen(), True) == ("aprobado", None)


@pytest.mark.parametrize(
    ("codigo", "auditoria"),
    [
        (_resumen(1), _resumen()),
        (_resumen(), _resumen(2)),
        (_resumen(cobertura="incompleta"), _resumen()),
        (_resumen(), _resumen(cobertura="incompleta")),
        (None, _resumen()),
        (_resumen(), None),
        (None, None),
    ],
)
def test_consolidar_con_bloqueantes(codigo, auditoria):
    resultado, motivo = veredicto.consolidar(codigo, auditoria, True)
    assert resultado == "con bloqueantes"
    assert motivo


def test_consolidar_sin_cambios_no_se_aprueba_aunque_los_resumenes_sean_limpios():
    assert veredicto.consolidar(_resumen(), _resumen(), False) == (
        "con bloqueantes",
        "sin cambios",
    )


def test_consolidar_sin_base_de_comparacion():
    assert veredicto.consolidar(_resumen(), _resumen(), None) == (
        "con bloqueantes",
        "sin base de comparación",
    )


# --- Base y cambios ------------------------------------------------------------------


def test_base_de_fusion_es_la_de_origin_main(repo_con_cambio):
    assert veredicto.base_de_fusion(repo_con_cambio) == git(repo_con_cambio, "rev-parse", "main")


def test_hay_cambios(repo, repo_con_cambio):
    assert veredicto.hay_cambios(repo) is True


def test_sin_cambios_frente_a_la_base(repo):
    assert veredicto.hay_cambios(repo) is False


def test_sin_origin_main_no_hay_base(repo):
    git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    assert veredicto.base_de_fusion(repo) is None
    assert veredicto.hay_cambios(repo) is None


def test_la_base_no_es_el_main_local(repo_con_cambio):
    repo = repo_con_cambio
    git(repo, "switch", "-q", "main")
    escribir(repo, "otro.txt", "solo en el main local\n")
    confirmar(repo, "main local adelantado")
    git(repo, "switch", "-q", "004-demo")
    assert veredicto.base_de_fusion(repo) == git(repo, "rev-parse", "origin/main")


# --- Registro y lectura --------------------------------------------------------------


def test_registrar_aprobado_escribe_el_archivo_del_commit(repo_con_cambio):
    repo = repo_con_cambio
    sha = git(repo, "rev-parse", "HEAD")
    assert registrar(repo, LIMPIO, LIMPIO) == ("aprobado", None)
    archivo = veredicto.ruta_veredicto(repo, sha)
    assert archivo == repo / ".claude" / "veredictos" / f"{sha}.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    assert datos["commit"] == sha
    assert datos["rama"] == "004-demo"
    assert datos["veredicto"] == "aprobado"
    assert FECHA.match(datos["fecha"])
    assert datos["codigo"] == {"bloqueantes": 0, "sugerencias": 2, "cobertura": "completa"}
    assert datos["auditoria"] == {"bloqueantes": 0, "sugerencias": 2, "cobertura": "completa"}


def test_registrar_con_bloqueantes_tambien_se_registra(repo_con_cambio):
    repo = repo_con_cambio
    sha = git(repo, "rev-parse", "HEAD")
    resultado, motivo = registrar(repo, CON_BLOQUEANTES, LIMPIO)
    assert resultado == "con bloqueantes"
    assert motivo
    datos = veredicto.leer(repo, sha)
    assert datos["veredicto"] == "con bloqueantes"
    assert datos["codigo"]["bloqueantes"] == 3


def test_registrar_con_reporte_no_utilizable_guarda_nulo(repo_con_cambio):
    repo = repo_con_cambio
    sha = git(repo, "rev-parse", "HEAD")
    resultado, _ = registrar(repo, "sin resumen", LIMPIO)
    assert resultado == "con bloqueantes"
    datos = veredicto.leer(repo, sha)
    assert datos["codigo"] is None
    assert datos["auditoria"]["cobertura"] == "completa"


def test_registrar_incompleto_no_se_aprueba(repo_con_cambio):
    resultado, _ = registrar(repo_con_cambio, INCOMPLETO, LIMPIO)
    assert resultado == "con bloqueantes"


def test_registrar_rama_sin_cambios(repo):
    sha = git(repo, "rev-parse", "HEAD")
    assert registrar(repo, LIMPIO, LIMPIO) == ("con bloqueantes", "sin cambios")
    assert veredicto.leer(repo, sha)["veredicto"] == "con bloqueantes"


def test_registrar_sin_base_de_comparacion(repo_con_cambio):
    git(repo_con_cambio, "update-ref", "-d", "refs/remotes/origin/main")
    assert registrar(repo_con_cambio, LIMPIO, LIMPIO) == (
        "con bloqueantes",
        "sin base de comparación",
    )


def test_un_archivo_por_commit_y_se_sobrescribe_el_del_mismo_commit(repo_con_cambio):
    repo = repo_con_cambio
    primero = git(repo, "rev-parse", "HEAD")
    registrar(repo, CON_BLOQUEANTES, LIMPIO)
    registrar(repo, LIMPIO, LIMPIO)
    assert veredicto.leer(repo, primero)["veredicto"] == "aprobado"
    escribir(repo, "src/b.py", "y = 2\n")
    segundo = confirmar(repo, "otro cambio")
    assert veredicto.leer(repo, segundo) is None
    assert veredicto.leer(repo, primero)["veredicto"] == "aprobado"
    assert len(list((repo / ".claude" / "veredictos").glob("*.json"))) == 1


@pytest.mark.parametrize(
    "contenido",
    [
        "no es json",
        "[]",
        "{}",
        json.dumps({"commit": "otro", "veredicto": "aprobado"}),
    ],
)
def test_leer_archivo_ilegible_o_con_otro_formato(repo_con_cambio, contenido):
    repo = repo_con_cambio
    sha = git(repo, "rev-parse", "HEAD")
    archivo = veredicto.ruta_veredicto(repo, sha)
    archivo.parent.mkdir(parents=True)
    archivo.write_text(contenido, encoding="utf-8")
    assert veredicto.leer(repo, sha) is None


def test_leer_con_commit_distinto_del_nombre(repo_con_cambio):
    repo = repo_con_cambio
    sha = git(repo, "rev-parse", "HEAD")
    registrar(repo, LIMPIO, LIMPIO)
    datos = json.loads(veredicto.ruta_veredicto(repo, sha).read_text(encoding="utf-8"))
    datos["commit"] = "0" * 40
    veredicto.ruta_veredicto(repo, sha).write_text(json.dumps(datos), encoding="utf-8")
    assert veredicto.leer(repo, sha) is None


def test_leer_veredicto_inexistente(repo_con_cambio):
    assert veredicto.leer(repo_con_cambio, "a" * 40) is None


@pytest.mark.parametrize("sha", ["", "abc", "../x", "g" * 40, "A" * 40, "a" * 41])
def test_ruta_veredicto_rechaza_un_sha_que_no_es_hexadecimal(tmp_path, sha):
    with pytest.raises(ValueError):
        veredicto.ruta_veredicto(tmp_path, sha)


# --- Línea de comandos ---------------------------------------------------------------


def ejecutar_cli(repo, codigo, auditoria, commit=ACTUAL):
    """`ACTUAL` pasa el sha de HEAD; `None` omite `--commit`."""
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    entorno["CLAUDE_PROJECT_DIR"] = str(repo)
    if commit is ACTUAL:
        commit = git(repo, "rev-parse", "HEAD")
    argumentos = ["--commit", commit] if commit is not None else []
    return subprocess.run(
        [sys.executable, str(SCRIPT), "registrar", *argumentos]
        + ["--codigo", codigo, "--auditoria", auditoria],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
        check=False,
    )


def test_cli_aprobado(repo_con_cambio):
    resultado = ejecutar_cli(repo_con_cambio, LIMPIO, LIMPIO)
    assert resultado.returncode == 0
    assert resultado.stdout.strip() == "veredicto: aprobado"


def test_cli_con_bloqueantes_sale_con_uno(repo_con_cambio):
    resultado = ejecutar_cli(repo_con_cambio, CON_BLOQUEANTES, LIMPIO)
    assert resultado.returncode == 1
    assert resultado.stdout.startswith("veredicto: con bloqueantes (")


def test_cli_sin_cambios_sale_con_uno(repo):
    resultado = ejecutar_cli(repo, LIMPIO, LIMPIO)
    assert resultado.returncode == 1
    assert resultado.stdout.strip() == "veredicto: con bloqueantes (sin cambios)"


def test_cli_sin_poder_registrar_sale_con_dos(tmp_path):
    resultado = ejecutar_cli(tmp_path, LIMPIO, LIMPIO, commit="a" * 40)
    assert resultado.returncode == 2
    assert resultado.stderr.strip()
    assert "Traceback" not in resultado.stderr


def test_cli_sin_argumentos_sale_con_dos(tmp_path):
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert resultado.returncode == 2


# --- El veredicto queda atado al commit revisado (hallazgo 1) ---------------------------


def mensaje_de_commit_cambiado(revisado, actual):
    return (
        f"El commit cambió durante la revisión (revisado {revisado[:7]}, actual {actual[:7]}): "
        "ejecute /abrir-pr de nuevo."
    )


def commit_nuevo(repo):
    escribir(repo, "src/b.py", "y = 2\n")
    return confirmar(repo, "commit durante la revisión")


def test_registrar_con_un_commit_que_ya_no_es_head_lanza_y_no_escribe(repo_con_cambio):
    repo = repo_con_cambio
    revisado = git(repo, "rev-parse", "HEAD")
    actual = commit_nuevo(repo)
    with pytest.raises(veredicto.CommitCambiado) as error:
        registrar(repo, LIMPIO, LIMPIO, commit=revisado)
    assert str(error.value) == mensaje_de_commit_cambiado(revisado, actual)
    assert archivos_de_veredicto(repo) == []
    assert veredicto.leer(repo, actual) is None
    assert veredicto.leer(repo, revisado) is None


def test_registrar_con_el_commit_de_head_hace_lo_de_siempre(repo_con_cambio):
    repo = repo_con_cambio
    sha = git(repo, "rev-parse", "HEAD")
    assert registrar(repo, LIMPIO, LIMPIO, commit=sha) == ("aprobado", None)
    assert veredicto.leer(repo, sha)["commit"] == sha


@pytest.mark.parametrize("commit", ["", "abc1234", "g" * 40, "A" * 40, "../x", "a" * 41])
def test_registrar_rechaza_un_commit_que_no_es_un_sha_completo(repo_con_cambio, commit):
    with pytest.raises(ValueError):
        registrar(repo_con_cambio, LIMPIO, LIMPIO, commit=commit)
    assert archivos_de_veredicto(repo_con_cambio) == []


def test_cli_con_un_commit_distinto_de_head_sale_con_dos_y_no_escribe(repo_con_cambio):
    repo = repo_con_cambio
    revisado = git(repo, "rev-parse", "HEAD")
    actual = commit_nuevo(repo)
    resultado = ejecutar_cli(repo, LIMPIO, LIMPIO, commit=revisado)
    assert resultado.returncode == 2
    assert resultado.stderr.strip() == mensaje_de_commit_cambiado(revisado, actual)
    assert resultado.stdout == ""
    assert archivos_de_veredicto(repo) == []


def test_cli_sin_commit_sale_con_dos_y_no_escribe(repo_con_cambio):
    resultado = ejecutar_cli(repo_con_cambio, LIMPIO, LIMPIO, commit=None)
    assert resultado.returncode == 2
    assert "--commit" in resultado.stderr
    assert archivos_de_veredicto(repo_con_cambio) == []


@pytest.mark.parametrize("commit", ["abc1234", "g" * 40, "A" * 40, "a" * 41, "HEAD"])
def test_cli_con_un_commit_abreviado_o_no_hexadecimal_sale_con_dos(repo_con_cambio, commit):
    resultado = ejecutar_cli(repo_con_cambio, LIMPIO, LIMPIO, commit=commit)
    assert resultado.returncode == 2
    assert resultado.stderr.strip()
    assert "Traceback" not in resultado.stderr
    assert archivos_de_veredicto(repo_con_cambio) == []


def test_cli_con_el_commit_de_head_aprueba_como_siempre(repo_con_cambio):
    repo = repo_con_cambio
    resultado = ejecutar_cli(repo, LIMPIO, LIMPIO)
    assert resultado.returncode == 0
    assert resultado.stdout.strip() == "veredicto: aprobado"
    assert [p.stem for p in archivos_de_veredicto(repo)] == [git(repo, "rev-parse", "HEAD")]
