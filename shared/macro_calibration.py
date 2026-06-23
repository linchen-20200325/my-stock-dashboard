"""shared/macro_calibration.py — macro_thresholds.json loader SSOT(S-GRAY-1 v18.244)

從 L2 `macro_helpers.py`(屬「純函式 / 無 I/O」)下沉至 L0 Infra(config loader 屬
cross-cutting 基礎建設)。修復 CLAUDE.md §8.3 灰色地帶:
「`macro_helpers.py`:分類 L2 但有輕度 I/O(讀 `macro_thresholds.json`)→ 該抽 config-loader 到 L0」。

對外 API:
- `HEALTH_DEFENSE_THRESHOLD_DEFAULT` / `BULL_MIN_SCORE_DEFAULT`:json 缺檔 / 越界時 fallback
- `load_calibrated_thresholds()`:讀 json 回 `(HEALTH_DEFENSE_THRESHOLD, BULL_MIN_SCORE)` tuple

caller(`macro_helpers.py`)在 module-level 一次性呼叫,賦值給原 module-level 常數,
向後相容介面 0 改(caller import path 改 + module 內常數值來源改,API 不變)。

設計:純檔 I/O 模組,僅 `json` + `os` std lib 依賴,**無**外部 HTTP / streamlit / pandas。
"""
from __future__ import annotations
import json as _json
import os as _os
from typing import Tuple

# Default 常數(json 缺檔/越界時 fallback)。
# 來源:原 `macro_helpers.py:28-29`,值域守門 health ∈ [20, 60] / score ∈ [1, 6]。
HEALTH_DEFENSE_THRESHOLD_DEFAULT: int = 35
BULL_MIN_SCORE_DEFAULT: int = 4

# JSON 檔位置(repo root)。
# 由 `recalibrate_macro.yml` cron 季度 update,PR 審閱後 merge 寫入。
_CALIBRATION_PATH: str = _os.path.join(
    _os.path.dirname(_os.path.dirname(__file__)),  # shared/ → repo root
    'macro_thresholds.json',
)


def load_calibrated_thresholds() -> Tuple[int, int]:
    """讀 `macro_thresholds.json`,回傳 `(HEALTH_DEFENSE_THRESHOLD, BULL_MIN_SCORE)`。

    缺檔 / 解析失敗 / 值越界 → silently 回 default,不噴錯。
    Production 流程不應因設定檔損毀而連帶崩潰(L0 跨層失敗會牽動全棧)。

    值域守門:health ∈ [20, 60] / score ∈ [1, 6](維持原 macro_helpers loader 邏輯)。
    """
    try:
        if _os.path.exists(_CALIBRATION_PATH):
            with open(_CALIBRATION_PATH, 'r', encoding='utf-8') as _f:
                _cfg = _json.load(_f)
            _h = int(_cfg.get('HEALTH_DEFENSE_THRESHOLD', HEALTH_DEFENSE_THRESHOLD_DEFAULT))
            _s = int(_cfg.get('BULL_MIN_SCORE', BULL_MIN_SCORE_DEFAULT))
            # 越界守門:health ∈ [20, 60]、score ∈ [1, 6]
            if 20 <= _h <= 60 and 1 <= _s <= 6:
                return _h, _s
    except Exception:
        pass
    return HEALTH_DEFENSE_THRESHOLD_DEFAULT, BULL_MIN_SCORE_DEFAULT
