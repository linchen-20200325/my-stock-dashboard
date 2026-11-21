"""C-OB-HOLDINGS-ADAPTER-DORMANT-1 — `src/services/onebrain_holdings_adapter.py`（dormant L3 純轉換）的合成驗收。

授權：Issue #1199 comment 7062910532。契約：`docs/vnext/ONEBRAIN_HOLDINGS_INPUT_CONTRACT_2026-11-21.md`（§A／§B／§C）。
- L1 tally 一律以純函式 `tally_portfolio_records` 由合成 records 產生（或直接建構 `PortfolioReadTally` 表示非 ok 狀態）；
  讀取失敗以合成例外物件表示。⛔ 不讀 Sheet、不呼叫 `load_portfolio_tallied`、不連網（socket 守衛）、不呼叫時鐘。
- 測試分類：規範＝`test_norm_*`；現況快照＝名稱含 `current_behavior`（非規範）；突變＝`test_mutation_*`；守衛＝`test_guard_*`。
⚠️ 作者自測；未經獨立 QA。Digest NOT READY。
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
import socket
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
SYNTH_TICKERS = ("0050", "0056", "2330", "9001", "9002", "00878")

# 最小常數（概念同 #1254 契約測試；刻意複製，⛔ 不 import 該檔私有物件）
ZERO_HOLDING_CLAIMS = ("0 檔", "0檔", "零檔", "無持股", "沒有持股", "空倉", "持股為零", "零持股", "持股 0")
NEUTRAL_SAFE_CLAIMS = ("中性", "正常", "安全", "SAFE", "safe", "neutral")
HOLDINGS_RELATED_SECTIONS = ("buy_and_hold", "capital_gain", "actions")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("測試不得連網")
    monkeypatch.setattr(socket.socket, "connect", _boom)


# ── 合成輸入 ───────────────────────────────────────────────────────────
def _rec(ticker, lots=1, avg=10.0):
    return {"name": PF_NAME, "ticker": ticker, "lots": lots, "avg_price": avg, "updated_at": "t"}


def _tally(recs, *, blank=False, **parts):
    # 以 dict 展開傳參：本檔不寫 `keep_blank=` 關鍵字字面（與 b10 守衛的精神一致；tests/ 本不在其掃描範圍）
    return GSP.tally_portfolio_records(recs, **{"keep_blank": blank}, **parts)


def _unknown(status, *, blank=False):
    return GSP.PortfolioReadTally(status, blank)


def _adapt(x):
    return A.adapt_holdings_read(x)          # 經模組屬性呼叫 ⇒ 突變測試可替換


# 例外 → 預期原因碼（訊息刻意塞入代號／sheet_id／身分／數字，驗證不外流）
_SECRET_MSG = f"{SYNTH_TICKERS[0]} {SHEET_ID} {IDENTITY} {PF_NAME} 403"
EXCEPTION_CASES = {
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
STATUS_CASES = {
    "not_selected": (_unknown(GSP.TALLY_NOT_SELECTED), A.REASON_NOT_SELECTED),
    "worksheet_missing": (_unknown(GSP.READ_WORKSHEET_MISSING), A.REASON_READ_STATUS_WORKSHEET_MISSING),
    "schema_mismatch": (_unknown(GSP.READ_SCHEMA_MISMATCH, blank=True), A.REASON_READ_STATUS_SCHEMA_MISMATCH),
    "empty": (_unknown(GSP.READ_EMPTY), A.REASON_READ_STATUS_EMPTY),
    "unknown_status": (_unknown(f"weird_{SHEET_ID}_7"), A.REASON_READ_STATUS_OTHER),
}
_CLEAN = _tally([_rec("0050"), _rec("0056")])
UNKNOWN_COUNT_CASES = {
    "ok_all_counts_none": (GSP.PortfolioReadTally(GSP.READ_OK, False), A.REASON_COUNTS_UNKNOWN),
    "ok_kept_none": (dataclasses.replace(_CLEAN, kept=None), A.REASON_COUNTS_UNKNOWN),
    "ok_rows_none": (dataclasses.replace(_CLEAN, rows=None), A.REASON_COUNTS_UNKNOWN),
    "ok_dup_tickers_none": (dataclasses.replace(_CLEAN, duplicate_tickers=None), A.REASON_COUNTS_UNKNOWN),
    "inconsistent_kept": (dataclasses.replace(_CLEAN, kept=5), A.REASON_TALLY_INCONSISTENT),
    "inconsistent_row_ticker": (dataclasses.replace(_CLEAN, rows=({"ticker": 50}, {"ticker": "0056"})),
                                A.REASON_TALLY_INCONSISTENT),
    "inconsistent_bool_count": (dataclasses.replace(_CLEAN, blank_rows=True), A.REASON_TALLY_INCONSISTENT),
}
ZERO_ROW_CASES = {
    "empty_records": (_tally([]), A.REASON_ZERO_ROWS),
    "absent_name": (_tally([], other_name_rows=3), A.REASON_ZERO_ROWS),
    "absent_name_keep_blank": (_tally([], blank=True, other_name_rows=1, blank_rows=2), A.REASON_ZERO_ROWS),
}
#: EX／IN-U 丟失證據 ⇒ None，原因碼集合
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
    "blank_dropped_default": ([_rec("0050"), _rec("0056", lots="")], False, {A.REASON_IN_U_BLANK_DROPPED}),
    "all_dropped": ([_rec("", lots=1), _rec("0050", lots=0)], False,
                    {A.REASON_EX_DROPPED_BLANK_TICKER, A.REASON_EX_DROPPED_NON_POSITIVE}),
    "combo": ([_rec("0050"), _rec("0050"), _rec("0056", lots=NAN), _rec("00878", lots=""), _rec("9001", lots="x")],
              False, {A.REASON_DUPLICATE_TICKERS, A.REASON_NON_FINITE_KEPT, A.REASON_IN_U_BLANK_DROPPED,
                      A.REASON_EX_DROPPED_NON_NUMERIC}),
}
#: 乾淨 ⇒ list（records, keep_blank, 預期代號序列, 預期 IN-U 數）
LIST_CASES = {
    "clean_default": ([_rec("0050"), _rec("0056"), _rec("9001")], False, ["0050", "0056", "9001"], 0),
    "clean_keep_blank": ([_rec("0050"), _rec("0056")], True, ["0050", "0056"], 0),
    "in_u_blank_kept": ([_rec("0050"), _rec("0056", lots=""), _rec("9001", avg="  ")], True,
                        ["0050", "0056", "9001"], 2),
    "all_in_u": ([_rec("0050", lots=""), _rec("0056", avg="")], True, ["0050", "0056"], 2),
    "with_other_partitions": ([_rec("00878")], False, ["00878"], 0),
}


def _none_inputs():
    """所有應得 None 的輸入：{label: (input, 預期原因碼集合)}。"""
    out = {k: (x, {r}) for k, (x, r) in {**EXCEPTION_CASES, **STATUS_CASES, **UNKNOWN_COUNT_CASES,
                                         **ZERO_ROW_CASES}.items()}
    out.update({k: (_tally(recs, blank=b), rs) for k, (recs, b, rs) in DEGRADE_CASES.items()})
    return out


def _list_inputs():
    parts = {"with_other_partitions": dict(other_name_rows=4, blank_rows=1, blank_name_rows=2)}
    return {k: (_tally(recs, blank=b, **parts.get(k, {})), tks, inu) for k, (recs, b, tks, inu) in LIST_CASES.items()}


# ══════════════════════════════════════════════════════════════════════
# 規範：分支表
# ══════════════════════════════════════════════════════════════════════
def _check_none_paths() -> None:
    for label, (x, expected) in _none_inputs().items():
        res = _adapt(x)
        assert res.holdings_rows is None, f"規範 §B1：{label} 必須回 None（未知不得映成 [] 或 list），得到 {res.holdings_rows!r}"
        assert set(res.reasons) == expected, f"規範：{label} 原因碼 {res.reasons} ≠ {sorted(expected)}"
        assert res.reasons, f"規範：{label} None 時原因碼不得為空"
        assert res.kept_positions is None and res.in_u_positions is None, f"規範 §B1：{label} 計數必須 None（未知不是 0）"


def test_norm_none_branches_table():
    """§B1／§B3：例外、非 ok 狀態、計數未知／矛盾、零列、EX 證據、預設模式丟 IN-U ⇒ None＋固定原因碼。"""
    _check_none_paths()


def _check_list_paths() -> None:
    for label, (t, tickers, in_u) in _list_inputs().items():
        res = _adapt(t)
        assert res.holdings_rows is not None, f"規範：{label} 乾淨來源必須回 list，得到 None（{res.reasons}）"
        rows = list(res.holdings_rows)
        assert len(rows) == t.kept, f"規範 §B3：{label} 輸出列數必須＝L1 kept（不得遺失／灌水）"
        assert [r["ticker"] for r in rows] == tickers, f"規範 §B3：{label} 每列一筆、順序不變、不丟 IN-U：{rows}"
        assert all(r == {"ticker": r["ticker"], "held": True} and r["held"] is True for r in rows), \
            f"規範 §B3：{label} 每列只含 ticker 與 held=True（bool）"
        assert res.kept_positions == len(rows) and res.in_u_positions == in_u, f"規範：{label} 計數"
        assert A.REASON_UNIVERSE_NOT_INDEPENDENT in res.reasons, f"規範 §B2-1：{label} 必須標示缺獨立母體"
        assert (A.REASON_IN_U_BLANK_KEPT in res.reasons) == (in_u > 0), f"規範 §C-8：{label} IN-U 標示"


def test_norm_list_branches_table():
    """§B3：ok＋乾淨（含 keep_blank 模式下張數／均價空白的 IN-U 列）⇒ list：每列一筆 held=True、不去重、不丟 IN-U。"""
    _check_list_paths()


def test_norm_list_path_reasons_exact():
    res = _adapt(_list_inputs()["clean_default"][0])
    assert res.reasons == (A.REASON_UNIVERSE_NOT_INDEPENDENT,)
    res = _adapt(_list_inputs()["in_u_blank_kept"][0])
    assert res.reasons == (A.REASON_IN_U_BLANK_KEPT, A.REASON_UNIVERSE_NOT_INDEPENDENT)


def test_norm_never_returns_empty_list_for_any_branch():
    for x, _ in _none_inputs().values():
        assert _adapt(x).holdings_rows != ()
    for t, _, _ in _list_inputs().values():
        assert _adapt(t).holdings_rows


@pytest.mark.parametrize("bad", [None, {}, [], (), "ok", 0, types.SimpleNamespace(**dataclasses.asdict(_CLEAN))])
def test_norm_non_tally_input_type_error(bad):
    """Fail Loud：不是 PortfolioReadTally、也不是例外物件 ⇒ TypeError（不得猜）。"""
    with pytest.raises(TypeError):
        A.adapt_holdings_read(bad)


def test_norm_exception_not_reraised_and_type_name_not_leaked():
    class SecretPortfolioError0050(RuntimeError):
        pass
    res = A.adapt_holdings_read(SecretPortfolioError0050(_SECRET_MSG))
    assert res.holdings_rows is None and res.reasons == (A.REASON_READ_EXCEPTION_OTHER,)
    assert "Secret" not in "".join(res.reasons)


def test_norm_input_not_mutated_and_output_rows_are_copies():
    t = _tally([_rec("0050"), _rec("0056", lots="")], blank=True)
    before = [dict(r) for r in t.rows]
    res = A.adapt_holdings_read(t)
    assert [dict(r) for r in t.rows] == before
    assert all(o is not i for o, i in zip(res.holdings_rows, t.rows))
    fresh = res.rows_for_digest()
    assert fresh == [dict(r) for r in res.holdings_rows] and fresh[0] is not res.holdings_rows[0]
    assert A.adapt_holdings_read(t) == res                         # 純函式：同輸入同輸出


def test_norm_result_type_rejects_unsafe_shapes():
    """結果型別本身拒收「空清單」「None 無原因」「列帶私人欄位」「列數與計數不符」「非固定原因碼」。"""
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
        dict(holdings_rows=None, reasons=(A.REASON_ZERO_ROWS, A.REASON_NOT_SELECTED)),   # 未依固定順序
    ]
    for kw in bad:
        with pytest.raises(ValueError):
            R(**kw)


def test_norm_repr_hides_rows():
    res = A.adapt_holdings_read(_list_inputs()["clean_default"][0])
    assert not any(tk in repr(res) for tk in SYNTH_TICKERS)


# ══════════════════════════════════════════════════════════════════════
# 規範：原因碼隱私與穩定排序
# ══════════════════════════════════════════════════════════════════════
def test_norm_reason_codes_are_fixed_private_and_ordered():
    forbidden = (*SYNTH_TICKERS, PF_NAME, SHEET_ID, IDENTITY, "example", "@")
    for code in A.ALL_REASONS:
        assert re.fullmatch(r"[a-z_]+", code), code
    assert len(set(A.ALL_REASONS)) == len(A.ALL_REASONS)
    results = [_adapt(x) for x, _ in _none_inputs().values()] + [_adapt(t) for t, _, _ in _list_inputs().values()]
    for res in results:
        assert res.reasons == tuple(sorted(set(res.reasons), key=A.ALL_REASONS.index))
        for code in res.reasons:
            assert code in A.ALL_REASONS
            assert not re.search(r"\d", code), code
            assert not any(f in code for f in forbidden), code


# ══════════════════════════════════════════════════════════════════════
# 端到端：adapter → assemble_digest → build_rule_summary
# ══════════════════════════════════════════════════════════════════════
def _macro_state():
    disc = RiskCapDisclosure(snapshot_ts="2026-10-26 18:30:00", not_evaluated=(), disabled=(), sahm_status=None)
    return {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5,
            "exposure_limit_pct": 60, "defense": False, "risk_cap_disclosure": disc}


def _station_for(*tickers):
    return [{"代號": t, "held": True, "_action": "add", "建議動作": f"txt-add-{t}", "_detail": {}} for t in tickers]


def _keys_for(*tickers):
    return {t: HoldingKey(PID, t) for t in tickers}


def _assemble(holdings_rows, *, keyed=SYNTH_TICKERS, station=SYNTH_TICKERS):
    m = _macro_state()
    ev = lambda name: EvidenceInput(stamp=SourceStamp(name, D), freshness=FreshnessStatus.FRESH)  # noqa: E731
    return assemble_digest(generated_at=NOW, macro_state=m, macro_evidence=ev("macro_state.json"),
                           allocation=build_allocation_decision(m), station_rows=_station_for(*station),
                           station_evidence=ev("dividend_station_service"), holdings_rows=holdings_rows,
                           holding_keys=_keys_for(*keyed))


def _sections(digest) -> dict:
    return dict(build_rule_summary(digest).lines)


def _check_e2e_none_paths() -> None:
    for label, (x, _) in _none_inputs().items():
        res = _adapt(x)
        a = _assemble(res.rows_for_digest() if hasattr(res, "rows_for_digest") else res.holdings_rows)
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
            for line in secs.get(sec, ()):
                assert not any(w in line for w in NEUTRAL_SAFE_CLAIMS), f"規範 §B1：{label} {sec} 段把未知說成中性／安全"
            assert secs[sec] and all("無法判定" in ln for ln in secs[sec]), f"規範 §B1：{label} {sec} 段須只說無法判定"


def test_norm_e2e_none_paths_unknown_everywhere():
    """§B1 端到端：每個 None 分支餵入 Digest（macro／站內證據齊備、站內有行動）⇒ UNAVAILABLE、coverage 未知、
    is_complete False、無零持股字樣、持股與行動段只說「無法判定」、不以中性／安全描述。"""
    _check_e2e_none_paths()


def _check_e2e_list_positions_retained() -> None:
    for label, (t, tickers, _) in _list_inputs().items():
        res = _adapt(t)
        keyed = tickers[:1]                                         # 只有第一檔有鍵，其餘為「已知但未評估」
        a = _assemble(list(res.holdings_rows), keyed=keyed, station=keyed)
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
    """§B2／§B3 端到端：list 路徑上，有鍵部位成為 entries、無鍵部位（含 IN-U）以 unkeyed 計數保留，不被丟。"""
    _check_e2e_list_positions_retained()


def test_current_behavior_e2e_list_all_keyed_is_complete_true():
    """**current_behavior，非規範**：list 路徑上四段齊備、每列有鍵有行動時，`is_complete` 現況為 True。
    依契約 §B2-1／§C-6 這**不應**被讀成「已證明完整」——缺獨立應有母體；該缺口由 #1254 的 strict xfail
    `test_gap_contract_fed_input_without_independent_universe_must_be_incomplete` 釘住（仍 xfail）。adapter 只能在自己的
    結果上以 `universe_not_independent` 標示。轉紅（變 False）⇒ 代表 coverage 已補上母體檢查：連同 #1254 的 xfail 一起升級。"""
    t, tickers, _ = _list_inputs()["clean_default"]
    res = _adapt(t)
    a = _assemble(list(res.holdings_rows), keyed=tickers, station=tickers)
    assert a.coverage.is_complete is True
    assert A.REASON_UNIVERSE_NOT_INDEPENDENT in res.reasons


