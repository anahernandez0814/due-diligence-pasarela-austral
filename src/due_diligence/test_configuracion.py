"""Tests de las opciones del SDK, las herramientas por agente y la carga del entorno
(R2, R3, R8, R9; FR-002 a FR-004; SC-002).

Ningún test llama al modelo ni carga el archivo de entorno real: `load_dotenv` se parchea.
"""

import subprocess
import sys

import pytest

from due_diligence import configuracion
from due_diligence.frentes import (
    FRENTES,
    HERRAMIENTAS_DECISION,
    HERRAMIENTAS_FUENTES,
    HERRAMIENTAS_PASARELA,
    Frente,
    nombre_completo,
)

PASARELA = "mcp__pasarela__"
DELEGAR = "mcp__delegacion__delegar_frente"
SEIS = {PASARELA + h for h in HERRAMIENTAS_PASARELA}


def _servidor_delegacion():
    return {"type": "sdk", "name": "delegacion", "instance": object()}


def _opciones_coordinador(**kwargs):
    return configuracion.opciones_coordinador(_servidor_delegacion(), "instrucciones", **kwargs)


def _opciones_subagente(frente, **kwargs):
    return configuracion.opciones_subagente(frente, "instrucciones", **kwargs)


def _todas_las_opciones():
    return [_opciones_coordinador(), *(_opciones_subagente(f) for f in Frente)]


# ---------------------------------------------------------------- tabla de frentes


def test_la_tabla_de_frentes_tiene_la_herramienta_de_cada_uno():
    assert {f: d.herramienta for f, d in FRENTES.items()} == {
        Frente.REGISTRO: "consultar_registro_mercantil",
        Frente.LISTAS: "consultar_listas_restrictivas",
        Frente.NOTICIAS: "buscar_noticias",
        Frente.CATEGORIA: "consultar_riesgo_categoria",
    }
    assert FRENTES[Frente.LISTAS].dependencia is Frente.REGISTRO
    assert all(FRENTES[f].dependencia is None for f in Frente if f is not Frente.LISTAS)
    assert (
        FRENTES[Frente.REGISTRO].herramienta_completa == PASARELA + "consultar_registro_mercantil"
    )


def test_son_exactamente_seis_herramientas_cuatro_de_fuentes_y_dos_de_decision():
    assert len(HERRAMIENTAS_PASARELA) == 6
    assert len(HERRAMIENTAS_FUENTES) == 4 and len(HERRAMIENTAS_DECISION) == 2
    assert nombre_completo("x") == "mcp__pasarela__x"


# ---------------------------------------------------------------- opciones del SDK (R2)


def test_toda_opcion_aisla_el_entorno_de_desarrollo():
    for opciones in _todas_las_opciones():
        assert opciones.setting_sources == []
        assert opciones.tools == []
        assert opciones.strict_mcp_config is True
        assert opciones.cwd == str(configuracion.RAIZ)


def test_la_raiz_es_la_del_repositorio():
    assert (configuracion.RAIZ / "pyproject.toml").is_file()
    assert (configuracion.RAIZ / "src" / "due_diligence").is_dir()


def test_max_turns_es_una_constante_de_seguridad_en_todas_las_opciones():
    assert isinstance(configuracion.MAX_TURNOS_SEGURIDAD, int)
    for opciones in _todas_las_opciones():
        assert opciones.max_turns == configuracion.MAX_TURNOS_SEGURIDAD


def test_los_hooks_se_reparten_a_todas_las_opciones():
    hooks = {"PreToolUse": []}
    for opciones in (
        _opciones_coordinador(hooks=hooks),
        *(_opciones_subagente(f, hooks=hooks) for f in Frente),
    ):
        assert opciones.hooks is hooks


# ---------------------------------------------------------------- herramientas por agente (R3)


def test_el_coordinador_solo_delega_y_tiene_los_canales_de_decision():
    opciones = _opciones_coordinador()
    assert set(opciones.allowed_tools) == {
        DELEGAR,
        PASARELA + "registrar_informe",
        PASARELA + "escalar_a_cumplimiento",
    }
    assert set(opciones.disallowed_tools) == {PASARELA + h for h in HERRAMIENTAS_FUENTES}


