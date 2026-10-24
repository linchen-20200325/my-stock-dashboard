"""shared/input_provenance_policy.py — 引擎輸入「資料身分 × 新鮮度」兩軸契約與計分資格規則（L0 純規則，零 I/O）。

C2a-1（契約層，2026-10-24）。⛔ **本批只新增契約，不接線**：沒有任何產品程式 import 本檔；
Risk Cap 分數、門檻、權重、公式、Required Core、`RISK_CAP_RULESET_VERSION` 一律不變。

客戶裁示 DEC-080（摘要，本檔依此落地）
──────────────────────────────────────
- 資料契約兩軸：**provenance** ∈ {official, secondary, estimated, proxy, unavailable}
  × **freshness** ∈ {fresh, stale, carried_forward}；另保留 `as_of`、`source_id`。
- ⛔ 不得把 exists／fresh／displayable／scoring_eligible／riskcap_eligible 壓成同一個 boolean ——
  `classify_eligibility` 一律回五個欄位、分開存放。
- BIAS240 短窗估算（estimated）、PCR 三大法人估算（proxy，detail `proxy_estimate`）未來不參與 Risk Cap。
- 台灣 PMI：data.gov.tw／NDC／CIER＝official；同一序列的第三方轉載（StockFeel／Cnyes／MoneyDJ）＝secondary，
  可滿足 Core（須揭露來源）。
- carried_forward 只在「正式定義」的發布期內可滿足 Core —— **總管已判定目前沒有正式定義**，
  故一律記 `PENDING_SPEC`（`"undetermined_pending_spec"`）。⛔ 不得新增任何天數常數、
  ⛔ 不得引用 `shared.staleness` 的常數頂替（`carried_forward_window` 全表為 None）。

總管拍板（C2a-1 規格）
──────────────────────
- VIX（yfinance ^VIX，轉載 CBOE）、MA5（yfinance ^TWII，轉載 TWSE 指數）、外資期貨（FinMind 鏡像 TAIFEX）、
  BIAS240 非估算（yfinance ^TWII 序列）＝ **secondary**：轉載正式序列（總管判定；DEC-080 下
  official／secondary 皆可滿足 Core，不影響資格）。
- `Provenance` 嚴格五值，⛔ 不加 unknown：判不出來由呼叫端記 None ＋ basis（說明為什麼判不出來）。
- `FreshnessAxis` 是**新的**三值軸，與既有 `shared.freshness_policy.FreshnessStatus`（四值：
  fresh／stale／missing／undetermined）**並存、不取代**；後者照舊是計分新鮮度的 SSOT。
  對映（L2 `src/compute/macro/input_provenance.py` 負責）：STALE→stale；FRESH 且上游帶舊快照標記
  →carried_forward；FRESH→fresh；MISSING／UNDETERMINED→None（缺值由 provenance 的 unavailable 表達）。
- DEC-080 第 4 點「超過允許期間 → `unavailable`」在兩軸下的對映（總管規格）：**provenance 保留**原身分
  （例：stale-cache(CIER) 仍記 official，不改寫成 unavailable —— 身分是「這個數字從哪來」，與「還能不能用」
  分屬兩軸），**freshness＝stale**，**eligibility＝False**（Required Core 無效 → 不產生新的 Risk Cap，
  與 DEC-048 同向）。「是否超過允許期間」目前一律由既有 `FreshnessStatus`（月頻依資料月＋發布期）判定；
  STALE **優先於** carried_forward（舊快照標記不得把已過期的值翻成「沿用」）。provenance＝unavailable
  只用於「沒有值」。
- `SHADOW_POLICY_VERSION` 只是本契約的版本，與 `RISK_CAP_RULESET_VERSION` 無關（⛔ 不升 Risk Cap 版本）。

`scoring_eligible` 與 `riskcap_eligible`
────────────────────────────────────────
`scoring_eligible` 的射程**只限 Risk Cap 引擎**（16 燈／五桶的計分資格屬 DEC-076 ①，不在本檔）；
規則目前與 `riskcap_eligible` 相同，但**分開存放** —— 日後兩者若因裁示分岔，不必改資料形狀。
判定順序（第一個成立者為準；值為 `True`／`False`／`PENDING_SPEC`）：
1. 輸入鍵未登錄於 `INPUT_POLICY` → False（不猜）；
2. role 為 disabled（規則版本依定義停用，例：M1B／M2）→ False；
3. 不存在（exists 不是 True）→ False；
4. provenance 判不出來（None）或不在 `RISKCAP_ALLOWED_PROVENANCE`（estimated／proxy／unavailable）→ False；
5. freshness 為 stale 或判不出來（None）→ False；
6. freshness 為 carried_forward → `PENDING_SPEC`（無正式發布期定義；**永不 True**）；
7. official／secondary 且 fresh → True。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫；⛔ 不 import L1（PCR 來源欄名、PMI 來源標籤
一律以字面寫，與 L1 的一致性由 `tests/test_c2a_input_provenance.py` 以 import／AST 守住）。
import 時不做任何驗證、不 raise。
"""
from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, NamedTuple


