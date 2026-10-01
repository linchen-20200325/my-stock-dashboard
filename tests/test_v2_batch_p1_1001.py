"""批 P1（2026-10-01）持股戰情室文字與測試缺口的守衛：H1-f11／H1-f12／H1-f14。

  · H1-f11：v2 `page_hold._split_facts()`「只納入有市值的持有列」那一列 —— 修前寫
    「缺張數／均價的持有列不進分子也不進分母」，但 L3 `compute_allocation_split()` 只看
    「市值 > 0」（市值＝張數 × 現價，不看均價）⇒ 只缺均價的列照樣納入。修法：刪去「／均價」
    （只刪不改，K1）。v1 同型已由 #734（H1-f5）修。

列一律走**真的** L3 `build_station_rows()`（`metrics_fn` 注入、全離線、不打網路），
夾具沿用批 H2 `tests/test_v2_batch_h2_0928.py`（⛔ 不另捏 row 的形狀）。
每一條的有效性已做突變驗證（把修正改回修前 → 本檔對應測試轉紅）。
"""
from __future__ import annotations

from shared import dividend_station_thresholds as T
from src.services import dividend_station_service as svc
from src.ui.views import page_hold as P
from tests.test_v2_batch_h2_0928 import _FULL, _rows

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