@pytest.mark.parametrize("frente", list(Frente))
def test_cada_subagente_solo_tiene_la_herramienta_de_su_frente(frente):
    opciones = _opciones_subagente(frente)
    assert opciones.allowed_tools == [FRENTES[frente].herramienta_completa]
    assert set(opciones.disallowed_tools) == SEIS - {FRENTES[frente].herramienta_completa}
    assert len(opciones.disallowed_tools) == 5


def test_permitidas_mas_prohibidas_de_la_pasarela_son_siempre_las_seis():
    """SC-002: ninguna herramienta de la pasarela queda ni libre ni olvidada."""
    for opciones in _todas_las_opciones():
        permitidas = {t for t in opciones.allowed_tools if t.startswith(PASARELA)}
        prohibidas = {t for t in opciones.disallowed_tools if t.startswith(PASARELA)}
        assert permitidas | prohibidas == SEIS
        assert permitidas & prohibidas == set()


def test_ningun_agente_lleva_herramientas_integradas():
    integradas = {"Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task", "Agent", "WebFetch"}
    for opciones in _todas_las_opciones():
        assert not integradas & set(opciones.allowed_tools)
        assert opciones.tools == []


def test_los_subagentes_no_pueden_delegar_ni_decidir():
    for frente in Frente:
        opciones = _opciones_subagente(frente)
        assert DELEGAR not in opciones.allowed_tools
        assert PASARELA + "registrar_informe" not in opciones.allowed_tools
        assert PASARELA + "escalar_a_cumplimiento" not in opciones.allowed_tools


def test_el_subagente_no_ve_el_servidor_de_delegacion():
    for frente in Frente:
        assert set(_opciones_subagente(frente).mcp_servers) == {"pasarela"}
    assert set(_opciones_coordinador().mcp_servers) == {"pasarela", "delegacion"}


# ---------------------------------------------------------------- servidor pasarela


def test_el_servidor_pasarela_se_declara_con_el_interprete_actual():
    servidor = configuracion.servidor_pasarela({})
    assert servidor["type"] == "stdio"
    assert servidor["command"] == sys.executable
    assert servidor["args"] == ["-m", "servidor_mcp"]


def test_el_servidor_reenvia_solo_las_variables_pasarela_presentes():
    entorno = {
        "PASARELA_FALLA_NOTICIAS": "1",
        "PASARELA_RESULTADOS_DIR": "carpeta",
        "OTRA_VARIABLE": "no se reenvia",
    }
    assert configuracion.servidor_pasarela(entorno)["env"] == {
        "PASARELA_FALLA_NOTICIAS": "1",
        "PASARELA_RESULTADOS_DIR": "carpeta",
    }
    assert (
        "env" not in configuracion.servidor_pasarela({})
        or configuracion.servidor_pasarela({})["env"] == {}
    )


# ---------------------------------------------------------------- modelos (R9)


def test_el_modelo_por_defecto_es_opus_para_el_coordinador_y_los_cuatro_subagentes():
    # Decisión de la analista en el #7: Opus 5.5 en el código, sin depender del archivo de entorno.
    assert configuracion.MODELO_POR_DEFECTO == "claude-opus-5-5"
    assert configuracion.modelo_coordinador({}) == "claude-opus-5-5"
    assert configuracion.modelo_subagentes({}) == "claude-opus-5-5"


def test_las_variables_permiten_volver_a_sonnet():
    entorno = {
        "PASARELA_MODELO_COORDINADOR": "claude-sonnet-5-5",
        "PASARELA_MODELO_SUBAGENTES": "claude-sonnet-5-5",
    }
    assert configuracion.modelo_coordinador(entorno) == "claude-sonnet-5-5"
    assert configuracion.modelo_subagentes(entorno) == "claude-sonnet-5-5"


def test_cada_modelo_se_sustituye_por_separado_con_su_variable(monkeypatch):
    monkeypatch.setenv("PASARELA_MODELO_COORDINADOR", "modelo-del-coordinador")
    monkeypatch.delenv("PASARELA_MODELO_SUBAGENTES", raising=False)
    assert _opciones_coordinador().model == "modelo-del-coordinador"
    assert all(_opciones_subagente(f).model == "claude-opus-5-5" for f in Frente)

    monkeypatch.delenv("PASARELA_MODELO_COORDINADOR")
    monkeypatch.setenv("PASARELA_MODELO_SUBAGENTES", "modelo-de-subagentes")
    assert _opciones_coordinador().model == "claude-opus-5-5"
    assert all(_opciones_subagente(f).model == "modelo-de-subagentes" for f in Frente)


