"""Q2：「💼 我的持股」⑤ 80/20 `hold.alloc_split` ＋ ⑥ 核心／衛星 `hold.deep.core_satellite`
—— 「取數失敗」與「真的算不出比例」必須分得開。

（客戶 2026-09-26 批次授權「失敗被當成沒結果」的所有卡；⛔ 不新造文案（K1）；⛔ 不動版面。）

根因（L3 `dividend_station_service.compute_allocation_split`，本批 ⛔ 未改）：
  · 整批抓取失敗的持有列（`_detail.error`）被**整列跳過** —— 連 `held_n` 都不計，所以
    連 `partial` 都不會標 ⇒ 全部失敗時回 `None`，部分失敗時回一個**沒講它漏了哪幾檔**的比例；
  · 現價抓不到的持有列（`現價` 為 None，L3 不標 `_detail.error`，見批次 4）因 `市值` 為 None
    不進分子分母 ⇒ 同上。
  ⇒ 卡片原本落在灰卡 `SPLIT_NO_VALUE_NOW`「**這是一個有效的結果**」（全部失敗），
    或畫成 live 的比例（部分失敗）。

修法只在 L5（`_split_uncounted` ＋ `_split_state`，兩張卡共用同一個判定）：
  · 有任一持有列整批抓取失敗、或連現價都沒有 → 既有紅卡 `SPLIT_FAILED_NOW`，
    why 摘自 L0 `MISS_TEXT`（與 ⑤ 衛星停利卡同一條失敗路徑**逐字同一套**），
    where 用既有 `STATION_ERROR_WHERE`；
  · 有現價、只是缺張數 → **缺輸入**，照舊灰卡（原文本來就指去補張數）。

每條路徑五件事：
  (a) 全部失敗 → 紅；
  (b) 部分失敗 → 紅（⛔ 不畫那個不完整的比例）；
  (c) 真的沒有（缺張數／沒持股／只有觀察清單）→ 與改前 byte-identical；
  (d) 既有呼叫端（不傳任何新參數 —— 本批沒有新增參數）回傳值不變：L3 簽章與輸出不變、
      其他所有持股卡輸出逐位元組不變；
  (e) 突變：拔掉本批守衛 → (a)/(b) 必須轉紅。
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import pathlib
import sys
import types

import pytest

import src.services.dividend_station_service as S
from shared import dividend_station_thresholds as T
from shared.station_specs import MISS_FETCH_FAILED, MISS_NO_INPUT, MISS_TEXT
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_IDLE, UI_LIVE
from src.ui.views import page_hold as PH

_VALID = "有效的結果"
_SPLIT_KEYS = ("hold.alloc_split", "hold.deep.core_satellite")
#: 兩句 why（摘自 L0 `MISS_TEXT`，只刪開頭的單數主詞）—— 與 ⑤ 衛星停利卡同一套。
#: 現價抓不到那一句**另刪句尾**「，可以重跑一次。」（總管裁定：快取 1 小時內那半句不成立）。
_WHOLE_ROW_TEXT = MISS_TEXT[MISS_FETCH_FAILED].removeprefix("這一檔")
_NO_PRICE_TEXT = MISS_TEXT[MISS_NO_INPUT].removeprefix("這盞燈").split("，", 1)[0]


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 的原始碼裡每一組 `old` **恰好一處**換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b8_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


#: 本批守衛整段中和（＝本批之前的行為）。
_REVERT = (("_uncounted = _failed + _unpriced", "_uncounted = ()"),)


def _station(P, rows, split=None, **kw):
    return P.StationReadout(requested=True, submitted=True, bound=True,
                            holdings_n=len(rows), rows=tuple(rows), split=split, **kw)


def _both(P, st_):
    return P.build_allocation_split_card(st_), P.build_core_satellite_card(st_)


def _l3_split(rows):
    """真的走 L3 `compute_allocation_split`（本批 ⛔ 未改）。"""
    return PH._digest_map(S.compute_allocation_split(list(rows)))


# 與 L3 `build_station_rows` 產出的列同形（只留兩張卡讀到的欄位）。
_ETF_OK = {"代號": "0056", "種類": "ETF", "held": True, "現價": 35.0, "張數": 3.0,
           "市值": 105.0, "_detail": {}}
_SAT_OK = {"代號": "2330", "種類": "個股", "held": True, "現價": 100.0, "張數": 1.0,
           "市值": 100.0, "_detail": {}}
_ETF_ERR = {"代號": "00878", "種類": "ETF", "held": True, "_detail": {"error": "HTTPError 502"}}
_SAT_ERR = {"代號": "6505", "種類": "個股", "held": True, "_detail": {"error": "HTTPError 502"}}
_SAT_NO_PRICE = {"代號": "2454", "種類": "個股", "held": True, "現價": None, "張數": 1.0,
                 "市值": None, "_detail": {}}
_SAT_NO_LOTS = {"代號": "3008", "種類": "個股", "held": True, "現價": 150.0, "張數": None,
                "市值": None, "_detail": {}}
_WATCH_ERR = dict(_SAT_ERR, 代號="2603", held=False)
_WATCH_NO_PRICE = dict(_SAT_NO_PRICE, 代號="2609", held=False)


# ══════════════════════════════════════════════════════════════════
# 根因釘住：L3 對取數失敗的持有列是**跳過**的（本批刻意不改 L3）
# ══════════════════════════════════════════════════════════════════
class TestRootCauseInL3:
    def test_all_error_rows_make_l3_return_none(self):
        assert S.compute_allocation_split([_ETF_ERR, _SAT_ERR]) is None

    def test_an_error_row_is_silently_dropped_without_partial(self):
        sp = S.compute_allocation_split([_SAT_OK, _ETF_ERR])
        assert sp is not None and sp["partial"] is False and sp["held_n"] == 1, (
            "整批失敗的那一檔連分母都不進 —— 比例看起來是完整的（這就是 live 說謊的來源）")

    def test_price_missing_only_makes_l3_return_none(self):
        assert S.compute_allocation_split([_SAT_NO_PRICE]) is None


# ══════════════════════════════════════════════════════════════════
# (a) 全部失敗 → 紅
# ══════════════════════════════════════════════════════════════════
def _assert_red(built, why):
    card, _facts, sig = built
    assert card.state == UI_FAILED and card.state != UI_EMPTY
    assert card.note.now == PH.SPLIT_FAILED_NOW
    assert card.note.now != PH.SPLIT_NO_VALUE_NOW
    assert _VALID not in card.note.why
    assert card.note.why == why
    assert card.note.where == PH.STATION_ERROR_WHERE
    assert card.value == "" and sig == ""
    html = PH.v2_card_html(*built)
    assert PH.SPLIT_NO_VALUE_NOW.strip("*") not in html
    assert PH._V2_BLANK_LINE_RE.sub("\n", html) == html, "卡面文字含空行（空行守衛）"


class TestAllFailedIsRed:
    @pytest.mark.parametrize("rows,why", [
        ((_ETF_ERR,), f"00878：{_WHOLE_ROW_TEXT}"),
        ((_ETF_ERR, _SAT_ERR), f"00878、6505：{_WHOLE_ROW_TEXT}"),
        ((_SAT_NO_PRICE,), f"2454：{_NO_PRICE_TEXT}"),
        ((_SAT_ERR, _SAT_NO_PRICE), f"6505：{_WHOLE_ROW_TEXT}2454：{_NO_PRICE_TEXT}"),
        # 現價抓不到時，張數有沒有填都算不出市值 —— 取數失敗優先（同批次 4）。
        ((dict(_SAT_NO_PRICE, 張數=None),), f"2454：{_NO_PRICE_TEXT}"),
    ], ids=["one_error", "two_errors", "no_price", "error_and_no_price", "no_price_no_lots"])
    def test_a_all_held_rows_uncounted_is_red_on_both_cards(self, rows, why):
        st_ = _station(PH, rows, _l3_split(rows))
        assert st_.split is None, "前提：L3 回 None（原本畫成灰卡「有效的結果」）"
        for built in _both(PH, st_):
            _assert_red(built, why)

    def test_a_several_codes_are_listed_and_not_called_one(self):
        why = PH.build_allocation_split_card(_station(PH, (_ETF_ERR, _SAT_ERR)))[0].note.why
        assert "這一檔" not in why and "這盞燈" not in why

    def test_a_face_uses_the_existing_excerpts(self):
        face = dict(PH.v2_short_rows(
            PH.build_allocation_split_card(_station(PH, (_SAT_ERR, _SAT_NO_PRICE)))[0])[0])
        assert face[PH.V2_WHY_FACT_KEY] == (
            "整批抓取失敗 —— 看該列的錯誤訊息" + PH.V2_EXCERPT_GAP
            + "需要的數字沒抓到 —— 通常是上游來源這輪失敗")
        assert face[PH.V2_GUIDE_FACT_KEY] == "先確認網路與 Google 授權是否仍有效"

    def test_a_same_page_same_failure_same_words_as_take_profit(self):
        """同一頁、同一檔、同一條失敗路徑 ⛔ 不給兩種說法（⑤ 停利卡批次 1／4 的 why）。"""
        st_ = _station(PH, (_SAT_ERR, _SAT_NO_PRICE))
        assert (PH.build_allocation_split_card(st_)[0].note.why
                == PH.build_take_profit_card(st_)[0].note.why)

    def test_a_station_exception_still_wins_and_keeps_its_note(self):
        st_ = PH.StationReadout(requested=True, submitted=True, bound=True, holdings_n=1,
                                rows=(_SAT_NO_PRICE,), error="RuntimeError('Google 502')")
        for card, _f, _s in _both(PH, st_):
            assert card.state == UI_FAILED and "Google 502" in card.note.why
            assert _NO_PRICE_TEXT not in card.note.why
            assert card.note.where != PH.STATION_ERROR_WHERE

    def test_a_through_the_real_l3_rows(self):
        """真的走 L3 `build_station_rows` ＋ `build_station_digest`（逐檔 metrics 全部失敗）。"""
        def _boom(tk, ak):
            raise ConnectionError("yfinance 429")

        hold = [{"ticker": "0056", "asset_kind": T.KIND_ETF, "held": True, "lots": 3,
                 "avg_price": 30.0},
                {"ticker": "2330", "asset_kind": T.KIND_STOCK, "held": True, "lots": 1,
                 "avg_price": 100.0}]
        rows = S.build_station_rows(hold, vix=18.0, metrics_fn=_boom)
        dg = S.build_station_digest(rows, 18.0)
        assert dg["allocation"] is None
        st_ = _station(PH, rows, PH._digest_map(dg["allocation"]))
        for built in _both(PH, st_):
            _assert_red(built, f"0056、2330：{_WHOLE_ROW_TEXT}")

    def test_a_end_to_end_through_load_station(self, monkeypatch):
        """`load_station` → L3 `get_station_rows`（逐檔 metrics 由測試替換成「現價抓不到」）。"""
        monkeypatch.setattr(S, "fetch_vix", lambda *a, **k: 18.0)
        monkeypatch.setattr(S, "fetch_metrics", lambda tk, ak: {
            "mj_grade": None, "mj_score_pct": None, "mj_headline": "", "mj_fail_items": [],
            "kd_state": None, "current_price": None, "name": tk, "trend_verdict": None})
        st_ = PH.load_station(PH.HoldingsReadout(
            requested=True, submitted=True, bound=True,
            holdings=({"ticker": "2454", "asset_kind": T.KIND_STOCK, "held": True,
                       "lots": 1, "avg_price": 100.0},)))
        assert not st_.error and st_.split is None
        for built in _both(PH, st_):
            _assert_red(built, f"2454：{_NO_PRICE_TEXT}")


# ══════════════════════════════════════════════════════════════════
# (b) 部分失敗 → 紅（⛔ 不畫不完整的比例）
# ══════════════════════════════════════════════════════════════════
class TestPartialFailureIsRed:
    @pytest.mark.parametrize("rows,why", [
        ((_ETF_OK, _SAT_ERR), f"6505：{_WHOLE_ROW_TEXT}"),
        ((_ETF_OK, _SAT_NO_PRICE), f"2454：{_NO_PRICE_TEXT}"),
        ((_ETF_OK, _SAT_OK, _ETF_ERR, _SAT_NO_PRICE),
         f"00878：{_WHOLE_ROW_TEXT}2454：{_NO_PRICE_TEXT}"),
    ], ids=["error_row", "no_price", "both"])
    def test_b_some_counted_some_failed_is_red_not_a_live_ratio(self, rows, why):
        st_ = _station(PH, rows, _l3_split(rows))
        assert st_.split is not None, "前提：L3 算得出一個（不完整的）比例"
        for built in _both(PH, st_):
            _assert_red(built, why)
            facts = dict(built[1])
            assert "核心偏離目標" not in facts and "納入計算的市值（元·張價）" not in facts
            assert "核心 " not in built[0].value

    def test_b_the_error_row_partial_was_live_before_this_batch(self):
        """前提自證：修前那一例是 live（整批失敗的那一檔被靜默丟掉，連 partial 都沒標）。"""
        rows = (_ETF_OK, _SAT_ERR)
        old = _mutant(PH, *_REVERT)
        for built in _both(old, _station(old, rows, _l3_split(rows))):
            assert built[0].state == UI_LIVE


# ══════════════════════════════════════════════════════════════════
# 總管裁定 1：現價抓不到那一句截掉「，可以重跑一次。」—— ⑤⑥ 與停利卡兩處同一句
# ══════════════════════════════════════════════════════════════════
_PARTIAL_LABEL = "⚠️ 這個比例只涵蓋一部分"


class TestRerunClauseTruncated:
    def test_1_the_sentence_is_the_l0_text_cut_at_the_first_comma_only(self):
        full = MISS_TEXT[MISS_NO_INPUT]
        assert PH.NO_PRICE_WHY == "需要的數字沒抓到 —— 通常是上游來源這輪失敗"
        # 只刪不加：是原文去掉開頭主詞後的**逐字前綴**，且剛好停在第一個「，」前。
        assert full.removeprefix("這盞燈").startswith(PH.NO_PRICE_WHY)
        assert full.removeprefix("這盞燈")[len(PH.NO_PRICE_WHY)] == "，"
        assert "，" not in PH.NO_PRICE_WHY and "重跑" not in PH.NO_PRICE_WHY

    def test_1_split_cards_and_take_profit_say_the_same_truncated_sentence(self):
        st_ = _station(PH, (_SAT_NO_PRICE,))
        tp = PH.build_take_profit_card(st_)[0]
        assert tp.state == UI_FAILED
        for card, _f, _s in _both(PH, st_):
            assert card.note.why == tp.note.why == f"2454：{PH.NO_PRICE_WHY}"
            assert "重跑" not in card.note.why

    def test_1_both_failures_together_still_read_as_two_sentences(self):
        why = PH.build_allocation_split_card(_station(PH, (_SAT_ERR, _SAT_NO_PRICE)))[0].note.why
        assert why == ("6505：整批抓取失敗 —— 看該列的錯誤訊息，多半是代號或來源問題。"
                       "2454：需要的數字沒抓到 —— 通常是上游來源這輪失敗")


# ══════════════════════════════════════════════════════════════════
# 總管裁定 2：紅卡不畫比例 ⇒「這個比例只涵蓋一部分」紅態不渲染；非紅照舊
# ══════════════════════════════════════════════════════════════════
class TestPartialFactNotOnRed:
    def test_2_red_partial_does_not_show_the_partial_ratio_line(self):
        rows = (_ETF_OK, _SAT_NO_PRICE)
        st_ = _station(PH, rows, _l3_split(rows))
        assert st_.split["partial"] is True, "前提：L3 標了 partial（修前這一列會出現在紅卡上）"
        for built in _both(PH, st_):
            assert built[0].state == UI_FAILED
            assert _PARTIAL_LABEL not in dict(built[1])
            assert "只算了" not in PH.v2_card_html(*built)

    def test_2_live_partial_still_discloses_it(self):
        rows = (_ETF_OK, _SAT_NO_LOTS)
        st_ = _station(PH, rows, _l3_split(rows))
        for built in _both(PH, st_):
            assert built[0].state == UI_LIVE
            assert dict(built[1])[_PARTIAL_LABEL] == "2 檔持有列裡只算了 1 檔（其餘缺金額）—— **僅供參考**"


# ══════════════════════════════════════════════════════════════════
# (c) 真的沒有 → 與改前 byte-identical
# ══════════════════════════════════════════════════════════════════
def _fp(P, built) -> str:
    card, facts, sig = built
    return repr((card, tuple(facts), sig)) + P.v2_card_html(card, facts, sig)


def _genuine_stations(P):
    """沒有任何「持有列取數失敗」的輸入 —— 本批 ⛔ 不得改動其中任何一張卡。"""
    def s(rows, **kw):
        return _station(P, rows, _l3_split(rows), **kw)

    return [
        s((_SAT_NO_LOTS,)),                                   # 有現價、缺張數 → 缺輸入
        s((_SAT_NO_LOTS, dict(_SAT_NO_LOTS, 代號="2412"))),
        s((_ETF_OK, _SAT_NO_LOTS)),                           # 部分缺張數 → live＋partial
        s((_ETF_OK, _SAT_OK)),
        s((_ETF_OK,)),
        s((_WATCH_ERR,)),                                     # 只有觀察清單（抓不到也不進 80/20）
        s((_WATCH_NO_PRICE, _WATCH_ERR)),
        s((_ETF_OK, _WATCH_ERR, _WATCH_NO_PRICE)),
        s((dict(_SAT_NO_LOTS, held=False),)),
        s(()),                                                # 持股 0 檔
        P.StationReadout(requested=True, submitted=True, bound=False),
        P.StationReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                         error="RuntimeError('boom')"),
        P.StationReadout(requested=False, submitted=True),
        P.StationReadout(requested=False, submitted=False),
    ]


class TestGenuineEmptyUnchanged:
    def test_c_missing_lots_is_missing_input_and_stays_grey(self):
        for card, _f, _s in _both(PH, _station(PH, (_SAT_NO_LOTS,))):
            assert card.state == UI_EMPTY and card.note.now == PH.SPLIT_NO_VALUE_NOW
            assert card.note.why.startswith("**這是一個有效的結果**（已經算過，不是還沒算）")

    def test_c_watchlist_failures_do_not_touch_the_split(self):
        for card, _f, _s in _both(PH, _station(PH, (_WATCH_ERR, _WATCH_NO_PRICE))):
            assert card.state == UI_EMPTY and card.note.now == PH.SPLIT_NO_VALUE_NOW

    def test_c_zero_holdings_and_idle_unchanged(self):
        assert PH.build_allocation_split_card(PH.StationReadout(
            requested=True, submitted=True, bound=True))[0].state == UI_EMPTY
        assert PH.build_allocation_split_card(PH.StationReadout(
            requested=False))[0].state == UI_IDLE

    def test_c_every_genuine_input_is_byte_identical_to_before(self):
        old = _mutant(PH, *_REVERT)
        before = [_fp(old, b) for st_ in _genuine_stations(old) for b in _both(old, st_)]
        after = [_fp(PH, b) for st_ in _genuine_stations(PH) for b in _both(PH, st_)]
        assert len(before) == len(after) == 2 * len(_genuine_stations(PH))
        assert before == after


# ══════════════════════════════════════════════════════════════════
# (d) 既有呼叫端 —— 本批沒有新增任何參數；L3 與其他卡一律不變
# ══════════════════════════════════════════════════════════════════
class TestExistingCallersUnchanged:
    def test_d_signatures_unchanged_no_new_parameter(self):
        for fn in (PH.build_allocation_split_card, PH.build_core_satellite_card):
            assert list(inspect.signature(fn).parameters) == ["station"]
        assert list(inspect.signature(S.compute_allocation_split).parameters) == ["rows"]
        assert list(inspect.signature(S.build_station_digest).parameters) == ["rows", "vix"]

    def test_d_l3_return_values_unchanged(self):
        """L3 輸出釘值（本批 ⛔ 未改 L3；⑦ AI 總結與 v1 戰情室吃同一份）。"""
        assert S.compute_allocation_split([_ETF_OK, _SAT_OK, _SAT_ERR, _SAT_NO_LOTS]) == {
            "core_pct": 51.2, "sat_pct": 48.8, "core_target": T.CORE_TARGET_PCT,
            "sat_target": T.SATELLITE_TARGET_PCT,
            "core_dev": round(51.2195 - T.CORE_TARGET_PCT, 1), "total_value": 205.0,
            "partial": True, "held_n": 3, "valued_n": 2}
        dg = S.build_station_digest([_ETF_ERR, _SAT_NO_PRICE], 18.0)
        assert dg["allocation"] is None and dg["errors"] == ["00878"]

    def test_d_every_other_hold_card_is_byte_identical_with_or_without_this_batch(self):
        from tests import test_p04_hold_v2_cards as E

        def _prints(P):
            _orig = E.P
            E.P = P
            try:
                _notes, builts = E._enumerate()
            finally:
                E.P = _orig
            out = []
            for card, facts, sig in builts:
                _k = repr((card, tuple(facts), sig)) + P.v2_card_html(card, facts, sig)
                _new = (card.key in _SPLIT_KEYS and card.state == UI_FAILED
                        and card.note.where == P.STATION_ERROR_WHERE)
                out.append((card.key, card.state, _new,
                            hashlib.sha256(_k.encode()).hexdigest()))
            return out

        before = _prints(_mutant(PH, *_REVERT))
        after = _prints(PH)
        # 同一份窮舉（順序固定）→ 逐位置對齊比。
        assert len(before) == len(after) > 1000
        assert {k for k, *_ in after} >= set(_SPLIT_KEYS)
        new_idx = {i for i, a in enumerate(after) if a[2]}
        # 本批新路徑只出現在 p04 窮舉裡 Q2 那三例 × 兩張卡；修前它們不是紅卡。
        assert len(new_idx) == 6
        assert not any(b[2] for b in before)
        assert all(before[i][1] != UI_FAILED for i in new_idx)
        assert ([b for i, b in enumerate(before) if i not in new_idx]
                == [a for i, a in enumerate(after) if i not in new_idx]), "有既有卡的輸出變了"


# ══════════════════════════════════════════════════════════════════
# (e) 突變 —— 拔掉本批守衛，(a)/(b) 必須轉紅
# ══════════════════════════════════════════════════════════════════
class TestMutations:
    def test_e_dropping_the_whole_guard_turns_all_failed_back_into_a_valid_empty(self):
        m = _mutant(PH, *_REVERT)
        for card, _f, _s in _both(m, _station(m, (_ETF_ERR, _SAT_NO_PRICE))):
            assert card.state == UI_EMPTY and _VALID in card.note.why, (
                "拿掉守衛後 (a) 必須失敗 —— 否則 (a) 沒有守到東西")

    def test_e_dropping_the_partial_guard_turns_partial_live(self):
        m = _mutant(PH, ("has_value=station.split is not None and not _uncounted,",
                         "has_value=station.split is not None,"))
        rows = (_ETF_OK, _SAT_ERR)
        for card, _f, _s in _both(m, _station(m, rows, _l3_split(rows))):
            assert card.state == UI_LIVE, "不完整的比例又被畫成 live —— (b) 必須抓到"

    def test_e_dropping_the_no_price_half_turns_no_price_grey(self):
        m = _mutant(PH, ("_uncounted = _failed + _unpriced", "_uncounted = _failed"))
        card = m.build_allocation_split_card(_station(m, (_SAT_NO_PRICE,)))[0]
        assert card.state == UI_EMPTY and _VALID in card.note.why

    def test_e_dropping_the_price_check_turns_missing_lots_red(self):
        """拿掉「連現價都沒有」那一條 → 缺張數也升紅 —— (c) 的缺輸入分界必須抓到。"""
        m = _mutant(PH, ('\n        and not (isinstance(_r.get("現價"), (int, float)) '
                         'and _r["現價"] > 0))', ")"))
        card = m.build_allocation_split_card(_station(m, (_SAT_NO_LOTS,)))[0]
        assert card.state == UI_FAILED

    def test_e_core_satellite_off_the_shared_state_is_caught(self):
        m = _mutant(PH, (
            "Q2）：持有列取數失敗 → 兩張一起紅。\n    \"\"\"\n    _state = _split_state(station)",
            "Q2）：持有列取數失敗 → 兩張一起紅。\n    \"\"\"\n    _state = classify_ui_state("
            "requested=station.requested, error=station.error or None, "
            "has_value=station.split is not None)"))
        five, six = _both(m, _station(m, (_SAT_ERR,)))
        assert five[0].state == UI_FAILED and six[0].state != five[0].state

    def test_e_reusing_the_whole_row_sentence_for_no_price_is_caught(self):
        m = _mutant(PH, ("(_unpriced, NO_PRICE_WHY))",
                         '(_unpriced, MISS_TEXT[MISS_FETCH_FAILED].removeprefix("這一檔")))'))
        assert _WHOLE_ROW_TEXT in m.build_allocation_split_card(
            _station(m, (_SAT_NO_PRICE,)))[0].note.why

    def test_e_1_restoring_the_rerun_clause_is_caught_on_both_places(self):
        """裁定 1 的突變：常數不截斷 → ⑤⑥ 與停利卡**兩處**都回到「可以重跑一次」。"""
        m = _mutant(PH, ('NO_PRICE_WHY: str = MISS_TEXT[MISS_NO_INPUT].removeprefix("這盞燈")'
                         '.split("，", 1)[0]',
                         'NO_PRICE_WHY: str = MISS_TEXT[MISS_NO_INPUT].removeprefix("這盞燈")'))
        st_ = _station(m, (_SAT_NO_PRICE,))
        for card in (m.build_allocation_split_card(st_)[0], m.build_core_satellite_card(st_)[0],
                     m.build_take_profit_card(st_)[0]):
            assert "可以重跑一次" in card.note.why, "裁定 1 的測試必須抓到這個退回"

    def test_e_2_dropping_the_red_guard_on_the_partial_line_is_caught(self):
        """裁定 2 的突變：拿掉紅態判定 → 紅卡上又出現「這個比例只涵蓋一部分」。"""
        m = _mutant(PH, ('if _sp and _sp.get("partial") and _split_state(station) != UI_FAILED:',
                         'if _sp and _sp.get("partial"):'))
        rows = (_ETF_OK, _SAT_NO_PRICE)
        for built in _both(m, _station(m, rows, _l3_split(rows))):
            assert built[0].state == UI_FAILED and _PARTIAL_LABEL in dict(built[1])
