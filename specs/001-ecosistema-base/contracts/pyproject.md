# Contrato: `pyproject.toml`

Secciones y claves obligatorias. Las versiones exactas de ruff y pytest las fija `uv.lock`.

```toml
[project]
name = "due-diligence-pasarela-austral"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = []

[dependency-groups]
dev = ["pytest", "ruff"]

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = ["due_diligence", "servidor_mcp"]

[tool.ruff]
target-version = "py312"
line-length = 100
extend-exclude = [".specify"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["src"]
python_files = ["test_*.py"]
addopts = ["--import-mode=importlib"]
```

## Invariantes

- No existe una carpeta `tests/`; los tests viven junto al módulo que prueban.
- `uv run pytest --collect-only -q` lista al menos un test en `src/due_diligence/` y otro en
  `src/servidor_mcp/`, ambos en archivos `test_humo.py`.
- `uv sync`, `uv run ruff check .`, `uv run ruff format --check .` y `uv run pytest`
  terminan con código 0.
