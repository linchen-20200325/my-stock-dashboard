"""tests/uit_fakes.py — UI-T（🎯 標的頁）測試共用的假資料與下毒／計次夾具（不是測試檔）。

做法比照 UI-M 先例：不碰網路，把 `page_find` / `page_inspect` 的 **loader**（它們是 L3 的唯一入口）與薄 L3
`target_industry_service` 換成「計次的假貨」。假貨回的是**真的 dataclass**（`ScreenResult`、`StockReadout`…），
所以頁面走的是真的 builder／renderer，不是替身 renderer。

`Calls` 記每個 loader 被呼叫幾次 ⇒ 操作隔離（C4）、冷啟動零 L3（C1）、失敗不重打（C5）都以它計次。
"""
from __future__ import annotations

import datetime as _dt
from collections import Counter
from typing import Any

import pandas as pd

from src.services.target_industry_service import TickerSectorMap
from src.ui.views import page_find as F
from src.ui.views import page_inspect as I

#: 三檔假候選：2330 個股（有產業、有 PE）、2317 個股（PE 缺）、2891 個股（產業對映缺）。
CANDIDATES = (("2330", "台積電", 88.5), ("2317", "鴻海", 71.0), ("2891", "中信金", 60.2))
PE = {"2330": 22.5, "2891": 11.0}                     # 2317 缺 PE（L1 已不放 key）
SECTOR_MAP = {"2330": "半導體業", "2317": "其他電子業"}  # 2891 不在對映
SECTORS = (
    {"sector": "半導體業", "x_yi": 120.5, "y_yi": 3.2, "size_yi": 300.0, "quadrant": "漲潮", "n_days": 20},
    {"sector": "航運業", "x_yi": -40.0, "y_yi": -2.0, "size_yi": 80.0, "quadrant": "退潮", "n_days": 20},
    {"sector": "生技醫療", "x_yi": None, "y_yi": None, "size_yi": None, "quadrant": "未取得",
     "unavailable": True, "n_days": 12},
    {"sector": "塑膠工業", "x_yi": 1.0, "y_yi": None, "size_yi": 5.0, "quadrant": "資料不足",
     "insufficient": True, "n_days": 3},
)


class Calls(Counter):
    """loader 名 → 呼叫次數。"""


def screen_df() -> pd.DataFrame:
    return pd.DataFrame({
        "代碼": [c[0] for c in CANDIDATES],
        "名稱": [c[1] for c in CANDIDATES],
        "綜合分": [c[2] for c in CANDIDATES],
        "估值分": [90.0, None, 40.0],
    })


def make_screen_result(req: Any, *, rows: int = 3, error: str = "", pe_n: int | None = 2,
                       factor_input_failed: tuple[str, ...] = ()) -> F.ScreenResult:
    if not req.submitted:
        return F.ScreenResult(requested=False)
    if error:
        return F.ScreenResult(requested=True, error=error, survivors_n=100, pe_n=pe_n, name_n=3,
                              factor_input_failed=factor_input_failed)
    _df = screen_df().head(rows)
    return F.ScreenResult(requested=True, df=_df, note="（總經為 caution：空頭濾網已套用）\n\n⚠️ 總經為 caution",
                          rows=len(_df), survivors_n=324, pe_n=pe_n, name_n=3,
                          hits=("估值 2/3",), factor_input_failed=factor_input_failed)


def make_flow(*, ok: bool = True, stale: bool = False, tpex_complete: bool | None = True,
              error: str = "") -> F.SectorFlowReadout:
    if error:
        return F.SectorFlowReadout(requested=True, error=error)
    if not ok:
        return F.SectorFlowReadout(requested=True, ok=False, reason="板塊資金快取尚未產生")
    return F.SectorFlowReadout(
        requested=True, ok=True, stale=stale, stale_reason=("上次更新距今 9.0 日" if stale else ""),
        sectors=SECTORS, highlight=("半導體業",), insufficient=("塑膠工業",),
        quadrant_counts=(("漲潮", 1), ("退潮", 1), ("資料不足", 1)), updated_at="2026-10-28T10:00:00+00:00",
        n_days="20", unavailable=("生技醫療",), tpex_complete=tpex_complete)


def make_heatmap(*, failed: bool = False) -> F.HeatmapReadout:
    if failed:
        return F.HeatmapReadout(requested=True, error="批次全失敗")
    return F.HeatmapReadout(requested=True, any_data=True, complete=True, fetched_n=10, sectors_n=10,
                            figure=None, single_stock_proxy=True, disclosure="台股側每個類股其實是一檔代表股")


def make_stock(*, score: float | None = 82.0, fail_items: tuple[str, ...] = ("負債比",)) -> I.StockReadout:
    return I.StockReadout(
        requested=True, score_pct=score, grade="A" if score is not None else "", headline="體質良好",
        fail_items=fail_items, trend_verdict={"verdict": "跨季穩定"}, name="台積電", price=900.0,
        price_asof=I.PAL.PriceAsOf(as_of=_dt.date(2026, 10, 28), src="yfinance"))


