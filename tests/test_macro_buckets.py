"""test_macro_buckets.py — 五桶危險門檻 SSOT 註冊表測試 (v18.284)

重點：
1. drift guard — 鏡像值必須 == macro_core.MACRO_THRESHOLDS（CLAUDE.md §3.3 防漂移）
2. classify_danger 三方向（high_bad / low_bad / band）+ gray 邊界
3. 註冊表結構完整性（bucket 合法 / key 唯一 / 紅黃線方向自洽）
"""
import math

import pytest

from shared import macro_buckets as mb
from src.data.macro import MACRO_THRESHOLDS


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
# 1b. MACRO_INFO_KEYS — macro_info dict key 契約 SSOT(v18.349)
#     data_coverage 覆蓋率表 + tab_macro has-data 判定共用，杜絕 v18.282 漂移
# ──────────────────────────────────────────────────────────
def test_macro_info_keys_contract():
    """釘 macro_info 6 核心 key 契約;順序 + 內容(防誤刪/誤加)。"""
    assert mb.MACRO_INFO_KEYS == (
        "vix", "ism_pmi", "us_core_cpi", "fed_funds", "ndc_signal", "tw_export",
    )
    # tuple(不可變) → 避免 caller 意外 mutate 污染 SSOT
    assert isinstance(mb.MACRO_INFO_KEYS, tuple)


def test_macro_info_keys_overlap_danger_specs():
    """漂移守門:除 fed_funds(無門檻判讀)外,其餘 5 key 必須是 DangerSpec key。
    這正是 v18.282 那種 key typo 的攔截點 — 打錯字會在此 fail。"""
    _overlap = set(mb.MACRO_INFO_KEYS) - {"fed_funds"}
    _missing = _overlap - set(mb.SPECS_BY_KEY)
    assert not _missing, f"MACRO_INFO_KEYS 含非 DangerSpec key(疑似 typo): {_missing}"


def test_data_coverage_consumes_macro_info_keys_ssot():
    """src.ui.pages.data_coverage._macro_keys 必須來自 SSOT(非各自寫死)。
    以行為驗證:macro_info 放滿 SSOT key → 認列數 == len(SSOT)。"""
    import sys
    import types
    # 最小 streamlit stub(macro_buckets 不需 st,但 data_coverage import st)
    if "streamlit" not in sys.modules:
        _m = types.ModuleType("streamlit")
        _m.session_state = {}
        sys.modules["streamlit"] = _m
    from src.ui.pages import compute_tab_coverage
    _macro = {k: {"current": 1.0} for k in mb.MACRO_INFO_KEYS}
    rows = compute_tab_coverage(state={"macro_info": _macro})
    macro_row = next(r for r in rows if "總經" in r["tab"])
    # ⚠️ 2026-08-20:分母改為**已接線的決策燈**(`BUCKET_DANGER_SPECS`),
    #    不再是 macro_info 容器數。本測試的原始意圖(「非各自寫死、隨 SSOT 連動」)
    #    完全不變 —— 只是連動的對象換成真正驅動五桶決策的那一份清單。
    #    改動理由:舊分母 6 個容器,而決策實際吃 16 盞燈,差集 11 盞從不在檢查裡。
    _n_wired = sum(1 for s in mb.BUCKET_DANGER_SPECS if s.wired)
    assert macro_row["ratio_txt"].endswith(f"/{_n_wired}"), (
        f"覆蓋率分母未連動決策燈 SSOT：{macro_row['ratio_txt']}")
    # 且 macro_info 容器計數仍以第二個子計數出現(user 2026-08-20 裁示:
    # fed_funds 這類「在 macro_info 但不是決策燈」的不該掉出畫面,
    # 但也不該與決策燈加總 —— 語意不同的東西不相加)。
    assert f"/{len(mb.MACRO_INFO_KEYS)} 有值" in macro_row["detail"], (
        f"macro 容器子計數消失：{macro_row['detail']}")


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
    from src.compute.macro import compute_five_bucket_summary
    out = compute_five_bucket_summary()
    assert set(out.keys()) == set(mb.BUCKET_ORDER)
    for b in mb.BUCKET_ORDER:
        assert out[b]["level"] in ("green", "yellow", "red", "gray")
        assert out[b]["emoji"] in mb.LEVEL_EMOJI.values()
        assert isinstance(out[b]["details"], list)


def test_compute_empty_is_gray():
    """全 None → 每桶 gray（§1：不偽綠）。"""
    from src.compute.macro import compute_five_bucket_summary
    out = compute_five_bucket_summary()
    for b in mb.BUCKET_ORDER:
        assert out[b]["level"] == "gray", f"{b} 應 gray"


