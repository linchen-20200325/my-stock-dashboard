"""🎯 智慧選股 TAB — 三階段濾網（基本面 / 籌碼技術 / AI 綜合建議）

Per CLAUDE.md §2 設計：使用者輸入觀察清單 10-30 檔，按鈕觸發批次跑（不全市場掃描避免 API 風暴）

三階段邏輯（全 15 項條件實作完成 — Stage 1 ×9 + Stage 2 ×6 + Stage 3 AI）
==========================================================================

Stage 1：基本面防禦與成長（9 項）
- ✅ 負債比 < 50%（FinMind 資產負債表，金融股標 ⚠️ 不誤殺）
- ✅ 三率三升 YoY（毛利率 / 營益率 / 淨利率 — FinMind 損益表 8 季）
- ✅ 連續 5 年配息 + 平均殖利率 > 7%（yfinance.dividends）
- ✅ PE 河流圖區間（真 TTM EPS = 近 4 季加總；便宜 <10 / 合理 <15 / 昂貴）
- ✅ 應收帳款周轉天數穩定（季變動 < 30%）
- ✅ 存貨周轉率年化 > 4 次
- ✅ 資本支出積極（CapEx > 股東權益 5%）
- ✅ 淨流動值為正（流動資產 > 總負債）
- ✅ 合約負債 YoY > 20% + 連 2 季增（FinMind BS 多季）

Stage 2：籌碼與技術面鎖定（6 項）
- ✅ 股價站穩 MA20 + 月線翻揚
- ✅ MACD 綠轉紅 / 柱狀體收斂轉發散
- ✅ KD 低檔黃金交叉（K < 20）
- ✅ 布林通道剛開口（band 寬度近 5 日 > 前 20 日 1.3 倍）
- ✅ 投信連續 5 日買超（FinMind 法人買賣超）
- ✅ 大戶 ≥1000 張級距持股近 2 週比例增加（FinMind 集保股權分散）

Stage 3：AI 綜合建議
- ✅ Gemini Markdown 報告 — 積極型 / 保守型 / 止損紀律三型分析

呼叫端（H2 2026-08 更正 —— 舊文寫的三件事全部不成立）
======================================================
舊文：「app.py 於『💎 高息網』(tab_screener) 候選清單下方呼叫，candidates 帶入
       render_yield_screener() 的篩選結果」。逐項查證：
  (a) **「💎 高息網」這個模組不存在** —— `render_yield_screener` 全 repo 零定義
      （`src/ui/tabs/yield_screener.py` 只有 `render_yield_confirm` 等）。
      選股分頁的真名是 **「🔭 選股網」**（app.py `st.tabs([... '🔭 選股網'])`）。
  (b) app.py **不再呼叫本函式** —— v19.111 選股網極簡化時移除，並由
      `tests/test_app_no_magic_bare_ternary.py::test_screener_keeps_only_single_button_flow`
      反向釘住（app.py 再出現 `render_tab_stock_picker` = 測試紅燈）。
  (c) 候選來源也不是殖利率篩選，而是基本面存活池 / 使用者輸入。

現況（2026-08 實測）：
- `render_tab_stock_picker` 的唯一 production caller = `src/ui/tabs/tab_stock_grp.py`
  （🏆 個股組合 → 三階段濾網），傳 `source_label='個股組合輸入'`。
- `render_prescreen_panel` 由 app.py「🔭 選股網」①基本面優選 呼叫。
"""
from __future__ import annotations

import streamlit as st

from shared.thresholds import YIELD_HIGH
# F1 v19.184 §3.3：全台股基本面初篩的說明文字改吃同一份 SSOT（原手抄 50% / EPS>0 / 四項）
from shared.fundamental_prescreen_thresholds import (
    DEBT_RATIO_MAX as _PRESCREEN_DEBT_MAX,
    EPS_MIN as _PRESCREEN_EPS_MIN,
    PRESCREEN_REQUIRED_PASSES as _PRESCREEN_N,
)
# H2 2026-08：選股網總覽卡「本次因子」摘要用的既有 tier SSOT（不新增門檻）。
# 兩個模組都有 `TIER_MID` 等同名常數 → 一律加前綴 alias，避免同名不同義互相覆蓋。
from shared.rs_screen_thresholds import (
    TIER_LEAD as _RS_TIER_LEAD,
    TIER_MILD as _RS_TIER_MILD,
)
from shared.shortage_screen_thresholds import (
    TIER_MID as _SHORT_TIER_MID,
    TIER_STRONG as _SHORT_TIER_STRONG,
)
from src.config import FINMIND_API_URL  # Batch 10 v18.412 SSOT

# ── 三階段濾網門檻（SSOT，§3.3 反捏造：禁止 inline magic number）─────────────
# v18.466：使用者要求「基本面當主篩、門檻拉高到 6/9」。原 inline `>= 5` / `>= 3` 抽出集中。
PICKER_S1_MIN_PASS = 6   # Stage 1 基本面：9 項中至少通過項數（進入通過清單門檻）
PICKER_S2_MIN_PASS = 3   # Stage 2 籌碼技術：6 項中至少通過項數
PICKER_DEEP_SCAN_N = 50  # 選股網候選池深掃檔數上限（依估值排序取前 N，控管 FinMind API 用量）

# ── F1 v19.184 §3.3：逐項判定門檻抽 SSOT ──────────────────────────────────
# 【為什麼】這 6 個數字原本**同時**出現在兩個地方且各寫各的：
#   (a) 判定式裡的 inline magic（`abs(_chg) < 30`、`_turnover > 4`、`_ratio > 0.05`、
#       `_yoy_pct > 20`、`_ratio > 1.3`、`_pos == 5`）；
#   (b) 表格下方 `st.caption` 的手抄說明（「季變動 < 30%」「年化 > 4 次」…）。
# 這正是 v18.466 那個 bug 的形狀：`PICKER_S1_MIN_PASS` 由 5 改 6 時，同檔三處 caption
# 都改了，只有餵給 AI 的統計沒改 → 送進 LLM 的篩選標準是假的（v19.178 才修）。
# 現在把 (a)(b) 綁在同一個常數上，改一次兩邊一起動。
#
# 📌 待辦（非本批）：整個 `PICKER_*` 區塊應搬去 `shared/picker_thresholds.py`（L0），
#    與 `shared/rs_screen_thresholds.py` / `shared/shortage_screen_thresholds.py` 一致。
#    那是純搬家（零行為變更），但會動到 `tests/test_picker_funnel.py` 的 import 路徑，
#    與本批「只接說明文字」的範圍無關，故不在此順手做。
PICKER_AR_TURNOVER_STABLE_QOQ_PCT = 30.0
"""應收帳款天數「穩定」判定：|季增率| < 30%（單位：%）。原 `_check_ar_turnover` inline。"""

PICKER_INV_TURNOVER_MIN_TIMES = 4.0
"""存貨周轉率「OK」判定：年化 > 4 次/年。原 `_check_inventory_turnover` inline。"""

PICKER_CAPEX_EQUITY_MIN_RATIO = 0.05
"""資本支出「積極」判定：單季 CapEx / 股東權益 > 0.05（≈ 年化 0.2）。
⚠️ 單位是**比值**不是 %，caption 顯示時要自己 ×100（§4.1 百分比 vs 小數）。
原 `_check_capex_vs_equity` inline。"""

PICKER_CONTRACT_LIAB_YOY_MIN_PCT = 20.0
"""合約負債「OK」判定：YoY > 20%（單位：%）且同時滿足連續季增。
原 `_check_contract_liab_yoy` inline（兩處 `> 20`）。"""

PICKER_CONTRACT_LIAB_QOQ_QUARTERS = 2
"""合約負債連續季增的季數要求（本季 > 前季 > 前前季 ＝ 2 段成長）。
⚠️ 判定式是**鏈式比較**寫死 3 個點；本常數目前只餵說明文字，
改成 3 段以上需同時改判定式（屬行為變更，不是文案修正）。"""

PICKER_BOLL_OPENING_RATIO = 1.3
"""布林開口判定：近 N 日 band 寬度均值 > 前 M 日均值的 1.3 倍。
原 `_check_bollinger_opening` inline。"""

PICKER_BOLL_RECENT_DAYS = 5
"""布林開口的「近期」窗（交易日）。原 `_width.iloc[-5:]` inline。
⚠️ 與 `PICKER_INST_BUY_STREAK_DAYS`（同為 5）**同數字不同義**，
兩者刻意各自具名，禁止互相代入（§3.3 前綴分名防耦合）。"""

PICKER_BOLL_BASELINE_DAYS = 20
"""布林開口的「基準」窗（交易日）。原 `_width.iloc[-25:-5]` inline（25 − 5 = 20）。"""

PICKER_INST_BUY_STREAK_DAYS = 5
"""投信「連續買超」判定所需的交易日數。原 `_check_institutional_buying` inline
（`[:5]` / `len(_dates) < 5` / `_pos == 5` 三處同值）。"""

# ── 15 項條件 SSOT：(result dict label 欄, 顯示名)。自訂篩選器 + 兩張表共用 ──────
# 每項「過/沒過」以 label 開頭是否為 '✅' 判定（同 s1/s2_pass_cnt 計數邏輯）。
PICKER_S1_CONDITIONS = [
    ('debt_ratio_label',   '負債比'),
    ('three_rate_label',   '三率三升'),
    ('div_5y_label',       '5Y配息'),
    ('pe_zone_label',      'PE區間'),
    ('ar_turnover_label',  '應收周轉'),
    ('inv_turnover_label', '存貨周轉'),
    ('capex_label',        '資本支出'),
    ('book_value_label',   '淨流動值'),
    ('contract_liab_label', '合約負債'),
]
PICKER_S2_CONDITIONS = [
    ('ma20_label',  'MA20站穩'),
    ('macd_label',  'MACD翻紅'),
    ('kd_label',    'KD黃叉'),
    ('boll_label',  '布林開口'),
    ('inst_label',  '投信買超'),
    ('major_label', '大戶持股'),
]
PICKER_ALL_CONDITIONS = PICKER_S1_CONDITIONS + PICKER_S2_CONDITIONS


