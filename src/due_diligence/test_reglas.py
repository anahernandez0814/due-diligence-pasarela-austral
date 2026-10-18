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
    ConsultaListas,
    ConsultaRiesgo,
    Escalamiento,
    LibroReglas,
)
from due_diligence.reglas import (
    ALTO_RIESGO,
    MOTIVO_ENTRADA_INFORME,
    RECOMENDACIONES,
    Rechazo,
    categoria_determinada,
    causas_vigentes,
    consulta_coincide,
    es_alto_riesgo,
    escalamiento_cubre,
    evaluar_cierre,
    evaluar_informe,
    motivo_de_escalar,
    normalizar_recomendacion,
    permite_delegar_listas,
    permite_listas,
    reglas_de,
    requiere_escalamiento,
)
from due_diligence.simulacion import (
    comercio_alto_riesgo,
    comercio_del_registro,
    comercios_parecidos,
    respuesta_registro,
)

COMERCIO = {"identificador": "CO-TV-0001", "nombre": "Tienda Verde SAS"}
CLAVE_TV = ("CO-TV-0001", "Tienda Verde SAS", True)
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
    # #10 (R8): el escalamiento guarda el comercio del caso, el `CO-TV-0001` de estos estados.
    libro.escalamientos = [Escalamiento(frozenset(e), CLAVE_TV) for e in escalamientos]
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
    libro.escalamientos.append(Escalamiento(causas_vigentes(libro), CLAVE_TV))
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


def test_sin_causas_no_habilitar_se_acepta_sin_escalar_y_decide_cumplimiento_exige_escalar():
    # Desde el #10 (FR-004) `decide_cumplimiento` exige un escalamiento del comercio actual, también
    # sin causas: el oficial solo decide lo que le llega. `no_habilitar` no cambia.
    from due_diligence.reglas import MOTIVO_DECIDE_SIN_ESCALAR

    assert evaluar_informe(_estado_de_informe(), _informe("no_habilitar")) == []
    assert evaluar_informe(_estado_de_informe(), _informe("decide_cumplimiento")) == [
        Rechazo(MOTIVO_DECIDE_SIN_ESCALAR, "V")
    ]
    escalado = _estado_de_informe()
    escalado.libro.escalamientos.append(Escalamiento(frozenset(), CLAVE_TV))
    assert evaluar_informe(escalado, _informe("decide_cumplimiento")) == []


# --------------------------------------------------------------- regla I.3: categoría y alto riesgo


def _libro_de_riesgo(*consultas):
    libro = LibroReglas()
    libro.consultas_riesgo = [ConsultaRiesgo(c, n) for c, n in consultas]
    return libro


@pytest.mark.parametrize(
    ("consultas", "esperado"),
    [
        ([("suplementos dietarios", "alto")], True),
        (
            [("suplementos dietarios", "medio")],
            True,
        ),  # la constante manda aunque el nivel diga medio
        ([("Suplementos Dietarios", "bajo")], True),  # otras mayúsculas
        (
            [("suplementos dietarios", None)],
            True,
        ),  # desconocida para la herramienta, pero en la constante
        ([("SUPLEMENTOS  DIETARIOS", "medio")], True),
        ([("apuestas", "alto")], True),
        ([("criptoactivos", "medio")], True),
        ([("venta de medicamentos", "bajo")], True),
        ([("talleres", "alto")], True),  # nivel «alto» para una categoría fuera de la constante
        ([("suplementos dietarios", "alto"), ("talleres", "bajo")], True),  # persistente
        ([("talleres", "bajo"), ("suplementos dietarios", "alto")], True),
        ([("talleres", "bajo")], False),
        ([("talleres", "medio"), ("panaderías", "bajo")], False),
        ([("algo raro", None)], False),
        ([], False),
    ],
)
def test_es_alto_riesgo(consultas, esperado):
    assert es_alto_riesgo(_libro_de_riesgo(*consultas)) is esperado


@pytest.mark.parametrize(
    ("consultas", "esperado"),
    [
        ([], False),  # sin consultas
        ([("talleres", "bajo")], True),
        ([("talleres", "medio")], True),
        ([("algo raro", None)], False),  # la última desconocida
        ([("talleres", "bajo"), ("algo raro", None)], False),  # conocida y luego desconocida
        ([("algo raro", None), ("talleres", "bajo")], True),  # desconocida y luego conocida
        ([("suplementos dietarios", "alto")], True),
        ([("suplementos dietarios", "alto"), ("algo raro", None)], True),  # alto riesgo determina
    ],
)
def test_categoria_determinada(consultas, esperado):
    assert categoria_determinada(_libro_de_riesgo(*consultas)) is esperado


def test_el_alto_riesgo_es_una_causa_de_escalamiento_solo_si_aplica():
    assert causas_vigentes(_libro_de_riesgo(("talleres", "bajo"))) == frozenset()
    alto = _libro_de_riesgo(("suplementos dietarios", "alto"))
    assert causas_vigentes(alto) == {CAUSA_ALTO_RIESGO}
    assert requiere_escalamiento(alto) is True
    alto.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))
    assert causas_vigentes(alto) == {CAUSA_ALTO_RIESGO, CAUSA_COINCIDENCIA_REPRESENTANTE}


