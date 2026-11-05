"""ETF 組合回測退役路徑防回歸（僅測 static contract；實際 UI 另由 CI 測試）。

背景：原回測頁與 writer 已刪除，舊 ETF AI 頁殘留 session reader 與
「有回測資料則展示 CAGR / Sharpe」的分支，會誤導使用者誤認功能仍可用。
移除 reader 不等於移除誠實揭露：prompt 仍應告知無組合回測功能，
不可要求使用者執行已不存在的流程，也不能憑單檔數據編造組合回測。
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src/ui/etf/etf_tab_ai.py"


def _source_and_tree() -> tuple[str, ast.Module]:
    source = SRC.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(SRC))


def test_retired_backtest_session_key_is_not_read_by_etf_ai():
    """避免在已無正式 writer 的情況下，從 session 重啟舊路徑。"""
    _, tree = _source_and_tree()
    # 檢查 executable AST 的 string constants，不把註解/歷史說明算成讀取。
    string_literals = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    assert "etf_backtest_data" not in string_literals


def test_generate_report_does_not_accept_retired_backtest_payload():
    """刪除與外部 payload 的連線，防止原條件分支無意復活。"""
    _, tree = _source_and_tree()
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "_generate_report")
    names = [n.arg for n in fn.args.args]
    assert "backtest_d" not in names
    assert not any(isinstance(n, ast.Name) and n.id == "backtest_d"
                   for n in ast.walk(fn))


def test_ai_prompt_preserves_explicit_retired_capability_disclosure():
    """刪掉 dead branch 不可同時刪除防 AI 幻覺的限制說明。"""
    source, _ = _source_and_tree()
    assert "本系統目前沒有 ETF 組合歷史回測功能" in source
    assert "請勿在報告中要求使用者去執行回測" in source
    assert "請勿把單檔數字當成組合數字" in source
