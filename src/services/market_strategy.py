"""
市場狀態判斷引擎 v4.1 (§5.1)
目的：先判斷是否適合積極進場
輸出：bull / neutral / bear + 建議持股比例
v4.0 新增：M1B-M2 資金活水評分維度
v4.1 [step 3c]：來源切換 — TWSE BFI82U 直連 → tw_macro.fetch_finmind_foreign_investor
              ；yfinance.Ticker 直連 → macro_core.fetch_yf_ohlcv，全部走 NAS proxy
"""
try:
    from src.config import (MARKET_SCORE_BULL, MARKET_SCORE_NEUTRAL,
                        EXPOSURE_BULL, EXPOSURE_NEUTRAL, EXPOSURE_BEAR)
except ImportError:
    MARKET_SCORE_BULL = 3; MARKET_SCORE_NEUTRAL = 2
    EXPOSURE_BULL = 0.8; EXPOSURE_NEUTRAL = 0.5; EXPOSURE_BEAR = 0.2

# v18.449:市場廣度中性門檻 SSOT(原 inline `1.0`，尺度語意錯誤，見下方 market_regime docstring）
from shared.signal_thresholds import M1B_M2_LEG_ENABLED, MARKET_BREADTH_NEUTRAL_PCT

# P0-2 v18.369 深層拔毒:portfolio_exposure SSOT 收攏至 L2 risk_control(原本兩處同名異實作)
from src.compute.risk.risk_control import portfolio_exposure  # noqa: F401


# ── 外部資料抓取 ──────────────────────────────────────────────
def fetch_market_data():
    """
    取得大盤外資法人淨買賣（備援用，供 get_market_assessment 在 foreign_net=None 時呼叫）。

    [step 3c 來源切換] TWSE BFI82U 直連 → tw_macro.fetch_finmind_foreign_investor
    （走 NAS proxy，避免雲端 IP 被 TWSE 限流）。回傳 schema 不變，仍為
    {'foreign_net': 元(float), 'date': 'YYYYMMDD'}；外部呼叫端不需修改。
    """
    from src.data.macro import fetch_finmind_foreign_investor
    snap = fetch_finmind_foreign_investor(days_back=7)
    if snap.get('error') or snap.get('fii_net') is None:
        if snap.get('error'):
            print(f"[MarketStrategy] FinMind 法人數據失敗: {snap['error']}")
        return {'foreign_net': None, 'date': ''}  # None 表示資料取得失敗，非「零」
    # tw_macro 回 'YYYY-MM-DD'，對齊原 fetch_market_data 回傳的 'YYYYMMDD'
    date_str = str(snap.get('date', '')).replace('-', '')
    # v18.357 PR-Q5c S-PROV-1 phase 19:dict 加 source/fetched_at(schema-additive)
    import datetime as _dt_ms
    return {'foreign_net': float(snap['fii_net']), 'date': date_str,
            'source': 'tw_macro.fetch_finmind_foreign_investor',
            'fetched_at': _dt_ms.datetime.utcnow().isoformat() + 'Z'}


