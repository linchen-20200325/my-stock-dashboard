"""tests/test_macro_v2_tab.py — 總經 v2 分頁守衛（2026-08-25）

## 這些測試在守什麼

v2 分頁的**唯一價值主張**是「同一份資料，換一種誠實的呈現」。它有兩種
死法，兩種都不會讓畫面看起來壞掉，所以只能靠測試釘住：

1. **第二條取數路徑** —— 若 v2 自己從 session_state 抽值（而不是走
   `compute_five_bucket_summary` 的 readiness 側車），就會與舊分頁漂移：
   同一個指標在兩個分頁顯示不同數字，而且**兩邊看起來都很正常**。
   本檔守「v2 的值必須等於側車的值」。

2. **拿合成序列充當走勢** —— 16 盞燈裡多數沒有落地歷史序列。若哪天有人
   為了「版面完整」把假序列接上去，畫面會更好看而錯得更徹底（§1）。
   本檔守「宣稱可畫圖的指標必須真的拿得到序列」，且 VIX 這種沒序列的
   必須留在純數值卡。

⚠️ 本檔只測 L1 讀檔 + L2/L5 純轉換，**不啟動 Streamlit runtime**。
"""
from __future__ import annotations

import pytest

from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    CL_INTL_KEY_DXY,
    SPECS_BY_KEY,
    classify_danger,
)
from src.compute.macro.macro_helpers import compute_five_bucket_summary


def _readiness(**kw) -> dict:
    rd: dict = {}
    compute_five_bucket_summary(readiness_out=rd, **kw)
    return rd


# ════════════════════════════════════════════════════════════════
# 一、readiness 側車的 value 欄（v2 取數的唯一來源）
# ════════════════════════════════════════════════════════════════
class TestReadinessCarriesValue:

    def test_every_light_has_the_field(self):
        """16 盞燈全部要帶 value —— 漏一盞，消費端就得寫 .get() 猜。"""
        rd = _readiness()
        missing = [k for k, v in rd.items() if "value" not in v]
        assert not missing, f"readiness 缺 value 欄:{missing}"
        assert len(rd) == len(BUCKET_DANGER_SPECS) == 16

    def test_empty_input_yields_all_none(self):
        """§1:沒資料就是 None，不代任何預設值。"""
        rd = _readiness()
        assert all(v["value"] is None for v in rd.values())
        assert all(v["state"] == "missing" for v in rd.values())

    def test_value_is_the_resolved_number(self):
        """有值時，side-car 的 value 必須就是取數解析出的那個數。"""
        rd = _readiness(
            macro_info={"vix": {"current": 19.4}, "ism_pmi": {"value": 48.6}},
            warroom_summary={"health_score": 52.0},
        )
        assert rd["vix"]["value"] == pytest.approx(19.4)
        assert rd["ism_pmi"]["value"] == pytest.approx(48.6)
        assert rd["health"]["value"] == pytest.approx(52.0)
        assert rd["vix"]["state"] == "ok"

    def test_unwired_stays_none(self):
        """wired=False 的燈永遠沒有值 —— 就算上游硬塞也一樣。"""
        rd = _readiness()
        assert rd["foreign_net"]["wired"] is False
        assert rd["foreign_net"]["value"] is None

    def test_out_of_range_is_rejected_not_clamped(self):
        """§3.2:超出合理範圍的值要被擋成 None，**不是**夾到邊界。

        夾邊界會讓「上游換了標的」這件事變得看不見（DXY→UUP 那類事故）。

        目前只有 us10y / dxy 設了 valid range —— 它們的上游 fallback 最會換
        標的（DXY→UUP、^TNX 殖利率×10）。兩者的取數容器不同，所以各自有
        餵法。**有設範圍卻沒有餵法的 spec 會讓本測試直接紅** —— 這樣新增
        範圍守衛時就一定會被逼著補一筆，不會出現「設了範圍但從沒被驗過」。
        """
        ranged = [s for s in BUCKET_DANGER_SPECS if s.valid_max is not None]
        assert ranged, "沒有任何 spec 設 valid range —— §3.2 的範圍守衛整組失效了"

        def _feed_macro_info(key, value):      # macro_info.<key>.current
            return {"macro_info": {key: {"current": value}}}

        def _feed_intl_df(intl_key, value):    # cl_data.intl[<中文名>] 末列 Close
            pd = pytest.importorskip("pandas")
            return {"cl_data": {"intl": {intl_key: pd.DataFrame({"Close": [value]})}}}

        _FEED = {
            "us10y": lambda v: _feed_macro_info("us10y", v),
            "dxy": lambda v: _feed_intl_df(CL_INTL_KEY_DXY, v),
        }
        no_feed = [s.key for s in ranged if s.key not in _FEED]
        assert not no_feed, (
            f"這些 spec 設了 valid range 卻沒有對應的測試餵法:{no_feed}。"
            f"請在 _FEED 補一筆，否則那道範圍守衛從來沒被驗證過。"
        )

        for spec in ranged:
            rd = _readiness(**_FEED[spec.key](spec.valid_max + 500))
            assert rd[spec.key]["value"] is None, f"{spec.key} 超範圍的值沒被擋下"
            assert rd[spec.key]["reason"] == "out_of_range", (
                f"{spec.key} 被擋下的原因記成 {rd[spec.key]['reason']!r}，"
                f"應為 out_of_range —— 記成 no_value 會讓「上游換標的」"
                f"被誤診成「上游沒回值」，處置完全不同。"
            )


