"""Hooks del Agent SDK que garantizan las reglas I.1, I.2 e I.3 (R1 a R6, FR-010, FR-012).

`HooksDelCaso` construye, para un caso, los hooks de cada agente con cierre sobre **el mismo**
`EstadoCaso` y registro de eventos: lo compartido es el estado, los hooks van por agente
(`contracts/hooks.md`). Son funciones Python del proceso del caso: no hay estado de módulo y no se
pasa nada por el SDK.

Lo medido con el SDK 0.2.168 (research R1 a R3) condiciona el diseño:

- `PostToolUse` recibe `tool_response` como texto JSON (stdio) o lista de bloques (en proceso); un
  error estructurado de la pasarela llega solo por `PostToolUseFailure`. Un único lector,
  `ejecutor.interpretar_resultado`, entiende las dos formas.
- Una excepción o una salida inválida en un hook **deja pasar la acción**. Por eso los hooks se
  envuelven con `fallar_cerrado` y sus salidas se construyen solo con `permitir`, `denegar`,
  `bloquear_cierre` y `reemplazar_entrada` (la cobertura calculada por el código, #8).
- La excepción es el `PreToolUse` de `escalar_a_cumplimiento`: escalar es la acción segura, así
  que va envuelto con `degradar_escalamiento`, que nunca deniega (#8, R6).
"""

import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from claude_agent_sdk import HookMatcher

from due_diligence.cobertura import CoberturaCaso, calcular_cobertura
from due_diligence.configuracion import MAX_CIERRES_IMPEDIDOS
from due_diligence.conflictos import calcular_conflictos
from due_diligence.ejecutor import interpretar_resultado
from due_diligence.estado import EstadoCaso
from due_diligence.eventos import (
    TIPO_BLOQUEO_REGLA,
    TIPO_CIERRE_IMPEDIDO,
    TIPO_CIERRE_SIN_ESCALAR,
    TIPO_CIERRE_SIN_INFORME,
    TIPO_COBERTURA_SUSTITUIDA,
    TIPO_CONSULTA_FALLIDA,
    TIPO_DATOS_SUSTITUIDOS,
    TIPO_ESCALAMIENTO_REGISTRADO,
    TIPO_FALLO_DE_HOOK,
    TIPO_INFORME_REGISTRADO,
    RegistroEventos,
)
from due_diligence.frentes import (
    FRENTES,
    HERRAMIENTA_DELEGAR,
    SERVIDOR_DELEGACION,
    Frente,
    nombre_completo,
)
from due_diligence.informe import (
    NO_CALCULADOS,
    Huella,
    InformeRegistrado,
    comercio_del_informe,
    huella_con,
    problemas_de_fuente,
)
from due_diligence.libro import Coincidencia, ConsultaListas, ConsultaRiesgo
from due_diligence.reglas import (
    ETIQUETAS_CAUSA,
    Rechazo,
    causas_vigentes,
    evaluar_cierre,
    evaluar_informe,
    falta_para_cerrar,
    permite_delegar_listas,
    permite_listas,
    reglas_de,
)
from servidor_mcp.informe import Problema, validar_informe

Hook = Callable[[dict[str, Any], str | None, Any], Awaitable[dict[str, Any]]]

MOTIVO_FALLO_DE_HOOK = "No se pudo verificar la regla; se bloquea por precaución."
MOTIVO_LIBRO_SELLADO = "No se pudo registrar un hecho de la regla; se bloquea por precaución."
MOTIVO_ENTRADA_MALFORMADA = (
    "La entrada de la herramienta no tiene la forma esperada; se bloquea por precaución."
)
# Cobertura con la que sale un escalamiento si falla su cálculo (#8, R6): escalar nunca se deniega.
COBERTURA_NO_CALCULADA = "No se pudo calcular la cobertura; debe tratarse como incompleta."
REGLA_LISTAS = "I.1"
# Fuente y forma de cada afirmación del informe (#9, FR-001 a FR-004).
REGLA_FUENTE = "I.4"
MOTIVO_SIN_COMERCIO_INFORME = (
    "No hay comercio para el informe: el registro no identificó uno único y no hay un comercio "
    "pedido por el analista."
)
# Solo para validar la forma del resto del informe cuando falta el comercio o la recomendación:
# esas dos ausencias ya son motivos propios y `validar_informe` se detendría en ellas.
_COMERCIO_PARA_VALIDAR = {"identificador": None, "nombre": "-", "verificado": False}
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


