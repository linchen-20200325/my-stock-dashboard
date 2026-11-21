"""C-OB-L1-DIGEST-ELIGIBILITY-HEADLESS-QA-1 — L1 持股計數 × Decision Digest 的 fail-closed 離線負測（tests-only）。

授權：Issue #1199 comment 7057338506（單一 tests-only PR）。
範圍：只新增本檔；不改任何 production code、既有測試或文件。全離線（socket 守衛）、合成資料、無時鐘
（`generated_at` 固定值）、不讀真實 Sheet。

⚠️ 現況：L1 `PortfolioReadTally` 可用，但 **Digest NOT READY** —— L1 tally 的 `rows` 沒有 `held` 欄位，
production 也沒有「tally.rows → Digest `holdings_rows`」的 adapter。**本檔不建立 adapter**：L1 與 Digest
兩側各自用既有公開純函式＋合成資料測，絕不在測試裡寫轉換膠水（那等於發明 production 不存在的路徑）。

本檔釘住的項目（標 `current_behavior` 者為現況快照、非規範；語意待裁示，不得被讀成「這是對的」）：
  (b)  Digest 層無法區分「未選定」與「空」：`holdings_rows=None` 與 `[]` 的規則式摘要逐字相同、不宣稱零持股；
       L1 側 not_selected 全部計數 None、不讀 Sheet。（v1 限制）
  (d)  無持股輸入時，即使站內列有行動碼且證據新鮮，Digest 不帶行動、摘要行動段只有「無法判定」類句子。
  (e1) held 但無鍵的同代號兩列不去重：`unkeyed_count`／coverage `unkeyed_held_count` 為 2（無 fail-loud 路徑）。
  (e2) current_behavior：持股列 NaN／+inf 張數在 Digest 與 coverage 完全不揭露（builder 不讀 lots）；
       揭露責任目前只在 L1 `kept_non_finite`（既有測試已釘，見報告）。
  (G3) current_behavior：選定組合名不存在 ⇒ status ok、raw 0、other_name_rows>0，可與空表區分（DEC-218 Q1 待裁示）。
  (G4) 未登入 fail-closed：`LoginRequiredError` 原樣上拋，不轉成 tally 狀態、不回任何計數 0。
(b)(d)(e1)(G4) 各附 monkeypatch 突變測試（teeth）：臨時改壞行為，核心斷言必須轉紅；不留任何 production 修改。

⚠️ 單組作者自測，未經獨立 QA。
"""
from __future__ import annotations

import json
import socket
from datetime import date, datetime, timezone

import pytest

import src.data.portfolio.gsheet_portfolio as GSP
import src.services.decision_digest_builder as B
from shared.decision_digest import Availability, HoldingKey, MissingReason
from shared.decision_digest_validator import SummaryState, assess_digest
from shared.freshness_policy import FreshnessStatus
from src.services.decision_digest_assembly import EvidenceInput, assemble_digest
from src.services.decision_digest_builder import SourceStamp, build_decision_digest
from src.services.decision_digest_summary import build_rule_summary

NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)      # 固定；本檔不呼叫時鐘
D = date(2026, 10, 26)
STATION_STAMP = SourceStamp("dividend_station_service", D)
NAN, INF = float("nan"), float("inf")
H = GSP._HEADERS

#: 「宣稱零持股／空倉」類字眼：(b) 的摘要不得出現任何一個（未選定 ≠ 空）。
ZERO_HOLDING_CLAIMS = ("0 檔", "0檔", "零檔", "無持股", "沒有持股", "空倉", "持股為零", "零持股", "持股 0")

#: 站內列的行動碼文字（合成）；(d) 斷言摘要中一個字都不能出現。
ACTION_TEXTS = {"0050": "🔴 汰弱：吃本金（合成）", "0056": "➕ 加碼（合成）", "00878": "⏸ 暫停加碼（合成）"}


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


# ── Digest 側合成輸入 ───────────────────────────────────────────────────────
def station_rows():
    codes = {"0050": "cut", "0056": "add", "00878": "pause_add"}
    return [{"代號": t, "held": True, "_action": c, "建議動作": ACTION_TEXTS[t], "_detail": {}}
            for t, c in codes.items()]


def keys_for(*tickers, pid="pf-A"):
    return {t: HoldingKey(pid, t) for t in tickers}


def fresh_station():
    return EvidenceInput(stamp=STATION_STAMP, freshness=FreshnessStatus.FRESH)


def _all_lines(summary) -> list[str]:
    return [ln for _sec, lines in summary.lines for ln in lines]


