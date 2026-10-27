"""shared/decision_digest_terms.py — AB-2a 摘要／grounding 共用的**具名常數**（L0；只放常數，零邏輯）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
`docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §2.4 的 G1～G6 需要「字眼清單」與「標示語」。
依 CLAUDE.md §3.3（禁止 inline magic）與 §8.2，這些清單集中在本檔，由
`shared/decision_digest_grounding.py`（驗證）與 `src/services/decision_digest_summary.py`（規則式摘要）
共用 —— 兩邊引用同一份，漂移即測試紅燈。

⚠️ **全部字眼清單都是「盡力而為的拒收／要求名單」，不是完備判定**（換個拼法就能繞過；中文數字、
同義詞、英文以外的語言都擋不住）。它們是縱深防禦的一層；結構性防線是
「引用封閉＋逐字引用（quote）豁免＋數字字面一致」（見 grounding 模組）。

⚠️ 這些清單不是投資規則、門檻或權重：它們決定的是「這句話**能不能出現在摘要裡**」，不是「市場怎麼樣」。
本檔不新增任何投資判斷，不重述任何規則層文字。
"""
from __future__ import annotations

from shared.decision_digest import PLACEHOLDER_TEXTS  # AB-0 缺值佔位字（G3 沿用其概念；只讀）

# ══════════════════════════════════════════════════════════════════════
# 五段結構（C §3.1；客戶規格 §九）
# ══════════════════════════════════════════════════════════════════════
SEC_MARKET = "market"
SEC_INDUSTRY = "industry"
SEC_BUY_AND_HOLD = "buy_and_hold"
SEC_CAPITAL_GAIN = "capital_gain"
SEC_ACTIONS = "actions"

#: 五段的**固定順序**（市場／產業／存股／資本利得／本期行動）。
SECTION_KEYS: tuple = (SEC_MARKET, SEC_INDUSTRY, SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN, SEC_ACTIONS)

SECTION_LABELS: dict = {
    SEC_MARKET: "市場",
    SEC_INDUSTRY: "產業",
    SEC_BUY_AND_HOLD: "存股",
    SEC_CAPITAL_GAIN: "資本利得",
    SEC_ACTIONS: "本期行動",
}

# ══════════════════════════════════════════════════════════════════════
# 引用 id（evidence_refs）的命名空間
# ══════════════════════════════════════════════════════════════════════
#: 段落層引用：`section:<digest 段名>`。Digest 的 fact_id／action_id 不得以此開頭（見 validator `ref_id_reserved`）。
REF_SECTION_PREFIX = "section:"
#: 持股層引用：`holding:<portfolio_id>:<symbol>`。
REF_HOLDING_PREFIX = "holding:"
#: Digest 段名（對應 `DecisionDigest` 欄位）。
DIGEST_SECTIONS: tuple = ("market", "tw_trend", "intl_trend", "valuation", "industry", "holdings",
                          "risk_cap", "actions")

# ══════════════════════════════════════════════════════════════════════
# 標示語（G3／G5：缺值、過期、代理、未定義必須「明示」）
# ══════════════════════════════════════════════════════════════════════
MARK_INSUFFICIENT = "資料不足"
MARK_UNDETERMINED = "無法判定"
MARK_NOT_DEFINED = "尚未定義"
MARK_NOT_WIRED = "尚未接線"
MARK_RESEARCH_ONLY = "研究框架，未啟用"
MARK_STALE = "資料已過期"
MARK_PROXY = "代理估算"
MARK_STRATEGY_UNSET = "尚未設定投資策略分類"
MARK_UNKEYED = "缺少投資組合鍵"
MARK_NO_ACTION = "規則層未產出行動"
#: 客戶 DEC-081 Q2-2 核准的 Risk Cap 卡面措辭（逐字）。Risk Cap 獨立數字未核准顯示前，
#: 摘要與驗證一律**不得**出現 Risk Cap 區段的任何數值（見 grounding `restricted`）。
RISK_CAP_HIDDEN_WORDING = "風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate"
#: 缺值提示用的符號（C §2.5：「⬜ 資料不足／無法判定」）。
MISSING_GLYPH = "⬜"

