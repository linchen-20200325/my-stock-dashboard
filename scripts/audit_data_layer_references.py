"""Read-only static import inventory for data-layer refactors.

This is NOT a dead-code oracle: reflection, runtime plugin loading,
dynamic imports, and session keys are outside its evidence scope.
Never imports application modules or writes to the repository.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

SCAN_ROOTS = ("src", "shared", "scripts", "tests")
ROOT_ENTRYPOINTS = ("app.py", "app_ui2.py")


def _python_files(root: Path):
    for part in SCAN_ROOTS:
        directory = root / part
        if directory.is_dir():
            for f in sorted(directory.rglob("*.py")):
                if not any(x in {".venv", "venv", "__pycache__", ".git"}
                           or x.startswith("wt-") for x in f.relative_to(root).parts):
                    yield f
    for part in ROOT_ENTRYPOINTS:
        f = root / part
        if f.is_file():
            yield f


def inventory(root: Path) -> dict:
    """Return deterministic AST-only import inventory without executing code."""
    root = root.resolve()
    records = []
    problems = []
    for f in _python_files(root):
        rel = f.relative_to(root).as_posix()
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError, OSError) as e:
            problems.append({"file": rel, "error": type(e).__name__})
            continue
        module = rel.removesuffix(".py").replace("/", ".")
        package = module if rel.endswith("/__init__.py") else module.rpartition(".")[0]
        if rel.endswith("/__init__.py"):
            module = module.removesuffix(".__init__")
            package = module
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    records.append({"file": rel, "line": node.lineno,
                                    "imported": alias.name, "kind": "import"})
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split(".") if package else []
                    drop = node.level - 1
                    base = ".".join(parts[:len(parts)-drop]) if drop <= len(parts) else ""
                    target = ".".join(x for x in (base, node.module or "") if x)
                else:
                    target = node.module or ""
                for alias in node.names:
                    records.append({"file": rel, "line": node.lineno,
                                    "imported": target, "symbol": alias.name, "kind": "from"})
    records.sort(key=lambda x: (x["file"], x["line"], x["imported"], x.get("symbol", "")))
    problems.sort(key=lambda x: x["file"])
    return {"scope": "static_ast_imports_only", "imports": records,
            "parse_errors": problems, "import_count": len(records)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--prefix", default="src.data",
                        help="Only show imports under this namespace")
    args = parser.parse_args(argv)
    result = inventory(args.repo)
    prefix = args.prefix
    result["imports"] = [
        record for record in result["imports"]
        if record["imported"] == prefix or record["imported"].startswith(prefix + ".")
    ]
    result["selected_count"] = len(result["imports"])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not result["parse_errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
