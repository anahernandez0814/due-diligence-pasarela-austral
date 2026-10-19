"""El código del proyecto no controla el ciclo agéntico (R5, R8, FR-010, FR-011, Q4, Q6).

ES UNA COMPROBACIÓN DE FORMA, no una prueba de la ausencia total de control propio: recorre con
`ast` los módulos que ejecutan el ciclo (`coordinador`, `ejecutor` y `delegacion`) y comprueba que
no tienen `while`, que no comparan el texto de un mensaje y que `max_turns` solo vive en
`configuracion.py`. Un control escondido en otra forma (una función auxiliar, un `for` con `break`)
no lo detectaría; por eso las otras garantías son los tests de comportamiento (`test_terminacion`
y `test_coordinador`) y la revisión.

`sondeo_aislamiento.py` es una herramienta manual, fuera del flujo de un caso: usa `max_turns=1`
para provocar el límite y lee el texto del agente para la verificación del aislamiento. Por eso
queda fuera de las reglas de `max_turns` y de texto, pero no de las reglas de entorno y claves.
"""

import ast
import re
from pathlib import Path

PAQUETE = Path(__file__).resolve().parent
MODULOS_DEL_CICLO = ("coordinador.py", "ejecutor.py", "delegacion.py")
# Los sondeos manuales provocan el límite de turnos a propósito para medirlo (R5 del #6, R3 del #7).
FUERA_DE_MAX_TURNS = {"configuracion.py", "sondeo_aislamiento.py", "sondeo_hooks.py"}
ATRIBUTOS_DE_TEXTO = {"text", "result", "respuesta", "resumen"}
ARCHIVO_DE_ENTORNO = "." + "env"  # construido al ejecutar: ningún archivo lo escribe literal


def _modulos():
    """Los módulos del paquete, sin los tests."""
    return sorted(p for p in PAQUETE.glob("*.py") if not p.name.startswith("test_"))


def _arbol(ruta: Path) -> ast.AST:
    return ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))


# ---------------------------------------------------------------- detectores (con su prueba)


def hay_while(arbol: ast.AST) -> bool:
    return any(isinstance(nodo, ast.While) for nodo in ast.walk(arbol))


def compara_texto(arbol: ast.AST) -> bool:
    """Una comparación (`==`, `in`, `is`…) que involucra el texto de un mensaje."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Compare):
            for hijo in ast.walk(nodo):
                if isinstance(hijo, ast.Attribute) and hijo.attr in ATRIBUTOS_DE_TEXTO:
                    return True
    return False


def usa_max_turns(arbol: ast.AST) -> bool:
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.keyword) and nodo.arg == "max_turns":
            return True
        if isinstance(nodo, ast.Attribute) and nodo.attr in {"max_turns", "MAX_TURNOS_SEGURIDAD"}:
            return True
        if isinstance(nodo, ast.Name) and nodo.id in {"max_turns", "MAX_TURNOS_SEGURIDAD"}:
            return True
    return False


def llama_a(arbol: ast.AST, nombre: str) -> bool:
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            funcion = nodo.func
            if isinstance(funcion, ast.Name) and funcion.id == nombre:
                return True
            if isinstance(funcion, ast.Attribute) and funcion.attr == nombre:
                return True
    return False


def test_los_detectores_encuentran_lo_que_buscan_y_no_inventan():
    malo = ast.parse(
        "while True:\n"
        "    if 'listo' in bloque.text:\n"
        "        break\n"
        "for i in range(3):\n"
        "    pass\n"
        "opciones(max_turns=3)\n"
        "cargar_entorno()\n"
    )
    bueno = ast.parse(
        "async for mensaje in consulta():\n"
        "    if isinstance(mensaje, ResultMessage):\n"
        "        clasificacion = clasificar_resultado(mensaje)\n"
        "    elif mensaje.subtype == 'success':\n"
        "        pass\n"
        "respuesta = bloque.text\n"
    )
    assert (
        hay_while(malo)
        and compara_texto(malo)
        and usa_max_turns(malo)
        and llama_a(malo, "cargar_entorno")
    )
    assert not (hay_while(bueno) or compara_texto(bueno) or usa_max_turns(bueno))
    assert not llama_a(bueno, "cargar_entorno")


# ---------------------------------------------------------------- el ciclo (FR-010)


def test_ningun_modulo_del_ciclo_tiene_while():
    for nombre in MODULOS_DEL_CICLO:
        assert not hay_while(_arbol(PAQUETE / nombre)), f"{nombre} tiene un while"


def test_ningun_modulo_del_ciclo_compara_el_texto_de_un_mensaje():
    for nombre in MODULOS_DEL_CICLO:
        assert not compara_texto(_arbol(PAQUETE / nombre)), f"{nombre} compara texto de un mensaje"


def test_max_turns_solo_aparece_en_configuracion():
    for ruta in _modulos():
        if ruta.name in FUERA_DE_MAX_TURNS:
            continue
        assert not usa_max_turns(_arbol(ruta)), f"{ruta.name} usa max_turns"
    assert usa_max_turns(_arbol(PAQUETE / "configuracion.py"))


def test_max_turns_esta_documentado_como_proteccion_de_seguridad():
    texto = (PAQUETE / "configuracion.py").read_text(encoding="utf-8")
    cercano = texto[
        texto.index("MAX_TURNOS_SEGURIDAD =") - 600 : texto.index("MAX_TURNOS_SEGURIDAD =")
    ]
    assert "PROTECCIÓN DE SEGURIDAD" in cercano
    assert "no un mecanismo de control" in cercano


# ---------------------------------------------------------------- entorno y claves (R8)


def test_cargar_entorno_solo_se_llama_desde_el_punto_de_entrada():
    llamadas = [ruta.name for ruta in _modulos() if llama_a(_arbol(ruta), "cargar_entorno")]
    # #11 (R8): la interfaz de chat es el segundo punto de entrada; la lista es exacta.
    assert llamadas == ["__main__.py", "chat.py"]


def test_ningun_modulo_nombra_el_archivo_de_entorno_ni_escribe_una_clave():
    patron_archivo = re.compile(
        r"(?<![A-Za-z0-9_])" + re.escape(ARCHIVO_DE_ENTORNO) + r"(?![A-Za-z0-9_])"
    )
    patron_clave = re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}|ANTHROPIC_API_KEY\s*=")
    for ruta in _modulos():
        texto = ruta.read_text(encoding="utf-8")
        assert not patron_archivo.search(texto), f"{ruta.name} nombra el archivo de entorno"
        assert not patron_clave.search(texto), f"{ruta.name} escribe una clave"
