"""src/compute/etf/portfolio_gates.py — ETF 組合三大體檢閘門判定(L2 純函式,B5-a v19.180)。

單一職責：**只回判定**（pass / fail / unknown + 理由 + 指標），零 I/O、零 Streamlit。
UI（`src/ui/etf/etf_tab_portfolio.py`）只負責把判定畫成燈號。

━━ 為什麼要有這個檔（§1 Fail Loud, Never Fake）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B5-a 實機盤點：三個綠燈同時在說謊 ——
  E-1 核心 100% / 衛星 0%，卻判「✅ 符合建議 60~80% / 20~40%」
      → `portfolio_manager.check_rebalance` 的判定式 `excess_ratio >= 0.10` 是**單邊**，
        只抓「衛星超標」；衛星**不足** 30pp 永遠落到 else 分支印綠燈。
  E-2 「最大偏離 0.0%」
      → 目標權重從來沒有輸入，程式拿「現況」當目標（`target = actual`），
        偏離度恆等於 0。綠燈不是「平衡」，是「沒算」。
  E-3 「任兩檔重疊 < 30%」
      → 跨市場成分股名稱分屬中文 / 英文兩個命名空間，永遠交集為空 → 恆 0%；
        且 yfinance 只給前 10 大（權重覆蓋率約 15%），
        重疊率**上限**本來就低於 30% 門檻 —— 這種「不可能失敗」的檢查通過了不代表任何事。

本檔的不變量：
    **綠燈 = 「算過、而且通過」**。
    「沒資料」「算不出來」「算得出來但結論不成立（上限低於門檻 → 不可能失敗）」
    一律回 `STATUS_UNKNOWN`，由 UI 顯示 ⚪ 無法判定 + **缺什麼**。

門檻一律走 `shared/signal_thresholds.py`（§3.3 反捏造，本檔不留 inline magic）。
"""
from __future__ import annotations

import math
import re

from shared.signal_thresholds import (
    PORTFOLIO_CORE_SAT_TOLERANCE_PP,
    PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT,
    PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT,
    PORTFOLIO_TARGET_SUM_TOLERANCE_PP,
)

# ── 判定狀態（三態，禁止二態）───────────────────────────────────────────────
STATUS_PASS: str = 'pass'
"""算過且通過。UI 畫綠燈。"""
STATUS_FAIL: str = 'fail'
"""算過且未通過。UI 畫紅燈。"""
STATUS_UNKNOWN: str = 'unknown'
"""**沒算 / 算不出來 / 算了也不成立**。UI 畫 ⚪ 無法判定 —— 絕不可退化成綠燈。"""

ROLE_CORE: str = '核心'
ROLE_SATELLITE: str = '衛星'
ROLE_BOND: str = '債券'
ROLE_UNKNOWN: str = '未知'

_TW_CODE_RE = re.compile(r'^\d{4,6}[A-Z]?$')
_CJK_RE = re.compile(r'[一-鿿]')


def _verdict(status: str, headline: str, detail: str = '', **metrics) -> dict:
    """統一判定結構。metrics 放可稽核的數字（UI 顯示 / 測試斷言用）。"""
    return {'status': status, 'headline': headline, 'detail': detail, **metrics}


def _to_float(v):
    """寬鬆轉 float；None / '' / NaN / 非數字 → None（不捏造 0）。"""
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    try:
        _f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(_f) else _f


# ══════════════════════════════════════════════════════════════════════════
# 閘門 1｜核心 / 衛星 配置 vs regime 目標
# ══════════════════════════════════════════════════════════════════════════

