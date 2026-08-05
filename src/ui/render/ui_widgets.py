"""UI 元件純函式（HTML 字串生成器） — 從 app.py 抽出（PR P2-B Phase 2）

零 Streamlit / 零 session state 依賴，只回傳 HTML 字串給呼叫端做
`st.markdown(..., unsafe_allow_html=True)` 渲染。

收錄函式
========
- explain_box(term, simple_explain, detail='')        — 術語說明框
- traffic_light(value, good_cond, bad_cond, ...)      — 紅綠燈指示器
- beginner_kpi(title, value, plain_meaning, ...)      — 初學者版 KPI 卡
- show_term_help(term)                                — 顯示術語對照表內容
- kpi(title, value, sub='', color, border)            — 一般 KPI 卡
- strategy_box(icon, strategy, logic)                 — 策略邏輯框（舊版）
- strategy_conclusion(strategy, indicator_val, ...)   — 策略結論（自動配色）
  ⚠️ v19.174 去識別化：舊名 teacher_box / teacher_conclusion，第一參數舊為人名。
     過渡期保留同名 alias，caller 全部遷移完成後可移除（見檔尾）。
- strategy_label(strategy)                            — 取「策略N（範疇）」章節標題
- signal_box(label, color, desc='')                   — 訊號方塊

常數
====
- TERM_EXPLAIN: dict — 13 個常見術語的白話對照表
- STRATEGY_SCOPE: dict — 策略代號 → 涵蓋範疇（括號內容的 SSOT）
- STRATEGY_LABELS: dict — 策略代號 → 「策略N（範疇）」完整顯示字串（SSOT）
"""
from __future__ import annotations

from typing import NamedTuple

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
# §3.3 反捏造：廣度門檻不 inline，一律取 L0 SSOT（L4 Render → L0 為合法下行 import）
from shared.signal_thresholds import BREADTH_BULL_PCT


# ════════════════════════════════════════════════════════════════
# 市場廣度家族 — 名詞定義 SSOT（P0-C，2026-08-05）
#
# 【為什麼要有這一塊】§2.1 SSOT。修正前同一個概念散落四個檔各寫一份說明，
# 且**四份互相矛盾**：
#   - ui_widgets:38          「旌旗指數＝全市場健康度＝站上均線家數比」
#   - ui_widgets:39          「騰落指標＝市場廣度」
#   - macro_classroom:136    「旌旗指數（站上 20MA 家數比＝市場廣度）」
#   - macro_stock_link:53    印「市場廣度：」但值取自 jingqi_info
#   - section_overview:50    標題「全市場健康度」，值是旌旗
#   - section_short:187-190  標題「全市場健康度」，值是**當日**上漲佔比，還寫成「N 分」
# 使用者會同時看到這幾個 tab → 三個名字四種意思。
#
# 【考證結論】追到 compute 層（不是看標籤猜）後發現：
#   ⚠️ **全站沒有任何一行程式在算「站上 20MA 的家數比」**。
#   grep `站上|above_ma|pct_above` 全 repo：`tab_stock.py:563-565` 的
#   `_above_ma20` 是**單檔個股**自己跟自己的均線比，不是市場廣度；
#   `daily_data_fetchers.py:445` 的 `adl_ma20` 是「ADL 累積線的 MA20」，
#   **不是**「站上 20MA 的股票家數」。兩者都跟廣度定義無關。
#   → 「站上均線家數比」這句話是**憑空捏造的資料描述**（§1 反捏造）：
#      它描述了一個系統根本沒有計算的量，讀者會據此下與事實不符的判讀。
#
# 【真實的量】旌旗指數其實是「上漲佔比的 5 日均」，見下方 evidence 欄。
#
# 【定名原則】這些**本來就是不同的量**，所以不是「統一成同一個詞」，而是
# 讓名字互不混淆：一個量一個正式名，畫面標題一律取 `.canonical`。
# 「市場廣度」是這一**家族**的統稱（涵蓋下列 4 個量），**不是**任何單一
# 數字的名字 —— 因此禁止拿它當 KPI 標題配一個數值（見 `BREADTH_FAMILY_NAME`）。
# ════════════════════════════════════════════════════════════════