# ════════════════════════════════════════════════════════════════
# 二、v2 不得有第二條取數路徑
# ════════════════════════════════════════════════════════════════
class TestNoSecondDataPath:

    def test_rows_mirror_the_sidecar_exactly(self):
        """build_rows 的值必須逐一等於側車的值，不多不少不加工。"""
        from src.ui.tabs.tab_macro_v2 import build_rows
        rd = _readiness(
            macro_info={"vix": {"current": 19.4}, "ism_pmi": {"value": 48.6}},
            warroom_summary={"health_score": 52.0},
        )
        rows = build_rows(rd)
        assert len(rows) == 16
        for r in rows:
            assert r.value == rd[r.key]["value"], f"{r.key} 的值與側車不同"

    def test_band_uses_upstream_classifier(self):
        """判燈必須是上游 classify_danger 的結果，不是 v2 自己重寫的一套。"""
        from src.ui.tabs.tab_macro_v2 import build_rows
        rd = _readiness(
            macro_info={"vix": {"current": 19.4}},
            warroom_summary={"health_score": 52.0},
        )
        for r in build_rows(rd):
            assert r.band == classify_danger(r.value, SPECS_BY_KEY[r.key]), (
                f"{r.key} 判燈與上游 classify_danger 不一致"
            )

    def test_tab_does_not_read_session_state_for_values(self):
        """靜態守衛:v2 檔內不得出現直接從 session_state 取指標值的樣子。

        允許 `load_section_inputs(st.session_state)`（那是 L3 adapter，
        與舊分頁同一條路），但不允許自己 `st.session_state['macro_info']`。
        """
        import pathlib
        src = pathlib.Path("src/ui/tabs/tab_macro_v2.py").read_text(encoding='utf-8')
        for bad in ("st.session_state[", "st.session_state.get("):
            assert bad not in src, (
                f"tab_macro_v2 出現 `{bad}` —— 那是第二條取數路徑，"
                f"會與舊分頁漂移。值一律從 readiness 側車取。"
            )


# ════════════════════════════════════════════════════════════════
# 三、不得拿合成序列充當走勢（§1）
# ════════════════════════════════════════════════════════════════
class TestChartsUseRealSeriesOnly:

    def test_declared_chart_keys_are_real_specs(self):
        from src.ui.tabs.tab_macro_v2 import _CHART_SPECS, _VALUE_CARD_KEYS
        for key, kind, note in _CHART_SPECS:
            assert key in SPECS_BY_KEY, f"{key} 不是有效的 DangerSpec key"
            assert kind in ("parquet", "session")
            assert note.strip(), f"{key} 沒寫序列說明"
        for key in _VALUE_CARD_KEYS:
            assert key in SPECS_BY_KEY

    def test_chart_and_value_cards_do_not_overlap(self):
        """同一個指標不能又畫圖又當純數值卡 —— 那就是同一資訊重複兩次。"""
        from src.ui.tabs.tab_macro_v2 import _CHART_SPECS, _VALUE_CARD_KEYS
        chart_keys = {k for k, _, _ in _CHART_SPECS}
        assert not (chart_keys & set(_VALUE_CARD_KEYS))

    def test_vix_stays_a_value_card(self):
        """VIX 沒有任何落地歷史序列。它若跑進圖表名單，必定是有人接了假序列。

        （2026-08-25 盤點:vix / 台灣 PMI / jingqi / news_systemic 完全查無序列。）
        """
        from src.ui.tabs.tab_macro_v2 import _CHART_SPECS, _VALUE_CARD_KEYS
        assert "vix" in _VALUE_CARD_KEYS
        assert "vix" not in {k for k, _, _ in _CHART_SPECS}

    def test_parquet_series_are_actually_loadable(self):
        """宣稱走 parquet 的指標，必須真的從本地快取讀得到序列。

        讀不到就該從 `_CHART_SPECS` 拿掉改成數值卡，而不是留一張空圖。
        """
        from src.data.macro.macro_cache_reader import load_v2_chart_series
        from src.ui.tabs.tab_macro_v2 import _CHART_SPECS

        declared = {k for k, kind, _ in _CHART_SPECS if kind == "parquet"}
        if not declared:
            pytest.skip("目前沒有宣告走 parquet 的圖表指標")
        got = load_v2_chart_series()
        missing = declared - set(got)
        assert not missing, (
            f"這些指標宣稱有 parquet 長序列但實際讀不到:{sorted(missing)}。"
            f"§1:不要留空圖，請改列進 _VALUE_CARD_KEYS。"
        )
        for k in declared:
            assert len(got[k]) > 0, f"{k} 序列是空的"

    def test_margin_series_is_in_yi_not_yuan(self):
        """§4.1 量綱:融資餘額門檻是「億」，parquet 原欄是「元」。

        沒換算的話圖會畫在 1e11 量級、門檻線縮成一條貼地的線 —— 看起來
        「有畫圖」但完全讀不出訊息。這是最容易無聲發生的錯。
        """
        from src.data.macro.macro_cache_reader import load_v2_chart_series
        got = load_v2_chart_series()
        if "margin" not in got:
            pytest.skip("本機無 finmind_margin.parquet")
        latest = float(got["margin"].iloc[-1])
        spec = SPECS_BY_KEY["margin"]
        # 億級應與門檻同數量級（門檻 2500/3400 億）；元級會是 1e11 量級
        assert 100 < latest < 100_000, (
            f"margin 序列最新值 {latest:,.0f} 不在「億」的合理量級 —— "
            f"對照門檻 黃{spec.yellow}/紅{spec.red}（億）。可能漏了元→億換算。"
        )

    def test_bias_240_series_is_percent(self):
        """bias_240 的單位是 %，不是價格也不是比值。"""
        from src.data.macro.macro_cache_reader import load_v2_chart_series
        got = load_v2_chart_series()
        if "bias_240" not in got:
            pytest.skip("本機無 twii_ohlcv.parquet")
        s = got["bias_240"]
        assert SPECS_BY_KEY["bias_240"].unit == "%"
        # 乖離率歷史上不會超過 ±100%（那是價格翻倍/歸零等級）
        assert s.abs().max() < 100, f"bias_240 值域異常，最大 {s.abs().max():.1f}"


