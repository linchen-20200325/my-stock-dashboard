"""New UI2 層登記（G1）＋入口 boot smoke／floor（G10）＋production default 未動。

NUI2-GUARD-REGISTRATION／NUI2-PREVIEW（Architecture Gate §6.1、§9 G1／G10）。
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys
import textwrap

import pytest

from shared.ui2_contract.pages import PAGE4_LABELS, PAGE_IDS, SCENARIO_IDS
from shared.ui2_contract.text import PREVIEW_BANNER_TEXT
from tests import test_c3_layering_guard as c3
from tests.test_macro_v2_tab import TestStreamlitFloorCompatibility as _FloorBase

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_UI2 = ROOT / "app_ui2.py"
UI2_DIRS = (ROOT / "src" / "ui2", ROOT / "src" / "services" / "ui2", ROOT / "shared" / "ui2_contract")


def _ui2_files() -> list[pathlib.Path]:
    out = [p for d in UI2_DIRS for p in sorted(d.rglob("*.py")) if "__pycache__" not in p.parts]
    return out + [APP_UI2]


def _rel(p: pathlib.Path) -> str:
    return p.relative_to(ROOT).as_posix()


# ── G1 層登記 ────────────────────────────────────────────────────────
def unregistered(layer_of_file=c3._layer_of_file) -> list[str]:
    return [_rel(p) for p in _ui2_files() if layer_of_file(_rel(p)) is None]


def test_g1_every_ui2_file_has_a_layer():
    assert unregistered() == []


def test_g1_expected_layers():
    assert c3._layer_of_file("src/ui2/shell/app.py") == c3.L5
    assert c3._layer_of_file("src/services/ui2/market_vm.py") == c3.L3
    assert c3._layer_of_file("shared/ui2_contract/models.py") == c3.L0
    assert c3._layer_of_file("app_ui2.py") == c3.L6
    assert c3._layer_of_module("src.ui2.shell.app") == c3.L5
    assert c3._layer_of_module("src.services.ui2.market_vm") == c3.L3
    assert c3._layer_of_module("shared.ui2_contract.models") == c3.L0
    assert c3._layer_of_module("app_ui2") == c3.L6


def test_g1_app_ui2_is_actually_scanned():
    assert "app_ui2.py" in c3._SCAN_FILES
    scanned = {r.relpath for r in c3._ALL_IMPORTS}
    assert "app_ui2.py" in scanned
    assert any(f.startswith("src/ui2/") for f in scanned)


def test_g1_guard_has_teeth_when_registration_removed(monkeypatch):
    """mutation：拔掉 `src/ui2/` 登記 → meta 測試必須抓到（否則五條硬規則會對 UI2 靜默失效）。"""
    monkeypatch.setattr(c3, "_PATH_LAYERS",
                        tuple(x for x in c3._PATH_LAYERS if x[0] != "src/ui2/"))
    assert any(f.startswith("src/ui2/") for f in unregistered(c3._layer_of_file))
    monkeypatch.undo()
    monkeypatch.setattr(c3, "_SCAN_FILES", ("app.py",))
    monkeypatch.setattr(c3, "_layer_of_file", lambda rel: c3.L6 if rel == "app.py" else None)
    assert "app_ui2.py" in unregistered(c3._layer_of_file)


def test_g1_c3_rules_bite_on_ui2(monkeypatch):
    """登記後 c3 五條規則對 UI2 真的生效：假造一筆 `src/ui2` → `src.data` 的 import 必被 R4 抓到。"""
    fake = c3.ImportRecord("src/ui2/shell/x.py", 1, "from src.data.macro import fetch_fred",
                           "src.data.macro", ("fetch_fred",), None)
    monkeypatch.setattr(c3, "_ALL_IMPORTS", c3._ALL_IMPORTS + [fake])
    assert ("src/ui2/shell/x.py", "src.data.macro") in c3._rule4_ui_calls_l1()
    up = c3.ImportRecord("src/services/ui2/x.py", 1, "from src.ui2 import shell",
                         "src.ui2.shell", ("shell",), None)
    monkeypatch.setattr(c3, "_ALL_IMPORTS", c3._ALL_IMPORTS + [up])
    assert ("src/services/ui2/x.py", "src.ui2.shell") in c3._rule5_upward()
    l0 = c3.ImportRecord("shared/ui2_contract/x.py", 1, "from src.services.ui2 import m",
                         "src.services.ui2.m", ("m",), None)
    monkeypatch.setattr(c3, "_ALL_IMPORTS", c3._ALL_IMPORTS + [l0])
    assert ("shared/ui2_contract/x.py", "src.services.ui2.m") in c3._rule3_l0_upward()


# ── production default 未動 ────────────────────────────────────────────
def test_production_app_does_not_reference_ui2():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "ui2" not in src.lower(), "app.py 不得引用 New UI2（Preview 期 production default 不動）"


def test_app_ui2_first_streamlit_call_is_set_page_config():
    tree = ast.parse(APP_UI2.read_text(encoding="utf-8"))
    first = next(n for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                 and isinstance(n.value.func, ast.Attribute)
                 and isinstance(n.value.func.value, ast.Name) and n.value.func.value.id == "st")
    assert first.value.func.attr == "set_page_config"


def test_app_ui2_only_imports_src_ui2():
    mods = [n.module for n in ast.walk(ast.parse(APP_UI2.read_text(encoding="utf-8")))
            if isinstance(n, ast.ImportFrom) and n.module]
    assert mods and all(m == "src.ui2" or m.startswith("src.ui2.") for m in mods), mods


# ── G10 floor（現場讀 requirements.txt；掃描範圍補上 app_ui2.py）──────────
class _UI2Floor(_FloorBase):
    @classmethod
    def _scan_targets(cls):
        return sorted(pathlib.Path("src/ui2").rglob("*.py")) + [pathlib.Path("app_ui2.py")]


def test_g10_ui2_uses_no_api_newer_than_declared_floor():
    f = _UI2Floor()
    floor = f._declared_floor()
    assert floor >= (1, 56), "floor 讀取異常"
    assert f._violations(floor) == []


def test_g10_floor_scan_covers_the_entrypoint_and_bites(tmp_path, monkeypatch):
    assert pathlib.Path("app_ui2.py") in _UI2Floor._scan_targets()
    bad = tmp_path / "bad.py"
    bad.write_text("import streamlit as st\nst.dataframe(x, width='stretch')\nst.pills('a', [1])\n", encoding="utf-8")
    monkeypatch.setattr(_UI2Floor, "_scan_targets", classmethod(lambda cls: [bad]))
    assert _UI2Floor()._violations(_UI2Floor._ver("1.36.0")), "floor 守衛對 app_ui2 範圍沒有牙"


# ── G10 boot smoke（AppTest：in-process＋乾淨行程）─────────────────────────
@pytest.fixture(scope="module")
def at():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(APP_UI2), default_timeout=60).run(timeout=60)


def _blob(at_) -> str:
    return "\n".join(m.value for m in at_.markdown)


def test_boot_has_no_exception_and_preview_banner(at):
    assert not at.exception
    assert PREVIEW_BANNER_TEXT in _blob(at)


def test_nav_has_exactly_the_four_pages(at):
    nav = at.radio(key="ui2_page")
    assert list(nav.options) == [PAGE4_LABELS[p] for p in PAGE_IDS]
    assert list(nav.options) == ["📊 市場", "🎯 標的", "💼 持股", "👤 我的"]


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_every_page_switches_and_renders_in_every_scenario(at, scenario):
    at.selectbox(key="ui2_scenario").set_value(scenario).run(timeout=60)
    for page in PAGE_IDS:
        at.radio(key="ui2_page").set_value(page).run(timeout=60)
        assert not at.exception, f"{page}/{scenario}: {at.exception}"
        blob = _blob(at)
        assert PREVIEW_BANNER_TEXT in blob, f"{page}/{scenario}: 缺 Preview fake 標示"
        assert PAGE4_LABELS[page] in blob, f"{page}/{scenario}: 缺頁標題"
        assert "是否需要行動" in blob and "ui2-cta" in blob      # DEC-129：不強制可見題號「②」
    at.radio(key="ui2_page").set_value(PAGE_IDS[0]).run(timeout=60)


def test_cold_boot_in_fresh_process_has_no_exception():
    code = textwrap.dedent(f"""
        from streamlit.testing.v1 import AppTest
        a = AppTest.from_file({str(APP_UI2)!r}, default_timeout=100).run(timeout=100)
        exc = [str(e.value)[:300] for e in a.exception]
        if exc:
            print("EXC:", exc); raise SystemExit(3)
        print("UI2_COLD_BOOT_OK")
    """)
    r = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(ROOT)!r})\n" + code],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0 and "UI2_COLD_BOOT_OK" in r.stdout, r.stdout[-1500:] + r.stderr[-1500:]
