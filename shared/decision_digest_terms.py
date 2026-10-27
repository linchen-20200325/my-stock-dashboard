"""shared/decision_digest_terms.py — AB-2a 摘要／grounding 共用的**具名常數**（L0；只放常數，零邏輯）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
`docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §2.4 的 G1～G6 需要「模板」與「標示語」。
依 CLAUDE.md §3.3（禁止 inline magic）與 §8.2，這些常數集中在本檔，由
`shared/decision_digest_grounding.py`（驗證）與 `src/services/decision_digest_summary.py`（規則式摘要）共用。

═══ 主防線：句型白名單（fail-closed） ═══════════════════════════════════════
摘要句子不是自由文字，而是 **segment 序列**：每個 segment 只能是 (a) 本檔 `TEMPLATES` 的**固定模板片段**
（以 id 引用，不是任意字串），或 (b) 對某個 Digest 項目的**欄位展開**（`FIELD_*`，由 checker 從 Digest 取值）。
不允許任何殘餘自由文字，因此同形異字、簡體、同義詞、中文數字、否定／矛盾、夾帶結論都沒有地方可以放。

⚠️ 下方的字眼清單（洗白／確定語氣／行動／方向／狀態詞）**不再是執行期的主防線**：它們是 **L0 模板與標籤的
建置期 lint**（測試保證每個模板、標籤、標示語都不含這些字眼，避免日後有人在模板裡偷渡）。它們仍是盡力而為，不是完備判定。

本檔不新增任何投資判斷規則、門檻或權重。
"""
from __future__ import annotations


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
#: 中文洗白字眼：以「去空白、NFKC、casefold」後的**子字串**比對。
WASHING_TERMS_CJK: tuple = (
    "中性", "正常", "維持", "續抱", "持有", "觀望", "不動作", "照舊", "如常", "不變", "無異常",
)
#: 英文洗白字眼：依非英數字元切 token 後「等於」比對。
WASHING_TERMS_LATIN: frozenset = frozenset({
    "neutral", "normal", "hold", "maintain", "steady", "unchanged",
})
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

#: Digest 文字（Fact.text／ActionRef.text／strategy_source）與摘要不得含的字元類別：控制、零寬／格式、代理、
#: 私用區、未指派、行／段分隔。另外 `Zs` 只允許普通空格 U+0020（NBSP、全形空白 U+3000 等一律拒收 ——
#: 全形空白的決定：拒收，因為它能讓「看起來相同」的兩段文字逐字不相等）。
FORBIDDEN_CHAR_CATEGORIES: tuple = ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp")
#: 唯一允許的空白字元。
ALLOWED_SPACE = " "
#: 組合記號類別（孤立判定用）：Mn／Mc／Me。
COMBINING_CATEGORIES: tuple = ("Mn", "Mc", "Me")
#: 持股／行動目標的 `symbol` 允許的字元集（fullmatch）：英數字開頭，之後英數字、`.`、`-`，總長 1～12。
#: 與台股代號相容：個股 4 碼（2330、6488）、ETF 5～6 碼含字尾（00878、006208、00679B、00937B）、
#: 含市場後綴的寫法（2330.TW）。不含 `:`、空白、全形字元（AB-0 另要求 NFKC 與無空白）。
#: `portfolio_id` 是不透明鍵（來源屬 AB-4r），只套用字元類別檢查，不套用本字元集。
SYMBOL_PATTERN = r"[0-9A-Za-z][0-9A-Za-z.\-]{0,11}"
#: 摘要的「缺值原因」若屬「資料不足」家族才可包成「資料不足，無法判定（原因）」；其餘原因各有自己的固定句型。
INSUFFICIENT_FAMILY_REASONS: tuple = ("no_input", "fetch_failed", "not_enough_history")
#: 市場事實允許的單位（None 以外）。摘要的單位由「模板」決定，不展開 Digest 的 unit 字串。
UNIT_PERCENT = "%"
SUPPORTED_UNITS: tuple = (UNIT_PERCENT,)

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
#: Digest 層閘門的固定順序（`failed_gates` 輸出順序；確定性，不依賴 set／hash）。
DIGEST_GATES_ORDER: tuple = (GATE_AB0_CONTRACT, GATE_AB1_RULE_ID, GATE_AB1_ACTION_ORDER, GATE_AB2A_TEXT,
                             GATE_AB2A_REFS)


