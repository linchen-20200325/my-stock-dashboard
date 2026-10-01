"""批 P1（2026-10-01）持股戰情室文字與測試缺口的守衛：H1-f11／H1-f12／H1-f14。

  · H1-f11：v2 `page_hold._split_facts()`「只納入有市值的持有列」那一列 —— 修前寫
    「缺張數／均價的持有列不進分子也不進分母」，但 L3 `compute_allocation_split()` 只看
    「市值 > 0」（市值＝張數 × 現價，不看均價）⇒ 只缺均價的列照樣納入。修法：刪去「／均價」
    （只刪不改，K1）。v1 同型已由 #734（H1-f5）修。
  · H1-f12：`tests/test_v2_silent_fail_b10_sheet.py` 模組 docstring 引的金額列畫面字樣
    「缺張數或均價，沒有納入」改成現行字樣「缺張數／均價／現價，沒有納入」（逐字取自
    `page_hold._totals_facts()`；同 H1-f7 對 `load_holdings()` docstring 的修法）。
    同檔其餘「缺張數或均價」是情境描述、非畫面引文，未動。
  · H1-f14（測試缺口，產品碼未動）：v1 80/20 部分納入註記「另有 {held_n − valued_n}/{held_n} 檔」
    的既有測試資料對稱（2 持有、1 納入 ⇒ 「持有−納入」與「納入」都是 1），算式沒被釘住
    ⇒ 補一組不對稱資料（3 持有、1 納入 ⇒ 「2/3 檔」）。

列一律走**真的** L3 `build_station_rows()`（`metrics_fn` 注入、全離線、不打網路），
夾具沿用批 H2 `tests/test_v2_batch_h2_0928.py`（⛔ 不另捏 row 的形狀）。
每一條的有效性已做突變驗證（把修正改回修前 → 本檔對應測試轉紅）。
"""
from __future__ import annotations

import ast
import pathlib
import re

from shared import dividend_station_thresholds as T
from src.services import dividend_station_service as svc
from src.ui.views import page_hold as P
from src.ui.etf import etf_tab_dividend_station as V1  # noqa: F401（`_alloc_out` 會 patch 它）
from tests.test_v2_batch_h2_0928 import _ALLOC_APPROX, _FULL, _alloc_out, _captions, _rows

_E, _S = T.KIND_ETF, T.KIND_STOCK

#: H1-f11 修後那一列的值。⚠️ 刻意寫死：被改了一個位元組就會紅。
_SPLIT_ONLY_VALUED = "缺張數的持有列**不進分子也不進分母** —— 硬算等於替你編一個比例"


def _split_station(rows) -> P.StationReadout:
    return P.StationReadout(requested=True, submitted=True, bound=True, holdings_n=len(rows),
                            rows=tuple(rows), split=svc.compute_allocation_split(rows))


# ══════════════════════════════════════════════════════════════════
# H1-f11：v2 80/20 中繼資料列 ⛔ 不再說「缺均價不進分子分母」
# ══════════════════════════════════════════════════════════════════
class TestH1f11SplitFacts:
    def test_fact_no_longer_claims_missing_avg_is_excluded(self):
        _facts = dict(P._split_facts(_split_station(_rows(_FULL))))
        assert _facts["只納入有市值的持有列"] == _SPLIT_ONLY_VALUED, _facts
        assert "均價" not in _facts["只納入有市值的持有列"]

    def test_the_fact_matches_l3_missing_avg_is_counted(self):
        """前提：只缺均價 ⇒ L3 照樣納入（修前那句話在這裡不成立）。"""
        rows = _rows(_FULL, ("2330", _S, True, 2.0, None, 600.0, False))
        _a = svc.compute_allocation_split(rows)
        assert (_a["held_n"], _a["valued_n"], _a["partial"]) == (2, 2, False)

    def test_the_fact_matches_l3_missing_lots_is_excluded(self):
        """前提：缺張數 ⇒ L3 不納入（修後那句話成立）。"""
        rows = _rows(_FULL, ("2330", _S, True, None, 500.0, 600.0, False))
        _a = svc.compute_allocation_split(rows)
        assert (_a["held_n"], _a["valued_n"], _a["partial"]) == (2, 1, True)

    def test_old_wording_is_gone_from_page_hold(self):
        import inspect
        assert "缺張數／均價的持有列" not in inspect.getsource(P)


# ══════════════════════════════════════════════════════════════════
# H1-f12：b10 測試檔 docstring 引的金額列字樣 = 現行字樣
# ══════════════════════════════════════════════════════════════════
_B10 = pathlib.Path(__file__).with_name("test_v2_silent_fail_b10_sheet.py")


class TestH1f12B10Docstring:
    def test_docstring_quotes_the_live_totals_wording(self):
        _doc = re.sub(r"\n\s*", "", ast.get_docstring(ast.parse(_B10.read_text("utf-8"))) or "")
        assert "缺張數或均價，沒有納入" not in _doc
        _quote = "檔持股缺張數／均價／現價，沒有納入"
        assert _quote in _doc, _doc
        # 引的是 `_totals_facts()` 現行那一句（去掉粗體記號後逐字相同）。
        _rows_ = _rows(_FULL, ("2330", _S, True, 2.0, 500.0, None, False))
        st_ = P.StationReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                               rows=tuple(_rows_),
                               totals=svc.compute_portfolio_totals(_rows_))
        _live = dict(P._totals_facts(st_))["⚠️ 上面兩個金額只涵蓋一部分"].replace("**", "")
        assert _quote in _live, _live


# ══════════════════════════════════════════════════════════════════
# H1-f14：v1 80/20 部分納入註記的檔數算式（不對稱資料釘住「持有−納入」）
# ══════════════════════════════════════════════════════════════════
class TestH1f14AllocationPartialCount:
    def test_count_is_held_minus_valued_over_held(self, monkeypatch):
        """修後不變守衛（產品碼未動；有效性靠突變驗證）：3 持有、1 納入 ⇒「2/3 檔」。"""
        rows = _rows(_FULL,
                     ("2330", _S, True, 2.0, 500.0, None, False),    # 缺現價 → 不納入
                     ("2317", _S, True, None, 100.0, 120.0, False))  # 缺張數 → 不納入
        _a = svc.compute_allocation_split(rows)
        # 前提：資料不對稱 —— 「持有−納入」(2) ≠「納入」(1)，兩種算法數字分得開。
        assert (_a["held_n"], _a["valued_n"], _a["partial"]) == (3, 1, True)
        caps = _captions(_alloc_out(monkeypatch, rows))
        assert caps == [_ALLOC_APPROX + "　⚠️ 另有 2/3 檔缺張數／均價／現價未納入計算。"], caps