def classify_portfolio_role(ticker) -> str:
    """核衛閘門專用分類 → `'債券' | '核心' | '衛星' | '未知'`。純函式。

    **不新增白名單**，依序串既有三個 SSOT，第一個命中者勝（禁止平均、禁止猜）：

    1. `portfolio_coherence.classify_asset_class` == 'bond' → `債券`
       （債券先判，否則 `BND` / `00679B` 會被下面的核心白名單吃掉 —— 那正是
       `auto_role` 現在的行為，會讓一個 100% 債券組合顯示「核心 100%」）
    2. `etf_categories.get_category_name(ticker)`（台股同儕分類表）
       - `'市值型'` → `核心`（追大盤、定期定額不理循環）
       - 其他任何非空類別（高股息 / 半導體科技 / Smart Beta / …）→ `衛星`
    3. **非台股代號**（不合 `^\\d{4,6}[A-Z]?$`）且落在
       `etf_helpers.CORE_TICKER_WHITELIST` → `核心`
       （撈 `VT` / `VTI` / `VOO` / `SPY` / `VEA` / `VWO` 這些台股分類表沒有的海外寬基）
    4. 以上皆不中 → `未知`

    ⚠️ 為什麼台股代號**不**吃第 3 步的白名單：`CORE_TICKER_WHITELIST` 把
    `0056` / `00878` / `00713`（高股息）與 `00679B`（債券）也列為「核心」，
    對核衛閘門而言語意是錯的。台股一律以分類表為準；分類表查無 → `未知`
    （§1：寧可回未知讓使用者知道要補分類，也不硬塞一個桶）。
    """
    from src.compute.etf.etf_categories import get_category_name  # noqa: PLC0415
    from src.compute.etf.etf_helpers import CORE_TICKER_WHITELIST  # noqa: PLC0415
    from src.compute.etf.portfolio_coherence import classify_asset_class  # noqa: PLC0415
    from shared.etf_codes import bare_etf_code  # noqa: PLC0415

    _code = bare_etf_code(ticker)
    if not _code:
        return ROLE_UNKNOWN
    if classify_asset_class(ticker) == 'bond':
        return ROLE_BOND
    _cat = get_category_name(ticker)
    if _cat == '市值型':
        return ROLE_CORE
    if _cat:
        return ROLE_SATELLITE
    if not _TW_CODE_RE.match(_code) and _code in CORE_TICKER_WHITELIST:
        return ROLE_CORE
    return ROLE_UNKNOWN


def assess_role_split(rows) -> dict:
    """rows: `[{ticker, value}]` → 四桶金額 + 股票腿（核心+衛星+未知）內的佔比。

    債券**不進**核心/衛星分母 —— 核衛講的是「股票部位怎麼拆」，
    股債比另有 `portfolio_coherence.assess_stock_bond` 專門看（避免同一數字兩種語意）。

    Returns
    -------
    dict：`core_value / satellite_value / bond_value / unknown_value /
    equity_value / total_value / core_pct / satellite_pct / unknown_pct /
    bond_pct_of_total / unclassified(list[str])`
    佔比皆為「股票腿內」百分比；`equity_value == 0` 時佔比皆 0.0。
    """
    _buckets = {ROLE_CORE: 0.0, ROLE_SATELLITE: 0.0, ROLE_BOND: 0.0, ROLE_UNKNOWN: 0.0}
    _unclassified: list[str] = []
    for _r in rows or []:
        _v = _to_float((_r or {}).get('value'))
        if _v is None or _v <= 0:
            continue
        _role = classify_portfolio_role((_r or {}).get('ticker'))
        _buckets[_role] += _v
        if _role == ROLE_UNKNOWN:
            _tk = str((_r or {}).get('ticker') or '?')
            if _tk not in _unclassified:
                _unclassified.append(_tk)
    _equity = _buckets[ROLE_CORE] + _buckets[ROLE_SATELLITE] + _buckets[ROLE_UNKNOWN]
    _total = _equity + _buckets[ROLE_BOND]

    def _pct(v):
        return round(v / _equity * 100, 2) if _equity > 0 else 0.0

    return {
        'core_value': _buckets[ROLE_CORE],
        'satellite_value': _buckets[ROLE_SATELLITE],
        'bond_value': _buckets[ROLE_BOND],
        'unknown_value': _buckets[ROLE_UNKNOWN],
        'equity_value': _equity,
        'total_value': _total,
        'core_pct': _pct(_buckets[ROLE_CORE]),
        'satellite_pct': _pct(_buckets[ROLE_SATELLITE]),
        'unknown_pct': _pct(_buckets[ROLE_UNKNOWN]),
        'bond_pct_of_total': (round(_buckets[ROLE_BOND] / _total * 100, 2)
                              if _total > 0 else 0.0),
        'unclassified': _unclassified,
    }


