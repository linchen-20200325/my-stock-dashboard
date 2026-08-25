"""scripts/diagnose_etf_total_return_fix.py — 「1Y 含息報酬重複計息」修正對**你真實持股**的影響對照表。

這支腳本在做什麼
================
`src/compute/etf/etf_calc.calc_total_return_1y` 原本把同一筆配息算了兩次:

    修正前:  (p_end - p_start + div_sum) / p_start * 100
    修正後:  (p_end - p_start)           / p_start * 100      ← commit 1a0992b(現行 code)

`df['Close']` 來自 `yf.Ticker(t).history(period='max', auto_adjust=True)` —— **已還原權息**,
價差本身就是含息總報酬,再加現金配息 = 重複計入。本腳本逐檔算出**同一天、同一批資料**下
「修正前會看到什麼 / 修正後會看到什麼」,並把三個吃這個數字的判定各跑兩遍。

⚠️ 為什麼「修前」是腳本自己重建的
=================================
修正已經進 main(commit `1a0992b`),現行 code 裡**沒有**舊算式了。本腳本用
`_calc_total_return_1y_prefix()` 逐字重建 `git show 1a0992b^:src/compute/etf/etf_calc.py`
的舊版本(見該函式 docstring),再用 context manager `_prefix_bug_active()` **暫時**把
`etf_calc.calc_total_return_1y` 換掉,讓 production 判定函式原封不動地跑一次舊數字。

- 這個替換**只存在於本 process 的記憶體中**,不改任何檔案、不需要你 `git revert`。
- 兩邊的「判定」全部 import production 函式,腳本**沒有**自己複寫任何判定式:
    · 戰情室健康燈號  → `etf_calc._compute_etf_warroom_row`
    · 配息健康度      → `etf_helpers.dividend_health_label`(經 `build_etf_score_row`)
    · 綜合分 / 星等   → `etf_scoring_helpers.compute_etf_composite_score`
    · 🚦 留/觀察/換   → `etf_recommendation.recommend_etf_actions`(整批,含同類重疊偵測)

兩種用法
========
    # 用法 A(建議):讀你 Google Sheet 的真實持股,與每日推播 cron 同一條路
    #   需要環境變數:GCP_SERVICE_ACCOUNT_JSON + PORTFOLIO_SHEET_ID / STOCK_PORTFOLIO_SHEET_ID
    #   (與 scripts/push_holdings_daily.py 完全相同的取數路徑,不另立第二套)
    python scripts/diagnose_etf_total_return_fix.py

    # 用法 B(fallback):直接在命令列指定代號(不需要 Google 憑證)
    python scripts/diagnose_etf_total_return_fix.py 0050 0056 00878 00919

    # 兩者都可以加:把整張表另存 CSV(終端機對不齊時看這個)
    python scripts/diagnose_etf_total_return_fix.py --csv /tmp/etf_fix_impact.csv

行情來源與 proxy
================
價格 / 配息 / info 走既有 L1 `src/data/etf/etf_fetch.py`,內部已用 `_proxy_env()` 套 NAS
Squid proxy(讀 `st.secrets['PROXY_URL']` 或 OS 的 `HTTPS_PROXY`/`HTTP_PROXY`)。
**海外 IP 直連 Yahoo 會 403 → 全部欄位空白**,請在有 proxy 的環境跑。

輸出怎麼讀
==========
主表**依「判定有沒有變」排序,有變的排最前面**,欄位:

    代號 / 名稱          — 代號為 yfinance 格式(台股自動補 .TW)
    類型                 — 核心 / 衛星,走 `etf_helpers.auto_role`(與 ETF 組合頁同一支)
    修前1Y% / 修後1Y%    — 同一批資料、兩種算式;`None` 代表**算不出來**(見下方「算不出來」清單)
    差(pp)               — 修前 − 修後,恆 ≥ 0(重複計息只會高估)
    配息率%              — `calc_current_yield`,兩邊相同(不受本 bug 影響)
    修前燈 / 修後燈       — 戰情室健康燈號(表內只印 emoji + 短語,完整字串見「明細」區)
    變色                 — 燈號**顏色**(🔴🟡🟢⚪)有沒有變。
                           ⚠️ 只有「核心」的燈吃 1Y 報酬;「衛星」的燈是 σ 位階
                           (`_compute_etf_warroom_row` 衛星分支只讀 σ),所以衛星恆不變色。
    配息健康             — `dividend_health_label` 修前→修後
    綜合分 / 星等 / 🚦建議 — 修前→修後(`total_ret_1y` 是 7 維中權重最大 0.25、
                           正規化跨距僅 15pp,掉幅容易跨過 KEEP 0.65 / SELL 0.35 門檻)

§1 Fail Loud
============
抓不到就說抓不到:任何一檔算不出 1Y 報酬,**一律列進表尾「算不出來」清單並寫原因**,
不填估計值、不 `fillna(0)`、不靜默跳過。非 ETF 的持股(個股 / 特別股)也會列出來說明
「本 bug 不影響」,而不是無聲消失。

§8.2:本檔為 scripts/ orchestrator(同 push_holdings_daily / update_forward_test_freeze),
可**往下**跨層 import(L1/L2/L3);唯讀診斷,不寫任何檔案(除非你指定 --csv)。

⚠️ commit 前必辦:`tests/test_c3_layering_guard.py` 把 `scripts/**` 標成 L1,所以本檔的
L2/L3 import 會讓 `test_rule5_no_upward_imports` 紅燈(與同目錄每一支 cron 完全同一根因,
見該檔 `_TODO_SCRIPTS_LAYER`)。要在該檔 scripts 區塊的 tuple 補 6 條:

    ("scripts/diagnose_etf_total_return_fix.py", "src.compute.etf.etf_calc"),
    ("scripts/diagnose_etf_total_return_fix.py", "src.compute.etf.etf_helpers"),
    ("scripts/diagnose_etf_total_return_fix.py", "src.compute.etf.etf_quality"),
    ("scripts/diagnose_etf_total_return_fix.py", "src.compute.etf.etf_recommendation"),
    ("scripts/diagnose_etf_total_return_fix.py", "src.compute.etf.etf_scoring_helpers"),
    ("scripts/diagnose_etf_total_return_fix.py", "src.services.etf_scoring_service"),

**刻意不**用 `importlib.import_module()` 之類的寫法繞開那個 AST 掃描 —— 那是把違憲藏起來
而不是解決它(CLAUDE.md §8.2.A.0 規則 5),而且守衛的價值就在於「新增就會紅」。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import logging
import os
import sys
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TW_TZ = _dt.timezone(_dt.timedelta(hours=8))

# 兩條 sheet 通道,與 scripts/push_holdings_daily.py 同名同義(不另立第二套)。
_PORTFOLIO_SHEET_ENV = "PORTFOLIO_SHEET_ID"
_STOCK_SHEET_ENV = "STOCK_PORTFOLIO_SHEET_ID"

# 燈號顏色字元(取燈號字串第一個字元判「變色」)。
_LAMP_COLORS = ("🔴", "🟡", "🟢", "⚪", "🟠")


def _tw_now() -> str:
    return _dt.datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")


def _quiet_bare_mode_warnings() -> None:
    """靜音 streamlit「No runtime found / missing ScriptRunContext」bare-mode 提示。

    §1 分寸:這裡壓掉的是 **streamlit 自己說「在 bare mode 可以忽略」的框架提示**,
    不是資料層錯誤。所有 fetcher 的失敗 log(`[etf_fetch] ❌ ...`)照印不誤。
    加 `--verbose` 可以把這些提示放回來。
    """
    for _name in ("streamlit.runtime.caching.cache_data_api",
                  "streamlit.runtime.caching.cache_resource_api",
                  "streamlit.runtime.scriptrunner_utils.script_run_context",
                  "streamlit.runtime.state.session_state_proxy"):
        logging.getLogger(_name).setLevel(logging.ERROR)


# ──────────────────────────────────────────────────────────────────────
# 修正前算式:逐字重建(唯一「腳本自己寫」的計算,判定式一律 import production)
# ──────────────────────────────────────────────────────────────────────
def _calc_total_return_1y_prefix(df, divs, *, require_full_period: bool = False):
    """**修正前**的 `calc_total_return_1y` —— 逐字重建自 `git show 1a0992b^`。

    與舊版唯一的差別是 `require_full_period` 改成 keyword-only,好讓它能直接頂替
    現行簽章 `calc_total_return_1y(df, *, require_full_period=False)`;函式體
    (含 `except` 吞例外回 0.0 這個舊行為)一行未改 —— 目的就是重現當時畫面上的數字,
    連它的缺點一起重現,否則對照表會失真。

    代數關係(commit 1a0992b 已驗證):設 r = 真實總報酬、y = 殖利率(分母同為最新
    收盤價),則 修前值 = r + y(1 + r)。本函式不走這條代數捷徑,直接重算原式,
    讓對照表的「修前」是**重跑出來的**而不是推導出來的。
    """
    if df.empty:
        return 0.0
    try:
        cutoff = df.index[-1] - timedelta(days=365)
        df_1y = df[df.index >= cutoff]
        if len(df_1y) < 2:
            return 0.0
        if require_full_period:
            _span_days = (df_1y.index[-1] - df_1y.index[0]).days
            if _span_days < 365 * 0.9:
                return None
        p_start = float(df_1y['Close'].iloc[0])
        p_end = float(df_1y['Close'].iloc[-1])
        _didx = (divs.index.tz_localize(None)
                 if (not divs.empty and divs.index.tz is not None) else divs.index)
        div_sum = float(divs[_didx >= cutoff].sum()) if not divs.empty else 0.0
        return round((p_end - p_start + div_sum) / p_start * 100, 2)
    except Exception as _e:  # noqa: BLE001 — 刻意保留舊版行為(吞例外回 0.0)
        print(f'[prefix_total_return] swallow: {type(_e).__name__}: {_e}', file=sys.stderr)
        return 0.0


@contextmanager
def _prefix_bug_active(divs):
    """暫時把 `etf_calc.calc_total_return_1y` 換成修正前版本(只在本 process 記憶體)。

    為什麼用替換而不是「算完再改欄位」:`_compute_etf_warroom_row` 與
    `build_etf_score_row` 兩支 production 函式**內部**呼叫 `calc_total_return_1y`,
    替換掉它等於真的把那次 commit 退回去跑一遍,不必假設「這個數字只被用在 N 個地方」
    (那種假設正是最容易漏的)。`build_etf_score_row` 是 function-local import、
    `_compute_etf_warroom_row` 走 module global,兩者都在**呼叫當下**才解析,故有效。

    `finally` 一定還原;即使中途例外也不會污染同一 process 後續的「修後」計算。
    """
    import src.compute.etf.etf_calc as _ec

    _orig = _ec.calc_total_return_1y

    def _patched(df, *, require_full_period: bool = False):
        return _calc_total_return_1y_prefix(
            df, divs, require_full_period=require_full_period)

    _ec.calc_total_return_1y = _patched
    try:
        yield
    finally:
        _ec.calc_total_return_1y = _orig


# ──────────────────────────────────────────────────────────────────────
# 持股讀取(用法 A:Google Sheet Service Account,與 push_holdings_daily 同路徑)
# ──────────────────────────────────────────────────────────────────────
def _read_holdings_from_sheets() -> list[dict]:
    """讀兩條 sheet 通道的 `portfolios` 分頁 → `[{ticker, lots, avg_price}, ...]`。

    §2.1 SSOT:直接用 `gsheet_sa_reader`(headless Service Account 路徑),與每日推播
    cron 同一支;**不**走 `gsheet_portfolio` 的 OAuth 路徑(那條需要瀏覽器 session,
    純 CLI 沒有)。憑證 / sheet id 缺 → raise(§1,不假裝「你沒持股」)。
    """
    from src.data.portfolio.gsheet_sa_reader import load_sa_credentials, read_holdings

    _creds = load_sa_credentials()          # 缺 / 壞 JSON → raise
    _pf = os.environ.get(_PORTFOLIO_SHEET_ENV, "").strip()
    _stk = os.environ.get(_STOCK_SHEET_ENV, "").strip()
    if not _pf and not _stk:
        raise ValueError(
            f"{_PORTFOLIO_SHEET_ENV} / {_STOCK_SHEET_ENV} 皆未設定 —— 請設定至少一個"
            "你的 Google Sheet ID(並已分享給 service account 的 client_email);"
            "或改用命令列指定代號:python scripts/diagnose_etf_total_return_fix.py 0050 0056")
    _out: list[dict] = []
    for _sid in (_pf, _stk):
        if _sid:
            _out += read_holdings(_sid, _creds)
    return _out


def _split_etf_vs_other(raw_tickers: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """原始代號清單 → (要分析的 ETF 代號, 不分析的清單 [(代號, 原因)])。

    ETF / 個股判別走 L0 SSOT `classify_asset_kind`(代號規則);ETF 代號再過
    `normalize_etf_ticker`(台股 4-6 碼自動補 .TW,與三個 ETF Tab 同一支)。
    §1:個股不是「跳過」,是**列出來說明本 bug 不影響**(`calc_total_return_1y` 全 repo
    3 個 production 呼叫端都在 ETF 路徑上)。
    """
    from shared.dividend_station_thresholds import KIND_ETF, classify_asset_kind
    from src.compute.etf.etf_helpers import normalize_etf_ticker

    _etfs: list[str] = []
    _others: list[tuple[str, str]] = []
    _seen: set[str] = set()
    for _raw in raw_tickers:
        _raw = str(_raw or "").strip()
        if not _raw:
            continue
        if classify_asset_kind(_raw) != KIND_ETF:
            _others.append((_raw, "個股 / 特別股 —— 不走 ETF 1Y 含息報酬路徑,本 bug 不影響"))
            continue
        _tk = normalize_etf_ticker(_raw)
        if not _tk:
            _others.append((_raw, "代號正規化後為空,無法查詢"))
            continue
        if _tk in _seen:
            continue
        _seen.add(_tk)
        _etfs.append(_tk)
    return _etfs, _others


# ──────────────────────────────────────────────────────────────────────
# 逐檔取數 + 兩遍判定
# ──────────────────────────────────────────────────────────────────────
def _fetch_bundle(ticker: str) -> dict:
    """單檔 I/O,鏡像 `etf_tab_grp_compare._fetch_one_etf` 的取數(不含算欄位)。

    抓 5y 價格 / 配息 / info / 中文名 / 品質 / 追蹤誤差 benchmark。任何一項失敗
    只 log 不炸整檔(與 UI 行為一致);價格空 → `df=None`,後續由
    `build_etf_score_row` 標 `error='無 K 線資料'`(§1 不腦補)。
    """
    from src.compute.etf.etf_calc import auto_detect_benchmark, calc_tracking_error
    from src.compute.etf.etf_quality import compute_etf_quality
    from src.data.etf import (
        fetch_etf_dividends, fetch_etf_info, fetch_etf_price, fetch_etf_zh_name,
    )

    _b = {'ticker': ticker, 'df': None, 'divs': None, 'info': {},
          'zh_name': None, 'quality': None, 'te': None, 'fetch_err': None}
    try:
        _df = fetch_etf_price(ticker, period='5y')
        if _df is None or getattr(_df, 'empty', True) or 'Close' not in _df.columns:
            _b['fetch_err'] = '無 K 線資料(Yahoo 回空 —— 常見原因:海外 IP 403 / proxy 未生效 / 代號錯誤)'
            return _b
        _b['df'] = _df
        _b['divs'] = fetch_etf_dividends(ticker)
        _b['info'] = fetch_etf_info(ticker) or {}
        try:
            _b['zh_name'] = fetch_etf_zh_name(ticker)
        except Exception as _e_nm:  # noqa: BLE001 — 名稱抓不到不影響數字
            print(f'[diag] {ticker} 中文名抓取失敗:{type(_e_nm).__name__}: {_e_nm}',
                  file=sys.stderr)
        try:
            _b['quality'] = compute_etf_quality(ticker)
        except Exception as _e_q:  # noqa: BLE001 — 品質缺 → 綜合分少一維(rescale),不炸
            print(f'[diag] {ticker} 品質評等失敗:{type(_e_q).__name__}: {_e_q}',
                  file=sys.stderr)
        try:
            _bench = auto_detect_benchmark(ticker)
            if _bench and _bench != ticker:
                _bdf = fetch_etf_price(_bench, period='5y')
                if _bdf is not None and not _bdf.empty:
                    _b['te'] = calc_tracking_error(_df, _bdf)
        except Exception as _e_te:  # noqa: BLE001 — TE 缺 → 少一個紅旗來源,不炸
            print(f'[diag] {ticker} 追蹤誤差計算失敗:{type(_e_te).__name__}: {_e_te}',
                  file=sys.stderr)
    except Exception as _e:  # noqa: BLE001
        _b['fetch_err'] = f'{type(_e).__name__}: {str(_e)[:120]}'
    return _b


def _rows_and_lamps(bundle: dict, role: str) -> dict:
    """一檔 → {row_before, row_after, lamp_before, lamp_after}(判定全走 production)。

    修前那一遍包在 `_prefix_bug_active(divs)` 裡跑;`_compute_etf_warroom_row` 有
    `@st.cache_data`,兩遍**同一組參數**會命中同一個 cache key,所以每次呼叫前都
    `.clear()` 強制重算(底層 `_fetch_etf_price_max` / `fetch_etf_dividends` /
    `fetch_etf_info` 各有自己的 cache,不會因此多打一次網路)。
    """
    import pandas as pd

    from src.compute.etf.etf_calc import _compute_etf_warroom_row
    from src.compute.etf.etf_scoring_helpers import build_etf_score_row

    _tk = bundle['ticker']
    _df = bundle['df']
    _divs = bundle['divs'] if bundle['divs'] is not None else pd.Series(dtype=float)

    def _build() -> dict:
        return build_etf_score_row(_tk, _df, _divs, bundle['info'],
                                   quality=bundle['quality'],
                                   tracking_error=bundle['te'],
                                   zh_name=bundle['zh_name'])

    # ── 修後(＝現行 code 的真實行為)──
    _row_after = _build()
    _name = _row_after.get('name') or _tk
    _compute_etf_warroom_row.clear()
    _lamp_after = _compute_etf_warroom_row(_tk, _name, role)

    # ── 修前(暫時換掉 calc_total_return_1y)──
    with _prefix_bug_active(_divs):
        _row_before = _build()
        _compute_etf_warroom_row.clear()
        _lamp_before = _compute_etf_warroom_row(_tk, _name, role)
    _compute_etf_warroom_row.clear()   # 別把「修前」結果留在 cache 裡

    return {'row_before': _row_before, 'row_after': _row_after,
            'lamp_before': _lamp_before, 'lamp_after': _lamp_after,
            'name': _name, 'role': role}


def _score_batch(rows: list[dict]) -> None:
    """整批 rows → 就地填 composite / stars / rec_verdict(鏡像 etf_tab_grp_compare)。"""
    from src.compute.etf.etf_recommendation import recommend_etf_actions
    from src.compute.etf.etf_scoring_helpers import compute_etf_composite_score

    for _r in rows:
        if _r.get('error'):
            _r['composite'] = None
            _r['stars'] = None
            continue
        _r['composite'], _r['stars'] = compute_etf_composite_score(_r)
    for _r, _v in zip(rows, recommend_etf_actions(rows)):
        _r['rec_verdict'] = f"{_v['icon']} {_v['verdict']}"
        _r['rec_reason'] = _v.get('reason_text', '')


# ──────────────────────────────────────────────────────────────────────
# 呈現
# ──────────────────────────────────────────────────────────────────────
def _lamp_color(lamp) -> str:
    """燈號字串 → 開頭那串**顏色**字元;取不到回 '?'。

    取「一整串」而非第一個字元:衛星燈號的 σ 分級是 🟢 / 🟢🟢 / 🟢🟢🟢 三階同色,
    只看第一個字元會把「便宜價 → 股災價」看成沒變。核心燈號則只有單一顏色字元,
    行為與只取首字相同。
    """
    _s = str(lamp or '').strip()
    _out = ''
    for _c in _s:
        if _c in _LAMP_COLORS:
            _out += _c
        else:
            break
    return _out or '?'


def _short_lamp(lamp) -> str:
    """燈號字串 → 『emoji + 短語』(完整字串在明細區印)。"""
    _s = str(lamp or '').strip()
    if not _s:
        return '—'
    for _sep in ('（', '(', ' ｜', '｜'):
        _i = _s.find(_sep)
        if _i > 0:
            _s = _s[:_i]
    return _s.strip()


def _health_verdict(s) -> str:
    """配息健康度字串 → 只取**分級**，砍掉尾巴的 pp 數字。

    `dividend_health_label` 回的是 `'✅ 雙贏 +2.1pp'` 這種「分級 + 差距」合成字串。
    差距的數字**必然**隨 1Y 報酬變動（那正是本 bug 改到的量），所以直接比字串會讓
    每一檔有配息的 ETF 都被判成「配息健康度改變」—— 那是雜訊，不是使用者要的訊號。
    使用者要知道的是分級本身有沒有翻面（✅ 雙贏 ↔ 🔴 吃本金）。
    """
    _s = str(s or '').strip()
    _parts = _s.split()
    if len(_parts) >= 2 and _parts[-1].endswith('pp'):
        return ' '.join(_parts[:-1])
    return _s


def _fmt(v, digits: int = 2) -> str:
    """數字 → 字串;None → 'None'(**刻意印出來**,§1:算不出來要看得見,不留空白)。"""
    if v is None:
        return 'None'
    try:
        return f'{float(v):.{digits}f}'
    except (TypeError, ValueError):
        return str(v)


def _arrow(a, b, digits: int = 2) -> str:
    """`a→b`;相同時只印一份 + '(不變)'。"""
    _sa, _sb = _fmt(a, digits), _fmt(b, digits)
    return _sa if _sa == _sb else f'{_sa}→{_sb}'


def _stars_str(s) -> str:
    return ('★' * s + '☆' * (5 - s)) if s else '—'


def _analyze(rec: dict) -> dict:
    """一檔的 before/after 結果 → 表格用的一列 + 變化旗標。"""
    _rb, _ra = rec['row_before'], rec['row_after']
    _tb, _ta = _rb.get('total_ret_1y'), _ra.get('total_ret_1y')
    _delta = (None if (_tb is None or _ta is None) else round(_tb - _ta, 2))

    _cb, _ca = _lamp_color(rec['lamp_before'].get('健康燈號')), \
        _lamp_color(rec['lamp_after'].get('健康燈號'))
    _lamp_changed = (_cb != _ca)
    _health_changed = (_health_verdict(_rb.get('dividend_health'))
                       != _health_verdict(_ra.get('dividend_health')))
    _stars_changed = (_rb.get('stars') != _ra.get('stars'))
    _verdict_changed = (_rb.get('rec_verdict') != _ra.get('rec_verdict'))
    _composite_changed = (_rb.get('composite') != _ra.get('composite'))
    _judgement_changed = (_lamp_changed or _health_changed
                          or _stars_changed or _verdict_changed)

    # §1:算不出來的原因要具名,不填估計值
    _reason = None
    if _ra.get('error'):
        _reason = _ra['error']
    elif _ta is None and _tb is None:
        _reason = '1Y 報酬 = None(require_full_period:實際資料跨度不足 365 天的 90%,'\
                  '多為上市未滿 1 年 —— 重跑一百次也一樣,不是暫時性錯誤)'
    elif _ta is None or _tb is None:
        _reason = f'修前/修後只有一邊算得出來(before={_tb!r} / after={_ta!r})—— 請回報,這不該發生'

    return {
        'ticker': rec['row_after'].get('ticker'),
        'name': rec['name'],
        'role': rec['role'],
        'ttl_before': _tb, 'ttl_after': _ta, 'delta': _delta,
        'yield': _ra.get('div_yield'),
        'lamp_before': rec['lamp_before'].get('健康燈號'),
        'lamp_after': rec['lamp_after'].get('健康燈號'),
        'lamp_changed': _lamp_changed,
        'health_before': _rb.get('dividend_health'),
        'health_after': _ra.get('dividend_health'),
        'health_changed': _health_changed,
        'composite_before': _rb.get('composite'), 'composite_after': _ra.get('composite'),
        'composite_changed': _composite_changed,
        'stars_before': _rb.get('stars'), 'stars_after': _ra.get('stars'),
        'stars_changed': _stars_changed,
        'verdict_before': _rb.get('rec_verdict'), 'verdict_after': _ra.get('rec_verdict'),
        'verdict_changed': _verdict_changed,
        'judgement_changed': _judgement_changed,
        'uncomputable_reason': _reason,
    }


def _build_table(analyses: list[dict]):
    """analyses → 排序好的 DataFrame(有變的排最前面)。"""
    import pandas as pd

    def _sort_key(a):
        # 0 = 判定有變、1 = 只有數字變、2 = 完全沒變 / 算不出來
        if a['judgement_changed']:
            _grp = 0
        elif a['delta'] not in (None, 0.0):
            _grp = 1
        else:
            _grp = 2
        return (_grp, -(a['delta'] or 0.0), str(a['ticker']))

    _sorted = sorted(analyses, key=_sort_key)
    _recs = []
    for a in _sorted:
        _recs.append({
            '代號': a['ticker'],
            '名稱': (a['name'] or '')[:14],
            '類型': a['role'],
            '修前1Y%': _fmt(a['ttl_before']),
            '修後1Y%': _fmt(a['ttl_after']),
            '差(pp)': _fmt(a['delta']),
            '配息率%': _fmt(a['yield']),
            '修前燈': _short_lamp(a['lamp_before']),
            '修後燈': _short_lamp(a['lamp_after']),
            '變色': ('🔺 是' if a['lamp_changed'] else '—'),
            '配息健康': _arrow(a['health_before'], a['health_after']),
            '綜合分': _arrow(a['composite_before'], a['composite_after'], 3),
            '星等': _arrow(_stars_str(a['stars_before']), _stars_str(a['stars_after'])),
            '🚦建議': _arrow(a['verdict_before'], a['verdict_after']),
        })
    return pd.DataFrame(_recs), _sorted


def _print_details(sorted_analyses: list[dict]) -> None:
    """判定有變的逐檔印完整燈號字串(表內只放得下短語)。"""
    _changed = [a for a in sorted_analyses if a['judgement_changed']]
    if not _changed:
        print('（沒有任何一檔的判定改變 —— 明細區從缺）')
        return
    for a in _changed:
        print(f"\n■ {a['ticker']} {a['name']}（{a['role']}）")
        print(f"    1Y 含息報酬 : {_fmt(a['ttl_before'])}%  →  {_fmt(a['ttl_after'])}%"
              f"   （高估 {_fmt(a['delta'])} pp；年化配息率 {_fmt(a['yield'])}%）")
        if a['lamp_changed']:
            print(f"    戰情室燈號  : {a['lamp_before']}")
            print(f"                → {a['lamp_after']}")
        if a['health_changed']:
            print(f"    配息健康度  : {a['health_before']}  →  {a['health_after']}")
        if a['stars_changed'] or a['composite_before'] != a['composite_after']:
            print(f"    綜合分/星等 : {_fmt(a['composite_before'], 3)} "
                  f"{_stars_str(a['stars_before'])}  →  "
                  f"{_fmt(a['composite_after'], 3)} {_stars_str(a['stars_after'])}")
        if a['verdict_changed']:
            print(f"    🚦 建議     : {a['verdict_before']}  →  {a['verdict_after']}")


def _print_summary(analyses: list[dict], others: list[tuple[str, str]]) -> None:
    print('\n' + '=' * 78)
    print('摘要')
    print('=' * 78)

    _lamp_ch = [a for a in analyses if a['lamp_changed']]
    if _lamp_ch:
        print(f'\n🚨 有 {len(_lamp_ch)} 檔「戰情室健康燈號」會變色：')
        for a in _lamp_ch:
            print(f'   · {a["ticker"]} {a["name"]}：'
                  f'{_short_lamp(a["lamp_before"])} → {_short_lamp(a["lamp_after"])}')
    else:
        print('\n✅ 沒有任何一檔的「戰情室健康燈號」會變色。')
        print('   （提醒：「衛星」的燈號讀的是 σ 位階、不吃 1Y 報酬 —— '
              '看 _compute_etf_warroom_row 衛星分支；只有「核心」的燈會被這個 bug 影響。）')

    _health_ch = [a for a in analyses if a['health_changed']]
    print(f'\n配息健康度「分級」改變：{len(_health_ch)} 檔'
          '（只算 ✅雙贏 / 🔴吃本金 這層翻面；標籤尾巴的 pp 數字必然跟著變，不算）')
    for a in _health_ch:
        print(f'   · {a["ticker"]} {a["name"]}：{a["health_before"]} → {a["health_after"]}')
    if not _health_ch:
        print('   （無）')

    _star_ch = [a for a in analyses if a['stars_changed']]
    _comp_ch = [a for a in analyses if a['composite_changed']]
    print(f'\n綜合分下修：{len(_comp_ch)} 檔；其中星等掉級：{len(_star_ch)} 檔')
    for a in _star_ch:
        print(f'   · {a["ticker"]} {a["name"]}：'
              f'{_stars_str(a["stars_before"])} → {_stars_str(a["stars_after"])}'
              f'（綜合分 {_fmt(a["composite_before"], 3)} → {_fmt(a["composite_after"], 3)}）')

    _verdict_ch = [a for a in analyses if a['verdict_changed']]
    print(f'\n🚦 留/觀察/換 建議改變：{len(_verdict_ch)} 檔')
    for a in _verdict_ch:
        print(f'   · {a["ticker"]} {a["name"]}：'
              f'{a["verdict_before"]} → {a["verdict_after"]}')
    if not _verdict_ch:
        print('   （無）')

    _with_delta = [a for a in analyses if a['delta'] is not None]
    if _with_delta:
        _max = max(_with_delta, key=lambda a: a['delta'])
        print(f'\n📏 高估幅度最大：{_max["ticker"]} {_max["name"]} '
              f'—— 修前 {_fmt(_max["ttl_before"])}% vs 修後 {_fmt(_max["ttl_after"])}%，'
              f'差 {_fmt(_max["delta"])} pp')
        _avg = sum(a['delta'] for a in _with_delta) / len(_with_delta)
        print(f'   （{len(_with_delta)} 檔平均高估 {_avg:.2f} pp）')
    else:
        print('\n📏 高估幅度：無可比較的檔位（見下方「算不出來」清單）。')

    _bad = [a for a in analyses if a['uncomputable_reason']]
    print(f'\n⚠️ 算不出來：{len(_bad)} 檔'
          '（§1：據實列出，沒有填估計值、沒有靜默跳過）')
    for a in _bad:
        print(f'   · {a["ticker"]} {a["name"] or ""}：{a["uncomputable_reason"]}')
    if not _bad:
        print('   （無）')

    if others:
        print(f'\nℹ️ 非 ETF、未納入本表：{len(others)} 檔')
        for _tk, _why in others:
            print(f'   · {_tk}：{_why}')


# ──────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description='ETF 1Y 含息報酬「重複計息」修正前後對照表（唯讀診斷，不改任何檔案）',
        epilog='用法 A：python scripts/diagnose_etf_total_return_fix.py'
               '（讀 Google Sheet 持股，需 GCP_SERVICE_ACCOUNT_JSON + *_SHEET_ID）；'
               '用法 B：python scripts/diagnose_etf_total_return_fix.py 0050 0056 00878')
    ap.add_argument('tickers', nargs='*',
                    help='ETF 代號（留空 = 讀 Google Sheet 持股）；台股純數字會自動補 .TW')
    ap.add_argument('--csv', default='',
                    help='把主表另存 CSV（utf-8-sig，Excel 可直接開）')
    ap.add_argument('--verbose', action='store_true',
                    help='保留 streamlit bare-mode 提示訊息（預設靜音）')
    args = ap.parse_args(argv)

    if not args.verbose:
        _quiet_bare_mode_warnings()

    print('=' * 78)
    print(f'ETF「1Y 含息報酬重複計息」修正影響對照表   as_of={_tw_now()} (TW)')
    print('修前算式 (p_end-p_start+div_sum)/p_start  vs  修後 (p_end-p_start)/p_start')
    print('修前值由本腳本重建（現行 code 已無舊算式，commit 1a0992b 已修）')
    print('=' * 78)

    # ── 決定要分析哪些代號 ──
    if args.tickers:
        _raw = list(args.tickers)
        print(f'\n[來源] 命令列指定 {len(_raw)} 個代號：{", ".join(_raw)}')
    else:
        print('\n[來源] Google Sheet 持股（Service Account，與每日推播 cron 同一條路）')
        try:
            _hold = _read_holdings_from_sheets()
        except Exception as _e:
            print(f'\n❌ 讀不到持股：{type(_e).__name__}: {_e}', file=sys.stderr)
            print('   → 改用命令列指定代號即可跳過 Google 憑證，例如：\n'
                  '     python scripts/diagnose_etf_total_return_fix.py 0050 0056 00878',
                  file=sys.stderr)
            return 1
        _raw = [str(h.get('ticker', '') or '').strip() for h in _hold]
        _raw = [t for t in _raw if t]
        print(f'   讀到 {len(_raw)} 檔持股：{", ".join(_raw) if _raw else "(空)"}')
        if not _raw:
            print('\n❌ Sheet 讀得到但持股清單是空的 —— 不偽造清單（§1）。'
                  '請確認 portfolios 分頁有資料，或改用命令列指定代號。', file=sys.stderr)
            return 1

    _etfs, _others = _split_etf_vs_other(_raw)
    if not _etfs:
        print('\n❌ 這批代號裡沒有任何 ETF，本 bug 不影響。', file=sys.stderr)
        for _tk, _why in _others:
            print(f'   · {_tk}：{_why}', file=sys.stderr)
        return 1
    print(f'   → 待分析 ETF {len(_etfs)} 檔：{", ".join(_etfs)}')
    if _others:
        print(f'   → 非 ETF {len(_others)} 檔（表尾列出，不納入計算）')

    # ── 夏普無風險利率注入（與畫面同源；失敗維持 SSOT fallback）──
    try:
        from src.services.etf_scoring_service import ensure_etf_rf_injected
        _rf = ensure_etf_rf_injected()
        _rf_txt = (f'FEDFUNDS {_rf:.2f}%' if _rf is not None
                   else 'SSOT fallback（FEDFUNDS 抓不到）')
        print(f'   → 夏普無風險利率：{_rf_txt}'
              '（修前 / 修後同一個值，不影響差值）')
    except Exception as _e_rf:  # noqa: BLE001 — 注入失敗維持 fallback，不影響 before/after 差值
        print(f'   → 夏普無風險利率注入失敗（維持 fallback）：{type(_e_rf).__name__}: {_e_rf}')

    # ── 逐檔取數 + 兩遍判定 ──
    from src.compute.etf.etf_helpers import auto_role

    _recs = []
    for _i, _tk in enumerate(_etfs, 1):
        print(f'\n[{_i}/{len(_etfs)}] {_tk} 取數中 ...')
        _bundle = _fetch_bundle(_tk)
        if _bundle['fetch_err']:
            print(f'    ⚠️ {_bundle["fetch_err"]}')
        _recs.append(_rows_and_lamps(_bundle, auto_role(_tk)))

    # ── 整批評分（同類重疊偵測需要整批，故 before / after 各跑一次）──
    _score_batch([r['row_before'] for r in _recs])
    _score_batch([r['row_after'] for r in _recs])

    _analyses = [_analyze(r) for r in _recs]
    _df, _sorted = _build_table(_analyses)

    import pandas as pd
    pd.set_option('display.unicode.east_asian_width', True)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 260)

    print('\n' + '=' * 78)
    print('對照表（判定有變的排最前面）')
    print('=' * 78)
    print(_df.to_string(index=False))

    print('\n' + '=' * 78)
    print('明細（僅列判定有變者，完整燈號字串）')
    print('=' * 78)
    _print_details(_sorted)

    _print_summary(_sorted, _others)

    if args.csv:
        _p = Path(args.csv).expanduser()
        _p.parent.mkdir(parents=True, exist_ok=True)
        _df.to_csv(_p, index=False, encoding='utf-8-sig')
        print(f'\n💾 主表已存：{_p}')

    print('\n（本腳本唯讀：未修改任何 production code，'
          '「修前」是在記憶體中暫時替換 calc_total_return_1y 跑出來的。）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
