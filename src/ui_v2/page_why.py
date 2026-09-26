"""「📖 憑什麼」頁的版面契約 —— 純結構層（與 `page_today.py` / `page_find.py` / `page_hold.py` /
`page_inspect.py` 同一套作法）。

唯一資料來源：`docs/v2/spec/UI_PAGE_WHY.md` ② 六層結構表（⛔ 不寫行號）。
⛔ 本檔不 import streamlit。

**範圍（同找標的頁／我的持股頁／查一檔頁，客戶 2026-09-25 裁示 1）**：只登記本頁**真的畫成卡**的
程式卡 key，讓 `markup.card_html(block=…)` 經 `src/ui_v2/blocks.py` 查得到它們的密度階。
⛔ 不是整張 ② 表的搬家：規格裡**沒有卡在畫**的 block 不登記 ——
葉外 chrome 三塊（`why.statusbar` / `why.asof` / `why.footer`）、葉1 下半的五塊門檻表與說明
（`why.edu.table.*`，那是 `st.dataframe` ＋ `st.caption`）、葉2 的三段常駐說明
（`why.source.named` / `.cache_semantics` / `.coverage`，那是 `st.caption`）、
工程師版的監控表（`why.engineer.monitor`，那是 `st.dataframe`）。

🔴 **規格 block key ≠ 程式卡 key（據實登記，⛔ 本檔不改名）**：
  · 規格 `why.source.wall` 是**容器**：程式每一支 fetcher 畫一張卡，key 是
    `why.source.<fetcher 名>` —— **名字來自 L0 登錄表，執行期才知道**（登錄幾支就幾張）。
    登錄表讀得到但是空的時，程式畫 `why.source.none` 一張；登錄表**本身讀不出來**時，
    程式畫 `why.source.registry.unreadable` 一張紅卡（view 的 `WALL_REGISTRY_FAILED_KEY`，
    內容同工程師版 failed 那張）—— 它也走前綴歸進 `why.source.wall`（n3 → t3），
    ⛔ 不再借用 `why.engineer.gate`（QA 2026-09-26 F1／F2：同一輪兩張同 id 的摺疊、且誤掛 t4）。
  · 規格 `why.spec.flags` 是**容器**：程式每一盞被 L0 標記的燈畫一張卡，key 是
    `why.spec.<L0 spec key>` —— 同樣由 L0 決定有幾張。
  · 規格 `why.engineer.panels` 是**容器**：程式畫成五張未接線卡（`why.engineer.registry` …）。
  ⇒ 固定 key 照程式登記；兩個**動態**容器以規格 key 本身登記，程式卡 key 經
  `block_for_card()` 的**前綴表**歸到它（⛔ 不猜：前綴對不上 → `KeyError`）。

**密度由層決定**（UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」）：
每張卡的 `tier` 一律經 `components.tier_for_layer()` 推出，⛔ 沒有逐卡寫死的階。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

from src.ui_v2 import components


def _frozen(mapping: dict) -> Mapping:
    return MappingProxyType(mapping)


#: 線框 `n5`（葉3 AI 問答）**不在** `components.tier_for_layer()` 認得的 0~4 之內。
#: 規格 ② 表「葉3」列逐字：「`t2`（**沿用 `UI_PAGE_FIND` 對 `n5` 的新訂**：超出 `n1~n4`
#: 自動對映時取「核心卡」，⛔ 非本組發明）」⇒ 取**核心卡那一層（第二層）的密度**
#: （同 `src/ui_v2/page_find.py::N5_DENSITY_LAYER`）。
#: ⚠️ 據實揭露：這是規格組新訂的對映，⛔ 不是線框自動掛出來的。
N5_DENSITY_LAYER: Final[int] = 2

# (密度層, 線框 n, 規格 block key, 該 block 的 cols（桌機, 平板, 手機）, 程式卡 keys)
# 層與 cols 一律取 UI_PAGE_WHY.md ② 表（「四塊全 3/2/1」「全 1/1/1」「(3/2/1)」逐格照抄）。
_LAYER_PLAN: Final[tuple[tuple[int, str, str, tuple[int, int, int], tuple[str, ...]], ...]] = (
    # ② 表「第一層 四張說明卡」列（n1，「四塊全 3/2/1」）
    (1, "n1", "why.edu.lights", (3, 2, 1), ("why.edu.lights",)),
    (1, "n1", "why.edu.health6", (3, 2, 1), ("why.edu.health6",)),
    (1, "n1", "why.edu.scales", (3, 2, 1), ("why.edu.scales",)),
    (1, "n1", "why.edu.legacy", (3, 2, 1), ("why.edu.legacy",)),
    # ② 表「第三層 資料體檢 · 使用者版」列（n3）：`why.source.wall`(3/2/1) 是動態容器（見檔頭）
    (3, "n3", "why.source.wall", (3, 2, 1), ("why.source.wall", "why.source.none")),
    (3, "n3", "why.source.unmeasured.finmind_quota", (3, 2, 1),
     ("why.source.unmeasured.finmind_quota",)),
    (3, "n3", "why.spec.flags", (3, 2, 1), ("why.spec.flags",)),
    # ② 表「第四層 資料體檢 · 工程師版」列（n4）：`.gate`（未標 cols ⇒ 1/1/1）、`.panels`(3/2/1)
    (4, "n4", "why.engineer.gate", (1, 1, 1), ("why.engineer.gate",)),
    (4, "n4", "why.engineer.panels", (3, 2, 1),
     ("why.engineer.registry", "why.engineer.reconcile", "why.engineer.api_root",
      "why.engineer.raw", "why.engineer.calibration")),
    # ② 表「葉3」列（n5 → 取核心卡層，見 `N5_DENSITY_LAYER`；1/1/1）
    (N5_DENSITY_LAYER, "n5", "why.qa", (1, 1, 1), ("why.qa",)),
)


def _build_layers() -> tuple[Mapping[str, object], ...]:
    built = []
    for layer, wireframe_n, spec_block, _cols, blocks in _LAYER_PLAN:
        tier = components.tier_for_layer(layer)
        built.append(_frozen({
            "layer": layer,
            "wireframe_n": wireframe_n,
            "spec_block": spec_block,
            "blocks": tuple(blocks),
            "tier": tier,
            "badge_size": components.CARD_TIERS[tier]["badge_size"],
            "title_px": components.CARD_TIERS[tier]["title_px"],
        }))
    return tuple(built)


LAYERS: Final[tuple[Mapping[str, object], ...]] = _build_layers()

#: 登記的卡 key → 它所屬規格 block 的 cols `(桌機, 平板, 手機)`（UI_PAGE_WHY.md ② 表）。
#: ⚠️ 同其他頁：本頁的卡由 Streamlit `_ui_kit.grid()` 排，⛔ 不走 `markup.grid_html()`，
#:   故本表⛔ 不得拿去餵 `grid_html()`。
#: ⚠️ 據實揭露：本頁 view **仍一律以 `MAX_COLS` 排列**（卡化這一批⛔ 不改版面）；
#:   規格自陳「`3/2/1` 的 `tablet=2` 未落地」—— 要照本表排 ＝ 版面佈局異動，先送客戶拍板。
BLOCK_COLS: Final[Mapping[str, tuple[int, int, int]]] = _frozen({
    block: cols for _l, _n, _spec, cols, blocks in _LAYER_PLAN for block in blocks
})

#: 登記的卡 key → 規格 block key。
SPEC_BLOCK: Final[Mapping[str, str]] = _frozen({
    block: spec for _l, _n, spec, _c, blocks in _LAYER_PLAN for block in blocks
})

#: **動態容器**：程式卡 key 的前綴 → 登記的卡 key（＝規格容器 key 本身）。依序比對，取第一個。
#: ⚠️ 固定 key（`why.source.none` / `why.source.unmeasured.finmind_quota`）**先查精確表**，
#:   查不到才走前綴 —— 所以它們不會被歸進 `why.source.wall`。
DYNAMIC_PREFIXES: Final[tuple[tuple[str, str], ...]] = (
    ("why.source.", "why.source.wall"),
    ("why.spec.", "why.spec.flags"),
)

#: UI_PAGE_WHY.md ④ 狀態覆蓋表 #10 列：本頁**有**適用對象（`emits_level=False` 的 KD 指標），
#: 但「現況以 `st.caption` 逐列呈現、`◆` 0 命中 ⇒ **徽章化為待補**」，且
#: 「⛔ 不得把 #10 併進 #5／#4／#7 任何一種」⇒ 本頁的**卡**目前不畫 #10。
#: ⚠️ 這是「還沒畫」，⛔ 不是「不適用」—— 徽章化要先改規格／view，不在本批。
BADGES_NOT_ON_PAGE: Final[frozenset[int]] = frozenset({10})

_BLOCK_LAYER: Final[Mapping[str, int]] = _frozen(
    {block: layer["layer"] for layer in LAYERS for block in layer["blocks"]}
)

assert set(BLOCK_COLS) == set(_BLOCK_LAYER) == set(SPEC_BLOCK), (
    "BLOCK_COLS / SPEC_BLOCK 與 LAYERS 登記的卡不一致 —— 要一起改")
assert len(_BLOCK_LAYER) == sum(len(p[4]) for p in _LAYER_PLAN), "同一張卡登記了兩次"
assert all(_target in _BLOCK_LAYER for _p, _target in DYNAMIC_PREFIXES), (
    "動態前綴指向一個沒有登記的卡 key")


def block_for_card(card_key: str) -> str:
    """程式卡 key → 登記的卡 key（`markup.card_html(block=…)` 要的那一個）。

    精確登記 → 原樣；否則依 `DYNAMIC_PREFIXES` 歸進動態容器；都不是 → `KeyError`（⛔ 不猜一個）。
    """
    if card_key in _BLOCK_LAYER:
        return card_key
    for _prefix, _target in DYNAMIC_PREFIXES:
        if card_key.startswith(_prefix) and len(card_key) > len(_prefix):
            return _target
    raise KeyError(f"未知的卡：{card_key!r}")


def tier_for_block(block_key: str) -> str:
    """登記的卡 key → 卡密度。**⛔ 刻意不提供 tier 覆寫參數**（同 `page_today.tier_for_block`）。"""
    try:
        layer = _BLOCK_LAYER[block_key]
    except KeyError:
        raise KeyError(f"未知的 block：{block_key!r}") from None
    return components.tier_for_layer(layer)


__all__ = ["LAYERS", "BLOCK_COLS", "SPEC_BLOCK", "DYNAMIC_PREFIXES", "BADGES_NOT_ON_PAGE",
           "N5_DENSITY_LAYER", "block_for_card", "tier_for_block"]
