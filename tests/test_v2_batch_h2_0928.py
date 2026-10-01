"""批 H2（2026-09-28）v1「💼 我的持股戰情室」文字指引修正的守衛：H1-f5／H1-f6／H1-f7。

  · H1-f5：`etf_tab_dividend_station._render_allocation_take_profit()`（80/20）——
    L3 `compute_allocation_split()` 只看「市值 > 0」，而市值 = 張數 × 現價（L3 `build_station_rows`）
    ⇒ 缺**現價**的不納入、只缺**均價**的照樣納入。修前部分納入註記「缺張數/均價未納入計算」
    兩頭都錯 ⇒ 改用同檔卡①既有的「缺張數／均價／現價」；算不出來那一句的句尾
    「到 📁 組合管理的 Portfolio 填張數/均價即可顯示。」對「全部只缺現價」是錯的指引
    ⇒ 換成同檔既有的條件子句 `_IF_LOTS_AVG_MISSING_WHERE` ＋「。」。
  · H1-f6：`etf_tab_dividend_station._render_layer1()` 卡①「算不出來」那一句 ——
    句尾「到 📁 組合管理的 Portfolio 補齊才會出現。」→ 同一條件子句 ＋「。」；
    持有列**全部**整批抓取失敗時整句不出，只留既有的「⚠️ 另有 N 檔整批抓取失敗，未納入任何判斷。」。
  · H1-f7：`page_hold.load_holdings()` docstring 引用的金額列字樣改成現行字樣。

本檔兩類測試（沿用批 W `tests/test_v2_batch_w_0928.py` 的標法）：
  · **修前會紅**：直接釘住本批修掉的錯誤字樣／行為。
  · **修後不變守衛**（修前本來就綠）：釘住本批 ⛔ 不准順手改到的既有文字／行為，
    有效性靠**突變驗證**；每一條的 docstring 以「修後不變守衛」開頭標明。
  ⚠️ 修前（`7020d13`）上實跑本檔 19 條：15 紅 4 綠（4 綠即標明的修後不變守衛）——
     這是**量測值**（2026-09-28，含 QA N2 補的一條）；增刪測試時請重跑、⛔ 不要沿用。

列一律走**真的** L3 `build_station_rows()`（`metrics_fn` 注入、全離線、不打網路）——
市值 / 張數 / 均價 / 現價 / 整批抓取失敗列都由 L3 產生，本檔不手捏 row 的形狀。
畫面文字以假的 `st` 攔下（**不啟動 Streamlit runtime**），手法同批 W 的 H1-f4 守衛。
"""
from __future__ import annotations

import ast
import contextlib
import pathlib
import re

import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from src.services import dividend_station_service as svc
from src.ui.etf import etf_tab_dividend_station as V1
from src.ui.render import station_cards as SC
from src.ui.views import page_hold as P

#: 條件子句原文。⚠️ 刻意在測試裡**寫死**（同批 W）：常數被改了一個位元組，下面就會紅。
_CLAUSE = "若是缺張數／均價，到既有的 📁 組合管理分頁補齊"
#: 卡①「算不出來」那一句（批 H2 後）。
_TOTALS_NONE = ("未實現損益與總市值算不出來：持股沒有張數／均價／現價。"
                "§1 這裡**不填 0** —— " + _CLAUSE + "。")
#: 80/20 算不出來那一句（批 H2 後；前一句一字未動）。
#: 批 H3 H1-f9（2026-10-01）：半形「張數/均價」統一為全形「張數／均價」；
#:    持有列全部整批抓取失敗的那一種改走另一句，守衛移到 `tests/test_v2_batch_h3_1001.py`。
_ALLOC_NONE = ("📊 80/20 配置偏離：你的持股未帶張數／均價（或無市值）→ 無法計算實際佔比。"
               + _CLAUSE + "。")
#: 80/20 算得出來時的近似法說明（修前修後一字未動）。
_ALLOC_APPROX = "核心=ETF、衛星=個股（依代號近似;若你把主題型 ETF 當衛星,此偏離僅供參考）。"

_E, _S = T.KIND_ETF, T.KIND_STOCK


# ══════════════════════════════════════════════════════════════════
# 夾具：真的 L3 列 ＋ 假的 st
# ══════════════════════════════════════════════════════════════════
def _weekly(n: int = 60) -> pd.Series:
    _idx = pd.date_range("2024-01-07", periods=n, freq="W-SUN")
    return pd.Series([100.0] * n, index=_idx)


