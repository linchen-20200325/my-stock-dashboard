"""tests/test_station_specs.py — 戰情室燈號規格表守衛（2026-08-25）

## 這個規格表在解什麼問題

戰情室現行把**四種完全不同的意思**畫成同一個 ⚪：

| 出處 | 意思 |
|---|---|
| `Flag.level="⚪"` | 該項缺輸入 |
| `_error_row` 的健檢欄 | **整檔抓取失敗** |
| `health_d`（個股） | **這類持股不適用** |
| `suggest_action` | **⚪ 巡航：維持定期定額 ← 一切正常！** |

也就是在主表裡，「一切正常」跟「什麼都沒抓到」長得一模一樣。
user 2026-08-25 拍板拆開。

## 這些測試守什麼

1. **規格表不得與實作漂移** —— 燈的數量、kind 分流必須對得上 L2 實際產出的
   assessment 欄位。規格表寫 8 盞但實作只算 7 盞，畫面就會有一格永遠空著。
2. **門檻文字不得寫死數字** —— 全部由 `dividend_station_thresholds` 組出。
   寫死就會出現「規格表寫 1.5% 但實作用 2%」那種只有讀 code 才看得出來的謊。
3. **旗標必填理由** —— 標了 `wired=False` / `discriminative=False` 卻不說原因，
   等於「這盞燈不能信，但我不告訴你為什麼」，比不標更糟。
4. **四態符號互斥** —— 這是本次改動的**核心目的**，四個狀態不得共用符號。

⚠️ **這裡測得住什麼、測不住什麼（寫給後人，請不要假裝它測得更多）**

`threshold_text` 裡的**數字**釘得住:每個數字都必須來自登錄過的 SSOT 常數
（見 `PINNED_SSOT_NUMBERS`），多一個沒登錄的數字就當場紅。

`source` 裡的**數字**同樣釘得住（2026-08-26 補齊）。原本這一段寫「`source`
釘不住」而把守衛只做在 `threshold_text` 上 —— 但當時判定「最嚴重」的那一筆
（`health_b` 宣稱「無風險利率視為 0」，實際 5.33%）**就住在 `source`**。
用「哪一種比較嚴重」排優先序、卻用「欄位名」劃守衛範圍，是兩把不一致的尺;
結果最嚴重的那一類反而只有一條點狀斷言、沒有進掃描。現已比照辦理，
`source` 的數字走 `PINNED_SSOT_SOURCE_NUMBERS` + 反向掃描（見第二節）。

`source` / `why` 的**文意**仍然釘不住。「5 年日報酬年化」寫成「週報酬 ×√52
年化」是對是錯，沒有任何斷言判得出來 —— `health_b` 那句連數字都沒寫錯，
它寫的 `0` 是個「正確地寫出來的錯誤事實」，**再嚴的數字掃描也掃不到**;
同理 `screen_return` 的門檻曾寫「需為正報酬」而實作要年化 ≥ 7%。

所以這類漂移只有一個防線:**改判燈邏輯的那個 PR 裡順手檢查同一盞燈的
`source` / `why`**，而不是事後再掃一輪。事後掃描找得到的是「讀起來怪」的，
找不到的是「讀起來很合理但不是程式在做的事」的 —— 後者才是危險的那種。

⚠️ 本檔只測 L0 純資料，**不啟動 Streamlit、不做網路 I/O**。
"""
from __future__ import annotations

import re

import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from shared.signal_thresholds import ETF_SHARPE_RF_FALLBACK_PCT
from shared.station_specs import (
    AXIS_LABELS,
    LIGHT235_AXES,
    MISS_PRIORITY,
    MISS_TEXT,
    SPECS_BY_KEY,
    STATE_DEGRADED,
    STATE_LIVE,
    STATE_META,
    STATE_MISSING,
    STATE_UNWIRED,
    STATION_SPECS,
    axes_text,
    classify_state,
    most_fundamental_miss,
    specs_for,
)

#: 目前唯一被標記門檻失準者。新增時本清單要同步 —— 強迫「標記」是有意識的決定，
#: 而不是有人順手加個 flag 就悄悄改變了一盞燈的可信度語意。
KNOWN_DEGRADED: frozenset[str] = frozenset({"stock_trend"})
KNOWN_UNWIRED: frozenset[str] = frozenset()
#: 目前唯一宣告「依規格就不出等級」者（2026-08-26 user 裁示，個股 KD）。
#: 同 KNOWN_DEGRADED 的用意：這個旗標會**把一盞燈移出可信度分母**，
#: 亦即會讓畫面上的分數變好看 —— 更不該有人順手加上去而沒被任何人看見。
KNOWN_NO_LEVEL: frozenset[str] = frozenset({"stock_kd"})


# ════════════════════════════════════════════════════════════════
# 一、規格表與實作不得漂移
# ════════════════════════════════════════════════════════════════
class TestRegistryMatchesImplementation:

    def test_etf_has_eight_lights(self):
        """ETF 8 盞：健檢 A/B/C/D + 235 + 3-3-3 三子項。

        數字來自 `assess_holding` 實際產出的 `HoldingAssessment` 欄位
        （health_a/b/c/d + light + screen 的三個 bool）。
        """
        assert len(specs_for(T.KIND_ETF)) == 8

    def test_stock_has_four_lights(self):
        """個股 4 盞：財報體檢 / 財報趨勢 / KD / 汰換建議。

        對應 `_STOCK_COLS` 的後四欄。**個股不走 `assess_holding`** ——
        service 是二選一分流（`dividend_station_service` 的 `ak == KIND_STOCK`
        分支走 `assess_stock`），所以 A/B/C/D 不適用個股。
        """
        assert len(specs_for(T.KIND_STOCK)) == 4

    def test_kinds_do_not_overlap_by_accident(self):
        """ETF 與個股的燈目前完全不重疊。若哪天真的有共用燈（kind="both"），
        改這條並在 PR 說明為什麼 —— 不要讓它悄悄發生。"""
        etf = {s.key for s in specs_for(T.KIND_ETF)}
        stock = {s.key for s in specs_for(T.KIND_STOCK)}
        assert not (etf & stock), f"意外重疊:{sorted(etf & stock)}"
        assert etf | stock == {s.key for s in STATION_SPECS}

    def test_keys_are_unique(self):
        keys = [s.key for s in STATION_SPECS]
        assert len(keys) == len(set(keys)), "spec key 重複"

    def test_every_spec_declares_a_valid_kind(self):
        for s in STATION_SPECS:
            assert s.kind in (T.KIND_ETF, T.KIND_STOCK, "both"), \
                f"{s.key} 的 kind={s.kind!r} 不合法"

    def test_every_spec_declares_a_direction(self):
        for s in STATION_SPECS:
            assert s.direction in ("high_bad", "low_bad", "band", "categorical"), \
                f"{s.key} 的 direction={s.direction!r} 不合法"


