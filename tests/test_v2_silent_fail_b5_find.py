"""批次 5（2026-09-26）：「🔎 找標的」選股結果卡 —— 取數失敗不得再被畫成「選股已完成、0 檔」。

客戶授權（2026-09-26 批，原文）：「本批放行『失敗被當成沒結果』的所有卡，不用每張問我」。
批次 1（PR #690）已修「本頁存活池取數拋例外」那一條；本檔守其餘三條歧義路徑：

  ② **去年同季季快照缺** → 三率三升全判不過 → 存活池 0 檔 → L3 回空表＋「季快照未就緒」、
     **不報錯** → 原本畫成灰「有效的結果」。現：L3 `get_fundamental_survivors(strict=True)`
     以排名器自己的 note 原文拋出 → 走批次 1 那條紅卡。
  ③ **唯一勾選因子自身的輸入失敗** → `drop_unscored` 剔光 → 0 列 → 原本灰。
     跨季轉強（L3 `build_trend_map` 吞例外回 `{}`）、估值（L1 `fetch_pe_name_maps` 把失敗的
     市場靜默丟掉）、缺貨／RS（L3 掃描回空排行＋note、不拋）。現：`factor_input_failed` → 紅。
  ⓟ **部分失敗**（勾的因子有一個沒拿到、其他因子仍排得出名單）→ 比照「💼 持有」頁批次 2～4
     一律紅（名單不上桌）。**這是總管判讀**，不是客戶逐字裁示。
  ① **一個因子都沒勾 / session 值形狀壞掉** → 使用者輸入、不是失敗 → **本批不改**
     （現有狀態裡沒有一則講得對它，⛔ 不新寫字句）；本檔釘住「維持原樣」，並已上報規格缺口。

每條三件事：(a) 失敗 → 紅「選股中止」、⛔ 不說「有效的結果」；(b) 真的 0 → 原封不動；
(c) 突變：拿掉本批的那一段判定 → (a) 必須轉回灰（否則 (a) 沒守到東西）。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pandas as pd
import pytest

import src.data.stock.yield_pe_fetcher as YPF
import src.services.allocation_service as AL
import src.services.fundamental_screener_service as S
import src.services.rs_leader_service as RS
import src.services.shortage_screener_service as SH
import src.services.valuation_service as V
from shared.station_specs import MISS_NO_INPUT, MISS_TEXT
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE
from src.compute.screener.fundamental_prescreen import run_fundamental_prescreen
from src.ui.views import page_find as PF

_VALID = "有效的結果"
_SNAP_NOTE = "基本面存活池為空（季快照未就緒）。"
_TWSE, _TPEX = "上市 TWSE", "上櫃 TPEX"


def _mutant(mod: types.ModuleType, old: str, new: str) -> types.ModuleType:
    """把 `mod` 的原始碼裡**恰好一處** `old` 換成 `new`，載成一個獨立的新模組（同批次 1）。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
    name = f"_mutant_b5_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src.replace(old, new), mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ══════════════════════════════════════════════════════════════════
# 假世界：每一支上游預設都「正常」，個別測試再把其中一支換成失敗。
# ══════════════════════════════════════════════════════════════════
#: 存活池三檔：兩檔上市（2330 / 2317）、一檔上櫃（6488）。
_SURV = pd.DataFrame({"stock_id": ["2330", "2317", "6488"],
                      "eps": [30.0, 10.0, 5.0], "survivor": [True, True, True]})


def _twse_ok() -> pd.DataFrame:
    return pd.DataFrame({"代碼": ["2330", "2317"], "名稱": ["台積電", "鴻海"],
                         "本益比": [20.0, 12.0]})


def _tpex_ok() -> pd.DataFrame:
    return pd.DataFrame({"代碼": ["6488"], "名稱": ["環球晶"], "本益比": [15.0]})


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame()


def _no_pe_df() -> pd.DataFrame:
    """回了表、有名稱，但本益比全是缺值（NaN）—— 一筆有效本益比都沒有。"""
    return pd.DataFrame({"代碼": ["2330", "2317"], "名稱": ["台積電", "鴻海"],
                         "本益比": [float("nan"), float("nan")]})


def _no_pe_col_df() -> pd.DataFrame:
    return pd.DataFrame({"代碼": ["2330"], "名稱": ["台積電"]})


def _boom(*_a, **_k):
    raise RuntimeError("upstream boom")


def _trends(fav_of: int = 4) -> pd.DataFrame:
    return pd.DataFrame({"stock_id": ["2330", "2317", "6488"],
                         "favorable_count": [3, 1, 2] if fav_of else [0, 0, 0],
                         "favorable_of": [fav_of] * 3})


_SHORT_ROWS = [{"代碼": "2330", "缺貨分數": 8}, {"代碼": "2317", "缺貨分數": 5},
               {"代碼": "6488", "缺貨分數": 3}]
