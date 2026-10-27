"""shared/decision_digest.py — Decision Digest 資料契約（AB-0；L0 純型別＋不變量驗證）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
DEC-092 後 D2.5 計畫的第一個實作批次 AB-0（`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5／§8；
設計草案 `docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §2／§3／§4／§7.2）。
Decision Digest 是「全站唯一一份、給 One AI Brain 當唯一輸入」的結構：它只**搬運**規則層
（L2／L3）既有的結構化輸出，附逐項來源與狀態。本檔只定**型別＋不變量**，不做任何其他事。

═══ 本檔刻意「不做」的事（客戶邊界，硬性） ═══════════════════════════════
- 不取數、不寫入、不接 AI、不接 UI；`app.py`／`shared/ia_nav.py` 不**直接** import 本檔
  （測試以 AST 鎖死，只檢查直接 import，不追蹤間接 import 鏈）。
- **不新增任何投資判斷規則**：本檔沒有多空／趨勢方向列舉、沒有續抱／減碼等行動詞彙、
  沒有產業強弱分級、沒有任何門檻常數。規則層的文字輸出（例如位階標籤、建議動作文字）
  以 `Fact.text`／`ActionRef.text` **原樣搬運**，本檔不認得也不解讀它們。
- `HoldingKey.portfolio_id` 只定為**不透明非空字串鍵**；它的實際來源（哪個 Sheet／組合名
  怎麼組）**不在本檔決定**，留給 AB-4r（C §7.2 (3)）。上游缺鍵的列不得由本契約補鍵，
  只以 `HoldingsSection.unkeyed_count` 計數。
- 不做 `from_dict`（反序列化）：目前沒有消費者需要；日後若需要，必須同樣嚴格。

═══ 型別嚴格度 ═══════════════════════════════════════════════════════════
每個契約節點必須**恰好**是本檔的類別（`type(x) is Fact`，子類別一律拒收 —— 子類別可夾帶
`ai_verdict` 之類未經審查的欄位）。文字欄位必須恰好是 `str`、`as_of` 恰好是 `date`、
時間欄位恰好是 `datetime`。`to_dict` 只輸出契約類別宣告的欄位。

═══ 缺值語意（全檔通用，Fail Loud；CLAUDE.md §1、PROJECT_RULES.md §16.1） ═══════
- 缺值＝`None`（`to_dict()` 輸出 `null`），**絕不**以 0、空字串、"neutral" 代替；
  有值狀態（ok／stale／proxy）的 `text`、行動文字與 `strategy_source` 也不得是缺值佔位字
  （`_is_placeholder`；**盡力而為的拒收名單，不是完備判定**）。
- `DataStatus` **沒有** neutral；`INVALID`＝C §4.1 D11「有值但不是合法數值」：值丟棄為 None、
  不附 missing_reason（station_specs Z49：它不是 MISS 概念；給客戶的文案屬 UI 層）。
- 可用性 `Availability.UNAVAILABLE` 是「判不出來」，**不是**中性。
  `DefinitionState` 只有「尚未定義」「研究框架，未啟用」兩個非判斷值。
- `AiParticipation` 沒有「AI 產生數值或判斷」這種合法值；行動的來源 `ActionOrigin`
  只有「規則層既有輸出」一種（DEC-092 Q4：不得創造規則層沒有產出的買賣動作）。
  `Provenance.source`／`RuleRef.rule_id`／`strategy_source` 拒收 AI 字樣（`_ai_reserved`；
  **盡力而為的拒收名單**；權威的 rule_id 允許名單在 AB-1 補上）。

═══ 鍵（portfolio_id／symbol／fact_id／action_id／evidence_refs） ═══════════════
必須是非空 `str`，且：不含任何空白（前後或中間）、不含控制字元（Cc）或零寬／格式字元（Cf）、
已是 NFKC 正規形（全形數字「００５０」會被拒收，不會被默默轉成「0050」）。
**大小寫敏感、本檔不做大小寫折疊**；正規化（含大小寫政策）的責任在上游
（`portfolio_id` 來源 → AB-4r；其餘 → AB-1 Builder）。

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
   且**任何輸入都不 raise**：無法檢查的物件（型別錯、未初始化、repr 會炸）一律回報為違規。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫；零 I/O、零 streamlit、零 `src.*`。
本檔是 Stock 端自有檔，不屬跨 repo 單向同步（fund → stock）的標的；
該同步只覆蓋檔頭帶同步標記的檔（如 `shared/__init__.py`、`shared/colors.py`）。
"""
from __future__ import annotations

import math
import numbers
import re
import unicodedata
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

#: Digest 契約版本。改欄位語意時必須升版（讀端靠它分辨新舊契約）。
SCHEMA_VERSION: str = "decision_digest.v1"

#: 本期行動上限（DEC-092 Q4／客戶規格 §九：只給最重要 1–3 項；這是**筆數上限**，不是投資門檻）。
MAX_ACTIONS: int = 3

#: 台股業務日的時區（CLAUDE.md §4.5：Asia/Taipei，UTC+8）。
TW_TZ = timezone(timedelta(hours=8))

#: 有值狀態下文字不得使用的「缺值佔位字」（正規化後比對，見 `_norm_placeholder`）。
#: ⚠️ 盡力而為的拒收名單，不是完備判定。另加規則：符合 `^[0.]+%?$` 的字串（0、0.0、0%…）。
PLACEHOLDER_TEXTS: frozenset = frozenset({
    "n/a", "na", "n.a.", "nan", "none", "null", "unknown", "?", "-", "--", "—", "–",
    "無資料", "未評估", "尚無資料", "暫無資料", "未知", "無",
})
_ZERO_LIKE_RE = re.compile(r"[0.]+%?")

#: AI 字樣拒收名單（盡力而為；權威 rule_id 允許名單在 AB-1）。見 `_ai_reserved`。
_AI_EXACT_TOKENS: frozenset = frozenset({"ai", "llm", "genai", "gen_ai"})
_AI_PREFIX_TOKENS: tuple = ("gemini", "gpt", "chatgpt", "claude", "anthropic", "openai",
                            "deepseek", "copilot", "llm", "mistral", "llama")
