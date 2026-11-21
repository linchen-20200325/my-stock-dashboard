"""C-OB-HOLDINGS-ADAPTER-DORMANT-1 — `src/services/onebrain_holdings_adapter.py`（純資料 dormant L3 adapter）的合成驗收。

授權：Issue #1199 comment 7062910532；純資料介面設計 7063534925、逐項裁定 7063710260。
契約：`docs/vnext/ONEBRAIN_HOLDINGS_INPUT_CONTRACT_2026-11-21.md`（§A／§B／§C）。

- **轉換邊界**：資料層讀取結果 → `HoldingsReadSnapshot` 的轉換器 `snapshot_from_tally`／`snapshot_from_exception`
  **只存在本檔**（測試專用；正式轉換與來源驗證待接線 Gate）。快照通過驗證只代表形狀與自洽。
- 資料層 tally 一律以純函式 `tally_portfolio_records` 由合成 records 產生，或直接建構表示非 ok 狀態；讀取失敗以合成例外物件
  表示。⛔ 不讀 Sheet、不呼叫資料層讀取入口、不連網（socket 守衛）、不呼叫時鐘。
- 分類：規範＝`test_norm_*`；漂移＝`test_drift_*`；現況快照＝名稱含 `current_behavior`（非規範）；突變＝`test_mutation_*`；
  守衛＝`test_guard_*`。
⚠️ 作者自測；未經獨立 QA。Digest NOT READY。
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
import socket
import subprocess
import sys
import types
from datetime import date

import pytest

import src.data.portfolio.gsheet_portfolio as GSP
import src.services.onebrain_holdings_adapter as A
from shared.allocation_decision import build_allocation_decision
from shared.decision_digest import Availability, HoldingKey
from shared.freshness_policy import FreshnessStatus
from shared.risk_cap_policy import RiskCapDisclosure
from src.services.decision_digest_assembly import EvidenceInput, assemble_digest
from src.services.decision_digest_builder import SourceStamp
from src.services.decision_digest_summary import build_rule_summary
from tests.decision_digest_factory import NOW

REPO = pathlib.Path(__file__).resolve().parents[1]
ADAPTER_FILE = REPO / "src" / "services" / "onebrain_holdings_adapter.py"
D = date(2026, 10, 26)
NAN, INF = float("nan"), float("inf")
PID = "pf-selected"
PF_NAME = "核心組合"                       # 合成組合名：不得出現在任何原因碼
SHEET_ID = "sheet-SYNTH-1234567890"       # 合成 sheet_id：不得出現在任何原因碼
IDENTITY = "someone@example.invalid"      # 合成身分：不得出現在任何原因碼
IN_U_TICKERS = ("7001", "7002")           # 合成：專供張數／均價空白（IN-U）列使用
SYNTH_TICKERS = ("0050", "0056", "2330", "9001", "00878", *IN_U_TICKERS)

# 最小常數（概念同 #1254 契約測試；刻意複製，⛔ 不 import 該檔私有物件）
ZERO_HOLDING_CLAIMS = ("0 檔", "0檔", "零檔", "無持股", "沒有持股", "空倉", "持股為零", "零持股", "持股 0")
NEUTRAL_SAFE_CLAIMS = ("中性", "正常", "安全", "SAFE", "safe", "neutral")
HOLDINGS_RELATED_SECTIONS = ("buy_and_hold", "capital_gain", "actions")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("測試不得連網")
    monkeypatch.setattr(socket.socket, "connect", _boom)


# ══════════════════════════════════════════════════════════════════════
# 測試專用轉換器（資料層 → 快照）；⛔ 不得被 production 引用
# ══════════════════════════════════════════════════════════════════════
#: 資料層狀態 → 快照結局。資料層每個非錯誤類 `READ_*` 狀態都必須在此明列（漂移測試強制）。
STATUS_TO_OUTCOME = {
    GSP.READ_OK: A.OUTCOME_OK,
    GSP.TALLY_NOT_SELECTED: A.OUTCOME_NOT_SELECTED,
    GSP.READ_WORKSHEET_MISSING: A.OUTCOME_STATUS_WORKSHEET_MISSING,
    GSP.READ_SCHEMA_MISMATCH: A.OUTCOME_STATUS_SCHEMA_MISMATCH,
    GSP.READ_EMPTY: A.OUTCOME_STATUS_EMPTY,
    GSP.READ_NOT_CONFIGURED: A.OUTCOME_STATUS_OTHER,     # tally 路徑不會產生；明列以免漂移守衛誤報
}
#: 資料層 `classify_read_error` 代碼 → 快照結局（`error:<型別>` 一律 OTHER）。
ERROR_TO_OUTCOME = {
    GSP.READ_ERROR_LOGIN_REQUIRED: A.OUTCOME_EXCEPTION_LOGIN_REQUIRED,
    GSP.READ_ERROR_PERMISSION_DENIED: A.OUTCOME_EXCEPTION_PERMISSION_DENIED,
    GSP.READ_ERROR_SHEET_NOT_FOUND: A.OUTCOME_EXCEPTION_SHEET_NOT_FOUND,
    GSP.READ_ERROR_QUOTA_EXCEEDED: A.OUTCOME_EXCEPTION_QUOTA_EXCEEDED,
    GSP.READ_ERROR_NETWORK: A.OUTCOME_EXCEPTION_NETWORK,
    GSP.READ_WORKSHEET_MISSING: A.OUTCOME_EXCEPTION_WORKSHEET_MISSING,
    GSP.READ_SCHEMA_MISMATCH: A.OUTCOME_EXCEPTION_SCHEMA_MISMATCH,
}


def snapshot_from_exception(exc: BaseException, *, retained: bool = False) -> A.HoldingsReadSnapshot:
    """讀取例外 → 快照（只看型別：經資料層 `classify_read_error`）。訊息與型別名不進快照。"""
    return A.HoldingsReadSnapshot(ERROR_TO_OUTCOME.get(GSP.classify_read_error(exc), A.OUTCOME_EXCEPTION_OTHER), retained)


def snapshot_from_tally(t) -> A.HoldingsReadSnapshot:
    """資料層 tally → 快照。未知狀態收成 status_other；未知或缺漏的丟列鍵 ⇒ raise（拒收，不猜）。"""
    if type(t) is not GSP.PortfolioReadTally:
        raise TypeError(type(t).__name__)
    outcome = STATUS_TO_OUTCOME.get(t.status, A.OUTCOME_STATUS_OTHER)
    if outcome != A.OUTCOME_OK:
        return A.HoldingsReadSnapshot(outcome, t.keep_blank)
    dropped = None if t.dropped_by_reason is None else dict(t.dropped_by_reason)
    if dropped is not None and set(dropped) != set(A.DROP_REASON_KEYS):
        raise ValueError("snapshot_from_tally：丟列鍵與快照詞彙不一致（未知或缺漏），拒收")
    drop_kw = {A.DROP_REASON_FIELDS[k]: None if dropped is None else dropped[k] for k in A.DROP_REASON_KEYS}
    return A.HoldingsReadSnapshot(
        outcome, t.keep_blank,
        kept_tickers=None if t.rows is None else tuple(r["ticker"] for r in t.rows),
        source_row_count=t.raw, **drop_kw,
        kept_blank_value_count=t.kept_with_missing_value, kept_non_finite_count=t.kept_non_finite,
        duplicate_ticker_count=None if t.duplicate_tickers is None else len(t.duplicate_tickers))


# ── 合成輸入 ───────────────────────────────────────────────────────────
def _rec(ticker, lots=1, avg=10.0):
    return {"name": PF_NAME, "ticker": ticker, "lots": lots, "avg_price": avg, "updated_at": "t"}


def _tally(recs, *, blank=False, **parts):
    return GSP.tally_portfolio_records(recs, **{"keep_blank": blank}, **parts)


def _snap(recs, *, blank=False, **parts):
    return snapshot_from_tally(_tally(recs, blank=blank, **parts))


def _ok(**kw):
    """直接建構 ok 快照（預設：兩檔乾淨列）。"""
    base = dict(kept_tickers=("0050", "0056"), source_row_count=2, dropped_blank_ticker=0, dropped_non_numeric=0,
                dropped_non_finite=0, dropped_non_positive=0, dropped_blank_value=0, kept_blank_value_count=0,
                kept_non_finite_count=0, duplicate_ticker_count=0)
    retained = kw.pop("retained", False)
    return A.HoldingsReadSnapshot(A.OUTCOME_OK, retained, **{**base, **kw})


def _adapt(x):
    return A.adapt_holdings_read(x)          # 經模組屬性呼叫 ⇒ 突變測試可替換


_SECRET_MSG = f"0050 {SHEET_ID} {IDENTITY} {PF_NAME} 403"


def _exception_cases():
    return {
        "login_required": (GSP.LoginRequiredError(_SECRET_MSG), A.REASON_READ_EXCEPTION_LOGIN_REQUIRED),
        "permission": (PermissionError(_SECRET_MSG), A.REASON_READ_EXCEPTION_PERMISSION_DENIED),
        "network": (ConnectionError(_SECRET_MSG), A.REASON_READ_EXCEPTION_NETWORK),
        "timeout": (TimeoutError(_SECRET_MSG), A.REASON_READ_EXCEPTION_NETWORK),
        "worksheet_missing_exc": (GSP.SheetWorksheetMissingError(GSP._WORKSHEET_NAME),
                                  A.REASON_READ_EXCEPTION_WORKSHEET_MISSING),
        "schema_mismatch_exc": (GSP.SheetSchemaMismatchError(GSP._WORKSHEET_NAME, GSP._HEADERS),
                                A.REASON_READ_EXCEPTION_SCHEMA_MISMATCH),
        "runtime_other": (RuntimeError(_SECRET_MSG), A.REASON_READ_EXCEPTION_OTHER),
        "value_other": (ValueError(_SECRET_MSG), A.REASON_READ_EXCEPTION_OTHER),
    }


#: EX／IN-U 丟失證據 ⇒ None：(records, 保留空白值模式, 原因碼集合)
DEGRADE_CASES = {
    "blank_ticker": ([_rec("0050"), _rec("")], False, {A.REASON_EX_DROPPED_BLANK_TICKER}),
    "non_numeric": ([_rec("0050"), _rec("0056", lots="abc")], False, {A.REASON_EX_DROPPED_NON_NUMERIC}),
    "neg_inf": ([_rec("0050"), _rec("0056", avg=-INF)], False, {A.REASON_EX_DROPPED_NON_FINITE}),
    "non_positive": ([_rec("0050"), _rec("0056", lots=0)], False, {A.REASON_EX_DROPPED_NON_POSITIVE}),
    "nan_kept": ([_rec("0050"), _rec("0056", lots=NAN)], False, {A.REASON_NON_FINITE_KEPT}),
    "pos_inf_kept": ([_rec("0050", avg=INF)], True, {A.REASON_NON_FINITE_KEPT}),
    "duplicate": ([_rec("2330"), _rec("2330", lots=2)], False, {A.REASON_DUPLICATE_TICKERS}),
    "duplicate_one_dropped": ([_rec("2330"), _rec("2330", lots=0)], False,
                              {A.REASON_DUPLICATE_TICKERS, A.REASON_EX_DROPPED_NON_POSITIVE}),
    "blank_dropped_default": ([_rec("0050"), _rec("7001", lots="")], False, {A.REASON_IN_U_BLANK_DROPPED}),
    "duplicate_with_blank_ticker": ([_rec("2330"), _rec("2330", lots=2), _rec("")], False,   # 界限恰好相等：仍合法
                                    {A.REASON_DUPLICATE_TICKERS, A.REASON_EX_DROPPED_BLANK_TICKER}),
    "all_dropped": ([_rec("", lots=1), _rec("0050", lots=0)], False,
                    {A.REASON_EX_DROPPED_BLANK_TICKER, A.REASON_EX_DROPPED_NON_POSITIVE}),
    "combo": ([_rec("0050"), _rec("0050"), _rec("0056", lots=NAN), _rec("7001", lots=""), _rec("9001", lots="x")],
              False, {A.REASON_DUPLICATE_TICKERS, A.REASON_NON_FINITE_KEPT, A.REASON_IN_U_BLANK_DROPPED,
                      A.REASON_EX_DROPPED_NON_NUMERIC}),
}
#: 乾淨 ⇒ list：(records, 保留空白值模式, 預期代號序列, 預期 IN-U 數, P0 分區)
LIST_CASES = {
    "clean_default": ([_rec("0050"), _rec("0056"), _rec("9001")], False, ["0050", "0056", "9001"], 0, {}),
    "clean_retained": ([_rec("0050"), _rec("0056")], True, ["0050", "0056"], 0, {}),
    "in_u_blank_kept": ([_rec("0050"), _rec("7001", lots=""), _rec("7002", avg="  ")], True,
                        ["0050", "7001", "7002"], 2, {}),
    "all_in_u": ([_rec("7001", lots=""), _rec("7002", avg="")], True, ["7001", "7002"], 2, {}),
    "mixed_stock_and_etf_codes": ([_rec("2330"), _rec("00878"), _rec("0056"), _rec("006208"), _rec("0050")], False,
                                  ["2330", "00878", "0056", "006208", "0050"], 0, {}),   # 前導零保留、原樣、順序不變
    "with_other_partitions": ([_rec("00878")], False, ["00878"], 0,
                              dict(other_name_rows=4, blank_rows=1, blank_name_rows=2)),
}


def _none_inputs():
    """所有應得 None 的快照：{label: (snapshot, 預期原因碼集合)}。快照於呼叫時建構（突變可介入建構期）。"""
    out = {k: (snapshot_from_exception(e), {r}) for k, (e, r) in _exception_cases().items()}
    out.update({
        "not_selected": (snapshot_from_tally(GSP.PortfolioReadTally(GSP.TALLY_NOT_SELECTED, False)), {A.REASON_NOT_SELECTED}),
        "worksheet_missing": (snapshot_from_tally(GSP.PortfolioReadTally(GSP.READ_WORKSHEET_MISSING, False)),
                              {A.REASON_READ_STATUS_WORKSHEET_MISSING}),
        "schema_mismatch": (snapshot_from_tally(GSP.PortfolioReadTally(GSP.READ_SCHEMA_MISMATCH, True)),
                            {A.REASON_READ_STATUS_SCHEMA_MISMATCH}),
        "empty": (snapshot_from_tally(GSP.PortfolioReadTally(GSP.READ_EMPTY, False)), {A.REASON_READ_STATUS_EMPTY}),
        "unknown_status": (snapshot_from_tally(GSP.PortfolioReadTally(f"weird_{SHEET_ID}_7", False)),
                           {A.REASON_READ_STATUS_OTHER}),
        "ok_all_counts_none": (snapshot_from_tally(GSP.PortfolioReadTally(GSP.READ_OK, False)), {A.REASON_COUNTS_UNKNOWN}),
        "ok_one_count_none": (_ok(kept_non_finite_count=None), {A.REASON_COUNTS_UNKNOWN}),
        "ok_tickers_none": (_ok(kept_tickers=None), {A.REASON_COUNTS_UNKNOWN}),
        "inconsistent_rowcount": (_ok(source_row_count=5), {A.REASON_TALLY_INCONSISTENT}),
        "inconsistent_from_tally": (snapshot_from_tally(dataclasses.replace(_tally([_rec("0050")]), raw=3)),
                                    {A.REASON_TALLY_INCONSISTENT}),
        "inconsistent_retained_but_blank_dropped": (_ok(retained=True, source_row_count=3, dropped_blank_value=1),
                                                    {A.REASON_TALLY_INCONSISTENT}),
        "inconsistent_default_but_blank_kept": (_ok(kept_blank_value_count=1), {A.REASON_TALLY_INCONSISTENT}),
        "inconsistent_kept_dup_claims_none": (_ok(kept_tickers=("0050", "0050")), {A.REASON_TALLY_INCONSISTENT}),
        "inconsistent_dup_exceeds_source_rows": (_ok(duplicate_ticker_count=2), {A.REASON_TALLY_INCONSISTENT}),
        "inconsistent_dup_exceeds_nonblank_ticker_rows": (     # 舊界限（≤ 來源列數）會放行；收緊後才抓到
            _ok(kept_tickers=("0050",), source_row_count=2, dropped_blank_ticker=1, duplicate_ticker_count=1),
            {A.REASON_TALLY_INCONSISTENT}),
        "inconsistent_flavors_exceed_kept": (_ok(kept_blank_value_count=2, kept_non_finite_count=1, retained=True),
                                             {A.REASON_TALLY_INCONSISTENT}),
        "zero_rows": (_snap([]), {A.REASON_ZERO_ROWS}),
        "zero_rows_absent_name": (_snap([], other_name_rows=3), {A.REASON_ZERO_ROWS}),
        "zero_rows_retained": (_snap([], blank=True, other_name_rows=1, blank_rows=2), {A.REASON_ZERO_ROWS}),
    })
    out.update({k: (_snap(recs, blank=b), rs) for k, (recs, b, rs) in DEGRADE_CASES.items()})
    return out


def _list_inputs():
    return {k: (_snap(recs, blank=b, **parts), tks, inu) for k, (recs, b, tks, inu, parts) in LIST_CASES.items()}


# ══════════════════════════════════════════════════════════════════════
# 規範：分支表
# ══════════════════════════════════════════════════════════════════════
def _check_none_paths() -> None:
    for label, (s, expected) in _none_inputs().items():
        res = _adapt(s)
        assert res.holdings_rows is None, f"規範 §B1：{label} 必須回 None（未知不得映成 [] 或 list），得到 {res.holdings_rows!r}"
        assert set(res.reasons) == expected, f"規範：{label} 原因碼 {res.reasons} ≠ {sorted(expected)}"
        assert res.reasons, f"規範：{label} None 時原因碼不得為空"
        assert res.kept_positions is None and res.in_u_positions is None, f"規範 §B1：{label} 計數必須 None（未知不是 0）"


def test_norm_none_branches_table():
    """§B1／§B3：例外、非 ok 狀態、計數未知、跨欄不一致、零列、EX 證據、未保留模式丟 IN-U ⇒ None＋固定原因碼。"""
    _check_none_paths()


def _check_list_paths() -> None:
    for label, (s, tickers, in_u) in _list_inputs().items():
        res = _adapt(s)
        assert res.holdings_rows is not None, f"規範：{label} 乾淨來源必須回 list，得到 None（{res.reasons}）"
        rows = list(res.holdings_rows)
        assert len(rows) == len(s.kept_tickers), f"規範 §B3：{label} 輸出列數必須＝保留列數（不得遺失／灌水）"
        assert [r["ticker"] for r in rows] == tickers, f"規範 §B3：{label} 每列一筆、順序不變、不丟 IN-U：{rows}"
        assert all(set(r) == {"ticker", "held"} and r["held"] is True for r in rows), \
            f"規範 §B3：{label} 每列只含 ticker 與 held=True（bool）"
        assert res.kept_positions == len(rows) and res.in_u_positions == in_u, f"規範：{label} 計數"
        assert A.REASON_UNIVERSE_NOT_INDEPENDENT in res.reasons, f"規範 §B2-1：{label} 必須標示缺獨立母體"
        assert (A.REASON_IN_U_BLANK_KEPT in res.reasons) == (in_u > 0), f"規範 §C-8：{label} IN-U 標示"


def test_norm_list_branches_table():
    """§B3：ok＋乾淨（含保留空白值模式下的 IN-U 列）⇒ list：每列一筆 held=True、不去重、不丟 IN-U。"""
    _check_list_paths()


def test_norm_list_path_reasons_exact():
    assert _adapt(_list_inputs()["clean_default"][0]).reasons == (A.REASON_UNIVERSE_NOT_INDEPENDENT,)
    assert _adapt(_list_inputs()["in_u_blank_kept"][0]).reasons == (A.REASON_IN_U_BLANK_KEPT,
                                                                     A.REASON_UNIVERSE_NOT_INDEPENDENT)


def test_norm_both_semantic_branches_reachable():
    """counts_unknown 與 tally_inconsistent 兩分支都可達（形狀合法的快照，在 adapter 才回 None，不在建構期炸）。"""
    seen = {r for s, _ in _none_inputs().values() for r in _adapt(s).reasons}
    assert {A.REASON_COUNTS_UNKNOWN, A.REASON_TALLY_INCONSISTENT} <= seen


def test_norm_never_returns_empty_list_for_any_branch():
    for s, _ in _none_inputs().values():
        assert _adapt(s).holdings_rows != ()
    for s, _, _ in _list_inputs().values():
        assert _adapt(s).holdings_rows


def test_norm_input_type_no_duck_typing_backdoor():
    """只收 `HoldingsReadSnapshot` 本身：資料層 tally、具同名屬性的物件、子類別實例、dict 等一律 TypeError。"""
    snap = _ok()

    class _Sub(A.HoldingsReadSnapshot):
        pass
    bad = [_tally([_rec("0050")]), types.SimpleNamespace(**dataclasses.asdict(snap)), _Sub(**dataclasses.asdict(snap)),
           dataclasses.asdict(snap), None, (), "ok", 0]
    for b in bad:
        with pytest.raises(TypeError):
            A.adapt_holdings_read(b)


@pytest.mark.parametrize("kw, exc", [
    (dict(outcome="ok_but_not_really"), ValueError),
    (dict(outcome=None), ValueError),
    (dict(blank_values_retained=1), TypeError),
    (dict(source_row_count=-1), ValueError),
    (dict(dropped_non_numeric=True), ValueError),
    (dict(kept_non_finite_count=1.0), ValueError),
    (dict(kept_tickers=["0050"]), TypeError),
    (dict(kept_tickers=(" 0050",)), ValueError),
    (dict(kept_tickers=("",)), ValueError),
    (dict(kept_tickers=(50,)), ValueError),
])
def test_norm_snapshot_constructor_rejects_bad_shapes(kw, exc):
    base = dict(dataclasses.asdict(_ok()))
    base.update(kw)
    with pytest.raises(exc) as ei:
        A.HoldingsReadSnapshot(**base)
    assert not re.search(r"\d{3,}", str(ei.value)), "建構期錯誤訊息不得含資料值"


def test_norm_snapshot_non_ok_must_carry_no_counts():
    with pytest.raises(ValueError):
        A.HoldingsReadSnapshot(A.OUTCOME_NOT_SELECTED, False, source_row_count=0)
    with pytest.raises(ValueError):
        A.HoldingsReadSnapshot(A.OUTCOME_EXCEPTION_NETWORK, False, kept_tickers=())


def test_norm_exception_message_and_type_name_not_leaked():
    class SecretPortfolioError0050(RuntimeError):
        pass
    snap = snapshot_from_exception(SecretPortfolioError0050(_SECRET_MSG))
    res = A.adapt_holdings_read(snap)
    assert res.holdings_rows is None and res.reasons == (A.REASON_READ_EXCEPTION_OTHER,)
    assert "Secret" not in repr(snap) + "".join(res.reasons) and SHEET_ID not in repr(snap)


def test_norm_pure_and_output_rows_are_copies():
    s = _list_inputs()["in_u_blank_kept"][0]
    res = A.adapt_holdings_read(s)
    fresh = res.rows_for_digest()
    assert fresh == [dict(r) for r in res.holdings_rows] and fresh[0] is not res.holdings_rows[0]
    assert A.adapt_holdings_read(s) == res


def test_norm_result_type_rejects_unsafe_shapes():
    R, U = A.HoldingsAdapterResult, A.REASON_UNIVERSE_NOT_INDEPENDENT
    bad = [
        dict(holdings_rows=(), reasons=(U,), kept_positions=0, in_u_positions=0),
        dict(holdings_rows=None, reasons=()),
        dict(holdings_rows=None, reasons=(A.REASON_ZERO_ROWS,), kept_positions=0),
        dict(holdings_rows=({"ticker": "0050", "held": True, "lots": 1.0},), reasons=(U,), kept_positions=1,
             in_u_positions=0),
        dict(holdings_rows=({"ticker": "0050", "held": 1},), reasons=(U,), kept_positions=1, in_u_positions=0),
        dict(holdings_rows=({"ticker": "0050", "held": True},), reasons=(U,), kept_positions=2, in_u_positions=0),
        dict(holdings_rows=({"ticker": "0050", "held": True},), reasons=(), kept_positions=1, in_u_positions=0),
        dict(holdings_rows=None, reasons=("custom 0050",)),
        dict(holdings_rows=None, reasons=(A.REASON_ZERO_ROWS, A.REASON_NOT_SELECTED)),
    ]
    for kw in bad:
        with pytest.raises(ValueError):
            R(**kw)


def test_norm_repr_hides_tickers():
    s = _list_inputs()["clean_default"][0]
    assert not any(tk in repr(s) + repr(A.adapt_holdings_read(s)) for tk in SYNTH_TICKERS)


def test_norm_reason_codes_are_fixed_private_and_ordered():
    forbidden = (*SYNTH_TICKERS, PF_NAME, SHEET_ID, IDENTITY, "example", "@", "weird")
    for code in A.ALL_REASONS:
        assert re.fullmatch(r"[a-z_]+", code), code
    assert len(set(A.ALL_REASONS)) == len(A.ALL_REASONS)
    results = [_adapt(s) for s, _ in _none_inputs().values()] + [_adapt(s) for s, _, _ in _list_inputs().values()]
    for res in results:
        assert res.reasons == tuple(sorted(set(res.reasons), key=A.ALL_REASONS.index))
        for code in res.reasons:
            assert code in A.ALL_REASONS and not re.search(r"\d", code), code
            assert not any(f in code for f in forbidden), code


# ══════════════════════════════════════════════════════════════════════
# 快照欄位逐欄對照資料層原義＋漂移
# ══════════════════════════════════════════════════════════════════════
def test_norm_snapshot_fields_match_l1_meaning():
    recs = [_rec("0050"), _rec("0050", lots=2), _rec("0056", lots=NAN), _rec("7001", lots=""), _rec(""),
            _rec("9001", lots="x"), _rec("00878", avg=-INF), _rec("2330", lots=0)]
    for blank in (False, True):
        t = _tally(recs, blank=blank, other_name_rows=5, blank_rows=1)
        s = snapshot_from_tally(t)
        d = t.dropped
        assert s.blank_values_retained is t.keep_blank is blank
        assert s.kept_tickers == tuple(r["ticker"] for r in t.rows)
        assert s.source_row_count == t.raw == len(recs)            # 只計選定組合；不含其他組合／空白列
        for k in A.DROP_REASON_KEYS:
            assert getattr(s, A.DROP_REASON_FIELDS[k]) == d[k], k
        assert s.kept_blank_value_count == t.kept_with_missing_value == (1 if blank else 0)
        assert s.kept_non_finite_count == t.kept_non_finite == 1
        assert s.duplicate_ticker_count == len(t.duplicate_tickers) == 1
        assert (s.dropped_blank_value, s.dropped_non_finite) == ((0 if blank else 1), 1)


def test_drift_vocab_mirrors_l1_constants():
    assert A.DROP_REASON_KEYS == GSP.TALLY_DROP_REASONS                         # 含順序
    assert set(A.DROP_REASON_FIELDS) == set(GSP.TALLY_DROP_REASONS)
    assert A.OUTCOME_OK == GSP.READ_OK and A.OUTCOME_NOT_SELECTED == GSP.TALLY_NOT_SELECTED
    assert (A.OUTCOME_STATUS_WORKSHEET_MISSING, A.OUTCOME_STATUS_SCHEMA_MISMATCH, A.OUTCOME_STATUS_EMPTY) \
        == (GSP.READ_WORKSHEET_MISSING, GSP.READ_SCHEMA_MISMATCH, GSP.READ_EMPTY)
    for code, outcome in ERROR_TO_OUTCOME.items():
        assert outcome == f"exception_{code}", (code, outcome)
    l1_status = {v for k, v in vars(GSP).items() if k.startswith("READ_") and not k.startswith("READ_ERROR_")}
    l1_status.add(GSP.TALLY_NOT_SELECTED)
    assert l1_status == set(STATUS_TO_OUTCOME), "資料層新增／移除狀態常數 ⇒ 轉換器須明列"
    l1_errors = {v for k, v in vars(GSP).items() if k.startswith("READ_ERROR_") and k != "READ_ERROR_OTHER_PREFIX"}
    assert l1_errors <= set(ERROR_TO_OUTCOME), "資料層新增錯誤分類 ⇒ 轉換器須明列"
    assert set(STATUS_TO_OUTCOME.values()) | set(ERROR_TO_OUTCOME.values()) | {A.OUTCOME_EXCEPTION_OTHER} \
        == set(A.ALL_OUTCOMES)


def test_drift_unknown_status_collapses_to_other_and_unknown_drop_key_rejected():
    s = snapshot_from_tally(GSP.PortfolioReadTally("brand_new_status", False))
    assert s.outcome == A.OUTCOME_STATUS_OTHER and _adapt(s).reasons == (A.REASON_READ_STATUS_OTHER,)
    t = _tally([_rec("0050")])
    for pairs in ((*t.dropped_by_reason, ("brand_new_reason", 0)), t.dropped_by_reason[:-1]):
        with pytest.raises(ValueError, match="丟列鍵"):
            snapshot_from_tally(dataclasses.replace(t, dropped_by_reason=pairs))


# ══════════════════════════════════════════════════════════════════════
# 端到端：adapter → assemble_digest → build_rule_summary
# ══════════════════════════════════════════════════════════════════════
def _macro_state():
    disc = RiskCapDisclosure(snapshot_ts="2026-10-26 18:30:00", not_evaluated=(), disabled=(), sahm_status=None)
    return {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5,
            "exposure_limit_pct": 60, "defense": False, "risk_cap_disclosure": disc}


def _station_for(*tickers):
    return [{"代號": t, "held": True, "_action": "add", "建議動作": f"txt-add-{t}", "_detail": {}} for t in tickers]


def _assemble(holdings_rows, *, keyed=SYNTH_TICKERS, station=SYNTH_TICKERS):
    m = _macro_state()

    def ev(name):
        return EvidenceInput(stamp=SourceStamp(name, D), freshness=FreshnessStatus.FRESH)
    return assemble_digest(generated_at=NOW, macro_state=m, macro_evidence=ev("macro_state.json"),
                           allocation=build_allocation_decision(m), station_rows=_station_for(*station),
                           station_evidence=ev("dividend_station_service"), holdings_rows=holdings_rows,
                           holding_keys={t: HoldingKey(PID, t) for t in keyed})


def _sections(digest) -> dict:
    return dict(build_rule_summary(digest).lines)


def _digest_rows(res):
    return res.rows_for_digest() if isinstance(res, A.HoldingsAdapterResult) else (
        None if res.holdings_rows is None else list(res.holdings_rows))


def _check_e2e_none_paths() -> None:
    for label, (s, _) in _none_inputs().items():
        a = _assemble(_digest_rows(_adapt(s)))
        d, c = a.digest, a.coverage
        assert d.holdings.availability is Availability.UNAVAILABLE, f"規範 §B1：{label} holdings 必須 UNAVAILABLE"
        assert d.holdings.entries == () and d.actions.items == (), f"規範 §B1：{label} 不得有持股 entry／行動"
        assert c.unkeyed_held_count is None, f"規範 §B1：{label} unkeyed_held_count 必須 None（未知不是 0）"
        assert c.is_complete is False, f"規範 §B1：{label} is_complete 必須 False"
        secs = _sections(d)
        text = "\n".join(x for ls in secs.values() for x in ls)
        for w in ZERO_HOLDING_CLAIMS:
            assert w not in text, f"規範 §B1：{label} 摘要不得宣稱零持股：{w!r}"
        for sec in HOLDINGS_RELATED_SECTIONS:
            assert not any(w in ln for ln in secs.get(sec, ()) for w in NEUTRAL_SAFE_CLAIMS), \
                f"規範 §B1：{label} {sec} 段把未知說成中性／安全"
            assert secs[sec] and all("無法判定" in ln for ln in secs[sec]), f"規範 §B1：{label} {sec} 段須只說無法判定"


def test_norm_e2e_none_paths_unknown_everywhere():
    """§B1 端到端：每個 None 分支（含 zero_rows）餵入 Digest ⇒ UNAVAILABLE、coverage 未知、is_complete False、
    無零持股字樣、持股與行動段只說「無法判定」、不以中性／安全描述。"""
    _check_e2e_none_paths()


def _check_e2e_list_positions_retained() -> None:
    for label, (s, tickers, _) in _list_inputs().items():
        keyed = tickers[:1]                                         # 只有第一檔有鍵；其餘（含 IN-U）為「已知但未評估」
        a = _assemble(_digest_rows(_adapt(s)), keyed=keyed, station=keyed)
        d, c = a.digest, a.coverage
        n_entries = len(d.holdings.entries)
        assert n_entries + d.holdings.unkeyed_count == len(tickers), \
            f"規範 §B2：{label} 部位不得遺失（entries {n_entries} + unkeyed {d.holdings.unkeyed_count} ≠ {len(tickers)}）"
        assert [e.key.symbol for e in d.holdings.entries] == keyed
        assert c.unkeyed_held_count == len(tickers) - 1, f"規範 §B2：{label} 無鍵部位須計入 coverage"
        if len(tickers) > 1:
            assert c.is_complete is False, f"規範 §B2：{label} 有無法評估部位時 is_complete 必須 False"
            assert d.holdings.availability is Availability.PARTIAL
            assert any("缺少投資組合鍵" in x for x in _sections(d)["buy_and_hold"]), f"規範 §B2：{label} 須揭露無鍵部位"
        text = "\n".join(x for ls in _sections(d).values() for x in ls)
        assert not any(w in text for w in ZERO_HOLDING_CLAIMS), f"規範：{label} 有部位時不得宣稱零持股"


def test_norm_e2e_list_paths_positions_retained():
    """§B2／§B3 端到端：有鍵部位成為 entries、無鍵部位（含 IN-U 空白列）以 unkeyed 計數保留，不被丟。"""
    _check_e2e_list_positions_retained()


def test_current_behavior_e2e_list_all_keyed_is_complete_true():
    """**current_behavior，非規範**：list 路徑上四段齊備、每列有鍵、站內每檔都有對應時，`is_complete` 現況為 True。
    依契約 §B2-1／§C-6 這**不應**被讀成「已證明完整」——缺獨立應有母體；該缺口由 #1254 的 strict xfail
    `test_gap_contract_fed_input_without_independent_universe_must_be_incomplete` 釘住（仍 xfail）。adapter 只能以
    `universe_not_independent` 標示。轉紅（變 False）⇒ coverage 已補母體檢查：連同 #1254 的 xfail 一起升級。"""
    s, tickers, _ = _list_inputs()["clean_default"]
    res = _adapt(s)
    a = _assemble(res.rows_for_digest(), keyed=tickers, station=tickers)
    assert a.coverage.is_complete is True
    assert A.REASON_UNIVERSE_NOT_INDEPENDENT in res.reasons


