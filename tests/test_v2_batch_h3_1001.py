"""批 H3（2026-10-01）持股戰情室「算不出來」歸因修正的守衛：H1-f8／H1-f9／H1-f10。

  · H1-f8：v2 `page_hold._totals_facts()` —— 持有列**全部**整批抓取失敗時，L3
    `compute_portfolio_totals()` 把它們整列跳過 ⇒ 算不出來是因為抓不到、不是持股缺資料
    ⇒ 歸因子句「 —— 持股缺張數／均價／現價」整段不出（只刪不改）；失敗原因由卡上既有的
    「⚠️ 未納入任何判斷」那一列交代。v1 同型已由 #734（H1-f6）修。
  · H1-f9：v1 `etf_tab_dividend_station._render_allocation_take_profit()` 80/20 算不出來那一句 ——
    持有列全部整批抓取失敗時刪去歸因「你的持股未帶張數/均價（或無市值）→ 」與去哪補子句，
    改接同檔卡①既有的「⚠️ 另有 N 檔整批抓取失敗，未納入任何判斷。」；其餘情形只把半形
    「張數/均價」統一為全形「張數／均價」。

列一律走**真的** L3 `build_station_rows()`（`metrics_fn` 注入、全離線、不打網路），
夾具沿用批 H2 `tests/test_v2_batch_h2_0928.py`（⛔ 不另捏 row 的形狀）。
每一條的有效性已做突變驗證（把修正改回修前 → 本檔對應測試轉紅）。
"""
from __future__ import annotations

from shared import dividend_station_thresholds as T
from src.services import dividend_station_service as svc
from src.ui.views import page_hold as P
from tests.test_v2_batch_h2_0928 import _CLAUSE, _alloc_out, _captions, _rows

_E, _S = T.KIND_ETF, T.KIND_STOCK

#: 修前那一句（沒有任何持有列失敗時照舊）。⚠️ 刻意寫死：被改了一個位元組就會紅。
_TOTALS_NONE_V2 = ("**算不出來** —— 持股缺張數／均價／現價。"
                   "本站在這裡**不填 0**：0 元損益是一個結論，缺值不是")
#: 持有列全部整批抓取失敗時（批 H3 後）：只刪掉歸因子句。
_TOTALS_NONE_V2_FAILED = "**算不出來**。本站在這裡**不填 0**：0 元損益是一個結論，缺值不是"


def _station(rows) -> P.StationReadout:
    """照 `page_hold.load_station()` 的組法，由真的 L3 列組出 `StationReadout`。"""
    _digest = svc.build_station_digest(rows, 17.3)
    return P.StationReadout(
        requested=True, submitted=True, bound=True, holdings_n=len(rows),
        rows=tuple(rows), totals=svc.compute_portfolio_totals(rows),
        err_n=len(_digest.get("errors") or ()))


def _action_facts(rows) -> dict[str, str]:
    _card, _facts, _sig = P.build_action_card(_station(rows))
    return dict(_facts)