#: 「判不出來」類標示（缺值、失敗、不合法共用）：任一出現即滿足。
MARKERS_UNDETERMINED: tuple = (MARK_INSUFFICIENT, MARK_UNDETERMINED)
#: 段落層引用（unavailable／partial）可接受的標示語（較寬；具體要求由 G5 的 basis 逐項指定）。
MARKERS_SECTION_BROAD: tuple = (
    MARK_INSUFFICIENT, MARK_UNDETERMINED, MARK_NOT_DEFINED, MARK_NOT_WIRED, MARK_RESEARCH_ONLY,
    MARK_STRATEGY_UNSET, MARK_UNKEYED, MARK_NO_ACTION, RISK_CAP_HIDDEN_WORDING,
)

# ══════════════════════════════════════════════════════════════════════
# G3：洗白字眼（missing ≠ neutral／normal／HOLD；PROJECT_RULES.md §16.1）
# ══════════════════════════════════════════════════════════════════════
#: 中文洗白字眼：以「去空白、NFKC、casefold」後的**子字串**比對。
WASHING_TERMS_CJK: tuple = (
    "中性", "正常", "維持", "續抱", "持有", "觀望", "不動作", "照舊", "如常", "不變", "無異常",
)
#: 英文洗白字眼：依非英數字元切 token 後「等於」比對。
WASHING_TERMS_LATIN: frozenset = frozenset({
    "neutral", "normal", "hold", "maintain", "steady", "unchanged",
})
#: 缺值佔位字（沿用 AB-0 `PLACEHOLDER_TEXTS`）：句中以標點／空白切開的**整段**等於其一者拒收。
PLACEHOLDER_SEGMENTS: frozenset = PLACEHOLDER_TEXTS
#: 句子切段用的分隔字元集合（標點與空白；比對 `PLACEHOLDER_SEGMENTS` 用）。
SEGMENT_SPLIT_CHARS: str = "：:，,、；;。！!（）()「」『』｜|"
#: 「確定語氣」字眼：引用 status ∈ {missing, stale, proxy, failed, invalid} 的項目時，句中不得出現。
ASSERTIVE_TERMS_CJK: tuple = (
    "確定", "確認", "肯定", "必然", "一定", "明確", "顯然", "毫無疑問", "必定", "絕對", "已證實",
    "穩健", "良好", "強勁", "安全", "無虞", "可靠", "改善", "惡化",
)

# ══════════════════════════════════════════════════════════════════════
# G4：不得新增結論類別
# ══════════════════════════════════════════════════════════════════════
#: 行動字眼：只能出現在「逐字引用的 Digest 行動／事實文字」之內，句中其餘部分不得出現。
ACTION_TERMS_CJK: tuple = (
    "買進", "買入", "賣出", "加碼", "減碼", "停利", "停損", "汰弱", "汰換", "換股", "轉換", "出清",
    "進場", "出場", "布局", "佈局", "建倉", "加倉", "減倉", "調降", "調升", "增持", "減持",
    "降低持股", "提高持股", "暫停加碼", "續抱", "持有",
)
ACTION_TERMS_LATIN: frozenset = frozenset({"buy", "sell", "hold", "add", "reduce", "trim"})
#: 方向／趨勢字眼：Digest 沒有任何方向欄位（趨勢＝尚未定義、產業＝尚未定義），故只能出現在逐字引用內。
DIRECTION_TERMS_CJK: tuple = (
    "變強", "變弱", "轉強", "轉弱", "走強", "走弱", "衰退", "崛起", "復甦", "升溫", "降溫", "看好", "看壞",
    "偏多", "偏空", "看多", "看空", "多頭", "空頭", "利多", "利空", "受惠", "擴張", "萎縮", "領漲", "領跌", "強勢", "弱勢",
    "上升趨勢", "下降趨勢", "反彈", "回檔", "築底",
)
DIRECTION_TERMS_LATIN: frozenset = frozenset({
    "bull", "bear", "bullish", "bearish", "uptrend", "downtrend", "strong", "weak",
})

