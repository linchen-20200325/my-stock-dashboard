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
        """`未接線` 與 `門檻已失準` 是兩種完全不同的「別信這盞燈」。

        ⚠️ 2026-08-26:原本這裡餵的是**空的** `_readiness()`,卻期待 margin 是
        degraded —— 那正是本次修掉的 bug(判定順序與 L0 SSOT 相反,沒值也被印成
        「門檻已失準」)。degraded 的前提是**有值**,所以要驗 degraded 就得先餵值。
        「沒值 + discriminative=False」該是什麼,由
        `TestFourStateOrderMatchesL0SSOT` 那一組負責釘。
        """
        from src.ui.tabs.tab_macro_v2 import build_rows
        rows = {r.key: r for r in build_rows(_readiness(cl_data={"margin": 5148.0}))}
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
# 四之二、四態的**判定順序**必須與 L0 SSOT 一致（2026-08-26）
#
# `build_rows()` 判四態的順序,在 2026-08-26 前是
#   wired → discriminative → live → missing
# 而 L0 SSOT `shared.station_specs.classify_state()` 是
#   wired → 沒值 → discriminative → live
# 兩者在「**沒值 + discriminative=False**」這一格結論相反:舊碼印
# 「🟠 門檻已失準」,SSOT 說「▨ 無資料」。實際受害者是融資餘額(margin)——
# 它 discriminative=False,沒抓到值時畫面卻寫「門檻已失準」,使用者讀成
# 「有值,只是別太當真」,而事實是根本沒有值(§1:錯的敘述比沒有敘述更危險)。
#
# 這一格不會讓畫面看起來壞掉,所以只能靠測試釘住。
# ⚠️ `build_rows` **刻意複製**了 SSOT 的順序而非呼叫它(型別不同,理由見該處
#    註解),所以這裡另外加一條交叉比對:哪天有人只改了一邊,這組就紅。
# ════════════════════════════════════════════════════════════════
class TestFourStateOrderMatchesL0SSOT:

    #: 這盞燈 discriminative=False（門檻已失準），是本組的主角。
    _DEGRADED_KEY = "margin"
    #: 這盞燈 wired=False（決策端刻意沒接）。
    _UNWIRED_KEY = "foreign_net"

    def test_the_fixture_keys_still_have_the_flags_this_class_assumes(self):
        """先確認前提還成立 —— 上游把旗標翻回 True 時，本組要當場紅，
        而不是安靜地變成一組驗不到東西的測試。"""
        assert SPECS_BY_KEY[self._DEGRADED_KEY].discriminative is False
        assert SPECS_BY_KEY[self._DEGRADED_KEY].wired is True
        assert SPECS_BY_KEY[self._UNWIRED_KEY].wired is False

    # ── 四態各一 ────────────────────────────────────────────────
    def test_unwired(self):
        from src.ui.tabs.tab_macro_v2 import build_rows
        rows = {r.key: r for r in build_rows(_readiness())}
        assert rows[self._UNWIRED_KEY].state == "unwired"

    def test_missing(self):
        """一般（discriminative=True）的燈沒值 → missing。"""
        from src.ui.tabs.tab_macro_v2 import build_rows
        rows = {r.key: r for r in build_rows(_readiness())}
        assert rows["ndc_signal"].state == "missing"
        assert rows["ndc_signal"].value is None

    def test_degraded_requires_a_value(self):
        """discriminative=False **且有值** → degraded（燈照亮，只是別照門檻讀）。"""
        from src.ui.tabs.tab_macro_v2 import build_rows
        row = {r.key: r for r in
               build_rows(_readiness(cl_data={"margin": 5148.0}))}[self._DEGRADED_KEY]
        assert row.state == "degraded"
        assert row.value == pytest.approx(5148.0)

    def test_live(self):
        from src.ui.tabs.tab_macro_v2 import build_rows
        rows = {r.key: r for r in
                build_rows(_readiness(macro_info={"vix": {"current": 19.4}}))}
        assert rows["vix"].state == "live"

    # ── 本次修正的核心：順序 ────────────────────────────────────
    def test_no_value_beats_not_discriminative(self):
        """**沒值 + discriminative=False → missing（不是 degraded）。**

        對齊 L0 SSOT 的 `classify_state`（姊妹守衛：
        `tests/test_station_light_cells.py::test_no_value_beats_not_discriminative`）。
        degraded 的語意是「有值，但門檻失準」—— 一個值都沒有時，「門檻準不準」
        是個沒有意義的問題，先判 degraded 會讓畫面對著空資料說「門檻已失準」。

        ⚠️ 把 `build_rows` 的順序改回「discriminative 先判」，這條會轉紅。
        """
        from src.ui.tabs.tab_macro_v2 import build_rows
        row = {r.key: r for r in build_rows(_readiness())}[self._DEGRADED_KEY]
        assert row.value is None, "前提:全空輸入下這盞燈本來就沒有值"
        assert row.state == "missing", (
            f"{self._DEGRADED_KEY} 沒有值卻被判成 {row.state!r} —— "
            f"對著空資料印「門檻已失準」會被讀成「有值只是別太當真」"
        )

    def test_missing_light_never_shows_the_degraded_wording(self):
        """換句話說的同一件事:任何 state=missing 的列，畫面文案不得是「門檻已失準」。"""
        from src.ui.render.macro_v2_cards import STATE_META
        from src.ui.tabs.tab_macro_v2 import build_rows
        for r in build_rows(_readiness()):
            if r.state == "missing":
                assert STATE_META[r.state][0] == "無資料", (
                    f"{r.key} 沒資料卻被標成 {STATE_META[r.state][0]!r}"
                )

    # ── 兩份順序不得漂移 ────────────────────────────────────────
    def test_order_agrees_with_station_specs_classify_state(self):
        """`build_rows` 複製了 L0 的順序（型別不同無法直接呼叫）——
        這條交叉比對兩邊：只改一邊就紅。

        `classify_state` 讀的是 `StationSpec` 的旗標，這裡用合成 spec 把
        `build_rows` 實際看到的 `wired` / `discriminative` / 有沒有值餵進去，
        比對兩邊對同一組輸入是否給出同一個四態。
        """
        from shared.station_specs import StationSpec, classify_state
        from src.ui.tabs.tab_macro_v2 import build_rows

        # ⚠️ 兩份輸入缺一不可:第一份讓 margin **有值**(→ degraded)，第二份讓它
        #    **沒值**(→ missing)。兩份順序真正分岔的就是後者那一格，只跑第一份
        #    的話，這條交叉比對在順序被改回去時仍然是綠的（實測過）。
        seen: set[str] = set()
        for rd in (_readiness(macro_info={"vix": {"current": 19.4}},
                              cl_data={"margin": 5148.0}),
                   _readiness(macro_info={"vix": {"current": 19.4}})):
            for r in build_rows(rd):
                rec = rd[r.key]
                ghost = StationSpec(
                    key=r.key, label=r.label, kind="both", group="macro",
                    unit=r.unit, direction="high_bad", threshold_text="—",
                    source="—", why="—",
                    wired=bool(rec.get("wired", True)),
                    unwired_reason="x",
                    discriminative=bool(rec.get("discriminative", True)),
                    degraded_reason="x",
                )
                has_value = rec.get("state") == "ok" and rec.get("value") is not None
                assert r.state == classify_state(ghost, has_value=has_value), (
                    f"{r.key}:tab_macro_v2 判 {r.state!r}，L0 SSOT 判 "
                    f"{classify_state(ghost, has_value=has_value)!r} —— 兩份順序漂移了"
                )
                seen.add(r.state)
        # 這兩份輸入必須真的走過四態，否則上面那圈等於沒驗到分歧點
        assert {"live", "degraded", "unwired", "missing"} <= seen, seen


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


