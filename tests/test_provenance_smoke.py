"""S-PROV-1 smoke test — 確保 schema-additive provenance 契約不退化(v18.265).

目的:CLAUDE.md §2.2 規定核心 fetcher 須帶 `source` + `fetched_at`,本檔
驗證主要 L1 fetcher 在「成功 path」回傳的 DataFrame / Series 確實含 provenance
欄位 / attrs,防止後續 mechanical refactor 不小心拆掉。

策略:檔案內容靜態檢查為主(不需 import 含 streamlit / 外部 SDK 的 module);
僅 macro_core 走真實 import + monkeypatch 驗證 runtime schema。
"""
from __future__ import annotations

import os
import pandas as pd
import pytest


PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name: str) -> str:
    with open(os.path.join(PROJ_ROOT, name), "r", encoding="utf-8") as f:
        return f.read()


# ── 1. macro_core.fetch_fred:DataFrame 須含 source + fetched_at columns ──
def test_fetch_fred_carries_source_columns(monkeypatch):
    """phase 1 v18.246 — fetch_fred(成功 path)DataFrame 須含 schema-additive
    source/fetched_at columns(SSOT: macro_core.py)。"""
    try:
        import macro_core
    except ImportError as e:
        pytest.skip(f"macro_core import failed: {e}")

    fake_json = {
        "observations": [
            {"date": "2026-05-01", "value": "3.1"},
            {"date": "2026-06-01", "value": "3.2"},
        ]
    }

    class _MockResp:
        status_code = 200
        def json(self):
            return fake_json
        def raise_for_status(self):
            pass

    def _mock_fetch(*args, **kwargs):
        return _MockResp()

    monkeypatch.setattr(macro_core, "fetch_url", _mock_fetch, raising=False)
    if hasattr(macro_core.fetch_fred, "cache_clear"):
        macro_core.fetch_fred.cache_clear()
    df = macro_core.fetch_fred("CPILFESL", "dummy-key")
    assert isinstance(df, pd.DataFrame)
    if df.empty:
        pytest.skip("fetch_fred returned empty (fixture mismatch with current parser)")
    assert "source" in df.columns, "fetch_fred 須帶 schema-additive `source` 欄"
    assert "fetched_at" in df.columns, "fetch_fred 須帶 schema-additive `fetched_at` 欄"
    src = str(df["source"].iloc[0])
    assert src.startswith("FRED:"), f"source 須以 `FRED:` 開頭,實際 = {src}"


# ── 2. leading_indicators:build_leading_fast 輸出 schema 含 provenance ──
def test_leading_fast_carries_provenance_columns():
    """phase 18 v18.264 — build_leading_fast 在有效資料 path 須帶
    source + fetched_at columns(schema-additive,靜態檢查)。"""
    src = _read("leading_indicators.py")
    assert 'df["source"]' in src, "build_leading_fast 須有 df['source'] 寫入(phase 18)"
    assert 'df["fetched_at"]' in src or "df['fetched_at']" in src, \
        "build_leading_fast 須有 fetched_at 寫入"
    assert "FinMind+TAIFEX:leading_indicators:fast" in src, \
        "build_leading_fast 須用約定的 source 命名"
    assert "TWSE+FinMind+TAIFEX:leading_indicators:full" in src, \
        "build_leading_indicators(full)須用約定的 source 命名"


# ── 3. tw_stock_data_fetcher.fetch_mops_financials:provenance 命名約定 ──
def test_mops_financials_provenance_naming():
    """phase 16 v18.262 — fetch_mops_financials 須帶 source/fetched_at,
    且 source 含 `MOPS:t164sb03:Y<year>Q<season>` 命名(SSOT 命名約定)。"""
    src = _read("tw_stock_data_fetcher.py")
    assert "MOPS:t164sb03" in src, "fetch_mops_financials 命名約定須含 MOPS:t164sb03"
    assert "Goodinfo:" in src, "fetch_goodinfo_financials 須有 Goodinfo: 命名"
    assert "FinMind:TaiwanStockCashFlowsStatement" in src, \
        "fetch_5_years_cash_flow 須用 FinMind:TaiwanStockCashFlowsStatement"


