"""tests/test_station_miss_reasons.py — 戰情室「⚪ 到底是哪一種」的守衛（2026-08-25）。

## 這些測試在守什麼

`tests/test_station_specs.py` 守的是 **L0 規格表本身**（四態符號、門檻文字不寫死）。
本檔守的是 **L2/L3 實際跑出來的結果**有沒有把原因帶上 —— 這是上一輪漏掉的那一半：
規格表寫得再好，判燈函式不填 `miss_reason`，畫面上還是一片分不出來的 ⚪。

⚠️ **本檔最重要的一條**：`light_235` 的缺資料判斷必須用 **`assess_holding` 這條真實
路徑**驗，不能只直呼 `light_235`。上一輪的 bug 正是這樣漏掉的 ——
直呼 `light_235(vix=None, weekly_close=None, ...)` 時條件成立、單元測試全綠，
但 `assess_holding` 永遠傳 `float(weekly_close.iloc[-1])`（非 None）進去，
所以那段防護在 production **一次都沒觸發過**。測試測的是「函式能不能」，
不是「真的會不會」—— 差別就在有沒有走呼叫端。

## 鐵律：這批改動不得改變任何判燈結果

`Flag.level` / `Light235.light` / `deploy_pct` / `take_profit` / `Screen333.passed` /
`worst_health` / `swap_level` 一律不變，只多了「為什麼」。故本檔每一組缺值測試
**都同時斷言判燈結果**，避免哪天有人「順手」讓缺值改判。
"""
from __future__ import annotations

import math
from typing import ClassVar

import numpy as np
import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from src.compute.etf import dividend_station as ds
from src.services import dividend_station_service as svc

NAN = float("nan")


def _wk(n: int, lo: float = 80.0, hi: float = 120.0) -> pd.Series:
    """n 週的週K（W-FRI 週五定案，與 `weekly_closes` 產出同形）。"""
    idx = pd.date_range("2022-01-07", periods=n, freq="W-FRI")
    return pd.Series(np.linspace(lo, hi, n), index=idx, dtype="float64")


def _assess(weekly, **kw):
    """`assess_holding` 的真實路徑呼叫（缺項一律 None，模擬上游抓不到）。"""
    base = {"ticker": "0050", "name": "測試", "asset_class": T.ASSET_CORE,
            "weekly_close": weekly, "vix": None, "premium_pct": None, "sharpe": None,
            "total_return_1y_pct": None, "annual_yield_pct": None,
            "inception_years": None, "ann_return_3y_pct": None,
            "cum_return_3y_pct": None, "peer_ranks": None}
    base.update(kw)
    return ds.assess_holding(**base)


# ════════════════════════════════════════════════════════════════
# 一、235 逐軸可用性 —— 缺陷 1（必須走 assess_holding 真實路徑）
# ════════════════════════════════════════════════════════════════
class TestLight235AxesViaAssessHolding:

    def test_all_axes_unavailable_is_flagged_through_assess_holding(self):
        """新上市（3 週歷史）+ VIX 抓不到 → 三軸皆不可用，必須標 MISS_NO_INPUT。

        這是**真實會發生**的組合：週數不足 4 → 三條均線全 None（週線軸廢）、
        不足 20 週 → 布林 z 為 None（布林軸廢）、VIX 來源掛掉 → VIX 軸廢。
        改動前這裡的 `miss_reason` 是空字串，畫面顯示「⚪ 巡航：維持定期定額」——
        什麼都沒抓到卻叫使用者照常買。
        """
        a = _assess(_wk(3), vix=None)
        assert a.light.axes_used == ()
        assert a.light.miss_reason == SS.MISS_NO_INPUT
        # 判燈不變：仍是巡航、仍不加碼（§1 缺值不觸發條件是對的，只是要說出來）
        assert a.light.light == T.LIGHT_CRUISE
        assert a.light.deploy_pct == 0.0 and a.light.take_profit is None

    def test_all_axes_unavailable_reason_text_does_not_claim_calm(self):
        """reasons 不得再宣稱「均未觸發」—— 那是在說「我看過三個依據，都沒事」。"""
        a = _assess(_wk(3), vix=None)
        txt = "、".join(a.light.reasons)
        assert "均未觸發" not in txt, f"沒有依據卻宣稱未觸發:{txt}"
        assert "沒有資料" in txt

    def test_partial_axes_are_reported_not_silently_full(self):
        """只有 VIX 抓不到（週線 + 布林都在）→ 燈照亮，但要說得出只用了 2/3 個依據。"""
        a = _assess(_wk(60), vix=None)
        assert set(a.light.axes_used) == {SS.AXIS_WEEKLY, SS.AXIS_BOLL}
        assert a.light.miss_reason == "", "有軸可用就不是「沒資料」"
        assert SS.AXIS_VIX not in a.light.axes_used

    def test_all_axes_available_keeps_the_original_wording(self):
        """三軸齊全時的巡航文案**刻意保持原字串** —— 沒壞的東西不要順手改掉。"""
        a = _assess(_wk(60, lo=100.0, hi=101.0), vix=15.0)
        assert set(a.light.axes_used) == set(SS.LIGHT235_AXES)
        if a.light.light == T.LIGHT_CRUISE:
            assert a.light.reasons == ["VIX/週線/布林 均未觸發"]

    def test_axes_used_is_in_canonical_order(self):
        """順序固定 → 畫面文字不會因為呼叫端迴圈順序不同而漂移。"""
        a = _assess(_wk(60), vix=22.0)
        order = [SS.LIGHT235_AXES.index(x) for x in a.light.axes_used]
        assert order == sorted(order)

    @pytest.mark.parametrize("axis_kw,expect_missing", [
        ({"vix": None}, SS.AXIS_VIX),
        ({"vix": NAN}, SS.AXIS_VIX),
    ])
    def test_missing_vix_axis_never_counts_as_used(self, axis_kw, expect_missing):
        a = _assess(_wk(60), **axis_kw)
        assert expect_missing not in a.light.axes_used