_RS_ROWS = [{"代碼": "2330", "RS(σ)": 1.2, "贏過大盤": True},
            {"代碼": "2317", "RS(σ)": 0.4, "贏過大盤": True},
            {"代碼": "6488", "RS(σ)": -0.3, "贏過大盤": False}]
_SHORT_EMPTY_NOTE = "⚠️ 深掃 3 檔後無可評分：資料不足 3 檔（其中 3 檔 FinMind 回 0 季）"
_RS_EMPTY_NOTE = "⚠️ 大盤 ^TWII 抓取失敗（Yahoo 暫時不可用），無基準可比較 RS，稍後再試。"


@pytest.fixture()
def world(monkeypatch):
    """把本頁會碰到的每一支上游換成可控的假貨（**只換最底下那一層**，
    中間的 L3 `get_fundamental_survivors` / `build_trend_map` / `get_pe_name_maps` /
    `get_ranked_picks` 與 L1 `fetch_pe_name_maps` 都跑真的 —— 本批改的就是它們）。"""
    monkeypatch.setattr(S, "get_fundamental_prescreen", lambda **_k: (_SURV.copy(), {}))
    monkeypatch.setattr(S, "get_cross_quarter_trends", lambda **_k: _trends())
    monkeypatch.setattr(YPF, "fetch_twse_yield_pe", _twse_ok)
    monkeypatch.setattr(YPF, "fetch_tpex_yield_pe", _tpex_ok)
    monkeypatch.setattr(SH, "run_shortage_scan",
                        lambda **_k: ([dict(r) for r in _SHORT_ROWS], {"note": ""}))
    monkeypatch.setattr(RS, "run_rs_leader_scan",
                        lambda **_k: ([dict(r) for r in _RS_ROWS], {"note": ""}))
    monkeypatch.setattr(AL, "get_macro_regime",
                        lambda: {"is_loaded": True, "regime": "bull"})
    return monkeypatch


def _run(P, factors, top_n: int = 50):
    """真的走 `load_screen_result` → `build_screen_result_card`（`P` 可以是突變模組）。"""
    req = P.ScreenRequest(submitted=True, factors=tuple(factors), top_n=top_n)
    res = P.load_screen_result(req)
    card, facts = P.build_screen_result_card(res, req)
    return res, card, facts


def _assert_aborted(card) -> None:
    assert card.state == UI_FAILED, card.state
    assert card.note.now == PF.SCREEN_ABORTED_NOW
    assert card.note.now != PF.SCREEN_EMPTY_NOW
    assert _VALID not in card.note.why


def _assert_valid_zero(card) -> None:
    assert card.state == UI_EMPTY, card.state
    assert card.note.now == PF.SCREEN_EMPTY_NOW
    assert _VALID in card.note.why


# ══════════════════════════════════════════════════════════════════
# 0. 新常數全是既有字句（⛔ 不新寫）
# ══════════════════════════════════════════════════════════════════
class TestNoNewWording:
    def test_factor_miss_why_is_the_l0_sentence_cut_delete_only(self):
        """L0 原句只刪不改：刪主詞「這盞燈」＋刪第一個「，」之後的「可以重跑一次。」。"""
        assert MISS_TEXT[MISS_NO_INPUT].startswith("這盞燈" + PF.FACTOR_MISS_WHY + "，")
        assert PF.FACTOR_MISS_WHY == "需要的數字沒抓到 —— 通常是上游來源這輪失敗"

    def test_no_red_path_of_this_batch_promises_a_rerun(self, world):
        """QA 2026-09-26 實測：失敗被快取（估值 1 天、缺貨 1 天、RS 1 小時）、快照缺要等排程
        —— 上游恢復後重按，卡照樣是紅的。本批的紅卡**不得**叫人重跑。"""
        for which, factor in (("trend", "trend"), ("pe_both", "pe_low"),
                              ("shortage_empty", "shortage"), ("rs_empty", "rs_leader")):
            _break(world, which)
            _, card, _ = _run(PF, (factor,))
            assert card.state == UI_FAILED
            assert "重跑" not in card.note.why and "重跑" not in card.note.where, which
        world.setattr(S, "get_fundamental_prescreen", _prescreen_with_prev(pd.DataFrame()))
        _, card, _ = _run(PF, ("eps_high",))
        assert "重跑" not in card.note.why

    def test_snapshot_wait_where_is_the_grey_cards_existing_text(self):
        """上提的那一句，與 0 檔灰卡的 where 原文一字不差（灰卡整句也一字未變）。"""
        card, _ = _card(factors=("eps_high",), df=_Frame(0), rows=0, survivors_n=3)
        assert card.note.where == (
            f"放寬條件（少勾幾個因子）後再{PF.press(PF.ACTION_RUN_SCREEN_LABEL)}；"
            "若「L3 說明」指向季快照未就緒，那要等排程補抓，重按不會改變它")
        assert PF.SNAPSHOT_WAIT_WHERE in card.note.where

    def test_factor_labels_are_the_labels_the_facts_already_used(self):
        """上提前寫在 `load_screen_result` 裡的四個 facts 標籤，一字未改。"""
        assert PF.FACTOR_INPUT_LABELS == {
            "pe_low": "估值（本益比）", "shortage": "缺貨掃描",
            "rs_leader": "抗跌 RS 掃描", "trend": "跨季轉強"}
        assert set(PF.FACTOR_INPUT_LABELS) <= set(S.SCREEN_ANGLE_LABELS.values())