class BreadthTerm(NamedTuple):
    """市場廣度家族的單一名詞定義。畫面文案一律引用本結構，不要各檔重寫。

    正式名 / 白話名分兩欄是刻意的：名詞表要印「術語（白話名）」，
    KPI 標題要印正式名。合成一欄就會出現「旌旗指數（旌旗指數）」。
    """
    canonical: str   # 正式名 — KPI 標題 / 章節標題用這個
    nickname: str    # 白話名 — 名詞表括號內用這個（不可與 canonical 相同）
    unit: str        # 單位（'%' / '家' / '累積家'）—— §4.1 量綱防呆
    plain: str       # 白話一句話（給初學者 KPI 卡的 plain_meaning）
    formula: str     # 實際公式（考證結果，非標籤猜測）
    evidence: str    # file:line —— 可回頭覆核


#: 家族統稱。可當**分類**標題（如章節名），但後面不可直接接一個數字。
BREADTH_FAMILY_NAME = '市場廣度'

BREADTH_UP_RATIO = BreadthTerm(
    canonical='上漲佔比',
    nickname='今天幾成股票在漲',
    unit='%',
    plain='今天上漲的股票，占「有漲有跌的股票」幾成',
    formula='上漲家數 ÷（上漲家數＋下跌家數）× 100 —— 單日、不平滑',
    evidence='src/data/daily/daily_data_fetchers.py:446（欄名 ad_ratio）；'
             'TWSE 即時同義值見 section_short.py 的 _ratio_v',
)

BREADTH_JINGQI = BreadthTerm(
    canonical='旌旗指數',
    nickname='廣度 5 日均',
    unit='%',
    plain='最近 5 個交易日「上漲佔比」的平均（比單日穩，不會被一天暴漲暴跌帶走）',
    formula='上漲佔比的 5 日移動平均 = ad_ratio.tail(5).mean()',
    evidence='src/services/jingqi_calc.py:43（ADL 主源）／:51-54（大盤估算備援）',
)

BREADTH_AD_VALUE = BreadthTerm(
    canonical='AD 值',
    nickname='漲家減跌家',
    unit='家',
    plain='今天上漲家數減掉下跌家數，正數代表漲的比跌的多',
    formula='上漲家數 − 下跌家數 —— 單日、有正負號',
    evidence='src/data/daily/daily_data_fetchers.py:443（欄名 ad）',
)

BREADTH_ADL = BreadthTerm(
    canonical='騰落指標 ADL',
    nickname='漲跌家數累積線',
    unit='累積家',
    plain='把每天的 AD 值一直加總起來的線，看「方向」比看絕對值重要',
    formula='AD 值的累積和 = ad.cumsum()',
    evidence='src/data/daily/daily_data_fetchers.py:444（欄名 adl）',
)

#: 正式名 → 定義。新增廣度類指標請加進這裡，不要在各 UI 檔另寫說明。
BREADTH_TERMS: dict[str, BreadthTerm] = {
    _t.canonical: _t for _t in (
        BREADTH_UP_RATIO, BREADTH_JINGQI, BREADTH_AD_VALUE, BREADTH_ADL,
    )
}

#: 已退役的舊稱 → (正式名 | None, 退役理由)。留作考古 + 守衛測試的黑名單來源。
#: 「全市場健康度」為何整個退役：它同時被貼在**三個不同的量**上 ——
#:   section_overview(旌旗 5 日均) / section_short(當日上漲佔比) /
#:   紅綠燈卡「綜合健康度 /100」(= 0.6×旌旗 + 0.4×大盤評分，
#:   macro_helpers.compute_macro_health)。三者數值不同、單位不同（% vs 分），
#:   共用一個標題必然誤導 → 廢名，改各自用正式名。
BREADTH_DEPRECATED_TITLES: dict[str, tuple[str | None, str]] = {
    '全市場健康度': (
        None,
        '一名三義（旌旗 / 當日上漲佔比 / 綜合健康度分數），且與紅綠燈卡的'
        '「綜合健康度」撞名 —— 一律改用各自正式名，不要復活',
    ),
    '站上均線家數比': (
        BREADTH_JINGQI.canonical,
        '系統從未計算此量（§1 反捏造）；被誤指的 jingqi_info.avg 實為上漲佔比 5 日均',
    ),
    '站上 20MA 家數比': (
        BREADTH_JINGQI.canonical,
        '同上 —— adl_ma20 是「ADL 累積線的 MA20」，不是「站上 20MA 的家數」',
    ),
}


