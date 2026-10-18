"""Pruebas del servidor por el protocolo, con el cliente en memoria del SDK (R2, R12).

Se llama a las herramientas como las llamaría Claude Code: por MCP, no como funciones.
"""

import asyncio
import json
import sys

import pytest
from mcp import StdioServerParameters
from mcp.client import Client

from servidor_mcp import datos, registro
from servidor_mcp.riesgo import categorias_conocidas
from servidor_mcp.servidor import servidor

HERRAMIENTAS = {
    "consultar_registro_mercantil",
    "consultar_listas_restrictivas",
    "buscar_noticias",
    "consultar_riesgo_categoria",
    "registrar_informe",
    "escalar_a_cumplimiento",
}
ALEGACIONES_EN_INGLES = ("field required", "validation error", "input should", "error executing")


@pytest.fixture(autouse=True)
def _entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("PASARELA_RESULTADOS_DIR", str(tmp_path / "resultados"))
    monkeypatch.delenv("PASARELA_FALLA_NOTICIAS", raising=False)
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)
    datos.limpiar_cache()
    yield
    datos.limpiar_cache()


def _con_cliente(coroutine_fn):
    async def principal():
        async with Client(servidor) as cliente:
            return await coroutine_fn(cliente)

    return asyncio.run(principal())


def _llamar(nombre, argumentos=None):
    return _con_cliente(lambda c: c.call_tool(nombre, argumentos or {}))


def _herramientas():
    async def listar(cliente):
        return (await cliente.list_tools()).tools

    return {t.name: t for t in _con_cliente(listar)}


def _texto(resultado):
    return "\n".join(c.text for c in resultado.content)


def _informe():
    """Un informe en el formato del #9 (R2): afirmaciones con fuente y fecha, y conflictos."""
    return {
        "comercio": {
            "identificador": "CO-TV-0001",
            "nombre": "Tienda Verde SAS",
            "verificado": True,
        },
        "recomendacion": "No habilitar de forma automática.",
        "hallazgos": {
            "registro": [
                {"texto": "Una coincidencia.", "fuente": "Registro", "fecha": "2026-09-30"}
            ]
        },
        "conflictos": {"resumen": "Sin conflictos entre las fuentes registrales.", "lista": []},
        "cobertura": "Cubiertos: todos los frentes.",
    }