class Provenance(str, Enum):
    """資料身分（DEC-080 五值；⛔ 不加 unknown —— 判不出來記 None ＋ basis）。"""

    OFFICIAL = "official"         # 主要發布者的正式序列
    SECONDARY = "secondary"       # 同一正式序列的轉載／鏡像（非主要發布者）
    ESTIMATED = "estimated"       # 同一個量的近似算法（例：BIAS240 短窗均線）
    PROXY = "proxy"               # 不同的量拿來替代（例：TXO 三大法人 OI 比）
    UNAVAILABLE = "unavailable"   # 沒有可用值


class FreshnessAxis(str, Enum):
    """新鮮度軸（DEC-080 三值）。與 `shared.freshness_policy.FreshnessStatus` 並存、不取代。"""

    FRESH = "fresh"
    STALE = "stale"
    CARRIED_FORWARD = "carried_forward"   # 上游沿用舊快照（例：PMI stale-cache、先行指標 stale pickle）


#: carried_forward 的資格值：正式發布期定義待規格（總管判定目前無正式定義）。
PENDING_SPEC: str = "undetermined_pending_spec"

#: 本契約（shadow 分類）的版本。⛔ 與 `shared.risk_cap_policy.RISK_CAP_RULESET_VERSION` 無關、不連動。
SHADOW_POLICY_VERSION: str = "c2a-shadow-1"

#: Risk Cap 允許的 provenance（DEC-080：official／secondary 皆可滿足 Core）。
RISKCAP_ALLOWED_PROVENANCE: frozenset = frozenset({Provenance.OFFICIAL, Provenance.SECONDARY})


# ══════════════════════════════════════════════════════════════════════
# PCR：逐日來源標籤 → provenance
# ══════════════════════════════════════════════════════════════════════

#: 先行指標表的逐日 PCR 來源欄名（L1 `leading_indicators` 寫入；L0 不得 import L1，故以字面寫，
#: 一致性由測試守住）。
PCR_SOURCE_COLUMN: str = "_pcr_src"

#: PCR 來源標籤 → (provenance, provenance_detail)。精確比對，⛔ 不做 substring。
#: 「TAIFEX」＝期交所 pcRatio 全市場正式值；「FinMind-TXO-inst-est」＝只含三大法人部位的估算 ——
#: 是**另一個量**，故記 proxy、detail 沿用 L1 的來源種類字樣 `proxy_estimate`。
PCR_LABEL_PROVENANCE: Mapping[str, tuple[Provenance, str | None]] = MappingProxyType({
    "TAIFEX": (Provenance.OFFICIAL, None),
    "FinMind-TXO-inst-est": (Provenance.PROXY, "proxy_estimate"),
})


# ══════════════════════════════════════════════════════════════════════
# 台灣 PMI：來源標籤 → provenance（當期＋前月同一張表）
# ══════════════════════════════════════════════════════════════════════

#: 正式發布者（中經院 CIER 系列、政府開放資料 data.gov.tw 6100、國發會 NDC）。
#: 「data.gov.tw:dataset:6100」是 cron（`scripts/update_macro_history.py`）寫進 PMI 歷史 parquet 的
#: 前月來源字樣；其餘是 L1 `macro_core` 當期 8 源賽跑各源回傳的 `source` 字面值。
PMI_OFFICIAL_SOURCE_LABELS: frozenset = frozenset({
    "CIER-EN",
    "CIER",
    "data.gov.tw/6100",
    "NDC",
    "data.gov.tw:dataset:6100",
})

