"""Tests de la fuente única de la identificación del comercio (R4, FR-001, FR-013).

`derivar_comercio` es el único intérprete de la respuesta del registro y el hook del registro el
único escritor: `EstadoCaso.registrar_identificacion` guarda lo que `derivar_comercio` devuelve y
`comercio` / `motivo_comercio` son propiedades derivadas de eso y de la situación del registro.
"""

import pytest

from due_diligence import estado as modulo_estado
from due_diligence.delegacion import Delegador
from due_diligence.estado import EstadoCaso, Situacion
from due_diligence.frentes import Frente
from due_diligence.libro import LibroReglas
from due_diligence.simulacion import comercio_del_registro, respuesta_del_contrato


def _registro(*comercios, coincidencias=None):
    contenidos = list(comercios)
    if coincidencias is None:
        coincidencias = [c["identificador"] for c in contenidos]
    return respuesta_del_contrato("coincidencias", contenidos, coincidencias)


def _llevar_registro_a(estado, destino):
    if destino is Situacion.RECHAZADO:
        estado.cambiar_situacion(Frente.REGISTRO, Situacion.RECHAZADO, "motivo")
        return
    if destino is Situacion.SIN_INICIAR:
        return
    estado.cambiar_situacion(Frente.REGISTRO, Situacion.EN_CURSO)
    if destino in (Situacion.TERMINADO, Situacion.NO_TERMINADO):
        estado.cambiar_situacion(Frente.REGISTRO, destino)


def _estado_terminado(*respuestas):
    estado = EstadoCaso("solicitud")
    _llevar_registro_a(estado, Situacion.TERMINADO)
    for respuesta in respuestas:
        estado.registrar_identificacion(respuesta)
    return estado


# ------------------------------------------------------- derivar_comercio es el único intérprete


def test_registrar_identificacion_llama_a_derivar_comercio_una_vez_por_consulta(monkeypatch):
    llamadas = []
    original = modulo_estado.derivar_comercio

    def espia(resultado):
        llamadas.append(resultado)
        return original(resultado)

    monkeypatch.setattr(modulo_estado, "derivar_comercio", espia)
    estado = EstadoCaso("solicitud")
    respuesta = _registro(comercio_del_registro())
    estado.registrar_identificacion(respuesta)
    assert llamadas == [respuesta]
    estado.registrar_identificacion(respuesta)
    assert len(llamadas) == 2


def test_el_estado_no_interpreta_la_respuesta_por_su_cuenta(monkeypatch):
    # Si `derivar_comercio` dijera otra cosa, el estado la sigue: no hay una segunda interpretación.
    monkeypatch.setattr(
        modulo_estado, "derivar_comercio", lambda _r: ({"identificador": "X", "nombre": "Y"}, "")
    )
    estado = _estado_terminado()
    estado.registrar_identificacion({"cualquier": "cosa"})
    assert estado.comercio == {"identificador": "X", "nombre": "Y"}


# ------------------------------------------------------------ comercio y motivo (propiedades)


def test_una_coincidencia_con_el_registro_terminado_identifica_al_comercio():
    estado = _estado_terminado(_registro(comercio_del_registro()))
    comercio = estado.comercio
    assert comercio is not None
    assert comercio["identificador"] == "CO-TV-0001" and comercio["nombre"] == "Tienda Verde SAS"
    assert comercio["representante_legal"]["identificador"] == "PE-0001"
    assert estado.motivo_comercio == ""


def test_sin_identificaciones_y_registro_terminado_no_hay_datos():
    estado = _estado_terminado()
    assert estado.comercio is None
    assert estado.motivo_comercio == "El registro no devolvió datos."


@pytest.mark.parametrize(
    "situacion",
    [Situacion.NO_TERMINADO, Situacion.EN_CURSO, Situacion.RECHAZADO, Situacion.SIN_INICIAR],
)
def test_con_el_registro_sin_terminar_no_hay_comercio(situacion):
    estado = EstadoCaso("solicitud")
    estado.registrar_identificacion(_registro(comercio_del_registro()))
    _llevar_registro_a(estado, situacion)
    assert estado.comercio is None
    assert estado.motivo_comercio.startswith("El registro mercantil no terminó")


def test_varias_coincidencias_no_identifican_y_el_motivo_lo_dice():
    estado = _estado_terminado(
        _registro(
            comercio_del_registro("CO-AM-0004", "Almacén Mirador SAS"),
            comercio_del_registro("CO-AM-0005", "Almacén Mirador del Sur SAS"),
        )
    )
    assert estado.comercio is None
    assert "varias coincidencias" in estado.motivo_comercio