def breadth_kpi_title(term: BreadthTerm, suffix: str = '') -> str:
    """廣度 KPI 卡標題。`suffix` 用來標「今日」「TWSE 即時」等口徑差異。

    刻意要求傳 `BreadthTerm` 而非字串：手打字串正是本次 P0-C 的成因。
    """
    return f'{term.canonical}（{suffix}）' if suffix else term.canonical


# 術語白話對照表
# ⚠️ 廣度相關 4 條（旌旗指數 / 騰落指標 / ADL / AD值）的說明**不在這裡手寫**，
#    改由上方 `BREADTH_TERMS` 生成（見檔案下方 TERM_EXPLAIN.update(...)），
#    避免名詞表與教學頁、KPI 卡再度各說各話。
TERM_EXPLAIN = {
    'RSI':      ('強弱指數', '衡量股票最近漲跌的「溫度」。<70正常，>70過熱，<30過冷。'),
    'KD':       ('買賣時機指標', 'K線和D線的交叉代表買賣時機。K>D往上穿越=可能要漲了。'),
    # 'ADL' / '旌旗指數' / '騰落指標' 三條由 BREADTH_TERMS 生成（見檔案下方），
    # 不在此手寫 —— 手寫就是「名詞表 vs 教學頁 vs KPI 卡」再度分歧的成因。
    'VCP':      ('波動收縮形態', '股價震盪越來越小，像彈弓拉緊。突破時可能大漲。'),
    'IBS':      ('K棒位置指標', '今天收盤在今天高低價的哪個位置。越靠近低點=隔天可能反彈。'),
    'M1B-M2':   ('資金流向指標', '活錢(M1B)比定存(M2)跑得快=錢往股市跑=行情要來了。'),
    '乖離率':    ('偏離正常值多少', '股價離平均成本線差多少%。>20%=可能過熱了，<-20%=可能太便宜。'),
    '多頭排列':  ('均線向上排列', '短期均線>中期>長期均線，代表趨勢向上，可以操作多方。'),
    '布林通道':  ('價格正常範圍', '統計出來的「正常價格範圍」。突破上軌=強勢但可能過熱。'),
    '量比':      ('成交量比較', '今天的成交量是過去20天平均的幾倍。>2=放量異常，要注意。'),
    'PCR':      ('多空情緒比', '選擇權市場的多空比例。>1偏多，<1偏空。'),
}

# ── 廣度 4 條由 SSOT 生成（P0-C）─────────────────────────────────
# 名詞表的「白話說明」= BreadthTerm.plain + 公式，改定義只需改上面一處。
# key 沿用既有名（'ADL' / '旌旗指數' / '騰落指標'），避免既有 caller 壞掉
# （app.py:286 `show_term_help('ADL')`；tests/test_ui_widgets.py:81-84 釘 key 集合）。
TERM_EXPLAIN.update({
    'ADL':      (BREADTH_ADL.nickname, f'{BREADTH_ADL.plain}（{BREADTH_ADL.formula}）'),
    '騰落指標':  (BREADTH_ADL.nickname, f'{BREADTH_ADL.plain}（{BREADTH_ADL.formula}）'),
    'AD值':     (BREADTH_AD_VALUE.nickname,
                 f'{BREADTH_AD_VALUE.plain}（{BREADTH_AD_VALUE.formula}）'),
    '上漲佔比':  (BREADTH_UP_RATIO.nickname,
                 f'{BREADTH_UP_RATIO.plain}（{BREADTH_UP_RATIO.formula}）'),
    # ⚠️ 舊說明寫「有幾%的股票站在均線之上」是**捏造**（系統無此計算），
    #    §1 反捏造 —— 改為實際公式，並明示它不是均線類指標。
    '旌旗指數':  (BREADTH_JINGQI.nickname,
                 f'{BREADTH_JINGQI.plain}。{BREADTH_JINGQI.formula}；'
                 f'≥{int(BREADTH_BULL_PCT)}% 視為廣度健康。'
                 f'⚠️ 它**不是**「站上均線的家數比」，系統並未計算該量。'),
})


