"""src/ui/tabs/tab_macro.py 共用純函式 — Phase 7A-Ext（2026-05-16）。

零 Streamlit / Plotly 依賴，純資料計算。從 tab_macro.render_tab_macro
抽出供 unit test 與未來模組共用。

設計原則：
- pure function：相同輸入恆等輸出
- 防呆優先：所有 helper 對 None / 空 dict / 缺欄位皆有 fallback
- 易測：對應 tests/test_macro_helpers.py 完整 coverage
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
# v18.241 E1+E2: 抽 inline magic 到 shared SSOT（CLAUDE.md §3.3）
from shared.signal_thresholds import (
    HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE, HEALTH_FNET_BONUS, CONFIDENCE_SOURCE_COUNT,
)

# 季末日對照（DataFrame 內「季度標籤 2024Q4」→「2024-12-31」用）
_QE_MAP = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}

# v18.140 校準收斂門檻：health 低於此值觸發 🔴 防禦；regime=bull 需 score ≥ 此值才升 🟢
# v18.143+：優先讀 macro_thresholds.json（由季度 recalibrate workflow 經 PR 審閱後寫入），
# 缺檔則 fall back 至模組預設常數
# S-GRAY-1 v18.244:loader I/O 已下沉 `shared/macro_calibration.py`(L0 Infra),
# 本檔僅做 module-level call 後 expose 常數,符合 L2 「純函式 / 無 I/O」邊界。
from shared.macro_calibration import load_calibrated_thresholds as _load_calibrated_thresholds

HEALTH_DEFENSE_THRESHOLD, BULL_MIN_SCORE = _load_calibrated_thresholds()


def calc_traffic_light(
    mkt_info: Optional[dict],
    jingqi_info: Optional[dict],
    cl_data: Optional[dict],
    li_latest: Any,
    *,
    health_defense_threshold: Optional[int] = None,
    bull_min_score: Optional[int] = None,
) -> Optional[dict]:
    """根據當前數據計算紅綠燈狀態，回傳 dict。無數據時回傳 None。

    取代 tab_macro.render_tab_macro._calc_traffic_light closure。

    決策樹（v18.140 校準後收斂門檻，常數見模組 HEALTH_DEFENSE_THRESHOLD / BULL_MIN_SCORE）：
      1. 三來源全空 → None（由 placeholder 顯示等待）
      2. defense 觸發（score<2 且外資期貨大空單）或 health<HEALTH_DEFENSE_THRESHOLD → 🔴 空頭防禦
      3. regime=='bull' AND score>=BULL_MIN_SCORE → 🟢 多頭積極
      4. regime in ('caution','bear') → 🔴 保守防禦
      5. 其他 → 🟡 震盪整理

    Args:
        mkt_info:    market_regime() 回傳，含 'score' / 'regime'
        jingqi_info: 景氣指標，含 'avg'
        cl_data:     籌碼資料，含 'inst'（外資 net）/ 'adl'
        li_latest:   先行指標 DataFrame，含 '外資大小' / '韭菜指數' 欄

    Returns:
        dict (color, icon, label, action, sub, health, defense,
              score, jqavg, leek, fnet, fk, fut_net, conf, regime) 或 None
    """
    if not mkt_info and not jingqi_info and not cl_data:
        return None
    _mkt    = mkt_info   or {}
    _jq     = jingqi_info or {}
    _cd     = cl_data    or {}
    _score  = _mkt.get('score', 0)
    _jqavg  = _jq.get('avg', 50)
    _inst   = _cd.get('inst', {})
    _fk     = next((k for k in _inst if '外資' in k), None)
    _fnet   = _inst.get(_fk, {}).get('net', 0) if _fk else 0

    # 先行指標：期貨外資大小、韭菜指數
    _fut_net = 0
    _leek = 50
    if li_latest is not None and not li_latest.empty:
        if '外資大小' in li_latest.columns:
            try:
                _fut_net = float(li_latest.iloc[-1].get('外資大小', 0))
            except Exception:
                pass
        if '韭菜指數' in li_latest.columns:
            try:
                _leek = float(li_latest.iloc[-1].get('韭菜指數', 50))
            except Exception:
                pass

    _regime  = _mkt.get('regime', 'neutral')
    # v18.436 #3:外資期貨防禦門檻 SSOT 化
    from shared.signal_thresholds import FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
    _defense = (_score < 2 and abs(_fut_net) > FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
                and _fut_net < 0)
    # v18.241 E1: 健康評分權重從 SSOT 引入（原 0.4/0.4/20 inline）
    # v19.102 校準採納(方案 B,MACRO_HEALTH_WEIGHT_PROPOSAL.md AUC 0.753):
    # ① 權重 0.6/0.4/0(SSOT 已改);② score 正規化除數自 CONFIDENCE_SOURCE_COUNT(5,
    # 借用錯配)改用 market_regime 回傳的真 max_score(預設 4.0 = market_regime 基本
    # 滿分,ad_ratio/m1b_m2 有傳才升 5/6)— 修「預設模式 score 永遠到不了 100」。
    _max_score = float(_mkt.get('max_score') or 4.0)
    _health  = round(
        _jqavg * HEALTH_WEIGHT_JQ
        + min(_score / _max_score * 100, 100) * HEALTH_WEIGHT_SCORE
        + (HEALTH_FNET_BONUS if _fnet > 0 else 0), 1
    )

    # R-CALC-4 v18.412:Method A ↔ Method B 雙演算法對帳(§4.3)
    # 嵌入 production render 路徑(原只在 reconcile_panel diagnostic page);
    # drift_warning / extreme_divergence 走 stderr log,**不改 UI 行為**(觀測性升級)。
    try:
        from src.compute.health.health_reconcile import reconcile_health_score as _reconcile
        _rec = _reconcile(_health, jqavg=_jqavg, score=_score, fnet=_fnet,
                          max_score=_max_score)
        if not _rec.within_tolerance:
            import sys as _sys_rec
            print(f'[health_reconcile] {_rec.reason} '
                  f'method_a={_rec.method_a} method_b={_rec.method_b:.1f} '
                  f'diff={_rec.diff:+.1f} abs_diff={_rec.abs_diff:.1f}',
                  file=_sys_rec.stderr)
    except Exception as _e_rec:
        # 對帳失敗不影響主路徑(§1 fail loud 範圍外:這是觀測性,主邏輯仍走 Method A)
        try:
            import sys as _sys_rec_err
            print(f'[health_reconcile] swallow: {type(_e_rec).__name__}: {_e_rec}',
                  file=_sys_rec_err.stderr)
        except Exception:
            pass

    # 校準腳本可注入測試門檻；正式呼叫不傳 → 用模組常數
    _h_thr = health_defense_threshold if health_defense_threshold is not None else HEALTH_DEFENSE_THRESHOLD
    _s_thr = bull_min_score if bull_min_score is not None else BULL_MIN_SCORE

    if _defense or _health < _h_thr:
        _color, _icon  = TRAFFIC_RED, '🔴'
        _label  = '空頭防禦｜降低部位'
        _action = '⛔ 大環境惡化，系統已啟動資金保護機制'
        _sub    = '建議持有現金，等待市場明確訊號，禁止追買任何個股'
    elif _regime == 'bull' and _score >= _s_thr:
        _color, _icon  = TRAFFIC_GREEN, '🟢'
        _label  = '多頭市場｜積極操作'
        _action = '✅ 市場健康，籌碼乾淨，可積極尋找強勢標的'
        _sub    = '可積極尋找強勢標的，留意趨勢延續性'
    elif _regime in ('caution', 'bear'):
        _color, _icon  = TRAFFIC_RED, '🔴'
        _label  = '保守防禦｜縮減部位'
        _action = '⛔ 市場走弱，建議縮減持股比例，等待多頭確認'
        _sub    = '降低風險暴露，避免新開倉，等待多頭重啟'
    else:
        _color, _icon  = TRAFFIC_YELLOW, '🟡'
        _label  = '震盪整理｜謹慎觀望'
        _action = '⚠️ 市場處於整理期，謹慎操作，降低部位'
        _sub    = '持有現有倉位觀望，不追高，等待更明確信號'

    _conf_sources = [
        ('大盤趨勢評分 (market_regime)', bool(mkt_info)),
        ('旌旗指數 (站上均線比例)',       bool(jingqi_info)),
        ('外資買賣超 (三大法人)',         bool(_fk)),
        ('先行指標 (期貨/PCR/韭菜)',      bool(li_latest is not None and not li_latest.empty)),
        ('ADL 騰落指標',                  bool(_cd.get('adl') is not None)),
    ]
    # v18.241 E2: confidence 分子分母從 SSOT 引入
    _conf = round(sum(_ok for _, _ok in _conf_sources) / CONFIDENCE_SOURCE_COUNT * 100)
    _missing = [_name for _name, _ok in _conf_sources if not _ok]
    return {
        'color': _color, 'icon': _icon, 'label': _label,
        'action': _action, 'sub': _sub, 'health': _health,
        'defense': _defense, 'score': _score, 'jqavg': _jqavg,
        'leek': _leek, 'fnet': _fnet, 'fk': _fk, 'fut_net': _fut_net,
        'conf': _conf, 'missing_sources': _missing, 'regime': _regime,
    }


def rp_ts(df: Any) -> str:
    """取 DataFrame 最新日期字串（與 _reg_add 邏輯一致）。

    支援來源（依序嘗試）：
      1. DatetimeIndex → 直接取 max
      2. 「季度標籤」欄（'2024Q4' → '2024-12-31'，依 _QE_MAP）
      3. 「年度」欄（int → 'YYYY-12-31'）
      4. _date / date / datetime / timestamp / 日期 / quarter / period 欄
         （_date 強制 '%Y%m%d' format，其他自動推斷）

    任何例外或無法解析 → 回 'N/A'。
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 'N/A'
    if isinstance(df.index, pd.DatetimeIndex):
        try:
            return pd.Timestamp(df.index.max()).strftime('%Y-%m-%d')
        except Exception:
            pass
    for c in df.columns:
        cl = str(c)
        cll = cl.lower()
        if cl == '季度標籤':
            try:
                lq = str(df[c].dropna().iloc[-1])
                yr_q, qn = lq.split('Q')
                return f'{yr_q}-{_QE_MAP.get(qn, "12-31")}'
            except Exception:
                pass
        if cl == '年度':
            try:
                yr = int(df[c].dropna().iloc[-1])
                return f'{yr}-12-31'
            except Exception:
                pass
        fmt = '%Y%m%d' if cll == '_date' else None
        if cll in ('_date', 'date', 'datetime', 'timestamp', '日期', 'quarter', 'period'):
            try:
                lat = pd.to_datetime(df[c], format=fmt, errors='coerce').max()
                if lat is not None and not pd.isna(lat):
                    return lat.strftime('%Y-%m-%d')
            except Exception:
                pass
    return 'N/A'


