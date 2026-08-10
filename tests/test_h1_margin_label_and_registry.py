# -*- coding: utf-8 -*-
"""H1 ③④：融資卡 label 的手打門檻、與「ETF回測」那列永久紅燈。

③ `src/ui/render/macro_ui_components.margin_card`
   比較式吃 SSOT 常數、label 卻**手打**數字::

       label = ('🔴超過3400億高危' if margin > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI
                else ('⚡超過2500億警戒' if margin > MARGIN_BALANCE_WARN_THRESHOLD_YI ...

   → 有人調常數時，顏色會跟著變、字還在講舊數字，卡片當場開始說謊。
   本檔用 **monkeypatch 常數 → 重新呼叫 → 驗 label 跟著動** 的方式驗證，
   而不是去比對原始碼字面 —— 字面守衛照抄實作，永遠驗不出實作本身是錯的。

④ `data_registry_scanner` / `macro_registry_patch` 的「[ETF回測] 回測績效」註冊列
   ETF 回測分頁 v18.265 隨 `etf_tab_backtest.py` / `backtest_engine.py` 刪除，
   `etf_backtest_data` 全 repo 只有讀者、零寫入者 ⇒ 那一列在「🔍 資料診斷」頁
   **永遠是紅燈「缺」**。永遠觸發的警告等於沒有警告。
   本檔實際呼叫兩支 registry 產生器（餵 plain dict 當 session_state），
   斷言輸出裡不存在該 key —— 而且**連 `etf_backtest_data` 被塞滿資料時也不存在**
   （證明是「不再讀」而不是「只砍了 else 分支」）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
)

import src.services.data_registry_scanner as _scanner
import src.services.macro_registry_patch as _patch
import src.ui.render.macro_ui_components as _mui

_BACKTEST_PREFIX = "[ETF回測]"


# ══════════════════════════════════════════════════════════════
# ③ margin_card：label 必須由 SSOT 現算
# ══════════════════════════════════════════════════════════════
class TestMarginCardLabel:

    def test_red_band_label_quotes_the_ssot_number(self):
        html = _mui.margin_card(MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI + 1)
        assert f"{MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:.0f}" in html
        assert "高危" in html
        assert TRAFFIC_RED in html

    def test_yellow_band_label_quotes_the_ssot_number(self):
        html = _mui.margin_card(MARGIN_BALANCE_WARN_THRESHOLD_YI + 1)
        assert f"{MARGIN_BALANCE_WARN_THRESHOLD_YI:.0f}" in html
        assert "警戒" in html
        assert TRAFFIC_YELLOW in html

    def test_boundary_is_strictly_greater(self):
        """判定式是 `>`：剛好等於黃線 → 仍算安全水位（邊界方向一併釘住）。"""
        html = _mui.margin_card(MARGIN_BALANCE_WARN_THRESHOLD_YI)
        assert "安全水位" in html
        assert TRAFFIC_GREEN in html

    def test_label_follows_the_constant_not_a_hard_coded_string(self, monkeypatch):
        """**核心**：改常數 → label 立刻跟著改。

        舊碼寫死 '🔴超過3400億高危'，這條會失敗（label 仍講 3400）。
        """
        _fake_red = 9_999.0
        monkeypatch.setattr(
            _mui, "MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI", _fake_red)
        # mock 真的被用到嗎：把值調到 9999 之後，10000 才會進紅帶
        assert "高危" not in _mui.margin_card(9_000), (
            "monkeypatch 沒有生效 —— margin_card 沒有在呼叫時查模組全域常數"
            "（E2 掃出過 22 處失效 patch 但測試照樣綠）")
        html = _mui.margin_card(_fake_red + 1)
        assert "9999" in html, f"label 沒跟著常數走：{html}"
        assert "3400" not in html, (
            f"label 仍印著舊的硬編碼門檻，SSOT 沒接上：{html}")

    def test_yellow_label_follows_the_constant(self, monkeypatch):
        _fake_warn = 1_234.0
        monkeypatch.setattr(_mui, "MARGIN_BALANCE_WARN_THRESHOLD_YI", _fake_warn)
        assert "警戒" not in _mui.margin_card(_fake_warn - 1), "mock 未生效"
        html = _mui.margin_card(_fake_warn + 1)
        assert "1234" in html and "2500" not in html, html

    def test_format_is_unchanged_from_before_the_fix(self):
        """格式維持 `:.0f`（無千分位）—— 修改前後畫面字元完全相同，零位移。"""
        html = _mui.margin_card(MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI + 1)
        assert f"🔴超過{MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:.0f}億高危" in html
        html_y = _mui.margin_card(MARGIN_BALANCE_WARN_THRESHOLD_YI + 1)
        assert f"⚡超過{MARGIN_BALANCE_WARN_THRESHOLD_YI:.0f}億警戒" in html_y

    def test_none_and_garbage_still_degrade_honestly(self):
        """§1 回歸：None / 無法轉數字 → 「抓取中」卡片，不給任何水位結論。"""
        for bad in (None, "-", "", "n/a", object()):
            html = _mui.margin_card(bad)
            assert "抓取中" in html
            assert "安全水位" not in html and "高危" not in html


# ══════════════════════════════════════════════════════════════
# ④ registry：不得再登記已不存在的 ETF 回測
# ══════════════════════════════════════════════════════════════
def _fake_backtest_payload() -> dict:
    """一份「假裝回測真的跑過」的 payload —— 用來證明我們是**不再讀**這個 key。

    若只砍掉 else 分支而保留讀取，這份 payload 會讓 `[ETF回測]` 又長回來。
    """
    return {"cagr": 0.12, "weights": {"0050": 0.6, "00878": 0.4}}


def _base_state() -> dict:
    """最小可跑的 session_state（plain dict —— `load_section_inputs` 明確支援）。"""
    _df = pd.DataFrame({"date": pd.to_datetime(["2026-08-06", "2026-08-07"]),
                        "close": [100.0, 101.0]})
    return {
        "cl_data": {"intl": {}, "tw": {}, "tech": {}, "adl": _df,
                    "inst": {}, "margin": 2600.0},
        "cl_ts": "2026-08-07 17:00:00",
        "t2_data": None,
        "t3_data": {"results": [{"stock_id": "2330"}], "score_t3": []},
        "etf_single_data": {"ticker": "0050", "name": "元大台灣50",
                            "price_df": _df, "cur_yield": 3.2},
        "etf_portfolio_data": {"rows": [{"ticker": "0050"}]},
    }


def _rp_entry(df, cat, freq):
    return {"last_updated": "N/A", "rows": 0, "category": cat,
            "frequency": freq, "missing": True}


def _rp_scalar(v, cat, freq, proxy):
    return {"last_updated": proxy, "rows": 1 if v is not None else 0,
            "category": cat, "frequency": freq}


def _rp_ts(df):
    return "2026-08-07"


class TestNoDeadBacktestRegistryRow:

    @pytest.mark.parametrize("with_payload", [False, True])
    def test_patch_registry_never_emits_backtest_row(self, monkeypatch, with_payload):
        state = _base_state()
        if with_payload:
            state["etf_backtest_data"] = _fake_backtest_payload()
        monkeypatch.setattr(_patch.st, "session_state", state)

        _patch.patch_registry(
            intl_map={}, tw_map={}, tech_map={},
            rp_entry=_rp_entry, rp_scalar=_rp_scalar, rp_ts=_rp_ts)

        reg = state.get("data_registry")
        assert isinstance(reg, dict), (
            "patch_registry 沒有寫出 data_registry —— 它整段被 try/except 吞了，"
            "下面的斷言會變成空跑（測試必須先證明自己真的跑到）")
        assert "[ETF組合] 再平衡分析（1檔）" in reg, (
            "沒走到 ETF 區段，本測試的證據力不成立")
        _bad = [k for k in reg if k.startswith(_BACKTEST_PREFIX)]
        assert not _bad, f"又出現已刪功能的註冊列：{_bad}"

    def test_patch_registry_purges_stale_backtest_key(self, monkeypatch):
        """同 process 內殘留的舊 key 必須被清掉，不會卡在畫面上當永久紅燈。"""
        state = _base_state()
        state["data_registry"] = {
            "[ETF回測] 回測績效": {"last_updated": "N/A", "rows": 0,
                                   "category": "🏦 ETF / 基金",
                                   "frequency": "daily", "missing": True},
        }
        monkeypatch.setattr(_patch.st, "session_state", state)
        _patch.patch_registry(
            intl_map={}, tw_map={}, tech_map={},
            rp_entry=_rp_entry, rp_scalar=_rp_scalar, rp_ts=_rp_ts)
        assert not [k for k in state["data_registry"]
                    if k.startswith(_BACKTEST_PREFIX)]

    @pytest.mark.parametrize("with_payload", [False, True])
    def test_scanner_never_emits_backtest_row(self, monkeypatch, with_payload):
        state = _base_state()
        if with_payload:
            state["etf_backtest_data"] = _fake_backtest_payload()
        monkeypatch.setattr(_scanner.st, "session_state", state)

        _scanner.scan_and_write_data_registry(intl_map={}, tw_map={}, tech_map={})

        reg = state.get("data_registry")
        assert isinstance(reg, dict), (
            "scan_and_write_data_registry 沒有寫出 data_registry —— "
            "整段被 try/except 吞了，斷言會空跑")
        assert "[ETF組合] 再平衡分析（1檔）" in reg, (
            "沒走到 ETF 區段，本測試的證據力不成立")
        _bad = [k for k in reg if k.startswith(_BACKTEST_PREFIX)]
        assert not _bad, f"又出現已刪功能的註冊列：{_bad}"

    def test_backtest_session_key_still_has_no_writer(self):
        """前提複驗：`etf_backtest_data` 仍然零寫入者。

        （`tests/test_b6a_edu_doc_parity.py` 也有一份守衛；這裡再釘一次，
        因為一旦有人重新實作 ETF 回測，本批「拿掉註冊列」的前提就翻轉了，
        必須有測試把這件事講出來而不是讓註冊列默默缺席。）
        """
        import re
        repo = Path(__file__).resolve().parent.parent
        pat = re.compile(r"session_state\[['\"]etf_backtest_data['\"]\]\s*=(?!=)")
        # 只掃 production 樹（避開 .venv / site-packages / tests 這種會拖垮且無意義的路徑）
        candidates = [repo / "app.py"]
        for _sub in ("src", "shared", "scripts"):
            candidates += sorted((repo / _sub).rglob("*.py"))
        assert len(candidates) > 50, (
            f"只掃到 {len(candidates)} 個檔 —— 掃描範圍不對，本守衛等於空跑")
        writers = [
            str(p) for p in candidates
            if p.exists() and pat.search(p.read_text(encoding="utf-8",
                                                     errors="ignore"))
        ]
        assert not writers, (
            "etf_backtest_data 出現寫入者：\n" + "\n".join(writers)
            + "\n→ ETF 回測功能回來了？那就該把註冊列一起加回去。")
