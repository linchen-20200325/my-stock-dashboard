"""System Action Aggregator 測試共用：golden 夾具＋可對「任意模組版本」執行的檢查函式（M-A2）。

設計（突變驗證用）：每個 `check_*` 只透過傳入的 `agg`（aggregator 模組）與 `C`（contract 模組）呼叫，
故 `tests/test_system_action_aggregator_mutation.py` 能把「拔掉守衛的突變模組」餵進同一個檢查，
證明守衛被拔掉時檢查會轉紅（AssertionError 或建構期 ValueError／TypeError）。

夾具一律以**真的** L2 `dividend_station`（assess_holding／assess_stock／action_branch／light_cells）
＋L3 `dividend_station_service`（row_from_assessment／stock_row_from_assessment／_mark_insufficient／
_error_row／build_station_digest）產生，⛔ 手寫燈格。唯一合成的是 `KEY_FX_UNCONFIRMED`／
`KEY_INVALID_INPUTS` 兩個旗標鍵（production 由 `build_station_rows` 依取數結果設；此處無網路）。
"""
from __future__ import annotations

import dataclasses
import re

import numpy as np
import pandas as pd

from shared import asset_currency_gate as FXG
from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from shared.allocation_decision import build_allocation_decision
from src.compute.etf import dividend_station as ds
from src.services import dividend_station_service as svc

_IDX = pd.date_range("2023-01-01", periods=120, freq="W-SUN")
_I = np.arange(120)
_SERIES = pd.Series(20 + 0.01 * _I + 0.05 * np.sin(_I), index=_IDX)
_PEERS = {m: 0.1 for m in T.PEER_WINDOWS_MONTHS}
STAMP_KW = {"as_of": "2026-11-20", "source": "fixture:dividend_station"}


def _base_assessment(ticker: str, *, peers: bool = True) -> ds.HoldingAssessment:
    return ds.assess_holding(
        ticker=ticker, name=f"名-{ticker}", asset_class=T.ASSET_CORE, weekly_close=_SERIES,
        vix=T.VIX_LIGHT1 - 5.0, premium_pct=0.1, sharpe=0.8, total_return_1y_pct=10.0,
        annual_yield_pct=5.0, inception_years=5, ann_return_3y_pct=5.0, cum_return_3y_pct=15.0,
        peer_ranks=_PEERS if peers else None)


def _light(base: ds.Light235, light_key: str, **over) -> ds.Light235:
    _m = T.LIGHT_META[light_key]
    return dataclasses.replace(base, light=light_key, icon=_m["icon"], label=_m["label"],
                               deploy_pct=_m["deploy_pct"], reasons=["fixture"], **over)


#: 真實格式夾具的**資料輸入**（不是比例字樣；百分比字樣一律由來源函式 `ds.health_a`／`ds.health_d`／
#: `ds.suggest_action` 依來源常數組出，⛔ 測試手打）。賺息賠本＝年報酬 < 配息率；高溢價＝溢價 > 門檻。
REAL_CUT_YIELD_PCT: float = 5.0
REAL_CUT_RETURN_PCT: float = REAL_CUT_YIELD_PCT - 1.75
REAL_PREMIUM_PCT: float = T.PREMIUM_ALERT_PCT + 0.37


def etf_assessment(branch: str, ticker: str, *, peers: bool = True, light: str = T.LIGHT_1,
                   real_text: bool = False) -> ds.HoldingAssessment:
    """用真的 assess_holding 產生 8 盞燈，再以 dataclasses.replace 走到指定分支（action_branch 自驗）。

    `light`：add／pause_add 分支用哪一盞 235 燈（`T.LIGHT_1／2／3` → 來源 `DEPLOY_LIGHT1／2／3_PCT`）。
    `real_text=True`：cut／premium 的健檢旗標改由**真的** `ds.health_a`／`ds.health_d` 產生（真實格式
    「賺息賠本：年報酬 x% < 配息率 y%」「高溢價 p% > 門檻%」；A-T5／A-T7 選項 1 驗收案例 (g)）。"""
    a = _base_assessment(ticker, peers=peers)
    if branch == ds.ACTION_CUT and real_text:
        _fa = ds.health_a(total_return_1y_pct=REAL_CUT_RETURN_PCT, annual_yield_pct=REAL_CUT_YIELD_PCT)
        assert _fa.level == "🔴", _fa
        a = dataclasses.replace(a, health_a=_fa)
    elif branch == ds.ACTION_PREMIUM and real_text:
        _fd = ds.health_d(premium_pct=REAL_PREMIUM_PCT)
        assert _fd.level == "🟡", _fd
        a = dataclasses.replace(a, health_d=_fd)
    elif real_text:
        raise ValueError(f"real_text 只用於 cut／premium：{branch}")
    elif branch == ds.ACTION_CUT:
        a = dataclasses.replace(a, health_a=ds.Flag("🔴", "近一年含息總報酬低於配息率（吃本金）"))
    elif branch == ds.ACTION_TAKE_PROFIT_FORCE:
        a = dataclasses.replace(a, light=dataclasses.replace(a.light, take_profit="force"))
    elif branch == ds.ACTION_TAKE_PROFIT_PARTIAL:
        a = dataclasses.replace(a, light=dataclasses.replace(a.light, take_profit="partial"))
    elif branch == ds.ACTION_PAUSE_ADD:
        a = dataclasses.replace(a, light=_light(a.light, light),
                                health_c=ds.Flag("🟡", "季線下彎（趨勢轉弱）"))
    elif branch == ds.ACTION_ADD:
        a = dataclasses.replace(a, light=_light(a.light, light))
    elif branch == ds.ACTION_PREMIUM:
        a = dataclasses.replace(a, health_d=ds.Flag("🟡", "溢價偏高，不追高"))
    elif branch != ds.ACTION_CRUISE:
        raise ValueError(branch)
    # 健檢欄＝四盞取最嚴重（與 assess_holding 同一支 L2 函式重算，避免夾具自相矛盾）
    a = dataclasses.replace(a, worst_health=ds._worst_level(a.health_a, a.health_b, a.health_c, a.health_d))
    assert ds.action_branch(a) == branch, (branch, ds.action_branch(a))
    return a


