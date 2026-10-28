"""shared/ia_nav4.py — 新版戰情室「固定四頁主導覽」的名稱 / 對映 / 旗標 SSOT（L0 Infra；NAV-1，DEC-092 Q6／DEC-097）。

═══ 這個模組在解什麼問題 ══════════════════════════════════════════════
客戶（DEC-092／DEC-097）指定新版的主導覽**固定四頁**：📊 市場／🎯 標的／💼 持股／👤 我的；
手機＝底部固定四按鈕、桌機＝左側欄四項（`docs/vnext/d25_wireframes/`），**兩者共用同一個頁狀態**。
本模組只回「字串、對映、key 名稱、純函式」，**不做導覽、不碰 session、不 import streamlit**
（同 `shared/ia_nav.py` 的既有慣例）。畫面由 `src/ui/views/shell_nav4.py`（L5）負責，路由由 `app.py` 負責。

═══ 與 `shared/ia_nav.py` 的關係（⚠️ 先讀）════════════════════════════
- **不改、不取代** `shared/ia_nav.py`（D2 Cloud 啟動事故模組，`NEWUI-STAGE-D2-BOOT-INCIDENT`；
  DEC-092 Q6：D2 殼過渡版保留至四頁替代）。本檔只 **import 它的頁 id 常數**（單向、向下），
  不複製第二份頁 id（§2.1 SSOT）。
- ia_nav 的六向 `NAV_TREE` / `PAGE_LABELS`（「📊 大盤」「💼 我的持股」…）**原封不動**，仍是 legacy 模式（`?legacy=1`）的導覽。
  四頁的顯示名 **不寫進** `PAGE_LABELS`（I-1 頁名改寫＝客戶尚未拍板，不在本批範圍）。

═══ 為什麼是 L0 ══════════════════════════════════════════════════════
純顯示字串 + 純函式，零 I/O、零 streamlit。
"""
from __future__ import annotations

from collections.abc import Iterable

from shared import ia_nav

# ══════════════════════════════════════════════════════════════════
# 四頁 id / 顯示名（客戶逐字，⛔ 一字不改：emoji、空格、字詞都算）
# ══════════════════════════════════════════════════════════════════
#: 頁 id 一律 `p4_` 前綴：`market` / `hold` / `me` 同時是 `ia_nav` 的 view 頁 id，
#: 共用字串會讓「這個 id 是主導覽頁還是 view」在 grep 時分不清（同 `ia_nav.DIR_*` 的 `dir_` 前綴作法）。
P4_MARKET: str = "p4_market"
P4_TARGET: str = "p4_target"
P4_HOLD: str = "p4_hold"
P4_ME: str = "p4_me"

#: 四頁 id → 顯示名。⚠️ 順序就是導覽元件的順序（客戶指定：市場／標的／持股／我的）。
PAGE4_LABELS: dict[str, str] = {
    P4_MARKET: "📊 市場",
    P4_TARGET: "🎯 標的",
    P4_HOLD: "💼 持股",
    P4_ME: "👤 我的",
}

#: 主導覽頁 id → 該頁底下承接的 view 頁 id（`ia_nav.PAGE_LABELS` 的 key）。
#: 多於一個 ＝ 同一方向內的第二層選擇（沿用 D2 的「葉」機制；見 `leaf_options`）。
#: 🎯 標的 ＝ 🔍 找標的 ＋ 🔬 查一檔（A 規格 §2.1「承接的現有頁」欄）。
PAGE4_TO_VIEW: dict[str, tuple[str, ...]] = {
    P4_MARKET: (ia_nav.PAGE_MARKET,),
    P4_TARGET: (ia_nav.PAGE_FIND, ia_nav.PAGE_INSPECT),
    P4_HOLD: (ia_nav.PAGE_HOLD,),
    P4_ME: (ia_nav.PAGE_ME,),
}

#: **不在四頁導覽內**的 view：D2 過渡殼（🚦 今天、📖 憑什麼），只在 legacy 模式（`?legacy=1`）的 D2 側欄可達。
#: 為什麼這不是能力遺失（DEC-092 Q6／A 規格 §2.1）：⚡行動→各頁「需要處理」、🩺→資料健康小入口、
#: 📖→「查看依據」都是**之後批次**（UI-M／AB-5／AB-6）要併入四頁的能力；且這兩頁的功能在舊 7 頁籤
#: （🔧 工具箱 › 🔎 資料診斷、🧬 AI 問答）**仍然存在**（舊 UI 不刪，DEC-019/020）。
#: ⚠️ 誠實揭露：預設（新）模式下這兩頁的**入口**暫時不可見——這是已知的暫時缺口，不是「已併入」；
#: 見 `docs/vnext/NEWUI_D25_NAV1_SPEC_2026-10-28.md`「已知限制」。
LEGACY_ONLY_VIEWS: tuple[str, ...] = (ia_nav.PAGE_TODAY, ia_nav.PAGE_WHY)