# ════════════════════════════════════════════════════════════════
# 二、§3.3 反捏造：門檻不得寫死
# ════════════════════════════════════════════════════════════════
#: 門檻文字裡**每一個數字**的 SSOT 出處。`(燈 key, 該常數算出來的字串, 常數名)`。
#:
#: 為什麼要窮舉到這種程度:2026-08-26 的稽核顯示，規格表 9 項敘述問題裡至少 3 項
#: 是「改了 code 忘了改字」。舊版本這張表只有 5 個 key、而且只檢查「某個數字有出現
#: 在字串裡」—— 連它涵蓋的 `light235` 都漏了三段加碼的 −1σ/−2σ/−3σ（那三個當時
#: 根本是寫死的字面值，不是從 `Z_LIGHT*` 組出來的）。**表列不全 = 漏的那幾個從來
#: 沒有被守過**，而漏掉哪幾個又完全看不出來。故改為「窮舉 + 反向掃描」兩面夾:
#:   · 正向（`test_threshold_text_reflects_ssot`）：登錄的常數值必須出現在文字裡
#:     → 上游改常數、文字沒跟著動 = 紅。
#:   · 反向（`test_no_unpinned_number_in_threshold_text`）：文字裡出現的數字必須
#:     登錄過 → 有人手寫一個新數字進去 = 紅（§3.3 inline magic number）。
#: 兩條合起來才是「每個寫了數字的 threshold_text 都釘住它的 SSOT 常數」。
PINNED_SSOT_NUMBERS: tuple[tuple[str, str, str], ...] = (
    ("health_b",         f"{T.SHARPE_NEG_THRESHOLD:g}",         "SHARPE_NEG_THRESHOLD"),
    ("health_c",         f"{T.MA_QUARTER_WEEKS:g}",             "MA_QUARTER_WEEKS"),
    ("health_d",         f"{T.PREMIUM_ALERT_PCT:g}",            "PREMIUM_ALERT_PCT"),
    ("light235",         f"{T.BOLL_PERIOD_WEEKS:g}",            "BOLL_PERIOD_WEEKS"),
    # 三段加碼的 σ 帶。文字排版寫「−Nσ」,負號是排版、數值取 abs（見規格表註解）,
    # 故釘 abs 值 —— 這三個常數依定義恆為負。
    ("light235",         f"{abs(T.Z_LIGHT1):g}",                "Z_LIGHT1"),
    ("light235",         f"{abs(T.Z_LIGHT2):g}",                "Z_LIGHT2"),
    ("light235",         f"{abs(T.Z_LIGHT3):g}",                "Z_LIGHT3"),
    ("light235",         f"{T.Z_TAKE_PROFIT_PARTIAL:g}",        "Z_TAKE_PROFIT_PARTIAL"),
    ("light235",         f"{T.Z_TAKE_PROFIT_FORCE:g}",          "Z_TAKE_PROFIT_FORCE"),
    ("screen_inception", f"{T.MIN_INCEPTION_YEARS:g}",          "MIN_INCEPTION_YEARS"),
    ("screen_return",    f"{T.MIN_ANN_RETURN_3Y_PCT:g}",        "MIN_ANN_RETURN_3Y_PCT"),
    ("screen_return",    f"{T.MIN_CUM_RETURN_3Y_PCT:g}",        "MIN_CUM_RETURN_3Y_PCT"),
    ("screen_peer",      f"{round(1 / T.PEER_TOP_FRACTION):g}", "PEER_TOP_FRACTION"),
) + tuple(("screen_peer", f"{_m:g}", "PEER_WINDOWS_MONTHS") for _m in T.PEER_WINDOWS_MONTHS)

#: 反向掃描的**唯一豁免**:屬於「寫法」而非「門檻」的數字。
#:
#: ⚠️ 這是個逃生門,加東西進來前先想清楚 —— 只有「改了它不等於改了門檻」的數字
#: 才該進來。目前唯一一筆是「前 1/3」的**分子 1**:分母 3 由
#: `PEER_TOP_FRACTION` 算出（已登錄在上表）,分子的 1 是分數記法的一部分,
#: 不是可調參數。若哪天有人想把新門檻塞進這裡以求測試變綠,那就是本表被誤用了。
NOTATION_LITERALS: dict[str, frozenset[str]] = {
    "screen_peer": frozenset({"1"}),
}

#: 抓「整數」與「小數」兩種寫法。刻意**不**抓負號 —— 規格表的負號是排版符號
#: U+2212「−」而非 ASCII "-",且數值一律以 abs 登錄（見上表 σ 帶說明）。
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _allowed_numbers(key: str) -> set[str]:
    """某盞燈的門檻文字裡「可以出現」的數字 = 登錄的 SSOT 值 + 記法豁免。"""
    return ({n for k, n, _ in PINNED_SSOT_NUMBERS if k == key}
            | set(NOTATION_LITERALS.get(key, frozenset())))


# ── `source` 欄的數字（2026-08-26 補齊）────────────────────────────────────
#
# 為什麼要補:上一輪把「最嚴重」的一筆判給 `health_b.source`（宣稱「無風險利率
# 視為 0」，實際取即時 FEDFUNDS、fallback 5.33%），卻把守衛範圍劃在
# `threshold_text` —— **用「哪一種比較嚴重」排優先序、用「欄位名」劃範圍**，
# 兩把尺不一致。結果 `screen_return` 那一類進了掃描，`health_b` 那一類只留下
# 一條點狀斷言。這一節把 `source` 比照 `threshold_text` 辦理。
#
# 三張表的分工（**刻意分三張，不是一張加旗標**）:
#   1. `PINNED_SSOT_SOURCE_NUMBERS` —— 有 SSOT 常數可釘。上游改值，這裡自動跟。
#   2. `SOURCE_NOTATION_LITERALS`   —— **記法 / 固定事實**，改變它不等於改門檻
#      （一年 365 天、一年 52 週）。每一筆都必須答得出「這個數字變了，
#      為什麼不需要有人注意」。
#   3. `SOURCE_UNPINNED_UPSTREAM`   —— **既知欠債**:它確實是可調參數，但上游
#      就是把它寫死在呼叫端、沒有 SSOT 常數。這一格**不是豁免**，是把 §3.3 的
#      違憲**寫在明面上**並指出兇手在哪一行。
#
# ⚠️ 這三張表都**不准**用來「讓測試變綠」。特別是第 3 張:遇到沒有 SSOT 的數字，
#    正確處置是登錄成欠債 + 回報，**不是**在 `shared/` 新造一個常數把它包起來 ——
#    那只是把違憲藏進一個看起來合規的名字裡。
PINNED_SSOT_SOURCE_NUMBERS: tuple[tuple[str, str, str], ...] = (
    # `health_b` 的無風險利率 fallback。這一筆是本輪的起點:它寫錯時
    # （原文「視為 0」）畫面會讓使用者把「rf=5.33% 下為負」讀成「連 0 都跑不贏」。
    ("health_b",    f"{ETF_SHARPE_RF_FALLBACK_PCT:g}", "ETF_SHARPE_RF_FALLBACK_PCT"),
    # 235 的布林週期。與同一盞燈 `threshold_text` 用的是**同一個**常數 ——
    # 原本來源欄寫死 `20`，上游改週期時門檻欄會動、來源欄不會，同一張卡自相矛盾。
    ("light235",    f"{T.BOLL_PERIOD_WEEKS:g}",        "BOLL_PERIOD_WEEKS"),
    # 同儕排名的最小同類檔數。
    ("screen_peer", f"{T.PEER_MIN_GROUP_SIZE:g}",      "PEER_MIN_GROUP_SIZE"),
)

