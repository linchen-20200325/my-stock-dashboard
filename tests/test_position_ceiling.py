"""tests/test_position_ceiling.py — 姿態油門「建議區間」× §十一「風險上限」並排守衛(v19.168 第1項)。

user 拍板:「兩個都留 上限 vs 建議區間」。§十一 曝險鎖的 exposure_limit_pct(薩姆/PMI/
外資期貨硬否決天花板)不再是孤立的第三個持股%,而是與總經油門 gauge 的「建議持股區間」
並排呈現、清楚標成互補(實際持股取兩者較低)。未跑 §十一 AI 裁決(無 exposure_limit_pct)
時只顯示區間(§1 fail-safe)。

v19.170 更新:油門改吃建議持股 SSOT `get_allocation()`,「取兩者較低」這條規則
從 UI 文案變成 `shared/allocation_decision.build_allocation_decision` 裡真的執行的
`min()`。本檔斷言隨之改為(a) 釘死接線入口 (b) 用 `warroom_summary` + tmp_path 的
`macro_state.json` 餵真實來源鏈,驗證最終數字**確實被天花板壓低**,而非只是並排顯示。
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

import pytest

_SRC = (Path(__file__).resolve().parents[1]
        / "src/ui/tabs/macro/section_traffic_light.py").read_text(encoding="utf-8")


# ── source-scan:接線不回退 ──────────────────────────────────────
def test_gauge_reads_exposure_ceiling_and_labels_complement():
    """v19.170:油門改吃 `get_allocation()` SSOT,天花板由 SSOT 內部仲裁。

    原斷言 `"exposure_limit_pct" in _SRC` 已成 false green —— 該字串只剩在
    docstring「不再自行讀 macro_state['exposure_limit_pct']」裡,反而是
    *拿掉* 直讀的證據。改釘「確實接上唯一取數入口」+ 新 UI 文案。
    """
    assert "get_allocation" in _SRC, "gauge 未接建議持股 SSOT(get_allocation)"
    assert "風險上限" in _SRC, "未顯示 §十一 硬否決天花板"
    assert "兩者取較低" in _SRC, "未標明『實際取兩者較低』的互補關係"
    assert "最終建議持股" in _SRC, "未輸出全站唯一該被記住的持股數字"


# ── 實機 render(AppTest,對齊 pe_river/cross_ai slow 慣例)──────
# health 62 → 姿態帶 50–70%(中性偏多);天花板 40% < 70% → 最終必須被壓到 40%。
_WARROOM = {"health_score": 62, "regime": "neutral", "traffic_light": "🟡 震盪整理"}


def _script_render():
    """v19.170:fixture 改設 `warroom_summary`。

    舊 fixture 設的是 `st.session_state['macro_state']`,但 `get_allocation()`
    的來源鏈是 `warroom_summary` + `macro_state.json`,那個 key 根本沒人讀 →
    `is_loaded=False` → UI 走 `st.info` 早退 → 底下所有 markdown 斷言全落空。
    """
    import streamlit as st
    st.session_state["warroom_summary"] = dict(_WARROOM)
    from src.ui.tabs.macro.section_traffic_light import render_position_throttle
    render_position_throttle({"health": 62, "regime": "neutral", "defense": False})


def _patch_state_file(monkeypatch, path) -> None:
    """把 `get_macro_state` 的 `state_file_path` 導向測試檔,其餘邏輯照原樣跑。

    `allocation_service.get_allocation()` 內是 function-local import
    (`from src.services.macro_state_locker import get_macro_state`),
    每次呼叫才解析模組屬性 → 直接 patch 模組屬性即可生效。
    """
    from src.services import macro_state_locker as _msl
    monkeypatch.setattr(
        _msl, "get_macro_state",
        functools.partial(_msl.get_macro_state, state_file_path=str(path)))


@pytest.mark.slow
class TestCeilingRender:
    @classmethod
    def setup_class(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:
            pytest.skip("streamlit.testing.v1.AppTest 不可用(collection stub 生態)")

    def test_ceiling_caps_posture_band(self, tmp_path, monkeypatch):
        """姿態帶 50–70% × 風險上限 40% → 最終必須是 40%,不是 50–70%。

        這是本檔的核心意圖:UI 寫著「兩者取較低」,程式必須真的執行 min(),
        而不是只把兩個數字並排印出來。
        """
        _f = tmp_path / "macro_state.json"
        _f.write_text(
            json.dumps({"market_regime": "🟡 震盪整理", "exposure_limit_pct": 40},
                       ensure_ascii=False),
            encoding="utf-8")
        _patch_state_file(monkeypatch, _f)

        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_script_render).run(timeout=30)
        assert not at.exception
        _all = " ".join(m.value for m in at.markdown)
        assert "姿態帶 <b>50–70%</b>" in _all          # 姿態帶原樣並排呈現
        assert "風險上限 <b>40%</b>" in _all            # 天花板並排
        # v19.170:UI 改吃 `AllocationDecision.range_text`(顯示格式 SSOT),
        # lo==hi 時回 '40%' 而非 '40–40%' → 斷言同步改成新格式。
        assert "最終建議持股 40%" in _all               # ✅ min() 真的生效
        assert "40–40%" not in _all                     # 不得回退成怪字串
        assert "最終建議持股 50–70%" not in _all        # 沒有退回未壓制的姿態帶

    def test_no_ceiling_keeps_full_posture_band(self, tmp_path, monkeypatch):
        """未跑 §十一 AI 裁決(無 macro_state.json)→ 不偽造天花板,保留姿態帶(§1)。"""
        _patch_state_file(monkeypatch, tmp_path / "does_not_exist.json")

        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_script_render).run(timeout=30)
        assert not at.exception
        _all = " ".join(m.value for m in at.markdown)
        assert "最終建議持股 50–70%" in _all            # 無天花板 → 姿態帶即最終
        assert "風險上限：無硬否決" in _all              # 誠實寫明,不留白
        assert "系統風險上限" not in _all                # 不捏造 cap(§1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