def etf_row(branch: str, ticker: str = "0050", *, held: bool = True, price: float | None = 10.0,
            peers: bool = True, fx: bool = False, invalid_inputs: bool = False, light: str = T.LIGHT_1,
            real_text: bool = False) -> dict:
    r = svc.row_from_assessment(etf_assessment(branch, ticker, peers=peers, light=light, real_text=real_text))
    r["held"] = held
    r["現價"] = price
    if invalid_inputs and held:
        r[SS.KEY_INVALID_INPUTS] = (SS.ITEM_LOTS,)
    if fx and held:
        r[FXG.KEY_FX_UNCONFIRMED] = True
    svc._mark_insufficient(r, ak=T.KIND_ETF, held=held)
    return r


def stock_row(level: str, ticker: str = "2330", *, held: bool = True, price: float | None = 600.0,
              drift: bool = False, trend_verdict: str = "stable") -> dict:
    """真的 assess_stock：🔴（C 級、無 KD）／🟡（A 級＋死亡交叉）／🟢（A 級＋KD 值）／⚪（無財報）。"""
    _kd = {"k": 50.0, "d": 40.0, "label": "無"}
    _grade = {"🔴": "C", "🟡": "A", "🟢": "A", "⚪": None}[level]
    if level == "🟡":
        _kd = {"k": 40.0, "d": 50.0, "label": "死亡交叉", "cross": "death"}
    if drift:
        _grade = "Z"
    sa = ds.assess_stock(ticker=ticker, name=f"名-{ticker}", asset_class=T.ASSET_SATELLITE,
                         mj_grade=_grade, mj_score_pct=None if _grade is None else 70,
                         mj_headline="fixture", mj_fail_items=[], kd=_kd, trend={"verdict": trend_verdict})
    assert sa.swap_level == ("⚪" if drift else level), (level, sa.swap_level)
    r = svc.stock_row_from_assessment(sa)
    r["held"] = held
    r["現價"] = price
    svc._mark_insufficient(r, ak=T.KIND_STOCK, held=held)
    return r


def error_row(ticker: str = "9999", *, kind: str = T.KIND_ETF, held: bool = True) -> dict:
    return svc._error_row(ticker, f"名-{ticker}", T.ASSET_CORE, kind, "fixture timeout", held=held)


def digest(rows):
    return svc.build_station_digest(rows, None)


def risk_caps(C, agg) -> dict:
    """三種 Risk Cap state（valid 由真的 build_allocation_decision 建）。"""
    _alloc = build_allocation_decision({"is_loaded": True, "regime": "bull", "health": 80.0,
                                        "defense": False, "exposure_limit_pct": 40})
    _none = build_allocation_decision({"is_loaded": True, "regime": "bull", "health": 80.0,
                                       "defense": False, "exposure_limit_pct": None})
    _st = C.ActionSourceStamp(as_of="2026-11-20", source="fixture:risk_cap_state.json")
    return {
        "valid": agg.risk_cap_state_from_allocation(_alloc, stamp=_st),
        "invalid": agg.risk_cap_state_from_allocation(None, error="ValueError('讀壞')", stamp=_st),
        "missing": agg.risk_cap_state_from_allocation(_none, stamp=_st),
    }


def run(agg, C, rows, *, risk="missing", dig=None):
    return agg.aggregate_system_actions(
        station_rows=list(rows), station_digest=digest(rows) if dig is None else dig,
        risk_cap=risk_caps(C, agg)[risk], station_stamp=C.ActionSourceStamp(**STAMP_KW))


def run_with_basis(agg, C, rows, *, risk="missing", dig=None):
    """內部對照用：`(state, DayBasis)`（`_aggregate_with_basis`；`DayBasis` ⛔ 在公開輸出）。
    同時斷言公開 `aggregate_system_actions` 與內部 state 相等（同一份計算，⛔ 兩套判定）。"""
    kw = dict(station_rows=list(rows), station_digest=digest(rows) if dig is None else dig,
              risk_cap=risk_caps(C, agg)[risk], station_stamp=C.ActionSourceStamp(**STAMP_KW))
    st, basis = agg._aggregate_with_basis(**kw)
    assert agg.aggregate_system_actions(**kw) == st
    return st, basis