def rp_entry(df: Any, cat: str, freq: str) -> dict:
    """DataFrame → registry entry dict（last_updated + rows + cat + freq）。

    空 / None → missing=True；有資料 → 用 rp_ts 取最後日期。
    """
    if isinstance(df, pd.DataFrame) and not df.empty:
        return {'last_updated': rp_ts(df), 'rows': len(df), 'category': cat, 'frequency': freq}
    return {'last_updated': 'N/A', 'rows': 0, 'category': cat, 'frequency': freq, 'missing': True}


def rp_scalar(val: Any, cat: str, freq: str, proxy_date: str) -> dict:
    """純量值（健康度評分 / RSI / 殖利率等）→ registry entry dict。

    有值（非 None）→ rows=1 + last_updated=proxy_date（呼叫端傳入今天或總經更新時間）
    None → missing=True。
    """
    if val is not None:
        return {'last_updated': proxy_date, 'rows': 1, 'category': cat, 'frequency': freq}
    return {'last_updated': 'N/A', 'rows': 0, 'category': cat, 'frequency': freq, 'missing': True}


# v18.169: CPI × Fed Funds 雙頂回落 — 純函式 helper
# ── v19.173 正名(命名不實技術債)──────────────────────────────────────────
# 原名 `detect_mk_golden_inflection`,UI 顯示「MK 黃金拐點」。
# 「MK」在統計文獻是 Mann-Kendall 的通用縮寫,而本函式**不是** Mann-Kendall:
#   它只做「本月 vs 上月」兩點差分 + 固定門檻,沒有 S 統計量、沒有 Var(S)、
#   沒有 Z、沒有 p-value、也沒有 tie 修正(全 repo `grep -i mann` = 0 hit)。
# 舊名會讓讀者以為這條規則有無母數趨勢檢定背書 → 誇大確信度,故正名。
# (v19.174 去識別化前,本 repo 別處的「MK」曾指某 ETF 存股框架的作者代號,兩者撞名更添誤讀;
#  該處已一併改為「存股框架」中性描述。)
# 真正的 Mann-Kendall 實作見 `shared/mk_test.py::mann_kendall`,
# 用於 UI 上的**並列佐證**;本函式的判定邏輯 v19.173 一律不動(零行為變更)。
def detect_cpi_fed_double_top(
    cpi_yoy: Optional[float],
    cpi_prev_yoy: Optional[float],
    fed_rate: Optional[float],
    fed_prev_rate: Optional[float],
) -> Optional[dict]:
    """CPI YoY × Fed Funds Rate「雙頂回落」偵測（鏡像 fund _detect_inflection）。

    ⚠️ 這是什麼 / 不是什麼（v19.173 誠實揭露）
    ------------------------------------------
    **是**：對「最新月」與「上一月」兩個純量做差分，再比對固定 ppt 門檻的
            經驗規則。輸入只有 4 個數字，沒有時間序列。
    **不是**：Mann-Kendall 無母數趨勢檢定。本函式沒有 S 統計量、沒有 Var(S)、
            沒有 Z、沒有 p-value、沒有 tie 修正，也沒有做任何顯著性宣稱。
            若需要真正的趨勢檢定，請用 `shared.mk_test.mann_kendall()`
            （它吃整條序列，回 Z / p / Sen's slope）。
    ⚠️ v19.173 現況：兩者**尚未**在 UI 並列 —— `mann_kendall()` 目前
    **零 production caller**。原因是 `macro_snapshot.fetch_cpi_block()` /
    `fetch_fed_funds_block()` 只回「本月 + 上月」兩個純量，全 repo 沒有
    CPI/Fed 的歷史序列可餵給檢定（n=2 時 `mann_kendall()` 本來就回 None）。
    **規劃**是等序列 fetcher 到位後並列呈現：本規則負責「拐點事件」判讀、
    Mann-Kendall 負責「這段期間有沒有統計上的趨勢」佐證，**互不覆寫**。
    接序列屬新資料流，§7 需先對齊 endpoint／單位／發布延遲／PIT 鍵
    （FRED CPI 必須用 release_date 而非 observation_date）。

    參數
    ----
    cpi_yoy        : 最新月度美國核心 CPI 年增率（%）
    cpi_prev_yoy   : 上月度美國核心 CPI 年增率（%）
    fed_rate       : 最新月度 Fed Funds Rate（%，月均有效利率）
    fed_prev_rate  : 上月度 Fed Funds Rate（%）

    回傳
    ----
    None  — 資料不足（任一參數為 None）或無訊號
    dict  — {'label', 'icon', 'color', 'detail', 'strength'}
            strength: 'strong'（雙明確回落）/ 'weak'（CPI 弱降+Fed 持平）

    判讀規則（防雜訊：±0.05ppt 視為持平）
    --------
    - CPI 月降 ≥ 0.2ppt AND Fed 持平或月降      → ⭐ 強訊號（CPI×Fed 雙頂回落）
    - CPI 月降 ∈ [0.05, 0.2)ppt AND Fed 持平或月降 → ✅ 弱訊號（回落觀察中）
    - 任一上升 (> 0.05ppt) 或 CPI 未降          → None（無訊號）
    """
    if cpi_yoy is None or cpi_prev_yoy is None:
        return None
    if fed_rate is None or fed_prev_rate is None:
        return None

    try:
        cpi_delta = float(cpi_yoy) - float(cpi_prev_yoy)      # 負值 = 通膨降溫
        fed_delta = float(fed_rate) - float(fed_prev_rate)    # 負/零 = 降息或暫停
    except (TypeError, ValueError):
        return None

    # 任一指標明確上升 → 無訊號
    if cpi_delta > 0.05 or fed_delta > 0.05:
        return None
    # CPI 須至少出現降溫（>= 0.05ppt 月降）
    if cpi_delta > -0.05:
        return None

    _fed_desc = '持平' if abs(fed_delta) < 0.05 else f'月降 {abs(fed_delta):.2f}ppt'

    if cpi_delta <= -0.2:
        return {
            # v19.173 正名:原 'MK 黃金拐點 ⭐'(見上方函式註解:MK ≠ Mann-Kendall)
            'label': 'CPI×Fed 雙頂回落 ⭐',
            'icon': '⭐',
            'color': TRAFFIC_GREEN,
            'detail': (
                f'核心 CPI {cpi_prev_yoy:+.2f}% → {cpi_yoy:+.2f}% '
                f'（月降 {abs(cpi_delta):.2f}ppt） + Fed Funds '
                f'{fed_prev_rate:.2f}% → {fed_rate:.2f}% （{_fed_desc}） '
                f'→ ⭐ 通膨+利率雙頂回落，景氣多頭最佳買點（歷史勝率最高）'
            ),
            'strength': 'strong',
        }
    return {
        # v19.173 正名:原 'MK 拐點觀察中'
        'label': 'CPI×Fed 回落觀察中',
        'icon': '✅',
        'color': TRAFFIC_YELLOW,
        'detail': (
            f'核心 CPI {cpi_prev_yoy:+.2f}% → {cpi_yoy:+.2f}% + '
            f'Fed Funds {fed_prev_rate:.2f}% → {fed_rate:.2f}% '
            f'→ 通膨初步降溫，待 CPI 加速回落或 Fed 確認暫停升息'
        ),
        'strength': 'weak',
    }


# ── v19.173 向後相容 alias（DEPRECATED，勿用於新程式碼）────────────────────
# 舊名 `detect_mk_golden_inflection` 命名不實（「MK」= Mann-Kendall 的通用縮寫，
# 但本規則只是兩點差分）。正名後保留 alias 是為了**不破壞既有 caller**。
# v19.173 當下仍以舊名呼叫的地方（全 repo 掃描結果）：
#   - src/ui/tabs/macro/section_long_term.py:43  （長期 regime 的 mk_signal 輸入）
#     ← 該檔本輪不在授權改動範圍內，故 alias 不刪。
#   - tests/test_macro_helpers.py                 （刻意保留，兼測 alias 未斷）
# 已遷移到新名的：src/ui/tabs/macro/section_state.py（拐點面板第 7 項）。
# 新程式碼一律改用 `detect_cpi_fed_double_top`；待全部 caller 遷移完成後移除本行。
detect_mk_golden_inflection = detect_cpi_fed_double_top


