"""src/ui/views/shell_nav4.py — 新版戰情室「固定四頁主導覽」元件（L5 UI；NAV-1，DEC-092 Q6／DEC-097）。

單一職責：把 L0 `shared/ia_nav4` 的四頁渲染成**原生 Streamlit 單選元件**，並讓它們共用**同一個頁狀態**。

═══ 兩個導覽元件、一個頁狀態（SSOT）═══════════════════════════════════
- **桌機**（wireframe：左側欄四項）：`st.sidebar` 內的 `st.radio`（垂直）。由 `app.py` 在它的 `with st.sidebar:` 區塊內呼叫
  `render_sidebar_nav()`。
- **手機**（DEC-097：底部固定四按鈕）：`st.container(key="nav4_bottom")` 內的橫排 `st.radio` ＋ CSS
  （`.st-key-nav4_bottom{position:fixed;bottom:0…}`，只在窄螢幕固定到底部；桌機隱藏）。
- 兩者的 `on_change` 回呼**都只寫** `ia_nav4.NAV4_PAGE_KEY` 這一格；每輪渲染前再把兩個 widget 的顯示值預填成該格的值。
  ⇒ routing／page state 與裝置無關，只有一份（客戶 DEC-097 需求 (3)）。

═══ 失效降級必須良性（CSS 是加分，不是依賴）══════════════════════════
兩個元件本身就是可用的原生 radio。CSS 全部失效（Streamlit 改了 `st-key-` class、瀏覽器不支援 `:has`…）時：
底部那一組退化成**主內容流中一個普通的橫排 radio**，仍可點、仍寫同一格 SSOT；畫面不會因此消失或不可用。
（底部固定列的 `position:fixed` 只在 `@media (max-width: 768px)` 內；`display:none`（桌機隱藏）只在 `@media (min-width: 769px)` 內
  —— 沒有「預設隱藏、靠 CSS 才顯示」的規則，故 CSS 失效只會多出一組導覽，不會少一組。）

═══ 邊界（先讀）═══════════════════════════════════════════════════════
- ❌ **不取數、不讀任何資料、不顯示任何數字或燈號。** 只有導覽字串。
- ❌ **不手抄頁名**：四頁名／葉名全部來自 L0 `shared/ia_nav4`（葉名再轉 `ia_nav.page_label`）。
- ❌ **不使用紅色錯誤框**（導覽沒有「真出錯」的狀態；§-1.5.D §02）。壞掉的 state 一律 raise（由 `app.py` 的隔離器紅態顯示）。
- ❌ **不渲染任何指向舊 UI／legacy 的字或連結**（DEC-097：legacy 入口不得出現在一般使用者主導覽）。
"""
from __future__ import annotations

import streamlit as st

from shared import ia_nav4
from src.ui_v2.tokens import get_token

# ══════════════════════════════════════════════════════════════════
# CSS（只在新版模式注入；legacy 模式不 import 本模組，故舊畫面零影響）
# ══════════════════════════════════════════════════════════════════
#: 手機底部固定列的斷點。⚠️ 768px 是依 Streamlit 側欄在窄螢幕改為「抽屜」的斷點估的（INFERENCE，未實機驗證）；
#: 桌機＝左側欄、其下＝底部固定列，兩者在同一個寬度只會有一個是「主要」導覽（另一個即使同時出現也無害：同 SSOT）。
_MOBILE_MAX_PX = 768
_DESKTOP_MIN_PX = _MOBILE_MAX_PX + 1

