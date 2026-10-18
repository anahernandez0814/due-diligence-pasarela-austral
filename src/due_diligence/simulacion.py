"""Ejecutor simulado y constructores de resultados para los tests (R12).

Permite probar la delegación, el orden de los frentes y el estado sin llamar al modelo: un
`EjecutorSimulado` espera un tiempo conocido, registra cuándo empezó y terminó cada frente y
devuelve un resultado fijo. Los datos son los ficticios del #5.
"""

import asyncio
import inspect
import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from due_diligence.estado import Consulta, ResultadoFrente
from due_diligence.frentes import FRENTES, Frente
from due_diligence.terminacion import Clasificacion, clasificar
from servidor_mcp.normalizar import igual, igual_identificador, normalizar

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


def consulta_listas(tipo: str, **argumento: str) -> Consulta:
    """Una consulta de listas restrictivas por `nombre` o `identificador`, con su `tipo`."""
    return consulta(
        Frente.LISTAS,
        {"tipo": tipo, **argumento},
        respuesta_del_contrato("sin_coincidencias", [], [], fuente="Lista Restrictiva Ficticia"),
    )


def resultado_listas(consultas: list[Consulta] | None = None) -> ResultadoFrente:
    """El resultado de listas: por defecto, la consulta del comercio y la de su representante."""
    if consultas is None:
        consultas = [
            consulta_listas("comercio", identificador="CO-TV-0001"),
            consulta_listas("persona", identificador=REPRESENTANTE["identificador"]),
        ]
    return resultado_frente(Frente.LISTAS, consultas)


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
        return await _con_hooks(self._resultado(frente, contexto), opciones)

    def _resultado(self, frente: Frente, contexto: str) -> ResultadoFrente:
        resultado = self.resultados.get(frente)
        if callable(resultado):
            return resultado(contexto)
        if resultado is not None:
            return resultado
        if frente is Frente.REGISTRO:
            return resultado_registro()
        if frente is Frente.LISTAS:
            return resultado_listas()
        return resultado_frente(frente)


async def _con_hooks(resultado: ResultadoFrente, opciones: Any) -> ResultadoFrente:
    """Reproduce las consultas del resultado por una `SesionSimulada` de las `opciones` (R4).

    Así los hooks que el código puso en las opciones del agente ven cada llamada, igual que en el
    SDK. Una consulta que un `PreToolUse` deniega no se ejecuta: queda como una consulta con el
    error de herramienta que el SDK devolvería, y sin resultado. Sin hooks no cambia nada.
    """
    if not getattr(opciones, "hooks", None):
        return resultado
    sesion = SesionSimulada(opciones)
    consultas: list[Consulta] = []
    for c in resultado.consultas:
        respuesta = c.error if c.error is not None else (c.resultado or {})
        llamada = await sesion.llamar(c.herramienta, c.argumentos, respuesta=respuesta)
        if llamada.denegada:
            error = {
                "error": True,
                "tipo": "error_de_herramienta",
                "mensaje": llamada.texto,
                "reintentable": False,
                "obtenido": {},
            }
            c = Consulta(c.frente, c.herramienta, c.argumentos, None, False, error)
        consultas.append(c)
    return replace(resultado, consultas=consultas)


# ------------------------------------------------------------------ sesión simulada (R4, R12)


@dataclass
class ResultadoLlamada:
    """Lo que devuelve `SesionSimulada.llamar`: lo que vería el modelo y qué pasó."""

    herramienta: str
    ejecutada: bool
    denegada: bool
    es_error: bool
    texto: str
    motivo: str | None = None


@dataclass
class ResultadoCierre:
    """Lo que devuelve `SesionSimulada.terminar`: si el agente termina o continúa."""

    termino: bool
    motivo: str | None = None