def test_una_causa_de_alto_riesgo_posterior_al_escalamiento_exige_escalar_de_nuevo():
    libro = _libro_con("persona", escalamientos=[{CAUSA_COINCIDENCIA_REPRESENTANTE}])
    libro.consultas_riesgo.append(ConsultaRiesgo("apuestas", "alto"))
    assert escalamiento_cubre(libro) is False


# ------------------------------------------------------------------ evaluar_informe (regla I.3)


def _libro_del_caso_b(**cambios):
    """Bajo riesgo, categoría determinada y listas consultadas para comercio y representante."""
    libro = LibroReglas()
    libro.consultas_listas = [
        ConsultaListas("comercio", None, "CO-TV-0001", "sin_coincidencias"),
        ConsultaListas("persona", None, "PE-0001", "sin_coincidencias"),
    ]
    libro.consultas_riesgo = [ConsultaRiesgo("talleres", "bajo")]
    for campo, valor in cambios.items():
        setattr(libro, campo, valor)
    return libro


def test_el_caso_b_bajo_riesgo_sin_hallazgos_acepta_habilitar_sin_escalar():
    estado = _estado_de_informe(_libro_del_caso_b())
    assert evaluar_informe(estado, _informe("habilitar")) == []
    assert requiere_escalamiento(estado.libro) is False


def test_habilitar_a_un_comercio_de_alto_riesgo_se_rechaza_con_la_regla_i3():
    libro = _libro_del_caso_b(consultas_riesgo=[ConsultaRiesgo("suplementos dietarios", "alto")])
    rechazos = evaluar_informe(_estado_de_informe(libro), _informe("habilitar"))
    assert (
        "La categoría es de alto riesgo: la decisión es de un oficial de cumplimiento."
        in _textos(rechazos)
    )
    assert any(r.regla == "I.3" for r in rechazos)


def test_habilitar_con_la_categoria_no_determinada_se_rechaza():
    for consultas in ([], [ConsultaRiesgo("algo raro", None)]):
        libro = _libro_del_caso_b(consultas_riesgo=consultas)
        rechazos = evaluar_informe(_estado_de_informe(libro), _informe("habilitar"))
        assert "La categoría del caso no quedó determinada." in _textos(rechazos)
        assert any(r.regla == "I.3" for r in rechazos)


def test_habilitar_sin_consulta_de_listas_se_rechaza():
    libro = _libro_del_caso_b(consultas_listas=[])
    texto = _textos(evaluar_informe(_estado_de_informe(libro), _informe("habilitar")))
    assert (
        "Falta la consulta de listas restrictivas del comercio y de su representante legal."
        in texto
    )


def test_habilitar_sin_la_consulta_del_representante_se_rechaza_si_el_registro_lo_devolvio():
    libro = _libro_del_caso_b(
        consultas_listas=[ConsultaListas("comercio", None, "CO-TV-0001", "sin_coincidencias")]
    )
    assert evaluar_informe(_estado_de_informe(libro), _informe("habilitar"))


def test_sin_representante_en_el_registro_basta_la_consulta_del_comercio():
    estado = _estado_con_registro(
        Situacion.TERMINADO, {**comercio_alto_riesgo(), "representante_legal": None}
    )
    estado.libro = _libro_del_caso_b(
        consultas_listas=[ConsultaListas("comercio", "Tienda Verde SAS", None, "sin_coincidencias")]
    )
    assert evaluar_informe(estado, _informe("habilitar")) == []


@pytest.mark.parametrize(
    "consulta",
    [
        ConsultaListas("persona", None, "CO-TV-0001", "sin_coincidencias"),  # tipo incorrecto
        ConsultaListas("comercio", None, "CO-TA-0002", "sin_coincidencias"),  # otro comercio
        ConsultaListas("comercio", "Almacén Mirador SAS", None, "sin_coincidencias"),
    ],
)
def test_una_consulta_de_tipo_incorrecto_o_de_otro_comercio_no_cuenta(consulta):
    libro = _libro_del_caso_b(
        consultas_listas=[consulta, ConsultaListas("persona", None, "PE-0001", "sin_coincidencias")]
    )
    texto = _textos(evaluar_informe(_estado_de_informe(libro), _informe("habilitar")))
    assert "Falta la consulta de listas restrictivas" in texto


def test_las_consultas_del_comercio_anterior_no_cuentan_si_el_registro_cambia_de_comercio():
    estado = _estado_de_informe(_libro_del_caso_b())
    assert evaluar_informe(estado, _informe("habilitar")) == []
    estado.reiniciar_identificacion()
    estado.registrar_identificacion(
        respuesta_registro(comercio_del_registro("CO-TA-0002", "Taller Aurora SAS"))
    )
    texto = _textos(evaluar_informe(estado, _informe("habilitar")))
    assert "Falta la consulta de listas restrictivas" in texto


def test_habilitar_sin_comercio_identificado_se_rechaza():
    estado = _estado_con_registro(Situacion.TERMINADO, *comercios_parecidos())
    estado.libro = _libro_del_caso_b()
    assert "Falta la consulta de listas restrictivas" in _textos(
        evaluar_informe(estado, _informe("habilitar"))
    )


