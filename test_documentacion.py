"""Tests de la documentación de entrega (#14): README, DECISIONES.md y docs/.

Contrato: `specs/014-documentacion-entrega/contracts/documentos.md`. Leen archivos versionados;
no llaman al modelo ni a la red. El de la revisión del historial crea un repositorio git
temporal con una credencial generada al ejecutar (nunca escrita literal).
"""

import os
import re
import secrets
import shutil
import string
import subprocess
import textwrap
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent
README = RAIZ / "README.md"
DECISIONES = RAIZ / "DECISIONES.md"
DETALLE = RAIZ / "docs" / "decisiones-detalle.md"
ENTREGA = RAIZ / "docs" / "entrega.md"
DETECTOR = RAIZ / "plugins" / "guardas-y-revision" / "hooks"

LIMITE_LINEAS = 100
COLUMNAS = 90
COMMIT_DE_PARTIDA = "f9e82d6"
TICKETS = [*range(1, 14), 19]


def leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def lineas_impresas(texto: str) -> int:
    """Líneas a `COLUMNAS` cortando por palabras; una línea vacía cuenta una (R1)."""
    return sum(max(1, len(textwrap.wrap(linea, COLUMNAS))) for linea in texto.splitlines())


def seccion(texto: str, encabezado: str) -> str:
    """El cuerpo de la sección `## encabezado`, hasta la siguiente `## `."""
    lineas = texto.splitlines()
    inicio = lineas.index(f"## {encabezado}") + 1
    fin = next((i for i in range(inicio, len(lineas)) if lineas[i].startswith("## ")), len(lineas))
    return "\n".join(lineas[inicio:fin])


def slug(encabezado: str) -> str:
    """El ancla que GitHub da a un encabezado (R3): conserva las letras con tilde."""
    texto = re.sub(r"[^\w\- ]", "", encabezado.strip().lower())
    return texto.replace(" ", "-")


def anclas(texto: str) -> set[str]:
    vistas: dict[str, int] = {}
    resultado = set()
    dentro_de_bloque = False
    for linea in texto.splitlines():
        if linea.startswith("```"):
            dentro_de_bloque = not dentro_de_bloque
        if dentro_de_bloque or not re.match(r"#{1,6} ", linea):
            continue
        base = slug(linea.lstrip("#"))
        n = vistas.get(base, 0)
        vistas[base] = n + 1
        resultado.add(base if n == 0 else f"{base}-{n}")
    return resultado


# --- DECISIONES.md (US2; FR-008 a FR-012) ----------------------------------------------


def test_decisiones_no_pasa_de_dos_paginas():
    medida = lineas_impresas(leer(DECISIONES))
    assert medida <= LIMITE_LINEAS, (
        f"DECISIONES.md mide {medida} líneas a {COLUMNAS} columnas (máximo {LIMITE_LINEAS}); "
        "lo largo va a docs/decisiones-detalle.md"
    )


def test_decisiones_tiene_una_fila_por_necesidad_con_enlace_al_detalle():
    filas = {
        int(m.group(1)): linea
        for linea in leer(DECISIONES).splitlines()
        if (m := re.match(r"\| (\d+) \|", linea))
    }
    assert sorted(filas) == list(range(1, 12))
    for numero, fila in filas.items():
        celdas = [c.strip() for c in fila.strip("|").split("|")]
        assert len(celdas) == 6, (
            f"fila {numero}: N, necesidad, mecanismo, por qué, descartado, dónde"
        )
        assert all(celdas), f"fila {numero}: hay una celda vacía"
        assert re.search(r"#\d+", celdas[5]), f"fila {numero}: «Dónde» sin ticket"
        assert "docs/decisiones-detalle.md#" in celdas[5], f"fila {numero}: sin enlace al detalle"


def test_decisiones_traza_todos_los_tickets():
    citados = {int(n) for n in re.findall(r"#(\d+)\b", leer(DECISIONES))}
    faltan = [n for n in TICKETS if n not in citados]
    assert not faltan, f"tickets sin trazar en DECISIONES.md: {faltan}"


