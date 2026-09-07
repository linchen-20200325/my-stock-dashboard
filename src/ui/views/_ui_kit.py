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

⚠️ **2026-09-07（紅隊實測後修）：那道拒收改由 public 的
`assert_signal_text_clean()` 供給，呼叫端請在「建構期」先驗一次。**
只留在 `render_card()` 裡的話，一個含 `🔴` 的 SSOT 標籤會讓
`page_today` 畫到第 27 個 markdown **之後**才拋 `ValueError` ——
上半頁已經渲染、下半頁全部消失，而畫面上一句解釋都沒有（**半截死頁**）。
`render_card()` 那一道**沒有拿掉**，它現在是最後一道防線（同一支函式，
不是第二把尺）。

═══ 鐵律 4：空狀態引導三要素 ═══════════════════════════════════════════
資料型別是 `tab_today.Note(now, why, where)`（三個都不得為空、都不得自帶
狀態 glyph，`__post_init__` 會 raise）。本檔**只包一層渲染** `render_note()`，
**刻意不另做 `empty_state(now, why, where)`** —— 再開一支收三個 str 的入口
等於旁邊多一條繞過 `Note` 驗證的路。

⚠️ **2026-09-07（紅隊實測後修）：`render_card()` 只要卡上有 `Note` 就畫，
不再只在非 `live` 時畫。** `Card.__post_init__` 擋的是「非 live 沒 Note」與
「非 live 帶 value」，**沒有**擋「live 帶 Note」；於是一張
`state=live` / `value=''` / 帶 `Note` 的卡會被畫成標著「🟢 運作中」的
**空白框**，而那段 Note（往往正是「另一半算不出來」的原因）被**靜默丟棄**。
靜默丟棄上游明明附上的說明，就是 §1 禁止的「掩蓋問題」。

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
from typing import Any, Callable, Iterator, Sequence

import streamlit as st

from shared.macro_buckets import LEVEL_EMOJI
from shared.ui_state import UI_FAILED, UI_STATE_META, is_alarming, state_meta
# L5 → L5 同層 import（C3 分層守衛合規）。資料結構與版面上限的唯一來源。
from src.ui.tabs.tab_today import MAX_COLS, Card, Note, scrub_state_glyphs

