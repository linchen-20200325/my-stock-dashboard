"""Phase 1 對稱性修法守衛(v19.197):A1 rf 冪等 / C4 P/B 同源 / C2 龍頭 gate / D2 單一抓取點。

皆離線(無網路):L1 純邏輯用 monkeypatch,UI 檔用原始碼掃描(避免 import streamlit UI)。
"""
from __future__ import annotations

import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


# ── A1:rf 注入責任歸位 + 單檔頁評分前注入(§5 冪等)────────────────────────
def test_a1_rf_inject_alias_identity():
    """ensure_etf_rf_injected 遷至中性 L3,grp_compare 保留 re-export → 同一物件。"""
    from src.services.etf_grp_compare_service import ensure_etf_rf_injected as _a
    from src.services.etf_scoring_service import ensure_etf_rf_injected as _b
    assert _a is _b


def test_a1_single_page_injects_rf_before_scoring():
    """單檔頁必須在 build_etf_score_row 前呼叫 ensure_etf_rf_injected(否則 Sharpe 不冪等)。"""
    s = _src("src/ui/etf/etf_tab_single.py")
    assert "ensure_etf_rf_injected()" in s
    assert s.index("ensure_etf_rf_injected()") < s.index("build_etf_score_row(ticker, df"), \
        "rf 注入必須在 build_etf_score_row 之前"


# ── C4:個股 P/B 單一源鏈(TWSE 官方 T1 → FinMind T2)──────────────────────
def test_c4_get_pb_ratio_twse_primary(monkeypatch):
    from src.data.stock import yield_pe_fetcher as ypf
    monkeypatch.setattr(ypf, "_twse_official_pbratio", lambda sid: 2.5)
    out = ypf.get_pb_ratio("2330", 250.0)
    assert out["pb"] == 2.5
    assert out["bps"] == pytest.approx(100.0)     # 250 / 2.5
    assert out["source"].startswith("TWSE")


def test_c4_get_pb_ratio_falls_back_to_bps(monkeypatch):
    from src.data.stock import yield_pe_fetcher as ypf
    monkeypatch.setattr(ypf, "_twse_official_pbratio", lambda sid: None)
    monkeypatch.setattr("src.data.core.fetch_bps", lambda sid: 20.0)
    out = ypf.get_pb_ratio("9999", 40.0)
    assert out["pb"] == pytest.approx(2.0)         # 40 / 20
    assert out["bps"] == 20.0
    assert out["source"].startswith("FinMind")


def test_c4_get_pb_ratio_both_missing_returns_none(monkeypatch):
    from src.data.stock import yield_pe_fetcher as ypf
    monkeypatch.setattr(ypf, "_twse_official_pbratio", lambda sid: None)
    monkeypatch.setattr("src.data.core.fetch_bps", lambda sid: 0.0)
    out = ypf.get_pb_ratio("0000", 40.0)
    assert out["pb"] is None                        # §1 不捏造


def test_c4_single_and_multi_share_official_source(monkeypatch):
    """單檔 helper 與多檔 get_pb_ratio 命中同一 TWSE 官方值 → 同股跨頁不再分歧(§2.1)。"""
    from src.data.stock import yield_pe_fetcher as ypf
    monkeypatch.setattr(ypf, "_twse_official_pbratio",
                        lambda sid: 3.14 if str(sid) == "2330" else None)
    # 多檔路徑
    assert ypf.get_pb_ratio("2330", 100.0)["pb"] == 3.14
    # 單檔路徑(delegator)
    from src.ui.tabs.stock_sections.section_357_valuation import _fetch_pbratio_from_twse
    assert _fetch_pbratio_from_twse("2330") == 3.14


# ── D2:P/B 抓取點唯一(多檔頁不得再自行 price/fetch_bps 算 P/B)──────────────
def test_d2_multi_page_routes_pb_via_ssot():
    s = _src("src/ui/tabs/stock_grp_sections/section_portfolio_summary.py")
    assert "get_pb_ratio" in s, "多檔頁 P/B 必須走 get_pb_ratio SSOT"
    # 不得再 import raw BPS fetcher 自行反推 P/B(繞過 TWSE 官方源) —— import 移除即定論
    assert "get_bps as fetch_bps" not in s, "多檔頁不得再 import get_bps 自算 P/B"


def test_d2_single_page_routes_pb_via_ssot():
    s = _src("src/ui/tabs/stock_sections/section_357_valuation.py")
    assert "_twse_official_pbratio" in s, "單檔頁 TWSE P/B 必須走 L1 SSOT"


# ── C2:多檔補股本 → 龍頭 gate 佔股本比(修「有值就當高」假陽性)───────────────
def test_c2_batch_uses_share_capital_and_leading_gates():
    s = _src("src/ui/tabs/stock_grp_sections/section_batch_fetcher.py")
    assert "fetch_share_capital" in s, "多檔批次必須補抓股本(龍頭 gate 分母)"
    assert "evaluate_leading_gates" in s, "多檔批次必須重用單檔龍頭 gate SSOT"
    assert "_cl_lead" in s and "_cx_lead" in s, "須輸出真判定 gate 鍵"
    # _cl_ok(has-value,health_inspector probe 用)語意不得被改成 lead
    assert "'_cl_ok':      bool(cl4 and cl4 > 0)" in s, "_cl_ok 應維持 has-value 語意"
