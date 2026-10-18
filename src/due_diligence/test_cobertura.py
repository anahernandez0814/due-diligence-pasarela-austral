"""Tests de la cobertura calculada por el código (#8, R5, contrato `cobertura.md`; FR-010,
FR-012, US4-1 a US4-5, SC-003). Puros: ninguno llama al modelo ni a la delegación."""

import itertools

import pytest

from due_diligence.cobertura import CoberturaCaso, CoberturaFrente, calcular_cobertura
from due_diligence.ejecutor import TIPO_BLOQUEADO_POR_HOOK
from due_diligence.estado import Causa, EstadoCaso, Situacion
from due_diligence.frentes import Frente
from due_diligence.simulacion import comercio_del_registro, respuesta_registro

NOMBRE = "Taller Aurora SAS"
IDENTIFICADOR = "CO-TA-0002"
COMBINACIONES = list(itertools.product(list(Situacion), repeat=len(Frente)))


def _estado(situaciones, errores=None, motivos=None):
    """Un estado con la situación de cada frente forzada (solo en los tests)."""
    estado = EstadoCaso(f"Due diligence de {NOMBRE}, identificador {IDENTIFICADOR}.")
    for frente, situacion in zip(Frente, situaciones, strict=True):
        estado._situaciones[frente] = situacion
        estado._motivos[frente] = (motivos or {}).get(frente, f"motivo con {IDENTIFICADOR}")
    estado.errores.update(errores or {})
    return estado


def _error(causa, intento=1, tipos=()):
    return {
        "causa": causa.value,
        "intento": intento,
        "obtenido": {"errores": [{"error": True, "tipo": t} for t in tipos]},
    }


# ------------------------------------------------------------------ las 625 combinaciones


def test_hay_625_combinaciones():
    assert len(COMBINACIONES) == 5**4 == 625


@pytest.mark.parametrize("situaciones", COMBINACIONES)
def test_la_cobertura_es_completa_solo_con_los_cuatro_terminados(situaciones):
    cobertura = calcular_cobertura(_estado(situaciones))
    todos = all(s is Situacion.TERMINADO for s in situaciones)
    assert cobertura.completa is todos
    assert list(cobertura.frentes) == list(Frente)
    for frente, situacion in zip(Frente, situaciones, strict=True):
        del_frente = cobertura.frentes[frente]
        assert del_frente.cubierto is (situacion is Situacion.TERMINADO)
        if not del_frente.cubierto:
            assert del_frente.motivo  # cada frente no cubierto trae su motivo
        lineas = cobertura.lineas()
        linea = lineas[1 + list(Frente).index(frente)]
        assert linea.startswith(f"{frente.value}: ")
        assert ("no cubierto" in linea) is not del_frente.cubierto


# ------------------------------------------------------------------ motivos (US4-1 a US4-4)


def test_un_frente_sin_iniciar_figura_como_no_delegado():
    cobertura = calcular_cobertura(_estado([Situacion.TERMINADO] * 3 + [Situacion.SIN_INICIAR]))
    categoria = cobertura.frentes[Frente.CATEGORIA]
    assert not categoria.cubierto and "no se delegó" in categoria.motivo


def test_un_frente_en_curso_figura_como_no_cubierto():
    cobertura = calcular_cobertura(
        _estado([Situacion.TERMINADO, Situacion.EN_CURSO, Situacion.TERMINADO, Situacion.TERMINADO])
    )
    assert "seguía en curso" in cobertura.frentes[Frente.LISTAS].motivo


def test_un_error_de_la_fuente_lleva_su_causa_su_tipo_y_sus_intentos():
    situaciones = [
        Situacion.TERMINADO,
        Situacion.TERMINADO,
        Situacion.NO_TERMINADO,
        Situacion.TERMINADO,
    ]
    errores = {Frente.NOTICIAS: _error(Causa.ERROR_DE_FUENTE, 2, ["servicio_no_disponible"])}
    cobertura = calcular_cobertura(_estado(situaciones, errores))
    noticias = cobertura.frentes[Frente.NOTICIAS]
    assert noticias.causa is Causa.ERROR_DE_FUENTE and noticias.intentos == 2
    assert "servicio_no_disponible" in noticias.motivo
    assert cobertura.lineas()[3] == (
        "noticias: no cubierto; error de la fuente (servicio_no_disponible); 2 intentos."
    )


def test_un_bloqueo_de_hook_no_figura_entre_los_tipos_de_error_de_la_fuente():
    situaciones = [
        Situacion.TERMINADO,
        Situacion.NO_TERMINADO,
        Situacion.TERMINADO,
        Situacion.TERMINADO,
    ]
    tipos = ["servicio_no_disponible", TIPO_BLOQUEADO_POR_HOOK]
    errores = {Frente.LISTAS: _error(Causa.ERROR_DE_FUENTE, 1, tipos)}
    listas = calcular_cobertura(_estado(situaciones, errores)).frentes[Frente.LISTAS]
    assert listas.motivo == "error de la fuente (servicio_no_disponible)"