#: 凍結 O1～O5 的公開欄位（Gate §4.6.6：O1 items／O2 counts／O3 day_status／O4a risk_cap_state／
#: O4b exposure_gate／O5 provenance）。明列；⛔ 從契約反推。
O1_O5_FIELDS = ("items", "counts", "day_status", "risk_cap_state", "exposure_gate", "provenance")


def check_o1_o5_public_fields(agg, C) -> None:
    """公開 `SystemActionState` 欄位集合**等於**凍結 O1～O5（多一欄、少一欄皆紅）；實際輸出亦無 day_basis。"""
    import dataclasses
    names = [f.name for f in dataclasses.fields(C.SystemActionState)]
    assert set(names) == set(O1_O5_FIELDS) and len(names) == len(O1_O5_FIELDS), names
    st = run(agg, C, golden_scenarios()["seven_branches"], risk="valid")
    assert {f.name for f in dataclasses.fields(type(st))} == set(O1_O5_FIELDS)
    assert not hasattr(st, "day_basis")


def golden_scenarios() -> dict:
    """golden 夾具（名稱 → rows）。涵蓋七分支、四級、三種資料不足、整批失敗、觀察清單、空集合。"""
    B = ds
    return {
        "all_cruise_full": [etf_row(B.ACTION_CRUISE, "0050"), etf_row(B.ACTION_CRUISE, "0056")],
        "cruise_peer_missing": [etf_row(B.ACTION_CRUISE, "0050"), etf_row(B.ACTION_CRUISE, "006208", peers=False)],
        "seven_branches": [etf_row(b, f"00{i}T") for i, b in enumerate(
            (B.ACTION_CUT, B.ACTION_TAKE_PROFIT_FORCE, B.ACTION_TAKE_PROFIT_PARTIAL, B.ACTION_PAUSE_ADD,
             B.ACTION_ADD, B.ACTION_PREMIUM, B.ACTION_CRUISE))],
        "four_levels": [stock_row(lv, f"23{i}0") for i, lv in enumerate(("🔴", "🟡", "🟢", "⚪"))],
        "stock_keep_only": [stock_row("🟢", "2330"), stock_row("🟡", "2317")],
        # 財報趨勢 verdict 不認得 → 該燈 level 空、state 非 missing（判不出；judged_count 的 level 條件）
        "stock_trend_unknown_verdict": [stock_row("🟢", "2330", trend_verdict="not-a-verdict")],
        "mixed_with_error": [etf_row(B.ACTION_ADD, "0050"), error_row("9999"), stock_row("🟢", "2330")],
        "error_only": [error_row("9999"), error_row("8888", kind=T.KIND_STOCK)],
        "drift": [stock_row("🟢", "2330", drift=True), etf_row(B.ACTION_CRUISE, "0050")],
        "price_missing_kept": [etf_row(B.ACTION_PREMIUM, "0050", price=None), etf_row(B.ACTION_CRUISE, "0056")],
        "price_missing_cruise_replaced": [etf_row(B.ACTION_CRUISE, "0050", price=None)],
        "fx_unconfirmed": [etf_row(B.ACTION_CRUISE, "VOO", fx=True), etf_row(B.ACTION_CRUISE, "0050")],
        "invalid_inputs_cut": [etf_row(B.ACTION_CUT, "0050", invalid_inputs=True)],
        "watchlist": [etf_row(B.ACTION_ADD, "0050", held=False), etf_row(B.ACTION_CUT, "0056", held=False),
                      stock_row("🔴", "2330", held=False), etf_row(B.ACTION_CRUISE, "006208")],
        "add_and_undeterminable": [etf_row(B.ACTION_ADD, "0050"), stock_row("⚪", "2330")],
        # A-T5／A-T7 選項 1 驗收 (a)：add 三盞燈（加碼 20／30／50%，比例由來源 DEPLOY_LIGHT*_PCT 組出）
        "add_three_lights": [etf_row(B.ACTION_ADD, f"00{i}A", light=lk)
                             for i, lk in enumerate((T.LIGHT_1, T.LIGHT_2, T.LIGHT_3))],
        # A-T5／A-T7 選項 1 驗收 (g)：真實格式 cut（賺息賠本 x%／y%）與 premium（高溢價 p%）
        "real_format_cut_premium": [etf_row(B.ACTION_CUT, "00878", real_text=True),
                                    etf_row(B.ACTION_PREMIUM, "00919", real_text=True)],
        "empty": [],
    }


# ══════════════════════════════════════════════════════════════════════
# 檢查函式（A-T2～A-T7、A-T9、A-T10；突變測試共用）
# ══════════════════════════════════════════════════════════════════════

