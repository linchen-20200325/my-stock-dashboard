"""tests/test_etf_price_basis_invariant.py — 不變量:**餵給總報酬算式的價格，必須來自還原價來源**。

這條為什麼要存在(它取代不了、但補上了 `test_etf_price_proxy.py` §auto_adjust 的死角)
══════════════════════════════════════════════════════════════════════════════
`test_etf_price_proxy.py` 的 §auto_adjust 兩條釘子釘的是**一行程式**:
`etf_fetch._fetch_etf_price_max` 裡的 `history(period='max', auto_adjust=True)`。
寫那兩條的人自己指出了它的極限 ——

    如果有人把 `build_etf_score_row` 的取價路由到另一個 fetcher
    (FinMind 原始價、TWSE 原始價、`etf_fetch.py` 裡另一個 `yf.download`),
    `auto_adjust` 釘子**仍然全綠**,因為它釘的那一行已經不在路徑上了。

所以本檔改釘**不變量**而不是某一行。不變量拆成兩半,兩半**互相扣住**:

  A(執行面)「allow-list 裡的每個來源,都真的是還原價來源」
      —— 每個 allow-list 成員都會被**實際呼叫**一次(假 yfinance),必須同時證明:
         ① 它在回傳的 df 上蓋 `attrs['price_basis'] == 'adjusted'`;
         ② 它**真的向上游要了**還原價(`history(..., auto_adjust=True)`)。
      光蓋章不算數 —— 沒有 ② 的話,allow-list 就退化成「相信我這是還原價」的名單。

  B(靜態面)「除了 allow-list,沒有別的東西餵得到總報酬算式」
      —— AST 追出所有「df 匯入口」(`calc_total_return_1y(df,…)` /
         `build_etf_score_row(t, df,…)`)的 df 是**哪個 fetcher** 產的,
         那個 fetcher 必須在 allow-list 內。

  合起來:B 保證路徑上只會出現 allow-list 的名字,A 保證那些名字名副其實。
  把取價改路由到 FinMind 原始價 → B 紅(未登記);硬把它加進 allow-list → A 紅
  (沒蓋章 / 沒要 auto_adjust)。**兩條路都堵住,才叫不變量。**

⚠️ B 用 import 解析而不是比對「呼叫端寫了什麼名字」——這是實測過的必要條件,不是潔癖
──────────────────────────────────────────────────────────────────────────────
`src/ui/etf/etf_tab_grp_compare.py` 寫的是

    from src.services.etf_grp_compare_service import get_etf_price as fetch_etf_price

呼叫端看起來叫 `fetch_etf_price`,實際是 L3 的 `get_etf_price`。純比對名字會被
**別名**騙過去(`from x import raw_price as fetch_etf_price` 一樣過關)。所以 B 會把
local name 解回 `(module, symbol)` 再 `import` 出真正的函式物件來比對 —— barrel
re-export(`src.data.etf` ↔ `src.data.etf.etf_fetch`)因為是同一個物件,也自動收斂,
不必在名單裡列出每一條 import 路徑。

⚠️ 為什麼**不**在 `calc_total_return_1y` 裡加 runtime 斷言(誠實交代這個取捨)
──────────────────────────────────────────────────────────────────────────────
「算式端斷言 `df.attrs['price_basis']` 存在」聽起來更直接,但:
  * 該函式的既有測試(`test_etf_total_return_no_double_count.py` 等)全部餵**合成 df**
    —— 合成 df 沒有 attrs,加硬斷言等於讓演算法拒絕自己的單元測試;
  * 退而求其次寫成「只印 warning」,就會變成沒人看的 stderr 一行 —— 那正是
    「看起來有釘、實際上釘不到」,比不釘更糟(它會讓後人以為有保護)。
本檔改成 **build time(CI)** 擋:真正的風險是「有人改路由」,那是**改 code** 的動作,
在 CI 擋得住,不必付 runtime 的代價。

⚠️ 本檔的已知極限(別把它當成「不可能出錯」)
──────────────────────────────────────────────────────────────────────────────
1. A ② 只認得**yfinance 形狀**的上游。若將來 allow-list 收了一個 FinMind / TWSE
   來源,`_run_with_recording_yf` 會因為「假 yfinance 從頭到尾沒被碰過」而**紅**
   (見 `test_every_allowed_source_actually_requests_adjusted_prices` 的
   `stub_was_used` 斷言)—— 刻意讓它紅而不是默默略過,逼下一個人為新上游補對應的
   錄製器,而不是收下一個沒被驗證的來源。
2. B 只追**同一個函式內**的 `名字 = fetcher(...)`。刻意繞(把 df 塞進 dict/list 再
   取出來、跨函式傳三層)追不到 —— 但那種寫法會落到「無法解析」而**紅**,不是靜默通過。
3. B 的掃描範圍是 `src/**`(production)。`scripts/**` 的診斷 CLI 不在內 ——
   與 `test_etf_total_return_no_double_count.py` 既有 G/H 節同一範圍,刻意一致。
"""
from __future__ import annotations

