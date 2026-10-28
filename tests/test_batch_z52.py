"""批 Z52 —— 新 UI 持股頁：VIX 卡與 ⑦ AI 輸入的資料異常（沿用批 Z49 客戶裁示 B）。

客戶裁示（2026-10-13，逐字）：統一採用「{項目}資料異常，無法計算，不下結論。」
  · NaN／±inf／其他無效數值一律視為異常；不顯示 nan／inf；不使用替代值繼續計算；
  · 該數值會影響結論時，該卡停止計算並不下結論；正常資料路徑不得改變；
  · 不擴大修改資料層、公式、門檻、權重、版面或其他文案。

兩項（修前實測重現）：
  1. Z51-n1：`build_vix_card(VixReadout(vix=±inf／nan))` → 🟢「運作中」、值印成 inf／nan。
     另：`load_vix()` 遇 L3 回 inf／轉不成數字時，修前併成「抓不到」（叫人重跑），本批改為資料異常。
     呼叫鏈：`page_hold.render_page_hold` → `load_vix` → L3 `fetch_vix(strict=True)` → `build_vix_card`。
  2. Z51-n2：Z49 的持股輸入異常（`SS.KEY_INVALID_INPUTS`：張數／均價／現價）不進 ⑦ 的
     「資料異常未判」事實列 → prompt 仍帶「續抱、定期定額即可」引導（配置那一行默默消失、
     衛星停利判不出來，AI 卻被引導說續抱）。
     呼叫鏈：`load_station` → L3 `get_station_rows` → `build_station_rows`（標 `_invalid_inputs`）
     → `build_station_digest`（`invalid`）→ `load_ai_summary` → `build_ai_summary` → `build_summary_prompt`。

本檔驗：
  A. VIX 卡：NaN／±inf（直接構造與 `load_vix` 兩條路；`load_vix` 另含字串）→ 不下結論、不印 nan／inf、
     出現客戶句；VIX=None／正常值與修前逐值相同；revert-pair 突變。
  B. ⑦：張數／均價／現價 NaN／±inf／字串 → 事實列逐字、不送續抱引導、prompt 其餘逐字同修前；
     沒有異常（含一般缺資料）→ digest 鍵與 prompt 逐字同修前；revert-pair 突變。
  修前＝現行原始碼套上本批 revert pair（測試本身不呼叫 git，見 `tests/test_zz_test_portability.py`）。
"""
from __future__ import annotations

import functools
import pathlib
import re
import sys
import types

import numpy as np
import pandas as pd
import pytest

import src.services.dividend_station_service as S
import src.ui.views.page_hold as PH
from shared import station_specs as SS
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_IDLE, UI_LIVE

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PAGE = "src/ui/views/page_hold.py"
_SVC = "src/services/dividend_station_service.py"

_BAD = {"nan": float("nan"), "pos_inf": float("inf"), "neg_inf": float("-inf")}
_BAD_STR = {**_BAD, "np_nan": np.nan, "text": "abc"}
_NONFINITE_RE = re.compile(r"(?i)(?<![a-z])(nan|inf|infinity)(?![a-z])")
_KEEP = "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。"
_FACT_HEAD = "- 資料異常未判："


def _sentence(item: str) -> str:
    return f"{item}資料異常，無法計算，不下結論。"


def _no_nonfinite(text: str) -> None:
    _hit = _NONFINITE_RE.search(text)
    assert _hit is None, f"出現 {_hit.group(0)!r}：…{text[max(0, _hit.start() - 40):_hit.end() + 40]}…"


# ══════════════════════════════════════════════════════════════════
# revert-pair（修後逐字, 修前逐字）與變體載入
# ══════════════════════════════════════════════════════════════════
#: `build_vix_card` 的異常判定（只拔這一環 → 直接構造的 inf／nan 畫成 🟢 運作中、印出 inf／nan）。
Z52_CARD_PAIR = (
    "    _invalid = vix.requested and (vix.invalid\n",
    "    _invalid = False and (vix.invalid\n")
#: `load_vix` 的異常分流（只拔這一環 → L3 回 inf／字串時併成「抓不到」，叫人重跑）。
Z52_LOAD_PAIR = ("    if is_invalid_number(_v):\n", "    if False:\n")
#: L3 `build_station_digest`：持有列的持股輸入異常進 `invalid`（只拔這一環 → 修前：⑦ 看不到、續抱引導還在）。
Z52_DIGEST_PAIR = (
    '        return tuple(r.get(SS.KEY_INVALID_INPUTS) or ()) if r.get("held") else ()\n',
    "        return ()\n")
