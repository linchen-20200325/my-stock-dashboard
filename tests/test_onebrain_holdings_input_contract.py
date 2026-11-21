"""C-OB-HOLDINGS-INPUT-CONTRACT-1 — OneBrain「持股讀取結果 → Digest 輸入」離線契約的合成驗收案例（tests-first）。

授權：Issue #1199 comment 7060205009（契約設計＋離線驗收案例；最多一支 Draft PR；不合併）。
契約文件：`docs/vnext/ONEBRAIN_HOLDINGS_INPUT_CONTRACT_2026-11-21.md`（下文「§A／§B／§C」指該文件章節）。

═══ 本檔是什麼／不是什麼 ═══════════════════════════════════════════════
- **是**：用既有公開純函式（L1 `tally_portfolio_records`／`load_portfolio_tallied`；L3 `build_decision_digest`／
  `plan_action_selection`／`assemble_digest`／`build_rule_summary`）驗證「**依契約餵入時**」Digest／coverage／摘要的結果。
- **不是 adapter**：本檔唯一的「L1 → Digest 輸入」對照是 `contract_expected_holdings_input`（**契約規格表**，只回傳
  「預期輸入類別」，不產生任何 holdings_rows）。合成 `holdings_rows` 一律依契約 §B3 **手寫**；⛔ 不寫 tally.rows → holdings_rows
  的通用轉換函式（那會發明一條 production 不存在的路徑）。
- 全離線（socket 守衛）、無時鐘（`generated_at` 固定）、不讀真實 Sheet／OAuth、不呼叫 AI Provider；只新增本檔，不改 production。

═══ 三類測試（不可混用；同 #1251 經驗）════════════════════════════════════
1. **規範**（`test_norm_*`）：契約條文；不得默認 v1 缺口，不得依賴 current_behavior 快照。
2. **現況≠契約**（`test_gap_*`）：`pytest.mark.xfail(strict=True)`；reason 引用契約條號。XPASS ＝ 缺口被改掉 ⇒
   升為正式斷言並同步契約文件（不是直接刪 xfail 了事）。
3. **current_behavior 快照**（名稱含 `current_behavior`）：§C 待決案例的**目前行為**，非規範；轉紅處置寫在各 docstring。
另有突變測試（`test_mutation_*`）：monkeypatch production 符號，確認規範測試會轉紅；monkeypatch 於測試結束自動還原。

⚠️ 作者自測；未經獨立 QA。L1 可用、**Digest NOT READY**。
"""
from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import socket
from datetime import date, datetime, timezone

import pytest

import src.data.portfolio.gsheet_portfolio as GSP
import src.services.decision_digest_assembly as ASM
import src.services.decision_digest_builder as B
from shared.allocation_decision import build_allocation_decision
from shared.decision_digest import Availability, HoldingKey
from shared.freshness_policy import FreshnessStatus
from shared.risk_cap_policy import RiskCapDisclosure
from src.services.decision_digest_assembly import EvidenceInput, assemble_digest
from src.services.decision_digest_builder import SourceStamp, build_decision_digest, plan_action_selection
from src.services.decision_digest_summary import build_rule_summary

THIS_FILE = pathlib.Path(__file__).resolve()
REPO = THIS_FILE.parents[1]
CONTRACT_DOC = REPO / "docs" / "vnext" / "ONEBRAIN_HOLDINGS_INPUT_CONTRACT_2026-11-21.md"

NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)   # 固定；本檔不呼叫時鐘
D = date(2026, 10, 26)
MACRO_STAMP = SourceStamp("macro_state.json", D)
STATION_STAMP = SourceStamp("dividend_station_service", D)
PID = "pf-selected"                                          # 選定的單一本組合（DEC-218 Q2=(a)）；合成不透明鍵
NAN, INF = float("nan"), float("inf")
H = GSP._HEADERS

#: 「宣稱零持股／空倉」類字眼：未知／未選定／讀取失敗的摘要不得出現任何一個（契約 §B1）。
ZERO_HOLDING_CLAIMS = ("0 檔", "0檔", "零檔", "無持股", "沒有持股", "空倉", "持股為零", "零持股", "持股 0")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """離線守衛：任何真實 socket 連線 ＝ 測試失敗。"""
    def _boom(*_a, **_k):
        raise AssertionError("測試不得連網")
    monkeypatch.setattr(socket.socket, "connect", _boom)


@pytest.fixture(autouse=True)
def _clean_read_cache():
    GSP.clear_read_cache()
    yield
    GSP.clear_read_cache()


