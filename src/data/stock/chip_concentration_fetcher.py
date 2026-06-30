"""src/data/stock/chip_concentration_fetcher.py — 集保股權分散表 fetcher(L1 Data)。

v18.426 Phase 2 Batch 3b:從 `src/ui/tabs/chip_radar.py:30-258`(L5 UI)抽出。

**動機**:Phase 1 §0.11 audit 點名 R-UI-FETCH-2 — L5 UI Tab 不應定義 L1 fetcher
(含 `pd.read_html` 業務 parsing 邏輯)。違反 §8.2 + EX-PASSTHRU-1 規範。

**資料源**:norway.twsthr.info `StockHolders.aspx?stock={代號}`(集保戶股權分散表,
每週更新)。透過 `proxy_helper.fetch_url`(NAS Squid Proxy → 自動降級直連 + 3 次重試)
+ 隨機 User-Agent 防爬。

**回溯相容**:`src/ui/tabs/chip_radar.py:fetch_chip_concentration` 改 thin re-export,
caller(`render_chip_radar`)無需改 import path。

**§8.2.A EX-CACHE-1 letter compliance**:條件 import streamlit + _NoOpST fallback,
僅用 `@st.cache_data` 裝飾器(無真 UI 呼叫)。

**回傳契約**(dict,cache-safe — 不依賴 DataFrame.attrs 在快取後存活):
```
{
    'df':        DataFrame(欄位:日期 / 大戶比例 / 散戶人數;失敗為空),
    'err':       str(''=成功),
    'tables':    list[dict](診斷:每個 read_html 表格的 shape/columns/preview),
    'html_head': str(read_html 失敗時保留 HTML 開頭片段),
}
```

對外 API:
- `fetch_chip_concentration(ticker: str) -> dict` — 主 fetcher
- `TWSTHR_URL` / `_UA_POOL` — 常數(test diagnostics 可用)
"""
from __future__ import annotations

import pandas as pd

# §8.2.A EX-CACHE-1:條件 import streamlit + 無 UI 呼叫 fallback。
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
    st = _NoOpST()  # noqa

from shared.ttls import TTL_1DAY
from src.data.core.provenance import prov_log

TWSTHR_URL = 'https://norway.twsthr.info/StockHolders.aspx?stock={ticker}'

_UA_POOL = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
)


# ══════════════════════════════════════════════════════════════════════════════
# 解析輔助(純函式)
# ══════════════════════════════════════════════════════════════════════════════
def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    """攤平 MultiIndex 欄位成單層字串,並去頭尾空白。"""
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [
            ' '.join(str(x) for x in tup if str(x) not in ('nan', 'None')).strip()
            for tup in out.columns
        ]
    else:
        out.columns = [str(c).strip() for c in out.columns]
    return out


def _to_num(v) -> float:
    """把 '12.3%' / '1,234' / ' 56 ' 之類字串轉為 float;無法解析回 NaN。"""
    import re as _re
    s = str(v).strip()
    if not s or s.lower() in ('nan', 'none', '-', '--'):
        return float('nan')
    s = _re.sub(r'[^0-9.\-]', '', s)
    if s in ('', '-', '.', '-.'):
        return float('nan')
    try:
        return float(s)
    except ValueError:
        return float('nan')


def _find_col(cols: list[str], keywords: tuple[str, ...]) -> str | None:
    for c in cols:
        if any(k in str(c) for k in keywords):
            return c
    return None


def _find_major_col(cols: list[str]) -> str | None:
    """大戶持股『比例』欄:優先同時含大戶關鍵字 + 比例/率/% 字樣,再退而求其次。"""
    _major = ('大股東', '大戶', '400張', '1000張', '千張', '集中')
    _ratio = ('比例', '率', '%', '占', '佔', '百分比', '百分點')
    # pass1:大戶 + 比例
    for c in cols:
        cl = str(c)
        if any(m in cl for m in _major) and any(r in cl for r in _ratio):
            return c
    # pass2:純大戶關鍵字(可能就是比例欄)
    return _find_col(cols, _major)


def _parse_date_series(s: pd.Series) -> pd.Series:
    """盡量把日期欄轉 datetime:先一般解析,命中率低時退 %Y%m%d(純數字)。"""
    raw = s.astype(str).str.strip()
    out = pd.to_datetime(raw, errors='coerce')
    if out.notna().sum() < max(1, len(raw)) * 0.5:
        digits = raw.str.replace(r'[^0-9]', '', regex=True)
        out2 = pd.to_datetime(digits, format='%Y%m%d', errors='coerce')
        if out2.notna().sum() > out.notna().sum():
            out = out2
    return out