def test_alto_riesgo_sin_escalar_rechaza_tambien_no_habilitar():
    libro = _libro_del_caso_b(consultas_riesgo=[ConsultaRiesgo("suplementos dietarios", "alto")])
    texto = _textos(evaluar_informe(_estado_de_informe(libro), _informe("no_habilitar")))
    assert "aún no se ha escalado por: categoría de alto riesgo" in texto


def test_alto_riesgo_escalado_acepta_decide_cumplimiento_y_no_habilitar():
    libro = _libro_del_caso_b(
        consultas_riesgo=[ConsultaRiesgo("suplementos dietarios", "alto")],
        escalamientos=[Escalamiento(frozenset({CAUSA_ALTO_RIESGO}), CLAVE_TV)],
    )
    estado = _estado_de_informe(libro)
    assert evaluar_informe(estado, _informe("decide_cumplimiento")) == []
    assert evaluar_informe(estado, _informe("no_habilitar")) == []
    assert evaluar_informe(estado, _informe("habilitar"))  # escalar no habilita


def test_la_regla_de_un_rechazo_por_alto_riesgo_y_coincidencia_es_i2_i3():
    libro = _libro_del_caso_b(
        consultas_riesgo=[ConsultaRiesgo("suplementos dietarios", "alto")],
        coincidencias=[Coincidencia("persona", "L", "F", "2026-09-30")],
    )
    rechazos = evaluar_informe(_estado_de_informe(libro), _informe("habilitar"))
    reglas = {r.regla for r in rechazos}
    assert "I.2, I.3" in reglas  # el de falta de escalamiento lleva las dos reglas


# ------------------------------------------------------------------ evaluar_cierre (US4, FR-007)


def _estado_de_cierre(libro=None):
    """Como `_estado_de_informe`, con un informe vigente (#9, T037): estos tests del #7 siguen
    probando solo el escalamiento, con sus mismas igualdades exactas."""
    from due_diligence.informe import InformeRegistrado, huella_actual

    estado = _estado_de_informe(libro)
    estado.informes.append(
        InformeRegistrado("INF-0001", "no_habilitar", False, huella_actual(estado))
    )
    return estado


def test_sin_causas_el_caso_puede_cerrar():
    assert evaluar_cierre(_estado_de_cierre(_libro_del_caso_b())) is None


def test_con_una_coincidencia_sin_escalar_el_cierre_se_impide_nombrando_la_causa():
    motivo = evaluar_cierre(_estado_de_cierre(_libro_con("persona")))
    assert motivo == (
        "El caso requiere escalamiento a cumplimiento y aún no se ha escalado por: "
        "coincidencia del representante legal en listas restrictivas."
    )


def test_con_alto_riesgo_sin_escalar_el_cierre_se_impide_nombrando_la_causa():
    libro = _libro_del_caso_b(consultas_riesgo=[ConsultaRiesgo("apuestas", "alto")])
    assert "por: categoría de alto riesgo." in evaluar_cierre(_estado_de_cierre(libro))


def test_con_coincidencia_y_alto_riesgo_el_motivo_nombra_las_dos_causas():
    libro = _libro_con("comercio")
    libro.consultas_riesgo.append(ConsultaRiesgo("apuestas", "alto"))
    motivo = evaluar_cierre(_estado_de_cierre(libro))
    assert "coincidencia del comercio en listas restrictivas" in motivo
    assert "categoría de alto riesgo" in motivo


def test_con_el_escalamiento_cubierto_el_caso_puede_cerrar():
    libro = _libro_con("persona", escalamientos=[{CAUSA_COINCIDENCIA_REPRESENTANTE}])
    assert evaluar_cierre(_estado_de_cierre(libro)) is None


def test_una_causa_nueva_tras_escalar_vuelve_a_impedir_el_cierre():
    libro = _libro_con("persona", escalamientos=[{CAUSA_COINCIDENCIA_REPRESENTANTE}])
    libro.consultas_riesgo.append(ConsultaRiesgo("apuestas", "alto"))
    motivo = evaluar_cierre(_estado_de_cierre(libro))
    # Un escalamiento nuevo cubriría todas las causas vigentes, así que el motivo las nombra todas.
    assert "categoría de alto riesgo" in motivo
    assert "coincidencia del representante legal" in motivo


def test_el_motivo_del_cierre_no_repite_nombres_ni_identificadores():
    libro = _libro_con("comercio", "persona")
    motivo = evaluar_cierre(_estado_de_cierre(libro))
    for dato in ("CO-TV-0001", "Tienda Verde", "PE-0001", "Lucía", "coincidencia_comercio"):
        assert dato not in motivo


# ------------------------------------------------------------------ #9: el informe en el cierre


def test_falta_para_cerrar_distingue_escalamiento_e_informe():
    from due_diligence.reglas import falta_para_cerrar

    assert falta_para_cerrar(_estado_de_informe(_libro_del_caso_b())) == (False, True)
    assert falta_para_cerrar(_estado_de_cierre(_libro_del_caso_b())) == (False, False)
    assert falta_para_cerrar(_estado_de_informe(_libro_con("persona"))) == (True, True)