_AI_TOKEN_SPLIT_RE = re.compile(r"[:._/\-\s]+")
_CJK = r"㐀-䶿一-鿿豈-﫿"
_AI_CJK_RE = re.compile(rf"(?:(?<=[{_CJK}])ai)|(?:ai(?=[{_CJK}]))")

#: 方向字樣拒收名單（套用於趨勢／估值／產業段的識別欄位；盡力而為，不是完備判定）。
#: 英文：依非英數字元切 token 後「等於」比對；中文：子字串比對。
_DIRECTION_LATIN: frozenset = frozenset({
    "bull", "bear", "bullish", "bearish", "long", "short", "up", "down", "uptrend", "downtrend",
    "buy", "sell", "strong", "weak",
})
_DIRECTION_CJK: tuple = ("偏多", "偏空", "多頭", "空頭", "看多", "看空", "轉強", "轉弱", "強", "弱")

#: grounding 檢查識別碼（C §2.4 的 G1～G6；G7 是輸出過濾，不是內容驗證，故不列）。
_CHECK_ID_RE = re.compile(r"G[1-6]")
#: 圖表序列引用識別碼格式。
_SERIES_REF_RE = re.compile(r"[a-z0-9_.:\-]+")
#: 定義狀態段 observations 的單位格式。
_UNIT_RE = re.compile(r"[A-Za-z0-9%._/\-]*")


# ══════════════════════════════════════════════════════════════════════
# 列舉（成員集合由測試鎖死；新增成員＝改契約，須升 SCHEMA_VERSION 並過審）
# ══════════════════════════════════════════════════════════════════════
class DataStatus(str, Enum):
    """單一資料項的狀態（C §4 SourceStatus.status）。⛔ 沒有 neutral。"""
    OK = "ok"
    STALE = "stale"        # 有值但過期（須揭露）
    MISSING = "missing"    # 沒有值
    PROXY = "proxy"        # 代理／估算值，不得以正式資料身分顯示或計分（DEC-037／074／080）
    FAILED = "failed"      # 抓取或計算失敗，沒有值
    INVALID = "invalid"    # D11：上游給了值但不是合法數值（NaN／inf…）；值丟棄、不附 missing_reason