def evaluate_core_satellite_gate(
    rows,
    *,
    target_core_pct,
    tolerance_pp: float = PORTFOLIO_CORE_SAT_TOLERANCE_PP,
    regime: str = '',
) -> dict:
    """核心 / 衛星比 vs regime 目標 → 三態判定。純函式。

    判定式（**雙邊**，對齊畫面上寫的 `目標 ± tolerance_pp`）：
        band = [target_core_pct - tolerance_pp, target_core_pct + tolerance_pp]

    未分類部位（`未知`）用**區間法**處理，不硬歸任一桶：
        core_pct_min = 核心 / 股票腿                 （未知全算衛星，最不利核心）
        core_pct_max = (核心 + 未知) / 股票腿        （未知全算核心，最有利核心）
      - 整段區間都落在 band 內 → `pass`
      - 整段區間都在 band 外   → `fail`（不管未知怎麼歸都不合格 → 結論穩健）
      - 區間跨過 band 邊界     → `unknown`（未分類的那幾檔會左右結論 → 不下判斷）

    Parameters
    ----------
    rows            : iterable of `{ticker, value}`（value = 市值，同一幣別）
    target_core_pct : float | None  regime 對應的核心目標 %（None → 無法判定）
    tolerance_pp    : float  雙邊容忍帶（百分點），SSOT
        `shared.signal_thresholds.PORTFOLIO_CORE_SAT_TOLERANCE_PP`
    regime          : str    僅供訊息顯示

    Returns
    -------
    dict：`status / headline / detail / split / target_core_pct / band_lo /
    band_hi / core_pct_min / core_pct_max / tolerance_pp / regime`
    """
    _split = assess_role_split(rows)
    # 容忍帶壞掉(None / 非數字)不該讓整頁炸,但也不能悄悄變成 0 → 退回 SSOT 預設。
    _tol = _to_float(tolerance_pp)
    if _tol is None or _tol < 0:
        _tol = PORTFOLIO_CORE_SAT_TOLERANCE_PP
    _base = {'split': _split, 'tolerance_pp': float(_tol), 'regime': regime,
             'target_core_pct': _to_float(target_core_pct),
             'band_lo': None, 'band_hi': None,
             'core_pct_min': _split['core_pct'],
             'core_pct_max': round(_split['core_pct'] + _split['unknown_pct'], 2)}

    if _split['equity_value'] <= 0:
        return _verdict(
            STATUS_UNKNOWN, '⚪ 無法判定：組合沒有股票部位',
            '核心 / 衛星是「股票部位怎麼拆」的檢查。目前股票市值為 0（可能全為債券，'
            '或所有持股的市值都取不到）→ 分母不存在，本檢查不成立。', **_base)

    _target = _to_float(target_core_pct)
    if _target is None:
        return _verdict(
            STATUS_UNKNOWN, '⚪ 無法判定：拿不到 regime 核心目標比',
            '目標比例取決於市場狀態（regime）。目前 regime 未評估或配資引擎不可用 → '
            '沒有可比對的目標，**不顯示綠燈**（缺：regime 核心目標 %）。', **_base)

    _lo = round(_target - _tol, 2)
    _hi = round(_target + _tol, 2)
    _base['band_lo'], _base['band_hi'] = _lo, _hi
    _cmin, _cmax = _base['core_pct_min'], _base['core_pct_max']
    _regime_txt = f'（regime={regime}）' if regime else ''
    _range_txt = (f'{_cmin:.1f}%' if _split['unknown_pct'] <= 0
                  else f'{_cmin:.1f}~{_cmax:.1f}%')

    # 整段區間都在 band 外 → 不管未分類怎麼歸，結論都一樣 → 可以下 fail
    if _cmax < _lo or _cmin > _hi:
        _dev = (_cmax - _lo) if _cmax < _lo else (_cmin - _hi)
        return _verdict(
            STATUS_FAIL,
            f'🔴 偏離目標：核心 {_range_txt}，超出建議帶 {_lo:.0f}~{_hi:.0f}%'
            f' {_dev:+.1f}pp',
            f'目標核心 {_target:.0f}%{_regime_txt}，雙邊容忍 ±{_tol:.0f}pp。'
            f'衛星 {_split["satellite_pct"]:.1f}%（目標 {100 - _target:.0f}%）。',
            **_base)
    # 整段區間都在 band 內 → 真的通過
    if _cmin >= _lo and _cmax <= _hi:
        return _verdict(
            STATUS_PASS,
            f'✅ 符合建議：核心 {_range_txt}（建議 {_lo:.0f}~{_hi:.0f}%）',
            f'目標核心 {_target:.0f}%{_regime_txt}，雙邊容忍 ±{_tol:.0f}pp。'
            f'衛星 {_split["satellite_pct"]:.1f}%（目標 {100 - _target:.0f}%）。',
            **_base)
    # 區間跨邊界：未分類部位會左右結論
    return _verdict(
        STATUS_UNKNOWN,
        f'⚪ 無法判定：核心佔比只能算到 {_range_txt}，跨過建議帶邊界',
        f'未分類部位佔股票腿 {_split["unknown_pct"]:.1f}%'
        f'（{"、".join(_split["unclassified"]) or "—"}）—— 這幾檔算核心或算衛星，'
        f'會落在建議帶 {_lo:.0f}~{_hi:.0f}% 的不同側，因此不下判斷。'
        f'缺：這些代號的 ETF 分類（`src/compute/etf/etf_categories.py`）。',
        **_base)