# ══════════════════════════════════════════════════════════════════════
# 突變（替換 adapter 公開函式、內部 helper 或快照建構期；monkeypatch 自動還原）
# ══════════════════════════════════════════════════════════════════════
_ORIG = A.adapt_holdings_read


def _ns(rows, reasons=(), kept=None, in_u=0):
    return types.SimpleNamespace(holdings_rows=rows, reasons=tuple(reasons), kept_positions=kept, in_u_positions=in_u)


def test_mutation_baselines_are_green():
    _check_none_paths()
    _check_list_paths()
    _check_e2e_none_paths()
    _check_e2e_list_positions_retained()


def test_mutation_unknown_becomes_empty_list_turns_norm_red(monkeypatch):
    """M1：未知 ⇒ `[]`。"""
    def _mut(s):
        r = _ORIG(s)
        return _ns((), r.reasons, 0) if r.holdings_rows is None else r
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_e2e_none_paths()


def test_mutation_swallowed_exception_returns_list_turns_norm_red(monkeypatch):
    """M2：讀取例外被吞、以上次乾淨結果冒充 list。"""
    stale = _ORIG(_ok())

    def _mut(s):
        if s.outcome.startswith("exception_"):
            return _ns(stale.holdings_rows, (), stale.kept_positions)
        return _ORIG(s)
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


