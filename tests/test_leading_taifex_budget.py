"""Regression: 先行指標明細表空白 + 誤導文案（台股籌碼「三大法人 Table」不見）。

User 2026-06-28 回報：FinMind 額度正常（36/600）卻看不到「先行指標明細表」，畫面卻
顯示「4 個 FinMind API 全回空 / 額度用罄」。

根因：`build_leading_fast` §6.5「TAIFEX 補強段」（前五大/前十大/精確韭菜）為逐日序列
爬，最多 14 天 × 每天十幾秒 timeout，整段可達 ~100s，超過外層併發池對 li job 的
80s/100s 預算 → 整張表（連已抓到的 FinMind 三大法人/期貨/PCR/融資）一起被砍成空。
而 `leading_table_empty_state_html` 的 token-present 文案逕指 FinMind 額度，誤導（§1）。

修法：
  1. §6.5 TAIFEX 迴圈加整段時間預算 `_TAIFEX_ENRICH_BUDGET_S`，逾時 break、用已收部分組表。
  2. 文案改以「補強來源逾時」為首因，額度/token 退為次因，不再硬指 FinMind 全空。

本測試守衛這兩點，避免回歸。純靜態 AST + 純函式呼叫，零網路。
"""
from __future__ import annotations

import ast

from shared.macro_buckets import leading_table_empty_state_html

# ── 1. TAIFEX 補強時間預算守衛 ────────────────────────────────────
LI_SRC = open("src/data/macro/leading_indicators.py", encoding="utf-8").read()  # F-6.2 後 path
LI_TREE = ast.parse(LI_SRC)

# li job 在 tab_macro 併發池的 timeout（build_leading_fast 內部 join）；預算須 ≪ 此值，
# 確保 build_leading_fast 在被砍前先回傳。對齊 tab_macro.py:1228 'li': 80。
_LI_JOB_TIMEOUT_S = 80


def _module_const(name):
    for node in LI_TREE.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    v = node.value
                    if isinstance(v, ast.Constant) and isinstance(v.value, (int, float)):
                        return v.value
    return None


def _build_leading_fast_fn() -> ast.FunctionDef:
    for node in ast.walk(LI_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == "build_leading_fast":
            return node
    raise AssertionError("找不到 build_leading_fast")


def test_taifex_budget_constant_exists_and_safe():
    budget = _module_const("_TAIFEX_ENRICH_BUDGET_S")
    assert budget is not None, (
        "_TAIFEX_ENRICH_BUDGET_S 應為 module-level 數值常數（SSOT，非 inline magic）"
    )
    assert 0 < budget < _LI_JOB_TIMEOUT_S, (
        f"TAIFEX 補強預算 {budget}s 必須 < li job 額度 {_LI_JOB_TIMEOUT_S}s，"
        f"否則 build_leading_fast 仍會被併發池砍掉 → 表格照樣空。"
    )
    # 須留足裕度（FinMind 主抓 + probe + PCR 批次 + 組表/回傳），不可貼著 80。
    assert budget <= _LI_JOB_TIMEOUT_S - 30, (
        f"預算 {budget}s 太接近 job 額度 {_LI_JOB_TIMEOUT_S}s，組表/回傳時間不足"
    )


def test_taifex_loop_has_budget_break():
    fn = _build_leading_fast_fn()
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert "_TAIFEX_ENRICH_BUDGET_S" in names, "build_leading_fast 未引用 TAIFEX 預算常數"
    # 以 time.monotonic() 量測（避免系統時鐘跳動影響 deadline）
    assert any(isinstance(n, ast.Attribute) and n.attr == "monotonic" for n in ast.walk(fn)), (
        "預算守衛應以 time.monotonic() 量測"
    )
    # for 迴圈內須有 break（逾預算截斷、用已收部分組表）
    for loop in ast.walk(fn):
        if isinstance(loop, ast.For) and any(isinstance(b, ast.Break) for b in ast.walk(loop)):
            break
    else:
        raise AssertionError("build_leading_fast 的 for 迴圈缺 break（逾預算截斷）")


# ── 2. 誤導文案守衛 ─────────────────────────────────────────────
def test_token_present_message_blames_timeout_not_finmind_quota():
    """有 token 卻空 → 文案以『補強逾時』為首因，不再硬指『4 個 FinMind API 全回空』。"""
    html = leading_table_empty_state_html(attempted=True, token_present=True)
    assert "4 個 FinMind API 全回空" not in html, (
        "不可再逕指 FinMind 全空（實測最常見根因是 TAIFEX 補強逾時，FinMind 主資料其實有抓到）"
    )
    assert "補強" in html and ("逾時" in html or "TAIFEX" in html), (
        "token-present 文案應點出 TAIFEX 補強逾時被截斷這個真正首因"
    )


def test_no_token_message_still_points_to_token():
    """無 token 支線維持正確（4 源全需 token → 缺 token 必空）。"""
    html = leading_table_empty_state_html(attempted=True, token_present=False)
    assert "FINMIND_TOKEN" in html


def test_not_attempted_message_is_cold_start():
    """冷啟動未點更新 → 提示去點按鈕，不報錯。"""
    html = leading_table_empty_state_html(attempted=False, token_present=True)
    assert "尚未載入" in html
