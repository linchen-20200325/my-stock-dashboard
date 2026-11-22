"""C-ONEBRAIN-SHADOW-CHAIN-TESTS-1 — OneBrain 持股跨層離線鏈：
`HoldingsReadSnapshot → adapt_holdings_read → assemble_digest → build_rule_summary → run_shadow(FakeProvider)`。

授權：Issue #1199 comment 7071984103（核准）；客戶口徑 7071998333；設計 7071897672。DEPENDS ON #1258（adapter）。
只新增本檔（tests-only）；⛔ 不改 adapter／Digest／schema／shared／production／既有測試／docs。

═══ 分類（每個測試名與 docstring 標其一，不可混用）═══════════════════════
- `norm_transition`：客戶已核准的**過渡期**語意（7071998333）——未知／異常輸入 ⇒ 整段無法判定；effective 恆為規則式摘要；
  adapter 原因碼**不傳遞**到下游（⚠️ 這是「未傳遞」，**不是**「已揭露」：下游目前沒有任何通道承載原因碼）。
  突變（`test_norm_transition_mutation_*`）與守衛（`test_norm_transition_guard_*`）用來證明這類測試有牙齒，歸同類。
- `current_behavior`：現況快照，**非規範**；轉紅表示行為改變，處置寫在各 docstring。
- `target_state`：未來目標態，**只能**以 `xfail(strict=True, raises=AssertionError)` 表達；XPASS ⇒ 缺口已補，升為正式斷言。
- `unit_guard`：結果型別建構期不變量的單元守衛（G7）；**不是**過渡期語意，也不是跨層鏈，只是補上此前無測試執行的檢查。

本檔聚焦**跨層鏈**；#1258 既有 48 測試已覆蓋的 adapter 單元斷言（分支表、建構期、repr 等）不重做。
全離線（socket 封鎖）、無時鐘（`generated_at` 固定）、不讀 Sheet、不呼叫真 Provider。
⚠️ 初版 116bd15e 經兩組非作者 QA 本地 PASS（#1261）；其後依 QA 意見的修訂為作者自測，尚未再經 QA。Digest NOT READY；OneBrain NOT READY。
"""
from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import socket
from datetime import date

import pytest

import src.data.portfolio.gsheet_portfolio as GSP
import src.services.decision_digest_assembly as ASM
import src.services.decision_digest_summary as S
import src.services.onebrain_holdings_adapter as A
import src.services.onebrain_shadow as SH
from shared.allocation_decision import build_allocation_decision
from shared.decision_digest import Availability, HoldingKey
from shared.decision_digest import AiParticipation
from shared.decision_digest_coverage import SEGMENT_HOLDINGS, WITHHELD_NOT_LOADED, DigestCoverage
from shared.decision_digest_grounding import (
    Lit,
    SummaryDraft,
    SummarySection,
    SummaryResult,
    SummarySentence,
)
from shared.freshness_policy import FreshnessStatus
from shared.onebrain_provider import ProviderErrorKind, ProviderRequest
from shared.risk_cap_policy import RiskCapDisclosure
from src.services.decision_digest_assembly import EvidenceInput
from src.services.decision_digest_builder import SourceStamp
from tests.decision_digest_factory import NOW
from tests.onebrain_fake_provider import (
    MODE_BOOM,
    MODE_ECHO,
    MODE_PAYLOAD,
    FakeProvider,
)
from tests.test_onebrain_holdings_input_contract import (
    EXPECT_LIST,
    contract_expected_holdings_input,
)

THIS_FILE = pathlib.Path(__file__).resolve()
D = date(2026, 10, 26)
PID = "pf-chain"
NAN = float("nan")
KEYED_STATION = ("0050", "0056")             # None 路徑：有鍵、有站內列（上游其餘齊備，只有持股未知）
LIST_TICKERS = ("0050", "7001")              # list 路徑：7001 為 IN-U 變體中的空白值列
ZERO_HOLDING_CLAIMS = ("0 檔", "0檔", "零檔", "無持股", "沒有持股", "空倉", "持股為零", "零持股", "持股 0")
NEUTRAL_SAFE_CLAIMS = ("中性", "正常", "安全", "SAFE", "safe", "neutral")
HOLDINGS_RELATED_SECTIONS = ("buy_and_hold", "capital_gain", "actions")


@pytest.fixture(autouse=True)
def _socket_blocked(monkeypatch):
    """整條鏈在 socket 封鎖下執行：任何連線嘗試 ＝ 測試失敗。"""
    def _no_net(*_a, **_k):
        raise AssertionError("離線鏈不得連網")
    monkeypatch.setattr(socket.socket, "connect", _no_net)
    monkeypatch.setattr(socket.socket, "connect_ex", _no_net)
    monkeypatch.setattr(socket, "create_connection", _no_net)


# ══════════════════════════════════════════════════════════════════════
# 合成輸入（直接建構 HoldingsReadSnapshot；不經資料層）
# ══════════════════════════════════════════════════════════════════════
_CLEAN = dict(dropped_blank_ticker=0, dropped_non_numeric=0, dropped_non_finite=0, dropped_non_positive=0,
              dropped_blank_value=0, kept_blank_value_count=0, kept_non_finite_count=0, duplicate_ticker_count=0)