def test_sin_informe_el_motivo_es_fijo_y_con_escalamiento_pendiente_va_despues():
    from due_diligence.reglas import MOTIVO_SIN_INFORME, SUFIJO_LUEGO_INFORME

    assert evaluar_cierre(_estado_de_informe(_libro_del_caso_b())) == MOTIVO_SIN_INFORME
    motivo = evaluar_cierre(_estado_de_informe(_libro_con("persona")))
    assert motivo == (
        "El caso requiere escalamiento a cumplimiento y aún no se ha escalado por: "
        "coincidencia del representante legal en listas restrictivas." + SUFIJO_LUEGO_INFORME
    )


def test_varios_cambios_se_nombran_juntos_en_el_motivo():
    from due_diligence.estado import Situacion
    from due_diligence.frentes import Frente
    from due_diligence.simulacion import consulta

    estado = _estado_de_cierre(_libro_del_caso_b())
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.TERMINADO)
    respuesta = respuesta_registro(comercio_alto_riesgo())
    estado.agregar_consultas([consulta(Frente.REGISTRO, {}, respuesta)])  # ya se pueden comparar
    assert evaluar_cierre(estado) == (
        "El informe registrado ya no está vigente: cambió la cobertura y los conflictos después "
        "de registrarlo. Registra uno nuevo."
    )


# ------------------------------------------------------------------ #9: fallo de hook (US4, R9)


def _sellado(libro=None):
    estado = _estado_de_informe(libro or _libro_del_caso_b())
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"
    return estado


def test_el_sello_es_una_causa_de_escalamiento_con_su_etiqueta_y_sin_regla():
    from due_diligence.libro import CAUSA_FALLO_DE_HOOK
    from due_diligence.reglas import ETIQUETAS_CAUSA

    assert CAUSA_FALLO_DE_HOOK == "fallo_de_hook"
    estado = _sellado()
    assert causas_vigentes(estado.libro) == frozenset({CAUSA_FALLO_DE_HOOK})
    assert ETIQUETAS_CAUSA[CAUSA_FALLO_DE_HOOK] == "fallo de un hook de verificación"
    assert reglas_de({CAUSA_FALLO_DE_HOOK}) is None
    assert causas_vigentes(_estado_de_informe(_libro_del_caso_b()).libro) == frozenset()


def test_el_informe_minimo_solo_admite_decide_cumplimiento_y_tras_escalar():
    from due_diligence.libro import CAUSA_FALLO_DE_HOOK
    from due_diligence.reglas import MOTIVO_SOLO_OFICIAL, evaluar_informe_minimo

    assert MOTIVO_SOLO_OFICIAL == (
        "Tras un fallo de hook solo decide el oficial: la recomendación debe ser "
        "decide_cumplimiento."
    )
    sin_escalar = _sellado()
    escalar = Rechazo(motivo_de_escalar({CAUSA_FALLO_DE_HOOK}), None)
    assert evaluar_informe_minimo(sin_escalar, _informe("decide_cumplimiento")) == [escalar]
    for recomendacion in ("habilitar", "no_habilitar", "aprobar"):
        assert evaluar_informe_minimo(sin_escalar, _informe(recomendacion)) == [
            Rechazo(MOTIVO_SOLO_OFICIAL, None),
            escalar,
        ]
    escalado = _sellado(
        _libro_del_caso_b(escalamientos=[Escalamiento(frozenset({CAUSA_FALLO_DE_HOOK}), CLAVE_TV)])
    )
    assert evaluar_informe_minimo(escalado, _informe("decide_cumplimiento")) == []
    assert evaluar_informe_minimo(escalado, _informe("no_habilitar")) == [
        Rechazo(MOTIVO_SOLO_OFICIAL, None)
    ]
    assert evaluar_informe_minimo(escalado, "no es un objeto") == [
        Rechazo(MOTIVO_ENTRADA_INFORME, None)
    ]


def test_con_el_sello_y_sin_otras_causas_el_cierre_exige_escalar():
    # Cambio respecto al #7 (R9): un caso sellado sin otras causas ya no puede cerrarse sin escalar.
    from due_diligence.reglas import falta_para_cerrar

    estado = _sellado()
    assert falta_para_cerrar(estado)[0] is True
    assert evaluar_cierre(estado).startswith(
        "El caso requiere escalamiento a cumplimiento y aún no se ha escalado por: "
        "fallo de un hook de verificación."
    )


# ------------------------------------------------------------ #10: esperas del analista (T010)

COINCIDENCIAS_PARECIDAS = ("CO-AM-0004", "CO-AM-0005")


def _registro_caido():
    estado = _estado_con_registro(Situacion.NO_TERMINADO, identificar=False)
    estado.errores[Frente.REGISTRO] = {"causa": "terminacion_anomala", "reintentable": False}
    return estado


def _con_categoria_bloqueada(estado):
    estado.categoria_bloqueada = True
    return estado


def test_varias_coincidencias_es_la_espera_del_identificador():
    from due_diligence.reglas import MOTIVO_ESPERA_IDENTIFICADOR, Espera, espera_del_analista

    estado = _estado_con_registro(Situacion.TERMINADO, *comercios_parecidos())
    assert espera_del_analista(estado) == Espera("identificador", MOTIVO_ESPERA_IDENTIFICADOR)


