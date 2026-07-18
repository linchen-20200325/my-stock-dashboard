"""v19.134 效能/省 API:AI 財報體檢改按鈕 opt-in — 防回退成「一進個股就自動打 Gemini」。

背景:`tab_stock.py` 的「🔬 AI 財報體檢（策略2）」原本一進到某檔股票、expander 首次 render
就自動呼叫 `analyze_financial_health`(Gemini)。有 session 快取(每檔一次)但無按鈕 gate →
首屏慢 + 每檔耗 API 額度。改「點按鈕才生成」(user 2026-07-18 核准)。

本檔以 source-inspection 當 golden(render 函式巨大,不 mock-render),防回退。
"""
from __future__ import annotations

from pathlib import Path

_SRC = (Path(__file__).parents[1] / 'src/ui/tabs/tab_stock.py').read_text(encoding='utf-8')


def test_ai_financial_health_has_generate_button():
    """AI 財報體檢應有「生成」按鈕 + session flag 記憶已請求(opt-in)。"""
    assert '生成 AI 財報體檢' in _SRC, 'AI 財報體檢應有「🔬 生成 AI 財報體檢」按鈕(opt-in)'
    assert '_fh_req_' in _SRC, '應以 session flag(_fh_req_*)記憶已請求生成'


def test_ai_call_gated_behind_button():
    """analyze_financial_health(Gemini)呼叫必須在生成按鈕之後(opt-in gate)。"""
    _idx_btn = _SRC.find('生成 AI 財報體檢')
    _idx_ai = _SRC.find('analyze_financial_health(api_key')
    assert _idx_btn != -1, '缺生成按鈕'
    assert _idx_ai != -1, '缺 analyze_financial_health 呼叫'
    assert _idx_btn < _idx_ai, (
        '生成按鈕須在 analyze_financial_health(api_key ...) 呼叫之前 — '
        '否則等於自動觸發 Gemini(回退 bug)')
