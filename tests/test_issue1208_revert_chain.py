"""tests/test_issue1208_revert_chain.py — Issue #1208（客戶 2026-11-17 取消 ETF 經理人換手策略）對
`shared/signal_thresholds.py` 的還原鏈新頭節。

═══ 為什麼需要 ═══════════════════════════════════════════════════════════
#1208 刪除 `ETF_MANAGER_TENURE_NEW_DAYS`（唯一 consumer＝已移除的「新經理人 <6 月再給時間」例外）。
`shared/signal_thresholds.py` 被舊鏈（DEC-074…）以「新寫法 → 舊寫法」錨點還原成各自的基底 sha256；
本批改動落在它們的比對範圍之內 ⇒ 在鏈頭**往前接一節**：`twii_ohlc_revert_for` 開頭先呼叫本節的
`i1208_revert_for`（比照 `b2_revert_for` 開頭先呼叫 `twii_ohlc_revert_for` 的作法；⛔ 不動任何舊表與
舊基底 sha、不放寬任何斷言、不 skip）。有意識的接鏈，不是漏改。

基底 ＝ #1208 開工前的 `efa0e015`（origin/main）；`git show efa0e015:<檔> | sha256sum` 實算後寫死，測試不依賴 git。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

I1208_BASE_SHA = {'shared/signal_thresholds.py': 'b93355a5100d58a957c6558fcbf6d3c6633b6a13c6d6849399c7ef0cefc6c1e5'}

I1208_REVERT_PAIRS = {'shared/signal_thresholds.py': (('# ── #5(已移除)ETF 基金經理新任門檻 ETF_MANAGER_TENURE_NEW_DAYS ──\n# Issue #1208(2026-11-17 客戶取消 ETF 經理人換手策略):唯一 consumer\n# asset_lag.classify_lag_verdict 的「新經理人 <6 月再給時間」例外已移除,本常數一併刪除。\n',
                                                         '# ── #5 ETF 基金經理新任門檻(etf_calc 經理人燈號)──\nETF_MANAGER_TENURE_NEW_DAYS: int = 180\n"""ETF 基金經理「新任」判定門檻(單位:天,約 6 個月)。\n任期 <180 天視為新經理人,表現待觀察 → UI 顯示「再給時間」建議。\n原 src/compute/etf/etf_calc.py:915 inline。"""\n'),)}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def i1208_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 #1208 之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    # #1208 PR2（MoneyDJ 全入口零請求止血，DEC-189）在本節之後又改了一批檔 ⇒ 最新的那一批先換回
    # （比照 twii_ohlc_revert_for 開頭先呼叫本節；有意識的接鏈，不是漏改）。
    from tests.test_issue1208_pr2_revert_chain import i1208pr2_revert_for
    code = i1208pr2_revert_for(rel, code)
    pairs = I1208_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} #1208 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_i1208_revert_is_exact_base_source():
    assert set(I1208_REVERT_PAIRS) == set(I1208_BASE_SHA)
    for rel in sorted(I1208_REVERT_PAIRS):
        code = i1208_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == I1208_BASE_SHA[rel], rel


def test_i1208_revert_is_idempotent():
    for rel in sorted(I1208_REVERT_PAIRS):
        once = i1208_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert i1208_revert_for(rel, once) == once, rel


def test_i1208_link_is_reached_from_twii_ohlc_head():
    """接鏈本身：`twii_ohlc_revert_for` 必須先套本節（否則舊鏈對 signal_thresholds 的基底 sha 會紅）。"""
    from tests.test_twii_ohlc_revert_chain import twii_ohlc_revert_for
    rel = "shared/signal_thresholds.py"
    code = (REPO / rel).read_text(encoding="utf-8")
    assert twii_ohlc_revert_for(rel, code) == i1208_revert_for(rel, code)