#: A-T2 期望表（獨立 oracle：Gate §4.6.6「計入規則」「分組」＋DEC-124；⛔ 從被測模組抄）。
#: (action_class, group, counts_toward_today, rule_id, risk_cap_tag)
EXPECT_ETF = {
    "cut": ("actionable", "減", True, "cut", ""),
    "take_profit_force": ("actionable", "減", True, "take_profit_force", ""),
    "take_profit_partial": ("actionable", "減", True, "take_profit_partial", ""),
    "pause_add": ("actionable", "留", True, "pause_add", ""),
    "add": ("actionable", "加", True, "add", "Risk Cap 無法判定"),
    "premium": ("non_actionable", "留", False, "", ""),
    "cruise": ("non_actionable", "留", False, "", ""),
}
EXPECT_SWAP = {
    "🔴": ("actionable", "換", True, "", ""),
    "🟡": ("non_actionable", "留", False, "", ""),
    "🟢": ("non_actionable", "留", False, "", ""),
    "⚪": ("undeterminable", "", False, "", ""),
}


def _sig(item):
    return (item.action_class, item.group, item.counts_toward_today, item.rule_id, item.risk_cap_tag)


def check_t2_table(agg, C) -> int:
    """A-T2：七分支 × 四級 × Risk Cap {valid, invalid, missing} 全組合。回傳檢查的組合數。"""
    n = 0
    for risk in ("valid", "invalid", "missing"):
        for branch, want in EXPECT_ETF.items():
            st = run(agg, C, [etf_row(branch, "0050")], risk=risk)
            assert len(st.items) == 1 and _sig(st.items[0]) == want, (risk, branch, _sig(st.items[0]))
            assert st.items[0].source_rule == branch and st.items[0].source_kind == "action_branch.v1"
            n += 1
        for level, want in EXPECT_SWAP.items():
            st = run(agg, C, [stock_row(level, "2330")], risk=risk)
            assert len(st.items) == 1 and _sig(st.items[0]) == want, (risk, level, _sig(st.items[0]))
            assert st.items[0].source_rule == level and st.items[0].source_kind == "swap_level"
            n += 1
    return n


def check_t2_data_short(agg, C) -> None:
    """A-T2（I7 對映表）：unjudged → undeterminable；price_missing／fx 原分支照帶＋data_short_kind；
    整批失敗 → unavailable；undeterminable 與 not_evaluated 分列。"""
    st = run(agg, C, golden_scenarios()["invalid_inputs_cut"])
    it = st.items[0]
    assert (it.action_class, it.group, it.counts_toward_today, it.data_short_kind) == (
        "undeterminable", "", False, "unjudged"), _sig(it)
    assert st.counts.undeterminable_n == 1 and st.counts.not_evaluated_n == 0
    st = run(agg, C, golden_scenarios()["price_missing_kept"])
    it = st.items[0]
    assert (it.source_rule, it.action_class, it.group, it.data_short_kind) == (
        "premium", "non_actionable", "留", "price_missing"), _sig(it)
    st = run(agg, C, [etf_row("add", "VOO", fx=True)])
    it = st.items[0]
    assert (it.action_class, it.counts_toward_today, it.data_short_kind) == ("actionable", True, "fx_unconfirmed")
    st = run(agg, C, golden_scenarios()["error_only"])
    assert [i.action_class for i in st.items] == ["unavailable", "unavailable"]
    assert [i.source_kind for i in st.items] == ["action_branch.v1", "swap_level"]
    assert st.counts.unavailable_n == 2 and st.counts.undeterminable_n == 0 and st.counts.not_evaluated_n == 0
    st = run(agg, C, golden_scenarios()["drift"])
    assert st.items[0].action_class == "undeterminable" and st.items[0].data_short_kind == "unjudged"
    # swap_level ⚪ 即使沒帶 KEY_INSUFFICIENT（上游漏標）也只能是 undeterminable，⛔ not_evaluated／續抱
    r = stock_row("⚪", "2330")
    r.pop(SS.KEY_INSUFFICIENT, None)
    st = run(agg, C, [r])
    assert (st.items[0].action_class, st.items[0].data_short_kind) == ("undeterminable", ""), _sig(st.items[0])
    assert st.counts.undeterminable_n == 1 and st.counts.not_evaluated_n == 0


def check_t3_w5(agg, C) -> None:
    """A-T3：暫停加碼計入；🟡 留意（無正式 action code）不計入；巡航／續抱／高溢價不計入。"""
    st = run(agg, C, [etf_row("pause_add", "0050")])
    assert st.items[0].counts_toward_today is True and st.counts.today_n == 1
    assert st.day_status == "needs_action"
    for rows in ([stock_row("🟡", "2317")], [stock_row("🟢", "2330")], [etf_row("cruise", "0050")],
                 [etf_row("premium", "0056")]):
        st = run(agg, C, rows)
        assert st.items[0].counts_toward_today is False and st.counts.today_n == 0, _sig(st.items[0])
        assert st.day_status != "needs_action"
    st = run(agg, C, golden_scenarios()["seven_branches"] + golden_scenarios()["four_levels"])
    # 加 1（add）＋減 3（cut／force／partial）＋暫停加碼 1＋換 1（🔴）＝ 6
    assert st.counts.today_n == 6, st.counts
    assert dict(st.counts.by_group) == {"加": 1, "留": 5, "換": 1, "減": 3}, dict(st.counts.by_group)


