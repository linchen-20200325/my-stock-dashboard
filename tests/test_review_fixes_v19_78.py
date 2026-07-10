"""tests/test_review_fixes_v19_78.py — 第二份外部 review 查證後修復的守護測試。

TARGET:
- src/config/data_config.py            (S6/S14 HTTP timeout SSOT)
- src/data/core/data_loader.py         (S6 SDK timeout / S7 session 複用 / S8 UA / S11 去重)
- src/data/stock/app_stock_fetchers.py (S7 / S8)
- src/data/macro/macro_snapshot.py     (S7)
- src/data/proxy/proxy_helper.py       (S7 make_retry_session +429)
- src/data/macro/macro_core.py         (S9 cache 鎖)
- src/ui/tabs/stock_sections/section_health_score.py (S2 NaN MA 誤標)
- src/ui/tabs/tab_stock.py             (S3 IndexError / S4 nlargest / S5 動態視窗標籤)
- src/services/macro_registry_patch.py (S13 B5 條目保留)

查證裁決見 PR 描述;S1(CSS)v19.74 已修、S10(sidebar 重複)/S12(季報快取)/
S13 主張(股利缺監控)為誤判,細節見不修清單。
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# S6 / S14 — HTTP timeout SSOT + SDK 呼叫顯式逾時
# ══════════════════════════════════════════════════════════════
class TestHttpTimeoutSSOT:
    def test_constants_exist_and_sane(self):
        from src.config import HTTP_TIMEOUT_FINMIND_SDK_SEC, HTTP_TIMEOUT_YF_SEC
        assert isinstance(HTTP_TIMEOUT_FINMIND_SDK_SEC, int)
        assert isinstance(HTTP_TIMEOUT_YF_SEC, int)
        assert 5 <= HTTP_TIMEOUT_YF_SEC <= 60
        assert 10 <= HTTP_TIMEOUT_FINMIND_SDK_SEC <= 120

    def test_all_four_sdk_calls_pass_timeout(self):
        # FinMind SDK dataset 方法簽名 timeout=None → session.get(timeout=None)
        # = 無限等待;四個 SDK 呼叫點(daily/inst/margin/季報)必須顯式帶 SSOT 逾時
        src = _src("src/data/core/data_loader.py")
        assert src.count("timeout=HTTP_TIMEOUT_FINMIND_SDK_SEC") >= 4

    def test_yf_download_has_explicit_timeout(self):
        src = _src("src/data/core/data_loader.py")
        assert "kwargs.setdefault('timeout', HTTP_TIMEOUT_YF_SEC)" in src


# ══════════════════════════════════════════════════════════════
# S7 — session thread-local 複用 + 死碼 + Retry 429
# ══════════════════════════════════════════════════════════════
class TestSessionReuse:
    def test_bps_dl_same_thread_reuse(self):
        from src.data.core import data_loader as dl
        assert dl._bps_dl() is dl._bps_dl()

    def test_bps_dl_cross_thread_isolated(self):
        from src.data.core import data_loader as dl
        main_s = dl._bps_dl()
        got = {}
        t = threading.Thread(target=lambda: got.setdefault("s", dl._bps_dl()))
        t.start(); t.join()
        assert got["s"] is not main_s

    def test_twse_dl_dead_code_removed(self):
        from src.data.core import data_loader as dl
        assert not hasattr(dl, "_TWSE_DL")

    def test_app_stock_fetchers_session_reuse(self):
        from src.data.stock import app_stock_fetchers as asf
        assert asf._make_proxy_session() is asf._make_proxy_session()

    def test_macro_snapshot_session_reuse(self):
        from src.data.macro import macro_snapshot as ms
        assert ms._make_proxy_session() is ms._make_proxy_session()

    def test_proxy_helper_retry_covers_429(self):
        from src.data.proxy.proxy_helper import make_retry_session
        s = make_retry_session()
        fl = s.adapters["https://"].max_retries.status_forcelist
        assert 429 in fl and 503 in fl and 504 in fl


# ══════════════════════════════════════════════════════════════
# S8 — FinMind raw REST 補 User-Agent
# ══════════════════════════════════════════════════════════════
class TestFinmindRawUA:
    def test_helper_headers_with_token(self):
        from src.data.core.data_loader import _fm_raw_headers
        h = _fm_raw_headers("tok123")
        assert h.get("User-Agent") and "python-requests" not in h["User-Agent"]
        assert h.get("Authorization") == "Bearer tok123"

    def test_helper_headers_without_token_still_has_ua(self):
        from src.data.core.data_loader import _fm_raw_headers
        h = _fm_raw_headers("")
        assert h.get("User-Agent")
        assert "Authorization" not in h

    def test_no_more_bare_authorization_headers_in_data_loader(self):
        src = _src("src/data/core/data_loader.py")
        assert "headers={'Authorization': f'Bearer {_token}'} if _token else {}" not in src
        assert "headers={'Authorization':f'Bearer {_tok}'}" not in src

    def test_dividend_rest_uses_ua_helper(self):
        src = _src("src/data/stock/app_stock_fetchers.py")
        assert "_fm_hdrs_div(_get_finmind_token())" in src


# ══════════════════════════════════════════════════════════════
# S9 — macro_core cache 鎖(fetch_china_macro ThreadPool(5) 併發路徑)
# ══════════════════════════════════════════════════════════════
class TestMacroCoreCacheLocks:
    def test_locks_exist(self):
        from src.data.macro import macro_core as mc
        assert isinstance(mc._FRED_CACHE_LOCK, type(threading.Lock()))
        assert isinstance(mc._YF_CLOSE_CACHE_LOCK, type(threading.Lock()))

    def test_fetch_fred_concurrent_hammer_no_exception(self, monkeypatch):
        from src.data.macro import macro_core as mc

        class _FakeResp:
            def json(self):
                return {"observations": [
                    {"date": "2026-01-02", "value": "1.5"},
                    {"date": "2026-01-03", "value": "1.6"},
                ]}

        monkeypatch.setattr(mc, "fetch_url", lambda *a, **k: _FakeResp())
        mc._FRED_CACHE.clear()
        errs = []

        def _hammer():
            try:
                df = mc.fetch_fred("TESTSERIES", "test-key", 10)
                assert len(df) == 2
            except Exception as e:   # pragma: no cover - 失敗即記錄
                errs.append(e)

        ts = [threading.Thread(target=_hammer) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        mc._FRED_CACHE.clear()
        assert errs == []


# ══════════════════════════════════════════════════════════════
# S11 — 月營收「方案0」複製貼上冗餘已刪
# ══════════════════════════════════════════════════════════════
class TestMonthlyRevenueDedup:
    def test_only_one_raw_plan0_block(self):
        src = _src("src/data/core/data_loader.py")
        # raw REST 呼叫的 param dict 樣式僅存一份(方案B 走 finmind_get 不同樣式;
        # 其 log 前綴 [FM-Rev] 屬合法 fallback,不在斷言範圍)
        assert src.count("'dataset':'TaiwanStockMonthRevenue'") == 1
        assert src.count("[FM-Rev0]") >= 1   # 第一段方案0 保留


# ══════════════════════════════════════════════════════════════
# S2 — MA NaN 誤標「空箱整理」防護
# ══════════════════════════════════════════════════════════════
class TestHealthSectionNanMA:
    def test_notna_guards_present(self):
        src = _src("src/ui/tabs/stock_sections/section_health_score.py")
        assert "pd.notna(df2['MA20'].iloc[-1])" in src
        assert "pd.notna(df2['MA100'].iloc[-1])" in src
        assert "均線未成形" in src

    def test_nan_comparison_is_silent_false(self):
        # 文件化修復依據:price > NaN 靜默 False(這正是誤標機制)
        assert not (100.0 > float("nan"))


# ══════════════════════════════════════════════════════════════
# S3 / S4 / S5 — tab_stock 邊界修復
# ══════════════════════════════════════════════════════════════
class TestTabStockBoundaries:
    @property
    def _tab(self) -> str:
        return _src("src/ui/tabs/tab_stock.py")

    def test_s3_indexerror_covered(self):
        assert "except (ValueError, AttributeError, IndexError):" in self._tab

    def test_s3_empty_string_split_raises_indexerror(self):
        with pytest.raises(IndexError):
            _ = "".split()[0]

    def test_s4_nlargest_guard_present(self):
        src = self._tab
        assert "_red_k[_red_k['volume'].notna()].nlargest(1, 'volume')" in src
        assert "if not _top_red.empty:" in src

    def test_s4_all_nan_volume_filtered_pattern_is_empty(self):
        # 文件化修復依據:pandas 3.x nlargest 對全 NaN 會回含 NaN 的列(靜默選錯),
        # 舊版則回空 df(.iloc[0] IndexError)— 先 notna 過濾讓兩版行為統一為「空」
        df = pd.DataFrame({"close": [10.0, 11.0], "open": [9.0, 10.0],
                           "volume": [np.nan, np.nan]})
        assert df[df["volume"].notna()].nlargest(1, "volume").empty

    def test_s5_dynamic_window_label(self):
        src = self._tab
        assert "_win20_n = min(len(df2), 20)" in src
        assert "近{_win20_n}日壓力" in src
        assert "近{_win20_n}日支撐" in src
        assert "kpi('近20日壓力'" not in src


# ══════════════════════════════════════════════════════════════
# S13-adjacent — patch_registry 不再清掉 B5 監控條目
# ══════════════════════════════════════════════════════════════
class TestRegistryPatchKeepsB5:
    def test_b5_keep_suffixes_wired(self):
        src = _src("src/services/macro_registry_patch.py")
        assert "_b5_keep_suffixes" in src
        for kw in ("籌碼集中度", "股本", "5年現金流量允當比率"):
            assert kw in src

    def test_deletion_predicate_semantics(self):
        # 重現 patch 的刪除邏輯:B5 後綴保留,其餘 [個股] 刪除
        _b5_keep = (" | 籌碼集中度", " | 股本", " | 5年現金流量允當比率")
        rp = {
            "[個股] 2330 台積電 | 價格走勢": 1,
            "[個股] 2330 | 籌碼集中度": 2,
            "[個股] 2330 | 股本": 3,
            "[個股] 2330 | 5年現金流量允當比率": 4,
            "[總經] VIX": 5,
        }
        for k in list(rp.keys()):
            if k.startswith("[個股]") and k.endswith(_b5_keep):
                continue
            if k.startswith("[個股]"):
                del rp[k]
        assert "[個股] 2330 台積電 | 價格走勢" not in rp
        assert "[個股] 2330 | 籌碼集中度" in rp
        assert "[個股] 2330 | 股本" in rp
        assert "[個股] 2330 | 5年現金流量允當比率" in rp
        assert "[總經] VIX" in rp


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