#: 同一序列的第三方轉載（DEC-080：secondary，可滿足 Core＋揭露）。
PMI_SECONDARY_SOURCE_LABELS: frozenset = frozenset({
    "StockFeel",
    "Cnyes",
    "MoneyDJ",
})

#: 8 源全敗、也沒有快取時的來源字樣（此時值為 None ⇒ unavailable）。
PMI_FAILURE_SOURCE_LABELS: frozenset = frozenset({"TW_PMI:all_tiers_failed"})

#: 8 源全敗改用快取時，L1 把來源包成「stale-cache(原來源)」。只剝**一層**取原來源查表，
#: freshness 記 carried_forward（快取保留原資料月，是否在發布期內由 `assess_monthly` 判）。
PMI_STALE_CACHE_PREFIX: str = "stale-cache("
PMI_STALE_CACHE_SUFFIX: str = ")"

#: PMI 來源標籤 → provenance（精確比對，⛔ 不做 substring）。
PMI_LABEL_PROVENANCE: Mapping[str, Provenance] = MappingProxyType({
    **{lbl: Provenance.OFFICIAL for lbl in PMI_OFFICIAL_SOURCE_LABELS},
    **{lbl: Provenance.SECONDARY for lbl in PMI_SECONDARY_SOURCE_LABELS},
    **{lbl: Provenance.UNAVAILABLE for lbl in PMI_FAILURE_SOURCE_LABELS},
})


# ══════════════════════════════════════════════════════════════════════
# provenance_detail 字樣（機器可讀；人讀的說明放 basis）
# ══════════════════════════════════════════════════════════════════════
DETAIL_PCR_PROXY_ESTIMATE: str = "proxy_estimate"
DETAIL_BIAS_SHORT_WINDOW: str = "short_window_ma"          # BIAS240 以可得天數均線頂替 MA240
DETAIL_PMI_STALE_CACHE: str = "stale_cache"                # PMI 8 源全敗改用快取
DETAIL_M1B_TWII_PROXY: str = "twii_momentum_proxy"         # M1B／M2 以 ^TWII 動能代理


# ══════════════════════════════════════════════════════════════════════
# M1B／M2：只有央行（CBC）來源記 official
# ══════════════════════════════════════════════════════════════════════
#: L1 `macro_snapshot.fetch_m1b_m2_block` 走 CBC（tw_macro Tier 1／2）時寫進 `m1b_m2_info['source']`
#: 的字面值（`f'CBC-tier{tier_used}'`，tier_used ∈ {1, 2}；Tier 3 是 ^TWII 代理，另由
#: `shared.macro_provenance` 判定）。精確比對。
M1B_CBC_SOURCE_LABELS: frozenset = frozenset({"CBC-tier1", "CBC-tier2"})
#: L1 `tw_macro.fetch_cbc_m1b_m2` 的原生來源字樣前綴（例：`CBC:ms1.json:tier1`、`CBC:EF15M01:tier2`；
#: 若日後呼叫端改為直接透傳）。
M1B_CBC_SOURCE_PREFIX: str = "CBC:"


# ══════════════════════════════════════════════════════════════════════
# 每個引擎輸入一列
# ══════════════════════════════════════════════════════════════════════
ROLE_REQUIRED_CORE: str = "required_core"
ROLE_OPTIONAL: str = "optional"
ROLE_DISABLED: str = "disabled"
ROLES: frozenset = frozenset({ROLE_REQUIRED_CORE, ROLE_OPTIONAL, ROLE_DISABLED})

_BASIS_SECONDARY_REPOST = "轉載正式序列（總管判定，DEC-080 下 official/secondary 皆可滿足 Core，不影響資格）"


class InputPolicy(NamedTuple):
    """一個引擎輸入的身分規則。

    Attributes:
        role: `required_core`／`optional`／`disabled`（對齊 `shared.risk_cap_policy` 的
            `REQUIRED_CORE_INPUTS`／`OPTIONAL_INPUTS`／`RULESET_DISABLED_INPUTS[現行版本]`，測試守住）。
        normal_provenance: 正常運作時的 provenance（逐次觀測可能不同，例：PCR 混源、PMI 8 源）。
        provenance_basis: normal_provenance 的依據（人讀）。
        riskcap_allowed_provenance: 可用於 Risk Cap 的 provenance 集合。
        carried_forward_window: carried_forward 的正式發布期定義 —— **目前一律 None**（無正式定義，
            ⛔ 不得填天數）。c2a-shadow-1 的 `classify_eligibility` 對 carried_forward 一律回 `PENDING_SPEC`。
    """

    role: str
    normal_provenance: Provenance
    provenance_basis: str
    riskcap_allowed_provenance: frozenset
    carried_forward_window: Any