#: 記法 / 固定事實。**值是理由字串，不是註解** —— 強迫每一筆寫下「為什麼它改變時
#: 不需要有人注意」，寫不出來的就不該進這張表。
SOURCE_NOTATION_LITERALS: dict[str, dict[str, str]] = {
    "health_a": {
        "365": "一年的日曆天數。這裡刻意講「回推 365 天」而不是「近一年」,"
               "因為它是**日曆日**不是交易日(§4.1),寫清楚才對得上上游的 "
               "`pd.Timedelta(days=365)`。曆法不會改。",
    },
    "health_b": {
        "52": "一年的週數,週報酬年化因子 √52 的那個 52(上游 `sharpe_weekly` 的 "
              "`math.sqrt(52.0)` 與 `rf/100/52`)。它是曆法常數,不是可調門檻 —— "
              "⚠️ 特別注意它**不是** `MA_YEAR_WEEKS`(52 週年線):數字相同、意思不同,"
              "釘過去會做出「改年線週期連帶改年化因子」這種假耦合(§3.3)。",
    },
}

#: 既知欠債:上游確實把它寫死在呼叫端,沒有 SSOT 常數可釘。值 = 兇手在哪。
#: **登錄在這裡不等於它沒問題** —— 它等於「有人看過、知道它是欠債、且沒有偷造常數」。
SOURCE_UNPINNED_UPSTREAM: dict[str, dict[str, str]] = {
    "health_a": {
        "5": "日線資料窗 5 年。上游 `dividend_station_service.fetch_metrics` 直接寫 "
             "`fetch_etf_price(_yf, period=\"5y\")`,無常數。",
    },
    "health_b": {
        "5": "同上,同一個 `period=\"5y\"` 資料窗。",
        "0": "無風險利率**連取值本身都失敗**時的最後退路。上游 `fetch_metrics` 的 "
             "except 分支寫 "
             "`_rf_ds = 0.0`(註解自陳「等同修前行為」),沒有常數 —— 若哪天有人把它改成"
             "退 `ETF_SHARPE_RF_FALLBACK_PCT`,這句話就得跟著改,所以它不是記法。",
    },
    "screen_return": {
        "5": "同上,同一個 `period=\"5y\"` 資料窗。",
        "3": "3 年報酬的回看年數。上游寫 `_close_before(365 * 3)` / "
             "`annualized_return_pct(..., 3.0)`,是字面值;⚠️ **不可**釘 "
             "`MIN_INCEPTION_YEARS`(也是 3):那是「成立滿幾年」的門檻,與「回看幾年」"
             "無關,數字相同純屬巧合。",
    },
    "stock_kd": {
        "360": "個股日線回看天數。上游 `_fetch_stock_metrics` 寫 "
               "`StockDataLoader().get_combined_data(code, 360, True)`,是字面值。",
    },
}


def _allowed_source_numbers(key: str) -> set[str]:
    """某盞燈的來源文字裡「可以出現」的數字。

    **刻意與 `_allowed_numbers`（門檻文字）分開算** —— 同一盞燈在門檻欄合法的數字，
    在來源欄未必是同一個意思（`screen_peer` 的 `3` 在門檻欄是「前 1/3」的分母、
    在來源欄是「同類至少幾檔」，兩個 `3` 各有各的 SSOT）。合併算會讓其中一個
    悄悄借用另一個的登錄而不被發現。
    """
    return ({n for k, n, _ in PINNED_SSOT_SOURCE_NUMBERS if k == key}
            | set(SOURCE_NOTATION_LITERALS.get(key, {}))
            | set(SOURCE_UNPINNED_UPSTREAM.get(key, {})))


class TestNoHardcodedThresholds:

    @pytest.mark.parametrize(
        "key,needle,ssot_name", PINNED_SSOT_NUMBERS,
        ids=[f"{k}-{name}" for k, _, name in PINNED_SSOT_NUMBERS],
    )
    def test_threshold_text_reflects_ssot(self, key, needle, ssot_name):
        """門檻文字必須含當前 SSOT 值 —— 改上游常數，這裡自動跟著改。

        這條會在「有人改了 SSOT 但規格表文字沒跟著動」時紅，
        也就是漂移發生的**當下**，而不是等使用者看到不一致的畫面。
        """
        assert needle in SPECS_BY_KEY[key].threshold_text, (
            f"{key} 的門檻文字沒反映 SSOT 值 {needle!r}（來自 {ssot_name}）："
            f"{SPECS_BY_KEY[key].threshold_text!r}"
        )

    @pytest.mark.parametrize("spec", STATION_SPECS, ids=lambda s: s.key)
    def test_no_unpinned_number_in_threshold_text(self, spec):
        """反向:門檻文字裡出現的每個數字都必須登錄過（§3.3 反捏造）。

        正向那條只保證「登錄的有出現」，擋不住**新增**一個手寫數字 ——
        而規格表的漂移正是這樣長出來的（有人加一段門檻說明，順手把數字打上去，
        上游常數改了它不會動）。這條把「沒登錄的數字」變成當場紅燈。
        """
        found = set(_NUMBER_RE.findall(spec.threshold_text))
        stray = found - _allowed_numbers(spec.key)
        assert not stray, (
            f"{spec.key} 的門檻文字有沒登錄出處的數字 {sorted(stray)} —— "
            f"要嘛改用 f-string 從 SSOT 常數組出並登錄到 PINNED_SSOT_NUMBERS，"
            f"要嘛它根本不該是數字。**不要為了讓這條變綠而自己發明一個常數**："
            f"若上游確實沒有對應 SSOT，那是 §3.3 違憲，該另案處理。\n"
            f"    {spec.threshold_text!r}"
        )

    def test_every_spec_with_numbers_is_covered(self):
        """涵蓋率自檢:門檻文字寫了數字的燈，都必須至少登錄一筆 SSOT 出處。

        這條擋的是「整盞燈漏登」—— 舊版只涵蓋 5 個 key，而**漏了哪幾個
        從測試本身完全看不出來**（沒被守的燈與被守的燈長得一模一樣）。
        """
        pinned_keys = {k for k, _, _ in PINNED_SSOT_NUMBERS}
        with_numbers = {s.key for s in STATION_SPECS
                        if _NUMBER_RE.search(s.threshold_text)}
        assert with_numbers - pinned_keys == set(), (
            f"這些燈的門檻文字有數字卻完全沒登錄 SSOT 出處："
            f"{sorted(with_numbers - pinned_keys)}"
        )

    def test_pinned_and_notation_keys_are_real_specs(self):
        """登錄表不得指向不存在的燈（改了 key 卻忘了改測試 → 守衛靜默失效）。"""
        for k, _, _ in PINNED_SSOT_NUMBERS:
            assert k in SPECS_BY_KEY, f"PINNED_SSOT_NUMBERS 指向不存在的燈:{k}"
        for k in NOTATION_LITERALS:
            assert k in SPECS_BY_KEY, f"NOTATION_LITERALS 指向不存在的燈:{k}"

    def test_peer_window_months_come_from_ssot(self):
        txt = SPECS_BY_KEY["screen_peer"].threshold_text
        for m in T.PEER_WINDOWS_MONTHS:
            assert f"{m}M" in txt, f"同儕時間框 {m}M 沒出現在門檻文字"

    def test_stock_grades_come_from_ssot(self):
        txt = SPECS_BY_KEY["stock_health"].threshold_text
        for g in T.STOCK_HEALTH_GRADES:
            assert g in txt, f"評等 {g} 沒出現在門檻文字"

    def test_health_b_source_states_the_real_risk_free_rate(self):
        """`source` 的**文意**釘不住（見檔頭），但它寫出來的那個利率釘得住。

        ⚠️ 數字那一半現已由 `TestSourceNumbersArePinned` 的掃描涵蓋
        （`ETF_SHARPE_RF_FALLBACK_PCT` 登錄在 `PINNED_SSOT_SOURCE_NUMBERS`）。
        本條留著是為了它的**另一半**:「FEDFUNDS」這三個字 —— 少了它，
        `5.33` 會被讀成一個寫死的設定值，而不是「取不到即時利率時的退路」。

        2026-08-26 修正前這裡寫「無風險利率視為 0」，而實作取的是即時 FEDFUNDS、
        取不到才退 SSOT fallback。這盞燈的門檻是 `Sharpe < 0`，rf 直接平移分子 ——
        **rf=0 與 rf=5.33% 會判出不同燈色**，也就是畫面在對使用者說一個
        會讓他做錯決定的數字（§1）。故把 fallback 值本身釘在這裡。
        """
        src = SPECS_BY_KEY["health_b"].source
        assert f"{ETF_SHARPE_RF_FALLBACK_PCT:g}" in src, (
            f"health_b 的來源沒寫出實際採用的無風險利率 fallback："
            f"{src!r}"
        )
        assert "FEDFUNDS" in src, (
            f"health_b 的來源沒說 rf 取自即時 FEDFUNDS（會被讀成寫死值）：{src!r}"
        )


