"""shared/etf_ui_labels.py — ETF UI 指標「顯示標籤」單一權威(L0 SSOT,v19.166)。

問題:同一語意指標(含息報酬 / 現金殖利率 / 5年均殖…)在 ETF 單檔 / 多檔 / 組合三子頁
各叫不同名(「1Y累積%」vs「近1年含息總報酬」vs「1年含息報酬%」),使用者跨頁對不起來。
此檔把每個指標釘一個 canonical 中文標籤,三頁 `st.metric` / 欄名一律引此常數
(同 `shared/thresholds.py` 慣例)。

**只是「顯示字串」SSOT**,不含任何計算 / 門檻;值層 SSOT 仍在 `src/compute/etf/etf_calc.py`。
另把兩套同名「星等」正名:`quality_stars`(compute_etf_quality 4 因子)≠
`composite`(compute_etf_composite_score 7 維),避免使用者誤讀。
"""
from __future__ import annotations

ETF_METRIC_LABELS: dict[str, str] = {
    # ── 價 / 報酬 ──
    'close':           '收盤價',
    'total_ret_1y':    '近1年含息報酬',
    'cagr_3y':         '近3年CAGR',
    'sharpe':          '夏普值',
    'mdd':             '最大回撤MDD',
    # ── 配息 / 估值 ──
    'yield_ttm':       '現金殖利率(近12M)',
    'avg_yield_5y':    '近5年均殖',
    'valuation_zone':  '7%估值',
    'dividend_health': '配息健康',
    # ── 折溢價 / 追蹤 / 費用 / 規模 / 流動性 ──
    'premium':         '折溢價%',
    'tracking_error':  '追蹤誤差%',
    'expense':         '內扣費用率%',
    'beta':            'Beta(β)',
    'aum':             '規模AUM',
    'liquidity':       '流動性',
    # ── σ / 評分(兩套評分正名)──
    'sigma_z':         'σ位階',
    'quality_stars':   '體質星等',   # compute_etf_quality(4 因子)
    'composite':       '綜合評等',   # compute_etf_composite_score(7 維)
    'verdict':         '🚦建議',     # recommend_etf_action(留/觀察/換)
}


def etf_label(key: str, default: str | None = None) -> str:
    """取指標 canonical 顯示標籤;未登錄回 default(或 key 本身),不腦補。"""
    return ETF_METRIC_LABELS.get(key, key if default is None else default)