def _ok(retained=False, kept=("0050", "0056"), source=None, **kw):
    counts = {**_CLEAN, **kw}
    if source is None and kept is not None:
        source = len(kept) + sum(counts[f] for f in A.DROP_REASON_FIELDS.values() if counts[f] is not None)
    return A.HoldingsReadSnapshot(A.OUTCOME_OK, retained, kept_tickers=kept, source_row_count=source, **counts)


#: 非 ok 結局 → 預期原因碼（只用公開常數逐一明列；不讀 adapter 私有對照表）。
_OUTCOME_EXPECTED = {
    A.OUTCOME_NOT_SELECTED: A.REASON_NOT_SELECTED,
    A.OUTCOME_STATUS_WORKSHEET_MISSING: A.REASON_READ_STATUS_WORKSHEET_MISSING,
    A.OUTCOME_STATUS_SCHEMA_MISMATCH: A.REASON_READ_STATUS_SCHEMA_MISMATCH,
    A.OUTCOME_STATUS_EMPTY: A.REASON_READ_STATUS_EMPTY,
    A.OUTCOME_STATUS_OTHER: A.REASON_READ_STATUS_OTHER,
    A.OUTCOME_EXCEPTION_LOGIN_REQUIRED: A.REASON_READ_EXCEPTION_LOGIN_REQUIRED,
    A.OUTCOME_EXCEPTION_PERMISSION_DENIED: A.REASON_READ_EXCEPTION_PERMISSION_DENIED,
    A.OUTCOME_EXCEPTION_SHEET_NOT_FOUND: A.REASON_READ_EXCEPTION_SHEET_NOT_FOUND,
    A.OUTCOME_EXCEPTION_QUOTA_EXCEEDED: A.REASON_READ_EXCEPTION_QUOTA_EXCEEDED,
    A.OUTCOME_EXCEPTION_NETWORK: A.REASON_READ_EXCEPTION_NETWORK,
    A.OUTCOME_EXCEPTION_WORKSHEET_MISSING: A.REASON_READ_EXCEPTION_WORKSHEET_MISSING,
    A.OUTCOME_EXCEPTION_SCHEMA_MISMATCH: A.REASON_READ_EXCEPTION_SCHEMA_MISMATCH,
    A.OUTCOME_EXCEPTION_OTHER: A.REASON_READ_EXCEPTION_OTHER,
}


def _none_cases() -> dict:
    """{label: (snapshot, 預期 adapter 原因碼)}：每一種 None 原因（未知各狀態、讀取例外各 kind、counts_unknown、
    tally_inconsistent、zero_rows、EX 各型、重複、非有限、預設模式 blank_value 丟列）。"""
    out = {o: (A.HoldingsReadSnapshot(o, False), (r,)) for o, r in _OUTCOME_EXPECTED.items()}
    out.update({
        "counts_all_none": (A.HoldingsReadSnapshot(A.OUTCOME_OK, False), (A.REASON_COUNTS_UNKNOWN,)),
        "counts_one_none": (_ok(kept_non_finite_count=None), (A.REASON_COUNTS_UNKNOWN,)),
        "tickers_none": (_ok(kept=None, source=2), (A.REASON_COUNTS_UNKNOWN,)),
        "tally_inconsistent": (_ok(source=5), (A.REASON_TALLY_INCONSISTENT,)),
        "zero_rows": (_ok(kept=()), (A.REASON_ZERO_ROWS,)),
        "ex_blank_ticker": (_ok(dropped_blank_ticker=1), (A.REASON_EX_DROPPED_BLANK_TICKER,)),
        "ex_non_numeric": (_ok(dropped_non_numeric=1), (A.REASON_EX_DROPPED_NON_NUMERIC,)),
        "ex_non_finite": (_ok(dropped_non_finite=1), (A.REASON_EX_DROPPED_NON_FINITE,)),
        "ex_non_positive": (_ok(dropped_non_positive=1), (A.REASON_EX_DROPPED_NON_POSITIVE,)),
        "non_finite_kept": (_ok(kept_non_finite_count=1), (A.REASON_NON_FINITE_KEPT,)),
        "duplicate": (_ok(kept=("2330", "2330"), duplicate_ticker_count=1), (A.REASON_DUPLICATE_TICKERS,)),
        "in_u_blank_dropped_default_mode": (_ok(dropped_blank_value=1), (A.REASON_IN_U_BLANK_DROPPED,)),
    })
    return out


def _list_cases() -> dict:
    """{label: (snapshot, 有鍵代號)}：乾淨／IN-U 保留 × 無鍵／部分有鍵／全有鍵。兩種變體代號相同（便於逐字比對）。"""
    clean = _ok(kept=LIST_TICKERS)
    in_u = _ok(retained=True, kept=LIST_TICKERS, kept_blank_value_count=1)
    keys = {"no_keys": (), "partial_keys": LIST_TICKERS[:1], "all_keys": LIST_TICKERS}
    out = {}
    for kname, keyed in keys.items():
        out[f"clean_{kname}"] = (clean, keyed)
        out[f"in_u_kept_{kname}"] = (in_u, keyed)
    return out


