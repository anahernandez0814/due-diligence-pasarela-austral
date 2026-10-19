"""Tests de `observacion.py` (#12, R6, R7): la proyección de los casos simulados y los guardas de
FR-003, que impiden que una verificación de la suite de punta a punta llegue al texto del modelo.

No llaman al modelo: los casos son los del `CoordinadorSimulado` de los tickets #9 al #11.
"""

import ast
import asyncio
import dataclasses
from pathlib import Path

import pytest

from due_diligence import observacion
from due_diligence.eventos import TIPO_BLOQUEO_REGLA
from due_diligence.frentes import Frente
from due_diligence.observacion import (
    CAUSA_ALTO_RIESGO,
    MOTIVO_ESPERA_IDENTIFICADOR,
    ComercioObservado,
    ConflictoObservado,
    ConsultaListasObservada,
    ConsultaObservada,
    EscalamientoObservado,
    EsperaObservada,
    EventoObservado,
    FrenteObservado,
    InformeObservado,
    Metricas,
    Observacion,
    Registros,
    leer_registros,
    observar,
)
from due_diligence.test_presentacion import caso_a, caso_d, caso_f

E2E = Path(__file__).with_name("test_e2e_casos.py")


@pytest.fixture(autouse=True)
def _sin_caidas(monkeypatch):
    monkeypatch.delenv("PASARELA_FALLA_REGISTRO", raising=False)
    monkeypatch.delenv("PASARELA_FALLA_NOTICIAS", raising=False)


def _registros(caso):
    """Lo que aceptó la `PasarelaSimulada` del coordinador simulado del caso."""
    pasarela = caso._consulta.pasarela
    return Registros(tuple(pasarela.informes), tuple(pasarela.escalamientos))


def _observar(caso):
    return observar(caso, _registros(caso), duracion_s=1.5)


def caso_b():
    from due_diligence.simulacion import comercio_bajo_riesgo
    from due_diligence.test_casos_escalamiento import SOLICITUD_B, _caso, _delegaciones
    from due_diligence.test_casos_escalamiento import _listas as listas
    from due_diligence.test_casos_escalamiento import _registro as registro
    from due_diligence.test_casos_escalamiento import _riesgo as riesgo

    resultados = {
        Frente.REGISTRO: registro("CO-TA-0002", comercio_bajo_riesgo()),
        Frente.CATEGORIA: riesgo("tecnología y software", "bajo"),
        Frente.LISTAS: listas("CO-TA-0002", "PE-0002"),
    }
    guion = [
        _delegaciones({"identificador": "CO-TA-0002"}, "tecnología y software"),
        ("delegar", {"frente": "listas"}),
        ("informe", "habilitar"),
        ("terminar",),
    ]
    caso, _, _ = _caso([guion], resultados, SOLICITUD_B)
    return caso


def caso_g():
    from due_diligence.test_casos_informe import (
        SOLICITUD_G,
        _caso_con,
        _delegaciones,
        _resultados_g,
    )

    guion = [
        _delegaciones("CO-RF-0006", "comercio de calzado"),
        ("delegar", {"frente": "listas"}),
        ("informe", "no_habilitar"),
        ("terminar",),
    ]
    caso, _ = _caso_con(guion, _resultados_g(), SOLICITUD_G)
    return caso


# ------------------------------------------------------- la proyección de los casos (T005, R6)


def test_caso_a_escalamiento_por_alto_riesgo_e_informe_que_lo_deja_al_oficial():
    observado = _observar(caso_a())
    (escalamiento,) = observado.escalamientos
    assert CAUSA_ALTO_RIESGO in escalamiento.causas
    assert [i.recomendacion for i in observado.informes] == ["decide_cumplimiento"]
    assert observado.registros_coherentes
    assert observado.metricas.duracion_s == 1.5


def test_caso_b_habilitar_sin_escalar_con_los_cuatro_frentes_cubiertos():
    observado = _observar(caso_b())
    assert [i.recomendacion for i in observado.informes] == ["habilitar"]
    assert observado.escalamientos == ()
    assert set(observado.cobertura) == {f.value for f in Frente}
    assert all(f.cubierto for f in observado.cobertura.values())
    assert observado.completo is True
    assert observado.comercio == ComercioObservado("CO-TA-0002", "Taller Aurora SAS", True)


