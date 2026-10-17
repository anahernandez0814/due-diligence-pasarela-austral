"""Pruebas de registrar_informe y escalar_a_cumplimiento (FR-008, FR-009, R6, R11).

Todas fijan `PASARELA_RESULTADOS_DIR` en `tmp_path`: ninguna escribe en `resultados/`.
"""

import json
import os
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from servidor_mcp import decisiones
from servidor_mcp.decisiones import (
    carpeta_resultados,
    escalar_a_cumplimiento,
    registrar_informe,
)

FUENTE_INFORMES = "Registro local de informes (ficticio)"
FUENTE_ESCALAMIENTOS = "Registro local de escalamientos (ficticio)"
VARIABLE = "PASARELA_RESULTADOS_DIR"


@pytest.fixture(autouse=True)
def _carpeta_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv(VARIABLE, str(tmp_path / "resultados"))
    monkeypatch.setattr(decisiones, "_ahora", lambda: datetime(2026, 10, 17, 12, 30, tzinfo=UTC))
    return tmp_path / "resultados"


@pytest.fixture
def carpeta(_carpeta_temporal):
    return _carpeta_temporal


def _hallazgos():
    return {
        "registro": {
            "contenido": "Una coincidencia: Tienda Verde SAS.",
            "fuente": "Registro Mercantil Ficticio del Sur",
        },
        "riesgo": {
            "contenido": "Categoría suplementos dietarios: nivel alto.",
            "fuente": "Catálogo Ficticio de Categorías de Riesgo",
        },
    }