# ══════════════════════════════════════════════════════════════════════
# 鏈（經模組屬性呼叫 ⇒ 突變可介入）
# ══════════════════════════════════════════════════════════════════════
def _macro_state() -> dict:
    disc = RiskCapDisclosure(snapshot_ts="2026-10-26 18:30:00", not_evaluated=(), disabled=(), sahm_status=None)
    return {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5,
            "exposure_limit_pct": 60, "defense": False, "risk_cap_disclosure": disc}


def _assemble(holdings_rows, keyed):
    m = _macro_state()

    def ev(name):
        return EvidenceInput(stamp=SourceStamp(name, D), freshness=FreshnessStatus.FRESH)
    station = [{"代號": t, "held": True, "_action": "add", "建議動作": f"txt-add-{t}", "_detail": {}} for t in keyed]
    return ASM.assemble_digest(generated_at=NOW, macro_state=m, macro_evidence=ev("macro_state.json"),
                               allocation=build_allocation_decision(m), station_rows=station,
                               station_evidence=ev("dividend_station_service"), holdings_rows=holdings_rows,
                               holding_keys={t: HoldingKey(PID, t) for t in keyed})


def _providers(digest) -> dict:
    """FakeProvider：echo／boom（非 ProviderError）／timeout（ProviderError）／forged（偽造草稿兩種）／
    clean_reordered（通過 grounding、但內容與規則式草稿不同：market 段句序反轉）。"""
    honest = S.compose_rule_draft(digest)
    safe_literal = SummaryDraft((SummarySection("market", (SummarySentence((Lit("safe"),)),)),))
    drop_holdings = SummaryDraft(tuple(s for s in honest.sections if s.key != "buy_and_hold"))
    return {
        MODE_ECHO: FakeProvider(MODE_ECHO),
        MODE_BOOM: FakeProvider(MODE_BOOM),
        ProviderErrorKind.TIMEOUT.value: FakeProvider(ProviderErrorKind.TIMEOUT.value),
        "forged_safe_literal": FakeProvider(MODE_PAYLOAD, safe_literal),
        "forged_drop_holdings": FakeProvider(MODE_PAYLOAD, drop_holdings),
        MODE_CLEAN_REORDERED: FakeProvider(MODE_PAYLOAD, _clean_reordered_draft(honest)),
    }


MODE_CLEAN_REORDERED = "clean_reordered"
#: 草稿乾淨（應通過 grounding）的模式；其餘模式一律不得被接受。
CLEAN_MODES = (MODE_ECHO, MODE_CLEAN_REORDERED)


def _clean_reordered_draft(honest: SummaryDraft) -> SummaryDraft:
    """乾淨但內容不同的草稿：只把 market 段句序反轉（G5 不限段內句序；段落順序與句子集合不變）。"""
    m = honest.sections[0]
    return SummaryDraft((SummarySection(m.key, tuple(reversed(m.sentences))),) + honest.sections[1:])


@dataclasses.dataclass
class Chain:
    result: object
    assembled: object
    summary: object
    shadow: dict          # mode -> (ShadowOutcome, FakeProvider)


def _chain(snapshot, keyed, *, rows_override=None) -> Chain:
    res = A.adapt_holdings_read(snapshot)
    rows = res.rows_for_digest() if rows_override is None else rows_override
    a = _assemble(rows, keyed)
    summary = S.build_rule_summary(a.digest)
    shadow = {mode: (SH.run_shadow(a.digest, p), p) for mode, p in _providers(a.digest).items()}
    return Chain(res, a, summary, shadow)


def _downstream_text(c: Chain) -> str:
    """Digest＋coverage＋摘要＋ShadowOutcome＋ProviderRequest 的全文（原因碼洩漏檢查用）。"""
    parts = [json.dumps(c.assembled.to_dict(), ensure_ascii=False, sort_keys=True, default=str),
             json.dumps(c.summary.lines, ensure_ascii=False)]
    for o, p in c.shadow.values():
        parts.append(repr(o))
        for req in p.requests:
            assert type(req) is ProviderRequest
            parts += [repr(req), json.dumps(req.digest.to_dict(), ensure_ascii=False, default=str)]
    return "\n".join(parts)


def _fingerprint(c: Chain) -> str:
    """下游（不含 adapter 結果）的決定性指紋。"""
    return "\n".join([json.dumps(c.assembled.to_dict(), ensure_ascii=False, sort_keys=True, default=str),
                      json.dumps(c.summary.lines, ensure_ascii=False),
                      *(repr(o) for o, _ in c.shadow.values())])


def _check_shadow_effective_is_rule_summary(label: str, c: Chain) -> None:
    reordered = c.shadow[MODE_CLEAN_REORDERED][1].payload
    assert reordered != S.compose_rule_draft(c.assembled.digest), f"norm_transition：{label} 對照草稿須與規則式不同"
    for mode, (o, p) in c.shadow.items():
        assert p.calls >= 1, f"norm_transition：{label}/{mode} provider 應被呼叫"
        assert o.effective == c.summary, f"norm_transition：{label}/{mode} effective 必須恆為規則式摘要"
        if mode in CLEAN_MODES:
            assert o.shadow_accepted is True and o.error_kind is None, \
                f"norm_transition：{label}/{mode} 乾淨草稿應通過 grounding（只供離線比對、不採用）"
        else:
            assert o.shadow_accepted is False, f"norm_transition：{label}/{mode} 失敗／偽造不得被接受"
            assert isinstance(o.error_kind, ProviderErrorKind), f"norm_transition：{label}/{mode} 須分類錯誤"