# v18.170: 長期總經位階分類（12M 視角，景氣大循環）— 純函式 helper
def _safe_float(x: Any) -> Optional[float]:
    """容錯轉浮點：None/字串/NaN → None。"""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN guard
        return None
    return f


def classify_long_term_regime(
    cpi_yoy: Any,
    fed_rate: Any,
    fed_prev_rate: Any,
    ndc_score: Any,
    pmi: Any,
    mk_signal: Optional[dict] = None,
) -> dict:
    """長期總經位階判讀（12M 視角，景氣大循環）。

    參數
    ----
    cpi_yoy        : 美國核心 CPI YoY（%）
    fed_rate       : 最新 Fed Funds Rate（%）
    fed_prev_rate  : 上月 Fed Funds Rate（%）
    ndc_score      : 台灣景氣對策信號分數（9-45）
    pmi            : 台灣製造業 PMI 指數（CIER）
    mk_signal      : detect_cpi_fed_double_top() 回傳值（None 或 dict）
                     ⚠️ v19.173：參數名維持 `mk_signal` 是為了不破壞既有
                     keyword caller（section_long_term.py:66）；語意上它是
                     「CPI×Fed 雙頂回落」訊號，**與 Mann-Kendall 無關**。

    回傳
    ----
    dict 含 regime / score / color / detail / suggest_pct / components
    components 為 list[tuple(name, score_pts, weight_pct)]，便於 UI 拆解顯示

    評分（每項 ∈ [-2, +2]，加權加總）
    --------
    - CPI YoY (25%)：≤2%+2 / 2-3%+1 / 3-4% 0 / 4-5%-1 / ≥5%-2
    - Fed 方向 (20%)：月降+2 / 持平+1 / 月升-2
    - NDC (20%)：紅(≥38)+2 / 黃紅(32-37)+1 / 綠(23-31) 0 / 黃藍(17-22)-1 / 藍(<17)-2
    - PMI (20%)：≥55+2 / 52-55+1 / 50-52 0 / 48-50-1 / <48-2
    - CPI×Fed 雙頂 (15%)：⭐強+2 / ✅弱+1 / None 0（v19.173 正名，原「MK 拐點」）
    """
    cpi_v = _safe_float(cpi_yoy)
    fed_v = _safe_float(fed_rate)
    fed_p = _safe_float(fed_prev_rate)
    ndc_v = _safe_float(ndc_score)
    pmi_v = _safe_float(pmi)

    components: list = []
    weighted_sum = 0.0
    weight_total = 0.0

    # 1. CPI YoY 趨勢（25%）
    if cpi_v is not None:
        if cpi_v <= 2.0:
            cpi_pts = 2
        elif cpi_v <= 3.0:
            cpi_pts = 1
        elif cpi_v <= 4.0:
            cpi_pts = 0
        elif cpi_v <= 5.0:
            cpi_pts = -1
        else:
            cpi_pts = -2
        components.append(('美 CPI YoY', cpi_pts, 25))
        weighted_sum += cpi_pts * 25
        weight_total += 25

    # 2. Fed Funds 方向（20%）
    if fed_v is not None and fed_p is not None:
        fed_delta = fed_v - fed_p
        if fed_delta < -0.05:
            fed_pts = 2
        elif fed_delta <= 0.05:
            fed_pts = 1
        else:
            fed_pts = -2
        components.append(('Fed 方向', fed_pts, 20))
        weighted_sum += fed_pts * 20
        weight_total += 20

    # 3. NDC 景氣對策（20%）
    if ndc_v is not None:
        if ndc_v >= 38:
            ndc_pts = 2
        elif ndc_v >= 32:
            ndc_pts = 1
        elif ndc_v >= 23:
            ndc_pts = 0
        elif ndc_v >= 17:
            ndc_pts = -1
        else:
            ndc_pts = -2
        components.append(('NDC 景氣燈號', ndc_pts, 20))
        weighted_sum += ndc_pts * 20
        weight_total += 20

    # 4. PMI 水準（20%）
    if pmi_v is not None:
        if pmi_v >= 55:
            pmi_pts = 2
        elif pmi_v >= 52:
            pmi_pts = 1
        elif pmi_v >= 50:
            pmi_pts = 0
        elif pmi_v >= 48:
            pmi_pts = -1
        else:
            pmi_pts = -2
        components.append(('台 PMI', pmi_pts, 20))
        weighted_sum += pmi_pts * 20
        weight_total += 20

    # 5. CPI×Fed 雙頂回落訊號（15%）— 僅當至少一個主指標存在時才計入
    # v19.173 正名：原「MK 黃金拐點」。components 目前無 production render
    # （v18.190 已移除雙視角 UI 區塊，僅 _lt['score'] / ['regime'] 被下游取用），
    # 故改名不影響任何畫面；改的是未來讀 code 的人不會再被「MK」誤導。
    if weight_total > 0:
        if mk_signal is not None and isinstance(mk_signal, dict):
            _s = mk_signal.get('strength')
            mk_pts = 2 if _s == 'strong' else (1 if _s == 'weak' else 0)
        else:
            mk_pts = 0
        components.append(('CPI×Fed 雙頂', mk_pts, 15))
        weighted_sum += mk_pts * 15
        weight_total += 15

    if weight_total == 0:
        return {
            'regime': '⚪ 資料不足',
            'score': 0.0,
            'color': '#8b949e',
            'detail': '所有長期指標皆缺失，無法判讀',
            'suggest_pct': 'N/A',
            'components': components,
        }

    score = weighted_sum / weight_total  # ∈ [-2, +2]

    if score >= 1.0:
        regime, color, suggest = '🟢 成長期', TRAFFIC_GREEN, '80%+'
        detail = '景氣擴張+通膨溫和+資金寬鬆 → 多頭主升段，可積極做多'
    elif score >= 0.0:
        regime, color, suggest = '🔵 復甦期', '#58a6ff', '60-80%'
        detail = '景氣由谷底回升 → 加碼基本面好的標的，留意通膨變化'
    elif score >= -1.0:
        regime, color, suggest = '🟡 過熱/震盪期', TRAFFIC_YELLOW, '40-60%'
        detail = '景氣高檔震盪或通膨壓力 → 謹慎觀望，等待方向確認'
    else:
        regime, color, suggest = '🔴 衰退期', TRAFFIC_RED, '<30%'
        detail = '景氣下行+通膨壓力或政策緊縮 → 保守減倉，現金為王'

    return {
        'regime': regime,
        'score': round(score, 2),
        'color': color,
        'detail': detail,
        'suggest_pct': suggest,
        'components': components,
    }