# ════════════════════════════════════════════════════════════════
# 六、第 3 層篩選（搜尋框 + 分類 chip，2026-08-26）
#
# 這一組守的東西只有一個核心:**畫面說 A、內容不能是 B**。
# `st.dataframe(on_select=...)` 回的 `selection.rows` 是「畫面上那張表的列序」,
# 一旦有了篩選就不再等於 `build_rows()` 的原始 16 列序。拿錯清單去索引,
# 右側面板會安靜地顯示另一個指標的值與門檻 —— 兩邊看起來都很正常(§1)。
# 其餘(搜尋 / 各 chip / 0 筆文案)是同一組篩選的邊界。
# ════════════════════════════════════════════════════════════════

def _mixed() -> dict:
    """一份四態齊備的 readiness:綠燈 live / 紅燈 live / unwired / degraded / missing。

    `is_problem` 的正反例、以及「篩選後列序 ≠ 原始列序」都靠它撐起來。
    """
    return _readiness(
        macro_info={"vix": {"current": 38.0},      # 紅燈 + live（市場有問題）
                    "ism_pmi": {"value": 58.0}},   # 綠燈 + live（都沒問題）
        warroom_summary={"health_score": 88.0},    # 綠燈 + live
        # degraded 的前提是**有值**（門檻失準 ≠ 沒資料）。2026-08-26 前這裡沒餵
        # margin，卻靠當時「discriminative 先判」的錯誤順序湊出 degraded ——
        # 順序修正後那個 degraded 就不存在了，故改成餵真值。
        cl_data={"margin": 5148.0},                # 紅燈 + degraded（門檻已失準）
    )


