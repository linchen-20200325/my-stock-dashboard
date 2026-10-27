"""shared/decision_digest.py — Decision Digest 資料契約（AB-0；L0 純型別＋不變量驗證）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
DEC-092 後 D2.5 計畫的第一個實作批次 AB-0（`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5／§8；
設計草案 `docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §2／§3／§4／§7.2）。
Decision Digest 是「全站唯一一份、給 One AI Brain 當唯一輸入」的結構：它只**搬運**規則層
（L2／L3）既有的結構化輸出，附逐項來源與狀態。本檔只定**型別＋不變量**，不做任何其他事。

═══ 本檔刻意「不做」的事（客戶邊界，硬性） ═══════════════════════════════
- 不取數、不寫入、不接 AI、不接 UI；不被 `app.py`／`shared/ia_nav.py` import（測試鎖死）。
- **不新增任何投資判斷規則**：本檔沒有多空／趨勢方向列舉、沒有續抱／減碼等行動詞彙、
  沒有產業強弱分級、沒有任何門檻常數。規則層的文字輸出（例如位階標籤、建議動作文字）
  以 `Fact.text`／`ActionRef.text` **原樣搬運**，本檔不認得也不解讀它們。
- `HoldingKey.portfolio_id` 只定為**不透明非空字串鍵**；它的實際來源（哪個 Sheet／組合名
  怎麼組）**不在本檔決定**，留給 AB-4r（C §7.2 (3)）。
- 不做 `from_dict`（反序列化）：目前沒有消費者需要；日後若需要，必須同樣嚴格。

═══ 缺值語意（全檔通用，Fail Loud；CLAUDE.md §1、PROJECT_RULES.md §16.1） ═══════
- 缺值＝`None`（`to_dict()` 輸出 `null`），**絕不**以 0、空字串、"neutral" 代替；
  有值狀態（ok／stale／proxy）的 `text` 也不得是 "N/A"、"-"、"未評估"、"0" 這類缺值佔位字
  （`PLACEHOLDER_TEXTS`）。
- `DataStatus` **沒有** neutral；可用性 `Availability` 的 `UNAVAILABLE` 是「判不出來」，
  **不是**中性。`DefinitionState` 只有「尚未定義」「研究框架，未啟用」兩個非判斷值。
- `AiParticipation` 沒有「AI 產生數值或判斷」這種合法值；行動的來源 `ActionOrigin`
  只有「規則層既有輸出」一種；`Provenance.source`／`RuleRef.rule_id` 不得以 AI 保留前綴開頭。
- C §4.1 HoldingBlock 的 `invalid`（D11：NaN／inf 等不合法值）在本契約表達為
  `status=FAILED`＋`missing_reason=CONTRACT_DRIFT`（值被丟棄為 None，不參與計算）。

═══ 鍵（portfolio_id／symbol／fact_id／action_id／evidence_refs） ═══════════════
必須是非空字串，且：無前後空白、無零寬／格式字元（Unicode Cf 類）、已是 NFKC 正規形
（全形數字「００５０」會被拒收，不會被默默轉成「0050」）。**大小寫敏感、本檔不做大小寫折疊**；
正規化（含大小寫政策）的責任在上游（`portfolio_id` 來源 → AB-4r；其餘 → AB-1 Builder）。

═══ 時區規則 ════════════════════════════════════════════════════════════
- `DecisionDigest.generated_at`：tz-aware 且**必須是 UTC**（utcoffset == 0）。
- `Provenance.fetched_at`：tz-aware（任一時區），且 ≤ generated_at。
- `Provenance.as_of`：台股業務日（`date`，不帶時區，以 UTC+8 解讀），
  必須 ≤ generated_at 換算 UTC+8 的日期；兩者都有時，亦必須 ≤ fetched_at 換算 UTC+8 的日期
  （資料不可能屬於「抓取當下之後」的日子 —— 防 lookahead）。
- status 為 ok 或 stale 時 as_of 必填（沒有資料日就談不上新鮮或過期）；proxy 可無 as_of。

═══ 驗證分兩層 ═══════════════════════════════════════════════════════════
1. 葉節點在 `__post_init__` 就檢查自己的不變量，違反即 `ValueError`（建構即失敗）。
2. 根節點 `DecisionDigest` 的跨物件不變量由 `validate(digest)` 一次回傳**全部**違規，
   `assert_valid(digest)` 有違規即 raise；`to_dict()` 先 `assert_valid` 再輸出。
   `validate` 也會重跑所有葉節點檢查（防 `object.__setattr__` 繞過 frozen），
   且**任何輸入都不 raise**：無法檢查的物件（型別錯、未初始化）一律回報為違規。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫；零 I/O、零 streamlit、零 `src.*`。
本檔是 Stock 端自有檔，不屬跨 repo 單向同步（fund → stock）的標的；
該同步只覆蓋檔頭帶同步標記的檔（如 `shared/__init__.py`、`shared/colors.py`）。
"""
from __future__ import annotations

import math
import numbers
import re
import unicodedata
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

#: Digest 契約版本。改欄位語意時必須升版（讀端靠它分辨新舊契約）。
SCHEMA_VERSION: str = "decision_digest.v1"

#: 本期行動上限（DEC-092 Q4／客戶規格 §九：只給最重要 1–3 項；這是**筆數上限**，不是投資門檻）。
MAX_ACTIONS: int = 3

#: 台股業務日的時區（CLAUDE.md §4.5：Asia/Taipei，UTC+8）。
TW_TZ = timezone(timedelta(hours=8))

#: 有值狀態下 text 不得使用的「缺值佔位字」（strip＋casefold 後比對）。
PLACEHOLDER_TEXTS: frozenset = frozenset({
    "n/a", "na", "nan", "none", "null", "-", "--", "—", "無資料", "未評估", "尚無資料", "0",
})

#: AI 保留前綴：`Provenance.source`／`RuleRef.rule_id` 的首段（依非英數字元切開的第一個 token）
#: 若「等於」ai／llm，或「以」gemini／gpt／claude／openai 開頭 → 拒收。
#: （ai／llm 用「等於」而非「開頭」，以免誤殺 air_quality、llmc 之類無關識別字。）
_AI_EXACT_TOKENS: frozenset = frozenset({"ai", "llm"})
_AI_PREFIX_TOKENS: tuple = ("gemini", "gpt", "claude", "openai")