# v18.170: 短期總經分類（1Q 視角，對齊台股財報季）— 純函式 helper
def classify_short_term_regime(
    export_yoy: Any,
    pmi: Any,
    vix_current: Any,
    fi_streak_days: Any,
    cpi_yoy: Any,
    cpi_prev_yoy: Any,
) -> dict:
    """短期總經偏向判讀（1Q 視角，對齊台股財報季 Q1/Q2/Q3/Q4）。

    參數
    ----
    export_yoy      : 台灣出口 YoY（%）
    pmi             : 台灣製造業 PMI（CIER 指數）
    vix_current     : VIX 收盤
    fi_streak_days  : 外資連續買賣超天數（+正=連買，負=連賣）
    cpi_yoy         : 美 CPI YoY（%）
    cpi_prev_yoy    : 上月 CPI YoY（%）

    回傳
    ----
    dict 含 regime / score / color / detail / action / components

    評分（每項 ∈ [-2, +2]，加權加總）
    --------
    - 出口 YoY (25%)：≥15%+2 / 5-15%+1 / 0-5% 0 / -5-0%-1 / <-5%-2
    - PMI 水準 (25%)：≥55+2 / 52-55+1 / 50-52 0 / 48-50-1 / <48-2
    - VIX 水準 (15%)：<15+2 / 15-20+1 / 20-25 0 / 25-30-1 / ≥30-2
    - 外資連續 (20%)：連買≥5+2 / 1-4+1 / 0 0 / 連賣1-4-1 / 連賣≥5-2
    - CPI 月降 (15%)：降≥0.3+2 / 0.1-0.3+1 / ±0.1 0 / 升0.1-0.3-1 / 升≥0.3-2
    """
    exp_v = _safe_float(export_yoy)
    pmi_v = _safe_float(pmi)
    vix_v = _safe_float(vix_current)
    fi_v  = _safe_float(fi_streak_days)
    cpi_v = _safe_float(cpi_yoy)
    cpi_p = _safe_float(cpi_prev_yoy)

    components: list = []
    weighted_sum = 0.0
    weight_total = 0.0

    # 1. 出口 YoY（25%）
    if exp_v is not None:
        if exp_v >= 15:
            exp_pts = 2
        elif exp_v >= 5:
            exp_pts = 1
        elif exp_v >= 0:
            exp_pts = 0
        elif exp_v >= -5:
            exp_pts = -1
        else:
            exp_pts = -2
        components.append(('出口 YoY', exp_pts, 25))
        weighted_sum += exp_pts * 25
        weight_total += 25

    # 2. PMI 水準（25%）
    if pmi_v is not None:
        if pmi_v >= 55:
            pmi_pts = 2
        elif pmi_v >= 52:
            pmi_pts = 1
        elif pmi_v >= 50:
            pmi_pts = 0
        elif pmi_v >= 48:
            pmi_pts = -1
        else:
            pmi_pts = -2
        components.append(('台 PMI', pmi_pts, 25))
        weighted_sum += pmi_pts * 25
        weight_total += 25

    # 3. VIX 水準（15%）
    if vix_v is not None:
        if vix_v < 15:
            vix_pts = 2
        elif vix_v < 20:
            vix_pts = 1
        elif vix_v < 25:
            vix_pts = 0
        elif vix_v < 30:
            vix_pts = -1
        else:
            vix_pts = -2
        components.append(('VIX 波動', vix_pts, 15))
        weighted_sum += vix_pts * 15
        weight_total += 15

    # 4. 外資連續日數（20%）
    if fi_v is not None:
        if fi_v >= 5:
            fi_pts = 2
        elif fi_v >= 1:
            fi_pts = 1
        elif fi_v > -1:
            fi_pts = 0
        elif fi_v > -5:
            fi_pts = -1
        else:
            fi_pts = -2
        components.append(('外資籌碼', fi_pts, 20))
        weighted_sum += fi_pts * 20
        weight_total += 20

    # 5. CPI 月降幅（15%）
    if cpi_v is not None and cpi_p is not None:
        cpi_delta = cpi_v - cpi_p   # 負值 = 通膨降溫
        if cpi_delta <= -0.3:
            cpi_pts = 2
        elif cpi_delta <= -0.1:
            cpi_pts = 1
        elif cpi_delta <= 0.1:
            cpi_pts = 0
        elif cpi_delta <= 0.3:
            cpi_pts = -1
        else:
            cpi_pts = -2
        components.append(('CPI 月降', cpi_pts, 15))
        weighted_sum += cpi_pts * 15
        weight_total += 15

    if weight_total == 0:
        return {
            'regime': '⚪ 資料不足',
            'score': 0.0,
            'color': '#8b949e',
            'detail': '所有短期指標皆缺失，無法判讀',
            'action': 'N/A',
            'components': components,
        }

    score = weighted_sum / weight_total  # ∈ [-2, +2]

    if score >= 0.8:
        regime, color = '⚡ 偏多', TRAFFIC_GREEN
        detail = '下個財報季正向動能 → 加碼績優股、波段佈局好時機'
        action = '建議：擇強做多、留意外資連續買超的個股'
    elif score >= -0.3:
        regime, color = '⚖️ 中性', TRAFFIC_YELLOW
        detail = '訊號分歧或多空交織 → 觀望為主、留意個股輪動'
        action = '建議：區間操作、避免追高殺低、續抱長期持股'
    else:
        regime, color = '⚠️ 偏空', TRAFFIC_RED
        detail = '下個財報季承壓 → 防守為主、現金為王'
        action = '建議：減碼高估值、停利出場、留意外資連續賣超'

    return {
        'regime': regime,
        'score': round(score, 2),
        'color': color,
        'detail': detail,
        'action': action,
        'components': components,
    }


# ════════════════════════════════════════════════════════════════════════════
# v18.270 — TW 央行政策階段衍生函式
# Spec(§7 對齊):純函式無 I/O,搭配 tw_macro.fetch_* 上游
# ════════════════════════════════════════════════════════════════════════════

def calc_real_rate(rate_pct: Optional[float],
                   cpi_yoy_pct: Optional[float]) -> Optional[float]:
    """實質利率(%) = 名目政策利率(%) − CPI YoY(%)。

    Args
    ----
    rate_pct: CBC 重貼現率或銀行間隔夜拆款 (% level)
    cpi_yoy_pct: CPI 年增率 (% YoY)

    Returns
    -------
    float | None
        實質利率;任一輸入為 None / NaN → None(§1 不偽造)。

    Notes
    -----
    經濟學上,實質利率為負(rate < CPI)= 寬鬆;為正且 > 1% = 緊縮。
    """
    if rate_pct is None or cpi_yoy_pct is None:
        return None
    try:
        rr = float(rate_pct) - float(cpi_yoy_pct)
        if pd.isna(rr):
            return None
        return round(rr, 3)
    except (TypeError, ValueError):
        return None


def classify_rate_cycle(rate_series: Optional[pd.Series],
                        lookback_months: int = 6,
                        epsilon: float = 0.05) -> str:
    """依政策利率近 N 月變化分類「升息中 / 持平 / 降息中」。

    Args
    ----
    rate_series: 時間序 % level(date index ascending),最少需 2 筆。
    lookback_months: 比較窗口,預設 6 月(對齊台灣央行季度理監事會節奏)。
    epsilon: 視為「持平」的容差(% pts),預設 0.05% = 5bp。

    Returns
    -------
    str: '🟢 升息中' / '⚪ 持平' / '🔴 降息中' / '⬜ 資料不足'
    """
    if rate_series is None:
        return '⬜ 資料不足'
    try:
        s = pd.Series(rate_series).dropna()
    except (TypeError, ValueError):
        return '⬜ 資料不足'
    if len(s) < 2:
        return '⬜ 資料不足'
    s_tail = s.tail(min(lookback_months, len(s)))
    delta = float(s_tail.iloc[-1]) - float(s_tail.iloc[0])
    if abs(delta) < epsilon:
        return '⚪ 持平'
    return '🟢 升息中' if delta > 0 else '🔴 降息中'


def calc_china_credit_impulse_proxy(m2_series: Optional[pd.Series],
                                    lag_months: int = 12) -> Optional[float]:
    """中國信貸脈衝 proxy:M2 YoY 與 N 月前 M2 YoY 的差(% pts)。

    真正信貸脈衝 = Δ(信貸/GDP),需社融存量 + GDP,無乾淨 FRED 來源;
    M2 YoY 變化是粗略貨幣寬鬆代理。對稱 Fund 端同名函式。

    Args
    ----
    m2_series: M2 YoY % 月頻時間序(date index ascending,**需已 YoY**)。
    lag_months: 比較期,預設 12 月。

    Returns
    -------
    float | None
        正值 = 12 月內 M2 加速(寬鬆中)、負值 = 緊縮中;
        資料不足 N+1 筆 → None(§1 不偽造)。
    """
    if m2_series is None:
        return None
    try:
        s = pd.Series(m2_series).dropna()
    except (TypeError, ValueError):
        return None
    if len(s) < lag_months + 1:
        return None
    cur = float(s.iloc[-1])
    prev = float(s.iloc[-(lag_months + 1)])
    return round(cur - prev, 3)


def calc_twd_trend(usdtwd_series: Optional[pd.Series],
                   window_days: int = 60) -> Optional[dict]:
    """USDTWD 60 日趨勢:回 latest / 60D MA / 斜率(% pts/月)。

    Args
    ----
    usdtwd_series: USD/TWD 日序列(數字越大 = 台幣越貶)。
    window_days: 滾動窗口,預設 60(約 2 個月)。

    Returns
    -------
    dict | None
        {
          'latest': float,                # 最新匯率
          'ma_60d': float | None,         # 60 日均線(資料不足回 None)
          'slope_per_month': float|None,  # 線性斜率 (TWD/USD per 月,正=台幣貶)
          'direction': str,               # '🔴 台幣貶' / '🟢 台幣升' / '⚪ 持平'
        }
        輸入無效回 None。
    """
    if usdtwd_series is None:
        return None
    try:
        s = pd.Series(usdtwd_series).dropna()
    except (TypeError, ValueError):
        return None
    if s.empty:
        return None
    latest = float(s.iloc[-1])
    out: dict = {
        'latest': round(latest, 4),
        'ma_60d': None,
        'slope_per_month': None,
        'direction': '⚪ 持平',
    }
    if len(s) < window_days:
        return out
    tail = s.tail(window_days)
    out['ma_60d'] = round(float(tail.mean()), 4)
    # 線性斜率(per trading day → per month ≈ 21 交易日)
    xs = list(range(len(tail)))
    ys = tail.values
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return out
    slope_per_day = num / den
    slope_per_month = slope_per_day * 21
    out['slope_per_month'] = round(slope_per_month, 4)
    # 月斜率 > 0.1 (~0.3%) 算貶值方向;< -0.1 算升值
    if slope_per_month > 0.1:
        out['direction'] = '🔴 台幣貶'
    elif slope_per_month < -0.1:
        out['direction'] = '🟢 台幣升'
    return out


# ════════════════════════════════════════════════════════════════════════════
# v18.272 — China 副盤(snapshot + sub-score + sub-regime)
# 對稱 Fund v19.114 的 services/macro_service.py 同名函式,演算法 100% 一致
#
# 設計決策(對齊 §-1 + §8.1 step 6):
# - 副盤獨立,**不**接入主 compute_macro_health(避免改變既有評分歷史可信度)
# - 5 因子等權 0.20 each(CLI/PMI/CPI/M2/USDCNY)
# - 4 級 regime + USDCNY > 7.4 fx_alert 獨立 flag
# - 全缺 → return None(§1 fail loud,不偽 50 中性)
# ════════════════════════════════════════════════════════════════════════════