__all__ = [
    "MAX_COLS", "Card", "Note",
    "is_alarming", "state_meta",
    "banned_signal_glyphs", "assert_signal_text_clean",
    "grid", "render_note", "render_card", "render_card_isolated",
    "render_cards", "section_header", "single_submit_form",
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

    ⚠️ **驗證與 yield 刻意分成兩層**（實測抓到的：整支寫成 generator 時，
    `grid(x, cols=0)` **不會當場炸** —— 例外要等到第一次 `next()` 才丟出來，
    而呼叫端很可能在那之前就已經照著錯的欄數排好版了）。
    參數檢查跑在**呼叫的當下**，逐列 yield 留給內層的 `_rows()`。
    """
    if isinstance(cols, bool) or not isinstance(cols, int) or cols < 1:
        raise ValueError(f"grid(cols=) 必須是 >=1 的整數，收到 {cols!r}")
    _n = min(cols, MAX_COLS)
    if cols > MAX_COLS:
        # §1 不靜默：夾住是對的，但**不能讓呼叫端以為它拿到了 7 欄**。
        print(f"[views/_ui_kit.grid] ⚠️ 要求 {cols} 欄，超過全站上限 "
              f"MAX_COLS={MAX_COLS} → 已夾到 {_n} 欄並換行排列。"
              "欄數上限是視覺規格，不是呼叫端可以覆寫的東西。")

    def _rows() -> Iterator[tuple[Sequence[Any], list]]:
        for _i in range(0, len(items), _n):
            _chunk = items[_i:_i + _n]
            yield _chunk, st.columns(len(_chunk))

    return _rows()


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
def banned_signal_glyphs(text: str) -> list[str]:
    """`text` 裡出現的**禁用符號**（狀態 glyph ∪ 燈號 emoji），排序後回傳。

    空 list = 乾淨。字面集合是 L0 兩個 SSOT 的聯集，本檔不新增任何符號。
    """
    return sorted(_g for _g in _BANNED_SIGNAL_GLYPHS if _g in str(text))


def assert_signal_text_clean(owner: str, signal_text: str) -> None:
    """訊號頻道**只准出中文標籤** —— 帶了狀態 glyph／燈號 emoji 就地 raise。

    Args:
        owner: 出問題的東西是誰（卡的 key、或建構中的 Tile）。只用在錯誤訊息。
        signal_text: 要檢查的訊號文字。

    Raises:
        ValueError: `signal_text` 含 `_BANNED_SIGNAL_GLYPHS` 裡的任一符號。

    ⚠️ **為什麼 2026-09-07 把它從 `render_card()` 裡抽成 public**（紅隊實測，
    不是理論）：這道檢查原本只長在 `render_card()` 內，也就是**畫到那一張卡
    的當下**才炸。只要任何一個 SSOT 標籤含 `🔴`，`page_today` 會在畫出
    第 27 個 markdown **之後**拋 `ValueError` → **半截死頁**：上半頁已經
    渲染、下半頁全部消失，而畫面上沒有任何一句話說發生了什麼事。
    §1 要的是「紅態看得見」，**不是「畫一半才炸」**。

    抽出來之後，呼叫端（`page_today.Tile.__post_init__`）可以在**建構期**、
    也就是**任何一個 `st.*` 被呼叫之前**就驗完整批 —— 要嘛整頁是對的，
    要嘛在還沒畫任何東西時就當場說明。`render_card()` 仍保留同一道檢查
    當最後一道防線；那**不是第二把尺** —— 兩邊呼叫的是同一支函式。
    """
    _bad = banned_signal_glyphs(signal_text)
    if _bad:
        raise ValueError(
            f"{owner} 的 signal_text 含符號 {_bad} —— "
            "訊號頻道**只出中文標籤**。狀態頻道的『取得失敗』與燈號的『紅』"
            "在 SSOT 裡用的是同一顆 🔴，同一張卡出兩個等於沒有資訊。"
            "（user 2026-08-26 對 `macro_v2_cards.STATE_META` 的同一裁示。）")


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

            ⚠️ **`degraded`（門檻已失準）到底要不要給燈？** 判準只有一條：
            **這個頻道載的是「觀測」還是「判決」**。
            （2026-09-07 獨立稽核裁定；寫在這裡是因為缺了它 ——
            這份 docstring 修前只寫「空字串 = 沒有燈號頻道」——
            兩頁對同一個狀態做出了相反的處理，這就是那次分歧的根因。）

            · 載 **band / level 觀測**（「這個值落在哪一段」：綠 / 黃 / 紅、
              多頭 / 震盪 / 空頭）→ **照出**。狀態頻道那顆「門檻已失準」的
              chip 本身就是免責聲明，`Note` 的 `where` 再講一次該怎麼讀；
              一律留白反而會把使用者**本來看得到的資訊藏起來**。
            · 載 **判決語**（pass / fail 的結論，如「門檻內」「月度尾部可控」）
              → **留白**。對一個**已知失準**的數字下「過關」判決，就是
              §1「錯誤的數字比沒有數字更危險」講的失準值冒充過關。

            依據是 L0 `shared/station_specs.py:139`
            （「`discriminative=False` → 燈會亮、**也有等級**，
            只是門檻已失去判別力」）與同檔 `:527`
            （「degraded（**有值、燈照亮**，只是別照門檻讀）」）——
            **degraded 不是「沒有東西可給」**，所以「一律留白」不是安全解。

            ⚠️ 灰態（`idle` / `empty` / `unwired`）與紅態 (`failed`) 則**一律
            留白**：那是「沒評估」，不是「評估過沒事」（**未評估 ≠ 綠**）。
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
    # 最後一道防線。呼叫端應已在**建構期**驗過（見 `assert_signal_text_clean`
    # 的 docstring：只靠這裡會變成「畫一半才炸」的半截死頁）。
    assert_signal_text_clean(f"卡 {card.key!r}", signal_text)
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
    # 【6】2026-09-07 修：**只要有 Note 就畫，不再只在非 live 時畫。**
    # 修前是 `if card.state != UI_LIVE and card.note is not None:` ——
    # `Card.__post_init__` 擋的是「非 live 沒 Note」與「非 live 帶 value」，
    # **沒有**擋「live 帶 Note」。於是一張 `state=live` / `value=''` / 帶 Note
    # 的卡，會被畫成一個標著「🟢 運作中」的**空白框**，而那段 Note 裡的
    # 說明（往往正是「另一半算不出來」的原因）**被靜默丟棄**。
    # 靜默丟棄上游明明附上的說明 = §1 禁止的「掩蓋問題」。
    if card.note is not None:
        render_note(card.note)


def render_card_isolated(card: Card, *,
                         signal_text: str = "",
                         signal_color: str = "",
                         facts: Sequence[tuple[str, str]] = (),
                         owner: str,
                         error_why: Callable[[str], str],
                         where: str) -> None:
    """畫一張卡，**並且不讓它把整頁畫到一半就死掉**。

    渲染期若仍有東西炸（例如 L0 給了一個未知狀態名 → `state_meta()` fail loud），
    把它**就地轉成一張紅卡 ＋ `repr(e)`**，其餘的卡照畫。

    ⚠️ **不是 `except: pass`**：例外被轉成一個看得見的紅態並附原文，
    log 也留一份。§1 要的是「紅態看得見」——
    半截死頁（上半頁在、下半頁全沒了、畫面上沒有任何一句解釋）
    比一張紅卡危險得多，因為使用者根本不知道有東西不見了。

    Args:
        card / signal_text / signal_color / facts: 原樣轉給 `render_card()`。
        owner: log 前綴（呼叫端的頁名，如 `"views/page_today"`）。
            **只影響 stderr/stdout 的那一行**，不影響畫面。
        error_why: `repr(e)` → `Note.why` 的那一句話。由呼叫端提供，
            因為「出事的是哪一層」是**頁面自己**才知道的事
            （頁 1 的【8b】就是拿共用文案去包別的層，對使用者謊報出事的層）。
            洗 glyph 一律在該函式內走 `tab_today.scrub_state_glyphs()` SSOT。
        where: 這張補救卡的「去哪補」。各頁不同（頁 1 指回它的唯讀說明，
            頁 2 指回維護者），故由呼叫端給。

    ⚠️ **這是搬家不是重寫**（2026-09-07 FE-9）：`page_today` 與 `page_find`
    原本**各有一份逐行同構的 `_render_one()`** —— 兩把尺遲早會漂移
    （一邊修了「`except ... as _e` 的 `_e` 會被 `del`」這個坑、另一邊沒修，
    就是最典型的漂移）。本函式的內文與那兩份**逐行相同**，
    差異只有上面三個參數化掉的東西（log 前綴 / 出處文案 / 去哪補）。
    """
    try:
        render_card(card, signal_text=signal_text, signal_color=signal_color,
                    facts=tuple(facts))
        return
    except Exception as _e:  # noqa: BLE001 — 轉成看得見的紅卡，不吞
        # ⚠️ `except ... as _e` 的 `_e` 在區塊結束時會被 `del` 掉，
        #    所以在區塊內就把字串取出來（不然下面會是 NameError）。
        _err = repr(_e)
        print(f"[{owner}] 卡 {card.key!r} 渲染失敗 → 轉紅卡：{_err}")
    # 卡的 label 本身不受 `Note` 那道 glyph 驗證管，先洗過再放進 `Note.now`，
    # 否則這張補救卡自己會再炸一次（§1：紅態要看得見，不是換一種炸法）。
    _label = scrub_state_glyphs(card.label)[0] or card.key
    render_card(Card(
        key=f"{card.key}.render_failed", label=_label, state=UI_FAILED,
        note=Note(now=f"{_label}　**這一格畫不出來**",
                  why=error_why(_err),
                  where=where)))


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
