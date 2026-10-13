"""批 Z53 —— 新 UI 三處資料異常（沿用批 Z49 客戶裁示 B）。

客戶裁示（2026-10-13，逐字）：統一採用「{項目}資料異常，無法計算，不下結論。」
  · NaN／±inf／其他無效數值一律視為異常；不顯示 nan／inf；不使用替代值繼續計算；
  · 該數值會影響結論時，該卡停止計算並不下結論；正常資料路徑不得改變；
  · 不擴大修改資料層、公式、門檻、權重、版面或其他文案。

三項（修前實測重現）：
  1. ④ 換股卡：持有列健檢 A 資料異常（⚪ 不判定）、又沒有 🔴 列 → 修前仍是灰卡
     「這是一個有效的結果…你持有的部位裡沒有健檢紅燈可換出」＝ 在壞資料上下結論。
     （總管 2026-10-13 依 QA 裁定：四盞健檢只有 A／B 會亮 🔴、B 無資料異常路徑 ⇒ 只有 A 影響換出；
      C／D 異常 ④ 不變。已有 🔴 時 🔴 照常下結論，異常列只在 facts 另外標出。）
     呼叫鏈：`page_hold.load_station` → L3 `build_station_rows`（`_invalid_lights`／`_invalid_texts`）
     → `load_switch` → L3 `build_switch_advice`（`switch_out_invalid`）→ `build_switch_card`
     （v2 摘錄 `V2_SHORT_ROWS[("hold.switch", SWITCH_FAILED_NOW)]`）；⑦ 經 `SwitchReadout.failed`。
  2. ⑥ 配息現金流：L3 `dividend_tax_service._recent_payments_and_failure` 的 `float(_v or 0.0) > 0`
     把 NaN 付息當成沒付（少報、照樣綠）、inf 會 OverflowError。
     呼叫鏈：`page_hold.load_deep` → L3 `portfolio_deep_service.get_dividend_cash_flow`
     → `dividend_tax_service.get_dividend_tax_view` → `_recent_payments_and_failure`
     → `build_dividend_cash_card`。
  3. ETF 品質評等：L2 `etf_quality.score_aum／score_expense／score_beta` 遇 NaN／+inf
     因 `min(1.0, nan) == 1.0` 給滿分 → `compute_etf_quality` 給出星等；字串則 TypeError。
     呼叫鏈：`page_inspect.load_etf_readout` → `_fetch_metrics` → L3 `fetch_metrics`
     （`m["etf_quality"] = compute_etf_quality(...)`）→ `build_peer_card` 的「品質評等」列。

修前＝現行原始碼套上本批 revert pair（測試本身不呼叫 git，見 `tests/test_zz_test_portability.py`）。
"""
from __future__ import annotations

import datetime as _dt
import functools
import itertools
import pathlib
import re
import sys
import types

import numpy as np
import pandas as pd
import pytest

import src.compute.etf.etf_quality as Q
import src.services.dividend_station_service as S
import src.services.dividend_tax_service as TX
import src.services.portfolio_deep_service as D
import src.ui.views.page_hold as PH
import src.ui.views.page_inspect as PI
from shared import station_specs as SS
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PAGE = "src/ui/views/page_hold.py"
_INSPECT = "src/ui/views/page_inspect.py"
_SVC = "src/services/dividend_station_service.py"
_TAX = "src/services/dividend_tax_service.py"
_QUAL = "src/compute/etf/etf_quality.py"

_BAD = {"nan": float("nan"), "pos_inf": float("inf"), "neg_inf": float("-inf")}
_BAD_S = {**_BAD, "np_nan": np.nan, "text": "abc"}
_NONFINITE_RE = re.compile(r"(?i)(?<![a-z])(nan|inf|infinity)(?![a-z])")
_VALID_PHRASE = "有效的結果"
_NO_RED_PHRASE = "沒有健檢紅燈可換出"


def _sentence(item: str) -> str:
    return f"{item}資料異常，無法計算，不下結論。"


def _no_nonfinite(text: str) -> None:
    _hit = _NONFINITE_RE.search(text)
    assert _hit is None, f"出現 {_hit.group(0)!r}：…{text[max(0, _hit.start() - 40):_hit.end() + 40]}…"


# ══════════════════════════════════════════════════════════════════
# revert-pair（修後逐字, 修前逐字）與變體載入
# ══════════════════════════════════════════════════════════════════
#: ① L3 `build_switch_advice`：不出 `switch_out_invalid`（＝修前輸出）。
Z53_L3_SWITCH_PAIR = ("    if _out_invalid:\n", "    if False:\n")
#: ① L5 ④ 卡：不看 `rows_invalid`（只拔這一環 → 卡回到灰「有效的結果」）。
Z53_CARD_PAIR = ("    _invalid_blocks = () if switch.switch_out else _rows_invalid\n",
                 "    _invalid_blocks = ()\n")
#: ① L5 `SwitchReadout.failed`：不看 `rows_invalid`（只拔這一環 → ⑦ 照樣帶「建議換出：無」）。
Z53_FAILED_PAIR = ("                    or (self.rows_invalid and not self.switch_out))\n",
                   "                    )\n")
#: ② L3 配息：不偵測異常值（＝修前：NaN 被丟掉、inf 進金額）。
Z53_TAX_PAIR = ("    if any(SS.is_invalid_number(_v) for _v in _recent.values):\n",
                "    if False:\n")
#: ③ L2 品質評等：三個評分函式與主入口的異常判定全部拔掉（＝修前）。
Z53_QUAL_PAIRS = (
    ("    if SS.is_invalid_number(aum):\n        return None\n", ""),
    ("    if SS.is_invalid_number(expense_ratio):\n        return None\n", ""),
    ("    if SS.is_invalid_number(beta):\n        return None\n", ""),
    ("    if _bad:\n        return {'stars': None,\n", "    if False:\n        return {'stars': None,\n"),
    # 追加（總管裁定）：配息序列異常的兩處判定。
    ("    if _divs_invalid(divs):\n        return None\n", ""),
    ("    _ycv_raw = None if _divs_bad else _yield_cv(_divs)\n", "    _ycv_raw = _yield_cv(_divs)\n"),
)
#: ③ L5 找標的頁：不看 `invalid_items`（只拔這一環 → 「品質評等」回到「—」）。
Z53_PEER_PAIR = ('        _q_bad = tuple(str(_i) for _i in (etf.quality.get("invalid_items") or ()))\n',
                 "        _q_bad = ()\n")

_ALL_PAIRS = {
    _SVC: (Z53_L3_SWITCH_PAIR,),
    _PAGE: (Z53_CARD_PAIR, Z53_FAILED_PAIR),
    _TAX: (Z53_TAX_PAIR,),
    _QUAL: Z53_QUAL_PAIRS,
    _INSPECT: (Z53_PEER_PAIR,),
}


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


