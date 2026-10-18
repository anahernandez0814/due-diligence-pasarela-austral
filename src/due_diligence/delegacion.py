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
from mcp_types import ToolAnnotations

from due_diligence.contexto import FrenteRechazado, construir_contexto
from due_diligence.ejecutor import EjecutorSubagente
from due_diligence.estado import (
    Consulta,
    EstadoCaso,
    ResultadoFrente,
    Situacion,
)
from due_diligence.eventos import (
    TIPO_DELEGACION,
    TIPO_DELEGACION_REPETIDA,
    TIPO_FRENTE_FIN,
    TIPO_FRENTE_INICIO,
    TIPO_FRENTE_INVALIDADO,
    TIPO_FRENTE_RECHAZADO,
    RegistroEventos,
)
from due_diligence.frentes import HERRAMIENTA_DELEGAR, SERVIDOR_DELEGACION, Frente
from due_diligence.reglas import consulta_coincide
from due_diligence.terminacion import Clasificacion, Terminacion

DESCRIPCION = (
    "Delega un frente de la investigación en un subagente especializado y devuelve su resultado. "
    "Frentes: registro (registro mercantil), noticias, categoria (riesgo de categoría) y listas "
    "(listas restrictivas del comercio y de su representante legal; el comercio sale del resultado "
    "del registro, no hay que pasarlo). Los frentes registro, noticias y categoria son "
    "independientes: delégalos juntos, en la misma respuesta. listas necesita el registro. Pasa "
    "solo los datos que el frente necesita y nunca inventes uno: si falta, la delegación se "
    "rechaza. La categoría es el sector o producto del comercio, sin el canal de venta (por "
    "ejemplo «suplementos dietarios», no «venta en línea de suplementos dietarios»). Si "
    "consultar_riesgo_categoria devuelve categoria_desconocida, solo vuelve a delegar con un "
    "nombre del catálogo que aparezca en la solicitud. Repetir un frente con la misma entrada "
    "devuelve el resultado guardado; con otra entrada, vuelve a ejecutarlo. "
    "Esta herramienta no consulta fuentes por sí misma, no registra el informe ni escala "
    "el caso."
)

MOTIVO_REGISTRO_PRIMERO = (
    "Listas necesita el resultado del registro mercantil: delega primero el registro y vuelve a "
    "pedir listas cuando termine."
)