def _rows(*spec) -> list[dict]:
    """spec：`(代號, 種類, held, 張數, 均價, 現價, 整批抓取失敗?)` → L3 `build_station_rows()` 的列。"""
    _holdings, _m = [], {}
    for _tk, _kind, _held, _lots, _avg, _cur, _fail in spec:
        _holdings.append({"ticker": _tk, "name": _tk, "asset_kind": _kind, "held": _held,
                          "asset_class": T.ASSET_CORE if _kind == _E else T.ASSET_SATELLITE,
                          "lots": _lots, "avg_price": _avg})
        _m[_tk] = (_cur, _fail)

    def _metrics(tk, ak):
        _cur, _fail = _m[tk]
        if _fail:
            raise RuntimeError("HTTPError: 404")      # → L3 `_error_row`（整批抓取失敗）
        if ak == _S:
            return {"mj_grade": "A", "mj_score_pct": 88, "mj_headline": "體質佳",
                    "mj_fail_items": [], "kd_state": {"k": 70.0, "d": 65.0, "label": "無"},
                    "current_price": _cur}
        return {"weekly_close": _weekly(), "current_price": _cur}

    return svc.build_station_rows(_holdings, vix=17.3, metrics_fn=_metrics)


class _CapturingST:
    """假的 `st` —— 依序收 markdown／info／caption／success／warning 的文字。"""

    def __init__(self) -> None:
        self.out: list[tuple[str, str]] = []

    def markdown(self, body="", **_kw) -> None:
        self.out.append(("markdown", str(body)))

    def info(self, body="", **_kw) -> None:
        self.out.append(("info", str(body)))

    def caption(self, body="", **_kw) -> None:
        self.out.append(("caption", str(body)))

    def success(self, body="", **_kw) -> None:
        self.out.append(("success", str(body)))

    def warning(self, body="", **_kw) -> None:
        self.out.append(("warning", str(body)))

    def columns(self, spec, **_kw):
        return [contextlib.nullcontext()
                for _ in range(spec if isinstance(spec, int) else len(spec))]


def _card1_note(monkeypatch, rows) -> str | None:
    """卡①「這個組合現在該做什麼」的 note 那一段；沒有 note → `None`。"""
    fake = _CapturingST()
    monkeypatch.setattr(V1, "st", fake)
    monkeypatch.setattr(SC, "st", fake)            # 卡①由 L4 `render_conclusion_card` 畫
    V1._render_layer1(rows, 17.3)
    cards = [b for _k, b in fake.out if "這個組合現在該做什麼" in b]
    assert len(cards) == 1, fake.out
    m = re.search(r'<div class="dsl-sub" style="margin-top:8px">(.*?)</div>', cards[0])
    return m.group(1) if m else None


def _alloc_out(monkeypatch, rows) -> list[tuple[str, str]]:
    """80/20 ＋ 衛星停利那一段畫出來的 `(元件, 文字)`，依序。"""
    fake = _CapturingST()
    monkeypatch.setattr(V1, "st", fake)
    V1._render_allocation_take_profit(rows)
    return fake.out


def _captions(out) -> list[str]:
    return [b for _k, b in out if _k == "caption"]


