"""葡萄串領息法（Grape Ladder）— 高股息 ETF 月配組合最佳化

挑選不同除息月份的高股息 ETF 組成投組，讓每個月都有息可領。

兩個入口：
- recommend_income_ladder(): 從 etf_categories['高股息'] 10 檔自動挑最少 ETF cover 最多月
- evaluate_income_ladder(): 評估使用者輸入組合的月份覆蓋率與現金流

資料源：yfinance via etf_dashboard.fetch_etf_dividends（既有 cache）
"""
from __future__ import annotations
import datetime as _dt
from itertools import combinations
import pandas as pd
import streamlit as st

from src.compute.etf import ETF_PEER_GROUPS
from src.compute.etf.etf_dividend_schedule import classify_pay_frequency
from src.ui.etf import fetch_etf_dividends
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.dividend_frequency import PAY_FREQ_LABEL_MONTHLY
from shared.ttls import TTL_1DAY

# ── Constants ─────────────────────────────────────────────────
LOOKBACK_DAYS = 400         # 取近 ~13 月配息，給月配 ETF 偶缺一月緩衝
MAX_COMBO_SIZE = 5          # 暴力搜尋上限
MIN_PAYMENTS_FOR_VALID = 2  # 至少 2 次配息才算「有資料」
TARGET_MONTHS_FULL = 12

# 月配 ETF 清單（slider 排除選項用）
_MONTHLY_ETFS = {'00929.TW', '00940.TW', '00939.TW'}

# 12 月份中文名 SSOT（grid + 明細表共用）
_MONTH_NAMES = ['一月', '二月', '三月', '四月', '五月', '六月',
                '七月', '八月', '九月', '十月', '十一月', '十二月']


# ══════════════════════════════════════════════════════════════
# Pure Logic（無 Streamlit 副作用，可單測）
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def get_pay_months(ticker: str, lookback_days: int = LOOKBACK_DAYS) -> set[int]:
    """取得 ticker 近 lookback_days 內實際除息月份集合（1-12）。

    Returns
    -------
    set[int]  例：{1, 4, 7, 10}；資料不足或抓取失敗回 set()。
    """
    _divs = fetch_etf_dividends(ticker)
    if _divs is None or _divs.empty:
        return set()
    _cutoff = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=lookback_days))
    _recent = _divs[_divs.index >= _cutoff]
    if len(_recent) < MIN_PAYMENTS_FOR_VALID:
        return set()
    return set(_recent.index.month.tolist())


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def get_pay_profile(ticker: str, lookback_days: int = LOOKBACK_DAYS) -> dict:
    """近 lookback_days 除息 profile:{'months': set[int], 'n_payments': int}。

    比 get_pay_months 多回配息次數,供 classify_pay_frequency 判「月配」——用來區分
    「月配 ETF 新上市未滿一年、某月尚未觀察到除息」(待觀察)與「結構性缺月」(真缺口)。
    §1:資料不足(< MIN_PAYMENTS_FOR_VALID)/ 抓取失敗 → months 空 set、n_payments 0,不捏造。
    """
    _divs = fetch_etf_dividends(ticker)
    if _divs is None or _divs.empty:
        return {'months': set(), 'n_payments': 0}
    _cutoff = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=lookback_days))
    _recent = _divs[_divs.index >= _cutoff]
    if len(_recent) < MIN_PAYMENTS_FOR_VALID:
        return {'months': set(), 'n_payments': 0}
    return {'months': set(_recent.index.month.tolist()),
            'n_payments': int(len(_recent))}


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def get_avg_monthly_cash(ticker: str, shares: int = 1000) -> dict[int, float]:
    """{月份: 該月平均每股配息 × shares}。

    Returns
    -------
    dict[int, float]  缺月份不出現在 key 中。
    """
    _divs = fetch_etf_dividends(ticker)
    if _divs is None or _divs.empty:
        return {}
    _cutoff = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=LOOKBACK_DAYS))
    _recent = _divs[_divs.index >= _cutoff]
    if _recent.empty:
        return {}
    _by_month = _recent.groupby(_recent.index.month).mean()
    return {int(_m): round(float(_v) * shares, 2) for _m, _v in _by_month.items()}