# ══════════════════════════════════════════════════════════════════════
# 突變（替換 adapter 公開函式或內部 helper；monkeypatch 自動還原）
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
    """突變 1：未知 ⇒ `[]`（把不知道說成已知沒有）。"""
    def _mut(x):
        r = _ORIG(x)
        return _ns((), r.reasons, 0) if r.holdings_rows is None else r
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_e2e_none_paths()


def test_mutation_swallowed_exception_returns_list_turns_norm_red(monkeypatch):
    """突變 2：吞掉讀取例外、回一個 list（以上次乾淨結果冒充）。"""
    stale = _ORIG(_CLEAN)

    def _mut(x):
        return _ns(stale.holdings_rows, (), stale.kept_positions) if isinstance(x, BaseException) else _ORIG(x)
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


def test_mutation_in_u_rows_dropped_turns_norm_red(monkeypatch):
    """突變 3：丟掉張數／均價空白的 IN-U 列。"""
    def _mut(x):
        r = _ORIG(x)
        if r.holdings_rows is None or not x.kept_with_missing_value:
            return r
        keep = [{"ticker": s["ticker"], "held": True} for s in x.rows
                if s.get("lots") is not None and s.get("avg_price") is not None]
        return _ns(tuple(keep), r.reasons, len(keep), 0)
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B3"):
        _check_list_paths()
    with pytest.raises(AssertionError, match="規範 §B2"):
        _check_e2e_list_positions_retained()


