"""shared/decision_digest_rules.py — Decision Digest 的 rule_id 允許名單與行動排序守衛（AB-1；L0）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
AB-0 契約（`shared/decision_digest.py`）刻意把兩件事留給 AB-1（見其 `Fact`／`ActionRef` docstring 與
`_ai_reserved` 註解）：(1) `rule_id` 的**權威允許名單**；(2) Q4 行動優先序的**執行**。
本檔補這兩件事，並且**不改 AB-0 的任何語意**（不加參數給 `validate()`、不讓 `RuleRef.__post_init__`
變得認得名單 —— AB-0 的測試 fixture 用 `rule_x` 這種臨時 id）。

⚠️ **治理關係（寫死）**：本檔的 `RULE_ID_ALLOWLIST` 是 rule_id 的**主要**治理手段；
AB-0 的 AI／方向字樣拒收名單（`_ai_reserved`、`_has_direction_token`）只剩**縱深防禦**
（盡力而為，不是完備判定）。換句話說：一個 rule_id 能不能出現在 Digest，以本名單為準；
名單外的 id 即使躲過字樣黑名單也一律是違規。

═══ 允許名單的成員（每個都只能是「程式裡已經存在」的識別字，不得預載推測成員） ═══
- `risk_cap` → {`risk_cap.v2`}：版本取自 `shared.risk_cap_policy.RISK_CAP_RULESET_VERSION`（SSOT）。
- 行動規則 id ＝ `src/compute/etf/dividend_station.py` 的 `action_branch` 既有分支代碼
  `ACTION_CUT／ACTION_TAKE_PROFIT_FORCE／ACTION_TAKE_PROFIT_PARTIAL／ACTION_PAUSE_ADD／ACTION_ADD`
  （L0 不得 import `src.*`，故以字串複本登記；`tests/test_decision_digest_rules.py` 逐一 pin 住與
  `dividend_station.ACTION_*` 相等）。
- ⛔ `premium`／`cruise` **刻意不收**：它們不在客戶的行動順序（汰弱＞停利＞趨勢暫停＞加碼）內，
  不得成為本期行動（DEC-092 Q4：不得創造規則層沒有、客戶沒核准的買賣動作）。
- 市場事實（regime／light／health）是**搬運值**，不是規則輸出：`Fact.rule` 在 AB-0 是選填，
  故不編造 rule id，只帶 Provenance。

═══ AB-1 內部命名決定（⚠️ 不是客戶裁示） ═══════════════════════════════
行動規則**沒有**既有的版本常數。本檔使用單一標籤 `ACTION_RULE_VERSION = "action_branch.v1"`
作為 `rule_version`，這是 **AB-1 實作者的內部命名決定**，不是客戶核准的規則版本；
日後若 `action_branch` 的條件或優先序變更，必須升此標籤（並過審）。

═══ Q4 行動優先序（`Q4_ACTION_PRIORITY`） ════════════════════════════════
出處：`docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §4 與 `dividend_station.action_branch`／
`suggest_action` docstring 的「汰弱 > 停利 > 趨勢暫停 > 加碼」。程式裡沒有可 import 的排序 SSOT，
故本檔登記一份，並由測試 pin 住它與 `action_branch` 實際解決衝突條件的順序一致（漂移即紅燈）。
同一階內：`take_profit_force` 在 `take_profit_partial` 之前（即 `action_branch` 的程式順序），
其餘依輸入順序（stable）。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫與 `shared.*`；零 I/O、零 streamlit、零 `src.*`。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from shared.decision_digest import (
    MAX_ACTIONS, ActionRef, DecisionDigest, Fact, HoldingEntry, HoldingsSection, RuleRef, Violation,
    validate,
)
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION

#: 行動規則的版本標籤（⚠️ AB-1 內部命名決定，非客戶裁示；見模組 docstring）。
ACTION_RULE_VERSION: str = "action_branch.v1"

#: 行動分支代碼（複本；與 `dividend_station.ACTION_*` 相等由測試 pin 住）。
RULE_CUT: str = "cut"                                  # dividend_station.ACTION_CUT
RULE_TAKE_PROFIT_FORCE: str = "take_profit_force"      # dividend_station.ACTION_TAKE_PROFIT_FORCE
RULE_TAKE_PROFIT_PARTIAL: str = "take_profit_partial"  # dividend_station.ACTION_TAKE_PROFIT_PARTIAL
RULE_PAUSE_ADD: str = "pause_add"                      # dividend_station.ACTION_PAUSE_ADD
RULE_ADD: str = "add"                                  # dividend_station.ACTION_ADD

#: Q4 優先序：(階名, 該階分支代碼 tuple)，由高到低（出處見模組 docstring）。
Q4_ACTION_PRIORITY: tuple = (
    ("汰弱", (RULE_CUT,)),
    ("停利", (RULE_TAKE_PROFIT_FORCE, RULE_TAKE_PROFIT_PARTIAL)),
    ("趨勢暫停", (RULE_PAUSE_ADD,)),
    ("加碼", (RULE_ADD,)),
)

#: 行動規則 id（Q4 序攤平）。
ACTION_RULE_IDS: tuple = tuple(c for _, codes in Q4_ACTION_PRIORITY for c in codes)

#: rule_id → 允許的 rule_version 集合（不可變）。
RULE_ID_ALLOWLIST: Mapping = MappingProxyType({
    "risk_cap": frozenset({RISK_CAP_RULESET_VERSION}),
    **{rid: frozenset({ACTION_RULE_VERSION}) for rid in ACTION_RULE_IDS},
})


def q4_tier_index(rule_id: str) -> int | None:
    """rule_id 所在的 Q4 階序（0＝汰弱…）；不在行動序內回 None。"""
    for i, (_, codes) in enumerate(Q4_ACTION_PRIORITY):
        if rule_id in codes:
            return i
    return None


def q4_sort_index(rule_id: str) -> int | None:
    """rule_id 在攤平 Q4 序中的位置（同階內 force 先於 partial）；不在行動序內回 None。"""
    try:
        return ACTION_RULE_IDS.index(rule_id)
    except ValueError:
        return None


def _v(path: str, code: str, message: str) -> Violation:
    return Violation(path=path, code=code, message=message)


def _r(x: Any) -> str:
    try:
        s = repr(x)
        return s if type(s) is str else f"<unrepr-able {type(x).__name__}>"
    except Exception:  # noqa: BLE001 —— 刻意：違規訊息格式化不得讓 validate raise
        return f"<unrepr-able {type(x).__name__}>"


def _check_rule(rule: Any, path: str) -> list:
    """單一 RuleRef 對允許名單。型別不對由 AB-0 `validate` 回報，這裡不重複。"""
    if type(rule) is not RuleRef:
        return []
    rid, ver = rule.rule_id, rule.rule_version
    allowed = RULE_ID_ALLOWLIST.get(rid) if type(rid) is str else None
    if allowed is None:
        return [_v(f"{path}.rule_id", "rule_not_allowlisted", f"rule_id 不在允許名單：{_r(rid)}")]
    if ver not in allowed:
        return [_v(f"{path}.rule_version", "rule_version_not_allowed",
                   f"{_r(rid)} 的版本 {_r(ver)} 不在允許版本 {sorted(allowed)}")]
    return []


def _walk_rules(d: DecisionDigest) -> list:
    """(path, RuleRef|None) —— 每個 Fact.rule 與 ActionRef.rule。不 raise。"""
    out: list = []

    def facts(path: str, fs: Any) -> None:
        if type(fs) is tuple:
            for i, f in enumerate(fs):
                if type(f) is Fact:
                    out.append((f"{path}[{i}].rule", f.rule))

    facts("market.facts", getattr(getattr(d, "market", None), "facts", None))
    for name in ("tw_trend", "intl_trend", "valuation", "industry"):
        facts(f"{name}.observations", getattr(getattr(d, name, None), "observations", None))
    hs = getattr(d, "holdings", None)
    if type(hs) is HoldingsSection and type(hs.entries) is tuple:
        for i, h in enumerate(hs.entries):
            if type(h) is HoldingEntry:
                facts(f"holdings.entries[{i}].facts", h.facts)
    rc = getattr(d, "risk_cap", None)
    for name in ("cap_pct", "exposure_lo_pct", "exposure_hi_pct"):
        f = getattr(rc, name, None)
        if type(f) is Fact:
            out.append((f"risk_cap.{name}.rule", f.rule))
    acts = getattr(d, "actions", None)
    items = getattr(acts, "items", None)
    if type(items) is tuple:
        for i, a in enumerate(items):
            if type(a) is ActionRef:
                out.append((f"actions.items[{i}].rule", a.rule))
    return out


def validate_rule_ids(digest: Any) -> tuple:
    """走訪每個 `Fact.rule` 與 `ActionRef.rule`，回傳允許名單違規（不 raise）。

    違規碼：`rule_not_allowlisted`、`rule_version_not_allowed`。`Fact.rule is None` 合法（AB-0 選填）。
    """
    if type(digest) is not DecisionDigest:
        return (_v("digest", "type", f"必須恰好是 DecisionDigest：{type(digest).__name__}"),)
    try:
        out: list = []
        for path, rule in _walk_rules(digest):
            if rule is not None:
                out += _check_rule(rule, path[: -len(".rule")])
        return tuple(out)
    except Exception as exc:  # noqa: BLE001 —— 刻意：validate 不得 raise
        return (_v("digest", "uninspectable", f"無法檢查 rule_id（{type(exc).__name__}: {_r(exc)}）"),)


def validate_action_order(digest: Any) -> tuple:
    """行動必須依 Q4 排序（不 raise）。

    檢查：≤ MAX_ACTIONS 由 AB-0 負責，這裡**再**檢查（縱深）；每項 rule 在行動允許名單內；
    Q4 序（攤平位置）不遞減；priority_rank 必填且嚴格遞增。
    違規碼：`action_rule_not_allowed`、`action_order_violation`、`action_rank_missing`、
    `action_rank_not_increasing`、`too_many_actions`。
    """
    if type(digest) is not DecisionDigest:
        return (_v("digest", "type", f"必須恰好是 DecisionDigest：{type(digest).__name__}"),)
    try:
        acts = digest.actions
        items = getattr(acts, "items", None)
        if type(items) is not tuple:
            return ()
        out: list = []
        if len(items) > MAX_ACTIONS:
            out.append(_v("actions.items", "too_many_actions", f"行動至多 {MAX_ACTIONS} 項：實得 {len(items)}"))
        prev_sort: int | None = None
        prev_rank: int | None = None
        for i, a in enumerate(items):
            if type(a) is not ActionRef:
                continue
            p = f"actions.items[{i}]"
            rule = a.rule
            if type(rule) is RuleRef:
                idx = q4_sort_index(rule.rule_id) if type(rule.rule_id) is str else None
                if idx is None or rule.rule_version not in RULE_ID_ALLOWLIST.get(rule.rule_id, frozenset()):
                    out.append(_v(f"{p}.rule", "action_rule_not_allowed",
                                  f"行動的 rule 必須是行動允許名單內的 id＋版本：{_r(rule)}"))
                elif prev_sort is not None and idx < prev_sort:
                    out.append(_v(f"{p}.rule", "action_order_violation",
                                  f"行動未依 Q4 序（汰弱＞停利＞趨勢暫停＞加碼）排序：{_r(rule.rule_id)}"))
                if idx is not None:
                    prev_sort = idx if prev_sort is None else max(prev_sort, idx)
            r = a.priority_rank
            if r is None or isinstance(r, bool) or not isinstance(r, int):
                out.append(_v(f"{p}.priority_rank", "action_rank_missing",
                              f"priority_rank 必須是整數（Q4 序位置）：{_r(r)}"))
            else:
                if prev_rank is not None and r <= prev_rank:
                    out.append(_v(f"{p}.priority_rank", "action_rank_not_increasing",
                                  f"priority_rank 必須嚴格遞增：{r} ≤ 前一項 {prev_rank}"))
                prev_rank = r
        return tuple(out)
    except Exception as exc:  # noqa: BLE001 —— 刻意：validate 不得 raise
        return (_v("digest", "uninspectable", f"無法檢查行動排序（{type(exc).__name__}: {_r(exc)}）"),)


def validate_strict(digest: Any) -> tuple:
    """AB-0 `validate` ＋ rule_id 允許名單 ＋ 行動排序。回傳全部違規（不 raise）。"""
    base = tuple(validate(digest))
    if type(digest) is not DecisionDigest:
        return base
    return base + validate_rule_ids(digest) + validate_action_order(digest)


def assert_strict(digest: Any) -> None:
    """Fail Loud：`validate_strict` 有任何違規即 raise ValueError（格式同 AB-0）。"""
    vs = validate_strict(digest)
    if vs:
        raise ValueError("Decision Digest 契約違規：" + "；".join(
            f"[{v.code}] {v.path}: {v.message}" for v in vs))


__all__ = [
    "ACTION_RULE_VERSION", "RULE_CUT", "RULE_TAKE_PROFIT_FORCE", "RULE_TAKE_PROFIT_PARTIAL",
    "RULE_PAUSE_ADD", "RULE_ADD", "Q4_ACTION_PRIORITY", "ACTION_RULE_IDS", "RULE_ID_ALLOWLIST",
    "q4_tier_index", "q4_sort_index",
    "validate_rule_ids", "validate_action_order", "validate_strict", "assert_strict",
]
