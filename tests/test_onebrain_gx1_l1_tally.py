"""C-OB-GX1-L1-ADDITIVE-TALLY-1 — L1 持股讀取「計數」API 測試（全離線、合成資料、固定格點窮舉；無網路、無 hypothesis）。

授權：Issue #1199 客戶裁示 comment 7055751465；施工包 comment 7055505068。
範圍：僅 L1 純加性 `PortfolioReadTally` / `tally_portfolio_records` / `load_portfolio_tallied`；
0 production caller；不改 `parse_portfolio_records` / `load_portfolio` / `_editor_loaded_row` 的判定；
不修補 NaN／+inf（只揭露）、不去重、不接 L3／UI。

⚠️ 單組作者自測，未經獨立 QA。`raw` 與 `rows` 同源，不是獨立 expected completeness。
"""
from __future__ import annotations

import ast
import importlib.util
import itertools
import math
import pathlib
import socket
import sys
import types
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, patch

import pytest

import src.data.portfolio.gsheet_portfolio as GSP

REPO = pathlib.Path(__file__).resolve().parents[1]
GSP_PATH = pathlib.Path(GSP.__file__).resolve()
H = GSP._HEADERS
NAN, INF, NINF = float("nan"), float("inf"), float("-inf")
FOUR_REASONS = (GSP.DROP_BLANK_TICKER, GSP.DROP_NON_NUMERIC, GSP.DROP_NON_FINITE, GSP.DROP_NON_POSITIVE)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """離線守衛：任何真實 socket 連線 ＝ 測試失敗。"""
    def _boom(*_a, **_k):
        raise AssertionError("測試不得連網")
    monkeypatch.setattr(socket.socket, "connect", _boom)


# ── 合成輸入 ─────────────────────────────────────────────────────────────
def seven_raw_records():
    """與 gap evidence 檔同一組：7 筆、預設路徑只剩 1 筆（公開代號、匿名合成）。"""
    return [
        {"ticker": "2330", "lots": 2, "avg_price": 100.0},
        {"ticker": "", "lots": 1, "avg_price": 50.0},
        {"ticker": "0050", "lots": 0, "avg_price": 120.0},
        {"ticker": "2317", "lots": 1, "avg_price": -1},
        {"ticker": "2454", "lots": "abc", "avg_price": 30.0},
        {"ticker": "2412", "lots": "", "avg_price": ""},
        {"ticker": "2882", "lots": None, "avg_price": 10.0},
    ]


GRID_TICKERS = ("", " ", "A")
GRID_CELLS = (None, "", " ", 0, "0", -1, 1, 1.5, "abc", "nan", NAN, INF, NINF, "1_0", "1,050", False, [], "inf", "-inf")


def grid_records():
    return [{"ticker": t, "lots": a, "avg_price": b}
            for t, a, b in itertools.product(GRID_TICKERS, GRID_CELLS, GRID_CELLS)]


def _same(a, b) -> bool:
    return repr(a) == repr(b)      # repr 讓 nan == nan


def _label(mod, rec, keep_blank):
    """單列 → 'dropped:<reason>' 或 'kept:<flavor>'（走公開 tally，mutant 模組也可用）。"""
    t = mod.tally_portfolio_records([rec], keep_blank=keep_blank)
    drops = [k for k, v in t.dropped_by_reason if v]
    if drops:
        assert len(drops) == 1 and t.kept == 0
        return f"dropped:{drops[0]}"
    return "kept:" + ("non_finite" if t.kept_non_finite else "missing" if t.kept_with_missing_value else "clean")


