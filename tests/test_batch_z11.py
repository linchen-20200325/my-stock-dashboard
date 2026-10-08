"""批 Z11（2026-10-08）—— Z5-n2（§二 面板 5 籌碼群登記）＋ Z5-n3（面板 6-B 領先指標轉折判定）。

Z5-n2（L5 `section_state.render_section_state` 面板 5）
────────────────────────────────────────────────────────────────
修前（origin/main `1354d9ac`）：`li_latest` 只要非空就 `_fam_ok.add('chips')` —— 末列 `外資大小`／
`韭菜指數` 為 NaN／None／欄位不存在時，籌碼群仍被登記為可評估，分群明細印「籌碼（外資期貨 / 韭菜 /
外資連續）：中性」、頭句算進「可評估 2/6 群」（失敗被說成中性；與 C7-n1 同類）。
修法：比照 C7-n1 —— 兩欄任一為有限數值才登記（`_finite_yoy`，不另寫一份）；沒登記走 L2
`aggregate_pivot_families` 的既有「未評估」路徑與既有字樣。⛔ 新增字。

Z5-n3（L1 `tw_macro.fetch_ndc_leading_index` 轉折判定；客戶 2026-10-06 Q-r9b ②「領先指標看兩位小數
判轉負：准」）
────────────────────────────────────────────────────────────────
修前：判定式用未捨入的 6M smoothed change —— 只降 0.0017% 也判「⚠️ 由正轉負」，畫面（兩位小數）
卻印「+0.10%→-0.00%」紅燈。修法：以兩位小數判斷，等於 0 算「📊 持平」（既有字，面板 6-B 不亮燈）。

golden：以 origin/main `1354d9ac`（修前）同 harness 實跑後寫死於各測試 docstring／常數 ——
⛔ 在測試裡讀 git、⛔ 由程式反推。harness 沿用 `tests/test_batch_z5.py`（假 st＋離線替身），不觸網。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import src.data.macro.tw_macro as TW
from tests.test_batch_z5 import (
    _CHIPS, _FI_FAIL, _GOLDEN_FLAT, _H_FLAT, _LI_FLAT, _expected_flat, _render_state,
)


# ══════════════════════════════════════════════════════════════════════════
# Z5-n2 —— 面板 5：末列無有限值 ⇒ 籌碼群「未評估」，不是「中性」
# ══════════════════════════════════════════════════════════════════════════
#: 外資連續日數（6-C）失敗 ⇒ 籌碼群能不能評估只看面板 5（`li_latest`）。
_LI_LATEST_NO_VALUE = {
    "last_row_nan": pd.DataFrame({"外資大小": [1.0, np.nan], "韭菜指數": [2.0, np.nan]}),
    "last_row_none": pd.DataFrame({"外資大小": [1, None], "韭菜指數": [2, None]}, dtype=object),
    "columns_absent": pd.DataFrame({"選PCR": [1.0]}),
    "one_col_absent_other_nan": pd.DataFrame({"韭菜指數": [np.nan]}),
}

#: 至少一欄有限 ⇒ 照舊登記（修前修後同為 `_GOLDEN_FLAT`：無訊號、籌碼「中性」）。
_LI_LATEST_HAS_VALUE = {
    "fut_only": pd.DataFrame({"外資大小": [5000.0], "韭菜指數": [np.nan]}),
    "leek_only": pd.DataFrame({"外資大小": [None], "韭菜指數": [5.0]}, dtype=object),
    "both": pd.DataFrame({"外資大小": [5000.0], "韭菜指數": [5.0]}),
    "fut_zero": pd.DataFrame({"外資大小": [0.0]}),          # 0 是真的值（不看真假值）
}


class TestZ5n2ChipsRegisteredOnlyWithFiniteValue:

    @pytest.mark.parametrize("name", sorted(_LI_LATEST_NO_VALUE))
    def test_no_finite_value_is_unevaluated(self, monkeypatch, name):
        """修前（1354d9ac 實跑）：四種形狀的完整輸出皆＝`_GOLDEN_FLAT`（籌碼：中性、可評估 2/6 群）。"""
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FAIL,
                          ss={"li_latest": _LI_LATEST_NO_VALUE[name]})
        assert r.out == _expected_flat(chips_ok=False, cycle_ok=True)
        assert f"{_CHIPS}：未評估" in r.text and f"{_CHIPS}：中性" not in r.text
        assert r.out != _GOLDEN_FLAT
        assert r.pivots == []

    @pytest.mark.parametrize("name", sorted(_LI_LATEST_HAS_VALUE))
    def test_finite_value_still_registered(self, monkeypatch, name):
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FAIL,
                          ss={"li_latest": _LI_LATEST_HAS_VALUE[name]})
        assert r.out == _GOLDEN_FLAT

    def test_signal_path_unchanged(self, monkeypatch):
        """有值且觸發訊號：照舊（外資期貨淨空 > 3 萬口 → 籌碼偏空）。"""
        df = pd.DataFrame({"外資大小": [-40000.0], "韭菜指數": [np.nan]})
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FAIL, ss={"li_latest": df})
        assert f"{_CHIPS}：偏空" in r.text
        assert [p[0] for p in r.pivots] == ["外資期貨大量空單"]


# ══════════════════════════════════════════════════════════════════════════
# Z5-n3 —— 6-B 領先指標：以兩位小數判轉折
# ══════════════════════════════════════════════════════════════════════════
def _li_from_series(monkeypatch, vals) -> dict:
    """真 L1 判定式：餵一條領先指標序列（替身取代 FinMind／dgtw），回 `fetch_ndc_leading_index` 結果。"""
    df = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=len(vals), freq="MS"),
                       "leading": [float(v) for v in vals]})
    monkeypatch.setattr(TW, "fetch_business_indicator_series", lambda **_k: df.copy())
    TW.fetch_ndc_leading_index.cache_clear()
    try:
        return TW.fetch_ndc_leading_index(months_back=18)
    finally:
        TW.fetch_ndc_leading_index.cache_clear()


#: 末期 6M smoothed change ≈ −0.0017%（前期 +0.10%）。修前（1354d9ac 實跑）：
#:   smooth6m=-0.0、prev_s6m=0.1、inflection='⚠️ 由正轉負'；面板 6-B 印
#:   「⚠️ 領先指標 6M 由正轉負」＋「6M smoothed change：+0.10%→-0.00% → 景氣轉折下行」。
_TINY_DROP = [100] * 8 + [100.6, 100 - 0.0102]
#: 前後兩期都只差千分之幾（前期 +0.003%、末期 −0.0017%）——HANDOFF 原述的「+0.00%→-0.00%」。
#:   修前（1354d9ac 實跑）：inflection='⚠️ 由正轉負'，印「+0.00%→-0.00%」。
_TINY_BOTH = [100] * 8 + [100 + 0.018, 100 - 0.0102]
#: 鏡像：末期 +0.0017%、前期 −0.10%。修前（1354d9ac 實跑）：'🚀 6M 由負轉正'，印「-0.10%→+0.00%」。
_TINY_RISE = [100] * 8 + [100 - 0.6, 100 + 0.0102]


class TestZ5n3LeadingIndexTwoDecimals:

    @pytest.mark.parametrize("vals", [_TINY_DROP, _TINY_BOTH, _TINY_RISE],
                             ids=["tiny_drop", "tiny_both", "tiny_rise"])
    def test_rounds_to_zero_is_flat(self, monkeypatch, vals):
        r = _li_from_series(monkeypatch, vals)
        assert r["error"] is None
        assert r["smooth6m"] == 0
        assert r["inflection"] == "📊 持平"

    @pytest.mark.parametrize("vals", [_TINY_DROP, _TINY_BOTH, _TINY_RISE],
                             ids=["tiny_drop", "tiny_both", "tiny_rise"])
    def test_panel_6b_no_lamp(self, monkeypatch, vals):
        """端到端：真 L1 結果送進 §二 面板 6 —— 6-B 不亮燈，景氣群「中性」。"""
        li = _li_from_series(monkeypatch, vals)
        r = _render_state(monkeypatch, _H_FLAT, li, _FI_FAIL)
        assert r.pivots == []
        assert "領先指標" not in "".join(p[0] for p in r.pivots)
        assert "-0.00%" not in r.text and "→+0.00%" not in r.text

    @pytest.mark.parametrize("vals,inflection", [
        ([100] * 8 + [100.6, 100 - 0.6], "⚠️ 由正轉負"),        # +0.10% → −0.10%
        ([100] * 8 + [100 - 0.6, 100 + 0.6], "🚀 6M 由負轉正"),   # −0.10% → +0.10%
        ([100] * 8 + [100.6, 100.3], "🟢 持續擴張"),
        ([100] * 8 + [100 - 0.6, 100 - 0.3], "🔴 持續收縮"),
    ])
    def test_visible_changes_unchanged(self, monkeypatch, vals, inflection):
        """兩位小數看得出正負的情境：判定與修前（1354d9ac 實跑）相同。"""
        assert _li_from_series(monkeypatch, vals)["inflection"] == inflection

    def test_drop_after_flat_prev_shows_plus_zero(self, monkeypatch):
        """前期只差 −0.004%（兩位小數＝0）、末期 −0.10%：以兩位小數判 ⇒ 前期算 0 ⇒「由正轉負」
        （與前期恰為 0.0 的既有判定同解）；畫面前期印「+0.00%」，不印「-0.00%」。"""
        li = _li_from_series(monkeypatch, [100] * 8 + [100 - 0.024, 100 - 0.6])
        assert li["inflection"] == "⚠️ 由正轉負"
        r = _render_state(monkeypatch, _H_FLAT, li, _FI_FAIL)
        assert "6M smoothed change：+0.00%→-0.10% → 景氣轉折下行" in r.text