def test_compute_red_scenario():
    import pandas as pd
    from src.compute.macro import compute_five_bucket_summary
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
    from src.compute.macro import compute_five_bucket_summary
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
    from src.compute.macro import compute_five_bucket_summary
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


# ──────────────────────────────────────────────────────────
# 7. v19.172 — 紅燈標籤依觸發方向分流(過熱 vs 惡化)
#    實機 bug：中期桶因 BIAS240 +32.7%(high_bad 過熱)轉紅，五桶摘要卻印
#    「🔴 循環惡化」，同頁四象限同時寫「主升段狂熱…順勢作多」→ 自相矛盾。
#    矛盾來源是**標籤**，不是燈號/門檻/處置(四象限本身自洽)。
# ──────────────────────────────────────────────────────────
def test_red_flavor_by_direction():
    """high_bad → 過熱；low_bad → 惡化；band 依觸發側。"""
    assert mb.red_flavor(mb.SPECS_BY_KEY["bias_240"], 32.7) == mb.RED_FLAVOR_OVERHEAT
    assert mb.red_flavor(mb.SPECS_BY_KEY["us_core_cpi"], 4.5) == mb.RED_FLAVOR_OVERHEAT
    assert mb.red_flavor(mb.SPECS_BY_KEY["ism_pmi"], 44) == mb.RED_FLAVOR_DETERIORATION
    assert mb.red_flavor(mb.SPECS_BY_KEY["tw_export"], -8) == mb.RED_FLAVOR_DETERIORATION
    _ndc = mb.SPECS_BY_KEY["ndc_signal"]          # band: red_lo=16 / red=38
    assert mb.red_flavor(_ndc, 40) == mb.RED_FLAVOR_OVERHEAT        # ≥38 紅過熱側
    assert mb.red_flavor(_ndc, 12) == mb.RED_FLAVOR_DETERIORATION   # ≤16 藍衰退側
    # 值不可解析 → 保守維持原標籤語意(不擅自改口徑)
    assert mb.red_flavor(_ndc, None) == mb.RED_FLAVOR_DETERIORATION
    assert mb.red_flavor(_ndc, "n/a") == mb.RED_FLAVOR_DETERIORATION


def test_bucket_level_label_backward_compatible():
    """不傳 spec → 與原 BUCKET_LEVEL_LABEL 逐格一致(caller 介面 0 改變)。"""
    for _b in mb.BUCKET_ORDER:
        for _lv in ("green", "yellow", "red", "gray"):
            assert mb.bucket_level_label(_b, _lv) == mb.BUCKET_LEVEL_LABEL[_b][_lv]


def test_bucket_level_label_red_overheat_vs_deterioration():
    """紅燈才分流；long / mid 有過熱版，其餘桶語意中性維持原字串。"""
    assert mb.bucket_level_label(
        "mid", "red", spec=mb.SPECS_BY_KEY["bias_240"], value=32.7) == "循環過熱"
    assert mb.bucket_level_label(
        "mid", "red", spec=mb.SPECS_BY_KEY["ism_pmi"], value=44) == "循環惡化"
    assert mb.bucket_level_label(
        "long", "red", spec=mb.SPECS_BY_KEY["ndc_signal"], value=40) == "結構過熱"
    assert mb.bucket_level_label(
        "long", "red", spec=mb.SPECS_BY_KEY["ndc_signal"], value=12) == "結構防禦"
    # 方向中性的桶不分流
    assert mb.bucket_level_label(
        "short", "red", spec=mb.SPECS_BY_KEY["vix"], value=35) == "急殺風險"
    assert mb.bucket_level_label(
        "chips", "red", spec=mb.SPECS_BY_KEY["margin"], value=5000) == "籌碼危險"


def test_bucket_level_label_non_red_not_flavored():
    """v19.172 範圍限定紅燈；黃 / 綠 / 灰維持原字串(不擴大行為變更面)。"""
    for _lv in ("green", "yellow", "gray"):
        _got = mb.bucket_level_label(
            "mid", _lv, spec=mb.SPECS_BY_KEY["bias_240"], value=15)
        assert _got == mb.BUCKET_LEVEL_LABEL["mid"][_lv], _lv


def test_bucket_level_label_unknown_key_fails_loud():
    """§1：未知 bucket / level 不得靜默回空字串。"""
    with pytest.raises(KeyError):
        mb.bucket_level_label("nonexist", "red")
    with pytest.raises(KeyError):
        mb.bucket_level_label("mid", "purple")


