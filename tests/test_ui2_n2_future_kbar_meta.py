# -*- coding: utf-8 -*-
"""tests/test_ui2_n2_future_kbar_meta.py — N2 反例：📊 市場頁 Real feed 在 TWII「未來資料日」情境，
卡片說「資料日期不可信」，但日 K 圖下 meta 行仍印出那個不可信的未來日期（自相矛盾）。

根因（B 線定位，單組結論，未經第二組驗證）：
`src/services/ui2/real_canonical.py::kbar_chart_spec` 在所有分支判斷**之前**執行
`base.update(source=k.source, as_of=k.as_of)`，故 `ohlc_ok=False`（含 `FUTURE_DATE`）的 undeterminable 分支
也把未來 `as_of` 帶進 `FreshnessInfo`；`src/ui2/components/html.py::kbar_meta_text` 照實印出「資料日 <未來日>」。
對照組：`twii_card_spec` 在未來日分支（`snap.twii is None and twii_error == FUTURE_AS_OF_ERROR`）於 `base.update` 之前
return，`as_of` 維持 None（`tests/test_issue1202_future_as_of.py` 已鎖「⛔ 不帶那個不可信的日期」，但只鎖卡片，未鎖日 K）。

本檔：
- §1 反例（現行 main 應 FAIL）：真 L1 讀 tmp parquet 端到端（沿用 #1202 測試的 `_Env`，固定台北今日，無網路）。
- §2 反例（現行 main 應 FAIL）：未來日被**較早列**的其他原因碼遮蔽（`validate_ohlc_window` 逐列檢查、先遇先回），
  日 K 原因碼不是 `FUTURE_DATE`，但 `TwiiTrendView.as_of_future=True`——只看原因碼的修法會漏。
- §3 對照組（現行 main 應 PASS，鎖住「合理的資料日顯示」不被修法誤傷）：stale／非未來的不合格／讀取失敗／缺檔。
- §4 加固鎖（DEC-201 修法後新增）：修法兩條件（`as_of_future is True`／`ohlc_reason == FUTURE_DATE`）各自獨立鎖住；
  `validate_twii_kbar_fact` 拒收非三態 `as_of_future`。
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import re
from html import unescape

import pytest

from shared import twii_ohlc_contract as OC
from shared.ui2_contract import text as T
from shared.ui2_contract.models import FieldState, JudgementState
from shared.ui2_contract.pages import P4_MARKET
from src.services.ui2 import real_canonical as RC
from src.services.ui2.real_canonical import get_real_page_vm
from src.ui2.components import html as H
from src.ui2.views import _page, market
from tests.test_issue1202_future_as_of import BASE, FUTURE_TEXT, _Env
from tests.test_ui2_twii_kbar import _feed, _kbar_view, _matching_card

_META_RX = re.compile(r'data-ui2-kbar-meta="1">(.*?)</div>')


def _render_market(snap, monkeypatch) -> str:
    out: list[str] = []
    monkeypatch.setattr(market, "_md", out.append)
    monkeypatch.setattr(_page, "_md", out.append)
    market.render(get_real_page_vm(P4_MARKET, snap))
    return "".join(out)


def _meta(html: str) -> str:
    m = _META_RX.search(html)
    assert m, "找不到日 K meta 行"
    return unescape(m.group(1))


# ════════════════════════════════════════════════════════════════════
# §1｜反例：未來資料日（FUTURE_DATE）端到端 —— 卡片與日 K meta 不得自相矛盾
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("ahead", [1, 3])
def test_future_as_of_kbar_meta_must_not_print_the_untrusted_date(monkeypatch, tmp_path, ahead):
    env = _Env(monkeypatch, tmp_path)
    future = (BASE + dt.timedelta(days=ahead)).isoformat()
    env.write(BASE + dt.timedelta(days=ahead))
    snap = env.snapshot()

    # 前提（#1202 已鎖）：卡片＝紅 Unavailable＋「資料日期不可信」＋不帶日期；日 K＝不畫、原因碼 FUTURE_DATE
    card = RC.twii_card_spec(snap)
    assert card["state"] == "unavailable" and card["reason"] == FUTURE_TEXT and card["as_of"] is None
    assert snap.kbar is not None and snap.kbar.ohlc_ok is False and snap.kbar.ohlc_reason == OC.FUTURE_DATE
    spec = RC.kbar_chart_spec(snap)
    assert spec["candles"] == [] and spec["field"]["state"] == "undeterminable"

    # 反例 1：canonical spec 不得帶不可信的未來日期（與卡片同規則）
    assert spec["field"]["as_of"] is None, f"日 K spec 帶出不可信的未來資料日 {spec['field']['as_of']!r}"
    # 反例 2：VM freshness
    chart = get_real_page_vm(P4_MARKET, snap).context.kbar
    assert chart is not None and chart.field.state is JudgementState.UNDETERMINABLE
    assert chart.field.freshness.as_of is None
    # 反例 3：畫面 meta 行＝既有缺日期字樣，⛔「資料日 <未來日>」
    html = _render_market(snap, monkeypatch)
    meta = _meta(html)
    assert future not in meta, f"meta 行印出不可信的未來日期：{meta!r}"
    assert meta.startswith(T.TEXT_ASOF_MISSING)
    # 反例 4：整個 📊 市場頁可見文字都不得出現該未來日期（卡片說不可信，別處不得再當資料日呈現）
    assert future not in unescape(re.sub(r"<[^>]+>", " ", html))


# ════════════════════════════════════════════════════════════════════
# §2｜反例：未來日被較早列的原因碼遮蔽（原因碼≠FUTURE_DATE，但 as_of_future=True）
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("masking_code", [OC.INCOMPLETE_BAR, OC.FETCHED_AT_MISSING, OC.NOT_FINITE])
def test_masked_future_as_of_kbar_meta_must_not_print_the_untrusted_date(monkeypatch, masking_code):
    future = (BASE + dt.timedelta(days=2)).isoformat()
    good = _kbar_view()
    xs = good.xs[:-1] + (future,)
    kv = _kbar_view(xs=xs, as_of=future, is_stale=True, age_days=None, stale_reason="資料日晚於今日，無法判定新鮮度",
                    ohlc_ok=False, ohlc_error=masking_code, open=(), high=(), low=(), n_ohlc=0, as_of_future=True)
    card = _matching_card(kv, as_of_future=True)
    snap = _feed(monkeypatch, kbar=kv, card=card)
    assert snap.twii is None and snap.twii_error == RC.FUTURE_AS_OF_ERROR          # 卡片：資料日期不可信
    assert snap.kbar is not None and snap.kbar.ohlc_reason == masking_code            # 日 K：原因碼不是 FUTURE_DATE
    assert RC.twii_card_spec(snap)["reason"] == FUTURE_TEXT
    spec = RC.kbar_chart_spec(snap)
    assert spec["candles"] == []
    assert spec["field"]["as_of"] is None, f"遮蔽情境仍帶出未來資料日 {spec['field']['as_of']!r}"
    meta = _meta(_render_market(snap, monkeypatch))
    assert future not in meta and meta.startswith(T.TEXT_ASOF_MISSING)


# ════════════════════════════════════════════════════════════════════
# §3｜對照組（現行 main 應 PASS）：資料日可信時，meta 照實顯示「資料日 X」是正確行為
# ════════════════════════════════════════════════════════════════════
def test_control_stale_shows_its_real_as_of(monkeypatch):
    """Stale＝真歷史但舊：照畫＋顯示真實資料日（與卡片同日）。修法不得連這裡也拿掉。"""
    kv = _kbar_view(is_stale=True, age_days=4, stale_reason="已 4 天沒有新資料")
    snap = _feed(monkeypatch, kbar=kv)
    assert RC.kbar_chart_spec(snap)["field"]["as_of"] == kv.as_of == RC.twii_card_spec(snap)["as_of"]
    assert _meta(_render_market(snap, monkeypatch)).startswith(f"資料日 {kv.as_of}｜")


@pytest.mark.parametrize("code", [OC.NOT_FINITE, OC.INCOMPLETE_BAR, OC.OHLC_RELATION, OC.FETCHED_AT_MISSING])
def test_control_non_future_ohlc_reject_keeps_the_trusted_as_of(monkeypatch, code):
    """日 K 因非日期原因不合格、資料日≤基準日（as_of_future=False）：卡片同日照常顯示，meta 顯示同一資料日不矛盾。"""
    kv = _kbar_view(ohlc_ok=False, ohlc_error=code, open=(), high=(), low=(), n_ohlc=0, as_of_future=False)
    snap = _feed(monkeypatch, kbar=kv, card=_matching_card(kv, as_of_future=False))
    card = RC.twii_card_spec(snap)
    assert "state" not in card and card["as_of"] == kv.as_of
    spec = RC.kbar_chart_spec(snap)
    assert spec["field"]["state"] == "undeterminable" and spec["field"]["as_of"] == kv.as_of
    assert _meta(_render_market(snap, monkeypatch)).startswith(f"資料日 {kv.as_of}｜")


def test_control_failed_and_missing_never_carry_a_date(monkeypatch):
    """讀取失敗（紅）與缺檔（灰）：service 本就不給 as_of → meta＝既有缺日期字樣。"""
    snap = _feed(monkeypatch, kbar=_kbar_view(ok=False, failed=True, error="OSError: x", xs=(), close=(), as_of=None,
                                              is_stale=None, age_days=None, ohlc_ok=False, ohlc_error=OC.READ_FAILED,
                                              open=(), high=(), low=(), n_ohlc=0), card=_matching_card(_kbar_view()))
    chart = get_real_page_vm(P4_MARKET, snap).context.kbar
    assert chart.field.state is FieldState.UNAVAILABLE and chart.field.freshness.as_of is None
    assert H.kbar_meta_text(chart.field.freshness).startswith(T.TEXT_ASOF_MISSING)
    snap2 = _feed(monkeypatch, kbar=_kbar_view(ok=False, xs=(), close=(), as_of=None, is_stale=None, age_days=None,
                                               ohlc_ok=False, ohlc_error=OC.EMPTY, open=(), high=(), low=(), n_ohlc=0),
                  card=_matching_card(_kbar_view()))
    chart2 = get_real_page_vm(P4_MARKET, snap2).context.kbar
    assert chart2.field.state is FieldState.MISSING and chart2.field.freshness.as_of is None


# ════════════════════════════════════════════════════════════════════
# §4｜加固鎖（N2 修法兩條件各自獨立鎖住；突變「只看其一」必須轉紅）
# ════════════════════════════════════════════════════════════════════
def test_future_date_code_alone_drops_as_of_even_without_l3_flag():
    """L3 沒有可信台北基準（as_of_future=None）但 L0 日 K 檢查已判 FUTURE_DATE：日期同樣不可信，⛔ 帶 as_of。
    鎖住修法的 `ohlc_reason == FUTURE_DATE` 條件（只看 as_of_future 的修法會漏）。"""
    future = (BASE + dt.timedelta(days=2)).isoformat()
    kv = _kbar_view(as_of=future, ohlc_ok=False, ohlc_error=OC.FUTURE_DATE, open=(), high=(), low=(), n_ohlc=0,
                    as_of_future=None)
    k = RC.TwiiKbarFact.from_view(kv)
    assert k.as_of_future is None and k.ohlc_reason == OC.FUTURE_DATE
    snap = RC.RealFeedSnapshot(twii=None, twii_error="Exception", regime=None, regime_error="Exception", kbar=k)
    spec = RC.kbar_chart_spec(snap)
    assert spec["field"]["state"] == "undeterminable" and spec["field"]["as_of"] is None
    assert spec["field"]["source"] == k.source                    # source 照舊


@pytest.mark.parametrize("bad", [1, 0, "true", 1.0])
def test_validate_kbar_fact_rejects_non_tristate_as_of_future(bad):
    """as_of_future 只能是 True／False／None（身分比較，比照卡片端 validate_twii_fact）。"""
    k = RC.TwiiKbarFact.from_view(_kbar_view())
    with pytest.raises(RC.RealFeedContractError):
        RC.validate_twii_kbar_fact(dataclasses.replace(k, as_of_future=bad))
