"""Ejecutor simulado y constructores de resultados para los tests (R12).

Permite probar la delegación, el orden de los frentes y el estado sin llamar al modelo: un
`EjecutorSimulado` espera un tiempo conocido, registra cuándo empezó y terminó cada frente y
devuelve un resultado fijo. Los datos son los ficticios del #5.
"""

import asyncio
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from due_diligence.estado import Consulta, ResultadoFrente
from due_diligence.frentes import FRENTES, Frente
from due_diligence.terminacion import Clasificacion, clasificar

FUENTE = "Registro Mercantil Ficticio del Sur"
FECHA = "2026-09-30"
REPRESENTANTE = {"nombre": "Lucía Ferrer Montalvo", "identificador": "PE-0001"}


def respuesta_del_contrato(
    resultado: str = "coincidencias",
    contenidos: list[dict[str, Any]] | None = None,
    coincidencias: list[str] | None = None,
    fuente: str = FUENTE,
    fecha: str = FECHA,
) -> dict[str, Any]:
    """Una respuesta con la forma del contrato del #5: contenido separado de los metadatos."""
    hechos = [
        {"contenido": c, "metadatos": {"fuente": fuente, "fecha": fecha}} for c in contenidos or []
    ]
    respuesta: dict[str, Any] = {
        "resultado": resultado,
        "hechos": hechos,
        "metadatos": {"fuentes": [fuente], "fecha": fecha},
    }
    if coincidencias is not None:
        respuesta["coincidencias"] = coincidencias
    return respuesta


def comercio_del_registro(
    identificador: str = "CO-TV-0001",
    nombre: str = "Tienda Verde SAS",
    representante: Mapping[str, Any] | None = REPRESENTANTE,
) -> dict[str, Any]:
    return {
        "identificador": identificador,
        "nombre": nombre,
        "fecha_constitucion": "2019-04-12",
        "estado": "activo",
        "representante_legal": dict(representante) if representante else None,
    }


def consulta(
    frente: Frente,
    argumentos: Mapping[str, Any] | None = None,
    resultado: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> Consulta:
    """Una `Consulta` del frente. Sin `resultado` ni `error`, con una respuesta válida."""
    if resultado is None and error is None:
        resultado = respuesta_del_contrato("sin_coincidencias")
    return Consulta(
        frente,
        FRENTES[frente].herramienta_completa,
        dict(argumentos or {}),
        resultado,
        resultado is not None,
        error,
    )


def terminacion_normal() -> Clasificacion:
    return clasificar("success", "end_turn", False, "completed")


def terminacion_anomala() -> Clasificacion:
    return clasificar("success", "max_tokens", False, "completed")


def resultado_frente(
    frente: Frente,
    consultas: list[Consulta] | None = None,
    terminacion: Clasificacion | None = None,
    resumen: str = "resumen del subagente",
) -> ResultadoFrente:
    terminacion = terminacion or terminacion_normal()
    consultas = [consulta(frente)] if consultas is None else consultas
    return ResultadoFrente(frente, consultas, resumen, terminacion, terminacion.detalle)


def resultado_registro(
    comercios: list[dict[str, Any]] | None = None, fuentes: int = 1
) -> ResultadoFrente:
    """El resultado del registro: `comercios` (por defecto uno), con `fuentes` hechos cada uno."""
    comercios = [comercio_del_registro()] if comercios is None else comercios
    contenidos = [c for c in comercios for _ in range(fuentes)]
    identificadores = list(dict.fromkeys(c["identificador"] for c in comercios))
    respuesta = (
        respuesta_del_contrato("coincidencias", contenidos, identificadores)
        if comercios
        else respuesta_del_contrato("sin_coincidencias", [], [])
    )
    return resultado_frente(
        Frente.REGISTRO, [consulta(Frente.REGISTRO, {"identificador": "CO-TV-0001"}, respuesta)]
    )


@dataclass
class LlamadaSimulada:
    frente: Frente
    contexto: str
    opciones: Any
    inicio: float
    fin: float | None = None


class EjecutorSimulado:
    """Cumple `EjecutorSubagente`: espera `retardo` segundos y devuelve un resultado fijo.

    `resultados` asigna a cada frente un `ResultadoFrente` o una función `contexto -> resultado`;
    sin asignar, devuelve el registro con un comercio único o una consulta válida del frente.
    `retardos` ajusta el tiempo por frente y `excepciones` hace fallar a un frente.
    """

    def __init__(
        self,
        resultados: Mapping[Frente, ResultadoFrente | Callable[[str], ResultadoFrente]]
        | None = None,
        retardo: float = 0.0,
        retardos: Mapping[Frente, float] | None = None,
        excepciones: Mapping[Frente, BaseException] | None = None,
    ) -> None:
        self.resultados = dict(resultados or {})
        self.retardo = retardo
        self.retardos = dict(retardos or {})
        self.excepciones = dict(excepciones or {})
        self.llamadas: list[LlamadaSimulada] = []

    def llamadas_de(self, frente: Frente) -> list[LlamadaSimulada]:
        return [llamada for llamada in self.llamadas if llamada.frente is frente]

    async def __call__(self, frente: Frente, contexto: str, opciones: Any) -> ResultadoFrente:
        llamada = LlamadaSimulada(frente, contexto, opciones, time.monotonic())
        self.llamadas.append(llamada)
        await asyncio.sleep(self.retardos.get(frente, self.retardo))
        llamada.fin = time.monotonic()
        if frente in self.excepciones:
            raise self.excepciones[frente]
        resultado = self.resultados.get(frente)
        if callable(resultado):
            return resultado(contexto)
        if resultado is not None:
            return resultado
        if frente is Frente.REGISTRO:
            return resultado_registro()
        return resultado_frente(frente)
