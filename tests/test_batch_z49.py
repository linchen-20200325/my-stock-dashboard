"""批 Z49 —— 數值資料異常（NaN／±inf／轉不成數字）的同一批防呆（客戶 2026-10-13 裁示 B）。

客戶裁示（逐字）：統一採用「{項目}資料異常，無法計算，不下結論。」
  · NaN／±inf／其他無效數值一律視為異常；不顯示 nan／inf；
  · 不使用替代值繼續計算（例如 Beta 不得自動補 1.0）；
  · 該數值會影響結論時，該卡停止計算並不下結論；
  · 正常資料路徑不得改變；不擴大修改資料層、公式、門檻、權重、版面或其他文案。

五處（修前實測重現）：
  1. 持股頁衛星停利卡：現價 inf → 「1 檔達停利門檻」「可停利」「2330（inf%）」。
  2. 持股頁③燈牆＋①該做什麼：折溢價 NaN → 健檢 D 綠燈、巡航；配息率 inf → 健檢 A 汰弱紅燈。
  3. 查一檔頁估值（357）卡：配息均值 NaN／inf → 印 nan／inf 並下「逢高減碼」「存股首選」。
  4. 持股頁壓力測試卡：Beta NaN／inf → 「約 nan 元」「門檻內」／「約 inf 元」「超過門檻」。
  5. 持股頁總額、80/20、核心／衛星：張數／均價／現價 inf → 印 nan／inf、80/20 誤判「接近目標」。

本檔驗：
  A. L0 判定與逐字句。
  B. 五處各自：NaN／+inf／-inf（／轉不成數字）→ 畫面無 nan／inf、無結論字樣、出現逐字新句。
  C. 正常路徑：與修前**逐值相同**（修前＝現行原始碼套上本批全部 revert pair；該組 revert 與
     `git show 18b51ea0:<path>`（本批之前的 main）的等價性已在開發時以 git 版本跑同一組測試驗過 ——
     測試本身不呼叫 git，見 `tests/test_zz_test_portability.py`）。
  D. revert-pair 突變：把本批的防呆換回修前那一行 → 對應斷言轉紅。
"""
from __future__ import annotations

import dataclasses
import functools
import math
import pathlib
import re
import sys
import types

import numpy as np
import pandas as pd
import pytest

import src.compute.etf.dividend_station as DSL2
import src.compute.etf.etf_calc as EC
import src.services.dividend_station_service as S
import src.services.portfolio_deep_service as D
import src.services.valuation_service as V
import src.ui.views.page_hold as PH
import src.ui.views.page_inspect as PI
from shared import station_specs as SS
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE

_ROOT = pathlib.Path(__file__).resolve().parents[1]

_BAD = {"nan": float("nan"), "pos_inf": float("inf"), "neg_inf": float("-inf")}
_BAD_STR = {**_BAD, "text": "abc"}
_NONFINITE_RE = re.compile(r"(?i)(?<![a-z])(nan|inf|infinity)(?![a-z])")


def _sentence(item: str) -> str:
    return f"{item}資料異常，無法計算，不下結論。"


def _no_nonfinite(text: str) -> None:
    _hit = _NONFINITE_RE.search(text)
    assert _hit is None, f"畫面出現 {_hit.group(0)!r}：…{text[max(0, _hit.start() - 40):_hit.end() + 40]}…"


# ══════════════════════════════════════════════════════════════════
# 變體載入（revert-pair ／ 修前 git 版本）
# ══════════════════════════════════════════════════════════════════
def _exec_module(name: str, path: pathlib.Path, code: str) -> types.ModuleType:
    m = types.ModuleType(name)
    m.__file__ = str(path)
    sys.modules[name] = m           # dataclass 解析註解需要模組已註冊
    exec(compile(code, str(path), "exec"), m.__dict__)
    return m


@functools.lru_cache(maxsize=None)
def _variant(rel: str, pairs: tuple[tuple[str, str], ...], name: str) -> types.ModuleType:
    """現行原始碼只套 `pairs`（修後 → 修前），載成獨立模組物件（不影響本尊）。"""
    path = _ROOT / rel
    code = path.read_text(encoding="utf-8")
    for new, old in pairs:
        assert code.count(new) == 1, f"替換點不唯一或已不存在：{new[:70]!r}"
        code = code.replace(new, old)
    return _exec_module(name, path, code)


def _pre(rel: str) -> types.ModuleType:
    """修前行為：現行原始碼套上**本批全部** revert pair（`_PRE_PAIRS[rel]`）。

    ⚠️ 本 repo 測試不准呼叫外部程式（`tests/test_zz_test_portability.py`），故不在測試裡
    `git show`。這組 revert 的等價性已在本批開發時**另以 `git show 18b51ea0:<rel>`（修前 main）
    逐檔比對過**：同一組 C 類測試把 `_pre` 換成 git 版本照樣全過（見批 Z49 回報）。
    """
    return _variant(rel, _PRE_PAIRS[rel], f"_z49_pre_{rel.replace('/', '_').removesuffix('.py')}")


# ══════════════════════════════════════════════════════════════════
# 合成資料（確定性，不用亂數）
# ══════════════════════════════════════════════════════════════════
_WK = pd.Series(np.linspace(20, 30, 120),
                index=pd.date_range("2023-01-06", periods=120, freq="W-FRI"))
_PX_IDX = pd.bdate_range("2025-01-02", periods=60)