def check_t4_day_status(agg, C) -> None:
    """A-T4：「今日無需調整」只在 today_n=0 且 0 判不出、0 不可得、全列判全；任一判不出 → undeterminable。"""
    g = golden_scenarios()
    for name in ("all_cruise_full", "stock_keep_only"):   # 🟡 留意不計入（W-5）→ 全判得出即可「無需調整」
        st, basis = run_with_basis(agg, C, g[name])
        assert st.day_status == "no_adjustment_today", (name, basis, st.counts)
    expect_undet = ("cruise_peer_missing", "error_only", "drift", "price_missing_kept",
                    "price_missing_cruise_replaced", "fx_unconfirmed", "invalid_inputs_cut", "empty",
                    "stock_trend_unknown_verdict")
    for name in expect_undet:
        st, basis = run_with_basis(agg, C, g[name])
        assert st.counts.today_n == 0, name
        assert st.day_status == "undeterminable", (name, st.day_status, st.counts, basis)
    st = run(agg, C, g["add_and_undeterminable"])
    assert st.day_status == "needs_action" and st.counts.today_n == 1 and st.counts.undeterminable_n == 1
    # digest 層資料不足（例：errors 非空）單獨也擋得住，即使列本身全判得出。
    rows = g["all_cruise_full"]
    _d = dict(digest(rows))
    _d["errors"] = ["9999"]
    st, basis = run_with_basis(agg, C, rows, dig=_d)
    assert basis.digest_data_short is True and st.day_status == "undeterminable"


# ── A-T5／A-T7 範圍（選項 1；#1199 comment 7062611025；總管技術裁定〔GPT 接任總管，#1199 comment 7062910532；非客戶裁示〕2026-11-21） ─────────────
# 1) 比例禁令（`_RATIO_RE`）**只**適用 Aggregator **自產欄位**：action_class／group／day_status／
#    risk_cap_tag／counts（含 by_group 鍵）／source_kind／source_rule／rule_id／data_short_kind／
#    exposure_gate／provenance 的版本與輸入名，及其他 Aggregator 自己組出的字串。採**預設全掃**：
#    只有下列 `T5_PASSTHROUGH_FIELDS` 的來源透傳欄位不套比例正則（新增欄位自動落入自產範圍）。
# 2) O1 `formal_label` 依 A-T7 **逐字**透傳來源「建議動作」，其中既有百分比 —— 「加碼 20／30／50%」
#    （N≡`shared/dividend_station_thresholds.DEPLOY_LIGHT1/2/3_PCT`）、汰弱「賺息賠本：年報酬 x% <
#    配息率 y%」、高溢價「高溢價 p% > PREMIUM_ALERT_PCT%」—— 不屬 Aggregator 產生；整欄改由 A-T7
#    byte-identical 比對＋`check_t7_option1_real_labels` 規則複本守護（⛔ 增刪改任一字元）。
# 3) **整份輸出（含 formal_label）**仍 ⛔「減碼 1/2」「全出」（`_FORBIDDEN_ANYWHERE`）與新 action code。
_FORBIDDEN_ANYWHERE = ("減碼 1/2", "減碼1/2", "1/2", "１/２", "1／2", "１／２", "½", "全出")
#: 比例字樣（只套自產欄位）：半形／全形百分號（`\d` 亦含全形數字）、分數、N 成（阿拉伯／中文數字）、半、分之。
_RATIO_RE = re.compile(r"\d+\s*[%％]|\d+\s*[/／]\s*\d+|\d+\s*成|[一二兩三四五六七八九十]\s*成|半|分之")
#: 來源透傳欄位（不屬 Aggregator 產生；比例正則豁免、禁令字樣照掃）。改這張表＝改 A-T5 範圍，須經 Gate。
T5_PASSTHROUGH_FIELDS = (
    "items[*].formal_label",        # O1 來源「建議動作」逐字（A-T7 守護）
    "items[*].ticker", "items[*].name",
    "items[*].stamp.*",             # I5 as_of／source
    "risk_cap_state.*",             # O4a＝I4 原樣傳遞（A-T10 守護）
    "provenance.inputs[*][1].*",    # O5 各輸入的 as_of／source
)
_PASSTHROUGH_PATH_RE = re.compile(
    r"^state\.items\[\d+\]\.(?:formal_label|ticker|name|stamp\.[A-Za-z_]+)$"
    r"|^state\.risk_cap_state\."
    r"|^state\.provenance\.inputs\[\d+\]\[1\]\.")


def _strings(obj, path="state"):
    if isinstance(obj, str):
        yield path, obj
    elif dataclasses.is_dataclass(obj):
        for f in dataclasses.fields(obj):
            yield from _strings(getattr(obj, f.name), f"{path}.{f.name}")
    elif isinstance(obj, (tuple, list)):
        for i, x in enumerate(obj):
            yield from _strings(x, f"{path}[{i}]")
    elif hasattr(obj, "items") and callable(obj.items):
        for k, v in obj.items():
            yield from _strings(k, f"{path}<key>")
            yield from _strings(v, f"{path}[{k!r}]")


def is_t5_passthrough(path: str) -> bool:
    return bool(_PASSTHROUGH_PATH_RE.search(path))