def test_mutation_in_u_rows_dropped_turns_norm_red(monkeypatch):
    """M3：丟掉 IN-U（張數／均價空白）列。"""
    def _mut(s):
        r = _ORIG(s)
        if r.holdings_rows is None:
            return r
        keep = tuple(x for x in r.holdings_rows if x["ticker"] not in IN_U_TICKERS)
        return _ns(keep, r.reasons, len(keep), 0)
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B3"):
        _check_list_paths()
    with pytest.raises(AssertionError, match="規範 §B2"):
        _check_e2e_list_positions_retained()


def test_mutation_in_u_rows_dropped_inside_helper_fails_loud(monkeypatch):
    """M3b：在內部 `_rows_for_digest` 丟 IN-U 列 ⇒ 結果型別列數不變量 ValueError。"""
    monkeypatch.setattr(A, "_rows_for_digest",
                        lambda tks: tuple({"ticker": t, "held": True} for t in tks if t not in IN_U_TICKERS))
    with pytest.raises(ValueError, match="kept_positions"):
        _check_list_paths()


def test_mutation_ex_evidence_still_returns_list_turns_norm_red(monkeypatch):
    """M4：EX 證據時仍回 list。"""
    monkeypatch.setattr(A, "_ex_evidence_reasons", lambda s: ())
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


