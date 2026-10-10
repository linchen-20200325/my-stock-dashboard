"""`foreign_net`（外資現貨淨買賣）燈接線守衛（2026-09-27）。

接線前：`macro_helpers.compute_five_bucket_summary` 對本 key 寫死 `_unwired`
（理由「FinMind inst net 單位未確認」），燈自註冊以來從未亮過。

單位證據（repo 內，§4.1）：
- 主源 TWSE BFI82U：`daily_data_fetchers._parse_bfi82u_rows` 取「買賣差額」欄（元）
  ÷ `shared.margin_schema.TWD_PER_YI`（1e8）→ **億**；
- 備援 FinMind `TaiwanStockTotalInstitutionalInvestors`：buy/sell 為元，
  `macro_fetch_orchestrator` 同樣 ÷ TWD_PER_YI → 億。
⇒ `cl_data['inst']['外資及陸資']['net']` 已是億，L2 不再換算；另掛 ±9999 億範圍守衛
  （範圍值取自 `shared/schemas.py` ForeignFlowSchema）擋元 / 千元 / 百萬元尺度混入。

本檔守：單位換算（含反例）、門檻邊界、缺值 / 失敗不當 0、其餘 15 盞逐位不變。
"""
from __future__ import annotations

import copy
import inspect

import pytest

from shared.macro_buckets import (
    BUCKET_DANGER_SPECS, SPECS_BY_KEY, classify_danger,
)
from shared.margin_schema import TWD_PER_YI
from src.compute.macro import compute_five_bucket_summary

_KEY = "foreign_net"
_FOREIGN = "外資及陸資"


def _run(**kw):
    rd: dict = {}
    out = compute_five_bucket_summary(readiness_out=rd, **kw)
    lights = {d["key"]: d for b in out.values() for d in b["details"]}
    return out, lights, rd


def _inst(net):
    return {"inst": {_FOREIGN: {"net": net}, "投信": {"net": 12.3}, "自營商": {"net": -4.5}}}


# ════════════════════════════════════════════════════════════════
# 1. 單位：元 → 億（L1 解析）＋ 尺度混入反例（L2 範圍守衛）
# ════════════════════════════════════════════════════════════════
class TestUnitConversion:

    def test_l0_constant_is_one_yi(self):
        assert TWD_PER_YI == 1e8

    def test_bfi82u_yuan_becomes_yi(self):
        """TWSE BFI82U「買賣差額」為元（帶千分位）→ 解析後為億。"""
        from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows
        fields = ["單位名稱", "買進金額", "賣出金額", "買賣差額"]
        data = [
            ["自營商(自行買賣)", "1", "1", "1,000,000,000"],
            ["自營商(避險)", "1", "1", "-500,000,000"],
            ["投信", "1", "1", "2,345,000,000"],
            ["外資及陸資(不含外資自營商)", "1", "1", "-25,000,000,000"],
        ]
        got = _parse_bfi82u_rows(fields, data)
        assert got[_FOREIGN]["net"] == pytest.approx(-250.0)   # -250 億，不是 -2.5e10
        assert got["投信"]["net"] == pytest.approx(23.45)
        assert got["自營商"]["net"] == pytest.approx(5.0)

    def test_parsed_value_lands_in_the_right_band(self):
        """端到端：-250 億（元 → 億之後）→ 紅；若漏除 1e8 會變成越界灰，不會是紅。"""
        from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows
        inst = _parse_bfi82u_rows(["單位名稱", "買賣差額"],
                                  [["外資及陸資(不含外資自營商)", "-25,000,000,000"]])
        _, lights, rd = _run(cl_data={"inst": inst})
        assert rd[_KEY]["value"] == pytest.approx(-250.0)
        assert lights[_KEY]["danger"] == "red"

    def test_finmind_rescue_uses_the_same_l0_constant(self):
        """備援路徑同樣 ÷ TWD_PER_YI（元 → 億），不得另寫一個 inline 1e8。"""
        from src.services import macro_fetch_orchestrator as O
        src = inspect.getsource(O)
        assert "(_df_i['buy'] - _df_i['sell']) / TWD_PER_YI" in src
        assert O.TWD_PER_YI is TWD_PER_YI

    # §4.1 陷阱反例：同一筆「外資賣超 250 億」若以別的尺度進來，必須被擋成灰，
    # **不得**被判紅（更不得被判綠）—— 也不得自行猜換算。
    @pytest.mark.parametrize("raw,why", [
        (-25_000_000_000.0, "元（漏除 1e8）"),
        (-25_000_000.0, "千元"),
        (-25_000.0, "百萬元"),
        (25_000_000_000.0, "元（買超方向）"),
    ])
    def test_wrong_scale_is_rejected_not_guessed(self, raw, why):
        _, lights, rd = _run(cl_data=_inst(raw))
        assert lights[_KEY]["danger"] == "gray", f"{why} 尺度混入卻被判燈"
        assert rd[_KEY]["value"] is None
        assert rd[_KEY]["reason"] == "out_of_range", why

    def test_percent_scale_is_not_rescaled(self):
        """百分比 / 小數陷阱：L2 **不做任何乘除**，值原樣進入判燈（-2.5 就是 -2.5 億）。"""
        _, lights, rd = _run(cl_data=_inst(-2.5))
        assert rd[_KEY]["value"] == pytest.approx(-2.5)
        assert lights[_KEY]["danger"] == "yellow"

    def test_range_bounds_are_inclusive(self):
        for v in (-9999.0, 9999.0):
            assert _run(cl_data=_inst(v))[2][_KEY]["value"] == pytest.approx(v)
        for v in (-9999.01, 9999.01):
            assert _run(cl_data=_inst(v))[2][_KEY]["value"] is None


