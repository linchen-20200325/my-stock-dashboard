"""決策燈 readiness 守衛（2026-08-20）。

## 這個設計的價值全在這幾條測試

`MACRO_INFO_KEYS`（6 個）與 `BUCKET_DANGER_SPECS`（16 盞）的差集之所以能存活到
今天，不是因為沒人看得出來，而是因為**沒有任何機制會因為它而變紅**。

readiness 側車本身只是把資訊算出來；真正防止它三個月後退化成第四份手寫清單的，
是下面這幾條會在 CI 紅燈的斷言。

## 為什麼是「消費端宣告」而不是「生產端自報」

因為**消費端的失效模式可以機械驗證，生產端的不行**：

- 消費端漏接 → `spec 集合 != 取值集合` → 一條 assert 抓到
- 生產端漏掛裝飾器 → 它從一開始就不在聯集裡，沒有東西會缺席

實例：`us10y` 自 v18.286 註冊、v19.175 才接線，中間 4 個版本永久灰燈，
而上游 `fetch_us10y_block` **全程抓取成功** —— 沒有任何生產端能回報這種病。
"""
from __future__ import annotations

import pandas as pd
import pytest

from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    MISSING_NOT_LOADED,
    MISSING_NOT_WIRED,
    MISSING_NO_EXTRACTION,
    MISSING_NO_VALUE,
    MISSING_OUT_OF_RANGE,
    SPECS_BY_KEY,
)
from src.compute.macro import compute_five_bucket_summary


def _readiness(**kw) -> dict:
    rd: dict = {}
    compute_five_bucket_summary(readiness_out=rd, **kw)
    return rd


class TestEverySpecHasExtraction:
    """spec 註冊了卻沒人寫取值 → 永久灰燈，而且沒有任何上游會報錯。"""

    def test_no_spec_is_missing_extraction(self):
        rd = _readiness()
        orphans = [k for k, r in rd.items() if r["reason"] == MISSING_NO_EXTRACTION]
        assert not orphans, (
            f"這些 spec 註冊了但 values dict 沒有取值：{orphans}。"
            f"它們會是永久灰燈，而上游可能一直抓得好好的（us10y 病了 4 個版本的形狀）。")

    def test_readiness_covers_every_spec_exactly_once(self):
        rd = _readiness()
        assert set(rd) == {s.key for s in BUCKET_DANGER_SPECS}
        assert len(rd) == len(BUCKET_DANGER_SPECS) == 16


class TestUnwiredMustDeclareReason:
    """刻意不接可以，靜默不接不行。"""

    def test_unwired_specs_have_named_reason(self):
        for s in BUCKET_DANGER_SPECS:
            if not s.wired:
                assert s.unwired_reason.strip(), (
                    f"{s.key} 標記 wired=False 但沒填 unwired_reason —— "
                    f"使用者會看到一盞永遠不亮的燈而不知道為什麼")

    def test_unwired_reported_as_not_wired_not_as_failure(self):
        """未接線**不是抓取失敗**。混為一談會讓使用者去修一個沒壞的東西。"""
        rd = _readiness()
        for s in BUCKET_DANGER_SPECS:
            if not s.wired:
                assert rd[s.key]["reason"] == MISSING_NOT_WIRED, (
                    f"{s.key} 未接線卻被報成 {rd[s.key]['reason']}")

    def test_foreign_net_stays_unwired(self):
        """釘住現況：`foreign_net` 在 FinMind 單位確認前不得接上（§4.1）。

        這條不是說它永遠不能接，是說**接上時必須同時改這裡**，
        讓「單位已確認」這個決定被看見，而不是靜靜地把 wired 翻成 True。
        """
        assert SPECS_BY_KEY["foreign_net"].wired is False


class TestWiredSpecsDeclareUpstream:
    """每盞已接線的燈都要說得出自己的上游 —— 否則診斷給不出排查方向。"""

    def test_every_wired_spec_has_candidates(self):
        rd = _readiness()
        naked = [k for k, r in rd.items()
                 if r["wired"] and not r["candidates"]]
        assert not naked, f"這些燈沒有宣告任何上游候選源：{naked}"


