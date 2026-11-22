"""OneBrain 持股 FAKE 離線示意（OFFLINE-WIRING-SCRATCH-1；**原型，可拋棄**；不是測試檔，不會被收集；**僅限 tests/ 使用**）。

基準：main（#1258＋#1261 已合併）；移植自 scratch/onebrain-holdings-ui2-demo-20261122@61619ad6。
設計＝#1199 v2 設計 ＋ 總管 D1–D9 裁定（comment 7075101372）、D8（comment 7076099172）。
QA 狀態不寫進程式檔（由 PR／#1199 記錄）。Digest NOT READY；OneBrain NOT READY。

執行：`python -m tests.onebrain_holdings_ui2_demo [R1|R2|R3|L1|L2|L3|all]`（純文字輸出；**未**接 UI2 hold view）

═══ 這是什麼 ═══════════════════════════════════════════════════════════
以合成 `HoldingsReadSnapshot` 跑整條離線鏈
`adapt_holdings_read → assemble_digest → build_rule_summary → run_shadow(FakeProvider 全模式)`，
把結果排成「tests/ 獨立示範頁上模擬的 💼 OneBrain 槽」內容（D2）。每一行都帶區域標籤：
`disclosure`（示意聲明）／`derived`（UI 衍生「持股判讀」列，D9）／`system_output`（Digest 存股＋資本利得兩段**逐字**原句）／
`ui_note`（UI 說明區；D3 核定註記）／`footer`（來源、時點、顯示口徑）／`test_input`（測試輸入說明；非系統輸出）。

═══ 硬邊界 ═════════════════════════════════════════════════════════════
- ⛔ 不是 production：0 production caller；不改 src／shared／app*／scripts／守衛；production 💼 文案「尚未提供／此功能尚未開放」不動。
- ⛔ 不顯示（D4／D5）：市場段、Risk Cap、產業段、本期行動、shadow_accepted、grounding、FakeProvider 草稿、is_complete／任何完整性結論。
- ⛔ 不轉譯原因碼；「（尚無輸入）」逐字保留，另於 UI 說明區（資料驅動）附核定註記（D3=a）。
- ⛔ 零網路、零時鐘（`generated_at` 固定）、零 Secrets、不讀 Sheet／OAuth、無真實 Provider。
- Fail-closed：鏈中任何例外、可用性不符預期、effective ≠ 規則式摘要、或待顯示文字含禁字 ⇒
  只輸出聲明＋「持股判讀 ⬜ 無法判定」＋固定失敗說明＋頁尾，**不**猜任何系統句（`FAILCLOSED_*`）。
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

import src.services.decision_digest_assembly as ASM
import src.services.decision_digest_summary as S
import src.services.onebrain_holdings_adapter as A
import src.services.onebrain_shadow as SH
from shared.allocation_decision import build_allocation_decision
from shared.decision_digest import Availability, HoldingKey
from shared.decision_digest_grounding import Lit, SummaryDraft, SummarySection, SummarySentence
from shared.freshness_policy import FreshnessStatus
from shared.risk_cap_policy import RiskCapDisclosure
from src.services.decision_digest_builder import SourceStamp
from tests.onebrain_fake_provider import ALL_MODES, MODE_PAYLOAD, FakeProvider

_log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# 區域與逐字常數（白名單；測試逐字鎖定）
# ══════════════════════════════════════════════════════════════════════
AREA_DISCLOSURE = "disclosure"
AREA_DERIVED = "derived"
AREA_SYSTEM = "system_output"
AREA_UI_NOTE = "ui_note"
AREA_FOOTER = "footer"
AREA_TEST_INPUT = "test_input"
AREAS = (AREA_DISCLOSURE, AREA_DERIVED, AREA_SYSTEM, AREA_UI_NOTE, AREA_FOOTER, AREA_TEST_INPUT)

DISCLOSURE_LINES = (
    "示意：合成持股快照（FAKE）；非真實持股；非即時 OneBrain；非投資建議",
    "與本頁其他 FAKE 數字無關",
)
#: D9：兩種缺資料態統一字樣（＝ `shared.ui2_contract.text.TEXT_RISK_CAP_UNDETERMINABLE` 的值；
#: ⛔ 不重用 breadth 專屬「⬜ 未評估／資料不足」）。只在此示範使用，不改既有常數的全域語意。
HOLDINGS_UNDETERMINABLE = "⬜ 無法判定"
DERIVED_LABEL = "持股判讀"
DERIVED_MARK = "（UI 依持股可用性推導；非 Digest 原句）"
#: D3=a 核定文案（逐字）。
NOTE_NO_INPUT_TRIGGER = "（尚無輸入）"
NOTE_NO_INPUT = "註：『尚無輸入』是現行摘要措辭，也可能代表讀取失敗、輸入異常或缺少組合鍵；請勿解讀為零持股。"
FOOTER_DISPLAY = "顯示＝規則式摘要；FakeProvider 草稿不採用"
FOOTER_SOURCE = "來源：FAKE 合成持股快照"
FOOTER_ASOF = "時點：FAKE 示意（無持股讀取時點，§C-10）"
FOOTER_LINES = (FOOTER_DISPLAY, FOOTER_SOURCE, FOOTER_ASOF)
TEST_INPUT_PREFIX = "測試輸入說明（非系統輸出；系統不傳遞此資訊，§C-2）："
FAILCLOSED_NOTE = "示範鏈未通過檢查，未顯示任何系統句"

#: 只顯示 Digest 這兩段（D4：market／industry／actions 一律不顯示）。
SHOWN_SECTIONS = ("buy_and_hold", "capital_gain")
SECTION_LABELS = {"buy_and_hold": "存股", "capital_gain": "資本利得"}

#: 待顯示文字的執行期禁字（命中 ⇒ fail-closed；測試另有獨立掃描）。
RUNTIME_BANNED = ("bull", "🟢", "72.5", "市場位階", "txt-", "本期行動", "is_complete", "shadow_accepted",
                  "Risk Cap", "風險上限", "完整", *A.ALL_REASONS)


# ══════════════════════════════════════════════════════════════════════
# 合成案例（D6：R1–R3、L1–L3；排除 zero_rows／status_empty）
# ══════════════════════════════════════════════════════════════════════
TICKERS = ("FAKE-T1", "FAKE-T2")
_PID = "pf-fake-demo"
_D = date(2026, 10, 26)                                       # 合成資料日（固定）
_GENERATED_AT = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)   # 固定；無時鐘
_CLEAN = dict(dropped_blank_ticker=0, dropped_non_numeric=0, dropped_non_finite=0, dropped_non_positive=0,
              dropped_blank_value=0, kept_blank_value_count=0, kept_non_finite_count=0, duplicate_ticker_count=0)


def _ok_snapshot(**kw) -> A.HoldingsReadSnapshot:
    counts = {**_CLEAN, **kw}
    source = len(TICKERS) + sum(counts[f] for f in A.DROP_REASON_FIELDS.values())
    return A.HoldingsReadSnapshot(A.OUTCOME_OK, False, kept_tickers=TICKERS, source_row_count=source, **counts)


@dataclass(frozen=True)
class DemoCase:
    case_id: str
    snapshot: A.HoldingsReadSnapshot
    keyed: tuple                      # 有投資組合鍵的代號（其餘為無鍵）
    expect_none: bool                 # adapter 預期回 None（未知）
    expect_availability: Availability
    test_input: str                   # 人讀的合成輸入說明（非系統輸出；不含原因碼）


CASES: dict = {
    "R1": DemoCase("R1", A.HoldingsReadSnapshot(A.OUTCOME_EXCEPTION_NETWORK, False), TICKERS, True,
                   Availability.UNAVAILABLE, "合成讀取結局為網路例外；無列資訊"),
    "R2": DemoCase("R2", A.HoldingsReadSnapshot(A.OUTCOME_NOT_SELECTED, False), TICKERS, True,
                   Availability.UNAVAILABLE, "合成讀取結局為未選定投資組合；無列資訊"),
    "R3": DemoCase("R3", _ok_snapshot(dropped_non_numeric=1), TICKERS, True,
                   Availability.UNAVAILABLE, "合成快照含 1 列非數字（另 2 列可讀）"),
    "L1": DemoCase("L1", _ok_snapshot(), (), False,
                   Availability.UNAVAILABLE, "合成 2 列，均無組合鍵"),
    "L2": DemoCase("L2", _ok_snapshot(), TICKERS[:1], False,
                   Availability.PARTIAL, "合成 2 列，其中 1 列有組合鍵"),
    "L3": DemoCase("L3", _ok_snapshot(), TICKERS, False,
                   Availability.AVAILABLE, "合成 2 列，均有組合鍵"),
}
CASE_IDS = tuple(CASES)


# ══════════════════════════════════════════════════════════════════════
# 輸出型別
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Line:
    area: str
    text: str
    section: Optional[str] = None     # 僅 system_output：Digest 段鍵


@dataclass(frozen=True)
class DemoBlock:
    case_id: str
    lines: tuple
    fail_closed: bool
    error_type: Optional[str] = None  # fail-closed 時的例外型別名（不含資料值）

    def area(self, name: str) -> tuple:
        return tuple(ln.text for ln in self.lines if ln.area == name)


class DemoChainError(RuntimeError):
    """示範鏈檢查失敗（用 raise，不用 assert：-O 下也不得跳過）。"""


# ══════════════════════════════════════════════════════════════════════
# 鏈（經模組屬性呼叫 ⇒ 突變可介入）
# ══════════════════════════════════════════════════════════════════════
def _macro_state() -> dict:
    disc = RiskCapDisclosure(snapshot_ts="2026-10-26 18:30:00", not_evaluated=(), disabled=(), sahm_status=None)
    return {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5,
            "exposure_limit_pct": 60, "defense": False, "risk_cap_disclosure": disc}


def assemble(case: DemoCase, holdings_rows):
    m = _macro_state()

    def ev(name):
        return ASM.EvidenceInput(stamp=SourceStamp(name, _D), freshness=FreshnessStatus.FRESH)
    station = [{"代號": t, "held": True, "_action": "add", "建議動作": f"txt-add-{t}", "_detail": {}} for t in case.keyed]
    return ASM.assemble_digest(generated_at=_GENERATED_AT, macro_state=m, macro_evidence=ev("macro_state.json"),
                               allocation=build_allocation_decision(m), station_rows=station,
                               station_evidence=ev("dividend_station_service"), holdings_rows=holdings_rows,
                               holding_keys={t: HoldingKey(_PID, t) for t in case.keyed})


def providers(digest) -> dict:
    """FakeProvider 全模式（含 payload=None）＋兩種偽造草稿＋一種乾淨但內容不同的草稿。"""
    out = {mode: FakeProvider(mode) for mode in ALL_MODES}
    honest = S.compose_rule_draft(digest)
    out["forged_safe_literal"] = FakeProvider(MODE_PAYLOAD, SummaryDraft(
        (SummarySection("market", (SummarySentence((Lit("safe"),)),)),)))
    out["forged_drop_holdings"] = FakeProvider(MODE_PAYLOAD, SummaryDraft(
        tuple(s for s in honest.sections if s.key != "buy_and_hold")))
    m = honest.sections[0]
    out["clean_reordered"] = FakeProvider(MODE_PAYLOAD, SummaryDraft(
        (SummarySection(m.key, tuple(reversed(m.sentences))),) + honest.sections[1:]))
    return out


def derive_holdings_judgement(availability) -> Optional[str]:
    """D9：只讀 `digest.holdings.availability`。UNAVAILABLE／PARTIAL → 「⬜ 無法判定」；AVAILABLE → None（不輸出列）。
    其他任何值 ⇒ DemoChainError（呼叫端 fail-closed）。"""
    if availability is Availability.UNAVAILABLE or availability is Availability.PARTIAL:
        return HOLDINGS_UNDETERMINABLE
    if availability is Availability.AVAILABLE:
        return None
    raise DemoChainError("未預期的持股可用性")


def _section_lines(summary) -> list:
    secs = dict(summary.lines)
    out = []
    for key in SHOWN_SECTIONS:
        lines = secs.get(key)
        if not lines or any(type(x) is not str or not x for x in lines):
            raise DemoChainError(f"Digest 段 {key} 缺句或非字串")
        out += [(key, x) for x in lines]
    return out


def _guard_displayed(lines) -> None:
    for ln in lines:
        if ln.area in (AREA_UI_NOTE,):          # 白名單常數區（核定註記含「零持股」字樣，屬警示語）
            continue
        hit = [w for w in RUNTIME_BANNED if w in ln.text]
        if hit:
            raise DemoChainError(f"待顯示文字含禁字（{ln.area}）")


def _run_chain(case: DemoCase) -> tuple:
    res = A.adapt_holdings_read(case.snapshot)
    if (res.holdings_rows is None) is not case.expect_none:
        raise DemoChainError("adapter 結果路徑與案例預期不符")
    a = assemble(case, res.rows_for_digest())
    summary = S.build_rule_summary(a.digest)
    for mode, p in providers(a.digest).items():
        o = SH.run_shadow(a.digest, p)
        if p.calls < 1:
            raise DemoChainError(f"provider {mode} 未被呼叫")
        if o.effective != summary or o.effective != S.build_rule_summary(a.digest):
            raise DemoChainError(f"provider {mode}：effective ≠ build_rule_summary(digest)")
    availability = a.digest.holdings.availability
    if availability is not case.expect_availability:
        raise DemoChainError("持股可用性與案例預期不符")
    return availability, _section_lines(summary)


def _failclosed_block(case_id: str, err: BaseException) -> DemoBlock:
    _log.warning("onebrain holdings demo %s fail-closed: %s", case_id, type(err).__name__)
    lines = ([Line(AREA_DISCLOSURE, t) for t in DISCLOSURE_LINES]
             + [Line(AREA_DERIVED, f"{DERIVED_LABEL} {HOLDINGS_UNDETERMINABLE}{DERIVED_MARK}"),
                Line(AREA_UI_NOTE, FAILCLOSED_NOTE)]
             + [Line(AREA_FOOTER, t) for t in FOOTER_LINES])
    return DemoBlock(case_id, tuple(lines), True, type(err).__name__)


def build_case_block(case_id: str) -> DemoBlock:
    """純函式（給定 case id ⇒ 決定性輸出）。任何例外／檢查失敗 ⇒ fail-closed 區塊（記 log，不往上拋、不猜句子）。
    ⚠️ 未知 case id 是呼叫端錯誤 ⇒ KeyError 照常往上拋（不 fail-closed）。"""
    case = CASES[case_id]
    try:
        availability, sents = _run_chain(case)
        derived = derive_holdings_judgement(availability)
        lines = [Line(AREA_DISCLOSURE, t) for t in DISCLOSURE_LINES]
        if derived is not None:
            lines.append(Line(AREA_DERIVED, f"{DERIVED_LABEL} {derived}{DERIVED_MARK}"))
        lines += [Line(AREA_SYSTEM, text, key) for key, text in sents]
        if any(NOTE_NO_INPUT_TRIGGER in text for _k, text in sents):
            lines.append(Line(AREA_UI_NOTE, NOTE_NO_INPUT))
        lines += [Line(AREA_FOOTER, t) for t in FOOTER_LINES]
        lines.append(Line(AREA_TEST_INPUT, TEST_INPUT_PREFIX + case.test_input))
        _guard_displayed(lines)
        return DemoBlock(case_id, tuple(lines), False)
    except Exception as e:  # noqa: BLE001 — fail-closed：記 log、輸出固定安全區塊；BaseException 照常上傳
        return _failclosed_block(case_id, e)


# ══════════════════════════════════════════════════════════════════════
# 純文字呈現（模擬 tests/ 示範頁的 💼 OneBrain 槽；未接 UI2 hold view）
# ══════════════════════════════════════════════════════════════════════
def render_text(block: DemoBlock) -> str:
    out = []
    for ln in block.lines:
        if ln.area == AREA_SYSTEM:
            out.append(f"│ {SECTION_LABELS[ln.section]}｜{ln.text}")
        elif ln.area == AREA_TEST_INPUT:
            out.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄（以下非系統輸出）")
            out.append(f"┄ {ln.text}")
        else:
            out.append(f"│ {ln.text}")
    return "\n".join(out)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    sel = args[0] if args else "all"
    ids = CASE_IDS if sel == "all" else (sel,)
    for cid in ids:
        print(f"===== {cid}（tests/ 示範頁模擬 💼 OneBrain 槽；FAKE 離線示範、基準 main）=====")
        print(render_text(build_case_block(cid)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