# ════════════════════════════════════════════════════════════════
# 2. 門檻邊界（DangerSpec 原值 0 / -200、low_bad，⛔ 未改）
# ════════════════════════════════════════════════════════════════
class TestThresholdBoundaries:

    def test_spec_thresholds_unchanged(self):
        s = SPECS_BY_KEY[_KEY]
        assert (s.direction, s.yellow, s.red, s.unit, s.bucket) == (
            "low_bad", 0.0, -200.0, "億", "chips")
        assert s.wired is True

    @pytest.mark.parametrize("v,band", [
        (350.0, "green"), (0.01, "green"),
        (0.0, "yellow"), (-0.01, "yellow"), (-199.99, "yellow"),
        (-200.0, "red"), (-200.01, "red"), (-1500.0, "red"),
    ])
    def test_band(self, v, band):
        _, lights, rd = _run(cl_data=_inst(v))
        assert rd[_KEY]["state"] == "ok"
        assert lights[_KEY]["danger"] == band
        assert classify_danger(v, SPECS_BY_KEY[_KEY]) == band

    def test_value_str_uses_existing_formatter(self):
        _, lights, _ = _run(cl_data=_inst(-250.4))
        assert lights[_KEY]["value_str"] == "-250億"


# ════════════════════════════════════════════════════════════════
# 3. 缺值 / 抓取失敗 → 灰（無資料），⛔ 不得當成 0
# ════════════════════════════════════════════════════════════════
class TestFailureIsNotZero:

    @pytest.mark.parametrize("cl_data,reason", [
        (None, "not_loaded"),                                   # 冷啟動
        ({}, "not_loaded"),
        ({"inst": {}}, "no_value"),                             # 上游全敗（契約收斂成 {}）
        ({"inst": None}, "no_value"),                           # 舊 session 殘留 None
        ({"inst": {"投信": {"net": 5.0}}}, "no_value"),          # 缺外資 key
        ({"inst": {_FOREIGN: {"net": None}}}, "no_value"),      # key 在、值 None
        ({"inst": {_FOREIGN: None}}, "no_value"),               # 列型別違約
        ({"inst": {_FOREIGN: {"net": "--"}}}, "no_value"),      # 不可解析
        ({"inst": {_FOREIGN: {"net": float("nan")}}}, "out_of_range"),
    ])
    def test_missing_is_gray_not_yellow(self, cl_data, reason):
        _, lights, rd = _run(cl_data=cl_data)
        assert lights[_KEY]["danger"] == "gray", (
            "缺值被判成有結論 —— 0 在 low_bad(yellow=0) 下會變成「🟡 賣超邊緣」")
        assert rd[_KEY]["value"] is None
        assert rd[_KEY]["state"] == "missing"
        assert rd[_KEY]["reason"] == reason

    def test_true_zero_is_a_real_observation(self):
        """真的 0.0（外資不買不賣）與「沒資料」必須分得開。"""
        _, lights, rd = _run(cl_data=_inst(0.0))
        assert rd[_KEY]["state"] == "ok" and rd[_KEY]["value"] == 0.0
        assert lights[_KEY]["danger"] == "yellow"

    def test_today_page_state(self):
        """今天頁：有值 → live；缺值 → 非 live；取數例外 → failed（紅）。"""
        from shared.ui_state import UI_FAILED, UI_LIVE
        from src.ui.views import page_today as P
        spec = SPECS_BY_KEY[_KEY]
        _, _, rd_ok = _run(cl_data=_inst(-50.0))
        _, _, rd_no = _run(cl_data={"inst": {}})
        assert P.indicator_state(rd_ok[_KEY], spec, requested=True, error="") == UI_LIVE
        assert P.indicator_state(rd_no[_KEY], spec, requested=True, error="") != UI_LIVE
        assert P.indicator_state({}, spec, requested=True,
                                 error="RuntimeError('x')") == UI_FAILED