class SesionSimulada:
    """Una sesión de agente que ejecuta los hooks de sus opciones como lo hace el SDK 0.2.168.

    Reproduce lo medido en `research.md` (R1 a R3): `PreToolUse` → herramienta → `PostToolUse`
    (éxito, `tool_response` como texto JSON o lista de bloques si es en proceso) o
    `PostToolUseFailure` (error estructurado, en `error`); un `deny` impide ejecutar la herramienta
    y el modelo recibe el motivo; una excepción en un hook **deja pasar la acción**; un `Stop` con
    `block` hace continuar y `stop_hook_active` pasa a `True`. Los matchers se resuelven como el
    SDK, por expresión regular sobre el nombre completo de la herramienta.
    """

    def __init__(
        self,
        opciones: Any,
        herramientas: Mapping[str, Callable[[dict[str, Any]], Any]] | None = None,
    ) -> None:
        self._opciones = opciones
        self.herramientas = dict(herramientas or {})
        self.llamadas: list[ResultadoLlamada] = []
        self.excepciones_de_hooks: list[Exception] = []
        self._stop_activo = False
        self._contador = 0

    def _hooks(self, evento: str, herramienta: str | None) -> list[Callable[..., Any]]:
        encontrados: list[Callable[..., Any]] = []
        for matcher in (getattr(self._opciones, "hooks", None) or {}).get(evento, []):
            patron = matcher.matcher
            if patron is None or (herramienta and re.fullmatch(patron, herramienta)):
                encontrados.extend(matcher.hooks)
        return encontrados

    async def _correr(
        self, evento: str, herramienta: str | None, entrada: dict[str, Any], identificador: str
    ) -> list[dict[str, Any]]:
        salidas: list[dict[str, Any]] = []
        for hook in self._hooks(evento, herramienta):
            try:
                salidas.append(await hook(entrada, identificador, None) or {})
            except Exception as error:  # el SDK deja pasar la acción (R2)
                self.excepciones_de_hooks.append(error)
        return salidas

    @staticmethod
    def _motivo_de_denegacion(salidas: list[dict[str, Any]]) -> str | None:
        for salida in salidas:
            especifica = salida.get("hookSpecificOutput") or {}
            if especifica.get("permissionDecision") == "deny":
                return str(especifica.get("permissionDecisionReason", ""))
        return None

    async def llamar(
        self,
        herramienta: str,
        entrada: Mapping[str, Any],
        *,
        respuesta: Any = None,
        en_proceso: bool = False,
    ) -> ResultadoLlamada:
        """Una llamada del agente a una herramienta, con sus hooks."""
        self._contador += 1
        identificador = f"toolu_sim_{self._contador}"
        argumentos = dict(entrada)
        base = {"tool_name": herramienta, "tool_input": argumentos, "tool_use_id": identificador}
        salidas = await self._correr(
            "PreToolUse", herramienta, {"hook_event_name": "PreToolUse", **base}, identificador
        )
        motivo = self._motivo_de_denegacion(salidas)
        if motivo is not None:
            texto = f"PreToolUse:{herramienta} hook error: {motivo}"
            resultado = ResultadoLlamada(herramienta, False, True, True, texto, motivo)
            self.llamadas.append(resultado)
            return resultado

        if respuesta is None:
            if herramienta not in self.herramientas:
                raise KeyError(f"La sesión simulada no tiene la herramienta {herramienta!r}.")
            respuesta = self.herramientas[herramienta](argumentos)
            if inspect.isawaitable(respuesta):  # una herramienta en proceso asíncrona
                respuesta = await respuesta
        es_error = isinstance(respuesta, Mapping) and respuesta.get("error") is True
        texto = json.dumps(respuesta, ensure_ascii=False)
        if es_error:
            evento = {"hook_event_name": "PostToolUseFailure", **base, "error": texto}
            await self._correr("PostToolUseFailure", herramienta, evento, identificador)
        else:
            contenido: Any = [{"type": "text", "text": texto}] if en_proceso else texto
            evento = {"hook_event_name": "PostToolUse", **base, "tool_response": contenido}
            await self._correr("PostToolUse", herramienta, evento, identificador)
        resultado = ResultadoLlamada(herramienta, True, False, es_error, texto)
        self.llamadas.append(resultado)
        return resultado

    async def terminar(self, ultimo_mensaje: str = "") -> ResultadoCierre:
        """El agente intenta terminar: los hooks de `Stop` pueden hacerlo continuar."""
        entrada = {
            "hook_event_name": "Stop",
            "stop_hook_active": self._stop_activo,
            "last_assistant_message": ultimo_mensaje,
        }
        for salida in await self._correr("Stop", None, entrada, ""):
            if salida.get("decision") == "block":
                self._stop_activo = True
                return ResultadoCierre(False, str(salida.get("reason", "")))
        return ResultadoCierre(True)


