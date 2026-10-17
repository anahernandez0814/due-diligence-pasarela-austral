"""Pruebas del cargador de datos ficticios (R8) y, más abajo, de los datos reales."""

import json

import pytest

from servidor_mcp import datos
from servidor_mcp.datos import DatosNoDisponibles, cargar


def _escribir(ruta, contenido):
    ruta.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
    return ruta


def _valido(**extra):
    return {
        "ficticio": True,
        "aviso": "Datos ficticios de prueba.",
        "fecha_corte": "2026-09-30",
        **extra,
    }


@pytest.fixture(autouse=True)
def _sin_cache():
    datos.limpiar_cache()
    yield
    datos.limpiar_cache()


# --- cargador ------------------------------------------------------------------------------


def test_cargar_devuelve_el_contenido(tmp_path):
    ruta = _escribir(tmp_path / "x.json", _valido(comercios=[{"identificador": "CO-AA-0001"}]))
    assert cargar(ruta)["comercios"] == [{"identificador": "CO-AA-0001"}]


def test_archivo_ausente(tmp_path):
    with pytest.raises(DatosNoDisponibles) as exc:
        cargar(tmp_path / "no_existe.json")
    assert "no_existe.json" in str(exc.value)


def test_json_corrupto(tmp_path):
    ruta = tmp_path / "roto.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    with pytest.raises(DatosNoDisponibles):
        cargar(ruta)


def test_un_json_que_no_es_un_objeto(tmp_path):
    with pytest.raises(DatosNoDisponibles):
        cargar(_escribir(tmp_path / "lista.json", [1, 2, 3]))


@pytest.mark.parametrize("quitar", ["ficticio", "aviso", "fecha_corte"])
def test_falta_una_marca_obligatoria(tmp_path, quitar):
    contenido = _valido()
    del contenido[quitar]
    with pytest.raises(DatosNoDisponibles) as exc:
        cargar(_escribir(tmp_path / "x.json", contenido))
    assert quitar in str(exc.value)


@pytest.mark.parametrize("valor", [False, "true", 1, None])
def test_ficticio_debe_ser_exactamente_true(tmp_path, valor):
    with pytest.raises(DatosNoDisponibles):
        cargar(_escribir(tmp_path / "x.json", _valido() | {"ficticio": valor}))


@pytest.mark.parametrize("valor", ["", "   ", 5])
def test_el_aviso_debe_ser_un_texto_no_vacio(tmp_path, valor):
    with pytest.raises(DatosNoDisponibles):
        cargar(_escribir(tmp_path / "x.json", _valido() | {"aviso": valor}))


@pytest.mark.parametrize("valor", ["30/09/2026", "2026-9-30", "ayer", 20260930, ""])
def test_fecha_corte_con_formato_aaaa_mm_dd(tmp_path, valor):
    with pytest.raises(DatosNoDisponibles):
        cargar(_escribir(tmp_path / "x.json", _valido() | {"fecha_corte": valor}))


def test_el_cargador_no_imprime_nada(tmp_path, capsys):
    cargar(_escribir(tmp_path / "x.json", _valido()))
    with pytest.raises(DatosNoDisponibles):
        cargar(tmp_path / "no_existe.json")
    salida = capsys.readouterr()
    assert salida.out == ""
    assert salida.err == ""


# --- funciones por frente ------------------------------------------------------------------


def test_las_funciones_leen_el_directorio_de_datos(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "DIRECTORIO_DATOS", tmp_path)
    _escribir(tmp_path / "categorias.json", _valido(categorias=[{"nombre": "x", "nivel": "bajo"}]))
    assert datos.categorias()["categorias"] == [{"nombre": "x", "nivel": "bajo"}]


def test_las_funciones_guardan_el_resultado_en_cache_por_proceso(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "DIRECTORIO_DATOS", tmp_path)
    ruta = _escribir(tmp_path / "noticias.json", _valido(noticias=[]))
    primero = datos.noticias()
    ruta.unlink()
    assert datos.noticias() is primero
    datos.limpiar_cache()
    with pytest.raises(DatosNoDisponibles):
        datos.noticias()


def test_un_archivo_ausente_no_queda_en_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "DIRECTORIO_DATOS", tmp_path)
    with pytest.raises(DatosNoDisponibles):
        datos.listas()
    _escribir(tmp_path / "listas_restrictivas.json", _valido(listas=[]))
    assert datos.listas()["listas"] == []


def test_registros_devuelve_las_dos_fuentes_registrales(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "DIRECTORIO_DATOS", tmp_path)
    _escribir(tmp_path / "registro_rmf_sur.json", _valido(fuente="A", comercios=[]))
    _escribir(tmp_path / "registro_rufe.json", _valido(fuente="B", comercios=[]))
    assert [r["fuente"] for r in datos.registros()] == ["A", "B"]