# ── 核心：市場狀態判斷 (§5.1) ─────────────────────────────────
def market_regime(index_close, ma60, ma120, foreign_buy, ad_ratio=None,
                  ma60_prev=None, ma120_prev=None, vol_today=0, avg_vol_20=1,
                  m1b_m2_gap=None, m1b_m2_prev=None,
                  ma60_above_3d=False, ma60_below_3d=False,
                  ma120_above_3d=False, ma120_below_3d=False,
                  ma120_rising=False, ma120_falling=False):
    """
    市場狀態判斷引擎 v4.1
    新增：MA60 連三日遲滯區間（Hysteresis）+ MA斜率過濾 + M1B-M2

    ma60_above_3d / ma60_below_3d: 最近3日收盤均站上/均跌破 MA60（防盤整雙巴）
    ad_ratio:    float | None — 市場廣度(0-100% 上漲家數佔比,`fetch_adl` 的
                 `ad_ratio` 欄位)；None = 不納入評分(選填,同 m1b_m2_gap 慣例)。
                 v18.449 修復:原預設 `1.0` + 門檻 `>1.0` 是誤把「比值」尺度
                 套用在「0-100% 百分比」資料源上，兩者恰好同值導致此因子從未
                 真正生效（永遠顯示同一個寫死的 1.00）；改預設 None + 選填，
                 未傳入時誠實不計分/不顯示，而非塞一個假中性值(§1 寧缺勿假)。
    m1b_m2_gap:  float | None — M1B年增率 - M2年增率（百分點）
    m1b_m2_prev: float | None — 上月 gap，用於判斷趨勢方向
    """
    score = 0
    signals = []

    # ① MA60 三日確認法則（Hysteresis — 防盤整頻繁加減倉）
    if ma60_above_3d:
        score += 1
        signals.append('✅ 站上MA60（連3日確認）')
        if ma60_prev and ma60 > ma60_prev:
            score += 0.5
            signals.append('✅ MA60向上彎折（真突破濾網）')
        elif ma60_prev and ma60 < ma60_prev:
            signals.append('⚠️ MA60仍向下（季線仍弱，觀察中）')
    elif ma60_below_3d:
        signals.append('❌ 跌破MA60（連3日確認）')
        if ma60_prev and ma60 < ma60_prev:
            signals.append('🔴 MA60向下彎折（季線走弱）')
    else:
        # 尚未連3日確認 → 中性，不計分也不扣分
        _lbl = '⚠️ 站上MA60（未滿3日，觀察中）' if index_close > ma60 else '⚠️ 跌破MA60（未滿3日，過渡中）'
        signals.append(_lbl)

    # ② MA120 三日確認法則 + 斜率訊號
    if ma120_above_3d:
        score += 1
        signals.append('✅ 站上MA120（連3日確認）')
        if ma120_rising:
            score += 0.5
            signals.append('✅ MA120向上彎折（真突破）')
        else:
            signals.append('⚠️ MA120橫盤偏弱（連3日在上但均線未翻揚）')
    elif ma120_below_3d:
        signals.append('❌ 跌破MA120（連3日確認）')
        if ma120_falling:
            signals.append('🔴 MA120向下彎折（空頭確認）')
    else:
        _lbl = '⚠️ 站上MA120（未滿3日，觀察中）' if index_close > ma120 else '⚠️ 跌破MA120（未滿3日，過渡中）'
        signals.append(_lbl)

    # ③ 外資方向
    # ── P1 v19.470:`foreign_buy == 0` 原本與 `None` 共用同一條「待更新」分支 ──
    # 兩者語意完全不同:`None` = 沒抓到(不知道),`0` = 真的買賣相抵(知道,且是中性)。
    # 舊碼把兩者混為一談,再配上 `market_assessment_apply` 端 `_foreign_net_loaded = 0`
    # 的預設值,等於**把「不知道」編碼成一個合法的市場觀測值**(§1)。
    # 兩者計分都是 0 分(持平本來就不該加分),差別在**畫面要說實話**:
    # 一個是「還沒公布」,一個是「公布了,剛好持平」。
    if foreign_buy is None:
        signals.append('⏰ 外資數據待更新（收盤後15:30可用）')
    elif foreign_buy == 0:
        signals.append('➖ 外資買賣相抵（持平，0 分）')
    elif foreign_buy > 0:
        score += 1
        signals.append(f'✅ 外資買超 {foreign_buy/1e8:.1f}億')
    else:
        signals.append(f'❌ 外資賣超 {abs(foreign_buy)/1e8:.1f}億')

    # ④ 市場廣度（選填，不傳則略過，同 m1b_m2_gap 慣例 — 未接真值前不假裝中性）
    if ad_ratio is not None:
        if ad_ratio > MARKET_BREADTH_NEUTRAL_PCT:
            score += 1
            signals.append(f'✅ 市場廣度正向 ({ad_ratio:.1f}%)')
        else:
            signals.append(f'❌ 市場廣度偏弱 ({ad_ratio:.1f}%)')

    # ⑤ M1B-M2 資金活水（選填，不傳則略過，向後相容）
    # ── 2026-08-19：本條腿已停用（`M1B_M2_LEG_ENABLED = False`）────────────
    # 停用理由與復活條件全寫在 `shared/signal_thresholds.M1B_M2_LEG_ENABLED`
    # 的 docstring（AUC 0.5366、lift 1.019 vs 0.984、方向與設計假設相反，
    # 且來源資料量綱本身就是壞的）。**計分邏輯刻意保留**，同
    # `HEALTH_FNET_BONUS = 0` 的處置 —— 刪掉會讓「評估過、結論是無預測力」
    # 這件事從程式碼裡消失。開關在 L0，離線校準與線上畫面**同一個開關**，
    # 不會再出現「校準與線上是兩套系統」（本次修正的問題之一）。
    if m1b_m2_gap is not None and not M1B_M2_LEG_ENABLED:
        # 停用 ≠ 缺資料。上游確實給了值，只是我們判定它不該進分數 ——
        # 這件事要說出來（§1），否則使用者只會發現「資金活水那行不見了」。
        signals.append(f'⬜ M1B-M2 資金活水已停用（{m1b_m2_gap:+.2f}%，'
                       f'AUC 0.54 無預測力＋來源量綱異常）— 不計分')
    elif m1b_m2_gap is not None:
        _trending_up = (m1b_m2_prev is not None) and (m1b_m2_gap > m1b_m2_prev)
        if m1b_m2_gap > 0 and _trending_up:
            score += 1
            signals.append(f'💧 M1B-M2 活水正向且上升 ({m1b_m2_gap:+.2f}%)')
        elif m1b_m2_gap > 0:
            score += 0.5
            signals.append(f'💧 M1B-M2 活水正向 ({m1b_m2_gap:+.2f}%)，趨勢待確認')
        else:
            signals.append(f'🚱 M1B-M2 資金動能偏弱 ({m1b_m2_gap:+.2f}%)，延後積極進場')

    # ── 狀態機判定（MA120 三日法則為主軸，其餘因子為輔助訊號）
    if ma120_above_3d and ma120_rising:
        regime = 'bull'    # 🟢 晴天：連3日站上 + 均線向上
    elif ma120_below_3d and ma120_falling:
        regime = 'bear'    # 🔴 雨天：連3日跌破 + 均線向下
    else:
        regime = 'neutral' # 🟡 多雲：所有過渡狀態（含單日訊號、均線走平等）

    # ── 瘋牛濾網
    # ── P1 v19.470:`else False` 把「沒有量資料」靜默等同「沒有瘋牛」──────────
    # 實測 `data_cache/twii_ohlcv.parquet` 自 2026-07-09 起 volume 每日皆為 0
    # (Yahoo Chart API 對 ^TWII 停止回傳量),整條濾網已**靜默死亡一個多月**,
    # 不 log、不 raise、不帶旗標 —— 完全符合 §1 所禁的「讓程式不報錯」。
    # 瘋牛本來就不計分(只 append signal),故行為零位移;差別在**畫面說實話**。
    _vol_ok  = (avg_vol_20 or 0) > 0 and (vol_today or 0) > 0
    _bullrun = (vol_today > avg_vol_20 * 1.3) if _vol_ok else False
    if _bullrun:
        signals.append(f'💹 瘋牛模式：成交量 {vol_today/avg_vol_20:.1f}x 均量')
    elif not _vol_ok:
        signals.append('⬜ 成交量資料缺失（瘋牛濾網未評估）')

    # v18.449:max_score 須反映「實際可拿到的滿分」——固定 4 項一定會評（MA60/MA60斜率
    # /MA120/MA120斜率共 3.0 + 外資 1.0 = 4.0），ad_ratio/m1b_m2_gap 未傳入時不該計入
    # 分母（否則分母恆虛高 1，score/max_score 永遠達不到滿分,即使全部訊號皆正向）。
    _max = 4.0
    if ad_ratio is not None:
        _max += 1
    # 停用的腿**不進分母**——否則分子恆拿不到那 1 分、分母卻算它，等於把
    # 「我們決定不看這條腿」編碼成「這條腿是利空」（正是本輪在修的那類錯）。
    if m1b_m2_gap is not None and M1B_M2_LEG_ENABLED:
        _max += 1

    # ── 2026-08-19:選填腿缺席必須可見(§1 降級不得靜默)────────────────────────
    # `_max` 隨「當天有沒有拿到這兩條選填腿」在 4/5/6 之間浮動。數學上這是權重
    # 重新歸一化(缺的腿同時退出分子與分母),與 macro_helpers 對 jqavg 的做法一致;
    # **但它有一個危險的副作用**:同一組原始 score,腿缺席時百分比會**上升**。
    #   例:base 4 腿拿 4 分 → 有 m1b 腿(該腿 0 分)= 4/5 = 80%
    #                        → 無 m1b 腿          = 4/4 = 100%
    # 也就是「沒抓到」看起來比「抓到了但偏弱」更樂觀。實測(2007-2026 n=4,789):
    # max_score 5 vs 6 讓 12.4% 的交易日換 tier,方向偏綠(轉守→中性偏多 366 天)。
    #
    # 上游已於同版修掉主要來源(`market_assessment_apply` 備援分支漏傳 m1b_m2_gap)。
    # 這裡補的是**可見性**:schema-additive 兩個欄位 + stderr log,不改任何計分。
    # 消費端可據 `missing_factors` 標示「本次評分少了哪幾條腿」。
    _missing_factors = []
    if ad_ratio is None:
        _missing_factors.append('市場廣度')
    # 「停用」不算「缺失」——腿停用時分子分母同時不算它，數學上不存在
    # 上面警告的那種偏移；把它列進 missing 會每天噴一次假警報。
    if m1b_m2_gap is None and M1B_M2_LEG_ENABLED:
        _missing_factors.append('M1B-M2 資金活水')
    if _missing_factors:
        import sys as _sys_mr
        print(f'[market_regime] ⚠️ 選填腿缺席:{"、".join(_missing_factors)}'
              f' → max_score={_max:.0f}(滿分 6)。同一組 score 在腿缺席時百分比會偏高,'
              f' 消費端請據 missing_factors 標示降級', file=_sys_mr.stderr)

    return {
        'regime': regime,
        'bullrun': _bullrun,
        'score': score,
        'max_score': _max,
        'signals': signals,
        'label': {'bull': '🟢 多頭（晴天）', 'neutral': '🟡 震盪（多雲）', 'bear': '🔴 空頭防禦（雨天）'}[regime],
        'm1b_m2_gap': m1b_m2_gap,
        # 2026-08-19 schema-additive:選填腿缺席揭露(不改計分,見上方 _max 註解)
        'missing_factors': _missing_factors,
        'score_partial': bool(_missing_factors),
    }


