"""Herramienta `delegar_frente`: la única vía de delegación del coordinador (R1, R4, FR-002).

El coordinador no consulta fuentes: delega cada frente con esta herramienta, que lanza al subagente
con el ejecutor del caso. Aquí viven las garantías del ticket que no deben depender del modelo:
el contexto explícito de cada subagente (construido por el código), el estado y los eventos de
cada frente y el rechazo de lo que no tiene los datos necesarios.
"""

import asyncio
import json
from collections.abc import Callable, Mapping
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, SdkMcpTool, create_sdk_mcp_server, tool

from due_diligence.contexto import FrenteRechazado, construir_contexto
from due_diligence.ejecutor import EjecutorSubagente
from due_diligence.estado import (
    Consulta,
    EstadoCaso,
    ResultadoFrente,
    Situacion,
    derivar_comercio,
)
from due_diligence.eventos import (
    TIPO_DELEGACION,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
    TIPO_FRENTE_RECHAZADO,
    RegistroEventos,
)
from due_diligence.frentes import HERRAMIENTA_DELEGAR, SERVIDOR_DELEGACION, Frente
from due_diligence.terminacion import Clasificacion, Terminacion

DESCRIPCION = (
    "Delega un frente de la investigación en un subagente especializado y devuelve su resultado. "
    "Frentes: registro (registro mercantil), noticias, categoria (riesgo de categoría) y listas "
    "(listas restrictivas del comercio y de su representante legal; el comercio sale del resultado "
    "del registro, no hay que pasarlo). Los frentes registro, noticias y categoria son "
    "independientes: delégalos juntos, en la misma respuesta. listas necesita el registro. Pasa "
    "solo los datos que el frente necesita y nunca inventes uno: si falta, la delegación se "
    "rechaza. Esta herramienta no consulta fuentes por sí misma, no registra el informe ni escala "
    "el caso."
)

ESQUEMA = {
    "type": "object",
    "properties": {
        "frente": {
            "type": "string",
            "enum": [f.value for f in Frente],
            "description": "Frente a delegar.",
        },
        "identificador": {
            "type": "string",
            "description": "Identificador del comercio (frentes registro y noticias).",
        },
        "nombre": {
            "type": "string",
            "description": "Nombre del comercio, si no hay identificador (registro y noticias).",
        },
        "categoria": {
            "type": "string",
            "description": "Categoría de negocio que aporta el analista (frente categoria).",
        },
    },
    "required": ["frente"],
}


def _error(
    tipo: str, mensaje: str, reintentable: bool, obtenido: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "error": True,
        "tipo": tipo,
        "mensaje": mensaje,
        "reintentable": reintentable,
        "obtenido": obtenido or {},
    }


def _nombre_corto(herramienta: str) -> str:
    return herramienta.rsplit("__", 1)[-1]