def test_ninguna_coincidencia_es_la_espera_del_nombre():
    from due_diligence.reglas import MOTIVO_ESPERA_NOMBRE, Espera, espera_del_analista

    estado = _estado_con_registro(Situacion.TERMINADO)  # respuesta sin comercios
    assert espera_del_analista(estado) == Espera("nombre", MOTIVO_ESPERA_NOMBRE)


def test_d3_del_9_unica_e_invalida_no_son_espera():
    from due_diligence.reglas import espera_del_analista

    assert espera_del_analista(_con_comercio()) is None
    otra = {**comercio_alto_riesgo(), "nombre": "Tienda Verde Ltda"}
    contradictoria = _estado_con_registro(Situacion.TERMINADO, identificar=False)
    contradictoria.registrar_identificacion(
        {
            "resultado": "coincidencias",
            "hechos": [
                {"contenido": comercio_alto_riesgo(), "metadatos": {}},
                {"contenido": otra, "metadatos": {}},
            ],
            "coincidencias": ["CO-TV-0001"],
        }
    )
    assert contradictoria.clase_identificacion == "contradictoria"
    assert espera_del_analista(contradictoria) is None
    invalida = _estado_con_registro(Situacion.TERMINADO, identificar=False)
    invalida.registrar_identificacion({"hola": 1})
    assert invalida.clase_identificacion == "invalida" and espera_del_analista(invalida) is None


@pytest.mark.parametrize(
    "situacion", [Situacion.SIN_INICIAR, Situacion.EN_CURSO, Situacion.RECHAZADO]
)
def test_un_registro_que_no_termino_no_es_espera(situacion):
    from due_diligence.reglas import espera_del_analista

    estado = _estado_con_registro(situacion, identificar=False)
    assert espera_del_analista(estado) is None


def test_el_registro_caido_por_si_solo_no_es_espera():
    from due_diligence.reglas import espera_del_analista

    assert espera_del_analista(_registro_caido()) is None


@pytest.mark.parametrize("estado_base", ["identificado", "caido", "sin_delegar"])
def test_la_categoria_bloqueada_sin_resultado_es_espera_con_cualquier_registro(estado_base):
    from due_diligence.reglas import MOTIVO_ESPERA_CATEGORIA, Espera, espera_del_analista

    estado = {
        "identificado": _con_comercio,
        "caido": _registro_caido,
        "sin_delegar": lambda: _estado_con_registro(Situacion.SIN_INICIAR, identificar=False),
    }[estado_base]()
    _con_categoria_bloqueada(estado)
    assert espera_del_analista(estado) == Espera("categoria", MOTIVO_ESPERA_CATEGORIA)


@pytest.mark.parametrize("nivel", ["bajo", None])
def test_con_un_resultado_de_categoria_no_hay_espera_de_categoria(nivel):
    from due_diligence.reglas import espera_del_analista

    estado = _con_categoria_bloqueada(_con_comercio())
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("ropa y accesorios", nivel))
    assert espera_del_analista(estado) is None


def test_con_varias_coincidencias_y_la_categoria_bloqueada_prevalece_el_identificador():
    from due_diligence.reglas import espera_del_analista

    estado = _con_categoria_bloqueada(
        _estado_con_registro(Situacion.TERMINADO, *comercios_parecidos())
    )
    assert espera_del_analista(estado).clase == "identificador"


def test_los_motivos_de_espera_no_repiten_las_coincidencias():
    from due_diligence.reglas import (
        MOTIVO_ESPERA_CATEGORIA,
        MOTIVO_ESPERA_IDENTIFICADOR,
        MOTIVO_ESPERA_NOMBRE,
        espera_del_analista,
    )

    estado = _estado_con_registro(Situacion.TERMINADO, *comercios_parecidos())
    for texto in (
        espera_del_analista(estado).motivo,
        MOTIVO_ESPERA_IDENTIFICADOR,
        MOTIVO_ESPERA_NOMBRE,
        MOTIVO_ESPERA_CATEGORIA,
    ):
        assert not any(c in texto for c in COINCIDENCIAS_PARECIDAS)
        assert "Almacén Mirador" not in texto


def test_el_motivo_sin_comercio_lee_la_clase_y_no_el_texto(monkeypatch):
    from due_diligence.reglas import MOTIVO_VARIAS_COINCIDENCIAS, _motivo_sin_comercio

    estado = _estado_con_registro(Situacion.TERMINADO, *comercios_parecidos())
    # Un motivo del registro con otro texto: la clase sigue diciendo `varias`.
    monkeypatch.setattr(type(estado), "motivo_comercio", property(lambda self: "otro texto"))
    assert _motivo_sin_comercio(estado) == MOTIVO_VARIAS_COINCIDENCIAS


# ------------------------------------------- #10: la categoría de los mensajes del analista (T020)

SOLICITUD_DEL_EJEMPLO = (
    "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. Quieren "
    "procesar ventas en línea de suplementos dietarios y estiman unos $80.000.000 mensuales. "
    "¿Lo podemos habilitar esta semana?"
)


