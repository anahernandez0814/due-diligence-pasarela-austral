"""Pruebas de los subagentes y las skills de revisión (R1, R2, R3, R5, R12; FR-003, FR-004).

Comprueban la configuración versionada de `.claude/agents/` y `.claude/skills/`: que los
revisores son de solo lectura por su rol, que cada skill se ejecuta en un contexto separado
ligada a su subagente, y que el comando que inyecta el contexto es exactamente el único que
la skill pre-aprueba (contracts/revisiones.md).
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
AGENTES = RAIZ / ".claude" / "agents"
SKILLS = RAIZ / ".claude" / "skills"

# (subagente, skill).
REVISIONES = [
    ("revisor-codigo", "revisar-codigo"),
    ("auditor-cumplimiento", "auditar-cumplimiento"),
]

HERRAMIENTAS_DE_LECTURA = {"Read", "Grep", "Glob"}
INYECCION = re.compile(r"!`([^`]+)`")
UNIDAD_ABSOLUTA = re.compile(r"^[A-Za-z]:[\\/]")
CONSTITUCION = ".specify/memory/constitution.md"


def separar(texto: str) -> tuple[dict, str]:
    """`(frontmatter, cuerpo)`: YAML mínimo con escalares y listas, sin dependencias."""
    lineas = texto.splitlines()
    assert lineas and lineas[0] == "---", "falta el frontmatter"
    cierre = lineas.index("---", 1)
    datos: dict = {}
    clave = None
    for linea in lineas[1:cierre]:
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        if linea.startswith((" ", "\t")) and linea.strip().startswith("- ") and clave:
            datos[clave].append(linea.strip()[2:].strip())
        else:
            nombre, _, valor = linea.partition(":")
            clave = nombre.strip()
            valor = valor.strip()
            datos[clave] = [] if valor == "" else valor.strip("\"'")
    return datos, "\n".join(lineas[cierre + 1 :])


def cargar_agente(nombre: str) -> tuple[dict, str]:
    return separar((AGENTES / f"{nombre}.md").read_text(encoding="utf-8"))


def cargar_skill(nombre: str) -> tuple[dict, str]:
    return separar((SKILLS / nombre / "SKILL.md").read_text(encoding="utf-8"))


def comando_inyectado(cuerpo: str) -> str:
    comandos = INYECCION.findall(cuerpo)
    assert len(comandos) == 1, f"debe haber exactamente una inyección, hay {len(comandos)}"
    return comandos[0]


# --- Subagentes ----------------------------------------------------------------------


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_el_subagente_existe_y_se_llama_como_su_archivo(subagente, skill):
    frontmatter, _ = cargar_agente(subagente)
    assert frontmatter["name"] == subagente
    assert frontmatter["description"]


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_tools_es_exactamente_read_grep_glob(subagente, skill):
    frontmatter, _ = cargar_agente(subagente)
    herramientas = [x.strip() for x in frontmatter["tools"].split(",")]
    assert len(herramientas) == len(set(herramientas))
    assert set(herramientas) == HERRAMIENTAS_DE_LECTURA


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_el_subagente_no_declara_otra_forma_de_ganar_herramientas(subagente, skill):
    frontmatter, _ = cargar_agente(subagente)
    assert "omitClaudeMd" not in frontmatter
    assert not {"mcpServers", "hooks", "permissionMode"} & set(frontmatter)


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_el_subagente_solo_reporta_y_termina_con_el_resumen(subagente, skill):
    _, cuerpo = cargar_agente(subagente)
    assert "RESUMEN: bloqueantes=" in cuerpo
    assert "BLOQUEANTE" in cuerpo
    assert "SUGERENCIA" in cuerpo
    assert "no corrige" in cuerpo.lower()


# --- Skills --------------------------------------------------------------------------


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_la_skill_se_ejecuta_en_un_contexto_separado_ligada_a_su_subagente(subagente, skill):
    frontmatter, _ = cargar_skill(skill)
    assert frontmatter["context"] == "fork"
    assert frontmatter["agent"] == subagente
    assert (AGENTES / f"{frontmatter['agent']}.md").is_file()


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_la_skill_declara_la_pista_del_argumento(subagente, skill):
    frontmatter, _ = cargar_skill(skill)
    assert frontmatter["argument-hint"]
    assert "specs/" in frontmatter["argument-hint"]


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_allowed_tools_contiene_solo_el_comando_del_script(subagente, skill):
    frontmatter, cuerpo = cargar_skill(skill)
    permitidas = frontmatter["allowed-tools"]
    assert len(permitidas) == 1
    assert permitidas[0] == f"Bash({comando_inyectado(cuerpo)})"


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_el_comando_inyectado_ejecuta_el_script_de_preparacion(subagente, skill):
    _, cuerpo = cargar_skill(skill)
    comando = comando_inyectado(cuerpo)
    assert comando.startswith("uv run --no-project --python 3.12 --quiet ")
    assert comando.endswith("/.claude/hooks/preparar_revision.py")


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_el_comando_inyectado_no_interpola_el_argumento(subagente, skill):
    _, cuerpo = cargar_skill(skill)
    comando = comando_inyectado(cuerpo)
    assert "$ARGUMENTS" not in comando
    assert "$" not in comando.replace("${CLAUDE_PROJECT_DIR}", "").replace(
        "${CLAUDE_SKILL_DIR}", ""
    )
    # El argumento solo aparece en prosa, fuera de la inyección (R2.2).
    assert "$ARGUMENTS" in INYECCION.sub("", cuerpo)


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_el_comando_inyectado_no_usa_rutas_absolutas(subagente, skill):
    _, cuerpo = cargar_skill(skill)
    for palabra in comando_inyectado(cuerpo).split():
        assert not palabra.startswith("/")
        assert not UNIDAD_ABSOLUTA.match(palabra)
        assert "\\" not in palabra
        assert str(RAIZ).replace("\\", "/") not in palabra.replace("\\", "/")


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_el_cuerpo_de_la_skill_fija_la_marca_el_resumen_y_la_lectura_de_la_constitucion(
    subagente, skill
):
    _, cuerpo = cargar_skill(skill)
    assert "CONTEXTO DE REVISIÓN" in cuerpo
    assert "CONTEXTO INCOMPLETO" in cuerpo
    assert "RESUMEN: bloqueantes=" in cuerpo
    assert "Read" in cuerpo
    assert CONSTITUCION in cuerpo
    for documento in ("spec.md", "plan.md", "tasks.md"):
        assert documento in cuerpo


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_la_skill_trata_los_documentos_del_ticket_como_referencia_y_la_lista_agrupada(
    subagente, skill
):
    _, cuerpo = cargar_skill(skill)
    assert "referencia" in cuerpo
    assert "agrupada por directorio" in cuerpo
    assert "cobertura=incompleta" in cuerpo


# --- Auditor de cumplimiento (US2) --------------------------------------------------

REGLAS = ["I.1", "I.2", "I.3", "I.4", "I.5"]
ESTADOS = ["cumple", "incumple", "no aplica", "no verificada"]


def test_el_auditor_conoce_las_cinco_reglas_del_principio_i():
    _, cuerpo = cargar_agente("auditor-cumplimiento")
    for regla in REGLAS:
        assert regla in cuerpo
    assert "I.6" not in cuerpo


def test_el_auditor_declara_los_cuatro_estados():
    _, cuerpo = cargar_agente("auditor-cumplimiento")
    for estado in ESTADOS:
        assert f"`{estado}`" in cuerpo


def test_el_auditor_exige_razon_en_cada_no_aplica_y_nunca_cumple_sin_evidencia():
    _, cuerpo = cargar_agente("auditor-cumplimiento")
    assert "razón" in cuerpo
    assert "evidencia" in cuerpo
    assert "nunca" in cuerpo.lower()
    assert "no verificada" in cuerpo
    assert "bloqueante" in cuerpo.lower()


def test_el_auditor_define_cuando_aplica_una_regla():
    _, cuerpo = cargar_agente("auditor-cumplimiento")
    assert "la spec del ticket la cita" in cuerpo
    assert "el diff toca código o tests que la implementan o la prueban" in cuerpo
    assert "sin código de producción ni tests de las reglas" in cuerpo.lower()
    # Un cambio que solo borra o debilita el test de una regla sí la toca (hallazgo 1).
    assert "borra o debilita" in cuerpo


def test_el_auditor_pide_la_tabla_de_las_cinco_reglas():
    _, cuerpo = cargar_agente("auditor-cumplimiento")
    assert "| Regla | Estado |" in cuerpo
    assert CONSTITUCION in cuerpo


def test_la_skill_de_auditoria_pone_la_constitucion_como_documento_principal():
    _, cuerpo = cargar_skill("auditar-cumplimiento")
    assert cuerpo.index(CONSTITUCION) < cuerpo.index("spec.md")
    assert "las cinco reglas" in cuerpo


# --- Faltantes y carpeta del ticket (parada B) ----------------------------------------


def test_el_revisor_no_rebaja_a_sugerencia_lo_que_no_puede_ubicar():
    _, cuerpo = cargar_agente("revisor-codigo")
    assert "ponlo como sugerencia" not in cuerpo


def test_el_revisor_ubica_lo_que_falta_en_el_requisito_y_lo_marca_bloqueante():
    _, cuerpo = cargar_agente("revisor-codigo")
    assert "spec.md:línea" in cuerpo
    assert "tasks.md:línea" in cuerpo
    assert "sin implementar" in cuerpo
    assert "sin prueba" in cuerpo
    assert "obligatorio" in cuerpo


def test_el_auditor_tambien_ubica_lo_que_falta_en_el_requisito():
    _, cuerpo = cargar_agente("auditor-cumplimiento")
    assert "spec.md:línea" in cuerpo
    assert "tasks.md:línea" in cuerpo


@pytest.mark.parametrize(("subagente", "skill"), REVISIONES)
def test_la_carpeta_del_ticket_es_la_de_la_linea_ticket_del_contexto(subagente, skill):
    _, cuerpo = cargar_skill(skill)
    assert "la línea `Ticket:` del contexto" in cuerpo
    assert "pista" in cuerpo.lower()
    assert "$ARGUMENTS" in INYECCION.sub("", cuerpo)
    assert "Carpeta del ticket: $ARGUMENTS" not in cuerpo
    # Si $ARGUMENTS indica otra carpeta, se dice y la cobertura es incompleta.
    assert "otra carpeta" in cuerpo