def denegar_informe(rechazos: list[Rechazo], problemas: list[Problema]) -> dict[str, Any]:
    """`PreToolUse` de `registrar_informe`: deniega con un error estructurado en JSON (#9, R3).

    Junta en un solo rechazo los motivos de las reglas (con su regla) y los problemas de forma o de
    fuente (con su ruta). `reintentable: false`: la misma entrada volvería a fallar.
    """
    textos = [r.texto for r in rechazos]
    if problemas:
        detalle = "; ".join(
            f"{p.ruta}: {p.texto[0].lower()}{p.texto[1:].rstrip('.')}" for p in problemas
        )
        textos.append(f"Problemas de forma o de fuente: {detalle}.")
    cuerpo = {
        "error": True,
        "tipo": "informe_rechazado",
        "mensaje": f"No se registra el informe. {' '.join(textos)} Corrige y vuelve a registrarlo.",
        "reintentable": False,
        "motivos": [{"regla": r.regla, "texto": r.texto} for r in rechazos],
        "problemas": [p.como_dict() for p in problemas],
    }
    return denegar(json.dumps(cuerpo, ensure_ascii=False))


def bloquear_cierre(motivo: str) -> dict[str, Any]:
    """`Stop`: el coordinador no termina y el motivo llega al modelo."""
    return {"decision": "block", "reason": motivo}