def _section(summary, name: str) -> tuple:
    return dict(summary.lines)[name]


# ── L1 側 fake worksheet（照 tests/test_onebrain_gx1_l1_tally.py 的 fake 模式自行複製，不 import 其私有 helper）──
class _FakeWS:
    def __init__(self, values):
        self.values, self.reads = values, 0

    def get_all_values(self):
        self.reads += 1
        return [list(r) for r in self.values]


def _sheet(*body):
    return [list(H), *[list(r) for r in body]]


def _install_sheet(monkeypatch, values) -> _FakeWS:
    ws = _FakeWS(values)
    monkeypatch.setattr(GSP, "_ws", lambda **_k: ws)
    monkeypatch.setattr(GSP, "_cache_identity", lambda: "")     # 無身分 ⇒ 不碰快取，直走 raw
    return ws


def _assert_all_counts_unknown(t) -> None:
    assert t.rows is None and t.dropped_by_reason is None and t.duplicate_tickers is None and t.dropped is None
    for f in GSP._TALLY_COUNT_FIELDS:
        assert getattr(t, f) is None, f"{f} 必須是 None（UNKNOWN），得到 {getattr(t, f)!r}"


# ═══ (b) 未選定 vs 空：Digest 層無法區分（v1 限制）════════════════════════════
def _check_none_vs_empty_summary_identical() -> None:
    d_none = build_decision_digest(generated_at=NOW, holdings_rows=None)
    d_empty = build_decision_digest(generated_at=NOW, holdings_rows=[])
    for d in (d_none, d_empty):
        assert d.holdings.availability is Availability.UNAVAILABLE
        assert d.holdings.missing_reason is MissingReason.NO_INPUT
        assert d.holdings.entries == () and d.holdings.unkeyed_count == 0
        assert assess_digest(d).state is not SummaryState.INVALID
    assert d_none.to_dict() == d_empty.to_dict(), "Digest 本身也無從區分 None 與 []"
    s_none, s_empty = build_rule_summary(d_none), build_rule_summary(d_empty)
    assert s_none.lines == s_empty.lines, "None 與 [] 的摘要必須逐字相同（v1 無法區分未選定與空）"
    text = "\n".join(_all_lines(s_empty))
    for w in ZERO_HOLDING_CLAIMS:
        assert w not in text, f"摘要不得宣稱零持股：{w!r}"
    # 持股兩段只說「資料不足，無法判定」
    for sec in ("buy_and_hold", "capital_gain"):
        assert all("無法判定" in ln for ln in _section(s_empty, sec))


def test_b_digest_cannot_tell_not_selected_from_empty_v1_limitation():
    """v1 限制：Digest 只有 `holdings_rows`，None（未選定／沒給）與 []（給了但空）產出同一份摘要，
    holdings 為 UNAVAILABLE、不出現「0 檔／無持股／空倉」。L1 not_selected 的計數為 None（見下一個測試），
    所以任何未來 adapter 都不得把 not_selected 映成 `[]` 再宣稱「空」。"""
    _check_none_vs_empty_summary_identical()


def _check_l1_not_selected(monkeypatch) -> None:
    def _no(**_k):
        raise AssertionError("not_selected 時不得讀 Sheet")
    monkeypatch.setattr(GSP, "_ws", _no)
    monkeypatch.setattr(GSP, "_open_spreadsheet", _no)
    monkeypatch.setattr(GSP, "_build_client", _no)
    for nm in ("", "   ", None):
        for kb in (False, True):
            t = GSP.load_portfolio_tallied(nm, sheet_id="S", keep_blank=kb)
            assert t.status == GSP.TALLY_NOT_SELECTED
            _assert_all_counts_unknown(t)


def test_b_l1_not_selected_all_counts_none_and_never_reads_sheet(monkeypatch):
    """補足既有 `test_not_selected_never_reads_sheet`（只斷言 raw／rows／dropped）：全部 11 個計數欄＋
    duplicate_tickers 皆為 None（UNKNOWN，⛔ 不是 0），兩種 keep_blank 模式皆然，且不建 client、不讀 Sheet。"""
    _check_l1_not_selected(monkeypatch)


