"""Los datos reproducen cada uno de los siete casos obligatorios (a)–(g).

Aquí solo se prueba que **los datos** reproducen el caso, leyendo `datos.py` y usando
`normalizar`. Los casos completos, con el coordinador y los hooks, son del ticket #12.
Mapa caso→dato: `specs/005-servidor-mcp-pasarela/data-model.md`.
"""

from servidor_mcp import datos
from servidor_mcp.normalizar import contiene, contiene_en_registro, igual


def _comercios():
    """identificador → lista de (fuente, comercio), en el orden de las fuentes registrales."""
    por_id: dict[str, list[tuple[str, dict]]] = {}
    for fuente in datos.registros():
        for comercio in fuente["comercios"]:
            por_id.setdefault(comercio["identificador"], []).append((fuente["fuente"], comercio))
    return por_id


def _entradas_de_listas():
    return [e for lista in datos.listas()["listas"] for e in lista["entradas"]]


def _entidades_en_listas(identificador, nombre):
    return [
        e
        for e in _entradas_de_listas()
        if e["identificador"] == identificador or igual(e["nombre"], nombre)
    ]


def _noticias_que_mencionan(identificador, nombre):
    return [
        n
        for n in datos.noticias()["noticias"]
        for m in n["menciona"]
        if m["identificador"] == identificador or igual(m["nombre"], nombre)
    ]


def _nivel(categoria):
    niveles = [
        c["nivel"] for c in datos.categorias()["categorias"] if igual(c["nombre"], categoria)
    ]
    assert len(niveles) == 1, categoria
    return niveles[0]


def _esta_en_las_dos_fuentes(identificador):
    registros = _comercios()[identificador]
    assert len(registros) == len(datos.registros()) == 2
    return registros


def test_datos_del_caso_a_alto_riesgo_a_un_oficial():
    (_, comercio), _ = _esta_en_las_dos_fuentes("CO-TV-0001")
    assert comercio["nombre"] == "Tienda Verde SAS"
    assert not _entidades_en_listas("CO-TV-0001", comercio["nombre"])
    assert not _noticias_que_mencionan("CO-TV-0001", comercio["nombre"])
    # La categoría la nombra el analista; el registro no la devuelve.
    assert "categoria" not in comercio
    assert _nivel("suplementos dietarios") == "alto"


def test_datos_del_caso_b_bajo_riesgo_sin_hallazgos():
    (_, comercio), _ = _esta_en_las_dos_fuentes("CO-TA-0002")
    assert not _entidades_en_listas("CO-TA-0002", comercio["nombre"])
    assert not _noticias_que_mencionan("CO-TA-0002", comercio["nombre"])
    assert _nivel("ropa y accesorios") == "bajo"


def test_datos_del_caso_c_representante_legal_en_listas():
    registros = _esta_en_las_dos_fuentes("CO-PL-0003")
    representantes = {c["representante_legal"]["identificador"] for _, c in registros}
    assert representantes == {"PE-0003"}  # el representante es el de un comercio del registro
    nombre = registros[0][1]["representante_legal"]["nombre"]
    en_listas = _entidades_en_listas("PE-0003", nombre)
    assert [e["tipo"] for e in en_listas] == ["persona"]
    # El comercio por sí solo no figura en las listas.
    assert not _entidades_en_listas("CO-PL-0003", registros[0][1]["nombre"])


def test_datos_del_caso_d_dos_comercios_con_nombres_casi_identicos():
    coinciden = {
        identificador
        for identificador, registros in _comercios().items()
        if contiene("almacén mirador", registros[0][1]["nombre"])
    }
    assert coinciden == {"CO-AM-0004", "CO-AM-0005"}


def test_datos_del_caso_e_el_nombre_ambiguo_es_el_de_d_sin_datos_nuevos():
    # Sin datos nuevos: el nombre ambiguo de (d) coincide con más de un comercio del registro,
    # que es la ambigüedad sobre la que actúa el hook de listas del ticket #7. Se comprueba solo
    # con datos.py y normalizar.contiene, sin llamar a ninguna herramienta.
    identificadores = {
        c["identificador"]
        for fuente in datos.registros()
        for c in fuente["comercios"]
        if contiene("almacén mirador", c["nombre"])
    }
    assert len(identificadores) > 1


def test_datos_del_caso_f_cualquier_comercio_sirve_para_la_caida_de_noticias():
    # Sin datos nuevos: la caída se activa con una variable de entorno, no con un dato. Basta con
    # que el registro tenga comercios y que las noticias existan para que la variable las oculte.
    assert _comercios()
    assert datos.noticias()["noticias"]
    texto = " ".join(
        (datos.DIRECTORIO_DATOS / n).read_text(encoding="utf-8")
        for n in ("noticias.json", "registro_rmf_sur.json", "registro_rufe.json")
    )
    assert "PASARELA_FALLA_NOTICIAS" not in texto


def test_datos_del_caso_g_dos_fuentes_con_fechas_de_constitucion_distintas():
    (fuente_a, a), (fuente_b, b) = _esta_en_las_dos_fuentes("CO-RF-0006")
    assert fuente_a != fuente_b
    assert (a["fecha_constitucion"], b["fecha_constitucion"]) == ("2016-03-14", "2017-09-02")
    # Solo difiere la fecha: el resto de los datos coincide.
    assert {k: v for k, v in a.items() if k != "fecha_constitucion"} == {
        k: v for k, v in b.items() if k != "fecha_constitucion"
    }


def test_datos_adicionales_mencion_en_noticias_sin_estar_en_listas():
    # US2, escenario 3: CO-AM-0005 aparece en noticias y no en listas.
    nombre = _comercios()["CO-AM-0005"][0][1]["nombre"]
    assert _noticias_que_mencionan("CO-AM-0005", nombre)
    assert not _entidades_en_listas("CO-AM-0005", nombre)


def test_datos_del_caso_d_con_el_mensaje_natural_del_analista():
    # «Almacén Mirador SAS» (con su forma jurídica) también coincide con los dos comercios.
    for mensaje in ("Almacén Mirador SAS", "Almacén Mirador S.A.S."):
        coinciden = {
            identificador
            for identificador, registros in _comercios().items()
            if contiene_en_registro(mensaje, registros[0][1]["nombre"])
        }
        assert coinciden == {"CO-AM-0004", "CO-AM-0005"}