def test_mutation_in_u_dropped_default_mode_still_returns_list_turns_norm_red(monkeypatch):
    """M4b：未保留模式已丟 IN-U 列時仍回 list。"""
    monkeypatch.setattr(A, "_in_u_dropped_reasons", lambda s: ())
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


def test_mutation_duplicates_silently_deduped_turns_norm_red(monkeypatch):
    """M5：重複代號被默默去重後回 list。"""
    def _mut(s):
        r = _ORIG(s)
        if r.reasons != (A.REASON_DUPLICATE_TICKERS,):
            return r
        rows = tuple({"ticker": t, "held": True} for t in dict.fromkeys(s.kept_tickers))
        return _ns(rows, (A.REASON_UNIVERSE_NOT_INDEPENDENT,), len(rows), 0)
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


def test_mutation_zero_rows_becomes_empty_list_turns_norm_red(monkeypatch):
    """M6：零列（§C-1 待決）直接當已知空 `[]`。"""
    def _mut(s):
        r = _ORIG(s)
        return _ns((), (), 0) if r.reasons == (A.REASON_ZERO_ROWS,) else r
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


def test_mutation_consistency_check_removed_turns_norm_red(monkeypatch):
    """M7：移除跨欄自洽檢查（`tally_inconsistent` 分支消失）。"""
    monkeypatch.setattr(A, "_is_consistent", lambda s: True)
    with pytest.raises(AssertionError, match="規範"):
        _check_none_paths()