def _etf_metrics(**over) -> dict:
    base = dict(weekly_close=_WK, premium_pct=0.3, sharpe=0.8, total_return_1y_pct=10.0,
                annual_yield_pct=5.0, inception_years=5.0, ann_return_3y_pct=8.0,
                cum_return_3y_pct=25.0, peer_ranks={3: .2, 6: .2, 12: .2}, current_price=30.0)
    base.update(over)
    return base


def _stock_metrics(price) -> dict:
    return {"mj_grade": None, "mj_score_pct": None, "mj_headline": "", "mj_fail_items": [],
            "kd_state": None, "current_price": price, "name": "", "trend_verdict": None}


def _metrics_fn(prices: dict, etf_over: dict | None = None):
    def fn(tk, kind):
        if kind == "etf":
            return _etf_metrics(**{"current_price": prices.get(tk), **(etf_over or {})})
        return _stock_metrics(prices.get(tk))
    return fn


def _h(tk, kind, lots=1.0, avg=100.0, held=True) -> dict:
    return {"ticker": tk, "name": tk, "asset_kind": kind, "lots": lots, "avg_price": avg,
            "held": held}


#: 基準組合：衛星 2330、2317（個股）＋ 核心 0050（ETF）。2330 的值由各測試換成異常值。
def _holdings(**bad) -> list[dict]:
    return [_h("2330", "stock", lots=bad.get("lots", 1.0), avg=bad.get("avg", 100.0)),
            _h("2317", "stock", lots=2.0, avg=100.0),
            _h("0050", "etf", lots=3.0, avg=25.0)]


def _prices(**bad) -> dict:
    return {"2330": bad.get("price", 120.0), "2317": 118.0, "0050": 30.0}


def _close_df(offset: float) -> pd.DataFrame:
    return pd.DataFrame({"Close": [100.0 + offset + (i % 5) for i in range(len(_PX_IDX))]},
                        index=_PX_IDX)


def _tax_view(items, marginal_rate=None):
    return {"summary": {"gross": 1000.0 * len(items), "nhi_premium": 0.0,
                        "net_after_nhi": 1000.0 * len(items)},
            "per_etf": [{"代號": _i["ticker"], "配息筆數": 1} for _i in items],
            "overseas": [], "n_tw": len(items)}


@pytest.fixture
def offline(monkeypatch):
    """把 ⑥ 三支 L3 會打的上游全部換成確定性替身（不連網）。"""
    _beta = {"value": 1.1}
    monkeypatch.setattr("src.data.etf.etf_fetch.fetch_etf_price",
                        lambda t, period="1y", failed=None: _close_df(len(str(t))))
    monkeypatch.setattr("src.compute.etf.etf_calc.fetch_etf_info",
                        lambda t: {"beta": _beta["value"]})
    monkeypatch.setattr("src.services.dividend_tax_service.get_dividend_tax_view", _tax_view)
    return _beta


def _rows(Smod, holdings, prices, etf_over=None):
    return Smod.build_station_rows(holdings, vix=15.0,
                                   metrics_fn=_metrics_fn(prices, etf_over))


def _load(P, Smod, monkeypatch, holdings, prices, etf_over=None):
    """走 L5 真的 `load_station()`／`load_deep()`（只把 L3 抓取換成合成列）。"""
    monkeypatch.setattr(
        "src.services.dividend_station_service.get_station_rows",
        lambda hs: (_rows(Smod, hs, prices, etf_over), 15.0))
    for _n in ("build_station_digest", "compute_portfolio_totals"):
        monkeypatch.setattr(f"src.services.dividend_station_service.{_n}", getattr(Smod, _n))
    h = P.HoldingsReadout(requested=True, submitted=True, bound=True,
                          holdings=tuple(holdings))
    st = P.load_station(h)
    return st, P.load_deep(st)


_STATION_CARDS = ("build_action_card", "build_confidence_card", "build_todo_card",
                  "build_lightwall_card", "build_allocation_split_card",
                  "build_take_profit_card", "build_core_satellite_card")
_DEEP_CARDS = ("build_stress_card", "build_var_card", "build_dividend_cash_card")


def _built(P, st, deep) -> dict[str, tuple]:
    out = {_n: getattr(P, _n)(st) for _n in _STATION_CARDS}
    out.update({_n: getattr(P, _n)(deep) for _n in _DEEP_CARDS})
    return out


def _same(a, b) -> bool:
    """深比較（列裡有 pandas 序列，`==` 會拋「truth value is ambiguous」）。"""
    if isinstance(a, (pd.Series, pd.DataFrame, pd.Index)):
        return type(a) is type(b) and a.equals(b)
    if isinstance(a, dict):
        return (isinstance(b, dict) and list(a) == list(b)
                and all(_same(a[_k], b[_k]) for _k in a))
    if isinstance(a, (list, tuple)):
        return (type(a) is type(b) and len(a) == len(b)
                and all(_same(_x, _y) for _x, _y in zip(a, b)))
    if isinstance(a, float) and isinstance(b, float) and a != a and b != b:
        return True
    return a == b


def _blob(P, built) -> str:
    card, facts, sig = built
    return repr(card) + repr(tuple(facts)) + sig + P.v2_card_html(card, facts, sig)


# ══════════════════════════════════════════════════════════════════
# A. L0
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("v", [float("nan"), float("inf"), float("-inf"), "nan", "inf",
                               "-inf", "abc", object(), np.nan, np.float64("inf")],
                         ids=repr)
def test_l0_invalid(v):
    assert SS.is_invalid_number(v) is True


@pytest.mark.parametrize("v", [None, "", "   ", 0, 0.0, -5.0, 1, 1.5, "1.5", np.float64(2.0),
                               True, 1e308], ids=repr)
