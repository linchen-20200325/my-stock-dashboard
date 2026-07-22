"""shared/forward_test_thresholds.py — 前進式驗證(Forward-test)門檻 SSOT(L0).

前進式驗證:凍結每期選股 → 一段時間後對帳報酬 vs 被動基準,累積真實勝率/超額。
零 lookahead、零存活者偏誤(都是當下真實決定)。取代已移除的舊回測引擎(v18.265)。
"""
from __future__ import annotations

FORWARD_TEST_BENCHMARK: str = "0050"
"""前進式驗證的被動基準:元大台灣50。用「可買的 ETF」當對照,問「這套選股贏不贏得過直接買 0050」。"""

FORWARD_TEST_MIN_COHORT_PICKS: int = 3
"""單一 cohort(凍結批次)至少要有幾檔有效持股才納入績效統計;不足 → 標記略過(§1 樣本太小不硬算)。"""

FORWARD_TEST_FREEZE_TOP_N: int = 20
"""每月 cron 自動凍結「綜合評分前 N 名」當該期 cohort(v19.147;對齊 UI 手動凍結的前 20 名)。"""
