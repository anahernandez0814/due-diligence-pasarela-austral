"""Tests de las reglas puras de negocio I.1, I.2 e I.3 (R7 a R10, FR-002, FR-003, FR-005, FR-008).

Son funciones puras: reciben el estado o el libro y devuelven una decisión. No tocan el SDK ni el
modelo. Los datos son los ficticios del #5; ningún valor tiene forma de tarjeta, NIT o cédula.
"""

import pytest

from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.frentes import Frente
from due_diligence.libro import (
    CAUSA_ALTO_RIESGO,
    CAUSA_COINCIDENCIA_COMERCIO,
    CAUSA_COINCIDENCIA_REPRESENTANTE,
    Coincidencia,
    LibroReglas,
)
from due_diligence.reglas import (
    ALTO_RIESGO,
    RECOMENDACIONES,
    causas_vigentes,
    consulta_coincide,
    escalamiento_cubre,
    evaluar_informe,
    normalizar_recomendacion,
    permite_delegar_listas,
    permite_listas,
    reglas_de,
    requiere_escalamiento,
)
from due_diligence.simulacion import comercio_alto_riesgo, comercios_parecidos, respuesta_registro

COMERCIO = {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS"}
REPRESENTANTE = {"identificador": "PE-0001", "nombre": "Lucía Ferrer Montalvo"}
REPRESENTANTE_SIN_IDENTIFICADOR = {"nombre": "Lucía Ferrer Montalvo"}

# ------------------------------------------------------------------ constantes (FR-008, R10)


def test_las_categorias_de_alto_riesgo_son_una_constante_del_codigo():
    assert ALTO_RIESGO == (
        "apuestas",
        "criptoactivos",
        "suplementos dietarios",
        "venta de medicamentos",
    )


def test_el_conjunto_cerrado_de_recomendaciones():
    assert RECOMENDACIONES == ("habilitar", "no_habilitar", "decide_cumplimiento")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("habilitar", "habilitar"),
        ("Habilitar", "habilitar"),
        (" no habilitar ", "no_habilitar"),
        ("No-Habilitar", "no_habilitar"),
        ("no_habilitar", "no_habilitar"),
        ("DECIDE_CUMPLIMIENTO", "decide_cumplimiento"),
        ("Decide cumplimiento", "decide_cumplimiento"),
        ("aprobar", None),
        ("", None),
        ("   ", None),
        ("habilitar con reservas", None),
        ("no habilitar nunca", None),
        (None, None),
        (3, None),
        (["habilitar"], None),
        ({"valor": "habilitar"}, None),
    ],
)
def test_normalizar_recomendacion(texto, esperado):
    assert normalizar_recomendacion(texto) == esperado


# ------------------------------------------------------------------ consulta_coincide (R7)


@pytest.mark.parametrize(
    ("consulta", "entidad", "tipo", "esperado"),
    [
        # nombre igual, con otras mayúsculas, tildes o puntuación
        ({"tipo": "comercio", "nombre": "Tienda Verde SAS"}, COMERCIO, "comercio", True),
        ({"tipo": "comercio", "nombre": "TIENDA VERDE S.A.S."}, COMERCIO, "comercio", True),
        ({"tipo": "comercio", "nombre": "tienda  verde sas"}, COMERCIO, "comercio", True),
        ({"tipo": "persona", "nombre": "LUCIA FERRER MONTALVO"}, REPRESENTANTE, "persona", True),
        ({"tipo": "persona", "nombre": "lucía ferrer-montalvo"}, REPRESENTANTE, "persona", True),
        # el tipo debe ser el esperado
        ({"tipo": "persona", "nombre": "Tienda Verde SAS"}, COMERCIO, "comercio", False),
        ({"tipo": "comercio", "nombre": "Lucía Ferrer Montalvo"}, REPRESENTANTE, "persona", False),
        ({"tipo": "COMERCIO", "nombre": "Tienda Verde SAS"}, COMERCIO, "comercio", True),
        # identificador
        ({"tipo": "comercio", "identificador": "CO-TV-0001"}, COMERCIO, "comercio", True),
        ({"tipo": "comercio", "identificador": " co-tv-0001 "}, COMERCIO, "comercio", True),
        ({"tipo": "comercio", "identificador": "CO-TV-0009"}, COMERCIO, "comercio", False),
        # trae los dos y uno no coincide
        (
            {"tipo": "comercio", "nombre": "Tienda Verde SAS", "identificador": "CO-TV-0009"},
            COMERCIO,
            "comercio",
            False,
        ),
        (
            {"tipo": "comercio", "nombre": "Otra Tienda SAS", "identificador": "CO-TV-0001"},
            COMERCIO,
            "comercio",
            False,
        ),
        (
            {"tipo": "comercio", "nombre": "Tienda Verde SAS", "identificador": "CO-TV-0001"},
            COMERCIO,
            "comercio",
            True,
        ),
        # sin ninguna clave
        ({"tipo": "comercio"}, COMERCIO, "comercio", False),
        ({"tipo": "comercio", "nombre": None, "identificador": None}, COMERCIO, "comercio", False),
        ({"tipo": "comercio", "nombre": "", "identificador": "  "}, COMERCIO, "comercio", False),
        # un nombre ajeno
        ({"tipo": "comercio", "nombre": "Almacén Mirador SAS"}, COMERCIO, "comercio", False),
        # nombre parcial: no coincide (la pasarela busca por el nombre completo)
        ({"tipo": "comercio", "nombre": "Tienda Verde"}, COMERCIO, "comercio", False),
        # sin tipo
        ({"nombre": "Tienda Verde SAS"}, COMERCIO, "comercio", False),
    ],
)
def test_consulta_coincide(consulta, entidad, tipo, esperado):
    assert consulta_coincide(consulta, entidad, tipo) is esperado