# ══════════════════════════════════════════════════════════════════════
# 契約規格表（contract oracle）—— 測試專用參考對照
# ══════════════════════════════════════════════════════════════════════
EXPECT_NONE = "holdings_rows=None"                         # 未知：不得映成 []（§B1）
EXPECT_LIST = "holdings_rows=list"                         # 依 §B3 手寫的 list（每列一筆、held=True）
EXPECT_PENDING_RAW_ZERO = "pending:raw_zero(None|[])"      # §C 待決：選定組合 0 列（組合不存在／空表）

_TALLY_FIELDS = tuple(f.name for f in dataclasses.fields(GSP.PortfolioReadTally) if f.name not in ("status", "keep_blank"))


def contract_expected_holdings_input(source) -> str:
    """**契約規格表，非 production adapter；不得被 `src/`、`shared/`、`scripts/`、`app*.py` 引用**（本檔有守衛）。

    輸入：L1 `load_portfolio_tallied` 的結果（`PortfolioReadTally`）或它拋出的例外。
    輸出：「預期 Digest 輸入類別」字串（§A 對照表的第二欄），**只是類別，不產生任何 holdings_rows**。
    - 例外（`LoginRequiredError`、權限／網路等）→ L1 不產生 tally；若 L3 仍建 Digest，holdings 必為 None（§A 第 3 列）。
    - status 非 ok（not_selected／worksheet_missing／schema_mismatch／任何未知狀態）→ None（§B1）。
    - status ok 但 rows／任何計數為 None（計數未知）→ None（§B1，fail-closed）。
    - ok 且 raw == 0（組合不存在／空表）→ 待決（§C-1；候選 None 或 []，兩者都須滿足 §B1 的安全性質）。
    - 其餘（raw > 0，含 kept == 0、dropped > 0、重複、非有限值）→ list（依 §B3 手寫；揭露缺口見 §C）。
    """
    if isinstance(source, BaseException):
        return EXPECT_NONE
    if type(source) is not GSP.PortfolioReadTally:
        raise TypeError(f"契約規格表只接受 PortfolioReadTally 或例外：{type(source).__name__}")
    if source.status != GSP.READ_OK:
        return EXPECT_NONE
    if any(getattr(source, f) is None for f in _TALLY_FIELDS):
        return EXPECT_NONE
    if source.raw == 0:
        return EXPECT_PENDING_RAW_ZERO
    return EXPECT_LIST


# ── 合成輸入（Digest 側；依契約 §B3 手寫，不由 tally.rows 轉換）─────────────────────────
def held(*tickers) -> list:
    """§B3：選定組合 rows 一列一筆、held=True（明確 bool）。只帶 builder 會讀的欄位。"""
    return [{"ticker": t, "held": True} for t in tickers]


def keys_for(*tickers, pid=PID) -> dict:
    return {t: HoldingKey(pid, t) for t in tickers}


def station_for(*tickers, code="add") -> list:
    return [{"代號": t, "held": True, "_action": code, "建議動作": f"txt-{code}-{t}", "_detail": {}} for t in tickers]


def macro_state() -> dict:
    disc = RiskCapDisclosure(snapshot_ts="2026-10-26 18:30:00", not_evaluated=(), disabled=(), sahm_status=None)
    return {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5,
            "exposure_limit_pct": 60, "defense": False, "risk_cap_disclosure": disc}


def fresh(stamp: SourceStamp) -> EvidenceInput:
    return EvidenceInput(stamp=stamp, freshness=FreshnessStatus.FRESH)


def full_kwargs(holdings_rows, *, station_tickers=None, holding_keys=None) -> dict:
    """四段證據齊備的組裝參數（macro／站內皆 FRESH）。holdings_rows 由呼叫端依 §B3 手寫。"""
    m = macro_state()
    tickers = [r["ticker"] for r in holdings_rows] if holdings_rows else []
    st = station_tickers if station_tickers is not None else tickers
    return dict(generated_at=NOW, macro_state=m, macro_evidence=fresh(MACRO_STAMP),
                allocation=build_allocation_decision(m), station_rows=station_for(*st),
                station_evidence=fresh(STATION_STAMP), holdings_rows=holdings_rows,
                holding_keys=holding_keys if holding_keys is not None else keys_for(*tickers))


def _lines(digest) -> list:
    return [ln for _sec, lines in build_rule_summary(digest).lines for ln in lines]


def _section(digest, name) -> tuple:
    return dict(build_rule_summary(digest).lines)[name]


def _dump(a) -> str:
    return json.dumps(a.to_dict(), ensure_ascii=False, sort_keys=True)