_PRE_PAGE_PAIRS = (Z52_CARD_PAIR, Z52_LOAD_PAIR)
_PRE_SVC_PAIRS = (Z52_DIGEST_PAIR,)


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


def _page_pre() -> types.ModuleType:
    return _variant(_PAGE, _PRE_PAGE_PAIRS, "_z52_pre_page_hold")


def _svc_pre() -> types.ModuleType:
    return _variant(_SVC, _PRE_SVC_PAIRS, "_z52_pre_svc")


def test_revert_pairs_are_unique_anchors():
    for rel, pairs in ((_PAGE, _PRE_PAGE_PAIRS), (_SVC, _PRE_SVC_PAIRS)):
        code = (_ROOT / rel).read_text(encoding="utf-8")
        for new, _old in pairs:
            assert code.count(new) == 1, new


def _blob(P, built) -> str:
    card, facts, sig = built
    return repr(card) + repr(tuple(facts)) + sig + P.v2_card_html(card, facts, sig)


# ══════════════════════════════════════════════════════════════════
# A. VIX 卡（Z51-n1）
# ══════════════════════════════════════════════════════════════════
def _assert_vix_unconcluded(built) -> None:
    card, facts, sig = built
    _b = _blob(PH, built)
    _no_nonfinite(_b)
    assert card.state == UI_FAILED and card.state != UI_LIVE
    assert "運作中" not in _b and card.value in (None, "")
    assert sig == ""
    assert card.note.now == PH.VIX_FAILED_NOW
    assert card.note.why == _sentence("VIX")
    # v2 卡面：客戶句整句上卡面（摘錄對得上，不是 KeyError 紅卡）。
    assert _sentence("VIX") in PH.v2_card_html(card, facts, sig)
    # 不叫人重跑（值有給、是壞的），也不說「沒抓到」。
    assert PH.VIX_RETRY_WHERE not in _b and "沒抓到" not in _b
    # 燈號判讀字樣（巡航／燈一～三）只在門檻說明那一列出現，不作為卡值或結論。
    assert all("巡航" not in str(_x) for _x in (card.value, sig, card.note.now, card.note.why))


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_vix_card_direct_invalid_does_not_conclude(bad):
    _assert_vix_unconcluded(PH.build_vix_card(PH.VixReadout(requested=True, vix=_BAD[bad])))


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_vix_card_invalid_wins_over_fetch_failed_flag(bad):
    _assert_vix_unconcluded(PH.build_vix_card(
        PH.VixReadout(requested=True, vix=_BAD[bad], fetch_failed=True)))


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
def test_load_vix_invalid_marks_and_card_stops(bad, monkeypatch):
    monkeypatch.setattr("src.services.dividend_station_service.fetch_vix",
                        lambda strict=False: _BAD_STR[bad])
    vx = PH.load_vix(PH.HoldRequest(submitted=True))
    assert (vx.requested, vx.vix, vx.error, vx.fetch_failed, vx.invalid) == (
        True, None, "", False, True)
    _assert_vix_unconcluded(PH.build_vix_card(vx))


def _card_or_raise(P, **kw) -> str:
    """卡片輸出，或建卡時拋的例外（`classify_ui_state` 對「沒送出過卻帶值」fail loud）。"""
    try:
        return _blob(P, P.build_vix_card(P.VixReadout(**kw)))
    except Exception as _e:  # noqa: BLE001 — 比對修前／修後是否拋同一個例外
        return f"RAISE {type(_e).__name__}: {_e}"


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_vix_card_not_requested_with_invalid_value_unchanged(bad):
    """沒送出過卻帶著值 ＝ 殘值：照舊由 `classify_ui_state` fail loud（與修前同一個例外）。"""
    now = _card_or_raise(PH, requested=False, vix=_BAD[bad])
    assert now.startswith("RAISE ValueError")
    assert now == _card_or_raise(_page_pre(), requested=False, vix=_BAD[bad])