def test_b_mutation_builder_distinguishes_empty_turns_red(monkeypatch):
    """突變：讓 builder 對 [] 給不同的缺值原因（模擬「把空當成另一種已知狀態」）→ 逐字相同的斷言必須轉紅。"""
    orig = B._holdings_and_actions

    def _mut(holdings_rows, holding_keys, station_rows, station_stamp):
        h, a = orig(holdings_rows, holding_keys, station_rows, station_stamp)
        if holdings_rows is not None and len(holdings_rows) == 0:
            h = B.HoldingsSection(availability=Availability.UNAVAILABLE, entries=(),
                                  missing_reason=MissingReason.NOT_APPLICABLE, unkeyed_count=0)
        return h, a
    monkeypatch.setattr(B, "_holdings_and_actions", _mut)
    with pytest.raises(AssertionError):
        _check_none_vs_empty_summary_identical()


def test_b_mutation_l1_not_selected_returns_zero_counts_turns_red(monkeypatch):
    """突變：not_selected 回「ok 且全 0」的 tally（把未選定說成空）→ 必須轉紅。"""
    monkeypatch.setattr(GSP, "_unknown_tally",
                        lambda status, keep_blank: GSP.tally_portfolio_records([], keep_blank=keep_blank))
    with pytest.raises(AssertionError):
        _check_l1_not_selected(monkeypatch)


# ═══ (d) 無持股輸入 ⇒ 摘要沒有任何行動句 ═══════════════════════════════════
def _check_no_holdings_no_action_text() -> None:
    for hr in (None, []):
        # builder 直呼（站內 stamp 齊）與 headless 組裝（站內證據 FRESH）兩條路徑都要守
        direct = build_decision_digest(generated_at=NOW, station_rows=station_rows(), station_stamp=STATION_STAMP,
                                       holdings_rows=hr, holding_keys=keys_for(*ACTION_TEXTS))   # 連鍵都給了
        for d in (direct, None):
            if d is None:
                a = assemble_digest(generated_at=NOW, station_rows=station_rows(), station_evidence=fresh_station(),
                                    holdings_rows=hr, holding_keys=keys_for(*ACTION_TEXTS))
                assert a.coverage.actions_shown == 0 and a.coverage.is_complete is False
                d = a.digest
            assert d.actions.items == (), f"holdings_rows={hr!r} 時不得有行動"
            assert d.actions.availability is Availability.UNAVAILABLE
            s = build_rule_summary(d)
            text = "\n".join(_all_lines(s))
            for t in ACTION_TEXTS.values():
                assert t not in text, f"摘要不得出現行動文字：{t!r}"
            acts = _section(s, "actions")
            assert acts and all("無法判定" in ln for ln in acts), acts


def test_d_no_holdings_input_means_no_action_sentence_even_with_fresh_station_actions():
    """站內列有 cut／add／pause_add、站內證據 FRESH、鍵也給了，但 `holdings_rows` 是 None 或 []：
    Digest `actions.items == ()`，規則式摘要行動段只有「資料不足／無法判定」類句子、不含任何 ActionRef 文字。
    （既有 `test_actions_unavailable_when_holdings_unavailable` 只釘 Digest 層；本測試補摘要文字層。）"""
    _check_no_holdings_no_action_text()


def test_d_mutation_builder_fabricates_holdings_from_keys_turns_red(monkeypatch):
    """突變：無持股時改由 holding_keys 「推出」持股（模擬發明 adapter）→ 行動會出現，必須轉紅。"""
    orig = B._holdings_and_actions

    def _mut(holdings_rows, holding_keys, station_rows, station_stamp):
        if not holdings_rows and holding_keys:
            holdings_rows = [{"ticker": t, "held": True} for t in holding_keys]
        return orig(holdings_rows, holding_keys, station_rows, station_stamp)
    monkeypatch.setattr(B, "_holdings_and_actions", _mut)
    with pytest.raises(AssertionError):
        _check_no_holdings_no_action_text()


# ═══ (e1) 無鍵重複代號不去重 ════════════════════════════════════════════════
def _check_unkeyed_duplicates_not_deduped() -> None:
    hr = [{"ticker": "2330", "held": True}, {"ticker": "2330", "held": True},
          {"ticker": "2330", "held": False}]                         # 非持有列不計
    d = build_decision_digest(generated_at=NOW, holdings_rows=hr, holding_keys=None)
    assert d.holdings.unkeyed_count == 2, d.holdings.unkeyed_count
    assert d.holdings.entries == ()
    a = assemble_digest(generated_at=NOW, station_rows=[], station_evidence=fresh_station(),
                        holdings_rows=hr, holding_keys=None)
    assert a.digest.holdings.unkeyed_count == 2
    assert a.coverage.unkeyed_held_count == 2
    assert a.coverage.is_complete is False
    plan = B.plan_action_selection(station_rows=[], station_stamp=STATION_STAMP, holdings_rows=hr)
    assert (plan.unkeyed_held_count, plan.holdings_not_held_rows, plan.holdings_rows_total) == (2, 1, 3)


