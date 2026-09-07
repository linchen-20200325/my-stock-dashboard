"""tests/test_p03_inspect_view.py — FE-10 的頁 3 守衛（IA v2「🔬 查一檔」）。

守的是 `src/ui/views/page_inspect.py`。風格與粒度沿用
`tests/test_p02_find_view.py`：**一條測試對應一個具體的說謊方式**，
不是補覆蓋率。對應表：

  · `TestFourEmptiesNeverMix`     ← 本頁的狀態比前兩頁多**一種**：
    「還沒輸入」／「輸入了但查無此代碼」／「上游掛了」／**「判不出型別」**。
    線框葉1-C 的原文是「**第三條路 · 不是紅態**」，note 還寫明
    「v1 只有『未輸入』灰態與『抓取失敗』紅態，`unknown` 無處可去 ——
    那會逼實作把它塞進其中一個，**兩個都是說謊**」。本類就是釘那件事。
  · `TestRequestedIsNotDerivedFromData` ← gate 從資料反推（頁 1 的恆真式事故）。
    做法與頁 2 完全相同：**白名單 AST 斷言**（`requested=` 只准讀被宣告成
    gate 的識別字），不是一條越加越長的黑名單。
  · `TestNothingIsCalledBeforeYouAsk` ← 「沒按就不取數」只是 docstring 宣稱。
    把 L2/L3 全部下毒（毒藥**不繼承 `Exception`**，本頁的 try/except 吞不掉），
    再跑一次每一支 loader —— 碰到就當場紅。
  · `TestThreeBranchesOfClassification` ← 三分支判型（個股／ETF／unknown），
    以及**手動覆寫**（線框 F4，理由是 repo 已記錄的型別字面事故）。
  · `TestUnwiredStaysUnwired`     ← 未接線的四項被「按一次就變好」或三要素留空。
  · `TestMissingIsGreyNotRed`     ← 💰 獲利能力診斷的**缺值三律樣板**：
    缺值是灰的「資料缺漏」，**不是**紅的「辛苦生意」（線框點名要修的那一格）。
  · `TestBatchDoesNotVoidTheWholeRun` ← 線框葉2 err 原文：
    「其餘 2 檔照常顯示，**不整批作廢**」。
  · `TestFormStructure`           ← 線框 F11：form 內放 `st.button` 實跑即拋；
    一個 form 只准一顆 submit；6 個 MA checkbox 不得回到 `st.columns(6)`。
  · `test_page_mounts_clean`（slow）← 這一頁真的畫得出來，不是半截死頁。

⚠️ **這些是護欄，不是證明**（同 `tests/test_ui_state_model.py` /
`tests/test_p01_today_view.py` / `tests/test_p02_find_view.py` 的自陳）：
釘住的是「已知的那幾種說謊方式不會再回來」，**不是**「這一頁不會再說謊」。
全綠不等於合規。
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

from shared.station_specs import MISS_NOT_APPLICABLE
from shared.ui_state import (
    UI_EMPTY,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_UNWIRED,
)
from src.ui.tabs.tab_today import Note
from src.ui.views import page_inspect as P

_VIEW = pathlib.Path(P.__file__)


def _tree() -> ast.Module:
    return ast.parse(_VIEW.read_text(encoding="utf-8"))


def _req(**kw) -> P.InspectRequest:
    kw.setdefault("submitted", True)
    return P.InspectRequest(**kw)


def _verdict(ticker: str, **kw) -> P.KindVerdict:
    """真的走一次 `classify_kind()` —— 型別字串一律由 L2 SSOT 決定。

    刻意**不**在測試裡手寫 `kind="stock"`：那會讓測試自己變成第二份型別字面，
    對面改字串時測試照樣綠、畫面卻已經全部掉進 unknown 分支
    （線框 F4 引用的 `station_cards.py` 事故就是字面漂移）。
    """
    return P.classify_kind(_req(ticker=ticker, **kw))


def _note_triple(note: Note | None) -> tuple[str, str, str]:
    assert note is not None, "非 live 的卡一定要附三要素（鐵律 4）"
    return note.now, note.why, note.where


# ══════════════════════════════════════════════════════════════════
# 【1】四種「沒有結果」絕不可混（本頁比前兩頁多一種）
# ══════════════════════════════════════════════════════════════════
class TestFourEmptiesNeverMix:
    """還沒輸入 ／ 代碼欄空白 ／ 判不出型別 ／ 上游掛了 —— 四件不同的事。

    ⚠️ **最重要的一條是 unknown 不得是紅態**。線框特地為它補畫了一個 block
    （葉1-C），note 原文：「v1 的查一檔只有『未輸入』灰態與『抓取失敗』紅態，
    `unknown` 無處可去 —— 那會逼實作把它塞進其中一個，**兩個都是說謊**。」
    """

    def test_cold_start_is_idle(self):
        _card, _, _ = P.build_kind_card(
            P.classify_kind(P.InspectRequest(submitted=False)),
            P.InspectRequest(submitted=False))
        assert _card.state == UI_IDLE
        assert _card.value == "", "idle 不准帶結論文字"

    def test_unknown_is_grey_not_red(self):
        _v = _verdict("AAPL")
        assert _v.is_unknown and not _v.is_resolved
        _card, _, _ = P.build_kind_card(_v, _req(ticker="AAPL"))
        assert _card.state == UI_EMPTY, (
            f"判不出型別被畫成 {_card.state!r} —— "
            "線框葉1-C 明寫「第三條路 · 不是紅態」")
        assert _card.state != UI_FAILED

    def test_unknown_block_is_also_grey_and_not_unwired(self):
        """獨立的葉1-C 區塊同樣不准是紅、也不准是「未接線」。

        `unwired` 的語意是「這個功能沒接」；判型是接好的、而且正常運作，
        它只是誠實地說判不出來。兩者混用會讓使用者以為這是待開發功能。
        """
        _card, _facts, _ = P.build_unknown_card(_verdict("AAPL"))
        assert _card.state == UI_EMPTY
        assert _card.state not in (UI_FAILED, UI_UNWIRED)
        assert _facts, "unknown 卡也要讓人看見代碼與系統判型"

    def test_unknown_uses_the_l0_not_applicable_reason(self):
        """灰色不是靠本檔自己判，是靠 L0 的 `FAILED_REASONS` 不含這個原因。

        若有人把 reason 換成 `MISS_FETCH_FAILED`，L0 會**自動升紅** ——
        本條讓那個改動當場轉紅，而不是等使用者看到假故障。
        """
        _src = _VIEW.read_text(encoding="utf-8")
        assert "MISS_NOT_APPLICABLE" in _src
        from shared.ui_state import FAILED_REASONS
        assert MISS_NOT_APPLICABLE not in FAILED_REASONS, (
            "L0 把 n/a 升成 failed 了 —— 本頁的 unknown 分支會跟著變紅")

    def test_blank_ticker_is_not_cold_start(self):
        """「按了送出但沒填」是一個**有效的使用者行為**，不是冷啟動。"""
        _v = _verdict("")
        _card, _, _ = P.build_kind_card(_v, _req(ticker=""))
        assert _card.state == UI_EMPTY
        _now, _, _where = _note_triple(_card.note)
        assert _now == P.BLANK_TICKER_NOW
        assert _now != P.SINGLE_IDLE_NOW, "空代碼與冷啟動被畫成同一句話"
        assert _where != P.SINGLE_IDLE_WHERE

    def test_classifier_failure_is_the_only_red(self):
        _v = P.KindVerdict(requested=True, code="2330", error="RuntimeError('x')")
        _card, _, _ = P.build_kind_card(_v, _req(ticker="2330"))
        assert _card.state == UI_FAILED
        assert "RuntimeError" in _card.note.why

    def test_the_four_states_are_pairwise_distinct(self):
        _cases = {
            "cold": P.build_kind_card(
                P.classify_kind(P.InspectRequest(submitted=False)),
                P.InspectRequest(submitted=False))[0],
            "blank": P.build_kind_card(_verdict(""), _req(ticker=""))[0],
            "unknown": P.build_kind_card(_verdict("AAPL"),
                                         _req(ticker="AAPL"))[0],
            "failed": P.build_kind_card(
                P.KindVerdict(requested=True, code="2330", error="boom"),
                _req(ticker="2330"))[0],
        }
        _nows = {_k: _c.note.now for _k, _c in _cases.items()}
        assert len(set(_nows.values())) == 4, (
            f"四態有人共用了同一句話：{_nows}")
        _wheres = {_k: _c.note.where for _k, _c in _cases.items()}
        assert len(set(_wheres.values())) == 4, (
            f"四態的「去哪補」有人重複 —— 使用者會被指去做沒用的事：{_wheres}")

    def test_stock_score_missing_is_empty_not_failed(self):
        """L3 對個股是 best-effort：財報那一腿沒抓到 → 灰，不是紅、也不是 0 分。"""
        _card, _, _ = P.build_health_card(
            P.StockReadout(requested=True, score_pct=None))
        assert _card.state == UI_EMPTY
        _now, _why, _ = _note_triple(_card.note)
        assert "0" not in _card.value
        assert "有效的結果" in _why, "缺值必須明講它是有效結果，不是故障"

    def test_stock_score_zero_is_a_conclusion_not_a_gap(self):
        """0 分是一個結論（不是缺值）→ 它必須畫成 live，而不是被當成沒值。"""
        _card, _, _ = P.build_health_card(
            P.StockReadout(requested=True, score_pct=0.0, grade="D"))
        assert _card.state == UI_LIVE, (
            "0 分被當成缺值 —— 那會讓一家真的很爛的公司看起來像沒資料")


# ══════════════════════════════════════════════════════════════════
# 【2】gate 不得從資料反推（白名單 AST 斷言，做法同頁 2）
# ══════════════════════════════════════════════════════════════════
#: `requested=` **只准**讀這些識別字。它們全都是「使用者按過沒有」的事實。
#: ⚠️ 這是**白名單**，不是黑名單：任何沒被宣告成 gate 的東西出現在那裡就是紅燈，
#: 不必先想得到它的名字（頁 1 的恆真式 `(alloc is not None)` 就是想不到的那種）。
_GATE_ATTRS: frozenset[str] = frozenset({
    "requested", "submitted",
    # 容器名（讀的是它們的欄位，不是它們本身）
    "req", "verdict", "stock", "etf", "prof", "readout", "flow", "self",
})

#: 明確的結果資料名 —— 一個都不准出現在 `requested=` 裡（黑名單，第二道）。
_PAYLOAD_TOKENS: frozenset[str] = frozenset({
    "score_pct", "premium_pct", "annual_yield_pct", "peer_ranks", "cells",
    "rows", "has_rows", "has_value", "metrics", "df", "kind", "is_resolved",
    "is_stock", "is_etf", "is_unknown", "ticker", "tickers", "code",
    "len", "empty", "any", "all", "error",
})


def _leaf_names(node: ast.AST) -> set[str]:
    """運算式**實際讀出來的識別字**（容器名不算，讀的欄位才算）。

    - `verdict.requested`  → `{"requested"}`
    - `bool(x.requested and x.is_stock)` → `{"bool", "requested", "is_stock"}`
    - `not df.empty`       → `{"df", "empty"}`（`df` 是裸 Name，被當值用了）
    """
    _bases = {id(_n.value) for _n in ast.walk(node)
              if isinstance(_n, ast.Attribute)}
    _out: set[str] = set()
    for _n in ast.walk(node):
        if isinstance(_n, ast.Attribute):
            _out.add(_n.attr)
        elif isinstance(_n, ast.Name) and id(_n) not in _bases:
            _out.add(_n.id)
    return _out


def _classify_calls(tree: ast.Module):
    for _n in ast.walk(tree):
        if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                and _n.func.id == "classify_ui_state"):
            yield _n


def _requested_offences(tree: ast.Module) -> list[str]:
    """本檔用的**單一**判定入口（測試與自證共用，不是兩把尺）。"""
    _bad: list[str] = []
    for _call in _classify_calls(tree):
        _kw = {_k.arg: _k.value for _k in _call.keywords if _k.arg}
        if "requested" not in _kw:
            _bad.append(f"line {_call.lineno}: 沒有傳 requested=")
            continue
        _req_expr = _kw["requested"]
        _names = _leaf_names(_req_expr)
        # (a) 白名單：讀出來的欄位只准是 gate 欄位；容器名與布林轉換不算。
        _illegal = {_x for _x in _names
                    if _x not in _GATE_ATTRS and not _x.endswith("requested")
                    and not _x.endswith("submitted") and _x != "bool"}
        if _illegal:
            _bad.append(f"line {_call.lineno}: requested= 讀了非 gate 的東西 "
                        f"{sorted(_illegal)}")
        # (b) 黑名單：明確的結果資料名一個都不准出現。
        _payload = _names & _PAYLOAD_TOKENS
        if _payload:
            _bad.append(f"line {_call.lineno}: requested= 含結果資料名 "
                        f"{sorted(_payload)}")
        # (c) 舊護欄（`test_ui_state_model` 那條）也照跑一次：AST 不得相同。
        if "has_value" in _kw and ast.dump(_req_expr) == ast.dump(_kw["has_value"]):
            _bad.append(f"line {_call.lineno}: requested= 與 has_value= "
                        "是同一個運算式")
        # (d) 讀出來的欄位不得與 has_value= 的欄位重疊。
        if "has_value" in _kw:
            _overlap = (_names & _leaf_names(_kw["has_value"])) - {"bool"}
            if _overlap:
                _bad.append(f"line {_call.lineno}: requested= 與 has_value= "
                            f"讀同一個欄位 {sorted(_overlap)}")
    return _bad


class TestRequestedIsNotDerivedFromData:
    """L0 的鐵律：**`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**"""

    def test_there_are_calls_to_guard(self):
        _calls = list(_classify_calls(_tree()))
        assert len(_calls) >= 6, (
            f"頁 3 至少有 6 個判態點（判型 / unknown / 健康度 / 估值 / 籌碼 / "
            f"獲利能力 / ETF 三格 / 明細 / 批次），實際找到 {len(_calls)}")

    def test_every_call_passes_requested(self):
        for _call in _classify_calls(_tree()):
            assert any(_k.arg == "requested" for _k in _call.keywords), (
                f"{_VIEW.name}:{_call.lineno} 沒有傳 `requested=`")

    def test_no_call_derives_requested_from_result_data(self):
        _bad = _requested_offences(_tree())
        assert not _bad, (
            "`requested=` 從資料反推了（idle 只能由上游帶下來）：\n  "
            + "\n  ".join(_bad))

    def test_the_gate_keys_are_written_by_handlers_only(self):
        """gate 的兩個 session key **只有** submit handler 會寫。

        寫入點若多一個，「有沒有人叫過」就不再是事實，而是可以被別人偽造的值。
        """
        _writes: dict[str, list[str]] = {P.SS_APPLIED_TICKER: [],
                                         P.SS_APPLIED_BATCH: []}
        for _fn in ast.walk(_tree()):
            if not isinstance(_fn, ast.FunctionDef):
                continue
            for _s in ast.walk(_fn):
                if not (isinstance(_s, ast.Assign) and _s.targets
                        and isinstance(_s.targets[0], ast.Subscript)):
                    continue
                _sub = _s.targets[0]
                if not isinstance(_sub.slice, ast.Name):
                    continue
                for _key, _const in ((P.SS_APPLIED_TICKER, "SS_APPLIED_TICKER"),
                                     (P.SS_APPLIED_BATCH, "SS_APPLIED_BATCH")):
                    if _sub.slice.id == _const:
                        _writes[_key].append(_fn.name)
        assert _writes[P.SS_APPLIED_TICKER] == ["_render_ticker_form"], (
            f"葉1 gate 的寫入點變成 {_writes[P.SS_APPLIED_TICKER]}")
        assert _writes[P.SS_APPLIED_BATCH] == ["_render_batch_form"], (
            f"葉2 gate 的寫入點變成 {_writes[P.SS_APPLIED_BATCH]}")

    def test_reader_looks_at_key_existence_not_content(self):
        """`bool(ticker)` 分不出「還沒送出」與「送出了但沒填」→ 只准看 key 在不在。"""
        assert P.applied_inspect_request({}).submitted is False
        assert P.applied_inspect_request(
            {P.SS_APPLIED_TICKER: None}).submitted is True
        _r = P.applied_inspect_request({P.SS_APPLIED_TICKER: {"ticker": ""}})
        assert _r.submitted is True and _r.has_ticker is False, (
            "送出了但沒填 —— 這是有效行為，不得退化成冷啟動的 idle")
        assert P.applied_batch_request({}).submitted is False
        assert P.applied_batch_request(
            {P.SS_APPLIED_BATCH: {"raw": ""}}).submitted is True

    def test_a_result_with_data_but_no_gate_cannot_even_be_built(self):
        """**恆真式的直接反證**：這種卡在 L0 就**構造不出來**（§1 Fail Loud）。"""
        with pytest.raises(ValueError, match="requested=False"):
            P.build_health_card(P.StockReadout(requested=False, score_pct=78.0))

    def test_the_page_never_produces_that_contradiction_itself(self):
        """而本頁自己的 loader 走不到上面那個矛盾：沒按 → 什麼都不帶回來。"""
        _v = P.classify_kind(P.InspectRequest(submitted=False))
        assert (_v.requested, _v.kind, _v.is_resolved) == (False, "", False)
        assert P.load_stock_readout(_v).score_pct is None
        assert P.load_etf_readout(_v).premium_pct is None
        assert P.load_profitability(_v).cells == ()
        assert P.load_batch_rows(P.BatchRequest(submitted=False)).rows == ()
        _val = P.load_valuation(_v, P.load_stock_readout(_v))
        assert (_val.requested, _val.est_yield_pct) == (False, None)
        _chips = P.load_chips(_v, P.InspectRequest(submitted=False))
        assert (_chips.requested, _chips.concentration) == (False, None)


# ══════════════════════════════════════════════════════════════════
# 【3】沒按之前一行 L3 都不呼叫（下毒實測，不是讀 docstring）
# ══════════════════════════════════════════════════════════════════
class _L3Touched(BaseException):
    """毒藥。**刻意不繼承 `Exception`** —— 本頁每一支 loader 都是

    `except Exception`，繼承 `Exception` 的話會被吞成一則錯誤字串，
    測試照樣綠、而 L3 其實已經被呼叫過了。不繼承才穿得出來。
    """


class _PoisonModule:
    """任何屬性取用都當場引爆的假模組。"""

    def __init__(self, name: str) -> None:
        self.__name__ = name

    def __getattr__(self, item: str):
        raise _L3Touched(f"{self.__name__}.{item} 在 requested=False 時被碰到了")


#: 頁 3 檔頭「取數」表列出的全部下游（L2 兩支 ＋ L3 五支）。
#: ⚠️ 2026-09-07 FE-18 補上本批接線的三支（357 的 L2、配息的 L3、籌碼的 L3）——
#: **漏補的話那三支就沒有被下毒**，「沒按之前一行 L3 都不呼叫」這條守衛
#: 對它們形同虛設（測試照樣綠、而它們其實已經被呼叫過了）。
_DOWNSTREAM = (
    "src.compute.etf.asset_lag",
    "src.compute.strategy.v5_modules",
    "src.services.dividend_station_service",
    "src.services.stock_grp_service",
    "src.services.financial_health_engine",
    "src.services.valuation_service",
    "src.services.stock_chips_service",
)


@pytest.fixture()
def poisoned(monkeypatch):
    """把全部下游換成毒藥模組。碰到就 `_L3Touched`，穿過所有 try/except。"""
    for _m in _DOWNSTREAM:
        monkeypatch.setitem(sys.modules, _m, _PoisonModule(_m))
    return _DOWNSTREAM


class TestNothingIsCalledBeforeYouAsk:
    """檔頭宣稱「`requested=False` 時本檔一行 L3 都不呼叫」——

    在本條之前那是一句**沒有人驗過的自我宣稱**。idle 態的 Note 還把它
    寫給使用者看；宣稱與實作若不一致，那就是對使用者說謊（§1）。
    """

    def test_classifier_touches_nothing(self, poisoned):
        _v = P.classify_kind(P.InspectRequest(submitted=False))
        assert _v.requested is False and _v.error == ""

    def test_every_leaf1_loader_touches_nothing(self, poisoned):
        _v = P.KindVerdict(requested=False)
        _req = P.InspectRequest(submitted=False)
        assert P.load_stock_readout(_v).requested is False
        assert P.load_etf_readout(_v).requested is False
        assert P.load_profitability(_v).requested is False
        # 本批接上的兩支同樣受這一條管（FE-18）。
        assert P.load_valuation(_v, P.StockReadout(requested=False)
                                ).requested is False
        assert P.load_chips(_v, _req).requested is False

    def test_batch_loader_touches_nothing(self, poisoned):
        assert P.load_batch_rows(P.BatchRequest(submitted=False)).rows == ()

    def test_the_poison_really_would_have_fired(self, poisoned):
        """**反證**：同一組毒藥下，`requested=True` 一定炸。

        沒有這一條，上面三條可能只是因為毒藥根本沒裝上去而綠。
        """
        with pytest.raises(_L3Touched):
            P.classify_kind(_req(ticker="2330"))
        with pytest.raises(_L3Touched):
            P.load_batch_rows(P.BatchRequest(submitted=True,
                                             tickers=("2330",)))
        # 反證也要涵蓋本批新接的兩支，否則上面那兩行可能只是「毒藥沒裝上」而綠。
        _stock_v = P.KindVerdict(requested=True, code="2330", kind="stock",
                                 is_stock=True)
        with pytest.raises(_L3Touched):
            P.load_valuation(_stock_v, P.StockReadout(requested=True,
                                                      price=100.0))
        with pytest.raises(_L3Touched):
            P.load_chips(_stock_v, _req(ticker="2330"))

    def test_idle_note_promise_matches_the_code(self):
        """畫給使用者看的那句承諾，與上面實測到的行為必須是同一件事。"""
        assert "一次 L3 取數都不會發" in P.SINGLE_IDLE_WHY
        assert "一次 L3 取數都不會發" in P.BATCH_IDLE_WHY


# ══════════════════════════════════════════════════════════════════
# 【4】三分支判型 ＋ 手動覆寫（線框 F4）
# ══════════════════════════════════════════════════════════════════
class TestThreeBranchesOfClassification:
    """線框葉1 的 job 原文：「系統判型，然後走**兩套完全不同的**明細」。

    ⚠️ 測試裡**刻意不手寫型別字串**（`kind == "stock"`）—— 那會讓測試自己
    變成第二份型別字面，對面改字串時測試照樣綠、畫面卻已經全部掉進 unknown。
    一律走 `classify_kind()` 回來的三個布林旗標。
    """

    @pytest.mark.parametrize("code", ["2330", "6488", "1101", "2317"])
    def test_stock_codes_go_to_branch_a(self, code):
        _v = _verdict(code)
        assert (_v.is_stock, _v.is_etf, _v.is_unknown) == (True, False, False)
        assert _v.benchmark, "個股要有比較基準"

    @pytest.mark.parametrize("code", ["0050", "00878", "00980A"])
    def test_etf_codes_go_to_branch_b(self, code):
        _v = _verdict(code)
        assert (_v.is_stock, _v.is_etf, _v.is_unknown) == (False, True, False)
        assert _v.benchmark

    @pytest.mark.parametrize("code", ["AAPL", "^TWII", "ABC", "TSLA"])
    def test_non_tw_codes_go_to_branch_c_and_are_not_red(self, code):
        _v = _verdict(code)
        assert (_v.is_stock, _v.is_etf, _v.is_unknown) == (False, False, True)
        assert _v.error == "", "判不出型別不是錯誤 —— 它是一個有效的答案"
        assert _v.benchmark is None, "判不出型別就沒有基準，不得硬給一個"
        _card, _, _ = P.build_kind_card(_v, _req(ticker=code))
        assert _card.state != UI_FAILED

    def test_the_three_branches_are_mutually_exclusive(self):
        for _code in ("2330", "00878", "AAPL"):
            _v = _verdict(_code)
            assert sum((_v.is_stock, _v.is_etf, _v.is_unknown)) == 1, (
                f"{_code} 同時落在多於一個分支")

    def test_manual_override_wins_and_is_visible(self):
        """線框 F4：判型結果**就地顯示且可手動覆寫**，兩列並陳。

        理由是 repo 已記錄的同型事故（`station_cards.py`：型別大小寫打錯一個
        字母 → 可信度虛高到 100% 並打開巡航 gate）。使用者必須看得到
        **系統判成什麼**，才知道自己在覆寫什麼。
        """
        _v = _verdict("AAPL", kind_choice=P.KIND_CHOICE_STOCK)
        assert _v.is_stock and _v.overridden
        assert _v.auto_kind != _v.kind, "覆寫時系統判型必須仍然保留"
        _card, _facts, _ = P.build_kind_card(_v, _req(ticker="AAPL"))
        _fields = {_k: _val for _k, _val in _facts}
        assert _fields["系統判型"] != _fields["這一輪採用"], (
            "覆寫了卻只顯示一列 —— 使用者看不到自己蓋掉了什麼")
        assert "覆寫" in _fields["判型來源"]

    def test_auto_choice_does_not_pretend_to_be_an_override(self):
        _v = _verdict("2330", kind_choice=P.KIND_CHOICE_AUTO)
        assert _v.overridden is False
        _, _facts, _ = P.build_kind_card(_v, _req(ticker="2330"))
        assert "覆寫" not in dict(_facts)["判型來源"]

    def test_override_to_the_same_kind_is_not_an_override(self):
        """把個股手動指定成個股 —— 沒有蓋掉任何東西，不該說成覆寫。"""
        _v = _verdict("2330", kind_choice=P.KIND_CHOICE_STOCK)
        assert _v.is_stock and _v.overridden is False

    def test_unknown_kind_string_is_not_treated_as_a_value(self):
        """`is_resolved` 不得寫成 `bool(kind)` —— unknown 也是非空字串。"""
        _v = _verdict("AAPL")
        assert _v.kind, "unknown 本身是一個非空的型別字串"
        assert _v.is_resolved is False, (
            "`bool(kind)` 恆真式回來了 —— 判不出來會被畫成綠燈")

    def test_ticker_is_not_silently_normalised_with_a_suffix(self):
        """代碼只做 strip + upper。補 `.TW` 是取數端的規則，抄一份就是第二個 SSOT。"""
        _r = P.applied_inspect_request(
            {P.SS_APPLIED_TICKER: {"ticker": "  2330  "}})
        assert _r.ticker == "2330"
        assert ".TW" not in _r.ticker


# ══════════════════════════════════════════════════════════════════
# 【5】未接線的四項永遠是 unwired（按幾次都一樣）
# ══════════════════════════════════════════════════════════════════
def _facts_nonempty(facts) -> bool:
    return bool(facts) and all(_k and _v for _k, _v in facts)


class TestUnwiredStaysUnwired:
    """檔頭誠實揭露的**兩項**：個股明細／ETF 明細。

    ⚠️ **2026-09-07 FE-18：估值（357）與籌碼已接線，從本類移走。**
    這**不是**放寬斷言 —— 它們接上之後就**不該**再是 `unwired`
    （`unwired` 的語意是「這個功能沒接」，接了還標它才是說謊）。
    原本掛在它們身上的三條守衛各自有等效替身，不留缺口：
      · 「按幾次都一樣」→ `TestWiredCellsAreNotUnwiredAnyMore`
        改釘「它們**永遠不是** `unwired`」（反向，射程同樣涵蓋誤標）；
      · 「三要素齊備」→ 同上類，對**每一種非 live 狀態**都驗一次
        （比原本只驗 `unwired` 一種**更寬**）；
      · 「沒有使用者出口」→ 改釘**相反的事實**：接上之後那兩格的
        `where` **不得**再帶 `NO_EXIT_MARKER`（留著就是說「沒有出口」，
        而其實重按有機會好）。
      · 「四項說法不得複製貼上」→ 仍在本類（明細兩張）＋ 新類（估值/籌碼）。

    ⚠️ 未接線的東西不會因為多按一次而改變，而「查不到」重按有機會好。
    畫成同一種灰＝把一個沒有出口的狀態說成有出口。
    """

    _BUILDERS = (
        ("個股明細", lambda r: P.build_detail_card(
            r, key="k", label="個股明細",
            sections=P.STOCK_DETAIL_SECTIONS, entry="🔬 個股分頁")),
        ("ETF 明細", lambda r: P.build_detail_card(
            r, key="k", label="ETF 明細",
            sections=P.ETF_DETAIL_SECTIONS, entry="🏦 ETF 分頁")),
    )

    @pytest.mark.parametrize("requested", [False, True])
    def test_all_stay_unwired_whatever_you_press(self, requested):
        for _name, _build in self._BUILDERS:
            _card, _, _ = _build(requested)
            assert _card.state == UI_UNWIRED, (
                f"{_name} 在 requested={requested} 時變成 {_card.state!r}")

    def test_each_has_all_three_elements(self):
        for _name, _build in self._BUILDERS:
            _card, _facts, _ = _build(True)
            _now, _why, _where = _note_triple(_card.note)
            assert _now.strip() and _why.strip() and _where.strip(), _name
            assert _facts_nonempty(_facts), f"{_name} 的 facts 有空格子"

    def test_each_says_there_is_no_user_action(self):
        """未接線的「去哪補」必須明講**沒有使用者可執行的出口**。

        寫成「請稍後再試」會讓人一直重按一個永遠不會變的東西。
        """
        from src.ui.tabs.tab_today import NO_EXIT_MARKER
        for _name, _build in self._BUILDERS:
            _card, _, _ = _build(True)
            assert NO_EXIT_MARKER in _card.note.where, _name

    def test_the_wheres_are_not_copy_pasted(self):
        """未接線與**已接線但缺料**的「去哪補」不得是同一句話。

        個股／ETF 明細共用同一段補法（兩者卡在同一件事：section 不能重複
        掛載），那是**事實**；但它們與估值／籌碼那兩種**必須**不同 ——
        一種沒有出口、另一種有。抄同一句話就是把兩件事講成一件。
        """
        _detail = self._BUILDERS[0][1](True)[0].note.where
        _val = P.build_valuation_card(_empty_valuation())[0].note.where
        _chips = P.build_chips_card(_missing_chips())[0].note.where
        assert len({_detail, _val, _chips}) == 3, (_detail, _val, _chips)

    def test_valuation_never_eats_etf_dividends(self):
        """擋住「拿 ETF 配息去餵個股 357」那條路。**接線之後這條更重要。**

        ⚠️ **原名 `test_valuation_never_gets_wired_by_accident` 已改名**
        （2026-09-07 FE-18）：357 這一格**已經接線**，「不得被接上」那個名字
        本身變成假的。**禁令一個字都沒有放寬** —— 改的只有名字，
        斷言與射程完全相同：本頁不得用那兩個 ETF 專用符號。
        接上的是**正確的來源**（L3 `valuation_service.get_stock_dividends`
        → L1 個股配息鏈），不是這條禁令的例外。

        ⚠️ 用 **AST**（真的被 import / 被呼叫的識別字）而不是**字串搜尋** ——
        檔頭的「為什麼不拿 ETF 配息」本來就必須寫出那兩個函式名才說得清楚，
        字串搜尋會把**誠實的揭露**判成違規，逼下一個人把理由刪掉。
        （頁 2 對估值 PE 因子是同一種拒絕；那裡的理由也寫在 docstring 裡。）
        """
        _banned = {"fetch_etf_dividends", "get_etf_dividends"}
        _used: set[str] = set()
        for _n in ast.walk(_tree()):
            if isinstance(_n, ast.Name) and _n.id in _banned:
                _used.add(_n.id)
            elif isinstance(_n, ast.Attribute) and _n.attr in _banned:
                _used.add(_n.attr)
            elif isinstance(_n, ast.ImportFrom):
                _used |= {_a.name for _a in _n.names} & _banned
        assert not _used, (
            f"本頁真的用了 {sorted(_used)} —— 拿 ETF 配息去餵個股 357 是"
            "替上游宣稱一件它沒說的事")

    def test_detail_cards_list_what_you_are_missing(self):
        """只寫「明細未接線」會讓人不知道自己少看了什麼。"""
        _card, _facts, _ = P.build_detail_card(
            True, key="k", label="個股明細",
            sections=P.STOCK_DETAIL_SECTIONS, entry="🔬 個股分頁")
        _listed = dict(_facts)["這一段本來會有"]
        for _sec in P.STOCK_DETAIL_SECTIONS:
            assert _sec in _listed, f"{_sec} 沒有列出來"

    def test_stock_and_etf_details_do_not_overlap(self):
        """線框紅隊註記：**與個股分支重疊近零** —— 合併的是入口與骨架，不是內容。"""
        assert not (set(P.STOCK_DETAIL_SECTIONS)
                    & set(P.ETF_DETAIL_SECTIONS)), (
            "兩支明細列出現共用項目 —— 線框實測是 0 命中")


# ══════════════════════════════════════════════════════════════════
# 【5b】本批接上的兩格（估值 357 / 籌碼）—— 它們**不再**是 unwired
# ══════════════════════════════════════════════════════════════════
def _empty_valuation() -> P.ValuationReadout:
    """「查得到、但三段備援都沒有配息紀錄」—— **有效結果**，不是故障。"""
    return P.ValuationReadout(requested=True, zone_code="na",
                              est_yield_pct=None, avg_div_twd=None,
                              paying_years=None, source="", years_n=0,
                              price=100.0,
                              msg="無配息記錄，357 殖利率法則不適用")


def _live_valuation() -> P.ValuationReadout:
    """真的算出一個位階（走 L2 的字面，本測試不自己編中文）。"""
    return P.ValuationReadout(
        requested=True, est_yield_pct=6.85, zone_code="fair",
        signal="🟡 合理（5~7%）", msg="殖利率 6.85%，位於合理區間（97.9~137.0）",
        avg_div_twd=6.85, paying_years=5, source="FinMind", years_n=5,
        price=100.0)


def _missing_chips() -> P.ChipsView:
    """「日線回來了，但法人欄全為 0」—— **資料缺漏**，不是故障。"""
    return P.ChipsView(requested=True, signal="⚫ 資料不足",
                       miss_reason="df法人欄全為0", rows=250, days_loaded=250)


def _live_chips() -> P.ChipsView:
    return P.ChipsView(requested=True, signal="🔥 大戶吸籌", concentration=6.32,
                       continuity=60.0, days=20, pos_days=12, rows=250,
                       days_loaded=250)


class TestWiredCellsAreNotUnwiredAnyMore:
    """估值（357）與籌碼**已接線** —— 它們**永遠不該**再判成 `unwired`。

    ⚠️ 這一類是 `TestUnwiredStaysUnwired` 對這兩格的**反向替身**，不是刪掉
    守衛：原本釘「它們恆為 unwired」，現在釘「它們**恆不是** unwired」。
    射程同樣涵蓋「有人把它標錯」這個失效模式，只是方向掉過來 ——
    接上之後還標 unwired，等於告訴使用者「這個功能沒接」，那是說謊。
    """

    _CASES = (
        ("估值·冷啟動", lambda: P.build_valuation_card(
            P.ValuationReadout(requested=False)), UI_IDLE),
        ("估值·沒有配息紀錄", lambda: P.build_valuation_card(
            _empty_valuation()), UI_EMPTY),
        ("估值·取數失敗", lambda: P.build_valuation_card(
            P.ValuationReadout(requested=True, error="RuntimeError('boom')")),
         UI_FAILED),
        ("估值·算出位階", lambda: P.build_valuation_card(_live_valuation()),
         UI_LIVE),
        ("籌碼·冷啟動", lambda: P.build_chips_card(
            P.ChipsView(requested=False)), UI_IDLE),
        ("籌碼·判不出來", lambda: P.build_chips_card(_missing_chips()),
         UI_EMPTY),
        ("籌碼·取數失敗", lambda: P.build_chips_card(
            P.ChipsView(requested=True, error="RuntimeError('boom')")),
         UI_FAILED),
        ("籌碼·判出來了", lambda: P.build_chips_card(_live_chips()), UI_LIVE),
    )

    @pytest.mark.parametrize("name,build,expect", _CASES)
    def test_state_is_what_it_should_be_and_never_unwired(self, name, build,
                                                          expect):
        _card, _, _ = build()
        assert _card.state != UI_UNWIRED, (
            f"{name} 仍被標成未接線 —— 它已經接上了，標 unwired 是說謊")
        assert _card.state == expect, f"{name} 判成 {_card.state!r}"

    @pytest.mark.parametrize("name,build,expect", _CASES)
    def test_every_non_live_state_has_all_three_elements(self, name, build,
                                                         expect):
        """鐵律 4 的射程**變寬了**：原本只驗 `unwired` 一種，現在四種都驗。"""
        _card, _facts, _ = build()
        if _card.state == UI_LIVE:
            return
        _now, _why, _where = _note_triple(_card.note)
        assert _now.strip() and _why.strip() and _where.strip(), name
        assert _facts_nonempty(_facts), f"{name} 的 facts 有空格子"

    def test_no_exit_marker_is_gone_from_the_wired_cells(self):
        """接上之後**不得**再說「沒有使用者出口」——重按真的有機會好。

        留著那句話，使用者會以為這一格永遠不會變而放棄；
        那與接線前把它標成「重試看看」是**同一種**說謊，只是方向相反。
        """
        from src.ui.tabs.tab_today import NO_EXIT_MARKER
        for _name, _build, _ in self._CASES:
            _card, _, _ = _build()
            if _card.note is None:
                continue
            assert NO_EXIT_MARKER not in _card.note.where, (
                f"{_name} 的「去哪補」仍宣稱沒有出口")

    def test_they_go_through_l3_only(self):
        """AST：本頁**沒有**任何 `src.data.*` import，也沒有走 L5 re-export 繞道。

        接線的正解是補 L3；經另一個 L5 檔 re-export **只是騙過靜態檢查、
        不改變性質**。這一條就是釘住「不准走那條捷徑」。
        """
        _mods: set[str] = set()
        for _n in ast.walk(_tree()):
            if isinstance(_n, ast.ImportFrom) and _n.module:
                _mods.add(_n.module)
            elif isinstance(_n, ast.Import):
                _mods |= {_a.name for _a in _n.names}
        _bad = {_m for _m in _mods
                if _m.startswith("src.data")
                or _m.startswith("src.ui.tabs.yield_screener")}
        assert not _bad, f"本頁直接 import 了 {sorted(_bad)} —— L5→L1 是分層違憲"
        assert "src.services.valuation_service" in _mods, (
            "357 的輸入沒有走本批新增的 L3")
        assert "src.services.stock_chips_service" in _mods, (
            "籌碼的 df 沒有走本批新增的 L3")


class TestValuation357IsHonest:
    """357 這一格最容易說的三種謊：0%、假紅燈、把「沒有配息」講成故障。"""

    def test_no_dividend_record_is_empty_not_failed(self):
        """**「查得到但沒有配息紀錄」是有效結果**，不是故障（灰，不是紅）。"""
        _card, _, _ = P.build_valuation_card(_empty_valuation())
        assert _card.state == UI_EMPTY

    def test_no_source_says_both_possibilities(self):
        """三段備援都沒給時，**兩種可能都要講** —— 上游分不出，本站不猜。"""
        _card, _, _ = P.build_valuation_card(_empty_valuation())
        _why = _card.note.why
        assert "真的沒有配息" in _why and "都沒拿到" in _why, _why

    def test_it_never_shows_zero_percent(self):
        """0% 會被同一套門檻判成「超貴」＝ 拿缺資料當看空結論。"""
        _card, _facts, _signal = P.build_valuation_card(_empty_valuation())
        assert _card.value == "", "非 live 不得帶結論文字"
        assert "0.00%" not in str(dict(_facts)), dict(_facts)
        assert _signal == "", "沒算出來就不該有訊號燈"

    def test_missing_inputs_show_a_dash_not_zero(self):
        """缺值顯示 `—`，**不是** 0 元 / 0 年（§1 不假報）。"""
        _, _facts, _ = P.build_valuation_card(_empty_valuation())
        _f = dict(_facts)
        assert _f["近 5 年平均年現金股利"].startswith("—")
        assert _f["近 5 年有配息年數"].startswith("—")
        # ⚠️ 不能只 grep `"0 年"`：正確的文案本來就會寫「不是 0 年」——
        # 那樣的 grep 會把**誠實的揭露**判成違規（同 AST 那條的教訓）。
        # 要釘的是「這一格沒有宣稱一個年數」，故改驗它明說「未知」。
        assert "未知" in _f["近 5 年有配息年數"]
        assert not _f["近 5 年有配息年數"].startswith("0")

    def test_live_shows_the_yield_and_a_chinese_only_signal(self):
        """鐵律 3：訊號頻道只出中文（帶 `🟡` 會被共用層當場 raise）。"""
        from src.ui.views._ui_kit import assert_signal_text_clean

        _card, _facts, _signal = P.build_valuation_card(_live_valuation())
        assert _card.state == UI_LIVE and "6.85" in _card.value
        assert _signal == "合理（5~7%）", _signal
        assert_signal_text_clean("valuation signal", _signal)

    def test_l2_message_is_passed_through_verbatim(self):
        """「是缺股價還是缺配息」由 L2 的 `msg` 說，本頁不改寫（§2.1）。"""
        _, _facts, _ = P.build_valuation_card(_live_valuation())
        assert dict(_facts)["L2 說明"] == _live_valuation().msg

    def test_failure_names_the_layer(self):
        """紅態要講出**是哪一層**出事，否則等於對使用者謊報出事的層。"""
        _card, _, _ = P.build_valuation_card(P.ValuationReadout(
            requested=True,
            error=P._error_why(P.SRC_DIVIDENDS, "RuntimeError('boom')")))
        assert _card.state == UI_FAILED
        assert "valuation_service" in _card.note.why
        assert "boom" in _card.note.why

    def test_a_value_without_a_gate_cannot_even_be_built(self):
        """恆真式的直接反證：沒被叫過卻有值 → L0 當場 `ValueError`。"""
        with pytest.raises(ValueError, match="requested=False"):
            P.build_valuation_card(P.ValuationReadout(
                requested=False, est_yield_pct=6.0, zone_code="fair"))

    def test_upstream_glyphs_do_not_blow_up_the_whole_page(self):
        """⭐ 上游訊息帶狀態 glyph → 要畫出**灰卡**，不是炸掉整頁。

        `Note.__post_init__` 拒收狀態 glyph，而卡片是在 `_render_one()` 的
        **保護圈外**建好的（`_render_stock_branch` 先組三張卡才畫）——
        不洗 glyph 就會是整頁未捕捉例外，而畫面上沒有任何一句話解釋。
        §1 要的是「狀態看得見」，**不是換一種炸法**。
        """
        # ⚠️ 這一組**刻意有 `source` 與配息紀錄**：沒有的話會走
        # `VALUATION_NO_SOURCE_WHY` 那條固定文案，`msg` 根本沒被用到，
        # 這條測試就會**在沒有驗到東西的情況下綠**（假綠燈）。
        # 這裡的情境是「配息查得到、但沒有現價」—— 那條路才會用 L2 的 `msg`。
        _card, _, _ = P.build_valuation_card(P.ValuationReadout(
            requested=True, zone_code="na", price=None,
            avg_div_twd=6.85, paying_years=5, source="FinMind", years_n=5,
            msg="🔴 無股價，357 殖利率法則不適用"))
        assert _card.state == UI_EMPTY
        assert "🔴" not in _card.note.why
        assert "無股價" in _card.note.why, "洗 glyph 不該把整句話洗掉"


class TestChipsIsHonest:
    """籌碼這一格最容易說的兩種謊：把缺漏畫成紅色、把缺值寫成 0% 集中度。"""

    def test_missing_inst_columns_is_grey_not_red(self):
        """日線回來了、法人欄沒有 → **資料缺漏**（灰），不是故障（紅）。"""
        _card, _, _ = P.build_chips_card(_missing_chips())
        assert _card.state == UI_EMPTY
        assert "資料缺漏" in _card.note.why or "不是這一檔籌碼不好" in _card.note.why

    def test_the_upstream_reason_is_shown_verbatim(self):
        """L0 給的原因原文要看得見，否則使用者不知道缺的是哪一腿。"""
        _card, _facts, _ = P.build_chips_card(_missing_chips())
        assert dict(_facts)["上游說明"] == "df法人欄全為0"
        assert "df法人欄全為0" in _card.note.why

    def test_it_never_shows_zero_concentration(self):
        """0% 集中度是「買賣超剛好抵銷」這個**結論**，不是缺值。"""
        _card, _facts, _signal = P.build_chips_card(_missing_chips())
        assert _card.value == ""
        assert "0%" not in str(dict(_facts))
        assert _signal == "", "判不出來就不該有訊號燈"

    def test_live_shows_concentration_and_a_chinese_only_signal(self):
        from src.ui.views._ui_kit import assert_signal_text_clean

        _card, _facts, _signal = P.build_chips_card(_live_chips())
        assert _card.state == UI_LIVE and "6.32" in _card.value
        assert _signal == "大戶吸籌", _signal
        assert_signal_text_clean("chips signal", _signal)
        assert "12 / 20 日" in dict(_facts)["連續性"]

    def test_a_red_signal_never_leaks_into_the_signal_channel(self):
        """L0 的「大戶倒貨」帶 `🔴` —— 那是**狀態 glyph**，混進來就是兩盞燈。"""
        from src.ui.views._ui_kit import assert_signal_text_clean

        _, _, _signal = P.build_chips_card(P.ChipsView(
            requested=True, signal="🔴 大戶倒貨", concentration=-8.1,
            continuity=20.0, days=20, pos_days=4, rows=250, days_loaded=250))
        assert _signal == "大戶倒貨"
        assert_signal_text_clean("chips signal", _signal)

    def test_the_judgement_window_is_not_the_form_period(self):
        """期間改了**不會**改變近 20 日的判讀窗 —— 卡上必須講清楚。

        講不清楚，使用者會以為把期間調成 500 就能看「近 500 日籌碼」。
        """
        _, _facts, _ = P.build_chips_card(_live_chips())
        _f = dict(_facts)
        assert "最近 20 個交易日" in _f["判讀窗"]
        assert "不隨表單的「期間」改變" in _f["判讀窗"]
        assert "250 個交易日的日線" in _f["本輪載入"]

    def test_failure_names_the_layer(self):
        _card, _, _ = P.build_chips_card(P.ChipsView(
            requested=True,
            error=P._error_why(P.SRC_CHIPS, "RuntimeError('boom')")))
        assert _card.state == UI_FAILED
        assert "stock_chips_service" in _card.note.why
        assert "boom" in _card.note.why

    def test_a_returned_error_string_is_not_called_an_exception(self, monkeypatch):
        """L1 的暫時性失敗是**回傳字串**，不是拋例外 —— 動詞要講對。

        寫「拋出例外」會讓下一個人去 traceback 裡找一個根本不存在的東西；
        那與把「還沒載入」畫成紅色是同一族的問題：敘述與事實不符。
        """
        from src.data.stock import app_stock_fetchers as A

        monkeypatch.setattr(A, "fetch_price_data",
                            lambda _s, _d: (None, None, "查無資料"),
                            raising=True)
        _v = _verdict("2330")
        _view = P.load_chips(_v, _req(ticker="2330"))
        assert "回報失敗" in _view.error and "拋出例外" not in _view.error, (
            _view.error)
        assert "查無資料" in _view.error

    def test_a_value_without_a_gate_cannot_even_be_built(self):
        with pytest.raises(ValueError, match="requested=False"):
            P.build_chips_card(P.ChipsView(requested=False,
                                           signal="🔥 大戶吸籌",
                                           concentration=6.3))

    def test_upstream_glyphs_do_not_blow_up_the_whole_page(self):
        """理由同估值那一條：灰卡要畫得出來，不是換一種炸法。"""
        _card, _, _ = P.build_chips_card(P.ChipsView(
            requested=True, signal="⚫ 資料不足",
            miss_reason="🔴 df法人欄全為0", rows=250, days_loaded=250))
        assert _card.state == UI_EMPTY
        assert "🔴" not in _card.note.why
        assert "df法人欄全為0" in _card.note.why


class TestTheTwoNewServicesKeepTheirPromises:
    """兩支新 L3 的契約 —— **不打網路**，把 L1 換成假的再驗形狀。

    ⚠️ 守的是「L1 的哨兵值有沒有被誠實翻譯」這一件事，不是覆蓋率：
    `fetch_dividend_data` 用 `0.0` 表示「什麼都沒找到」，原樣往上送就會
    變成「平均股利 0 元」這個**結論**。
    """

    @staticmethod
    def _patch_dividends(monkeypatch, avg, yearly, source):
        from src.data.stock import app_stock_fetchers as A

        monkeypatch.setattr(A, "fetch_dividend_data",
                            lambda _sid: (avg, yearly, source), raising=True)

    def test_zero_average_becomes_none_not_zero(self, monkeypatch):
        from src.services import valuation_service as V

        self._patch_dividends(monkeypatch, 0.0, [], "")
        _d = V.get_stock_dividends("2330")
        assert _d.avg_div_twd is None, "0.0 是哨兵值，不是「平均股利 0 元」"
        assert _d.paying_years is None, "沒有明細就是未知，不是 0 年"
        assert _d.source == "" and _d.has_record is False

    def test_real_record_is_carried_through(self, monkeypatch):
        from src.services import valuation_service as V

        self._patch_dividends(
            monkeypatch, 6.85,
            [{"year": 2021 + _i, "cash": 6.0 + _i} for _i in range(5)],
            "FinMind")
        _d = V.get_stock_dividends("2330")
        assert _d.avg_div_twd == 6.85 and _d.paying_years == 5
        assert _d.source == "FinMind" and len(_d.years) == 5

    def test_dividend_failure_is_not_swallowed(self, monkeypatch):
        """§1：L1 炸了就往上拋，**不回一份看起來很合理的空資料**。"""
        from src.data.stock import app_stock_fetchers as A
        from src.services import valuation_service as V

        def _boom(_sid):
            raise RuntimeError("finmind down")

        monkeypatch.setattr(A, "fetch_dividend_data", _boom, raising=True)
        with pytest.raises(RuntimeError, match="finmind down"):
            V.get_stock_dividends("2330")

    def test_chips_fetch_error_becomes_error_not_a_miss(self, monkeypatch):
        """L1 的 `err` 字串是**取數失敗**（紅），不得退化成「判不出來」（灰）。"""
        from src.data.stock import app_stock_fetchers as A
        from src.services import stock_chips_service as C

        monkeypatch.setattr(A, "fetch_price_data",
                            lambda _s, _d: (None, None, "查無資料"),
                            raising=True)
        _r = C.get_chips_readout("2330", days=250)
        assert _r.error == "查無資料" and _r.miss_reason == ""

    def test_chips_missing_columns_becomes_miss_not_error(self, monkeypatch):
        """反過來：df 回來了但欄位不足 ＝ **缺漏**（灰），不得升成紅。"""
        import pandas as pd

        from src.data.stock import app_stock_fetchers as A
        from src.services import stock_chips_service as C

        _df = pd.DataFrame({"close": [1.0] * 30, "volume": [10] * 30})
        monkeypatch.setattr(A, "fetch_price_data",
                            lambda _s, _d: (_df, "台積電", None), raising=True)
        _r = C.get_chips_readout("2330", days=250)
        assert _r.error == "" and _r.miss_reason, _r
        assert _r.concentration is None, "算不出來就是 None，不是 0"
        assert _r.rows == 30 and _r.name == "台積電"

    def test_chips_happy_path_uses_the_l0_verdict(self, monkeypatch):
        """判讀字面與門檻**由 L0 決定**，L3 只搬運（不重算、不改字）。"""
        import pandas as pd

        from shared.macro_compute import analyze_20d_chips_from_df
        from src.data.stock import app_stock_fetchers as A
        from src.services import stock_chips_service as C

        _df = pd.DataFrame({
            "外資": [500] * 30, "投信": [100] * 30, "volume": [5000] * 30})
        monkeypatch.setattr(A, "fetch_price_data",
                            lambda _s, _d: (_df, "X", None), raising=True)
        _r = C.get_chips_readout("2330", days=250)
        _expected = analyze_20d_chips_from_df(_df)
        assert _r.miss_reason == "" and _r.error == ""
        assert _r.signal == _expected["signal"]
        assert _r.concentration == _expected["concentration"]


# ══════════════════════════════════════════════════════════════════
# 【6】💰 獲利能力診斷：缺值是灰的，不是紅的（線框點名要修的那一格）
# ══════════════════════════════════════════════════════════════════
def _prof(**slots) -> P.ProfitabilityReadout:
    """組一份 L3 `profitability_module` 的回傳形狀，走真的 `_cell()` 判讀。"""
    _cells = (
        P._cell("gross_margin", "毛利率", slots.get("gm"),
                value_field="Value", status_field="Status",
                labels=P.GROSS_MARGIN_LABELS),
        P._cell("operating_margin", "營業利益率", slots.get("om"),
                value_field="Value", status_field="Core_Business_Profitable",
                labels=P.OPERATING_MARGIN_LABELS),
        P._cell("safety_margin", "安全邊際", slots.get("mos"),
                value_field="Value", status_field="Status",
                labels=P.SAFETY_MARGIN_LABELS),
    )
    return P.ProfitabilityReadout(requested=True, cells=_cells,
                                  upstream_note=slots.get("note", ""))


class TestMissingIsGreyNotRed:
    """線框原文：「**切到灰態看這一格：缺值是灰的「⚪ 資料缺漏」，

    不是紅的「辛苦生意」。**現行這組卡用 `== 'Good'` 布林判定，欄位取不到就
    落 else → 紅底 ＋ N/A ＋「辛苦生意」，**把「沒有資料」講成「這是爛生意」**。」
    """

    def test_all_three_missing_are_grey(self):
        for _card, _, _sig in P.build_profit_cards(_prof()):
            assert _card.state == UI_EMPTY, (
                f"{_card.label} 缺值被畫成 {_card.state!r}")
            assert _card.state != UI_FAILED
            assert _sig == "", "缺值不得帶任何結論標籤"

    def test_missing_note_says_it_is_not_a_bad_business(self):
        _card, _, _ = P.build_profit_cards(_prof())[0]
        _now, _why, _where = _note_triple(_card.note)
        assert "資料缺漏" in _now
        assert "不是" in _why and "生意" in _why, (
            "缺值的理由必須明講「這不是一個負面結論」")

    def test_na_value_is_treated_as_missing(self):
        """L3 對單位異常回 `Value='N/A (rev 單位異常)'` —— 那是缺值，不是結論。"""
        _cards = P.build_profit_cards(_prof(
            om={"Value": "N/A (rev 單位異常)",
                "Core_Business_Profitable": "N/A"}))
        assert _cards[1][0].state == UI_EMPTY

    def test_one_missing_does_not_grey_out_the_others(self):
        """線框 `errCells` 的形狀：毛利率⚪ / 營業利益率 42.1% / 安全邊際⚪。

        ⚠️ **粒度就是一張卡**：掛在區塊上會讓「只有一格缺」被另外兩格替它通過。
        """
        _cards = P.build_profit_cards(_prof(
            om={"Value": "42.1%", "Core_Business_Profitable": "Yes"}))
        _states = [_c.state for _c, _, _ in _cards]
        assert _states == [UI_EMPTY, UI_LIVE, UI_EMPTY], _states
        assert _cards[1][2] == "本業獲利", "有值的那一格要帶中文結論標籤"

    def test_a_value_with_an_unknown_verdict_still_shows_the_number(self):
        """L3 換了 Status 詞彙 = **契約漂移**，不是「沒有資料」。

        數字明明在手上卻畫成灰色的「資料缺漏」，是第二種說謊。
        正確處置：照實把數字畫出來、結論那一格**留白**
        （`_ui_kit.render_card()` 的契約：`signal_text` 空字串 = 沒有燈號頻道）。
        """
        _cards = P.build_profit_cards(_prof(
            gm={"Value": "58.2%", "Status": "SomethingNew"}))
        assert _cards[0][0].state == UI_LIVE, (
            "有數字卻被畫成缺值 —— 那是對使用者說謊")
        assert _cards[0][0].value == "58.2%"
        assert _cards[0][2] == "", (
            "對映表查不到卻硬給一個標籤 —— 那是替 L3 發明一個結論")

    def test_full_house_is_live_with_chinese_labels(self):
        _cards = P.build_profit_cards(_prof(
            gm={"Value": "58.2%", "Status": "Good"},
            om={"Value": "42.1%", "Core_Business_Profitable": "Yes"},
            mos={"Value": "72.4%", "Status": "Strong"}))
        assert [_c.state for _c, _, _ in _cards] == [UI_LIVE] * 3
        assert [_s for _, _, _s in _cards] == ["好生意", "本業獲利", "抗震極強"]

    def test_signal_labels_carry_no_emoji(self):
        """鐵律 3：訊號頻道**只出中文標籤**（帶 glyph 會被共用層當場 raise）。"""
        from src.ui.views._ui_kit import assert_signal_text_clean
        for _table in (P.GROSS_MARGIN_LABELS, P.OPERATING_MARGIN_LABELS,
                       P.SAFETY_MARGIN_LABELS):
            for _text in _table.values():
                assert_signal_text_clean("profit label", _text)

    def test_upstream_note_is_passed_through_verbatim(self):
        """L3 回的 `error` 欄（查無此代碼）是**有效結果**，不是例外 → 灰 + 原話。"""
        _cards = P.build_profit_cards(_prof(note="查無此股票代號"))
        _card, _facts, _ = _cards[0]
        assert _card.state == UI_EMPTY
        assert dict(_facts)["L3 說明"] == "查無此股票代號"

    def test_etf_branch_has_no_profitability_block(self):
        """ETF 沒有這一組指標 → `requested=False` → idle，**不是** empty。"""
        _prof_etf = P.load_profitability(_verdict("00878"))
        assert _prof_etf.requested is False
        assert P.build_profit_cards(_prof_etf)[0][0].state == UI_IDLE


# ══════════════════════════════════════════════════════════════════
# 【7】ETF 三格各自判態（線框 errCells：折溢價🔴 / 配息🟢 / 同儕⬜）
# ══════════════════════════════════════════════════════════════════
class TestEtfCellsAreIndependent:
    """三格不是同一次取數的成敗，不得共用一個狀態。"""

    def test_missing_premium_is_not_zero_percent(self):
        """L3 檔內記著一個已修的事故：假淨值 → **假溢價 +5.07%** 觸發假燈。

        現行契約是拿不到就不填欄位；把它顯示成 0%（＝「貼近淨值」這個結論）
        是同一個錯的另一半。
        """
        _card, _, _ = P.build_premium_card(
            P.EtfReadout(requested=True, premium_pct=None))
        assert _card.state == UI_EMPTY
        assert _card.value == "", "非 live 不准帶結論文字"
        assert "0" not in _card.note.now

    def test_zero_premium_is_a_real_answer(self):
        _card, _, _ = P.build_premium_card(
            P.EtfReadout(requested=True, premium_pct=0.0))
        assert _card.state == UI_LIVE, "折溢價真的是 0% 時要畫成有值"

    def test_missing_dividend_is_not_zero_yield(self):
        _card, _, _ = P.build_dividend_card(
            P.EtfReadout(requested=True, annual_yield_pct=None))
        assert _card.state == UI_EMPTY
        assert "0%" not in _card.note.why or "不配息" in _card.note.why

    def test_a_failed_fetch_reds_all_three_but_says_which_layer(self):
        """ETF 那一支 L3 是 fail-loud 的（拿不到日線就拋）→ 三格同時紅是**對的**，

        因為它們來自**同一次**呼叫。但理由必須講對是哪一層。
        """
        _etf = P.EtfReadout(requested=True, error="ValueError('無日線資料')")
        for _build in (P.build_premium_card, P.build_dividend_card,
                       P.build_peer_card):
            _card, _, _ = _build(_etf)
            assert _card.state == UI_FAILED
            assert "無日線資料" in _card.note.why
            assert "dividend_station_service" in _card.note.why, (
                "沒講出是哪一層出事 —— 對使用者謊報出事的層")

    def test_stock_branch_gets_no_etf_cells(self):
        _etf = P.load_etf_readout(_verdict("2330"))
        assert _etf.requested is False
        assert P.build_premium_card(_etf)[0].state == UI_IDLE

    def test_the_two_branches_share_no_card_label(self):
        """線框：**與個股分支重疊近零** —— 合併的是骨架，不是內容。"""
        _stock_labels = {
            P.build_health_card(P.StockReadout(requested=False))[0].label,
            P.build_valuation_card(P.ValuationReadout(requested=False))[0].label,
            P.build_chips_card(P.ChipsView(requested=False))[0].label,
        }
        _etf_labels = {
            P.build_premium_card(P.EtfReadout(requested=False))[0].label,
            P.build_dividend_card(P.EtfReadout(requested=False))[0].label,
            P.build_peer_card(P.EtfReadout(requested=False))[0].label,
        }
        assert not (_stock_labels & _etf_labels), (
            f"兩支判決卡共用了 label：{_stock_labels & _etf_labels}")


# ══════════════════════════════════════════════════════════════════
# 【8】批次：一檔失敗不作廢整批（線框葉2 err 原文）
# ══════════════════════════════════════════════════════════════════
class TestBatchDoesNotVoidTheWholeRun:
    """線框原文：「🔴 3 檔中 1 檔失敗（2317）· **其餘 2 檔照常顯示，不整批作廢**」。"""

    @staticmethod
    def _mixed() -> P.BatchReadout:
        return P.BatchReadout(requested=True, rows=(
            P.BatchRow(code="2330", kind="stock", kind_label="個股",
                       is_stock=True, metrics=(("財報體檢", "78 分"),)),
            P.BatchRow(code="00878", kind="etf", kind_label="ETF",
                       is_etf=True, metrics=(("折溢價", "+0.12%"),)),
            P.BatchRow(code="2317", kind="stock", kind_label="個股",
                       is_stock=True, error="TimeoutError('逾時')"),
        ))

    def test_one_failure_keeps_the_card_live(self):
        _card, _facts, _ = P.build_batch_card(
            self._mixed(), P.BatchRequest(submitted=True,
                                          tickers=("2330", "00878", "2317")))
        assert _card.state == UI_LIVE, "一檔失敗把整張卡染紅了"
        assert "2317" in dict(_facts)["其中失敗"]

    def test_the_failed_row_is_still_on_the_table(self):
        _readout = self._mixed()
        _rows = P.visible_batch_rows(
            _readout, P.BatchRequest(submitted=True, kind_filter=P.BATCH_FILTER_ALL))
        assert [_r.code for _r in _rows] == ["2330", "00878", "2317"]

    def test_filtering_never_hides_a_failure(self):
        """篩選只影響顯示；把失敗列篩掉會讓人以為那幾檔沒貼到。"""
        _readout = self._mixed()
        for _f in (P.KIND_CHOICE_STOCK, P.KIND_CHOICE_ETF):
            _rows = P.visible_batch_rows(
                _readout, P.BatchRequest(submitted=True, kind_filter=_f))
            assert "2317" in [_r.code for _r in _rows], (
                f"篩選 {_f} 把失敗的那一列藏起來了")

    def test_filter_actually_filters_the_successful_rows(self):
        _rows = P.visible_batch_rows(
            self._mixed(),
            P.BatchRequest(submitted=True, kind_filter=P.KIND_CHOICE_ETF))
        assert [_r.code for _r in _rows] == ["00878", "2317"]

    def test_mixed_paste_is_allowed(self):
        """客戶已核准**允許混貼** —— 解析不得把 ETF 或個股其中一種丟掉。"""
        _codes, _cut = P.parse_tickers("2330, 00878\n2317;0050")
        assert _codes == ("2330", "00878", "2317", "0050") and _cut == 0

    def test_duplicates_collapse_but_order_is_kept(self):
        assert P.parse_tickers("2330 0050 2330")[0] == ("2330", "0050")

    def test_over_the_cap_is_reported_not_silently_dropped(self):
        """§1：靜默丟掉使用者貼的東西，等於讓他以為那幾檔查過了。"""
        _raw = " ".join(str(1000 + _i) for _i in range(P.BATCH_MAX_TICKERS + 3))
        _codes, _cut = P.parse_tickers(_raw)
        assert len(_codes) == P.BATCH_MAX_TICKERS and _cut == 3
        _card, _facts, _ = P.build_batch_card(
            P.BatchReadout(requested=True, rows=(P.BatchRow(code="1000"),)),
            P.BatchRequest(submitted=True, tickers=_codes, truncated=_cut))
        assert "沒有查過" in dict(_facts)["超出上限被截掉"]

    def test_nothing_parsed_is_empty_not_idle(self):
        _req_b = P.applied_batch_request({P.SS_APPLIED_BATCH: {"raw": "   "}})
        _card, _, _ = P.build_batch_card(
            P.load_batch_rows(_req_b), _req_b)
        assert _card.state == UI_EMPTY
        assert _card.note.now == P.BATCH_EMPTY_NOW
        assert _card.note.now != P.BATCH_IDLE_NOW

    def test_whole_batch_failure_is_red(self):
        _card, _, _ = P.build_batch_card(
            P.BatchReadout(requested=True, error="ImportError('asset_lag')"),
            P.BatchRequest(submitted=True, tickers=("2330",)))
        assert _card.state == UI_FAILED
        assert "asset_lag" in _card.note.why

    def test_unknown_rows_count_as_success(self):
        """判不出型別是有效答案 —— 不得被算成「這一檔失敗」。"""
        _row = P.BatchRow(code="AAPL", kind_label=P.KIND_LABEL_FALLBACK,
                          is_unknown=True)
        assert _row.ok is True
        _card, _facts, _ = P.build_batch_card(
            P.BatchReadout(requested=True, rows=(_row,)),
            P.BatchRequest(submitted=True, tickers=("AAPL",)))
        assert _card.state == UI_LIVE
        assert "其中失敗" not in dict(_facts)


# ══════════════════════════════════════════════════════════════════
# 【9】Form 結構（線框 F11：form 內放 button 實跑即拋）
# ══════════════════════════════════════════════════════════════════
def _form_withs(tree: ast.Module) -> list[ast.With]:
    _out = []
    for _n in ast.walk(tree):
        if not isinstance(_n, ast.With):
            continue
        for _item in _n.items:
            _c = _item.context_expr
            if (isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute)
                    and _c.func.attr == "form"):
                _out.append(_n)
    return _out


def _attr_calls(nodes) -> list[ast.Call]:
    return [_c for _n in nodes for _c in ast.walk(_n)
            if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute)]


class TestFormStructure:
    """鐵律 2 的**結構**面。線框註記本頁是「**全站最大 form 受益點**」：

    代碼 + 期間 + 6 個 MA + 判型覆寫，改一個就整站 rerun 一次。
    """

    def test_there_are_exactly_two_forms(self):
        assert len(_form_withs(_tree())) == 2, (
            "頁 3 應該有兩個 form（葉1 form_ticker、葉2 form_batch）")

    def test_each_form_has_exactly_one_submit_button(self):
        for _form in _form_withs(_tree()):
            _submits = [_c for _c in _attr_calls([_form])
                        if _c.func.attr == "form_submit_button"]
            assert len(_submits) == 1, (
                f"form @line {_form.lineno} 有 {len(_submits)} 顆 submit")

    def test_no_button_of_any_kind_inside_any_form(self):
        """線框 F11：form 內的 `st.button` / `st.download_button` 實跑即拋。"""
        _bad = [f"st.{_c.func.attr} @line {_c.lineno}"
                for _c in _attr_calls(_form_withs(_tree()))
                if _c.func.attr in ("button", "download_button")]
        assert not _bad, (
            f"form 內出現按鈕 {_bad} —— 線框 F11：實跑即拋 StreamlitAPIException")

    def test_the_page_has_no_stray_button_outside_either(self):
        """本頁**刻意一顆 `st.button` 都沒有** —— 兩個入口都是 form submit。

        （下鑽用 `st.selectbox`，它讀的是**已經算完**的批次結果，不發新取數。）
        若哪天加了一顆鈕，本條會轉紅，提醒去確認它在 form 外、而且有自己的 gate。
        """
        _bad = [f"st.{_c.func.attr} @line {_c.lineno}"
                for _c in _attr_calls([_tree()])
                if _c.func.attr in ("button", "download_button")]
        assert not _bad, f"本頁多了裸按鈕 {_bad} —— 請確認它的 gate 與位置"

    def test_widget_values_are_only_read_inside_the_form_handlers(self):
        """**鐵律 2 的本體**：下游只准讀已套用值，不准讀 widget 當下值。"""
        _widgets = {"SS_TICKER_WIDGET", "SS_PERIOD_WIDGET", "SS_KIND_WIDGET",
                    "SS_MA_WIDGET_PREFIX", "SS_BATCH_WIDGET",
                    "SS_BATCH_FILTER_WIDGET"}
        _allowed = {"_render_ticker_form", "_render_batch_form"}
        _offenders = []
        for _fn in ast.walk(_tree()):
            if not isinstance(_fn, ast.FunctionDef) or _fn.name in _allowed:
                continue
            for _s in ast.walk(_fn):
                if isinstance(_s, ast.Name) and _s.id in _widgets:
                    _offenders.append(f"{_fn.name}:{_s.lineno} 讀了 {_s.id}")
        assert not _offenders, (
            f"widget 當下值被 form handler 以外的地方讀了：{_offenders}")

    def test_no_bare_columns_above_three(self):
        """鐵律 1：格子多於 3 個要換行，不是加欄（本頁一律走 `grid()`）。

        ⚠️ 線框 F11 點名的兩處降階都在這條底下：6 個 MA checkbox
        （原 `st.columns(6)`）與 💰 獲利能力（原 `st.columns(5)`）。
        """
        for _n in ast.walk(_tree()):
            if (isinstance(_n, ast.Call)
                    and isinstance(_n.func, ast.Attribute)
                    and _n.func.attr == "columns" and _n.args
                    and isinstance(_n.args[0], ast.Constant)):
                assert _n.args[0].value <= P.MAX_COLS, (
                    f"{_VIEW.name}:{_n.lineno} 用了 {_n.args[0].value} 欄")

    def test_six_ma_checkboxes_exist_and_go_through_the_grid(self):
        """MA 那一組必須是 6 個、而且是**一個 `grid()` 迴圈**畫出來的。

        寫成六行並排的 `st.checkbox` 就會有人下次直接改回 `st.columns(6)`。
        """
        assert len(P.MA_OPTIONS) == 6, P.MA_OPTIONS
        assert set(P.DEFAULT_MAS) <= set(P.MA_OPTIONS)
        _src = _VIEW.read_text(encoding="utf-8")
        assert "grid(MA_OPTIONS, MAX_COLS)" in _src, (
            "6 個 MA checkbox 沒有走 grid() —— 3 欄上限失守")

    def test_ma_periods_come_from_the_l0_ssot(self):
        """20 / 60 / 120 / 240 一律讀 `src/config/config.py`，不得手抄（§3.3）。"""
        from src.config.config import MA_ANNUAL, MA_LONG, MA_MID, MA_SHORT
        for _v in (MA_SHORT, MA_MID, MA_LONG, MA_ANNUAL):
            assert _v in P.MA_OPTIONS, f"MA{_v} 不在本頁的選項裡"
        _src = _VIEW.read_text(encoding="utf-8")
        assert "from src.config.config import" in _src


# ══════════════════════════════════════════════════════════════════
# 【10】渲染邊界走共用層（不得長出第三份 `_render_one`）
# ══════════════════════════════════════════════════════════════════
class TestRenderBoundaryIsShared:
    """頁 1 與頁 2 原本各有一份逐行同構的 `_render_one()`（兩把尺遲早漂移）。

    FE-9 已把本體上移 `_ui_kit.render_card_isolated()`。**本頁不寫第三份。**
    """

    def test_the_page_does_not_own_a_third_copy(self):
        assert not hasattr(P, "render_card"), (
            "`page_inspect` 自己持有 render_card 了 —— "
            "渲染期轉紅卡的邏輯只准有一份（`_ui_kit.render_card_isolated`）")
        assert hasattr(P, "render_card_isolated")

    def test_all_three_pages_bind_the_same_shared_function(self):
        from src.ui.views import _ui_kit as K
        from src.ui.views import page_find as F
        from src.ui.views import page_today as T

        assert (P.render_card_isolated is K.render_card_isolated
                is F.render_card_isolated is T.render_card_isolated), (
            "三頁綁到了不同的東西 —— 共用層形同虛設")

    def test_this_page_keeps_its_own_source_and_exit(self):
        """搬家保留了**該保留的差異**：出處與「去哪補」仍是本頁自己的。"""
        import inspect

        _src = inspect.getsource(P._render_one)
        assert 'owner="views/page_inspect"' in _src
        assert "SRC_RENDER" in _src and "NO_EXIT_MARKER" in _src

    def test_a_broken_card_becomes_a_red_card_not_half_a_page(self, monkeypatch):
        from src.ui.views import _ui_kit as K

        _md: list[str] = []
        _ns = type("NS", (), {})()
        _ns.markdown = lambda _s, **_k: _md.append(str(_s))
        _ns.caption = lambda _s, **_k: _md.append(str(_s))
        monkeypatch.setattr(K, "st", _ns)

        _calls = {"n": 0}
        _real = K.render_card

        def _boom(card, **kw):
            _calls["n"] += 1
            if _calls["n"] == 1:
                raise RuntimeError("render exploded")
            return _real(card, **kw)

        monkeypatch.setattr(K, "render_card", _boom)
        P._render_one(P.build_chips_card(P.ChipsView(requested=False)))
        _all = "\n".join(_md)
        assert "這一格畫不出來" in _all, "半截死頁：例外沒有被轉成看得見的紅卡"
        assert "render exploded" in _all, "原始例外必須看得見（§1）"


# ══════════════════════════════════════════════════════════════════
# 【FE-28】籌碼卡的異常值徽章：「判不出來」不得長得像「沒有異常」
# ══════════════════════════════════════════════════════════════════
def _ssot_threshold() -> float:
    """判定門檻的 **L0 SSOT**。測試自己也不准抄這個數字。"""
    from shared.signal_thresholds import INST_NET_OUTLIER_VOLUME_RATIO

    return float(INST_NET_OUTLIER_VOLUME_RATIO)


def _ssot_window() -> int:
    """均量窗長度 —— 讀 L2 那支的簽章預設值（同樣不抄數字）。"""
    import inspect as _i

    from src.compute.risk.inst_sanity import flag_latest_inst_outlier_from_df

    return int(_i.signature(
        flag_latest_inst_outlier_from_df).parameters["window"].default)


def _chips_df(*, latest_main: float, rows: int | None = None,
              inst: float = 500.0, vol: float = 5000.0):
    """一份「日線 ＋ 三大法人」的假 df —— 欄位照 L1 `get_combined_data` 的實況。

    ⚠️ 欄名**刻意不從測試自己的常數來**：`主力合計` / `volume` 是 L1 產出的
    欄名，測試在這裡就是要驗「L3 吃得到 L1 真的會給的那兩欄」。
    """
    import pandas as pd

    _n = rows if rows is not None else _ssot_window() + 10
    _main = [inst] * _n
    _main[-1] = latest_main
    return pd.DataFrame({"外資": [inst] * _n, "投信": [inst * 0.2] * _n,
                         "volume": [vol] * _n, "主力合計": _main})


def _patch_price(monkeypatch, df):
    from src.data.stock import app_stock_fetchers as A

    monkeypatch.setattr(A, "fetch_price_data",
                        lambda _s, _d: (df, "X", None), raising=True)


def _badge_text(view: P.ChipsView) -> str | None:
    """卡上徽章那一列的值；**沒有那一列 → `None`**（要能分辨「沒畫」）。"""
    return dict(P.build_chips_card(view)[1]).get(P.CHIPS_OUTLIER_LABEL)


class TestOutlierBadgeIsHonest:
    """線框那句「含異常值徽章」的守衛。**釘的是一個具體的失效模式**：

    既有 🔬 個股分頁的寫法是 `if _inst_flag.is_outlier:` 才畫徽章 ——
    於是「**判不出來**」與「**判過了、沒有異常**」在畫面上長得**一模一樣**
    （兩者都是沒有徽章），而使用者只會讀成後者。
    §1：把「沒量到」講成「量到了沒事」，就是捏造一個不存在的觀測。
    """

    # ── 真異常：要出現，而且要講得出倍數 ──────────────────────────
    def test_a_real_outlier_reaches_the_card(self, monkeypatch):
        """L1 → L3 → L5 走完整條：最新一日爆量 → 卡上真的看得到。"""
        _spike = _ssot_threshold() * 5000.0 * 2      # 遠超門檻，不卡在邊界
        _patch_price(monkeypatch, _chips_df(latest_main=_spike))
        _view = P.load_chips(_verdict("2330"), _req(ticker="2330"))
        assert _view.outlier_verdict == "anomaly", _view.outlier_verdict
        _txt = _badge_text(_view)
        assert _txt is not None, "真異常卻沒有畫出徽章那一列"
        assert "有異常" in _txt and "判不出來" not in _txt, _txt
        assert f"{_view.outlier_ratio:.1f}" in _txt, "倍數沒有出現在卡上"

    # ── 判不出來：**要出現**，不是靜默消失 ────────────────────────
    @pytest.mark.parametrize("name,df_kw", [
        ("均量窗不足", dict(latest_main=1.0, rows=3)),
        ("最新一日為 0", dict(latest_main=0.0)),
    ])
    def test_unknown_is_shown_not_silently_dropped(self, monkeypatch,
                                                   name, df_kw):
        _patch_price(monkeypatch, _chips_df(**df_kw))
        _view = P.load_chips(_verdict("2330"), _req(ticker="2330"))
        assert _view.outlier_verdict == "unknown", f"{name}：{_view!r}"
        _txt = _badge_text(_view)
        assert _txt is not None, f"{name}：判不出來被靜默拿掉了那一列"
        assert "判不出來" in _txt, f"{name}：{_txt}"
        assert "不等於" in _txt and "沒有異常" in _txt, (
            f"{name}：沒有明說「判不出來 ≠ 沒有異常」—— {_txt}")

    def test_missing_column_is_unknown_not_normal(self, monkeypatch):
        """連 `主力合計` 欄都沒有 → 判不出來，**不是**「沒有異常」。"""
        import pandas as pd

        _n = _ssot_window() + 10
        _patch_price(monkeypatch, pd.DataFrame({
            "外資": [500] * _n, "投信": [100] * _n, "volume": [5000] * _n}))
        _view = P.load_chips(_verdict("2330"), _req(ticker="2330"))
        assert _view.outlier_verdict == "unknown"
        assert _view.outlier_ratio is None, "判不出來就不該有倍數"
        assert "判不出來" in (_badge_text(_view) or "")

    def test_a_latest_zero_is_not_called_normal(self, monkeypatch):
        """最新一日 0 → **判不出來**（上游對這一欄補過 0，兩種意思分不出）。

        這一條是刻意的取捨，理由寫在 L3 檔頭：`data_loader` 的 `fill_cols`
        對 `主力合計` 做 `fillna(0)`，所以「0」可能是「今天沒有法人買賣超」，
        也可能是「今天的法人資料還沒到」（三大法人常態比日線晚到）。
        判成 `normal` 等於替後者背書。
        """
        _patch_price(monkeypatch, _chips_df(latest_main=0.0))
        _view = P.load_chips(_verdict("2330"), _req(ticker="2330"))
        assert _view.outlier_verdict == "unknown"
        assert _view.outlier_reason == "inst_net_zero", _view.outlier_reason
        assert "補 0" in (_badge_text(_view) or ""), "沒有交代 0 為什麼不算數"

    # ── 三態的字面必須真的不一樣 ──────────────────────────────────
    def test_the_three_verdicts_do_not_share_a_sentence(self):
        _mk = lambda **kw: P.ChipsView(                       # noqa: E731
            requested=True, signal="🔥 大戶吸籌", concentration=6.3,
            days=20, rows=250, days_loaded=250,
            outlier_threshold=_ssot_threshold(),
            outlier_window=_ssot_window(), **kw)
        _a = _badge_text(_mk(outlier_verdict="anomaly", outlier_ratio=12.0,
                             outlier_reason="outlier"))
        _n = _badge_text(_mk(outlier_verdict="normal", outlier_ratio=0.1,
                             outlier_reason="ok"))
        _u = _badge_text(_mk(outlier_verdict="unknown",
                             outlier_reason="vol_unavailable"))
        assert len({_a, _n, _u}) == 3, "三態共用了同一句話"
        assert "判過了" in _n and "判不出來" not in _n
        assert "判不出來" in _u and "判過了" not in _u, (
            "「判不出來」被寫成「判過了」—— 那正是本類要擋的那句謊")

    def test_no_verdict_at_all_draws_no_row(self):
        """取數失敗 / 冷啟動 → 連 df 都沒有，**不畫這一列**（卡自己已在紅／灰態）。"""
        assert _badge_text(P.ChipsView(requested=False)) is None
        assert _badge_text(P.ChipsView(
            requested=True, error="RuntimeError('boom')")) is None

    # ── 徽章不得越權：不佔訊號頻道、不改卡的狀態 ──────────────────
    def test_the_badge_never_takes_the_signal_channel(self):
        """訊號頻道已被 L0 的籌碼訊號佔住；徽章載的是判決語 → 一律留白。"""
        _, _, _sig = P.build_chips_card(P.ChipsView(
            requested=True, signal="🔥 大戶吸籌", concentration=6.3, days=20,
            rows=250, days_loaded=250, outlier_verdict="anomaly",
            outlier_ratio=12.0, outlier_threshold=_ssot_threshold(),
            outlier_window=_ssot_window(), outlier_reason="outlier"))
        assert _sig == "大戶吸籌", f"徽章擠掉／污染了訊號頻道：{_sig!r}"

        _card, _, _sig2 = P.build_chips_card(P.ChipsView(
            requested=True, signal="⚫ 資料不足", miss_reason="df法人欄全為0",
            rows=250, days_loaded=250, outlier_verdict="anomaly",
            outlier_ratio=12.0, outlier_threshold=_ssot_threshold(),
            outlier_window=_ssot_window(), outlier_reason="outlier"))
        assert _sig2 == "", "灰態不得因為徽章有話說就點亮訊號頻道"
        assert _card.state == UI_EMPTY, "徽章不得把集中度的灰態改掉"

    def test_the_badge_does_not_change_the_card_state(self):
        """集中度判得出來 + 徽章判不出來 → 卡仍是 live（別把好的一半藏掉）。"""
        _card, _facts, _ = P.build_chips_card(P.ChipsView(
            requested=True, signal="🔥 大戶吸籌", concentration=6.3,
            continuity=60.0, days=20, pos_days=12, rows=250, days_loaded=250,
            outlier_verdict="unknown", outlier_threshold=_ssot_threshold(),
            outlier_window=_ssot_window(), outlier_reason="vol_unavailable"))
        assert _card.state == UI_LIVE
        assert "判不出來" in dict(_facts)[P.CHIPS_OUTLIER_LABEL]

    def test_the_badge_is_judged_even_when_chips_is_not(self, monkeypatch):
        """兩支吃的欄位不同 → 一支判不出來**不得**連坐另一支。"""
        import pandas as pd

        _n = _ssot_window() + 10
        _main = [500.0] * _n
        _main[-1] = _ssot_threshold() * 5000.0 * 2
        # 外資 / 投信 全 0 → L0 判「df法人欄全為0」；主力合計 仍有爆量
        _patch_price(monkeypatch, pd.DataFrame({
            "外資": [0] * _n, "投信": [0] * _n, "volume": [5000] * _n,
            "主力合計": _main}))
        _view = P.load_chips(_verdict("2330"), _req(ticker="2330"))
        assert _view.miss_reason, "前提沒成立：集中度應該判不出來"
        assert _view.outlier_verdict == "anomaly", (
            "集中度判不出來就把徽章一起丟掉了 —— 兩支是獨立的檢查")
        assert "有異常" in (_badge_text(_view) or "")


class TestOutlierThresholdStaysInTheSSOT:
    """門檻與均量窗**一個數字都不准出現在本批改的兩個檔裡**（§3.3）。

    ⚠️ 這一類**不是**覆蓋率填充：門檻抄一份到畫面上，上游改的時候它不會跟著
    動、也沒有任何測試會紅 —— 畫面就會長期對使用者講一個**不是實際判定用的**
    數字。那是 §1「錯誤的數字比沒有數字更危險」的標準形狀。
    """

    @staticmethod
    def _badge_funcs() -> tuple[tuple[pathlib.Path, tuple[str, ...]], ...]:
        """(檔案, 要掃的函式名)。**在測試裡才 import L3** —— class body 會在
        collection 期跑，那時 L3 還沒載進來，`sys.modules` 查回 `None`
        會讓這條守衛變成永遠綠的假守衛。
        """
        from src.services import stock_chips_service as _C

        return ((pathlib.Path(_C.__file__),
                 ("_outlier_fields", "_outlier_window")),
                (_VIEW, ("_outlier_fact",)))

    def test_l2_default_threshold_is_the_l0_ssot(self):
        """對帳（§4.3）：L2 拿來判的那個門檻，就是 L0 那個常數。

        L3 報給畫面的是 L0 常數，L2 判定用的是它自己的簽章預設值 ——
        **兩條路必須是同一個數字**，否則畫面會講一個沒有在判定的門檻。
        """
        import inspect as _i

        from src.compute.risk.inst_sanity import (
            flag_latest_inst_outlier_from_df,
            is_inst_net_outlier,
        )

        for _fn in (flag_latest_inst_outlier_from_df, is_inst_net_outlier):
            _d = _i.signature(_fn).parameters["threshold_ratio"].default
            assert float(_d) == _ssot_threshold(), (
                f"{_fn.__name__} 的門檻預設值與 L0 SSOT 不一致：{_d}")

    def test_l3_reports_exactly_the_ssot_numbers(self, monkeypatch):
        from src.services import stock_chips_service as C

        _patch_price(monkeypatch, _chips_df(latest_main=1.0))
        _r = C.get_chips_readout("2330", days=250)
        assert _r.outlier_threshold == _ssot_threshold()
        assert _r.outlier_window == _ssot_window()

    def test_the_number_is_never_written_into_the_badge_code(self):
        """AST：徽章那幾支函式體內**不得**有等於門檻／窗長度的數字字面。"""
        for _path, _names in self._badge_funcs():
            _tree_ = ast.parse(_path.read_text(encoding="utf-8"))
            _seen = {_n.name for _n in ast.walk(_tree_)
                     if isinstance(_n, ast.FunctionDef)}
            assert set(_names) <= _seen, (
                f"{_path.name} 找不到 {sorted(set(_names) - _seen)} —— "
                "函式改名了，這條守衛會變成永遠綠的假守衛")
            _wanted = {_ssot_threshold(), float(_ssot_window())}
            for _node in ast.walk(_tree_):
                if not isinstance(_node, ast.FunctionDef):
                    continue
                if _node.name not in _names:
                    continue
                for _c in ast.walk(_node):
                    if (isinstance(_c, ast.Constant)
                            and isinstance(_c.value, (int, float))
                            and not isinstance(_c.value, bool)):
                        assert float(_c.value) not in _wanted, (
                            f"{_path.name}::{_node.name} 把 {_c.value} 寫死了 "
                            f"—— 門檻與均量窗只准從上游讀（§3.3）")

    def test_the_number_is_never_written_into_the_card_copy(self):
        """文案常數裡也不准出現那兩個數字（寫進去就繞過了上面那條 AST）。"""
        _bad = {f"{_ssot_threshold():.1f}", str(_ssot_window())}
        for _name in dir(P):
            if not _name.startswith("CHIPS_OUTLIER_"):
                continue
            _val = getattr(P, _name)
            if not isinstance(_val, str):
                continue
            for _b in _bad:
                assert _b not in _val, (
                    f"{_name} 把 {_b} 寫進文案了 —— 那個數字必須由 L3 帶上來")

    @pytest.mark.parametrize("field,given,ssot", [
        ("outlier_threshold", 99.0, None),
        ("outlier_window", 7, None),
    ])
    def test_the_copy_tracks_what_it_was_given(self, field, given, ssot):
        """給它一個**不是** SSOT 的值 → 卡上必須跟著變。

        這是上面兩條 AST／字面守衛的**行為版替身**：有人若把數字硬編進
        f-string 的組裝過程（AST 掃得到、但寫法千變萬化），這一條照樣會紅。
        """
        _kw = {"outlier_verdict": "normal", "outlier_ratio": 0.1,
               "outlier_reason": "ok", "outlier_threshold": _ssot_threshold(),
               "outlier_window": _ssot_window()}
        _kw[field] = given
        _txt = _badge_text(P.ChipsView(
            requested=True, signal="🔥 大戶吸籌", concentration=6.3, days=20,
            rows=250, days_loaded=250, **_kw))
        assert str(given) in (_txt or ""), (
            f"{field} 換成 {given} 之後卡上沒跟著變 —— 數字被寫死了：{_txt}")


# ══════════════════════════════════════════════════════════════════
# 冒煙（slow lane）：這一頁真的畫得出來
# ══════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_page_mounts_clean(tmp_path):
    """冷啟動整頁 mount：**沒有 uncaught exception、不是半截頁面**。

    ⚠️ 這一條看得到的只有「畫得出來」；它**看不到**畫出來的東西是不是真的
    （狀態對不對、有沒有靜默降級）—— 那些由上面的單元測試守。
    """
    import textwrap

    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_p03_view.py"
    _script.write_text(textwrap.dedent("""
        from src.ui.views.page_inspect import render_page_inspect
        render_page_inspect()
    """), encoding="utf-8")

    _at = AppTest.from_file(str(_script), default_timeout=120)
    _at.run()
    assert not _at.exception, (
        f"page_inspect mount 有 uncaught exception: {_at.exception}")

    _all = ("\n".join(_m.value for _m in _at.markdown)
            + "\n" + "\n".join(_c.value for _c in _at.caption))

    # 兩顆 submit（form 外沒有任何裸按鈕，見 TestFormStructure）。
    _labels = [_b.label for _b in _at.button]
    assert P.ACTION_LOAD_INSPECT_LABEL in _labels, "葉1 submit 沒畫出來"
    assert P.ACTION_RUN_BATCH_LABEL in _labels, "葉2 submit 沒畫出來"

    # 6 個 MA checkbox 真的畫出來了（3 欄 × 2 排）。
    assert len(_at.checkbox) == len(P.MA_OPTIONS), (
        f"MA checkbox 應有 {len(P.MA_OPTIONS)} 個，實際 {len(_at.checkbox)}")

    # 冷啟動 = idle，**不是** empty、**不是**紅、**不是** unknown。
    assert P.SINGLE_IDLE_NOW.strip("*") in _all, "冷啟動不是 idle 態"
    assert P.BLANK_TICKER_NOW.strip("*") not in _all, (
        "冷啟動被畫成「代碼欄是空的」—— 還沒送出 ≠ 送出了沒填")
    assert "無法判定這是個股還是 ETF" not in _all, (
        "冷啟動就跑出 unknown 分支了")

    # 常駐揭露（不隨狀態消失）—— 這一句畫不出來就是半截死頁。
    # ⚠️ 2026-09-07 FE-18：原本 grep 的是「在本頁未接線」；估值與籌碼接線後
    # 那句話已經改寫（仍留「K 線與其餘明細**仍**未接線」）。**改成直接比對
    # 常數本身**，這比原本的字串片段**更嚴** —— 以後改文案不必再改測試，
    # 而且揭露被整段刪掉時一樣會紅。
    assert P.WIRING_DISCLOSURE_SINGLE in _all, "葉1 的接線揭露沒畫出來"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