import ast
import importlib
import pathlib

import numpy as np
import pandas as pd
import pytest

from src.compute.etf import etf_calc
from src.compute.etf.etf_scoring_helpers import build_etf_score_row
from src.data.etf import etf_fetch

_REPO = pathlib.Path(__file__).resolve().parents[1]
_SRC = _REPO / 'src'

#: 標記值的 SSOT —— 從 production 引入,不在測試裡複寫字面值(§3.3 反捏造)。
PRICE_BASIS_ADJUSTED = etf_fetch.PRICE_BASIS_ADJUSTED


# ════════════════════════════════════════════════════════════════════
# allow-list —— 「可以餵給總報酬算式的價格來源」
# ════════════════════════════════════════════════════════════════════
#
# 新增一筆的門檻(不是形式,是本檔會實際驗的):
#   1. 它必須在回傳 df 上蓋 `attrs['price_basis'] = PRICE_BASIS_ADJUSTED`;
#   2. 它必須真的向上游要還原價(目前:`history(..., auto_adjust=True)`);
#   3. 它必須能用 `fn('0050.TW')` 單參數呼叫(period 走預設值)。
# 三條任一不成立,A 節就會紅。**不要**為了讓它綠而放寬 A 節 —— A 節放寬,
# 這份名單就退回「口頭保證」。
def _allowed_sources() -> dict:
    """{ 顯示名: 函式物件 } —— 用**物件**比對,barrel 別名自動收斂。"""
    from src.data.etf import fetch_etf_price
    from src.services.etf_grp_compare_service import get_etf_price
    return {
        'src.data.etf.fetch_etf_price': fetch_etf_price,
        'src.services.etf_grp_compare_service.get_etf_price': get_etf_price,
    }


#: 「df 匯入口」—— 函式名 → df 是第幾個位置參數(0-based)。
#: `build_etf_score_row` 的 df 是 caller 注入的,所以它本身也算一個匯入口:
#: 追到「df 是本函式的參數」時,責任就轉移到它的呼叫端(而呼叫端同樣在本表裡被掃)。
_DF_SINKS: dict[str, int] = {
    'calc_total_return_1y': 0,
    'build_etf_score_row': 1,
}


# ════════════════════════════════════════════════════════════════════
# A. 執行面 —— allow-list 的每一筆都要「名副其實」
# ════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _no_fake_prices_left_behind():
    """本檔會把**假**價格灌進 `_fetch_etf_price_max` 的 st.cache_data,跑完要清掉。

    monkeypatch 只還原 `etf_fetch.yf` 這個屬性,**還原不了快取內容** ——
    假 df 會以 key `'0050.TW'` 留在跨測試共享的 cache 裡,下一個呼叫
    `fetch_etf_price('0050.TW')` 的測試就吃到本檔捏的直線價格序列。
    這種汙染只在特定執行順序下發作(本 repo 有 module 級 stub 汙染害 CI 全滅的
    實績,見 `test_zz_streamlit_pollution_lock.py`),所以前後都清,不賭順序。
    """
    etf_fetch._fetch_etf_price_max.clear()
    try:
        yield
    finally:
        etf_fetch._fetch_etf_price_max.clear()


