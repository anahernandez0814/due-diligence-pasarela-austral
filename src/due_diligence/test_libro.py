"""Tests del libro de reglas del caso (data-model, FR-011).

El libro guarda lo que los hooks registran para decidir las reglas I.1, I.2 e I.3. Es por caso y no
comparte nada con otro libro.
"""

import copy
from dataclasses import fields

from due_diligence.libro import Coincidencia, ConsultaListas, ConsultaRiesgo, LibroReglas


def test_un_libro_nuevo_empieza_vacio():
    libro = LibroReglas()
    assert libro.consultas_listas == []
    assert libro.coincidencias == []
    assert libro.consultas_riesgo == []
    assert libro.escalamientos == []
    assert libro.cierres_impedidos == 0
    assert libro.fallo_de_hook is None


def test_dos_libros_no_comparten_listas():
    uno, otro = LibroReglas(), LibroReglas()
    uno.consultas_listas.append(
        ConsultaListas("comercio", "Tienda Verde SAS", None, "sin_coincidencias")
    )
    uno.coincidencias.append(Coincidencia("persona", "Lista A", "Fuente A", "2026-09-30"))
    uno.consultas_riesgo.append(ConsultaRiesgo("apuestas", "alto"))
    uno.escalamientos.append(frozenset({"alto_riesgo"}))
    uno.cierres_impedidos += 1
    uno.fallo_de_hook = "fallo"
    assert otro.consultas_listas == [] and otro.coincidencias == []
    assert otro.consultas_riesgo == [] and otro.escalamientos == []
    assert otro.cierres_impedidos == 0 and otro.fallo_de_hook is None


def test_consulta_de_listas_guarda_tipo_nombre_identificador_y_resultado():
    consulta = ConsultaListas("persona", None, "PE-0003", "coincidencias")
    assert (consulta.tipo, consulta.nombre, consulta.identificador, consulta.resultado) == (
        "persona",
        None,
        "PE-0003",
        "coincidencias",
    )


def test_la_coincidencia_no_guarda_nombre_ni_identificador():
    # Las causas de escalamiento son claves fijas y los motivos no repiten lo consultado (FR-016).
    nombres = {campo.name for campo in fields(Coincidencia)}
    assert nombres == {"tipo", "lista", "fuente", "fecha"}


def test_la_causa_de_una_coincidencia_sale_de_su_tipo():
    assert Coincidencia("comercio", "L", "F", "2026-09-30").causa == "coincidencia_comercio"
    assert Coincidencia("persona", "L", "F", "2026-09-30").causa == "coincidencia_representante"


def test_consulta_de_riesgo_guarda_categoria_y_nivel_o_ninguno():
    assert ConsultaRiesgo("suplementos dietarios", "alto").nivel == "alto"
    desconocida = ConsultaRiesgo("algo raro", None)
    assert desconocida.nivel is None and desconocida.categoria == "algo raro"


def test_la_copia_profunda_del_libro_es_independiente():
    libro = LibroReglas()
    libro.coincidencias.append(Coincidencia("comercio", "L", "F", "2026-09-30"))
    copia = copy.deepcopy(libro)
    libro.coincidencias.append(Coincidencia("persona", "L2", "F2", "2026-09-30"))
    libro.fallo_de_hook = "x"
    assert len(copia.coincidencias) == 1 and copia.fallo_de_hook is None