class TestLayer3Filtering:

    # ── 搜尋框 ───────────────────────────────────────────────────
    def test_search_hits_by_substring(self):
        from src.ui.tabs.tab_macro_v2 import build_rows, filter_rows
        rows = build_rows(_mixed())
        got = {r.key for r in filter_rows(rows, query="融資")}
        assert got == {"margin"}, "設計稿 placeholder 明寫「例如 VIX、融資」"

    def test_search_is_case_insensitive(self):
        from src.ui.tabs.tab_macro_v2 import build_rows, filter_rows
        rows = build_rows(_mixed())
        lower = {r.key for r in filter_rows(rows, query="vix")}
        upper = {r.key for r in filter_rows(rows, query="VIX")}
        assert lower == upper == {"vix"}

    def test_search_miss_yields_empty_not_everything(self):
        """查無此指標要回空 —— 回全部等於默默把搜尋當成沒打(§1)。"""
        from src.ui.tabs.tab_macro_v2 import build_rows, filter_rows
        rows = build_rows(_mixed())
        assert filter_rows(rows, query="這個指標不存在") == []

    def test_blank_query_shows_everything(self):
        """空字串 / 純空白 = 沒在搜尋,不是「查無此指標」。"""
        from src.ui.tabs.tab_macro_v2 import build_rows, filter_rows
        rows = build_rows(_mixed())
        assert len(filter_rows(rows, query="")) == len(rows) == 16
        assert len(filter_rows(rows, query="   ")) == 16

    def test_search_matches_label_not_internal_key(self):
        """只比對畫面上看得到的指標名,不比對內部 key(`ism_pmi` 那類)。"""
        from src.ui.tabs.tab_macro_v2 import build_rows, filter_rows
        rows = build_rows(_mixed())
        assert filter_rows(rows, query="ism_pmi") == []
        assert {r.key for r in filter_rows(rows, query="PMI")} == {"ism_pmi"}

    # ── 分類 chip ────────────────────────────────────────────────
    def test_seven_chips_and_bucket_names_come_from_the_existing_ssot(self):
        """7 個 chip;5 個桶名與順序**沿用既有常數**,不是另抄一份中文字串。"""
        from src.ui.tabs.tab_macro_v2 import (
            _BUCKET_ORDER,
            _BUCKET_ZH,
            _CHIP_ALL,
            _CHIP_PROBLEM,
            CHIP_LABELS,
            CHIP_ORDER,
        )
        assert len(CHIP_ORDER) == len(CHIP_LABELS) == 7
        assert CHIP_ORDER[:2] == [_CHIP_ALL, _CHIP_PROBLEM]
        assert CHIP_ORDER[2:] == _BUCKET_ORDER, "桶順序沒沿用 _BUCKET_ORDER"
        for b in _BUCKET_ORDER:
            assert CHIP_LABELS[b] == _BUCKET_ZH[b], (
                f"chip 的「{b}」桶名與 _BUCKET_ZH 不同 —— 兩把尺已經漂移了"
            )

    @pytest.mark.parametrize("bucket", ["long", "mid", "short", "chips", "news"])
    def test_each_bucket_chip_filters_to_that_bucket(self, bucket):
        from src.ui.tabs.tab_macro_v2 import build_rows, filter_rows
        rows = build_rows(_mixed())
        got = filter_rows(rows, chip=bucket)
        assert got, f"{bucket} 桶篩出 0 筆 —— 16 盞燈每桶都該有成員"
        assert all(r.bucket == bucket for r in got)
        assert len(got) == sum(1 for r in rows if r.bucket == bucket)

    def test_all_chip_filters_nothing(self):
        from src.ui.tabs.tab_macro_v2 import _CHIP_ALL, build_rows, filter_rows
        rows = build_rows(_mixed())
        assert [r.key for r in filter_rows(rows, chip=_CHIP_ALL)] == \
            [r.key for r in rows]

    def test_unknown_chip_raises(self):
        """§1:未知 chip 若默默回傳全部,畫面會長得跟「全部」一模一樣。"""
        from src.ui.tabs.tab_macro_v2 import build_rows, filter_rows
        with pytest.raises(ValueError, match="未知的篩選 chip"):
            filter_rows(build_rows(_mixed()), chip="長期")   # 傳了顯示名而非 key

    def test_chip_and_query_are_anded(self):
        from src.ui.tabs.tab_macro_v2 import build_rows, filter_rows
        rows = build_rows(_mixed())
        assert {r.key for r in filter_rows(rows, chip="short", query="VIX")} \
            == {"vix"}
        # VIX 在 short 桶,拿去跟 chips 桶 AND 就該是空的
        assert filter_rows(rows, chip="chips", query="VIX") == []

    # ── 「只看有問題的」 ─────────────────────────────────────────
    def test_problem_chip_is_the_union_of_market_and_system(self):
        """定義:黃/紅燈(市場有問題) ∪ state != live(系統有問題)。

        反例(**不該**入選)必須是「綠燈且 live」—— 只有這種才是真的沒事。
        """
        from src.ui.tabs.tab_macro_v2 import (
            _CHIP_PROBLEM,
            build_rows,
            filter_rows,
            is_problem,
        )
        rows = {r.key: r for r in build_rows(_mixed())}

        # 正例 1｜市場有問題:紅燈但一切正常運作
        assert rows["vix"].band == "red" and rows["vix"].state == "live"
        assert is_problem(rows["vix"])
        # 正例 2｜系統有問題:未接線(不是市場的錯,但它永遠不會亮)
        assert rows["foreign_net"].state == "unwired"
        assert is_problem(rows["foreign_net"])
        # 正例 3｜系統有問題:門檻已失準
        assert rows["margin"].state == "degraded"
        assert is_problem(rows["margin"])
        # 正例 4｜系統有問題:無資料
        assert rows["ndc_signal"].state == "missing"
        assert is_problem(rows["ndc_signal"])
        # 反例｜綠燈 + live = 真的沒事
        for k in ("health", "ism_pmi"):
            assert rows[k].band == "green" and rows[k].state == "live"
            assert not is_problem(rows[k])

        picked = {r.key for r in filter_rows(list(rows.values()),
                                             chip=_CHIP_PROBLEM)}
        assert "health" not in picked and "ism_pmi" not in picked
        assert {"vix", "foreign_net", "margin", "ndc_signal"} <= picked

    def test_unwired_light_is_never_hidden_by_the_problem_chip(self):
        """把「未接線」藏起來 = 使用者按了 chip 後合理推論「其他都沒事」,
        但其中一部分根本沒在回報 —— 那正是本分頁要消滅的誤解(§1)。"""
        from src.ui.tabs.tab_macro_v2 import _CHIP_PROBLEM, build_rows, filter_rows
        rows = build_rows(_mixed())
        got = {r.key for r in filter_rows(rows, chip=_CHIP_PROBLEM)}
        for r in rows:
            if r.state != "live":
                assert r.key in got, f"{r.key}({r.state})被「有問題」篩掉了"

    # ── 選取列對應（本組最重要的一條）───────────────────────────
    def test_panel_shows_exactly_the_row_the_table_shows(self):
        """右側面板的指標，必須等於表格**該列**顯示的指標。

        `visible_table()` 刻意把「篩選」與「組表」綁在同一次呼叫回傳;
        若哪天有人把表格改成吃未篩選的 `rows`(或反過來),這條就會紅。
        """
        from src.ui.tabs.tab_macro_v2 import (
            CHIP_ORDER,
            build_rows,
            selected_row,
            visible_table,
        )
        rows = build_rows(_mixed())
        for chip in CHIP_ORDER:
            for q in ("", "率", "指數"):
                visible, table = visible_table(rows, chip=chip, query=q)
                assert len(table["指標"]) == len(visible)
                for i in range(len(visible)):
                    picked = selected_row(visible, [i])
                    assert picked is not None
                    assert picked.label == table["指標"][i], (
                        f"chip={chip} query={q!r} 第 {i} 列:表格顯示"
                        f"「{table['指標'][i]}」,面板卻拿到「{picked.label}」"
                    )

    def test_row_index_is_into_the_filtered_list_not_the_original(self):
        """同一個索引在「篩選後」與「原始 16 列」指到不同指標 —— 用錯清單
        就是右側面板顯示另一個指標的成因。這條釘住那個差異真的存在。"""
        from src.ui.tabs.tab_macro_v2 import (
            build_rows,
            selected_row,
            visible_table,
        )
        rows = build_rows(_mixed())
        visible, _ = visible_table(rows, chip="chips")
        assert len(visible) < len(rows)
        i = 1
        assert visible[i].key != rows[i].key, (
            "測試前提失效:篩選後第 1 列剛好等於原始第 1 列，這條就測不到東西"
        )
        assert selected_row(visible, [i]) is visible[i]
        assert selected_row(visible, [i]) is not rows[i]

    def test_stale_selection_after_filter_change_returns_none(self):
        """先選第 N 列 → 改篩選讓清單變短 → 舊索引越界。

        §1:回 None 讓 caller 說「選取已失效」,**不得**退回第 0 列 ——
        那等於默默換一個指標給使用者看。
        """
        from src.ui.tabs.tab_macro_v2 import (
            build_rows,
            selected_row,
            visible_table,
        )
        rows = build_rows(_mixed())
        wide, _ = visible_table(rows)                    # 16 列
        assert selected_row(wide, [12]) is not None
        narrow, _ = visible_table(rows, chip="news")     # 1 列
        assert len(narrow) == 1
        assert selected_row(narrow, [12]) is None, "越界索引沒被擋下"
        assert selected_row(narrow, []) is None
        assert selected_row(narrow, [-1]) is None, "負索引會從尾端取,同樣是換指標"

    # ── 篩選後 0 筆 ──────────────────────────────────────────────
    def test_zero_result_message_states_the_active_filter(self):
        """§1:不留一張空表。文案要把 chip 與搜尋字原樣講出來。"""
        from src.ui.tabs.tab_macro_v2 import (
            build_rows,
            empty_hint,
            visible_table,
        )
        rows = build_rows(_mixed())
        visible, table = visible_table(rows, chip="chips", query="VIX")
        assert visible == [] and all(not col for col in table.values())
        msg = empty_hint(chip="chips", query="VIX", total=len(rows))
        assert "沒有符合的指標" in msg
        assert "籌碼" in msg, "沒講出目前選的分類"
        assert "VIX" in msg, "沒講出目前的搜尋字"
        assert "16" in msg, "沒告訴使用者清掉篩選會看回幾盞燈"

    def test_zero_result_message_omits_an_empty_query(self):
        from src.ui.tabs.tab_macro_v2 import empty_hint
        msg = empty_hint(chip="news", query="   ", total=16)
        assert "新聞" in msg
        assert "搜尋「" not in msg, "沒打搜尋字卻報了一個搜尋條件"
        assert "清掉搜尋字" not in msg, "叫人清掉一個他沒打的東西"