def _adaptive_parse(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """從 read_html 的多個表格中挑最像「股權分散時序」的一張並抽三欄。

    回傳欄位:日期 / 大戶比例 / 散戶人數(缺的欄補 NaN);找不到回空 DataFrame。
    """
    best = None
    best_score = -1.0
    for t in tables:
        if t is None or getattr(t, 'empty', True) or t.shape[1] < 2:
            continue
        ft = _flatten_cols(t)
        # read_html 未抓到表頭時欄名是整數索引('0','1',…)→ 用第一列當表頭
        # (twsthr 時間序列表即此情況,真實欄名「資料日期 / >400張大股東持有百分比」在首列)
        if len(ft) >= 2 and all(str(c).strip().isdigit() for c in ft.columns):
            ft = ft.copy()
            ft.columns = [str(x).strip() for x in ft.iloc[0].tolist()]
            ft = ft.iloc[1:].reset_index(drop=True)
        cols = list(ft.columns)
        c_major = _find_major_col(cols)
        c_retail = _find_col(cols, ('股東人數', '散戶', '50張', '人數'))
        if not (c_major or c_retail):
            continue
        c_date = _find_col(cols, ('日期', '週', 'date', '時間')) or cols[0]
        # 有效日期比例(時間序列指標)— 分級分佈表/雜訊無有效日期,會被壓低分數
        _date_valid = 0.0
        if c_date in ft.columns:
            _dts = _parse_date_series(ft[c_date])
            _date_valid = float(_dts.notna().mean()) if len(_dts) else 0.0
        # 評分:有效日期(時序) > 大戶比例 > 散戶人數 > 列數
        score = (_date_valid * 3.0 + (2.0 if c_major else 0)
                 + (1.0 if c_retail else 0) + min(len(ft), 300) / 1000.0)
        if score > best_score:
            best_score = score
            best = (ft, c_date, c_major, c_retail)

    if best is None:
        return pd.DataFrame()

    ft, c_date, c_major, c_retail = best
    out = pd.DataFrame()
    out['日期'] = _parse_date_series(ft[c_date]) if c_date in ft.columns else pd.NaT
    out['大戶比例'] = ft[c_major].map(_to_num) if c_major else float('nan')
    out['散戶人數'] = ft[c_retail].map(_to_num) if c_retail else float('nan')

    # 清洗:丟掉兩個數值都缺的列;日期缺的列也丟
    out = out.dropna(how='all', subset=['大戶比例', '散戶人數'])
    if out['日期'].notna().any():
        out = out.dropna(subset=['日期']).sort_values('日期')
    out = out.reset_index(drop=True)
    return out


def _table_diag(tables: list[pd.DataFrame]) -> list[dict]:
    """壓縮成可快取的輕量診斷結構(shape / columns / 前 5 列)。"""
    diag = []
    for i, t in enumerate(tables):
        try:
            ft = _flatten_cols(t)
            diag.append({
                'idx': i,
                'shape': list(t.shape),
                'columns': [str(c) for c in ft.columns][:30],
                'preview': ft.head(5),
            })
        except Exception:
            diag.append({'idx': i, 'shape': list(getattr(t, 'shape', [0, 0])),
                         'columns': [], 'preview': pd.DataFrame()})
    return diag


# ══════════════════════════════════════════════════════════════════════════════
# 核心抓取(@st.cache_data — 回 dict,cache-safe)
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_chip_concentration(ticker: str) -> dict:
    """抓集保股權分散表並自適應解析。失敗回空 df + 錯誤訊息(不拋例外)。"""
    import io as _io
    import random as _rnd

    _empty = {'df': pd.DataFrame(), 'err': '', 'tables': [], 'html_head': ''}

    _tk = ''.join(c for c in str(ticker) if c.isalnum()).strip()
    if not _tk:
        _empty['err'] = '股票代號為空'
        return _empty

    _url = TWSTHR_URL.format(ticker=_tk)
    try:
        from src.data.proxy import fetch_url
        _resp = fetch_url(_url, headers={'User-Agent': _rnd.choice(_UA_POOL)},
                          timeout=15, attempts=3)
    except Exception as _fe:
        _empty['err'] = f'連線例外(已重試):{type(_fe).__name__}: {_fe}'
        return _empty

    if _resp is None:
        _empty['err'] = 'NAS 代理與直連皆失敗(重試 3 次後回空)'
        return _empty
    if getattr(_resp, 'status_code', 0) != 200:
        _empty['err'] = f'HTTP 非 200(status={getattr(_resp, "status_code", None)})— 網站/代理異常'
        return _empty

    # ── 解碼(先 .text,過短再嘗試多編碼)──
    try:
        _html = _resp.text or ''
        if len(_html) < 200 and getattr(_resp, 'content', None):
            for _enc in ('utf-8', 'big5', 'cp950'):
                try:
                    _html = _resp.content.decode(_enc)
                    break
                except Exception:
                    continue
    except Exception:
        _empty['err'] = '回應內容解碼失敗'
        return _empty

    if not _html or len(_html) < 50:
        _empty['err'] = '回應內容為空或過短'
        return _empty

    # ── read_html ──
    try:
        _tables = pd.read_html(_io.StringIO(_html))
    except ValueError:
        _empty['err'] = 'pandas.read_html 在頁面找不到任何 HTML 表格(網站可能改版或回了錯誤頁)'
        _empty['html_head'] = _html[:600]
        return _empty
    except Exception as _pe:
        _empty['err'] = f'read_html 例外:{type(_pe).__name__}: {_pe}'
        _empty['html_head'] = _html[:600]
        return _empty

    if not _tables:
        _empty['err'] = 'read_html 回傳空清單'
        _empty['html_head'] = _html[:600]
        return _empty

    _parsed = _adaptive_parse(_tables)
    _diag = _table_diag(_tables)
    _err = '' if not _parsed.empty else \
        '找到表格但無法辨識「大戶比例 / 散戶人數」欄位 — 請展開下方診斷面板看實際欄位結構'
    # v18.357 PR-Q5c S-PROV-1 phase 19 — prov_log emits [fetch_chip_concentration] marker
    prov_log('fetch_chip_concentration', 'norway.twsthr.info(集保股權分散表)',
             f'dict:df_rows={len(_parsed)}:err={"Y" if _err else "N"}', ticker=ticker)
    return {'df': _parsed, 'err': _err, 'tables': _diag, 'html_head': ''}
