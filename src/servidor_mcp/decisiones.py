"""Los dos canales de decisión: registrar_informe y escalar_a_cumplimiento.

Son los únicos canales por los que sale una decisión (constitución IV). Exigen sus campos
obligatorios y nombran **todos** los que faltan (`campos_obligatorios_ausentes`, no
reintentable). Guardan lo recibido en una carpeta local que git no versiona. **No validan reglas
de negocio**: que una categoría de alto riesgo no reciba habilitación automática lo garantiza el
hook del SDK (ticket #7), no el servidor.
"""

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

from servidor_mcp import informe
from servidor_mcp.entradas import campos_obligatorios
from servidor_mcp.respuestas import error, hecho, respuesta

VARIABLE_CARPETA = "PASARELA_RESULTADOS_DIR"
FUENTE_INFORMES = "Registro local de informes (ficticio)"
FUENTE_ESCALAMIENTOS = "Registro local de escalamientos (ficticio)"

# Primer nivel del informe (#9): los que faltan se nombran todos con el error del #5; la forma de
# cada parte la valida `informe.validar_informe` (R2).
_REQUERIDOS_INFORME: dict[str, type | tuple[type, ...]] = {
    "comercio": dict,
    "recomendacion": str,
    "hallazgos": dict,
    "cobertura": (str, list),
    "conflictos": dict,
}
_REQUERIDOS_ESCALAMIENTO: dict[str, type | tuple[type, ...]] = {
    "comercio": dict,
    "hallazgos": dict,
    "cobertura": (str, list),
    "causa_escalamiento": str,
    "accion_recomendada": str,
}


def _ahora() -> datetime:
    """La hora del registro, en UTC como los eventos del caso (#9, R10)."""
    return datetime.now(UTC)


def carpeta_resultados() -> Path:
    """La carpeta de informes y casos escalados.

    Sale de `PASARELA_RESULTADOS_DIR`; si no está definida, es `resultados/` en la raíz del
    repositorio, calculada desde este archivo (`src/servidor_mcp/` → raíz). Queda fuera de
    `.claude/` y está en `.gitignore`.
    """
    configurada = os.environ.get(VARIABLE_CARPETA, "").strip()
    if configurada:
        return Path(configurada)
    return Path(__file__).resolve().parents[2] / "resultados"


def _anidados(
    prefijo: str, objeto: Any, requeridos: dict[str, type | tuple[type, ...]]
) -> tuple[list[str], str | None]:
    """Campos faltantes (con prefijo) y, si lo hay, el motivo de un tipo incorrecto."""
    err = campos_obligatorios(objeto, requeridos)
    if err is None:
        return [], None
    cuerpo = err.structured_content
    if cuerpo["tipo"] == "campos_obligatorios_ausentes":
        return [f"{prefijo}.{nombre}" for nombre in cuerpo["campos_faltantes"]], None
    return [], f"{prefijo}: {cuerpo['mensaje']}"


def _validar(entrada: dict[str, Any], requeridos: dict[str, Any]) -> CallToolResult | None:
    """Campos de primer nivel y, dentro de ellos, el comercio y la fuente de cada hallazgo."""
    err = campos_obligatorios(entrada, requeridos)
    if err is not None:
        return err
    faltantes: list[str] = []
    incorrectos: list[str] = []
    partes = [("comercio", entrada["comercio"], {"identificador": str, "nombre": str})]
    partes += [
        (f"hallazgos.{frente}", valor, {"contenido": str, "fuente": str})
        for frente, valor in entrada["hallazgos"].items()
    ]
    for prefijo, objeto, requeridos_anidados in partes:
        faltan, mal = _anidados(prefijo, objeto, requeridos_anidados)
        faltantes += faltan
        if mal:
            incorrectos.append(mal)
    if faltantes:
        lista = ", ".join(f"«{nombre}»" for nombre in faltantes)
        return error(
            "campos_obligatorios_ausentes",
            f"Faltan campos obligatorios: {lista}.",
            False,
            campos_faltantes=faltantes,
        )
    if incorrectos:
        return error(
            "entrada_invalida",
            "Campos con un tipo incorrecto: " + "; ".join(incorrectos) + ".",
            False,
        )
    return None


def _guardar(subcarpeta: str, prefijo: str, documento: dict[str, Any]) -> str | None:
    """Escribe el documento de forma atómica y devuelve su id, o `None` si no se pudo."""
    destino = carpeta_resultados() / subcarpeta
    temporal = None
    try:
        destino.mkdir(parents=True, exist_ok=True)
        identificador = f"{prefijo}-{uuid.uuid4().hex[:8]}"
        while (destino / f"{identificador}.json").exists():
            identificador = f"{prefijo}-{uuid.uuid4().hex[:8]}"
        temporal = destino / f"{identificador}.json.tmp"
        temporal.write_text(
            json.dumps({"id": identificador} | documento, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporal, destino / f"{identificador}.json")
        return identificador
    except OSError:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
        return None


def _resultado(
    estado: str, fuente: str, subcarpeta: str, prefijo: str, documento: dict[str, Any]
) -> CallToolResult:
    ahora = _ahora().astimezone(UTC)
    identificador = _guardar(subcarpeta, prefijo, {"registrado_en": ahora.isoformat()} | documento)
    if identificador is None:
        return error(
            "error_de_almacenamiento",
            "No se pudo guardar el registro en la carpeta de resultados.",
            False,
        )
    fecha = ahora.date().isoformat()
    return respuesta(estado, [hecho({"id": identificador}, fuente, fecha)], [fuente], fecha)


def registrar_informe(
    comercio: Any = None,
    recomendacion: Any = None,
    hallazgos: Any = None,
    conflictos: Any = None,
    cobertura: Any = None,
) -> CallToolResult:
    """Registra el informe: comercio, recomendación, afirmaciones, conflictos y cobertura (#9).

    Primero los campos de primer nivel (`campos_obligatorios_ausentes` o `entrada_invalida`, como
    en el #5); después la forma de cada parte con `informe.validar_informe`, que da
    `entrada_invalida` con **todos** los `problemas`. Un informe inválido nunca se guarda, ni en
    parte (FR-005).
    """
    entrada = {
        "comercio": comercio,
        "recomendacion": recomendacion,
        "hallazgos": hallazgos,
        "conflictos": conflictos,
        "cobertura": cobertura,
    }
    err = campos_obligatorios(entrada, _REQUERIDOS_INFORME, admite_vacio=("hallazgos",))
    if err is not None:
        return err
    problemas = informe.validar_informe(entrada)
    if problemas:
        return error(
            "entrada_invalida",
            informe.mensaje(problemas),
            False,
            problemas=[p.como_dict() for p in problemas],
        )
    return _resultado("informe_registrado", FUENTE_INFORMES, "informes", "INF", entrada)


def escalar_a_cumplimiento(
    comercio: Any = None,
    hallazgos: Any = None,
    cobertura: Any = None,
    causa_escalamiento: Any = None,
    accion_recomendada: Any = None,
) -> CallToolResult:
    """Escala el caso con el resumen autosuficiente que necesita el oficial de cumplimiento."""
    entrada = {
        "comercio": comercio,
        "hallazgos": hallazgos,
        "cobertura": cobertura,
        "causa_escalamiento": causa_escalamiento,
        "accion_recomendada": accion_recomendada,
    }
    err = _validar(entrada, _REQUERIDOS_ESCALAMIENTO)
    if err is not None:
        return err
    return _resultado("caso_escalado", FUENTE_ESCALAMIENTOS, "escalamientos", "ESC", entrada)