# ════════════════════════════════════════════════════════════════
# 二、NaN 不是「有值」—— 缺陷 1 的第二半
# ════════════════════════════════════════════════════════════════
class TestNaNIsNotAValue:

    def test_nan_scalars_are_not_axes(self):
        """`float("nan") is not None` 為真，但 NaN 跟任何門檻比都是 False ——
        那個軸其實**靜默失效**了，不能算成「有資料、沒觸發」。"""
        lt = ds.light_235(vix=NAN, weekly_close=NAN, ma4w=NAN, ma13w=NAN,
                          ma52w=NAN, z=NAN)
        assert lt.axes_used == ()
        assert lt.miss_reason == SS.MISS_NO_INPUT
        assert lt.light == T.LIGHT_CRUISE      # 判燈不變

    def test_inf_is_not_a_value_either(self):
        lt = ds.light_235(vix=float("inf"), weekly_close=100.0, ma4w=90.0,
                          ma13w=90.0, ma52w=90.0, z=None)
        assert SS.AXIS_VIX not in lt.axes_used

    def test_nan_weekly_series_end_makes_weekly_axis_unavailable(self):
        """週K 最後一筆是 NaN（上游污染）→ 週線軸不可用，且不得被當成「沒觸發」。"""
        wk = _wk(60)
        wk.iloc[-1] = NAN
        a = _assess(wk, vix=None)
        assert a.light.axes_used == ()
        assert a.light.miss_reason == SS.MISS_NO_INPUT

    def test_weekly_axis_needs_both_close_and_a_moving_average(self):
        """只有週收沒有均線 → 比不出高低，不算可用（反之亦然）。"""
        only_close = ds.light_235(vix=None, weekly_close=100.0, ma4w=None,
                                  ma13w=None, ma52w=None, z=None)
        only_ma = ds.light_235(vix=None, weekly_close=None, ma4w=95.0,
                               ma13w=None, ma52w=None, z=None)
        assert only_close.axes_used == () and only_ma.axes_used == ()
        assert only_close.miss_reason == SS.MISS_NO_INPUT
        assert only_ma.miss_reason == SS.MISS_NO_INPUT

    def test_one_moving_average_is_enough_for_the_weekly_axis(self):
        lt = ds.light_235(vix=None, weekly_close=100.0, ma4w=None,
                          ma13w=None, ma52w=110.0, z=None)
        assert lt.axes_used == (SS.AXIS_WEEKLY,)


