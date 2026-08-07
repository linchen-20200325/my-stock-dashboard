"""v19.134 效能/省 API:AI 財報體檢改按鈕 opt-in — 防回退成「一進個股就自動打 Gemini」。

背景:`tab_stock.py` 的「🔬 AI 財報體檢（策略2）」原本一進到某檔股票、expander 首次 render
就自動呼叫 `analyze_financial_health`(Gemini)。有 session 快取(每檔一次)但無按鈕 gate →
首屏慢 + 每檔耗 API 額度。改「點按鈕才生成」(user 2026-07-18 核准)。

本檔以 source-inspection 當 golden(render 函式巨大,不 mock-render),防回退。
"""
from __future__ import annotations

import ast
from pathlib import Path

_SRC = (Path(__file__).parents[1] / 'src/ui/tabs/tab_stock.py').read_text(encoding='utf-8')


def test_ai_financial_health_has_generate_button():
    """AI 財報體檢應有「生成」按鈕 + session flag 記憶已請求(opt-in)。"""
    assert '生成 AI 財報體檢' in _SRC, 'AI 財報體檢應有「🔬 生成 AI 財報體檢」按鈕(opt-in)'
    assert '_fh_req_' in _SRC, '應以 session flag(_fh_req_*)記憶已請求生成'


def _call_linenos(name: str) -> list[int]:
    """所有「呼叫 `name`」的**真實 Call 節點**行號（AST，註解/docstring 天然不算）。"""
    _out: list[int] = []
    for _n in ast.walk(ast.parse(_SRC)):
        if not isinstance(_n, ast.Call):
            continue
        _f = _n.func
        _nm = (_f.id if isinstance(_f, ast.Name)
               else _f.attr if isinstance(_f, ast.Attribute) else None)
        if _nm == name:
            _out.append(_n.lineno)
    return sorted(_out)


def _button_linenos(label_substr: str) -> list[int]:
    """所有 `st.button(...)`（或任何 `.button(...)`）其字面參數含 `label_substr` 的行號。"""
    _out: list[int] = []
    for _n in ast.walk(ast.parse(_SRC)):
        if not (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                and _n.func.attr == 'button'):
            continue
        _lits = [c.value for c in ast.walk(_n)
                 if isinstance(c, ast.Constant) and isinstance(c.value, str)]
        if any(label_substr in s for s in _lits):
            _out.append(_n.lineno)
    return sorted(_out)


def test_ai_call_gated_behind_button():
    """analyze_financial_health(Gemini)呼叫必須在生成按鈕之後(opt-in gate)。

    ⚠️ v19.187 改用 AST（本 session 第 9 次同類假紅燈的處置）
    ────────────────────────────────────────────────────────
    原本兩行是 `_SRC.find('analyze_financial_health(api_key')` 掃**字面**。
    F2 把 `api_key` 從 `from app import`（L5→L6 上行）改成 L3 `get_gemini_api_key()`
    時，在檔頭寫了一段解釋註解，內容含 ``analyze_financial_health(api_key, ...)``
    —— 於是 `find()` 命中那則**註解**（位置遠早於按鈕）→ 判定「AI 在按鈕前被呼叫」。
    實際呼叫點沒動過，gate 也完好。

    這是本 session 反覆出現的形狀：**守衛照抄實作字面，於是任何提到該實作的
    文字都會觸發它，而真正改壞邏輯時它未必抓得到**。改成比對真實 `ast.Call`
    節點的行號：註解與 docstring 天然不在 AST 裡，且函式改名/換行都不影響判定。
    """
    _btn = _button_linenos('生成 AI 財報體檢')
    _ai = _call_linenos('analyze_financial_health')
    assert _btn, '缺「生成 AI 財報體檢」按鈕'
    assert _ai, '缺 analyze_financial_health 呼叫'
    assert min(_btn) < min(_ai), (
        f'生成按鈕（行 {min(_btn)}）須在 analyze_financial_health 呼叫'
        f'（行 {min(_ai)}）之前 — 否則等於自動觸發 Gemini(回退 bug)\n'
        f'  按鈕行號={_btn}\n  呼叫行號={_ai}')
