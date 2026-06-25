"""test_macro_buckets.py — 五桶危險門檻 SSOT 註冊表測試 (v18.284)

重點：
1. drift guard — 鏡像值必須 == macro_core.MACRO_THRESHOLDS（CLAUDE.md §3.3 防漂移）
2. classify_danger 三方向（high_bad / low_bad / band）+ gray 邊界
3. 註冊表結構完整性（bucket 合法 / key 唯一 / 紅黃線方向自洽）
"""
import math

import pytest

from shared import macro_buckets as mb
from macro_core import MACRO_THRESHOLDS


# ──────────────────────────────────────────────────────────
# 1. drift guard：鏡像值 == L1 SSOT 源
# ──────────────────────────────────────────────────────────
def test_mirror_matches_macro_core():
    assert mb._VIX_YELLOW == MACRO_THRESHOLDS["VIX"]["yellow_above"]
    assert mb._VIX_RED == MACRO_THRESHOLDS["VIX"]["red_above"]
    assert mb._CPI_YELLOW == MACRO_THRESHOLDS["CPI"]["yellow_above"]
    assert mb._CPI_RED == MACRO_THRESHOLDS["CPI"]["red_above"]
    assert mb._PMI_YELLOW == MACRO_THRESHOLDS["PMI"]["yellow_below"]
    assert mb._PMI_RED == MACRO_THRESHOLDS["PMI"]["red_below"]


def test_imported_ssot_constants_used():
    """融資 / 外資期貨紅黃線確實來自 signal_thresholds（非腦補）。"""
    from shared.signal_thresholds import (
        MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
        FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS,
        FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS,
    )
    _margin = mb.SPECS_BY_KEY["margin"]
    assert _margin.red == float(MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI)
    _fut = mb.SPECS_BY_KEY["fut_net"]
    assert _fut.yellow == float(FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS)
    assert _fut.red == float(FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS)


# ──────────────────────────────────────────────────────────
# 2. classify_danger
# ──────────────────────────────────────────────────────────
def test_classify_high_bad():
    vix = mb.SPECS_BY_KEY["vix"]  # yellow=22 red=30
    assert mb.classify_danger(15, vix) == "green"
    assert mb.classify_danger(22, vix) == "yellow"
    assert mb.classify_danger(25, vix) == "yellow"
    assert mb.classify_danger(30, vix) == "red"
    assert mb.classify_danger(45, vix) == "red"


def test_classify_low_bad():
    pmi = mb.SPECS_BY_KEY["ism_pmi"]  # yellow=50 red=46
    assert mb.classify_danger(55, pmi) == "green"
    assert mb.classify_danger(50, pmi) == "yellow"
    assert mb.classify_danger(48, pmi) == "yellow"
    assert mb.classify_danger(46, pmi) == "red"
    assert mb.classify_danger(40, pmi) == "red"


def test_classify_band():
    ndc = mb.SPECS_BY_KEY["ndc_signal"]  # yellow_lo=23 yellow=32 red_lo=16 red=38
    assert mb.classify_danger(28, ndc) == "green"   # 23-31 綠
    assert mb.classify_danger(34, ndc) == "yellow"  # 32-37 黃紅
    assert mb.classify_danger(20, ndc) == "yellow"  # 17-22 黃藍
    assert mb.classify_danger(40, ndc) == "red"     # 38+ 過熱
    assert mb.classify_danger(12, ndc) == "red"     # ≤16 藍衰退


def test_classify_gray_on_none():
    vix = mb.SPECS_BY_KEY["vix"]
    assert mb.classify_danger(None, vix) == "gray"
    assert mb.classify_danger("n/a", vix) == "gray"


# ──────────────────────────────────────────────────────────
# 3. 註冊表結構完整性
# ──────────────────────────────────────────────────────────
def test_all_specs_valid():
    seen_keys = set()
    for s in mb.BUCKET_DANGER_SPECS:
        assert s.bucket in mb.BUCKET_ORDER, f"{s.key} bucket 非法: {s.bucket}"
        assert s.direction in ("high_bad", "low_bad", "band"), f"{s.key} direction 非法"
        assert s.key not in seen_keys, f"{s.key} 重複"
        seen_keys.add(s.key)
        assert s.source, f"{s.key} 缺 source 標註"
        if s.direction == "band":
            assert s.yellow_lo is not None and s.red_lo is not None, f"{s.key} band 缺低側線"


def test_every_bucket_has_specs():
    for b in mb.BUCKET_ORDER:
        assert mb.specs_for_bucket(b), f"桶 {b} 無任何 DangerSpec"


def test_high_bad_red_ge_yellow():
    """high_bad：red 線應 >= yellow 線；low_bad 反之。"""
    for s in mb.BUCKET_DANGER_SPECS:
        if s.direction == "high_bad":
            assert s.red >= s.yellow, f"{s.key} high_bad red<yellow"
        elif s.direction == "low_bad":
            assert s.red <= s.yellow, f"{s.key} low_bad red>yellow"
