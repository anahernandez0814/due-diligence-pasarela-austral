"""Test de humo: mismo nombre de archivo que en due_diligence, descubierto sin choque."""

import sys
from pathlib import Path

import servidor_mcp


def test_paquete_se_carga_desde_src():
    ruta = Path(servidor_mcp.__file__).resolve().parent
    assert ruta.parts[-2:] == ("src", "servidor_mcp")


def test_version_de_python():
    assert sys.version_info[:2] == (3, 12)