def test_mutation_in_u_rows_dropped_inside_helper_fails_loud(monkeypatch):
    """突變 3b：在內部 `_rows_for_digest` 丟 IN-U 列 ⇒ 結果型別的列數不變量直接 ValueError（規範測試轉紅）。"""
    monkeypatch.setattr(A, "_rows_for_digest", lambda rows: tuple(
        {"ticker": r["ticker"], "held": True} for r in rows if r.get("lots") is not None))
    with pytest.raises(ValueError, match="kept_positions"):
        _check_list_paths()


def test_mutation_ex_evidence_still_returns_list_turns_norm_red(monkeypatch):
    """突變 4：EX 證據（丟列／NaN／+inf）時仍回 list。"""
    monkeypatch.setattr(A, "_ex_evidence_reasons", lambda t: ())
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


def test_mutation_in_u_dropped_default_mode_still_returns_list_turns_norm_red(monkeypatch):
    """突變 4b：預設模式已丟 IN-U 列時仍回 list。"""
    monkeypatch.setattr(A, "_in_u_dropped_reasons", lambda t: ())
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


def test_mutation_duplicates_silently_deduped_turns_norm_red(monkeypatch):
    """突變 5：重複代號被默默去重後回 list。"""
    def _mut(x):
        r = _ORIG(x)
        if isinstance(x, BaseException) or r.reasons != (A.REASON_DUPLICATE_TICKERS,):
            return r
        seen, rows = set(), []
        for s in x.rows:
            if s["ticker"] not in seen:
                seen.add(s["ticker"])
                rows.append({"ticker": s["ticker"], "held": True})
        return _ns(tuple(rows), (A.REASON_UNIVERSE_NOT_INDEPENDENT,), len(rows), 0)
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


