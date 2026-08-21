"""L5 UI — 全域「🔗 我的組合」狀態列(P3a v19.207 順暢化)。

把「選 Sheet」從一個必經分頁(📁 組合管理)提升為**標題下常駐的全域狀態**(像登入身分一樣),
點開就地綁定 → 消滅「先繞組合管理才能分析」的心智模型。分頁結構**不動**(user 選「只加狀態列」)。

三態(§1 不混:綁定 ≠ 有資料):
  ⚪ 未綁定(未登入 / 未選 Sheet)→ 點開就地登入 + 挑 Sheet(重用 P1 的 render_holdings_binder)
  🟡 已綁定但空表            → 顯示現況 + 提示去 📁 組合管理 補持股 + 可換一本
  🟢 已綁定 N 本組合          → 顯示現況 + 可換一本

§8.2:L5 → L3 portfolio_binding_service(讀狀態)+ L5 → L5 portfolio_binder(綁定 UI);
直呼 L1 gsheet_portfolio 僅為把 `_gsp` 注入 binder(§8.2.A EX-PASSTHRU-1,同 💼 戰情室範式)。
§1:狀態列是全域 chrome,整個 render 包 try/except 誠實降級,不可因附帶失敗炸掉整頁。
"""
from __future__ import annotations

import streamlit as st

from src.services.portfolio_binding_service import (
    STATUS_BOUND,
    STATUS_BOUND_EMPTY,
    STATUS_UNBOUND,
)

# widget key 前綴,與 📁 組合管理(_mgmt_drive_)/ 💼 戰情室(_station_)物理隔離,不撞。
_BAR_KEY = "_pfbar_"


def render_portfolio_status_bar() -> None:
    """標題下、總經指南針之上,渲染一條常駐「🔗 我的組合」狀態列。

    §1:狀態列跑在**每頁最頂**(module-level,早於各 tab)。任何環節丟例外都會炸掉整頁 →
    **整個 render 包 try/except**(不只讀狀態,連 popover 內容 _render_bar_body 也要包),
    失敗誠實 log + 不畫,絕不擋整頁。
    """
    try:
        from src.services.portfolio_binding_service import get_binding_state
        _bs = get_binding_state()
        _label, _help = _label_for(_bs)
        # 用 popover(浮層,不推擠內容)。requirements 已 pin streamlit>=1.36(popover 自 1.31 起),
        # 故 popover 必在;hasattr 僅為極舊環境的防禦性退路。⚠️ popover 內可放 expander,但
        # **expander 內不可再放 expander** —— render_holdings_binder 自帶「貼網址」expander,
        # 故本檔外層一律用 popover、且**不得**自行再包 expander(否則與 binder 內的 expander 撞)。
        if hasattr(st, "popover"):
            with st.popover(_label, help=_help, use_container_width=False):
                _render_bar_body(_bs)
        else:  # 極舊 streamlit(理論上被版本 floor 擋掉):inline 展開,避免 expander 巢狀
            st.caption(_label)
            _render_bar_body(_bs)
    except Exception as _e:  # noqa: BLE001 — 全域 chrome,任何環節失敗誠實 log + 不擋整頁(§1)
        print(f"[portfolio status bar] {type(_e).__name__}: {_e}")


def _label_for(_bs) -> "tuple[str, str]":
    """三態 → (晶片文字, tooltip)。純函式,易測。"""
    if _bs.status == STATUS_BOUND:
        # count is None = 已綁但本數讀取失敗(降級)→ 誠實顯「數量未知」,**不印字面 None、不腦補**(§1)。
        _cnt = f" · {_bs.portfolio_count} 本" if _bs.portfolio_count is not None else "（數量未知）"
        return (f"🟢 我的組合：已綁定{_cnt}",
                f"Sheet：{_bs.sheet_id[:16]}…　點開可換一本")
    if _bs.status == STATUS_BOUND_EMPTY:
        return ("🟡 我的組合：已綁定,但還沒有組合資料",
                f"Sheet：{_bs.sheet_id[:16]}…")
    return ("⚪ 我的組合：未綁定", "點開登入 + 選一份 Google Sheet,之後各頁自動載入")


def _render_bar_body(_bs) -> None:
    """popover / expander 內容:未綁 → 就地綁定;已綁 → 現況 + 換一本。"""
    from src.ui.tabs.portfolio_binder import render_holdings_binder    # L5→L5
    from src.data.portfolio import gsheet_portfolio as _gsp            # EX-PASSTHRU-1(注入 binder)

    if _bs.status == STATUS_UNBOUND:
        render_holdings_binder(_gsp, key_prefix=_BAR_KEY)
        return

    # 已綁(空表或有資料)→ 顯示現況。⚠️ 不可用 st.expander 包 render_holdings_binder
    # (binder 內已自帶「貼網址」expander,expander 巢狀會炸);用 markdown 標題即可。
    st.caption(f"目前投組資料庫 Sheet：`{_bs.sheet_id}`"
               + (f"　（{_bs.portfolio_count} 本組合）"
                  if _bs.status == STATUS_BOUND and _bs.portfolio_count is not None else ""))
    if _bs.status == STATUS_BOUND_EMPTY:
        st.info("這本 Sheet 還沒有組合資料 —— 到 **📁 組合管理** 新增「投資組合 / 觀察清單」。")
    st.markdown("**🔄 換一本 Sheet**")
    render_holdings_binder(_gsp, key_prefix=_BAR_KEY)