def _sample_history() -> pd.DataFrame:
    idx = pd.date_range('2022-01-03', periods=700, freq='B')
    _line = np.linspace(10.0, 20.0, 700)
    return pd.DataFrame(
        {'Open': _line, 'High': _line, 'Low': _line, 'Close': _line,
         'Volume': np.full(700, 1000)},
        index=idx,
    )


def _run_with_recording_yf(monkeypatch, fn):
    """用假 yfinance 跑一次 `fn('0050.TW')`,回傳 (df, 上游收到的 kwargs, 有沒有被碰過)。"""
    seen: dict = {}
    _hist = _sample_history()

    class _RecTicker:
        def __init__(self, ticker):
            seen['ticker'] = ticker

        def history(self, *args, **kwargs):
            seen['kwargs'] = kwargs
            return _hist.copy()

        @property
        def dividends(self):
            return pd.Series(dtype=float)

    class _RecYF:
        Ticker = _RecTicker

    monkeypatch.setattr(etf_fetch, 'yf', _RecYF)
    # `_fetch_etf_price_max` 帶 @st.cache_data —— 不清就吃到別條測試留下的快取,
    # 假 yfinance 根本不會被呼叫,A 節會變成假通過(這是實測踩過的)。
    etf_fetch._fetch_etf_price_max.clear()
    _df = fn('0050.TW')
    return _df, seen.get('kwargs'), ('ticker' in seen)


@pytest.mark.parametrize('label', sorted(_allowed_sources()))
def test_every_allowed_source_stamps_the_adjusted_marker(monkeypatch, label):
    """allow-list 的每個來源都必須在 df 上蓋還原價標記。"""
    _fn = _allowed_sources()[label]
    _df, _kwargs, _stub_used = _run_with_recording_yf(monkeypatch, _fn)
    assert _stub_used, (
        f'{label} 沒有碰到假 yfinance —— 本測試沒有真的驗到它。'
        '若它換了上游(FinMind / TWSE 等),請為那個上游補對應的錄製器,'
        '不要把這條斷言拿掉(拿掉 = allow-list 退回口頭保證)。'
    )
    assert getattr(_df, 'attrs', {}).get('price_basis') == PRICE_BASIS_ADJUSTED, (
        f"{label} 回傳的 df 沒有 attrs['price_basis'] == {PRICE_BASIS_ADJUSTED!r} —— "
        f"實際 attrs = {getattr(_df, 'attrs', {})}。"
        '含息總報酬把「價差本身已含息」當前提,這個標記就是那個前提的機器可讀出處;'
        '沒有它,下游無從分辨手上這份 Close 是還原價還是原始價。'
    )


@pytest.mark.parametrize('label', sorted(_allowed_sources()))
def test_every_allowed_source_actually_requests_adjusted_prices(monkeypatch, label):
    """而且要**真的**向上游要還原價 —— 只蓋章不算數。

    這條與上一條的分工:上一條驗「它自稱是還原價」,本條驗「它沒有說謊」。
    只留上一條的話,任何 fetcher 只要多寫一行 `attrs['price_basis']='adjusted'`
    就能混進 allow-list,而那正是這份名單最該防的事。
    """
    _fn = _allowed_sources()[label]
    _df, _kwargs, _stub_used = _run_with_recording_yf(monkeypatch, _fn)
    assert _stub_used, f'{label} 沒有碰到假 yfinance(理由同上一條)'
    assert (_kwargs or {}).get('auto_adjust') is True, (
        f'{label} 對上游的請求是 {_kwargs} —— 缺 auto_adjust=True。'
        '它蓋了「還原價」的章,卻沒有向上游要還原價:Close 會靜默變成純價差,'
        '含息總報酬低估一整年配息,而所有吃合成 df 的守衛都不會紅。'
    )


