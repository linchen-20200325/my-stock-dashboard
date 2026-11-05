"""Contract tests for standard-library-only data import inventory."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "scripts" / "audit_data_layer_references.py"
spec = importlib.util.spec_from_file_location("_audit_data_layer_refs", TOOL)
assert spec is not None and spec.loader is not None
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


def test_default_prefix_keeps_package_symbol_candidates(tmp_path, capsys):
    package = tmp_path / "src"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from . import data as public_data\n"
        "from src import data\n"
        "from src import database\n"
        "import src.database\n"
        "import src.data.fetcher\n", encoding="utf-8")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert mod.main(["--repo", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["import_count"] == 5
    assert result["selected_count"] == 3
    assert [(r["imported"], r.get("symbol")) for r in result["imports"]] == [
        ("src", "data"), ("src", "data"), ("src.data.fetcher", None),
    ]
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_child_prefix_keeps_symbol_reference_without_resolving_it(tmp_path, capsys):
    package = tmp_path / "src" / "data"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "from . import core\n"
        "from src.data import core as alias\n"
        "from src.data import core_extra\n"
        "import src.data.core_extra\n"
        "from .core import VALUE\n", encoding="utf-8")
    assert mod.main(["--repo", str(tmp_path), "--prefix", "src.data.core"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["selected_count"] == 3
    assert [(r["imported"], r.get("symbol")) for r in result["imports"]] == [
        ("src.data", "core"), ("src.data", "core"), ("src.data.core", "VALUE"),
    ]


def test_cli_parse_error_returns_nonzero_and_retains_valid_records(tmp_path, capsys):
    package = tmp_path / "src"
    package.mkdir()
    (package / "bad.py").write_text("def broken(\n", encoding="utf-8")
    (package / "good.py").write_text(
        "from src import data\nraise AssertionError('must never execute')\n", encoding="utf-8")
    assert mod.main(["--repo", str(tmp_path)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["parse_errors"] == [{"file": "src/bad.py", "error": "SyntaxError"}]
    assert result["selected_count"] == 1
