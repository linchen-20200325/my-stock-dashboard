"""Phase 3 共用視覺元件 —— 純字串模組（無 I/O、無 streamlit）。

規格出處（本檔所有決定的上位）：
- `docs/vnext/PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md` §3（客戶 2026-10-30 核准，DEC-115；
  標「未採用」處不實作）
- `docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md` §16.2 步驟 1
- `docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md` §4／§6／§8／§10／§11／§19

⛔ 硬邊界
- 只 import 標準庫、`shared.ui_state`（L0）與 `src.ui_v2.*`；⛔ 不 import streamlit／`src.data`／
  `src.services`／`_ui_kit`（AST 守衛在 `tests/ui_v2/test_compact.py`）。
- ⛔ 不掛任何頁；`compact_css()` 與 `markup.page_css()` 分開，不被既有頁注入。
- ⛔ chip 不進 `components.BADGES`（封閉 11 種）、⛔ 不走訊號文字頻道（本檔不 import `_ui_kit`）。
- ⛔ Missing 誠實：符號與狀態字一律讀 `shared.ui_state.UI_STATE_META`；本檔不自造 ⬜／▨ 等符號文字、
  不自造原因字（原因由呼叫端傳入，且不得自帶第二個狀態符號）。
- ⛔ sparkline／小倍數不顯示最新／最高／最低數字（D5=A）。
- 色彩：紅色只給 `failed`；stale 用琥珀 ⚠；護欄為實線粗框（D3=A，⛔ 虛線）。
- ⚠️ 掛頁注意（Phase 3 步驟 4，floor 1.56.0 實跑，`docs/vnext/PHASE3_D8_FLOOR156_VERIFICATION_2026-10-30.md`）：
  **SVG 不可經 `st.html`**（1.56.0 會把行內 `<svg>` 整段剝除，無 exception）；`sparkline_svg` 的輸出掛頁時
  用 `st.markdown(unsafe_allow_html=True)`，或改包成 data-URI `<img>`。
"""
from __future__ import annotations

import math
import numbers
import re
import unicodedata
from dataclasses import dataclass
from html import escape
from types import MappingProxyType
from typing import Final, Generic, Mapping, Sequence, TypeVar

from shared import ui_state as _ui_state
from src.ui_v2 import components, markup, tokens

T = TypeVar("T")


# ══════════════════════════════════════════════════════════════════
# 0. 小工具
# ══════════════════════════════════════════════════════════════════
def _esc(text: object) -> str:
    """所有外部字串一律 escape（含引號，可安全放進屬性）。"""
    return escape(str(text), quote=True)


def _state_glyphs() -> tuple[str, ...]:
    """狀態符號全集（**呼叫時**讀 L0，⛔ 不抄字、⛔ 不在 import 時凍結）——
    用來擋「原因／值裡自帶第二個狀態符號」（契約 §6 R8-2）。"""
    return tuple(meta[1] for meta in _ui_state.UI_STATE_META.values())


#: 零寬／不可見字元：視為空（不可見的「文字」不是文字）。
_INVISIBLE: Final[str] = "\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\ufeff\u00ad\u180e\u3164\u2800\u115f\u1160"
_INVISIBLE_TABLE: Final[dict[int, None]] = {ord(c): None for c in _INVISIBLE}
_LINE_BREAKS: Final[str] = "\n\r\x0b\x0c\x85\u2028\u2029"


def _norm(text: str) -> str:
    """比對用正規化：NFKC、去零寬、空白收斂、去頭尾（`group_window_text` 與 tile 窗口比對用）。"""
    t = unicodedata.normalize("NFKC", text).translate(_INVISIBLE_TABLE)
    return " ".join(t.split())


def _check_str(name: str, value: object, *, allow_glyph: bool = False) -> str:
    """非空（零寬字元視為空）、單行、不含狀態符號（除非 allow_glyph）的 str，否則 ValueError。"""
    if not isinstance(value, str):
        raise ValueError(f"{name} 必須是 str，收到 {type(value).__name__}：{value!r}")
    if not value.translate(_INVISIBLE_TABLE).strip():
        raise ValueError(f"{name} 不得為空字串（零寬／空白字元視為空）")
    if any(ch in value for ch in _LINE_BREAKS):
        raise ValueError(f"{name} 不得含換行：{value!r}")
    if not allow_glyph:
        for g in _state_glyphs():
            if g in value:
                raise ValueError(
                    f"{name} 不得自帶狀態符號 {g!r}（符號只能來自 UI_STATE_META，"
                    f"⛔ 同一狀態出現兩種符號）：{value!r}"
                )
    return value


def _check_int(name: str, value: object, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} 必須是 int，收到 {value!r}")
    if not lo <= value <= hi:
        raise ValueError(f"{name} 必須在 [{lo}, {hi}]，收到 {value}")
    return value


def _check_bool(name: str, value: object) -> bool:
    """旗標只收真正的 `True`／`False`（⛔ 不收 1／"yes"／None 等 truthy／falsy）。"""
    if value is not True and value is not False:
        raise ValueError(f"{name} 必須是 True 或 False，收到 {value!r}")
    return value


#: 防呆用私有 token：只有本模組內部能建 `SafeHtml`。
_SAFE_TOKEN: Final[object] = object()


class SafeHtml(str):
    """標記「由本模組產出、已 escape 的 HTML 片段」的 str 子類。

    `kpi_tile_html(spark=)`／`SmCell.svg` 只收 `SafeHtml`（解 `P1R-SPARK-TRUSTED-HTML`）；
    一般 str 一律 `ValueError`。

    - 建構需要本模組私有 token（`SafeHtml("<x>")` → `ValueError`）；**不在 `__all__`**；
      `placeholder` 是**唯讀**屬性（建構時決定；`placeholder=True` 表示 Missing placeholder，
      不含任何線／點）。
    - ⚠️ **這是防呆，不是 XSS 邊界**：Python 無法真正阻止同一行程內的程式取用私有 token。
      它擋的是「呼叫端不小心把未 escape 的外部字串當成受信任標記傳進來」；
      呼叫端只能傳 compact 內部（`sparkline_svg`）的產出，不得自行組 HTML。
    """

    __slots__ = ("_ph",)

    def __new__(cls, text: str, *, _token: object = None, _placeholder: bool = False) -> "SafeHtml":
        if _token is not _SAFE_TOKEN:
            raise ValueError("SafeHtml 只能由 compact 內部（sparkline_svg）產出，呼叫端不得自行建構")
        if not isinstance(text, str):
            raise ValueError(f"SafeHtml 內容必須是 str：{type(text).__name__}")
        obj = super().__new__(cls, text)
        object.__setattr__(obj, "_ph", bool(_placeholder))
        return obj

    @property
    def placeholder(self) -> bool:
        return self._ph

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("SafeHtml 不可變")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("SafeHtml 不可變")


def _check_safe_html(name: str, x: object) -> bool:
    """`SafeHtml` 的唯一驗證點（kpi_tile／small_multiples 共用）：必須 isinstance SafeHtml，且 `_ph`
    存在且為真正的 bool。回傳 placeholder。`str.__new__(SafeHtml, ..)` 偽造（沒有 `_ph`）→ ValueError。"""
    if not isinstance(x, SafeHtml):
        raise ValueError(f"{name} 只收 SafeHtml（由 sparkline_svg 產出）")
    try:
        ph = object.__getattribute__(x, "_ph")
    except AttributeError:
        raise ValueError(f"{name} 不是由 sparkline_svg 產出的 SafeHtml（缺 _ph；疑似偽造）") from None
    if ph is not True and ph is not False:
        raise ValueError(f"{name} 的 SafeHtml._ph 必須是 bool（疑似偽造）：{ph!r}")
    return ph


def _safe(markup_text: str, *, placeholder: bool = False) -> SafeHtml:
    return SafeHtml(markup_text, _token=_SAFE_TOKEN, _placeholder=placeholder)