def test_revert_pairs_are_unique_anchors():
    for rel, pairs in _ALL_PAIRS.items():
        code = (_ROOT / rel).read_text(encoding="utf-8")
        for new, _old in pairs:
            assert code.count(new) == 1, new


def _blob_hold(built) -> str:
    card, facts, sig = built
    return repr(card) + repr(tuple(facts)) + sig + PH.v2_card_html(card, facts, sig)


# ══════════════════════════════════════════════════════════════════
# 1. ④ 換股卡
# ══════════════════════════════════════════════════════════════════
_IDX = pd.date_range("2023-01-06", periods=120, freq="W-FRI")
_WK = pd.Series(np.linspace(20, 30, 120), index=_IDX)


def _wk_at(pos: int, v) -> pd.Series:
    w = _WK.astype(object).copy() if isinstance(v, str) else _WK.copy()
    w.iloc[pos] = v
    return w


def _etf_metrics(**over) -> dict:
    base = dict(weekly_close=_WK, premium_pct=0.3, sharpe=0.8, total_return_1y_pct=10.0,
                annual_yield_pct=5.0, inception_years=5.0, ann_return_3y_pct=8.0,
                cum_return_3y_pct=25.0, peer_ranks={3: .2, 6: .2, 12: .2}, current_price=30.0)
    base.update(over)
    return base


#: 被測列（0056）的健檢異常情境：(覆寫, 預期項目標籤, 預期客戶句)
#: 會改變換出結論的只有健檢 A（四盞裡只有 A／B 會亮 🔴，B 沒有資料異常路徑）。
_HEALTH_CASES = {
    "A_ret": (lambda v: {"total_return_1y_pct": v}, "健檢A", _sentence("近一年總報酬")),
    "A_yield": (lambda v: {"annual_yield_pct": v}, "健檢A", _sentence("配息率")),
}
#: C／D 只會亮 🟡／🟢 → 異常不改變換出結論 → ④ 不因此變（⑦「資料異常未判」照舊揭露）。
_NON_RED_CASES = {
    "C_last": lambda v: {"weekly_close": _wk_at(-1, v)},
    "D": lambda v: {"premium_pct": v},
}
_RED = {"sharpe": -1.0}          # 健檢 B 🔴 → 整列 🔴（正常值造出來的紅燈）
_CAND = ({"代碼": "00878", "名稱": "國泰永續", "綜合分": 80},)


def _hold_pair(held_0056: bool = True) -> list[dict]:
    return [{"ticker": "0056", "name": "0056", "asset_kind": "etf", "lots": 1.0,
             "avg_price": 25.0, "held": held_0056},
            {"ticker": "0050", "name": "0050", "asset_kind": "etf", "lots": 3.0,
             "avg_price": 25.0, "held": True}]


def _rows(over56: dict, over50: dict | None = None, *, held_0056: bool = True,
          Smod=S, vix=15.0) -> list[dict]:
    def mf(tk, kind):
        return _etf_metrics(**(over56 if tk == "0056" else (over50 or {})))
    return Smod.build_station_rows(_hold_pair(held_0056), vix=vix, metrics_fn=mf)


def _switch_run(monkeypatch, over56: dict, over50: dict | None = None, *, held_0056=True,
                Smod=S, Pmod=PH, cands=(), vix=15.0):
    """走新 UI 真的 `load_station` → `load_switch` → ④ 卡 → ⑦ prompt（外部全部替身）。"""
    monkeypatch.setattr(
        "src.services.dividend_station_service.get_station_rows",
        lambda h: (_rows(over56, over50, held_0056=held_0056, Smod=Smod, vix=vix), vix))
    monkeypatch.setattr("src.services.dividend_station_service.build_switch_advice",
                        Smod.build_switch_advice)
    monkeypatch.setattr("src.services.dividend_station_service.get_switch_in_candidates",
                        lambda **k: [dict(_c) for _c in cands])
    _cap: dict = {}

    def _gem(prompt, max_tokens=None, **k):
        _cap["prompt"] = prompt
        return "摘要OK"
    monkeypatch.setattr("src.services.app_ai_service.gemini_call", _gem)
    h = Pmod.HoldingsReadout(requested=True, submitted=True, bound=True,
                             holdings=tuple(_hold_pair(held_0056)))
    st = Pmod.load_station(h)
    sw = Pmod.load_switch(st, Pmod.MacroReadout(requested=True, loaded=False), h)
    built = Pmod.build_switch_card(sw, st)
    Pmod.load_ai_summary(True, st, sw)
    return st, sw, built, _cap.get("prompt", "")


def _svc_pre():
    return _variant(_SVC, (Z53_L3_SWITCH_PAIR,), "_z53_pre_svc")


def _page_pre():
    return _variant(_PAGE, (Z53_CARD_PAIR, Z53_FAILED_PAIR), "_z53_pre_page")


_HB = [(c, b) for c in _HEALTH_CASES for b in _BAD_S]
#: 週收序列放字串會讓 L2 均線在 `float()` 時就拋例外 → 該列整批抓取失敗（另有出口，非本批範圍），
#: 故 C 的字串情境不列。
_NB = [(c, b) for c in _NON_RED_CASES for b in _BAD_S if not (c == "C_last" and b == "text")]


@pytest.mark.parametrize("case,bad", _HB, ids=[f"{c}-{b}" for c, b in _HB])
def test_l3_switch_marks_held_health_a_invalid(case, bad):
    over, label, sentence = _HEALTH_CASES[case]
    adv = S.build_switch_advice(_rows(over(_BAD_S[bad])), {"loaded": False}, [])
    assert adv["switch_out"] == [], "前提：沒有 🔴 列"
    assert adv["switch_out_invalid"] == [{"代號": "0056", "項目": ((label, sentence),)}]
    _no_nonfinite(repr(adv))


def test_l3_switch_combined_a_items_one_sentence_pair():
    """A 兩個輸入都壞 → L2 一句裡兩個客戶句，原樣帶下來（不拆、不改）。"""
    adv = S.build_switch_advice(
        _rows({"total_return_1y_pct": float("nan"), "annual_yield_pct": float("inf")}),
        {"loaded": False}, [])
    assert adv["switch_out_invalid"] == [
        {"代號": "0056", "項目": (("健檢A", _sentence("近一年總報酬") + _sentence("配息率")),)}]


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_l3_switch_only_health_a_listed_when_c_also_invalid(bad):
    adv = S.build_switch_advice(
        _rows({"weekly_close": _wk_at(-1, _BAD[bad]), "annual_yield_pct": _BAD[bad],
               "inception_years": _BAD[bad]}), {"loaded": False}, [])
    assert [_t[0] for _t in adv["switch_out_invalid"][0]["項目"]] == ["健檢A"]