# ════════════════════════════════════════════════════════════════
# 四、四態必須各自可辨（v2 的主要價值）
# ════════════════════════════════════════════════════════════════
class TestFourStatesAreDistinguishable:

    def test_unwired_and_degraded_are_not_conflated(self):
        """`未接線` 與 `門檻已失準` 是兩種完全不同的「別信這盞燈」。"""
        from src.ui.tabs.tab_macro_v2 import build_rows
        rows = {r.key: r for r in build_rows(_readiness())}
        assert rows["foreign_net"].state == "unwired"
        assert rows["margin"].state == "degraded"

    def test_degraded_light_still_shows_a_value_when_available(self):
        """§ 與 wired 的關鍵差異:門檻失準的燈**照常有值、照常亮**。"""
        from src.ui.tabs.tab_macro_v2 import build_rows
        rd = _readiness(cl_data={"margin": 5148.0})
        row = {r.key: r for r in build_rows(rd)}["margin"]
        assert row.state == "degraded"
        assert row.value == pytest.approx(5148.0)
        assert row.band != "gray", "有值就該判燈，degraded 不影響判燈"

    def test_missing_carries_an_actionable_reason(self):
        """無資料的燈必須說得出「該做什麼」，否則等於沒講。"""
        from src.ui.tabs.tab_macro_v2 import _REASON_TXT, build_rows
        rows = build_rows(_readiness())
        for r in rows:
            if r.state == "missing":
                assert r.reason in _REASON_TXT, (
                    f"{r.key} 的缺值原因 {r.reason!r} 沒有對應文案"
                )

    def test_live_requires_an_actual_value(self):
        """不得把「無資料」畫成運作中。"""
        from src.ui.tabs.tab_macro_v2 import build_rows
        for r in build_rows(_readiness()):
            assert r.state != "live", f"{r.key} 全空輸入下不該是 live"


# ════════════════════════════════════════════════════════════════
# 五、rollup 與舊分頁同語意
# ════════════════════════════════════════════════════════════════
class TestRollupMatchesLegacy:

    def test_verdict_is_worst_of_buckets(self):
        from src.ui.tabs.tab_macro_v2 import overall_verdict
        assert overall_verdict([])[0] == "gray"
        assert overall_verdict([{"band": "green", "name": "長期"},
                                {"band": "red", "name": "籌碼"}])[0] == "red"
        assert overall_verdict([{"band": "green", "name": "長期"},
                                {"band": "yellow", "name": "中期"}])[0] == "yellow"

    def test_gray_buckets_do_not_count_as_green(self):
        """§1:全部無資料時不得顯示綠燈。"""
        from src.ui.tabs.tab_macro_v2 import bucket_summary, overall_verdict
        summ = bucket_summary(
            __import__("src.ui.tabs.tab_macro_v2", fromlist=["build_rows"])
            .build_rows(_readiness()))
        assert all(b["band"] == "gray" for b in summ)
        assert overall_verdict(summ)[0] == "gray"

    def test_every_bucket_appears(self):
        from src.ui.tabs.tab_macro_v2 import bucket_summary, build_rows
        summ = bucket_summary(build_rows(_readiness()))
        assert [b["name"] for b in summ] == ["長期", "中期", "短線急殺", "籌碼", "新聞"]
        assert sum(b["n"] for b in summ) == 16