# ══════════════════════════════════════════════════════════════════
# 1. L1 / L3 新參數：預設呼叫行為不變；標記只在傳入時才有
# ══════════════════════════════════════════════════════════════════
_MARKET_CASES = [
    (_twse_ok, _tpex_ok, []),
    (_boom, _tpex_ok, [_TWSE]),
    (_twse_ok, _empty_df, [_TPEX]),
    (_no_pe_df, _tpex_ok, [_TWSE]),
    (_no_pe_col_df, _tpex_ok, [_TWSE]),
    (_boom, _boom, [_TWSE, _TPEX]),
    (_empty_df, _no_pe_df, [_TWSE, _TPEX]),
]


class TestL1FailedMarkets:
    @pytest.mark.parametrize("twse,tpex,expected", _MARKET_CASES)
    def test_reports_each_market_that_gave_no_valid_pe(self, monkeypatch, twse, tpex, expected):
        monkeypatch.setattr(YPF, "fetch_twse_yield_pe", twse)
        monkeypatch.setattr(YPF, "fetch_tpex_yield_pe", tpex)
        got: list[str] = []
        YPF.fetch_pe_name_maps(failed_markets=got)
        assert got == expected

    @pytest.mark.parametrize("twse,tpex,expected", _MARKET_CASES)
    def test_return_values_identical_with_or_without_the_marker(self, monkeypatch,
                                                                twse, tpex, expected):
        monkeypatch.setattr(YPF, "fetch_twse_yield_pe", twse)
        monkeypatch.setattr(YPF, "fetch_tpex_yield_pe", tpex)
        assert YPF.fetch_pe_name_maps() == YPF.fetch_pe_name_maps(failed_markets=[])


class TestL3Defaults:
    def test_valuation_default_calls_l1_with_no_arguments(self, monkeypatch):
        calls = []
        monkeypatch.setattr(YPF, "fetch_pe_name_maps",
                            lambda *a, **k: calls.append((a, k)) or ({}, {}))
        V.get_pe_name_maps()
        assert calls == [((), {})], "預設呼叫必須與既有一字不變（L1 收到無引數呼叫）"

    def test_valuation_forwards_the_marker_list(self, monkeypatch):
        monkeypatch.setattr(YPF, "fetch_twse_yield_pe", _boom)
        monkeypatch.setattr(YPF, "fetch_tpex_yield_pe", _tpex_ok)
        got: list[str] = []
        assert V.get_pe_name_maps(failed_markets=got) == YPF.fetch_pe_name_maps()
        assert got == [_TWSE]

    def test_survivors_default_still_returns_an_empty_pool(self, monkeypatch):
        monkeypatch.setattr(S, "get_fundamental_prescreen",
                            lambda **_k: (_SURV.assign(survivor=False), {"m": 1}))
        surv, meta = S.get_fundamental_survivors()
        assert surv.empty and meta == {"m": 1}

    def test_survivors_strict_raises_with_the_rankers_own_note(self, monkeypatch):
        monkeypatch.setattr(S, "get_fundamental_prescreen",
                            lambda **_k: (_SURV.assign(survivor=False), {}))
        _, note = S.composite_rank_candidates(pd.DataFrame(), factors=[])
        assert note == _SNAP_NOTE                         # 前提：訊息是 L3 既有那一句
        with pytest.raises(RuntimeError) as ei:
            S.get_fundamental_survivors(strict=True)
        assert str(ei.value) == _SNAP_NOTE

    def test_survivors_strict_with_a_pool_returns_the_same_frame(self, monkeypatch):
        monkeypatch.setattr(S, "get_fundamental_prescreen", lambda **_k: (_SURV.copy(), {}))
        pd.testing.assert_frame_equal(S.get_fundamental_survivors(strict=True)[0],
                                      S.get_fundamental_survivors()[0])

    def test_trend_map_default_still_swallows_but_strict_raises(self, monkeypatch):
        monkeypatch.setattr(S, "get_cross_quarter_trends", _boom)
        assert S.build_trend_map() == {}
        with pytest.raises(RuntimeError, match="upstream boom"):
            S.build_trend_map(strict=True)

    def test_trend_map_strict_empty_frame_is_a_failure(self, monkeypatch):
        """趨勢表**一列都沒有**（季快照讀進來沒有一列可用）≠ 沒有證據 → strict 拋；預設照舊 {}。"""
        monkeypatch.setattr(S, "get_cross_quarter_trends",
                            lambda **_k: pd.DataFrame(columns=["stock_id", "favorable_count",
                                                               "favorable_of"]))
        assert S.build_trend_map() == {}
        with pytest.raises(RuntimeError):
            S.build_trend_map(strict=True)

    def test_trend_map_strict_no_evidence_is_not_a_failure(self, monkeypatch):
        """全市場 favorable_of == 0（季數不足）→ strict 也回 `{}`，不拋 —— 那不是取數失敗。"""
        monkeypatch.setattr(S, "get_cross_quarter_trends", lambda **_k: _trends(fav_of=0))
        assert S.build_trend_map(strict=True) == {} == S.build_trend_map()


