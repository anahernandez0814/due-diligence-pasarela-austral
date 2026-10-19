"""Los siete casos obligatorios (a)–(g) de punta a punta, con el modelo real (#12, FR-001, FR-002).

Marcados `e2e` y excluidos de `uv run pytest`; se piden con `uv run pytest -m e2e -rs` y consumen
API. Sin la clave, cada uno se omite con el motivo: omitido no es «pasó». Los ejecuta, en paralelo,
la fixture de `conftest.py`.

Cada test solo ve la `Observacion` de su caso: eventos, consultas, libro de reglas, registros de
la pasarela y estado calculado por el código. Ninguna verificación lee el texto del modelo
(FR-003); `test_observacion.py` lo comprueba sin llamar al modelo.
"""

import pytest

from due_diligence.observacion import (
    CAUSA_ALTO_RIESGO,
    CAUSA_COINCIDENCIA_REPRESENTANTE,
    MOTIVO_ESPERA_IDENTIFICADOR,
    TIPO_BLOQUEO_REGLA,
    mismo_identificador,
    mismo_nombre,
)

pytestmark = pytest.mark.e2e

ALMACEN = "CO-AM-0004"
ALMACEN_NORTE = ("CO-AM-0005", "Almacén Mirador Norte SAS")
REPRESENTANTE_NORTE = ("PE-0005", "Gaspar Linares Ibáñez")  # el de CO-AM-0005


def _comunes(observado):
    """Lo que vale para todo caso: registros coherentes y listas solo tras identificar (US1-8).

    Solo cuentan las consultas válidas: una denegada o no válida no consultó ninguna fuente.
    """
    assert observado.registros_coherentes, "el libro y los registros de la pasarela no cuadran"
    validas = [c for c in observado.consultas if c.valida]
    listas = [i for i, c in enumerate(validas) if c.frente == "listas"]
    if listas:
        unicas = [
            i
            for i, c in enumerate(validas)
            if c.frente == "registro" and c.clase_registro == "unica"
        ]
        assert unicas, "se consultaron listas sin una identificación única en el registro"
        assert listas[0] > unicas[0], "se consultaron listas antes de identificar"


def test_caso_a_alto_riesgo(caso_e2e):
    (observado,) = caso_e2e("a")
    _comunes(observado)
    assert [e for e in observado.escalamientos if CAUSA_ALTO_RIESGO in e.causas], (
        "falta el escalamiento con la causa de alto riesgo"
    )
    assert "decide_cumplimiento" in [i.recomendacion for i in observado.informes], (
        "falta el informe al oficial"
    )
    assert "habilitar" not in [i.recomendacion for i in observado.informes], (
        "se recomendó habilitar (I.3)"
    )


def test_caso_b_bajo_riesgo(caso_e2e):
    (observado,) = caso_e2e("b")
    _comunes(observado)
    assert "habilitar" in [i.recomendacion for i in observado.informes], (
        "falta el informe con habilitar"
    )
    assert observado.escalamientos == (), "un bajo riesgo sin hallazgos no se escala (V)"
    assert [f for f, c in observado.cobertura.items() if not c.cubierto] == []
    assert observado.completo is True


def test_caso_c_representante(caso_e2e):
    (observado,) = caso_e2e("c")
    _comunes(observado)
    assert [e for e in observado.escalamientos if CAUSA_COINCIDENCIA_REPRESENTANTE in e.causas], (
        "falta el escalamiento por la coincidencia del representante legal"
    )
    assert "habilitar" not in [i.recomendacion for i in observado.informes], (
        "se recomendó habilitar (I.2)"
    )


def test_caso_d_dos_turnos(caso_e2e):
    primero, segundo = caso_e2e("d")
    # Turno 1: varias coincidencias, se espera el identificador y no se consultan listas.
    _comunes(primero)
    assert primero.espera is not None, "el primer turno no quedó esperando al analista"
    assert primero.espera.clase == "identificador"
    assert primero.espera.motivo == MOTIVO_ESPERA_IDENTIFICADOR
    assert [c for c in primero.consultas if c.clase_registro == "varias"], (
        "el registro no devolvió varias coincidencias"
    )
    assert primero.consultas_listas == (), "se consultaron listas antes del identificador"
    assert primero.informes == () and primero.escalamientos == ()
    # Turno 2, con «CO-AM-0004»: listas solo ahora, con los datos de ese comercio.
    _comunes(segundo)
    assert segundo.comercio is not None and segundo.comercio.verificado
    assert mismo_identificador(segundo.comercio.identificador, ALMACEN)
    del_comercio = [c for c in segundo.consultas_listas if c.tipo == "comercio"]
    assert del_comercio, "en el segundo turno no se consultaron listas del comercio"
    for consulta in del_comercio:
        assert (
            consulta.identificador is not None
            and mismo_identificador(consulta.identificador, ALMACEN)
        ) or (
            consulta.nombre is not None and mismo_nombre(consulta.nombre, segundo.comercio.nombre)
        ), "una consulta de listas no es la de CO-AM-0004"
        assert not (
            consulta.identificador is not None
            and mismo_identificador(consulta.identificador, ALMACEN_NORTE[0])
        )
        assert not (consulta.nombre is not None and mismo_nombre(consulta.nombre, ALMACEN_NORTE[1]))
    for consulta in (c for c in segundo.consultas_listas if c.tipo == "persona"):
        assert not (
            consulta.identificador is not None
            and mismo_identificador(consulta.identificador, REPRESENTANTE_NORTE[0])
        ), "una consulta de listas es del representante legal de CO-AM-0005"
        assert not (
            consulta.nombre is not None and mismo_nombre(consulta.nombre, REPRESENTANTE_NORTE[1])
        ), "una consulta de listas es del representante legal de CO-AM-0005"
    assert len(segundo.informes) >= 1, "el segundo turno no registró el informe"


def test_caso_e_listas_sin_identificar(caso_e2e):
    (observado,) = caso_e2e("e")
    _comunes(observado)
    assert [
        e
        for e in observado.eventos
        if e.tipo == TIPO_BLOQUEO_REGLA and e.regla == "I.1" and e.frente == "listas"
    ], "no hubo un bloqueo de la regla I.1 sobre listas"
    assert observado.consultas_listas == (), "una consulta de listas llegó a ejecutarse"


def test_caso_f_noticias_caido(caso_e2e):
    (observado,) = caso_e2e("f")
    _comunes(observado)
    assert observado.informes, "con noticias caído, el informe se entrega igual (I.5)"
    ultimo = observado.informes[-1]
    assert observado.cobertura["noticias"].cubierto is False
    assert ultimo.cobertura == observado.cobertura_lineas, (
        "el informe no declara la cobertura calculada, con noticias sin cubrir"
    )
    assert observado.completo is False, "un caso sin noticias no puede figurar como completo"


def test_caso_g_fechas_distintas(caso_e2e):
    (observado,) = caso_e2e("g")
    _comunes(observado)
    assert observado.informes, "falta el informe"
    fechas = [c for c in observado.informes[-1].conflictos if c.campo == "fecha_constitucion"]
    assert len(fechas) == 1, "el informe no muestra el conflicto de fecha de constitución"
    (conflicto,) = fechas
    valores = {valor for valor, _ in conflicto.valores}
    fuentes = {fuente for _, fuente in conflicto.valores}
    assert len(valores) == 2 and len(fuentes) == 2, "faltan las dos fechas con sus dos fuentes"
