"""
v5_modules.py — 台股 AI 戰情室 v5.0 策略滿配版
Tasks: 5=財報領先 6=RS相對強度 7=估值河流圖 8=型態辨識
       9=布林爆發 10=7%存股 11=強制防守 12=動態配置
Author: AI戰情室 v5.0 | 防禦性開發
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple
from shared.colors import TRAFFIC_YELLOW
from shared.thresholds import (
    YIELD_HIGH, YIELD_MID, YIELD_LOW,
    # v19.179 B1-b:三檔目標價的反推(÷ YIELD_*_DEC)已下沉 classify_stock_357_price,
    # 本檔不再自行除,故不再 import YIELD_*_DEC(§2.1 一個算式只有一份實作)。
    classify_stock_357_price,
)
# v18.241 E12: 龍多股篩選門檻從 shared SSOT 引入
from shared.signal_thresholds import (
    BB_NEAR_UPPER_STRICT_RATIO,  # Phase 2 Batch 5d v18.432:布林貼近上軌 STRICT tier SSOT
    CONTRACT_LIABILITY_YOY_GROWTH_THRESHOLD_PCT,
    CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT,
    RS_SIGMA_LEAD_MIN,   # v19.70:RS σ 分級 SSOT（原 1.0/0.3/-0.3 inline，抗跌 RS 選股共用）
    RS_SIGMA_MILD_MIN,
    RS_SIGMA_LAG_MAX,
    VOLUME_RATIO_SURGE,  # v19.95 批次3(a):布林突破量能確認 gate（既有 SSOT 1.5×,不新增常數）
)


# ══════════════════════════════════════════════════════════════════════════════
# [Task 5] 財報領先指標 — 合約負債 + 資本支出增速
# ══════════════════════════════════════════════════════════════════════════════
def analyze_fundamental_leading(cl_now: Optional[float], cl_prev: Optional[float],
                                 capex_now: Optional[float], capex_prev: Optional[float],
                                 equity: Optional[float]) -> dict:
    """
    合約負債 YoY 成長 + 資本支出 / 股本比，預判未來 3-6 個月營收動向。

    Args:
        cl_now:    本期合約負債（元）
        cl_prev:   去年同期合約負債（元）
        capex_now: 本期資本支出（元）
        capex_prev:去年同期資本支出
        equity:    股本（元）

    Edge E-C(新股): cl_prev=None → 只做截面分析，不計 YoY
    Edge E-A(API斷): cl_now=None → 回傳 neutral

    Returns: {cl_yoy, capex_ratio, signal, color, msg}
    """
    R = '#da3633'; Y = TRAFFIC_YELLOW; N = '#484f58'

    # Edge: 完全無數據
    if cl_now is None and capex_now is None:
        return {"signal": "⚪ 無財報資料", "color": N,
                "msg": "合約負債與資本支出資料均不可用", "cl_yoy": None, "capex_ratio": None}

    # 合約負債 YoY
    cl_yoy = None
    if cl_now and cl_prev and cl_prev > 0:
        cl_yoy = (cl_now - cl_prev) / cl_prev * 100

    # 資本支出 / 股本比
    capex_ratio = None
    if capex_now and equity and equity > 0:
        capex_ratio = capex_now / equity * 100

    # 訊號邏輯（「龍多股」標準）
    cl_ok     = cl_now and cl_now > 0
    # v18.241 E12: 龍多股篩選門檻從 SSOT 引入
    cl_growth = cl_yoy and cl_yoy > CONTRACT_LIABILITY_YOY_GROWTH_THRESHOLD_PCT
    capex_ok  = capex_ratio and capex_ratio > CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT

    if cl_growth and capex_ok:
        return {"signal": "🔴 龍多股", "color": R,
                "msg": f"合約負債 YoY +{cl_yoy:.1f}% + 資本支出/股本 {capex_ratio:.0f}% — 未來 3-6 月營收爆發機率高",
                "cl_yoy": round(cl_yoy, 1), "capex_ratio": round(capex_ratio, 1)}
    elif cl_ok and cl_growth:
        return {"signal": "🔴 訂單增加", "color": R,
                "msg": f"合約負債 YoY +{cl_yoy:.1f}% — 手頭訂單充裕，業績有保障",
                "cl_yoy": round(cl_yoy, 1) if cl_yoy else None, "capex_ratio": round(capex_ratio, 1) if capex_ratio else None}
    elif capex_ok:
        return {"signal": "🟡 積極擴張", "color": Y,
                "msg": f"資本支出/股本 {capex_ratio:.0f}% — 積極蓋廠，2年後可能爆發",
                "cl_yoy": round(cl_yoy, 1) if cl_yoy else None, "capex_ratio": round(capex_ratio, 1)}
    else:
        return {"signal": "⚪ 一般水準", "color": N,
                "msg": "合約負債與資本支出未達龍多標準，建議持續觀察",
                "cl_yoy": round(cl_yoy, 1) if cl_yoy else None,
                "capex_ratio": round(capex_ratio, 1) if capex_ratio else None}


# ══════════════════════════════════════════════════════════════════════════════
# [Task 6] RS 相對強度指標
# 公式: RS = (個股同期漲跌幅 - 大盤同期漲跌幅) / 大盤同期波動率
# ══════════════════════════════════════════════════════════════════════════════
def calc_relative_strength(df_stock: pd.DataFrame, df_market: pd.DataFrame,
                            periods: Tuple[int, ...] = (20, 60, 120)) -> dict:
    """
    計算個股相對大盤的超額報酬強度（Z-Score 正規化）。

    Args:
        df_stock:  個股 K 線（含 close 欄）
        df_market: 大盤 K 線（含 close 欄）
        periods:   多週期評估（預設 20/60/120 日）

    Edge E-C(資料不足): 若 len < period → 跳過該週期
    Edge E-B(波動率=0): σ=0 時 RS=0，避免 ZeroDivisionError

    Returns: {rs_scores: {20: 1.23, 60: 0.8, ...}, signal, color, msg}
    """
    R = '#da3633'; G = '#2ea043'; Y = TRAFFIC_YELLOW; N = '#484f58'

    # 各週期同時算出 σ標準化 RS + 原始個股/大盤區間報酬(供顯示，schema-additive)
    def _rs_one(n):
        if len(df_stock) < n or len(df_market) < n:
            return None
        s_ret = (df_stock['close'].iloc[-1] / df_stock['close'].iloc[-n] - 1) * 100
        m_ret = (df_market['close'].iloc[-1] / df_market['close'].iloc[-n] - 1) * 100
        m_std = df_market['close'].pct_change().tail(n).std() * 100
        _rs = round((s_ret - m_ret) / m_std, 2) if m_std > 0.01 else 0.0
        return {"rs": _rs, "s_ret": round(s_ret, 2), "m_ret": round(m_ret, 2)}

    detail = {p: _rs_one(p) for p in periods}
    scores = {p: (d["rs"] if d else None) for p, d in detail.items()}
    valid  = [d for d in detail.values() if d is not None]

    if not valid:
        return {"rs_scores": scores, "signal": "⚪ 資料不足", "color": N,
                "avg_rs": None, "avg_stock_ret": None, "avg_market_ret": None,
                "msg": "資料不足，無法計算相對強度"}

    avg_rs = round(sum(d["rs"] for d in valid) / len(valid), 2)
    # v19.70:回原始報酬均值(顯示用)。σRS 排名 + 這兩欄讓 UI 直接標「個股 vs 大盤」超額。
    avg_stock_ret = round(sum(d["s_ret"] for d in valid) / len(valid), 2)
    avg_market_ret = round(sum(d["m_ret"] for d in valid) / len(valid), 2)

    if avg_rs >= RS_SIGMA_LEAD_MIN:
        signal, color = "🔴 逆勢強股（領漲）", R
        msg = f"RS均值 +{avg_rs:.2f}σ — 顯著強於大盤，主力護盤意願高"
    elif avg_rs >= RS_SIGMA_MILD_MIN:
        signal, color = "🟡 偏強（溫和抗跌）", Y
        msg = f"RS均值 +{avg_rs:.2f}σ — 略強於大盤，可列觀察清單"
    elif avg_rs >= RS_SIGMA_LAG_MAX:
        signal, color = "⚪ 同步大盤", N
        msg = f"RS均值 {avg_rs:.2f}σ — 與大盤連動，無特別籌碼支撐"
    else:
        signal, color = "🟢 落後大盤（弱勢）", G
        msg = f"RS均值 {avg_rs:.2f}σ — 弱於大盤，空頭環境中優先出清"

    return {"rs_scores": scores, "signal": signal, "color": color,
            "avg_rs": avg_rs, "avg_stock_ret": avg_stock_ret,
            "avg_market_ret": avg_market_ret, "msg": msg}


# ══════════════════════════════════════════════════════════════════════════════
# [Task 7] 估值河流圖（PE / PB 滾動 μ ± σ 分區）
# ══════════════════════════════════════════════════════════════════════════════
def calc_valuation_zone(price: float, eps_ttm: float, bvps: float,
                         hist_pe_mean: float, hist_pe_std: float,
                         hist_pb_mean: float, hist_pb_std: float) -> dict:
    """
    根據滾動 PE/PB 的歷史均值 ± 標準差，判定現在估值位階。

    區間: 特價(<μ-2σ) | 便宜(μ-2σ~μ-σ) | 合理(μ-σ~μ+σ) | 昂貴(μ+σ~μ+2σ) | 超貴(>μ+2σ)

    Edge E-A(EPS=0負): eps_ttm <= 0 → 改用 PB 評估，跳過 PE
    Edge E-B(歷史不足): hist_std = 0 → 只顯示現值，無法分區
    """
    R = '#da3633'; G = '#2ea043'; N = '#484f58'

    result = {"pe": None, "pb": None, "pe_zone": "N/A", "pb_zone": "N/A",
              "signal": "⚪", "color": N, "msg": ""}

    def _zone(val, mu, sigma):
        if sigma < 0.01: return "無歷史基準", N
        if val < mu - 2*sigma: return "🟢便宜（特價）", G
        if val < mu - sigma:   return "🟢便宜", G
        if val < mu + sigma:   return "⚪合理", N
        if val < mu + 2*sigma: return "🔴昂貴", R
        return "🔴超貴", R

    # PE 評估
    if eps_ttm and eps_ttm > 0 and price > 0:
        pe = round(price / eps_ttm, 1)
        pe_zone, _ = _zone(pe, hist_pe_mean, hist_pe_std)
        result.update({"pe": pe, "pe_zone": pe_zone})
    else:
        pe_zone = "EPS<0（虧損）"
        result.update({"pe": None, "pe_zone": pe_zone})

    # PB 評估
    if bvps and bvps > 0 and price > 0:
        pb = round(price / bvps, 2)
        pb_zone, _ = _zone(pb, hist_pb_mean, hist_pb_std)
        result.update({"pb": pb, "pb_zone": pb_zone})
    else:
        pb_zone = "無資料"
        result.update({"pb": None, "pb_zone": pb_zone})

    # 綜合訊號（PE 優先，PB 備援）
    primary_zone  = pe_zone  if result['pe'] else pb_zone

    if "便宜" in primary_zone or "特價" in primary_zone:
        result.update({"signal": "🟢 估值便宜", "color": G,
                        "msg": f"PE={result['pe']} 位於{primary_zone} — 估值具吸引力，可分批布局"})
    elif "昂貴" in primary_zone or "超貴" in primary_zone:
        result.update({"signal": "🔴 估值昂貴", "color": R,
                        "msg": f"PE={result['pe']} 位於{primary_zone} — 估值偏高，追高風險大"})
    else:
        result.update({"signal": "⚪ 估值合理", "color": N,
                        "msg": f"PE={result['pe']} 位於合理區間 — 可持有，等候更好買點"})
    return result


# ══════════════════════════════════════════════════════════════════════════════
# [Task 9] 布林帶寬爆發偵測
# 公式: BW = (Upper - Lower) / MA20 × 100%
# ══════════════════════════════════════════════════════════════════════════════
def detect_bollinger_breakout(df: pd.DataFrame, window: int = 20, std_k: float = 2.0) -> dict:
    """
    計算布林帶寬 BW，偵測「極度收縮」(窒息量前兆) 與「突破上軌」訊號。

    Args:
        df: K 線（含 close 與 volume 欄）
        window: MA 週期，預設 20
        std_k:  帶寬倍數，預設 2σ

    Edge E-C(資料<20): 直接回傳警示
    Edge E-B(std=0): close 全相同（停牌），回傳中性

    Returns: {bw, bw_pct, upper, lower, ma, signal, color, msg}
    """
    R = '#da3633'; Y = TRAFFIC_YELLOW; N = '#484f58'

    if len(df) < window:
        return {"bw": None, "signal": "⚪ 資料不足", "color": N,
                "msg": f"需至少 {window} 根 K 線，目前僅 {len(df)} 根"}

    # v18.339 PR-J3 S-MED:bfill 移除避免 lookahead(未來資料回填過去)。
    # 改 ffill().dropna() — 起頭缺值丟掉而不是用後續資料偽造,
    # rolling(window).mean() 後 NaN tail 自然不影響最新一根判斷。
    close = df['close'].ffill().dropna()
    ma    = close.rolling(window).mean()
    std   = close.rolling(window).std(ddof=0)  # v19.105:Bollinger 母體 σ

    ma_now  = float(ma.iloc[-1])
    std_now = float(std.iloc[-1])

    if std_now < 0.001 or ma_now < 0.001:
        return {"bw": 0, "signal": "⚪ 停牌/無波動", "color": N, "msg": "價格無波動（疑似停牌）"}

    upper = ma_now + std_k * std_now
    lower = ma_now - std_k * std_now
    bw    = round((upper - lower) / ma_now * 100, 2)
    close_now = float(close.iloc[-1])

    # 歷史 BW 百分位（近 120 日）
    bw_hist = ((ma + std_k*std) - (ma - std_k*std)) / ma * 100
    bw_pct  = round(float((bw_hist.tail(120) < bw).mean() * 100), 1)

    # v19.95 批次3(a) 量能確認（§7 user 核准）:docstring 一直聲明吃 volume 但從未用 —
    # 無量突破常為假突破。vol_ratio = 今量 / 20 日均量(mirror check_fake_breakout pattern);
    # 缺 volume 欄 / 均量無效 → None(誠實未知,不偽造 1.0),此時不降級(維持舊行為)。
    vol_ratio = None
    if 'volume' in df.columns:
        _avg_v = df['volume'].rolling(window).mean().iloc[-1]
        if pd.notna(_avg_v) and _avg_v > 0:
            vol_ratio = round(float(df['volume'].iloc[-1]) / float(_avg_v), 2)
    volume_confirmed = vol_ratio is not None and vol_ratio >= VOLUME_RATIO_SURGE

    # 訊號判斷
    # v18.432 Batch 5d:0.995 → BB_NEAR_UPPER_STRICT_RATIO SSOT(STRICT tier,訊號層 action 用嚴格門檻)
    # 對應 LOOSE tier BB_NEAR_UPPER_RATIO=0.97(tech_indicators / tab_stock 篩選用,寬鬆 3% tolerance)
    near_upper = close_now >= upper * BB_NEAR_UPPER_STRICT_RATIO
    bw_squeeze = bw_pct < 20  # 帶寬在近120日最低20%

    if near_upper and bw > 3:
        # v19.95:量能分流 — 有量=爆發🔴;量不足=待確認🟡(防無量假突破);量未知=舊行為🔴
        if volume_confirmed:
            signal, color = "🔴 布林突破爆發", R
            msg = (f"BW={bw:.1f}% 且收盤 {close_now:.2f} 貼近上軌 {upper:.2f}"
                   f"（量增 {vol_ratio:.1f}× 確認）— 短線爆發買點")
        elif vol_ratio is not None:
            signal, color = "🟡 布林突破待確認", Y
            msg = (f"BW={bw:.1f}% 貼近上軌 {upper:.2f} 但量能不足"
                   f"（{vol_ratio:.1f}× < {VOLUME_RATIO_SURGE}×）— 慎防無量假突破")
        else:
            signal, color = "🔴 布林突破爆發", R
            msg = f"BW={bw:.1f}% 且收盤 {close_now:.2f} 貼近上軌 {upper:.2f} — 短線爆發買點（量能未知）"
    elif bw_squeeze:
        signal, color = "🟡 布林極度收縮", Y
        msg = f"BW={bw:.1f}%（近120日第{bw_pct:.0f}百分位）— 窒息量前兆，方向選擇即將到來"
    elif near_upper:
        signal, color = "🟡 靠近上軌", Y
        msg = f"收盤 {close_now:.2f} 靠近布林上軌 {upper:.2f}，注意短線壓力"
    else:
        signal, color = "⚪ 帶寬正常", N
        msg = f"BW={bw:.1f}%，帶寬正常，無特殊訊號"

    return {"bw": bw, "bw_pct": bw_pct, "upper": round(upper, 2),
            "lower": round(lower, 2), "ma": round(ma_now, 2),
            "close": close_now, "near_upper": near_upper,
            "vol_ratio": vol_ratio, "volume_confirmed": volume_confirmed,
            "signal": signal, "color": color, "msg": msg}


# ══════════════════════════════════════════════════════════════════════════════
# [Task 10] 存股殖利率評估（357 殖利率法則）
# 公式: Y = AvgCashDividend_TWD / Price × 100%
#
# v19.179 B1-b 量綱修正（CLAUDE.md §4.1 / §2.1 SSOT / §1 Fail Loud）
# ------------------------------------------------------------------------------
# 舊契約是 `est_div = eps_ttm × avg_payout`，其中 `avg_payout` 標明是「配發率
# (0~1)」。但唯一的 production caller（section_health_score.py:304）傳的是
# `avg_div / price` —— 那是**殖利率**，不是配發率。於是：
#
#     est_yield = (eps × (avg_div / price)) / price × 100     ← price 出現兩次
#
# 實機 2330 對帳：avg_div=13.70、price=2320 ⇒ 誤傳 payout=0.0059
#   ⇒ est_div ≈ EPS_ttm × 0.0059 ≈ 0.35 元 ⇒ est_yield ≈ 0.01%（畫面值）
#   真值 13.70 / 2320 × 100 = 0.59%      ⇒ 低估約 40 倍（＝ price/eps_ttm 倍）
# 0.01% 會落進「🔴 超貴（<3%）」，是個由量綱錯誤生出來的**假結論**。
#
# 修法選擇：改函式契約收「年均現金股利（元）」，而不是在 caller 端補傳
# `avg_div / eps_ttm`。理由：
#   1. §2.1 SSOT — 配息的權威值是 `fetch_dividend_data` 實際抓到的現金股利
#      金額；`eps × payout` 只是它的二次推估。既然真值在手，不繞 EPS。
#   2. 同頁 B 區 357（`section_357_valuation` → `classify_stock_357_price`）
#      用的就是 avg_div，改成同一個輸入後，兩處**由建構保證一致**，
#      而不是「代數上剛好等價」（payout>1 被 clamp、EPS≤0 時就會分岔）。
#   3. 少一個外部輸入 = 少一個可以再次接錯的介面。
# 分級不再自己寫 if-elif，直接委派 `classify_stock_357_price`（同一 SSOT），
# 本函式只負責把 zone code 映射成 v5 卡片的 UX 措辭。
# ══════════════════════════════════════════════════════════════════════════════
def calc_dividend_yield_357(price: float, *,
                            avg_div_twd: Optional[float],
                            div_years: Optional[int] = None) -> dict:
    """存股殖利率 + 357 位階判定（與 B 區 357 同一 SSOT）。

    Args:
        price:       現價（元）
        avg_div_twd: 近 N 年**平均年現金股利（元／股）** — 注意是金額，不是
                     配發率、也不是殖利率。參數名帶 `_twd` 即為 §4.1 單位標記。
        div_years:   近 5 年實際有配息的年數；`None` = 未知（不臆測穩定性）。

    Note:
        keyword-only 是刻意的 —— 舊版簽章是
        `(price, eps_ttm, avg_payout, div_years)`，若有殘留的位置呼叫，
        會當場 `TypeError` 而不是靜默算出錯 40 倍的數字（§1 Fail Loud）。

    Edge:
        - price ≤ 0 或 avg_div_twd ≤ 0 / None → **未評估**（est_yield=None）。
          §1：不可回 0 —— 0% 會被判成「超貴」，那是拿缺資料當看空結論。

    Returns:
        {est_yield, est_div, p_cheap, p_fair, p_expensive, zone_code,
         div_years, signal, color, msg}
        est_yield 為 None 時代表未評估，caller 必須顯示「未評估」而非數字。
    """
    R = '#da3633'; G = '#2ea043'; Y = TRAFFIC_YELLOW; N = '#484f58'

    # 分級與三檔目標價全部委派 SSOT；'na' 已涵蓋 price/avg_div 缺值或 ≤0
    zone_code, targets = classify_stock_357_price(price, avg_div_twd)
    if zone_code == 'na':
        _why = "無股價" if (not price or price <= 0) else "無配息記錄"
        return {
            "est_yield": None, "est_div": None,
            "p_cheap": None, "p_fair": None, "p_expensive": None,
            "zone_code": "na", "div_years": div_years,
            "signal": "⚪ 未評估", "color": N,
            "msg": f"{_why}，357 殖利率法則不適用（不以 0% 代替，避免誤判為超貴）",
        }

    est_div = float(avg_div_twd)
    est_yield = round(est_div / price * 100, 2)
    p_cheap, p_fair, p_expensive = targets['cheap'], targets['fair'], targets['dear']

    # 近 5 年年年有配 → 視為穩定；div_years 未知時不下穩定性結論（§1）
    stable = (div_years is not None and div_years >= 5)
    _yr_txt = "配息年數未知" if div_years is None else f"近5年配息 {div_years} 年"

    if zone_code == 'cheap' and stable:
        signal, color = "🟢 甜甜價（7%+近5年年年配）", G
        msg = (f"殖利率 {est_yield:.2f}% ≥ {YIELD_HIGH:g}%（便宜價 {p_cheap}）"
               f"且{_yr_txt} — 策略1 存股首選")
    elif zone_code == 'cheap':
        signal, color = "🟢 高殖利率（穩定性待確認）", G
        msg = (f"殖利率 {est_yield:.2f}% ≥ {YIELD_HIGH:g}%（便宜價 {p_cheap}），"
               f"但{_yr_txt}，需確認配息穩定性")
    elif zone_code == 'fair':
        signal, color = f"🟡 合理（{YIELD_MID:g}~{YIELD_HIGH:g}%）", Y
        msg = f"殖利率 {est_yield:.2f}%，位於合理區間（{p_cheap}~{p_fair}），可分批布局"
    elif zone_code == 'dear':
        signal, color = f"🔴 昂貴（{YIELD_LOW:g}~{YIELD_MID:g}%）", R
        msg = f"殖利率 {est_yield:.2f}%，位於昂貴區（{p_fair}~{p_expensive}），持有但不追高"
    else:  # 'overpriced'
        signal, color = f"🔴 超貴（<{YIELD_LOW:g}%）", R
        msg = (f"殖利率僅 {est_yield:.2f}%（現價已高於昂貴價 {p_expensive}），"
               f"估值過高，建議逢高減碼")

    return {
        "est_yield": est_yield, "est_div": round(est_div, 2),
        "p_cheap": p_cheap, "p_fair": p_fair, "p_expensive": p_expensive,
        "zone_code": zone_code, "div_years": div_years,
        "signal": signal, "color": color, "msg": msg,
    }


def count_dividend_paying_years(yearly: Optional[list]) -> Optional[int]:
    """從 `fetch_dividend_data` 的 `yearly`（近 5 年 list[{'year','cash'}]）
    數出「實際有配息的年數」。

    v19.179 B1-b：原 caller 讀 `st.session_state['t2_div_hist']`，但**全站
    沒有任何一行寫入這個 key**（grep 僅 1 個讀取點）⇒ `div_years` 恆為 0
    ⇒ 卡片永遠宣稱「連續配息 0 年」。那是把「沒去查」講成「查到沒有」，
    §1 反捏造。真值就在同一個 caller 已持有的 `yearly2` 裡。

    Returns:
        有配息年數（0~5）；`yearly` 為 None / 形狀不符 → `None`（未知，
        由下游顯示「配息年數未知」，不填 0）。
    """
    if not yearly:
        return None
    try:
        n = 0
        for row in yearly:
            cash = row['cash'] if isinstance(row, dict) else None
            if cash is None:
                return None
            if float(cash) > 0:
                n += 1
        return n
    except (TypeError, ValueError, KeyError) as e:
        # §1：形狀不符不猜 0，回 None 讓 UI 誠實說「未知」
        print(f'[count_dividend_paying_years] yearly 形狀不符，回 None: '
              f'{type(e).__name__}: {e}')
        return None


# ══════════════════════════════════════════════════════════════════════════════
# [Task 12] 動態資產配置建議
# 總經紅燈 → 建議防禦型 ETF 停泊資金
# ══════════════════════════════════════════════════════════════════════════════
DEFENSIVE_ETFS = {
    "00679B": {"name": "元大美債 20年", "type": "長天期美債", "note": "總經高風險首選避風港"},
    "00720B": {"name": "元大投資級債",  "type": "投資級公司債", "note": "中度風險緩衝"},
    "00878":  {"name": "國泰永續高股息","type": "高息防禦股", "note": "景氣下行仍有配息"},
    "006208": {"name": "富邦台50",      "type": "大型權值ETF", "note": "黃燈時降低個股風險"},
}

def get_defensive_allocation(macro_level: str) -> dict:
    """
    依總經燈號給出資金停泊建議。

    Args:
        macro_level: 'High Risk' / 'Medium Risk' / 'Safe'

    Returns: {allocation, etf_recommendations, msg}
    """
    if macro_level == "High Risk":
        return {
            "stock_pct": 20, "bond_pct": 60, "cash_pct": 20,
            "etf_recommendations": ["00679B", "00720B"],
            "msg": "🚨 總經紅燈：建議股票部位降至 20%，60% 轉入長天期美債 ETF（00679B）停泊，20% 保留現金備戰"
        }
    elif macro_level == "Medium Risk":
        return {
            "stock_pct": 50, "bond_pct": 30, "cash_pct": 20,
            "etf_recommendations": ["00720B", "006208"],
            "msg": "⚠️ 總經黃燈：股票降至 50%，30% 轉入投資級債 ETF，20% 現金等候回補機會"
        }
    else:
        return {
            "stock_pct": 80, "bond_pct": 10, "cash_pct": 10,
            "etf_recommendations": [],
            "msg": "✅ 總經安全：可積極佈局，維持 80% 股票部位，10% 債券避險，10% 現金備戰"
        }


# ══════════════════════════════════════════════════════════════════════════════
# [Step 6] 自動化邊界測試
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("src/compute/strategy/v5_modules.py 自動化邊界測試")
    print("=" * 60)

    import traceback

    # ── Task 5: 財報領先
    print("\n[Task 5] 財報領先指標")
    try:
        r = analyze_fundamental_leading(5e9, 2e9, 8e9, 3e9, 10e9)
        print(f"  {r['signal']}: {r['msg'][:50]}  ✅")
        r2 = analyze_fundamental_leading(None, None, None, None, None)
        assert r2['cl_yoy'] is None
        print(f"  無資料防禦: {r2['signal']}  ✅")
    except Exception as e:
        print(f"  ❌ {e}"); traceback.print_exc()

    # ── Task 6: RS 相對強度
    print("\n[Task 6] RS 相對強度")
    try:
        dates = pd.date_range('2024-01-01', periods=150)
        df_s = pd.DataFrame({'close': 100 * (1 + np.random.randn(150).cumsum()*0.01)}, index=dates)
        df_m = pd.DataFrame({'close':  50 * (1 + np.random.randn(150).cumsum()*0.01)}, index=dates)
        r = calc_relative_strength(df_s, df_m)
        print(f"  {r['signal']}: RS={r['avg_rs']}  ✅")
        # 邊界：資料不足
        r2 = calc_relative_strength(df_s.head(5), df_m)
        print(f"  資料不足防禦: {r2['signal']}  ✅")
    except Exception as e:
        print(f"  ❌ {e}"); traceback.print_exc()

    # ── Task 7: 估值河流圖
    print("\n[Task 7] 估值河流圖")
    try:
        r = calc_valuation_zone(100, 8, 60, 12, 3, 1.5, 0.3)
        print(f"  {r['signal']}: PE={r['pe']}  ✅")
        r2 = calc_valuation_zone(100, -1, 60, 12, 3, 1.5, 0.3)
        assert r2['pe'] is None
        print(f"  EPS<0防禦: pe={r2['pe']}  ✅")
    except Exception as e:
        print(f"  ❌ {e}"); traceback.print_exc()

    # ── Task 9: 布林爆發
    print("\n[Task 9] 布林帶寬偵測")
    try:
        df_bb = pd.DataFrame({'close': [100]*15 + list(100+np.random.randn(25)*2),
                              'volume': np.random.randint(1000, 5000, 40)})
        r = detect_bollinger_breakout(df_bb)
        print(f"  {r['signal']}: BW={r['bw']}%  ✅")
        r2 = detect_bollinger_breakout(df_bb.head(5))
        print(f"  資料不足防禦: {r2['signal']}  ✅")
    except Exception as e:
        print(f"  ❌ {e}"); traceback.print_exc()

    # ── Task 10: 存股殖利率(v19.179 B1-b:改收「年均現金股利(元)」)
    print("\n[Task 10] 存股殖利率 357")
    try:
        r = calc_dividend_yield_357(100, avg_div_twd=8.0, div_years=5)
        print(f"  {r['signal']}: Y={r['est_yield']}%  ✅")   # 8/100 = 8% → 甜甜價
        r2 = calc_dividend_yield_357(0, avg_div_twd=8.0, div_years=5)
        print(f"  Price=0防禦: {r2['signal']} est_yield={r2['est_yield']}  ✅")
        r3 = calc_dividend_yield_357(100, avg_div_twd=0, div_years=None)
        print(f"  無配息防禦: {r3['signal']} est_yield={r3['est_yield']}  ✅")
        r4 = calc_dividend_yield_357(2320, avg_div_twd=13.70, div_years=5)
        print(f"  2330 對帳: Y={r4['est_yield']}%(應 0.59) {r4['signal']}  ✅")
        print(f"  配息年數: {count_dividend_paying_years([{'year': 2024, 'cash': 3.0}])}  ✅")
    except Exception as e:
        print(f"  ❌ {e}"); traceback.print_exc()

    # ── Task 12: 動態配置
    print("\n[Task 12] 動態資產配置")
    try:
        for level in ["High Risk", "Medium Risk", "Safe"]:
            r = get_defensive_allocation(level)
            print(f"  {level}: 股{r['stock_pct']}%/債{r['bond_pct']}%  ✅")
    except Exception as e:
        print(f"  ❌ {e}"); traceback.print_exc()

    print("\n" + "=" * 60)
    print("v5_modules 邊界測試完成")
    print("=" * 60)