# ── L1 側 fake worksheet（同 #1251 模式自行複製，不 import 他檔私有 helper）────────────
class _FakeWS:
    def __init__(self, values):
        self.values = values

    def get_all_values(self):
        return [list(r) for r in self.values]


def _sheet(*body):
    return [list(H), *[list(r) for r in body]]


def _install_sheet(monkeypatch, values) -> None:
    monkeypatch.setattr(GSP, "_ws", lambda **_k: _FakeWS(values))
    monkeypatch.setattr(GSP, "_cache_identity", lambda: "")      # 無身分 ⇒ 不碰快取，直走 raw


def _rec(ticker, lots=1, avg=10.0, name="核心") -> dict:
    return {"name": name, "ticker": ticker, "lots": lots, "avg_price": avg, "updated_at": "t"}


# ══════════════════════════════════════════════════════════════════════
# 規範（§B1）：未選定／讀取失敗／計數未知 ⇒ holdings_rows=None
# ══════════════════════════════════════════════════════════════════════
def _unknown_tallies(monkeypatch) -> dict:
    """以 L1 公開入口產出各種「未知」狀態的 tally（離線替身只替換 worksheet 層）。"""
    out = {"not_selected": GSP.load_portfolio_tallied("   ", sheet_id="S")}

    def _missing(**_k):
        raise GSP.SheetWorksheetMissingError(GSP._WORKSHEET_NAME)
    monkeypatch.setattr(GSP, "_ws", _missing)
    monkeypatch.setattr(GSP, "_cache_identity", lambda: "")
    out["worksheet_missing"] = GSP.load_portfolio_tallied("核心", sheet_id="S")
    _install_sheet(monkeypatch, [["名稱", "代號"], ["核心", "0050"]])
    out["schema_mismatch"] = GSP.load_portfolio_tallied("核心", sheet_id="S")
    out["ok_but_counts_unknown"] = GSP.PortfolioReadTally(status=GSP.READ_OK, keep_blank=False)
    return out


def _check_unknown_maps_to_none(monkeypatch) -> None:
    tallies = _unknown_tallies(monkeypatch)
    for label, t in tallies.items():
        got = contract_expected_holdings_input(t)
        assert got == EXPECT_NONE, f"規範 §B1：{label} 必須對應 holdings_rows=None（不得映成 []），得到 {got}"
        if label != "ok_but_counts_unknown":
            for f in _TALLY_FIELDS:
                assert getattr(t, f) is None, f"規範 §B1：{label} 的 L1 計數 {f} 必須是 None（未知不是 0）"
    assert contract_expected_holdings_input(GSP.LoginRequiredError(GSP.LOGIN_REQUIRED_MSG)) == EXPECT_NONE
    assert (tallies["not_selected"].status, tallies["worksheet_missing"].status, tallies["schema_mismatch"].status) \
        == (GSP.TALLY_NOT_SELECTED, GSP.READ_WORKSHEET_MISSING, GSP.READ_SCHEMA_MISMATCH), "規範 §B1：狀態分類"


def test_norm_unknown_l1_states_map_to_none_not_empty_list(monkeypatch):
    """§A 第 1、2、4 列＋§B1：not_selected／worksheet_missing／schema_mismatch／ok 但計數未知 ⇒ None；L1 計數全 None。"""
    _check_unknown_maps_to_none(monkeypatch)


def _check_none_input_is_unknown_everywhere() -> None:
    """§B1：holdings_rows=None 時 Digest／coverage／摘要皆為「未知」，且不宣稱零持股。"""
    variants = (dict(generated_at=NOW, holdings_rows=None),
                {**full_kwargs(held("0050", "0056")), "holdings_rows": None})
    for kw in variants:
        a = assemble_digest(**kw)
        d, c = a.digest, a.coverage
        assert d.holdings.availability is Availability.UNAVAILABLE, "規範 §B1：holdings 必須 UNAVAILABLE"
        assert d.holdings.entries == () and d.actions.items == (), "規範 §B1：未知時不得有持股 entry／行動"
        assert c.unkeyed_held_count is None, f"規範 §B1：coverage unkeyed_held_count 必須 None，得到 {c.unkeyed_held_count!r}"
        assert c.holdings_non_mapping_rows is None, "規範 §B1：coverage holdings_non_mapping_rows 必須 None"
        assert c.is_complete is False, "規範 §B1：未知時 is_complete 必須 False"
        text = "\n".join(_lines(d))
        for w in ZERO_HOLDING_CLAIMS:
            assert w not in text, f"規範 §B1：摘要不得宣稱零持股：{w!r}"
        for sec in ("buy_and_hold", "capital_gain", "actions"):
            ls = _section(d, sec)
            assert ls and all("無法判定" in x for x in ls), f"規範 §B1：{sec} 段須只說無法判定：{ls}"