def test_l2_only_health_a_and_b_can_be_red():
    """第 1 點的事實守衛：C／D 在各種正常值下都不會亮 🔴；B 沒有資料異常旗標。"""
    from src.compute.etf import dividend_station as L2
    _c = {L2.health_c(pd.Series(np.linspace(a, b, 30))).level
          for a, b in ((10, 30), (30, 10), (20, 20.0001))}
    _d = {L2.health_d(p).level for p in (-5.0, 0.0, 1.0, 1.6, 50.0)}
    assert "🔴" not in _c | _d
    assert L2.health_b(-1.0).level == "🔴" and L2.health_a(1.0, 5.0).level == "🔴"
    assert not getattr(L2.health_b(None), "invalid", False)


@pytest.mark.parametrize("case,bad", _NB, ids=[f"{c}-{b}" for c, b in _NB])
@pytest.mark.parametrize("cands", [(), _CAND], ids=["no_cands", "cands"])
def test_c_d_invalid_does_not_change_switch(case, bad, cands, monkeypatch):
    """C／D 異常不改變換出結論 → L3 輸出、④ 卡、⑦ prompt 全部同修前；⑦ 照舊揭露資料異常未判。"""
    over = _NON_RED_CASES[case](_BAD_S[bad])
    rows = _rows(over)
    adv = S.build_switch_advice(rows, {"loaded": False}, list(cands))
    assert "switch_out_invalid" not in adv
    assert adv == _svc_pre().build_switch_advice(rows, {"loaded": False}, list(cands))
    _now = _switch_run(monkeypatch, over, cands=cands)
    _pre = _switch_run(monkeypatch, over, cands=cands, Pmod=_page_pre(), Smod=_svc_pre())
    assert repr(_now[2]) == repr(_pre[2]) and _now[3] == _pre[3]
    assert "- 資料異常未判：0056（" in _now[3]


def test_mut_c_d_counted_as_switch_out_invalid():
    """把 C／D 也算進換出異常（QA 指出的假警報）→ 本測試轉紅。"""
    m = _variant(_SVC, ((
        "_SWITCH_OUT_INVALID_KEYS: frozenset[str] = frozenset({SS.KEY_HEALTH_A})\n",
        "_SWITCH_OUT_INVALID_KEYS: frozenset[str] = frozenset("
        "{SS.KEY_HEALTH_A, SS.KEY_HEALTH_C, SS.KEY_HEALTH_D})\n"),), "_z53_mut_cd")
    adv = m.build_switch_advice(_rows({"premium_pct": float("nan")}, Smod=m), {"loaded": False}, [])
    assert "switch_out_invalid" in adv


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_l3_switch_red_row_with_invalid_not_marked(bad):
    """該列本來就 🔴（B 紅）→ 換出結論成立，不另列；輸出同修前。"""
    rows = _rows({**_RED, "annual_yield_pct": _BAD[bad]})
    adv = S.build_switch_advice(rows, {"loaded": False}, [])
    assert [d["代號"] for d in adv["switch_out"]] == ["0056"]
    assert "switch_out_invalid" not in adv
    assert adv == _svc_pre().build_switch_advice(rows, {"loaded": False}, [])


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_l3_switch_watchlist_invalid_not_marked(bad):
    """觀察清單列異常 → 不是換出對象，不列；輸出同修前。"""
    rows = _rows({"annual_yield_pct": _BAD[bad]}, held_0056=False)
    adv = S.build_switch_advice(rows, {"loaded": False}, [])
    assert "switch_out_invalid" not in adv
    assert adv == _svc_pre().build_switch_advice(rows, {"loaded": False}, [])


# ── M23：只有 235 燈異常的列 ⛔ 不得列為換出異常 ─────────────────────
@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_m23_only_235_invalid_not_switch_out_invalid(bad, monkeypatch):
    rows = _rows({}, vix=_BAD[bad])
    assert all(SS.KEY_LIGHT235 in (r.get(SS.KEY_INVALID_LIGHTS) or ()) for r in rows), "前提"
    adv = S.build_switch_advice(rows, {"loaded": False}, [])
    assert "switch_out_invalid" not in adv
    _now = _switch_run(monkeypatch, {}, vix=_BAD[bad])
    _pre = _switch_run(monkeypatch, {}, vix=_BAD[bad], Pmod=_page_pre(), Smod=_svc_pre())
    assert repr(_now[2]) == repr(_pre[2]) and _now[1].rows_invalid == ()


def test_m23_mut_235_counted():
    m = _variant(_SVC, ((
        "_SWITCH_OUT_INVALID_KEYS: frozenset[str] = frozenset({SS.KEY_HEALTH_A})\n",
        "_SWITCH_OUT_INVALID_KEYS: frozenset[str] = frozenset({SS.KEY_HEALTH_A, SS.KEY_LIGHT235})\n"),),
        "_z53_mut_235")
    adv = m.build_switch_advice(_rows({}, vix=float("nan"), Smod=m), {"loaded": False}, [])
    assert "switch_out_invalid" in adv


# ── ④ 卡：無 🔴 ＋ 健檢 A 異常 → 紅、不下結論 ───────────────────────
_SWITCH_INVALID_WHERE = f"{PH.NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者"


@pytest.mark.parametrize("case,bad", _HB, ids=[f"{c}-{b}" for c, b in _HB])
def test_card_no_red_invalid_does_not_conclude(case, bad, monkeypatch):
    over, _label, sentence = _HEALTH_CASES[case]
    st, sw, built, prompt = _switch_run(monkeypatch, over(_BAD_S[bad]))
    card, facts, sig = built
    assert card.state == UI_FAILED and sig == ""
    assert card.note.now == PH.SWITCH_FAILED_NOW
    assert card.note.why == f"0056：{sentence}"
    assert card.note.where == _SWITCH_INVALID_WHERE                    # M33
    assert _VALID_PHRASE not in _blob_hold(built) and _NO_RED_PHRASE not in _blob_hold(built)
    _no_nonfinite(_blob_hold(built))
    _short, _full = PH.v2_short_rows(card)            # 摘錄對得上原文（不 KeyError）
    assert dict(_short)[PH.V2_WHY_FACT_KEY] == sentence
    assert "── 換股建議 ──" not in prompt, "④ 判不出來時 ⑦ 不帶「建議換出：無」"
    assert f"- 資料異常未判：0056（健檢A：{sentence}" in prompt, "⑦ 揭露健檢 A 異常（Z51 機制）"
    assert sentence not in repr(tuple(facts)), "N8：紅卡 why 已講，facts 不重複追加"


def test_n8_mut_facts_appended_on_red_card(monkeypatch):
    """N8：拿掉「有 🔴 才在 facts 標出」的條件 → 紅卡 facts 又多一列「代號｜客戶句」→ 紅。"""
    P0 = _variant(_PAGE, ((
        "    if _rows_invalid and switch.switch_out:      # 批 Z53：有 🔴 時異常列另外標出\n",
        "    if _rows_invalid:\n"),), "_z53_mut_n8")
    card, facts, _s = _switch_run(monkeypatch, {"annual_yield_pct": float("nan")}, Pmod=P0)[2]
    assert card.state == UI_FAILED and ("0056", _sentence("配息率")) in tuple(facts)