def _score_combo(combo: tuple, month_map: dict[str, set[int]]) -> tuple[int, int]:
    """(覆蓋月數, -成員數) — tuple comparison 先比覆蓋、再比成員少。"""
    _covered = set().union(*(month_map[t] for t in combo))
    return (len(_covered), -len(combo))


def recommend_income_ladder(
    candidates: list[str] | None = None,
    target_months: int = TARGET_MONTHS_FULL,
    max_etfs: int = 4,
    min_etfs: int = 1,
    exclude_monthly: bool = False,
    min_stars: int = 1,
) -> dict:
    """暴力 itertools.combinations 搜尋最佳組合。

    Parameters
    ----------
    min_stars : int
        最低品質星等過濾門檻（1-5）。1 = 不過濾，3+ 用 etf_quality 預先剔除。

    Returns
    -------
    dict
      best_combo, covered_months, missing_months, coverage_pct,
      month_map, all_candidates_evaluated, skipped_tickers, low_quality, alternatives
    """
    _cands = list(candidates) if candidates else list(ETF_PEER_GROUPS.get('高股息', []))
    if exclude_monthly:
        _cands = [t for t in _cands if t not in _MONTHLY_ETFS]
    # 品質星等過濾（min_stars >= 2 才啟動，避免 1=不過濾時白抓）
    _low_quality: list[str] = []
    if min_stars >= 2:
        try:
            from src.compute.etf import compute_etf_quality
            _filtered: list[str] = []
            for _t in _cands:
                _q = compute_etf_quality(_t)
                _s = _q.get('stars') if _q else None
                if _s is None or _s >= min_stars:
                    # 未評等者保留（避免資料缺漏誤殺）
                    _filtered.append(_t)
                else:
                    _low_quality.append(_t)
            _cands = _filtered
        except Exception as _e_q:
            print(f'[grape_ladder/min_stars] ❌ {type(_e_q).__name__}: {_e_q}')
    # 抓每檔配息月份；空 set 視為無資料
    _month_map: dict[str, set[int]] = {}
    _skipped: list[str] = []
    for _t in _cands:
        _m = get_pay_months(_t)
        if _m:
            _month_map[_t] = _m
        else:
            _skipped.append(_t)
    _valid = list(_month_map.keys())
    if len(_valid) < min_etfs:
        return {
            'best_combo': [], 'covered_months': set(), 'missing_months': set(range(1, 13)),
            'coverage_pct': 0.0, 'month_map': {},
            'all_candidates_evaluated': 0, 'skipped_tickers': _skipped,
            'low_quality': _low_quality, 'alternatives': [],
            '_err': f'有效 ETF 僅 {len(_valid)} 檔，少於 min_etfs={min_etfs}',
        }
    _max_k = min(max_etfs, len(_valid), MAX_COMBO_SIZE)
    _best_score: tuple[int, int] | None = None
    _best_combo: tuple = ()
    _evaluated = 0
    _all_top: list[tuple] = []  # 同分組合
    for _k in range(min_etfs, _max_k + 1):
        for _combo in combinations(_valid, _k):
            _evaluated += 1
            _sc = _score_combo(_combo, _month_map)
            if _best_score is None or _sc > _best_score:
                _best_score = _sc
                _best_combo = _combo
                _all_top = [_combo]
            elif _sc == _best_score:
                _all_top.append(_combo)
    _best_covered = set().union(*(_month_map[t] for t in _best_combo))
    _missing = set(range(1, target_months + 1)) - _best_covered
    # 每月 → 哪幾檔配
    _by_month: dict[int, list[str]] = {}
    for _t in _best_combo:
        for _m in _month_map[_t]:
            _by_month.setdefault(_m, []).append(_t)
    # alternatives：除 best 外取前 3 個
    _alts = [list(_c) for _c in _all_top if _c != _best_combo][:3]
    return {
        'best_combo': list(_best_combo),
        'covered_months': _best_covered,
        'missing_months': _missing,
        'coverage_pct': round(len(_best_covered) / target_months * 100, 1),
        'month_map': _by_month,
        'all_candidates_evaluated': _evaluated,
        'skipped_tickers': _skipped,
        'low_quality': _low_quality,
        'alternatives': _alts,
    }