# ══════════════════════════════════════════════════════════════════
# 1. 狀態標籤（讀 UI_STATE_META）
# ══════════════════════════════════════════════════════════════════
def _state_label(ui_state: str, n: int | None, m: int | None) -> tuple[str, str]:
    """`ui_state` → (glyph, 狀態字)；全部讀 `UI_STATE_META`。

    - 未知鍵 → ValueError。
    - `partial` 的「N／M 計入」需 n、m（0 ≤ n ≤ m，m ≥ 1）；其他態傳 n／m → ValueError。
    """
    if not isinstance(ui_state, str) or ui_state not in _ui_state.UI_STATE_META:
        raise ValueError(
            f"未知的 UI 狀態 {ui_state!r}；合法值：{sorted(_ui_state.UI_STATE_META)}"
        )
    name, glyph, _traffic = _ui_state.UI_STATE_META[ui_state]
    if ui_state == _ui_state.UI_PARTIAL:
        if n is None or m is None:
            raise ValueError("partial 態必須同時傳入 n 與 m（◧ N／M 計入）")
        _check_int("n", n, 0, 10**9)
        _check_int("m", m, 1, 10**9)
        if n > m:
            raise ValueError(f"partial 態 n 不得大於 m：n={n}, m={m}")
        name = name.replace("N／M", f"{n}／{m}")
        if f"{n}／{m}" not in name:  # pragma: no cover - L0 改字時 fail loud
            raise ValueError(f"UI_STATE_META[partial] 文字格式已變，無法代入 N／M：{name!r}")
    else:
        if n is not None or m is not None:
            raise ValueError(f"只有 partial 態可傳 n／m；收到 ui_state={ui_state!r}")
    return glyph, name


def _state_color(ui_state: str) -> str:
    """狀態 → 色族。紅只給 failed；degraded 琥珀；live 綠；其餘一律灰。"""
    if ui_state == _ui_state.UI_FAILED:
        return "red"
    if ui_state == _ui_state.UI_DEGRADED:
        return "amber"
    if ui_state == _ui_state.UI_LIVE:
        return "green"
    return "grey"


def _check_missing_state(ui_state: str) -> None:
    """Missing 槽不接受 `live`（🟢 運作中不是缺資料；畫在 Missing 槽＝說謊）。"""
    if ui_state == _ui_state.UI_LIVE:
        raise ValueError("Missing placeholder 不可用 live 態（🟢 運作中不是缺資料）")


# ══════════════════════════════════════════════════════════════════
# 2. metadata／status chips
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class MetaKindSpec:
    """契約 §6 表一列。`family`：info／status／guard／delegated。"""

    family: str
    tone: str | None
    mode: str            # fixed／value／optional_value／verbatim／delegated
    template: str | None
    rank: int            # 溢出時移出的優先序：小者保留（0 護欄 ＞ 1 狀態／揭露〔ai、pretax 同級〕＞ 2 asof ＞ 3 window ＞ 4 source ＞ 5 retrieved）；同 rank 依傳入順序，後者先移出
    fallback: str | None = None


#: chip 的「值」（呼叫端提供的那一段）字數上限（契約 §19 Q9）；逐字客戶句（verbatim）豁免。
CHIP_VALUE_MAX_CHARS: Final[int] = 12
#: 單一 chip 列的外露上限（契約 §4：3～5 顆）。
CHIPS_MAX: Final[int] = 5

_G, _S, _I, _D = "guard", "status", "info", "delegated"

#: 封閉集合：鍵集合必須與契約 §6 表 kind 欄逐一相等（含 `unavailable`；測試對帳）。
#: ⛔ 各頁不得自創 kind（`meta_chip` 未登記 kind → ValueError）。
META_KINDS: Final[Mapping[str, MetaKindSpec]] = MappingProxyType({
    "asof":         MetaKindSpec(_I, "info", "value", "🕒 資料 {v}", 2),
    "asof_missing": MetaKindSpec(_S, _ui_state.UI_IDLE, "fixed", "⬜ 資料日未提供", 1),
    "source":       MetaKindSpec(_I, "info", "value", "來源 {v}", 4),
    "retrieved_at": MetaKindSpec(_I, "info", "value", "抓取 {v}", 5),
    "window":       MetaKindSpec(_I, "info", "value", "{v}", 3),
    "readable":     MetaKindSpec(_S, _ui_state.UI_LIVE, "fixed", "✅ 可讀", 1),
    "stale":        MetaKindSpec(_S, _ui_state.UI_DEGRADED, "optional_value", "⚠ 過期 {v}", 1,
                                 fallback="⚠ 可能已過期"),
    "freshness":    MetaKindSpec(_S, _ui_state.UI_DEGRADED, "value", "⚠ {v}", 1),
    "coverage":     MetaKindSpec(_S, _ui_state.UI_PARTIAL, "value", "{v}", 1),
    # 委派：走 status_chip(ui_state)（沿用 UI_STATE_META 的 ⛔ 未接線），meta_chip 不自帶文字。
    "unavailable":  MetaKindSpec(_D, None, "delegated", None, 1),
    "not_defined":  MetaKindSpec(_G, "guard", "fixed", "⬜ 尚未定義", 0),
    "not_approved": MetaKindSpec(_G, "guard", "fixed", "⬜ 尚未核准／無法判定", 0),
    "estimated":    MetaKindSpec(_G, "guard", "fixed", "≈ 估算值", 0),
    "proxy":        MetaKindSpec(_G, "guard", "fixed", "≈ 代理值", 0),
    "imputed":      MetaKindSpec(_G, "guard", "fixed", "≈ 含補值", 0),
    "data_quality": MetaKindSpec(_G, "guard", "fixed", "⚠ 資料疑義", 0),
    "fx_partial":   MetaKindSpec(_G, "guard", "verbatim", None, 0),
    "fx_tp":        MetaKindSpec(_G, "guard", "verbatim", None, 0),
    "pretax":       MetaKindSpec(_I, "info", "fixed", "稅前", 1),     # F8：與狀態類同級（不先於資料日被擠出）
    "ai":           MetaKindSpec(_I, "info", "fixed", "🤖 AI 生成·非投資建議", 1),   # F8：同上
})

#: 非 META_KINDS 的兩種 Chip.kind：狀態 chip（`status_chip`）與逐字客戶護欄句（`guard_chip`）。
KIND_STATUS: Final[str] = "status"
KIND_GUARD_TEXT: Final[str] = "guard_text"
#: Top-N「另 K 筆見全部」chip（F10）：資訊族、不屬契約 §6 表的封閉集合 `META_KINDS`（故放 `_EXTRA_KINDS`），
#: 文字必須由 `TOPN_MORE_FMT` 推導（K≥1）；只經 `TopN.more_chip()` 產生。
KIND_TOPN_MORE: Final[str] = "topn_more"
_EXTRA_KINDS: Final[frozenset[str]] = frozenset({KIND_STATUS, KIND_GUARD_TEXT, KIND_TOPN_MORE})

#: 一個 chip 列內最多出現一次的 kind（契約 §6-5：同一 metadata 事實外露層最多一次）。
_SINGLETON_KINDS: Final[frozenset[str]] = frozenset(
    {"asof", "asof_missing", "source", "retrieved_at", "readable", "window", "topn_more"}
)


def _valid_tones() -> frozenset[str]:
    return frozenset({"info", "guard"}) | frozenset(_ui_state.UI_STATE_META)


def _state_of_status_text(text: str) -> tuple[str, int | None, int | None]:
    """狀態 chip 文字 → (UI 狀態鍵, n, m)；文字必須完全由 `UI_STATE_META` 推導，否則 ValueError。"""
    for key, (name, glyph, _traffic) in _ui_state.UI_STATE_META.items():
        full = f"{glyph} {name}"
        if key == _ui_state.UI_PARTIAL:
            pat = r"(\d+)／(\d+)".join(re.escape(part) for part in full.split("N／M"))
            mt = re.fullmatch(pat, text)
            if mt:
                n_s, m_s = mt.group(1), mt.group(2)
                n, m = int(n_s), int(m_s)
                if str(n) != n_s or str(m) != m_s or m < 1 or n > m:
                    raise ValueError(f"狀態 chip 的 N／M 不合法：{text!r}")
                return key, n, m
        elif text == full:
            return key, None, None
    raise ValueError(f"狀態 chip 文字 {text!r} 不是由 UI_STATE_META 推導的（⛔ 自造狀態字）")


#: stale／freshness 的值禁用的「可讀」符號（✅ 可讀 與 過期 互斥）。
_READABLE_SYMBOLS: Final[tuple[str, ...]] = ("✅", "✔", "☑", "✓", "可讀")


