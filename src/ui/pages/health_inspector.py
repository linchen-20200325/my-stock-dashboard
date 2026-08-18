"""資料健診儀表板（Raw Data Health Inspector）

從 etf_dashboard.py 抽出 — render_data_health_raw() 主要負責顯示「從網路 API
直接抓取的第一手原始資料」健康狀態。

絕對禁止：均線 / RSI / 乖離率 / AI 評分等任何計算值。
欄位：資料名稱 | 最後更新 | 狀態燈號

呼叫端：app.py:9055 `render_data_health_raw()`
"""
import datetime as _dt
from typing import Optional

import streamlit as st
from shared.colors import MATERIAL_ORANGE, TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.data_freshness import (
    freshness_level,
    monthly_freshness_level,
    quarterly_freshness_level,
)
from shared.staleness import stale_days_threshold, staleness_days
from shared.ttls import TTL_1DAY


# ══════════════════════════════════════════════════════════════════
# 資料新鮮度燈號 — v19.181 D3:從 `render_data_health_raw` 內的巢狀 closure
# `_light()` 抽到模組層,原因有三:(1) 巢狀 closure 無法單測;(2) 門檻全是
# 沒有名字的 inline 數字;(3) 其中兩條是實打實的錯,不是政策差異。
#
# ═══ 修的是什麼(逐條)═══════════════════════════════════════════════
# 【① 日頻沒有黃燈,而且紅線是全站第三個數字】
#   舊碼:`age <= 5 → 🟢,否則 🔴`。落後 6 天的日頻資料在這頁直接紅,
#   但同一個「🔎 資料診斷」Tab 的另外兩張表會說:
#       data_coverage(B4-a)   lag 6 → 🟡(warn 3 / bad = SSOT 7)
#       data_registry_panel   6 ≤ 7 → 🟢(FRESHNESS_THRESHOLDS_DAYS)
#   同一筆資料、同一個分頁,三種顏色。本版把**紅線**收斂到 SSOT
#   `shared.staleness.stale_days_threshold('daily')`,並補上黃燈帶,
#   黃燈起點沿用 data_coverage 已論證過的 3 天(= 一個週末的自然差值上限)。
#
# 【② `yearly` 恆綠 —— 這是說謊,不是寬鬆】
#   舊碼對 freq='yearly' 直接 `return '🟢', f'{age}天前'`,不看 age。
#   於是「最後一次配息在 2019 年」的個股,股利歷史照樣亮 🟢。
#   年頻資料一年一筆,超過一年又一個公告緩衝仍無新筆 = 真的斷了。
#
# 【③ `static` 落到日頻規則 → 把「任期長」判成「資料過期」】
#   ETF 經理人那列傳的 date 是**到職日**(`_mgr['since']`),freq='static'
#   在舊碼會 fall-through 到日頻的 `age <= 5`,於是一位在職 3 年的經理人
#   會被標成「1,100天前 ⚠️ 🔴」並列進「⚠️ 資料異常清單」。
#   到職日久遠是**好事**,語意上根本不是新鮮度問題 → static 只有兩態:抓到 / 沒抓到。
#
# ═══ 月頻:v19.181 D3 的 90/120 已於 G2(2026-08-08)收斂 ══════════════
# D3 當時的判斷「不能套 `STALE_DAYS_MONTHLY=45`」是**對的**(45 的推導前提是
# as_of 落在月底,而本表月頻大戶 FRED 的 as_of 是月初觀測日),但那時只是換上
# 另外兩個沒有推導過程的數字(90 / 120),於是全站月頻有三把尺:
#       data_coverage        45          → 當期 CPI 每天假紅
#       health_inspector     90 / 120    → 落後**整整一期**的資料只亮 🟡
#       data_registry_panel  90 / 180
# G2 的結論:病根不是「門檻幾天」,而是**拿日曆天去量一個以月為發布單位的東西**。
# 本檔月頻改與 data_coverage 共用同一條 L0 規則
# (`shared.data_freshness.monthly_freshness_level` → `staleness.monthly_release_status`):
#       落後 0 期 → 🟢 當期        (不論它的 as_of 是 37 天還是 89 天前)
#       下期逾原定發布日、仍在緩衝內 → 🟡 待公布（逾N日）
#       落後 ≥1 期 → 🔴 落後N期
# 代價:每一列月頻資料**必須指名它是哪個序列**(`indicator=`),因為發布延遲
# 逐源不同(PMI 1 天 / 出口 10 天 / CPI 13 天 / NDC 27 天)。沒指名 → ⬜「門檻未登錄」,
# **不**退回猜一個門檻(§1:不確定 ≠ 新鮮,也 ≠ 過期)。
#
# ═══ 季頻:G3(2026-08-08)把 150 天也一併收掉 ════════════════════════
# 同一個病在季頻更嚴重。台股季報 as_of = 季末,但下一份何時出現由**法定公告
# 截止日**決定,而那四個日子**不等距**:
#       Q1 5/15、Q2 8/14、Q3 11/14(以上皆季末 +45 天)、Q4 年報 次年 3/31(+90 天)
# ⇒ Q3 公布後要等 **4.5 個月**才有下一份,當期 Q3 的 as_of 年齡上限 196 天,
#   150 天門檻每年約 **3/02–4/14** 對一份完全當期的財報亮 🔴(每年約 30~44 天)。
# 本檔季頻改與 `ai_qa_service` 共用同一條 L0 規則
# (`shared.data_freshness.quarterly_freshness_level` → `staleness.quarterly_release_status`),
# 三態語意與月頻逐字相同,且**不需要 indicator**(法定日曆全市場一致)。
# ══════════════════════════════════════════════════════════════════

#: 日頻黃燈起點(日曆天)。與 `data_coverage._DIAG_DAILY_WARN_DAYS` **同值同理由**:
#: `staleness_days` 量的是日曆天,而「週五資料在週一被讀到」是完全正常的狀態,
#: lag 卻等於 3 → 低於 3 不報警,否則每個週一早上整頁假黃。
_INSPECTOR_DAILY_WARN_DAYS = 3

#: 年頻黃/紅(日曆天)。370 = 一年 + 5 天公告緩衝;400 = 再多一個多月仍無新筆 = 斷了。
#: (台股股利以「年度」標記,2025 年度股利在 2026 年中發放 → 標 2025-12-31,
#:  故 2026-08 讀到 2025-12-31 的 age≈219 天屬正常,不能用一年整當紅線。)
_INSPECTOR_YEARLY_WARN_DAYS = 370
_INSPECTOR_YEARLY_BAD_DAYS = 400

#: 「不過期」類別:經理人姓名 / 到職日這種**屬性**,只有「抓到 / 沒抓到」兩態。
FREQ_STATIC = 'static'


def freshness_bands(freq: str) -> tuple[int, int]:
    """回本頁對某發布頻率採用的 `(黃燈起點, 紅燈起點)`(**日曆天**)。

    紅線能取自 SSOT 的一律取自 `shared.staleness.stale_days_threshold()`;
    取不到的(年頻)用本檔具名常數,且在上方寫明為什麼不同。

    不變量(由 `tests/test_d3_toolbox_registry.py` 守):**warn ≤ bad**。
    設出「黃燈比紅燈還寬」= 黃燈永遠不會出現,是靜默失效。

    Raises
    ------
    ValueError
        `freq in ('monthly', 'quarterly')`。這兩種頻率**不存在**正確的日曆天
        門檻(見上方 G2 / G3 區塊):設小 → 當期假紅,設大 → 漏一期假綠。
        這裡刻意炸掉而不是回一組數字,是為了讓「有人又想給它一個天數」在第一
        時間就停下來,而不是多出第四把尺。
    """
    if freq == 'monthly':
        raise ValueError(
            "月頻不使用日曆天門檻:as_of 是資料月月初,任何天數門檻都會在"
            "『當期假紅』與『漏一期假綠』之間二選一。"
            "請改用 shared.data_freshness.monthly_freshness_level(as_of, indicator=...)")
    if freq == 'quarterly':
        raise ValueError(
            "季頻不使用日曆天門檻:台股季報的公告截止日是四個固定日曆日"
            "(Q1 5/15 / Q2 8/14 / Q3 11/14 / Q4 年報次年 3/31),Q3 之後要等 "
            "4.5 個月才有下一份 ⇒ 當期 Q3 的 as_of 年齡上限 196 天,"
            "150 天門檻每年約 3/02–4/14 對一份完全當期的財報亮假紅。"
            "請改用 shared.data_freshness.quarterly_freshness_level(as_of)")
    if freq == 'yearly':
        return (_INSPECTOR_YEARLY_WARN_DAYS, _INSPECTOR_YEARLY_BAD_DAYS)
    # daily 與所有未登記頻率 → 走最嚴的日頻(同 `stale_days_threshold` 的 fallback 政策)
    return (_INSPECTOR_DAILY_WARN_DAYS, stale_days_threshold('daily'))


def freshness_light(
    date_str,
    freq: str = 'daily',
    *,
    today: Optional[_dt.date] = None,
    indicator: Optional[str] = None,
) -> tuple[str, str]:
    """資料日期 → `(emoji, 人看的標籤)`。

    Parameters
    ----------
    date_str : str | date | None
        資料的最新日期(as-of)。None / 空 → 🔴 未取得。
    freq : str
        `daily` / `monthly` / `quarterly` / `yearly` / `static`;
        未知值一律退 daily(最嚴)。
    today : date | None
        測試注入用;None → 由 `shared.staleness` 取「預期最新交易日」。
    indicator : str | None
        **`freq='monthly'` 時必填**:該序列在
        `shared.staleness.MACRO_PUBLICATION_LAG_DAYS` 的 key
        (`us_core_cpi` / `ism_pmi` / `tw_export` / `ndc_signal` / `fed_funds` /
        `tw_monthly_revenue` / `m1b_m2`)。缺 / 未登錄 → ⬜「門檻未登錄」。

    Notes
    -----
    **落後天數的量法也統一了**:舊碼用 `Timestamp.now().normalize()`(日曆今天),
    本版改吃 `shared.staleness.staleness_days()`(= 距**預期最新交易日**),
    與 data_coverage 同一個基準 —— 否則週末讀盤後資料會憑空多算 1-2 天 lag。

    **月頻不走天數**(G2,見上方區塊):委派 L0
    `shared.data_freshness.monthly_freshness_level()`,與 data_coverage 同一份規則
    —— 同一筆 as_of 在兩頁必得同一個燈號(由 tests/test_g2_monthly_freshness.py 釘)。

    其餘頻率的 emoji 規則委派 L0 `shared.data_freshness.freshness_level()`,
    本檔只決定「這個頻率該用哪組門檻」+ 標籤措辭,不重寫一套 emoji 判定。
    """
    if not date_str:
        return '🔴', '未取得'
    if freq == FREQ_STATIC:
        # 屬性類:有值就是有值,不隨時間過期(到職日越久 = 任期越長 = 好事)。
        return '🟢', '已取得'
    if freq == 'monthly':
        return monthly_freshness_level(date_str, indicator=indicator, today=today)
    if freq == 'quarterly':
        # G3:季頻同樣改判發布期數(as_of = 季末,下一份由**法定公告截止日**決定,
        # 而那四個日子不等距 → 任何日曆天門檻都會對 Q3 假紅)。不需要 indicator:
        # 台股季報公告期限是全市場一致的法定日曆,不逐序列不同。
        return quarterly_freshness_level(date_str, today=today)
    _lag = staleness_days(date_str, today=today)
    if _lag is None:
        return '🔴', '無法解析'
    _warn, _bad = freshness_bands(freq)
    _emoji, _ = freshness_level(_lag, warn=_warn, bad=_bad)
    _age = max(0, int(_lag))
    _lbl = '今天' if _age == 0 else ('昨天' if _age == 1 else f'{_age}天前')
    if _emoji == '🔴':
        return _emoji, f'{_age}天前 ⚠️'
    return _emoji, _lbl