def render_prescreen_panel(*, refresh: bool = False) -> None:
    """全台股基本面初篩結果面板（v19.64）：顯示四項全過存活池 + 明細。

    接線 Phase 2 後端（fundamental_prescreen L2 / screener_service L3）——原本只當
    隱形閘門過濾候選池，這裡把「哪些股票四項全過、各項數值」直接攤給使用者看。
    唯讀顯示既有 L3 資料；快照缺 → 靜默略過（不炸選股網）。
    """
    import pandas as pd  # noqa: PLC0415 — 本檔 pandas 為局部 import
    try:
        from src.services.fundamental_screener_service import (
            describe_snapshot_coverage,
            get_fundamental_prescreen,
        )
        _df, _meta = get_fundamental_prescreen(refresh=refresh)
    except Exception as _e:  # noqa: BLE001 — 面板不可用不炸選股網
        st.caption(f'（全台股基本面初篩結果暫不可用：{type(_e).__name__}）')
        return
    if _df is None or _df.empty:
        st.caption('（全台股基本面初篩：尚無快照，請先跑 Update Fundamentals workflow）')
        return
    _surv = _df[_df['survivor']]
    _q = f"民國{_meta.get('roc_year')}Q{_meta.get('season')}"
    _yoy = ('（三率三升 YoY vs 去年同季）' if _meta.get('prev_roc_year') is not None
            else '（缺去年同季→三率三升不判）')
    with st.expander(
            f'🔬 全台股基本面初篩結果 — 四項全過 {len(_surv)}/{len(_df)} 檔 · {_q}{_yoy}',
            expanded=False):
        # F1 v19.184 §3.3：「<50%」「EPS>0」原為手抄，改吃初篩 SSOT
        #（`shared/fundamental_prescreen_thresholds`）。「四項」改吃
        # `PRESCREEN_REQUIRED_PASSES` —— 那個常數的 docstring 明文寫「禁止 UI/L2 端寫死 == 4」。
        st.caption(f'{_PRESCREEN_N} 項：①負債比<{_PRESCREEN_DEBT_MAX * 100:g}% '
                   f'②三率三升 YoY（毛利/營益/淨利率 本季>去年同季）'
                   f'③淨流動值>0（流動資產>總負債）④EPS>{_PRESCREEN_EPS_MIN:g}。'
                   f'**{_PRESCREEN_N} 項全過**才入選股網候選池。')
        # v19.71 涵蓋率診斷（§5）：讓「慢公布是否已納入」看得見
        _cov = describe_snapshot_coverage(_meta)
        (st.warning if _cov['possibly_incomplete'] else st.caption)(f'📦 {_cov["text"]}')
        _show_all = st.checkbox('顯示全市場（否則只看四項全過）', value=False,
                                key='prescreen_show_all')
        _v = _df if _show_all else _surv
        if _v.empty:
            st.info('目前無四項全過的標的。')
            return
        _yn = {True: '✅', False: '❌'}
        _tbl = pd.DataFrame({
            '代號':      _v['stock_id'].astype(str),
            '負債比%':   (_v['debt_ratio'] * 100).round(1),
            '毛利率%':   (_v['gross_margin'] * 100).round(1),
            '營益率%':   (_v['op_margin'] * 100).round(1),
            '淨利率%':   (_v['net_margin'] * 100).round(1),
            'EPS':       _v['eps'].round(2),
            '負債':      _v['pass_debt'].map(_yn),
            '三率三升':  _v['pass_three_rise'].map(_yn),
            '淨流動':    _v['pass_net_current'].map(_yn),
            'EPS>0':     _v['pass_eps_positive'].map(_yn),
            '通過':      _v['pass_count'].astype(str) + '/4',
        }).sort_values(['通過', 'EPS'], ascending=[False, False])
        st.dataframe(_tbl, hide_index=True, use_container_width=True)


def _label_passes(label) -> bool:
    """單項條件是否通過：label 開頭為 '✅'（同 s1/s2_pass_cnt 判定）。"""
    return isinstance(label, str) and label.startswith('✅')


def count_condition_passes(result: dict, label_keys) -> int:
    """一檔在指定條件欄中『過』了幾項（純函式，供自訂篩選 + 測試）。"""
    return sum(1 for k in label_keys if _label_passes(result.get(k, '')))


def filter_by_custom_conditions(results, selected_keys, min_pass: int):
    """自訂篩選：回「選中條件裡至少過 min_pass 項」的股票子集（純函式）。

    selected_keys 空 → 回 None（代表未啟用自訂，caller 走預設 S1/S2 門檻）。
    """
    if not selected_keys:
        return None
    _n = max(1, int(min_pass))
    return [r for r in results if count_condition_passes(r, selected_keys) >= _n]


# ══════════════════════════════════════════════════════════════════════════════
# 🔭 選股網總覽卡「本次因子」摘要（H2 2026-08）
# ══════════════════════════════════════════════════════════════════════════════
# 【修的是什麼】app.py 的選股結果總覽卡原本印三個裸 `len(...)` 並冠上「命中」：
#   ① 「缺貨命中 N」的 N = len(_shortage_rows)。但
#      `shortage_screener_service._RANKABLE_TIERS = (TIER_STRONG, TIER_MID, TIER_WEAK)`
#      **含 TIER_WEAK（畫面字樣「⬜ 不明顯」）** ⇒ 那是「被評分的檔數」，不是命中數。
#   ② 「抗跌RS N」的 N = len(_rs_rows_all)。但選股網走
#      `run_rs_leader_scan(beat_only=False, top_n=RS_SCAN_MAX)`，
#      `RS_RANKABLE_TIERS` **含 TIER_SYNC（同步大盤）/ TIER_LAG（落後大盤）**
#      ⇒ 冠上「抗跌」不成立。`SCREEN_ANGLE_LABELS` 早在 B6-b 就為同一理由改過文案
#      （「不保證贏大盤」），總覽卡沒跟上 —— 同一個事實，同一頁兩種說法。
#   ③ 「跨季轉強 N」的 N = len(_trend_map)。但 `build_trend_map` 只濾掉
#      `favorable_of == 0`（＝四個趨勢因子全算不出來），
#      **`favorable_count == 0`（四項全不佳）照樣有 key** ⇒ 那是「有資料可算的檔數」，
#      規模≈全市場（app.py 同頁另一個 expander 自己就寫「全市場 ~2000 檔」）。
#
# 【修法】不發明新門檻：分子一律取**既有 SSOT tier 邊界**，並且分子/分母一起印，
#         讓「N 檔裡有 M 檔真的有訊號」直接看得到。
_SHORTAGE_SIGNAL_TIERS: tuple[str, ...] = (_SHORT_TIER_STRONG, _SHORT_TIER_MID)
"""缺貨「有訊號」= 🟥 強缺貨 + 🟧 中度（＝ 分數 ≥ SHORTAGE_TIER_MID_MIN）。
排除 ⬜ 不明顯（TIER_WEAK）—— 它的畫面字樣自己就叫「不明顯」。"""

_RS_RESILIENT_TIERS: tuple[str, ...] = (_RS_TIER_LEAD, _RS_TIER_MILD)
"""RS「偏強以上」= 🔴 逆勢強股 + 🟡 偏強抗跌（＝ avg_rs ≥ RS_SIGMA_MILD_MIN）。
排除 ⚪ 同步大盤 / 🟢 落後大盤。"""


def _count_tier(rows, tiers) -> int | None:
    """rows 中 `_tier` ∈ tiers 的筆數；**沒有任何一列帶 `_tier` 時回 None**。

    §1：None 的語意是「分級欄不存在 → 數不出來」，不是「0 筆」。
    caller 必須據此改印誠實文案，不得把 None 當 0 顯示。
    （`_tier` 是 shortage_screener / rs_leader_screener `to_row()` 的固定欄位，
      正常情況不會缺；這條防的是上游 schema 悄悄改掉時不要靜默報 0。）
    """
    _typed = [r for r in rows if isinstance(r, dict) and r.get('_tier')]
    if rows and not _typed:
        return None
    return sum(1 for r in _typed if r.get('_tier') in tiers)


def _is_favorable(v) -> bool:
    """跨季趨勢 favorable_count > 0（至少一項方向為佳）。非數字 → False（不猜）。"""
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False