def test_un_valor_vacio_usa_el_modelo_por_defecto():
    assert (
        configuracion.modelo_coordinador({"PASARELA_MODELO_COORDINADOR": "  "}) == "claude-opus-5-5"
    )


# ---------------------------------------------------------------- entorno (R8)


def test_cargar_entorno_llama_a_load_dotenv_sin_sobrescribir(monkeypatch):
    """Se parchea `load_dotenv`: ningún test ejecuta la carga real ni lee el archivo de entorno."""
    llamadas = []

    def falso(*args, **kwargs):
        llamadas.append((args, kwargs))
        return True

    monkeypatch.setattr(configuracion, "load_dotenv", falso)
    assert configuracion.cargar_entorno() is True
    assert llamadas == [((), {"override": False})]


def test_importar_el_paquete_no_carga_el_entorno():
    """En un proceso aparte, `load_dotenv` falla si algo la llama al importar."""
    codigo = (
        "import dotenv\n"
        "def prohibido(*a, **k):\n"
        "    raise SystemExit('se cargó el entorno al importar')\n"
        "dotenv.load_dotenv = prohibido\n"
        "import due_diligence, due_diligence.configuracion\n"
        "print('sin carga')\n"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, timeout=60, check=False
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "sin carga" in resultado.stdout


def test_el_aviso_de_conectores_se_descarta_y_los_errores_reales_pasan(capsys):
    configuracion.filtrar_stderr("Warning: claude.ai connectors are disabled in this session")
    configuracion.filtrar_stderr("Error: no se pudo iniciar el servidor")
    capturado = capsys.readouterr()
    assert "connectors" not in capturado.err
    assert "no se pudo iniciar el servidor" in capturado.err


def test_todas_las_opciones_usan_el_filtro_de_stderr():
    opciones = configuracion.opciones_base(
        modelo="m", system_prompt="s", permitidas=[], prohibidas=[], mcp_servers={}
    )
    assert opciones.stderr is configuracion.filtrar_stderr


# ------------------------------------------------ límite de devoluciones y demo (#7, R3, R11)


def test_el_limite_de_devoluciones_del_cierre_es_tres_y_menor_que_el_de_turnos():
    assert configuracion.MAX_CIERRES_IMPEDIDOS == 3
    assert configuracion.MAX_CIERRES_IMPEDIDOS < configuracion.MAX_TURNOS_SEGURIDAD


@pytest.mark.parametrize("valor", ["0", "true", "", " ", "11", "si", "yes"])
def test_el_modo_demostracion_solo_se_activa_con_el_valor_exacto_uno(valor):
    entorno = {configuracion.VARIABLE_MODO_DEMO: valor}
    assert configuracion.modo_demostracion(entorno) is False


def test_el_modo_demostracion_con_uno_se_activa_y_sin_variable_no():
    assert configuracion.modo_demostracion({configuracion.VARIABLE_MODO_DEMO: "1"}) is True
    assert configuracion.modo_demostracion({}) is False


def test_el_modo_demostracion_lee_el_entorno_dado_y_con_none_lee_os_environ(monkeypatch):
    # Con un entorno dado no mira `os.environ`; con `None` sí (el patrón de `_modelo`, R11).
    monkeypatch.setenv(configuracion.VARIABLE_MODO_DEMO, "1")
    assert configuracion.modo_demostracion({}) is False
    assert configuracion.modo_demostracion(None) is True
    assert configuracion.modo_demostracion() is True
    monkeypatch.delenv(configuracion.VARIABLE_MODO_DEMO)
    assert configuracion.modo_demostracion(None) is False


def test_la_variable_de_demostracion_no_se_reenvia_al_servidor():
    assert configuracion.VARIABLE_MODO_DEMO == "PASARELA_MODO_DEMO_HOOKS"
    assert configuracion.VARIABLE_MODO_DEMO not in configuracion.VARIABLES_PASARELA
    entorno = {configuracion.VARIABLE_MODO_DEMO: "1"}
    assert "env" not in configuracion.servidor_pasarela(entorno)