def _check_reasons_not_transmitted(label: str, c: Chain) -> None:
    text = _downstream_text(c)
    leaked = [r for r in A.ALL_REASONS if r in text]
    assert not leaked, f"norm_transition：{label} 原因碼不得出現在下游（未傳遞，非已揭露）：{leaked}"


def _check_none_chain() -> None:
    for label, (snap, expected) in _none_cases().items():
        c = _chain(snap, KEYED_STATION)
        assert c.result.holdings_rows is None and c.result.reasons == expected, \
            f"norm_transition：{label} adapter 必須回 None＋{expected}，得到 {c.result.reasons}"
        d, cov = c.assembled.digest, c.assembled.coverage
        assert d.holdings.availability is Availability.UNAVAILABLE, f"norm_transition：{label} holdings 必須 UNAVAILABLE"
        assert d.holdings.entries == () and d.actions.items == (), f"norm_transition：{label} 不得有持股 entry／行動"
        assert cov.unkeyed_held_count is None, f"norm_transition：{label} coverage unkeyed_held_count 必須 None（未知）"
        assert cov.is_complete is False, f"norm_transition：{label} is_complete 必須 False"
        secs = dict(c.summary.lines)
        text = "\n".join(x for ls in secs.values() for x in ls)
        assert not [w for w in ZERO_HOLDING_CLAIMS if w in text], f"norm_transition：{label} 摘要不得宣稱零持股"
        for sec in HOLDINGS_RELATED_SECTIONS:
            assert secs[sec] and all("無法判定" in ln for ln in secs[sec]), \
                f"norm_transition：{label} {sec} 段須整段無法判定"
            assert not any(w in ln for ln in secs[sec] for w in NEUTRAL_SAFE_CLAIMS), \
                f"norm_transition：{label} {sec} 段不得以中性／正常／安全描述未知"
        _check_shadow_effective_is_rule_summary(label, c)
        _check_reasons_not_transmitted(label, c)


def _check_list_chain() -> None:
    for label, (snap, keyed) in _list_cases().items():
        c = _chain(snap, keyed)
        assert c.result.holdings_rows is not None, f"norm_transition：{label} 乾淨／IN-U 保留必須回 list"
        assert [r["ticker"] for r in c.result.holdings_rows] == list(LIST_TICKERS), f"norm_transition：{label} 列"
        d, cov = c.assembled.digest, c.assembled.coverage
        n_unkeyed = len(LIST_TICKERS) - len(keyed)
        assert [e.key.symbol for e in d.holdings.entries] == list(keyed), f"norm_transition：{label} 有鍵部位成 entry"
        assert d.holdings.unkeyed_count == n_unkeyed and cov.unkeyed_held_count == n_unkeyed, \
            f"norm_transition：{label} 無鍵部位（含 IN-U）須以計數保留"
        if n_unkeyed:
            assert cov.is_complete is False, f"norm_transition：{label} 有無鍵部位時 is_complete 必須 False"
            assert d.holdings.availability is not Availability.AVAILABLE, f"norm_transition：{label} 不得 AVAILABLE"
        text = "\n".join(x for _s, ls in c.summary.lines for x in ls)
        assert not [w for w in ZERO_HOLDING_CLAIMS if w in text], f"norm_transition：{label} 有部位時不得宣稱零持股"
        _check_shadow_effective_is_rule_summary(label, c)
        _check_reasons_not_transmitted(label, c)


# ══════════════════════════════════════════════════════════════════════
# norm_transition
# ══════════════════════════════════════════════════════════════════════
def test_norm_transition_none_paths_unknown_through_whole_chain():
    """[norm_transition] 每種 None 原因（含 EX／重複／非有限／預設模式丟 IN-U 等異常輸入）→ Digest holdings UNAVAILABLE、
    coverage 未知（None）、is_complete False、摘要無零持股字樣、持股與行動段整段「無法判定」且無中性／正常／安全；
    run_shadow 在 echo／boom／timeout／偽造／乾淨但內容不同下 effective 恆為規則式摘要；原因碼不出現在任何下游物件（未傳遞，非已揭露）。"""
    _check_none_chain()


def test_norm_transition_list_paths_positions_retained_through_whole_chain():
    """[norm_transition] 乾淨／IN-U 保留 × 無鍵／部分有鍵／全有鍵：部位不遺失（entries＋unkeyed＝列數）、
    有無鍵部位時 is_complete False、effective 恆為規則式摘要、原因碼不傳遞到下游。"""
    _check_list_chain()


def test_norm_transition_none_case_inventory_covers_every_none_reason():
    """[norm_transition] None 案例清單涵蓋 adapter 每一個 None 原因碼與每一個非 ok 結局（避免新原因碼／結局未進鏈測）。"""
    assert set(_OUTCOME_EXPECTED) == set(A.ALL_OUTCOMES) - {A.OUTCOME_OK}
    seen = {r for _s, rs in _none_cases().values() for r in rs}
    list_only = {A.REASON_IN_U_BLANK_KEPT, A.REASON_UNIVERSE_NOT_INDEPENDENT}
    assert seen == set(A.ALL_REASONS) - list_only