def test_norm_none_input_digest_coverage_summary_all_unknown():
    """§B1：依契約餵 None（即使 macro／站內證據齊備、站內有行動）⇒ UNAVAILABLE、coverage 計數 None、
    is_complete False、摘要無零持股字樣且持股／行動段只說「無法判定」。"""
    _check_none_input_is_unknown_everywhere()


def test_norm_none_and_empty_list_are_distinguishable_in_coverage():
    """§B1 的理由：若 adapter 把未知映成 []，coverage 的 `unkeyed_held_count` 會由 None（未知）變成 0（已知）——
    故 [] 不是 None 的無害替代。本測試只確認兩者在 coverage 可區分（現況成立；adapter 不得破壞）。"""
    a_none = assemble_digest(generated_at=NOW, holdings_rows=None)
    a_empty = assemble_digest(generated_at=NOW, holdings_rows=[])
    assert (a_none.coverage.unkeyed_held_count, a_empty.coverage.unkeyed_held_count) == (None, 0)
    assert a_none.coverage.to_dict() != a_empty.coverage.to_dict()


def test_norm_pending_raw_zero_both_candidates_never_claim_zero_holdings():
    """§C-1 待決（組合不存在／空表）：不論日後裁示選 None 或 []，都必須滿足——holdings UNAVAILABLE、
    is_complete False、摘要不宣稱零持股。此處只驗兩個候選的**共同**安全性質，不替裁示選邊。"""
    for cand in (None, []):
        a = assemble_digest(**{**full_kwargs(held()), "holdings_rows": cand})
        assert a.digest.holdings.availability is Availability.UNAVAILABLE
        assert a.coverage.is_complete is False
        text = "\n".join(_lines(a.digest))
        assert not any(w in text for w in ZERO_HOLDING_CLAIMS), text


def test_norm_l1_login_required_never_becomes_a_tally(monkeypatch):
    """§A 第 3 列：未登入 ⇒ L1 原樣上拋 `LoginRequiredError`（不轉成 tally／0）；契約規格表對例外只給 None。"""
    def _not_logged_in():
        raise GSP.LoginRequiredError(GSP.LOGIN_REQUIRED_MSG)
    monkeypatch.setattr(GSP, "_build_client", _not_logged_in)
    monkeypatch.setattr(GSP, "_cache_identity", lambda: "")
    with pytest.raises(GSP.LoginRequiredError) as ei:
        GSP.load_portfolio_tallied("核心", sheet_id="S")
    assert type(ei.value) is GSP.LoginRequiredError
    assert contract_expected_holdings_input(ei.value) == EXPECT_NONE


# ══════════════════════════════════════════════════════════════════════
# 規範（§B2／§B3）：可評估持有列、無法評估列保留、held 來源
# ══════════════════════════════════════════════════════════════════════
def test_norm_ok_with_rows_maps_to_list_including_dropped_dup_nonfinite():
    """§A 第 7–11 列：ok 且 raw>0 ⇒ list（含 dropped>0、重複列、非有限值、全部被丟棄）；揭露缺口另見 §C。"""
    cases = {
        "clean": [_rec("0050"), _rec("0056")],
        "dropped": [_rec("0050"), _rec(""), _rec("0056", lots="abc")],
        "all_dropped": [_rec("", lots=1), _rec("0050", lots=0)],
        "duplicate": [_rec("2330"), _rec("2330", lots=2)],
        "non_finite": [_rec("0050", lots=NAN), _rec("0056", avg=INF)],
    }
    for label, recs in cases.items():
        t = GSP.tally_portfolio_records(recs, keep_blank=False)
        assert t.raw > 0
        assert contract_expected_holdings_input(t) == EXPECT_LIST, label
    assert GSP.tally_portfolio_records(cases["all_dropped"], keep_blank=False).kept == 0


def _check_one_row_one_entry() -> None:
    """§B3：每一列 held=True 的持有列恰好一筆——有鍵者一個 entry（輸入順序），無鍵者計入 unkeyed（不去重、不丟）。"""
    rows = held("0050", "0056", "9001", "9001")                           # 9001 無鍵且重複
    keys = keys_for("0050", "0056")
    d = build_decision_digest(generated_at=NOW, holdings_rows=rows, holding_keys=keys,
                              station_rows=station_for("0050", "0056"), station_stamp=STATION_STAMP)
    assert [e.key.symbol for e in d.holdings.entries] == ["0050", "0056"], "規範 §B3：有鍵列一列一個 entry、順序不變"
    assert d.holdings.unkeyed_count == 2, f"規範 §B2：無鍵持有列必須逐列保留為計數（不去重），得到 {d.holdings.unkeyed_count}"
    p = plan_action_selection(station_rows=station_for("0050", "0056"), station_stamp=STATION_STAMP,
                              holdings_rows=rows, holding_keys=keys)
    assert p.holdings_held_keyed_rows + p.unkeyed_held_count == len(rows), "規範 §B3：持有列分割必須恰好覆蓋每一列"
    assert (p.holdings_not_held_rows, p.holdings_non_mapping_rows) == (0, 0)


