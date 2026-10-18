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
from due_diligence.cobertura import CoberturaCaso, calcular_cobertura
from due_diligence.conflictos import ConflictosCaso, calcular_conflictos
from due_diligence.contexto import instrucciones
from due_diligence.delegacion import Delegador
from due_diligence.ejecutor import EjecutorSDK, EjecutorSubagente
from due_diligence.estado import EstadoCaso
from due_diligence.eventos import (
    TIPO_CASO_INICIADO,
    TIPO_MODO_DEMOSTRACION,
    TIPO_TERMINACION,
    Evento,
    RegistroEventos,
)
from due_diligence.frentes import Frente
from due_diligence.hooks import HooksDelCaso
from due_diligence.informe import informe_vigente
from due_diligence.terminacion import (
    Clasificacion,
    Terminacion,
    clasificar_error,
    clasificar_resultado,
    sin_resultado,
)

_PRESENTACION = (
    "Eres el coordinador del due diligence de comercios de la pasarela de pagos Pasarela Austral. "
    "Atiendes a un analista interno y le hablas siempre de usted, sin tutearlo ni mencionar "
    "tickets. Descompones su solicitud en frentes y delegas cada uno en un subagente "
    "especializado."
)

_REGLA_DELEGAR = (
    "No consultas fuentes: solo delegas con la herramienta delegar_frente. Los frentes registro, "
    "noticias y categoria son independientes: delégalos juntos, en la misma respuesta (varias "
    "llamadas a delegar_frente a la vez). Después delega listas: usa el comercio que devolvió el "
    "registro y no pases datos, porque salen del resultado del registro."
)

_REGLA_DATOS = (
    "A cada frente pásale solo los datos que aparecen en la solicitud: el identificador o el "
    "nombre del comercio y la categoría de negocio. Nunca inventes un identificador, un nombre, "
    "una categoría ni un representante legal. Si falta un dato, no delegues el frente que lo "
    "necesita y dilo. La categoría es el sector o producto del comercio, sin el canal de venta "
    "(«suplementos dietarios», no «venta en línea de suplementos dietarios»). Si la herramienta "
    "de categoría devuelve categoria_desconocida, solo vuelve a delegar con un nombre del "
    "catálogo que aparezca en la solicitud; si ninguno aparece, pide confirmación al analista."
)

# Guía de la regla de negocio I.1 (listas solo con identificación unívoca). Es guía: la garantía es
# el hook de `delegar_frente` y el de la consulta de listas. El modo de demostración la quita.
_REGLA_VARIAS_COINCIDENCIAS = (
    "Si el registro devuelve varias coincidencias, no elijas una ni sigas con listas: informa las "
    "coincidencias y pide al analista el identificador."
)

# Guía de las reglas I.2 e I.3 (escalar). Es guía: la garantía son los hooks de `registrar_informe`
# y del fin de turno. El modo de demostración la quita.
_REGLA_ESCALAR = (
    "Si hay una coincidencia en listas restrictivas o la categoría es de alto riesgo, llama a "
    "escalar_a_cumplimiento."
)

_REGLA_INFORME = (
    "Al final registra el informe con registrar_informe y una recomendación que sea exactamente "
    "habilitar, no_habilitar o decide_cumplimiento."
)

_REGLA_CUANDO_USAR_CADA_RECOMENDACION = (
    "Cuando el caso se escaló (coincidencia en listas o alto riesgo), la recomendación es "
    "decide_cumplimiento; no_habilitar es para un caso que no requiere escalamiento y no se "
    "habilita; habilitar, solo si no hay coincidencia, el comercio no es de alto riesgo y la "
    "categoría quedó determinada."
)

# Guía del reintento y de la cobertura (#8, R7, FR-008). No es una regla de negocio I.1 a I.3: está
# también en el modo de demostración. Lo que no puede fallar lo hace el código: el `Delegador`
# solo vuelve a ejecutar lo reintentable, y los hooks registran la cobertura calculada.
_REGLA_FALLOS = (
    "Si un frente devuelve un error con reintentable true, puedes volver a delegarlo una vez con "
    "la misma entrada; si devuelve reintentable false, no lo repitas: sigue con los demás "
    "frentes y registra el informe igualmente. La cobertura del informe la calcula el sistema a "
    "partir de lo que devolvieron los frentes."
)

# Guía del informe con procedencia (#9, R12). No es una regla de negocio I.1 a I.3: está también en
# el modo de demostración. Lo que no puede fallar lo hace el código: el hook de `registrar_informe`
# valida la forma y la fuente de cada afirmación y pone el comercio, los conflictos y la cobertura.
_REGLA_AFIRMACIONES = (
    "En el informe, escribe los hallazgos de cada frente como una lista de afirmaciones, cada una "
    "con texto, fuente y fecha; la fuente y la fecha son las de los metadatos del resultado, y "
    "solo cites fuentes que consultaste para ese frente. Si nada quedó cubierto, el informe va "
    "sin afirmaciones. El comercio, los conflictos entre fuentes y la cobertura los pone el "
    "sistema: no elijas entre valores que se contradicen. Si hay que escalar, registra el informe "
    "después de escalar. Si el registro mercantil no responde, reintenta el registro o registra "
    "el informe con el comercio que pidió el analista."
)