def test_danger_exceedance_zero_and_negative_thresholds():
    """§4.1：門檻含 0 / 負值 → 不可用倍數；帶寬正規化須成立且不除零。"""
    _exp = mb.SPECS_BY_KEY["tw_export"]     # low_bad yellow=0 red=-5
    assert math.isclose(mb.danger_exceedance(-8, _exp, "red"), 0.6, abs_tol=1e-9)
    _gap = mb.SPECS_BY_KEY["m1b_m2_gap"]    # low_bad yellow=1 red=0
    assert math.isclose(mb.danger_exceedance(-0.5, _gap, "red"), 0.5, abs_tol=1e-9)
    _fut = mb.SPECS_BY_KEY["fut_net"]       # low_bad yellow=-10000 red=-20000
    assert math.isclose(mb.danger_exceedance(-30000, _fut, "red"), 1.0, abs_tol=1e-9)
    _bias = mb.SPECS_BY_KEY["bias_240"]     # high_bad yellow=10 red=20
    assert math.isclose(mb.danger_exceedance(32.7, _bias, "red"), 1.27, abs_tol=1e-9)
    # 黃燈以黃線為基準
    assert math.isclose(mb.danger_exceedance(15, _bias, "yellow"), 0.5, abs_tol=1e-9)


def test_danger_exceedance_degrades_to_zero_not_crash():
    """不可解析 / 非 red|yellow → 0.0(排序退回註冊順序,不爆)。"""
    _bias = mb.SPECS_BY_KEY["bias_240"]
    assert mb.danger_exceedance(None, _bias, "red") == 0.0
    assert mb.danger_exceedance("n/a", _bias, "red") == 0.0
    assert mb.danger_exceedance(float("nan"), _bias, "red") == 0.0
    assert mb.danger_exceedance(32.7, _bias, "green") == 0.0
    assert mb.danger_exceedance(32.7, _bias, "gray") == 0.0


def test_danger_exceedance_band_both_sides():
    _ndc = mb.SPECS_BY_KEY["ndc_signal"]   # yellow_lo=23 yellow=32 red_lo=16 red=38
    assert math.isclose(mb.danger_exceedance(44, _ndc, "red"), 1.0, abs_tol=1e-9)   # (44-38)/6
    assert math.isclose(mb.danger_exceedance(9, _ndc, "red"), 1.0, abs_tol=1e-9)    # (16-9)/7
    assert mb.danger_exceedance(28, _ndc, "red") == 0.0    # 綠區,兩側皆未觸發


def test_five_bucket_mid_red_label_overheat_on_bias():
    """實機重現：中期桶只有 BIAS240 過熱轉紅 → 標籤須是「循環過熱」不是「循環惡化」。"""
    from src.compute.macro import compute_five_bucket_summary
    out = compute_five_bucket_summary(
        macro_info={"ism_pmi": {"value": 55}, "us_core_cpi": {"yoy": 2.0},
                    "tw_export": {"yoy": 54.6}},
        bias_info={"bias_240": 32.7},
    )
    assert out["mid"]["level"] == "red"
    assert out["mid"]["label"] == "循環過熱"
    assert "年線乖離" in out["mid"]["headline"]


def test_five_bucket_mid_red_label_deterioration_on_pmi():
    """反向：由 PMI(low_bad)觸發 → 仍是「循環惡化」(原語意保留)。"""
    from src.compute.macro import compute_five_bucket_summary
    out = compute_five_bucket_summary(
        macro_info={"ism_pmi": {"value": 40}, "us_core_cpi": {"yoy": 2.0},
                    "tw_export": {"yoy": 5}},
        bias_info={"bias_240": 5},
    )
    assert out["mid"]["level"] == "red"
    assert out["mid"]["label"] == "循環惡化"
    assert "PMI" in out["mid"]["headline"]


def test_five_bucket_long_red_label_overheat_on_ndc():
    """長期桶 band 指標 NDC 熱到紅(≥38)→「結構過熱」；藍燈(≤16)→「結構防禦」。"""
    from src.compute.macro import compute_five_bucket_summary
    _hot = compute_five_bucket_summary(
        macro_info={"ndc_signal": {"score": 41}},
        warroom_summary={"health_score": 70}, m1b_m2_info={"gap": 2.0},
    )
    assert _hot["long"]["level"] == "red" and _hot["long"]["label"] == "結構過熱"
    _cold = compute_five_bucket_summary(
        macro_info={"ndc_signal": {"score": 12}},
        warroom_summary={"health_score": 70}, m1b_m2_info={"gap": 2.0},
    )
    assert _cold["long"]["level"] == "red" and _cold["long"]["label"] == "結構防禦"