class TestReasonsAreDiscriminated:
    """五種灰燈長得一樣，處置完全不同 —— 這是整個設計的目的。"""

    def test_container_absent_is_not_loaded(self):
        """容器不在 → 按更新就會好。"""
        rd = _readiness()
        assert rd["m1b_m2_gap"]["reason"] == MISSING_NOT_LOADED

    def test_container_present_but_empty_is_no_value(self):
        """容器在、欄位空 → 上游那一源失敗，按更新不會好。"""
        rd = _readiness(macro_info={"ism_pmi": {}})
        assert rd["ism_pmi"]["reason"] == MISSING_NO_VALUE

    def test_out_of_range_is_distinguished_and_names_the_value(self):
        """最毒的一種：有值、數字看起來正常、但尺度錯。

        `^TNX` 回 46.3 是殖利率 ×10 的報價慣例。若不擋，會直接觸發最高等級
        危險燈 —— 一個純粹由上游慣例造成的假警報。
        """
        rd = _readiness(cl_data={"intl": {"10Y公債殖利率": pd.DataFrame({"close": [46.3]})}})
        r = rd["us10y"]
        assert r["reason"] == MISSING_OUT_OF_RANGE
        assert r["rejected"], "被擋下卻沒記錄是哪個源、什麼值 → 使用者無從排查"
        _lbl, _v, _why = r["rejected"][0]
        assert _v == pytest.approx(46.3)
        assert "out_of_range" in _why

    def test_ok_records_which_source_won(self):
        """多源賽跑命中哪一源必須記下來 —— 否則不知道現在用的是主源還是備援。"""
        rd = _readiness(macro_info={"vix": {"current": 17.2}})
        assert rd["vix"]["state"] == "ok"
        assert rd["vix"]["hit_source"], "命中了卻沒記來源"


class TestNoBehaviourShift:
    """readiness 是側車 —— 不傳就完全不影響既有 caller。"""

    def test_not_passing_readiness_out_is_safe(self):
        out = compute_five_bucket_summary()
        assert set(out) == {"long", "mid", "short", "chips", "news"}

    def test_lights_identical_with_and_without_readiness(self):
        """有沒有傳側車，16 盞燈的結論必須逐位相同。"""
        fixture = dict(
            macro_info={"vix": {"current": 17.2}, "ism_pmi": {"value": 52.4}},
            cl_data={"margin": 2480.0},
        )
        a = compute_five_bucket_summary(**fixture)
        rd: dict = {}
        b = compute_five_bucket_summary(**fixture, readiness_out=rd)
        flat = lambda o: [(d["key"], d["value_str"], d["danger"])  # noqa: E731
                          for bk in o.values() for d in bk["details"]]
        assert flat(a) == flat(b), "傳了 readiness_out 之後燈號變了 —— 側車不該有副作用"
        assert len(rd) == 16


class TestCoverageRowUsesReadiness:
    """行為面：診斷頁那一列真的改讀決策燈了。"""

    @staticmethod
    def _macro_row(**session):
        import streamlit as st
        from src.ui.pages.data_coverage import compute_tab_coverage
        for k, v in session.items():
            st.session_state[k] = v
        return [r for r in compute_tab_coverage() if "總經" in r["tab"]][0]

    def test_denominator_excludes_unwired(self):
        """分母不含刻意未接線者 —— 恆亮的警告等於沒有警告。"""
        row = self._macro_row(macro_info={"vix": {"current": 17.2}, "_loaded_at": "2026-08-20T01:00"})
        n_wired = sum(1 for s in BUCKET_DANGER_SPECS if s.wired)
        assert row["ratio_txt"].endswith(f"/{n_wired}"), (
            f"分母應為已接線的 {n_wired} 盞，實際 {row['ratio_txt']}")

    def test_detail_names_the_out_of_range_value(self):
        row = self._macro_row(
            macro_info={"vix": {"current": 17.2}, "_loaded_at": "2026-08-20T01:00"},
            cl_data={"intl": {"10Y公債殖利率": pd.DataFrame({"close": [46.3]})}},
        )
        assert "46.3" in row["detail"], "量綱異常沒把實際值講出來，使用者無從判斷"

    def test_detail_surfaces_mkt_missing_factors(self):
        """`market_regime` 早就在算 `missing_factors`，只是沒人讀。"""
        row = self._macro_row(
            macro_info={"vix": {"current": 17.2}, "_loaded_at": "2026-08-20T01:00"},
            mkt_info={"missing_factors": ["市場廣度"]},
        )
        assert "市場廣度" in row["detail"]