def _validate_chip_text(kind: str, text: str, tone: str) -> None:
    """固定文字 kind 的 text 必須等於模板；status 的 text 必須由 UI_STATE_META 推導（F2/L1）。"""
    if kind == KIND_STATUS:
        key, _n, _m = _state_of_status_text(text)
        if key != tone:
            raise ValueError(f"狀態 chip 的 tone {tone!r} 與文字推導的狀態 {key!r} 不符")
        return
    if kind == KIND_GUARD_TEXT:
        return                                     # 逐字客戶句：只驗非空單行（上面已驗）
    if kind == KIND_TOPN_MORE:
        mt = re.fullmatch(r"另 (\d+) 筆見全部", text, re.ASCII)
        if tone != "info" or not mt or str(int(mt.group(1))) != mt.group(1) or int(mt.group(1)) < 1:
            raise ValueError(f"topn_more chip 必須是 tone='info'、文字 {TOPN_MORE_FMT!r}（K≥1、無前導零）：{text!r}")
        return
    spec = META_KINDS[kind]
    if spec.tone is not None and tone != spec.tone:
        raise ValueError(f"kind {kind!r} 的 tone 必須是 {spec.tone!r}，收到 {tone!r}")
    if spec.mode == "fixed":
        if text != spec.template:
            raise ValueError(f"kind {kind!r} 是固定文字 {spec.template!r}，不得改寫：{text!r}")
    elif spec.mode == "verbatim":
        return                                     # 逐字句：任意非空單行
    else:                                          # value／optional_value
        if spec.mode == "optional_value" and text == spec.fallback:
            return
        tpl = spec.template or "{v}"
        prefix, _sep, suffix = tpl.partition("{v}")
        if not (text.startswith(prefix) and text.endswith(suffix)
                and len(text) > len(prefix) + len(suffix)):
            raise ValueError(f"kind {kind!r} 的文字必須符合模板 {tpl!r}：{text!r}")
        v = text[len(prefix):len(text) - len(suffix)] if suffix else text[len(prefix):]
        _check_str(f"{kind}.value", v)
        if len(v) > CHIP_VALUE_MAX_CHARS:
            raise ValueError(f"chip 值最多 {CHIP_VALUE_MAX_CHARS} 字：{kind}={v!r}")
        if kind in ("stale", "freshness"):
            for sym in _READABLE_SYMBOLS:
                if sym in v:
                    raise ValueError(f"{kind} 的值不得含可讀符號 {sym!r}（過期與可讀互斥）：{v!r}")
        if kind == "coverage":
            _check_coverage_value(v)


def _check_coverage_value(v: str) -> None:
    """coverage 的值只接受契約 §6 的兩種形式：(a)『N／M』或『N／M 項有資料』（半形數字、無前導零、
    M≥1、0≤N≤M）；(b)『N 項未評估』（N≥0、無前導零）。其餘 ValueError。"""
    mt = re.fullmatch(r"(\d+)／(\d+)( 項有資料)?", v, re.ASCII)
    if mt:
        n_s, m_s = mt.group(1), mt.group(2)
        n, m = int(n_s), int(m_s)
        if str(n) != n_s or str(m) != m_s or m < 1 or n > m:
            raise ValueError(f"coverage 的 N／M 不合法（需 0≤N≤M、M≥1、無前導零）：{v!r}")
        return
    mu = re.fullmatch(r"(\d+) 項未評估", v, re.ASCII)
    if mu:
        if str(int(mu.group(1))) != mu.group(1):
            raise ValueError(f"coverage 的『N 項未評估』N 不得有前導零：{v!r}")
        return
    raise ValueError(f"coverage 的值必須是『N／M』『N／M 項有資料』或『N 項未評估』（半形數字）：{v!r}")


def _validate_chip(kind: object, text: object, tone: object) -> None:
    """Chip 的唯一驗證點：建構（`__post_init__`）與輸出前（`_chip_span`／`_check_chip_seq`）共用，
    使 `object.__setattr__` 偽造的 Chip 在輸出前被擋下。"""
    for fname, val in (("kind", kind), ("text", text), ("tone", tone)):
        if not isinstance(val, str):
            raise ValueError(f"Chip.{fname} 必須是 str，收到 {type(val).__name__}：{val!r}")
    if kind in _EXTRA_KINDS:
        family = {KIND_STATUS: _S, KIND_GUARD_TEXT: _G, KIND_TOPN_MORE: _I}[kind]
    elif kind in META_KINDS:
        spec = META_KINDS[kind]
        if spec.family == _D:
            raise ValueError(f"kind {kind!r} 委派給 status_chip，不可直接建 Chip")
        family = spec.family
    else:
        raise ValueError(f"未登記的 chip kind {kind!r}（封閉集合，見 META_KINDS）")
    _check_str("Chip.text", text, allow_glyph=True)
    if tone not in _valid_tones():
        raise ValueError(f"Chip.tone {tone!r} 不合法；合法值：{sorted(_valid_tones())}")
    if family == _I and tone != "info":
        raise ValueError(f"資訊族 chip 的 tone 必須是 'info'：{kind}/{tone}")
    if family == _G and tone != "guard":
        raise ValueError(f"護欄族 chip 的 tone 必須是 'guard'：{kind}/{tone}")
    if family == _S and tone in ("info", "guard"):
        raise ValueError(f"狀態族 chip 的 tone 必須是 UI_STATE_META 鍵：{kind}/{tone}")
    # 紅（failed）只給 status failed：由上面的族別 tone 規則（資訊／護欄只能 info／guard）
    # ＋ `_validate_chip_text`（固定 kind 的 tone 必須等於模板 tone）共同保證，無需另寫一條。
    _validate_chip_text(kind, text, tone)


@dataclass(frozen=True)
class Chip:
    """一顆 chip。**無 `parts`、無合併**（D10=(a)：護欄各自獨立）。

    `tone`：`info`／`guard`，或 `UI_STATE_META` 十態鍵（只決定色族；不自訂第二套狀態詞彙）。

    **直接建構即驗證**（F2/L1，選擇「`__post_init__` 驗證」而非私有 token——驗證只讀
    `META_KINDS`／`UI_STATE_META`，不呼叫 `meta_chip`/`status_chip`，故無循環）：
    固定文字 kind 的 text 必須等於模板；status 的 text 必須由 `UI_STATE_META` 推導且 tone 與之相符；
    value kind 的 text 必須符合模板；stale／freshness 只能 degraded、readable 只能 live、
    紅（failed）只給 status failed；護欄 `guard_text` 不驗模板但須非空單行；
    tone／kind／text 非 str → ValueError（⛔ 不是 TypeError）。
    """

    kind: str
    text: str
    tone: str

    def __post_init__(self) -> None:
        _validate_chip(self.kind, self.text, self.tone)

    @property
    def family(self) -> str:
        if self.kind == KIND_STATUS:
            return _S
        if self.kind == KIND_GUARD_TEXT:
            return _G
        if self.kind == KIND_TOPN_MORE:
            return _I
        return META_KINDS[self.kind].family

    @property
    def rank(self) -> int:
        if self.kind == KIND_STATUS:
            return 1
        if self.kind == KIND_GUARD_TEXT:
            return 0
        if self.kind == KIND_TOPN_MORE:
            return 5
        return META_KINDS[self.kind].rank