def test_vix_card_not_requested_invalid_flag_is_idle():
    built = PH.build_vix_card(PH.VixReadout(requested=False, invalid=True))
    assert built[0].state == UI_IDLE
    assert _blob(PH, built) == _blob(_page_pre(), _page_pre().build_vix_card(
        _page_pre().VixReadout(requested=False)))


_VIX_NORMAL = [None, 0.0, 9.5, 15.0, 19.99, 20.0, 25.0, 30.0, 45.12, 99.95]


@pytest.mark.parametrize("fetch_failed", [False, True])
@pytest.mark.parametrize("error", ["", "RuntimeError('x')"])
@pytest.mark.parametrize("requested", [True, False])
@pytest.mark.parametrize("v", _VIX_NORMAL, ids=repr)
def test_vix_card_normal_and_missing_identical_to_pre(v, requested, error, fetch_failed):
    kw = dict(requested=requested, vix=v, error=error, fetch_failed=fetch_failed)
    assert _card_or_raise(PH, **kw) == _card_or_raise(_page_pre(), **kw)


def test_vix_none_card_text_verbatim():
    card, _f, _s = PH.build_vix_card(PH.VixReadout(requested=True))
    assert card.state == UI_EMPTY and card.note.now == PH.VIX_EMPTY_NOW
    card, _f, _s = PH.build_vix_card(PH.VixReadout(requested=True, fetch_failed=True))
    assert card.state == UI_FAILED and "沒抓到" in card.note.why


@pytest.mark.parametrize("raw", [None, "", 0.0, 15.0, 22.5, "18.25", True], ids=repr)
def test_load_vix_normal_and_missing_identical_to_pre(raw, monkeypatch):
    P0 = _page_pre()
    monkeypatch.setattr("src.services.dividend_station_service.fetch_vix",
                        lambda strict=False: raw)
    now = PH.load_vix(PH.HoldRequest(submitted=True))
    pre = P0.load_vix(P0.HoldRequest(submitted=True))
    assert now.invalid is False
    assert (now.requested, now.vix, now.error, now.fetch_failed) == (
        pre.requested, pre.vix, pre.error, pre.fetch_failed)
    assert _blob(PH, PH.build_vix_card(now)) == _blob(P0, P0.build_vix_card(pre))


def test_load_vix_exception_identical_to_pre(monkeypatch):
    P0 = _page_pre()

    def boom(strict=False):
        raise RuntimeError("boom")
    monkeypatch.setattr("src.services.dividend_station_service.fetch_vix", boom)
    now, pre = PH.load_vix(PH.HoldRequest(submitted=True)), P0.load_vix(P0.HoldRequest(submitted=True))
    assert (now.vix, now.error, now.fetch_failed, now.invalid) == (pre.vix, pre.error,
                                                                   pre.fetch_failed, False)
    assert _blob(PH, PH.build_vix_card(now)) == _blob(P0, P0.build_vix_card(pre))


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_mut_card_reopens_live_with_nonfinite(bad):
    """只拔卡片那一環 → 修前重現：🟢 運作中、值印成 inf／nan。"""
    m = _variant(_PAGE, (Z52_CARD_PAIR,), "_z52_no_card")
    card, facts, sig = m.build_vix_card(m.VixReadout(requested=True, vix=_BAD[bad]))
    assert card.state == UI_LIVE and _NONFINITE_RE.search(str(card.value))
    _assert_vix_unconcluded(PH.build_vix_card(PH.VixReadout(requested=True, vix=_BAD[bad])))


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
def test_mut_load_reopens_fetch_failed_wording(bad, monkeypatch):
    """只拔 `load_vix` 那一環 → 修前重現：異常值被講成「沒抓到、稍後重跑」。"""
    m = _variant(_PAGE, (Z52_LOAD_PAIR,), "_z52_no_load")
    monkeypatch.setattr("src.services.dividend_station_service.fetch_vix",
                        lambda strict=False: _BAD_STR[bad])
    vx = m.load_vix(m.HoldRequest(submitted=True))
    assert vx.fetch_failed is True and vx.invalid is False
    card = m.build_vix_card(vx)[0]
    assert "沒抓到" in card.note.why and card.note.why != _sentence("VIX")


# ══════════════════════════════════════════════════════════════════
# B. ⑦ AI 輸入（Z51-n2）
# ══════════════════════════════════════════════════════════════════
_WK = pd.Series(np.linspace(20, 30, 120),
                index=pd.date_range("2023-01-06", periods=120, freq="W-FRI"))