# 判定順序表：空代號 > 非數值 > -inf > <=0 > 空白（空白最後）。(ticker, lots, avg, 預設模式, keep_blank 模式)
_BT, _NN, _NF, _NP = ("dropped:blank_ticker", "dropped:non_numeric", "dropped:non_finite", "dropped:non_positive")
ORDER_TABLE = (
    ("", 1, 1, _BT, _BT),
    (" ", "abc", NINF, _BT, _BT),                    # 空代號壓過一切
    ("A", "abc", 1, _NN, _NN),
    ("A", "abc", "", _NN, _NN),                      # 非數值壓過空白
    ("A", "abc", NINF, _NN, _NN),                    # 非數值壓過 -inf
    ("A", "", NINF, _NF, _NF),                       # -inf 壓過空白
    ("A", NINF, -1, _NF, _NF),                       # -inf 壓過 <=0
    ("A", -1, "", _NP, _NP),                         # <=0 壓過空白
    ("A", 0, 1, _NP, _NP),                           # 使用者寫 0 ＝ non_positive（不是空白）
    ("A", 1, False, _NP, _NP),                       # False 不是空白格
    ("A", "", 1, "dropped:blank_value", "kept:missing"),
    ("A", None, None, "dropped:blank_value", "kept:missing"),
    ("A", " ", 1, "dropped:blank_value", "kept:missing"),
    ("A", 1, 1, "kept:clean", "kept:clean"),
    ("A", NAN, 1, "kept:non_finite", "kept:non_finite"),
    ("A", 1, INF, "kept:non_finite", "kept:non_finite"),
    ("A", "", NAN, "dropped:blank_value", "kept:non_finite"),   # 缺值＋NaN：keep_blank 下 non_finite 優先
)


def _violations(mod) -> list[str]:
    """對 `mod`（原模組或 mutant 副本）跑全部核心斷言，回傳違規描述；空 ＝ 通過。"""
    bad: list[str] = []
    # (1) 判定順序表
    for tk, a, b, d_exp, k_exp in ORDER_TABLE:
        rec = {"ticker": tk, "lots": a, "avg_price": b}
        for kb, exp in ((False, d_exp), (True, k_exp)):
            try:
                got = _label(mod, rec, kb)
            except ValueError as e:
                got = f"ValueError:{e}"
            if got != exp:
                bad.append(f"順序表 {tk!r},{a!r},{b!r} kb={kb}: {got} != {exp}")
    # (2) 格點：與 parse 保留集合逐列相同＋恆等式＋跨模式 M1–M4
    recs = grid_records()
    for r in recs:
        try:
            td = mod.tally_portfolio_records([r], keep_blank=False)
            tk_ = mod.tally_portfolio_records([r], keep_blank=True)
        except ValueError as e:
            bad.append(f"格點 raise {r!r}: {e}")
            continue
        for t, kb in ((td, False), (tk_, True)):
            if not _same(list(t.rows), mod.parse_portfolio_records([r], keep_blank=kb)):
                bad.append(f"rows != parse {r!r} kb={kb}")
        dd, dk = td.dropped, tk_.dropped
        if td.raw != tk_.raw:
            bad.append(f"M1 {r!r}")
        if tk_.kept < td.kept:
            bad.append(f"M2 {r!r}")
        if tk_.kept - td.kept != dd[mod.DROP_BLANK_VALUE]:
            bad.append(f"M3 {r!r}")
        if any(dd[k] != dk[k] for k in FOUR_REASONS):
            bad.append(f"M4a {r!r}")
        if (tk_.kept_non_finite - td.kept_non_finite) + tk_.kept_with_missing_value != dd[mod.DROP_BLANK_VALUE]:
            bad.append(f"M4b {r!r}")
        if dk[mod.DROP_BLANK_VALUE] != 0 or td.kept_with_missing_value != 0:
            bad.append(f"blank_value 模式約束 {r!r}")
    # 整批（一次 868 列）同樣要過
    for kb in (False, True):
        try:
            t = mod.tally_portfolio_records(recs, keep_blank=kb)
        except ValueError as e:
            bad.append(f"整批 raise kb={kb}: {e}")
            continue
        if not _same(list(t.rows), mod.parse_portfolio_records(recs, keep_blank=kb)):
            bad.append(f"整批 rows != parse kb={kb}")
    return bad