def test_mutation_unknown_check_removed_turns_norm_red(monkeypatch):
    """M8：移除計數未知檢查（`counts_unknown` 分支消失 ⇒ None 計數流入自洽檢查而炸）。"""
    monkeypatch.setattr(A, "_has_unknown", lambda s: False)
    with pytest.raises((AssertionError, TypeError)):
        _check_none_paths()


def test_mutation_duplicate_bound_removed_turns_norm_red(monkeypatch):
    """M11：移除「2 × 重複代號數 ≤ 代號非空來源列數」界限 ⇒ 兩個 inconsistent_dup_* 案例改走 duplicate_tickers ⇒ 轉紅。"""
    monkeypatch.setattr(A, "_duplicate_bound_ok", lambda s: True)
    with pytest.raises(AssertionError, match="inconsistent_dup_"):
        _check_none_paths()


def test_mutation_duplicate_bound_loosened_turns_norm_red(monkeypatch):
    """M12：界限放寬回「≤ 來源列數」（不扣代號空白列）⇒ 收緊專屬案例轉紅。"""
    monkeypatch.setattr(A, "_duplicate_bound_ok", lambda s: s.duplicate_ticker_count * 2 <= s.source_row_count)
    with pytest.raises(AssertionError, match="inconsistent_dup_exceeds_nonblank_ticker_rows"):
        _check_none_paths()