def _informe(**cambios):
    base = {
        "comercio": {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS"},
        "recomendacion": "No habilitar de forma automática: decide un oficial de cumplimiento.",
        "hallazgos": _hallazgos(),
        "cobertura": "Cubiertos: registro, listas, noticias y riesgo. Sin cubrir: ninguno.",
    }
    return base | cambios


def _escalamiento(**cambios):
    base = {
        "comercio": {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS"},
        "hallazgos": _hallazgos(),
        "cobertura": "Cubiertos: registro, listas, noticias y riesgo. Sin cubrir: ninguno.",
        "causa_escalamiento": "Categoría de alto riesgo: suplementos dietarios.",
        "accion_recomendada": "Decisión del oficial de cumplimiento; no habilitar automáticamente.",
    }
    return base | cambios


def _error(resultado):
    assert resultado.is_error is True
    return resultado.structured_content


def _archivos(carpeta, subcarpeta):
    destino = carpeta / subcarpeta
    return sorted(destino.iterdir()) if destino.exists() else []


# --- registrar_informe ---------------------------------------------------------------------


def test_un_informe_completo_se_guarda_y_devuelve_un_hecho_con_el_id(carpeta):
    resultado = registrar_informe(**_informe())
    assert resultado.is_error is False
    cuerpo = resultado.structured_content
    assert cuerpo["resultado"] == "informe_registrado"
    (hecho,) = cuerpo["hechos"]
    identificador = hecho["contenido"]["id"]
    assert re.fullmatch(r"INF-[0-9a-f]{8}", identificador)
    assert list(hecho["contenido"]) == ["id"]
    assert hecho["metadatos"] == {"fuente": FUENTE_INFORMES, "fecha": "2026-10-17"}
    assert cuerpo["metadatos"] == {"fuentes": [FUENTE_INFORMES], "fecha": "2026-10-17"}
    assert "contenido" not in cuerpo  # ningún contenido fuera del hecho
    assert [a.name for a in _archivos(carpeta, "informes")] == [f"{identificador}.json"]


def test_el_archivo_del_informe_conserva_lo_recibido(carpeta):
    resultado = registrar_informe(**_informe())
    identificador = resultado.structured_content["hechos"][0]["contenido"]["id"]
    guardado = json.loads((carpeta / "informes" / f"{identificador}.json").read_text("utf-8"))
    entrada = _informe()
    assert guardado["id"] == identificador
    assert guardado["registrado_en"] == "2026-10-17T12:30:00+00:00"
    assert guardado["comercio"] == entrada["comercio"]
    assert guardado["recomendacion"] == entrada["recomendacion"]
    assert guardado["hallazgos"] == entrada["hallazgos"]
    assert guardado["cobertura"] == entrada["cobertura"]


def test_dos_informes_del_mismo_comercio_se_conservan_con_ids_distintos(carpeta):
    a = registrar_informe(**_informe()).structured_content["hechos"][0]["contenido"]["id"]
    b = registrar_informe(**_informe()).structured_content["hechos"][0]["contenido"]["id"]
    assert a != b
    assert len(_archivos(carpeta, "informes")) == 2


def test_la_cobertura_puede_ser_una_lista():
    cobertura = ["registro", "listas", "riesgo"]
    assert registrar_informe(**_informe(cobertura=cobertura)).is_error is False


def test_no_valida_reglas_de_negocio(carpeta):
    # Una recomendación de habilitar para una categoría alta se guarda tal cual: la garantía de
    # esa regla es del hook del SDK (ticket #7), no del servidor.
    resultado = registrar_informe(**_informe(recomendacion="Habilitar automáticamente."))
    assert resultado.is_error is False


@pytest.mark.parametrize("campo", ["comercio", "recomendacion", "hallazgos", "cobertura"])
def test_a_registrar_informe_le_falta_un_campo(carpeta, campo):
    entrada = _informe()
    del entrada[campo]
    cuerpo = _error(registrar_informe(**entrada))
    assert cuerpo["tipo"] == "campos_obligatorios_ausentes"
    assert cuerpo["reintentable"] is False
    assert cuerpo["campos_faltantes"] == [campo]
    assert campo in cuerpo["mensaje"]
    assert not carpeta.exists()  # no se escribe nada


def test_registrar_informe_nombra_todos_los_campos_que_faltan():
    cuerpo = _error(registrar_informe())
    assert cuerpo["tipo"] == "campos_obligatorios_ausentes"
    assert cuerpo["campos_faltantes"] == ["comercio", "recomendacion", "hallazgos", "cobertura"]


@pytest.mark.parametrize("vacio", ["", "   ", {}, [], None])
def test_un_campo_presente_pero_vacio_cuenta_como_faltante(vacio):
    cuerpo = _error(registrar_informe(**_informe(cobertura=vacio)))
    assert cuerpo["campos_faltantes"] == ["cobertura"]


def test_un_hallazgo_sin_fuente_es_un_campo_faltante():
    hallazgos = _hallazgos()
    del hallazgos["riesgo"]["fuente"]
    cuerpo = _error(registrar_informe(**_informe(hallazgos=hallazgos)))
    assert cuerpo["tipo"] == "campos_obligatorios_ausentes"
    assert cuerpo["campos_faltantes"] == ["hallazgos.riesgo.fuente"]


def test_un_hallazgo_sin_contenido_es_un_campo_faltante():
    hallazgos = _hallazgos()
    hallazgos["registro"]["contenido"] = "  "
    cuerpo = _error(registrar_informe(**_informe(hallazgos=hallazgos)))
    assert cuerpo["campos_faltantes"] == ["hallazgos.registro.contenido"]


def test_el_comercio_necesita_identificador_y_nombre():
    cuerpo = _error(registrar_informe(**_informe(comercio={"nombre": "Tienda Verde SAS"})))
    assert cuerpo["campos_faltantes"] == ["comercio.identificador"]
    cuerpo = _error(registrar_informe(**_informe(comercio={"identificador": "CO-TV-0001"})))
    assert cuerpo["campos_faltantes"] == ["comercio.nombre"]


@pytest.mark.parametrize(
    "cambio",
    [
        {"comercio": 5},
        {"comercio": "Tienda Verde SAS"},
        {"recomendacion": 5},
        {"hallazgos": ["registro"]},
        {"cobertura": 5},
        {"hallazgos": {"registro": "texto"}},
    ],
)
def test_un_tipo_incorrecto_da_entrada_invalida(carpeta, cambio):
    cuerpo = _error(registrar_informe(**_informe(**cambio)))
    assert cuerpo["tipo"] == "entrada_invalida"
    assert cuerpo["reintentable"] is False
    assert not carpeta.exists()


# --- escalar_a_cumplimiento ----------------------------------------------------------------


def test_un_escalamiento_completo_se_guarda_y_devuelve_un_hecho_con_el_id(carpeta):
    resultado = escalar_a_cumplimiento(**_escalamiento())
    assert resultado.is_error is False
    cuerpo = resultado.structured_content
    assert cuerpo["resultado"] == "caso_escalado"
    (hecho,) = cuerpo["hechos"]
    identificador = hecho["contenido"]["id"]
    assert re.fullmatch(r"ESC-[0-9a-f]{8}", identificador)
    assert list(hecho["contenido"]) == ["id"]
    assert hecho["metadatos"] == {"fuente": FUENTE_ESCALAMIENTOS, "fecha": "2026-10-17"}
    assert cuerpo["metadatos"] == {"fuentes": [FUENTE_ESCALAMIENTOS], "fecha": "2026-10-17"}
    assert "contenido" not in cuerpo
    assert [a.name for a in _archivos(carpeta, "escalamientos")] == [f"{identificador}.json"]


def test_el_archivo_del_escalamiento_conserva_los_cinco_campos(carpeta):
    resultado = escalar_a_cumplimiento(**_escalamiento())
    identificador = resultado.structured_content["hechos"][0]["contenido"]["id"]
    guardado = json.loads((carpeta / "escalamientos" / f"{identificador}.json").read_text("utf-8"))
    entrada = _escalamiento()
    for campo in (
        "comercio",
        "hallazgos",
        "cobertura",
        "causa_escalamiento",
        "accion_recomendada",
    ):
        assert guardado[campo] == entrada[campo]
    assert guardado["id"] == identificador


@pytest.mark.parametrize(
    "campo",
    ["comercio", "hallazgos", "cobertura", "causa_escalamiento", "accion_recomendada"],
)
def test_a_escalar_le_falta_un_campo(carpeta, campo):
    entrada = _escalamiento()
    del entrada[campo]
    cuerpo = _error(escalar_a_cumplimiento(**entrada))
    assert cuerpo["tipo"] == "campos_obligatorios_ausentes"
    assert cuerpo["reintentable"] is False
    assert cuerpo["campos_faltantes"] == [campo]
    assert not carpeta.exists()


def test_escalar_nombra_los_cinco_campos_cuando_faltan_todos():
    cuerpo = _error(escalar_a_cumplimiento())
    assert cuerpo["campos_faltantes"] == [
        "comercio",
        "hallazgos",
        "cobertura",
        "causa_escalamiento",
        "accion_recomendada",
    ]


def test_escalar_con_un_hallazgo_sin_fuente_es_un_campo_faltante():
    hallazgos = _hallazgos()
    del hallazgos["registro"]["fuente"]
    cuerpo = _error(escalar_a_cumplimiento(**_escalamiento(hallazgos=hallazgos)))
    assert cuerpo["campos_faltantes"] == ["hallazgos.registro.fuente"]


def test_escalar_con_tipo_incorrecto_da_entrada_invalida():
    assert _error(escalar_a_cumplimiento(**_escalamiento(causa_escalamiento=5)))["tipo"] == (
        "entrada_invalida"
    )


# --- carpeta y almacenamiento --------------------------------------------------------------


def test_la_carpeta_se_crea_si_no_existe(tmp_path, monkeypatch):
    nueva = tmp_path / "no" / "existe" / "todavia"
    monkeypatch.setenv(VARIABLE, str(nueva))
    assert not nueva.exists()
    assert registrar_informe(**_informe()).is_error is False
    assert len(_archivos(nueva, "informes")) == 1


def test_la_carpeta_sale_de_la_variable_de_entorno(tmp_path, monkeypatch):
    destino = tmp_path / "otra"
    monkeypatch.setenv(VARIABLE, str(destino))
    assert carpeta_resultados() == destino


def test_sin_la_variable_la_ruta_por_defecto_es_resultados_en_la_raiz(monkeypatch):
    monkeypatch.delenv(VARIABLE)
    esperada = Path(decisiones.__file__).resolve().parents[2] / "resultados"
    assert carpeta_resultados() == esperada
    assert esperada.name == "resultados"
    assert ".claude" not in esperada.parts  # fuera de la configuración protegida


def test_una_variable_vacia_usa_la_ruta_por_defecto(monkeypatch):
    monkeypatch.setenv(VARIABLE, "  ")
    assert carpeta_resultados().name == "resultados"


def test_si_no_se_puede_escribir_da_error_de_almacenamiento(tmp_path, monkeypatch):
    ocupada = tmp_path / "ocupada"
    ocupada.write_text("un archivo ocupa el lugar de la carpeta", encoding="utf-8")
    monkeypatch.setenv(VARIABLE, str(ocupada))
    for resultado in (registrar_informe(**_informe()), escalar_a_cumplimiento(**_escalamiento())):
        cuerpo = _error(resultado)
        assert cuerpo["tipo"] == "error_de_almacenamiento"
        assert cuerpo["reintentable"] is False
        assert str(ocupada) not in cuerpo["mensaje"]


def test_no_queda_ningun_archivo_temporal(carpeta):
    registrar_informe(**_informe())
    escalar_a_cumplimiento(**_escalamiento())
    nombres = [a.name for a in carpeta.rglob("*") if a.is_file()]
    assert len(nombres) == 2
    assert all(n.endswith(".json") for n in nombres)


def test_si_falla_el_reemplazo_no_queda_un_archivo_a_medias(carpeta, monkeypatch):
    def falla(*_args, **_kwargs):
        raise OSError("fallo simulado")

    monkeypatch.setattr(os, "replace", falla)
    cuerpo = _error(registrar_informe(**_informe()))
    assert cuerpo["tipo"] == "error_de_almacenamiento"
    assert [a for a in carpeta.rglob("*") if a.is_file()] == []


# --- fecha de registro en hora local -------------------------------------------------------


def test_la_hora_por_defecto_es_la_local_con_su_desfase(monkeypatch):
    monkeypatch.undo()  # quita el reloj fijo del fixture
    antes = datetime.now().astimezone()
    ahora = decisiones._ahora()
    despues = datetime.now().astimezone()
    assert ahora.tzinfo is not None
    assert ahora.utcoffset() == antes.utcoffset() == despues.utcoffset()
    assert antes <= ahora <= despues


def test_la_fecha_de_registro_es_la_de_la_hora_local_y_no_la_utc(monkeypatch):
    # 23:30 en UTC-5 ya es el día siguiente en UTC; la fecha de registro es la local.
    local = datetime(2026, 10, 17, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    monkeypatch.setattr(decisiones, "_ahora", lambda: local)
    cuerpo = registrar_informe(**_informe()).structured_content
    assert cuerpo["hechos"][0]["metadatos"]["fecha"] == "2026-10-17"
    assert cuerpo["metadatos"]["fecha"] == "2026-10-17"
    identificador = cuerpo["hechos"][0]["contenido"]["id"]
    carpeta = decisiones.carpeta_resultados()
    guardado = json.loads((carpeta / "informes" / f"{identificador}.json").read_text("utf-8"))
    assert guardado["registrado_en"] == "2026-10-17T23:30:00-05:00"
