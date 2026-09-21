"""戰情室 v2 渲染層（契約 E）—— **`src/ui_v2/` 裡唯一 import streamlit 的檔**。

職責只有三件事，一件都不多：
  ① 把 `markup.page_css(mode)` 注入**一次**；
  ② 依**層序**把 `markup.grid_html()` / `markup.layer_html()` 吐到 `st.markdown`；
  ③ 主 CTA 用**真 widget**（`st.button`），⛔ 不得畫成一段長得像按鈕的 HTML。

⛔ **本檔不取數。** 零 `src.data.*` import、零 `requests`、零 `@st.cache_data`。
   資料一律由 caller 以 `view_model` 參數傳進來。三個理由，任一條都足以拘束：
   · `CLAUDE.md §8.2` 硬規則第 4 條「L5 UI / L6 App 不得直呼 L1 Data fetcher」；
   · v3（§-1.5.D）§01 三層圖「**嚴禁在 UI 層私自存放或抓取原始資料**」；
   · 測試才不會打網路（`tests/ui_v2/test_render.py` 用真的 `AppTest` 冷啟動整頁）。

🔴 **一個網格 ＝ 一次 `st.markdown`。**
   Streamlit 每次 `st.markdown` 在瀏覽器端各自是一個獨立的 DOM 節點 ——
   `<div>` 開在 A 呼叫、想收在 B 呼叫，**不會**包住 B 的產出，
   結果是版面靜默走樣：不報錯、不變紅、沒有人查得到。
   故一個容器連同它的內容，必須在**同一次**呼叫裡整段吐完。
   repo 先例：`src/ui/render/station_cards.py` docstring 逐字
   「整面牆是一次 `st.markdown` 的純 HTML」。

🔴 **兩個網格，兩種處理**（⛔ 不要混用，`page_today` 已用 🔴 標出）：
   · 有登記**層級網格**的層（`page_today.LAYER_GRID_COLS`，實測只有第二層）
     → 該層的所有 block 包進**一次** `layer_html()`，這樣三張卡才會並排
     （客戶 2026-09-16「第二層＝**3 張並排卡**」）；
   · 沒登記的層 → 逐 block 各自一次 `grid_html()`，全寬堆疊。
   ⛔ 不得為沒登記的層「預設 1 欄」硬包一個層級網格：`layer_html()` 會炸，
   而那個 raise 是刻意的（§1：沒有來源就不要給一個猜的答案）。

⚠️ **本輪不接真實資料**（總管拍板：規格 → 畫面）。`unwired_view_model()` 產的是
   **全部 `state="unwired"`（徽章 #5「這項還沒做」）** 的頁面 —— 那是**事實**，
   ⛔ 不是示範假資料，詳見該函式的 docstring。
"""
from __future__ import annotations

from typing import Mapping, Sequence

import streamlit as st

from src.ui_v2 import markup, page_today

#: block → 它所在的層。⛔ 不手抄，一律自 `page_today.LAYERS` 推。
_LAYER_OF_BLOCK: Mapping[str, int] = {
    block: layer["layer"] for layer in page_today.LAYERS for block in layer["blocks"]
}

#: 由上而下的層序。
_LAYER_ORDER: tuple[int, ...] = tuple(layer["layer"] for layer in page_today.LAYERS)

#: 掛主 CTA 的層（`UI_PAGE_TODAY` ①：全站唯一一顆，掛第三層）。⛔ 不寫死 `today.actions`。
_MAIN_CTA_LAYERS: frozenset[int] = frozenset(
    layer["layer"] for layer in page_today.LAYERS if layer["has_main_cta"]
)

#: 主 CTA 的 widget key —— 固定值，讓同一顆鈕在 rerun 之間保持同一個身分。
_MAIN_CTA_KEY = "ui_v2_today_main_cta"

#: 本輪的未接線態。⛔ 不是「預設值」，是**這一頁目前的真實狀態**。
_UNWIRED_STATE = "unwired"


def _group_by_layer(
    entries: Sequence[Mapping[str, object]],
) -> list[tuple[int, list[Mapping[str, object]]]]:
    """把扁平的 `blocks` 依層序分組（層內維持 view model 給的順序）。

    ⛔ **不得靜默丟掉任何一筆** —— 不在任何層裡的 block 一律炸（§1 Fail Loud）：
    悄悄少畫一張卡，畫面上只是「少一張」，不會有任何錯誤訊息。
    """
    buckets: dict[int, list[Mapping[str, object]]] = {L: [] for L in _LAYER_ORDER}
    for entry in entries:
        block = entry["block"]
        if block not in _LAYER_OF_BLOCK:
            raise KeyError(
                f"view model 帶了一個不屬於任何層的 block：{block!r}"
                f"（版面 SSOT 是 page_today.LAYERS）—— ⛔ 不得靜默略過"
            )
        buckets[_LAYER_OF_BLOCK[str(block)]].append(entry)
    return [(L, buckets[L]) for L in _LAYER_ORDER if buckets[L]]