# ════════════════════════════════════════════════════════════════
# 七、版本陷阱:不得使用超出 requirements.txt floor 的 widget
# ════════════════════════════════════════════════════════════════
class TestStreamlitFloorCompatibility:
    """守住「宣告的 floor」與「程式碼真正需要的版本」不脫節。

    ⚠️ 2026-08-27 重寫。舊版是**壞掉的守衛**,三個獨立問題:

    1. **地板寫死在測試裡**。舊版 `banned` 表拿 1.36 當基準。而 2026-08-27 把
       `requirements.txt` 的 floor 抬到 1.56 之後,表裡那三個(pills 1.40 /
       segmented_control 1.42 / fragment 1.37)**全部落在地板底下** ——
       整條守衛會變成永遠不會擋任何東西的綠燈裝飾品。
       → 現在 floor **從 `requirements.txt` 反解**,是唯一真相源。地板一改,
         哪些 API 該擋自動跟著改,不需要有人記得回來同步這張表。
    2. **只比對屬性名,不看關鍵字參數**。舊版只看 `st.<name>`,所以它掃的那個檔案裡
       就擺著 `st.dataframe(..., width='stretch')`(需 1.49)而它抓不到 ——
       這正是本次事故的形狀:壞掉的東西不在元件名,在參數。
       → 現在 `(元件, 關鍵字)` 與 `(*, 關鍵字)` 兩層都掃。
    3. **只掃單一檔案** `tab_macro_v2.py`。同一組畫面的姊妹檔
       `macro_v2_cards.py` 完全在守備範圍外。
       → 現在掃 `src/**/*.py` + `app.py` 全域,並另有一條斷言釘死那兩個檔案
         必須在掃描範圍內,避免日後範圍被悄悄縮回去。

    **表裡每一個版本號都是實測的,不是查文件抄的**(wheel `pip download --no-deps`
    解壓 + `PYTHONPATH` 就地跑 `streamlit.testing.v1.AppTest`)。為了不編造「首個
    支援版本」,表的語意刻意定成 **「已實測**不**支援的最高版本」**:
    判定式是 `floor <= 該值 → 違規`。這樣每個數字都是我親眼看它壞掉的那一版,
    沒有任何靠推論填空的區間。
    """

    #: `st.<name>` 本身在該版本**實測不存在**(hasattr 為 False)。
    _ATTR_UNSUPPORTED_AT = {
        # 1.36.0 實測 hasattr 皆 False(沿用舊表的三個,但版本改為實測值)
        "pills": "1.36.0",
        "segmented_control": "1.36.0",
        "fragment": "1.36.0",
        # 1.56.0 實測 hasattr 皆 False,沙箱 1.61.1 為 True —— 典型「本機全綠、
        # 部署 AttributeError」的形狀,正是這條守衛存在的理由。
        "mermaid_chart": "1.56.0",
        "pagination": "1.56.0",
        "skeleton": "1.56.0",
        "bottom": "1.56.0",
    }

    #: `st.<元件>(<關鍵字>=...)` 在該版本**實測無效**。`"*"` = 任何 `st.*` 呼叫。
    _KWARG_UNSUPPORTED_AT = {
        # ── 本次事故的兩條主角 ──────────────────────────────
        # 1.48.1 實測直接 TypeError: 'str' object cannot be interpreted as an
        # integer(硬炸,至少會被發現);1.49.0 通過。
        ("dataframe", "width"): "1.48.1",
        # 1.50.0 實測被 `**kwargs` 吞掉:產生的 proto 與「完全不傳 width」逐欄相同,
        # 且零錯誤訊息 —— 比硬炸危險,因為沒有任何跡象。1.51.0 才是真參數。
        ("plotly_chart", "width"): "1.50.0",
        # ── 這次把 floor 抬到 1.56 的驅動:程式化指定表格選取列 ──
        ("dataframe", "selection_default"): "1.55.0",
        # ── 1.56.0 實測不存在、沙箱 1.61.1 存在的關鍵字 ────────
        ("dataframe", "lazy"): "1.56.0",
        ("metric", "icon"): "1.56.0",
        ("tabs", "height"): "1.56.0",
        ("expander", "type"): "1.56.0",
        ("status", "type"): "1.56.0",
        ("markdown", "anchors"): "1.56.0",
        ("chat_input", "submit_mode"): "1.56.0",
        ("camera_input", "resolution"): "1.56.0",
        ("cache_data", "refresh_mode"): "1.56.0",
        ("cache_resource", "refresh_mode"): "1.56.0",
        ("fragment", "parallel"): "1.56.0",
        ("time_input", "format"): "1.56.0",
        ("error", "title"): "1.56.0",
        ("info", "title"): "1.56.0",
        ("success", "title"): "1.56.0",
        ("warning", "title"): "1.56.0",
        # `persist_state` 1.56.0 實測橫跨 16 個 widget 全無 —— 逐個列會漏,
        # 用萬用字元蓋掉任何 `st.*(persist_state=...)`。
        ("*", "persist_state"): "1.56.0",
    }

    #: 掃描範圍最低限度必須含這兩個檔(同一組畫面的正副檔)。
    _MUST_COVER = ("src/ui/tabs/tab_macro_v2.py", "src/ui/render/macro_v2_cards.py")

    @staticmethod
    def _ver(text: str) -> tuple[int, ...]:
        return tuple(int(p) for p in text.split("."))

    @classmethod
    def _declared_floor(cls) -> tuple[int, ...]:
        """從 `requirements.txt` 反解 streamlit 的 floor —— 唯一真相源。"""
        import pathlib
        import re

        for line in pathlib.Path("requirements.txt").read_text(
                encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or not line.startswith("streamlit"):
                continue
            m = re.match(r"streamlit>=(\d+(?:\.\d+)*)", line)
            assert m, f"requirements.txt 的 streamlit 行沒有可解析的 floor:{line!r}"
            return cls._ver(m.group(1))
        raise AssertionError("requirements.txt 找不到 streamlit 這一行")

    @classmethod
    def _scan_targets(cls):
        import pathlib

        files = sorted(pathlib.Path("src").rglob("*.py"))
        app = pathlib.Path("app.py")
        if app.exists():
            files.append(app)
        return files

    def _violations(self, floor):
        import ast

        hits = []
        for path in self._scan_targets():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                # (1) 元件本身太新 —— 也涵蓋 `@st.fragment` 這種裝飾器用法
                if (isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id == "st"):
                    bad = self._ATTR_UNSUPPORTED_AT.get(node.attr)
                    if bad and floor <= self._ver(bad):
                        hits.append(
                            f"{path}:{node.lineno} st.{node.attr}"
                            f"(實測 {bad} 尚無此 API)")
                # (2) 元件沒問題但關鍵字參數太新 —— 舊守衛完全看不到的那一層
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "st"):
                    for kw in node.keywords:
                        if kw.arg is None:  # **kwargs 展開,無法靜態判定
                            continue
                        for key in ((node.func.attr, kw.arg), ("*", kw.arg)):
                            bad = self._KWARG_UNSUPPORTED_AT.get(key)
                            if bad and floor <= self._ver(bad):
                                hits.append(
                                    f"{path}:{node.lineno} "
                                    f"st.{node.func.attr}({kw.arg}=...)"
                                    f"(實測 {bad} 此參數無效)")
        return sorted(set(hits))

    # ── 守衛本體 ──────────────────────────────────────────────
    def test_no_streamlit_api_newer_than_the_declared_floor(self):
        """程式碼不得用到超出 `requirements.txt` 宣告 floor 的 streamlit API。

        沒有 lock 檔時 resolver 會解到 cap 內最新版,所以沙箱與 production 都
        跑得動 —— 宣告與實況脫節不會有任何症狀,直到有人真的照著宣告去裝。
        """
        floor = self._declared_floor()
        hits = self._violations(floor)
        assert not hits, (
            "用到超出宣告 floor 的 streamlit API:\n  "
            + "\n  ".join(hits)
            + f"\n\nrequirements.txt 宣告 streamlit>="
            + ".".join(str(p) for p in floor)
            + "。要嘛改用該版本就有的寫法,要嘛連同 requirements.txt 一起把 floor 抬上去"
              "(抬 floor 記得同步 tests/test_hotfix_v19_79.py 的逐字 pin)。"
        )

    # ── 守衛的守衛:確保它真的還會擋東西、範圍沒被縮掉 ──────────
    def test_scan_covers_both_macro_v2_files(self):
        """掃描範圍不得縮回單一檔案 —— 舊版只掃 tab_macro_v2.py 就漏掉了姊妹檔。"""
        scanned = {p.as_posix() for p in self._scan_targets()}
        missing = [f for f in self._MUST_COVER if f not in scanned]
        assert not missing, f"這些檔案掉出掃描範圍:{missing}"

    def test_guard_actually_bites(self):
        """反向驗證:守衛必須真的抓得到違規,不能是永遠綠燈的裝飾品。

        舊版守衛就是死在這裡 —— floor 抬到 1.56 後表裡三個 API 全在地板下,
        它變成不可能紅燈,但沒有任何測試會告訴你這件事。故這條直接把地板往下壓,
        要求它一定要吐出東西來。
        """
        # 壓到 1.36:全 repo 現有的 width='stretch' 都該被抓出來
        hits_136 = self._violations(self._ver("1.36.0"))
        assert hits_136, "把 floor 壓到 1.36 竟然抓不到任何東西 —— 守衛已失效"
        assert any("dataframe(width=" in h for h in hits_136)
        assert any("plotly_chart(width=" in h for h in hits_136)
        # 壓到 1.49:dataframe 的 width 已合法,plotly 的還不合法 —— 證明它辨識得出
        # 「同一個關鍵字、不同元件、不同版本」,不是一刀切。
        hits_149 = self._violations(self._ver("1.49.0"))
        assert not any("dataframe(width=" in h for h in hits_149)
        assert any("plotly_chart(width=" in h for h in hits_149)
        # 現行 floor 之上仍有東西可擋 —— 表沒有整組落到地板底下(舊版的死法)
        floor = self._declared_floor()
        live = [v for v in (*self._ATTR_UNSUPPORTED_AT.values(),
                            *self._KWARG_UNSUPPORTED_AT.values())
                if floor <= self._ver(v)]
        assert live, (
            f"現行 floor {floor} 之上一條規則都不剩 —— 守衛已退化成裝飾品,"
            "請補上比 floor 更新的 API/參數(照表頭說明:填『實測不支援的最高版本』)。"
        )