# ════════════════════════════════════════════════════════════════
# 4. 其餘 15 盞逐位不變
# ════════════════════════════════════════════════════════════════
def _full_fixture():
    import pandas as pd
    return dict(
        macro_info={"ndc_signal": {"score": 28}, "ism_pmi": {"value": 52.4},
                    "us_core_cpi": {"yoy": 3.1}, "tw_export": {"yoy": 8.5},
                    "vix": {"current": 17.2}, "us10y": {"current": 4.28}},
        m1b_m2_info={"gap": 1.8},
        bias_info={"bias_240": 12.4},
        warroom_summary={"health_score": 58.0},
        cl_data={"intl": {"美元指數 DXY": pd.DataFrame({"close": [104.2]})},
                 "adl": pd.DataFrame({"ad_ratio": [53.1]}), "margin": 2480.0},
        li_latest=pd.DataFrame({"外資大小": [-12000]}),
        jingqi_info={"avg": 51.3},
        news_items=[],
    )


class TestOtherLampsByteIdentical:

    @pytest.mark.parametrize("net", [-250.0, 0.0, 120.0, -2.5e10])
    def test_other_lamps_unchanged(self, net):
        base = _full_fixture()
        wired = copy.deepcopy(base)
        wired["cl_data"].update(_inst(net))
        out0, l0, rd0 = _run(**base)
        out1, l1, rd1 = _run(**wired)
        others = [s.key for s in BUCKET_DANGER_SPECS if s.key != _KEY]
        assert len(others) == 15
        for k in others:
            assert repr(l1[k]) == repr(l0[k]), k
            assert repr(rd1[k]) == repr(rd0[k]), k
        for b in ("long", "mid", "short", "news"):
            assert repr(out1[b]) == repr(out0[b]), b

    def test_other_today_tiles_unchanged(self):
        from src.ui.views import page_today as P
        base = _full_fixture()
        wired = copy.deepcopy(base)
        wired["cl_data"].update(_inst(-250.0))
        _, _, rd0 = _run(**base)
        _, _, rd1 = _run(**wired)
        t0 = P.build_indicator_tiles(P.MacroReadout(requested=True, readiness=rd0))
        t1 = P.build_indicator_tiles(P.MacroReadout(requested=True, readiness=rd1))
        flat0 = {x.card.key: x for b in t0.values() for x in b}
        flat1 = {x.card.key: x for b in t1.values() for x in b}
        assert set(flat0) == set(flat1) and len(flat0) == 16
        for k in flat0:
            if k == f"detail.{_KEY}":
                continue
            assert flat1[k] == flat0[k], k
            assert P.v2_card_html(flat1[k]) == P.v2_card_html(flat0[k]), k
        assert flat1[f"detail.{_KEY}"].card.state == P.UI_LIVE


