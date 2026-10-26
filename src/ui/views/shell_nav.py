"""src/ui/views/shell_nav.py — 新版戰情室「導覽殼」的主畫面部分（L5 UI；D2，DEC-089 G1＝C／DEC-090）。

單一職責：被選到的頁**上方**的「📍 位置列」、🚦 今天的一行說明，以及兩個佔位頁（⚡ 行動、🩺 資料中心本體）。

═══ 邊界（先讀）═══════════════════════════════════════════════════════
- ❌ **不取數、不讀任何資料、不顯示任何數字或燈號。** 佔位頁只是文字（客戶 DEC-090 P-1／P-2 核准的字面）。
- ❌ **不手抄頁名 / 方向名 / 文案。** 全部來自 L0 `shared/ia_nav`（位置列、說明句、佔位頁文案模板）。
- ❌ **不使用紅色錯誤框。** 「⬜ 尚未建置」是灰色說明（`st.caption`），不是故障（§-1.5.D §02：未建 ≠ 系統真出錯）。
- ✅ 導覽控制項（兩層 radio）在 `app.py` 側欄，不在本檔。
"""
from __future__ import annotations

import streamlit as st

from shared import ia_nav


def render_position_bar(page: str) -> None:
    """主畫面最上方「📍 位置：〈方向〉 › 〈頁〉」（DEC-090 ②）。不加數字或結論。"""
    st.caption(ia_nav.position_text(page))


def render_today_notice() -> None:
    """🚦 今天頁頂一行說明（DEC-090 ⑤）。"""
    st.caption(ia_nav.today_notice())


def render_placeholder(page: str) -> None:
    """佔位頁（⚡ 行動、🩺 資料中心本體）。字面逐字依線框 §4；灰色，不用紅色，不放數字／燈號／空表格。"""
    _c = ia_nav.placeholder_copy(page)
    with st.container(border=True):
        st.markdown(f"**{_c['title']}**　{ia_nav.UNBUILT_MARK} 尚未建置")
        st.caption(f"現在怎樣：{_c['now']}")
        st.caption(f"為什麼：{_c['why']}")
        for _i, _line in enumerate(_c["where"]):
            st.caption(f"去哪：{_line}" if _i == 0 else f"　　　{_line}")


def render_shell(page: str) -> None:
    """位置列 ＋（🚦 今天）說明句 ＋（佔位頁）本體。已建的頁，其內容由呼叫端另行渲染（殼不碰頁內部）。"""
    render_position_bar(page)
    if page == ia_nav.PAGE_TODAY:
        render_today_notice()
    if not ia_nav.is_built(page):
        render_placeholder(page)