def test_ninguna_coincidencia_no_identifica_y_trae_el_motivo_de_derivar_comercio():
    estado = _estado_terminado(respuesta_del_contrato("sin_coincidencias", [], []))
    assert estado.comercio is None
    assert "ninguna coincidencia" in estado.motivo_comercio


def test_fuentes_que_difieren_en_el_nombre_no_identifican():
    estado = _estado_terminado(
        _registro(
            comercio_del_registro("CO-RF-0006", "Ruta Fría SAS"),
            comercio_del_registro("CO-RF-0006", "Ruta Fria Ltda"),
            coincidencias=["CO-RF-0006"],
        )
    )
    assert estado.comercio is None and "difieren" in estado.motivo_comercio


def test_dos_consultas_que_identifican_comercios_distintos_no_eligen_uno():
    estado = _estado_terminado(
        _registro(comercio_del_registro("CO-TV-0001", "Tienda Verde SAS")),
        _registro(comercio_del_registro("CO-TA-0002", "Tienda Azul SAS")),
    )
    assert estado.comercio is None
    assert "comercios distintos: no se elige uno" in estado.motivo_comercio


def test_dos_consultas_que_identifican_al_mismo_comercio_lo_identifican():
    respuesta = _registro(comercio_del_registro())
    estado = _estado_terminado(respuesta, respuesta)
    assert estado.comercio is not None
    assert estado.comercio["identificador"] == "CO-TV-0001"


def test_una_consulta_con_coincidencia_y_otra_sin_ella_no_elige_la_primera_sin_comprobar():
    # La que no tiene coincidencias no cuenta: el comercio es el de la que sí las tiene.
    estado = _estado_terminado(
        respuesta_del_contrato("sin_coincidencias", [], []),
        _registro(comercio_del_registro()),
    )
    assert estado.comercio is not None
    assert estado.comercio["identificador"] == "CO-TV-0001"
    # Y si la que tiene coincidencias es ambigua, no se identifica aunque otra no tenga ninguna.
    ambiguo = _estado_terminado(
        respuesta_del_contrato("sin_coincidencias", [], []),
        _registro(
            comercio_del_registro("CO-AM-0004", "Almacén Mirador SAS"),
            comercio_del_registro("CO-AM-0005", "Almacén Mirador del Sur SAS"),
        ),
    )
    assert ambiguo.comercio is None and "varias coincidencias" in ambiguo.motivo_comercio


def test_si_ninguna_consulta_tiene_coincidencias_el_motivo_es_el_de_la_primera():
    estado = _estado_terminado(
        respuesta_del_contrato("sin_coincidencias", [], []),
        {"respuesta": "sin la forma del contrato"},
    )
    assert estado.comercio is None
    assert "ninguna coincidencia" in estado.motivo_comercio


def test_una_respuesta_ilegible_no_identifica_al_comercio():
    estado = _estado_terminado({"cualquier": "cosa"})
    assert estado.comercio is None
    assert estado.motivo_comercio  # dice por qué


def test_el_representante_se_guarda_tal_como_lo_devolvio_el_registro():
    sin_representante = comercio_del_registro(representante=None)
    estado = _estado_terminado(_registro(sin_representante))
    assert estado.comercio is not None
    assert estado.comercio["representante_legal"] is None


# ------------------------------------------------------------ reiniciar y copiar


def test_reiniciar_la_identificacion_la_vacia():
    estado = _estado_terminado(_registro(comercio_del_registro()))
    assert estado.comercio is not None
    estado.reiniciar_identificacion()
    assert estado.identificaciones == []
    assert estado.comercio is None
    assert estado.motivo_comercio == "El registro no devolvió datos."


def test_ya_no_existe_fijar_comercio_ni_el_fijar_del_delegador():
    assert not hasattr(EstadoCaso, "fijar_comercio")
    assert not hasattr(Delegador, "_fijar_comercio")


def test_la_instantanea_copia_las_identificaciones_y_el_libro():
    estado = _estado_terminado(_registro(comercio_del_registro()))
    estado.libro.fallo_de_hook = "x"
    copia = estado.instantanea()
    estado.reiniciar_identificacion()
    estado.libro.fallo_de_hook = None
    assert copia.comercio is not None
    assert copia.libro.fallo_de_hook == "x"
    assert isinstance(copia.libro, LibroReglas)


def test_el_cierre_sin_escalar_empieza_en_falso_y_cada_estado_tiene_su_libro():
    uno, otro = EstadoCaso("a"), EstadoCaso("b")
    assert uno.cierre_sin_escalar is False
    uno.cierre_sin_escalar = True
    uno.libro.cierres_impedidos += 1
    assert otro.cierre_sin_escalar is False and otro.libro.cierres_impedidos == 0
    assert uno.libro is not otro.libro
