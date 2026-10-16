"""Revisión del repositorio completo con el detector (FR-007, SC-002, R8).

Cubre lo que no pasa por los hooks: recorre los archivos versionados (`git ls-files`),
salta los binarios y falla si encuentra un dato con forma real o una credencial. Informa
`archivo:línea:tipo`, nunca el valor.
"""

import subprocess
from pathlib import Path

import detector_datos
from test_guarda_datos import TIPOS, generar

RAIZ = Path(__file__).resolve().parents[2]
BYTES_DE_MUESTRA = 8192


def archivos_versionados(raiz: Path) -> list[str]:
    salida = subprocess.run(
        ["git", "-C", str(raiz), "ls-files", "-z"], capture_output=True, check=True
    ).stdout
    return [r for r in salida.decode("utf-8").split("\0") if r]


def hallazgos(raiz: Path) -> list[str]:
    """`archivo:línea:tipo` de cada hallazgo en los archivos versionados de `raiz`.

    Salta los binarios (un byte nulo en los primeros 8 KB) y los archivos que están en el
    índice pero ya no en disco.
    """
    encontrados = []
    for relativa in archivos_versionados(raiz):
        ruta = raiz / relativa
        if not ruta.is_file():
            continue
        datos = ruta.read_bytes()
        if b"\0" in datos[:BYTES_DE_MUESTRA]:
            continue
        texto = datos.decode("utf-8", errors="replace")
        encontrados += [
            f"{relativa}:{linea}:{tipo}" for tipo, linea in detector_datos.buscar(texto)
        ]
    return encontrados


def test_el_repositorio_no_tiene_datos_con_forma_real():
    encontrados = hallazgos(RAIZ)
    assert encontrados == [], "Datos con forma real:\n" + "\n".join(encontrados)


def test_el_recorrido_detecta_toda_la_muestra(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for tipo in TIPOS:
        (tmp_path / f"{tipo}.txt").write_text(f"línea uno\n{generar(tipo)}\n", encoding="utf-8")
    (tmp_path / "limpio.md").write_text("CO-TV-0001 y $80.000.000\n", encoding="utf-8")
    (tmp_path / "binario.bin").write_bytes(b"\0" + generar("tarjeta").encode())
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    assert sorted(hallazgos(tmp_path)) == sorted(f"{tipo}.txt:2:{tipo}" for tipo in TIPOS)