def _literal_numbers_in_spec_source() -> dict[str, set[str]]:
    """用 AST 讀出每盞燈的 `source` 裡**寫死**（非 f-string 代入）的數字。

    為什麼需要這一層（**這是本檔最容易被誤解的一段，請先讀完再改**）:
    值比對（`PINNED_SSOT_*`）只證明「文字裡的數字**等於**現在的 SSOT 值」——
    有人把 `{T.BOLL_PERIOD_WEEKS}` 改回寫死 `20`，測試**照樣綠**，因為 20 這時
    的確等於常數值。實測驗證過:單獨把 f-string 改回字面值，132 條全過;
    要等到有人動了上游常數才會紅 —— 那時漂移已經發生了。

    所以再加一道**寫法**檢查:把字串拆成「靜態片段」與「格式化欄位」，
    出現在靜態片段裡的數字就是寫死的。寫死的數字只准是記法或既知欠債;
    凡是宣稱「釘住 SSOT」的數字，就不准同時是寫死的 —— 兩者只能擇一為真。

    回傳 `{spec.key: {寫死的數字}}`（只看 `source`;門檻文字另有一份）。
    """
    import ast
    import pathlib

    src = pathlib.Path(SS.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    elts = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "STATION_SPECS":
            elts = node.value.elts
        elif isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "STATION_SPECS" for t in node.targets):
            elts = node.value.elts
    # §1:解析不到就當場炸，不要靜默回空 dict（那會讓整條守衛變成永遠通過的裝飾品）。
    assert elts is not None, "AST 找不到 STATION_SPECS —— 這條守衛已失效，請修"
    assert len(elts) == len(STATION_SPECS), (
        f"AST 讀到 {len(elts)} 筆、實際 {len(STATION_SPECS)} 筆 —— 對不起來就不能信")

    def _static_text(node) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):      # f-string:只取字面片段
            return "".join(v.value for v in node.values
                           if isinstance(v, ast.Constant) and isinstance(v.value, str))
        return ""                                # 其他運算式 → 沒有字面片段

    out: dict[str, set[str]] = {}
    for spec, call in zip(STATION_SPECS, elts):
        txt = "".join(_static_text(kw.value) for kw in call.keywords
                      if kw.arg == "source")
        out[spec.key] = set(_NUMBER_RE.findall(txt))
    return out


