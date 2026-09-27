"""shared/secret_md.py — L0：例外原文上 Markdown 畫面前的最後一步（SEC-3，2026-09-26）。

v2 五頁以外的舊頁（`app.py`、`src/ui/etf/**`、`src/ui/pages/**`、`src/ui/tabs/**`）把例外原文
直接塞進 `st.error` / `st.warning` / `st.caption` / `st.markdown`。實證（#709）：secrets.toml 壞掉時
例外會帶出整份 secrets 原文。本檔只是把 L0 `shared.secret_scrub.scrub_secrets` 包成兩個
Markdown 版本，規則一律在 `secret_scrub`（⛔ 本檔不加任何規則）。
**純函式，零 I/O、零 streamlit** —— 放 L0 是為了讓 `app.py`／L4／L5 都能引用，
又不必載入 `src.ui.render` 整包（`portfolio_manager` 要能在沒有 streamlit 的環境 import）。

- `scrub_md(x)`：洗完後把 `*` 全部跳脫（同 `station_cards` 的作法）—— 用在「例外原文」那一段。
  `\\*` 在 Markdown 裡顯示成 `*`，一般訊息看起來逐字不變。
- `scrub_md_mask(x)`：洗完後**只**跳脫遮罩 `***`（同 `page_today._md_scrub`）—— 用在整句本身
  含刻意 `**粗體**` 的訊息。
⚠️ 要截斷（`[:300]` 之類）一律用 `scrub_md(x, limit)`，⛔ 不要在外面先截再洗 ——
  先截會把秘密截成半截，半截秘密可能對不上清洗規則。
"""
from __future__ import annotations

from shared.secret_scrub import MASK, scrub_secrets


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