# ══════════════════════════════════════════════════════════════════════
# 句型白名單：固定模板片段（id → 字串）與欄位展開名
# ══════════════════════════════════════════════════════════════════════
TPL_GLYPH = "tpl.glyph"
TPL_COLON = "tpl.colon"
TPL_PCT = "tpl.pct"
TPL_CLOSE = "tpl.close"
TPL_DATE_OPEN = "tpl.date_open"
TPL_STALE_DATE_OPEN = "tpl.stale_date_open"
TPL_PROXY_TAIL = "tpl.proxy_tail"
TPL_MISSING_OPEN = "tpl.missing_open"
TPL_INVALID_TAIL = "tpl.invalid_tail"
TPL_UNDETERMINED_TAIL = "tpl.undetermined_tail"
TPL_UNKEYED_OPEN = "tpl.unkeyed_open"
TPL_UNKEYED_TAIL = "tpl.unkeyed_tail"
TPL_LABEL_BUY_AND_HOLD = "tpl.label_buy_and_hold"
TPL_LABEL_CAPITAL_GAIN = "tpl.label_capital_gain"
TPL_HOLDINGS_UNAVAILABLE_MID = "tpl.holdings_unavailable_mid"
TPL_STRATEGY_UNSET_TAIL = "tpl.strategy_unset_tail"
TPL_STRATEGY_IS = "tpl.strategy_is"
TPL_ENTRY_TAIL = "tpl.entry_tail"
TPL_ACT_UNAVAILABLE_OPEN = "tpl.act_unavailable_open"
TPL_ACT_NONE = "tpl.act_none"
TPL_ACT_STALE_OPEN = "tpl.act_stale_open"
TPL_STRATEGY_NONE_TAIL = "tpl.strategy_none_tail"
TPL_NOT_APPLICABLE_TAIL = "tpl.not_applicable_tail"
TPL_NO_VARIATION_TAIL = "tpl.no_variation_tail"
TPL_CONTRACT_DRIFT_TAIL = "tpl.contract_drift_tail"
TPL_NOT_DEFINED_TAIL = "tpl.not_defined_tail"
TPL_NOT_WIRED_TAIL = "tpl.not_wired_tail"
TPL_HOLDINGS_NO_BASIS_TAIL = "tpl.holdings_no_basis_tail"
TPL_ACT_NO_BASIS = "tpl.act_no_basis"
TPL_UNCLASSIFIED_OPEN = "tpl.unclassified_open"
TPL_UNCLASSIFIED_TAIL = "tpl.unclassified_tail"