def t5_violations(st) -> list:
    """A-T5 掃描（選項 1）：回傳 [(path, 字串, 原因)]。整份輸出掃禁令字樣；自產欄位另掃比例字樣。"""
    out = []
    for path, s in _strings(st):
        for bad in _FORBIDDEN_ANYWHERE:
            if bad in s:
                out.append((path, s, f"forbidden:{bad}"))
        if not is_t5_passthrough(path) and _RATIO_RE.search(s):
            out.append((path, s, "ratio"))
    return out


def check_t5_forbidden(agg, C) -> None:
    """A-T5（選項 1）：整份輸出 ⛔「減碼 1/2」「全出」；Aggregator 自產欄位 ⛔ 任何比例字樣（含全形％）；
    ⛔ 新 action code。`formal_label` 的既有來源百分比（加碼 N%／賺息賠本／高溢價）由 A-T7 逐字守護。"""
    allowed_rules = set(EXPECT_ETF) | set(EXPECT_SWAP) | {""}
    for name, rows in golden_scenarios().items():
        for risk in ("valid", "invalid", "missing"):
            st = run(agg, C, rows, risk=risk)
            bad = t5_violations(st)
            assert not bad, (name, risk, bad)
            for it in st.items:
                assert it.source_rule in allowed_rules, it.source_rule
                assert it.group in ("加", "留", "換", "減", ""), it.group


def check_t6_rule_ids(agg, C) -> None:
    """A-T6：每個 item 的 rule_id ⊆ RULE_ID_ALLOWLIST（或空）。"""
    from shared.decision_digest_rules import RULE_ID_ALLOWLIST
    for name, rows in golden_scenarios().items():
        st = run(agg, C, rows)
        for it in st.items:
            assert it.rule_id == "" or it.rule_id in RULE_ID_ALLOWLIST, (name, it.rule_id)
            if it.rule_id:
                assert it.action_class == "actionable" and it.rule_id == it.source_rule


def check_t7_verbatim(agg, C) -> None:
    """A-T7：formal_label 與來源 `建議動作` byte-identical；ticker／name 亦原樣。"""
    for name, rows in golden_scenarios().items():
        st = run(agg, C, rows)
        assert len(st.items) == len(rows)
        for it, r in zip(st.items, rows):
            assert it.formal_label.encode("utf-8") == r["建議動作"].encode("utf-8"), (name, it.formal_label)
            assert it.ticker == r["代號"] and it.name == r["名稱"]


# ── A-T7 選項 1：formal_label 中來源既有百分比的**規則複本**（驗收案例 (f)；來源改動即轉紅、人工複核） ──
#: `shared/dividend_station_thresholds.DEPLOY_LIGHT1/2/3_PCT` 的值複本（⛔ 從被測模組或來源反推）。
PINNED_DEPLOY_PCT = {"DEPLOY_LIGHT1_PCT": 20.0, "DEPLOY_LIGHT2_PCT": 30.0, "DEPLOY_LIGHT3_PCT": 50.0}
#: `shared/dividend_station_thresholds.PREMIUM_ALERT_PCT` 的值複本。
PINNED_PREMIUM_ALERT_PCT = 1.5
#: `dividend_station.suggest_action` add 分支句型複本：`{icon} 加碼 {deploy_pct:.0f}%：{reasons}{（深水註）}`。
PINNED_ADD_RE = re.compile(r"^(?P<icon>🟢|🟡|🔴) 加碼 (?P<pct>20|30|50)%：(?P<rest>.+)$")
#: cut 分支＋健檢 A 🔴 句型複本：`🔴 汰弱：賺息賠本：年報酬 {x:.1f}% < 配息率 {y:.1f}%（吃到本金）`。
PINNED_CUT_RE = re.compile(r"^🔴 汰弱：賺息賠本：年報酬 -?\d+\.\d% < 配息率 -?\d+\.\d%（吃到本金）$")
#: premium 分支＋健檢 D 🟡 句型複本：`🟡 高溢價 {p:.2f}% > {PREMIUM_ALERT_PCT}% → 不追高`。
PINNED_PREMIUM_RE = re.compile(r"^🟡 高溢價 -?\d+\.\d{2}% > 1\.5% → 不追高$")


def check_rule_copies_pinned() -> None:
    """(f)：來源常數值＝規則複本（DEPLOY_LIGHT*_PCT 三值、LIGHT_META 對映、PREMIUM_ALERT_PCT）。"""
    assert {k: getattr(T, k) for k in PINNED_DEPLOY_PCT} == PINNED_DEPLOY_PCT
    assert [T.LIGHT_META[k]["deploy_pct"] for k in (T.LIGHT_1, T.LIGHT_2, T.LIGHT_3)] == list(
        PINNED_DEPLOY_PCT.values())
    assert T.PREMIUM_ALERT_PCT == PINNED_PREMIUM_ALERT_PCT