# ══════════════════════════════════════════════════════════════════════════
# 閘門 2｜再平衡（實際權重 vs 目標權重）
# ══════════════════════════════════════════════════════════════════════════

def evaluate_rebalance_gate(
    rows,
    *,
    tolerance_pp,
    target_sum_tolerance_pp: float = PORTFOLIO_TARGET_SUM_TOLERANCE_PP,
) -> dict:
    """實際權重 vs **使用者設定的**目標權重 → 三態判定。純函式。

    §1 的核心：**沒有目標就沒有偏離**。原碼在使用者沒填目標時把「現況」當目標
    （`target = actual`），偏離度恆為 0，於是永遠印「✅ 無需再平衡」——
    那個綠燈代表的是「沒算」而不是「平衡」。本函式把這種情況判為 `unknown`。

    Parameters
    ----------
    rows : iterable of `{ticker, actual_pct, target_pct}`
        `target_pct` 為 `None` / 空白 → 該檔沒有目標。
    tolerance_pp : float  容忍偏離（百分點）；`|actual - target| > tolerance_pp` → 需調整。
    target_sum_tolerance_pp : float  目標總和容差，SSOT
        `shared.signal_thresholds.PORTFOLIO_TARGET_SUM_TOLERANCE_PP`。

    Returns
    -------
    dict：`status / headline / detail / breaches(list) / deviations(dict) /
    target_sum / missing_targets(list) / tolerance_pp`
    """
    _rows = [r for r in (rows or []) if r]
    _tol = _to_float(tolerance_pp)
    _base = {'breaches': [], 'deviations': {}, 'target_sum': None,
             'missing_targets': [], 'tolerance_pp': _tol}

    if not _rows:
        return _verdict(STATUS_UNKNOWN, '⚪ 無法判定：組合是空的',
                        '沒有任何有效持股 → 無從計算權重偏離。', **_base)
    if _tol is None or _tol <= 0:
        return _verdict(STATUS_UNKNOWN, '⚪ 無法判定：容忍偏離度無效',
                        f'容忍偏離度必須 > 0，收到 {tolerance_pp!r}。', **_base)

    _missing = [str(r.get('ticker') or '?') for r in _rows
                if _to_float(r.get('target_pct')) is None]
    _base['missing_targets'] = _missing

    if len(_missing) == len(_rows):
        return _verdict(
            STATUS_UNKNOWN, '⚪ 無法判定：尚未設定目標權重',
            '再平衡是「實際權重 vs **你想要的**目標權重」的比較。目前每一檔的'
            '目標比例都是空的 —— 若拿現況當目標，偏離度必然是 0.0%，'
            '那不是「已平衡」而是「沒算」。'
            '缺：請在上方表格的「目標比例%」欄填入各檔目標（總和 100%）。', **_base)
    if _missing:
        return _verdict(
            STATUS_UNKNOWN, f'⚪ 無法判定：{len(_missing)} 檔缺目標權重',
            f'以下持股沒有目標比例：{"、".join(_missing)}。'
            '部分填寫時無法決定剩餘權重該怎麼分（平均分？照現況分？兩種都是猜）→ '
            '不判定。缺：把「目標比例%」全部填滿（總和 100%）。', **_base)

    _targets = {str(r.get('ticker') or '?'): _to_float(r.get('target_pct')) for r in _rows}
    _sum = round(sum(_targets.values()), 4)
    _base['target_sum'] = _sum
    _sum_tol = float(target_sum_tolerance_pp)
    if abs(_sum - 100.0) > _sum_tol:
        return _verdict(
            STATUS_UNKNOWN, f'⚪ 無法判定：目標權重總和 {_sum:.1f}% ≠ 100%',
            f'目標權重要能構成一個完整組合才有意義（容許 ±{_sum_tol:.0f}pp 四捨五入）。'
            f'目前總和 {_sum:.1f}%，差 {_sum - 100:+.1f}pp → 以它算出的偏離度沒有意義。'
            '缺：把「目標比例%」調整到總和 100%。', **_base)

    _breaches = []
    for _r in _rows:
        _tk = str(_r.get('ticker') or '?')
        _actual = _to_float(_r.get('actual_pct')) or 0.0
        _target = _targets[_tk]
        _dev = round(_actual - _target, 4)
        _base['deviations'][_tk] = _dev
        if abs(_dev) > _tol:
            _breaches.append({'ticker': _tk, 'actual_pct': _actual,
                              'target_pct': _target, 'deviation_pp': _dev,
                              'action': '買進' if _dev < 0 else '賣出'})
    _base['breaches'] = _breaches
    _max_dev = max((abs(v) for v in _base['deviations'].values()), default=0.0)

    if _breaches:
        return _verdict(
            STATUS_FAIL,
            f'🔴 需再平衡：{len(_breaches)} 檔偏離超過 ±{_tol:.0f}pp'
            f'（最大偏離 {_max_dev:.1f}pp）',
            '、'.join(f'{b["ticker"]} {b["deviation_pp"]:+.1f}pp' for b in _breaches),
            **_base)
    return _verdict(
        STATUS_PASS,
        f'✅ 無需再平衡：所有標的偏離度均在 ±{_tol:.0f}pp 內'
        f'（最大偏離 {_max_dev:.1f}pp）',
        f'已比對 {len(_rows)} 檔的實際權重 vs 你設定的目標權重（總和 {_sum:.1f}%）。',
        **_base)