# ════════════════════════════════════════════════════════════════
# 5. 上游「預填 0.0 / fillna(0)」不得變成燈上的「0億」（2026-09-27 續批，加性）
# ════════════════════════════════════════════════════════════════
_BFI_FIELDS = ["單位名稱", "買進金額", "賣出金額", "買賣差額"]
_BFI_NO_FOREIGN = [
    ["自營商(自行買賣)", "1", "1", "1,000,000,000"],
    ["投信", "1", "1", "2,345,000,000"],
]
_BFI_FULL = _BFI_NO_FOREIGN + [["外資及陸資(不含外資自營商)", "1", "1", "-25,000,000,000"]]


def _parse(data):
    from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows
    return _parse_bfi82u_rows(_BFI_FIELDS, data)


class TestBfi82uMissingForeignRow:

    def test_missing_foreign_row_is_gray_not_zero(self):
        inst = _parse(_BFI_NO_FOREIGN)
        # 既有消費點看到的內容**逐位不變**（仍是預填 0.0）
        assert inst == {"外資及陸資": {"net": 0.0}, "投信": {"net": 23.45},
                        "自營商": {"net": 10.0}}
        assert inst.unobserved_net == frozenset({"外資及陸資"})
        _, lights, rd = _run(cl_data={"inst": inst})
        assert lights[_KEY]["danger"] == "gray", "缺外資列被畫成「0億」＝ §1 假值"
        assert rd[_KEY]["value"] is None and rd[_KEY]["reason"] == "no_value"

    def test_unparsable_foreign_value_is_gray(self):
        inst = _parse(_BFI_NO_FOREIGN + [["外資及陸資(不含外資自營商)", "1", "1", "--"]])
        assert inst["外資及陸資"]["net"] == 0.0            # 既有行為
        assert "外資及陸資" in inst.unobserved_net
        assert _run(cl_data={"inst": inst})[1][_KEY]["danger"] == "gray"

    def test_full_rows_are_observed(self):
        inst = _parse(_BFI_FULL)
        assert inst.unobserved_net == frozenset()
        _, lights, rd = _run(cl_data={"inst": inst})
        assert rd[_KEY]["value"] == pytest.approx(-250.0) and lights[_KEY]["danger"] == "red"

    def test_true_zero_row_is_still_an_observation(self):
        inst = _parse(_BFI_NO_FOREIGN + [["外資及陸資(不含外資自營商)", "1", "1", "0"]])
        assert "外資及陸資" not in inst.unobserved_net
        assert _run(cl_data={"inst": inst})[2][_KEY]["value"] == 0.0

    def test_flag_survives_pickle(self):
        """`_pkl_put` / `st.cache_data` 都走 pickle —— 旗標不得在快取層掉。"""
        import pickle
        inst = pickle.loads(pickle.dumps(_parse(_BFI_NO_FOREIGN)))
        assert inst.unobserved_net == frozenset({"外資及陸資"})
        assert _run(cl_data={"inst": inst})[1][_KEY]["danger"] == "gray"

    def test_plain_dict_keeps_legacy_reading(self):
        """舊 pickle / 無旗標的 plain dict → 退回既有行為（讀 net），不更糟。"""
        _, _, rd = _run(cl_data={"inst": {"外資及陸資": {"net": 0.0}}})
        assert rd[_KEY]["value"] == 0.0