def _render_main_cta(cta: Mapping[str, object]) -> None:
    """主 CTA —— **真 widget**（`UI_COMPONENTS` §3「主 CTA（全站唯一一顆）」）。

    ⛔ 不畫成 HTML 假鈕：假鈕按下去不會 rerun、鍵盤 tab 不到、螢幕閱讀器讀不出
    「這是按鈕」—— 而畫面上看起來一模一樣。
    標籤**逐字**取 `page_today.MAIN_CTA["label"]`，⛔ 不在這裡重打一份字串。
    停用態依 `page_today.main_cta_state()`：契約漂移時**重按不會好**，
    所以鈕停用、說明字照出（⛔ 不得給「可以重跑」這種錯指引）。
    """
    st.button(
        str(page_today.MAIN_CTA["label"]),
        key=_MAIN_CTA_KEY,
        type="primary",
        disabled=not cta["enabled"],
    )
    note = cta.get("note")
    if note:
        st.markdown(str(note))


def render_page_today(view_model: Mapping[str, object]) -> None:
    """把「🚦 今天」頁的 view model 畫出來。

    `view_model` 形狀（契約在 `tests/ui_v2/test_render.py`）::

        {"mode": "dark",
         "blocks": [{"block": <block key>, "cards": [{state, title, value,
                                                      level, badge_n, facts}, …]}, …],
         "main_cta": {"enabled": bool, "note": str | None}}
    """
    mode = str(view_model["mode"])
    # ① 樣式表只注入一次 —— 注入兩次不會壞掉，但後面那份會蓋前面那份，
    #    改了樣式卻沒反應時沒有人查得到原因。
    st.markdown(f"<style>{markup.page_css(mode)}</style>", unsafe_allow_html=True)

    cta = view_model["main_cta"]
    cta_drawn = False
    blocks = view_model["blocks"]
    assert isinstance(blocks, Sequence), "view_model['blocks'] 必須是序列"

    for layer, entries in _group_by_layer(blocks):
        grids = [
            markup.grid_html(
                block=str(entry["block"]),
                cards=[markup.card_html(block=str(entry["block"]), **dict(card))
                       for card in entry["cards"]],
            )
            for entry in entries
        ]
        if layer in page_today.LAYER_GRID_COLS:
            # 有層級網格 → 整層包成一塊，⛔ 不可拆成多次呼叫（見檔頭 🔴）。
            st.markdown(
                markup.layer_html(layer=layer, block_htmls=grids),
                unsafe_allow_html=True,
            )
        else:
            for grid in grids:
                st.markdown(grid, unsafe_allow_html=True)

        if layer in _MAIN_CTA_LAYERS:
            _render_main_cta(cta)
            cta_drawn = True

    if not cta_drawn:
        # 掛 CTA 的那一層不在這次的 view model 裡 —— 鈕仍然要有，且**只有一顆**。
        _render_main_cta(cta)


def unwired_view_model(*, mode: str = "dark") -> Mapping[str, object]:
    """**尚未接線**的 view model —— ⛔ 不是示範資料、⛔ 不是假數字。

    每一張卡都是 `state="unwired"` ⇒ 徽章 #5「這項還沒做」，而大字區依
    `page_today.card_value_text` 一律**留白** ⇒ **畫面上不會出現任何數字**。
    這就是本輪的事實：渲染層先落地，取數在下一輪。
    ⛔ 不得為了讓畫面好看而填一組示意值（`CLAUDE.md §1`：寧可留白，不可造假；
    「回傳 dummy / example / 範例資料」是明文禁止的手段之一）。

    ⚠️ `title` 直接用 block key（如 `today.verdict`）：規格層**沒有**「每個 block
    叫什麼」的 SSOT，⛔ 不在這裡發明一組中文標題 —— 那會變成一組沒有出處的規格值，
    而且看起來就像客戶審過的。要補請先補契約層。
    """
    badge_n = page_today.resolve_badge(state=_UNWIRED_STATE)
    return {
        "mode": mode,
        "blocks": [
            {
                "block": block,
                "cards": [{
                    "state": _UNWIRED_STATE,
                    "title": block,
                    "value": None,
                    "level": None,
                    "badge_n": badge_n,
                    "facts": (),
                }],
            }
            for block in page_today.BLOCK_COLS
        ],
        "main_cta": dict(page_today.main_cta_state()),
    }


__all__ = ["render_page_today", "unwired_view_model"]