@pytest.mark.parametrize("kw, match", [
    (dict(kept_positions=1, in_u_positions=-1), "in_u_positions 在 list 路徑必須是非負 int"),
    (dict(kept_positions=True, in_u_positions=0), "kept_positions 在 list 路徑必須是非負 int"),
    (dict(kept_positions=1, in_u_positions=1.0), "in_u_positions 在 list 路徑必須是非負 int"),
    (dict(kept_positions=1, in_u_positions=2, reasons=(A.REASON_IN_U_BLANK_KEPT, A.REASON_UNIVERSE_NOT_INDEPENDENT)),
     "不得大於"),
    (dict(kept_positions=1, in_u_positions=1), "標示不一致"),
    (dict(kept_positions=1, in_u_positions=0, reasons=(A.REASON_IN_U_BLANK_KEPT, A.REASON_UNIVERSE_NOT_INDEPENDENT)),
     "標示不一致"),
], ids=["in_u_negative", "kept_bool", "in_u_float", "in_u_gt_kept", "in_u_without_reason", "reason_without_in_u"])
def test_unit_guard_g7_result_list_path_invariants_raise(kw, match):
    """[unit_guard；非過渡期語意] G7：`HoldingsAdapterResult` list 路徑三項此前未有測試執行的檢查——負數／非 int 計數、
    in_u > kept、in_u 與 `in_u_blank_kept` 原因碼不一致 ⇒ ValueError（各自命中預期訊息，非被其他檢查先擋）。"""
    base = dict(holdings_rows=({"ticker": "0050", "held": True},), reasons=(A.REASON_UNIVERSE_NOT_INDEPENDENT,))
    with pytest.raises(ValueError, match=match):
        A.HoldingsAdapterResult(**{**base, **kw})


# ══════════════════════════════════════════════════════════════════════
# current_behavior（現況快照，非規範）
# ══════════════════════════════════════════════════════════════════════
def test_current_behavior_g3_none_reasons_indistinguishable_downstream():
    """[current_behavior，非規範] G3：跨不同 None 原因，下游 Digest／coverage／摘要／ShadowOutcome 逐字相同——
    原因碼在下游**無承載**（不是已揭露）。轉紅 ⇒ 下游新增了原因通道：須同步 norm_transition 的不洩漏斷言與契約，記錄裁示。"""
    prints = {label: _fingerprint(_chain(s, KEYED_STATION)) for label, (s, _r) in _none_cases().items()}
    assert len(set(prints.values())) == 1, sorted(prints)
    assert len({_r for _s, _r in _none_cases().values()}) > 10      # 原因確實不同（adapter 層可區分）


@pytest.mark.parametrize("kname", ["no_keys", "partial_keys", "all_keys"])
def test_current_behavior_in_u_kept_identical_to_clean_downstream(kname):
    """[current_behavior，非規範] IN-U 保留列與同代號乾淨列：adapter 層可區分（原因碼／in_u_positions），
    下游 Digest／coverage／摘要／ShadowOutcome 逐字相同（IN-U 標記無承載；契約 §C-8）。轉紅 ⇒ 下游新增 IN-U 通道。"""
    cases = _list_cases()
    c_clean, c_in_u = _chain(*cases[f"clean_{kname}"]), _chain(*cases[f"in_u_kept_{kname}"])
    assert (c_clean.result.reasons, c_clean.result.in_u_positions) != (c_in_u.result.reasons, c_in_u.result.in_u_positions)
    assert _fingerprint(c_clean) == _fingerprint(c_in_u)


def test_current_behavior_g4_in_u_all_keyed_is_complete_true():
    """[current_behavior，非規範] G4：IN-U 保留列全部有鍵、站內齊備時 `is_complete` 現況為 True（coverage 看不到 IN-U）。
    目標態見 `test_target_state_in_u_all_keyed_must_not_claim_complete`（strict xfail）；轉紅 ⇒ 兩者一起升級。"""
    c = _chain(*_list_cases()["in_u_kept_all_keys"])
    assert A.REASON_IN_U_BLANK_KEPT in c.result.reasons
    assert c.assembled.coverage.is_complete is True


def test_current_behavior_g5_non_mapping_holdings_rows_report_zero_unkeyed():
    """[current_behavior，非規範；接線風險記錄] G5：若呼叫端誤把非 Mapping（例如原因碼字串 tuple）當 `holdings_rows` 傳入，
    coverage `unkeyed_held_count` 為 0（已知），不是 None（未知）；僅 `holdings_non_mapping_rows` 計數與 is_complete False 擋住。
    正確接線必須用 `rows_for_digest()`；轉紅 ⇒ builder 對非 Mapping 的處置改變，更新本快照。"""
    snap, _r = _none_cases()[A.OUTCOME_EXCEPTION_NETWORK]
    reasons = A.adapt_holdings_read(snap).reasons
    c = _chain(snap, KEYED_STATION, rows_override=reasons)
    cov = c.assembled.coverage
    assert cov.unkeyed_held_count == 0
    assert cov.holdings_non_mapping_rows == len(reasons) and cov.is_complete is False


