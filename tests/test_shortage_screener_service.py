"""tests/test_shortage_screener_service.py — 缺貨選股 L1 fetcher 解析 + L3 編排測試（v19.65）。

不觸網:monkeypatch finmind_get / batch fetcher，用合成 FinMind rows 驗解析與編排。
"""
from __future__ import annotations

import pandas as pd
import pytest


# ════════════════════════════════════════════════════════════════
# L1 fetcher：季報解析
# ════════════════════════════════════════════════════════════════
def _is_rows():
    return pd.DataFrame([
        {"date": "2025-03-31", "type": "Revenue", "origin_name": "營業收入合計", "value": 1000},
        {"date": "2025-03-31", "type": "CostOfGoodsSold", "origin_name": "營業成本", "value": 400},
        {"date": "2024-12-31", "type": "Revenue", "origin_name": "營業收入合計", "value": 900},
        {"date": "2024-12-31", "type": "GrossProfit", "origin_name": "營業毛利", "value": 500},
        {"date": "2024-12-31", "type": "CostOfGoodsSold", "origin_name": "營業成本", "value": 400},
    ])


def _bs_rows():
    return pd.DataFrame([
        {"date": "2025-03-31", "type": "x", "origin_name": "合約負債－流動", "value": 120},
        {"date": "2025-03-31", "type": "y", "origin_name": "合約負債－非流動", "value": 80},
        {"date": "2025-03-31", "type": "Inventories", "origin_name": "存貨", "value": 300},
        {"date": "2024-12-31", "type": "Inventories", "origin_name": "存貨", "value": 350},
    ])


def test_fetch_quarterly_shortage_frame_parses(monkeypatch):
    import src.data.stock.quarterly_financials_fetcher as qf

    def fake_get(dataset, **kw):
        if dataset == "TaiwanStockFinancialStatements":
            return _is_rows()
        if dataset == "TaiwanStockBalanceSheet":
            return _bs_rows()
        return pd.DataFrame()

    monkeypatch.setattr(qf, "finmind_get", fake_get)
    monkeypatch.setenv("FINMIND_TOKEN", "dummy")
    if hasattr(qf.fetch_quarterly_shortage_frame, "clear"):
        qf.fetch_quarterly_shortage_frame.clear()

    out = qf.fetch_quarterly_shortage_frame("2330")
    assert len(out) == 2
    q0 = out[0]  # 近→遠：2025Q1 在前
    assert q0["label"] == "2025Q1"
    assert q0["revenue"] == 1000
    assert q0["gross_profit"] == 600      # 毛利缺 → 用 營收−成本 補算
    assert q0["cogs"] == 400
    assert q0["contract_liab"] == 200     # 流動 120 + 非流動 80
    assert q0["inventory"] == 300
    q1 = out[1]  # 2024Q4：合約負債缺 → None
    assert q1["gross_profit"] == 500      # 直接有 GrossProfit
    assert q1["contract_liab"] is None


def test_fetch_frame_no_token_returns_empty(monkeypatch):
    import src.data.stock.quarterly_financials_fetcher as qf
    monkeypatch.delenv("FINMIND_TOKEN", raising=False)
    monkeypatch.delenv("FM_TOKEN", raising=False)
    if hasattr(qf.fetch_quarterly_shortage_frame, "clear"):
        qf.fetch_quarterly_shortage_frame.clear()
    assert qf.fetch_quarterly_shortage_frame("9999") == []


def test_sum_contract_liab_english_fallback():
    import src.data.stock.quarterly_financials_fetcher as qf
    rows = [{"date": "2025-03-31", "type": "ContractLiabilities",
             "origin_name": "", "value": 150}]
    assert qf._sum_contract_liab(rows) == {"2025-03-31": 150.0}


# ════════════════════════════════════════════════════════════════
# L3 service：候選池 + 金融股 + 端到端
# ════════════════════════════════════════════════════════════════
def _monthly_series(stock_id: str, values: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(values), freq="MS")
    return pd.DataFrame({"stock_id": stock_id, "date": dates, "revenue": values})


def _make_batch() -> pd.DataFrame:
    n = 18
    rising_fast = [100 + i * 8 for i in range(n)]   # 高斜率
    rising_slow = [100 + i * 3 for i in range(n)]   # 低斜率
    falling = [300 - i * 5 for i in range(n)]
    flat = [100] * n
    return pd.concat([
        _monthly_series("1001", rising_fast),
        _monthly_series("1002", rising_slow),
        _monthly_series("1003", falling),
        _monthly_series("1004", flat),
    ], ignore_index=True)


def test_candidate_pool_keeps_rising_sorted():
    from src.services.shortage_screener_service import _candidate_pool
    pool = _candidate_pool(_make_batch(), max_n=50)
    ids = [c["stock_id"] for c in pool]
    assert "1003" not in ids and "1004" not in ids   # 下跌/持平剔除
    assert set(ids) == {"1001", "1002"}
    # 依末月 YoY 降冪 → 高斜率在前
    assert pool[0]["last_yoy"] >= pool[1]["last_yoy"]