# ════════════════════════════════════════════════════════════════
# 三、health_b vs health_c 同病同因 —— 缺陷 2
# ════════════════════════════════════════════════════════════════
class TestHealthBAndCAgreeOnTheSameIllness:

    @pytest.mark.parametrize("weeks", [1, 5, T.MA_QUARTER_WEEKS])
    def test_same_week_count_same_miss_reason(self, weeks):
        """週數不足時 B 與 C 同時 ⚪ —— 同一個病因（週數不夠）必須標同一個原因。

        改動前 B 標「來源這輪失敗，可以重跑一次」、C 標「等時間累積」，
        對新上市 ETF 而言前者是錯誤指引：重跑不會生出歷史。
        """
        wk = _wk(weeks)
        fb, fc = ds.health_b(ds.sharpe_weekly(wk)), ds.health_c(wk)
        assert fb.level == "⚪" and fc.level == "⚪"
        assert fb.miss_reason == fc.miss_reason == SS.MISS_NOT_ENOUGH

    def test_both_recover_at_the_same_week_count(self):
        """週數一夠，兩盞燈同時判得出來（證明它們卡在同一個門檻上）。"""
        wk = _wk(T.MA_QUARTER_WEEKS + 1)
        fb, fc = ds.health_b(ds.sharpe_weekly(wk)), ds.health_c(wk)
        assert fb.level != "⚪" and fc.level != "⚪"
        assert fb.miss_reason == "" and fc.miss_reason == ""

    def test_zero_volatility_is_also_not_enough_not_a_fetch_failure(self):
        """波動為零（夏普分母 0）也是「算不出來」，不是「沒抓到」。"""
        flat = pd.Series([100.0] * 60,
                         index=pd.date_range("2022-01-07", periods=60, freq="W-FRI"))
        assert ds.sharpe_weekly(flat) is None
        assert ds.health_b(None).miss_reason == SS.MISS_NOT_ENOUGH


# ════════════════════════════════════════════════════════════════
# 四、health_a 雙因分流 —— 缺陷 2
# ════════════════════════════════════════════════════════════════
class TestHealthATwoCauses:

    def test_missing_return_is_history_not_fetch(self):
        f = ds.health_a(None, 5.0)
        assert f.level == "⚪" and f.miss_reason == SS.MISS_NOT_ENOUGH
        assert "報酬" in f.msg, "訊息要說得出缺的是哪一半"

    def test_missing_yield_is_a_fetch_problem(self):
        f = ds.health_a(12.0, None)
        assert f.level == "⚪" and f.miss_reason == SS.MISS_NO_INPUT
        assert "配息" in f.msg

    def test_the_two_causes_do_not_share_a_reason(self):
        """單一常數必然說錯一半 —— 這條就是在擋「又被合併回去」。"""
        assert ds.health_a(None, 5.0).miss_reason != ds.health_a(12.0, None).miss_reason

    def test_both_missing_takes_the_more_fundamental_one(self):
        """兩者皆缺 → 歷史不足是更根本的原因（重跑補不回歷史）。"""
        f = ds.health_a(None, None)
        assert f.miss_reason == SS.MISS_NOT_ENOUGH

    def test_judgement_unchanged_for_every_missing_combination(self):
        for tr, ay in ((None, None), (None, 5.0), (12.0, None)):
            assert ds.health_a(tr, ay).level == "⚪"


