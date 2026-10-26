"""shared/ia_nav.py — 五頁戰情室 IA 的「頁 / 葉 / 動作」名稱 SSOT（L0 Infra）。

═══ 這個模組在解什麼問題 ══════════════════════════════════════════════
四大鐵律第 4 條「空狀態引導」要求每個非正常狀態都附三要素：
**現在怎樣 ／ 為什麼 ／ 去哪補**。第三個要素是一句**指路**，
而指路句裡一定會出現一個分頁名或按鈕名。

**線框定的是「指到哪個分區」，不是「那個分區叫什麼名字」** ——
名字會改，指路句不會自己跟著改。本 repo 已經有這個 bug 的實例：

    src/ui/render/macro_ui_components.py::key_alerts_banner
        灰態文案寫死「請按『🚀 一鍵更新全部數據』」
    docs/wireframes/stock_ia_v1.html  葉1 ② 操作列
        新 IA 的 submit 改名為「🚀 更新今日戰情」

⇒ 改名之後，那句灰態指路會指向一顆**畫面上不存在的按鈕**。
線框自己在 ④ 今日關鍵橫幅的 note 裡點名了這個連帶事項。

本模組把「分區 / 動作的顯示名稱」收成唯一真相源，指路句一律用
`where_to_find()` / `where_to_press()` 組出來，**任何地方都不准手抄字串**。
改名只需要改這裡一行，全站指路自動跟著動。

═══ 這個模組**不做**什麼 ══════════════════════════════════════════════
- **不做導覽**。它只回字串，不切分頁、不碰 session、不 import streamlit。
- **不收舊 IA 的分頁名**。舊的 7 群組分頁（'🌍 市場環境' 等）由 `app.py`
  持有，本模組**不重抄** —— 抄過來就是第二份真相源（§2.1 SSOT）。
  舊分頁在五頁 IA 落地前不動、不接線（客戶 2026-09-05 指示）。

═══ 為什麼是 L0 ══════════════════════════════════════════════════════
純顯示字串 + 純函式，零 I/O、零 streamlit、零 L1+ 依賴。
同 `shared/etf_ui_labels.py` 的既有慣例（那也是「只是顯示字串」的 SSOT）。

出處：`docs/wireframes/stock_ia_v1.html` 的 `PAGES` 資料結構
（頁 id 直接沿用該檔的 `id` 欄，**不另取名**）。
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════
# 頁 id —— 直接沿用線框 `PAGES[*].id`，不另取名
# ══════════════════════════════════════════════════════════════════
#: 📊 大盤（2026-10-25 客戶裁示 Q1=C 新增）。⚠️ 不在原線框 `PAGES` 裡 —— 出處是
#: `docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md`（v4）＋客戶 2026-10-25 裁示。
#: 它承接「🚦 今天」的大盤能力；**「🚦 今天」在驗收前原樣保留**（不刪、不改名）。
PAGE_MARKET: str = "market"
PAGE_TODAY: str = "today"
PAGE_FIND: str = "find"
PAGE_INSPECT: str = "inspect"
PAGE_HOLD: str = "hold"
PAGE_WHY: str = "why"
#: 👤 我的（2026-10-25 客戶裁示 DEC-083 Q1=A 新增；AI 總管裁示排第 7、最後一頁）。⚠️ 不在原線框 `PAGES` 裡 ——
#: 出處是 `docs/vnext/ME_PAGE_DRAFT_2026-10-25.md`＋DEC-083。Google 帳號、Sheet 綁定與新版 Sheet SSOT 的唯一設定入口。
PAGE_ME: str = "me"

#: 頁 id → 顯示名（線框 `PAGES[*].name`）。
#: ⚠️ 順序就是側欄 radio 的順序（`app.py` 照這份展開）：大盤排第一個頁。
PAGE_LABELS: dict[str, str] = {
    PAGE_MARKET: "📊 大盤",
    PAGE_TODAY: "🚦 今天",
    PAGE_FIND: "🔍 找標的",
    PAGE_INSPECT: "🔬 查一檔",
    PAGE_HOLD: "💼 我的持股",
    PAGE_WHY: "📖 憑什麼",
    PAGE_ME: "👤 我的",
}

# ══════════════════════════════════════════════════════════════════
# 葉 / 分區 id —— 一律 `<page>.<slug>`，讓 `where_to_find` 能反查母頁
# ══════════════════════════════════════════════════════════════════
LEAF_TODAY_CONCLUSION: str = "today.conclusion"
LEAF_TODAY_DETAIL: str = "today.detail"
#: 📖 憑什麼 的資料體檢分區 —— 「這一源現在怎樣」的唯一去處。
SECTION_WHY_DATA_HEALTH: str = "why.data_health"
#: 💼 我的持股 的組合設定分區 —— ~~綁 Google Sheet 的入口~~（👤 我的 P1，DEC-083 Q1，有意識的更正，⛔ 不是漏刪：
#: 那一葉一直是**唯讀**的綁定狀態 / 持股預覽，沒有選 Sheet 的控制項）。現行：綁 Sheet 的入口是 `SECTION_ME_SHEET`。
SECTION_HOLD_PORTFOLIO_SETUP: str = "hold.portfolio_setup"
#: 📖 憑什麼 的 AI 問答分區 —— 「📊 大盤」頁「問 AI／查看依據」的去處。
#: 顯示名須與 `src/ui/views/page_why.py::LEAF_QA_TITLE` 相同（`tests/test_page_market.py` 釘住）。
SECTION_WHY_QA: str = "why.qa"
#: 👤 我的 的三張卡（DEC-083 C 段「首屏 1. Google 帳號 2. 目前 Sheet 3. 這本 Sheet 內目前分析的組合／觀察清單」）。
#: 顯示名須與 `src/ui/views/page_me.py` 的卡名相同（`tests/test_page_me.py` 釘住）。
SECTION_ME_ACCOUNT: str = "me.account"
SECTION_ME_SHEET: str = "me.sheet"
SECTION_ME_CONTENT: str = "me.content"
#: 💼 我的持股 的戰情室分頁（D2 / DEC-090 P-1 指路句用：「🛡️ 持股 › 💼 我的持股 › 戰情室」）。
#: ⚠️ 短名「戰情室」是線框 §4 P-1 核准的字面；頁內實際標題是 `page_hold.LEAF_WARROOM_TITLE`
#:    （「戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）」）。兩者的對帳由 `tests/test_ia_nav_shell.py` 釘住「前綴一致」。
SECTION_HOLD_WARROOM: str = "hold.warroom"

#: 分區 id → 該分區在**母頁之內**的顯示名（不含母頁名，由 `where_to_find` 串）。
SECTION_LABELS: dict[str, str] = {
    LEAF_TODAY_CONCLUSION: "今日結論",
    LEAF_TODAY_DETAIL: "指標明細（五桶逐段）",
    SECTION_WHY_DATA_HEALTH: "資料體檢",
    SECTION_HOLD_PORTFOLIO_SETUP: "組合設定",
    SECTION_WHY_QA: "AI 問答",
    SECTION_ME_ACCOUNT: "Google 帳號",
    SECTION_ME_SHEET: "目前 Sheet",
    SECTION_ME_CONTENT: "這本 Sheet 內容",
    SECTION_HOLD_WARROOM: "戰情室",
}

# ══════════════════════════════════════════════════════════════════
# 動作（按鈕）id → 按鈕上的字
# ══════════════════════════════════════════════════════════════════
#: 🚦 今天 的唯一 submit。**線框 F11**：form 內不得放 `st.button`
#: （實跑即拋 `StreamlitAPIException`），故「正常更新／強制重抓」收斂成
#: 一顆 submit + 一組 radio。
ACTION_UPDATE_TODAY: str = "update_today"
#: 👤 我的 P1（DEC-083 C 段：「明確『使用這本』」「重新讀取」「登入」）。
ACTION_ME_USE_SHEET: str = "me_use_sheet"
ACTION_ME_RELOAD: str = "me_reload"
ACTION_GOOGLE_LOGIN: str = "google_login"

ACTION_LABELS: dict[str, str] = {
    ACTION_UPDATE_TODAY: "🚀 更新今日戰情",
    ACTION_ME_USE_SHEET: "✅ 使用這本",
    ACTION_ME_RELOAD: "🔄 重新讀取",
    ACTION_GOOGLE_LOGIN: "🔐 用 Google 登入",
}

# ══════════════════════════════════════════════════════════════════
# 「要改持股 / 組合 / 觀察清單內容」的唯一指路句（👤 我的 P1，DEC-083 D 段）
# ══════════════════════════════════════════════════════════════════
#: 客戶 2026-10-25 逐字（⛔ 一字不改）：「需要修改持股／組合／觀察清單內容：P1 尚未提供 CRUD，因此必須誠實指路：
#: 『目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。』」
#: ⚠️ **本檔頭寫「不收舊 IA 的分頁名」—— 這是有意識的例外，⛔ 不是漏改**：這一句是客戶逐字句，舊頁籤名
#:    「📁 組合管理」是句子的一部分（不是本檔另抄一份分頁名 SSOT）。舊頁籤名的 SSOT 仍在 `app.py`；
#:    兩邊字面一致由 `tests/test_me_p1_deadends.py` 對 `app.py` 原始碼核對（舊頁籤改名 ⇒ 測試轉紅）。
CONTENT_EDIT_OLD_UI_WHERE: str = "目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。"

#: 指路句一律用這對引號包住目標，讓使用者一眼看出「這是畫面上的一個東西」。
_OPEN, _CLOSE = "「", "」"
#: 母頁與其分區之間的分隔符（線框原文用的就是這個）。
_SEP = " › "


# ══════════════════════════════════════════════════════════════════
# 導覽殼（D2，DEC-089 G1＝C ＋ DEC-090 形式 (b)）—— 六個方向 × 葉
# ══════════════════════════════════════════════════════════════════
# 客戶 2026-10-26 核准（`docs/vnext/NEWUI_D1_SHELL_WIREFRAME_2026-10-26.md`）：
# 最上層固定六個方向；現行 7 頁成為方向底下的「葉」；沒建的方向 / 頁誠實顯示「⬜ 尚未建置」。
# ⚠️ 本節**只有名稱 / 對映 / 文案模板**（純字串 + 純函式，零 streamlit、零 I/O）。
#    沒有投資語意、門檻、權重、資料源；畫面由 `app.py`（側欄）與 `src/ui/views/shell_nav.py`（主畫面）負責。

#: 六個方向 id。⚠️ 刻意加 `dir_` 前綴：`market` / `hold` / `me` 同時是頁 id，
#: 方向與頁共用同一個字串會讓「這個 id 是方向還是頁」在 grep 時分不清。
DIR_MARKET: str = "dir_market"
DIR_TARGET: str = "dir_target"
DIR_ACTION: str = "dir_action"
DIR_HOLD: str = "dir_hold"
DIR_ME: str = "dir_me"
DIR_DATA: str = "dir_data"

#: 方向 id → 顯示名。⚠️ 順序就是側欄第一層 radio 的順序（客戶核准，一次定案，之後不再改導覽）。
DIRECTION_LABELS: dict[str, str] = {
    DIR_MARKET: "📊 大盤",
    DIR_TARGET: "🎯 標的",
    DIR_ACTION: "⚡ 行動",
    DIR_HOLD: "🛡️ 持股",
    DIR_ME: "👤 我的",
    DIR_DATA: "🩺 資料中心",
}

#: 佔位頁（尚未建置）。⚠️ **不是 view**，不進 `PAGE_LABELS`，也不進 `app.py` 的 `_IA_VIEWS` 對帳。
PAGE_ACTION: str = "action"
PAGE_DATA_CENTER: str = "data_center"
PLACEHOLDER_LABELS: dict[str, str] = {
    PAGE_ACTION: "⚡ 行動",
    PAGE_DATA_CENTER: "🩺 資料中心",
}

#: 方向 id → 該方向底下的頁（順序＝第二層順序；**已建的在前、未建的在後**，線框 §2.2 ⑥；
#: 進入方向預設落在第一個頁）。每個頁 id 必須且只能出現一次（import 時對帳，見檔尾）。
NAV_TREE: dict[str, tuple[str, ...]] = {
    DIR_MARKET: (PAGE_MARKET, PAGE_TODAY),
    DIR_TARGET: (PAGE_FIND, PAGE_INSPECT),
    DIR_ACTION: (PAGE_ACTION,),
    DIR_HOLD: (PAGE_HOLD,),
    DIR_ME: (PAGE_ME,),
    DIR_DATA: (PAGE_WHY, PAGE_DATA_CENTER),
}

#: 方向本身就是佔位頁時，路徑只帶方向一層（線框 §3.6「📍 位置：⚡ 行動」）。
_DIRECTION_IS_THE_PAGE: frozenset[str] = frozenset({PAGE_ACTION})

#: ⬜ 標記與圖例（DEC-090 ③）。未建項目靠文字與符號辨識，不只靠顏色。
UNBUILT_MARK: str = "⬜"
NAV_LEGEND: str = "⬜ ＝ 尚未建置"
#: 第二層小標題（DEC-090 ④）：「〈方向〉底下：」
_SUBTITLE_TAIL = " 底下："
#: 位置列（DEC-090 ②）。不加任何數字或結論。
_POSITION_PREFIX = "📍 位置："
#: 🚦 今天頁頂一行說明（DEC-090 ⑤，線框 §3.7 S6）。
_TODAY_NOTICE_HEAD = "ⓘ "


def is_built(page: str) -> bool:
    """頁是否已建（N4）。佔位頁 ＝ 未建；未知 id → Fail Loud。"""
    if page in PAGE_LABELS:
        return True
    if page in PLACEHOLDER_LABELS:
        return False
    raise ValueError(
        f"未知的頁 id {page!r}；合法值：{sorted(PAGE_LABELS)} + {sorted(PLACEHOLDER_LABELS)}")


def direction_label(direction: str) -> str:
    if direction not in DIRECTION_LABELS:
        raise ValueError(f"未知的方向 id {direction!r}；合法值：{sorted(DIRECTION_LABELS)}")
    return DIRECTION_LABELS[direction]


def page_direction(page: str) -> str:
    """頁 id → 它所屬的方向 id。未知 id → Fail Loud。"""
    for _d, _pages in NAV_TREE.items():
        if page in _pages:
            return _d
    raise ValueError(f"頁 id {page!r} 不在任何方向底下；NAV_TREE={NAV_TREE}")


def direction_is_built(direction: str) -> bool:
    """方向底下只要有一個已建的頁就算已建（⚡ 只有佔位頁 ⇒ 未建）。"""
    return any(is_built(p) for p in NAV_TREE[direction])


def path_text(page: str, *, collapse_same_name: bool = False) -> str:
    """頁 id → ``'🩺 資料中心 › 📖 憑什麼'``（不含引號；方向 › 頁）。

    ⚡ 行動：方向本身就是佔位頁 ⇒ 只回 ``'⚡ 行動'``（線框 §3.6）。
    ``collapse_same_name=True``（`where_to_find` 指路句用）：方向名與頁名相同時只留一層
    （📊 大盤 › 📊 大盤 → 📊 大盤；👤 我的 › 👤 我的 → 👤 我的）。
    理由：指路句要塞進有字數上限的卡面短句（`FACT_VALUE_MAX_CHARS`），
    「👤 我的 › 👤 我的 › 這本 Sheet 內容」會讓既有 `hold.ai_summary` 短句超限被契約層截斷；
    疊兩個一樣的名字也沒有多給使用者任何資訊。
    位置列（`position_text`）不折疊，照線框 §3.1／§3.6 逐字兩層。
    """
    _d = direction_label(page_direction(page))
    if page in _DIRECTION_IS_THE_PAGE:
        return _d
    _pl = page_label(page)
    if collapse_same_name and _pl == _d:
        return _d
    return f"{_d}{_SEP}{_pl}"


def position_text(page: str) -> str:
    """主畫面最上方「📍 位置列」的字（DEC-090 ②）。"""
    return f"{_POSITION_PREFIX}{path_text(page)}"


def first_built_page(direction: str) -> str:
    """進入方向預設落點（DEC-090 ⑥）：第一個已建的頁；全未建 ⇒ 第一個頁。"""
    _pages = NAV_TREE[direction]
    for _p in _pages:
        if is_built(_p):
            return _p
    return _pages[0]


def direction_options() -> tuple[str, ...]:
    """側欄第一層 radio 的顯示字串（方向名；整個方向未建 ⇒ 尾端加 ⬜）。"""
    return tuple(
        DIRECTION_LABELS[d] if direction_is_built(d)
        else f"{DIRECTION_LABELS[d]} {UNBUILT_MARK}"
        for d in NAV_TREE)


def direction_from_option(option: str) -> str | None:
    """第一層顯示字串 → 方向 id；不是任何方向（＝「不使用」）→ None。"""
    for _d, _o in zip(NAV_TREE, direction_options()):
        if _o == option:
            return _d
    return None


def leaf_options(direction: str) -> tuple[str, ...]:
    """側欄第二層 radio 的顯示字串（未建的頁尾端加 ⬜）。"""
    return tuple(
        page_label(p) if is_built(p) else f"{page_label(p)} {UNBUILT_MARK}"
        for p in NAV_TREE[direction])


def page_from_leaf_option(direction: str, option: str) -> str | None:
    """第二層顯示字串 → 頁 id；不在該方向底下 → None（呼叫端必須處理，不得靜默改用預設頁）。"""
    for _p, _o in zip(NAV_TREE[direction], leaf_options(direction)):
        if _o == option:
            return _p
    return None


def leaf_subtitle(direction: str) -> str:
    """第二層小標題：「🎯 標的 底下：」（DEC-090 ④）。"""
    return f"{direction_label(direction)}{_SUBTITLE_TAIL}"


def today_notice() -> str:
    """🚦 今天頁頂一行說明（DEC-090 ⑤）。新版的大盤＝📊 方向的第一個頁。"""
    return (f"{_TODAY_NOTICE_HEAD}{page_label(PAGE_TODAY)} 是舊版頁面，暫時保留。"
            f"新版的大盤請到側欄{_OPEN}{direction_label(DIR_MARKET)}{_CLOSE}第一個頁。")


# ── 佔位頁文案（DEC-090 P-1／P-2；三要素：現在怎樣／為什麼／去哪）─────────────────────────
#: ⑨（DEC-090）：指到舊版的說明句補「側欄選『不使用』」這一步。
#: 位置決定（D2 自決，交付報告揭露）：插在「切回舊版」與「→」之間，保持客戶句型
#: 「目前請切回舊版 → 〔位置〕；新版〔項目〕會在下一階段處理。」的固定字連續不被拆開。
OLD_UI_SWITCH_STEP: str = "（側欄選『不使用』）"
#: 舊版頁籤路徑。⚠️ 與 `CONTENT_EDIT_OLD_UI_WHERE` 同一個有意識的例外（舊頁籤名的 SSOT 仍在 `app.py`，
#: 此處是客戶逐字句的一部分，不是第二份分頁名 SSOT）；兩邊字面一致由 `tests/test_ia_nav_shell.py` 對 `app.py` 核對。
OLD_UI_PATH_WARROOM: str = "💼 我的持股戰情室"
OLD_UI_PATH_DIAGNOSTIC: str = "🔧 工具箱 › 🔎 資料診斷"


def old_ui_sentence(where: str, new_item: str, *, schedule_note: str = "") -> str:
    """舊版指路句：「目前請切回舊版（側欄選『不使用』）→ 〔where〕；新版〔new_item〕會在下一階段處理〔note〕。」"""
    return f"目前請切回舊版{OLD_UI_SWITCH_STEP}→ {where}；新版{new_item}會在下一階段處理{schedule_note}。"


#: page id → (標題, 現在怎樣, 為什麼, 去哪 的句子們)。字面逐字依線框 §4（客戶 DEC-090 P-1／P-2「同意」）。
PLACEHOLDER_COPY: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    PAGE_ACTION: (
        PLACEHOLDER_LABELS[PAGE_ACTION],
        "⚡ 行動這個方向目前沒有任何內容。",
        "這個方向已規劃但還沒開始建，不是故障，也不是資料出問題。"
        "這裡沒有內容，不代表目前沒有需要處理的事。",
        (
            "目前還沒有集中的「行動」頁。持股的風險與配置檢查請到"
            + "{warroom}（需先登入並選定組合）。",
            "{old}",
        ),
    ),
    PAGE_DATA_CENTER: (
        PLACEHOLDER_LABELS[PAGE_DATA_CENTER],
        "資料中心本體目前沒有內容：這裡不會彙總各資料來源是否健康、是否過期、哪裡缺值。",
        "本體要等後續步驟才會建立，不是故障。這裡沒有看到警示，不代表資料都正常。",
        (
            "目前可到{health}查看，那裡的涵蓋範圍以該頁自己的揭露為準（不是全站體檢）。",
            "{old}",
        ),
    ),
}


def placeholder_copy(page: str) -> dict[str, object]:
    """佔位頁文案（已把指路句組好）。非佔位頁 → Fail Loud。

    回傳 ``{'title','now','why','where': tuple[str, ...]}``；全部是純字串，沒有數字、燈號。
    """
    if page not in PLACEHOLDER_COPY:
        raise ValueError(f"{page!r} 不是佔位頁；佔位頁：{sorted(PLACEHOLDER_COPY)}")
    _title, _now, _why, _where = PLACEHOLDER_COPY[page]
    if page == PAGE_ACTION:
        # 客戶句型：「新版 ⚡ 行動會在下一階段處理」——「新版」後有一個空格、「會」前無空格。
        _old = old_ui_sentence(OLD_UI_PATH_WARROOM, f" {PLACEHOLDER_LABELS[PAGE_ACTION]}",
                               schedule_note="（尚未排定日期）")
    else:
        _old = old_ui_sentence(OLD_UI_PATH_DIAGNOSTIC, "資料中心")
    _fmt = {
        "warroom": where_to_find(SECTION_HOLD_WARROOM),
        "health": where_to_find(SECTION_WHY_DATA_HEALTH),
        "old": _old,
    }
    return {"title": _title, "now": _now, "why": _why,
            "where": tuple(w.format(**_fmt) for w in _where)}


def page_label(page: str) -> str:
    """頁 id → 顯示名（含 D2 的兩個佔位頁）。未知 id → Fail Loud（§1）。

    不回一個「還算像樣的預設字串」——那會讓打錯的 id 靜默變成一句
    看起來正常、實際指向不存在分頁的指路句，永遠沒人發現。
    """
    if page in PAGE_LABELS:
        return PAGE_LABELS[page]
    if page in PLACEHOLDER_LABELS:
        return PLACEHOLDER_LABELS[page]
    raise ValueError(
        f"未知的頁 id {page!r}；合法值：{sorted(PAGE_LABELS)} + {sorted(PLACEHOLDER_LABELS)}")


def action_label(action: str) -> str:
    """動作 id → 按鈕上的字。未知 id → Fail Loud（§1）。"""
    if action not in ACTION_LABELS:
        raise ValueError(
            f"未知的動作 id {action!r}；合法值：{sorted(ACTION_LABELS)}")
    return ACTION_LABELS[action]


def where_to_find(dest: str) -> str:
    """頁 / 分區 id → 一句可以直接嵌進指路句的目標描述（D2 起**多帶方向名**，DEC-090 ⑦）。

    Args:
        dest: 頁 id（如 ``'today'``），或 ``'<page>.<slug>'`` 的分區 id。

    Returns:
        頁：``'「📊 大盤 › 🚦 今天」'``；分區：``'「🩺 資料中心 › 📖 憑什麼 › 資料體檢」'``。
        ⚡ 行動（方向本身就是佔位頁）只帶一層：``'「⚡ 行動」'``（線框 §3.6）。

    Raises:
        ValueError: 未知的頁或分區 id（§1 Fail Loud，理由同 `page_label`）。

    為什麼分區要用 ``'<page>.<slug>'``：這樣**母頁名不必再抄一次** ——
    改「📖 憑什麼」這個名字時，所有指到它底下分區的句子一起跟著改。
    方向層同理：頁屬於哪個方向只在 `NAV_TREE` 一處定義。
    """
    if dest in PAGE_LABELS or dest in PLACEHOLDER_LABELS:
        return f"{_OPEN}{path_text(dest, collapse_same_name=True)}{_CLOSE}"
    if dest not in SECTION_LABELS:
        raise ValueError(
            f"未知的分區 id {dest!r}；"
            f"合法值：{sorted(PAGE_LABELS)} + {sorted(SECTION_LABELS)}")
    _page = dest.split(".", 1)[0]
    if _page not in PAGE_LABELS:
        raise ValueError(
            f"分區 id {dest!r} 的母頁 {_page!r} 不在 PAGE_LABELS —— "
            "分區 id 必須寫成 '<page>.<slug>'")
    return f"{_OPEN}{path_text(_page, collapse_same_name=True)}{_SEP}{SECTION_LABELS[dest]}{_CLOSE}"


def where_to_press(action: str) -> str:
    """動作 id → ``'按「🚀 更新今日戰情」'``。未知 id → Fail Loud（§1）。"""
    return f"按{_OPEN}{action_label(action)}{_CLOSE}"


# ══════════════════════════════════════════════════════════════════
# 導覽樹自洽對帳（import 時就跑；用 raise 不用 assert —— `python -O` 不會把它拿掉，§1）
# ══════════════════════════════════════════════════════════════════
def reconcile_nav(view_page_ids) -> None:
    """導覽樹 ↔ 頁表 ↔（呼叫端提供的）view 派發表，三方對帳；對不起來 → ``RuntimeError``。

    ``view_page_ids``：`app.py` 的 ``_IA_VIEWS`` 的 key 集合（真的有 renderer 的頁）。
    規則：
      1. 方向表與樹的方向一致；
      2. 樹裡每個頁 id 恰出現一次，且都是 `PAGE_LABELS` ∪ `PLACEHOLDER_LABELS`；
      3. `PAGE_LABELS` 每個頁都在樹裡（7 頁一個不少）；
      4. 樹裡「已建」的頁 ＝ 派發表（view_page_ids）；佔位頁不得有 renderer；
      5. 每個方向內「已建的在前、未建的在後」（線框 §2.2 ⑥）。
    """
    if set(DIRECTION_LABELS) != set(NAV_TREE):
        raise RuntimeError(f"DIRECTION_LABELS 與 NAV_TREE 的方向對不起來："
                           f"{sorted(DIRECTION_LABELS)} vs {sorted(NAV_TREE)}")
    if set(PAGE_LABELS) & set(PLACEHOLDER_LABELS):
        raise RuntimeError(f"佔位頁 id 與 PAGE_LABELS 撞名：{sorted(set(PAGE_LABELS) & set(PLACEHOLDER_LABELS))}")
    _flat = [p for _ps in NAV_TREE.values() for p in _ps]
    _dups = sorted({p for p in _flat if _flat.count(p) > 1})
    if _dups:
        raise RuntimeError(f"NAV_TREE 內有頁出現在多個位置：{_dups}")
    _known = set(PAGE_LABELS) | set(PLACEHOLDER_LABELS)
    if set(_flat) != _known:
        raise RuntimeError(
            f"NAV_TREE 與頁表對不起來（漏接 / 多接）：缺 {sorted(_known - set(_flat))}，"
            f"多 {sorted(set(_flat) - _known)}")
    _built = {p for p in _flat if p in PAGE_LABELS}
    if set(view_page_ids) != _built:
        raise RuntimeError(
            f"view 派發表與導覽樹的已建頁對不起來：派發表 {sorted(view_page_ids)} vs 樹 {sorted(_built)}")
    for _d, _ps in NAV_TREE.items():
        _flags = [p in PAGE_LABELS for p in _ps]
        if _flags != sorted(_flags, reverse=True):
            raise RuntimeError(f"方向 {_d} 底下未建的頁排在已建的前面：{_ps}")
    for _p in PLACEHOLDER_COPY:
        if _p not in PLACEHOLDER_LABELS:
            raise RuntimeError(f"PLACEHOLDER_COPY 有未宣告的佔位頁 {_p!r}")
    if set(PLACEHOLDER_COPY) != set(PLACEHOLDER_LABELS):
        raise RuntimeError("佔位頁缺文案：" + str(sorted(set(PLACEHOLDER_LABELS) - set(PLACEHOLDER_COPY))))


# 不依賴 view 派發表的那幾條，import 時就先驗（派發表那條由 `app.py` 再呼叫一次）。
reconcile_nav(set(PAGE_LABELS))
