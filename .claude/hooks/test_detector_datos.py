"""Pruebas del detector de datos con forma real.

Ningún valor con forma real se escribe en este archivo: los positivos se generan en
tiempo de ejecución (dígito de Luhn y DV de la DIAN calculados, credenciales
concatenadas con caracteres aleatorios).
"""

import random
import re
import string
import time
from pathlib import Path

import detector_datos
import pytest

RAIZ = Path(__file__).resolve().parents[2]
AZAR = random.Random(20261016)

# --- Generadores --------------------------------------------------------------------


def digito_luhn(cuerpo: str) -> str:
    """Dígito que hace válido por Luhn al número `cuerpo + dígito`."""
    total = 0
    for i, c in enumerate(reversed(cuerpo)):
        d = int(c)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def tarjeta(prefijo: str, longitud: int) -> str:
    cuerpo = prefijo + "".join(AZAR.choice(string.digits) for _ in range(longitud - 2))
    return cuerpo + digito_luhn(cuerpo)


def agrupar(numero: str, separador: str) -> str:
    return separador.join(numero[i : i + 4] for i in range(0, len(numero), 4))


def dv_dian(nueve: str) -> int:
    pesos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    s = sum(int(d) * p for d, p in zip(reversed(nueve), pesos, strict=False)) % 11
    return s if s in (0, 1) else 11 - s


def nueve_digitos() -> str:
    return str(AZAR.randint(800_000_000, 999_999_999))


def con_puntos(nueve: str) -> str:
    return f"{nueve[:3]}.{nueve[3:6]}.{nueve[6:]}"


def aleatorio(alfabeto: str, n: int) -> str:
    return "".join(AZAR.choice(alfabeto) for _ in range(n))


ALNUM = string.ascii_letters + string.digits


def tipos(texto: str) -> set[str]:
    return {tipo for tipo, _ in detector_datos.buscar(texto)}


# --- Tarjeta ------------------------------------------------------------------------


@pytest.mark.parametrize("prefijo", ["2", "3", "4", "5", "6"])
@pytest.mark.parametrize("longitud", [13, 16, 19])
@pytest.mark.parametrize("separador", [None, " ", "-"])
def test_tarjeta_coincide(prefijo, longitud, separador):
    numero = tarjeta(prefijo, longitud)
    texto = numero if separador is None else agrupar(numero, separador)
    assert "tarjeta" in tipos(f"pago con {texto} hoy")


def test_tarjeta_con_un_digito_cambiado_no_coincide():
    numero = tarjeta("4", 16)
    cambiado = numero[:5] + str((int(numero[5]) + 1) % 10) + numero[6:]
    assert "tarjeta" not in tipos(cambiado)


def test_tarjeta_con_prefijo_1_no_coincide():
    assert "tarjeta" not in tipos(tarjeta("1", 16))