def test_norm_evaluable_rows_one_row_one_entry():
    _check_one_row_one_entry()


def _check_unevaluable_rows_retained() -> None:
    """§B2：有持有列但無法評估（無 HoldingKey）⇒ 部位保留為 `unkeyed_count`／`unkeyed_held_count`，
    coverage incomplete，摘要兩個持股段都揭露「缺少投資組合鍵」。"""
    a = assemble_digest(**full_kwargs(held("0050", "0056", "9001"), station_tickers=["0050", "0056"],
                                      holding_keys=keys_for("0050", "0056")))
    assert a.digest.holdings.unkeyed_count == 1, f"規範 §B2：無法評估列必須保留，得到 {a.digest.holdings.unkeyed_count}"
    assert a.coverage.unkeyed_held_count == 1, "規範 §B2：coverage 必須揭露無法評估列數"
    assert a.coverage.is_complete is False, "規範 §B2：有無法評估列時 is_complete 必須 False"
    assert a.digest.holdings.availability is Availability.PARTIAL
    for sec in ("buy_and_hold", "capital_gain"):
        assert any("缺少投資組合鍵" in x for x in _section(a.digest, sec)), f"規範 §B2：{sec} 段須揭露無鍵持股"


def test_norm_unevaluable_rows_retained_with_count():
    _check_unevaluable_rows_retained()


def _check_held_only_from_selected_rows() -> None:
    """§B3：held 只來自選定組合 rows；`holding_keys` 多給的代號（例：別本組合）不得變成持股或行動。"""
    keys = {**keys_for("0050", "0056"), "2603": HoldingKey("pf-other", "2603")}
    a = assemble_digest(**full_kwargs(held("0050", "0056"), station_tickers=["0050", "0056", "2603"],
                                      holding_keys=keys))
    syms = [e.key.symbol for e in a.digest.holdings.entries]
    assert syms == ["0050", "0056"], f"規範 §B3：持股不得由 holding_keys 推得，得到 {syms}"
    assert all(x.target.symbol != "2603" for x in a.digest.actions.items), "規範 §B3：別本組合代號不得出現行動"
    assert all(e.key.portfolio_id == PID for e in a.digest.holdings.entries), "規範 §B3：不跨組合"
    assert a.coverage.station_rows_unmatched == 1 and a.coverage.is_complete is False


def test_norm_held_only_from_selected_portfolio_rows_not_from_keys():
    _check_held_only_from_selected_rows()


@pytest.mark.parametrize("bad", ["True", 1, 1.0, "yes"])
def test_norm_held_must_be_explicit_bool(bad):
    """§B3：held 必須是明確 bool（不得由字串／數字等推測）；型別不對 ⇒ builder Fail Loud（TypeError）。"""
    with pytest.raises(TypeError):
        build_decision_digest(generated_at=NOW, holdings_rows=[{"ticker": "0050", "held": bad}])


# ══════════════════════════════════════════════════════════════════════
# 現況≠契約（xfail strict）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.xfail(strict=True, reason=(
    "契約 §B2（缺獨立應有母體）：DEC-218 Q2=(a) 的獨立 expected 未落地，L1 raw 與 rows 同源；依契約 coverage 必須 "
    "incomplete，但現行 coverage 無任何欄位承載『應有母體』或 L1 dropped，四段齊備時 is_complete=True。"
    "修法需 coverage／Digest schema 變更（另需放行；§D）。XPASS ⇒ 升為正式斷言並更新契約 §C-6。"))
@pytest.mark.parametrize("recs", [
    [_rec("0050"), _rec("0056")],                                   # L1 dropped == 0
    [_rec("0050"), _rec("0056"), _rec(""), _rec("00878", lots="abc")],   # L1 dropped == 2
], ids=["l1_clean", "l1_dropped_2"])
def test_gap_contract_fed_input_without_independent_universe_must_be_incomplete(recs):
    t = GSP.tally_portfolio_records(recs, keep_blank=False)
    assert contract_expected_holdings_input(t) == EXPECT_LIST and t.kept == 2
    a = assemble_digest(**full_kwargs(held("0050", "0056")))          # §B3 手寫：kept 兩列
    assert a.coverage.is_complete is False