def test_norm_mixed_codes_kept_verbatim():
    """list 路徑：4 碼股與 5／6 碼 ETF 混合，代號原樣（前導零保留）、順序不變、列數不變。"""
    s, tickers, _ = _list_inputs()["mixed_stock_and_etf_codes"]
    res = _adapt(s)
    assert [r["ticker"] for r in res.holdings_rows] == tickers == list(s.kept_tickers)
    assert all(type(r["ticker"]) is str for r in res.holdings_rows) and res.kept_positions == 5


@pytest.mark.parametrize("semantic", ["_is_consistent", "_has_unknown"])
def test_mutation_semantic_check_moved_into_constructor_turns_norm_red(monkeypatch, semantic):
    """M9／M10：把語意檢查搬進快照建構期（形狀合法但語意不足的快照改成 raise）⇒ 規範的
    「回 None＋counts_unknown／tally_inconsistent」不再可達，規範測試轉紅。"""
    orig_post = A.HoldingsReadSnapshot.__post_init__

    def _post(self):
        orig_post(self)
        if self.outcome != A.OUTCOME_OK:
            return
        unknown = A._has_unknown(self)
        if (semantic == "_has_unknown" and unknown) or (semantic == "_is_consistent" and not unknown
                                                         and not A._is_consistent(self)):
            raise ValueError("語意檢查被搬進建構期（突變）")
    monkeypatch.setattr(A.HoldingsReadSnapshot, "__post_init__", _post)
    with pytest.raises(ValueError, match="突變"):
        _check_none_paths()
    with pytest.raises(ValueError, match="突變"):
        test_norm_both_semantic_branches_reachable()


