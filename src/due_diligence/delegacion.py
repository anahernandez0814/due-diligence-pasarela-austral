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

from due_diligence.configuracion import MAX_REINTENTOS_POR_FRENTE
from due_diligence.contexto import FrenteRechazado, construir_contexto
from due_diligence.ejecutor import EjecutorSubagente, es_bloqueo_de_hook
from due_diligence.estado import (
    Causa,
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
    TIPO_FRENTE_REINTENTO,
    TIPO_REINTENTO_DENEGADO,
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
    "devuelve el resultado guardado si terminó; con otra entrada, vuelve a ejecutarlo. Si un "
    "frente devolvió un error con reintentable true, se puede pedir una vez más con la misma "
    "entrada; con reintentable false no se vuelve a ejecutar: sigue con los demás frentes. "
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


MOTIVO_CANCELADO = "Se canceló el frente."


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


def _error_de_frente(
    tipo: str,
    frente: Frente,
    causa: Causa,
    mensaje: str,
    reintentable: bool,
    obtenido: dict[str, Any] | None = None,
    *,
    intento: int,
    reintentos_restantes: int,
) -> dict[str, Any]:
    """El `ErrorFrente` del #8 (data-model, contrato `delegar-frente.md`).

    `tipo` se conserva por compatibilidad con el #6; el «tipo de error» de FR-002 es `causa`.
    `reintentable` es verdadero solo si la causa lo es **y** quedan reintentos (R3).
    `reintentos_restantes` nunca baja de 0 (data-model).
    """
    reintentos_restantes = max(0, reintentos_restantes)
    return {
        **_error(tipo, mensaje, reintentable and reintentos_restantes > 0, obtenido),
        "frente": frente.value,
        "causa": causa.value,
        "intento": intento,
        "reintentos_restantes": reintentos_restantes,
    }


def _rechazo(frente: Frente, motivo: str, reintentable: bool = False) -> dict[str, Any]:
    """Un rechazo sin ejecución: no lanza al subagente ni consume reintentos (FR-003)."""
    return _error_de_frente(
        "frente_rechazado",
        frente,
        Causa.RECHAZADO,
        motivo,
        reintentable,
        {"frente": frente.value},
        intento=0,
        reintentos_restantes=MAX_REINTENTOS_POR_FRENTE,
    )


def _nombre_corto(herramienta: str) -> str:
    return herramienta.rsplit("__", 1)[-1]


def _errores_reales(respuesta: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Los errores de la fuente de una respuesta, sin los bloqueos de hook (#7)."""
    obtenido = respuesta.get("obtenido") or {}
    return [e for e in obtenido.get("errores") or [] if not es_bloqueo_de_hook(e)]


def _fuente_reintentable(respuesta: Mapping[str, Any]) -> bool:
    """Si la causa del error es reintentable por sí misma, sin contar los reintentos que quedan."""
    reales = _errores_reales(respuesta)
    return (
        respuesta.get("causa") == Causa.ERROR_DE_FUENTE
        and bool(reales)
        and all(e.get("reintentable") is True for e in reales)
    )


def _causa_legible(respuesta: Mapping[str, Any]) -> str:
    """La causa de un error, en palabras, para los eventos de reintento (FR-009)."""
    if respuesta.get("causa") == Causa.ERROR_DE_FUENTE:
        tipos = ", ".join(str(e.get("tipo")) for e in _errores_reales(respuesta))
        return f"error de la fuente: {tipos}"
    return str(respuesta.get("causa", "")).replace("_", " ")


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
        # Historial de la política de reintento (#8, R3): ejecuciones y último resultado por
        # `(frente, contexto)`. El contexto lo construye el código desde la entrada, así que «la
        # misma entrada» es exactamente la misma clave, sea o no la última del frente.
        self._intentos: dict[tuple[Frente, str], int] = {}
        self._ultimo: dict[tuple[Frente, str], dict[str, Any]] = {}
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

        espero = await self._esperar_si_en_curso(frente)

        if frente is Frente.LISTAS:
            previa = await self._esperar_al_registro()
            if previa is not None:
                return previa
            # Esperar al registro cede el control: otra llamada a `listas` pudo lanzar el frente
            # mientras tanto. Desde esta última comprobación hasta `_ejecutar` no hay ningún await.
            espero = await self._esperar_si_en_curso(frente) or espero

        try:
            contexto = construir_contexto(frente, entrada, self.estado)
        except FrenteRechazado as rechazo:
            if frente in self._respuestas:  # ya tiene resultado: se conserva, no se rechaza
                motivo = str(rechazo)
                self.eventos.registrar(TIPO_FRENTE_RECHAZADO, frente, motivo)
                return _rechazo(frente, motivo)
            return self._rechazar(frente, str(rechazo))

        clave = (frente, contexto)
        ultimo = self._ultimo.get(clave)
        actual = frente in self._respuestas and self._contextos.get(frente) == contexto
        # Un error de esta entrada sigue la política aunque después se delegara otra (A, B, A):
        # alternar entradas no da más intentos que los del límite.
        if ultimo is not None and (actual or ultimo.get("error")):
            return await self._misma_entrada(frente, contexto, ultimo, espero and actual)
        if ultimo is not None:
            # Terminó, pero el frente se delegó después con otra entrada: es una delegación nueva,
            # como en el #6 (un registro A, B, A vuelve a identificar A), y su cuenta empieza de 0.
            self._intentos[clave] = 0

        return await self._ejecutar(frente, contexto, repite=frente in self._respuestas)

    async def _misma_entrada(
        self, frente: Frente, contexto: str, guardada: dict[str, Any], espero: bool
    ) -> dict[str, Any]:
        """La política de reintento con la misma entrada (#8, R3, contrato `delegar-frente.md`).

        `guardada` es el último resultado de esta entrada, sea o no la última del frente.

        - Terminado, o una llamada que esperó a esa misma ejecución en curso: lo guardado.
        - Error con `reintentable` (la causa lo es y quedan reintentos): se ejecuta de nuevo.
        - En otro caso: el mismo error con `reintentable: false` y sin reintentos, sin ejecutar ni
          cambiar el estado del caso.
        """
        if espero or not guardada.get("error"):
            self.eventos.registrar(
                TIPO_DELEGACION_REPETIDA,
                frente,
                f"Misma entrada que la anterior: se devuelve lo guardado de {frente.value}.",
            )
            return guardada
        if guardada.get("reintentable") is True:
            intento = self._intentos.get((frente, contexto), 0) + 1
            self.eventos.registrar(
                TIPO_FRENTE_REINTENTO,
                frente,
                f"Reintento {intento - 1} de {MAX_REINTENTOS_POR_FRENTE} del frente "
                f"{frente.value}: el intento anterior falló ({_causa_legible(guardada)}).",
            )
            return await self._ejecutar(frente, contexto, reintento=True)
        motivo = (
            "se agotaron los reintentos"
            if guardada.get("reintentos_restantes") == 0 and _fuente_reintentable(guardada)
            else "el error no es reintentable"
        )
        self.eventos.registrar(
            TIPO_REINTENTO_DENEGADO, frente, f"No se reintenta el frente {frente.value}: {motivo}."
        )
        return {**guardada, "reintentable": False, "reintentos_restantes": 0}

    def _rechazar(self, frente: Frente, motivo: str, reintentable: bool = False) -> dict[str, Any]:
        self.estado.cambiar_situacion(frente, Situacion.RECHAZADO, motivo)
        self.eventos.registrar(TIPO_FRENTE_RECHAZADO, frente, motivo)
        respuesta = _rechazo(frente, motivo, reintentable)
        self.estado.errores[frente] = respuesta
        return respuesta

    async def _esperar_si_en_curso(self, frente: Frente) -> bool:
        """Espera mientras el frente siga en curso: un frente en curso no se lanza dos veces.

        Se vuelve a comprobar tras cada espera (otra llamada pudo relanzarlo). Es recursiva y no un
        `while` porque `test_sin_control_propio` prohíbe `while` en los módulos del ciclo (FR-010).
        Devuelve si esperó: una llamada que esperó recibe el resultado de esa ejecución y no
        reintenta (#8, R3, pedidos simultáneos).
        """
        if self.estado.situacion(frente) is Situacion.EN_CURSO:
            await self._hecho[frente].wait()
            await self._esperar_si_en_curso(frente)
            return True
        return False

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
        self, frente: Frente, contexto: str, repite: bool = False, reintento: bool = False
    ) -> dict[str, Any]:
        if reintento:
            detalle = f"Se reintenta el frente {frente.value} con la misma entrada."
        elif repite:
            detalle = f"Se vuelve a delegar el frente {frente.value} con otra entrada."
        else:
            detalle = f"Se delega el frente {frente.value}."
        self.eventos.registrar(TIPO_DELEGACION, frente, detalle)
        # Cada lanzamiento del subagente con esta entrada es un intento (#8, R3).
        clave = (frente, contexto)
        intento = self._intentos.get(clave, 0) + 1
        self._intentos[clave] = intento
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
                # Solo el tipo de la excepción: su texto interno no llega al modelo, a los
                # eventos ni al estado (US2-7 del #8), como en `hooks._registrar_fallo` del #7.
                detalle = f"excepción {type(error).__name__}"
                resultado = ResultadoFrente(
                    frente,
                    [],
                    "",
                    Clasificacion(Terminacion.ANOMALA, None, None, detalle, True),
                    detalle,
                )
            respuesta = self._concluir(frente, resultado, anterior, intento)
            self._ultimo[clave] = respuesta
            return respuesta
        finally:
            if self.estado.situacion(frente) is Situacion.EN_CURSO:  # cancelado: no se pierde
                self.estado.cambiar_situacion(frente, Situacion.NO_TERMINADO, MOTIVO_CANCELADO)
                cancelado = _error_de_frente(
                    "frente_no_terminado",
                    frente,
                    Causa.CANCELADO,
                    MOTIVO_CANCELADO,
                    False,
                    {"frente": frente.value, "resultados": [], "errores": [], "terminacion": ""},
                    intento=intento,
                    reintentos_restantes=MAX_REINTENTOS_POR_FRENTE - (intento - 1),
                )
                # También es lo guardado del frente: con la misma entrada no se vuelve a ejecutar,
                # una llamada que esperaba recibe este error y un rechazo posterior no lo pisa.
                self._respuestas[frente] = cancelado
                self._ultimo[clave] = cancelado
                self.estado.errores[frente] = cancelado
            self._hecho[frente].set()

    # ------------------------------------------------------------ resultado de un frente

    def _evaluar(
        self, frente: Frente, resultado: ResultadoFrente
    ) -> tuple[Situacion, str, Causa | None]:
        """(situación final, motivo, causa) de un frente según cómo terminó y qué devolvió.

        El orden de las comprobaciones es la prioridad de las causas (data-model del #8).
        """
        clasificacion = resultado.terminacion
        if clasificacion is None or clasificacion.terminacion is not Terminacion.NORMAL:
            donde = resultado.detalle_terminacion
            return (
                Situacion.NO_TERMINADO,
                f"El subagente no terminó con normalidad ({donde}).",
                Causa.TERMINACION_ANOMALA,
            )
        # Un intento que un hook bloqueó (regla I.1) no cuenta contra el frente: queda como evento
        # de la regla y como traza en el estado, pero decide lo que sí se consultó (#7).
        efectivas = [c for c in resultado.consultas if not es_bloqueo_de_hook(c.error)]
        errores = [c.error for c in efectivas if c.error]
        if errores:
            tipos = ", ".join(str(e.get("tipo")) for e in errores)
            return (
                Situacion.NO_TERMINADO,
                f"La herramienta devolvió un error estructurado ({tipos}).",
                Causa.ERROR_DE_FUENTE,
            )
        if not efectivas:
            return (
                Situacion.NO_TERMINADO,
                "El subagente no hizo ninguna consulta.",
                Causa.SIN_CONSULTAS,
            )
        if any(not c.valido for c in efectivas):
            return (
                Situacion.NO_TERMINADO,
                "Un resultado no tiene la forma del contrato de la pasarela.",
                Causa.RESULTADO_INVALIDO,
            )
        if frente is Frente.LISTAS:
            faltante = self._falta_en_listas(resultado)
            if faltante:
                return Situacion.NO_TERMINADO, faltante, Causa.CONSULTA_INCOMPLETA
        return Situacion.TERMINADO, "", None

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
                consulta.valido and consulta_coincide(consulta.argumentos, entidad, tipo)
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
        self,
        frente: Frente,
        resultado: ResultadoFrente,
        anterior: dict[str, Any] | None = None,
        intento: int = 1,
    ) -> dict[str, Any]:
        self.estado.guardar_resultado(resultado)
        self.estado.agregar_consultas(resultado.consultas)
        situacion, motivo, causa = self._evaluar(frente, resultado)
        self.estado.cambiar_situacion(frente, situacion, motivo)
        # El comercio ya no se deriva aquí: lo identifica el hook del registro (R4) y
        # `estado.comercio` lo consolida. Solo se compara con el que había antes de esta ejecución.
        if frente is Frente.REGISTRO and self.estado.comercio != anterior:
            self._invalidar_listas()
        detalle = f"{situacion.value}: {resultado.detalle_terminacion}"
        self.eventos.registrar(TIPO_FRENTE_FIN, frente, f"{detalle}. {motivo}".strip())
        respuesta = self._respuesta(frente, situacion, motivo, causa, resultado, intento)
        self._respuestas[frente] = respuesta
        # Último error de cada frente no cubierto (#8): un frente que termina bien lo borra.
        if situacion is Situacion.TERMINADO:
            self.estado.errores.pop(frente, None)
        else:
            self.estado.errores[frente] = respuesta
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
        # Y su historial (data-model, «Historial de intentos»): listas empieza de cero aunque el
        # registro vuelva a un comercio anterior.
        self._intentos = {c: n for c, n in self._intentos.items() if c[0] is not Frente.LISTAS}
        self._ultimo = {c: r for c, r in self._ultimo.items() if c[0] is not Frente.LISTAS}
        self.eventos.registrar(TIPO_FRENTE_INVALIDADO, Frente.LISTAS, MOTIVO_COMERCIO_CAMBIO)
        # Solo en el estado y la cobertura: volver a delegar listas es una ejecución nueva (#6).
        self.estado.errores[Frente.LISTAS] = _error_de_frente(
            "frente_no_terminado",
            Frente.LISTAS,
            Causa.INVALIDADO,
            MOTIVO_COMERCIO_CAMBIO,
            False,
            {"frente": Frente.LISTAS.value},
            intento=0,
            reintentos_restantes=MAX_REINTENTOS_POR_FRENTE,
        )

    def _respuesta(
        self,
        frente: Frente,
        situacion: Situacion,
        motivo: str,
        causa: Causa | None,
        resultado: ResultadoFrente,
        intento: int = 1,
    ) -> dict[str, Any]:
        if situacion is Situacion.TERMINADO:
            return {
                "frente": frente.value,
                "situacion": situacion.value,
                "resultados": [self._resultado_de(c) for c in resultado.consultas if c.valido],
                "resumen": resultado.resumen,
            }
        obtenido = {
            "frente": frente.value,
            "resultados": [self._resultado_de(c) for c in resultado.consultas if c.valido],
            "errores": [c.error for c in resultado.consultas if c.error],
            "terminacion": resultado.detalle_terminacion,
        }
        # Solo un error de la fuente que la fuente declara reintentable lo es (FR-003): un
        # indicador ausente o que no es exactamente `True` cuenta como no reintentable.
        reintentable = _fuente_reintentable({"causa": causa, "obtenido": obtenido})
        return _error_de_frente(
            "frente_no_terminado",
            frente,
            causa or Causa.TERMINACION_ANOMALA,
            motivo,
            reintentable,
            obtenido,
            intento=intento,
            reintentos_restantes=MAX_REINTENTOS_POR_FRENTE - (intento - 1),
        )

    @staticmethod
    def _resultado_de(consulta: Consulta) -> dict[str, Any]:
        return {
            "herramienta": _nombre_corto(consulta.herramienta),
            "argumentos": consulta.argumentos,
            **(consulta.resultado or {}),
        }