def _etf_metrics(**over) -> dict:
    base = dict(weekly_close=_WK, premium_pct=0.3, sharpe=0.8, total_return_1y_pct=10.0,
                annual_yield_pct=5.0, inception_years=5.0, ann_return_3y_pct=8.0,
                cum_return_3y_pct=25.0, peer_ranks={3: .2, 6: .2, 12: .2}, current_price=30.0)
    base.update(over)
    return base


def _stock_metrics(price, grade=None) -> dict:
    # XV-H1-EXT（客戶 2026-10-28 裁示，取代 Z51/Z52 該部分語意）：`grade=None` ＝ 財報缺 ⇒ 個股汰換燈 ⚪
    # ＝「燈全判不出」⇒ 組合層不再帶續抱句；要測「資料完整仍帶續抱」時傳 `grade="A"`。
    return {"mj_grade": grade, "mj_score_pct": None, "mj_headline": "", "mj_fail_items": [],
            "kd_state": None, "current_price": price, "name": "", "trend_verdict": None}


def _h(tk, kind, lots=1.0, avg=100.0, held=True) -> dict:
    return {"ticker": tk, "name": tk, "asset_kind": kind, "lots": lots, "avg_price": avg,
            "held": held}


#: 衛星 2330（受測）、2317（個股）＋ 核心 0050（ETF，受測）＋ 觀察清單 00878（ETF）。
def _holdings(s_lots=1.0, s_avg=100.0, e_lots=3.0, e_avg=25.0, w_lots=None, w_avg=None):
    return [_h("2330", "stock", lots=s_lots, avg=s_avg),
            _h("2317", "stock", lots=2.0, avg=100.0),
            _h("0050", "etf", lots=e_lots, avg=e_avg),
            _h("00878", "etf", lots=w_lots, avg=w_avg, held=False)]


_ORIG_DIGEST = S.build_station_digest
_ORIG_PROMPT = S.build_summary_prompt


def _run(monkeypatch, *, holdings, prices=None, etf_over=None, svc_mod=None, vix=15.0,
         stock_grade=None):
    """走新 UI 真的 `load_station` → `load_ai_summary`（⑦）；只把 L3 抓取換成合成列。"""
    prices = {"2330": 120.0, "2317": 118.0, "0050": 30.0, "00878": 20.0, **(prices or {})}

    def mf(tk, kind):
        if kind == "etf":
            return _etf_metrics(**{"current_price": prices.get(tk),
                                   **((etf_over or {}) if tk == "0050" else {})})
        return _stock_metrics(prices.get(tk), grade=stock_grade)
    monkeypatch.setattr("src.services.dividend_station_service.get_station_rows",
                        lambda hs: (S.build_station_rows(hs, vix=vix, metrics_fn=mf), vix))
    _svc = svc_mod
    monkeypatch.setattr("src.services.dividend_station_service.build_station_digest",
                        _svc.build_station_digest if _svc is not None else _ORIG_DIGEST)
    monkeypatch.setattr("src.services.dividend_station_service.build_summary_prompt",
                        _svc.build_summary_prompt if _svc is not None else _ORIG_PROMPT)
    _cap: dict = {}

    def _gem(prompt, max_tokens=None, **k):
        _cap["prompt"] = prompt
        return "摘要OK"
    monkeypatch.setattr("src.services.app_ai_service.gemini_call", _gem)
    h = PH.HoldingsReadout(requested=True, submitted=True, bound=True, holdings=tuple(holdings))
    st = PH.load_station(h)
    ai = PH.load_ai_summary(True, st, PH.SwitchReadout(requested=False))
    return st, ai, _cap.get("prompt", "")


def _prompt_line(prompt: str, head: str) -> str:
    assert prompt, "⑦ 沒有被呼叫"
    _l = [ln for ln in prompt.splitlines() if ln.startswith(head)]
    assert len(_l) == 1, prompt
    return _l[0]


def _fact(*rows) -> str:
    return _FACT_HEAD + "、".join(
        f"{_c}（" + "　".join(f"{_l}：{_t}" for _l, _t in _items) + "）" for _c, _items in rows)


def _inp(*items) -> tuple:
    return tuple((_i, _sentence(_i)) for _i in items)


