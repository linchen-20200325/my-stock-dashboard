"""src/compute/etf/etf_smart_analysis.py — ETF 標準差買賣帶 + 多維分散度分析（L2 純計算）。

職責（單一）：給定價格 DataFrame / 持股清單，回傳計算結果；無 I/O、無 Streamlit。

§8.2 分層：L2 Compute — 禁止 import requests / httpx / streamlit；
資料由 L5 UI 呼叫 L1 fetcher 後傳入。

分散度三維度：
  1. 價格相關係數（weight 0.4）：日報酬 Pearson corr；正規化 [-1,1] → [0,1]
  2. 持股重疊度（weight 0.4）：Jaccard similarity（top holdings set）
  3. 類別相似度（weight 0.2）：ETF_PEER_GROUPS 類別向量 cosine similarity

分散指數 = 1 - weighted_similarity；越高 = 與輸入 ETF 越不相關 = 越好的分散標的
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

# ── 標準差買賣帶 ─────────────────────────────────────────────────────────────

_BAND_LABELS = {
    'strong_buy':  ('強買點', '🟢🟢', '#16a085'),
    'buy':         ('買進參考', '🟢',   '#1abc9c'),
    'hold':        ('正常區間', '⚪',   '#586069'),
    'caution':     ('注意偏高', '🟡',   '#e67e22'),
    'sell':        ('考慮減碼', '🔴',   '#e74c3c'),
}


def compute_std_bands(
    price_series: pd.Series,
    window: int = 252,
) -> dict:
    """計算收盤價的標準差買賣帶。

    Parameters
    ----------
    price_series : pd.Series  日收盤價，index 為 DatetimeIndex，升序排列
    window       : int        滾動窗口（交易日），預設 252（約 1 年）

    Returns
    -------
    dict with keys:
        current      : float  最新收盤價
        mu           : float  rolling mean（最新）
        sigma        : float  rolling std（最新）
        upper_2s     : float  μ + 2σ
        upper_1s     : float  μ + 1σ
        lower_1s     : float  μ - 1σ
        lower_2s     : float  μ - 2σ
        pct_from_mu  : float  (current - mu) / mu × 100
        sigma_z      : float  (current - mu) / sigma（z-score）
        signal       : str    'strong_buy' | 'buy' | 'hold' | 'caution' | 'sell'
        signal_label : str    中文標籤
        signal_icon  : str    emoji
        signal_color : str    hex color
        series_mu    : pd.Series  rolling mean 序列（供畫圖）
        series_u2    : pd.Series  μ+2σ 序列
        series_u1    : pd.Series  μ+1σ 序列
        series_l1    : pd.Series  μ-1σ 序列
        series_l2    : pd.Series  μ-2σ 序列
        has_data     : bool
    """
    _empty = {'has_data': False}
    if price_series is None or len(price_series) < 20:
        return _empty

    s = price_series.dropna().sort_index()
    if len(s) < 20:
        return _empty

    _w = min(window, len(s))
    mu_s  = s.rolling(_w, min_periods=max(20, _w // 4)).mean()
    std_s = s.rolling(_w, min_periods=max(20, _w // 4)).std()

    current = float(s.iloc[-1])
    mu      = float(mu_s.iloc[-1])
    sigma   = float(std_s.iloc[-1])

    if mu == 0 or math.isnan(mu) or math.isnan(sigma) or sigma == 0:
        return _empty

    upper_2s = mu + 2 * sigma
    upper_1s = mu + 1 * sigma
    lower_1s = mu - 1 * sigma
    lower_2s = mu - 2 * sigma
    z = (current - mu) / sigma

    if z < -2:
        sig = 'strong_buy'
    elif z < -1:
        sig = 'buy'
    elif z <= 1:
        sig = 'hold'
    elif z <= 2:
        sig = 'caution'
    else:
        sig = 'sell'

    lbl, icon, color = _BAND_LABELS[sig]

    return {
        'has_data':    True,
        'current':     current,
        'mu':          mu,
        'sigma':       sigma,
        'upper_2s':    upper_2s,
        'upper_1s':    upper_1s,
        'lower_1s':    lower_1s,
        'lower_2s':    lower_2s,
        'pct_from_mu': (current - mu) / mu * 100,
        'sigma_z':     z,
        'signal':      sig,
        'signal_label':lbl,
        'signal_icon': icon,
        'signal_color':color,
        'series_mu':   mu_s,
        'series_u2':   mu_s + 2 * std_s,
        'series_u1':   mu_s + 1 * std_s,
        'series_l1':   mu_s - 1 * std_s,
        'series_l2':   mu_s - 2 * std_s,
    }


# ── ETF 分散度分析 ───────────────────────────────────────────────────────────

def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity（持股重疊度）。兩集合皆空時回 0。"""
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    inter = set_a & set_b
    return len(inter) / len(union) if union else 0.0


