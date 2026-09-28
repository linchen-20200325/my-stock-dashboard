"""shared/secret_md.py — L0：例外原文上 Markdown 畫面前的最後一步（SEC-3，2026-09-26）。

v2 五頁以外的舊頁（`app.py`、`src/ui/etf/**`、`src/ui/pages/**`、`src/ui/tabs/**`）把例外原文
直接塞進 `st.error` / `st.warning` / `st.caption` / `st.markdown`。實證（#709）：secrets.toml 壞掉時
例外會帶出整份 secrets 原文。本檔只是把 L0 `shared.secret_scrub.scrub_secrets` 包成兩個
Markdown 版本（另把散文版 `scrub_prose_secrets` 包成一個，見 `scrub_qa_text`），
規則一律在 `secret_scrub`（⛔ 本檔不加任何規則）。
**純函式，零 I/O、零 streamlit** —— 放 L0 是為了讓 `app.py`／L4／L5 都能引用，
又不必載入 `src.ui.render` 整包（`portfolio_manager` 要能在沒有 streamlit 的環境 import）。

- `scrub_md(x)`：洗完後把 `*` 全部跳脫（同 `station_cards` 的作法）—— 用在「例外原文」那一段。
  `\\*` 在 Markdown 裡顯示成 `*`，一般訊息看起來逐字不變。
- `scrub_md_mask(x)`：洗完後**只**跳脫遮罩 `***`（同 `page_today._md_scrub`）—— 用在整句本身
  含刻意 `**粗體**` 的訊息。
- `scrub_qa_text(x)`（SEC-r12／SEC-r11，2026-09-28 自 `src/ui/views/page_why.py` 下沉）：**問答散文**
  （使用者的提問、AI 的回答）上 Markdown 畫面／寫進對話紀錄用這一支 —— 洗法是**散文版**
  `scrub_prose_secrets`（⛔ 不是 `scrub_secrets`：錯誤字串的第 1 類截法會把引用錯誤訊息的提問與解法截掉）。
  v2 `page_why` 與 v1 `tab_ai_chat` 共用（v1 L5 ⛔ 不得 import v2 view 模組，故放 L0）。
  送給 L3（→ 模型）的純文字版直接用 `shared.secret_scrub.scrub_prose_secrets`（模型收到的是文字，不渲染 Markdown）。
⚠️ 要截斷（`[:300]` 之類）一律用 `scrub_md(x, limit)`，⛔ 不要在外面先截再洗 ——
  先截會把秘密截成半截，半截秘密可能對不上清洗規則。
"""
from __future__ import annotations

from shared.secret_scrub import MASK, scrub_prose_secrets, scrub_secrets


def scrub_md(text, limit: int | None = None) -> str:
    """`scrub_secrets` →（有 `limit` 才）截斷 → 跳脫全部 `*`（`None` → 空字串）。

    截斷夾在清洗與跳脫之間：先洗才不會把秘密截在規則外，後跳脫才不會截出落單的 `\\`。
    """
    out = scrub_secrets(text)
    if limit is not None:
        out = out[:limit]
    return out.replace("*", "\\*")


def scrub_md_mask(text) -> str:
    """`scrub_secrets` 後只跳脫遮罩 `***`，保留原句的 `**粗體**`（`None` → 空字串）。"""
    return scrub_secrets(text).replace(MASK, "\\*" * len(MASK))


def scrub_qa_text(text) -> str:
    """問答散文（提問／AI 回答）上 Markdown 畫面、寫進對話紀錄前的清洗（`None`／空 → 空字串）。

    SEC-r7（2026-09-27）起於 `page_why`；SEC-r12／SEC-r11（2026-09-28）下沉本檔、洗法改散文版：
    `scrub_prose_secrets` 沒命中任何規則 → **原字串逐字回傳**（回答常有 `**粗體**`／`***粗斜體***`，
    一個字都不動）；有命中 → 只跳脫遮罩 `***`（同 `scrub_md_mask` 的慣例：保留原句粗體）。
    寫進紀錄的就是洗過的字串 ⇒ rerun 重播的對話紀錄、下一輪隨 history 送出的也是洗過的。
    """
    _raw = str(text or "")
    _out = scrub_prose_secrets(_raw)
    return _raw if _out == _raw else _out.replace(MASK, "\\*" * len(MASK))