# ══════════════════════════════════════════════════════════════════
# 2. ② 去年同季快照缺 → 存活 0 檔 → 紅（走批次 1 那一則）
# ══════════════════════════════════════════════════════════════════
def _snapshot(eps: float = 3.0, margin_bump: float = 0.0) -> pd.DataFrame:
    """一檔四項都會過的公司（前提：有去年同季可比，且今年三率都比去年高）。"""
    return pd.DataFrame({
        "stock_id": ["2330"], "revenue": [100.0], "gross_profit": [50.0 + margin_bump],
        "op_income": [30.0 + margin_bump], "net_income": [20.0 + margin_bump],
        "eps": [eps], "total_assets": [100.0], "total_liab": [20.0],
        "current_assets": [60.0]})


def _prescreen_with_prev(prev: pd.DataFrame):
    cur = _snapshot(margin_bump=5.0)
    return lambda **_k: (run_fundamental_prescreen(cur, prev), {})


class TestPathTwoSnapshotMissing:
    def test_premise_same_company_survives_when_last_year_is_present(self, world):
        world.setattr(S, "get_fundamental_prescreen", _prescreen_with_prev(_snapshot()))
        res, card, _ = _run(PF, ("eps_high",))
        assert res.survivors_n == 1 and card.state == UI_LIVE

    def test_a_last_year_missing_is_red_not_a_valid_zero(self, world):
        world.setattr(S, "get_fundamental_prescreen", _prescreen_with_prev(pd.DataFrame()))
        res, card, facts = _run(PF, ("eps_high",))
        assert res.rows == 0 and res.survivors_error
        _assert_aborted(card)
        assert "季快照未就緒" in card.note.why
        assert PF.SRC_SURVIVORS.split("（")[0] in card.note.why
        face = dict(PF.v2_short_rows(card)[0])
        assert face[PF.V2_WHY_FACT_KEY] == "L3 基本面存活池…拋出例外"
        # 去哪補：要等排程補抓（⛔ 不是 FinMind 額度／MOPS 備援鏈那一句 —— 那與快照無關）。
        assert res.survivors_pool_empty
        assert card.note.where == PF.SNAPSHOT_WAIT_WHERE
        assert face[PF.V2_GUIDE_FACT_KEY] == PF.SNAPSHOT_WAIT_WHERE
        assert "FinMind" not in card.note.where

    def test_survivors_read_error_keeps_the_existing_where(self, world):
        """讀取例外（批次 1 那一種）→ where 照舊是 FinMind／備援鏈那一句，一字未改。"""
        world.setattr(S, "get_fundamental_prescreen", _boom)
        res, card, _ = _run(PF, ("eps_high",))
        assert res.survivors_error and not res.survivors_pool_empty
        assert card.note.where.startswith("本站不以殘缺資料湊出名單")
        face = dict(PF.v2_short_rows(card)[0])
        assert face[PF.V2_GUIDE_FACT_KEY] == "FinMind 額度每日 00:00 重置；其餘看資料體檢"

    def test_c_mutation_l3_flag_dropped_sends_it_to_the_wrong_where(self, world):
        m = _mutant(S, "        _err.empty_survivor_pool = True\n", "")
        world.setattr(m, "get_fundamental_prescreen", lambda **_k: (_SURV.assign(survivor=False), {}))
        with pytest.raises(RuntimeError) as ei:
            m.get_fundamental_survivors(strict=True)
        assert not getattr(ei.value, "empty_survivor_pool", False)

    def test_c_mutation_page_ignores_the_flag(self, world):
        m = _mutant(PF, 'bool(getattr(_e, "empty_survivor_pool", False))', "False")
        world.setattr(S, "get_fundamental_prescreen", _prescreen_with_prev(pd.DataFrame()))
        _, card, _ = _run(m, ("eps_high",))
        assert card.state == UI_FAILED and card.note.where.startswith("本站不以殘缺資料湊出名單")

    def test_c_mutation_card_ignores_the_flag(self, world):
        m = _mutant(PF, "where=(SNAPSHOT_WAIT_WHERE if result.survivors_pool_empty\n",
                    "where=(SNAPSHOT_WAIT_WHERE if False\n")
        world.setattr(S, "get_fundamental_prescreen", _prescreen_with_prev(pd.DataFrame()))
        _, card, _ = _run(m, ("eps_high",))
        assert card.note.where.startswith("本站不以殘缺資料湊出名單")

    def test_c_mutation_non_strict_survivors_turns_it_grey_again(self, world):
        m = _mutant(PF, "get_fundamental_survivors(strict=True)", "get_fundamental_survivors()")
        world.setattr(S, "get_fundamental_prescreen", _prescreen_with_prev(pd.DataFrame()))
        _, card, _ = _run(m, ("eps_high",))
        assert card.state == UI_EMPTY and _VALID in card.note.why, (
            "拿掉 strict 後 ② 必須回到灰 —— 否則上面那條沒守到東西")

    def test_c_mutation_l3_strict_check_removed_turns_it_grey_again(self, world):
        m = _mutant(S, "    if strict and (surv is None or surv.empty",
                    "    if False and (surv is None or surv.empty")
        world.setattr(m, "get_fundamental_prescreen", lambda **_k: (_SURV.assign(survivor=False), {}))
        surv, _ = m.get_fundamental_survivors(strict=True)
        assert surv.empty, "拿掉 L3 的空池判定後 strict 就不拋了 —— 上面那條靠的是它"


