"""tests/test_macro_state_canonical.py — ① 總經→選股 canonical 契約（v19.148）。

驗 normalize_regime（中/英/emoji/未知 → 英文）+ get_macro_state（warroom / 檔 / 皆無
→ 標準 dict + defense 推導 + is_loaded 誠實）。這兩支是「總經狀態單一契約」的核心，
個股頁加碼三問 / 個股組合評分 / AI regime 全靠它。純函式、離線可測。
"""
from __future__ import annotations

import json

from src.services.macro_state_locker import get_macro_state, normalize_regime


# ── normalize_regime ─────────────────────────────────────────
def test_normalize_english_passthrough():
    for r in ("bull", "neutral", "caution", "bear"):
        assert normalize_regime(r) == r
    assert normalize_regime("BULL") == "bull"        # 大小寫不敏感


def test_normalize_chinese():
    assert normalize_regime("多頭") == "bull"
    assert normalize_regime("空頭") == "bear"
    assert normalize_regime("震盪") == "neutral"
    assert normalize_regime("系統異常") == "neutral"   # fail-safe → 中性


def test_normalize_emoji_and_suffix():
    assert normalize_regime("🟢 多頭市場") == "bull"
    assert normalize_regime("🔴 空頭防禦") == "bear"
    assert normalize_regime("🟡 震盪整理") == "neutral"


def test_normalize_unknown_to_neutral():
    assert normalize_regime("") == "neutral"
    assert normalize_regime(None) == "neutral"
    assert normalize_regime("gibberish") == "neutral"


# ── get_macro_state ──────────────────────────────────────────
def test_warroom_bull_no_defense(tmp_path):
    _f = str(tmp_path / "nofile.json")                # 不存在 → 只走 warroom
    # C1 v19.182:fixture 補 `effective_regime`(紅綠燈決策樹的生效結論)。
    # `regime` 這個 key 現在的語意是**趨勢面輸入**,不再直接當結論 ——
    # 因為總經惡化(健康分跌破 / 外資期貨大額淨空)時燈號會覆蓋它,
    # 舊碼直接讀它正是「頁頂 🔴、頁底 🟢」那個矛盾的來源。
    wr = {"regime": "bull", "effective_regime": "bull", "light": "🟢",
          "market_score": 4, "health_score": 80, "traffic_light": "🟢 多頭市場"}
    ms = get_macro_state(wr, state_file_path=_f)
    assert ms["regime"] == "bull"
    assert ms["light"] == "🟢"
    assert ms["health"] == 80.0
    assert ms["is_loaded"] is True
    assert ms["defense"] is False                     # bull + 健康 80 → 不防守


def test_defense_when_low_health(tmp_path):
    _f = str(tmp_path / "nofile.json")
    ms = get_macro_state({"regime": "neutral", "health_score": 20}, state_file_path=_f)
    assert ms["defense"] is True                       # health 20 < 35 → 防守


def test_defense_when_bear(tmp_path):
    _f = str(tmp_path / "nofile.json")
    ms = get_macro_state({"regime": "bear", "health_score": 70}, state_file_path=_f)
    assert ms["defense"] is True                       # bear → 防守（不論健康）


def test_file_source_chinese_to_english(tmp_path):
    _f = tmp_path / "macro_state.json"
    _f.write_text(json.dumps({"market_regime": "空頭防禦", "exposure_limit_pct": 30}),
                  encoding="utf-8")
    ms = get_macro_state(None, state_file_path=str(_f))
    assert ms["regime"] == "bear"                      # 中文 → 英文
    assert ms["exposure_limit_pct"] == 30
    assert ms["is_loaded"] is True


def test_not_loaded_is_honest(tmp_path):
    _f = str(tmp_path / "nofile.json")                 # 無 warroom、無檔
    ms = get_macro_state(None, state_file_path=_f)
    assert ms["is_loaded"] is False                    # 誠實:未評估
    # ── C1 v19.182 契約變更（§1 Fail Loud）──────────────────────────────
    # 舊斷言是 `regime == "neutral"`，註解寫「不誤判多空」。但 'neutral' 在本
    # 系統裡**是一個市場判斷**（🟡 震盪整理），不是「沒有判斷」：ETF 三個分頁
    # 拿到它就會照跑整套核衛 70/30 判定並給出綠燈，而同一頁的配置橫幅卻印
    # 「⬜ 總經未評估」。「不知道」必須有自己的表示法。
    assert ms["regime"] == "unknown"
    assert ms["light"] == "⬜"
    assert ms["defense"] is False