def summarize_factor_hits(factors, *, shortage_rows=None, rs_rows=None,
                          trend_map=None) -> list[str]:
    """🔭 選股網總覽卡「本次因子」片語清單（純函式：不讀 session_state、不碰 streamlit）。

    Args:
        factors: 本次勾選的因子 key（SCREEN_ANGLE_LABELS 的值，如 'shortage'）。
        shortage_rows / rs_rows: 掃描結果 list[dict]（含 `_tier`）。
            **None = 沒掃 / 掃失敗 → 不產生片語**（§1：掃失敗不假報 0，
            沿用 app.py 原本的 `is not None` 判斷）；`[]` = 掃了但零結果 → 印 0/0。
        trend_map: `build_trend_map()` 的 {stock_id: favorable_count 0-4}。

    Returns:
        list[str]，每個片語都是「分子/分母」形式，caller 以 ' · ' 串接。
    """
    _f = set(factors or ())
    out: list[str] = []

    if 'shortage' in _f and shortage_rows is not None:
        _n = len(shortage_rows)
        _sig = _count_tier(shortage_rows, _SHORTAGE_SIGNAL_TIERS)
        out.append(f'缺貨 訊號{_sig}/已評分{_n}' if _sig is not None
                   else f'缺貨 已評分{_n}（分級欄缺失，訊號數不明）')

    if 'rs_leader' in _f and rs_rows is not None:
        _n = len(rs_rows)
        _res = _count_tier(rs_rows, _RS_RESILIENT_TIERS)
        # 刻意不寫「抗跌 N」：這份排行含同步/落後分級（beat_only=False）。
        out.append(f'RS 偏強以上{_res}/已排名{_n}' if _res is not None
                   else f'RS 已排名{_n}（分級欄缺失，偏強數不明）')

    if 'trend' in _f and trend_map is not None:
        _n = len(trend_map)
        _fav = sum(1 for v in trend_map.values() if _is_favorable(v))
        out.append(f'跨季 佳項>0 共{_fav}/可算{_n}')

    return out


