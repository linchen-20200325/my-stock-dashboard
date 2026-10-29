"""DEC-102(3)（客戶 2026-10-28，XV-FX-ROW-ACTION＝同意）：外幣個股列層建議動作。

外幣／幣別未確認的持有個股列，汰換燈判得出 🟢 → **保留**「🟢 續抱…」原句，同列加註
「停利未判：外幣」（明確外幣）或「停利未判：幣別未確認」（其餘），⛔ 不換成「⬜ 資料不足／無法判定」。
台股列與修前（`1e603094`，經 `tests/test_dec102_revert_chain.dec102_revert_for` 還原）逐字相同。
"""
from __future__ import annotations

import pytest

import src.services.dividend_station_service as S
from shared import asset_currency_gate as FXG
from shared import price_asof_label as PAL
from shared import station_specs as SS
from tests.test_dec102_revert_chain import base_module


def _mf(tk, kind, *, grade="A", price=500.0):
    return {"mj_grade": grade, "kd_state": None, "current_price": price}


def _rows(holdings, mf=_mf, mod=S):
    return mod.build_station_rows(holdings, vix=15.0, metrics_fn=mf)


def _h(tk, held=True):
    return {"ticker": tk, "lots": 1, "avg_price": 400, "asset_kind": "stock", "held": held}


@pytest.fixture(scope="module")
def BS():
    return base_module("src/services/dividend_station_service.py", "_dec102_base_svc_r")


@pytest.mark.parametrize("tk,note", [("VOO", FXG.FX_TP_UNJUDGED_FOREIGN), ("BRK.B", FXG.FX_TP_UNJUDGED_FOREIGN),
                                     ("50", FXG.FX_TP_UNJUDGED_UNCONFIRMED),
                                     ("^TWII", FXG.FX_TP_UNJUDGED_UNCONFIRMED)])
def test_fx_hold_kept_and_annotated(BS, tk, note):
    r, = _rows([_h(tk)])
    br, = _rows([_h(tk)], mod=BS)
    assert br["建議動作"].startswith("🟢 續抱")               # 前提：修前就是續抱
    assert r["建議動作"] == f"{br['建議動作']}　{note}"
    assert r["健檢"] == "🟢" and SS.KEY_INSUFFICIENT not in r
    assert r["建議動作"] != SS.INSUFFICIENT_ACTION_TEXT


def test_reason_split_matches_exclusion_reason():
    assert FXG.fx_exclusion_reason("VOO") == FXG.FX_EXCLUDED_REASON
    assert FXG.fx_take_profit_note("VOO") == "停利未判：外幣"
    assert FXG.fx_take_profit_note("50") == "停利未判：幣別未確認"


@pytest.mark.parametrize("hs", [
    [_h("2330"), _h("0050"), _h("00878")],
    [_h("2330.TW"), _h("6488.TWO")],
    [_h("VOO", held=False), _h("2330")],      # 觀察清單外幣：不進外幣排除 → 逐字不變
])
def test_tw_and_watchlist_rows_identical_to_base(BS, hs):
    rows, brows = _rows(hs), _rows(hs, mod=BS)
    assert [r["建議動作"] for r in rows] == [r["建議動作"] for r in brows]
    # 📌 XV-ASOF 整合（2026-10-28，有意識的放寬，⛔ 不是漏改）：XV-ASOF 批（同基底 `1e603094`）在每一列加性帶出
    #   價格時間＋來源的非顯示鍵（`PAL.PRICE_ASOF_KEYS`）；整合後 `base_module` 兩批一起還原 ⇒ 這幾鍵排除後
    #   才是本批要守的「逐鍵不變」。其餘鍵與值照舊逐一比對。
    _asof = set(PAL.PRICE_ASOF_KEYS)
    assert [sorted(set(r) - _asof) for r in rows] == [sorted(br) for br in brows]   # 逐鍵不變（無新鍵）
    for r, br in zip(rows, brows):
        for k in r:
            if k in _asof:
                continue
            if k != S.KEY_WEEKLY_SERIES:    # 週線原料含 Series（另由既有測試守）
                assert r[k] == br[k], (r["代號"], k)


def test_fx_no_price_still_insufficient(BS):
    mf = lambda tk, kind: _mf(tk, kind, price=None)   # noqa: E731
    r, = _rows([_h("VOO")], mf)
    br, = _rows([_h("VOO")], mf, mod=BS)
    assert r["建議動作"] == br["建議動作"] == SS.INSUFFICIENT_ACTION_TEXT


@pytest.mark.parametrize("grade", ["C", "Z"])     # 🔴／契約漂移 ⚪：非續抱結論，不加註、逐字不變
def test_fx_non_hold_rows_unchanged(BS, grade):
    mf = lambda tk, kind: _mf(tk, kind, grade=grade)   # noqa: E731
    r, = _rows([_h("VOO")], mf)
    br, = _rows([_h("VOO")], mf, mod=BS)
    assert r["建議動作"] == br["建議動作"]
    assert "停利未判" not in r["建議動作"]
