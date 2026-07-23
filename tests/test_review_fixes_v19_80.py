"""tests/test_review_fixes_v19_80.py — 第三份外部 review 查證後修復守護。

TARGET:
- src/data/core/data_loader.py       (N2a 失敗不進快取 / N2c T86 負快取 /
                                      N3 _yf_dl env 引用計數 / N1 分母防呆 / N5 log)
- src/data/macro/leading_indicators.py (N4a 主源 try→備援 / N4b status 檢查)
- src/data/stock/app_stock_fetchers.py (N5 TWSE 股利備援 log)

查證裁決:N7 省成本說法機制錯誤(expander 收合不阻止 body 執行)/ N8 REFUTED
(flatten_snapshot 無 production caller 且 consumer .get() 安全)/ N10 已修
(v19.75+v19.78)— 詳 PR 描述。
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# N2a — 暫時性失敗不進 st.cache_data
# ══════════════════════════════════════════════════════════════
class TestNoNegativeCache:
    def test_transient_error_returns_tuple_via_wrapper(self, monkeypatch):
        from src.data.core.data_loader import StockDataLoader, _CombinedDataError

        def _boom(self, sid, days, use_adjusted=True):
            raise _CombinedDataError("系統錯誤: transient boom")

        monkeypatch.setattr(StockDataLoader, "_get_combined_data_cached", _boom)
        loader = StockDataLoader()
        out = loader.get_combined_data("2330", 60)
        # caller 介面不變:仍是 (None, err, None) 3-tuple
        assert out == (None, "系統錯誤: transient boom", None)

    def test_cached_inner_raises_not_returns_none_tuple(self):
        src = _src("src/data/core/data_loader.py")
        assert 'raise _CombinedDataError(f"系統錯誤: {str(e)}")' in src
        assert 'return None, f"系統錯誤: {str(e)}", None' not in src

    def test_loader_version_bumped(self):
        from src.data.core.data_loader import _LOADER_VERSION
        assert _LOADER_VERSION != "v2-raw-http-fallback"


# ══════════════════════════════════════════════════════════════
# N2c — T86 暫時性失敗改短 TTL 負快取(不永久釘空 dict)
# ══════════════════════════════════════════════════════════════
class TestT86NegativeCache:
    def test_transient_fail_uses_fail_ts_not_day_cache(self, monkeypatch):
        # B8-b v19.156:_get_t86_day + 其 _T86_DAY_CACHE/_T86_FAIL_TS 快取搬至
        # data_loader_inst_fetchers → patch/存取真正持有者模組。
        import src.data.core.data_loader_inst_fetchers as ifx
        calls = {"n": 0}

        def _none_fetch(*a, **k):
            calls["n"] += 1
            return None

        monkeypatch.setattr(ifx, "_fetch_url_dl", _none_fetch)
        ifx._T86_DAY_CACHE.pop("20990101", None)
        ifx._T86_FAIL_TS.pop("20990101", None)
        assert ifx._get_t86_day("20990101") == {}
        assert "20990101" not in ifx._T86_DAY_CACHE      # 不永久釘
        assert "20990101" in ifx._T86_FAIL_TS            # 負快取記錄
        # 負快取窗內第二次呼叫不重打
        assert ifx._get_t86_day("20990101") == {}
        assert calls["n"] == 1
        # 模擬過期 → 允許重試
        ifx._T86_FAIL_TS["20990101"] = time.time() - 10_000
        ifx._get_t86_day("20990101")
        assert calls["n"] == 2
        ifx._T86_FAIL_TS.pop("20990101", None)


# ══════════════════════════════════════════════════════════════
# P1 v19.159(團隊稽核 QA-Med)— TPEX 暫時性失敗改短 TTL 負快取
# (對稱補上 T86 早有、TPEX 一直漏的護欄;暫時性失敗不再永久釘空 dict)
# ══════════════════════════════════════════════════════════════
class TestTPEXNegativeCache:
    def test_transient_fail_uses_fail_ts_not_day_cache(self, monkeypatch):
        import src.data.core.data_loader_inst_fetchers as ifx
        calls = {"n": 0}

        def _none_fetch(*a, **k):
            calls["n"] += 1
            return None

        monkeypatch.setattr(ifx, "_fetch_url_dl", _none_fetch)
        ifx._TPEX_DAY_CACHE.pop("20990102", None)
        ifx._TPEX_FAIL_TS.pop("20990102", None)
        assert ifx._get_tpex_day("20990102") == {}
        assert "20990102" not in ifx._TPEX_DAY_CACHE     # 不永久釘(舊 bug:永久空快取)
        assert "20990102" in ifx._TPEX_FAIL_TS           # 負快取記錄
        # 負快取窗內第二次呼叫不重打
        assert ifx._get_tpex_day("20990102") == {}
        assert calls["n"] == 1
        # 模擬過期 → 允許重試(來源恢復後可重抓)
        ifx._TPEX_FAIL_TS["20990102"] = time.time() - 10_000
        ifx._get_tpex_day("20990102")
        assert calls["n"] == 2
        ifx._TPEX_FAIL_TS.pop("20990102", None)


# ══════════════════════════════════════════════════════════════
# N3 — _yf_dl os.environ 引用計數護欄(並行不互踩)
# ══════════════════════════════════════════════════════════════
class TestYfEnvRefcount:
    def test_parallel_downloads_env_stable_and_restored(self, monkeypatch):
        import src.data.core.data_loader as dl
        import src.data.stock as sds

        monkeypatch.setattr(sds, "_load_proxy_config",
                            lambda: {"https": "http://test-px:1"})
        seen: list = []

        def _fake_download(sym, **kw):
            seen.append(os.environ.get("HTTPS_PROXY"))
            time.sleep(0.05)   # 拉長交疊窗,重現原競態
            return "df"

        monkeypatch.setattr(dl.yf, "download", _fake_download)
        _old = os.environ.get("HTTPS_PROXY")
        ts = [threading.Thread(target=lambda: dl._yf_dl("TEST")) for _ in range(3)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        # 下載期間 env 恆為 proxy 值(舊版:同儕 finally 會中途拔掉)
        assert seen == ["http://test-px:1"] * 3
        # 全部離開後精確還原 + 深度歸零(舊版:晚進者備份到同儕設定值 → 外洩)
        assert os.environ.get("HTTPS_PROXY") == _old
        assert dl._YF_ENV_DEPTH == 0


# ══════════════════════════════════════════════════════════════
# N4 — leading_indicators 韌性
# ══════════════════════════════════════════════════════════════
class TestLeadingIndicatorsRobustness:
    @property
    def _li(self) -> str:
        return _src("src/data/macro/leading_indicators.py")

    def test_n4a_finmind_main_wrapped_falls_to_taifex(self):
        src = self._li
        assert "FinMind 主源失敗(走 TAIFEX 備援)" in src

    def test_n4b_taifex_post_checks_status(self):
        src = self._li
        assert "r.status_code == 200 and len(r.text) > 200" in src
        assert "\n            if len(r.text) > 200:\n                return r.text" not in src

    def test_taifex_fallback_no_silent_pass(self):
        src = self._li
        assert "pass  # TAIFEX 備援靜默失敗" not in src
        assert "TAIFEX 備援失敗" in src


# ══════════════════════════════════════════════════════════════
# N1 — 毛利率/稅後純益率分母防呆
# ══════════════════════════════════════════════════════════════
class TestGrossMarginDenominatorGuard:
    def test_all_three_sites_guarded(self):
        src = _src("src/data/core/data_loader.py")
        # gp 路徑 / 成本路徑 / 金融股稅後純益率 — 三處分母皆走 0→NaN
        assert src.count("N1 v19.80") >= 3
        assert "(gp / df_quarterly['營收'] * 100)" not in src
        assert "(net_income / pd.to_numeric(df_quarterly['營收'], errors='coerce') * 100)" not in src

    def test_zero_revenue_yields_nan_not_inf(self):
        rev = pd.Series([100.0, 0.0, 200.0])
        gp = pd.Series([40.0, 10.0, 80.0])
        out = (gp / pd.to_numeric(rev, errors="coerce").replace(0, float("nan")) * 100)
        assert pd.isna(out.iloc[1])
        assert not any(v == float("inf") for v in out.dropna())


# ══════════════════════════════════════════════════════════════
# N5 — 股利 TWSE 備援 / 產業別查詢 不再靜默
# ══════════════════════════════════════════════════════════════
class TestSilentExceptLogs:
    def test_dividend_twse_fallback_logs(self):
        src = _src("src/data/stock/app_stock_fetchers.py")
        assert "TWSE 備援失敗" in src

    def test_is_financial_stock_logs(self):
        src = _src("src/data/core/data_loader.py")
        assert "產業別查詢失敗(退前綴啟發式)" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
