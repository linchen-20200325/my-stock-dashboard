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

⚠️ 本檔只測 L0 純資料，**不啟動 Streamlit、不做網路 I/O**。
"""
from __future__ import annotations

import re

import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
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
class TestNoHardcodedThresholds:

    @pytest.mark.parametrize("key,needle", [
        ("health_b", f"{T.SHARPE_NEG_THRESHOLD:g}"),
        ("health_c", str(T.MA_QUARTER_WEEKS)),
        ("health_d", f"{T.PREMIUM_ALERT_PCT:g}"),
        ("light235", str(T.BOLL_PERIOD_WEEKS)),
        ("screen_inception", f"{T.MIN_INCEPTION_YEARS:g}"),
    ])
    def test_threshold_text_reflects_ssot(self, key, needle):
        """門檻文字必須含當前 SSOT 值 —— 改上游常數，這裡自動跟著改。

        這條會在「有人改了 SSOT 但規格表文字沒跟著動」時紅，
        也就是漂移發生的**當下**，而不是等使用者看到不一致的畫面。
        """
        assert needle in SPECS_BY_KEY[key].threshold_text, (
            f"{key} 的門檻文字沒反映 SSOT 值 {needle!r}："
            f"{SPECS_BY_KEY[key].threshold_text!r}"
        )

    def test_peer_window_months_come_from_ssot(self):
        txt = SPECS_BY_KEY["screen_peer"].threshold_text
        for m in T.PEER_WINDOWS_MONTHS:
            assert f"{m}M" in txt, f"同儕時間框 {m}M 沒出現在門檻文字"

    def test_stock_grades_come_from_ssot(self):
        txt = SPECS_BY_KEY["stock_health"].threshold_text
        for g in T.STOCK_HEALTH_GRADES:
            assert g in txt, f"評等 {g} 沒出現在門檻文字"


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