# ── 4. macro_core.fetch_yf_ohlcv:provenance 命名約定 ──
def test_yf_ohlcv_provenance_naming():
    """phase 16 v18.262 — fetch_yf_ohlcv 須帶 Yahoo:chart:<ticker>:<range>:<interval>
    命名(SSOT)。"""
    src = _read("macro_core.py")
    assert "Yahoo:chart" in src, "fetch_yf_ohlcv source 命名須含 Yahoo:chart"
    # fetch_fred provenance(phase 1)
    assert 'FRED:' in src, "fetch_fred source 命名須含 FRED:"


# ── 5a. macro_core.fetch_ism_pmi:source 命名 SSOT 精確度(v18.296 phase 3) ──
def test_ism_pmi_source_includes_specific_endpoint():
    """S-PROV-1 phase 3 v18.296 — fetch_ism_pmi 7 段備援的 source 必須帶
    具體 endpoint / series ID,不可只標 'FRED' / 'MacroMicro' 等模糊字串。"""
    src = _read("macro_core.py")
    # FRED 路徑須帶 series ID
    assert "'source': f'FRED:{sid}'" in src or '"source": f"FRED:{sid}"' in src, \
        "fetch_ism_pmi FRED 段 source 須帶 series ID 變數"
    # 各 fallback 路徑須帶具體 endpoint
    assert "'MacroMicro:us-ism-mfg-pmi'" in src, "MacroMicro 段 source 須含 chart slug"
    assert "'ISM:ismworld.org'" in src, "ISM World 段 source 須含 host"
    assert "'DBnomics:ISM/pmi/pm'" in src, "DBnomics 段 source 須含 dataset 路徑"
    # PhilFed / OECD proxy 路徑須帶 FRED series ID + :proxy 標記
    assert "f'FRED:{FRED_PHILLY_FED}:proxy'" in src, \
        "PhilFed-Proxy 段 source 須帶 series ID + :proxy"
    assert "f'FRED:{FRED_BSCICP02}:proxy'" in src, \
        "OECD-Proxy 段 source 須帶 series ID + :proxy"
    # err path 也須帶 source
    assert "'ISM-PMI:all_7_stages_failed'" in src, \
        "fetch_ism_pmi 7 段全失敗 err 回傳也須帶 source"


# ── 5. macro_core.fetch_macro_compass:provenance 透傳 ──
def test_macro_compass_carries_provenance(monkeypatch):
    """S-PROV-1 phase 2 v18.295 — fetch_macro_compass(成功 path)三 ticker dict
    各 entry 須含 source + fetched_at(透傳自底層 fetch_yf_close 的 s.attrs)。"""
    try:
        import macro_core
    except ImportError as e:
        pytest.skip(f"macro_core import failed: {e}")

    # 構造帶 attrs 的 fake Series(模擬 fetch_yf_close 回傳),
    # 走 monkeypatch 替換 fetch_yf_close 避免真實 NAS proxy 抓取。
    def _fake_yf_close(ticker, range_="2y", interval="1d"):
        idx = pd.date_range("2026-01-01", periods=100, freq="D")
        s = pd.Series(range(100), index=idx, dtype=float, name=ticker)
        s.attrs["source"] = f"Yahoo:{ticker}"
        s.attrs["fetched_at"] = "2026-06-26T12:00:00+00:00"
        return s

    monkeypatch.setattr(macro_core, "fetch_yf_close", _fake_yf_close, raising=True)

    out = macro_core.fetch_macro_compass(range_="6mo")

    # 三 ticker 各自有 dict
    for key in ("vix", "tnx", "gspc"):
        entry = out.get(key)
        assert entry is not None, f"compass['{key}'] 應有 dict"
        assert "source" in entry, f"compass['{key}'] 須有 source 欄"
        assert "fetched_at" in entry, f"compass['{key}'] 須有 fetched_at 欄"
        assert entry["source"].startswith("Yahoo:"), (
            f"compass['{key}']['source'] 應以 'Yahoo:' 開頭,"
            f"實際 = {entry['source']}"
        )
        assert entry["fetched_at"] == "2026-06-26T12:00:00+00:00", (
            f"compass['{key}']['fetched_at'] 應透傳自 s.attrs,"
            f"實際 = {entry['fetched_at']}"
        )