def _mutant(*pairs: tuple[str, str]) -> types.ModuleType:
    """把 gsheet_portfolio 原始碼的每組 old **恰好一處**換成 new，載成獨立副本（同 b10 作法）。"""
    src = GSP_PATH.read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = "_mutant_gx1_gsheet_portfolio"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = str(GSP_PATH)
    sys.modules[name] = m
    try:
        exec(compile(src, str(GSP_PATH), "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ═══ 1. 7 → 1：兩模式精確計數 ═══════════════════════════════════════════
def test_seven_to_one_default_mode_exact_counts():
    t = GSP.tally_portfolio_records(seven_raw_records(), keep_blank=False)
    assert (t.status, t.raw, t.kept, t.sheet_data_rows) == ("ok", 7, 1, 7)
    assert t.dropped == {"blank_ticker": 1, "non_numeric": 1, "non_finite": 0, "non_positive": 2, "blank_value": 2}
    assert (t.kept_clean, t.kept_with_missing_value, t.kept_non_finite) == (1, 0, 0)
    assert list(t.rows) == [{"ticker": "2330", "lots": 2.0, "avg_price": 100.0}]
    assert t.raw - t.kept == 6                         # 原 xfail 的期望：dropped == 6


def test_seven_to_three_keep_blank_mode_exact_counts():
    t = GSP.tally_portfolio_records(seven_raw_records(), keep_blank=True)
    assert (t.raw, t.kept) == (7, 3)
    assert t.dropped == {"blank_ticker": 1, "non_numeric": 1, "non_finite": 0, "non_positive": 2, "blank_value": 0}
    assert (t.kept_clean, t.kept_with_missing_value, t.kept_non_finite) == (1, 2, 0)
    assert {r["ticker"] for r in t.rows} == {"2330", "2412", "2882"}


def test_dropped_by_reason_has_fixed_five_keys_in_order():
    for kb in (False, True):
        t = GSP.tally_portfolio_records([], keep_blank=kb)
        assert tuple(k for k, _ in t.dropped_by_reason) == GSP.TALLY_DROP_REASONS
        assert t.raw == t.kept == t.sheet_data_rows == 0 and all(v == 0 for _, v in t.dropped_by_reason)
    assert GSP.tally_portfolio_records(None, keep_blank=False).raw == 0     # 與 parse 一致：None 視為空


# ═══ 2. 格點窮舉 ＋ 判定順序表 ＋ 恆等式 ＋ M1–M4 ═══════════════════════
def test_grid_matches_parse_and_all_invariants():
    assert len(grid_records()) >= 800
    assert _violations(GSP) == []


def test_order_table_is_nonempty_and_covers_every_reason():
    reasons = {e for row in ORDER_TABLE for e in row[3:]}
    assert {f"dropped:{k}" for k in GSP.TALLY_DROP_REASONS} <= reasons
    assert {"kept:clean", "kept:missing", "kept:non_finite"} <= reasons


def test_identity_violation_raises_value_error_not_silent():
    t = GSP.tally_portfolio_records(seven_raw_records(), keep_blank=False)
    import dataclasses
    bad = dataclasses.replace(t, kept=t.kept + 1)
    with pytest.raises(ValueError, match="恆等式"):
        GSP._verify_tally_identities(bad)
    bad2 = dataclasses.replace(t, sheet_data_rows=t.sheet_data_rows + 1)
    with pytest.raises(ValueError, match="sheet_data_rows"):
        GSP._verify_tally_identities(bad2)
    bad3 = dataclasses.replace(t, dropped_by_reason=t.dropped_by_reason[:-1])
    with pytest.raises(ValueError, match="五鍵"):
        GSP._verify_tally_identities(bad3)
    unk = GSP.PortfolioReadTally(status=GSP.READ_WORKSHEET_MISSING, keep_blank=False, raw=0)
    with pytest.raises(ValueError, match="UNKNOWN"):
        GSP._verify_tally_identities(unk)


# ═══ 3. 空白 vs <=0 分流；NaN／+inf 只揭露；-inf 丟棄 ═══════════════════
def test_blank_vs_non_positive_are_split():
    recs = [{"ticker": "A", "lots": "", "avg_price": 5}, {"ticker": "B", "lots": 0, "avg_price": 5},
            {"ticker": "C", "lots": -3, "avg_price": 5}]
    d = GSP.tally_portfolio_records(recs, keep_blank=False).dropped
    assert (d["blank_value"], d["non_positive"]) == (1, 2)
    k = GSP.tally_portfolio_records(recs, keep_blank=True)
    assert (k.dropped["blank_value"], k.dropped["non_positive"], k.kept_with_missing_value) == (0, 2, 1)


def test_nan_and_pos_inf_are_kept_and_disclosed_not_filtered():
    recs = [{"ticker": "A", "lots": NAN, "avg_price": 1}, {"ticker": "B", "lots": 1, "avg_price": INF},
            {"ticker": "C", "lots": "nan", "avg_price": 1}, {"ticker": "D", "lots": 1, "avg_price": 1}]
    for kb in (False, True):
        t = GSP.tally_portfolio_records(recs, keep_blank=kb)
        assert (t.kept, t.kept_non_finite, t.kept_clean) == (4, 3, 1)
        assert [r["ticker"] for r in t.rows] == ["A", "B", "C", "D"]          # 仍在 rows 內：未改判
        assert math.isnan(t.rows[0]["lots"]) and t.rows[1]["avg_price"] == INF
        assert _same(list(t.rows), GSP.parse_portfolio_records(recs, keep_blank=kb))


def test_neg_inf_is_dropped_as_non_finite():
    recs = [{"ticker": "A", "lots": NINF, "avg_price": 1}, {"ticker": "B", "lots": 1, "avg_price": "-inf"}]
    for kb in (False, True):
        t = GSP.tally_portfolio_records(recs, keep_blank=kb)
        assert (t.kept, t.dropped["non_finite"], t.dropped["non_positive"]) == (0, 2, 0)


def test_kept_split_priority_non_finite_over_missing():
    r = [{"ticker": "A", "lots": "", "avg_price": NAN}]
    t = GSP.tally_portfolio_records(r, keep_blank=True)
    assert (t.kept_non_finite, t.kept_with_missing_value, t.kept_clean) == (1, 0, 0)


# ═══ 4. 重複代號：原樣保留＋計數，不去重 ═════════════════════════════════
def test_duplicate_tickers_counted_never_deduped():
    recs = [{"ticker": "2330", "lots": 1, "avg_price": 10}, {"ticker": " 2330 ", "lots": 2, "avg_price": 20},
            {"ticker": "2330", "lots": 0, "avg_price": 20},          # 丟棄列，但仍算來源重複
            {"ticker": "aapl", "lots": 1, "avg_price": 1}, {"ticker": "AAPL", "lots": 1, "avg_price": 1},  # 大小寫不同＝不同
            {"ticker": "0050", "lots": 1, "avg_price": 1}]
    t = GSP.tally_portfolio_records(recs, keep_blank=False)
    assert t.duplicate_tickers == ("2330",)
    assert (t.duplicate_source_rows, t.duplicate_kept_rows) == (3, 2)
    assert [r["ticker"] for r in t.rows] == ["2330", "2330", "aapl", "AAPL", "0050"]   # 不去重、不改大小寫
    assert t.kept == 5


# ═══ 5. Sheet 層：fake worksheet（離線）══════════════════════════════════
class _FakeWS:
    def __init__(self, values):
        self.values, self.reads = values, 0

    def get_all_values(self):
        self.reads += 1
        return [list(r) for r in self.values]


def _sheet(*body, header=None):
    return [list(header or H), *[list(r) for r in body]]


SYNTH = _sheet(
    ["核心", "2330", "2", "100", "t"],
    ["核心", "", "1", "50", "t"],            # 空代號
    ["核心", "0050", "0", "120", "t"],       # 0 張
    ["核心", "2317", "1", "-1", "t"],
    ["核心", "2454", "abc", "30", "t"],
    ["核心", "2412", "", "", "t"],           # 兩欄空白
    ["核心", "2882", "", "10", "t"],
    ["", "9999", "1", "1", "t"],             # name 空白、列非全空
    ["", "", "", "", ""],                    # 整列全空
    ["別組", "2603", "1", "1", "t"],
    ["別組", "2618", "x", "1", "t"],
    ["核心", "2330", "3", "110", "t"],       # 重複代號
)


@pytest.fixture
def fake_sheet(monkeypatch):
    holder = {}

    def _install(values):
        ws = _FakeWS(values)
        holder["ws"] = ws
        monkeypatch.setattr(GSP, "_ws", lambda **_k: ws)
        monkeypatch.setattr(GSP, "_cache_identity", lambda: "")      # 無身分 ⇒ 不碰快取，直走 raw
        return ws
    return _install


def test_sheet_partition_and_single_read(fake_sheet):
    ws = fake_sheet(SYNTH)
    t = GSP.load_portfolio_tallied("核心", sheet_id="S", keep_blank=False)
    assert ws.reads == 1                                       # 一次呼叫只讀一次
    assert (t.status, t.sheet_data_rows) == ("ok", 12)
    assert (t.blank_rows, t.blank_name_rows, t.other_name_rows, t.raw) == (1, 1, 2, 8)
    assert t.sheet_data_rows == t.blank_rows + t.blank_name_rows + t.other_name_rows + t.raw
    assert (t.kept, t.dropped) == (2, {"blank_ticker": 1, "non_numeric": 1, "non_finite": 0,
                                       "non_positive": 2, "blank_value": 2})
    assert t.raw == t.kept + sum(t.dropped.values())
    assert t.duplicate_tickers == ("2330",) and (t.duplicate_source_rows, t.duplicate_kept_rows) == (2, 2)
    kb = GSP.load_portfolio_tallied("核心", sheet_id="S", keep_blank=True)
    assert (kb.raw, kb.kept, kb.kept_with_missing_value) == (8, 4, 2)


def test_sheet_rows_equal_load_portfolio_rows(fake_sheet):
    fake_sheet(SYNTH)
    for kb in (False, True):
        t = GSP.load_portfolio_tallied("核心", sheet_id="S", keep_blank=kb)
        assert _same(list(t.rows), GSP.load_portfolio("核心", sheet_id="S", keep_blank=kb))
        assert _same(list(t.rows), GSP.parse_portfolio_records(
            [GSP._sheet_record(SYNTH[0], r) for r in SYNTH[1:] if r[0] == "核心"], keep_blank=kb))


def test_sheet_numeric_name_like_cells_do_not_corrupt_partition(fake_sheet):
    # name 欄保留原字串（_TEXT_COLS）：'0050' 作為組合名也能正確分區
    fake_sheet(_sheet(["0050", "2330", "1", "1", "t"], ["0050", "2317", "1", "1", "t"], ["50", "x", "1", "1", "t"]))
    t = GSP.load_portfolio_tallied("0050", sheet_id="S")
    assert (t.raw, t.kept, t.other_name_rows) == (2, 2, 1)


def test_status_worksheet_missing_schema_mismatch_all_none(fake_sheet, monkeypatch):
    def _missing(**_k):
        raise GSP.SheetWorksheetMissingError("portfolios")
    monkeypatch.setattr(GSP, "_cache_identity", lambda: "")
    monkeypatch.setattr(GSP, "_ws", _missing)
    t = GSP.load_portfolio_tallied("核心", sheet_id="S")
    assert t.status == GSP.READ_WORKSHEET_MISSING
    fake_sheet([["foo", "bar"], ["核心", "2330"]])
    m = GSP.load_portfolio_tallied("核心", sheet_id="S")
    assert m.status == GSP.READ_SCHEMA_MISMATCH
    for u in (t, m):
        assert u.rows is None and u.dropped_by_reason is None and u.duplicate_tickers is None
        assert all(getattr(u, f) is None for f in GSP._TALLY_COUNT_FIELDS)    # UNKNOWN，不是 0
        assert u.dropped is None
        GSP._verify_tally_identities(u)


def test_empty_sheet_is_ok_all_zero(fake_sheet):
    fake_sheet([])
    t = GSP.load_portfolio_tallied("核心", sheet_id="S")
    assert (t.status, t.sheet_data_rows, t.raw, t.kept) == ("ok", 0, 0, 0)


def test_not_selected_never_reads_sheet(monkeypatch):
    def _no(**_k):
        raise AssertionError("name 空白時不得讀 Sheet")
    monkeypatch.setattr(GSP, "_ws", _no)
    monkeypatch.setattr(GSP, "_open_spreadsheet", _no)
    for nm in ("", "  ", None):
        t = GSP.load_portfolio_tallied(nm, sheet_id="S")
        assert t.status == GSP.TALLY_NOT_SELECTED and t.raw is None and t.rows is None
        assert t.dropped is None


def test_read_failure_propagates_not_swallowed(fake_sheet, monkeypatch):
    monkeypatch.setattr(GSP, "_cache_identity", lambda: "")
    monkeypatch.setattr(GSP, "_ws", lambda **_k: (_ for _ in ()).throw(PermissionError("no ACL")))
    with pytest.raises(PermissionError):
        GSP.load_portfolio_tallied("核心", sheet_id="S")


# ═══ 6. 快取／身分隔離／clear_read_cache（走真 st.cache_data，同 b5 作法）═══════
_BOOKS = {
    "A": {"SID1": _sheet(["核心", "2330", "1", "1", "t"], ["核心", "0050", "", "5", "t"])},
    "B": {"SID1": _sheet(["核心", "2317", "9", "9", "t"])},          # 同 sheet_id、不同使用者、不同內容
}


@pytest.fixture
def env():
    calls: list[tuple[str, str]] = []
    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.secrets = {}
    state = {"fail": False}

    class _WSx:
        def __init__(self, rows):
            self.rows = rows

        def get_all_values(self):
            if state["fail"]:
                raise ConnectionError("boom")
            return [list(r) for r in self.rows]

    class _SH:
        def __init__(self, rows):
            self.rows = rows

        def worksheet(self, _n):
            return _WSx(self.rows)

    class _Client:
        def __init__(self, who):
            self.who = who

        def open_by_key(self, sid):
            calls.append((self.who, sid))
            return _SH(_BOOKS[self.who][sid])

    class _Env:
        calls_ = calls
        st_state = state

        def login(self, who):
            fake_st.session_state = {"gsheet_tokens": {"who": who, "access_token": f"at-{who}",
                                                       "refresh_token": f"rt-{who}"}}

        def n(self, who, sid="SID1"):
            return calls.count((who, sid))

    GSP.clear_read_cache()
    with GSP._READ_GEN_LOCK:
        GSP._READ_GEN.clear()
    with patch.object(GSP, "st", fake_st), \
            patch("src.data.portfolio.oauth_state.is_oauth_configured", return_value=True), \
            patch("src.data.portfolio.oauth_state._get_oauth_client",
                  side_effect=lambda: _Client(fake_st.session_state["gsheet_tokens"]["who"])):
        yield _Env()
    GSP.clear_read_cache()
    with GSP._READ_GEN_LOCK:
        GSP._READ_GEN.clear()


def test_cache_hit_same_identity_and_identity_isolation(env):
    env.login("A")
    a1 = GSP.load_portfolio_tallied("核心", sheet_id="SID1", keep_blank=True)
    a2 = GSP.load_portfolio_tallied("核心", sheet_id="SID1", keep_blank=True)
    assert env.n("A") == 1 and a1 == a2                     # 第二次命中快取：0 次再問 Google
    env.login("B")
    b = GSP.load_portfolio_tallied("核心", sheet_id="SID1", keep_blank=True)
    assert env.n("B") == 1                                  # B 不吃 A 的快取
    assert (a1.kept, b.kept) == (2, 1) and [r["ticker"] for r in b.rows] == ["2317"]
    env.login("A")
    assert GSP.load_portfolio_tallied("核心", sheet_id="SID1", keep_blank=True) == a1 and env.n("A") == 1
    # keep_blank 屬快取鍵：另一種模式另取一份
    GSP.load_portfolio_tallied("核心", sheet_id="SID1", keep_blank=False)
    assert env.n("A") == 2


def test_clear_read_cache_clears_tallied_cache(env):
    env.login("A")
    GSP.load_portfolio_tallied("核心", sheet_id="SID1")
    GSP.load_portfolio_tallied("核心", sheet_id="SID1")
    assert env.n("A") == 1
    GSP.clear_read_cache()
    GSP.load_portfolio_tallied("核心", sheet_id="SID1")
    assert env.n("A") == 2


def test_my_sheet_invalidation_hits_tallied_cache_via_read_gen(env):
    env.login("A")
    GSP.load_portfolio_tallied("核心", sheet_id="SID1")
    assert GSP.invalidate_my_read_cache("SID1") == 1
    GSP.load_portfolio_tallied("核心", sheet_id="SID1")
    assert env.n("A") == 2


def test_failed_read_is_not_cached(env):
    env.login("A")
    env.st_state["fail"] = True
    with pytest.raises(ConnectionError):
        GSP.load_portfolio_tallied("核心", sheet_id="SID1")
    env.st_state["fail"] = False
    t = GSP.load_portfolio_tallied("核心", sheet_id="SID1")
    assert t.status == "ok" and t.raw == 2                   # 失敗沒被凍成快取


def test_read_gen_param_is_not_underscored():
    import inspect
    sig = inspect.signature(getattr(GSP._load_portfolio_tallied_cached, "__wrapped__",
                                    GSP._load_portfolio_tallied_cached))
    assert "read_gen" in sig.parameters and "identity" in sig.parameters


# ═══ 7. 隱私 ═════════════════════════════════════════════════════════════
def test_repr_str_and_errors_leak_nothing(fake_sheet):
    secret_sid = "SHEET-ID-SECRET-123"
    ws_vals = _sheet(["核心", "2330", "1", "1", "t"], ["別組私密名", "SECRETTK", "777.5", "888.5", "t"])
    fake_sheet(ws_vals)
    t = GSP.load_portfolio_tallied("核心", sheet_id=secret_sid, keep_blank=True)
    for text in (repr(t), str(t)):
        for leak in (secret_sid, "別組私密名", "SECRETTK", "777.5", "888.5", "2330"):
            assert leak not in text, leak
    assert "duplicate_tickers" in repr(t)                     # 只有本組合的重複代號欄可含代號
    try:
        GSP._verify_tally_identities(__import__("dataclasses").replace(t, kept=99))
    except ValueError as e:
        for leak in (secret_sid, "別組私密名", "SECRETTK", "2330"):
            assert leak not in str(e)
    assert t.other_name_rows == 1                             # 其他組合只剩數字


def test_other_group_content_never_reaches_rows_or_tickers(fake_sheet):
    fake_sheet(SYNTH)
    t = GSP.load_portfolio_tallied("核心", sheet_id="S")
    assert "2603" not in {r["ticker"] for r in t.rows} and "2603" not in t.duplicate_tickers


# ═══ 8. 不可變 ═══════════════════════════════════════════════════════════
def test_frozen_and_pairs_are_immutable():
    t = GSP.tally_portfolio_records(seven_raw_records(), keep_blank=False)
    with pytest.raises(FrozenInstanceError):
        t.kept = 99
    assert isinstance(t.dropped_by_reason, tuple) and isinstance(t.rows, tuple)
    t.dropped["blank_value"] = 123                            # 動副本不影響本體
    assert t.dropped["blank_value"] == 2
    import pickle
    assert pickle.loads(pickle.dumps(t)) == t                 # st.cache_data 需可 pickle


def test_tally_does_not_mutate_input_and_is_deterministic():
    recs = seven_raw_records()
    a = GSP.tally_portfolio_records(recs, keep_blank=True)
    assert recs == seven_raw_records()
    assert a == GSP.tally_portfolio_records(recs, keep_blank=True)


# ═══ 9. 相容性：既有行為未動 ═════════════════════════════════════════════
def test_parse_and_editor_loaded_row_behavior_unchanged():
    assert GSP.parse_portfolio_records(seven_raw_records()) == [{"ticker": "2330", "lots": 2.0, "avg_price": 100.0}]
    assert len(GSP.parse_portfolio_records(seven_raw_records(), keep_blank=True)) == 3
    # _editor_loaded_row 真值表（逐列判準＝預設模式 parse）
    h = list(H)
    table = (
        (["核心", "2330", "2", "100", "t"], True),
        (["核心", "2330", "1,050", "100", "t"], True),
        (["核心", "2330", "", "100", "t"], False),
        (["核心", "2330", "0", "100", "t"], False),
        (["核心", "2330", "abc", "100", "t"], False),
        (["核心", "", "2", "100", "t"], False),
        (["別組", "2330", "2", "100", "t"], False),
        (["核心", "2330", "nan", "100", "t"], True),       # 現況：NaN 通過（本批只揭露、不改）
        (["", "", "", "", ""], False),
    )
    for row, exp in table:
        assert GSP._editor_loaded_row(h, row, "核心") is exp, row


def test_zero_production_callers_ast_guard():
    names = {"tally_portfolio_records", "load_portfolio_tallied", "PortfolioReadTally",
             "_load_portfolio_tallied_cached", "_load_portfolio_tallied_raw", "_load_portfolio_tallied_rows"}
    files = [REPO / "app.py", *sorted(REPO.glob("app_*.py")), *sorted((REPO / "src").rglob("*.py")),
             *sorted((REPO / "scripts").rglob("*.py")), *sorted((REPO / "shared").rglob("*.py")),
             *sorted((REPO / "infra").rglob("*.py"))]
    files += sorted((REPO / "mcp_server").rglob("*.py")) if (REPO / "mcp_server").exists() else []
    hits = set()
    for f in files:
        if f.resolve() == GSP_PATH or not f.exists():
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            ref = (n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute)
                   else [a.name for a in n.names] if isinstance(n, ast.ImportFrom) else None)
            if ref is None:
                continue
            if (isinstance(ref, list) and names & set(ref)) or (isinstance(ref, str) and ref in names):
                hits.add(str(f.relative_to(REPO)))
    assert hits == set(), f"新 API 目前必須 0 production caller：{sorted(hits)}"


def test_existing_b10_string_pins_still_hold():
    src = GSP_PATH.read_text(encoding="utf-8")
    assert src.count("        return parse_portfolio_records(recs, keep_blank=True)\n") == 1
    assert src.count("    if _is_blank_cell(value):\n        return None\n") == 1


def test_tally_text_is_not_a_verbatim_copy_of_pinned_readers():
    """新碼不得逐字複製 `_all_records` / `_load_portfolio_rows`（既有測試以 count==1 釘字串）。"""
    src = GSP_PATH.read_text(encoding="utf-8")
    assert src.count("    return [_sheet_record(values[0], r) for r in values[1:]]") == 1
    assert src.count("recs = [r for r in _all_records(sheet_id=sheet_id)") == 1


def test_new_cache_is_registered_in_clear_read_cache():
    import inspect
    assert "_load_portfolio_tallied_cached" in inspect.getsource(GSP.clear_read_cache)


# ═══ 10. 突變：拔掉／換掉判定邏輯必須轉紅（先證明 harness 對原版是綠的）═══════════
def test_mutation_baseline_original_is_green():
    assert _violations(GSP) == []


def test_mutation_neg_inf_reclassified_as_non_positive_turns_red():
    m = _mutant(("    if _v == -math.inf:\n        return _CELL_NEG_INF\n",
                 "    if False:\n        return _CELL_NEG_INF\n"))
    v = _violations(m)
    assert v and any("順序表" in x for x in v)


def test_mutation_swapped_blank_and_non_positive_order_turns_red():
    m = _mutant(("    if _CELL_NON_POSITIVE in _cells:\n        return False, DROP_NON_POSITIVE\n"
                 "    if _CELL_BLANK in _cells and not keep_blank:\n        return False, DROP_BLANK_VALUE\n",
                 "    if _CELL_BLANK in _cells and not keep_blank:\n        return False, DROP_BLANK_VALUE\n"
                 "    if _CELL_NON_POSITIVE in _cells:\n        return False, DROP_NON_POSITIVE\n"))
    v = _violations(m)
    assert v and any("順序表" in x for x in v)


def test_mutation_swapped_non_numeric_and_neg_inf_order_turns_red():
    m = _mutant(("    if _CELL_NON_NUMERIC in _cells:\n        return False, DROP_NON_NUMERIC\n"
                 "    if _CELL_NEG_INF in _cells:\n        return False, DROP_NON_FINITE\n",
                 "    if _CELL_NEG_INF in _cells:\n        return False, DROP_NON_FINITE\n"
                 "    if _CELL_NON_NUMERIC in _cells:\n        return False, DROP_NON_NUMERIC\n"))
    assert any("順序表" in x for x in _violations(m))


def test_mutation_nan_filtered_out_diverges_from_parse_turns_red():
    m = _mutant(("    if math.isnan(_v):\n        return _CELL_NAN\n",
                 "    if math.isnan(_v):\n        return _CELL_NEG_INF\n"))
    v = _violations(m)
    assert v and any("raise" in x or "順序表" in x for x in v)


def test_mutation_removing_identity_check_is_detected():
    m = _mutant(("    if t.raw != t.kept + _dsum:\n        raise ValueError('tally 恆等式失敗:raw != kept + Σ dropped_by_reason')\n",
                 ""), ("            _dropped[_label] += 1\n", "            _dropped[DROP_BLANK_TICKER] += 1\n"))
    assert _violations(m)                                     # 原因混記 ⇒ 順序表／M 系列抓到