def test_l0_not_invalid(v):
    """缺值（None／空白）與有限數（含 0、負數）都**不是**本批的「異常」—— 照各處既有規則。"""
    assert SS.is_invalid_number(v) is False


def test_l0_sentence_is_verbatim():
    assert SS.INVALID_DATA_TEXT == "{item}資料異常，無法計算，不下結論。"
    for _i in ("現價", "張數", "均價", "折溢價", "配息率", "配息", "Beta"):
        assert SS.invalid_data_text(_i) == _sentence(_i)


# ══════════════════════════════════════════════════════════════════
# B-1／B-5. 持股頁：現價／張數／均價異常（停利、總額、80/20、核心／衛星、⑥ 三格）
# ══════════════════════════════════════════════════════════════════
#: 各卡會受哪個輸入影響（＝本批的「影響結論就停」）。
_AFFECTS = {
    "price": {"totals", "split", "take_profit", "stress", "var"},
    "lots": {"totals", "split", "stress", "var", "cash"},
    "avg": {"totals", "take_profit", "stress", "var"},
}
_ITEM = {"price": "現價", "lots": "張數", "avg": "均價"}
_CONCLUSION_WORDS = ("可停利", "接近目標", "偏離", "門檻內", "超過門檻",
                     "月度尾部可控", "月度尾部偏高", "達停利門檻")


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
@pytest.mark.parametrize("field", ["price", "lots", "avg"])
def test_l3_row_marks_invalid_and_never_computes_with_it(field, bad):
    hs = _holdings(**({field: _BAD_STR[bad]} if field != "price" else {}))
    rows = _rows(S, hs, _prices(**({"price": _BAD_STR[bad]} if field == "price" else {})))
    r = rows[0]
    assert r["代號"] == "2330" and not r["_detail"].get("error"), "轉不成數字不得被講成整批抓取失敗"
    assert r[SS.KEY_INVALID_INPUTS] == (_ITEM[field],)
    assert r[{"price": "現價", "lots": "張數", "avg": "均價"}[field]] is None
    for _k in ("市值", "損益%", "張數", "均價", "現價"):
        _v = r[_k]
        assert _v is None or math.isfinite(_v), f"{_k}={_v!r}"
    assert all(SS.KEY_INVALID_INPUTS not in _r for _r in rows[1:]), "正常列不得帶這一鍵"
    # L3 彙總：影響到的就整個不算（⛔ 不剔除那一檔後照算）
    assert S.compute_portfolio_totals(rows) is None
    assert (S.compute_allocation_split(rows) is None) == (field in ("price", "lots"))
    assert all(math.isfinite(_t["損益%"]) for _t in S.flag_take_profit(rows))


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
@pytest.mark.parametrize("field", ["price", "lots", "avg"])
def test_hold_cards_stop_and_show_the_sentence(field, bad, monkeypatch, offline):
    hs = _holdings(**({field: _BAD_STR[bad]} if field != "price" else {}))
    px = _prices(**({"price": 999.0 if field != "price" else _BAD_STR[bad]}))
    st, deep = _load(PH, S, monkeypatch, hs, px)
    out = _built(PH, st, deep)
    sentence = _sentence(_ITEM[field])
    for _name, _b in out.items():
        _no_nonfinite(_blob(PH, _b))
    # 總額（① 該做什麼的金額列）
    facts = dict(out["build_action_card"][1])
    assert facts["未實現損益／總市值"] == f"2330：{sentence}"
    assert "未實現損益（元）" not in facts and "總市值（元）" not in facts
    # 80/20 ＋ 核心／衛星
    for _n in ("build_allocation_split_card", "build_core_satellite_card"):
        card, _f, sig = out[_n]
        if "split" in _AFFECTS[field]:
            assert card.state == UI_FAILED and card.value == "" and sig == ""
            assert f"2330：{sentence}" in card.note.why
        else:
            assert card.state == UI_LIVE, "均價不進市值 —— 只有均價異常時 80/20 照算"
    # 衛星停利
    card, facts_tp, sig = out["build_take_profit_card"]
    if "take_profit" in _AFFECTS[field]:
        assert card.state == UI_FAILED and sig == "" and card.value == ""
        assert card.note.why == f"2330：{sentence}"
    else:
        assert card.state != UI_FAILED
    # ⑥ 壓測／VaR／配息
    for _n, _key in (("build_stress_card", "stress"), ("build_var_card", "var"),
                     ("build_dividend_cash_card", "cash")):
        card, _f, sig = out[_n]
        if _key in _AFFECTS[field]:
            assert card.state == UI_FAILED and sig == "" and card.value == ""
            assert card.note.why == f"2330：{sentence}", (_n, card.note.why)
        else:
            assert card.state == UI_LIVE, (_n, card.state)
    # 有停的卡一律沒有結論字樣
    for _n, (card, facts_, sig) in out.items():
        if card.state == UI_FAILED:
            assert not any(_w in sig + card.value for _w in _CONCLUSION_WORDS), _n


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_hold_take_profit_was_concluding_before(bad, monkeypatch, offline):
    """**修前**（L3 偵測拔掉）：+inf 現價 → 停利卡下「可停利」並印 inf；NaN／-inf 現價過不了
    修前的 `> 0` 擋關 → 被講成「這檔查不到報價」（原因講錯）。本批兩種都改成逐字新句。"""
    pre_s = _variant("src/services/dividend_station_service.py", (Z49_L3_ROWS_PAIR,),
                     "_z49_no_detect_svc")
    st, deep = _load(PH, pre_s, monkeypatch, _holdings(), _prices(price=_BAD[bad]))
    out = _built(PH, st, deep)
    blob = "".join(_blob(PH, _b) for _b in out.values())
    tp_pre = out["build_take_profit_card"]
    if bad == "pos_inf":
        assert _NONFINITE_RE.search(blob) and tp_pre[2] == "可停利", "修前的錯誤結論沒重現"
    else:
        assert tp_pre[0].note.why == f"2330：{PH.NO_PRICE_WHY}", "修前的錯誤原因沒重現"
    st2, deep2 = _load(PH, S, monkeypatch, _holdings(), _prices(price=_BAD[bad]))
    out2 = _built(PH, st2, deep2)
    _no_nonfinite("".join(_blob(PH, _b) for _b in out2.values()))
    assert out2["build_take_profit_card"][0].note.why == f"2330：{_sentence('現價')}"