def test_m33_mut_switch_invalid_where_falls_back():
    P0 = _variant(_PAGE, ((
        "                         why=_switch_invalid_why(_invalid_blocks),\n"
        f'                         where=f"{{NO_EXIT_MARKER}} —— 請把上面那行訊息回報給維護者")\n',
        "                         why=_switch_invalid_why(_invalid_blocks),\n"
        "                         where=STATION_ERROR_WHERE)\n"),), "_z53_mut_m33")
    st = P0.StationReadout(requested=True, submitted=True, bound=True, holdings_n=1,
                           rows=({"代號": "0056", "held": True, "_detail": {}},))
    sw = P0.SwitchReadout(requested=True, submitted=True,
                          rows_invalid=(("0056", (_sentence("配息率"),)),))
    assert P0.build_switch_card(sw, st)[0].note.where != _SWITCH_INVALID_WHERE


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_card_switch_in_only_with_invalid_does_not_conclude(bad, monkeypatch):
    """沒有 🔴、但有換入候選 → 修前是綠卡「換出 0 檔 → 換入 1 檔」；修後不下「換出 0 檔」結論。"""
    st, sw, built, prompt = _switch_run(monkeypatch, {"annual_yield_pct": _BAD[bad]}, cands=_CAND)
    card, facts, _sig = built
    assert card.state == UI_FAILED and card.value == ""
    assert ("建議換入（來源：選股池全自動排名）", "00878 國泰永續") in facts, "已算出的換入照列"
    assert card.note.why == f"0056：{_sentence('配息率')}"
    assert "── 換股建議 ──" not in prompt


# ── ④ 卡：有 🔴 ＋ 異常列 → 🔴 照常下結論，異常列另外標示 ─────────────
@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
@pytest.mark.parametrize("cands", [(), _CAND], ids=["no_cands", "cands"])
def test_card_red_kept_and_invalid_flagged(bad, cands, monkeypatch):
    """0050 🔴（正常值造的）＋ 0056 健檢 A 異常 → 卡片狀態／數值／訊號／⑦ 換股段同修前，
    只在 facts 尾端多一列「0056｜客戶句」。"""
    _now = _switch_run(monkeypatch, {"annual_yield_pct": _BAD_S[bad]}, _RED, cands=cands)
    _pre = _switch_run(monkeypatch, {"annual_yield_pct": _BAD_S[bad]}, _RED, cands=cands,
                       Pmod=_page_pre(), Smod=_svc_pre())
    card, facts, sig = _now[2]
    pcard, pfacts, psig = _pre[2]
    assert card.state == UI_LIVE and repr(card) == repr(pcard) and sig == psig == "有換股"
    assert tuple(facts) == tuple(pfacts) + (("0056", _sentence("配息率")),)
    assert _now[3] == _pre[3] and "── 換股建議 ──" in _now[3], "🔴 照常傳給 ⑦"
    assert "- 建議換出（你持有的紅燈汰弱）：0050（" in _now[3]
    assert f"- 資料異常未判：0056（健檢A：{_sentence('配息率')}" in _now[3]
    assert _now[1].failed is False
    _no_nonfinite(_blob_hold(_now[2]))


def test_mut_red_case_turns_red_again(monkeypatch):
    """把「有 🔴 時不擋」拔掉 → 整卡轉紅（QA 指出的過度封鎖）。"""
    P0 = _variant(_PAGE, ((
        "    _invalid_blocks = () if switch.switch_out else _rows_invalid\n",
        "    _invalid_blocks = _rows_invalid\n"),), "_z53_mut_block")
    built = _switch_run(monkeypatch, {"annual_yield_pct": float("nan")}, _RED, Pmod=P0)[2]
    assert built[0].state == UI_FAILED


def test_card_two_rows_same_sentence_grouped(monkeypatch):
    """兩檔同一句 → `代號、代號：句子`（同 `_invalid_why` 的列舉方式）。"""
    st, sw, built, _p = _switch_run(monkeypatch, {"annual_yield_pct": float("nan")},
                                    {"annual_yield_pct": float("inf")})
    assert built[0].note.why == f"0056、0050：{_sentence('配息率')}"


def test_card_invalid_with_row_fetch_failed_both_told():
    """整批抓取失敗的列 ＋ 健檢異常的列（沒有 🔴）→ 兩件都講（失敗那句在前），where 照修前。"""
    st = PH.StationReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                           rows=({"代號": "0056", "held": True, "_detail": {}},
                                 {"代號": "9999", "held": True, "_detail": {"error": "x"}}))
    sw = PH.SwitchReadout(requested=True, submitted=True, rows_failed=("9999",),
                          rows_invalid=(("0056", (_sentence("配息率"),)),))
    card, _f, _s = PH.build_switch_card(sw, st)
    assert card.state == UI_FAILED and card.note.where == PH.STATION_ERROR_WHERE
    assert card.note.why.startswith("9999：") and card.note.why.endswith(f"0056：{_sentence('配息率')}")
    PH.v2_short_rows(card)


def test_card_row_fetch_failed_with_red_and_invalid_flags_in_facts():
    """整批抓取失敗 ＋ 🔴 ＋ 健檢異常 → 照修前因抓取失敗轉紅；異常列標在 facts、why 不重複。"""
    st = PH.StationReadout(requested=True, submitted=True, bound=True, holdings_n=3,
                           rows=({"代號": "0056", "held": True, "_detail": {}},))
    sw = PH.SwitchReadout(requested=True, submitted=True, rows_failed=("9999",),
                          switch_out=({"代號": "0050", "建議動作": "汰弱"},),
                          rows_invalid=(("0056", (_sentence("配息率"),)),))
    card, facts, _s = PH.build_switch_card(sw, st)
    assert card.state == UI_FAILED and _sentence("配息率") not in card.note.why
    assert facts[-1] == ("0056", _sentence("配息率"))


# ── M28：`SwitchReadout.failed` 直接行為 ──────────────────────────────
_OUT = ({"代號": "0050", "建議動作": "🔴 汰弱"},)
_INV = (("0056", (_sentence("配息率"),)),)


def test_m28_failed_red_plus_invalid_is_not_failed():
    sw = PH.SwitchReadout(requested=True, switch_out=_OUT, rows_invalid=_INV)
    assert sw.failed is False
    assert PH._switch_payload(sw)["switch_out"] == [dict(_OUT[0])], "⑦ 照常帶換股段"


def test_m28_failed_invalid_without_red_is_failed():
    sw = PH.SwitchReadout(requested=True, switch_in=({"代號": "00878", "名稱": "x"},),
                          rows_invalid=_INV)
    assert sw.failed is True and PH._switch_payload(sw) is None


