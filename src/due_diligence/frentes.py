"""Los cuatro frentes de la investigación y las herramientas de la pasarela (data-model, R3).

Cada frente tiene una herramienta propia del servidor `pasarela` (ticket #5), una dependencia
opcional (`listas` depende de `registro`) y los campos de contexto que necesita. Es una tabla
de constantes: no guarda estado de ningún caso.
"""

from dataclasses import dataclass
from enum import StrEnum

SERVIDOR_PASARELA = "pasarela"
SERVIDOR_DELEGACION = "delegacion"
HERRAMIENTA_DELEGAR = "delegar_frente"


class Frente(StrEnum):
    REGISTRO = "registro"
    LISTAS = "listas"
    NOTICIAS = "noticias"
    CATEGORIA = "categoria"


# Las seis herramientas del servidor `pasarela` (FR-001 del #5), por frente y de decisión.
HERRAMIENTAS_FUENTES = (
    "consultar_registro_mercantil",
    "consultar_listas_restrictivas",
    "buscar_noticias",
    "consultar_riesgo_categoria",
)
HERRAMIENTAS_DECISION = ("registrar_informe", "escalar_a_cumplimiento")
HERRAMIENTAS_PASARELA = HERRAMIENTAS_FUENTES + HERRAMIENTAS_DECISION


def nombre_completo(herramienta: str, servidor: str = SERVIDOR_PASARELA) -> str:
    """Nombre con el que el agente ve la herramienta: `mcp__<servidor>__<herramienta>`."""
    return f"mcp__{servidor}__{herramienta}"


@dataclass(frozen=True)
class DefinicionFrente:
    frente: Frente
    herramienta: str
    dependencia: Frente | None
    campos: tuple[str, ...]

    @property
    def herramienta_completa(self) -> str:
        return nombre_completo(self.herramienta)


FRENTES: dict[Frente, DefinicionFrente] = {
    Frente.REGISTRO: DefinicionFrente(
        Frente.REGISTRO, "consultar_registro_mercantil", None, ("identificador", "nombre")
    ),
    Frente.NOTICIAS: DefinicionFrente(
        Frente.NOTICIAS, "buscar_noticias", None, ("identificador", "nombre")
    ),
    Frente.CATEGORIA: DefinicionFrente(
        Frente.CATEGORIA, "consultar_riesgo_categoria", None, ("categoria",)
    ),
    Frente.LISTAS: DefinicionFrente(
        Frente.LISTAS, "consultar_listas_restrictivas", Frente.REGISTRO, ()
    ),
}


def herramientas_ajenas(frente: Frente) -> tuple[str, ...]:
    """Las herramientas de la pasarela que NO son de este frente (el complemento de R3)."""
    propia = FRENTES[frente].herramienta
    return tuple(h for h in HERRAMIENTAS_PASARELA if h != propia)
