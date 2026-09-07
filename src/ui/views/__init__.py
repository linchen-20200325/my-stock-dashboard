"""src/ui/views/ — 五頁戰情室 IA v2 的 View 層（L5 UI）。

本套件是 IA v2（`docs/wireframes/stock_ia_v1.html`）五頁的新家：
`page_today` / `page_find` / `page_inspect` / `page_hold` / `page_why`
（本批只落地第 1 頁）。

═══ 為什麼 `__init__.py` 是空的（刻意，不是漏寫）═══════════════════════
**不在這裡 re-export 任何 view**。理由兩條：

1. `page_*.py` 一律 `import streamlit`。若本檔 re-export，任何人只要寫
   `from src.ui import views` 就會把 streamlit（以及該頁 lazy import 的
   整條 L3/L2 依賴鏈）拉進來 —— 包含只是想讀套件 docstring 的測試。
2. 五頁是**逐批落地**的。barrel 一旦寫上五個名字，就會有四個 ImportError；
   寫上一個名字，下一批又得回頭改這個檔（等於每批都動一次共用檔，
   與 CLAUDE.md §-1.5 第一條 2 的 File Boundary 隔離相衝）。

呼叫端請直接寫 `from src.ui.views.page_today import render_page_today`。

═══ 分層（CLAUDE.md §8.2）═════════════════════════════════════════════
本套件是 **L5 UI Tabs**。`tests/test_c3_layering_guard.py` 的 `_MODULE_LAYERS`
兜底規則 `("src.ui", L5)` 已涵蓋 `src.ui.views.*` 的**被 import 側**；
~~但該檔的 `_PATH_LAYERS` **沒有** `src/ui/views/` 這一列，故本套件檔案的
**主動 import 側目前不受該守衛檢查**。這是已知缺口，**不是**「已經守住了」——
補那一列要動既有測試檔，不在本批的檔案邊界內，已在交付回報中登記。~~

⚠️ **2026-09-07 事實更正（FE-7），不是漏刪；決策者:AI 總管。**
上面那段的前提**已不成立**：`tests/test_c3_layering_guard.py` 的 `_PATH_LAYERS`
**已經有** `("src/ui/views/", L5)` 這一列（實測命中，量測日 2026-09-07），
故本套件檔案的**主動 import 側現在受該守衛檢查**，該缺口已補上。
⚠️ 只有「那一列在不在」這個**事實**被更正 —— 該守衛本身的其他已知限制
（例如它是 AST 靜態掃描、看不到執行期動態 import）**一條都沒有變**。
"""
