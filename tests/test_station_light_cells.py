"""tests/test_station_light_cells.py — 逐盞燈輸出（`light_cells`）的守衛（2026-08-25）。

## 這一層在補什麼洞

`row_from_assessment` 把四盞健檢燈壓成一個 `worst_health`、把 3-3-3 三個子項壓成
一個「✅合格 / ❌未過 / ❔待資料」字串 —— **逐盞燈的判定在組表那一步整個消失**。
既有的 `_health_miss` 只收「⚪ 且有登記原因」的燈,所以**一盞 🟢 和一盞 🟡 在 row
裡產出的東西一模一樣（都是空的）**。要畫「每檔 8 格燈」或算「N/40 盞可信度」,
現況唯一的來源是 `_detail` 裡的中文 msg 字串 —— 而 L2 檔內註解已明說解析 msg
字串太脆弱（改一個字就壞,且**不會有任何錯誤**）。

## 鐵律：`light_cells` 是純轉換,不得重新判燈

`Flag.level` / `Light235.light` / `LIGHT_META` icon / `Screen333` 三個 bool /
`swap_level` —— **每一個 `level` 都必須逐字等於它的來源欄位**。本檔用
`TestLevelsAreVerbatim` 直接對來源比對,不是「看起來對」就算過。
零行為變更的另一半（row 既有鍵不動）由 `TestRowIsAdditiveOnly` 守。

⚠️ 本檔只測 L2/L3 純函式,**不啟動 Streamlit、不做網路 I/O**。
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from src.compute.etf import dividend_station as ds
from src.services import dividend_station_service as svc

NAN = float("nan")


def _wk(n: int, lo: float = 80.0, hi: float = 120.0) -> pd.Series:
    """n 週的週K（W-FRI 週五定案,與 `weekly_closes` 產出同形）。"""
    idx = pd.date_range("2022-01-07", periods=n, freq="W-FRI")
    return pd.Series(np.linspace(lo, hi, n), index=idx, dtype="float64")


def _assess(weekly=None, **kw):
    """`assess_holding` 的真實路徑呼叫（缺項一律 None,模擬上游抓不到）。"""
    base = {"ticker": "0050", "name": "測試", "asset_class": T.ASSET_CORE,
            "weekly_close": _wk(200) if weekly is None else weekly,
            "vix": None, "premium_pct": None, "sharpe": None,
            "total_return_1y_pct": None, "annual_yield_pct": None,
            "inception_years": None, "ann_return_3y_pct": None,
            "cum_return_3y_pct": None, "peer_ranks": None}
    base.update(kw)
    return ds.assess_holding(**base)


def _full_etf():
    """所有輸入齊全的 ETF（8 盞全部判得出來）。"""
    return _assess(vix=27.0, premium_pct=3.0, sharpe=1.4,
                   total_return_1y_pct=18.0, annual_yield_pct=5.0,
                   inception_years=9.0, ann_return_3y_pct=8.5,
                   cum_return_3y_pct=30.0, peer_ranks={3: 0.1, 6: 0.2, 12: 0.3})


def _stock(**kw):
    base = {"ticker": "2330", "name": "測試個股", "asset_class": T.ASSET_SATELLITE,
            "mj_grade": "A", "mj_score_pct": 88, "mj_headline": "體質優",
            "mj_fail_items": [], "kd": {"label": "高檔鈍化", "high_passivation": True,
                                        "k": 88.0, "d": 80.0},
            "trend": {"verdict": "improving"}}
    base.update(kw)
    return ds.assess_stock(**base)


def _by_key(cells) -> dict:
    return {c.key: c for c in cells}


# ════════════════════════════════════════════════════════════════
# 一、涵蓋範圍 —— 燈的清單必須來自規格表,不得自己列
# ════════════════════════════════════════════════════════════════
class TestCoverage:

    def test_etf_emits_exactly_the_eight_registered_lights(self):
        cells = ds.light_cells(_full_etf())
        assert len(cells) == 8
        assert [c.key for c in cells] == [s.key for s in SS.specs_for(T.KIND_ETF)]

    def test_stock_emits_exactly_the_four_registered_lights(self):
        cells = ds.light_cells(_stock())
        assert len(cells) == 4
        assert [c.key for c in cells] == [s.key for s in SS.specs_for(T.KIND_STOCK)]

    def test_no_key_is_invented(self):
        """每一個 key 都必須查得到規格 —— 查不到 = 消費端拿不到 label/why/source。"""
        for cells in (ds.light_cells(_full_etf()), ds.light_cells(_stock())):
            for c in cells:
                assert c.key in SS.SPECS_BY_KEY, f"{c.key} 不在規格表"

    def test_order_is_the_registry_order_not_call_order(self):
        """順序固定 = 畫面格子牆不會因為呼叫端不同就換位（同 `axes_text` 的理由）。"""
        a, b = _full_etf(), _assess(_wk(3))
        assert [c.key for c in ds.light_cells(a)] == [c.key for c in ds.light_cells(b)]

    def test_a_registered_light_that_is_not_wired_blows_up(self):
        """規格表加一盞、`light_cells` 沒接 → 當場炸,**不是**畫面永遠空一格（§1）。"""
        ghost = SS.StationSpec(key="ghost_light", label="幽靈", kind=T.KIND_ETF,
                               group="health", unit="", direction="categorical",
                               threshold_text="—", source="—", why="—")
        real = SS.specs_for
        try:
            SS.specs_for = lambda kind: list(real(kind)) + [ghost]
            with pytest.raises(KeyError, match="ghost_light"):
                ds.light_cells(_full_etf())
        finally:
            SS.specs_for = real

    def test_unknown_assessment_type_is_refused(self):
        with pytest.raises(TypeError):
            ds.light_cells({"ticker": "0050"})


# ════════════════════════════════════════════════════════════════
# 二、純轉換 —— level 必須逐字等於來源,不得新判
# ════════════════════════════════════════════════════════════════
class TestLevelsAreVerbatim:

    @pytest.mark.parametrize("key,attr", [
        (SS.KEY_HEALTH_A, "health_a"), (SS.KEY_HEALTH_B, "health_b"),
        (SS.KEY_HEALTH_C, "health_c"), (SS.KEY_HEALTH_D, "health_d"),
    ])
    def test_health_level_equals_the_flag(self, key, attr):
        for a in (_full_etf(), _assess(_wk(3)), _assess(_wk(60), sharpe=-0.5,
                                                        total_return_1y_pct=1.0,
                                                        annual_yield_pct=6.0,
                                                        premium_pct=9.0)):
            assert _by_key(ds.light_cells(a))[key].level == getattr(a, attr).level

    def test_light235_level_equals_the_icon(self):
        for vix in (None, 12.0, 22.0, 27.0, 35.0):
            a = _assess(vix=vix)
            assert _by_key(ds.light_cells(a))[SS.KEY_LIGHT235].level == a.light.icon

    def test_take_profit_icon_survives_as_is(self):
        """💰 是 `LIGHT_META` 的第五個符號 —— 不得被硬塞回 🔴/🟡/🟢/⚪ 四色。"""
        # 平盤 60 週後最後一週急拉 → 20 週布林 z 遠大於 +2σ（線性上升拉不出 +2σ）。
        wk = _wk(60, 100.0, 100.5)
        wk.iloc[-1] = 400.0
        a = _assess(wk)
        assert a.light.take_profit == "force", "測資沒觸發停利 → 本測試等於沒測"
        assert a.light.icon == T.LIGHT_META[T.LIGHT_TAKE_PROFIT]["icon"]
        assert _by_key(ds.light_cells(a))[SS.KEY_LIGHT235].level == a.light.icon

    @pytest.mark.parametrize("key,attr", [
        (SS.KEY_SCREEN_INCEPTION, "inception_ok"),
        (SS.KEY_SCREEN_RETURN, "return_ok"),
        (SS.KEY_SCREEN_PEER, "peer_ok"),
    ])
    def test_screen_level_maps_the_existing_bool_one_to_one(self, key, attr):
        """✅/❌/❔ 沿用 `Screen333.detail` 已在用的符號。

        ⚠️ **刻意不**把「未過」畫成 🔴:3-3-3 從不參與 `worst_health`,
        主表顯示的也是「❌ 未過」。改成 🔴 會讓格子牆多出一盞主表沒有的紅燈 = 新判斷。
        """
        for a in (_full_etf(),
                  _assess(inception_years=1.0, ann_return_3y_pct=-9.0,
                          cum_return_3y_pct=-9.0, peer_ranks={3: .9, 6: .9, 12: .9}),
                  _assess()):
            want = {True: "✅", False: "❌", None: "❔"}[getattr(a.screen, attr)]
            assert _by_key(ds.light_cells(a))[key].level == want

    def test_stock_swap_level_equals_swap_level(self):
        for grade in ("A+", "A", "B+", "B", "C", "F", None, "Z+"):
            sa = _stock(mj_grade=grade)
            assert _by_key(ds.light_cells(sa))[SS.KEY_STOCK_SWAP].level == sa.swap_level

    @pytest.mark.parametrize("key", [SS.KEY_STOCK_HEALTH, SS.KEY_STOCK_TREND,
                                     SS.KEY_STOCK_KD])
    def test_stock_lights_without_an_upstream_verdict_stay_blank(self, key):
        """`assess_stock` **從未**為這三盞各自判過等級（只當 `swap_level` 的輸入）。

        補一個等級出來就是新判燈 → 這裡誠實留空,消費端才知道「這格沒有判定可填色」,
        而不是拿到一個看起來像判定、其實是轉換層發明的東西（§1）。
        """
        assert _by_key(ds.light_cells(_stock()))[key].level == ds.LEVEL_UNJUDGED

    def test_transform_does_not_touch_the_assessment(self):
        """跑完 `light_cells` 後,所有判燈結果原封不動。"""
        a = _full_etf()
        before = (a.health_a.level, a.health_b.level, a.health_c.level, a.health_d.level,
                  a.light.light, a.light.deploy_pct, a.light.take_profit,
                  a.screen.passed, a.worst_health, ds.suggest_action(a))
        ds.light_cells(a)
        after = (a.health_a.level, a.health_b.level, a.health_c.level, a.health_d.level,
                 a.light.light, a.light.deploy_pct, a.light.take_profit,
                 a.screen.passed, a.worst_health, ds.suggest_action(a))
        assert before == after


# ════════════════════════════════════════════════════════════════
# 三、四態 —— 四種都要出得來,且一律走 classify_state
# ════════════════════════════════════════════════════════════════
class TestStates:

    def test_live_when_the_light_has_a_value(self):
        for c in ds.light_cells(_full_etf()):
            assert c.state == SS.STATE_LIVE, f"{c.key} 應為 live"

    def test_missing_when_the_input_is_absent(self):
        cells = _by_key(ds.light_cells(_assess(_wk(3))))
        for k in (SS.KEY_HEALTH_A, SS.KEY_HEALTH_B, SS.KEY_HEALTH_C, SS.KEY_HEALTH_D,
                  SS.KEY_SCREEN_INCEPTION, SS.KEY_SCREEN_RETURN, SS.KEY_SCREEN_PEER):
            assert cells[k].state == SS.STATE_MISSING, f"{k} 應為 missing"

    def test_degraded_comes_from_the_registry_not_from_here(self):
        """`stock_trend` 在規格表標了 `discriminative=False` → 有值時必為 degraded。

        第 2 層要據此顯示「門檻已失準」（這格只比較最近兩季,看不出趨勢）。
        """
        assert SS.SPECS_BY_KEY[SS.KEY_STOCK_TREND].discriminative is False
        cell = _by_key(ds.light_cells(_stock()))[SS.KEY_STOCK_TREND]
        assert cell.state == SS.STATE_DEGRADED
        # 理由必填 —— 標了失準卻不說為什麼,比不標更糟。
        assert SS.SPECS_BY_KEY[cell.key].degraded_reason.strip()

    def test_degraded_light_is_still_lit(self):
        """degraded ≠ 沒資料:燈照亮,只是別照門檻讀。這裡確認它沒被誤標成 missing。"""
        assert _by_key(ds.light_cells(_stock()))[SS.KEY_STOCK_TREND].state \
            != SS.STATE_MISSING

    def test_no_value_beats_not_discriminative(self):
        """`stock_trend` 沒有趨勢資料時 → missing（**不是** degraded）。

        這是 `classify_state` 的實際行為（`has_value` 先判）。門檻失不失準,
        在「根本沒有值」時是沒有意義的問題。⚠️ `classify_state` 的 docstring
        把 discriminative 列在 has_value **之前**,與程式碼相反 —— 本測試釘的是
        **程式碼**（L0 SSOT 的實際行為）。
        """
        cell = _by_key(ds.light_cells(_stock(trend=None)))[SS.KEY_STOCK_TREND]
        assert cell.state == SS.STATE_MISSING

    def test_state_matches_classify_state_for_every_cell(self):
        """四態只有一個 SSOT。任一格若自己算,這條就紅。"""
        for cells in (ds.light_cells(_full_etf()), ds.light_cells(_assess(_wk(3))),
                      ds.light_cells(_stock()), ds.light_cells(_stock(mj_grade=None,
                                                                     kd=None,
                                                                     trend=None))):
            for c in cells:
                spec = SS.SPECS_BY_KEY[c.key]
                assert c.state in SS.STATE_META, f"{c.key} 的 state 不在四態內"
                assert c.state == SS.classify_state(
                    spec, has_value=c.state != SS.STATE_MISSING, reason=c.miss_reason)

    def test_unwired_is_reachable_when_the_registry_says_so(self):
        """目前沒有 `wired=False` 的燈;真的登記一盞時必須壓過一切（連有值也是）。"""
        assert not [s for s in SS.STATION_SPECS if not s.wired], \
            "有 wired=False 的燈了 → 請補一條真實案例測試,別只靠這個合成 spec"
        ghost = SS.StationSpec(key="x", label="x", kind=T.KIND_ETF, group="health",
                               unit="", direction="categorical", threshold_text="—",
                               source="—", why="—", wired=False, unwired_reason="沒接")
        assert SS.classify_state(ghost, has_value=True) == SS.STATE_UNWIRED


# ════════════════════════════════════════════════════════════════
# 四、缺值原因 —— 必須對得上上游,不得自己挑一個
# ════════════════════════════════════════════════════════════════
class TestMissReasons:

    def test_health_reasons_match_the_flags(self):
        a = _assess(_wk(3))
        cells = _by_key(ds.light_cells(a))
        for key, flag in ((SS.KEY_HEALTH_A, a.health_a), (SS.KEY_HEALTH_B, a.health_b),
                          (SS.KEY_HEALTH_C, a.health_c), (SS.KEY_HEALTH_D, a.health_d)):
            assert cells[key].miss_reason == flag.miss_reason

    def test_screen_reasons_match_the_registry_keyed_dict(self):
        a = _assess(_wk(3))
        cells = _by_key(ds.light_cells(a))
        for key in (SS.KEY_SCREEN_INCEPTION, SS.KEY_SCREEN_RETURN, SS.KEY_SCREEN_PEER):
            assert cells[key].miss_reason == a.screen.miss_reasons.get(key, "")

    def test_new_listing_says_not_enough_not_try_again(self):
        """新上市:歷史不足 → 「等時間累積」。標成「可以重跑一次」是**錯誤指引**。"""
        cells = _by_key(ds.light_cells(_assess(_wk(5))))
        for key in (SS.KEY_HEALTH_B, SS.KEY_HEALTH_C, SS.KEY_SCREEN_RETURN):
            assert cells[key].miss_reason == SS.MISS_NOT_ENOUGH

    def test_stock_kind_marks_not_applicable_not_waiting(self):
        """個股走 `assess_holding` 時,D 折溢價 / 3-3-3 是「不適用」不是「壞掉」。"""
        a = _assess(asset_kind=T.KIND_STOCK)
        cells = _by_key(ds.light_cells(a))
        assert cells[SS.KEY_HEALTH_D].miss_reason == SS.MISS_NOT_APPLICABLE
        for key in (SS.KEY_SCREEN_INCEPTION, SS.KEY_SCREEN_RETURN, SS.KEY_SCREEN_PEER):
            assert cells[key].miss_reason == SS.MISS_NOT_APPLICABLE

    def test_contract_drift_is_not_flattened_into_missing_data(self):
        """上游給了不在分級表裡的 grade = **程式 bug 訊號**,不可畫成「資料不足」。"""
        cells = _by_key(ds.light_cells(_stock(mj_grade="Z+")))
        assert cells[SS.KEY_STOCK_HEALTH].miss_reason == SS.MISS_CONTRACT_DRIFT
        assert cells[SS.KEY_STOCK_SWAP].miss_reason == SS.MISS_CONTRACT_DRIFT

    def test_blank_grade_is_no_input(self):
        cells = _by_key(ds.light_cells(_stock(mj_grade=None)))
        assert cells[SS.KEY_STOCK_HEALTH].miss_reason == SS.MISS_NO_INPUT

    def test_every_reason_emitted_is_registered(self):
        """§1:不得發明新的原因字串 —— 未登錄的原因畫面查不到「該怎麼辦」。"""
        seen = set()
        for a in (_full_etf(), _assess(_wk(3)), _assess(_wk(5)),
                  _assess(asset_kind=T.KIND_STOCK)):
            seen |= {c.miss_reason for c in ds.light_cells(a)}
        for sa in (_stock(), _stock(mj_grade=None), _stock(mj_grade="Z+")):
            seen |= {c.miss_reason for c in ds.light_cells(sa)}
        for r in seen - {""}:
            assert r in SS.MISS_TEXT, f"{r!r} 沒有給使用者的說明"
            assert r in SS.MISS_PRIORITY, f"{r!r} 沒有排序"

    def test_a_light_that_can_be_judged_carries_no_reason(self):
        """判得出來就不該有原因 —— 硬塞空原因會讓消費端誤以為它也缺。"""
        for c in ds.light_cells(_full_etf()):
            assert c.miss_reason == ""


# ════════════════════════════════════════════════════════════════
# 五、235 的依據軸
# ════════════════════════════════════════════════════════════════
class TestAxesRideAlong:

    def test_axes_are_carried_verbatim(self):
        a = _assess(vix=22.0)
        cell = _by_key(ds.light_cells(a))[SS.KEY_LIGHT235]
        assert cell.axes_used == a.light.axes_used
        assert set(cell.axes_used) <= set(SS.LIGHT235_AXES)

    def test_only_the_235_light_has_axes(self):
        for c in ds.light_cells(_full_etf()):
            if c.key != SS.KEY_LIGHT235:
                assert c.axes_used == ()
        for c in ds.light_cells(_stock()):
            assert c.axes_used == ()

    def test_all_three_axes_dead_is_missing_not_a_calm_cruise(self):
        """三軸全空 → 燈仍是 ⚪ 巡航（判燈不變）,但 state 必須說「沒有依據」。

        這正是「什麼都沒抓到,卻告訴使用者一切正常、繼續買」那個坑。
        """
        a = _assess(_wk(2), vix=None)        # <4 週 → 無均線;<20 週 → 無 z;無 VIX
        assert a.light.axes_used == ()
        cell = _by_key(ds.light_cells(a))[SS.KEY_LIGHT235]
        assert a.light.light == T.LIGHT_CRUISE          # 判燈一個字都沒動
        assert cell.level == a.light.icon
        assert cell.state == SS.STATE_MISSING
        assert cell.miss_reason == SS.MISS_NO_INPUT

    def test_nan_axis_never_counts_as_evidence(self):
        """NaN 躲得過 `is not None` —— 不可讓它變成一個假的可用軸。"""
        a = _assess(vix=NAN)
        assert SS.AXIS_VIX not in _by_key(ds.light_cells(a))[SS.KEY_LIGHT235].axes_used

    def test_partial_evidence_is_still_live_and_countable(self):
        """依據不完整時 state 仍是 live（`classify_state` 只認 has_value）——
        「幾個依據可用」由 `axes_used` 揭露,不靠四態硬擠。
        """
        a = _assess(_wk(60), vix=None)       # 有週線 + 布林,無 VIX
        cell = _by_key(ds.light_cells(a))[SS.KEY_LIGHT235]
        assert 0 < len(cell.axes_used) < len(SS.LIGHT235_AXES)
        assert cell.state == SS.STATE_LIVE


# ════════════════════════════════════════════════════════════════
# 六、L3 row —— 只准多一個鍵
# ════════════════════════════════════════════════════════════════
class TestRowIsAdditiveOnly:

    def test_etf_row_carries_eight_cells(self):
        row = svc.row_from_assessment(_full_etf())
        assert len(row["_lights"]) == 8
        assert isinstance(row["_lights"], tuple)

    def test_stock_row_carries_four_cells(self):
        row = svc.stock_row_from_assessment(_stock())
        assert len(row["_lights"]) == 4

    @pytest.mark.parametrize("kind,n", [(T.KIND_ETF, 8), (T.KIND_STOCK, 4)])
    def test_error_row_still_draws_every_cell(self, kind, n):
        """整檔抓取失敗:格子**不可消失** —— 否則「N/40 盞」的分母會悄悄變小,
        畫面反而顯示可信度更高（§1）。
        """
        row = svc._error_row("X", "x", T.ASSET_CORE, kind, "boom")
        cells = row["_lights"]
        assert len(cells) == n
        assert {c.state for c in cells} == {SS.STATE_MISSING}
        assert {c.miss_reason for c in cells} == {SS.MISS_FETCH_FAILED}
        assert {c.level for c in cells} == {ds.LEVEL_UNJUDGED}
        # 與整列的 `_miss_reason` 同一個常數 —— 兩邊不得漂移。
        assert row["_miss_reason"] == SS.MISS_FETCH_FAILED

    def test_lights_is_the_only_new_key(self):
        """釘住鍵集合:多一個少一個都要有人看到（畫面 diff 必須為 0）。"""
        etf = set(svc.row_from_assessment(_full_etf()))
        assert etf == {"代號", "名稱", "種類", "類別", "健檢", "235 燈號", "加碼金",
                       "3-3-3", "建議動作", "_detail", "_health_miss", "_miss_reason",
                       "_light_miss", "_light_axes_used", "_screen_miss", "_lights"}
        stock = set(svc.stock_row_from_assessment(_stock()))
        assert stock == {"代號", "名稱", "種類", "類別", "財報體檢", "KD", "財報趨勢",
                         "健檢", "建議動作", "_detail", "_miss_reason", "_lights"}

    def test_the_new_key_never_reaches_the_table(self):
        """`_perf_row` 依欄位清單取值 → 底線欄不進表格。這裡實證,不假設。"""
        from src.ui.etf.etf_tab_dividend_station import (
            _ETF_COLS, _STOCK_COLS, _perf_row)
        assert "_lights" not in _ETF_COLS and "_lights" not in _STOCK_COLS
        etf = _perf_row(svc.row_from_assessment(_full_etf()), _ETF_COLS)
        stock = _perf_row(svc.stock_row_from_assessment(_stock()), _STOCK_COLS)
        assert list(etf) == _ETF_COLS and list(stock) == _STOCK_COLS
        for out in (etf, stock):
            assert not any(str(k).startswith("_") for k in out)

    def test_display_columns_still_say_what_they_said(self):
        """既有顯示欄逐位不變（`_lights` 是加法,不是改法）。"""
        a = _full_etf()
        row = svc.row_from_assessment(a)
        assert row["健檢"] == a.worst_health
        assert row["235 燈號"] == f"{a.light.icon} {a.light.label}"
        assert row["3-3-3"] == "✅ 合格"
        assert row["建議動作"] == ds.suggest_action(a)

    def test_cells_are_immutable(self):
        """frozen dataclass:消費端不能就地把 L2 的結論改掉。"""
        cell = svc.row_from_assessment(_full_etf())["_lights"][0]
        with pytest.raises(dataclasses.FrozenInstanceError):
            cell.level = "🔴"


# ════════════════════════════════════════════════════════════════
# 七、邊界
# ════════════════════════════════════════════════════════════════
class TestEdges:

    def test_single_week_series(self):
        cells = ds.light_cells(_assess(_wk(1)))
        assert len(cells) == 8

    def test_empty_series_still_raises_upstream(self):
        """空序列在 `assess_holding` 就該炸 —— `light_cells` 不該把它救回來。"""
        with pytest.raises(ValueError):
            _assess(pd.Series(dtype="float64"))

    def test_all_inputs_none_produces_a_full_grid(self):
        cells = ds.light_cells(_assess(_wk(1)))
        assert len(cells) == len(SS.specs_for(T.KIND_ETF))
        assert all(c.state in SS.STATE_META for c in cells)

    def test_stock_with_nothing_at_all(self):
        cells = _by_key(ds.light_cells(_stock(mj_grade=None, mj_score_pct=None,
                                              kd=None, trend=None)))
        assert cells[SS.KEY_STOCK_HEALTH].state == SS.STATE_MISSING
        assert cells[SS.KEY_STOCK_KD].state == SS.STATE_MISSING
        assert cells[SS.KEY_STOCK_SWAP].state == SS.STATE_MISSING

    def test_kd_without_k_and_d_is_missing(self):
        """只有 label / cross 沒有 K/D 數值 → 主表那一欄顯示「資料不足」,格子同步。"""
        cells = _by_key(ds.light_cells(_stock(kd={"cross": "death", "label": "死亡交叉"})))
        assert cells[SS.KEY_STOCK_KD].state == SS.STATE_MISSING

    def test_missing_light_cells_defaults_unknown_kind_to_etf(self):
        """與 `_error_row` 的「種類」判法一致（非 stock 一律當 ETF）,不得各判各的。"""
        assert len(ds.missing_light_cells("???", reason=SS.MISS_FETCH_FAILED)) == 8
        assert len(ds.missing_light_cells(T.KIND_STOCK,
                                          reason=SS.MISS_FETCH_FAILED)) == 4