def test_is_finance_prefix():
    from src.services.shortage_screener_service import _is_finance
    assert _is_finance("2801") is True
    assert _is_finance("5876") is True
    assert _is_finance("2330") is False


def _strong_frame():
    def _q(rev, gp, cogs, cl, inv):
        return {"label": "Q", "date": "2025-01-01", "revenue": rev,
                "gross_profit": gp, "cogs": cogs, "contract_liab": cl, "inventory": inv}
    return [
        _q(1000, 600, 400, 200, 300), _q(1000, 550, 400, 160, 350),
        _q(1000, 540, 400, 150, 360), _q(1000, 530, 400, 150, 380),
        _q(1000, 500, 400, 150, 400), _q(1000, 500, 400, 140, 400),
        _q(1000, 500, 400, 140, 400), _q(1000, 500, 400, 140, 400),
    ]


def test_run_shortage_scan_survivor_path(monkeypatch):
    """主路徑：免費基本面存活池 → 逐檔單抓月營收 + 季報 → 計分。"""
    import src.services.shortage_screener_service as svc

    monkeypatch.setattr(svc, "_survivor_pool", lambda max_n: ["1001"])
    monkeypatch.setattr(svc, "fetch_quarterly_shortage_frame",
                        lambda sid, quarters=12: _strong_frame())
    monkeypatch.setattr(svc, "fetch_monthly_revenue",
                        lambda sid, months=18: _monthly_series(sid, [100 + i * 8 for i in range(18)]))
    if hasattr(svc._scan_cached, "clear"):
        svc._scan_cached.clear()

    rows, meta = svc.run_shortage_scan(name_map={"1001": "強缺貨A"})
    assert "存活池" in meta["pool_source"]
    assert meta["deep_scanned"] == 1
    assert rows and "🟥" in rows[0]["訊號強度"]
    assert rows[0]["名稱"] == "強缺貨A"


def test_run_shortage_scan_batch_fallback(monkeypatch):
    """存活池空 → fallback 全市場月營收批次。"""
    import src.services.shortage_screener_service as svc

    monkeypatch.setattr(svc, "_survivor_pool", lambda max_n: [])
    monkeypatch.setattr(svc, "fetch_batch_monthly_revenue", lambda months=18: _make_batch())
    monkeypatch.setattr(svc, "fetch_quarterly_shortage_frame",
                        lambda sid, quarters=12: _strong_frame())
    if hasattr(svc._scan_cached, "clear"):
        svc._scan_cached.clear()

    rows, meta = svc.run_shortage_scan()
    assert "月營收動能" in meta["pool_source"]
    assert meta["candidates"] == 2
    assert rows and "🟥" in rows[0]["訊號強度"]


def test_run_shortage_scan_all_sources_empty(monkeypatch):
    import src.services.shortage_screener_service as svc
    monkeypatch.setattr(svc, "_survivor_pool", lambda max_n: [])
    monkeypatch.setattr(svc, "fetch_batch_monthly_revenue", lambda months=18: pd.DataFrame())
    if hasattr(svc._scan_cached, "clear"):
        svc._scan_cached.clear()
    rows, meta = svc.run_shortage_scan()
    assert rows == []
    assert "sponsor" in meta["note"]


# ════════════════════════════════════════════════════════════════
# AI 三型建議 prompt（純函式）
# ════════════════════════════════════════════════════════════════
def test_build_shortage_ai_prompt():
    from src.services.shortage_screener_service import build_shortage_ai_prompt
    rows = [
        {"代碼": "2330", "名稱": "台積電", "缺貨分數": 100.0, "訊號強度": "🟥 強缺貨",
         "理由": "🟢合約負債YoY+33%", "_tier": "強缺貨"},
        {"代碼": "1590", "名稱": "亞德客", "缺貨分數": 45.0, "訊號強度": "🟧 中度",
         "理由": "🟡合約負債YoY+20%", "_tier": "中度"},
    ]
    p = build_shortage_ai_prompt(rows, top_n=10, news_text="測試新聞")
    assert "缺貨 / 供不應求選股候選清單" in p
    assert "2330 台積電" in p and "1590 亞德客" in p
    assert "積極型" in p and "穩健型" in p and "保守型" in p
    assert "45 天" in p or "事後驗證" in p          # 誠實揭露 section
    assert "測試新聞" in p


def test_build_shortage_ai_prompt_empty_rows():
    from src.services.shortage_screener_service import build_shortage_ai_prompt
    p = build_shortage_ai_prompt([], top_n=10)
    assert "沒有掃出" in p          # 空清單顯式標示，不炸