# ════════════════════════════════════════════════════════════════
# 五、3-3-3 三個 ❔ 各自帶原因 —— 缺陷 3
# ════════════════════════════════════════════════════════════════
class TestScreen333Reasons:

    def test_each_undecidable_item_has_a_reason(self):
        sc = ds.screen_333(inception_years=None, ann_return_3y_pct=None,
                           cum_return_3y_pct=None, peer_ranks=None)
        assert sc.passed is False
        assert set(sc.miss_reasons) == {SS.KEY_SCREEN_INCEPTION,
                                        SS.KEY_SCREEN_RETURN, SS.KEY_SCREEN_PEER}
        assert sc.miss_reasons[SS.KEY_SCREEN_INCEPTION] == SS.MISS_NO_INPUT
        assert sc.miss_reasons[SS.KEY_SCREEN_RETURN] == SS.MISS_NOT_ENOUGH
        assert sc.miss_reasons[SS.KEY_SCREEN_PEER] == SS.MISS_NOT_ENOUGH

    def test_decidable_items_carry_no_reason(self):
        """判得出來的子項不該出現在 miss_reasons —— 空鍵會讓消費端誤以為它也缺。"""
        sc = ds.screen_333(inception_years=5.0, ann_return_3y_pct=9.0,
                           cum_return_3y_pct=None,
                           peer_ranks={m: 0.1 for m in T.PEER_WINDOWS_MONTHS})
        assert sc.miss_reasons == {} and sc.passed is True

    def test_partial_peer_windows_still_count_as_not_enough(self):
        sc = ds.screen_333(inception_years=5.0, ann_return_3y_pct=9.0,
                           cum_return_3y_pct=None, peer_ranks={3: 0.1})
        assert sc.peer_ok is None
        assert sc.miss_reasons[SS.KEY_SCREEN_PEER] == SS.MISS_NOT_ENOUGH

    def test_reason_keys_are_registry_keys(self):
        """鍵必須查得到規格 —— 這是「原因」能被畫成一盞燈的前提。"""
        sc = ds.screen_333(inception_years=None, ann_return_3y_pct=None,
                           cum_return_3y_pct=None, peer_ranks=None)
        for k in sc.miss_reasons:
            assert k in SS.SPECS_BY_KEY, f"{k} 不在規格表裡"

    def test_stock_gets_not_applicable_not_waiting_for_data(self):
        """個股的 3-3-3 是「永遠不適用」，不是「等資料」—— 叫使用者等是誤導。"""
        a = _assess(_wk(60), asset_kind=T.KIND_STOCK)
        assert a.screen.passed is False
        assert set(a.screen.miss_reasons.values()) == {SS.MISS_NOT_APPLICABLE}


# ════════════════════════════════════════════════════════════════
# 六、個股財報：沒抓到 vs 上游契約漂移 —— 缺陷 3
# ════════════════════════════════════════════════════════════════
class TestStockGradeDrift:

    def test_missing_grade_is_no_input(self):
        sa = ds.assess_stock(ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
                             mj_grade=None, mj_score_pct=None, mj_headline="",
                             mj_fail_items=None, kd=None)
        assert sa.swap_level == "⚪" and sa.miss_reason == SS.MISS_NO_INPUT

    def test_unknown_grade_is_a_bug_signal_not_missing_data(self):
        """評等回了分級表以外的值 = 上下游契約破了。重跑不會好，要修程式。"""
        sa = ds.assess_stock(ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
                             mj_grade="ZZ", mj_score_pct=None, mj_headline="",
                             mj_fail_items=None, kd=None)
        assert sa.swap_level == "⚪"                 # 判燈不變
        assert sa.miss_reason == SS.MISS_CONTRACT_DRIFT
        assert sa.miss_reason != SS.MISS_NO_INPUT

    def test_blank_grade_counts_as_not_fetched(self):
        """空字串是「沒抓到」的另一種寫法，不是髒值。"""
        sa = ds.assess_stock(ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
                             mj_grade="  ", mj_score_pct=None, mj_headline="",
                             mj_fail_items=None, kd=None)
        assert sa.miss_reason == SS.MISS_NO_INPUT

    @pytest.mark.parametrize("grade", list(T.STOCK_HEALTH_GRADES))
    def test_known_grades_carry_no_reason(self, grade):
        sa = ds.assess_stock(ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
                             mj_grade=grade, mj_score_pct=70, mj_headline="",
                             mj_fail_items=None, kd=None)
        assert sa.swap_level != "⚪" and sa.miss_reason == ""


