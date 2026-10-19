"""Lo que la suite de punta a punta puede ver de un caso (#12, R6, data-model `Observacion`).

`observar` convierte un `Caso` terminado y lo que registró la pasarela en una `Observacion`
inmutable: eventos sin su detalle, consultas con solo los argumentos que identifican, el libro de
reglas, los informes y escalamientos aceptados y el estado calculado por el código. **Nada del
modelo**: no se copian `respuesta`, `detalle`, `resumen`, `hallazgos`, `accion_recomendada` ni los
mensajes del analista. Las cadenas que sí se leen son constantes del código (motivos, causas, la
cobertura que fija el hook) y los tests las comparan por igualdad con la constante.

Es la frontera que garantiza FR-003: `test_e2e_casos.py` solo importa este módulo, y
`test_observacion.py` comprueba que la observación no tiene ningún campo de texto libre.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from due_diligence.estado import clase_de
from due_diligence.eventos import TIPO_BLOQUEO_REGLA
from due_diligence.frentes import Frente
from due_diligence.informe import comercio_del_informe
from due_diligence.libro import (
    CAUSA_ALTO_RIESGO,
    CAUSA_COINCIDENCIA_COMERCIO,
    CAUSA_COINCIDENCIA_REPRESENTANTE,
)
from due_diligence.reglas import (
    MOTIVO_ESPERA_CATEGORIA,
    MOTIVO_ESPERA_IDENTIFICADOR,
    MOTIVO_ESPERA_NOMBRE,
)
from servidor_mcp.normalizar import igual as mismo_nombre
from servidor_mcp.normalizar import igual_identificador as mismo_identificador

if TYPE_CHECKING:
    from due_diligence.coordinador import Caso

# Reexportadas para que el test de punta a punta solo importe este módulo (R7).
__all__ = [
    "CAUSA_ALTO_RIESGO",
    "CAUSA_COINCIDENCIA_COMERCIO",
    "CAUSA_COINCIDENCIA_REPRESENTANTE",
    "MOTIVO_ESPERA_CATEGORIA",
    "MOTIVO_ESPERA_IDENTIFICADOR",
    "MOTIVO_ESPERA_NOMBRE",
    "TIPO_BLOQUEO_REGLA",
    "mismo_identificador",
    "mismo_nombre",
    "ComercioObservado",
    "ConflictoObservado",
    "ConsultaListasObservada",
    "ConsultaObservada",
    "EscalamientoObservado",
    "EsperaObservada",
    "EventoObservado",
    "FrenteObservado",
    "InformeObservado",
    "Metricas",
    "Observacion",
    "Registros",
    "leer_registros",
    "observar",
]

# Solo los argumentos de una consulta que identifican al comercio o a la persona consultada.
_ARGUMENTOS_QUE_IDENTIFICAN = ("nombre", "identificador", "tipo")


@dataclass(frozen=True)
class EventoObservado:
    tipo: str
    frente: str | None
    regla: str | None
    accion: str | None


@dataclass(frozen=True)
class ConsultaObservada:
    frente: str
    herramienta: str
    nombre: str | None
    identificador: str | None
    tipo: str | None
    valida: bool
    clase_registro: str | None  # solo en el registro: `clase_de` del resultado


@dataclass(frozen=True)
class ConsultaListasObservada:
    tipo: str
    nombre: str | None
    identificador: str | None
    resultado: str


@dataclass(frozen=True)
class EscalamientoObservado:
    id: str | None
    causas: frozenset[str]


@dataclass(frozen=True)
class ConflictoObservado:
    campo: str
    valores: tuple[tuple[str, str], ...]  # (valor, fuente) por cada fuente


@dataclass(frozen=True)
class InformeObservado:
    id: str
    recomendacion: str
    minimo: bool
    cobertura: tuple[str, ...]  # la que registró la pasarela: la fija el hook
    conflictos: tuple[ConflictoObservado, ...]


@dataclass(frozen=True)
class FrenteObservado:
    cubierto: bool
    causa: str | None


@dataclass(frozen=True)
class EsperaObservada:
    clase: str
    motivo: str


@dataclass(frozen=True)
class ComercioObservado:
    identificador: str | None
    nombre: str | None
    verificado: bool


@dataclass(frozen=True)
class Metricas:
    coste_usd: float | None
    turnos: tuple[int | None, ...]
    duracion_s: float


@dataclass(frozen=True)
class Registros:
    """Los documentos que aceptó la pasarela, en orden: de la carpeta del caso o simulados."""

    informes: tuple[Mapping[str, Any], ...] = ()
    escalamientos: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class Observacion:
    eventos: tuple[EventoObservado, ...]
    consultas: tuple[ConsultaObservada, ...]
    consultas_listas: tuple[ConsultaListasObservada, ...]
    escalamientos: tuple[EscalamientoObservado, ...]
    informes: tuple[InformeObservado, ...]
    cobertura: Mapping[str, FrenteObservado]
    cobertura_lineas: tuple[str, ...]
    completo: bool
    espera: EsperaObservada | None
    comercio: ComercioObservado | None
    terminaciones: tuple[str, ...]
    metricas: Metricas
    registros_coherentes: bool


def leer_registros(carpeta: Path) -> Registros:
    """Los informes y escalamientos que la pasarela guardó en `carpeta`, en orden de nombre."""

    def leer(subcarpeta: str) -> tuple[Mapping[str, Any], ...]:
        archivos = sorted((carpeta / subcarpeta).glob("*.json"))
        return tuple(json.loads(a.read_text(encoding="utf-8")) for a in archivos)

    return Registros(leer("informes"), leer("escalamientos"))


def observar(caso: "Caso", registros: Registros, duracion_s: float = 0.0) -> Observacion:
    """La observación del caso tras su último turno; solo datos del código, nunca del modelo."""
    estado = caso.estado
    cobertura = caso.cobertura
    espera = caso.espera
    comercio = comercio_del_informe(estado)
    escalamientos = estado.libro.escalamientos
    return Observacion(
        eventos=tuple(
            EventoObservado(e.tipo, _frente(e.frente), e.regla, e.accion) for e in caso.eventos()
        ),
        consultas=tuple(_consulta(c) for c in estado.consultas),
        consultas_listas=tuple(
            ConsultaListasObservada(c.tipo, c.nombre, c.identificador, c.resultado)
            for c in estado.libro.consultas_listas
        ),
        escalamientos=tuple(
            EscalamientoObservado(_id(registros.escalamientos, i), frozenset(e.causas))
            for i, e in enumerate(escalamientos)
        ),
        informes=tuple(
            _informe(informe.id, informe.recomendacion, informe.minimo, registros.informes, i)
            for i, informe in enumerate(estado.informes)
        ),
        cobertura={
            f.value: FrenteObservado(c.cubierto, None if c.causa is None else c.causa.value)
            for f, c in cobertura.frentes.items()
        },
        cobertura_lineas=tuple(cobertura.lineas()),
        completo=caso.completo,
        espera=None if espera is None else EsperaObservada(espera.clase, espera.motivo),
        comercio=None
        if comercio is None
        else ComercioObservado(
            comercio.get("identificador"), comercio.get("nombre"), bool(comercio.get("verificado"))
        ),
        terminaciones=tuple(f"{t.terminacion.value} ({t.subtype})" for t in caso.turnos_del_caso),
        metricas=Metricas(_coste(caso), tuple(caso.turnos_por_turno), duracion_s),
        registros_coherentes=(
            len(registros.informes) == len(estado.informes)
            and len(registros.escalamientos) == len(escalamientos)
        ),
    )


def _frente(frente: Frente | None) -> str | None:
    return None if frente is None else frente.value


def _consulta(consulta: Any) -> ConsultaObservada:
    argumentos = consulta.argumentos if isinstance(consulta.argumentos, Mapping) else {}
    nombre, identificador, tipo = (
        _texto(argumentos.get(clave)) for clave in _ARGUMENTOS_QUE_IDENTIFICAN
    )
    es_registro = consulta.frente is Frente.REGISTRO and consulta.resultado is not None
    return ConsultaObservada(
        consulta.frente.value,
        consulta.herramienta,
        nombre,
        identificador,
        tipo,
        bool(consulta.valido),
        clase_de(consulta.resultado) if es_registro else None,
    )


def _texto(valor: Any) -> str | None:
    return valor if isinstance(valor, str) else None


def _id(documentos: tuple[Mapping[str, Any], ...], indice: int) -> str | None:
    if indice >= len(documentos):
        return None
    return _texto(documentos[indice].get("id"))


def _informe(
    id_: str, recomendacion: str, minimo: bool, documentos: tuple[Mapping[str, Any], ...], i: int
) -> InformeObservado:
    documento = documentos[i] if i < len(documentos) else {}
    cobertura = documento.get("cobertura")
    lineas = tuple(cobertura) if isinstance(cobertura, list) else ()
    return InformeObservado(id_, recomendacion, minimo, lineas, _conflictos(documento))


def _conflictos(documento: Mapping[str, Any]) -> tuple[ConflictoObservado, ...]:
    conflictos = documento.get("conflictos")
    lista = conflictos.get("lista") if isinstance(conflictos, Mapping) else None
    if not isinstance(lista, list):
        return ()
    observados = []
    for conflicto in lista:
        if not isinstance(conflicto, Mapping):
            continue
        valores = conflicto.get("valores") if isinstance(conflicto.get("valores"), list) else []
        pares = tuple(
            (str(v.get("valor")), str(v.get("fuente"))) for v in valores if isinstance(v, Mapping)
        )
        observados.append(ConflictoObservado(str(conflicto.get("dato")), pares))
    return tuple(observados)


def _coste(caso: "Caso") -> float | None:
    """Como `__main__`: el coordinador más el último resultado de cada frente (aproximado, R8)."""
    costes = [caso.coste_usd, *(r.coste_usd for r in caso.estado.resultados.values())]
    conocidos = [c for c in costes if c is not None]
    return sum(conocidos) if conocidos else None