def _code_str_literals(path: pathlib.Path) -> list[str]:
    """`path` 裡**程式碼**的字串常值（排除 docstring 與其他單獨成句的字串；註解本來就不在 AST）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    _docs = {id(_n.value) for _n in ast.walk(tree)
             if isinstance(_n, ast.Expr) and isinstance(_n.value, ast.Constant)
             and isinstance(_n.value.value, str)}
    return [_n.value for _n in ast.walk(tree)
            if isinstance(_n, ast.Constant) and isinstance(_n.value, str) and id(_n) not in _docs]


_FULL = ("0050.TW", _E, True, 10.0, 140.0, 150.0, False)


# ══════════════════════════════════════════════════════════════════
# H1-f6：卡①「算不出來」—— 三種情形
# ══════════════════════════════════════════════════════════════════
class TestH1f6Card1TotalsNone:
    def test_all_missing_lots_and_avg(self, monkeypatch):
        rows = _rows(("0050.TW", _E, True, None, None, 150.0, False),
                     ("2330", _S, True, None, None, 600.0, False))
        assert svc.compute_portfolio_totals(rows) is None          # 前提：走「算不出來」
        note = _card1_note(monkeypatch, rows)
        assert note == _TOTALS_NONE, note
        assert "Portfolio 補齊才會出現" not in note

    def test_all_missing_price_only(self, monkeypatch):
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, None, False),
                     ("2330", _S, True, 2.0, 500.0, None, False))
        # 前提：真的是「只缺現價」—— 張數／均價都在，L3 仍判算不出來（修的就是這一種）。
        assert all(r["張數"] and r["均價"] and r["現價"] is None for r in rows)
        assert svc.compute_portfolio_totals(rows) is None
        note = _card1_note(monkeypatch, rows)
        assert note == _TOTALS_NONE, note
        assert "Portfolio 補齊才會出現" not in note

    def test_all_fetch_failed_keeps_only_the_failure_sentence(self, monkeypatch):
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, 150.0, True),
                     ("2330", _S, True, 2.0, 500.0, 600.0, True))
        assert all((r.get("_detail") or {}).get("error") for r in rows)   # 前提：兩列都是失敗列
        note = _card1_note(monkeypatch, rows)
        # 只剩既有那一句，⛔ 不說持股缺資料；句首 ⛔ 不帶全形空白分隔。
        assert note == "⚠️ 另有 2 檔整批抓取失敗，未納入任何判斷。", note

    def test_held_rows_all_failed_while_watchlist_ok(self, monkeypatch):
        """持有列全失敗、觀察清單抓到了 —— 算不出損益的原因仍是持有列抓不到（L3 只算持有列）。"""
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, 150.0, True),
                     ("0056.TW", _E, False, None, None, 35.0, False))
        note = _card1_note(monkeypatch, rows)
        assert note == "⚠️ 另有 1 檔整批抓取失敗，未納入任何判斷。", note

    def test_some_held_failed_rest_missing_price_keeps_both_sentences(self, monkeypatch):
        """還有沒失敗的持有列（只缺現價）⇒「持股缺資料」那一句要留，失敗那一句接在後面。"""
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, 150.0, True),
                     ("2330", _S, True, 2.0, 500.0, None, False))
        note = _card1_note(monkeypatch, rows)
        assert note == _TOTALS_NONE + "　⚠️ 另有 1 檔整批抓取失敗，未納入任何判斷。", note

    def test_held_rows_fetched_but_watchlist_failed_keeps_the_sentence(self, monkeypatch):
        """持有列都抓到了（只缺現價）、觀察清單那檔整批抓取失敗 ⇒「持股缺資料」那一句要留，
        失敗那一句接在後面（批 H2 QA N2）。

        ⚠️ 檔數刻意取「失敗列數 ≥ 持有列數，但沒有一列持有列失敗」：判的是**持有列本身**失敗與否
        （照抄 L3 跳過條件），⛔ 不是拿失敗列數去比持有列數 —— QA 突變 M5
        （判法改成 `_err_n >= len(_held)`）在本檔其他條都存活，這一條會轉紅。
        """
        rows = _rows(("0050.TW", _E, True, 10.0, 140.0, None, False),
                     ("0056.TW", _E, False, None, None, 35.0, True))
        _held = [r for r in rows if r.get("held")]
        _failed = [r for r in rows if (r.get("_detail") or {}).get("error")]
        # 前提：持有列沒有一列失敗、只缺現價；失敗的那一列是觀察清單；兩邊檔數相等。
        assert [r["代號"] for r in _held] == ["0050.TW"]
        assert not (_held[0].get("_detail") or {}).get("error")
        assert _held[0]["張數"] and _held[0]["均價"] and _held[0]["現價"] is None
        assert [(r["代號"], r["held"]) for r in _failed] == [("0056.TW", False)]
        assert len(_failed) >= len(_held)
        assert svc.compute_portfolio_totals(rows) is None          # 走「算不出來」
        note = _card1_note(monkeypatch, rows)
        assert note == _TOTALS_NONE + "　⚠️ 另有 1 檔整批抓取失敗，未納入任何判斷。", note

    @pytest.mark.parametrize("watch_failed", [False, True], ids=["watch_ok", "watch_failed"])
    def test_no_held_rows_still_gets_the_sentence(self, monkeypatch, watch_failed):
        """沒有任何持有列（只有觀察清單）：不在本批範圍 ⇒ 照修前出這一句（只換句尾）——
        觀察清單有一檔抓取失敗也一樣（失敗的不是持有列，⛔ 不因此把這一句拿掉）。"""
        rows = _rows(("0056.TW", _E, False, None, None, 35.0, False),
                     *([("00878.TW", _E, False, None, None, 20.0, True)] if watch_failed else []))
        note = _card1_note(monkeypatch, rows)
        assert note == _TOTALS_NONE + (
            "　⚠️ 另有 1 檔整批抓取失敗，未納入任何判斷。" if watch_failed else ""), note


class TestH1f6Card1Unchanged:
    def test_partial_note_is_unchanged(self, monkeypatch):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：批 W H1-f4 的 partial 註記一字不動。"""
        note = _card1_note(monkeypatch, _rows(_FULL, ("2330", _S, True, 2.0, 500.0, None, False)))
        assert note == ("⚠️ 1/2 檔持股缺張數／均價／現價，**沒有**納入損益與市值 —— "
                        "上面兩個金額只涵蓋其餘 1 檔。" + _CLAUSE + "。"), note

    def test_all_valued_has_no_note(self, monkeypatch):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：全部算得出來 ⇒ 卡①沒有 note。"""
        assert _card1_note(monkeypatch, _rows(_FULL)) is None


# ══════════════════════════════════════════════════════════════════
# H1-f5：80/20 —— 部分納入（缺現價不納入、缺均價仍納入）＋ 算不出來三種情形
# ══════════════════════════════════════════════════════════════════
class TestH1f5AllocationPartial:
    def test_missing_price_is_not_counted_and_note_says_price(self, monkeypatch):
        rows = _rows(_FULL, ("2330", _S, True, 2.0, 500.0, None, False))
        _a = svc.compute_allocation_split(rows)
        assert (_a["held_n"], _a["valued_n"], _a["partial"]) == (2, 1, True)   # 前提：缺現價不納入
        caps = _captions(_alloc_out(monkeypatch, rows))
        assert caps == [_ALLOC_APPROX + "　⚠️ 另有 1/2 檔缺張數／均價／現價未納入計算。"], caps
        assert "缺張數/均價未納入計算" not in caps[0]

    def test_missing_lots_is_not_counted(self, monkeypatch):
        rows = _rows(_FULL, ("2330", _S, True, None, 500.0, 600.0, False))
        caps = _captions(_alloc_out(monkeypatch, rows))
        assert caps == [_ALLOC_APPROX + "　⚠️ 另有 1/2 檔缺張數／均價／現價未納入計算。"], caps

    def test_missing_avg_is_still_counted(self, monkeypatch):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：只缺均價 ⇒ 照樣納入、⛔ 不出部分納入註記。"""
        rows = _rows(_FULL, ("2330", _S, True, 2.0, None, 600.0, False))
        _a = svc.compute_allocation_split(rows)
        assert (_a["held_n"], _a["valued_n"], _a["partial"]) == (2, 2, False)
        assert _a["sat_pct"] > 0                       # 2330（衛星）的市值真的進了分子
        out = _alloc_out(monkeypatch, rows)
        assert _captions(out) == [_ALLOC_APPROX], out
        assert any(f"🚀衛星 {_a['sat_pct']:.0f}%" in b for _k, b in out if _k == "warning"), out