def test_hold_multiple_items_are_listed_with_the_existing_enumeration(monkeypatch, offline):
    """同一卡多個項目異常：沿用「代號：句子」逐項接起來（⛔ 不另寫句子）。"""
    hs = [_h("2330", "stock", lots=float("nan"), avg=float("-inf")),
          _h("2317", "stock", lots=2.0, avg=100.0)]
    st, deep = _load(PH, S, monkeypatch, hs, {"2330": float("inf"), "2317": 118.0})
    facts = dict(PH.build_action_card(st)[1])
    assert facts["未實現損益／總市值"] == ("2330：" + _sentence("張數") + "2330："
                                          + _sentence("均價") + "2330：" + _sentence("現價"))
    tp = PH.build_take_profit_card(st)[0]
    assert tp.note.why == "2330：" + _sentence("均價") + "2330：" + _sentence("現價")
    split = PH.build_allocation_split_card(st)[0]
    assert split.note.why == "2330：" + _sentence("張數") + "2330：" + _sentence("現價")
    cash = PH.build_dividend_cash_card(deep)[0]
    assert cash.note.why == "2330：" + _sentence("張數")


def test_hold_failed_row_and_invalid_row_both_listed(monkeypatch, offline):
    """整批抓取失敗的列與異常列同時存在：兩種原因各講各的（既有那句在前）。"""
    hs = _holdings(lots=float("inf")) + [_h("9999", "etf", lots=1.0, avg=10.0)]

    def _mf(tk, kind):
        if tk == "9999":
            raise RuntimeError("boom")
        return _metrics_fn(_prices())(tk, kind)
    monkeypatch.setattr("src.services.dividend_station_service.get_station_rows",
                        lambda h: (S.build_station_rows(h, vix=15.0, metrics_fn=_mf), 15.0))
    st = PH.load_station(PH.HoldingsReadout(requested=True, submitted=True, bound=True,
                                            holdings=tuple(hs)))
    why = PH.build_allocation_split_card(st)[0].note.why
    assert why.startswith("9999：") and why.endswith("2330：" + _sentence("張數"))


# ══════════════════════════════════════════════════════════════════
# B-2. 燈牆 ＋ ① 該做什麼：折溢價／配息率／近一年總報酬異常
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
def test_l2_health_d_invalid_premium_is_unjudged(bad):
    f = DSL2.health_d(_BAD_STR[bad])
    assert f.level == "⚪" and f.msg == _sentence("折溢價") and f.miss_reason == ""


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
@pytest.mark.parametrize("which", ["yield", "ret", "both"])
def test_l2_health_a_invalid_input_is_unjudged(which, bad):
    v = _BAD_STR[bad]
    ret, yld = {"yield": (2.0, v), "ret": (v, 5.0), "both": (v, v)}[which]
    f = DSL2.health_a(ret, yld)
    want = {"yield": _sentence("配息率"), "ret": _sentence("近一年總報酬"),
            "both": _sentence("近一年總報酬") + _sentence("配息率")}[which]
    assert f.level == "⚪" and f.msg == want and f.miss_reason == ""


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
@pytest.mark.parametrize("key,item", [("premium_pct", "折溢價"), ("annual_yield_pct", "配息率")])
def test_lightwall_and_action_do_not_conclude(key, item, bad, monkeypatch, offline):
    hs = [_h("0056", "etf", lots=1.0, avg=25.0)]
    # 配息率異常時把近一年報酬壓低 —— 修前 inf 會在這組判成「吃本金」紅燈。
    over = {key: _BAD[bad], **({"total_return_1y_pct": 2.0} if key == "annual_yield_pct" else {})}
    st, _deep = _load(PH, S, monkeypatch, hs, {"0056": 30.0}, etf_over=over)
    row = st.rows[0]
    _detail_key = {"premium_pct": "健檢D", "annual_yield_pct": "健檢A"}[key]
    assert row["_detail"][_detail_key] == _sentence(item)
    cells = {c.key: c for c in row["_lights"]}
    _cell = cells[{"premium_pct": SS.KEY_HEALTH_D, "annual_yield_pct": SS.KEY_HEALTH_A}[key]]
    assert _cell.level == "⚪" and _cell.state == SS.STATE_MISSING
    assert st.cut_n == 0, "異常燈不得計入汰弱"
    assert st.judged == st.total_lights - 1 and st.tally[SS.STATE_MISSING] == 1
    card, _f, sig = PH.build_action_card(st)
    assert "巡航" not in card.value and sig == "", "異常燈不得打開巡航／不得說有動作"
    assert "汰弱" not in card.value
    for _b in (PH.build_action_card(st), PH.build_lightwall_card(st),
               PH.build_confidence_card(st), PH.build_todo_card(st)):
        _no_nonfinite(_blob(PH, _b))
    assert "nan" not in repr(row["_detail"]).lower() and "inf" not in repr(row["_detail"]).lower()