@pytest.mark.parametrize(
    ("categoria", "mensajes", "aparece"),
    [
        ("suplementos dietarios", [SOLICITUD_DEL_EJEMPLO], True),
        ("Suplementos  Dietarios", [SOLICITUD_DEL_EJEMPLO], True),  # mayúsculas y espacios
        ("ropa y accesorios", [SOLICITUD_DEL_EJEMPLO], False),
        ("ropa", ["Vende uniformes para la tropa."], False),  # límites de palabra
        ("suplementos dietarios", ["Vende un suplemento dietario."], False),  # plural: riesgo
        ("educación en línea", ["Ofrece educacion en linea."], True),  # tildes
        ("talleres", ["Primer mensaje.", "La categoría es talleres."], True),  # mensaje posterior
        ("talleres", [], False),
        ("", [SOLICITUD_DEL_EJEMPLO], False),
    ],
)
def test_la_categoria_tiene_que_aparecer_en_un_mensaje_del_analista(categoria, mensajes, aparece):
    from due_diligence.reglas import categoria_en_mensajes

    assert categoria_en_mensajes(categoria, mensajes) is aparece


def test_el_motivo_de_la_categoria_no_repite_la_categoria_ni_el_comercio():
    from due_diligence.reglas import MOTIVO_CATEGORIA_NO_DEL_ANALISTA

    assert MOTIVO_CATEGORIA_NO_DEL_ANALISTA == (
        "La categoría no aparece en los mensajes del analista: use la que dio o pregúntesela."
    )


# ------------------------------------------- #10: recorrido de las esperas de SC-004 (T023)

ESTADOS_DEL_REGISTRO = ("sin_delegar", "en_curso", "varias", "ninguna", "identificado", "caido")
ESTADOS_DE_LA_CATEGORIA = ("con_resultado", "sin_delegar", "bloqueada")


def _estado_del_registro(nombre):
    if nombre == "sin_delegar":
        return _estado_con_registro(Situacion.SIN_INICIAR, identificar=False)
    if nombre == "en_curso":
        return _estado_con_registro(Situacion.EN_CURSO, identificar=False)
    if nombre == "varias":
        return _estado_con_registro(Situacion.TERMINADO, *comercios_parecidos())
    if nombre == "ninguna":
        return _estado_con_registro(Situacion.TERMINADO)
    if nombre == "identificado":
        return _con_comercio()
    return _registro_caido()


@pytest.mark.parametrize("con_causas", [False, True])
@pytest.mark.parametrize("categoria", ESTADOS_DE_LA_CATEGORIA)
@pytest.mark.parametrize("registro", ESTADOS_DEL_REGISTRO)
def test_sc004_la_espera_solo_existe_en_las_tres_situaciones(registro, categoria, con_causas):
    from due_diligence.reglas import espera_del_analista

    estado = _estado_del_registro(registro)
    if categoria == "con_resultado":
        estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))
    elif categoria == "bloqueada":
        estado.categoria_bloqueada = True
    if con_causas:
        estado.libro.coincidencias.append(Coincidencia("persona", "Lista A", "F", "2026-09-30"))
    espera = espera_del_analista(estado)
    if registro == "varias":
        assert espera.clase == "identificador"
    elif registro == "ninguna":
        assert espera.clase == "nombre"
    elif categoria == "bloqueada":
        # Hallazgo A1: también con el registro caído, que por sí solo no es una espera.
        assert espera.clase == "categoria"
    else:
        assert espera is None


def _contradictoria():
    estado = _estado_con_registro(Situacion.TERMINADO, identificar=False)
    otra = {**comercio_alto_riesgo(), "nombre": "Tienda Verde Ltda"}
    estado.registrar_identificacion(
        {
            "resultado": "coincidencias",
            "hechos": [
                {"contenido": comercio_alto_riesgo(), "metadatos": {}},
                {"contenido": otra, "metadatos": {}},
            ],
            "coincidencias": ["CO-TV-0001"],
        }
    )
    return estado


def test_sc004_d3_del_9_no_es_espera_salvo_por_la_categoria_bloqueada():
    from due_diligence.reglas import espera_del_analista

    estado = _contradictoria()
    assert espera_del_analista(estado) is None
    estado.categoria_bloqueada = True
    assert espera_del_analista(estado).clase == "categoria"


@pytest.mark.parametrize("registro", ESTADOS_DEL_REGISTRO)
def test_sc004_la_categoria_bloqueada_con_un_resultado_ya_no_es_espera(registro):
    # La condición es «bloqueada **y sin resultado**»: un resultado de categoría (por ejemplo, de
    # una delegación anterior al bloqueo) la quita. Sin este caso, la mutación que olvida el
    # resultado sobrevivía al recorrido.
    from due_diligence.reglas import espera_del_analista

    estado = _estado_del_registro(registro)
    estado.categoria_bloqueada = True
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))
    espera = espera_del_analista(estado)
    esperada = {"varias": "identificador", "ninguna": "nombre"}.get(registro)
    assert (espera.clase if espera else None) == esperada


# ------------------------------------------- #10: consulta del comercio identificado (T025)

NORTE = {"identificador": "CO-AM-0005", "nombre": "Almacén Mirador Norte SAS"}


