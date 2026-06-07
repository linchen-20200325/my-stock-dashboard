"""v18.173 雙速合議 UI 接線測試 — _render_global_risk_radar slow_verdict 路徑。

驗證重點：
1. slow_verdict=None → 不渲染合議 banner（純 10 燈雷達）
2. slow_verdict 提供 → 呼叫 synthesize_dual_verdict 並渲染 banner
3. 雷達警報 + 樂觀 slow → 渲染「雙速分歧降槓桿」
4. 雷達極端警報 + 任意 slow → 強制覆蓋為「立即減倉防守」
5. 雷達平靜 + slow → adopt_slow 模式，banner 含原 slow level
6. AppTest 保護門：fred_api_key < 30 字元 → 完全跳過（含 slow_verdict）
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import tab_macro


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────
def _yf(vals: list[float], base_date: str = "2026-06-01") -> pd.Series:
    n = len(vals)
    return pd.Series(vals, index=pd.date_range(base_date, periods=n, freq="D"),
                     dtype=float)


def _fred(vals: list[float], base_date: str = "2026-06-01") -> pd.DataFrame:
    n = len(vals)
    return pd.DataFrame({"date": pd.date_range(base_date, periods=n, freq="D"),
                         "value": vals})


@pytest.fixture
def stub_st(monkeypatch):
    """把 tab_macro 內 st.* 替換成 MagicMock，避免 streamlit runtime。"""
    fake = MagicMock()
    fake.columns.return_value = (MagicMock(), MagicMock(), MagicMock(),
                                  MagicMock(), MagicMock())
    fake.expander.return_value.__enter__ = lambda *_a, **_k: MagicMock()
    fake.expander.return_value.__exit__ = lambda *_a, **_k: False
    monkeypatch.setattr(tab_macro, 'st', fake)
    return fake


_FRED_KEY = 'a' * 32  # 32 字元（real FRED key 長度，繞過 AppTest 保護門）


def _calm_slow_v() -> dict:
    """模擬 v18.171 dual-view 算出的 _lt 映射成 slow_verdict（樂觀情境）。"""
    return {
        'level':  '🟢 成長期',
        'score':  10.0,  # 已乘 5 後的校準分數（原 _lt score ~+2.0）
        'color':  '#3fb950',
        'icon':   '🟢',
        'action': '景氣擴張中；建議持股 85%',
    }


def _bear_slow_v() -> dict:
    return {
        'level':  '🔴 衰退期',
        'score':  -7.0,
        'color':  '#f85149',
        'icon':   '🔴',
        'action': '景氣衰退；建議持股 30%',
    }


# ════════════════════════════════════════════════════════════════════════
# §1 slow_verdict=None → 不渲染合議 banner
# ════════════════════════════════════════════════════════════════════════
class TestSlowVerdictNone:
    def test_no_slow_verdict_no_synth_banner(self, stub_st):
        """slow_verdict=None → 10 燈渲染但不呼叫 synth banner。"""
        with patch('risk_radar.fetch_yf_close', return_value=_yf([15.0] * 8)), \
             patch('risk_radar.fetch_fred', return_value=_fred([3.5, 3.51])):
            tab_macro._render_global_risk_radar(_FRED_KEY, slow_verdict=None)

        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        # 應渲染雷達 heading 但不渲染合議 banner
        assert '全球風險雷達' in joined
        assert '雙速合議' not in joined


# ════════════════════════════════════════════════════════════════════════
# §2 slow_verdict 提供 → 渲染合議 banner
# ════════════════════════════════════════════════════════════════════════
class TestSlowVerdictProvided:
    def test_calm_radar_with_bull_slow_adopts(self, stub_st):
        """雷達平靜 + 慢樂觀 → adopt_slow，level 含原 slow level。"""
        # 所有 yf 抓平靜資料 → 雷達應為平靜
        with patch('risk_radar.fetch_yf_close', return_value=_yf([15.0] * 8)), \
             patch('risk_radar.fetch_fred', return_value=_fred([3.5, 3.51])):
            tab_macro._render_global_risk_radar(_FRED_KEY,
                                                  slow_verdict=_calm_slow_v())
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '雙速合議' in joined
        assert '成長期' in joined  # 原 slow level 應在 banner
        assert 'adopt_slow' in joined  # mode 字串

    def test_alert_radar_with_bull_slow_diverges(self, stub_st):
        """雷達警報（red=2 或 3，未達極端 ≥4）+ 慢樂觀 → 雙速分歧降槓桿。"""
        # 構造剛好 2 紅燈：VIX>30, MOVE>130（避免 ≥4 變極端警報）
        def _yf_red(t, **kw):
            if t == '^VIX':
                return _yf([22.0] * 7 + [32.0])  # 紅
            if t == '^MOVE':
                return _yf([105.0] * 7 + [135.0])  # 紅
            return _yf([100.0] * 30)  # 其他保持平靜

        with patch('risk_radar.fetch_yf_close', side_effect=_yf_red), \
             patch('risk_radar.fetch_fred', return_value=_fred([3.5, 3.51])):
            tab_macro._render_global_risk_radar(_FRED_KEY,
                                                  slow_verdict=_calm_slow_v())
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '雙速合議' in joined
        # slow_score=10.0 >= 5 → downgrade_2 雙速分歧
        assert 'downgrade_2' in joined or '雙速分歧' in joined or '降槓桿' in joined

    def test_extreme_radar_overrides_any_slow(self, stub_st):
        """雷達極端警報（≥4 紅燈）→ 強制覆蓋為立即減倉防守，慢總經暫不採信。"""
        def _yf_red(t, **kw):
            # 多紅燈確保 ≥4 紅
            if t == '^VIX':
                return _yf([22.0] * 7 + [32.0])
            if t == '^MOVE':
                return _yf([105.0] * 7 + [135.0])
            if t == '^CPC':
                return _yf([0.9] * 7 + [1.25])
            if t == '^SOX':
                return _yf([5500.0] * 7 + [5280.0])  # -4%
            if t in ('^N225', '^HSI'):
                return _yf([100.0] * 20 + [97.0])
            return _yf([100.0] * 30)

        with patch('risk_radar.fetch_yf_close', side_effect=_yf_red), \
             patch('risk_radar.fetch_fred', return_value=_fred([3.5, 3.82])):  # HY +32bp 紅
            tab_macro._render_global_risk_radar(_FRED_KEY,
                                                  slow_verdict=_calm_slow_v())
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '雙速合議' in joined
        # 雷達極端警報 → override_defense，不採信慢總經
        assert 'override_defense' in joined or '立即減倉' in joined


# ════════════════════════════════════════════════════════════════════════
# §3 防呆：malformed slow_verdict 不爆
# ════════════════════════════════════════════════════════════════════════
class TestSlowVerdictDefense:
    def test_partial_slow_verdict_uses_defaults(self, stub_st):
        """slow_verdict 缺欄位 → fallback 不爆。"""
        partial = {'level': '🟡 過熱期'}  # 缺 score/color/icon/action
        with patch('risk_radar.fetch_yf_close', return_value=_yf([15.0] * 8)), \
             patch('risk_radar.fetch_fred', return_value=_fred([3.5, 3.51])):
            tab_macro._render_global_risk_radar(_FRED_KEY, slow_verdict=partial)
        # 不爆即 pass — 應仍渲染合議 banner
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '雙速合議' in joined

    def test_synth_exception_does_not_break(self, stub_st):
        """synth 拋例外不應中斷整體渲染（catch print）。"""
        with patch('risk_radar.fetch_yf_close', return_value=_yf([15.0] * 8)), \
             patch('risk_radar.fetch_fred', return_value=_fred([3.5, 3.51])), \
             patch('risk_radar.synthesize_dual_verdict',
                   side_effect=RuntimeError('synth boom')):
            tab_macro._render_global_risk_radar(_FRED_KEY,
                                                  slow_verdict=_calm_slow_v())
        # 雷達 heading 應該仍渲染（10 燈在 synth 之前）
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '全球風險雷達' in joined
        # 但合議 banner 因例外而沒渲染
        assert '雙速合議' not in joined


# ════════════════════════════════════════════════════════════════════════
# §4 AppTest 保護門也覆蓋 slow_verdict 路徑
# ════════════════════════════════════════════════════════════════════════
class TestAppTestGuardWithSlowVerdict:
    def test_short_key_skips_even_with_slow_verdict(self, stub_st):
        """短 key + slow_verdict → 仍然完全跳過渲染（不執行任何 markdown）。"""
        with patch('risk_radar.fetch_yf_close') as _m_yf, \
             patch('risk_radar.fetch_fred') as _m_fred:
            tab_macro._render_global_risk_radar('short', slow_verdict=_calm_slow_v())
            _m_yf.assert_not_called()
            _m_fred.assert_not_called()
        stub_st.markdown.assert_not_called()


# ════════════════════════════════════════════════════════════════════════
# §5 雷達警戒（紅+黃 ≥4）+ 樂觀 slow → 警戒觀察
# ════════════════════════════════════════════════════════════════════════
class TestWarningBranchWithSlowVerdict:
    def test_warning_radar_with_bull_slow_observes(self, stub_st):
        """4 黃燈（紅+黃 ≥4）+ 慢樂觀 → 警戒觀察，暫緩加碼。"""
        # 構造 4 黃燈（VIX yellow / MOVE yellow / SOX yellow / P/C yellow）
        def _yf_yellow(t, **kw):
            if t == '^VIX':
                return _yf([20.0] * 6 + [24.0, 26.0])  # 黃 (>=25)
            if t == '^MOVE':
                return _yf([95.0] * 7 + [115.0])  # 黃 (>=110)
            if t == '^SOX':
                return _yf([5500.0] * 7 + [5390.0])  # 黃 -2%
            if t == '^CPC':
                return _yf([0.85] * 7 + [1.05])  # 黃 >=1.0
            return _yf([100.0] * 30)

        with patch('risk_radar.fetch_yf_close', side_effect=_yf_yellow), \
             patch('risk_radar.fetch_fred', return_value=_fred([3.5, 3.51])):
            tab_macro._render_global_risk_radar(_FRED_KEY,
                                                  slow_verdict=_calm_slow_v())
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '雙速合議' in joined
        # slow_score=10.0 >=5 + 雷達警戒 → downgrade_1 警戒觀察
        assert 'downgrade_1' in joined or '警戒觀察' in joined

    def test_warning_radar_with_bear_slow_neutralizes(self, stub_st):
        """雷達警戒 + 慢悲觀（score=-7×5=-35）→ 中性觀察。"""
        def _yf_yellow(t, **kw):
            if t == '^VIX':
                return _yf([20.0] * 6 + [24.0, 26.0])
            if t == '^MOVE':
                return _yf([95.0] * 7 + [115.0])
            if t == '^SOX':
                return _yf([5500.0] * 7 + [5390.0])
            if t == '^CPC':
                return _yf([0.85] * 7 + [1.05])
            return _yf([100.0] * 30)

        with patch('risk_radar.fetch_yf_close', side_effect=_yf_yellow), \
             patch('risk_radar.fetch_fred', return_value=_fred([3.5, 3.51])):
            tab_macro._render_global_risk_radar(_FRED_KEY,
                                                  slow_verdict=_bear_slow_v())
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '雙速合議' in joined
        assert 'downgrade_1' in joined or '中性觀察' in joined