# ══════════════════════════════════════════════════════════════════════════
# 閘門 3｜持股重疊（含「可比對性」與「量得到的上限」）
# ══════════════════════════════════════════════════════════════════════════

def holdings_coverage_pct(holdings) -> float:
    """成分股權重覆蓋率 %：Σ weight（上限 100）。空 / None → 0.0。純函式。

    為什麼重要：yfinance 只回**前 10 大**持股（VT 前十大約佔淨值 15%），
    台灣 Yahoo 則可到 30-60 檔（覆蓋率 85%+）。
    覆蓋率決定「權重 Overlap% 最大可能是多少」——
    覆蓋率 15% 的 ETF，跟任何東西比對都不可能超過 15%。
    """
    from src.compute.etf.etf_calc import _canonical_weight_map  # noqa: PLC0415
    if not holdings:
        return 0.0
    try:
        _m = _canonical_weight_map(holdings)
    except (AttributeError, TypeError):
        return 0.0
    return round(min(sum(_m.values()), 100.0), 2)


def holdings_namespace(holdings) -> str:
    """成分股「名稱命名空間」→ `'zh' | 'en' | 'mixed' | 'empty'`。純函式。

    台股來源（台灣 Yahoo / MoneyDJ）回中文股名「台積電」；
    海外來源（yfinance funds_data）回英文「Taiwan Semiconductor Manufacturing Co Ltd」。
    兩者永遠對不上 —— 這不是「重疊 0%」，是「根本沒比到」。
    """
    from src.compute.etf.etf_calc import _canonical_holding_key  # noqa: PLC0415
    try:
        _keys = [_canonical_holding_key(k)
                 for k in (holdings.keys() if hasattr(holdings, 'keys') else (holdings or []))]
    except (AttributeError, TypeError):
        return 'empty'
    _keys = [k for k in _keys if k]
    if not _keys:
        return 'empty'
    _cjk = sum(1 for k in _keys if _CJK_RE.search(k))
    if _cjk == len(_keys):
        return 'zh'
    if _cjk == 0:
        return 'en'
    return 'mixed'


