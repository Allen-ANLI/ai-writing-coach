"""Every third-party module imported by app/ must be a declared RUNTIME
dependency. The production Docker image installs the package without the dev
extras, so a dev-only dependency that app code imports crashes the image.
This guard caught httpx being dev-only while the LanguageTool client, LLM
providers and embeddings all import it (Slice 11b).
"""

import ast
import pathlib
import sys
import tomllib

from packaging.requirements import Requirement

BACKEND = pathlib.Path(__file__).resolve().parents[1]

# Import name -> the distribution that provides it (normalized names).
IMPORT_TO_DISTRIBUTION = {
    "argon2": "argon2-cffi",
    "jwt": "pyjwt",
    "pydantic_settings": "pydantic-settings",
    # starlette ships with fastapi; uvicorn/alembic/psycopg are used via CLI
    # and the DB URL rather than app imports, so they are checked separately.
    "starlette": "fastapi",
}
CLI_DISTRIBUTIONS = {"uvicorn", "alembic", "psycopg"}


def _normalize(name: str) -> str:
    return name.lower().replace("-", "_")


def _app_imports() -> set[str]:
    stdlib = set(sys.stdlib_module_names)
    modules: set[str] = set()
    for path in (BACKEND / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
    return {m for m in modules if m and m not in stdlib and m != "app"}


def test_app_imports_are_runtime_dependencies():
    pyproject = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = {_normalize(Requirement(dep).name) for dep in pyproject["project"]["dependencies"]}
    missing = []
    for module in sorted(_app_imports()):
        distribution = _normalize(IMPORT_TO_DISTRIBUTION.get(module, module))
        if distribution not in runtime:
            missing.append(f"{module} (distribution {distribution})")
    assert not missing, (
        "app/ imports modules that are not declared runtime dependencies "
        f"(production image installs without dev extras): {missing}"
    )


def test_cli_and_driver_distributions_declared():
    pyproject = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = {_normalize(Requirement(dep).name) for dep in pyproject["project"]["dependencies"]}
    for distribution in CLI_DISTRIBUTIONS:
        assert _normalize(distribution) in runtime or any(
            name.startswith(_normalize(distribution)) for name in runtime
        ), f"{distribution} must be a runtime dependency"