class TestSourceNumbersArePinned:
    """`source` 欄的數字比照 `threshold_text` 辦理（2026-08-26）。

    ⚠️ 這一組守的是**數字**，不是文意。`health_b.source` 那句「無風險利率視為 0」
    當年寫的 `0` 語法上完全合法、數字上也「正確地」寫出了一個錯誤的事實 ——
    本組擋得住的是「上游改了 5.33 這裡沒跟著改」，擋不住「一開始就寫錯」。
    後者的唯一防線仍然是:改判燈邏輯的那個 PR 裡順手看一眼同一盞燈的 `source`。
    """

    @pytest.mark.parametrize(
        "key,needle,ssot_name", PINNED_SSOT_SOURCE_NUMBERS,
        ids=[f"{k}-{name}" for k, _, name in PINNED_SSOT_SOURCE_NUMBERS],
    )
    def test_source_reflects_ssot(self, key, needle, ssot_name):
        """來源文字必須含當前 SSOT 值 —— 改上游常數，這裡自動跟著改。"""
        assert needle in SPECS_BY_KEY[key].source, (
            f"{key} 的來源文字沒反映 SSOT 值 {needle!r}（來自 {ssot_name}）："
            f"{SPECS_BY_KEY[key].source!r}"
        )

    @pytest.mark.parametrize("spec", STATION_SPECS, ids=lambda s: s.key)
    def test_no_unpinned_number_in_source(self, spec):
        """反向:來源文字裡每個數字都必須登錄過（SSOT / 記法 / 既知欠債 三者之一）。

        這條擋的是「有人在來源欄補一段說明、順手把數字打上去」——
        `light235.source` 的「20 週布林」正是這樣長出來的（隔壁就是
        `BOLL_PERIOD_WEEKS`，但它是寫死的）。
        """
        found = set(_NUMBER_RE.findall(spec.source))
        stray = found - _allowed_source_numbers(spec.key)
        assert not stray, (
            f"{spec.key} 的來源文字有沒登錄出處的數字 {sorted(stray)} —— "
            f"三條路:(a) 上游有 SSOT 常數 → 改 f-string 並登錄 "
            f"PINNED_SSOT_SOURCE_NUMBERS;(b) 它是記法/固定事實 → 登錄 "
            f"SOURCE_NOTATION_LITERALS 並寫明為什麼它改變時不需要有人注意;"
            f"(c) 它是可調參數但上游沒有 SSOT → 登錄 SOURCE_UNPINNED_UPSTREAM "
            f"並指出兇手在哪一行。**不准為了讓這條變綠而自己造一個常數**。\n"
            f"    {spec.source!r}"
        )

    def test_every_spec_with_numbers_in_source_is_registered(self):
        """涵蓋率自檢:來源寫了數字的燈，都必須至少登錄一筆出處。

        擋的是「整盞燈漏登」—— 沒被守的燈與被守的燈在測試報告上長得一模一樣。
        """
        registered = ({k for k, _, _ in PINNED_SSOT_SOURCE_NUMBERS}
                      | set(SOURCE_NOTATION_LITERALS) | set(SOURCE_UNPINNED_UPSTREAM))
        with_numbers = {s.key for s in STATION_SPECS if _NUMBER_RE.search(s.source)}
        assert with_numbers - registered == set(), (
            f"這些燈的來源文字有數字卻完全沒登錄："
            f"{sorted(with_numbers - registered)}"
        )

    def test_source_registries_point_at_real_specs(self):
        """登錄表不得指向不存在的燈（改了 key 卻忘了改測試 → 守衛靜默失效）。"""
        for _k in ({k for k, _, _ in PINNED_SSOT_SOURCE_NUMBERS}
                   | set(SOURCE_NOTATION_LITERALS) | set(SOURCE_UNPINNED_UPSTREAM)):
            assert _k in SPECS_BY_KEY, f"來源登錄表指向不存在的燈:{_k}"

    def test_a_number_is_registered_in_exactly_one_table(self):
        """同一個 (燈, 數字) 不得同時登錄在兩張表 —— 那代表沒人說得清它到底是什麼。"""
        for spec in STATION_SPECS:
            pinned = {n for k, n, _ in PINNED_SSOT_SOURCE_NUMBERS if k == spec.key}
            notation = set(SOURCE_NOTATION_LITERALS.get(spec.key, {}))
            debt = set(SOURCE_UNPINNED_UPSTREAM.get(spec.key, {}))
            for a, b, why in ((pinned, notation, "SSOT/記法"),
                              (pinned, debt, "SSOT/欠債"),
                              (notation, debt, "記法/欠債")):
                assert not (a & b), f"{spec.key} 的 {sorted(a & b)} 同時登錄在{why}兩張表"

    def test_every_registered_literal_has_a_written_reason(self):
        """記法與欠債**每一筆**都要寫理由。

        逃生門只要允許「登錄了就過」，下一個人就會把新門檻塞進來求綠燈。
        寫得出理由是唯一的門檻:記法要答得出「它改變時為什麼不需要有人注意」，
        欠債要指得出兇手在上游哪一行。
        """
        for table, name in ((SOURCE_NOTATION_LITERALS, "SOURCE_NOTATION_LITERALS"),
                            (SOURCE_UNPINNED_UPSTREAM, "SOURCE_UNPINNED_UPSTREAM")):
            for key, entries in table.items():
                for num, reason in entries.items():
                    assert len(reason.strip()) >= 20, \
                        f"{name}[{key}][{num}] 的理由過短（等於沒寫）:{reason!r}"

    def test_no_stale_escape_hatch(self):
        """登錄過的記法 / 欠債數字**必須真的還出現在那盞燈的文字裡**。

        ⚠️ 這條是為了堵逃生門的長效風險:白名單一旦登錄就永久有效 ——
        `NOTATION_LITERALS` 為「前 1/3」登錄了 `1`，此後在那盞燈寫任何 `1`
        都不會紅。留著失效的登錄等於**預先授權**了未來某個還沒寫出來的數字。
        本條把「文案改了、登錄沒清」變成當場紅燈，讓白名單只在它真的還被用到時存在。
        （擋不住「同一盞燈剛好又出現同一個數字」—— 白名單的本質就是這樣，
        所以第一道防線仍然是「每一筆都要寫得出理由」。）
        """
        for key, entries in SOURCE_NOTATION_LITERALS.items():
            found = set(_NUMBER_RE.findall(SPECS_BY_KEY[key].source))
            assert set(entries) <= found, (
                f"{key} 的來源記法登錄了 {sorted(set(entries) - found)}，"
                f"但文字裡已經沒有這些數字 —— 請刪掉失效的登錄")
        for key, entries in SOURCE_UNPINNED_UPSTREAM.items():
            found = set(_NUMBER_RE.findall(SPECS_BY_KEY[key].source))
            assert set(entries) <= found, (
                f"{key} 的來源欠債登錄了 {sorted(set(entries) - found)}，"
                f"但文字裡已經沒有這些數字 —— 那筆欠債若已還清請刪掉登錄")
        for key, nums in NOTATION_LITERALS.items():
            found = set(_NUMBER_RE.findall(SPECS_BY_KEY[key].threshold_text))
            assert set(nums) <= found, (
                f"{key} 的門檻記法登錄了 {sorted(set(nums) - found)}，"
                f"但文字裡已經沒有這些數字 —— 請刪掉失效的登錄")

    def test_ssot_pinned_numbers_are_not_written_literally(self):
        """宣稱「釘住 SSOT」的數字，不准同時被寫死在字串裡。

        ⚠️ **這條補的是值比對的盲點，不是重複它。** 值比對只會在上游常數改了、
        文字沒跟著改時紅 —— 也就是漂移**已經發生之後**。有人把 f-string 改回
        字面值時，數字仍等於當下的常數值，值比對全綠（實測確認）。
        本條直接看**寫法**:靜態片段裡出現的數字就是寫死的，
        而寫死的數字不可能「上游改了會自動跟著動」。

        紅了怎麼修:把那個數字改回 f-string 從 SSOT 常數組出。
        **不要**改成把它登錄進記法/欠債表 —— 它明明有 SSOT 常數可用。
        """
        literal = _literal_numbers_in_spec_source()
        for key, _needle, ssot_name in PINNED_SSOT_SOURCE_NUMBERS:
            assert _needle not in literal.get(key, set()), (
                f"{key} 的來源文字把 {_needle!r} 寫死了，卻宣稱它來自 {ssot_name} —— "
                f"現在數值剛好相同所以看不出來，上游一改就漂移。"
                f"請改成 f-string 從 SSOT 常數組出。")

    def test_literal_numbers_in_source_are_all_registered(self):
        """反過來:寫死在來源文字裡的數字，只准是記法或既知欠債。

        （沒有 SSOT 可釘的數字本來就只能寫死 —— 但必須有人登錄過、
        寫得出它為什麼沒被釘。）
        """
        literal = _literal_numbers_in_spec_source()
        for key, nums in literal.items():
            allowed = (set(SOURCE_NOTATION_LITERALS.get(key, {}))
                       | set(SOURCE_UNPINNED_UPSTREAM.get(key, {})))
            assert nums <= allowed, (
                f"{key} 的來源文字寫死了 {sorted(nums - allowed)}，"
                f"既沒登錄成記法、也沒登錄成既知欠債")