def _normalize_ticker(t: str) -> str:
    """統一 ticker 格式：字母後綴保留；數字串補 .TW。"""
    t = (t or '').strip()
    if not t:
        return t
    if '.' not in t:
        return f'{t}.TW'
    return t


def build_holdings_set(holdings, top_n: int = 15) -> set:
    """從 fetch_etf_holdings 回傳值建立代號 set（取前 N 檔）。

    容錯（§1）：list / DataFrame / dict / Series / None 皆安全,任何非預期格式都
    回傳能拿到的部分而非 raise（避免自動計算時單一 ETF 格式異常拖垮整個分散度區塊）。
    """
    if holdings is None:
        return set()
    # 統一成 list-of-record（DataFrame 先轉;其餘用 list() 強制迭代,失敗即空）
    if isinstance(holdings, pd.DataFrame):
        records = holdings.head(top_n).to_dict('records') if not holdings.empty else []
    else:
        try:
            records = list(holdings)[:top_n]
        except Exception:
            return set()
    codes: set[str] = set()
    for h in records:
        try:
            if isinstance(h, dict):
                sym = h.get('symbol') or h.get('Symbol') or h.get('code') or ''
            else:
                sym = str(h)
            sym = str(sym).strip().upper()
            if sym:
                codes.add(sym)
        except Exception:
            continue
    return codes


def _category_vector(ticker: str, groups: dict) -> list[float]:
    """回傳 ticker 在各類別的二元向量（長度 = len(groups)）。"""
    t = _normalize_ticker(ticker)
    v = [1.0 if t in peers else 0.0 for peers in groups.values()]
    return v


def _cosine(v1: list[float], v2: list[float]) -> float:
    """Cosine similarity，任一向量全零回 0。"""
    dot = sum(a * b for a, b in zip(v1, v2))
    n1  = math.sqrt(sum(a * a for a in v1))
    n2  = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


# 價格相關警示門檻(v19.63):分散指數是綜合的,可能掩蓋「價格其實高度同向」。
# 明細/圖旁標出來,避免只看分散指數被誤導(崩盤時高相關者仍會一起跌)。
PRICE_CORR_HIGH_WARN: float = 0.7


def price_corr_warn_label(price_corr) -> str:
    """價格相關(Pearson)→ 警示標籤。≥0.7 → '⚠️ 高度同向';否則 ''。純函式。"""
    if price_corr is None:
        return ''
    try:
        _pc = float(price_corr)
    except (TypeError, ValueError):
        return ''
    if _pc != _pc:  # NaN
        return ''
    return '⚠️ 高度同向' if _pc >= PRICE_CORR_HIGH_WARN else ''


