"""src/ui/views/_ui_kit.py — 五頁戰情室共用的**渲染**層（L5 UI）。

四大鐵律（線框 `docs/wireframes/stock_ia_v1.html` §04）的**畫面落點**。
五頁共用；本批只有 `page_today` 消費，但介面按五頁設計。

═══ 本模組的邊界（**先讀這段**，它決定了這裡不准出現什麼）═══════════════
**這裡只有「怎麼畫」，沒有「這是什麼」。**

- ❌ **不定義狀態。** 四態 / 七態的唯一真相源是 L0 `shared/ui_state.py`
  （`UI_IDLE` / `UI_LOADING` / `UI_FAILED` / `UI_EMPTY` / `UI_DEGRADED` /
  `UI_UNWIRED` / `UI_LIVE` ＋ `UI_STATE_META` ＋ `classify_ui_state()` ＋
  `is_alarming()` ＋ `state_meta()`）。本檔**只 import、不鏡像、不加第八態**。
- ❌ **不定義資料結構。** `Note` / `Card` / `Block` 已存在於
  `src/ui/tabs/tab_today.py`（PR #662，有 `tests/test_p01_today_skeleton.py`
  守著），本檔 **import 復用**，不複寫一份。
- ❌ **不判燈、不判態、不取數、不建快取。** 全檔 **0 個**
  `@st.cache_data` / `@st.cache_resource`（前車之鑑：`CLAUDE.md §8.2.A.2`
  **V-SMART-CACHE-1** —— `etf_tab_smart.py` 在 L5 自建 5 個 cache ＋ 5 個
  inline `ttl=` 數字，同時違反 §8.2「cache 才能集中」與 §3.3）。
- ❌ **不手抄分頁名 / 按鈕名 / 分區名。** 那些走 L0 `shared/ia_nav.py`，
  由呼叫端組好字串再傳進來。

═══ 鐵律 1：3 欄自適應網格 ═════════════════════════════════════════════
`grid()` 一律 `min(cols, MAX_COLS)`，多的**換行排下一列，不是加欄**；
`MAX_COLS` 直接 import `tab_today.MAX_COLS`，**本檔不另立一個 3**。

⚠️ 這裡有一個已知取捨要講明：`tab_today._grid` 的稽核結論是「**連參數都
不要有**」—— 它原本的 `per_row=3` 讓 `_grid(cards, 7)` 一行就開出 7 欄，
而所有守衛照樣綠。本 kit 仍保留 `cols`（五頁確有 1 欄 / 2 欄的版面需求），
但把那個失效模式從「靜默成功」改成「**夾住 + 出聲**」：
上限由單一常數決定，呼叫端**沒有語法可以超過它**。

═══ 鐵律 2：Form 封裝防重繪 ═══════════════════════════════════════════
`single_submit_form()` 是本 kit 唯一的表單入口，結構上保證：
form 內**只有一顆** `st.form_submit_button`、**沒有** `st.button` /
`st.download_button`（Streamlit 實跑即拋 `StreamlitAPIException`，線框 F11）、
模式切換用 form 內的 `st.radio`。

⚠️ **form 只是外殼，防重繪真正靠的是「widget 當下值 / 已套用值」分家。**
radio 綁 `widget_key`，下游一律只讀 submit handler 寫進去的 `applied_key`
（本頁的讀取器是 `tab_today.applied_update_mode()`）。
只包一層 `st.form` 只擋得住互動 rerun，**重運算一分沒省**。

═══ 鐵律 3：四態分離的**視覺**落點 ═════════════════════════════════════
狀態頻道的 glyph / 中文 / 色碼一律取自 L0 `state_meta(state)`，
本檔**不配色、不挑 emoji**。

⚠️ 本檔真正新增的那條防線是**兩個紅撞在一起**：
`UI_STATE_META[UI_FAILED]` 的 glyph 是 `🔴`（**故障紅**），
`macro_buckets.LEVEL_EMOJI["red"]` 也是 `🔴`（**訊號紅**）。
同一張卡若兩個頻道都出 emoji，使用者無從分辨「VIX 真的很高」與「VIX 抓不到」。
處置沿用 user 2026-08-26 對 `src/ui/render/macro_v2_cards.py::STATE_META`
的裁示：**狀態頻道出 glyph ＋ 中文，訊號頻道只出中文標籤**。
`render_card()` 直接拒收帶 glyph 的 `signal_text`（fail loud，不是只靠測試掃）。

═══ 鐵律 4：空狀態引導三要素 ═══════════════════════════════════════════
資料型別是 `tab_today.Note(now, why, where)`（三個都不得為空、都不得自帶
狀態 glyph，`__post_init__` 會 raise）。本檔**只包一層渲染** `render_note()`，
**刻意不另做 `empty_state(now, why, where)`** —— 再開一支收三個 str 的入口
等於旁邊多一條繞過 `Note` 驗證的路。

⚠️ 上游例外訊息請先過 `tab_today.scrub_state_glyphs()` / `upstream_error_why()`
再放進 `Note.why`：全 repo 帶 `🔴` 的字串有數百處，一個「FRED 連線失敗 🔴」
直接塞進去會在 `__post_init__` 變成 `ValueError`，把**一張該畫出來的紅卡**
變成**整頁未捕捉例外** —— §1 要的是「紅態看得見」，不是「換一種炸法」。

═══ Streamlit API 相容性 ═══════════════════════════════════════════════
本檔只用 `st.columns` / `st.markdown` / `st.caption` / `st.form` /
`st.radio` / `st.form_submit_button` / `st.divider` —— 全部遠早於
`requirements.txt` 宣告的 floor（由
`tests/test_macro_v2_tab.py::TestStreamlitFloorCompatibility` 反解並守衛）。
**本檔不寫死版本號**（§8.2.A.0 規則 4：會漂移的量測值一律現場量測）。
"""
from __future__ import annotations