def test_e1_unkeyed_duplicate_ticker_counted_twice_no_fail_loud_path():
    """held=True、無 HoldingKey 的同一代號兩列：`unkeyed_count`／coverage `unkeyed_held_count` 為 2（不是 1），
    不 raise（現況：無鍵重複沒有 fail-loud 路徑；有鍵重複才由契約 duplicate_holding_key 擋）。"""
    _check_unkeyed_duplicates_not_deduped()


def test_e1_mutation_dedupe_unkeyed_turns_red(monkeypatch):
    """突變：無鍵持股依代號去重 → 計數變 1，必須轉紅。"""
    def _mut(holdings_rows, holding_keys):
        keyed, seen = [], set()
        for row in holdings_rows:
            if not isinstance(row, dict) or not B._is_held(row):
                continue
            k = B._key_for(B._ticker_of(row), holding_keys)
            if k is None:
                seen.add(B._ticker_of(row))
            else:
                keyed.append(k)
        return keyed, len(seen)
    monkeypatch.setattr(B, "_keyed_holdings", _mut)
    with pytest.raises(AssertionError):
        _check_unkeyed_duplicates_not_deduped()


# ═══ (e2) current_behavior：NaN／+inf 張數在 Digest 不揭露 ══════════════════════
def _holding_rows(lots_a, lots_b):
    return [{"ticker": "0050", "held": True, "lots": lots_a, "avg_price": 100.0},
            {"ticker": "0056", "held": True, "lots": lots_b, "avg_price": 30.0}]


def test_e2_current_behavior_non_finite_lots_not_disclosed_by_digest_or_coverage():
    """current_behavior（非規範快照）：builder 不讀 `lots`，所以持股列的 NaN／+inf 張數與乾淨值產生
    **逐字相同**的 Digest、coverage 與摘要；coverage 沒有任何 lots／non_finite 欄位。
    揭露責任目前只在 L1 `PortfolioReadTally.kept_non_finite`（既有
    `test_onebrain_gx1_l1_tally.py::test_nan_and_pos_inf_are_kept_and_disclosed_not_filtered` 已釘）。
    此測試轉紅＝行為改變（可能是補上揭露），請同步更新本快照與裁示紀錄，不要直接改斷言讓它過。"""
    for keys in (keys_for("0050", "0056"), None):                   # 有鍵（帶行動）與無鍵兩種
        outs = []
        for la, lb in ((2, 1), (NAN, 1), (2, INF), (NAN, INF)):
            a = assemble_digest(generated_at=NOW, station_rows=station_rows()[:2],
                                station_evidence=fresh_station(), holdings_rows=_holding_rows(la, lb),
                                holding_keys=keys)
            outs.append((json.dumps(a.to_dict(), ensure_ascii=False, sort_keys=True),
                         build_rule_summary(a.digest).lines))
        assert all(o == outs[0] for o in outs[1:])
        cov_keys = json.loads(outs[0][0])["coverage"].keys()
        assert not any("finite" in k or "lots" in k or "nan" in k.lower() for k in cov_keys)
    # 有鍵的那組確實帶了行動（確認比較的不是兩份空殼）
    a = assemble_digest(generated_at=NOW, station_rows=station_rows()[:2], station_evidence=fresh_station(),
                        holdings_rows=_holding_rows(NAN, INF), holding_keys=keys_for("0050", "0056"))
    assert len(a.digest.actions.items) == 2


# ═══ (G3) current_behavior：選定組合名不存在 ════════════════════════════════════
def test_g3_current_behavior_selected_name_absent_is_ok_zero_raw_with_other_name_rows(monkeypatch):
    """current_behavior（語意待裁示：DEC-218 Q1）：Sheet 只有其他組合名的列時，`load_portfolio_tallied(name)`
    回 status ok、raw 0、kept 0、other_name_rows>0；與「空表」「只有表頭」可由 other_name_rows／sheet_data_rows 區分。
    ⛔ 本測試**不**斷言它代表「無持股」—— 名稱打錯／組合被改名與真的空倉在此都長這樣。"""
    ws = _install_sheet(monkeypatch, _sheet(["別組", "2603", "1", "1", "t"], ["別組", "2618", "2", "3", "t"]))
    t = GSP.load_portfolio_tallied("核心", sheet_id="S")
    assert ws.reads == 1
    assert (t.status, t.raw, t.kept, t.rows) == (GSP.READ_OK, 0, 0, ())
    assert (t.other_name_rows, t.sheet_data_rows, t.blank_rows, t.blank_name_rows) == (2, 2, 0, 0)
    assert t.duplicate_tickers == ()
    assert "2603" not in repr(t) and "別組" not in repr(t)              # 不洩漏其他組合內容

    for empty in ([], _sheet()):                                       # 空表／只有表頭
        _install_sheet(monkeypatch, empty)
        e = GSP.load_portfolio_tallied("核心", sheet_id="S")
        assert (e.status, e.raw, e.kept, e.other_name_rows, e.sheet_data_rows) == (GSP.READ_OK, 0, 0, 0, 0)
        assert (e.other_name_rows, e.sheet_data_rows) != (t.other_name_rows, t.sheet_data_rows)