# ── G1 known_divergence：契約 oracle（list）vs adapter（None）────────────
def _rec(ticker, lots=1, avg=10.0):
    return {"name": "合成組合", "ticker": ticker, "lots": lots, "avg_price": avg, "updated_at": "t"}


def _snapshot_from_tally(t) -> A.HoldingsReadSnapshot:
    """最小測試轉換（ok tally → 快照；概念同 #1258 測試檔，刻意複製、不 import 其私有物件）。"""
    assert t.status == GSP.READ_OK
    dropped = dict(t.dropped_by_reason)
    return A.HoldingsReadSnapshot(
        A.OUTCOME_OK, t.keep_blank, kept_tickers=tuple(r["ticker"] for r in t.rows), source_row_count=t.raw,
        **{A.DROP_REASON_FIELDS[k]: dropped[k] for k in A.DROP_REASON_KEYS},
        kept_blank_value_count=t.kept_with_missing_value, kept_non_finite_count=t.kept_non_finite,
        duplicate_ticker_count=len(t.duplicate_tickers))


INF = float("inf")
G1_DIVERGENCE_CASES = {
    "blank_ticker": ([_rec("0050"), _rec("")], False),
    "non_numeric": ([_rec("0050"), _rec("0056", lots="abc")], False),
    "neg_inf": ([_rec("0050"), _rec("0056", avg=-INF)], False),
    "non_positive": ([_rec("0050"), _rec("0056", lots=0)], False),
    "nan_kept": ([_rec("0050"), _rec("0056", lots=NAN)], False),
    "pos_inf_kept": ([_rec("0050", avg=INF)], True),
    "duplicate": ([_rec("2330"), _rec("2330", lots=2)], False),
    "duplicate_one_dropped": ([_rec("2330"), _rec("2330", lots=0)], False),
    "blank_dropped_default": ([_rec("0050"), _rec("7001", lots="")], False),
    "duplicate_with_blank_ticker": ([_rec("2330"), _rec("2330", lots=2), _rec("")], False),
    "all_dropped": ([_rec("", lots=1), _rec("0050", lots=0)], False),
    "combo": ([_rec("0050"), _rec("0050"), _rec("0056", lots=NAN), _rec("7001", lots=""), _rec("9001", lots="x")],
              False),
}


def test_current_behavior_g1_known_divergence_contract_oracle_list_vs_adapter_none():
    """[current_behavior，非規範；known_divergence] G1：12 個 EX／重複／非有限／IN-U 被丟案例——契約 oracle
    `contract_expected_holdings_input` 期望 list（契約 §A 第 9–11 列），adapter 回 None（保守降級）。
    此差異已由客戶裁示 #1199 comment 7071998333 定為「**過渡期 None、目標態 list**」；本測試只釘住兩邊現況。
    任一邊改動即紅 ⇒ 須對照裁示：adapter 轉 list 屬目標態落地（需揭露通道就緒，見 target_state xfail），
    oracle 改動屬契約變更；兩者都須記錄裁示，不得只改斷言。"""
    assert len(G1_DIVERGENCE_CASES) == 12
    for label, (recs, blank) in G1_DIVERGENCE_CASES.items():
        t = GSP.tally_portfolio_records(recs, keep_blank=blank)
        assert contract_expected_holdings_input(t) == EXPECT_LIST, f"{label}：oracle 應期望 list"
        res = A.adapt_holdings_read(_snapshot_from_tally(t))
        assert res.holdings_rows is None and res.reasons, f"{label}：adapter 過渡期應回 None＋原因碼"


# ══════════════════════════════════════════════════════════════════════
# target_state（strict xfail；只表達未來目標態）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "target_state：契約 §B2 第 1 點（缺獨立應有母體：任何以 L1 rows 餵入者 coverage 必須 incomplete）、§C-6、"
    "§C-8(a)（IN-U 在 coverage 的標示）＋#1199 comment 7071998333——IN-U 列全部有鍵時 coverage 不得宣稱完整；"
    "現行 coverage 無 IN-U／母體欄位，is_complete=True。此為 §C-6 缺口的特例（clean_all_keys 同樣 is_complete=True，"
    "已由 #1254 strict xfail 釘住）。需 coverage／schema 放行。XPASS ⇒ 升為正式斷言。"))
def test_target_state_in_u_all_keyed_must_not_claim_complete():
    """[target_state] IN-U 全有鍵時 coverage 不得宣稱完整（預期失敗於 is_complete 斷言）。"""
    c = _chain(*_list_cases()["in_u_kept_all_keys"])
    assert c.assembled.coverage.is_complete is False, "target_state：IN-U 全有鍵仍不得宣稱完整"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "target_state：main 契約 §A 第 9–11 列與 §C-2（EX 剔除、其餘 list、剔除須可回報）＋客戶裁示 #1199 comment 7071998333"
    "（過渡期 None、目標態 list）——目前 Digest／coverage 無承載剔除列數與原因的通道，adapter 保守降級為 None。"
    "XPASS ⇒ 揭露通道已就緒：升為正式斷言，並同步 G1 known_divergence 快照與 norm_transition 鏈。"))
