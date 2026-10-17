"""Pruebas del cargador de datos ficticios (R8) y, más abajo, de los datos reales."""

import json
import re

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


# --- datos reales (FR-013, FR-014, data-model «Reglas de validación») -------------------------

ARCHIVOS = [
    "registro_rmf_sur.json",
    "registro_rufe.json",
    "listas_restrictivas.json",
    "noticias.json",
    "categorias.json",
]
ALTO_RIESGO = {
    "apuestas",
    "criptoactivos",
    "suplementos dietarios",
    "venta de medicamentos",
}


def _claves_con_valor(valor, nombre):
    """Los valores de todas las claves `nombre`, a cualquier profundidad."""
    if isinstance(valor, dict):
        for clave, v in valor.items():
            if clave == nombre:
                yield v
            yield from _claves_con_valor(v, nombre)
    elif isinstance(valor, list):
        for v in valor:
            yield from _claves_con_valor(v, nombre)


def _real(nombre):
    return cargar(datos.DIRECTORIO_DATOS / nombre)


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_cada_archivo_es_ficticio_con_aviso_y_fecha_de_corte(nombre):
    contenido = _real(nombre)
    assert contenido["ficticio"] is True
    assert "ficticio" in contenido["aviso"].lower()
    assert contenido["fecha_corte"]


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_ningun_valor_tiene_seis_o_mas_digitos_seguidos(nombre):
    texto = (datos.DIRECTORIO_DATOS / nombre).read_text(encoding="utf-8")
    assert not re.search(r"\d{6,}", texto)


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_las_url_son_de_dominio_example(nombre):
    texto = (datos.DIRECTORIO_DATOS / nombre).read_text(encoding="utf-8")
    for host in re.findall(r"https?://([^/\s\"']+)", texto):
        assert host.endswith(".example"), host


def test_los_identificadores_tienen_el_formato_propio():
    for nombre in ARCHIVOS:
        for identificador in _claves_con_valor(_real(nombre), "identificador"):
            assert re.fullmatch(r"CO-[A-Z]{2}-\d{4}|PE-\d{4}", identificador), identificador


def test_los_comercios_de_las_fuentes_registrales_tienen_id_de_comercio():
    for nombre in ("registro_rmf_sur.json", "registro_rufe.json"):
        comercios = _real(nombre)["comercios"]
        assert comercios
        for c in comercios:
            assert re.fullmatch(r"CO-[A-Z]{2}-\d{4}", c["identificador"])
            assert re.fullmatch(r"PE-\d{4}", c["representante_legal"]["identificador"])
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["fecha_constitucion"])
            assert c["estado"] in {"activo", "suspendido", "cancelado"}
            assert "categoria" not in c  # la categoría la aporta el analista


def test_las_fuentes_registrales_tienen_nombre_de_fuente_distinto():
    fuentes = [r["fuente"] for r in datos.registros()]
    assert len(set(fuentes)) == 2
    assert all("Ficticio" in f for f in fuentes)


def test_alto_riesgo_es_exactamente_el_del_enunciado():
    categorias = _real("categorias.json")["categorias"]
    assert len(categorias) == 10
    altas = {c["nombre"] for c in categorias if c["nivel"] == "alto"}
    assert altas == ALTO_RIESGO
    assert {c["nivel"] for c in categorias} == {"alto", "medio", "bajo"}
    assert len({c["nombre"] for c in categorias}) == 10
