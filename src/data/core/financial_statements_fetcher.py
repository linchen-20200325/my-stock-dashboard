"""financial_statements_fetcher.py — 老師 財報體檢原始數據 fetcher(L1)。

`fetch_financial_statements`:從 FinMind 抓最新季 資產負債表 / 現金流量表 / 損益表,
算 老師 體系所需指標。B8-a v19.155 從 data_loader.py(2545 行)原封拆出以降體積 + 職責
單一化;呼叫端經 `src.data.core` 套件 PEP 562 __getattr__ 轉發,介面完全不變。

自足:所有 I/O(requests / yfinance / pandas / ThreadPoolExecutor)皆函式內 late import。
"""
from __future__ import annotations

# §8.2.A EX-CACHE-1:條件 import streamlit(僅 @st.cache_data,無真 UI 呼叫)。
try:
    import streamlit as st
except ImportError:  # 純 .py 環境(cron / 測試)無 streamlit
    class _NoOpST:  # noqa
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

import pandas as pd

from shared.ttls import TTL_1HOUR
from src.config import FINMIND_API_URL


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_financial_statements(stock_id: str, token: str = "") -> dict:
    """
    從 FinMind 抓取最新一季資產負債表、現金流量表、損益表，
    計算 老師 體系所需指標。
    回傳 dict；失敗時回傳 {"error": "..."}。
    """
    import os as _os_ffs, requests as _rq_ffs, datetime as _dt_ffs

    _tok = token or _os_ffs.environ.get("FINMIND_TOKEN", "")
    _start = (_dt_ffs.date.today() - _dt_ffs.timedelta(days=730)).strftime("%Y-%m-%d")
    _hdrs = {"Authorization": f"Bearer {_tok}"} if _tok else {}

    def _fm(dataset):
        _p = {"dataset": dataset, "data_id": stock_id, "start_date": _start}
        if _tok:
            _p["token"] = _tok
        try:
            _r = _rq_ffs.get(
                FINMIND_API_URL,
                params=_p, headers=_hdrs, timeout=20,
            )
            _j = _r.json()
            _st = _j.get("status")
            if _st != 200:
                print(f"[fetch_fin/{dataset}] 非200回應: status={_st} msg={_j.get('msg','')}")
            return _j.get("data", []) if _st == 200 else [], _st
        except Exception as _e:
            print(f"[fetch_fin/{dataset}] {_e}")
            return [], None

    # 3 個 dataset 彼此獨立 → 並行抓（_fm 純獨立 requests、無共享可變狀態，線程安全）。
    # map 保序，故下方解包順序與 _ds_ffs 一致；總請求數不變（FinMind 限額為每小時制）。
    from concurrent.futures import ThreadPoolExecutor as _TPE_ffs
    _ds_ffs = ("TaiwanStockBalanceSheet", "TaiwanStockCashFlowsStatement",
               "TaiwanStockFinancialStatements")
    with _TPE_ffs(max_workers=3) as _ex_ffs:
        _fm_res = list(_ex_ffs.map(_fm, _ds_ffs))
    (_bs_rows, _bs_st), (_cf_rows, _cf_st), (_is_rows, _is_st) = _fm_res

    if not _bs_rows and not _cf_rows:
        # 區分 Token 問題 vs 股票本身無資料
        _statuses = [s for s in [_bs_st, _cf_st] if s is not None]
        if not _tok:
            _err = f"{stock_id}：未設定 FINMIND_TOKEN，無法查詢財報"
        elif any(s in (401, 403) for s in _statuses):
            _err = f"{stock_id}：FINMIND_TOKEN 無效或已過期（HTTP {_statuses[0]}）"
        else:
            _err = (f"{stock_id}：FinMind 無此股票財報資料"
                    f"（可能為新掛牌、未上市、或 FinMind 資料源尚未收錄）")
        return {"error": _err}

    def _build(rows):
        """同一 (date,key) 多筆值衝突時取最大絕對值。
        FinMind 對某些股票（例如 6770）會回傳多筆 type=Revenue 但 origin_name 不同
        （合計行 + 子科目行）；若用 last-wins 子科目會覆蓋合計，導致 rev 被低估、
        om/nm 出現 >100% 的荒謬比率。改取 max(|val|) 以保證合計優於子科目。"""
        m: dict = {}
        for r in rows:
            d = r.get("date", "")
            try:
                v = float(str(r.get("value", 0) or 0).replace(",", ""))
            except Exception:
                v = 0.0
            slot = m.setdefault(d, {})
            for _key in (r.get("type", ""), r.get("origin_name", "")):
                if not _key:
                    continue
                _prev = slot.get(_key)
                if _prev is None or abs(v) > abs(float(_prev) if _prev else 0):
                    slot[_key] = v
        return m

    _bs = _build(_bs_rows)
    _cf = _build(_cf_rows)
    _is = _build(_is_rows)

    _dates = sorted(set(list(_bs.keys()) + list(_cf.keys())))
    if not _dates:
        return {"error": f"{stock_id}：財報日期解析失敗"}

    _lat = _dates[-1]
    _prv = _dates[-2] if len(_dates) >= 2 else _lat

    def _v(m, d, keys):
        slot = m.get(d, {})
        for k in keys:
            v = slot.get(k)
            if v is not None:
                try:
                    fv = float(str(v).replace(",", "") or 0)
                    if fv != 0:
                        return fv
                except Exception:
                    pass
        return 0.0

    def _vsum(m, d, keys):
        """加總 keys 中所有非零欄位（用於應收票據+帳款需分開列示的報表）"""
        slot = m.get(d, {})
        total = 0.0
        for k in keys:
            v = slot.get(k)
            if v is not None:
                try:
                    fv = float(str(v).replace(",", "") or 0)
                    if fv > 0:
                        total += fv
                except Exception:
                    pass
        return total

    cash   = _v(_bs, _lat, ["CashAndCashEquivalents", "現金及約當現金", "Cash",
                              "現金及銀行存款", "庫存現金及約當現金"])
    assets = _v(_bs, _lat, ["TotalAssets", "資產總計", "資產合計", "資產總額",
                              "資產總計（千元）", "Assets"])
    liab   = _v(_bs, _lat, ["TotalLiabilities", "負債總計", "負債合計", "負債總額",
                             "Liabilities", "負債合計（千元）", "負債總額（千元）",
                             "負債總計（千元）"])
    cur_assets = _v(_bs, _lat, ["CurrentAssets", "流動資產合計", "流動資產總計",
                                  "流動資產", "流動資產總額"])
    cur_liab = _v(_bs, _lat, ["CurrentLiabilities", "流動負債合計", "流動負債總計",
                                "流動負債", "流動負債總額"])
    # FinMind 不一定提供「負債合計」彙總行，直接用 流動+非流動 相加
    _non_cur_liab = _v(_bs, _lat, ["NoncurrentLiabilities", "非流動負債合計",
                                    "非流動負債總計", "非流動負債"])
    if liab == 0 and (cur_liab > 0 or _non_cur_liab > 0):
        liab = cur_liab + _non_cur_liab
        print(f"[fetch_fin] {stock_id} 負債合計查無，改用 流動({cur_liab:.0f})+非流動({_non_cur_liab:.0f})={liab:.0f}千")
    # FinMind 不一定提供「資產合計」彙總行，直接用 流動+非流動 相加
    _non_cur_assets = _v(_bs, _lat, ["NoncurrentAssets", "非流動資產合計",
                                      "非流動資產總計", "非流動資產"])
    if assets == 0 and (cur_assets > 0 or _non_cur_assets > 0):
        assets = cur_assets + _non_cur_assets
        print(f"[fetch_fin] {stock_id} 資產合計查無，改用 流動({cur_assets:.0f})+非流動({_non_cur_assets:.0f})={assets:.0f}千")
    # AR：L1 先加總分開列示的票據+帳款+關係人（避免與合計行重疊）
    # 涵蓋：舊格式（淨額/關係人）+ IFRS 括號格式（非關係人）/（關係人）+ 含稅格式
    # + em-dash（－）半形連字號（-）波折號（—）三種變體 + 全形括號（）+ 半形括號()
    ar = _vsum(_bs, _lat, [
        "應收票據淨額", "應收帳款淨額", "應收帳款－關係人淨額", "應收款項",
        "應收帳款（非關係人）", "應收帳款（關係人）",
        "應收帳款（非關係人）淨額", "應收帳款（關係人）淨額",
        "應收帳款－非關係人淨額",          # em-dash 非關係人淨額
        "應收票據（非關係人）", "應收票據（關係人）",
        "應收帳款-非關係人", "應收帳款-關係人",
        "應收帳款—非關係人", "應收帳款—關係人",          # 全形破折號
        "應收帳款 - 非關係人", "應收帳款 - 關係人",      # 帶空白
        "應收票據－非關係人淨額", "應收票據－關係人淨額",  # 票據 em-dash
        "應收帳款-非關係人淨額", "應收帳款-關係人淨額",   # 半形 + 淨額
        "應收帳款(非關係人)", "應收帳款(關係人)",         # 半形括號
    ])
    # L2 若 L1 = 0，改抓合併列示的合計行（不與 L1 混加，避免重複計算）
    if ar == 0:
        ar = _vsum(_bs, _lat, ["應收帳款及票據", "應收帳款及票據淨額",
                                "應收票據及帳款淨額",                    # 新增
                                "應收票據及應收帳款", "應收帳款",
                                "應收帳款（含稅）", "應收帳款淨額（含稅）"])
    if ar == 0:
        ar = _v(_bs, _lat, ["AccountsReceivable", "應收帳款淨額", "應收帳款",
                             "NoteAndAccountsReceivable", "應收帳款及票據應收款",
                             "應收票據及帳款", "應收帳款（淨額）", "貿易應收款及其他應收款",
                             "貿易及其他應收款",                          # 新增：外資掛牌台企
                             "應收帳款，淨額", "貿易應收款",
                             "應收款項", "應收款項合計", "應收帳款及其他應收款",
                             "ReceivablesNet", "NetReceivables",
                             "合約資產", "工程應收款", "應收帳款及合約資產",
                             "應收票據及應收帳款",
                             "應收帳款（非關係人）", "應收帳款（關係人）"])
    ap     = _v(_bs, _lat, ["AccountsPayable", "應付帳款",
                             "NoteAndAccountsPayable", "應付帳款及票據應付款",
                             "應付票據及帳款", "貿易應付款"])
    inv    = _v(_bs, _lat, ["Inventories", "存貨", "存貨淨額"])
    inv_p  = _v(_bs, _prv, ["Inventories", "存貨", "存貨淨額"])
    ppe    = _v(_bs, _lat, ["PropertyPlantAndEquipmentNet", "不動產、廠房及設備淨額",
                             "固定資產淨額", "不動產廠房及設備",
                             "PropertyPlantAndEquipment", "不動產廠房及設備淨額",
                             "不動產、廠房及設備"])
    lt_inv = _v(_bs, _lat, ["LongTermInvestments", "長期投資", "採權益法之投資"])
    # ── v10.57.0 新增：老師 體檢補充原料（速動比率 / 現金再投資比率 / EPS）──
    prepaid = _v(_bs, _lat, ["Prepayments", "預付款項", "預付費用", "預付貨款",
                              "預付投資款", "其他預付款項"])
    other_nca = _v(_bs, _lat, ["OtherNoncurrentAssets", "其他非流動資產",
                                "其他非流動資產合計"])
    # 基本 EPS（IS）
    eps_v = _v(_is, _lat, ["BasicEarningsPerShare", "基本每股盈餘", "每股盈餘",
                            "EPS", "Earnings Per Share", "稀釋每股盈餘"])

    ocf    = _v(_cf, _lat, ["CashFlowsFromOperatingActivities",
                             "營業活動之淨現金流入（流出）", "來自營業活動之現金流量"])
    icf    = _v(_cf, _lat, ["CashFlowsFromInvestingActivities",
                             "投資活動之淨現金流入（流出）", "來自投資活動之現金流量"])
    fncf   = _v(_cf, _lat, ["CashFlowsFromFinancingActivities",
                             "籌資活動之淨現金流入（流出）", "來自籌資活動之現金流量"])
    capex  = abs(_v(_cf, _lat, ["AcquisitionOfPropertyPlantAndEquipment",
                                 "取得不動產、廠房及設備", "購置不動產、廠房及設備", "資本支出"]))
    div_paid = abs(_v(_cf, _lat, ["CashDividendsPaid", "發放現金股利", "現金股利"]))

    rev    = _v(_is, _lat, ["Revenue", "營業收入合計", "營業收入", "NetRevenue",
                              "OperatingRevenue", "營業總收入", "營業淨收入",
                              "銷貨收入淨額", "銷貨收入"])
    cogs   = abs(_v(_is, _lat, ["CostOfGoodsSold", "營業成本", "銷售成本",
                                 "OperatingCosts", "營業總成本"]))
    oper_income = _v(_is, _lat, ["OperatingIncome", "營業利益（損失）", "營業利益",
                                  "Operating Income", "OperatingProfit",
                                  "營業淨利", "營業損益"])
    net_ni = _v(_is, _lat, ["NetIncome", "本期淨利（淨損）", "淨利", "稅後淨利",
                              "ProfitLoss", "本期綜合損益總額",
                              "歸屬於母公司業主之淨利（淨損）"])
    # ── Sanity: oi/ni 不應大於 rev × 1.2（單位錯亂或子科目誤抓）──────
    if rev > 0:
        if abs(oper_income) > rev * 1.2:
            print(f"[fetch_fin] {stock_id} ⚠️ oper_income={oper_income:.0f} > rev={rev:.0f}×1.2，疑似誤抓子科目，重置為 0")
            oper_income = 0
        if abs(net_ni) > rev * 1.2:
            print(f"[fetch_fin] {stock_id} ⚠️ net_ni={net_ni:.0f} > rev={rev:.0f}×1.2，疑似誤抓子科目，重置為 0")
            net_ni = 0

    rev_p  = _v(_is, _prv, ["Revenue", "營業收入合計", "營業收入"])
    ar_p   = _v(_bs, _prv, [
        "AccountsReceivable", "應收帳款淨額", "應收帳款",
        "應收帳款（非關係人）", "應收帳款（關係人）",
        "應收帳款（非關係人）淨額", "應收帳款及票據", "應收票據及應收帳款",
        "應收帳款（含稅）",
    ])
    equity = _v(_bs, _lat, ["TotalEquity", "權益總額", "股東權益合計",
                             "TotalStockholdersEquity", "股東權益總額",
                             "EquityAttributableToOwnersOfParent",
                             "歸屬於母公司業主之權益合計",
                             "權益合計"])
    # 理智校驗：equity < 0.1% of assets → 可能抓到子項目而非合計，改用 assets−liab 重算
    if 0 < equity < assets * 0.001 and liab > 0:
        recalc = max(assets - liab, 0)
        print(f"[fetch_fin] {stock_id} equity={equity:.0f}千 疑似欄位誤配（{equity/assets:.6%}），改用 assets-liab={recalc:.0f}千")
        equity = recalc
    # Fallback: Assets = Liabilities + Equity（IFRS 恆等式，雙向兜底）
    if liab == 0 and assets > 0 and equity > 0:
        liab = max(assets - equity, 0)
        print(f"[fetch_fin] {stock_id} 負債欄位查無資料，改用 資產-權益 計算: {round(liab/1e3)}千")
    if assets == 0 and equity > 0 and liab > 0:
        assets = equity + liab
        print(f"[fetch_fin] {stock_id} 資產欄位查無資料，改用 權益+負債 計算: {round(assets/1e3)}千")

    # 模糊比對兜底：從 BS 所有欄位取最大值（合計行通常是最大的）
    # 正規化 key：去除全形/半形空白，確保「負 債 總 計」等全形空白格式能匹配
    _bs_slot = _bs.get(_lat, {})
    def _fuzzy_bs(_inc, _exc=()):
        _best = 0.0
        for _fk, _fvv in _bs_slot.items():
            _fks = str(_fk).replace(' ', '').replace('　', '')
            if all(_i in _fks for _i in _inc) and not any(_e in _fks for _e in _exc):
                try:
                    _ffv = float(str(_fvv).replace(",", "") or 0)
                    if _ffv > _best:
                        _best = _ffv
                except Exception:
                    pass
        return _best
    if assets == 0:
        assets = _fuzzy_bs(["資產"], ["負債", "資本", "遞延"])
        if assets > 0:
            print(f"[fetch_fin] {stock_id} assets 模糊比對: {assets:.0f}千")
    if liab == 0:
        liab = _fuzzy_bs(["負債"], ["資產", "準備", "權益"])
        if liab == 0:
            # 放寬：移除「準備」排除（避免「負債準備」類科目被錯排）
            liab = _fuzzy_bs(["負債"], ["資產", "權益"])
        if liab > 0:
            print(f"[fetch_fin] {stock_id} liab 模糊比對: {liab:.0f}千")
        else:
            # 完全失敗：印出 BS 所有欄位名稱供診斷
            _all_bs_keys = sorted(_bs_slot.keys())
            print(f"[fetch_fin] {stock_id} liab 模糊全失敗 "
                  f"bs_keys={_all_bs_keys[:30]}")
    if ar == 0:
        ar = _fuzzy_bs(["應收"], ["利息", "所得稅", "員工", "遞延", "退稅"])
        if ar == 0:
            ar = _fuzzy_bs(["合約資產"])  # IFRS 15 合約資產
        if ar > 0:
            print(f"[fetch_fin] {stock_id} ar 模糊比對: {ar:.0f}千")

    # ── Pandas regex 終極兜底：正規化所有空白後做 str.contains，抓全形空白科目 ──
    if (ar == 0 or liab == 0) and _bs_slot:
        try:
            import pandas as _pd_regex
            _bsdf = _pd_regex.DataFrame(
                list(_bs_slot.items()), columns=['type', 'value']
            )
            _bsdf['type_n'] = _bsdf['type'].str.replace(r'\s+|　', '', regex=True)
            _bsdf['val_n'] = _pd_regex.to_numeric(
                _bsdf['value'].astype(str).str.replace(',', '', regex=False),
                errors='coerce'
            )
            _bsdf = _bsdf[_bsdf['val_n'].notna() & (_bsdf['val_n'] > 0)]
            if ar == 0:
                _ar_mask = (_bsdf['type_n'].str.contains('應收帳款|應收票據', regex=True, na=False) &
                            ~_bsdf['type_n'].str.contains('利息|所得稅|員工|遞延|退稅', regex=True, na=False))
                if _ar_mask.any():
                    ar = float(_bsdf.loc[_ar_mask, 'val_n'].max())
                    print(f"[fetch_fin] {stock_id} ar pandas-regex兜底: {ar:.0f}千 "
                          f"type={_bsdf.loc[_ar_mask, 'type'].iloc[0]!r}")
            if liab == 0:
                _lb_mask = (_bsdf['type_n'].str.contains('負債總計|負債合計|負債總額', regex=True, na=False) &
                            ~_bsdf['type_n'].str.contains('非流動|流動負債', regex=True, na=False))
                if _lb_mask.any():
                    liab = float(_bsdf.loc[_lb_mask, 'val_n'].max())
                    print(f"[fetch_fin] {stock_id} liab pandas-regex兜底: {liab:.0f}千 "
                          f"type={_bsdf.loc[_lb_mask, 'type'].iloc[0]!r}")
        except Exception as _e_regex:
            print(f"[fetch_fin] {stock_id} pandas-regex兜底異常: {_e_regex}")

    # ── FinMind 原始列 str.contains 兜底（非標準科目命名，如力積電等）──
    if ar == 0 and _bs_rows:
        try:
            import pandas as _pd_ar_sc
            _bs_df_sc = _pd_ar_sc.DataFrame(_bs_rows)
            if not _bs_df_sc.empty and 'date' in _bs_df_sc.columns and 'type' in _bs_df_sc.columns:
                _lat_sc = _bs_df_sc[_bs_df_sc['date'] == _lat].copy()
                _excl_kw = '利息|所得稅|員工|遞延|退稅'
                _on_col = (_lat_sc['origin_name'] if 'origin_name' in _lat_sc.columns
                           else _pd_ar_sc.Series([''] * len(_lat_sc), index=_lat_sc.index))
                _ar_mask = (
                    (_lat_sc['type'].str.contains('應收帳款', na=False) |
                     _on_col.str.contains('應收帳款', na=False)) &
                    ~_lat_sc['type'].str.contains(_excl_kw, na=False)
                )
                _ar_match_sc = _lat_sc[_ar_mask]
                if not _ar_match_sc.empty:
                    ar = float(_ar_match_sc['value'].max() or 0)
                    if ar > 0:
                        print(f"[fetch_fin] {stock_id} ar str.contains兜底: {ar:.0f}千 "
                              f"types={list(_ar_match_sc['type'].values)[:3]}")
        except Exception as _e_ar_sc:
            print(f"[fetch_fin] {stock_id} ar str.contains兜底異常: {_e_ar_sc}")

    # ── yfinance 備援：對仍為零的關鍵欄位嘗試補值 ────────────────────────
    if ar == 0 or liab == 0 or assets == 0:
        try:
            import yfinance as _yf_ffs, pandas as _pd_yf_ffs
            _yf_bs_df = None
            for _sfx_yf in (".TW", ".TWO"):
                _tk_yf = _yf_ffs.Ticker(f"{stock_id}{_sfx_yf}")
                _qbs_yf = getattr(_tk_yf, "quarterly_balance_sheet", None)
                if _qbs_yf is not None and not _qbs_yf.empty:
                    _yf_bs_df = _qbs_yf
                    break
            if _yf_bs_df is not None and not _yf_bs_df.empty:
                _yfc = _yf_bs_df.columns[0]
                def _yf_v(*_keys_yf):
                    for _k in _keys_yf:
                        for _idx in _yf_bs_df.index:
                            if _k.lower() in str(_idx).lower():
                                try:
                                    _v = float(_yf_bs_df.loc[_idx, _yfc])
                                    if _pd_yf_ffs.notna(_v) and _v != 0:
                                        return _v
                                except Exception:
                                    pass
                    return 0.0
                _filled_yf = []
                if assets == 0:
                    _va = _yf_v("total assets")
                    if _va > 0:
                        assets = _va; _filled_yf.append("assets")
                if liab == 0:
                    _vl = _yf_v("total liab", "total liabilities")
                    if _vl > 0:
                        liab = _vl; _filled_yf.append("liab")
                if ar == 0:
                    _var = _yf_v("net receivables", "accounts receivable", "receivables")
                    if _var > 0:
                        ar = _var; _filled_yf.append("ar")
                if _filled_yf:
                    print(f"[fetch_fin] {stock_id} yfinance備援補值 {_filled_yf}: "
                          f"assets={assets:.0f} liab={liab:.0f} ar={ar:.0f} 千")
                    # 若 yfinance 補了 assets/equity，再試一次 IFRS identity
                    if liab == 0 and assets > 0 and equity > 0:
                        liab = max(assets - equity, 0)
                    if assets == 0 and equity > 0 and liab > 0:
                        assets = equity + liab
        except Exception as _e_yf:
            print(f"[fetch_fin] {stock_id} yfinance備援異常: {_e_yf}")

    _zero_fields = [f for f, v in [("ar", ar), ("ppe", ppe), ("liab", liab), ("equity", equity)] if v == 0]
    if _zero_fields:
        _all_bs_keys = list((_bs.get(_lat) or {}).keys())
        print(f"[fetch_fin] {stock_id} 零值欄位={_zero_fields} 全部BS欄位({len(_all_bs_keys)})={_all_bs_keys}")
        # AR 全部失敗時額外嘗試：合約資產（IFRS 15）/ 貿易應收款 / 應收款項（不含利息）
        if ar == 0 and _all_bs_keys:
            for _extra_ar in ["合約資產", "流動合約資產", "貿易及其他應收款項",
                               "應收款項（不含關係人）", "短期應收款"]:
                _ev = _bs_slot.get(_extra_ar)
                if _ev:
                    try:
                        _ef = float(str(_ev).replace(',', ''))
                        if _ef > 0:
                            ar = _ef
                            print(f"[fetch_fin] {stock_id} ar 補充別名 '{_extra_ar}': {ar:.0f}千")
                            break
                    except Exception:
                        pass

    # 最終 sanity check：liab/assets < 1% → 疑似子科目誤配（非零但近零的 cur+noncur）
    # 印出所有含「負債」的欄位供診斷；嘗試 IFRS identity（equity 在此已被修正過）
    if 0 < liab < assets * 0.01 and assets > 0:
        _liab_keys = [(k, _bs_slot.get(k)) for k in sorted(_bs_slot.keys())
                      if '負債' in str(k) and '資產' not in str(k)]
        print(f"[fetch_fin] {stock_id} ⚠️ liab={liab:.0f} 僅 {liab/assets:.4%} of assets={assets:.0f}，"
              f"cur_liab={cur_liab:.0f} ncl={_non_cur_liab:.0f}，"
              f"負債欄位={_liab_keys[:10]}")
        # 用 IFRS identity 嘗試修正（equity 已在 1700-1703 處被修正為 assets-old_liab ≈ assets）
        # 此時 equity ≈ assets，故用 assets - equity 不可行；改用 fuzzy 強制再跑一次
        _liab_fuzzy2 = _fuzzy_bs(["負債"], ["資產", "權益"])
        if _liab_fuzzy2 > liab * 5:
            liab = _liab_fuzzy2
            print(f"[fetch_fin] {stock_id} liab sanity 修正 via fuzzy: {liab:.0f}千")

    # AR sanity：ar/季收入 < 0.5% → 疑似子科目誤配（如關係人應收幾千元）
    if 0 < ar < (rev * 0.005) and rev > 0:
        _ar_keys = [(k, _bs_slot.get(k)) for k in sorted(_bs_slot.keys())
                    if '應收' in str(k) and '利息' not in str(k) and '所得稅' not in str(k)]
        print(f"[fetch_fin] {stock_id} ⚠️ ar={ar:.0f}千 僅 {ar/(rev*4)*360:.1f}天，"
              f"應收欄位={_ar_keys[:10]}")
        _ar_fuzzy2 = _fuzzy_bs(["應收"], ["利息", "所得稅", "員工", "遞延", "退稅"])
        if _ar_fuzzy2 > ar * 5:
            ar = _ar_fuzzy2
            print(f"[fetch_fin] {stock_id} ar sanity 修正 via fuzzy: {ar:.0f}千")

    cash_ratio = round(cash / assets * 100, 1) if assets > 0 else 0
    debt_ratio = round(liab / assets * 100, 1) if assets > 0 else 0
    gp         = rev - cogs
    gm         = round(gp / rev * 100, 1) if rev > 0 else 0
    # 年化：單季數字 × 4，以免 DSO/DPO 被低估 4 倍；天數基準統一 360 天
    ar_days = round(ar / (rev * 4) * 360, 1) if rev > 0 and ar > 0 else 0
    ap_days = round(ap / (cogs * 4) * 360, 1) if cogs > 0 and ap > 0 else 0
    fcf        = round(ocf - capex)
    ar_chg     = round((ar - ar_p) / abs(ar_p) * 100, 1) if ar_p != 0 else None
    rev_chg    = round((rev - rev_p) / abs(rev_p) * 100, 1) if rev_p != 0 else None

    print(f"[fetch_fin] {stock_id} {_lat}: cash={cash_ratio}% debt={debt_ratio}% "
          f"OCF={round(ocf/1e6,1)}百萬 AR_days={ar_days} AP_days={ap_days}")

    # ── prev_period_data：供 老師 trend 季際比較 bootstrap（v18.456）─────────────────
    # 用已抓到的 730 天 FinMind 資料再計算上一季指標，避免 Streamlit Cloud 重啟後
    # 快照清空導致 mj_trend 恆為 0。不做模糊比對/yfinance 兜底（零值時 analyze 給 N/A 即可）。
    _prev_period_data: dict = {}
    if len(_dates) >= 2:
        _pp = _prv                                          # 上一季日期
        _pp_prv = _dates[-3] if len(_dates) >= 3 else _prv  # 上上季（for 存貨前期）
        _pp_cash   = _v(_bs, _pp, ["CashAndCashEquivalents", "現金及約當現金", "Cash", "現金及銀行存款"])
        _pp_assets = _v(_bs, _pp, ["TotalAssets", "資產總計", "資產合計", "資產總額"])
        _pp_cur_a  = _v(_bs, _pp, ["CurrentAssets", "流動資產合計", "流動資產總計", "流動資產"])
        _pp_cur_l  = _v(_bs, _pp, ["CurrentLiabilities", "流動負債合計", "流動負債總計", "流動負債"])
        _pp_ncl    = _v(_bs, _pp, ["NoncurrentLiabilities", "非流動負債合計", "非流動負債總計", "非流動負債"])
        _pp_liab   = _v(_bs, _pp, ["TotalLiabilities", "負債總計", "負債合計", "負債總額"])
        if _pp_liab == 0 and (_pp_cur_l > 0 or _pp_ncl > 0):
            _pp_liab = _pp_cur_l + _pp_ncl
        if _pp_assets == 0 and _pp_cur_a > 0:
            _pp_nca = _v(_bs, _pp, ["NoncurrentAssets", "非流動資產合計", "非流動資產"])
            _pp_assets = _pp_cur_a + _pp_nca
        _pp_equity = _v(_bs, _pp, ["TotalEquity", "權益總額", "股東權益合計", "股東權益總額", "權益合計"])
        if _pp_liab == 0 and _pp_assets > 0 and _pp_equity > 0:
            _pp_liab = max(_pp_assets - _pp_equity, 0)
        if _pp_assets == 0 and _pp_equity > 0 and _pp_liab > 0:
            _pp_assets = _pp_equity + _pp_liab
        _pp_inv    = _v(_bs, _pp, ["Inventories", "存貨", "存貨淨額"])
        _pp_inv_p  = _v(_bs, _pp_prv, ["Inventories", "存貨", "存貨淨額"])
        _pp_ppe    = _v(_bs, _pp, ["PropertyPlantAndEquipmentNet", "不動產、廠房及設備淨額",
                                    "固定資產淨額", "不動產廠房及設備淨額"])
        _pp_lt_inv = _v(_bs, _pp, ["LongTermInvestments", "長期投資", "採權益法之投資"])
        _pp_ar     = _v(_bs, _pp, ["AccountsReceivable", "應收帳款淨額", "應收帳款",
                                    "應收帳款（非關係人）淨額", "應收帳款及票據",
                                    "應收票據及應收帳款", "應收帳款（含稅）"])
        _pp_ap     = _v(_bs, _pp, ["AccountsPayable", "應付帳款",
                                    "應付帳款及票據應付款", "應付票據及帳款"])
        _pp_rev    = _v(_is, _pp, ["Revenue", "營業收入合計", "營業收入", "NetRevenue", "OperatingRevenue"])
        _pp_cogs   = abs(_v(_is, _pp, ["CostOfGoodsSold", "營業成本", "銷售成本", "OperatingCosts"]))
        _pp_gp     = _pp_rev - _pp_cogs
        _pp_oi     = _v(_is, _pp, ["OperatingIncome", "營業利益（損失）", "營業利益", "OperatingProfit"])
        _pp_ni     = _v(_is, _pp, ["NetIncome", "本期淨利（淨損）", "淨利", "稅後淨利", "ProfitLoss"])
        _pp_ocf    = _v(_cf, _pp, ["CashFlowsFromOperatingActivities",
                                    "營業活動之淨現金流入（流出）", "來自營業活動之現金流量"])
        _pp_capex  = abs(_v(_cf, _pp, ["AcquisitionOfPropertyPlantAndEquipment",
                                        "取得不動產、廠房及設備", "資本支出"]))
        _pp_div    = abs(_v(_cf, _pp, ["CashDividendsPaid", "發放現金股利", "現金股利"]))

        _pp_cash_ratio = round(_pp_cash / _pp_assets * 100, 1) if _pp_assets > 0 else 0
        _pp_debt_ratio = round(_pp_liab / _pp_assets * 100, 1) if _pp_assets > 0 else 0
        _pp_gm         = round(_pp_gp / _pp_rev * 100, 1) if _pp_rev > 0 else 0
        _pp_ar_days    = round(_pp_ar / (_pp_rev * 4) * 360, 1) if _pp_rev > 0 and _pp_ar > 0 else 0
        _pp_ap_days    = round(_pp_ap / (_pp_cogs * 4) * 360, 1) if _pp_cogs > 0 and _pp_ap > 0 else 0

        _prev_period_data = {
            "stock_id":           stock_id,
            "period":             _pp,
            "現金佔總資產(%)":    _pp_cash_ratio,
            "負債比率(%)":        _pp_debt_ratio,
            "OCF(千)":            round(_pp_ocf),
            "ICF(千)":            0,
            "籌資CF(千)":         0,
            "自由現金流(千)":     round(_pp_ocf - _pp_capex),
            "資本支出(千)":       round(_pp_capex),
            "應收帳款天數":       _pp_ar_days,
            "應付帳款天數":       _pp_ap_days,
            "毛利率(%)":          _pp_gm,
            "營業收入(千)":       round(_pp_rev),
            "毛利(千)":           round(_pp_gp),
            "營業利益(千)":       round(_pp_oi),
            "稅後淨利(千)":       round(_pp_ni),
            "股東權益(千)":       round(_pp_equity),
            "流動資產(千)":       round(_pp_cur_a),
            "非流動負債(千)":     round(max(_pp_liab - _pp_cur_l, 0)),
            "營業成本(千)":       round(_pp_cogs),
            "OCF符號":            "正" if _pp_ocf > 0 else "負",
            "ICF符號":            "負",
            "籌資CF符號":         "負",
            "應收帳款季增率(%)":  None,
            "營收季增率(%)":      None,
            "總資產(千)":         round(_pp_assets),
            "總負債(千)":         round(_pp_liab),
            "流動負債(千)":       round(_pp_cur_l),
            "存貨(千)":           round(_pp_inv),
            "存貨前期(千)":       round(_pp_inv_p),
            "現金股利(千)":       round(_pp_div),
            "固定資產(千)":       round(_pp_ppe),
            "長期投資(千)":       round(_pp_lt_inv),
            "現金及約當現金(千)": round(_pp_cash),
            "應收帳款(千)":       round(_pp_ar),
            "EPS":                0,
            "預付款項(千)":       0,
            "其他非流動資產(千)": 0,
            "is_finance":         stock_id.startswith(('28', '58')),
        }

    return {
        "stock_id":         stock_id,
        "period":           _lat,
        "現金佔總資產(%)":  cash_ratio,
        "負債比率(%)":      debt_ratio,
        "OCF(千)":          round(ocf),
        "ICF(千)":          round(icf),
        "籌資CF(千)":       round(fncf),
        "自由現金流(千)":   fcf,
        "資本支出(千)":     round(capex),
        "應收帳款天數":     ar_days,
        "應付帳款天數":     ap_days,
        "毛利率(%)":        gm,
        "營業收入(千)":      round(rev),
        "毛利(千)":          round(gp),
        "營業利益(千)":      round(oper_income),
        "稅後淨利(千)":      round(net_ni),
        "股東權益(千)":      round(equity),
        "流動資產(千)":      round(cur_assets),
        "非流動負債(千)":    round(max(liab - cur_liab, 0)),
        "營業成本(千)":      round(cogs),
        "OCF符號":          "正" if ocf > 0 else "負",
        "ICF符號":          "正" if icf > 0 else "負",
        "籌資CF符號":       "正" if fncf > 0 else "負",
        "應收帳款季增率(%)": ar_chg,
        "營收季增率(%)":     rev_chg,
        "總資產(千)":        round(assets),
        "總負債(千)":        round(liab),
        "流動負債(千)":      round(cur_liab),
        "存貨(千)":          round(inv),
        "存貨前期(千)":      round(inv_p),
        "現金股利(千)":      round(div_paid),
        "固定資產(千)":      round(ppe),
        "長期投資(千)":      round(lt_inv),
        # ── v10.57.0 新增：老師 體檢原料（5 個）──
        "現金及約當現金(千)": round(cash),
        "應收帳款(千)":      round(ar),
        "EPS":               round(eps_v, 2) if eps_v else 0,
        "預付款項(千)":      round(prepaid),
        "其他非流動資產(千)": round(other_nca),
        "is_finance":        stock_id.startswith(('28', '58')),
        # ── 原始 slot 暴露：供診斷頁分辨「API 真失敗 / 此股無此科目 / 該股本季為 0」──
        "_bs_slot_latest":   dict(_bs_slot),
        "_cf_slot_latest":   dict(_cf.get(_lat, {})),
        "_is_slot_latest":   dict(_is.get(_lat, {})),
        "_period_latest":    _lat,
        # S-PROV-1 v18.250 phase 6:provenance(§2.2)
        "source":            "FinMind:FinancialStatements",
        "fetched_at":        pd.Timestamp.now('UTC').isoformat(),
        # v18.456: 上季關鍵指標，供 mj_trend bootstrap（ephemeral 重啟後仍可計算 2 季對比）
        "prev_period_data":  _prev_period_data,
    }