class TestH1f5AllocationNone:
    @pytest.mark.parametrize("spec", [
        (("0050.TW", _E, True, None, None, 150.0, False),
         ("2330", _S, True, None, None, 600.0, False)),
        (("0050.TW", _E, True, 10.0, 140.0, None, False),
         ("2330", _S, True, 2.0, 500.0, None, False)),
    ], ids=["all_missing_lots_avg", "all_missing_price"])
    def test_caption_ends_on_the_conditional_clause(self, monkeypatch, spec):
        rows = _rows(*spec)
        assert svc.compute_allocation_split(rows) is None           # 前提：走「算不出來」
        caps = _captions(_alloc_out(monkeypatch, rows))
        assert caps == [_ALLOC_NONE], caps
        assert "填張數/均價即可顯示" not in caps[0]


# ══════════════════════════════════════════════════════════════════
# 條件子句在 v1 只准有一份原文（三處共用 `_IF_LOTS_AVG_MISSING_WHERE`）
# ══════════════════════════════════════════════════════════════════
class TestClauseSharedInV1:
    def test_the_clause_is_written_once_in_v1(self):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：本批新增的兩處改用常數、⛔ 不逐字再抄。

        只數程式碼裡的字串常值；註解與 docstring 引用 ⛔ 不算。
        """
        n = sum(_s.count(_CLAUSE) for _s in _code_str_literals(pathlib.Path(V1.__file__)))
        assert n == 1, "條件子句又被逐字抄了一份（應共用 `_IF_LOTS_AVG_MISSING_WHERE`）"

    def test_old_guides_are_gone_from_v1_code(self):
        _lits = "".join(_code_str_literals(pathlib.Path(V1.__file__)))
        for _old in ("Portfolio 補齊才會出現", "填張數/均價即可顯示", "缺張數/均價未納入計算"):
            assert _old not in _lits, _old


# ══════════════════════════════════════════════════════════════════
# H1-f7：`load_holdings()` docstring 引用的金額列字樣 = 現行字樣
# ══════════════════════════════════════════════════════════════════
class TestH1f7LoadHoldingsDoc:
    def test_docstring_quotes_the_live_totals_wording(self):
        _doc = re.sub(r"\n\s*", "", P.load_holdings.__doc__ or "")
        assert "缺張數或均價，沒有納入" not in _doc
        _quote = "檔持股缺張數／均價／現價，沒有納入"
        assert _quote in _doc, _doc
        # 引的是 `_totals_facts()` 現行那一句（去掉粗體記號後逐字相同）。
        _rows_ = _rows(_FULL, ("2330", _S, True, 2.0, 500.0, None, False))
        st_ = P.StationReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                               rows=tuple(_rows_),
                               totals=svc.compute_portfolio_totals(_rows_))
        _live = dict(P._totals_facts(st_))["⚠️ 上面兩個金額只涵蓋一部分"].replace("**", "")
        assert _quote in _live, _live
