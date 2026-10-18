"""Hooks del Agent SDK que garantizan las reglas I.1, I.2 e I.3 (R1 a R6, FR-010, FR-012).

`HooksDelCaso` construye, para un caso, los hooks de cada agente con cierre sobre **el mismo**
`EstadoCaso` y registro de eventos: lo compartido es el estado, los hooks van por agente
(`contracts/hooks.md`). Son funciones Python del proceso del caso: no hay estado de módulo y no se
pasa nada por el SDK.

Lo medido con el SDK 0.2.168 (research R1 a R3) condiciona el diseño:

- `PostToolUse` recibe `tool_response` como texto JSON (stdio) o lista de bloques (en proceso); un
  error estructurado de la pasarela llega solo por `PostToolUseFailure`. Un único lector,
  `ejecutor.interpretar_resultado`, entiende las dos formas.
- Una excepción o una salida inválida en un hook **deja pasar la acción**. Por eso cada hook se
  envuelve con `fallar_cerrado` y sus salidas se construyen solo con `permitir`, `denegar` y
  `bloquear_cierre`.
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from claude_agent_sdk import HookMatcher

from due_diligence.ejecutor import interpretar_resultado
from due_diligence.estado import EstadoCaso
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_CONSULTA_FALLIDA,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_FALLO_DE_HOOK,
    RegistroEventos,
)
from due_diligence.frentes import (
    FRENTES,
    HERRAMIENTA_DELEGAR,
    SERVIDOR_DELEGACION,
    Frente,
    nombre_completo,
)
from due_diligence.libro import Coincidencia, ConsultaListas, ConsultaRiesgo
from due_diligence.reglas import (
    ETIQUETAS_CAUSA,
    causas_vigentes,
    evaluar_informe,
    permite_delegar_listas,
    permite_listas,
)

Hook = Callable[[dict[str, Any], str | None, Any], Awaitable[dict[str, Any]]]

MOTIVO_FALLO_DE_HOOK = "No se pudo verificar la regla; se bloquea por precaución."
MOTIVO_LIBRO_SELLADO = "No se pudo registrar un hecho de la regla; se bloquea por precaución."
MOTIVO_ENTRADA_MALFORMADA = (
    "La entrada de la herramienta no tiene la forma esperada; se bloquea por precaución."
)
REGLA_LISTAS = "I.1"
NIVELES_DE_RIESGO = ("alto", "medio", "bajo")
HERRAMIENTA_DELEGAR_COMPLETA = nombre_completo(HERRAMIENTA_DELEGAR, SERVIDOR_DELEGACION)
HERRAMIENTA_INFORME = nombre_completo("registrar_informe")
HERRAMIENTA_ESCALAR = nombre_completo("escalar_a_cumplimiento")

# --------------------------------------------------------------------------- salidas tipadas


def permitir() -> dict[str, Any]:
    """La acción sigue."""
    return {}


def denegar(motivo: str) -> dict[str, Any]:
    """`PreToolUse`: la herramienta no se ejecuta y el modelo recibe el motivo."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        }
    }


def bloquear_cierre(motivo: str) -> dict[str, Any]:
    """`Stop`: el coordinador no termina y el motivo llega al modelo."""
    return {"decision": "block", "reason": motivo}


# --------------------------------------------------------------------------- lectura


def leer_respuesta(contenido: Any, es_error: bool = False) -> tuple[Any, Any]:
    """(resultado del contrato, error estructurado) de lo que devolvió una herramienta.

    Reutiliza `ejecutor.interpretar_resultado`, el único lector (R1): acepta el texto JSON de un
    servidor stdio y la lista de bloques de uno en proceso. Lo que no es ni lo uno ni lo otro, o no
    es texto ni lista, es `(None, None)`.
    """
    if contenido is not None and not isinstance(contenido, (str, list, tuple)):
        return None, None
    return interpretar_resultado(contenido, es_error)


# --------------------------------------------------------------------------- fallo cerrado