# ════════════════════════════════════════════════════════════════
# 七、L3 組表：worst_health 彙總掉的原因要留在列上 —— 缺陷 3
# ════════════════════════════════════════════════════════════════
class TestRowsKeepTheReason:

    def test_error_row_carries_fetch_failed(self):
        """整檔抓取失敗的 ⚪ ≠ 某盞燈缺輸入的 ⚪。`MISS_FETCH_FAILED` 就是為它定義的。"""
        def _boom(ticker, asset_kind=T.KIND_ETF):
            raise RuntimeError("無日線資料")

        rows = svc.build_station_rows(
            [{"ticker": "9999", "name": "壞檔", "asset_class": T.ASSET_CORE}],
            vix=None, metrics_fn=_boom)
        assert rows[0]["健檢"] == "⚪"                      # 判燈欄不變
        assert rows[0]["_miss_reason"] == SS.MISS_FETCH_FAILED

    def test_healthy_row_has_no_reason(self):
        def _good(ticker, asset_kind=T.KIND_ETF):
            return {"weekly_close": _wk(60), "premium_pct": 0.3, "sharpe": 1.1,
                    "total_return_1y_pct": 15, "annual_yield_pct": 6,
                    "inception_years": 8, "ann_return_3y_pct": 10,
                    "cum_return_3y_pct": None,
                    "peer_ranks": {m: 0.2 for m in T.PEER_WINDOWS_MONTHS}}

        r = svc.build_station_rows([{"ticker": "0056", "name": "高股息",
                                     "asset_class": T.ASSET_CORE}],
                                   vix=18, metrics_fn=_good)[0]
        assert r["_miss_reason"] == "" and r["_health_miss"] == {}

    def test_all_white_row_keeps_every_light_reason(self):
        """四盞燈全 ⚪ 時，列上仍查得到每一盞為什麼 ⚪（worst_health 只剩一個符號）。"""
        def _thin(ticker, asset_kind=T.KIND_ETF):
            return {"weekly_close": _wk(3)}          # 新上市：什麼都算不出來

        r = svc.build_station_rows([{"ticker": "00999", "name": "新上市",
                                     "asset_class": T.ASSET_CORE}],
                                   vix=None, metrics_fn=_thin)[0]
        assert r["健檢"] == "⚪"
        assert set(r["_health_miss"]) == {SS.KEY_HEALTH_A, SS.KEY_HEALTH_B,
                                          SS.KEY_HEALTH_C, SS.KEY_HEALTH_D}
        assert r["_miss_reason"] == SS.most_fundamental_miss(r["_health_miss"].values())
        assert r["_light_miss"] == SS.MISS_NO_INPUT and r["_light_axes_used"] == []

    def test_stock_row_carries_the_drift_signal(self):
        def _dirty(ticker, asset_kind=T.KIND_STOCK):
            return {"mj_grade": "ZZ", "mj_score_pct": None, "mj_headline": "",
                    "mj_fail_items": [], "kd_state": None}

        r = svc.build_station_rows([{"ticker": "2330", "name": "台積電",
                                     "asset_class": T.ASSET_SATELLITE,
                                     "asset_kind": T.KIND_STOCK}],
                                   vix=None, metrics_fn=_dirty)[0]
        assert r["健檢"] == "⚪" and r["_miss_reason"] == SS.MISS_CONTRACT_DRIFT

    def test_new_keys_do_not_collide_with_display_columns(self):
        """新鍵一律底線開頭（同 `_detail` 慣例）→ 不會被畫進表格欄位。"""
        def _good(ticker, asset_kind=T.KIND_ETF):
            return {"weekly_close": _wk(60), "sharpe": 1.1}

        r = svc.build_station_rows([{"ticker": "0056", "name": "x",
                                     "asset_class": T.ASSET_CORE}],
                                   vix=18, metrics_fn=_good)[0]
        for k in ("_miss_reason", "_health_miss", "_light_miss",
                  "_light_axes_used", "_screen_miss"):
            assert k in r and k.startswith("_")