def test_la_seccion_del_agent_sdk_ocupa_de_6_a_8_lineas():
    cuerpo = seccion(leer(DECISIONES), "Sistema con el Agent SDK")
    medida = lineas_impresas("\n".join(linea for linea in cuerpo.splitlines() if linea.strip()))
    assert 6 <= medida <= 8, f"la sección del Agent SDK mide {medida} líneas"


def test_decisiones_tiene_el_flujo_de_trabajo_y_los_limites():
    texto = leer(DECISIONES)
    flujo = seccion(texto, "Flujo de trabajo")
    for termino in ("#1", "merge commit", "Item closed", "Pull request merged", "FR-015"):
        assert termino in flujo, f"falta «{termino}» en el flujo de trabajo"
    assert seccion(texto, "Límites conocidos").count("\n- ") >= 3


def test_cada_enlace_al_detalle_llega_a_un_encabezado():
    existentes = anclas(leer(DETALLE))
    enlaces = re.findall(r"\(docs/decisiones-detalle\.md#([^)]+)\)", leer(DECISIONES))
    assert enlaces
    rotos = sorted({e for e in enlaces if e not in existentes})
    assert not rotos, f"enlaces sin encabezado en el detalle: {rotos}"


def test_los_enlaces_internos_del_detalle_llegan_a_un_encabezado():
    texto = leer(DETALLE)
    rotos = sorted({e for e in re.findall(r"\]\(#([^)]+)\)", texto) if e not in anclas(texto)})
    assert not rotos, f"enlaces internos rotos: {rotos}"


# --- docs/decisiones-detalle.md (US3; FR-013, FR-014) --------------------------------


