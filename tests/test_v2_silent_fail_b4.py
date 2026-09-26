"""批次 4：「💼 我的持股」衛星停利卡 `hold.take_profit` —— 「現價抓不到」與「沒達停利」必須分得開。

（客戶 2026-09-26：⛔ 只修這一張卡；其他卡的行為與輸出一律不動；⛔ 不新造文案；⛔ 不動版面。）

根因（L3 `dividend_station_service._fetch_stock_metrics`）：個股日線抓取失敗只 `print`、
`current_price` 留 `None`、**不寫 `_detail.error`**（不 raise，整列不會變成 `_error_row`）
⇒ 該列 `現價` 與 `損益%` 皆 `None` ⇒ L3 `flag_take_profit` 跳過它 ⇒ 卡片畫成
灰卡「沒有任何一檔衛星達停利門檻」＋「這是一個有效的結果」。批次 1（PR #690）只接到
`_detail.error` 那一種，現價單獨失敗這一種漏掉了。

修法只在 L5 `build_take_profit_card`（L3 一行未動 —— 列上本來就有 `現價`／`損益%` 兩欄）：
  · 有現價、缺均價 → **缺輸入**，照舊灰卡（灰卡原文本來就講「沒有均價因此判不了」）；
  · 連現價都沒有  → **取數失敗**，升紅。

每條失敗路徑三件事（同批次 1／2／3）：
  (a) 上游失敗 → 紅卡 `TP_FAILED_NOW`；⛔ 不得是灰卡「沒有任何一檔衛星達停利門檻」／「有效的結果」，
      ⛔ 不得是 live 的部分清單（旁邊還有一檔沒判過）；
  (b) 真的 0（或只是缺均價）→ 原封不動；其他卡的輸出一字不變；
  (c) 突變：拿掉本批新加的那一條判定 → (a) 必須失敗。
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
import types

import pandas as pd
import pytest

import src.services.dividend_station_service as S
from shared import dividend_station_thresholds as T
from shared.station_specs import MISS_FETCH_FAILED, MISS_NO_INPUT, MISS_TEXT
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE
from src.ui.views import page_hold as PH

_VALID = "有效的結果"
#: 本批現價抓不到那幾檔的 why（摘自 L0 `MISS_TEXT[MISS_NO_INPUT]`，只刪開頭主詞）。
_NO_PRICE_TEXT = MISS_TEXT[MISS_NO_INPUT].removeprefix("這盞燈")
#: 批次 1 那一句 —— 對「只有現價抓不到」**不成立**（沒有整批失敗、列上也沒有錯誤訊息）。
_WHOLE_ROW_TEXT = MISS_TEXT[MISS_FETCH_FAILED].removeprefix("這一檔")


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 的原始碼裡每一組 `old` **恰好一處**換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b4_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


def _station(P, rows, take_profit=()):
    return P.StationReadout(requested=True, submitted=True, bound=True,
                            holdings_n=len(rows), rows=tuple(rows),
                            take_profit=tuple(take_profit))


# 與 L3 `build_station_rows` 產出的列同形（只留本卡讀到的欄位）。
_SAT_PRICED = {"代號": "2330", "種類": "個股", "held": True, "現價": 103.0, "均價": 100.0,
               "損益%": 3.0, "_detail": {}}
_SAT_HIT = dict(_SAT_PRICED, **{"現價": 122.0, "損益%": 22.0})
_SAT_NO_PRICE = {"代號": "2454", "種類": "個股", "held": True, "現價": None, "均價": 100.0,
                 "損益%": None, "_detail": {}}
_SAT_NO_AVG = {"代號": "3008", "種類": "個股", "held": True, "現價": 150.0, "均價": None,
               "損益%": None, "_detail": {}}
_SAT_ERR = {"代號": "6505", "種類": "個股", "held": True, "_detail": {"error": "HTTPError 502"}}
_HIT = ({"代號": "2330", "損益%": 22.0},)


def _tp_no_price(P):
    return P.build_take_profit_card(_station(P, (_SAT_PRICED, _SAT_NO_PRICE)))


def _tp_mixed(P):
    return P.build_take_profit_card(_station(P, (_SAT_HIT, _SAT_NO_PRICE), _HIT))


# ══════════════════════════════════════════════════════════════════
# 根因釘住：L3 對「現價抓不到」**不**標 `_detail.error`（本批刻意不改 L3）
# ══════════════════════════════════════════════════════════════════
class _BoomLoader:
    def get_combined_data(self, *_a, **_k):
        raise ConnectionError("yfinance 429 / FinMind quota")


class _EmptyLoader:
    def get_combined_data(self, *_a, **_k):
        return None, "四源皆無資料", None


@pytest.fixture
def _offline_stock_fetch(monkeypatch):
    """`_fetch_stock_metrics` 的四個外部依賴全部離線化；日線那一支由測試各自指定。"""
    import src.config.config as C
    import src.config.stock_names as N
    import src.data.core.financial_statements_fetcher as FS

    monkeypatch.setattr(C, "get_finmind_token", lambda: "")
    monkeypatch.setattr(FS, "fetch_financial_statements",
                        lambda code, tok: {"error": "offline"})
    monkeypatch.setattr(N, "get_stock_name", lambda code: code)
    monkeypatch.setattr(S, "fetch_vix", lambda: 18.0)

    def _use(loader_cls):
        import src.data.core.data_loader as DL
        monkeypatch.setattr(DL, "StockDataLoader", loader_cls)
    return _use


_HOLD_SAT = {"ticker": "2454", "name": "聯發科", "asset_class": T.ASSET_SATELLITE,
             "asset_kind": T.KIND_STOCK, "held": True, "lots": 1, "avg_price": 100.0}


class TestRootCauseInL3:
    @pytest.mark.parametrize("loader", [_BoomLoader, _EmptyLoader], ids=["raises", "empty"])
    def test_price_failure_leaves_no_error_marker_and_is_skipped(self, _offline_stock_fetch,
                                                                 loader):
        _offline_stock_fetch(loader)
        m = S.fetch_metrics("2454", T.KIND_STOCK)
        assert m["current_price"] is None and "error" not in m
        rows, _vix = S.get_station_rows([dict(_HOLD_SAT)])
        (r,) = rows
        assert not (r.get("_detail") or {}).get("error"), "現價失敗沒有被寫成整列失敗（前提）"
        assert r["現價"] is None and r["損益%"] is None and r["均價"] == 100.0
        assert S.flag_take_profit(rows) == [], "L3 跳過它 —— 這就是灰卡說謊的來源"
        assert S.build_station_digest(rows, 18.0)["errors"] == [], (
            "L3 digest 契約不變（⑦ AI 總結吃同一份）—— 本批⛔ 不改 L3")

    @pytest.mark.parametrize("loader", [_BoomLoader, _EmptyLoader], ids=["raises", "empty"])
    def test_a_through_the_real_loader_the_card_is_red(self, _offline_stock_fetch, loader):
        """真的走 `load_station` → L3 `get_station_rows` → 真的 `_fetch_stock_metrics`。"""
        _offline_stock_fetch(loader)
        st_ = PH.load_station(PH.HoldingsReadout(
            requested=True, submitted=True, bound=True, holdings=(dict(_HOLD_SAT),)))
        assert not st_.error and st_.take_profit == ()
        card = PH.build_take_profit_card(st_)[0]
        assert card.state == UI_FAILED and card.note.now == PH.TP_FAILED_NOW
        assert _VALID not in card.note.why
        assert card.note.why == f"2454：{_NO_PRICE_TEXT}"


# ══════════════════════════════════════════════════════════════════
# (a) 上游失敗 → 紅
# ══════════════════════════════════════════════════════════════════
class TestNoPriceIsRed:
    def test_a_a_price_missing_satellite_is_not_a_valid_empty(self):
        built = _tp_no_price(PH)
        card = built[0]
        assert card.state == UI_FAILED and card.state != UI_EMPTY
        assert card.note.now == PH.TP_FAILED_NOW
        assert card.note.now != PH.TP_EMPTY_NOW
        assert _VALID not in card.note.why
        assert card.note.why == f"2454：{_NO_PRICE_TEXT}"
        assert card.note.where == PH.STATION_ERROR_WHERE
        html = PH.v2_card_html(*built)
        assert PH.TP_EMPTY_NOW.strip("*") not in html

    def test_a_the_whole_row_sentence_is_not_used_for_a_price_only_failure(self):
        """批次 1 那一句說「整批抓取失敗、看該列的錯誤訊息」—— 對這裡兩件事都不成立。"""
        why = _tp_no_price(PH)[0].note.why
        assert _WHOLE_ROW_TEXT not in why and "整批" not in why and "錯誤訊息" not in why

    def test_a_face_names_the_no_input_excerpt(self):
        face = dict(PH.v2_short_rows(_tp_no_price(PH)[0])[0])
        assert face[PH.V2_WHY_FACT_KEY] == "需要的數字沒抓到 —— 通常是上游來源這輪失敗"
        assert face[PH.V2_GUIDE_FACT_KEY] == "先確認網路與 Google 授權是否仍有效"

    def test_a_several_codes_are_listed_and_not_called_one(self):
        other = dict(_SAT_NO_PRICE, 代號="2603")
        why = PH.build_take_profit_card(
            _station(PH, (_SAT_PRICED, _SAT_NO_PRICE, other)))[0].note.why
        assert why == f"2454、2603：{_NO_PRICE_TEXT}"
        assert "這盞燈" not in why

    def test_a_price_missing_plus_avg_missing_on_the_same_row_is_still_red(self):
        """現價抓不到時，均價有沒有填都判不了 —— 取數失敗優先（同 L0 `MISS_PRIORITY` 的精神）。"""
        row = dict(_SAT_NO_PRICE, 均價=None)
        card = PH.build_take_profit_card(_station(PH, (row,)))[0]
        assert card.state == UI_FAILED and card.note.why == f"2454：{_NO_PRICE_TEXT}"

    def test_a_mixed_hit_and_price_missing_is_red_not_a_partial_live_list(self):
        built = _tp_mixed(PH)
        card, facts = built[0], dict(built[1])
        assert card.state == UI_FAILED and card.state != UI_LIVE
        assert card.note.now == PH.TP_FAILED_NOW
        assert card.value == "", "⛔ 不得給「1 檔達停利門檻」這個不完整的結論"
        assert built[2] == "", "非 live ⛔ 不出「可停利」訊號"
        assert card.note.why == f"2454：{_NO_PRICE_TEXT}", "只點名沒判過的那一檔"
        # 已算出的達標檔**不藏**：照樣列在 facts（同 ④ 換股批次 2 的做法）。
        assert facts["達門檻的衛星"] == "2330（22.0%）"
        assert "2330（22.0%）" in PH.v2_card_html(*built)

    def test_a_error_row_and_price_missing_together_name_both(self):
        built = PH.build_take_profit_card(_station(PH, (_SAT_ERR, _SAT_NO_PRICE)))
        card = built[0]
        assert card.state == UI_FAILED
        assert card.note.why == f"6505：{_WHOLE_ROW_TEXT}2454：{_NO_PRICE_TEXT}"
        face = dict(PH.v2_short_rows(card)[0])
        assert face[PH.V2_WHY_FACT_KEY] == (
            "整批抓取失敗 —— 看該列的錯誤訊息" + PH.V2_EXCERPT_GAP
            + "需要的數字沒抓到 —— 通常是上游來源這輪失敗")

    def test_a_station_exception_still_wins_and_keeps_its_note(self):
        """戰情表本身拋例外 → 仍是既有那一則（例外原文看得見），不被本批的 why 取代。"""
        card = PH.build_take_profit_card(PH.StationReadout(
            requested=True, submitted=True, bound=True, holdings_n=2,
            rows=(_SAT_NO_PRICE,), error="RuntimeError('Google 502')"))[0]
        assert card.state == UI_FAILED and "Google 502" in card.note.why
        assert _NO_PRICE_TEXT not in card.note.why


# ══════════════════════════════════════════════════════════════════
# (b) 真的 0 ／ 只是缺均價 ／ 本卡射程外 → 原封不動
# ══════════════════════════════════════════════════════════════════
def _assert_unchanged_valid_empty(card):
    assert card.state == UI_EMPTY
    assert card.note.now == PH.TP_EMPTY_NOW
    assert card.note.why.startswith("**這是一個有效的結果**（已經逐檔判過，不是還沒判）")
    assert "沒有均價因此**判不了**" in card.note.why
    assert card.note.where.startswith("若你預期應該要有：到 📁 組合管理確認")


class TestGenuineEmptyUnchanged:
    def test_b_all_priced_none_over_threshold(self):
        _assert_unchanged_valid_empty(
            PH.build_take_profit_card(_station(PH, (_SAT_PRICED,)))[0])

    def test_b_avg_cost_missing_is_missing_input_and_stays_grey(self):
        """有現價、缺均價 → ⛔ 不是取數失敗：灰卡原文本來就講「沒有均價因此判不了」並指去補均價。"""
        _assert_unchanged_valid_empty(
            PH.build_take_profit_card(_station(PH, (_SAT_PRICED, _SAT_NO_AVG)))[0])

    def test_b_a_hit_with_all_prices_present_stays_live(self):
        built = PH.build_take_profit_card(_station(PH, (_SAT_HIT, _SAT_NO_AVG), _HIT))
        assert built[0].state == UI_LIVE and built[0].value == "1 檔達停利門檻"
        assert built[2] == "可停利"

    @pytest.mark.parametrize("row", [
        dict(_SAT_NO_PRICE, 種類="ETF", 代號="0056"),
        dict(_SAT_NO_PRICE, held=False),
    ], ids=["held_etf_no_price", "watchlist_stock_no_price"])
    def test_b_no_price_outside_the_take_profit_scope_keeps_the_valid_empty(self, row):
        """L3 本來就不對 ETF／觀察清單判停利 → 它們抓不到現價不影響「0 檔達標」。"""
        _assert_unchanged_valid_empty(
            PH.build_take_profit_card(_station(PH, (_SAT_PRICED, row)))[0])


# ══════════════════════════════════════════════════════════════════
# (b) 其他卡：輸出一字不變
# ══════════════════════════════════════════════════════════════════
#: 把本批的判定整段中和掉（＝本批之前的行為）。其他卡在兩個版本下必須一個 byte 都不差。
_REVERT_B4 = (
    ("_unjudged = _fetch_failed + _no_price", "_unjudged = _fetch_failed"),
    ("has_value=bool(station.take_profit) and not _unjudged,",
     "has_value=bool(station.take_profit),"),
    ("if station.take_profit and not station.error:\n        _facts.insert(0, (\"達門檻的衛星\",",
     "if _state == UI_LIVE:\n        _facts.insert(0, (\"達門檻的衛星\","),
)


def _prod_station(P):
    """真的走 L3 `build_station_rows` ＋ `build_station_digest`（持股裡混了現價抓不到的衛星）。"""
    idx = pd.date_range("2020-01-03", periods=300, freq="W-FRI")

    def _metrics(tk, ak):
        if ak == T.KIND_ETF:
            return {"weekly_close": pd.Series([30 + (i % 7) * 0.3 for i in range(300)],
                                              index=idx), "current_price": 35.0}
        return {"mj_grade": "A", "mj_score_pct": 80, "mj_headline": "ok", "mj_fail_items": [],
                "kd_state": None if tk == "2454" else {"k": 50, "d": 40, "label": "中性"},
                "name": tk, "trend_verdict": None,
                "current_price": {"2454": None, "3008": 150.0}.get(tk, 105.0)}

    hold = [{"ticker": "0056", "name": "高股息", "asset_class": T.ASSET_CORE,
             "asset_kind": T.KIND_ETF, "held": True, "lots": 3, "avg_price": 30.0}]
    for tk in ("2330", "2454", "3008"):
        hold.append({"ticker": tk, "name": tk, "asset_class": T.ASSET_SATELLITE,
                     "asset_kind": T.KIND_STOCK, "held": True, "lots": 1, "avg_price": 100.0})
    rows = S.build_station_rows(hold, vix=18.0, metrics_fn=_metrics)
    dg = S.build_station_digest(rows, 18.0)
    return P.StationReadout(
        requested=True, submitted=True, bound=True, holdings_n=len(hold), rows=tuple(rows),
        digest=P._digest_map(dg), totals=P._digest_map(S.compute_portfolio_totals(rows)),
        split=P._digest_map(dg.get("allocation")),
        take_profit=tuple(dict(x) for x in (dg.get("take_profit") or ())),
        add_n=len(dg.get("adds") or ()), cut_n=len(dg.get("reds") or ()),
        err_n=len(dg.get("errors") or ()), judged=1, total_lights=2)


def _other_card_fingerprints(P) -> list[tuple[str, str]]:
    from tests import test_p04_hold_v2_cards as E

    _orig = E.P
    E.P = P
    try:
        _notes, builts = E._enumerate()
    finally:
        E.P = _orig
    st_ = _prod_station(P)
    builts = list(builts) + list(P.build_conclusion_cards(st_)) + [
        P.build_lightwall_card(st_),
        P.build_switch_card(P.SwitchReadout(requested=True, submitted=True, stance="neutral"),
                            st_),
        P.build_allocation_split_card(st_), P.build_core_satellite_card(st_),
        P.build_ai_summary_card(P.AiSummaryReadout(requested=True, text="x"), st_),
        P.build_take_profit_card(st_)]
    seen: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    for card, facts, sig in builts:
        if card.key == "hold.take_profit":
            continue
        _k = repr((card, tuple(facts), sig))
        if _k not in seen:
            seen[_k] = P.v2_card_html(card, facts, sig)
        out.append((card.key, hashlib.sha256((_k + seen[_k]).encode()).hexdigest()))
    return out


class TestOtherCardsByteIdentical:
    def test_b_every_other_hold_card_is_byte_identical_with_or_without_this_batch(self):
        before = _other_card_fingerprints(_mutant(PH, *_REVERT_B4))
        after = _other_card_fingerprints(PH)
        assert len(before) == len(after) > 1000
        assert {k for k, _ in after} >= {
            "hold.lightwall", "hold.switch", "hold.alloc_split", "hold.deep.core_satellite",
            "hold.ai_summary", "hold.conclusion.action", "hold.conclusion.todo"}
        assert before == after

    def test_b_the_prod_station_take_profit_differs_only_in_this_card(self):
        """前提自證：上面那一組裡，本卡在兩個版本下**確實**不同（否則比對沒有意義）。"""
        old = _mutant(PH, *_REVERT_B4).build_take_profit_card(_prod_station(PH))[0]
        new = PH.build_take_profit_card(_prod_station(PH))[0]
        assert old.state == UI_LIVE and new.state == UI_FAILED


# ══════════════════════════════════════════════════════════════════
# (c) 突變 —— 拿掉本批的判定，(a) 必須失敗
# ══════════════════════════════════════════════════════════════════
class TestMutations:
    def test_c_dropping_the_no_price_half_turns_a_red(self):
        m = _mutant(PH, ("_unjudged = _fetch_failed + _no_price", "_unjudged = _fetch_failed"))
        card = _tp_no_price(m)[0]
        assert card.state == UI_EMPTY and _VALID in card.note.why, (
            "拿掉新判定後 (a) 必須失敗 —— 否則 (a) 沒有守到東西")

    def test_c_dropping_the_partial_guard_turns_mixed_live(self):
        m = _mutant(PH, ("has_value=bool(station.take_profit) and not _unjudged,",
                         "has_value=bool(station.take_profit),"))
        assert _tp_mixed(m)[0].state == UI_LIVE, "部分清單又被畫成 live —— (a) 必須抓到"

    def test_c_dropping_the_price_check_turns_avg_missing_red(self):
        """拿掉「連現價都沒有」那一條 → 缺均價也升紅 —— (b) 的缺輸入分界必須抓到。"""
        m = _mutant(PH, ('        and not (isinstance(_r.get("現價"), (int, float)) '
                         'and _r.get("現價") > 0))', "        )"))
        card = m.build_take_profit_card(_station(m, (_SAT_PRICED, _SAT_NO_AVG)))[0]
        assert card.state == UI_FAILED

    def test_c_reusing_the_whole_row_sentence_is_caught(self):
        m = _mutant(PH, ("{MISS_TEXT[MISS_NO_INPUT].removeprefix('這盞燈')}",
                         "{MISS_TEXT[MISS_FETCH_FAILED].removeprefix('這一檔')}"))
        assert _WHOLE_ROW_TEXT in _tp_no_price(m)[0].note.why