def test_marca_de_tiempo_en_milisegundos_no_coincide():
    assert detector_datos.buscar(str(time.time_ns() // 10**6)) == []


def test_tarjeta_dentro_de_un_numero_mas_largo_no_coincide():
    assert "tarjeta" not in tipos(tarjeta("4", 16) + "7")
    assert "tarjeta" not in tipos("x" + tarjeta("4", 16))


# --- NIT ----------------------------------------------------------------------------


def test_nit_con_guion_coincide():
    nueve = nueve_digitos()
    assert "nit" in tipos(f"{nueve}-{dv_dian(nueve)}")
    assert "nit" in tipos(f"{con_puntos(nueve)}-{dv_dian(nueve)}")


@pytest.mark.parametrize("forma", ["NIT {n}{d}", "nit: {n}{d}", "NIT No. {n}{d}", "NIT # {n}{d}"])
def test_nit_tras_la_palabra_nit_coincide(forma):
    nueve = nueve_digitos()
    assert "nit" in tipos(forma.format(n=nueve, d=dv_dian(nueve)))


def test_nit_con_dv_erroneo_no_coincide():
    nueve = nueve_digitos()
    erroneo = (dv_dian(nueve) + 1) % 10
    assert "nit" not in tipos(f"{nueve}-{erroneo}")
    assert "nit" not in tipos(f"NIT {nueve}{erroneo}")


# --- Cédula -------------------------------------------------------------------------


def cedula() -> str:
    return str(AZAR.randint(10_000_000, 99_999_999))


@pytest.mark.parametrize(
    "contexto",
    [
        "cédula",
        "Cedula",
        "cédula de ciudadanía",
        "C.C.",
        "CC",
        "documento de identidad",
        "identificación",
        "Identificacion",
    ],
)
def test_cedula_con_contexto_coincide(contexto):
    numero = cedula()
    assert "cedula" in tipos(f"{contexto} {numero}")
    assert "cedula" in tipos(f"{contexto}: No. {numero[:2]}.{numero[2:5]}.{numero[5:]}")


def test_cedula_sin_contexto_no_coincide():
    assert detector_datos.buscar(f"referencia {cedula()}") == []


def test_cedula_precedida_de_pesos_no_coincide():
    numero = cedula()
    assert "cedula" not in tipos(f"cédula: ${numero[:2]}.{numero[2:5]}.{numero[5:]}")


def test_cc_en_minusculas_no_es_contexto():
    assert "cedula" not in tipos(f"cc {cedula()}")


# --- Credenciales -------------------------------------------------------------------


def credenciales_validas() -> list[str]:
    privada = "-----BEGIN " + "RSA PRI" + "VATE KEY-----"
    return [
        "gh" + "p_" + aleatorio(ALNUM, 20),
        "gh" + "o_" + aleatorio(ALNUM, 20),
        "gh" + "u_" + aleatorio(ALNUM, 20),
        "gh" + "s_" + aleatorio(ALNUM, 20),
        "gh" + "r_" + aleatorio(ALNUM, 20),
        "github" + "_pat_" + aleatorio(ALNUM + "_", 20),
        "sk-" + "ant-" + aleatorio(ALNUM + "_-", 20),
        "AK" + "IA" + aleatorio(string.ascii_uppercase + string.digits, 16),
        privada,
    ]


@pytest.mark.parametrize("indice", range(9))
def test_credencial_coincide(indice):
    assert "credencial" in tipos(f"x = '{credenciales_validas()[indice]}'")


def test_credenciales_con_un_caracter_menos_no_coinciden():
    cortas = [
        "gh" + "p_" + aleatorio(ALNUM, 19),
        "github" + "_pat_" + aleatorio(ALNUM, 19),
        "sk-" + "ant-" + aleatorio(ALNUM, 19),
        "AK" + "IA" + aleatorio(string.ascii_uppercase + string.digits, 15),
    ]
    for corta in cortas:
        assert "credencial" not in tipos(f"x = '{corta}'")


def test_prefijos_sin_longitud_minima_no_coinciden():
    assert detector_datos.buscar("Los tokens empiezan por gh" + "p_ o por sk-" + "ant-.") == []


# --- Permitidos (FR-006) ------------------------------------------------------------


def test_mensaje_de_ejemplo_del_enunciado_no_coincide():
    enunciado = (RAIZ / "docs" / "enunciado.md").read_text(encoding="utf-8")
    mensaje = re.search(r'"(Necesito el due diligence[^"]*)"', enunciado)
    assert mensaje is not None
    assert "CO-TV-0001" in mensaje.group(1)
    assert detector_datos.buscar(mensaje.group(1)) == []


@pytest.mark.parametrize("texto", ["CO-TV-0001", "$80.000.000", "2026-10-16"])
def test_datos_ficticios_no_coinciden(texto):
    assert detector_datos.buscar(texto) == []


# --- Resultado ----------------------------------------------------------------------


def test_resultado_solo_tiene_tipo_y_linea():
    numero = tarjeta("5", 16)
    hallazgos = detector_datos.buscar(f"primera línea\nsegunda {numero}\n")
    assert hallazgos == [("tarjeta", 2)]
    assert numero not in repr(hallazgos)