# ------------------------------------------------------------------ datos de los casos (G1)

REPRESENTANTE_BAJO_RIESGO = {"nombre": "Tomás Valdivia Arce", "identificador": "PE-0002"}
REPRESENTANTE_EN_LISTAS = {"nombre": "Ernesto Calderón Ibarra", "identificador": "PE-0003"}


def comercio_alto_riesgo() -> dict[str, Any]:
    """Caso (a): `CO-TV-0001`, cuya categoría de la solicitud es «suplementos dietarios»."""
    return comercio_del_registro()


def comercio_bajo_riesgo() -> dict[str, Any]:
    """Caso (b): `CO-TA-0002`, de bajo riesgo y sin hallazgos."""
    return comercio_del_registro("CO-TA-0002", "Taller Aurora SAS", REPRESENTANTE_BAJO_RIESGO)


def comercio_con_representante_en_listas() -> dict[str, Any]:
    """Caso (c): `CO-PL-0003`, cuyo representante `PE-0003` figura en listas."""
    return comercio_del_registro("CO-PL-0003", "Panadería Luna Nueva SAS", REPRESENTANTE_EN_LISTAS)


def comercios_parecidos() -> list[dict[str, Any]]:
    """Caso (e): dos comercios con nombres casi idénticos, `CO-AM-0004` y `CO-AM-0005`."""
    return [
        comercio_del_registro(
            "CO-AM-0004",
            "Almacén Mirador SAS",
            {"nombre": "Renata Olmedo Sáenz", "identificador": "PE-0004"},
        ),
        comercio_del_registro(
            "CO-AM-0005",
            "Almacén Mirador Norte SAS",
            {"nombre": "Gaspar Linares Ibáñez", "identificador": "PE-0005"},
        ),
    ]


CATEGORIAS_SIMULADAS = {
    "suplementos dietarios": "alto",
    "apuestas": "alto",
    "talleres": "bajo",
    "panaderías": "bajo",
    "comercio de calzado": "medio",
}
_FUENTE_CATEGORIAS = "Catálogo Ficticio de Categorías"
_FUENTE_LISTAS = "Lista Restrictiva Ficticia A"


def respuesta_registro(*comercios: Mapping[str, Any]) -> dict[str, Any]:
    """Respuesta del registro: una coincidencia, varias, o ninguna si no hay comercios."""
    if not comercios:
        return respuesta_del_contrato("sin_coincidencias", [], [])
    identificadores = list(dict.fromkeys(c["identificador"] for c in comercios))
    return respuesta_del_contrato("coincidencias", [dict(c) for c in comercios], identificadores)


def respuesta_riesgo(categoria: str, nivel: str | None) -> dict[str, Any]:
    """Respuesta de riesgo: conocida con `nivel`, o `categoria_desconocida` si `nivel` es `None`."""
    if nivel is None:
        contenido = {"categoria": categoria, "categorias_conocidas": list(CATEGORIAS_SIMULADAS)}
        return respuesta_del_contrato(
            "categoria_desconocida", [contenido], fuente=_FUENTE_CATEGORIAS
        )
    return respuesta_del_contrato(
        "categoria_conocida", [{"categoria": categoria, "nivel": nivel}], fuente=_FUENTE_CATEGORIAS
    )