# ═══ (G4) 未登入 fail-closed ══════════════════════════════════════════════════
def _check_login_required_propagates(monkeypatch) -> None:
    calls = []

    def _not_logged_in():
        calls.append(1)
        raise GSP.LoginRequiredError(GSP.LOGIN_REQUIRED_MSG)

    # (i) 注入點：_build_client 拋 LoginRequiredError，無身分 ⇒ 直走 raw
    monkeypatch.setattr(GSP, "_build_client", _not_logged_in)
    monkeypatch.setattr(GSP, "_cache_identity", lambda: "")
    for kb in (False, True):
        with pytest.raises(GSP.LoginRequiredError) as ei:
            GSP.load_portfolio_tallied("核心", sheet_id="S", keep_blank=kb)
        assert type(ei.value) is GSP.LoginRequiredError
    # (ii) 有身分 ⇒ 走 st.cache_data 包裝路徑：例外照樣上拋，且不被快取（第二次仍真的再試一次）
    monkeypatch.setattr(GSP, "_cache_identity", lambda: "fp-test-identity")
    n0 = len(calls)
    for _ in range(2):
        with pytest.raises(GSP.LoginRequiredError):
            GSP.load_portfolio_tallied("核心", sheet_id="S")
    assert len(calls) - n0 == 2, "LoginRequiredError 不得被快取成一份 tally"
    # (iii) 真實匿名路徑：沒有 OAuth token ⇒ 原本的 _build_client 就拋（不靠替身）
    monkeypatch.setattr(GSP, "_build_client", _ORIG_BUILD_CLIENT)
    monkeypatch.setattr(GSP, "_has_oauth_tokens", lambda: False)
    monkeypatch.setattr(GSP, "login_expired", lambda: False)
    monkeypatch.setattr(GSP, "_cache_identity", lambda: "")
    with pytest.raises(GSP.LoginRequiredError, match=GSP.LOGIN_REQUIRED_MSG):
        GSP.load_portfolio_tallied("核心", sheet_id="S")


_ORIG_BUILD_CLIENT = GSP._build_client


def test_g4_login_required_propagates_unchanged_never_becomes_tally(monkeypatch):
    """未登入：`load_portfolio_tallied` 必須原樣上拋 `LoginRequiredError`（型別不變），
    不得轉成任何 tally 狀態、不得回傳任何計數 0；有身分走快取包裝時例外也不入快取。"""
    _check_login_required_propagates(monkeypatch)


@pytest.mark.parametrize("swallow_as", ["unknown_status", "ok_zero"])
def test_g4_mutation_swallowing_login_error_turns_red(monkeypatch, swallow_as):
    """突變：`_read_status` 吞掉 LoginRequiredError（轉成未知狀態或 ok＋全 0）→ 必須轉紅。"""
    orig = GSP._read_status

    def _mut(fn, **kwargs):
        try:
            return orig(fn, **kwargs)
        except GSP.LoginRequiredError:
            if swallow_as == "ok_zero":
                return GSP.READ_OK, GSP.tally_portfolio_records([], keep_blank=kwargs.get("keep_blank", False))
            return GSP.READ_ERROR_LOGIN_REQUIRED, []
    monkeypatch.setattr(GSP, "_read_status", _mut)
    with pytest.raises(BaseException) as ei:
        _check_login_required_propagates(monkeypatch)
    assert isinstance(ei.value, (AssertionError, pytest.fail.Exception))


def test_mutation_harness_baselines_are_green(monkeypatch):
    """突變 harness 對原版必須是綠的（否則轉紅不代表抓到突變）。"""
    _check_none_vs_empty_summary_identical()
    _check_no_holdings_no_action_text()
    _check_unkeyed_duplicates_not_deduped()
    _check_login_required_propagates(monkeypatch)