# China zone(對齊 §3.2 合理範圍 + macro_core.MACRO_THRESHOLDS v18.271 5 項)
_CHINA_SUBSCORE_THRESHOLDS = {
    "CHN_CLI":   {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},
    "CHN_BCI":   {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},  # v18.459: renamed from CHN_PMI
    "CHN_CPI":   {"green_low": 1.0, "green_high": 3.0, "yellow_above": 4.0, "red_above": 5.0},
    "CHN_M2":    {"red_below": 5.0, "green_above": 9.0},
    "USDCNY":    {"green_below": 7.0, "yellow_above": 7.2, "red_above": 7.4},
}


def _classify_china_zone(value: Optional[float], rules: dict) -> str:
    """通用 traffic 分類:依 rules dict → 字串。"""
    if value is None or pd.isna(value):
        return "⬜ 無資料"
    v = float(value)
    if "red_above" in rules and v > rules["red_above"]:
        return "🔴 紅"
    if "red_below" in rules and v < rules["red_below"]:
        return "🔴 紅"
    if "yellow_above" in rules and v > rules["yellow_above"]:
        return "🟡 黃"
    if "yellow_below" in rules and v < rules["yellow_below"]:
        return "🟡 黃"
    if "green_above" in rules and v > rules["green_above"]:
        return "🟢 綠"
    if "green_below" in rules and v < rules["green_below"]:
        return "🟢 綠"
    if "green_low" in rules and "green_high" in rules:
        if rules["green_low"] <= v <= rules["green_high"]:
            return "🟢 綠"
    return "⚪ 中性"


def china_macro_snapshot(china_dict: dict) -> dict:
    """組裝 tw_macro.fetch_china_macro 結果為簡單 snapshot。

    Args
    ----
    china_dict: dict[series_id, DataFrame]
        tw_macro.fetch_china_macro() 回傳;每個 DataFrame 含
        [date, value, source, fetched_at] 至少欄位。

    Returns
    -------
    dict 包含 5 個 key:cli/pmi/cpi_yoy/m2_yoy/usdcny,
    每個對應 {"value", "date", "zone", "source"};
    + "credit_impulse_proxy"(M2 YoY 12 月變化,§4.3 衍生)。

    v18.273 校正(§4.1 量綱):
    - `FRED_CHN_M2`(`MABMM301CNM189S`)FRED 回的是 **M3 level (兆 CNY)**,
      非 YoY %。本函式內部先 `pct_change(12) * 100` 轉 YoY 才進 scorer。
    - `m2_yoy["value"]` 為轉換後 YoY %,可直接餵 `_score_china_m2`(門檻 5/9%)
    - `credit_impulse_proxy` 輸入也用 YoY 序列,而非 level
    """
    # SSOT 從 shared/fred_series 引入(對應 tw_macro._china_fred_specs)
    from shared.fred_series import (  # noqa: PLC0415
        FRED_CHN_CPI,
        FRED_CHN_M2,
        FRED_CHN_OECD_CLI,
        FRED_CHN_PMI,
        FRED_USDCNY,
    )

    def _extract(sid: str, threshold_key: str) -> dict:
        df = china_dict.get(sid) if china_dict else None
        out = {"value": None, "date": None, "zone": "⬜ 無資料", "source": None}
        if df is None or df.empty:
            return out
        try:
            last = df.iloc[-1]
            v = float(last["value"])
            d = pd.Timestamp(last["date"]).strftime("%Y-%m-%d")
            out["value"] = round(v, 4)
            out["date"] = d
            out["zone"] = _classify_china_zone(v, _CHINA_SUBSCORE_THRESHOLDS.get(threshold_key, {}))
            out["source"] = str(last.get("source", f"FRED:{sid}"))
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/{sid}] extract 失敗: {e}")
        return out

    # v18.273 校正:M2(實 M3 level)先轉 YoY series 再進 _extract 路徑
    # 避免直接吃 level 餵 _score_china_m2(門檻 5/9%)造成評分恆 100 的 bug
    m2_yoy_df = None
    m2_df_raw = china_dict.get(FRED_CHN_M2) if china_dict else None
    if m2_df_raw is not None and not m2_df_raw.empty:
        try:
            tmp = m2_df_raw.copy()
            # A4 v18.384:抽 shared/calc_helpers.pct_change_yoy SSOT
            from shared.calc_helpers import pct_change_yoy as _pcy
            tmp["value"] = _pcy(tmp["value"].astype(float))
            tmp = tmp.dropna(subset=["value"])
            if not tmp.empty:
                m2_yoy_df = tmp
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/m2_yoy_conv] {e}")

    def _extract_m2_yoy() -> dict:
        out = {"value": None, "date": None, "zone": "⬜ 無資料", "source": None}
        if m2_yoy_df is None:
            return out
        try:
            last = m2_yoy_df.iloc[-1]
            v = float(last["value"])
            d = pd.Timestamp(last["date"]).strftime("%Y-%m-%d")
            out["value"] = round(v, 4)
            out["date"] = d
            out["zone"] = _classify_china_zone(v, _CHINA_SUBSCORE_THRESHOLDS.get("CHN_M2", {}))
            out["source"] = str(last.get("source", f"FRED:{FRED_CHN_M2}"))
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/m2_yoy] {e}")
        return out

    snapshot = {
        "cli":     _extract(FRED_CHN_OECD_CLI, "CHN_CLI"),
        "pmi":     _extract(FRED_CHN_PMI, "CHN_PMI"),
        "cpi_yoy": _extract(FRED_CHN_CPI, "CHN_CPI"),
        "m2_yoy":  _extract_m2_yoy(),
        "usdcny":  _extract(FRED_USDCNY, "USDCNY"),
    }

    # 衍生:信貸脈衝 proxy(M2 YoY 12 月變化)— 用已轉換的 YoY series
    if m2_yoy_df is not None:
        try:
            m2_yoy_series = m2_yoy_df["value"].astype(float)
            snapshot["credit_impulse_proxy"] = calc_china_credit_impulse_proxy(m2_yoy_series)
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/credit_impulse] {e}")
            snapshot["credit_impulse_proxy"] = None
    else:
        snapshot["credit_impulse_proxy"] = None

    return snapshot


# ── 5 因子各自打分(0/25/50/100,對應紅/黃綠 zone)──
def _score_china_cli(v: Optional[float]) -> Optional[float]:
    """CLI 評分:>100 擴張 100 / 99-100 中性 50 / 98-99 收縮 25 / <98 衰退 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if v > 100.0:  return 100.0
    if v >= 99.0:  return 50.0
    if v >= 98.0:  return 25.0
    return 0.0


def _score_china_pmi(v: Optional[float]) -> Optional[float]:
    """PMI proxy 評分:同 CLI 結構"""
    return _score_china_cli(v)


def _score_china_cpi(v: Optional[float]) -> Optional[float]:
    """CPI YoY 評分:1-3% 理想 100 / 0-1 或 3-4 中性 50 / >4 過熱 0 / <0 通縮 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if 1.0 <= v <= 3.0:  return 100.0
    if 0.0 <= v < 1.0 or 3.0 < v <= 4.0:  return 50.0
    return 0.0


def _score_china_m2(v: Optional[float]) -> Optional[float]:
    """M2 YoY 評分:>=9% 寬鬆 100 / 5-9% 中性 50 / <5% 緊縮 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if v >= 9.0:  return 100.0
    if v >= 5.0:  return 50.0
    return 0.0


def _score_china_usdcny(v: Optional[float]) -> Optional[float]:
    """USDCNY 評分:<7.0 強勢 100 / 7.0-7.2 中性 50 / 7.2-7.4 偏弱 25 / >7.4 大貶 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    # C-3 v18.382:7.2 / 7.4 補抽(P2-3 已抽 7.0)
    from shared.signal_thresholds import (
        CHINA_USDCNY_STRONG, CHINA_USDCNY_NEUTRAL, CHINA_USDCNY_WEAK,
    )
    if v < CHINA_USDCNY_STRONG: return 100.0
    if v <= CHINA_USDCNY_NEUTRAL: return 50.0
    if v <= CHINA_USDCNY_WEAK: return 25.0
    return 0.0


def compute_china_subscore(snapshot: dict) -> Optional[dict]:
    """5 因子等權 0.20 each 計算 China 副盤分數。

    Args
    ----
    snapshot: china_macro_snapshot() 回傳結果

    Returns
    -------
    dict | None:
        {"score": float|None, "factors": {...}, "n_available": int, "n_total": 5}
        全缺 → None(§1 fail loud,**不**偽 50 中性)。
    """
    if not snapshot:
        return None
    scorers = [
        ("cli",    "cli",     _score_china_cli),
        ("pmi",    "pmi",     _score_china_pmi),
        ("cpi",    "cpi_yoy", _score_china_cpi),
        ("m2",     "m2_yoy",  _score_china_m2),
        ("usdcny", "usdcny",  _score_china_usdcny),
    ]
    factors = {}
    scores = []
    for short, snap_key, scorer in scorers:
        entry = snapshot.get(snap_key, {})
        val = entry.get("value") if isinstance(entry, dict) else None
        s = scorer(val)
        factors[short] = {"value": val, "score": s}
        if s is not None:
            scores.append(s)
    n_avail = len(scores)
    if n_avail == 0:
        return None
    avg = round(sum(scores) / n_avail, 2)
    return {"score": avg, "factors": factors, "n_available": n_avail, "n_total": 5}