#: 情境：(holdings 參數, prices 覆寫, 期望事實列)
_CASES: dict = {}
for _b, _v in _BAD_STR.items():
    _CASES[f"stock_lots_{_b}"] = ({"s_lots": _v}, {}, (("2330", _inp("張數")),))
    _CASES[f"stock_avg_{_b}"] = ({"s_avg": _v}, {}, (("2330", _inp("均價")),))
    _CASES[f"stock_px_{_b}"] = ({}, {"2330": _v}, (("2330", _inp("現價")),))
    _CASES[f"etf_lots_{_b}"] = ({"e_lots": _v}, {}, (("0050", _inp("張數")),))
for _b, _v in _BAD.items():
    _CASES[f"stock_all3_{_b}"] = ({"s_lots": _v, "s_avg": _v}, {"2330": _v},
                                  (("2330", _inp("張數", "均價", "現價")),))
    _CASES[f"two_rows_{_b}"] = ({"s_avg": _v, "e_lots": _v}, {},
                                (("2330", _inp("均價")), ("0050", _inp("張數"))))


@pytest.mark.parametrize("case", list(_CASES))
def test_prompt_lists_held_input_invalid_and_drops_keep(case, monkeypatch):
    hk, px, want = _CASES[case]
    st, ai, prompt = _run(monkeypatch, holdings=_holdings(**hk), prices=px)
    assert "續抱、定期定額即可" not in prompt, "持股輸入資料異常時不得引導 AI 說續抱"
    assert _prompt_line(prompt, _FACT_HEAD) == _fact(*want)
    _no_nonfinite(prompt)
    assert st.digest["invalid"] == [{"代號": _c, "項目": _it} for _c, _it in want]
    # 新 UI ⑦ 卡（卡片、facts、v2 HTML）也不得出現 nan／inf。
    _no_nonfinite(_blob(PH, PH.build_ai_summary_card(ai, st)))
    # 除了拿掉那句指示、加上事實列，prompt 其餘逐字同修前。
    _st, _ai, pre = _run(monkeypatch, holdings=_holdings(**hk), prices=px, svc_mod=_svc_pre())
    # XV-H1-EXT（客戶 2026-10-28 裁示，取代 Z52 該部分語意）：本 fixture 個股無財報（燈全判不出）
    # ⇒ 修前（拔 Z52 digest 環）也不再帶續抱句，改帶資料不足指示；其餘逐字同修前。
    assert _KEEP not in pre and S._INSUFFICIENT_INSTRUCTION in pre and _FACT_HEAD not in pre
    _anchor = _prompt_line(pre, "- 抓取失敗未納入：") + "\n"
    assert prompt == pre.replace(_anchor, _anchor + _fact(*want) + "\n")


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_prompt_light_and_input_invalid_on_same_row_combined(bad, monkeypatch):
    """同一列燈（批 Z51）與持股輸入（本批）都異常 → 一列一個括號，燈的項目在前。"""
    st, _ai, prompt = _run(monkeypatch, holdings=_holdings(e_lots=_BAD[bad]),
                           etf_over={"premium_pct": _BAD[bad]})
    assert _prompt_line(prompt, _FACT_HEAD) == _fact(
        ("0050", (("健檢D", _sentence("折溢價")),) + _inp("張數")))
    assert "續抱、定期定額即可" not in prompt
    _no_nonfinite(prompt)


@pytest.mark.parametrize("bad", list(_BAD_STR), ids=list(_BAD_STR))
def test_prompt_watchlist_input_invalid_not_listed(bad, monkeypatch):
    """觀察清單列的持股輸入不進 allocation／take_profit → 不列、prompt 與修前逐字相同。"""
    st, _ai, prompt = _run(monkeypatch, holdings=_holdings(), prices={"00878": _BAD_STR[bad]})
    row = next(_r for _r in st.rows if _r["代號"] == "00878")
    assert SS.ITEM_PRICE in row[SS.KEY_INVALID_INPUTS]
    assert "invalid" not in st.digest
    _st, _ai2, pre = _run(monkeypatch, holdings=_holdings(), prices={"00878": _BAD_STR[bad]},
                          svc_mod=_svc_pre())
    # XV-H1-EXT（客戶 2026-10-28 裁示，取代 Z52 該部分語意）：個股無財報 ⇒ 不帶續抱句。
    assert prompt == pre and _KEEP not in prompt


