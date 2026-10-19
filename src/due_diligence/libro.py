"""Libro de reglas del caso (data-model, R3, R7, R8, R9, FR-011).

Guarda lo que los hooks registran para decidir las reglas de negocio I.1, I.2 e I.3: las consultas
de listas válidas, las coincidencias, las consultas de riesgo, los escalamientos y el contador de
cierres impedidos. Es **por caso** y no tiene estado de módulo. Solo lo escriben los hooks
(`PostToolUse`, el `Stop` y el envoltorio de fallo); las reglas lo leen con funciones puras.

Las coincidencias **no guardan el nombre ni el identificador consultados**: la causa de escalamiento
sale de su tipo (`comercio` o `persona`) y es una clave fija, para que ningún motivo repita lo
consultado (FR-016).
"""

from dataclasses import dataclass, field
from typing import Any

CAUSA_COINCIDENCIA_COMERCIO = "coincidencia_comercio"
CAUSA_COINCIDENCIA_REPRESENTANTE = "coincidencia_representante"
CAUSA_ALTO_RIESGO = "alto_riesgo"
# El sello `fallo_de_hook` también es causa de escalamiento (#9, R9): tras un fallo de hook solo
# decide un oficial, y un oficial solo decide lo que recibe.
CAUSA_FALLO_DE_HOOK = "fallo_de_hook"


@dataclass(frozen=True)
class ConsultaListas:
    """Una consulta de listas **válida** (llegó sin error) y su resultado."""

    tipo: str  # "comercio" o "persona"
    nombre: str | None
    identificador: str | None
    resultado: str  # "coincidencias" o "sin_coincidencias"


@dataclass(frozen=True)
class Coincidencia:
    """Un hallazgo de listas. Nunca se borra, aunque el registro cambie de comercio."""

    tipo: str  # "comercio" o "persona"
    lista: str
    fuente: str
    fecha: str

    @property
    def causa(self) -> str:
        if self.tipo == "persona":
            return CAUSA_COINCIDENCIA_REPRESENTANTE
        return CAUSA_COINCIDENCIA_COMERCIO


@dataclass(frozen=True)
class ConsultaRiesgo:
    """Una consulta de riesgo de categoría; `nivel` es `None` si la categoría fue desconocida."""

    categoria: str
    nivel: str | None  # "alto", "medio", "bajo" o None


@dataclass(frozen=True)
class Escalamiento:
    """Un escalamiento aceptado por la pasarela (#10, R8, data-model).

    `causas` es la instantánea de las causas vigentes cuando el `PreToolUse` aceptó la llamada;
    `comercio`, la clave `(identificador, nombre, verificado)` del comercio del caso en ese momento,
    la misma de la huella del informe (#9). Solo cuenta para ese comercio.
    """

    causas: frozenset[str]
    comercio: tuple[Any, Any, bool] | None


@dataclass
class LibroReglas:
    consultas_listas: list[ConsultaListas] = field(default_factory=list)
    coincidencias: list[Coincidencia] = field(default_factory=list)
    consultas_riesgo: list[ConsultaRiesgo] = field(default_factory=list)
    # Cada escalamiento exitoso, con sus causas y su comercio (#10, R8).
    escalamientos: list[Escalamiento] = field(default_factory=list)
    cierres_impedidos: int = 0
    # Sello pegajoso: un hook no pudo registrar un hecho o terminar su evaluación (R2).
    fallo_de_hook: str | None = None
