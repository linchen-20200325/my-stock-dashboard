"""src/data/stock/yield_pe_fetcher.py — 全市場本益比 / 殖利率 / 股價淨值比 fetcher(L1)。

資料來源(皆 T1 官方 OpenAPI,§2.1):
  ① 上市:TWSE OpenAPI `BWIBBU_d`(單次抓全上市)
  ② 上櫃:TPEX OpenAPI `tpex_mainboard_peratio_analysis`(單次抓全上櫃)

搬遷理由(E2,2026-08;解 C3-d 待修)
──────────────────────────────────
本檔三個函式原本住在 `src/ui/tabs/yield_screener.py`(**L5 UI Tab**),而該檔
module-level 無條件 `import streamlit as st`。四個 caller 裡有兩個是 headless cron
(`scripts/push_daily_signals.py`、`scripts/update_forward_test_freeze.py`)——
走那條 import 會把整個 streamlit UI 鏈拉進 cron。`update_forward_test_freeze.py`
正是每月凍結**前進式驗證**的那支(本專案唯一零 lookahead / 零存活者偏誤的績效量測),
import 鏈一斷紀錄就靜默停止更新(§1:靜默失敗 = 違憲)。

原檔的合理化說法是「本腳本為 orchestrator 可直呼 L5」——那不是豁免理由,
是把已知錯誤敘述成設計(CLAUDE.md §8.2.A.0 規則 5 明文點名的反模式)。
正解就是把 fetcher 放回它該待的層。

§8.2 分層:L1 Data(純取數 + 解析 + provenance,零 UI)。
  caller: L5 `src/ui/tabs/yield_screener.py`(re-export,EX-PASSTHRU-1)
          L5 `src/ui/tabs/stock_sections/section_357_valuation.py`(EX-PASSTHRU-1)
          L6 `app.py` / cron `scripts/*.py` / `mcp_server/server.py`(orchestrator)
§8.2.A EX-CACHE-1:條件 import streamlit,**僅**為取得 `@st.cache_data`;
  全檔零 `st.session_state` / `st.error` / `st.warning` 等真 UI 呼叫。

⚠️ 測試 patch 目標(踩過的坑,勿回退)
  - HTTP 層 → `src.data.stock.yield_pe_fetcher.proxy_fetch_url`
  - 單一市場 → `patch.object(<本模組>, "fetch_twse_yield_pe" / "fetch_tpex_yield_pe")`
  `fetch_pe_name_maps` 在**呼叫時**才從本模組 globals 取這兩個名字,所以 patch 本模組
  有效、patch `src.ui.tabs.yield_screener` 的 re-export **無效**(那只是同一物件的別名,
  改綁定打不到內部呼叫)。patch 沒打到卻照樣綠燈 = 打真網路的假綠燈。
"""
from __future__ import annotations

import pandas as pd

from shared.ttls import TTL_1DAY

# ── EX-CACHE-1 標準寫法(CLAUDE.md §8.2.A.1)—— 無 streamlit 環境(headless
#    cron / pytest / MCP server)照樣 import 得動,decorator 退化為 no-op。
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            # 支援 @st.cache_data 和 @st.cache_data(ttl=...) 兩種呼叫
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

TWSE_BWIBBU_URL = 'https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d'
# 上櫃(OTC)本益比 / 殖利率 / 股價淨值比 — TWSE BWIBBU_d 只含上市,上櫃走 TPEX。
TPEX_PERATIO_URL = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis'