# ══════════════════════════════════════════════════════════════════
# B-3. 查一檔頁估值（357）
# ══════════════════════════════════════════════════════════════════
def _valuation(avg, yearly=None, monkeypatch=None, P=PI):
    monkeypatch.setattr(
        "src.data.stock.app_stock_fetchers.fetch_dividend_data",
        lambda sid, failed=None: (avg, yearly if yearly is not None
                                  else [{"year": 2020 + i, "cash": 5.0} for i in range(5)],
                                  "FinMind"))
    v = P.KindVerdict(requested=True, code="2330", is_stock=True)
    s = P.StockReadout(requested=True, price=100.0)
    return P.build_valuation_card(P.load_valuation(v, s))


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
def test_valuation_invalid_average_stops(bad, monkeypatch):
    card, facts, sig = _valuation(_BAD_STR[bad], monkeypatch=monkeypatch)
    assert card.state == UI_FAILED and sig == "" and card.value == ""
    assert card.note.why == _sentence("配息")
    blob = repr(card) + repr(facts) + PI.v2_card_html(card, facts, sig)
    _no_nonfinite(blob)
    for _w in ("減碼", "首選", "甜甜價", "合理", "昂貴", "便宜"):
        assert _w not in sig + repr(facts), _w
    assert "上游說明" not in dict(facts), "異常時不呼叫 L2，不帶 L2 的結論句"


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
def test_valuation_invalid_yearly_cash_stops(bad, monkeypatch):
    yearly = [{"year": 2020 + i, "cash": (_BAD_STR[bad] if i == 2 else 5.0)} for i in range(5)]
    card, facts, sig = _valuation(5.0, yearly, monkeypatch=monkeypatch)
    assert card.state == UI_FAILED and card.note.why == _sentence("配息") and sig == ""
    _no_nonfinite(repr(card) + repr(facts) + PI.v2_card_html(card, facts, sig))


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
def test_l3_dividends_invalid_never_carries_a_number(bad, monkeypatch):
    monkeypatch.setattr("src.data.stock.app_stock_fetchers.fetch_dividend_data",
                        lambda sid, failed=None: (_BAD_STR[bad], [{"year": 2024, "cash": 1.0}],
                                                  "FinMind"))
    d = V.get_stock_dividends("2330", strict=True)
    assert d.invalid is True and d.avg_div_twd is None and d.paying_years is None
    assert d.has_record is False and d.source == "FinMind"


# ══════════════════════════════════════════════════════════════════
# B-4. 壓力測試：Beta 異常（⛔ 不補 1.0）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
def test_l2_stress_invalid_beta_is_flagged_not_imputed(bad, monkeypatch):
    monkeypatch.setattr("src.compute.etf.etf_calc.fetch_etf_info",
                        lambda t: {"beta": _BAD_STR[bad] if t == "A" else 1.0})
    r = EC.calc_portfolio_stress_test([{"ticker": "A", "actual_pct": 50},
                                       {"ticker": "B", "actual_pct": 50}], 1_000_000)
    assert r["beta_invalid_tickers"] == ["A"]
    assert r["beta_imputed_tickers"] == [] and r["beta_imputed_count"] == 0
    assert not math.isfinite(r["total_loss"]), "異常那一檔不得以 1.0 估算後照算"


@pytest.mark.parametrize("raw", [None, 0, 0.0], ids=repr)
def test_l2_stress_missing_beta_still_imputes_one(raw, monkeypatch):
    """查無 Beta（None／0）→ 1.0 估算的既有行為不變（裁示只禁「異常值」補 1.0）。"""
    monkeypatch.setattr("src.compute.etf.etf_calc.fetch_etf_info", lambda t: {"beta": raw})
    r = EC.calc_portfolio_stress_test([{"ticker": "A", "actual_pct": 100}], 1_000_000)
    assert r["beta_imputed_tickers"] == ["A"] and abs(r["total_loss"] + 200_000) < 1e-6
    assert "beta_invalid_tickers" not in r


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
def test_stress_card_invalid_beta_stops(bad, monkeypatch, offline):
    offline["value"] = _BAD_STR[bad]
    st, deep = _load(PH, S, monkeypatch, _holdings(), _prices())
    res = deep.stress
    assert res.computed is False and res.reason == _sentence("Beta")
    assert set(res.beta_invalid) == {"2330.TW", "2317.TW", "0050.TW"}
    assert res.loss_twd == 0.0 and res.loss_pct == 0.0 and res.warn is False
    card, facts, sig = PH.build_stress_card(deep)
    assert card.state == UI_FAILED and sig == "" and card.value == ""
    assert card.note.why.endswith("：" + _sentence("Beta"))
    assert not any("Beta 是估的" in _k for _k, _ in facts), "異常不是估算"
    _no_nonfinite(_blob(PH, (card, facts, sig)))


# ══════════════════════════════════════════════════════════════════
# C. 正常路徑與修前逐值相同（修前＝git `18b51ea0`）
# ══════════════════════════════════════════════════════════════════
_FINITE_VALUES = (None, 0.0, -3.0, 1.0, 2.5, 100.0, 118.0, 1e-6, 12345.678, "", "7.5")


def _normal_cases():
    """確定性窮舉：2330 的張數／均價／現價各取有限值（含 0、負數、None、數字字串）。"""
    rng = np.random.default_rng(49)
    for _ in range(40):
        lots, avg, px = (rng.choice(_FINITE_VALUES, 3)).tolist()
        yield lots, avg, px