def classify_china_regime(snapshot: dict) -> dict:
    """從 China snapshot 推導 4 級 regime + USDCNY 警示 flag。

    Levels(BCI = OECD 商業信心 BSCICP03CNM665S，基準值 100，≠ PMI 50 榮枯線):
      🟢 擴張:CLI > 100 AND BCI > 100
      🟡 減速:CLI < 99 OR BCI < 99(但非衰退)
      🔴 衰退/緊縮:(CLI < 98 AND BCI < 98) OR M2 < 5%
      ⚪ 中性:其餘
      🚨 fx_alert flag(獨立):USDCNY > 7.4

    Returns:
        {"regime": str, "fx_alert": bool, "reason": str}
    """
    if not snapshot:
        return {"regime": "⬜ 資料不足", "fx_alert": False, "reason": "snapshot 空"}

    def _val(k: str):
        entry = snapshot.get(k, {})
        return entry.get("value") if isinstance(entry, dict) else None

    cli = _val("cli")
    pmi = _val("pmi")
    m2 = _val("m2_yoy")
    usdcny = _val("usdcny")

    fx_alert = (usdcny is not None and not pd.isna(usdcny) and float(usdcny) > 7.4)

    if cli is None and pmi is None:
        return {"regime": "⬜ 資料不足", "fx_alert": fx_alert,
                "reason": "CLI/PMI 雙缺"}

    cli_red = (cli is not None and float(cli) < 98.0)
    pmi_red = (pmi is not None and float(pmi) < 98.0)
    m2_tight = (m2 is not None and float(m2) < 5.0)
    if (cli_red and pmi_red) or m2_tight:
        reasons = []
        if cli_red and pmi_red:
            reasons.append(f"CLI={cli:.1f} & BCI={pmi:.1f} 雙紅")
        if m2_tight:
            reasons.append(f"M2={m2:.1f}% 緊縮")
        return {"regime": "🔴 衰退/緊縮", "fx_alert": fx_alert,
                "reason": "; ".join(reasons)}

    cli_green = (cli is not None and float(cli) > 100.0)
    pmi_green = (pmi is not None and float(pmi) > 100.0)
    if cli_green and pmi_green:
        return {"regime": "🟢 擴張", "fx_alert": fx_alert,
                "reason": f"CLI={cli:.1f} & BCI={pmi:.1f} 雙綠"}

    cli_slow = (cli is not None and float(cli) < 99.0)
    pmi_slow = (pmi is not None and float(pmi) < 99.0)
    if cli_slow or pmi_slow:
        which = []
        if cli_slow:  which.append(f"CLI={cli:.1f}")
        if pmi_slow:  which.append(f"BCI={pmi:.1f}")
        return {"regime": "🟡 減速", "fx_alert": fx_alert,
                "reason": " / ".join(which) + " <99"}

    return {"regime": "⚪ 中性", "fx_alert": fx_alert,
            "reason": f"CLI={cli}, BCI={pmi} 皆 99-100 區間"}


# ════════════════════════════════════════════════════════════════════════════
# v18.274 — China 副盤 → 主分 乘法 modifier(對稱 Fund v19.116)
# 設計:composite = main × (0.7 + 0.3 × china/100)
#   - china=100(全綠)→ multiplier=1.0 → composite=main(不加成)
#   - china=50 (中性)→ multiplier=0.85 → composite=0.85×main(15% 懲罰)
#   - china=0  (全紅)→ multiplier=0.7 → composite=0.7×main(30% 懲罰)
# 哲學:不對「中國好」主觀加成(避免主分高估),只對「中國壞」做風險溢價懲罰。
# 台股 ~30% 營收 China exposure → 中國弱 = 確定 tail risk,連續線性折扣。
#
# 用法(caller 自行選用,本檔不強制套用):
#   from macro_helpers import (
#       china_macro_snapshot, compute_china_subscore, apply_china_modifier,
#       compute_macro_health,
#   )
#   main = compute_macro_health(macro_dict)["score"]
#   china = compute_china_subscore(china_macro_snapshot(china_dict))
#   composite = apply_china_modifier(main, china["score"] if china else None)
# ════════════════════════════════════════════════════════════════════════════

CHINA_MODIFIER_FLOOR: float = 0.7  # China 全紅時的最低折扣(70% × main)
CHINA_MODIFIER_RANGE: float = 0.3  # 0.7 ~ 1.0 之間擺動


def apply_china_modifier(main_score: Optional[float],
                         china_subscore: Optional[float]) -> Optional[dict]:
    """套用 China 副盤對主分的乘法 modifier。

    公式:composite = main × (CHINA_MODIFIER_FLOOR + CHINA_MODIFIER_RANGE × china/100)
    範圍:multiplier ∈ [0.7, 1.0],只懲罰不加成。

    Args
    ----
    main_score: 主 macro 健康分,[0, 100] 或 None
    china_subscore: China 副盤分數,[0, 100] 或 None(無資料)

    Returns
    -------
    dict | None:
      - main_score=None 或 非數值 → None(無主分可乘)
      - 否則 dict 含:
          composite:  float [0,100],套用 modifier 後的分數(若 china=None 則=main)
          main:       float [0,100],主分(已 clip)
          china:      float [0,100] | None,使用的 china 副盤分數(None 表無資料)
          multiplier: float [0.7, 1.0],實際使用的乘子(china=None 時為 1.0,fail-safe)

    §1 fail loud:中國資料缺失時 multiplier=1.0(不懲罰)但欄位明示 china=None,
    caller 從 china==None 即知「modifier 未實際啟用」,UI 可條件渲染。
    """
    if main_score is None:
        return None
    try:
        m = float(main_score)
    except (TypeError, ValueError):
        return None
    # main clip 到 [0,100] 防越界帶來的結果越界
    m_clipped = max(0.0, min(100.0, m))

    if china_subscore is None:
        # Fail-safe:無中國資料 → multiplier=1.0,composite=main
        return {
            "composite": round(m_clipped, 2),
            "main": round(m_clipped, 2),
            "china": None,
            "multiplier": 1.0,
        }
    try:
        c = float(china_subscore)
    except (TypeError, ValueError):
        return None
    # clip china 到 [0, 100] 防越界
    c_clipped = max(0.0, min(100.0, c))
    multiplier = CHINA_MODIFIER_FLOOR + CHINA_MODIFIER_RANGE * (c_clipped / 100.0)
    composite = max(0.0, min(100.0, m_clipped * multiplier))
    return {
        "composite": round(composite, 2),
        "main": round(m_clipped, 2),
        "china": round(c_clipped, 2),
        "multiplier": round(multiplier, 4),
    }


def get_china_snapshot(fred_api_key: str) -> dict:
    """v18.276 L2 一站式 wrapper:抓取 + 組裝 China macro snapshot。

    對稱 Fund v19.118 `services.macro_service.get_china_snapshot`。
    存在意義:讓 L5 UI(tab_macro)用單一 L2 介面取 China 資料,**無需**
    擴充 EX-PASSTHRU-1 例外清單(此前該例外僅含 data_loader / etf_fetch)。
    本函式 thin wrapper,僅串接 L1 tw_macro.fetch_china_macro + 本檔
    china_macro_snapshot,5 行邏輯。

    Args
    ----
    fred_api_key: FRED API key,空字串或 <30 字元 → 回空 dict(AppTest 守衛)

    Returns
    -------
    dict: snapshot 結構同 china_macro_snapshot(),5 key + credit_impulse_proxy;
          fred_api_key 缺時回 {} ,caller 應檢查 truthy 後再 compute_china_subscore。
    """
    if not fred_api_key or len(str(fred_api_key).strip()) < 30:
        return {}
    from src.data.macro import fetch_china_macro  # noqa: PLC0415
    return china_macro_snapshot(fetch_china_macro(fred_api_key))