#: grounding 檢查識別碼（C §2.4 的 G1～G7…）。
_CHECK_ID_RE = re.compile(r"^G[1-9][0-9]*$")
#: 圖表序列引用識別碼格式。
_SERIES_REF_RE = re.compile(r"^[a-z0-9_.:\-]+$")


# ══════════════════════════════════════════════════════════════════════
# 列舉（成員集合由測試鎖死；新增成員＝改契約，須升 SCHEMA_VERSION 並過審）
# ══════════════════════════════════════════════════════════════════════
class DataStatus(str, Enum):
    """單一資料項的狀態（C §4 SourceStatus.status）。⛔ 沒有 neutral。"""
    OK = "ok"
    STALE = "stale"        # 有值但過期（須揭露）
    MISSING = "missing"    # 沒有值
    PROXY = "proxy"        # 代理／估算值，不得以正式資料身分顯示或計分（DEC-037／074／080）
    FAILED = "failed"      # 抓取或計算失敗，沒有值（含 D11 invalid：見模組 docstring）


#: 這兩個狀態代表「沒有值」，value／text 必須為 None，且必須附 missing_reason。
NO_VALUE_STATUSES: frozenset = frozenset({DataStatus.MISSING, DataStatus.FAILED})


class MissingReason(str, Enum):
    """缺值原因。**對映**（非沿用）`shared/station_specs.MISS_*`，字串值不同；
    對映表見 `MISS_CODE_TO_REASON`。另加 C §4 的 NOT_DEFINED／NOT_WIRED。"""
    NO_INPUT = "no_input"
    FETCH_FAILED = "fetch_failed"
    NOT_ENOUGH_HISTORY = "not_enough_history"
    NOT_APPLICABLE = "not_applicable"
    CONTRACT_DRIFT = "contract_drift"
    NO_VARIATION = "no_variation"  # 輸入齊、值合法，但期間零變異（統計量數學上無定義）
    NOT_DEFINED = "not_defined"    # 規則／定義尚未經客戶核准（例：台股趨勢）
    NOT_WIRED = "not_wired"        # 規則存在但尚未接進 Digest


#: `shared/station_specs.MISS_*` 的字串值 → MissingReason（本檔維持 stdlib-only，故以字串值對映；
#: 測試會 import station_specs 逐一斷言每個 MISS_* 都在此表內）。
MISS_CODE_TO_REASON: dict = {
    "no_input": MissingReason.NO_INPUT,
    "fetch_failed": MissingReason.FETCH_FAILED,
    "not_enough": MissingReason.NOT_ENOUGH_HISTORY,
    "n/a": MissingReason.NOT_APPLICABLE,
    "contract_drift": MissingReason.CONTRACT_DRIFT,
    "no_variation": MissingReason.NO_VARIATION,
}

#: 定義狀態段只允許的缺值原因。
_DEFINITION_REASONS: frozenset = frozenset({MissingReason.NOT_DEFINED, MissingReason.NOT_WIRED})


class Availability(str, Enum):
    """一段（section）的可得性。⛔ UNAVAILABLE ≠ 中性／正常。"""
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class AiParticipation(str, Enum):
    """AI 是否參與（C §3.2 第 6 區塊）。⛔ 沒有「AI 產生數值或判斷」這種合法值。"""
    NONE = "rule_only"                 # 規則式（無 AI）
    AI_EXPLAINED = "ai_explained"      # AI 僅整理／排序／解釋規則層輸出，且已通過 grounding 驗證
    AI_REJECTED = "ai_rejected"        # AI 文字被驗證退回，改顯示規則式


class StrategyType(str, Enum):
    """持股策略分類（DEC-092 Q1）。唯一合法預設＝未分類；不得由 ETF／個股推導、不得 AI 猜。"""
    BUY_AND_HOLD = "存股"
    CAPITAL_GAIN = "資本利得"
    UNCLASSIFIED = "未分類"


class DefinitionState(str, Enum):
    """台股趨勢／國際趨勢／產業趨勢／EPS×PE 估值的「定義狀態」。

    ⛔ 只有非判斷值。正式定義屬 High Gate（DEC-092 Q2／Q5），核准前本列舉**不得**增加任何
    偏多／偏空／變強／轉弱之類的值 —— 那會讓 Digest 有能力表達一個未經核准的投資判斷。
    """
    NOT_DEFINED = "尚未定義"
    RESEARCH_ONLY = "研究框架，未啟用"


class ActionOrigin(str, Enum):
    """行動的來源。只允許規則層既有輸出（DEC-092 Q4；PROJECT_RULES §19.5：AI 不得為行動來源）。"""
    RULE_LAYER = "rule_layer"


# ══════════════════════════════════════════════════════════════════════
# 違規紀錄與共用檢查（所有 _check_* 都不得 raise：遇到無法檢查的物件回報違規）
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Violation:
    path: str      # 例："holdings.entries[1].key"
    code: str      # 機器可讀代碼，例："duplicate_holding_key"
    message: str


def _v(path: str, code: str, message: str) -> Violation:
    return Violation(path=path, code=code, message=message)


def _raise_if(violations: list) -> None:
    if violations:
        raise ValueError("Decision Digest 契約違規：" + "；".join(
            f"[{v.code}] {v.path}: {v.message}" for v in violations))


def _safe(check, obj: Any, path: str, **kw) -> list:
    """執行一個 _check_*；若物件無法檢查（未初始化、屬性被竄改成怪型別）回報違規而非 raise。"""
    try:
        return check(obj, path, **kw)
    except Exception as exc:  # noqa: BLE001 —— 刻意：validate 不得 raise，改以違規回報（Fail Loud 由 assert_valid 負責）
        return [_v(path, "uninspectable", f"無法檢查此物件（{type(exc).__name__}: {exc}）")]


def _is_nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _key_problem(v: Any) -> Optional[str]:
    """鍵字串檢查；合格回 None，否則回原因。"""
    if not isinstance(v, str) or v == "":
        return "必須是非空字串"
    if v != v.strip():
        return "不得有前後空白"
    if any(unicodedata.category(ch) == "Cf" for ch in v):
        return "不得含零寬／格式字元"
    if unicodedata.normalize("NFKC", v) != v:
        return "必須是 NFKC 正規形（例：全形數字須在上游轉半形）"
    return None