# ══════════════════════════════════════════════════════════════════
# 3. ③ 唯一勾選因子自身的輸入失敗 → 紅
# ══════════════════════════════════════════════════════════════════
def _break(world, which: str) -> None:
    if which == "trend":
        world.setattr(S, "get_cross_quarter_trends", _boom)
    elif which == "pe_both":
        world.setattr(YPF, "fetch_twse_yield_pe", _boom)
        world.setattr(YPF, "fetch_tpex_yield_pe", _empty_df)
    elif which == "pe_twse":
        world.setattr(YPF, "fetch_twse_yield_pe", _boom)
    elif which == "pe_tpex":
        world.setattr(YPF, "fetch_tpex_yield_pe", _empty_df)
    elif which == "shortage_empty":
        world.setattr(SH, "run_shortage_scan", lambda **_k: ([], {"note": _SHORT_EMPTY_NOTE}))
    elif which == "shortage_raise":
        world.setattr(SH, "run_shortage_scan", _boom)
    elif which == "rs_empty":
        world.setattr(RS, "run_rs_leader_scan", lambda **_k: ([], {"note": _RS_EMPTY_NOTE}))
    elif which == "rs_raise":
        world.setattr(RS, "run_rs_leader_scan", _boom)
    else:   # pragma: no cover
        raise AssertionError(which)


_ONLY_FACTOR = [
    ("trend", "trend", "跨季轉強"),
    ("pe_both", "pe_low", "估值（本益比）"),
    ("shortage_empty", "shortage", "缺貨掃描"),
    ("shortage_raise", "shortage", "缺貨掃描"),
    ("rs_empty", "rs_leader", "抗跌 RS 掃描"),
    ("rs_raise", "rs_leader", "抗跌 RS 掃描"),
]


class TestPathThreeOnlyFactorInputFails:
    @pytest.mark.parametrize("which,factor,label", _ONLY_FACTOR, ids=[c[0] for c in _ONLY_FACTOR])
    def test_premise_the_same_factor_alone_ranks_rows_when_healthy(self, world, which, factor, label):
        res, card, _ = _run(PF, (factor,))
        assert res.rows and card.state == UI_LIVE

    @pytest.mark.parametrize("which,factor,label", _ONLY_FACTOR, ids=[c[0] for c in _ONLY_FACTOR])
    def test_a_is_red_and_names_the_factor(self, world, which, factor, label):
        _break(world, which)
        res, card, facts = _run(PF, (factor,))
        assert res.rows == 0, "前提：這一條原本就是『0 列 → 灰』那一種"
        assert res.factor_input_failed == (factor,)
        _assert_aborted(card)
        assert card.note.why == f"{label}：{PF.FACTOR_MISS_WHY}"
        assert card.note.where.startswith("本站不以殘缺資料湊出名單")
        face = dict(PF.v2_short_rows(card)[0])
        assert face[PF.V2_WHY_FACT_KEY] == (
            f"{label}{PF.V2_EXCERPT_GAP}需要的數字沒抓到 —— 通常是上游來源這輪失敗")
        html = PF.v2_card_html(card, facts)
        assert PF.SCREEN_EMPTY_NOW.strip("*") not in html
        assert label in dict(facts), "出事的那一個因子，原文那一列照樣在 facts"

    def test_empty_scan_uses_l3s_own_note_verbatim(self, world):
        _break(world, "shortage_empty")
        _, _, facts = _run(PF, ("shortage",))
        assert dict(facts)["缺貨掃描"] == f"失敗，該因子不計入綜合分：{_SHORT_EMPTY_NOTE}"
        _break(world, "rs_empty")
        _, _, facts = _run(PF, ("rs_leader",))
        assert dict(facts)["抗跌 RS 掃描"] == f"失敗，該因子不計入綜合分：{_RS_EMPTY_NOTE}"

    def test_empty_scan_without_a_note_still_counts_as_failed(self, world):
        world.setattr(SH, "run_shortage_scan", lambda **_k: ([], {}))
        res, card, facts = _run(PF, ("shortage",))
        assert res.factor_input_failed == ("shortage",) and card.state == UI_FAILED
        assert dict(facts)["缺貨掃描"].endswith(PF.UNKNOWN_ERROR_TEXT)

    def test_trend_empty_frame_is_red_not_a_valid_zero(self, world):
        world.setattr(S, "get_cross_quarter_trends", lambda **_k: pd.DataFrame(
            columns=["stock_id", "favorable_count", "favorable_of"]))
        res, card, facts = _run(PF, ("trend",))
        assert res.rows == 0 and res.factor_input_failed == ("trend",)
        _assert_aborted(card)
        assert card.note.why.startswith("跨季轉強：")
        assert dict(facts)["跨季轉強"] == "失敗，該因子不計入綜合分：RuntimeError()"

    def test_pe_only_twse_missing_and_the_pool_is_all_twse(self, world):
        """只少上市半邊、存活池剛好全是上市 → 0 列。原本連一列 facts 都不會出現。"""
        world.setattr(S, "get_fundamental_prescreen",
                      lambda **_k: (_SURV[_SURV.stock_id != "6488"].copy(), {}))
        _break(world, "pe_twse")
        res, card, facts = _run(PF, ("pe_low",))
        assert res.rows == 0 and res.pe_n == 1
        _assert_aborted(card)
        assert card.note.why.startswith("估值（本益比）：")


