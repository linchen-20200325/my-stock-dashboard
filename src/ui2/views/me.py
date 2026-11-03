"""me 頁 view：只渲染 PageVM（帳戶／登入切換 skeleton；FAKE）。

⛔ 真 Google OAuth、⛔ 讀寫 Sheet、⛔ 改 portfolio／watchlist／strategy、⛔ 寫 secrets、
⛔ import oauth_state／gsheet_portfolio／任何 src.data。帳戶狀態由 VM（fake canonical）提供。
"""
from __future__ import annotations

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import account_actions_html, first_screen_html
from src.ui2.views._page import _md, render_cards, render_sections, render_title


def render(vm: PageVM) -> None:
    acc = vm.context.account
    render_title(vm, account=acc.account_state if acc else "")
    _md(first_screen_html(vm.context.first_screen))      # ① 連線狀態 ② 連線異常 ③ 下一步 ④ 主 CTA
    if acc is not None:
        _md(account_actions_html(acc))
    render_cards(vm)
    render_sections(vm)
