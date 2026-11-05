"""Contract tests for standard-library-only data import inventory."""
from __future__ import annotations

import importlib.util
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "scripts" / "audit_data_layer_references.py"
spec = importlib.util.spec_from_file_location("_audit_data_layer_refs", TOOL)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_detects_regular_and_relative_imports(tmp_path):
    package = tmp_path / "src" / "services"
    package.mkdir(parents=True)
    (package / "example.py").write_text(
        "import src.data.stock.fetcher\n"
        "from src.data.core import DATA_REGISTRY\n"
        "from .helper import fn\n", encoding="utf-8")
    records = mod.inventory(tmp_path)["imports"]
    assert [(x["imported"], x.get("symbol")) for x in records] == [
        ("src.data.stock.fetcher", None),
        ("src.data.core", "DATA_REGISTRY"),
        ("src.services.helper", "fn"),
    ]


def test_does_not_execute_imported_code(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "bomb.py").write_text(
        "import src.data.core\nraise AssertionError('must never execute')\n",
        encoding="utf-8")
    assert mod.inventory(tmp_path)["import_count"] == 1


def test_parse_errors_are_explicit(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "bad.py").write_text("def broken(\n", encoding="utf-8")
    result = mod.inventory(tmp_path)
    assert result["parse_errors"] == [{"file": "src/bad.py", "error": "SyntaxError"}]


def test_no_repo_writes(tmp_path):
    d = tmp_path / "shared"
    d.mkdir()
    (d / "x.py").write_text("import src.data.core\n", encoding="utf-8")
    before = sorted(x.relative_to(tmp_path) for x in tmp_path.rglob("*"))
    assert mod.inventory(tmp_path)["import_count"] == 1
    after = sorted(x.relative_to(tmp_path) for x in tmp_path.rglob("*"))
    assert before == after