def make_chips(*, ok: bool = True) -> I.ChipsView:
    if ok:
        return I.ChipsView(requested=True, signal="🔥 大戶吸籌", concentration=6.3, days=20, pos_days=14,
                           rows=250, days_loaded=250, outlier_verdict="normal", outlier_ratio=0.2,
                           outlier_threshold=5.0, outlier_window=30)
    return I.ChipsView(requested=True, miss_reason="df缺法人/量欄", days_loaded=250, rows=250)


def make_valuation() -> I.ValuationReadout:
    return I.ValuationReadout(requested=True, est_yield_pct=5.5, zone_code="fair", signal="🟡 合理（5~7%）",
                              msg="合理區間", avg_div_twd=10.0, paying_years=5, source="FinMind", years_n=5,
                              price=900.0)


def make_profit() -> I.ProfitabilityReadout:
    return I.ProfitabilityReadout(requested=True, cells=(
        I.ProfitCell(key="gross_margin", label="毛利率", value_text="53.2%", label_text="好生意"),
        I.ProfitCell(key="operating_margin", label="營業利益率", value_text="42.0%", label_text="本業獲利"),
        I.ProfitCell(key="safety_margin", label="安全邊際", value_text="", label_text="")))


def make_etf() -> I.EtfReadout:
    return I.EtfReadout(requested=True, premium_pct=0.12, annual_yield_pct=4.2, peer_ranks={12: 0.2})


def install(monkeypatch: Any, calls: Calls, *, screen_error: str = "", flow: F.SectorFlowReadout | None = None,
            heatmap: F.HeatmapReadout | None = None, chips_ok: bool = True, stock_score: float | None = 82.0,
            sector_error: bool = False) -> None:
    """把所有 loader 換成計次假貨。`calls[name]` 就是該 loader 被呼叫的次數。"""
    def _screen(req):
        calls["screen"] += 1
        return make_screen_result(req, error=screen_error)

    def _pe():
        calls["pe"] += 1
        return dict(PE), {c[0]: c[1] for c in CANDIDATES}, "", ()

    def _sector():
        calls["sector"] += 1
        if sector_error:
            raise RuntimeError("ticker_sector.json 壞了")
        return TickerSectorMap(available=True, mapping=dict(SECTOR_MAP))

    def _flow(session, *, requested):
        calls["flow"] += 1
        return flow or make_flow()

    def _heat(*, requested):
        calls["heatmap"] += 1
        return heatmap or make_heatmap()

    def _stock(verdict):
        calls["stock"] += 1
        return make_stock(score=stock_score)

    def _val(verdict, stock):
        calls["valuation"] += 1
        return make_valuation()

    def _chips(verdict, req):
        calls["chips"] += 1
        return make_chips(ok=chips_ok)

    def _profit(verdict):
        calls["profit"] += 1
        return make_profit()

    def _etf(verdict):
        calls["etf"] += 1
        return make_etf()

    def _batch(req):
        calls["batch"] += 1
        if not req.submitted:
            return I.BatchReadout(requested=False)
        _rows = tuple(
            I.BatchRow(code=c, kind="stock" if c[0] != "0" else "etf", kind_label="個股" if c[0] != "0" else "ETF",
                       is_stock=c[0] != "0", is_etf=c[0] == "0", headline="體質良好",
                       metrics=(("財報體檢", "82 / 100"),),
                       price_asof=I.PAL.PriceAsOf(as_of=_dt.date(2026, 10, 28), src="yfinance"))
            for c in req.tickers) + (I.BatchRow(code="9999", kind="stock", kind_label="個股", is_stock=True,
                                                error="RuntimeError('FinMind 額度用罄')"),)
        return I.BatchReadout(requested=True, rows=_rows)

    monkeypatch.setattr(F, "load_screen_result", _screen)
    monkeypatch.setattr(F, "_load_pe_name_maps", _pe)
    monkeypatch.setattr(F, "load_sector_flow", _flow)
    monkeypatch.setattr(F, "load_heatmap", _heat)
    monkeypatch.setattr("src.services.target_industry_service.get_ticker_sector_map", _sector)
    monkeypatch.setattr(I, "load_stock_readout", _stock)
    monkeypatch.setattr(I, "load_valuation", _val)
    monkeypatch.setattr(I, "load_chips", _chips)
    monkeypatch.setattr(I, "load_profitability", _profit)
    monkeypatch.setattr(I, "load_etf_readout", _etf)
    monkeypatch.setattr(I, "load_batch_rows", _batch)


def page_app() -> None:
    """AppTest.from_function 用的腳本：只掛 🎯 標的頁（不含導覽殼）。"""
    from src.ui.views.page_target import render_page_target
    render_page_target()