@pytest.mark.parametrize("lots,avg,px", list(_normal_cases()), ids=repr)
def test_normal_rows_identical_to_pre(lots, avg, px):
    pre_s = _pre("src/services/dividend_station_service.py")
    hs = _holdings(lots=lots, avg=avg)
    pr = _prices(price=px)
    a, b = _rows(S, hs, pr), _rows(pre_s, hs, pr)
    assert _same(a, b)
    assert S.compute_portfolio_totals(a) == pre_s.compute_portfolio_totals(b)
    assert S.compute_allocation_split(a) == pre_s.compute_allocation_split(b)
    assert _same(S.build_station_digest(a, 15.0), pre_s.build_station_digest(b, 15.0))


@pytest.mark.parametrize("args", [(None, None), (None, 5.0), (12.0, None), (12.0, 5.0),
                                  (2.0, 5.0), (-30.0, 0.0), (0.0, 0.0), (5.0, 5.0)], ids=repr)
def test_normal_health_a_identical_to_pre(args):
    pre = _pre("src/compute/etf/dividend_station.py")
    assert dataclasses.asdict(DSL2.health_a(*args)) == dataclasses.asdict(pre.health_a(*args))


@pytest.mark.parametrize("p", [None, 0.0, 1.5, 1.6, -2.0, 30.0], ids=repr)
def test_normal_health_d_identical_to_pre(p):
    pre = _pre("src/compute/etf/dividend_station.py")
    assert dataclasses.asdict(DSL2.health_d(p)) == dataclasses.asdict(pre.health_d(p))


@pytest.mark.parametrize("beta", [None, 0, 0.0, 0.5, 1.0, 1.37, "1.2", -0.4, "  "], ids=repr)
def test_normal_stress_l2_identical_to_pre(beta, monkeypatch):
    pre = _pre("src/compute/etf/etf_calc.py")
    for _m in (EC, pre):
        monkeypatch.setattr(_m, "fetch_etf_info", lambda t: {"beta": beta})
    rows = [{"ticker": "A", "actual_pct": 60.0}, {"ticker": "B", "actual_pct": 40.0}]
    assert EC.calc_portfolio_stress_test(rows, 1_234_567) == \
        pre.calc_portfolio_stress_test(rows, 1_234_567)


@pytest.mark.parametrize("v", [None, 0.0, -1.0, 1e-9, 3.0, 5e300, True], ids=repr)
def test_normal_pos_identical_to_pre(v):
    assert D._pos(v) == _pre("src/services/portfolio_deep_service.py")._pos(v)


@pytest.mark.parametrize("avg,yearly", [
    (5.0, [{"year": 2020 + i, "cash": 5.0} for i in range(5)]),
    (2.5, [{"year": 2024, "cash": 0.0}, {"year": 2023, "cash": 5.0}]),
    (0.0, []), (None, None), (3.0, [{"year": 2024, "cash": None}]),
], ids=["full", "partial", "sentinel", "none", "cash_none"])
def test_normal_dividends_identical_to_pre(avg, yearly, monkeypatch):
    pre = _pre("src/services/valuation_service.py")
    monkeypatch.setattr("src.data.stock.app_stock_fetchers.fetch_dividend_data",
                        lambda sid, failed=None: (avg, yearly, "FinMind"))
    a, b = V.get_stock_dividends("2330"), pre.get_stock_dividends("2330")
    assert dataclasses.asdict(a) == {**dataclasses.asdict(b), "invalid": False}
    assert repr(a) == repr(b).replace(pre.__name__, V.__name__)


@pytest.mark.parametrize("avg", [5.0, 7.5, 3.0, 0.0, None], ids=repr)
def test_normal_valuation_card_identical_to_pre(avg, monkeypatch):
    pre = _pre("src/ui/views/page_inspect.py")
    a = _valuation(avg, monkeypatch=monkeypatch, P=PI)
    b = _valuation(avg, monkeypatch=monkeypatch, P=pre)
    assert a == b
    assert PI.v2_card_html(*a) == pre.v2_card_html(*b)


@pytest.mark.parametrize("lots,avg,px", list(_normal_cases())[:20], ids=repr)
@pytest.mark.parametrize("beta", [1.1, None], ids=["beta", "no_beta"])
def test_normal_hold_page_identical_to_pre(lots, avg, px, beta, monkeypatch, offline):
    """持股頁 ① ③ ⑤ ⑥ 全部卡（狀態、數字、訊號、v2 HTML）與修前逐字相同。"""
    pre = _pre("src/ui/views/page_hold.py")
    offline["value"] = beta
    hs = _holdings(lots=lots, avg=avg)
    st_a, d_a = _load(PH, S, monkeypatch, hs, _prices(price=px))
    st_b, d_b = _load(pre, S, monkeypatch, hs, _prices(price=px))
    out_a, out_b = _built(PH, st_a, d_a), _built(pre, st_b, d_b)
    for _n in out_a:
        assert out_a[_n] == out_b[_n], _n
        assert PH.v2_card_html(*out_a[_n]) == pre.v2_card_html(*out_b[_n]), _n


# ══════════════════════════════════════════════════════════════════
# D. revert-pair 突變：拔掉本批防呆 → 對應斷言轉紅
# ══════════════════════════════════════════════════════════════════
#: (修後逐字, 修前逐字)
Z49_L3_ROWS_PAIR = ("                             if SS.is_invalid_number(_v))",
                    "                             if False)")
