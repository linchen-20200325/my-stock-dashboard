"""批 Z18（客戶 2026-10-09 Q-r15a 裁示「1：A」）—— 門檻說明（note）符號依實際判燈邊界修正。

裁示原文：「A 原則同意 14 列依實際程式邊界修正；但受第 2 題裁示影響，第 4、14 列暫緩，
不得先改」。本批只改其中 12 列使用者可見字串（只改 `<`／`>`／區間寫法 → `≤`／`≥`，
其餘一字不動）；⛔ 不改門檻常數、⛔ 不改判燈邏輯。

本檔兩件事：
1. **逐字守衛**：12 列的新字句（note 前綴 / 第 3 列 source 全句）。
2. **邊界語意守衛**：以 `classify_danger` 的**實際門檻**，驗證「剛好等於門檻的值」
   落在 note 所寫的那一側（例：健康評分 35 判紅、note 寫「≤35 防禦」）。
   修前 note 寫「<35」，等於門檻的值在字面上不屬於「防禦」，但程式判紅 → 字與燈打架。

⛔ 暫緩（不得先改）：第 4 列 `ism_pmi` note、第 14 列 section_mid PMI 說明 —— 本檔
另以守衛釘住它們**維持原句**，防止被順手改掉。
"""
from __future__ import annotations

import pytest

import shared.macro_buckets as mb

S = mb.SPECS_BY_KEY

#: 第 1、2、5~13 列：note 必須以新字句開頭（note 後段的揭露文字不在本批範圍，一字未動）。
NOTE_PREFIX = {
    "health": "≤35 防禦 / ≤50 轉弱",                       # 1
    "m1b_m2_gap": ">1 黃金交叉 / ≤0 死亡交叉",              # 2
    "us_core_cpi": "≥3.5% 外資提款風險 / ≥4% 通膨嚴峻",      # 5
    "tw_export": "≤0% 衰退邊界 / ≤-5% 連續衰退",             # 6
    "bias_240": "≥+20% 正乖離過熱",                          # 7
    "adl": "≤50 廣度轉弱 / ≤35 廣度崩",                       # 8
    "fut_net": "≤-10000 避險 / ≤-20000 大戶閃人",             # 9
    "margin": "≥2500 警戒 / ≥3400 散戶槓桿極危",              # 10
    "jingqi": ">60 積極 / ≤60 中性 / ≤40 弱勢",               # 11
    # 12：Q-r15a 只改 -200 段；之後裁示 3：B 再補「（0 亦判黃）」（見檔尾）。
    "foreign_net": ">0 買超 / <0 賣超（0 亦判黃）/ ≤-200 大賣（軟線）",
}
USDTWD_NOTE_PREFIX = "≥32 台幣貶值警戒 / ≥33 外資撤離壓力"      # 13
M1B_SOURCE = "系統設計之警示線（資金動能交叉慣例）：>1 黃金交叉／≤0 死亡交叉"  # 3


def _usdtwd():
    return next(s for s in mb.REFERENCE_TREND_SPECS if s.key == "usdtwd")


@pytest.mark.parametrize("key,prefix", sorted(NOTE_PREFIX.items()))
def test_note_new_wording(key, prefix):
    assert S[key].note.startswith(prefix), f"{key} note 未照 Q-r15a 擬句：{S[key].note!r}"


def test_m1b_note_exact():
    assert S["m1b_m2_gap"].note == ">1 黃金交叉 / ≤0 死亡交叉"


def test_m1b_source_exact():
    assert S["m1b_m2_gap"].source == M1B_SOURCE


def test_usdtwd_note_new_wording():
    _n = _usdtwd().note
    assert _n.startswith(USDTWD_NOTE_PREFIX), _n
    # 後段（強勢區說明 + 參考走勢聲明）一字未動
    assert "（＜30.5 為台幣強勢區，非燈號等級）" in _n
    assert "**參考走勢：不計入 16 盞燈的分母、不進五桶彙總。**" in _n


