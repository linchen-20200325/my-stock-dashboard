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
    wr = {"regime": "bull", "health_score": 80, "traffic_light": "🟢 多頭市場"}
    ms = get_macro_state(wr, state_file_path=_f)
    assert ms["regime"] == "bull"
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
    assert ms["regime"] == "neutral"                   # 不誤判多空
    assert ms["defense"] is False