def test_m28_failed_normal_unchanged():
    for sw in (PH.SwitchReadout(requested=True, switch_out=_OUT),
               PH.SwitchReadout(requested=True)):
        assert sw.failed is False
    assert PH.SwitchReadout(requested=True, rows_failed=("9",), switch_out=_OUT).failed is True
    assert PH.SwitchReadout(requested=True, error="x").failed is True


def test_m28_mut_failed_unconditional_blocks_red():
    P0 = _variant(_PAGE, ((
        "                    or (self.rows_invalid and not self.switch_out))\n",
        "                    or self.rows_invalid)\n"),), "_z53_mut_m28a")
    assert P0.SwitchReadout(requested=True, switch_out=_OUT, rows_invalid=_INV).failed is True


def test_m28_mut_failed_ignores_invalid():
    P0 = _variant(_PAGE, (Z53_FAILED_PAIR,), "_z53_mut_m28b")
    assert P0.SwitchReadout(requested=True, rows_invalid=_INV).failed is False


_NORMAL_CASES = {
    "all_green": ({}, None),
    "red_0050": ({}, _RED),
    "missing_premium": ({"premium_pct": None}, None),
    "missing_yield": ({"annual_yield_pct": None}, None),
}


@pytest.mark.parametrize("case", list(_NORMAL_CASES), ids=list(_NORMAL_CASES))
@pytest.mark.parametrize("cands", [(), _CAND], ids=["no_cands", "cands"])
def test_switch_normal_identical_to_pre(case, cands, monkeypatch):
    o56, o50 = _NORMAL_CASES[case]
    rows = _rows(o56, o50)
    adv = S.build_switch_advice(rows, {"loaded": False}, list(cands))
    assert "switch_out_invalid" not in adv
    assert adv == _svc_pre().build_switch_advice(rows, {"loaded": False}, list(cands))
    _now = _switch_run(monkeypatch, o56, o50, cands=cands)
    _pre = _switch_run(monkeypatch, o56, o50, cands=cands, Pmod=_page_pre(), Smod=_svc_pre())
    assert repr(_now[2]) == repr(_pre[2])
    assert _now[3] == _pre[3], "⑦ prompt 逐字同修前"
    assert _now[1].rows_invalid == ()


def test_mut_l3_switch_reopens_valid_result(monkeypatch):
    """拔 L3 那一環 → ④ 又變回灰「有效的結果…沒有健檢紅燈可換出」（修前 bug）。"""
    _st, _sw, built, _p = _switch_run(monkeypatch, {"annual_yield_pct": float("nan")},
                                      Smod=_svc_pre())
    assert built[0].state == UI_EMPTY and _NO_RED_PHRASE in built[0].note.why


def test_mut_card_reopens_valid_result(monkeypatch):
    """只拔卡片那一環 → 灰「有效的結果」（L3 照樣標了也沒用）。"""
    P0 = _variant(_PAGE, (Z53_CARD_PAIR,), "_z53_pre_card_only")
    _st, _sw, built, _p = _switch_run(monkeypatch, {"annual_yield_pct": float("nan")}, Pmod=P0)
    assert built[0].state == UI_EMPTY and _VALID_PHRASE in built[0].note.why


def test_mut_failed_reopens_ai_switch_section(monkeypatch):
    """只拔 `failed` 那一環 → ⑦ 照樣把「建議換出：無」送進 prompt。"""
    P0 = _variant(_PAGE, (Z53_FAILED_PAIR,), "_z53_pre_failed_only")
    _st, _sw, _b, prompt = _switch_run(
        monkeypatch, {"annual_yield_pct": float("nan")}, Pmod=P0, cands=_CAND)
    assert "- 建議換出（你持有的紅燈汰弱）：無" in prompt


def test_v2_item_names_match_l2():
    """④ v2 摘錄候選的項目名與 L2 健檢 A 實際寫進客戶句的一致（L2 改名 → 這裡紅）。"""
    from src.compute.etf import dividend_station as L2
    _l2 = (L2.health_a(float("nan"), 1.0).msg, L2.health_a(1.0, float("nan")).msg)
    assert _l2 == PH._V2_SWITCH_INVALID_WHY


# ══════════════════════════════════════════════════════════════════
# 2. ⑥ 配息現金流
# ══════════════════════════════════════════════════════════════════
def _divs(values, *, old=(), obj: bool = False) -> pd.Series:
    """近一年逐月配息 `values`（最近的在最後）；`old` 放在 400 天前（超出近一年窗）。"""
    _today = pd.Timestamp(_dt.date.today())
    idx = [_today - pd.Timedelta(days=30 * (len(values) - _i)) for _i in range(len(values))]
    old_idx = [_today - pd.Timedelta(days=400 + _i) for _i in range(len(old))]
    vals = list(old) + list(values)
    dtype = object if obj or any(isinstance(_v, str) for _v in vals) else float
    return pd.Series(vals, index=old_idx + idx, dtype=dtype)


def _tax_pre():
    return _variant(_TAX, (Z53_TAX_PAIR,), "_z53_pre_tax")


def _tax_env(monkeypatch, mod, series_by_ticker: dict):
    monkeypatch.setattr(mod, "holding_currency", lambda t: "TWD")
    monkeypatch.setattr(mod, "fetch_etf_dividends",
                        lambda t: series_by_ticker[str(t).split(".")[0]])


@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
@pytest.mark.parametrize("pos", [0, -1], ids=["first", "last"])
def test_l3_tax_recent_invalid_marks_not_zero(bad, pos, monkeypatch):
    vals = [1.0, 1.2, 1.1]
    vals[pos] = _BAD_S[bad]
    _tax_env(monkeypatch, TX, {"0056": _divs(vals)})
    assert TX._recent_payments_and_failure("0056", 1000) == ([], _sentence("配息"))
    view = TX.get_dividend_tax_view([{"ticker": "0056", "shares": 1000}])
    assert view["invalid"] == {"0056": _sentence("配息")}
    assert view["fetch_failed"] == {}, "資料異常 ≠ 抓取失敗"
    assert view["per_etf"][0]["配息筆數"] == 0 and view["summary"]["gross"] == 0
    _no_nonfinite(repr(view))


@pytest.mark.parametrize("bad", ["pos_inf", "neg_inf"])
def test_mut_tax_pre_inf_overflows_or_counts(bad, monkeypatch):
    """修前：+inf 進金額 → 下游 OverflowError；-inf 被當成「沒付」靜默丟掉（金額少報）。"""
    _tax_env(monkeypatch, _tax_pre(), {"0056": _divs([1.0, _BAD[bad]])})
    if bad == "pos_inf":
        with pytest.raises(OverflowError):
            _tax_pre().get_dividend_tax_view([{"ticker": "0056", "shares": 1000}])
    else:
        view = _tax_pre().get_dividend_tax_view([{"ticker": "0056", "shares": 1000}])
        assert view["per_etf"][0]["配息筆數"] == 1 and "invalid" not in view