def render_tab_stock_picker(gemini_fn=None, candidates=None,
                              # H2 2026-08:預設值原為 '高息網' —— 那個模組全 repo 零定義
                              # (見檔頭「呼叫端」段)，而本參數會直接插進 4 處 st.caption /
                              # st.markdown / st.multiselect 標籤渲染到畫面。現況所有 caller
                              # 都顯式傳值(tab_stock_grp='個股組合輸入'、測試='基本面優選')，
                              # 所以這個預設**沒有正在**渲染 —— 但它是「哪天有人漏傳就印出
                              # 不存在模組名」的地雷。改成中性且為真的字串。
                              source_label: str = '上游候選',
                              key_prefix: str = 'picker',
                              *, auto_run: bool = False,
                              auto_pick: bool = False,
                              fh_map: dict | None = None,
                              skip_s3: bool = False):
    """v19.58：source_label + key_prefix 抽參數，個股組合 tab 共用此函式（不複製 Stage 1/2/3 邏輯）。

    candidates: pandas.DataFrame，需含 '代碼' 欄。為 None / 空 → 顯示 info 提示。
    source_label: 候選清單來源顯示名。實際在用的值：'個股組合輸入'(tab_stock_grp)、
    '基本面優選'(測試)。**會渲染到畫面**（caption / multiselect 標籤共 4 處），
    故不得填不存在的模組名（H2 2026-08 移除舊預設 '高息網'）。
    key_prefix: 所有 st.* widget key 前綴，避免同一頁多處渲染碰撞。
    auto_run: v18.223 — True 時跳過「開始三階段篩選」按鈕直接跑，AI 三型報告也自動生成（cache 防 rerun 重跑）。
    fh_map: v18.453 — dict[代碼, analyze_financial_health() 結果]。個股組合 tab 已跑過
    「批次財報體檢」時傳入,Stage 1 負債比檢查會直接沿用其判定(避免同頁兩處門檻不一致);
    未跑財報體檢的呼叫端省略此參數即可,行為與改動前完全相同。
    """
    # ─ Late imports（避免循環 import + 啟動時間）─
    import datetime as _dt_sp
    import pandas as pd

    st.caption(f'從上方「{source_label}」候選清單勾選標的，系統自動跑三階段篩選並提供配置建議。'
               f'全 {len(PICKER_ALL_CONDITIONS)} 項條件：'
               f'3️⃣ 基本面 ×{len(PICKER_S1_CONDITIONS)} → '
               f'4️⃣ 籌碼技術 ×{len(PICKER_S2_CONDITIONS)} → 5️⃣ AI 綜合建議。')

    with st.expander('💡 三階段濾網在篩什麼？（基本面 → 籌碼技術 → AI）', expanded=False):
        # F1 v19.184 §3.3：這段原本把「9 項 / 7% / 6 項 / 6 項」全手抄 ——
        # 而且「過 6 項以上（PICKER_S1_MIN_PASS）」還把常數名寫在旁邊卻不引用它，
        # 正是 v18.466 那個「門檻由 5 改 6、文案漏改」bug 的溫床。全部改插值。
        st.markdown(
            f'**Stage 1 · 基本面防禦（{len(PICKER_S1_CONDITIONS)} 項）**：負債比、'
            f'三率三升（毛利/營益/淨利率同步走高）、連續 5 年配息且均殖利率>{YIELD_HIGH:g}%、'
            f'本益比估值區、應收帳款週轉、存貨週轉、資本支出/股東權益、淨值比、合約負債 YoY。'
            f'→ 過 {PICKER_S1_MIN_PASS} 項以上（`PICKER_S1_MIN_PASS`）視為體質健康。\n\n'
            f'**Stage 2 · 籌碼技術（{len(PICKER_S2_CONDITIONS)} 項）**：站上 20MA 且上彎、'
            f'MACD 翻多、KD 黃金交叉、布林通道開口、三大法人買超、集保大戶持股增加。'
            f'→ 抓「便宜又剛要發動」的時機。\n\n'
            '**Stage 3 · AI 綜合建議**：把上述量化結果＋新聞餵給 AI，輸出客觀的進場/觀望總結與配置權重。\n\n'
            '🎯 核心邏輯：**先用基本面排除地雷，再用籌碼技術抓發動點** —— 避免買到便宜卻沒人要的「價值陷阱」。'
        )

    # ── Section 1：候選清單來自上游篩選結果 ─────────────────────
    if candidates is None or len(candidates) == 0:
        st.info(f'💡 上游「{source_label}」尚未提供候選清單，無法跑三階段。')
        return

    # 去重保序取出純代碼
    _codes: list[str] = []
    for _, _row in candidates.iterrows():
        _c = str(_row.get('代碼') or '').strip()
        if _c and _c not in _codes:
            _codes.append(_c)
    if not _codes:
        st.info(f'💡「{source_label}」候選清單為空，請放寬篩選條件。')
        return

    # v19.59：個股組合輸入場景跳過 multiselect / extra_codes 二次勾選 — 直接拿上方 N 檔全跑出結果
    # v19.89：auto_pick=True（選股網簡易版）同樣跳過手動勾選，直接對上游候選全跑（不要求 USER 勾）
    _t3_mode = auto_pick or (source_label == '個股組合輸入')
    if _t3_mode:
        _preview = ', '.join(_codes[:10]) + ('...' if len(_codes) > 10 else '')
        st.markdown(f'#### 📋 候選清單（已自動帶入上方輸入的 {len(_codes)} 檔）')
        st.caption(f'✅ {_preview}')
        _sel = list(_codes)
        _extra_raw = ''
    else:
        st.markdown(f'#### 📋 候選清單（來自「{source_label}」結果，勾選後跑三階段）')
        _sel = st.multiselect(
            f'從{source_label} {len(_codes)} 檔候選中勾選（建議 10-30 檔，避免 API 風暴）',
            _codes, default=_codes[:10], key=f'{key_prefix}_multiselect',
            help='預設帶入前 10 檔，可自由增減；上限 30 檔')

        _extra_raw = st.text_input(
            f'➕ 額外加入代碼（不在{source_label}清單內也可；逗號或空白分隔，例：6770, 2330 1101）',
            value='', key=f'{key_prefix}_extra_codes',
            help='手動補進想一起跑三階段的個股，會與上方勾選自動合併、去重；台股代號 4-6 碼')

    # ── 解析清單（勾選 + 手動輸入，合併去重）——移到按鈕前，供「已跑過」旗標綁定 ──
    import re as _re_pk
    from src.compute.etf import bare_etf_code as _bare
    _extra: list[str] = []
    _bad:   list[str] = []
    for _c0 in _re_pk.split(r'[,\s、，;；]+', (_extra_raw or '').strip()):
        if not _c0:
            continue
        _c = _bare(_c0)
        if _re_pk.fullmatch(r'\d{4,6}[A-Z]?', _c):
            _extra.append(_c)
        else:
            _bad.append(_c0)
    _tickers = list(dict.fromkeys(list(_sel) + _extra))
    if _bad:
        st.warning(f'⚠️ 略過無法識別的代碼：{", ".join(_bad)}（台股代號應為 4-6 碼數字）')
    if not _tickers:
        st.info('💡 請至少勾選一檔候選股票，或於上方手動輸入代碼')
        return
    if len(_tickers) > 30:
        st.warning(f'⚠️ 超過 30 檔（{len(_tickers)}），僅取前 30 檔避免 API 風暴')
        _tickers = _tickers[:30]
    if _extra:
        st.caption(f'➕ 已併入手動代碼 {len(_extra)} 檔：{", ".join(_extra)}')

    # v18.223：auto_run 跳過按鈕。v19.61：按一次後用 session_state 記住「已跑過這組股票」，
    # 之後動下方「自訂條件」勾選觸發 rerun 也不會讓結果消失（旗標 key 綁定 ticker 集合 →
    # 只有『換候選股票』才需要重按，動條件不會重跑昂貴的三階段掃描）。
    _ran_key = f'{key_prefix}_ran_{hash(tuple(_tickers))}'
    if not auto_run:
        if st.button('🎯 開始三階段篩選', key=f'{key_prefix}_btn',
                     use_container_width=True, type='primary'):
            st.session_state[_ran_key] = True
        if not st.session_state.get(_ran_key):
            if _t3_mode:
                st.info(f'💡 按「🎯 開始三階段篩選」分析 {len(_codes)} 檔（並行 ~30s）')
            else:
                st.info('💡 勾選候選股票後按「🎯 開始三階段篩選」')
            return

    # ── 跑三階段篩選（ThreadPoolExecutor 並行，v18.223 加 cache 防 rerun 重跑）──
    # 原本序列跑 N 檔，每檔 ~2 yfinance + ~4 FinMind ≈ 上百次阻塞請求逐一等。
    # _check_one_stock 線程安全（獨立 requests + yfinance、無 st.*、無共享 loader），
    # 故無需鎖；總請求數不變（FinMind 限額為每小時制），純粹把 I/O 等待重疊。
    _pick_cache_key = f'{key_prefix}_results_{hash(tuple(_tickers))}'
    results = st.session_state.get(_pick_cache_key)
    if results is None:
        _today = _dt_sp.date.today()
        from concurrent.futures import ThreadPoolExecutor
        _idx_results: dict[int, dict] = {}
        with st.spinner(f'三階段篩選中（{len(_tickers)} 檔，並行）...'):
            with ThreadPoolExecutor(max_workers=5) as _pick_exec:
                _pick_futs = {
                    _pick_exec.submit(_check_one_stock, _tk, _today,
                                      (fh_map or {}).get(_tk)): _i
                    for _i, _tk in enumerate(_tickers)
                }
            for _fut, _i in _pick_futs.items():
                try:
                    _idx_results[_i] = _fut.result()
                except Exception as _e_pick:
                    print(f'[picker] {_tickers[_i]}: {type(_e_pick).__name__}: {_e_pick}')
                    _idx_results[_i] = _blank_pick_result(_tickers[_i], note='❌ 分析失敗')
        results: list[dict] = [_idx_results[_i] for _i in range(len(_tickers))]
        st.session_state[_pick_cache_key] = results

    # ── Stage 1：基本面表 ─────────────────────────────────────
    st.markdown('#### 3️⃣ 基本面防禦篩選')
    _s1_df = pd.DataFrame([{
        '代號':       r['ticker'],
        '負債比':     r['debt_ratio_label'],
        '三率三升':   r['three_rate_label'],
        '5Y 配息':    r['div_5y_label'],
        'PE 區間':    r['pe_zone_label'],
        '應收周轉':   r['ar_turnover_label'],
        '存貨周轉':   r['inv_turnover_label'],
        '資本支出':   r['capex_label'],
        '淨流動值':   r['book_value_label'],
        '合約負債':   r['contract_liab_label'],
        'S1 通過':    f"{r['s1_pass_cnt']}/9",
    } for r in results])
    st.dataframe(_s1_df, hide_index=True, use_container_width=True)
    # F1 v19.184 §3.3：門檻全部插 SSOT（見檔頭 `PICKER_*` 區塊註解）。
    st.caption(f'💡 通過數 = {len(PICKER_S1_CONDITIONS)} 項實作條件中過的個數；'
               f'{PICKER_S1_MIN_PASS}+ 通過視為基本面健康。'
               f'「應收周轉」穩定 = 季變動 < {PICKER_AR_TURNOVER_STABLE_QOQ_PCT:g}%；'
               f'「存貨周轉」OK = 年化 > {PICKER_INV_TURNOVER_MIN_TIMES:g} 次；'
               f'「資本支出」積極 = CapEx > 股東權益 '
               f'{PICKER_CAPEX_EQUITY_MIN_RATIO * 100:g}%；'
               f'「淨流動值」OK = 流動資產 > 總負債；'
               f'「合約負債」OK = YoY > {PICKER_CONTRACT_LIAB_YOY_MIN_PCT:g}% '
               f'且連 {PICKER_CONTRACT_LIAB_QOQ_QUARTERS} 季增。'
               + ('「負債比」判定與上方「批次財報體檢」共用同一套門檻（不會兩處顯示不同顏色）。'
                  if fh_map else ''))

    # ── Stage 2：籌碼 + 技術 ──────────────────────────────────
    st.markdown('#### 4️⃣ 籌碼與技術鎖定')
    _s2_df = pd.DataFrame([{
        '代號':       r['ticker'],
        'MA20 站穩':  r['ma20_label'],
        'MACD 翻紅':  r['macd_label'],
        'KD 黃叉':    r['kd_label'],
        '布林開口':   r['boll_label'],
        '投信買超':   r['inst_label'],
        '大戶持股':   r['major_label'],
        '位階(追高)': r.get('overheat_label', '❓ N/A'),
        'S2 通過':    f"{r['s2_pass_cnt']}/6",
    } for r in results])
    st.dataframe(_s2_df, hide_index=True, use_container_width=True)
    st.caption(f'💡 S1 ≥ {PICKER_S1_MIN_PASS}/{len(PICKER_S1_CONDITIONS)} 且 '
               f'S2 ≥ {PICKER_S2_MIN_PASS}/{len(PICKER_S2_CONDITIONS)} → 進入 Stage 3 AI 重點分析。'
               f'「布林開口」= 近 {PICKER_BOLL_RECENT_DAYS} 日 band 寬度 > 前 '
               f'{PICKER_BOLL_BASELINE_DAYS} 日 {PICKER_BOLL_OPENING_RATIO:g} 倍；'
               f'「投信買超」= 近 {PICKER_INST_BUY_STREAK_DAYS} 日連續買超；'
               f'「大戶持股」= ≥1000 張級距近 2 週比例增加。')

    # ── ⚠️ 追高風險警示(v19.62：位階過熱 = 遠離均線 / RSI 過熱)──
    _hot = [r for r in results
            if str(r.get('overheat_label', '')).startswith(('🔴', '🟡'))]
    if _hot:
        _hot_txt = '、'.join(f"{r['ticker']}({str(r['overheat_label']).split('｜')[0][2:]})"
                             for r in _hot)
        st.warning(f'🚫 **追高風險**：{len(_hot)} 檔位階偏高 → {_hot_txt}')
        st.caption('💡 「位階」是把「熱門」降級成**警示**：新聞越熱、股價常已噴出，'
                   '**遠離均線 / RSI 過熱 = 題材已發酵，追高風險大**。體質好也要等**拉回**再進，'
                   '別追在頭部。')

    # ── 🎛️ 自訂必過條件（v19.61：改打勾格子，一次全看得到，比下拉選單好操作）──
    st.markdown('#### 🎛️ 自訂必過條件（可選）')
    # F1 v19.184 §3.3：「S1≥6 且 S2≥3」「基本面 9 項」「籌碼技術 6 項」原為手抄。
    st.caption(f'勾你要求的條件，再設下方「至少過幾項」；'
               f'全部不勾 = 用預設 S1≥{PICKER_S1_MIN_PASS} 且 S2≥{PICKER_S2_MIN_PASS}。'
               f'（勾選會即時重篩，不會重跑三階段掃描）')
    _sel_keys: list[str] = []
    for _grp_title, _grp_conds in (
            (f'基本面 {len(PICKER_S1_CONDITIONS)} 項', PICKER_S1_CONDITIONS),
            (f'籌碼技術 {len(PICKER_S2_CONDITIONS)} 項', PICKER_S2_CONDITIONS)):
        st.markdown(f'**{_grp_title}**')
        _cb_cols = st.columns(3)
        for _ci, (_ck, _cname) in enumerate(_grp_conds):
            if _cb_cols[_ci % 3].checkbox(_cname, key=f'{key_prefix}_cb_{_ck}'):
                _sel_keys.append(_ck)
    _min_pass = len(_sel_keys)
    if _sel_keys:
        # key 綁定勾選數量：改變勾選數時重置 value（避免舊值 > 新上限的 clamp 錯誤）
        _min_pass = st.number_input(
            f'這些條件裡至少要過幾項（1 ~ {len(_sel_keys)}）',
            min_value=1, max_value=len(_sel_keys), value=len(_sel_keys),
            step=1, key=f'{key_prefix}_cond_minpass_{len(_sel_keys)}')

    # ── 通過清單：自訂條件優先；未啟用則走預設門檻（S1≥6 & S2≥3，SSOT）──
    _custom = filter_by_custom_conditions(results, _sel_keys, int(_min_pass))
    if _custom is not None:
        _qualified = _custom
        st.caption(f'🎛️ 自訂模式：{len(PICKER_ALL_CONDITIONS)} 項中選 {len(_sel_keys)} 項、'
                   f'至少過 {int(_min_pass)} 項')
        _crit_txt = f'自訂條件（{len(_sel_keys)} 選 {int(_min_pass)} 過）'
    else:
        _qualified = [r for r in results
                      if r['s1_pass_cnt'] >= PICKER_S1_MIN_PASS
                      and r['s2_pass_cnt'] >= PICKER_S2_MIN_PASS]
        _crit_txt = (f'S1 ≥ {PICKER_S1_MIN_PASS}/{len(PICKER_S1_CONDITIONS)} 且 '
                     f'S2 ≥ {PICKER_S2_MIN_PASS}/{len(PICKER_S2_CONDITIONS)}')
    if _qualified:
        st.success(f'✅ 符合條件（{_crit_txt}）：{len(_qualified)} 檔 → {[r["ticker"] for r in _qualified]}')
    else:
        st.warning(f'⚠️ 觀察清單中沒有符合條件（{_crit_txt}）的標的')

    # v18.xxx: skip_s3 模式 — 倒序選股流程，跳過 AI S3，將通過清單存入 session_state 供下方殖利率確認使用
    if skip_s3:
        st.session_state[f'{key_prefix}_s1s2_qualified_tickers'] = (
            [r['ticker'] for r in _qualified]
        )
        return

    # ── Stage 3：AI 綜合建議 ──────────────────────────────────
    st.markdown('#### 5️⃣ AI 綜合操作建議')
    if not gemini_fn:
        st.warning('⚠️ 未設定 GEMINI_API_KEY，無法生成 AI 建議')
        return
    if not _qualified:
        st.info('💡 無通過標的可生成 AI 建議；可嘗試擴大觀察清單或放寬條件')
        return
    # v18.223：auto_run 模式跳過 AI 按鈕，自動生成（cache 防 rerun 重打 Gemini）
    _ai_cache_key = (
        f'{key_prefix}_ai_md_'
        f'{hash(tuple(q["ticker"] for q in _qualified))}'
    )
    if auto_run:
        _md = st.session_state.get(_ai_cache_key)
        if _md is None:
            with st.spinner('AI 三型策略分析中（約 8-12 秒）...'):
                _md = _generate_ai_report(gemini_fn, _qualified, results)
            st.session_state[_ai_cache_key] = _md
        st.markdown(_md)
    elif st.button('🤖 生成 AI 三型建議報告（積極 / 保守 / 止損紀律）',
                   key=f'{key_prefix}_ai_btn',
                   use_container_width=True, type='primary'):
        _md = st.session_state.get(_ai_cache_key)
        if _md is None:
            with st.spinner('AI 三型策略分析中（約 8-12 秒）...'):
                _md = _generate_ai_report(gemini_fn, _qualified, results)
            st.session_state[_ai_cache_key] = _md
        st.markdown(_md)