def evaluate_income_ladder(holdings: list[str]) -> dict:
    """評估「使用者持股」的月月領息覆蓋率（純函式，資料源＝get_pay_profile）。

    與 recommend_income_ladder 不同：**不做組合搜尋**，直接就 user 實際持有的
    tickers 逐檔取配息 profile（月份 + 次數），回傳覆蓋 / 缺口 / 待觀察 / 每月配息名單。
    §1 誠實原則：無配息歷史的 ETF（get_pay_profile 回空 months）→ 不貢獻任何月份、不捏造。

    Parameters
    ----------
    holdings : list[str]
        使用者持股 ticker（已含 .TW/.TWO 後綴，來自 st.session_state['etf_portfolio_rows']）。
        重複 ticker 會去重（保序）。

    Returns
    -------
    dict
      covered_months        : list[int]            有息覆蓋的月份（1-12，排序）
      gap_months            : list[int]            **結構性**缺月（未覆蓋且無月配新上市 ETF 會補）
      pending_months        : list[int]            待觀察缺月（月配 ETF 上市未滿一年，尚未觀察到該月除息）
      young_monthly_tickers : list[str]            造成 pending 的月配新上市 ETF（除息史未跨滿 12 月）
      month_map             : dict[int, list[str]] {月份: [該月配息的持股 tickers]}（排序）
      per_ticker            : dict[str, list[int]] {ticker: 該檔配息月份（排序）}
      no_data_tickers       : list[str]            無配息歷史（貢獻 0 月，誠實列出）
      coverage_pct          : float                len(covered)/12 * 100
      holdings_count        : int                  去重後持股數

    §1：pending_months **不塗綠**（未真的觀察到除息），只與結構性缺口區分——避免把「月配
    ETF 剛上市、某月還沒輪到」誤標成永久紅缺口 + 亂建議補檔。
    """
    # 去重保序 + 去空白
    _seen: set[str] = set()
    _holdings: list[str] = []
    for _raw in (holdings or []):
        _t = str(_raw).strip()
        if _t and _t not in _seen:
            _seen.add(_t)
            _holdings.append(_t)

    _month_map: dict[int, list[str]] = {}
    _per_ticker: dict[str, list[int]] = {}
    _no_data: list[str] = []
    _young_monthly: list[str] = []            # 月配但除息史未跨滿 12 月（新上市未滿一年）
    for _t in _holdings:
        _prof = get_pay_profile(_t)
        _months = _prof['months']
        if not _months:                       # §1：無配息歷史 → 不貢獻月份，不捏造
            _no_data.append(_t)
            _per_ticker[_t] = []
            continue
        _per_ticker[_t] = sorted(_months)
        for _m in _months:
            _month_map.setdefault(_m, []).append(_t)
        # 月配（≥PAY_FREQ_MONTHLY_MIN 次/年）但尚未觀察到全 12 月 → 新上市未滿一年
        if (classify_pay_frequency(_prof['n_payments']) == PAY_FREQ_LABEL_MONTHLY
                and len(_months) < TARGET_MONTHS_FULL):
            _young_monthly.append(_t)

    _covered = sorted(_month_map.keys())
    _uncovered = [_m for _m in range(1, 13) if _m not in _month_map]
    # 組合內若有「月配新上市」ETF → 該檔成熟後必覆蓋每一個月 → 目前未覆蓋月份皆屬「待觀察」，
    # 非結構性缺口（§1：不塗綠假裝已配，只把紅『缺口』改成黃『待觀察』並停止亂建議補檔）。
    if _young_monthly:
        _pending, _gap = _uncovered, []
    else:
        _pending, _gap = [], _uncovered
    return {
        'covered_months': _covered,
        'gap_months': _gap,
        'pending_months': _pending,
        'young_monthly_tickers': _young_monthly,
        'month_map': {_m: sorted(_ts) for _m, _ts in _month_map.items()},
        'per_ticker': _per_ticker,
        'no_data_tickers': _no_data,
        'coverage_pct': round(len(_covered) / TARGET_MONTHS_FULL * 100, 1),
        'holdings_count': len(_holdings),
    }