def test_mut_tax_pre_nan_silently_dropped(monkeypatch):
    _tax_env(monkeypatch, _tax_pre(), {"0056": _divs([1.0, float("nan"), 1.0])})
    view = _tax_pre().get_dividend_tax_view([{"ticker": "0056", "shares": 1000}])
    assert view["per_etf"][0]["配息筆數"] == 2 and view["summary"]["gross"] == 2000


_TAX_NORMAL = {
    "monthly": _divs([1.0] * 12),
    "with_zero": _divs([1.0, 0.0, 1.2]),
    # object 序列裡的 None ＝ 缺值（`is_invalid_number(None)` 為 False），照修前當沒付。
    # ⚠️ float 序列裡的 None 會被 pandas 轉成 NaN ＝ 異常（裁示 B），不屬正常路徑。
    "none_values": _divs([1.0, None, 1.2], obj=True),
    "old_invalid_outside_window": _divs([1.0, 1.1], old=(float("nan"), float("inf"))),
    "empty": pd.Series([], dtype=float),
    "none": None,
}


@pytest.mark.parametrize("case", list(_TAX_NORMAL), ids=list(_TAX_NORMAL))
def test_l3_tax_normal_identical_to_pre(case, monkeypatch):
    m = {"0056": _TAX_NORMAL[case], "0050": _divs([2.0, 2.0])}
    _tax_env(monkeypatch, TX, m)
    _tax_env(monkeypatch, _tax_pre(), m)
    hs = [{"ticker": "0056", "shares": 1000}, {"ticker": "0050", "shares": 2000}]
    now = TX.get_dividend_tax_view(hs, marginal_rate=0.12)
    assert "invalid" not in now
    assert now == _tax_pre().get_dividend_tax_view(hs, marginal_rate=0.12)


def test_l3_tax_fetch_failed_flag_unchanged(monkeypatch):
    from src.data.etf import DIVIDENDS_FETCH_FAILED_ATTR
    s = pd.Series([], dtype=float)
    s.attrs[DIVIDENDS_FETCH_FAILED_ATTR] = "boom"
    _tax_env(monkeypatch, TX, {"0056": s})
    view = TX.get_dividend_tax_view([{"ticker": "0056", "shares": 1000}])
    assert view["fetch_failed"] == {"0056": "boom"} and "invalid" not in view


def _deep_cash(monkeypatch, series_by_ticker: dict, rows: list[dict]):
    _tax_env(monkeypatch, TX, series_by_ticker)
    monkeypatch.setattr(D, "_yf_tickers", lambda ts, failed=None: {t: t for t in ts})
    return D.get_dividend_cash_flow(rows)


def _cash_row(code: str, lots: float = 1.0) -> dict:
    return {"代號": code, "held": True, "張數": lots, "均價": 20.0, "現價": 30.0, "_detail": {}}


def _cash_card(res, rows):
    deep = PH.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=len(rows),
                          has_station_rows=True, cash=res)
    return PH.build_dividend_cash_card(deep)


@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
def test_cash_card_invalid_only_does_not_conclude(bad, monkeypatch):
    rows = [_cash_row("0056"), _cash_row("0050")]
    res = _deep_cash(monkeypatch, {"0056": _divs([1.0, _BAD_S[bad]]), "0050": _divs([2.0])}, rows)
    assert res.invalid_tickers == ("0056.TW",) and "0056.TW" not in res.no_payout_tickers
    assert res.failed_tickers == ()
    built = _cash_card(res, rows)
    card, facts, sig = built
    assert card.state == UI_FAILED and sig == "" and card.value == ""
    assert card.note.now == PH.CASH_FAILED_NOW
    assert card.note.why == f"0056.TW：{_sentence('配息')}"
    assert "拋出例外" not in card.note.why, "資料異常不是例外"
    assert card.note.where == f"{PH.NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者"   # M16
    assert "貢獻 0 元" not in repr(facts) or "0056" not in dict(facts).get("這幾檔在這一年貢獻 0 元", "")
    _no_nonfinite(_blob_hold(built))
    _short, _ = PH.v2_short_rows(card)
    assert dict(_short)[PH.V2_WHY_FACT_KEY] == _sentence("配息")


def test_cash_card_invalid_with_l1_failure_both_told(monkeypatch):
    from src.data.etf import DIVIDENDS_FETCH_FAILED_ATTR
    s = pd.Series([], dtype=float)
    s.attrs[DIVIDENDS_FETCH_FAILED_ATTR] = "boom"
    rows = [_cash_row("0056"), _cash_row("0050")]
    res = _deep_cash(monkeypatch, {"0056": _divs([1.0, float("nan")]), "0050": s}, rows)
    assert res.invalid_tickers == ("0056.TW",) and res.failed_tickers == ("0050.TW",)
    card = _cash_card(res, rows)[0]
    assert card.state == UI_FAILED
    assert "0050.TW: boom" in card.note.why and card.note.why.endswith(f"0056.TW：{_sentence('配息')}")
    PH.v2_short_rows(card)


def test_cash_card_invalid_with_lots_invalid_keeps_station_where(monkeypatch):
    """Z49 張數異常（戰情表那一層）＋ 配息異常 → 兩句都講，where 照 Z49 既有。"""
    rows = [_cash_row("0056")]
    res = _deep_cash(monkeypatch, {"0056": _divs([1.0, float("inf")])}, rows)
    deep = PH.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                          has_station_rows=True, cash=res,
                          invalid_rows=((SS.ITEM_LOTS, ("0050",)),))
    card = PH.build_dividend_cash_card(deep)[0]
    assert card.state == UI_FAILED and card.note.where == PH.STATION_ERROR_WHERE
    assert card.note.why == f"0050：{_sentence('張數')}0056.TW：{_sentence('配息')}"


@pytest.mark.parametrize("case", ["monthly", "with_zero", "none_values",
                                  "old_invalid_outside_window", "empty"])
def test_cash_card_normal_identical_to_pre(case, monkeypatch):
    rows = [_cash_row("0056"), _cash_row("0050")]
    m = {"0056": _TAX_NORMAL[case], "0050": _divs([2.0, 2.0])}
    res = _deep_cash(monkeypatch, m, rows)
    assert res.invalid_tickers == ()
    P0 = _page_pre()
    deep_kw = dict(requested=True, submitted=True, bound=True, holdings_n=2,
                   has_station_rows=True, cash=res)
    assert repr(PH.build_dividend_cash_card(PH.DeepReadout(**deep_kw))) == repr(
        P0.build_dividend_cash_card(P0.DeepReadout(**deep_kw)))