def meta_chip(kind: str, value: str | None = None, *, verbatim: str | None = None) -> Chip:
    """建一顆 metadata chip（契約 §6 表）。

    - 未登記 kind／`unavailable`（委派給 `status_chip`）→ ValueError。
    - `value` 模式（asof／source／retrieved_at／window／freshness／coverage，stale 可選）：
      值必填、非空、單行、≤12 字、不得自帶狀態符號。
    - 固定文字 kind（readable／not_defined／…）：傳 value／verbatim → ValueError（不改寫固定字）。
    - `verbatim` kind（fx_partial／fx_tp）：逐字句必填、不截、不改寫（豁免字數上限）；
      `fx_partial` 可另傳 value 代表檔數 → 逐字句後接「（N 檔）」。
    """
    if not isinstance(kind, str) or kind not in META_KINDS:
        raise ValueError(f"未登記的 chip kind {kind!r}；合法值：{sorted(META_KINDS)}")
    spec = META_KINDS[kind]
    if spec.mode == "delegated":
        raise ValueError(f"kind {kind!r} 不自帶文字，請改用 status_chip(ui_state)")
    if spec.mode == "verbatim":
        text = _check_str(f"{kind}.verbatim", verbatim, allow_glyph=True)
        if value is not None:
            if kind != "fx_partial":
                raise ValueError(f"{kind} 不接受 value")
            v = _check_str(f"{kind}.value", value)
            text = f"{text}（{v} 檔）"
    else:
        if verbatim is not None:
            raise ValueError(f"kind {kind!r} 不接受 verbatim（只有 fx_partial／fx_tp 逐字）")
        if spec.mode == "fixed":
            if value is not None:
                raise ValueError(f"kind {kind!r} 是固定文字，不接受 value：{value!r}")
            text = spec.template or ""
        else:
            if value is None:
                if spec.mode == "optional_value":
                    text = spec.fallback or ""
                else:
                    raise ValueError(f"kind {kind!r} 需要 value")
            else:
                v = _check_str(f"{kind}.value", value)
                if len(v) > CHIP_VALUE_MAX_CHARS:
                    raise ValueError(
                        f"chip 值最多 {CHIP_VALUE_MAX_CHARS} 字（契約 Q9；超過改放摺疊）："
                        f"{kind}={v!r}（{len(v)} 字）"
                    )
                text = (spec.template or "{v}").format(v=v)
    assert spec.tone is not None
    return Chip(kind=kind, text=text, tone=spec.tone)


def guard_chip(sentence: str) -> Chip:
    """逐字客戶護欄句 chip（例 `_market_blocks.CHART_A_MA_DISCLAIMER`）。

    契約 §6／§4：客戶逐字句作 chip 時豁免字數上限、逐字不截、不改寫；屬護欄族（實線粗框）。
    ⛔ 與 `not_defined` 各自獨立成 chip，不合併（D10=(a)）。
    """
    return Chip(kind=KIND_GUARD_TEXT, text=_check_str("sentence", sentence, allow_glyph=True),
                tone="guard")


def status_chip(ui_state: str, *, n: int | None = None, m: int | None = None) -> Chip:
    """狀態 chip；icon＋字全部讀 `UI_STATE_META`（M3：與 BADGES 同源，⛔ 另造符號）。"""
    glyph, name = _state_label(ui_state, n, m)
    return Chip(kind=KIND_STATUS, text=f"{glyph} {name}", tone=ui_state)


def _chip_span(chip: Chip) -> str:
    if not isinstance(chip, Chip):
        raise ValueError(f"chip 必須是 Chip，收到 {type(chip).__name__}")
    _validate_chip(chip.kind, chip.text, chip.tone)      # 輸出前再驗（擋 object.__setattr__ 偽造）
    if chip.family == _I:
        cls = "cp-chip cp-info"
    elif chip.family == _G:
        cls = "cp-chip cp-guard"
    else:
        cls = f"cp-chip cp-status cp-t-{_state_color(chip.tone)}"
    return f'<span class="{cls}" data-kind="{_esc(chip.kind)}">{_esc(chip.text)}</span>'


def _check_chip_seq(chips: object) -> tuple[Chip, ...]:
    if isinstance(chips, (str, bytes)) or not isinstance(chips, (list, tuple)):
        raise ValueError(f"chips 必須是 list／tuple，收到 {type(chips).__name__}")
    for c in chips:
        if not isinstance(c, Chip):
            raise ValueError(f"chips 只收 Chip，收到 {type(c).__name__}：{c!r}")
        _validate_chip(c.kind, c.text, c.tone)            # 每顆再驗（擋 object.__setattr__ 偽造）
    seen: set[tuple[str, str]] = set()
    singles: set[str] = set()
    for c in chips:
        key = (c.kind, c.text)
        if key in seen:
            raise ValueError(f"重複的 chip：{c.kind}/{c.text!r}（同一事實最多外露一次）")
        seen.add(key)
        if c.kind in _SINGLETON_KINDS:
            if c.kind in singles:
                raise ValueError(f"chip 列內 {c.kind!r} 只能出現一次")
            singles.add(c.kind)
    if "asof" in singles and "asof_missing" in singles:
        raise ValueError("asof 與 asof_missing 不得同列（資料日有或沒有，二選一）")
    # F3：列內互斥——狀態語意不得自相矛盾
    non_readable_status = [c for c in chips if c.family == _S and c.kind != "readable"]
    if len(non_readable_status) > 1:
        raise ValueError(
            "同列最多一顆非 readable 的狀態類 chip（狀態語意互斥）："
            + "、".join(f"{c.kind}/{c.text}" for c in non_readable_status)
        )
    if "readable" in singles:
        for c in chips:
            if c.kind in ("stale", "freshness", "coverage") or (
                    c.kind == KIND_STATUS and c.tone != _ui_state.UI_LIVE):
                raise ValueError(
                    f"✅ 可讀 不得與 {c.kind}/{c.text!r} 同列（過期／部分／非運作中，不能同時可讀）"
                )
    return tuple(chips)


def chips_html(chips: Sequence[Chip], *, max_chips: int = CHIPS_MAX) -> tuple[str, tuple[Chip, ...]]:
    """chip 列 → `(html, 溢出 chip)`。

    超過 `max_chips` 時，**依優先序由低往高移出**（retrieved_at ＞ source ＞ window ＞ asof ＞ 狀態；
    護欄最後才動，且護欄本身超過上限 → ValueError，⛔ 不靜默丟、⛔ 不合併）。
    溢出者原序回傳，供呼叫端交給摺疊「來源」段；外露者保持呼叫端給的相對順序。
    """
    _check_int("max_chips", max_chips, 1, CHIPS_MAX)
    items = _check_chip_seq(chips)
    guards = [c for c in items if c.rank == 0]
    if len(guards) > max_chips:
        raise ValueError(
            f"護欄 chip {len(guards)} 顆超過外露上限 {max_chips}（⛔ 不靜默丟、⛔ 不合併）"
        )
    if len(items) <= max_chips:
        kept_idx = set(range(len(items)))
    else:
        order = sorted(range(len(items)), key=lambda i: (items[i].rank, i))
        kept_idx = set(order[:max_chips])
    shown = [items[i] for i in range(len(items)) if i in kept_idx]
    overflow = tuple(items[i] for i in range(len(items)) if i not in kept_idx)
    if not shown:
        return "", overflow
    html = '<div class="cp-chips">' + "".join(_chip_span(c) for c in shown) + "</div>"
    return html, overflow


# ══════════════════════════════════════════════════════════════════
# 3. chart header
# ══════════════════════════════════════════════════════════════════
#: 契約 §19 Q8：1 句 ≤ 32 字（客戶原句豁免）。
SAY_MAX_CHARS: Final[int] = 32
#: chart header 標題字數上限（客戶逐字標題走 `title_verbatim=True`）。
TITLE_MAX_CHARS: Final[int] = 40