def suggest_fill_for_gaps(
    gap_months: list[int], exclude: list[str] | None = None,
) -> dict[int, str | None]:
    """為每個缺月，從 ETF_PEER_GROUPS['高股息'] 挑一檔「配息月份含該缺月」的 ETF。

    純函式，資料源＝get_pay_months（既有 cache 路徑）；找不到合適者回 None，不捏造。

    Parameters
    ----------
    gap_months : list[int]   欲補的缺月（1-12）。
    exclude    : list[str]   排除的 tickers（通常＝使用者現有持股，避免推薦已持有）。

    Returns
    -------
    dict[int, str | None]  {缺月: 建議補一檔 ticker 或 None}。
    """
    _exclude = {str(_t).strip() for _t in (exclude or [])}
    _cand_months: dict[str, set[int]] = {}
    for _cand in ETF_PEER_GROUPS.get('高股息', []):
        if _cand in _exclude:
            continue
        _cand_months[_cand] = get_pay_months(_cand)
    _suggest: dict[int, str | None] = {}
    for _gm in gap_months:
        _pick: str | None = None
        for _cand, _months in _cand_months.items():
            if _gm in _months:
                _pick = _cand
                break
        _suggest[_gm] = _pick
    return _suggest


# ══════════════════════════════════════════════════════════════
# UI Helpers
# ══════════════════════════════════════════════════════════════

def _render_month_grid(month_etfs: dict[int, list[str]],
                       pending: set[int] | None = None) -> None:
    """12 月份 3×4 grid；有配 → 綠底 + ETF chips；待觀察（月配新上市）→ 黃底 🕓；真缺月 → 紅底 ❌。

    綠/黃/紅由「該月是否在 month_etfs」+「是否 pending」決定；缺月即非上兩者（不需另傳缺月集）。
    """
    _pending = set(pending or set())
    for _row in range(3):
        _cols = st.columns(4)
        for _i in range(4):
            _m = _row * 4 + _i + 1
            with _cols[_i]:
                _etfs = month_etfs.get(_m, [])
                _has = bool(_etfs)
                if _has:
                    _bg, _border, _icon = '#0d2818', TRAFFIC_GREEN, '✅'
                elif _m in _pending:                       # 月配新上市未滿一年 → 待觀察
                    _bg, _border, _icon = '#1e1a00', TRAFFIC_YELLOW, '🕓'
                else:
                    _bg, _border, _icon = '#2d0e0e', TRAFFIC_RED, '❌'
                if _has:
                    _content = '<br>'.join(
                        f"<span style='background:#1f6feb22;color:#79c0ff;"
                        f"padding:2px 6px;border-radius:8px;font-size:10px;"
                        f"margin:2px 0;display:inline-block'>{_e}</span>"
                        for _e in _etfs)
                elif _m in _pending:
                    _content = '<span style="color:#d4a017">待觀察（新上市）</span>'
                else:
                    _content = '<span style="color:#8b949e">無 ETF</span>'
                st.markdown(
                    f"<div style='background:{_bg};border:1px solid {_border};"
                    f"border-radius:6px;padding:8px;min-height:80px'>"
                    f"<div style='color:#e6edf3;font-weight:700;font-size:12px'>"
                    f"{_icon} {_MONTH_NAMES[_m - 1]}</div>"
                    f"<div style='margin-top:4px;line-height:1.6'>{_content}</div>"
                    f"</div>", unsafe_allow_html=True)


