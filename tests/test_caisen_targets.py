"""tests/test_caisen_targets.py — 蔡森形態學目標價引擎單元測試(純邏輯,無 I/O)。

涵蓋:
  1. compute_caisen_targets 例題數字驗算(破底翻 + N字兩種 stop)。
  2. detect_swings 合成 ZigZag 交替 pivots + NaN 跳過。
  3. derive_caisen_levels 關鍵位對映(wave1_high / wave1_start / consolidation_low)。
  4. 邊界:空 / 太短 / 缺 consolidation_low / 除零 → rr=None。
  5. property-based:pivots 永遠 kind 交替 + idx 遞增。
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src.compute.strategy.caisen_targets import (
    compute_caisen_targets,
    derive_caisen_levels,
    detect_swings,
    summarize_caisen,
)


# ── 1. 例題數字驗算 ────────────────────────────────────────────────
def test_golden_breakdown_reversal_numbers():
    """破底翻例題:target_n=145、sweet=120、stop≈95*0.99、rr 為正且合理。"""
    r = compute_caisen_targets(
        pattern="破底翻",
        support=100,
        breakdown_low=95,
        wave1_start=100,
        wave1_high=130,
        consolidation_low=115,
        neckline=120,
        current_price=120,
    )
    # 目標(等幅滿足):115 + (130-100) = 145
    assert math.isclose(r["target_n"], 145.0, rel_tol=1e-9)
    assert math.isclose(r["target1"], 145.0, rel_tol=1e-9)  # N字優先
    # 甜蜜價 = 頸線
    assert math.isclose(r["sweet"], 120.0, rel_tol=1e-9)
    assert math.isclose(r["sweet_low"], 115.0, rel_tol=1e-9)   # 整理低
    assert math.isclose(r["sweet_high"], 120.0, rel_tol=1e-9)
    # 破底翻 → stop 用 breakdown_low
    assert math.isclose(r["stop"], 95 * 0.99, rel_tol=1e-9)
    # 底型目標:120 + (130-95) = 155;第二波 120 + 2*35 = 190
    assert math.isclose(r["target_box"], 155.0, rel_tol=1e-9)
    assert math.isclose(r["target2"], 190.0, rel_tol=1e-9)
    # 風報比 = (145-120)/(120-94.05) = 25/25.95 ≈ 0.9634,正且合理
    assert r["rr"] is not None
    assert r["rr"] > 0
    assert math.isclose(r["rr"], (145 - 120) / (120 - 95 * 0.99), rel_tol=1e-9)
    assert 0 < r["rr"] < 5  # 合理量級


def test_golden_n_pattern_stop_uses_min_consol_neckline():
    """同一組數字改判 N字進場:stop 改用 min(consolidation_low, neckline)*(1-buffer)。

    專業判斷驗證:N字回踩不破整理低才是有效買點,故止損應貼整理低(115),
    而非甩轎破底低(95)——後者是破底翻專用的更寬停損。
    """
    r = compute_caisen_targets(
        pattern="N字整理",
        support=100,
        breakdown_low=95,
        wave1_start=100,
        wave1_high=130,
        consolidation_low=115,
        neckline=120,
        current_price=120,
    )
    # min(115, 120) * 0.99 = 113.85
    assert math.isclose(r["stop"], 115 * 0.99, rel_tol=1e-9)
    # target1 仍為 N字 145(與 pattern 無關,只看 target_n 是否算得出)
    assert math.isclose(r["target1"], 145.0, rel_tol=1e-9)
    # rr = (145-120)/(120-113.85) = 25/6.15 ≈ 4.065,較窄止損 → 較高 rr
    assert math.isclose(r["rr"], (145 - 120) / (120 - 115 * 0.99), rel_tol=1e-9)
    assert r["rr"] > 0
    # notes 明確說明採哪條止損公式
    assert any("N字" in n and "止損" in n for n in r["notes"])


def test_two_stop_regimes_differ():
    """同數字下,破底翻止損(95 基)必寬於 N字止損(115 基)→ 破底翻 rr 較低。"""
    kw = dict(support=100, breakdown_low=95, wave1_start=100, wave1_high=130,
              consolidation_low=115, neckline=120, current_price=120)
    br = compute_caisen_targets(pattern="破底翻", **kw)
    nz = compute_caisen_targets(pattern="N字整理", **kw)
    assert br["stop"] < nz["stop"]      # 破底翻停損更低(更寬)
    assert br["rr"] < nz["rr"]          # 更寬停損 → 風報比較低


# ── 2. detect_swings 合成 ZigZag ──────────────────────────────────
def test_detect_swings_alternating_pivots():
    """100→130→115→145 明顯轉折 → 交替 pivots (low,high,low)。"""
    seq = [100.0, 130.0, 115.0, 145.0]
    piv = detect_swings(seq, seq, pct=0.08)
    kinds = [p["kind"] for p in piv]
    prices = [p["price"] for p in piv]
    idxs = [p["idx"] for p in piv]
    # 確認交替、遞增、價格正確(末段上行的 145 未反轉確認,不列入)
    assert kinds == ["low", "high", "low"]
    assert prices == [100.0, 130.0, 115.0]
    assert idxs == [0, 1, 2]


def test_detect_swings_separate_high_low_arrays():
    """high 用 highs、low 用 lows:峰用高價、谷用低價。"""
    highs = [101, 132, 118, 148]
    lows = [99, 128, 112, 142]
    piv = detect_swings(highs, lows, pct=0.08)
    assert piv[0] == {"idx": 0, "price": 99.0, "kind": "low"}    # 谷取 low
    assert piv[1] == {"idx": 1, "price": 132.0, "kind": "high"}  # 峰取 high
    assert piv[2] == {"idx": 2, "price": 112.0, "kind": "low"}


def test_detect_swings_ignores_small_wiggles():
    """小於 pct 的抖動不產生轉折。"""
    # 100 → 103(+3%)→ 101 → 104:全在 8% 帶內,無反轉確認
    seq = [100.0, 103.0, 101.0, 104.0, 102.0]
    piv = detect_swings(seq, seq, pct=0.08)
    assert piv == []


def test_detect_swings_skips_nan():
    """NaN 整根跳過,不填補;其餘仍正確偵測。"""
    nan = float("nan")
    highs = [100.0, nan, 130.0, 115.0, 145.0]
    lows = [100.0, nan, 130.0, 115.0, 145.0]
    piv = detect_swings(highs, lows, pct=0.08)
    kinds = [p["kind"] for p in piv]
    prices = [p["price"] for p in piv]
    assert kinds == ["low", "high", "low"]
    assert prices == [100.0, 130.0, 115.0]


def test_detect_swings_too_short_returns_empty():
    assert detect_swings([100, 110], [100, 110]) == []
    assert detect_swings([], []) == []
    assert detect_swings([100.0], [100.0]) == []


def test_detect_swings_property_alternating_and_monotone():
    """property:任意序列輸出的 pivots kind 必交替、idx 必嚴格遞增。"""
    seqs = [
        [100, 120, 108, 135, 120, 150, 130],
        [200, 180, 195, 160, 190, 150],
        [50, 55, 60, 45, 70, 40, 80],
    ]
    for seq in seqs:
        s = [float(x) for x in seq]
        piv = detect_swings(s, s, pct=0.08)
        # idx 嚴格遞增
        for a, b in zip(piv, piv[1:]):
            assert a["idx"] < b["idx"]
            assert a["kind"] != b["kind"]  # kind 交替


def test_detect_swings_accepts_pandas_series():
    """接受 pd.Series(若環境有 pandas);等同 list 結果。"""
    pd = pytest.importorskip("pandas")
    seq = [100.0, 130.0, 115.0, 145.0]
    piv_list = detect_swings(seq, seq, pct=0.08)
    piv_ser = detect_swings(pd.Series(seq), pd.Series(seq), pct=0.08)
    assert piv_ser == piv_list


# ── 3. derive_caisen_levels 對映 ──────────────────────────────────
def test_derive_levels_maps_wave_points():
    """low100 → high130 → low115,現價120 → 正確對映三關鍵位。"""
    swings = [
        {"idx": 0, "price": 100.0, "kind": "low"},
        {"idx": 1, "price": 130.0, "kind": "high"},
        {"idx": 2, "price": 115.0, "kind": "low"},
    ]
    lv = derive_caisen_levels(swings, current_price=120.0)
    assert lv is not None
    assert lv["wave1_high"] == 130.0
    assert lv["neckline"] == 130.0            # neckline == wave1_high
    assert lv["wave1_start"] == 100.0         # 高之前最近的低
    assert lv["consolidation_low"] == 115.0   # 高之後的低
    assert lv["breakdown_low"] == 100.0       # 所有低中最低
    assert lv["current_price"] == 120.0


def test_derive_levels_pattern_n_shape():
    """有整理低、未破前低 → 型態 = N字整理。"""
    swings = [
        {"idx": 0, "price": 100.0, "kind": "low"},
        {"idx": 1, "price": 130.0, "kind": "high"},
        {"idx": 2, "price": 115.0, "kind": "low"},
    ]
    lv = derive_caisen_levels(swings, current_price=120.0)
    assert lv["pattern"] == "N字整理"


def test_derive_levels_pattern_breakdown_reversal():
    """整理低破前低(95 < 起漲 110)後現價站回 → 破底翻。"""
    swings = [
        {"idx": 0, "price": 110.0, "kind": "low"},   # 起漲 / 支撐
        {"idx": 1, "price": 140.0, "kind": "high"},  # 第一波高
        {"idx": 2, "price": 95.0, "kind": "low"},    # 破底(<110)
    ]
    lv = derive_caisen_levels(swings, current_price=120.0)  # 站回 110 之上
    assert lv["pattern"] == "破底翻"
    assert lv["breakdown_low"] == 95.0


def test_derive_levels_no_consolidation_low_is_none():
    """最近高之後尚無擺動低 → consolidation_low = None(§4.6 三態,不腦補)。"""
    swings = [
        {"idx": 0, "price": 100.0, "kind": "low"},
        {"idx": 1, "price": 130.0, "kind": "high"},
    ]
    lv = derive_caisen_levels(swings, current_price=128.0)
    assert lv["consolidation_low"] is None
    assert lv["pattern"] == "型態未明"


def test_derive_end_to_end_from_detect_swings():
    """detect_swings → derive_caisen_levels 串接一致。"""
    seq = [100.0, 130.0, 115.0, 145.0]
    piv = detect_swings(seq, seq, pct=0.08)
    lv = derive_caisen_levels(piv, current_price=145.0)
    assert lv["wave1_high"] == 130.0
    assert lv["wave1_start"] == 100.0
    assert lv["consolidation_low"] == 115.0


# ── 4. 邊界 ────────────────────────────────────────────────────────
def test_derive_levels_insufficient_swings_returns_none():
    assert derive_caisen_levels([], current_price=100.0) is None
    assert derive_caisen_levels([{"idx": 0, "price": 100.0, "kind": "low"}],
                                current_price=100.0) is None
    # 只有低點、無高點 → None
    assert derive_caisen_levels(
        [{"idx": 0, "price": 100.0, "kind": "low"},
         {"idx": 1, "price": 90.0, "kind": "low"}],
        current_price=95.0) is None


def test_missing_consolidation_low_target_n_none_box_ok():
    """缺 consolidation_low → target_n=None,但 target_box 仍算得出。"""
    r = compute_caisen_targets(
        pattern="型態未明",
        support=100,
        breakdown_low=95,
        wave1_start=100,
        wave1_high=130,
        consolidation_low=None,   # 缺
        neckline=120,
        current_price=120,
    )
    assert r["target_n"] is None
    # box_low = breakdown_low(95);target_box = 120 + (130-95) = 155
    assert math.isclose(r["target_box"], 155.0, rel_tol=1e-9)
    assert math.isclose(r["target1"], 155.0, rel_tol=1e-9)  # 退回底型
    # sweet_low 無整理低 → 退回 support
    assert math.isclose(r["sweet_low"], 100.0, rel_tol=1e-9)


def test_target_box_falls_back_to_support_when_no_breakdown():
    """無 breakdown_low → box_low 退回 support。"""
    r = compute_caisen_targets(
        pattern="型態未明",
        support=90,
        breakdown_low=None,
        wave1_start=100,
        wave1_high=130,
        consolidation_low=None,
        neckline=120,
        current_price=120,
    )
    # box_low = support(90);target_box = 120 + (130-90) = 160
    assert math.isclose(r["target_box"], 160.0, rel_tol=1e-9)


def test_rr_none_on_zero_denominator():
    """sweet - stop ≤ 0 → rr=None(除零 guard,不炸不腦補)。"""
    r = compute_caisen_targets(
        pattern="破底翻",
        support=120,
        breakdown_low=125,     # stop = 125*0.99 = 123.75 > sweet(120) → 分母負
        wave1_start=100,
        wave1_high=130,
        consolidation_low=115,
        neckline=120,
        current_price=120,
    )
    assert r["sweet"] - r["stop"] <= 0
    assert r["rr"] is None


def test_all_none_inputs_no_crash():
    """全 None 輸入不炸,關鍵值回 None。"""
    r = compute_caisen_targets(
        pattern="型態未明",
        support=None,
        breakdown_low=None,
        wave1_start=None,
        wave1_high=None,
        consolidation_low=None,
        neckline=None,
        current_price=None,
    )
    assert r["sweet"] is None
    assert r["stop"] is None
    assert r["target_n"] is None
    assert r["target_box"] is None
    assert r["target1"] is None
    assert r["rr"] is None
    assert isinstance(r["notes"], list) and r["notes"]


def test_result_dict_has_all_keys():
    """回傳 dict 契約:所有 key 齊備。"""
    r = compute_caisen_targets(
        pattern="N字整理", support=100, breakdown_low=95, wave1_start=100,
        wave1_high=130, consolidation_low=115, neckline=120, current_price=120,
    )
    for k in ("sweet", "sweet_low", "sweet_high", "stop", "target_n",
              "target_box", "target2", "target1", "rr", "pattern", "notes"):
        assert k in r


# ── 5. summarize_caisen(批次摘要 + 誠實 gate)──────────────────────
_SUMMARY_KEYS = ("pattern", "sweet", "dist_pct", "stop", "target1", "rr",
                 "levels", "ok", "reason")


def test_summarize_contract_keys():
    """回傳 dict 契約:批次摘要 key 齊備。"""
    s = summarize_caisen([100.0, 130.0, 115.0, 145.0],
                         [100.0, 130.0, 115.0, 145.0], 145.0, pct=0.08)
    for k in _SUMMARY_KEYS:
        assert k in s


def test_summarize_n_pattern_actionable():
    """N字型態 → 有可操作數字:pattern/sweet/rr/dist_pct 皆備、ok=True、reason=None。"""
    seq = [100.0, 130.0, 115.0, 145.0]
    s = summarize_caisen(seq, seq, 145.0, pct=0.08)
    assert s["pattern"] == "N字整理"
    assert math.isclose(s["sweet"], 130.0, rel_tol=1e-9)   # 甜蜜價=頸線=wave1_high
    assert s["rr"] is not None and s["rr"] > 0
    assert s["ok"] is True
    assert s["reason"] is None
    # 距甜蜜價% = (145-130)/130*100 ≈ +11.54(已突破)
    assert math.isclose(s["dist_pct"], (145 - 130) / 130 * 100, rel_tol=1e-9)
    assert s["levels"] is not None


def test_summarize_gate_blocks_undetermined_pattern():
    """型態未明:引擎止損退化會灌假高 rr → 封鎖所有可操作數字,只留 pattern + reason。"""
    # [100,150,120]:上衝後回落確認高、其後無擺動低 → consolidation_low=None → 型態未明
    seq = [100.0, 150.0, 120.0]
    s = summarize_caisen(seq, seq, 120.0, pct=0.08)
    assert s["pattern"] == "型態未明"
    assert s["sweet"] is None
    assert s["stop"] is None
    assert s["target1"] is None
    assert s["rr"] is None          # ← 關鍵:不給假高風報比
    assert s["dist_pct"] is None
    assert s["ok"] is False
    assert s["reason"] == "型態未明·需看圖"
    assert s["levels"] is not None  # levels 仍回傳供下鑽看圖


def test_summarize_insufficient_swings():
    """擺動點不足 → 全 None、pattern=None、reason 標明,不腦補。"""
    s = summarize_caisen([100.0, 105.0], [100.0, 105.0], 105.0, pct=0.08)
    assert s["pattern"] is None
    assert s["levels"] is None
    assert s["ok"] is False
    assert s["reason"] == "擺動點不足"
    assert all(s[k] is None for k in ("sweet", "dist_pct", "stop", "target1", "rr"))
