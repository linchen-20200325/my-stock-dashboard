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
PAGE_TODAY: str = "today"
PAGE_FIND: str = "find"
PAGE_INSPECT: str = "inspect"
PAGE_HOLD: str = "hold"
PAGE_WHY: str = "why"

#: 頁 id → 顯示名（線框 `PAGES[*].name`）。
PAGE_LABELS: dict[str, str] = {
    PAGE_TODAY: "🚦 今天",
    PAGE_FIND: "🔍 找標的",
    PAGE_INSPECT: "🔬 查一檔",
    PAGE_HOLD: "💼 我的持股",
    PAGE_WHY: "📖 憑什麼",
}

# ══════════════════════════════════════════════════════════════════
# 葉 / 分區 id —— 一律 `<page>.<slug>`，讓 `where_to_find` 能反查母頁
# ══════════════════════════════════════════════════════════════════
LEAF_TODAY_CONCLUSION: str = "today.conclusion"
LEAF_TODAY_DETAIL: str = "today.detail"
#: 📖 憑什麼 的資料體檢分區 —— 「這一源現在怎樣」的唯一去處。
SECTION_WHY_DATA_HEALTH: str = "why.data_health"
#: 💼 我的持股 的組合設定分區 —— 綁 Google Sheet 的入口。
SECTION_HOLD_PORTFOLIO_SETUP: str = "hold.portfolio_setup"

#: 分區 id → 該分區在**母頁之內**的顯示名（不含母頁名，由 `where_to_find` 串）。
SECTION_LABELS: dict[str, str] = {
    LEAF_TODAY_CONCLUSION: "今日結論",
    LEAF_TODAY_DETAIL: "指標明細（五桶逐段）",
    SECTION_WHY_DATA_HEALTH: "資料體檢",
    SECTION_HOLD_PORTFOLIO_SETUP: "組合設定",
}

# ══════════════════════════════════════════════════════════════════
# 動作（按鈕）id → 按鈕上的字
# ══════════════════════════════════════════════════════════════════
#: 🚦 今天 的唯一 submit。**線框 F11**：form 內不得放 `st.button`
#: （實跑即拋 `StreamlitAPIException`），故「正常更新／強制重抓」收斂成
#: 一顆 submit + 一組 radio。
ACTION_UPDATE_TODAY: str = "update_today"

ACTION_LABELS: dict[str, str] = {
    ACTION_UPDATE_TODAY: "🚀 更新今日戰情",
}

#: 指路句一律用這對引號包住目標，讓使用者一眼看出「這是畫面上的一個東西」。
_OPEN, _CLOSE = "「", "」"
#: 母頁與其分區之間的分隔符（線框原文用的就是這個）。
_SEP = " › "


def page_label(page: str) -> str:
    """頁 id → 顯示名。未知 id → Fail Loud（§1）。

    不回一個「還算像樣的預設字串」——那會讓打錯的 id 靜默變成一句
    看起來正常、實際指向不存在分頁的指路句，永遠沒人發現。
    """
    if page not in PAGE_LABELS:
        raise ValueError(f"未知的頁 id {page!r}；合法值：{sorted(PAGE_LABELS)}")
    return PAGE_LABELS[page]


def action_label(action: str) -> str:
    """動作 id → 按鈕上的字。未知 id → Fail Loud（§1）。"""
    if action not in ACTION_LABELS:
        raise ValueError(
            f"未知的動作 id {action!r}；合法值：{sorted(ACTION_LABELS)}")
    return ACTION_LABELS[action]


def where_to_find(dest: str) -> str:
    """分區 id → 一句可以直接嵌進指路句的目標描述。

    Args:
        dest: 頁 id（如 ``'today'``），或 ``'<page>.<slug>'`` 的分區 id。

    Returns:
        ``'「📖 憑什麼 › 資料體檢」'`` 這樣的字串。

    Raises:
        ValueError: 未知的頁或分區 id（§1 Fail Loud，理由同 `page_label`）。

    為什麼分區要用 ``'<page>.<slug>'``：這樣**母頁名不必再抄一次** ——
    改「📖 憑什麼」這個名字時，所有指到它底下分區的句子一起跟著改。
    """
    if dest in PAGE_LABELS:
        return f"{_OPEN}{PAGE_LABELS[dest]}{_CLOSE}"
    if dest not in SECTION_LABELS:
        raise ValueError(
            f"未知的分區 id {dest!r}；"
            f"合法值：{sorted(PAGE_LABELS)} + {sorted(SECTION_LABELS)}")
    _page = dest.split(".", 1)[0]
    if _page not in PAGE_LABELS:
        raise ValueError(
            f"分區 id {dest!r} 的母頁 {_page!r} 不在 PAGE_LABELS —— "
            "分區 id 必須寫成 '<page>.<slug>'")
    return f"{_OPEN}{PAGE_LABELS[_page]}{_SEP}{SECTION_LABELS[dest]}{_CLOSE}"


def where_to_press(action: str) -> str:
    """動作 id → ``'按「🚀 更新今日戰情」'``。未知 id → Fail Loud（§1）。"""
    return f"按{_OPEN}{action_label(action)}{_CLOSE}"