#: 引擎輸入名 → 身分規則。鍵集合＝`shared.freshness_policy.FRESHNESS_POLICY` 的鍵
#: ＝ Required Core ∪ Optional（含停用的 M1B／M2）。鍵名以字面寫（L0 不得 import L2 `dated_inputs`）。
INPUT_POLICY: Mapping[str, InputPolicy] = MappingProxyType({
    "VIX_Index": InputPolicy(
        ROLE_REQUIRED_CORE, Provenance.SECONDARY,
        "yfinance ^VIX 日線，轉載 CBOE VIX；" + _BASIS_SECONDARY_REPOST,
        RISKCAP_ALLOWED_PROVENANCE, None),
    "ISM_PMI_or_OECD_CLI": InputPolicy(
        ROLE_REQUIRED_CORE, Provenance.OFFICIAL,
        "台灣 PMI 當期：逐次依 L1 來源標籤查 PMI_LABEL_PROVENANCE（CIER／data.gov.tw／NDC＝official；"
        "StockFeel／Cnyes／MoneyDJ 轉載＝secondary；stale-cache(X) 剝一層取 X、freshness＝carried_forward）；"
        "正常首選 CIER-EN＝official（DEC-080）",
        RISKCAP_ALLOWED_PROVENANCE, None),
    "PMI_Prev_Month": InputPolicy(
        ROLE_REQUIRED_CORE, Provenance.OFFICIAL,
        "台灣 PMI 前一資料月：PMI 歷史 parquet 該資料月列的來源標籤查 PMI_LABEL_PROVENANCE；"
        "cron 固定寫 data.gov.tw:dataset:6100＝official（DEC-080）",
        RISKCAP_ALLOWED_PROVENANCE, None),
    "Futures_Net_Short": InputPolicy(
        ROLE_REQUIRED_CORE, Provenance.SECONDARY,
        "FinMind 外資期貨未平倉，鏡像 TAIFEX 三大法人期貨部位；" + _BASIS_SECONDARY_REPOST,
        RISKCAP_ALLOWED_PROVENANCE, None),
    "Index_Below_MA5": InputPolicy(
        ROLE_REQUIRED_CORE, Provenance.SECONDARY,
        "yfinance ^TWII 收盤對 MA5，轉載 TWSE 加權指數；" + _BASIS_SECONDARY_REPOST,
        RISKCAP_ALLOWED_PROVENANCE, None),
    "BIAS240_pct": InputPolicy(
        ROLE_OPTIONAL, Provenance.SECONDARY,
        "非估算（足 240 日）：yfinance ^TWII 收盤序列算 MA240 乖離，" + _BASIS_SECONDARY_REPOST
        + "；不足 240 日以短窗均線頂替＝estimated（DEC-080：不參與 Risk Cap）",
        RISKCAP_ALLOWED_PROVENANCE, None),
    "PCR": InputPolicy(
        ROLE_OPTIONAL, Provenance.OFFICIAL,
        "逐日依先行指標表來源欄查 PCR_LABEL_PROVENANCE：TAIFEX pcRatio＝official；"
        "FinMind TXO 三大法人估算＝proxy（proxy_estimate，DEC-080：不參與 Risk Cap）",
        RISKCAP_ALLOWED_PROVENANCE, None),
    "M1B_YoY_pct": InputPolicy(
        ROLE_DISABLED, Provenance.OFFICIAL,
        "央行 M1B 年增率（CBC 來源標籤）＝official；^TWII 動能代理＝proxy；FRED／IMF 等非央行來源 → None"
        "（IMF 為 USD 計價，§4.1 禁止跨幣別混用；不猜）；"
        "risk_cap.v2 依定義停用 M1B-M2 腿（不計分、不算未評估）",
        RISKCAP_ALLOWED_PROVENANCE, None),
    "M2_YoY_pct": InputPolicy(
        ROLE_DISABLED, Provenance.OFFICIAL,
        "央行 M2 年增率（CBC 來源標籤）＝official；^TWII 動能代理＝proxy；FRED／IMF 等非央行來源 → None"
        "（IMF 為 USD 計價，§4.1 禁止跨幣別混用；不猜）；"
        "risk_cap.v2 依定義停用 M1B-M2 腿（不計分、不算未評估）",
        RISKCAP_ALLOWED_PROVENANCE, None),
})