# ══════════════════════════════════════════════════════════════════
# 4. ⓟ 部分失敗 → 紅（名單不上桌），比照批次 2～4
# ══════════════════════════════════════════════════════════════════
class TestPartialFailureIsRed:
    def test_one_of_two_factors_failed_rows_still_ranked(self, world):
        _break(world, "trend")
        res, card, _ = _run(PF, ("eps_high", "trend"))
        assert res.rows and res.rows > 0, "前提：另一個因子照樣排得出名單"
        _assert_aborted(card)
        assert card.note.why.startswith("跨季轉強：")

    def test_pe_half_missing_with_rows_is_red_not_a_silent_green(self, world):
        """只少上櫃半邊 → 修前：綠燈、而且**沒有任何一列說明**（L1 靜默丟掉那半邊）。"""
        _break(world, "pe_tpex")
        res, card, _ = _run(PF, ("pe_low", "eps_high"))
        assert res.rows and res.pe_n == 2
        assert not any(k == "估值（本益比）" and "取不到" in v for k, v in res.aux_errors)
        _assert_aborted(card)
        assert card.note.why.startswith("估值（本益比）：")

    def test_several_failed_factors_listed_in_fixed_order(self, world):
        _break(world, "trend")
        _break(world, "pe_both")
        res, card, _ = _run(PF, ("trend", "eps_high", "pe_low"))
        assert res.factor_input_failed == ("pe_low", "trend")
        assert card.note.why == f"估值（本益比）、跨季轉強：{PF.FACTOR_MISS_WHY}"
        face = dict(PF.v2_short_rows(card)[0])
        assert face[PF.V2_WHY_FACT_KEY].startswith("估值（本益比）…")

    def test_c_mutation_has_value_ignores_the_failure_turns_partial_live(self, world):
        m = _mutant(PF, "has_value=result.has_rows and not _input_failed,",
                    "has_value=result.has_rows,")
        _break(world, "trend")
        _, card, _ = _run(m, ("eps_high", "trend"))
        assert card.state == UI_LIVE, "拿掉後部分失敗必須回到綠 —— 否則上面那條沒守到東西"


# ══════════════════════════════════════════════════════════════════
# 5. (b) 真的 0 ／沒勾的因子失敗 ／非因子的週邊失敗 → 原封不動
# ══════════════════════════════════════════════════════════════════
class TestGenuineOutcomesUnchanged:
    def test_bear_filter_emptying_a_valid_ranking_stays_a_valid_zero(self, world):
        world.setattr(AL, "get_macro_regime", lambda: {"is_loaded": True, "regime": "bear"})
        world.setattr(RS, "run_rs_leader_scan", lambda **_k: (
            [dict(r, 贏過大盤=False) for r in _RS_ROWS], {"note": ""}))
        res, card, facts = _run(PF, ("rs_leader",))
        assert res.rows == 0 and res.factor_input_failed == ()
        assert "沒有任何一檔" in dict(facts)["L3 說明"], "前提：0 是濾網剔光的"
        _assert_valid_zero(card)

    def test_trend_with_no_evidence_anywhere_stays_a_valid_zero(self, world):
        world.setattr(S, "get_cross_quarter_trends", lambda **_k: _trends(fav_of=0))
        res, card, _ = _run(PF, ("trend",))
        assert res.rows == 0 and res.factor_input_failed == ()
        _assert_valid_zero(card)

    def test_all_healthy_is_live_without_a_note(self, world):
        res, card, _ = _run(PF, ("pe_low", "eps_high", "shortage", "rs_leader", "trend"))
        assert res.rows == 3 and card.state == UI_LIVE and card.note is None

    def test_pe_failure_when_pe_is_not_ticked_stays_live(self, world):
        """沒勾估值 → 估值那一輪只撐「名稱」欄；照舊只在 facts 講，不轉紅。"""
        _break(world, "pe_both")
        res, card, facts = _run(PF, ("eps_high",))
        assert res.factor_input_failed == () and card.state == UI_LIVE
        assert dict(facts)["估值（本益比）"] == PF.PE_EMPTY_WHY

    def test_regime_failure_is_not_a_factor_input(self, world):
        world.setattr(AL, "get_macro_regime", _boom)
        res, card, facts = _run(PF, ("eps_high",))
        assert card.state == UI_LIVE and "總經位階" in dict(facts)