def check_t7_option1_real_labels(agg, C) -> int:
    """A-T5／A-T7 選項 1 驗收 (a)(f)(g)：真實格式 add（加碼 20／30／50%）、cut（賺息賠本 x%／y%）、
    premium（高溢價 p%）的 formal_label ＝來源 `suggest_action` 逐字（byte-identical）、符合規則複本句型，
    且整份輸出通過 A-T5（自產欄位無比例、全份無「減碼 1/2」「全出」）。回傳檢查的 label 數。"""
    check_rule_copies_pinned()
    n = 0
    lights = (T.LIGHT_1, T.LIGHT_2, T.LIGHT_3)
    rows = golden_scenarios()["add_three_lights"]
    st = run(agg, C, rows)
    assert not t5_violations(st), t5_violations(st)
    for lk, it, r in zip(lights, st.items, rows, strict=True):
        src = ds.suggest_action(etf_assessment(ds.ACTION_ADD, it.ticker, light=lk))
        assert it.formal_label.encode("utf-8") == r["建議動作"].encode("utf-8") == src.encode("utf-8"), lk
        _m = PINNED_ADD_RE.match(it.formal_label)
        assert _m, it.formal_label
        _pct = T.LIGHT_META[lk]["deploy_pct"]
        assert float(_m["pct"]) == _pct and _m["icon"] == T.LIGHT_META[lk]["icon"], (lk, it.formal_label)
        assert f"加碼 {_pct:.0f}%" in it.formal_label
        assert it.source_rule == "add" and it.group == "加" and it.risk_cap_tag == "Risk Cap 無法判定"
        n += 1
    assert sorted(float(PINNED_ADD_RE.match(i.formal_label)["pct"]) for i in st.items) == sorted(
        PINNED_DEPLOY_PCT.values())
    rows = golden_scenarios()["real_format_cut_premium"]
    st = run(agg, C, rows)
    assert not t5_violations(st), t5_violations(st)
    cut, prem = st.items
    _a_cut = etf_assessment(ds.ACTION_CUT, cut.ticker, real_text=True)
    _a_prem = etf_assessment(ds.ACTION_PREMIUM, prem.ticker, real_text=True)
    for it, r, a, pat in ((cut, rows[0], _a_cut, PINNED_CUT_RE), (prem, rows[1], _a_prem, PINNED_PREMIUM_RE)):
        src = ds.suggest_action(a)
        assert it.formal_label.encode("utf-8") == r["建議動作"].encode("utf-8") == src.encode("utf-8")
        assert pat.match(it.formal_label), it.formal_label
        assert _RATIO_RE.search(it.formal_label)        # 確實含資料百分比（選項 1 允許、逐字）
        n += 1
    assert cut.formal_label == "🔴 汰弱：" + ds.health_a(total_return_1y_pct=REAL_CUT_RETURN_PCT,
                                                         annual_yield_pct=REAL_CUT_YIELD_PCT).msg
    assert prem.formal_label == "🟡 " + ds.health_d(premium_pct=REAL_PREMIUM_PCT).msg
    assert (cut.source_rule, cut.group, prem.source_rule, prem.group) == ("cut", "減", "premium", "留")
    return n


def check_t9_slice_independent(agg, C) -> None:
    """A-T9：輸出不受 consumer 的 top_n／收合影響 —— 不截斷、不重排、無呈現參數、重複呼叫相同。"""
    import inspect
    params = set(inspect.signature(agg.aggregate_system_actions).parameters)
    assert params == {"station_rows", "station_digest", "risk_cap", "station_stamp"}, params
    rows = [etf_row(("add", "cut", "cruise", "pause_add")[i % 4], f"T{i:03d}") for i in range(40)]
    st1 = run(agg, C, rows)
    st2 = run(agg, C, rows)
    assert st1 == st2
    assert [i.ticker for i in st1.items] == [r["代號"] for r in rows]
    assert st1.counts.today_n == 30 and st1.counts.by_group["加"] == 10
    assert len(st1.items) == len(rows) == 40


def check_t10_risk_cap(agg, C) -> None:
    """A-T10：O4a 與輸入 I4 逐欄相等（原樣傳遞）；O4b 恆 undeterminable；⛔ 自產數值。"""
    rows = golden_scenarios()["seven_branches"]
    caps = risk_caps(C, agg)
    assert caps["valid"].status == "valid" and caps["valid"].system_cap_pct == 40
    assert caps["missing"].status == "missing" and caps["missing"].system_cap_pct is None
    assert caps["invalid"].status == "invalid" and caps["invalid"].error == "ValueError('讀壞')"
    for risk, rc in caps.items():
        st = agg.aggregate_system_actions(station_rows=rows, station_digest=digest(rows), risk_cap=rc,
                                          station_stamp=C.ActionSourceStamp(**STAMP_KW))
        for f in dataclasses.fields(rc):
            assert getattr(st.risk_cap_state, f.name) == getattr(rc, f.name), (risk, f.name)
        assert st.risk_cap_state == rc
        assert st.exposure_gate.status == "undeterminable", risk
        tags = {(i.source_rule, i.risk_cap_tag) for i in st.items}
        assert ("add", "Risk Cap 無法判定") in tags and all(
            t == "" for r, t in tags if r != "add"), tags
        assert dict(st.provenance.inputs)["risk_cap"] == rc.stamp