#: 固定模板片段。⚠️ 摘要裡**所有**非 Digest 展開的文字都只能來自這張表；不得含阿拉伯數字（數字只能來自欄位展開）。
TEMPLATES: dict = {
    TPL_GLYPH: f"{MISSING_GLYPH} ",
    TPL_COLON: "：",
    TPL_PCT: "%",
    TPL_CLOSE: "）",
    TPL_DATE_OPEN: "（資料日 ",
    TPL_STALE_DATE_OPEN: f"（{MARK_STALE}，資料日 ",
    TPL_PROXY_TAIL: f"（{MARK_PROXY}值，非正式資料）",
    TPL_MISSING_OPEN: f"：{MARK_INSUFFICIENT}，{MARK_UNDETERMINED}（",
    TPL_INVALID_TAIL: f"：資料不合法，已丟棄，{MARK_INSUFFICIENT}，{MARK_UNDETERMINED}",
    TPL_UNDETERMINED_TAIL: f"，{MARK_UNDETERMINED}",
    TPL_UNKEYED_OPEN: f"{MISSING_GLYPH} 另有 ",
    TPL_UNKEYED_TAIL: f" 檔持股{MARK_UNKEYED}，未納入判讀，{MARK_INSUFFICIENT}，{MARK_UNDETERMINED}",
    TPL_LABEL_BUY_AND_HOLD: SECTION_LABELS[SEC_BUY_AND_HOLD],
    TPL_LABEL_CAPITAL_GAIN: SECTION_LABELS[SEC_CAPITAL_GAIN],
    TPL_HOLDINGS_UNAVAILABLE_MID: f"：持股資料不足，{MARK_UNDETERMINED}（",
    TPL_STRATEGY_UNSET_TAIL: f"：{MARK_STRATEGY_UNSET}，{MARK_UNDETERMINED}",
    TPL_STRATEGY_IS: "：策略分類為",
    TPL_ENTRY_TAIL: f"；基本面與配置判定{MARK_NOT_WIRED}，{MARK_UNDETERMINED}",
    TPL_ACT_UNAVAILABLE_OPEN: f"{MISSING_GLYPH} 本期行動：{MARK_INSUFFICIENT}，{MARK_UNDETERMINED}（",
    TPL_ACT_NONE: f"本期行動：{MARK_NO_ACTION}",
    TPL_ACT_STALE_OPEN: f"（依據{MARK_STALE}，資料日 ",
    TPL_STRATEGY_NONE_TAIL: "：此策略下無歸類持股",
    # 持股已鍵入、但規則層沒有產出任何可引用的依據：不寫「尚無輸入」（有持股，不是沒輸入），也不暗示持有／正常
    TPL_HOLDINGS_NO_BASIS_TAIL: f"：規則層未產出可引用依據，{MARK_UNDETERMINED}",
    TPL_ACT_NO_BASIS: f"{MISSING_GLYPH} 本期行動：規則層未產出可引用依據，{MARK_UNDETERMINED}",
    TPL_UNCLASSIFIED_OPEN: f"{MISSING_GLYPH} 另有 ",
    TPL_UNCLASSIFIED_TAIL: f" 檔持股尚未分類策略，未納入判讀，{MARK_UNDETERMINED}",
    TPL_NOT_APPLICABLE_TAIL: f"：不適用，{MARK_UNDETERMINED}",
    TPL_NO_VARIATION_TAIL: f"：期間無變異，{MARK_UNDETERMINED}",
    TPL_CONTRACT_DRIFT_TAIL: f"：資料契約不一致，{MARK_UNDETERMINED}",
    TPL_NOT_DEFINED_TAIL: f"：{MARK_NOT_DEFINED}，{MARK_UNDETERMINED}",
    TPL_NOT_WIRED_TAIL: f"：{MARK_NOT_WIRED}，{MARK_UNDETERMINED}",
}
#: 摘要段 → 該段「策略標籤」模板 id。
TPL_SECTION_LABEL: dict = {SEC_BUY_AND_HOLD: TPL_LABEL_BUY_AND_HOLD, SEC_CAPITAL_GAIN: TPL_LABEL_CAPITAL_GAIN}

#: 欄位展開名（`Ref.field`）。⛔ 沒有任何欄位能展開 `strategy_source`（使用者自由文字）。
FIELD_LABEL = "label"
FIELD_TEXT = "text"
FIELD_VALUE = "value"
FIELD_AS_OF = "as_of"
FIELD_REASON = "reason"
FIELD_SYMBOL = "symbol"
FIELD_STRATEGY = "strategy"
FIELD_COUNT = "count"
FIELD_UNCLASSIFIED_COUNT = "unclassified_count"
FIELD_MARKER = "marker"
FIELD_WORDING = "wording"
FIELD_BIND = "bind"
FIELDS: tuple = (FIELD_LABEL, FIELD_TEXT, FIELD_VALUE, FIELD_AS_OF, FIELD_REASON, FIELD_SYMBOL, FIELD_STRATEGY,
                 FIELD_COUNT, FIELD_UNCLASSIFIED_COUNT, FIELD_MARKER, FIELD_WORDING, FIELD_BIND)

#: `section:<名>` 的顯示標籤（只有這四段有；其餘段名沒有 label 欄位）。
SECTION_REF_LABELS: dict = {
    "tw_trend": LABEL_TW_TREND, "intl_trend": LABEL_INTL_TREND, "valuation": LABEL_VALUATION,
    "industry": LABEL_INDUSTRY_TREND,
}
#: 診斷用：整份 Digest 層級（不屬任一摘要段）的顯示名。
LABEL_ALL_SECTIONS = "整份 Digest（跨段／結構）"