@pytest.mark.xfail(strict=True, reason=(
    "契約 §B2（無法評估列須保留部位與原因）：現行只保留計數 unkeyed_count／unkeyed_held_count，"
    "部位（代號）與原因皆不在 Digest／coverage／摘要內。需 schema 變更（另需放行；§C-5）。"))
def test_gap_unevaluable_row_identity_and_reason_preserved():
    def run(tk):
        return assemble_digest(**full_kwargs(held("0050", tk), station_tickers=["0050"],
                                             holding_keys=keys_for("0050")))
    a1, a2 = run("9001"), run("9002")
    assert _dump(a1) != _dump(a2), "無法評估列的部位身分必須可區分"
    assert build_rule_summary(a1.digest).lines != build_rule_summary(a2.digest).lines


@pytest.mark.xfail(strict=True, reason=(
    "DEC-218 §一 第 5 點（來源無效值不得作為有效評分值、剔除須可回報；歸類已定＝EX，雙母體表 §2 同）＋契約 §C-4："
    "差距在 L1 現況仍把 NaN／+inf 保留於 rows（DEC-219 第 4 點），以一般持有列進 Digest，Digest／coverage／摘要與乾淨值"
    "逐字相同。NaN／+inf 過濾修補屬 DEC-219 HOLD 項的放行問題。"))
def test_gap_non_finite_source_value_disclosed_downstream():
    def run(lots):
        rows = [{"ticker": "0050", "held": True, "lots": lots, "avg_price": 10.0}, *held("0056")]
        return assemble_digest(**full_kwargs(rows))
    assert _dump(run(1)) != _dump(run(NAN))


@pytest.mark.xfail(strict=True, reason=(
    "DEC-218 第 5 點（重複代號須揭露列數與代號）＋契約 §C-3：無鍵重複列只計 2，與兩個不同代號逐字相同，"
    "coverage 無持有側重複欄位；聚合粒度（列 vs 部位）待技術契約＋客戶裁示。"))
def test_gap_duplicate_holding_rows_disclosed():
    def run(t1, t2):
        return assemble_digest(**full_kwargs(held("0050", t1, t2), station_tickers=["0050"],
                                             holding_keys=keys_for("0050")))
    assert _dump(run("2330", "2330")) != _dump(run("2330", "2331"))


# ══════════════════════════════════════════════════════════════════════
# current_behavior 快照（§C 待決案例的目前行為；非規範）
# ══════════════════════════════════════════════════════════════════════
def test_current_behavior_c1_raw_zero_is_ok_empty_for_absent_name_and_empty_sheet(monkeypatch):
    """§C-1 現況：選定組合名不存在／空表／只有表頭 ⇒ status ok、raw 0、rows ()；僅 other_name_rows 不同。
    L1 無法分辨「名稱打錯／改名」與「真的 0 列」。轉紅 ⇒ L1 行為改變：更新 §C-1 與本快照、記錄裁示，不得直接改斷言。"""
    _install_sheet(monkeypatch, _sheet(["別組", "2603", "1", "1", "t"]))
    absent = GSP.load_portfolio_tallied("核心", sheet_id="S")
    assert (absent.status, absent.raw, absent.rows, absent.other_name_rows) == (GSP.READ_OK, 0, (), 1)
    for vals in ([], _sheet()):
        _install_sheet(monkeypatch, vals)
        e = GSP.load_portfolio_tallied("核心", sheet_id="S")
        assert (e.status, e.raw, e.rows, e.other_name_rows) == (GSP.READ_OK, 0, (), 0)
    assert contract_expected_holdings_input(absent) == EXPECT_PENDING_RAW_ZERO


def test_current_behavior_c3_duplicates_l1_disclosed_digest_keyed_raises_unkeyed_counted():
    """§C-3 現況：L1 揭露 duplicate_tickers、rows 不去重；Digest 有鍵重複 ⇒ ValueError（duplicate_holding_key）；
    無鍵重複 ⇒ 計 2、摘要寫「另有 2 檔」（列數被說成檔數）。轉紅 ⇒ 更新 §C-3＋本快照（不得放寬 §B3 不去重）。"""
    t = GSP.tally_portfolio_records([_rec("2330"), _rec("2330", lots=2)], keep_blank=False)
    assert (t.duplicate_tickers, t.duplicate_source_rows, t.kept) == (("2330",), 2, 2)
    with pytest.raises(ValueError, match="duplicate_holding_key"):
        assemble_digest(**full_kwargs(held("2330", "2330")))
    a = assemble_digest(**full_kwargs(held("0050", "2330", "2330"), station_tickers=["0050"],
                                      holding_keys=keys_for("0050")))
    assert a.coverage.unkeyed_held_count == 2
    assert any("另有 2 檔" in x for x in _section(a.digest, "buy_and_hold"))