def proxy_fetch_url(url: str, *args, **kwargs):
    """走 NAS Squid Proxy 抓 URL(自動降級直連;重試 / timeout / Storm Shield 見 proxy_helper)。

    lazy import:本模組被 headless cron import 時不必在 module load 就拉整條 requests
    依賴鏈。同時這個具名間接層是**唯一穩定的 HTTP patch 目標**(見模組 docstring)。
    """
    from src.data.proxy import fetch_url
    return fetch_url(url, *args, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# ① 全市場 — TWSE BWIBBU_d 單次抓取
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_twse_yield_pe() -> pd.DataFrame:
    """從 TWSE OpenAPI 一次取得**全上市**本益比 / 殖利率 / 股價淨值比。

    ⚠️ B6-b（2026-08）修：原本回傳前做 `dropna(subset=['殖利率(%)'])`，把「沒有殖利率」
    的上市股整列丟掉。BWIBBU_d 對未配息 / 尚未公告配息的公司 `DividendYield` 給空字串
    （2026-08-05 實測前 410 檔中 99 檔為空 ≈ 24%），其中不乏本益比正常可用者
    （如 2514 龍邦 PEratio 7.07、2516 新建 11.82、2524 京城 61.32）。
    後果：選股網「估值便宜」因子與名稱 map 走本函式（`fetch_pe_name_maps` SSOT），
    這些股會變成「無估值分 + 名稱空白」——不是「PE 貴被排後面」，而是**沒有參賽資格**，
    還可能因 SCREENER_MIN_FACTOR_COVERAGE_RATIO 涵蓋門檻被整檔擋出榜單。
    而上櫃版 `fetch_tpex_yield_pe` 早已刻意不做這個 dropna（見該函式 docstring）→
    同一個因子，上市 / 上櫃兩套母體規則（§2.1 SSOT 不一致）。
    改為**不丟**：殖利率缺 → 該欄 NaN（§1 缺值就是缺值，不用它連坐 PE / 名稱）。
    需要「只看有配息」的呼叫端請自行 `dropna(subset=['殖利率(%)'])`。

    Returns:
        DataFrame with columns: 代碼 / 名稱 / 本益比 / 殖利率(%) / 股價淨值比
        （殖利率 / 本益比 / 股價淨值比 可能為 NaN = 該欄無資料）
        失敗回傳空 DataFrame（呼叫端用 .empty 檢查）
    """
    try:
        _resp = proxy_fetch_url(TWSE_BWIBBU_URL, timeout=15)
        if _resp is None or getattr(_resp, 'status_code', 0) != 200:
            print('[yield_pe_fetcher] TWSE BWIBBU 回傳非 200 或 None')
            return pd.DataFrame()
        _data = _resp.json()
        if not isinstance(_data, list) or not _data:
            print('[yield_pe_fetcher] TWSE BWIBBU 回傳格式異常')
            return pd.DataFrame()
        _df = pd.DataFrame(_data).rename(columns={
            'Code':          '代碼',
            'Name':          '名稱',
            'PEratio':       '本益比',
            'DividendYield': '殖利率(%)',
            'PBratio':       '股價淨值比',
        })
        for _c in ['本益比', '殖利率(%)', '股價淨值比']:
            if _c in _df.columns:
                _df[_c] = pd.to_numeric(_df[_c], errors='coerce')
        # B6-b:**不**依殖利率 dropna（見 docstring）—— 未配息股仍保留其 PE / 名稱 / PB。
        if '代碼' in _df.columns:
            _df['代碼'] = _df['代碼'].astype(str).str.strip()
            _df = _df[_df['代碼'] != '']
        _result = _df.reset_index(drop=True)
        # v18.356 PR-Q5b S-PROV-1 phase 19:DataFrame 走 attrs
        try:
            _result.attrs.setdefault('source', 'TWSE:OpenAPI:BWIBBU_d')
            _result.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        return _result
    except Exception as _e:
        print(f'[yield_pe_fetcher] TWSE BWIBBU 解析失敗：{_e}')
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# ①-b 全上櫃 — TPEX peratio_analysis 單次抓取（對稱 ①，補上櫃估值 + 名稱）
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_tpex_yield_pe() -> pd.DataFrame:
    """從 TPEX OpenAPI 一次取得全上櫃本益比 / 殖利率 / 股價淨值比。

    對稱 `fetch_twse_yield_pe`（上市 BWIBBU_d）；補「不在 TWSE 表」的上櫃股估值 + 名稱。
    欄位對映（驗證自 TPEX openapi `tpex_mainboard_peratio_analysis`，值為字串，'-' = 無資料）：
        SecuritiesCompanyCode→代碼 / CompanyName→名稱 / PriceEarningRatio→本益比 /
        YieldRatio（TPEX 曾用 DividendYield，故 fallback）→殖利率(%) / PriceBookRatio→股價淨值比

    與 TWSE 版差異：**不** `dropna(殖利率)` —— 本函式主要餵 pe_map / name_map，上櫃股常無
    配息，若比照 TWSE 依殖利率 dropna 會連本益比 + 名稱一起丟；改僅要求「代碼非空」。

    Returns:
        DataFrame（代碼 / 名稱 / 本益比 / 殖利率(%) / 股價淨值比）；失敗回空 DataFrame。
    """
    try:
        _resp = proxy_fetch_url(TPEX_PERATIO_URL, timeout=15)
        if _resp is None or getattr(_resp, 'status_code', 0) != 200:
            print('[yield_pe_fetcher] TPEX peratio 回傳非 200 或 None')
            return pd.DataFrame()
        _data = _resp.json()
        if not isinstance(_data, list) or not _data:
            print('[yield_pe_fetcher] TPEX peratio 回傳格式異常')
            return pd.DataFrame()
        _df = pd.DataFrame(_data)
        # 殖利率欄:TPEX openapi 曾出現 YieldRatio / DividendYield 兩種命名 → 取存在者
        _yld_col = 'YieldRatio' if 'YieldRatio' in _df.columns else 'DividendYield'
        _df = _df.rename(columns={
            'SecuritiesCompanyCode': '代碼',
            'CompanyName':           '名稱',
            'PriceEarningRatio':     '本益比',
            _yld_col:                '殖利率(%)',
            'PriceBookRatio':        '股價淨值比',
        })
        if '代碼' not in _df.columns:
            print('[yield_pe_fetcher] TPEX peratio 缺代碼欄')
            return pd.DataFrame()
        _df['代碼'] = _df['代碼'].astype(str).str.strip()
        for _c in ['本益比', '殖利率(%)', '股價淨值比']:
            if _c in _df.columns:
                _df[_c] = pd.to_numeric(_df[_c], errors='coerce')
        _result = _df[_df['代碼'] != ''].reset_index(drop=True)
        # S-PROV-1:DataFrame 走 attrs 攜帶血緣（對稱 TWSE 版）
        try:
            _result.attrs.setdefault('source', 'TPEX:OpenAPI:peratio_analysis')
            _result.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        return _result
    except Exception as _e:
        print(f'[yield_pe_fetcher] TPEX peratio 解析失敗：{_e}')
        return pd.DataFrame()


def fetch_pe_name_maps() -> tuple[dict, dict]:
    """上市(TWSE BWIBBU) + 上櫃(TPEX peratio) 合併 → (pe_map, name_map)。

    選股網 pe_low（估值分）+ 顯示名稱的 **SSOT**：畫面 / 推播 / 前進式凍結 / MCP 四個
    orchestrator 皆走此函式，確保「上市 + 上櫃」涵蓋一致（原僅 TWSE → 上櫃股估值分 None、
    名稱空白）。

    合併規則：上市 / 上櫃代碼空間互斥，本質是 union；仍用 `setdefault`（上市先填）保序、
    防偶發重碼（§2.1：同 T1 官方源，不平均、上層先填者贏）。任一源失敗 **fail-soft**
    ——只少半邊涵蓋、不炸；缺料的股在 `_percentile_scores` 會自動不計入（§1）。

    B6-b（2026-08）：本益比 ≤ 0 視為「無本益比」而**不放進 pe_map**（§1 不造假）。
    pe_low 因子是「值越小分越高」，若讓 0 / 負數進榜，虧損股會被排成「全市場最便宜」
    —— 那是缺值，不是估值。（TWSE 目前給空字串、TPEX 給 '-'，都已是 NaN；本檢查是
    對「來源改用 0 佔位」的防呆，且順手擋掉理論上的負 PE。）

    ⚠️ 兩個 fetcher 刻意在**呼叫時**才從本模組 globals 解析（下面的 tuple 是在函式體內
    建的），測試才 patch 得到（見模組 docstring 的 patch 目標說明）。

    Returns:
        (pe_map, name_map)：pe_map = {代碼: 本益比(float > 0)}；
        name_map = {代碼: 名稱}（過濾空字串 / 'nan'，避免畫面顯示 "nan"）。
    """
    pe_map: dict = {}
    name_map: dict = {}
    for _mkt, _fetch in (('上市 TWSE', fetch_twse_yield_pe), ('上櫃 TPEX', fetch_tpex_yield_pe)):
        try:
            _df = _fetch()
        except Exception as _e:  # noqa: BLE001 — 任一市場抓不到 → 只少半邊涵蓋,不炸
            print(f'[yield_pe_fetcher] {_mkt} PE 抓取失敗:{type(_e).__name__}: {_e}')
            continue
        if _df is None or _df.empty or '代碼' not in _df.columns:
            continue
        _codes = _df['代碼'].astype(str)
        if '本益比' in _df.columns:
            for _c, _v in zip(_codes, _df['本益比']):
                try:
                    _pe = float(_v)
                except (TypeError, ValueError):
                    continue
                if _pe != _pe or _pe <= 0:      # NaN / ≤0 → 無本益比,不放 key
                    continue
                pe_map.setdefault(_c, _pe)
        if '名稱' in _df.columns:
            for _c, _n in zip(_codes, _df['名稱'].astype(str)):
                _n = _n.strip()
                if _n and _n.lower() != 'nan':
                    name_map.setdefault(_c, _n)
    return pe_map, name_map
