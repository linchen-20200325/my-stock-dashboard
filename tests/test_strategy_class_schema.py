"""AB-4r：L0 `shared/strategy_class_schema.py` —— portfolio_id、持股鍵、策略分頁解析（純函式，無 I/O）。"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import math
import pathlib
from types import MappingProxyType

import pytest

from shared import strategy_class_schema as S
from shared.decision_digest import HoldingEntry, HoldingKey, StrategyType, _key_problem
from shared.decision_digest_validator import has_forbidden_char, holding_ref

H = list(S.STRATEGY_HEADERS)
SID = "1AbC_def-GHI"
BUY, CAP, UNC = StrategyType.BUY_AND_HOLD, StrategyType.CAPITAL_GAIN, StrategyType.UNCLASSIFIED


def pid(name, sid=SID):
    return S.derive_portfolio_id(sid, name)


def key(name, ticker, sid=SID):
    return HoldingKey(pid(name, sid), ticker)


def parse(*rows, sid=SID):
    return S.parse_strategy_records([H, *[list(r) for r in rows]], sheet_id=sid)


# ── 常數 ───────────────────────────────────────────────────────────────
def test_constants():
    assert S.STRATEGY_WORKSHEET_NAME == "strategy_class"
    assert S.STRATEGY_HEADERS == ("name", "ticker", "strategy", "updated_at")
    assert S.PORTFOLIO_ID_PREFIX == "pfv1-" and S.PORTFOLIO_ID_HEX_LEN == 20
    assert S.STRATEGY_SOURCE == "google_sheet:strategy_class"


@pytest.mark.parametrize("st", [BUY, CAP])
def test_strategy_source_passes_ab0_holding_entry(st):
    e = HoldingEntry(key=key("核心", "2330"), strategy=st, strategy_source=S.STRATEGY_SOURCE)
    assert e.strategy_source == S.STRATEGY_SOURCE


def test_l0_imports_only_stdlib_and_shared():
    src = pathlib.Path(S.__file__).read_text(encoding="utf-8")
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or "").split(".")[0])
    assert mods <= {"__future__", "collections", "hashlib", "unicodedata", "dataclasses", "types", "typing", "shared"}, mods


# ── portfolio_id ──────────────────────────────────────────────────────
def test_pid_formula_and_determinism():
    expect = "pfv1-" + hashlib.sha256((SID + "\x00" + "核心").encode("utf-8")).hexdigest()[:20]
    assert pid("核心") == expect == pid("核心")
    assert len(pid("核心")) == len("pfv1-") + 20


def test_pid_differs_across_sheets_same_name():
    assert pid("核心", "SHEET_A") != pid("核心", "SHEET_B")


def test_pid_differs_across_names():
    assert pid("核心") != pid("衛星")


def test_pid_outer_whitespace_same():
    assert pid("  核心\t") == pid("核心") == pid("\u3000核心\u3000")


def test_pid_sheet_id_whitespace_same():
    assert S.derive_portfolio_id(f"  {SID} ", "核心") == pid("核心")


@pytest.mark.parametrize("a,b", [("核 心", "核心"), ("ＡＢＣ", "ABC"), ("abc", "ABC"), ("核  心", "核 心")])
def test_pid_keeps_inner_space_fullwidth_case_differences(a, b):
    assert pid(a) != pid(b)


@pytest.mark.parametrize("sid,name", [
    ("", "核心"), ("   ", "核心"), (None, "核心"), (123, "核心"), ("e", "核心"), ("bad id!", "核心"),
    (SID, ""), (SID, "   "), (SID, None), (SID, 5),
])
def test_pid_rejects_empty_or_non_str(sid, name):
    with pytest.raises(ValueError):
        S.derive_portfolio_id(sid, name)


@pytest.mark.parametrize("name", ["核心", "a b", "ＡＢＣ", "x\u200by", "😀", "a:b"])
def test_pid_passes_ab0_and_ab2a_char_checks(name):
    p = pid(name)
    assert _key_problem(p) is None
    assert HoldingKey(p, "2330").portfolio_id == p
    assert not has_forbidden_char(p)
    assert holding_ref(p, "2330").startswith("holding:")


# ── build_holding_keys ────────────────────────────────────────────────
def test_build_holding_keys_maps_original_ticker():
    r = S.build_holding_keys(sheet_id=SID, portfolio_name=" 核心 ", tickers=["2330", "0050", "2330"])
    assert dict(r.keys) == {"2330": key("核心", "2330"), "0050": key("核心", "0050")}
    assert r.rejected == ()
    assert isinstance(r.keys, MappingProxyType)
    with pytest.raises(TypeError):
        r.keys["x"] = 1                          # type: ignore[index]


def test_build_holding_keys_rejects_without_rewriting():
    bad = [" 2330", "２３３０", "23 30", "", "a\u200bb"]
    r = S.build_holding_keys(sheet_id=SID, portfolio_name="核心", tickers=["2454", *bad, " 2330"])
    assert r.rejected == tuple(bad)
    assert list(r.keys) == ["2454"]


def test_build_holding_keys_does_not_apply_ab2a_symbol_pattern():
    # AB-2a SYMBOL_PATTERN 不允許 '_' 與超長；AB-0 鍵允許 ⇒ 這裡不得先濾掉（不遮蔽 AB-2a fail-closed）
    r = S.build_holding_keys(sheet_id=SID, portfolio_name="核心", tickers=["AB_C", "X" * 30])
    assert set(r.keys) == {"AB_C", "X" * 30} and r.rejected == ()


def test_build_holding_keys_type_and_pid_errors():
    with pytest.raises(TypeError):
        S.build_holding_keys(sheet_id=SID, portfolio_name="核心", tickers=[2330])
    with pytest.raises(TypeError):
        S.build_holding_keys(sheet_id=SID, portfolio_name="核心", tickers="2330")
    with pytest.raises(ValueError):
        S.build_holding_keys(sheet_id="", portfolio_name="核心", tickers=["2330"])


def test_build_holding_keys_feeds_ab1_builder_key_check():
    from src.services.decision_digest_builder import _key_for
    r = S.build_holding_keys(sheet_id=SID, portfolio_name="核心", tickers=["2330"])
    assert _key_for("2330", r.keys) == key("核心", "2330")


# ── 表頭 ───────────────────────────────────────────────────────────────
def test_header_ok_and_extra_right_columns():
    r = S.parse_strategy_records([H + ["memo", ""], ["核心", "2330", "存股", "t", "x"]], sheet_id=SID)
    assert r.status == "ok" and dict(r.entries) == {key("核心", "2330"): BUY}


def test_header_only_is_empty_ok():
    r = S.parse_strategy_records([H], sheet_id=SID)
    assert r.status == "ok" and not r.entries and not r.invalid_rows


@pytest.mark.parametrize("values", [[], [[]], [["", "  "]], [["", ""], ["", None]]])
def test_no_rows_or_all_blank_is_empty_ok(values):
    r = S.parse_strategy_records(values, sheet_id=SID)
    assert r.status == "ok" and not r.entries and not r.invalid_rows and not r.conflict_keys


@pytest.mark.parametrize("header,reason", [
    (["name", "ticker", "strategy"], S.HEADER_MISMATCH),               # 缺 updated_at（不放寬窄表頭）
    (["name", "ticker"], S.HEADER_MISMATCH),
    (["ticker", "name", "strategy", "updated_at"], S.HEADER_MISMATCH),
    (["Name", "ticker", "strategy", "updated_at"], S.HEADER_MISMATCH),
    ([" name", "ticker", "strategy", "updated_at"], S.HEADER_MISMATCH),
    (["", "name", "ticker", "strategy", "updated_at"], S.HEADER_MISMATCH),
    (H + ["strategy"], S.HEADER_DUPLICATE),
    (H + ["name"], S.HEADER_DUPLICATE),
    (["", "", ""], S.HEADER_FIRST_ROW_BLANK),
])
def test_header_mismatch_raises(header, reason):
    with pytest.raises(S.StrategySchemaMismatchError) as ei:
        S.parse_strategy_records([header, ["核心", "2330", "存股", "t"]], sheet_id=SID)
    assert ei.value.reason == reason


def test_user_extra_duplicate_columns_ok():
    r = S.parse_strategy_records([H + ["memo", "memo"], ["核心", "2330", "存股", "t"]], sheet_id=SID)
    assert dict(r.entries) == {key("核心", "2330"): BUY}


# ── 值 ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expect", [
    ("存股", BUY), ("存股 ", BUY), ("\u3000資本利得\t", CAP), ("資本利得", CAP),
])
def test_valid_strategy_values(raw, expect):
    assert dict(parse(["核心", "2330", raw, "t"]).entries) == {key("核心", "2330"): expect}


@pytest.mark.parametrize("raw", ["ＢＵＹ", "BUY", "HOLD", "hold", "😀", "", "   ", "存 股", "存股😀",
                                 "buy_and_hold", "存股\u200b", "存股/資本利得"])
def test_invalid_strategy_values_recorded_not_unclassified(raw):
    r = parse(["核心", "2330", raw, "t"])
    assert not r.entries and r.invalid_rows == (S.InvalidRow(2, S.INVALID_BAD_STRATEGY),)
    assert S.lookup(r, key("核心", "2330")) is UNC


def test_nfkc_applied_to_strategy():
    # U+F9DD 是「利」的 CJK 相容表意字（strip 不會動它，只有 NFKC 會轉成「利」）
    r = parse(["核心", "2330", "資本\uf9dd得", "t"])
    assert dict(r.entries) == {key("核心", "2330"): CAP}


def test_missing_name_and_ticker():
    r = parse(["", "2330", "存股", "t"], ["核心", "  ", "存股", "t"], ["  ", "", "存股", ""])
    assert r.invalid_rows == (S.InvalidRow(2, S.INVALID_MISSING_NAME),
                              S.InvalidRow(3, S.INVALID_MISSING_TICKER),
                              S.InvalidRow(4, S.INVALID_MISSING_NAME))
    assert not r.entries


def test_ticker_only_stripped_and_bad_key_recorded():
    r = parse([" 核心 ", " 2330 ", "存股", "t"], ["核心", "２３３０", "存股", "t"], ["核心", "23 30", "存股", "t"])
    assert dict(r.entries) == {key("核心", "2330"): BUY}
    assert r.invalid_rows == (S.InvalidRow(3, S.INVALID_BAD_KEY), S.InvalidRow(4, S.INVALID_BAD_KEY))


def test_blank_rows_skipped_and_short_rows_padded():
    r = parse(["", "", "", ""], [], ["核心", "2330", "存股"], ["  ", None])
    assert dict(r.entries) == {key("核心", "2330"): BUY} and r.invalid_rows == ()


@pytest.mark.parametrize("cell_row", [
    [float("nan"), "2330", "存股", "t"], ["核心", 2330, "存股", "t"], ["核心", "2330", 1.0, "t"],
    ["核心", "2330", True, "t"],
])
def test_non_text_cells_invalid(cell_row):
    r = parse(cell_row)
    assert r.invalid_rows == (S.InvalidRow(2, S.INVALID_NON_TEXT_CELL),) and not r.entries


def test_non_text_updated_at_is_ignored():
    r = parse(["核心", "2330", "存股", math.nan])
    assert dict(r.entries) == {key("核心", "2330"): BUY}


def test_values_type_errors():
    with pytest.raises(TypeError):
        S.parse_strategy_records(((*H,),), sheet_id=SID)            # type: ignore[arg-type]
    with pytest.raises(TypeError):
        S.parse_strategy_records([H, "核心,2330"], sheet_id=SID)
    with pytest.raises(ValueError):
        S.parse_strategy_records([H], sheet_id="")


# ── 去重 / 衝突 / 未分類 ──────────────────────────────────────────────
def test_duplicate_same_value_deduped():
    r = parse(["核心", "2330", "存股", "a"], [" 核心", "2330 ", "存股 ", "b"])
    assert dict(r.entries) == {key("核心", "2330"): BUY} and r.conflict_keys == ()


def test_conflict_excluded_not_picked():
    r = parse(["核心", "2330", "存股", "a"], ["核心", "2330", "資本利得", "b"], ["核心", "2330", "存股", "c"],
              ["核心", "0050", "資本利得", "d"])
    assert r.conflict_keys == (key("核心", "2330"),)
    assert dict(r.entries) == {key("核心", "0050"): CAP}
    assert S.lookup(r, key("核心", "2330")) is UNC


def test_conflict_key_listed_once():
    r = parse(["核心", "2330", "存股", ""], ["核心", "2330", "資本利得", ""], ["核心", "2330", "資本利得", ""])
    assert r.conflict_keys == (key("核心", "2330"),)


def test_conflict_with_unclassified_also_conflict():
    r = parse(["核心", "2330", "未分類", "a"], ["核心", "2330", "存股", "b"])
    assert r.conflict_keys == (key("核心", "2330"),) and not r.entries


def test_same_ticker_different_portfolio_independent():
    r = parse(["核心", "2330", "存股", ""], ["衛星", "2330", "資本利得", ""])
    assert dict(r.entries) == {key("核心", "2330"): BUY, key("衛星", "2330"): CAP}


def test_unclassified_rows_not_in_entries():
    r = parse(["核心", "2330", "未分類", "t"])
    assert r.status == "ok" and not r.entries and not r.invalid_rows and not r.conflict_keys
    assert S.lookup(r, key("核心", "2330")) is UNC


def test_entries_immutable():
    r = parse(["核心", "2330", "存股", ""])
    assert isinstance(r.entries, MappingProxyType)
    with pytest.raises(TypeError):
        r.entries[key("核心", "0050")] = CAP          # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.status = "x"                                   # type: ignore[misc]


def test_entries_build_valid_holding_entries():
    r = parse(["核心", "2330", "存股", ""], ["核心", "0050", "資本利得", ""])
    for k, v in r.entries.items():
        HoldingEntry(key=k, strategy=v, strategy_source=S.STRATEGY_SOURCE)


# ── lookup / result 不變量 ────────────────────────────────────────────
@pytest.mark.parametrize("status", ["ok", "worksheet_missing", "not_bound"])
def test_lookup_default_unclassified(status):
    assert S.lookup(S.empty_result(status), key("核心", "2330")) is UNC


def test_lookup_type_errors():
    r = S.empty_result("ok")
    with pytest.raises(TypeError):
        S.lookup(r, ("pid", "2330"))                     # type: ignore[arg-type]
    with pytest.raises(TypeError):
        S.lookup({}, key("核心", "2330"))                 # type: ignore[arg-type]


def test_result_invariants():
    with pytest.raises(ValueError):
        S.StrategyReadResult(status="error")
    with pytest.raises(TypeError):
        S.StrategyReadResult(status="ok", entries=[])                       # type: ignore[arg-type]
    with pytest.raises(TypeError):
        S.StrategyReadResult(status="ok", invalid_rows=((2, "bad_key"),))
    with pytest.raises(TypeError):
        S.StrategyReadResult(status="ok", conflict_keys=(("pid", "2330"),))
    with pytest.raises(ValueError):
        S.StrategyReadResult(status="ok", entries={("pid", "2330"): BUY})
    with pytest.raises(ValueError):
        S.StrategyReadResult(status="ok", entries={key("核心", "2330"): "存股"})
    with pytest.raises(ValueError):
        S.StrategyReadResult(status="ok", entries=MappingProxyType({key("核心", "2330"): UNC}))
    with pytest.raises(ValueError):
        S.StrategyReadResult(status="not_bound", entries=MappingProxyType({key("核心", "2330"): BUY}))



# ── QA m-2：entries／keys 一律複製（斷開外部 dict 別名）──────────────────────
def test_result_entries_copied_from_external_dict():
    d = {key("核心", "2330"): BUY}
    r = S.StrategyReadResult(status="ok", entries=d)
    d[key("核心", "0050")] = CAP
    d[key("核心", "2330")] = CAP
    assert dict(r.entries) == {key("核心", "2330"): BUY}
    assert isinstance(r.entries, MappingProxyType)


def test_result_entries_copied_even_from_mappingproxy():
    d = {key("核心", "2330"): BUY}
    r = S.StrategyReadResult(status="ok", entries=MappingProxyType(d))
    d[key("核心", "2330")] = CAP
    assert r.entries[key("核心", "2330")] is BUY


def test_holding_keys_result_copied_and_validated():
    d = {"2330": key("核心", "2330")}
    r = S.HoldingKeysResult(keys=d)
    d["0050"] = key("核心", "0050")
    assert list(r.keys) == ["2330"] and isinstance(r.keys, MappingProxyType)
    with pytest.raises(ValueError):
        S.HoldingKeysResult(keys={"2330": key("核心", "0050")})
    with pytest.raises(ValueError):
        S.HoldingKeysResult(keys={"2330": "x"})
    with pytest.raises(TypeError):
        S.HoldingKeysResult(keys=[])                                         # type: ignore[arg-type]
    with pytest.raises(TypeError):
        S.HoldingKeysResult(rejected=(1,))


# ── QA m-1：合法列＋bad_strategy 列同鍵 → 衝突 ─────────────────────────────
@pytest.mark.parametrize("rows", [
    (["核心", "2330", "存股", ""], ["核心", "2330", "HOLD", ""]),
    (["核心", "2330", "ＢＵＹ", ""], ["核心", "2330", "存股", ""]),
    (["核心", "2330", "存股", ""], [" 核心 ", "2330 ", "", ""]),
])
def test_valid_plus_bad_strategy_same_key_is_conflict(rows):
    r = parse(*rows)
    assert r.conflict_keys == (key("核心", "2330"),) and not r.entries
    assert S.InvalidRow(2, S.INVALID_BAD_STRATEGY) in r.invalid_rows or \
        S.InvalidRow(3, S.INVALID_BAD_STRATEGY) in r.invalid_rows
    assert S.lookup(r, key("核心", "2330")) is UNC


def test_bad_strategy_only_is_invalid_not_conflict():
    r = parse(["核心", "2330", "HOLD", ""], ["核心", "0050", "存股", ""])
    assert r.conflict_keys == () and dict(r.entries) == {key("核心", "0050"): BUY}


def test_bad_key_row_does_not_poison_valid_key():
    r = parse(["核心", "2330", "存股", ""], ["核心", "２３３０", "HOLD", ""])
    assert dict(r.entries) == {key("核心", "2330"): BUY} and r.conflict_keys == ()
    assert r.invalid_rows == (S.InvalidRow(3, S.INVALID_BAD_KEY),)


# ── QA-A M-1：unmatched_keys ─────────────────────────────────────────────
def test_unmatched_keys_reports_orphans_without_changing_lookup():
    r = parse(["核心", "50", "存股", ""], ["核心", "00631l", "資本利得", ""], ["核心", "2330", "存股", ""],
              ["核芯", "2454", "存股", ""])
    hk = S.build_holding_keys(sheet_id=SID, portfolio_name="核心", tickers=["0050", "00631L", "2330", "2454"])
    assert S.unmatched_keys(r, hk.keys.values()) == (key("核心", "50"), key("核心", "00631l"), key("核芯", "2454"))
    assert S.lookup(r, hk.keys["0050"]) is UNC and S.lookup(r, hk.keys["00631L"]) is UNC
    assert S.lookup(r, hk.keys["2330"]) is BUY
    assert S.lookup(r, key("核心", "50")) is BUY              # 不改 lookup 結果


def test_unmatched_keys_multi_portfolio_union_same_ticker():
    r = parse(["核心", "2330", "存股", ""], ["衛星", "2330", "資本利得", ""])
    core = S.build_holding_keys(sheet_id=SID, portfolio_name="核心", tickers=["2330"])
    sat = S.build_holding_keys(sheet_id=SID, portfolio_name="衛星", tickers=["2330"])
    union = [*core.keys.values(), *sat.keys.values()]
    assert S.unmatched_keys(r, union) == ()                       # 同 ticker 兩組合不互蓋、不誤報
    assert S.unmatched_keys(r, iter(union)) == ()                  # 任何 iterable（含 generator）
    assert S.unmatched_keys(r, core.keys.values()) == (key("衛星", "2330"),)   # 只給一組合 ⇒ 另一組合被列出（用法限制）


def test_unmatched_keys_excludes_conflict_keys():
    r = parse(["核心", "9999", "存股", ""], ["核心", "9999", "資本利得", ""], ["核心", "8888", "存股", ""])
    assert r.conflict_keys == (key("核心", "9999"),)
    assert S.unmatched_keys(r, []) == (key("核心", "8888"),)      # 衝突鍵不列為孤兒（另有 conflict 揭露）


def test_unmatched_keys_empty_when_all_matched_and_types():
    r = parse(["核心", "2330", "存股", ""])
    hk = S.build_holding_keys(sheet_id=SID, portfolio_name="核心", tickers=["2330"])
    assert S.unmatched_keys(r, hk.keys.values()) == ()
    assert S.unmatched_keys(S.empty_result("not_bound"), ()) == ()
    for bad in (hk.keys, {"2330": key("核心", "2330")}, {key("核心", "2330"): BUY}, "2330", b"2330", "", b"", {}, 5, None):
        with pytest.raises(TypeError):
            S.unmatched_keys(r, bad)                                        # type: ignore[arg-type]
    with pytest.raises(TypeError):
        S.unmatched_keys(r, ["2330"])                                       # type: ignore[list-item]
    with pytest.raises(TypeError):
        S.unmatched_keys({}, hk.keys.values())                              # type: ignore[arg-type]


# ── 第三組：InvalidRow／HoldingKeysResult／entries 鍵重建 ───────────────────
@pytest.mark.parametrize("row,reason", [(0, S.INVALID_BAD_KEY), (-1, S.INVALID_BAD_KEY), (True, S.INVALID_BAD_KEY),
                                        (2.0, S.INVALID_BAD_KEY), ("2", S.INVALID_BAD_KEY), (2, "oops"), (2, None)])
def test_invalid_row_validation(row, reason):
    with pytest.raises(ValueError):
        S.InvalidRow(row, reason)


def test_invalid_row_ok():
    assert S.InvalidRow(1, S.INVALID_MISSING_NAME).row == 1


def test_holding_keys_result_no_overlap_and_single_portfolio():
    with pytest.raises(ValueError):
        S.HoldingKeysResult(keys={"2330": key("核心", "2330")}, rejected=("2330",))
    with pytest.raises(ValueError):
        S.HoldingKeysResult(keys={"2330": key("核心", "2330"), "0050": key("衛星", "0050")})
    assert len(S.HoldingKeysResult(keys={"2330": key("核心", "2330"), "0050": key("核心", "0050")},
                                   rejected=("x y",)).keys) == 2


def test_entries_key_rebuilt_blocks_new_bypass():
    bogus = object.__new__(HoldingKey)
    object.__setattr__(bogus, "portfolio_id", "has space")
    object.__setattr__(bogus, "symbol", "2330")
    with pytest.raises(ValueError):
        S.StrategyReadResult(status="ok", entries={bogus: BUY})