def test_note_tails_untouched():
    """note 後段的揭露文字不在本批範圍 —— 確認沒被順手改掉。"""
    assert S["health"].note.startswith("≤35 防禦 / ≤50 轉弱（此分只有 2 個輸入")
    assert S["bias_240"].note == "≥+20% 正乖離過熱（負乖離為超賣機會，非危險）"
    assert S["adl"].note == ("≤50 廣度轉弱 / ≤35 廣度崩（大型股獨撐）"
                             "（此為佔比類指標,不受市值成長侵蝕,但仍建議對照歷史分位判讀）")
    assert S["fut_net"].note == "≤-10000 避險 / ≤-20000 大戶閃人"
    assert S["us_core_cpi"].note == "≥3.5% 外資提款風險 / ≥4% 通膨嚴峻"
    assert S["tw_export"].note == "≤0% 衰退邊界 / ≤-5% 連續衰退"
    assert S["foreign_net"].note == ">0 買超 / <0 賣超（0 亦判黃）/ ≤-200 大賣（軟線）"  # 裁示 3：B
    assert "（⚠️ 本項用的是絕對金額門檻" in S["margin"].note
    assert "（此值為上漲佔比的 5 日均" in S["jingqi"].note


def test_deferred_rows_untouched():
    """⛔ 第 4 列（ism_pmi note）於 Z18 暫緩，Q-r15a 明令不得先改。

    批 Z19 更新：客戶 PMI=50 裁示（=50 中性／榮枯線，1：A 採擬稿全句）後本列已不再暫緩，
    改釘 Z19 核准字（逐字守衛另見 `tests/test_batch_z19.py`）。
    """
    assert S["ism_pmi"].note == "=50 中性（榮枯線） / <50 收縮 / ≤46 嚴重收縮"


# ── 邊界語意：剛好等於門檻的值，燈號要落在 note 所寫的那一側 ──
#    (key, 等於門檻的值, 預期燈號, note 中描述該側的片段)
BOUNDARY_CASES = [
    ("health", 35.0, "red", "≤35 防禦"),
    ("health", 50.0, "yellow", "≤50 轉弱"),
    ("m1b_m2_gap", 1.0, "yellow", ">1 黃金交叉"),     # 1.0 不算黃金交叉（判黃）
    ("m1b_m2_gap", 0.0, "red", "≤0 死亡交叉"),
    ("us_core_cpi", 3.5, "yellow", "≥3.5% 外資提款風險"),
    ("us_core_cpi", 4.0, "red", "≥4% 通膨嚴峻"),
    ("tw_export", 0.0, "yellow", "≤0% 衰退邊界"),
    ("tw_export", -5.0, "red", "≤-5% 連續衰退"),
    ("bias_240", 20.0, "red", "≥+20% 正乖離過熱"),
    ("adl", 50.0, "yellow", "≤50 廣度轉弱"),
    ("adl", 35.0, "red", "≤35 廣度崩"),
    ("fut_net", -10000.0, "yellow", "≤-10000 避險"),
    ("fut_net", -20000.0, "red", "≤-20000 大戶閃人"),
    ("margin", 2500.0, "yellow", "≥2500 警戒"),
    ("margin", 3400.0, "red", "≥3400 散戶槓桿極危"),
    ("jingqi", 60.0, "yellow", "≤60 中性"),           # 60 不算積極（判黃）
    ("jingqi", 40.0, "red", "≤40 弱勢"),
    ("foreign_net", -200.0, "red", "≤-200 大賣"),
]


@pytest.mark.parametrize("key,value,level,phrase", BOUNDARY_CASES)
def test_boundary_value_falls_on_side_note_says(key, value, level, phrase):
    spec = S[key]
    assert mb.classify_danger(value, spec) == level, "判燈邏輯不得變動"
    assert phrase in spec.note, f"{key}={value:g} 判 {level}，note 須寫「{phrase}」：{spec.note!r}"