def _registrar_fallo(
    tipo: str, error: Exception, estado: EstadoCaso, eventos: RegistroEventos, frente: Frente | None
) -> None:
    """Deja el sello y el evento; el texto de la excepción no sale al modelo ni al evento."""
    estado.libro.fallo_de_hook = f"{tipo}: {type(error).__name__}"
    eventos.registrar(
        TIPO_FALLO_DE_HOOK,
        frente,
        f"Un hook de {tipo} falló: la regla no se pudo verificar y se bloquea por precaución.",
    )


def fallar_cerrado(
    hook: Hook,
    tipo: str,
    estado: EstadoCaso,
    eventos: RegistroEventos,
    frente: Frente | None = None,
) -> Hook:
    """Envuelve un hook para que un fallo no deje pasar la acción (FR-012, R2).

    - `PreToolUse`: deniega con un motivo genérico.
    - `Stop`: bloquea el cierre y cuenta como una devolución.
    - `PostToolUse` y `PostToolUseFailure`: no pueden impedir nada; sellan el libro y los
      `PreToolUse` de las reglas deniegan mientras el sello exista.

    Atrapa `Exception`, no `BaseException`: una cancelación del frente se propaga.
    """

    async def envuelto(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
        try:
            return await hook(entrada, tool_use_id, contexto)
        except Exception as error:
            _registrar_fallo(tipo, error, estado, eventos, frente)
            if tipo == "PreToolUse":
                return denegar(MOTIVO_FALLO_DE_HOOK)
            if tipo == "Stop":
                estado.libro.cierres_impedidos += 1
                return bloquear_cierre(MOTIVO_FALLO_DE_HOOK)
            return permitir()

    return envuelto


# --------------------------------------------------------------------------- hooks del caso


class HooksDelCaso:
    """Los hooks de un caso, por agente, sobre el mismo estado y registro de eventos (R5)."""

    def __init__(
        self,
        estado: EstadoCaso,
        eventos: RegistroEventos,
        entorno: Mapping[str, str] | None = None,
    ) -> None:
        self.estado = estado
        self.eventos = eventos
        self.entorno = entorno

    # -------------------------------------------------------------- construcción

    def _matcher(
        self, herramienta: str, hook: Hook, tipo: str, frente: Frente | None
    ) -> HookMatcher:
        envuelto = fallar_cerrado(hook, tipo, self.estado, self.eventos, frente)
        return HookMatcher(matcher=herramienta, hooks=[envuelto])

    def subagente(self, frente: Frente) -> dict[str, list[HookMatcher]]:
        """Los hooks del subagente de un frente (los que vigilan su propia herramienta)."""
        herramienta = FRENTES[frente].herramienta_completa
        posterior = {
            Frente.REGISTRO: self._registro_posterior,
            Frente.LISTAS: self._listas_posterior,
            Frente.CATEGORIA: self._categoria_posterior,
        }.get(frente)
        hooks: dict[str, list[HookMatcher]] = {}
        if frente is Frente.LISTAS:
            hooks["PreToolUse"] = [
                self._matcher(herramienta, self._listas_previo, "PreToolUse", frente)
            ]
        if posterior is not None:
            hooks["PostToolUse"] = [self._matcher(herramienta, posterior, "PostToolUse", frente)]
            hooks["PostToolUseFailure"] = [
                self._matcher(
                    herramienta, self._fallo_de_herramienta(frente), "PostToolUseFailure", frente
                )
            ]
        return hooks

    def coordinador(self) -> dict[str, list[HookMatcher]]:
        """Los hooks del coordinador: delegar, informe y escalamiento."""
        return {
            "PreToolUse": [
                self._matcher(
                    HERRAMIENTA_DELEGAR_COMPLETA, self._delegar_previo, "PreToolUse", Frente.LISTAS
                ),
                self._matcher(HERRAMIENTA_INFORME, self._informe_previo, "PreToolUse", None),
            ],
            "PostToolUse": [
                self._matcher(HERRAMIENTA_ESCALAR, self._escalar_posterior, "PostToolUse", None)
            ],
            "PostToolUseFailure": [
                self._matcher(
                    HERRAMIENTA_ESCALAR,
                    self._fallo_de_herramienta(None),
                    "PostToolUseFailure",
                    None,
                )
            ],
        }

    # -------------------------------------------------------------- denegar por regla

    def _denegar_por_regla(self, frente: Frente | None, regla: str | None, motivo: str):
        """Deniega, y deja el evento con la regla y el motivo (FR-013)."""
        self.eventos.registrar(TIPO_BLOQUEO_REGLA, frente, motivo, regla=regla)
        return denegar(motivo)

    def _sellado(self, frente: Frente | None, regla: str | None):
        """Con el libro sellado un hecho pudo quedar sin registrar: no se permite."""
        if self.estado.libro.fallo_de_hook:
            return self._denegar_por_regla(frente, regla, MOTIVO_LIBRO_SELLADO)
        return None

    # -------------------------------------------------------------- regla I.1: listas

    async def _listas_previo(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`PreToolUse` de la consulta de listas: solo el comercio o su representante (FR-002)."""
        sellado = self._sellado(Frente.LISTAS, REGLA_LISTAS)
        if sellado is not None:
            return sellado
        permitida, motivo = permite_listas(self.estado, entrada.get("tool_input"))
        if permitida:
            return permitir()
        return self._denegar_por_regla(Frente.LISTAS, REGLA_LISTAS, motivo)

    async def _delegar_previo(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`PreToolUse` de `delegar_frente`: listas necesita un comercio único (FR-018).

        Cualquier otro frente se deja pasar sin leer el estado; una entrada malformada se deniega.
        """
        argumentos = entrada.get("tool_input")
        frente = argumentos.get("frente") if isinstance(argumentos, Mapping) else None
        if not isinstance(frente, str):
            return self._denegar_por_regla(None, None, MOTIVO_ENTRADA_MALFORMADA)
        if frente.strip().casefold() != Frente.LISTAS.value:
            return permitir()
        sellado = self._sellado(Frente.LISTAS, REGLA_LISTAS)
        if sellado is not None:
            return sellado
        permitida, motivo = permite_delegar_listas(self.estado)
        if permitida:
            return permitir()
        return self._denegar_por_regla(Frente.LISTAS, REGLA_LISTAS, motivo)

    # -------------------------------------------------------------- registro (FR-001)

    async def _registro_posterior(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """Guarda la identificación que `derivar_comercio` saca de una respuesta válida."""
        resultado, error = leer_respuesta(entrada.get("tool_response"))
        if resultado is not None:
            self.estado.registrar_identificacion(resultado)
        else:
            self._constancia_de_consulta_fallida(Frente.REGISTRO, error)
        return permitir()

    # -------------------------------------------------------------- regla I.3: riesgo de categoría

    async def _categoria_posterior(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`PostToolUse` del riesgo de categoría: guarda la categoría y su nivel (R8)."""
        resultado, error = leer_respuesta(entrada.get("tool_response"))
        if resultado is None:
            self._constancia_de_consulta_fallida(Frente.CATEGORIA, error)
            return permitir()
        argumentos = entrada.get("tool_input")
        pedida = argumentos.get("categoria") if isinstance(argumentos, Mapping) else None
        hechos = resultado.get("hechos") or [{}]
        contenido = hechos[0].get("contenido", {}) if isinstance(hechos[0], Mapping) else {}
        categoria = contenido.get("categoria") if isinstance(contenido, Mapping) else None
        categoria = categoria if isinstance(categoria, str) else str(pedida or "")
        nivel = contenido.get("nivel") if isinstance(contenido, Mapping) else None
        conocida = resultado.get("resultado") == "categoria_conocida"
        nivel = nivel if conocida and nivel in NIVELES_DE_RIESGO else None
        self.estado.libro.consultas_riesgo.append(ConsultaRiesgo(categoria, nivel))
        return permitir()

    # -------------------------------------------------------------- regla I.2: coincidencias

    async def _listas_posterior(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`PostToolUse` de listas: guarda la consulta válida y cada coincidencia (FR-004)."""
        resultado, error = leer_respuesta(entrada.get("tool_response"))
        if resultado is None:
            self._constancia_de_consulta_fallida(Frente.LISTAS, error)
            return permitir()
        argumentos = entrada.get("tool_input")
        argumentos = argumentos if isinstance(argumentos, Mapping) else {}
        tipo = str(argumentos.get("tipo", "")).strip().casefold()
        nombre, identificador = argumentos.get("nombre"), argumentos.get("identificador")
        hechos = (
            resultado.get("hechos", []) if resultado.get("resultado") == "coincidencias" else []
        )
        self.estado.libro.consultas_listas.append(
            ConsultaListas(
                tipo,
                nombre if isinstance(nombre, str) else None,
                identificador if isinstance(identificador, str) else None,
                "coincidencias" if hechos else "sin_coincidencias",
            )
        )
        for hecho in hechos:
            contenido, metadatos = hecho.get("contenido", {}), hecho.get("metadatos", {})
            tipo_de_la_coincidencia = tipo if tipo in ("comercio", "persona") else "comercio"
            self.estado.libro.coincidencias.append(
                Coincidencia(
                    tipo_de_la_coincidencia,
                    str(contenido.get("lista", "")),
                    str(metadatos.get("fuente", "")),
                    str(metadatos.get("fecha", "")),
                )
            )
        return permitir()

    async def _escalar_posterior(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`PostToolUse` de `escalar_a_cumplimiento`: guarda las causas que cubre."""
        resultado, error = leer_respuesta(entrada.get("tool_response"))
        if resultado is None or resultado.get("resultado") != "caso_escalado":
            self._constancia_de_consulta_fallida(None, error)
            return permitir()
        causas = causas_vigentes(self.estado.libro)
        self.estado.libro.escalamientos.append(causas)
        cubiertas = ", ".join(texto for clave, texto in ETIQUETAS_CAUSA.items() if clave in causas)
        detalle = f"Escalamiento registrado; cubre: {cubiertas or 'ninguna causa vigente'}."
        self.eventos.registrar(TIPO_ESCALAMIENTO_REGISTRADO, None, detalle)
        return permitir()

    async def _informe_previo(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`PreToolUse` de `registrar_informe`: rechaza lo que las reglas no permiten (FR-005)."""
        sellado = self._sellado(None, None)
        if sellado is not None:
            return sellado
        rechazos = evaluar_informe(self.estado, entrada.get("tool_input"))
        if not rechazos:
            return permitir()
        reglas = {parte for r in rechazos if r.regla for parte in r.regla.split(", ")}
        regla = ", ".join(sorted(reglas)) or None
        return self._denegar_por_regla(None, regla, " ".join(r.texto for r in rechazos))

    # -------------------------------------------------------------- errores de herramienta

    def _constancia_de_consulta_fallida(self, frente: Frente | None, error: Any) -> None:
        """Deja el evento `consulta_fallida` de una respuesta que no cuenta como consulta.

        Una respuesta que no es ni el JSON del contrato ni un error estructurado, o un error
        estructurado, no entra a ninguna regla: queda constancia del motivo (FR-001) sin repetir
        lo recibido.
        """
        if isinstance(error, dict):
            tipo = error.get("tipo")
            etiqueta = tipo if isinstance(tipo, str) else "desconocido"
            detalle = f"La herramienta devolvió un error estructurado ({etiqueta}); no cuenta."
        else:
            detalle = (
                "La respuesta de la herramienta no tiene la forma del contrato de la pasarela "
                "ni es un error estructurado; no cuenta."
            )
        self.eventos.registrar(TIPO_CONSULTA_FALLIDA, frente, detalle)

    def _fallo_de_herramienta(self, frente: Frente | None) -> Hook:
        """`PostToolUseFailure`: un error estructurado de la pasarela no cuenta como consulta."""

        async def hook(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
            _, error = leer_respuesta(entrada.get("error"), es_error=True)
            self._constancia_de_consulta_fallida(frente, error)
            return permitir()

        return hook
