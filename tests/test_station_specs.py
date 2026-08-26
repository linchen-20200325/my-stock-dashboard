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

`source` 與 `why` **釘不住**。它們是自然語言 —— 「5 年日報酬年化」寫成
「週報酬 ×√52 年化」是對是錯，沒有任何斷言判得出來。2026-08-26 抓到的兩個
實例正是這種:`health_b.source` 宣稱「無風險利率視為 0」而實作取的是即時
FEDFUNDS（fallback 5.33%），`screen_return` 的門檻寫「需為正報酬」而實作要
年化 ≥ 7%。前者連數字都沒寫錯 —— 它寫的 `0` 是個「正確地寫出來的錯誤事實」，
**再嚴的數字掃描也掃不到**。

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
        """`source` 整體釘不住（見檔頭），但它**寫出來的那個利率**釘得住。

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

    def test_no_orphan_reasons(self):
        """反向：沒標旗標就不該有理由（寫了卻不生效的孤兒文案）。"""
        assert not [s.key for s in STATION_SPECS
                    if s.wired and s.unwired_reason.strip()]
        assert not [s.key for s in STATION_SPECS
                    if s.discriminative and s.degraded_reason.strip()]

    def test_marked_sets_match_known_lists(self):
        """被標記的集合要與本檔清單一致 —— 新增/移除都要有人有意識地改測試。"""
        assert {s.key for s in STATION_SPECS if not s.discriminative} == KNOWN_DEGRADED
        assert {s.key for s in STATION_SPECS if not s.wired} == KNOWN_UNWIRED

    @pytest.mark.parametrize("key", sorted(KNOWN_DEGRADED))
    def test_degraded_reason_tells_user_what_to_do(self, key):
        """光說「不能信」沒用 —— 必須說改看什麼。"""
        txt = SPECS_BY_KEY[key].degraded_reason
        assert "該怎麼看" in txt or "改看" in txt or "請到" in txt, \
            f"{key} 只說了不能信，沒說該改看什麼:\n{txt}"

    @pytest.mark.parametrize("key", sorted(KNOWN_DEGRADED | KNOWN_UNWIRED))
    def test_reason_is_user_facing_not_a_dev_memo(self, key):
        """這欄會直接印給使用者。v19.170 有前科（margin.note 誤植開發者備忘，
        實機驗證確認整段被印到畫面）。"""
        spec = SPECS_BY_KEY[key]
        txt = (spec.degraded_reason or "") + (spec.unwired_reason or "")
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