class Delegador:
    """La delegación de un caso: su estado, sus eventos y su ejecutor. Sin estado de módulo."""

    def __init__(
        self,
        estado: EstadoCaso,
        eventos: RegistroEventos,
        ejecutor: EjecutorSubagente,
        opciones_subagente: Callable[[Frente], ClaudeAgentOptions],
    ) -> None:
        self.estado = estado
        self.eventos = eventos
        self._ejecutor = ejecutor
        self._opciones = opciones_subagente
        self._hecho: dict[Frente, asyncio.Event] = {f: asyncio.Event() for f in Frente}
        self._respuestas: dict[Frente, dict[str, Any]] = {}
        self.herramienta: SdkMcpTool[Any] = self._crear_herramienta()

    # ------------------------------------------------------------ servidor en proceso

    def _crear_herramienta(self) -> SdkMcpTool[Any]:
        @tool(HERRAMIENTA_DELEGAR, DESCRIPCION, ESQUEMA)
        async def delegar_frente(args: dict[str, Any]) -> dict[str, Any]:
            respuesta = await self.delegar(args)
            return {
                "content": [{"type": "text", "text": json.dumps(respuesta, ensure_ascii=False)}],
                "is_error": bool(respuesta.get("error")),
            }

        return delegar_frente

    def servidor(self) -> Any:
        return create_sdk_mcp_server(SERVIDOR_DELEGACION, tools=[self.herramienta])

    # ------------------------------------------------------------ delegación

    async def delegar(self, entrada: Mapping[str, Any]) -> dict[str, Any]:
        try:
            frente = Frente(entrada.get("frente"))
        except ValueError:
            valores = ", ".join(f.value for f in Frente)
            return _error(
                "entrada_invalida", f"El frente debe ser uno de: {valores}.", reintentable=False
            )

        repetida = await self._si_ya_delegado(frente)
        if repetida is not None:
            return repetida

        try:
            contexto = construir_contexto(frente, entrada, self.estado)
        except FrenteRechazado as rechazo:
            return self._rechazar(frente, str(rechazo))

        return await self._ejecutar(frente, contexto)

    async def _si_ya_delegado(self, frente: Frente) -> dict[str, Any] | None:
        """Un frente en curso o ya terminado no lanza otro subagente: devuelve lo guardado."""
        situacion = self.estado.situacion(frente)
        if situacion is Situacion.EN_CURSO:
            await self._hecho[frente].wait()
            situacion = self.estado.situacion(frente)
        if situacion in (Situacion.TERMINADO, Situacion.NO_TERMINADO):
            return self._respuestas[frente]
        return None

    def _rechazar(self, frente: Frente, motivo: str) -> dict[str, Any]:
        self.estado.cambiar_situacion(frente, Situacion.RECHAZADO, motivo)
        self.eventos.registrar(TIPO_FRENTE_RECHAZADO, frente, motivo)
        return _error("frente_rechazado", motivo, False, {"frente": frente.value})

    async def _ejecutar(self, frente: Frente, contexto: str) -> dict[str, Any]:
        self.eventos.registrar(TIPO_DELEGACION, frente, f"Se delega el frente {frente.value}.")
        self.estado.cambiar_situacion(frente, Situacion.EN_CURSO)
        self.eventos.registrar(TIPO_FRENTE_INICIO, frente, f"Contexto entregado: {contexto}")
        try:
            try:
                resultado = await self._ejecutor(frente, contexto, self._opciones(frente))
            except Exception as error:  # el subagente falló: se conserva como no terminado
                resultado = ResultadoFrente(
                    frente,
                    [],
                    "",
                    Clasificacion(
                        Terminacion.ANOMALA, None, None, f"excepción {type(error).__name__}", True
                    ),
                    f"excepción {type(error).__name__}: {error}",
                )
            return self._concluir(frente, resultado)
        finally:
            if self.estado.situacion(frente) is Situacion.EN_CURSO:  # cancelado: no se pierde
                self.estado.cambiar_situacion(
                    frente, Situacion.NO_TERMINADO, "Se canceló el frente."
                )
            self._hecho[frente].set()

    # ------------------------------------------------------------ resultado de un frente

    def _evaluar(self, frente: Frente, resultado: ResultadoFrente) -> tuple[Situacion, str]:
        """(situación final, motivo) de un frente según cómo terminó y qué devolvió."""
        clasificacion = resultado.terminacion
        if clasificacion is None or clasificacion.terminacion is not Terminacion.NORMAL:
            donde = resultado.detalle_terminacion
            return Situacion.NO_TERMINADO, f"El subagente no terminó con normalidad ({donde})."
        errores = [c.error for c in resultado.consultas if c.error]
        if errores:
            tipos = ", ".join(str(e.get("tipo")) for e in errores)
            return (
                Situacion.NO_TERMINADO,
                f"La herramienta devolvió un error estructurado ({tipos}).",
            )
        if not resultado.consultas:
            return Situacion.NO_TERMINADO, "El subagente no hizo ninguna consulta."
        if any(not c.valido for c in resultado.consultas):
            return (
                Situacion.NO_TERMINADO,
                "Un resultado no tiene la forma del contrato de la pasarela.",
            )
        return Situacion.TERMINADO, ""

    def _concluir(self, frente: Frente, resultado: ResultadoFrente) -> dict[str, Any]:
        self.estado.guardar_resultado(resultado)
        self.estado.agregar_consultas(resultado.consultas)
        situacion, motivo = self._evaluar(frente, resultado)
        self.estado.cambiar_situacion(frente, situacion, motivo)
        if frente is Frente.REGISTRO:
            self._fijar_comercio(situacion, motivo, resultado)
        detalle = f"{situacion.value}: {resultado.detalle_terminacion}"
        self.eventos.registrar(TIPO_FRENTE_FIN, frente, f"{detalle}. {motivo}".strip())
        respuesta = self._respuesta(frente, situacion, motivo, resultado)
        self._respuestas[frente] = respuesta
        return respuesta

    def _fijar_comercio(
        self, situacion: Situacion, motivo: str, resultado: ResultadoFrente
    ) -> None:
        """Deriva el comercio del registro, tal como lo devolvió (FR-005, FR-013)."""
        if situacion is not Situacion.TERMINADO:
            self.estado.fijar_comercio(None, f"El registro mercantil no terminó. {motivo}".strip())
            return
        motivos = []
        for consulta in resultado.consultas:
            comercio, razon = derivar_comercio(consulta.resultado)
            if comercio is not None:
                self.estado.fijar_comercio(comercio)
                return
            motivos.append(razon)
        self.estado.fijar_comercio(
            None, motivos[0] if motivos else "El registro no devolvió datos."
        )

    def _respuesta(
        self, frente: Frente, situacion: Situacion, motivo: str, resultado: ResultadoFrente
    ) -> dict[str, Any]:
        if situacion is Situacion.TERMINADO:
            return {
                "frente": frente.value,
                "situacion": situacion.value,
                "resultados": [self._resultado_de(c) for c in resultado.consultas],
                "resumen": resultado.resumen,
            }
        errores = [c.error for c in resultado.consultas if c.error]
        reintentable = bool(errores) and all(e.get("reintentable") is True for e in errores)
        return _error(
            "frente_no_terminado",
            motivo,
            reintentable,
            {
                "frente": frente.value,
                "resultados": [self._resultado_de(c) for c in resultado.consultas if c.valido],
                "errores": errores,
                "terminacion": resultado.detalle_terminacion,
            },
        )

    @staticmethod
    def _resultado_de(consulta: Consulta) -> dict[str, Any]:
        return {
            "herramienta": _nombre_corto(consulta.herramienta),
            "argumentos": consulta.argumentos,
            **(consulta.resultado or {}),
        }