def _check_key(v: Any, path: str) -> list:
    p = _key_problem(v)
    return [] if p is None else [_v(path, "bad_key", f"{p}：{v!r}")]


def _is_real_number(v: Any) -> bool:
    """有限實數（含 numpy 數值）；⛔ bool／np.bool_ 不得冒充數值、NaN／inf／溢位拒收。"""
    if isinstance(v, bool) or not isinstance(v, numbers.Real):
        return False
    try:
        return math.isfinite(v)
    except (OverflowError, TypeError, ValueError):
        return False


def _is_plain_date(v: Any) -> bool:
    return isinstance(v, date) and not isinstance(v, datetime)


def _is_aware(v: Any) -> bool:
    return isinstance(v, datetime) and v.tzinfo is not None and v.utcoffset() is not None


def _is_placeholder(text: Any) -> bool:
    return isinstance(text, str) and text.strip().casefold() in PLACEHOLDER_TEXTS


def _ai_reserved(s: Any) -> bool:
    if not isinstance(s, str):
        return False
    token = re.split(r"[^0-9a-z]", s.strip().casefold(), maxsplit=1)[0]
    return token in _AI_EXACT_TOKENS or token.startswith(_AI_PREFIX_TOKENS)


def _check_str_tuple(v: Any, path: str, *, nonempty: bool, key: bool = False) -> list:
    if not isinstance(v, tuple):
        return [_v(path, "not_tuple", f"必須是 tuple：{type(v).__name__}")]
    out: list = []
    if nonempty and not v:
        out.append(_v(path, "empty", "不得為空"))
    for i, s in enumerate(v):
        if key:
            out += _check_key(s, f"{path}[{i}]")
        elif not _is_nonempty_str(s):
            out.append(_v(f"{path}[{i}]", "blank_str", f"必須是非空字串：{s!r}"))
    return out


def _check_check_ids(v: Any, path: str) -> list:
    if not isinstance(v, tuple):
        return [_v(path, "not_tuple", f"必須是 tuple：{type(v).__name__}")]
    return [_v(f"{path}[{i}]", "bad_check_id", f"必須是 grounding 檢查識別碼（G1、G2…）：{c!r}")
            for i, c in enumerate(v) if not (isinstance(c, str) and _CHECK_ID_RE.match(c))]


# ══════════════════════════════════════════════════════════════════════
# 葉節點
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Provenance:
    """來源血緣（CLAUDE.md §2.2）。as_of＝資料歸屬日（台股業務日，≠ 抓取日、≠ 判定日）。

    `source` 不得以 AI 保留前綴開頭（AI 不得成為資料來源）。時區規則見模組 docstring。
    """
    source: str
    as_of: Optional[date] = None
    fetched_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        _raise_if(_check_provenance(self, "provenance"))


def _check_provenance(p: Any, path: str) -> list:
    if not isinstance(p, Provenance):
        return [_v(path, "type", f"必須是 Provenance：{type(p).__name__}")]
    out: list = []
    if not _is_nonempty_str(p.source):
        out.append(_v(f"{path}.source", "blank_str", f"source 必須是非空字串：{p.source!r}"))
    elif _ai_reserved(p.source):
        out.append(_v(f"{path}.source", "ai_reserved_prefix", f"source 不得以 AI 保留前綴開頭：{p.source!r}"))
    as_of_ok = p.as_of is None or _is_plain_date(p.as_of)
    if not as_of_ok:
        out.append(_v(f"{path}.as_of", "type", f"as_of 必須是 datetime.date（非 datetime）：{p.as_of!r}"))
    fetched_ok = p.fetched_at is None or _is_aware(p.fetched_at)
    if not fetched_ok:
        out.append(_v(f"{path}.fetched_at", "naive_datetime",
                      f"fetched_at 必須是 tz-aware datetime：{p.fetched_at!r}"))
    if as_of_ok and fetched_ok and p.as_of is not None and p.fetched_at is not None:
        if p.as_of > p.fetched_at.astimezone(TW_TZ).date():
            out.append(_v(f"{path}.as_of", "as_of_after_fetched",
                          f"as_of({p.as_of}) 晚於 fetched_at 的台北日期（lookahead）"))
    return out


@dataclass(frozen=True)
class RuleRef:
    """規則層輸出的出處：既有規則 id＋版本（引用，非新設）。rule_id 不得以 AI 保留前綴開頭。"""
    rule_id: str
    rule_version: str

    def __post_init__(self) -> None:
        _raise_if(_check_rule_ref(self, "rule"))


def _check_rule_ref(r: Any, path: str) -> list:
    if not isinstance(r, RuleRef):
        return [_v(path, "type", f"必須是 RuleRef：{type(r).__name__}")]
    out: list = []
    if not _is_nonempty_str(r.rule_id):
        out.append(_v(f"{path}.rule_id", "blank_str", f"rule_id 必須是非空字串：{r.rule_id!r}"))
    elif _ai_reserved(r.rule_id):
        out.append(_v(f"{path}.rule_id", "ai_reserved_prefix", f"rule_id 不得以 AI 保留前綴開頭：{r.rule_id!r}"))
    if not _is_nonempty_str(r.rule_version):
        out.append(_v(f"{path}.rule_version", "blank_str",
                      f"rule_version 必須是非空字串：{r.rule_version!r}"))
    return out


@dataclass(frozen=True)
class Fact:
    """一個被搬運的資料項或規則輸出（數值 **或** 原樣文字，二擇一或皆無）。

    不變量：
    - `value`：None 或有限實數（含 numpy 數值；⛔ bool／NaN／inf／溢位）。
    - `text`：None 或非空字串；有值狀態下不得是缺值佔位字（`PLACEHOLDER_TEXTS`）。
      ⚠️ `text` **必須逐字等於所引 `rule`（rule_id）的既有規則輸出**；本契約無法驗證這件事，
      正確性責任在 AB-1 Builder；rule_id 的允許名單於 AB-1 補上。
    - status ∈ {missing, failed} ⇔ value 與 text 皆為 None ⇔ missing_reason 必填。
    - status ∈ {ok, stale} ⇒ provenance.as_of 必填。
    """
    fact_id: str
    status: DataStatus
    provenance: Provenance
    value: Optional[float] = None
    text: Optional[str] = None
    unit: Optional[str] = None
    missing_reason: Optional[MissingReason] = None
    rule: Optional[RuleRef] = None

    def __post_init__(self) -> None:
        _raise_if(_check_fact(self, "fact"))