def _render_holdings_coverage(holdings: list[str]) -> None:
    """主視圖：你的持股月月領覆蓋（由 st.session_state['etf_portfolio_rows'] 驅動）。"""
    st.markdown('##### 🍇 你的持股月月領覆蓋')
    st.caption('就你目前持有的 ETF 逐檔計算配息月份，看一年 12 個月哪些月領得到息、哪些月缺。')
    _res = evaluate_income_ladder(holdings)
    _covered = _res['covered_months']
    _gaps = _res['gap_months']
    _pending = _res.get('pending_months', [])
    _young = _res.get('young_monthly_tickers', [])

    _m1, _m2, _m3 = st.columns(3)
    _m1.metric('覆蓋月數', f'{len(_covered)}/12')
    _m2.metric('缺口月數', len(_gaps), help='結構性缺月（不含月配新上市的待觀察月）')
    _m3.metric('覆蓋率', f'{_res["coverage_pct"]}%')

    if _gaps:
        st.warning('⚠️ 缺月份：' + '、'.join(_MONTH_NAMES[_m - 1] for _m in _gaps))
    elif _pending:
        st.info(
            '🕓 待觀察月份：' + '、'.join(_MONTH_NAMES[_m - 1] for _m in _pending)
            + '。你持有的月配 ETF（' + '、'.join(_young)
            + '）上市未滿一年，這些月份只是**尚未觀察到**除息紀錄（去年還沒上市、今年還沒輪到），'
            '該檔滿一年後應會覆蓋 —— 屬待觀察、**非**永久缺口，故不建議為此補檔。')
    else:
        st.success('✅ 你的持股已覆蓋全部 12 個月，月月有息可領！')

    st.markdown('##### 📅 12 月份覆蓋圖（你的持股）')
    _render_month_grid(_res['month_map'], pending=set(_pending))

    st.markdown('##### 📋 每月配息明細')
    _tbl = [{
        '月份': _MONTH_NAMES[_m - 1],
        '檔數': len(_res['month_map'].get(_m, [])),
        '配息 ETF': '、'.join(_res['month_map'].get(_m, [])) or '—',
    } for _m in range(1, 13)]
    st.dataframe(pd.DataFrame(_tbl), use_container_width=True, hide_index=True)

    if _res['no_data_tickers']:
        st.caption('⚪ 無配息歷史（誠實不計入覆蓋）：'
                   + '、'.join(_res['no_data_tickers']))

    # ── 補缺建議（次要）：非你持股，僅供參考 ──
    if _gaps:
        st.markdown('##### 💡 建議補（非你持股）')
        _sugg = suggest_fill_for_gaps(_gaps, exclude=holdings)
        _srows = [{
            '缺月': _MONTH_NAMES[_gm - 1],
            '建議補一檔': _sugg.get(_gm) or '（高股息 10 檔中查無配該月）',
        } for _gm in _gaps]
        st.dataframe(pd.DataFrame(_srows), use_container_width=True, hide_index=True)
        st.caption('上表為「若想補齊該缺月，可從高股息 10 檔中考慮加入的標的」，'
                   '**非你目前持股**；加入前仍請看品質星等與含息總報酬（領息 ≠ 賺錢）。')


def _render_propose_subtab() -> None:
    """葡萄串主入口：優先以「使用者持股」評估月月領覆蓋；未載入組合則 fallback 高股息 10 檔提議。"""
    _rows = st.session_state.get('etf_portfolio_rows', []) or []
    _holdings = [r['ticker'] for r in _rows
                 if isinstance(r, dict) and r.get('ticker')]
    if _holdings:
        _render_holdings_coverage(_holdings)
        return
    st.caption('（尚未載入你的組合 —— 於上方「⚖️ ETF 組合」填入持股並按「計算組合」後，'
               '本區會改以你的**實際持股**評估月月領覆蓋。以下先示範高股息 10 檔的參考組合。）')
    _render_curated_recommendation()


