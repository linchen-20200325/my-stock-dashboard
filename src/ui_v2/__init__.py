"""`src/ui_v2` —— 戰情室 v2 UI（分支 `ui-v2`）。

~~三個模組，由低到高：~~
~~  `tokens.py`      設計 token（顏色／字級／間距／圓角）—— SSOT `docs/v2/spec/UI_TOKENS.md`~~
~~  `components.py`  元件規格（卡片四階／徽章 10 種／按鈕五類／斷點）—— SSOT `UI_COMPONENTS.md`~~
~~  `page_today.py`  「🚦 今天」頁版面與狀態契約 —— SSOT `UI_PAGE_TODAY.md`~~

~~⛔ **全層不 import streamlit**：這三個模組是框架無關的純資料結構＋純函式，~~
~~   要能在沒有 Streamlit runtime 的沙箱裡單測。渲染層（`st.*`）留到下一輪，~~
~~   屆時由 UI 層引用本層，⛔ 不得反向依賴。~~

⚠️ **2026-09-21 事實更正，不是漏刪；決策者：AI 總管。**
上面三句在寫下的當天都是對的，現在**三句全部過期**：模組已是 **6 個**（不是三個）、
`render.py` 就 import streamlit（不是「全層不 import」）、渲染層**這一輪就落地了**
（不是「留到下一輪」）。舊句依本 repo 慣例保留不刪 —— 它記錄的是「本層一開始是純資料層」
這個**事實**，而那正是下面「純層 / 渲染層 / 進入點」三分的由來。

**現行（六個模組，由低到高）**
────────────────────────────
**純層（⛔ 不 import streamlit，能在沒有 Streamlit runtime 的沙箱裡單測）**
  `tokens.py`      設計 token（顏色／間距）—— SSOT `docs/v2/spec/UI_TOKENS.md`
  `components.py`  元件規格（卡片四階／徽章 10 種／按鈕五類／大字區／斷點）—— SSOT `UI_COMPONENTS.md`
  `page_today.py`  「🚦 今天」頁版面與狀態契約 —— SSOT `UI_PAGE_TODAY.md`
  `markup.py`      純字串（CSS 文字 ＋ HTML 文字）—— 把上面三層組成標記，⛔ 不碰 `st.*`

  `page_find.py`   「🔍 找標的」頁的版面契約（只登記真的畫成卡的 4 個 block）—— SSOT `UI_PAGE_FIND.md`
  `blocks.py`      block 登記處：block → 所屬頁 → 該頁 `tier_for_block`（`markup.card_html` 經此查階）
  📌 2026-09-25 新增上兩行（客戶裁示 1）；上面「六個模組」的計數自本日起為八個，舊字樣照留。

**渲染層（`src/ui_v2/` 裡唯一 import streamlit 的檔）**
  `render.py`      把 `markup` 的字串吐進 `st.markdown`；主 CTA 用真 widget

**進入點**
  `app_today.py`   `streamlit run src/ui_v2/app_today.py`；⛔ 零邏輯

⛔ **`render` ⛔ 不得加進 `__all__`** —— `__all__` 是 `from src.ui_v2 import *` 會拉進來的
   東西；把 `render` 放進去，等於讓任何一個 `import *` **連帶 import streamlit**，
   純層「沒有 Streamlit 也能跑」的性質就在**別人的**測試裡靜默破功
   （壞的不是這裡，是下一個 `import *` 的人，而且症狀看起來與本層無關）。
   同理 `app_today` 也不列 —— 它是進入點，`import` 它會**直接把整頁畫出來**。
   要用 `render` 請具名 `from src.ui_v2 import render`，⛔ 不要靠 `*`。

⛔ **方向仍然是單向的**：`render` / `app_today` 引用純層，⛔ 純層不得反向依賴它們。

⛔ **不重新宣告狀態常數**：七態 SSOT 是既有 L0 `shared/ui_state.py`；
   本套件只存**常數名字串**（`"UI_LIVE"` …），⛔ 不在此長出第二份（CLAUDE.md §2.1）。
"""

__all__ = ["tokens", "components", "page_today", "page_find", "blocks", "markup"]