def test_un_identificador_consultado_para_un_representante_sin_identificador_no_coincide():
    # Si el registro devolvió al representante sin identificador, una consulta que trae un
    # identificador no puede verificarse como la misma persona, aunque el nombre coincida (R7).
    consulta = {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo", "identificador": "PE-0001"}
    assert consulta_coincide(consulta, REPRESENTANTE_SIN_IDENTIFICADOR, "persona") is False
    solo_identificador = {"tipo": "persona", "identificador": "PE-0001"}
    assert (
        consulta_coincide(solo_identificador, REPRESENTANTE_SIN_IDENTIFICADOR, "persona") is False
    )
    # También con el identificador vacío o ausente (None) en la entidad.
    con_none = {"nombre": "Lucía Ferrer Montalvo", "identificador": None}
    assert consulta_coincide(solo_identificador, con_none, "persona") is False


def test_un_nombre_para_un_representante_sin_identificador_si_coincide_por_el_nombre():
    consulta = {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo"}
    assert consulta_coincide(consulta, REPRESENTANTE_SIN_IDENTIFICADOR, "persona") is True


def test_un_nombre_para_un_representante_con_identificador_coincide_por_el_nombre():
    consulta = {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo"}
    assert consulta_coincide(consulta, REPRESENTANTE, "persona") is True


def test_una_consulta_con_claves_que_no_son_texto_no_coincide_ni_lanza():
    for malformada in (
        {"tipo": "comercio", "nombre": 3},
        {"tipo": "comercio", "identificador": ["CO-TV-0001"]},
        {"tipo": 7, "nombre": "Tienda Verde SAS"},
    ):
        assert consulta_coincide(malformada, COMERCIO, "comercio") is False
    assert consulta_coincide(None, COMERCIO, "comercio") is False
    assert consulta_coincide("texto", COMERCIO, "comercio") is False
    assert (
        consulta_coincide({"tipo": "comercio", "nombre": "Tienda Verde SAS"}, None, "comercio")
        is False
    )


# ------------------------------------------------------------------ permite_listas (US1, FR-002)

MOTIVO_SIN_COMERCIO = (
    "Aún no hay un comercio identificado de forma unívoca en el registro mercantil."
)


def _estado_con_registro(situacion, *comercios, identificar=True):
    estado = EstadoCaso("solicitud")
    if situacion is Situacion.RECHAZADO:
        estado.cambiar_situacion(Frente.REGISTRO, Situacion.RECHAZADO, "motivo")
    elif situacion is not Situacion.SIN_INICIAR:
        estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
        if situacion in (Situacion.TERMINADO, Situacion.NO_TERMINADO):
            estado.cambiar_situacion(Frente.REGISTRO, situacion)
    if identificar:
        estado.registrar_identificacion(respuesta_registro(*comercios))
    return estado


def _con_comercio():
    return _estado_con_registro(Situacion.TERMINADO, comercio_alto_riesgo())


def test_sin_registro_delegado_no_se_permite_consultar_listas():
    estado = _estado_con_registro(Situacion.SIN_INICIAR, identificar=False)
    permitida, motivo = permite_listas(estado, {"tipo": "comercio", "nombre": "Tienda Verde SAS"})
    assert permitida is False and motivo == MOTIVO_SIN_COMERCIO


def test_con_varias_coincidencias_se_bloquea_y_se_pide_el_identificador_al_analista():
    estado = _estado_con_registro(Situacion.TERMINADO, *comercios_parecidos())
    permitida, motivo = permite_listas(estado, {"tipo": "comercio", "identificador": "CO-AM-0004"})
    assert permitida is False
    assert "varias coincidencias" in motivo and "identificador" in motivo
    assert "CO-AM-0004" not in motivo and "Almacén" not in motivo  # no repite lo consultado


def test_con_ninguna_coincidencia_se_bloquea():
    estado = _estado_con_registro(Situacion.TERMINADO)
    permitida, motivo = permite_listas(estado, {"tipo": "comercio", "nombre": "Tienda Verde SAS"})
    assert permitida is False and "no devolvió coincidencias" in motivo


def test_el_comercio_identificado_con_tipo_comercio_se_permite():
    por_nombre = {"tipo": "comercio", "nombre": "Tienda Verde SAS"}
    por_identificador = {"tipo": "comercio", "identificador": "CO-TV-0001"}
    assert permite_listas(_con_comercio(), por_nombre) == (True, "")
    assert permite_listas(_con_comercio(), por_identificador) == (True, "")


def test_el_representante_con_tipo_persona_se_permite():
    por_nombre = {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo"}
    por_identificador = {"tipo": "persona", "identificador": "PE-0001"}
    assert permite_listas(_con_comercio(), por_nombre) == (True, "")
    assert permite_listas(_con_comercio(), por_identificador) == (True, "")


@pytest.mark.parametrize(
    "consulta",
    [
        {"tipo": "persona", "nombre": "Tienda Verde SAS"},  # el comercio con tipo persona
        {"tipo": "comercio", "nombre": "Lucía Ferrer Montalvo"},  # el representante como comercio
        {"tipo": "persona", "identificador": "CO-TV-0001"},
        {"tipo": "comercio", "identificador": "PE-0001"},
        {"tipo": "comercio", "nombre": "Almacén Mirador SAS"},  # un nombre ajeno
        {"tipo": "persona", "nombre": "Mateo Ríos Cabrera"},
        {"tipo": "comercio"},  # sin ninguna clave
        {"nombre": "Tienda Verde SAS"},  # sin tipo
        {"tipo": "comercio", "nombre": "Tienda Verde SAS", "identificador": "CO-TV-0009"},
        {"tipo": "comercio", "nombre": 3},
        None,
        "texto",
    ],
)
def test_una_consulta_que_no_es_del_comercio_ni_del_representante_con_su_tipo_se_bloquea(consulta):
    permitida, motivo = permite_listas(_con_comercio(), consulta)
    assert permitida is False
    assert "no corresponde al comercio identificado ni a su representante legal" in motivo
    assert "Mateo" not in motivo and "CO-TV-0009" not in motivo and "Tienda Verde" not in motivo


def test_las_claves_en_otro_formato_se_permiten():
    consulta = {"tipo": "comercio", "nombre": "  tienda VERDE s.a.s. "}
    assert permite_listas(_con_comercio(), consulta)[0] is True


def test_sin_representante_solo_se_puede_consultar_al_comercio():
    estado = _estado_con_registro(
        Situacion.TERMINADO, {**comercio_alto_riesgo(), "representante_legal": None}
    )
    assert permite_listas(estado, {"tipo": "comercio", "nombre": "Tienda Verde SAS"})[0] is True
    assert (
        permite_listas(estado, {"tipo": "persona", "nombre": "Lucía Ferrer Montalvo"})[0] is False
    )


# ------------------------------------------------------------------ permite_delegar_listas (FR-018)


@pytest.mark.parametrize(
    "situacion", [Situacion.SIN_INICIAR, Situacion.RECHAZADO, Situacion.NO_TERMINADO]
)
def test_no_se_delega_listas_si_el_registro_no_se_delego_fue_rechazado_o_no_termino(situacion):
    estado = _estado_con_registro(situacion, comercio_alto_riesgo(), identificar=False)
    permitida, motivo = permite_delegar_listas(estado)
    assert permitida is False and motivo


def test_el_motivo_de_registro_sin_iniciar_pide_delegarlo_primero():
    estado = _estado_con_registro(Situacion.SIN_INICIAR, identificar=False)
    assert "primero el registro mercantil" in permite_delegar_listas(estado)[1]


def test_no_se_delega_listas_si_el_registro_termino_con_varias_coincidencias():
    estado = _estado_con_registro(Situacion.TERMINADO, *comercios_parecidos())
    permitida, motivo = permite_delegar_listas(estado)
    assert permitida is False
    assert "varias coincidencias" in motivo and "identificador" in motivo
    assert "CO-AM" not in motivo


def test_no_se_delega_listas_si_el_registro_termino_sin_coincidencias():
    permitida, motivo = permite_delegar_listas(_estado_con_registro(Situacion.TERMINADO))
    assert permitida is False and "no devolvió coincidencias" in motivo


def test_se_delega_listas_si_el_registro_termino_con_un_comercio_unico():
    assert permite_delegar_listas(_con_comercio()) == (True, "")


def test_se_permite_delegar_listas_con_el_registro_en_curso_la_herramienta_espera():
    estado = _estado_con_registro(Situacion.EN_CURSO, identificar=False)
    assert permite_delegar_listas(estado) == (True, "")


# ----------------------------------------------------------------- regla I.2: causas y escalamiento


def _libro_con(*tipos_de_coincidencia, escalamientos=()):
    libro = LibroReglas()
    libro.coincidencias = [
        Coincidencia(t, "Lista A", "Fuente A", "2026-09-30") for t in tipos_de_coincidencia
    ]
    libro.escalamientos = [frozenset(e) for e in escalamientos]
    return libro


def test_las_causas_vigentes_son_claves_fijas_sin_nombres_ni_identificadores():
    assert causas_vigentes(LibroReglas()) == frozenset()
    assert causas_vigentes(_libro_con("comercio")) == {CAUSA_COINCIDENCIA_COMERCIO}
    assert causas_vigentes(_libro_con("persona")) == {CAUSA_COINCIDENCIA_REPRESENTANTE}
    assert causas_vigentes(_libro_con("comercio", "persona", "persona")) == {
        CAUSA_COINCIDENCIA_COMERCIO,
        CAUSA_COINCIDENCIA_REPRESENTANTE,
    }
    # Las tres claves posibles son exactamente estas.
    assert {CAUSA_COINCIDENCIA_COMERCIO, CAUSA_COINCIDENCIA_REPRESENTANTE, CAUSA_ALTO_RIESGO} == {
        "coincidencia_comercio",
        "coincidencia_representante",
        "alto_riesgo",
    }


def test_requiere_escalamiento_es_que_haya_causas_vigentes():
    assert requiere_escalamiento(LibroReglas()) is False
    assert requiere_escalamiento(_libro_con("persona")) is True


def test_el_escalamiento_cubre_segun_las_instantaneas():
    assert escalamiento_cubre(LibroReglas()) is True  # sin causas no hay nada que cubrir
    assert escalamiento_cubre(_libro_con("persona")) is False  # con una causa y sin escalar
    cubierto = _libro_con("persona", escalamientos=[{CAUSA_COINCIDENCIA_REPRESENTANTE}])
    assert escalamiento_cubre(cubierto) is True


def test_una_causa_nueva_posterior_al_escalamiento_no_queda_cubierta():
    libro = _libro_con("persona", escalamientos=[{CAUSA_COINCIDENCIA_REPRESENTANTE}])
    libro.coincidencias.append(Coincidencia("comercio", "Lista B", "Fuente B", "2026-09-30"))
    assert escalamiento_cubre(libro) is False  # hace falta escalar de nuevo
    libro.escalamientos.append(causas_vigentes(libro))
    assert escalamiento_cubre(libro) is True


def test_una_segunda_coincidencia_de_la_misma_entidad_no_es_una_causa_nueva():
    libro = _libro_con("persona", escalamientos=[{CAUSA_COINCIDENCIA_REPRESENTANTE}])
    libro.coincidencias.append(Coincidencia("persona", "Lista B", "Fuente B", "2026-09-30"))
    assert escalamiento_cubre(libro) is True


def test_la_regla_del_evento_sale_de_las_causas():
    assert reglas_de({CAUSA_COINCIDENCIA_COMERCIO}) == "I.2"
    assert reglas_de({CAUSA_COINCIDENCIA_REPRESENTANTE}) == "I.2"
    assert reglas_de({CAUSA_ALTO_RIESGO}) == "I.3"
    assert reglas_de({CAUSA_ALTO_RIESGO, CAUSA_COINCIDENCIA_COMERCIO}) == "I.2, I.3"
    assert reglas_de(frozenset()) is None


# ------------------------------------------------------------------ evaluar_informe (regla I.2)


def _estado_de_informe(libro=None):
    estado = _estado_con_registro(Situacion.TERMINADO, comercio_alto_riesgo())
    if libro is not None:
        estado.libro = libro
    return estado


def _informe(recomendacion):
    return {
        "comercio": {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS"},
        "recomendacion": recomendacion,
        "hallazgos": {},
        "cobertura": "completa",
    }


def _textos(rechazos):
    return " ".join(r.texto for r in rechazos)


@pytest.mark.parametrize("valor", ["aprobar", "", None, 3, "habilitar con reservas"])
def test_una_recomendacion_fuera_del_conjunto_se_rechaza_aunque_ninguna_regla_aplique(valor):
    rechazos = evaluar_informe(_estado_de_informe(), _informe(valor))
    assert rechazos, "debe rechazarse"
    texto = _textos(rechazos)
    assert "habilitar, no_habilitar o decide_cumplimiento" in texto


def test_una_entrada_que_no_es_un_mapa_se_rechaza():
    for malformada in (None, "informe", ["habilitar"]):
        assert evaluar_informe(_estado_de_informe(), malformada)


def test_con_coincidencia_se_rechaza_habilitar_y_el_motivo_nombra_la_coincidencia():
    libro = _libro_con("persona")
    rechazos = evaluar_informe(_estado_de_informe(libro), _informe("habilitar"))
    texto = _textos(rechazos)
    assert "coincidencia en listas restrictivas: no se puede recomendar habilitar" in texto
    assert any(r.regla == "I.2" for r in rechazos)


@pytest.mark.parametrize("recomendacion", ["habilitar", "no_habilitar", "decide_cumplimiento"])
def test_con_coincidencia_sin_escalar_cualquier_recomendacion_se_rechaza(recomendacion):
    libro = _libro_con("comercio")
    texto = _textos(evaluar_informe(_estado_de_informe(libro), _informe(recomendacion)))
    assert "El caso requiere escalamiento a cumplimiento y aún no se ha escalado por" in texto
    assert "coincidencia del comercio en listas restrictivas" in texto


def test_el_motivo_de_escalar_usa_solo_etiquetas_fijas_y_ningun_dato_consultado():
    libro = _libro_con("comercio", "persona")
    texto = _textos(evaluar_informe(_estado_de_informe(libro), _informe("decide_cumplimiento")))
    assert "coincidencia del comercio en listas restrictivas" in texto
    assert "coincidencia del representante legal en listas restrictivas" in texto
    for dato in ("CO-TV-0001", "Tienda Verde", "PE-0001", "Lucía", "coincidencia_comercio"):
        assert dato not in texto


@pytest.mark.parametrize("recomendacion", ["no_habilitar", "decide_cumplimiento"])
def test_con_coincidencia_y_escalamiento_cubierto_se_aceptan_las_que_no_habilitan(recomendacion):
    libro = _libro_con("persona", escalamientos=[{CAUSA_COINCIDENCIA_REPRESENTANTE}])
    assert evaluar_informe(_estado_de_informe(libro), _informe(recomendacion)) == []


def test_con_coincidencia_y_escalamiento_cubierto_habilitar_sigue_rechazado():
    libro = _libro_con("persona", escalamientos=[{CAUSA_COINCIDENCIA_REPRESENTANTE}])
    texto = _textos(evaluar_informe(_estado_de_informe(libro), _informe("habilitar")))
    assert "no se puede recomendar habilitar" in texto
    assert "aún no se ha escalado" not in texto


def test_el_rechazo_acumula_todos_los_motivos_que_apliquen():
    libro = _libro_con("persona")
    rechazos = evaluar_informe(_estado_de_informe(libro), _informe("habilitar"))
    textos = [r.texto for r in rechazos]
    assert any("no se puede recomendar habilitar" in t for t in textos)
    assert any("aún no se ha escalado" in t for t in textos)


def test_sin_causas_una_recomendacion_que_no_habilita_se_acepta_sin_escalar():
    assert evaluar_informe(_estado_de_informe(), _informe("no_habilitar")) == []
    assert evaluar_informe(_estado_de_informe(), _informe("decide_cumplimiento")) == []
