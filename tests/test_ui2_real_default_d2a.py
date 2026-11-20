"""D2-A（客戶 #1199 comment 7052908287，極窄授權）：獨立 `app_ui2.py` Preview 的一般入口預設以 Real-data Preview 呈現。

只改 `app_ui2.py`（run() 之前、session 尚無 `ui2_feed` 才播種為 Real）；FAKE 開發模式保留於 `?ui2_dev=1`。
本檔釘：①預設 Real ②開發面可切 FAKE 且持久 ③預填值不被覆蓋 ④Real 整體失敗只降級、不自動切 FAKE
⑤Real 缺值誠實 ⬜ ⑥session 寫入與 import 邊界不放寬。以下結論為作者自跑，未經第二組驗證。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import shared.ui2_contract.text as T
from shared.ui2_contract.pages import FEED_FAKE, FEED_REAL, SCENARIO_REAL
from tests.test_ui2_real_feed import (  # noqa: F401  (session_write_log 為 fixture，須在本模組命名空間)
    ALLOWED_UI2_WRITES, _blob, _boom_shell, _feed, _twii_view, session_write_log,
)

ROOT = Path(__file__).resolve().parents[1]
APP_UI2 = ROOT / "app_ui2.py"


def _run(*, dev: bool = False, preset: str | None = None):
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    if dev:
        a.query_params["ui2_dev"] = "1"
    if preset is not None:
        a.session_state["ui2_feed"] = preset
    return a.run(timeout=60)


def test_seed_constant_equals_contract_constants():
    from src.ui2.shell import app as shell
    assert shell.FEED_REAL == FEED_REAL == "real" and shell.KEY_FEED == "ui2_feed" and FEED_FAKE == "fake"


# ① 一般入口預設 Real
def test_default_entry_is_real_data_preview(monkeypatch):
    _feed(monkeypatch)
    at = _run()
    blob = _blob(at)
    assert not at.exception and at.session_state["ui2_feed"] == "real"
    assert T.REAL_PREVIEW_BANNER_TEXT in blob and T.PREVIEW_BANNER_TEXT not in blob and "FAKE" not in blob
    assert f'data-ui2-scenario="{SCENARIO_REAL}"' in blob
    assert len(at.selectbox) == 0                                  # 一般入口仍無任何開發面控制
    assert "23,456" in blob                                        # 注入的 Real 台股卡存在


# ② 開發面：feed 初值 real，可切 FAKE，切換後 rerun 持久，FAKE 場景內容正確
def test_dev_surface_starts_real_can_switch_to_fake_and_it_persists(monkeypatch):
    _feed(monkeypatch)
    at = _run(dev=True)
    assert not at.exception and at.selectbox(key="ui2_feed").value == "real"
    at.selectbox(key="ui2_feed").set_value("fake").run(timeout=60)
    assert at.session_state["ui2_feed"] == "fake"
    for _ in range(2):                                             # 後續 rerun（換頁／換場景）不被播種蓋回 Real
        at.selectbox(key="ui2_scenario").set_value("loaded").run(timeout=60)
        assert not at.exception and at.session_state["ui2_feed"] == "fake"
    blob = _blob(at)
    assert T.PREVIEW_BANNER_TEXT in blob and T.REAL_PREVIEW_BANNER_TEXT not in blob
    assert 'data-ui2-scenario="loaded"' in blob and f'data-ui2-scenario="{SCENARIO_REAL}"' not in blob
    assert not at.selectbox(key="ui2_scenario").disabled


# ③ 使用者／開發面已選的值不被播種覆蓋
def test_preset_fake_is_not_overwritten_by_seeding():
    at = _run(preset="fake")
    blob = _blob(at)
    assert not at.exception and at.session_state["ui2_feed"] == "fake"
    assert T.PREVIEW_BANNER_TEXT in blob and T.REAL_PREVIEW_BANNER_TEXT not in blob


# ④ Real 讀取整體失敗：既有降級提示，不含 FAKE 場景字樣，ui2_feed 仍 real（絕不自動切 FAKE）
def test_real_read_failure_degrades_and_never_falls_back_to_fake(monkeypatch):
    _boom_shell(monkeypatch)
    at = _run()
    blob = _blob(at)
    assert not at.exception and at.session_state["ui2_feed"] == "real"
    assert blob.count(T.REAL_FEED_DEGRADED_TEXT) == 1
    assert T.REAL_PREVIEW_BANNER_TEXT in blob and f'data-ui2-scenario="{SCENARIO_REAL}"' in blob
    assert "FAKE" not in blob and T.PREVIEW_BANNER_TEXT not in blob and T.PREVIEW_BANNER_NOTE not in blob
    assert "secret-token" not in blob and "23,456" not in blob


# ⑤ Real 缺值：誠實 ⬜，無假數、不標成 FAKE
def test_real_missing_twii_is_honest_blank_not_fake_number(monkeypatch):
    _feed(monkeypatch, twii=_twii_view(ok=False, close=(), as_of=None, error="讀不到"))
    at = _run()
    blob = _blob(at)
    assert not at.exception and at.session_state["ui2_feed"] == "real"
    assert "⬜" in blob and "23,456" not in blob and "<polyline" not in blob
    assert T.REAL_PREVIEW_BANNER_TEXT in blob and "FAKE" not in blob and T.REAL_FEED_DEGRADED_TEXT not in blob


# ⑥ 邊界不放寬
def test_default_real_session_writes_stay_within_allowed_ui2_keys(monkeypatch, session_write_log):
    _feed(monkeypatch)
    at = _run(dev=True)
    assert ("__setitem__", "ui2_feed") in session_write_log          # 播種確實發生且被記錄
    assert {k for _, k in session_write_log} <= ALLOWED_UI2_WRITES, session_write_log
    assert not at.exception


def test_app_ui2_seeds_before_run_and_imports_nothing_private():
    src = APP_UI2.read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert all(m == "src.ui2" or m.startswith("src.ui2.") or m == "src.services.connection_diag_service" for m in mods), mods
    assert not any(w in src for w in ("portfolio", "holdings", "OneBrain", "onebrain", "gsheet"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "run"]
    seeds = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "st.session_state['ui2_feed']"]
    assert len(calls) == 1 and len(seeds) == 1 and seeds[0].lineno < calls[0].lineno
    guard = [n for n in ast.walk(tree) if isinstance(n, ast.If) and "ui2_feed" in ast.unparse(n.test)]
    assert guard and "not in" in ast.unparse(guard[0].test)           # 只在尚無 ui2_feed 才播種