# ══════════════════════════════════════════════════════════════════════
# 計分資格（純函式；⛔ 不 raise —— 型別不符一律當「判不出來」）
# ══════════════════════════════════════════════════════════════════════

#: `classify_eligibility` 回傳的五個欄位（順序即報告順序）。
ELIGIBILITY_FIELDS: tuple[str, ...] = (
    "exists", "fresh", "displayable", "scoring_eligible", "riskcap_eligible",
)


def is_strict_true(v: Any) -> bool:
    """Python `True` 或 numpy `bool_(True)` 才算 True（1、"true" 不算）。

    L0 與 L2 `input_provenance`（上游舊快照標記）共用同一份判定（⛔ 不各寫一份）。
    """
    if v is True:
        return True
    return (type(v).__module__ == "numpy" and type(v).__name__ in ("bool", "bool_")
            and bool(v) is True)


def _coerce_enum(enum_cls: type, v: Any) -> Any:
    """enum 成員或其字串值 → 成員；其餘（None、未知字串、其他型別）→ None。"""
    if isinstance(v, enum_cls):
        return v
    if isinstance(v, str):
        try:
            return enum_cls(v)
        except ValueError:
            return None
    return None


def _eligibility(policy: InputPolicy | None, prov: Provenance | None,
                 fresh_axis: FreshnessAxis | None, exists: bool) -> bool | str:
    """檔頭「判定順序」1～7（Risk Cap 射程）。回 True／False／`PENDING_SPEC`。"""
    if policy is None:                                         # 1. 未登錄
        return False
    if policy.role == ROLE_DISABLED:                           # 2. 停用
        return False
    if not exists:                                             # 3. 不存在
        return False
    if prov is None or prov not in policy.riskcap_allowed_provenance:   # 4. 身分
        return False
    if fresh_axis is None or fresh_axis == FreshnessAxis.STALE:         # 5. 過期／判不出
        return False
    if fresh_axis == FreshnessAxis.CARRIED_FORWARD:            # 6. 無正式發布期定義
        # c2a-shadow-1：`carried_forward_window` 全表為 None（無正式定義）⇒ 一律待規格。
        # ⛔ 日後即使填入窗值，本版也不評估窗內外（須另行裁示並升 SHADOW_POLICY_VERSION）。
        return PENDING_SPEC
    return True                                                # 7. official／secondary＋fresh


def classify_eligibility(*, input_key: Any, provenance: Any, freshness: Any,
                         exists: Any) -> dict[str, bool | str]:
    """一個輸入的五欄資格（⛔ 不壓成單一 boolean；DEC-080）。

    Args:
        input_key: 引擎輸入名（`INPUT_POLICY` 的鍵）；未登錄 → 兩個 eligible 皆 False。
        provenance: `Provenance` 成員或其字串值；None／未知 → 視為判不出來。
        freshness: `FreshnessAxis` 成員或其字串值；None／未知 → 視為判不出來。
        exists: 是否有觀測值；只有 Python `True`（或 numpy `True`）才算存在。

    Returns:
        `{exists, fresh, displayable, scoring_eligible, riskcap_eligible}`：
        - `exists`：bool；`displayable` ＝ `exists`（DEC-080：有值即可顯示，身分由標籤揭露）；
        - `fresh`：bool，只有 freshness＝fresh 才 True（carried_forward／stale 皆 False）；
        - `scoring_eligible`／`riskcap_eligible`：True／False／`PENDING_SPEC`（規則見檔頭）。
    """
    policy = INPUT_POLICY.get(input_key) if isinstance(input_key, str) else None
    prov = _coerce_enum(Provenance, provenance)
    fresh_axis = _coerce_enum(FreshnessAxis, freshness)
    ex = is_strict_true(exists)
    verdict = _eligibility(policy, prov, fresh_axis, ex)
    return {
        "exists": ex,
        "fresh": fresh_axis == FreshnessAxis.FRESH,
        "displayable": ex,
        "scoring_eligible": verdict,
        "riskcap_eligible": verdict,
    }
