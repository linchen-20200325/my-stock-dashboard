# -*- coding: utf-8 -*-
"""I1 ③：抗跌 RS 排行為空時，note 不得把原因寫死。

修掉的原始碼（`src/services/rs_leader_service.py::_scan_cached`）::

    note = (f"⚠️ 掃描 {len(stocks)} 檔後無可排名標的：其中資料不足 {_insuff} 檔"
            f"（歷史 < lookback 或 yfinance 抓不到價）"
            + ("；且已勾選『只留贏過大盤』，此期間存活池全數未贏過大盤。" if beat_only else "。"))

兩句話都可能是假的：

  (a) H2（2026-08）之後 `calc_relative_strength` 在「大盤日報酬 σ ≤
      `RS_MARKET_SIGMA_MIN_PCT` 或 NaN」時回 `avg_rs=None` → `TIER_INSUFFICIENT`。
      那是**大盤側**的分母問題，個股歷史再長、yfinance 再正常也排不進去，
      而畫面卻叫使用者去查個股。
  (b) 一檔都沒被成功量測時，「此期間存活池全數未贏過大盤」是憑空生出來的**市場結論**
      —— 沒有人被量過，就不知道有沒有人贏。這比 (a) 嚴重：(a) 指錯方向，(b) 無中生有。

測試分三層：

  A. **這件事真的會發生** —— 用真的 L2（`rank_rs_leaders` / `count_insufficient`）
     證明「大盤 σ 不可用」確實產生一個全空排行 + 全檔資料不足（不是我假設的）。
  B. `_empty_scan_note()` 的歸因行為（建構輸入 → 呼叫 → 驗字串內容）。
  C. 走 `run_rs_leader_scan` 的實際接線（monkeypatch 抓價，不觸網）。

測資全部用固定日期（`2026-01-02` 起），**不吃執行當天日期**。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.services.rs_leader_service as SVC  # noqa: E402
from shared.rs_screen_thresholds import RS_MIN_ALIGNED_ROWS  # noqa: E402
from shared.signal_thresholds import RS_MARKET_SIGMA_MIN_PCT  # noqa: E402
from src.compute.screener.rs_leader_screener import (  # noqa: E402
    count_insufficient,
    rank_rs_leaders,
)

_LOOKBACK = 60
_N = 200


def _idx(n: int = _N) -> pd.DatetimeIndex:
    """固定日曆日 index —— 測資絕不吃「今天是哪天」。"""
    return pd.date_range("2026-01-02", periods=n, freq="D")


def _frozen_market(n: int = _N) -> pd.DataFrame:
    """凍結 / 停更的大盤：收盤價恆定 ⇒ 日報酬 σ = 0 ⇒ RS 的分母不成立。"""
    return pd.DataFrame({"close": [18_000.0] * n}, index=_idx(n))


def _live_market(n: int = _N, total_ret: float = -0.25, seed: int = 3) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    drift = (1 + total_ret) ** (1 / (n - 1)) - 1
    rets = np.r_[0.0, drift + rng.normal(0, 0.011, n - 1)]
    return pd.DataFrame({"close": 18_000.0 * np.cumprod(1 + rets)}, index=_idx(n))


def _stock(total_ret: float = 0.05, n: int = _N, seed: int = 11) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    drift = (1 + total_ret) ** (1 / (n - 1)) - 1
    rets = np.r_[0.0, drift + rng.normal(0, 0.014, n - 1)]
    return pd.DataFrame({"Close": 100.0 * np.cumprod(1 + rets)}, index=_idx(n))


def _det(base: float, cycle: list[float], n: int = _N, col: str = "close") -> pd.DataFrame:
    """完全確定性的序列（報酬率循環）。

    給「誰贏過誰」這類需要**必然成立**的測資用 —— 隨機噪音在 60 日視窗下有幾個 %
    的機率翻轉結論，那種測試會變成偶爾紅一次的鬼故事。循環報酬讓 σ > 0（RS 分母
    成立）但趨勢完全由 drift 決定。
    """
    rets = np.array([cycle[i % len(cycle)] for i in range(n)], dtype=float)
    rets[0] = 0.0
    return pd.DataFrame({col: base * np.cumprod(1 + rets)}, index=_idx(n))


def _pool(dfs) -> list[dict]:
    return [{"stock_id": f"S{i}", "name": "", "df": d} for i, d in enumerate(dfs)]


def _note(stocks, market, *, beat_only: bool = False, lookback: int = _LOOKBACK) -> str:
    return SVC._empty_scan_note(stocks, market, lookback=lookback, beat_only=beat_only)


# ══════════════════════════════════════════════════════════════
# A. 先證明「大盤 σ 不可用 → 全空排行」是真的會發生的路徑
# ══════════════════════════════════════════════════════════════
class TestTheSigmaPathIsReal:

    def test_frozen_market_makes_every_stock_insufficient(self):
        """真的 L2：大盤凍結 ⇒ 排行全空、且每一檔都被判「資料不足」。

        這條是本檔其餘斷言的**前提**。沒有它，下面測的只是我對訊息的想像。
        """
        stocks = _pool([_stock(0.10, seed=1), _stock(-0.05, seed=2), _stock(0.30, seed=3)])
        frozen = _frozen_market()
        assert rank_rs_leaders(stocks, frozen, lookback=_LOOKBACK) == []
        assert count_insufficient(stocks, frozen, lookback=_LOOKBACK) == len(stocks)

    def test_same_stocks_do_rank_against_a_live_market(self):
        """非空自證：同一批個股對上正常大盤是排得出來的 ⇒ 上一條不是測資本身壞掉。"""
        stocks = _pool([_stock(0.10, seed=1), _stock(-0.05, seed=2), _stock(0.30, seed=3)])
        live = _live_market()
        assert count_insufficient(stocks, live, lookback=_LOOKBACK) == 0
        assert len(rank_rs_leaders(stocks, live, lookback=_LOOKBACK)) == len(stocks)

    def test_market_baseline_probe_matches_that_split(self):
        """`_market_baseline_unusable` 必須跟上面兩條的結論一致（同一個判準，不是第二套）。"""
        assert SVC._market_baseline_unusable(_frozen_market(), _LOOKBACK) is True
        assert SVC._market_baseline_unusable(_live_market(), _LOOKBACK) is False


# ══════════════════════════════════════════════════════════════
# B. 歸因文字
# ══════════════════════════════════════════════════════════════
class TestEmptyScanNote:

    def test_sigma_failure_points_at_the_market_not_the_stocks(self):
        stocks = _pool([_stock(0.10, seed=1), _stock(0.02, seed=2)])
        note = _note(stocks, _frozen_market())
        assert "^TWII" in note and "大盤" in note, note
        assert f"{RS_MARKET_SIGMA_MIN_PCT:g}" in note, "σ 門檻要講出來（且取自 SSOT）"
        assert "資料不足" in note
        # 修前那句「歷史 < lookback 或 yfinance 抓不到價」的關鍵字不得出現
        assert "yfinance" not in note, f"仍把 σ 問題歸咎於抓價失敗：\n{note}"

    def test_no_price_case_counts_them_and_clears_the_market(self):
        stocks = _pool([None, None, None])
        note = _note(stocks, _live_market())
        assert "3 檔完全抓不到 K 線" in note, note
        assert "本身正常" in note, "大盤沒問題就要講，否則使用者不知道往哪查"
        assert "大盤日報酬標準差" not in note, f"誤報成 σ 問題：\n{note}"

    def test_short_history_case_says_aligned_days(self):
        stocks = _pool([_stock(0.1, n=10, seed=4), _stock(0.1, n=8, seed=5)])
        note = _note(stocks, _live_market())
        _need = max(_LOOKBACK, RS_MIN_ALIGNED_ROWS)
        assert "共同交易日" in note and str(_need) in note, note
        assert "0 檔完全抓不到 K 線" in note, note
        assert "資料不足" in note

    def test_never_claims_nobody_beat_the_market_when_nobody_was_measured(self):
        """(b) 的直接釘子：一檔都沒量到時，不得產出「全數未贏過大盤」這個結論。"""
        for _market in (_frozen_market(), _live_market()):
            stocks = _pool([None, None])
            note = _note(stocks, _market, beat_only=True)
            assert "全數未贏過大盤" not in note, note
            assert "無法" in note and "贏過大盤" in note, note

    def test_beat_only_filter_is_named_when_stocks_were_measured(self):
        """反面：真的量到了、只是沒人贏 —— 這時「0 檔贏過大盤」是可以斷言的事實。

        測資刻意用確定性序列：大盤每日 +0.2%/+0.1% 交替（σ>0 但趨勢向上）、
        個股每日 −0.3%/−0.2% 交替 ⇒ 60 日超額必為負，不靠隨機數碰運氣。
        """
        market = _det(18_000.0, [0.002, 0.001])
        stocks = _pool([_det(100.0, [-0.003, -0.002], col="Close")])
        assert count_insufficient(stocks, market, lookback=_LOOKBACK) == 0, "測資前提"
        assert rank_rs_leaders(stocks, market, lookback=_LOOKBACK,
                               beat_only=True) == [], "測資前提：beat_only 後應為空"
        note = _note(stocks, market, beat_only=True)
        assert "成功量測 1 檔" in note, note
        assert "贏過大盤" in note and "取消勾選" in note
        assert "抓不到 K 線" not in note, f"沒有抓價問題卻怪抓價：\n{note}"

    def test_note_is_never_empty(self):
        """任何一條路都要講話 —— 空字串等於畫面上一片沉默（§5）。"""
        for _stocks in ([], _pool([None]), _pool([_stock()])):
            for _mkt in (_frozen_market(), _live_market()):
                for _bo in (True, False):
                    assert _note(_stocks, _mkt, beat_only=_bo).strip()


# ══════════════════════════════════════════════════════════════
# C. 實際接線（run_rs_leader_scan，不觸網）
# ══════════════════════════════════════════════════════════════
def _patch_scan(monkeypatch, survivors, price_map, market: pd.DataFrame) -> dict:
    calls = {"pool": 0, "market": 0, "price": 0}

    def _pool_fn(max_n):
        calls["pool"] += 1
        return list(survivors)[:max_n]

    def _market_fn(_tk, range_="2y"):
        calls["market"] += 1
        return market["close"]                    # fetch_yf_close 回 Series

    def _price_fn(sid):
        calls["price"] += 1
        return price_map.get(sid), f"{sid}.TW"

    monkeypatch.setattr(SVC, "_survivor_pool", _pool_fn)
    monkeypatch.setattr(SVC, "fetch_yf_close", _market_fn)
    monkeypatch.setattr(SVC, "fetch_stock_history_1y", _price_fn)
    if hasattr(SVC._scan_cached, "clear"):
        SVC._scan_cached.clear()
    return calls


class TestWiredThroughService:

    def test_frozen_market_scan_blames_the_market(self, monkeypatch):
        _map = {"A": _stock(0.10, seed=1), "B": _stock(-0.02, seed=2)}
        calls = _patch_scan(monkeypatch, ["A", "B"], _map, _frozen_market())
        rows, meta = SVC.run_rs_leader_scan(lookback=_LOOKBACK)
        assert calls["market"] >= 1 and calls["price"] == 2, (
            f"monkeypatch 沒生效，測試可能打了真網路：{calls}")
        assert rows == []
        assert "^TWII" in meta["note"] and "大盤" in meta["note"], meta["note"]
        assert "yfinance" not in meta["note"], meta["note"]

    def test_all_missing_prices_scan_blames_the_fetch(self, monkeypatch):
        calls = _patch_scan(monkeypatch, ["A", "B"], {"A": None, "B": None},
                            _live_market())
        rows, meta = SVC.run_rs_leader_scan(lookback=_LOOKBACK)
        assert calls["price"] == 2, calls
        assert rows == []
        assert "2 檔完全抓不到 K 線" in meta["note"], meta["note"]
        assert "本身正常" in meta["note"]

    def test_beat_only_with_nothing_measured_makes_no_market_claim(self, monkeypatch):
        calls = _patch_scan(monkeypatch, ["A"], {"A": None}, _live_market())
        rows, meta = SVC.run_rs_leader_scan(lookback=_LOOKBACK, beat_only=True)
        assert calls["price"] == 1, calls
        assert rows == []
        assert "全數未贏過大盤" not in meta["note"], meta["note"]


if __name__ == "__main__":   # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