# ════════════════════════════════════════════════════════════════
# v18.284 — 總經五桶總結（長期/中期/短線急殺/籌碼/新聞）純函式
#   閾值全讀 shared.macro_buckets SSOT；本函式只負責「取值 → 分級 → 聚合」。
# ════════════════════════════════════════════════════════════════
def compute_five_bucket_summary(
    macro_info: Optional[dict] = None,
    mkt_info: Optional[dict] = None,
    warroom_summary: Optional[dict] = None,
    m1b_m2_info: Optional[dict] = None,
    bias_info: Optional[dict] = None,
    cl_data: Optional[dict] = None,
    li_latest: Any = None,
    jingqi_info: Optional[dict] = None,
    news_items: Optional[list] = None,
) -> dict:
    """總經五桶總結純函式。

    吃各 session_state 片段 → 回五桶 summary，每桶含燈號 + headline + 指標明細。
    門檻全部讀 `shared.macro_buckets.BUCKET_DANGER_SPECS`（SSOT），**不在此 inline**。

    Returns
    -------
    dict: {bucket: {level, label, headline, color, emoji, details:[...]}}，
          bucket ∈ long/mid/short/chips/news。

    §1 Fail Loud：缺值 → 該指標 gray（未載入），桶全 gray → ⬜，**不**偽綠。
    §4.1：foreign_net 因 inst net 單位待確認，v1 暫不接（保持 gray 不誤判）。
    """
    # v19.172：BUCKET_LEVEL_LABEL 改由 bucket_level_label() 取用(紅燈依觸發方向
    #   分流過熱 / 惡化)；danger_exceedance 用來在同桶多盞同色燈時挑主因。
    from shared.macro_buckets import (
        BUCKET_ORDER, LEVEL_COLOR, LEVEL_EMOJI, SPECS_BY_KEY,
        specs_for_bucket, classify_danger, aggregate_level, fmt_value,
        bucket_level_label, danger_exceedance,
    )

    macro_info = macro_info or {}

    def _g(d, *keys):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    def _num(x):
        if x is None:
            return None
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    def _df_last(df, col):
        """DataFrame 末列某欄 → float / None。"""
        try:
            if (df is not None and hasattr(df, "empty") and not df.empty
                    and col in df.columns):
                return float(df[col].iloc[-1])
        except Exception:
            return None
        return None

    _news_sys = None
    if news_items is not None:
        try:
            _news_sys = float(sum(1 for h in news_items
                                  if isinstance(h, dict) and h.get("is_systemic")))
        except Exception:
            _news_sys = None

    values = {
        "health":        _num(_g(warroom_summary, "health_score")),
        "ndc_signal":    _num(_g(macro_info, "ndc_signal", "score")),
        "m1b_m2_gap":    _num(_g(m1b_m2_info, "gap")),
        "ism_pmi":       _num(_g(macro_info, "ism_pmi", "value")),
        "us_core_cpi":   _num(_g(macro_info, "us_core_cpi", "yoy")),
        "tw_export":     _num(_g(macro_info, "tw_export", "yoy")),
        "bias_240":      _num(_g(bias_info, "bias_240")),
        "vix":           _num(_g(macro_info, "vix", "current")),
        "adl":           _df_last(_g(cl_data, "adl"), "ad_ratio"),
        "fut_net":       _df_last(li_latest, "外資大小"),
        "margin":        _num(_g(cl_data, "margin")),
        "jingqi":        _num(_g(jingqi_info, "avg")),
        # §4.1 inst net 單位待確認 → 故意回 None(§1 fail-safe:寧缺勿錯)。
        # v18.436 #20:此為「外部資訊阻斷」項,非程式 bug。啟用前置條件:
        #   確認 FinMind TaiwanStockInstitutionalInvestorsBuySell 的 buy/sell 單位
        #   (股 vs 千股 vs 億元)→ 才能對齊 spec 門檻判讀。在確認前 None 是正解,
        #   不可猜單位填值(會誤判紅綠燈)。ForeignFlowSchema(71b310c)已備 schema。
        "foreign_net":   None,
        "news_systemic": _news_sys,
    }

    out: dict = {}
    for bucket in BUCKET_ORDER:
        details = []
        for s in specs_for_bucket(bucket):
            v = values.get(s.key)
            details.append({
                "key": s.key, "label": s.label,
                "value_str": fmt_value(v, s),
                "danger": classify_danger(v, s), "note": s.note,
            })
        blevel = aggregate_level([d["danger"] for d in details])
        d0 = None
        if blevel == "gray":
            headline = "尚未載入（按更新 / 執行 AI 裁決）"
        elif blevel == "green":
            _n_ok = sum(1 for d in details if d["danger"] == "green")
            headline = f"{_n_ok} 項指標全綠"
        else:
            # v19.172：原本 `next(...)` 取「註冊順序第一個同色燈」當主因，
            #   註冊順序純屬歷史，同桶多盞紅時顯示的常不是最嚴重那盞，
            #   而它同時決定下方標籤的方向 → 一起收斂。
            #   改取「超標幅度」最大者（以黃→紅帶寬為單位，見 danger_exceedance
            #   docstring 說明為何不用倍數）。幅度平手時 max() 保留先出現者，
            #   完全退回原註冊順序，行為不退步。
            _hits = [d for d in details if d["danger"] == blevel]
            d0 = max(_hits, key=lambda d: danger_exceedance(
                values.get(d["key"]), SPECS_BY_KEY[d["key"]], blevel))
            headline = f"{d0['label']} {d0['value_str']}｜{d0['note']}"
        out[bucket] = {
            "level": blevel,
            # v19.172：紅燈標籤依「觸發該桶紅燈的 spec 方向」分流
            #   （high_bad → 結構/循環過熱；low_bad → 結構防禦/循環惡化），
            #   修實機「🔴 循環惡化」配同頁「主升段狂熱…順勢作多」的自相矛盾。
            "label": bucket_level_label(
                bucket, blevel,
                spec=SPECS_BY_KEY[d0["key"]] if d0 is not None else None,
                value=values.get(d0["key"]) if d0 is not None else None,
            ),
            "headline": headline,
            "color": LEVEL_COLOR[blevel],
            "emoji": LEVEL_EMOJI[blevel],
            "details": details,
        }
    return out


# ════════════════════════════════════════════════════════════════════════════
# v19.173 — 拐點訊號「分群 + 分母」聚合（修「4 個空頭訊號」誇大確信度）
#
# 【問題一：共線性 —— 把同一個因子數成好幾個獨立證據】
# 舊寫法是 `sum(1 for ... if color == TRAFFIC_RED)`，等於假設每盞紅燈都是
# **一份獨立證據**。實際上拐點面板的訊號高度相關：
#   - 「年線乖離過大 / 外資期貨大量空單 / 散戶極度看多」本質是同一個
#     「多頭末端擁擠度」因子的三種量測；
#   - 「景氣對策連 2 月翻空 / 領先指標 6M 由正轉負」同屬國發會**同一份資料集**
#     （領先指標本身就是景氣對策信號的構成項之一），幾乎必然同號。
#
# 等相關（equicorrelated）近似下的有效獨立訊號數：
#
#       n_eff = n / ( 1 + (n − 1) · ρ̄ )
#
#   （推導：n 個單位變異數、兩兩相關 ρ̄ 的訊號，其和的變異數為
#     Var(Σ) = n + n(n−1)ρ̄；若改用 n_eff 個**獨立**訊號要有同樣的
#     「平均訊號」精度，需 n_eff = n²/Var(Σ) = n / (1 + (n−1)ρ̄)。）
#
#   代 n = 4、ρ̄ = 0.7 →  n_eff = 4 / (1 + 3×0.7) = 4 / 3.1 ≈ 1.29
#   也就是「4 個空頭訊號」實際只值 ~1.3 個獨立訊號，確信度被誇大約 3 倍。
#
#   ⚠️ 誠實揭露：ρ̄ = 0.7 是**量級假設**，不是本專案實測值（要實測需要各訊號
#   的歷史觸發序列，目前沒有落地）。因此本模組**不把 n_eff 當數字印到畫面**
#   （§3.3 反捏造），只用它說明「為什麼要分群」。真正落地的是下面的分群規則。
#
# 【問題二：對資訊集非單調 —— 少抓到一個來源，結論反而反轉】
# 舊門檻 `_bear_pts >= 2` 是**絕對計數、沒有分母**。面向 6 需 FinMind token、
# 面向 7 需 CPI + Fed，任一 fetch 失敗 → 可評估訊號數下降 →
# 同一個市場可能從「🔴 4 個空頭」變成「⚪ 訊號分歧」。使用者只會看到
# 「昨天紅燈、今天變白燈」而找不到原因。
# 這與 `src/services/allocation_service.py:178-212`（v19.170 修好的三環第一環）
# 是同一類 bug，本次把該處的處理原則推廣過來：
#   **未知 ≠ 不利，也 ≠ 有利** —— 資料拿不到的群從分母剔除並標「未評估」，
#   不計入偏多也不計入偏空，且**分母一定顯示給使用者看**。
#
# 【落地規則】
#   1. 每個訊號歸入一個 family（同一個潛在因子 → 同一群）。
#   2. 群內**取最壞、不累加**：只要有一盞空 → 該群 = 偏空（一群最多算一次）。
#   3. 顯示改為「N 群中 M 群偏空（可評估 K/N 群）」，比例 + 分母同時揭露。
# ════════════════════════════════════════════════════════════════════════════

#: 拐點訊號分群（key, 顯示名）。分群原則：**同一個潛在因子放同一群**。
#: 順序即 UI 顯示順序，與 section_state.py 面板 1~7 的敘事順序對齊。
PIVOT_FAMILIES: tuple[tuple[str, str], ...] = (
    ('trend',     '趨勢（均線結構）'),
    ('level',     '位階（乖離率）'),
    ('liquidity', '資金（M1B-M2 / 台幣）'),
    ('chips',     '籌碼（外資期貨 / 韭菜 / 外資連續）'),
    ('cycle',     '景氣（NDC 對策 / 領先指標）'),
    ('inflation', '通膨利率（CPI × Fed）'),
)

#: family key → 顯示名
PIVOT_FAMILY_NAME: dict = dict(PIVOT_FAMILIES)