import html as _html
from typing import Any, Iterator, Sequence

import streamlit as st

from shared.macro_buckets import LEVEL_EMOJI
from shared.ui_state import UI_LIVE, UI_STATE_META, is_alarming, state_meta
# L5 → L5 同層 import（C3 分層守衛合規）。資料結構與版面上限的唯一來源。
from src.ui.tabs.tab_today import MAX_COLS, Card, Note

__all__ = [
    "MAX_COLS", "Card", "Note",
    "is_alarming", "state_meta",
    "grid", "render_note", "render_card", "render_cards",
    "section_header", "single_submit_form",
]

#: 訊號頻道**禁止出現**的符號 = 狀態 glyph ∪ 燈號 emoji。
#: 兩個集合都是 L0 的，本檔只做聯集，不新增任何字面。
#: 聯集的理由見檔頭鐵律 3：兩邊都有 `🔴`，撞在同一張卡上就沒有資訊了。
_BANNED_SIGNAL_GLYPHS: frozenset[str] = (
    frozenset(_g for _n, _g, _h in UI_STATE_META.values())
    | frozenset(LEVEL_EMOJI.values())
)


# ══════════════════════════════════════════════════════════════════
# 鐵律 1 — 網格
# ══════════════════════════════════════════════════════════════════
def grid(items: Sequence[Any],
         cols: int = MAX_COLS) -> Iterator[tuple[Sequence[Any], list]]:
    """把 `items` 切成每列至多 `min(cols, MAX_COLS)` 格，逐列 yield `(chunk, columns)`。

    Args:
        items: 要排的東西（通常是 `Card`）。空序列 → 一列都不 yield。
        cols: 想要的欄數。**上限硬夾在 `MAX_COLS`**。

    Yields:
        `(該列的 items, 該列的 st.columns 物件)`，兩者等長。

    Raises:
        ValueError: `cols` 不是 ≥1 的整數（§1：不猜呼叫端的意思）。

    多出來的格子**換行排下一列**；天然不足一列的**保持原欄數、不硬湊三欄**
    （線框 §04：硬湊三欄跟擠七欄一樣是排版失敗）。
    """
    if isinstance(cols, bool) or not isinstance(cols, int) or cols < 1:
        raise ValueError(f"grid(cols=) 必須是 ≥1 的整數，收到 {cols!r}")
    _n = min(cols, MAX_COLS)
    if cols > MAX_COLS:
        # §1 不靜默：夾住是對的，但**不能讓呼叫端以為它拿到了 7 欄**。
        print(f"[views/_ui_kit.grid] ⚠️ 要求 {cols} 欄，超過全站上限 "
              f"MAX_COLS={MAX_COLS} → 已夾到 {_n} 欄並換行排列。"
              "欄數上限是視覺規格，不是呼叫端可以覆寫的東西。")
    for _i in range(0, len(items), _n):
        _chunk = items[_i:_i + _n]
        yield _chunk, st.columns(len(_chunk))