def chart_header_html(*, title: str, chips: Sequence[Chip], say: str | None,
                      max_chips: int = CHIPS_MAX,
                      say_verbatim: bool = False,
                      title_verbatim: bool = False) -> tuple[str, tuple[Chip, ...]]:
    """主圖 header：標題 → chip 列 → 1 句（契約 §4，順序固定；圖與摺疊入口由呼叫端接在後面）。

    回傳 `(html, 溢出 chip)`；溢出 chip 交給 `render_fold` 的「來源」段。
    `say` 非客戶原句時 ≤32 字（`say_verbatim=True` 豁免、逐字不截）；不得含換行。
    標題 ≤40 字（客戶逐字標題傳 `title_verbatim=True` 豁免）。
    ⚠️ **chip 下限由呼叫端負責**：契約 §4／線框 §3.2 要求圖 header 外露 3～5 顆 chip，本函式只擋上限
    （溢出回傳）；chip 太少（含 0 顆）**不會**報錯——呼叫端須自行確保至少有資料日／狀態類 chip。
    **唯一合法例外＝冷啟動**：尚未載入時線框 §3.2 本來就只畫 2 顆（護欄＋狀態），2 顆是合法的；
    除冷啟動外少於 3 顆＝呼叫端缺 chip（例如漏了資料日）。本函式不自判是否冷啟動。
    """
    say_verbatim = _check_bool("say_verbatim", say_verbatim)
    title_verbatim = _check_bool("title_verbatim", title_verbatim)
    t = _check_str("title", title, allow_glyph=True)
    if not title_verbatim and len(t) > TITLE_MAX_CHARS:
        raise ValueError(f"標題最多 {TITLE_MAX_CHARS} 字（客戶逐字標題請傳 title_verbatim=True）：{len(t)} 字")
    parts = [f'<div class="cp-ch-title">{_esc(t)}</div>']
    chips_part, overflow = chips_html(chips, max_chips=max_chips)
    if chips_part:
        parts.append(chips_part)
    if say is not None:
        s = _check_str("say", say, allow_glyph=True)
        if not say_verbatim and len(s) > SAY_MAX_CHARS:
            raise ValueError(f"1 句最多 {SAY_MAX_CHARS} 字（客戶原句請傳 say_verbatim=True）：{len(s)} 字")
        parts.append(f'<div class="cp-ch-say">{_esc(s)}</div>')
    return '<div class="cp-chart-header">' + "".join(parts) + "</div>", overflow


# ══════════════════════════════════════════════════════════════════
# 4. Missing placeholder
# ══════════════════════════════════════════════════════════════════
#: 契約 §19 Q3：Primary 圖槽桌機高上限（手機 140px 由 CSS 夾）。
SLOT_HEIGHT_MAX_PX: Final[int] = 220
#: Primary 圖槽高度下限（契約 §19 Q1 的最小區塊感；低於此值放不下 Missing 原因文字）。
SLOT_HEIGHT_MIN_PX: Final[int] = 96


def _missing_text(ui_state: str, reason: str, n: int | None = None, m: int | None = None) -> str:
    _check_missing_state(ui_state)
    glyph, name = _state_label(ui_state, n, m)
    r = _check_str("reason", reason)
    return f"{glyph} {name}：{r}"


def chart_slot_missing_html(ui_state: str, reason: str, *, height_px: int | None = None,
                            variant: str = "primary", n: int | None = None,
                            m: int | None = None) -> str:
    """圖槽 Missing placeholder（契約 §8；D6=B）。

    - `variant="primary"`：保留正式高度（`height_px` 必填，96～220；手機由 CSS 夾到 140px）。
    - `variant="secondary"`：縮成一行（`height_px` 必須是 None）；⛔ 不隱藏 Missing。
    - 符號與狀態字讀 `UI_STATE_META`；`reason` 必填、不得自帶狀態符號；`live` 態與未知態 → ValueError。
    - ⛔ 不畫任何線／點／軸／格線；只有 `failed` 用紅。
    """
    if variant not in ("primary", "secondary"):
        raise ValueError(f"variant 只能是 'primary' 或 'secondary'：{variant!r}")
    text = _missing_text(ui_state, reason, n, m)
    color = "red" if ui_state == _ui_state.UI_FAILED else "grey"
    role = "alert" if ui_state == _ui_state.UI_FAILED else "status"
    if variant == "secondary":
        if height_px is not None:
            raise ValueError("secondary 縮成一行，不接受 height_px")
        return (f'<div class="cp-slot cp-slot-line cp-s-{color}" role="{role}" '
                f'data-state="{_esc(ui_state)}">{_esc(text)}</div>')
    if height_px is None:
        raise ValueError("primary 圖槽必須指定 height_px（保留正式高度）")
    h = _check_int("height_px", height_px, SLOT_HEIGHT_MIN_PX, SLOT_HEIGHT_MAX_PX)
    return (f'<div class="cp-slot cp-slot-primary cp-s-{color}" role="{role}" '
            f'data-state="{_esc(ui_state)}" style="--cp-slot-h:{h}px">'
            f'<span>{_esc(text)}</span></div>')


# ══════════════════════════════════════════════════════════════════
# 5. compact KPI tile
# ══════════════════════════════════════════════════════════════════
#: 契約 §19：Q6 卡面 ≤60 字、Q7 主值 ≤12 字。
TILE_FACE_MAX_CHARS: Final[int] = 60
TILE_VALUE_MAX_CHARS: Final[int] = 12
TILE_CHIPS_MAX: Final[int] = 2
#: 這些 kind 寫在最近的共同容器（頁級／組級 chip 列），tile 內傳入即 ValueError（契約 §6-5）。
_TILE_FORBIDDEN_KINDS: Final[frozenset[str]] = frozenset(
    {"asof", "asof_missing", "source", "retrieved_at", "readable"}
)
#: 主值不得是占位字樣（L3）。⚠️ `"0"` **不在其中**：0 可以是真值——是否該顯示 0 由呼叫端負責
#: （「沒資料」必須傳 `value=None` 並帶說明原因的 chip，⛔ 不得用 "0" 充數）。
_PLACEHOLDER_VALUES: Final[frozenset[str]] = frozenset({
    "n/a", "na", "nan", "none", "null", "nil", "undefined", "unknown", "tbd", "?", "？",
    "暫無", "無資料", "無", "尚無", "暫無資料", "尚無資料", "沒有資料", "無數據", "暫無數據", "待補", "缺",
})
_PLACEHOLDER_STRIP = re.compile(r"[\s.．·・。…]+")
_DASH_ONLY = re.compile(r"[\s\-–—―−－ー_=.．·・*＊?？%％]*")


def _check_tile_value(value: object) -> str:
    v = _check_str("value", value, allow_glyph=True)
    if len(v) > TILE_VALUE_MAX_CHARS:
        raise ValueError(f"主值最多 {TILE_VALUE_MAX_CHARS} 字（超過改 chip）：{len(v)} 字")
    norm = _PLACEHOLDER_STRIP.sub("", _norm(v))          # 去空白與點號後再比（"N. A."、"暫 無"）
    if _DASH_ONLY.fullmatch(norm) or norm.casefold() in _PLACEHOLDER_VALUES:
        raise ValueError(
            f"主值不得是占位字樣 {v!r}（沒資料請傳 value=None 並帶說明原因的 chip；⛔ 沉默的假值）"
        )
    return v