# ════════════════════════════════════════════════════════════════
# 二之二、邊界符號:文字寫的 ≤ / < 必須是程式真的在做的事
# ════════════════════════════════════════════════════════════════
class TestBoundarySymbolsMatchCode:
    """2026-08-26:`light235` 的門檻文字寫 `z ≤ −1σ`，實作是 `z < T.Z_LIGHT1`。

    邊界上那一點是假敘述。**改的是文字不是程式** —— 證據顯示程式沒錯:
      · SSOT 常數自己的註解就寫 `# z < -1σ → 燈一`（三條加碼帶皆然）;
      · 判燈當下印給使用者的理由字串是 `布林<{-1}σ`（同樣嚴格小於）;
      · 同一段程式用 `z >= Z_LIGHT2` 當「布林未達 -2σ」的補集 ——
        補集寫 `>=` 反證主集是 `<`，兩者是同一刀切下去的;
      · 同一句門檻文字的停利那半段本來就寫 `>`，與程式一致 ——
        也就是這句話自己前後兩半用了兩套符號，比較像排版手滑而非有意宣告。
    改程式（`<` → `<=`）會改變燈號行為（z 剛好等於 −1σ 時從不亮變成亮），
    屬行為變更，需 user 核准 —— 本輪不做。
    """

    def test_light235_add_bands_are_strictly_less_than(self):
        txt = SPECS_BY_KEY["light235"].threshold_text
        assert "≤" not in txt, (
            f"235 的門檻文字出現 ≤，但三段加碼實作是嚴格小於（`z < Z_LIGHT*`）："
            f"{txt!r}")
        assert "<" in txt and ">" in txt, f"加碼/停利兩半的符號都該在:{txt!r}"

    #: 判定式**真的**用 `>=` / `<=` 的燈（逐燈讀程式得來，不是照抄文字）:
    #:   · `screen_inception` → `inception_years >= MIN_INCEPTION_YEARS`
    #:   · `screen_return`    → `ann_return_3y_pct >= …` 或 `cum_return_3y_pct >= …`
    #:   · `screen_peer`      → `percentile <= PEER_TOP_FRACTION`
    #:     （文字以「前 1/3」表達，本來就沒寫符號 —— 但它**允許**寫）
    #: 其餘各燈皆為嚴格不等式:`health_a` `<`、`health_b` `<`、`health_c` `<` 且斜率 `<`、
    #: `health_d` `>`、`light235` 三段加碼 `<` / 停利 `>`。
    INCLUSIVE_IMPL = frozenset({"screen_inception", "screen_return", "screen_peer"})

    @pytest.mark.parametrize("spec", STATION_SPECS, ids=lambda s: s.key)
    def test_no_inclusive_symbol_without_an_inclusive_rule(self, spec):
        """全表掃描:實作是嚴格不等式的燈，門檻文字不准出現 ≥ / ≤。

        新增燈時請**去讀那盞燈的判定式**再決定要不要進 `INCLUSIVE_IMPL`，
        不要因為測試紅了就把 key 加進去 —— 那等於用白名單把假敘述合法化。
        """
        if spec.key in self.INCLUSIVE_IMPL:
            pytest.skip("實作本身就是 >= / <=，允許寫 ≥ / ≤")
        assert "≥" not in spec.threshold_text and "≤" not in spec.threshold_text, (
            f"{spec.key} 的門檻文字出現 ≥/≤，但它的實作是嚴格不等式 —— "
            f"邊界上那一點是假敘述:{spec.threshold_text!r}")

    @pytest.mark.parametrize("key", ["screen_inception", "screen_return"])
    def test_inclusive_rules_keep_saying_inclusive(self, key):
        """反向:這兩盞燈的判定式含邊界（`>=`），文字就得寫 ≥。

        寫成 `>` 會把門檻講嚴一個點 —— 剛好等於門檻的標的會被讀成沒過。
        （`screen_peer` 不在此列:它的文字用「前 1/3」表達，本來就不帶符號。）
        """
        assert "≥" in SPECS_BY_KEY[key].threshold_text, (
            f"{key} 的實作是 >=，門檻文字卻沒寫 ≥:"
            f"{SPECS_BY_KEY[key].threshold_text!r}")