def explain_box(term, simple_explain, detail=''):
    """顯示一個術語說明框"""
    return (
        f'<div style="background:#161b22;border-left:3px solid #58a6ff;'
        f'padding:8px 12px;margin:4px 0;border-radius:0 6px 6px 0;">'
        f'<span style="font-size:12px;font-weight:700;color:#58a6ff;">{term}</span>'
        f'<span style="font-size:12px;color:#c9d1d9;"> = {simple_explain}</span>'
        + (f'<br><span style="font-size:11px;color:#8b949e;">{detail}</span>' if detail else '') +
        '</div>'
    )


def traffic_light(value, good_cond, bad_cond, good_label, bad_label, neutral_label='⚪ 觀察'):
    """紅綠燈指示器"""
    if good_cond:
        color, label = TRAFFIC_GREEN, f'🟢 {good_label}'
    elif bad_cond:
        color, label = TRAFFIC_RED, f'🔴 {bad_label}'
    else:
        color, label = TRAFFIC_YELLOW, neutral_label
    return color, label


def beginner_kpi(title, value, plain_meaning, color='#e6edf3', tip=''):
    """初學者版 KPI 卡（有說明文字）"""
    return (
        f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:10px;'
        f'padding:12px;text-align:center;">'
        f'<div style="font-size:10px;color:#484f58;margin-bottom:2px;">{title}</div>'
        f'<div style="font-size:22px;font-weight:900;color:{color};">{value}</div>'
        f'<div style="font-size:11px;color:#8b949e;margin-top:3px;">{plain_meaning}</div>'
        + (f'<div style="font-size:10px;color:#484f58;margin-top:2px;">💡 {tip}</div>' if tip else '') +
        '</div>'
    )


def show_term_help(term):
    """顯示術語說明 - 在任何 section 都可呼叫"""
    if term not in TERM_EXPLAIN:
        return ''
    name, desc = TERM_EXPLAIN[term]
    return explain_box(f'❓ {term}（{name}）', desc)


def kpi(title, value, sub='', color='#e6edf3', border='#21262d'):
    return (f'<div style="background:#161b22;border:1px solid {border};border-radius:8px;'
            f'padding:12px 14px;text-align:center;">'
            f'<div style="font-size:10px;color:#484f58;margin-bottom:3px;">{title}</div>'
            f'<div style="font-size:20px;font-weight:900;color:{color};">{value}</div>'
            f'<div style="font-size:10px;color:#8b949e;margin-top:3px;">{sub}</div></div>')


# ════════════════════════════════════════════════════════════════
# v19.174 去識別化：策略代號 → icon（**不再保存任何人名**）
#
# 原本這裡是 `_STRATEGY_MAP`，key 是 10 個真實人名（估值派 2 位、財報派 2 位、
# 技術派 6 位），由 `_to_strategy()` 在渲染時翻成「策略1/2/3」。也就是說：
# 畫面上看不到人名，**但原始碼裡有**，而且每個 caller 都在傳人名字串。
#
# 2026-08-05 去識別化決議：人名一律移除，顯示形式維持「策略1/2/3」。因此：
#   1. 人名字典整份刪除，改成「策略代號 → icon」的極簡表；
#   2. caller 一律直接傳 `策略1` / `策略2` / `策略3`（見 `STRATEGY_*` 常數）；
#   3. 保留 `_to_strategy()` 的寬鬆行為 —— 傳到未知字串時退化為通用標籤而非
#      KeyError，避免漏改的 caller 讓整頁炸掉（§1：降級要看得見，不是靜默）。
# ════════════════════════════════════════════════════════════════

# 策略代號常數（caller 用這三個，不要再寫字面字串）
STRATEGY_VALUATION = '策略1'   # 估值 / 存股
STRATEGY_FINANCIAL = '策略2'   # 財報體檢
STRATEGY_TECHNICAL = '策略3'   # 技術 / 動能 / 資金面

_STRATEGY_ICON = {
    STRATEGY_VALUATION: '💡',
    STRATEGY_FINANCIAL: '🏥',
    STRATEGY_TECHNICAL: '🎯',
}