def overlap_ceiling_pct(h1, h2, method: str = 'weight') -> float:
    """兩檔 ETF「在現有資料下**最高可能**的重疊率 %」。純函式。

    - `weight`  ：Σ min(w_a, w_b) ≤ min(Σw_a, Σw_b) = min(兩邊覆蓋率)
    - `jaccard` ：|A∩B| / |A∪B| ≤ min(|A|,|B|) / max(|A|,|B|)

    用途：若**上限 ≤ 警示門檻**，這對組合再怎麼雷同都不可能觸發警示 →
    「沒超過門檻」是資料截斷造成的，不是分散得好 → 判 unknown（§1）。
    """
    from src.compute.etf.etf_calc import _canonical_holding_key  # noqa: PLC0415
    if not h1 or not h2:
        return 0.0
    if method == 'jaccard':
        _n1 = len({_canonical_holding_key(k)
                   for k in (h1.keys() if hasattr(h1, 'keys') else h1)} - {''})
        _n2 = len({_canonical_holding_key(k)
                   for k in (h2.keys() if hasattr(h2, 'keys') else h2)} - {''})
        if _n1 == 0 or _n2 == 0:
            return 0.0
        return round(min(_n1, _n2) / max(_n1, _n2) * 100, 2)
    return round(min(holdings_coverage_pct(h1), holdings_coverage_pct(h2)), 2)


def _common_key_count(h1, h2) -> int:
    from src.compute.etf.etf_calc import _canonical_holding_key  # noqa: PLC0415
    _s1 = {_canonical_holding_key(k) for k in (h1.keys() if hasattr(h1, 'keys') else h1)} - {''}
    _s2 = {_canonical_holding_key(k) for k in (h2.keys() if hasattr(h2, 'keys') else h2)} - {''}
    return len(_s1 & _s2)


