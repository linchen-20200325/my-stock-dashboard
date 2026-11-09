"""Real-data Preview：snapshot（既有 canonical service 的原樣結果）→ canonical dict → 既有 VM builder。

NUI2-REAL-FEED A2（客戶 2026-11-03 (11)）。**純函式**（G2 照掃：⛔ streamlit／I/O／session_state／時鐘）。
唯一做 I/O 的檔是 `real_feed.py`（G2F 守衛）；本檔**不** import 它（依賴方向：feed → 本檔）。

只接 **2 個**已確認 canonical、無 session 寫入、無網路、自帶 provenance 的事實（mapping 見
`docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md`）：
1. 台股加權指數（`market_twii_view_service.get_twii_trend_view`）→ 📊 `cards.twii`。
2. 市場位階（`allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)`）→ 📊 `current_state`、
   🎯 `context_rows.market_regime`、🎯 `lookup.snapshot.dim_market_env`——三處吃**同一個** `RegimeFact`
   （同一次呼叫結果；跨頁一致性測試鎖定）。
其餘欄位一律 capability `⬜ 尚未提供`＋原因（⛔ FAKE 值、⛔ 補 0／中性／safe）；契約固定欄（Risk Cap
`⬜ 無法判定`、目前曝險 `⬜ 資料未備`、趨勢／產業 `⬜ 尚未定義`、動作欄待 Aggregator）照凍結契約。

═══ 語意映射（AI 總管內部判準標「可推翻」者，登記於 BACKLOG `NUI2-REAL-FEED` 段）═══
台股：
- 讀取丟例外（feed 接住）→ Unavailable；`failed=True` → Unavailable；`ok=False, failed=False` → Missing `⬜ 資料未取得`。
  畫面錯誤句＝固定人話句（⛔ 例外型別名、⛔ 訊息原文；型別名只留 snapshot 內部代碼與 log）；`upstream_error` 只顯示「上游最近一次抓取失敗」。
- `is_stale=True` → Stale `⚠ 過期 N 天`（N＝`age_days`；None → `⚠ 可能已過期`）。
- `is_stale=None` → Stale `⚠ 可能已過期`（**AI 總管內部判準，可推翻**：新鮮度未知 ⛔ 當 OK；service 檔頭明文
  「attrs 缺 → is_stale=None（⬜ 未判定），⛔ 不當成新鮮」）。
- `ok=True` 但無收盤值／非有限數、`is_stale` 非 bool／None → 契約違反（見 `RealFeedContractError`：讀取期隔離、
  該欄紅色 Unavailable＋log、另一事實照常）。
市場位階：
- 讀取丟例外（strict：「讀壞了」≠「未評估」）→ Unavailable。
- `is_loaded=True` → OK＋`shared.allocation_decision.REGIME_LABEL`（全站統一顯示字；⛔ 另寫一份）。
- `source=unloaded`（冷啟動；UI2 Preview 不跑更新鏈，故恆為此態）→ Not Evaluated `⬜ 尚未載入`＋L0
  `NOT_LOADED_PENDING_BREADTH_EXPLAIN`（DH-REGIME-NOWARROOM 既有說明）。
- `source=unevaluated:breadth_unavailable` → Unable to Determine `⬜ 未評估／資料不足`（DEC-074／075 客戶逐字；
  DEC-124 歸類）＋L0 `UNEVALUATED_BREADTH_EXPLAIN`。⛔ 新造字樣。
- 未知 `source`、或 `is_loaded` 與 `source` 矛盾 → 契約違反（同上；⛔ 默默落某一態）。
- 位階契約**沒有 as_of** → `as_of=None`（呈現 `⬜ 資料日未提供`），⛔ 用 `cl_ts`／抓取時間頂替（新資料定義＝Stop Gate）。
- `FieldVM.source` 誠實標「規則分支 id」，⛔ 偽裝成資料來源。
- 契約回傳的 `exposure_limit_pct`／`risk_cap_disclosure`（Risk Cap）**不進 snapshot**（Risk Cap 恆 `⬜ 無法判定`）。
台股日 K（Issue #1099 PR-2；DEC-156 A／B／A）——📊 主圖位置，與 TWII 卡**分屬兩個事實、互相隔離**：
- 讀取：feed 另呼叫一次同一個 canonical service `get_twii_trend_view(KBAR_VISIBLE_BARS, with_ohlc=True)`（卡片那次
  `TWII_CARD_DAYS=1` 不動）；欄位複製在本檔 `RealFeedSnapshot.kbar_fact_of()`（純；feed 在自己的 try 內呼叫）。
- 讀取期自洽檢查 `validate_twii_kbar_fact`（長度一致、日期 ISO 嚴格升序、有限正值、OHLC 關係、根數 ≤ 20、末根＝as_of、
  不合格時 OHLC 必為空）→ 違反＝契約違反（紅；卡片照常）。
- 對帳（純、映射期）：日 K 與卡片的 as_of／最新收盤／is_stale／upstream_state／來源須一致（兩次讀取＝同一份快照），
  不一致 → 紅 Unavailable（⛔ 把分開讀到的不同版本假裝一致）；卡片本身讀不到 → 灰 `⬜ 無法判定`（無法對帳，不畫）。
- `failed=True`／讀取例外 → 紅；`ok=False` → 灰 Missing；`ohlc_ok=False` → 灰 `⬜ 無法判定`＋原因**類別**人話句（⛔ 原因碼）。
- 合格：照畫；`is_stale` True／None 的字樣與 TWII 卡**同一套**（Stale 照畫，資料是真歷史但舊）；不足 20 根 →
  照實少畫＋「僅 N 根（不足 20）」（⛔ 補棒／補 0／內插）。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from shared.allocation_decision import REGIME_LABEL
from shared import regime_arbiter as RA
from shared.ui2_contract.models import PageVM
from shared.upstream_state import UPSTREAM_TEXT_FETCH_FAILED, upstream_state_text as _upstream_state_text
from shared import twii_ohlc_contract as OC
from shared.ui2_contract.pages import (
    MODE_CURATED, MODE_LOOKUP, MODE_LABELS, P4_DATA, P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE4_LABELS, PAGE_IDS,
    SCENARIO_REAL,
)
from shared.ui2_contract.text import (
    RULE_BRANCH_SOURCE_PREFIX, TEXT_ASOF_MISSING, TEXT_NOT_DEFINED, TEXT_NOT_EVALUATED_DATA_SHORT, TEXT_NOT_LOADED, TEXT_NOT_PROVIDED,
    TEXT_RISK_CAP_UNDETERMINABLE,
)
from src.services.ui2.data_page import data_page_canonical
from src.services.ui2.market_vm import build_market_page_vm
from src.services.ui2.skeleton_vm import build_skeleton_page_vm


# ════════════════════════════════════════════════════════════════════
# Snapshot（feed 產出的 frozen 原樣結果；每 rerun 一份、四頁共用）
# ════════════════════════════════════════════════════════════════════
class RealFeedContractError(ValueError):
    """canonical service 回傳值違反其自身契約（未知 source、is_loaded 與分支矛盾、ok 卻無有限收盤值…）。

    §1 fail loud 的落點（實作組依 `CLAUDE.md` §1／§1.A-4 判斷，可推翻）：`real_feed` 在**讀取期**驗證，違反時該事實記為
    錯誤（畫面＝紅色 Unavailable「資料格式異常，暫時無法顯示」＋log 全文），**另一個事實照常顯示**——
    ⛔ 默默落成某一態（掩蓋），也 ⛔ 讓整頁例外（會把另一個有效事實一起蓋掉）。純函式本身遇到違反仍 raise（防呆）。
    """


#: 錯誤代碼只允許「例外型別名」這種識別字（⛔ 例外訊息／路徑／URL 進 snapshot；全文只進 log）。
_ERR_CODE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
#: 對外（feed 用）同一條正規式（⛔ 另寫一份）。
ERROR_CODE_RE = _ERR_CODE_RE
#: 錯誤代碼：canonical 契約違反（`RealFeedContractError`）。
CONTRACT_ERROR = "RealFeedContractError"     # ＝類別名（測試鎖定；⛔ dunder 屬性，G2／G2F 通用禁令）


def exception_code(e: BaseException) -> str:
    """例外 → 錯誤代碼（類別名；契約違反＝`CONTRACT_ERROR`）。不經 dunder 屬性：由 `repr(type(e))`
    （`<class 'pkg.Cls'>`）取最後一段；不符正規式 → `Exception`。⛔ 訊息原文。"""
    if isinstance(e, RealFeedContractError):
        return CONTRACT_ERROR
    r = repr(type(e))
    name = r.split("'")[1].rsplit(".", 1)[-1] if r.count("'") >= 2 else ""
    return name if _ERR_CODE_RE.match(name) else "Exception"


def _safe_code(err: str) -> str:
    return err if (not err or _ERR_CODE_RE.match(err)) else "Exception"


@dataclass(frozen=True)
class TwiiFact:
    """`TwiiTrendView` 的欄位（只拷貝本卡用到者）。

    錯誤細節（例外訊息、`metadata.last_error` 原文）**不進 snapshot**——畫面只顯示固定說明句（型別名只留 snapshot 內部代碼），全文只 log
    （NUI2-REALFEED-ERROR-SCRUB 收斂：避免 token／路徑上畫面）。`stale_reason` 為 L1 依規則產生的說明句（非錯誤原文）。
    """

    ok: bool
    close: tuple[float, ...]
    as_of: str | None
    is_stale: bool | None
    stale_reason: str
    age_days: int | None
    has_upstream_error: bool
    error_type: str            # failed=True 時的例外型別名；其餘 ""
    failed: bool
    source: str
    #: B2（DEC-148）：最近一次抓取三態 ""／NO_NEW_DATA／FETCH_FAILED／UNDETERMINED（L0 `shared.upstream_state` 判定）。
    #: 與 `is_stale`（新鮮度）、`has_upstream_error`（＝FETCH_FAILED）各自獨立；`""` 且 has_upstream_error → 沿用舊讀法（失敗句）。
    upstream_state: str = ""

    def __post_init__(self) -> None:
        if self.error_type and not _ERR_CODE_RE.match(self.error_type):
            raise ValueError(f"error_type 只能是例外型別名（識別字），收到 {self.error_type!r}")


@dataclass(frozen=True)
class RegimeFact:
    """`get_macro_regime()` 契約的**位階**欄位（原樣）。

    ⛔ 收 `exposure_limit_pct`／`risk_cap_disclosure`（Risk Cap 數值 Gate 前 UI2 恆 `⬜ 無法判定`；測試鎖定欄位集合）。
    `has_file_error`：strict 下契約多帶 `file_error`（只在 warroom 可用或 Risk Cap 新檔讀壞時）；不影響位階，**不呈現**，
    原文只 log（mapping 登記 `NUI2-REALFEED-FILE-ERROR-UNSURFACED`）。
    """

    regime: str
    light: str
    source: str
    is_loaded: bool
    has_file_error: bool = False


#: 📊 主圖預設可見根數（DEC-156 B：手機預設最近 20 根已驗證完整日 K）。feed 的 `TWII_KBAR_DAYS` 必須等於此值
#: （feed 不得自本檔 import 新名稱〔G2F 精確白名單〕，故兩處各一份，由 tests/test_ui2_twii_kbar.py 釘相等）。
KBAR_VISIBLE_BARS = 20
_UPSTREAM_STATES = ("", "NO_NEW_DATA", "FETCH_FAILED", "UNDETERMINED")
_ISO_DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class TwiiKbarFact:
    """`get_twii_trend_view(n, with_ohlc=True)` 的日 K 相關欄位（原樣；Issue #1099 PR-2）。

    與 `TwiiFact`（卡片）是**兩個獨立事實**：任一個壞掉不影響另一個。錯誤細節不進 snapshot（同 `TwiiFact`）。
    `ohlc_reason`＝L0 `shared.twii_ohlc_contract` 原因碼（內部代碼，**不上畫面**；畫面只放類別人話句）。
    `xs`／`closes` 在 `ohlc_ok` 非 True 時是卡片用的收盤序列（不畫）；`opens`／`highs`／`lows` 在不合格時必為空。
    """

    ok: bool
    failed: bool
    error_type: str
    ohlc_ok: bool | None
    ohlc_reason: str
    xs: tuple[str, ...]
    opens: tuple[float, ...]
    highs: tuple[float, ...]
    lows: tuple[float, ...]
    closes: tuple[float, ...]
    as_of: str | None
    is_stale: bool | None
    age_days: int | None
    stale_reason: str
    upstream_state: str
    has_upstream_error: bool
    source: str

    def __post_init__(self) -> None:
        if self.error_type and not _ERR_CODE_RE.match(self.error_type):
            raise ValueError(f"error_type 只能是例外型別名（識別字），收到 {self.error_type!r}")

    @classmethod
    def from_view(cls, v: Any, *, error_type: str = "") -> "TwiiKbarFact":
        """service 回傳值（`TwiiTrendView`，鴨子型別；本檔不 import L3 service）→ 事實。只複製、⛔ 修補。"""
        return cls(
            ok=bool(v.ok), failed=bool(v.failed), error_type=error_type, ohlc_ok=v.ohlc_ok,
            ohlc_reason=str(v.ohlc_error or ""), xs=tuple(v.xs), opens=tuple(v.open), highs=tuple(v.high),
            lows=tuple(v.low), closes=tuple(v.close), as_of=v.as_of, is_stale=v.is_stale, age_days=v.age_days,
            stale_reason=str(v.stale_reason or ""), upstream_state=v.upstream_state,
            has_upstream_error=(v.upstream_state == "FETCH_FAILED"), source=str(v.source))


def _finite_positive(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def validate_twii_kbar_fact(k: TwiiKbarFact) -> None:
    """日 K 事實自洽檢查（純；**重驗** L0 契約的核心條件，⛔ 只信 `ohlc_ok`）。違反 → `RealFeedContractError`。"""
    if not (k.is_stale is True or k.is_stale is False or k.is_stale is None):
        raise RealFeedContractError(f"台股日 K：is_stale 不是 True／False／None：{k.is_stale!r}")
    if not (k.ohlc_ok is True or k.ohlc_ok is False):
        raise RealFeedContractError(f"台股日 K：有要求日 K 但 ohlc_ok 不是 True／False：{k.ohlc_ok!r}")
    if k.ok and k.failed:
        raise RealFeedContractError("台股日 K：ok=True 與 failed=True 矛盾")
    if k.upstream_state not in _UPSTREAM_STATES:
        raise RealFeedContractError(f"台股日 K：upstream_state 不是三態之一：{k.upstream_state!r}")
    if k.ohlc_ok is False:
        if k.ohlc_reason not in OC.OHLC_REASON_CODES:
            raise RealFeedContractError(f"台股日 K：不合格但原因碼未知：{k.ohlc_reason!r}")
        if k.opens or k.highs or k.lows:
            raise RealFeedContractError("台股日 K：不合格卻帶開高低（⛔ 部分填）")
        return
    # ohlc_ok is True
    if not k.ok or k.failed or k.ohlc_reason:
        raise RealFeedContractError(f"台股日 K：ohlc_ok=True 但 ok={k.ok} failed={k.failed} reason={k.ohlc_reason!r}")
    n = len(k.xs)
    if not (1 <= n <= KBAR_VISIBLE_BARS):
        raise RealFeedContractError(f"台股日 K：根數 {n} 不在 1..{KBAR_VISIBLE_BARS}")
    if not (len(k.opens) == len(k.highs) == len(k.lows) == len(k.closes) == n):
        raise RealFeedContractError("台股日 K：日期／開高低收長度不一致")
    if not all(isinstance(d, str) and _ISO_DATE_RX.match(d) for d in k.xs):
        raise RealFeedContractError("台股日 K：日期不是 YYYY-MM-DD")
    if any(a >= b for a, b in zip(k.xs, k.xs[1:])):
        raise RealFeedContractError("台股日 K：日期未嚴格升序或重複")
    for d, o, h, lo, c in zip(k.xs, k.opens, k.highs, k.lows, k.closes):
        if not all(_finite_positive(x) for x in (o, h, lo, c)):
            raise RealFeedContractError(f"台股日 K：{d} 開高低收不是有限正值")
        if not (lo <= min(o, c) and max(o, c) <= h):
            raise RealFeedContractError(f"台股日 K：{d} 違反 low ≤ min(open,close) ≤ max(open,close) ≤ high")
    if k.as_of != k.xs[-1]:
        raise RealFeedContractError(f"台股日 K：末根日期 {k.xs[-1]!r} ≠ as_of {k.as_of!r}")


@dataclass(frozen=True)
class RealFeedSnapshot:
    """一次 rerun 的真資料快照。每個事實恰為「有值」或「有錯誤代碼」其一；錯誤代碼必為識別字（例外型別名）。
    feed 經 `of()` 建構（不符者降為 `"Exception"`）。"""

    twii: TwiiFact | None
    twii_error: str
    regime: RegimeFact | None
    regime_error: str
    #: 📊 台股日 K（Issue #1099 PR-2；加性欄位、有預設值）。兩者皆空＝這份 snapshot 沒有日 K 事實（主圖照舊誠實空槽）；
    #: feed 一律讀取 ⇒ Real-data Preview 恰為「有值」或「有錯誤代碼」其一。
    kbar: TwiiKbarFact | None = None
    kbar_error: str = ""

    def __post_init__(self) -> None:
        for name, fact, err in (("twii", self.twii, self.twii_error), ("regime", self.regime, self.regime_error)):
            if (fact is None) == (not err):
                raise ValueError(f"{name}: 必須恰為『有值』或『有錯誤代碼』其一（收到 fact={fact!r}, error={err!r}）")
            if err and not _ERR_CODE_RE.match(err):
                raise ValueError(f"{name}: 錯誤代碼只能是例外型別名（識別字；⛔ 訊息原文），收到 {err!r}"
                                 "（feed 一律經 `RealFeedSnapshot.of()`，不符者降為 `Exception`）")
        if self.kbar is not None and self.kbar_error:
            raise ValueError(f"kbar: 不得同時有值與錯誤代碼（收到 error={self.kbar_error!r}）")
        if self.kbar_error and not _ERR_CODE_RE.match(self.kbar_error):
            raise ValueError(f"kbar: 錯誤代碼只能是例外型別名（識別字；⛔ 訊息原文），收到 {self.kbar_error!r}")

    @classmethod
    def of(cls, twii: "TwiiFact | None", twii_error: str, regime: "RegimeFact | None",
           regime_error: str, *, kbar: "TwiiKbarFact | None" = None, kbar_error: str = "") -> "RealFeedSnapshot":
        """feed 唯一的建構入口：錯誤代碼不符正規式 → 降為 `Exception`（複驗 P3-4：⛔ 在 feed 的 try 之外 raise
        讓整頁崩、⛔ 原文進 snapshot）。直接呼叫建構子給壞代碼仍 raise（程式錯誤，fail loud）。"""
        return cls(twii=twii, twii_error=_safe_code(twii_error), regime=regime, regime_error=_safe_code(regime_error),
                   kbar=kbar, kbar_error=_safe_code(kbar_error))

    @staticmethod
    def kbar_fact_of(view: Any, *, error_type: str = "") -> TwiiKbarFact:
        """feed 在**自己的 try 內**呼叫：service 回傳值 → `TwiiKbarFact` → 讀取期自洽檢查（違反 raise
        `RealFeedContractError`，feed 接住 → 日 K 紅色 Unavailable、卡片照常）。

        為什麼掛在 `RealFeedSnapshot` 上：feed 只准自本檔 import 具名白名單（G2F，本 PR 不改守衛），且 feed 禁止
        `.open` 屬性（G2F 為擋檔案 I/O 而禁）；欄位複製是純動作（含讀 `view.open` 開盤價欄位），放在 G2 照掃的本檔。"""
        fact = TwiiKbarFact.from_view(view, error_type=error_type)
        validate_twii_kbar_fact(fact)
        return fact


# ════════════════════════════════════════════════════════════════════
# 兩個真事實 → canonical spec
# ════════════════════════════════════════════════════════════════════
#: 位階 `source` 的已知值（`shared.regime_arbiter.SOURCE_*` 全集；SSOT，⛔ 另列一份）。
KNOWN_REGIME_SOURCES: frozenset[str] = frozenset(
    v for k, v in vars(RA).items() if k.startswith("SOURCE_") and isinstance(v, str))
_NOT_LOADED_SOURCES = frozenset({RA.SOURCE_UNLOADED, RA.SOURCE_UNEVALUATED_BREADTH})

#: 位階 `FieldVM.source`：誠實標規則分支 id（⛔ 偽裝成資料來源）。
REGIME_SOURCE_FMT = RULE_BRANCH_SOURCE_PREFIX + "{source}（非資料來源）"
REGIME_ASOF_NOTE = f"{TEXT_ASOF_MISSING}（市場位階未提供資料日）"
#: 第一屏（L1）只放一句人話原因（P1：不再指向「為什麼（L2）」——該區塊屬 P3 移除範圍，且其中的 L0 完整說明含
#: 決策編號／狀態檔名，不畫在 Human UI；完整說明改放資料健康度·市場位階項〔P6〕，現在只留在 VM 的 `regime_explain` 欄）。
#: 這句只轉述 L0 `NOT_LOADED_PENDING_BREADTH_EXPLAIN`／`UNEVALUATED_BREADTH_EXPLAIN` 共同的原因（缺正式市場廣度資料），
#: ⛔ 新增原因或推論。
#: ⚠ 前提：目前 `shared.signal_thresholds.BREADTH_PROXY_SCORING_ENABLED=False`（市場廣度代理值不計分、缺正式廣度來源 →
#: 位階恆未評估）。若日後改 True，這句「尚缺正式的市場廣度」可能不再成立 → 須重審文案與 L0 `*_EXPLAIN`；
#: `tests/test_ui2_p1_human_text.py::test_regime_see_why_premise_breadth_proxy_scoring_is_off` 會轉紅提醒。
REGIME_SEE_WHY = "原因：尚缺正式的市場廣度（漲跌家數）資料"
#: 🎯 與 📊 同一句（跨頁一致性測試鎖定；舊版 🎯 指向 📊 的區塊，區塊不再是指引目標）。
REGIME_SEE_WHY_MARKET = REGIME_SEE_WHY
#: L0 說明句提到「按更新」指正式網站；Real-data Preview 沒有可用的更新入口 ⇒ 另加連接句說清楚（⛔ 改 L0 原文）。
PREVIEW_NO_REFRESH_NOTE = "註：上句的「按更新」指正式網站；這裡不提供更新，所以這一格維持尚未載入"
PREVIEW_NO_REFRESH_SHORT = "這裡不提供更新，所以這一格維持尚未載入"

_TWII_MISSING_TEXT = "加權指數歷史快取讀不到（檔案不存在、壞檔、缺欄或內容為空）"
_UPSTREAM_ERROR_TEXT = UPSTREAM_TEXT_FETCH_FAILED     # 舊名保留（FETCH_FAILED 句）；三態文案 SSOT 在 L0 `shared.upstream_state`


def _error_text(what: str, code: str) -> str:
    """畫面上的錯誤句：**固定人話句**（⛔ 例外型別名、⛔ 訊息原文）。型別名留在 snapshot 的錯誤代碼與 feed 的 log
    （P1 QA 修：型別名是工程資訊，不上使用者畫面）。契約違反＝另一句固定說明。"""
    if code == CONTRACT_ERROR:
        return f"{what}：資料格式異常，暫時無法顯示"
    return f"{what}暫時無法讀取"


def validate_regime_fact(f: RegimeFact) -> None:
    """位階契約自洽檢查（純）。違反 → `RealFeedContractError`。"""
    if f.source not in KNOWN_REGIME_SOURCES:
        raise RealFeedContractError(f"市場位階：未知 source {f.source!r}（允許 {sorted(KNOWN_REGIME_SOURCES)}）")
    if f.is_loaded and (f.source in _NOT_LOADED_SOURCES or f.regime not in REGIME_LABEL or f.regime == "unknown"):
        raise RealFeedContractError(f"市場位階契約矛盾：is_loaded=True 但 regime={f.regime!r} source={f.source!r}")
    if not f.is_loaded and f.source not in _NOT_LOADED_SOURCES:
        raise RealFeedContractError(f"市場位階契約矛盾：is_loaded=False 但 source={f.source!r} 屬已載入分支")


def validate_twii_fact(t: TwiiFact) -> None:
    """台股契約自洽檢查（純）。違反 → `RealFeedContractError`。"""
    # 身分比較（⛔ `in (True, False, None)`：`1`／`1.0`／`np.True_` 會被 `==` 當成 True 而漏網；複驗 P2-1）
    if not (t.is_stale is True or t.is_stale is False or t.is_stale is None):
        raise RealFeedContractError(f"台股：is_stale 不是 True／False／None：{t.is_stale!r}")
    if t.ok and t.failed:
        raise RealFeedContractError("台股：ok=True 與 failed=True 矛盾")
    if t.upstream_state not in ("", "NO_NEW_DATA", "FETCH_FAILED", "UNDETERMINED"):
        raise RealFeedContractError(f"台股：upstream_state 不是三態之一：{t.upstream_state!r}")
    if t.ok:
        if not t.close:
            raise RealFeedContractError("台股：ok=True 但沒有收盤值")
        last = t.close[-1]
        if not isinstance(last, (int, float)) or isinstance(last, bool) or not math.isfinite(last):
            raise RealFeedContractError(f"台股：收盤值不是有限數 {last!r}")


def regime_spec(snap: RealFeedSnapshot, key: str, label: str, *, brief: bool = True,
                see_why: str = REGIME_SEE_WHY) -> dict:
    """市場位階 → spec。📊／🎯 三處（`brief=True`）＋📊 L2 位階說明（`brief=False`）都呼叫本函式、吃同一個
    `snap.regime`（⛔ 各自讀取）。`brief`／`see_why` 只決定 detail 文字；態／值／字樣／provenance 完全相同。"""
    base: dict[str, Any] = {"key": key, "label": label, "value": None, "as_of": None, "source": None}
    if snap.regime is None:
        return {**base, "state": "unavailable", "reason": _error_text("市場位階", snap.regime_error)}
    f = snap.regime
    validate_regime_fact(f)                     # 防呆：feed 已驗；直接餵壞 fact 仍 fail loud
    src = REGIME_SOURCE_FMT.format(source=f.source)
    if f.is_loaded:
        return {**base, "value": REGIME_LABEL[f.regime], "source": src, "reason": REGIME_ASOF_NOTE}
    short = f"{REGIME_ASOF_NOTE}；{see_why}"
    if f.source == RA.SOURCE_UNEVALUATED_BREADTH:
        return {**base, "state": "undeterminable", "sub_reason": TEXT_NOT_EVALUATED_DATA_SHORT, "source": src,
                "reason": short if brief else f"{RA.UNEVALUATED_BREADTH_EXPLAIN}。{REGIME_ASOF_NOTE}"}
    # SOURCE_UNLOADED（validate 已排除其他分支）
    state = {"is_loaded": f.is_loaded, "source": f.source}
    explain = (f"{RA.NOT_LOADED_PENDING_BREADTH_EXPLAIN}。{PREVIEW_NO_REFRESH_NOTE}"
               if RA.is_not_loaded_pending_breadth(state) else PREVIEW_NO_REFRESH_SHORT)
    return {**base, "state": "not_evaluated", "sub_reason": TEXT_NOT_LOADED, "source": src,
            "reason": short if brief else f"{explain}。{REGIME_ASOF_NOTE}"}


def twii_card_spec(snap: RealFeedSnapshot) -> dict:
    """台股加權指數 → 📊 `cards.twii` spec（值＝最新一筆收盤，原樣格式化；⛔ 任何計算）。"""
    base: dict[str, Any] = {"key": "twii", "label": "台股", "value": None, "as_of": None, "source": None}
    if snap.twii is None:
        return {**base, "state": "unavailable", "reason": _error_text("台股加權指數", snap.twii_error)}
    t = snap.twii
    validate_twii_fact(t)                       # 防呆：feed 已驗
    base.update(source=t.source, as_of=t.as_of)
    if not t.ok:
        if t.failed:
            return {**base, "state": "unavailable", "reason": _error_text("台股加權指數", t.error_type or "Exception")}
        return {**base, "missing_kind": "not_fetched", "reason": _TWII_MISSING_TEXT}
    last = t.close[-1]
    # B2：依三態分流文案；⛔ 不再把所有空抓取都稱為「抓取失敗」。upstream_state 為空但 has_upstream_error（舊事實）→ 失敗句。
    _up_text = _upstream_state_text(t.upstream_state) or (_UPSTREAM_ERROR_TEXT if t.has_upstream_error else "")
    notes = [x for x in (t.stale_reason, _up_text) if x]
    spec = {**base, "value": f"{last:,.2f}"}
    if t.is_stale is True:
        return {**spec, "state": "stale", "stale_days": t.age_days, "reason": "；".join(notes) or None}
    if t.is_stale is None:      # 新鮮度未判定 ⛔ 當 OK（AI 總管內部判準，可推翻）
        return {**spec, "state": "stale", "stale_days": None,
                "reason": "；".join(["新鮮度未判定", *notes])}
    return {**spec, "reason": "；".join(notes) or None}


#: 日 K 不合格原因碼 → 畫面上的**類別**人話句（⛔ 原因碼本身上畫面；碼只留 snapshot 與 log）。
_KBAR_REASON_CATEGORY: dict[str, str] = {
    OC.EMPTY: "日 K 資料為空",
    OC.LENGTH_MISMATCH: "日 K 日期或筆數異常", OC.BAD_DATE: "日 K 日期或筆數異常",
    OC.DUPLICATE_DATE: "日 K 日期或筆數異常", OC.NOT_ASCENDING: "日 K 日期或筆數異常",
    OC.FUTURE_DATE: "日 K 日期或筆數異常",
    OC.NOT_FINITE: "日 K 價格有缺值或不合理", OC.NON_POSITIVE: "日 K 價格有缺值或不合理",
    OC.OHLC_RELATION: "日 K 價格有缺值或不合理",
    OC.FETCHED_AT_MISSING: "無法確認最近的日 K 已收盤完成", OC.INCOMPLETE_BAR: "無法確認最近的日 K 已收盤完成",
    OC.AS_OF_MISMATCH: "日 K 與最新收盤不同步", OC.WINDOW_MISMATCH: "日 K 與最新收盤不同步",
    OC.READ_FAILED: "日 K 暫時無法讀取",
}
KBAR_LABEL = "台股加權指數日 K"
KBAR_NOT_DRAWN_SUFFIX = "，這次不畫日 K（缺值不補）"
KBAR_CARD_UNAVAILABLE_TEXT = "最新收盤暫時無法讀取，無法確認日 K 與其同步" + KBAR_NOT_DRAWN_SUFFIX
KBAR_MISMATCH_TEXT = "台股日 K：與最新收盤資料不同步，暫時無法顯示"
KBAR_PARTIAL_FMT = "僅 {n} 根（不足 {target}）"


def kbar_reason_text(code: str) -> str:
    """不合格原因碼 → 類別人話句（未知碼 → 通用句；⛔ 原碼上畫面）。"""
    return _KBAR_REASON_CATEGORY.get(code, "日 K 資料未通過檢核") + KBAR_NOT_DRAWN_SUFFIX


def kbar_same_source_problem(k: TwiiKbarFact, card: TwiiFact | None) -> str:
    """日 K（`ohlc_ok=True`）與 TWII 卡是否同一份快照（純）。回傳 `""`＝一致；`"card_unavailable"`＝卡片讀不到
    （無法對帳）；`"mismatch"`＝兩次讀取不一致（⛔ 假裝一致）。比較：as_of／最新收盤（容差，§4.3）／is_stale（身分）／
    age_days／upstream_state／來源。"""
    if card is None or not card.ok or not card.close:
        return "card_unavailable"
    same = (card.as_of == k.as_of and card.is_stale is k.is_stale and card.age_days == k.age_days
            and card.upstream_state == k.upstream_state and card.source == k.source
            and math.isclose(card.close[-1], k.closes[-1], rel_tol=1e-9, abs_tol=1e-9))
    return "" if same else "mismatch"


def kbar_chart_spec(snap: RealFeedSnapshot) -> dict | None:
    """台股日 K → 📊 主圖 spec（`vm_common.kbar_from_spec` 的輸入）。snapshot 沒有日 K 事實 → None（主圖照舊誠實空槽）。"""
    if snap.kbar is None and not snap.kbar_error:
        return None
    base: dict[str, Any] = {"key": "twii_kbar", "label": KBAR_LABEL, "value": None, "as_of": None, "source": None}

    def out(field: dict, candles: list | None = None, notes: list | None = None) -> dict:
        return {"field": field, "candles": candles or [], "target_n": KBAR_VISIBLE_BARS, "notes": notes or []}

    if snap.kbar is None:
        return out({**base, "state": "unavailable", "reason": _error_text("台股日 K", snap.kbar_error)})
    k = snap.kbar
    validate_twii_kbar_fact(k)                  # 防呆：feed 已驗；直接餵壞 fact 仍 fail loud
    base.update(source=k.source, as_of=k.as_of)
    if k.failed:
        return out({**base, "state": "unavailable", "reason": _error_text("台股日 K", k.error_type or "Exception")})
    if not k.ok:
        return out({**base, "missing_kind": "not_fetched", "reason": _TWII_MISSING_TEXT})
    if k.ohlc_ok is False:
        return out({**base, "state": "undeterminable", "reason": kbar_reason_text(k.ohlc_reason)})
    problem = kbar_same_source_problem(k, snap.twii)
    if problem == "card_unavailable":
        return out({**base, "state": "undeterminable", "reason": KBAR_CARD_UNAVAILABLE_TEXT})
    if problem:
        return out({**base, "state": "unavailable", "reason": KBAR_MISMATCH_TEXT})
    candles = [{"date": d, "open": o, "high": h, "low": lo, "close": c}
               for d, o, h, lo, c in zip(k.xs, k.opens, k.highs, k.lows, k.closes)]
    notes = [KBAR_PARTIAL_FMT.format(n=len(candles), target=KBAR_VISIBLE_BARS)] if len(candles) < KBAR_VISIBLE_BARS else []
    # 新鮮度字樣與 TWII 卡同一套（twii_card_spec）：Stale 照畫（真歷史但舊），⛔ 當 fresh。
    _up_text = _upstream_state_text(k.upstream_state) or (_UPSTREAM_ERROR_TEXT if k.has_upstream_error else "")
    fresh_notes = [x for x in (k.stale_reason, _up_text) if x]
    field = {**base, "value": f"{k.closes[-1]:,.2f}"}
    if k.is_stale is True:
        field.update(state="stale", stale_days=k.age_days, reason="；".join(fresh_notes) or None)
    elif k.is_stale is None:
        field.update(state="stale", stale_days=None, reason="；".join(["新鮮度未判定", *fresh_notes]))
    else:
        field.update(reason="；".join(fresh_notes) or None)
    return out(field, candles, notes)


# ════════════════════════════════════════════════════════════════════
# 契約固定欄（與 FAKE 同字樣；跨頁／跨 feed 相等由測試鎖定）＋ capability 欄
# ════════════════════════════════════════════════════════════════════
def _not_provided(key: str, label: str, reason: str, sub: str = TEXT_NOT_PROVIDED) -> dict:
    return {"key": key, "label": label, "value": None, "state": "not_provided", "sub_reason": sub,
            "reason": reason, "as_of": None, "source": None}


def _risk_cap_row() -> dict:
    """Risk Cap＝Unable to Determine（Freeze §0.1.4；DEC-124）。⛔ 讀 `get_macro_regime` 的 exposure／disclosure。"""
    return {"key": "risk_cap", "label": "Risk Cap", "value": None, "state": "undeterminable",
            "sub_reason": TEXT_RISK_CAP_UNDETERMINABLE, "reason": "必要輸入不足：目前曝險尚無正式來源",
            "as_of": None, "source": None}


#: 使用者可見的簡短人話原因（P1；原工程原因〔session／PORT／Legacy／OAuth／路徑 C／Gate／Stage〕不外露，
#: 對映與出處留在 mapping 文件 `NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` 與 BACKLOG，見 Active Contract §8）。
_R_SESSION = "此項目尚未開放"
_R_PORT = "此項目尚未開放"
_R_PATH_C = "需登入並讀取 Sheet，目前尚未開放"
_R_NOT_IN_BATCH = "此項目尚未開放"
_R_STAGE_G = "此功能尚未開放"


def _market(snap: RealFeedSnapshot) -> dict:
    return {
        "page": P4_MARKET, "title": PAGE4_LABELS[P4_MARKET],
        "current_state": regime_spec(snap, "regime", "市場目前狀態"),
        "context_rows": [_risk_cap_row()],
        "next_step": None,                      # → 待 System Action Aggregator（VM 統一處理）
        "cta": {"label": "🚀 更新今日戰情", "disabled_reason": "目前不提供更新"},
        "cards": [
            twii_card_spec(snap),
            _not_provided("vix", "VIX", _R_SESSION),
            _not_provided("us10y", "US 10Y", _R_SESSION),
            _not_provided("spread", "利差", "「利差」尚無正式定義（10Y-2Y／10Y-3M／M1B-M2 擇一，待定義）"),
            _not_provided("dxy", "DXY", _R_SESSION),
            _not_provided("pmi", "PMI／景氣", "台灣 PMI 與景氣燈號意義不同，用哪一個尚待定義"),
        ],
        "sections": [
            {"key": "onebrain", "title": "🤖 OneBrain Outlook", "level": "L1",
             "fields": [_not_provided("onebrain_f", "OneBrain Outlook", _R_STAGE_G)]},
            {"key": "why", "title": "為什麼", "level": "L2",
             "fields": [regime_spec(snap, "regime_explain", "位階說明", brief=False),
                        _not_provided("why_f", "位階理由／反證／資料新鮮度／來源", _R_SESSION)]},
            {"key": "detail", "title": "指標明細（16 項）", "level": "L3",
             "fields": [_not_provided("detail_f", "指標明細", _R_SESSION)]},
            {"key": "raw", "title": "原始資料表", "level": "L3",
             "fields": [_not_provided("raw_f", "原始資料表", _R_SESSION)]},
        ],
        # 第一屏短句（Freeze §16.5 縮字句）；完整原因見 mapping 文件 M6／M7。
        "conclusion": _not_provided("conclusion", "今日結論", "今日結論尚未提供"),
        "main_risk": _not_provided("main_risk_f", "今日主要風險", "今日風險摘要尚未開放"),
        "kbar": kbar_chart_spec(snap),          # Issue #1099 PR-2：None＝無日 K 事實（主圖照舊誠實空槽）
    }


def _target(snap: RealFeedSnapshot) -> dict:
    snapshot = [
        _not_provided("dim_fundamental", "基本面", _R_NOT_IN_BATCH),
        _not_provided("dim_valuation", "估值", _R_NOT_IN_BATCH),
        _not_provided("dim_chips", "籌碼", _R_NOT_IN_BATCH),
        {"key": "dim_trend", "label": "趨勢", "value": None, "state": "not_evaluated",
         "sub_reason": TEXT_NOT_DEFINED, "as_of": None, "source": None},
        {"key": "dim_industry", "label": "產業", "value": None, "state": "not_evaluated",
         "sub_reason": TEXT_NOT_DEFINED, "as_of": None, "source": None},
        regime_spec(snap, "dim_market_env", "市場環境", see_why=REGIME_SEE_WHY_MARKET),
    ]
    return {
        "page": P4_TARGET, "title": PAGE4_LABELS[P4_TARGET],
        "current_state": _not_provided("pick_summary", "精選摘要",
                                       "精選尚未開放（需連網取得，且候選的組合方式尚待定義）"),
        "context_rows": [regime_spec(snap, "market_regime", "市場位階", see_why=REGIME_SEE_WHY_MARKET),
                         _risk_cap_row()],
        "action_needed": _not_provided("no_holding_action", "是否需要行動", "本頁不產生持股動作；動作權威＝💼 持股"),
        "next_step": _not_provided("next", "下一步", "選一檔後進入研究頁（尚未提供）"),
        "cta": {"label": "查詢", "disabled_reason": "尚未開放查詢"},
        "cards": [
            _not_provided("industry_top", "產業機會 Top 5", _R_PORT),
            _not_provided("candidates", "候選 Top 10", "候選 Top 10 尚未開放（組合方式尚待定義）"),
        ],
        "sections": [
            {"key": "conditions", "title": "選股條件（收合）", "level": "L2", "mode": MODE_CURATED,
             "fields": [_not_provided("cond_f", "選股條件", _R_NOT_IN_BATCH)]},
            {"key": "full", "title": "完整 6 欄表／跨季趨勢", "level": "L3", "mode": MODE_CURATED,
             "fields": [_not_provided("full_f", "完整表", _R_NOT_IN_BATCH)]},
        ],
        "target": {
            "modes": [{"id": m, "label": MODE_LABELS[m]} for m in (MODE_CURATED, MODE_LOOKUP)],
            "default_mode": MODE_CURATED,
            "search": {
                "placeholder": "代碼／名稱",
                "name_search": _not_provided("name_search", "名稱搜尋", "請輸入代碼（名稱搜尋尚未提供）"),
                "cta": {"label": "查詢", "disabled_reason": "尚未開放查詢"},
            },
            "lookup": {
                "ticker": "", "name": "", "chips": [], "queried": False,
                "summary": _not_provided("lookup_summary", "查詢摘要", "即時查一檔尚未開放"),
                "snapshot": snapshot,
                "add_watch": {"label": "加入觀察（尚未提供）",
                              "disabled_reason": "加入觀察尚未開放；這裡不會寫入任何持股或觀察清單"},
                "isolation_note": "查一檔只在這次瀏覽有效：不會加入持股、觀察或候選池，也不會改變策略、Risk Cap 或排名，不寫入 Sheet。",
                "sections": [
                    {"key": "lk_fundamental", "title": "基本面", "level": "L2", "mode": MODE_LOOKUP,
                     "fields": [_not_provided("lk_f1", "基本面明細", _R_NOT_IN_BATCH)]},
                    {"key": "lk_valuation", "title": "估值", "level": "L2", "mode": MODE_LOOKUP,
                     "fields": [_not_provided("lk_f2", "估值（EPS basis／PE 口徑）", _R_NOT_IN_BATCH)]},
                    {"key": "lk_research", "title": "🤖 研究解釋", "level": "L2", "mode": MODE_LOOKUP,
                     "fields": [_not_provided("lk_f3", "研究解釋", _R_STAGE_G)]},
                ],
            },
        },
    }


def _hold() -> dict:
    return {
        "page": P4_HOLD, "title": PAGE4_LABELS[P4_HOLD],
        "current_state": _not_provided("portfolio", "組合狀態", _R_PATH_C),
        "context_rows": [
            _risk_cap_row(),
            {"key": "exposure", "label": "目前曝險", "value": None, "missing_kind": "not_ready",
             "reason": "無現金／總資產來源", "as_of": None, "source": None},
        ],
        "next_step": None,
        "cta": {"label": "🚀 更新持股戰情", "disabled_reason": "目前不提供更新；需登入後才能讀取持股"},
        "cards": [_not_provided("holdings_table", "持股清單", _R_PATH_C)],
        "sections": [
            {"key": "onebrain", "title": "🤖 OneBrain 持股摘要", "level": "L1",
             "fields": [_not_provided("ob_f", "OneBrain 持股摘要", _R_STAGE_G)]},
            {"key": "why", "title": "明細", "level": "L2",
             "fields": [_not_provided("why_f", "基本面／風險／籌碼／證據", _R_PATH_C)]},
            {"key": "raw", "title": "原始明細", "level": "L3",
             "fields": [_not_provided("raw_f", "原始明細", _R_PATH_C)]},
        ],
    }


_R_ME = "需登入 Google 才能顯示，目前尚未開放"


def _me() -> dict:
    return {
        "page": P4_ME, "title": PAGE4_LABELS[P4_ME],
        "current_state": _not_provided("conn", "連線狀態", _R_ME),
        "context_rows": [],
        "action_needed": _not_provided("conn_issue", "連線異常", _R_ME),
        "next_step": _not_provided("next", "下一步", _R_ME),
        "cta": {"label": "帳戶管理", "disabled_reason": "登入與 Sheet 操作尚未開放"},
        "cards": [
            _not_provided("google", "Google", _R_PATH_C),
            _not_provided("sheet", "Sheet（末 6 碼）", _R_PATH_C),
            _not_provided("portfolio", "組合", _R_PATH_C),
            _not_provided("watchlist", "觀察清單", _R_PATH_C),
        ],
        "sections": [
            {"key": "settings", "title": "一般設定", "level": "L1", "fields": [
                _not_provided("strategy", "Strategy", _R_NOT_IN_BATCH),
                _not_provided("notify", "Notifications", _R_NOT_IN_BATCH),
                _not_provided("display", "Display preference", _R_NOT_IN_BATCH)]},
            {"key": "digest", "title": "Audit：Decision Digest", "level": "L2", "fields": [
                _not_provided("digest_f", "Decision Digest", _R_STAGE_G)]},
            {"key": "registry", "title": "Audit：Rule Registry（唯讀）", "level": "L2",
             "fields": [_not_provided("registry_f", "Rule Registry", _R_NOT_IN_BATCH)]},
            {"key": "fresh", "title": "Audit：Data Freshness", "level": "L2",
             "fields": [_not_provided("fresh_f", "Data Freshness", _R_NOT_IN_BATCH)]},
            {"key": "sysinfo", "title": "Audit：System Information", "level": "L2",
             "fields": [_not_provided("sys_f", "System Information", _R_NOT_IN_BATCH)]},
        ],
        # account＝None：Real-data Preview 不知道真實帳戶狀態（⛔ 假裝 signed-in／signed-out）。
    }


def _data() -> dict:
    """🗂 資料頁：固定誠實空殼（與 FAKE 軸同一份內容；全為 Capability `⬜ 尚未提供`，⛔ 讀取任何 snapshot 欄位）。"""
    return data_page_canonical()


def real_canonical(page_id: str, snap: RealFeedSnapshot) -> dict:
    """`page_id`×snapshot → canonical dict（`is_fake=False`、`scenario='real'`）。每次回新 dict。"""
    if page_id not in PAGE_IDS:
        raise ValueError(f"unknown page {page_id!r}")
    if not isinstance(snap, RealFeedSnapshot):
        raise TypeError(f"需要 RealFeedSnapshot，收到 {type(snap)!r}")
    c = {P4_MARKET: lambda: _market(snap), P4_TARGET: lambda: _target(snap),
         P4_HOLD: _hold, P4_ME: _me, P4_DATA: _data}[page_id]()
    c["scenario"] = SCENARIO_REAL
    c["is_fake"] = False
    return c


def get_real_page_vm(page_id: str, snap: RealFeedSnapshot, *, top_n: int | None = None,
                     mode: str | None = None) -> PageVM:
    """Real-data Preview 的 PageVM：沿用既有 VM builder（VM／UI 不因 fake→real 重寫）。"""
    canonical = real_canonical(page_id, snap)
    if page_id == P4_MARKET:
        return build_market_page_vm(canonical, top_n=top_n, mode=mode)
    return build_skeleton_page_vm(canonical, top_n=top_n, mode=mode)