# ══════════════════════════════════════════════════════════════════
# 資料診斷 v2：嚴格 Raw-only 版
# ══════════════════════════════════════════════════════════════════
def render_data_health_raw():
    """
    只顯示從網路 API 直接抓取的第一手原始資料。
    絕對禁止：均線 / RSI / 乖離率 / AI 評分等任何計算值。
    欄位：資料名稱 | 最後更新 | 狀態燈號
    """
    import pandas as _pd_r
    import datetime as _dt_r

    # v19.181 D3:原本這裡有 `_today = Timestamp.now().normalize()`,只被舊的
    # 巢狀 `_light()` 用來算日曆天差。落後天數改由 `shared.staleness.staleness_days`
    # (基準 = 預期最新交易日)計算後,本變數已無 caller,刪除。

    def _last_date(df):
        """從 DataFrame 取最新日期字串 YYYY-MM-DD"""
        try:
            if df is None or (hasattr(df, 'empty') and df.empty):
                return None
            if isinstance(df.index, _pd_r.DatetimeIndex):
                v = _pd_r.Timestamp(df.index.max())
                return v.strftime('%Y-%m-%d') if not _pd_r.isna(v) else None
            for col in (['_date', 'date', 'Date', '日期', 'period', 'quarter', '季度標籤']
                        if hasattr(df, 'columns') else []):
                if col in df.columns:
                    v = _pd_r.to_datetime(df[col], errors='coerce').max()
                    if not _pd_r.isna(v):
                        return v.strftime('%Y-%m-%d')
        except Exception:
            pass
        return None

    def _last_date_col(df, col):
        """從 DataFrame 取特定欄位有值的最新日期"""
        try:
            if df is None or (hasattr(df, 'empty') and df.empty):
                return None
            if col not in df.columns:
                return None
            sub = df[df[col].notna()]
            return _last_date(sub) if not sub.empty else None
        except Exception:
            return None

    def _probe_col(df, col):
        """欄位三態探測：分辨「fetch 失敗 / 此股無此欄 / 該股本期為空 / 已抓到」。
        Returns: (status, last_date)
          status: 'fail' (df 整個沒抓到) / 'na' (df 有但無此欄) / 'zero' (有欄但全空) / 'ok'
        """
        try:
            if df is None or (hasattr(df, 'empty') and df.empty):
                return ('fail', None)
            if col not in df.columns:
                return ('na', None)
            sub = df[df[col].notna()]
            if sub.empty:
                return ('zero', None)
            return ('ok', _last_date(sub))
        except Exception:
            return ('fail', None)

    def _probe_fin_field(fin_raw, key, aliases, slot='_bs_slot_latest'):
        """財報欄位三態探測（針對 _fin_raw2 內的 dict）。
        Returns: (status, value)
          'fail': fin_raw 整體錯誤（API 沒回）
          'na'  : raw slot 內無任一 alias（此股無此科目）
          'zero': raw slot 有 alias 但值為 0（該股本季為 0）
          'ok'  : 有值 > 0
        """
        try:
            if not fin_raw or fin_raw.get('error'):
                return ('fail', None)
            v = float(fin_raw.get(key) or 0)
            if v > 0:
                return ('ok', v)
            _slot = fin_raw.get(slot) or {}
            if not _slot:
                # 沒有 raw slot（舊版 fetcher 或解析失敗）→ 退化為 'fail'
                return ('fail', None)
            for _a in aliases:
                if _a in _slot:
                    try:
                        return ('zero', float(str(_slot[_a]).replace(',', '') or 0))
                    except Exception:
                        return ('zero', 0.0)
            return ('na', None)
        except Exception:
            return ('fail', None)

    def _light(date_str, freq='daily', indicator=None):
        """回傳 (icon, label)。門檻與量法一律走模組層 `freshness_light`(v19.181 D3)。

        保留這層薄 wrapper 只是為了不動下方 ~40 處 caller 的呼叫寫法;
        真正的規則、常數與理由全在 `freshness_light` / `freshness_bands`。

        `indicator` 只有 freq='monthly' 用得到(G2:月頻改判發布期數,
        各序列的發布延遲不同 → 必須指名是哪一個序列)。
        """
        return freshness_light(date_str, freq, indicator=indicator)

    # 'static' = 不隨時間過期的屬性(經理人姓名 / 到職日)。原本沒登記,
    # 於是「頻率」欄會直接印出英文 `static`,與其餘中文標籤不一致。
    _FREQ_LBL = {'daily': '日頻', 'monthly': '月頻', 'quarterly': '季頻',
                 'yearly': '不定期', FREQ_STATIC: '不過期'}

    def _row(name, date_str, freq='daily', error_msg=None, optional=False,
             source='', endpoint='', proxy=False, probe_status=None,
             indicator=None):
        """資料新鮮度單列。
        indicator: freq='monthly' 時必填，見 `freshness_light` docstring
        source: 來源系統（如 FRED / yfinance / FinMind）
        endpoint: API 端點 / Ticker（如 NAPM / ^VIX）
        proxy: 是否經 Squid Proxy 出口（True=✅ / False=—）
        probe_status: 三態探測結果，覆蓋預設燈號邏輯
          'na'   → ⚪ 此股無此科目（非異常，不入異常清單）
          'zero' → 🔵 該股本期為 0（非異常）
          'fail' → 🔴 fetch 失敗（真異常）
          'ok'   → 套既有 _light 流程
        """
        _fl = _FREQ_LBL.get(freq, freq)
        _px = '✅' if proxy else '—'
        _base = {'資料名稱': name, '頻率': _fl, '來源': source or '—',
                 '端點': endpoint or '—', 'Proxy': _px}
        # ── probe_status 優先：分辨 N/A vs zero vs fail ─────────────
        if probe_status == 'na':
            # error_msg 帶自訂 N/A 說明（海外 ETF / 此股無此科目 等情境）
            _na_lbl = f'⚪ {str(error_msg)[:55]}' if error_msg else '⚪ 此股無此科目'
            return {**_base, '最後更新': _na_lbl, '日期': '—', '狀態': '⚪'}
        if probe_status == 'zero':
            return {**_base, '最後更新': '🔵 該股本期為 0',
                    '日期': '—', '狀態': '🔵'}
        if probe_status == 'fail':
            _emsg = f'🔴 抓取失敗：{str(error_msg)[:50]}' if error_msg else '🔴 抓取失敗'
            return {**_base, '最後更新': _emsg, '日期': '—', '狀態': '🔴'}
        # ── 既有邏輯 ─────────────────────────────────────────────
        if not date_str and error_msg:
            short = str(error_msg)[:55]
            return {**_base, '最後更新': f'❌ {short}', '日期': '—', '狀態': '🔴'}
        if not date_str and optional:
            # 走到這代表 caller 沒給 probe_status — 保守標 ⚪ N/A，避免假性紅燈
            return {**_base, '最後更新': '⚪ 此股無此科目', '日期': '—', '狀態': '⚪'}
        if not date_str:
            return {**_base, '最後更新': '🔴 未取得', '日期': '—', '狀態': '🔴'}
        icon, lbl = _light(date_str, freq, indicator)
        return {**_base, '最後更新': lbl, '日期': str(date_str)[:10], '狀態': icon}

    def _tbl(rows):
        if not rows:
            st.info('尚無資料（請先觸發對應的抓取動作）')
            return
        _df_t = _pd_r.DataFrame(rows)
        # 固定欄位順序：先體檢模組分組 → 名稱/適用指標 → 來源/端點/Proxy → 時序 → 狀態
        _order = ['體檢模組', '資料名稱', '適用體檢指標', '來源', '端點', 'Proxy',
                  '頻率', '日期', '最後更新', '狀態']
        _cols  = [c for c in _order if c in _df_t.columns] + \
                 [c for c in _df_t.columns if c not in _order]
        st.dataframe(_df_t[_cols], use_container_width=True, hide_index=True)

    # ── 標題 ─────────────────────────────────────────────────────
    st.markdown('### 🔎 原始資料健診儀表板')
    st.caption(
        '📌 **僅顯示從網路 API 直接抓取的第一手原始資料**。'
        '均線、RSI、乖離率、AI 評分等計算指標**不在此列**。'
    )

    # ── 燈號圖例 + 重新整理按鈕（不再要求用戶手動觸發按鈕流程）──
    _bn1, _bn2 = st.columns([8, 2])
    with _bn1:
        st.info(
            '💡 **燈號語意**：'
            '🟢 已抓取且新鮮 ｜ 🟡 時效延遲或待補抓 ｜ '
            '🔵 該股本期數值為 0（非異常） ｜ ⚪ 此股無此科目（非異常） ｜ '
            '🔴 真失敗（API/proxy/網路問題）'
        )
    with _bn2:
        if st.button('🔄 重新整理', key='btn_diag_rerun', use_container_width=True):
            st.rerun()

    # ── [v10.56.0] 立即測試融資餘額 6 段備援（FinMind + 5 段網爬）──
    _diag_c1, _diag_c2 = st.columns([3, 7])
    with _diag_c1:
        if st.button('🩺 立即測試融資餘額（6段備援）',
                     key='btn_test_margin', use_container_width=True):
            try:
                from src.services import fetch_margin_balance as _fmb_test
                from src.config import PKL_DIR as _pkl_dir_t
                import os as _os_t
                # 只清 margin_balance 快取，不影響其他 fetcher 快取
                _mb_pkl = _os_t.path.join(_pkl_dir_t, 'margin_balance.pkl')
                try:
                    if _os_t.path.exists(_mb_pkl):
                        _os_t.remove(_mb_pkl)
                except Exception:
                    pass
                with st.spinner('測試中（最多 35 秒，依序試 6 段備援）…'):
                    _mb_v = _fmb_test()
                if _mb_v is not None:
                    st.session_state.setdefault('cl_data', {})['margin'] = _mb_v
                    st.session_state['_diag_margin_msg'] = (
                        f'✅ 融資餘額抓取成功：**{_mb_v} 億元**（請看 console log 判斷哪段命中）'
                    )
                else:
                    st.session_state['_diag_margin_msg'] = (
                        '❌ 6 段備援全部失效。可能原因：FinMind Token 額度耗盡 / NAS proxy 斷線 / 全部來源全擋 / 非交易日。\n\n'
                        '請查 console log 找 `[融資餘額/...]` 相關訊息。'
                    )
                st.rerun()
            except Exception as _emb:
                st.session_state['_diag_margin_msg'] = f'❌ 測試異常：{type(_emb).__name__}: {_emb}'
                st.rerun()
    with _diag_c2:
        _diag_msg = st.session_state.get('_diag_margin_msg')
        if _diag_msg:
            if _diag_msg.startswith('✅'):
                st.success(_diag_msg)
            else:
                st.error(_diag_msg)

    # ── 🛰️ NAS 代理 + ETF 成分股抓取自我檢測（確認 PROXY_URL 是否生效）──
    _px_c1, _px_c2 = st.columns([3, 7])
    with _px_c1:
        if st.button('🛰️ 測試 NAS 代理 + 成分股',
                     key='btn_test_proxy', use_container_width=True):
            import time as _tt
            import re as _re_px
            _lines = []
            _ok = True
            try:
                from src.data.proxy import get_proxy_config, get_nas_relay, fetch_url
                # 1) 代理偵測（密碼遮蔽，不外洩 secret）
                _pc = get_proxy_config()
                if _pc and _pc.get('http'):
                    _masked = _re_px.sub(r'//([^:/]+):[^@]+@', r'//\1:***@',
                                         str(_pc['http']))
                    _lines.append(f'🔑 Squid 代理 PROXY_URL 已偵測：`{_masked}`')
                else:
                    _ok = False
                    _lines.append('⚪ **未偵測到 PROXY_URL**（Streamlit Cloud → Settings → '
                                  'Secrets 尚未設定 NAS Squid 代理）')
                _relay = get_nas_relay()
                _lines.append(f'🔁 NAS FastAPI 中繼站：'
                              f'{"已設定 `" + _relay[0] + "`" if _relay else "未設定"}')
                # 2) 出口 IP（透過代理）— 確認是否走台灣 IP
                try:
                    _rip = fetch_url('https://api.ipify.org?format=json',
                                     timeout=10, attempts=1)
                    if _rip is not None and _rip.status_code == 200:
                        _ip = _re_px.search(r'"ip"\s*:\s*"([^"]+)"', _rip.text)
                        _lines.append(f'🌐 對外出口 IP：`{_ip.group(1) if _ip else _rip.text[:40]}`'
                                      '（應為你 NAS 的台灣 IP；若為海外機房 IP 代表代理未生效）')
                    else:
                        _lines.append('🌐 出口 IP 測試無回應（不一定影響成分股，續看下方實測）')
                except Exception as _eip:
                    _lines.append(f'🌐 出口 IP 測試略過：{type(_eip).__name__}')
                # 3) 台灣 Yahoo 股市直測（國內版 Yahoo，海外 IP 可直連）
                from src.data.etf import _fetch_holdings_yahoo_tw, fetch_etf_holdings
                try:
                    _yh = _fetch_holdings_yahoo_tw('0050.TW')
                    if _yh:
                        _lines.append(f'🇹🇼 台灣 Yahoo 股市：✅ 0050.TW 取得 {len(_yh)} 檔持股（主源生效）')
                    else:
                        _lines.append('🇹🇼 台灣 Yahoo 股市：⚪ 0050.TW 解析不出持股'
                                      '（頁面結構可能改版，續看下方整合結果）')
                except Exception as _eyh:
                    _lines.append(f'🇹🇼 台灣 Yahoo 股市：測試異常 {type(_eyh).__name__}')
                # 4) 實測整合抓取 0050.TW 成分股（清快取確保真打網路）
                try:
                    fetch_etf_holdings.clear()
                except Exception:
                    pass
                _t0 = _tt.time()
                with st.spinner('實測整合抓取 0050.TW 成分股中…'):
                    _h = fetch_etf_holdings('0050.TW')
                _dt = _tt.time() - _t0
                if _h:
                    _lines.append(f'✅ **0050.TW 成分股抓取成功：{len(_h)} 檔**（{_dt:.1f}s）'
                                  '— 代理生效，其他台股 ETF（含主動式）應一併恢復')
                else:
                    _ok = False
                    _lines.append(f'❌ **0050.TW 成分股仍抓不到**（{_dt:.1f}s）'
                                  '— 代理未生效或來源全擋；請查 console `[Holdings/...]` log')
            except Exception as _epx:
                _ok = False
                _lines.append(f'❌ 測試異常：{type(_epx).__name__}: {_epx}')
            st.session_state['_diag_proxy_ok']  = _ok
            st.session_state['_diag_proxy_msg'] = '\n\n'.join(_lines)
            st.rerun()
    with _px_c2:
        _pm = st.session_state.get('_diag_proxy_msg')
        if _pm:
            (st.success if st.session_state.get('_diag_proxy_ok') else st.warning)(_pm)

    # ══════════════════════════════════════════════════════════════
    # 📊 全域資料健康總表（統一視圖）
    # ══════════════════════════════════════════════════════════════
    st.markdown('#### 📊 全域資料健康總表')
    st.caption('一覽所有資料來源的最新狀態 ｜ 色塊代表新鮮度（🟢新鮮 / 🟡可接受 / 🔴過舊）｜ 下次 Release 來自 FRED API（30 天 cache）')

    _ma_g  = st.session_state.get('macro_info') or {}
    _cl_g  = st.session_state.get('cl_data')    or {}
    _mi_g  = st.session_state.get('m1b_m2_info') or {}
    _li_g  = st.session_state.get('li_latest')
    _t2_g  = st.session_state.get('t2_data')    or {}
    _e1_g  = st.session_state.get('etf_single_data') or {}
    _cl_ts_g = str(st.session_state.get('cl_ts', ''))[:10] or None

    # v18.225 T2：FRED 下次 release 取值（30 天 cache → rerun 不重打 API）
    import os as _os_hi
    try:  # v19.81:無 secrets.toml 時 st.secrets.get 會 raise(CI/裸跑)→ 降級 env-only
        _sec_fred_hi = st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else None
    except Exception:
        _sec_fred_hi = None
    _fred_key_hi = (_os_hi.environ.get('FRED_API_KEY') or _sec_fred_hi or '')
    try:
        from src.data.macro import fred_get_next_release_date as _fred_nrd
    except Exception:
        _fred_nrd = None

    @st.cache_data(ttl=TTL_1DAY, show_spinner=False)
    def _next_release_cached(series_id: str, api_key_present: bool) -> str:
        """Streamlit 層多包一層 1 日 cache，避免 macro_core 30 天 disk cache 之外仍重複打。
        api_key_present 進入 cache key 確保切換 secrets 時 invalidates。"""
        if not series_id or not api_key_present or _fred_nrd is None:
            return ''
        try:
            _d = _fred_nrd(series_id, _fred_key_hi)
            return _d.isoformat() if _d else ''
        except Exception:
            return ''

    _global_rows = []

    def _g_add(name, source, freq, df=None, date_str=None, count=None,
               fred_series_id: str = '', indicator: str = ''):
        """indicator: freq='monthly' 時必填(G2),見 `freshness_light` docstring。"""
        if isinstance(df, _pd_r.DataFrame) and not df.empty:
            _d = _last_date(df)
            _cnt = len(df) if count is None else count
        else:
            _d = date_str
            _cnt = count
        if _d:
            icon, lbl = _light(_d, freq, indicator or None)
            _fresh = f'{icon} {lbl}'
        else:
            _fresh = '🔴 未取得'
        # v18.225 T2：僅 FRED-backed 指標查下次 release，其餘留空 "—"
        _nr = _next_release_cached(fred_series_id, bool(_fred_key_hi)) if fred_series_id else ''
        _global_rows.append({
            '資料名稱': name,
            '來源':     source,
            '頻率':     _FREQ_LBL.get(freq, freq),
            '最新日期': _d or '—',
            '新鮮度':   _fresh,
            '下次Release': _nr or '—',
            '筆數':     _cnt if _cnt is not None else '—',
        })

    # 總經
    _g_add('VIX 恐慌指數',     'yfinance',       'daily',
           date_str=str((_ma_g.get('vix') or {}).get('date',''))[:10] or _cl_ts_g
                    if (_ma_g.get('vix') or {}).get('current') is not None else None)
    _g_add('美國核心 CPI YoY', 'FRED',           'monthly',
           date_str=str((_ma_g.get('us_core_cpi') or {}).get('date',''))[:10] or None,
           fred_series_id='CPILFESL', indicator='us_core_cpi')
    _g_add('🇹🇼 台灣製造業 PMI',
           'CIER-EN+data.gov.tw+NDC+CIER首頁+StockFeel+鉅亨+CIER-cid8+MoneyDJ 8 段', 'monthly',
           date_str=str((_ma_g.get('ism_pmi') or {}).get('date',''))[:10] or None,
           indicator='ism_pmi')
    _g_add('NDC 景氣燈號',      'StockFeel+MacroMicro 雙源', 'monthly',
           date_str=str((_ma_g.get('ndc_signal') or {}).get('date',''))[:10] or None,
           indicator='ndc_signal')
    _g_add('台灣出口 YoY',      'stat.gov.tw+FRED+data.gov.tw/6053(海關新臺幣)+CKAN 5段', 'monthly',
           date_str=str((_ma_g.get('tw_export') or {}).get('date',''))[:10] or None,
           indicator='tw_export')
    # ⚠️ 已知 provenance 缺口(G2 記錄,非本輪修):本列餵進去的 `cl_ts` 是**抓取時間**,
    #    不是 M1B/M2 的資料月 as_of(m1b_m2_info 目前不帶資料日期)。任何新鮮度規則
    #    量抓取時間都只會恆綠。改法屬 §2.2 provenance 另案(要 fetcher 先帶出 as_of)。
    _g_add('台灣 M1B / M2',    'CBC + FinMind 雙源',         'monthly',
           date_str=(_cl_ts_g if _mi_g.get('m1b_yoy') is not None else None),
           indicator='m1b_m2')

    # v18.226：外資連續日數（fetch_foreign_consecutive_days → _fi_streak_cache）
    _fi_streak_g = st.session_state.get('_fi_streak_cache') or {}
    _g_add('外資連續日數', 'FinMind TaiwanStockTotalInstitutionalInvestors', 'daily',
           date_str=(_fi_streak_g.get('date_latest') or None)
                    if _fi_streak_g.get('consec_days') is not None else None)

    # 大盤指數 + 籌碼
    for _gk, _glbl, _gsrc in [
        ('intl', '國際指數 OHLCV',    'yfinance'),
        ('tw',   '台股指數 OHLCV',    'yfinance'),
        ('tech', '科技股指數 OHLCV',  'yfinance'),
    ]:
        _grp = _cl_g.get(_gk) or {}
        _dfs = [df for df in _grp.values() if isinstance(df, _pd_r.DataFrame) and not df.empty] \
               if isinstance(_grp, dict) else []
        _maxd = max((_last_date(d) for d in _dfs), default=None) if _dfs else None
        _cnt  = sum(len(d) for d in _dfs) if _dfs else None
        _g_add(_glbl, _gsrc, 'daily', date_str=_maxd or _cl_ts_g, count=_cnt)

    _inst_df = _cl_g.get('inst')
    # inst 是 dict（非 DataFrame）→ 必須有 key 才算真有資料，避免 {} 被誤判 🟢
    _inst_has_data = (isinstance(_inst_df, dict) and len(_inst_df) > 0) or \
                     (isinstance(_inst_df, _pd_r.DataFrame) and not _inst_df.empty)
    _g_add('三大法人現貨買賣超', 'TWSE BFI82U', 'daily',
           df=_inst_df if isinstance(_inst_df, _pd_r.DataFrame) else None,
           date_str=(_cl_ts_g if _inst_has_data and not isinstance(_inst_df, _pd_r.DataFrame) else None))
    _g_add('融資餘額',           'FinMind+TWSE+HiStock+Goodinfo+Yahoo+鉅亨 6段備援', 'daily',
           date_str=(_cl_ts_g if _cl_g.get('margin') is not None else None))
    _adl_df = _cl_g.get('adl')
    _g_add('ADL 漲跌家數',       'yfinance/TWSE', 'daily',
           df=_adl_df if isinstance(_adl_df, _pd_r.DataFrame) else None,
           date_str=_cl_ts_g if _adl_df is not None and not isinstance(_adl_df, _pd_r.DataFrame) else None)

    # 先行指標
    if isinstance(_li_g, _pd_r.DataFrame) and not _li_g.empty:
        _g_add('先行指標（外資期貨/法人/PCR）', 'FinMind/TAIFEX', 'daily', df=_li_g)
    else:
        _g_add('先行指標（外資期貨/法人/PCR）', 'FinMind/TAIFEX', 'daily', date_str=None)

    # 個股
    if _t2_g.get('df') is not None:
        _g_add(f'個股 K線 {_t2_g.get("sid","-")}', 'FinMind / yfinance', 'daily',
               df=_t2_g.get('df'))
        _g_add(f'個股月營收 {_t2_g.get("sid","-")}', 'FinMind', 'monthly',
               df=_t2_g.get('rev'), indicator='tw_monthly_revenue')
        _g_add(f'個股季財報 {_t2_g.get("sid","-")}', 'FinMind', 'quarterly',
               df=_t2_g.get('qtr'))

    # ETF
    if _e1_g.get('ticker'):
        _g_add(f'ETF K線 {_e1_g.get("ticker")}', 'yfinance', 'daily',
               df=_e1_g.get('price_df'))

    if _global_rows:
        _fresh_cnt = {'🟢': 0, '🟡': 0, '🔴': 0}
        for _r in _global_rows:
            _ic = (_r['新鮮度'] or '')[:1]
            if _ic in _fresh_cnt: _fresh_cnt[_ic] += 1
        _total = len(_global_rows)
        _ok_pct = round(_fresh_cnt['🟢'] / _total * 100) if _total else 0
        _light_color = (TRAFFIC_GREEN if _ok_pct >= 80 else
                        TRAFFIC_YELLOW if _ok_pct >= 50 else TRAFFIC_RED)
        _light_label = ('🟢 綠燈（資料健康）' if _ok_pct >= 80 else
                        '🟡 黃燈（部分缺失，AI 仍可執行，參考性降低）' if _ok_pct >= 50 else
                        '🔴 紅燈（資料不足，建議重新更新）')
        st.markdown(
            f'<div style="background:#0d1117;border-left:4px solid {_light_color};border-radius:0 6px 6px 0;'
            f'padding:8px 14px;margin-bottom:10px;font-size:13px;">'
            f'<b style="color:{_light_color};">{_light_label}</b>'
            f'<span style="color:#8b949e;margin-left:14px;">'
            f'共 {_total} 個資料源 ｜ 🟢 {_fresh_cnt["🟢"]} ｜ 🟡 {_fresh_cnt["🟡"]} ｜ 🔴 {_fresh_cnt["🔴"]} ｜ 健康度 {_ok_pct}%'
            f'</span></div>', unsafe_allow_html=True)

        # ── [v10.55.1 統一 UI] 三組 multiselect 篩選器（狀態 / 來源 / 頻率）──
        _opts_status_g = sorted({(r['新鮮度'] or '')[:1] for r in _global_rows
                                 if (r['新鮮度'] or '')[:1] in ('🟢', '🟡', '🔴')})
        _opts_source_g = sorted({r['來源'] for r in _global_rows if r.get('來源')})
        _opts_freq_g   = sorted({r['頻率'] for r in _global_rows if r.get('頻率')})
        _flt_g1, _flt_g2, _flt_g3 = st.columns([1, 2, 1])
        with _flt_g1:
            _sel_status_g = st.multiselect(
                '狀態', _opts_status_g, default=_opts_status_g, key='glb_flt_status'
            )
        with _flt_g2:
            _sel_source_g = st.multiselect(
                '來源', _opts_source_g, default=_opts_source_g, key='glb_flt_source'
            )
        with _flt_g3:
            _sel_freq_g = st.multiselect(
                '頻率', _opts_freq_g, default=_opts_freq_g, key='glb_flt_freq'
            )

        _rows_filtered = [
            r for r in _global_rows
            if (r['新鮮度'] or '')[:1] in _sel_status_g
            and (r.get('來源', '') in _sel_source_g or not r.get('來源'))
            and (r.get('頻率', '') in _sel_freq_g or not r.get('頻率'))
        ]

        # ── 頻率徽章顏色（與基金端對齊）──
        _FREQ_COLOR = {
            '日頻':   '#42a5f5',
            '月頻':   MATERIAL_ORANGE,
            '季頻':   '#ef5350',
            '不定期': '#9e9e9e',
        }
        _th_g = ('font-size:10px;color:#888;font-weight:700;padding:4px 8px;'
                 'border-bottom:1px solid #30363d')
        _td_g = 'font-size:11px;padding:4px 8px'
        # v18.225 T2：grid 6→7 欄，第 6 欄為「下次 Release」（FRED-backed 才有值）
        _hdr_g = (
            f"<div style='display:grid;grid-template-columns:2fr 1.6fr 0.7fr 1fr 1.4fr 1fr 0.7fr;"
            f"background:#0d1117;border-radius:6px 6px 0 0'>"
            f"<span style='{_th_g}'>資料名稱</span>"
            f"<span style='{_th_g}'>來源</span>"
            f"<span style='{_th_g}'>頻率</span>"
            f"<span style='{_th_g}'>最新日期</span>"
            f"<span style='{_th_g}'>新鮮度</span>"
            f"<span style='{_th_g}'>下次 Release</span>"
            f"<span style='{_th_g}'>筆數</span>"
            f"</div>"
        )
        _rows_html_g = _hdr_g
        for _r in _rows_filtered:
            _ic_r = (_r['新鮮度'] or '')[:1]
            _row_bg = ('#161b22' if _ic_r == '🟢' else
                       '#1a1200' if _ic_r == '🟡' else '#1a0808')
            _fcol_r = (TRAFFIC_GREEN if _ic_r == '🟢' else
                       TRAFFIC_YELLOW if _ic_r == '🟡' else TRAFFIC_RED)
            _fq = _r.get('頻率', '')
            _fc = _FREQ_COLOR.get(_fq, '#9e9e9e')
            _rows_html_g += (
                f"<div style='display:grid;grid-template-columns:2fr 1.6fr 0.7fr 1fr 1.4fr 1fr 0.7fr;"
                f"background:{_row_bg};border-bottom:1px solid #21262d'>"
                f"<span style='{_td_g};color:#e6edf3'>{_r.get('資料名稱','')}</span>"
                f"<span style='{_td_g};color:#888'>{_r.get('來源','')}</span>"
                f"<span style='{_td_g}'>"
                f"<span style='background:{_fc}22;color:{_fc};border:1px solid {_fc};"
                f"border-radius:10px;padding:1px 7px;font-size:10px;font-weight:700'>"
                f"{_fq}</span></span>"
                f"<span style='{_td_g};color:#aaa'>{_r.get('最新日期','—')}</span>"
                f"<span style='{_td_g};color:{_fcol_r};font-weight:600'>{_r.get('新鮮度','')}</span>"
                f"<span style='{_td_g};color:#aaa'>{_r.get('下次Release','—')}</span>"
                f"<span style='{_td_g};color:#aaa'>{_r.get('筆數','—')}</span>"
                f"</div>"
            )
        st.markdown(
            f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
            f"{_rows_html_g}</div>",
            unsafe_allow_html=True,
        )
        _shown_g = len(_rows_filtered)
        if _shown_g < _total:
            st.caption(f'已篩選：顯示 {_shown_g}/{_total}　｜　🟢 {_fresh_cnt["🟢"]}　🟡 {_fresh_cnt["🟡"]}　🔴 {_fresh_cnt["🔴"]}')
    else:
        st.info('尚未載入任何資料。系統會於下次背景輪詢自動補抓；可點上方「🔄 重新整理」即時重抓。')

    # ══════════════════════════════════════════════════════════════
    # 🔍 詳細抽查（依資料類別）
    # ══════════════════════════════════════════════════════════════
    st.markdown('---')
    st.markdown('#### 🔍 詳細抽查（依資料類別）')

    # 累積各 expander 內的 detail rows，供下方「⚠️ 資料異常清單」併入（個股+ETF granular missing 也算）
    _all_section_rows: list = []

    # ════ 1. 總經 Raw ════════════════════════════════════════════
    with st.expander('🌍 總經 Raw Data', expanded=False):
        _ma = st.session_state.get('macro_info') or {}
        # 三態判斷：
        # 1. _ma 整體缺 → 從未抓取（提示用戶點 Tab 4 一鍵更新）
        # 2. _ma 有 _all_failed → 抓過但全失敗（網路/proxy 問題）
        # 3. _ma 有部分 keys → 個別缺失才標 🔴
        _ma_never = not _ma
        _ma_all_failed = bool(_ma.get('_all_failed'))
        _ma_loaded_at = str(_ma.get('_loaded_at', ''))[:16]
        rows = []
        for label, key, freq, err_key, src, ep, px in [
            ('VIX 恐慌指數',          'vix',         'daily',   '_err_vix',
             'yfinance',                      '^VIX',                                False),
            ('美國核心 CPI YoY',       'us_core_cpi', 'monthly', '_err_cpi',
             'FRED',                          'CPILFESL',                            True),
            ('🇹🇼 台灣製造業 PMI',     'ism_pmi',     'monthly', '_err_pmi',
             'CIER-EN+data.gov.tw+NDC+CIER首頁+StockFeel+鉅亨+CIER-cid8+MoneyDJ 8段',
             'cier.edu.tw / data.gov.tw/dataset/6100 / index.ndc / stockfeel / cnyes / MoneyDJ', True),
            ('NDC 景氣燈號分數',        'ndc_signal',  'monthly', '_err_ndc',
             'FinMind-TBI+StockFeel+MacroMicro 三源',
             'TaiwanBusinessIndicator / stockfeel/biz-light + charts/2',           True),
            ('台灣出口 YoY',           'tw_export',   'monthly', '_err_export',
             'stat.gov.tw+FRED+data.gov.tw+CKAN 5段', 'XTEXVA01TWM664S',             True),
        ]:
            item = _ma.get(key) or {}
            date = (item.get('date') or item.get('period') or
                    str(item.get('year', ''))[:7] or None)
            if not date:
                if _ma_never:
                    # 整批沒抓 — 黃燈友善提示。
                    # v18.436 #21 翻案:原訊息「系統下次背景輪詢自動處理」是空承諾 —
                    # session_state['macro_info'] 只在 user 點「🚀 一鍵更新」時才填,
                    # 無任何背景 scheduler 會補(cron 只更新 history parquet,不碰 session)。
                    # 改為誠實導引使用者手動觸發,對齊 L561 註解。
                    rows.append({**{'資料名稱': label, '頻率': _FREQ_LBL.get(freq, freq),
                                    '來源': src, '端點': ep, 'Proxy': '✅' if px else '—'},
                                 # B6-a v19.181:Tab 名對齊 app.py:568（真名 🌍 總經）
                                 '最後更新': '⚪ 尚未抓取（請至「🌍 總經」分頁點「🚀 一鍵更新」）',
                                 '日期': '—', '狀態': '⚪'})
                    continue
                if _ma_all_failed:
                    err = (f'抓取失敗（{_ma_loaded_at}）｜全部 5 段備援均無回應；'
                           f'通常是 Streamlit Cloud 海外 IP 對台灣源限制')
                else:
                    # 三層 fallback：err_key → _all_failed → 「key 缺失但其他來源已抓」
                    err = (_ma.get(err_key)
                           or f'此來源回傳缺 date/period（已抓 {_ma_loaded_at}），其他總經 keys 正常；'
                              f'多半是 HTML 結構改版或 proxy 對單站 block')
                rows.append(_row(label, None, freq,
                                 error_msg=err, source=src, endpoint=ep, proxy=px))
            else:
                # G2:月頻走發布期數規則 → indicator 就是 macro_info 的 key
                # (與 shared.staleness.MACRO_PUBLICATION_LAG_DAYS 同名)。
                rows.append(_row(label, str(date)[:10], freq,
                                 source=src, endpoint=ep, proxy=px,
                                 indicator=key))
        # M1B / M2（無獨立 date 欄位，以 cl_ts 代理）
        _mi = st.session_state.get('m1b_m2_info') or {}
        _mi_date = None
        if _mi.get('m1b_yoy') is not None:
            _mi_date = str(st.session_state.get('cl_ts', ''))[:10] or str(_dt_r.date.today())
        if _mi_date:
            # ⚠️ 同上方全域表:_mi_date 目前是抓取時間(cl_ts)而非資料月 as_of,
            #    屬 §2.2 provenance 另案(G2 記錄,未修)。
            rows.append(_row('M1B / M2 貨幣供給', _mi_date, 'monthly',
                             source='CBC + FinMind 雙源',
                             endpoint='cbc.gov.tw / TaiwanStockMonetaryAggregates',
                             proxy=True, indicator='m1b_m2'))
        else:
            # m1b_m2_info 尚未抓取 → 黃燈提示，與上方 5 個 macro 一致
            _m1b_never = not _mi
            rows.append({'資料名稱': 'M1B / M2 貨幣供給',
                         '頻率': _FREQ_LBL.get('monthly', 'monthly'),
                         '來源': 'CBC + FinMind 雙源',
                         '端點': 'cbc.gov.tw / TaiwanStockMonetaryAggregates',
                         'Proxy': '✅',
                         '最後更新': ('🟡 待補抓（系統下次背景輪詢自動處理）'
                                      if _m1b_never else '❌ 抓取失敗'),
                         '日期': '—',
                         '狀態': '🟡' if _m1b_never else '🔴'})
        _all_section_rows.extend(rows)
        _tbl(rows)
        st.caption('⚠️ M1B-M2 利差、年增率為計算值，不顯示於此。'
                   ' Proxy=✅ 表示經 Squid Proxy 出口（地理 IP 限制需求）。')

    # ════ 2. 大盤指數 & 籌碼 Raw ═════════════════════════════════
    with st.expander('📊 大盤指數 & 籌碼 Raw Data', expanded=False):
        _cl = st.session_state.get('cl_data') or {}
        _cl_ts = str(st.session_state.get('cl_ts', ''))[:10] or None
        rows = []
        for gkey, glabel, _ep_g in [
            ('intl',  '國際指數 OHLCV',    'SPY/QQQ/MSCI/^GSPC'),
            ('tw',    '台股指數 OHLCV',    '^TWII/^TWOII'),
            ('tech',  '科技股指數 OHLCV',  'SOXX/SMH'),
        ]:
            grp = _cl.get(gkey) or {}
            dates = [_last_date(df) for df in grp.values()
                     if isinstance(df, _pd_r.DataFrame)] if isinstance(grp, dict) else []
            dates = [d for d in dates if d]
            rows.append(_row(glabel, max(dates) if dates else _cl_ts, 'daily',
                             source='yfinance', endpoint=_ep_g, proxy=False))

        # 美債10Y殖利率、DXY美元指數 — 從 intl group 讀取個別 key
        _intl_grp = _cl.get('intl') or {}
        for _ik, _ilabel, _ep_y in [
            ('10Y公債殖利率', '美債 10Y 殖利率', '^TNX'),
            ('美元指數 DXY',  '美元指數 DXY',    'DX-Y.NYB'),
        ]:
            _idf = _intl_grp.get(_ik)
            rows.append(_row(_ilabel,
                             _last_date(_idf) if isinstance(_idf, _pd_r.DataFrame) else _cl_ts,
                             'daily', source='yfinance', endpoint=_ep_y, proxy=False))

        for key, label, _src, _ep, _px in [
            ('inst',   '三大法人現貨買賣超',
             'TWSE BFI82U',
             'twse.com.tw/rwd/zh/fund/BFI82U', True),
            ('margin', '融資餘額',
             'FinMind+TWSE+HiStock+Goodinfo+Yahoo+鉅亨 6段備援',
             'TaiwanStockTotalMarginPurchaseShortSale → MI_MARGN → 4 大網爬', True),
        ]:
            val = _cl.get(key)
            if isinstance(val, _pd_r.DataFrame):
                date = _last_date(val) or _cl_ts
            elif val is not None:
                date = _cl_ts
            else:
                date = None
            rows.append(_row(label, date, 'daily',
                             source=_src, endpoint=_ep, proxy=_px))

        _adl = _cl.get('adl')
        rows.append(_row(
            'ADL 漲跌家數',
            _last_date(_adl) if isinstance(_adl, _pd_r.DataFrame) else _cl_ts,
            'daily',
            source='yfinance + TWSE',
            endpoint='^TWII 估算 + MI_INDEX 精確',
            proxy=True))
        _all_section_rows.extend(rows)
        _tbl(rows)
        st.caption('⚠️ ADL 累計值、年線乖離率為計算值，不顯示於此。')

    # ════ 3. 先行指標 Raw ════════════════════════════════════════
    with st.expander('📈 先行指標 Raw Data', expanded=False):
        _li = st.session_state.get('li_latest')
        _li_date = _last_date(_li) if isinstance(_li, _pd_r.DataFrame) else None
        _pcr_date = _last_date_col(_li, '選PCR') if isinstance(_li, _pd_r.DataFrame) else None
        rows = [
            _row('外資期貨留倉', _li_date, 'daily',
                 source='FinMind', endpoint='TaiwanFuturesInstitutionalInvestors TX+MTX',
                 proxy=False),
            _row('外資期貨淨口（多−空×0.25 合約）', _li_date, 'daily',
                 source='TAIFEX', endpoint='OpenData/Future/MarketDataDaily', proxy=True),
            _row('選擇權法人部位', _li_date, 'daily',
                 source='FinMind', endpoint='TaiwanOptionInstitutionalInvestors TXO',
                 proxy=False),
            _row('三大法人現貨', _li_date, 'daily',
                 source='FinMind', endpoint='TaiwanStockTotalInstitutionalInvestors',
                 proxy=False),
            _row('PCR 選擇權 Put/Call 比值', _pcr_date or _li_date, 'daily',
                 source='TAIFEX', endpoint='pcRatio.aspx', proxy=True),
        ]
        _all_section_rows.extend(rows)
        _tbl(rows)
        st.caption('⚠️ 外資期貨淨額、PCR 為計算後欄位，如無獨立抓取日期則沿用先行指標最後日期。')

    # ════ 4. 個股 Raw ════════════════════════════════════════════
    with st.expander('🔬 個股 Raw Data', expanded=False):
        _t2 = st.session_state.get('t2_data') or {}
        if not _t2:
            st.info('尚未載入個股。前往「🔬 個股」Tab 輸入代碼並點擊「載入完整分析」')
        else:
            sid2 = _t2.get('sid', '')
            name2 = _t2.get('name', sid2)
            st.markdown(f'**當前個股：{name2}（{sid2}）**')
            rows = []
            rows.append(_row('K線 OHLCV', _last_date(_t2.get('df')), 'daily',
                             source='FinMind / yfinance',
                             endpoint='TaiwanStockPrice / Ticker.history', proxy=False))
            rows.append(_row('月營收', _last_date(_t2.get('rev')), 'monthly',
                             source='FinMind', endpoint='TaiwanStockMonthRevenue',
                             proxy=False, indicator='tw_monthly_revenue'))
            # qtr 拆成個別欄位
            _qtr2 = _t2.get('qtr')
            rows.append(_row('季營收', _last_date_col(_qtr2, '營收'), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockFinancialStatement',
                             proxy=False))
            rows.append(_row('EPS 每股盈餘', _last_date_col(_qtr2, 'EPS'), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockFinancialStatement',
                             proxy=False))
            rows.append(_row('毛利率', _last_date_col(_qtr2, '毛利率'), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockFinancialStatement',
                             proxy=False))
            # qtr_extra 拆成個別欄位（移除重複的合約負債 TaiwanStockBalanceSheet 行）
            _qte = _t2.get('qtr_extra')
            rows.append(_row('存貨', _last_date_col(_qte, '存貨'), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockBalanceSheet',
                             proxy=False))
            # 合約負債：三態探測（fail/na/zero/ok）— 不再硬標 🔴
            _cl_st, _cl_dt = _probe_col(_qte, '合約負債')
            rows.append(_row('合約負債',
                             _cl_dt if _cl_st == 'ok' else None, 'quarterly',
                             optional=True,
                             probe_status=None if _cl_st == 'ok' else _cl_st,
                             source='FinMind + MOPS 雙源',
                             endpoint='TaiwanStockBalanceSheet → ajax_t164sb03',
                             proxy=True))
            rows.append(_row('CapEx 資本支出', _last_date_col(_qte, '資本支出'), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockCashFlowsStatement',
                             proxy=False))
            # 股利
            _yr = _t2.get('yearly') or []
            _yr_date = None
            if _yr:
                _yr_raw = str(_yr[-1].get('year', ''))[:4]
                _yr_date = f'{_yr_raw}-12-31' if _yr_raw.isdigit() else None
            rows.append(_row('股利歷史', _yr_date, 'yearly',
                             source='FinMind', endpoint='TaiwanStockDividend',
                             proxy=False))
            # 財報體檢原始財報
            _fh2 = st.session_state.get(f'_fh_{sid2}')
            _fh2_date = (str(_dt_r.date.today())
                         if _fh2 and not _fh2.get('error') else None)
            rows.append(_row('財報體檢原始 BS+CF+IS', _fh2_date, 'quarterly',
                             source='FinMind 3 datasets',
                             endpoint='BalanceSheet+CashFlows+IncomeStatement',
                             proxy=False))
            # ── 財報體檢科目連動診斷（與「🏥 體檢表」N/A 項目 1:1 對應）──
            #   此處只回答「該科目本季原料是否抓到」，不顯示計算值或現況數字。
            _fin_raw2 = st.session_state.get(f'_fin_raw_{sid2}') or {}
            if _fh2_date and _fin_raw2:
                _b5_2 = _fin_raw2.get('b_item_5y') or {}
                _is_finance = _fin_raw2.get('is_finance', False)

                def _add_field(name, key, fh_indicator, optional=False,
                               source='FinMind', endpoint='', proxy=False,
                               module='', aliases=None, slot='_bs_slot_latest'):
                    """檢查單一財報原料欄位。三態探測（針對 optional=True）：
                      🟢 已抓到（value > 0）
                      🔵 該股本期為 0（raw slot 有 alias 但值 = 0）
                      ⚪ 此股無此科目（raw slot 完全沒此 alias）
                      🔴 fetch 失敗（_fin_raw2 整體錯誤或 raw slot 缺）
                    aliases: FinMind 該欄位的所有別名 list（傳入避免硬編維護成本）
                    slot: '_bs_slot_latest' / '_cf_slot_latest' / '_is_slot_latest'
                    """
                    _meta = {
                        '體檢模組': module,
                        '資料名稱': f'{name}',
                        '適用體檢指標': fh_indicator,
                        '頻率': '季頻',
                        '來源': source,
                        '端點': endpoint or '—',
                        'Proxy': '✅' if proxy else '—',
                        '日期': '—',
                    }
                    if optional and aliases:
                        # 三態探測：分辨「真失敗 / 此股無此科目 / 該股本季為 0」
                        _st_p, _val_p = _probe_fin_field(_fin_raw2, key, aliases, slot=slot)
                        if _st_p == 'ok':
                            rows.append({**_meta, '最後更新': f'已抓取（{_val_p:,.0f}千）',
                                         '狀態': '🟢'})
                        elif _st_p == 'na':
                            rows.append({**_meta, '最後更新': '⚪ 此股無此科目',
                                         '狀態': '⚪'})
                        elif _st_p == 'zero':
                            rows.append({**_meta, '最後更新': '🔵 該股本期為 0',
                                         '狀態': '🔵'})
                        else:
                            rows.append({**_meta, '最後更新': '🔴 抓取失敗',
                                         '狀態': '🔴'})
                        return
                    # ── 必要欄位 / 未提供 aliases：值=0 即視為失敗 ─────────────
                    _v = float(_fin_raw2.get(key) or 0)
                    if _v > 0:
                        rows.append({**_meta, '最後更新': '已抓取', '狀態': '🟢'})
                    elif optional:
                        # 沒給 aliases 的 optional 欄位 — 退回 ⚪ 而非紅燈，避免誤判
                        rows.append({**_meta, '最後更新': '⚪ 此股本期無值',
                                     '狀態': '⚪'})
                    else:
                        rows.append({**_meta, '最後更新': '❌ 缺失', '狀態': '🔴'})

                _BS_EP = 'TaiwanStockBalanceSheet'
                _CF_EP = 'TaiwanStockCashFlowsStatement'
                _IS_EP = 'TaiwanStockFinancialStatement'

                # ━━━ 一、現金流量（氣長不長）━━━━━━━━━━━━━━━━━━━━━━
                _M1 = '一、現金流量(氣長)'
                _add_field('現金及約當現金（千）', '現金及約當現金(千)',
                           '現金與約當現金比率', module=_M1, endpoint=_BS_EP)
                _add_field('資產總計 / 總資產（千）', '總資產(千)',
                           '現金與約當現金比率 + 總資產週轉率 + 負債比率',
                           module=_M1, endpoint=_BS_EP)
                _add_field('OCF 營業活動之淨現金流入（千）', 'OCF(千)',
                           '現金流量比率(>100) + 現金流量允當比率(>100) + 現金再投資比率(>10)',
                           module=_M1, endpoint=_CF_EP)
                _add_field('資本支出 取得不動產廠房設備（千）', '資本支出(千)',
                           '現金流量允當比率（5年加總） + 現金再投資比率',
                           module=_M1, endpoint=_CF_EP)
                _add_field('發放現金股利（千）', '現金股利(千)',
                           '現金流量允當比率（5年加總） + 現金再投資比率',
                           module=_M1, endpoint=_CF_EP, optional=True,
                           aliases=['CashDividendsPaid', '發放現金股利',
                                    '現金股利', '支付之現金股利',
                                    '本期支付之股利'],
                           slot='_cf_slot_latest')
                _add_field('固定資產毛額（千）', '固定資產(千)',
                           '現金再投資比率（分母）',
                           module=_M1, endpoint=_BS_EP)
                _add_field('長期投資（千）', '長期投資(千)',
                           '現金再投資比率（分母）',
                           module=_M1, endpoint=_BS_EP, optional=True,
                           aliases=['LongTermInvestments', '長期投資',
                                    '採權益法之投資',
                                    '採用權益法之投資'])
                _add_field('其他非流動資產（千）', '其他非流動資產(千)',
                           '現金再投資比率（分母）',
                           module=_M1, endpoint=_BS_EP, optional=True,
                           aliases=['OtherNoncurrentAssets', '其他非流動資產',
                                    '其他非流動資產合計'])

                # ━━━ 二、獲利能力（好生意）━━━━━━━━━━━━━━━━━━━━━━━━
                _M2 = '二、獲利能力(好生意)'
                _add_field('營業收入合計（千）', '營業收入(千)',
                           '毛利率 + 營業利益率 + 淨利率 + ROA + 總資產週轉率 + DSO + 安全邊際',
                           module=_M2, endpoint=_IS_EP)
                _add_field('營業毛利（千）', '毛利(千)',
                           '毛利率 = 毛利 / 營業收入',
                           module=_M2, endpoint=_IS_EP)
                _add_field('營業利益（損失）（千）', '營業利益(千)',
                           '營業利益率 = 營業利益 / 營業收入',
                           module=_M2, endpoint=_IS_EP)
                _add_field('本期淨利（淨損）／稅後淨利（千）', '稅後淨利(千)',
                           '淨利率 + ROE（分子）',
                           module=_M2, endpoint=_IS_EP)
                _add_field('權益總計／股東權益（千）', '股東權益(千)',
                           'ROE = 淨利 / 股東權益（分母）',
                           module=_M2, endpoint=_BS_EP)
                _add_field('基本每股盈餘 EPS（元）', 'EPS',
                           '每股盈餘 EPS（直接抓取）',
                           module=_M2, endpoint=_IS_EP)

                # ━━━ 三、經營能力（翻桌率）━━━━━━━━━━━━━━━━━━━━━━━━
                _M3 = '三、經營能力(翻桌率)'
                _add_field('應收帳款（含關係人+票據，千）', '應收帳款(千)',
                           'DSO 應收帳款收現天數 + CCC',
                           module=_M3, endpoint=_BS_EP, optional=True,
                           aliases=['AccountsReceivable', '應收帳款淨額',
                                    '應收帳款', '應收帳款及票據', '應收票據及帳款',
                                    '應收帳款及合約資產', '應收款項', '貿易應收款'])
                _add_field('應收帳款收現天數（DSO，計算值）', '應收帳款天數',
                           'DSO = 應收 / 營收 × 360（衍生）',
                           module=_M3, endpoint=_BS_EP, optional=True)  # 計算值無 raw alias
                _add_field('存貨（千）', '存貨(千)',
                           'DIO 存貨週轉天數 + 速動比率（扣除項）',
                           module=_M3, endpoint=_BS_EP, optional=_is_finance,
                           aliases=['Inventories', '存貨', '存貨淨額'])
                _add_field('營業成本合計（千）', '營業成本(千)',
                           'DIO = 存貨 / 營業成本 × 360（分母）',
                           module=_M3, endpoint=_IS_EP)
                _add_field('應付帳款（千）', '應付帳款天數',
                           'DPO 應付帳款付款天數 + CCC',
                           module=_M3, endpoint=_BS_EP)

                # ━━━ 四、償債能力（還債）━━━━━━━━━━━━━━━━━━━━━━━━━━
                _M4 = '四、償債能力(還債)'
                _add_field('流動資產合計（千）', '流動資產(千)',
                           '流動比率 + 速動比率（分子）',
                           module=_M4, endpoint=_BS_EP)
                _add_field('流動負債合計（千）', '流動負債(千)',
                           '流動比率 + 速動比率 + 現金流量比率（分母）',
                           module=_M4, endpoint=_BS_EP)
                _add_field('預付款項（千）', '預付款項(千)',
                           '速動比率（扣除項）',
                           module=_M4, endpoint=_BS_EP, optional=True,
                           aliases=['Prepayments', '預付款項', '預付費用',
                                    '預付貨款', '預付投資款', '其他預付款項'])

                # ━━━ 五、財務結構（那根棒子）━━━━━━━━━━━━━━━━━━━━━━
                _M5 = '五、財務結構(那根棒子)'
                _add_field('負債總計（千）', '總負債(千)',
                           '負債佔資產比率 = 負債 / 資產',
                           module=_M5, endpoint=_BS_EP, optional=_is_finance,
                           aliases=['TotalLiabilities', '負債總計', '負債合計',
                                    '負債總額'])

                # ━━━ 5 年加總（允當比率 B 項）━━━━━━━━━━━━━━━━━━━━━━
                _b5_ok = _b5_2.get('status') == 'ok'
                rows.append({
                    '體檢模組':   _M1,
                    '資料名稱':  '5 年現金流加總（OCF + Capex + 存貨增加 + 現金股利）',
                    '適用體檢指標': '現金流量允當比率（5 年版）',
                    '頻率':     '年頻',
                    '來源':     'FinMind',
                    '端點':     'TaiwanStockCashFlowsStatement (5y)',
                    'Proxy':    '—',
                    '日期':     '—',
                    '最後更新': '已抓取' if _b5_ok else f'❌ 缺失（{_b5_2.get("label","未取得")}）',
                    '狀態':     '🟢' if _b5_ok else '🔴',
                })
            _all_section_rows.extend(rows)
            _tbl(rows)
            st.caption(
                '🩺 **本表僅回答「該欄位本季是否抓到」**，不顯示數值或現況；'
                '若體檢表出現 N/A，請對照本表紅燈科目。\n\n'
                '📚 **體檢五大模組對照**：一、現金流量（氣長）｜二、獲利能力（好生意）｜'
                '三、經營能力（翻桌率）｜四、償債能力（還債）｜五、財務結構（那根棒子）。')

        # ────────── 個股組合：逐檔批次分析診斷 ─────────────────
        _t3 = st.session_state.get('t3_data') or {}
        _t3_results = _t3.get('results') or []
        if _t3_results:
            st.markdown('---')
            st.markdown(f'**📊 多檔個股比較逐檔診斷（{len(_t3_results)} 檔）**')
            _grp_diag_rows = []
            _today_grp = str(_dt_r.date.today())
            for _gr in _t3_results:
                _sid = _gr.get('stock_id') or _gr.get('代碼') or '?'
                _nm  = _gr.get('名稱', _sid)
                _err = _gr.get('_fetch_err')
                # K線 OHLCV
                _grp_diag_rows.append(_row(
                    f'{_sid} {_nm} K線',
                    _gr.get('_price_date'), 'daily',
                    error_msg=_err or None,
                    source='FinMind / yfinance',
                    endpoint='TaiwanStockPrice / Ticker.history',
                    proxy=False))
                # 合約負債（三態）
                _grp_diag_rows.append(_row(
                    f'{_sid} 合約負債',
                    _today_grp if _gr.get('_cl_ok') else None, 'quarterly',
                    optional=True,
                    probe_status=None if _gr.get('_cl_ok') else 'na',
                    source='FinMind + MOPS 雙源',
                    endpoint='TaiwanStockBalanceSheet → ajax_t164sb03',
                    proxy=True))
                # 資本支出（三態）
                _grp_diag_rows.append(_row(
                    f'{_sid} 資本支出 / 固定資產',
                    _today_grp if _gr.get('_cx_ok') else None, 'quarterly',
                    optional=True,
                    probe_status=None if _gr.get('_cx_ok') else 'na',
                    source='FinMind',
                    endpoint='TaiwanStockCashFlowsStatement',
                    proxy=False))
                # 股利（三態）
                _grp_diag_rows.append(_row(
                    f'{_sid} 股利歷史',
                    _today_grp if _gr.get('_has_div') else None, 'yearly',
                    optional=True,
                    probe_status=None if _gr.get('_has_div') else 'zero',
                    source='FinMind',
                    endpoint='TaiwanStockDividend',
                    proxy=False))
            _all_section_rows.extend(_grp_diag_rows)
            _tbl(_grp_diag_rows)
            st.caption(
                '💡 批次分析涵蓋 K線+合約負債+資本支出+股利 4 大維度（不含體檢五大模組 N/A 對照）。'
                '若需單檔深度診斷請至「🔬 個股」Tab 載入完整分析。')

    # ════ 5. ETF Raw ═════════════════════════════════════════════
    with st.expander('🏦 ETF Raw Data', expanded=False):
        _e1 = st.session_state.get('etf_single_data') or {}
        if not _e1.get('ticker'):
            st.info('尚未載入 ETF。前往「🏦 ETF」Tab 輸入代號並診斷。')
        else:
            tk = _e1.get('ticker', '')
            nm = _e1.get('name', tk)
            st.markdown(f'**當前 ETF：{nm}（{tk}）**')
            rows = []
            _pdf = _e1.get('price_df')
            rows.append(_row(f'ETF K線 OHLCV {tk}', _last_date(_pdf), 'daily',
                             source='yfinance', endpoint=f'Ticker({tk}).history(auto_adjust=True)',
                             proxy=False))
            # AUM / Beta / 費用率：拆成個別行各自檢查
            _is_oversea_etf = bool(_e1.get('_is_overseas'))
            _is_private_etf = bool(_e1.get('_likely_private'))
            _is_active_etf_main = bool(_e1.get('_is_active_etf'))
            _oversea_msg = '海外 ETF 不適用（本系統 5 源僅限台灣 ETF）'
            _private_msg = '私募/特殊 ETF — AUM、費用率、NAV 主流資料源皆未揭露'
            _active_msg  = '主動式 ETF — 公開資料受限（投信官網有揭露但格式不一致，本系統暫無法穩定抓取）'
            # v1.1：主動式 ETF 失敗併入 na（黃燈），不再算入紅燈
            _restricted = _is_private_etf or _is_active_etf_main
            _aum_na = _restricted and not _e1.get('aum')
            rows.append(_row('ETF 規模 AUM',
                             str(_dt_r.date.today()) if _e1.get('aum') else None, 'daily',
                             error_msg=((_active_msg if _is_active_etf_main else _private_msg)
                                        if _aum_na else None),
                             probe_status=('na' if _aum_na else None),
                             source='yfinance', endpoint='.info[totalAssets]', proxy=False))
            rows.append(_row('ETF Beta',
                             str(_dt_r.date.today()) if _e1.get('beta') is not None else None,
                             'daily',
                             source='yfinance', endpoint='.info[beta]', proxy=False))
            _exp_na = (_is_oversea_etf or _restricted) and not _e1.get('expense')
            rows.append(_row('ETF 費用率',
                             str(_dt_r.date.today()) if _e1.get('expense') else None, 'daily',
                             optional=False,
                             error_msg=(_oversea_msg if _is_oversea_etf
                                        else _active_msg if _is_active_etf_main
                                        else _private_msg if _is_private_etf
                                        else _e1.get('_err_expense')),
                             probe_status=('na' if _exp_na else None),
                             source='SITCA + MoneyDJ + Yuanta + yfinance 4 源',
                             endpoint='sitca.org.tw / moneydj Basic0004 / yuantaetfs / .info',
                             proxy=True))
            # NAV 淨值
            _prem = _e1.get('premium') or {}
            _nav_ok = _prem.get('nav') is not None
            _nav_na = (_is_oversea_etf or _restricted) and not _nav_ok
            rows.append(_row('NAV 淨值',
                             str(_dt_r.date.today()) if _nav_ok else None, 'daily',
                             error_msg=(_oversea_msg if _is_oversea_etf
                                        else _active_msg if _is_active_etf_main
                                        else _private_msg if _is_private_etf
                                        else _e1.get('_err_nav')),
                             probe_status=('na' if _nav_na else None),
                             source='FinMind / TWSE OpenAPI',
                             endpoint='TaiwanETFNetAssetValue / opendata',
                             proxy=True))
            # 基金經理人（ETF 表現與經理人相關，換手須提醒）
            try:
                from src.data.etf import fetch_etf_manager as _fem_r
                _mgr_r = _fem_r(tk)
            except Exception:
                _mgr_r = None
            _mgr_name = (_mgr_r or {}).get('name')
            # S-H3 v18.244:讀 module-level accessor(原 st.session_state)
            _mgr_last_err = None
            if not _mgr_name:
                try:
                    from src.data.etf.etf_fetch import get_etf_manager_last_err as _get_mgr_err
                    _mgr_last_err = _get_mgr_err().get(tk.replace('.tw', '.TW'))
                except Exception:
                    pass
            rows.append(_row('基金經理人',
                             str(_dt_r.date.today()) if _mgr_name else None, 'static',
                             optional=True,
                             error_msg=_mgr_last_err,
                             source='MoneyDJ / SITCA / Yuanta',
                             endpoint='Basic0004/0001/0006/0011 → SITCA → 官網',
                             proxy=True))
            _all_section_rows.extend(rows)
            _tbl(rows)
            st.caption('⚠️ 殖利率、追蹤誤差、CAGR、Sharpe、折溢價率為計算值，不顯示於此。')

        # ────────── ETF 組合：逐檔個別診斷 ──────────────────────
        _ep = st.session_state.get('etf_portfolio_data') or {}
        _ep_rows = _ep.get('rows') or []
        if _ep_rows:
            st.markdown('---')
            st.markdown(f'**🗂️ ETF 組合逐檔診斷（{len(_ep_rows)} 檔）**')
            _today_ep = str(_dt_r.date.today())
            _port_diag_rows = []
            for _pr in _ep_rows:
                _tk_p = _pr.get('ticker', '')
                if not _tk_p:
                    continue
                _cp  = _pr.get('current_price') or 0
                _shr = _pr.get('shares') or 0
                _dvr = _pr.get('dividend_received') or 0
                _is_tw = _tk_p.endswith('.TW') or _tk_p.endswith('.TWO')
                # 現價（K線）
                _port_diag_rows.append(_row(
                    f'{_tk_p} 現價 / K線',
                    _today_ep if _cp > 0 else None, 'daily',
                    error_msg=None if _cp > 0 else 'yfinance 抓不到收盤價（代號錯誤或下市）',
                    source='yfinance',
                    endpoint=f'Ticker({_tk_p}).history(5d)',
                    proxy=False))
                # 配息
                _div_st = None
                _div_err = None
                if _dvr > 0:
                    _div_st = None  # green
                elif _is_tw and _shr > 0:
                    _div_st = 'zero'  # 台股 ETF 但近 1 年無配息（成長型 / 新上市 / yfinance 缺）
                else:
                    _div_st = 'na'  # 海外或無股數
                    _div_err = '海外 ETF 不適用本系統配息計算' if not _is_tw else None
                _port_diag_rows.append(_row(
                    f'{_tk_p} 配息（近1年）',
                    _today_ep if _dvr > 0 else None, 'yearly',
                    optional=True,
                    probe_status=_div_st,
                    error_msg=_div_err,
                    source='yfinance',
                    endpoint=f'Ticker({_tk_p}).dividends',
                    proxy=False))
            _all_section_rows.extend(_port_diag_rows)
            _tbl(_port_diag_rows)
            st.caption('💡 配息「🔵 該股本期為 0」可能為成長型 ETF（不配息）或新上市未滿 1 年；「⚪ 不適用」為海外 ETF。')

            # ────── 主動 ETF 經理人 / 持股探測 ──────
            try:
                from src.data.etf import is_active_etf, fetch_etf_manager, fetch_etf_holdings
            except ImportError:
                is_active_etf = fetch_etf_manager = fetch_etf_holdings = None

            if is_active_etf is not None and fetch_etf_manager is not None:
                st.markdown('---')
                _h1, _h2, _h3 = st.columns([4, 1, 1])
                _h1.markdown('**🏃 主動 ETF 經理人 / 持股 MoneyDJ 探測**')
                if _h2.button('🗑️ 清快取重試', key='_etf_mgr_clear',
                               use_container_width=True,
                               help='清掉 fetch_etf_manager + fetch_etf_holdings 的 None 快取，重新走 proxy 抓'):
                    try:
                        fetch_etf_manager.clear()
                    except Exception:
                        pass
                    try:
                        fetch_etf_holdings.clear()
                    except Exception:
                        pass
                    st.rerun()
                _do_deep = _h3.button('🔬 深度診斷', key='_etf_mgr_deep',
                                       use_container_width=True,
                                       help='挑首檔主動式 ETF，直接打 MoneyDJ 不走快取，逐源顯示 HTTP status / regex match')
                st.caption('診斷「弱勢度檢測」表格「經理人」「任期」全空的根因：'
                           'MoneyDJ 反爬擋海外 IP，需走 proxy_helper（NAS Squid 台灣 IP）。'
                           '若清完仍 ❌ 但 proxy 連線狀態🟢 → 按「🔬 深度診斷」看 MoneyDJ 是否擋 NAS IP / regex 漏抓。')

                # ────── 🔬 深度診斷：不走快取 raw probe ──────
                if _do_deep:
                    _active_tks = [_pr.get('ticker', '') for _pr in _ep_rows
                                   if is_active_etf(_pr.get('ticker', ''))]
                    if not _active_tks:
                        st.warning('組合內無主動式 ETF（被動式不需查經理人）')
                    else:
                        _tk_probe = _active_tks[0]
                        _url_probe = (
                            'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm'
                            f'?etfid={_tk_probe}')
                        st.markdown(f'**🎯 探測對象：`{_tk_probe}`** → `{_url_probe}`')
                        # 源 1：proxy_helper.fetch_url
                        try:
                            from src.data.proxy import fetch_url as _fu_d
                            _r_p = _fu_d(_url_probe, timeout=12, attempts=2)
                            if _r_p is None:
                                st.error('❌ **proxy_helper.fetch_url** 回 None（proxy 全失敗或 403×2 後降級也失敗）')
                            else:
                                _len_p = len(_r_p.text) if _r_p.text else 0
                                _msg = f'**proxy_helper.fetch_url** → HTTP `{_r_p.status_code}` · 長度 `{_len_p}` chars'
                                if _r_p.status_code == 200 and _len_p > 1000:
                                    st.success(f'✅ {_msg}')
                                    _r_p.encoding = 'utf-8'
                                    import re as _re_d
                                    _txt = _r_p.text
                                    _nm_m = _re_d.search(r'經理人[^<>\d]{0,30}?>?\s*([一-鿿]{2,8})\s*<', _txt)
                                    _dt_m = _re_d.search(
                                        r'(?:到職日|上任日|任期|管理基金日)[^\d]{0,30}?(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',
                                        _txt)
                                    if _nm_m:
                                        st.success(f'✅ regex 經理人：`{_nm_m.group(1)}`')
                                    else:
                                        st.warning('⚠️ regex 沒抓到「經理人」欄位 — MoneyDJ HTML 結構可能改版')
                                    if _dt_m:
                                        st.success(f'✅ regex 到職日：`{_dt_m.group(1)}-{_dt_m.group(2)}-{_dt_m.group(3)}`')
                                    else:
                                        st.info('ℹ️ regex 沒抓到「到職日 / 上任日」（只有經理人沒任期也算部分成功）')
                                    # 預覽含「經理人」字眼附近 200 字
                                    _pos = _txt.find('經理人')
                                    if _pos >= 0:
                                        st.code(_txt[max(0, _pos - 50):_pos + 250], language='html')
                                    else:
                                        st.warning('⚠️ 整篇文章連「經理人」這三字都沒有 — 可能是錯誤頁面 / 反爬干擾頁')
                                else:
                                    st.error(f'❌ {_msg} — MoneyDJ 擋了 NAS IP 或回了空頁')
                        except Exception as _ep_d:
                            st.error(f'❌ proxy_helper 例外：{type(_ep_d).__name__}: {_ep_d}')
                        # 源 2：curl_cffi 直連
                        try:
                            from curl_cffi import requests as _cffi_d
                            _r_c = _cffi_d.get(_url_probe, impersonate='chrome124', timeout=12)
                            _len_c = len(_r_c.text) if _r_c.text else 0
                            _msg = f'**curl_cffi 直連** → HTTP `{_r_c.status_code}` · 長度 `{_len_c}` chars'
                            if _r_c.status_code == 200 and _len_c > 1000:
                                st.success(f'✅ {_msg}（fallback 可用）')
                            else:
                                st.warning(f'⚠️ {_msg}（fallback 也失敗，預期 — 海外 IP 被擋）')
                        except Exception as _ec_d:
                            st.warning(f'⚠️ curl_cffi 例外：{type(_ec_d).__name__}: {_ec_d}')

                _probe_rows = []
                _tk_seen: set[str] = set()
                for _pr in _ep_rows:
                    _tk_p = _pr.get('ticker', '')
                    if not _tk_p or _tk_p in _tk_seen:
                        continue
                    _tk_seen.add(_tk_p)
                    _active = is_active_etf(_tk_p)
                    # 經理人探測
                    if not _active:
                        _probe_rows.append(_row(
                            f'{_tk_p} 經理人', None, 'static',
                            optional=True, probe_status='na',
                            source='MoneyDJ', endpoint='Basic0001.xdjhtm',
                            proxy=True))
                    else:
                        try:
                            _mgr = fetch_etf_manager(_tk_p)
                        except Exception as _emgr:
                            _mgr = None
                            print(f'[diag/manager] {_tk_p}: {type(_emgr).__name__}: {_emgr}')
                        if _mgr and _mgr.get('name'):
                            _nm_mgr = _mgr['name']
                            _tn = _mgr.get('tenure_days')
                            _label = f'{_nm_mgr}' + (f'（任期 {_tn} 天）' if _tn else '（任期未抓到）')
                            _probe_rows.append(_row(
                                f'{_tk_p} 經理人 = {_label}',
                                _mgr.get('since') or _today_ep, 'static',
                                source='MoneyDJ', endpoint='Basic0001.xdjhtm',
                                proxy=True))
                        else:
                            # S-H3 v18.244:讀 module-level accessor(原 st.session_state)
                            try:
                                from src.data.etf.etf_fetch import get_etf_manager_last_err as _gele
                                _last_err = _gele().get(_tk_p)
                            except Exception:
                                _last_err = None
                            # v1.1：主動式 ETF Yuanta 也失敗 → 黃燈 na（公開資料受限）
                            _err_str = (
                                '主動式 ETF — 公開資料受限'
                                f'（trace: {_last_err}）' if _last_err
                                else '主動式 ETF — 公開資料受限'
                            )
                            _probe_rows.append(_row(
                                f'{_tk_p} 經理人',
                                None, 'static',
                                probe_status='na',
                                error_msg=_err_str,
                                source='MoneyDJ + SITCA + Yuanta',
                                endpoint='Basic0001/0006/0011 + SITCA IN24XX + yuantaetfs',
                                proxy=True))
                    # 持股探測（簡版：有 / 無）
                    try:
                        _hd = fetch_etf_holdings(_tk_p) if fetch_etf_holdings else None
                    except Exception as _ehd:
                        _hd = None
                        print(f'[diag/holdings] {_tk_p}: {type(_ehd).__name__}: {_ehd}')
                    if _hd:
                        # G2:本列餵的 `_today_ep` 是**本次探測時間**,不是持股表的
                        # 資料月 as_of(fetch_etf_holdings 不回資料日期)。原本標
                        # 'monthly' 等於拿抓取時間冒充月頻 as_of —— 任何月頻規則
                        # 量它都恆綠,是 D-2 那類「量抓取時間」的病灶。改標
                        # FREQ_STATIC:語意就是「探測到 / 沒探測到」兩態,燈號不變(🟢),
                        # 但不再假裝這是一個資料日期判定。
                        _probe_rows.append(_row(
                            f'{_tk_p} 持股 = {len(_hd)} 檔',
                            _today_ep, FREQ_STATIC,
                            source='yfinance/MoneyDJ',
                            endpoint='funds_data → Basic0007/0008/RankA0001',
                            proxy=True))
                    else:
                        _probe_rows.append(_row(
                            f'{_tk_p} 持股',
                            None, FREQ_STATIC, optional=True,
                            error_msg='三條備援 URL 全失敗（403 / 端點變動）',
                            source='yfinance/MoneyDJ',
                            endpoint='funds_data → Basic0007/0008/RankA0001',
                            proxy=True))
                _all_section_rows.extend(_probe_rows)
                _tbl(_probe_rows)
                st.caption('💡 經理人「⚪ 不適用」= 被動式 ETF 無需查；「❌ 抓取失敗」= 主動式但 proxy/regex 異常。')

    # ══════════════════════════════════════════════════════════════
    # ⚠️ 資料異常清單（最下方一覽，獨立於上方總表/抽查）
    # ══════════════════════════════════════════════════════════════
    st.markdown('---')
    st.markdown('#### ⚠️ 資料異常清單')
    # 合併「全域聚合 rows」+「5 個 expander 的 detail rows」(個股+ETF granular missing)
    # detail rows schema 用『日期/狀態』，全域用『最新日期/新鮮度』；統一 normalize
    def _norm_anom(_r):
        _ic = (_r.get('新鮮度') or _r.get('狀態') or '')[:1]
        return {
            '資料名稱': _r.get('資料名稱', '—'),
            '來源':     _r.get('來源', '—') or '—',
            '頻率':     _r.get('頻率', '—'),
            '最新日期': _r.get('最新日期') or _r.get('日期', '—') or '—',
            '新鮮度':   _r.get('新鮮度') or _r.get('最後更新') or _ic,
            '_icon':    _ic,
        }
    _anom_combined = (
        [_norm_anom(r) for r in _global_rows]
        + [_norm_anom(r) for r in _all_section_rows]
    )
    # 依資料名稱去重（保留第一筆）
    _seen_anom: set = set()
    _anom_dedup = []
    for _r in _anom_combined:
        _k = _r.get('資料名稱', '')
        if _k and _k not in _seen_anom:
            _seen_anom.add(_k)
            _anom_dedup.append(_r)
    _anom_rows = [r for r in _anom_dedup if r['_icon'] in ('🔴', '🟡')]
    # 排序：🔴 在前，🟡 在後；組內依資料名稱字母序
    _anom_rows.sort(key=lambda r: (
        0 if r['_icon'] == '🔴' else 1,
        r.get('資料名稱', ''),
    ))
    if not _anom_rows:
        st.success('✅ 全數資料源狀態正常（皆為 🟢 最新）')
    else:
        _a_red = sum(1 for r in _anom_rows if r['_icon'] == '🔴')
        _a_yel = sum(1 for r in _anom_rows if r['_icon'] == '🟡')
        st.caption(
            f'共 {len(_anom_rows)} 筆異常　｜　🔴 抓不到/過舊 {_a_red}　🟡 時效延遲 {_a_yel}'
            f'　｜　依嚴重度排序（含個股+ETF detail rows）'
        )
        _FREQ_COLOR_A = {'日頻': '#42a5f5', '月頻': MATERIAL_ORANGE,
                        '季頻': '#ef5350', '不定期': '#9e9e9e'}
        _td_aa = ('padding:6px 10px;border-bottom:1px solid #21262d;'
                  'font-size:12px')
        _hd_aa = (
            f"<div style='display:grid;grid-template-columns:2.4fr 1.4fr 0.8fr 1.2fr 1.6fr;"
            f"background:#0d1117'>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>資料名稱</div>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>來源</div>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>頻率</div>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>最新日期</div>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>狀態</div>"
            f"</div>"
        )
        _rows_aa = _hd_aa
        for _ar in _anom_rows:
            _aic = _ar['_icon']
            _abg2 = '#1a0808' if _aic == '🔴' else '#1a1200'
            _acol2 = '#ef5350' if _aic == '🔴' else '#ffb74d'
            _afq = _ar.get('頻率', '') or '—'
            _afq_color = _FREQ_COLOR_A.get(_afq, '#555')
            _rows_aa += (
                f"<div style='display:grid;grid-template-columns:2.4fr 1.4fr 0.8fr 1.2fr 1.6fr;"
                f"background:{_abg2}'>"
                f"<div style='{_td_aa};color:#e6edf3'>{_ar.get('資料名稱','—')}</div>"
                f"<div style='{_td_aa};color:#888'>{_ar.get('來源','—') or '—'}</div>"
                f"<div style='{_td_aa}'>"
                f"<span style='background:{_afq_color}22;color:{_afq_color};"
                f"border:1px solid {_afq_color};border-radius:10px;padding:1px 7px;"
                f"font-size:10px;font-weight:700'>{_afq}</span></div>"
                f"<div style='{_td_aa};color:#aaa'>{_ar.get('最新日期','—') or '—'}</div>"
                f"<div style='{_td_aa};color:{_acol2};font-weight:600'>"
                f"{_ar.get('新鮮度','—')}</div>"
                f"</div>"
            )
        st.markdown(
            f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
            f"{_rows_aa}</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            '💡 **燈號語意**：🔴 真失敗（API/proxy/網路問題）｜🟡 時效延遲或待補抓（仍可參考）；'
            '⚪ 此股無此科目、🔵 該股本期為 0 — 兩者**非異常**，已從本清單剔除（請至各 Tab 詳查）。'
        )