def test_boundary_matches_spec_thresholds():
    """門檻常數未動：note 裡的數字就是 spec 的 yellow / red。"""
    assert (S["health"].red, S["health"].yellow) == (35.0, 50.0)
    assert (S["m1b_m2_gap"].yellow, S["m1b_m2_gap"].red) == (1.0, 0.0)
    assert (S["jingqi"].yellow, S["jingqi"].red) == (60.0, 40.0)
    assert (S["margin"].yellow, S["margin"].red) == (2500.0, 3400.0)
    assert (S["fut_net"].yellow, S["fut_net"].red) == (-10000.0, -20000.0)


@pytest.mark.parametrize("value,level,phrase", [
    (32.0, "yellow", "≥32 台幣貶值警戒"),
    (33.0, "red", "≥33 外資撤離壓力"),
])
def test_usdtwd_boundary(value, level, phrase):
    spec = _usdtwd()
    assert mb.classify_danger(value, spec) == level
    assert phrase in spec.note


# ══════════════════════════════════════════════════════════════════════════
# 追加（客戶 2026-10-09 裁示「採最簡版說明，能直接寫門檻就不要加入內部實作說明；
# 不改計算、門檻或邏輯」）：3 個 source 括號內字改最簡版。
# ⛔ ism_pmi source、foreign_net note 不在本次範圍（另由上方守衛釘住）。
# ══════════════════════════════════════════════════════════════════════════
SIMPLE_SOURCES = {
    "health": "紅線 35：有既有常數背書（防禦門檻預設值，手訂未校準）；黃線 50：系統設計之警示線（≤50 轉弱警示）",
    "tw_export": "紅線 -5%：沿用總經基本面否決檢查的出口門檻（台灣出口 YoY -5%）；黃線 0%：系統設計之警示線（衰退邊界）",
    "fut_net": "黃線 -10,000 口／紅線 -20,000 口：沿用 v4 引擎風險燈的外資期貨門檻（空單 1 萬口 黃燈／2 萬口 紅燈）",
}


@pytest.mark.parametrize("key,text", sorted(SIMPLE_SOURCES.items()))
def test_simple_source_wording(key, text):
    assert S[key].source == text


def test_simple_source_out_of_scope_untouched():
    # 批 Z19：ism_pmi source 依客戶 PMI=50 裁示改為 Z19 核准字（括號尾段移入 note），不再屬 Z18 範圍外暫緩。
    assert S["ism_pmi"].source == "黃線 50／紅線 46：有既有常數背書（統一閾值表）"
    assert S["foreign_net"].note == ">0 買超 / <0 賣超（0 亦判黃）/ ≤-200 大賣（軟線）"  # 裁示 3：B


# ══════════════════════════════════════════════════════════════════════════
# 再追加（客戶 2026-10-09 裁示 3：B）：「外資現貨 0 不能描述成賣超。採：
# 『>0 買超 / <0 賣超（0 亦判黃）/ ≤-200 大賣（軟線）』只修說明完整性，
# 不改既有判燈邏輯。」
# ══════════════════════════════════════════════════════════════════════════
FOREIGN_NET_NOTE = ">0 買超 / <0 賣超（0 亦判黃）/ ≤-200 大賣（軟線）"


def test_foreign_net_note_states_zero_is_yellow():
    assert S["foreign_net"].note == FOREIGN_NET_NOTE


def test_foreign_net_zero_is_yellow_as_note_says():
    """判燈邏輯不變：0 落在 low_bad 的 `v <= yellow(0)` → 黃；note 須明講。"""
    spec = S["foreign_net"]
    assert mb.classify_danger(0.0, spec) == "yellow"
    assert "（0 亦判黃）" in spec.note
    assert mb.classify_danger(0.01, spec) == "green"      # >0 買超
    assert mb.classify_danger(-0.01, spec) == "yellow"    # <0 賣超
    assert mb.classify_danger(-200.0, spec) == "red"      # ≤-200 大賣