#: 代表「沒有可用值」的狀態：value／text 必須為 None。
NO_VALUE_STATUSES: frozenset = frozenset({DataStatus.MISSING, DataStatus.FAILED, DataStatus.INVALID})
#: 需要 missing_reason 的狀態（INVALID 不需要：它不是 MISS 概念）。
_REASON_STATUSES: frozenset = frozenset({DataStatus.MISSING, DataStatus.FAILED})
#: 可當行動依據的狀態。
_EVIDENCE_STATUSES: frozenset = frozenset({DataStatus.OK, DataStatus.STALE})


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
    RULE_ONLY = "rule_only"            # 規則式（無 AI）
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
    綁定：tw_trend／intl_trend／industry ＝ NOT_DEFINED；valuation ＝ RESEARCH_ONLY。
    """
    NOT_DEFINED = "尚未定義"
    RESEARCH_ONLY = "研究框架，未啟用"


class ActionOrigin(str, Enum):
    """行動的來源。只允許規則層既有輸出（DEC-092 Q4：AI 不得創造規則層沒有產出的動作）。"""
    RULE_LAYER = "rule_layer"


# ══════════════════════════════════════════════════════════════════════
# 違規紀錄與共用檢查（所有 _check_* 都不得 raise：遇到無法檢查的物件回報違規）
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Violation:
    path: str      # 例："holdings.entries[1].key"
    code: str      # 機器可讀代碼，例："duplicate_holding_key"
    message: str


def _r(x: Any) -> str:
    """不會 raise 的 repr（訊息格式化用）。"""
    try:
        s = repr(x)
        return s if type(s) is str else f"<unrepr-able {type(x).__name__}>"
    except Exception:  # noqa: BLE001 —— 刻意：違規訊息格式化不得讓 validate raise
        return f"<unrepr-able {type(x).__name__}>"


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
        return [_v(path, "uninspectable", f"無法檢查此物件（{type(exc).__name__}: {_r(exc)}）")]


def _is_str(v: Any) -> bool:
    return type(v) is str


def _is_nonempty_str(v: Any) -> bool:
    return type(v) is str and v.strip() != ""


def _is_tuple(v: Any) -> bool:
    return type(v) is tuple


def _key_problem(v: Any) -> Optional[str]:
    """鍵字串檢查；合格回 None，否則回原因。"""
    if type(v) is not str or v == "":
        return "必須是非空 str"
    if any(ch.isspace() for ch in v):
        return "不得含任何空白"
    if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in v):
        return "不得含控制字元或零寬／格式字元"
    if unicodedata.normalize("NFKC", v) != v:
        return "必須是 NFKC 正規形（例：全形數字須在上游轉半形）"
    return None


def _check_key(v: Any, path: str) -> list:
    p = _key_problem(v)
    return [] if p is None else [_v(path, "bad_key", f"{p}：{_r(v)}")]


def _is_real_number(v: Any) -> bool:
    """有限實數（含 numpy 數值）；⛔ bool／np.bool_／Decimal／NaN／inf／溢位拒收。"""
    if isinstance(v, bool) or not isinstance(v, numbers.Real):
        return False
    try:
        return math.isfinite(v)
    except (OverflowError, TypeError, ValueError):
        return False


def _is_integral(v: Any) -> bool:
    return isinstance(v, numbers.Integral) and not isinstance(v, bool)


def _is_plain_date(v: Any) -> bool:
    return type(v) is date


def _is_aware(v: Any) -> bool:
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def _strip_controls(s: str) -> str:
    return "".join(ch for ch in s if unicodedata.category(ch) not in ("Cc", "Cf"))


def _norm_placeholder(s: str) -> str:
    s = _strip_controls(unicodedata.normalize("NFKC", s)).casefold()
    return "".join(s.split())


def _is_placeholder(text: Any) -> bool:
    """盡力而為的缺值佔位字判定（NFKC → 去 Cc/Cf → casefold → 去所有空白後比對）。"""
    if type(text) is not str:
        return False
    n = _norm_placeholder(text)
    return n in PLACEHOLDER_TEXTS or bool(_ZERO_LIKE_RE.fullmatch(n))


def _ai_reserved(s: Any) -> bool:
    """盡力而為的 AI 字樣判定（NFKC → 去 Cf → casefold → 依 `[:._/\\-\\s]` 切 token）。"""
    if type(s) is not str:
        return False
    n = "".join(ch for ch in unicodedata.normalize("NFKC", s) if unicodedata.category(ch) != "Cf").casefold()
    if "模型" in n or _AI_CJK_RE.search(n):
        return True
    if "gen_ai" in n:
        return True
    for tok in _AI_TOKEN_SPLIT_RE.split(n):
        if tok in _AI_EXACT_TOKENS or (tok and tok.startswith(_AI_PREFIX_TOKENS)):
            return True
    return False


def _has_direction_token(s: Any) -> bool:
    """盡力而為的方向字樣判定（NFKC → casefold；英文依非英數切 token 等於比對、中文子字串）。"""
    if type(s) is not str:
        return False
    n = unicodedata.normalize("NFKC", s).casefold()
    if any(w in n for w in _DIRECTION_CJK):
        return True
    return any(tok in _DIRECTION_LATIN for tok in re.split(r"[^0-9a-z]+", n))


def _check_str_tuple(v: Any, path: str, *, nonempty: bool, key: bool = False) -> list:
    if not _is_tuple(v):
        return [_v(path, "not_tuple", f"必須是 tuple：{type(v).__name__}")]
    out: list = []
    if nonempty and not v:
        out.append(_v(path, "empty", "不得為空"))
    for i, s in enumerate(v):
        if key:
            out += _check_key(s, f"{path}[{i}]")
        elif not _is_nonempty_str(s):
            out.append(_v(f"{path}[{i}]", "blank_str", f"必須是非空 str：{_r(s)}"))
    return out


def _check_check_ids(v: Any, path: str) -> list:
    if not _is_tuple(v):
        return [_v(path, "not_tuple", f"必須是 tuple：{type(v).__name__}")]
    out = [_v(f"{path}[{i}]", "bad_check_id", f"必須是 grounding 檢查識別碼 G1～G6：{_r(c)}")
           for i, c in enumerate(v) if not (type(c) is str and _CHECK_ID_RE.fullmatch(c))]
    if not out and len(set(v)) != len(v):
        out.append(_v(path, "duplicate_check_id", f"檢查 id 不得重複：{_r(v)}"))
    return out


def _type_violation(x: Any, cls: type, path: str) -> list:
    if type(x) is not cls:
        return [_v(path, "type", f"必須恰好是 {cls.__name__}（子類別拒收）：{type(x).__name__}")]
    return []


# ══════════════════════════════════════════════════════════════════════
# 葉節點
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Provenance:
    """來源血緣（CLAUDE.md §2.2）。as_of＝資料歸屬日（台股業務日，≠ 抓取日、≠ 判定日）。

    `source` 不得含 AI 字樣（AI 不得成為資料來源）。時區規則見模組 docstring。
    """
    source: str
    as_of: Optional[date] = None
    fetched_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        _raise_if(_safe(_check_provenance, self, "provenance"))


def _check_provenance(p: Any, path: str) -> list:
    if type(p) is not Provenance:
        return _type_violation(p, Provenance, path)
    out: list = []
    if not _is_nonempty_str(p.source):
        out.append(_v(f"{path}.source", "blank_str", f"source 必須是非空 str：{_r(p.source)}"))
    elif _ai_reserved(p.source):
        out.append(_v(f"{path}.source", "ai_reserved", f"source 不得含 AI 字樣：{_r(p.source)}"))
    as_of_ok = p.as_of is None or _is_plain_date(p.as_of)
    if not as_of_ok:
        out.append(_v(f"{path}.as_of", "type", f"as_of 必須恰好是 datetime.date：{_r(p.as_of)}"))
    fetched_ok = p.fetched_at is None or _is_aware(p.fetched_at)
    if not fetched_ok:
        out.append(_v(f"{path}.fetched_at", "naive_datetime",
                      f"fetched_at 必須是 tz-aware datetime：{_r(p.fetched_at)}"))
    if as_of_ok and fetched_ok and p.as_of is not None and p.fetched_at is not None:
        if p.as_of > p.fetched_at.astimezone(TW_TZ).date():
            out.append(_v(f"{path}.as_of", "as_of_after_fetched",
                          f"as_of({p.as_of}) 晚於 fetched_at 的台北日期（lookahead）"))
    return out


@dataclass(frozen=True)
class RuleRef:
    """規則層輸出的出處：既有規則 id＋版本（引用，非新設）。rule_id 不得含 AI 字樣。"""
    rule_id: str
    rule_version: str

    def __post_init__(self) -> None:
        _raise_if(_safe(_check_rule_ref, self, "rule"))


def _check_rule_ref(r: Any, path: str) -> list:
    if type(r) is not RuleRef:
        return _type_violation(r, RuleRef, path)
    out: list = []
    if not _is_nonempty_str(r.rule_id):
        out.append(_v(f"{path}.rule_id", "blank_str", f"rule_id 必須是非空 str：{_r(r.rule_id)}"))
    elif _ai_reserved(r.rule_id):
        out.append(_v(f"{path}.rule_id", "ai_reserved", f"rule_id 不得含 AI 字樣：{_r(r.rule_id)}"))
    if not _is_nonempty_str(r.rule_version):
        out.append(_v(f"{path}.rule_version", "blank_str",
                      f"rule_version 必須是非空 str：{_r(r.rule_version)}"))
    return out


@dataclass(frozen=True)
class Fact:
    """一個被搬運的資料項或規則輸出（數值 **或** 原樣文字，二擇一或皆無）。

    不變量：
    - `value`：None 或有限實數（含 numpy 數值；⛔ bool／Decimal／NaN／inf／溢位）。
    - `text`：None 或非空 str；有值狀態下不得是缺值佔位字（盡力而為名單）。
      ⚠️ `text` **必須逐字等於所引 `rule`（rule_id）的既有規則輸出**；本契約無法驗證這件事，
      正確性責任在 AB-1 Builder；rule_id 的允許名單於 AB-1 補上。
    - status ∈ {missing, failed, invalid} ⇔ value 與 text 皆為 None。
    - missing_reason：status ∈ {missing, failed} 時必填，其餘（含 invalid）必須為 None。
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
        _raise_if(_safe(_check_fact, self, "fact"))