def kpi_tile_html(*, label: str, value: str | None, chips: Sequence[Chip] = (),
                  say: str | None = None, spark: SafeHtml | None = None,
                  state_badge_n: int | None = None, group_window_text: str | None = None,
                  say_verbatim: bool = False) -> str:
    """compact KPI tile（線框 §3.5）。

    - `value=None`＝主值槽留白（⛔ 不補 0／—％／中性字）；留白時 chips 必須至少含一顆
      「狀態族（非 live）／護欄族／stale 類」說明原因的 chip（窗口 chip 不算），否則 ValueError。
    - 主值拒絕占位字樣（「—」「-」「—％」「N/A」「nan」「None」「null」…）；**`"0"` 保留**——
      0 可為真值，是否為真值由呼叫端負責（沒資料請用 `value=None`）。
    - 資料日／來源／抓取時間／可讀不在 tile 內（寫在組級 chip 列）；傳入 → ValueError。
    - chip 合計 ≤2（≤1 窗口＋≤1 狀態／護欄）；窗口與 `group_window_text` 相同 → ValueError。
    - `value=None` 且 `spark` 是 placeholder → ValueError（F3：說明原因的 chip 已外露一次，
      placeholder 會再說一次；冷啟動請不要傳 spark）。
    - 有 `spark` 時必須有可見窗口：tile 內窗口 chip，或 `group_window_text`（組級已外露的窗口）。
    - `spark` 只收 `SafeHtml`；主值 ≤12 字；卡面可見字（標籤＋主值＋chip＋1 句）≤60，
      客戶原句（`say_verbatim=True`）另計。
    """
    say_verbatim = _check_bool("say_verbatim", say_verbatim)
    lab = _check_str("label", label, allow_glyph=True)
    val: str | None = None
    if value is not None:
        val = _check_tile_value(value)
    items = _check_chip_seq(chips)
    if len(items) > TILE_CHIPS_MAX:
        raise ValueError(f"tile 內 chip 最多 {TILE_CHIPS_MAX} 顆（≤1 窗口＋≤1 狀態／護欄）：{len(items)}")
    windows = [c for c in items if c.kind == "window"]
    others = [c for c in items if c.kind != "window"]
    if len(windows) > 1 or len(others) > 1:
        raise ValueError("tile 內 chip：≤1 顆窗口、≤1 顆狀態／護欄")
    for c in items:
        if c.kind in _TILE_FORBIDDEN_KINDS:
            raise ValueError(
                f"{c.kind} 不得出現在 tile 內（同一事實外露層最多一次，請放組級 chip 列）"
            )
    if group_window_text is not None:
        _check_str("group_window_text", group_window_text, allow_glyph=True)
        if windows and _norm(windows[0].text) == _norm(group_window_text):
            raise ValueError("tile 窗口與組級窗口相同，請只放組級（不得重複外露）")
    if val is None and not any(
            c.family == _G or (c.family == _S and c.kind != "readable" and c.tone != _ui_state.UI_LIVE)
            for c in items
    ):
        raise ValueError(
            "主值留白時 chips 必須至少含一顆說明原因的狀態類（非 live）／護欄類／stale chip（⛔ 沉默的空槽）"
        )
    s: str | None = None
    if say is not None:
        s = _check_str("say", say, allow_glyph=True)
    if spark is not None:
        spark_ph = _check_safe_html("spark", spark)
        if val is None and spark_ph:
            raise ValueError(
                "主值留白（冷啟動）時不得帶 placeholder sparkline：原因 chip 已說明一次，"
                "placeholder 會讓『尚未載入』在同一 tile 外露兩次（契約 §6-5）；請不要傳 spark"
            )
        if not spark_ph and not windows and group_window_text is None:
            raise ValueError("有 sparkline 的 tile 必須有可見窗口 chip（tile 內或組級）")
    face = len(lab) + len(val or "") + sum(len(c.text) for c in items)
    if s is not None and not say_verbatim:
        face += len(s)
    if face > TILE_FACE_MAX_CHARS:
        raise ValueError(f"tile 卡面可見字最多 {TILE_FACE_MAX_CHARS}（客戶原句另計）：{face} 字")

    parts = [f'<div class="cp-tile-label">{_esc(lab)}</div>']
    if val is None:
        parts.append('<div class="cp-tile-value cp-blank"></div>')
    else:
        parts.append(f'<div class="cp-tile-value">{_esc(val)}</div>')
    if state_badge_n is not None:
        _check_int("state_badge_n", state_badge_n, 1, len(components.BADGES))
        parts.append(f'<div class="cp-tile-badge">{markup.badge_html(state_badge_n)}</div>')
    if items:
        parts.append('<div class="cp-chips">' + "".join(_chip_span(c) for c in items) + "</div>")
    if s is not None:
        parts.append(f'<div class="cp-tile-say">{_esc(s)}</div>')
    if spark is not None:
        parts.append(f'<div class="cp-tile-spark">{spark}</div>')
    return '<div class="cp-tile">' + "".join(parts) + "</div>"


# ══════════════════════════════════════════════════════════════════
# 6. sparkline
# ══════════════════════════════════════════════════════════════════
SPARK_HEIGHT_MAX_PX: Final[int] = 64   # 契約 §19 Q5
_SPARK_PAD: Final[float] = 2.0


def _spark_points(values: object) -> list[float | None]:
    """逐點檢查：None／NaN → 缺口；非實數、bool、±inf → ValueError。"""
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        raise ValueError(f"values 必須是 list／tuple（保留原索引），收到 {type(values).__name__}")
    out: list[float | None] = []
    for i, v in enumerate(values):
        if v is None:
            out.append(None)
            continue
        if isinstance(v, bool) or not isinstance(v, numbers.Real):
            raise ValueError(f"values[{i}] 不是實數：{v!r}")
        try:
            f = float(v)
        except OverflowError:
            raise ValueError(f"values[{i}] 數值過大，無法轉為有限浮點：{type(v).__name__}") from None
        if math.isnan(f):
            out.append(None)
        elif math.isinf(f):
            raise ValueError(f"values[{i}] 是非有限數：{v!r}")
        else:
            out.append(f)
    return out


def sparkline_svg(values: Sequence[float | None], *, w: int = 100, h: int = 48, title: str,
                  missing_state: str, missing_text: str) -> SafeHtml:
    """內嵌 SVG sparkline（線框 §3.6）。

    - None／NaN **不補 0、不插值、不跨缺口連線**；x 位置保留原索引（缺口佔掉它的水平空間）。
    - 連續有效點成一段 `<polyline>`；孤立單點畫 `<circle>`；**有效點 <2 → placeholder**（不畫線也不畫點）。
    - 單色中性線；⛔ 不顯示最新／最高／最低數字（D5=A）；無軸無圖例；`<title>` 供讀屏，不算外露。
    - `missing_state`（UI_STATE_META 鍵）與 `missing_text` 必填（即使這次畫得出來），元件不自判未載入或無資料。
    - ⚠️ **掛頁**：回傳的行內 `<svg>` **不可經 `st.html`**（Streamlit 1.56.0 會把行內 svg 整段剝除，
      畫面上只剩文字、不報錯）；請用 `st.markdown(unsafe_allow_html=True)`，或改包成 data-URI `<img>`
      （兩者在 1.56.0 實測保留；`docs/vnext/PHASE3_D8_FLOOR156_VERIFICATION_2026-10-30.md` §3.3）。
      placeholder（`<span>`）不受影響，但為一致建議走同一條路徑。
    - 孤立點畫 `r=2.5` 的實心圓（F5：1.5 在 100×48 上近乎看不見；2.2 → 2.5 為 QA 看圖後加大）。
    - `<polyline>` 帶 `vector-effect="non-scaling-stroke"`：SVG 被 CSS 縮放（小倍數 `width:100%`）時線寬不隨之變化。
    """
    _check_int("w", w, 20, 600)
    _check_int("h", h, 8, SPARK_HEIGHT_MAX_PX)
    ttl = _check_str("title", title, allow_glyph=True)
    if missing_state == _ui_state.UI_PARTIAL:
        raise ValueError("sparkline placeholder 不支援 partial 態（需 N／M）")
    placeholder_text = _missing_text(missing_state, missing_text)   # 先驗，再看要不要用
    pts = _spark_points(values)
    valid = [(i, v) for i, v in enumerate(pts) if v is not None]
    if len(valid) < 2:
        return _safe(
            f'<span class="cp-spark cp-spark-missing" role="img" aria-label="{_esc(ttl)}" '
            f'style="width:100%;max-width:{w}px;min-height:{h}px">{_esc(placeholder_text)}</span>',
            placeholder=True,
        )
    n = len(pts)
    lo = min(v for _, v in valid)
    hi = max(v for _, v in valid)
    if not math.isfinite(hi - lo):
        raise ValueError(f"sparkline 值域 hi−lo 非有限（{lo!r}～{hi!r}）：數值太極端，無法縮放")
    span_x = w - 2 * _SPARK_PAD
    span_y = h - 2 * _SPARK_PAD

    def xy(i: int, v: float) -> tuple[float, float]:
        x = _SPARK_PAD + i * span_x / (n - 1)
        y = h / 2 if hi == lo else _SPARK_PAD + (1 - (v - lo) / (hi - lo)) * span_y
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"sparkline 縮放結果非有限：values[{i}]={v!r}")
        return x, y

    runs: list[list[tuple[int, float]]] = []
    prev = -2
    for i, v in valid:
        if i == prev + 1 and runs:
            runs[-1].append((i, v))
        else:
            runs.append([(i, v)])
        prev = i
    shapes: list[str] = []
    for run in runs:
        if len(run) == 1:
            x, y = xy(*run[0])
            shapes.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.5"/>')
        else:
            coords = " ".join("{:.2f},{:.2f}".format(*xy(i, v)) for i, v in run)
            shapes.append(f'<polyline fill="none" vector-effect="non-scaling-stroke" points="{coords}"/>')
    return _safe(
        f'<svg class="cp-spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
        f'aria-label="{_esc(ttl)}"><title>{_esc(ttl)}</title>{"".join(shapes)}</svg>'
    )