# ══════════════════════════════════════════════════════════════════
# H1-f8：v2 `_totals_facts()` —— 持有列全部整批抓取失敗 ⇒ 不歸因成缺資料
# ══════════════════════════════════════════════════════════════════
class TestH1f8V2TotalsNone:
    def test_all_held_failed_drops_the_missing_data_clause(self):
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, 150.0, True),
                     ("2330", _S, True, 2.0, 500.0, 600.0, True))
        assert all((r.get("_detail") or {}).get("error") for r in rows)   # 前提：兩列都失敗
        assert svc.compute_portfolio_totals(rows) is None
        facts = _action_facts(rows)
        assert facts["未實現損益／總市值"] == _TOTALS_NONE_V2_FAILED, facts
        assert "持股缺張數" not in facts["未實現損益／總市值"]
        # 失敗原因由既有那一列交代（⛔ 不新寫）。
        assert facts["⚠️ 未納入任何判斷"].startswith("另有 2 檔整批抓取失敗"), facts

    def test_held_all_failed_while_watchlist_ok(self):
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, 150.0, True),
                     ("0056.TW", _E, False, None, None, 35.0, False))
        facts = _action_facts(rows)
        assert facts["未實現損益／總市值"] == _TOTALS_NONE_V2_FAILED, facts

    def test_some_held_not_failed_keeps_the_sentence(self):
        """修後不變守衛：還有沒失敗的持有列（只缺現價）⇒ 修前那一句照留。"""
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, 150.0, True),
                     ("2330", _S, True, 2.0, 500.0, None, False))
        assert _action_facts(rows)["未實現損益／總市值"] == _TOTALS_NONE_V2

    def test_held_ok_but_watchlist_failed_keeps_the_sentence(self):
        """修後不變守衛：判的是**持有列本身**失敗與否 ⛔ 不是拿失敗檔數比持有檔數。"""
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, None, False),
                     ("0056.TW", _E, False, None, None, 35.0, True))
        assert _action_facts(rows)["未實現損益／總市值"] == _TOTALS_NONE_V2

    def test_all_missing_lots_avg_keeps_the_sentence(self):
        """修後不變守衛：真的缺張數／均價 ⇒ 修前那一句照留。"""
        rows = _rows(("0050.TW", _E, True, None, None, 150.0, False))
        assert _action_facts(rows)["未實現損益／總市值"] == _TOTALS_NONE_V2

    def test_no_held_rows_keeps_the_sentence(self):
        """修後不變守衛：沒有任何持有列 ⇒ 照修前（`all([])` 為真的陷阱）。"""
        rows = _rows(("0056.TW", _E, False, None, None, 35.0, True))
        assert _action_facts(rows)["未實現損益／總市值"] == _TOTALS_NONE_V2


# ══════════════════════════════════════════════════════════════════
# H1-f9：v1 80/20 算不出來 —— 持有列全部整批抓取失敗 ⇒ 不歸因成缺張數／均價；半形→全形
# ══════════════════════════════════════════════════════════════════
_ALLOC_NONE_V1 = ("📊 80/20 配置偏離：你的持股未帶張數／均價（或無市值）→ 無法計算實際佔比。"
                  + _CLAUSE + "。")


def _alloc_failed(n: int) -> str:
    return f"📊 80/20 配置偏離：無法計算實際佔比。　⚠️ 另有 {n} 檔整批抓取失敗，未納入任何判斷。"


class TestH1f9V1AllocationNone:
    def test_all_held_failed_says_fetch_failed(self, monkeypatch):
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, 150.0, True),
                     ("2330", _S, True, 2.0, 500.0, 600.0, True))
        assert svc.compute_allocation_split(rows) is None          # 前提：走「算不出來」
        caps = _captions(_alloc_out(monkeypatch, rows))
        assert caps == [_alloc_failed(2)], caps
        assert "張數" not in caps[0]

    def test_held_all_failed_while_watchlist_failed_counts_held_only(self, monkeypatch):
        """檔數只數持有列（80/20 只看持有列）—— 觀察清單那檔失敗 ⛔ 不算進來。"""
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, 150.0, True),
                     ("0056.TW", _E, False, None, None, 35.0, True))
        caps = _captions(_alloc_out(monkeypatch, rows))
        assert caps == [_alloc_failed(1)], caps

    def test_missing_lots_uses_full_width_slash(self, monkeypatch):
        rows = _rows(("0050.TW", _E, True, None, None, 150.0, False))
        caps = _captions(_alloc_out(monkeypatch, rows))
        assert caps == [_ALLOC_NONE_V1], caps
        assert "張數/均價" not in caps[0]

    def test_some_held_not_failed_keeps_the_sentence(self, monkeypatch):
        """還有沒失敗的持有列（只缺現價）⇒ 原句照留（只換全形）。"""
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, 150.0, True),
                     ("2330", _S, True, 2.0, 500.0, None, False))
        assert _captions(_alloc_out(monkeypatch, rows)) == [_ALLOC_NONE_V1]

    def test_no_held_rows_keeps_the_sentence(self, monkeypatch):
        """沒有任何持有列 ⇒ 原句照留（`all([])` 為真的陷阱）。"""
        rows = _rows(("0056.TW", _E, False, None, None, 35.0, True))
        assert _captions(_alloc_out(monkeypatch, rows)) == [_ALLOC_NONE_V1]
