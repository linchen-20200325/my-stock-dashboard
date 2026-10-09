"""批 Z17（第十輪分類 A、B 兩組一致判可自主；規格為總管轉述）。

- Z7-n6（L5 `section_health_score`，個股健康度頁 v4 引擎輸入，**不上畫面**）：
  ① 先行指標有列但「外資大小」欄缺／None／pd.NA 時，原 `.get('外資大小', 0) or 0` 仍把 0.0 交給引擎
     （§1 缺值填 0）→ 改為照 Z7 已立的「未取得＝None」；真的 0 口照舊是 0.0。
  ② `_v4_vix2` 原自行 `float()`：收下 ≤0、bool、數字字串 → 改走 L0 `shared.vix_validity.vix_value_or_none`
     （與 §三／§八／§九 同一套「有效 VIX」規則）。
  兩者只影響引擎的 `macro_veto`，本頁只畫防守價／上方賣壓／相對籌碼三卡 ⇒ 畫面零變化（本檔 A 段實跑證明）。
- Z11-n1（併 Z11-n2；L5 `section_state` §二 拐點面板 5）：末列 外資大小／韭菜指數 為 ±inf 時印
  「外資期貨淨多 inf口」「韭菜指數 +inf% …」並出訊號；object 欄為 pd.NA 時 `float(pd.NA)` 拋 TypeError、
  整個面板崩。改為兩欄取值走既有 `_finite_yoy`（與同段登記判定同一函式）→ 非有限／NA 一律當缺、不出訊號，
  籌碼群是否可評估照 Z11 既有判定（另一欄有限才登記）。

golden：修前行為於基底 origin/main `6bc4f44b` 實跑後寫死於各測試註解（⛔ 不讀 git、不由現行碼反推）。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from tests.test_batch_z5 import (
    _CHIPS, _FI_FAIL, _GOLDEN_FLAT, _H_FLAT, _LI_FLAT, _expected_flat, _render_state,
)
from tests.test_batch_z7 import _df2
from tests.test_m2n2_no_zero_fill import _FakeST

_HUGE = 10 ** 400


# ══════════════════════════════════════════════════════════════════════════
# A. Z7-n6 —— 個股健康度頁 v4 引擎輸入
# ══════════════════════════════════════════════════════════════════════════
def _health(mp, li, vix_current=18.0, *, force=None):
    """實跑個股健康度頁。回 (畫面輸出, 交給 V4 引擎的 macro dict)。force：強制改寫引擎收到的 macro 欄位。"""
    import src.ui.tabs.stock_sections.section_health_score as mod
    from src.compute.strategy.v4_strategy_engine import V4StrategyEngine as _engine_cls
    seen: list = []

    class _Spy(_engine_cls):
        def __init__(self, df, macro, shares):
            if force is not None:
                macro = {**macro, **force}
            seen.append(dict(macro))
            super().__init__(df, macro, shares)

    fake = _FakeST({"macro_info": {"vix": {"current": vix_current}}, "li_latest": li})
    mp.setattr(mod, "st", fake)
    mp.setattr(mod, "V4StrategyEngine", _Spy)
    mod.render_health_score_section("2330", 70.0, {}, _df2(), 100.0, None, None, None,
                                    55.0, 1.2, 0.5, 60.0, 55.0, None, None, None)
    assert len(seen) == 1
    return list(fake.out), seen[0]


#: 修前（6bc4f44b 實跑）：col-absent／none 引擎收到 foreign_futures=0.0；pd-na-object 修前已是 None
#: （`pd.NA or 0` 拋 TypeError 被既有 except 接住）—— 留作回歸。
_FUT_MISSING = {
    "col-absent": pd.DataFrame({"選PCR": [90.0]}),
    "none": pd.DataFrame({"外資大小": [None], "選PCR": [90.0]}, dtype=object),
    "pd-na-object": pd.DataFrame({"外資大小": [pd.NA], "選PCR": [90.0]}, dtype=object),
}

#: 修前（6bc4f44b 實跑）引擎收到的 vix：-5.0／0.0／-0.0／1.0／1.0／18.5／-inf→None（已擋）…
_VIX_INVALID = {
    "neg": -5.0, "zero": 0.0, "neg-zero": -0.0, "true": True, "np-true": np.True_,
    "num-str": "18.5", "inf": math.inf, "neg-inf": -math.inf, "nan": math.nan, "huge": _HUGE,
}
_VIX_PRE = {"neg": -5.0, "zero": 0.0, "neg-zero": -0.0, "true": 1.0, "np-true": 1.0, "num-str": 18.5}


class TestZ7n6FuturesMissingIsNone:

    @pytest.mark.parametrize("name", sorted(_FUT_MISSING))
    def test_missing_not_zero(self, monkeypatch, name):
        _out, macro = _health(monkeypatch, _FUT_MISSING[name])
        assert macro["foreign_futures"] is None                 # 修前：0.0
        assert macro["pcr"] == 90.0 and macro["vix"] == 18.0

    @pytest.mark.parametrize("v", [0.0, 0, -40000.0, 12345])
    def test_value_present_passes_through(self, monkeypatch, v):
        _out, macro = _health(monkeypatch, pd.DataFrame({"外資大小": [v], "選PCR": [90.0]}))
        assert macro["foreign_futures"] == float(v) and isinstance(macro["foreign_futures"], float)

    @pytest.mark.parametrize("name", sorted(_FUT_MISSING))
    def test_screen_identical_to_pre_fix(self, monkeypatch, name):
        now, _ = _health(monkeypatch, _FUT_MISSING[name])
        old, m_old = _health(monkeypatch, _FUT_MISSING[name], force={"foreign_futures": 0.0})
        assert m_old["foreign_futures"] == 0.0
        assert now == old


class TestZ7n6VixValidity:

    @pytest.mark.parametrize("name", sorted(_VIX_INVALID))
    def test_invalid_vix_is_none(self, monkeypatch, name):
        _out, macro = _health(monkeypatch, None, _VIX_INVALID[name])
        assert macro["vix"] is None

    @pytest.mark.parametrize("v", [18.0, 5e-324, 150.0, np.float64(21.3), 22])
    def test_valid_vix_unchanged(self, monkeypatch, v):
        _out, macro = _health(monkeypatch, None, v)
        assert macro["vix"] == float(v)

    @pytest.mark.parametrize("name", sorted(_VIX_PRE))
    def test_screen_identical_to_pre_fix(self, monkeypatch, name):
        now, _ = _health(monkeypatch, None, _VIX_INVALID[name])
        old, m_old = _health(monkeypatch, None, _VIX_INVALID[name], force={"vix": _VIX_PRE[name]})
        assert m_old["vix"] == _VIX_PRE[name]
        assert now == old

    def test_odd_object_does_not_crash(self, monkeypatch):
        """有 `__float__`、沒有比較運算子：共用判定照拋 TypeError —— 本頁既有 try 接住、當缺值（不崩頁）。"""
        class _FloatOnly:
            def __float__(self):
                return 18.0
        _out, macro = _health(monkeypatch, None, _FloatOnly())
        assert macro["vix"] is None


# ══════════════════════════════════════════════════════════════════════════
# B. Z11-n1（併 Z11-n2）—— §二 面板 5：非有限值／pd.NA 當缺
# ══════════════════════════════════════════════════════════════════════════
#: 修前（6bc4f44b 實跑）：兩欄皆無有限值 ⇒ 籌碼群未登記，但仍出訊號：
#:   fut+inf → ('外資期貨多方', '外資期貨淨多 inf口 → 多頭強勢確認')
#:   fut-inf → ('外資期貨大量空單', '外資期貨淨空 inf口 > 3萬口 → 頂部起跌訊號')
#:     （↑ 修前原句照錄；批 Z10 續作〔客戶 2026-10-09 裁示 2〕起現行文案為「… ≥ 3萬口 …」）
#:   leek+inf → ('散戶極度看多（危險）', '韭菜指數 +inf% > +20% → …')
#:   leek-inf → ('散戶極度悲觀（機會）', '韭菜指數 -inf% < -20% → …')
#:   pd-na → TypeError（float(pd.NA)），整個 render_section_state 拋出
_LI_NO_FINITE = {
    "fut+inf": pd.DataFrame({"外資大小": [math.inf], "韭菜指數": [math.nan]}),
    "fut-inf": pd.DataFrame({"外資大小": [-math.inf], "韭菜指數": [math.nan]}),
    "leek+inf": pd.DataFrame({"外資大小": [math.nan], "韭菜指數": [math.inf]}),
    "leek-inf": pd.DataFrame({"外資大小": [math.nan], "韭菜指數": [-math.inf]}),
    "both-inf": pd.DataFrame({"外資大小": [math.inf], "韭菜指數": [-math.inf]}),
    "pd-na": pd.DataFrame({"外資大小": [pd.NA], "韭菜指數": [pd.NA]}, dtype=object),
}

#: 修前（6bc4f44b 實跑）：另一欄有限 ⇒ 籌碼群登記，但非有限那欄仍出訊號（inf）或整面板 TypeError（pd.NA）。
_LI_OTHER_FINITE = {
    "fut+inf-leek5": pd.DataFrame({"外資大小": [math.inf], "韭菜指數": [5.0]}),
    "fut-inf-leek5": pd.DataFrame({"外資大小": [-math.inf], "韭菜指數": [5.0]}),
    "fut5000-leek+inf": pd.DataFrame({"外資大小": [5000.0], "韭菜指數": [math.inf]}),
    "fut-na-leek5": pd.DataFrame({"外資大小": [pd.NA], "韭菜指數": [5.0]}, dtype=object),
    "fut5000-leek-na": pd.DataFrame({"外資大小": [5000.0], "韭菜指數": [pd.NA]}, dtype=object),
}


class TestZ11n1PanelFiveNonFinite:

    @pytest.mark.parametrize("name", sorted(_LI_NO_FINITE))
    def test_no_finite_value_is_unevaluated_no_signal(self, monkeypatch, name):
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FAIL,
                          ss={"li_latest": _LI_NO_FINITE[name]})
        assert r.out == _expected_flat(chips_ok=False, cycle_ok=True)
        assert r.pivots == []
        assert "inf" not in r.text and f"{_CHIPS}：未評估" in r.text

    @pytest.mark.parametrize("name", sorted(_LI_OTHER_FINITE))
    def test_other_column_finite_still_registered(self, monkeypatch, name):
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FAIL,
                          ss={"li_latest": _LI_OTHER_FINITE[name]})
        assert r.out == _GOLDEN_FLAT
        assert r.pivots == []

    @pytest.mark.parametrize("fut, leek, title", [
        (-40000.0, math.inf, "外資期貨大量空單"),
        (-5000.0, math.nan, "外資空單縮減"),
        (20000.0, pd.NA, "外資期貨多方"),
        (math.inf, 25.0, "散戶極度看多（危險）"),
        (pd.NA, -25.0, "散戶極度悲觀（機會）"),
    ])
    def test_finite_column_signal_unchanged(self, monkeypatch, fut, leek, title):
        df = pd.DataFrame({"外資大小": [fut], "韭菜指數": [leek]}, dtype=object)
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FAIL, ss={"li_latest": df})
        assert [p[0] for p in r.pivots] == [title]
        assert "inf" not in r.text

    def test_finite_signal_text_unchanged(self, monkeypatch):
        """有限值的訊號字樣逐字照舊（修前 6bc4f44b 實跑同字）。"""
        df = pd.DataFrame({"外資大小": [20000.0], "韭菜指數": [25.0]})
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FAIL, ss={"li_latest": df})
        assert [p[3] for p in r.pivots] == [
            "外資期貨淨多 20,000口 → 多頭強勢確認",
            "韭菜指數 +25.0% > +20% → 散戶過熱，頂部拐點警示（反向指標）",
        ]