# ══════════════════════════════════════════════════════════════════
# 7. small multiples
# ══════════════════════════════════════════════════════════════════
SM_NAME_MAX_CHARS: Final[int] = 8   # 線框 §3.7：系列名 ≤8 字


@dataclass(frozen=True)
class SmCell:
    """一格。`svg` 有值＝畫圖（不得同時給 missing_*）；`svg=None`＝缺系列 placeholder（missing_* 必填）。

    `window_chip` 只在該格窗口與組級不同時才給（kind 必須是 window）；格內不放資料日。
    """

    name: str
    svg: SafeHtml | None = None
    window_chip: Chip | None = None
    missing_state: str | None = None
    missing_text: str | None = None


def small_multiples_html(cells: Sequence[SmCell], *, cols_desktop: int = 3, cols_mobile: int = 2) -> str:
    """小倍數版面（HTML／CSS grid；每格各自座標，⛔ 疊軸、⛔ 正規化、⛔ 顯示數字）。"""
    _check_int("cols_desktop", cols_desktop, 1, components.MAX_COLS)
    _check_int("cols_mobile", cols_mobile, 1, 2)
    if cols_mobile > cols_desktop:
        raise ValueError(f"cols_mobile 不得大於 cols_desktop：{cols_mobile} > {cols_desktop}")
    if isinstance(cells, (str, bytes)) or not isinstance(cells, (list, tuple)) or not cells:
        raise ValueError("cells 必須是非空 list／tuple")
    out: list[str] = []
    seen_names: set[str] = set()
    for c in cells:
        if not isinstance(c, SmCell):
            raise ValueError(f"cells 只收 SmCell，收到 {type(c).__name__}")
        name = _check_str("SmCell.name", c.name, allow_glyph=True)
        if _norm(name) in seen_names:
            raise ValueError(f"小倍數系列名重複：{name!r}（兩格同名＝讀者無法分辨）")
        seen_names.add(_norm(name))
        if len(name) > SM_NAME_MAX_CHARS:
            raise ValueError(f"系列名最多 {SM_NAME_MAX_CHARS} 字：{name!r}")
        if c.svg is not None:
            _check_safe_html("SmCell.svg", c.svg)
            if c.missing_state is not None or c.missing_text is not None:
                raise ValueError("有 svg 的格不得同時給 missing_state／missing_text")
            body = str(c.svg)
        else:
            if c.missing_state is None or c.missing_text is None:
                raise ValueError("缺系列的格必須給 missing_state 與 missing_text（⛔ 不隱藏 Missing）")
            if c.missing_state == _ui_state.UI_PARTIAL:
                raise ValueError("小倍數 placeholder 不支援 partial 態（需 N／M）")
            body = f'<div class="cp-sm-missing">{_esc(_missing_text(c.missing_state, c.missing_text))}</div>'
        chip_html = ""
        if c.window_chip is not None:
            if not isinstance(c.window_chip, Chip) or c.window_chip.kind != "window":
                raise ValueError("SmCell.window_chip 必須是 kind='window' 的 Chip")
            chip_html = _chip_span(c.window_chip)
        out.append(f'<div class="cp-sm-cell"><div class="cp-sm-name">{_esc(name)}</div>{body}{chip_html}</div>')
    return (f'<div class="cp-sm cp-sm-d{cols_desktop}-m{cols_mobile}">' + "".join(out) + "</div>")


# ══════════════════════════════════════════════════════════════════
# 8. Top-N 切片（純顯示切片）
# ══════════════════════════════════════════════════════════════════
#: 契約 §10 R9-4 的字樣（只提供格式常數；渲染由呼叫端，⛔ 不新增 chip kind）。
TOPN_MORE_FMT: Final[str] = "另 {k} 筆見全部"
TOPN_ALL_LABEL_FMT: Final[str] = "▸ 查看全部（{n} 筆）"


@dataclass(frozen=True)
class TopN(Generic[T]):
    shown: tuple[T, ...]
    hidden: int
    total: int

    def __post_init__(self) -> None:
        if not isinstance(self.shown, tuple):
            raise ValueError(f"TopN.shown 必須是 tuple：{type(self.shown).__name__}")
        _check_int("TopN.hidden", self.hidden, 0, 10**9)
        _check_int("TopN.total", self.total, 0, 10**9)
        if len(self.shown) + self.hidden != self.total:
            raise ValueError(
                f"TopN 不一致：shown {len(self.shown)} ＋ hidden {self.hidden} ≠ total {self.total}"
            )

    @property
    def empty(self) -> bool:
        """`total == 0`：來源清單本身是空的。⚠️ 空清單**不是**「0 筆結果」——呼叫端必須另外
        把它當 Missing（用 `chart_slot_missing_html`／清單槽 placeholder 說明原因），
        不得拿空的 `shown` 畫一張沒有任何列的表。"""
        return self.total == 0

    @property
    def more_text(self) -> str | None:
        return TOPN_MORE_FMT.format(k=self.hidden) if self.hidden > 0 else None

    def more_chip(self) -> Chip:
        """「另 K 筆見全部」chip（F10）：資訊族（細外框）、文字＝`TOPN_MORE_FMT`，kind=`topn_more`
        （不在 `META_KINDS` 封閉集合內，僅此處產生）。可進 `chips_html`／`_check_chip_seq` 的去重檢查
        （同列最多一顆）。`hidden == 0` 時沒有「另 K 筆」可說 → ValueError（⛔ 不回傳 K=0 的假 chip；
        呼叫端先看 `more_text is not None`）。"""
        if self.hidden <= 0:
            raise ValueError("TopN 沒有被隱藏的筆數（hidden=0），不產生『另 K 筆』chip")
        return Chip(kind=KIND_TOPN_MORE, text=TOPN_MORE_FMT.format(k=self.hidden), tone="info")

    @property
    def all_label(self) -> str | None:
        return TOPN_ALL_LABEL_FMT.format(n=self.total) if self.hidden > 0 else None


def topn_view(rows: Sequence[T], n: int) -> TopN[T]:
    """只取前 n 筆：保序、保物件同一性（`shown[i] is rows[i]`）；⛔ 改排序／篩選／重算。

    `rows` 必須是 list／tuple（generator 會被消耗，`total` 不準 → ValueError）；`n` 必須是 >0 的 int。
    ⚠️ **空清單不報錯**，回傳 `TopN.empty == True`：呼叫端**必須**另行處理為 Missing
    （說明為什麼沒有資料），⛔ 不得把空 `shown` 當成「已載入、0 筆」。
    """
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ValueError(f"n 必須是 >0 的 int，收到 {n!r}")
    if isinstance(rows, (str, bytes)) or not isinstance(rows, (list, tuple)):
        raise ValueError(f"rows 必須是 list／tuple（generator 會被消耗），收到 {type(rows).__name__}")
    shown = tuple(rows[:n])
    return TopN(shown=shown, hidden=len(rows) - len(shown), total=len(rows))


# ══════════════════════════════════════════════════════════════════
# 9. segmented 選項（純資料；widget 呼叫在後續步驟，⛔ 本檔不碰 streamlit）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SegmentSpec:
    options: tuple[str, ...]
    default: str

    def __post_init__(self) -> None:
        if not isinstance(self.options, tuple) or not self.options:
            raise ValueError("SegmentSpec.options 必須是非空 tuple")
        norm: set[str] = set()
        for i, o in enumerate(self.options):
            _check_str(f"options[{i}]", o, allow_glyph=True)
            if _norm(o) in norm:
                raise ValueError(f"SegmentSpec.options 有重複項：{o!r}")
            norm.add(_norm(o))
        if not isinstance(self.default, str) or self.default not in self.options:
            raise ValueError(f"default {self.default!r} 不在 options {list(self.options)} 內")

    @property
    def default_index(self) -> int:
        return self.options.index(self.default)


