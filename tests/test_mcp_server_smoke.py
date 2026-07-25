"""tests/test_mcp_server_smoke.py — MCP server(無頭第二前端)首波守衛(v20)。

守的是「adapter 契約」,不重測 L3 選股邏輯(那有 fundamental_screener 自己的測試):
  1. server 模組可 import、`screen_stocks` 工具確實註冊進 FastMCP。
  2. `_df_to_records` JSON 序列化:NaN→None(§1 缺料留空**不填 0**)、numpy 純量→py 原生。
  3. fail-loud 契約:選股回空(季快照未就緒)→ ok=False + reason,**不編造清單**、不炸。
  4. 正常路徑:有資料 → ok=True + 記錄,NaN 因子欄仍為 None(非 0)。

全程 monkeypatch 隔絕網路(_build_pe_name_maps)與季快照(get_ranked_picks),
→ 快、確定性、不依賴 data_cache / 外部 API。
"""
from __future__ import annotations

import asyncio

import numpy as np
import pandas as pd
import pytest

# fastmcp 屬 MCP server 專用依賴(requirements-mcp.txt),**不在** requirements.txt。
# CI fast lane 只裝 requirements.txt → 此處整檔 graceful skip(對齊 test_position_ceiling
# 對 AppTest 缺席的處理);本機裝了 requirements-mcp.txt 才真跑。
pytest.importorskip("fastmcp")


# ── 1. 結構:模組 + 3 工具註冊 ───────────────────────────────────
def test_server_module_and_tools_registered():
    from fastmcp import FastMCP

    from mcp_server import server
    assert isinstance(server.mcp, FastMCP)
    for _name in ("screen_stocks", "forward_test_reconcile", "stock_health"):
        # fastmcp 3.x:get_tool(name) 為 coroutine,回 FunctionTool
        _tool = asyncio.run(server.mcp.get_tool(_name))
        assert getattr(_tool, "name", None) == _name
    assert callable(server._screen_stocks_impl)
    assert callable(server._forward_test_reconcile_impl)
    assert callable(server._stock_health_impl)


# ── 2. JSON 序列化:NaN→None、numpy→py ──────────────────────────
def test_df_to_records_nan_and_numpy():
    from mcp_server import server
    _df = pd.DataFrame({
        "代碼": ["2330", "2317"],
        "綜合分": [95.0, np.nan],          # NaN 必須 → None(不可變 0)
        "EPS分": [np.int64(88), np.int64(70)],  # numpy int → py int
    })
    recs = server._df_to_records(_df)
    assert recs[0]["代碼"] == "2330"
    assert recs[1]["綜合分"] is None                    # §1:缺料留空
    assert recs[0]["EPS分"] == 88 and isinstance(recs[0]["EPS分"], int)


# ── 3. fail-loud:選股回空 → ok=False,不編造 ───────────────────
def test_screen_stocks_fail_loud_when_empty(monkeypatch):
    import src.services.fundamental_screener_service as fss
    from mcp_server import server

    monkeypatch.setattr(server, "_build_pe_name_maps", lambda: ({}, {}))  # 斷網路
    monkeypatch.setattr(fss, "get_ranked_picks",
                        lambda *a, **k: (pd.DataFrame(), "季快照未就緒"))
    out = server._screen_stocks_impl(["eps_high"], 5)
    assert out["ok"] is False
    assert out["picks"] == []          # 不編造清單
    assert out["count"] == 0
    assert "季快照" in out["note"]


# ── 4. 正常路徑:有資料 → 記錄正確、缺料欄為 None ────────────────
def test_screen_stocks_returns_records(monkeypatch):
    import src.services.fundamental_screener_service as fss
    from mcp_server import server

    monkeypatch.setattr(server, "_build_pe_name_maps",
                        lambda: ({}, {"2330": "台積電"}))
    _df = pd.DataFrame({
        "代碼": ["2330", "2317"],
        "名稱": ["台積電", "鴻海"],
        "綜合分": [95.0, np.nan],
        "EPS分": [np.int64(88), np.int64(70)],
    })
    monkeypatch.setattr(fss, "get_ranked_picks", lambda *a, **k: (_df, ""))
    out = server._screen_stocks_impl(["eps_high"], 5)
    assert out["ok"] is True
    assert out["count"] == 2
    assert out["factors"] == ["eps_high"]
    assert out["picks"][0]["代碼"] == "2330"
    assert out["picks"][1]["綜合分"] is None       # NaN→None,不變 0
    assert "as_of" in out                          # provenance:抓取時間戳