def test_target_state_ex_removed_rows_kept_and_disclosed():
    """[target_state] EX 剔除後保留其餘列（只含有效列）並揭露剔除 N 列與原因（預期失敗於 adapter 仍回 None 的斷言）。
    揭露通道的 schema 名稱**待定**，故不綁欄位名：以通用方式在 Digest／coverage 的 to_dict 與摘要中找「非零剔除計數」或
    「明示的剔除原因」。"""
    snap = _ok(kept=("0050",), dropped_non_numeric=1)
    res = A.adapt_holdings_read(snap)
    assert res.holdings_rows is not None, "target_state：EX 剔除後應保留其餘列（list）"
    assert [r["ticker"] for r in res.holdings_rows] == ["0050"], "target_state：只含有效列"
    c = _chain(snap, ("0050",))
    assert _has_observable_exclusion_disclosure(c), "target_state：下游須可觀測到剔除列數或原因"


_EXCLUSION_KEY_HINTS = ("exclu", "drop", "remov", "reject", "剔除")
_EXCLUSION_TEXT_HINTS = ("剔除", "non_numeric", "ex_dropped")


def _has_observable_exclusion_disclosure(c: Chain) -> bool:
    """通用揭露檢查（不綁 schema 名）：任一鍵名含剔除語意且值為非零 int，或任一字串明示剔除原因。
    ⚠️ 既有 `excluded_invalid_rows` 是站內列計數，本情境站內列乾淨（恆 0），不會誤判。"""
    found = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v, key)
        elif type(o) is int and o > 0 and any(h in key.lower() for h in _EXCLUSION_KEY_HINTS):
            found.append(key)
        elif isinstance(o, str) and any(h in o for h in _EXCLUSION_TEXT_HINTS):
            found.append(o)
    walk(c.assembled.to_dict())
    walk([ln for _s, ls in c.summary.lines for ln in ls])
    return bool(found)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "target_state：CLAUDE.md §1（missing≠0、Fail Loud）＋契約 §B1（未知不得映成已知）——holdings_rows 含非 Mapping 列時，"
    "應 fail-loud（TypeError／ValueError）或 coverage unkeyed_held_count 為 None（未知）；現況為 0（已知），見 G5 current_behavior。"
    "XPASS ⇒ 升為正式斷言並更新 G5 快照。"))
def test_target_state_g5_non_mapping_holdings_rows_fail_loud_or_unknown():
    """[target_state] G5：非 Mapping 的 holdings_rows 不得被算成「已知 0 個無鍵部位」（預期失敗於 unkeyed_held_count 斷言）。"""
    snap, _r = _none_cases()[A.OUTCOME_EXCEPTION_NETWORK]
    reasons = A.adapt_holdings_read(snap).reasons
    try:
        c = _chain(snap, KEYED_STATION, rows_override=reasons)
    except (TypeError, ValueError):
        return                                                       # fail-loud 亦符合目標態
    assert c.assembled.coverage.unkeyed_held_count is None, "target_state：非 Mapping 列 ⇒ unkeyed 必須未知（None），不是 0"


_NO_INPUT_WORDING = "（尚無輸入）"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "target_state：客戶裁示 #1199 comment 7071998333 第 3 點＋契約 §C-2（「尚無輸入」描述不準）——None 路徑中來源**有讀到但異常**"
    "（EX／重複／非有限／丟 IN-U）或**讀取例外**時，持股段文案不得為「（尚無輸入）」，coverage holdings 段 withheld_reason 不得為 "
    "not_loaded。具體文案與原因值待 UI Gate，本測試只斷言「不得是」。XPASS ⇒ 升為正式斷言。"))
def test_target_state_none_path_wording_not_no_input_and_not_not_loaded():
    """[target_state] EX／讀取例外的 None 路徑：持股段不得寫成「尚無輸入」、withheld_reason 不得為 not_loaded
    （預期失敗於第一個案例的文案斷言）。"""
    labels = [k for k in _none_cases() if k.startswith(("ex_", "exception_"))]
    labels += ["non_finite_kept", "duplicate", "in_u_blank_dropped_default_mode"]
    assert len(labels) >= 12
    for label in labels:
        c = _chain(_none_cases()[label][0], KEYED_STATION)
        secs = dict(c.summary.lines)
        for sec in HOLDINGS_RELATED_SECTIONS[:2]:
            assert not any(_NO_INPUT_WORDING in ln for ln in secs[sec]), \
                f"target_state：{label} {sec} 段不得寫成「尚無輸入」"
        seg = {g.segment: g for g in c.assembled.coverage.segments}[SEGMENT_HOLDINGS]
        assert seg.withheld_reason != WITHHELD_NOT_LOADED, f"target_state：{label} withheld_reason 不得為 not_loaded"


# ══════════════════════════════════════════════════════════════════════
# 突變（monkeypatch 自動還原）：證明 norm_transition 有牙齒
# ══════════════════════════════════════════════════════════════════════
def test_norm_transition_mutation_baselines_are_green():
    """[norm_transition] 突變基準：未突變時兩條鏈檢查皆綠。"""
    _check_none_chain()
    _check_list_chain()