def test_mut_cash_pre_nan_is_live(monkeypatch):
    """拔 L3 那一環 → NaN 那筆被丟掉，卡片照樣綠（修前 bug：少報）。"""
    rows = [_cash_row("0056")]
    _tax_env(monkeypatch, _tax_pre(), {"0056": _divs([1.0, float("nan")])})
    monkeypatch.setattr("src.services.dividend_tax_service.get_dividend_tax_view",
                        _tax_pre().get_dividend_tax_view)
    monkeypatch.setattr(D, "_yf_tickers", lambda ts, failed=None: {t: t for t in ts})
    res = D.get_dividend_cash_flow(rows)
    assert res.invalid_tickers == () and res.payouts_n == 1
    assert _cash_card(res, rows)[0].state == UI_LIVE


def test_m16_mut_cash_invalid_where_falls_back(monkeypatch):
    """M16：只有配息異常時 where 必須是 Z52 那一句；拔掉分流 → 退回「確認網路」那句 → 紅。"""
    P0 = _variant(_PAGE, ((
        "                     where=(STATION_ERROR_WHERE if (_cash_row_failed or _cash_bad)\n"
        '                            else f"{NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者"))\n',
        "                     where=STATION_ERROR_WHERE)\n"),), "_z53_mut_m16")
    rows = [_cash_row("0056")]
    res = _deep_cash(monkeypatch, {"0056": _divs([1.0, float("nan")])}, rows)
    deep = P0.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=1,
                          has_station_rows=True, cash=res)
    assert P0.build_dividend_cash_card(deep)[0].note.where == PH.STATION_ERROR_WHERE


def test_item_dividend_matches_l3():
    assert TX.INVALID_DIVIDEND_TEXT == SS.invalid_data_text(PH.ITEM_DIVIDEND) == _sentence("配息")


# ══════════════════════════════════════════════════════════════════
# 3. ETF 品質評等
# ══════════════════════════════════════════════════════════════════
def _qual_pre():
    return _variant(_QUAL, Z53_QUAL_PAIRS, "_z53_pre_qual")


_TICK = itertools.count()


def _quality(monkeypatch, mod, *, aum=5e10, exp=0.004, beta=0.95, divs="ok"):
    """`compute_etf_quality` 替身取數；每次用新代號，避開 `st.cache_data`。"""
    _d = (pd.Series([1.0, 1.1, 1.0, 1.05, 1.0, 1.1],
                    index=pd.date_range(end=pd.Timestamp(_dt.date.today()), periods=6,
                                        freq="180D"))
          if isinstance(divs, str) and divs == "ok" else divs)
    monkeypatch.setattr(mod, "fetch_etf_info", lambda t: {"totalAssets": aum, "beta": beta})
    monkeypatch.setattr(mod, "get_etf_expense_ratio_safe", lambda t: exp)
    monkeypatch.setattr(mod, "fetch_etf_dividends", lambda t: _d)
    return mod.compute_etf_quality(f"Z53Q{next(_TICK)}.TW")


_QF = {"aum": "AUM", "exp": "費用率", "beta": "Beta"}
_QB = [(f, b) for f in _QF for b in _BAD_S]


@pytest.mark.parametrize("field,bad", _QB, ids=[f"{f}-{b}" for f, b in _QB])
def test_l2_quality_invalid_no_stars(field, bad, monkeypatch):
    q = _quality(monkeypatch, Q, **{field: _BAD_S[bad]})
    assert q["stars"] is None
    assert q["invalid_items"] == (_QF[field],)
    assert q["_err"] == _sentence(_QF[field])
    assert "score" not in q and "weakest" not in q


@pytest.mark.parametrize("fn", ["score_aum", "score_expense", "score_beta"])
@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
def test_l2_score_fns_invalid_none(fn, bad):
    assert getattr(Q, fn)(_BAD_S[bad]) is None


def test_l2_quality_multiple_invalid_listed_in_order(monkeypatch):
    q = _quality(monkeypatch, Q, aum=float("nan"), beta=float("inf"))
    assert q["invalid_items"] == ("AUM", "Beta")
    assert q["_err"] == _sentence("AUM") + _sentence("Beta")


@pytest.mark.parametrize("fn", ["score_aum", "score_expense", "score_beta"])
@pytest.mark.parametrize("bad", ["nan", "pos_inf"])
def test_mut_l2_score_pre_full_marks(fn, bad):
    """修前：NaN／+inf 拿滿分（`min(1.0, nan) == 1.0`）。"""
    _v = _qual_pre()
    if fn == "score_aum" or bad == "nan":
        assert getattr(_v, fn)(_BAD[bad]) == 1.0
    else:
        assert getattr(_v, fn)(_BAD[bad]) in (0.0, 1.0)


@pytest.mark.parametrize("field", list(_QF))
def test_mut_l2_quality_pre_gives_stars(field, monkeypatch):
    q = _quality(monkeypatch, _qual_pre(), **{field: float("nan")})
    assert q["stars"] is not None, "修前在壞資料上給星等"


_Q_NORMAL = {
    "base": {},
    "low_aum": {"aum": 2e9},
    "aum_none": {"aum": None},
    "aum_zero": {"aum": 0},
    "exp_none": {"exp": None},
    "exp_neg": {"exp": -0.1},
    "beta_none": {"beta": None},
    "beta_far": {"beta": 2.5},
    "divs_none": {"divs": None},
    "all_none": {"aum": None, "exp": None, "beta": None, "divs": None},
}


@pytest.mark.parametrize("case", list(_Q_NORMAL), ids=list(_Q_NORMAL))
def test_l2_quality_normal_identical_to_pre(case, monkeypatch):
    now = _quality(monkeypatch, Q, **_Q_NORMAL[case])
    pre = _quality(monkeypatch, _qual_pre(), **_Q_NORMAL[case])
    assert "invalid_items" not in now
    assert now == pre


@pytest.mark.parametrize("v", [None, 0, -1, 1e8, 5e9, 1e10, 1e12, 0.001, 0.003, 0.015, 0.9, 1.0, 2.0])
def test_l2_score_fns_normal_identical_to_pre(v):
    for fn in ("score_aum", "score_expense", "score_beta"):
        assert getattr(Q, fn)(v) == getattr(_qual_pre(), fn)(v)


def _peer(quality):
    return PI.build_peer_card(PI.EtfReadout(requested=True, peer_ranks={3: .2, 6: .3, 12: .4},
                                            quality=quality, inception_years=5.0))


@pytest.mark.parametrize("field,bad", _QB, ids=[f"{f}-{b}" for f, b in _QB])
def test_peer_card_quality_invalid_shows_sentence(field, bad, monkeypatch):
    q = _quality(monkeypatch, Q, **{field: _BAD_S[bad]})
    card, facts, sig = _peer(q)
    assert dict(facts)["品質評等"] == _sentence(_QF[field])
    _blob = repr(card) + repr(tuple(facts)) + sig
    assert "★" not in _blob
    _no_nonfinite(_blob)


