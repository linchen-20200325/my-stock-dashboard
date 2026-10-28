"""xview V5：🔬 葉2 批次表 —— 個股「日線抓取失敗」與「查無資料」不得同顯示「—」。

修前 `_batch_row` 呼叫 `_fetch_metrics(code, kind)` 不帶 `failed=`：個股走 L3 best-effort，
暫時性失敗與查無資料都是 `current_price=None` → 同形「—」。修後個股傳 `failed=`，
日線抓取失敗 → 沿用既有整列錯誤狀態（`BatchRow.error`）；查無資料仍「—」。
ETF 不傳（ETF 拿不到日線本來就 raise → 已是整列紅）。財報腿失敗不在範圍（仍「—」）。
"""
from __future__ import annotations

import requests

import src.data.core.data_loader as DL
import src.services.dividend_station_service as DS
from src.compute.etf.asset_lag import ASSET_ETF, ASSET_STOCK, ASSET_UNKNOWN
from src.ui.views import page_inspect as P

_LABELS = {ASSET_STOCK: "個股", ASSET_ETF: "ETF", ASSET_UNKNOWN: "未知"}


def _row(code, kind):
    return P._batch_row(code, stock_kind=ASSET_STOCK, etf_kind=ASSET_ETF,
                        kind_labels=_LABELS, classify=lambda _c: kind,
                        benchmark_of=lambda _k: "0050")


def _price(row):
    return dict(row.metrics).get("現價")


# ── 第 1 層：L3 fetch_metrics 假件 ──────────────────────────────────
def test_stock_price_fetch_failure_is_an_error_row(monkeypatch):
    def _fm(code, kind, *, failed=None):
        assert failed is not None, "個股路徑必須傳 failed="
        failed[DS.FAILED_PRICE] = "ConnectionError: 429 transient"
        return {"current_price": None, "name": "台積電"}
    monkeypatch.setattr(DS, "fetch_metrics", _fm)
    r = _row("2330", ASSET_STOCK)
    assert not r.ok
    assert r.error == "ConnectionError: 429 transient"
    assert r.is_stock


def test_stock_no_data_stays_dash(monkeypatch):
    def _fm(code, kind, *, failed=None):
        assert failed is not None
        return {"current_price": None, "name": ""}   # 查無資料：不寫 failed
    monkeypatch.setattr(DS, "fetch_metrics", _fm)
    r = _row("2330", ASSET_STOCK)
    assert r.ok and r.error == ""
    assert _price(r) == "—"


def test_stock_statements_failure_out_of_scope_stays_dash(monkeypatch):
    """範圍守衛：財報腿失敗不轉整列紅（本修只處理現價腿）。"""
    def _fm(code, kind, *, failed=None):
        failed[DS.FAILED_STATEMENTS] = "fin 402"
        return {"current_price": 100.0, "name": "x", "mj_score_pct": None}
    monkeypatch.setattr(DS, "fetch_metrics", _fm)
    r = _row("2330", ASSET_STOCK)
    assert r.ok
    assert _price(r) == "100.00"


def test_etf_path_does_not_pass_failed(monkeypatch):
    seen = []

    def _fm(code, kind, **kw):
        seen.append(kw)
        return {"current_price": 50.0}
    monkeypatch.setattr(DS, "fetch_metrics", _fm)
    r = _row("0050", ASSET_ETF)
    assert seen == [{}]
    assert r.ok


# ── 第 2 層：走真 L3 `_fetch_stock_metrics`，只 stub L1 ───────────────
def _stub_l1(monkeypatch, combined):
    calls = []

    def _gcd(self, stock_id, days, use_adjusted=True, *, strict=False):
        calls.append(strict)
        return combined(strict)
    monkeypatch.setattr(DL.StockDataLoader, "get_combined_data", _gcd)
    import src.data.core.financial_statements_fetcher as FFS
    monkeypatch.setattr(FFS, "fetch_financial_statements",
                        lambda code, tok="", *, failed=None: {"error": "無財報"})
    return calls


def test_real_l3_transient_vs_no_data_are_distinguishable(monkeypatch):
    def _transient(strict):
        if strict:
            raise requests.ConnectionError("429 transient")
        return None, "暫時性失敗（best-effort 吞掉）", None
    calls = _stub_l1(monkeypatch, _transient)
    r_fail = _row("2330", ASSET_STOCK)
    assert calls == [True], "批次個股必須走 L1 strict（同一快取鍵／冷卻）"
    assert not r_fail.ok and "429 transient" in r_fail.error

    calls = _stub_l1(monkeypatch, lambda strict: (None, "❌ 查無資料", None))
    r_none = _row("2330", ASSET_STOCK)
    assert r_none.ok and _price(r_none) == "—"
    assert r_fail.error != r_none.error