Z49_L3_TOTALS_PAIR = (
    "        if r.get(SS.KEY_INVALID_INPUTS):\n"
    "            # 批 Z49：張數／均價／現價任一是異常值 → 整個總額不算（⛔ 不剔除那一檔後照算）。\n"
    "            return None\n", "")
Z49_L3_SPLIT_PAIR = ("        if {SS.ITEM_LOTS, SS.ITEM_PRICE} & set(r.get(SS.KEY_INVALID_INPUTS) or ()):",
                     "        if False:")
Z49_L2_D_PAIR = ("    if SS.is_invalid_number(premium_pct):", "    if False:")
Z49_L2_A_PAIR = ("    if _bad:\n        return Flag(\"⚪\", \"\".join(SS.invalid_data_text(_i) for _i in _bad))",
                 "    if False:\n        return Flag(\"⚪\", \"\".join(SS.invalid_data_text(_i) for _i in _bad))")
Z49_L2_BETA_PAIR = ("        if _beta_raw and is_invalid_number(_beta_raw):", "        if False:")
Z49_L3_BETA_PAIR = ("    if _bad_beta:\n", "    if False:\n")
Z49_L3_POS_PAIR = ("    if not math.isfinite(_v) or _v <= 0:     # NaN／±inf 或非正",
                   "    if _v != _v or _v <= 0:     # NaN 或非正")
Z49_L3_DIV_PAIR = ("    if (is_invalid_number(_avg)\n"
                   "            or any(is_invalid_number(_r.get(\"cash\")) for _r in _rows)):",
                   "    if False:")
Z49_UI_VAL_PAIR = ("    if getattr(_div, \"invalid\", False):", "    if False:")
Z49_UI_TOTALS_PAIR = ("    if _bad:\n        return [(\"未實現損益／總市值\", _invalid_why(_bad))]",
                      "    if False:\n        return [(\"未實現損益／總市值\", _invalid_why(_bad))]")
Z49_UI_SPLIT_PAIR = (
    "    _uncounted += _invalid_codes(_invalid_groups(station.rows, (ITEM_LOTS, ITEM_PRICE)))\n", "")
Z49_UI_TP_PAIR = ("    _unjudged = _fetch_failed + _no_price + _invalid_codes(_tp_invalid)",
                  "    _unjudged = _fetch_failed + _no_price")
Z49_UI_STRESS_PAIR = ("    _stress_skipped += _invalid_codes(_stress_bad)\n", "")
Z49_UI_VAR_PAIR = ("    _var_skipped += _invalid_codes(deep.invalid_rows)\n", "")
Z49_UI_CASH_PAIR = ("    _cash_skipped += _invalid_codes(_cash_bad)\n", "")

_SVC = "src/services/dividend_station_service.py"
_HOLD = "src/ui/views/page_hold.py"

#: 每個檔「拔掉本批全部防呆」＝修前行為（C 類用）。
_PRE_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _SVC: (Z49_L3_ROWS_PAIR, Z49_L3_TOTALS_PAIR, Z49_L3_SPLIT_PAIR),
    "src/compute/etf/dividend_station.py": (Z49_L2_D_PAIR, Z49_L2_A_PAIR),
    "src/compute/etf/etf_calc.py": (Z49_L2_BETA_PAIR,),
    "src/services/portfolio_deep_service.py": (Z49_L3_BETA_PAIR, Z49_L3_POS_PAIR),
    "src/services/valuation_service.py": (Z49_L3_DIV_PAIR,),
    "src/ui/views/page_inspect.py": (Z49_UI_VAL_PAIR,),
    _HOLD: (Z49_UI_TOTALS_PAIR, Z49_UI_SPLIT_PAIR, Z49_UI_TP_PAIR, Z49_UI_STRESS_PAIR,
            Z49_UI_VAR_PAIR, Z49_UI_CASH_PAIR),
}


def test_mut_l3_row_detection(monkeypatch, offline):
    m = _variant(_SVC, (Z49_L3_ROWS_PAIR,), "_z49_no_detect_svc")
    rows = _rows(m, _holdings(), _prices(price=float("inf")))
    assert rows[0]["損益%"] == float("inf"), "拔掉偵測 → inf 回到損益%（＝修前）"
    assert {"代號": "2330", "損益%": float("inf")} in m.flag_take_profit(rows)
    st, _d = _load(PH, m, monkeypatch, _holdings(), _prices(price=float("inf")))
    card, facts, sig = PH.build_take_profit_card(st)
    assert sig == "可停利" and "inf%" in repr(facts), "修前的錯誤結論重現"


def test_mut_l3_totals_and_split_guards():
    rows_lots = _rows(S, _holdings(lots=float("inf")), _prices())
    rows_avg = _rows(S, _holdings(avg=float("nan")), _prices())
    m_t = _variant(_SVC, (Z49_L3_TOTALS_PAIR,), "_z49_no_totals_svc")
    m_s = _variant(_SVC, (Z49_L3_SPLIT_PAIR,), "_z49_no_split_svc")
    assert S.compute_portfolio_totals(rows_avg) is None
    assert m_t.compute_portfolio_totals(rows_avg)["partial"] is True, "拔掉 → 剔除那一檔後照算"
    assert S.compute_allocation_split(rows_lots) is None
    assert m_s.compute_allocation_split(rows_lots)["partial"] is True


@pytest.mark.parametrize("pair,call,bad_level", [
    (Z49_L2_D_PAIR, lambda m: m.health_d(float("nan")), "🟢"),
    (Z49_L2_A_PAIR, lambda m: m.health_a(2.0, float("inf")), "🔴"),
], ids=["health_d", "health_a"])
def test_mut_l2_health(pair, call, bad_level):
    m = _variant("src/compute/etf/dividend_station.py", (pair,), f"_z49_l2_{bad_level}")
    assert call(m).level == bad_level, "拔掉 → 修前的錯誤燈號重現"
    assert call(DSL2).level == "⚪"


