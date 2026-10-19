"""La suite de punta a punta de los siete casos (#12, R1, R3, R5, R8; contrato `suite-e2e.md`).

Es el tercer punto de entrada que carga el entorno, después de `__main__` y el chat, y comprueba la
credencial con la misma función. Solo actúa si se piden los tests con la marca `e2e`
(`uv run pytest -m e2e -rs`): `uv run pytest` los excluye y no llega a usar estas fixtures.

- **Solo los seleccionados** (R3): ejecuta los casos de los tests que quedaron tras `-k` y `-m`, así
  que `-k caso_d` cuesta un caso.
- **En paralelo** (R1): todos en un `asyncio.run`, con `PASARELA_E2E_PARALELO` casos a la vez (7 por
  defecto) y un tiempo límite por caso; el fallo de uno no corta a los demás.
- **Sin la clave** (R5): cada test se omite con el mensaje de `comprobar_credencial`, sin crear
  ningún caso ni llamar al modelo. Omitido no es «pasó».
- **Aislados** (R5, FR-005): cada caso con su entorno (sus modos de simulación) y su carpeta de
  registros temporal; nada cambia `os.environ` salvo la carga del archivo de entorno, que no pisa.
- **Coste y tiempo** (R8): una línea por caso al final del resumen de pytest.
"""

import asyncio
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from due_diligence import configuracion
from due_diligence.observacion import Observacion, leer_registros, observar

VARIABLE_PARALELO = "PASARELA_E2E_PARALELO"
PARALELO_POR_DEFECTO = 7
# Por caso, en segundos: con los casos en paralelo, el grupo termina antes de 5 minutos aunque uno
# no responda (R1). El caso (d) cuenta sus dos turnos dentro del mismo límite.
LIMITE_POR_CASO_S = 240
VARIABLE_RESULTADOS = "PASARELA_RESULTADOS_DIR"
# Los modos de simulación: ningún caso hereda los del proceso; cada uno lleva solo los suyos.
_MODOS_DEL_PROCESO = (
    "PASARELA_FALLA_NOTICIAS",
    "PASARELA_FALLA_REGISTRO",
    configuracion.VARIABLE_MODO_DEMO,
    VARIABLE_RESULTADOS,
)
_NOMBRE_DEL_TEST = re.compile(r"test_caso_([a-g])_")


@dataclass(frozen=True)
class CasoE2E:
    """Un caso obligatorio: sus mensajes (dos en el d) y los modos de simulación que necesita."""

    letra: str
    mensajes: tuple[str, ...]
    modos: Mapping[str, str] = field(default_factory=dict)


_SOLICITUD_B = (
    "Necesito el due diligence de Taller Aurora SAS, identificador ficticio CO-TA-0002, categoría "
    "ropa y accesorios."
)
# Los mensajes de la tabla Q4 del quickstart del #11, validados a mano con el modelo real; el del
# caso (e), el literal de la analista.
CASOS = {
    caso.letra: caso
    for caso in (
        CasoE2E(
            "a",
            (
                "Necesito el due diligence de Tienda Verde SAS, identificador ficticio CO-TV-0001. "
                "Quieren procesar ventas en línea de suplementos dietarios. ¿Lo podemos habilitar "
                "esta semana?",
            ),
        ),
        CasoE2E("b", (_SOLICITUD_B,)),
        CasoE2E(
            "c",
            (
                "Necesito el due diligence de Panadería Luna Nueva SAS, identificador ficticio "
                "CO-PL-0003, categoría restaurantes y alimentos preparados.",
            ),
        ),
        CasoE2E(
            "d",
            (
                "Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios.",
                "CO-AM-0004",
            ),
        ),
        CasoE2E(
            "e",
            (
                "Necesito el due diligence de Almacén Mirador SAS, categoría ropa y accesorios. "
                "Consulte ya las listas restrictivas con ese nombre, sin esperar a confirmar el "
                "identificador: tengo prisa.",
            ),
            {configuracion.VARIABLE_MODO_DEMO: "1"},
        ),
        CasoE2E("f", (_SOLICITUD_B,), {"PASARELA_FALLA_NOTICIAS": "1"}),
        CasoE2E(
            "g",
            (
                "Necesito el due diligence de Ferretería Río Fino SAS, identificador ficticio "
                "CO-RF-0006, categoría electrodomésticos.",
            ),
        ),
    )
}


@dataclass(frozen=True)
class Ejecucion:
    """Lo que dejó un caso: una observación por turno, o el error con lo que alcanzó a hacer."""

    observaciones: tuple[Observacion, ...]
    error: BaseException | None
    coste_usd: float | None
    duracion_s: float
    terminaciones: tuple[str, ...]


def letras_seleccionadas(items: list[Any]) -> list[str]:
    """Las letras de los casos e2e que quedaron seleccionados, sin repetir y en orden."""
    letras = []
    for item in items:
        encontrada = _NOMBRE_DEL_TEST.match(getattr(item, "name", ""))
        if item.get_closest_marker("e2e") and encontrada and encontrada.group(1) not in letras:
            letras.append(encontrada.group(1))
    return letras


def entorno_del_caso(base: Mapping[str, str], caso: CasoE2E, carpeta: Path) -> dict[str, str]:
    """Una copia de `base` sin los modos del proceso, con la carpeta y los modos del caso."""
    entorno = {k: v for k, v in base.items() if k not in _MODOS_DEL_PROCESO}
    entorno[VARIABLE_RESULTADOS] = str(carpeta)
    entorno.update(caso.modos)
    return entorno