def _check_fact(f: Any, path: str, *, rule_required: bool = False) -> list:
    if not isinstance(f, Fact):
        return [_v(path, "type", f"必須是 Fact：{type(f).__name__}")]
    out: list = _check_key(f.fact_id, f"{path}.fact_id")
    if not isinstance(f.status, DataStatus):
        out.append(_v(f"{path}.status", "type", f"status 必須是 DataStatus：{f.status!r}"))
        return out  # 其餘判斷都依賴 status
    if f.value is not None and not _is_real_number(f.value):
        out.append(_v(f"{path}.value", "bad_number",
                      f"value 必須是有限實數（bool／NaN／inf／溢位拒收）：{f.value!r}"))
    if f.text is not None and not _is_nonempty_str(f.text):
        out.append(_v(f"{path}.text", "blank_str", f"text 若有值必須是非空字串：{f.text!r}"))
    if f.unit is not None and not _is_nonempty_str(f.unit):
        out.append(_v(f"{path}.unit", "blank_str", f"unit 若有值必須是非空字串：{f.unit!r}"))
    if f.value is not None and f.text is not None:
        out.append(_v(path, "value_and_text", "value 與 text 只能二擇一"))
    has_value = f.value is not None or f.text is not None
    if f.status in NO_VALUE_STATUSES and has_value:
        out.append(_v(path, "value_with_missing_status",
                      f"status={f.status.value} 時 value／text 必須為 None"))
    if not has_value and f.status not in NO_VALUE_STATUSES:
        out.append(_v(path, "missing_value_with_present_status",
                      f"value／text 皆為 None 時 status 不得為 {f.status.value}（缺值不得冒充有值）"))
    if f.status not in NO_VALUE_STATUSES and _is_placeholder(f.text):
        out.append(_v(f"{path}.text", "placeholder_text",
                      f"status={f.status.value} 時 text 不得是缺值佔位字：{f.text!r}"))
    if f.status in NO_VALUE_STATUSES:
        if not isinstance(f.missing_reason, MissingReason):
            out.append(_v(f"{path}.missing_reason", "missing_reason_required",
                          f"status={f.status.value} 時 missing_reason 必填（MissingReason）"))
    elif f.missing_reason is not None:
        out.append(_v(f"{path}.missing_reason", "missing_reason_on_value",
                      f"status={f.status.value} 時 missing_reason 必須為 None"))
    out += _check_provenance(f.provenance, f"{path}.provenance")
    if (f.status in (DataStatus.OK, DataStatus.STALE) and isinstance(f.provenance, Provenance)
            and f.provenance.as_of is None):
        out.append(_v(f"{path}.provenance.as_of", "dated_status_without_as_of",
                      f"status={f.status.value} 時 as_of 必填（沒有資料日不得宣稱新鮮或過期）"))
    if f.rule is not None:
        out += _check_rule_ref(f.rule, f"{path}.rule")
    elif rule_required:
        out.append(_v(f"{path}.rule", "rule_required", "此處的 Fact 必須帶 rule（rule_id＋rule_version）"))
    return out


def derive_availability(facts: tuple) -> Availability:
    """由 facts 推導可得性（純函式；Section 宣告值必須與此一致）。

    - 無 fact，或全部 status ∈ {missing, failed} → UNAVAILABLE
    - 全部 status＝ok → AVAILABLE
    - 其餘（有值但含 stale／proxy／missing／failed）→ PARTIAL
    """
    if not facts or all(f.status in NO_VALUE_STATUSES for f in facts):
        return Availability.UNAVAILABLE
    if all(f.status is DataStatus.OK for f in facts):
        return Availability.AVAILABLE
    return Availability.PARTIAL


def _facts_are_inspectable(facts: Any) -> bool:
    return isinstance(facts, tuple) and all(
        isinstance(f, Fact) and isinstance(f.status, DataStatus) for f in facts)


# ══════════════════════════════════════════════════════════════════════
# 持股鍵與持股
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class HoldingKey:
    """策略分類的鍵（DEC-092 Q1）：`portfolio_id + symbol`。⛔ 不得以 symbol 作全站唯一鍵。

    `portfolio_id` 是**不透明**字串；本契約不解析、不決定其來源（AB-4r）。
    兩者皆受「鍵」規則拘束（見模組 docstring）：大小寫敏感，正規化責任在上游 AB-4r。
    """
    portfolio_id: str
    symbol: str

    def __post_init__(self) -> None:
        _raise_if(_check_holding_key(self, "key"))


def _check_holding_key(k: Any, path: str) -> list:
    if not isinstance(k, HoldingKey):
        return [_v(path, "type", f"必須是 HoldingKey：{type(k).__name__}")]
    return _check_key(k.portfolio_id, f"{path}.portfolio_id") + _check_key(k.symbol, f"{path}.symbol")


def _hashable_key(k: Any) -> Optional[HoldingKey]:
    """合格（可安全雜湊比較）的 HoldingKey，否則 None。"""
    if isinstance(k, HoldingKey) and not _check_holding_key(k, ""):
        return k
    return None


@dataclass(frozen=True)
class HoldingEntry:
    """一檔持股。策略預設且唯一合法預設＝未分類；有分類時必須註明分類來源（客戶設定位置）。"""
    key: HoldingKey
    strategy: StrategyType = StrategyType.UNCLASSIFIED
    strategy_source: Optional[str] = None
    facts: tuple = ()

    def __post_init__(self) -> None:
        _raise_if(_check_holding_entry(self, "holding"))