def _finmind_bundle(monkeypatch, rows):
    """以 stub 跑真正的 `fetch_macro_bundle`：TWSE inst 失敗 → FinMind rescue 回 `rows`。"""
    import importlib

    from src.data.macro import leading_indicators as _li_mod
    from src.services import macro_fetch_orchestrator as _orch

    monkeypatch.setattr(importlib, "reload", lambda m: m)
    monkeypatch.setattr(_li_mod, "build_leading_fast", lambda **kw: None, raising=False)

    class _Resp:
        def json(self):
            return {"status": 200, "data": rows}

    class _Sess:
        def get(self, *a, **kw):
            return _Resp()

    return _orch.fetch_macro_bundle(
        load_heavy=True, prev_cl_data={}, fm_token="", li_token="", bps_session=_Sess(),
        intl_map={"x": "X"}, tw_map={"台股加權指數": "^TWII"}, tech_map={"y": "Y"},
        fetch_single=lambda *a, **kw: None,
        fetch_institutional=lambda *a, **kw: ({}, "20260925"),
        fetch_margin_balance=lambda *a, **kw: None,
        fetch_adl=lambda *a, **kw: None,
    )


def _fm_row(name, buy, sell, date="2026-09-25"):
    return {"date": date, "name": name, "buy": buy, "sell": sell}


class TestFinMindRescueFillnaZero:

    _GOOD = [_fm_row("Foreign_Investor", 30_000_000_000, 55_000_000_000),
             _fm_row("Investment_Trust", 5_000_000_000, 3_000_000_000),
             _fm_row("Dealer_self", 1_000_000_000, 2_000_000_000)]

    def test_good_rows(self, monkeypatch):
        inst = _finmind_bundle(monkeypatch, self._GOOD)["inst"]
        assert repr(inst) == repr({"投信": {"net": 20.0}, "外資及陸資": {"net": -250.0},
                                   "自營商": {"net": -10.0}})
        assert _run(cl_data={"inst": inst})[1][_KEY]["danger"] == "red"

    @pytest.mark.parametrize("bad", [
        _fm_row("Foreign_Investor", None, 55_000_000_000),        # buy 缺 → 舊碼算成 −550 億
        _fm_row("Foreign_Investor", 30_000_000_000, "n/a"),       # sell 不可解析 → +300 億
    ])
    def test_missing_buy_or_sell_is_gray(self, monkeypatch, bad):
        inst = _finmind_bundle(monkeypatch, [bad] + self._GOOD[1:])["inst"]
        assert "外資及陸資" in inst                          # 既有消費點照舊拿到（假）值
        assert inst.unobserved_net == frozenset({"外資及陸資"})
        _, lights, rd = _run(cl_data={"inst": inst})
        assert lights[_KEY]["danger"] == "gray" and rd[_KEY]["reason"] == "no_value"

    def test_missing_columns_is_gray(self, monkeypatch):
        rows = [{"date": "2026-09-25", "name": "Foreign_Investor"},
                {"date": "2026-09-25", "name": "Investment_Trust"}]
        inst = _finmind_bundle(monkeypatch, rows)["inst"]
        # 實測：欄缺席時 `_df_i.get('buy', 0)` 回純量 0 → `.fillna` AttributeError →
        #   rescue 整段落入 except → inst 為 {}（既有行為，本就不會產生假淨額）
        assert inst == {}
        assert _run(cl_data={"inst": inst})[1][_KEY]["danger"] == "gray"


