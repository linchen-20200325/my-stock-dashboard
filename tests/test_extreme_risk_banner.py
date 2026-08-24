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
        """提示層一年約出現 77 次;它若也叫人清倉,動作層就沒有意義了。

        ⚠️ 2026-08-24 更正:原文寫「130 次以上」—— 那個數字同樣是用 mynews 那個
        壞掉的欄位算出來的(五日累計冒充日變動,自然灌高)。用真實日變動重測是
        **31% 的交易日、約 77 次/年**。`market_alert_banner.py` 與
        `shared/global_lead_markets.py` 都已更正,這裡當時漏了。
        """
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
            as_of="2026-08-23", alert_block=blk, alert_has_action=extreme)

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
    """`drop_in_progress_bar` 的規則測試:進行中的 K 棒不得被當成收盤。

    ═══ 撤回:本組原本掛在一個不存在的「事故」上(2026-08-24 當日更正)═══════
    原 docstring 寫「2026-08-24 事故的迴歸測試」,並引用 ^SOX **-5.45%** /
    ^IXIC **-2.05%** 當作「提示層漏報」的證據。**那組數字是錯的,那天也沒有事故。**

    它取自 mynews `index_fetcher` 一個有 bug 的欄位(把約五個交易日的累計變動
    當成隔夜變動)。當天六個標的的**真實單日變動**見
    `test_the_2026_08_24_numbers_correctly_produce_no_alert` —— 沒有一個到 -1.5%,
    四個還是漲的,所以當天整行不印是**正確行為**。

    **規則本身仍然成立**,而且與那天有沒有出事無關:拿一根還沒收盤的 K 棒當
    「收盤價」在任何時候都是錯的。本組測試釘的就是這條規則。

    ⚠️ 教訓寫在這裡而不是刪掉:當初會誤判,是因為拿了一個**沒有記錄日期**的數字
    當第一手證據。同樣的病,mynews 那邊犯了三個月沒人發現。
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
        # 真實收盤:08-20 = 11800.02、08-21 = 11740.37(來源見 class docstring)。
        # 原本這裡寫 12417.05 當 08-20 —— 那其實是 **08-14** 的收盤,
        # 沿用會把同一個誤解帶進 fixture。
        s = self._series(["2026-08-20", "2026-08-21", "2026-08-24"],
                         [11800.02, 11740.37, 11740.37])
        out = self._drop(s, self._now(2026, 8, 24, 8))     # 08:42 UTC ≈ 當初誤判的時點
        assert len(out) == 2
        assert out.index[-1].date().isoformat() == "2026-08-21"

    def test_after_close_bar_is_kept(self):
        """**反向守衛**:收盤後(排程 22:30 UTC)那根是完整的,不得丟。

        沒有這條,把函式寫成「一律丟最後一根」也能讓上面那條過 —— 而那會讓
        每天 06:30 的推播永遠慢一個交易日。
        """
        s = self._series(["2026-08-20", "2026-08-21", "2026-08-24"],
                         [11800.02, 11740.37, 11000.0])
        out = self._drop(s, self._now(2026, 8, 24, 22))    # 22:30 UTC = TW 06:30
        assert len(out) == 3
        assert out.index[-1].date().isoformat() == "2026-08-24"

    def test_older_last_bar_is_never_dropped(self):
        """最後一根不是「今天」→ 與收盤與否無關,一律保留。"""
        s = self._series(["2026-08-20", "2026-08-21"], [11800.02, 11740.37])
        for _h in (8, 22):
            assert len(self._drop(s, self._now(2026, 8, 24, _h))) == 2

    def test_the_2026_08_24_numbers_correctly_produce_no_alert(self):
        """2026-08-24 的**真實**報價 → 提示層必須回空字串(沉默是對的)。

        本條取代原 `test_real_incident_numbers_would_have_fired`。那條餵的是
        ^SOX -5.45% / ^IXIC -2.05%,並註明「第一手歸檔,非我推算」—— **註明是錯的**,
        那組數字來自 mynews 一個有 bug 的欄位。

        下面是真實單日變動,兩個獨立來源交叉驗證:
          (1) 本 repo 自己的 production log `[lead_mkt]`(run 32720204915)
          (2) mynews 歸檔 `last` 欄重建 —— 該欄對得上獨立新聞
              (同期報導「道瓊大跌 703 點」,重建為 -703.84 點)

        四個標的實際是**漲**的。這條測試現在釘的是:**那天不印任何東西是正確的**。
        """
        _chg = {"^GSPC": +0.43, "^IXIC": +0.43, "^DJI": +0.98,
                "^SOX": -0.51, "ES=F": +0.38, "NQ=F": +0.30}
        assert format_global_lead_line(_chg) == "", \
            "六個標的都沒到 -1.5%,提示層應保持沉默"

    def test_threshold_boundary_is_not_quietly_widened(self):
        """門檻邊界守衛:剛好沒到的不得列入,到了的必須列入。

        ⚠️ 下面的數字是**合成的**,不是任何一天的真實報價 —— 上一條已經用真實數字
        釘住「那天該沉默」,這一條只負責釘邊界,兩者用途不同不可混為一談。
        (原本這兩件事被擠在同一條測試裡,而它用的還是錯的數字。)
        """
        _chg = {"^GSPC": -1.43, "^IXIC": -2.05, "^DJI": -0.85,
                "^SOX": -5.45, "ES=F": -0.29, "NQ=F": -0.67}
        line = format_global_lead_line(_chg)
        # ⚠️ `-2.05` → `-2.0%`,不是 `-2.1%`:Python 的 format 走 round-half-to-even。
        #    顯示層四捨五入的方式不影響「有沒有達標」的判定。
        assert "費城半導體 -5.5%" in line and "那斯達克綜合 -2.0%" in line
        # 標普 -1.43% 差 0.07pp 沒到門檻 —— 不得被列入
        assert "標普" not in line
        assert "道瓊" not in line


class TestBroadLeadSelloff:
    """動作層 B:國際盤**至少 3 個**領先市場同日大跌 → 建議持股降至 20%。

    這一層是 2026-08-24 user 指定新增。設計要點是**看廣度不看深度** ——
    實測樣本裡 18 次提示層觸發有 17 次是費半單獨在跌(高波動指數,單日 ±1.5% 是常態),
    那是族群輪動不是系統性風險。用「幾個市場同時跌」當閘門剛好切開這兩者。
    """

    @staticmethod
    def _c(**kw):
        """六個標的預設持平,只覆寫指定的。"""
        base = {"^GSPC": 0.2, "^IXIC": 0.1, "^DJI": 0.3,
                "^SOX": -0.4, "ES=F": 0.1, "NQ=F": 0.2}
        base.update(kw)
        return base

    def test_three_markets_down_fires(self):
        from src.compute.notify.market_alert_banner import evaluate_broad_lead_selloff
        v = evaluate_broad_lead_selloff(self._c(**{"^GSPC": -1.6, "^IXIC": -2.0, "^DJI": -1.7}))
        assert v.is_fired and v.n_drops == 3

    def test_two_markets_down_does_not_fire(self):
        """反向守衛:差一個就不能響。沒有這條,把門檻寫成 >=1 也能讓上一條過,
        而那正是 user 明確不要的(一年 77 次)。"""
        from src.compute.notify.market_alert_banner import evaluate_broad_lead_selloff
        v = evaluate_broad_lead_selloff(self._c(**{"^GSPC": -1.6, "^IXIC": -2.0}))
        assert not v.is_fired and v.state == "clear"

    def test_sox_alone_crashing_does_not_fire(self):
        """整個設計的核心案例:費半單獨崩 8% 也不下動作指令 ——
        但提示層仍必須點名它(資訊不可以被吃掉)。"""
        from src.compute.notify.market_alert_banner import (
            build_alert_block,
            evaluate_broad_lead_selloff,
        )
        c = self._c(**{"^SOX": -8.0})
        assert not evaluate_broad_lead_selloff(c).is_fired
        blk = build_alert_block(_v(-1.0, +100.0), c)
        assert "降至 20%" not in blk, "單一族群大跌不該觸發動作層"
        assert "費城半導體" in blk and "-8.0%" in blk, "提示層必須照常點名"

    def test_missing_quotes_that_could_reach_threshold_are_unknown(self):
        """§1 三態:已知 2 跌 + 2 缺 → 缺的那兩個可能正在崩,**不可**說「沒有全面大跌」。"""
        from src.compute.notify.market_alert_banner import evaluate_broad_lead_selloff
        v = evaluate_broad_lead_selloff(
            {"^GSPC": -1.6, "^IXIC": -2.0, "^DJI": None, "^SOX": None,
             "ES=F": 0.1, "NQ=F": 0.2})
        assert v.state == "unknown" and v.n_missing == 2

    def test_missing_quotes_that_cannot_reach_threshold_are_clear(self):
        """反向守衛:已知 1 跌 + 1 缺 → 最多湊到 2,低於門檻 3 → CLEAR 是**算得出來**的
        結論,不是猜的。沒有這條,「有缺料一律 unknown」也能讓上一條過,那會讓
        ⬜ 區塊天天出現而失去意義。"""
        from src.compute.notify.market_alert_banner import evaluate_broad_lead_selloff
        v = evaluate_broad_lead_selloff(
            {"^GSPC": -1.6, "^IXIC": 0.1, "^DJI": None, "^SOX": -0.4,
             "ES=F": 0.1, "NQ=F": 0.2})
        assert v.state == "clear"

    def test_unknown_never_looks_like_safe(self):
        from src.compute.notify.market_alert_banner import (
            evaluate_broad_lead_selloff,
            format_broad_selloff_banner,
        )
        txt = format_broad_selloff_banner(evaluate_broad_lead_selloff({}))
        assert txt and "這不代表安全" in txt

    def test_stricter_directive_wins_when_both_layers_fire(self):
        """兩個動作層同時成立 → 只留 10%,不可以讓 20% 也印出來。
        同一則訊息出現兩個持股數字,使用者不知道該聽哪個。"""
        from src.compute.notify.market_alert_banner import build_alert_block
        c = self._c(**{"^GSPC": -1.6, "^IXIC": -2.0, "^DJI": -1.7})
        blk = build_alert_block(_v(-9.1, -612.0), c)
        assert "降至 10%" in blk
        assert "降至 20%" not in blk

    def test_broad_alone_still_gives_20(self):
        """反向守衛:台股兩腿沒事時,20% 那層必須照常出現 ——
        否則把 B 層整個關掉也能讓上一條過。"""
        from src.compute.notify.market_alert_banner import build_alert_block
        c = self._c(**{"^GSPC": -1.6, "^IXIC": -2.0, "^DJI": -1.7})
        blk = build_alert_block(_v(-1.0, +100.0), c)
        assert "降至 20%" in blk and "降至 10%" not in blk

    def test_action_flag_covers_both_layers(self):
        from src.compute.notify.market_alert_banner import has_action_directive
        c_broad = self._c(**{"^GSPC": -1.6, "^IXIC": -2.0, "^DJI": -1.7})
        assert has_action_directive(_v(-1.0, +100.0), c_broad) is True
        assert has_action_directive(_v(-9.1, -612.0), self._c()) is True
        assert has_action_directive(_v(-1.0, +100.0), self._c()) is False

    def test_unknown_is_not_an_action_directive(self):
        """⬜ 沒有叫使用者做任何事,不該抑制「今日無需動作」——
        它自己會講「這不代表安全」。"""
        from src.compute.notify.market_alert_banner import has_action_directive
        assert has_action_directive(_v(-1.0, +100.0), None) is False

    def test_threshold_matches_the_documented_evidence(self):
        """漂移鎖:門檻改了就要重跑頻率量測、重寫 L0 檔頭那張表。
        3 → 2 會讓指令從一年 13 次變成 34 次,那是行為改變不是參數微調。"""
        from shared.global_lead_markets import (
            GLOBAL_LEAD_DROP_PCT,
            LEAD_BROAD_DROP_MIN_MARKETS,
            LEAD_MARKETS,
            LEAD_TARGET_POSITION_PCT,
        )
        assert LEAD_BROAD_DROP_MIN_MARKETS == 3
        assert LEAD_TARGET_POSITION_PCT == 20
        assert GLOBAL_LEAD_DROP_PCT == -1.5
        assert len(LEAD_MARKETS) == 6


class TestMacroLineRemoved:
    """user 2026-08-24 指定移除「🧭 總經位階」整行(LINE + AI prompt 兩邊)。"""

    def test_message_has_no_macro_regime_line(self):
        from src.compute.notify.holdings_digest_message import format_holdings_message
        msg = format_holdings_message(
            {"vix": 15.9, "total": 14, "adds": [], "take_profit": [], "reds": []},
            {"loaded": True, "regime": "bull", "posture": "🟢 進攻",
             "posture_range": "70–90%", "switch_out": [], "switch_in": []},
            as_of="2026-08-24 06:30")
        assert "總經位階" not in msg
        assert "bull" not in msg and "70–90%" not in msg
        assert "VIX：15.9" in msg, "移除位階不得誤傷相鄰的 VIX 行"


class TestVixPlainLanguageAdvice:
    """VIX 從「裸數字」改成「數字 + 一句該怎麼辦」(user 2026-08-24)。

    原本只印「😱 VIX：15.9」—— 對不看盤的人等於沒有資訊。
    """

    @staticmethod
    def _msg(vix):
        from src.compute.notify.holdings_digest_message import format_holdings_message
        return format_holdings_message(
            {"vix": vix, "total": 14, "adds": [], "take_profit": [], "reds": []},
            {"switch_out": [], "switch_in": []}, as_of="2026-08-25 06:30")

    def test_calm_vix_gives_actionable_advice(self):
        msg = self._msg(15.9)
        assert "VIX：15.9" in msg, "數字本身必須保留（user 明確要求保留這行）"
        assert "市場平靜" in msg and "定期定額" in msg

    def test_panic_vix_says_do_not_catch_falling_knife(self):
        msg = self._msg(38.2)
        assert "市場恐慌" in msg and "接刀" in msg

    def test_elevated_vix_is_distinct_from_both(self):
        """反向守衛:黃燈不可以跟綠燈或紅燈講一樣的話 ——
        否則寫成「一律回同一句」也能讓上面兩條過。

        註:斷言只看 `_vix_line` 的輸出,不看整則訊息 —— 訊息別處另有一句
        「今日無需動作:續抱、定期定額即可」,拿整則訊息比對會誤判。"""
        from src.compute.notify.holdings_digest_message import _vix_line
        _advice = [_vix_line(v, 14)[1] for v in (15.9, 24.0, 38.2)]
        assert "波動升高" in _vix_line(24.0, 14)[0]
        assert "定期定額" not in _advice[1] and "接刀" not in _advice[1]
        assert len(set(_advice)) == 3, "三級建議必須互不相同"

    def test_missing_vix_gives_no_advice_at_all(self):
        """§1:抓不到就不准給建議。沒有數字卻說「照原計畫」等於捏造一個平靜結論。

        同上,只看 VIX 那兩行 —— 訊息別處的「續抱、定期定額」是個股健檢的結論,
        與波動度判讀無關,不該被這條守衛掃到。"""
        from src.compute.notify.holdings_digest_message import _vix_line
        _lines = _vix_line(None, 14)
        assert "抓取失敗" in _lines[0]
        assert "不是「市場平靜」" in _lines[1]
        _joined = "".join(_lines)
        assert "定期定額" not in _joined and "分批" not in _joined, \
            "缺值時 VIX 段不得給任何動作建議"
        assert "抓取失敗" in self._msg(None), "整則訊息仍須印出這行"

    def test_thresholds_come_from_ssot_not_inline(self):
        """VIX 分級必須走全站 SSOT（黃 22 / 紅 30），不可在推播模組另寫一套 ——
        否則同一個 VIX 值，推播與看板會講不一樣的話。"""
        import inspect

        from shared.macro_buckets import SPECS_BY_KEY
        from src.compute.notify import holdings_digest_message as m

        _spec = SPECS_BY_KEY["vix"]
        assert (_spec.yellow, _spec.red) == (22.0, 30.0)
        # 邊界對齊 SSOT：21.9 綠、22.0 黃、29.9 黃、30.0 紅
        assert "市場平靜" in self._msg(_spec.yellow - 0.1)
        assert "波動升高" in self._msg(_spec.yellow)
        assert "波動升高" in self._msg(_spec.red - 0.1)
        assert "市場恐慌" in self._msg(_spec.red)
        # 原始碼（**扣掉 docstring**）不得出現 inline 門檻（§3.3）。
        # docstring 本來就要寫明「黃 22 / 紅 30」讓讀的人知道走哪套 SSOT,
        # 那是說明不是邏輯 —— 守衛只該看真正會執行的那幾行。
        _src = inspect.getsource(m._vix_line)
        _body = _src.replace(m._vix_line.__doc__ or "", "")
        assert "22" not in _body and "30" not in _body, "VIX 門檻被寫死在推播模組"