def _check_fact(f: Any, path: str, *, rule_required: bool = False) -> list:
    if type(f) is not Fact:
        return _type_violation(f, Fact, path)
    out: list = _check_key(f.fact_id, f"{path}.fact_id")
    if type(f.status) is not DataStatus:
        out.append(_v(f"{path}.status", "type", f"status 必須是 DataStatus：{_r(f.status)}"))
        return out  # 其餘判斷都依賴 status
    if f.value is not None and not _is_real_number(f.value):
        out.append(_v(f"{path}.value", "bad_number",
                      f"value 必須是有限實數（bool／Decimal／NaN／inf／溢位拒收）：{_r(f.value)}"))
    if f.text is not None and not _is_nonempty_str(f.text):
        out.append(_v(f"{path}.text", "blank_str", f"text 若有值必須是非空 str：{_r(f.text)}"))
    if f.unit is not None and not _is_nonempty_str(f.unit):
        out.append(_v(f"{path}.unit", "blank_str", f"unit 若有值必須是非空 str：{_r(f.unit)}"))
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
                      f"status={f.status.value} 時 text 不得是缺值佔位字：{_r(f.text)}"))
    if f.status in _REASON_STATUSES:
        if type(f.missing_reason) is not MissingReason:
            out.append(_v(f"{path}.missing_reason", "missing_reason_required",
                          f"status={f.status.value} 時 missing_reason 必填（MissingReason）"))
    elif f.missing_reason is not None:
        out.append(_v(f"{path}.missing_reason", "missing_reason_forbidden",
                      f"status={f.status.value} 時 missing_reason 必須為 None"))
    out += _check_provenance(f.provenance, f"{path}.provenance")
    if (f.status in (DataStatus.OK, DataStatus.STALE) and type(f.provenance) is Provenance
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

    - 無 fact，或全部 status ∈ {missing, failed, invalid} → UNAVAILABLE
    - 全部 status＝ok → AVAILABLE
    - 其餘 → PARTIAL
    """
    if not facts or all(f.status in NO_VALUE_STATUSES for f in facts):
        return Availability.UNAVAILABLE
    if all(f.status is DataStatus.OK for f in facts):
        return Availability.AVAILABLE
    return Availability.PARTIAL


def _facts_are_inspectable(facts: Any) -> bool:
    return _is_tuple(facts) and all(type(f) is Fact and type(f.status) is DataStatus for f in facts)


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
        _raise_if(_safe(_check_holding_key, self, "key"))


def _check_holding_key(k: Any, path: str) -> list:
    if type(k) is not HoldingKey:
        return _type_violation(k, HoldingKey, path)
    return _check_key(k.portfolio_id, f"{path}.portfolio_id") + _check_key(k.symbol, f"{path}.symbol")


def _hashable_key(k: Any) -> Optional[HoldingKey]:
    """合格（可安全雜湊比較）的 HoldingKey，否則 None。"""
    if type(k) is HoldingKey and not _check_holding_key(k, ""):
        return k
    return None


@dataclass(frozen=True)
class HoldingEntry:
    """一檔持股。策略預設且唯一合法預設＝未分類；有分類時必須註明分類來源（客戶設定位置），
    且 strategy_source 不得是缺值佔位字、不得含 AI 字樣（不得 AI 猜）。"""
    key: HoldingKey
    strategy: StrategyType = StrategyType.UNCLASSIFIED
    strategy_source: Optional[str] = None
    facts: tuple = ()

    def __post_init__(self) -> None:
        _raise_if(_safe(_check_holding_entry, self, "holding"))


def _check_holding_entry(h: Any, path: str) -> list:
    if type(h) is not HoldingEntry:
        return _type_violation(h, HoldingEntry, path)
    out = _check_holding_key(h.key, f"{path}.key")
    sp = f"{path}.strategy_source"
    if type(h.strategy) is not StrategyType:
        out.append(_v(f"{path}.strategy", "type", f"strategy 必須是 StrategyType：{_r(h.strategy)}"))
    elif h.strategy is StrategyType.UNCLASSIFIED:
        if h.strategy_source is not None:
            out.append(_v(sp, "source_on_unclassified", "未分類時 strategy_source 必須為 None"))
    elif not _is_nonempty_str(h.strategy_source):
        out.append(_v(sp, "source_required",
                      f"策略為 {h.strategy.value} 時必須註明 strategy_source（客戶設定來源）"))
    if _is_str(h.strategy_source):
        if _is_placeholder(h.strategy_source):
            out.append(_v(sp, "placeholder_text", f"strategy_source 不得是缺值佔位字：{_r(h.strategy_source)}"))
        if _ai_reserved(h.strategy_source):
            out.append(_v(sp, "ai_reserved", f"strategy_source 不得含 AI 字樣：{_r(h.strategy_source)}"))
    out += _check_facts(h.facts, f"{path}.facts")
    return out


def _check_facts(facts: Any, path: str, *, rule_required: bool = False) -> list:
    if not _is_tuple(facts):
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
    `evidence_refs`：不得重複；必須指向本 Digest 內 status ∈ {ok, stale} 的 fact，
    且不得指向趨勢／估值／產業段的 observations（那些只是參考，不是判斷依據）。
    `priority_rank`：沿用既有 Q4 優先序（汰弱＞停利＞趨勢暫停＞加碼）；**執行該順序是 AB-1 的責任**，
    本契約只檢查 ≥1 的整數（numbers.Integral，非 bool）且不重複。
    """
    action_id: str
    text: str
    origin: ActionOrigin
    rule: RuleRef
    evidence_refs: tuple
    target: Optional[HoldingKey] = None
    priority_rank: Optional[int] = None

    def __post_init__(self) -> None:
        _raise_if(_safe(_check_action, self, "action"))


def _check_action(a: Any, path: str) -> list:
    if type(a) is not ActionRef:
        return _type_violation(a, ActionRef, path)
    out: list = _check_key(a.action_id, f"{path}.action_id")
    if not _is_nonempty_str(a.text):
        out.append(_v(f"{path}.text", "blank_str", f"text 必須是非空 str：{_r(a.text)}"))
    elif _is_placeholder(a.text):
        out.append(_v(f"{path}.text", "placeholder_text", f"行動文字不得是缺值佔位字：{_r(a.text)}"))
    if type(a.origin) is not ActionOrigin or a.origin is not ActionOrigin.RULE_LAYER:
        out.append(_v(f"{path}.origin", "non_rule_origin",
                      f"行動來源只允許規則層既有輸出（DEC-092 Q4；AI 不得為行動來源）：{_r(a.origin)}"))
    out += _check_rule_ref(a.rule, f"{path}.rule")
    ev = _check_str_tuple(a.evidence_refs, f"{path}.evidence_refs", nonempty=True, key=True)
    out += ev
    if not ev and len(set(a.evidence_refs)) != len(a.evidence_refs):
        out.append(_v(f"{path}.evidence_refs", "duplicate_evidence_ref", f"evidence_refs 不得重複：{_r(a.evidence_refs)}"))
    if a.target is not None:
        out += _check_holding_key(a.target, f"{path}.target")
    if a.priority_rank is not None and not (_is_integral(a.priority_rank) and a.priority_rank >= 1):
        out.append(_v(f"{path}.priority_rank", "bad_rank",
                      f"priority_rank 若有值必須是 ≥1 的整數：{_r(a.priority_rank)}"))
    return out


# ══════════════════════════════════════════════════════════════════════
# 各段（section）
# ══════════════════════════════════════════════════════════════════════
def _check_section_reason(availability: Any, reason: Any, path: str) -> list:
    if type(availability) is not Availability:
        return [_v(f"{path}.availability", "type", f"availability 必須是 Availability：{_r(availability)}")]
    out: list = []
    if availability is Availability.UNAVAILABLE:
        if type(reason) is not MissingReason:
            out.append(_v(f"{path}.missing_reason", "missing_reason_required",
                          "availability=unavailable 時 missing_reason 必填"))
    elif reason is not None:
        out.append(_v(f"{path}.missing_reason", "missing_reason_on_available",
                      f"availability={availability.value} 時 missing_reason 必須為 None"))
    return out


def _check_derived(declared: Any, derived: Optional[Availability], path: str, prior: list) -> list:
    if prior or type(declared) is not Availability or derived is None:
        return []
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
        _raise_if(_safe(_check_fact_section, self, "section"))


def _check_fact_section(s: Any, path: str) -> list:
    if type(s) is not FactSection:
        return _type_violation(s, FactSection, path)
    out = _check_facts(s.facts, f"{path}.facts")
    out += _check_section_reason(s.availability, s.missing_reason, path)
    derived = derive_availability(s.facts) if _facts_are_inspectable(s.facts) else None
    return out + _check_derived(s.availability, derived, path, out)


@dataclass(frozen=True)
class DefinitionSection:
    """台股趨勢／國際趨勢／產業趨勢／EPS×PE 估值：正式定義未核准前只有定義狀態，沒有結論欄位。

    - `series_ref`：可選的既有圖表序列識別碼（fullmatch `[a-z0-9_.:\\-]+`），**不等於**趨勢判斷（DEC-092 Q2）。
    - `observations`：可選的既有**數值**參考（例：既有指數／均線值；DEC-092 Q2 視覺參考線），
      各自帶來源與規則；⛔ 不得帶 `text`（文字標籤在此就是結論的載體）；unit 須 fullmatch
      `[A-Za-z0-9%._/\\-]*`。只有 tw_trend／intl_trend 可有 observations；
      valuation（research-only，不得有 EPS／PE 數字）與 industry 必須為 `()`（於 validate 檢查）。
    - 方向字樣拒收：series_ref 與 observations 的 fact_id／unit／rule_id／source 不得含
      bull／bear／long／short／up／down／buy／sell／strong／weak／偏多／偏空／強／弱…
      ⚠️ **盡力而為的拒收名單，不是完備判定**（換個拼法就能繞過；真正的防線是 AB-2a grounding）。
    - availability 固定 unavailable；missing_reason 只能是 NOT_DEFINED 或 NOT_WIRED。
    """
    definition: DefinitionState
    missing_reason: MissingReason = MissingReason.NOT_DEFINED
    availability: Availability = Availability.UNAVAILABLE
    series_ref: Optional[str] = None
    observations: tuple = ()

    def __post_init__(self) -> None:
        _raise_if(_safe(_check_definition_section, self, "section"))


def _check_definition_section(s: Any, path: str) -> list:
    if type(s) is not DefinitionSection:
        return _type_violation(s, DefinitionSection, path)
    out: list = []
    if type(s.definition) is not DefinitionState:
        out.append(_v(f"{path}.definition", "type", f"definition 必須是 DefinitionState：{_r(s.definition)}"))
    if s.availability is not Availability.UNAVAILABLE:
        out.append(_v(f"{path}.availability", "undefined_but_available",
                      "定義未核准時 availability 必須為 unavailable（未定義 ≠ 可判斷）"))
    if not (type(s.missing_reason) is MissingReason and s.missing_reason in _DEFINITION_REASONS):
        out.append(_v(f"{path}.missing_reason", "bad_definition_reason",
                      f"定義狀態段的 missing_reason 只能是 NOT_DEFINED／NOT_WIRED：{_r(s.missing_reason)}"))
    if s.series_ref is not None:
        if not (_is_str(s.series_ref) and _SERIES_REF_RE.fullmatch(s.series_ref)):
            out.append(_v(f"{path}.series_ref", "bad_series_ref",
                          f"series_ref 必須 fullmatch [a-z0-9_.:\\-]+：{_r(s.series_ref)}"))
        elif _has_direction_token(s.series_ref):
            out.append(_v(f"{path}.series_ref", "direction_token", f"不得含方向字樣：{_r(s.series_ref)}"))
    out += _check_facts(s.observations, f"{path}.observations", rule_required=True)
    if _is_tuple(s.observations):
        for i, f in enumerate(s.observations):
            if type(f) is not Fact:
                continue
            op = f"{path}.observations[{i}]"
            if f.text is not None:
                out.append(_v(f"{op}.text", "text_in_definition_section",
                              "定義未核准的段只能搬運數值參考，不得帶文字標籤（可能是結論）"))
            if f.unit is not None and not (_is_str(f.unit) and _UNIT_RE.fullmatch(f.unit)):
                out.append(_v(f"{op}.unit", "bad_unit", f"unit 必須 fullmatch [A-Za-z0-9%._/\\-]*：{_r(f.unit)}"))
            idents = [("fact_id", f.fact_id), ("unit", f.unit)]
            if type(f.rule) is RuleRef:
                idents.append(("rule.rule_id", f.rule.rule_id))
            if type(f.provenance) is Provenance:
                idents.append(("provenance.source", f.provenance.source))
            for name, val in idents:
                if _has_direction_token(val):
                    out.append(_v(f"{op}.{name}", "direction_token", f"不得含方向字樣：{_r(val)}"))
    return out


@dataclass(frozen=True)
class HoldingsSection:
    """持股段。

    - availability 依全部 entries 的 facts 推導（0 筆 → unavailable）；
    - `unkeyed_count`：上游缺 portfolio_id 或 symbol 的列數（int ≥ 0）；本契約**不補鍵**。
      >0 時 availability 不得為 available（有 entries → 至多 partial；無 entries → unavailable）。
    - unavailable 時以 missing_reason 區分讀取失敗（FETCH_FAILED）與未綁定（NO_INPUT）。
    """
    availability: Availability
    entries: tuple = ()
    missing_reason: Optional[MissingReason] = None
    unkeyed_count: int = 0

    def __post_init__(self) -> None:
        _raise_if(_safe(_check_holdings_section, self, "holdings"))


def _derive_holdings(s: HoldingsSection) -> Optional[Availability]:
    if not _is_tuple(s.entries) or not all(type(h) is HoldingEntry for h in s.entries):
        return None
    facts = tuple(f for h in s.entries for f in (h.facts if _is_tuple(h.facts) else ()))
    if not _facts_are_inspectable(facts):
        return None
    base = derive_availability(facts) if s.entries else Availability.UNAVAILABLE
    if type(s.unkeyed_count) is int and s.unkeyed_count > 0 and base is Availability.AVAILABLE:
        return Availability.PARTIAL
    return base


def _check_holdings_section(s: Any, path: str) -> list:
    if type(s) is not HoldingsSection:
        return _type_violation(s, HoldingsSection, path)
    out = _check_section_reason(s.availability, s.missing_reason, path)
    if type(s.unkeyed_count) is not int or s.unkeyed_count < 0:
        out.append(_v(f"{path}.unkeyed_count", "bad_unkeyed_count",
                      f"unkeyed_count 必須是 ≥0 的 int（bool 拒收）：{_r(s.unkeyed_count)}"))
    if not _is_tuple(s.entries):
        return out + [_v(f"{path}.entries", "not_tuple", "entries 必須是 tuple")]
    seen: dict = {}
    for i, h in enumerate(s.entries):
        out += _check_holding_entry(h, f"{path}.entries[{i}]")
        k = _hashable_key(h.key) if type(h) is HoldingEntry else None
        if k is not None:
            if k in seen:
                out.append(_v(f"{path}.entries[{i}].key", "duplicate_holding_key",
                              f"(portfolio_id, symbol) 重複：與 entries[{seen[k]}] 相同 {_r(k)}"))
            else:
                seen[k] = i
    return out + _check_derived(s.availability, _derive_holdings(s) if not out else None, path, out)


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
        _raise_if(_safe(_check_risk_cap_section, self, "risk_cap"))

    @property
    def facts(self) -> tuple:
        return (self.cap_pct, self.exposure_lo_pct, self.exposure_hi_pct)


def _check_risk_cap_section(s: Any, path: str) -> list:
    if type(s) is not RiskCapSection:
        return _type_violation(s, RiskCapSection, path)
    out: list = []
    if type(s.cap_valid) is not bool:
        out.append(_v(f"{path}.cap_valid", "type", f"cap_valid 必須恰好是 bool：{_r(s.cap_valid)}"))
    for name in ("cap_pct", "exposure_lo_pct", "exposure_hi_pct"):
        f = getattr(s, name)
        out += _check_fact(f, f"{path}.{name}", rule_required=True)
        if type(f) is Fact:
            if f.text is not None:
                out.append(_v(f"{path}.{name}.text", "text_on_numeric", "此處只承載數值，text 必須為 None"))
            if _is_real_number(f.value) and not (0 <= f.value <= 100):
                out.append(_v(f"{path}.{name}.value", "pct_out_of_domain",
                              f"百分比必須在 [0, 100]：{_r(f.value)}"))
    cap = s.cap_pct
    if type(cap) is Fact and type(cap.status) is DataStatus:
        if s.cap_valid is False and (cap.value is not None or cap.status is DataStatus.OK):
            out.append(_v(f"{path}.cap_pct", "invalid_cap_has_value",
                          "cap_valid=False 時 cap_pct 必須 value=None 且 status 非 ok（無法判定）"))
        if s.cap_valid is True and (cap.value is None
                                    or cap.status not in (DataStatus.OK, DataStatus.STALE)):
            out.append(_v(f"{path}.cap_pct", "valid_cap_without_value",
                          "cap_valid=True 時 cap_pct 必須有值且 status ∈ {ok, stale}"))
    lo, hi = s.exposure_lo_pct, s.exposure_hi_pct
    if (type(lo) is Fact and type(hi) is Fact
            and _is_real_number(lo.value) and _is_real_number(hi.value) and lo.value > hi.value):
        out.append(_v(path, "exposure_lo_gt_hi", f"exposure_lo_pct({_r(lo.value)}) > exposure_hi_pct({_r(hi.value)})"))
    out += _check_section_reason(s.availability, s.missing_reason, path)
    trio = (cap, lo, hi)
    derived = derive_availability(trio) if _facts_are_inspectable(trio) else None
    return out + _check_derived(s.availability, derived, path, out)


@dataclass(frozen=True)
class ActionsSection:
    """本期行動（0..3 項）。availability 只允許 available／unavailable（⛔ partial）。

    - unavailable＝判不出來：必須 0 筆行動且附 missing_reason；
    - available 且 0 筆＝「規則層未產出行動」，**明文合法**（不得湊數）；
    - ⚠️ 一致性規則（不是投資規則）：available 要求 holdings 不是 unavailable（於 validate 檢查）——
      持股都讀不到時，「沒有要做的事」與「判不出來」無法區分，不得顯示成前者。
    """
    availability: Availability
    items: tuple = ()
    missing_reason: Optional[MissingReason] = None

    def __post_init__(self) -> None:
        _raise_if(_safe(_check_actions_section, self, "actions"))


def _check_actions_section(s: Any, path: str) -> list:
    if type(s) is not ActionsSection:
        return _type_violation(s, ActionsSection, path)
    out = _check_section_reason(s.availability, s.missing_reason, path)
    if s.availability is Availability.PARTIAL:
        out.append(_v(f"{path}.availability", "partial_actions",
                      "行動段只允許 available／unavailable（行動不是可以「部分可得」的資料）"))
    if not _is_tuple(s.items):
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
        if type(a) is not ActionRef:
            continue
        if _key_problem(a.action_id) is None:
            if a.action_id in ids:
                out.append(_v(f"{path}.items[{i}].action_id", "duplicate_action_id", _r(a.action_id)))
            ids.add(a.action_id)
        r = a.priority_rank
        if _is_integral(r):
            ri = int(r)
            if ri in ranks:
                out.append(_v(f"{path}.items[{i}].priority_rank", "duplicate_rank", _r(ri)))
            ranks.add(ri)
    return out


# ══════════════════════════════════════════════════════════════════════
# 根
# ══════════════════════════════════════════════════════════════════════
#: 各定義狀態段必須綁定的定義狀態。
_SECTION_DEFINITION: dict = {
    "tw_trend": DefinitionState.NOT_DEFINED,
    "intl_trend": DefinitionState.NOT_DEFINED,
    "industry": DefinitionState.NOT_DEFINED,
    "valuation": DefinitionState.RESEARCH_ONLY,
}
#: 不得有 observations 的定義狀態段（valuation：research-only 不得有 EPS／PE 數字）。
_NO_OBSERVATION_SECTIONS: tuple = ("valuation", "industry")


@dataclass(frozen=True)
class DecisionDigest:
    """Decision Digest 根。建構時**不**做跨物件檢查；請以 `assert_valid` 收口（`to_dict` 會自動呼叫）。

    - `generated_at`：tz-aware UTC（時區規則見模組 docstring）。
    - `ai_passed_checks`：AI_EXPLAINED 時必填（非空，G1～G6，不重複）。
    - `ai_failed_checks`：AI_REJECTED 時必填（同格式）。RULE_ONLY 時兩者皆須為空；兩者不得交集。
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
    ai_participation: AiParticipation = AiParticipation.RULE_ONLY
    ai_passed_checks: tuple = ()
    ai_failed_checks: tuple = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        assert_valid(self)
        return _to_jsonable(self)


def _all_facts(d: DecisionDigest) -> list:
    """(path, Fact, is_observation) 全列表（供 fact_id 唯一性、evidence_refs 解析與時間一致性）。"""
    out: list = []

    def add(path: str, facts: Any, obs: bool = False) -> None:
        if _is_tuple(facts):
            out.extend((f"{path}[{i}]", f, obs) for i, f in enumerate(facts) if type(f) is Fact)
    m = getattr(d, "market", None)
    if type(m) is FactSection:
        add("market.facts", m.facts)
    for name in _SECTION_DEFINITION:
        s = getattr(d, name, None)
        if type(s) is DefinitionSection:
            add(f"{name}.observations", s.observations, obs=True)
    hs = getattr(d, "holdings", None)
    if type(hs) is HoldingsSection and _is_tuple(hs.entries):
        for i, h in enumerate(hs.entries):
            if type(h) is HoldingEntry:
                add(f"holdings.entries[{i}].facts", h.facts)
    rc = getattr(d, "risk_cap", None)
    if type(rc) is RiskCapSection:
        for name in ("cap_pct", "exposure_lo_pct", "exposure_hi_pct"):
            f = getattr(rc, name, None)
            if type(f) is Fact:
                out.append((f"risk_cap.{name}", f, False))
    return out


def _check_root(d: DecisionDigest, path: str) -> list:
    out: list = []
    if d.schema_version != SCHEMA_VERSION or not _is_str(d.schema_version):
        out.append(_v("schema_version", "schema_version_mismatch",
                      f"期望 {SCHEMA_VERSION!r}，實得 {_r(d.schema_version)}"))
    gen_ok = _is_aware(d.generated_at)
    if not gen_ok:
        out.append(_v("generated_at", "naive_datetime",
                      f"generated_at 必須是 tz-aware datetime：{_r(d.generated_at)}"))
    elif d.generated_at.utcoffset() != timedelta(0):
        out.append(_v("generated_at", "generated_at_not_utc", f"generated_at 必須是 UTC：{_r(d.generated_at)}"))
        gen_ok = False

    # 定義狀態段綁定
    for name, want in _SECTION_DEFINITION.items():
        s = getattr(d, name, None)
        if type(s) is not DefinitionSection:
            continue
        if type(s.definition) is DefinitionState and s.definition is not want:
            out.append(_v(f"{name}.definition", "definition_binding",
                          f"{name} 的 definition 必須是 {want.value}：實得 {s.definition.value}"))
        if name in _NO_OBSERVATION_SECTIONS and s.observations != ():
            out.append(_v(f"{name}.observations", "observations_forbidden",
                          f"{name} 不得有 observations（research-only／未定義，不得帶數字）"))

    # AI 參與
    ap = d.ai_participation
    if type(ap) is not AiParticipation:
        out.append(_v("ai_participation", "type", f"必須是 AiParticipation：{_r(ap)}"))
    else:
        passed_v = _check_check_ids(d.ai_passed_checks, "ai_passed_checks")
        failed_v = _check_check_ids(d.ai_failed_checks, "ai_failed_checks")
        out += passed_v + failed_v
        passed = d.ai_passed_checks if not passed_v else ()
        failed = d.ai_failed_checks if not failed_v else ()
        if set(passed) & set(failed):
            out.append(_v("ai_failed_checks", "check_in_both",
                          f"同一檢查不得同時通過與未通過：{_r(sorted(set(passed) & set(failed)))}"))
        if ap is AiParticipation.RULE_ONLY and (passed or failed):
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
    for p, f, obs in facts:
        if _key_problem(f.fact_id) is None:
            if f.fact_id in fact_by_id:
                out.append(_v(f"{p}.fact_id", "duplicate_fact_id",
                              f"{_r(f.fact_id)} 與 {fact_by_id[f.fact_id][0]} 重複"))
            else:
                fact_by_id[f.fact_id] = (p, f, obs)
        pv = f.provenance
        if gen_ok and type(pv) is Provenance:
            if _is_aware(pv.fetched_at) and pv.fetched_at > d.generated_at:
                out.append(_v(f"{p}.provenance.fetched_at", "fetched_after_generated",
                              f"fetched_at({_r(pv.fetched_at)}) 晚於 generated_at({_r(d.generated_at)})"))
            if _is_plain_date(pv.as_of) and pv.as_of > gen_tw_date:
                out.append(_v(f"{p}.provenance.as_of", "as_of_after_generated",
                              f"as_of({pv.as_of}) 晚於 generated_at 的台北日期 {gen_tw_date}"))

    # 行動 vs 持股一致性（不是投資規則）
    hs, acts = d.holdings, d.actions
    if (type(acts) is ActionsSection and acts.availability is Availability.AVAILABLE
            and type(hs) is HoldingsSection and hs.availability is Availability.UNAVAILABLE):
        out.append(_v("actions.availability", "actions_available_without_holdings",
                      "holdings 為 unavailable 時 actions 不得為 available（「無行動」≠「判不出來」）"))

    # 行動：evidence 指向可用、非參考 fact；target 在 holdings 內
    holding_keys: set = set()
    if type(hs) is HoldingsSection and _is_tuple(hs.entries):
        holding_keys = {k for k in (_hashable_key(getattr(h, "key", None)) for h in hs.entries
                                    if type(h) is HoldingEntry) if k is not None}
    if type(acts) is ActionsSection and _is_tuple(acts.items):
        for i, a in enumerate(acts.items):
            if type(a) is not ActionRef:
                continue
            if _is_tuple(a.evidence_refs):
                for j, ref in enumerate(a.evidence_refs):
                    if _key_problem(ref) is not None:
                        continue
                    hit = fact_by_id.get(ref)
                    rp = f"actions.items[{i}].evidence_refs[{j}]"
                    if hit is None:
                        out.append(_v(rp, "dangling_evidence_ref", f"{_r(ref)} 不是本 Digest 內任何 fact_id"))
                        continue
                    _, hf, obs = hit
                    if obs:
                        out.append(_v(rp, "evidence_on_observation",
                                      f"{_r(ref)} 是定義未核准段的參考數值，不得當行動依據"))
                    if type(hf.status) is DataStatus and hf.status not in _EVIDENCE_STATUSES:
                        out.append(_v(rp, "evidence_on_unusable_fact",
                                      f"{_r(ref)} 指向 status={hf.status.value} 的 fact（只允許 ok／stale）"))
            if a.target is not None:
                tk = _hashable_key(a.target)
                if tk is not None and tk not in holding_keys:
                    out.append(_v(f"actions.items[{i}].target", "target_not_in_holdings",
                                  f"{_r(a.target)} 不在 holdings 內（行動不得指向 Digest 外的標的）"))
    return out


def validate(digest: Any) -> tuple:
    """純函式：回傳 digest 的**全部**契約違規（空 tuple＝合規）。任何輸入都不 raise。"""
    if type(digest) is not DecisionDigest:
        return tuple(_type_violation(digest, DecisionDigest, "digest"))
    d = digest
    out: list = []
    out += _safe(lambda o, p: _check_fact_section(getattr(o, "market"), p), d, "market")
    for name in _SECTION_DEFINITION:
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
_CONTRACT_CLASSES: tuple = (
    Provenance, RuleRef, Fact, HoldingKey, HoldingEntry, ActionRef, FactSection, DefinitionSection,
    HoldingsSection, RiskCapSection, ActionsSection, DecisionDigest,
)


def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Enum):  # 須在 str 之前：本檔列舉皆繼承 str
        return str(obj.value)
    if isinstance(obj, bool):
        return bool(obj)
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
    for cls in _CONTRACT_CLASSES:
        if isinstance(obj, cls):  # 只輸出契約類別宣告的欄位（子類別夾帶欄位不輸出）
            return {f.name: _to_jsonable(getattr(obj, f.name)) for f in fields(cls)}
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