# ════════════════════════════════════════════════════════════════
# 三、旗標必填理由（同 DangerSpec 的既有慣例）
# ════════════════════════════════════════════════════════════════
class TestFlagsRequireReasons:

    def test_unwired_requires_reason(self):
        offenders = [s.key for s in STATION_SPECS
                     if not s.wired and not s.unwired_reason.strip()]
        assert not offenders, f"標了 wired=False 卻沒填 unwired_reason:{offenders}"

    def test_degraded_requires_reason(self):
        offenders = [s.key for s in STATION_SPECS
                     if not s.discriminative and not s.degraded_reason.strip()]
        assert not offenders, \
            f"標了 discriminative=False 卻沒填 degraded_reason:{offenders}"

    def test_no_level_requires_reason(self):
        """標了 `emits_level=False` 就必須說清楚**為什麼沒有等級**。

        這個旗標的效果是「把這盞燈移出可信度分母」—— 分數會變好看。
        不附理由 = 畫面少一盞燈卻沒有人交代得出來(§1)。
        """
        offenders = [s.key for s in STATION_SPECS
                     if not s.emits_level and not s.no_level_reason.strip()]
        assert not offenders, f"標了 emits_level=False 卻沒填 no_level_reason:{offenders}"

    def test_no_level_reason_does_not_borrow_the_not_applicable_text(self):
        """§1:不准把「還沒有規則」講成「不適用」。

        兩者的處置完全不同:「不適用」是這類持股結構上沒有這盞燈(永遠不會有,
        也不必等);「還沒有規則」是燈在、值也在,只是沒有人定義過怎麼判 ——
        照「不適用」寫,使用者會以為 KD 對個股沒有意義,那是假的。
        """
        for key in sorted(KNOWN_NO_LEVEL):
            txt = SPECS_BY_KEY[key].no_level_reason
            assert MISS_TEXT[SS.MISS_NOT_APPLICABLE] not in txt, \
                f"{key} 借用了「不適用」的文案"
            if "不適用" in txt:
                # 提到可以,但必須是**否定**它(「這不是不適用」),不能讀成在自稱不適用。
                assert "**不是**「這類持股不適用」" in txt, \
                    f"{key} 的理由提到「不適用」卻沒有明說它不是那一種:\n{txt}"

    def test_no_orphan_reasons(self):
        """反向：沒標旗標就不該有理由（寫了卻不生效的孤兒文案）。"""
        assert not [s.key for s in STATION_SPECS
                    if s.wired and s.unwired_reason.strip()]
        assert not [s.key for s in STATION_SPECS
                    if s.discriminative and s.degraded_reason.strip()]
        assert not [s.key for s in STATION_SPECS
                    if s.emits_level and s.no_level_reason.strip()]

    def test_marked_sets_match_known_lists(self):
        """被標記的集合要與本檔清單一致 —— 新增/移除都要有人有意識地改測試。"""
        assert {s.key for s in STATION_SPECS if not s.discriminative} == KNOWN_DEGRADED
        assert {s.key for s in STATION_SPECS if not s.wired} == KNOWN_UNWIRED
        assert {s.key for s in STATION_SPECS if not s.emits_level} == KNOWN_NO_LEVEL

    def test_the_three_flags_are_independent(self):
        """三個旗標各講各的事,不得互相冒充。

        KD 是 `emits_level=False` 而**不是** `wired=False`(它確實有接、燈也在看)、
        也**不是** `discriminative=False`(它根本沒有門檻可以失準)。
        用錯旗標的後果是畫面講錯話:標 unwired 會說「別等它亮」(它一直亮著)、
        標 degraded 會說「門檻已失準」(它沒有門檻)。
        """
        for key in sorted(KNOWN_NO_LEVEL):
            spec = SPECS_BY_KEY[key]
            assert spec.wired is True and spec.discriminative is True
        assert not (KNOWN_NO_LEVEL & (KNOWN_DEGRADED | KNOWN_UNWIRED))

    @pytest.mark.parametrize("key", sorted(KNOWN_DEGRADED))
    def test_degraded_reason_tells_user_what_to_do(self, key):
        """光說「不能信」沒用 —— 必須說改看什麼。"""
        txt = SPECS_BY_KEY[key].degraded_reason
        assert "該怎麼看" in txt or "改看" in txt or "請到" in txt, \
            f"{key} 只說了不能信，沒說該改看什麼:\n{txt}"

    @pytest.mark.parametrize("key",
                             sorted(KNOWN_DEGRADED | KNOWN_UNWIRED | KNOWN_NO_LEVEL))
    def test_reason_is_user_facing_not_a_dev_memo(self, key):
        """這欄會直接印給使用者。v19.170 有前科（margin.note 誤植開發者備忘，
        實機驗證確認整段被印到畫面）。

        `no_level_reason` 2026-08-26 納入同一個掃描 —— 它與另外兩個理由欄
        走的是明細面板同一塊區域，沒有理由套兩種標準。"""
        spec = SPECS_BY_KEY[key]
        txt = ((spec.degraded_reason or "") + (spec.unwired_reason or "")
               + (spec.no_level_reason or ""))
        for pat, why in (
            (re.compile(r"\bv\d+\.\d+"), "版本號"),
            (re.compile(r"\b[\w.]+\.py\b"), "檔名"),
            (re.compile(r"\b(?:shared|src|tests)/[\w/]+"), "模組路徑"),
            (re.compile(r"\bSSOT\b|\bTODO\b|\bFIXME\b"), "內部標記"),
        ):
            assert not pat.search(txt), f"{key} 的理由含{why}:\n{txt}"


# ════════════════════════════════════════════════════════════════
# 四、四態 —— 本次改動的核心目的
# ════════════════════════════════════════════════════════════════
class TestFourStatesAreDistinguishable:

    def test_all_four_symbols_are_distinct(self):
        """四態不得共用符號。

        **這是整個規格表存在的理由。** 現行畫面把「一切正常（⚪ 巡航）」、
        「該項缺資料」、「整檔抓取失敗」、「這類不適用」全部畫成 ⚪，
        使用者無從分辨。若這條紅了，代表又退回原點。
        """
        symbols = [v[1] for v in STATE_META.values()]
        assert len(symbols) == len(set(symbols)) == 4, \
            f"四態符號重複:{symbols}"

    def test_no_state_uses_the_cruise_symbol(self):
        """⚪ 保留給「巡航＝一切正常」的既有語意，四態一個都不准用它。

        用了就等於把「正常」和「不可信」又混在一起 —— 那正是要修的東西。
        """
        for state, (label, sym) in STATE_META.items():
            assert sym != "⚪", (
                f"{state}（{label}）用了 ⚪ —— 那個符號在戰情室代表"
                f"「巡航：維持定期定額」，也就是一切正常。四態不得佔用它。"
            )

    def test_unwired_wins_over_everything(self):
        """`wired=False` 就算硬塞值進來也永遠 unwired。"""
        from dataclasses import replace
        spec = replace(SPECS_BY_KEY["health_a"], wired=False,
                       unwired_reason="測試用")
        assert classify_state(spec, has_value=True) == STATE_UNWIRED
        assert classify_state(spec, has_value=False) == STATE_UNWIRED

    def test_degraded_still_has_a_value(self):
        """與 unwired 的關鍵差異：門檻失準的燈**照常有值、照常亮**。"""
        spec = SPECS_BY_KEY["stock_trend"]
        assert spec.discriminative is False
        assert classify_state(spec, has_value=True) == STATE_DEGRADED
        # 沒值時是 missing 而不是 degraded —— 沒值就是沒值，跟門檻好不好無關
        assert classify_state(spec, has_value=False) == STATE_MISSING

    def test_live_requires_a_value(self):
        assert classify_state(SPECS_BY_KEY["health_a"], has_value=True) == STATE_LIVE
        assert classify_state(SPECS_BY_KEY["health_a"], has_value=False) == STATE_MISSING

    def test_every_missing_reason_has_actionable_text(self):
        """缺值原因必須說得出「該做什麼」，否則等於沒講。"""
        for reason, txt in MISS_TEXT.items():
            assert txt.strip(), f"{reason} 沒有文案"
            assert len(txt) >= 15, f"{reason} 的文案過短:{txt}"

    def test_not_applicable_is_not_an_error(self):
        """「這類持股不適用」不是壞掉 —— 文案必須講清楚，否則使用者會去修一個沒壞的東西。"""
        from shared.station_specs import MISS_NOT_APPLICABLE
        assert "不是壞掉" in MISS_TEXT[MISS_NOT_APPLICABLE]


# ════════════════════════════════════════════════════════════════
# 五、文案品質 —— 這些字都會印給一般使用者
# ════════════════════════════════════════════════════════════════
class TestCopyIsUserFacing:

    @pytest.mark.parametrize("spec", STATION_SPECS, ids=lambda s: s.key)
    def test_why_explains_in_plain_language(self, spec):
        """每盞燈都要說得出「它在防什麼」，而且是人話。"""
        assert spec.why.strip(), f"{spec.key} 沒寫 why"
        assert len(spec.why) >= 10, f"{spec.key} 的 why 太短:{spec.why}"
        assert not re.search(r"\b[\w.]+\.py\b", spec.why), \
            f"{spec.key} 的 why 出現檔名"

    @pytest.mark.parametrize("spec", STATION_SPECS, ids=lambda s: s.key)
    def test_source_is_stated(self, spec):
        """每盞燈都要說得出資料從哪來 —— 明細面板要顯示。"""
        assert spec.source.strip(), f"{spec.key} 沒寫 source"

    @pytest.mark.parametrize("spec", STATION_SPECS, ids=lambda s: s.key)
    def test_label_is_short_enough_for_mobile(self, spec):
        """標籤要塞得進手機的表格欄位。"""
        assert len(spec.label) <= 12, f"{spec.key} 的 label 太長:{spec.label}"