# ── market_score:**現役程式碼**,不是相容性殘骸(2026-08-27 更正一句說謊的註解)──
#
# 本行以上原本掛著一句「舊版評分(退場中、僅保留相容性,新版請用 market_regime)」
# —— **那句話與事實相反**。照它動手(把本函式當垃圾清掉)會直接打斷主流程,因為:
#   `get_market_assessment()` 在下方**無條件**呼叫本函式,再把兩份結果合併成
#   `{**old_result, **regime_result}` 交給整個總經 / 大盤格局鏈路。
#
# 本函式**現在**的真實角色(2026-08-27 實查,非轉述):
#   1. 合併時 `score` / `max_score` / `signals` 三個 key **一律被 `market_regime()`
#      蓋掉**(regime 在右邊)。所以本函式對外的**獨佔輸出只剩兩個**:
#         `status`     — 多頭 / 盤整 / 空頭(中文字串)
#         `confidence` — 0~100
#      這兩個 key 是 `get_market_assessment()` 回傳 dict 裡**唯一**由本函式提供的東西。
#   2. 另有直接單測 caller:`tests/test_p1_unknown_vs_bearish.py::test_market_score_*`
#      —— 釘住兩條 §1 修補(`foreign_buy=None` 不得 TypeError;沒有均量時
#      不得捏 `量比 = 1.0x`)。那兩條測的是「不捏造」,與本函式存廢無關。
#
# 什麼條件下才可以**真的**退場(三條全成立才准動;缺一即為誤刪):
#   (a) 確認 `status` / `confidence` 兩個 key 在全 repo 沒有消費端 ——
#       含 `session_state['mkt_info']` 的下游、AI prompt 組裝、置底常駐條;
#   (b) **同時**刪掉下方的呼叫行與 `{**old_result, **regime_result}` 合併 ——
#       只刪函式會變 NameError,只刪呼叫會讓那兩個 key 靜默消失;
#   (c) 為 `tests/test_p1_unknown_vs_bearish.py` 的兩條 §1 迴歸另找宿主,
#       **不可**隨手連測試一起刪。
#
# ⚠️ (a) 的「目前無消費端」是 2026-08-27 **單組**掃描結果,**沒有第二組獨立驗過**
#    (§-2 規則 6)→ 只能當**待驗事項**,不得直接當成刪除許可。
#
# 守衛:`tests/test_deprecation_honesty.py`
#   - 有人把退場標記寫回本函式(而它仍有 caller)→ 轉紅;
#   - `status` / `confidence` 從 `get_market_assessment()` 的結果裡消失 → 轉紅。
#
# ⚠️ 本段刻意**不寫出**那句舊標記的原字串 —— 守衛是靠掃描標記文字判定的,
#    在這裡照抄一次會讓守衛把這段誠實的更正註解本身當成違規(實測過)。
def market_score(index_price, ma200, foreign_buy, volume, avg_volume=1000):
    """MA200 年線 + 外資 + 量能的三因子評分。**現役**,由 `get_market_assessment()` 呼叫。

    對外的獨佔輸出是 `status` / `confidence`(其餘 key 合併時會被 `market_regime()` 蓋掉)。
    退場條件見上方註解 —— 這不是「保留相容性」的死碼。
    """
    score = 0; signals = []
    if index_price > ma200:
        score += 2; signals.append('✅ 站上年線 (+2)')
    else:
        signals.append('❌ 跌破年線 (0)')
    # P1 v19.470:foreign_buy 可能為 None(上游三態化後)→ `abs(None)` 會 TypeError。
    if foreign_buy is None:
        signals.append('⏰ 外資數據待更新 (0)')
    else:
        _fb_bn = round(foreign_buy / 1e8, 1) if abs(foreign_buy) > 1e6 else foreign_buy
        if foreign_buy > 0:
            score += 2; signals.append(f'✅ 外資買超 {_fb_bn:+.1f}億 (+2)')
        else:
            signals.append(f'❌ 外資賣超 {abs(_fb_bn):.1f}億 (0)')
    # P1 v19.470:`else 1` 是捏造值 —— 沒有均量時「量比 = 1.0x」是憑空生出來的
    # 觀測(§1「自行估一個合理值當常數」)。改為 None + 誠實文案,不計分不扣分。
    _vol_ratio = round(volume / avg_volume, 2) if (avg_volume or 0) > 0 else None
    if _vol_ratio is None:
        signals.append('⬜ 成交量資料缺失（量能項未評估）')
    elif volume > avg_volume:
        score += 1; signals.append(f'✅ 量能放大 {_vol_ratio:.1f}x (+1)')
    else:
        signals.append(f'⚠️ 量能萎縮 {_vol_ratio:.1f}x (0)')
    status = '多頭' if score >= 4 else ('盤整' if score >= 2 else '空頭')
    confidence = min(100, score * 20) if score >= 4 else (score * 15 if score >= 2 else max(0, 30 - score*10))
    return {'score': score, 'max_score': 5, 'status': status,
            'confidence': confidence, 'signals': signals}


