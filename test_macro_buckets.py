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
    # v18.286 加入 10Y / DXY 鏡像
    assert mb._US10Y_YELLOW == MACRO_THRESHOLDS["US10Y"]["yellow_above"]
    assert mb._US10Y_RED == MACRO_THRESHOLDS["US10Y"]["red_above"]
    assert mb._DXY_YELLOW == MACRO_THRESHOLDS["DXY"]["yellow_above"]
    assert mb._DXY_RED == MACRO_THRESHOLDS["DXY"]["red_above"]


def test_us10y_dxy_specs_registered():
    """v18.286:us10y / dxy 加入 SPECS_BY_KEY 供 chart hline 使用。"""
    assert "us10y" in mb.SPECS_BY_KEY
    assert "dxy" in mb.SPECS_BY_KEY
    _y = mb.SPECS_BY_KEY["us10y"]
    assert _y.yellow == 4.5 and _y.red == 5.0
    _d = mb.SPECS_BY_KEY["dxy"]
    assert _d.yellow == 105.0 and _d.red == 110.0


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


# ──────────────────────────────────────────────────────────
# 4. aggregate_level / fmt_value
# ──────────────────────────────────────────────────────────
def test_aggregate_level():
    assert mb.aggregate_level(["green", "yellow", "red"]) == "red"
    assert mb.aggregate_level(["green", "yellow", "gray"]) == "yellow"
    assert mb.aggregate_level(["green", "green"]) == "green"
    assert mb.aggregate_level(["gray", "gray"]) == "gray"   # 全未載入
    assert mb.aggregate_level([]) == "gray"


def test_fmt_value():
    vix = mb.SPECS_BY_KEY["vix"]      # decimals=1 unit=""
    margin = mb.SPECS_BY_KEY["margin"]  # decimals=0 unit="億"
    assert mb.fmt_value(22.34, vix) == "22.3"
    assert mb.fmt_value(3400, margin) == "3400億"
    assert mb.fmt_value(None, vix) == "—"


# ──────────────────────────────────────────────────────────
# 5. compute_five_bucket_summary（L2 macro_helpers）
# ──────────────────────────────────────────────────────────
def test_compute_all_buckets_present():
    from macro_helpers import compute_five_bucket_summary
    out = compute_five_bucket_summary()
    assert set(out.keys()) == set(mb.BUCKET_ORDER)
    for b in mb.BUCKET_ORDER:
        assert out[b]["level"] in ("green", "yellow", "red", "gray")
        assert out[b]["emoji"] in mb.LEVEL_EMOJI.values()
        assert isinstance(out[b]["details"], list)


def test_compute_empty_is_gray():
    """全 None → 每桶 gray（§1：不偽綠）。"""
    from macro_helpers import compute_five_bucket_summary
    out = compute_five_bucket_summary()
    for b in mb.BUCKET_ORDER:
        assert out[b]["level"] == "gray", f"{b} 應 gray"


def test_compute_red_scenario():
    import pandas as pd
    from macro_helpers import compute_five_bucket_summary
    out = compute_five_bucket_summary(
        macro_info={
            "vix": {"current": 35},          # ≥30 → short red
            "ism_pmi": {"value": 44},         # <46 → mid red
            "us_core_cpi": {"yoy": 4.5},      # >4 → mid red
            "tw_export": {"yoy": -8},         # <-5 → mid red
            "ndc_signal": {"score": 14},      # ≤16 → long red
        },
        warroom_summary={"health_score": 30},  # <35 → long red
        m1b_m2_info={"gap": -0.5},             # <0 → long red
        bias_info={"bias_240": 25},            # >20 → mid red
        cl_data={"adl": pd.DataFrame({"ad_ratio": [30]}), "margin": 3500},  # adl<35 / margin>3400
        news_items=[{"is_systemic": True}, {"is_systemic": True}],  # 2 → news red
    )
    assert out["long"]["level"] == "red"
    assert out["mid"]["level"] == "red"
    assert out["short"]["level"] == "red"
    assert out["chips"]["level"] == "red"
    assert out["news"]["level"] == "red"


def test_compute_green_scenario():
    from macro_helpers import compute_five_bucket_summary
    out = compute_five_bucket_summary(
        macro_info={
            "vix": {"current": 15},
            "ism_pmi": {"value": 55},
            "us_core_cpi": {"yoy": 2.0},
            "tw_export": {"yoy": 5},
            "ndc_signal": {"score": 28},
        },
        warroom_summary={"health_score": 70},
        m1b_m2_info={"gap": 2.0},
        bias_info={"bias_240": 5},
        news_items=[],   # 0 systemic → news green
    )
    assert out["long"]["level"] == "green"
    assert out["mid"]["level"] == "green"
    assert out["short"]["level"] == "green"   # vix green（adl/fut gray 被忽略）
    assert out["news"]["level"] == "green"


def test_compute_news_yellow_on_single_systemic():
    from macro_helpers import compute_five_bucket_summary
    out = compute_five_bucket_summary(news_items=[{"is_systemic": True}, {"is_systemic": False}])
    assert out["news"]["level"] == "yellow"


# ──────────────────────────────────────────────────────────
# 4. chips_empty_state_html — v18.336 §1 Fail Loud 籌碼三源全空診斷
# ──────────────────────────────────────────────────────────
def test_chips_empty_state_not_attempted():
    """冷啟動未點更新 → 灰色「尚未載入」提示點按鈕。"""
    h = mb.chips_empty_state_html(attempted=False, token_present=False)
    assert "📡" in h and "尚未載入" in h
    assert "一鍵更新全部數據" in h
    assert "#6e7681" in h          # 灰
    assert "FINMIND_TOKEN" not in h  # 未嘗試不該嚇人提 token