# ══════════════════════════════════════════════════════════════
# 主檢測函式：對單檔個股跑完所有可實作條件
# ══════════════════════════════════════════════════════════════

def _blank_pick_result(ticker: str, note: str = '') -> dict:
    """選股結果骨架（Stage 1×9 + Stage 2×6 全 ❓ N/A）。
    _check_one_stock 起手 + 並行錯誤路徑共用，確保下游一律拿到完整 key。"""
    return {
        'ticker': ticker,
        'note':   note,
        # Stage 1 labels (9 條件)
        'debt_ratio_label':   '❓ N/A',
        'three_rate_label':   '❓ N/A',
        'div_5y_label':       '❓ N/A',
        'pe_zone_label':      '❓ N/A',
        'ar_turnover_label':  '❓ N/A',
        'inv_turnover_label': '❓ N/A',
        'capex_label':        '❓ N/A',
        'book_value_label':   '❓ N/A',
        'contract_liab_label':'❓ N/A',
        's1_pass_cnt':        0,
        # Stage 2 labels (6 條件)
        'ma20_label':         '❓ N/A',
        'macd_label':         '❓ N/A',
        'kd_label':           '❓ N/A',
        'boll_label':         '❓ N/A',
        'inst_label':         '❓ N/A',
        'major_label':        '❓ N/A',
        's2_pass_cnt':        0,
        'overheat_label':     '❓ N/A',   # 位階(追高風險)
    }


def _check_one_stock(ticker: str, today, fh_result: dict | None = None) -> dict:
    """對單檔個股跑完 Stage 1 + Stage 2 — 失敗條件統一回灰色 ❓ 不阻斷流程。
    全程獨立 requests + yfinance、零 st.* 呼叫 → 線程安全，可丟進 ThreadPoolExecutor。

    P1-1a v18.374:yfinance K 線直呼抽至 L1 fetcher(`src.data.stock.picker_fetcher`)。
    (v19.159:原 backward-compat `yf` 幽靈參數已移除 — 內部早不用。)

    fh_result:v18.453 — 個股組合場景已由「批次財報體檢」算好的
    analyze_financial_health() 結果(dict,鍵含 financial_structure_module 等 6 子模組)。
    有提供時,負債比檢查直接沿用其判定,避免同一頁兩處門檻不一致。
    """
    from src.data.stock.picker_fetcher import fetch_stock_history_1y
    _r = _blank_pick_result(ticker)
    # ── 抓 K 線(P1-1a:L1 fetcher 內含 .TW/.TWO 雙後綴 fallback)──
    _df, _resolved_ticker = fetch_stock_history_1y(ticker)
    if _df is None:
        _r['ma20_label'] = '❌ 抓不到 K 線'
        _r['macd_label'] = '❌ 抓不到 K 線'
        _r['kd_label'] = '❌ 抓不到 K 線'
        _r['boll_label'] = '❌ 抓不到 K 線'
        return _r
    # B7 v19.154:5Y 配息檢查改走 L1 cached_dividends(NAS proxy + 1h cache),
    # 取代原 L5 直呼 yfinance.Ticker(違 §8.2);回傳同一份 .dividends Series。
    from src.data.proxy import cached_dividends
    _divs5 = cached_dividends(_resolved_ticker)

    # ── 一次抓財報（多個 Stage 1 helpers 共用）──────────────
    _fs = _fetch_fs_safe(ticker)
    _qis = _fetch_quarterly_is(ticker)   # 多季損益表（三率三升 + PE TTM 共用）

    # ── Stage 1 條件 ──────────────────────────────────────────
    _r['debt_ratio_label']  = _check_debt_ratio(_fs, fh_result)
    _r['three_rate_label']  = _check_three_rate_growth(_qis)
    _r['div_5y_label']      = _check_dividend_5y(_df, _divs5)
    _r['pe_zone_label']     = _check_pe_zone(_qis, _df)
    _r['ar_turnover_label'] = _check_ar_turnover(_fs)
    _r['inv_turnover_label']= _check_inventory_turnover(_fs)
    _r['capex_label']       = _check_capex_vs_equity(_fs)
    _r['book_value_label']    = _check_book_value(_fs, _df)
    _r['contract_liab_label'] = _check_contract_liab_yoy(ticker)
    _r['s1_pass_cnt'] = sum(1 for k in (
        'debt_ratio_label', 'three_rate_label', 'div_5y_label', 'pe_zone_label',
        'ar_turnover_label', 'inv_turnover_label', 'capex_label', 'book_value_label',
        'contract_liab_label',
    ) if _r[k].startswith('✅'))

    # ── Stage 2 條件 ──────────────────────────────────────────
    _r['ma20_label']  = _check_ma20_uptrend(_df)
    _r['macd_label']  = _check_macd_bullish(_df)
    _r['kd_label']    = _check_kd_golden_cross(_df)
    _r['boll_label']  = _check_bollinger_opening(_df)
    _r['inst_label']  = _check_institutional_buying(ticker)
    _r['major_label'] = _check_major_holders(ticker)
    _r['s2_pass_cnt'] = sum(1 for k in ('ma20_label', 'macd_label', 'kd_label',
                                          'boll_label', 'inst_label', 'major_label')
                              if _r[k].startswith('✅'))

    # ── 位階過熱(追高風險 v19.62):遠離 MA20 / RSI 過熱 → 別追高 ──
    try:
        from src.compute.strategy.overextension import overextension_label
        _close = _df['Close'] if 'Close' in _df.columns else _df.iloc[:, 0]
        _r['overheat_label'] = overextension_label(_close)
    except Exception as _e_oh:
        print(f'[picker] {ticker} overheat: {type(_e_oh).__name__}: {_e_oh}')
        _r['overheat_label'] = '❓ N/A'
    return _r


def _fetch_fs_safe(stock_id: str) -> dict:
    """安全包裝 data_loader.fetch_financial_statements。失敗回 {}。"""
    try:
        from src.data.core import fetch_financial_statements
        from src.data.core.provenance import prov_log
        _r = fetch_financial_statements(stock_id)
        _result = _r if isinstance(_r, dict) and 'error' not in _r else {}
        # v18.356 PR-Q5b S-PROV-1 phase 19 — prov_log emits [_fetch_fs_safe] marker
        prov_log('_fetch_fs_safe', 'src.data.core.financial_statements_fetcher.fetch_financial_statements',
                 f'dict:{len(_result)}keys', ticker=stock_id)
        return _result
    except Exception as e:
        print(f'[picker/fs] {stock_id}: {type(e).__name__}: {e}')
        return {}


# ══════════════════════════════════════════════════════════════
# Stage 1 純函式（基本面）
# ══════════════════════════════════════════════════════════════

def _check_debt_ratio(fs: dict, fh_result: dict | None = None) -> str:
    """負債比健康度。

    v18.453:個股組合場景已有「批次財報體檢」(analyze_financial_health)結果時
    (fh_result 非 None),直接沿用其 financial_structure_module.Debt_Ratio 判定 ——
    與本函式舊版各自獨立計算相比,同一檔股票不會在「財報體檢」顯示🟡、「智慧選股」
    卻顯示✅(user 回報:兩張表門檻不一致造成混淆,40/60% 三級 vs 本函式舊版 <50%
    二分)。financial_health_engine 版本另有負債比為 0 時從原始科目重算的 fallback,
    判定更完整。無 fh_result(未跑財報體檢的呼叫場景)則維持原邏輯。
    """
    if fh_result:
        _fsm = fh_result.get('financial_structure_module', {}).get('Debt_Ratio', {})
        _status = _fsm.get('Status')
        _val = _fsm.get('Value', '')
        if _status == 'Pass':
            return f'✅ {_val}'
        if _status == 'Warning':
            return f'⚠️ {_val}'
        if _status == 'Fail':
            return f'❌ {_val}'
        # Status 為 N/A(如金融股/資料不足)→ 落回下方獨立計算,不放棄判定機會
    if not fs:
        return '❓ 無財報'
    _ratio = fs.get('負債比率(%)')
    if _ratio is None:
        return '❓ N/A'
    try:
        _v = float(_ratio)
    except (TypeError, ValueError):
        return '❓ N/A'
    if fs.get('is_finance'):
        return f'⚠️ 金融股 {_v:.1f}%'
    return f'✅ {_v:.1f}%' if _v < 50 else f'❌ {_v:.1f}%'