def get_market_assessment(df_index=None, foreign_net=None,
                          m1b_m2_gap=None, m1b_m2_prev=None, ad_ratio=None):
    """
    整合版市場評估（v4.0 升級版）
    同時輸出 regime (bull/neutral/bear) 與舊版 score
    m1b_m2_gap:  M1B年增率 - M2年增率（百分點）；None = 不納入評分
    m1b_m2_prev: 上月 gap，用於判斷趨勢方向
    ad_ratio:    市場廣度(0-100% 上漲家數佔比)；None = 不納入評分(v18.449 新增)
    """
    import pandas as pd
    if df_index is None:
        # [step 3c] yfinance.Ticker 直連 → macro_core.fetch_yf_ohlcv（走 NAS proxy 直打 Chart API）
        try:
            from src.data.macro import fetch_yf_ohlcv
            _df = fetch_yf_ohlcv('^TWII', range_='9mo', interval='1d')
            if _df.empty:
                print('[MarketStrategy] 大盤數據失敗: macro_core 回傳空 DataFrame')
                return None
            df_index = _df[['Close', 'Volume']]
        except Exception as e:
            print(f'[MarketStrategy] 大盤數據失敗: {e}')
            return None

    if df_index is None or df_index.empty:
        return None

    # ── 資料新鮮度守門：最後一筆若超過 7 個自然日，視為陳舊資料 ─────
    _last_ts = df_index.index[-1]
    _last_dt = pd.Timestamp(_last_ts).tz_localize(None) if getattr(_last_ts, 'tzinfo', None) else pd.Timestamp(_last_ts)
    _days_old = (pd.Timestamp.now() - _last_dt).days
    if _days_old > 7:
        print(f'[MarketStrategy] 資料過舊 {_days_old} 天（末筆 {_last_dt.date()}），視為無效')
        return None

    # 欄位標準化（fetch_single 回傳小寫 / yfinance 回傳大寫）
    _df = df_index.copy()
    if 'close' in _df.columns and 'Close' not in _df.columns:
        _df = _df.rename(columns={'close':'Close','open':'Open','high':'High','low':'Low','volume':'Volume'})
    if 'Close' not in _df.columns:
        return None
    df_index = _df

    current_price = float(df_index['Close'].iloc[-1])
    _close = df_index['Close']

    ma60  = float(_close.rolling(60).mean().iloc[-1])  if len(df_index) >= 60  else current_price
    ma200 = float(_close.rolling(200).mean().iloc[-1]) if len(df_index) >= 200 else current_price
    avg_vol   = float(df_index['Volume'].rolling(20).mean().iloc[-1]) if 'Volume' in df_index.columns else 1000
    vol_today = float(df_index['Volume'].iloc[-1]) if 'Volume' in df_index.columns else avg_vol
    ma5   = float(_close.rolling(5).mean().iloc[-1]) if len(df_index) >= 5 else current_price

    # ── MA120：NaN 防呆（資料不足時絕不用 current_price 填補）────────
    _ma120_series = _close.rolling(120).mean()
    _ma120_raw    = _ma120_series.iloc[-1] if len(df_index) >= 120 else float('nan')
    if pd.isna(_ma120_raw):
        print(f'[MarketStrategy] MA120 資料不足（{len(df_index)} bars），回傳 None 避免誤判')
        return None
    ma120 = float(_ma120_raw)

    # ── MA60 三日確認法則（Hysteresis，防季線盤整雙巴）─────────────────
    _ma60_series  = _close.rolling(60).mean()
    _c3_60 = _close.iloc[-3:].values
    _m3_60 = _ma60_series.iloc[-3:].values
    ma60_above_3d = bool(len(_c3_60) == 3 and not any(pd.isna(_m3_60)) and (_c3_60 > _m3_60).all())
    ma60_below_3d = bool(len(_c3_60) == 3 and not any(pd.isna(_m3_60)) and (_c3_60 < _m3_60).all())

    # ── MA120 三日確認法則（最近 3 交易日收盤 vs MA120）──────────────────
    _c3 = _close.iloc[-3:].values
    _m3 = _ma120_series.iloc[-3:].values
    ma120_above_3d = bool(len(_c3) == 3 and (_c3 > _m3).all())
    ma120_below_3d = bool(len(_c3) == 3 and (_c3 < _m3).all())

    # ── MA120 斜率（今日 vs 5 日前，防單日假訊號）────────────────────
    _ma120_5ago   = float(_ma120_series.iloc[-6]) if len(df_index) >= 126 else float('nan')
    ma120_rising  = (not pd.isna(_ma120_5ago)) and (ma120 > _ma120_5ago)
    ma120_falling = (not pd.isna(_ma120_5ago)) and (ma120 < _ma120_5ago)

    # MA60 斜率（供訊號顯示）
    ma60_prev = float(_ma60_series.iloc[-2]) if len(df_index) >= 61 else None

    if foreign_net is None:
        mkt = fetch_market_data()
        # P1 v19.470:`or 0` 又把 None 折回 0(且 falsy 回退連「真的 0」也吃掉)。
        # `fetch_market_data` 本來就會在失敗時回 `foreign_net=None`,並在
        # docstring 明說「None 表示資料取得失敗,非『零』」—— 這行把上游的誠實
        # 又抹掉一次。保留 None,交給 `market_regime` 的三態分支處理。
        foreign_net = mkt.get('foreign_net')

    regime_result = market_regime(
        current_price, ma60, ma120, foreign_net, ad_ratio=ad_ratio,
        ma60_prev=ma60_prev, ma120_prev=None,
        vol_today=vol_today, avg_vol_20=avg_vol,
        m1b_m2_gap=m1b_m2_gap, m1b_m2_prev=m1b_m2_prev,
        ma60_above_3d=ma60_above_3d, ma60_below_3d=ma60_below_3d,
        ma120_above_3d=ma120_above_3d, ma120_below_3d=ma120_below_3d,
        ma120_rising=ma120_rising, ma120_falling=ma120_falling,
    )
    # ⚠️ 本行**不是**相容性殘留:`market_score` 是現役的(2026-08-27 更正,見其定義處註解)。
    # 合併後 score/max_score/signals 由 regime 蓋掉,`old_result` 對外只剩
    # `status` / `confidence` 兩個 key —— 刪這行等於靜默拿掉那兩個欄位。
    old_result    = market_score(current_price, ma200, foreign_net, vol_today, avg_vol)

    # P5修正: 保留新版signals，不讓old_result.signals覆蓋
    result = {**old_result, **regime_result}   # regime優先
    result['signals'] = regime_result.get('signals', [])  # 確保新版signals不被覆蓋
    result['index_price']    = round(current_price, 2)
    result['ma5']            = round(ma5, 2)
    result['ma60']           = round(ma60, 2)
    result['ma120']          = round(ma120, 2)
    result['ma200']          = round(ma200, 2)
    result['index_below_ma5'] = current_price < ma5
    result['foreign_net']   = foreign_net
    result['exposure']      = portfolio_exposure(regime_result['regime'])
    result['exposure_pct']  = f"{portfolio_exposure(regime_result['regime'])*100:.0f}%"
    return result