def _check_holding_entry(h: Any, path: str) -> list:
    if not isinstance(h, HoldingEntry):
        return [_v(path, "type", f"必須是 HoldingEntry：{type(h).__name__}")]
    out = _check_holding_key(h.key, f"{path}.key")
    if not isinstance(h.strategy, StrategyType):
        out.append(_v(f"{path}.strategy", "type", f"strategy 必須是 StrategyType：{h.strategy!r}"))
    elif h.strategy is StrategyType.UNCLASSIFIED:
        if h.strategy_source is not None:
            out.append(_v(f"{path}.strategy_source", "source_on_unclassified",
                          "未分類時 strategy_source 必須為 None"))
    elif not _is_nonempty_str(h.strategy_source):
        out.append(_v(f"{path}.strategy_source", "source_required",
                      f"策略為 {h.strategy.value} 時必須註明 strategy_source（客戶設定來源）"))
    out += _check_facts(h.facts, f"{path}.facts")
    return out


def _check_facts(facts: Any, path: str, *, rule_required: bool = False) -> list:
    if not isinstance(facts, tuple):
        return [_v(path, "not_tuple", f"必須是 tuple：{type(facts).__name__}")]
    out: list = []
    for i, f in enumerate(facts):
        out += _check_fact(f, f"{path}[{i}]", rule_required=rule_required)
    return out


# ══════════════════════════════════════════════════════════════════════
# 行動
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ActionRef:
    """一項本期行動的**引用**。本契約不定義任何行動詞彙。

    ⚠️ `text` **必須逐字等於所引 `rule`（rule_id）的既有規則輸出**；本契約無法驗證這件事，
    正確性責任在 AB-1 Builder；rule_id 的允許名單於 AB-1 補上。
    `evidence_refs` 必須指向本 Digest 內有值（非 missing／failed）的 fact。
    """
    action_id: str
    text: str
    origin: ActionOrigin
    rule: RuleRef
    evidence_refs: tuple
    target: Optional[HoldingKey] = None
    priority_rank: Optional[int] = None   # 只能沿用既有優先序（DEC-092 Q4）；無則 None

    def __post_init__(self) -> None:
        _raise_if(_check_action(self, "action"))


def _check_action(a: Any, path: str) -> list:
    if not isinstance(a, ActionRef):
        return [_v(path, "type", f"必須是 ActionRef：{type(a).__name__}")]
    out: list = _check_key(a.action_id, f"{path}.action_id")
    if not _is_nonempty_str(a.text):
        out.append(_v(f"{path}.text", "blank_str", f"text 必須是非空字串：{a.text!r}"))
    elif _is_placeholder(a.text):
        out.append(_v(f"{path}.text", "placeholder_text", f"行動文字不得是缺值佔位字：{a.text!r}"))
    if not isinstance(a.origin, ActionOrigin) or a.origin is not ActionOrigin.RULE_LAYER:
        out.append(_v(f"{path}.origin", "non_rule_origin",
                      f"行動來源只允許規則層既有輸出（AI 不得為行動來源）：{a.origin!r}"))
    out += _check_rule_ref(a.rule, f"{path}.rule")
    out += _check_str_tuple(a.evidence_refs, f"{path}.evidence_refs", nonempty=True, key=True)
    if a.target is not None:
        out += _check_holding_key(a.target, f"{path}.target")
    if a.priority_rank is not None and (
            isinstance(a.priority_rank, bool) or not isinstance(a.priority_rank, int)
            or a.priority_rank < 1):
        out.append(_v(f"{path}.priority_rank", "bad_rank",
                      f"priority_rank 若有值必須是 ≥1 的 int：{a.priority_rank!r}"))
    return out


# ══════════════════════════════════════════════════════════════════════
# 各段（section）
# ══════════════════════════════════════════════════════════════════════
def _check_section_reason(availability: Any, reason: Any, path: str) -> list:
    if not isinstance(availability, Availability):
        return [_v(f"{path}.availability", "type", f"availability 必須是 Availability：{availability!r}")]
    out: list = []
    if availability is Availability.UNAVAILABLE:
        if not isinstance(reason, MissingReason):
            out.append(_v(f"{path}.missing_reason", "missing_reason_required",
                          "availability=unavailable 時 missing_reason 必填"))
    elif reason is not None:
        out.append(_v(f"{path}.missing_reason", "missing_reason_on_available",
                      f"availability={availability.value} 時 missing_reason 必須為 None"))
    return out


def _check_derived(declared: Any, facts: Any, path: str, prior: list) -> list:
    if prior or not isinstance(declared, Availability) or not _facts_are_inspectable(facts):
        return []
    derived = derive_availability(facts)
    if declared is not derived:
        return [_v(f"{path}.availability", "availability_mismatch",
                   f"宣告 {declared.value}，但由 facts 推導為 {derived.value}")]
    return []


@dataclass(frozen=True)
class FactSection:
    """以 facts 構成的段（market）。availability 必須等於 derive_availability。"""
    availability: Availability
    facts: tuple = ()
    missing_reason: Optional[MissingReason] = None

    def __post_init__(self) -> None:
        _raise_if(_check_fact_section(self, "section"))


def _check_fact_section(s: Any, path: str, *, rule_required: bool = False) -> list:
    if not isinstance(s, FactSection):
        return [_v(path, "type", f"必須是 FactSection：{type(s).__name__}")]
    out = _check_facts(s.facts, f"{path}.facts", rule_required=rule_required)
    out += _check_section_reason(s.availability, s.missing_reason, path)
    return out + _check_derived(s.availability, s.facts, path, out)


@dataclass(frozen=True)
class DefinitionSection:
    """台股趨勢／國際趨勢／產業趨勢／EPS×PE 估值：正式定義未核准前只有定義狀態，沒有結論欄位。

    - `series_ref`：可選的既有圖表序列識別碼（格式 `^[a-z0-9_.:\\-]+$`），**不等於**趨勢判斷（DEC-092 Q2）。
    - `observations`：可選的既有**數值**參考（例：既有指數／均線值），各自帶來源與規則；
      ⛔ 不得帶 `text` —— DEC-092 Q2「不得由 AI／均線／單一指標自行補成多空結論」，
      文字標籤在此處就是結論的載體。
    - 定義狀態只有非判斷值，故 availability 固定 unavailable，missing_reason 只能是
      NOT_DEFINED 或 NOT_WIRED。
    """
    definition: DefinitionState
    missing_reason: MissingReason = MissingReason.NOT_DEFINED
    availability: Availability = Availability.UNAVAILABLE
    series_ref: Optional[str] = None
    observations: tuple = ()

    def __post_init__(self) -> None:
        _raise_if(_check_definition_section(self, "section"))