@pytest.mark.parametrize("case", list(_Q_NORMAL), ids=list(_Q_NORMAL))
def test_peer_card_normal_identical_to_pre(case, monkeypatch):
    q = _quality(monkeypatch, Q, **_Q_NORMAL[case])
    P0 = _variant(_INSPECT, (Z53_PEER_PAIR,), "_z53_pre_inspect")
    assert repr(_peer(q)) == repr(P0.build_peer_card(P0.EtfReadout(
        requested=True, peer_ranks={3: .2, 6: .3, 12: .4}, quality=q, inception_years=5.0)))


def test_peer_card_failed_err_unchanged():
    """既有「抓取失敗」的 stars=None 照舊顯示「—」。"""
    assert dict(_peer({"stars": None, "_err": "抓取失敗 RuntimeError"})[1])["品質評等"] == "—"


def test_mut_peer_card_pre_shows_dash(monkeypatch):
    q = _quality(monkeypatch, Q, beta=float("nan"))
    P0 = _variant(_INSPECT, (Z53_PEER_PAIR,), "_z53_pre_inspect")
    _f = dict(P0.build_peer_card(P0.EtfReadout(requested=True, peer_ranks={12: .4},
                                               quality=q))[1])
    assert _f["品質評等"] == "—" and _sentence("Beta") not in repr(_f)


def test_mut_peer_card_pre_l2_shows_stars(monkeypatch):
    """L2 拔掉 → 壞資料給出星等數字，卡上照印（修前 bug）。"""
    q = _quality(monkeypatch, _qual_pre(), beta=float("nan"))
    assert dict(_peer(q)[1])["品質評等"] == str(q["stars"]) and q["stars"] is not None


# ══════════════════════════════════════════════════════════════════
# 3b. ETF 品質評等 —— 配息序列異常（總管 2026-10-13 追加，同一缺陷：殖利率穩定度遇無效值給滿分）
# ══════════════════════════════════════════════════════════════════
def _qdivs(values, *, old=()) -> pd.Series:
    """評分窗（近 3Y）內每 180 天一筆 `values`（最近的在最後）；`old` 放在 4 年多前（窗外）。"""
    _today = pd.Timestamp(_dt.date.today())
    idx = [_today - pd.Timedelta(days=180 * (len(values) - 1 - _i)) for _i in range(len(values))]
    old_idx = [_today - pd.Timedelta(days=1500 + _i) for _i in range(len(old))]
    vals = list(old) + list(values)
    dtype = object if any(isinstance(_v, str) for _v in vals) else float
    return pd.Series(vals, index=old_idx + idx, dtype=dtype)


_DIV_OK = [1.0, 1.1, 1.0, 1.05, 1.0, 1.1]


@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
@pytest.mark.parametrize("pos", [0, 3, -1], ids=["first", "mid", "last"])
def test_l2_quality_divs_invalid_no_stars(bad, pos, monkeypatch):
    vals = list(_DIV_OK)
    vals[pos] = _BAD_S[bad]
    q = _quality(monkeypatch, Q, divs=_qdivs(vals))
    assert q["stars"] is None
    assert q["invalid_items"] == ("殖利率穩定度",)
    assert q["_err"] == _sentence("殖利率穩定度")
    assert q["factors"]["yield_cv"] == {"val": None, "score": None}
    _no_nonfinite(repr({k: v for k, v in q.items() if k != "factors"}))
    assert Q.score_yield_cv(_qdivs(vals)) is None


def test_l2_quality_divs_item_name_is_existing_factor_name():
    assert Q.INVALID_ITEM_YIELD_CV == Q._FACTOR_NAMES["yield_cv"]


def test_l2_quality_divs_and_others_listed_in_factor_order(monkeypatch):
    q = _quality(monkeypatch, Q, aum=float("nan"), beta=float("inf"),
                 divs=_qdivs([1.0, float("inf"), 1.0, 1.0]))
    assert q["invalid_items"] == ("AUM", "殖利率穩定度", "Beta")


def test_mut_l2_score_yield_cv_pre_full_marks():
    """修前：+inf → 年度平均 inf、std NaN → CV 為 NaN → 滿分 1.0。
    （-inf 修前是平均 ≤ 0 → 當成缺值 None，整體仍用其餘因子給星等，見下一條。）"""
    vals = list(_DIV_OK)
    vals[-1] = float("inf")
    assert _qual_pre().score_yield_cv(_qdivs(vals)) == 1.0


@pytest.mark.parametrize("bad", ["nan", "pos_inf", "neg_inf"])
def test_mut_l2_quality_divs_pre_gives_stars(bad, monkeypatch):
    vals = list(_DIV_OK)
    vals[1] = _BAD[bad]
    q = _quality(monkeypatch, _qual_pre(), divs=_qdivs(vals))
    assert q["stars"] is not None, "修前在壞配息上給星等"


_DIV_NORMAL = {
    "ok": _qdivs(_DIV_OK),
    "too_few": _qdivs([1.0, 1.1, 1.0]),                    # < 4 筆 → CV None
    "one_year": pd.Series([1.0, 1.0, 1.0, 1.0],            # 同一年 → CV None
                          index=pd.date_range(end=pd.Timestamp(_dt.date.today()),
                                              periods=4, freq="7D")),
    "zeros": _qdivs([0.0] * 6),                            # 平均 ≤ 0 → CV None
    "varied": _qdivs([0.5, 2.0, 0.1, 3.0, 0.2, 1.5]),
    "old_invalid_outside_window": _qdivs(_DIV_OK, old=(float("nan"), float("inf"))),
    "empty": pd.Series([], dtype=float),
    "none": None,
}


@pytest.mark.parametrize("case", list(_DIV_NORMAL), ids=list(_DIV_NORMAL))
def test_l2_quality_divs_normal_identical_to_pre(case, monkeypatch):
    now = _quality(monkeypatch, Q, divs=_DIV_NORMAL[case])
    pre = _quality(monkeypatch, _qual_pre(), divs=_DIV_NORMAL[case])
    assert "invalid_items" not in now
    assert now == pre
    assert Q.score_yield_cv(_DIV_NORMAL[case]) == _qual_pre().score_yield_cv(_DIV_NORMAL[case])
    assert Q._yield_cv(_DIV_NORMAL[case]) == _qual_pre()._yield_cv(_DIV_NORMAL[case])


@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
def test_peer_card_divs_invalid_shows_sentence(bad, monkeypatch):
    vals = list(_DIV_OK)
    vals[2] = _BAD_S[bad]
    card, facts, sig = _peer(_quality(monkeypatch, Q, divs=_qdivs(vals)))
    assert dict(facts)["品質評等"] == _sentence("殖利率穩定度")
    _no_nonfinite(repr(card) + repr(tuple(facts)) + sig)