# ══════════════════════════════════════════════════════════════════
# 狀態 key（單一真相源 = 一個 session_state key）
# ══════════════════════════════════════════════════════════════════
#: **頁狀態的唯一真相源**：值為四頁 id。側欄單選、底部固定列、任何將來的導覽元件都只經 on_change 寫這一格。
NAV4_PAGE_KEY: str = "_nav4_page"
#: 🎯 標的 的第二層（葉）選擇：值為 view 頁 id（`find` / `inspect`）。與 `NAV4_PAGE_KEY` 分開存，
#: 切到別頁再切回來仍保留（widget 自己的 state 在該 widget 不渲染的那一輪會被 Streamlit 丟掉，所以 SSOT 不放在 widget key）。
NAV4_TARGET_LEAF_KEY: str = "_nav4_target_leaf"
#: 三個導覽 widget 的 key（只有「顯示」用途；值由上面兩個 SSOT 每輪預填，見 shell_nav4）。
NAV4_WIDGET_SIDE_KEY: str = "_nav4_w_side"
NAV4_WIDGET_BOTTOM_KEY: str = "_nav4_w_bottom"
NAV4_WIDGET_LEAF_KEY: str = "_nav4_w_leaf"
#: 底部固定列的 `st.container(key=...)`；CSS class 為 `.st-key-<此值>`（Streamlit 非公開保證，見 spec 已知限制）。
NAV4_BOTTOM_CONTAINER_KEY: str = "nav4_bottom"

# ══════════════════════════════════════════════════════════════════
# legacy / rollback 旗標（DEC-097：技術上用 routing／feature switch 隱藏舊 UI；入口不得出現在一般使用者導覽）
# ══════════════════════════════════════════════════════════════════
#: 唯一的進入方式：網址參數 `?legacy=1`（`?legacy=0` 清除）。⛔ 不在任何導覽、側欄、頁面放可見連結。
LEGACY_QUERY_PARAM: str = "legacy"
#: 首次出現即寫入的 session 旗標（耐 rerun；斷線重連若網址仍帶參數則重新寫入）。
LEGACY_SESSION_KEY: str = "_nav4_legacy"

#: 單行不換行的上限：4 個按鈕共用一列（手機 390px 寬 ⇒ 每格約 90px），標籤過長會撐破單行。
_LABEL_MAX_CHARS = 6


def resolve_legacy_flag(query_value: object, current: bool) -> bool:
    """`?legacy=` 的值 ＋ 目前旗標 → 新旗標。純函式。

    - `'1'` → True；`'0'` → False；
    - 參數不存在（None）、空字串、其他任何值（含 list、亂字）→ **維持 `current`**。
      ⚠️ 使用者可控的 URL 輸入：不 raise（亂打網址不該讓整個 app 白屏），也**不**把亂值當成 True
      （否則 `?legacy=` 空值就會把一般使用者丟進舊 UI）。
    """
    if isinstance(query_value, str):
        _v = query_value.strip()
        if _v == "1":
            return True
        if _v == "0":
            return False
    return bool(current)


# ══════════════════════════════════════════════════════════════════
# 查詢函式（未知 id → Fail Loud，不回「還算像樣」的預設，理由同 `ia_nav.page_label`）
# ══════════════════════════════════════════════════════════════════
def page4_ids() -> tuple[str, ...]:
    return tuple(PAGE4_LABELS)


def page4_options() -> tuple[str, ...]:
    """導覽元件的顯示字串（順序＝四頁順序）。"""
    return tuple(PAGE4_LABELS.values())


def default_page4() -> str:
    """預設落點＝第一個（📊 市場）。"""
    return next(iter(PAGE4_LABELS))


def page4_label(page4: str) -> str:
    if page4 not in PAGE4_LABELS:
        raise ValueError(f"未知的主導覽頁 id {page4!r}；合法值：{sorted(PAGE4_LABELS)}")
    return PAGE4_LABELS[page4]


def page4_from_label(label: object) -> str:
    """顯示字串 → 頁 id。對不到 → Fail Loud（不得靜默退回預設頁，否則使用者以為自己沒選到）。"""
    for _p, _l in PAGE4_LABELS.items():
        if _l == label:
            return _p
    raise ValueError(f"未知的主導覽選項 {label!r}；合法值：{list(PAGE4_LABELS.values())}")


def coerce_page4(value: object) -> str:
    """session 內取到的值 → 合法頁 id；缺（None）→ 預設頁；**存在但非法 → Fail Loud**。

    None 是「第一次進來」的正常態；非法值是壞掉的 state（例如舊版殘值），不得靜默吞掉。
    """
    if value is None:
        return default_page4()
    if value not in PAGE4_LABELS:
        raise ValueError(f"{NAV4_PAGE_KEY} 的值 {value!r} 不是合法頁 id；合法值：{sorted(PAGE4_LABELS)}")
    return value  # type: ignore[return-value]


def views_of(page4: str) -> tuple[str, ...]:
    page4_label(page4)  # 驗 id（Fail Loud）
    return PAGE4_TO_VIEW[page4]


def has_leaves(page4: str) -> bool:
    """該頁底下是否有第二層選擇（目前只有 🎯 標的）。"""
    return len(views_of(page4)) > 1