def _check_definition_section(s: Any, path: str) -> list:
    if not isinstance(s, DefinitionSection):
        return [_v(path, "type", f"必須是 DefinitionSection：{type(s).__name__}")]
    out: list = []
    if not isinstance(s.definition, DefinitionState):
        out.append(_v(f"{path}.definition", "type", f"definition 必須是 DefinitionState：{s.definition!r}"))
    if s.availability is not Availability.UNAVAILABLE:
        out.append(_v(f"{path}.availability", "undefined_but_available",
                      "定義未核准時 availability 必須為 unavailable（未定義 ≠ 可判斷）"))
    if not (isinstance(s.missing_reason, MissingReason) and s.missing_reason in _DEFINITION_REASONS):
        out.append(_v(f"{path}.missing_reason", "bad_definition_reason",
                      f"定義狀態段的 missing_reason 只能是 NOT_DEFINED／NOT_WIRED：{s.missing_reason!r}"))
    if s.series_ref is not None and not (isinstance(s.series_ref, str) and _SERIES_REF_RE.match(s.series_ref)):
        out.append(_v(f"{path}.series_ref", "bad_series_ref",
                      f"series_ref 必須符合 ^[a-z0-9_.:\\-]+$：{s.series_ref!r}"))
    out += _check_facts(s.observations, f"{path}.observations", rule_required=True)
    if isinstance(s.observations, tuple):
        for i, f in enumerate(s.observations):
            if isinstance(f, Fact) and f.text is not None:
                out.append(_v(f"{path}.observations[{i}].text", "text_in_definition_section",
                              "定義未核准的段只能搬運數值參考，不得帶文字標籤（可能是結論）"))
    return out


@dataclass(frozen=True)
class HoldingsSection:
    """持股段。availability 依全部 entries 的 facts 推導（0 筆 → unavailable）；
    unavailable 時以 missing_reason 區分讀取失敗（FETCH_FAILED）與未綁定（NO_INPUT）。"""
    availability: Availability
    entries: tuple = ()
    missing_reason: Optional[MissingReason] = None

    def __post_init__(self) -> None:
        _raise_if(_check_holdings_section(self, "holdings"))


def _check_holdings_section(s: Any, path: str) -> list:
    if not isinstance(s, HoldingsSection):
        return [_v(path, "type", f"必須是 HoldingsSection：{type(s).__name__}")]
    out = _check_section_reason(s.availability, s.missing_reason, path)
    if not isinstance(s.entries, tuple):
        return out + [_v(f"{path}.entries", "not_tuple", "entries 必須是 tuple")]
    seen: dict = {}
    for i, h in enumerate(s.entries):
        out += _check_holding_entry(h, f"{path}.entries[{i}]")
        k = _hashable_key(h.key) if isinstance(h, HoldingEntry) else None
        if k is not None:
            if k in seen:
                out.append(_v(f"{path}.entries[{i}].key", "duplicate_holding_key",
                              f"(portfolio_id, symbol) 重複：與 entries[{seen[k]}] 相同 {k!r}"))
            else:
                seen[k] = i
    if not out:
        all_facts = tuple(f for h in s.entries for f in h.facts)
        out += _check_derived(s.availability, all_facts, path, out)
    return out


@dataclass(frozen=True)
class RiskCapSection:
    """Risk Cap／建議持股水位：**只引用**既有輸出（`exposure_limit_pct`、`AllocationDecision.final_lo/hi`），不重算。

    `cap_valid`：搬運上游 `shared.risk_cap_policy.is_valid_risk_cap_snapshot` 的結果（引用，非新判）。
    不變量：
    - cap_valid=False ⇒ cap_pct 的 value 為 None 且 status 非 ok（D13：「無法判定」，不是 0、不是 100）；
    - cap_valid=True ⇒ cap_pct 必須有值且 status ∈ {ok, stale}（stale＝7 天沿用，須揭露）；
    - 三個 fact 都必須帶 rule；百分比若有值必須落在 [0, 100]（量綱定義域，非投資門檻）。
    """
    cap_valid: bool
    cap_pct: Fact
    exposure_lo_pct: Fact
    exposure_hi_pct: Fact
    availability: Availability
    missing_reason: Optional[MissingReason] = None

    def __post_init__(self) -> None:
        _raise_if(_check_risk_cap_section(self, "risk_cap"))

    @property
    def facts(self) -> tuple:
        return (self.cap_pct, self.exposure_lo_pct, self.exposure_hi_pct)


def _check_risk_cap_section(s: Any, path: str) -> list:
    if not isinstance(s, RiskCapSection):
        return [_v(path, "type", f"必須是 RiskCapSection：{type(s).__name__}")]
    out: list = []
    if not isinstance(s.cap_valid, bool):
        out.append(_v(f"{path}.cap_valid", "type", f"cap_valid 必須是 bool：{s.cap_valid!r}"))
    for name in ("cap_pct", "exposure_lo_pct", "exposure_hi_pct"):
        f = getattr(s, name)
        out += _check_fact(f, f"{path}.{name}", rule_required=True)
        if isinstance(f, Fact):
            if f.text is not None:
                out.append(_v(f"{path}.{name}.text", "text_on_numeric", "此處只承載數值，text 必須為 None"))
            if _is_real_number(f.value) and not (0 <= f.value <= 100):
                out.append(_v(f"{path}.{name}.value", "pct_out_of_domain",
                              f"百分比必須在 [0, 100]：{f.value!r}"))
    cap = s.cap_pct
    if isinstance(cap, Fact) and isinstance(cap.status, DataStatus):
        if s.cap_valid is False and (cap.value is not None or cap.status is DataStatus.OK):
            out.append(_v(f"{path}.cap_pct", "invalid_cap_has_value",
                          "cap_valid=False 時 cap_pct 必須 value=None 且 status 非 ok（無法判定）"))
        if s.cap_valid is True and (cap.value is None
                                    or cap.status not in (DataStatus.OK, DataStatus.STALE)):
            out.append(_v(f"{path}.cap_pct", "valid_cap_without_value",
                          "cap_valid=True 時 cap_pct 必須有值且 status ∈ {ok, stale}"))
    lo, hi = s.exposure_lo_pct, s.exposure_hi_pct
    if (isinstance(lo, Fact) and isinstance(hi, Fact)
            and _is_real_number(lo.value) and _is_real_number(hi.value) and lo.value > hi.value):
        out.append(_v(path, "exposure_lo_gt_hi", f"exposure_lo_pct({lo.value}) > exposure_hi_pct({hi.value})"))
    out += _check_section_reason(s.availability, s.missing_reason, path)
    return out + _check_derived(s.availability, (cap, lo, hi), path, out)


