# -*- coding: utf-8 -*-
"""I1 ②：🏆 個股組合「③ 多因子評分排行」的權重說明不得再寫死中性。

修掉的原始碼（`src/ui/tabs/stock_grp_sections/section_portfolio_summary.py`）::

    _w = WEIGHT_TABLES['neutral']
    st.caption(
        f"趨勢×{_w['trend']:.2f} + ... (neutral 權重,SSOT 來自 config.WEIGHT_TABLES)")

畫面上那些分數是 `section_batch_fetcher` 用**當下仲裁出來的 regime**（H1 之後）算的，
regime=bull 時總分確實走 bull 權重；caption 卻恆定宣稱中性。說明文字與數字來自兩個
不同的 regime，而使用者只讀得到說明文字。

同檔第二處：`score_t3` 為空時固定顯示「多因子資料計算中／等待評分載入」。H1 之後
**「總經未評估」也會讓 `score_t3` 為空**（§1 拒絕評分），此時「計算中」是錯的措辭 ——
沒有任何背景工作會把它算完，而真正該做的事（去開 🌍 總經頁）完全沒被提到。

測試策略：把 section 模組的 `st` 換成錄音機，**直接讀使用者會看到的那幾句**
（行為斷言，不掃原始碼字面）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.compute.screener.scorability import summarize_candidates  # noqa: E402
from src.config import WEIGHT_TABLES  # noqa: E402
from src.ui.tabs.stock_grp_sections import section_portfolio_summary as SEC  # noqa: E402


# ══════════════════════════════════════════════════════════════
# 假 Streamlit：錄下所有輸出給人看的字
# ══════════════════════════════════════════════════════════════
class _ColumnConfig:
    def __getattr__(self, _name):
        return lambda *a, **k: None


class _FakeSt:
    """只錄音，不渲染。`text` 把所有使用者可見的字串串起來。"""

    def __init__(self):
        self.markdowns: list[str] = []
        self.captions: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []
        self.dataframes: list = []
        self.column_config = _ColumnConfig()

    def markdown(self, body, **_k):
        self.markdowns.append(str(body))

    def caption(self, body, **_k):
        self.captions.append(str(body))

    def warning(self, body, **_k):
        self.warnings.append(str(body))

    def info(self, body, **_k):
        self.infos.append(str(body))

    def dataframe(self, data, **_k):
        self.dataframes.append(data)

    @property
    def text(self) -> str:
        return "\n".join(self.markdowns + self.captions + self.warnings + self.infos)


class _RegimeSpy:
    """假的 `get_macro_regime`；記錄呼叫次數（patch 失效必須看得出來）。"""

    def __init__(self, state: dict):
        self.state = state
        self.calls = 0

    def __call__(self) -> dict:
        self.calls += 1
        return self.state


def _loaded(regime: str) -> dict:
    return {"regime": regime, "light": "🟢", "source": "test", "trend_regime": None,
            "health": 60.0, "defense": False, "exposure_limit_pct": 70,
            "traffic_light": None, "is_loaded": True}


_UNLOADED = {"regime": "unknown", "light": "⬜", "source": "unloaded",
             "trend_regime": None, "health": None, "defense": False,
             "exposure_limit_pct": None, "traffic_light": None, "is_loaded": False}


def _score_row(sid: str, total: float, regime: str | None) -> dict:
    """`score_single_stock()` 輸出的最小子集（含它實際會回的 `regime` 戳記）。"""
    row = {"stock_id": sid, "stock_name": sid, "total": total, "grade": "B",
           "trend": 70, "momentum": 60, "chip": 55, "volume": 50, "risk": 45}
    if regime is not None:
        row["regime"] = regime
    return row


def _results(n: int) -> list[dict]:
    return [{"stock_id": f"S{i}", "代碼": f"S{i}", "名稱": f"N{i}",
             "健康度": 70, "357評價": "🟡合理"} for i in range(n)]


def _results_for(rows: list[dict]) -> list[dict]:
    """與 score rows 同代碼的批次結果（讓 stats 的分子分母對得上，避免假 0/0）。"""
    return [{"stock_id": r["stock_id"], "代碼": r["stock_id"], "名稱": r["stock_id"],
             "健康度": 70, "357評價": "🟡合理"} for r in rows]


@pytest.fixture
def fake_st(monkeypatch) -> _FakeSt:
    rec = _FakeSt()
    monkeypatch.setattr(SEC, "st", rec)
    return rec


@pytest.fixture
def regime_spy(monkeypatch) -> _RegimeSpy:
    spy = _RegimeSpy(dict(_UNLOADED))
    monkeypatch.setattr(SEC, "get_macro_regime", spy)
    return spy


def _weight_phrase(regime: str) -> str:
    """caption 裡「趨勢×0.30」那一段 —— 直接由 SSOT 生成，不手抄數字。"""
    return f"趨勢×{WEIGHT_TABLES[regime]['trend']:.2f}"


# ══════════════════════════════════════════════════════════════
# A. 「這批分數用了哪組權重」的判定（純函式）
# ══════════════════════════════════════════════════════════════
class TestBatchScoringRegime:

    @pytest.mark.parametrize("regime", ["bull", "neutral", "bear"])
    def test_reads_the_stamp_the_scorer_left(self, regime):
        rows = [_score_row("A", 80, regime), _score_row("B", 60, regime)]
        assert SEC._batch_scoring_regime(rows) == (regime, "")

    def test_no_stamp_refuses_to_declare(self):
        _reg, _why = SEC._batch_scoring_regime([_score_row("A", 80, None)])
        assert _reg is None and _why

    def test_mixed_stamps_refuse_and_name_both(self):
        rows = [_score_row("A", 80, "bull"), _score_row("B", 60, "bear")]
        _reg, _why = SEC._batch_scoring_regime(rows)
        assert _reg is None
        assert "bull" in _why and "bear" in _why

    def test_regime_without_weight_table_refuses(self):
        """`caution` 是 canonical regime，但 WEIGHT_TABLES 沒這個 key（H1 的潛伏坑）。"""
        assert "caution" not in WEIGHT_TABLES, "前提改變了，請重新確認本測試"
        _reg, _why = SEC._batch_scoring_regime([_score_row("A", 80, "caution")])
        assert _reg is None and "caution" in _why

    def test_empty_or_error_rows_refuse(self):
        assert SEC._batch_scoring_regime([])[0] is None
        assert SEC._batch_scoring_regime([{"stock_id": "A", "error": "無資料"}])[0] is None

    def test_never_returns_a_regime_without_weights(self):
        """不變量：能回出來的 regime 一定在 WEIGHT_TABLES 裡（caller 才敢直接索引）。"""
        for _r in ["bull", "neutral", "bear", "caution", "unknown", "", "BULL ", None]:
            _reg, _ = SEC._batch_scoring_regime([_score_row("A", 80, _r)])
            assert _reg is None or _reg in WEIGHT_TABLES, _r


# ══════════════════════════════════════════════════════════════
# B. caption 實際印出來的那一行
# ══════════════════════════════════════════════════════════════
class TestWeightCaption:

    @pytest.mark.parametrize("regime,other", [("bull", "neutral"), ("bear", "neutral"),
                                              ("neutral", "bull")])
    def test_caption_shows_the_weights_actually_used(self, fake_st, regime_spy,
                                                     regime, other):
        regime_spy.state = _loaded(regime)          # 目前總經＝同一個 → 不該有落差警示
        rows = [_score_row("A", 80, regime), _score_row("B", 60, regime)]
        SEC._render_multifactor_ranking(rows, {}, summarize_candidates(_results_for(rows), rows))
        _txt = fake_st.text
        assert _weight_phrase(regime) in _txt, _txt
        assert _weight_phrase(other) not in _txt, (
            f"caption 印出了 {other} 的權重，但這批分數是 {regime} 算的\n{_txt}")
        assert f"{regime} 權重" in _txt

    def test_caption_no_longer_hardcodes_neutral(self, fake_st, regime_spy):
        """回歸釘子：bull 批次不得再出現「neutral 權重」這句宣稱。"""
        regime_spy.state = _loaded("bull")
        rows = [_score_row("A", 80, "bull")]
        SEC._render_multifactor_ranking(rows, {}, summarize_candidates(_results_for(rows), rows))
        assert "neutral 權重" not in fake_st.text, fake_st.text

    def test_refuses_to_show_any_weights_without_a_stamp(self, fake_st, regime_spy):
        """說不出用了哪組 → 一個權重數字都不印（§1：不挑一組給人看）。"""
        rows = [_score_row("A", 80, None)]
        SEC._render_multifactor_ranking(rows, {}, summarize_candidates(_results_for(rows), rows))
        _txt = fake_st.text
        assert "趨勢×" not in _txt, _txt
        assert "沒有可宣告的加權權重" in _txt

    def test_warns_when_macro_moved_after_the_batch(self, fake_st, regime_spy):
        """跑完批次後總經才變 → 螢幕上的名次是舊 regime 算的，必須講。"""
        regime_spy.state = _loaded("bear")
        rows = [_score_row("A", 80, "bull"), _score_row("B", 60, "bull")]
        SEC._render_multifactor_ranking(rows, {}, summarize_candidates(_results_for(rows), rows))
        assert regime_spy.calls >= 1, "mock 沒被呼叫到 —— 這條測試等於沒驗"
        _warn = "\n".join(fake_st.warnings)
        assert "bull" in _warn and "bear" in _warn, _warn
        assert "重跑" in _warn

    def test_no_drift_warning_when_regime_unchanged(self, fake_st, regime_spy):
        regime_spy.state = _loaded("bull")
        rows = [_score_row("A", 80, "bull")]
        SEC._render_multifactor_ranking(rows, {}, summarize_candidates(_results_for(rows), rows))
        assert regime_spy.calls >= 1
        assert not fake_st.warnings, fake_st.warnings


# ══════════════════════════════════════════════════════════════
# C. 排行為空時的三態措辭
# ══════════════════════════════════════════════════════════════
_LOADING_WORDS = ("計算中", "載入中", "等待評分載入")


class TestEmptyRankingWording:

    def test_no_batch_run_yet(self, fake_st, regime_spy):
        SEC._render_multifactor_ranking([], {}, summarize_candidates([], []))
        _txt = fake_st.text
        assert "尚未執行批次分析" in _txt, _txt

    def test_macro_unevaluated_says_so_and_gives_the_fix(self, fake_st, regime_spy):
        """H1 之後最常見的空表原因 —— 它**不會**自己算完。"""
        SEC._render_multifactor_ranking([], {}, summarize_candidates(_results(3), []))
        assert regime_spy.calls >= 1, "mock 沒被呼叫到"
        _txt = fake_st.text
        assert "總經" in _txt and "未評估" in _txt, _txt
        assert "一鍵更新全部數據" in _txt
        for _w in _LOADING_WORDS:
            assert _w not in _txt, f"仍在暗示背景會算完：{_w}\n{_txt}"

    def test_really_no_scorable_stock(self, fake_st, regime_spy):
        """總經正常、但整批抓不到 K 線 —— 這是第三種，措辭要指向資料源而非總經。"""
        regime_spy.state = _loaded("bull")
        _why, _act = SEC._no_multifactor_reason(summarize_candidates(_results(3), []))
        assert regime_spy.calls >= 1, "mock 沒被呼叫到"
        assert "無法評分" in _why and "K 線" in _why, (_why, _act)
        assert "未評估" not in _why, "總經是好的，不該歸咎總經"
        SEC._render_multifactor_ranking([], {}, summarize_candidates(_results(3), []))
        _txt = fake_st.text
        assert "K 線" in _txt, _txt
        for _w in _LOADING_WORDS:
            assert _w not in _txt, f"{_w}\n{_txt}"

    def test_three_states_are_actually_different(self, monkeypatch, regime_spy):
        """自我對帳：三態必須產出三段不同的話，否則等於沒有三態。"""
        _msgs = []
        _msgs.append(SEC._no_multifactor_reason(summarize_candidates([], [])))
        _msgs.append(SEC._no_multifactor_reason(summarize_candidates(_results(3), [])))
        regime_spy.state = _loaded("bull")
        _msgs.append(SEC._no_multifactor_reason(summarize_candidates(_results(3), [])))
        assert len({m[0] for m in _msgs}) == 3, _msgs
        assert regime_spy.calls >= 2


class TestDimsWording:

    def test_dims_does_not_claim_it_is_still_loading(self, fake_st):
        """`_render_multifactor_dims` 只在 score_t3 已非空時被呼叫 ⇒ 空列＝算完且失敗。"""
        SEC._render_multifactor_dims([{"stock_id": "A", "error": "無資料"},
                                      {"stock_id": "B", "error": "無資料"}])
        _txt = fake_st.text
        assert _txt, "什麼都沒說 —— 使用者會以為畫面壞了"
        for _w in _LOADING_WORDS:
            assert _w not in _txt, f"{_w}\n{_txt}"


if __name__ == "__main__":   # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