def test_norm_transition_mutation_reason_injected_into_coverage_turns_red(monkeypatch):
    """[norm_transition] 突變 1：adapter 原因碼被「傳遞」進 coverage（to_dict 多一欄）⇒ 不洩漏斷言轉紅。"""
    last: list = []
    orig_adapt, orig_to_dict = A.adapt_holdings_read, DigestCoverage.to_dict

    def _adapt(s):
        r = orig_adapt(s)
        last[:] = r.reasons
        return r

    def _to_dict(self):
        return {**orig_to_dict(self), "holdings_reasons": list(last)}
    monkeypatch.setattr(A, "adapt_holdings_read", _adapt)
    monkeypatch.setattr(DigestCoverage, "to_dict", _to_dict)
    with pytest.raises(AssertionError, match="norm_transition：.*原因碼不得出現在下游"):
        _check_none_chain()
    with pytest.raises(AssertionError, match="norm_transition：.*原因碼不得出現在下游"):
        _check_list_chain()


def test_norm_transition_mutation_run_shadow_adopts_provider_draft_turns_red(monkeypatch):
    """[norm_transition] 突變 2：run_shadow 採用 provider 草稿（未失敗時以草稿取代 effective）⇒ effective 斷言轉紅。"""
    orig = SH.run_shadow

    def _mut(digest, provider):
        o = orig(digest, provider)
        try:
            draft = provider.propose_summary(ProviderRequest(digest=digest))
        except Exception:  # noqa: BLE001 — 突變體：失敗時沿用規則式
            return o
        return dataclasses.replace(o, effective=draft)
    monkeypatch.setattr(SH, "run_shadow", _mut)
    with pytest.raises(AssertionError, match="norm_transition：.*effective 必須恆為規則式摘要"):
        _check_none_chain()


def test_norm_transition_mutation_run_shadow_adopts_only_clean_draft_turns_red(monkeypatch):
    """[norm_transition] 突變 2b：run_shadow「只在草稿乾淨時採用」⇒ 乾淨但內容不同（clean_reordered）的情境轉紅
    （echo 草稿與規則式相同，抓不到；本情境專抓這種回歸）。"""
    orig = SH.run_shadow

    def _mut(digest, provider):
        o = orig(digest, provider)
        if not o.shadow_accepted:
            return o
        draft = provider.propose_summary(ProviderRequest(digest=digest))
        adopted = SummaryResult(digest=digest, mode=AiParticipation.RULE_ONLY, sections=draft.sections)
        return dataclasses.replace(o, effective=adopted)
    monkeypatch.setattr(SH, "run_shadow", _mut)
    with pytest.raises(AssertionError, match="norm_transition：.*/clean_reordered effective 必須恆為規則式摘要"):
        _check_none_chain()
    with pytest.raises(AssertionError, match="norm_transition：.*/clean_reordered effective 必須恆為規則式摘要"):
        _check_list_chain()


def test_norm_transition_mutation_adapter_ex_back_to_list_turns_red(monkeypatch):
    """[norm_transition] 突變 3：adapter 對 EX 證據改回 list（移除 EX 降級）⇒ None 鏈斷言轉紅。"""
    monkeypatch.setattr(A, "_ex_evidence_reasons", lambda s: ())
    with pytest.raises(AssertionError, match="norm_transition：ex_.*adapter 必須回 None"):
        _check_none_chain()


# ══════════════════════════════════════════════════════════════════════
# 守衛
# ══════════════════════════════════════════════════════════════════════
def test_norm_transition_guard_socket_block_is_active_for_chain():
    """[norm_transition] 守衛：本檔 socket 封鎖確實生效（connect／connect_ex／create_connection 皆 AssertionError），且鏈在封鎖下可完整執行。"""
    with pytest.raises(AssertionError, match="離線鏈不得連網"):
        socket.create_connection(("127.0.0.1", 9))
    with pytest.raises(AssertionError, match="離線鏈不得連網"):
        socket.socket().connect(("127.0.0.1", 9))
    with pytest.raises(AssertionError, match="離線鏈不得連網"):
        socket.socket().connect_ex(("127.0.0.1", 9))
    snap, _r = _none_cases()["zero_rows"]
    assert _chain(snap, KEYED_STATION).shadow[MODE_ECHO][0].effective is not None


def test_norm_transition_guard_this_file_offline_and_clockless_by_ast():
    """[norm_transition] 守衛：本檔 AST 無時鐘呼叫（now／today／utcnow／time.time／perf_counter／monotonic，含屬性與
    裸名呼叫）、不得 `import time`／`from datetime import datetime`、無網路套件 import、
    無 socket 實連呼叫（connect／create_connection 只以 monkeypatch 字串名替換、在被封鎖狀態下呼叫）。"""
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    banned_mods = {"requests", "urllib", "httpx", "gspread", "streamlit", "anthropic", "openai", "google", "time"}
    clock_attrs = ("now", "today", "utcnow", "time", "time_ns", "perf_counter", "monotonic", "localtime", "gmtime")
    mods: set = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
            if n.module.split(".")[0] == "datetime":
                assert {a.name for a in n.names} <= {"date"}, "本檔只可 from datetime import date（不得取 datetime 類別）"
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                assert f.attr not in clock_attrs + ("load_portfolio", "load_portfolio_tallied"), f.attr
            elif isinstance(f, ast.Name):
                assert f.id not in clock_attrs, f.id
    assert not (mods & banned_mods), mods & banned_mods
