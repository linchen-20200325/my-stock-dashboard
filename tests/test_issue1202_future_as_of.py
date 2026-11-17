# -*- coding: utf-8 -*-
"""tests/test_issue1202_future_as_of.py — Issue #1202「未來 as_of」候選 1 回歸（ChatGPT 2026-11-17 施工裁示）。

設計（以下結論為自跑，未經第二組驗證）：
- L3 `market_twii_view_service` 同一次呼叫**只取一次**台北今日（注入 `today` 優先），同一個值明確給 L1 `today=`、
  卡片 `as_of_future` 比對、日 K `validate_ohlc_window(today=)`；`TwiiTrendView.as_of_future`：None＝無可信基準／as_of 缺失或無法解析
  （不判未來）、True／False＝已與基準比對（`as_of > 基準` 才 True）。
- `real_feed` 只逐欄拷貝；`real_canonical.validate_twii_fact` 對 `ok and as_of_future is True` raise 專用子類
  `RealFeedFutureAsOfError(RealFeedContractError)`，`exception_code` 給專用代碼 → `twii_card_spec` 映射定稿文案（僅此一處）。
- 台北牆鐘只是 UI「資料日期可顯示性」基準，⛔ 不是 published_at／PIT。

固定日注入，不依賴真牆鐘；真實 L1（`macro_cache_reader`）讀 tmp parquet 端到端；無網路、不碰真實 data_cache。
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import pathlib
import re
import types

import pandas as pd
import pytest

from shared import twii_ohlc_contract as OC
from shared.ui2_contract.models import FieldState
from shared.ui2_contract.pages import P4_MARKET, PAGE_IDS, SCENARIO_IDS
from src.data.macro import macro_cache_reader as R
from src.services import market_twii_view_service as S
from src.services.ui2 import real_canonical as RC, real_feed as RF
from src.services.ui2.real_canonical import RealFeedSnapshot, TwiiFact, get_real_page_vm

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = dt.date(2026, 11, 17)                      # 注入的「台北今日」（固定）
FUTURE_TEXT = "台股加權指數：資料日期不可信，暫時無法顯示。"      # ChatGPT 定稿，逐字
FORMAT_TEXT = "台股加權指數：資料格式異常，暫時無法顯示"


# ── helpers ──────────────────────────────────────────────────────────────
def _write_twii(tmp_path, end: dt.date, n: int = 5, *, with_ohlc_cols: bool = True):
    dates = [end - dt.timedelta(days=n - 1 - i) for i in range(n)]
    df = pd.DataFrame({"date": pd.to_datetime(dates), "close": [22000.0 + i for i in range(n)]})
    if with_ohlc_cols:
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
        df["volume"] = 1000
        df["fetched_at"] = [f"{d.isoformat()}T10:00:00+00:00" for d in dates]   # 台北 18:00 ⇒ 已收盤
    df.to_parquet(tmp_path / "twii_ohlcv.parquet")


class _Env:
    """真實 L1 讀 tmp parquet；記錄 L1 收到的 today、`_taipei_today` 被呼叫次數。台北今日固定為 `tpe`。"""

    def __init__(self, monkeypatch, tmp_path, tpe=BASE):
        self.tmp, self.mp, self.tpe = tmp_path, monkeypatch, tpe
        self.l1_today: list = []
        self.tpe_calls = 0
        oc, oo = R.load_twii_close, R.load_twii_ohlc

        def close(*a, **k):
            self.l1_today.append(("close", k.get("today")))
            return oc(cache_dir=tmp_path, **k)

        def ohlc(*a, **k):
            self.l1_today.append(("ohlc", k.get("today")))
            return oo(cache_dir=tmp_path, **k)

        def taipei():
            self.tpe_calls += 1
            return self.tpe

        monkeypatch.setattr(R, "load_twii_close", close)
        monkeypatch.setattr(R, "load_twii_ohlc", ohlc)
        monkeypatch.setattr(S, "_taipei_today", taipei)

    def write(self, as_of: dt.date, **kw):
        _write_twii(self.tmp, as_of, **kw)

    def snapshot(self) -> RealFeedSnapshot:
        """經真 feed 的兩個台股讀取（卡片＋日 K）；位階略（給固定錯誤代碼，與本議題無關）。"""
        twii, twii_err = RF._read_twii()
        kbar, kbar_err = RF._read_twii_kbar()
        return RealFeedSnapshot.of(twii, twii_err, None, "Exception", kbar=kbar, kbar_error=kbar_err)


@pytest.fixture
def env(monkeypatch, tmp_path):
    return _Env(monkeypatch, tmp_path)


def _card(snap):
    return RC.twii_card_spec(snap)


def _kbar_field(snap):
    return RC.kbar_chart_spec(snap)


# ════════════════════════════════════════════════════════════════════
# 1｜未來日：卡片 unavailable＋專用文案＋無收盤值；日 K 不畫
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("ahead", [1, 3])
def test_future_as_of_card_unavailable_with_dedicated_text_and_no_close(env, ahead):
    env.write(BASE + dt.timedelta(days=ahead))
    v = S.get_twii_trend_view(1)
    assert v.ok and v.as_of_future is True and v.is_stale is True and v.age_days is None   # L3：#1140 C2 語意不動
    snap = env.snapshot()
    assert snap.twii is None and snap.twii_error == RC.FUTURE_AS_OF_ERROR                   # feed 專用代碼，非泛用 CONTRACT_ERROR
    card = _card(snap)
    assert card["state"] == "unavailable" and card["value"] is None
    assert card["reason"] == FUTURE_TEXT
    assert card["as_of"] is None                                                            # ⛔ 不帶那個不可信的日期
    # 頁面層：FieldVM 無收盤值、紅色 Unavailable、文案逐字
    f = get_real_page_vm(P4_MARKET, snap).context.cards[0].field
    assert f.state is FieldState.UNAVAILABLE and f.value_text is None
    assert FUTURE_TEXT in (f.detail or "") and "資料格式異常" not in (f.detail or "")
    assert "22,00" not in repr(f)                                                           # 沒有任何收盤值字樣


@pytest.mark.parametrize("ahead", [1, 3])
def test_future_as_of_kbar_not_drawn_and_both_unavailable_not_iff(env, ahead):
    env.write(BASE + dt.timedelta(days=ahead))
    kv = S.get_twii_trend_view(5, with_ohlc=True)
    assert kv.ok and kv.ohlc_ok is False and kv.open == () and kv.n_ohlc == 0
    assert kv.ohlc_error in (OC.FUTURE_DATE, OC.INCOMPLETE_BAR)        # 兩者都「不畫」（INCOMPLETE_BAR 可遮蔽 FUTURE_DATE）
    assert kv.as_of_future is True
    snap = env.snapshot()
    chart = _kbar_field(snap)
    assert chart["candles"] == []                                      # 日 K 不畫
    assert _card(snap)["state"] == "unavailable"                       # 卡片也不可用：future → 兩者皆不可用（單向，不寫 iff）


def test_card_unavailable_does_not_imply_future_for_kbar(env, monkeypatch):
    """反向不成立（不是 iff）：卡片因其他原因不可用（讀取例外）時，日 K 不是 FUTURE_DATE，也不出現新字串。"""
    env.write(BASE - dt.timedelta(days=1))

    def boom(*a, **k):
        raise OSError("disk")
    monkeypatch.setattr(R, "load_twii_close", boom)                     # 只有卡片那條 loader 壞
    snap = env.snapshot()
    assert _card(snap)["state"] == "unavailable" and _card(snap)["reason"] != FUTURE_TEXT
    assert snap.kbar is not None and snap.kbar.ohlc_reason != OC.FUTURE_DATE


# ════════════════════════════════════════════════════════════════════
# 2｜邊界：= 基準、基準-1 不回歸；`>` 非 `>=`
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("back", [0, 1])
def test_as_of_equal_or_before_base_is_not_future(env, back):
    env.write(BASE - dt.timedelta(days=back))
    v = S.get_twii_trend_view(1)
    assert v.as_of_future is False and v.is_stale is False and v.age_days == back
    snap = env.snapshot()
    assert snap.twii is not None and snap.twii.as_of_future is False
    card = _card(snap)
    assert "state" not in card and card["value"] == "22,004.00"
    kv = S.get_twii_trend_view(5, with_ohlc=True)
    assert kv.ohlc_ok is True and kv.as_of_future is False and kv.n_ohlc == 5     # 日 K 照畫


def test_gt_not_gte_boundary_unit():
    assert S._as_of_future("2026-11-17", BASE) is False         # 等於基準＝今日資料，不是未來
    assert S._as_of_future("2026-11-18", BASE) is True          # 基準+1 才是
    assert S._as_of_future("2026-11-16", BASE) is False


def test_stale_ten_days_is_stale_not_future(env):
    env.write(BASE - dt.timedelta(days=10))
    v = S.get_twii_trend_view(1)
    assert v.as_of_future is False and v.is_stale is True and v.age_days == 10
    card = _card(env.snapshot())
    assert card["state"] == "stale" and card["stale_days"] == 10 and card["value"] == "22,004.00"
    assert card["reason"] != FUTURE_TEXT


# ════════════════════════════════════════════════════════════════════
# 3｜沒有可信基準／as_of 缺失或無法解析 → 不判 future，行為同現況
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("as_of", [None, "", "garbage", "2026-02-30", "20261118", "2026-11-1", 20261118])
def test_unparseable_or_missing_as_of_is_never_judged_future(as_of):
    assert S._as_of_future(as_of, BASE) is None


@pytest.mark.parametrize("base", [None, "2026-11-17", 20261117])
def test_no_trusted_base_is_never_judged_future(base):
    assert S._as_of_future("2099-01-01", S._as_date(base)) is None      # 非日期型別 → 無基準 → 不判


def test_taipei_today_unavailable_card_keeps_legacy_stale_semantics(env, monkeypatch):
    """台北日取不到 → 不判 future；L1 沿用自己的預設（host 日）；遠未來資料仍走既有 stale（age_days=None、is_stale=True）、
    不稱最新、卡片仍 stale 並顯示收盤值（＝現況），⛔ 不憑空稱 fresh。"""
    env.write(dt.date(2099, 1, 1))

    def broken():
        raise RuntimeError("no tz")
    monkeypatch.setattr(S, "_taipei_today", broken)
    v = S.get_twii_trend_view(1)
    assert v.ok and v.as_of_future is None
    assert v.is_stale is True and v.age_days is None
    assert env.l1_today[-1] == ("close", None)                     # 沒有基準 → 不強塞，L1 自己的預設
    snap = env.snapshot()
    card = _card(snap)
    assert card["state"] == "stale" and card["value"] == "22,004.00" and card["reason"] != FUTURE_TEXT


def test_fact_with_as_of_none_or_flag_none_not_future():
    f = TwiiFact(True, (100.0,), None, None, "", None, False, "", False, "s")
    RC.validate_twii_fact(f)
    spec = RC.twii_card_spec(RealFeedSnapshot(twii=f, twii_error="", regime=None, regime_error="x"))
    assert spec["state"] == "stale" and spec["reason"].startswith("新鮮度未判定")        # 不稱最新


# ════════════════════════════════════════════════════════════════════
# 4｜控制組：fresh／STALE／FAULT／FAKE
# ════════════════════════════════════════════════════════════════════
def test_control_fresh_unchanged(env):
    env.write(BASE - dt.timedelta(days=1))
    snap = env.snapshot()
    card = _card(snap)
    assert "state" not in card and card["value"] == "22,004.00" and card["as_of"] == "2026-11-16"
    assert _kbar_field(snap)["candles"]


def test_control_fault_loader_exception_shows_read_failed_not_new_text(env, monkeypatch):
    env.write(BASE)

    def boom(*a, **k):
        raise OSError("disk")
    monkeypatch.setattr(R, "load_twii_close", boom)
    card = _card(env.snapshot())
    assert card["state"] == "unavailable" and card["reason"] == "台股加權指數暫時無法讀取"


def test_control_fake_scenarios_never_call_the_service(monkeypatch):
    from src.services.ui2.preview_feed import get_preview_page_vm

    def trap(*a, **k):
        raise AssertionError("FAKE 不得呼叫台股 service")
    monkeypatch.setattr(S, "get_twii_trend_view", trap)
    for sc in SCENARIO_IDS:
        vm = get_preview_page_vm(P4_MARKET, sc)
        assert FUTURE_TEXT not in repr(vm)


# ════════════════════════════════════════════════════════════════════
# 5｜單一基準：L1／卡片比對／日 K 同一個台北日（host 日與台北日不同時）
# ════════════════════════════════════════════════════════════════════
# 注意：`date.today` 是內建型別屬性，無法 monkeypatch；改把「注入的台北日」設得離真實 host 日很遠（2030／2020），
# 讓「L1 用 host 日」與「L1 用台北日」得到相反結論——測試結果與執行當天的真牆鐘無關。
@pytest.mark.parametrize("far_tpe", [dt.date(2030, 6, 15), dt.date(2020, 1, 6)])
def test_l1_receives_taipei_today_not_host_today_card_path(env, far_tpe):
    """台北今日 ≠ host 本地日：資料日＝台北今日 ⇒ L1 必須收到台北日（不是 None／host）→ 不被誤判未來。"""
    env.tpe = far_tpe
    env.write(far_tpe)
    v = S.get_twii_trend_view(1)
    assert env.l1_today[-1] == ("close", far_tpe)
    assert v.as_of_future is False and v.is_stale is False and v.age_days == 0


@pytest.mark.parametrize("far_tpe", [dt.date(2030, 6, 15), dt.date(2020, 1, 6)])
def test_l1_receives_taipei_today_not_host_today_ohlc_path(env, far_tpe):
    env.tpe = far_tpe
    env.write(far_tpe)
    kv = S.get_twii_trend_view(5, with_ohlc=True)
    assert env.l1_today[-1] == ("ohlc", far_tpe)
    assert kv.as_of_future is False and kv.is_stale is False and kv.ohlc_ok is True


@pytest.mark.parametrize("far_tpe", [dt.date(2030, 6, 15), dt.date(2020, 1, 6)])
def test_taipei_base_decides_future_for_l1_card_and_kbar_alike(env, far_tpe):
    """資料日＝台北今日+1：L1(is_stale／age_days None)、卡片(as_of_future)、日 K(不畫) 三者判準一致（與 host 日無關）。"""
    env.tpe = far_tpe
    env.write(far_tpe + dt.timedelta(days=1))
    v = S.get_twii_trend_view(1)
    kv = S.get_twii_trend_view(5, with_ohlc=True)
    assert v.as_of_future is True and v.is_stale is True and v.age_days is None
    assert kv.as_of_future is True and kv.is_stale is True and kv.ohlc_ok is False


def test_injected_today_takes_priority_and_taipei_clock_not_read(env):
    env.write(BASE + dt.timedelta(days=1))
    v = S.get_twii_trend_view(1, today=BASE + dt.timedelta(days=1))
    assert env.tpe_calls == 0 and v.as_of_future is False
    kv = S.get_twii_trend_view(5, with_ohlc=True, today=BASE)
    assert env.tpe_calls == 0 and kv.as_of_future is True and kv.ohlc_ok is False


@pytest.mark.parametrize("with_ohlc", [False, True])
def test_clock_read_exactly_once_per_call_and_same_value_everywhere(env, monkeypatch, with_ohlc):
    """跨午夜情境：每次呼叫只取一次台北日（之後即使時鐘變了也不重取）；L1 與比對、日 K 驗證用同一個值。"""
    env.write(BASE)
    seen = []
    orig = OC.validate_ohlc_window

    def spy(*a, **k):
        seen.append(k.get("today"))
        return orig(*a, **k)
    monkeypatch.setattr(OC, "validate_ohlc_window", spy)
    v = S.get_twii_trend_view(5, with_ohlc=with_ohlc)
    assert env.tpe_calls == 1
    assert env.l1_today[-1][1] == BASE
    if with_ohlc:
        assert seen == [BASE]                                    # 日 K 驗證收到同一個基準
    assert v.as_of_future is False


# ════════════════════════════════════════════════════════════════════
# 6｜錯誤原因不混淆：新字串僅 future；其他 CONTRACT_ERROR 仍是「資料格式異常」
# ════════════════════════════════════════════════════════════════════
def _bad_fact_card_reason(**over):
    base = dict(ok=True, close=(100.0,), as_of="2026-11-16", is_stale=False, stale_reason="", age_days=1,
                has_upstream_error=False, error_type="", failed=False, source="s")
    base.update(over)
    fact = TwiiFact(**base)
    try:
        RC.validate_twii_fact(fact)
    except Exception as e:  # noqa: BLE001 — 模擬 feed 的接住
        snap = RealFeedSnapshot.of(None, RC.exception_code(e), None, "Exception")
        return RC.exception_code(e), _card(snap)["reason"]
    raise AssertionError("expected violation")


@pytest.mark.parametrize("over", [
    dict(close=(float("nan"),)), dict(close=(-1.0,)), dict(close=()), dict(as_of="not-a-date"),
    dict(is_stale=1), dict(age_days=-3), dict(upstream_state="bogus"), dict(ok=True, failed=True),
    dict(as_of_future="yes"),
])
def test_other_contract_errors_keep_format_text_and_never_show_future_text(over):
    code, reason = _bad_fact_card_reason(**over)
    assert code == RC.CONTRACT_ERROR
    assert reason == FORMAT_TEXT and FUTURE_TEXT not in reason and "不可信" not in reason


def test_future_flag_maps_to_dedicated_code_not_generic():
    code, reason = _bad_fact_card_reason(as_of="2026-11-18", as_of_future=True, is_stale=True, age_days=None)
    assert code == RC.FUTURE_AS_OF_ERROR and code != RC.CONTRACT_ERROR
    assert reason == FUTURE_TEXT and "格式異常" not in reason


def test_future_flag_ignored_when_not_ok():
    f = TwiiFact(False, (), None, None, "", None, False, "", False, "s", as_of_future=True)
    RC.validate_twii_fact(f)                                    # ok=False 不判（讀不到走既有「讀不到」灰態）


def test_kbar_unavailable_path_never_uses_future_text(env):
    env.write(BASE + dt.timedelta(days=3))
    snap = env.snapshot()
    assert FUTURE_TEXT not in repr(_kbar_field(snap))
    snap2 = RealFeedSnapshot.of(snap.twii, snap.twii_error, None, "Exception", kbar=None, kbar_error="OSError")
    assert FUTURE_TEXT not in repr(_kbar_field(snap2))


def test_new_string_defined_once_and_used_once_in_repo():
    """全 repo（非測試、非文件）新字串僅一處定義、`TWII_FUTURE_AS_OF_TEXT` 僅一處使用。"""
    lit_hits, name_hits = [], []
    for base in ("src", "shared"):
        for p in (ROOT / base).rglob("*.py"):
            t = p.read_text(encoding="utf-8")
            if FUTURE_TEXT in t:
                lit_hits.append(str(p.relative_to(ROOT)))
            for i, line in enumerate(t.splitlines(), 1):
                if "TWII_FUTURE_AS_OF_TEXT" in line:
                    name_hits.append((str(p.relative_to(ROOT)), i, line.strip()))
    for p in ROOT.glob("*.py"):
        assert FUTURE_TEXT not in p.read_text(encoding="utf-8")
    assert lit_hits == ["src/services/ui2/real_canonical.py"]
    defs = [h for h in name_hits if re.match(r"^TWII_FUTURE_AS_OF_TEXT\s*=", h[2])]
    uses = [h for h in name_hits if h not in defs and not h[2].lstrip().startswith(("#", "`"))]
    assert len(defs) == 1 and len(uses) == 1, name_hits
    assert "twii_card_spec" in (ROOT / "src/services/ui2/real_canonical.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("page", PAGE_IDS)
def test_new_string_not_on_any_page_for_non_future_snapshots(env, page, monkeypatch):
    """fresh／stale／FAULT／契約違反的 snapshot，四頁任何位置都不出現新字串。"""
    env.write(BASE - dt.timedelta(days=1))
    fresh = env.snapshot()
    stale = RealFeedSnapshot.of(dataclasses.replace(fresh.twii, is_stale=True, age_days=3), "", None, "Exception",
                                kbar=fresh.kbar)
    fault = RealFeedSnapshot.of(None, "OSError", None, "Exception")
    fmt = RealFeedSnapshot.of(None, RC.CONTRACT_ERROR, None, "Exception")
    for snap in (fresh, stale, fault, fmt):
        assert FUTURE_TEXT not in repr(get_real_page_vm(page, snap))
    env.write(BASE + dt.timedelta(days=1))                         # 正向對照：只有 future 才出現（且只在 📊 市場頁的台股卡）
    assert (FUTURE_TEXT in repr(get_real_page_vm(page, env.snapshot()))) is (page == P4_MARKET)


# ════════════════════════════════════════════════════════════════════
# 7｜feed 只逐欄拷貝；日 K 的 card_unavailable 語意不衝突
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("flag,err", [(True, RC.FUTURE_AS_OF_ERROR), (False, ""), (None, "")])
def test_feed_copies_as_of_future_verbatim(monkeypatch, flag, err):
    from src.services.market_twii_view_service import TwiiTrendView
    v = TwiiTrendView(ok=True, xs=("2026-11-16",), close=(100.0,), as_of="2026-11-16", is_stale=False, age_days=1,
                      as_of_future=flag)
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n, *, with_ohlc=False, today=None: v)
    fact, e = RF._read_twii()
    assert e == err
    assert (fact is None) == bool(err)
    if fact is not None:
        assert fact.as_of_future is flag


def test_kbar_card_unavailable_semantics_unchanged_when_card_is_future_unavailable(env):
    """卡片因 future 不可用（twii=None）時，即使日 K 事實自稱 ok，對帳仍走既有 card_unavailable → 不畫（不衝突、不誤判 mismatch）。"""
    env.write(BASE - dt.timedelta(days=1))
    fresh = env.snapshot()
    snap = RealFeedSnapshot.of(None, RC.FUTURE_AS_OF_ERROR, None, "Exception", kbar=fresh.kbar)
    assert RC.kbar_same_source_problem(fresh.kbar, None) == "card_unavailable"
    chart = RC.kbar_chart_spec(snap)
    assert chart["candles"] == [] and chart["field"]["reason"] == RC.KBAR_CARD_UNAVAILABLE_TEXT
    assert RC.kbar_same_source_problem(fresh.kbar, fresh.twii) == ""        # 正常對帳不受新欄位影響（as_of_future 不在對帳欄位內）
    assert RC.kbar_same_source_problem(fresh.kbar, dataclasses.replace(fresh.twii, as_of_future=None)) == ""