def test_five_bucket_headline_picks_most_severe_not_first_registered():
    """v19.172：同桶多盞紅 → headline 取超標幅度最大者,非註冊順序第一個。

    中期桶註冊順序 ism_pmi → us_core_cpi → tw_export → bias_240。
    本例 PMI 45.5(僅超紅線 0.5/4 帶寬)vs BIAS 60(超 4.0 帶寬)→ 主因應是 BIAS。
    """
    from src.compute.macro import compute_five_bucket_summary
    out = compute_five_bucket_summary(
        macro_info={"ism_pmi": {"value": 45.5}, "us_core_cpi": {"yoy": 2.0},
                    "tw_export": {"yoy": 5}},
        bias_info={"bias_240": 60.0},
    )
    assert out["mid"]["level"] == "red"
    assert "年線乖離" in out["mid"]["headline"], out["mid"]["headline"]
    assert out["mid"]["label"] == "循環過熱"


# ──────────────────────────────────────────────────────────
# 8. v19.173 — 「總經健康評分」名不副實 → note 須誠實揭露因子組成
#
#    實機回報：五桶 4 盞紅，綜合健康度仍有 44 分。查證結論是**不是算錯** ——
#    compute_macro_health 在建構上只吃 2 個輸入：
#        health = jqavg × 0.6 + min(score/max_score×100,100) × 0.4 + 0
#    jqavg = 旌旗指數（站上 20MA 家數比）＝廣度；外資加分項 v19.102 校準後歸零。
#    本註冊表 16 個 DangerSpec 中，health 自己是輸出、真正餵進公式的只有 jingqi
#    （score 來自 mkt_info，不在註冊表內）；其餘 14 項（融資 / 外資期貨 / 年線乖離 /
#    NDC / M1B-M2 / VIX / PMI / CPI / 出口 / ADL / 新聞 …）**一個都沒有**。
#    使用者從「總經健康評分」這個名字完全看不出來 → 名不副實。
#
#    本版決策：**不全站改名**（會動到大量 UI 字串與 source-scan 測試，風險與收益
#    不對稱），改為在顯示處誠實揭露。這兩條測試就是防止未來有人「順手清掉太長的
#    note」把揭露刪掉 —— 揭露一旦消失，名不副實就悄悄復發。
# ──────────────────────────────────────────────────────────
def test_health_note_discloses_factor_composition():
    """health 的 note 必須講清楚「由誰組成、不含誰」。"""
    _note = mb.SPECS_BY_KEY["health"].note
    # 原有門檻語意不得被揭露文字擠掉
    assert "35" in _note and "50" in _note, "原門檻語意（<35 防禦 / <50 轉弱）不見了"
    # 兩個真實輸入 + 權重（對齊 shared/signal_thresholds.HEALTH_WEIGHT_*）
    assert "旌旗" in _note and "60%" in _note, "未揭露 jqavg（旌旗指數）權重"
    assert "大盤評分" in _note and "40%" in _note, "未揭露 score（大盤評分）權重"
    # 明講「不含什麼」—— 否則使用者仍會以為它綜合了五桶
    assert "不含" in _note, "未明講排除項"
    for _kw in ("融資", "外資期貨", "VIX", "PMI"):
        assert _kw in _note, f"note 未點名排除項: {_kw}"


def test_health_note_survives_card_render():
    """揭露文字必須真的印進卡片（不能只躺在 dataclass 裡沒人看得到）。"""
    _spec = mb.SPECS_BY_KEY["health"]
    h = mb.bucket_indicator_cards_html({"details": [
        {"key": "health", "label": _spec.label, "value_str": "44",
         "danger": "yellow", "note": _spec.note},
    ]})
    assert "旌旗" in h and "不含" in h, "卡片沒印出因子組成揭露"
    assert "44" in h and "🩺" in h


def test_health_weights_still_sum_to_one_and_fnet_is_dead_term():
    """v19.173 只改註解 / 揭露文字 —— 三個權重常數必須原封不動。

    §4.2 權重和 = 1；HEALTH_FNET_BONUS = 0 是 v19.102 校準後的**明示歸零**
    （有 AUC 佐證，非漏寫），本版不得順手「修好」它 —— 改值＝改行為，
    需重跑校準，屬另案。
    """
    from shared.signal_thresholds import (
        HEALTH_FNET_BONUS, HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE,
    )
    assert math.isclose(HEALTH_WEIGHT_JQ + HEALTH_WEIGHT_SCORE, 1.0, abs_tol=1e-9)
    assert HEALTH_FNET_BONUS == 0


def test_health_danger_lines_unchanged_by_v19_173():
    """揭露不得順手動門檻：red=35（DEFENSE 預設）/ yellow=50（DESIGN）。"""
    _spec = mb.SPECS_BY_KEY["health"]
    assert _spec.red == 35.0 and _spec.yellow == 50.0
    assert _spec.direction == "low_bad" and _spec.bucket == "long"
