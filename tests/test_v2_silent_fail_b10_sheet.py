"""Q4：「💼 我的持股」`EMPTY_SHEET_NOW`「Sheet 綁好了，但裡面還沒有任何一列持股」——
Sheet 明明有列、只是每一列的「張數／均價」是空白，被 L1 整列丟光 ⇒ 被講成「空的」。

（客戶 2026-09-26 批次授權「失敗被當成沒結果」的所有卡；⛔ 不新造文案（K1）；⛔ 不動版面；
  L1／L3 限加性參數、預設維持舊行為。）

根因（L1 `gsheet_portfolio.parse_portfolio_records`）：
  `float(rec.get('lots') or 0)` 把空白格讀成 0，再以 `lots <= 0 or avg <= 0` 整列丟掉。
  ⇒ 一本每列都缺張數或均價的組合，L3 `get_holdings()` 回空清單 ＋ `bound=True`，
     L5 的「三種沒有」落在第二種 `EMPTY_SHEET_NOW`（**「這是一個有效的結果」**）—— 那句話是假的。
  ⇒ 只缺幾列時更糟：那幾列**靜默消失**，金額與 80/20 被畫成「完整」的數字
     （`UI_PAGE_HOLD.md` ⑥B 逐字「缺的那幾檔一律單獨列出，⛔ 不靜默剔除」）。

修法（三層各一個加性參數，全部預設 False ＝ 改前行為）：
  · L1 `parse_portfolio_records(..., keep_blank=False)` ／ `load_portfolio(..., keep_blank=False)`：
    True 時空白格 → `None`（缺值，⛔ 不是 0），整列保留；**有填值**的格子規則一字不變
    （`0`／負數／非數字照舊丟 —— 本批不替使用者猜那個值的意思）。
  · L3 `get_holdings(*, keep_blank=False)`：True 才把參數帶給 L1；False 時 L1 呼叫逐字同改前。
  · L5 `page_hold.load_holdings()`：呼叫 `get_holdings(keep_blank=True)`。**L5 沒有新判態、
    沒有新字串** —— 缺張數／均價的持有列進到下游之後，各卡走的全是**既有**的那一套
    （金額列「N/M 檔持股缺張數／均價／現價，沒有納入」、80/20「只涵蓋一部分」等）。

每條路徑四件事：
  (a) 全部被丟 → ⛔ 不再是「空 Sheet」灰卡（也 ⛔ 不是「沒綁」）；落點全是既有 `*_NOW`；
      部分被丟 → 既有的「只涵蓋一部分」揭露出現（改前不出現）；
  (b) 真的空 Sheet／沒綁／全部有效／有填值但非正數 → 與改前 byte-identical；
  (c) 既有呼叫端（不傳新參數）回傳值不變：L1 `parse_portfolio_records`／`load_portfolio`、
      L3 `get_holdings`；其他 L1 呼叫端一個都沒有改成傳新參數；
  (d) 突變：拔掉任一新增點（L5 帶參數／L3 透傳／L1 透傳／L1 空白判定）→ (a) 必須轉紅。
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import itertools
import pathlib
import sys
import types

import pandas as pd
import pytest

import src.data.portfolio.gsheet_portfolio as GSP
import src.services.dividend_station_service as S
import src.services.holdings_service as HS
from shared import dividend_station_thresholds as T
from shared.ui_state import UI_EMPTY, UI_LIVE
from src.ui.views import page_hold as PH

_REPO = pathlib.Path(__file__).resolve().parents[1]
_HS_NAME = "src.services.holdings_service"
_REQ = PH.HoldRequest(submitted=True, mode=PH.SCOPE_WITH_BINDING)
_SID = "SHEET1"

#: 「沒有持股」的兩句灰卡 —— 全部被丟時**兩句都不得出現**。
_NOTHING_NOWS = (PH.EMPTY_SHEET_NOW, PH.NOT_BOUND_NOW)
#: 本頁全部既有的 `*_NOW` 常數（K1：卡面上的 `now` 只能是其中之一）。
_KNOWN_NOWS = {v for k, v in vars(PH).items() if k.endswith("_NOW") and isinstance(v, str)}


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 的原始碼裡每一組 `old` **恰好一處**換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b10_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ── 本批的每一個新增點（突變與「修前」重建共用同一組字串）───────────────────
_PH_KEEP = ("_h = get_holdings(keep_blank=True)", "_h = get_holdings()")
_HS_PASS = ("_gsp.load_portfolio(_pf_name, sheet_id=_sid, keep_blank=True)",
            "_gsp.load_portfolio(_pf_name, sheet_id=_sid)")
_GSP_PASS = ("        return parse_portfolio_records(recs, keep_blank=True)\n",
             "        return parse_portfolio_records(recs)\n")
_GSP_BLANK = ("    if _is_blank_cell(value):\n        return None\n",
              "    if _is_blank_cell(value):\n        return _UNUSABLE\n")


def _frozen_parse(records):
    """**改前**的 `parse_portfolio_records` 逐字凍結（(c) 的對照組；⛔ 不得跟著改）。"""
    out = []
    for rec in (records or []):
        tk = str(rec.get('ticker', '')).strip()
        if not tk:
            continue
        try:
            lots = float(rec.get('lots') or 0)
            avg = float(rec.get('avg_price') or 0)
        except (TypeError, ValueError):
            continue
        if lots <= 0 or avg <= 0:
            continue
        out.append({'ticker': tk, 'lots': lots, 'avg_price': avg})
    return out


# ── 資料 ──────────────────────────────────────────────────────────────
def _rec(ticker, lots, avg, name="核心"):
    return {"name": name, "ticker": ticker, "lots": lots, "avg_price": avg,
            "updated_at": "2026-09-26 09:00:00"}


#: 每一列都缺張數或均價（`get_all_records()` 對空白格回 `''`）。
_ALL_BLANK = (_rec("0056", "", ""), _rec("2330", 3, ""), _rec("00878", "", 18.5))
#: 一列有效、一列缺。
_PARTIAL = (_rec("0056", 3, 30.0), _rec("2330", "", ""))

#: 真的結果 —— 修前修後必須一字不變（L1 設定：records ／ 是否登入 ／ sheet id）。
_GENUINE = {
    "not_bound": dict(records=(), logged=False, sid=""),
    "bound_empty_sheet": dict(records=()),
    "bound_all_valid": dict(records=(_rec("0056", 3, 30.0), _rec("2330", 1, 100.0))),
    # 有填值、但不是正數 → **兩個模式都照舊丟**（本批只放寬「空白」，見 L1 docstring）。
    # ⚠️ 其中「整本都是這種」那一格改前改後都會落 `EMPTY_SHEET_NOW` —— 那是**本批刻意不動**
    #    的範圍（不是空白，是使用者寫了一個值），已隨交付回報；要改請連本條一起改。
    "bound_filled_but_not_positive": dict(records=(_rec("0056", 3, 30.0), _rec("2330", 0, 100.0),
                                                   _rec("2317", -1, 100.0), _rec("2454", "x", 900))),
    "bound_only_filled_not_positive": dict(records=(_rec("2330", 0, 100.0), _rec("2454", "x", 9))),
    "bound_blank_ticker_only": dict(records=(_rec("", "", ""), _rec("  ", 3, 30.0))),
}


def _metrics(tk, ak):
    idx = pd.date_range("2020-01-03", periods=300, freq="W-FRI")
    if ak == T.KIND_ETF:
        return {"weekly_close": pd.Series([30 + (i % 7) * 0.3 for i in range(300)], index=idx),
                "current_price": 35.0}
    return {"mj_grade": "A", "mj_score_pct": 80, "mj_headline": "ok", "mj_fail_items": [],
            "kd_state": {"k": 50, "d": 40, "label": "中性"}, "name": tk,
            "trend_verdict": None, "current_price": 125.0}


@pytest.fixture(autouse=True)
def _clear_l1_cache():
    GSP.clear_read_cache()
    yield
    GSP.clear_read_cache()


@pytest.fixture
def sheet(monkeypatch):
    """設定「投資組合」那張 worksheet 的原始列（**走真的 L1 解析**；只換掉讀 Google 那一步）。"""
    import src.services.app_ai_service as A
    import src.services.portfolio_deep_service as D

    # 下游的網路面一律換成離線替身（兩個版本吃同一組）。
    monkeypatch.setattr(S, "resolve_holding_names", lambda h: h)
    monkeypatch.setattr(S, "get_station_rows",
                        lambda hold: (S.build_station_rows(hold, vix=18.0, metrics_fn=_metrics), 18.0))
    monkeypatch.setattr(S, "get_switch_in_candidates", lambda **_k: [])
    for _fn in ("get_portfolio_stress", "get_portfolio_var", "get_dividend_cash_flow"):
        # `**_k`：Q3 起頁面以 `get_portfolio_var(rows, strict=True)` 呼叫（加性參數）——
        # 替身不收它的話會 TypeError，VaR 那格被悄悄換成「拋例外」紅卡，不再是本替身想模擬的「回 None」
        # （同 `test_v2_silent_fail_b7_binding.py` 的同一處）。
        monkeypatch.setattr(D, _fn, lambda rows, **_k: None)
    monkeypatch.setattr(A, "gemini_call", lambda *_a, **_k: "推播文字")

    def _use(*, records=(), logged=True, sid=_SID, mods=(GSP,)):
        def _all_records(*, sheet_id=None, worksheet_name=GSP._WORKSHEET_NAME, headers=None):
            if worksheet_name != GSP._WORKSHEET_NAME:
                return []
            return [dict(r) for r in records]
        for m in mods:
            monkeypatch.setattr(m, "_all_records", _all_records)
        monkeypatch.setattr(GSP, "_has_oauth_tokens", lambda: logged)
        monkeypatch.setattr(GSP, "_get_active_sheet_id", lambda: sid)
        monkeypatch.setattr(GSP, "_get_active_stock_sheet_id", lambda: "")
        monkeypatch.setattr(GSP, "_oauth_import_error", lambda: "")
    return _use


def _page(P) -> list[tuple]:
    """整頁以持股為輸入的卡：葉2 預覽 ＋ 戰情表家族全部（AI 按下）。"""
    h = P.load_holdings(_REQ)
    st_ = P.load_station(h)
    sw = P.load_switch(st_, P.MacroReadout(requested=True), h)
    dp = P.load_deep(st_)
    ai = P.load_ai_summary(True, st_, sw)
    return ([P.build_holdings_preview_card(h)]
            + list(P.build_conclusion_cards(st_))
            + [P.build_lightwall_card(st_), P.build_take_profit_card(st_),
               P.build_allocation_split_card(st_), P.build_core_satellite_card(st_),
               P.build_switch_card(sw, st_), P.build_stress_card(dp), P.build_var_card(dp),
               P.build_dividend_cash_card(dp), P.build_ai_summary_card(ai, st_)])


def _fp(P, built) -> str:
    card, facts, sig = built
    return repr((card, tuple(facts), sig)) + P.v2_card_html(card, facts, sig)


def _says_nothing(built) -> list[str]:
    """哪幾張卡把這一輪講成「沒有持股」（空 Sheet／沒綁）。"""
    return [b[0].key for b in built if b[0].note and b[0].note.now in _NOTHING_NOWS]


def _assert_a(built, n_rows: int) -> None:
    """(a) 的判準本體 —— 突變測試直接拿它來證明「拔掉就轉紅」。"""
    assert not _says_nothing(built), (
        f"Sheet 有 {n_rows} 列，卻被講成「沒有持股」：{_says_nothing(built)}")
    preview = built[0][0]
    assert preview.key == "hold.setup.preview"
    assert preview.state == UI_LIVE, preview
    assert preview.value == f"{n_rows} 列（持有 {n_rows} · 觀察 0）", preview.value


# ══════════════════════════════════════════════════════════════════
# (a) 全部被丟 → 不再是「空 Sheet」；部分被丟 → 既有揭露出現
# ══════════════════════════════════════════════════════════════════
class TestNotEmptyAnymore:
    def test_a_all_blank_rows_are_not_an_empty_sheet(self, sheet):
        sheet(records=_ALL_BLANK)
        _assert_a(_page(PH), len(_ALL_BLANK))

    def test_a_the_blank_cells_are_missing_not_zero(self, sheet):
        sheet(records=_ALL_BLANK)
        h = PH.load_holdings(_REQ)
        got = {x["ticker"]: (x["held"], x["lots"], x["avg_price"]) for x in h.holdings}
        assert got == {"0056": (True, None, None), "2330": (True, 3.0, None),
                       "00878": (True, None, 18.5)}, "空白格被填成 0 了 —— 缺值不是 0（§1）"
        assert PH._fmt_lots(None) == "—"

    def test_a_every_card_lands_on_an_existing_state(self, sheet):
        """K1：卡面上的 `now` 全部是本頁**既有**的 `*_NOW`；v2 卡面每張都畫得出來（⛔ 不落紅卡）。"""
        sheet(records=_ALL_BLANK)
        for card, facts, sig in _page(PH):
            if card.note is not None:
                assert card.note.now in _KNOWN_NOWS, (card.key, card.note.now)
            PH.v2_card_html(card, facts, sig)     # 短句表對不上會 KeyError

    def test_a_money_rows_say_they_cannot_be_computed_with_the_existing_sentence(self, sheet):
        """全部缺張數或均價 → 金額列走既有的「算不出來 —— 持股缺張數／均價／現價」。"""
        sheet(records=_ALL_BLANK)
        action = _page(PH)[1]
        assert action[0].key == PH.CONCLUSION_ACTION_KEY
        vals = dict(action[1])
        assert vals["未實現損益／總市值"].startswith("**算不出來** —— 持股缺張數／均價／現價")

    def test_a_partial_drop_is_disclosed_with_the_existing_sentence(self, sheet):
        """部分缺 → 既有的「⚠️ 上面兩個金額只涵蓋一部分」出現（改前那一列靜默消失、金額被當成完整）。"""
        sheet(records=_PARTIAL)
        new = dict(_page(PH)[1][1])
        assert new["⚠️ 上面兩個金額只涵蓋一部分"].startswith(
            "1/2 檔持股缺張數／均價／現價，**沒有**納入 —— 上面兩個數字只涵蓋其餘 1 檔")
        old = dict(_page(_mutant(PH, _PH_KEEP))[1][1])
        assert "⚠️ 上面兩個金額只涵蓋一部分" not in old, "對照組失效：改前就已經揭露了？"


# ══════════════════════════════════════════════════════════════════
# (b) 真的結果 → 與改前 byte-identical
# ══════════════════════════════════════════════════════════════════
class TestGenuineUnchanged:
    @pytest.mark.parametrize("case", sorted(_GENUINE))
    def test_b_whole_page_is_byte_identical_to_before(self, sheet, case):
        sheet(**_GENUINE[case])
        new = [_fp(PH, b) for b in _page(PH)]
        GSP.clear_read_cache()
        ph_old = _mutant(PH, _PH_KEEP)
        old = [_fp(ph_old, b) for b in _page(ph_old)]
        assert new == old

    def test_b_a_really_empty_sheet_is_still_the_grey_valid_result(self, sheet):
        sheet(records=())
        built = _page(PH)
        assert built[0][0].state == UI_EMPTY
        assert built[0][0].note.now == PH.EMPTY_SHEET_NOW
        assert "有效的結果" in built[0][0].note.why
        assert {b[0].note.now for b in built[1:]} == {PH.EMPTY_SHEET_NOW}


# ══════════════════════════════════════════════════════════════════
# (c) 既有呼叫端（不傳新參數）回傳值不變
# ══════════════════════════════════════════════════════════════════
#: 每一格可能的樣子（空白三種 ＋ 非正數 ＋ 非數字 ＋ 正數）。
_CELLS = (None, "", "   ", 0, "0", -1, "-2.5", "x", "1,000", 3, "3", 2.5, " 4 ")


def _is_blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


class TestExistingCallersUnchanged:
    def test_c_default_parse_equals_the_frozen_rule_on_every_cell_combo(self):
        recs = [_rec("T", lo, av) for lo, av in itertools.product(_CELLS, _CELLS)]
        assert GSP.parse_portfolio_records(recs) == _frozen_parse(recs)
        for r in recs:          # 一列一列比，失敗時看得出是哪一格
            assert GSP.parse_portfolio_records([r]) == _frozen_parse([r]), r

    def test_c_keep_blank_only_differs_on_blank_cells(self):
        """`keep_blank=True` 對「兩格都有填值」的列，結果與改前**逐列相同**；
        有空白格時：空白 → `None`，另一格照改前規則（不可用 → 整列照舊丟）。"""
        def _unusable(v) -> bool:
            return not _is_blank(v) and _frozen_parse([_rec("T", v, 1)]) == []

        for lo, av in itertools.product(_CELLS, _CELLS):
            r = [_rec("T", lo, av)]
            got = GSP.parse_portfolio_records(r, keep_blank=True)
            if not (_is_blank(lo) or _is_blank(av)):
                assert got == _frozen_parse(r), (lo, av)
            elif _unusable(lo) or _unusable(av):
                assert got == [], (lo, av)
            else:
                assert len(got) == 1 and got[0]["ticker"] == "T", (lo, av)
                for key, v in (("lots", lo), ("avg_price", av)):
                    assert (got[0][key] is None) == _is_blank(v), (lo, av, got)
                    if not _is_blank(v):
                        assert got[0][key] == float(v), (lo, av, got)

    def test_c_empty_inputs(self):
        assert GSP.parse_portfolio_records([]) == []
        assert GSP.parse_portfolio_records(None) == []
        assert GSP.parse_portfolio_records([], keep_blank=True) == []

    def test_c_new_params_default_to_the_old_behaviour(self):
        for fn in (GSP.parse_portfolio_records, getattr(GSP.load_portfolio, "__wrapped__",
                                                        GSP.load_portfolio), HS.get_holdings):
            p = inspect.signature(fn).parameters["keep_blank"]
            assert p.default is False and p.kind is inspect.Parameter.KEYWORD_ONLY, fn

    def test_c_load_portfolio_default_is_unchanged(self, sheet):
        rows = _ALL_BLANK + _PARTIAL + (_rec("9999", 1, 1, name="別本"),)
        sheet(records=rows)
        want = _frozen_parse([r for r in rows if r["name"] == "核心"])
        assert GSP.load_portfolio("核心", sheet_id=_SID) == want
        assert GSP.load_portfolio("核心") == want

    def test_c_get_holdings_default_calls_l1_exactly_as_before(self, sheet, monkeypatch):
        sheet(records=_ALL_BLANK + _PARTIAL)
        calls = []
        real = GSP.load_portfolio

        def _spy(*a, **k):
            calls.append((a, dict(k)))
            return real(*a, **k)
        monkeypatch.setattr(GSP, "load_portfolio", _spy)
        res = HS.get_holdings()
        assert calls == [(("核心",), {"sheet_id": _SID})], "預設路徑多帶了參數 —— L1 快取鍵變了"
        assert [(x["ticker"], x["lots"], x["avg_price"]) for x in res.held] == [("0056", 3.0, 30.0)]
        assert set(HS.HoldingsResult.__dataclass_fields__) == {
            "holdings", "bound", "logged_in", "portfolio_name", "watchlist_name",
            "more_portfolios", "more_watchlists", "watchlist_error"}, "L3 回傳型別多了欄位"

    def test_c_no_other_caller_passes_the_new_param(self):
        """只有本頁這一條鏈會開 `keep_blank`；📁 組合管理、ETF 存股戰情室、cron SA reader 都沒動。"""
        hits = set()
        for base in ("src", "scripts", "mcp_server", "app.py"):
            p = _REPO / base
            if not p.exists():
                continue
            for f in ([p] if p.is_file() else sorted(p.rglob("*.py"))):
                for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                    if isinstance(n, ast.keyword) and n.arg == "keep_blank":
                        hits.add(str(f.relative_to(_REPO)))
        assert hits == {"src/data/portfolio/gsheet_portfolio.py",
                        "src/services/holdings_service.py", "src/ui/views/page_hold.py"}


# ══════════════════════════════════════════════════════════════════
# (d) 突變 —— 拿掉本批的任一條，(a) 必須失敗
# ══════════════════════════════════════════════════════════════════
class _Swap:
    """讓頁面 late import 到指定版本的 L3。"""

    def __init__(self, hs):
        self._hs, self._old = hs, None

    def __enter__(self):
        self._old = sys.modules.get(_HS_NAME)
        sys.modules[_HS_NAME] = self._hs

    def __exit__(self, *_exc):
        sys.modules[_HS_NAME] = self._old


class TestMutations:
    def test_d_page_not_asking_for_blank_rows_turns_a_red(self, sheet):
        sheet(records=_ALL_BLANK)
        built = _page(_mutant(PH, _PH_KEEP))
        with pytest.raises(AssertionError):
            _assert_a(built, len(_ALL_BLANK))
        assert _says_nothing(built), "突變沒有重現原 bug —— 對照組失效"

    def test_d_l3_not_passing_it_on_turns_a_red(self, sheet):
        sheet(records=_ALL_BLANK)
        with _Swap(_mutant(HS, _HS_PASS)):
            built = _page(PH)
        with pytest.raises(AssertionError):
            _assert_a(built, len(_ALL_BLANK))

    def test_d_l1_load_not_passing_it_on_turns_a_red(self, sheet, monkeypatch):
        mut = _mutant(GSP, _GSP_PASS)
        sheet(records=_ALL_BLANK, mods=(GSP, mut))
        monkeypatch.setattr(GSP, "load_portfolio", mut.load_portfolio)
        built = _page(PH)
        with pytest.raises(AssertionError):
            _assert_a(built, len(_ALL_BLANK))

    def test_d_l1_blank_check_removed_turns_a_red(self, sheet, monkeypatch):
        sheet(records=_ALL_BLANK)
        monkeypatch.setattr(GSP, "parse_portfolio_records",
                            _mutant(GSP, _GSP_BLANK).parse_portfolio_records)
        built = _page(PH)
        with pytest.raises(AssertionError):
            _assert_a(built, len(_ALL_BLANK))

    def test_d_every_mutation_point_still_exists_exactly_once(self):
        for mod, pair in ((PH, _PH_KEEP), (HS, _HS_PASS), (GSP, _GSP_PASS), (GSP, _GSP_BLANK)):
            _mutant(mod, pair)


# ══════════════════════════════════════════════════════════════════
# Q3-r8：`sheet` fixture 的深度分析替身（`lambda rows, **_k: None`）要真的模擬「回 None」
# ══════════════════════════════════════════════════════════════════
#: Q3 起頁面以 `get_portfolio_var(rows, strict=True)` 呼叫；替身若不收 `strict`，
#: `_guarded` 會把 TypeError 轉成 `var_error` —— VaR 那格被**悄悄**換成「拋例外」紅卡，
#: 本檔所有經過 `_page()` 的比對就不再是在測「回 None」那條路。本段守住替身的前提本身。
class TestQ3r8DeepDoublesReturnNone:
    def _deep(self, sheet):
        sheet(**_GENUINE["bound_all_valid"])
        h = PH.load_holdings(_REQ)
        return PH.load_deep(PH.load_station(h))

    def test_all_three_doubles_ran_and_returned_none(self, sheet):
        dp = self._deep(sheet)
        assert dp.requested and dp.has_station_rows, "前提：真的走到三支 L3（有戰情表列）"
        assert (dp.stress_error, dp.var_error, dp.cash_error) == ("", "", ""), (
            "替身拋例外了（多半是頁面呼叫多了參數、替身沒收）："
            f"stress={dp.stress_error!r} var={dp.var_error!r} cash={dp.cash_error!r}")
        assert (dp.stress, dp.var, dp.cash) == (None, None, None)

    def test_var_card_is_not_the_raised_red_card(self, sheet):
        dp = self._deep(sheet)
        card = PH.build_var_card(dp)[0]
        assert "TypeError" not in repr(card), card

    def test_doubles_accept_every_kwarg_the_page_passes(self, sheet, monkeypatch):
        """頁面對三支 L3 傳的關鍵字參數，替身都要收（逐支記錄實際呼叫）。"""
        import src.services.portfolio_deep_service as D
        sheet(**_GENUINE["bound_all_valid"])
        seen: dict = {}
        for fn in ("get_portfolio_stress", "get_portfolio_var", "get_dividend_cash_flow"):
            double = getattr(D, fn)

            def _rec(rows, _fn=fn, _d=double, **kw):
                seen[_fn] = kw
                return _d(rows, **kw)
            monkeypatch.setattr(D, fn, _rec)
        dp = PH.load_deep(PH.load_station(PH.load_holdings(_REQ)))
        assert set(seen) == {"get_portfolio_stress", "get_portfolio_var", "get_dividend_cash_flow"}
        assert seen["get_portfolio_var"] == {"strict": True}, seen
        assert dp.var_error == "", dp.var_error