def _to_strategy(strategy: str) -> tuple[str, str]:
    """策略代號 → (顯示標籤, icon)。

    未登記的字串**不 raise**，退化為通用標籤 `('策略', '👤')` ——
    這條退化路徑同時是「還有 caller 沒改乾淨」的可見訊號（畫面會出現 👤 策略）。
    """
    if strategy in _STRATEGY_ICON:
        return (strategy, _STRATEGY_ICON[strategy])
    return ('策略', '👤')


# ── 策略代號 → 括號說明文字（SSOT）───────────────────────────────────
# 畫面上「策略N（…）」括號裡的字，**全站只有這一份**。
#
# 為什麼要收斂成常數（v19.175 regression 修正）：
# v19.174 去識別化把 10 個來源壓成 3 個代號後，章節 / 卡片標題的括號變成各
# caller 自己手打，於是「📖 系統說明書」同時存在
#   「📐 策略3（技術 / 動能）」與「💰 策略3（資金面）」
# —— 同一個編號兩種括號說明，讀者無從判斷是「分類本來就寬」還是「編號寫錯」。
# 這是 §3.3 inline magic 的典型後果：同一語意散落多份，改一處不會連動。
#
# 內容來源（考證，不是重新發明）：v19.174 刪掉的 `_STRATEGY_MAP` 其分組註解
# 本身就寫著「策略 1：估值 / 存股」「策略 2：財報體檢」
# 「策略 3：技術 / 動能 / 資金面」，與上方 `STRATEGY_*` 三行的行尾註解逐字一致。
STRATEGY_SCOPE: dict[str, tuple[str, ...]] = {
    STRATEGY_VALUATION: ('估值', '存股'),
    STRATEGY_FINANCIAL: ('財報體檢',),
    STRATEGY_TECHNICAL: ('技術', '動能', '資金面'),
}

# 「策略N（範疇）」完整顯示字串。caller 一律取這裡（或 `strategy_label()`），
# **不要自己用 f-string 拼括號** —— 自己拼就是上面那個 regression 的成因。
STRATEGY_LABELS: dict[str, str] = {
    _code: f'{_code}（{" / ".join(_scope)}）'
    for _code, _scope in STRATEGY_SCOPE.items()
}


def strategy_label(strategy: str) -> str:
    """策略代號 → 「策略N（範疇）」章節 / 卡片標題字串。

    Args:
        strategy: 策略代號常數（`STRATEGY_VALUATION` / `_FINANCIAL` / `_TECHNICAL`）

    Returns:
        e.g. `'策略3（技術 / 動能 / 資金面）'`

    Raises:
        ValueError: 代號未登記 —— §1 fail loud。

    ⚠️ **刻意不提供 scope 覆寫參數**：同一個代號在全站只能有一種括號說明。
    允許 caller 傳「子集」看似彈性，實際結果就是 v19.174→175 的
    「策略3（技術 / 動能）」vs「策略3（資金面）」並存。章節之間的差異請寫在
    破折號後面的**主題**（例：`— 型態學：…` / `— 資金動能 M1B-M2 …`），
    而不是改括號。

    註：本函式與 `_to_strategy()` 的寬鬆退化行為刻意不同 —— `_to_strategy` 走
    runtime 渲染路徑（一顆卡片壞掉不該白屏整頁），本函式走**靜態章節標題**
    路徑（module import 期就會執行，錯了要立刻知道）。
    """
    try:
        return STRATEGY_LABELS[strategy]
    except KeyError:
        raise ValueError(
            f'未登記的策略代號 {strategy!r}；'
            f'合法值：{sorted(STRATEGY_LABELS)}') from None


def strategy_box(icon, strategy, logic):
    """策略邏輯方塊（舊名 `teacher_box`，v19.174 去識別化改名）。"""
    _label, _ic = _to_strategy(strategy)
    return (f'<div class="teacher-card">'
            f'<span style="font-size:12px;color:#ffd700;font-weight:700;">{_ic} {_label}</span>'
            f'<div style="font-size:12px;color:#8b949e;margin-top:4px;line-height:1.6;">{logic}</div>'
            f'</div>')


