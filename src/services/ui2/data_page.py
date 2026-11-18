"""🗂 資料頁 canonical（DEC-146 第一批空殼＋DEC-177「資料新鮮度總覽」首屏方案 C；純函式，無 I/O）。

FAKE（`scenarios`）與 Real-data（`real_canonical`）兩軸共用本模組（避免 real 軸 import FAKE 的 `scenarios`）。
- 既有內容全是 Capability 軸 `⬜ 尚未提供`（功能尚未接線）：⛔ 來源健康度欄位／retrieved_at／proxy／刷新時間／真登入／Sheet／API／公式；⛔ 補 0。
- **示意軸（`counts=None`，`data_page_canonical()`）**：維持原本誠實空殼與原文案，⛔ 顯示任何摘要／計數／Real 導出值。
- **Real 軸（`counts` 由 `real_canonical.freshness_states(snap)` 導出）**：第一屏 `context_rows` 四列純文字計數（DEC-177、使用者 2026-11-18 核准方案 C）＋
  Q3=A 文案（與摘要同一個變更上線）。⛔ 本模組不讀 snapshot、不讀時鐘、不新增 fetched_at／published_at、不顯示規則名稱。
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from shared.ui2_contract.pages import P4_DATA, PAGE_LABELS
from shared.ui2_contract.text import (
    ALLOWED_STATUS_PREFIXES, TEXT_MISSING_NOT_READY, TEXT_NOT_EVALUATED, TEXT_NOT_PROVIDED, TEXT_UNAVAILABLE,
)

#: 連線診斷的獨立說明（`shared.ui2_contract.diag.TEXT_DIAG_HEALTH_NOT_OPEN` 同句）。示意軸原文案沿用；Real 軸改用 Q3 文案。
R_DATA_NOT_WIRED = "完整資料健康度尚未開放；本區僅檢查連線，不代表資料已更新"
# ── DEC-177 Q3=A（Real 軸；與總覽同一個變更）──
R_DATA_FIRST_SCREEN = "完整資料健康度尚未開放；本頁先顯示資料新鮮度摘要"
R_DATA_OLD_BLOCK = "完整資料健康度尚未開放；資料日與新鮮度請看『資料新鮮度總覽』"
R_DATA_NEXT_STEP = "完整資料健康度開放後才可查看"
R_DATA_CTA_DISABLED = "完整資料健康度尚未開放"
# ── 示意軸原文案（一字未動）──
_FAKE_NEXT_STEP = "資料健康度清單開放後才可查看"
_FAKE_CTA_DISABLED = "資料健康度尚未開放"

# ── 四列文案（GPT 定稿 2026-11-18；一字不改）──
FRESHNESS_ROW_LABELS = ("資料新鮮度總覽", "接入狀態", "新鮮度", "其他狀態")
FRESHNESS_DISCLAIMER = "資料日在規則內只表示資料日未超過規則，不是買賣訊號。"
FRESHNESS_UNDETERMINABLE_FMT = "另有 {n} 項判定結果為無法判定，不計入上列"
_L_IN_RULE = "資料日在規則內"
_L_STALE = ALLOWED_STATUS_PREFIXES["stale"][0] + "或可能已過期"      # "⚠ 過期或可能已過期"
_L_MISSING = TEXT_MISSING_NOT_READY                                # "⬜ 資料未備"
_L_UNAVAILABLE = TEXT_UNAVAILABLE + "或資料異常"                   # "🔴 來源目前不可用或資料異常"
_L_NOT_EVALUATED = TEXT_NOT_EVALUATED                              # "⬜ 尚未評估"
_L_NOT_PROVIDED = TEXT_NOT_PROVIDED.removeprefix("⬜ ")            # "尚未提供"（Q2=B；不帶 ⬜）
FRESHNESS_N = 8

# ── 項目狀態（Q5=A；互斥）──
S_IN_RULE = "in_rule"
S_STALE = "stale"
S_MISSING = "missing"
S_UNAVAILABLE = "unavailable"
S_NOT_EVALUATED = "not_evaluated"
S_UNDETERMINABLE = "undeterminable"
ITEM_STATES = frozenset({S_IN_RULE, S_STALE, S_MISSING, S_UNAVAILABLE, S_NOT_EVALUATED, S_UNDETERMINABLE})

#: 固定清單 8 項（DEC-177；順序＝線框 §1.2）：(項目 key, 已接入畫面的事實 key；None＝尚未接入)。
#: ⛔ 台股卡與日 K 不算兩個 dataset（K 線屬 `twii`）。接入新項目＝改這裡＋`freshness_states` 同步（`counts_from_states` 雙向驗證）。
FRESHNESS_ITEMS: tuple[tuple[str, str | None], ...] = (
    ("twii", "twii"), ("foreign_flow", None), ("margin", None), ("m1b_m2", None),
    ("pmi", None), ("sector_flow", None), ("regime", "regime"), ("fundamental", None),
)
WIRED_ITEM_KEYS = frozenset(k for k, fact in FRESHNESS_ITEMS if fact is not None)


@dataclass(frozen=True)
class FreshnessCounts:
    total: int
    wired: int
    in_rule: int
    stale: int
    missing: int
    unavailable: int
    not_evaluated: int
    undeterminable: int

    def __post_init__(self) -> None:
        vals = (self.total, self.wired, self.in_rule, self.stale, self.missing, self.unavailable,
                self.not_evaluated, self.undeterminable)
        if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in vals):
            raise ValueError(f"FreshnessCounts 欄位必須是非負整數：{vals!r}")
        if self.wired > self.total:
            raise ValueError(f"已接入 {self.wired} 項 > 固定清單 {self.total} 項")
        if sum(vals[2:]) != self.wired:
            raise ValueError("狀態計數（含無法判定）加總必須等於已接入項數（⛔ 未接入項目不計入任何狀態）")

    @property
    def not_provided(self) -> int:
        return self.total - self.wired


def counts_from_states(states: Mapping[str, str]) -> FreshnessCounts:
    """已接入項目的狀態 → 計數。`states` 的 key 必須**恰好**等於 `WIRED_ITEM_KEYS`、值必屬 `ITEM_STATES`（否則 raise；
    ⛔ 默默漏算或把未接入項目算進狀態）。N／K 皆由 `FRESHNESS_ITEMS` 導出，⛔ 硬寫。"""
    if set(states) != set(WIRED_ITEM_KEYS):
        raise ValueError(f"狀態項目必須恰為已接入項目 {sorted(WIRED_ITEM_KEYS)}，收到 {sorted(states)}")
    bad = {k: v for k, v in states.items() if v not in ITEM_STATES}
    if bad:
        raise ValueError(f"未知項目狀態：{bad!r}")
    n = lambda s: sum(1 for v in states.values() if v == s)  # noqa: E731
    return FreshnessCounts(total=len(FRESHNESS_ITEMS), wired=len(WIRED_ITEM_KEYS), in_rule=n(S_IN_RULE),
                           stale=n(S_STALE), missing=n(S_MISSING), unavailable=n(S_UNAVAILABLE),
                           not_evaluated=n(S_NOT_EVALUATED), undeterminable=n(S_UNDETERMINABLE))


def _np(key: str, label: str, reason: str) -> dict:
    return {"key": key, "label": label, "value": None, "state": "not_provided", "sub_reason": TEXT_NOT_PROVIDED,
            "reason": reason, "fixed": True, "as_of": None, "source": None}


def _count_row(key: str, label: str, value: str, detail: str | None = None) -> dict:
    """純文字計數列（資料語意 OK 態；⛔ 帶 as_of／source／規則名／抓取·發布時間）。"""
    return {"key": key, "label": label, "value": value, "state": None, "reason": detail, "as_of": None, "source": None}


def freshness_rows(c: FreshnessCounts) -> list[dict]:
    """第一屏 `context_rows` 的四列（固定順序；⛔ 第五列）。免責句在第 4 列 detail；n>0 才在其後另加一句。"""
    detail = FRESHNESS_DISCLAIMER
    if c.undeterminable:
        detail += "　" + FRESHNESS_UNDETERMINABLE_FMT.format(n=c.undeterminable)
    l0, l1, l2, l3 = FRESHNESS_ROW_LABELS
    return [
        _count_row("fresh_total", l0, f"固定清單 {c.total} 項"),
        _count_row("fresh_wired", l1, f"已接入畫面 {c.wired} 項｜{_L_NOT_PROVIDED} {c.not_provided} 項"),
        _count_row("fresh_a", l2, f"{_L_IN_RULE} {c.in_rule} 項｜{_L_STALE} {c.stale} 項｜{_L_MISSING} {c.missing} 項"),
        _count_row("fresh_b", l3, f"{_L_UNAVAILABLE} {c.unavailable} 項｜{_L_NOT_EVALUATED} {c.not_evaluated} 項", detail),
    ]


def data_page_canonical(counts: FreshnessCounts | None = None) -> dict:
    """`counts=None` ＝ 示意軸：原本誠實空殼與原文案（⛔ 摘要／計數）。Real 軸**必須**明確傳入由 snapshot 導出的計數。"""
    real = counts is not None
    reason = R_DATA_FIRST_SCREEN if real else R_DATA_NOT_WIRED
    old_block = R_DATA_OLD_BLOCK if real else R_DATA_NOT_WIRED
    return {
        "page": P4_DATA, "title": PAGE_LABELS[P4_DATA],
        "current_state": _np("data_state", "資料健康度", reason),
        "context_rows": freshness_rows(counts) if real else [],
        "action_needed": _np("data_action", "是否需要行動", "本頁不產生持股動作；動作權威＝💼 持股"),
        "next_step": _np("data_next", "下一步", R_DATA_NEXT_STEP if real else _FAKE_NEXT_STEP),
        "cta": {"label": "查看資料健康度", "disabled_reason": R_DATA_CTA_DISABLED if real else _FAKE_CTA_DISABLED},
        "cards": [],
        "sections": [
            {"key": "data_overview", "title": "資料來源與連線", "level": "L1", "fields": [
                _np("src_health", "來源健康度", old_block),
                _np("data_asof", "資料日", old_block),
                _np("active_sheet", "Active Sheet 連線", "登入與 Sheet 尚未開放")]},
        ],
    }
