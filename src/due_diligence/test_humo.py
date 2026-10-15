"""Test de humo: la configuración de pytest descubre y ejecuta tests junto al código."""

import sys
from pathlib import Path

import due_diligence


def test_paquete_se_carga_desde_src():
    ruta = Path(due_diligence.__file__).resolve().parent
    assert ruta.parts[-2:] == ("src", "due_diligence")


def test_version_de_python():
    assert sys.version_info[:2] == (3, 12)