def strategy_conclusion(strategy, indicator_val, conclusion, action='', color=None):
    """
    統一策略結論格式：
    策略X：指標數值 → 結論，行動建議

    v19.174 去識別化：舊名 `teacher_conclusion`，第一參數舊名 `teacher`
    且傳的是人名字串；現改為直接傳策略代號（`STRATEGY_VALUATION` /
    `STRATEGY_FINANCIAL` / `STRATEGY_TECHNICAL`）。

    strategy:      策略代號（'策略1'/'策略2'/'策略3'）
    indicator_val: 指標與數值（如 '費半 7837(+0.5%)'）
    conclusion:    目前結論（如 '半導體強勢'）
    action:        建議行動（如 '台股多方加分'）
    color:         顏色（自動依結論判斷，或手動指定 green/red/yellow）
    """
    # 自動判斷顏色
    if color is None:
        # 台股慣例: 正/漲/多=紅, 負/跌/空=綠, 中性=黃, 預設=藍
        # v18.427 Phase 2 Batch 4:_neg_kw 補 '侵蝕' '高估'、_pos_kw 補 '低估' '特價'
        # (原 etf_render._teacher_conclusion 私有副本擁有的 ETF 殖利率脈絡關鍵字,
        # 抽至 SSOT 後 etf_render 委派本函式統一)。
        _neg_kw = ['警戒', '危險', '賣超', '空單', '減碼', '停損', '撤離', '跌破', '過熱', '回調', '降倉', '空頭', '侵蝕', '高估']
        _pos_kw = ['強勢', '買超', '多頭', '安全', '健康', '買進', '加碼', '流入', '突破', '進攻', '上漲', '低估', '特價']
        if any(k in conclusion+action for k in _neg_kw):
            color = '#2ea043'   # 跌=綠
        elif any(k in conclusion+action for k in _pos_kw):
            color = '#da3633'   # 漲=紅
        else:
            color = TRAFFIC_YELLOW
    _label, _icon = _to_strategy(strategy)
    _action_str = f'，{action}' if action else ''
    return (
        f'<div style="border-left:3px solid {color};padding:6px 10px;margin:4px 0;'
        f'background:rgba(0,0,0,0.2);border-radius:0 6px 6px 0;">'
        f'<span style="color:#ffd700;font-weight:700;font-size:12px;">{_icon} {_label}</span>'
        f'<span style="color:#8b949e;font-size:12px;">：</span>'
        f'<span style="color:#c9d1d9;font-size:12px;">{indicator_val} → </span>'
        f'<span style="color:{color};font-size:12px;font-weight:600;">{conclusion}</span>'
        f'<span style="color:#8b949e;font-size:11px;">{_action_str}</span>'
        f'</div>'
    )


# ── v19.174 過渡期 alias（caller 全部遷移完成後移除）──────────────────
# 去識別化是跨 40+ 檔的改動，分批進行。這兩個 alias 讓「已改的 caller」與
# 「還沒改的 caller」可以並存，避免中途 ImportError 讓整站白屏。
# ⚠️ 舊 caller 傳的是人名字串 → `_to_strategy()` 查不到 → 退化為 👤 策略，
#    畫面看得出來還沒改完（刻意不靜默）。
teacher_box = strategy_box
teacher_conclusion = strategy_conclusion


def signal_box(label, color, desc=''):
    colors = {'green': ('#0d2818', TRAFFIC_GREEN), 'red': ('#2a0d0d', TRAFFIC_RED),
              'yellow': ('#2a1f00', TRAFFIC_YELLOW), 'blue': ('#0d1b2a', '#58a6ff')}
    bg, tc = colors.get(color, ('#161b22', '#8b949e'))
    return (f'<div style="background:{bg};border:1px solid {tc};border-radius:8px;'
            f'padding:10px 14px;margin:4px 0;">'
            f'<b style="color:{tc};">{label}</b>'
            f'<span style="color:#8b949e;font-size:12px;margin-left:8px;">{desc}</span></div>')


def cond_badge(ok, label):
    """條件徽章：True → 綠色實心，False → 灰色淡色。tab_macro 五維點火條件列。"""
    c = TRAFFIC_GREEN if ok else '#484f58'
    return (f'<span style="background:{c}22;border:1px solid {c};border-radius:4px;'
            f'padding:2px 8px;font-size:12px;color:{c};margin:2px;">{label}</span>')
