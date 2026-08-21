"""src/services/portfolio_analysis_bridge.py — 組合管理持股 → ETF 組合分析 rows 橋接(v19.202)。

單一職責:把「📁 組合管理」載入的持股(戰情室 `_load_holdings_from_portfolio` 格式)
轉成 ETF 組合分析所需的 `etf_portfolio_rows` 契約 —— **不再靠手打的範例列 data_editor**。

背景(2026-08 稽核 + user 指派「輸入持股組合分析全移到戰情室」):
  原 `render_etf_portfolio` 的輸入是範例列 data_editor(0050/00713/BND/00878),與 📁 組合管理
  脫節 → 使用者得重打持股,不打則 葡萄串 / AI / portfolio_linkage / tab_sector_flow 全空轉。
  本橋接讓「唯一資料來源 = 📁 組合管理」貫穿到所有下游(維持 `etf_portfolio_rows` session key 契約)。

§1 誠實:缺張數/均價的持股(觀察清單候選、只填代號者)**不**產生分析列(無成本無法算再平衡/
市值),也不腦補;跳過並回報跳過數,交 caller 揭露。純函式、零 I/O、零 streamlit → 可單測。
"""
from __future__ import annotations

from dataclasses import dataclass

from src.compute.etf.etf_helpers import auto_role, normalize_etf_ticker


@dataclass(frozen=True)
class PortfolioRowsResult:
    """轉換結果:rows(etf_portfolio_rows 契約)+ 被跳過的持股(§1 揭露用)。"""
    rows: tuple[dict, ...]
    skipped: tuple[dict, ...]   # [{'ticker':..., 'reason':...}, ...]


def _num(v):
    """None / 非數字 / NaN → None;否則 float。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def build_portfolio_rows_from_holdings(holdings) -> PortfolioRowsResult:
    """戰情室持股 list → (rows, skipped)。

    Args:
        holdings: [{ticker, held, lots, avg_price, ...}, ...]
            (戰情室 `_load_holdings_from_portfolio` 輸出格式)。

    只納入 **持有(held 為真或未標)且 lots>0 且 avg_price>0** 的部位 —— 觀察清單候選
    (held=False / 無張數)不是實際持股,不進組合分析。回傳的 row 契約與
    `etf_tab_portfolio.render_etf_portfolio` 寫入 `etf_portfolio_rows` 者一致:
    `{ticker, lots, shares, avg_price, cost, target_pct_user, target_pct, role}`。
    """
    rows: list[dict] = []
    skipped: list[dict] = []
    for h in (holdings or []):
        if not isinstance(h, dict):
            continue
        _tk = normalize_etf_ticker(h.get('ticker'))
        if not _tk:
            skipped.append({'ticker': str(h.get('ticker', '')), 'reason': '代號空白/無法正規化'})
            continue
        # 觀察清單候選(held 明確為 False)不是實際持股 → 排除(不算成本/市值)
        if h.get('held') is False:
            skipped.append({'ticker': _tk, 'reason': '觀察清單候選(非持有)'})
            continue
        _lots = _num(h.get('lots'))
        _avg = _num(h.get('avg_price'))
        if _lots is None or _avg is None or _lots <= 0 or _avg <= 0:
            skipped.append({'ticker': _tk, 'reason': '缺張數/均價(§1 不腦補成本)'})
            continue
        _shares = _lots * 1000.0   # 1 張 = 1000 股(§4.1)
        rows.append({
            'ticker':          _tk,
            'lots':            _lots,
            'shares':          _shares,
            'avg_price':       _avg,
            'cost':            _shares * _avg,
            'target_pct_user': None,   # 組合管理未存目標比例(§1:不拿現況冒充目標)
            'target_pct':      None,
            'role':            auto_role(_tk),
        })
    return PortfolioRowsResult(rows=tuple(rows), skipped=tuple(skipped))