def test_marker_survives_all_the_way_to_the_formula(monkeypatch):
    """標記要活到 `calc_total_return_1y` **真正收到 df 的那一刻**。

    為什麼要有這條:`DataFrame.attrs` 在 pandas 的部分操作會掉(concat / merge 等),
    而這條路上經過 `@st.cache_data` 往返、`df.loc[...]` 切片、`validate_in_log_mode`、
    再穿過 `build_etf_score_row`。**不能假設它活著,要實測。**
    (實測環境 pandas 3.0.5:全程存活;若哪天 pandas 改了行為,這條會紅在
     「標記掉了」而不是等到有人發現數字不對。)
    """
    _df, _kwargs, _stub_used = _run_with_recording_yf(
        monkeypatch, _allowed_sources()['src.data.etf.fetch_etf_price'])
    assert _stub_used

    _captured: dict = {}
    _orig = etf_calc.calc_total_return_1y

    def _spy(_d, **_kw):
        _captured['attrs'] = dict(getattr(_d, 'attrs', {}))
        return _orig(_d, **_kw)

    # `build_etf_score_row` 是 function-local import,patch 模組屬性會被它看到。
    monkeypatch.setattr(etf_calc, 'calc_total_return_1y', _spy)
    build_etf_score_row('0050.TW', _df, pd.Series(dtype=float), {})

    assert 'attrs' in _captured, (
        'build_etf_score_row 沒有呼叫 calc_total_return_1y —— '
        '本測試沒驗到東西(管線變了,請更新本檔)'
    )
    assert _captured['attrs'].get('price_basis') == PRICE_BASIS_ADJUSTED, (
        f"標記沒活到算式入口,實際 attrs = {_captured['attrs']} —— "
        'df.attrs 在管線中途被弄丟了(pandas 操作換過?中間多了一次 concat/merge?)。'
        '在修好之前,「餵進來的是還原價」這件事在算式端就是不可驗證的。'
    )


# ════════════════════════════════════════════════════════════════════
# B. 靜態面 —— 沒有登記過的來源餵不到總報酬算式
# ════════════════════════════════════════════════════════════════════
def _import_map(tree: ast.AST) -> dict[str, tuple[str, str]]:
    """local name → (module, 原始 symbol)。含函式內的 late import(本 repo 大量使用)。"""
    _out: dict[str, tuple[str, str]] = {}
    for _n in ast.walk(tree):
        if isinstance(_n, ast.ImportFrom) and _n.module and not _n.level:
            for _a in _n.names:
                _out[_a.asname or _a.name] = (_n.module, _a.name)
    return _out


def _resolve(local_name: str, imap: dict[str, tuple[str, str]]):
    """把呼叫端寫的名字解成真正的函式物件(解不出來回 None)。"""
    _hit = imap.get(local_name)
    if _hit is None:
        return None
    _mod, _sym = _hit
    try:
        return getattr(importlib.import_module(_mod), _sym, None)
    except Exception:
        return None