def _render_curated_recommendation() -> None:
    """💡 系統提議（fallback）：從高股息 10 檔自動挑選最佳組合。"""
    st.markdown('##### 💡 從高股息 10 檔自動挑選最佳組合')
    _c1, _c2, _c3 = st.columns([1, 1, 1])
    with _c1:
        _max_etfs = st.slider('最多 ETF 數', 1, 5, value=4, key='_grape_max_etfs')
    with _c2:
        # B6-a v19.181:help 原寫「3+ 才過濾」—— `recommend_income_ladder:109`
        # 是 `if min_stars >= 2:`,設 2 就已經開始剔除。文案改對齊判定式。
        # 另補「未評等者保留」(:116-118),否則使用者會以為抓不到評等的會被砍掉。
        _min_stars = st.slider('最低品質星等 ⭐', 1, 5, value=3,
                               key='_grape_min_stars',
                               help='1 = 不過濾；**2 以上**即用 etf_quality 4 因子'
                                    '預先剔除低星等 ETF（抓不到評等的一律保留，避免誤殺）')
    with _c3:
        _excl = st.checkbox('排除月配高息（00929/00940/00939）',
                            value=False, key='_grape_excl_monthly')
    if not st.button('🍇 生成提議', key='_grape_btn_propose', type='primary'):
        # B6-a v19.181:原寫「最多 C(10,5)=252 種」—— 引擎是 `for k in 1..N` **累加**
        # (`recommend_income_ladder:147-149`),C(10,5) 只是最大的那一層,不是總數。
        # 實際 N=4 → ΣC(10,1..4)=385、N=5 → 637。同一畫面 :396「嘗試組合」metric
        # 印的是真實累計值,兩個數字對不起來。改為只描述行為 + 指向該 metric。
        st.caption('點上方按鈕產生建議組合。提議引擎會**窮舉** 1 到「最多 ETF 數」的'
                   '所有組合（各層數量累加），實際跑了幾種請看結果區的「嘗試組合」。')
        return
    with st.spinner('搜尋最佳組合中…（< 10 秒）'):
        _res = recommend_income_ladder(
            max_etfs=_max_etfs, min_etfs=1,
            exclude_monthly=_excl, min_stars=_min_stars)
    if _res.get('_err'):
        st.error(f'❌ {_res["_err"]}')
        return
    _combo = _res['best_combo']
    _cover_pct = _res['coverage_pct']
    _missing = sorted(_res['missing_months'])
    if _cover_pct >= 100:
        st.success(f'✅ 用 {len(_combo)} 檔 cover 全部 12 個月！組合：{", ".join(_combo)}')
    else:
        st.warning(f'⚠️ 用 {len(_combo)} 檔 cover {len(_res["covered_months"])}/12 月 '
                   f'({_cover_pct}%)，缺月份：{_missing}')
    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric('覆蓋月數', f'{len(_res["covered_months"])}/12')
    _m2.metric('缺口', len(_missing))
    _m3.metric('ETF 數', len(_combo))
    _m4.metric('嘗試組合', _res['all_candidates_evaluated'])
    st.markdown('##### 📅 12 月份覆蓋圖')
    # 提議路徑無「月配新上市」概念,未覆蓋月一律紅缺月(不傳 pending)。
    _render_month_grid(_res['month_map'])
    if _res.get('skipped_tickers'):
        st.caption(f'⚪ 略過（配息資料不足）：{", ".join(_res["skipped_tickers"])}')
    if _res.get('low_quality'):
        st.caption(f'⭐ 品質星等過濾（< {_min_stars}★）剔除：{", ".join(_res["low_quality"])}')
    if _res.get('alternatives'):
        st.markdown('##### 🔄 同分次優組合')
        _alt_rows = [{'組合': ', '.join(_a), 'ETF 數': len(_a)}
                     for _a in _res['alternatives']]
        st.dataframe(pd.DataFrame(_alt_rows),
                     use_container_width=True, hide_index=True)


def render_grape_ladder(gemini_fn=None) -> None:
    """Streamlit UI 對外入口 — 主視圖：🍇 你的持股月月領覆蓋（由組合持股驅動）。

    優先讀 st.session_state['etf_portfolio_rows']（上方「⚖️ ETF 組合」按「計算組合」後寫入），
    評估你**實際持股**的月月領覆蓋 + 缺月補位建議；未載入組合時 fallback 到
    「高股息 10 檔自動挑選最佳組合」提議。
    """
    st.markdown('### 📅 葡萄串領息法')
    st.caption('「不同月配 ETF」組合形成「葡萄串」：讓每個月都有息可領。'
               '本區優先就**你的持股**評估月月領覆蓋（於上方「⚖️ ETF 組合」按「計算組合」後帶入）；'
               '未載入組合時，改示範高股息 10 檔的參考組合。')
    with st.expander('💡 葡萄串領息法是什麼？怎麼用？', expanded=False):
        st.markdown(
            '**核心概念**：台灣高股息 ETF 各有固定**配息月份**（如 0056 配 1/4/7/10 月、00878 配 2/5/8/11 月…）。'
            '單買一檔 → 一年只領幾次、現金流集中；**刻意搭配「配息月份互補」的數檔**，就能串成「葡萄串」→ '
            '**幾乎每月都有息入帳**，現金流平滑。\n\n'
            '**怎麼看下方結果**：\n'
            '- **覆蓋月份/覆蓋率**：這組合一年 12 個月中有幾個月領得到息（越接近 12 越好）。\n'
            '- **缺漏月份**：哪幾個月沒息 → 可再找該月配息的 ETF 補上。\n'
            '- **品質星等過濾**：先用 etf_quality 4 因子剔除低品質 ETF，避免「為領息買到爛標的」。\n\n'
            '🎯 適合想要**穩定月現金流**的存股/退休族。提醒：領息 ≠ 賺錢 —— 殖利率高但股價跌更多＝「賺息賠本」，仍要看含息總報酬。'
        )
    _render_propose_subtab()
