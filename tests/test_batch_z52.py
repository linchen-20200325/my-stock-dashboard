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
import pytest

import src.ui.views.page_hold as PH
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
_PRE_PAGE_PAIRS = (Z52_CARD_PAIR, Z52_LOAD_PAIR)


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


def test_revert_pairs_are_unique_anchors():
    for rel, pairs in ((_PAGE, _PRE_PAGE_PAIRS),):
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