def test_caso_d_turno_1_espera_el_identificador_sin_listas():
    observado = _observar(caso_d(1))
    assert observado.espera == EsperaObservada("identificador", MOTIVO_ESPERA_IDENTIFICADOR)
    clases = [c.clase_registro for c in observado.consultas if c.frente == "registro"]
    assert "varias" in clases
    assert observado.consultas_listas == ()
    assert observado.informes == () and observado.escalamientos == ()
    # El bloqueo de I.1 del guion (el que verifica el caso e) también se observa, sin su detalle.
    assert any(e.tipo == TIPO_BLOQUEO_REGLA and e.regla == "I.1" for e in observado.eventos)


def test_caso_d_turno_2_identifica_co_am_0004_y_consulta_listas():
    observado = _observar(caso_d(2))
    assert observado.comercio is not None
    assert observado.comercio.identificador == "CO-AM-0004"
    assert observado.consultas_listas
    assert [c.frente for c in observado.consultas].count("listas") >= 1
    assert len(observado.informes) == 1


def test_caso_f_el_informe_declara_la_cobertura_calculada_sin_noticias():
    observado = _observar(caso_f())
    (informe,) = observado.informes
    assert informe.cobertura == observado.cobertura_lineas
    assert observado.cobertura["noticias"].cubierto is False
    assert observado.completo is False


def test_caso_g_el_conflicto_de_fecha_conserva_las_dos_fuentes():
    observado = _observar(caso_g())
    (informe,) = observado.informes
    (fecha,) = [c for c in informe.conflictos if c.campo == "fecha_constitucion"]
    valores = {valor for valor, _ in fecha.valores}
    fuentes = {fuente for _, fuente in fecha.valores}
    assert len(fecha.valores) == 2 and len(valores) == 2 and len(fuentes) == 2


def test_leer_registros_lee_los_json_de_la_carpeta_en_orden(tmp_path):
    (tmp_path / "informes").mkdir()
    (tmp_path / "informes" / "INF-0002.json").write_text('{"id": "INF-0002"}', encoding="utf-8")
    (tmp_path / "informes" / "INF-0001.json").write_text('{"id": "INF-0001"}', encoding="utf-8")
    registros = leer_registros(tmp_path)
    assert [d["id"] for d in registros.informes] == ["INF-0001", "INF-0002"]
    assert registros.escalamientos == ()


def test_sin_los_registros_de_la_pasarela_la_observacion_no_es_coherente():
    caso = caso_a()
    assert observar(caso, Registros()).registros_coherentes is False


# ------------------------------------------------- guardas de FR-003 (T006, R7, SC-002)

CAMPOS = {
    Observacion: {
        "eventos",
        "consultas",
        "consultas_listas",
        "escalamientos",
        "informes",
        "cobertura",
        "cobertura_lineas",
        "completo",
        "espera",
        "comercio",
        "terminaciones",
        "metricas",
        "registros_coherentes",
    },
    EventoObservado: {"tipo", "frente", "regla", "accion"},
    ConsultaObservada: {
        "frente",
        "herramienta",
        "nombre",
        "identificador",
        "tipo",
        "valida",
        "clase_registro",
    },
    ConsultaListasObservada: {"tipo", "nombre", "identificador", "resultado"},
    EscalamientoObservado: {"id", "causas"},
    InformeObservado: {"id", "recomendacion", "minimo", "cobertura", "conflictos"},
    ConflictoObservado: {"campo", "valores"},
    FrenteObservado: {"cubierto", "causa"},
    EsperaObservada: {"clase", "motivo"},
    ComercioObservado: {"identificador", "nombre", "verificado"},
    Metricas: {"coste_usd", "turnos", "duracion_s"},
}
TEXTO_LIBRE = {
    "Caso",
    "respuesta",
    "detalle",
    "resumen",
    "hallazgos",
    "accion_recomendada",
    "texto",
    "mensajes",
}
MARCA = "«TEXTO-LIBRE-12»"


@pytest.mark.parametrize("clase", list(CAMPOS), ids=lambda c: c.__name__)
def test_los_campos_de_la_observacion_son_un_conjunto_cerrado_sin_texto_libre(clase):
    # Añadir un campo exige cambiar este test a sabiendas (data-model).
    nombres = {f.name for f in dataclasses.fields(clase)}
    assert nombres == CAMPOS[clase]
    assert not nombres & TEXTO_LIBRE