@dataclass(frozen=True)
class ActionsSection:
    """本期行動（0..3 項）。availability 只允許 available／unavailable（⛔ partial）。

    - unavailable＝判不出來：必須 0 筆行動且附 missing_reason；
    - available 且 0 筆＝「規則層未產出行動」，**明文合法**（不得湊數）。
    """
    availability: Availability
    items: tuple = ()
    missing_reason: Optional[MissingReason] = None

    def __post_init__(self) -> None:
        _raise_if(_check_actions_section(self, "actions"))


def _check_actions_section(s: Any, path: str) -> list:
    if not isinstance(s, ActionsSection):
        return [_v(path, "type", f"必須是 ActionsSection：{type(s).__name__}")]
    out = _check_section_reason(s.availability, s.missing_reason, path)
    if s.availability is Availability.PARTIAL:
        out.append(_v(f"{path}.availability", "partial_actions",
                      "行動段只允許 available／unavailable（行動不是可以「部分可得」的資料）"))
    if not isinstance(s.items, tuple):
        return out + [_v(f"{path}.items", "not_tuple", "items 必須是 tuple")]
    if len(s.items) > MAX_ACTIONS:
        out.append(_v(f"{path}.items", "too_many_actions",
                      f"行動至多 {MAX_ACTIONS} 項（不得湊數）：實得 {len(s.items)}"))
    if s.availability is Availability.UNAVAILABLE and s.items:
        out.append(_v(f"{path}.items", "items_when_unavailable", "availability=unavailable 時 items 必須為空"))
    ids: set = set()
    ranks: set = set()
    for i, a in enumerate(s.items):
        out += _check_action(a, f"{path}.items[{i}]")
        if not isinstance(a, ActionRef):
            continue
        if _key_problem(a.action_id) is None:
            if a.action_id in ids:
                out.append(_v(f"{path}.items[{i}].action_id", "duplicate_action_id", repr(a.action_id)))
            ids.add(a.action_id)
        r = a.priority_rank
        if isinstance(r, int) and not isinstance(r, bool):
            if r in ranks:
                out.append(_v(f"{path}.items[{i}].priority_rank", "duplicate_rank", repr(r)))
            ranks.add(r)
    return out


# ══════════════════════════════════════════════════════════════════════
# 根
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class DecisionDigest:
    """Decision Digest 根。建構時**不**做跨物件檢查；請以 `assert_valid` 收口（`to_dict` 會自動呼叫）。

    - `generated_at`：tz-aware UTC（時區規則見模組 docstring）。
    - `ai_passed_checks`：AI_EXPLAINED 時必填（非空，元素為 grounding 檢查識別碼 G1、G2…）。
    - `ai_failed_checks`：AI_REJECTED 時必填（同格式）。NONE 時兩者皆須為空。
    """
    generated_at: datetime
    market: FactSection
    tw_trend: DefinitionSection
    intl_trend: DefinitionSection
    valuation: DefinitionSection
    industry: DefinitionSection
    holdings: HoldingsSection
    risk_cap: RiskCapSection
    actions: ActionsSection
    ai_participation: AiParticipation = AiParticipation.NONE
    ai_passed_checks: tuple = ()
    ai_failed_checks: tuple = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        assert_valid(self)
        return _to_jsonable(self)


def _all_facts(d: DecisionDigest) -> list:
    """(path, Fact) 全列表（供 fact_id 唯一性、evidence_refs 解析與時間一致性）。"""
    out: list = []

    def add(path: str, facts: Any) -> None:
        if isinstance(facts, tuple):
            out.extend((f"{path}[{i}]", f) for i, f in enumerate(facts) if isinstance(f, Fact))
    m = getattr(d, "market", None)
    if isinstance(m, FactSection):
        add("market.facts", m.facts)
    for name in ("tw_trend", "intl_trend", "valuation", "industry"):
        s = getattr(d, name, None)
        if isinstance(s, DefinitionSection):
            add(f"{name}.observations", s.observations)
    hs = getattr(d, "holdings", None)
    if isinstance(hs, HoldingsSection) and isinstance(hs.entries, tuple):
        for i, h in enumerate(hs.entries):
            if isinstance(h, HoldingEntry):
                add(f"holdings.entries[{i}].facts", h.facts)
    rc = getattr(d, "risk_cap", None)
    if isinstance(rc, RiskCapSection):
        for name in ("cap_pct", "exposure_lo_pct", "exposure_hi_pct"):
            f = getattr(rc, name, None)
            if isinstance(f, Fact):
                out.append((f"risk_cap.{name}", f))
    return out


