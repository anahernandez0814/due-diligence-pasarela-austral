"""El coordinador y el caso (contrato `caso.md`, R1, R5, R7; FR-001, FR-002, FR-010).

Un `Caso` agrupa el estado, el registro de eventos y la delegación de una solicitud. El ciclo
agéntico del coordinador lo ejecuta el SDK: aquí solo se consume el flujo con `async for` y se
clasifica cómo terminó, sin contadores ni comparación de texto (FR-010).
"""

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from claude_agent_sdk._errors import ResultError

from due_diligence import configuracion
from due_diligence.contexto import instrucciones
from due_diligence.delegacion import Delegador
from due_diligence.ejecutor import EjecutorSDK, EjecutorSubagente
from due_diligence.estado import EstadoCaso
from due_diligence.eventos import (
    TIPO_CASO_INICIADO,
    TIPO_TERMINACION,
    Evento,
    RegistroEventos,
)
from due_diligence.frentes import Frente
from due_diligence.hooks import HooksDelCaso
from due_diligence.terminacion import (
    Clasificacion,
    Terminacion,
    clasificar_error,
    clasificar_resultado,
    sin_resultado,
)

# Instrucción, no garantía: los canales de decisión siguen entre las herramientas del coordinador
# (FR-002) y los hooks del #7 son los que cerrarán esta desviación temporal del principio II.
PROHIBICION_DECISION = (
    "NO llames a registrar_informe ni a escalar_a_cumplimiento: esa función aún no está "
    "disponible. Tus herramientas incluyen ambas, pero no las uses; limítate a delegar y a resumir."
)

INSTRUCCIONES_COORDINADOR = f"""\
Eres el coordinador del due diligence de comercios de la pasarela de pagos Pasarela Austral. \
Atiendes a un analista interno y le hablas siempre de usted, sin tutearlo ni mencionar \
tickets. Descompones su solicitud en frentes y delegas cada uno en un subagente especializado.

Reglas:
1. No consultas fuentes: solo delegas con la herramienta delegar_frente. Los frentes registro, \
noticias y categoria son independientes: delégalos juntos, en la misma respuesta (varias \
llamadas a delegar_frente a la vez). Después delega listas: usa el comercio que devolvió el \
registro y no pases datos, porque salen del resultado del registro.
2. A cada frente pásale solo los datos que aparecen en la solicitud: el identificador o el nombre \
del comercio y la categoría de negocio. Nunca inventes un identificador, un nombre, una categoría \
ni un representante legal. Si falta un dato, no delegues el frente que lo necesita y dilo. La \
categoría es el sector o producto del comercio, sin el canal de venta («suplementos dietarios», no \
«venta en línea de suplementos dietarios»). Si la herramienta de categoría devuelve \
categoria_desconocida, solo vuelve a delegar con un nombre del catálogo que aparezca en la \
solicitud; si ninguno aparece, pide confirmación al analista.
3. Si el registro devuelve varias coincidencias, no elijas una ni sigas con listas: informa las \
coincidencias y pide al analista el identificador.
4. {PROHIBICION_DECISION}
5. Al terminar, resume al analista, frente por frente, lo que se obtuvo con su fuente y su fecha, \
y qué frentes no se pudieron cubrir y por qué. No decidas la habilitación del comercio.
"""


class Caso:
    """Una ejecución del due diligence: su estado, sus eventos y su delegación (FR-014)."""

    def __init__(
        self,
        *,
        ejecutor: EjecutorSubagente | None = None,
        consulta: Callable[..., Any] | None = None,
        reloj: Callable[[], datetime] | None = None,
        entorno: Mapping[str, str] | None = None,
    ) -> None:
        self.estado = EstadoCaso()
        self._eventos = RegistroEventos(reloj)
        # Los hooks de las reglas (#7, R5) cierran sobre el estado y los eventos de este caso y se
        # reparten por agente. No se pueden desactivar desde fuera: no hay parámetro `hooks`.
        self.hooks = HooksDelCaso(self.estado, self._eventos, entorno)
        self.entorno = entorno
        self._consulta = consulta or query
        self.delegador = Delegador(
            self.estado, self._eventos, ejecutor or EjecutorSDK(), self._opciones_subagente
        )
        self.respuesta = ""
        self.coste_usd: float | None = None  # `total_cost_usd` del coordinador

    def eventos(self) -> list[Evento]:
        return self._eventos.eventos()

    @property
    def terminacion(self) -> Clasificacion | None:
        return self.estado.terminacion

    def _opciones_subagente(self, frente: Frente) -> ClaudeAgentOptions:
        return configuracion.opciones_subagente(
            frente,
            instrucciones(frente),
            hooks=self.hooks.subagente(frente),
            entorno=self.entorno,
        )

    def opciones_coordinador(self) -> ClaudeAgentOptions:
        return configuracion.opciones_coordinador(
            self.delegador.servidor(),
            INSTRUCCIONES_COORDINADOR,
            hooks=self.hooks.coordinador(),
            entorno=self.entorno,
        )

    async def ejecutar(self, solicitud: str) -> str:
        """Ejecuta el ciclo del coordinador y devuelve su respuesta final al analista."""
        self.estado.solicitud = solicitud
        self._eventos.registrar(TIPO_CASO_INICIADO, None, "Se inicia el caso.")
        clasificacion: Clasificacion | None = None
        try:
            async for mensaje in self._consulta(
                prompt=solicitud, options=self.opciones_coordinador()
            ):
                if isinstance(mensaje, AssistantMessage):
                    for bloque in mensaje.content:
                        if isinstance(bloque, TextBlock):
                            self.respuesta = bloque.text
                elif isinstance(mensaje, ResultMessage):
                    clasificacion = clasificar_resultado(mensaje)
                    self.coste_usd = mensaje.total_cost_usd
        except ResultError as error:
            # El SDK la lanza después del ResultMessage: solo se clasifica si no se vio antes.
            if clasificacion is None:
                clasificacion = clasificar_error(error)
        except Exception as error:
            # Otro fallo del SDK (conexión, proceso): queda constancia del corte y se relanza.
            clasificacion = Clasificacion(
                Terminacion.ANOMALA, None, None, f"excepción {type(error).__name__}", True
            )
            self._terminar(clasificacion)
            raise
        if clasificacion is None:
            clasificacion = sin_resultado()
        self._terminar(clasificacion)
        return self.respuesta

    def _terminar(self, clasificacion: Clasificacion) -> None:
        self.estado.terminacion = clasificacion
        self._eventos.registrar(
            TIPO_TERMINACION, None, f"{clasificacion.terminacion.value}: {clasificacion.detalle}"
        )


async def ejecutar_caso(
    solicitud: str,
    *,
    ejecutor: EjecutorSubagente | None = None,
    consulta: Callable[..., Any] | None = None,
    reloj: Callable[[], datetime] | None = None,
    entorno: Mapping[str, str] | None = None,
) -> Caso:
    """Crea un caso, lo ejecuta y lo devuelve. No carga el entorno (R8): lo hace `__main__`."""
    caso = Caso(ejecutor=ejecutor, consulta=consulta, reloj=reloj, entorno=entorno)
    await caso.ejecutar(solicitud)
    return caso