# ══════════════════════════════════════════════════════════════════════
# G1：引用封閉（標的代號、產業名稱、狀態詞）
# ══════════════════════════════════════════════════════════════════════
#: 產業名稱比對時略過的官方「泛稱」代碼（名稱太泛，會誤殺一般用語）。
INDUSTRY_GENERIC_CODES: frozenset = frozenset({"19", "20"})
#: 產業「主詞」字眼（句中出現代表在談產業／類股）；只用於 G4 方向判定的上下文說明，不是名單。
INDUSTRY_SUBJECT_TERMS: tuple = ("產業", "類股", "板塊", "族群")
#: 狀態詞：燈號符號（只能出現在逐字引用內；`⬜` 是本檔 `MISSING_GLYPH`，不在此列）。
STATE_SYMBOLS: tuple = ("🟢", "🟡", "🔴", "🟠", "⚪", "🟣", "🔵")
#: 狀態詞：regime 英文狀態（C §4 MarketBlock.regime 列舉）。
STATE_WORDS_LATIN: frozenset = frozenset({"bull", "neutral", "caution", "bear", "unknown"})
#: 代號形狀：4–6 位數字（可帶一個英文字尾，如 `00679B`）。
SYMBOL_NUMERIC_PATTERN = r"(?<![0-9A-Za-z.])\d{4,6}[A-Za-z]?(?![0-9A-Za-z]|\.\d)"
#: 英文代號形狀：2–5 個大寫字母（如 `TSLA`）。
SYMBOL_LATIN_PATTERN = r"(?<![A-Za-z0-9])[A-Z]{2,5}(?![A-Za-z0-9])"
#: 允許出現而不算「Digest 外的代號」的英文縮寫。
LATIN_ALLOWED_TOKENS: frozenset = frozenset({"ETF", "EPS", "PE"})

# ══════════════════════════════════════════════════════════════════════
# G2：數字字面一致
# ══════════════════════════════════════════════════════════════════════
#: ISO 日期（資料日）：整段視為一個 token，必須字面等於引用項目的 as_of。
DATE_PATTERN = r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)"
#: 數值 token：可帶正負號與小數；前面不得緊接數字或小數點（避免切半）。
NUMBER_PATTERN = r"(?<![0-9.])[+-]?\d+(?:\.\d+)?"
#: 非有限數值字樣（NaN／inf／∞）。
NONFINITE_PATTERN = r"(?<![a-z])(?:nan|inf|infinity)(?![a-z])|∞"
#: 單位為 None 時，數字後面不得緊接的標點（避免「60」被當成「60%」）。
UNIT_FORBIDDEN_AFTER_NONE: str = "%‰"

# ══════════════════════════════════════════════════════════════════════
# 規則式摘要的顯示字串（SSOT：摘要與驗證共用同一份）
# ══════════════════════════════════════════════════════════════════════
#: 市場事實 fact_id → 顯示標籤（builder 只產生這三個；其他 id → `FACT_LABEL_FALLBACK`）。
FACT_LABELS: dict = {
    "market.regime": "市場位階",
    "market.light": "市場燈號",
    "market.health": "市場健康度",
}
FACT_LABEL_FALLBACK = "市場資料項"
LABEL_TW_TREND = "台股趨勢"
LABEL_INTL_TREND = "國際趨勢"
LABEL_VALUATION = "大盤合理區間"
LABEL_INDUSTRY_TREND = "產業趨勢"

#: MissingReason.value → 顯示字串（對映 AB-0 `MissingReason`；非規則層文字）。
MISSING_REASON_LABELS: dict = {
    "no_input": "尚無輸入",
    "fetch_failed": "抓取失敗",
    "not_enough_history": "歷史長度不足",
    "not_applicable": "不適用",
    "contract_drift": "資料契約異常",
    "no_variation": "期間無變異",
    "not_defined": "尚未定義",
    "not_wired": "尚未接線",
}
MISSING_REASON_LABEL_UNKNOWN = "原因不明"

#: 單句不得含的字元類別（Unicode category）：控制字元與零寬／格式字元。
FORBIDDEN_CHAR_CATEGORIES: tuple = ("Cc", "Cf")

# ══════════════════════════════════════════════════════════════════════
# 閘門識別碼
# ══════════════════════════════════════════════════════════════════════
GATE_G1, GATE_G2, GATE_G3, GATE_G4, GATE_G5, GATE_G6 = "G1", "G2", "G3", "G4", "G5", "G6"
#: C §2.4 的 G1～G6（G7 輸出過濾不是內容驗證，不在本批）。
GROUNDING_GATES: tuple = (GATE_G1, GATE_G2, GATE_G3, GATE_G4, GATE_G5, GATE_G6)
#: 摘要結構不合格（無法解析）。
GATE_STRUCT = "STRUCT"
#: 驗證對象 Digest 本身不合格。
GATE_DIGEST = "DIGEST"
#: Digest 層閘門（assess_digest 回報用）。
GATE_AB0_CONTRACT = "AB0_CONTRACT"
GATE_AB1_RULE_ID = "AB1_RULE_ID"
GATE_AB1_ACTION_ORDER = "AB1_ACTION_ORDER"
GATE_AB2A_TEXT = "AB2A_TEXT"
GATE_AB2A_REFS = "AB2A_REFS"