def _check_root(d: DecisionDigest, path: str) -> list:
    out: list = []
    if d.schema_version != SCHEMA_VERSION:
        out.append(_v("schema_version", "schema_version_mismatch",
                      f"期望 {SCHEMA_VERSION!r}，實得 {d.schema_version!r}"))
    gen_ok = _is_aware(d.generated_at)
    if not gen_ok:
        out.append(_v("generated_at", "naive_datetime", f"generated_at 必須是 tz-aware datetime：{d.generated_at!r}"))
    elif d.generated_at.utcoffset() != timedelta(0):
        out.append(_v("generated_at", "generated_at_not_utc", f"generated_at 必須是 UTC：{d.generated_at!r}"))
        gen_ok = False

    # AI 參與
    ap = d.ai_participation
    if not isinstance(ap, AiParticipation):
        out.append(_v("ai_participation", "type", f"必須是 AiParticipation：{ap!r}"))
    else:
        passed_v = _check_check_ids(d.ai_passed_checks, "ai_passed_checks")
        failed_v = _check_check_ids(d.ai_failed_checks, "ai_failed_checks")
        out += passed_v + failed_v
        passed = d.ai_passed_checks if not passed_v else ()
        failed = d.ai_failed_checks if not failed_v else ()
        if ap is AiParticipation.NONE and (passed or failed):
            out.append(_v("ai_passed_checks", "checks_without_ai", "rule_only 時 ai_passed／failed_checks 必須為空"))
        if ap is AiParticipation.AI_EXPLAINED:
            if not passed and not passed_v:
                out.append(_v("ai_passed_checks", "explained_without_checks",
                              "ai_explained 時必須列出已通過的 grounding 檢查 id"))
            if failed:
                out.append(_v("ai_failed_checks", "explained_with_failures",
                              "ai_explained 時不得有未通過的檢查（應為 ai_rejected）"))
        if ap is AiParticipation.AI_REJECTED and not failed and not failed_v:
            out.append(_v("ai_failed_checks", "rejected_without_checks", "ai_rejected 時必須列出未通過的檢查 id"))

    # 跨物件：fact_id 唯一；時間一致性
    facts = _all_facts(d)
    fact_by_id: dict = {}
    gen_tw_date = d.generated_at.astimezone(TW_TZ).date() if gen_ok else None
    for p, f in facts:
        if _key_problem(f.fact_id) is None:
            if f.fact_id in fact_by_id:
                out.append(_v(f"{p}.fact_id", "duplicate_fact_id", f"{f.fact_id!r} 與 {fact_by_id[f.fact_id][0]} 重複"))
            else:
                fact_by_id[f.fact_id] = (p, f)
        pv = f.provenance
        if gen_ok and isinstance(pv, Provenance):
            if _is_aware(pv.fetched_at) and pv.fetched_at > d.generated_at:
                out.append(_v(f"{p}.provenance.fetched_at", "fetched_after_generated",
                              f"fetched_at({pv.fetched_at}) 晚於 generated_at({d.generated_at})"))
            if _is_plain_date(pv.as_of) and pv.as_of > gen_tw_date:
                out.append(_v(f"{p}.provenance.as_of", "as_of_after_generated",
                              f"as_of({pv.as_of}) 晚於 generated_at 的台北日期 {gen_tw_date}"))

    # 行動：evidence 指向有值 fact；target 在 holdings 內
    hs = d.holdings
    holding_keys: set = set()
    if isinstance(hs, HoldingsSection) and isinstance(hs.entries, tuple):
        holding_keys = {k for k in (_hashable_key(getattr(h, "key", None)) for h in hs.entries
                                    if isinstance(h, HoldingEntry)) if k is not None}
    acts = d.actions
    if isinstance(acts, ActionsSection) and isinstance(acts.items, tuple):
        for i, a in enumerate(acts.items):
            if not isinstance(a, ActionRef):
                continue
            if isinstance(a.evidence_refs, tuple):
                for j, ref in enumerate(a.evidence_refs):
                    if _key_problem(ref) is not None:
                        continue
                    hit = fact_by_id.get(ref)
                    rp = f"actions.items[{i}].evidence_refs[{j}]"
                    if hit is None:
                        out.append(_v(rp, "dangling_evidence_ref", f"{ref!r} 不是本 Digest 內任何 fact_id"))
                    elif isinstance(hit[1].status, DataStatus) and hit[1].status in NO_VALUE_STATUSES:
                        out.append(_v(rp, "evidence_on_missing_fact",
                                      f"{ref!r} 指向 status={hit[1].status.value} 的 fact（缺值不得當依據）"))
            if a.target is not None:
                tk = _hashable_key(a.target)
                if tk is not None and tk not in holding_keys:
                    out.append(_v(f"actions.items[{i}].target", "target_not_in_holdings",
                                  f"{a.target!r} 不在 holdings 內（行動不得指向 Digest 外的標的）"))
    return out


def validate(digest: Any) -> tuple:
    """純函式：回傳 digest 的**全部**契約違規（空 tuple＝合規）。任何輸入都不 raise。"""
    if not isinstance(digest, DecisionDigest):
        return (_v("digest", "type", f"必須是 DecisionDigest：{type(digest).__name__}"),)
    d = digest
    out: list = []
    out += _safe(lambda o, p: _check_fact_section(getattr(o, "market"), p), d, "market")
    for name in ("tw_trend", "intl_trend", "valuation", "industry"):
        out += _safe(lambda o, p, n=name: _check_definition_section(getattr(o, n), p), d, name)
    out += _safe(lambda o, p: _check_holdings_section(getattr(o, "holdings"), p), d, "holdings")
    out += _safe(lambda o, p: _check_risk_cap_section(getattr(o, "risk_cap"), p), d, "risk_cap")
    out += _safe(lambda o, p: _check_actions_section(getattr(o, "actions"), p), d, "actions")
    out += _safe(_check_root, d, "digest")
    return tuple(out)


def assert_valid(digest: Any) -> None:
    """Fail Loud：有任何違規即 raise ValueError（訊息列出全部違規）。"""
    _raise_if(list(validate(digest)))


# ══════════════════════════════════════════════════════════════════════
# 序列化（JSON 可序列化；None 保留為 null，⛔ 不轉 0／空字串；Enum 輸出 .value 純字串）
# ══════════════════════════════════════════════════════════════════════
def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Enum):  # 須在 str 之前：本檔列舉皆繼承 str
        return str(obj.value)
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        return str(obj)
    if isinstance(obj, numbers.Integral):
        return int(obj)
    if isinstance(obj, numbers.Real):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, tuple):
        return [_to_jsonable(x) for x in obj]
    if is_dataclass(obj):
        return {f.name: _to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    raise TypeError(f"Decision Digest 含無法序列化的型別：{type(obj).__name__}")


__all__ = [
    "SCHEMA_VERSION", "MAX_ACTIONS", "NO_VALUE_STATUSES", "TW_TZ", "PLACEHOLDER_TEXTS",
    "MISS_CODE_TO_REASON",
    "DataStatus", "MissingReason", "Availability", "AiParticipation", "StrategyType",
    "DefinitionState", "ActionOrigin",
    "Violation", "Provenance", "RuleRef", "Fact", "derive_availability",
    "HoldingKey", "HoldingEntry", "ActionRef",
    "FactSection", "DefinitionSection", "HoldingsSection", "RiskCapSection", "ActionsSection",
    "DecisionDigest", "validate", "assert_valid",
]
