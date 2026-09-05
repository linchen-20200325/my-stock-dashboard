"""src/ui/tabs/tab_today.py — 五頁戰情室 IA 第 1 頁「🚦 今天」（L5 UI）。

規格出處：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[0]`（id=`today`），
客戶 2026-09-05 拍板。**線框是可反序列化的資料結構**，本檔的區塊清單、
四態文案骨架與 submit 名稱皆自該結構取出，不是照畫面用眼睛抄的。

單一職責（線框 `job` 原文）::

    回答「今天能不能出手、出手到幾成」。

═══ 本批做到哪裡（**先讀這段再讀 code**）═════════════════════════════
本批是**骨架 + 各狀態的誠實呈現**，不是完成品：

- **已接上資料的只有一條線**：頂部狀態列與三欄摘要的「位階」格，
  讀 L3 canonical 契約 `services.macro_state_locker.get_macro_state`。
  線框 F13/N4 明訂狀態列**必須**讀它、不得依賴任何 render 副作用。
- **其餘區塊一律標「未接線」並就地寫明原因**。這裡的「未接線」是
  `shared.ui_state.UI_UNWIRED` 的字面語意 —— **刻意沒接，叫不叫都一樣**：
  本頁確實沒有那些區塊的取數程式碼，重按更新一百次也不會變。
  ⚠️ 它**不是**「這次沒抓到」（那是 `UI_EMPTY`），也**不是**「還沒有人叫」
  （那是 `UI_IDLE`）。分批落地的中間狀態只能這樣講才不是謊話。
- **本頁沒有 production caller**（`app.py` 本批不接線，客戶指示）。
  舊分頁不動、不接線、不下架。

═══ 四大鐵律在本檔的落點 ═════════════════════════════════════════════
1. **3 欄自適應網格**：`_grid()` 一律 `st.columns(3)`，格子多於 3 個就
   **換行排第二排，不是加欄**（線框 §04 原文）。天然不足 3 的不硬湊。
2. **Form 封裝防重繪**：**不是包了 `st.form` 就算**。widget 的**當下值**
   （`_SS_MODE_WIDGET`）與**已套用值**（`_SS_APPLIED`）是兩個東西，
   下游一律只讀後者 —— 只包 form 只擋得住互動 rerun，重運算一分沒省。
   線框 F11：form 內**不得**放 `st.button`（實跑即拋
   `StreamlitAPIException`），故兩個動作收斂成 radio + 單一 submit。
3. **四態分離**：走既有 L0 SSOT `shared.ui_state.classify_ui_state`
   （七態，是線框四態＋正常的超集），**不自己配色、不自己判態**。
   對應：灰＝`idle`/`empty`、未接線＝`unwired`、已失準＝`degraded`、
   紅＝`failed`、正常＝`live`。
4. **空狀態引導**：每一個非 `live` 的卡片都帶三要素
   `Note(now/why/where)`，且 `where` 裡的分頁名／按鈕名一律走
   `shared.ia_nav` 的 SSOT 函式，**不手抄字串**。

═══ 一個已知的連帶事項（本批刻意不動，登記在此）═══════════════════════
`src/ui/render/macro_ui_components.py::key_alerts_banner` 的灰態文案
**寫死**「請按『🚀 一鍵更新全部數據』」。新 IA 的 submit 叫
「🚀 更新今日戰情」（`ia_nav.ACTION_UPDATE_TODAY`）。兩者接上的那一天
必須一起改，否則舊文案會指向一顆本頁不存在的按鈕 —— 線框在 ④ 的 note
裡點名了這件事。**本批不改它**：那會動到現行「🌍 總經」分頁的畫面，
而客戶明令舊 tab 不動。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import streamlit as st

from shared import ia_nav
from shared.ui_state import (
    UI_DEGRADED,
    UI_FAILED,
    UI_LIVE,
    UI_UNWIRED,
    classify_ui_state,
    state_meta,
)

# ══════════════════════════════════════════════════════════════════
# session key（本頁自有前綴，不與任何既有 key 相撞）
# ══════════════════════════════════════════════════════════════════
#: radio 的 widget key —— **當下值**。下游禁止讀它（鐵律 2）。
_SS_MODE_WIDGET: str = "p01_update_mode_widget"
#: **已套用值**。只有 submit handler 會寫，下游只讀這個。
_SS_APPLIED: str = "_p01_applied"
#: gate 旗標：使用者有沒有真的送出過一次。
#: **只由 submit handler 寫入**，禁止由 `if not data:` 推導
#: （`shared/ui_state.py` 的鐵律；`tests/test_ui_state_model.py` 有 AST 守衛）。
_SS_REQUESTED: str = "_p01_requested"

# ── 更新模式（線框葉1 ② 的 radio）─────────────────────────────────
MODE_WARM: str = "warm"
MODE_FORCE: str = "force"
MODE_LABELS: dict[str, str] = {
    MODE_WARM: "正常更新（吃暖快取）",
    MODE_FORCE: "強制重抓（清快取）",
}

# ══════════════════════════════════════════════════════════════════
# 「本批尚未接線」的唯一理由字串 —— 一句話只准寫一次
# ══════════════════════════════════════════════════════════════════
#: 為什麼抽成常數：這句話會出現在十幾張卡上。手抄十幾份，改的時候一定會
#: 漏改，然後畫面上同時存在兩種說法（§2.1 SSOT）。
STAGED_ROLLOUT_WHY: str = (
    "五頁 IA 分批落地：本頁目前只有骨架，這一塊的取數尚未接上 —— "
    "**本頁沒有它的程式碼**，不是這次沒抓到"
)
#: 未接線態**沒有使用者可執行的出口**（線框葉2 unwired 原文）。
#: 誠實寫明「這是待接線項，不是你操作的問題」，不要給一個按了也沒用的指路。
STAGED_ROLLOUT_WHERE: str = (
    "這一態沒有你可以執行的出口 —— 這是待接線項，不是你操作的問題；"
    f"{ia_nav.where_to_press(ia_nav.ACTION_UPDATE_TODAY)}也不會改變它"
)


# ══════════════════════════════════════════════════════════════════
# 純資料層（零 streamlit，可單測）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Note:
    """空狀態引導的三要素（鐵律 4）。三個都不得為空。"""

    now: str
    why: str
    where: str

    def __post_init__(self) -> None:
        for _f in ("now", "why", "where"):
            if not str(getattr(self, _f)).strip():
                raise ValueError(
                    f"Note.{_f} 不得為空 —— 鐵律 4 要求三要素齊備"
                    "（現在怎樣 / 為什麼 / 去哪補）")


@dataclass(frozen=True)
class Card:
    """畫面上的**一張卡** —— 守衛的最小單位。

    ⚠️ **粒度就是這裡**：狀態與三要素掛在卡上，不掛在區塊上。
    掛在區塊上的話「只改其中一張卡」不會被守衛抓到（同一段裡別的卡
    會替它通過）。
    """

    key: str
    label: str
    state: str
    #: `live` 時可為 None（有結論就講結論）；其餘一律必填。
    note: Note | None = None
    #: 正常態才准有的結論文字。非 `live` 一律為空。
    value: str = ""

    def __post_init__(self) -> None:
        if self.state != UI_LIVE and self.note is None:
            raise ValueError(
                f"卡 {self.key!r} 的狀態是 {self.state!r} 卻沒有 Note —— "
                "非正常態一律要附三要素（鐵律 4）")
        if self.state != UI_LIVE and self.value:
            raise ValueError(
                f"卡 {self.key!r} 不是正常態卻帶了結論文字 {self.value!r} —— "
                "只有 live 能給結論（線框 §02：只有這一態能給結論文字）")


@dataclass(frozen=True)
class Block:
    """線框葉底下的一個區塊。`cards` 為空 = 該區塊是互動元件（如操作列）。"""

    key: str
    title: str
    leaf: str
    cards: tuple[Card, ...] = ()


# ── 葉 id（畫面上的兩葉；名字走 ia_nav SSOT）────────────────────────
LEAF_CONCLUSION: str = ia_nav.LEAF_TODAY_CONCLUSION
LEAF_DETAIL: str = ia_nav.LEAF_TODAY_DETAIL

#: 葉2 的七段（線框 `PAGES[0].blocks[5].n` 原文逐字）。
DETAIL_SEGMENTS: tuple[tuple[str, str], ...] = (
    ("a_state", "A 市場狀態"),
    ("b_long", "B 長期"),
    ("c_mid", "C 中期"),
    ("d_short", "D 短線"),
    ("e_chips", "E 籌碼"),
    ("f_global_risk", "F 全球風險"),
    ("g_cross", "G 跨桶裁決"),
)


def _staged_card(key: str, label: str, *, now: str) -> Card:
    """尚未接線的卡 —— 本批絕大多數卡片走這裡。"""
    return Card(
        key=key, label=label, state=UI_UNWIRED,
        note=Note(now=now, why=STAGED_ROLLOUT_WHY, where=STAGED_ROLLOUT_WHERE),
    )


def classify_macro_contract(state: Mapping[str, Any] | None,
                            *, error: Any = None) -> str:
    """L3 總經契約 → 本頁的畫面狀態（走 L0 SSOT，本檔不自己判態）。

    Args:
        state: `services.macro_state_locker.get_macro_state()` 的回傳 dict。
        error: 讀契約時拋出的例外（有值 = 系統真出錯 → 紅）。

    三條對映，逐條寫出理由：

    - ``requested`` ← ``source != SOURCE_UNLOADED``（或讀契約時拋了例外 ——
      例外本身就證明這次叫過它）。
      `source` 是**上游自己標的來源分支**，`SOURCE_UNLOADED` 的字面意思
      就是「四條來源都沒有、沒有人算過」。這是**上游帶下來的旗標**，
      不是拿資料的有無反推（`shared/ui_state.py` 的鐵律）。
    - ``has_value`` ← ``is_loaded``。契約自己的「這輪有沒有值」。
    - ``discriminative`` ← ``source != SOURCE_FILE_RULE_ENGINE``。
      **這是線框 N4 補的第 3 條來源**：走 `macro_state.json` 的 AI 鎖定
      快照時 `is_loaded=True`、畫面會長得像正常的 🟢，**但它是上一次鎖的
      結論，不是這一輪算的** → 已失準（有值但不能拿來下判斷）。
    """
    from shared import regime_arbiter as _RA

    _s = dict(state or {})
    _source = _s.get("source") or _RA.SOURCE_UNLOADED
    # 讀契約時拋了例外 → 這次**確實**叫過它（例外本身就是證據）。
    # 不補這一項的話 `classify_ui_state` 會因為「沒叫過卻有錯」而 raise，
    # 把一個真故障變成第二個例外（§1：紅態要看得見，不是換一種炸法）。
    _attempted = (error is not None) or (_source != _RA.SOURCE_UNLOADED)
    return classify_ui_state(
        requested=_attempted,
        error=error,
        has_value=bool(_s.get("is_loaded")),
        discriminative=(_source != _RA.SOURCE_FILE_RULE_ENGINE),
    )


def build_status_bar_card(state: Mapping[str, Any] | None,
                          *, error: Any = None) -> Card:
    """（跨頁）頂部狀態列 —— 線框 `PAGES[0].blocks[6]`。

    ⚠️ **刻意不顯示「更新於 hh:mm」**：`get_macro_state()` 的回傳 dict
    只有 9 個 key，**不含 timestamp**（檔內有，契約沒帶出來）。要顯示真實
    時間就得改回傳契約 —— 那是 L3 `.py` 變更，本批不做。
    **寧可寫「時間不明」，也不編一個時間出來**（線框 N4 原文）。
    """
    _st = classify_macro_contract(state, error=error)
    _s = dict(state or {})
    if _st == UI_LIVE:
        # 位階的中文說法**讀契約自己的 `traffic_light`**（它的 docstring 寫明
        # 那是「燈號卡的中文 label」），契約沒帶時才退回 canonical 的
        # `regime`。**不在本檔另立一份 regime→中文對照** —— 那會是第二份
        # 真相源，而且一定會跟燈號卡漂開（§2.1 SSOT）。
        _say = _s.get("traffic_light") or _s.get("regime", "")
        return Card(
            key="statusbar.macro", label="總經", state=UI_LIVE,
            value=f"{_s.get('light', '')} 位階 {_say}".strip(),
        )
    if _st == UI_DEGRADED:
        return Card(
            key="statusbar.macro", label="總經", state=UI_DEGRADED,
            note=Note(
                now="⚠️ 總經位階**來自快照，時間不明**",
                why=("本輪生效的是來源優先序第 3 條（`macro_state.json` 的 "
                     "AI 鎖定快照）—— 它是**上一次**鎖的結論，不是這一輪算的；"
                     "契約沒有把時間帶出來，所以這裡不編一個時間"),
                where=(f"到{ia_nav.where_to_find(ia_nav.PAGE_TODAY)}"
                       f"{ia_nav.where_to_press(ia_nav.ACTION_UPDATE_TODAY)}重算"),
            ),
        )
    if _st == UI_FAILED:
        return Card(
            key="statusbar.macro", label="總經", state=UI_FAILED,
            note=Note(
                now="🔴 總經位階讀取失敗",
                why=f"讀 L3 canonical 契約時拋出例外：{error}",
                where=(f"到{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"
                       "看該源狀態"),
            ),
        )
    return Card(
        key="statusbar.macro", label="總經", state=_st,
        note=Note(
            now="⬜ 總經未評估",
            why=("L3 canonical 契約四條來源本輪皆無值 → 回 `unknown`，"
                 "**不是** `neutral`；本站不以缺值推導「中性」"),
            where=(f"到{ia_nav.where_to_find(ia_nav.PAGE_TODAY)}"
                   f"{ia_nav.where_to_press(ia_nav.ACTION_UPDATE_TODAY)}"),
        ),
    )


def build_today_blocks(*, macro_state: Mapping[str, Any] | None = None,
                       macro_error: Any = None) -> tuple[Block, ...]:
    """本頁的**完整區塊清單**（線框 `PAGES[0].blocks` 七塊，一塊不少）。

    純函式：不碰 session、不 import streamlit。渲染端把 session 讀出來
    再傳進來，這樣整張畫面的狀態可以在沒有 streamlit 的情況下驗。
    """
    _bar = build_status_bar_card(macro_state, error=macro_error)
    _regime_card = Card(
        key="summary.regime", label="位階", state=_bar.state,
        note=_bar.note,
        value=(_bar.value if _bar.state == UI_LIVE else ""),
    )

    return (
        Block(
            key="today.statusbar", leaf=LEAF_CONCLUSION,
            title="（跨頁）頂部狀態列",
            cards=(_bar,),
        ),
        Block(
            key="today.verdict", leaf=LEAF_CONCLUSION,
            title="① 結論燈 — 建議持股 %",
            cards=(_staged_card(
                "verdict.exposure", "建議持股 %",
                now="⬜ 建議持股 % 尚未接線"),),
        ),
        Block(
            key="today.actions", leaf=LEAF_CONCLUSION,
            title="② 操作列",
        ),
        Block(
            key="today.summary", leaf=LEAF_CONCLUSION,
            title="③ 三欄摘要",
            cards=(
                _regime_card,
                _staged_card("summary.momentum", "動能",
                             now="⬜ 動能尚未接線"),
                _staged_card("summary.risk", "風險",
                             now="⬜ 風險尚未接線"),
            ),
        ),
        Block(
            key="today.key_banner", leaf=LEAF_CONCLUSION,
            title="④ 今日關鍵橫幅",
            cards=(_staged_card(
                "key_banner.alerts", "今日關鍵",
                now="⬜ 今日關鍵尚未接線 —— **未評估 ≠ 無異常**"),),
        ),
        Block(
            key="today.warroom", leaf=LEAF_CONCLUSION,
            title="⑤ 今日作戰室　⑥ AI 摘要（摺疊）",
            cards=(
                _staged_card("warroom.todo", "今天該做的事",
                             now="⬜ 尚無作戰項目"),
                _staged_card("warroom.ai", "AI 摘要",
                             now="⬜ AI 摘要尚未接線"),
            ),
        ),
        Block(
            key="today.detail", leaf=LEAF_DETAIL,
            title="指標明細 — 七段",
            cards=tuple(
                _staged_card(f"detail.{_k}", _label,
                             now=f"⬜ {_label} 尚未接線")
                for _k, _label in DETAIL_SEGMENTS
            ),
        ),
    )


def applied_update_mode(session: Mapping[str, Any]) -> str | None:
    """下游唯一准讀的更新模式來源 —— **已套用值**，不是 widget 當下值。

    回 None = 使用者還沒送出過（下游據此判 `requested=False`）。
    """
    _applied = session.get(_SS_APPLIED)
    if not isinstance(_applied, dict):
        return None
    _mode = _applied.get("mode")
    return _mode if _mode in MODE_LABELS else None


# ══════════════════════════════════════════════════════════════════
# 渲染層（薄；所有判斷都在上面的純函式裡）
# ══════════════════════════════════════════════════════════════════
def _grid(items: Sequence[Any], per_row: int = 3):
    """鐵律 1：一律 3 欄，**多於 3 個換行排第二排，不是加欄**。

    天然不足 3 的保持原欄數（線框 §04：硬湊三欄跟擠七欄一樣是排版失敗）。
    """
    for _i in range(0, len(items), per_row):
        _chunk = items[_i:_i + per_row]
        yield _chunk, st.columns(len(_chunk))


def _render_card(card: Card) -> None:
    _name, _glyph, _hex = state_meta(card.state)
    st.markdown(
        f"<div style='border:1px solid {_hex}33;border-left:3px solid {_hex};"
        "border-radius:0 6px 6px 0;padding:8px 12px;margin:4px 0;'>"
        f"<div style='font-size:12px;color:{_hex};'>{_glyph} {_name}</div>"
        f"<div style='font-weight:600;margin-top:2px;'>{card.label}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if card.state == UI_LIVE:
        st.markdown(f"**{card.value}**")
        return
    _n = card.note
    assert _n is not None  # Card.__post_init__ 已保證
    st.markdown(
        f"{_n.now}\n\n"
        f"　**為什麼**：{_n.why}\n\n"
        f"　**去哪補**：{_n.where}"
    )


def _render_update_form() -> None:
    """② 操作列 —— 鐵律 2 的落點。

    **form 只是外殼，防重繪靠的是「當下值 / 已套用值」分家**：
    radio 綁在 `_SS_MODE_WIDGET`，下游一律讀 `_SS_APPLIED`。
    使用者在 form 裡怎麼撥 radio 都不會動到已套用值，
    只有按下 submit 才會把當下值搬過去。
    """
    with st.form("form_today"):
        st.radio(
            "更新模式",
            options=list(MODE_LABELS),
            format_func=lambda _k: MODE_LABELS[_k],
            key=_SS_MODE_WIDGET,
            horizontal=True,
        )
        _submitted = st.form_submit_button(
            ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY),
            type="primary",
        )
    if _submitted:
        # 唯一的寫入點：當下值 → 已套用值 + gate 旗標。
        st.session_state[_SS_APPLIED] = {
            "mode": st.session_state.get(_SS_MODE_WIDGET, MODE_WARM),
        }
        st.session_state[_SS_REQUESTED] = True

    st.caption(
        "⚠️ 本批只落地骨架：按下之後會記下你選的更新模式，"
        "**但取數尚未接上** —— 標「未接線」的區塊不會因此改變。"
        "這不是故障，是分批落地的中間狀態。"
    )


def render_tab_today() -> None:
    """🚦 今天（五頁 IA 第 1 頁）。**本批無 production caller，刻意如此。**"""
    _macro_state: Mapping[str, Any] | None = None
    _macro_error: Any = None
    try:
        from src.services.macro_state_locker import get_macro_state
        _macro_state = get_macro_state(
            st.session_state.get("warroom_summary"))
    except Exception as _e:  # noqa: BLE001 — 讀契約失敗 = 系統真出錯 → 紅態
        _macro_error = _e

    _blocks = build_today_blocks(
        macro_state=_macro_state, macro_error=_macro_error)

    st.markdown(f"## {ia_nav.page_label(ia_nav.PAGE_TODAY)}")
    st.caption("回答「今天能不能出手、出手到幾成」。")

    # 頂部狀態列：常駐一條，位在兩葉之上。
    for _b in _blocks:
        if _b.key == "today.statusbar":
            for _cards, _cols in _grid(_b.cards):
                for _c, _col in zip(_cards, _cols):
                    with _col:
                        _render_card(_c)

    _leaf1, _leaf2 = st.tabs([
        ia_nav.SECTION_LABELS[LEAF_CONCLUSION],
        ia_nav.SECTION_LABELS[LEAF_DETAIL],
    ])
    with _leaf1:
        for _b in _blocks:
            if _b.leaf != LEAF_CONCLUSION or _b.key == "today.statusbar":
                continue
            st.markdown(f"#### {_b.title}")
            if _b.key == "today.actions":
                _render_update_form()
                continue
            for _cards, _cols in _grid(_b.cards):
                for _c, _col in zip(_cards, _cols):
                    with _col:
                        _render_card(_c)
    with _leaf2:
        for _b in _blocks:
            if _b.leaf != LEAF_DETAIL:
                continue
            st.markdown(f"#### {_b.title}")
            for _cards, _cols in _grid(_b.cards):
                for _c, _col in zip(_cards, _cols):
                    with _col:
                        _render_card(_c)