_NORMAL = {
    "all_normal": ({}, {}),
    "lots_none": ({"s_lots": None}, {}),
    "avg_none": ({"s_avg": None}, {}),
    "px_none": ({}, {"2330": None}),
    "etf_avg_zero": ({"e_avg": 0.0}, {}),
    "lots_negative": ({"s_lots": -1.0}, {}),
    "take_profit_hit": ({"s_avg": 80.0}, {}),
    "watch_has_lots": ({"w_lots": 1.0, "w_avg": 18.0}, {}),
}


@pytest.mark.parametrize("vix", [None, 15.0, 35.0])
@pytest.mark.parametrize("case", list(_NORMAL))
@pytest.mark.parametrize("grade", [None, "A"])
def test_prompt_normal_and_missing_identical_to_pre(case, vix, grade, monkeypatch):
    """沒有異常（含一般缺資料）：digest 鍵與 prompt 逐字同修前。

    XV-H1-EXT（客戶 2026-10-28 裁示，取代 Z52「缺值仍帶續抱」的語意）：
    - 資料完整（個股有財報 `grade="A"`、持有列都有現價）→ **仍帶**續抱指示（斷言保留）；
    - 缺資料（個股無財報 ⇒ 燈全判不出；或持有列缺現價 `px_none`）→ **不帶**續抱、改帶資料不足指示。
    """
    hk, px = _NORMAL[case]
    st, _ai, prompt = _run(monkeypatch, holdings=_holdings(**hk), prices=px, vix=vix,
                           stock_grade=grade)
    _st, _ai2, pre = _run(monkeypatch, holdings=_holdings(**hk), prices=px, vix=vix,
                          svc_mod=_svc_pre(), stock_grade=grade)
    assert "invalid" not in st.digest
    assert list(st.digest) == list(_st.digest)
    assert prompt == pre and _FACT_HEAD not in prompt
    if grade == "A" and case != "px_none":
        assert _KEEP in prompt and "insufficient" not in st.digest
    else:
        assert _KEEP not in prompt and S._INSUFFICIENT_INSTRUCTION in prompt
        assert "- 資料不足／無法判定（持有）：" in prompt


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_digest_pure_function_held_only_and_error_rows_skipped(bad):
    rows = [{"代號": "A", "held": True, SS.KEY_INVALID_INPUTS: (SS.ITEM_PRICE,), "_detail": {}},
            {"代號": "B", "held": False, SS.KEY_INVALID_INPUTS: (SS.ITEM_PRICE,), "_detail": {}},
            {"代號": "C", "held": True, SS.KEY_INVALID_INPUTS: (SS.ITEM_LOTS,),
             "_detail": {"error": "x"}}]
    d = S.build_station_digest(rows, vix=_BAD[bad])
    assert d["invalid"] == [{"代號": "A", "項目": _inp("現價")}]
    assert d["errors"] == ["C"]
    p = S.build_summary_prompt(d)
    _no_nonfinite(p)
    assert _KEEP not in p and _prompt_line(p, _FACT_HEAD) == _fact(("A", _inp("現價")))


def test_mut_digest_reopens_keep_instruction(monkeypatch):
    """只拔 digest 那一環 → 修前重現：衛星現價異常、停利判不出，⑦ 仍被引導說續抱。"""
    m = _variant(_SVC, (Z52_DIGEST_PAIR,), "_z52_no_digest")
    st, _ai, prompt = _run(monkeypatch, holdings=_holdings(), prices={"2330": float("inf")},
                           svc_mod=m)
    # XV-H1-EXT（客戶 2026-10-28 裁示，取代 Z52 該部分語意）：現價異常 ⇒ 現價 None ⇒「缺現價」
    # 另一道防線也擋住續抱 ⇒ 拔 Z52 環後續抱**不再**重現；突變只看「異常事實列消失」。
    assert "invalid" not in st.digest and _KEEP not in prompt and _FACT_HEAD not in prompt, \
        "拔掉 → 持股輸入異常不進 ⑦"
    st2, _ai2, prompt2 = _run(monkeypatch, holdings=_holdings(), prices={"2330": float("inf")})
    assert _KEEP not in prompt2 and _FACT_HEAD in prompt2