_CSS_TEMPLATE = """<style>
/* NAV-1：手機底部固定四按鈕（DEC-097）。key=@@KEY@@ ⇒ class .st-key-@@KEY@@（Streamlit 非公開保證；失效時退化為主內容流中的橫排 radio） */
@media (max-width: @@MOBILE@@px){
  .st-key-@@KEY@@{position:fixed;left:0;right:0;bottom:0;z-index:999;
    background:@@BG@@;border-top:1px solid @@RULE@@;
    padding:6px 6px calc(6px + env(safe-area-inset-bottom, 0px));box-sizing:border-box;}
  .st-key-@@KEY@@ [role="radiogroup"]{display:flex;flex-direction:row;flex-wrap:nowrap;width:100%;gap:0;}
  .st-key-@@KEY@@ label[data-baseweb="radio"]{flex:1 1 0;min-width:0;margin:0;padding:8px 2px;
    justify-content:center;text-align:center;white-space:nowrap;color:@@INK2@@;border-radius:8px;}
  .st-key-@@KEY@@ label[data-baseweb="radio"] > div:first-child{display:none;}
  .st-key-@@KEY@@ label[data-baseweb="radio"]:has(input:checked){color:@@INK@@;
    box-shadow:inset 0 2px 0 @@FOCUS@@;background:@@PANEL@@;}
  /* 主內容留出底部固定列的高度＋安全區，避免遮住頁尾與免責聲明 */
  [data-testid="stMainBlockContainer"]{padding-bottom:calc(5.5rem + env(safe-area-inset-bottom, 0px)) !important;}
}
/* 桌機：左側欄為主導覽，底部固定列隱藏（桌機寬度沒有預設隱藏規則 ⇒ CSS 失效時導覽不會消失） */
@media (min-width: @@DESKTOP@@px){
  .st-key-@@KEY@@{display:none;}
}
/* 列印：導覽不印 */
@media print{
  .st-key-@@KEY@@{display:none !important;}
}
</style>"""


def build_css() -> str:
    """組出導覽 CSS。顏色一律走 `src.ui_v2.tokens`（深色為實際運行模式；token 缺值會 fail loud，不回退近似色）。"""
    _t = {
        "@@KEY@@": ia_nav4.NAV4_BOTTOM_CONTAINER_KEY,
        "@@MOBILE@@": str(_MOBILE_MAX_PX),
        "@@DESKTOP@@": str(_DESKTOP_MIN_PX),
        "@@BG@@": get_token("--paper", mode="dark"),
        "@@RULE@@": get_token("--rule", mode="dark"),
        "@@INK@@": get_token("--ink", mode="dark"),
        "@@INK2@@": get_token("--ink-2", mode="dark"),
        "@@FOCUS@@": get_token("--focus", mode="dark"),
        "@@PANEL@@": get_token("--panel", mode="dark"),
    }
    _s = _CSS_TEMPLATE
    for _k, _v in _t.items():
        _s = _s.replace(_k, _v)
    if "@@" in _s:
        raise RuntimeError("導覽 CSS 仍有未替換的佔位符")
    return _s


NAV4_CSS: str = build_css()


# ══════════════════════════════════════════════════════════════════
# 狀態：單一真相源 = `ia_nav4.NAV4_PAGE_KEY`
# ══════════════════════════════════════════════════════════════════
def _log_reset(what: str, bad: object, to: str) -> None:
    """非法狀態被重設時留 log（stderr；不上畫面——導覽沒有「真出錯」狀態，且不得讓導覽消失）。"""
    import sys
    print(f"[nav4] {what} 的值 {bad!r} 不合法，已重設為預設 {to!r}", file=sys.stderr)


def current_page4() -> str:
    """目前的主導覽頁 id。缺 → 預設 📊 市場；**存在但非法 → 重設為預設並 log**（導覽不得因壞 state 消失，
    頁面與導覽狀態一致；L0 `coerce_page4` 本身仍 Fail Loud，這裡是 L5 的自癒層）。第一次呼叫會把值寫進 SSOT。"""
    _raw = st.session_state.get(ia_nav4.NAV4_PAGE_KEY)
    try:
        _p = ia_nav4.coerce_page4(_raw)
    except ValueError:
        _p = ia_nav4.default_page4()
        _log_reset(ia_nav4.NAV4_PAGE_KEY, _raw, _p)
    st.session_state[ia_nav4.NAV4_PAGE_KEY] = _p
    return _p


def current_leaf() -> str | None:
    """標的頁葉選擇（view 頁 id）。None＝尚未選（用預設葉）；**存在但非法 → 重設為預設葉並 log**。"""
    _raw = st.session_state.get(ia_nav4.NAV4_TARGET_LEAF_KEY)
    if _raw is None:
        return None
    try:
        ia_nav4.resolve_view(ia_nav4.P4_TARGET, _raw)
    except ValueError:
        _d = ia_nav4.views_of(ia_nav4.P4_TARGET)[0]
        _log_reset(ia_nav4.NAV4_TARGET_LEAF_KEY, _raw, _d)
        st.session_state[ia_nav4.NAV4_TARGET_LEAF_KEY] = _d
        return _d
    return _raw