@pytest.mark.parametrize(
    ("argumentos", "es_suya"),
    [
        ({"identificador": "CO-AM-0005"}, True),
        ({"identificador": "co-am-0005"}, True),  # el identificador no distingue mayúsculas
        ({"nombre": "ALMACEN MIRADOR NORTE S.A.S."}, True),  # la normalización de siempre
        ({"nombre": "Almacén Mirador SAS"}, False),  # el nombre ambiguo del primer turno
        ({"identificador": "CO-AM-0004"}, False),
        ({"identificador": "CO-AM-0005", "nombre": "Almacén Mirador SAS"}, False),
        ({}, False),
        (None, False),
        ({"nombre": ""}, False),
    ],
)
def test_la_consulta_es_del_comercio_solo_si_su_dato_es_el_del_comercio(argumentos, es_suya):
    from due_diligence.reglas import consulta_del_comercio

    assert consulta_del_comercio(argumentos, NORTE) is es_suya


# ------------------------------------------- #10: escalamiento con criterio (T039, R5, R8)


def _bajo_riesgo_comprobado():
    """El caso (b) completo: cuatro frentes, listas limpias, bajo, sin menciones ni conflictos."""
    from due_diligence.estado import ResultadoFrente
    from due_diligence.simulacion import (
        comercio_bajo_riesgo,
        consulta,
        respuesta_del_contrato,
        terminacion_normal,
    )

    estado = _estado_con_registro(Situacion.TERMINADO, comercio_bajo_riesgo())
    # La consulta del registro que identificó al comercio, como en producción: sin ella, los
    # conflictos quedan «sin consulta» y no «sin conflictos».
    estado.agregar_consultas(
        [
            consulta(
                Frente.REGISTRO,
                {"identificador": "CO-TA-0002"},
                respuesta_registro(comercio_bajo_riesgo()),
            )
        ]
    )
    for frente in (Frente.NOTICIAS, Frente.CATEGORIA, Frente.LISTAS):
        estado.cambiar_situacion(frente, Situacion.EN_CURSO)
        estado.cambiar_situacion(frente, Situacion.TERMINADO)
    noticias = respuesta_del_contrato("sin_coincidencias", fuente="Noticias Ficticias")
    estado.guardar_resultado(
        ResultadoFrente(
            Frente.NOTICIAS,
            [consulta(Frente.NOTICIAS, {"identificador": "CO-TA-0002"}, noticias)],
            "",
            terminacion_normal(),
            "",
        )
    )
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("talleres", "bajo"))
    estado.libro.consultas_listas = [
        ConsultaListas("comercio", None, "CO-TA-0002", "sin_coincidencias"),
        ConsultaListas("persona", None, "PE-0002", "sin_coincidencias"),
    ]
    return estado


def test_el_bajo_riesgo_sin_hallazgos_comprobado():
    from due_diligence.reglas import bajo_riesgo_sin_hallazgos

    assert bajo_riesgo_sin_hallazgos(_bajo_riesgo_comprobado()) is True


def _con_mencion(estado):
    from due_diligence.estado import ResultadoFrente
    from due_diligence.simulacion import consulta, respuesta_del_contrato, terminacion_normal

    mencion = respuesta_del_contrato("coincidencias", [{"titular": "x"}], fuente="Noticias")
    estado.guardar_resultado(
        ResultadoFrente(
            Frente.NOTICIAS,
            [consulta(Frente.NOTICIAS, {"identificador": "CO-TA-0002"}, mencion)],
            "",
            terminacion_normal(),
            "",
        )
    )


def _con_conflicto(estado):
    from due_diligence.simulacion import comercio_bajo_riesgo, consulta

    otra = {**comercio_bajo_riesgo(), "fecha_constitucion": "2001-01-01"}
    respuesta = {
        "resultado": "coincidencias",
        "hechos": [
            {
                "contenido": comercio_bajo_riesgo(),
                "metadatos": {"fuente": "A", "fecha": "2026-09-30"},
            },
            {"contenido": otra, "metadatos": {"fuente": "B", "fecha": "2026-09-28"}},
        ],
        "coincidencias": ["CO-TA-0002"],
        "metadatos": {"fuentes": ["A", "B"], "fecha": "2026-09-30"},
    }
    estado.reiniciar_identificacion()
    estado.registrar_identificacion(respuesta)
    estado.agregar_consultas(
        [consulta(Frente.REGISTRO, {"identificador": "CO-TA-0002"}, respuesta)]
    )


def _noticias_caido(estado):
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.NOTICIAS, Situacion.NO_TERMINADO, "caído")
    estado.errores[Frente.NOTICIAS] = {"causa": "error_de_fuente", "reintentable": False}


def _registro_caido_en(estado):
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.NO_TERMINADO, "caído")
    estado.errores[Frente.REGISTRO] = {"causa": "terminacion_anomala", "reintentable": False}


def _categoria_desconocida(estado):
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("otra", None))


def _coincidencia(estado):
    estado.libro.coincidencias.append(Coincidencia("persona", "L", "F", "2026-09-30"))


def _alto_riesgo(estado):
    estado.libro.consultas_riesgo.append(ConsultaRiesgo("apuestas", "alto"))


def _sello(estado):
    estado.libro.fallo_de_hook = "PostToolUse: RuntimeError"