MOTIVO_COMERCIO_CAMBIO = "El comercio del registro cambió; vuelva a delegar listas."

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
        self._contextos: dict[Frente, str] = {}
        self.herramienta: SdkMcpTool[Any] = self._crear_herramienta()

    # ------------------------------------------------------------ servidor en proceso

    def _crear_herramienta(self) -> SdkMcpTool[Any]:
        # readOnlyHint: delegar un frente no modifica nada fuera del caso, y es la señal que el SDK
        # usa para ejecutar en paralelo las llamadas de un mismo turno (R4). Sin ella las serializa.
        @tool(
            HERRAMIENTA_DELEGAR,
            DESCRIPCION,
            ESQUEMA,
            annotations=ToolAnnotations(readOnlyHint=True),
        )
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

        await self._esperar_si_en_curso(frente)

        if frente is Frente.LISTAS:
            previa = await self._esperar_al_registro()
            if previa is not None:
                return previa
            # Esperar al registro cede el control: otra llamada a `listas` pudo lanzar el frente
            # mientras tanto. Desde esta última comprobación hasta `_ejecutar` no hay ningún await.
            await self._esperar_si_en_curso(frente)

        try:
            contexto = construir_contexto(frente, entrada, self.estado)
        except FrenteRechazado as rechazo:
            if frente in self._respuestas:  # ya tiene resultado: se conserva, no se rechaza
                motivo = str(rechazo)
                self.eventos.registrar(TIPO_FRENTE_RECHAZADO, frente, motivo)
                return _error("frente_rechazado", motivo, False, {"frente": frente.value})
            return self._rechazar(frente, str(rechazo))

        if frente in self._respuestas and self._contextos.get(frente) == contexto:
            self.eventos.registrar(
                TIPO_DELEGACION_REPETIDA,
                frente,
                f"Misma entrada que la anterior: se devuelve lo guardado de {frente.value}.",
            )
            return self._respuestas[frente]

        return await self._ejecutar(frente, contexto, repite=frente in self._respuestas)

    def _rechazar(self, frente: Frente, motivo: str, reintentable: bool = False) -> dict[str, Any]:
        self.estado.cambiar_situacion(frente, Situacion.RECHAZADO, motivo)
        self.eventos.registrar(TIPO_FRENTE_RECHAZADO, frente, motivo)
        return _error("frente_rechazado", motivo, reintentable, {"frente": frente.value})

    async def _esperar_si_en_curso(self, frente: Frente) -> None:
        """Espera mientras el frente siga en curso: un frente en curso no se lanza dos veces.

        Se vuelve a comprobar tras cada espera (otra llamada pudo relanzarlo). Es recursiva y no un
        `while` porque `test_sin_control_propio` prohíbe `while` en los módulos del ciclo (FR-010).
        """
        if self.estado.situacion(frente) is Situacion.EN_CURSO:
            await self._hecho[frente].wait()
            await self._esperar_si_en_curso(frente)

    async def _esperar_al_registro(self) -> dict[str, Any] | None:
        """El orden de `listas` (R4): espera al registro en curso; sin iniciar, se rechaza.

        Devuelve una respuesta si `listas` no debe seguir (rechazo reintentable) y `None` si puede
        continuar. Los rechazos por varias coincidencias,
        ninguna o un registro que no terminó no son reintentables: salen de `construir_contexto`.
        """
        situacion = self.estado.situacion(Frente.REGISTRO)
        if situacion in (Situacion.SIN_INICIAR, Situacion.RECHAZADO):
            return self._rechazar(Frente.LISTAS, MOTIVO_REGISTRO_PRIMERO, reintentable=True)
        if situacion is Situacion.EN_CURSO:
            await self._hecho[Frente.REGISTRO].wait()
        return None

    async def _ejecutar(
        self, frente: Frente, contexto: str, repite: bool = False
    ) -> dict[str, Any]:
        detalle = (
            f"Se vuelve a delegar el frente {frente.value} con otra entrada."
            if repite
            else f"Se delega el frente {frente.value}."
        )
        self.eventos.registrar(TIPO_DELEGACION, frente, detalle)
        # El comercio que ya estaba identificado se conserva para decidir, al concluir, si el nuevo
        # es otro y `listas` deja de valer. Se reinicia la identificación antes de lanzar el frente:
        # la registra el hook del registro durante esta ejecución (R4).
        anterior = self.estado.comercio if frente is Frente.REGISTRO else None
        if frente is Frente.REGISTRO:
            self.estado.reiniciar_identificacion()
        self.estado.cambiar_situacion(frente, Situacion.EN_CURSO)
        self._contextos[frente] = contexto
        self._hecho[frente].clear()
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
            return self._concluir(frente, resultado, anterior)
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
        if frente is Frente.LISTAS:
            faltante = self._falta_en_listas(resultado)
            if faltante:
                return Situacion.NO_TERMINADO, faltante
        return Situacion.TERMINADO, ""

    def _falta_en_listas(self, resultado: ResultadoFrente) -> str:
        """Comprueba que `listas` consultó al comercio y, si lo hay, a su representante (FR-005).

        Usa `reglas.consulta_coincide`, la misma comparación que el hook de la consulta de listas
        (R7): el tipo correcto (`comercio` o `persona`) y cada clave que trae la consulta debe
        existir en la entidad del registro y coincidir, con la normalización de
        `servidor_mcp.normalizar`.
        Devuelve el motivo si falta una, o "" si están ambas.
        """
        comercio = self.estado.comercio
        if comercio is None:
            return ""

        def consultada(tipo: str, entidad: Mapping[str, Any]) -> bool:
            return any(
                consulta_coincide(consulta.argumentos, entidad, tipo)
                for consulta in resultado.consultas
            )

        if not consultada("comercio", comercio):
            return "Falta la consulta del comercio en listas restrictivas (tipo comercio)."
        representante = comercio.get("representante_legal")
        if representante and not consultada("persona", representante):
            return (
                "Falta la consulta del representante legal en listas restrictivas (tipo persona)."
            )
        return ""

    def _concluir(
        self, frente: Frente, resultado: ResultadoFrente, anterior: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.estado.guardar_resultado(resultado)
        self.estado.agregar_consultas(resultado.consultas)
        situacion, motivo = self._evaluar(frente, resultado)
        self.estado.cambiar_situacion(frente, situacion, motivo)
        # El comercio ya no se deriva aquí: lo identifica el hook del registro (R4) y
        # `estado.comercio` lo consolida. Solo se compara con el que había antes de esta ejecución.
        if frente is Frente.REGISTRO and self.estado.comercio != anterior:
            self._invalidar_listas()
        detalle = f"{situacion.value}: {resultado.detalle_terminacion}"
        self.eventos.registrar(TIPO_FRENTE_FIN, frente, f"{detalle}. {motivo}".strip())
        respuesta = self._respuesta(frente, situacion, motivo, resultado)
        self._respuestas[frente] = respuesta
        return respuesta

    def _invalidar_listas(self) -> None:
        """El comercio del registro cambió: lo que `listas` encontró era de otro comercio.

        Pasa a `no_terminado` y olvida su entrada, para que volver a delegarla se ejecute aunque el
        comercio coincida con uno anterior. Un `listas` en curso no se toca (R13.10).
        """
        if self.estado.situacion(Frente.LISTAS) not in (
            Situacion.TERMINADO,
            Situacion.NO_TERMINADO,
        ):
            return
        self.estado.cambiar_situacion(Frente.LISTAS, Situacion.NO_TERMINADO, MOTIVO_COMERCIO_CAMBIO)
        self._contextos.pop(Frente.LISTAS, None)
        self.eventos.registrar(TIPO_FRENTE_INVALIDADO, Frente.LISTAS, MOTIVO_COMERCIO_CAMBIO)

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