def _enclosing_functions(tree: ast.AST) -> list[ast.FunctionDef]:
    return [_n for _n in ast.walk(tree)
            if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _owner_function(tree: ast.AST, node: ast.AST):
    """找出包住 node 的**最內層**函式。"""
    _best = None
    for _fn in _enclosing_functions(tree):
        if any(_sub is node for _sub in ast.walk(_fn)):
            if _best is None or _fn.lineno > _best.lineno:
                _best = _fn
    return _best


def _param_names(fn) -> set[str]:
    _a = fn.args
    return {_p.arg for _p in
            (_a.posonlyargs + _a.args + _a.kwonlyargs
             + ([_a.vararg] if _a.vararg else []) + ([_a.kwarg] if _a.kwarg else []))}


def _sink_call_sites():
    """掃出 `src/**` 所有 df 匯入口的呼叫,產出 (檔, 行, sink 名, df 參數 node, tree)。"""
    for _p in sorted(_SRC.rglob('*.py')):
        _src = _p.read_text(encoding='utf-8')
        if not any(_k in _src for _k in _DF_SINKS):
            continue
        _tree = ast.parse(_src, filename=str(_p))
        for _n in ast.walk(_tree):
            if not isinstance(_n, ast.Call):
                continue
            _name = getattr(_n.func, 'id', getattr(_n.func, 'attr', None))
            if _name not in _DF_SINKS:
                continue
            _idx = _DF_SINKS[_name]
            _arg = _n.args[_idx] if len(_n.args) > _idx else None
            yield _p, _n.lineno, _name, _arg, _tree, _n


def test_sink_scan_is_not_vacuous():
    """先證明掃得到東西 —— 否則下面那條會在「一個呼叫都沒找到」時假通過。"""
    _sites = list(_sink_call_sites())
    _files = {_p.name for _p, *_ in _sites}
    assert len(_sites) >= 4, f'df 匯入口只掃到 {len(_sites)} 個,守衛疑似失效'
    assert _files >= {'etf_calc.py', 'etf_scoring_helpers.py'}, (
        f'兩個已知的 L2 匯入口沒被掃到(掃到:{sorted(_files)})'
    )


def test_only_registered_adjusted_sources_reach_the_total_return_formula():
    """**本檔的主條**:餵給總報酬算式的 df,只能來自 allow-list 的還原價來源。

    ⚠️ 後人看到本條紅燈,先讀本檔開頭那段 —— 它幾乎一定是在說:
    「你把取價改路由到一個沒有登記過的 fetcher 了」。正解是確認那個新來源
    **真的是還原價**、再把它加進 `_allowed_sources()`(加進去之後 A 節會實際跑它,
    蓋章與 auto_adjust 兩關都要過)。**不要**為了讓它綠而把匯入口從 `_DF_SINKS`
    拿掉 —— 那等於把守衛的眼睛遮起來。
    """
    _allowed = set(_allowed_sources().values())
    _bad: list[str] = []

    for _p, _lineno, _sink, _arg, _tree, _call in _sink_call_sites():
        _where = f'{_p.relative_to(_REPO)}:{_lineno} {_sink}(...)'
        if _arg is None:
            continue                                   # df 走 keyword / 預設值
        if isinstance(_arg, ast.Constant):
            continue                                   # build_etf_score_row(t, None, ...) 的錯誤列
        if not isinstance(_arg, ast.Name):
            _bad.append(f'{_where}: df 參數不是單純變數 ({ast.unparse(_arg)}) —— 無法追來源')
            continue

        _fn = _owner_function(_tree, _call)
        if _fn is None:
            _bad.append(f'{_where}: 不在任何函式內,無法追來源')
            continue

        # ① df 是本函式的參數 → 責任轉移給呼叫端(呼叫端本身也在掃描範圍內)
        if _arg.id in _param_names(_fn) and _sink in _DF_SINKS:
            continue

        # ② df 由本函式內的賦值產生 → 右手邊必須是 allow-list 的 fetcher 呼叫
        _assigns = [_n for _n in ast.walk(_fn)
                    if isinstance(_n, ast.Assign)
                    and any(getattr(_t, 'id', None) == _arg.id for _t in _n.targets)
                    and _n.lineno < _lineno]
        if not _assigns:
            _bad.append(f'{_where}: 追不到 `{_arg.id}` 的來源(既非參數也無賦值)')
            continue
        _rhs = max(_assigns, key=lambda _n: _n.lineno).value
        if not isinstance(_rhs, ast.Call):
            _bad.append(f'{_where}: `{_arg.id}` 不是直接由 fetcher 產生 ({ast.unparse(_rhs)})')
            continue
        _called = getattr(_rhs.func, 'id', getattr(_rhs.func, 'attr', None))
        _obj = _resolve(_called, _import_map(_tree))
        if _obj is None:
            _bad.append(f'{_where}: `{_called}` 解析不出來源模組(未 import?動態取得?)')
        elif _obj not in _allowed:
            _bad.append(
                f'{_where}: `{_arg.id}` 來自 `{_called}` '
                f'(實際是 {getattr(_obj, "__module__", "?")}.{getattr(_obj, "__qualname__", "?")}) '
                '—— 不在還原價來源 allow-list 內'
            )

    assert not _bad, (
        '有未登記的價格來源餵到總報酬算式 —— 「含息」這個前提在這些路徑上不成立:\n  '
        + '\n  '.join(_bad)
        + '\n\n若那個來源確實是還原價,請加進本檔 `_allowed_sources()`;'
          'A 節會實際執行它,驗它有蓋章且真的向上游要了 auto_adjust=True。'
    )


if __name__ == '__main__':
    import sys
    sys.exit(pytest.main([__file__, '-q']))