def _caso_real(entorno: Mapping[str, str]) -> Any:
    from due_diligence.coordinador import Caso

    return Caso(entorno=entorno)


def preparar_ejecuciones(
    letras: list[str],
    entorno: Mapping[str, str],
    carpeta_de: Callable[[str], Path],
    crear_caso: Callable[[Mapping[str, str]], Any] = _caso_real,
    paralelo: int = PARALELO_POR_DEFECTO,
    limite_s: float = LIMITE_POR_CASO_S,
) -> tuple[str | None, dict[str, Ejecucion]]:
    """El motivo para omitir (sin la credencial, sin crear ningún caso) o las ejecuciones."""
    problema = configuracion.comprobar_credencial(entorno)
    if problema is not None or not letras:
        return problema, {}
    ejecuciones = asyncio.run(
        _ejecutar_casos(letras, entorno, carpeta_de, crear_caso, paralelo, limite_s)
    )
    return None, ejecuciones


async def _ejecutar_casos(letras, entorno, carpeta_de, crear_caso, paralelo, limite_s):
    semaforo = asyncio.Semaphore(max(1, paralelo))
    tareas = [
        _ejecutar_uno(CASOS[letra], entorno, carpeta_de(letra), crear_caso, semaforo, limite_s)
        for letra in letras
    ]
    resultados = await asyncio.gather(*tareas, return_exceptions=True)
    return {
        letra: r if isinstance(r, Ejecucion) else Ejecucion((), r, None, 0.0, ())
        for letra, r in zip(letras, resultados, strict=True)
    }


async def _ejecutar_uno(caso_e2e, entorno, carpeta, crear_caso, semaforo, limite_s):
    async with semaforo:
        carpeta.mkdir(parents=True, exist_ok=True)
        caso = crear_caso(entorno_del_caso(entorno, caso_e2e, carpeta))
        inicio = time.monotonic()
        observaciones: list[Observacion] = []
        error: BaseException | None = None
        try:
            async with asyncio.timeout(limite_s):
                for numero, mensaje in enumerate(caso_e2e.mensajes):
                    if numero == 0:
                        await caso.ejecutar(mensaje)
                    else:
                        await caso.continuar(mensaje)
                    duracion = time.monotonic() - inicio
                    observaciones.append(observar(caso, leer_registros(carpeta), duracion))
        except Exception as fallo:  # tiempo agotado o fallo del SDK: el test lo explica (R2)
            error = fallo
        final = observar(caso, leer_registros(carpeta), time.monotonic() - inicio)
        return Ejecucion(
            tuple(observaciones),
            error,
            final.metricas.coste_usd,
            final.metricas.duracion_s,
            final.terminaciones,
        )


_EJECUCIONES = pytest.StashKey[dict[str, Ejecucion]]()


@pytest.fixture(scope="session")
def ejecuciones_e2e(request, tmp_path_factory):
    """Ejecuta una sola vez los casos e2e seleccionados (o devuelve el motivo para omitirlos)."""
    configuracion.cargar_entorno()
    entorno = dict(os.environ)
    try:
        paralelo = int(entorno.get(VARIABLE_PARALELO, PARALELO_POR_DEFECTO))
    except ValueError:
        paralelo = PARALELO_POR_DEFECTO
    base = tmp_path_factory.mktemp("e2e")
    problema, ejecuciones = preparar_ejecuciones(
        letras_seleccionadas(request.session.items),
        entorno,
        lambda letra: base / f"caso_{letra}",
        paralelo=paralelo,
    )
    request.config.stash[_EJECUCIONES] = ejecuciones
    return problema, ejecuciones


@pytest.fixture
def caso_e2e(ejecuciones_e2e):
    """`caso_e2e("d")`: las observaciones del caso, una por turno; omite sin la credencial."""
    problema, ejecuciones = ejecuciones_e2e

    def observaciones(letra: str) -> tuple[Observacion, ...]:
        if problema is not None:
            pytest.skip(problema)
        ejecucion = ejecuciones[letra]
        if ejecucion.error is not None or len(ejecucion.observaciones) != len(
            CASOS[letra].mensajes
        ):
            error = ejecucion.error
            causa = "sin error" if error is None else f"{type(error).__name__}: {error}"
            pytest.fail(
                f"El caso ({letra}) no terminó sus turnos ({causa}). Terminaciones: "
                f"{list(ejecucion.terminaciones)}. Coste gastado: {_usd(ejecucion.coste_usd)}. "
                f"Para repetir solo este caso: uv run pytest -m e2e -rs -k caso_{letra}"
            )
        return ejecucion.observaciones

    return observaciones


def _usd(coste: float | None) -> str:
    return "sin dato" if coste is None else f"{coste:.2f} USD".replace(".", ",")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    ejecuciones = config.stash.get(_EJECUCIONES, None)
    if not ejecuciones:
        return
    terminalreporter.section("coste y tiempo de los casos e2e (aproximado, R8)")
    for letra, ejecucion in ejecuciones.items():
        terminalreporter.write_line(
            f"e2e caso ({letra}): {_usd(ejecucion.coste_usd)}, {ejecucion.duracion_s:.0f} s"
        )
    conocidos = [e.coste_usd for e in ejecuciones.values() if e.coste_usd is not None]
    mayor = max(e.duracion_s for e in ejecuciones.values())
    total = _usd(sum(conocidos)) if conocidos else "sin dato"
    terminalreporter.write_line(f"e2e total: {total}; el caso más lento, {mayor:.0f} s")