def test_mut_l2_beta(monkeypatch):
    m = _variant("src/compute/etf/etf_calc.py", (Z49_L2_BETA_PAIR,), "_z49_l2_beta")
    monkeypatch.setattr(m, "fetch_etf_info", lambda t: {"beta": "abc"})
    r = m.calc_portfolio_stress_test([{"ticker": "A", "actual_pct": 100}], 1_000_000)
    assert r["beta_imputed_tickers"] == ["A"] and "beta_invalid_tickers" not in r, \
        "拔掉 → 轉不成數字的 Beta 又被補 1.0（＝修前）"


def test_mut_l3_beta_abort(monkeypatch, offline):
    offline["value"] = float("inf")
    m = _variant("src/services/portfolio_deep_service.py", (Z49_L3_BETA_PAIR,), "_z49_no_beta_abort")
    rows = _rows(S, _holdings(), _prices())
    res = m.get_portfolio_stress(rows, strict=True)
    assert res.computed is True and not math.isfinite(res.loss_twd), "拔掉 → 拿 inf 照算（＝修前）"
    assert D.get_portfolio_stress(rows, strict=True).computed is False


def test_mut_l3_pos():
    m = _variant("src/services/portfolio_deep_service.py", (Z49_L3_POS_PAIR,), "_z49_no_pos")
    assert m._pos(float("inf")) == float("inf") and D._pos(float("inf")) is None


def test_mut_l3_dividends(monkeypatch):
    m = _variant("src/services/valuation_service.py", (Z49_L3_DIV_PAIR,), "_z49_no_div")
    monkeypatch.setattr("src.data.stock.app_stock_fetchers.fetch_dividend_data",
                        lambda sid, failed=None: (float("inf"), [{"year": 2024, "cash": 1.0}],
                                                  "FinMind"))
    assert m.get_stock_dividends("2330").avg_div_twd == float("inf"), "拔掉 → inf 照帶（＝修前）"
    assert V.get_stock_dividends("2330").avg_div_twd is None


def test_mut_ui_valuation(monkeypatch):
    m = _variant("src/ui/views/page_inspect.py", (Z49_UI_VAL_PAIR,), "_z49_no_val_ui")
    card = _valuation(float("nan"), monkeypatch=monkeypatch, P=m)[0]
    assert card.state == UI_EMPTY and _sentence("配息") not in repr(card), \
        "拔掉 → L2 把它講成「無配息記錄、法則不適用」的灰卡（原因講錯）"
    assert _valuation(float("nan"), monkeypatch=monkeypatch)[0].state == UI_FAILED


def test_mut_ui_totals(monkeypatch, offline):
    m = _variant(_HOLD, (Z49_UI_TOTALS_PAIR,), "_z49_no_totals_ui")
    st, _d = _load(m, S, monkeypatch, _holdings(avg=float("inf")), _prices())
    facts = dict(m.build_action_card(st)[1])
    assert _sentence("均價") not in repr(facts) and "持股缺張數／均價／現價" in repr(facts), \
        "拔掉 → 把異常講成「缺」"


def test_mut_ui_split(monkeypatch, offline):
    m = _variant(_HOLD, (Z49_UI_SPLIT_PAIR,), "_z49_no_split_ui")
    hs = _holdings(lots=float("nan"))
    st, _d = _load(m, S, monkeypatch, hs, _prices())
    card = m.build_allocation_split_card(st)[0]
    assert card.state == UI_EMPTY and "有效的結果" in card.note.why, \
        "拔掉 → 異常被講成「沒有市值、這是有效的結果」的灰卡"
    st2, _d2 = _load(PH, S, monkeypatch, hs, _prices())
    assert PH.build_allocation_split_card(st2)[0].state == UI_FAILED


def test_mut_ui_take_profit(monkeypatch, offline):
    m = _variant(_HOLD, (Z49_UI_TP_PAIR,), "_z49_no_tp_ui")
    hs = _holdings(avg=float("inf"))
    st, _d = _load(m, S, monkeypatch, hs, _prices())
    card, _f, sig = m.build_take_profit_card(st)
    assert card.state == UI_LIVE and sig == "可停利", \
        "拔掉 → 2330 沒被判過，卡片卻照樣下「可停利」的整卡結論"
    st2, _d2 = _load(PH, S, monkeypatch, hs, _prices())
    assert PH.build_take_profit_card(st2)[0].state == UI_FAILED


@pytest.mark.parametrize("pair,builder,field", [
    (Z49_UI_STRESS_PAIR, "build_stress_card", "lots"),
    (Z49_UI_VAR_PAIR, "build_var_card", "avg"),
    (Z49_UI_CASH_PAIR, "build_dividend_cash_card", "lots"),
], ids=["stress", "var", "cash"])
def test_mut_ui_deep(pair, builder, field, monkeypatch, offline):
    m = _variant(_HOLD, (pair,), f"_z49_no_{builder}")
    hs = _holdings(**{field: float("inf")})
    _st, deep = _load(m, S, monkeypatch, hs, _prices())
    assert getattr(m, builder)(deep)[0].state != UI_FAILED, \
        "拔掉 → 剔除異常那檔後照給數字"
    _st2, deep2 = _load(PH, S, monkeypatch, hs, _prices())
    assert getattr(PH, builder)(deep2)[0].state == UI_FAILED
