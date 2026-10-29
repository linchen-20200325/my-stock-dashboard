"""DEC-102(1)（客戶 2026-10-28，XV-LINE-VIX-LINE＝同意）：LINE 推播 VIX 分級句的行動建議。

持股資料不足（本檔 `_data_short(digest)` ＝ L0 `holdings_data_short.digest_data_short` 同一謂詞）時，
VIX 只陳述分級事實那一行，**不附**「→ 照原計畫走，定期定額正常扣款即可」等行動句；
資料齊全時整則訊息與修前（`1e603094`，經 `tests/test_dec102_revert_chain.dec102_revert_for` 還原）逐字相同。
missing ≠ HOLD；VIX 不得代替持股完整性判斷。
"""
from __future__ import annotations

import pandas as pd
import pytest

import src.compute.notify.holdings_digest_message as M
import src.services.dividend_station_service as S
from tests.test_dec102_revert_chain import base_module

_ADVICE = ("照原計畫走，定期定額正常扣款即可。",
           "新單放慢、分批進場，不追高；手上部位先不動。",
           "別急著接刀，也別恐慌殺出；等波動收斂再分批，不要一次全下。")
_WK = pd.Series([20.0 + i * 0.1 for i in range(160)],
                index=pd.date_range("2023-01-06", periods=160, freq="W-FRI"))


def _mf_factory(*, fail=(), drift=(), no_price=()):
    def _mf(tk, kind):
        if tk in fail:
            raise RuntimeError("HTTPError: 503")
        _px = None if tk in no_price else (180.0 if kind == "etf" else 500.0)
        if kind == "etf":
            return {"weekly_close": _WK, "premium_pct": 0.3, "sharpe": 0.8, "total_return_1y_pct": 10.0,
                    "annual_yield_pct": 5.0, "inception_years": 5.0, "ann_return_3y_pct": 8.0,
                    "cum_return_3y_pct": 25.0, "peer_ranks": {3: .2, 6: .2, 12: .2},
                    "current_price": _px}
        return {"mj_grade": "Z" if tk in drift else "A", "kd_state": None, "current_price": _px}
    return _mf


_HOLD = [{"ticker": "0050", "lots": 2, "avg_price": 150}, {"ticker": "2330", "lots": 1, "avg_price": 400}]


def _msg(vix, holdings=_HOLD, **kw):
    rows = S.build_station_rows(holdings, vix=vix, metrics_fn=_mf_factory(**kw))
    d = S.build_station_digest(rows, vix)
    return d, M.format_holdings_message(d, {"switch_out": [], "switch_in": []}, as_of="t")


@pytest.mark.parametrize("vix", [15.0, 25.0, 35.0, None])
def test_complete_data_identical_to_base(vix):
    BS = base_module("src/services/dividend_station_service.py", "_dec102_base_svc_l")
    BM = base_module("src/compute/notify/holdings_digest_message.py", "_dec102_base_msg_l")
    d, msg = _msg(vix)
    assert not M._data_short(d)
    brows = BS.build_station_rows(_HOLD, vix=vix, metrics_fn=_mf_factory())
    bd = BS.build_station_digest(brows, vix)
    assert msg == BM.format_holdings_message(bd, {"switch_out": [], "switch_in": []}, as_of="t")
    if vix is not None:
        assert any(a in msg for a in _ADVICE)


_SHORT_CASES = {
    "partial_fetch_failed": dict(fail=("2330",)),
    "all_fetch_failed": dict(fail=("0050", "2330")),
    "all_contract_drift": dict(holdings=[{"ticker": "2330", "lots": 1, "avg_price": 400},
                                         {"ticker": "2317", "lots": 1, "avg_price": 100}],
                               drift=("2330", "2317")),
    "no_price": dict(no_price=("2330",)),
    "foreign": dict(holdings=_HOLD + [{"ticker": "VOO", "lots": 1, "avg_price": 400,
                                       "asset_kind": "stock"}]),
    "unconfirmed": dict(holdings=_HOLD + [{"ticker": "50", "lots": 1, "avg_price": 40,
                                          "asset_kind": "stock"}]),
}


@pytest.mark.parametrize("vix", [15.0, 25.0, 35.0])
@pytest.mark.parametrize("case", sorted(_SHORT_CASES))
def test_data_short_states_vix_fact_only(case, vix):
    d, msg = _msg(vix, **_SHORT_CASES[case])
    assert M._data_short(d), case                    # 前提：同一謂詞判為資料不足
    assert not any(a in msg for a in _ADVICE), msg
    _lines = msg.splitlines()
    _i = next(i for i, l in enumerate(_lines) if l.startswith("😱 VIX："))
    assert f"{vix:.1f}" in _lines[_i]                 # 分級事實仍在
    assert not _lines[_i + 1].startswith("　→"), msg   # 不附行動句


@pytest.mark.parametrize("case", sorted(_SHORT_CASES))
def test_data_short_vix_missing_unchanged(case):
    _d, msg = _msg(None, **_SHORT_CASES[case])
    assert "　→ 本項無資料，不做波動度判讀（不是「市場平靜」）。" in msg   # 灰階原句不變（本來就無行動句）


def test_vix_line_default_identical_to_base():
    BM = base_module("src/compute/notify/holdings_digest_message.py", "_dec102_base_msg_v")
    for v in (None, float("nan"), 12.0, 22.0, 29.9, 30.0, 80.0):
        assert M._vix_line(v, 3) == BM._vix_line(v, 3)
        assert M._vix_line(v, 3, data_short=False) == BM._vix_line(v, 3)
        if v is not None and v == v:
            assert M._vix_line(v, 3, data_short=True) == BM._vix_line(v, 3)[:1]
