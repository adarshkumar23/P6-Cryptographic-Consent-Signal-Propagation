"""
Boundary test: `app/` (the satellite) must never import anything from
`core-side-patch/`, and `core-side-patch/routes/patent_ingest_p6.py`
must never import anything from `app/`. The two sides talk only over
HTTP, never via a shared Python import.
"""
import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "app"
CORE_PATCH_DIR = REPO_ROOT / "core-side-patch"


def _imported_module_roots(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_app_never_imports_core_side_patch():
    for py_file in APP_DIR.rglob("*.py"):
        roots = _imported_module_roots(py_file)
        assert "core_side_patch" not in roots, f"{py_file} imports core-side-patch"


def test_core_side_patch_never_imports_app():
    for py_file in CORE_PATCH_DIR.rglob("*.py"):
        roots = _imported_module_roots(py_file)
        assert "app" not in roots, f"{py_file} imports the satellite's app package"


def test_core_side_patch_does_not_import_pynacl_or_local_crypto_module():
    """Core-side code may use `cryptography` directly (to independently
    re-verify), but must not import this repo's app.crypto module or
    PyNaCl — core gets its own self-contained verification, not a
    shared dependency on the satellite's signing code."""
    for py_file in CORE_PATCH_DIR.rglob("*.py"):
        roots = _imported_module_roots(py_file)
        assert "nacl" not in roots, f"{py_file} imports PyNaCl"
        assert "app" not in roots