def test_chips_empty_state_attempted_no_token():
    """點過更新仍空 + 無 token → 橙色明確指向 FINMIND_TOKEN(最可能根因)。"""
    h = mb.chips_empty_state_html(attempted=True, token_present=False)
    assert "⚠️" in h and "FINMIND_TOKEN" in h
    assert "已嘗試" in h
    assert "#f0883e" in h          # 橙


def test_chips_empty_state_attempted_with_token():
    """點過更新仍空 + 有 token → 橙色歸因暫時性(來源無回應/額度),不誤指 token 缺失。"""
    h = mb.chips_empty_state_html(attempted=True, token_present=True)
    assert "⚠️" in h
    assert "暫時" in h or "無回應" in h
    # 有 token 時不該說「偵測不到 FINMIND_TOKEN」
    assert "偵測不到" not in h


def test_chips_empty_state_always_valid_div():
    """三情境都回合法單一 <div> 容器(不偽造數字、不空字串)。"""
    for _att in (True, False):
        for _tok in (True, False):
            h = mb.chips_empty_state_html(attempted=_att, token_present=_tok)
            assert h.startswith("<div") and h.rstrip().endswith("</div>")
            assert "籌碼資料未顯示" in h


# ──────────────────────────────────────────────────────────
# 5. bucket_indicator_cards_html — v18.338 Fund 式分組卡片網格
# ──────────────────────────────────────────────────────────
def test_long_specs_have_emoji():
    """🌳 長期桶 3 指標都有小圖（卡片網格用），其餘桶預設空字串。"""
    for k in ("health", "ndc_signal", "m1b_m2_gap"):
        assert mb.SPECS_BY_KEY[k].emoji, f"{k} 缺 emoji"
    # 未指定 emoji 的指標預設空字串（向下相容）
    assert mb.SPECS_BY_KEY["vix"].emoji == ""


def test_cards_render_emoji_value_note():
    bs = {"details": [
        {"key": "health", "label": "總經健康評分", "value_str": "41",
         "danger": "yellow", "note": "<35 防禦 / <50 轉弱"},
        {"key": "m1b_m2_gap", "label": "M1B-M2 資金動能", "value_str": "-13.86%",
         "danger": "red", "note": "≥1 黃金交叉 / <0 死亡交叉"},
    ]}
    h = mb.bucket_indicator_cards_html(bs)
    assert "🩺" in h and "💰" in h            # 小圖
    assert "41" in h and "-13.86%" in h        # 值
    assert "防禦" in h and "黃金交叉" in h      # SPEC 註解
    assert "🟡" in h and "🔴" in h             # 燈號
    # 燈號色（紅/黃）入卡
    assert mb.LEVEL_COLOR["red"] in h and mb.LEVEL_COLOR["yellow"] in h


def test_cards_unknown_key_fallback_emoji():
    """details key 無對應 spec → fallback 📊（不爆）。"""
    h = mb.bucket_indicator_cards_html(
        {"details": [{"key": "nonexist", "label": "X", "value_str": "1",
                      "danger": "green", "note": "n"}]})
    assert "📊" in h and "X" in h


def test_cards_empty_details_loud_not_blank():
    """details 缺 → 「未載入」提示（§1 不偽造、不空字串）。"""
    assert "尚未載入" in mb.bucket_indicator_cards_html({})
    assert "尚未載入" in mb.bucket_indicator_cards_html({"details": []})


# ──────────────────────────────────────────────────────────
# 6. leading_table_empty_state_html — v18.340 §1 先行指標表三狀態分流
#    user 2026-06-28「原來的 table 呢?」對比 6/14 截圖 → 4 FinMind API 全敗時
#    原診斷文案沒明指 FINMIND_TOKEN,user 找不到救法。對齊 PR #362 chips 三狀態
#    分流模式,table 專屬 helper。
# ──────────────────────────────────────────────────────────
def test_leading_table_empty_not_attempted():
    """冷啟動未點更新 → 灰色「尚未載入」提示點按鈕。"""
    h = mb.leading_table_empty_state_html(attempted=False, token_present=False)
    assert "📡" in h and "尚未載入" in h
    assert "一鍵更新全部數據" in h
    assert "#6e7681" in h          # 灰
    assert "FINMIND_TOKEN" not in h  # 未嘗試不該嚇人提 token


def test_leading_table_empty_attempted_no_token():
    """點過更新仍空 + 無 token → 橙色明確指向 FINMIND_TOKEN(最可能根因)。"""
    h = mb.leading_table_empty_state_html(attempted=True, token_present=False)
    assert "⚠️" in h and "FINMIND_TOKEN" in h
    assert "已嘗試" in h
    assert "#f0883e" in h          # 橙
    # 4 個 FinMind API 名稱應出現(讓 user 明白範圍)
    assert "TX" in h and "TXO" in h


def test_leading_table_empty_attempted_with_token():
    """點過更新仍空 + 有 token → 橙色歸因額度/週末,不誤指 token 缺失。"""
    h = mb.leading_table_empty_state_html(attempted=True, token_present=True)
    assert "⚠️" in h
    # 該情境的常見三因
    assert "額度" in h or "週末" in h or "失效" in h
    # 有 token 時不該說「偵測不到 FINMIND_TOKEN」
    assert "偵測不到" not in h


def test_leading_table_empty_always_valid_div():
    """三情境都回合法單一 <div> 容器(不偽造數字、不空字串)。"""
    for _att in (True, False):
        for _tok in (True, False):
            h = mb.leading_table_empty_state_html(attempted=_att, token_present=_tok)
            assert h.startswith("<div") and h.rstrip().endswith("</div>")
            assert "先行指標明細表未顯示" in h