# ── 4b. 非法 factor 過濾 + 全空 fallback 全 5 因子 ──────────────
def test_screen_stocks_invalid_factor_falls_back(monkeypatch):
    import src.services.fundamental_screener_service as fss
    from mcp_server import server

    _seen = {}

    def _fake(factors, **k):
        _seen["factors"] = factors
        return pd.DataFrame(), ""

    monkeypatch.setattr(server, "_build_pe_name_maps", lambda: ({}, {}))
    monkeypatch.setattr(fss, "get_ranked_picks", _fake)
    server._screen_stocks_impl(["bogus_factor"], 5)   # 全非法 → 應 fallback 全 5 因子
    assert _seen["factors"] == list(fss.SCREEN_ANGLE_LABELS.values())


# ── 5. forward_test_reconcile:有對帳資料 → numpy 經 _json_safe ──
def test_forward_test_reconcile_shape(monkeypatch):
    import src.services.forward_test_service as fts
    from mcp_server import server

    _df = pd.DataFrame({"cohort": ["2026-06-01"],
                        "pick_return_pct": [np.float64(4.2)],
                        "bench_return_pct": [1.8]})
    monkeypatch.setattr(fts, "reconcile_all",
                        lambda: (_df, {"n_cohorts": 1, "alpha_pct": np.float64(2.4)}))
    out = server._forward_test_reconcile_impl()
    assert out["ok"] is True
    assert out["cohorts"][0]["cohort"] == "2026-06-01"
    assert out["cohorts"][0]["pick_return_pct"] == 4.2      # numpy→py
    assert out["overall"]["alpha_pct"] == 2.4               # numpy→py(遞迴 _json_safe)


# ── 5b. forward_test_reconcile:無凍結 → ok=True + note,不偽造績效 ──
def test_forward_test_reconcile_empty(monkeypatch):
    import src.services.forward_test_service as fts
    from mcp_server import server

    monkeypatch.setattr(fts, "reconcile_all",
                        lambda: (pd.DataFrame(), {"n_cohorts": 0, "note": "尚無凍結選股紀錄"}))
    out = server._forward_test_reconcile_impl()
    assert out["ok"] is True
    assert out["cohorts"] == []                            # 空,不偽造 cohort
    assert "尚無" in out["overall"]["note"]


# ── 6. stock_health:空 id → ok=False ────────────────────────────
def test_stock_health_empty_id():
    from mcp_server import server
    out = server._stock_health_impl("")
    assert out["ok"] is False


# ── 6b. stock_health:財報 error → ok=False,不編造評級(§1)──────
def test_stock_health_fail_loud_on_error_findata(monkeypatch):
    import src.data.core.financial_statements_fetcher as ffs
    from mcp_server import server

    monkeypatch.setattr(ffs, "fetch_financial_statements",
                        lambda sid, token="": {"error": "FinMind quota 用罄"})
    out = server._stock_health_impl("2330")
    assert out["ok"] is False
    assert "quota" in out["error"]
    assert "grade" not in out          # §1:缺料不得產生體質評級(headless smoke 曾誤回 B+)


# ── 6c. stock_health:正常 → ok=True + grade ─────────────────────
def test_stock_health_happy(monkeypatch):
    import src.data.core.financial_statements_fetcher as ffs
    import src.services.financial_health_engine as fhe
    from mcp_server import server

    monkeypatch.setattr(ffs, "fetch_financial_statements",
                        lambda sid, token="": {"revenue": 100})   # 非 error
    monkeypatch.setattr(fhe, "analyze_financial_health",
                        lambda k, sid, fd, **kw: {"business_model_dna": "A+ 印鈔機"})
    monkeypatch.setattr(fhe, "no_ai_overall_verdict",
                        lambda fd, fh: {"grade": "A+", "score_pct": 90,
                                        "headline": "🟢 印鈔機", "comment": "體質堅實",
                                        "pass_items": ["氣長"], "fail_items": []})
    out = server._stock_health_impl("2330")
    assert out["ok"] is True
    assert out["stock_id"] == "2330"
    assert out["grade"] == "A+" and out["score_pct"] == 90
    assert out["business_model_dna"] == "A+ 印鈔機"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
