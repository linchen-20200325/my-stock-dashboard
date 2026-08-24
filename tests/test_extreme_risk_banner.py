# -*- coding: utf-8 -*-
"""極端風險警語守衛（2026-08-23）。

這段程式會叫使用者**把持股砍到一成**。它出錯的代價不對稱:
  - 該響沒響 → 使用者少一次提醒(仍有其他資訊來源)
  - 不該響卻響 → 使用者在錯誤的時點清倉,或是響到麻痺、真的該跑那次也忽略
  - **算不出來卻被當成沒事 → 最糟**:使用者以為系統看過了

所以本檔的重心不在「門檻算得對不對」(那是一行比較),而在:
  ① 缺料**永遠**不能長得像安全(TestUnknownNeverReadsAsSafe)
  ② 門檻被改鬆會被實測頻率抓到(TestFrequencyDriftLock)
  ③ 輸出不會撞壞既有訊息模組的契約(TestHoldingsMessageContract)
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared.global_lead_markets import GLOBAL_LEAD_DROP_PCT, LEAD_MARKETS
from shared.signal_thresholds import (
    EXTREME_TARGET_POSITION_PCT,
    EXTREME_TWII_20D_DROP_PCT,
    FOREIGN_5D_NET_THRESHOLD_YI,
)
from src.compute.notify.market_alert_banner import (
    LEG_FOREIGN,
    LEG_TWII,
    STATE_CLEAR,
    STATE_EXTREME,
    STATE_UNKNOWN,
    build_alert_block,
    evaluate_extreme_risk,
    format_extreme_banner,
    format_global_lead_line,
)

_HIT_T = EXTREME_TWII_20D_DROP_PCT - 0.3       # 比門檻更慘
_MISS_T = EXTREME_TWII_20D_DROP_PCT + 0.3      # 沒到門檻
_HIT_F = FOREIGN_5D_NET_THRESHOLD_YI - 50.0
_MISS_F = FOREIGN_5D_NET_THRESHOLD_YI + 50.0


def _v(t, f):
    return evaluate_extreme_risk(twii_20d_pct=t, foreign_5d_yi=f)


class TestTwoLegTruthTable:
    """兩腿共振:必須**兩腿同時**成立。單腿成立是常態波動,不是極端。"""

    @pytest.mark.parametrize("t,f,expect", [
        (_HIT_T, _HIT_F, STATE_EXTREME),
        (_HIT_T, _MISS_F, STATE_CLEAR),    # 價格壞、資金沒跑 → 不是極端
        (_MISS_T, _HIT_F, STATE_CLEAR),    # 資金跑、價格還撐著 → 不是極端
        (_MISS_T, _MISS_F, STATE_CLEAR),
    ])
    def test_truth_table(self, t, f, expect):
        assert _v(t, f).state == expect

    def test_boundary_is_inclusive(self):
        """剛好踩在門檻上算成立（<=）。差 0.01 就不算,是最容易寫反的一行。"""
        assert _v(EXTREME_TWII_20D_DROP_PCT, FOREIGN_5D_NET_THRESHOLD_YI).state == STATE_EXTREME
        assert _v(EXTREME_TWII_20D_DROP_PCT + 0.01,
                  FOREIGN_5D_NET_THRESHOLD_YI).state == STATE_CLEAR
        assert _v(EXTREME_TWII_20D_DROP_PCT,
                  FOREIGN_5D_NET_THRESHOLD_YI + 0.01).state == STATE_CLEAR

    def test_positive_returns_never_trigger(self):
        """反向守衛:大漲 + 外資大買不得觸發。沒有這條,把比較符號寫反也能讓上面全綠。"""
        assert _v(+12.0, +800.0).state == STATE_CLEAR


class TestUnknownNeverReadsAsSafe:
    """本檔的核心。缺料必須**看得見**,而且不能被讀成「沒事」。"""

    @pytest.mark.parametrize("t,f,missing", [
        (None, _MISS_F, LEG_TWII),
        (_MISS_T, None, LEG_FOREIGN),
        (None, None, LEG_TWII),
    ])
    def test_missing_leg_is_unknown_not_clear(self, t, f, missing):
        v = _v(t, f)
        assert v.state == STATE_UNKNOWN
        assert missing in v.missing

    def test_missing_leg_is_not_silently_dropped(self):
        """unknown **必須**產出可見文字。回空字串等於靜默 —— 那正是這輪在修的病。"""
        assert format_extreme_banner(_v(None, None)).strip()

    def test_unknown_banner_names_which_leg(self):
        msg = format_extreme_banner(_v(_MISS_T, None))
        assert LEG_FOREIGN in msg, "沒講缺哪一腿 → 使用者無從排查"
        assert LEG_TWII not in msg, "沒缺的腿不該被列進缺料清單"

    def test_unknown_banner_says_it_is_not_safe(self):
        assert "不代表安全" in format_extreme_banner(_v(None, None))

    @pytest.mark.parametrize("word", ["安全", "無風險", "正常", "沒事", "可放心"])
    def test_unknown_banner_makes_no_all_clear_claim(self, word):
        """缺料時不得出現任何「沒事」語意的詞。

        「不代表安全」含「安全」二字 —— 那是**否定**用法,故先剔除該句再檢查,
        避免這條測試把正確的警語判成違規。
        """
        msg = format_extreme_banner(_v(None, None)).replace("這不代表安全", "")
        assert word not in msg

    def test_extreme_dominates_even_if_one_value_looks_mild(self):
        """兩腿都在、剛好都踩線 → 仍是 extreme,不因為數字看起來不誇張就降級。"""
        assert _v(EXTREME_TWII_20D_DROP_PCT, FOREIGN_5D_NET_THRESHOLD_YI).is_extreme


class TestExtremeBannerContent:
    def test_clear_prints_nothing(self):
        """沒事就別佔行 —— 但這只在**兩腿都評估過**時才成立(見 unknown 那組)。"""
        assert format_extreme_banner(_v(_MISS_T, _MISS_F)) == ""

    def test_extreme_states_the_action(self):
        msg = format_extreme_banner(_v(-9.1, -612.0))
        assert f"{EXTREME_TARGET_POSITION_PCT}%" in msg
        assert "停止買賣" in msg and "脫手" in msg

    def test_extreme_shows_the_numbers_that_triggered_it(self):
        """只講結論不講數字 → 使用者無法判斷該不該照做。"""
        msg = format_extreme_banner(_v(-9.1, -612.0))
        assert "-9.1%" in msg
        assert "612" in msg and "賣超" in msg

    def test_foreign_buy_is_worded_as_buy(self):
        """反向守衛:金額格式化不得把買超講成賣超（絕對值化最容易吃掉正負號）。"""
        v = evaluate_extreme_risk(twii_20d_pct=-9.1, foreign_5d_yi=+612.0)
        assert v.state == STATE_CLEAR          # 外資買超 → 不觸發
        assert "賣超" not in format_extreme_banner(_v(-9.1, +612.0))

    def test_carries_a_non_advice_marker(self):
        assert "非投資建議" in format_extreme_banner(_v(-9.1, -612.0))


class TestGlobalLeadLine:
    """提示層:只描述事實,不下動作指令。"""

    _ALL_CALM = {m.symbol: -0.2 for m in LEAD_MARKETS}

    def test_all_calm_prints_nothing(self):
        assert format_global_lead_line(self._ALL_CALM) == ""

    def test_drop_is_named_with_value(self):
        q = dict(self._ALL_CALM, **{"^SOX": -6.1})
        line = format_global_lead_line(q)
        assert "費城半導體" in line and "-6.1%" in line

    def test_boundary_is_inclusive(self):
        q = dict(self._ALL_CALM, **{"^IXIC": GLOBAL_LEAD_DROP_PCT})
        assert "那斯達克綜合" in format_global_lead_line(q)

    def test_all_missing_is_disclosed(self):
        for empty in ({}, None, {m.symbol: None for m in LEAD_MARKETS}):
            assert "未取得" in format_global_lead_line(empty)

    def test_partial_missing_without_drop_is_disclosed(self):
        """沒抓到的那幾個可能正在崩 —— 不能回空字串裝作看過了。"""
        q = {"^GSPC": -0.2, "^IXIC": -0.3}
        line = format_global_lead_line(q)
        assert "未取得" in line and "2/6" in line

    def test_partial_missing_with_drop_still_reports_the_drop(self):
        q = {"^SOX": -7.0}
        assert "費城半導體" in format_global_lead_line(q)

    def test_gives_no_action_instruction(self):
        """提示層一年出現 130 次以上;它若也叫人清倉,動作層就沒有意義了。"""
        line = format_global_lead_line(dict(self._ALL_CALM, **{"^SOX": -6.1}))
        for word in ("停止買賣", "脫手", "降至", "清倉"):
            assert word not in line


class TestAlertBlockOrdering:
    def test_extreme_comes_first(self):
        """LINE 通知預覽只顯示開頭 —— 要行動的那則必須搶第一行。"""
        block = build_alert_block(_v(-9.1, -612.0),
                                  {m.symbol: -0.2 for m in LEAD_MARKETS} | {"^SOX": -6.1})
        assert block.splitlines()[0].startswith("🚨")

    def test_nothing_to_say_is_empty(self):
        block = build_alert_block(_v(-1.0, +100.0), {m.symbol: -0.2 for m in LEAD_MARKETS})
        assert block == ""


class TestHoldingsMessageContract:
    """輸出會被塞進 holdings 訊息 —— 不能撞壞那邊既有的否定斷言。"""

    @pytest.mark.parametrize("verdict", [
        (-9.1, -612.0), (None, None), (-1.0, +100.0), (-9.1, +612.0),
    ])
    def test_never_leaks_python_none_literal(self, verdict):
        """`tests/test_holdings_digest_message.py` 全檔斷言 `"None" not in msg`。"""
        assert "None" not in build_alert_block(_v(*verdict), None)

    @pytest.mark.parametrize("word", ["無需動作", "續抱、定期定額", "建議換入", "今日選股"])
    def test_does_not_collide_with_holdings_sections(self, word):
        assert word not in build_alert_block(_v(-9.1, -612.0), {"^SOX": -6.1})

    def test_no_nan_leak(self):
        out = build_alert_block(_v(-9.1, -612.0), {"^SOX": -6.1})
        assert "nan" not in out.lower()


class TestLayerPurity:
    """§8.2:L2 不得有 I/O。V-RADAR-1 就是靠人工稽核才發現的,這裡用測試釘住。"""

    _BANNED = {"requests", "httpx", "yfinance", "FinMind", "streamlit",
               "proxy_helper", "pandas", "sqlite3", "urllib"}

    def test_module_has_no_io_imports(self):
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src/compute/notify/market_alert_banner.py").read_text(encoding="utf-8")
        mods: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                mods |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        assert not (mods & self._BANNED), f"L2 出現 I/O import：{mods & self._BANNED}"

    def test_module_does_not_touch_src_data(self):
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src/compute/notify/market_alert_banner.py").read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("src.data"):
                pytest.fail(f"L2 直接 import L1：{node.module}")


class TestFrequencyDriftLock:
    """門檻被改鬆 → 這裡紅燈。

    選 -8% / -500 億不是拍腦袋:2026-08-23 用同一份 parquet 實測 20.0 年
    (n=4,895 交易日)得 **25 episodes = 1.25 次/年**。若有人把門檻放寬成
    「常常響」,警語就退化成雜訊而**不會有任何其他測試發現** —— 因為單元測試
    只驗邏輯對不對,不驗它多常成立。故在此用真實歷史把頻率釘住。

    容忍區間 [0.8, 2.5] 次/年:給市場結構變化留餘裕,但擋掉數量級的漂移。
    """

    @staticmethod
    def _episodes_per_year():
        pd = pytest.importorskip("pandas")
        import numpy as np
        root = pathlib.Path(__file__).resolve().parents[1] / "data_cache"
        tw, inst = root / "twii_ohlcv.parquet", root / "finmind_inst.parquet"
        if not (tw.exists() and inst.exists()):
            pytest.skip("data_cache parquet 不存在（淺 checkout / 首次 clone）")
        t = pd.read_parquet(tw)[["date", "close"]].sort_values("date")
        f = pd.read_parquet(inst)[["date", "foreign_buy"]].sort_values("date")
        d = t.merge(f, on="date", how="inner").reset_index(drop=True)
        d["r20"] = (d["close"] / d["close"].shift(20) - 1) * 100
        d["f5"] = d["foreign_buy"].rolling(5).sum()
        d = d.dropna(subset=["r20", "f5"])
        m = ((d["r20"] <= EXTREME_TWII_20D_DROP_PCT)
             & (d["f5"] <= FOREIGN_5D_NET_THRESHOLD_YI)).to_numpy()
        episodes = int((m & ~np.r_[False, m[:-1]]).sum())
        years = (pd.to_datetime(d["date"].max())
                 - pd.to_datetime(d["date"].min())).days / 365.25
        return episodes / years, episodes, years

    def test_frequency_stays_rare(self):
        rate, episodes, years = self._episodes_per_year()
        assert 0.8 <= rate <= 2.5, (
            f"極端風險閘門頻率漂移：{rate:.2f} 次/年（{episodes} episodes / {years:.1f} 年）。"
            f"當前門檻 20D<={EXTREME_TWII_20D_DROP_PCT}% 且 外資5日<={FOREIGN_5D_NET_THRESHOLD_YI}億。"
            f"太高 → 警語變雜訊；太低 → 幾乎不會響。改門檻前請先讀 "
            f"shared/signal_thresholds.py 的『極端風險閘門』段。")

    def test_single_leg_would_be_too_frequent(self):
        """釘住「為什麼要兩腿」:任一單腿都達不到罕見標準。

        沒有這條,後人會覺得兩腿是多餘的複雜度而把它簡化掉。
        """
        pd = pytest.importorskip("pandas")
        import numpy as np
        root = pathlib.Path(__file__).resolve().parents[1] / "data_cache"
        if not (root / "twii_ohlcv.parquet").exists():
            pytest.skip("data_cache parquet 不存在")
        t = pd.read_parquet(root / "twii_ohlcv.parquet")[["date", "close"]].sort_values("date")
        f = pd.read_parquet(root / "finmind_inst.parquet")[["date", "foreign_buy"]]
        d = t.merge(f.sort_values("date"), on="date", how="inner").reset_index(drop=True)
        d["r20"] = (d["close"] / d["close"].shift(20) - 1) * 100
        d["f5"] = d["foreign_buy"].rolling(5).sum()
        d = d.dropna(subset=["r20", "f5"])
        years = (pd.to_datetime(d["date"].max())
                 - pd.to_datetime(d["date"].min())).days / 365.25
        ep = lambda m: int((m & ~np.r_[False, m[:-1]]).sum())  # noqa: E731
        price_only = ep((d["r20"] <= EXTREME_TWII_20D_DROP_PCT).to_numpy()) / years
        flow_only = ep((d["f5"] <= FOREIGN_5D_NET_THRESHOLD_YI).to_numpy()) / years
        assert price_only > 2.0, f"單看價格腿 {price_only:.2f} 次/年"
        assert flow_only > 4.0, f"單看資金腿 {flow_only:.2f} 次/年"


class TestNoContradictoryAdvice:
    """同一則訊息裡不能同時出現「清倉」與「續抱」。

    個股健檢(每檔體質)與大盤極端風險(價格+資金)是兩個不同範圍,結論可以相反 ——
    但使用者不會這樣讀。他會在兩個相反指令裡採信讓自己舒服的那一個,
    而在該跑的時候「舒服的那個」永遠是續抱。
    """

    @staticmethod
    def _msg(*, extreme: bool):
        from src.compute.notify.holdings_digest_message import format_holdings_message
        blk = build_alert_block(_v(-9.1, -612.0) if extreme else _v(-1.0, +100.0), None)
        return format_holdings_message(
            {"vix": 38.2, "total": 6, "adds": [], "take_profit": [], "reds": []},
            {"switch_out": [], "switch_in": []},
            as_of="2026-08-23", alert_block=blk, alert_extreme=extreme)

    def test_extreme_suppresses_the_no_action_line(self):
        msg = self._msg(extreme=True)
        assert "🚨" in msg
        assert "今日無需動作：續抱、定期定額即可。" not in msg, \
            "極端風險警語與「續抱、定期定額」同時出現 → 使用者會採信後者"
        assert "請以警語為準" in msg

    def test_normal_day_keeps_the_no_action_line(self):
        """反向守衛:沒有極端風險時,原本的「今日無需動作」必須照常 ——
        否則把那行整個刪掉也能讓上面那條過。"""
        msg = self._msg(extreme=False)
        assert "今日無需動作：續抱、定期定額即可。" in msg
        assert "🚨" not in msg

    def test_banner_sits_above_the_title(self):
        """LINE 通知預覽只顯示開頭 —— 警語排在標題後面等於看不到。"""
        assert self._msg(extreme=True).splitlines()[0].startswith("🚨")


class TestInProgressBarIsDropped:
    """2026-08-24 事故的迴歸測試。

    當天 08:42 UTC(TW 16:42)手動觸發推播,提示層**整行沒印**;而同日 mynews
    歸檔的同一批標的是 ^SOX **-5.45%** / ^IXIC **-2.05%**(as_of 2026-08-23 22:02 UTC,
    即上一個完整交易日 2026-08-21 vs 08-20)。production log 證實六個標的
    **全部抓取成功** —— 抓到了,但算出來的變動沒有一個達標。

    最可能的機制:Yahoo 的 `interval=1d` 在盤前就為「今天」開了一根未收盤的棒,
    於是 `iloc[-1]/iloc[-2]` 算的是「今天到目前為止」(≈0%)而非「上一個完整交易日」。

    ⚠️ 誠實揭露:此成因為**推論**,非實測確認 —— 沙箱連不到 Yahoo
    (`curl` 回 `CONNECT tunnel failed 403`),無法取得當下的原始序列。
    故本輪同時補了逐標的 log(哪兩天/什麼值/幾 %),下一次真實執行即可確認。
    本組測試釘的是**規則本身**,那部分是確定的:進行中的棒不該被當成收盤。
    """

    @staticmethod
    def _series(dates, values):
        pd = pytest.importorskip("pandas")
        return pd.Series(values, index=pd.to_datetime(dates), dtype=float)

    def _drop(self, s, now):
        from src.data.macro.macro_cache_reader import drop_in_progress_bar
        return drop_in_progress_bar(s, now)

    def _now(self, y, m, d, h):
        import datetime as dt
        return dt.datetime(y, m, d, h, tzinfo=dt.timezone.utc)

    def test_premarket_bar_is_dropped(self):
        """盤前觸發:今天那根未收盤的棒必須丟掉,改用前一個完整交易日。"""
        s = self._series(["2026-08-20", "2026-08-21", "2026-08-24"],
                         [12417.05, 11740.37, 11740.37])
        out = self._drop(s, self._now(2026, 8, 24, 8))     # 08:42 UTC ≈ 事故時點
        assert len(out) == 2
        assert out.index[-1].date().isoformat() == "2026-08-21"

    def test_after_close_bar_is_kept(self):
        """**反向守衛**:收盤後(排程 22:30 UTC)那根是完整的,不得丟。

        沒有這條,把函式寫成「一律丟最後一根」也能讓上面那條過 —— 而那會讓
        每天 06:30 的推播永遠慢一個交易日。
        """
        s = self._series(["2026-08-20", "2026-08-21", "2026-08-24"],
                         [12417.05, 11740.37, 11000.0])
        out = self._drop(s, self._now(2026, 8, 24, 22))    # 22:30 UTC = TW 06:30
        assert len(out) == 3
        assert out.index[-1].date().isoformat() == "2026-08-24"

    def test_older_last_bar_is_never_dropped(self):
        """最後一根不是「今天」→ 與收盤與否無關,一律保留。"""
        s = self._series(["2026-08-20", "2026-08-21"], [12417.05, 11740.37])
        for _h in (8, 22):
            assert len(self._drop(s, self._now(2026, 8, 24, _h))) == 2

    def test_real_incident_numbers_would_have_fired(self):
        """把當天的真實報價餵進去,提示層必須點名費半與那斯達克。

        數字取自 mynews `data/intl_alert/2026-08-24.json`(第一手歸檔,非我推算)。
        """
        _chg = {"^GSPC": -1.43, "^IXIC": -2.05, "^DJI": -0.85,
                "^SOX": -5.45, "ES=F": -0.29, "NQ=F": -0.67}
        line = format_global_lead_line(_chg)
        # ⚠️ `-2.05` → `-2.0%`,不是 `-2.1%`:Python 的 format 走 round-half-to-even。
        #    我第一版把期望值寫成 -2.1% 而測試紅了 —— **改的是測試不是程式**,
        #    因為顯示層四捨五入的方式不影響「有沒有達標」的判定。
        assert "費城半導體 -5.5%" in line and "那斯達克綜合 -2.0%" in line
        # 標普 -1.43% 差 0.07pp 沒到門檻 —— 不得被列入(釘住邊界沒有被放寬)
        assert "標普" not in line
        assert "道瓊" not in line