# ══════════════════════════════════════════════════════════════════════
# 守衛
# ══════════════════════════════════════════════════════════════════════
_SKIP_DIRS = {"tests", ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "data_cache"}
_PUBLIC_NAMES = {"onebrain_holdings_adapter", "adapt_holdings_read", "HoldingsAdapterResult", "HoldingsReadSnapshot"}
_L1_NAMES = ("PortfolioReadTally", "tally_portfolio_records", "load_portfolio_tallied", "_load_portfolio_tallied",
             "classify_read_error", "gsheet_portfolio")


def _non_test_py_files() -> list:
    out = []
    for p in REPO.rglob("*.py"):
        rel = p.relative_to(REPO)
        if rel.parts[0] in _SKIP_DIRS or any(part in _SKIP_DIRS for part in rel.parts[:-1]):
            continue
        out.append(p)
    return out


def test_guard_zero_production_caller():
    """repo 內所有非 tests/ 的 .py（含 app*.py、src、shared、scripts、tools、infra、mcp_server）不得 import／引用本模組
    或其公開符號（含 `HoldingsReadSnapshot`；adapter 自身除外）。⚠️ 防不了動態拼接字串的 import。"""
    paths = _non_test_py_files()
    assert {"src", "shared", "scripts", "app.py"} <= {p.relative_to(REPO).parts[0] for p in paths}
    hits = []
    for p in paths:
        if p.resolve() == ADAPTER_FILE.resolve():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        rel = str(p.relative_to(REPO))
        if any(n in text for n in _PUBLIC_NAMES):
            hits.append(f"{rel}: 字串命中")
        for n in ast.walk(ast.parse(text)):
            if isinstance(n, ast.Import):
                hits += [f"{rel}: import {a.name}" for a in n.names if "onebrain_holdings_adapter" in a.name]
            elif isinstance(n, ast.ImportFrom):
                if n.module and "onebrain_holdings_adapter" in n.module:
                    hits.append(f"{rel}: from {n.module}")
                hits += [f"{rel}: import 名 {a.name}" for a in n.names if a.name in _PUBLIC_NAMES]
    assert hits == []