def test_ningun_texto_del_modelo_llega_a_la_observacion():
    caso = caso_a()
    caso.respuesta = f"Respuesta al analista {MARCA}"
    caso.estado.mensajes.append(f"Mensaje del analista {MARCA}")
    for resultado in caso.estado.resultados.values():
        resultado.resumen = f"Resumen del subagente {MARCA}"
    caso._eventos.registrar(TIPO_BLOQUEO_REGLA, Frente.LISTAS, f"detalle {MARCA}", regla="I.1")
    pasarela = caso._consulta.pasarela
    documentos = [
        {**d, "hallazgos": {"registro": [{"texto": MARCA}]}, "accion_recomendada": MARCA}
        for d in [*pasarela.informes, *pasarela.escalamientos]
    ]
    informes = tuple(documentos[: len(pasarela.informes)])
    escalamientos = tuple(documentos[len(pasarela.informes) :])
    observado = observar(caso, Registros(informes, escalamientos))
    assert MARCA not in repr(observado)


_COLECCIONES = (ast.List, ast.Tuple, ast.Set, ast.ListComp, ast.SetComp)


def _problemas_de_texto(codigo: str) -> list[str]:
    """Lo que un módulo de tests e2e hace y lo acercaría al texto del modelo (R7)."""
    problemas = []
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.Import):
            problemas += [f"import {a.name}" for a in nodo.names if a.name != "pytest"]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module != "due_diligence.observacion":
            problemas.append(f"from {nodo.module} import …")
        elif isinstance(nodo, ast.Name) and nodo.id in TEXTO_LIBRE:
            problemas.append(f"nombre {nodo.id}")
        elif isinstance(nodo, ast.Attribute) and nodo.attr in TEXTO_LIBRE:
            problemas.append(f"atributo .{nodo.attr}")
        elif isinstance(nodo, ast.Attribute) and nodo.attr in {
            "startswith",
            "endswith",
            "find",
            "split",
            "lower",
            "upper",
        }:
            problemas.append(f"búsqueda en cadenas .{nodo.attr}")
        elif isinstance(nodo, ast.Constant) and nodo.value in TEXTO_LIBRE:
            problemas.append(f"cadena {nodo.value!r}")
        elif (
            isinstance(nodo, ast.Compare)
            and isinstance(nodo.left, ast.Constant)
            and isinstance(nodo.left.value, str)
            and any(isinstance(op, ast.In | ast.NotIn) for op in nodo.ops)
            # Pertenencia a una colección escrita en el propio test, no búsqueda en una cadena.
            and not all(isinstance(c, _COLECCIONES) for c in nodo.comparators)
        ):
            problemas.append(f"subcadena {nodo.left.value!r} in …")
    return problemas


def test_los_tests_e2e_no_pueden_llegar_al_texto_del_modelo():
    assert _problemas_de_texto(E2E.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "fragmento",
    [
        "assert observacion.respuesta",
        "from due_diligence.coordinador import Caso",
        "import re",
        "assert 'escal' in texto_cualquiera",
        "assert 'escal' in obtener_texto()",
        "assert algo.detalle == 'x'",
        "assert valor.startswith('I.')",
        "x = getattr(o, 'hallazgos')",
    ],
)
def test_el_guarda_detecta_cada_forma_de_leer_el_texto(fragmento):
    # Test de mutación del guarda: cada fragmento lo hace fallar.
    assert _problemas_de_texto(fragmento)


def test_el_modulo_reexporta_lo_que_necesitan_los_tests_e2e():
    for nombre in ("MOTIVO_ESPERA_IDENTIFICADOR", "CAUSA_ALTO_RIESGO", "observar"):
        assert nombre in observacion.__all__


def test_la_observacion_es_inmutable():
    observado = _observar(caso_f())
    with pytest.raises(dataclasses.FrozenInstanceError):
        observado.completo = True  # type: ignore[misc]


def test_observar_no_ejecuta_el_caso():
    # Solo lee: no hay `await`, así que no puede llamar al modelo ni a la pasarela.
    assert not asyncio.iscoroutinefunction(observar)