def test_el_detalle_conserva_sin_perdida_el_decisiones_de_partida():
    try:
        partida = subprocess.run(
            ["git", "show", f"{COMMIT_DE_PARTIDA}:DECISIONES.md"],
            cwd=RAIZ,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip(f"sin git o sin el commit {COMMIT_DE_PARTIDA} (clon superficial)")
    detalle = iter(leer(DETALLE).splitlines())
    for numero, linea in enumerate(partida.splitlines(), 1):
        if linea.strip():
            assert any(linea == otra for otra in detalle), (
                f"la línea {numero} del DECISIONES.md de partida falta o está fuera de orden"
            )


@pytest.mark.parametrize(
    "termino",
    [
        "contexto_revision.py:160",
        "revisor-codigo.md:67",
        "T055",
        "## Desviaciones declaradas",
        "## Sugerencias no atendidas de los PR",
        "## Mejoras futuras",
        "**Corrección (#14)**",
        "**Precisión (#14)**",
    ],
)
def test_el_detalle_tiene_los_anadidos(termino):
    assert termino in leer(DETALLE)


def test_el_detalle_enlaza_el_pr_de_cada_ticket_con_sugerencias():
    prs = {int(n) for n in re.findall(r"/pull/(\d+)\)", leer(DETALLE))}
    assert prs >= {16, 17, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29}


# --- README (US1; FR-001 a FR-007) --------------------------------------------------


def test_el_inicio_rapido_es_la_primera_seccion_con_sus_cinco_pasos_en_orden():
    texto = leer(README)
    primera = next(linea for linea in texto.splitlines() if linea.startswith("## "))
    assert primera == "## Inicio rápido"
    cuerpo = seccion(texto, "Inicio rápido")
    posiciones = [
        cuerpo.find(paso)
        for paso in (
            "uv python install 3.12",
            "uv sync",
            ".env.example",
            "uv run pytest src",
            "streamlit run",
        )
    ]
    assert -1 not in posiciones, f"faltan pasos: {posiciones}"
    assert posiciones == sorted(posiciones), "los pasos no están en orden"


def test_el_readme_tiene_los_mensajes_de_los_siete_casos():
    pytest.importorskip("claude_agent_sdk")
    from due_diligence.conftest import CASOS

    texto = leer(README)
    assert sorted(CASOS) == list("abcdefg")
    for letra, caso in CASOS.items():
        for mensaje in caso.mensajes:
            assert mensaje in texto, f"caso ({letra}): falta su mensaje en el README"


@pytest.mark.parametrize(
    "termino",
    [
        "https://github.com/users/anahernandez0814/projects/1",
        "**Video de funcionamiento**",
        "ANTHROPIC_API_KEY",
        "GITHUB_PAT",
        "`.mcp.json` no lee `.env`",
        "`repo` y `project`",
        "claude plugin marketplace add",
        "extraKnownMarketplaces",
        "el repositorio es privado y pide acceso",
        "4:43",
    ],
)
def test_el_readme_tiene_lo_que_pide_la_entrega(termino):
    assert termino in leer(README)


# --- docs/entrega.md (US5; FR-017 a FR-021) ------------------------------------------


@pytest.mark.parametrize(
    "termino",
    [
        "Acceso de los evaluadores",
        "clon limpio",
        ".specify/memory/",
        "50 MB",
        "no se reescribió",
        "ventana privada",
        "el repositorio es privado y pide acceso",
        "## Guion del video de funcionamiento",
        "## Guion del video de defensa",
    ],
)
def test_la_entrega_tiene_la_lista_y_los_guiones(termino):
    assert termino in leer(ENTREGA)


def bloque(nombre: str) -> str:
    """El primer bloque de código tras `<!-- bloque: nombre -->` de docs/entrega.md."""
    texto = leer(ENTREGA)
    marca = texto.index(f"<!-- bloque: {nombre} -->")
    m = re.compile(r"```[a-z]*\n(.*?)\n```", re.DOTALL).search(texto, marca)
    assert m, f"sin bloque de código tras la marca {nombre}"
    return m.group(1)


def bash() -> str | None:
    """Git Bash en Windows (el `bash` de System32 es WSL); `bash` en el resto."""
    if os.name == "nt":
        git = shutil.which("git")
        # La raíz de Git for Windows es la carpeta con `bin/bash.exe` y `usr/bin/`, por encima
        # de `cmd/`, `mingw64/bin/` o `ucrt64/bin/`, según dónde esté `git` en el PATH.
        for carpeta in Path(git).resolve().parents if git else ():
            if (carpeta / "bin" / "bash.exe").exists() and (carpeta / "usr" / "bin").is_dir():
                return str(carpeta / "bin" / "bash.exe")
        return None
    return shutil.which("bash")


@pytest.fixture
def repositorio_con_credencial(tmp_path):
    """Un repo git con un token de GitHub generado al ejecutar, en un commit anterior."""
    alfabeto = string.ascii_letters + string.digits
    valor = "ghp_" + "".join(secrets.choice(alfabeto) for _ in range(36))
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "prueba@example.invalid")
    git("config", "user.name", "Prueba")
    (repo / "config.txt").write_text(f"token = {valor}\n", encoding="utf-8")
    git("add", "config.txt")
    git("commit", "-q", "-m", "con credencial")
    (repo / "config.txt").write_text("token = (ninguno)\n", encoding="utf-8")
    git("commit", "-q", "-am", "sin credencial")
    return repo, valor


@pytest.mark.parametrize("nombre", ["revision-prefijos", "revision-detector"])
def test_la_revision_del_historial_encuentra_la_credencial_sin_mostrarla(
    nombre, repositorio_con_credencial, tmp_path
):
    ejecutable = bash()
    if ejecutable is None:
        pytest.skip("sin bash para ejecutar el bloque")
    repo, valor = repositorio_con_credencial
    guion = tmp_path / f"{nombre}.sh"
    guion.write_text(bloque(nombre) + "\n", encoding="utf-8", newline="\n")
    salida = subprocess.run(
        [ejecutable, str(guion)],
        cwd=repo,
        capture_output=True,
        env={**os.environ, "DETECTOR": str(DETECTOR)},
        timeout=120,
    )
    texto = (salida.stdout + salida.stderr).decode("utf-8", "replace")
    assert "config.txt" in texto, f"{nombre} no encontró la credencial:\n{texto}"
    assert valor not in texto, f"{nombre} imprimió el valor"
    assert valor[4:] not in texto, f"{nombre} imprimió parte del valor"