# ══════════════════════════════════════════════════════════════════
# 6. ① 一個因子都沒勾 / session 值壞掉 → 使用者輸入，本批不改（規格缺口已上報）
# ══════════════════════════════════════════════════════════════════
class TestPathOneUserInputIsLeftAsIs:
    def test_no_factor_ticked_is_not_escalated(self, world):
        res, card, facts = _run(PF, ())
        assert res.rows == 0 and res.factor_input_failed == ()
        assert card.state == UI_EMPTY and card.note.now == PF.SCREEN_EMPTY_NOW
        assert dict(facts)["L3 說明"] == "請至少勾選一個選股因子。"

    def test_no_factor_ticked_even_with_pe_failing_is_not_escalated(self, world):
        _break(world, "pe_both")
        _, card, _ = _run(PF, ())
        assert card.state == UI_EMPTY

    def test_malformed_session_value_reads_as_no_factor(self, world):
        req = PF.applied_screen_request({PF.SS_APPLIED_SCREEN: "garbage"})
        assert req.submitted and req.factors == ()
        card, _ = PF.build_screen_result_card(PF.load_screen_result(req), req)
        assert card.state == UI_EMPTY


# ══════════════════════════════════════════════════════════════════
# 7. 卡片層：判定只認「有勾、而且登記過」的因子；優先序不亂
# ══════════════════════════════════════════════════════════════════
class _Frame:
    def __init__(self, n: int) -> None:
        self._n = n

    def __len__(self) -> int:
        return self._n


def _card(factors=("trend",), **kw):
    req = PF.ScreenRequest(submitted=True, factors=tuple(factors))
    return PF.build_screen_result_card(PF.ScreenResult(requested=True, **kw), req)


class TestCardLevel:
    def test_unticked_or_unknown_keys_are_ignored(self):
        card, _ = _card(factors=("eps_high",), df=_Frame(0), rows=0, survivors_n=3,
                        factor_input_failed=("trend", "foo"))
        _assert_valid_zero(card)

    def test_pe_ticked_and_broken_is_red_even_without_the_loader_flag(self):
        """估值直接看 `pe_n`（取不到／0 檔），不靠 loader 旗標也接得住（原 live Note 看的就是它）。"""
        for pe_n in (None, 0):
            card, _ = _card(factors=("pe_low", "eps_high"), df=_Frame(3), rows=3, pe_n=pe_n)
            assert card.state == UI_FAILED and card.note.why.startswith("估值（本益比）：")
        card, _ = _card(factors=("eps_high",), df=_Frame(3), rows=3, pe_n=None)
        assert card.state == UI_LIVE, "沒勾估值 → 估值出事只影響名稱欄，不轉紅"

    def test_contract_drift_outranks_a_factor_failure(self):
        card, _ = _card(df=object(), rows=None, factor_input_failed=("trend",))
        assert card.state == UI_FAILED and card.note.now == PF.SCREEN_DRIFT_NOW

    def test_ranking_error_outranks_a_factor_failure(self):
        card, _ = _card(error="RuntimeError('x')", factor_input_failed=("trend",))
        assert card.note.why.startswith("L3 選股編排")

    def test_survivors_failure_outranks_a_factor_failure(self):
        card, _ = _card(df=_Frame(0), rows=0, survivors_error="RuntimeError('s')",
                        factor_input_failed=("trend",))
        assert card.note.why.startswith("L3 基本面存活池")

    def test_full_text_is_in_the_fold_and_the_table_is_not_shown(self):
        card, facts = _card(df=_Frame(3), rows=3, survivors_n=3,
                            factor_input_failed=("trend",))
        html = PF.v2_card_html(card, facts)
        assert PF.v2_plain(card.note.why) in html
        assert card.state != UI_LIVE, "非 live 不畫結果表（`_render_screen_leaf` 只在 live 畫）"