# ════════════════════════════════════════════════════════════════
# 八、判燈結果不得因為新欄位而改變（golden，不依賴舊版模組）
# ════════════════════════════════════════════════════════════════
class TestJudgementIsUntouched:

    #: (vix, weekly_close, ma4, ma13, ma52, z) → (light, deploy_pct, take_profit)
    GOLDEN: ClassVar[list] = [
        ((15.0, 110.0, 105.0, 100.0, 95.0, 0.5), (T.LIGHT_CRUISE, 0.0, None)),
        ((22.0, 110.0, 105.0, 100.0, 95.0, 0.5), (T.LIGHT_1, T.DEPLOY_LIGHT1_PCT, None)),
        ((27.0, 110.0, 105.0, 100.0, 95.0, 0.5), (T.LIGHT_2, T.DEPLOY_LIGHT2_PCT, None)),
        ((35.0, 110.0, 105.0, 100.0, 95.0, 0.0), (T.LIGHT_3, T.DEPLOY_LIGHT3_PCT, None)),
        ((22.0, 80.0, 95.0, 90.0, 100.0, -3.5), (T.LIGHT_3, T.DEPLOY_LIGHT3_PCT, None)),
        ((15.0, 140.0, 120.0, 110.0, 100.0, 2.5), (T.LIGHT_TAKE_PROFIT, 0.0, "partial")),
        ((15.0, 140.0, 120.0, 110.0, 100.0, 3.5), (T.LIGHT_TAKE_PROFIT, 0.0, "force")),
        # ↓ 缺軸版本：少了 VIX / 少了布林，**燈不准變**（只有依據數變少）
        ((None, 80.0, 95.0, 90.0, 100.0, -3.5), (T.LIGHT_3, T.DEPLOY_LIGHT3_PCT, None)),
        ((27.0, None, None, None, None, None), (T.LIGHT_2, T.DEPLOY_LIGHT2_PCT, None)),
        # NaN 的 VIX / 布林軸不觸發任何條件（跟改動前一樣）→ 只剩週線軸,
        # 週收 90 同時跌破月線 95(燈一)與季線 100(燈二)→ 取最嚴重的燈二。
        ((NAN, 90.0, 95.0, 100.0, 110.0, NAN), (T.LIGHT_2, T.DEPLOY_LIGHT2_PCT, None)),
    ]

    @pytest.mark.parametrize("args,expect", GOLDEN)
    def test_light_is_unchanged(self, args, expect):
        vix, wc, m4, m13, m52, z = args
        lt = ds.light_235(vix=vix, weekly_close=wc, ma4w=m4, ma13w=m13, ma52w=m52, z=z)
        assert (lt.light, lt.deploy_pct, lt.take_profit) == expect

    def test_worst_health_still_takes_the_most_severe(self):
        red = ds.Flag("🔴", "x")
        white = ds.Flag("⚪", "y", miss_reason=SS.MISS_NOT_ENOUGH)
        assert ds._worst_level(white, red, white, white) == "🔴"

    def test_suggest_action_unaffected_by_axis_bookkeeping(self):
        """建議動作只看燈與健檢等級 —— 新欄位不得滲進去。"""
        a = _assess(_wk(3), vix=None)
        assert ds.suggest_action(a) == "⚪ 巡航：維持定期定額"


# ════════════════════════════════════════════════════════════════
# 九、原因字串不得漂移（L2 用到的每個原因都要有使用者文案）
# ════════════════════════════════════════════════════════════════
class TestReasonsAreRegistered:

    def _collect(self) -> set[str]:
        seen: set[str] = set()
        seen.add(ds.health_a(None, None).miss_reason)
        seen.add(ds.health_a(None, 5.0).miss_reason)
        seen.add(ds.health_a(12.0, None).miss_reason)
        seen.add(ds.health_b(None).miss_reason)
        seen.add(ds.health_c(_wk(2)).miss_reason)
        seen.add(ds.health_d(None).miss_reason)
        seen.add(ds.light_235(vix=None, weekly_close=None, ma4w=None, ma13w=None,
                              ma52w=None, z=None).miss_reason)
        seen |= set(ds.screen_333(inception_years=None, ann_return_3y_pct=None,
                                  cum_return_3y_pct=None,
                                  peer_ranks=None).miss_reasons.values())
        seen |= set(_assess(_wk(60), asset_kind=T.KIND_STOCK).screen.miss_reasons.values())
        seen.add(_assess(_wk(60), asset_kind=T.KIND_STOCK).health_d.miss_reason)
        seen.add(ds.assess_stock(ticker="t", name="n", asset_class=T.ASSET_CORE,
                                 mj_grade="ZZ", mj_score_pct=None, mj_headline="",
                                 mj_fail_items=None, kd=None).miss_reason)
        return {r for r in seen if r}

    def test_every_reason_used_has_user_facing_text(self):
        """程式用的原因 ⊆ 有文案的原因。少一個 → 畫面印出 `no_input` 這種代號。"""
        missing = self._collect() - set(SS.MISS_TEXT)
        assert not missing, f"這些原因沒有使用者文案:{sorted(missing)}"

    def test_every_reason_used_is_ranked(self):
        """彙總時要排得出先後 —— 沒排序的原因會被當成最不根本的。"""
        assert not (self._collect() - set(SS.MISS_PRIORITY))

    def test_flags_without_problems_carry_no_reason(self):
        """有結論的燈不得帶原因（帶了就是假的缺值紀錄）。"""
        assert ds.health_b(1.2).miss_reason == ""
        assert ds.health_d(0.5).miss_reason == ""
        assert ds.health_a(12.0, 5.0).miss_reason == ""
        assert not math.isnan(0.0)      # sanity：本檔的 NaN 判斷沒被 pytest 改寫