# ══════════════════════════════════════════════════════════════════
# 鐵律 4 — 空狀態三要素（只包渲染，型別與驗證都在 `tab_today.Note`）
# ══════════════════════════════════════════════════════════════════
def render_note(note: Note) -> None:
    """畫出空狀態引導三要素：**現況一句話 / 為什麼沒有 / 去哪補**。

    收 `Note` 而不是收三個 str —— 三個 str 的入口等於旁邊多一條繞過
    `Note.__post_init__`（空值 + 狀態 glyph 兩道驗證）的路。
    """
    st.markdown(
        f"{note.now}\n\n"
        f"　**為什麼沒有**：{note.why}\n\n"
        f"　**去哪補**：{note.where}"
    )


# ══════════════════════════════════════════════════════════════════
# 鐵律 3 — 四態視覺
# ══════════════════════════════════════════════════════════════════
def _chip(text: str, color: str) -> str:
    """一顆小標籤的 HTML。內容一律 `html.escape`。"""
    return (f'<span style="display:inline-block;padding:1px 8px;'
            f'border-radius:999px;border:1px solid {_html.escape(color)}55;'
            f'color:{_html.escape(color)};font-size:11.5px;font-weight:600;'
            f'white-space:nowrap;">{_html.escape(text)}</span>')


def render_card(card: Card, *,
                signal_text: str = "",
                signal_color: str = "",
                facts: Sequence[tuple[str, str]] = ()) -> None:
    """畫一張卡。**狀態頻道（glyph ＋ 中文）與訊號頻道（純中文）分開出。**

    Args:
        card: `tab_today.Card`。狀態、標題、結論文字、`Note` 都在裡面，
            且它的 `__post_init__` 已保證「非 `live` 必附三要素」
            與「非 `live` 不得帶結論文字」。**本函式不重複那兩道驗證。**
        signal_text: 燈號的**中文標籤**（如「綠」「循環惡化」）。
            由呼叫端從 SSOT 取（L0 `bucket_level_label()` / L4 `band_meta()`），
            本層不生產這個字。空字串 = 這張卡沒有燈號頻道。
        signal_color: 燈號色碼（`macro_buckets.LEVEL_COLOR[...]` 或 L4 給的色）。
            `signal_text` 有值而這個沒給 → 退回狀態頻道的色，**不自己挑一個新色**。
        facts: `((欄位名, 值), ...)` 的中繼資料列（門檻帶 / 命中來源 / 門檻出處）。
            **任何狀態都可帶** —— 這些不是「這一輪量到的數字」，
            而是「這盞燈本來長什麼樣」，未接線時照樣該讓人看見。

    Raises:
        ValueError: `signal_text` 帶了狀態 glyph 或燈號 emoji（見檔頭鐵律 3）。

    ⚠️ **粒度就是一張卡**：狀態掛在卡上、不掛在區塊上。掛在區塊上的話
    「只有其中一格壞掉」會被同區塊其他格子替它通過（線框：**逐格獨立判態**，
    一格壞不把另外兩格一起染色）。
    """
    _bad = sorted(_g for _g in _BANNED_SIGNAL_GLYPHS if _g in str(signal_text))
    if _bad:
        raise ValueError(
            f"卡 {card.key!r} 的 signal_text 含符號 {_bad} —— "
            "訊號頻道**只出中文標籤**。狀態頻道的『取得失敗』與燈號的『紅』"
            "在 SSOT 裡用的是同一顆 🔴，同一張卡出兩個等於沒有資訊。"
            "（user 2026-08-26 對 `macro_v2_cards.STATE_META` 的同一裁示。）")
    _name, _glyph, _hex = state_meta(card.state)
    _head = _chip(f"{_glyph} {_name}", _hex)
    if signal_text:
        _head += "　" + _chip(signal_text, signal_color or _hex)
    st.markdown(
        f'<div style="border:1px solid {_hex}33;border-left:3px solid {_hex};'
        'border-radius:0 6px 6px 0;padding:8px 12px;margin:4px 0;">'
        f'<div>{_head}</div>'
        f'<div style="font-weight:600;margin-top:4px;">'
        f'{_html.escape(card.label)}</div>'
        + (f'<div style="font-size:24px;font-weight:700;line-height:1.25;'
           f'margin-top:2px;">{_html.escape(card.value)}</div>'
           if card.value else "")
        + "</div>",
        unsafe_allow_html=True,
    )
    for _k, _v in facts:
        st.caption(f"{_k}　{_v}")
    if card.state != UI_LIVE and card.note is not None:
        render_note(card.note)