def test_listas_rechazada_figura_como_no_cubierta_con_el_motivo_del_rechazo():
    situaciones = [
        Situacion.NO_TERMINADO,
        Situacion.RECHAZADO,
        Situacion.TERMINADO,
        Situacion.TERMINADO,
    ]
    errores = {Frente.LISTAS: _error(Causa.RECHAZADO, 0)}
    listas = calcular_cobertura(_estado(situaciones, errores)).frentes[Frente.LISTAS]
    assert not listas.cubierto and listas.causa is Causa.RECHAZADO
    assert "rechaz" in listas.motivo


def test_listas_invalidada_figura_como_no_cubierta():
    situaciones = [
        Situacion.TERMINADO,
        Situacion.NO_TERMINADO,
        Situacion.TERMINADO,
        Situacion.TERMINADO,
    ]
    errores = {Frente.LISTAS: _error(Causa.INVALIDADO, 0)}
    listas = calcular_cobertura(_estado(situaciones, errores)).frentes[Frente.LISTAS]
    assert not listas.cubierto and listas.causa is Causa.INVALIDADO
    assert "comercio del registro cambió" in listas.motivo


@pytest.mark.parametrize("causa", list(Causa))
def test_cada_causa_tiene_un_motivo_propio(causa):
    situacion = Situacion.RECHAZADO if causa is Causa.RECHAZADO else Situacion.NO_TERMINADO
    estado = _estado([situacion] * 4, {f: _error(causa) for f in Frente})
    motivos = {c.motivo for c in calcular_cobertura(estado).frentes.values()}
    assert len(motivos) == 1 and all(motivos)


def test_un_intento_no_se_menciona_y_dos_si():
    situaciones = [Situacion.NO_TERMINADO] * 4
    uno = calcular_cobertura(
        _estado(situaciones, {Frente.REGISTRO: _error(Causa.SIN_CONSULTAS, 1)})
    )
    dos = calcular_cobertura(
        _estado(situaciones, {Frente.REGISTRO: _error(Causa.SIN_CONSULTAS, 2)})
    )
    assert "intento" not in uno.lineas()[1]
    assert uno.lineas()[1].endswith(".") and dos.lineas()[1].endswith("; 2 intentos.")


# ------------------------------------------------------------------ formato registrado


def test_las_lineas_tienen_resumen_y_una_por_frente_en_orden():
    completa = calcular_cobertura(_estado([Situacion.TERMINADO] * 4)).lineas()
    assert completa == [
        "Cobertura completa: 4 de 4 frentes cubiertos.",
        "registro: cubierto.",
        "listas: cubierto.",
        "noticias: cubierto.",
        "categoria: cubierto.",
    ]
    situaciones = [
        Situacion.TERMINADO,
        Situacion.TERMINADO,
        Situacion.NO_TERMINADO,
        Situacion.TERMINADO,
    ]
    incompleta = calcular_cobertura(_estado(situaciones)).lineas()
    assert incompleta[0] == "Cobertura incompleta: 3 de 4 frentes cubiertos."
    assert len(incompleta) == 5


@pytest.mark.parametrize("situaciones", COMBINACIONES[::7])
def test_la_cobertura_no_repite_el_nombre_ni_el_identificador_del_comercio(situaciones):
    errores = {f: _error(c) for f, c in zip(Frente, list(Causa), strict=False)}
    estado = _estado(situaciones, errores)
    estado.registrar_identificacion(
        respuesta_registro(comercio_del_registro(IDENTIFICADOR, NOMBRE))
    )
    texto = " ".join(calcular_cobertura(estado).lineas())
    assert NOMBRE not in texto and IDENTIFICADOR not in texto


def test_calcular_la_cobertura_no_cambia_el_estado_ni_registra_nada():
    estado = _estado(
        [Situacion.TERMINADO, Situacion.RECHAZADO, Situacion.EN_CURSO, Situacion.SIN_INICIAR]
    )
    antes = estado.instantanea()
    calcular_cobertura(estado)
    assert estado.instantanea() == antes


def test_los_tipos_son_inmutables():
    cobertura = calcular_cobertura(_estado([Situacion.TERMINADO] * 4))
    assert isinstance(cobertura, CoberturaCaso)
    assert all(isinstance(c, CoberturaFrente) for c in cobertura.frentes.values())
    with pytest.raises(AttributeError):
        cobertura.completa = False  # type: ignore[misc]