def test_mutation_zero_rows_becomes_empty_list_turns_norm_red(monkeypatch):
    """突變 6：零列（§C-1 待決）直接當已知空 `[]`。"""
    def _mut(x):
        r = _ORIG(x)
        return _ns((), (), 0) if r.reasons == (A.REASON_ZERO_ROWS,) else r
    monkeypatch.setattr(A, "adapt_holdings_read", _mut)
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_paths()


# ══════════════════════════════════════════════════════════════════════
# 守衛
# ══════════════════════════════════════════════════════════════════════
_SKIP_DIRS = {"tests", ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "data_cache"}


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
    或其公開符號（adapter 自身除外）。⚠️ 防不了動態拼接字串的 import；只擋直接引用與字串命中。"""
    names = {"onebrain_holdings_adapter", "adapt_holdings_read", "HoldingsAdapterResult"}
    paths = _non_test_py_files()
    rel_tops = {p.relative_to(REPO).parts[0] for p in paths}
    assert {"src", "shared", "scripts", "app.py"} <= rel_tops
    hits = []
    for p in paths:
        if p.resolve() == ADAPTER_FILE.resolve():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        rel = str(p.relative_to(REPO))
        if any(n in text for n in names):
            hits.append(f"{rel}: 字串命中")
        tree = ast.parse(text)
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                hits += [f"{rel}: import {a.name}" for a in n.names if "onebrain_holdings_adapter" in a.name]
            elif isinstance(n, ast.ImportFrom):
                if n.module and "onebrain_holdings_adapter" in n.module:
                    hits.append(f"{rel}: from {n.module}")
                hits += [f"{rel}: import 名 {a.name}" for a in n.names if a.name in names]
    assert hits == []


def test_guard_adapter_is_pure_by_ast():
    tree = ast.parse(ADAPTER_FILE.read_text(encoding="utf-8"))
    allowed_roots = {"__future__", "collections", "dataclasses", "typing", "src"}
    allowed_src = {"src.data.portfolio"}
    io_names = {"load_portfolio_tallied", "load_portfolio", "list_portfolios", "save_portfolio",
                "load_stock_watchlist", "clear_read_cache", "invalidate_my_read_cache", "invalidate_sheet_read_cache"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                assert a.name.split(".")[0] in allowed_roots - {"src"}, a.name
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            assert mod.split(".")[0] in allowed_roots, mod
            if mod.startswith("src"):
                assert mod in allowed_src and [a.name for a in n.names] == ["gsheet_portfolio"], mod
        elif isinstance(n, ast.Call):
            f = n.func
            assert not (isinstance(f, ast.Name) and f.id in {"open", "exec", "eval", "__import__"}), ast.dump(f)
            if isinstance(f, ast.Attribute):
                assert f.attr not in {"now", "today", "utcnow", "time", "perf_counter", "monotonic"}, f.attr
        elif isinstance(n, ast.keyword):
            assert n.arg != "keep_blank", "adapter 不得以 keep_blank= 呼叫任何東西（b10 守衛）"
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "_gsp":
            assert not n.attr.startswith("_"), f"adapter 不得取 L1 private symbol：{n.attr}"
            assert n.attr not in io_names, f"adapter 不得呼叫 L1 讀取入口：{n.attr}"


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