def render_cards(cards: Sequence[Card], cols: int = MAX_COLS) -> None:
    """把一組卡照鐵律 1 排好並逐張畫出（無燈號頻道、無 facts 的簡單情形）。"""
    for _chunk, _columns in grid(cards, cols):
        for _card, _col in zip(_chunk, _columns):
            with _col:
                render_card(_card)


def section_header(title: str, caption: str = "") -> None:
    """區塊標題（＋一句說明）。標題文字由呼叫端提供，本層不手抄任何分頁名。"""
    st.markdown(f"#### {title}")
    if caption:
        st.caption(caption)


# ══════════════════════════════════════════════════════════════════
# 鐵律 2 — Form 封裝防重繪
# ══════════════════════════════════════════════════════════════════
def single_submit_form(form_key: str, *,
                       submit_label: str,
                       radio_label: str,
                       options: Sequence[str],
                       option_labels: dict,
                       widget_key: str,
                       applied_key: str) -> bool:
    """本 kit 唯一的表單入口：**一個 form、一組 radio、一顆 submit**。

    Args:
        form_key: `st.form` 的 key。
        submit_label: submit 上的字。請走 `shared.ia_nav.action_label()`，
            **不要手抄**（改名時全站指路句要一起動）。
        radio_label / options / option_labels: form 內那組 radio。
        widget_key: radio 的 session key —— **widget 當下值**。下游禁止讀它。
        applied_key: **已套用值**的 session key。只有本函式的 submit 分支會寫，
            寫入形狀為 `{"mode": <option>}`。

    Returns:
        這一次 rerun 是否由 submit 觸發。

    ⚠️ **form 內不得放 `st.button` / `st.download_button`**（Streamlit 實跑即拋
    `StreamlitAPIException`）。本函式在結構上不給你放的縫 —— 要多一個動作，
    請多一個 radio 選項，不是多一顆鈕。
    """
    if not options:
        raise ValueError(f"single_submit_form({form_key!r}) 的 options 不得為空")
    _missing = [_o for _o in options if _o not in option_labels]
    if _missing:
        raise ValueError(
            f"single_submit_form({form_key!r}) 的 options {_missing} 沒有對應的顯示名 —— "
            "§1：不拿 key 當畫面文字混過去")
    with st.form(form_key):
        st.radio(radio_label, options=list(options),
                 format_func=lambda _k: option_labels[_k],
                 key=widget_key, horizontal=True)
        _submitted = st.form_submit_button(submit_label, type="primary")
    if _submitted:
        # 唯一的寫入點：widget 當下值 → 已套用值。
        st.session_state[applied_key] = {
            "mode": st.session_state.get(widget_key, options[0]),
        }
    return bool(_submitted)