def find_best_diversifiers(
    ticker: str,
    price_pivot: pd.DataFrame,
    holdings_map: dict[str, set],
    *,
    w_price: float = 0.40,
    w_holdings: float = 0.40,
    w_category: float = 0.20,
    top_n: int = 10,
) -> pd.DataFrame:
    """三維度分散度分析：找與 ticker 最不相關的前 top_n 檔 ETF。

    Parameters
    ----------
    ticker       : str   輸入 ETF（e.g. '0050.TW'）
    price_pivot  : pd.DataFrame  columns=tickers, index=date, values=Close
    holdings_map : dict[ticker → set of holding symbols]
    w_*          : float  各維度權重（合計應 = 1.0）
    top_n        : int    回傳排名

    Returns
    -------
    pd.DataFrame  欄位：ticker / 分散指數 / 價格相關 / 持股重疊 / 類別差異 / 可用維度
    空白 DataFrame 若資料不足。
    """
    from src.compute.etf.etf_categories import ETF_PEER_GROUPS  # noqa: PLC0415

    t = _normalize_ticker(ticker)
    if price_pivot.empty or t not in price_pivot.columns:
        return pd.DataFrame()

    # 日報酬矩陣
    ret = price_pivot.pct_change().dropna(how='all')
    if ret.empty or t not in ret.columns:
        return pd.DataFrame()

    # 相關係數（ticker vs 其他所有）
    corr_row = ret.corr()[t].drop(labels=[t], errors='ignore')

    # 類別向量
    cat_v_t = _category_vector(t, ETF_PEER_GROUPS)
    h_t     = holdings_map.get(t, set())

    rows: list[dict] = []
    for peer in corr_row.index:
        if peer == t:
            continue
        # 維度 1：價格相關（[-1,1] → 正規化 [0,1]，越低 = 越分散）
        pr = corr_row[peer]
        if not math.isfinite(pr):
            pr = 0.0
        pr_norm = (pr + 1) / 2  # 0=完全反向 best, 1=完全同向 worst

        # 維度 2：持股重疊（Jaccard, [0,1]，越低 = 越分散）
        h_p     = holdings_map.get(peer, set())
        jac     = _jaccard(h_t, h_p)
        has_h   = bool(h_t or h_p)

        # 維度 3：類別差異（cosine, [0,1]，越低 = 越分散）
        cat_v_p = _category_vector(peer, ETF_PEER_GROUPS)
        cat_sim = _cosine(cat_v_t, cat_v_p)

        # 若無持股資料，把持股權重分配給其他維度
        if has_h:
            _wp, _wh, _wc = w_price, w_holdings, w_category
        else:
            _total = w_price + w_category
            _wp = w_price / _total if _total else 0.5
            _wh = 0.0
            _wc = w_category / _total if _total else 0.5

        sim  = _wp * pr_norm + _wh * jac + _wc * cat_sim
        divs = round(1.0 - sim, 4)

        rows.append({
            'ticker':    peer,
            '分散指數':  divs,
            '價格相關':  round(pr, 3),
            '持股重疊%': round(jac * 100, 1) if has_h else None,
            '類別差異':  round(1.0 - cat_sim, 3),
            '可用維度':  3 if has_h else 2,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values('分散指數', ascending=False)
    return df.head(top_n).reset_index(drop=True)


def find_diversifiers_by_category(
    ticker: str,
    price_pivot: pd.DataFrame,
    holdings_map: dict[str, set],
    *,
    per_category: int = 10,
    w_price: float = 0.40,
    w_holdings: float = 0.40,
    w_category: float = 0.20,
) -> "dict[str, pd.DataFrame]":
    """分散度分析按 ETF 大類分組:對全 universe 算分後,依 ETF_PEER_GROUPS 各類取前 per_category。

    回傳 {類別名: DataFrame}（欄同 find_best_diversifiers,按分散指數降序）。
    同屬多類的 ETF 會出現在每個所屬類別;某類無成員入榜則不列該類。空 → {}。
    """
    from src.compute.etf.etf_categories import ETF_PEER_GROUPS  # noqa: PLC0415
    _full = find_best_diversifiers(
        ticker, price_pivot, holdings_map,
        w_price=w_price, w_holdings=w_holdings, w_category=w_category,
        top_n=10 ** 6,   # 取全部候選,後續按類別分組
    )
    if _full.empty:
        return {}
    t = _normalize_ticker(ticker)
    out: "dict[str, pd.DataFrame]" = {}
    for _cat, _members in ETF_PEER_GROUPS.items():
        _norm = {_normalize_ticker(m) for m in _members} - {t}
        _sub = _full[_full['ticker'].isin(_norm)].head(per_category).reset_index(drop=True)
        if not _sub.empty:
            out[_cat] = _sub
    return out


# ── MK 3-3-3 原則篩選 ────────────────────────────────────────────────────────

def check_333_criteria(
    ticker: str,
    price_df: "pd.DataFrame | None",
    peer_prices: "pd.DataFrame | None" = None,
    *,
    min_years: float = 3.0,
    target_annualized: float = 0.07,
    peer_top_pct: float = 1 / 3,
) -> dict:
    """MK 郭俊宏「3-3-3 原則」評估。

    C1: 成立 > 3 年（以最早可取得的價格資料推算）
    C2: 過去 3 年平均年化報酬率 > 7%（資料不足 2.5 年時回傳 None）
    C3: 同儕排名前 1/3（需傳入 peer_prices；未傳時回傳 None）

    Parameters
    ----------
    ticker           : str
    price_df         : pd.DataFrame  含 'Close' 欄，index 為 DatetimeIndex
    peer_prices      : pd.DataFrame  columns=ticker_list，index=date，values=Close
    min_years        : float  C1/C2 年限（預設 3.0）
    target_annualized: float  C2 目標年化報酬（預設 0.07 = 7%）
    peer_top_pct     : float  C3 前幾分位視為通過（預設 1/3）

    Returns
    -------
    dict 含：
        c1_age_years     : float | None   成立年數
        c1_pass          : bool  | None
        c2_return_3y     : float | None   3 年年化報酬率（小數，非 %）
        c2_pass          : bool  | None
        c3_peer_rank_pct : float | None   排名百分位（0=最好 ~ 1=最差）
        c3_pass          : bool  | None
        overall_pass     : bool  | None   三項全過；有任一明確 Fail → False
        criteria_count   : int            可計算項目數（最多 3）
    """
    result: dict = {
        'ticker': ticker,
        'c1_age_years': None, 'c1_pass': None,
        'c2_return_3y': None, 'c2_pass': None,
        'c3_peer_rank_pct': None, 'c3_pass': None,
        'overall_pass': None,
        'criteria_count': 0,
    }

    if price_df is None or (hasattr(price_df, 'empty') and price_df.empty):
        return result

    # ── 統一取 Close series ──────────────────────────────────────────────────
    if isinstance(price_df, pd.Series):
        px = price_df.dropna().sort_index()
    elif 'Close' in price_df.columns:
        px = price_df['Close'].dropna().sort_index()
    elif 'close' in price_df.columns:
        px = price_df['close'].dropna().sort_index()
    else:
        try:
            px = price_df.squeeze().dropna().sort_index()
        except Exception:
            return result

    if len(px) < 20:
        return result

    # 確保 index 為 tz-naive（避免比較時 type mismatch）
    if hasattr(px.index, 'tz') and px.index.tz is not None:
        px.index = px.index.tz_localize(None)

    today = pd.Timestamp.utcnow().tz_localize(None).normalize()

    # ── C1：成立年數 ─────────────────────────────────────────────────────────
    earliest = pd.Timestamp(px.index[0])
    if earliest.tzinfo is not None:
        earliest = earliest.tz_localize(None)
    age_years = (today - earliest).days / 365.25
    c1_pass = age_years >= min_years
    result.update({'c1_age_years': round(age_years, 2), 'c1_pass': c1_pass})
    result['criteria_count'] += 1

    # ── C2：3 年年化報酬率 ───────────────────────────────────────────────────
    three_yr_ago = today - pd.Timedelta(days=int(min_years * 365.25))
    try:
        idx_loc = px.index.searchsorted(three_yr_ago, side='left')
        idx_loc = min(idx_loc, len(px) - 1)
        start_ts = pd.Timestamp(px.index[idx_loc])
        if start_ts.tzinfo is not None:
            start_ts = start_ts.tz_localize(None)
        actual_years = (today - start_ts).days / 365.25
        sp = float(px.iloc[idx_loc])
        ep = float(px.iloc[-1])
        if actual_years >= 2.5 and sp > 0 and ep > 0:
            ann_ret = (ep / sp) ** (1.0 / actual_years) - 1.0
            c2_pass = ann_ret >= target_annualized
            result.update({'c2_return_3y': round(ann_ret, 4), 'c2_pass': c2_pass})
            result['criteria_count'] += 1
    except Exception:
        pass

    # ── C3：同儕排名 ─────────────────────────────────────────────────────────
    if peer_prices is not None and not (hasattr(peer_prices, 'empty') and peer_prices.empty):
        try:
            t_norm = _normalize_ticker(ticker)
            # 找目標欄位（帶 .TW 或不帶）
            if t_norm not in peer_prices.columns:
                t_short = t_norm.replace('.TW', '').replace('.TWO', '')
                candidates = [c for c in peer_prices.columns
                              if t_short == c.replace('.TW', '').replace('.TWO', '')]
                t_norm = candidates[0] if candidates else t_norm

            peer_ann_rets: dict[str, float] = {}
            ref_ago = today - pd.Timedelta(days=int(min_years * 365.25))
            for col in peer_prices.columns:
                s = peer_prices[col].dropna().sort_index()
                if len(s) < 100:
                    continue
                if hasattr(s.index, 'tz') and s.index.tz is not None:
                    s.index = s.index.tz_localize(None)
                li = min(s.index.searchsorted(ref_ago, side='left'), len(s) - 1)
                sp_p = float(s.iloc[li])
                ep_p = float(s.iloc[-1])
                st_ts = pd.Timestamp(s.index[li])
                if st_ts.tzinfo is not None:
                    st_ts = st_ts.tz_localize(None)
                ay = (today - st_ts).days / 365.25
                if ay >= 2.5 and sp_p > 0 and ep_p > 0:
                    peer_ann_rets[col] = (ep_p / sp_p) ** (1.0 / ay) - 1.0

            if peer_ann_rets and t_norm in peer_ann_rets:
                sorted_rets = sorted(peer_ann_rets.values(), reverse=True)  # best first
                my_ret = peer_ann_rets[t_norm]
                rank_0 = sorted_rets.index(my_ret)
                rank_pct = rank_0 / len(sorted_rets)  # 0=最好, 1=最差
                c3_pass = rank_pct <= peer_top_pct
                result.update({'c3_peer_rank_pct': round(rank_pct, 3), 'c3_pass': c3_pass})
                result['criteria_count'] += 1
        except Exception:
            pass

    # ── overall ─────────────────────────────────────────────────────────────
    passes = [result['c1_pass'], result['c2_pass'], result['c3_pass']]
    if all(p is not None for p in passes):
        result['overall_pass'] = all(passes)
    elif any(p is False for p in passes):
        result['overall_pass'] = False  # 有一項明確 Fail → 整體 Fail

    return result