def _escalamiento():
    return {
        "comercio": {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS"},
        "hallazgos": {"riesgo": {"contenido": "Nivel alto.", "fuente": "Catálogo"}},
        "cobertura": "Cubiertos: todos los frentes.",
        "causa_escalamiento": "Categoría de alto riesgo.",
        "accion_recomendada": "Decide el oficial de cumplimiento.",
    }


LLAMADAS_VALIDAS = {
    "consultar_registro_mercantil": {"identificador": "CO-TV-0001"},
    "consultar_listas_restrictivas": {"tipo": "persona", "identificador": "PE-0003"},
    "buscar_noticias": {"identificador": "CO-AM-0005"},
    "consultar_riesgo_categoria": {"categoria": "suplementos dietarios"},
}


# --- las seis herramientas y sus descripciones ----------------------------------------------


def test_lista_exactamente_las_seis_herramientas():
    assert set(_herramientas()) == HERRAMIENTAS


def test_las_descripciones_dicen_lo_que_hacen_y_lo_que_no():
    herramientas = _herramientas()
    assert (
        "NO es una coincidencia en listas restrictivas"
        in herramientas["buscar_noticias"].description
    )
    assert "NO es una coincidencia en listas restrictivas" in (
        herramientas["consultar_listas_restrictivas"].description
    )
    registro_desc = herramientas["consultar_registro_mercantil"].description
    assert "TODOS" in registro_desc
    assert "no elige" in registro_desc
    for nombre in ("registrar_informe", "escalar_a_cumplimiento"):
        assert "canales de decisión" in herramientas[nombre].description
    assert "no devuelve la categoría" in registro_desc


def test_la_descripcion_de_riesgo_lista_las_categorias_conocidas():
    descripcion = _herramientas()["consultar_riesgo_categoria"].description
    for categoria in categorias_conocidas():
        assert categoria in descripcion


def test_todos_los_parametros_son_opcionales_y_llevan_descripcion_con_el_tipo_esperado():
    for nombre, herramienta in _herramientas().items():
        esquema = herramienta.input_schema
        assert not esquema.get("required"), nombre
        propiedades = esquema["properties"]
        assert propiedades, nombre
        for parametro, propiedad in propiedades.items():
            descripcion = propiedad.get("description", "")
            assert descripcion, f"{nombre}.{parametro}"
            assert any(tipo in descripcion for tipo in ("Texto", "Objeto", "Lista")), (
                f"{nombre}.{parametro}: {descripcion}"
            )


def test_descripciones_y_mensajes_estan_en_espanol():
    for nombre, herramienta in _herramientas().items():
        descripcion = herramienta.description.lower()
        assert " de " in descripcion or " el " in descripcion, nombre
        for ingles in ALEGACIONES_EN_INGLES:
            assert ingles not in descripcion, nombre
    for nombre, argumentos in (
        ("consultar_registro_mercantil", {}),
        ("registrar_informe", {}),
        ("escalar_a_cumplimiento", {"comercio": 5}),
    ):
        texto = _texto(_llamar(nombre, argumentos)).lower()
        for ingles in ALEGACIONES_EN_INGLES:
            assert ingles not in texto, nombre


# --- cada herramienta responde por el protocolo ---------------------------------------------


@pytest.mark.parametrize("nombre", sorted(LLAMADAS_VALIDAS))
def test_cada_herramienta_de_consulta_responde_por_el_protocolo(nombre):
    resultado = _llamar(nombre, LLAMADAS_VALIDAS[nombre])
    assert resultado.is_error is False
    cuerpo = resultado.structured_content
    assert cuerpo["metadatos"]["fuentes"]
    assert json.loads(_texto(resultado)) == cuerpo


def test_registrar_informe_responde_por_el_protocolo():
    resultado = _llamar("registrar_informe", _informe())
    assert resultado.is_error is False
    assert resultado.structured_content["resultado"] == "informe_registrado"
    assert resultado.structured_content["hechos"][0]["contenido"]["id"].startswith("INF-")


def test_escalar_a_cumplimiento_responde_por_el_protocolo():
    resultado = _llamar("escalar_a_cumplimiento", _escalamiento())
    assert resultado.is_error is False
    assert resultado.structured_content["resultado"] == "caso_escalado"
    assert resultado.structured_content["hechos"][0]["contenido"]["id"].startswith("ESC-")


def test_el_registro_devuelve_las_coincidencias_por_el_protocolo():
    cuerpo = _llamar("consultar_registro_mercantil", {"nombre": "Almacén Mirador SAS"})
    assert cuerpo.structured_content["coincidencias"] == ["CO-AM-0004", "CO-AM-0005"]


# --- campo ausente y tipo incorrecto: error estructurado en español, no el de pydantic ------


def _comprobar_error_estructurado(resultado, tipo):
    assert resultado.is_error is True
    assert resultado.structured_content is not None
    assert resultado.structured_content["tipo"] == tipo
    assert resultado.structured_content["reintentable"] is False
    texto = _texto(resultado).lower()
    for ingles in ALEGACIONES_EN_INGLES:
        assert ingles not in texto
    return resultado.structured_content


def test_registrar_informe_sin_campos_da_campos_obligatorios_ausentes():
    cuerpo = _comprobar_error_estructurado(
        _llamar("registrar_informe"), "campos_obligatorios_ausentes"
    )
    # La lista del #5 más `conflictos` (#9), en el mismo orden.
    assert cuerpo["campos_faltantes"] == [
        "comercio",
        "recomendacion",
        "hallazgos",
        "cobertura",
        "conflictos",
    ]


def test_registrar_informe_con_un_campo_ausente_nombra_ese_campo():
    entrada = _informe()
    del entrada["cobertura"]
    cuerpo = _comprobar_error_estructurado(
        _llamar("registrar_informe", entrada), "campos_obligatorios_ausentes"
    )
    assert cuerpo["campos_faltantes"] == ["cobertura"]


def test_registrar_informe_con_un_tipo_incorrecto_da_entrada_invalida():
    _comprobar_error_estructurado(
        _llamar("registrar_informe", _informe() | {"comercio": 5}), "entrada_invalida"
    )


def test_una_afirmacion_sin_fuente_da_entrada_invalida_con_sus_problemas_por_el_protocolo():
    # Q7 del #9: la forma de cada afirmación se valida en la pasarela, con su ruta.
    entrada = _informe()
    del entrada["hallazgos"]["registro"][0]["fuente"]
    cuerpo = _comprobar_error_estructurado(
        _llamar("registrar_informe", entrada), "entrada_invalida"
    )
    assert cuerpo["problemas"] == [
        {"ruta": "hallazgos.registro[0].fuente", "texto": "Debe ser un texto no vacío."}
    ]


def test_la_descripcion_de_registrar_informe_dice_lo_que_pone_el_sistema_y_lo_que_no_hace():
    # Constitución IV y hallazgo C1 del #9: qué hace y qué no hace.
    descripcion = _herramientas()["registrar_informe"].description
    assert "El comercio, los conflictos y la cobertura los pone el sistema" in descripcion
    assert "con su fuente y su fecha" in descripcion
    assert "tampoco comprueba que cada fuente se haya consultado" in descripcion.lower()
    assert "ni escala el caso" in descripcion


def test_escalar_sin_campos_da_los_cinco_faltantes():
    cuerpo = _comprobar_error_estructurado(
        _llamar("escalar_a_cumplimiento"), "campos_obligatorios_ausentes"
    )
    assert len(cuerpo["campos_faltantes"]) == 5


def test_escalar_con_un_campo_ausente():
    entrada = _escalamiento()
    del entrada["accion_recomendada"]
    cuerpo = _comprobar_error_estructurado(
        _llamar("escalar_a_cumplimiento", entrada), "campos_obligatorios_ausentes"
    )
    assert cuerpo["campos_faltantes"] == ["accion_recomendada"]


def test_escalar_con_un_tipo_incorrecto_da_entrada_invalida():
    _comprobar_error_estructurado(
        _llamar("escalar_a_cumplimiento", _escalamiento() | {"cobertura": 5}), "entrada_invalida"
    )


def test_el_registro_sin_argumentos_da_entrada_invalida():
    _comprobar_error_estructurado(_llamar("consultar_registro_mercantil"), "entrada_invalida")


@pytest.mark.parametrize("valor", [5, ["Tienda Verde"], {"a": 1}, True])
def test_el_registro_con_un_tipo_incorrecto_da_entrada_invalida(valor):
    _comprobar_error_estructurado(
        _llamar("consultar_registro_mercantil", {"nombre": valor}), "entrada_invalida"
    )


def test_ninguna_herramienta_lanza_con_argumentos_absurdos():
    absurdos = {"nombre": {"a": [1, 2]}, "identificador": 3.5, "tipo": None, "categoria": [[]]}
    for nombre in HERRAMIENTAS:
        resultado = _llamar(nombre, absurdos)
        assert resultado.structured_content is not None, nombre
        assert "traceback" not in _texto(resultado).lower(), nombre


# --- excepción interna ----------------------------------------------------------------------


def test_una_excepcion_interna_es_error_interno_no_reintentable_y_en_espanol(monkeypatch):
    def falla(*_args, **_kwargs):
        raise RuntimeError("detalle secreto del fallo")

    monkeypatch.setattr(registro, "consultar_registro_mercantil", falla)
    resultado = _llamar("consultar_registro_mercantil", {"identificador": "CO-TV-0001"})
    assert resultado.is_error is True
    cuerpo = resultado.structured_content
    assert cuerpo["tipo"] == "error_interno"
    assert cuerpo["reintentable"] is False
    assert cuerpo["obtenido"] == {}
    texto = _texto(resultado)
    assert "detalle secreto del fallo" not in texto
    assert "traceback" not in texto.lower()
    assert "error interno" in cuerpo["mensaje"].lower()


# --- caída de noticias: solo afecta a las noticias ------------------------------------------


def test_con_la_caida_de_noticias_las_otras_cinco_herramientas_responden(monkeypatch):
    monkeypatch.setenv("PASARELA_FALLA_NOTICIAS", "1")
    caida = _llamar("buscar_noticias", {"identificador": "CO-AM-0005"})
    assert caida.is_error is True
    assert caida.structured_content["tipo"] == "servicio_no_disponible"
    assert caida.structured_content["reintentable"] is True
    otras = {
        **{n: a for n, a in LLAMADAS_VALIDAS.items() if n != "buscar_noticias"},
        "registrar_informe": _informe(),
        "escalar_a_cumplimiento": _escalamiento(),
    }
    assert len(otras) == 5
    for nombre, argumentos in otras.items():
        assert _llamar(nombre, argumentos).is_error is False, nombre


def test_la_variable_se_lee_en_cada_llamada_con_el_servidor_ya_arrancado(monkeypatch):
    async def secuencia(cliente):
        antes = await cliente.call_tool("buscar_noticias", {"identificador": "CO-AM-0005"})
        monkeypatch.setenv("PASARELA_FALLA_NOTICIAS", "1")
        caida = await cliente.call_tool("buscar_noticias", {"identificador": "CO-AM-0005"})
        monkeypatch.setenv("PASARELA_FALLA_NOTICIAS", "0")
        despues = await cliente.call_tool("buscar_noticias", {"identificador": "CO-AM-0005"})
        return antes, caida, despues

    antes, caida, despues = _con_cliente(secuencia)
    assert (antes.is_error, caida.is_error, despues.is_error) == (False, True, False)


# --- arranque real por stdio ----------------------------------------------------------------


def test_el_servidor_arranca_por_stdio_y_responde_sin_ensuciar_stdout():
    async def principal():
        parametros = StdioServerParameters(command=sys.executable, args=["-m", "servidor_mcp"])
        async with Client(parametros) as cliente:
            herramientas = {t.name for t in (await cliente.list_tools()).tools}
            resultado = await cliente.call_tool(
                "consultar_riesgo_categoria", {"categoria": "apuestas"}
            )
            return herramientas, resultado

    herramientas, resultado = asyncio.run(principal())
    assert herramientas == HERRAMIENTAS
    assert resultado.is_error is False
    assert resultado.structured_content["hechos"][0]["contenido"]["nivel"] == "alto"


# --- el esquema publica el tipo JSON, y un tipo incorrecto sigue siendo error propio --------------

TIPOS_JSON = {
    "consultar_registro_mercantil": {"nombre": "string", "identificador": "string"},
    "consultar_listas_restrictivas": {
        "tipo": "string",
        "nombre": "string",
        "identificador": "string",
    },
    "buscar_noticias": {"nombre": "string", "identificador": "string"},
    "consultar_riesgo_categoria": {"categoria": "string"},
    "registrar_informe": {
        "comercio": "object",
        "recomendacion": "string",
        "hallazgos": "object",
        "conflictos": "object",
        "cobertura": ["string", "array"],
    },
    "escalar_a_cumplimiento": {
        "comercio": "object",
        "hallazgos": "object",
        "cobertura": ["string", "array"],
        "causa_escalamiento": "string",
        "accion_recomendada": "string",
    },
}


def test_tools_list_publica_el_tipo_json_de_cada_parametro():
    herramientas = _herramientas()
    for nombre, esperados in TIPOS_JSON.items():
        propiedades = herramientas[nombre].input_schema["properties"]
        assert {p: v.get("type") for p, v in propiedades.items()} == esperados, nombre


def test_publicar_el_tipo_no_vuelve_obligatorio_ningun_parametro():
    for nombre, herramienta in _herramientas().items():
        assert not herramienta.input_schema.get("required"), nombre


def _validos(herramienta):
    return {
        "consultar_registro_mercantil": {"identificador": "CO-TV-0001"},
        "consultar_listas_restrictivas": {"tipo": "persona", "identificador": "PE-0003"},
        "buscar_noticias": {"identificador": "CO-AM-0005"},
        "consultar_riesgo_categoria": {"categoria": "apuestas"},
        "registrar_informe": _informe(),
        "escalar_a_cumplimiento": _escalamiento(),
    }[herramienta]


TIPOS_INCORRECTOS = [
    ("consultar_registro_mercantil", {"identificador": None, "nombre": 5}),
    ("consultar_registro_mercantil", {"identificador": 5}),
    ("consultar_listas_restrictivas", {"tipo": 5}),
    ("consultar_listas_restrictivas", {"identificador": ["PE-0003"]}),
    ("buscar_noticias", {"identificador": None, "nombre": 5}),
    ("consultar_riesgo_categoria", {"categoria": 5}),
    ("consultar_riesgo_categoria", {"categoria": ["apuestas"]}),
    ("registrar_informe", {"comercio": "Tienda Verde SAS"}),
    ("registrar_informe", {"recomendacion": 5}),
    ("registrar_informe", {"hallazgos": ["registro"]}),
    ("registrar_informe", {"cobertura": 5}),
    ("registrar_informe", {"conflictos": "texto"}),
    ("escalar_a_cumplimiento", {"comercio": 5}),
    ("escalar_a_cumplimiento", {"hallazgos": "texto"}),
    ("escalar_a_cumplimiento", {"cobertura": {"a": 1}}),
    ("escalar_a_cumplimiento", {"causa_escalamiento": 5}),
    ("escalar_a_cumplimiento", {"accion_recomendada": ["x"]}),
]


@pytest.mark.parametrize(("herramienta", "cambio"), TIPOS_INCORRECTOS)
def test_un_tipo_incorrecto_sigue_dando_entrada_invalida_en_espanol(herramienta, cambio):
    # Con el tipo publicado en el esquema, el SDK sigue dejando pasar cualquier valor hasta la
    # validación propia: el error es el del contrato, no el de pydantic.
    resultado = _llamar(herramienta, _validos(herramienta) | cambio)
    cuerpo = _comprobar_error_estructurado(resultado, "entrada_invalida")
    assert "debe" in cuerpo["mensaje"] or "exactamente" in cuerpo["mensaje"]
    texto = _texto(resultado).lower()
    for ingles in ("pydantic", "[type=", "input_value", "valid string", "valid dictionary"):
        assert ingles not in texto


def test_la_descripcion_de_registrar_informe_nombra_los_tres_valores_de_recomendacion():
    herramienta = _herramientas()["registrar_informe"]
    for valor in ("habilitar", "no_habilitar", "decide_cumplimiento"):
        assert valor in herramienta.description
        assert valor in herramienta.input_schema["properties"]["recomendacion"]["description"]
    # Es una guía: la descripción dice que el servidor no la valida ni decide.
    assert "no la valida" in herramienta.description
    assert "No valida reglas de negocio ni decide" in herramienta.description


def test_el_servidor_sigue_aceptando_cualquier_recomendacion_textual():
    for texto in ("aprobar", "No habilitar de forma automática.", "decide_cumplimiento"):
        entrada = {**_informe(), "recomendacion": texto}
        resultado = _llamar("registrar_informe", entrada)
        assert resultado.is_error is False, texto
        assert resultado.structured_content["resultado"] == "informe_registrado"