def reemplazar_entrada(entrada: dict[str, Any]) -> dict[str, Any]:
    """`PreToolUse`: la herramienta se ejecuta con `entrada` en lugar de la del modelo (#8, R1).

    Medido con el SDK 0.2.168: `updatedInput` **sustituye la entrada entera**, no se fusiona, así
    que `entrada` debe ir completa.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": entrada,
        }
    }


# --------------------------------------------------------------------------- informe (#9)


def _identificador_del_informe(resultado: Any) -> str | None:
    """El id `INF-…` de una respuesta `informe_registrado` de la pasarela, o `None`."""
    if not isinstance(resultado, Mapping) or resultado.get("resultado") != "informe_registrado":
        return None
    hechos = resultado.get("hechos") or []
    contenido = hechos[0].get("contenido") if hechos and isinstance(hechos[0], Mapping) else None
    identificador = contenido.get("id") if isinstance(contenido, Mapping) else None
    return identificador if isinstance(identificador, str) and identificador else None


def _resumen_de_huella(huella: Huella) -> str:
    """La cobertura y los conflictos de un informe, en texto fijo y sin datos del comercio."""
    if huella.cobertura == NO_CALCULADOS:
        return "cobertura y conflictos no calculados"
    cubiertos = sum(cubierto for _, cubierto in huella.cobertura)
    total = len(huella.cobertura)
    completa = "completa" if cubiertos == total else "incompleta"
    cobertura = f"cobertura {completa}, {cubiertos} de {total} frentes"
    estado, lista = huella.conflictos
    if estado == "no_comparables":
        conflictos = "fuentes registrales no comparadas"
    elif not lista:
        conflictos = "sin conflictos"
    else:
        conflictos = "1 conflicto" if len(lista) == 1 else f"{len(lista)} conflictos"
    return f"{cobertura}; {conflictos}"


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


def _coincidencias_de(resultado: Mapping[str, Any], tipo: str) -> list[Coincidencia]:
    """Las coincidencias de una respuesta `coincidencias` de listas; nunca ninguna.

    Un hecho legible da su lista, su fuente y su fecha. Si no hay hechos, o un hecho no se puede
    leer, queda una coincidencia del `tipo` consultado con la fuente y la fecha de los metadatos
    de la respuesta, si existen.
    """
    metadatos = resultado.get("metadatos")
    metadatos = metadatos if isinstance(metadatos, Mapping) else {}
    fuentes = metadatos.get("fuentes")
    fuentes = fuentes if isinstance(fuentes, list) else []
    sin_detalle = Coincidencia(
        tipo,
        "",
        ", ".join(f for f in fuentes if isinstance(f, str)),
        str(metadatos.get("fecha") or ""),
    )
    hechos = resultado.get("hechos")
    if not isinstance(hechos, list) or not hechos:
        return [sin_detalle]
    coincidencias = []
    for hecho in hechos:
        contenido = hecho.get("contenido") if isinstance(hecho, Mapping) else None
        datos = hecho.get("metadatos") if isinstance(hecho, Mapping) else None
        if not isinstance(contenido, Mapping) or not isinstance(datos, Mapping):
            coincidencias.append(sin_detalle)
            continue
        coincidencias.append(
            Coincidencia(
                tipo,
                str(contenido.get("lista", "")),
                str(datos.get("fuente", "")),
                str(datos.get("fecha", "")),
            )
        )
    return coincidencias


# --------------------------------------------------------------------------- fallo cerrado


def _registrar_fallo(
    tipo: str,
    error: Exception,
    estado: EstadoCaso,
    eventos: RegistroEventos,
    frente: Frente | None,
    detalle: str | None = None,
) -> None:
    """Deja el sello y el evento; el texto de la excepción no sale al modelo ni al evento."""
    estado.libro.fallo_de_hook = f"{tipo}: {type(error).__name__}"
    eventos.registrar(
        TIPO_FALLO_DE_HOOK,
        frente,
        detalle
        or f"Un hook de {tipo} falló: la regla no se pudo verificar y se bloquea por precaución.",
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
                # Sin poder evaluar el cierre se bloquea, pero con el mismo límite de devoluciones.
                if estado.libro.cierres_impedidos >= MAX_CIERRES_IMPEDIDOS:
                    estado.cierre_sin_escalar = True
                    return permitir()
                estado.libro.cierres_impedidos += 1
                return bloquear_cierre(MOTIVO_FALLO_DE_HOOK)
            return permitir()

    return envuelto


def degradar_escalamiento(hook: Hook, estado: EstadoCaso, eventos: RegistroEventos) -> Hook:
    """Envuelve el `PreToolUse` de `escalar_a_cumplimiento`, que **nunca deniega** (#8, R6).

    Escalar es la acción segura. Ante una excepción calculando la cobertura, sella el libro (el
    caso no figura como completo y los `PreToolUse` de las reglas deniegan, #7) y deja pasar el
    escalamiento con la cobertura fija `COBERTURA_NO_CALCULADA`; si la entrada no es un objeto, la
    deja pasar sin cambios y la pasarela la rechaza por su cuenta.
    """

    async def envuelto(entrada: dict[str, Any], tool_use_id: str | None, contexto: Any):
        try:
            return await hook(entrada, tool_use_id, contexto)
        except Exception as error:
            _registrar_fallo(
                "PreToolUse",
                error,
                estado,
                eventos,
                None,
                "Un hook de PreToolUse falló al calcular la cobertura del escalamiento: el "
                "escalamiento sale con la cobertura declarada como no calculada.",
            )
            argumentos = entrada.get("tool_input")
            if isinstance(argumentos, Mapping):
                return reemplazar_entrada({**argumentos, "cobertura": [COBERTURA_NO_CALCULADA]})
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
        self, herramienta: str | None, hook: Hook, tipo: str, frente: Frente | None
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
                # Sin `fallar_cerrado`: el escalamiento nunca se deniega (#8, R6).
                HookMatcher(
                    matcher=HERRAMIENTA_ESCALAR,
                    hooks=[degradar_escalamiento(self._escalar_previo, self.estado, self.eventos)],
                ),
            ],
            "PostToolUse": [
                self._matcher(HERRAMIENTA_ESCALAR, self._escalar_posterior, "PostToolUse", None),
                # #9, R7: confirma la huella que dejó pendiente el `PreToolUse` del informe.
                self._matcher(HERRAMIENTA_INFORME, self._informe_posterior, "PostToolUse", None),
            ],
            "PostToolUseFailure": [
                self._matcher(
                    HERRAMIENTA_ESCALAR,
                    self._fallo_de_herramienta(None),
                    "PostToolUseFailure",
                    None,
                ),
                self._matcher(
                    HERRAMIENTA_INFORME, self._informe_fallido, "PostToolUseFailure", None
                ),
            ],
            "Stop": [self._matcher(None, self._cierre, "Stop", None)],
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

    # -------------------------------------------------------------- cierre garantizado (FR-007)

    async def _cierre(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`Stop` del coordinador: no termina sin el escalamiento ni sin el informe vigente.

        Escalamiento (#7) e informe (#9, R8) comparten el contador `cierres_impedidos` del libro,
        no `stop_hook_active` (R3). Es una protección: pasadas `MAX_CIERRES_IMPEDIDOS` devoluciones
        deja terminar, pero el caso queda marcado `cierre_sin_escalar`, `cierre_sin_informe` o los
        dos, y nunca figura como completo ni habilitado.
        """
        motivo = evaluar_cierre(self.estado)
        if motivo is None:
            return permitir()
        falta_escalar, falta_informe = falta_para_cerrar(self.estado)
        regla = reglas_de(causas_vigentes(self.estado.libro)) if falta_escalar else None
        if self.estado.libro.cierres_impedidos >= MAX_CIERRES_IMPEDIDOS:
            if falta_escalar:
                self.estado.cierre_sin_escalar = True
                self.eventos.registrar(
                    TIPO_CIERRE_SIN_ESCALAR,
                    None,
                    "El caso termina sin el escalamiento obligatorio: se agotaron las "
                    f"{MAX_CIERRES_IMPEDIDOS} devoluciones del cierre.",
                    regla=regla,
                )
            if falta_informe:
                self.estado.cierre_sin_informe = True
                self.eventos.registrar(
                    TIPO_CIERRE_SIN_INFORME,
                    None,
                    "El caso termina sin el informe vigente: se agotaron las "
                    f"{MAX_CIERRES_IMPEDIDOS} devoluciones del cierre.",
                )
            return permitir()
        self.estado.libro.cierres_impedidos += 1
        self.eventos.registrar(TIPO_CIERRE_IMPEDIDO, None, motivo, regla=regla)
        return bloquear_cierre(motivo)

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
        """`PostToolUse` de listas: guarda la consulta válida y cada coincidencia (FR-004).

        Falla cerrado ante la duda (FR-012):

        - Solo `sin_coincidencias` explícito cuenta como consulta limpia.
        - `coincidencias` deja una coincidencia por hecho. Si no trae hechos, o un hecho no se
          puede leer, la fuente dice igual que hay coincidencia: se guarda una del tipo consultado,
          con la fuente y la fecha de los metadatos de la respuesta, y obliga a escalar.
        - Cualquier otro resultado no cuenta como consulta y deja `consulta_fallida`.
        """
        resultado, error = leer_respuesta(entrada.get("tool_response"))
        if resultado is None:
            self._constancia_de_consulta_fallida(Frente.LISTAS, error)
            return permitir()
        tipo_de_resultado = resultado.get("resultado")
        if tipo_de_resultado not in ("coincidencias", "sin_coincidencias"):
            self.eventos.registrar(
                TIPO_CONSULTA_FALLIDA,
                Frente.LISTAS,
                "La consulta de listas devolvió un resultado que no es «coincidencias» ni "
                "«sin_coincidencias»; no cuenta.",
            )
            return permitir()
        argumentos = entrada.get("tool_input")
        argumentos = argumentos if isinstance(argumentos, Mapping) else {}
        tipo = str(argumentos.get("tipo", "")).strip().casefold()
        nombre, identificador = argumentos.get("nombre"), argumentos.get("identificador")
        self.estado.libro.consultas_listas.append(
            ConsultaListas(
                tipo,
                nombre if isinstance(nombre, str) else None,
                identificador if isinstance(identificador, str) else None,
                tipo_de_resultado,
            )
        )
        if tipo_de_resultado == "coincidencias":
            tipo_de_la_coincidencia = tipo if tipo in ("comercio", "persona") else "comercio"
            self.estado.libro.coincidencias.extend(
                _coincidencias_de(resultado, tipo_de_la_coincidencia)
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
        """`PreToolUse` de `registrar_informe` (#7 FR-005; #8 R6; #9 R1, R3, R5).

        Junta en un solo rechazo estructurado las reglas del #7 (`evaluar_informe`), la forma del
        informe (`validar_informe`, la misma de la pasarela) y la fuente consultada de cada
        afirmación (FR-004). Si acepta, la entrada completa lleva el comercio, los conflictos y la
        cobertura del código, y `hallazgos` y `recomendacion` tal como los envió el coordinador.
        """
        sellado = self._sellado(None, None)
        if sellado is not None:
            return sellado
        argumentos = entrada.get("tool_input")
        rechazos = list(evaluar_informe(self.estado, argumentos))
        if not isinstance(argumentos, Mapping):  # las reglas ya lo rechazan
            return self._denegar_informe(rechazos or [Rechazo(MOTIVO_ENTRADA_MALFORMADA, None)], [])
        comercio = comercio_del_informe(self.estado)
        if comercio is None:
            rechazos.append(Rechazo(MOTIVO_SIN_COMERCIO_INFORME, None))
        cobertura = calcular_cobertura(self.estado)
        conflictos = calcular_conflictos(self.estado)
        completa = {
            "comercio": comercio,
            "recomendacion": argumentos.get("recomendacion"),
            "hallazgos": argumentos.get("hallazgos"),
            "conflictos": conflictos.como_entrada(),
            "cobertura": cobertura.lineas(),
        }
        problemas = self._problemas_del_informe(completa)
        if rechazos or problemas:
            return self._denegar_informe(rechazos, problemas)
        self._evento_cobertura("registrar_informe", argumentos, cobertura)
        self._evento_datos(argumentos, completa)
        # R7: la huella se calcula aquí, con los mismos datos que se sustituyen, y queda pendiente
        # hasta que el `PostToolUse` confirme que la pasarela aceptó.
        self.estado.informes_pendientes[tool_use_id or ""] = (
            huella_con(self.estado, cobertura, conflictos),
            completa["recomendacion"],
            False,
        )
        return reemplazar_entrada(completa)

    async def _informe_posterior(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`PostToolUse` de `registrar_informe`: confirma la huella pendiente (R7, FR-016).

        No la recalcula: usa la del `PreToolUse`, así un frente que terminó entre los dos hooks
        deja el informe sin vigencia. Emite `informe_registrado`, sin datos del comercio.
        """
        pendiente = self.estado.informes_pendientes.pop(tool_use_id or "", None)
        resultado, error = leer_respuesta(entrada.get("tool_response"))
        identificador = _identificador_del_informe(resultado)
        if identificador is None:
            self._constancia_de_consulta_fallida(None, error)
            return permitir()
        if pendiente is None:  # sin `PreToolUse` que aceptara: no hay huella que confirmar
            return permitir()
        huella, recomendacion, minimo = pendiente
        self.estado.informes.append(InformeRegistrado(identificador, recomendacion, minimo, huella))
        minimo_texto = " Informe mínimo tras un fallo de hook." if minimo else ""
        self.eventos.registrar(
            TIPO_INFORME_REGISTRADO,
            None,
            f"Informe {identificador} registrado; recomendación: {recomendacion}; "
            f"{_resumen_de_huella(huella)}.{minimo_texto}",
        )
        return permitir()

    async def _informe_fallido(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`PostToolUseFailure` de `registrar_informe`: descarta la huella pendiente."""
        self.estado.informes_pendientes.pop(tool_use_id or "", None)
        _, error = leer_respuesta(entrada.get("error"), es_error=True)
        self._constancia_de_consulta_fallida(None, error)
        return permitir()

    def _problemas_del_informe(self, completa: dict[str, Any]) -> list[Problema]:
        """La forma (sin comercio ni recomendación, que son motivos propios) y las fuentes."""
        recomendacion = completa["recomendacion"]
        para_validar = {
            **completa,
            "comercio": completa["comercio"] or _COMERCIO_PARA_VALIDAR,
            "recomendacion": recomendacion
            if isinstance(recomendacion, str) and recomendacion.strip()
            else "-",
        }
        problemas = validar_informe(para_validar)
        return problemas + problemas_de_fuente(self.estado, completa["hallazgos"])

    def _denegar_informe(self, rechazos: list[Rechazo], problemas: list[Problema]):
        """Deniega el informe con el JSON de R3 y deja `bloqueo_regla` (I.4 si hay problemas)."""
        reglas = {parte for r in rechazos if r.regla for parte in r.regla.split(", ")}
        if problemas:
            reglas.add(REGLA_FUENTE)
        textos = [r.texto for r in rechazos]
        if problemas:
            cantidad = len(problemas)
            plural = "problema" if cantidad == 1 else "problemas"
            textos.append(f"{cantidad} {plural} de forma o de fuente en el informe.")
        self.eventos.registrar(
            TIPO_BLOQUEO_REGLA, None, " ".join(textos), regla=", ".join(sorted(reglas)) or None
        )
        return denegar_informe(rechazos, problemas)

    def _evento_datos(self, argumentos: Mapping[str, Any], completa: dict[str, Any]) -> None:
        """`datos_sustituidos`: lo que el código puso, sin datos del comercio (#9, R5)."""
        comercio, conflictos = completa["comercio"], completa["conflictos"]
        verificado = "comercio verificado" if comercio["verificado"] else "comercio sin verificar"
        distintos = [p for p in ("comercio", "conflictos") if argumentos.get(p) != completa[p]]
        declarado = (
            f"Lo declarado por el coordinador era distinto en: {', '.join(distintos)}."
            if distintos
            else "Coincide con lo declarado por el coordinador."
        )
        self.eventos.registrar(
            TIPO_DATOS_SUSTITUIDOS,
            None,
            f"Datos del código puestos en registrar_informe: {verificado}; "
            f"{conflictos['resumen']} {declarado}",
        )

    async def _escalar_previo(
        self, entrada: dict[str, Any], tool_use_id: str | None, contexto: Any
    ) -> dict[str, Any]:
        """`PreToolUse` de `escalar_a_cumplimiento`: pone la cobertura del código (#8, R6).

        No mira el sello del libro y nunca deniega: escalar es la acción segura. Lo envuelve
        `degradar_escalamiento`, no `fallar_cerrado`.
        """
        argumentos = entrada.get("tool_input")
        if not isinstance(argumentos, Mapping):
            return permitir()  # sin entrada que completar: la pasarela la rechaza
        return self._sustituir_cobertura("escalar_a_cumplimiento", argumentos)

    def _sustituir_cobertura(self, herramienta: str, argumentos: Mapping[str, Any]):
        """La entrada completa con la cobertura calculada y el evento `cobertura_sustituida`."""
        cobertura = calcular_cobertura(self.estado)
        self._evento_cobertura(herramienta, argumentos, cobertura)
        return reemplazar_entrada({**argumentos, "cobertura": cobertura.lineas()})

    def _evento_cobertura(
        self, herramienta: str, argumentos: Mapping[str, Any], cobertura: CoberturaCaso
    ) -> None:
        """`cobertura_sustituida` (#8): se emite antes de que la pasarela acepte la llamada.

        Dice qué cobertura se puso en ella y si la que declaró el coordinador era distinta, nunca
        que quedó registrada.
        """
        lineas = cobertura.lineas()
        cubiertos = sum(c.cubierto for c in cobertura.frentes.values())
        faltan = [f.value for f, c in cobertura.frentes.items() if not c.cubierto]
        resumen = (
            f"completa, {cubiertos} de {len(cobertura.frentes)} frentes"
            if cobertura.completa
            else f"incompleta, {cubiertos} de {len(cobertura.frentes)} frentes "
            f"(falta {', '.join(faltan)})"
        )
        declarada = (
            "La declarada por el coordinador era distinta y se sustituyó por la calculada."
            if argumentos.get("cobertura") != lineas
            else "Coincide con la declarada por el coordinador."
        )
        self.eventos.registrar(
            TIPO_COBERTURA_SUSTITUIDA,
            None,
            f"Cobertura puesta en {herramienta}: {resumen}. {declarada}",
        )

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