@pytest.mark.parametrize(
    "romper",
    [
        _con_mencion,  # US1-7
        _con_conflicto,  # US1-8
        _noticias_caido,
        _categoria_desconocida,
        _registro_caido_en,
        _coincidencia,
        _alto_riesgo,
        _sello,
    ],
)
def test_cada_condicion_por_separado_quita_el_bajo_riesgo_comprobado(romper):
    from due_diligence.reglas import bajo_riesgo_sin_hallazgos

    estado = _bajo_riesgo_comprobado()
    romper(estado)
    assert bajo_riesgo_sin_hallazgos(estado) is False


def test_el_escalamiento_de_otro_comercio_no_cubre_al_actual():
    clave_0004 = ("CO-AM-0004", "Almacén Mirador SAS", True)
    clave_0005 = ("CO-AM-0005", "Almacén Mirador Norte SAS", True)
    libro = _libro_con("persona")
    libro.escalamientos = [Escalamiento(frozenset({CAUSA_COINCIDENCIA_REPRESENTANTE}), clave_0004)]
    assert escalamiento_cubre(libro, clave_0004) is True
    assert escalamiento_cubre(libro, clave_0005) is False  # las causas coinciden, el comercio no
    assert escalamiento_cubre(libro) is True  # el libro solo: cualquier comercio, como en el #7


def test_escalado_para_el_comercio_aunque_no_haya_causas():
    from due_diligence.reglas import escalado_para_el_comercio

    estado = _estado_de_informe()
    assert escalado_para_el_comercio(estado) is False
    estado.libro.escalamientos.append(Escalamiento(frozenset(), CLAVE_TV))
    assert escalado_para_el_comercio(estado) is True
    otro = _estado_de_informe()
    otro.libro.escalamientos.append(Escalamiento(frozenset(), ("CO-AM-0004", "x", True)))
    assert escalado_para_el_comercio(otro) is False


def test_decide_cumplimiento_sin_escalamiento_del_comercio_actual_se_rechaza():
    from due_diligence.reglas import MOTIVO_DECIDE_SIN_ESCALAR

    estado = _estado_de_informe(_libro_del_caso_b())
    assert evaluar_informe(estado, _informe("decide_cumplimiento")) == [
        Rechazo(MOTIVO_DECIDE_SIN_ESCALAR, "V")
    ]
    assert MOTIVO_DECIDE_SIN_ESCALAR == (
        "decide_cumplimiento exige escalar antes: el oficial solo decide un caso que le llegó "
        "escalado."
    )
    estado.libro.escalamientos.append(Escalamiento(frozenset(), ("CO-AM-0004", "x", True)))
    assert evaluar_informe(estado, _informe("decide_cumplimiento")) == [
        Rechazo(MOTIVO_DECIDE_SIN_ESCALAR, "V")
    ]
    estado.libro.escalamientos.append(Escalamiento(frozenset(), CLAVE_TV))
    assert evaluar_informe(estado, _informe("decide_cumplimiento")) == []
    for recomendacion in ("no_habilitar", "habilitar"):  # no cambian
        assert Rechazo(MOTIVO_DECIDE_SIN_ESCALAR, "V") not in evaluar_informe(
            estado, _informe(recomendacion)
        )


def test_con_causas_sin_escalar_decide_cumplimiento_da_solo_el_motivo_de_escalar():
    from due_diligence.reglas import MOTIVO_DECIDE_SIN_ESCALAR

    estado = _estado_de_informe(_libro_con("persona"))
    textos = [r.texto for r in evaluar_informe(estado, _informe("decide_cumplimiento"))]
    assert textos == [motivo_de_escalar({CAUSA_COINCIDENCIA_REPRESENTANTE})]
    assert MOTIVO_DECIDE_SIN_ESCALAR not in textos


def test_evaluar_escalamiento_en_la_espera_y_con_el_bajo_riesgo_comprobado():
    from due_diligence.reglas import (
        MOTIVO_ESPERA_IDENTIFICADOR,
        MOTIVO_ESPERA_NOMBRE,
        MOTIVO_SIN_CAUSA,
        evaluar_escalamiento,
    )

    varias = _estado_con_registro(Situacion.TERMINADO, *comercios_parecidos())
    assert evaluar_escalamiento(varias) == [Rechazo(MOTIVO_ESPERA_IDENTIFICADOR, "V")]
    ninguna = _estado_con_registro(Situacion.TERMINADO)
    assert evaluar_escalamiento(ninguna) == [Rechazo(MOTIVO_ESPERA_NOMBRE, "V")]
    assert evaluar_escalamiento(_bajo_riesgo_comprobado()) == [Rechazo(MOTIVO_SIN_CAUSA, "V")]
    assert MOTIVO_SIN_CAUSA == (
        "El caso no tiene ninguna causa de escalamiento: es de bajo riesgo y no tiene hallazgos. "
        "No se escala; registre el informe."
    )
    categoria = _con_comercio()
    categoria.categoria_bloqueada = True
    assert evaluar_escalamiento(categoria) == []  # la espera de la categoría no lo impide
    # D3 del plan: el alto riesgo en la espera del identificador tampoco escala sin identificar.
    varias.libro.consultas_riesgo.append(ConsultaRiesgo("apuestas", "alto"))
    assert evaluar_escalamiento(varias) == [Rechazo(MOTIVO_ESPERA_IDENTIFICADOR, "V")]