class TestOtherInstConsumersByteIdentical:
    """旗標是**加性**：同內容的 plain dict 與 InstNetDict 對既有消費點不可分辨。"""

    @staticmethod
    def _pair():
        flagged = _parse(_BFI_NO_FOREIGN)
        plain = {"外資及陸資": {"net": 0.0}, "投信": {"net": 23.45}, "自營商": {"net": 10.0}}
        return plain, flagged

    def test_container_is_indistinguishable(self):
        import json
        plain, flagged = self._pair()
        assert isinstance(flagged, dict)
        assert flagged == plain and repr(flagged) == repr(plain) and str(flagged) == str(plain)
        assert list(flagged.items()) == list(plain.items())
        assert json.dumps(flagged, ensure_ascii=False) == json.dumps(plain, ensure_ascii=False)
        assert repr(copy.deepcopy(flagged)) == repr(plain)

    def test_calc_traffic_light_identical(self):
        """📌 批 Z35（Q-z15，客戶 2026-10-10 核准 A，有意識的變更，⛔ 不是漏改）：`calc_traffic_light` 起改讀旗標
        （外資未觀測當缺值，現行行為由 tests/test_batch_z35.py 斷言）。本測試守的是「旗標對未讀旗標的消費點不可分辨」
        ⇒ 改對只把批 Z35 換回的還原體（基底 `26a43064`）實跑，斷言不改。"""
        from tests.test_batch_z35 import z35_pre_module
        calc_traffic_light = z35_pre_module('tl').calc_traffic_light
        plain, flagged = self._pair()
        mkt = {"score": 4, "max_score": 6}
        jq = {"avg": 55.0}
        a = calc_traffic_light(mkt, jq, {"inst": plain}, None)
        b = calc_traffic_light(mkt, jq, {"inst": flagged}, None)
        assert repr(a) == repr(b)

    def test_only_the_lamp_reads_the_flag(self):
        """靜態守衛：`unobserved_net` / `is_net_observed` 只准出現在生產端、燈的取值端與已登記的消費端
        （作戰室外資方向，批 Z16 C9-n6 (a)；批 Z33 第 2／3 項 7 處，見 tests/test_batch_z33_inst.py）。

        本守衛的意圖：讀旗標的檔案必須是**明確登記過**的消費點（每一處都另有「未觀測 → 既有缺值路徑」的
        行為測試），不得有未經檢視的新讀者。批 Z33 起清單擴大，意圖不變；函式名沿用（改名會斷既有引用）。
        """
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        hits = {str(p.relative_to(root)) for d in ("src", "shared")
                for p in (root / d).rglob("*.py")
                if "is_net_observed" in p.read_text(encoding="utf-8")
                or "unobserved_net" in p.read_text(encoding="utf-8")}
        assert hits == {"shared/inst_net.py", "src/compute/macro/macro_helpers.py",
                        "src/data/daily/daily_data_fetchers.py",
                        "src/services/macro_fetch_orchestrator.py",
                        # 批 Z16 C9-n6 (a)：作戰室外資方向改讀旗標，未觀測時不把假 0 判成方向
                        "src/ui/tabs/macro/section_warroom.py",
                        # 批 Z33 第 2／3 項：未觀測時改走各處既有缺值路徑（行為測試見 tests/test_batch_z33_inst.py）
                        "src/ui/tabs/macro/section_mid.py",
                        "src/ui/tabs/macro/section_news_ai.py",
                        "src/ui/tabs/macro/section_chips.py",
                        "src/ui/tabs/macro/section_long.py",
                        "src/ui/tabs/tab_edu.py",
                        "src/ui/pages/reconcile_panel.py",
                        "src/ui/tabs/stock_sections/section_op_recommendation.py",
                        # 批 Z35（Q-z16）：市場評估外資訊號（未觀測 ⇒ 0 分＋同頁既有缺值字；行為測試見 tests/test_batch_z35.py）
                        #   （calc_traffic_light 同檔 macro_helpers.py 已在清單內；Q-z15 行為測試同見該檔）
                        "src/services/market_assessment_apply.py"}, hits
