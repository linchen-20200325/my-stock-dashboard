"""DEC-102(2)（客戶 2026-10-28，XV-OLDUI-FX-REASON＝B）：舊 UI「💼 我的持股戰情室」外幣原因句。

DEC-019 凍結的客戶核准**最小例外**：只改 `etf_tab_dividend_station` 卡①「算不出來」與 80/20「算不出來」
兩句在**有外幣／幣別未確認持有列**時的原因 —— 修前講成「持股沒有張數／均價…」（錯誤指引，§1），
修後改用新 UI 同一 L0 客戶句 `FX_PARTIAL_TEXT` ＋ `fx_excluded_text` 未納入清單（不新寫文案）。
外幣不存在時舊 UI 輸出必須與修前逐字相同（parity，見 `TestNoFxParity`）。

列一律走真的 L3 `build_station_rows()`（離線注入 metrics），畫面以假的 `st` 攔下（手法同批 H2）。
"""
from __future__ import annotations

import pandas as pd

from shared import asset_currency_gate as FXG
from shared import dividend_station_thresholds as T
from src.services import dividend_station_service as svc
from tests.test_v2_batch_h2_0928 import (
    _ALLOC_NONE,
    _TOTALS_NONE,
    _alloc_out,
    _captions,
    _card1_note,
)

_E, _S = T.KIND_ETF, T.KIND_STOCK


def _weekly(n: int = 60) -> pd.Series:
    return pd.Series([100.0] * n, index=pd.date_range("2024-01-07", periods=n, freq="W-SUN"))


def _rows(*spec):
    """spec：`(代號, 種類, held, 張數, 均價, 現價)` → 真的 L3 列。"""
    _h, _m = [], {}
    for _tk, _kind, _held, _lots, _avg, _cur in spec:
        _h.append({"ticker": _tk, "name": _tk, "asset_kind": _kind, "held": _held,
                   "asset_class": T.ASSET_CORE if _kind == _E else T.ASSET_SATELLITE,
                   "lots": _lots, "avg_price": _avg})
        _m[_tk] = _cur

    def _metrics(tk, ak):
        if ak == _S:
            return {"mj_grade": "A", "mj_score_pct": 88, "mj_headline": "體質佳",
                    "mj_fail_items": [], "kd_state": {"k": 70.0, "d": 65.0, "label": "無"},
                    "current_price": _m[tk]}
        return {"weekly_close": _weekly(), "current_price": _m[tk]}

    return svc.build_station_rows(_h, vix=17.3, metrics_fn=_metrics)


_TW = ("0050.TW", _E, True, 10.0, 140.0, 150.0)
_VOO = ("VOO", _S, True, 3.0, 400.0, 450.0)
_ODD = ("50", _S, True, 3.0, 40.0, 45.0)        # 幣別未確認（不是明確外幣，也不能確定 TWD）


def _wrong_reason(text: str) -> bool:
    return "沒有張數" in text or "未帶張數" in text


class TestFxPresent:
    def test_card1_foreign(self, monkeypatch):
        rows = _rows(_TW, _VOO)
        assert svc.compute_portfolio_totals(rows) is None            # 前提：L3 因外幣不算總額
        note = _card1_note(monkeypatch, rows)
        assert note == f"{FXG.FX_PARTIAL_TEXT}　未納入：VOO｜原因：{FXG.FX_EXCLUDED_REASON}", note
        assert not _wrong_reason(note)

    def test_card1_unconfirmed_and_foreign(self, monkeypatch):
        rows = _rows(_TW, _VOO, _ODD)
        note = _card1_note(monkeypatch, rows)
        assert note == (f"{FXG.FX_PARTIAL_TEXT}　未納入：VOO｜原因：{FXG.FX_EXCLUDED_REASON}"
                        f"；50｜原因：{FXG.FX_UNCONFIRMED_REASON}"), note

    def test_card1_only_unconfirmed(self, monkeypatch):
        note = _card1_note(monkeypatch, _rows(_TW, _ODD))
        assert note == f"{FXG.FX_PARTIAL_TEXT}　未納入：50｜原因：{FXG.FX_UNCONFIRMED_REASON}"

    def test_alloc_foreign(self, monkeypatch):
        rows = _rows(_TW, _VOO)
        assert svc.compute_allocation_split(rows) is None
        caps = _captions(_alloc_out(monkeypatch, rows))
        assert caps[0] == (f"📊 80/20 配置偏離：{FXG.FX_PARTIAL_TEXT}"
                           f"　未納入：VOO｜原因：{FXG.FX_EXCLUDED_REASON}"), caps
        assert not any(_wrong_reason(c) for c in caps)

    def test_alloc_unconfirmed(self, monkeypatch):
        caps = _captions(_alloc_out(monkeypatch, _rows(_TW, _ODD)))
        assert caps[0].endswith(f"未納入：50｜原因：{FXG.FX_UNCONFIRMED_REASON}"), caps


class TestNoFxParity:
    """外幣不存在 → 與修前逐字相同（`_TOTALS_NONE`／`_ALLOC_NONE` 為批 H2 釘住的修前原句）。"""

    def test_card1_missing_lots_identical(self, monkeypatch):
        rows = _rows(("0050.TW", _E, True, None, None, 150.0),
                     ("2330", _S, True, None, None, 600.0))
        assert _card1_note(monkeypatch, rows) == _TOTALS_NONE

    def test_alloc_missing_lots_identical(self, monkeypatch):
        rows = _rows(("0050.TW", _E, True, None, None, 150.0))
        assert _captions(_alloc_out(monkeypatch, rows))[0] == _ALLOC_NONE

    def test_card1_complete_has_no_note(self, monkeypatch):
        rows = _rows(_TW, ("2330", _S, True, 2.0, 500.0, 600.0))
        assert svc.compute_portfolio_totals(rows) is not None
        assert _card1_note(monkeypatch, rows) is None

    def test_watchlist_foreign_does_not_trigger(self, monkeypatch):
        # 觀察清單（未持有）外幣不進 `fx_excluded_codes`（L3 同一判定）→ 原句逐字不變。
        rows = _rows(("0050.TW", _E, True, None, None, 150.0), ("VOO", _S, False, None, None, 450.0))
        assert _card1_note(monkeypatch, rows) == _TOTALS_NONE