def check_t3_watchlist(agg, C) -> None:
    """A-T3 補：觀察清單（held=False）的加／換／減 ⛔ 計入今日需處理（同 digest watch_adds 不計入）。"""
    st = run(agg, C, golden_scenarios()["watchlist"])
    assert st.counts.today_n == 0, st.counts
    assert [i.action_class for i in st.items[:3]] == ["actionable"] * 3


def check_t4_contract_guard(agg, C) -> None:
    """A-T4（縱深，L0 契約）：有任何判不出／不可得時，SystemActionState ⛔ 建成 no_adjustment_today。"""
    _g = {g: 0 for g in C.GROUPS}
    for kw in ({"undeterminable_n": 1}, {"not_evaluated_n": 1}, {"unavailable_n": 1}, {"incomplete_rows_n": 1}):
        _c = dict(today_n=0, by_group=_g, not_evaluated_n=0, undeterminable_n=0, unavailable_n=0,
                  incomplete_rows_n=0)
        _c.update(kw)
        try:
            C.SystemActionState(items=(), counts=C.ActionCounts(**_c), day_status=C.DAY_NO_ADJUSTMENT_TODAY,
                                risk_cap_state=C.RiskCapState(status=C.RISK_CAP_MISSING),
                                exposure_gate=C.ExposureGate(), provenance=C.ActionProvenance(inputs=()))
        except ValueError:
            continue
        raise AssertionError(f"契約放行了 no_adjustment_today 且 {kw}")


def _patched_page_hold(rows):
    """以真的 page_hold.load_station 計算（只把 L3 取數換成固定列；build_station_digest 等其餘照真的跑）。"""
    from src.ui.views import page_hold as PH
    _orig = svc.get_station_rows
    svc.get_station_rows = lambda holdings: (list(rows), None)
    try:
        _hr = PH.HoldingsReadout(requested=True, bound=True,
                                 holdings=tuple({"ticker": r["代號"]} for r in rows) or ({"ticker": "X"},))
        return PH.load_station(_hr), PH
    finally:
        svc.get_station_rows = _orig


def check_t8_parity(agg, C) -> int:
    """A-T8：與既有 judged_count／is_fully_judged／aggregate_judged／tally_states／cruise_or_gap
    （L4 station_cards）、row_short_kind／total_judged／digest_data_short（L0）、
    page_hold.load_station 的 _unjudged／unjudged_rows 口徑在 golden 夾具上一致。回傳比對次數。"""
    from shared import holdings_data_short as HDS
    from src.ui.render import station_cards as SC
    from src.ui.views import risk_cap_gate as RCG
    n = 0
    assert agg.CRUISE_TEXT == SC.CRUISE_TEXT
    for name, rows in golden_scenarios().items():
        cells = [(r.get("_lights") or ()) for r in rows]
        for c in cells:
            assert agg.judged_count(c) == SC.judged_count(c), name
            assert agg.is_fully_judged(c) == SC.is_fully_judged(c), name
            n += 2
        assert agg.judged_count(()) == SC.judged_count(()) and agg.is_fully_judged(()) == SC.is_fully_judged(())
        assert agg.aggregate_judged(cells) == SC.aggregate_judged(cells), name
        assert agg.tally_states(cells) == SC.tally_states(cells), name
        j, t = SC.aggregate_judged(cells)
        for b in (True, False):
            assert agg.cruise_or_gap(j, t, all_rows_judged=b) == SC.cruise_or_gap(j, t, all_rows_judged=b)
        n += 4
        dig = digest(rows)
        st, basis = run_with_basis(agg, C, rows, dig=dig)
        assert [i.data_short_kind for i in st.items] == [HDS.row_short_kind(dict(r)) or "" for r in rows], name
        assert basis.digest_data_short == HDS.digest_data_short(dig), name
        assert HDS.total_judged(dig.get("total")) or st.day_status != "no_adjustment_today", name
        assert (basis.judged_lights, basis.total_lights) == SC.aggregate_judged(cells), name
        assert dict(basis.tally) == SC.tally_states(cells), name
        n += 5
        if rows:
            ph, PH = _patched_page_hold(rows)
            assert ph.error == "", (name, ph.error)
            assert st.counts.incomplete_rows_n == ph.unjudged_rows, (name, st.counts.incomplete_rows_n,
                                                                     ph.unjudged_rows)
            assert (basis.judged_lights, basis.total_lights) == (ph.judged, ph.total_lights), name
            assert dict(basis.tally) == dict(ph.tally), name
            assert basis.cruise_gate_open == (ph.cruise_text == PH._clean_signal(SC.CRUISE_TEXT)), name
            n += 4
    for j, t in ((0, 0), (3, 3), (2, 3), (0, 5), (5, 5)):
        for b in (True, False):
            assert agg.cruise_or_gap(j, t, all_rows_judged=b) == SC.cruise_or_gap(j, t, all_rows_judged=b)
            n += 1
    alloc_caps = [build_allocation_decision({"is_loaded": True, "regime": "bull", "health": 80.0,
                                             "defense": False, "exposure_limit_pct": p}).caps for p in (40, None)]
    for caps in alloc_caps + [(), None]:
        assert agg.has_system_risk_cap(caps) == RCG.has_system_risk_cap(caps)
        n += 1
    return n