# ════════════════════════════════════════════════════════════════
# 八、狀態欄的 emoji 雙重編碼（2026-08-26）
#
# 為什麼要有這一組:狀態欄原本只有中文字。加 emoji 是**冗餘**編碼 ——
# 在文字旁邊多一個線索，不是取代文字。三件事必須被釘住，否則加了等於沒加:
#
#   1. **對應不能漂**。特別是「門檻已失準」**不是** 🔴 ❌ —— 它的語意是
#      「有值、燈照亮，只是別照門檻讀」，不是故障。標紅叉會讓使用者以為
#      那盞燈壞了，但它正在正常回報數字（user 2026-08-26 裁示）。
#   2. **「無資料」與「未接線」必須看得出差別**。兩者的色碼本來就是同一個
#      灰（`#8a8e96`），肉眼分不出來 —— 而四態存在的整個理由就是要把
#      「上游沒給值」與「決策端沒接線」分開。emoji 這一欄是它們唯一的區隔。
#   3. **文案只准有一份**。上一輪才把四態中文從畫面層收回 L4 `STATE_META`；
#      emoji 若在畫面層另寫一份 dict，就是把它推回去（§3.3 第二把尺）。
# ════════════════════════════════════════════════════════════════

#: 狀態欄專屬的 emoji。⚠️ **刻意不列 `⚠️`** —— 它是 Streamlit 到處在用的
#: 通用警示圖示（`st.warning(icon=...)`），拿它當「有人另寫一份狀態文案」
#: 的證據會誤判。真的有第二份 dict 時，四態中文標籤那條斷言一樣抓得到。
_STATE_GLYPHS = ("🟢", "🟠", "⚪", "⚫", "✅", "➖", "🔌", "❓")