def segment_options(options: Sequence[str], default: str) -> SegmentSpec:
    """標準化 switcher 選項：去重（保第一次出現的位置）、保序、空字串報錯；預設必須在選項內。

    本函式**只回傳資料**（⛔ 不碰 streamlit）。日後掛 `st.segmented_control`（D8=B，floor 1.56.0 已驗，
    `docs/vnext/PHASE3_D8_FLOOR156_VERIFICATION_2026-10-30.md` §4）的呼叫端必須遵守 5 條硬性約束：

    1. **取消選取回退**：單選下點已選項會回 `None`（即使有 `default=`）；`None` 不得外洩到下游——
       首選 `on_change` 回呼把 key 寫回 `last_valid`；次選 `eff = v if v is not None else last_valid`。
       `last_valid` 只能是使用者上一次真實選擇或 `default`，⛔ 不得自編值。
    2. **form 內**：點選項不 rerun，值在 submit 才送出；submit 分支同樣要把 `None` 視同缺值
       （`None → 上次已套用值 ?? default`）；form 內 `on_change` 不即時觸發。
    3. **點擊尺寸**：預設 32px（<44px）；要 ≥44px 須用 CSS 覆寫（依賴內部 `data-testid`，失效退化為 32px），
       否則交付報告須揭露。
    4. **換行**：選項多／字長會換行（不橫捲、不裁切）；form 內 390 寬 5 顆×3 字會換 2 列（孤立第 5 顆）；
       設計稿須畫換行態。
    5. **避免 tuple options 與雙重指定**：⛔ 不用 tuple 當選項值（`default=<tuple>` 會 raise）；
       key 播種與 `default=` **二選一**；同 key 但 options 變動時選取值不在新 options 會靜默回 default。
    """
    if isinstance(options, (str, bytes)) or not isinstance(options, (list, tuple)):
        raise ValueError(f"options 必須是 list／tuple，收到 {type(options).__name__}")
    seen: list[str] = []
    for i, o in enumerate(options):
        _check_str(f"options[{i}]", o, allow_glyph=True)
        if o not in seen:
            seen.append(o)
    if not seen:
        raise ValueError("options 不得為空")
    if not isinstance(default, str) or default not in seen:
        raise ValueError(f"default {default!r} 不在 options {seen} 內（⛔ 預設被取消後無結果）")
    return SegmentSpec(options=tuple(seen), default=default)


# ══════════════════════════════════════════════════════════════════
# 10. compact_css（與 markup.page_css 分開；不被任何既有頁注入）
# ══════════════════════════════════════════════════════════════════
def compact_css() -> str:
    """元件樣式表（不含 `<style>`）。顏色引用 `page_css()` 已宣告的 token（--sig-*、--rule-2、--ink*），
    故掛頁時須與 `page_css(mode)` 一起注入；幾何 token 由本函式自己宣告到 `:root`。

    - 護欄＝**實線**粗框（D3=A；⛔ 虛線）；資訊＝細外框；狀態＝淡底。
    - 紅只用於 failed（`.cp-t-red`、`.cp-s-red`）；stale 為 `.cp-t-amber`。
    """
    geo = "".join(f"{k}:{v};" for k, v in tokens.COMPACT_GEOMETRY.items())
    mobile = components.BREAKPOINTS["mobile_max_px"]
    rules = [
        f":root{{{geo}}}",
        ".cp-chips{display:flex;flex-wrap:wrap;gap:var(--sp-2);margin:var(--sp-2) 0}",
        ".cp-chip{display:inline-flex;align-items:center;box-sizing:border-box;"
        "min-height:var(--cp-chip-h);padding:var(--cp-chip-pad-v) var(--cp-chip-pad-h);"
        "border-radius:var(--cp-chip-radius);font-size:var(--cp-chip-fs);line-height:1.3;"
        "max-width:100%;overflow-wrap:anywhere}",
        # F6：邊框改引既有 --ink-3（對 --panel：dark 4.97／light 5.34，≥3:1；--rule-2 僅 2.18／2.51）
        ".cp-info{border:1px solid var(--ink-3);color:var(--ink-2);background:transparent}",
        ".cp-status{border:1px solid transparent;color:var(--ink)}",
        ".cp-t-green{background:var(--sig-green-bg);color:var(--sig-green)}",
        ".cp-t-amber{background:var(--sig-amber-bg);color:var(--sig-amber)}",
        ".cp-t-red{background:var(--sig-red-bg);color:var(--sig-red)}",
        ".cp-t-grey{background:var(--sig-grey-bg);color:var(--sig-grey)}",
        ".cp-guard{border:2px solid var(--ink-2);color:var(--ink);background:transparent;font-weight:600}",
        ".cp-ch-title{font-size:var(--sp-6);font-weight:600;color:var(--ink);margin:0 0 var(--sp-2)}",
        ".cp-ch-say{color:var(--ink-2);margin:var(--sp-2) 0}",
        ".cp-slot{box-sizing:border-box;display:flex;align-items:center;justify-content:center;"
        "text-align:center;overflow-wrap:anywhere}",
        ".cp-slot-primary{height:var(--cp-slot-h);border:1px solid var(--rule)}",
        ".cp-slot-line{min-height:32px;padding:var(--sp-2) var(--sp-3);justify-content:flex-start}",
        ".cp-s-grey{color:var(--sig-grey)}",
        ".cp-s-red{color:var(--sig-red)}",
        ".cp-tile{box-sizing:border-box;min-height:var(--cp-tile-min-h);"
        "padding:var(--cp-tile-pad-v) var(--cp-tile-pad-h);border:1px solid var(--rule);"
        "border-radius:var(--cp-tile-radius);background:var(--panel);"
        # F2：flex column，使宿主格網 align-items:stretch 時同列等高、spark 貼底（DOM 結構不變）
        "display:flex;flex-direction:column}",
        ".cp-tile-label{font-size:13px;color:var(--ink-2)}",
        # F4：平衡折行，避免孤字
        ".cp-tile-value{font-size:20px;color:var(--ink);overflow-wrap:anywhere;text-wrap:balance}",
        ".cp-tile-value.cp-blank{min-height:24px}",
        ".cp-tile-say{font-size:12px;color:var(--ink-2);margin-top:var(--sp-2)}",
        ".cp-tile-spark{margin-top:auto;padding-top:var(--sp-2)}",
        ".cp-spark{display:block;max-height:var(--cp-spark-h);color:var(--ink-2)}",
        ".cp-spark polyline{stroke:currentColor;stroke-width:1.5;fill:none;vector-effect:non-scaling-stroke}",
        ".cp-spark circle{fill:currentColor}",
        # M2/F5：⛔ 不裁字——Missing 原因文字必須完整可見：不設 overflow:hidden；
        # 高度只給 min-height（可長）、寬度 100% 上限 max-width（可縮），文字自動換行。
        ".cp-spark-missing{display:flex;align-items:center;box-sizing:border-box;"
        "max-height:none;font-size:11px;color:var(--sig-grey);overflow-wrap:anywhere;white-space:normal}",
        ".cp-sm{display:grid;gap:var(--sp-3)}",
        ".cp-sm-cell{min-width:0}",
        # F1：SVG 隨格寬縮放（已有 viewBox，等比）
        ".cp-sm-cell .cp-spark{width:100%;height:auto;max-height:var(--cp-mini-h)}",
        ".cp-sm-cell .cp-spark-missing{max-height:none}",
        ".cp-sm-name{font-size:12px;color:var(--ink-2)}",
        ".cp-sm-missing{font-size:12px;color:var(--sig-grey);min-height:32px;"
        "overflow-wrap:anywhere;white-space:normal}",
    ]
    for d in range(1, components.MAX_COLS + 1):
        for m in (1, 2):
            rules.append(f".cp-sm-d{d}-m{m}{{grid-template-columns:repeat({d},minmax(0,1fr))}}")
    mob = [".cp-slot-primary{height:min(var(--cp-slot-h),var(--cp-slot-h-mobile))}"]
    for d in range(1, components.MAX_COLS + 1):
        for m in (1, 2):
            mob.append(f".cp-sm-d{d}-m{m}{{grid-template-columns:repeat({m},minmax(0,1fr))}}")
    rules.append(f"@media (max-width:{mobile}px){{{''.join(mob)}}}")
    return "\n".join(rules)


__all__ = [
    "META_KINDS", "MetaKindSpec", "Chip", "meta_chip", "guard_chip", "status_chip", "chips_html",
    "chart_header_html", "chart_slot_missing_html", "kpi_tile_html", "sparkline_svg",
    "SmCell", "small_multiples_html", "TopN", "topn_view", "SegmentSpec", "segment_options",
    "compact_css", "CHIP_VALUE_MAX_CHARS", "CHIPS_MAX",
]