def _fetch_quarterly_is(stock_id: str) -> dict:
    """抓 FinMind 近 8 季損益表 → {date: {type: value}}（多 helper 共用，避免重複打 API）。

    回傳 dict（含 '_dates' key 為由近到遠排序的日期 list）；失敗回 {}。
    """
    import os as _os_q
    import datetime as _dt_q
    import requests as _rq_q
    from src.data.core.provenance import prov_log
    try:
        _tok = _os_q.environ.get('FINMIND_TOKEN', '')
        _start = (_dt_q.date.today() - _dt_q.timedelta(days=900)).strftime('%Y-%m-%d')
        _p = {'dataset': 'TaiwanStockFinancialStatements',
              'data_id': stock_id, 'start_date': _start}
        # v19.170:憑證只走 header,不進 query string(避免落入 proxy / access log)
        # 原本無 headers,先補 data_loader._fm_raw_headers SSOT(帶 Bearer + UA)再移除 params token。
        from src.data.core.data_loader import _fm_raw_headers as _fm_hdrs_q
        _r = _rq_q.get(FINMIND_API_URL,
                       params=_p, headers=_fm_hdrs_q(_tok), timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        if not _data:
            return {}
        _quarters: dict = {}
        for _row in _data:
            _d = _row.get('date', '')
            _t = _row.get('type', '')
            try:
                _v = float(str(_row.get('value', 0) or 0).replace(',', ''))
            except (TypeError, ValueError):
                continue
            _quarters.setdefault(_d, {})[_t] = _v
        _quarters['_dates'] = sorted([d for d in _quarters if d != '_dates'], reverse=True)
        # v18.356 PR-Q5b S-PROV-1 phase 19 — prov_log emits [_fetch_quarterly_is] marker
        prov_log('_fetch_quarterly_is', 'FinMind:TaiwanStockFinancialStatements',
                 f'dict:{len(_quarters)-1}quarters', ticker=stock_id)
        return _quarters
    except Exception as _e:
        print(f'[picker/is] {stock_id}: {type(_e).__name__}: {_e}')
        return {}


def _check_three_rate_growth(qis: dict) -> str:
    """三率三升：毛利率 / 營益率 / 淨利率近季 YoY 同步成長（用共用 _fetch_quarterly_is 結果）。"""
    if not qis:
        return '❓ FinMind 無資料'
    _dates = qis.get('_dates', [])
    if len(_dates) < 5:
        return f'❓ 僅 {len(_dates)} 季'
    _lat, _yoy = qis[_dates[0]], qis[_dates[4]]

    def _margin(slot, num_keys, denom='Revenue'):
        _r = slot.get(denom, 0)
        if _r <= 0:
            return None
        _n = sum(slot.get(k, 0) for k in num_keys)
        return _n / _r * 100 if _r else None

    _now_gm = _margin(_lat, ['GrossProfit', 'GrossProfitLoss'])
    _yoy_gm = _margin(_yoy, ['GrossProfit', 'GrossProfitLoss'])
    _now_om = _margin(_lat, ['OperatingIncome', 'OperatingIncomeLoss'])
    _yoy_om = _margin(_yoy, ['OperatingIncome', 'OperatingIncomeLoss'])
    _now_nm = _margin(_lat, ['IncomeAfterTaxes', 'NetIncome', 'ProfitAfterTax'])
    _yoy_nm = _margin(_yoy, ['IncomeAfterTaxes', 'NetIncome', 'ProfitAfterTax'])
    _pairs = [(_now_gm, _yoy_gm), (_now_om, _yoy_om), (_now_nm, _yoy_nm)]
    _valid = [(n, y) for n, y in _pairs if n is not None and y is not None]
    if not _valid:
        return '❓ 利潤欄位缺'
    _ups = sum(1 for n, y in _valid if n > y)
    return f'✅ {_ups}/3 升' if _ups == 3 else f'❌ {_ups}/3 升'



def _check_dividend_5y(df, divs) -> str:
    """連續 5 年配息 + 平均殖利率 > 7%。divs = L1 cached_dividends 回的 .dividends Series。"""
    try:
        _divs = divs
        if _divs is None or _divs.empty or len(_divs) < 5:
            return '❌ 配息 <5 次'
        # 年度化 — 最近 5 年除息總額
        import pandas as _pd_d
        _divs.index = _pd_d.to_datetime(_divs.index)
        try:
            _divs.index = _divs.index.tz_localize(None)
        except Exception:
            pass
        _last5y = _divs.last('5Y') if hasattr(_divs, 'last') else _divs.tail(5)
        # 5 年平均年配
        _avg_annual_div = _last5y.sum() / 5 if len(_last5y) > 0 else 0
        _cur_price = float(df['Close'].iloc[-1])
        _yield_pct = (_avg_annual_div / _cur_price * 100) if _cur_price > 0 else 0
        if len(_divs.last('5Y') if hasattr(_divs, 'last') else _divs) >= 5 and _yield_pct > YIELD_HIGH:
            return f'✅ {_yield_pct:.2f}%'
        elif _yield_pct > 0:
            return f'❌ {_yield_pct:.2f}%'
        else:
            return '❌ 無配息'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_pe_zone(qis: dict, df) -> str:
    """PE 河流圖區間 — 用真正 TTM EPS（近 4 季 EPS 加總），三分位判讀便宜/合理/昂貴。

    回退：若多季 IS 不足 4 季，無法算真 TTM → 回 ❓（不再用單季 ×4 粗估誤判）。
    """
    if not qis:
        return '❓ 無財報'
    _dates = qis.get('_dates', [])
    if len(_dates) < 4:
        return f'❓ EPS 僅 {len(_dates)} 季'
    try:
        # TTM EPS = 近 4 季 EPS 加總
        _eps_ttm = 0.0
        _found = 0
        for _d in _dates[:4]:
            _slot = qis[_d]
            _eps_q = _slot.get('EPS')
            if _eps_q is None:
                continue
            _eps_ttm += float(_eps_q)
            _found += 1
        if _found < 4:
            return f'❓ EPS 缺 {4 - _found} 季'
        if _eps_ttm <= 0:
            return '⚠️ 虧損股'
        _cur = float(df['Close'].iloc[-1])
        _pe = _cur / _eps_ttm
        if _pe < 10:
            return f'✅ 便宜 {_pe:.1f}'
        elif _pe < 15:
            return f'✅ 合理 {_pe:.1f}'
        elif _pe < 20:
            return f'❌ 昂貴 {_pe:.1f}'
        else:
            return f'❌ 超昂貴 {_pe:.1f}'
    except (TypeError, ValueError, ZeroDivisionError) as _e:
        return f'❓ {type(_e).__name__}'


def _check_ar_turnover(fs: dict) -> str:
    """應收周轉天數穩定（季增率 < `PICKER_AR_TURNOVER_STABLE_QOQ_PCT`% 視為穩定）。"""
    if not fs:
        return '❓ 無財報'
    _days = fs.get('應收帳款天數')
    _chg = fs.get('應收帳款季增率(%)')
    if _days is None:
        return '❓ N/A'
    try:
        _d = float(_days)
        # 季增率 None or 在 ±門檻內 視為穩定（門檻與下方 caption 同一常數，F1 v19.184）
        _stable = _chg is None or abs(float(_chg)) < PICKER_AR_TURNOVER_STABLE_QOQ_PCT
        return f'✅ {_d:.0f}天' if _stable else f'❌ {_d:.0f}天 季變{_chg:+.0f}%'
    except (TypeError, ValueError):
        return '❓ N/A'


def _check_inventory_turnover(fs: dict) -> str:
    """存貨周轉率 = COGS / 平均存貨（年化） — 近季未異常下滑（>4 OK）。"""
    if not fs:
        return '❓ 無財報'
    _cogs = fs.get('營業成本(千)') or 0
    _inv = fs.get('存貨(千)') or 0
    _inv_p = fs.get('存貨前期(千)') or 0
    if _inv <= 0 and _inv_p <= 0:
        return '⚠️ 無存貨（金融/服務業）'
    try:
        _avg_inv = (float(_inv) + float(_inv_p)) / 2 if (_inv_p > 0) else float(_inv)
        if _avg_inv <= 0:
            return '❓ 存貨=0'
        _turnover = (float(_cogs) * 4) / _avg_inv   # 年化（×4 = 每年 4 季，日曆常數非門檻）
        return (f'✅ {_turnover:.1f}次/年'
                if _turnover > PICKER_INV_TURNOVER_MIN_TIMES
                else f'❌ {_turnover:.1f}次/年')
    except (TypeError, ValueError, ZeroDivisionError):
        return '❓ N/A'


def _check_capex_vs_equity(fs: dict) -> str:
    """資本支出積極（近一季 CapEx > 股東權益 0.05 倍 → 年化約 0.2，視為積極擴廠）。

    註：原 prompt 寫「資本支出 > 股本 0.8 倍」，但「股本」未在 fetch_fin 出，改用「股東權益」
    更穩定的 proxy；閾值校正為單季 0.05 ≈ 年化 0.2。
    """
    if not fs:
        return '❓ 無財報'
    _capex = fs.get('資本支出(千)') or 0
    _equity = fs.get('股東權益(千)') or 0
    if _equity <= 0:
        return '❓ N/A'
    try:
        _ratio = abs(float(_capex)) / float(_equity)
        return (f'✅ {_ratio*100:.1f}%/權益'
                if _ratio > PICKER_CAPEX_EQUITY_MIN_RATIO
                else f'❌ {_ratio*100:.1f}%/權益')
    except (TypeError, ValueError, ZeroDivisionError):
        return '❓ N/A'


def _check_book_value(fs: dict, df) -> str:
    """簡化清算價值：(流動資產 - 總負債) > 0 視為股東有淨清算保護。

    完整清算價值需流通股數，本版用「淨流動資產為正」判讀。
    """
    if not fs:
        return '❓ 無財報'
    _ca = fs.get('流動資產(千)') or 0
    _liab = fs.get('總負債(千)') or 0
    if _ca <= 0:
        return '❓ N/A'
    try:
        # fs 值單位為「千元」→ 換算億元：千 / 1e5
        _ncw_yi = (float(_ca) - float(_liab)) / 1e5
        if _ncw_yi > 0:
            return f'✅ 淨流動 +{_ncw_yi:,.0f}億'
        else:
            return f'❌ 淨流動 {_ncw_yi:,.0f}億'
    except (TypeError, ValueError):
        return '❓ N/A'


def _check_contract_liab_yoy(stock_id: str) -> str:
    """合約負債 YoY > 20% + 近兩季季增（在手訂單成長指標）。"""
    try:
        import os as _os_cl
        import datetime as _dt_cl
        import requests as _rq_cl
        _tok = _os_cl.environ.get('FINMIND_TOKEN', '')
        _start = (_dt_cl.date.today() - _dt_cl.timedelta(days=900)).strftime('%Y-%m-%d')
        _p = {'dataset': 'TaiwanStockBalanceSheet',
              'data_id': stock_id, 'start_date': _start}
        # v19.170:憑證只走 header,不進 query string(避免落入 proxy / access log)
        # 原本無 headers,先補 data_loader._fm_raw_headers SSOT(帶 Bearer + UA)再移除 params token。
        from src.data.core.data_loader import _fm_raw_headers as _fm_hdrs_cl
        _r = _rq_cl.get(FINMIND_API_URL,
                         params=_p, headers=_fm_hdrs_cl(_tok), timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        if not _data:
            return '❓ FinMind 無 BS'
        # 合約負債別名（含「－流動」「－非流動」需 sum）
        _aliases = ('合約負債', '合約負債－流動', '合約負債－非流動',
                    '預收款項', '遞延收入', 'ContractLiability', 'ContractLiabilities')
        _quarters: dict = {}  # date → 合約負債 sum
        for _row in _data:
            _t = str(_row.get('type', ''))
            _name = str(_row.get('origin_name', ''))
            if not any(a in _t or a in _name for a in _aliases):
                continue
            try:
                _v = float(str(_row.get('value', 0) or 0).replace(',', ''))
            except (TypeError, ValueError):
                continue
            if _v <= 0:
                continue
            _d = _row.get('date', '')
            _quarters[_d] = _quarters.get(_d, 0) + _v
        _dates = sorted(_quarters.keys(), reverse=True)
        if len(_dates) < 5:
            return f'❓ {len(_dates)}季 不足'
        _now = _quarters[_dates[0]]
        _yoy = _quarters[_dates[4]]
        _prev = _quarters[_dates[1]]
        _prev2 = _quarters[_dates[2]] if len(_dates) > 2 else 0
        _yoy_pct = (_now - _yoy) / _yoy * 100 if _yoy > 0 else 0
        _qoq_2 = _now > _prev > _prev2  # 連兩季季增（= PICKER_CONTRACT_LIAB_QOQ_QUARTERS）
        if _yoy_pct > PICKER_CONTRACT_LIAB_YOY_MIN_PCT and _qoq_2:
            return (f'✅ YoY+{_yoy_pct:.0f}% '
                    f'連{PICKER_CONTRACT_LIAB_QOQ_QUARTERS}季增')
        if _yoy_pct > PICKER_CONTRACT_LIAB_YOY_MIN_PCT:
            return f'⚠️ YoY+{_yoy_pct:.0f}% 季未連增'
        return f'❌ YoY{_yoy_pct:+.0f}%'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


# ══════════════════════════════════════════════════════════════
# Stage 2 純函式（籌碼 + 技術）
# ══════════════════════════════════════════════════════════════

def _check_ma20_uptrend(df) -> str:
    """股價 > MA20 且 MA20 翻揚（近 5 日 MA20 斜率為正）。"""
    try:
        # C5 v18.403:MA series 計算下沉 L2 SSOT
        from src.compute.strategy.tech_indicators import calc_ma_series
        _ma20 = calc_ma_series(df['Close'], window=20)
        if len(_ma20.dropna()) < 5:
            return '❓ 不足 25 日'
        _cur = float(df['Close'].iloc[-1])
        _ma20_now = float(_ma20.iloc[-1])
        _ma20_5d_ago = float(_ma20.iloc[-6])
        _above = _cur > _ma20_now
        _rising = _ma20_now > _ma20_5d_ago
        if _above and _rising:
            return '✅ 站穩翻揚'
        elif _above:
            return '⚠️ 站穩未翻揚'
        else:
            return '❌ 跌破'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_macd_bullish(df) -> str:
    """MACD 綠轉紅（DIF-DEA 由負轉正）or 柱狀體由收斂轉發散。"""
    try:
        from src.compute.scoring.exit_signals import compute_macd
        # 日 MACD 標準 12/26/9(B6 kernel);沿用舊 adjust=True(pandas ewm 預設)維持既有數值
        _dif, _dea, _macd = compute_macd(df['Close'], adjust=True)
        if len(_macd.dropna()) < 3:
            return '❓ 不足 30 日'
        _now = float(_macd.iloc[-1])
        _prev = float(_macd.iloc[-2])
        _prev2 = float(_macd.iloc[-3])
        # 綠轉紅：前一日負今日正
        if _prev < 0 and _now > 0:
            return '✅ 綠轉紅'
        # 柱狀體放大（已紅且擴大）
        if _now > 0 and _now > _prev > _prev2:
            return '✅ 柱狀放大'
        if _now > 0:
            return '⚠️ 紅但收斂'
        return '❌ 仍綠'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_bollinger_opening(df) -> str:
    """布林通道剛開口（band 寬度近 5 日均值 > 前 20 日均值 1.3 倍 → 突破前的瘦窄轉放大）。

    註：tech_indicators.calc_bollinger 只回最後一日純量 dict，無法算寬度時序，
    故此處自行 rolling 計算整段 band-width series。
    """
    try:
        # C5 v18.403:bandwidth series 計算下沉 L2 SSOT
        from src.compute.strategy.tech_indicators import calc_bollinger_width_series
        _close = df['Close']
        if len(_close.dropna()) < 25:
            return '❓ 不足 25 日'
        _width = calc_bollinger_width_series(_close, window=20, k=2.0).dropna()
        if len(_width) < 25:
            return '❓ 不足 25 日'
        _recent = _width.iloc[-PICKER_BOLL_RECENT_DAYS:].mean()
        _baseline = _width.iloc[
            -(PICKER_BOLL_RECENT_DAYS + PICKER_BOLL_BASELINE_DAYS):
            -PICKER_BOLL_RECENT_DAYS].mean()
        if _baseline <= 0:
            return '❓ baseline=0'
        _ratio = _recent / _baseline
        if _ratio > PICKER_BOLL_OPENING_RATIO:
            return f'✅ 開口 ×{_ratio:.2f}'
        elif _ratio > 1.0:
            return f'⚠️ 微擴 ×{_ratio:.2f}'
        else:
            return f'❌ 收斂 ×{_ratio:.2f}'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_kd_golden_cross(df) -> str:
    """KD 低檔（K<20）黃金交叉。

    註：tech_indicators.calc_kd 只回最後一日純量 (k, d)，無法判斷「昨日 K<D 今日 K>D」
    的交叉，故此處自行算 K/D series。
    """
    try:
        # C5 v18.403:KD series 計算下沉 L2 SSOT
        from src.compute.strategy.tech_indicators import calc_kd_series
        if len(df) < 11:
            return '❓ 不足 9 日'
        _k, _d = calc_kd_series(df['Close'], df['High'], df['Low'], period=9)
        _k = _k.dropna()
        _d = _d.dropna()
        if len(_k) < 2 or len(_d) < 2:
            return '❓ 不足 9 日'
        _k_now, _d_now = float(_k.iloc[-1]), float(_d.iloc[-1])
        _k_prev, _d_prev = float(_k.iloc[-2]), float(_d.iloc[-2])
        _golden = _k_prev < _d_prev and _k_now > _d_now
        if _golden and _k_now < 20:
            return f'✅ 低檔黃叉 K={_k_now:.1f}'
        if _golden:
            return f'⚠️ 黃叉 K={_k_now:.1f}'
        if _k_now > 80:
            return f'⚠️ 高檔 K={_k_now:.1f}'
        return f'❌ K={_k_now:.1f}'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_institutional_buying(stock_id: str) -> str:
    """投信近 5 個交易日連續買超（buy > sell）。"""
    try:
        import os as _os_in
        import datetime as _dt_in
        import requests as _rq_in
        _tok = _os_in.environ.get('FINMIND_TOKEN', '')
        _start = (_dt_in.date.today() - _dt_in.timedelta(days=20)).strftime('%Y-%m-%d')
        _p = {'dataset': 'TaiwanStockInstitutionalInvestorsBuySell',
              'data_id': stock_id, 'start_date': _start}
        # v19.170:憑證只走 header,不進 query string(避免落入 proxy / access log)
        # 原本無 headers,先補 data_loader._fm_raw_headers SSOT(帶 Bearer + UA)再移除 params token。
        from src.data.core.data_loader import _fm_raw_headers as _fm_hdrs_in
        _r = _rq_in.get(FINMIND_API_URL,
                         params=_p, headers=_fm_hdrs_in(_tok), timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        if not _data:
            return '❓ FinMind 無法人'
        # 過濾投信（Investment_Trust）每日 buy/sell
        _by_date: dict = {}
        for _row in _data:
            _name = str(_row.get('name', ''))
            if 'Investment_Trust' not in _name and '投信' not in _name:
                continue
            _d = _row.get('date', '')
            try:
                _buy = float(_row.get('buy', 0) or 0)
                _sell = float(_row.get('sell', 0) or 0)
            except (TypeError, ValueError):
                continue
            _by_date[_d] = _buy - _sell
        if not _by_date:
            return '❓ 無投信資料'
        _n = PICKER_INST_BUY_STREAK_DAYS
        _dates = sorted(_by_date.keys(), reverse=True)[:_n]
        if len(_dates) < _n:
            return f'❓ 僅 {len(_dates)} 日'
        _pos = sum(1 for d in _dates if _by_date[d] > 0)
        if _pos == _n:
            return f'✅ 連{_n}日買超'
        # ⚠️ 這個 `3` 是「部分買超 ⚠️」的中間帶，與 PICKER_S2_MIN_PASS(3) 同數字不同義，
        #    刻意不共用常數（§3.3 防同數字不同義耦合）。它不影響 ✅/❌ 通過判定，
        #    只切 ⚠️ 與 ❌ 的顯示，故未另立常數；若日後要調整再具名。
        if _pos >= 3:
            return f'⚠️ {_pos}/{_n} 日買超'
        return f'❌ {_pos}/{_n} 日買超'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_major_holders(stock_id: str) -> str:
    """大戶（≥1000 張 / 400 張級距）持股比例近 2 週增加（集保股權分散表）。

    FinMind dataset 欄位可能因版本而異 — 動態偵測 level / percent 欄位名；
    無資料時回 ⚠️（多為 FinMind 免費 token 不含此 premium 資料集，非錯誤）。
    """
    try:
        import os as _os_mh
        import datetime as _dt_mh
        import requests as _rq_mh
        _tok = _os_mh.environ.get('FINMIND_TOKEN', '')
        _start = (_dt_mh.date.today() - _dt_mh.timedelta(days=60)).strftime('%Y-%m-%d')
        _p = {'dataset': 'TaiwanStockHoldingSharesPer',
              'data_id': stock_id, 'start_date': _start}
        # v19.170:憑證只走 header,不進 query string(避免落入 proxy / access log)
        # 原本無 headers,先補 data_loader._fm_raw_headers SSOT(帶 Bearer + UA)再移除 params token。
        from src.data.core.data_loader import _fm_raw_headers as _fm_hdrs_mh
        _r = _rq_mh.get(FINMIND_API_URL,
                         params=_p, headers=_fm_hdrs_mh(_tok), timeout=15)
        _j = _r.json() if _r.status_code == 200 else {}
        _data = _j.get('data', [])
        if not _data:
            # 區分：premium 限制 vs 真無資料
            _msg = str(_j.get('msg', '')).lower()
            if 'limit' in _msg or 'permission' in _msg or 'sponsor' in _msg:
                return '⚠️ 需付費 token'
            return '⚠️ 集保無資料'
        # 動態找欄位名
        _sample = _data[0]
        _level_key = next((k for k in _sample
                           if 'level' in k.lower() or 'class' in k.lower() or '分級' in k), None)
        _pct_key = next((k for k in _sample
                         if 'percent' in k.lower() or 'ratio' in k.lower() or '比例' in k), None)
        if _level_key is None or _pct_key is None:
            return '❓ 欄位不符'
        # 鎖定大戶級距：含「1,000,001」「400,001」「以上」或數字級距 ≥ 14
        _by_date: dict = {}
        for _row in _data:
            _cls = str(_row.get(_level_key, ''))
            _is_major = ('1,000,001' in _cls or '400,001' in _cls or '以上' in _cls
                         or _cls in ('14', '15', '16', '17'))
            if not _is_major:
                continue
            _d = _row.get('date', '')
            try:
                _pct = float(_row.get(_pct_key, 0) or 0)
            except (TypeError, ValueError):
                continue
            _by_date[_d] = max(_by_date.get(_d, 0), _pct)
        if len(_by_date) < 2:
            return '⚠️ 大戶級距資料不足'
        _dates = sorted(_by_date.keys(), reverse=True)
        _now = _by_date[_dates[0]]
        _ago = _by_date[_dates[min(2, len(_dates) - 1)]]
        _chg = _now - _ago
        if _chg > 0.1:
            return f'✅ 大戶+{_chg:.2f}%'
        if _chg > -0.1:
            return f'⚠️ 持平 {_chg:+.2f}%'
        return f'❌ 大戶{_chg:+.2f}%'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


# ══════════════════════════════════════════════════════════════
# Stage 3 — Gemini AI 三型建議報告
# ══════════════════════════════════════════════════════════════

def _generate_ai_report(gemini_fn, qualified: list[dict], all_results: list[dict]) -> str:
    """用白話結構化摘要元件，把三關卡篩選結果翻成人話報告。"""
    from src.services import build_structured_summary_prompt
    from src.data.etf import _fetch_news_for

    # ── 第 1 節：通過名單（含為何入選）─────────────────────────
    _pick_lines = []
    for r in qualified:
        _name = (r.get('note') or '').strip()
        _title = f'{r["ticker"]} {_name}'.strip()
        _pick_lines.append(
            f'- {_title}：'
            f'基本面體質過了 {r["s1_pass_cnt"]}/{len(PICKER_S1_CONDITIONS)} 關'
            f'（負債{r.get("debt_ratio_label", "?")}、賺錢能力三率{r.get("three_rate_label", "?")}、'
            f'近5年配息{r.get("div_5y_label", "?")}、股價貴不貴{r.get("pe_zone_label", "?")}、'
            f'收帳速度{r.get("ar_turnover_label", "?")}、賣貨速度{r.get("inv_turnover_label", "?")}、'
            f'敢花錢擴廠{r.get("capex_label", "?")}、家底淨值{r.get("book_value_label", "?")}、'
            f'未來訂單合約負債{r.get("contract_liab_label", "?")}）；'
            f'買盤時機過了 {r["s2_pass_cnt"]}/{len(PICKER_S2_CONDITIONS)} 關'
            f'（站上月線{r.get("ma20_label", "?")}、MACD多空{r.get("macd_label", "?")}、'
            f'KD轉強{r.get("kd_label", "?")}、布林開口{r.get("boll_label", "?")}、'
            f'投信買超{r.get("inst_label", "?")}、千張大戶加碼{r.get("major_label", "?")}）'
        )
    _pick_data = '\n'.join(_pick_lines) if _pick_lines else '（這批觀察清單沒有同時通過基本面與買盤時機篩選的股票）'

    # ── 第 2 節：整批名單體質統計（通過率）────────────────────
    _total = len(all_results)
    _qual_n = len(qualified)
    # v19.178 §3.3:原 inline `>= 5` / `>= 3` + 文案「過 5 關」「過 3 關」。
    # `PICKER_S1_MIN_PASS` 已於 v18.466 由 5 拉高到 6，同檔 :318/:361/:363 都跟著改了，
    # **只有這份餵給 AI 的統計沒改** → 送進 LLM 的報告對使用者陳述的篩選標準是錯的
    # (畫面說 6/9、AI 報告說 5 關以上)。改為插值 SSOT，永不再漂移。
    _s1_strong = sum(1 for r in all_results if r.get('s1_pass_cnt', 0) >= PICKER_S1_MIN_PASS)
    _s2_strong = sum(1 for r in all_results if r.get('s2_pass_cnt', 0) >= PICKER_S2_MIN_PASS)
    _rate = (f'{_qual_n / _total * 100:.0f}%' if _total else '0%')
    _stat_lines = [
        f'- 這次總共掃了 {_total} 檔股票。',
        f'- 基本面體質健康（過 {PICKER_S1_MIN_PASS} 關以上）的有 {_s1_strong} 檔。',
        f'- 買盤時機到位（過 {PICKER_S2_MIN_PASS} 關以上）的有 {_s2_strong} 檔。',
        f'- 兩邊同時都過、最後入選的有 {_qual_n} 檔，等於每 100 檔大約只挑出 {_rate}。',
        '- 入選比例越低，代表標準守得越嚴、地雷股被擋掉越多。',
    ]
    _stat_data = '\n'.join(_stat_lines)

    _sections = [
        {'name': '哪些股票通過了三關卡篩選（基本面健康＋買盤時機到位）', 'data': _pick_data},
        {'name': '整體這批名單的體質與通過率怎麼樣', 'data': _stat_data},
    ]

    try:
        _news = _fetch_news_for('台股', '台股 高股息 存股 ETF', 5)
    except Exception:
        _news = ''

    _prompt = build_structured_summary_prompt(
        subject_title='高股息存股候選清單',
        sections=_sections,
        news_text=_news,
        overall_question='這批名單適不適合存股族、現在進場要注意什麼。',
    )
    try:
        _r = gemini_fn(_prompt)
        return _r if _r else '⚠️ AI 回傳為空，請確認 GEMINI_API_KEY'
    except Exception as e:
        return f'❌ AI 生成失敗：{type(e).__name__}: {e}'