#: 訊號 label → family key（SSOT）。
#: label 必須與 `section_state.py` 的 `pivot_signals.append((label, ...))` 逐字一致；
#: 對不上的 label 會被歸入回傳值的 `unknown_labels`（**不靜默吞掉**，§1）。
PIVOT_FAMILY_OF: dict = {
    # 1. 均線方向（同一條指數的多條均線，彼此相關極高）
    '均線多頭確認': 'trend',
    '均線初步翻多': 'trend',
    '均線空頭確認': 'trend',
    '整理區間':     'trend',
    # 2. 乖離率（年線 / 月線同為「離均線多遠」的量測）
    '年線乖離過大': 'level',
    '年線深度低估': 'level',
    '月線過熱':     'level',
    '月線超賣':     'level',
    # 3. 資金面（M1B-M2 與台幣同屬「錢往哪流」）
    'M1B>M2 黃金交叉': 'liquidity',
    'M1B<M2 死亡交叉': 'liquidity',
    '台幣升值':        'liquidity',
    '台幣貶值':        'liquidity',
    # 4. 籌碼（外資期貨 / 韭菜 / 外資現貨連續 —— 都是「外資 vs 散戶」同一齣戲）
    '外資期貨大量空單':   'chips',
    '外資空單縮減':       'chips',
    '外資期貨多方':       'chips',
    '散戶極度看多（危險）': 'chips',
    '散戶極度悲觀（機會）': 'chips',
    '外資由連賣轉買':     'chips',
    '外資由連買轉賣':     'chips',
    '外資連續買超':       'chips',
    '外資連續賣超':       'chips',
    # 5. 景氣（NDC 景氣對策信號與領先指標同屬國發會**同一資料集**，必然同號）
    '景氣對策連2月翻多':   'cycle',
    '景氣對策連2月翻空':   'cycle',
    '景氣對策連3月上升':   'cycle',
    '景氣對策連3月下降':   'cycle',
    '領先指標 6M 由負轉正': 'cycle',
    '領先指標 6M 由正轉負': 'cycle',
    '領先指標持續擴張':     'cycle',
    '領先指標持續收縮':     'cycle',
    # 6. 通膨利率（CPI×Fed 雙頂回落，v19.173 正名前為「MK 黃金拐點」）
    'CPI×Fed 雙頂回落 ⭐': 'inflation',
    'CPI×Fed 回落觀察中':  'inflation',
}

#: 判定方向所需的最少「群」數。
#: 新舊等價性推導（為何仍是 2）：
#:   舊規則 `_bear_pts >= 2` 的單位是「**訊號**」，新規則的單位是「**群**」。
#:   - 兩訊號**分屬不同群** → 新舊同時成立，**行為完全等價**。
#:   - 兩訊號**擠在同一群**（如「外資期貨大量空單」+「散戶極度看多」都在籌碼群）
#:     → 舊規則成立、新規則不成立。這正是共線性修正要擋掉的誤判：
#:       同一個因子的兩種量測不構成兩份獨立證據。
#:   故常數值不動（2），只改單位；沒有引入新的魔術數字。
PIVOT_MIN_SIDE_FAMILIES: int = 2

#: 可評估群數低於此值 → 不宣稱方向（分母太小，比例沒有意義）。
PIVOT_MIN_EVALUABLE_FAMILIES: int = 2


def aggregate_pivot_families(
    pivot_signals: Optional[list] = None,
    evaluable: Any = None,
) -> dict:
    """把拐點訊號依 family 收斂，回「群比例 + 分母」而非「訊號絕對計數」。

    參數
    ----
    pivot_signals : list[tuple[label, icon, color, detail]] | None
        `section_state.py` 累積的訊號清單。形狀不符的元素會被略過。
    evaluable : Iterable[str] | None
        **有資料、有能力判定**的 family key 集合（即使該群這次沒觸發任何訊號）。
        沒被列入且也沒有任何訊號的 family → 標記 'unevaluated'，
        **從分母剔除**、不計入偏多也不計入偏空（§1 誠實揭露 + 資訊單調性）。

    回傳
    ----
    dict::

        {
          'families':    {key: {'name', 'side', 'labels'}},   # side ∈ bull/bear/neutral/unevaluated
          'n_bull' / 'n_bear' / 'n_neutral': int,             # 單位 = 群
          'n_evaluable': int,   # 分母（= bull + bear + neutral）
          'n_total':     int,   # 群總數
          'unevaluated': list[str],      # 未評估群的顯示名
          'unknown_labels': list[str],   # 對不上 PIVOT_FAMILY_OF 的 label
          'verdict':  'bull' | 'bear' | 'mixed' | 'insufficient',
          'headline': str,   # 直接可印的結論句（含分母）
          'color':    str,   # traffic hex
          'note':     str,   # 未評估群的說明（無則空字串）
        }

    判定
    ----
    - 群內取最壞：一群裡只要有一盞 `TRAFFIC_RED` → 該群 = 'bear'（**不累加**）；
      否則有 `TRAFFIC_GREEN` → 'bull'；其餘（黃/灰/無訊號）→ 'neutral'。
    - verdict='bear'  ⟺ n_bear > n_bull 且 n_bear >= PIVOT_MIN_SIDE_FAMILIES
    - verdict='bull'  ⟺ 對稱條件
    - n_evaluable < PIVOT_MIN_EVALUABLE_FAMILIES → 'insufficient'（不宣稱方向）
    - 其餘 → 'mixed'

    ⚠️ 已知落差（v19.173 誠實揭露，本輪**刻意不改**）
    ------------------------------------------------
    `section_state.py` 的「月線過熱 / 月線超賣」用的是 `#da3633` / `#2ea043`，
    **不是** `TRAFFIC_RED` / `TRAFFIC_GREEN`。舊的計數邏輯同樣漏算它們，
    本函式維持一致（嚴格比對 traffic 常數），避免在「正名 + 去共線」這次改動裡
    夾帶一個沒被核准、也無法在此驗證的行為變更。若日後要修，請單獨提案：
    把那兩處色碼改成 traffic SSOT 常數（那是 `section_state.py` 端的修正）。

    效能
    ----
    O(len(pivot_signals))，單次線性掃描，無巢狀迴圈。
    """
    _eval_keys = set()
    if evaluable:
        try:
            _eval_keys = {str(k) for k in evaluable}
        except TypeError:
            _eval_keys = set()

    _fam_side: dict = {}
    _fam_labels: dict = {k: [] for k, _ in PIVOT_FAMILIES}
    unknown_labels: list = []

    for _sig in (pivot_signals or []):
        try:
            _label, _icon, _color, _detail = _sig
        except (TypeError, ValueError):
            # 形狀不符（非 4-tuple）→ 略過但不吞：計入 unknown_labels 供診斷
            unknown_labels.append(repr(_sig)[:40])
            continue
        _fam = PIVOT_FAMILY_OF.get(str(_label))
        if _fam is None:
            unknown_labels.append(str(_label))
            continue
        _fam_labels[_fam].append(str(_label))
        if _color == TRAFFIC_RED:
            _fam_side[_fam] = 'bear'          # 取最壞：空一旦成立就不被多蓋掉
        elif _color == TRAFFIC_GREEN:
            if _fam_side.get(_fam) != 'bear':
                _fam_side[_fam] = 'bull'
        else:
            _fam_side.setdefault(_fam, 'neutral')

    families: dict = {}
    n_bull = n_bear = n_neutral = 0
    unevaluated: list = []
    for _key, _name in PIVOT_FAMILIES:
        _has_signal = bool(_fam_labels[_key])
        # 有訊號 ⇒ 必定可評估（防呼叫端漏登記）；否則看 evaluable 名單
        if not (_has_signal or _key in _eval_keys):
            _side = 'unevaluated'
            unevaluated.append(_name)
        else:
            _side = _fam_side.get(_key, 'neutral')
            if _side == 'bull':
                n_bull += 1
            elif _side == 'bear':
                n_bear += 1
            else:
                n_neutral += 1
        families[_key] = {'name': _name, 'side': _side, 'labels': _fam_labels[_key]}

    n_total = len(PIVOT_FAMILIES)
    n_evaluable = n_bull + n_bear + n_neutral

    if n_evaluable < PIVOT_MIN_EVALUABLE_FAMILIES:
        verdict, color = 'insufficient', TRAFFIC_YELLOW
        headline = (f'⚪ 拐點資料不足：{n_total} 群僅 {n_evaluable} 群可評估 '
                    f'→ 不宣稱方向')
    elif n_bull > n_bear and n_bull >= PIVOT_MIN_SIDE_FAMILIES:
        verdict, color = 'bull', TRAFFIC_GREEN
        headline = (f'🟢 綜合拐點：{n_total} 群中 {n_bull} 群偏多'
                    f'（可評估 {n_evaluable}/{n_total} 群）→ 偏向底部起漲')
    elif n_bear > n_bull and n_bear >= PIVOT_MIN_SIDE_FAMILIES:
        verdict, color = 'bear', TRAFFIC_RED
        headline = (f'🔴 綜合拐點：{n_total} 群中 {n_bear} 群偏空'
                    f'（可評估 {n_evaluable}/{n_total} 群）→ 偏向頂部起跌')
    else:
        verdict, color = 'mixed', TRAFFIC_YELLOW
        headline = (f'⚪ 訊號分歧：偏多 {n_bull} 群 vs 偏空 {n_bear} 群'
                    f'（可評估 {n_evaluable}/{n_total} 群），方向待確認')

    note = ''
    if unevaluated:
        note = ('⚠️ 未評估：' + '、'.join(unevaluated)
                + '（資料未取得 → 已排除於分母外，既不計入偏多也不計入偏空）')

    return {
        'families': families,
        'n_bull': n_bull,
        'n_bear': n_bear,
        'n_neutral': n_neutral,
        'n_evaluable': n_evaluable,
        'n_total': n_total,
        'unevaluated': unevaluated,
        'unknown_labels': unknown_labels,
        'verdict': verdict,
        'headline': headline,
        'color': color,
        'note': note,
    }