def leaf_options(page4: str) -> tuple[str, ...]:
    """第二層的顯示字串（view 頁名，來自 `ia_nav.page_label` ⇒ 不手抄第二份）。"""
    return tuple(ia_nav.page_label(v) for v in views_of(page4))


def leaf_from_label(page4: str, label: object) -> str:
    """第二層顯示字串 → view 頁 id；對不到 → Fail Loud。"""
    for _v, _l in zip(views_of(page4), leaf_options(page4)):
        if _l == label:
            return _v
    raise ValueError(f"{page4!r} 底下沒有選項 {label!r}；合法值：{list(leaf_options(page4))}")


def resolve_view(page4: str, leaf: object = None) -> str:
    """主導覽頁 ＋（多葉頁的）葉選擇 → 要渲染的 view 頁 id。

    - 單 view 頁：回唯一的 view（`leaf` 被忽略）。
    - 多 view 頁：`leaf` 為 None → 第一個 view（進入預設落點，同 D2 `first_built_page`）；
      `leaf` 存在但不在該頁底下 → **Fail Loud**（不靜默退回預設葉）。
    """
    _views = views_of(page4)
    if len(_views) == 1:
        return _views[0]
    if leaf is None:
        return _views[0]
    if leaf not in _views:
        raise ValueError(f"{page4!r} 底下沒有葉 {leaf!r}；合法值：{list(_views)}")
    return leaf  # type: ignore[return-value]


# ══════════════════════════════════════════════════════════════════
# 自洽對帳（import 時就跑；用 raise 不用 assert —— `python -O` 不會把它拿掉，§1）
# ══════════════════════════════════════════════════════════════════
def reconcile_nav4(view_page_ids: Iterable[str] | None = None) -> None:
    """四頁表 ↔ 對映表 ↔ `ia_nav` view 頁表 ↔（呼叫端提供的）view 派發表，對不起來 → ``RuntimeError``。

    ``view_page_ids``：`app.py` 的 ``_IA_VIEWS`` 的 key 集合（真的有 renderer 的頁）；None ＝ 只驗不依賴派發表的那幾條。
    規則：
      1. 四頁恰四個；`PAGE4_TO_VIEW` 的 key ＝ `PAGE4_LABELS` 的 key；
      2. 每個 view 頁 id 恰出現在**一處**（四頁之一 或 `LEGACY_ONLY_VIEWS`），不重複；
      3. 四頁 ∪ legacy-only 的 view ＝ `ia_nav.PAGE_LABELS` 的全部（一頁都不能漏接、也不能多接）；
      4. 標籤單行：非空、不重複、≤ `_LABEL_MAX_CHARS` 字；
      5. 有派發表時：派發表的 key ＝ `ia_nav.PAGE_LABELS`（即每個被導覽引用的 view 都真的有 renderer，且沒有多餘的 renderer）。
    """
    if len(PAGE4_LABELS) != 4:
        raise RuntimeError(f"主導覽必須恰為 4 頁（客戶 DEC-092／DEC-097），實得 {len(PAGE4_LABELS)}：{list(PAGE4_LABELS)}")
    if set(PAGE4_TO_VIEW) != set(PAGE4_LABELS):
        raise RuntimeError(
            f"PAGE4_TO_VIEW 與 PAGE4_LABELS 的頁對不起來：{sorted(PAGE4_TO_VIEW)} vs {sorted(PAGE4_LABELS)}")
    _labels = list(PAGE4_LABELS.values())
    if len(set(_labels)) != len(_labels) or any((not _l) or len(_l) > _LABEL_MAX_CHARS for _l in _labels):
        raise RuntimeError(f"主導覽標籤必須非空、不重複、單行（≤{_LABEL_MAX_CHARS} 字）：{_labels}")
    _flat = [v for _vs in PAGE4_TO_VIEW.values() for v in _vs] + list(LEGACY_ONLY_VIEWS)
    _dups = sorted({v for v in _flat if _flat.count(v) > 1})
    if _dups:
        raise RuntimeError(f"view 頁同時出現在多個位置（四頁／legacy-only 重疊）：{_dups}")
    _known = set(ia_nav.PAGE_LABELS)
    if set(_flat) != _known:
        raise RuntimeError(
            f"四頁對映與 ia_nav.PAGE_LABELS 對不起來（漏接 / 多接）：缺 {sorted(_known - set(_flat))}，"
            f"多 {sorted(set(_flat) - _known)}")
    for _p, _vs in PAGE4_TO_VIEW.items():
        if not _vs:
            raise RuntimeError(f"主導覽頁 {_p!r} 沒有承接任何 view")
    if view_page_ids is not None:
        _ids = set(view_page_ids)
        if _ids != _known:
            raise RuntimeError(
                f"view 派發表與 ia_nav.PAGE_LABELS 對不起來：派發表 {sorted(_ids)} vs {sorted(_known)}")


# 不依賴 view 派發表的那幾條，import 時就先驗（派發表那條由 `app.py` 再呼叫一次）。
reconcile_nav4()