def evaluate_overlap_gate(
    holdings_map,
    tickers=None,
    *,
    method: str = 'weight',
    threshold_pct=None,
) -> dict:
    """兩兩持股重疊 vs 門檻 → 三態判定 + 逐對可稽核明細。純函式。

    每一對的 `status`：
      - `breach`               ：已算出且 > 門檻 → 整體 fail
      - `ok`                   ：已算出、≤ 門檻、且**確實有可能超過門檻**（上限 > 門檻、
                                 命名空間可比對）→ 才算真的通過
      - `no_data`              ：任一邊拿不到成分股
      - `incomparable_namespace`：中文名 vs 英文名兩個命名空間且交集為 0 → 沒比到
      - `inconclusive_ceiling` ：資料上限 ≤ 門檻（例如 yfinance 只給前 10 大）→
                                 這對「不可能失敗」，通過不代表任何事

    整體：任一 `breach` → `fail`；全部 `ok` → `pass`；否則 `unknown`。

    Parameters
    ----------
    holdings_map : dict[ticker → dict[名稱, 權重%] | None]
    tickers      : 指定比對順序 / 範圍；None → 用 `holdings_map` 的鍵
    method       : `'weight'`（業界標準，預設）| `'jaccard'`
    threshold_pct: None → 依 method 取 SSOT
        （`PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT` / `..._JACCARD_...`）

    Returns
    -------
    dict：`status / headline / detail / method / threshold_pct / pairs(list) /
    breaches / unmeasured / measured_pairs / total_pairs`
    """
    from src.compute.etf.etf_calc import (  # noqa: PLC0415
        calc_holdings_overlap_pct, calc_jaccard_overlap,
    )
    _method = 'jaccard' if method == 'jaccard' else 'weight'
    _thr = _to_float(threshold_pct)
    if _thr is None:
        _thr = (PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT if _method == 'jaccard'
                else PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT)
    _fn = calc_jaccard_overlap if _method == 'jaccard' else calc_holdings_overlap_pct
    _map = dict(holdings_map or {})
    _tks = [t for t in (tickers if tickers is not None else list(_map.keys()))]

    _pairs: list[dict] = []
    for _i in range(len(_tks)):
        for _j in range(_i + 1, len(_tks)):
            _a, _b = _tks[_i], _tks[_j]
            _ha, _hb = _map.get(_a), _map.get(_b)
            _p = {'a': _a, 'b': _b, 'value_pct': None, 'ceiling_pct': None,
                  'namespace_a': holdings_namespace(_ha),
                  'namespace_b': holdings_namespace(_hb),
                  'coverage_a_pct': holdings_coverage_pct(_ha),
                  'coverage_b_pct': holdings_coverage_pct(_hb),
                  'common_holdings': 0, 'status': 'no_data', 'reason': ''}
            if not _ha or not _hb:
                _missing = [str(t) for t, h in ((_a, _ha), (_b, _hb)) if not h]
                _p['reason'] = f'{"、".join(_missing)} 拿不到成分股清單'
                _pairs.append(_p)
                continue
            _val = float(_fn(_ha, _hb))
            _ceil = overlap_ceiling_pct(_ha, _hb, _method)
            _common = _common_key_count(_ha, _hb)
            _p.update({'value_pct': round(_val, 2), 'ceiling_pct': _ceil,
                       'common_holdings': _common})
            if _val > _thr:
                _p['status'] = 'breach'
                _p['reason'] = f'重疊 {_val:.1f}% > 門檻 {_thr:.0f}%'
            elif (_common == 0 and _p['namespace_a'] != _p['namespace_b']
                  and 'empty' not in (_p['namespace_a'], _p['namespace_b'])):
                _p['status'] = 'incomparable_namespace'
                _p['reason'] = (
                    f'成分股名稱分屬不同命名空間（{_a}={_p["namespace_a"]} / '
                    f'{_b}={_p["namespace_b"]}）且交集為 0 —— '
                    '中文股名對不上英文公司名，這是「沒比到」不是「不重疊」')
            elif _ceil <= _thr:
                _p['status'] = 'inconclusive_ceiling'
                _p['reason'] = (
                    f'資料只涵蓋 {min(_p["coverage_a_pct"], _p["coverage_b_pct"]):.0f}% '
                    f'權重 → 重疊率上限 {_ceil:.1f}% ≤ 門檻 {_thr:.0f}%，'
                    '這一對不可能觸發警示，通過不代表分散')
            else:
                _p['status'] = 'ok'
                _p['reason'] = f'重疊 {_val:.1f}% ≤ 門檻 {_thr:.0f}%（上限 {_ceil:.1f}%）'
            _pairs.append(_p)

    _base = {'method': _method, 'threshold_pct': float(_thr), 'pairs': _pairs,
             'breaches': [p for p in _pairs if p['status'] == 'breach'],
             'unmeasured': [p for p in _pairs if p['status'] not in ('ok', 'breach')],
             'measured_pairs': sum(1 for p in _pairs if p['status'] in ('ok', 'breach')),
             'total_pairs': len(_pairs)}
    _label = 'Jaccard 重疊' if _method == 'jaccard' else '權重重疊'

    if len(_tks) < 2:
        return _verdict(STATUS_UNKNOWN, '⚪ 無法判定：不足 2 檔，無從兩兩比對',
                        '持股重疊需要至少 2 檔 ETF。', **_base)
    if _base['breaches']:
        return _verdict(
            STATUS_FAIL,
            f'🔴 重疊過高：{len(_base["breaches"])} 對 {_label} > {_thr:.0f}%',
            '；'.join(f'{p["a"]} × {p["b"]} {p["value_pct"]:.1f}%'
                      for p in _base['breaches']), **_base)
    if _base['unmeasured']:
        return _verdict(
            STATUS_UNKNOWN,
            f'⚪ 無法判定：{len(_base["unmeasured"])}/{len(_pairs)} 對比不出來',
            '；'.join(f'{p["a"]} × {p["b"]}：{p["reason"]}' for p in _base['unmeasured']),
            **_base)
    return _verdict(
        STATUS_PASS,
        f'✅ 分散度良好：任兩檔 {_label} 皆 ≤ {_thr:.0f}%',
        f'已實際比對全部 {len(_pairs)} 對，每一對的可測上限都高於門檻'
        '（亦即真的有可能超標而沒超標）。', **_base)