class TestStateColumnDualCoding:

    # ── 四態各一條:emoji 與中文都要在，而且要對 ──────────────────
    @pytest.mark.parametrize(("state", "emoji", "zh"), [
        ("live",     "🟢 ✅", "運作中"),
        ("degraded", "🟠 ⚠️", "門檻已失準"),
        ("missing",  "⚪ ➖", "無資料"),
        ("unwired",  "⚫ 🔌", "未接線"),
    ])
    def test_each_state_shows_both_emoji_and_chinese(self, state, emoji, zh):
        """emoji 是**加在**中文旁邊的第二個線索，不是中文的替代品。

        只出 emoji 等於把資訊綁死在「看得懂這個符號」上；只出中文則是這次
        要改的現況。故兩者都必須出現，且順序固定（emoji 在前，掃視時先看到）。
        """
        from src.ui.render.macro_v2_cards import state_cell
        assert state_cell(state) == f"{emoji} {zh}"

    def test_degraded_is_not_a_red_cross(self):
        """**本組最重要的一條。** 「門檻已失準」= 有值、照常亮，只是門檻
        讀不出意義 —— 它**沒有壞**。紅色 + 叉是「故障 / 不通過」的通用語彙，
        用在這裡會把一盞正在正常回報數字的燈講成死掉的燈（§1 反過來的錯:
        不是編數字，是編一個比事實更嚴重的結論）。
        """
        from src.ui.render.macro_v2_cards import state_cell
        cell = state_cell("degraded")
        assert "🔴" not in cell and "❌" not in cell, (
            f"「門檻已失準」被標成故障:{cell!r} —— 它有值、燈照常亮"
        )
        assert "🟠" in cell, "失準應該是橙色警示（介於正常與故障之間）"

    def test_missing_and_unwired_are_visually_separable(self):
        """兩者的**色碼是同一個灰**，emoji 是它們畫面上唯一的區隔。

        這條同時把「色碼相同」這個事實釘住 —— 哪天有人把灰色拆開了，這條
        會紅，提醒他回來看這裡的註解（那時 emoji 就不再是唯一區隔）。
        """
        from src.ui.render.macro_v2_cards import STATE_META, state_cell
        assert STATE_META["missing"][1] == STATE_META["unwired"][1], (
            "色碼已經不同了 —— 請回頭更新 STATE_META 上方那段註解的前提"
        )
        assert state_cell("missing") != state_cell("unwired")
        assert STATE_META["missing"][2] != STATE_META["unwired"][2], (
            "「無資料」與「未接線」共用同一組 emoji —— 四態又被壓成三態了"
        )

    def test_all_four_states_have_distinct_cells(self):
        """四態兩兩不同。任何兩態撞在一起 = 使用者無從分辨（v2 的存在理由）。"""
        from src.ui.render.macro_v2_cards import STATE_META, state_cell
        cells = [state_cell(s) for s in STATE_META]
        assert len(set(cells)) == len(STATE_META) == 4, f"有重複:{cells}"

    # ── fallback:未定義狀態 ──────────────────────────────────────
    def test_unknown_state_falls_back_to_a_question_mark(self):
        """§1:未定義的狀態**不猜、不回退成「無資料」**。

        回退成「無資料」會把一個 bug 偽裝成一種正常結果 —— 使用者看到的是
        一個合法的四態之一，沒有任何跡象顯示上游出了沒人預期的事。
        """
        from src.ui.render.macro_v2_cards import state_cell
        assert state_cell("ghost_state") == "⚪ ❓ 未知狀態"

    def test_unknown_state_is_not_silent(self, capsys):
        """§1:走到 fallback 代表上游冒出了四態以外的東西，那是要有人去看的
        事。畫面顯示問號讓使用者知道這格不可信，同時要在 stdout 留下痕跡
        （比照 `macro_helpers._rec` / `_unwired` 對 SSOT 缺欄位的既有做法）。
        """
        from src.ui.render.macro_v2_cards import state_cell
        state_cell("ghost_state")
        out = capsys.readouterr().out
        assert "ghost_state" in out, "警告沒把那個未知狀態的值印出來"
        assert "⚠️" in out and "state_cell" in out, f"沒留下可辨識的警告痕跡:{out!r}"

    def test_known_states_do_not_warn(self, capsys):
        """反例:四態走正常路徑時**不得**噴警告 —— 否則真的出事時沒人會看。"""
        from src.ui.render.macro_v2_cards import STATE_META, state_cell
        for s in STATE_META:
            state_cell(s)
        assert capsys.readouterr().out == ""

    # ── 表格真的用了它 ───────────────────────────────────────────
    def test_table_state_column_is_exactly_the_ssot_cell(self):
        """總表的「狀態」欄必須逐格等於 `state_cell()` 的輸出。

        `_table_columns` 若哪天改成自己拼字串，這條就會紅。
        """
        from src.ui.render.macro_v2_cards import state_cell
        from src.ui.tabs.tab_macro_v2 import build_rows, visible_table
        rows = build_rows(_mixed())
        visible, table = visible_table(rows)
        assert len(table["狀態"]) == len(visible) == 16
        for r, cell in zip(visible, table["狀態"]):
            assert cell == state_cell(r.state), f"{r.key} 的狀態欄與 SSOT 不同"

    def test_table_covers_all_four_states_with_emoji(self):
        """端到端:一份四態齊備的 readiness，總表的狀態欄要四種都出現且帶 emoji。"""
        from src.ui.tabs.tab_macro_v2 import build_rows, visible_table
        _, table = visible_table(build_rows(_mixed()))
        seen = set(table["狀態"])
        assert {"🟢 ✅ 運作中", "🟠 ⚠️ 門檻已失準",
                "⚪ ➖ 無資料", "⚫ 🔌 未接線"} <= seen, seen

    def test_light_column_stays_plain_text(self):
        """「燈」欄維持純文字（user 2026-08-26 裁示:視覺重心留給核心結論）。

        這同時是狀態欄敢出 emoji 的**前提**:同一列若兩欄都出符號，🟢 會與
        狀態的 live 撞在一起 —— 那正是姊妹檔 `render/station_cards.py` 檔頭
        點名拒絕 emoji 的那個坑。這條紅了，就要連著那段一起重想。
        """
        from src.ui.tabs.tab_macro_v2 import build_rows, visible_table
        _, table = visible_table(build_rows(_mixed()))
        assert set(table["燈"]) <= {"綠", "黃", "紅", "無資料"}
        for cell in table["燈"]:
            assert not any(g in cell for g in _STATE_GLYPHS), (
                f"「燈」欄出現了狀態欄的符號:{cell!r} —— 同列兩個符號會互撞"
            )

    # ── SSOT 靜態守衛 ────────────────────────────────────────────
    def test_display_layer_writes_no_second_copy_of_the_four_states(self):
        """靜態守衛:畫面層(L5)不得自己寫四態的中文或 emoji。

        比照 `test_rows_mirror_the_sidecar_exactly` 的精神 —— 用「寫不出來」
        取代「請記得別寫」。上一輪才把四態中文從這一層收回 L4 `STATE_META`,
        emoji 若又在這裡落地一份，兩把尺就會各自演化。

        只看 **AST 的字串常數**:docstring 與註解裡提到狀態名是在解釋設計，
        不是第二把尺（註解根本不進 AST；docstring 逐一排除）。
        """
        import ast
        import pathlib

        from src.ui.render.macro_v2_cards import STATE_META, STATE_UNKNOWN_META

        tree = ast.parse(pathlib.Path("src/ui/tabs/tab_macro_v2.py")
                         .read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        consts = [
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings
        ]

        labels = {m[0] for m in STATE_META.values()} | {STATE_UNKNOWN_META[0]}
        for c in consts:
            assert c not in labels, (
                f"L5 又寫了一份四態文案:{c!r} —— 請改用 "
                f"`macro_v2_cards.state_cell()`（§3.3 第二把尺）"
            )
            hit = [g for g in _STATE_GLYPHS if g in c]
            assert not hit, (
                f"L5 出現狀態欄的 emoji {hit} 於 {c!r} —— emoji 與中文都只准"
                f"住在 L4 `STATE_META`"
            )

    def test_emoji_and_label_live_in_the_same_ssot_row(self):
        """emoji 與中文必須是**同一列**的兩個欄位，不是兩張平行的表。

        平行兩張表的失效模式:上游新增一個狀態，有人只加了其中一張 ——
        另一張 KeyError 或悄悄漏掉，而這件事在畫面上看不出來。
        """
        from src.ui.render.macro_v2_cards import STATE_META
        for state, meta in STATE_META.items():
            assert len(meta) == 3, f"{state} 的 meta 不是 (中文, 色碼, emoji)"
            label, color, emoji = meta
            assert label and emoji, f"{state} 缺中文或 emoji"
            assert color.startswith("#"), f"{state} 的色碼欄不是色碼:{color!r}"