def test_guard_adapter_stdlib_only_no_l1_names_no_dynamic_import():
    text = ADAPTER_FILE.read_text(encoding="utf-8")
    for name in (*_L1_NAMES, "importlib", "__import__", "getattr(", "keep_blank"):
        assert name not in text, f"adapter 不得出現：{name}"
    tree = ast.parse(text)
    allowed = {"__future__", "collections", "dataclasses", "typing"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert {a.name.split(".")[0] for a in n.names} <= allowed, ast.dump(n)
        elif isinstance(n, ast.ImportFrom):
            assert n.level == 0 and (n.module or "").split(".")[0] in allowed, ast.dump(n)
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                assert f.id not in {"open", "exec", "eval", "compile", "getattr", "setattr", "__import__", "vars"}, f.id
            if isinstance(f, ast.Attribute):
                assert f.attr not in {"now", "today", "utcnow", "time", "perf_counter", "monotonic"}, f.attr
        elif isinstance(n, ast.keyword):
            assert n.arg != "keep_blank"


def test_guard_adapter_imports_nothing_beyond_stdlib_at_runtime():
    """以獨立直譯器（-I，不經 `src` 套件）載入 adapter 檔：載入後 sys.modules 不得出現 src／shared／streamlit。"""
    code = ("import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('obh_adapter', {str(ADAPTER_FILE)!r})\n"
            "m = importlib.util.module_from_spec(spec); sys.modules['obh_adapter'] = m; spec.loader.exec_module(m)\n"
            "bad = sorted(k for k in sys.modules if k.split('.')[0] in ('src', 'shared', 'streamlit', 'gspread',"
            " 'requests', 'socket'))\n"
            "print(','.join(bad))\n")
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=60, check=True)
    loaded = out.stdout.strip()
    assert loaded == "", f"adapter 載入了非標準庫模組或 socket：{loaded}"


def test_guard_this_file_offline_and_clockless_by_ast():
    tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    banned = {"streamlit", "requests", "urllib", "httpx", "gspread", "anthropic", "openai", "google"}
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            assert n.func.attr not in ("now", "today", "utcnow", "load_portfolio_tallied", "load_portfolio")
    assert not (mods & banned), mods & banned
