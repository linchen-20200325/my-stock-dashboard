"""New UI2 真瀏覽器 lane 共用工具（DEC-137；測試規格 §2.4）。

`require_browser()` 是 New UI2 行為測試**唯一**允許 skip 的地方：
- 環境變數 `UI2_BROWSER_LANE=required`（CI `ui2-browser` job）→ 缺 playwright／缺 Chromium 一律 `pytest.fail`（skip ≠ PASS）。
- 未設（本機）→ skip 並印警示（不是通過）。
另：`UI2_EXPECT_STREAMLIT`＝matrix 期望的 Streamlit 版本（lane required 時必須設定；測試斷言實際版本相等）。
"""
from __future__ import annotations

import os
import warnings

import pytest

LANE_ENV = "UI2_BROWSER_LANE"
EXPECT_ENV = "UI2_EXPECT_STREAMLIT"


def lane_required() -> bool:
    return os.environ.get(LANE_ENV) == "required"


def require_browser(problem: str | None = None):
    """回傳 `sync_playwright`；缺 playwright（或呼叫端回報 `problem`，例如 Chromium 啟動失敗）→
    `UI2_BROWSER_LANE=required` 時 `pytest.fail`、本機 skip（印警示）。本函式是唯一允許 skip 的地方。"""
    if problem is None:
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError as exc:
            problem = f"未安裝 playwright：{exc}"
    if lane_required():
        pytest.fail(f"[{LANE_ENV}=required] {problem}（skip ≠ PASS：browser lane 不得缺瀏覽器）")
    warnings.warn(f"⚠️ New UI2 browser 測試被略過（不是通過）：{problem}")
    pytest.skip(f"本機未設 {LANE_ENV}=required：{problem}")


def launch_or_fail(p):
    """啟動 Chromium（沿用 measure_viewport 的 fallback）；失敗 → required 時 fail、本機 skip。"""
    from tests.ui2_viewport.measure_viewport import launch_chromium
    try:
        return launch_chromium(p)
    except Exception as exc:
        require_browser(f"無可用 Chromium：{str(exc)[:160]}")