_REGLA_RESUMEN = (
    "Al terminar, resume al analista, frente por frente, lo que se obtuvo con su fuente y su "
    "fecha, y qué frentes no se pudieron cubrir y por qué."
)


def instrucciones_coordinador(demo: bool = False) -> str:
    """El `system_prompt` del coordinador (FR-019, R11).

    La instrucción mínima de este ticket pide escalar y registrar el informe con una recomendación
    del conjunto cerrado; la prohibición de decidir del #6 ya no existe. Es guía: la garantía de las
    reglas 1, 2 y 3 son los hooks. En modo de demostración (`demo=True`) se quitan la regla de las
    varias coincidencias y la guía de escalar, para que el modelo pueda intentar lo prohibido; los
    hooks no cambian.
    """
    if demo:
        reglas = [
            _REGLA_DELEGAR,
            _REGLA_DATOS,
            _REGLA_FALLOS,
            _REGLA_INFORME,
            _REGLA_AFIRMACIONES,
            _REGLA_RESUMEN,
        ]
    else:
        reglas = [
            _REGLA_DELEGAR,
            _REGLA_DATOS,
            _REGLA_FALLOS,
            _REGLA_VARIAS_COINCIDENCIAS,
            f"{_REGLA_ESCALAR} {_REGLA_INFORME} {_REGLA_CUANDO_USAR_CADA_RECOMENDACION}",
            _REGLA_AFIRMACIONES,
            _REGLA_RESUMEN,
        ]
    numeradas = "\n".join(f"{numero}. {texto}" for numero, texto in enumerate(reglas, start=1))
    return f"{_PRESENTACION}\n\nReglas:\n{numeradas}\n"


INSTRUCCIONES_COORDINADOR = instrucciones_coordinador(demo=False)


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
        self.demo = configuracion.modo_demostracion(entorno)
        self._consulta = consulta or query
        self.delegador = Delegador(
            self.estado, self._eventos, ejecutor or EjecutorSDK(), self._opciones_subagente
        )
        self.respuesta = ""
        self.coste_usd: float | None = None  # `total_cost_usd` del coordinador
        # `num_turns` del coordinador (#8, R2): para comprobar que los reintentos y las
        # devoluciones del `Stop` caben en `MAX_TURNOS_SEGURIDAD`. `None` sin `ResultMessage`.
        self.turnos: int | None = None

    def eventos(self) -> list[Evento]:
        return self._eventos.eventos()

    @property
    def terminacion(self) -> Clasificacion | None:
        return self.estado.terminacion

    @property
    def cobertura(self) -> CoberturaCaso:
        """La cobertura calculada por el código (#8, R5): la misma que se registra."""
        return calcular_cobertura(self.estado)

    @property
    def conflictos(self) -> ConflictosCaso:
        """Los conflictos entre fuentes que calcula el código (#9, R6, FR-010): los del informe."""
        return calcular_conflictos(self.estado)

    @property
    def completo(self) -> bool:
        """Si el caso puede presentarse como completo (#7, FR-007; #8, FR-012).

        Solo si la cobertura calculada es completa (los cuatro frentes cubiertos, R5), el ciclo
        terminó con normalidad, el `Stop` no tuvo que dejar terminar un caso sin su escalamiento
        obligatorio ni sin su informe (#9), ningún hook falló (un `PostToolUse` que falló pudo dejar
        sin registrar una coincidencia o una identificación) y hay un informe vigente (#9, FR-023).
        """
        estado = self.estado
        return (
            self.cobertura.completa
            and estado.terminacion is not None
            and estado.terminacion.terminacion is Terminacion.NORMAL
            and not estado.cierre_sin_escalar
            and not estado.cierre_sin_informe
            and estado.libro.fallo_de_hook is None
            and informe_vigente(estado)
        )

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
            instrucciones_coordinador(self.demo),
            hooks=self.hooks.coordinador(),
            entorno=self.entorno,
        )

    async def ejecutar(self, solicitud: str) -> str:
        """Ejecuta el ciclo del coordinador y devuelve su respuesta final al analista."""
        self.estado.solicitud = solicitud
        self._eventos.registrar(TIPO_CASO_INICIADO, None, "Se inicia el caso.")
        if self.demo:
            self._eventos.registrar(
                TIPO_MODO_DEMOSTRACION,
                None,
                "Modo de demostración: las reglas 1, 2 y 3 no están en el prompt del coordinador "
                "y los hooks siguen activos.",
            )
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
                    self.turnos = mensaje.num_turns
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