def test_current_behavior_c4_non_finite_kept_by_l1_and_invisible_to_digest():
    """§C-4 現況：L1 把 NaN／+inf 列留在 rows（kept_non_finite 揭露）；builder 不讀 lots，Digest 與乾淨值相同。
    轉紅 ⇒ 若是補上揭露，`test_gap_non_finite_...` 應同時 XPASS：兩者一起升級並更新 §C-4。"""
    t = GSP.tally_portfolio_records([_rec("0050", lots=NAN), _rec("0056", avg=INF)], keep_blank=False)
    assert (t.kept, t.kept_non_finite, sum(t.dropped.values())) == (2, 2, 0)
    rows_nan = [{"ticker": "0050", "held": True, "lots": NAN}, *held("0056")]
    assert _dump(assemble_digest(**full_kwargs(rows_nan))) == _dump(assemble_digest(**full_kwargs(held("0050", "0056"))))


def test_current_behavior_c8_blank_lots_dropped_by_default_and_unmarked_with_keep_blank():
    """§C-8 現況：張數空白的列——L1 預設模式丟棄（blank_value）；keep_blank=True 保留且 lots=None。
    但 builder 不讀 lots，保留下來的空白列進 Digest 後與乾淨列逐字相同（沒有 IN-U 標記）。
    DEC-218 第 1 點要求空白列為 IN-U（保留、未能評估），adapter 該用哪個模式、IN-U 如何標示＝待決。
    轉紅 ⇒ 更新 §C-8 與本快照。"""
    recs = [_rec("0050"), _rec("0056", lots="")]
    t0 = GSP.tally_portfolio_records(recs, keep_blank=False)
    t1 = GSP.tally_portfolio_records(recs, keep_blank=True)
    assert (t0.kept, t0.dropped["blank_value"]) == (1, 1)
    assert (t1.kept, t1.kept_with_missing_value) == (2, 1)
    rows_blank = [*held("0050"), {"ticker": "0056", "held": True, "lots": None}]
    assert _dump(assemble_digest(**full_kwargs(rows_blank))) == _dump(assemble_digest(**full_kwargs(held("0050", "0056"))))


def test_current_behavior_c7_held_missing_or_false_rows_silently_not_held():
    """§C-7 現況：holdings_rows 內 `held` 缺／None／False 的列被當成「非持有」，coverage 沒有對應欄位，
    四段齊備時 is_complete 仍為 True（部位無痕消失）。契約 §B3 下 adapter 不應產生這種列；是否改為揭露待裁示。
    轉紅 ⇒ 更新 §C-7 與本快照。"""
    for extra in ({"ticker": "2603"}, {"ticker": "2603", "held": None}, {"ticker": "2603", "held": False}):
        a = assemble_digest(**full_kwargs([*held("0050", "0056"), extra],
                                          station_tickers=["0050", "0056"], holding_keys=keys_for("0050", "0056")))
        assert a.coverage.is_complete is True
        assert "2603" not in _dump(a)


# ══════════════════════════════════════════════════════════════════════
# 突變（production 符號；確認規範測試會轉紅；monkeypatch 自動還原）
# ══════════════════════════════════════════════════════════════════════
def test_mutation_l1_unknown_tally_reports_ok_zero_turns_norm_red(monkeypatch):
    """突變 1：L1 `_unknown_tally` 把未知狀態回成「ok＋全 0」→ §B1 規範（未知 ⇒ None）必須轉紅。"""
    monkeypatch.setattr(GSP, "_unknown_tally",
                        lambda status, keep_blank: GSP.tally_portfolio_records([], keep_blank=keep_blank))
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_unknown_maps_to_none(monkeypatch)


def test_mutation_plan_reports_zero_unkeyed_for_none_turns_norm_red(monkeypatch):
    """突變 2：組裝所用的 `plan_action_selection` 對 holdings_rows=None 回報 unkeyed／non_mapping＝0（把未知說成已知 0）
    → §B1 規範必須轉紅。"""
    orig = ASM.plan_action_selection

    def _mut(**kw):
        p = orig(**kw)
        if kw.get("holdings_rows") is None:
            p = dataclasses.replace(p, unkeyed_held_count=0, holdings_non_mapping_rows=0)
        return p
    monkeypatch.setattr(ASM, "plan_action_selection", _mut)
    with pytest.raises(AssertionError, match="規範 §B1"):
        _check_none_input_is_unknown_everywhere()