def respuesta_listas(coincidencia: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Respuesta de listas: con una coincidencia (`tipo`, `nombre`, `identificador`) o sin ella."""
    if coincidencia is None:
        return respuesta_del_contrato("sin_coincidencias", [], [], fuente=_FUENTE_LISTAS)
    contenido = {"lista": "Lista Restrictiva Ficticia A", **coincidencia}
    return respuesta_del_contrato("coincidencias", [contenido], fuente=_FUENTE_LISTAS)


def respuesta_de_decision(resultado: str, identificador: str) -> dict[str, Any]:
    """Respuesta de `registrar_informe` o `escalar_a_cumplimiento`: un hecho con el `id`."""
    return respuesta_del_contrato(
        resultado, [{"id": identificador}], fuente="Registro local (ficticio)"
    )


def error_estructurado(
    tipo: str = "servicio_no_disponible", reintentable: bool = True
) -> dict[str, Any]:
    """Un error estructurado de la pasarela, con la forma del #5."""
    return {
        "error": True,
        "tipo": tipo,
        "mensaje": "error simulado",
        "reintentable": reintentable,
        "obtenido": {},
    }


@dataclass
class PasarelaSimulada:
    """Las seis herramientas de la pasarela simuladas, con los datos de los casos a, b, c y e.

    `registro` son los comercios del registro; `en_listas` los identificadores (o nombres) de
    `comercio` y `persona` que figuran en listas; `categorias` el nivel por categoría. Guarda lo
    que recibieron `registrar_informe` y `escalar_a_cumplimiento`. `herramientas[nombre]` es una
    función `entrada -> respuesta` para `SesionSimulada`.
    """

    registro: list[dict[str, Any]] = field(default_factory=list)
    en_listas: dict[str, set[str]] = field(default_factory=dict)
    categorias: dict[str, str] = field(default_factory=lambda: dict(CATEGORIAS_SIMULADAS))
    informes: list[dict[str, Any]] = field(default_factory=list)
    escalamientos: list[dict[str, Any]] = field(default_factory=list)
    consultas_a_fuentes: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def __post_init__(self) -> None:
        def nombrar(corto: str) -> str:
            return f"mcp__pasarela__{corto}"

        self.herramientas: dict[str, Callable[[dict[str, Any]], Any]] = {
            nombrar("consultar_registro_mercantil"): self._registro,
            nombrar("consultar_listas_restrictivas"): self._listas,
            nombrar("buscar_noticias"): self._noticias,
            nombrar("consultar_riesgo_categoria"): self._riesgo,
            nombrar("registrar_informe"): self._informe,
            nombrar("escalar_a_cumplimiento"): self._escalar,
        }

    def _registro(self, entrada: dict[str, Any]) -> dict[str, Any]:
        self.consultas_a_fuentes.append(("registro", dict(entrada)))
        identificador, nombre = entrada.get("identificador"), entrada.get("nombre")
        if identificador:
            hallados = [
                c for c in self.registro if igual_identificador(c["identificador"], identificador)
            ]
        elif nombre:
            hallados = [c for c in self.registro if normalizar(nombre) in normalizar(c["nombre"])]
        else:
            hallados = []
        return respuesta_registro(*hallados)

    def _listas(self, entrada: dict[str, Any]) -> dict[str, Any]:
        self.consultas_a_fuentes.append(("listas", dict(entrada)))
        tipo = str(entrada.get("tipo", "")).casefold()
        figuran = self.en_listas.get(tipo, set())
        for clave in ("identificador", "nombre"):
            valor = entrada.get(clave)
            if valor and any(igual(valor, f) or igual_identificador(valor, f) for f in figuran):
                return respuesta_listas({"tipo": tipo, "nombre": "(ficticio)", clave: valor})
        return respuesta_listas()

    def _noticias(self, entrada: dict[str, Any]) -> dict[str, Any]:
        self.consultas_a_fuentes.append(("noticias", dict(entrada)))
        return respuesta_del_contrato("sin_coincidencias", [], [], fuente="Noticias Ficticias")

    def _riesgo(self, entrada: dict[str, Any]) -> dict[str, Any]:
        self.consultas_a_fuentes.append(("riesgo", dict(entrada)))
        categoria = str(entrada.get("categoria", ""))
        for conocida, nivel in self.categorias.items():
            if igual(conocida, categoria):
                return respuesta_riesgo(conocida, nivel)
        return respuesta_riesgo(categoria, None)

    def _informe(self, entrada: dict[str, Any]) -> dict[str, Any]:
        self.informes.append(dict(entrada))
        return respuesta_de_decision("informe_registrado", f"INF-{len(self.informes):04d}")

    def _escalar(self, entrada: dict[str, Any]) -> dict[str, Any]:
        self.escalamientos.append(dict(entrada))
        return respuesta_de_decision("caso_escalado", f"ESC-{len(self.escalamientos):04d}")


# ------------------------------------------------------------------ coordinador simulado (G1, T041)


def mensaje_de_resultado(
    subtype: str = "success", stop_reason: str = "end_turn", terminal: str = "completed"
) -> ResultMessage:
    """Un `ResultMessage` del SDK: por defecto, un fin normal."""
    return ResultMessage(
        subtype=subtype,
        duration_ms=1,
        duration_api_ms=1,
        is_error=subtype != "success",
        num_turns=1,
        session_id="sesion-de-prueba",
        stop_reason=stop_reason,
        terminal_reason=terminal,
    )


class CoordinadorSimulado:
    """Un `query()` del coordinador que ejecuta un guion de llamadas **por sus hooks** (G1).

    Cada paso del guion pasa por una `SesionSimulada` con las opciones del coordinador que el
    `Caso` le entrega. Así los `PreToolUse` de `delegar_frente` y de `registrar_informe`, los
    `PostToolUse` de `escalar_a_cumplimiento` y el `Stop` se ejecutan como en el SDK.
    `delegar_frente` llama al `Delegador` del caso (asignar `coordinador.caso`); `registrar_informe`
    y `escalar_a_cumplimiento`, a la `PasarelaSimulada`.

    Pasos del guion: `("delegar", entrada)`, `("delegar_paralelo", [entradas])`,
    `("informe", recomendacion)`, `("escalar",)` y `("terminar",)`. El resultado de cada uno queda
    en `pasos`, como `(tipo, resultado)`.
    """

    def __init__(
        self,
        guion: list[tuple[Any, ...]],
        pasarela: "PasarelaSimulada | None" = None,
        texto: str = "Resumen para el analista.",
    ) -> None:
        self.guion = list(guion)
        self.pasarela = pasarela or PasarelaSimulada()
        self.texto = texto
        self.caso: Any = None
        self.pasos: list[tuple[str, Any]] = []
        self.sesion: SesionSimulada | None = None

    def resultados_de(self, tipo: str) -> list[Any]:
        return [resultado for paso, resultado in self.pasos if paso == tipo]

    def _informe(self, recomendacion: str) -> dict[str, Any]:
        comercio = (self.caso.estado.comercio if self.caso is not None else None) or {}
        return {
            "comercio": {
                "identificador": comercio.get("identificador", "sin identificar"),
                "nombre": comercio.get("nombre", "sin identificar"),
            },
            "recomendacion": recomendacion,
            "hallazgos": {},
            "cobertura": "completa",
        }

    async def __call__(self, *, prompt: str, options: Any = None):
        herramientas = {
            **self.pasarela.herramientas,
            "mcp__delegacion__delegar_frente": lambda entrada: self.caso.delegador.delegar(entrada),
        }
        sesion = SesionSimulada(options, herramientas)
        self.sesion = sesion
        for paso in self.guion:
            tipo = paso[0]
            if tipo == "delegar":
                resultado = await sesion.llamar(
                    "mcp__delegacion__delegar_frente", paso[1], en_proceso=True
                )
            elif tipo == "delegar_paralelo":
                resultado = await asyncio.gather(
                    *(
                        sesion.llamar("mcp__delegacion__delegar_frente", entrada, en_proceso=True)
                        for entrada in paso[1]
                    )
                )
            elif tipo == "informe":
                resultado = await sesion.llamar(
                    "mcp__pasarela__registrar_informe", self._informe(paso[1])
                )
            elif tipo == "escalar":
                resultado = await sesion.llamar(
                    "mcp__pasarela__escalar_a_cumplimiento", {"causa_escalamiento": "simulada"}
                )
            elif tipo == "terminar":
                resultado = await sesion.terminar(self.texto)
            else:
                raise ValueError(f"Paso de guion desconocido: {tipo!r}")
            self.pasos.append((tipo, resultado))
        yield AssistantMessage(content=[TextBlock(self.texto)], model="simulado")
        yield mensaje_de_resultado()