def current_view() -> str:
    """目前要渲染的 view 頁 id（🎯 標的 會再看葉選擇）。"""
    return ia_nav4.resolve_view(current_page4(), current_leaf())


def _sync_widget(widget_key: str, value: str) -> None:
    """渲染前把 widget 的顯示值預填成 SSOT。⚠️ 必須在該 widget 實例化**之前**呼叫（之後寫會拋 StreamlitAPIException）。"""
    if st.session_state.get(widget_key) != value:
        st.session_state[widget_key] = value


def _on_nav_change(widget_key: str) -> None:
    """兩個導覽 widget 共用的回呼：**只寫 SSOT 一格**。對不到的值 → Fail Loud（不靜默改用預設頁）。"""
    st.session_state[ia_nav4.NAV4_PAGE_KEY] = ia_nav4.page4_from_label(st.session_state.get(widget_key))


def _on_leaf_change() -> None:
    _p = current_page4()
    st.session_state[ia_nav4.NAV4_TARGET_LEAF_KEY] = ia_nav4.leaf_from_label(
        _p, st.session_state.get(ia_nav4.NAV4_WIDGET_LEAF_KEY))


# ══════════════════════════════════════════════════════════════════
# 渲染
# ══════════════════════════════════════════════════════════════════
def render_sidebar_nav() -> str:
    """桌機左側欄導覽（呼叫端須在 `with st.sidebar:` 內）。回傳目前要渲染的 **view 頁 id**。"""
    _p = current_page4()
    _sync_widget(ia_nav4.NAV4_WIDGET_SIDE_KEY, ia_nav4.page4_label(_p))
    st.radio(
        "主導覽", ia_nav4.page4_options(), key=ia_nav4.NAV4_WIDGET_SIDE_KEY,
        label_visibility="collapsed",
        on_change=_on_nav_change, args=(ia_nav4.NAV4_WIDGET_SIDE_KEY,))
    return current_view()


def render_bottom_nav() -> None:
    """手機底部固定列（CSS 注入 ＋ 橫排 radio；桌機由 CSS 隱藏，CSS 失效時退化為一般橫排 radio）。"""
    st.markdown(NAV4_CSS, unsafe_allow_html=True)
    _p = current_page4()
    _sync_widget(ia_nav4.NAV4_WIDGET_BOTTOM_KEY, ia_nav4.page4_label(_p))
    with st.container(key=ia_nav4.NAV4_BOTTOM_CONTAINER_KEY):
        st.radio(
            "主導覽（手機）", ia_nav4.page4_options(), key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY,
            horizontal=True, label_visibility="collapsed",
            on_change=_on_nav_change, args=(ia_nav4.NAV4_WIDGET_BOTTOM_KEY,))


def render_target_leaf_selector() -> None:
    """🎯 標的 的第二層選擇（🔍 找標的／🔬 查一檔；沿用 D2 的「同一方向內第二層」機制）。其他頁不渲染。

    ⚠️ 過渡項：A 規格 §4.2 把標的頁定義成**單一頁**（產業機會 → 候選標的 → 單一股票同頁展開），
    那是 UI-T 批次（PLAN §5 序 7）的內容；NAV-1 只換導覽殼，現有 `page_find`／`page_inspect` 兩個 view 仍是兩頁，
    故用本選擇器在標的頁內切換。UI-T 落地時本函式應連同 `NAV4_TARGET_LEAF_KEY` 一併移除。
    """
    _p = current_page4()
    if not ia_nav4.has_leaves(_p):
        return
    _view = ia_nav4.resolve_view(_p, current_leaf())
    _label = ia_nav4.leaf_options(_p)[ia_nav4.views_of(_p).index(_view)]
    _sync_widget(ia_nav4.NAV4_WIDGET_LEAF_KEY, _label)
    st.radio(
        "標的頁子選單", ia_nav4.leaf_options(_p), key=ia_nav4.NAV4_WIDGET_LEAF_KEY,
        horizontal=True, label_visibility="collapsed", on_change=_on_leaf_change)


def render_main_nav() -> None:
    """主畫面區的導覽部分：底部固定列 ＋（🎯 標的 才有的）葉選擇器。"""
    render_bottom_nav()
    render_target_leaf_selector()