def test_mutation_builder_drops_unkeyed_rows_turns_norm_red(monkeypatch):
    """突變 3：builder `_keyed_holdings` 靜默丟掉無鍵持有列（unkeyed 回 0）→ §B2 保留規範必須轉紅。"""
    orig = B._keyed_holdings
    monkeypatch.setattr(B, "_keyed_holdings", lambda rows, keys: (orig(rows, keys)[0], 0))
    with pytest.raises(AssertionError, match="規範 §B2"):
        _check_unevaluable_rows_retained()
    with pytest.raises(AssertionError, match="規範 §B"):
        _check_one_row_one_entry()


def test_mutation_builder_infers_holdings_from_keys_turns_norm_red(monkeypatch):
    """突變 4：builder `_keyed_holdings` 由 holding_keys 補出 rows 沒有的持股 → §B3 held 來源規範必須轉紅。"""
    orig = B._keyed_holdings

    def _mut(rows, keys):
        ks, n = orig(rows, keys)
        have = {k.symbol for k in ks}
        return [*ks, *[k for t, k in (keys or {}).items() if t not in have]], n
    monkeypatch.setattr(B, "_keyed_holdings", _mut)
    with pytest.raises(AssertionError, match="規範 §B3"):
        _check_held_only_from_selected_rows()


def test_mutation_harness_baselines_are_green(monkeypatch):
    """突變 harness 對原版必須是綠的（否則轉紅不代表抓到突變）。"""
    _check_unknown_maps_to_none(monkeypatch)
    _check_none_input_is_unknown_everywhere()
    _check_one_row_one_entry()
    _check_unevaluable_rows_retained()
    _check_held_only_from_selected_rows()


# ══════════════════════════════════════════════════════════════════════
# 邊界守衛
# ══════════════════════════════════════════════════════════════════════
_SKIP_DIRS = {"tests", ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "data_cache"}


def _non_test_py_files() -> list:
    """repo 內所有不在 tests/ 下的 .py（含 src／shared／scripts／mcp_server／tools／infra／根目錄）。"""
    out = []
    for p in REPO.rglob("*.py"):
        rel = p.relative_to(REPO)
        if rel.parts and rel.parts[0] in _SKIP_DIRS or any(part in _SKIP_DIRS for part in rel.parts[:-1]):
            continue
        out.append(p)
    return out


def test_oracle_is_not_referenced_by_production():
    """契約規格表不得被 production 引用（它不是 adapter）。

    掃描 repo 內所有非 tests/ 的 .py：(1) AST 掃 import／from-import，模組名不得指向本測試模組，
    import 的名稱不得是 oracle；(2) 字串名比對（含註解、字串常數）。
    ⚠️ 據實限制：防不了動態拼接（`importlib.import_module("tests." + x)`、`getattr(mod, "contract_" + y)`）
    與 exec／eval；只擋直接引用。"""
    oracle, this_mod = "contract_expected_holdings_input", THIS_FILE.stem
    paths = _non_test_py_files()
    assert any(p.relative_to(REPO).parts[0] == "src" for p in paths)
    hits = []
    for p in paths:
        text = p.read_text(encoding="utf-8", errors="ignore")
        rel = str(p.relative_to(REPO))
        if oracle in text or this_mod in text:
            hits.append(f"{rel}: 字串命中")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            hits.append(f"{rel}: 無法解析（不得默默略過）")
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                hits += [f"{rel}: import {a.name}" for a in n.names if this_mod in a.name]
            elif isinstance(n, ast.ImportFrom):
                if n.module and this_mod in n.module:
                    hits.append(f"{rel}: from {n.module}")
                hits += [f"{rel}: import 名 {a.name}" for a in n.names if a.name in (oracle, this_mod)]
    assert hits == []


def test_this_file_is_offline_and_clockless_by_ast():
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    banned = {"streamlit", "requests", "urllib", "httpx", "gspread", "anthropic", "openai", "google"}
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            assert n.func.attr not in ("now", "today", "utcnow"), "本檔不得呼叫時鐘"
    assert not (mods & banned), mods & banned


def test_contract_doc_exists_and_names_each_section():
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    for needle in ("§A", "§B1", "§B2", "§B3", "§C-1", "§C-3", "§C-4", "§C-5", "§C-6", "§C-7", "§C-10", "§D",
                   "NOT READY", "DEC-218", "contract_expected_holdings_input"):
        assert needle in text, needle