# ════════════════════════════════════════════════════════════════
# 六、缺值原因的排序與 235 三軸（2026-08-25 新增）
#
# 這一組守的是「原因」本身的完整性:少一條文案 / 少一個排序位,
# 畫面就會印出 `no_input` 這種內部代號,或把某個原因悄悄降到最低優先。
# ════════════════════════════════════════════════════════════════
class TestMissReasonRegistry:

    def _all_miss_constants(self) -> set[str]:
        return {v for k, v in vars(SS).items()
                if k.startswith("MISS_") and isinstance(v, str)}

    def test_every_reason_has_text_and_a_rank(self):
        """新增一個 MISS_* 卻忘了補文案或排序 —— 這條會當場紅。"""
        consts = self._all_miss_constants()
        assert consts - set(MISS_TEXT) == set(), "有原因沒有使用者文案"
        assert consts - set(MISS_PRIORITY) == set(), "有原因沒有排在 MISS_PRIORITY 裡"
        assert set(MISS_PRIORITY) == set(MISS_TEXT), "文案表與排序表不同步"

    def test_priority_has_no_duplicates(self):
        assert len(MISS_PRIORITY) == len(set(MISS_PRIORITY))

    def test_not_applicable_never_wins(self):
        """「不適用」不是問題 —— 只有在**全部**都不適用時才該勝出。

        個股列的健檢同時有「歷史不足」與「D 折溢價不適用」,若 n/a 贏了,
        使用者會被告知「這檔不適用」而不是「資料還不夠」。
        """
        for other in set(MISS_PRIORITY) - {SS.MISS_NOT_APPLICABLE}:
            assert most_fundamental_miss([SS.MISS_NOT_APPLICABLE, other]) == other
        assert most_fundamental_miss([SS.MISS_NOT_APPLICABLE]) == SS.MISS_NOT_APPLICABLE

    def test_fetch_failed_wins_everything(self):
        """整檔沒抓到 → 其他項不可能算得出來,它解釋了全部。"""
        for other in set(MISS_PRIORITY) - {SS.MISS_FETCH_FAILED}:
            assert most_fundamental_miss([other, SS.MISS_FETCH_FAILED]) == SS.MISS_FETCH_FAILED

    def test_structural_beats_transient(self):
        """歷史不足（等時間）比單項沒抓到（可重跑）根本 —— 對應健檢 A 兩因皆缺的取捨。"""
        assert most_fundamental_miss([SS.MISS_NO_INPUT,
                                      SS.MISS_NOT_ENOUGH]) == SS.MISS_NOT_ENOUGH

    def test_no_variation_sits_between_not_enough_and_no_input(self):
        """零波動的排序位（2026-08-27 新增常數時一併釘住）。

        兩邊各有理由，寫成可執行的規格免得日後被「順手」挪動：
        - 輸給 `MISS_NOT_ENOUGH`:歷史長度不足時**整條線都不存在**，涵蓋面更大。
        - 贏過 `MISS_NO_INPUT`:「整段沒動」解釋的是**單一統計量沒有定義**，
          比「某一項沒抓到」具體;更重要的是若讓 `NO_INPUT` 勝出，畫面會印出
          「可以重跑一次」—— 那正是本次要修掉的錯誤指引。
        """
        assert most_fundamental_miss(
            [SS.MISS_NO_VARIATION, SS.MISS_NOT_ENOUGH]) == SS.MISS_NOT_ENOUGH
        assert most_fundamental_miss(
            [SS.MISS_NO_INPUT, SS.MISS_NO_VARIATION]) == SS.MISS_NO_VARIATION

    def test_no_variation_text_does_not_tell_the_user_to_rerun(self):
        """文案語意鎖：零波動**不可**給出「重跑一次」或「等時間累積」的指引。

        使用者看到的是文案不是常數名 —— 只鎖常數，文案被改回去仍會全綠。
        """
        _txt = MISS_TEXT[SS.MISS_NO_VARIATION]
        assert "重跑不會改變" in _txt
        assert "可以重跑" not in _txt
        assert "等時間累積" not in _txt
        assert _txt != MISS_TEXT[SS.MISS_NO_INPUT]
        assert _txt != MISS_TEXT[SS.MISS_NOT_ENOUGH]

    def test_unknown_reason_never_outranks_a_known_one(self):
        assert most_fundamental_miss(["某個沒登錄的原因",
                                      SS.MISS_NOT_APPLICABLE]) == SS.MISS_NOT_APPLICABLE

    def test_empty_input_is_empty_output(self):
        assert most_fundamental_miss([]) == ""
        assert most_fundamental_miss(None) == ""
        assert most_fundamental_miss(["", ""]) == ""

    def test_contract_drift_text_says_it_is_a_bug_not_a_wait(self):
        """契約漂移的文案若寫成「等一下再試」,就沒有人會去修那個 bug。"""
        txt = MISS_TEXT[SS.MISS_CONTRACT_DRIFT]
        assert "重跑" in txt and ("修" in txt or "回報" in txt)


class TestLight235Axes:

    def test_every_axis_has_a_label(self):
        assert set(LIGHT235_AXES) == set(AXIS_LABELS)
        assert len(LIGHT235_AXES) == len(set(LIGHT235_AXES)) == 3

    def test_axes_text_follows_canonical_order(self):
        """傳入順序不影響輸出 —— 否則「文案有沒有變」會變成不可判定的事。"""
        assert axes_text(LIGHT235_AXES) == axes_text(tuple(reversed(LIGHT235_AXES)))
        assert axes_text(LIGHT235_AXES) == "VIX/週線/布林"

    def test_axes_text_of_nothing_is_empty(self):
        assert axes_text(()) == "" and axes_text(None) == ""

    def test_spec_keys_are_constants_not_literals(self):
        """規格表的 key 必須就是 KEY_* 常數本身（跨層字典鍵靠它對齊）。"""
        for key in (SS.KEY_HEALTH_A, SS.KEY_HEALTH_B, SS.KEY_HEALTH_C, SS.KEY_HEALTH_D,
                    SS.KEY_LIGHT235, SS.KEY_SCREEN_INCEPTION, SS.KEY_SCREEN_RETURN,
                    SS.KEY_SCREEN_PEER, SS.KEY_STOCK_HEALTH, SS.KEY_STOCK_TREND,
                    SS.KEY_STOCK_KD, SS.KEY_STOCK_SWAP):
            assert key in SPECS_BY_KEY, f"{key} 不在規格表裡"
        assert len(SPECS_BY_KEY) == len(STATION_SPECS)