# ══════════════════════════════════════════════════════════════════
# 8. 突變：每一段新判定拿掉 → 對應的 (a) 回到灰
# ══════════════════════════════════════════════════════════════════
class TestMutations:
    def test_reason_line_removed(self, world):
        m = _mutant(PF, "else MISS_FETCH_FAILED if _input_failed",
                    'else "" if _input_failed')
        _break(world, "trend")
        _, card, _ = _run(m, ("trend",))
        assert card.state == UI_EMPTY and _VALID in card.note.why

    def test_trend_strict_removed_on_the_page(self, world):
        m = _mutant(PF, "build_trend_map(strict=True)", "build_trend_map()")
        _break(world, "trend")
        _, card, _ = _run(m, ("trend",))
        assert card.state == UI_EMPTY and _VALID in card.note.why

    def test_trend_strict_reraise_removed_in_l3(self, world):
        m = _mutant(S, "        if strict:\n            raise\n", "")
        world.setattr(m, "get_cross_quarter_trends", _boom)
        assert m.build_trend_map(strict=True) == {}

    def test_pe_marker_not_passed_on_the_page(self, world):
        m = _mutant(PF, "get_pe_name_maps(failed_markets=_failed)", "get_pe_name_maps()")
        _break(world, "pe_tpex")
        _, card, _ = _run(m, ("pe_low", "eps_high"))
        assert card.state == UI_LIVE, "估值半邊失敗又回到靜默綠燈"

    def test_pe_markets_ignored_in_the_judgment(self, world):
        """只少半邊（`pe_n > 0`，`_pe_broken` 看不到）只有市場標記接得住。"""
        m = _mutant(PF, "PE_FACTOR_KEY: bool(_pe_err or _pe_failed_markets),",
                    "PE_FACTOR_KEY: bool(_pe_err),")
        _break(world, "pe_tpex")
        _, card, _ = _run(m, ("pe_low", "eps_high"))
        assert card.state == UI_LIVE

    def test_card_pe_broken_derivation_removed(self):
        m = _mutant(PF, "        _failed_keys.add(PE_FACTOR_KEY)\n", "        pass\n")
        req = m.ScreenRequest(submitted=True, factors=("pe_low", "eps_high"))
        card, _ = m.build_screen_result_card(m.ScreenResult(
            requested=True, df=_Frame(3), rows=3, pe_n=None), req)
        assert card.state == UI_LIVE and card.note is None, "拿掉後勾了估值卻沒算到又靜默上桌"

    def test_trend_empty_frame_raise_removed_in_l3(self, world):
        m = _mutant(S, "            raise RuntimeError()\n", "")
        world.setattr(m, "get_cross_quarter_trends", lambda **_k: pd.DataFrame(
            columns=["stock_id", "favorable_count", "favorable_of"]))
        assert m.build_trend_map(strict=True) == {}

    def test_valuation_stops_forwarding(self, world):
        m = _mutant(V, "return fetch_pe_name_maps(failed_markets=failed_markets)",
                    "return fetch_pe_name_maps()")
        world.setattr(YPF, "fetch_twse_yield_pe", _boom)
        got: list[str] = []
        m.get_pe_name_maps(failed_markets=got)
        assert got == []

    def test_l1_marker_never_filled(self, monkeypatch):
        m = _mutant(YPF, "        failed_markets.extend(", "        (")
        monkeypatch.setattr(m, "fetch_twse_yield_pe", _boom)
        monkeypatch.setattr(m, "fetch_tpex_yield_pe", _tpex_ok)
        got: list[str] = []
        m.fetch_pe_name_maps(failed_markets=got)
        assert got == []

    def test_l1_success_not_recorded(self, monkeypatch):
        m = _mutant(YPF, "                _pe_markets.add(_mkt)\n", "")
        monkeypatch.setattr(m, "fetch_twse_yield_pe", _twse_ok)
        monkeypatch.setattr(m, "fetch_tpex_yield_pe", _tpex_ok)
        got: list[str] = []
        m.fetch_pe_name_maps(failed_markets=got)
        assert got == [_TWSE, _TPEX], "健康的市場被報成失敗 —— 上面「全齊 → []」那條守的就是它"

    @pytest.mark.parametrize("scan,which,factor", [
        ("run_shortage_scan()", "shortage_empty", "shortage"),
        ("run_rs_leader_scan(beat_only=False, top_n=RS_SCAN_MAX)", "rs_empty", "rs_leader"),
    ])
    def test_empty_scan_check_removed(self, world, scan, which, factor):
        m = _mutant(PF, f"_rows, _meta = {scan}\n        if not _rows:",
                    f"_rows, _meta = {scan}\n        if False:")
        _break(world, which)
        _, card, _ = _run(m, (factor,))
        assert card.state == UI_EMPTY and _VALID in card.note.why

    def test_ticked_filter_removed_in_the_card(self):
        m = _mutant(PF, "if _k in _failed_keys and _k in req.factors)",
                    "if _k in _failed_keys)")
        req = m.ScreenRequest(submitted=True, factors=("eps_high",))
        card, _ = m.build_screen_result_card(m.ScreenResult(
            requested=True, df=_Frame(0), rows=0, survivors_n=3,
            factor_input_failed=("trend",)), req)
        assert card.state == UI_FAILED, "沒勾的因子也被拿來判紅 —— 「只認有勾的」那條守的就是它"
